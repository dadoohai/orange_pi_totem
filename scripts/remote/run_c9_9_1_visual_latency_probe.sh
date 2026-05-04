#!/usr/bin/env bash
set -euo pipefail

HOST="root@192.168.1.147"
MODE="prepare-only"
REMOTE_TTY="2"
RUN_TIMEOUT_SEC="900"
REMOTE_DIR="/tmp/dadooh-c9-9-1"
REMOTE_OUT_DIR="/tmp/dadooh-c9-9-1-visual-latency-probe-run"
PROBE_OUT_DIR="/tmp/dadooh-c9-9-1-visual-latency-probe"
METHOD="unique_path_ipc_wait"
MPV_VIDEO_MODE="drm"
CONFIRM_PHRASE="CONFIRMO C9.9.1 PROBE VISUAL COM PAUSA DO PLAYER"

usage() {
  cat <<'USAGE'
Usage:
  run_c9_9_1_visual_latency_probe.sh [host] [--prepare-only|--probe|--run-visual-wizard-latency-check] [--tty N] [--timeout-sec N] [--method NAME] [--mpv-video-mode drm|gpu_drm]

Modes:
  --prepare-only
      Copy the C9.9.1 probe to /tmp and run self-test. Does not pause player.

  --probe
      Requires exact human confirmation. Pauses kiosky-player.service, runs
      synthetic auto-probe on HDMI/DRM, restores the player, and writes
      sanitized artifacts under /tmp.

  --run-visual-wizard-latency-check
      Requires exact human confirmation. Pauses player and opens a manual
      synthetic check. Human should press: Enter, A, B, Backspace, Enter.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only)
      MODE="prepare-only"
      ;;
    --probe)
      MODE="probe"
      ;;
    --run-visual-wizard-latency-check)
      MODE="run-visual-wizard-latency-check"
      ;;
    --tty)
      shift
      REMOTE_TTY="${1:-}"
      ;;
    --timeout-sec)
      shift
      RUN_TIMEOUT_SEC="${1:-}"
      ;;
    --method)
      shift
      METHOD="${1:-}"
      ;;
    --mpv-video-mode)
      shift
      MPV_VIDEO_MODE="${1:-}"
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
  prepare-only|probe|run-visual-wizard-latency-check)
    ;;
  *)
    echo "error: unsupported mode $MODE" >&2
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

case "$METHOD" in
  same_path_ipc|unique_path_ipc|unique_path_fsync_ipc|unique_path_ipc_wait|restart_mpv_unique_path)
    ;;
  *)
    echo "error: unsupported method $METHOD" >&2
    exit 2
    ;;
esac

case "$MPV_VIDEO_MODE" in
  drm|gpu_drm)
    ;;
  *)
    echo "error: unsupported --mpv-video-mode $MPV_VIDEO_MODE" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BOARD_DIR="$REPO_ROOT/scripts/board"

LOCAL_PROBE="$BOARD_DIR/totem_visual_render_latency_probe.py"
if [ ! -f "$LOCAL_PROBE" ]; then
  echo "error: missing local probe" >&2
  exit 1
fi

echo "Preparing C9.9.1 latency probe workspace on $HOST"
ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR'"

echo "Copying C9.9.1 latency probe to temporary board workspace"
scp "$LOCAL_PROBE" "$HOST:$REMOTE_DIR/"

echo "Running C9.9.1 prepare checks on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail
PROBE="$REMOTE_DIR/totem_visual_render_latency_probe.py"
python3 "$PROBE" --self-test
echo "remote C9.9.1 prepare checks: ok"
REMOTE_PREP

if [ "$MODE" = "prepare-only" ]; then
  echo "C9.9.1 prepare-only complete. Evidence dir reserved: $REMOTE_OUT_DIR"
  exit 0
fi

echo
echo "HDMI/tela local deve estar conectada. O player sera pausado temporariamente."
echo "O probe usa telas sinteticas sem dados reais."
echo "Before pausing the player and opening C9.9.1 probe, type exactly:"
echo "$CONFIRM_PHRASE"
printf '> '
IFS= read -r AUTH_TEXT
if [ "$AUTH_TEXT" != "$CONFIRM_PHRASE" ]; then
  echo "Authorization text did not match. Aborting before service pause." >&2
  exit 20
fi

echo "Running authorized C9.9.1 visual latency probe"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' PROBE_OUT_DIR='$PROBE_OUT_DIR' REMOTE_TTY='$REMOTE_TTY' RUN_TIMEOUT_SEC='$RUN_TIMEOUT_SEC' MODE='$MODE' METHOD='$METHOD' MPV_VIDEO_MODE='$MPV_VIDEO_MODE' bash -s" <<'REMOTE_RUN'
set -euo pipefail

