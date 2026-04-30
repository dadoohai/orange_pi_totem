#!/usr/bin/env bash
set -u

umask 077

APP_USER="totem"
APP_GROUP="totem"
RUNTIME_DIR="/tmp/kiosky"
MEDIA_ROOT="/data/media/kiosky-player"
IPC_SOCKET="$RUNTIME_DIR/playlist-watchdog-mpv.sock"
MPV_LOG="$RUNTIME_DIR/playlist-watchdog-mpv.log"
BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="${TOTEM_DIAG_TIMESTAMP:-$(date +%Y%m%d-%H%M%S%z)}"
RUN_NAME="media-playlist-watchdog-$TIMESTAMP"
OUT_DIR="$BASE_DIR/$RUN_NAME"
ARCHIVE="$BASE_DIR/$RUN_NAME.tar.gz"
SUMMARY="$OUT_DIR/summary.tsv"
PRIVATE_SPEC="$RUNTIME_DIR/playlist-watchdog-spec-$TIMESTAMP.tsv"
PUBLIC_SPEC="$OUT_DIR/playlist-spec-public.tsv"
LOADFILE_RESULTS="$OUT_DIR/loadfile-results.tsv"
PING_RESULTS="$OUT_DIR/ping-results.tsv"
STATE_RESULTS="$OUT_DIR/state-results.tsv"
ORCHESTRATOR_SUMMARY="$OUT_DIR/orchestrator-summary.tsv"
PING_INTERVAL_SEC="${MEDIA_PLAYLIST_WATCHDOG_PING_INTERVAL_SEC:-10}"
IPC_TIMEOUT_SEC="${MEDIA_PLAYLIST_WATCHDOG_IPC_TIMEOUT_SEC:-3}"
MPV_WRAPPER_PID=""
MPV_STOPPED=0

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

if [ "$#" -lt 2 ] || [ $(( $# % 2 )) -ne 0 ]; then
  echo "Usage: $0 <duration_ms> /data/media/kiosky-player/media [<duration_ms> /data/media/kiosky-player/media ...]" >&2
  exit 2
fi

case "$PING_INTERVAL_SEC" in
  ''|*[!0-9]*)
    echo "ERROR: MEDIA_PLAYLIST_WATCHDOG_PING_INTERVAL_SEC must be a positive integer." >&2
    exit 2
    ;;
  0)
    echo "ERROR: MEDIA_PLAYLIST_WATCHDOG_PING_INTERVAL_SEC must be greater than zero." >&2
    exit 2
    ;;
esac

case "$IPC_TIMEOUT_SEC" in
  ''|*[!0-9.]*)
    echo "ERROR: MEDIA_PLAYLIST_WATCHDOG_IPC_TIMEOUT_SEC must be a positive number." >&2
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
  local dest="$OUT_DIR/mpv-playlist-watchdog.log"
  local size=0

  if [ -f "$MPV_LOG" ]; then
    cp "$MPV_LOG" "$dest"
    chmod 0600 "$dest"
    size=$(wc -c <"$MPV_LOG" 2>/dev/null || printf '0')
    append_summary "mpv-log-copy" "0" "mpv-playlist-watchdog.log copied from runtime log; bytes=$size"
  else
    append_summary "mpv-log-copy" "missing" "runtime MPV log not present"
  fi
}

stop_mpv() {
  if [ "$MPV_STOPPED" -eq 1 ]; then
    return 0
  fi
  MPV_STOPPED=1

  if [ -S "$IPC_SOCKET" ]; then
    python3 - "$IPC_SOCKET" "$IPC_TIMEOUT_SEC" >/dev/null 2>&1 <<'PY' || true
import json
import socket
import sys

sock_path, timeout_s = sys.argv[1:]
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
    sock.settimeout(float(timeout_s))
    sock.connect(sock_path)
    sock.sendall((json.dumps({"command": ["quit"], "request_id": 999999}) + "\n").encode("utf-8"))
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

trap 'stop_mpv >/dev/null 2>&1 || true' EXIT

printf 'label\texit_code\tnote\n' >"$SUMMARY"
printf 'index\talias\tduration_ms\n' >"$PUBLIC_SPEC"
printf 'index\talias\tduration_ms\tpath\n' >"$PRIVATE_SPEC"
chmod 0600 "$PRIVATE_SPEC"

item_index=0
while [ "$#" -gt 0 ]; do
  duration_ms="$1"
  media_arg="$2"
  shift 2

  case "$duration_ms" in
    ''|*[!0-9]*)
      echo "ERROR: duration_ms must be a non-negative integer." >&2
      exit 2
      ;;
  esac

  resolved_path=""
  resolve_media_path "$media_arg" resolved_path
  media_alias="$(safe_media_alias_for_path "$resolved_path")"
  item_index=$((item_index + 1))
  printf '%s\t%s\t%s\n' "$item_index" "$media_alias" "$duration_ms" >>"$PUBLIC_SPEC"
  printf '%s\t%s\t%s\t%s\n' "$item_index" "$media_alias" "$duration_ms" "$resolved_path" >>"$PRIVATE_SPEC"
