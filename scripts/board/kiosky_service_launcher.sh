#!/usr/bin/env bash
set -u

umask 077

CONFIG_PATH="${KIOSKY_CONFIG_PATH:-/data/config/config.json}"
APP_CMD=(/usr/bin/python3 /opt/totem/kiosky-player/kiosk.py --config "$CONFIG_PATH")
RUNTIME_DIR="${KIOSKY_RUNTIME_DIR:-/tmp/kiosky}"
STATE_DIR="${KIOSKY_LAUNCHER_STATE_DIR:-/data/state/kiosky-player}"
STATUS_FILE="${KIOSKY_LAUNCHER_STATUS_FILE:-$STATE_DIR/launcher-status.json}"
FALLBACK_STATUS_FILE="${KIOSKY_LAUNCHER_FALLBACK_STATUS_FILE:-/tmp/kiosky-launcher-status.json}"
TOTEM_STATUS_AGGREGATOR="${TOTEM_STATUS_AGGREGATOR:-/opt/totem/bin/totem_status_aggregate.py}"
TOTEM_STATUS_OUT_DIR="${TOTEM_STATUS_OUT_DIR:-/tmp/dadooh-status}"
TOTEM_PLAYER_STATUS_FILE="${TOTEM_PLAYER_STATUS_FILE:-/tmp/kiosky-status.json}"
TOTEM_STATUS_RENDERER="${TOTEM_STATUS_RENDERER:-/opt/totem/bin/totem_status_renderer.sh}"
TOTEM_STATUS_SVG="${TOTEM_STATUS_SVG:-/tmp/dadooh-status/status.svg}"
TOTEM_STATUS_AGGREGATOR_TIMEOUT_SEC="${TOTEM_STATUS_AGGREGATOR_TIMEOUT_SEC:-2}"
TOTEM_STATUS_REFRESH_SEC="${TOTEM_STATUS_REFRESH_SEC:-5}"
TOTEM_STATUS_RENDERER_STOP_TIMEOUT_SEC="${TOTEM_STATUS_RENDERER_STOP_TIMEOUT_SEC:-3}"
DISPLAY_RETRY_SEC="${KIOSKY_DISPLAY_RETRY_SEC:-5}"
CONFIG_RETRY_SEC="${KIOSKY_CONFIG_RETRY_SEC:-5}"
APP_RESTART_SEC="${KIOSKY_APP_RESTART_SEC:-5}"
DISPLAY_LOG_INTERVAL_SEC="${KIOSKY_DISPLAY_LOG_INTERVAL_SEC:-60}"
STATUS_AGGREGATOR_WARN_INTERVAL_SEC="${TOTEM_STATUS_AGGREGATOR_WARN_INTERVAL_SEC:-60}"
STATUS_RENDERER_WARN_INTERVAL_SEC="${TOTEM_STATUS_RENDERER_WARN_INTERVAL_SEC:-60}"

CHILD_PID=""
SLEEP_PID=""
STATUS_REFRESH_PID=""
STATUS_RENDERER_PID=""
LAST_STATUS_FILE=""
STOP_REQUESTED=0
LAST_DISPLAY_LOG_EPOCH=0
LAST_CONFIG_LOG_EPOCH=0
LAST_STATUS_AGGREGATOR_WARN_EPOCH=0
LAST_STATUS_RENDERER_WARN_EPOCH=0

stamp() {
  date '+%Y-%m-%dT%H:%M:%S%z'
}

log() {
  printf '%s kiosky_service_launcher[%s]: %s\n' "$(stamp)" "$$" "$*"
}

positive_integer_or_default() {
  local value="$1"
  local fallback="$2"

  case "$value" in
    ''|*[!0-9]*|0)
      printf '%s\n' "$fallback"
      ;;
    *)
      printf '%s\n' "$value"
      ;;
  esac
}

