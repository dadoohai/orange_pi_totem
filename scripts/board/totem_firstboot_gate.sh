#!/usr/bin/env bash
set -euo pipefail

MODE="wait"
MARKER="/root/.not_logged_in_yet"
OUT_DIR="/run/dadooh-firstboot-gate"
REMOTE_TTY="2"
POLL_SEC="5"
TOTEM_C17_4_FIRSTBOOT_TRACE_DIR="${TOTEM_C17_4_FIRSTBOOT_TRACE_DIR:-/data/state/totem-debug/c17-4-firstboot}"
CANONICAL_PRODUCT_RESET_STATE_DIR="/data/state/totem-appliance/product-reset"
PRODUCT_RESET_STATE_DIR="${TOTEM_PRODUCT_RESET_STATE_DIR:-$CANONICAL_PRODUCT_RESET_STATE_DIR}"
PRODUCT_RESET_REQUEST_FILE="${TOTEM_PRODUCT_RESET_REQUEST_FILE:-/run/dadooh-settings/request.json}"
PRODUCT_RESET_LOCK_DIR="${TOTEM_PRODUCT_RESET_LOCK_DIR:-/run/totem/settings-session.lock}"
UPDATE_LOCK_FILE="${TOTEM_UPDATE_LOCK_FILE:-/run/totem-updatectl.lock}"
UPDATE_LOCK_TIMEOUT_SEC="${TOTEM_PRODUCT_RESET_UPDATE_LOCK_TIMEOUT_SEC:-5}"
PLAYER_STOP_TIMEOUT_SEC="${TOTEM_PRODUCT_RESET_PLAYER_STOP_TIMEOUT_SEC:-30}"
UPDATE_LOCK_HOLDER_ACTIVE_PID=""
FIRSTBOOT_READY_MARKER="/run/totem/c26-firstboot-ready.json"
BOOT_ID_FILE="/proc/sys/kernel/random/boot_id"

usage() {
  cat <<'USAGE'
Usage:
  totem_firstboot_gate.sh [--wait|--status|--self-test]

Blocks Dadooh product services while the Armbian technical first-login marker
exists. Image-lab board validation must provide private lab firstboot
autoconfig outside Git; otherwise this gate only shows a safe bootstrap-pending
notice and the card is not considered product-boot-validatable. It does not
configure users, passwords, networking, config.json or Wi-Fi.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --wait) MODE="wait" ;;
    --status) MODE="status" ;;
    --self-test) MODE="self-test" ;;
    --marker)
      shift
      MARKER="${1:-}"
      ;;
    --out-dir)
      shift
      OUT_DIR="${1:-}"
      ;;
    --tty)
      shift
      REMOTE_TTY="${1:-}"
      ;;
    --poll-sec)
      shift
      POLL_SEC="${1:-}"
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

