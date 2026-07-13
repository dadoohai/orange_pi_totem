#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="$(mktemp -d /tmp/dadooh-launcher-status-smoke.XXXXXX)"
OUT_DIR="/tmp/dadooh-status-test"

cleanup() {
  if [ -n "${STATUS_RENDERER_PID:-}" ]; then
    builtin kill -KILL "$STATUS_RENDERER_PID" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_DIR"
  rm -rf "$OUT_DIR"
}
trap cleanup EXIT
rm -rf "$OUT_DIR"

export KIOSKY_LAUNCHER_SOURCE_ONLY=1
export KIOSKY_LAUNCHER_STATUS_FILE="$TMP_DIR/state/launcher-status.json"
export KIOSKY_LAUNCHER_FALLBACK_STATUS_FILE="$TMP_DIR/fallback/launcher-status.json"
export KIOSKY_CONFIG_PATH="$TMP_DIR/missing-config.json"
export TOTEM_STATUS_AGGREGATOR="$SCRIPT_DIR/totem_status_aggregate.py"
export TOTEM_STATUS_OUT_DIR="$OUT_DIR"
export TOTEM_PLAYER_STATUS_FILE="$TMP_DIR/kiosky-status.json"
export TOTEM_STATUS_RENDERER="$TMP_DIR/fake-status-renderer"
export TOTEM_STATUS_SVG="$OUT_DIR/status.svg"
export TOTEM_RENDERER_FAKE_LOG="$TMP_DIR/status-renderer.log"
export TOTEM_RENDERER_FAKE_ACTIVE="$TMP_DIR/status-renderer.active"
export TOTEM_STATUS_AGGREGATOR_TIMEOUT_SEC=1
export TOTEM_STATUS_AGGREGATOR_WARN_INTERVAL_SEC=1
export TOTEM_STATUS_RENDERER_WARN_INTERVAL_SEC=1
export TOTEM_STATUS_REFRESH_SEC=1
export TOTEM_STATUS_RENDERER_STOP_TIMEOUT_SEC=1
export KIOSKY_CONFIG_RETRY_SEC=1

cat >"$TOTEM_STATUS_RENDERER" <<'SH'
#!/usr/bin/env sh
printf 'start pid=%s\n' "$$" >>"$TOTEM_RENDERER_FAKE_LOG"
touch "$TOTEM_RENDERER_FAKE_ACTIVE"
trap 'printf "term pid=%s\n" "$$" >>"$TOTEM_RENDERER_FAKE_LOG"; rm -f "$TOTEM_RENDERER_FAKE_ACTIVE"; exit 0' TERM INT
while :; do
  sleep 1
done
SH
chmod 0755 "$TOTEM_STATUS_RENDERER"

if "$TOTEM_STATUS_AGGREGATOR" \
  --launcher-status "$SCRIPT_DIR/testdata/status_aggregate/launcher-display-missing.json" \
  --out-dir /tmp >/dev/null 2>&1; then
  printf 'expected /tmp out-dir rejection\n' >&2
  exit 1
fi

# shellcheck disable=SC1091
. "$SCRIPT_DIR/kiosky_service_launcher.sh"

FAKE_DISPLAY_CONNECTED=1
display_connected() {
  [ "$FAKE_DISPLAY_CONNECTED" = "1" ]
}

reset_launcher_state() {
  CHILD_PID=""
  SLEEP_PID=""
  STATUS_REFRESH_PID=""
  STATUS_RENDERER_PID=""
  LAST_STATUS_FILE=""
  STOP_REQUESTED=0
  LAST_STATUS_AGGREGATOR_WARN_EPOCH=0
  LAST_STATUS_RENDERER_WARN_EPOCH=0
}

write_valid_config() {
  cat >"$KIOSKY_CONFIG_PATH" <<JSON
{
  "api_url": "https://api.example.invalid/search",
  "api_key": "replace-with-api-key",
  "environment_id": "replace-with-environment-id",
  "cache_dir": "$TMP_DIR/media",
  "state_dir": "$TMP_DIR/state-app",
  "status_file": "$TMP_DIR/kiosky-status.json",
  "ipc_path": "$TMP_DIR/mpv.sock"
}
JSON
}

renderer_start_count() {
  grep -c '^start ' "$TOTEM_RENDERER_FAKE_LOG" 2>/dev/null || true
}

