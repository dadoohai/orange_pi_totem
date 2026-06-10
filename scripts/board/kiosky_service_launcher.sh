#!/usr/bin/env bash
set -u

umask 077

CONFIG_PATH="${KIOSKY_CONFIG_PATH:-/data/config/config.json}"
KIOSKY_APP_DIR="${KIOSKY_APP_DIR:-/opt/totem/kiosky-player}"
# C18 baseline guard: the effective config must not lower HW decode by pointing
# mpv_path at a non-wrapper binary. Reuse the contract validator shipped in the
# image; the inline fallback in config_valid() keeps this fail-closed if the
# validator is absent. See docs/UPDATE_CONTRACT.md (Contrato De Config C18).
TOTEM_CONFIG_CONTRACT_VALIDATOR="${TOTEM_CONFIG_CONTRACT_VALIDATOR:-/opt/totem/bin/totem_config_contract_validate.py}"
TOTEM_C18_HWDECODE_WRAPPER="${TOTEM_C18_HWDECODE_WRAPPER:-/opt/totem/bin/totem-mpv-hwdecode}"
APP_CMD=(/usr/bin/python3 "$KIOSKY_APP_DIR/kiosk.py" --config "$CONFIG_PATH")
RUNTIME_DIR="${KIOSKY_RUNTIME_DIR:-/tmp/kiosky}"
STATE_DIR="${KIOSKY_LAUNCHER_STATE_DIR:-/data/state/kiosky-player}"
STATUS_FILE="${KIOSKY_LAUNCHER_STATUS_FILE:-$STATE_DIR/launcher-status.json}"
FALLBACK_STATUS_FILE="${KIOSKY_LAUNCHER_FALLBACK_STATUS_FILE:-/tmp/kiosky-launcher-status.json}"
TOTEM_STATUS_AGGREGATOR="${TOTEM_STATUS_AGGREGATOR:-/opt/totem/bin/totem_status_aggregate.py}"
TOTEM_STATUS_OUT_DIR="${TOTEM_STATUS_OUT_DIR:-/tmp/dadooh-status}"
TOTEM_PLAYER_STATUS_FILE="${TOTEM_PLAYER_STATUS_FILE:-/tmp/kiosky-status.json}"
TOTEM_STATUS_RENDERER="${TOTEM_STATUS_RENDERER:-/opt/totem/bin/totem_status_renderer.sh}"
TOTEM_STATUS_SVG="${TOTEM_STATUS_SVG:-/tmp/dadooh-status/status.svg}"
TOTEM_VISUAL_SPLASH="${TOTEM_VISUAL_SPLASH:-/opt/totem/bin/totem_visual_splash.py}"
TOTEM_PLAYER_SPLASH_SKIP_FILE="${TOTEM_PLAYER_SPLASH_SKIP_FILE:-/tmp/kiosky/player-splash-rendered}"
TOTEM_SETTINGS_SESSION_LOCK="${TOTEM_SETTINGS_SESSION_LOCK:-/run/totem/settings-session.lock}"
TOTEM_C17_4_FIRSTBOOT_TRACE_DIR="${TOTEM_C17_4_FIRSTBOOT_TRACE_DIR:-/data/state/totem-debug/c17-4-firstboot}"
TOTEM_SETUP_LOCAL_ENABLED="${TOTEM_SETUP_LOCAL_ENABLED:-0}"
TOTEM_SETUP_LOCAL_AUTORUN_CONFIG_MISSING="${TOTEM_SETUP_LOCAL_AUTORUN_CONFIG_MISSING:-0}"
TOTEM_SETUP_LOCAL_TRIGGER_FILE="${TOTEM_SETUP_LOCAL_TRIGGER_FILE:-/tmp/dadooh-setup-local.request}"
TOTEM_SETUP_LOCAL_WIZARD="${TOTEM_SETUP_LOCAL_WIZARD:-/opt/totem/bin/totem_setup_local_wizard.py}"
TOTEM_SETUP_LOCAL_OUT_DIR="${TOTEM_SETUP_LOCAL_OUT_DIR:-/tmp/dadooh-c9-4-setup-product-v0}"
TOTEM_SETUP_LOCAL_CANDIDATE_FILE="${TOTEM_SETUP_LOCAL_CANDIDATE_FILE:-config.candidate.json}"
TOTEM_SETUP_LOCAL_TTY="${TOTEM_SETUP_LOCAL_TTY:-2}"
TOTEM_SETUP_LOCAL_MAX_RUNS="${TOTEM_SETUP_LOCAL_MAX_RUNS:-1}"
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
LAST_SETTINGS_LOCK_LOG_EPOCH=0
LAST_SPLASH_MODE=""
SETUP_LOCAL_RUN_COUNT=0

