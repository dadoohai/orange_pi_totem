#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="$(mktemp -d /tmp/dadooh-launcher-status-smoke.XXXXXX)"
OUT_DIR="/tmp/dadooh-status-test"

cleanup() {
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
export TOTEM_STATUS_AGGREGATOR_TIMEOUT_SEC=1
export TOTEM_STATUS_AGGREGATOR_WARN_INTERVAL_SEC=1
export TOTEM_STATUS_REFRESH_SEC=1
export KIOSKY_CONFIG_RETRY_SEC=1

if "$TOTEM_STATUS_AGGREGATOR" \
  --launcher-status "$SCRIPT_DIR/testdata/status_aggregate/launcher-display-missing.json" \
  --out-dir /tmp >/dev/null 2>&1; then
  printf 'expected /tmp out-dir rejection\n' >&2
  exit 1
fi

# shellcheck disable=SC1091
. "$SCRIPT_DIR/kiosky_service_launcher.sh"

write_status "display_missing" "false"

test -s "$TOTEM_STATUS_OUT_DIR/status.json"
test -s "$TOTEM_STATUS_OUT_DIR/status.svg"

python3 - "$TOTEM_STATUS_OUT_DIR/status.json" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    status = json.load(handle)

assert status["schema_version"] == "totem-status.v0"
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

assert status["schema_version"] == "totem-status.v0"
assert status["state"] == "config_missing"
assert status["display_connected"] is True
assert status["config_state"] == "missing"
assert status["player_state"] == "not_started"
assert status["error_code"] == "CONFIG_MISSING"
PY

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
