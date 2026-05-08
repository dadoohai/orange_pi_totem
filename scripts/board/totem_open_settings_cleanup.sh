#!/usr/bin/env bash
set -euo pipefail

REQUEST_DIR="/run/dadooh-settings"
LOCK_DIR="/run/totem/settings-session.lock"
OUT_DIR="/run/dadooh-settings"
REMOTE_TTY="2"
REASON="manual"

usage() {
  cat <<'USAGE'
Usage:
  totem_open_settings_cleanup.sh [--reason TEXT] [--request-dir /run/...] [--lock-dir /run/...]

Best-effort cleanup for the visual Settings session. It removes only the
public request/lock state, kills leftover visual setup processes, and restores
the player/config_missing visual state. It never reads config content, never
calls writer, never changes Wi-Fi and never publishes input.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --reason)
      shift
      REASON="${1:-manual}"
      ;;
    --request-dir)
      shift
      REQUEST_DIR="${1:-}"
      ;;
    --lock-dir)
      shift
      LOCK_DIR="${1:-}"
      ;;
    --out-dir)
      shift
      OUT_DIR="${1:-}"
      ;;
    --tty)
      shift
      REMOTE_TTY="${1:-}"
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

case "$REQUEST_DIR" in
  /run/*|/tmp/*) ;;
  *) echo "error: --request-dir must be under /run or /tmp" >&2; exit 2 ;;
esac
case "$LOCK_DIR" in
  /run/*|/tmp/*) ;;
  *) echo "error: --lock-dir must be under /run or /tmp" >&2; exit 2 ;;
esac
case "$OUT_DIR" in
  /run/*|/tmp/*) ;;
  *) echo "error: --out-dir must be under /run or /tmp" >&2; exit 2 ;;
esac
case "$REMOTE_TTY" in
  ''|*[!0-9]*|0) echo "error: --tty must be a positive integer" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPLASH="$SCRIPT_DIR/totem_visual_splash.py"
TTY_GUARD="$SCRIPT_DIR/totem_visual_tty_guard.sh"
TTY_DEVICE="/dev/tty$REMOTE_TTY"
STATUS_OUT="$OUT_DIR/open-settings-cleanup-status.json"

mkdir -p "$REQUEST_DIR" "$OUT_DIR"
chmod 700 "$REQUEST_DIR" "$OUT_DIR" 2>/dev/null || true

session_process_running() {
  python3 - <<'PY'
import os
import pathlib
import sys

self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    pid = int(proc.name)
    if pid == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    joined = " ".join(parts)
    if "totem_open_settings_session.sh" in joined:
        sys.exit(0)
sys.exit(1)
PY
}

kill_leftover_visuals() {
  python3 - <<'PY'
import os
import pathlib
import signal
import time

self_pid = os.getpid()
pids = []
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    pid = int(proc.name)
    if pid == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    joined = " ".join(parts)
    if "totem_setup_visual_wizard.py" in joined or "dadooh-c10-6-2-visual-wizard" in joined:
        pids.append(pid)
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
print(len(pids))
PY
}

show_transition() {
  local mode="$1"
  if [ -e "$TTY_DEVICE" ]; then
    command -v chvt >/dev/null 2>&1 && chvt "$REMOTE_TTY" >/dev/null 2>&1 || true
    if [ -x "$TTY_GUARD" ]; then
      "$TTY_GUARD" --clear --tty "$REMOTE_TTY" >/dev/null 2>&1 || true
    fi
    printf '\033c\033[2J\033[3J\033[H\033[?25l' > "$TTY_DEVICE" 2>/dev/null || true
  fi
  if [ -f "$SPLASH" ]; then
    env TERM=linux PYTHONPATH="$SCRIPT_DIR" python3 "$SPLASH" "$mode" \
      --status-out "$OUT_DIR/cleanup-splash-status.json" \
      <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
  fi
}

restore_product_state() {
  if systemctl is-enabled kiosky-player.service >/dev/null 2>&1; then
    if [ -f /data/config/config.json ]; then
      show_transition player || true
    else
      show_transition config_pending || true
    fi
    systemctl start kiosky-player.service >/dev/null 2>&1 || true
  fi
}

write_status() {
  local skipped="$1"
  local visual_killed_count="$2"
  python3 - "$STATUS_OUT" "$REASON" "$skipped" "$visual_killed_count" "$LOCK_DIR" "$REQUEST_DIR" <<'PY'
import json
import os
import pathlib
import sys
import time

target = pathlib.Path(sys.argv[1])
payload = {
    "schema_version": "dadooh-open-settings-cleanup.v1",
    "cleaned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "reason": sys.argv[2],
    "skipped_active_session": sys.argv[3] == "true",
    "leftover_visual_processes_killed_count": int(sys.argv[4]) if sys.argv[4].isdigit() else 0,
    "session_lock_present_after": pathlib.Path(sys.argv[5]).exists(),
    "request_present_after": (pathlib.Path(sys.argv[6]) / "request.json").exists(),
    "writer_called": False,
    "real_config_read": False,
    "real_config_written": False,
    "wifi_changed": False,
    "input_values_published": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
PY
}

if session_process_running; then
  write_status true 0
  exit 0
fi

rm -f "$REQUEST_DIR/request.json" 2>/dev/null || true
rm -rf "$LOCK_DIR" 2>/dev/null || true
visual_killed_count="$(kill_leftover_visuals || printf '0\n')"
restore_product_state || true
write_status false "$visual_killed_count"
