#!/usr/bin/env bash
set -euo pipefail

REQUEST_DIR="/run/dadooh-settings"
LOCK_DIR="/run/totem/settings-session.lock"
OUT_DIR="/run/dadooh-settings"
REMOTE_TTY="2"
REASON="manual"
PRODUCT_RESET_STATE_DIR="${TOTEM_PRODUCT_RESET_STATE_DIR:-/data/state/totem-appliance/product-reset}"
PRODUCT_RESET_PENDING="false"
TERMINAL_ACTION_PENDING="false"
TERMINAL_ACTION_MAX_AGE_SEC="120"
EXPIRE_TERMINAL_ACTION="false"
TERMINAL_ACTION_RECONCILE_UNIT=""
UPDATE_LOCK_FILE="${TOTEM_UPDATE_LOCK_FILE:-/run/totem-updatectl.lock}"
UPDATE_LOCK_TIMEOUT_SEC="${TOTEM_PRODUCT_RESET_UPDATE_LOCK_TIMEOUT_SEC:-5}"
UPDATE_LOCK_STATE="not_checked"
RESET_HANDOFF_PRESERVED="false"
UPDATE_LOCK_HOLDER_ACTIVE_PID=""
PRODUCT_RESET_GC_UNIT="totem-product-reset-gc.service"
PRODUCT_RESET_GC_ENQUEUED="false"
PRODUCT_RESET_GC_ENQUEUE_RC="not_attempted"
SELF_TEST="false"

usage() {
  cat <<'USAGE'
Usage:
  totem_open_settings_cleanup.sh [--reason TEXT] [--request-dir /run/...] [--lock-dir /run/...] [--expire-terminal-action] [--terminal-action-reconcile-unit UNIT] [--self-test]

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
    --expire-terminal-action)
      EXPIRE_TERMINAL_ACTION="true"
      ;;
    --terminal-action-reconcile-unit)
      shift
      TERMINAL_ACTION_RECONCILE_UNIT="${1:-}"
      ;;
    --self-test)
      SELF_TEST="true"
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
if [ -n "$TERMINAL_ACTION_RECONCILE_UNIT" ] \
  && ! [[ "$TERMINAL_ACTION_RECONCILE_UNIT" =~ ^totem-terminal-action-reconcile-[0-9a-f]{32}$ ]]; then
  echo "error: invalid --terminal-action-reconcile-unit" >&2
  exit 2
fi
case "$UPDATE_LOCK_TIMEOUT_SEC" in
  ''|*[!0-9]*|0) echo "error: product reset update lock timeout must be a positive integer" >&2; exit 2 ;;
esac
if [ "$UPDATE_LOCK_TIMEOUT_SEC" -gt 30 ]; then
  echo "error: product reset update lock timeout must not exceed 30 seconds" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPLASH="$SCRIPT_DIR/totem_visual_splash.py"
TTY_GUARD="$SCRIPT_DIR/totem_visual_tty_guard.sh"
TTY_DEVICE="/dev/tty$REMOTE_TTY"
STATUS_OUT="$OUT_DIR/open-settings-cleanup-status.json"
TERMINAL_ACTION_MARKER="$REQUEST_DIR/terminal-action.json"
PLAYER_RESTORE_ATTEMPTED="false"
PLAYER_RESTORE_START_MODE="none"
PLAYER_RESTORE_START_RC="not_attempted"

product_reset_pending() {
  if [ -L "$PRODUCT_RESET_STATE_DIR" ]; then
    return 0
  fi
  if [ -e "$PRODUCT_RESET_STATE_DIR" ] && [ ! -d "$PRODUCT_RESET_STATE_DIR" ]; then
    return 0
  fi
  [ -e "$PRODUCT_RESET_STATE_DIR/intent.json" ] \
    || [ -L "$PRODUCT_RESET_STATE_DIR/intent.json" ] \
    || [ -e "$PRODUCT_RESET_STATE_DIR/pending-credential.json" ] \
    || [ -L "$PRODUCT_RESET_STATE_DIR/pending-credential.json" ] \
    || [ -e "$PRODUCT_RESET_STATE_DIR/receipt.json" ] \
    || [ -L "$PRODUCT_RESET_STATE_DIR/receipt.json" ]
}

