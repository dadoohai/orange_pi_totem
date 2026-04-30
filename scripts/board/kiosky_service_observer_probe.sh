#!/usr/bin/env bash
set -u

umask 077

SERVICE_NAME="${KIOSKY_SERVICE_NAME:-kiosky-player.service}"
APP_USER="totem"
APP_DIR="/opt/totem/kiosky-player"
CONFIG_PATH="/data/config/config.json"
RUNTIME_DIR="/tmp/kiosky"
STATUS_FILE="/tmp/kiosky-status.json"
MPV_LOG_FILE="/tmp/kiosky/mpv.log"
MPV_GENERATION_LOG_DIR="/tmp/kiosky"
BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="${TOTEM_DIAG_TIMESTAMP:-$(date +%Y%m%d-%H%M%S%z)}"
RUN_NAME="kiosky-service-observer-$TIMESTAMP"
OUT_DIR="$BASE_DIR/$RUN_NAME"
ARCHIVE="$BASE_DIR/$RUN_NAME.tar.gz"
SUMMARY="$OUT_DIR/summary.tsv"
MARKER="/tmp/kiosky-service-observer-$TIMESTAMP.marker"
OBSERVE_DURATION_SEC="${KIOSKY_SERVICE_OBSERVER_DURATION_SEC:-600}"
OBSERVER_INTERVAL_SEC="${KIOSKY_SERVICE_OBSERVER_INTERVAL_SEC:-1}"
OBSERVER_IPC_TIMEOUT_SEC="${KIOSKY_SERVICE_OBSERVER_IPC_TIMEOUT_SEC:-0.8}"
OBSERVER_PID=""
RUN_SHELL_LAST_RC=0

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

case "$OBSERVE_DURATION_SEC" in
  ''|*[!0-9]*|0)
    echo "ERROR: KIOSKY_SERVICE_OBSERVER_DURATION_SEC must be a positive integer." >&2
    exit 2
    ;;
esac

case "$OBSERVER_INTERVAL_SEC" in
  ''|*[!0-9.]*)
    echo "ERROR: KIOSKY_SERVICE_OBSERVER_INTERVAL_SEC must be a positive number." >&2
    exit 2
    ;;
esac

case "$OBSERVER_IPC_TIMEOUT_SEC" in
  ''|*[!0-9.]*)
    echo "ERROR: KIOSKY_SERVICE_OBSERVER_IPC_TIMEOUT_SEC must be a positive number." >&2
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

run_shell() {
  local label="$1"
  local title="$2"
  local command="$3"
  local stdout_file="$OUT_DIR/$label.stdout.txt"
  local stderr_file="$OUT_DIR/$label.stderr.txt"
  local meta_file="$OUT_DIR/$label.meta.txt"
  local rc=0

  {
    echo "### $title"
    echo "### started: $(stamp)"
    echo "### command: $command"
  } >"$meta_file"

  sh -c "$command" >"$stdout_file" 2>"$stderr_file"
  rc=$?

  {
    echo "### exit_code: $rc"
    echo "### finished: $(stamp)"
    echo "stdout=$stdout_file"
    echo "stderr=$stderr_file"
  } >>"$meta_file"

  RUN_SHELL_LAST_RC="$rc"
  append_summary "$label" "$rc" "$title"
  return 0
}

