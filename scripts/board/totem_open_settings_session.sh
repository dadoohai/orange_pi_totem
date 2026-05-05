#!/usr/bin/env bash
set -euo pipefail

MODE="interactive"
EXPECTED_RESULT="any"
REMOTE_TTY="2"
RUN_TIMEOUT_SEC="1800"
PREVIEW_SEC="12"
OUT_DIR="/tmp/dadooh-c10-6-open-settings-session"
WIZARD_OUT_DIR="/tmp/dadooh-c10-6-visual-wizard-session"
LOCK_DIR="/run/dadooh-settings/session.lock"

usage() {
  cat <<'USAGE'
Usage:
  totem_open_settings_session.sh [--mode preview|interactive] [--expect preview|cancelled|candidate_ready|any] [--tty N] [--timeout-sec N] [--preview-sec N] [--out-dir /tmp/...]

Opens the existing visual setup wizard as "Configuracoes do Totem" while the
player is running. It does not call writer, does not write /data/config and
does not alter Wi-Fi/NetworkManager.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode)
      shift
      MODE="${1:-}"
      ;;
    --expect)
      shift
      EXPECTED_RESULT="${1:-}"
      ;;
    --tty)
      shift
      REMOTE_TTY="${1:-}"
      ;;
    --timeout-sec)
      shift
      RUN_TIMEOUT_SEC="${1:-}"
      ;;
    --preview-sec)
      shift
      PREVIEW_SEC="${1:-}"
      ;;
    --out-dir)
      shift
      OUT_DIR="${1:-}"
      ;;
    --wizard-out-dir)
      shift
      WIZARD_OUT_DIR="${1:-}"
      ;;
    --lock-dir)
      shift
      LOCK_DIR="${1:-}"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "error: unsupported argument $1" >&2
      exit 2
      ;;
  esac
  shift
done

case "$MODE" in
  preview|interactive)
    ;;
  *)
    echo "error: unsupported mode $MODE" >&2
    exit 2
    ;;
esac

case "$EXPECTED_RESULT" in
  preview|cancelled|candidate_ready|any)
    ;;
  *)
    echo "error: unsupported expected result $EXPECTED_RESULT" >&2
    exit 2
    ;;
esac

case "$REMOTE_TTY" in
  ''|*[!0-9]*|0)
    echo "error: --tty must be a positive integer" >&2
    exit 2
    ;;
esac

case "$RUN_TIMEOUT_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --timeout-sec must be a positive integer" >&2
    exit 2
    ;;
esac

case "$PREVIEW_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --preview-sec must be a positive integer" >&2
    exit 2
    ;;
esac

