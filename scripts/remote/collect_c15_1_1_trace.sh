#!/usr/bin/env bash
# Collects /tmp/c15-session.trace, screens list, splash status, journal
# summary, and config existence — sanitized — after a wizard test.
set -euo pipefail
REPO_ROOT="${REPO_ROOT:-/home/builder/totem-os/orange_pi_totem}"
BOARD_HOST="${BOARD_HOST:-${1:-}}"
OUT="${OUT:-$REPO_ROOT/.cache/c15-1-1-trace-collect.out}"
[[ -z $BOARD_HOST ]] && { echo "BOARD_HOST required" >&2; exit 2; }
[[ -z ${TOTEM_BOARD_PASS:-} ]] && { echo "TOTEM_BOARD_PASS required" >&2; exit 2; }
mkdir -p "$(dirname "$OUT")"
CTL=$(mktemp -u /tmp/ssh-c15tc-XXXXXX)
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
ssh -o ControlPath="$CTL" "$BOARD_HOST" bash -s <<'REMOTE_EOF' 2>&1 | tee "$OUT"
set -u
echo "=== /tmp/c15-session.trace (full) ==="
if [ -f /tmp/c15-session.trace ]; then
  cat /tmp/c15-session.trace
else
  echo "(trace missing)"
fi
echo
echo "=== wizard screens (names only) ==="
ls /tmp/dadooh-c10-6-2-visual-wizard/screens/ 2>/dev/null | sort | head -30
echo
echo "=== wizard out-dir top-level files (names only) ==="
ls /tmp/dadooh-c10-6-2-visual-wizard/ 2>/dev/null
echo
echo "=== session-status.json (sanitized) ==="
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("/tmp/dadooh-c10-6-2-open-settings/session/session-status.json")
try:
  s = json.loads(p.read_text())
  forbidden = {"private_settings_context_path","private_values","candidate_path","api_url","api_key","environment_id","ssid","wifi"}
  for k in sorted(s):
    if k in forbidden: continue
    v = s[k]
    if isinstance(v, (str,int,float,bool,type(None))):
      sv=str(v); sv=sv[:90]+"..." if len(sv)>90 else sv
      print(f"  {k}={sv}")
    elif isinstance(v, dict):
      keys=sorted(v.keys())
      print(f"  {k}=dict(keys={','.join(keys)[:120]})")
except FileNotFoundError:
  print("  session-status.json missing")
except Exception as e:
  print(f"  read_error={type(e).__name__}")
PY
echo
echo "=== candidate / cancelled status (names only, no values) ==="
for f in config.candidate.json setup-cancelled.json screens-status.json setup-failed.json; do
  p=/tmp/dadooh-c10-6-2-visual-wizard/$f
  if [ -f "$p" ]; then
    python3 - "$p" <<'PY'
import json,pathlib,sys
try:
  d=json.loads(pathlib.Path(sys.argv[1]).read_text())
  if isinstance(d,dict):
    safe=("schema_version","cancelled","cancel_reason","setup_network_step","selected_orientation","selected_rotation_deg","screen","step","status","completed","wifi_kept","wifi_action","writer_called","real_config_read","real_config_written","rotation_deg")
    for k in safe:
      if k in d: print(f"  {sys.argv[1].split('/')[-1]}: {k}={d[k]}")
    print(f"  {sys.argv[1].split('/')[-1]}: total_keys={len(d)}")
except Exception as e:
  print(f"  {sys.argv[1].split('/')[-1]}: read_error={type(e).__name__}")
PY
  else
    echo "  $f: missing"
  fi
done
echo
echo "=== journal: totem-open-settings (last 1h) ==="
journalctl -u totem-open-settings.service --no-pager --since="-1h" 2>/dev/null | tail -30
echo
echo "=== journal: kiosky-player start/stop (last 1h) ==="
journalctl -u kiosky-player.service --no-pager --since="-1h" 2>/dev/null \
  | grep -Ei 'Starting|Started|Stopping|Stopped|Failed|Deactivated|shutdown_requested|consumed' \
  | tail -30
echo
echo "=== /data/config/config.json (non-sensitive only) ==="
python3 - <<'PY'
import json
keys=("rotation_deg","status_file","sync_enabled","preload_next","default_duration_ms","poll_interval_sec","schema_version","appliance_profile","telemetry_enabled")
try:
  with open("/data/config/config.json") as f: c=json.load(f)
  for k in keys:
    if k in c: print(f"  {k}={c[k]}")
  print(f"  total_keys={len(c)}")
except Exception as e:
  print(f"  read_error={type(e).__name__}")
PY
echo
echo "=== /data/state/totem-settings/last-settings.json (timestamp only) ==="
stat -c '%y %a %s bytes' /data/state/totem-settings/last-settings.json 2>/dev/null || echo missing
echo
echo "=== /data/config/backups recent ==="
ls -la /data/config/backups/ 2>/dev/null | head -10
echo
echo "=== /run/totem locks ==="
ls -la /run/totem/ 2>/dev/null
echo "session_lock=$(test -d /run/totem/settings-session.lock && echo present || echo absent)"
echo
echo "=== current foreground VT ==="
fgconsole 2>/dev/null || echo unknown
echo
echo "=== ps state ==="
ps -eo pid,ppid,stat,tty,comm 2>/dev/null \
  | grep -Ei 'mpv|kiosk\.py|wizard|trigger|launcher|setup_visual_wizard' \
  | grep -v grep | head -20
echo "=== DONE ==="
REMOTE_EOF
