#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
CONFIRMATION="${C11_3_2_CONFIRMATION:-}"
TIMESTAMP="${C11_3_2_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-/tmp/dadooh-c11-3-2-read-only-enable-dev}"
LOCAL_OUT_DIR="${C11_3_2_LOCAL_OUT_DIR:-$LOCAL_RUN_ROOT/$TIMESTAMP-c11-3-2-read-only-enable-dev}"
REMOTE_ROOT="${REMOTE_ROOT:-/tmp/dadooh-c11-3-2-read-only-enable-dev}"
REMOTE_OUT="$REMOTE_ROOT/out-$TIMESTAMP"
SSH_CONTROL_DIR="/tmp/dadooh-c11-3-2-ssh-$TIMESTAMP"
SSH_CONTROL_PATH="$SSH_CONTROL_DIR/%C"

ENABLE_CONFIRMATION="CONFIRMO ENABLE OVERLAYROOT C11.3.2 DEV"
REBOOT_CONFIRMATION="CONFIRMO REBOOT OVERLAYROOT C11.3.2 DEV"
ENABLE_DEDICATED_POWER_CONFIRMATION="CONFIRMO ENABLE OVERLAYROOT C11.3.2 DEV COM FONTE DEDICADA"
REBOOT_DEDICATED_POWER_CONFIRMATION="CONFIRMO REBOOT OVERLAYROOT C11.3.2 DEV COM FONTE DEDICADA"

usage() {
  cat <<'USAGE'
Usage:
  run_c11_3_2_read_only_enable_dev.sh <root@host> [mode] [options]

Modes:
  --prepare-only
  --inspect
  --dry-run-enable
  --enable
  --verify-before-reboot
  --reboot-check
  --rollback
  --offline-recovery-instructions
  --summary

Options:
  --confirm "CONFIRMO ..."
  --local-out-dir /tmp/...

Rules:
  - dev board only for C11.3.2;
  - --inspect and --dry-run-enable do not alter anything;
  - --enable requires: CONFIRMO ENABLE OVERLAYROOT C11.3.2 DEV
    or CONFIRMO ENABLE OVERLAYROOT C11.3.2 DEV COM FONTE DEDICADA;
  - --reboot-check requires: CONFIRMO REBOOT OVERLAYROOT C11.3.2 DEV
    or CONFIRMO REBOOT OVERLAYROOT C11.3.2 DEV COM FONTE DEDICADA;
  - does not poweroff, power-cut, touch the test board, call writer,
    read/write real config, change Wi-Fi or NetworkManager profiles, alter
    kiosky-player, install packages or run apt upgrade/full-upgrade/
    dist-upgrade/armbian-upgrade;
  - never publishes raw logs, config, secrets, SSID, IP, MAC, DNS, gateway,
    hostname or NetworkManager profile names.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --dry-run-enable) MODE="dry-run-enable" ;;
    --enable) MODE="enable" ;;
    --verify-before-reboot) MODE="verify-before-reboot" ;;
    --reboot-check) MODE="reboot-check" ;;
    --rollback) MODE="rollback" ;;
    --offline-recovery-instructions) MODE="offline-recovery-instructions" ;;
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
  prepare-only|inspect|dry-run-enable|enable|verify-before-reboot|reboot-check|rollback|offline-recovery-instructions|summary) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ "$MODE" != "prepare-only" ] && [ "$MODE" != "summary" ] && [ "$MODE" != "offline-recovery-instructions" ] && [ -z "$HOST" ]; then
  echo "error: host is required for $MODE" >&2
  exit 2
fi

if [ "$MODE" = "enable" ]; then
  case "$CONFIRMATION" in
    "$ENABLE_CONFIRMATION"|"$ENABLE_DEDICATED_POWER_CONFIRMATION") ;;
    *)
      echo "error: enable requires exact confirmation" >&2
      exit 2
      ;;
  esac
fi

if [ "$MODE" = "reboot-check" ]; then
  case "$CONFIRMATION" in
    "$REBOOT_CONFIRMATION"|"$REBOOT_DEDICATED_POWER_CONFIRMATION") ;;
    *)
      echo "error: reboot-check requires exact confirmation" >&2
      exit 2
      ;;
  esac
fi