stamp() {
  date '+%Y-%m-%dT%H:%M:%S%z'
}

log() {
  printf '%s kiosky_service_launcher[%s]: %s\n' "$(stamp)" "$$" "$*"
}

c17_4_trace() {
  local event="$1"
  local root="$TOTEM_C17_4_FIRSTBOOT_TRACE_DIR"
  local lock_state="absent"
  local uptime_value="unknown"

  [ -e "$TOTEM_SETTINGS_SESSION_LOCK" ] && lock_state="present"
  uptime_value="$(awk '{print int($1)}' /proc/uptime 2>/dev/null || printf unknown)"
  if ! mkdir -p "$root" 2>/dev/null; then
    root="/run/totem/c17-4-firstboot"
    mkdir -p "$root" 2>/dev/null || return 0
  fi
  chmod 700 "$root" 2>/dev/null || true
  printf '%s uptime=%s pid=%d component=kiosky_service_launcher event=%s session_lock=%s renderer_pid=%s child_pid=%s\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$uptime_value" "$$" "$event" "$lock_state" "${STATUS_RENDERER_PID:-none}" "${CHILD_PID:-none}" \
    >> "$root/events.log" 2>/dev/null || true
  case "$root" in
    /data/*) sync "$root/events.log" >/dev/null 2>&1 || true ;;
  esac
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
TOTEM_SETUP_LOCAL_TTY="$(positive_integer_or_default "$TOTEM_SETUP_LOCAL_TTY" 2)"
TOTEM_SETUP_LOCAL_MAX_RUNS="$(positive_integer_or_default "$TOTEM_SETUP_LOCAL_MAX_RUNS" 1)"
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

settings_session_active() {
  [ -e "$TOTEM_SETTINGS_SESSION_LOCK" ]
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
  if settings_session_active; then
    c17_4_trace "status_renderer_blocked_by_settings_session"
    return 0
  fi

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

show_public_splash() {
  local mode="$1"

  if settings_session_active; then
    c17_4_trace "public_splash_blocked_by_settings_session mode=$mode"
    return 0
  fi

  if [ "$mode" = "player" ] && [ -f "$TOTEM_PLAYER_SPLASH_SKIP_FILE" ]; then
    rm -f "$TOTEM_PLAYER_SPLASH_SKIP_FILE" 2>/dev/null || true
    LAST_SPLASH_MODE="player"
    return 0
  fi

  if [ "$LAST_SPLASH_MODE" = "$mode" ]; then
    return 0
  fi

  if ! display_connected; then
    return 0
  fi

  if [ ! -x "$TOTEM_VISUAL_SPLASH" ]; then
    return 0
  fi

  "$TOTEM_VISUAL_SPLASH" "$mode" --status-out "/tmp/dadooh-splash/launcher-${mode}/status.json" >/dev/null 2>&1 || true
  LAST_SPLASH_MODE="$mode"
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

  python3 - "$CONFIG_PATH" "$TOTEM_CONFIG_CONTRACT_VALIDATOR" "$TOTEM_C18_HWDECODE_WRAPPER" >/dev/null 2>&1 <<'PY'
import importlib.util
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
    # Unreadable / invalid config -> fail closed (do not start the player).
    sys.exit(1)

if not isinstance(config, dict):
    sys.exit(1)

for key in required_non_empty_strings:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        sys.exit(1)


def _c18_mpv_path_violation(cfg, validator_path, wrapper):
    """Return True if the effective mpv_path lowers the C18 HW-decode baseline.

    Reuses validate_c18_mpv_path_contract from the shipped config-contract
    validator (the same logic the config WRITER enforces). If that module
    cannot be loaded for any reason, fall back to the equivalent inline rule
    so this guard stays fail-closed.
    """
    try:
        spec = importlib.util.spec_from_file_location(
            "totem_config_contract_validate", validator_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("validator_unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _finding, invalid = module.validate_c18_mpv_path_contract(cfg)
        return invalid is not None
    except Exception:
        # Inline mirror of validate_c18_mpv_path_contract: absent is OK,
        # otherwise it must be exactly the C18 HW-decode wrapper.
        if "mpv_path" not in cfg:
            return False
        value = cfg.get("mpv_path")
        return not (isinstance(value, str) and value == wrapper)


if _c18_mpv_path_violation(config, sys.argv[2], sys.argv[3]):
    sys.exit(1)
PY
}

setup_local_enabled() {
  [ "$TOTEM_SETUP_LOCAL_ENABLED" = "1" ] || return 1
  [ "$SETUP_LOCAL_RUN_COUNT" -lt "$TOTEM_SETUP_LOCAL_MAX_RUNS" ] || return 1
  return 0
}

setup_local_requested() {
  setup_local_enabled || return 1

  if [ "$TOTEM_SETUP_LOCAL_AUTORUN_CONFIG_MISSING" = "1" ]; then
    return 0
  fi

  case "$TOTEM_SETUP_LOCAL_TRIGGER_FILE" in
    /tmp/*)
      [ -f "$TOTEM_SETUP_LOCAL_TRIGGER_FILE" ] && return 0
      ;;
  esac

  return 1
}

consume_setup_local_trigger() {
  case "$TOTEM_SETUP_LOCAL_TRIGGER_FILE" in
    /tmp/*)
      rm -f "$TOTEM_SETUP_LOCAL_TRIGGER_FILE" 2>/dev/null || true
      ;;
  esac
}

setup_local_candidate_ready() {
  case "$TOTEM_SETUP_LOCAL_CANDIDATE_FILE" in
    ''|*/*)
      return 1
      ;;
  esac

  if [ -f "$TOTEM_SETUP_LOCAL_OUT_DIR/$TOTEM_SETUP_LOCAL_CANDIDATE_FILE" ]; then
    return 0
  fi

  # Compatibility with the experimental C9.3 wizard artifact name.
  [ -f "$TOTEM_SETUP_LOCAL_OUT_DIR/candidate-config.json" ]
}

