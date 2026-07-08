#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MANIFEST="$SCRIPT_DIR/totem_appliance_manifest.json"
MODE=""
OUT_DIR="${OUT_DIR:-/tmp/dadooh-c10-8-appliance-installer/$(date -u +%Y%m%dT%H%M%SZ)}"
INSTALL_RUNTIME=0
INSTALL_READONLY_PREREQS=0
MANAGE_RUNNING_SERVICES=0

usage() {
  cat <<'USAGE'
Usage:
  install_totem_appliance.sh [mode] [options]

Modes:
  --dry-run
      Build a sanitized action plan. Does not change the board.

  --apply
      Apply the appliance layer from this repo copy. Requires root. Does not
      start/restart product services by default.

  --verify
      Run verify_totem_appliance.sh against the manifest.

  --manifest
      Emit a sanitized manifest copy under /tmp.

  --idempotence-check
      Run the dry-run planner twice and confirm the output is stable.

Options:
  --manifest-path PATH
  --repo-root PATH
  --out-dir /tmp/...
  --install-runtime
      With --apply only, run explicit apt-get install --no-install-recommends
      for the minimal runtime packages. Never runs upgrade/full-upgrade/
      dist-upgrade/armbian-upgrade.

  --install-readonly-prereqs
      With --dry-run or --apply only, plan/apply the exact read-only
      prerequisite package declared by the manifest. This never enables
      read-only and never runs upgrade/full-upgrade/dist-upgrade/
      armbian-upgrade.

  --manage-running-services
      With --apply only, allow stopping getty guardrail units. Product services
      are still not restarted by this installer.

The installer never reads config.json content, never creates private config,
never embeds Wi-Fi credentials, never calls writer, never changes NetworkManager
profiles, and never installs desktop/Chromium/Xorg/Wayland/compositor.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) MODE="dry-run" ;;
    --apply) MODE="apply" ;;
    --verify) MODE="verify" ;;
    --manifest) MODE="manifest" ;;
    --idempotence-check) MODE="idempotence-check" ;;
    --manifest-path)
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
    --install-runtime)
      INSTALL_RUNTIME=1
      ;;
    --install-readonly-prereqs)
      INSTALL_READONLY_PREREQS=1
      ;;
    --manage-running-services)
      MANAGE_RUNNING_SERVICES=1
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

if [ -z "$MODE" ]; then
  echo "error: choose one mode" >&2
  usage >&2
  exit 2
fi