DISPLAY_RETRY_SEC="$(positive_integer_or_default "$DISPLAY_RETRY_SEC" 5)"
CONFIG_RETRY_SEC="$(positive_integer_or_default "$CONFIG_RETRY_SEC" 5)"
APP_RESTART_SEC="$(positive_integer_or_default "$APP_RESTART_SEC" 5)"
DISPLAY_LOG_INTERVAL_SEC="$(positive_integer_or_default "$DISPLAY_LOG_INTERVAL_SEC" 60)"
TOTEM_STATUS_AGGREGATOR_TIMEOUT_SEC="$(positive_integer_or_default "$TOTEM_STATUS_AGGREGATOR_TIMEOUT_SEC" 2)"
TOTEM_STATUS_REFRESH_SEC="$(positive_integer_or_default "$TOTEM_STATUS_REFRESH_SEC" 5)"
TOTEM_STATUS_RENDERER_STOP_TIMEOUT_SEC="$(positive_integer_or_default "$TOTEM_STATUS_RENDERER_STOP_TIMEOUT_SEC" 3)"
STATUS_AGGREGATOR_WARN_INTERVAL_SEC="$(positive_integer_or_default "$STATUS_AGGREGATOR_WARN_INTERVAL_SEC" 60)"
STATUS_RENDERER_WARN_INTERVAL_SEC="$(positive_integer_or_default "$STATUS_RENDERER_WARN_INTERVAL_SEC" 60)"

warn_status_aggregator() {
  local message="$1"
  local now_epoch

  now_epoch="$(date +%s)"
  if [ $((now_epoch - LAST_STATUS_AGGREGATOR_WARN_EPOCH)) -ge "$STATUS_AGGREGATOR_WARN_INTERVAL_SEC" ]; then
    log "$message"
    LAST_STATUS_AGGREGATOR_WARN_EPOCH="$now_epoch"
  fi
}

warn_status_renderer() {
  local message="$1"
  local now_epoch

  now_epoch="$(date +%s)"
  if [ $((now_epoch - LAST_STATUS_RENDERER_WARN_EPOCH)) -ge "$STATUS_RENDERER_WARN_INTERVAL_SEC" ]; then
    log "$message"
    LAST_STATUS_RENDERER_WARN_EPOCH="$now_epoch"
  fi
}

process_alive() {
  local pid="$1"
  local state=""

  [ -n "$pid" ] || return 1
  kill -0 "$pid" >/dev/null 2>&1 || return 1

  if [ -r "/proc/$pid/stat" ]; then
    state="$(sed -n 's/^[^)]*) \([^ ]\).*/\1/p' "/proc/$pid/stat" 2>/dev/null || true)"
    if [ "$state" = "Z" ]; then
      return 1
    fi
  fi

  return 0
}

run_status_aggregator() {
  local launcher_status="$1"
  local rc=0

  if [ ! -x "$TOTEM_STATUS_AGGREGATOR" ]; then
    warn_status_aggregator "status_aggregator_unavailable"
    return 0
  fi

  if ! command -v timeout >/dev/null 2>&1; then
    warn_status_aggregator "status_aggregator_timeout_unavailable"
    return 0
  fi

  timeout "$TOTEM_STATUS_AGGREGATOR_TIMEOUT_SEC" "$TOTEM_STATUS_AGGREGATOR" \
    --launcher-status "$launcher_status" \
    --player-status "$TOTEM_PLAYER_STATUS_FILE" \
    --out-dir "$TOTEM_STATUS_OUT_DIR" >/dev/null 2>&1
  rc="$?"

  if [ "$rc" -eq 124 ]; then
    warn_status_aggregator "status_aggregator_timeout"
  elif [ "$rc" -ne 0 ]; then
    warn_status_aggregator "status_aggregator_failed rc=$rc"
  fi

  return 0
}

status_target() {
  local dir

  dir="$(dirname "$STATUS_FILE")"
  if { [ -d "$dir" ] || mkdir -p "$dir" 2>/dev/null; } && [ -w "$dir" ]; then
    printf '%s\n' "$STATUS_FILE"
    return 0
  fi

  dir="$(dirname "$FALLBACK_STATUS_FILE")"
  if { [ -d "$dir" ] || mkdir -p "$dir" 2>/dev/null; } && [ -w "$dir" ]; then
    printf '%s\n' "$FALLBACK_STATUS_FILE"
    return 0
  fi

  return 1
}