release_product_reset_update_lock() {
  if [ -n "$UPDATE_LOCK_HOLDER_ACTIVE_PID" ]; then
    kill -TERM "$UPDATE_LOCK_HOLDER_ACTIVE_PID" 2>/dev/null || true
    wait "$UPDATE_LOCK_HOLDER_ACTIVE_PID" 2>/dev/null || true
    UPDATE_LOCK_HOLDER_ACTIVE_PID=""
  fi
}

acquire_product_reset_update_lock() {
  local lock_status=""
  coproc CLEANUP_UPDATE_LOCK_HOLDER {
    exec /usr/bin/python3 /dev/fd/3 "$UPDATE_LOCK_FILE" "$$" "$UPDATE_LOCK_TIMEOUT_SEC" 3<<'PY'
import fcntl
import os
import pathlib
import stat
import sys
import time

path = pathlib.Path(sys.argv[1])
parent_pid = int(sys.argv[2])
timeout_sec = int(sys.argv[3])
try:
    if (
        not path.is_absolute()
        or path.parent.resolve(strict=True) != path.parent
    ):
        raise RuntimeError("lock_path_invalid")
    parent_info = path.parent.stat()
    if (
        not stat.S_ISDIR(parent_info.st_mode)
        or parent_info.st_uid != os.geteuid()
        or stat.S_IMODE(parent_info.st_mode) & 0o022
    ):
        raise RuntimeError("lock_parent_untrusted")
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("lock_nofollow_unavailable")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
        raise RuntimeError("lock_file_untrusted")
    os.fchmod(fd, 0o600)
    deadline = time.monotonic() + timeout_sec
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() >= deadline:
                print("BUSY", flush=True)
                raise SystemExit(0)
            time.sleep(0.1)
    print("LOCKED", flush=True)
    while os.getppid() == parent_pid:
        time.sleep(0.2)
except Exception as exc:
    print(f"ERROR:{type(exc).__name__}", flush=True)
    raise SystemExit(1)
PY
  }
  UPDATE_LOCK_HOLDER_ACTIVE_PID="$CLEANUP_UPDATE_LOCK_HOLDER_PID"
  local status_fd="${CLEANUP_UPDATE_LOCK_HOLDER[0]}"
  local input_fd="${CLEANUP_UPDATE_LOCK_HOLDER[1]}"
  exec {input_fd}>&-
  IFS= read -r lock_status <&"$status_fd" || true
  exec {status_fd}<&-
  if [ "$lock_status" = "LOCKED" ]; then
    UPDATE_LOCK_STATE="locked"
    return 0
  fi
  if [ "$lock_status" = "BUSY" ]; then
    UPDATE_LOCK_STATE="busy"
  else
    UPDATE_LOCK_STATE="unavailable"
  fi
  release_product_reset_update_lock
  return 1
}

terminal_action_pending() {
  if [ "${EXPIRE_TERMINAL_ACTION:-false}" = "true" ]; then
    return 1
  fi
  python3 - "$TERMINAL_ACTION_MARKER" "$TERMINAL_ACTION_MAX_AGE_SEC" <<'PY'
import datetime as dt
import json
import os
import pathlib
import stat
import sys
import uuid

path = pathlib.Path(sys.argv[1])
max_age_sec = int(sys.argv[2])
try:
    parent_info = path.parent.stat(follow_symlinks=False)
    info = path.stat(follow_symlinks=False)
    if (
        path.is_symlink()
        or path.parent.is_symlink()
        or not stat.S_ISDIR(parent_info.st_mode)
        or parent_info.st_uid != os.geteuid()
        or stat.S_IMODE(parent_info.st_mode) & 0o077
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or info.st_size <= 0
        or info.st_size > 4096
    ):
        raise SystemExit(1)
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, ValueError, json.JSONDecodeError):
    raise SystemExit(1)