case "$OUT_DIR" in
  /run/*|/tmp/*) ;;
  *) echo "error: --out-dir must be under /run or /tmp" >&2; exit 2 ;;
esac
case "$REMOTE_TTY" in
  ''|*[!0-9]*|0) echo "error: --tty must be a positive integer" >&2; exit 2 ;;
esac
case "$POLL_SEC" in
  ''|*[!0-9]*|0) echo "error: --poll-sec must be a positive integer" >&2; exit 2 ;;
esac
case "$UPDATE_LOCK_TIMEOUT_SEC" in
  ''|*[!0-9]*|0) echo "error: product reset update lock timeout must be a positive integer" >&2; exit 2 ;;
esac
if [ "$UPDATE_LOCK_TIMEOUT_SEC" -gt 30 ]; then
  echo "error: product reset update lock timeout must not exceed 30 seconds" >&2
  exit 2
fi
case "$PLAYER_STOP_TIMEOUT_SEC" in
  ''|*[!0-9]*|0) echo "error: product reset player stop timeout must be a positive integer" >&2; exit 2 ;;
esac
if [ "$PLAYER_STOP_TIMEOUT_SEC" -gt 30 ]; then
  echo "error: product reset player stop timeout must not exceed 30 seconds" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPLASH="$SCRIPT_DIR/totem_visual_splash.py"
CONFIG_WRITER="$SCRIPT_DIR/totem_config_writer_real.py"
TTY_DEVICE="/dev/tty$REMOTE_TTY"
STATUS_OUT="$OUT_DIR/status.json"

write_firstboot_ready_marker() {
  local target="${1:-$FIRSTBOOT_READY_MARKER}"
  local boot_id_file="${2:-$BOOT_ID_FILE}"
  local expected_uid="${3:-0}"
  local expected_gid="${4:-0}"
  python3 - "$target" "$boot_id_file" "$expected_uid" "$expected_gid" <<'PY'
import datetime as dt
import json
import os
import pathlib
import stat
import sys
import tempfile
import uuid

target = pathlib.Path(sys.argv[1])
boot_id_file = pathlib.Path(sys.argv[2])
expected_uid = int(sys.argv[3])
expected_gid = int(sys.argv[4])
parent = target.parent

if not target.is_absolute() or target.name != "c26-firstboot-ready.json":
    raise SystemExit("firstboot_ready_target_invalid")

parent_parent = parent.parent
parent_parent_info = os.lstat(parent_parent)
if (
    stat.S_ISLNK(parent_parent_info.st_mode)
    or not stat.S_ISDIR(parent_parent_info.st_mode)
    or parent_parent_info.st_uid != expected_uid
    or parent_parent_info.st_gid != expected_gid
    or stat.S_IMODE(parent_parent_info.st_mode) & 0o022
):
    raise SystemExit("firstboot_ready_parent_untrusted")

try:
    parent_info = os.lstat(parent)
except FileNotFoundError:
    parent.mkdir(mode=0o755, parents=False)
    parent_info = os.lstat(parent)
if (
    stat.S_ISLNK(parent_info.st_mode)
    or not stat.S_ISDIR(parent_info.st_mode)
    or parent_info.st_uid != expected_uid
    or parent_info.st_gid != expected_gid
    or stat.S_IMODE(parent_info.st_mode) & 0o022
):
    raise SystemExit("firstboot_ready_parent_untrusted")

boot_info = os.lstat(boot_id_file)
if stat.S_ISLNK(boot_info.st_mode) or not stat.S_ISREG(boot_info.st_mode):
    raise SystemExit("firstboot_boot_id_untrusted")
boot_id = boot_id_file.read_text(encoding="ascii").strip()
try:
    parsed_boot_id = uuid.UUID(boot_id)
except ValueError as exc:
    raise SystemExit("firstboot_boot_id_invalid") from exc
if str(parsed_boot_id) != boot_id:
    raise SystemExit("firstboot_boot_id_invalid")

try:
    target_info = os.lstat(target)
except FileNotFoundError:
    target_info = None
if target_info is not None and (
    stat.S_ISLNK(target_info.st_mode)
    or not stat.S_ISREG(target_info.st_mode)
    or target_info.st_uid != expected_uid
    or target_info.st_gid != expected_gid
    or target_info.st_nlink != 1
):
    raise SystemExit("firstboot_ready_target_untrusted")

payload = {
    "schema_version": "dadooh.c26.firstboot-ready.v1",
    "boot_id": boot_id,
    "completed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
}
fd, tmp_name = tempfile.mkstemp(prefix=".c26-firstboot-ready.", suffix=".tmp", dir=str(parent))
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        fd = -1
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_name, target)
    tmp_name = ""
    os.chmod(target, 0o600)
    directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
finally:
    if fd >= 0:
        os.close(fd)
    if tmp_name:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
PY
}

product_reset_requires_onboarding() {
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

product_reset_mutation_pending() {
  if [ -L "$PRODUCT_RESET_STATE_DIR" ]; then
    return 0
  fi
  if [ -e "$PRODUCT_RESET_STATE_DIR" ] && [ ! -d "$PRODUCT_RESET_STATE_DIR" ]; then
    return 0
  fi
  [ -e "$PRODUCT_RESET_STATE_DIR/intent.json" ] \
    || [ -L "$PRODUCT_RESET_STATE_DIR/intent.json" ] \
    || [ -e "$PRODUCT_RESET_STATE_DIR/pending-credential.json" ] \
    || [ -L "$PRODUCT_RESET_STATE_DIR/pending-credential.json" ]
}

ensure_product_reset_guard_lock() {
  python3 - "$PRODUCT_RESET_LOCK_DIR" <<'PY'
import os
import pathlib
import stat
import sys

lock_dir = pathlib.Path(sys.argv[1])
if not lock_dir.is_absolute() or lock_dir.name != "settings-session.lock":
    raise SystemExit("product_reset_lock_path_invalid")
if lock_dir.is_symlink() or lock_dir.parent.is_symlink():
    raise SystemExit("product_reset_lock_symlink")
lock_dir.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
lock_parent = lock_dir.parent.stat()
if not stat.S_ISDIR(lock_parent.st_mode) or lock_parent.st_uid != os.geteuid() or stat.S_IMODE(lock_parent.st_mode) & 0o022:
    raise SystemExit("product_reset_lock_parent_untrusted")
os.chmod(lock_dir.parent, 0o755)
try:
    lock_dir.mkdir(mode=0o755)
except FileExistsError:
    pass
lock_info = lock_dir.stat(follow_symlinks=False)
if not stat.S_ISDIR(lock_info.st_mode) or lock_info.st_uid != os.geteuid() or stat.S_IMODE(lock_info.st_mode) & 0o022:
    raise SystemExit("product_reset_lock_untrusted")
os.chmod(lock_dir, 0o755)
PY
}

write_product_reset_resume_request() {
  python3 - "$PRODUCT_RESET_REQUEST_FILE" <<'PY'
import json
import os
import pathlib
import stat
import sys
import tempfile
import time

target = pathlib.Path(sys.argv[1])
if not target.is_absolute() or target.name != "request.json":
    raise SystemExit("product_reset_guard_path_invalid")
if target.is_symlink() or target.parent.is_symlink():
    raise SystemExit("product_reset_guard_symlink")
target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
parent = target.parent.stat()
if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) & 0o077:
    raise SystemExit("product_reset_guard_parent_untrusted")
target_info = None
try:
    target_info = target.stat(follow_symlinks=False)
except FileNotFoundError:
    pass
if target_info is not None and (not stat.S_ISREG(target_info.st_mode) or target_info.st_uid != os.geteuid()):
    raise SystemExit("product_reset_guard_target_untrusted")
os.chmod(target.parent, 0o700)
payload = {
    "schema_version": 1,
    "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "trigger_type": "product_reset_resume",
    "action": "open_settings",
}
fd, raw_tmp = tempfile.mkstemp(prefix=".request.json.", suffix=".tmp", dir=str(target.parent), text=True)
tmp = pathlib.Path(raw_tmp)
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        fd = -1
        handle.write(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    os.chmod(target, 0o600)
    dir_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
finally:
    if fd >= 0:
        os.close(fd)
    try:
        tmp.unlink()
    except FileNotFoundError:
        pass
PY
}

clear_product_reset_runtime_guard() {
  python3 - "$PRODUCT_RESET_REQUEST_FILE" "$PRODUCT_RESET_LOCK_DIR" <<'PY'
import json
import os
import pathlib
import stat
import sys

request = pathlib.Path(sys.argv[1])
lock = pathlib.Path(sys.argv[2])
try:
    request_info = request.stat(follow_symlinks=False)
except FileNotFoundError:
    request_info = None
if request_info is not None:
    if (
        request.is_symlink()
        or not stat.S_ISREG(request_info.st_mode)
        or request_info.st_uid != os.geteuid()
        or request_info.st_nlink != 1
        or stat.S_IMODE(request_info.st_mode) != 0o600
        or request_info.st_size <= 0
        or request_info.st_size > 4096
    ):
        raise SystemExit("product_reset_request_untrusted")
    payload = json.loads(request.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("trigger_type") != "product_reset_resume"
        or payload.get("action") != "open_settings"
    ):
        raise SystemExit("product_reset_request_untrusted")
    request.unlink()

try:
    lock_info = lock.stat(follow_symlinks=False)
except FileNotFoundError:
    lock_info = None
if lock_info is not None:
    if (
        lock.is_symlink()
        or not stat.S_ISDIR(lock_info.st_mode)
        or lock_info.st_uid != os.geteuid()
        or stat.S_IMODE(lock_info.st_mode) & 0o022
    ):
        raise SystemExit("product_reset_lock_untrusted")
    lock.rmdir()
PY
}

complete_product_reset_onboarding_if_configured() {
  [ -e "$PRODUCT_RESET_STATE_DIR/receipt.json" ] || [ -L "$PRODUCT_RESET_STATE_DIR/receipt.json" ] || return 1
  product_reset_mutation_pending && return 1
  if [ ! -f "$CONFIG_WRITER" ] || [ -L "$CONFIG_WRITER" ]; then
    return 1
  fi
  set +e
  python3 "$CONFIG_WRITER" \
    --product-reset-complete-onboarding \
    --product-reset-data-root /data \
    --enable-real-write \
    --confirm-service-stopped \
    --confirm-product-reset-new-config-applied >/dev/null 2>&1
  local rc="$?"
  set -e
  if [ "$rc" -ne 0 ] || product_reset_requires_onboarding; then
    return 1
  fi
  clear_product_reset_runtime_guard
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
  coproc PRODUCT_RESET_UPDATE_LOCK_HOLDER {
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
  UPDATE_LOCK_HOLDER_ACTIVE_PID="$PRODUCT_RESET_UPDATE_LOCK_HOLDER_PID"
  local status_fd="${PRODUCT_RESET_UPDATE_LOCK_HOLDER[0]}"
  local input_fd="${PRODUCT_RESET_UPDATE_LOCK_HOLDER[1]}"
  exec {input_fd}>&-
  IFS= read -r lock_status <&"$status_fd" || true
  exec {status_fd}<&-
  if [ "$lock_status" = "LOCKED" ]; then
    return 0
  fi
  release_product_reset_update_lock
  return 1
}

session_process_running() {
  python3 - <<'PY'
import os
import pathlib
import sys

self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    if "totem_open_settings_session.sh" in " ".join(parts):
        raise SystemExit(0)
raise SystemExit(1)
PY
}

player_process_counts() {
  python3 - <<'PY'
import os
import pathlib

counts = {"kiosk": 0, "mpv": 0, "launcher": 0}
self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    names = [pathlib.Path(part).name.lower() for part in parts]
    if "kiosk.py" in names:
        counts["kiosk"] += 1
    if "mpv" in names:
        counts["mpv"] += 1
    if any(name in {"kiosky_service_launcher.sh", "totem-kiosky-launcher.sh"} for name in names):
        counts["launcher"] += 1
print(f"{counts['kiosk']} {counts['mpv']} {counts['launcher']}")
PY
}

player_is_stopped() {
  local counts=""
  if systemctl is-active --quiet kiosky-player.service; then
    return 1
  fi
  counts="$(player_process_counts)"
  set -- $counts
  [ "${1:-1}" -eq 0 ] && [ "${2:-1}" -eq 0 ] && [ "${3:-1}" -eq 0 ]
}

stop_player_for_product_reset() {
  local attempt=""
  systemctl stop kiosky-player.service >/dev/null 2>&1 || true
  for attempt in $(seq 1 "$PLAYER_STOP_TIMEOUT_SEC"); do
    if player_is_stopped; then
      c17_4_trace "product_reset_player_stopped"
      return 0
    fi
    sleep 1
  done
  systemctl kill --signal=SIGKILL kiosky-player.service >/dev/null 2>&1 || true
  pkill -KILL -f '/opt/totem/kiosky-player/kiosk\.py' >/dev/null 2>&1 || true
  pkill -KILL -f '/data/apps/kiosky-player/.*/kiosk\.py' >/dev/null 2>&1 || true
  pkill -KILL -x mpv >/dev/null 2>&1 || true
  pkill -KILL -f '/opt/totem/bin/kiosky_service_launcher\.sh' >/dev/null 2>&1 || true
  pkill -KILL -f '/opt/totem/bin/totem-kiosky-launcher\.sh' >/dev/null 2>&1 || true
  for attempt in $(seq 1 5); do
    if player_is_stopped; then
      c17_4_trace "product_reset_player_stopped_after_kill"
      return 0
    fi
    sleep 1
  done
  c17_4_trace "product_reset_player_stop_unconfirmed"
  return 1
}

