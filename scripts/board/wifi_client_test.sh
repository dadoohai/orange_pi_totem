#!/usr/bin/env bash
set -u

umask 077

BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="${TOTEM_DIAG_TIMESTAMP:-$(date +%Y%m%d-%H%M%S%z)}"
OUT_DIR="$BASE_DIR/wifi-client-$TIMESTAMP"
ARCHIVE="$BASE_DIR/wifi-client-$TIMESTAMP.tar.gz"
CONNECTION_NAME="${1:-}"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

stamp() {
  date '+%Y-%m-%dT%H:%M:%S%z'
}

run_cmd() {
  local title="$1"
  local outfile="$2"
  shift 2
  local rc=0

  {
    echo "### $title"
    echo "### started: $(stamp)"
    echo "### command: $*"
    echo
    "$@"
    rc=$?
    echo
    echo "### exit_code: $rc"
    echo "### finished: $(stamp)"
  } >"$OUT_DIR/$outfile" 2>&1
}

run_shell() {
  local title="$1"
  local outfile="$2"
  local command="$3"
  local rc=0

  {
    echo "### $title"
    echo "### started: $(stamp)"
    echo "### command: $command"
    echo
    sh -c "$command"
    rc=$?
    echo
    echo "### exit_code: $rc"
    echo "### finished: $(stamp)"
  } >"$OUT_DIR/$outfile" 2>&1
}

create_archive() {
  if command -v tar >/dev/null 2>&1; then
    tar -C "$BASE_DIR" -czf "$ARCHIVE" "wifi-client-$TIMESTAMP"
    tar_rc=$?
    if [ "$tar_rc" -eq 0 ]; then
      echo "Wi-Fi client test directory: $OUT_DIR"
      echo "Archive: $ARCHIVE"
      echo "WARNING: raw artifacts may contain SSIDs, IPs and connection names."
    else
      echo "ERROR: failed to create archive $ARCHIVE" >&2
      exit "$tar_rc"
    fi
  else
    echo "ERROR: tar not found; Wi-Fi client test kept at $OUT_DIR" >&2
    exit 127
  fi
}

{
  echo "wifi_client_test_version=1"
  echo "timestamp=$TIMESTAMP"
  echo "output_dir=$OUT_DIR"
  echo "archive=$ARCHIVE"
  echo "hostname=$(hostname 2>/dev/null || true)"
  echo "created_at=$(stamp)"
  echo "connection_name=$CONNECTION_NAME"
  echo "warning=raw artifacts may contain SSIDs, IPs and connection names"
  echo "password_policy=script does not request or print Wi-Fi passwords"
  echo "ethernet_policy=script does not disconnect Ethernet"
} >"$OUT_DIR/manifest.txt"

run_cmd "date" "date.txt" date
run_cmd "nmcli device status before" "nmcli-device-status-before.txt" nmcli device status
run_cmd "nmcli connection show" "nmcli-connection-show.txt" nmcli connection show
run_cmd "nmcli radio wifi" "nmcli-radio-wifi.txt" nmcli radio wifi
run_cmd "nmcli device wifi list" "nmcli-device-wifi-list.txt" nmcli device wifi list

if [ -z "$CONNECTION_NAME" ]; then
  run_shell "known Wi-Fi connections" "known-wifi-connections.txt" \
    "nmcli -t -f NAME,TYPE connection show | awk -F: '\$2 == \"802-11-wireless\" || \$2 == \"wifi\" {print \$1}'"
  {
    echo "ERROR: Wi-Fi connection name is required."
    echo
    echo "Known Wi-Fi connections are listed in known-wifi-connections.txt."
    echo "Run again with one existing NetworkManager connection name, for example:"
    echo "  $0 \"<connection-name>\""
    echo
    echo "This script does not create, delete or modify saved connections and does not request Wi-Fi passwords."
  } | tee "$OUT_DIR/instructions.txt" >&2
  create_archive
  exit 64
fi

run_cmd "nmcli connection up Wi-Fi" "nmcli-connection-up.txt" \
  nmcli connection up "$CONNECTION_NAME"
connection_rc="$(
  awk -F': ' '/^### exit_code:/ {code=$2} END {print code}' "$OUT_DIR/nmcli-connection-up.txt"
)"
connection_rc="${connection_rc:-1}"

run_cmd "ip -br addr after" "ip-br-addr-after.txt" ip -br addr
run_cmd "ip route" "ip-route.txt" ip route

if command -v ping >/dev/null 2>&1; then
  run_cmd "ping via wlan0" "ping-wlan0-1.1.1.1.txt" ping -I wlan0 -c 4 1.1.1.1
else
  {
    echo "### ping via wlan0"
    echo "### started: $(stamp)"
    echo
    echo "ping command not found; skipped."
    echo
    echo "### exit_code: 127"
    echo "### finished: $(stamp)"
  } >"$OUT_DIR/ping-wlan0-1.1.1.1.txt"
fi

run_cmd "DNS lookup" "getent-hosts-deb.debian.org.txt" getent hosts deb.debian.org
run_cmd "NetworkManager journal tail" "journalctl-networkmanager-tail.txt" \
  journalctl -b -u NetworkManager -n 300 --no-pager --output=short-iso
run_cmd "nmcli device status after" "nmcli-device-status-after.txt" nmcli device status

create_archive

exit "$connection_rc"
