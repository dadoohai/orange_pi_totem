#!/usr/bin/env bash
set -u

umask 077

KIOSKY_APP_DIR="${KIOSKY_APP_DIR:-/opt/totem/kiosky-player}"
RUNTIME_DIR="/tmp/kiosky"
MEDIA_ROOT="/data/media/kiosky-player"
IPC_SOCKET="$RUNTIME_DIR/controller-probe-mpv.sock"
MPV_LOG="$RUNTIME_DIR/controller-probe-mpv.log"
export MPV_CONTROLLER_PROBE_MPV_PATH="${MPV_CONTROLLER_PROBE_MPV_PATH:-/opt/totem/bin/totem-mpv-hwdecode}"
BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="${TOTEM_DIAG_TIMESTAMP:-$(date +%Y%m%d-%H%M%S%z)}"
RUN_NAME="mpv-controller-playlist-$TIMESTAMP"
OUT_DIR="$BASE_DIR/$RUN_NAME"
ARCHIVE="$BASE_DIR/$RUN_NAME.tar.gz"
SUMMARY="$OUT_DIR/summary.tsv"
COMMAND_RESULTS="$OUT_DIR/command-results.tsv"
PRIVATE_SPEC="$RUNTIME_DIR/controller-probe-spec-$TIMESTAMP.tsv"
PUBLIC_SPEC="$OUT_DIR/playlist-spec-public.tsv"
LOADFILE_RESULTS="$OUT_DIR/loadfile-results.tsv"
PING_RESULTS="$OUT_DIR/ping-results.tsv"
STATE_RESULTS="$OUT_DIR/state-results.tsv"
CONTROLLER_LOG="$OUT_DIR/mpv-controller-probe.log"
PROBE_STDOUT="$OUT_DIR/controller-probe.stdout.txt"
PROBE_STDERR="$OUT_DIR/controller-probe.stderr.txt"
PING_INTERVAL_SEC="${MPV_CONTROLLER_PROBE_PING_INTERVAL_SEC:-10}"
PY_PROBE=""

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

if [ "$#" -ne 10 ]; then
  echo "Usage: $0 <duration_ms> /data/media/kiosky-player/media ... exactly 5 pairs" >&2
  exit 2
fi

for arg in "$@"; do
  case "$arg" in
    *://*)
      echo "ERROR: URLs are not accepted; pass local media paths only." >&2
      exit 2
      ;;
  esac
done

case "$PING_INTERVAL_SEC" in
  ''|*[!0-9]*)
    echo "ERROR: MPV_CONTROLLER_PROBE_PING_INTERVAL_SEC must be a positive integer." >&2
    exit 2
    ;;
  0)
    echo "ERROR: MPV_CONTROLLER_PROBE_PING_INTERVAL_SEC must be greater than zero." >&2
    exit 2
    ;;
esac

mkdir -p "$OUT_DIR"
install -d -m 0750 "$RUNTIME_DIR"

stamp() {
  date '+%Y-%m-%dT%H:%M:%S%z'
}

append_command_result() {
  local label="$1"
  local rc="$2"
  local note="$3"

  printf '%s\t%s\t%s\n' "$label" "$rc" "$note" >>"$COMMAND_RESULTS"
}

append_summary_metric() {
  local metric="$1"
  local value="$2"

  printf '%s\t%s\n' "$metric" "$value" >>"$SUMMARY"
}

safe_media_alias_for_path() {
  printf '%s' "$1" | sha1sum | awk '{print "<media-path:" substr($1, 1, 10) ">"}'
}

resolve_media_path() {
  local input="$1"
  local var_name="$2"
  local resolved=""

  case "$input" in
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

  append_command_result "$label" "$rc" "$title"
  return 0
}

