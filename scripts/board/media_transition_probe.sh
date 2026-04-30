#!/usr/bin/env bash
set -u

umask 077

APP_USER="totem"
APP_GROUP="totem"
RUNTIME_DIR="/tmp/kiosky"
MEDIA_ROOT="/data/media/kiosky-player"
IPC_SOCKET="$RUNTIME_DIR/transition-mpv.sock"
MPV_LOG="$RUNTIME_DIR/transition-mpv.log"
BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="${TOTEM_DIAG_TIMESTAMP:-$(date +%Y%m%d-%H%M%S%z)}"
RUN_NAME="media-transition-$TIMESTAMP"
OUT_DIR="$BASE_DIR/$RUN_NAME"
ARCHIVE="$BASE_DIR/$RUN_NAME.tar.gz"
SUMMARY="$OUT_DIR/summary.tsv"
LOADFILE_RESULTS="$OUT_DIR/loadfile-results.tsv"
STATE_RESULTS="$OUT_DIR/state-results.tsv"
STEP_WAIT_SEC="${MEDIA_TRANSITION_STEP_WAIT_SEC:-12}"
IPC_TIMEOUT_SEC="${MEDIA_TRANSITION_IPC_TIMEOUT_SEC:-3}"
MPV_WRAPPER_PID=""

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 /data/media/kiosky-player/control-a /data/media/kiosky-player/suspect /data/media/kiosky-player/control-b" >&2
  exit 2
fi

case "$STEP_WAIT_SEC" in
  ''|*[!0-9]*)
    echo "ERROR: MEDIA_TRANSITION_STEP_WAIT_SEC must be a positive integer." >&2
    exit 2
    ;;
  0)
    echo "ERROR: MEDIA_TRANSITION_STEP_WAIT_SEC must be greater than zero." >&2
    exit 2
    ;;
esac

case "$IPC_TIMEOUT_SEC" in
  ''|*[!0-9.]*)
    echo "ERROR: MEDIA_TRANSITION_IPC_TIMEOUT_SEC must be a positive number." >&2
    exit 2
    ;;
esac

mkdir -p "$OUT_DIR"

stamp() {
  date '+%Y-%m-%dT%H:%M:%S%z'
}

append_summary() {
  local label="$1"
  local rc="$2"
  local note="$3"

  printf '%s\t%s\t%s\n' "$label" "$rc" "$note" >>"$SUMMARY"
}

safe_media_alias_for_path() {
  printf '%s' "$1" | sha1sum | awk '{print "<media-path:" substr($1, 1, 10) ">"}'
}