setup_local_cancelled() {
  [ -f "$TOTEM_SETUP_LOCAL_OUT_DIR/setup-cancelled.json" ]
}

prepare_setup_local_outcome_dir() {
  case "$TOTEM_SETUP_LOCAL_OUT_DIR" in
    /tmp/*)
      case "$TOTEM_SETUP_LOCAL_CANDIDATE_FILE" in
        ''|*/*)
          ;;
        *)
          rm -f "$TOTEM_SETUP_LOCAL_OUT_DIR/$TOTEM_SETUP_LOCAL_CANDIDATE_FILE" 2>/dev/null || true
          ;;
      esac
      rm -f \
        "$TOTEM_SETUP_LOCAL_OUT_DIR/candidate-config.json" \
        "$TOTEM_SETUP_LOCAL_OUT_DIR/setup-cancelled.json" \
        "$TOTEM_SETUP_LOCAL_OUT_DIR/setup-status.json" \
        "$TOTEM_SETUP_LOCAL_OUT_DIR/summary.txt" \
        2>/dev/null || true
      ;;
  esac
}

run_setup_local_once() {
  local rc=0

  SETUP_LOCAL_RUN_COUNT=$((SETUP_LOCAL_RUN_COUNT + 1))
  consume_setup_local_trigger
  prepare_setup_local_outcome_dir

  write_status "setup_local_requested" "true"
  log "setup_local_requested tty=$TOTEM_SETUP_LOCAL_TTY"

  if ! stop_status_renderer; then
    log "setup_local_failed reason=renderer_stop_failed"
    write_status "setup_local_failed" "true" "126"
    return 0
  fi

  if process_alive "$CHILD_PID"; then
    log "setup_local_failed reason=player_conflict"
    write_status "setup_local_failed" "true" "125"
    return 0
  fi

  if [ ! -r "$TOTEM_SETUP_LOCAL_WIZARD" ]; then
    log "setup_local_failed reason=wizard_unavailable"
    write_status "setup_local_failed" "true" "127"
    return 0
  fi

  if ! command -v openvt >/dev/null 2>&1; then
    log "setup_local_failed reason=openvt_unavailable"
    write_status "setup_local_failed" "true" "127"
    return 0
  fi

  write_status "setup_local_starting" "true"
  log "setup_local_starting"
  write_status "setup_local_running" "true"

  openvt -c "$TOTEM_SETUP_LOCAL_TTY" -s -f -w -- \
    env TERM=linux /usr/bin/python3 "$TOTEM_SETUP_LOCAL_WIZARD" \
      --out-dir "$TOTEM_SETUP_LOCAL_OUT_DIR"
  rc="$?"

  if [ "$rc" -eq 0 ] && setup_local_candidate_ready; then
    log "setup_candidate_ready"
    write_status "setup_candidate_ready" "true" "0"
    return 0
  fi

  if [ "$rc" -eq 130 ] || setup_local_cancelled; then
    log "setup_local_cancelled"
    write_status "setup_local_cancelled" "true" "130"
    return 0
  fi

  log "setup_local_failed rc=$rc"
  write_status "setup_local_failed" "true" "$rc"
  return 0
}