resume_product_reset_local() {
  product_reset_mutation_pending || return 0
  if [ ! -f "$CONFIG_WRITER" ] || [ -L "$CONFIG_WRITER" ]; then
    c17_4_trace "product_reset_writer_unavailable"
    return 1
  fi
  set +e
  python3 "$CONFIG_WRITER" \
    --product-reset-resume \
    --product-reset-data-root /data \
    --enable-real-write \
    --confirm-service-stopped >/dev/null 2>&1
  local rc="$?"
  set -e
  case "$rc" in
    0|10)
      c17_4_trace "product_reset_local_resume_rc_$rc"
      ;;
    *)
      c17_4_trace "product_reset_local_resume_failed_rc_$rc"
      return 1
      ;;
  esac
  return 0
}

reconcile_product_reset() {
  local rc=0
  product_reset_requires_onboarding || return 0
  if session_process_running; then
    c17_4_trace "product_reset_session_already_active"
    return 1
  fi
  if ! ensure_product_reset_guard_lock; then
    c17_4_trace "product_reset_guard_lock_failed"
    return 1
  fi
  if ! write_product_reset_resume_request; then
    c17_4_trace "product_reset_resume_request_failed"
    return 1
  fi
  if ! acquire_product_reset_update_lock; then
    c17_4_trace "product_reset_update_lock_busy"
    return 1
  fi
  if session_process_running; then
    c17_4_trace "product_reset_session_raced_update_lock"
    rc=1
  elif ! stop_player_for_product_reset; then
    c17_4_trace "product_reset_player_stop_failed"
    rc=1
  elif session_process_running; then
    c17_4_trace "product_reset_session_raced_player_stop"
    rc=1
  elif product_reset_mutation_pending && ! resume_product_reset_local; then
    c17_4_trace "product_reset_local_resume_deferred"
    rc=1
  elif complete_product_reset_onboarding_if_configured; then
    c17_4_trace "product_reset_onboarding_auto_completed"
  else
    c17_4_trace "product_reset_guard_ready_for_onboarding"
  fi
  release_product_reset_update_lock
  return "$rc"
}