case "$LOCAL_OUT_DIR" in
  /tmp/*) ;;
  *) echo "error: --local-out-dir must be under /tmp" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
C11_3_RUNNER="$REPO_ROOT/scripts/remote/run_c11_3_read_only_enablement_dev.sh"
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
  bash -n "$REPO_ROOT/scripts/remote/run_c11_3_2_read_only_enable_dev.sh"
  bash -n "$REPO_ROOT/scripts/remote/run_c11_3_read_only_enablement_dev.sh"
  bash -n "$REPO_ROOT/scripts/remote/run_c11_3_1_overlayroot_prereq.sh"
  bash -n "$REPO_ROOT/scripts/board/verify_totem_read_only_policy.sh"
  python3 -m json.tool "$REPO_ROOT/scripts/board/totem_read_only_policy.json" >/dev/null
  python3 -m json.tool "$REPO_ROOT/scripts/board/totem_appliance_manifest.json" >/dev/null
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
# C11.3.2 read-only enable dev runner artifact

- mode: \`$MODE\`
- result: \`$result\`
- repo_head: \`$LOCAL_HEAD\`
- repo_branch: \`$LOCAL_BRANCH\`
- source_dirty_entries: \`$LOCAL_DIRTY_COUNT\`
- host: \`<dev-board>\`
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

write_offline_recovery() {
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  cat > "$LOCAL_OUT_DIR/offline-recovery-instructions.md" <<'EOF'
# C11.3.2 offline recovery instructions

If the dev board does not return over SSH after enabling overlayroot and
rebooting:

1. Remove power from the board.
2. Remove the microSD/eMMC media and mount the Linux root filesystem on a
   workstation.
3. Edit `/etc/overlayroot.conf` on the mounted root filesystem.
4. Set `overlayroot=""` or `overlayroot=disabled`.
5. Keep `overlayroot_cfgdisk="disabled"`.
6. If a backup is available, restore
   `/data/state/totem-read-only-enable/backups/overlayroot.conf.before-c11-3-2`
   to `/etc/overlayroot.conf`.
7. Unmount cleanly, put the media back into the board and power it on.
8. After SSH returns, run the C11.3.2 `--rollback` mode before trying enable
   again.

The product config, API values, Wi-Fi credentials and NetworkManager profile
contents are not needed for this recovery path and must not be copied into
evidence.
EOF
  chmod 600 "$LOCAL_OUT_DIR/offline-recovery-instructions.md"
}

delegate_c11_3() {
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

run_remote_verify_before_reboot() {
  ssh_board "mkdir -p '$REMOTE_OUT' && chmod 700 '$REMOTE_ROOT' '$REMOTE_OUT'"
  ssh_board "REMOTE_OUT='$REMOTE_OUT' python3 -" <<'PY'
import json
import pathlib
import re
import subprocess
import time

OUT = pathlib.Path(__import__("os").environ["REMOTE_OUT"])
OVERLAY_CONF = pathlib.Path("/etc/overlayroot.conf")
ROLLBACK = pathlib.Path("/data/state/totem-read-only-enable/rollback-state.json")
EXPECTED = {
    "overlayroot": "tmpfs",
    "overlayroot_cfgdisk": "disabled",
}


def run(args, timeout=8):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except Exception:
        return None


def out(args, timeout=8):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


def active_overlay_conf_values():
    values = {}
    if not OVERLAY_CONF.exists() or OVERLAY_CONF.is_symlink():
        return values
    for raw in OVERLAY_CONF.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


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


def command_available(name):
    return bool(out(["sh", "-c", f"command -v {name}"], 4))


def package_installed(name):
    result = run(["dpkg-query", "-W", "-f=${Status}", name], 5)
    return bool(result is not None and result.returncode == 0 and (result.stdout or "").strip() == "install ok installed")


def initrd_has_overlayroot():
    img = out(["sh", "-c", "ls -1 /boot/initrd.img-* 2>/dev/null | tail -1"], 5)
    if not img:
        return "unknown"
    listing = out(["lsinitramfs", img], 20)
    return "scripts/init-bottom/overlayroot" in listing


status = first_json(("/tmp/dadooh-status/status.json", "/data/state/kiosky-player/launcher-status.json"))
player = first_json(("/tmp/kiosky-status.json",))
values = active_overlay_conf_values()
configured = values.get("overlayroot") == EXPECTED["overlayroot"] and values.get("overlayroot_cfgdisk") == EXPECTED["overlayroot_cfgdisk"]
payload = {
    "schema_version": "dadooh-c11.3.2-verify-before-reboot.v1",
    "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "overlay_conf_present": OVERLAY_CONF.exists() and not OVERLAY_CONF.is_symlink(),
    "overlay_conf_configured_for_tmpfs": configured,
    "overlay_conf_active_values_published": False,
    "overlayroot_package_present": package_installed("overlayroot"),
    "overlayroot_chroot_available": command_available("overlayroot-chroot"),
    "overlayroot_initramfs_script_present": pathlib.Path("/usr/share/initramfs-tools/scripts/init-bottom/overlayroot").exists(),
    "current_initrd_contains_overlayroot_script": initrd_has_overlayroot(),
    "update_initramfs_required": initrd_has_overlayroot() is not True,
    "rollback_available": ROLLBACK.exists() and not ROLLBACK.is_symlink(),
    "read_only_pending_reboot": configured,
    "read_only_enabled": False,
    "services": {
        "kiosky-player.service": unit_state("kiosky-player.service"),
        "totem-settings-trigger.service": unit_state("totem-settings-trigger.service"),
        "dadooh-visual-splash.service": unit_state("dadooh-visual-splash.service"),
    },
    "public_state": status.get("public_state") or status.get("state") or "unknown",
    "playback": status.get("playback") or status.get("playback_state") or player.get("playback") or player.get("playback_state") or "unknown",
    "systemctl_failed_count": failed_count(),
    "writer_called": False,
    "real_config_read": False,
    "real_config_written": False,
    "wifi_changed": False,
    "networkmanager_profiles_changed": False,
    "raw_logs_published": False,
    "secrets_published": False,
}
OUT.mkdir(parents=True, exist_ok=True)
OUT.chmod(0o700)
(OUT / "verify-before-reboot.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(OUT / "verify-before-reboot.json").chmod(0o600)
summary = [
    "C11.3.2 verify-before-reboot",
    f"overlay_conf_configured_for_tmpfs: {str(payload['overlay_conf_configured_for_tmpfs']).lower()}",
    f"current_initrd_contains_overlayroot_script: {payload['current_initrd_contains_overlayroot_script']}",
    f"update_initramfs_required: {str(payload['update_initramfs_required']).lower()}",
    f"rollback_available: {str(payload['rollback_available']).lower()}",
    f"read_only_pending_reboot: {str(payload['read_only_pending_reboot']).lower()}",
    f"public_state: {payload['public_state']}",
    f"playback: {payload['playback']}",
    f"systemctl_failed_count: {payload['systemctl_failed_count']}",
    "read_only_enabled: false",
    "writer_called: false",
    "real_config_read: false",
    "real_config_written: false",
    "wifi_changed: false",
]
(OUT / "verify-before-reboot-summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
(OUT / "verify-before-reboot-summary.txt").chmod(0o600)
if not payload["rollback_available"] or not payload["read_only_pending_reboot"]:
    raise SystemExit(3)
PY
  mkdir -p "$LOCAL_OUT_DIR/remote"
  chmod 700 "$LOCAL_OUT_DIR/remote"
  scp_board -q -r "$HOST:$REMOTE_OUT/." "$LOCAL_OUT_DIR/remote/" || true
}

write_summary_from_latest() {
  prepare_local
  mkdir -p "$LOCAL_OUT_DIR/summary"
  chmod 700 "$LOCAL_OUT_DIR/summary"
  python3 - "$LOCAL_RUN_ROOT" "$LOCAL_OUT_DIR/summary/c11-3-2-summary.json" "$LOCAL_OUT_DIR/summary/summary.txt" <<'PY'
import json, pathlib, sys, time
root = pathlib.Path(sys.argv[1])
out_json = pathlib.Path(sys.argv[2])
out_txt = pathlib.Path(sys.argv[3])
runs = []
for path in sorted(root.glob("*-c11-3-2-read-only-enable-dev/**/verify-before-reboot.json")):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    runs.append({
        "read_only_pending_reboot": data.get("read_only_pending_reboot"),
        "rollback_available": data.get("rollback_available"),
        "public_state": data.get("public_state"),
        "playback": data.get("playback"),
    })
