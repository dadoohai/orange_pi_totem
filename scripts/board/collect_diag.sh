#!/usr/bin/env bash
set -u

umask 077

BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="${TOTEM_DIAG_TIMESTAMP:-$(date +%Y%m%d-%H%M%S%z)}"
OUT_DIR="$BASE_DIR/$TIMESTAMP"
ARCHIVE="$BASE_DIR/totem-diag-$TIMESTAMP.tar.gz"

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

{
  echo "totem_diag_version=1"
  echo "timestamp=$TIMESTAMP"
  echo "output_dir=$OUT_DIR"
  echo "archive=$ARCHIVE"
  echo "hostname=$(hostname 2>/dev/null || true)"
  echo "created_at=$(stamp)"
} >"$OUT_DIR/manifest.txt"

run_cmd "date" "date.txt" date
run_cmd "uname -a" "uname-a.txt" uname -a
run_cmd "/etc/armbian-release" "etc-armbian-release.txt" cat /etc/armbian-release
run_cmd "apt-mark showhold" "apt-mark-showhold.txt" apt-mark showhold
run_shell "dpkg critical Armbian packages" "dpkg-critical-packages.txt" \
  "dpkg -l | grep -E 'linux-image|linux-dtb|linux-u-boot|armbian-bsp' || true"
run_cmd "/proc/sys/kernel/tainted" "proc-sys-kernel-tainted.txt" cat /proc/sys/kernel/tainted
run_cmd "free -h" "free-h.txt" free -h
run_cmd "df -h" "df-h.txt" df -h
run_cmd "lsblk -f" "lsblk-f.txt" lsblk -f
run_cmd "ip -br addr" "ip-br-addr.txt" ip -br addr
run_cmd "nmcli device status" "nmcli-device-status.txt" nmcli device status
run_cmd "nmcli connection show" "nmcli-connection-show.txt" nmcli connection show
run_cmd "rfkill list" "rfkill-list.txt" rfkill list
run_cmd "systemctl --failed" "systemctl-failed.txt" systemctl --failed
run_cmd "journalctl kernel critical" "journalctl-kernel-critical.txt" \
  journalctl -k -p crit -n 300 --no-pager --output=short-iso
run_cmd "journalctl NetworkManager tail" "journalctl-networkmanager-tail.txt" \
  journalctl -b -u NetworkManager -n 300 --no-pager --output=short-iso

if command -v tar >/dev/null 2>&1; then
  tar -C "$BASE_DIR" -czf "$ARCHIVE" "$TIMESTAMP"
  tar_rc=$?
  if [ "$tar_rc" -eq 0 ]; then
    echo "Diagnostic directory: $OUT_DIR"
    echo "Archive: $ARCHIVE"
  else
    echo "ERROR: failed to create archive $ARCHIVE" >&2
    exit "$tar_rc"
  fi
else
  echo "ERROR: tar not found; diagnostic directory kept at $OUT_DIR" >&2
  exit 127
fi