copy_controller_mpv_logs() {
  local copied=0
  local log_dir="$OUT_DIR/mpv-generation-logs"
  local log_file=""

  mkdir -p "$log_dir"
  for log_file in "$RUNTIME_DIR"/controller-probe-mpv-g*.log; do
    [ -f "$log_file" ] || continue
    cp "$log_file" "$log_dir/"
    chmod 0600 "$log_dir/$(basename "$log_file")"
    copied=$((copied + 1))
  done

  if [ -e "$MPV_LOG" ]; then
    cp -L "$MPV_LOG" "$OUT_DIR/mpv-current.log" 2>/dev/null || true
    [ -f "$OUT_DIR/mpv-current.log" ] && chmod 0600 "$OUT_DIR/mpv-current.log"
  fi

  append_summary_metric "mpv_generation_logs_copied" "$copied"
  append_command_result "mpv-generation-log-copy" "0" "copied MPV logs by generation"
}

cleanup_temp_probe() {
  if [ -n "$PY_PROBE" ] && [ -f "$PY_PROBE" ]; then
    rm -f "$PY_PROBE"
  fi
  rm -f "$PRIVATE_SPEC"
}

trap 'cleanup_temp_probe >/dev/null 2>&1 || true' EXIT

printf 'metric\tvalue\n' >"$SUMMARY"
printf 'label\texit_code\tnote\n' >"$COMMAND_RESULTS"
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

if [ "$item_index" -ne 5 ]; then
  echo "ERROR: expected exactly 5 playlist items." >&2
  exit 2
fi

{
  echo "mpv_controller_playlist_probe_version=1"
  echo "timestamp=$TIMESTAMP"
  echo "run_name=$RUN_NAME"
  echo "output_dir=$OUT_DIR"
  echo "archive=$ARCHIVE"
  echo "kiosky_app_dir=$KIOSKY_APP_DIR"
  echo "runtime_dir=$RUNTIME_DIR"
  echo "ipc_socket=$IPC_SOCKET"
  echo "mpv_log=$MPV_LOG"
  echo "media_root=$MEDIA_ROOT"
  echo "playlist_items=$item_index"
  echo "ping_interval_sec=$PING_INTERVAL_SEC"
  echo "kiosk_main_started=no"
  echo "api_called=no"
  echo "cache_state_modified=no"
  echo "hostname=$(hostname 2>/dev/null || true)"
  echo "created_at=$(stamp)"
} >"$OUT_DIR/manifest.txt"

if [ ! -f "$KIOSKY_APP_DIR/kiosk.py" ]; then
  echo "ERROR: kiosk.py not found in deployed app directory." >&2
  append_command_result "prereq-kiosk-py" "1" "missing deployed kiosk.py"
  append_summary_metric "probe_error" "missing_kiosk_py"
  tar -C "$BASE_DIR" -czf "$ARCHIVE" "$RUN_NAME" 2>/dev/null || true
  exit 1
fi

run_shell "pre-date" "date" "date" "date"
run_shell "pre-uname-a" "uname -a" "uname -a" "uname -a"
run_shell "pre-systemctl-failed" "systemctl --failed before MPVController probe" \
  "systemctl --failed" \
  "systemctl --failed"
run_shell "pre-command-mpv" "command -v mpv" "command -v mpv" "command -v mpv"

rm -f "$IPC_SOCKET" "$MPV_LOG" "$RUNTIME_DIR"/controller-probe-mpv-g*.log

PY_PROBE="$(mktemp "$RUNTIME_DIR/controller-probe.XXXXXX.py")"
cat >"$PY_PROBE" <<'PY'
#!/usr/bin/env python3
import importlib.util
import json
import logging
import os
import signal
import sys
import threading
import time
import traceback


