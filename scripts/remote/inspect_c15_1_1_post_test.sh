#!/usr/bin/env bash
# C15.1.1 - Post-test SSH inspection after the operator tried F10.
# Captures hotfix persistence + journal + wizard artifact paths (no
# secrets, no IP/MAC/config.json contents).

set -euo pipefail
REPO_ROOT="${REPO_ROOT:-/home/builder/totem-os/orange_pi_totem}"
BOARD_HOST="${BOARD_HOST:-${1:-}}"
OUT="${OUT:-$REPO_ROOT/.cache/c15-1-1-post-test.out}"

if [[ -z $BOARD_HOST ]]; then
  echo "Usage: BOARD_HOST=root@<lab-ip> TOTEM_BOARD_PASS=*** $(basename "$0")" >&2
  exit 2
fi
if [[ -z ${TOTEM_BOARD_PASS:-} ]]; then
  echo "TOTEM_BOARD_PASS required in env" >&2
  exit 2
fi
mkdir -p "$(dirname "$OUT")"
CTL=$(mktemp -u "/tmp/ssh-c15post-XXXXXX")

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
[ -S "$CTL" ] || { echo "control socket not created" >&2; exit 4; }

cleanup() {
  ssh -o ControlPath="$CTL" -O exit "$BOARD_HOST" 2>/dev/null || true
  rm -f "$CTL" || true
}
trap cleanup EXIT

ssh -o ControlPath="$CTL" "$BOARD_HOST" bash -s <<'REMOTE_EOF' 2>&1 | tee "$OUT"
set -u

echo "=== uptime + image identity ==="
uptime
cat /etc/dadooh/c12-lab-firstboot-mode 2>/dev/null || true
echo
echo "=== hotfix sha256 (expect c4cb256cbd023f99... if applied; ed2a48114edec... if rebooted) ==="
sha256sum /opt/totem/bin/totem_open_settings_session.sh 2>&1
echo "expected_post_hotfix=c4cb256cbd023f99aee1e85b11dcd07c2eba8e28a25174d78cfc85577b2619e3"
echo "expected_pre_hotfix =ed2a48114edeca47464ae2d6b421bbbc0badc753208ab6b98ee97976686edd6a"
echo
echo "=== boot time (was it rebooted?) ==="
who -b
stat -c '%y' /proc/1 2>/dev/null
echo
echo "=== current services ==="
for svc in kiosky-player.service totem-settings-trigger.service totem-open-settings.service totem-update-agent.timer; do
  printf '%-42s active=%-10s\n' "$svc" \
    "$(systemctl is-active "$svc" 2>/dev/null || echo unknown)"
done
echo
echo "=== /run/totem locks ==="
ls -la /run/totem/ 2>/dev/null || echo no /run/totem
echo "session_lock=$(test -d /run/totem/settings-session.lock && echo present || echo absent)"
echo
echo "=== /run/dadooh-settings ==="
ls -la /run/dadooh-settings/ 2>/dev/null | sed -E 's/-> .*/-> SANITIZED/'
echo
echo "=== trigger-status.json ==="
python3 - <<'PY'
import json, pathlib
try:
  s = json.loads(pathlib.Path("/run/dadooh-settings/trigger-status.json").read_text())
  for k in ("status","trigger_type","trigger_detected","request_written","session_lock_active","open_service_active_state","stale_lock_suspected","stale_lock_removed","cooldown_active","open_service_start_attempted","open_service_start_result"):
    if k in s: print(f"  {k}={s[k]}")
except Exception as e:
  print(f"  read_error={type(e).__name__}")
PY
echo
echo "=== open-settings-cleanup-status.json (if any) ==="
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("/run/dadooh-settings/open-settings-cleanup-status.json")
try:
  s = json.loads(p.read_text())
  for k in ("schema_version","reason","cleanup_completed","lock_removed","request_removed","tty_restored","wizard_killed_count","timestamp_utc","updated_at"):
    if k in s: print(f"  {k}={s[k]}")
except Exception as e:
  print(f"  read_error={type(e).__name__}")