handle_connected_display() {
  local now_epoch

  if settings_session_active; then
    if ! stop_status_renderer; then
      warn_status_renderer "status_renderer_stop_failed settings_session_active"
    fi
    now_epoch="$(date +%s)"
    if [ $((now_epoch - LAST_SETTINGS_LOCK_LOG_EPOCH)) -ge "$DISPLAY_LOG_INTERVAL_SEC" ]; then
      log "settings_session_active visual_surface_reserved"
      c17_4_trace "launcher_paused_for_settings_session"
      LAST_SETTINGS_LOCK_LOG_EPOCH="$now_epoch"
    fi
    sleep_interruptible "$CONFIG_RETRY_SEC"
    return 0
  fi

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
  show_public_splash "config_pending"

  if setup_local_requested; then
    run_setup_local_once
    if config_valid; then
      run_app_once
      return 0
    fi
    start_status_renderer
    sleep_interruptible "$CONFIG_RETRY_SEC"
    return 0
  fi

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

wait_child_after_stop() {
  local pid="$1"
  local rc="$2"

  if [ -z "$pid" ]; then
    return "$rc"
  fi

  if [ "$STOP_REQUESTED" -ne 0 ] && process_alive "$pid"; then
    log "shutdown_waiting_for_child pid=$pid"
    while process_alive "$pid"; do
      wait "$pid" 2>/dev/null
      rc="$?"
      if process_alive "$pid"; then
        sleep 0.2
      fi
    done
    log "shutdown_child_exited pid=$pid rc=$rc"
  fi

  return "$rc"
}

run_app_once() {
  local rc=0
  local child_pid=""

  if settings_session_active; then
    c17_4_trace "app_start_blocked_by_settings_session"
    sleep_interruptible "$APP_RESTART_SEC"
    return 0
  fi

  if ! stop_status_renderer; then
    log "status_renderer_stop_failed refusing_start_app"
    write_status "app_exited" "true" "125"
    sleep_interruptible "$APP_RESTART_SEC"
    return 0
  fi

  ensure_runtime_dir || true
  show_public_splash "player"
  write_status "starting" "true"
  log "display_connected starting_app"

  "${APP_CMD[@]}" &
  CHILD_PID="$!"
  child_pid="$CHILD_PID"
  LAST_SPLASH_MODE="player_running"
  write_status "running" "true"
  start_status_refresh "$LAST_STATUS_FILE"

  wait "$child_pid"
  rc="$?"
  wait_child_after_stop "$child_pid" "$rc"
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
  c17_4_trace "launcher_start"
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