expected_fields = {
    "schema_version",
    "phase",
    "action",
    "request_id",
    "settings_session_id",
    "prepared_at_utc",
    "accepted_at_utc",
}
valid = isinstance(payload, dict) and set(payload) == expected_fields
if valid:
    try:
        request_id = uuid.UUID(str(payload.get("request_id")))
        accepted = dt.datetime.fromisoformat(str(payload.get("accepted_at_utc")).replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        age = (now - accepted).total_seconds()
        valid = (
            payload.get("schema_version") == "dadooh.c26.terminal-action.v1"
            and payload.get("phase") == "accepted"
            and payload.get("action") in {"restart", "poweroff"}
            and request_id.version == 4
            and str(request_id) == payload.get("request_id")
            and isinstance(payload.get("settings_session_id"), str)
            and len(payload["settings_session_id"]) == 32
            and all(char in "0123456789abcdef" for char in payload["settings_session_id"])
            and isinstance(payload.get("prepared_at_utc"), str)
            and isinstance(payload.get("accepted_at_utc"), str)
            and payload["prepared_at_utc"].endswith("Z")
            and payload["accepted_at_utc"].endswith("Z")
            and accepted.utcoffset() == dt.timedelta(0)
            and -60 <= age <= max_age_sec
        )
    except (TypeError, ValueError):
        valid = False
raise SystemExit(0 if valid else 1)
PY
}

terminal_action_reconcile_complete() {
  [ "$EXPIRE_TERMINAL_ACTION" = "true" ] || return 1
  [ -n "$TERMINAL_ACTION_RECONCILE_UNIT" ] || return 1
  [ ! -e "$LOCK_DIR" ] && [ ! -L "$LOCK_DIR" ] || return 1
  [ ! -e "$REQUEST_DIR/request.json" ] && [ ! -L "$REQUEST_DIR/request.json" ] || return 1
  [ ! -e "$TERMINAL_ACTION_MARKER" ] && [ ! -L "$TERMINAL_ACTION_MARKER" ] || return 1
  [ "$PLAYER_RESTORE_START_RC" = "0" ]
}

stop_terminal_action_reconcile() {
  [ -n "$TERMINAL_ACTION_RECONCILE_UNIT" ] || return 0
  /usr/bin/systemctl --no-block stop "${TERMINAL_ACTION_RECONCILE_UNIT}.timer" \
    >/dev/null 2>&1 || true
}

if terminal_action_pending; then
  TERMINAL_ACTION_PENDING="true"
fi

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

restore_tty_text_mode() {
  [ -e "$TTY_DEVICE" ] || return 0
  python3 - "$TTY_DEVICE" <<'PY'
import fcntl
import os
import sys

KDSETMODE = 0x4B3A
KD_TEXT = 0x00
fd = os.open(sys.argv[1], os.O_RDWR | os.O_NOCTTY)
try:
    fcntl.ioctl(fd, KDSETMODE, KD_TEXT)
finally:
    os.close(fd)
PY
  if command -v timeout >/dev/null 2>&1; then
    timeout -k 0.2s 1.0s /usr/bin/stty -F "$TTY_DEVICE" sane >/dev/null 2>&1 || true
  else
    /usr/bin/stty -F "$TTY_DEVICE" sane >/dev/null 2>&1 || true
  fi
  if [ -x "$TTY_GUARD" ]; then
    "$TTY_GUARD" --quiet --tty "$REMOTE_TTY" >/dev/null 2>&1 || true
  fi
}