check_expected_config() {
  local label="pre-config-expected-fields"
  local stdout_file="$OUT_DIR/$label.stdout.txt"
  local stderr_file="$OUT_DIR/$label.stderr.txt"
  local result_file="$OUT_DIR/$label.tsv"
  local rc=0

  python3 - "$CONFIG_PATH" "$result_file" >"$stdout_file" 2>"$stderr_file" <<'PY'
import json
import os
import stat
import sys

config_path, result_path = sys.argv[1:]

expected = {
    "mpv_query_uses_fresh_ipc": True,
    "mpv_vo": "gpu",
    "mpv_gpu_context": "drm",
    "mpv_ao": "null",
    "low_resource_mode": False,
    "watchdog_interval_sec": 10,
    "mpv_watchdog_ping_failures_before_restart": 2,
    "mpv_watchdog_grace_after_load_sec": 0,
    "mpv_watchdog_grace_after_restart_sec": 0,
    "mpv_ipc_timeout_sec": 2.0,
    "mpv_startup_timeout_sec": 10.0,
    "hwdec": "auto-safe",
    "mpv_log_file": "/tmp/kiosky/mpv.log",
    "mpv_msg_level": "all=v",
    "mpv_debug_events": True,
}


def matches(actual, expected_value):
    if isinstance(expected_value, bool):
        return actual is expected_value
    if isinstance(expected_value, int) and not isinstance(expected_value, bool):
        try:
            return int(actual) == expected_value
        except Exception:
            return False
    if isinstance(expected_value, float):
        try:
            return abs(float(actual) - expected_value) < 0.000001
        except Exception:
            return False
    return actual == expected_value


with open(config_path, "r", encoding="utf-8") as fh:
    cfg = json.load(fh)

rows = []
ok = True
for key, expected_value in expected.items():
    status = "OK" if matches(cfg.get(key), expected_value) else "MISMATCH"
    rows.append((key, status))
    ok = ok and status == "OK"

st = os.stat(config_path)
mode_ok = stat.S_IMODE(st.st_mode) == 0o640
rows.append(("mode_0640", "OK" if mode_ok else "MISMATCH"))
ok = ok and mode_ok

try:
    import grp
    import pwd

    owner_ok = pwd.getpwuid(st.st_uid).pw_name == "root" and grp.getgrgid(st.st_gid).gr_name == "totem"
except Exception:
    owner_ok = False
rows.append(("owner_root_totem", "OK" if owner_ok else "MISMATCH"))
ok = ok and owner_ok

with open(result_path, "w", encoding="utf-8") as out:
    out.write("field\tstatus\n")
    for field, status in rows:
        out.write(f"{field}\t{status}\n")

print("OK: expected config fields confirmed" if ok else "ERROR: expected config fields mismatch")
sys.exit(0 if ok else 1)
PY
  rc=$?
  chmod 0600 "$result_file" "$stdout_file" "$stderr_file" 2>/dev/null || true
  RUN_SHELL_LAST_RC="$rc"
  append_summary "$label" "$rc" "expected non-sensitive config fields checked without printing config content"
  return 0
}

stop_observer() {
  if [ -n "$OBSERVER_PID" ] && kill -0 "$OBSERVER_PID" >/dev/null 2>&1; then
    kill "$OBSERVER_PID" >/dev/null 2>&1 || true
    wait "$OBSERVER_PID" >/dev/null 2>&1 || true
  fi
}

copy_mpv_log() {
  local phase="$1"
  local dest="$OUT_DIR/$phase-mpv.log"
  local size=0

  if [ -e "$MPV_LOG_FILE" ]; then
    cp -L "$MPV_LOG_FILE" "$dest" 2>/dev/null || true
    if [ -f "$dest" ]; then
      chmod 0600 "$dest"
      size=$(wc -c <"$dest" 2>/dev/null || printf '0')
      append_summary "$phase-mpv-log-copy" "0" "$MPV_LOG_FILE copied to artifact without printing content; bytes=$size"
    else
      append_summary "$phase-mpv-log-copy" "1" "$MPV_LOG_FILE copy failed"
    fi
  else
    append_summary "$phase-mpv-log-copy" "missing" "$MPV_LOG_FILE not present"
  fi
}

copy_new_mpv_generation_logs() {
  local dest_dir="$OUT_DIR/mpv-generation-logs"
  local list_file="$OUT_DIR/post-mpv-generation-logs-copied.tsv"
  local path=""
  local name=""
  local dest=""
  local size=0
  local count=0
  local total_bytes=0
  local names=""

  mkdir -p "$dest_dir"
  chmod 0700 "$dest_dir"
  printf 'name\tbytes\tsource\tartifact\n' >"$list_file"

  while IFS= read -r path; do
    [ -n "$path" ] || continue
    name="$(basename "$path")"
    dest="$dest_dir/$name"
    cp -L "$path" "$dest"
    chmod 0600 "$dest"
    size=$(wc -c <"$dest" 2>/dev/null || printf '0')
    printf '%s\t%s\t%s\t%s\n' "$name" "$size" "$path" "$dest" >>"$list_file"
    count=$((count + 1))
    total_bytes=$((total_bytes + size))
    if [ -z "$names" ]; then
      names="$name"
    else
      names="$names,$name"
    fi
  done < <(find -L "$MPV_GENERATION_LOG_DIR" -maxdepth 1 -type f -name 'mpv-g*.log' -newer "$MARKER" -print 2>/dev/null | sort)

  if [ "$count" -eq 0 ]; then
    names="none"
  fi

  chmod 0600 "$list_file"
  append_summary "post-mpv-generation-logs-copy" "0" "count=$count bytes=$total_bytes names=$names; logs copied without printing content"
}

