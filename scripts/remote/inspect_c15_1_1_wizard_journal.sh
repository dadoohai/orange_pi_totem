#!/usr/bin/env bash
# Deep journal trace around the F10 wizard event reported by operator on
# 2026-05-13. Captures every event that touches kiosky-player.service,
# totem-open-settings.service, totem-settings-trigger.service and the
# update agent.  Sanitizes paths and SHA tails.

set -euo pipefail
REPO_ROOT="${REPO_ROOT:-/home/builder/totem-os/orange_pi_totem}"
BOARD_HOST="${BOARD_HOST:-${1:-}}"
OUT="${OUT:-$REPO_ROOT/.cache/c15-1-1-wizard-journal.out}"
if [[ -z $BOARD_HOST ]]; then echo "BOARD_HOST required" >&2; exit 2; fi
if [[ -z ${TOTEM_BOARD_PASS:-} ]]; then echo "TOTEM_BOARD_PASS required" >&2; exit 2; fi
mkdir -p "$(dirname "$OUT")"
CTL=$(mktemp -u "/tmp/ssh-c15j-XXXXXX")
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
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -S "$CTL" ] && break; sleep 0.5; done
[ -S "$CTL" ] || { echo "ctl missing" >&2; exit 4; }
cleanup() { ssh -o ControlPath="$CTL" -O exit "$BOARD_HOST" 2>/dev/null || true; rm -f "$CTL"; }
trap cleanup EXIT

ssh -o ControlPath="$CTL" "$BOARD_HOST" bash -s <<'REMOTE_EOF' 2>&1 | tee "$OUT"
set -u

echo "=== since boot: all totem-open-settings entries ==="
journalctl -u totem-open-settings.service --no-pager --since "2026-05-12 19:16" 2>/dev/null

echo
echo "=== since boot: all totem-settings-trigger entries ==="
journalctl -u totem-settings-trigger.service --no-pager --since "2026-05-12 19:16" 2>/dev/null | head -200

echo
echo "=== since boot: kiosky-player start/stop/restart events ==="
journalctl -u kiosky-player.service --no-pager --since "2026-05-12 19:16" 2>/dev/null \
  | grep -Ei 'Starting|Started|Stopping|Stopped|Failed|Deactivated|killed|Main process exited|Restart counter|shutdown_requested|consumed|systemd\[1\]:' \
  | head -200

echo
echo "=== since boot: update-agent + related cgroup events ==="
journalctl --no-pager --since "2026-05-12 19:16" 2>/dev/null \
  | grep -E 'totem-update-agent|totem-open-settings|kiosky-player.service|totem_open_settings_session|hdmi_not_free|session-lock|settings_session_already_running' \
  | head -200

echo
echo "=== first 60 lines around 10:03 today ==="
journalctl --no-pager --since "2026-05-13 09:55" --until "2026-05-13 10:10" 2>/dev/null \
  | grep -Ei 'totem|kiosky|wizard|setup|trigger|open-settings|systemctl' \
  | head -150

echo
echo "=== status of cgroups around the event (current) ==="
systemctl status totem-open-settings.service --no-pager 2>/dev/null | head -30
echo "---"
systemctl status kiosky-player.service --no-pager 2>/dev/null | head -30

echo
echo "=== status of open-settings InvocationID for last failure ==="
journalctl --no-pager --since "2026-05-13 10:03" --until "2026-05-13 10:06" 2>/dev/null \
  | grep -E 'INVOCATION_ID|_PID|MESSAGE_ID|UNIT' \
  | head -30
echo
echo "=== systemd verbose for the open-settings unit  ==="
systemctl show totem-open-settings.service --no-pager 2>/dev/null \
  | grep -E '^(Restart|TimeoutStart|TimeoutStop|KillSignal|KillMode|MainPID|ExecMainStatus|ExecMainStartTimestamp|ExecMainExitTimestamp|Result|ConditionResult|AssertResult|StatusErrno|StatusText|NRestarts|InvocationID|ActiveEnterTimestamp|ActiveExitTimestamp|InactiveEnterTimestamp|InactiveExitTimestamp|StateChangeTimestamp|TriggeredBy|ConsistsOf|BoundBy)='
echo

echo "=== /tmp/dadooh-c10-6-2-open-settings/session/splash-setup-status.json (sanitized) ==="
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("/tmp/dadooh-c10-6-2-open-settings/session/splash-setup-status.json")
try:
  s = json.loads(p.read_text())
  for k in sorted(s):
    v = s[k]
    if isinstance(v, (str,int,float,bool,type(None))):
      sv=str(v); sv=sv[:80]+'...' if len(sv)>80 else sv
      print(f"  {k}={sv}")
except Exception as e:
  print(f"  read_error={type(e).__name__}")
PY
echo

echo "=== /tmp/dadooh-c10-6-2-visual-wizard/screens (list only) ==="
ls -la /tmp/dadooh-c10-6-2-visual-wizard/screens/ 2>/dev/null | head -20

echo "=== last-settings context exists? ==="
ls -la /data/state/totem-settings/last-settings.json 2>/dev/null || echo "missing"

echo
echo "=== overlayroot status (why did hotfix survive reboot?) ==="
mount | grep -Ei 'overlay|tmpfs.*opt' | head -10
findmnt /opt/totem 2>/dev/null || true
findmnt / 2>/dev/null || true
cat /proc/cmdline | tr ' ' '\n' | grep -Ei 'overlayroot' || true
echo
echo "=== systemd journal disk usage check (was journal rotated?) ==="
journalctl --disk-usage 2>/dev/null
echo "=== boot id  ==="
cat /proc/sys/kernel/random/boot_id

echo "=== DONE ==="
REMOTE_EOF

echo "captured: $OUT"