cleanup_private_session_artifacts() {
  local path
  for path in \
    /tmp/dadooh-c10-6-2-private/private-values.json \
    /tmp/dadooh-c10-6-2-private/last-settings.json \
    /tmp/dadooh-c10-6-2-handoff/config.candidate.private.json \
    /tmp/dadooh-c10-6-2-visual-wizard/qr-pairing/private-values.json
  do
    rm -f -- "$path" 2>/dev/null || true
  done
  rmdir /tmp/dadooh-c10-6-2-private 2>/dev/null || true
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
  if systemctl is-active --quiet kiosky-player.service; then
    PLAYER_RESTORE_START_MODE="already-active"
    PLAYER_RESTORE_START_RC="0"
    return 0
  fi
  if ! systemctl is-enabled kiosky-player.service >/dev/null 2>&1; then
    PLAYER_RESTORE_START_MODE="service-not-enabled"
    PLAYER_RESTORE_START_RC="1"
    return 1
  fi
  if [ -f /data/config/config.json ]; then
    show_transition player || true
  else
    show_transition config_pending || true
  fi
  PLAYER_RESTORE_ATTEMPTED="true"
  PLAYER_RESTORE_START_MODE="no-block"
  if /usr/bin/timeout -k 1s 5s systemctl start --no-block kiosky-player.service >/dev/null 2>&1; then
    PLAYER_RESTORE_START_RC="0"
  else
    PLAYER_RESTORE_START_RC="$?"
    return "$PLAYER_RESTORE_START_RC"
  fi
}

enqueue_product_reset_gc() {
  if [ ! -e "$PRODUCT_RESET_STATE_DIR/gc-pending.json" ] \
    && [ ! -L "$PRODUCT_RESET_STATE_DIR/gc-pending.json" ]; then
    return 0
  fi
  if /usr/bin/timeout -k 1s 5s systemctl start --no-block "$PRODUCT_RESET_GC_UNIT" >/dev/null 2>&1; then
    PRODUCT_RESET_GC_ENQUEUED="true"
    PRODUCT_RESET_GC_ENQUEUE_RC="0"
    return 0
  fi
  PRODUCT_RESET_GC_ENQUEUE_RC="$?"
  return "$PRODUCT_RESET_GC_ENQUEUE_RC"
}