write_status "display_missing" "false"

test -s "$TOTEM_STATUS_OUT_DIR/status.json"
test -s "$TOTEM_STATUS_OUT_DIR/status.svg"

python3 - "$TOTEM_STATUS_OUT_DIR/status.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    status = json.load(handle)

assert status["schema_version"] == "totem-status.v1"
assert status["state"] == "display_missing"
assert status["display_connected"] is False
assert status["error_code"] == "DISPLAY_MISSING"
PY

app_called="$TMP_DIR/app-called"
APP_CMD=(/bin/sh -c "touch '$app_called'")

handle_connected_display >/dev/null

if [ -e "$app_called" ]; then
  printf 'expected missing config to prevent app start\n' >&2
  exit 1
fi

python3 - "$TOTEM_STATUS_OUT_DIR/status.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    status = json.load(handle)

assert status["schema_version"] == "totem-status.v1"
assert status["state"] == "config_missing"
assert status["display_connected"] is True
assert status["config_state"] == "missing"
assert status["player_state"] == "not_started"
assert status["error_code"] == "CONFIG_MISSING"
PY

sleep 1
if [ "$(renderer_start_count)" -ne 1 ]; then
  printf 'expected renderer fake to start in config_missing\n' >&2
  exit 1
fi

start_status_renderer
if [ "$(renderer_start_count)" -ne 1 ]; then
  printf 'expected renderer fake not to duplicate\n' >&2
  exit 1
fi

TOTEM_STATUS_AGGREGATOR="$TMP_DIR/missing-aggregator-hot"
write_status "config_missing" "true" >/dev/null
if [ -e "$TOTEM_RENDERER_FAKE_ACTIVE" ]; then
  printf 'expected active stale renderer to stop when aggregation later fails\n' >&2
  exit 1
fi
if [ -e "$TOTEM_STATUS_SVG" ] || [ -e "$TOTEM_STATUS_JSON" ]; then
  printf 'expected active stale status artifacts to be invalidated when aggregation later fails\n' >&2
  exit 1
fi

TOTEM_STATUS_AGGREGATOR="$SCRIPT_DIR/totem_status_aggregate.py"
write_status "config_missing" "true" >/dev/null
start_status_renderer
if [ "$(renderer_start_count)" -ne 2 ]; then
  printf 'expected renderer fake to recover after aggregation returns\n' >&2
  exit 1
fi

stop_status_renderer
if [ -e "$TOTEM_RENDERER_FAKE_ACTIVE" ]; then
  printf 'expected renderer fake to stop cleanly\n' >&2
  exit 1
fi

: >"$TOTEM_RENDERER_FAKE_LOG"
FAKE_DISPLAY_CONNECTED=0
write_status "display_missing" "false"
start_status_renderer || true
sleep 1
if [ "$(renderer_start_count)" -ne 0 ]; then
  printf 'expected renderer fake not to start when display is missing\n' >&2
  exit 1
fi

FAKE_DISPLAY_CONNECTED=1
rm -f "$KIOSKY_CONFIG_PATH"
handle_connected_display >/dev/null
sleep 1
if [ "$(renderer_start_count)" -ne 1 ]; then
  printf 'expected renderer fake to start again for config_missing\n' >&2
  exit 1
fi

write_valid_config
app_after_renderer="$TMP_DIR/app-after-renderer"
APP_CMD=(/bin/sh -c "if [ -e '$TOTEM_RENDERER_FAKE_ACTIVE' ]; then printf 'app_with_renderer\n' >>'$TOTEM_RENDERER_FAKE_LOG'; exit 70; fi; printf 'app\n' >>'$TOTEM_RENDERER_FAKE_LOG'; touch '$app_after_renderer'")
handle_connected_display >/dev/null

if [ ! -e "$app_after_renderer" ]; then
  printf 'expected app fake to start after renderer stop\n' >&2
  exit 1
fi
if grep -q '^app_with_renderer$' "$TOTEM_RENDERER_FAKE_LOG"; then
  printf 'expected app fake not to start while renderer is active\n' >&2
  exit 1
fi

