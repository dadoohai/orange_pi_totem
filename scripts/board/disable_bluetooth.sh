#!/usr/bin/env bash
set -u

umask 077

BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S%z)"
OUT_DIR="$BASE_DIR/bluetooth-disable-$TIMESTAMP"
ARCHIVE="$BASE_DIR/bluetooth-disable-$TIMESTAMP.tar.gz"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

capture_state() {
  local outfile="$1"

  {
    echo "### date"
    date
    echo
    echo "### unit file"
    systemctl list-unit-files bluetooth.service --no-legend --no-pager 2>&1 || true
    echo
    echo "### is-enabled"
    systemctl is-enabled bluetooth 2>&1 || true
    echo
    echo "### is-active"
    systemctl is-active bluetooth 2>&1 || true
    echo
    echo "### status"
    systemctl status bluetooth --no-pager -l 2>&1 || true
    echo
    echo "### rfkill"
    rfkill list 2>&1 || true
  } >"$outfile"
}

unit_exists() {
  systemctl list-unit-files bluetooth.service --no-legend --no-pager 2>/dev/null |
    grep -q '^bluetooth\.service'
}

capture_state "$OUT_DIR/before.txt"

{
  echo "### action"
  echo "started_at=$(date '+%Y-%m-%dT%H:%M:%S%z')"
  if unit_exists; then
    echo "command=systemctl disable --now bluetooth"
    systemctl disable --now bluetooth
    action_rc=$?
  else
    echo "bluetooth.service not found; nothing to disable."
    action_rc=0
  fi
  echo "exit_code=$action_rc"
  echo "finished_at=$(date '+%Y-%m-%dT%H:%M:%S%z')"
} >"$OUT_DIR/action.txt" 2>&1

capture_state "$OUT_DIR/after.txt"

if command -v tar >/dev/null 2>&1; then
  tar -C "$BASE_DIR" -czf "$ARCHIVE" "bluetooth-disable-$TIMESTAMP"
  tar_rc=$?
  if [ "$tar_rc" -eq 0 ]; then
    echo "Bluetooth state directory: $OUT_DIR"
    echo "Archive: $ARCHIVE"
  else
    echo "ERROR: failed to create archive $ARCHIVE" >&2
    exit "$tar_rc"
  fi
fi

exit "$action_rc"