write_status() {
  local state="$1"
  local display_connected="$2"
  local exit_code="${3:-}"
  local exit_json="null"
  local target=""
  local dir=""
  local tmp=""

  if [ -n "$exit_code" ]; then
    exit_json="$exit_code"
  fi

  target="$(status_target 2>/dev/null || true)"
  [ -n "$target" ] || return 0
  dir="$(dirname "$target")"
  tmp="$(mktemp "$dir/.launcher-status.XXXXXX" 2>/dev/null || true)"
  [ -n "$tmp" ] || return 0

  {
    printf '{\n'
    printf '  "schema_version": 1,\n'
    printf '  "updated_at": "%s",\n' "$(stamp)"
    printf '  "state": "%s",\n' "$state"
    printf '  "display_connected": %s,\n' "$display_connected"
    printf '  "last_app_exit_code": %s,\n' "$exit_json"
    printf '  "launcher_pid": %s\n' "$$"
    printf '}\n'
  } >"$tmp"

  chmod 0600 "$tmp" 2>/dev/null || true
  if mv "$tmp" "$target" 2>/dev/null; then
    LAST_STATUS_FILE="$target"
    run_status_aggregator "$target"
  else
    rm -f "$tmp"
  fi
}

status_refresh_loop() {
  local launcher_status="$1"
  local child_pid="$2"
  local refresh_sleep_pid=""

  trap 'if [ -n "$refresh_sleep_pid" ] && kill -0 "$refresh_sleep_pid" >/dev/null 2>&1; then kill -TERM "$refresh_sleep_pid" >/dev/null 2>&1 || true; fi; exit 0' TERM INT

  while true; do
    sleep "$TOTEM_STATUS_REFRESH_SEC" &
    refresh_sleep_pid="$!"
    wait "$refresh_sleep_pid" 2>/dev/null || exit 0
    refresh_sleep_pid=""

    if ! kill -0 "$child_pid" >/dev/null 2>&1; then
      exit 0
    fi

    run_status_aggregator "$launcher_status"
  done
}

stop_status_refresh() {
  if [ -n "$STATUS_REFRESH_PID" ] && kill -0 "$STATUS_REFRESH_PID" >/dev/null 2>&1; then
    kill -TERM "$STATUS_REFRESH_PID" >/dev/null 2>&1 || true
    wait "$STATUS_REFRESH_PID" 2>/dev/null || true
  fi

  STATUS_REFRESH_PID=""
}

start_status_refresh() {
  local launcher_status="$1"

  stop_status_refresh

  if [ -z "$launcher_status" ]; then
    return 0
  fi

  status_refresh_loop "$launcher_status" "$CHILD_PID" &
  STATUS_REFRESH_PID="$!"
}

stop_status_renderer() {
  local pid="$STATUS_RENDERER_PID"
  local waited=0

  if [ -z "$pid" ]; then
    return 0
  fi

  if ! process_alive "$pid"; then
    wait "$pid" 2>/dev/null || true
    STATUS_RENDERER_PID=""
    return 0
  fi

  kill -TERM "$pid" >/dev/null 2>&1 || true

  while process_alive "$pid" && [ "$waited" -lt "$TOTEM_STATUS_RENDERER_STOP_TIMEOUT_SEC" ]; do
    sleep 1
    waited=$((waited + 1))
  done

  if process_alive "$pid"; then
    warn_status_renderer "status_renderer_kill pid=$pid"
    kill -KILL "$pid" >/dev/null 2>&1 || true
    sleep 1
  fi

  if process_alive "$pid"; then
    warn_status_renderer "status_renderer_stop_failed pid=$pid"
    return 1
  fi

  wait "$pid" 2>/dev/null || true
  STATUS_RENDERER_PID=""
  return 0
}

start_status_renderer() {
  if ! display_connected; then
    return 0
  fi

  if process_alive "$CHILD_PID"; then
    return 0
  fi

  if [ -n "$STATUS_RENDERER_PID" ]; then
    if process_alive "$STATUS_RENDERER_PID"; then
      return 0
    fi
    wait "$STATUS_RENDERER_PID" 2>/dev/null || true
    STATUS_RENDERER_PID=""
  fi

  if [ ! -r "$TOTEM_STATUS_SVG" ] || [ ! -f "$TOTEM_STATUS_SVG" ]; then
    return 0
  fi

  if [ ! -x "$TOTEM_STATUS_RENDERER" ]; then
    warn_status_renderer "status_renderer_unavailable"
    return 0
  fi

  "$TOTEM_STATUS_RENDERER" "$TOTEM_STATUS_SVG" >/dev/null 2>&1 &
  STATUS_RENDERER_PID="$!"
  log "status_renderer_started pid=$STATUS_RENDERER_PID"
  return 0
}

