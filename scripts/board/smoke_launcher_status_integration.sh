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
export TOTEM_STATUS_AGGREGATOR="$SCRIPT_DIR/totem_status_aggregate.py"
export TOTEM_STATUS_OUT_DIR="$OUT_DIR"
export TOTEM_PLAYER_STATUS_FILE="$TMP_DIR/kiosky-status.json"
export TOTEM_STATUS_AGGREGATOR_TIMEOUT_SEC=1
export TOTEM_STATUS_AGGREGATOR_WARN_INTERVAL_SEC=1

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

printf 'ok\n'
