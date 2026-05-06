#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
CONFIRMATION="${C11_3_CONFIRMATION:-}"
TIMESTAMP="${C11_3_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-/tmp/dadooh-c11-3-read-only-enable-dev}"
LOCAL_OUT_DIR="${C11_3_LOCAL_OUT_DIR:-$LOCAL_RUN_ROOT/$TIMESTAMP-c11-3-read-only-enable-dev}"
REMOTE_ROOT="${REMOTE_ROOT:-/tmp/dadooh-c11-3-read-only-enable-dev}"
REMOTE_WORK="$REMOTE_ROOT/work-$TIMESTAMP"
REMOTE_OUT="$REMOTE_ROOT/out-$TIMESTAMP"
SSH_CONTROL_DIR="/tmp/dadooh-c11-3-ssh-$TIMESTAMP"
SSH_CONTROL_PATH="$SSH_CONTROL_DIR/%C"

ENABLE_CONFIRMATION="CONFIRMO ENABLE READ ONLY C11.3 DEV"
REBOOT_CONFIRMATION="CONFIRMO REBOOT READ ONLY C11.3 DEV"

usage() {
  cat <<'USAGE'
Usage:
  run_c11_3_read_only_enablement_dev.sh <root@host> [mode] [options]

Modes:
  --prepare-only
  --inspect
  --dry-run-enable
  --enable-read-only
  --verify
  --reboot-check
  --rollback-read-only
  --summary

Options:
  --confirm "CONFIRMO ..."
  --local-out-dir /tmp/...

Rules:
  - dev board only for C11.3;
  - --inspect and --dry-run-enable do not alter anything;
  - --enable-read-only requires: CONFIRMO ENABLE READ ONLY C11.3 DEV;
  - --reboot-check requires: CONFIRMO REBOOT READ ONLY C11.3 DEV;
  - does not poweroff, power-cut, write config, call writer, change Wi-Fi or
    NetworkManager profiles, alter kiosky-player, install packages or touch the
    test board;
  - never publishes raw logs, config, secrets, SSID, IP, MAC, DNS, gateway,
    hostname or NetworkManager profile names.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --dry-run-enable) MODE="dry-run-enable" ;;
    --enable-read-only) MODE="enable-read-only" ;;
    --verify) MODE="verify" ;;
    --reboot-check) MODE="reboot-check" ;;
    --rollback-read-only) MODE="rollback-read-only" ;;
    --summary) MODE="summary" ;;
    --confirm)
      shift
      CONFIRMATION="${1:-}"
      ;;
    --local-out-dir)
      shift
      LOCAL_OUT_DIR="${1:-}"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      HOST="$1"
      ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|inspect|dry-run-enable|enable-read-only|verify|reboot-check|rollback-read-only|summary) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ "$MODE" != "prepare-only" ] && [ "$MODE" != "summary" ] && [ -z "$HOST" ]; then
  echo "error: host is required for $MODE" >&2
  exit 2
fi

if [ "$MODE" = "enable-read-only" ] && [ "$CONFIRMATION" != "$ENABLE_CONFIRMATION" ]; then
  echo "error: enable-read-only requires exact confirmation" >&2
  exit 2
fi

if [ "$MODE" = "reboot-check" ] && [ "$CONFIRMATION" != "$REBOOT_CONFIRMATION" ]; then
  echo "error: reboot-check requires exact confirmation" >&2
  exit 2
fi

