#!/usr/bin/env bash
# C15.1.1 - Read-only runtime inspection for wizard/F10 + player audit.
#
# Reads TOTEM_BOARD_PASS from env (never written anywhere).  Opens one SSH
# ControlMaster, runs sanitized inspection over the multiplexed channel,
# captures output to .cache/c15-1-1-runtime-audit.out.
#
# Does NOT touch Wi-Fi, NetworkManager, apt, pip, kernel, U-Boot, DTB, BSP,
# or the seed.  Does NOT print SSH password, api_key, api_url,
# environment_id, SSID/Wi-Fi password or config.json contents.

set -euo pipefail
REPO_ROOT="${REPO_ROOT:-/home/builder/totem-os/orange_pi_totem}"
BOARD_HOST="${BOARD_HOST:-${1:-}}"
OUT="${OUT:-$REPO_ROOT/.cache/c15-1-1-runtime-audit.out}"

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

CTL=$(mktemp -u "/tmp/ssh-c15-XXXXXX")

# Open master via expect (handles password prompt + accept-new)
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
expect {
  -re "Permission denied" { puts stderr auth_failed_after_send; exit 3 }
  eof { }
  timeout { puts stderr post_auth_timeout; exit 4 }
}
EXPECT_OPEN

# Wait briefly for socket
for _ in 1 2 3 4 5 6 7 8 9 10; do
  [ -S "$CTL" ] && break
  sleep 0.5
done
if [ ! -S "$CTL" ]; then
  echo "control socket not created at $CTL" >&2
  exit 4
fi

cleanup() {
  ssh -o ControlPath="$CTL" -O exit "$BOARD_HOST" 2>/dev/null || true
  rm -f "$CTL" || true
}
trap cleanup EXIT

# Now run a regular ssh through the master - no password needed
ssh -o ControlPath="$CTL" "$BOARD_HOST" bash -s <<'REMOTE_EOF' 2>&1 | tee "$OUT"
set -u

sanitize() {
  # remove anything that looks like an IPv4 or MAC; keep structure.
  sed -E '
    s/[A-Fa-f0-9]{2}(:[A-Fa-f0-9]{2}){5}/MAC/g;
    s/([0-9]{1,3}\.){3}[0-9]{1,3}/IP/g;
  '
}

echo "=== uptime ==="
uptime
echo
echo "=== uname ==="
uname -a
echo
echo "=== image identity ==="
cat /etc/dadooh/c12-lab-firstboot-mode 2>/dev/null || true
cat /etc/dadooh/c13-homologation-private-seed 2>/dev/null || true
echo
echo "=== unit state (key services) ==="
for svc in \
    kiosky-player.service \
    totem-update-agent.timer \
    totem-update-agent.service \
    totem-settings-trigger.service \
    totem-open-settings.service \
    totem-firstboot-gate.service \
    dadooh-visual-splash.service; do
  printf '%-42s active=%-10s enabled=%-10s\n' "$svc" \
    "$(systemctl is-active "$svc" 2>/dev/null || echo unknown)" \
    "$(systemctl is-enabled "$svc" 2>/dev/null || echo unknown)"
done
echo
echo "=== unit state (getty/serial) ==="
for g in getty@tty1.service getty@tty2.service getty@tty3.service \
         serial-getty@ttyS0.service serial-getty@ttyGS0.service; do
  printf '%-42s active=%-10s enabled=%-10s\n' "$g" \
    "$(systemctl is-active "$g" 2>/dev/null || echo unknown)" \
    "$(systemctl is-enabled "$g" 2>/dev/null || echo unknown)"
done
echo
echo "=== relevant systemd units list ==="
systemctl list-units --type=service --all --no-pager 2>/dev/null \
  | grep -Ei 'totem|dadooh|kiosky|wizard|settings|setup|getty|serial' \
  | head -60 || true
