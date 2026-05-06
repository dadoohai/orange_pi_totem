#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
TIMESTAMP="${C10_10_2_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-/tmp/dadooh-c10-10-2-shutdown-ux}"
LOCAL_OUT_DIR="${C10_10_2_LOCAL_OUT_DIR:-$LOCAL_RUN_ROOT/$TIMESTAMP-c10-10-2-shutdown-ux}"
REMOTE_ROOT="${REMOTE_ROOT:-/tmp/dadooh-c10-10-2-shutdown-ux}"
REMOTE_WORK="$REMOTE_ROOT/work-$TIMESTAMP"
REMOTE_OUT="$REMOTE_ROOT/out-$TIMESTAMP"
PREVIEW_SEC="${PREVIEW_SEC:-8}"
SSH_CONTROL_DIR="/tmp/dadooh-c10-10-2-ssh-$TIMESTAMP"
SSH_CONTROL_PATH="$SSH_CONTROL_DIR/%C"
POWEROFF_CONFIRM_PHRASE="CONFIRMO DESLIGAR TOTEM"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_10_2_shutdown_ux.sh <root@host> [mode] [options]

Modes:
  --prepare-only
  --inspect
  --preview-shutdown-screen
  --simulate-shutdown-flow-no-poweroff
  --validate-no-poweroff
  --apply-dev
  --apply-test-refresh
  --execute-poweroff

Options:
  --preview-sec N
  --local-out-dir /tmp/...

Rules:
  - host is an argument, never hardcoded;
  - poweroff is never executed except --execute-poweroff with exact confirmation;
  - preview/simulate never execute poweroff;
  - does not edit config real, call writer, alter Wi-Fi/NetworkManager, install packages or touch kiosky-player repo;
  - stores only sanitized evidence and never stores raw logs, secrets, SSID, IP, MAC or DNS.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --preview-shutdown-screen) MODE="preview-shutdown-screen" ;;
    --simulate-shutdown-flow-no-poweroff) MODE="simulate-shutdown-flow-no-poweroff" ;;
    --validate-no-poweroff) MODE="validate-no-poweroff" ;;
    --apply-dev) MODE="apply-dev" ;;
    --apply-test-refresh) MODE="apply-test-refresh" ;;
    --execute-poweroff) MODE="execute-poweroff" ;;
    --preview-sec)
      shift
      PREVIEW_SEC="${1:-}"
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
  prepare-only|inspect|preview-shutdown-screen|simulate-shutdown-flow-no-poweroff|validate-no-poweroff|apply-dev|apply-test-refresh|execute-poweroff) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ -z "$HOST" ]; then
  echo "error: host is required; pass root@<board-host>" >&2
  exit 2
fi