term_line="$(grep -n '^term ' "$TOTEM_RENDERER_FAKE_LOG" | tail -n 1 | cut -d: -f1)"
app_line="$(grep -n '^app$' "$TOTEM_RENDERER_FAKE_LOG" | tail -n 1 | cut -d: -f1)"
if [ -z "$term_line" ] || [ -z "$app_line" ] || [ "$term_line" -ge "$app_line" ]; then
  printf 'expected renderer stop event before app fake start\n' >&2
  exit 1
fi
stop_status_renderer

reset_launcher_state
write_valid_config
unstoppable_pid=424242
STATUS_RENDERER_PID="$unstoppable_pid"
blocked_app="$TMP_DIR/app-blocked-by-renderer"
APP_CMD=(/bin/sh -c "touch '$blocked_app'")
kill() {
  case "${1:-}" in
    -0|-TERM|-KILL)
      if [ "${2:-}" = "$unstoppable_pid" ]; then
        if [ "$1" = "-0" ]; then
          return 0
        fi
        return 1
      fi
      ;;
  esac
  builtin kill "$@"
}
run_app_once >/dev/null
unset -f kill
STATUS_RENDERER_PID=""

if [ -e "$blocked_app" ]; then
  printf 'expected app fake not to start when renderer stop fails\n' >&2
  exit 1
fi

reset_launcher_state
rm -f "$KIOSKY_CONFIG_PATH" "$app_called"
TOTEM_STATUS_RENDERER="$TMP_DIR/missing-renderer"
missing_renderer_output="$(handle_connected_display)"
case "$missing_renderer_output" in
  *status_renderer_unavailable*)
    ;;
  *)
    printf 'expected status_renderer_unavailable warning\n' >&2
    exit 1
    ;;
esac
if [ -e "$app_called" ]; then
  printf 'expected missing renderer not to start app when config is missing\n' >&2
  exit 1
fi

reset_launcher_state
TOTEM_STATUS_RENDERER="$TMP_DIR/fake-status-renderer"
write_valid_config
normal_app="$TMP_DIR/normal-app-called"
APP_CMD=(/bin/sh -c "touch '$normal_app'")
handle_connected_display >/dev/null
if [ ! -e "$normal_app" ]; then
  printf 'expected normal valid config path to call app fake\n' >&2
  exit 1
fi
if [ ! -e "$TOTEM_RENDERER_FAKE_ACTIVE" ]; then
  printf 'expected recovery renderer to cover app retry delay\n' >&2
  exit 1
fi
python3 - "$TOTEM_STATUS_OUT_DIR/status.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    status = json.load(handle)

assert status["state"] == "player_error"
assert status["error_code"] == "PLAYER_EXITED"
PY
stop_status_renderer

TOTEM_STATUS_AGGREGATOR="$TMP_DIR/missing-aggregator"
warning_output="$(write_status "running" "true")"
case "$warning_output" in
  *status_aggregator_unavailable*)
    ;;
  *)
    printf 'expected status_aggregator_unavailable warning\n' >&2
    exit 1
    ;;
esac

test -s "$KIOSKY_LAUNCHER_STATUS_FILE"

reset_launcher_state
: >"$TOTEM_RENDERER_FAKE_LOG"
rm -f "$KIOSKY_CONFIG_PATH"
printf '<svg>stale-player-running</svg>\n' >"$TOTEM_STATUS_SVG"
printf '{"state":"player_running"}\n' >"$TOTEM_STATUS_JSON"
handle_connected_display >/dev/null || true
if [ -e "$TOTEM_RENDERER_FAKE_ACTIVE" ] || [ "$(renderer_start_count)" -ne 0 ]; then
  printf 'expected config-missing path not to render stale status after aggregation failure\n' >&2
  exit 1
fi
if [ -e "$TOTEM_STATUS_SVG" ] || [ -e "$TOTEM_STATUS_JSON" ]; then
  printf 'expected config-missing path to invalidate stale status artifacts\n' >&2
  exit 1
fi

reset_launcher_state
: >"$TOTEM_RENDERER_FAKE_LOG"
write_valid_config
printf '<svg>stale-player-running</svg>\n' >"$TOTEM_STATUS_SVG"
printf '{"state":"player_running"}\n' >"$TOTEM_STATUS_JSON"
APP_CMD=(/bin/true)
APP_RESTART_SEC=1
run_app_once >/dev/null
if [ -e "$TOTEM_RENDERER_FAKE_ACTIVE" ] || [ "$(renderer_start_count)" -ne 0 ]; then
  printf 'expected stale recovery SVG not to start when aggregation fails\n' >&2
  exit 1