def load_kiosk_module(kiosk_path):
    spec = importlib.util.spec_from_file_location("kiosk_probe_module", kiosk_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to create import spec for kiosk.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_tsv(path, line):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def json_compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def log_basename(path):
    if not path:
        return "none"
    return os.path.basename(str(path)) or "none"


def pid_value(mpv):
    return str(mpv.pid() or "none")


def generation_value(mpv):
    try:
        return str(mpv.generation())
    except Exception:
        return "unknown"


def classify_result(ok, elapsed_ms, timeout_sec, exception_text=""):
    if exception_text:
        return "exception"
    if ok:
        return "success"
    if elapsed_ms >= int(max(timeout_sec, 0.1) * 1000) - 25:
        return "timeout"
    return "error"


def main(argv):
    if len(argv) != 11:
        raise SystemExit("internal usage error")

    (
        kiosk_path,
        spec_path,
        runtime_dir,
        ipc_path,
        mpv_log_file,
        ping_interval_s,
        summary_out,
        loadfile_out,
        ping_out,
        state_out,
        controller_log,
    ) = argv

    ping_interval = float(ping_interval_s)
    timeout_sec = 2.0
    stop_event = threading.Event()
    phase_lock = threading.Lock()
    phase = {"index": "none", "alias": "none"}
    counts = {
        "loadfile_success": 0,
        "loadfile_timeout": 0,
        "loadfile_error": 0,
        "ping_success": 0,
        "ping_timeout": 0,
        "ping_error": 0,
        "state_success": 0,
        "state_timeout": 0,
        "state_error": 0,
        "exceptions": 0,
    }

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(threadName)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(controller_log, encoding="utf-8"),
        ],
        force=True,
    )

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

    kiosk = load_kiosk_module(kiosk_path)
    cfg = dict(kiosk.DEFAULT_CONFIG)
    cfg.update(
        {
            "mpv_path": os.environ.get("MPV_CONTROLLER_PROBE_MPV_PATH", "/opt/totem/bin/totem-mpv-hwdecode"),
            "ipc_path": ipc_path,
            "runtime_dir": runtime_dir,
            "mpv_log_file": mpv_log_file,
            "mpv_msg_level": "all=v",
            "mpv_ipc_timeout_sec": 2.0,
            "mpv_startup_timeout_sec": 10.0,
            "mpv_debug_events": True,
            "hwdec": "auto-safe",
            "lock_input": True,
            "hotkeys_enabled": False,
            "low_resource_mode": True,
            "rotation_deg": 0,
            "cache_dir": "",
            "state_dir": "",
            "status_file": "",
            "log_file": "",
            "config_ui_enabled": False,
            "telemetry_enabled": False,
            "sync_enabled": False,
            "preload_next": False,
        }
    )

    write_tsv(
        loadfile_out,
        "index\talias\tduration_ms\tresult\tok\telapsed_ms\tbefore_generation\tbefore_pid\tbefore_log_file\tafter_generation\tafter_pid\tafter_log_file\texception",
    )
    write_tsv(
        ping_out,
        "seq\tphase_index\tphase_alias\tsince_start_ms\tresult\tok\telapsed_ms\tbefore_generation\tbefore_pid\tbefore_log_file\tafter_generation\tafter_pid\tafter_log_file\texception",
    )
    write_tsv(
        state_out,
        "index\talias\tproperty\tresult\tok\telapsed_ms\tgeneration\tpid\tcurrent_log_file\tvalue_json\texception",
    )

    mpv = kiosk.MPVController(cfg)
    started = time.monotonic()

    def request_stop(signum, frame):
        del signum, frame
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    def record_ping(seq):
        with phase_lock:
            phase_index = phase["index"]
            phase_alias = phase["alias"]
        before_generation = generation_value(mpv)
        before_pid = pid_value(mpv)
        before_log = log_basename(mpv.current_log_file())
        start = time.monotonic()
        ok = False
        exception_text = ""
        try:
            ok = bool(mpv.ping())
        except Exception as exc:
            counts["exceptions"] += 1
            exception_text = type(exc).__name__
            logging.exception("probe ping exception")
        elapsed_ms = int(round((time.monotonic() - start) * 1000))
        result = classify_result(ok, elapsed_ms, timeout_sec, exception_text)
        if result == "success":
            counts["ping_success"] += 1
        elif result == "timeout":
            counts["ping_timeout"] += 1
        else:
            counts["ping_error"] += 1
        write_tsv(
            ping_out,
            "\t".join(
                [
                    str(seq),
                    str(phase_index),
                    str(phase_alias),
                    str(int(round((time.monotonic() - started) * 1000))),
                    result,
                    str(bool(ok)).lower(),
                    str(elapsed_ms),
                    before_generation,
                    before_pid,
                    before_log,
                    generation_value(mpv),
                    pid_value(mpv),
                    log_basename(mpv.current_log_file()),
                    exception_text,
                ]
            ),
        )

    def ping_loop():
        seq = 0
        while not stop_event.is_set():
            seq += 1
            record_ping(seq)
            stop_event.wait(ping_interval)

    def record_state(item):
        for prop in ["idle-active", "time-pos", "duration", "eof-reached"]:
            start = time.monotonic()
            value = None
            exception_text = ""
            try:
                value = mpv.get_property(prop, timeout=timeout_sec)
            except Exception as exc:
                counts["exceptions"] += 1
                exception_text = type(exc).__name__
                logging.exception("probe state exception")
            elapsed_ms = int(round((time.monotonic() - start) * 1000))
            ok = value is not None and not exception_text
            result = classify_result(ok, elapsed_ms, timeout_sec, exception_text)
            if result == "success":
                counts["state_success"] += 1
            elif result == "timeout":
                counts["state_timeout"] += 1
            else:
                counts["state_error"] += 1
            write_tsv(
                state_out,
                "\t".join(
                    [
                        str(item["index"]),
                        item["alias"],
                        prop,
                        result,
                        str(bool(ok)).lower(),
                        str(elapsed_ms),
                        generation_value(mpv),
                        pid_value(mpv),
                        log_basename(mpv.current_log_file()),
                        json_compact(value),
                        exception_text,
                    ]
                ),
            )

    start_ok = False
    start_generation = "0"
    start_pid = "none"
    final_generation = "0"
    final_pid = "none"
    mpv_running_before_stop = "false"
    stop_exception = ""

    try:
        logging.info("probe importing kiosk.py without starting kiosk main")
        logging.info("probe starting MPVController")
        mpv.start()
        start_ok = mpv.is_running()
        start_generation = generation_value(mpv)
        start_pid = pid_value(mpv)
        if not start_ok:
            logging.error("probe MPVController did not start a running MPV process")
            return 1

        ping_thread = threading.Thread(target=ping_loop, name="probe-ping-loop", daemon=True)
        ping_thread.start()

        for item in playlist:
            if stop_event.is_set():
                break
            with phase_lock:
                phase["index"] = str(item["index"])
                phase["alias"] = item["alias"]
            before_generation = generation_value(mpv)
            before_pid = pid_value(mpv)
            before_log = log_basename(mpv.current_log_file())
            start = time.monotonic()
            ok = False
            exception_text = ""
            try:
                ok = bool(mpv.load_file(item["path"], alias=item["alias"]))
            except Exception as exc:
                counts["exceptions"] += 1
                exception_text = type(exc).__name__
                logging.exception("probe load_file exception")
            elapsed_ms = int(round((time.monotonic() - start) * 1000))
            result = classify_result(ok, elapsed_ms, timeout_sec, exception_text)
            if result == "success":
                counts["loadfile_success"] += 1
            elif result == "timeout":
                counts["loadfile_timeout"] += 1
            else:
                counts["loadfile_error"] += 1
            write_tsv(
                loadfile_out,
                "\t".join(
                    [
                        str(item["index"]),
                        item["alias"],
                        str(item["duration_ms"]),
                        result,
                        str(bool(ok)).lower(),
                        str(elapsed_ms),
                        before_generation,
                        before_pid,
                        before_log,
                        generation_value(mpv),
                        pid_value(mpv),
                        log_basename(mpv.current_log_file()),
                        exception_text,
                    ]
                ),
            )

            stop_event.wait(max(item["duration_ms"], 0) / 1000.0)
            if stop_event.is_set():
                break
            record_state(item)

        stop_event.set()
        ping_thread.join(timeout=ping_interval + timeout_sec + 1.0)
        final_generation = generation_value(mpv)
        final_pid = pid_value(mpv)
        mpv_running_before_stop = str(bool(mpv.is_running())).lower()
        return 0
    finally:
        try:
            logging.info("probe stopping MPVController")
            mpv.stop()
        except Exception as exc:
            stop_exception = type(exc).__name__
            counts["exceptions"] += 1
            logging.exception("probe stop exception")
        restart_count = str(getattr(mpv, "_restart_count", "unknown"))
        with open(summary_out, "a", encoding="utf-8") as fh:
            rows = [
                ("playlist_items", str(len(playlist))),
                ("controller_start_ok", str(bool(start_ok)).lower()),
                ("start_generation", start_generation),
                ("start_pid", start_pid),
                ("final_generation_before_stop", final_generation),
                ("final_pid_before_stop", final_pid),
                ("mpv_running_before_stop", mpv_running_before_stop),
                ("restart_count", restart_count),
                ("loadfile_success", str(counts["loadfile_success"])),
                ("loadfile_timeout", str(counts["loadfile_timeout"])),
                ("loadfile_error", str(counts["loadfile_error"])),
                ("ping_success", str(counts["ping_success"])),
                ("ping_timeout", str(counts["ping_timeout"])),
                ("ping_error", str(counts["ping_error"])),
                ("state_success", str(counts["state_success"])),
                ("state_timeout", str(counts["state_timeout"])),
                ("state_error", str(counts["state_error"])),
                ("exceptions", str(counts["exceptions"])),
                ("stop_exception", stop_exception or "none"),
            ]
            for metric, value in rows:
                fh.write(f"{metric}\t{value}\n")


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
PY
chmod 0700 "$PY_PROBE"

