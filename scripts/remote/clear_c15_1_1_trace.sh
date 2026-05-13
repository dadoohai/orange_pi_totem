#!/usr/bin/env bash
# Clears /tmp/c15-session.trace on the lab board so the next F10 test starts
# with an empty diagnostic trace.  Reads TOTEM_BOARD_PASS from env, never
# writes it anywhere.
set -euo pipefail
BOARD_HOST="${BOARD_HOST:-${1:-}}"
[[ -z $BOARD_HOST ]] && { echo "BOARD_HOST required" >&2; exit 2; }
[[ -z ${TOTEM_BOARD_PASS:-} ]] && { echo "TOTEM_BOARD_PASS required" >&2; exit 2; }
CTL=$(mktemp -u /tmp/ssh-c15clr-XXXXXX)
expect <<EXPECT_OPEN
log_user 0
set timeout 30
spawn ssh -fN -o ControlMaster=yes -o ControlPath=$CTL -o ControlPersist=300 \
  -o StrictHostKeyChecking=accept-new -o LogLevel=ERROR $BOARD_HOST
expect {
  -re "(yes/no|fingerprint)" { send "yes\r"; exp_continue }
  -re "(P|p)assword:" { send "\$env(TOTEM_BOARD_PASS)\r" }
  -re "Permission denied" { puts stderr permission_denied; exit 3 }
  timeout { puts stderr auth_timeout; exit 2 }
}
expect { eof {} timeout { exit 4 } }
EXPECT_OPEN
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -S "$CTL" ] && break; sleep 0.5; done
[ -S "$CTL" ] || { echo "ctl missing" >&2; exit 4; }
trap 'ssh -o ControlPath="$CTL" -O exit "$BOARD_HOST" 2>/dev/null||true; rm -f "$CTL"' EXIT
ssh -o ControlPath="$CTL" "$BOARD_HOST" 'rm -f /tmp/c15-session.trace; rm -rf /tmp/dadooh-c10-6-2-visual-wizard/screens/*; rm -f /tmp/dadooh-c10-6-2-open-settings/session/*.json; echo "trace cleared at $(date -u +%FT%TZ)"'
