#!/usr/bin/env bash
set -u

umask 077

APP_CMD=(/usr/bin/python3 /opt/totem/kiosky-player/kiosk.py --config /data/config/config.json)
RUNTIME_DIR="${KIOSKY_RUNTIME_DIR:-/tmp/kiosky}"
STATE_DIR="${KIOSKY_LAUNCHER_STATE_DIR:-/data/state/kiosky-player}"
STATUS_FILE="${KIOSKY_LAUNCHER_STATUS_FILE:-$STATE_DIR/launcher-status.json}"
FALLBACK_STATUS_FILE="${KIOSKY_LAUNCHER_FALLBACK_STATUS_FILE:-/tmp/kiosky-launcher-status.json}"
TOTEM_STATUS_AGGREGATOR="${TOTEM_STATUS_AGGREGATOR:-/opt/totem/bin/totem_status_aggregate.py}"
TOTEM_STATUS_OUT_DIR="${TOTEM_STATUS_OUT_DIR:-/tmp/dadooh-status}"
TOTEM_PLAYER_STATUS_FILE="${TOTEM_PLAYER_STATUS_FILE:-/tmp/kiosky-status.json}"
DISPLAY_RETRY_SEC="${KIOSKY_DISPLAY_RETRY_SEC:-5}"
APP_RESTART_SEC="${KIOSKY_APP_RESTART_SEC:-5}"
DISPLAY_LOG_INTERVAL_SEC="${KIOSKY_DISPLAY_LOG_INTERVAL_SEC:-60}"
STATUS_AGGREGATOR_WARN_INTERVAL_SEC="${TOTEM_STATUS_AGGREGATOR_WARN_INTERVAL_SEC:-60}"

CHILD_PID=""
SLEEP_PID=""
STOP_REQUESTED=0
LAST_DISPLAY_LOG_EPOCH=0
LAST_STATUS_AGGREGATOR_WARN_EPOCH=0

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
APP_RESTART_SEC="$(positive_integer_or_default "$APP_RESTART_SEC" 5)"
DISPLAY_LOG_INTERVAL_SEC="$(positive_integer_or_default "$DISPLAY_LOG_INTERVAL_SEC" 60)"
STATUS_AGGREGATOR_WARN_INTERVAL_SEC="$(positive_integer_or_default "$STATUS_AGGREGATOR_WARN_INTERVAL_SEC" 60)"

warn_status_aggregator() {
  local message="$1"
  local now_epoch

  now_epoch="$(date +%s)"
  if [ $((now_epoch - LAST_STATUS_AGGREGATOR_WARN_EPOCH)) -ge "$STATUS_AGGREGATOR_WARN_INTERVAL_SEC" ]; then
    log "$message"
    LAST_STATUS_AGGREGATOR_WARN_EPOCH="$now_epoch"
  fi
}

run_status_aggregator() {
  local launcher_status="$1"
  local rc=0

  if [ ! -x "$TOTEM_STATUS_AGGREGATOR" ]; then
    warn_status_aggregator "status_aggregator_unavailable"
    return 0
  fi

  "$TOTEM_STATUS_AGGREGATOR" \
    --launcher-status "$launcher_status" \
    --player-status "$TOTEM_PLAYER_STATUS_FILE" \
    --out-dir "$TOTEM_STATUS_OUT_DIR" >/dev/null 2>&1
  rc="$?"

  if [ "$rc" -ne 0 ]; then
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
    run_status_aggregator "$target"
  else
    rm -f "$tmp"
  fi
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

  if [ -n "$CHILD_PID" ] && kill -0 "$CHILD_PID" >/dev/null 2>&1; then
    kill -TERM "$CHILD_PID" >/dev/null 2>&1 || true
  fi

  if [ -n "$SLEEP_PID" ] && kill -0 "$SLEEP_PID" >/dev/null 2>&1; then
    kill -TERM "$SLEEP_PID" >/dev/null 2>&1 || true
  fi
}

run_app_once() {
  local rc=0

  ensure_runtime_dir || true
  write_status "starting" "true"
  log "display_connected starting_app"

  "${APP_CMD[@]}" &
  CHILD_PID="$!"
  write_status "running" "true"

  wait "$CHILD_PID"
  rc="$?"
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
      run_app_once
      continue
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