resolve_media_path() {
  local input="$1"
  local var_name="$2"
  local resolved=""

  case "$input" in
    *://*)
      echo "ERROR: URLs are not accepted; pass local media paths." >&2
      exit 2
      ;;
    /*)
      ;;
    *)
      echo "ERROR: media paths must be absolute." >&2
      exit 2
      ;;
  esac

  if [ ! -f "$input" ]; then
    echo "ERROR: media path is not a regular file." >&2
    exit 2
  fi

  resolved="$(readlink -f -- "$input" 2>/dev/null || true)"
  if [ -z "$resolved" ]; then
    echo "ERROR: failed to resolve media path." >&2
    exit 2
  fi

  case "$resolved" in
    "$MEDIA_ROOT"/*)
      printf -v "$var_name" '%s' "$resolved"
      ;;
    *)
      echo "ERROR: media paths must be under $MEDIA_ROOT." >&2
      exit 2
      ;;
  esac
}

run_shell() {
  local label="$1"
  local title="$2"
  local command="$3"
  local safe_command="$4"
  local stdout_file="$OUT_DIR/$label.stdout.txt"
  local stderr_file="$OUT_DIR/$label.stderr.txt"
  local meta_file="$OUT_DIR/$label.meta.txt"
  local rc=0

  {
    echo "### $title"
    echo "### started: $(stamp)"
    echo "### command: $safe_command"
  } >"$meta_file"

  sh -c "$command" >"$stdout_file" 2>"$stderr_file"
  rc=$?

  {
    echo "### exit_code: $rc"
    echo "### finished: $(stamp)"
    echo "stdout=$stdout_file"
    echo "stderr=$stderr_file"
  } >>"$meta_file"

  append_summary "$label" "$rc" "$title"
  return 0
}

copy_mpv_log() {
  local dest="$OUT_DIR/mpv-transition.log"
  local size=0

  if [ -f "$MPV_LOG" ]; then
    cp "$MPV_LOG" "$dest"
    chmod 0600 "$dest"
    size=$(wc -c <"$MPV_LOG" 2>/dev/null || printf '0')
    append_summary "mpv-log-copy" "0" "mpv-transition.log copied from runtime log; bytes=$size"
  else
    append_summary "mpv-log-copy" "missing" "runtime MPV log not present"
  fi
}

ipc_loadfile() {
  local role="$1"
  local path="$2"
  local alias="$3"
  local request_id="$4"
  local rc=0

  MEDIA_TRANSITION_TARGET="$path" python3 - "$IPC_SOCKET" "$role" "$alias" "$request_id" "$IPC_TIMEOUT_SEC" "$LOADFILE_RESULTS" <<'PY'
import json
import os
import socket
import sys
import time

sock_path, role, alias, request_id, timeout_s, out_path = sys.argv[1:]
timeout = float(timeout_s)
target = os.environ["MEDIA_TRANSITION_TARGET"]
command = {"command": ["loadfile", target, "replace"], "request_id": int(request_id)}
start = time.monotonic()
rc = 1
error = "no-response"
response = None

try:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(sock_path)
        sock.sendall((json.dumps(command) + "\n").encode("utf-8"))
        buffer = ""
        deadline = start + timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(deadline - time.monotonic(), 0.05))
            chunk = sock.recv(4096)
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                if payload.get("request_id") == int(request_id):
                    response = payload
                    error = str(payload.get("error", "missing-error"))
                    rc = 0 if error == "success" else 1
                    raise SystemExit
except SystemExit:
    pass
except socket.timeout:
    error = "timeout"
except Exception as exc:
    error = f"exception:{type(exc).__name__}"
finally:
    elapsed_ms = int(round((time.monotonic() - start) * 1000))
    response_safe = json.dumps(response or {}, sort_keys=True, separators=(",", ":"))
    with open(out_path, "a", encoding="utf-8") as fh:
        fh.write(f"{role}\t{alias}\t{rc}\t{elapsed_ms}\t{error}\t{response_safe}\n")
    sys.exit(rc)
PY
  rc=$?
  append_summary "loadfile-$role" "$rc" "IPC loadfile role=$role alias=$alias"
  return 0
}

ipc_probe_state() {
  local role="$1"
  local request_start="$2"

  python3 - "$IPC_SOCKET" "$role" "$request_start" "$IPC_TIMEOUT_SEC" "$STATE_RESULTS" <<'PY'
import json
import socket
import sys
import time

sock_path, role, request_start, timeout_s, out_path = sys.argv[1:]
timeout = float(timeout_s)
properties = ["idle-active", "time-pos", "duration", "eof-reached"]
request_id = int(request_start)

def command(prop, rid):
    return {"command": ["get_property", prop], "request_id": rid}

with open(out_path, "a", encoding="utf-8") as fh:
    for prop in properties:
        start = time.monotonic()
        rc = 1
        error = "no-response"
        data = None
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect(sock_path)
                sock.sendall((json.dumps(command(prop, request_id)) + "\n").encode("utf-8"))
                buffer = ""
                deadline = start + timeout
                while time.monotonic() < deadline:
                    sock.settimeout(max(deadline - time.monotonic(), 0.05))
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if not line.strip():
                            continue
                        try:
                            payload = json.loads(line)
                        except Exception:
                            continue
                        if payload.get("request_id") == request_id:
                            error = str(payload.get("error", "missing-error"))
                            data = payload.get("data")
                            rc = 0 if error == "success" else 1
                            raise StopIteration
        except StopIteration:
            pass
        except socket.timeout:
            error = "timeout"
        except Exception as exc:
            error = f"exception:{type(exc).__name__}"
        elapsed_ms = int(round((time.monotonic() - start) * 1000))
        fh.write(
            f"{role}\t{prop}\t{rc}\t{elapsed_ms}\t{error}\t"
            f"{json.dumps(data, sort_keys=True, separators=(',', ':'))}\n"
        )
        request_id += 1
PY
  append_summary "state-$role" "0" "safe IPC state probe after role=$role"
  return 0
}

stop_mpv() {
  if [ -S "$IPC_SOCKET" ]; then
    python3 - "$IPC_SOCKET" "$IPC_TIMEOUT_SEC" >/dev/null 2>&1 <<'PY' || true
import json
import socket
import sys

sock_path, timeout_s = sys.argv[1:]
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
    sock.settimeout(float(timeout_s))
    sock.connect(sock_path)
    sock.sendall((json.dumps({"command": ["quit"], "request_id": 9999}) + "\n").encode("utf-8"))
PY
  fi

  if [ -n "$MPV_WRAPPER_PID" ]; then
    for _ in $(seq 1 50); do
      if ! kill -0 "$MPV_WRAPPER_PID" >/dev/null 2>&1; then
        break
      fi
      sleep 0.1
    done
    if kill -0 "$MPV_WRAPPER_PID" >/dev/null 2>&1; then
      kill "$MPV_WRAPPER_PID" >/dev/null 2>&1 || true
    fi
    wait "$MPV_WRAPPER_PID" >/dev/null 2>&1 || true
  fi
}

resolve_media_path "$1" CONTROL_INITIAL_PATH
resolve_media_path "$2" SUSPECT_PATH
resolve_media_path "$3" CONTROL_FINAL_PATH

CONTROL_INITIAL_ALIAS="$(safe_media_alias_for_path "$CONTROL_INITIAL_PATH")"
SUSPECT_ALIAS="$(safe_media_alias_for_path "$SUSPECT_PATH")"
CONTROL_FINAL_ALIAS="$(safe_media_alias_for_path "$CONTROL_FINAL_PATH")"

printf 'label\texit_code\tnote\n' >"$SUMMARY"
printf 'role\talias\texit_code\telapsed_ms\terror\tresponse_json\n' >"$LOADFILE_RESULTS"
printf 'role\tproperty\texit_code\telapsed_ms\terror\tdata_json\n' >"$STATE_RESULTS"

{
  echo "media_transition_probe_version=1"
  echo "timestamp=$TIMESTAMP"
  echo "run_name=$RUN_NAME"
  echo "output_dir=$OUT_DIR"
  echo "archive=$ARCHIVE"
  echo "runtime_dir=$RUNTIME_DIR"
  echo "ipc_socket=$IPC_SOCKET"
  echo "mpv_log=$MPV_LOG"
  echo "media_root=$MEDIA_ROOT"
  echo "control_initial_alias=$CONTROL_INITIAL_ALIAS"
  echo "suspect_alias=$SUSPECT_ALIAS"
  echo "control_final_alias=$CONTROL_FINAL_ALIAS"
  echo "step_wait_sec=$STEP_WAIT_SEC"
  echo "ipc_timeout_sec=$IPC_TIMEOUT_SEC"
  echo "hostname=$(hostname 2>/dev/null || true)"
  echo "created_at=$(stamp)"
} >"$OUT_DIR/manifest.txt"

if ! id "$APP_USER" >/dev/null 2>&1; then
  echo "ERROR: user not found: $APP_USER" >&2
  append_summary "prereq-totem-user" "1" "missing user: $APP_USER"
  exit 1
fi

if ! getent group "$APP_GROUP" >/dev/null 2>&1; then
  echo "ERROR: group not found: $APP_GROUP" >&2
  append_summary "prereq-totem-group" "1" "missing group: $APP_GROUP"
  exit 1
fi

install -d -m 0750 -o "$APP_USER" -g "$APP_GROUP" "$RUNTIME_DIR"

run_shell "pre-date" "date" "date" "date"
run_shell "pre-uname-a" "uname -a" "uname -a" "uname -a"
run_shell "pre-systemctl-failed" "systemctl --failed" "systemctl --failed" "systemctl --failed"
run_shell "pre-id-totem" "id totem" "id totem" "id totem"
run_shell "pre-command-mpv" "command -v mpv" "command -v mpv" "command -v mpv"

rm -f "$IPC_SOCKET" "$MPV_LOG"

runuser -u "$APP_USER" -- env XDG_RUNTIME_DIR="$RUNTIME_DIR" mpv \
  --idle=yes \
  --input-ipc-server="$IPC_SOCKET" \
  --vo=gpu \
  --gpu-context=drm \
  --ao=null \
  --fs \
  --no-config \
  --force-window=yes \
  --no-terminal \
  --no-osc \
  --osd-level=0 \
  --log-file="$MPV_LOG" \
  --msg-level=all=v \
  >"$OUT_DIR/mpv-process.stdout.txt" \
  2>"$OUT_DIR/mpv-process.stderr.txt" &
MPV_WRAPPER_PID="$!"

append_summary "mpv-start" "0" "MPV started once in idle IPC mode"

socket_ready=0
for _ in $(seq 1 100); do
  if [ -S "$IPC_SOCKET" ]; then
    socket_ready=1
    break
  fi
  sleep 0.1
done

if [ "$socket_ready" -ne 1 ]; then
  append_summary "ipc-socket-ready" "1" "MPV IPC socket did not appear"
  stop_mpv
  copy_mpv_log
  tar -C "$BASE_DIR" -czf "$ARCHIVE" "$RUN_NAME"
  exit 1
fi

append_summary "ipc-socket-ready" "0" "MPV IPC socket ready"

ipc_loadfile "control_initial" "$CONTROL_INITIAL_PATH" "$CONTROL_INITIAL_ALIAS" "1001"
sleep "$STEP_WAIT_SEC"
ipc_probe_state "control_initial" "2001"

ipc_loadfile "suspect" "$SUSPECT_PATH" "$SUSPECT_ALIAS" "1002"
sleep "$STEP_WAIT_SEC"
ipc_probe_state "suspect" "2011"

ipc_loadfile "control_final" "$CONTROL_FINAL_PATH" "$CONTROL_FINAL_ALIAS" "1003"
sleep "$STEP_WAIT_SEC"
ipc_probe_state "control_final" "2021"

stop_mpv
copy_mpv_log

run_shell "post-systemctl-failed" "systemctl --failed after media transition probe" \
  "systemctl --failed" \
  "systemctl --failed"
run_shell "post-journalctl-kernel-critical-filter" "journalctl kernel critical filter after media transition probe" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|voltage|fail|error' || true" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|voltage|fail|error' || true"

if command -v tar >/dev/null 2>&1; then
  tar -C "$BASE_DIR" -czf "$ARCHIVE" "$RUN_NAME"
  tar_rc=$?
  if [ "$tar_rc" -eq 0 ]; then
    echo "Media transition probe directory: $OUT_DIR"
    echo "Archive: $ARCHIVE"
  else
    echo "ERROR: failed to create archive $ARCHIVE" >&2
    exit "$tar_rc"
  fi
else
  echo "ERROR: tar not found; probe directory kept at $OUT_DIR" >&2
  exit 127
fi
