#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICY="$SCRIPT_DIR/totem_read_only_policy.json"
OUT_DIR="${OUT_DIR:-/tmp/dadooh-c11-1-read-only-policy-verify/$(date -u +%Y%m%dT%H%M%SZ)}"
JSON_OUT=""
SUMMARY_OUT=""
MODE="verify"

usage() {
  cat <<'USAGE'
Usage:
  verify_totem_read_only_policy.sh [--policy PATH] [--out-dir /tmp/...] [--self-test]

Read-only verifier for the C11.1 root read-only policy. It writes sanitized JSON
and summary.txt under /tmp. It does not enable read-only, remount filesystems,
restart services, change NetworkManager, read config content, call writer,
collect raw logs, install packages, reboot or poweroff.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --policy)
      shift
      POLICY="${1:-}"
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
  JSON_OUT="$OUT_DIR/read-only-policy-verify.json"
fi
if [ -z "$SUMMARY_OUT" ]; then
  SUMMARY_OUT="$OUT_DIR/summary.txt"
fi

if [ "$MODE" = "self-test" ]; then
  python3 - "$POLICY" <<'PY'
import json
import pathlib
import sys

policy = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert policy["schema_version"] == "dadooh-c11.1-read-only-policy.v1"
assert policy["root_read_only_enabled"] is False
for section in (
    "persistent_writable_paths",
    "runtime_writable_paths",
    "special_policy_paths",
    "prohibited_runtime_write_paths",
    "networkmanager_policy",
    "logs_policy",
):
    assert section in policy
special = {item["path"]: item for item in policy["special_policy_paths"]}
assert "/etc/NetworkManager/system-connections" in special
assert "/var/log/journal" in special
assert policy["networkmanager_policy"]["publish_ssid_or_credentials"] is False
assert policy["logs_policy"]["raw_logs_in_evidence"] is False
blocked = "\n".join(policy.get("must_not_publish", []))
assert "api_key" in blocked
print("self-test: ok")
PY
  exit 0
fi

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"

python3 - "$POLICY" "$JSON_OUT" "$SUMMARY_OUT" <<'PY'
import grp
import json
import os
import pathlib
import pwd
import stat
import subprocess
import sys
import time

policy_path = pathlib.Path(sys.argv[1])
json_out = pathlib.Path(sys.argv[2])
summary_out = pathlib.Path(sys.argv[3])
policy = json.loads(policy_path.read_text(encoding="utf-8"))


def run(args, timeout=8):
    try:
        return subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return None


def out(args, timeout=8):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


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


def path_meta(path_text):
    path = pathlib.Path(path_text)
    data = {"path": path_text, "exists": path.exists(), "is_symlink": path.is_symlink()}
    if not path.exists() or path.is_symlink():
        return data
    try:
        st = path.stat()
    except OSError:
        data["stat_available"] = False
        return data
    data.update(
        {
            "type": "dir" if path.is_dir() else ("file" if path.is_file() else "other"),
            "owner": owner_name(st.st_uid),
            "group": group_name(st.st_gid),
            "mode": f"{stat.S_IMODE(st.st_mode):04o}",
        }
    )
    return data


def unit_state(unit_name):
    nrestarts = out(["systemctl", "show", unit_name, "-p", "NRestarts", "--value"])
    return {
        "active": out(["systemctl", "is-active", unit_name]) or "unknown",
        "enabled": out(["systemctl", "is-enabled", unit_name]) or "unknown",
        "nrestarts": int(nrestarts) if nrestarts.isdigit() else None,
    }


def failed_count():
    text = out(["systemctl", "list-units", "--failed", "--no-legend", "--no-pager"], 10)
    return len([line for line in text.splitlines() if line.strip()])


def size_bucket_kib(kib):
    if kib is None:
        return "unknown"
    if kib == 0:
        return "empty"
    if kib < 1024:
        return "lt_1m"
    if kib < 10240:
        return "lt_10m"
    if kib < 102400:
        return "lt_100m"
    return "gte_100m"