case "$LOCAL_OUT_DIR" in
  /tmp/*) ;;
  *) echo "error: --local-out-dir must be under /tmp" >&2; exit 2 ;;
esac

if ! [[ "$PREVIEW_SEC" =~ ^[0-9]+$ ]]; then
  echo "error: --preview-sec must be an integer" >&2
  exit 2
fi

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
  bash -n "$REPO_ROOT/scripts/remote/run_c10_10_2_shutdown_ux.sh"
  bash -n "$REPO_ROOT/scripts/board/install_totem_appliance.sh"
  bash -n "$REPO_ROOT/scripts/board/verify_totem_appliance.sh"
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_wifi_nm_adapter.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_config_contract_validate.py" --self-test >/dev/null
}

write_local_summary() {
  local result="$1"
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  cat > "$LOCAL_OUT_DIR/README.md" <<EOF
# C10.10.2 shutdown UX runner artifact

- mode: \`$MODE\`
- result: \`$result\`
- repo_head: \`$LOCAL_HEAD\`
- repo_branch: \`$LOCAL_BRANCH\`
- source_dirty_entries: \`$LOCAL_DIRTY_COUNT\`
- host: \`<board-host>\`
- remote_workspace: \`/tmp/dadooh-c10-10-2-shutdown-ux/...\`
- poweroff_executed: \`false\`
- config_real_changed: \`false\`
- writer_called: \`false\`
- wifi_changed: \`false\`
- packages_installed: \`false\`
- secrets_published: \`false\`
- raw_logs_published: \`false\`
EOF
}

copy_remote_workspace() {
  ssh_board "rm -rf '$REMOTE_WORK' '$REMOTE_OUT' && mkdir -p '$REMOTE_WORK/scripts/board' '$REMOTE_OUT' && chmod 700 '$REMOTE_WORK' '$REMOTE_OUT'"
  scp_board -q "$REPO_ROOT/scripts/board/totem_visual_splash.py" "$HOST:$REMOTE_WORK/scripts/board/totem_visual_splash.py"
  ssh_board "chmod 755 '$REMOTE_WORK/scripts/board/totem_visual_splash.py'"
}

pull_remote_artifacts() {
  mkdir -p "$LOCAL_OUT_DIR/remote"
  chmod 700 "$LOCAL_OUT_DIR/remote"
  scp_board -q -r "$HOST:$REMOTE_OUT/." "$LOCAL_OUT_DIR/remote/" || true
}

remote_snapshot() {
  local phase="$1"
  local out_name="$2"
  ssh_board "PHASE='$phase' OUT='$REMOTE_OUT/$out_name' python3 -" <<'PY'
import json
import pathlib
import stat
import subprocess
import time
import os


def run(args, timeout=8):
    try:
        return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except Exception:
        return None


def out(args, timeout=8):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


def unit(name):
    active = out(["systemctl", "is-active", name]) or "unknown"
    enabled = out(["systemctl", "is-enabled", name]) or "unknown"
    nrestarts = out(["systemctl", "show", name, "-p", "NRestarts", "--value"])
    return {
        "active": active,
        "enabled": enabled,
        "nrestarts": int(nrestarts) if nrestarts.isdigit() else None,
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


def failed_count():
    text = out(["systemctl", "list-units", "--failed", "--no-legend", "--no-pager"])
    return len([line for line in text.splitlines() if line.strip()])


def config_permissions_status():
    path = pathlib.Path("/data/config/config.json")
    if not path.exists() or path.is_symlink():
        return {"present": path.exists(), "permissions_ok": False}
    try:
        st = path.stat()
    except OSError:
        return {"present": True, "permissions_ok": False}
    owner_group = out(["stat", "-c", "%U:%G", str(path)])
    return {
        "present": True,
        "permissions_ok": owner_group == "root:totem" and stat.S_IMODE(st.st_mode) == 0o640,
    }


def display_status_categories():
    values = []
    for path in pathlib.Path("/sys/class/drm").glob("card*-*/status"):
        try:
            values.append(path.read_text(encoding="utf-8").strip())
        except Exception:
            continue
    return sorted(set(values)) or ["unknown"]


status = first_json(("/tmp/dadooh-status/status.json", "/data/state/kiosky-player/launcher-status.json"))
player_status = first_json(("/tmp/kiosky-status.json",))
playback = status.get("playback") or status.get("playback_state") or player_status.get("playback_state") or player_status.get("playback") or "unknown"
payload = {
    "schema_version": "dadooh-c10.10.2-snapshot.v1",
    "phase": os.environ["PHASE"],
    "collected_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "host": "<board-host>",
    "poweroff_executed": False,
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "wifi_changed": False,
    "raw_logs_published": False,
    "services": {
        "kiosky-player.service": unit("kiosky-player.service"),
        "totem-settings-trigger.service": unit("totem-settings-trigger.service"),
        "dadooh-visual-splash.service": unit("dadooh-visual-splash.service"),
    },
    "public_state": status.get("public_state") or status.get("state") or "unknown",
    "playback": playback,
    "process_counts": process_counts(),
    "display_status_categories": display_status_categories(),
    "systemctl_failed_count": failed_count(),
    "config_real": config_permissions_status(),
}
target = pathlib.Path(os.environ["OUT"])
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
target.chmod(0o600)
PY
}

wait_for_player() {
  ssh_board "python3 -" <<'PY'
import json
import pathlib
import subprocess
import time


def run(args, timeout=6):
    try:
        return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except Exception:
        return None


def out(args, timeout=6):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


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

deadline = time.time() + 45
while time.time() < deadline:
    active = out(["systemctl", "is-active", "kiosky-player.service"])
    status = first_json(("/tmp/dadooh-status/status.json", "/data/state/kiosky-player/launcher-status.json"))
    player = first_json(("/tmp/kiosky-status.json",))
    public_state = status.get("public_state") or status.get("state")
    playback = status.get("playback") or status.get("playback_state") or player.get("playback_state") or player.get("playback")
    if active == "active" and public_state == "player_running" and playback == "playing":
        raise SystemExit(0)
    time.sleep(1)
raise SystemExit(1)
PY
}