PYTHONPATH="$KIOSKY_APP_DIR${PYTHONPATH:+:$PYTHONPATH}" \
  XDG_RUNTIME_DIR="$RUNTIME_DIR" \
  python3 "$PY_PROBE" \
  "$KIOSKY_APP_DIR/kiosk.py" \
  "$PRIVATE_SPEC" \
  "$RUNTIME_DIR" \
  "$IPC_SOCKET" \
  "$MPV_LOG" \
  "$PING_INTERVAL_SEC" \
  "$SUMMARY" \
  "$LOADFILE_RESULTS" \
  "$PING_RESULTS" \
  "$STATE_RESULTS" \
  "$CONTROLLER_LOG" \
  >"$PROBE_STDOUT" \
  2>"$PROBE_STDERR"
probe_rc=$?
append_command_result "mpv-controller-probe" "$probe_rc" "MPVController playlist with concurrent pings"

copy_controller_mpv_logs

run_shell "post-systemctl-failed" "systemctl --failed after MPVController probe" \
  "systemctl --failed" \
  "systemctl --failed"
run_shell "post-journalctl-kernel-critical-filter" "journalctl kernel critical filter after MPVController probe" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|voltage|fail|error' || true" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|voltage|fail|error' || true"

if command -v tar >/dev/null 2>&1; then
  tar -C "$BASE_DIR" -czf "$ARCHIVE" "$RUN_NAME"
  tar_rc=$?
  if [ "$tar_rc" -eq 0 ]; then
    echo "MPVController playlist probe directory: $OUT_DIR"
    echo "Archive: $ARCHIVE"
  else
    echo "ERROR: failed to create archive $ARCHIVE" >&2
    exit "$tar_rc"
  fi
else
  echo "ERROR: tar not found; probe directory kept at $OUT_DIR" >&2
  exit 127
fi

exit "$probe_rc"