c17_4_trace() {
  local event="$1"
  local root="$TOTEM_C17_4_FIRSTBOOT_TRACE_DIR"
  local marker_state="absent"
  local uptime_value="unknown"

  [ -e "$MARKER" ] && marker_state="present"
  uptime_value="$(awk '{print int($1)}' /proc/uptime 2>/dev/null || printf unknown)"
  if ! mkdir -p "$root" 2>/dev/null; then
    root="/run/totem/c17-4-firstboot"
    mkdir -p "$root" 2>/dev/null || return 0
  fi
  chown totem:totem "$root" 2>/dev/null || true
  chmod 700 "$root" 2>/dev/null || true
  printf '%s uptime=%s pid=%d component=firstboot_gate event=%s armbian_marker=%s tty=%s\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$uptime_value" "$$" "$event" "$marker_state" "$REMOTE_TTY" \
    >> "$root/events.log" 2>/dev/null || true
  case "$root" in
    /data/*) sync "$root/events.log" >/dev/null 2>&1 || true ;;
  esac
}

if [ "$MODE" = "self-test" ]; then
  bash -n "$0"
  python3 - "$SCRIPT_DIR" "$CANONICAL_PRODUCT_RESET_STATE_DIR" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
canonical = sys.argv[2]
expected = {
    "totem_firstboot_gate.sh": f'CANONICAL_PRODUCT_RESET_STATE_DIR="{canonical}"',
    "totem_config_writer_real.py": 'PRODUCT_RESET_STATE_REL = pathlib.Path("state/totem-appliance/product-reset")',
    "totem_open_settings_session.sh": f'PRODUCT_RESET_STATE_DIR="${{TOTEM_PRODUCT_RESET_STATE_DIR:-{canonical}}}"',
    "totem_open_settings_cleanup.sh": f'PRODUCT_RESET_STATE_DIR="${{TOTEM_PRODUCT_RESET_STATE_DIR:-{canonical}}}"',
    "totem_settings_trigger.py": f'"{canonical}",',
}
for name, needle in expected.items():
    assert needle in (root / name).read_text(encoding="utf-8"), f"product_reset_state_path_drift:{name}"
text = (root / "totem_firstboot_gate.sh").read_text(encoding="utf-8")
reconcile = text[text.index("reconcile_product_reset() {"):text.index("\nc17_4_trace() {")]
assert reconcile.index("ensure_product_reset_guard_lock") < reconcile.index("write_product_reset_resume_request")
assert reconcile.index("write_product_reset_resume_request") < reconcile.index("acquire_product_reset_update_lock")
assert reconcile.index("acquire_product_reset_update_lock") < reconcile.index("stop_player_for_product_reset")
assert reconcile.index("stop_player_for_product_reset") < reconcile.index("resume_product_reset_local")
assert "fcntl.flock" in text
PY
  self_test_root="$(mktemp -d -t dadooh-c26-firstboot-XXXXXX)"
  trap 'rm -rf "$self_test_root"' EXIT
  PRODUCT_RESET_STATE_DIR="$self_test_root/state"
  PRODUCT_RESET_REQUEST_FILE="$self_test_root/run/request.json"
  PRODUCT_RESET_LOCK_DIR="$self_test_root/run-totem/settings-session.lock"
  UPDATE_LOCK_FILE="$self_test_root/updatectl.lock"
  UPDATE_LOCK_TIMEOUT_SEC="1"
  mkdir -p "$PRODUCT_RESET_STATE_DIR"
  printf '{}\n' > "$PRODUCT_RESET_STATE_DIR/intent.json"
  ensure_product_reset_guard_lock
  write_product_reset_resume_request
  python3 - "$PRODUCT_RESET_REQUEST_FILE" <<'PY'
import json
import pathlib
import stat
import sys

path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
assert data["trigger_type"] == "product_reset_resume"
assert data["action"] == "open_settings"
assert stat.S_IMODE(path.stat().st_mode) == 0o600
lock = pathlib.Path(sys.argv[1]).parents[1] / "run-totem" / "settings-session.lock"
assert lock.is_dir()
assert stat.S_IMODE(lock.stat().st_mode) == 0o755
PY
  clear_product_reset_runtime_guard
  [ ! -e "$PRODUCT_RESET_REQUEST_FILE" ] && [ ! -e "$PRODUCT_RESET_LOCK_DIR" ]
  ensure_product_reset_guard_lock
  write_product_reset_resume_request
  rm -f "$PRODUCT_RESET_STATE_DIR/intent.json"
  printf '{"local_complete":true,"result":"revoked"}\n' > "$PRODUCT_RESET_STATE_DIR/receipt.json"
  product_reset_requires_onboarding
  if product_reset_mutation_pending; then
    echo "self-test: finalized receipt incorrectly marked mutable" >&2
    exit 1
  fi
  rm -f "$PRODUCT_RESET_REQUEST_FILE"
  rmdir "$PRODUCT_RESET_LOCK_DIR"
  ensure_product_reset_guard_lock
  write_product_reset_resume_request
  [ -f "$PRODUCT_RESET_REQUEST_FILE" ] && [ -d "$PRODUCT_RESET_LOCK_DIR" ]
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
  wait "$update_lock_holder_pid"
  self_test_boot_id="$self_test_root/boot-id"
  self_test_ready_parent="$self_test_root/run"
  self_test_ready_marker="$self_test_ready_parent/c26-firstboot-ready.json"
  mkdir -p "$self_test_ready_parent"
  chmod 700 "$self_test_ready_parent"
  printf '11111111-2222-4333-8444-555555555555\n' > "$self_test_boot_id"
  write_firstboot_ready_marker \
    "$self_test_ready_marker" \
    "$self_test_boot_id" \
    "$(id -u)" \
    "$(id -g)"
  python3 - "$self_test_ready_marker" <<'PY'
import json
import pathlib
import stat
import sys

target = pathlib.Path(sys.argv[1])
payload = json.loads(target.read_text(encoding="utf-8"))
assert set(payload) == {"schema_version", "boot_id", "completed_at_utc"}
assert payload["schema_version"] == "dadooh.c26.firstboot-ready.v1"
assert payload["boot_id"] == "11111111-2222-4333-8444-555555555555"
assert stat.S_IMODE(target.stat(follow_symlinks=False).st_mode) == 0o600
PY
  printf 'self-test: ok\n'
  exit 0
fi

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR" 2>/dev/null || true
rm -f "$FIRSTBOOT_READY_MARKER"
c17_4_trace "firstboot_gate_start"
trap release_product_reset_update_lock EXIT

write_status() {
  local state="$1"
  local reset_required="false"
  if product_reset_requires_onboarding; then
    reset_required="true"
  fi
  PRODUCT_RESET_ONBOARDING_REQUIRED="$reset_required" python3 - "$STATUS_OUT" "$state" "$MARKER" <<'PY'
import json
import os
import pathlib
import sys
import time

target = pathlib.Path(sys.argv[1])
marker = pathlib.Path(sys.argv[3])
payload = {
    "schema_version": "dadooh-c12-image-lab-firstboot-gate.v1",
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "state": sys.argv[2],
    "armbian_first_login_pending": marker.exists(),
    "product_reset_onboarding_required": os.environ.get("PRODUCT_RESET_ONBOARDING_REQUIRED") == "true",
    "product_services_blocked": marker.exists() or os.environ.get("PRODUCT_RESET_ONBOARDING_REQUIRED") == "true",
    "secrets_embedded": False,
    "config_real_embedded": False,
    "writer_called": False,
    "wifi_changed": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
PY
}

show_firstboot_splash() {
  c17_4_trace "config_pending_render_attempt"
  if [ -e "$TTY_DEVICE" ]; then
    command -v chvt >/dev/null 2>&1 && chvt "$REMOTE_TTY" >/dev/null 2>&1 || true
    printf '\033c\033[2J\033[3J\033[H\033[?25l' > "$TTY_DEVICE" 2>/dev/null || true
  fi
  if [ -f "$SPLASH" ] && [ -e "$TTY_DEVICE" ]; then
    env TERM=linux PYTHONPATH="$SCRIPT_DIR" python3 "$SPLASH" firstboot \
      --status-out "$OUT_DIR/splash-status.json" \
      <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || {
        if [ -e "$TTY_DEVICE" ]; then
          printf '\033c\033[2J\033[3J\033[H\033[?25l' > "$TTY_DEVICE" 2>/dev/null || true
        fi
      }
  fi
  c17_4_trace "config_pending_render_done"
}

if [ "$MODE" = "status" ]; then
  write_status status
  c17_4_trace "firstboot_gate_status"
  exit 0
fi

if product_reset_requires_onboarding; then
  until reconcile_product_reset; do
    write_status product_reset_deferred
    c17_4_trace "product_reset_reconcile_retry"
    show_firstboot_splash || true
    sleep "$POLL_SEC"
  done
fi

while [ -e "$MARKER" ]; do
  write_status waiting
  show_firstboot_splash || true
  sleep "$POLL_SEC"
done

write_status complete
c17_4_trace "firstboot_gate_complete"
write_firstboot_ready_marker
