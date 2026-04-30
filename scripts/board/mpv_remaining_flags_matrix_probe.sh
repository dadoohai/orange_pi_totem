#!/usr/bin/env bash
set -u

umask 077

APP_USER="totem"
APP_GROUP="totem"
RUNTIME_DIR="/tmp/kiosky"
MEDIA_ROOT="/data/media/kiosky-player"
BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="${TOTEM_DIAG_TIMESTAMP:-$(date +%Y%m%d-%H%M%S%z)}"
RUN_NAME="mpv-remaining-flags-matrix-$TIMESTAMP"
OUT_DIR="$BASE_DIR/$RUN_NAME"
ARCHIVE="$BASE_DIR/$RUN_NAME.tar.gz"
SUMMARY="$OUT_DIR/summary.tsv"
PUBLIC_SPEC="$OUT_DIR/media-spec-public.tsv"
PRIVATE_SPEC="$RUNTIME_DIR/mpv-remaining-flags-matrix-spec-$TIMESTAMP.tsv"
VARIANTS_TSV="$OUT_DIR/variants.tsv"
RESULTS_TSV="$OUT_DIR/progress-results.tsv"
SAMPLES_TSV="$OUT_DIR/progress-samples.tsv"
COMMANDS_TSV="$OUT_DIR/command-results.tsv"
ORCHESTRATOR_STDOUT="$OUT_DIR/orchestrator.stdout.txt"
ORCHESTRATOR_STDERR="$OUT_DIR/orchestrator.stderr.txt"
OBSERVE_SEC="${MPV_REMAINING_FLAGS_OBSERVE_SEC:-9}"
SAMPLE_INTERVAL_SEC="${MPV_REMAINING_FLAGS_SAMPLE_INTERVAL_SEC:-0.5}"
IPC_TIMEOUT_SEC="${MPV_REMAINING_FLAGS_IPC_TIMEOUT_SEC:-1.0}"
PY_ORCHESTRATOR=""

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 /data/media/kiosky-player/media [...]" >&2
  echo "       $0 '<media-path:xxxxxxxxxx>' [...]" >&2
  exit 2
fi

case "$OBSERVE_SEC" in
  ''|*[!0-9.]*)
    echo "ERROR: MPV_REMAINING_FLAGS_OBSERVE_SEC must be a positive number." >&2
    exit 2
    ;;
esac

case "$SAMPLE_INTERVAL_SEC" in
  ''|*[!0-9.]*)
    echo "ERROR: MPV_REMAINING_FLAGS_SAMPLE_INTERVAL_SEC must be a positive number." >&2
    exit 2
    ;;
esac

case "$IPC_TIMEOUT_SEC" in
  ''|*[!0-9.]*)
    echo "ERROR: MPV_REMAINING_FLAGS_IPC_TIMEOUT_SEC must be a positive number." >&2
    exit 2
    ;;
esac

mkdir -p "$OUT_DIR"

stamp() {
  date '+%Y-%m-%dT%H:%M:%S%z'
}

append_command_result() {
  local label="$1"
  local rc="$2"
  local note="$3"

  printf '%s\t%s\t%s\n' "$label" "$rc" "$note" >>"$COMMANDS_TSV"
}

append_summary_metric() {
  local metric="$1"
  local value="$2"

  printf '%s\t%s\n' "$metric" "$value" >>"$SUMMARY"
}

safe_media_alias_for_path() {
  printf '%s' "$1" | sha1sum | awk '{print "<media-path:" substr($1, 1, 10) ">"}'
}

is_alias_token() {
  case "$1" in
    \<media-path:[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]\>) return 0 ;;
    [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) return 0 ;;
    *) return 1 ;;
  esac
}

normalize_alias_token() {
  local input="$1"

  case "$input" in
    \<media-path:*\>)
      printf '%s' "$input"
      ;;
    *)
      printf '<media-path:%s>' "$input"
      ;;
  esac
}

resolve_alias_to_path() {
  local alias="$1"
  local var_name="$2"
  local found=""
  local resolved=""
  local candidate_alias=""

  if [ ! -d "$MEDIA_ROOT" ]; then
    echo "ERROR: media root is missing." >&2
    exit 2
  fi

  while IFS= read -r -d '' candidate; do
    resolved="$(readlink -f -- "$candidate" 2>/dev/null || true)"
    [ -n "$resolved" ] || continue
    candidate_alias="$(safe_media_alias_for_path "$resolved")"
    if [ "$candidate_alias" = "$alias" ]; then
      found="$resolved"
      break
    fi
  done < <(find "$MEDIA_ROOT" -type f -print0 2>/dev/null)

  if [ -z "$found" ]; then
    echo "ERROR: media alias was not found under the allowed media root: $alias" >&2
    exit 2
  fi

  printf -v "$var_name" '%s' "$found"
}

