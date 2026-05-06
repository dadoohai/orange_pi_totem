#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="summary"
TIMESTAMP="${C10_10_1_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-/tmp/dadooh-c10-10-1-power-state-audit}"
LOCAL_OUT_DIR="${C10_10_1_LOCAL_OUT_DIR:-$LOCAL_RUN_ROOT/$TIMESTAMP-c10-10-1-power-state-shutdown-ux-audit}"
SSH_CONTROL_DIR="/tmp/dadooh-c10-10-1-ssh-$TIMESTAMP"
SSH_CONTROL_PATH="$SSH_CONTROL_DIR/%C"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_10_1_power_state_audit.sh <root@host> [mode] [options]

Modes:
  --inspect-current
  --postmortem-previous-boot
  --classify
  --summary

Options:
  --local-out-dir /tmp/...

Rules:
  - read-only audit only;
  - host is an argument, never hardcoded;
  - does not reboot, poweroff, call writer, edit config, edit Wi-Fi, install packages or restart services;
  - analyzes journal output in memory and stores only sanitized categories/counts;
  - never writes raw logs, config content, secrets, SSID, IP, MAC, DNS or payloads to artifacts.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --inspect-current) MODE="inspect-current" ;;
    --postmortem-previous-boot) MODE="postmortem-previous-boot" ;;
    --classify) MODE="classify" ;;
    --summary) MODE="summary" ;;
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
  inspect-current|postmortem-previous-boot|classify|summary) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ -z "$HOST" ]; then
  echo "error: host is required; pass root@<second-board-host>" >&2
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

prepare_local() {
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  git -C "$REPO_ROOT" diff --check
  bash -n "$REPO_ROOT/scripts/remote/run_c10_10_1_power_state_audit.sh"
}