echo
echo "=== systemctl cat kiosky-player.service (+ drop-ins) ==="
systemctl cat kiosky-player.service 2>/dev/null
echo
echo "=== systemctl cat totem-settings-trigger.service ==="
systemctl cat totem-settings-trigger.service 2>/dev/null || echo MISSING
echo
echo "=== systemctl cat totem-open-settings.service ==="
systemctl cat totem-open-settings.service 2>/dev/null || echo MISSING
echo
echo "=== systemctl cat dadooh-visual-splash.service ==="
systemctl cat dadooh-visual-splash.service 2>/dev/null || echo MISSING
echo
echo "=== systemctl cat totem-firstboot-gate.service ==="
systemctl cat totem-firstboot-gate.service 2>/dev/null || echo MISSING
echo
echo "=== getty@tty1 unit ==="
systemctl cat getty@tty1.service 2>/dev/null | head -40 || echo MISSING
echo
echo "=== /proc/cmdline (sanitized) ==="
sanitize </proc/cmdline
echo
echo "=== /dev/tty[0-2] ==="
ls -l /dev/tty0 /dev/tty1 /dev/tty2 2>/dev/null
echo
echo "=== fgconsole / openvt? ==="
command -v fgconsole >/dev/null && { echo "fgconsole=$(fgconsole 2>/dev/null || echo unknown)"; } || echo fgconsole=missing
command -v openvt   >/dev/null && echo openvt=present  || echo openvt=missing
command -v chvt     >/dev/null && echo chvt=present    || echo chvt=missing
command -v setterm  >/dev/null && echo setterm=present || echo setterm=missing
echo
echo "=== who/last (sanitized) ==="
(who 2>/dev/null || true) | sanitize | head -20
echo
echo "=== ps relevant ==="
ps -eo pid,ppid,stat,tty,comm,args 2>/dev/null \
  | grep -Ei 'mpv|kiosk\.py|wizard|settings|trigger|launcher|getty|login|splash|setup|status_renderer|open-settings|update-agent|update-agent' \
  | grep -v 'grep' | head -50
echo
echo "=== /data layout (no content) ==="
for d in /data /data/apps /data/apps/kiosky-player /data/apps/kiosky-player/releases \
         /data/updates /data/updates/incoming /data/logs /data/state \
         /data/state/totem-settings /data/state/kiosky-player /data/config /data/config/backups; do
  if [ -d "$d" ]; then
    printf '%s -> dir (mode=%s)\n' "$d" "$(stat -c '%a' "$d" 2>/dev/null || echo ?)"
  else
    printf '%s -> MISSING\n' "$d"
  fi
done
echo
echo "=== /data/apps/kiosky-player/current ==="
readlink -f /data/apps/kiosky-player/current 2>/dev/null || echo unset
echo
echo "=== seed presence (no content) ==="
stat -c '%a %U:%G %n' /data/state/totem-settings/private-values.seed.json 2>/dev/null \
  || echo seed=MISSING
test -f /data/state/totem-settings/homologation-seed.enabled \
  && echo seed_marker=present || echo seed_marker=MISSING
echo
echo "=== /run lock state ==="
ls -la /run/totem/ 2>/dev/null || echo "no /run/totem"
echo "---"
ls -la /run/dadooh-settings/ 2>/dev/null | sed -E 's/-> .*$/-> SANITIZED/' || echo "no /run/dadooh-settings"
echo "---"
echo "session_lock_dir_exists=$(test -d /run/totem/settings-session.lock && echo true || echo false)"
echo "session_lock_dir_age_sec=$(test -d /run/totem/settings-session.lock && stat -c %Y /run/totem/settings-session.lock 2>/dev/null | awk -v now=$(date +%s) '{print now-$0}' || echo na)"
echo
echo "=== /run/dadooh-settings/trigger-status.json ==="
if [ -f /run/dadooh-settings/trigger-status.json ]; then
  python3 -c '
import json
try:
  with open("/run/dadooh-settings/trigger-status.json") as f:
    s = json.load(f)
  for k in ("schema_version","status","trigger_type","trigger_detected","request_written","devices_opened_count","open_service_start_attempted","open_service_start_result","session_lock_active","session_lock_age_bucket","open_service_active_state","stale_lock_suspected","stale_lock_removed","cooldown_active","raw_key_values_logged","characters_logged","credentials_collected"):
    if k in s:
      print(f"  {k}={s[k]}")
except Exception as e:
  print(f"  read_error={type(e).__name__}")
'
else
  echo "  trigger-status.json missing"
fi
echo
echo "=== /tmp/dadooh-status/status.json (public_state only) ==="
if [ -f /tmp/dadooh-status/status.json ]; then
  python3 -c '
import json
try:
  with open("/tmp/dadooh-status/status.json") as f:
    s = json.load(f)
  for k in ("public_state","state","reason","schema_version"):
    if k in s:
      print(f"  {k}={s[k]}")
except Exception as e:
  print(f"  read_error={type(e).__name__}")