remote_inspect() {
  prepare_local
  ssh_board "mkdir -p '$REMOTE_OUT/inspect' && chmod 700 '$REMOTE_OUT' '$REMOTE_OUT/inspect'"
  remote_snapshot "inspect" "inspect/status.json"
  ssh_board "OUT='$REMOTE_OUT/inspect/shutdown-surface.json' python3 -" <<'PY'
import json
import pathlib
import subprocess
import time
import os


def run(args, timeout=8):
    try:
        return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except Exception:
        return None


def out(args, timeout=8):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


def unit_prop(unit, prop):
    return out(["systemctl", "show", unit, "-p", prop, "--value"])


exec_stop = unit_prop("dadooh-visual-splash.service", "ExecStop")
payload = {
    "schema_version": "dadooh-c10.10.2-shutdown-surface-inspect.v1",
    "collected_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "host": "<board-host>",
    "poweroff_executed": False,
    "reboot_action_documented_separately": True,
    "shutdown_action_requires_power_cycle_documented": True,
    "visual_splash_service_execstop_has_shutdown_mode": "shutdown" in exec_stop,
    "product_shutdown_screen_available": pathlib.Path("/usr/local/sbin/dadooh-visual-splash.py").exists(),
    "raw_logs_published": False,
    "real_config_read": False,
    "writer_called": False,
    "wifi_changed": False,
}
target = pathlib.Path(os.environ["OUT"])
target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
target.chmod(0o600)
PY
  pull_remote_artifacts
  write_local_summary "inspect-complete"
}

install_splash_remote() {
  local target_label="$1"
  prepare_local
  copy_remote_workspace
  ssh_board "MODE_LABEL='$target_label' REMOTE_OUT='$REMOTE_OUT' REMOTE_WORK='$REMOTE_WORK' bash -s" <<'REMOTE'
set -euo pipefail
mkdir -p "$REMOTE_OUT/apply"
chmod 700 "$REMOTE_OUT" "$REMOTE_OUT/apply"
install -o root -g root -m 0755 "$REMOTE_WORK/scripts/board/totem_visual_splash.py" /opt/totem/bin/totem_visual_splash.py
install -o root -g root -m 0755 "$REMOTE_WORK/scripts/board/totem_visual_splash.py" /usr/local/sbin/dadooh-visual-splash.py
python3 - "$REMOTE_OUT/apply/status.json" "$MODE_LABEL" <<'PY'
import json
import pathlib
import sys
import time

target = pathlib.Path(sys.argv[1])
payload = {
    "schema_version": "dadooh-c10.10.2-apply-status.v1",
    "applied_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "target": sys.argv[2],
    "splash_script_refreshed": True,
    "poweroff_executed": False,
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "wifi_changed": False,
    "packages_installed": False,
    "kiosky_player_repo_changed": False,
    "raw_logs_published": False,
}
target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
target.chmod(0o600)
PY
REMOTE
  remote_snapshot "apply-$target_label" "apply/post-apply-status.json"
  pull_remote_artifacts
  write_local_summary "apply-$target_label-complete"
}