resolve_media_path() {
  local input="$1"
  local var_name="$2"
  local resolved=""
  local alias=""

  case "$input" in
    *://*)
      echo "ERROR: URLs are not accepted; pass local media paths only." >&2
      exit 2
      ;;
  esac

  if is_alias_token "$input"; then
    alias="$(normalize_alias_token "$input")"
    resolve_alias_to_path "$alias" "$var_name"
    return
  fi

  case "$input" in
    /*)
      ;;
    *)
      echo "ERROR: media paths must be absolute local paths or sanitized media aliases." >&2
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
      echo "ERROR: media path is outside the allowed media root." >&2
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

cleanup_temp_probe() {
  if [ -n "$PY_ORCHESTRATOR" ] && [ -f "$PY_ORCHESTRATOR" ]; then
    rm -f "$PY_ORCHESTRATOR"
  fi
  rm -f "$PRIVATE_SPEC"
}

finish_archive() {
  cleanup_temp_probe >/dev/null 2>&1 || true
  if command -v tar >/dev/null 2>&1; then
    tar -C "$BASE_DIR" -czf "$ARCHIVE" "$RUN_NAME"
    tar_rc=$?
    if [ "$tar_rc" -eq 0 ]; then
      echo "MPV remaining flags matrix probe directory: $OUT_DIR"
      echo "Archive: $ARCHIVE"
      return 0
    fi
    echo "ERROR: failed to create archive $ARCHIVE" >&2
    return "$tar_rc"
  fi

  echo "ERROR: tar not found; probe directory kept at $OUT_DIR" >&2
  return 127
}

trap 'cleanup_temp_probe >/dev/null 2>&1 || true' EXIT

printf 'metric\tvalue\n' >"$SUMMARY"
printf 'label\texit_code\tnote\n' >"$COMMANDS_TSV"
printf 'index\talias\n' >"$PUBLIC_SPEC"
printf 'index\talias\tpath\n' >"$PRIVATE_SPEC"
chmod 0600 "$PRIVATE_SPEC"

if ! id "$APP_USER" >/dev/null 2>&1; then
  echo "ERROR: user not found: $APP_USER" >&2
  append_command_result "prereq-user" "1" "missing user"
  finish_archive
  exit 1
fi

if ! getent group "$APP_GROUP" >/dev/null 2>&1; then
  echo "ERROR: group not found: $APP_GROUP" >&2
  append_command_result "prereq-group" "1" "missing group"
  finish_archive
  exit 1
fi

install -d -m 0750 -o "$APP_USER" -g "$APP_GROUP" "$RUNTIME_DIR"

item_index=0
for media_arg in "$@"; do
  resolved_path=""
  resolve_media_path "$media_arg" resolved_path
  media_alias="$(safe_media_alias_for_path "$resolved_path")"
  item_index=$((item_index + 1))
  printf '%s\t%s\n' "$item_index" "$media_alias" >>"$PUBLIC_SPEC"
  printf '%s\t%s\t%s\n' "$item_index" "$media_alias" "$resolved_path" >>"$PRIVATE_SPEC"
done

{
  echo "mpv_remaining_flags_matrix_probe_version=1"
  echo "timestamp=$TIMESTAMP"
  echo "run_name=$RUN_NAME"
  echo "output_dir=$OUT_DIR"
  echo "archive=$ARCHIVE"
  echo "runtime_dir=$RUNTIME_DIR"
  echo "media_root=$MEDIA_ROOT"
  echo "media_count=$item_index"
  echo "observe_sec=$OBSERVE_SEC"
  echo "sample_interval_sec=$SAMPLE_INTERVAL_SEC"
  echo "ipc_timeout_sec=$IPC_TIMEOUT_SEC"
  echo "kiosk_main_started=no"
  echo "cache_state_modified=no"
  echo "hostname=$(hostname 2>/dev/null || true)"
  echo "created_at=$(stamp)"
} >"$OUT_DIR/manifest.txt"

append_summary_metric "media_count" "$item_index"
append_summary_metric "observe_sec" "$OBSERVE_SEC"
append_summary_metric "sample_interval_sec" "$SAMPLE_INTERVAL_SEC"
append_summary_metric "ipc_timeout_sec" "$IPC_TIMEOUT_SEC"

run_shell "pre-date" "date before MPV remaining flags matrix probe" "date" "date"
run_shell "pre-uname-a" "uname -a before MPV remaining flags matrix probe" "uname -a" "uname -a"
run_shell "pre-systemctl-failed" "systemctl --failed before MPV remaining flags matrix probe" \
  "systemctl --failed" \
  "systemctl --failed"
run_shell "pre-id-totem" "id totem before MPV remaining flags matrix probe" "id totem" "id totem"
run_shell "pre-command-mpv" "command -v mpv before MPV remaining flags matrix probe" "command -v mpv" "command -v mpv"

PY_ORCHESTRATOR="$(mktemp "$RUNTIME_DIR/mpv-remaining-flags-matrix.XXXXXX.py")"
cat >"$PY_ORCHESTRATOR" <<'PY'
#!/usr/bin/env python3
import csv
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


def write_tsv(path, row):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\t".join(str(value) for value in row) + "\n")


def compact_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def scalar(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return f"{float(value):.6f}".rstrip("0").rstrip(".")
    return str(value)


def number(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def bool_text(value):
    if value is True:
        return "true"
    if value is False:
        return "false"
    return ""


def ipc_command(sock_path, command, timeout, request_id):
    start = time.monotonic()
    response = None
    error = "no-response"
    data = None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(sock_path)
            payload = {"command": command, "request_id": request_id}
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
                    if candidate.get("request_id") == request_id:
                        response = candidate
                        error = str(candidate.get("error", "missing-error"))
                        data = candidate.get("data")
                        elapsed_ms = int(round((time.monotonic() - start) * 1000))
                        return error == "success", error, data, response, elapsed_ms
    except socket.timeout:
        error = "timeout"
    except Exception as exc:
        error = f"exception:{type(exc).__name__}"
    elapsed_ms = int(round((time.monotonic() - start) * 1000))
    return False, error, data, response, elapsed_ms


def sample_properties(sock_path, timeout, request_base):
    props = [
        "time-pos",
        "estimated-frame-number",
        "pause",
        "idle-active",
        "eof-reached",
        "duration",
        "percent-pos",
    ]
    values = {}
    errors = {}
    elapsed_total = 0
    for index, prop in enumerate(props, start=1):
        ok, error, data, _response, elapsed_ms = ipc_command(
            sock_path,
            ["get_property", prop],
            timeout,
            request_base + index,
        )
        elapsed_total += elapsed_ms
        errors[prop] = error
        values[prop] = data if ok else None
    return values, errors, elapsed_total


def wait_socket(sock_path, proc, timeout_sec=10.0):
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        if os.path.exists(sock_path):
            return True
        time.sleep(0.1)
    return False


def terminate_mpv(proc, sock_path, timeout, request_id):
    if os.path.exists(sock_path):
        ipc_command(sock_path, ["quit"], timeout, request_id)
    try:
        proc.wait(timeout=2.0)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        proc.terminate()
        proc.wait(timeout=2.0)
        return
    except Exception:
        pass
    try:
        proc.kill()
        proc.wait(timeout=2.0)
    except Exception:
        pass


def app_low_resource_off_flags(sock_path, log_path):
    return [
        "mpv",
        "--fs",
        "--force-window=yes",
        "--idle=yes",
        "--keep-open=yes",
        "--no-terminal",
        "--loop-file=inf",
        "--image-display-duration=inf",
        "--no-osc",
        "--osd-level=0",
        f"--input-ipc-server={sock_path}",
        f"--log-file={log_path}",
        "--msg-level=all=v",
        "--no-input-default-bindings",
        "--video-rotate=0",
        "--input-vo-keyboard=no",
        "--hwdec=auto-safe",
    ]


def without_flag(args, flag):
    return [arg for arg in args if arg != flag]


def with_no_config(sock_path, log_path):
    args = app_low_resource_off_flags(sock_path, log_path)
    return ["mpv", "--no-config"] + args[1:]


def with_explicit_output(sock_path, log_path):
    args = app_low_resource_off_flags(sock_path, log_path)
    return args + ["--vo=gpu", "--gpu-context=drm", "--ao=null"]


def simple_flags(sock_path, log_path):
    return [
        "mpv",
        "--no-config",
        "--fs",
        "--force-window=yes",
        "--idle=yes",
        "--no-terminal",
        "--no-osc",
        "--osd-level=0",
        "--vo=gpu",
        "--gpu-context=drm",
        "--hwdec=auto-safe",
        "--ao=null",
        f"--input-ipc-server={sock_path}",
        f"--log-file={log_path}",
        "--msg-level=all=v",
    ]


def sanitize_flags(args):
    safe = []
    for arg in args:
        if arg.startswith("--input-ipc-server="):
            safe.append("--input-ipc-server=<runtime-socket>")
        elif arg.startswith("--log-file="):
            safe.append("--log-file=<runtime-log>")
        else:
            safe.append(arg)
    return " ".join(safe)


def sanitize_text(text, media_items):
    for media in media_items:
        text = text.replace(media["path"], media["alias"])
    text = text.replace("/data/media/kiosky-player", "<media-root>")
    return text


def sanitize_file_in_place(path, media_items):
    path = Path(path)
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        path.write_text(sanitize_text(text, media_items), encoding="utf-8")
    except Exception:
        return


def load_media_spec(path):
    media = []
    with open(path, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            media.append(
                {
                    "index": int(row["index"]),
                    "alias": row["alias"],
                    "path": row["path"],
                }
            )
    return media


def main(argv):
    (
        private_spec,
        runtime_dir,
        out_dir,
        variants_tsv,
        results_tsv,
        samples_tsv,
        summary_tsv,
        observe_sec_s,
        sample_interval_s,
        ipc_timeout_s,
    ) = argv

    runtime = Path(runtime_dir)
    out = Path(out_dir)
    logs_dir = out / "mpv-logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    observe_sec = float(observe_sec_s)
    sample_interval = float(sample_interval_s)
    ipc_timeout = float(ipc_timeout_s)
    request_id = 20000
    total_runs = 0

    variants = [
        {
            "id": "V0",
            "label": "app-low-resource-off",
            "description": "Perfil app atual com low_resource_mode=false",
            "builder": app_low_resource_off_flags,
        },
        {
            "id": "V1",
            "label": "app-low-resource-off-no-config",
            "description": "V0 + --no-config",
            "builder": with_no_config,
        },
        {
            "id": "V2",
            "label": "app-low-resource-off-no-loop-file",
            "description": "V0 sem --loop-file=inf",
            "builder": lambda sock, log: without_flag(
                app_low_resource_off_flags(sock, log), "--loop-file=inf"
            ),
        },
        {
            "id": "V3",
            "label": "app-low-resource-off-no-keep-open",
            "description": "V0 sem --keep-open=yes",
            "builder": lambda sock, log: without_flag(
                app_low_resource_off_flags(sock, log), "--keep-open=yes"
            ),
        },
        {
            "id": "V4",
            "label": "app-low-resource-off-no-image-display-duration",
            "description": "V0 sem --image-display-duration=inf",
            "builder": lambda sock, log: without_flag(
                app_low_resource_off_flags(sock, log), "--image-display-duration=inf"
            ),
        },
        {
            "id": "V5",
            "label": "app-low-resource-off-explicit-output",
            "description": "V0 + --vo=gpu --gpu-context=drm --ao=null",
            "builder": with_explicit_output,
        },
        {
            "id": "V6",
            "label": "simple-direct-like-positive-control",
            "description": "Perfil simples aprovado, controle positivo",
            "builder": simple_flags,
        },
    ]

    write_tsv(variants_tsv, ["variant", "label", "description", "sanitized_flags"])
    for variant in variants:
        preview_sock = str(runtime / "mpv-remaining-flags-preview.sock")
        preview_log = str(runtime / "mpv-remaining-flags-preview.log")
        write_tsv(
            variants_tsv,
            [
                variant["id"],
                variant["label"],
                variant["description"],
                sanitize_flags(variant["builder"](preview_sock, preview_log)),
            ],
        )

    write_tsv(
        results_tsv,
        [
            "media_index",
            "media_alias",
            "variant",
            "variant_label",
            "socket_ready",
            "loadfile_error",
            "loadfile_elapsed_ms",
            "exit_code",
            "samples",
            "initial_time_pos",
            "final_time_pos",
            "max_time_pos",
            "time_pos_delta",
            "time_pos_advanced",
            "initial_frame",
            "final_frame",
            "max_frame",
            "frame_delta",
            "frame_advanced",
            "pause_true",
            "idle_true",
            "eof_true",
            "duration",
            "percent_initial",
            "percent_final",
            "mpv_log",
            "stdout_log",
            "stderr_log",
        ],
    )
    write_tsv(
        samples_tsv,
        [
            "media_index",
            "media_alias",
            "variant",
            "seq",
            "rel_sec",
            "time_pos",
            "estimated_frame_number",
            "pause",
            "idle_active",
            "eof_reached",
            "duration",
            "percent_pos",
            "property_errors_json",
        ],
    )

    media_items = load_media_spec(private_spec)

    for media in media_items:
        for variant in variants:
            total_runs += 1
            run_id = f"media{media['index']:02d}-{variant['id']}"
            sock_path = str(runtime / f"mpv-remaining-flags-{os.getpid()}-{run_id}.sock")
            runtime_log = str(runtime / f"mpv-remaining-flags-{os.getpid()}-{run_id}.log")
            stdout_path = logs_dir / f"{run_id}.stdout.txt"
            stderr_path = logs_dir / f"{run_id}.stderr.txt"
            artifact_log = logs_dir / f"{run_id}.mpv.log"

            for path in (sock_path, runtime_log):
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

            args = variant["builder"](sock_path, runtime_log)
            command = [
                "runuser",
                "-u",
                "totem",
                "--",
                "env",
                f"XDG_RUNTIME_DIR={runtime_dir}",
            ] + args

            with open(stdout_path, "w", encoding="utf-8") as stdout_fh, open(
                stderr_path, "w", encoding="utf-8"
            ) as stderr_fh:
                proc = subprocess.Popen(
                    command,
                    stdout=stdout_fh,
                    stderr=stderr_fh,
                    start_new_session=True,
                )

                socket_ready = wait_socket(sock_path, proc, timeout_sec=10.0)
                load_error = "socket_not_ready"
                load_elapsed = 0
                samples = []
                if socket_ready:
                    request_id += 100
                    _ok, load_error, _data, _response, load_elapsed = ipc_command(
                        sock_path,
                        ["loadfile", media["path"], "replace"],
                        ipc_timeout,
                        request_id,
                    )

                    started = time.monotonic()
                    seq = 0
                    while time.monotonic() - started <= observe_sec:
                        seq += 1
                        request_id += 100
                        values, errors, _elapsed_total = sample_properties(
                            sock_path,
                            ipc_timeout,
                            request_id,
                        )
                        rel_sec = time.monotonic() - started
                        sample = {
                            "seq": seq,
                            "rel_sec": rel_sec,
                            "time-pos": values.get("time-pos"),
                            "estimated-frame-number": values.get("estimated-frame-number"),
                            "pause": values.get("pause"),
                            "idle-active": values.get("idle-active"),
                            "eof-reached": values.get("eof-reached"),
                            "duration": values.get("duration"),
                            "percent-pos": values.get("percent-pos"),
                            "errors": errors,
                        }
                        samples.append(sample)
                        write_tsv(
                            samples_tsv,
                            [
                                media["index"],
                                media["alias"],
                                variant["id"],
                                seq,
                                f"{rel_sec:.3f}",
                                scalar(sample["time-pos"]),
                                scalar(sample["estimated-frame-number"]),
                                bool_text(sample["pause"]),
                                bool_text(sample["idle-active"]),
                                bool_text(sample["eof-reached"]),
                                scalar(sample["duration"]),
                                scalar(sample["percent-pos"]),
                                compact_json(errors),
                            ],
                        )
                        if sample["eof-reached"] is True:
                            break
                        sleep_until = started + (seq * sample_interval)
                        while time.monotonic() < sleep_until:
                            time.sleep(min(0.05, sleep_until - time.monotonic()))

                request_id += 100
                terminate_mpv(proc, sock_path, ipc_timeout, request_id)
                exit_code = proc.returncode

            if os.path.exists(runtime_log):
                shutil.copyfile(runtime_log, artifact_log)
                sanitize_file_in_place(artifact_log, media_items)
                os.chmod(artifact_log, 0o600)
            for copied_path in (stdout_path, stderr_path):
                sanitize_file_in_place(copied_path, media_items)
                try:
                    os.chmod(copied_path, 0o600)
                except OSError:
                    pass

            time_values = [number(s["time-pos"]) for s in samples if number(s["time-pos"]) is not None]
            frame_values = [
                number(s["estimated-frame-number"])
                for s in samples
                if number(s["estimated-frame-number"]) is not None
            ]
            duration_values = [number(s["duration"]) for s in samples if number(s["duration"]) is not None]
            percent_values = [number(s["percent-pos"]) for s in samples if number(s["percent-pos"]) is not None]
            pause_true = any(s["pause"] is True for s in samples)
            idle_true = any(s["idle-active"] is True for s in samples)
            eof_true = any(s["eof-reached"] is True for s in samples)
            time_delta = (max(time_values) - min(time_values)) if len(time_values) >= 2 else 0.0
            frame_delta = (max(frame_values) - min(frame_values)) if len(frame_values) >= 2 else 0.0

            write_tsv(
                results_tsv,
                [
                    media["index"],
                    media["alias"],
                    variant["id"],
                    variant["label"],
                    "true" if socket_ready else "false",
                    load_error,
                    load_elapsed,
                    "" if exit_code is None else exit_code,
                    len(samples),
                    scalar(time_values[0] if time_values else None),
                    scalar(time_values[-1] if time_values else None),
                    scalar(max(time_values) if time_values else None),
                    scalar(time_delta),
                    "yes" if time_delta > 0.5 else "no",
                    scalar(frame_values[0] if frame_values else None),
                    scalar(frame_values[-1] if frame_values else None),
                    scalar(max(frame_values) if frame_values else None),
                    scalar(frame_delta),
                    "yes" if frame_delta > 1 else "no" if frame_values else "n/a",
                    "yes" if pause_true else "no",
                    "yes" if idle_true else "no",
                    "yes" if eof_true else "no",
                    scalar(max(duration_values) if duration_values else None),
                    scalar(percent_values[0] if percent_values else None),
                    scalar(percent_values[-1] if percent_values else None),
                    artifact_log.name if artifact_log.exists() else "",
                    stdout_path.name,
                    stderr_path.name,
                ],
            )

            for path in (sock_path, runtime_log):
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

    with open(summary_tsv, "a", encoding="utf-8") as fh:
        fh.write(f"variant_count\t{len(variants)}\n")
        fh.write(f"run_count\t{total_runs}\n")
        fh.write("orchestrator_status\tcomplete\n")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
PY
chmod 0700 "$PY_ORCHESTRATOR"

run_shell "orchestrator" "run MPV remaining flags matrix without kiosk.py" \
  "python3 '$PY_ORCHESTRATOR' '$PRIVATE_SPEC' '$RUNTIME_DIR' '$OUT_DIR' '$VARIANTS_TSV' '$RESULTS_TSV' '$SAMPLES_TSV' '$SUMMARY' '$OBSERVE_SEC' '$SAMPLE_INTERVAL_SEC' '$IPC_TIMEOUT_SEC'" \
  "python3 <orchestrator> <private-spec> <runtime-dir> <out-dir> <variants.tsv> <results.tsv> <samples.tsv> <summary.tsv> $OBSERVE_SEC $SAMPLE_INTERVAL_SEC $IPC_TIMEOUT_SEC"

run_shell "post-date" "date after MPV remaining flags matrix probe" "date" "date"
run_shell "post-systemctl-failed" "systemctl --failed after MPV remaining flags matrix probe" \
  "systemctl --failed" \
  "systemctl --failed"
run_shell "post-processes-totem" "totem mpv/kiosk processes after MPV remaining flags matrix probe" \
  "ps -eo pid=,user=,comm= | awk '\$2 == \"totem\" && (\$3 == \"mpv\" || \$3 ~ /python/) {print \$1 \" \" \$2 \" \" \$3}' || true" \
  "ps -eo pid=,user=,comm= | awk '<sanitized process filter>'"
run_shell "post-journalctl-kernel-critical-filter" "journalctl kernel critical filter after MPV remaining flags matrix probe" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei 'oops|panic|tainted|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|thermal|voltage|fail|error|Bluetooth: hci0' || true" \
  "journalctl -k -b --no-pager --output=short-iso | grep -Ei '<critical-filter>' || true"

append_summary_metric "archive" "$ARCHIVE"
finish_archive