PY
echo
echo "=== wizard out dir traces (file names only, no contents) ==="
for d in /tmp/dadooh-c10-6-2-visual-wizard /tmp/dadooh-c10-6-2-open-settings/session /tmp/dadooh-c10-6-2-handoff /tmp/dadooh-c10-6-2-writer /tmp/dadooh-c10-6-2-private; do
  if [ -d "$d" ]; then
    echo "$d:"
    ls -la "$d" 2>/dev/null | sed -E 's/-> .*/-> SANITIZED/' | head -30
  else
    echo "$d=MISSING"
  fi
done
echo
echo "=== session-status.json (sanitized non-sensitive keys) ==="
python3 - <<'PY'
import json, pathlib
for p in (pathlib.Path("/tmp/dadooh-c10-6-2-open-settings/session/session-status.json"),):
  try:
    s = json.loads(p.read_text())
    for k in sorted(s):
      v = s[k]
      if k in ("private_settings_context_path","private_values","candidate_path"):
        continue
      if isinstance(v, (str, int, float, bool, type(None))):
        sv = str(v)
        if len(sv) > 80: sv = sv[:80] + "...TRUNC"
        print(f"  {k}={sv}")
  except Exception as e:
    print(f"  {p.name}: read_error={type(e).__name__}")
PY
echo
echo "=== wizard config.candidate.json keys (just keys; no values) ==="
python3 - <<'PY'
import json, pathlib
for p in (pathlib.Path("/tmp/dadooh-c10-6-2-visual-wizard/config.candidate.json"),
          pathlib.Path("/tmp/dadooh-c10-6-2-visual-wizard/setup-cancelled.json"),
          pathlib.Path("/tmp/dadooh-c10-6-2-visual-wizard/screens-status.json")):
  try:
    s = json.loads(p.read_text())
    keys = sorted(s.keys()) if isinstance(s, dict) else []
    print(f"  {p.name}: keys={','.join(keys)}")
    if isinstance(s, dict):
      for safe_k in ("status","cancelled","cancel_reason","schema_version","completed","screen","step","selected_orientation","selected_network","wifi_kept","wifi_action"):
        if safe_k in s:
          v = s[safe_k]
          if isinstance(v, (str, int, float, bool, type(None))):
            print(f"    {safe_k}={v}")
  except FileNotFoundError:
    print(f"  {p.name}: missing")
  except Exception as e:
    print(f"  {p.name}: read_error={type(e).__name__}")
PY
echo
echo "=== journal: totem-open-settings (last 4h) ==="
journalctl -u totem-open-settings.service --no-pager --since="-4h" -n 60 2>/dev/null | tail -60
echo
echo "=== journal: kiosky-player (last 4h, info+) ==="
journalctl -u kiosky-player.service --no-pager --since="-4h" -n 40 2>/dev/null | tail -40
echo
echo "=== journal: totem-settings-trigger (last 4h) ==="
journalctl -u totem-settings-trigger.service --no-pager --since="-4h" -n 30 2>/dev/null | tail -30
echo
echo "=== journal: systemd errors mentioning totem/kiosky/wizard last 4h ==="
journalctl --no-pager --since="-4h" 2>/dev/null \
  | grep -Ei 'totem|kiosky|wizard|hdmi_not_free|session-lock|openvt|setup-cancel' \
  | grep -vE 'starting Dadooh|Started Dadooh|Stopped Dadooh' \
  | head -40
echo
echo "=== boots since hotfix (uptime sanity) ==="
last reboot 2>/dev/null | head -10 || true
echo
echo "=== ps post-test ==="
ps -eo pid,ppid,stat,tty,comm,args 2>/dev/null \
  | grep -Ei 'mpv|kiosk\.py|wizard|trigger|launcher|open_settings|setup_visual_wizard|setup_writer_handoff|config_writer|status_renderer' \
  | grep -v grep | head -30
echo
echo "=== /data/config/config.json exists? non-sensitive only ==="
if [ -r /data/config/config.json ]; then
  python3 -c '
import json
keys = ("rotation_deg","status_file","sync_enabled","preload_next","default_duration_ms","poll_interval_sec","schema_version")
with open("/data/config/config.json") as f: c=json.load(f)
for k in keys:
  if k in c: print(f"  {k}={c[k]}")
print(f"  total_keys={len(c)}")
'
else
  echo "  config.json not readable"
fi
echo
echo "=== /data/config/backups (recent) ==="
ls -la /data/config/backups/ 2>/dev/null | tail -10 || true
echo
echo "=== DONE ==="
REMOTE_EOF

echo "captured: $OUT"
