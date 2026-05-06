#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
CONFIRMATION="${C11_3_3_CONFIRMATION:-}"
TIMESTAMP="${C11_3_3_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-/tmp/dadooh-c11-3-3-overlayroot-mechanism-lab}"
LOCAL_OUT_DIR="${C11_3_3_LOCAL_OUT_DIR:-$LOCAL_RUN_ROOT/$TIMESTAMP-c11-3-3-overlayroot-mechanism-lab}"
SSH_CONTROL_DIR="/tmp/dadooh-c11-3-3-ssh-$TIMESTAMP"
SSH_CONTROL_PATH="$SSH_CONTROL_DIR/%C"

ENABLE_TEST_CONFIRMATION="CONFIRMO ENABLE OVERLAYROOT LAB NA PLACA TESTE"
REBOOT_TEST_CONFIRMATION="CONFIRMO REBOOT OVERLAYROOT LAB NA PLACA TESTE"

usage() {
  cat <<'USAGE'
Usage:
  run_c11_3_3_overlayroot_mechanism_lab.sh <root@host> [mode] [options]

Modes:
  --prepare-only
  --inspect-dev
  --inspect-test
  --diagnose-test
  --dry-run-test-enable
  --enable-test
  --reboot-test
  --verify-test
  --rollback-test
  --summary

Options:
  --confirm "CONFIRMO ..."
  --local-out-dir /tmp/...

Rules:
  - dev host is inspect-only in C11.3.3;
  - test host is the overlayroot laboratory;
  - --enable-test requires: CONFIRMO ENABLE OVERLAYROOT LAB NA PLACA TESTE;
  - --reboot-test requires: CONFIRMO REBOOT OVERLAYROOT LAB NA PLACA TESTE;
  - no poweroff, power cut, writer/config, Wi-Fi/NetworkManager profile changes,
    kiosky-player changes, package installs or apt upgrade paths;
  - no raw logs, config, secrets, SSID, IP, MAC, DNS, gateway, hostname or
    NetworkManager profile names in artifacts.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect-dev) MODE="inspect-dev" ;;
    --inspect-test) MODE="inspect-test" ;;
    --diagnose-test) MODE="diagnose-test" ;;
    --dry-run-test-enable) MODE="dry-run-test-enable" ;;
    --enable-test) MODE="enable-test" ;;
    --reboot-test) MODE="reboot-test" ;;
    --verify-test) MODE="verify-test" ;;
    --rollback-test) MODE="rollback-test" ;;
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
  prepare-only|inspect-dev|inspect-test|diagnose-test|dry-run-test-enable|enable-test|reboot-test|verify-test|rollback-test|summary) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ "$MODE" != "prepare-only" ] && [ "$MODE" != "summary" ] && [ -z "$HOST" ]; then
  echo "error: host is required for $MODE" >&2
  exit 2
fi

if [ "$MODE" = "enable-test" ] && [ "$CONFIRMATION" != "$ENABLE_TEST_CONFIRMATION" ]; then
  echo "error: enable-test requires exact confirmation" >&2
  exit 2
fi

if [ "$MODE" = "reboot-test" ] && [ "$CONFIRMATION" != "$REBOOT_TEST_CONFIRMATION" ]; then
  echo "error: reboot-test requires exact confirmation" >&2
  exit 2
fi

