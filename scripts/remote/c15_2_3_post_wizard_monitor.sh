#!/usr/bin/env bash
set -u

OUT_ROOT="/data/state/totem-debug/c15-2-3"
DURATION_SEC="600"
INTERVAL_SEC="1"
PRINT_RUN_DIR="false"

usage() {
  cat <<'USAGE'
Usage:
  c15_2_3_post_wizard_monitor.sh [--duration-sec N] [--interval-sec N] [--out-root /data/state/...] [--print-run-dir]

Records sanitized post-wizard state to persistent /data storage. It does not
read real config, seed, NetworkManager profiles, SSID, passwords, IP, MAC, or
DNS values.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --duration-sec)
      shift
      DURATION_SEC="${1:-}"
      ;;
    --interval-sec)
      shift
      INTERVAL_SEC="${1:-}"
      ;;
    --out-root)
      shift
      OUT_ROOT="${1:-}"
      ;;
    --print-run-dir)
      PRINT_RUN_DIR="true"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "error: unsupported argument $1" >&2
      exit 2
      ;;
  esac
  shift
done

case "$OUT_ROOT" in
  /data/state/totem-debug/c15-2-3|/data/state/totem-debug/c15-2-3/*)
    ;;
  *)
    echo "error: --out-root must be under /data/state/totem-debug/c15-2-3" >&2
    exit 2
    ;;
esac

case "$DURATION_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --duration-sec must be a positive integer" >&2
    exit 2
    ;;
esac

case "$INTERVAL_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --interval-sec must be a positive integer" >&2
    exit 2
    ;;
esac

utc_now() {
  date -u '+%Y-%m-%dT%H:%M:%SZ'
}

monotonic_seconds() {
  awk '{print int($1)}' /proc/uptime 2>/dev/null || printf '0\n'
}

boot_id_value() {
  if [ -r /proc/sys/kernel/random/boot_id ]; then
    tr -d '\n' < /proc/sys/kernel/random/boot_id
  else
    printf 'unknown'
  fi
}

service_active_bool() {
  unit="$1"
  if systemctl is-active --quiet "$unit" 2>/dev/null; then
    printf 'true'
  else
    printf 'false'
  fi
}

ssh_active_bool() {
  if systemctl is-active --quiet ssh.service 2>/dev/null; then
    printf 'true'
    return
  fi
  if systemctl is-active --quiet sshd.service 2>/dev/null; then
    printf 'true'
    return
  fi
  printf 'false'
}

process_present_bool() {
  pattern="$1"
  if pgrep -f "$pattern" >/dev/null 2>&1; then
    printf 'true'
  else
    printf 'false'
  fi
}

network_connected_category() {
  state="$(nmcli -t -f STATE general status 2>/dev/null | head -n 1 | tr -d '\r' || true)"
  case "$state" in
    connected|connected\ *)
      printf 'true'
      ;;
    disconnected|asleep|connecting)
      printf 'false'
      ;;
    *)
      printf 'unknown'
      ;;
  esac
}

memory_bucket() {
  awk '
    /MemAvailable:/ {mb=int($2/1024)}
    END {
      if (mb >= 512) print "free_ge_512mb";
      else if (mb >= 256) print "free_ge_256mb";
      else if (mb >= 128) print "free_ge_128mb";
      else if (mb > 0) print "free_lt_128mb";
      else print "unknown";
    }
  ' /proc/meminfo 2>/dev/null || printf 'unknown\n'
}

disk_bucket() {
  used="$(df -P /data 2>/dev/null | awk 'NR==2 {gsub(/%/, "", $5); print $5}')"
  case "$used" in
    ''|*[!0-9]*)
      printf 'unknown'
      ;;
    *)
      if [ "$used" -lt 70 ]; then
        printf 'used_lt_70pct'
      elif [ "$used" -lt 85 ]; then
        printf 'used_lt_85pct'
      elif [ "$used" -lt 95 ]; then
        printf 'used_lt_95pct'
      else
        printf 'used_ge_95pct'
      fi
      ;;
  esac
}

json_field() {
  path="$1"
  field="$2"
  if [ ! -f "$path" ] || [ -L "$path" ]; then
    printf 'unknown'
    return
  fi
  python3 - "$path" "$field" <<'PY' 2>/dev/null || printf 'unknown'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
field = sys.argv[2]
try:
    value = json.loads(path.read_text(encoding="utf-8"))
    for part in field.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
            break
    if isinstance(value, bool):
        print(str(value).lower())
    elif value is None:
        print("unknown")
    else:
        text = str(value)
        safe = "".join(ch for ch in text if ch.isalnum() or ch in "._:-")
        print(safe[:64] or "unknown")
except Exception:
    print("unknown")
PY
}

last_trace_phase() {
  if [ ! -f /tmp/c15-session.trace ] || [ -L /tmp/c15-session.trace ]; then
    printf 'none'
    return
  fi
  tail -n 1 /tmp/c15-session.trace 2>/dev/null \
    | sed -E 's/.* phase=//; s/[^A-Za-z0-9_+=:., -]/_/g; s/[[:space:]]+/_/g' \
    | cut -c 1-160
}

append_line() {
  path="$1"
  line="$2"
  printf '%s\n' "$line" >> "$path" 2>/dev/null || true
}

install -d -o root -g root -m 0700 "$OUT_ROOT" || exit 1
RUN_ID="$(date -u '+%Y%m%dT%H%M%SZ')-pid$$"
RUN_DIR="$OUT_ROOT/$RUN_ID"
install -d -o root -g root -m 0700 "$RUN_DIR" || exit 1
chmod 0700 "$RUN_DIR" 2>/dev/null || true
printf '%s\n' "$RUN_DIR" > "$OUT_ROOT/current-run-dir"
chmod 0600 "$OUT_ROOT/current-run-dir" 2>/dev/null || true
if [ "$PRINT_RUN_DIR" = "true" ]; then
  printf '%s\n' "$RUN_DIR"
fi

MONITOR_LOG="$RUN_DIR/monitor.log"
PHASES_LOG="$RUN_DIR/phases.log"
SYSTEMD_LOG="$RUN_DIR/systemd-state.log"
NETWORK_LOG="$RUN_DIR/network-state.log"
PLAYER_LOG="$RUN_DIR/player-state.log"
SUMMARY_JSON="$RUN_DIR/final-summary.json"

for path in "$MONITOR_LOG" "$PHASES_LOG" "$SYSTEMD_LOG" "$NETWORK_LOG" "$PLAYER_LOG"; do
  : > "$path"
  chmod 0600 "$path" 2>/dev/null || true
done

BOOT_ID_START="$(boot_id_value)"
START_MONO="$(monotonic_seconds)"
END_MONO=$(( START_MONO + DURATION_SEC ))
SAMPLE_COUNT=0
LAST_PHASE="none"

append_line "$PHASES_LOG" "$(utc_now) uptime=$START_MONO phase=monitor_started boot_id=$BOOT_ID_START"
sync

while [ "$(monotonic_seconds)" -lt "$END_MONO" ]; do
  NOW="$(utc_now)"
  MONO="$(monotonic_seconds)"
  BOOT_ID="$(boot_id_value)"
  LOADAVG="$(cut -d ' ' -f 1-3 /proc/loadavg 2>/dev/null | tr ' ' ',' || printf 'unknown')"
  MEM_BUCKET="$(memory_bucket)"
  DISK_BUCKET="$(disk_bucket)"
  NM_ACTIVE="$(service_active_bool NetworkManager.service)"
  NETWORK_CONNECTED="$(network_connected_category)"
  SSH_ACTIVE="$(ssh_active_bool)"
  KIOSKY_ACTIVE="$(service_active_bool kiosky-player.service)"
  OPEN_SETTINGS_ACTIVE="$(service_active_bool totem-open-settings.service)"
  TRIGGER_ACTIVE="$(service_active_bool totem-settings-trigger.service)"
  GUARD_ACTIVE="$(service_active_bool totem-visual-tty-guard.service)"
  MPV_PRESENT="$(process_present_bool '(^|/)mpv($| )')"
  KIOSK_PRESENT="$(process_present_bool 'kiosk\.py')"
  OPENVT_PRESENT="$(process_present_bool 'openvt')"
  SESSION_LOCK_PRESENT="false"
  if [ -e /run/totem/settings-session.lock ] || [ -e /run/dadooh-settings/session.lock ]; then
    SESSION_LOCK_PRESENT="true"
  fi
  PUBLIC_STATE="$(json_field /tmp/kiosky-status.json state)"
  PLAYBACK_STATE="$(json_field /tmp/kiosky-status.json playback_state)"
  TRACE_PHASE="$(last_trace_phase)"
  if [ "$TRACE_PHASE" != "$LAST_PHASE" ]; then
    append_line "$PHASES_LOG" "$NOW uptime=$MONO phase=trace_observed value=$TRACE_PHASE"
    LAST_PHASE="$TRACE_PHASE"
  fi

  COMMON="ts=$NOW uptime=$MONO boot_id=$BOOT_ID loadavg=$LOADAVG memory=$MEM_BUCKET disk=$DISK_BUCKET"
  append_line "$MONITOR_LOG" "$COMMON network_connected=$NETWORK_CONNECTED ssh_active=$SSH_ACTIVE kiosky_active=$KIOSKY_ACTIVE mpv_present=$MPV_PRESENT kiosk_present=$KIOSK_PRESENT openvt_present=$OPENVT_PRESENT open_settings_active=$OPEN_SETTINGS_ACTIVE session_lock=$SESSION_LOCK_PRESENT playback_state=$PLAYBACK_STATE public_state=$PUBLIC_STATE last_trace_phase=$TRACE_PHASE hdmi_state=unknown"
  append_line "$SYSTEMD_LOG" "$COMMON NetworkManager_active=$NM_ACTIVE ssh_active=$SSH_ACTIVE kiosky_player_active=$KIOSKY_ACTIVE totem_open_settings_active=$OPEN_SETTINGS_ACTIVE totem_settings_trigger_active=$TRIGGER_ACTIVE totem_visual_tty_guard_active=$GUARD_ACTIVE"
  append_line "$NETWORK_LOG" "$COMMON NetworkManager_active=$NM_ACTIVE network_connected=$NETWORK_CONNECTED"
  append_line "$PLAYER_LOG" "$COMMON kiosky_active=$KIOSKY_ACTIVE mpv_present=$MPV_PRESENT kiosk_present=$KIOSK_PRESENT playback_state=$PLAYBACK_STATE public_state=$PUBLIC_STATE"

  SAMPLE_COUNT=$(( SAMPLE_COUNT + 1 ))
  if [ $(( SAMPLE_COUNT % 5 )) -eq 0 ]; then
    sync
  fi
  sleep "$INTERVAL_SEC"
done

END_MONO_ACTUAL="$(monotonic_seconds)"
append_line "$PHASES_LOG" "$(utc_now) uptime=$END_MONO_ACTUAL phase=monitor_finished samples=$SAMPLE_COUNT"

cat > "$SUMMARY_JSON" <<EOF
{
  "schema_version": "dadooh-c15-2-3-post-wizard-monitor.v1",
  "run_id": "$RUN_ID",
  "duration_sec": $DURATION_SEC,
  "interval_sec": $INTERVAL_SEC,
  "sample_count": $SAMPLE_COUNT,
  "boot_id_start": "$BOOT_ID_START",
  "boot_id_end": "$(boot_id_value)",
  "monitor_stopped_reason": "normal_timeout",
  "secrets_published": false,
  "config_read": false,
  "seed_read": false,
  "network_profiles_read": false,
  "ip_mac_dns_logged": false,
  "ssid_logged": false,
  "wifi_password_logged": false
}
EOF
chmod 0600 "$SUMMARY_JSON" 2>/dev/null || true

current="$(cat "$OUT_ROOT/current-run-dir" 2>/dev/null || true)"
if [ "$current" = "$RUN_DIR" ]; then
  rm -f "$OUT_ROOT/current-run-dir" 2>/dev/null || true
fi
sync