finish_archive() {
  stop_observer
  if command -v tar >/dev/null 2>&1; then
    tar -C "$BASE_DIR" -czf "$ARCHIVE" "$RUN_NAME"
    tar_rc=$?
    if [ "$tar_rc" -eq 0 ]; then
      echo "Kiosky service observer probe directory: $OUT_DIR"
      echo "Archive: $ARCHIVE"
      return 0
    fi
    echo "ERROR: failed to create archive $ARCHIVE" >&2
    return "$tar_rc"
  fi

  echo "ERROR: tar not found; probe directory kept at $OUT_DIR" >&2
  return 127
}

trap 'stop_observer >/dev/null 2>&1 || true' EXIT

start_observer() {
  local stdout_file="$OUT_DIR/playback-observer.stdout.txt"
  local stderr_file="$OUT_DIR/playback-observer.stderr.txt"
  local samples_file="$OUT_DIR/playback-samples.tsv"
  local status_samples_file="$OUT_DIR/status-samples.ndjson"
  local observer_summary_file="$OUT_DIR/playback-observer-summary.tsv"

  python3 - "$CONFIG_PATH" "$STATUS_FILE" "$samples_file" "$status_samples_file" \
    "$observer_summary_file" "$OBSERVER_INTERVAL_SEC" "$OBSERVER_IPC_TIMEOUT_SEC" \
    >"$stdout_file" 2>"$stderr_file" <<'PY' &
import hashlib
import json
import os
import signal
import socket
import sys
import time

(
    config_path,
    fallback_status_path,
    samples_path,
    status_samples_path,
    summary_path,
    interval_s,
    ipc_timeout_s,
) = sys.argv[1:]

interval = float(interval_s)
ipc_timeout = float(ipc_timeout_s)
stop = False
started = time.monotonic()
props = [
    "idle-active",
    "pause",
    "time-pos",
    "duration",
    "percent-pos",
    "eof-reached",
    "estimated-frame-number",
    "filename",
    "path",
    "video-params",
]
counts = {"success": 0, "timeout": 0, "error": 0}
unique_aliases = set()


def request_stop(signum, frame):
    del signum, frame
    global stop
    stop = True


signal.signal(signal.SIGTERM, request_stop)
signal.signal(signal.SIGINT, request_stop)


def sha1_short(value):
    return hashlib.sha1(str(value).encode("utf-8"), usedforsecurity=False).hexdigest()[:10]


def media_alias(path="", url=""):
    source = url or path or ""
    return f"media-{sha1_short(source)}" if source else ""


def safe_path_alias(value):
    if not isinstance(value, str) or not value:
        return ""
    if "://" in value:
        return f"<redacted-url:{sha1_short(value)}>"
    if value.startswith("/data/media/") or value.startswith("/tmp/"):
        return f"<media-path:{sha1_short(value)}>"
    if value.startswith("/data/"):
        return f"<data-path:{sha1_short(value)}>"
    if value.startswith("/"):
        return f"<local-path:{sha1_short(value)}>"
    return f"<filename:{sha1_short(value)}>"


def scalar(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return f"{float(value):.6f}".rstrip("0").rstrip(".")
    return str(value)


def compact_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def load_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except Exception:
        return {"_parse_error": True}


def sanitize_item(value):
    if not isinstance(value, dict):
        return {}
    path = value.get("path") if isinstance(value.get("path"), str) else ""
    url = value.get("url") if isinstance(value.get("url"), str) else ""
    out = {
        "alias": media_alias(path, url),
        "path_alias": safe_path_alias(path),
    }
    if isinstance(value.get("duration_ms"), (int, float, str)):
        try:
            out["duration_ms"] = int(value.get("duration_ms"))
        except Exception:
            pass
    if isinstance(value.get("offset_ms"), (int, float, str)):
        try:
            out["offset_ms"] = int(value.get("offset_ms"))
        except Exception:
            pass
    if isinstance(value.get("started_at"), str):
        out["started_at_present"] = True
    return out


def sanitize_error_presence(value):
    if value in (None, "", False):
        return "null"
    return "present"


def sanitize_status(status_path):
    raw = load_json_file(status_path)
    if raw is None:
        return {"present": False}
    if not isinstance(raw, dict):
        return {"present": True, "parse_error": True}
    if raw.get("_parse_error"):
        return {"present": True, "parse_error": True}
    current_item = sanitize_item(raw.get("current_item"))
    next_item = sanitize_item(raw.get("next_item"))
    return {
        "present": True,
        "playback_state": raw.get("playback_state"),
        "playlist_size": raw.get("playlist_size"),
        "current_index": raw.get("current_index"),
        "mpv_running": raw.get("mpv_running"),
        "consecutive_failures": raw.get("consecutive_failures"),
        "blocked_media_count": raw.get("blocked_media_count"),
        "uptime_sec": raw.get("uptime_sec"),
        "last_poll_error": sanitize_error_presence(raw.get("last_poll_error")),
        "last_render_error": sanitize_error_presence(raw.get("last_render_error")),
        "black_screen_risk_reason": sanitize_error_presence(raw.get("black_screen_risk_reason")),
        "current_item": current_item,
        "next_item": next_item,
    }


def sanitize_video_params(value):
    if not isinstance(value, dict):
        return {}
    safe = {}
    for key in (
        "w",
        "h",
        "dw",
        "dh",
        "aspect",
        "par",
        "rotate",
        "pixelformat",
        "hw-pixelformat",
        "stereo-in",
    ):
        if key in value and (value[key] is None or isinstance(value[key], (str, int, float, bool))):
            safe[key] = value.get(key)
    return safe


def ipc_query_many(ipc_path):
    if not ipc_path:
        return "error", "missing_ipc_path", {}, 0, {}
    if not os.path.exists(ipc_path):
        return "error", "missing_socket", {}, 0, {}

    start = time.monotonic()
    responses = {}
    rid_to_prop = {}
    prop_errors = {}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(ipc_timeout)
            sock.connect(ipc_path)
            for index, prop in enumerate(props, start=1):
                rid = 700000 + index
                rid_to_prop[rid] = prop
                payload = {"command": ["get_property", prop], "request_id": rid}
                sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))

            buffer = ""
            deadline = start + ipc_timeout
            while len(responses) < len(rid_to_prop) and time.monotonic() < deadline:
                sock.settimeout(max(deadline - time.monotonic(), 0.05))
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    break
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
                    rid = candidate.get("request_id")
                    prop = rid_to_prop.get(rid)
                    if not prop:
                        continue
                    responses[prop] = candidate.get("data")
                    prop_errors[prop] = str(candidate.get("error", "missing-error"))
    except socket.timeout:
        elapsed_ms = int(round((time.monotonic() - start) * 1000))
        return "timeout", "socket_timeout", responses, elapsed_ms, prop_errors
    except Exception as exc:
        elapsed_ms = int(round((time.monotonic() - start) * 1000))
        return "error", type(exc).__name__, responses, elapsed_ms, prop_errors

    elapsed_ms = int(round((time.monotonic() - start) * 1000))
    if len(responses) < len(rid_to_prop):
        return "timeout", "partial_response", responses, elapsed_ms, prop_errors
    return "success", "", responses, elapsed_ms, prop_errors