case "$LOCAL_OUT_DIR" in
  /tmp/*) ;;
  *) echo "error: --local-out-dir must be under /tmp" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
C11_3_RUNNER="$REPO_ROOT/scripts/remote/run_c11_3_read_only_enablement_dev.sh"
VERIFY_POLICY="$REPO_ROOT/scripts/board/verify_totem_read_only_policy.sh"
LOCAL_HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || printf unknown)"
LOCAL_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || printf unknown)"

ssh_board() {
  mkdir -p "$SSH_CONTROL_DIR"
  chmod 700 "$SSH_CONTROL_DIR"
  ssh -o ConnectTimeout=10 -o NumberOfPasswordPrompts=1 -o ControlMaster=auto -o ControlPersist=300 -o ControlPath="$SSH_CONTROL_PATH" "$HOST" "$@"
}

prepare_local() {
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  git -C "$REPO_ROOT" diff --check
  bash -n "$0"
  bash -n "$C11_3_RUNNER"
  bash -n "$VERIFY_POLICY"
  python3 -m json.tool "$REPO_ROOT/scripts/board/totem_read_only_policy.json" >/dev/null
  python3 -m json.tool "$REPO_ROOT/scripts/board/totem_appliance_manifest.json" >/dev/null
}

write_readme() {
  local result="$1"
  local reboot_executed="false"
  [ "$MODE" = "reboot-test" ] && reboot_executed="true"
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  cat > "$LOCAL_OUT_DIR/README.md" <<EOF
# C11.3.3 overlayroot mechanism lab artifact

- mode: \`$MODE\`
- result: \`$result\`
- repo_head: \`$LOCAL_HEAD\`
- repo_branch: \`$LOCAL_BRANCH\`
- host: \`<sanitized>\`
- dev_enable_executed: \`false\`
- poweroff_executed: \`false\`
- power_cut_tested: \`false\`
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

write_offline_recovery() {
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  cat > "$LOCAL_OUT_DIR/offline-recovery-instructions.md" <<'EOF'
# C11.3.3 offline recovery instructions

If the test board does not return over SSH after an overlayroot lab reboot:

1. Remove power from the test board.
2. Mount the Linux root filesystem of the test media on another Linux system.
3. Edit `/etc/overlayroot.conf` on that mounted root filesystem.
4. Set `overlayroot=""` and keep `overlayroot_cfgdisk="disabled"`.
5. Unmount cleanly, return the media to the board and power it on.
6. After SSH returns, run `--rollback-test`.

Do not copy product config, API values, Wi-Fi credentials, NetworkManager
profile contents or raw logs into evidence.
EOF
  chmod 600 "$LOCAL_OUT_DIR/offline-recovery-instructions.md"
}

remote_diag() {
  local label="$1"
  local out_file="$LOCAL_OUT_DIR/$label.json"
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  local code
  code="$(cat <<'PY' | base64 -w0
import json
import os
import re
import subprocess
from pathlib import Path

def run(cmd, timeout=8):
    return subprocess.run(["sh", "-lc", cmd], capture_output=True, text=True, timeout=timeout)

def out(cmd, timeout=8):
    try:
        return run(cmd, timeout).stdout.strip()
    except Exception:
        return ""

def service(name):
    return {
        "active": out(f"systemctl is-active {name} 2>/dev/null || true") or "unknown",
        "enabled": out(f"systemctl is-enabled {name} 2>/dev/null || true") or "unknown",
        "nrestarts": int((out(f"systemctl show {name} -p NRestarts --value 2>/dev/null || echo 0") or "0").splitlines()[-1] or "0"),
    }

def package_installed(name):
    return out(f"dpkg-query -W -f='${{Status}}' {name} 2>/dev/null || true") == "install ok installed"

def command_available(name):
    return bool(out(f"command -v {name} 2>/dev/null || true"))

def mount_info(target):
    text = out(f"findmnt -n -o FSTYPE,OPTIONS --target {target} 2>/dev/null || true")
    parts = text.split(None, 1)
    opts = parts[1].split(",") if len(parts) > 1 else []
    fstype = parts[0] if parts else "unknown"
    return {"fstype": fstype, "overlay_active": fstype == "overlay", "read_only": "ro" in opts}

def grep_count(pattern, boot="0"):
    try:
        value = out("journalctl -k -b %s --no-pager 2>/dev/null | grep -Eic %r || true" % (boot, pattern), 20)
        return int(value or "0")
    except Exception:
        return 0

conf = Path("/etc/overlayroot.conf")
conf_text = conf.read_text(errors="ignore") if conf.exists() else ""
last_overlay = None
last_cfgdisk = None
for line in conf_text.splitlines():
    s = line.strip()
    if s.startswith("overlayroot="):
        last_overlay = s.split("=", 1)[1].strip().strip('"')
    if s.startswith("overlayroot_cfgdisk="):
        last_cfgdisk = s.split("=", 1)[1].strip().strip('"')

armbian_env = Path("/boot/armbianEnv.txt")
env_text = armbian_env.read_text(errors="ignore") if armbian_env.exists() else ""
cmdline = Path("/proc/cmdline").read_text(errors="ignore") if Path("/proc/cmdline").exists() else ""
root_mount = mount_info("/")
log = Path("/run/initramfs/overlayroot.log")
log_text = log.read_text(errors="ignore") if log.exists() else ""

payload = {
    "schema_version": "dadooh-c11.3.3-overlayroot-lab-diagnostic.v1",
    "overlayroot_package_installed": package_installed("overlayroot"),
    "overlayroot_chroot_available": command_available("overlayroot-chroot"),
    "overlayroot_command_available": command_available("overlayroot"),
    "overlayroot_initramfs_script_present": Path("/usr/share/initramfs-tools/scripts/init-bottom/overlayroot").exists(),
    "overlayroot_conf_present": conf.exists(),
    "overlayroot_conf_effective_disabled": last_overlay in ("", "disabled"),
    "overlayroot_conf_effective_tmpfs": last_overlay == "tmpfs",
    "overlayroot_cfgdisk_disabled": last_cfgdisk == "disabled",
    "overlayroot_local_conf_present": Path("/etc/overlayroot.local.conf").exists(),
    "kernel_cmdline_has_overlayroot": "overlayroot" in cmdline,
    "armbian_env_has_overlayroot": "overlayroot" in env_text,
    "armbian_env_has_extraargs": "extraargs=" in env_text,
    "initrd_current_exists": bool(out("test -e /boot/initrd.img-$(uname -r) && echo yes || true")),
    "uinitrd_exists": Path("/boot/uInitrd").exists(),
    "update_initramfs_available": command_available("update-initramfs"),
    "root_mount": root_mount,
    "read_only_enabled": root_mount["read_only"] or root_mount["overlay_active"],
    "overlay_active": root_mount["overlay_active"],
    "root_write_blocked": root_mount["read_only"] or root_mount["overlay_active"],
    "data_writable": os.access("/data", os.W_OK),
    "tmp_writable": os.access("/tmp", os.W_OK),
    "run_writable": os.access("/run", os.W_OK),
    "journald_storage_volatile": out("systemd-analyze cat-config systemd/journald.conf 2>/dev/null | grep -E '^Storage=' | tail -1 | cut -d= -f2 || true") == "volatile",
    "services": {name: service(name) for name in ["kiosky-player.service", "totem-settings-trigger.service", "dadooh-visual-splash.service"]},
    "systemctl_failed_count": int(out("systemctl --failed --no-legend --plain 2>/dev/null | wc -l") or "0"),
    "kernel_critical_filter_count": sum(grep_count(p) for p in ["panic|Kernel panic", "Oops|BUG:", "EXT4-fs error|EXT4-fs.*failed", "mmc.*(timeout|error|reset|I/O error)"]),
    "initramfs_overlayroot_log_present": log.exists(),
    "initramfs_log_driver_lookup_failed": "Unable to find a driver" in log_text or "Unable to find driver/module" in log_text,
    "initramfs_log_overlay_mount_failed": "overlay" in log_text.lower() and "mount" in log_text.lower() and ("fail" in log_text.lower() or "failure" in log_text.lower()),
    "raw_logs_published": False,
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "wifi_changed": False,
    "networkmanager_profiles_changed": False,
    "secrets_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
)"
  ssh_board "python3 -c 'import base64; exec(base64.b64decode(\"$code\").decode())'" > "$out_file"
  chmod 600 "$out_file"
}

delegate_test() {
  local delegate_mode="$1"
  local delegate_confirm="${2:-}"
  local delegate_out="$LOCAL_OUT_DIR/delegate-$delegate_mode"
  mkdir -p "$delegate_out"
  chmod 700 "$delegate_out"
  if [ -n "$delegate_confirm" ]; then
    "$C11_3_RUNNER" "$HOST" "$delegate_mode" --confirm "$delegate_confirm" --local-out-dir "$delegate_out"
  else
    "$C11_3_RUNNER" "$HOST" "$delegate_mode" --local-out-dir "$delegate_out"
  fi
}

write_summary() {
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  python3 - <<PY > "$LOCAL_OUT_DIR/summary.txt"
from pathlib import Path
root = Path("$LOCAL_RUN_ROOT")
print("C11.3.3 overlayroot mechanism lab")
for path in sorted(root.glob("*c11-3-3-overlayroot-mechanism-lab/*.json"))[-10:]:
    print(path)
PY
  chmod 600 "$LOCAL_OUT_DIR/summary.txt"
}

case "$MODE" in
  prepare-only)
    prepare_local
    write_offline_recovery
    write_readme "prepare-only-complete"
    ;;
  inspect-dev)
    prepare_local
    remote_diag "inspect-dev"
    write_readme "inspect-dev-complete"
    ;;
  inspect-test)
    prepare_local
    write_offline_recovery
    remote_diag "inspect-test"
    write_readme "inspect-test-complete"
    ;;
  diagnose-test)
    prepare_local
    write_offline_recovery
    remote_diag "diagnose-test"
    write_readme "diagnose-test-complete"
    ;;
  dry-run-test-enable)
    prepare_local
    write_offline_recovery
    delegate_test --dry-run-enable
    remote_diag "dry-run-test-enable"
    write_readme "dry-run-test-enable-complete"
    ;;
  enable-test)
    prepare_local
    write_offline_recovery
    delegate_test --enable-read-only "CONFIRMO ENABLE READ ONLY C11.3 DEV"
    remote_diag "enable-test"
    write_readme "enable-test-complete-pending-reboot"
    ;;
  reboot-test)
    prepare_local
    write_offline_recovery
    delegate_test --reboot-check "CONFIRMO REBOOT READ ONLY C11.3 DEV"
    remote_diag "reboot-test"
    write_readme "reboot-test-complete"
    ;;
  verify-test)
    prepare_local
    remote_diag "verify-test"
    write_readme "verify-test-complete"
    ;;
  rollback-test)
    prepare_local
    delegate_test --rollback-read-only
    remote_diag "rollback-test"
    write_readme "rollback-test-complete"
    ;;
  summary)
    write_summary
    ;;
esac