display_connected() {
  local drm_status
  local value

  for drm_status in /sys/class/drm/*/status; do
    [ -r "$drm_status" ] || continue
    IFS= read -r value <"$drm_status" || value=""
    if [ "$value" = "connected" ]; then
      return 0
    fi
  done

  return 1
}

config_valid() {
  [ -f "$CONFIG_PATH" ] || return 1
  [ -r "$CONFIG_PATH" ] || return 1

  python3 - "$CONFIG_PATH" >/dev/null 2>&1 <<'PY'
import json
import sys

required_non_empty_strings = (
    "api_url",
    "api_key",
    "environment_id",
    "cache_dir",
    "state_dir",
    "status_file",
    "ipc_path",
)

try:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        config = json.load(handle)
except Exception:
    sys.exit(1)

if not isinstance(config, dict):
    sys.exit(1)

for key in required_non_empty_strings:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        sys.exit(1)
PY
}

handle_connected_display() {
  local now_epoch

  if config_valid; then
    run_app_once
    return 0
  fi

  now_epoch="$(date +%s)"
  if [ $((now_epoch - LAST_CONFIG_LOG_EPOCH)) -ge "$DISPLAY_LOG_INTERVAL_SEC" ]; then
    log "config_missing retry_sec=$CONFIG_RETRY_SEC"
    LAST_CONFIG_LOG_EPOCH="$now_epoch"
  fi

  write_status "config_missing" "true"
  start_status_renderer
  sleep_interruptible "$CONFIG_RETRY_SEC"
}

ensure_runtime_dir() {
  if ! mkdir -p "$RUNTIME_DIR" 2>/dev/null; then
    log "runtime_dir_unavailable"
    return 1
  fi

  chmod 0750 "$RUNTIME_DIR" 2>/dev/null || true
  return 0
}

sleep_interruptible() {
  local duration="$1"

  sleep "$duration" &
  SLEEP_PID="$!"
  wait "$SLEEP_PID" 2>/dev/null || true
  SLEEP_PID=""
}

request_stop() {
  STOP_REQUESTED=1
  log "shutdown_requested"

  stop_status_refresh
  stop_status_renderer || true

  if [ -n "$CHILD_PID" ] && kill -0 "$CHILD_PID" >/dev/null 2>&1; then
    kill -TERM "$CHILD_PID" >/dev/null 2>&1 || true
  fi

  if [ -n "$SLEEP_PID" ] && kill -0 "$SLEEP_PID" >/dev/null 2>&1; then
    kill -TERM "$SLEEP_PID" >/dev/null 2>&1 || true
  fi
}

run_app_once() {
  local rc=0

  if ! stop_status_renderer; then
    log "status_renderer_stop_failed refusing_start_app"
    write_status "app_exited" "true" "125"
    sleep_interruptible "$APP_RESTART_SEC"
    return 0
  fi

  ensure_runtime_dir || true
  write_status "starting" "true"
  log "display_connected starting_app"

  "${APP_CMD[@]}" &
  CHILD_PID="$!"
  write_status "running" "true"
  start_status_refresh "$LAST_STATUS_FILE"

  wait "$CHILD_PID"
  rc="$?"
  stop_status_refresh
  CHILD_PID=""

  if [ "$STOP_REQUESTED" -ne 0 ]; then
    write_status "stopped" "true" "$rc"
    exit 0
  fi

  log "app_exited exit_code=$rc"
  write_status "app_exited" "true" "$rc"
  sleep_interruptible "$APP_RESTART_SEC"
}

main() {
  local now_epoch

  trap request_stop TERM INT

  log "launcher_started uid=$(id -u) user=$(id -un 2>/dev/null || printf unknown)"
  write_status "starting" "false"

  while true; do
    if [ "$STOP_REQUESTED" -ne 0 ]; then
      write_status "stopped" "false"
      exit 0
    fi

    if display_connected; then
      handle_connected_display
      continue
    fi

    if ! stop_status_renderer; then
      warn_status_renderer "status_renderer_stop_failed display_missing"
    fi

    now_epoch="$(date +%s)"
    if [ $((now_epoch - LAST_DISPLAY_LOG_EPOCH)) -ge "$DISPLAY_LOG_INTERVAL_SEC" ]; then
      log "display_missing retry_sec=$DISPLAY_RETRY_SEC"
      LAST_DISPLAY_LOG_EPOCH="$now_epoch"
    fi

    write_status "display_missing" "false"
    sleep_interruptible "$DISPLAY_RETRY_SEC"
  done
}

if [ "${KIOSKY_LAUNCHER_SOURCE_ONLY:-0}" != "1" ]; then
  main "$@"
fi