PROBE="$REMOTE_DIR/totem_visual_render_latency_probe.py"
RUN_OUT="$REMOTE_OUT_DIR/$MODE"
FINAL_STATUS="$RUN_OUT/final-status.json"
PROBE_RC="not_run"
INITIAL_SERVICE_ACTIVE="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
INITIAL_SERVICE_ENABLED="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"
SERVICE_STOP_ATTEMPTED="false"
SERVICE_RESTORE_ATTEMPTED="false"

umask 077
rm -rf "$RUN_OUT" "$PROBE_OUT_DIR"
mkdir -p "$RUN_OUT" "$PROBE_OUT_DIR"
chmod 700 "$RUN_OUT" "$PROBE_OUT_DIR"

process_counts() {
  python3 - <<'PY'
import os
import pathlib
counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0, "probe": 0}
self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    names = [pathlib.Path(part).name.lower() for part in parts]
    if "totem_visual_render_latency_probe.py" in names:
        counts["probe"] += 1
    if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
        counts["setup"] += 1
    if any("totem_status_renderer" in name for name in names):
        counts["renderer"] += 1
    if any(name == "mpv" for name in names):
        counts["mpv"] += 1
    if "kiosk.py" in names:
        counts["player"] += 1
print(f"{counts['player']} {counts['mpv']} {counts['renderer']} {counts['setup']} {counts['probe']}")
PY
}

read_playback() {
  python3 - <<'PY'
import json
import pathlib
try:
    data = json.loads(pathlib.Path("/tmp/kiosky-status.json").read_text(encoding="utf-8"))
    value = data.get("playback_state")
    print(value if isinstance(value, str) else "unknown")
except Exception:
    print("unknown")
PY
}

read_public_state() {
  python3 - <<'PY'
import json
import pathlib
try:
    data = json.loads(pathlib.Path("/tmp/dadooh-status/status.json").read_text(encoding="utf-8"))
    value = data.get("public_state") or data.get("state")
    print(value if isinstance(value, str) else "unknown")
except Exception:
    print("unknown")
PY
}

refresh_public_status() {
  if [ -f /opt/totem/bin/totem_status_aggregate.py ]; then
    PYTHONPATH=/opt/totem/bin python3 /opt/totem/bin/totem_status_aggregate.py >/dev/null 2>&1 || true
  else
    return 0
  fi
}

