#!/usr/bin/env bash
set -u
set -o pipefail

umask 077

BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S%z)"
RUN_DIR="$BASE_DIR/stress-light-30m-$TIMESTAMP"
RUN_LOG="$RUN_DIR/run.log"
STRESS_LOG="$RUN_DIR/stress-ng-30m.log"
THERMAL_LOG="$RUN_DIR/thermal-samples.log"
ARCHIVE="$BASE_DIR/stress-light-30m-$TIMESTAMP.tar.gz"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECT_DIAG="${TOTEM_COLLECT_DIAG:-$SCRIPT_DIR/collect_diag.sh}"
THERMAL_PID=""

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

if ! command -v stress-ng >/dev/null 2>&1; then
  echo "ERROR: stress-ng not found." >&2
  echo "Install it manually on the board, in a controlled bench session, with:" >&2
  echo "  apt install --no-upgrade stress-ng" >&2
  exit 127
fi

if [ ! -r "$COLLECT_DIAG" ]; then
  echo "ERROR: collect_diag.sh not found at $COLLECT_DIAG" >&2
  echo "Copy scripts/board/collect_diag.sh next to this script before running stress." >&2
  exit 1
fi

mkdir -p "$RUN_DIR"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" | tee -a "$RUN_LOG"
}

thermal_sample_loop() {
  while :; do
    {
      printf 'timestamp=%s' "$(date '+%Y-%m-%dT%H:%M:%S%z')"

      if uptime_out="$(uptime 2>/dev/null)"; then
        printf ' uptime="%s"' "$uptime_out"
      fi

      if loadavg="$(cat /proc/loadavg 2>/dev/null)"; then
        printf ' loadavg="%s"' "$loadavg"
      fi

      for temp_file in /sys/class/thermal/thermal_zone*/temp; do
        [ -e "$temp_file" ] || continue

        zone_dir="${temp_file%/temp}"
        zone_name="${zone_dir##*/}"
        zone_type=""
        temp_raw=""

        if [ -r "$zone_dir/type" ]; then
          zone_type="$(cat "$zone_dir/type" 2>/dev/null || true)"
        fi

        if [ -r "$temp_file" ]; then
          temp_raw="$(cat "$temp_file" 2>/dev/null || true)"
        fi

        printf ' %s' "$zone_name"
        if [ -n "$zone_type" ]; then
          printf '(%s)' "$zone_type"
        fi
        printf '=%s_millicelsius' "$temp_raw"
      done

      printf '\n'
    } >>"$THERMAL_LOG"

    sleep 5 || break
  done
}

stop_thermal_sampler() {
  if [ -n "$THERMAL_PID" ]; then
    kill "$THERMAL_PID" 2>/dev/null || true
    wait "$THERMAL_PID" 2>/dev/null || true
    THERMAL_PID=""
  fi
}

cleanup() {
  stop_thermal_sampler
}

on_signal() {
  cleanup
  exit 130
}

trap cleanup EXIT
trap on_signal INT TERM

log "stress_light_30m started"
log "run_dir=$RUN_DIR"
log "collect_diag=$COLLECT_DIAG"

log "collecting diagnostics before stress"
diag_before_ts="before-$(date +%Y%m%d-%H%M%S%z)"
TOTEM_DIAG_BASE="$RUN_DIR" TOTEM_DIAG_TIMESTAMP="$diag_before_ts" \
  bash "$COLLECT_DIAG" 2>&1 | tee "$RUN_DIR/diag-before.log"
diag_before_rc=${PIPESTATUS[0]}
if [ "$diag_before_rc" -ne 0 ]; then
  log "diagnostics before stress failed with exit_code=$diag_before_rc"
  exit "$diag_before_rc"
fi

log "running: stress-ng --cpu 4 --vm 1 --vm-bytes 50% --timeout 30m --metrics-brief"
{
  echo "# thermal_samples_version=1"
  echo "# interval_seconds=5"
  echo "# units: thermal zone temperatures are raw millidegrees Celsius from /sys/class/thermal"
} >"$THERMAL_LOG"
thermal_sample_loop &
THERMAL_PID=$!
log "thermal sampling started pid=$THERMAL_PID log=$THERMAL_LOG"
stress-ng --cpu 4 --vm 1 --vm-bytes 50% --timeout 30m --metrics-brief 2>&1 | tee "$STRESS_LOG"
stress_rc=${PIPESTATUS[0]}
stop_thermal_sampler
log "thermal sampling stopped"
log "stress-ng finished with exit_code=$stress_rc"

log "collecting diagnostics after stress"
diag_after_ts="after-$(date +%Y%m%d-%H%M%S%z)"
TOTEM_DIAG_BASE="$RUN_DIR" TOTEM_DIAG_TIMESTAMP="$diag_after_ts" \
  bash "$COLLECT_DIAG" 2>&1 | tee "$RUN_DIR/diag-after.log"
diag_after_rc=${PIPESTATUS[0]}
log "diagnostics after stress finished with exit_code=$diag_after_rc"

if command -v tar >/dev/null 2>&1; then
  tar -C "$BASE_DIR" -czf "$ARCHIVE" "stress-light-30m-$TIMESTAMP"
  tar_rc=$?
  if [ "$tar_rc" -eq 0 ]; then
    log "archive=$ARCHIVE"
  else
    log "failed to create archive=$ARCHIVE exit_code=$tar_rc"
  fi
fi

log "stress_light_30m finished"

if [ "$stress_rc" -ne 0 ]; then
  exit "$stress_rc"
fi

exit "$diag_after_rc"