case "$OUT_DIR" in
  /tmp/*) ;;
  *) echo "error: --out-dir must be under /tmp" >&2; exit 2 ;;
esac

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"

if [ "$MODE" = "verify" ]; then
  exec "$SCRIPT_DIR/verify_totem_appliance.sh" --manifest "$MANIFEST" --repo-root "$REPO_ROOT" --out-dir "$OUT_DIR/verify"
fi

if [ "$MODE" = "manifest" ]; then
  python3 -m json.tool "$MANIFEST" > "$OUT_DIR/totem_appliance_manifest.json"
  chmod 600 "$OUT_DIR/totem_appliance_manifest.json"
  printf 'manifest=%s\n' "$OUT_DIR/totem_appliance_manifest.json"
  exit 0
fi

if [ "$MODE" = "apply" ] && [ "$(id -u)" -ne 0 ]; then
  echo "error: --apply requires root" >&2
  exit 1
fi

if [ "$INSTALL_RUNTIME" -eq 1 ] && [ "$MODE" != "apply" ]; then
  echo "error: --install-runtime is only valid with --apply" >&2
  exit 2
fi

if [ "$INSTALL_READONLY_PREREQS" -eq 1 ] && [ "$MODE" != "apply" ] && [ "$MODE" != "dry-run" ]; then
  echo "error: --install-readonly-prereqs is only valid with --dry-run or --apply" >&2
  exit 2
fi

if [ "$MANAGE_RUNNING_SERVICES" -eq 1 ] && [ "$MODE" != "apply" ]; then
  echo "error: --manage-running-services is only valid with --apply" >&2
  exit 2
fi

run_planner() {
  local planner_mode="$1"
  local output_json="$2"
  local summary_txt="$3"
  python3 - "$MANIFEST" "$REPO_ROOT" "$planner_mode" "$INSTALL_RUNTIME" "$INSTALL_READONLY_PREREQS" "$MANAGE_RUNNING_SERVICES" "$output_json" "$summary_txt" <<'PY'
import grp
import hashlib
import json
import os
import pathlib
import pwd
import shutil
import stat
import subprocess
import sys
import time

manifest_path = pathlib.Path(sys.argv[1])
repo_root = pathlib.Path(sys.argv[2])
mode = sys.argv[3]
install_runtime = sys.argv[4] == "1"
install_readonly_prereqs = sys.argv[5] == "1"
manage_running_services = sys.argv[6] == "1"
output_json = pathlib.Path(sys.argv[7])
summary_txt = pathlib.Path(sys.argv[8])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
actions = []
blockers = []
warnings = []
changed = []
action_keys = set()


def run(args, timeout=20):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except Exception:
        return None


def out(args, timeout=20):
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


def action(kind, target, reason, apply_safe=True):
    key = (kind, target)
    if key in action_keys:
        return None
    action_keys.add(key)
    item = {"kind": kind, "target": target, "reason": reason, "apply_safe": apply_safe}
    actions.append(item)
    return item


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


def exists_user(name):
    result = run(["id", name], 5)
    return result is not None and result.returncode == 0


def exists_group(name):
    result = run(["getent", "group", name], 5)
    return result is not None and result.returncode == 0


def uid(name):
    return pwd.getpwnam(name).pw_uid


def gid(name):
    return grp.getgrnam(name).gr_gid


def owner_name(path):
    try:
        return pwd.getpwuid(path.lstat().st_uid).pw_name
    except Exception:
        return "unknown"


def group_name(path):
    try:
        return grp.getgrgid(path.lstat().st_gid).gr_name
    except Exception:
        return "unknown"


def mode_str(path):
    try:
        return f"{stat.S_IMODE(path.lstat().st_mode):04o}"
    except Exception:
        return "unknown"


def chmod_chown(path, owner, group, mode_text):
    os.chown(path, uid(owner), gid(group))
    os.chmod(path, int(mode_text, 8))


def ensure_user():
    spec = manifest["users"]["totem"]
    user = spec["user"]
    group = spec["group"]
    if not exists_group(group):
        action("create_group", group, "required appliance group missing")
        if mode == "apply":
            subprocess.run(["groupadd", "--system", group], check=True)
            changed.append(f"group:{group}")
    if not exists_user(user):
        shell = "/usr/sbin/nologin" if pathlib.Path("/usr/sbin/nologin").exists() else "/sbin/nologin"
        if not pathlib.Path(shell).exists():
            blockers.append("nologin_shell_missing")
            return
        action("create_user", user, "required appliance user missing")
        if mode == "apply":
            subprocess.run([
                "useradd",
                "--system",
                "--gid",
                group,
                "--home-dir",
                spec["home"],
                "--no-create-home",
                "--shell",
                shell,
                user,
            ], check=True)
            subprocess.run(["passwd", "-l", user], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            changed.append(f"user:{user}")
    if exists_user(user):
        groups = set(out(["id", "-nG", user], 5).split())
        for extra in spec.get("supplementary_groups_if_present", []):
            if exists_group(extra) and extra not in groups:
                action("add_user_to_group", f"{user}:{extra}", "optional hardware group exists and user is not a member")
                if mode == "apply":
                    subprocess.run(["usermod", "-aG", extra, user], check=True)
                    changed.append(f"group-membership:{user}:{extra}")


def check_runtime():
    runtime = manifest["runtime"]
    for command in runtime["required_commands"]:
        if shutil.which(command) is None:
            action("runtime_command_missing", command, "required runtime command missing", apply_safe=install_runtime)
    missing_packages = []
    for package in runtime["required_debian_packages"]:
        result = run(["dpkg-query", "-W", "-f=${Status}", package], 6)
        present = bool(result is not None and result.returncode == 0 and (result.stdout or "").strip() == "install ok installed")
        if not present:
            missing_packages.append(package)
    if missing_packages:
        if install_runtime:
            action("apt_install_runtime", ",".join(missing_packages), "explicit --install-runtime provided")
            if mode == "apply":
                subprocess.run(["apt-get", "install", "-y", "--no-install-recommends", *missing_packages], check=True)
                changed.append("runtime-packages")
        else:
            action("runtime_packages_missing", ",".join(missing_packages), "missing packages; --install-runtime not provided", apply_safe=False)
            blockers.append("runtime_packages_missing")
    for command in runtime["required_commands"]:
        if shutil.which(command) is None:
            if mode == "dry-run" and install_runtime:
                warnings.append(f"runtime_command_missing_pending_explicit_runtime_install:{command}")
            else:
                blockers.append(f"runtime_command_missing:{command}")
    for command in runtime["forbidden_commands"]:
        if shutil.which(command) is not None:
            blockers.append(f"forbidden_command_present:{command}")
    for package in runtime["forbidden_packages"]:
        result = run(["dpkg-query", "-W", "-f=${Status}", package], 6)
        present = bool(result is not None and result.returncode == 0 and (result.stdout or "").strip() == "install ok installed")
        if present:
            blockers.append(f"forbidden_package_present:{package}")


def check_readonly_prerequisites():
    prereq = manifest.get("read_only_prerequisites", {})
    if not prereq:
        return
    packages = list(prereq.get("required_debian_packages", []))
    commands = list(prereq.get("required_commands", []))
    missing_packages = []
    for package in packages:
        result = run(["dpkg-query", "-W", "-f=${Status}", package], 6)
        present = bool(result is not None and result.returncode == 0 and (result.stdout or "").strip() == "install ok installed")
        if not present:
            missing_packages.append(package)
    if missing_packages:
        if install_readonly_prereqs:
            action("apt_install_readonly_prereqs", ",".join(missing_packages), "explicit --install-readonly-prereqs provided")
            if mode == "apply":
                subprocess.run(["apt-get", "install", "-y", "--no-upgrade", "--no-install-recommends", *missing_packages], check=True)
                changed.append("readonly-prereq-packages")
        else:
            action("readonly_prereq_packages_missing", ",".join(missing_packages), "missing read-only prerequisites; --install-readonly-prereqs not provided", apply_safe=False)
    for command in commands:
        if shutil.which(command) is None:
            if install_readonly_prereqs:
                warnings.append(f"readonly_prereq_command_missing_pending_explicit_install:{command}")
            else:
                warnings.append(f"readonly_prereq_command_missing:{command}")


def ensure_dir(item):
    path = pathlib.Path(item["path"])
    if not path.exists():
        action("create_dir", str(path), f"expected {item['mode']} {item['owner']}:{item['group']}")
        if mode == "apply":
            path.mkdir(parents=True, exist_ok=True)
            chmod_chown(path, item["owner"], item["group"], item["mode"])
            changed.append(str(path))
        return
    if not path.is_dir() or path.is_symlink():
        blockers.append(f"path_not_plain_directory:{path}")
        return
    if mode_str(path) != item["mode"] or owner_name(path) != item["owner"] or group_name(path) != item["group"]:
        action("fix_dir_metadata", str(path), f"expected {item['mode']} {item['owner']}:{item['group']}")
        if mode == "apply":
            chmod_chown(path, item["owner"], item["group"], item["mode"])
            changed.append(str(path))


def manifest_path_item(path, fallback):
    path_text = str(path)
    for item in manifest["paths"]:
        if item.get("path") == path_text:
            return item
    return fallback


def copy_file(item):
    source = repo_root / item["source"]
    target = pathlib.Path(item["target"])
    if not source.exists() or not source.is_file():
        blockers.append(f"missing_repo_source:{item['source']}")
        return False
    target_parent = target.parent
    if not target_parent.exists():
        action("create_parent_dir", str(target_parent), "parent for installed file missing")
        if mode == "apply":
            target_parent.mkdir(parents=True, exist_ok=True)
            changed.append(str(target_parent))
    needs_copy = not target.exists() or sha(source) != sha(target)
    needs_meta = target.exists() and (mode_str(target) != item["mode"] or owner_name(target) != item["owner"] or group_name(target) != item["group"])
    if needs_copy or needs_meta:
        action("install_file", str(target), item["source"])
        if mode == "apply":
            shutil.copy2(source, target)
            chmod_chown(target, item["owner"], item["group"], item["mode"])
            changed.append(str(target))
        return True
    return False


def ensure_files():
    daemon_reload_needed = False
    for item in manifest["bin_scripts"]:
        copy_file(item)
    for item in manifest.get("extra_files", []):
        copy_file(item)
    for item in manifest["systemd_units"]:
        if copy_file({**item, "owner": "root", "group": "root", "mode": "0644"}):
            daemon_reload_needed = True
    if daemon_reload_needed:
        action("systemctl_daemon_reload", "systemd", "unit files changed")
        if mode == "apply":
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            changed.append("systemd-daemon-reload")
    for item in manifest["systemd_units"]:
        unit = pathlib.Path(item["target"]).name
        enabled = out(["systemctl", "is-enabled", unit], 6) or "unknown"
        if item.get("enabled") is True and enabled != "enabled":
            action("enable_unit", unit, "manifest requires service enabled")
            if mode == "apply":
                subprocess.run(["systemctl", "enable", unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                changed.append(f"enable:{unit}")
        if item.get("enabled") is False and item.get("enabled_state") != "static" and enabled not in {"disabled", "masked"}:
            action("disable_unit", unit, "manifest requires service disabled")
            if mode == "apply":
                subprocess.run(["systemctl", "disable", unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                changed.append(f"disable:{unit}")


def write_text_file(target, text, mode_text="0644", reason="generated appliance metadata"):
    target = pathlib.Path(target)
    current = None
    if target.exists() and not target.is_symlink() and target.is_file():
        try:
            current = target.read_text(encoding="utf-8")
        except OSError:
            current = None
    if current == text and mode_str(target) == mode_text and owner_name(target) == "root" and group_name(target) == "root":
        return
    action("write_text_file", str(target), reason)
    if mode == "apply":
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.tmp")
        tmp.write_text(text, encoding="utf-8")
        chmod_chown(tmp, "root", "root", mode_text)
        os.replace(tmp, target)
        changed.append(str(target))


def ensure_totem_core_image_embed():
    spec = manifest.get("totem_core_image_embed", {})
    if not spec or spec.get("enabled") is not True:
        return
    version = str(spec.get("current_version") or "").strip()
    core_files = list(spec.get("core_files") or [])
    if not version:
        blockers.append("totem_core_image_embed_current_version_missing")
        return
    if not core_files:
        blockers.append("totem_core_image_embed_core_files_missing")
        return

    layout = spec.get("layout") or {}
    base_dir = pathlib.Path(str(layout.get("base") or "/data/core/totem"))
    releases_dir = base_dir / "releases"
    release_dir = releases_dir / version
    release_bin = release_dir / "bin"
    fallback_bin = pathlib.Path(str(layout.get("fallback") or "/opt/totem/core-fallback/bin"))
    wrappers_bin = pathlib.Path(str(layout.get("wrappers") or "/opt/totem/bin"))
    current_link = pathlib.Path(str(layout.get("current") or "/data/core/totem/current"))
    current_target = str(layout.get("current_target") or f"releases/{version}")

    for path in (base_dir, releases_dir, release_dir, release_bin, release_dir / "health", release_dir / "manifest-fragment", fallback_bin, wrappers_bin):
        ensure_dir({"path": str(path), "type": "dir", "owner": "root", "group": "root", "mode": "0755"})

    wrapper_py = "scripts/board/totem_core_exec.py"
    wrapper_sh = "scripts/board/totem_core_exec.sh"
    copy_file({"source": wrapper_py, "target": str(wrappers_bin / "totem_core_exec.py"), "owner": "root", "group": "root", "mode": "0755"})
    copy_file({"source": wrapper_sh, "target": str(wrappers_bin / "totem_core_exec.sh"), "owner": "root", "group": "root", "mode": "0755"})

    for core_file in core_files:
        if "/" in core_file or core_file.startswith("."):
            blockers.append(f"totem_core_image_embed_unsafe_core_file:{core_file}")
            continue
        source_rel = f"scripts/board/{core_file}"
        copy_file({"source": source_rel, "target": str(fallback_bin / core_file), "owner": "root", "group": "root", "mode": "0755"})
        copy_file({"source": source_rel, "target": str(release_bin / core_file), "owner": "root", "group": "root", "mode": "0755"})
        wrapper_rel = wrapper_py if core_file.endswith(".py") else wrapper_sh if core_file.endswith(".sh") else ""
        if not wrapper_rel:
            blockers.append(f"totem_core_image_embed_unknown_wrapper_type:{core_file}")
            continue
        copy_file({"source": wrapper_rel, "target": str(wrappers_bin / core_file), "owner": "root", "group": "root", "mode": "0755"})

    health = {
        "schema": "dadooh.totem.core.health.v1",
        "component": "totem-core",
        "version": version,
        "embedded_in_image": True,
        "self_tests": [
            "python3 bin/totem_setup_visual_wizard.py --self-test",
            "python3 bin/totem_wifi_nm_adapter.py --self-test",
            "python3 bin/totem_visual_splash.py --self-test",
            "python3 bin/totem_config_contract_validate.py --self-test",
            "python3 bin/totem_qr_pairing_client.py --self-test",
            "bash -n bin/totem_open_settings_session.sh",
            "bash -n bin/totem_visual_tty_guard.sh",
            "bash -n bin/totem_firstboot_gate.sh",
            "bash -n bin/totem_status_renderer.sh",
            "restore-order-static-check",
        ],
    }
    write_text_file(
        release_dir / "health" / "totem-core-health.json",
        json.dumps(health, indent=2, sort_keys=True) + "\n",
        "0644",
        "totem-core embedded health metadata",
    )

    fragment = {
        "component": "totem-core",
        "layout": str(base_dir),
        "fallback": str(fallback_bin),
        "wrappers": str(wrappers_bin),
        "systemd_units_included": False,
        "updater_self_update": False,
        "embedded_in_image": True,
    }
    write_text_file(
        release_dir / "manifest-fragment" / "totem-core.json",
        json.dumps(fragment, indent=2, sort_keys=True) + "\n",
        "0644",
        "totem-core embedded manifest fragment",
    )

    if current_link.exists() or current_link.is_symlink():
        if current_link.is_symlink() and os.readlink(current_link) == current_target:
            pass
        elif current_link.is_symlink() or current_link.is_file():
            action("set_totem_core_current_symlink", str(current_link), current_target)
            if mode == "apply":
                current_link.unlink()
                os.symlink(current_target, current_link)
                changed.append(str(current_link))
        else:
            blockers.append(f"totem_core_current_not_replaceable:{current_link}")
    else:
        action("set_totem_core_current_symlink", str(current_link), current_target)
        if mode == "apply":
            current_link.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(current_target, current_link)
            changed.append(str(current_link))

    state = {
        "schema": "dadooh.totem.update.state.v1",
        "component": "totem-core",
        "current": {
            "version": version,
            "path": current_target,
            "source": "image_embed",
            "source_repo": "dadoohai/orange_pi_totem",
            "source_branch": manifest.get("orange_pi_totem", {}).get("branch", "foundation-v0.1"),
            "source_commit": repo_value(["rev-parse", "HEAD"], ".orange_pi_totem_head"),
            "payload_sha256": spec.get("payload_sha256"),
        },
        "previous": None,
        "last_operation": {
            "type": "image_embed",
            "status": "ok",
            "version": version,
        },
        "updated_at": "image_embed",
    }
    write_text_file(
        base_dir / "state.json",
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        "0644",
        "totem-core image embedded update state",
    )


def parse_armbian_env(path):
    lines = []
    values = {}
    if path.exists():
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return lines, values


def apply_armbian_env(path, values, set_keys, tokens):
    lines, _ = parse_armbian_env(path)
    seen = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key, _ = stripped.split("=", 1)
        key = key.strip()
        if key in set_keys:
            new_lines.append(f"{key}={set_keys[key]}")
            seen.add(key)
        elif key == "extraargs":
            existing = values.get("extraargs", "")
            merged = []
            for token in existing.split() + tokens:
                if token not in merged:
                    merged.append(token)
            new_lines.append("extraargs=" + " ".join(merged))
            seen.add("extraargs")
        else:
            new_lines.append(line)
    for key, value in set_keys.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")
    if "extraargs" not in seen:
        new_lines.append("extraargs=" + " ".join(tokens))
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def ensure_boot_guardrails():
    spec = manifest["boot_visual_guardrails"]
    state_dir = pathlib.Path(spec["backup_state_dir"])
    ensure_dir(manifest_path_item(state_dir, {"path": str(state_dir), "type": "dir", "owner": "root", "group": "root", "mode": "0700"}))
    env_path = pathlib.Path(spec["armbian_env"])
    lines, values = parse_armbian_env(env_path)
    key_changes = {key: value for key, value in spec["set_keys"].items() if values.get(key) != value}
    extraargs = set(values.get("extraargs", "").split())
    missing_tokens = [token for token in spec["required_extraargs_tokens"] if token not in extraargs]
    if not env_path.exists() or key_changes or missing_tokens:
        action("apply_boot_visual_guardrails", str(env_path), "armbianEnv allowlisted keys/tokens differ")
        if mode == "apply":
            if env_path.exists():
                backup = state_dir / "armbianEnv.txt.c10-8.bak"
                if not backup.exists():
                    shutil.copy2(env_path, backup)
                    changed.append(str(backup))
            apply_armbian_env(env_path, values, spec["set_keys"], spec["required_extraargs_tokens"])
            os.chmod(env_path, 0o644)
            changed.append(str(env_path))
    for unit in spec.get("getty_units_disabled", []):
        enabled = out(["systemctl", "is-enabled", unit], 6) or "unknown"
        active = out(["systemctl", "is-active", unit], 6) or "unknown"
        if enabled not in {"disabled", "masked", "static"}:
            action("disable_getty_unit", unit, "visual guardrail forbids visible login getty")
            if mode == "apply":
                subprocess.run(["systemctl", "disable", unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                changed.append(f"disable:{unit}")
        if active == "active":
            if manage_running_services:
                action("stop_getty_unit", unit, "--manage-running-services provided")
                if mode == "apply":
                    subprocess.run(["systemctl", "stop", unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                    changed.append(f"stop:{unit}")
            else:
                warnings.append(f"getty_active_not_stopped_without_flag:{unit}")


def ensure_orientation():
    spec = manifest["public_orientation"]
    path = pathlib.Path(spec["path"])
    parent = path.parent
    ensure_dir(manifest_path_item(parent, {"path": str(parent), "type": "dir", "owner": "root", "group": "root", "mode": "0700"}))
    needs_write = False
    public_data = None
    if path.exists() and not path.is_symlink():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and set(raw) <= set(spec["allowed_fields"]) and raw.get("schema_version") == spec["schema_version"] and raw.get("rotation_deg") in spec["allowed_rotation_deg"]:
                public_data = raw
            else:
                needs_write = True
        except Exception:
            needs_write = True
    else:
        needs_write = True
    if needs_write:
        action("write_public_orientation_default", str(path), "missing or invalid public orientation contract")
        if mode == "apply":
            data = {
                "schema_version": spec["schema_version"],
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                **spec["default_if_missing"],
            }
            tmp = path.with_name(f".{path.name}.tmp")
            tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.chmod(tmp, int(spec["mode"], 8))
            os.chown(tmp, uid(spec["owner"]), gid(spec["group"]))
            os.replace(tmp, path)
            changed.append(str(path))
    if path.exists() and (mode_str(path) != spec["mode"] or owner_name(path) != spec["owner"] or group_name(path) != spec["group"]):
        action("fix_public_orientation_metadata", str(path), "public orientation owner/mode differs")
        if mode == "apply":
            chmod_chown(path, spec["owner"], spec["group"], spec["mode"])
            changed.append(str(path))


def generate_installed_manifest():
    state_dir = pathlib.Path("/data/state/totem-appliance")
    ensure_dir({"path": str(state_dir), "type": "dir", "owner": "root", "group": "root", "mode": "0755"})
    target = state_dir / "manifest-installed.json"
    repo_head = repo_value(["rev-parse", "HEAD"], ".orange_pi_totem_head")
    should_write = True
    if target.exists() and not target.is_symlink():
        try:
            current = json.loads(target.read_text(encoding="utf-8"))
            should_write = current.get("repo_head") != repo_head or current.get("schema_version") != "dadooh-totem-appliance-installed-manifest.v1"
        except Exception:
            should_write = True
    if not should_write:
        return
    action("write_installed_manifest", str(target), "sanitized manifest record")
    if mode == "apply":
        record = {
            "schema_version": "dadooh-totem-appliance-installed-manifest.v1",
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "repo_head": repo_head,
            "manifest": manifest,
            "private_values_included": False,
        }
        target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(target, 0o644)
        os.chown(target, uid("root"), gid("root"))
        changed.append(str(target))


def check_kiosky_pin():
    spec = manifest["kiosky_player"]
    app = pathlib.Path(spec["install_path"])
    if not app.exists():
        action("create_kiosky_player_placeholder_dir", str(app), "install path missing; app deployment is separate from appliance refresh")
        warnings.append("kiosky_player_app_tree_missing_deploy_pinned_commit_before_operational_use")
    if spec.get("pin_status") == "PIN_MISSING" or spec.get("expected_commit") == "PIN_MISSING":
        blockers.append("kiosky_player_PIN_MISSING")
        return
    git_required_on_dev = bool(spec.get("expected_git_metadata_on_dev", spec.get("expected_git_metadata", True)))
    if not (app / ".git").exists():
        if not git_required_on_dev:
            warnings.append("kiosky_player_git_metadata_absent_pin_from_manifest_docs")
            return
        blockers.append("kiosky_player_git_metadata_missing")
        return
    head = out(["git", "-C", str(app), "rev-parse", "HEAD"], 8)
    if head != spec.get("expected_commit"):
        blockers.append("kiosky_player_pin_mismatch")


ensure_user()
check_runtime()
check_readonly_prerequisites()
for item in manifest["paths"]:
    ensure_dir(item)
ensure_files()
ensure_totem_core_image_embed()
ensure_boot_guardrails()
ensure_orientation()
generate_installed_manifest()
check_kiosky_pin()

if mode == "apply" and blockers:
    payload_status = "blocked_before_apply"
else:
    payload_status = "planned" if mode == "dry-run" else "applied"

payload = {
    "schema_version": "dadooh-c10.8-appliance-installer-plan.v1",
    "mode": mode,
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "rules": {
        "config_content_read": False,
        "private_config_created": False,
        "writer_called": False,
        "networkmanager_profiles_changed": False,
        "wifi_credentials_embedded": False,
        "product_services_restarted_by_default": False,
        "runtime_install_requires_explicit_flag": True,
        "readonly_prereq_install_requires_explicit_flag": True,
        "apt_upgrade_called": False,
        "apt_full_upgrade_called": False,
        "armbian_upgrade_called": False,
    },
    "repo": {
        "branch": repo_value(["rev-parse", "--abbrev-ref", "HEAD"], ".orange_pi_totem_branch"),
        "head": repo_value(["rev-parse", "HEAD"], ".orange_pi_totem_head"),
        "dirty_entries": repo_dirty_entries(),
    },
    "install_runtime": install_runtime,
    "install_readonly_prereqs": install_readonly_prereqs,
    "manage_running_services": manage_running_services,
    "actions": actions,
    "action_count": len(actions),
    "changed": changed,
    "changed_count": len(changed),
    "warnings": warnings,
    "blockers": blockers,
    "status": payload_status,
    "ready_for_second_board": not blockers,
}

output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(output_json, 0o600)

lines = [
    "C10.8 appliance installer summary",
    f"mode={mode}",
    f"status={payload_status}",
    f"repo_branch={payload['repo']['branch']}",
    f"repo_head={payload['repo']['head']}",
    f"repo_dirty_entries={payload['repo']['dirty_entries']}",
    f"action_count={len(actions)}",
    f"changed_count={len(changed)}",
    f"install_runtime={str(install_runtime).lower()}",
    f"install_readonly_prereqs={str(install_readonly_prereqs).lower()}",
    f"manage_running_services={str(manage_running_services).lower()}",
    f"ready_for_second_board={str(payload['ready_for_second_board']).lower()}",
]
if blockers:
    lines.append("blockers:")
    lines.extend(f"- {item}" for item in blockers)
else:
    lines.append("blockers: none")
if warnings:
    lines.append("warnings:")
    lines.extend(f"- {item}" for item in warnings)
if actions:
    lines.append("actions:")
    lines.extend(f"- {item['kind']} {item['target']}" for item in actions[:80])
summary_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
os.chmod(summary_txt, 0o600)

print(f"plan_json={output_json}")
print(f"summary={summary_txt}")
print(f"status={payload_status}")
if mode == "apply" and blockers:
    sys.exit(10)
PY
}

if [ "$MODE" = "dry-run" ]; then
  run_planner "dry-run" "$OUT_DIR/dry-run.json" "$OUT_DIR/summary.txt"
  exit 0
fi

if [ "$MODE" = "apply" ]; then
  PREFLIGHT_JSON="$OUT_DIR/apply-preflight.json"
  run_planner "dry-run" "$PREFLIGHT_JSON" "$OUT_DIR/apply-preflight.txt" >/dev/null
  python3 - "$PREFLIGHT_JSON" <<'PY'
import json
import pathlib
import sys

data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
unsafe = [item for item in data.get("actions", []) if item.get("apply_safe") is False]
if data.get("blockers") or unsafe:
    print("apply_preflight_status=blocked")
    if data.get("blockers"):
        print("blockers=" + ",".join(data["blockers"]))
    if unsafe:
        print("unsafe_actions=" + ",".join(item["kind"] for item in unsafe))
    sys.exit(10)
print("apply_preflight_status=ok")
PY
  run_planner "apply" "$OUT_DIR/apply.json" "$OUT_DIR/summary.txt"
  exit 0
fi

if [ "$MODE" = "idempotence-check" ]; then
  FIRST="$OUT_DIR/idempotence-first.json"
  SECOND="$OUT_DIR/idempotence-second.json"
  run_planner "dry-run" "$FIRST" "$OUT_DIR/idempotence-first.txt" >/dev/null
  run_planner "dry-run" "$SECOND" "$OUT_DIR/idempotence-second.txt" >/dev/null
  python3 - "$FIRST" "$SECOND" "$OUT_DIR/idempotence.json" "$OUT_DIR/summary.txt" <<'PY'
import json
import pathlib
import sys

first = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
second = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
out_json = pathlib.Path(sys.argv[3])
summary = pathlib.Path(sys.argv[4])

stable_keys = ["actions", "blockers", "warnings", "install_runtime", "install_readonly_prereqs", "manage_running_services", "ready_for_second_board"]
stable = all(first.get(key) == second.get(key) for key in stable_keys)
payload = {
    "schema_version": "dadooh-c10.8-idempotence-dry-run.v1",
    "stable": stable,
    "first_action_count": first.get("action_count"),
    "second_action_count": second.get("action_count"),
    "blockers": first.get("blockers", []),
    "ready_for_second_board": first.get("ready_for_second_board", False),
    "dry_run_only": True,
    "board_changed": False,
}
out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
summary.write_text(
    "\n".join(
        [
            "C10.8 idempotence dry-run summary",
            f"stable={str(stable).lower()}",
            f"first_action_count={payload['first_action_count']}",
            f"second_action_count={payload['second_action_count']}",
            f"ready_for_second_board={str(payload['ready_for_second_board']).lower()}",
            "blockers:" if payload["blockers"] else "blockers: none",
            *[f"- {item}" for item in payload["blockers"]],
        ]
    )
    + "\n",
    encoding="utf-8",
)
print(f"idempotence_json={out_json}")
print(f"summary={summary}")
print(f"stable={str(stable).lower()}")
sys.exit(0 if stable else 11)
PY
  chmod 600 "$OUT_DIR/idempotence.json" "$OUT_DIR/summary.txt"
  exit 0
fi

echo "error: unreachable mode: $MODE" >&2
exit 2