def dir_size_bucket(path_text):
    path = pathlib.Path(path_text)
    if not path.exists() or path.is_symlink():
        return "not_present"
    result = out(["du", "-sk", path_text], 10)
    try:
        kib = int(result.split()[0])
    except Exception:
        kib = None
    return size_bucket_kib(kib)


def journald_storage():
    conf_paths = [pathlib.Path("/etc/systemd/journald.conf")]
    conf_dir = pathlib.Path("/etc/systemd/journald.conf.d")
    if conf_dir.exists() and conf_dir.is_dir() and not conf_dir.is_symlink():
        conf_paths.extend(sorted(conf_dir.glob("*.conf")))
    storage = "default"
    for conf in conf_paths:
        if not conf.exists() or conf.is_symlink():
            continue
        try:
            for raw in conf.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("Storage="):
                    storage = line.split("=", 1)[1].strip() or "default"
        except OSError:
            storage = "unknown"
    return storage


def nm_profile_policy():
    root = pathlib.Path("/etc/NetworkManager/system-connections")
    count = None
    dedicated = "unknown"
    mode_buckets = {}
    owner_group_buckets = {}
    if root.exists() and root.is_dir() and not root.is_symlink():
        try:
            files = [path for path in root.iterdir() if path.is_file() and not path.is_symlink()]
            count = len(files)
            dedicated = any(
                path.name.startswith("dadooh-c9-8-") or path.name.startswith("dadooh-product-wifi-")
                for path in files
            )
            for item in files:
                try:
                    st = item.stat()
                except OSError:
                    continue
                mode_buckets[f"{stat.S_IMODE(st.st_mode):04o}"] = mode_buckets.get(f"{stat.S_IMODE(st.st_mode):04o}", 0) + 1
                owner_group = f"{owner_name(st.st_uid)}:{group_name(st.st_gid)}"
                owner_group_buckets[owner_group] = owner_group_buckets.get(owner_group, 0) + 1
        except OSError:
            count = None
    return {
        "path": "/etc/NetworkManager/system-connections",
        "path_exists": root.exists(),
        "profile_count": count,
        "dedicated_profile_present": dedicated,
        "mode_buckets": mode_buckets,
        "owner_group_buckets": owner_group_buckets,
        "profile_names_published": False,
        "ssid_or_credentials_published": False,
        "selected_policy": policy["networkmanager_policy"]["profile_path"],
        "classification": "NEEDS_NETWORKMANAGER_POLICY",
    }


def first_json(paths):
    for raw in paths:
        path = pathlib.Path(raw)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            return data
    return {}