case "$OUT_DIR" in
  /tmp/*|/run/*)
    ;;
  *)
    echo "error: --out-dir must be under /tmp or /run" >&2
    exit 2
    ;;
esac

case "$WIZARD_OUT_DIR" in
  /tmp/*|/run/*)
    ;;
  *)
    echo "error: --wizard-out-dir must be under /tmp or /run" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VISUAL="$SCRIPT_DIR/totem_setup_visual_wizard.py"
SPLASH="$SCRIPT_DIR/totem_visual_splash.py"
AGGREGATE="$SCRIPT_DIR/totem_status_aggregate.py"
TTY_DEVICE="/dev/tty$REMOTE_TTY"
FINAL_STATUS="$OUT_DIR/session-status.json"
GETTY_UNITS=("getty@tty1.service" "getty@tty${REMOTE_TTY}.service")
WIZARD_RC="not_run"
SERVICE_STOP_ATTEMPTED="false"
SERVICE_RESTORE_ATTEMPTED="false"
INITIAL_SERVICE_ACTIVE="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
INITIAL_SERVICE_ENABLED="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"
declare -A GETTY_ACTIVE
declare -A GETTY_ENABLED

for path in "$VISUAL" "$SPLASH" "$AGGREGATE"; do
  if [ ! -f "$path" ]; then
    echo "error: missing local session dependency" >&2
    exit 1
  fi
done

umask 077
mkdir -p "$OUT_DIR" "$WIZARD_OUT_DIR" "$(dirname "$LOCK_DIR")"
chmod 700 "$OUT_DIR" "$WIZARD_OUT_DIR" "$(dirname "$LOCK_DIR")" 2>/dev/null || true
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "settings_session_already_running" >&2
  exit 23
fi

for unit in "${GETTY_UNITS[@]}"; do
  GETTY_ACTIVE["$unit"]="$(systemctl is-active "$unit" 2>/dev/null || true)"
  GETTY_ENABLED["$unit"]="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
done

process_counts() {
  python3 - <<'PY'
import os
import pathlib
counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    names = [pathlib.Path(part).name.lower() for part in parts]
    if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
        counts["setup"] += 1
    if any("totem_status_renderer" in name for name in names):
        counts["renderer"] += 1
    if any(name == "mpv" for name in names):
        counts["mpv"] += 1
    if "kiosk.py" in names:
        counts["player"] += 1
print(f"{counts['player']} {counts['mpv']} {counts['renderer']} {counts['setup']}")
PY
}

refresh_public_status() {
  if [ -f /opt/totem/bin/totem_status_aggregate.py ]; then
    PYTHONPATH=/opt/totem/bin python3 /opt/totem/bin/totem_status_aggregate.py >/dev/null 2>&1 || true
  else
    PYTHONPATH="$SCRIPT_DIR" python3 "$AGGREGATE" >/dev/null 2>&1 || true
  fi
}

read_json_value() {
  local path="$1"
  local key="$2"
  python3 - "$path" "$key" <<'PY'
import json
import pathlib
import sys
try:
    data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    key = sys.argv[2]
    value = data.get("public_state") or data.get("state") if key == "public_state" else data.get(key)
    print(value if isinstance(value, str) else "unknown")
except Exception:
    print("unknown")
PY
}

wait_player_running() {
  for _ in $(seq 1 90); do
    refresh_public_status
    state="$(read_json_value /tmp/dadooh-status/status.json public_state)"
    playback="$(read_json_value /tmp/kiosky-status.json playback_state)"
    set -- $(process_counts)
    if [ "$state" = "player_running" ] && [ "$playback" = "playing" ] && [ "${1:-0}" -ge 1 ] && [ "${2:-0}" -ge 1 ] && [ "${3:-0}" -eq 0 ] && [ "${4:-0}" -eq 0 ]; then
      return 0
    fi
    sleep 2
  done
  return 1
}

show_transition() {
  local mode="$1"
  command -v chvt >/dev/null 2>&1 && chvt "$REMOTE_TTY" >/dev/null 2>&1 || true
  printf '\033c\033[2J\033[3J\033[H\033[?25l' > "$TTY_DEVICE" 2>/dev/null || true
  env TERM=linux PYTHONPATH="$SCRIPT_DIR" python3 "$SPLASH" "$mode" --status-out "$OUT_DIR/splash-$mode-status.json" <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
}

restore_getty() {
  for unit in "${GETTY_UNITS[@]}"; do
    if [ "${GETTY_ENABLED[$unit]}" = "enabled" ]; then
      systemctl enable "$unit" >/dev/null 2>&1 || true
    else
      systemctl disable "$unit" >/dev/null 2>&1 || true
    fi
    if [ "${GETTY_ACTIVE[$unit]}" = "active" ]; then
      systemctl start "$unit" >/dev/null 2>&1 || true
    else
      systemctl stop "$unit" >/dev/null 2>&1 || true
    fi
  done
}

restore_service() {
  SERVICE_RESTORE_ATTEMPTED="true"
  if [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
    systemctl enable kiosky-player.service >/dev/null 2>&1 || true
  fi
  if [ "$INITIAL_SERVICE_ACTIVE" = "active" ] || [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
    show_transition player || true
    systemctl start kiosky-player.service >/dev/null 2>&1 || true
  fi
}

kill_visual_if_running() {
  python3 - "$VISUAL" "$WIZARD_OUT_DIR" <<'PY'
import os
import pathlib
import signal
import sys
import time
visual = sys.argv[1]
out = sys.argv[2]
pids = []
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == os.getpid():
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    joined = " ".join(parts)
    if visual in joined or out in joined:
        pids.append(int(proc.name))
for pid in pids:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
time.sleep(2)
for pid in pids:
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
PY
}

write_final_status() {
  wait_player_running || true
  python3 - "$FINAL_STATUS" "$OUT_DIR" "$WIZARD_OUT_DIR" "$MODE" "$EXPECTED_RESULT" "$WIZARD_RC" \
    "$INITIAL_SERVICE_ACTIVE" "$INITIAL_SERVICE_ENABLED" "$SERVICE_STOP_ATTEMPTED" "$SERVICE_RESTORE_ATTEMPTED" \
    "$(systemctl is-active kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null || true)" \
    "$(read_json_value /tmp/dadooh-status/status.json public_state)" \
    "$(read_json_value /tmp/kiosky-status.json playback_state)" <<'PY'
import json
import os
import pathlib
import stat
import sys

target = pathlib.Path(sys.argv[1])
out_dir = pathlib.Path(sys.argv[2])
wizard_out = pathlib.Path(sys.argv[3])
mode = sys.argv[4]
expected_result = sys.argv[5]
wizard_rc = sys.argv[6]
initial_active = sys.argv[7] or "unknown"
initial_enabled = sys.argv[8] or "unknown"
service_stop_attempted = sys.argv[9] == "true"
service_restore_attempted = sys.argv[10] == "true"
service_active = sys.argv[11] or "unknown"
service_enabled = sys.argv[12] or "unknown"
nrestarts = sys.argv[13] or "unknown"
public_state = sys.argv[14] or "unknown"
playback = sys.argv[15] or "unknown"

def load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}

setup_status = load_json(wizard_out / "setup-status.json")
network = setup_status.get("network") if isinstance(setup_status.get("network"), dict) else {}
validation = setup_status.get("validation") if isinstance(setup_status.get("validation"), dict) else {}
interface = setup_status.get("interface") if isinstance(setup_status.get("interface"), dict) else {}
counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    names = [pathlib.Path(part).name.lower() for part in parts]
    if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
        counts["setup"] += 1
    if any("totem_status_renderer" in name for name in names):
        counts["renderer"] += 1
    if any(name == "mpv" for name in names):
        counts["mpv"] += 1
    if "kiosk.py" in names:
        counts["player"] += 1

payload = {
    "schema_version": "dadooh-c10.6-open-settings-session.v1",
    "mode": mode,
    "expected_result": expected_result,
    "trigger_opens_wizard_directly": True,
    "wizard_rc": wizard_rc,
    "visual_wizard_opened": (wizard_out / "screens").exists() or bool(setup_status) or (wizard_out / "setup-cancelled.json").exists(),
    "visual_candidate_generated": (wizard_out / "config.candidate.json").exists(),
    "setup_cancelled": (wizard_out / "setup-cancelled.json").exists(),
    "orientation_category": {0: "landscape", 90: "portrait_right", 180: "inverted", 270: "portrait_left"}.get(
        validation.get("rotation_degrees"), "unknown"
    ),
    "rotation_degrees": validation.get("rotation_degrees", "unknown"),
    "network_step": network.get("network_step", "unknown"),
    "linux_prompt_visible": bool(interface.get("linux_prompt_visible", False)),
    "service_initial_active": initial_active,
    "service_initial_enabled": initial_enabled,
    "service_stop_attempted": service_stop_attempted,
    "service_restore_attempted": service_restore_attempted,
    "service_active": service_active,
    "service_enabled": service_enabled,
    "nrestarts": nrestarts,
    "public_state": public_state,
    "playback": playback,
    "process_counts": counts,
    "writer_called": False,
    "real_config_read": False,
    "real_config_written": False,
    "wifi_changed": False,
    "networkmanager_changed": False,
    "hotspot_created": False,
    "portal_created": False,
    "root_read_only_enabled": False,
    "power_cut_tested": False,
    "credential_values_published": False,
    "network_identifiers_published": False,
    "environment_identifier_raw_published": False,
    "config_content_published": False,
    "raw_logs_written": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
assert stat.S_IMODE(out_dir.stat().st_mode) == 0o700
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

on_exit() {
  rc="$?"
  trap - EXIT INT TERM HUP
  kill_visual_if_running || true
  restore_service || true
  write_final_status || true
  restore_getty || true
  rmdir "$LOCK_DIR" 2>/dev/null || true
  exit "$rc"
}
trap on_exit EXIT INT TERM HUP

for unit in "${GETTY_UNITS[@]}"; do
  systemctl stop "$unit" >/dev/null 2>&1 || true
done

show_transition setup || true
if [ "$INITIAL_SERVICE_ACTIVE" = "active" ] || [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
  SERVICE_STOP_ATTEMPTED="true"
  systemctl stop kiosky-player.service >/dev/null 2>&1 || true
  for _ in $(seq 1 30); do
    set -- $(process_counts)
    if [ "${1:-0}" -eq 0 ] && [ "${2:-0}" -eq 0 ] && [ "${3:-0}" -eq 0 ] && [ "${4:-0}" -eq 0 ]; then
      break
    fi
    sleep 1
  done
fi
show_transition setup || true

set -- $(process_counts)
if [ "${1:-0}" -ne 0 ] || [ "${2:-0}" -ne 0 ] || [ "${3:-0}" -ne 0 ] || [ "${4:-0}" -ne 0 ]; then
  echo "hdmi_not_free_after_player_pause" >&2
  exit 42
fi

set +e
if [ "$MODE" = "preview" ]; then
  setsid openvt -c "$REMOTE_TTY" -s -f -w -- \
    env TERM=linux PYTHONPATH="$SCRIPT_DIR" /usr/bin/python3 "$VISUAL" \
      --out-dir "$WIZARD_OUT_DIR" --preview-screens --show-preview --auto-exit-sec "$PREVIEW_SEC" >/dev/null 2>&1
  WIZARD_RC="$?"
else
  setsid openvt -c "$REMOTE_TTY" -s -f -w -- \
    env TERM=linux PYTHONPATH="$SCRIPT_DIR" /usr/bin/python3 "$VISUAL" \
      --out-dir "$WIZARD_OUT_DIR" >/dev/null 2>&1 &
  OPENVT_PID="$!"
  deadline=$(( $(date +%s) + RUN_TIMEOUT_SEC ))
  while kill -0 "$OPENVT_PID" 2>/dev/null && [ "$(date +%s)" -lt "$deadline" ]; do
    sleep 2
  done
  if kill -0 "$OPENVT_PID" 2>/dev/null; then
    kill -TERM "-$OPENVT_PID" 2>/dev/null || kill -TERM "$OPENVT_PID" 2>/dev/null || true
    sleep 3
    kill -KILL "-$OPENVT_PID" 2>/dev/null || kill -KILL "$OPENVT_PID" 2>/dev/null || true
    kill_visual_if_running || true
    WIZARD_RC="124"
  else
    wait "$OPENVT_PID"
    WIZARD_RC="$?"
  fi
fi
set -e

if [ "$EXPECTED_RESULT" = "preview" ] && [ ! -d "$WIZARD_OUT_DIR/screens" ]; then
  echo "preview_not_generated" >&2
  exit 41
fi
if [ "$EXPECTED_RESULT" = "cancelled" ] && [ ! -f "$WIZARD_OUT_DIR/setup-cancelled.json" ] && [ "$WIZARD_RC" != "130" ]; then
  echo "expected_cancel_not_observed" >&2
  exit 43
fi
if [ "$EXPECTED_RESULT" = "candidate_ready" ] && [ ! -f "$WIZARD_OUT_DIR/config.candidate.json" ]; then
  echo "candidate_not_generated" >&2
  exit 44
fi

restore_service || true
wait_player_running || true
write_final_status
restore_getty || true
trap - EXIT INT TERM HUP
rmdir "$LOCK_DIR" 2>/dev/null || true
exit 0