collect_current() {
  mkdir -p "$LOCAL_OUT_DIR"
  ssh_board "python3 -" > "$LOCAL_OUT_DIR/current.json" <<'PY'
import json
import os
import pathlib
import stat
import subprocess
import time


def run(args, timeout=10):
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
        return result.returncode, result.stdout, result.stderr
    except Exception as exc:
        return 127, "", str(exc)


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


def unit(name):
    active = run(["systemctl", "is-active", name])[1].strip() or "unknown"
    enabled = run(["systemctl", "is-enabled", name])[1].strip() or "unknown"
    nrestarts = run(["systemctl", "show", name, "-p", "NRestarts", "--value"])[1].strip()
    return {
        "active": active,
        "enabled": enabled,
        "nrestarts": int(nrestarts) if nrestarts.isdigit() else None,
    }


def failed_count():
    rc, stdout, _ = run(["systemctl", "list-units", "--failed", "--no-legend", "--no-pager"])
    if rc != 0 and not stdout:
        return None
    return len([line for line in stdout.splitlines() if line.strip()])


def process_counts():
    counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmdline = (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
        except Exception:
            continue
        if not cmdline:
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


def journal_count(args):
    rc, stdout, _ = run(args, timeout=20)
    if rc != 0:
        return None
    return len([line for line in stdout.splitlines() if line.strip()])


def config_status():
    path = pathlib.Path("/data/config/config.json")
    if not path.exists() or path.is_symlink():
        return {"present": path.exists(), "mode": None, "owner_group_ok": False, "mode_0640": False, "permissions_ok": False}
    st = path.stat()
    mode = stat.S_IMODE(st.st_mode)
    owner = run(["stat", "-c", "%U:%G", str(path)])[1].strip()
    return {
        "present": True,
        "mode": oct(mode)[2:].zfill(4),
        "owner_group_ok": owner == "root:totem",
        "mode_0640": mode == 0o640,
        "permissions_ok": owner == "root:totem" and mode == 0o640,
    }


def dedicated_wifi_present():
    rc, stdout, _ = run(["nmcli", "-t", "-f", "NAME", "connection", "show"], timeout=10)
    if rc != 0:
        return "unknown"
    prefixes = ("dadooh-c9-8-", "dadooh-product-wifi-")
    return any(line.startswith(prefixes) for line in stdout.splitlines())


def read_boot_id():
    try:
        return pathlib.Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    except Exception:
        return "unknown"


status_data = first_json(("/tmp/dadooh-status/status.json", "/data/state/kiosky-player/launcher-status.json"))
player_status = first_json(("/tmp/kiosky-status.json",))
playback = (
    status_data.get("playback")
    or status_data.get("playback_state")
    or player_status.get("playback_state")
    or player_status.get("playback")
    or "unknown"
)
orientation = pathlib.Path("/data/state/totem-display/orientation.json")
payload = {
    "schema_version": "dadooh-c10.10.1-current-state.v1",
    "collected_at_epoch": int(time.time()),
    "host": "<second-board-host>",
    "raw_logs_published": False,
    "config_content_read": False,
    "secrets_published": False,
    "uptime_seconds": float(pathlib.Path("/proc/uptime").read_text(encoding="utf-8").split()[0]),
    "current_boot_id": read_boot_id(),
    "services": {
        "kiosky-player.service": unit("kiosky-player.service"),
        "totem-settings-trigger.service": unit("totem-settings-trigger.service"),
        "totem-open-settings.service": unit("totem-open-settings.service"),
        "dadooh-visual-splash.service": unit("dadooh-visual-splash.service"),
    },
    "public_state": status_data.get("public_state") or status_data.get("state") or "unknown",
    "playback": playback,
    "process_counts": process_counts(),
    "systemctl_failed_count": failed_count(),
    "kernel_critical_filter_count": journal_count(["journalctl", "-k", "-b", "0", "-p", "crit..emerg", "--no-pager", "-o", "cat"]),
    "config_real": config_status(),
    "dedicated_wifi_present": dedicated_wifi_present(),
    "orientation_json_present": orientation.exists() and not orientation.is_symlink(),
    "session_lock_present": pathlib.Path("/run/dadooh-settings/session.lock").exists(),
    "request_present": pathlib.Path("/run/dadooh-settings/request.json").exists(),
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

collect_previous_boot() {
  mkdir -p "$LOCAL_OUT_DIR"
  ssh_board "python3 -" > "$LOCAL_OUT_DIR/previous_boot.json" <<'PY'
import json
import re
import subprocess
import time


def run(args, timeout=30):
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
        return result.returncode, result.stdout, result.stderr
    except Exception as exc:
        return 127, "", str(exc)


def has(pattern, text):
    return bool(re.search(pattern, text, re.IGNORECASE | re.MULTILINE))


def count(pattern, text):
    return len(re.findall(pattern, text, re.IGNORECASE | re.MULTILINE))


def tri(value, available):
    return bool(value) if available else "unknown"


list_rc, list_boots, _ = run(["journalctl", "--list-boots", "--no-pager"], timeout=20)
journal_available = list_rc == 0 and bool(list_boots.strip())
previous_boot_available = "-1" in list_boots if journal_available else False

prev_rc, prev_text, _ = run(["journalctl", "-b", "-1", "--no-pager", "-o", "cat"], timeout=30)
prev_available = prev_rc == 0 and bool(prev_text.strip())

kernel_rc, kernel_text, _ = run(["journalctl", "-k", "-b", "-1", "--no-pager", "-o", "cat"], timeout=30)
kernel_available = kernel_rc == 0 and bool(kernel_text.strip())

last_rc, last_text, _ = run(["last", "-x", "-n", "20"], timeout=10)
last_available = last_rc == 0 and bool(last_text.strip())

combined = "\n".join([prev_text, kernel_text])
clean_poweroff_markers = (
    has(r"Reached target .*Power[- ]Off", prev_text)
    or has(r"Reached target System Power Off", prev_text)
    or has(r"Powering off", combined)
    or has(r"poweroff\.target", prev_text)
    or has(r"systemd-shutdown.*Powering off", combined)
)
clean_reboot_markers = (
    has(r"Reached target .*Reboot", prev_text)
    or has(r"reboot\.target", prev_text)
    or has(r"systemd-shutdown.*Rebooting", combined)
)
shutdown_markers = (
    has(r"Shutting down", combined)
    or has(r"Stopped target", prev_text)
    or has(r"Reached target Shutdown", prev_text)
)
panic_markers = has(r"kernel panic|panic:|Oops:|BUG: unable to handle|Call Trace:", combined)
ext4_errors = count(r"EXT4-fs error|EXT4-fs .* aborted|journal has aborted|Remounting filesystem read-only", combined)
mmc_errors = count(r"\bmmc\d+:.*(error|timeout|failed)|I/O error.*mmc|Buffer I/O error.*mmc|card never left busy", combined)
network_shutdown = has(r"Stopped Network Manager|NetworkManager.*stopped|Reached target .*Network.*Offline", prev_text)
last_shutdown = has(r"^shutdown\s", last_text) if last_available else False
last_reboot = has(r"^reboot\s", last_text) if last_available else False
last_crash = has(r"\bcrash\b", last_text) if last_available else False
clean_shutdown_without_reboot = (
    shutdown_markers
    and last_shutdown
    and not clean_reboot_markers
    and not panic_markers
    and ext4_errors == 0
    and mmc_errors == 0
)

if clean_poweroff_markers or clean_shutdown_without_reboot:
    end_category = "clean_poweroff"
elif clean_reboot_markers:
    end_category = "clean_reboot"
elif panic_markers:
    end_category = "crash_or_panic"
elif last_crash and not shutdown_markers:
    end_category = "abrupt_power_loss"
else:
    end_category = "unknown"

payload = {
    "schema_version": "dadooh-c10.10.1-previous-boot-postmortem.v1",
    "collected_at_epoch": int(time.time()),
    "host": "<second-board-host>",
    "journal_previous_boot_available": prev_available,
    "raw_logs_published": False,
    "secrets_published": False,
    "previous_boot_had_clean_poweroff": tri(clean_poweroff_markers or clean_shutdown_without_reboot, prev_available or kernel_available or last_available),
    "previous_boot_reached_poweroff_target": tri(clean_poweroff_markers, prev_available),
    "previous_boot_had_reboot_marker": tri(clean_reboot_markers, prev_available),
    "previous_boot_had_kernel_panic": tri(panic_markers, prev_available or kernel_available),
    "previous_boot_had_ext4_error": tri(ext4_errors > 0, prev_available or kernel_available),
    "previous_boot_had_mmc_error": tri(mmc_errors > 0, prev_available or kernel_available),
    "previous_boot_had_network_shutdown": tri(network_shutdown, prev_available),
    "previous_boot_shutdown_markers_present": tri(shutdown_markers, prev_available or kernel_available),
    "previous_boot_clean_shutdown_without_reboot": tri(clean_shutdown_without_reboot, prev_available or kernel_available or last_available),
    "last_x_available": last_available,
    "last_x_shutdown_marker_present": last_shutdown,
    "last_x_reboot_marker_present": last_reboot,
    "last_x_crash_marker_present": last_crash,
    "kernel_critical_filter_count": count(r"kernel panic|panic:|Oops:|BUG:|Call Trace:", combined) if (prev_available or kernel_available) else None,
    "ext4_error_count": ext4_errors if (prev_available or kernel_available) else None,
    "mmc_error_count": mmc_errors if (prev_available or kernel_available) else None,
    "previous_boot_end_category": end_category,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

classify_local() {
  python3 - "$LOCAL_OUT_DIR/current.json" "$LOCAL_OUT_DIR/previous_boot.json" "$LOCAL_OUT_DIR/classification.json" "$LOCAL_OUT_DIR/summary.txt" <<'PY'
import json
import pathlib
import sys

current_path = pathlib.Path(sys.argv[1])
previous_path = pathlib.Path(sys.argv[2])
class_path = pathlib.Path(sys.argv[3])
summary_path = pathlib.Path(sys.argv[4])

current = json.loads(current_path.read_text(encoding="utf-8"))
previous = json.loads(previous_path.read_text(encoding="utf-8"))
category = previous.get("previous_boot_end_category", "unknown")
if category == "clean_poweroff":
    incident_classification = "POWER_STATE_EXPECTED_BUT_UX_UNCLEAR"
    installable_bench_rc_status = "valid_with_shutdown_ux_followup"
    recommendation = "C10.10.2 Shutdown UX"
    blocked_reason = "none"
elif category in {"crash_or_panic", "abrupt_power_loss"}:
    incident_classification = "BLACK_SCREEN_OR_BOOT_FAILURE"
    installable_bench_rc_status = "blocked_until_recovery_audit"
    recommendation = "C10.10.2 Black-screen recovery"
    blocked_reason = category
else:
    incident_classification = "BLACK_SCREEN_OR_BOOT_FAILURE"
    installable_bench_rc_status = "blocked_until_previous_boot_classified"
    recommendation = "C10.10.2 Black-screen recovery"
    blocked_reason = "previous_boot_unknown"

payload = {
    "schema_version": "dadooh-c10.10.1-power-state-classification.v1",
    "incident_observed": True,
    "ssh_unavailable_before_power_cycle": True,
    "hdmi_black_before_power_cycle": True,
    "power_cycle_restored": True,
    "previous_boot_end_category": category,
    "clean_poweroff_detected": category == "clean_poweroff",
    "incident_classification": incident_classification,
    "installable_bench_rc_status": installable_bench_rc_status,
    "blocked_reason": blocked_reason,
    "current_state": {
        "public_state": current.get("public_state"),
        "playback": current.get("playback"),
        "systemctl_failed_count": current.get("systemctl_failed_count"),
        "kernel_critical_filter_count": current.get("kernel_critical_filter_count"),
        "config_permissions_ok": current.get("config_real", {}).get("permissions_ok"),
        "session_lock_present": current.get("session_lock_present"),
        "request_present": current.get("request_present"),
        "process_counts": current.get("process_counts"),
    },
    "previous_boot": {
        "kernel_critical_filter_count": previous.get("kernel_critical_filter_count"),
        "ext4_error_detected": previous.get("previous_boot_had_ext4_error"),
        "mmc_error_detected": previous.get("previous_boot_had_mmc_error"),
        "kernel_panic_detected": previous.get("previous_boot_had_kernel_panic"),
        "clean_poweroff_detected": previous.get("previous_boot_had_clean_poweroff"),
    },
    "recommendation": recommendation,
    "raw_logs_published": False,
    "secrets_published": False,
}
class_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
class_path.chmod(0o600)

lines = [
    "C10.10.1 power state audit summary",
    f"incident_observed={str(payload['incident_observed']).lower()}",
    f"ssh_unavailable_before_power_cycle={str(payload['ssh_unavailable_before_power_cycle']).lower()}",
    f"hdmi_black_before_power_cycle={str(payload['hdmi_black_before_power_cycle']).lower()}",
    f"power_cycle_restored={str(payload['power_cycle_restored']).lower()}",
    f"previous_boot_end_category={category}",
    f"clean_poweroff_detected={str(payload['clean_poweroff_detected']).lower()}",
    f"incident_classification={incident_classification}",
    f"installable_bench_rc_status={installable_bench_rc_status}",
    f"kernel_critical_filter_count={previous.get('kernel_critical_filter_count')}",
    f"ext4_error_detected={previous.get('previous_boot_had_ext4_error')}",
    f"mmc_error_detected={previous.get('previous_boot_had_mmc_error')}",
    f"current_public_state={current.get('public_state')}",
    f"current_playback={current.get('playback')}",
    f"recommendation={recommendation}",
    "raw_logs_published=false",
    "secrets_published=false",
]
summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
summary_path.chmod(0o600)
print("\n".join(lines))
PY
}

write_runner_readme() {
  cat > "$LOCAL_OUT_DIR/README.md" <<EOF
# C10.10.1 remote runner artifact

- mode: \`$MODE\`
- repo_head: \`$LOCAL_HEAD\`
- repo_branch: \`$LOCAL_BRANCH\`
- source_dirty_entries: \`$LOCAL_DIRTY_COUNT\`
- host: \`<second-board-host>\`
- raw_logs_published: \`false\`
- secrets_published: \`false\`
- config_content_published: \`false\`
- network_identifiers_published: \`false\`
- reboot_called: \`false\`
- poweroff_called: \`false\`
- writer_called: \`false\`
- wifi_changed: \`false\`
- packages_installed: \`false\`
EOF
  chmod 600 "$LOCAL_OUT_DIR/README.md"
}

run_inspect_current() {
  prepare_local
  collect_current
  write_runner_readme
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_postmortem_previous_boot() {
  prepare_local
  collect_previous_boot
  write_runner_readme
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_classify() {
  prepare_local
  collect_current
  collect_previous_boot
  classify_local
  write_runner_readme
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

case "$MODE" in
  inspect-current) run_inspect_current ;;
  postmortem-previous-boot) run_postmortem_previous_boot ;;
  classify|summary) run_classify ;;
esac
