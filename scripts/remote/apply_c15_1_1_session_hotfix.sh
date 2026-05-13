#!/usr/bin/env bash
# C15.1.1 - Deploy minimal session.sh hotfix to lab board (no reboot, no apt,
# no pip).  Idempotent: replaces /opt/totem/bin/totem_open_settings_session.sh
# with the repo copy.  The next F10 activation picks the new code on its own.
#
# Reads TOTEM_BOARD_PASS from env (never written anywhere).
#
# Note: rootfs uses overlayroot=tmpfs (C12 read-only).  Hotfix lives in the
# tmpfs upper layer and reverts on reboot; persistence requires an image
# rebuild (recorded in C15.1.1 evidence as a follow-up).

set -euo pipefail
REPO_ROOT="${REPO_ROOT:-/home/builder/totem-os/orange_pi_totem}"
BOARD_HOST="${BOARD_HOST:-${1:-}}"
OUT="${OUT:-$REPO_ROOT/.cache/c15-1-1-hotfix.out}"

if [[ -z $BOARD_HOST ]]; then
  echo "Usage: BOARD_HOST=root@<lab-ip> TOTEM_BOARD_PASS=*** $(basename "$0")" >&2
  exit 2
fi
if [[ -z ${TOTEM_BOARD_PASS:-} ]]; then
  echo "TOTEM_BOARD_PASS required in env" >&2
  exit 2
fi
command -v expect >/dev/null || { echo "expect not installed" >&2; exit 2; }

mkdir -p "$(dirname "$OUT")"

LOCAL_SCRIPT="$REPO_ROOT/scripts/board/totem_open_settings_session.sh"
if [ ! -f "$LOCAL_SCRIPT" ]; then
  echo "missing $LOCAL_SCRIPT" >&2
  exit 2
fi

CTL=$(mktemp -u "/tmp/ssh-c15hot-XXXXXX")

expect <<EXPECT_OPEN
log_user 0
set timeout 30
spawn ssh -fN -o ControlMaster=yes -o ControlPath=$CTL -o ControlPersist=300 \
  -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=15 \
  -o LogLevel=ERROR $BOARD_HOST
expect {
  -re "(yes/no|fingerprint)" { send "yes\r"; exp_continue }
  -re "(P|p)assword:" { send "\$env(TOTEM_BOARD_PASS)\r" }
  -re "Permission denied" { puts stderr permission_denied; exit 3 }
  timeout { puts stderr auth_timeout; exit 2 }
}
expect { eof {} timeout { exit 4 } }
EXPECT_OPEN

for _ in 1 2 3 4 5 6 7 8 9 10; do
  [ -S "$CTL" ] && break
  sleep 0.5
done
[ -S "$CTL" ] || { echo "control socket not created" >&2; exit 4; }

cleanup() {
  ssh -o ControlPath="$CTL" -O exit "$BOARD_HOST" 2>/dev/null || true
  rm -f "$CTL" || true
}
trap cleanup EXIT

REMOTE_TARGET="/opt/totem/bin/totem_open_settings_session.sh"

{
  echo "=== c15.1.1 hotfix begin $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
  echo "host=$BOARD_HOST target=$REMOTE_TARGET"

  echo "--- baseline sha256 (before) ---"
  ssh -o ControlPath="$CTL" "$BOARD_HOST" "sha256sum $REMOTE_TARGET 2>&1 || true"

  echo "--- copy new script to /tmp on board ---"
  scp -o ControlPath="$CTL" "$LOCAL_SCRIPT" "$BOARD_HOST:/tmp/c15-1-1-session.sh"

  echo "--- install in place (root tmpfs overlay, no reboot) ---"
  ssh -o ControlPath="$CTL" "$BOARD_HOST" "
    set -e
    install -m 0755 -o root -g root /tmp/c15-1-1-session.sh $REMOTE_TARGET
    rm -f /tmp/c15-1-1-session.sh
    bash -n $REMOTE_TARGET
    echo bash_n_after=ok
    sha256sum $REMOTE_TARGET
    # No service restart needed: session.sh is read on each open-settings start.
    # Trigger keeps running with same daemon (unchanged).
    systemctl is-active totem-settings-trigger.service
    systemctl is-active kiosky-player.service
  "
  echo "=== c15.1.1 hotfix end $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
} 2>&1 | tee "$OUT"

LOCAL_SHA=$(sha256sum "$LOCAL_SCRIPT" | awk '{print $1}')
echo "local_sha256=$LOCAL_SHA"
echo "captured: $OUT"