payload = {
    "schema_version": "dadooh-c11.3.2-summary.v1",
    "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "runs_found": len(runs),
    "runs": runs[-10:],
    "power_cut_tested": False,
    "poweroff_executed": False,
}
out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
out_json.chmod(0o600)
out_txt.write_text("C11.3.2 summary\nruns_found: %d\npower_cut_tested: false\npoweroff_executed: false\n" % len(runs), encoding="utf-8")
out_txt.chmod(0o600)
PY
  write_local_readme "summary-complete"
}

case "$MODE" in
  prepare-only)
    prepare_local
    write_offline_recovery
    write_local_readme "prepare-only-complete"
    ;;
  inspect)
    prepare_local
    write_offline_recovery
    delegate_c11_3 --inspect
    write_local_readme "inspect-complete"
    ;;
  dry-run-enable)
    prepare_local
    write_offline_recovery
    delegate_c11_3 --dry-run-enable
    write_local_readme "dry-run-enable-complete"
    ;;
  enable)
    prepare_local
    write_offline_recovery
    delegate_c11_3 --enable-read-only "CONFIRMO ENABLE READ ONLY C11.3 DEV"
    run_remote_verify_before_reboot
    write_local_readme "enable-complete-pending-reboot"
    ;;
  verify-before-reboot)
    prepare_local
    write_offline_recovery
    run_remote_verify_before_reboot
    write_local_readme "verify-before-reboot-complete"
    ;;
  reboot-check)
    prepare_local
    write_offline_recovery
    delegate_c11_3 --reboot-check "CONFIRMO REBOOT READ ONLY C11.3 DEV"
    write_local_readme "reboot-check-complete"
    ;;
  rollback)
    prepare_local
    delegate_c11_3 --rollback-read-only
    write_local_readme "rollback-complete"
    ;;
  offline-recovery-instructions)
    prepare_local
    write_offline_recovery
    write_local_readme "offline-recovery-instructions-complete"
    ;;
  summary)
    write_summary_from_latest
    ;;
esac