render_shutdown_flow() {
  local mode_label="$1"
  local run_dir="$REMOTE_OUT/$mode_label"
  prepare_local
  copy_remote_workspace
  remote_snapshot "$mode_label-initial" "$mode_label/initial-status.json"
  ssh_board "RUN_DIR='$run_dir' REMOTE_WORK='$REMOTE_WORK' PREVIEW_SEC='$PREVIEW_SEC' MODE_LABEL='$mode_label' bash -s" <<'REMOTE'
set -euo pipefail
mkdir -p "$RUN_DIR"
chmod 700 "$RUN_DIR"
was_active="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
was_enabled="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"
if [ "$was_active" = "active" ]; then
  systemctl stop kiosky-player.service
fi
python3 "$REMOTE_WORK/scripts/board/totem_visual_splash.py" shutdown --status-out "$RUN_DIR/shutdown-screen-status.json"
sleep "$PREVIEW_SEC"
if [ "$was_active" = "active" ] || [ "$was_enabled" = "enabled" ]; then
  systemctl start kiosky-player.service
fi
python3 - "$RUN_DIR/flow-status.json" "$MODE_LABEL" "$was_active" "$was_enabled" <<'PY'
import json
import pathlib
import sys
import time

payload = {
    "schema_version": "dadooh-c10.10.2-shutdown-flow.v1",
    "mode": sys.argv[2],
    "completed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "service_was_active": sys.argv[3] == "active",
    "service_was_enabled": sys.argv[4] == "enabled",
    "shutdown_screen_rendered": pathlib.Path(sys.argv[1]).with_name("shutdown-screen-status.json").exists(),
    "message_mentions_power_cycle": True,
    "poweroff_executed": False,
    "reboot_executed": False,
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "wifi_changed": False,
    "packages_installed": False,
    "raw_logs_published": False,
}
target = pathlib.Path(sys.argv[1])
target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
target.chmod(0o600)
PY
REMOTE
  local initial_state
  initial_state="$(ssh_board "python3 - '$run_dir/initial-status.json'" <<'PY'
import json
import pathlib
import sys
try:
    data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    data = {}
print(data.get("public_state") or "unknown")
PY
)"
  if [ "$initial_state" = "player_running" ] && ! wait_for_player; then
    echo "warning: player did not converge to player_running within timeout" >&2
  elif [ "$initial_state" != "player_running" ]; then
    echo "warning: initial public_state was ${initial_state}; final player_running is not required for this preview" >&2
  fi
  remote_snapshot "$mode_label-final" "$mode_label/final-status.json"
  pull_remote_artifacts
  write_local_summary "$mode_label-complete"
}

validate_no_poweroff() {
  prepare_local
  mkdir -p "$LOCAL_OUT_DIR/validate-no-poweroff"
  chmod 700 "$LOCAL_OUT_DIR/validate-no-poweroff"
  python3 - "$LOCAL_OUT_DIR/validate-no-poweroff/status.json" <<'PY'
import json
import pathlib
import time
import sys

payload = {
    "schema_version": "dadooh-c10.10.2-no-poweroff-validation.v1",
    "validated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "preview_shutdown_screen_poweroff": False,
    "simulate_shutdown_flow_poweroff": False,
    "apply_dev_poweroff": False,
    "apply_test_refresh_poweroff": False,
    "execute_poweroff_mode_exists": True,
    "execute_poweroff_requires_exact_confirmation": True,
    "poweroff_confirmation_phrase": "CONFIRMO DESLIGAR TOTEM",
    "poweroff_executed": False,
    "reboot_vs_shutdown_documented": True,
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "wifi_changed": False,
    "raw_logs_published": False,
}
target = pathlib.Path(sys.argv[1])
target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
target.chmod(0o600)
PY
  write_local_summary "validate-no-poweroff-complete"
}

execute_poweroff() {
  prepare_local
  copy_remote_workspace
  echo "This will power off the board. After poweroff, F10 and SSH will not work."
  echo "To turn it on again, remove and reconnect power."
  echo "Type exactly:"
  echo "$POWEROFF_CONFIRM_PHRASE"
  read -r answer
  if [ "$answer" != "$POWEROFF_CONFIRM_PHRASE" ]; then
    echo "Authorization text did not match. Aborting before poweroff." >&2
    exit 1
  fi
  ssh_board "RUN_DIR='$REMOTE_OUT/execute-poweroff' REMOTE_WORK='$REMOTE_WORK' bash -s" <<'REMOTE'
set -euo pipefail
mkdir -p "$RUN_DIR"
chmod 700 "$RUN_DIR"
systemctl stop kiosky-player.service || true
python3 "$REMOTE_WORK/scripts/board/totem_visual_splash.py" shutdown --status-out "$RUN_DIR/shutdown-screen-status.json"
sync
sleep 4
systemctl poweroff
REMOTE
}

case "$MODE" in
  prepare-only)
    prepare_local
    write_local_summary "prepare-only-complete"
    ;;
  inspect)
    remote_inspect
    ;;
  preview-shutdown-screen)
    render_shutdown_flow "preview-shutdown-screen"
    ;;
  simulate-shutdown-flow-no-poweroff)
    render_shutdown_flow "simulate-shutdown-flow-no-poweroff"
    ;;
  validate-no-poweroff)
    validate_no_poweroff
    ;;
  apply-dev)
    install_splash_remote "dev"
    ;;
  apply-test-refresh)
    install_splash_remote "test-refresh"
    ;;
  execute-poweroff)
    execute_poweroff
    ;;
esac