wait_public_state() {
  for _ in $(seq 1 45); do
    refresh_public_status
    state="$(read_public_state)"
    if [ "$state" = "player_running" ]; then
      return 0
    fi
    playback="$(read_playback)"
    set -- $(process_counts)
    if [ "${1:-0}" -ge 1 ] && [ "${2:-0}" -ge 1 ] && [ "${3:-0}" -eq 0 ] && [ "${4:-0}" -eq 0 ] && [ "$playback" = "playing" ]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

write_final_status() {
  wait_public_state || true
  python3 - "$FINAL_STATUS" "$RUN_OUT" "$PROBE_OUT_DIR" "$MODE" "$METHOD" "$PROBE_RC" \
    "$INITIAL_SERVICE_ACTIVE" "$INITIAL_SERVICE_ENABLED" "$SERVICE_STOP_ATTEMPTED" "$SERVICE_RESTORE_ATTEMPTED" \
    "$(systemctl is-active kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null || true)" \
    "$(read_public_state)" "$(read_playback)" <<'PY'
import json
import os
import pathlib
import sys

target = pathlib.Path(sys.argv[1])
run_out = pathlib.Path(sys.argv[2])
probe_out = pathlib.Path(sys.argv[3])
mode = sys.argv[4]
method = sys.argv[5]
probe_rc = sys.argv[6]
initial_active = sys.argv[7] or "unknown"
initial_enabled = sys.argv[8] or "unknown"
service_stop_attempted = sys.argv[9] == "true"
service_restore_attempted = sys.argv[10] == "true"
service_active = sys.argv[11] or "unknown"
service_enabled = sys.argv[12] or "unknown"
nrestarts = sys.argv[13] or "unknown"
public_state = sys.argv[14] or "unknown"
playback = sys.argv[15] or "unknown"

counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0, "probe": 0}
self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    names = [pathlib.Path(part).name.lower() for part in parts]
    if "totem_visual_render_latency_probe.py" in names:
        counts["probe"] += 1
    if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
        counts["setup"] += 1
    if any("totem_status_renderer" in name for name in names):
        counts["renderer"] += 1
    if any(name == "mpv" for name in names):
        counts["mpv"] += 1
    if "kiosk.py" in names:
        counts["player"] += 1

probe_status = {}
probe_status_path = probe_out / "latency-status.json"
if probe_status_path.exists():
    try:
        probe_status = json.loads(probe_status_path.read_text(encoding="utf-8"))
    except Exception:
        probe_status = {}

payload = {
    "schema_version": "dadooh-c9.9.1-visual-latency-run.v1",
    "mode": mode,
    "method": method,
    "mpv_video_mode": probe_status.get("mpv_video_mode", "unknown"),
    "probe_rc": probe_rc,
    "probe_status_present": bool(probe_status),
    "probable_cause": probe_status.get("probable_cause", "unknown"),
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
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "wifi_changed": False,
    "network_changed": False,
    "hotspot_created": False,
    "portal_created": False,
    "reboot_called": False,
    "credential_values_published": False,
    "network_identifiers_published": False,
    "raw_screenshot_saved": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

restore_service() {
  SERVICE_RESTORE_ATTEMPTED="true"
  if [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
    systemctl enable kiosky-player.service >/dev/null 2>&1 || true
  fi
  if [ "$INITIAL_SERVICE_ACTIVE" = "active" ] || [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
    systemctl start kiosky-player.service >/dev/null 2>&1 || true
  fi
}

kill_probe_if_running() {
  python3 - "$PROBE" "$PROBE_OUT_DIR" <<'PY'
import os
import pathlib
import signal
import sys
import time
probe = sys.argv[1]
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
    if probe in joined or out in joined:
        pids.append(int(proc.name))
for pid in pids:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
time.sleep(1)
for pid in pids:
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
PY
}

on_exit() {
  rc="$?"
  trap - EXIT INT TERM HUP
  kill_probe_if_running || true
  restore_service || true
  write_final_status || true
  exit "$rc"
}
trap on_exit EXIT INT TERM HUP

if [ "$INITIAL_SERVICE_ACTIVE" = "active" ] || [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
  SERVICE_STOP_ATTEMPTED="true"
  systemctl stop kiosky-player.service >/dev/null 2>&1 || true
  for _ in $(seq 1 30); do
    set -- $(process_counts)
    if [ "${1:-0}" -eq 0 ] && [ "${2:-0}" -eq 0 ] && [ "${3:-0}" -eq 0 ] && [ "${4:-0}" -eq 0 ] && [ "${5:-0}" -eq 0 ]; then
      break
    fi
    sleep 1
  done
fi

set -- $(process_counts)
if [ "${1:-0}" -ne 0 ] || [ "${2:-0}" -ne 0 ] || [ "${3:-0}" -ne 0 ] || [ "${4:-0}" -ne 0 ] || [ "${5:-0}" -ne 0 ]; then
  echo "hdmi_not_free_after_player_pause" >&2
  exit 42
fi

set +e
if [ "$MODE" = "probe" ]; then
  setsid openvt -c "$REMOTE_TTY" -s -f -w -- \
    env TERM=linux /usr/bin/python3 "$PROBE" --auto-probe --mpv-video-mode "$MPV_VIDEO_MODE" --out-dir "$PROBE_OUT_DIR" >/dev/null 2>&1 &
else
  setsid openvt -c "$REMOTE_TTY" -s -f -w -- \
    env TERM=linux /usr/bin/python3 "$PROBE" --manual-check --method "$METHOD" --mpv-video-mode "$MPV_VIDEO_MODE" --out-dir "$PROBE_OUT_DIR" >/dev/null 2>&1 &
fi
PROBE_PID="$!"
deadline=$(( $(date +%s) + RUN_TIMEOUT_SEC ))
while kill -0 "$PROBE_PID" 2>/dev/null && [ "$(date +%s)" -lt "$deadline" ]; do
  sleep 2
done
if kill -0 "$PROBE_PID" 2>/dev/null; then
  kill -TERM "-$PROBE_PID" 2>/dev/null || kill -TERM "$PROBE_PID" 2>/dev/null || true
  sleep 2
  kill -KILL "-$PROBE_PID" 2>/dev/null || kill -KILL "$PROBE_PID" 2>/dev/null || true
  kill_probe_if_running || true
  PROBE_RC="124"
else
  wait "$PROBE_PID"
  PROBE_RC="$?"
fi
set -e

if [ ! -f "$PROBE_OUT_DIR/latency-status.json" ]; then
  echo "probe_status_not_generated" >&2
  exit 44
fi

exit 0
REMOTE_RUN

echo "C9.9.1 visual latency probe complete. Evidence: $REMOTE_OUT_DIR"