with open(config_path, "r", encoding="utf-8") as fh:
    cfg = json.load(fh)

ipc_path = cfg.get("ipc_path") or "/tmp/kiosky/mpv.sock"
status_path = cfg.get("status_file") or fallback_status_path

with open(samples_path, "w", encoding="utf-8") as samples:
    samples.write(
        "seq\trel_sec\twall_time\tipc_result\tipc_error\tipc_elapsed_ms\t"
        "current_alias\tpath_alias\tfilename_alias\ttime_pos\tduration\tpercent_pos\t"
        "idle_active\tpause\teof_reached\testimated_frame_number\tvideo_params_json\t"
        "property_errors_json\tstatus_present\tstatus_playback_state\tstatus_current_alias\t"
        "status_path_alias\tstatus_duration_ms\tstatus_current_index\tstatus_mpv_running\t"
        "status_snapshot_json\n"
    )

seq = 0
while not stop:
    seq += 1
    rel_sec = time.monotonic() - started
    wall_time = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    ipc_result, ipc_error, values, ipc_elapsed_ms, prop_errors = ipc_query_many(ipc_path)
    counts[ipc_result] = counts.get(ipc_result, 0) + 1

    path_alias = safe_path_alias(values.get("path"))
    filename_alias = safe_path_alias(values.get("filename"))
    current_alias = path_alias or filename_alias
    video_params_json = compact_json(sanitize_video_params(values.get("video-params")))
    status = sanitize_status(status_path)
    current_item = status.get("current_item") if isinstance(status, dict) else {}
    if not isinstance(current_item, dict):
        current_item = {}
    status_current_alias = current_item.get("alias", "")
    status_path_alias = current_item.get("path_alias", "")
    if not current_alias:
        current_alias = status_path_alias or status_current_alias
    if current_alias:
        unique_aliases.add(current_alias)

    status_snapshot_json = compact_json(status)
    with open(status_samples_path, "a", encoding="utf-8") as status_samples:
        status_samples.write(compact_json({"seq": seq, "rel_sec": round(rel_sec, 3), "status": status}) + "\n")

    row = [
        str(seq),
        f"{rel_sec:.3f}",
        wall_time,
        ipc_result,
        ipc_error,
        str(ipc_elapsed_ms),
        current_alias,
        path_alias,
        filename_alias,
        scalar(values.get("time-pos")),
        scalar(values.get("duration")),
        scalar(values.get("percent-pos")),
        scalar(values.get("idle-active")),
        scalar(values.get("pause")),
        scalar(values.get("eof-reached")),
        scalar(values.get("estimated-frame-number")),
        video_params_json,
        compact_json(prop_errors),
        "true" if status.get("present") else "false",
        scalar(status.get("playback_state")),
        status_current_alias,
        status_path_alias,
        scalar(current_item.get("duration_ms")),
        scalar(status.get("current_index")),
        scalar(status.get("mpv_running")),
        status_snapshot_json,
    ]
    with open(samples_path, "a", encoding="utf-8") as samples:
        samples.write("\t".join(row) + "\n")

    deadline = time.monotonic() + interval
    while not stop and time.monotonic() < deadline:
        time.sleep(min(0.1, deadline - time.monotonic()))

