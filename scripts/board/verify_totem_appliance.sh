#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MANIFEST="$SCRIPT_DIR/totem_appliance_manifest.json"
OUT_DIR="${OUT_DIR:-/tmp/dadooh-c10-8-appliance-verify/$(date -u +%Y%m%dT%H%M%SZ)}"
JSON_OUT=""
SUMMARY_OUT=""
MODE="verify"

usage() {
  cat <<'USAGE'
Usage:
  verify_totem_appliance.sh [--manifest PATH] [--repo-root PATH] [--out-dir /tmp/...] [--self-test]

Read-only verifier for the Dadooh Orange Pi appliance layer. It compares the
installed board state with scripts/board/totem_appliance_manifest.json and
writes sanitized JSON plus summary.txt under /tmp.

It does not read config.json content, publish Wi-Fi details, collect logs,
change services, call writer, alter NetworkManager, run apt, or reboot.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --manifest|--manifest-path)
      shift
      MANIFEST="${1:-}"
      ;;
    --repo-root)
      shift
      REPO_ROOT="${1:-}"
      ;;
    --out-dir)
      shift
      OUT_DIR="${1:-}"
      ;;
    --json-out)
      shift
      JSON_OUT="${1:-}"
      ;;
    --summary-out)
      shift
      SUMMARY_OUT="${1:-}"
      ;;
    --self-test)
      MODE="self-test"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "error: unsupported argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