fi
if [ -e "$TOTEM_STATUS_SVG" ]; then
  printf 'expected stale recovery SVG to be invalidated when aggregation fails\n' >&2
  exit 1
fi
if [ -e "$TOTEM_STATUS_JSON" ]; then
  printf 'expected stale recovery JSON to be invalidated when aggregation fails\n' >&2
  exit 1
fi

reset_launcher_state
TOTEM_STATUS_AGGREGATOR="$SCRIPT_DIR/totem_status_aggregate.py"
quick_exit_renderer="$TMP_DIR/quick-exit-status-renderer"
cat >"$quick_exit_renderer" <<'SH'
#!/usr/bin/env sh
exit 23
SH
chmod 0755 "$quick_exit_renderer"
TOTEM_STATUS_RENDERER="$quick_exit_renderer"
write_valid_config
printf '<svg>stale-player-error</svg>\n' >"$TOTEM_STATUS_SVG"
APP_CMD=(/bin/true)
APP_RESTART_SEC=1
run_app_once >/dev/null
if [ -n "$STATUS_RENDERER_PID" ]; then
  printf 'expected immediately failed renderer pid to be cleared\n' >&2
  exit 1
fi
if [ -e "$TOTEM_STATUS_SVG" ]; then
  printf 'expected failed recovery renderer not to leave stale status SVG\n' >&2
  exit 1
fi
if [ -e "$TOTEM_STATUS_JSON" ]; then
  printf 'expected failed recovery renderer not to leave stale status JSON\n' >&2
  exit 1
fi

TOTEM_STATUS_RENDERER="$TMP_DIR/fake-status-renderer"

slow_aggregator="$TMP_DIR/slow-aggregator"
cat >"$slow_aggregator" <<'SH'
#!/usr/bin/env sh
sleep 5
SH
chmod 0755 "$slow_aggregator"

TOTEM_STATUS_AGGREGATOR="$slow_aggregator"
LAST_STATUS_AGGREGATOR_WARN_EPOCH=0
timeout_output="$(write_status "running" "true")"
case "$timeout_output" in
  *status_aggregator_timeout*)
    ;;
  *)
    printf 'expected status_aggregator_timeout warning\n' >&2
    exit 1
    ;;
esac

test -s "$KIOSKY_LAUNCHER_STATUS_FILE"

counting_aggregator="$TMP_DIR/counting-aggregator"
counting_log="$TMP_DIR/counting-aggregator.log"
cat >"$counting_aggregator" <<SH
#!/usr/bin/env sh
launcher_status=""
while [ "\$#" -gt 0 ]; do
  case "\$1" in
    --launcher-status)
      launcher_status="\${2:-}"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
state=""
if [ -n "\$launcher_status" ] && [ -r "\$launcher_status" ]; then
  state="\$(sed -n 's/.*"state": "\\([^"]*\\)".*/\\1/p' "\$launcher_status" | head -n 1)"
fi
printf '%s\\n' "\$state" >>"$counting_log"
exit 0
SH
chmod 0755 "$counting_aggregator"

TOTEM_STATUS_AGGREGATOR="$counting_aggregator"
APP_CMD=(/bin/sh -c 'sleep 4')
APP_RESTART_SEC=1
STOP_REQUESTED=0
CHILD_PID=""
STATUS_REFRESH_PID=""
LAST_STATUS_FILE=""

run_app_once >/dev/null

running_aggregations="$(grep -c '^running$' "$counting_log" || true)"
if [ "$running_aggregations" -lt 3 ]; then
  printf 'expected periodic refresh to aggregate running state at least twice after immediate running status\n' >&2
  exit 1
fi

if [ -n "$STATUS_REFRESH_PID" ]; then
  printf 'expected status refresh loop to stop after child exits\n' >&2
  exit 1
fi

aggregations_after_stop="$(wc -l <"$counting_log")"
sleep 2
aggregations_final="$(wc -l <"$counting_log")"
if [ "$aggregations_after_stop" -ne "$aggregations_final" ]; then
  printf 'expected status refresh loop to stop producing calls after child exits\n' >&2
  exit 1
fi

printf 'ok\n'