with open(summary_path, "w", encoding="utf-8") as summary:
    summary.write("metric\tvalue\n")
    summary.write(f"samples\t{seq}\n")
    summary.write(f"ipc_success\t{counts.get('success', 0)}\n")
    summary.write(f"ipc_timeout\t{counts.get('timeout', 0)}\n")
    summary.write(f"ipc_error\t{counts.get('error', 0)}\n")
    summary.write(f"unique_aliases\t{len(unique_aliases)}\n")
PY
  OBSERVER_PID="$!"
  append_summary "playback-observer-start" "0" "external short-connection MPV IPC observer started pid=$OBSERVER_PID"
}

{
  echo "kiosky_service_observer_probe_version=1"
  echo "timestamp=$TIMESTAMP"
  echo "run_name=$RUN_NAME"
  echo "output_dir=$OUT_DIR"
  echo "archive=$ARCHIVE"
  echo "service_name=$SERVICE_NAME"
  echo "app_dir=$APP_DIR"
  echo "config_path=$CONFIG_PATH"
  echo "runtime_dir=$RUNTIME_DIR"
  echo "status_file=$STATUS_FILE"
  echo "mpv_log_file=$MPV_LOG_FILE"
  echo "mpv_generation_log_dir=$MPV_GENERATION_LOG_DIR"
  echo "marker=$MARKER"
  echo "observe_duration_sec=$OBSERVE_DURATION_SEC"
  echo "observer_interval_sec=$OBSERVER_INTERVAL_SEC"
  echo "observer_ipc_timeout_sec=$OBSERVER_IPC_TIMEOUT_SEC"
  echo "hostname=$(hostname 2>/dev/null || true)"
  echo "created_at=$(stamp)"
} >"$OUT_DIR/manifest.txt"

printf 'label\texit_code\tnote\n' >"$SUMMARY"

if ! id "$APP_USER" >/dev/null 2>&1; then
  echo "ERROR: user not found: $APP_USER" >&2
  append_summary "prereq-user" "1" "missing user: $APP_USER"
  finish_archive
  exit 1
fi

if [ ! -f "$CONFIG_PATH" ]; then
  echo "ERROR: required config not found: $CONFIG_PATH" >&2
  append_summary "prereq-config" "1" "missing config: $CONFIG_PATH"
  finish_archive
  exit 1
fi

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: application directory not found: $APP_DIR" >&2
  append_summary "prereq-app-dir" "1" "missing app dir: $APP_DIR"
  finish_archive
  exit 1
fi

if ! systemctl list-unit-files "$SERVICE_NAME" >/dev/null 2>&1; then
  echo "ERROR: service unit not found: $SERVICE_NAME" >&2
  append_summary "prereq-service-unit" "1" "service unit not found: $SERVICE_NAME"
  finish_archive
  exit 1