'
else
  echo "  status.json missing"
fi
echo
echo "=== /tmp/kiosky-status.json (sanitized non-sensitive only) ==="
if [ -f /tmp/kiosky-status.json ]; then
  python3 -c '
import json
keys = ("playback_state","current_index","playlist_length","sync_enabled","sync_state","loop_active","mpv_alive","mpv_generation","status_age_sec","schema_version","last_update_status","fallback_active","fallback_reason","offline_mode")
try:
  with open("/tmp/kiosky-status.json") as f:
    s = json.load(f)
  for k in keys:
    if k in s:
      v = s[k]
      print(f"  {k}={v}")
except Exception as e:
  print(f"  read_error={type(e).__name__}")
'
else
  echo "  kiosky-status.json missing"
fi
echo
echo "=== /data/config/config.json non-sensitive fields only ==="
if [ -r /data/config/config.json ]; then
  python3 -c '
import json
keys = (
  "sync_enabled","preload_next","poll_interval_sec","default_duration_ms",
  "status_file","mpv_log_file","mpv_debug_events","allow_empty_playlist_from_api",
  "offline_fallback","media_load_retry_cooldown_sec","config_ui_enabled","hotkeys_enabled",
  "mpv_msg_level","status_interval_sec","mpv_watchdog_ping_threshold",
  "telemetry_enabled","schema_version","rotation_deg","appliance_profile"
)
try:
  with open("/data/config/config.json") as f:
    cfg = json.load(f)
  for k in keys:
    if k in cfg:
      print(f"  {k}={cfg[k]}")
  total = len(cfg)
  redacted = sum(1 for k in cfg if k not in keys)
  print(f"  config_keys_total={total}")
  print(f"  config_keys_redacted={redacted}")
except Exception as e:
  print(f"  config_read_error={type(e).__name__}")
'
else
  echo "  config.json not present or not readable"
fi
echo
echo "=== mpv log files (count, sizes only) ==="
ls -la /tmp/kiosky/ 2>/dev/null | grep -E 'mpv.*\.log' | head -10 || true
ls -la /data/state/kiosky-player/ 2>/dev/null | head -20 || true
ls -la /data/logs/ 2>/dev/null | head -20 || true
echo
echo "=== totem-updatectl status (sanitized) ==="
/opt/totem/bin/totem-updatectl status 2>&1 \
  | sed -E '
    s|/data/apps/kiosky-player/releases/[A-Za-z0-9._-]+|/data/apps/kiosky-player/releases/REDACTED|g;
    s|sha256=[0-9a-f]{64}|sha256=REDACTED|g
  ' | head -40 || true
echo
echo "=== F10/hotkey binding scan ==="
grep -rE -i 'KEY_F10|F10|hotkey' /etc/systemd /opt/totem 2>/dev/null \
  | grep -v Binary \
  | grep -vE '^[^:]+:[^:]+:#' \
  | head -20 || echo none
echo
echo "=== journalctl tail (errors only, last 30 from totem-open-settings) ==="
journalctl -u totem-open-settings.service --no-pager --since="-1h" -p err -n 30 2>/dev/null | tail -30 || true
echo "---"
echo "=== journalctl tail (errors only, last 30 from kiosky-player) ==="
journalctl -u kiosky-player.service --no-pager --since="-1h" -p err -n 30 2>/dev/null | tail -30 || true
echo "---"
echo "=== journalctl tail (totem-settings-trigger summary) ==="
journalctl -u totem-settings-trigger.service --no-pager --since="-1h" -n 20 2>/dev/null | tail -20 || true
echo
echo "=== systemd-coredump or service crashes (counts) ==="
journalctl -p err --no-pager --since="-2h" 2>/dev/null \
  | grep -Ei 'totem|kiosky|wizard|settings|getty' \
  | head -20 || true
echo
echo "=== getty visibility / tty1 reset history ==="
journalctl -u getty@tty1.service --no-pager --since="-1h" -n 10 2>/dev/null \
  | tail -10 || true
echo
echo "=== mpv processes + ttys ==="
pgrep -a mpv 2>/dev/null | head -5 || echo no_mpv_processes
echo
echo "=== current foreground VT ==="
if command -v fgconsole >/dev/null; then
  echo "fgconsole_now=$(fgconsole 2>/dev/null || echo unknown)"
fi
echo
echo "=== DONE ==="
REMOTE_EOF

echo "captured: $OUT"