write_status() {
  local skipped="$1"
  local killed_count="$2"
  env \
    PLAYER_RESTORE_ATTEMPTED="$PLAYER_RESTORE_ATTEMPTED" \
    PLAYER_RESTORE_START_MODE="$PLAYER_RESTORE_START_MODE" \
    PLAYER_RESTORE_START_RC="$PLAYER_RESTORE_START_RC" \
    PRODUCT_RESET_PENDING="$PRODUCT_RESET_PENDING" \
    TERMINAL_ACTION_PENDING="$TERMINAL_ACTION_PENDING" \
    UPDATE_LOCK_STATE="$UPDATE_LOCK_STATE" \
    RESET_HANDOFF_PRESERVED="$RESET_HANDOFF_PRESERVED" \
    PRODUCT_RESET_GC_ENQUEUED="$PRODUCT_RESET_GC_ENQUEUED" \
    PRODUCT_RESET_GC_ENQUEUE_RC="$PRODUCT_RESET_GC_ENQUEUE_RC" \
    PLAYER_SERVICE_ACTIVE_AFTER="$(systemctl is-active kiosky-player.service 2>/dev/null || true)" \
    PLAYER_SERVICE_RESULT_AFTER="$(systemctl show kiosky-player.service -p Result --value 2>/dev/null || true)" \
    PLAYER_SERVICE_EXEC_MAIN_STATUS_AFTER="$(systemctl show kiosky-player.service -p ExecMainStatus --value 2>/dev/null || true)" \
    python3 - "$STATUS_OUT" "$REASON" "$skipped" "$killed_count" "$LOCK_DIR" "$REQUEST_DIR" <<'PY'
import json
import os
import pathlib
import sys
import time

target = pathlib.Path(sys.argv[1])
restore_rc_raw = os.environ.get("PLAYER_RESTORE_START_RC", "not_attempted")
gc_rc_raw = os.environ.get("PRODUCT_RESET_GC_ENQUEUE_RC", "not_attempted")
payload = {
    "schema_version": "dadooh-open-settings-cleanup.v1",
    "cleaned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "reason": sys.argv[2],
    "skipped_active_session": sys.argv[3] == "true",
    "leftover_visual_processes_killed_count": int(sys.argv[4]) if sys.argv[4].isdigit() else 0,
    "session_lock_present_after": pathlib.Path(sys.argv[5]).exists(),
    "request_present_after": (pathlib.Path(sys.argv[6]) / "request.json").exists(),
    "product_reset_pending": os.environ.get("PRODUCT_RESET_PENDING") == "true",
    "terminal_action_pending": os.environ.get("TERMINAL_ACTION_PENDING") == "true",
    "update_lock_state": os.environ.get("UPDATE_LOCK_STATE", "not_checked"),
    "reset_handoff_preserved": os.environ.get("RESET_HANDOFF_PRESERVED") == "true",
    "product_reset_gc_enqueued": os.environ.get("PRODUCT_RESET_GC_ENQUEUED") == "true",
    "product_reset_gc_enqueue_rc": int(gc_rc_raw) if gc_rc_raw.isdigit() else None,
    "writer_called": False,
    "real_config_read": False,
    "real_config_written": False,
    "wifi_changed": False,
    "input_values_published": False,
    "player_restore_attempted": os.environ.get("PLAYER_RESTORE_ATTEMPTED") == "true",
    "player_restore_start_mode": os.environ.get("PLAYER_RESTORE_START_MODE", "none"),
    "player_restore_start_rc": int(restore_rc_raw) if restore_rc_raw.isdigit() else None,
    "player_restore_enqueued": os.environ.get("PLAYER_RESTORE_ATTEMPTED") == "true" and restore_rc_raw == "0",
    "player_service_active_after": os.environ.get("PLAYER_SERVICE_ACTIVE_AFTER") or "unknown",
    "player_service_result_after": os.environ.get("PLAYER_SERVICE_RESULT_AFTER") or "unknown",
    "player_service_exec_main_status_after": os.environ.get("PLAYER_SERVICE_EXEC_MAIN_STATUS_AFTER") or "unknown",
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
PY
}

if [ "$SELF_TEST" = "true" ]; then
  bash -n "$0"
  python3 - "$0" <<'PY'
import pathlib
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
main = text[text.index('trap release_product_reset_update_lock EXIT'):]
preserve = main.index('if product_reset_pending; then')
assert 'receipt.json' in text
assert preserve < main.index('rm -f "$REQUEST_DIR/request.json"')
assert preserve < main.index('restore_product_state || true')
assert main.index('restore_product_state || true') < main.index('enqueue_product_reset_gc || true')
assert main.index('enqueue_product_reset_gc || true') < main.rindex('write_status false "$visual_killed_count"')
assert 'fcntl.flock' in text
PY
  self_test_root="$(mktemp -d -t dadooh-c26-cleanup-XXXXXX)"
  trap 'rm -rf "$self_test_root"' EXIT
  PRODUCT_RESET_STATE_DIR="$self_test_root/state"
  UPDATE_LOCK_FILE="$self_test_root/updatectl.lock"
  UPDATE_LOCK_TIMEOUT_SEC="1"
  mkdir -p "$PRODUCT_RESET_STATE_DIR"
  printf '{"local_complete":true,"result":"revoked"}\n' > "$PRODUCT_RESET_STATE_DIR/receipt.json"
  product_reset_pending
  acquire_product_reset_update_lock
  release_product_reset_update_lock
  python3 - "$UPDATE_LOCK_FILE" "$self_test_root/update-lock-ready" <<'PY' &
import fcntl
import pathlib
import sys
import time

with pathlib.Path(sys.argv[1]).open("a+", encoding="utf-8") as handle:
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    pathlib.Path(sys.argv[2]).write_text("ready\n", encoding="utf-8")
    time.sleep(2)
PY
  update_lock_holder_pid="$!"
  for self_test_attempt in $(seq 1 20); do
    [ -f "$self_test_root/update-lock-ready" ] && break
    sleep 0.1
  done
  if acquire_product_reset_update_lock; then
    echo "self-test: bounded update lock unexpectedly acquired" >&2
    release_product_reset_update_lock
    exit 1
  fi
  [ "$UPDATE_LOCK_STATE" = "busy" ]
  wait "$update_lock_holder_pid"
  REQUEST_DIR="$self_test_root/request"
  TERMINAL_ACTION_MARKER="$REQUEST_DIR/terminal-action.json"
  mkdir -m 700 "$REQUEST_DIR"
  python3 - "$TERMINAL_ACTION_MARKER" <<'PY'
import datetime as dt
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
payload = {
    "schema_version": "dadooh.c26.terminal-action.v1",
    "phase": "prepared",
    "action": "restart",
    "request_id": "11111111-2222-4333-8444-555555555555",
    "settings_session_id": "1" * 32,
    "prepared_at_utc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    "accepted_at_utc": None,
}
path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
path.chmod(0o600)
PY
  if terminal_action_pending; then
    echo "self-test: prepared terminal action incorrectly treated as accepted" >&2
    exit 1
  fi
  python3 - "$TERMINAL_ACTION_MARKER" <<'PY'
import datetime as dt
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
payload["phase"] = "accepted"
payload["accepted_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
path.chmod(0o600)
PY
  terminal_action_pending
  EXPIRE_TERMINAL_ACTION="true"
  if terminal_action_pending; then
    echo "self-test: forced terminal-action expiry incorrectly remained pending" >&2
    exit 1
  fi
  EXPIRE_TERMINAL_ACTION="false"
  python3 - "$TERMINAL_ACTION_MARKER" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
payload["accepted_at_utc"] = "2020-01-01T00:00:00Z"
path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
path.chmod(0o600)
PY
  if terminal_action_pending; then
    echo "self-test: stale terminal action incorrectly treated as pending" >&2
    exit 1
  fi
  printf 'self-test: ok\n'
  exit 0
fi

mkdir -p "$REQUEST_DIR" "$OUT_DIR"
chmod 700 "$REQUEST_DIR" "$OUT_DIR" 2>/dev/null || true
trap release_product_reset_update_lock EXIT

if product_reset_pending; then
  PRODUCT_RESET_PENDING="true"
  RESET_HANDOFF_PRESERVED="true"
  UPDATE_LOCK_STATE="not_acquired_reset_pending"
  write_status false 0
  exit 0
fi

if session_process_running; then
  write_status true 0
  exit 0
fi

if ! acquire_product_reset_update_lock; then
  write_status false 0
  exit 0
fi

if product_reset_pending; then
  PRODUCT_RESET_PENDING="true"
  RESET_HANDOFF_PRESERVED="true"
  write_status false 0
  exit 0
fi

if [ "$TERMINAL_ACTION_PENDING" = "true" ]; then
  visual_killed_count="$(kill_leftover_visuals || printf '0\n')"
  cleanup_private_session_artifacts || true
  restore_tty_text_mode || true
  write_status false "$visual_killed_count"
  exit 0
fi

rm -f "$REQUEST_DIR/request.json" "$TERMINAL_ACTION_MARKER" 2>/dev/null || true
rm -rf "$LOCK_DIR" 2>/dev/null || true
visual_killed_count="$(kill_leftover_visuals || printf '0\n')"
cleanup_private_session_artifacts || true
restore_tty_text_mode || true
restore_product_state || true
enqueue_product_reset_gc || true
write_status false "$visual_killed_count"
if terminal_action_reconcile_complete; then
  stop_terminal_action_reconcile
fi