fi

install -d -m 0750 -o "$APP_USER" -g "$APP_USER" "$RUNTIME_DIR"
chmod 0750 "$RUNTIME_DIR"
chown "$APP_USER:$APP_USER" "$RUNTIME_DIR"

run_shell "pre-date" "date before service observation" "date"
run_shell "pre-systemctl-is-enabled" "systemctl is-enabled before service observation" "systemctl is-enabled '$SERVICE_NAME' || true"
run_shell "pre-systemctl-is-active" "systemctl is-active before service observation" "systemctl is-active '$SERVICE_NAME' || true"
run_shell "pre-systemctl-status" "systemctl status before service observation" "systemctl status '$SERVICE_NAME' --no-pager || true"
run_shell "pre-systemctl-cat" "systemctl cat service unit" "systemctl cat '$SERVICE_NAME'"
run_shell "pre-systemctl-failed" "systemctl --failed before service observation" "systemctl --failed"
run_shell "pre-id-totem" "id totem before service observation" "id totem"
run_shell "pre-command-mpv" "command -v mpv before service observation" "command -v mpv"
run_shell "pre-python-requests" "python3 requests version before service observation" "python3 -c 'import requests; print(requests.__version__)'"
run_shell "pre-stat-config" "stat config before service observation without printing content" "stat '$CONFIG_PATH'"
run_shell "pre-stat-runtime-dir" "stat runtime dir before service observation" "stat '$RUNTIME_DIR'"
run_shell "pre-processes-totem" "totem kiosk/mpv processes before observation" "pgrep -a -u '$APP_USER' -f 'kiosk.py|mpv' || true"

run_shell "pre-config-json-valid" "validate config JSON without printing content" "python3 -m json.tool '$CONFIG_PATH' >/dev/null"
if [ "$RUN_SHELL_LAST_RC" -ne 0 ]; then
  echo "ERROR: config is not valid JSON: $CONFIG_PATH" >&2
  append_summary "prereq-config-json" "1" "invalid JSON; service was not observed"
  finish_archive
  exit 1
fi

check_expected_config
if [ "$RUN_SHELL_LAST_RC" -ne 0 ]; then
  echo "ERROR: expected non-sensitive config fields do not match." >&2
  append_summary "prereq-config-expected-fields" "1" "config mismatch; service was not observed"
  finish_archive
  exit 1
fi

touch "$MARKER"
chmod 0600 "$MARKER"
JOURNAL_SINCE="$(date '+%Y-%m-%d %H:%M:%S')"
append_summary "marker-created" "0" "$MARKER"

start_observer
sleep "$OBSERVE_DURATION_SEC"
stop_observer

run_shell "post-systemctl-is-active-before-stop" "systemctl is-active before stopping service" "systemctl is-active '$SERVICE_NAME' || true"
run_shell "post-systemctl-status-before-stop" "systemctl status before stopping service" "systemctl status '$SERVICE_NAME' --no-pager || true"
run_shell "post-service-journal" "journal for service observation window" "journalctl -u '$SERVICE_NAME' --since '$JOURNAL_SINCE' --no-pager || true"
run_shell "post-status-json-stat" "stat status JSON without printing content" "stat '$STATUS_FILE' || true"
copy_mpv_log "post"
copy_new_mpv_generation_logs

run_shell "stop-service" "stop service after observation" "systemctl stop '$SERVICE_NAME'"
run_shell "post-systemctl-is-active-after-stop" "systemctl is-active after stopping service" "systemctl is-active '$SERVICE_NAME' || true"
run_shell "post-processes-totem" "totem kiosk/mpv processes after stopping service" "pgrep -a -u '$APP_USER' -f 'kiosk.py|mpv' || true"
run_shell "post-processes-all" "all kiosk/mpv processes after stopping service" "pgrep -a -f 'kiosk.py|mpv' || true"
run_shell "post-systemctl-failed" "systemctl --failed after service observation" "systemctl --failed"
run_shell "post-opt-newer-marker" "files written under /opt/totem/kiosky-player after marker" \
  "find '$APP_DIR' -newer '$MARKER' -printf '%TY-%Tm-%TdT%TH:%TM:%TS %u %g %m %p\n' 2>/dev/null | sort || true"
run_shell "post-journalctl-kernel-critical-filter" "journalctl kernel critical filter after service observation" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|voltage|fail|error' || true"

finish_archive