case "$OUT_DIR" in
  /tmp/*) ;;
  *) echo "error: --out-dir must be under /tmp" >&2; exit 2 ;;
esac

if [ -z "$JSON_OUT" ]; then
  JSON_OUT="$OUT_DIR/verify.json"
fi
if [ -z "$SUMMARY_OUT" ]; then
  SUMMARY_OUT="$OUT_DIR/summary.txt"
fi

if [ "$MODE" = "self-test" ]; then
  python3 - "$MANIFEST" "$REPO_ROOT" <<'PY'
import json
import pathlib
import sys

manifest = pathlib.Path(sys.argv[1])
repo = pathlib.Path(sys.argv[2])
data = json.loads(manifest.read_text(encoding="utf-8"))
assert data["schema_version"] == "dadooh-totem-appliance-manifest.v1"
for section in ("bin_scripts", "systemd_units", "paths", "runtime", "never_embed"):
    assert section in data
for item in data["bin_scripts"] + data.get("extra_files", []) + data["systemd_units"]:
    src = repo / item["source"]
    assert src.exists(), item["source"]
    assert item["target"].startswith("/")
for path in data["private_or_field_provisioned_files"]:
    assert "api_key" not in path.lower()
assert data["kiosky_player"]["pin_status"] in {"PIN_MISSING", "PINNED"}
print("self-test: ok")
PY
  exit 0
fi

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"

python3 - "$MANIFEST" "$REPO_ROOT" "$JSON_OUT" "$SUMMARY_OUT" <<'PY'
import grp
import hashlib
import json
import os
import pathlib
import pwd
import shlex
import stat
import subprocess
import sys
import time

manifest_path = pathlib.Path(sys.argv[1])
repo_root = pathlib.Path(sys.argv[2])
json_out = pathlib.Path(sys.argv[3])
summary_out = pathlib.Path(sys.argv[4])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))


def run(args, timeout=6):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except Exception:
        return None


def out(args, timeout=6):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


def repo_value(command, fallback_name):
    value = out(["git", "-C", str(repo_root), *command], 5)
    if value:
        return value
    fallback = repo_root / fallback_name
    if fallback.exists() and not fallback.is_symlink():
        try:
            return fallback.read_text(encoding="utf-8").strip() or "unknown"
        except OSError:
            return "unknown"
    return "unknown"


def repo_dirty_entries():
    status = out(["git", "-C", str(repo_root), "status", "--short"], 5)
    if status:
        return len([line for line in status.splitlines() if line.strip()])
    fallback = repo_root / ".orange_pi_totem_dirty_entries"
    if fallback.exists() and not fallback.is_symlink():
        try:
            return int(fallback.read_text(encoding="utf-8").strip() or "0")
        except Exception:
            return 0
    return 0


def sha(path):
    path = pathlib.Path(path)
    if not path.exists() or not path.is_file() or path.is_symlink():
        return "missing"
    try:
        if path.stat().st_size > 4 * 1024 * 1024:
            return "skipped_large"
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return "unavailable"


def owner_name(uid):
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return f"uid:{uid}"


def group_name(gid):
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return f"gid:{gid}"


def stat_meta(path):
    path = pathlib.Path(path)
    data = {"exists": path.exists()}
    if not path.exists():
        return data
    try:
        st = path.lstat()
    except OSError:
        data["stat_error"] = True
        return data
    data.update(
        {
            "type": "symlink" if path.is_symlink() else ("dir" if path.is_dir() else "file"),
            "mode": f"{stat.S_IMODE(st.st_mode):04o}",
            "owner": owner_name(st.st_uid),
            "group": group_name(st.st_gid),
        }
    )
    return data


def pkg_present(name):
    result = run(["dpkg-query", "-W", "-f=${Status}", name], 5)
    return bool(result is not None and result.returncode == 0 and (result.stdout or "").strip() == "install ok installed")


def command_present(name):
    return bool(out(["sh", "-c", f"command -v {shlex.quote(name)}"], 4))


def unit_state(unit_name):
    return {
        "active": out(["systemctl", "is-active", unit_name], 5) or "unknown",
        "enabled": out(["systemctl", "is-enabled", unit_name], 5) or "unknown",
        "fragment_path": out(["systemctl", "show", unit_name, "-p", "FragmentPath", "--value"], 5) or "",
    }


def file_compare(item):
    source = repo_root / item["source"]
    target = pathlib.Path(item["target"])
    meta = stat_meta(target)
    source_hash = sha(source)
    target_hash = sha(target)
    checks = {
        "source_present": source.exists(),
        "target_present": target.exists(),
        "hash_match": source_hash == target_hash and source_hash not in {"missing", "unavailable"},
        "mode_ok": meta.get("mode") == item.get("mode"),
        "owner_ok": meta.get("owner") == item.get("owner"),
        "group_ok": meta.get("group") == item.get("group"),
    }
    return {
        "source": item["source"],
        "target": item["target"],
        "meta": meta,
        "source_sha256": source_hash,
        "target_sha256": target_hash,
        "checks": checks,
        "ok": all(checks.values()),
    }


def path_check(item):
    meta = stat_meta(item["path"])
    checks = {
        "exists": meta.get("exists") is True,
        "type_ok": meta.get("type") == item.get("type"),
        "mode_ok": meta.get("mode") == item.get("mode"),
        "owner_ok": meta.get("owner") == item.get("owner"),
        "group_ok": meta.get("group") == item.get("group"),
    }
    return {
        "path": item["path"],
        "runtime_state": bool(item.get("runtime_state")),
        "content_policy": item.get("content_policy", "exact_metadata_only_no_content_hash"),
        "content_hash_compared": False,
        "timestamp_compared": False,
        "raw_content_read": False,
        "meta": meta,
        "checks": checks,
        "ok": all(checks.values()),
    }


def user_check():
    spec = manifest["users"]["totem"]
    exists = run(["id", spec["user"]], 4)
    group = run(["getent", "group", spec["group"]], 4)
    groups = out(["id", "-nG", spec["user"]], 4).split() if exists is not None and exists.returncode == 0 else []
    optional = {}
    for group_name_ in spec.get("supplementary_groups_if_present", []):
        present = run(["getent", "group", group_name_], 4)
        optional[group_name_] = {"group_exists": bool(present is not None and present.returncode == 0), "user_member": group_name_ in groups}
    ok = bool(exists is not None and exists.returncode == 0 and group is not None and group.returncode == 0 and spec["group"] in groups)
    missing_optional_membership = [name for name, value in optional.items() if value["group_exists"] and not value["user_member"]]
    return {
        "user_exists": bool(exists is not None and exists.returncode == 0),
        "group_exists": bool(group is not None and group.returncode == 0),
        "groups": groups,
        "optional_groups": optional,
        "ok": ok and not missing_optional_membership,
        "missing_optional_membership": missing_optional_membership,
    }


def boot_check():
    spec = manifest["boot_visual_guardrails"]
    path = pathlib.Path(spec["armbian_env"])
    parsed = {}
    if path.exists() and not path.is_symlink():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            parsed[key.strip()] = value.strip().strip('"')
    extraargs = set(parsed.get("extraargs", "").split())
    key_checks = {key: parsed.get(key) == value for key, value in spec["set_keys"].items()}
    token_checks = {token: token in extraargs for token in spec["required_extraargs_tokens"]}
    gettys = {}
    for unit_name in spec.get("getty_units_disabled", []):
        state = unit_state(unit_name)
        gettys[unit_name] = {
            "active": state["active"],
            "enabled": state["enabled"],
            "ok": state["active"] in {"inactive", "unknown"} and state["enabled"] in {"disabled", "masked", "static", "unknown"},
        }
    ok = bool(path.exists() and all(key_checks.values()) and all(token_checks.values()) and all(item["ok"] for item in gettys.values()))
    return {
        "armbian_env_exists": path.exists(),
        "set_key_checks": key_checks,
        "extraargs_token_checks": token_checks,
        "getty_units": gettys,
        "backup_state_dir_present": pathlib.Path(spec["backup_state_dir"]).exists(),
        "ok": ok,
    }


def orientation_check():
    spec = manifest["public_orientation"]
    path = pathlib.Path(spec["path"])
    meta = stat_meta(path)
    data = {}
    parse_ok = False
    if path.exists() and not path.is_symlink():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = {key: raw.get(key) for key in spec["allowed_fields"]}
                parse_ok = set(raw) <= set(spec["allowed_fields"])
        except Exception:
            parse_ok = False
    checks = {
        "exists": path.exists(),
        "parse_ok": parse_ok,
        "schema_ok": data.get("schema_version") == spec["schema_version"],
        "rotation_ok": data.get("rotation_deg") in spec["allowed_rotation_deg"],
        "mode_ok": meta.get("mode") == spec["mode"],
        "owner_ok": meta.get("owner") == spec["owner"],
        "group_ok": meta.get("group") == spec["group"],
    }
    return {"path": str(path), "public_fields": data, "meta": meta, "checks": checks, "ok": all(checks.values())}


def config_private_check():
    path = pathlib.Path("/data/config/config.json")
    meta = stat_meta(path)
    return {
        "present_on_dev": path.exists(),
        "content_read": False,
        "owner_mode_ok_if_present": (not path.exists()) or (meta.get("owner") == "root" and meta.get("group") == "totem" and meta.get("mode") == "0640"),
        "meta": meta,
        "image_policy": "private_or_field_provisioned_do_not_embed",
    }


def app_pin_check():
    spec = manifest["kiosky_player"]
    app = pathlib.Path(spec["install_path"])
    marker = pathlib.Path("/data/state/totem-appliance/kiosky-player-installed.json")
    has_git = (app / ".git").exists()
    head = out(["git", "-C", str(app), "rev-parse", "HEAD"], 8) if has_git else "unknown"
    branch = out(["git", "-C", str(app), "rev-parse", "--abbrev-ref", "HEAD"], 8) if has_git else "unknown"
    remote = out(["git", "-C", str(app), "config", "--get", "remote.origin.url"], 8) if has_git else "unknown"
    expected = spec.get("expected_commit")
    pin_missing = spec.get("pin_status") == "PIN_MISSING" or expected == "PIN_MISSING"
    git_required_on_dev = bool(spec.get("expected_git_metadata_on_dev", spec.get("expected_git_metadata", True)))
    path_exists = app.exists()
    if pin_missing:
        pin_ok = False
        blocker = "PIN_MISSING"
        verification_level = "missing_pin"
    elif not path_exists:
        pin_ok = False
        blocker = "APP_MISSING"
        verification_level = "pinned_app_missing"
    elif has_git:
        pin_ok = head == expected
        blocker = None if pin_ok else "PIN_MISMATCH"
        verification_level = "git_head"
    elif git_required_on_dev:
        pin_ok = False
        blocker = "GIT_METADATA_MISSING"
        verification_level = "git_metadata_required_missing"
    else:
        marker_ok = False
        if marker.exists() and not marker.is_symlink():
            try:
                raw_marker = json.loads(marker.read_text(encoding="utf-8"))
                if isinstance(raw_marker, dict):
                    marker_ok = (
                        raw_marker.get("commit") == expected
                        and raw_marker.get("ref") == spec.get("expected_ref")
                        and raw_marker.get("repo_full_name") in {spec.get("repo_full_name"), spec.get("expected_repo")}
                        and raw_marker.get("private_values_included") is False
                    )
            except Exception:
                marker_ok = False
        pin_ok = True
        blocker = None
        verification_level = "installed_marker" if marker_ok else "documented_pin_installed_tree_without_git_metadata"
    return {
        "path_exists": path_exists,
        "git_metadata_present": has_git,
        "installed_marker_present": marker.exists(),
        "branch": branch,
        "remote": remote,
        "head": head,
        "repo_full_name": spec.get("repo_full_name") or spec.get("expected_repo"),
        "expected_ref": spec.get("expected_ref"),
        "expected_commit": expected,
        "expected_commit_short": spec.get("expected_commit_short"),
        "pin_status": spec.get("pin_status"),
        "pin_source": spec.get("pin_source"),
        "git_metadata_required_on_dev": git_required_on_dev,
        "verification_level": verification_level,
        "pin_ok": pin_ok,
        "blocker": blocker,
        "warning": None if has_git or not path_exists or verification_level == "installed_marker" else "installed_tree_commit_not_machine_verifiable_without_git_metadata",
    }


def service_unit_check(item):
    file_result = file_compare({**item, "owner": "root", "group": "root", "mode": "0644"})
    unit_name = pathlib.Path(item["target"]).name
    state = unit_state(unit_name)
    if item.get("enabled") is True:
        enabled_ok = state["enabled"] == "enabled"
    else:
        enabled_ok = state["enabled"] == item.get("enabled_state", "disabled")
    active_expected = item.get("active_expected_on_dev")
    active_ok = state["active"] == active_expected if active_expected else True
    return {
        **file_result,
        "unit": unit_name,
        "state": state,
        "enabled_ok": enabled_ok,
        "active_ok": active_ok,
        "ok": file_result["ok"] and enabled_ok and active_ok,
    }


repo_head = repo_value(["rev-parse", "HEAD"], ".orange_pi_totem_head")
repo_branch = repo_value(["rev-parse", "--abbrev-ref", "HEAD"], ".orange_pi_totem_branch")
repo_dirty_entries = repo_dirty_entries()

script_results = [file_compare(item) for item in manifest["bin_scripts"]]
extra_file_results = [file_compare(item) for item in manifest.get("extra_files", [])]
unit_results = [service_unit_check(item) for item in manifest["systemd_units"]]
path_results = [path_check(item) for item in manifest["paths"]]
runtime = {
    "commands": {name: command_present(name) for name in manifest["runtime"]["required_commands"]},
    "packages": {name: pkg_present(name) for name in manifest["runtime"]["required_debian_packages"]},
    "forbidden_commands_present": {name: command_present(name) for name in manifest["runtime"]["forbidden_commands"]},
    "forbidden_packages_present": {name: pkg_present(name) for name in manifest["runtime"]["forbidden_packages"]},
}
runtime["ok"] = all(runtime["commands"].values()) and all(runtime["packages"].values()) and not any(runtime["forbidden_commands_present"].values()) and not any(runtime["forbidden_packages_present"].values())

user_result = user_check()
boot_result = boot_check()
orientation_result = orientation_check()
config_result = config_private_check()
pin_result = app_pin_check()
system_failed_raw = out(["systemctl", "--failed", "--no-legend", "--plain"], 8)
system_failed_count = 0 if not system_failed_raw else len([line for line in system_failed_raw.splitlines() if line.strip()])

blockers = []
warnings = []
for label, collection in (
    ("path", path_results),
    ("script", script_results),
    ("extra_file", extra_file_results),
    ("unit", unit_results),
):
    for item in collection:
        if not item["ok"]:
            blockers.append(f"{label}:{item.get('path') or item.get('target') or item.get('unit')}")
if not runtime["ok"]:
    blockers.append("runtime_minimum_or_forbidden_runtime")
if not user_result["ok"]:
    blockers.append("totem_user_or_groups")
if not boot_result["ok"]:
    blockers.append("boot_visual_guardrails")
if not orientation_result["ok"]:
    blockers.append("public_orientation_contract")
if system_failed_count != 0:
    blockers.append("systemctl_failed_nonzero")
if config_result["present_on_dev"] and not config_result["owner_mode_ok_if_present"]:
    blockers.append("private_config_owner_mode")
if pin_result["blocker"]:
    blockers.append(f"kiosky_player_{pin_result['blocker']}")
if pin_result.get("warning"):
    warnings.append(f"kiosky_player_{pin_result['warning']}")

payload = {
    "schema_version": "dadooh-c10.8-appliance-verify.v1",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "rules": {
        "read_only": True,
        "config_content_read": False,
        "writer_called": False,
        "network_changed": False,
        "services_changed": False,
        "apt_called": False,
        "reboot_called": False,
        "raw_logs_collected": False,
        "sensitive_values_published": False,
    },
    "repo": {
        "branch": repo_branch,
        "head": repo_head,
        "dirty_entries": repo_dirty_entries,
    },
    "system": {
        "systemctl_failed_count": system_failed_count,
    },
    "runtime": runtime,
    "user": user_result,
    "paths": path_results,
    "bin_scripts": script_results,
    "extra_files": extra_file_results,
    "systemd_units": unit_results,
    "boot_visual_guardrails": boot_result,
    "public_orientation": orientation_result,
    "private_config": config_result,
    "kiosky_player": pin_result,
    "private_or_field_provisioned_files": manifest["private_or_field_provisioned_files"],
    "never_embed": manifest["never_embed"],
    "blockers": blockers,
    "warnings": warnings,
    "ready_for_second_board": len(blockers) == 0,
    "overall_status": "ok" if not blockers else "differences_found",
}

json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(json_out, 0o600)

lines = [
    "C10.8 appliance verify summary",
    f"repo_branch={repo_branch}",
    f"repo_head={repo_head}",
    f"repo_dirty_entries={repo_dirty_entries}",
    f"overall_status={payload['overall_status']}",
    f"ready_for_second_board={str(payload['ready_for_second_board']).lower()}",
    f"systemctl_failed_count={system_failed_count}",
    f"runtime_ok={str(runtime['ok']).lower()}",
    f"user_ok={str(user_result['ok']).lower()}",
    f"boot_guardrails_ok={str(boot_result['ok']).lower()}",
    f"orientation_ok={str(orientation_result['ok']).lower()}",
    f"private_config_present_on_dev={str(config_result['present_on_dev']).lower()}",
    f"private_config_content_read=false",
    f"kiosky_player_pin_status={pin_result['pin_status']}",
    f"kiosky_player_verification_level={pin_result['verification_level']}",
]
if blockers:
    lines.append("blockers:")
    lines.extend(f"- {item}" for item in blockers)
else:
    lines.append("blockers: none")
if warnings:
    lines.append("warnings:")
    lines.extend(f"- {item}" for item in warnings)
summary_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
os.chmod(summary_out, 0o600)
print(f"verify_json={json_out}")
print(f"summary={summary_out}")
print(f"overall_status={payload['overall_status']}")
PY