case "$LOCAL_OUT_DIR" in
  /tmp/*) ;;
  *) echo "error: --local-out-dir must be under /tmp" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || printf unknown)"
LOCAL_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || printf unknown)"
LOCAL_DIRTY_COUNT="$(git -C "$REPO_ROOT" status --short 2>/dev/null | wc -l | tr -d ' ')"

ssh_board() {
  mkdir -p "$SSH_CONTROL_DIR"
  chmod 700 "$SSH_CONTROL_DIR"
  ssh -o ConnectTimeout=10 -o NumberOfPasswordPrompts=1 -o ControlMaster=auto -o ControlPersist=300 -o ControlPath="$SSH_CONTROL_PATH" "$HOST" "$@"
}

scp_board() {
  mkdir -p "$SSH_CONTROL_DIR"
  chmod 700 "$SSH_CONTROL_DIR"
  scp -o ConnectTimeout=10 -o NumberOfPasswordPrompts=1 -o ControlMaster=auto -o ControlPersist=300 -o ControlPath="$SSH_CONTROL_PATH" "$@"
}

prepare_local() {
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  git -C "$REPO_ROOT" diff --check
  bash -n "$REPO_ROOT/scripts/remote/run_c11_3_read_only_enablement_dev.sh"
  bash -n "$REPO_ROOT/scripts/remote/run_c11_2_read_only_mitigation_apply.sh"
  bash -n "$REPO_ROOT/scripts/board/verify_totem_read_only_policy.sh"
  python3 -m json.tool "$REPO_ROOT/scripts/board/totem_read_only_policy.json" >/dev/null
  "$REPO_ROOT/scripts/board/verify_totem_read_only_policy.sh" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_wifi_nm_adapter.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_config_contract_validate.py" --self-test >/dev/null
}

write_local_readme() {
  local result="$1"
  local reboot_executed="false"
  if [ "$MODE" = "reboot-check" ]; then
    reboot_executed="true"
  fi
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  cat > "$LOCAL_OUT_DIR/README.md" <<EOF
# C11.3 read-only enablement runner artifact

- mode: \`$MODE\`
- result: \`$result\`
- repo_head: \`$LOCAL_HEAD\`
- repo_branch: \`$LOCAL_BRANCH\`
- source_dirty_entries: \`$LOCAL_DIRTY_COUNT\`
- host: \`<dev-board>\`
- remote_workspace: \`/tmp/dadooh-c11-3-read-only-enable-dev/...\`
- test_board_touched: \`false\`
- power_cut_tested: \`false\`
- poweroff_executed: \`false\`
- reboot_executed: \`$reboot_executed\`
- writer_called: \`false\`
- real_config_read: \`false\`
- real_config_written: \`false\`
- wifi_changed: \`false\`
- networkmanager_profiles_changed: \`false\`
- packages_installed: \`false\`
- raw_logs_published: \`false\`
- secrets_published: \`false\`
EOF
  chmod 600 "$LOCAL_OUT_DIR/README.md"
}

pull_remote_artifacts() {
  mkdir -p "$LOCAL_OUT_DIR/remote"
  chmod 700 "$LOCAL_OUT_DIR/remote"
  scp_board -q -r "$HOST:$REMOTE_OUT/." "$LOCAL_OUT_DIR/remote/" || true
}

copy_helpers() {
  ssh_board "mkdir -p '$REMOTE_WORK' '$REMOTE_OUT' && chmod 700 '$REMOTE_ROOT' '$REMOTE_WORK' '$REMOTE_OUT'"
  scp_board -q \
    "$REPO_ROOT/scripts/board/verify_totem_read_only_policy.sh" \
    "$REPO_ROOT/scripts/board/totem_read_only_policy.json" \
    "$HOST:$REMOTE_WORK/"
  ssh_board "chmod 700 '$REMOTE_WORK/verify_totem_read_only_policy.sh'"
}

run_remote_verify() {
  ssh_board "'$REMOTE_WORK/verify_totem_read_only_policy.sh' --policy '$REMOTE_WORK/totem_read_only_policy.json' --out-dir '$REMOTE_OUT/verify-$1'"
}

run_remote_python() {
  local remote_mode="$1"
  ssh_board "REMOTE_MODE='$remote_mode' REMOTE_OUT='$REMOTE_OUT' python3 -" <<'PY'
import json
import os
import pathlib
import shutil
import subprocess
import time

MODE = os.environ["REMOTE_MODE"]
OUT = pathlib.Path(os.environ["REMOTE_OUT"])
STATE = pathlib.Path("/data/state/totem-read-only-enable")
BACKUPS = STATE / "backups"
ROLLBACK = STATE / "rollback-state.json"
OVERLAY_CONF = pathlib.Path("/etc/overlayroot.conf")
OVERLAY_CONF_TEXT = """# Dadooh C11.3 root read-only enablement.
overlayroot_cfgdisk=\"disabled\"
overlayroot=\"tmpfs\"
"""


def run(args, timeout=8):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except Exception:
        return None


def out(args, timeout=8):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


def command_available(name):
    return bool(out(["sh", "-c", f"command -v {name}"], 4))


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


def mount_info(target):
    text = out(["findmnt", "-n", "-o", "TARGET,FSTYPE,OPTIONS", "--target", target], 8)
    parts = text.split(None, 2)
    options = parts[2].split(",") if len(parts) > 2 else []
    return {
        "target": target,
        "mounted": bool(text),
        "fstype_category": parts[1] if len(parts) > 1 else "unknown",
        "read_only": "ro" in options,
        "overlay_active": (parts[1] == "overlay") if len(parts) > 1 else False,
    }


def unit_state(name):
    nrestarts = out(["systemctl", "show", name, "-p", "NRestarts", "--value"])
    return {
        "active": out(["systemctl", "is-active", name]) or "unknown",
        "enabled": out(["systemctl", "is-enabled", name]) or "unknown",
        "nrestarts": int(nrestarts) if nrestarts.isdigit() else None,
    }


def failed_count():
    text = out(["systemctl", "list-units", "--failed", "--no-legend", "--no-pager"], 10)
    return len([line for line in text.splitlines() if line.strip()])


def safe_write_probe(path_text):
    path = pathlib.Path(path_text)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("probe\n", encoding="utf-8")
        path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def overlayroot_status():
    if command_available("overlayroot-chroot"):
        result = run(["overlayroot-chroot", "true"], 6)
        return result is not None and result.returncode == 0
    return False


def mechanism():
    armbian_config_path = out(["sh", "-c", "command -v armbian-config"], 4) or "missing"
    config_jobs = pathlib.Path("/usr/lib/armbian-config/config.jobs.json")
    config_system = pathlib.Path("/usr/lib/armbian-config/config.system.sh")
    module_present = False
    for path in (config_jobs, config_system):
        if path.exists() and not path.is_symlink():
            try:
                if "module_overlayfs" in path.read_text(encoding="utf-8", errors="ignore"):
                    module_present = True
            except OSError:
                pass
    overlayroot_available = command_available("overlayroot")
    overlayroot_chroot_available = command_available("overlayroot-chroot")
    return {
        "mechanism_detected": "armbian_config_module_overlayfs" if module_present else "unknown",
        "armbian_config_available": armbian_config_path != "missing",
        "armbian_config_path_category": "present" if armbian_config_path != "missing" else "missing",
        "armbian_module_overlayfs_present": module_present,
        "overlayroot_available": overlayroot_available,
        "overlayroot_chroot_available": overlayroot_chroot_available,
        "overlayroot_package_present": overlayroot_available or overlayroot_chroot_available,
        "can_enable_without_package_install": overlayroot_available and overlayroot_chroot_available,
        "package_install_required": module_present and not (overlayroot_available and overlayroot_chroot_available),
        "risk_level": "blocked_missing_overlayroot_package" if module_present and not (overlayroot_available and overlayroot_chroot_available) else ("medium" if module_present else "high_unknown"),
    }


def snapshot():
    status = first_json(("/tmp/dadooh-status/status.json", "/data/state/kiosky-player/launcher-status.json"))
    player = first_json(("/tmp/kiosky-status.json",))
    root = mount_info("/")
    data = mount_info("/data")
    tmp = mount_info("/tmp")
    run_mount = mount_info("/run")
    mech = mechanism()
    return {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "public_state": status.get("public_state") or status.get("state") or "unknown",
        "playback": status.get("playback") or status.get("playback_state") or player.get("playback") or player.get("playback_state") or "unknown",
        "services": {
            "kiosky-player.service": unit_state("kiosky-player.service"),
            "totem-settings-trigger.service": unit_state("totem-settings-trigger.service"),
            "dadooh-visual-splash.service": unit_state("dadooh-visual-splash.service"),
        },
        "systemctl_failed_count": failed_count(),
        "mounts": {"root": root, "data": data, "tmp": tmp, "run": run_mount},
        "read_only_enabled": root["read_only"] or root["overlay_active"] or overlayroot_status(),
        "overlay_active": root["overlay_active"] or overlayroot_status(),
        "writable_paths_ok": {
            "data": safe_write_probe("/data/state/totem-read-only-enable/.data-write-probe"),
            "tmp": safe_write_probe("/tmp/.dadooh-c11-3-tmp-write-probe"),
            "run": safe_write_probe("/run/.dadooh-c11-3-run-write-probe"),
        },
        "protected_root_write_blocked": not safe_write_probe("/root/.dadooh-c11-3-protected-root-test"),
        "journald_storage": "volatile" if pathlib.Path("/etc/systemd/journald.conf.d/90-dadooh-volatile.conf").exists() else "unknown",
        "networkmanager_profile_path_present": pathlib.Path("/etc/NetworkManager/system-connections").exists(),
        "dedicated_wifi_present": "unknown",
        "config_real_present_without_reading_content": pathlib.Path("/data/config/config.json").exists(),
        "orientation_json_present": pathlib.Path("/data/state/totem-display/orientation.json").exists(),
        "rollback_state_present": ROLLBACK.exists(),
        "mechanism": mech,
    }


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def planned_actions(mech):
    actions = []
    if not mech["can_enable_without_package_install"]:
        actions.append("abort_enable_missing_overlayroot_package")
        return actions
    if not OVERLAY_CONF.exists() or OVERLAY_CONF.read_text(encoding="utf-8", errors="ignore") != OVERLAY_CONF_TEXT:
        actions.append("write_overlayroot_conf_tmpfs")
    actions.append("write_rollback_state")
    actions.append("require_reboot")
    return actions


def enable(snapshot_before):
    mech = snapshot_before["mechanism"]
    if not mech["can_enable_without_package_install"]:
        return False, "blocked_missing_overlayroot_package"
    STATE.mkdir(parents=True, exist_ok=True)
    STATE.chmod(0o700)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    BACKUPS.chmod(0o700)
    rollback = {
        "schema_version": "dadooh-c11.3-read-only-enable-rollback.v1",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "overlay_conf_path": str(OVERLAY_CONF),
        "overlay_conf_existed_before": OVERLAY_CONF.exists(),
        "overlay_conf_backup": None,
        "read_only_enabled_before": snapshot_before["read_only_enabled"],
        "package_installed": False,
        "wifi_changed": False,
        "config_changed": False,
    }
    if OVERLAY_CONF.exists() and not OVERLAY_CONF.is_symlink():
        backup = BACKUPS / "overlayroot.conf.before-c11-3"
        shutil.copy2(OVERLAY_CONF, backup)
        backup.chmod(0o600)
        rollback["overlay_conf_backup"] = str(backup)
    tmp = OVERLAY_CONF.with_name(".overlayroot.conf.tmp")
    tmp.write_text(OVERLAY_CONF_TEXT, encoding="utf-8")
    tmp.chmod(0o644)
    os.replace(tmp, OVERLAY_CONF)
    write_json(ROLLBACK, rollback)
    write_json(
        STATE / "enable-state.json",
        {
            "schema_version": "dadooh-c11.3-read-only-enable-state.v1",
            "status": "enabled_pending_reboot",
            "updated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "mechanism": mech["mechanism_detected"],
            "read_only_enabled": False,
            "reboot_required": True,
            "package_installed": False,
            "wifi_changed": False,
            "writer_called": False,
            "real_config_written": False,
        },
    )
    return True, "enabled_pending_reboot"


def rollback_read_only():
    state = {}
    if ROLLBACK.exists() and not ROLLBACK.is_symlink():
        try:
            state = json.loads(ROLLBACK.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    existed = bool(state.get("overlay_conf_existed_before"))
    backup = state.get("overlay_conf_backup")
    if overlayroot_status() and command_available("overlayroot-chroot"):
        command = "rm -f /etc/overlayroot.conf"
        if existed and backup:
            command = "cp /data/state/totem-read-only-enable/backups/overlayroot.conf.before-c11-3 /etc/overlayroot.conf"
        run(["overlayroot-chroot", "sh", "-c", command], 12)
    else:
        if existed and backup and pathlib.Path(backup).exists() and not pathlib.Path(backup).is_symlink():
            shutil.copy2(backup, OVERLAY_CONF)
            OVERLAY_CONF.chmod(0o644)
        elif OVERLAY_CONF.exists() and not OVERLAY_CONF.is_symlink():
            OVERLAY_CONF.unlink()
    write_json(
        STATE / "rollback-applied.json",
        {
            "schema_version": "dadooh-c11.3-read-only-rollback-result.v1",
            "rolled_back_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "reboot_required": True,
            "raw_logs_published": False,
            "secrets_published": False,
        },
    )


OUT.mkdir(parents=True, exist_ok=True)
OUT.chmod(0o700)
before = snapshot()
result = {
    "schema_version": "dadooh-c11.3-read-only-enable-run.v1",
    "mode": MODE,
    "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "mechanism": before["mechanism"],
    "files_to_change": ["/etc/overlayroot.conf"] if before["mechanism"]["can_enable_without_package_install"] else [],
    "rollback_files": ["/data/state/totem-read-only-enable/rollback-state.json"],
    "expected_writable_paths": ["/data", "/tmp", "/run"],
    "power_cut_tested": False,
    "poweroff_executed": False,
    "writer_called": False,
    "real_config_read": False,
    "real_config_written": False,
    "wifi_changed": False,
    "networkmanager_profiles_changed": False,
    "packages_installed": False,
    "raw_logs_published": False,
    "secrets_published": False,
    "before": before,
    "planned_actions": planned_actions(before["mechanism"]),
    "enable_executed": False,
    "rollback_executed": False,
    "enable_result": "not_requested",
    "smoke_f10_cancel_result": "not_run",
}
if MODE == "enable":
    ok, reason = enable(before)
    result["enable_executed"] = ok
    result["enable_result"] = reason
elif MODE == "rollback":
    rollback_read_only()
    result["rollback_executed"] = True
    result["enable_result"] = "rollback_applied_reboot_required"
after = snapshot()
result["after"] = after
result["read_only_enabled"] = after["read_only_enabled"]
result["overlay_active"] = after["overlay_active"]
result["protected_root_write_blocked"] = after["protected_root_write_blocked"]
result["writable_paths_ok"] = all(after["writable_paths_ok"].values())
result["rollback_available"] = after["rollback_state_present"] or result["rollback_executed"]
result["ready_for_c11_4"] = bool(
    result["read_only_enabled"]
    and result["overlay_active"]
    and result["writable_paths_ok"]
    and result["protected_root_write_blocked"]
    and after["public_state"] == "player_running"
    and after["playback"] == "playing"
    and after["systemctl_failed_count"] == 0
)
write_json(OUT / f"{MODE}.json", result)
summary = [
    f"C11.3 {MODE}",
    f"mechanism_detected: {before['mechanism']['mechanism_detected']}",
    f"risk_level: {before['mechanism']['risk_level']}",
    f"package_install_required: {str(before['mechanism']['package_install_required']).lower()}",
    f"can_enable_without_package_install: {str(before['mechanism']['can_enable_without_package_install']).lower()}",
    f"enable_executed: {str(result['enable_executed']).lower()}",
    f"enable_result: {result['enable_result']}",
    f"read_only_enabled: {str(result['read_only_enabled']).lower()}",
    f"overlay_active: {str(result['overlay_active']).lower()}",
    f"protected_root_write_blocked: {str(result['protected_root_write_blocked']).lower()}",
    f"writable_paths_ok: {str(result['writable_paths_ok']).lower()}",
    f"rollback_available: {str(result['rollback_available']).lower()}",
    f"ready_for_c11_4: {str(result['ready_for_c11_4']).lower()}",
    f"public_state: {after['public_state']}",
    f"playback: {after['playback']}",
    f"systemctl_failed_count: {after['systemctl_failed_count']}",
    "power_cut_tested: false",
    "poweroff_executed: false",
    "writer_called: false",
    "real_config_read: false",
    "real_config_written: false",
    "wifi_changed: false",
    "networkmanager_profiles_changed: false",
    "packages_installed: false",
    "raw_logs_published: false",
]
(OUT / f"{MODE}-summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
(OUT / f"{MODE}-summary.txt").chmod(0o600)
if MODE == "enable" and result["enable_result"] == "blocked_missing_overlayroot_package":
    raise SystemExit(3)
PY
}

run_remote_mode() {
  local remote_mode="$1"
  prepare_local
  copy_helpers
  set +e
  run_remote_python "$remote_mode"
  local rc=$?
  set -e
  run_remote_verify "$remote_mode" || true
  pull_remote_artifacts
  write_local_readme "$MODE-complete-rc-$rc"
  return "$rc"
}

run_remote_verify() {
  ssh_board "'$REMOTE_WORK/verify_totem_read_only_policy.sh' --policy '$REMOTE_WORK/totem_read_only_policy.json' --out-dir '$REMOTE_OUT/verify-$1'"
}

run_reboot_check() {
  prepare_local
  copy_helpers
  run_remote_verify before-reboot
  ssh_board "REMOTE_OUT='$REMOTE_OUT' python3 -" <<'PY'
import json, os, pathlib, time
out = pathlib.Path(os.environ["REMOTE_OUT"])
payload = {
  "schema_version": "dadooh-c11.3-reboot-check.v1",
  "reboot_requested_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "power_cut_tested": False,
  "poweroff_executed": False
}
(out / "reboot-request.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(out / "reboot-request.json").chmod(0o600)
PY
  ssh_board "systemctl reboot" || true
  sleep 25
  ssh_board "true"
  copy_helpers
  run_remote_verify after-reboot
  pull_remote_artifacts
  write_local_readme "reboot-check-complete"
}

write_summary_from_latest() {
  prepare_local
  mkdir -p "$LOCAL_OUT_DIR/summary"
  chmod 700 "$LOCAL_OUT_DIR/summary"
  python3 - "$LOCAL_RUN_ROOT" "$LOCAL_OUT_DIR/summary/read-only-enable-summary.json" "$LOCAL_OUT_DIR/summary/summary.txt" <<'PY'
import json, pathlib, sys, time
root = pathlib.Path(sys.argv[1])
out_json = pathlib.Path(sys.argv[2])
out_txt = pathlib.Path(sys.argv[3])
runs = []
for path in sorted(root.glob("*-c11-3-read-only-enable-dev/remote/*.json")):
    if path.name.startswith("verify-"):
        continue
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    runs.append({
        "mode": data.get("mode"),
        "enable_result": data.get("enable_result"),
        "read_only_enabled": data.get("read_only_enabled"),
        "overlay_active": data.get("overlay_active"),
        "ready_for_c11_4": data.get("ready_for_c11_4"),
    })
payload = {
    "schema_version": "dadooh-c11.3-read-only-enable-summary.v1",
    "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "runs_found": len(runs),
    "runs": runs[-10:],
    "power_cut_tested": False,
    "poweroff_executed": False,
    "writer_called": False,
    "wifi_changed": False,
    "packages_installed": False,
}
out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
out_json.chmod(0o600)
out_txt.write_text("C11.3 read-only enablement summary\nruns_found: %d\npower_cut_tested: false\npoweroff_executed: false\n" % len(runs), encoding="utf-8")
out_txt.chmod(0o600)
PY
  write_local_readme "summary-complete"
}

case "$MODE" in
  prepare-only)
    prepare_local
    write_local_readme "prepare-only-complete"
    ;;
  inspect)
    run_remote_mode inspect
    ;;
  dry-run-enable)
    run_remote_mode dry-run
    ;;
  enable-read-only)
    run_remote_mode enable
    ;;
  verify)
    prepare_local
    copy_helpers
    run_remote_verify current
    pull_remote_artifacts
    write_local_readme "verify-complete"
    ;;
  rollback-read-only)
    run_remote_mode rollback
    ;;
  reboot-check)
    run_reboot_check
    ;;
  summary)
    write_summary_from_latest
    ;;
esac