done

if [ "$item_index" -eq 0 ]; then
  echo "ERROR: empty playlist." >&2
  exit 2
fi

{
  echo "media_playlist_watchdog_probe_version=1"
  echo "timestamp=$TIMESTAMP"
  echo "run_name=$RUN_NAME"
  echo "output_dir=$OUT_DIR"
  echo "archive=$ARCHIVE"
  echo "runtime_dir=$RUNTIME_DIR"
  echo "ipc_socket=$IPC_SOCKET"
  echo "mpv_log=$MPV_LOG"
  echo "media_root=$MEDIA_ROOT"
  echo "playlist_items=$item_index"
  echo "ping_interval_sec=$PING_INTERVAL_SEC"
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

python3 - "$IPC_SOCKET" "$PRIVATE_SPEC" "$IPC_TIMEOUT_SEC" "$PING_INTERVAL_SEC" \
  "$LOADFILE_RESULTS" "$PING_RESULTS" "$STATE_RESULTS" "$ORCHESTRATOR_SUMMARY" <<'PY'
import json
import socket
import sys
import threading
import time

(
    sock_path,
    spec_path,
    ipc_timeout_s,
    ping_interval_s,
    loadfile_out,
    ping_out,
    state_out,
    summary_out,
) = sys.argv[1:]
ipc_timeout = float(ipc_timeout_s)
ping_interval = float(ping_interval_s)
stop_event = threading.Event()
phase_lock = threading.Lock()
phase = {"index": "none", "alias": "none"}
request_lock = threading.Lock()
request_id = 1000

with open(spec_path, "r", encoding="utf-8") as fh:
    next(fh)
    playlist = []
    for line in fh:
        index, alias, duration_ms, path = line.rstrip("\n").split("\t", 3)
        playlist.append(
            {
                "index": int(index),
                "alias": alias,
                "duration_ms": int(duration_ms),
                "path": path,
            }
        )


def next_request_id():
    global request_id
    with request_lock:
        request_id += 1
        return request_id


def ipc_command(command, timeout=ipc_timeout):
    rid = next_request_id()
    payload = {"command": command, "request_id": rid}
    start = time.monotonic()
    rc = 1
    error = "no-response"
    data = None
    response = None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(sock_path)
            sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
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
                        candidate = json.loads(line)
                    except Exception:
                        continue
                    if candidate.get("request_id") == rid:
                        response = candidate
                        error = str(candidate.get("error", "missing-error"))
                        data = candidate.get("data")
                        rc = 0 if error == "success" else 1
                        elapsed_ms = int(round((time.monotonic() - start) * 1000))
                        return rc, elapsed_ms, error, data, response
    except socket.timeout:
        error = "timeout"
    except Exception as exc:
        error = f"exception:{type(exc).__name__}"
    elapsed_ms = int(round((time.monotonic() - start) * 1000))
    return rc, elapsed_ms, error, data, response


def write_tsv(path, line):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


write_tsv(
    loadfile_out,
    "index\talias\tduration_ms\texit_code\telapsed_ms\terror\tresponse_json",
)
write_tsv(
    ping_out,
    "seq\tphase_index\tphase_alias\tsince_start_ms\texit_code\telapsed_ms\terror\tdata_json",
)
write_tsv(
    state_out,
    "index\talias\tproperty\texit_code\telapsed_ms\terror\tdata_json",
)

started = time.monotonic()
ping_counts = {"success": 0, "timeout": 0, "other_error": 0}
load_counts = {"success": 0, "timeout": 0, "other_error": 0}


def ping_loop():
    seq = 0
    while not stop_event.is_set():
        seq += 1
        with phase_lock:
            phase_index = phase["index"]
            phase_alias = phase["alias"]
        rc, elapsed_ms, error, data, _ = ipc_command(["get_property", "idle-active"])
        since_start_ms = int(round((time.monotonic() - started) * 1000))
        if rc == 0:
            ping_counts["success"] += 1
        elif error == "timeout":
            ping_counts["timeout"] += 1
        else:
            ping_counts["other_error"] += 1
        write_tsv(
            ping_out,
            "\t".join(
                [
                    str(seq),
                    str(phase_index),
                    str(phase_alias),
                    str(since_start_ms),
                    str(rc),
                    str(elapsed_ms),
                    str(error),
                    json.dumps(data, sort_keys=True, separators=(",", ":")),
                ]
            ),
        )
        stop_event.wait(ping_interval)


ping_thread = threading.Thread(target=ping_loop, name="ping-loop", daemon=True)
ping_thread.start()

for item in playlist:
    with phase_lock:
        phase["index"] = str(item["index"])
        phase["alias"] = item["alias"]
    rc, elapsed_ms, error, _data, response = ipc_command(
        ["loadfile", item["path"], "replace"]
    )
    if rc == 0:
        load_counts["success"] += 1
    elif error == "timeout":
        load_counts["timeout"] += 1
    else:
        load_counts["other_error"] += 1
    write_tsv(
        loadfile_out,
        "\t".join(
            [
                str(item["index"]),
                item["alias"],
                str(item["duration_ms"]),
                str(rc),
                str(elapsed_ms),
                str(error),
                json.dumps(response or {}, sort_keys=True, separators=(",", ":")),
            ]
        ),
    )
    time.sleep(max(item["duration_ms"], 0) / 1000.0)
    for prop in ["idle-active", "time-pos", "duration", "eof-reached"]:
        s_rc, s_elapsed_ms, s_error, s_data, _ = ipc_command(["get_property", prop])
        write_tsv(
            state_out,
            "\t".join(
                [
                    str(item["index"]),
                    item["alias"],
                    prop,
                    str(s_rc),
                    str(s_elapsed_ms),
                    str(s_error),
                    json.dumps(s_data, sort_keys=True, separators=(",", ":")),
                ]
            ),
        )

stop_event.set()
ping_thread.join(timeout=ipc_timeout + ping_interval + 1.0)

with open(summary_out, "w", encoding="utf-8") as fh:
    fh.write("metric\tvalue\n")
    fh.write(f"playlist_items\t{len(playlist)}\n")
    fh.write(f"loadfile_success\t{load_counts['success']}\n")
    fh.write(f"loadfile_timeout\t{load_counts['timeout']}\n")
    fh.write(f"loadfile_other_error\t{load_counts['other_error']}\n")
    fh.write(f"ping_success\t{ping_counts['success']}\n")
    fh.write(f"ping_timeout\t{ping_counts['timeout']}\n")
    fh.write(f"ping_other_error\t{ping_counts['other_error']}\n")
PY
orchestrator_rc=$?
append_summary "playlist-watchdog-orchestrator" "$orchestrator_rc" "loadfile sequence with concurrent IPC pings"

stop_mpv
copy_mpv_log

run_shell "post-systemctl-failed" "systemctl --failed after playlist watchdog probe" \
  "systemctl --failed" \
  "systemctl --failed"
run_shell "post-journalctl-kernel-critical-filter" "journalctl kernel critical filter after playlist watchdog probe" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|voltage|fail|error' || true" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|voltage|fail|error' || true"

if command -v tar >/dev/null 2>&1; then
  tar -C "$BASE_DIR" -czf "$ARCHIVE" "$RUN_NAME"
  tar_rc=$?
  if [ "$tar_rc" -eq 0 ]; then
    echo "Media playlist watchdog probe directory: $OUT_DIR"
    echo "Archive: $ARCHIVE"
  else
    echo "ERROR: failed to create archive $ARCHIVE" >&2
    exit "$tar_rc"
  fi
else
  echo "ERROR: tar not found; probe directory kept at $OUT_DIR" >&2
  exit 127
fi

exit "$orchestrator_rc"