def process_counts():
    counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmdline = (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
        except Exception:
            continue
        if "kiosk.py" in cmdline or "/opt/totem/kiosky-player" in cmdline:
            counts["player"] += 1
        if "mpv" in cmdline:
            counts["mpv"] += 1
        if "totem_status_renderer" in cmdline or "totem_status_render_preview.py" in cmdline:
            counts["renderer"] += 1
        if "totem_setup_visual_wizard.py" in cmdline or "totem_open_settings_session.sh" in cmdline:
            counts["setup"] += 1
    return counts


def list_policy_rows(section):
    rows = []
    for item in policy.get(section, []):
        row = {key: value for key, value in item.items() if key not in {"selected_policy", "rollback", "reason"}}
        row.update(path_meta(item["path"]))
        rows.append(row)
    return rows


status = first_json(("/tmp/dadooh-status/status.json", "/data/state/kiosky-player/launcher-status.json"))
player_status = first_json(("/tmp/kiosky-status.json",))
playback = (
    status.get("playback")
    or status.get("playback_state")
    or player_status.get("playback_state")
    or player_status.get("playback")
    or "unknown"
)
special_policy_count = len(policy.get("special_policy_paths", []))
special_without_policy = [
    item.get("path", "unknown")
    for item in policy.get("special_policy_paths", [])
    if not item.get("policy_id") or not item.get("selected_policy") or not item.get("c11_2_action")
]
blockers_remaining = []
if special_without_policy:
    blockers_remaining.append("special_policy_without_c11_2_action")
if policy.get("networkmanager_policy", {}).get("c11_2_required") is not True:
    blockers_remaining.append("networkmanager_c11_2_action_missing")
if policy.get("logs_policy", {}).get("c11_2_required") is not True:
    blockers_remaining.append("journald_c11_2_action_missing")

payload = {
    "schema_version": "dadooh-c11.1-read-only-policy-verify.v1",
    "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "policy_schema_version": policy.get("schema_version"),
    "rules": {
        "read_only_enabled": False,
        "poweroff_executed": False,
        "reboot_executed": False,
        "writer_called": False,
        "real_config_read": False,
        "real_config_written": False,
        "wifi_changed": False,
        "networkmanager_changed": False,
        "packages_installed": False,
        "raw_logs_published": False,
        "secrets_published": False,
    },
    "services": {
        "kiosky-player.service": unit_state("kiosky-player.service"),
        "totem-settings-trigger.service": unit_state("totem-settings-trigger.service"),
        "dadooh-visual-splash.service": unit_state("dadooh-visual-splash.service"),
    },
    "public_state": status.get("public_state") or status.get("state") or "unknown",
    "playback": playback,
    "process_counts": process_counts(),
    "systemctl_failed_count": failed_count(),
    "persistent_writable_paths": list_policy_rows("persistent_writable_paths"),
    "runtime_writable_paths": list_policy_rows("runtime_writable_paths"),
    "special_policy_paths": list_policy_rows("special_policy_paths"),
    "prohibited_runtime_write_paths": list_policy_rows("prohibited_runtime_write_paths"),
    "networkmanager": nm_profile_policy(),
    "journald": {
        "storage": journald_storage(),
        "persistent_dir_present": pathlib.Path("/var/log/journal").exists(),
        "persistent_dir_size_bucket": dir_size_bucket("/var/log/journal"),
        "selected_policy": policy["logs_policy"]["journald"],
        "classification": "NEEDS_LOG_POLICY",
        "raw_logs_published": False,
    },
    "var_policy": {
        "var_lib_systemd": path_meta("/var/lib/systemd"),
        "var_lib_networkmanager": path_meta("/var/lib/NetworkManager"),
        "selected_policy": "volatile_or_overlay_runtime_state_to_validate_in_c11_2",
    },
    "boot_policy": {
        "boot_path": "/boot",
        "boot_env_present": pathlib.Path("/boot/armbianEnv.txt").exists(),
        "normal_runtime_write_allowed": policy["boot_policy"]["normal_runtime_write_allowed"],
    },
    "policy_completeness": {
        "special_policy_count": special_policy_count,
        "special_without_policy_count": len(special_without_policy),
        "networkmanager_policy_defined": True,
        "journald_policy_defined": True,
        "boot_policy_defined": True,
        "data_tmp_run_policy_defined": True,
    },
    "blockers_remaining": blockers_remaining,
    "root_read_only_ready": False,
    "ready_for_read_only_enablement": False,
    "ready_for_c11_2_enablement": not blockers_remaining,
    "recommendation": "C11.2 pode aplicar mitigacoes reversiveis se policy_completeness estiver completa; ainda nao habilitar read-only antes da rodada C11.2.",
}

json_out.parent.mkdir(parents=True, exist_ok=True)
json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(json_out, 0o600)
lines = [
    "C11.1 read-only policy verify",
    f"policy_schema_version: {payload['policy_schema_version']}",
    f"root_read_only_ready: {payload['root_read_only_ready']}",
    f"ready_for_read_only_enablement: {payload['ready_for_read_only_enablement']}",
    f"ready_for_c11_2_enablement: {payload['ready_for_c11_2_enablement']}",
    f"blockers_remaining_count: {len(blockers_remaining)}",
    f"networkmanager_policy: {payload['networkmanager']['classification']}",
    f"journald_policy: {payload['journald']['classification']}",
    "read_only_enabled: false",
    "poweroff_executed: false",
    "reboot_executed: false",
    "writer_called: false",
    "real_config_read: false",
    "real_config_written: false",
    "wifi_changed: false",
    "raw_logs_published: false",
    "secrets_published: false",
]
summary_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
os.chmod(summary_out, 0o600)
PY
