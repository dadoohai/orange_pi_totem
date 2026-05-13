#!/usr/bin/env bash
set -u

OUT_ROOT="/data/state/totem-debug/c15-3-1"
DURATION_SEC="180"
INTERVAL_SEC="1"
PRINT_RUN_DIR="false"

usage() {
  cat <<'USAGE'
Usage:
  c15_3_1_visual_transition_timeline.sh [--duration-sec N] [--interval-sec N] [--out-root /data/state/...] [--print-run-dir]

Records a sanitized visual/perceptive transition timeline to persistent /data
storage. It does not read real config, seed, NetworkManager profiles, SSID,
passwords, IP, MAC, or DNS values.
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
  /data/state/totem-debug/c15-3-1|/data/state/totem-debug/c15-3-1/*)
    ;;
  *)
    echo "error: --out-root must be under /data/state/totem-debug/c15-3-1" >&2
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

process_name_present_bool() {
  name="$1"
  if pgrep -x "$name" >/dev/null 2>&1; then
    printf 'true'
  else
    printf 'false'
  fi
}

network_connected_category() {
  state="$(timeout 2 nmcli -t -f STATE general status 2>/dev/null | head -n 1 | tr -d '\r' || true)"
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

safe_json_field() {
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
        print(safe[:72] or "unknown")
except Exception:
    print("unknown")
PY
}

latest_splash_status() {
  if [ ! -d /tmp/dadooh-splash ]; then
    printf 'none'
    return
  fi
  find /tmp/dadooh-splash -type f -name status.json -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr \
    | awk 'NR==1 {print $2}'
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

last_player_log_category() {
  journalctl -u kiosky-player.service -n 120 -o cat --no-pager 2>/dev/null \
    | awk '
      /MPV IPC unresponsive|Failed to load media|restarting MPV/ {cat="player_media_or_mpv_issue"}
      /display_connected starting_app/ {cat="launcher_started_app"}
      /config_missing/ {cat="config_missing"}
      /app_exited/ {cat="app_exited"}
      END {print cat ? cat : "unknown"}
    '
}

expected_screen_state() {
  splash_mode="$1"
  public_state="$2"
  playback_state="$3"
  launcher_state="$4"
  player_active="$5"
  mpv_present="$6"
  kiosk_present="$7"
  lock_present="$8"
  open_settings_active="$9"

  if [ "$lock_present" = "true" ] || [ "$open_settings_active" = "true" ]; then
    printf 'splash_setup'
    return
  fi
  if [ "$playback_state" = "playing" ]; then
    printf 'player_playing'
    return
  fi
  case "$splash_mode" in
    saving)
      printf 'splash_saving'
      return
      ;;
    setup)
      printf 'splash_setup'
      return
      ;;
  esac
  case "$launcher_state:$public_state" in
    config_missing:*|*:config_missing|*:config_pending)
      printf 'config_pending'
      return
      ;;
  esac
  if [ "$player_active" = "true" ] && [ "$mpv_present" = "true" ] && [ "$kiosk_present" = "true" ]; then
    if [ "$playback_state" = "playing" ]; then
      printf 'player_playing'
    else
      printf 'player_black_possible'
    fi
    return
  fi
  if [ "$splash_mode" = "player" ] || [ "$launcher_state" = "starting" ]; then
    printf 'splash_player'
    return
  fi
  printf 'unknown'
}

append_json_sample() {
  target="$1"
  python3 - "$target" \
    "$sample_index" "$uptime_s" "$wall_clock" "$boot_id" "$nm_active" "$network_connected" \
    "$ssh_active" "$player_active" "$mpv_present" "$kiosk_present" "$openvt_present" \
    "$open_settings_active" "$session_lock" "$splash_mode" "$splash_rendered" "$public_state" \
    "$playback_state" "$launcher_state" "$last_phase" "$last_player_category" "$expected_screen" <<'PY'
import json
import sys

target = sys.argv[1]
keys = (
    "sample_index",
    "monotonic_uptime_sec",
    "wall_clock_utc",
    "boot_id",
    "networkmanager_active",
    "network_connected",
    "ssh_active",
    "kiosky_player_active",
    "mpv_process_present",
    "kiosk_process_present",
    "openvt_process_present",
    "totem_open_settings_active",
    "session_lock_present",
    "splash_mode",
    "splash_rendered",
    "public_state",
    "playback_state",
    "launcher_state",
    "last_wizard_phase",
    "last_player_log_category",
    "expected_screen",
)
payload = {}
for key, value in zip(keys, sys.argv[2:]):
    if value in ("true", "false"):
        payload[key] = value == "true"
    else:
        try:
            payload[key] = int(value) if key in {"sample_index", "monotonic_uptime_sec"} else value
        except ValueError:
            payload[key] = value
with open(target, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(payload, sort_keys=True) + "\n")
PY
}

install -d -o root -g root -m 0700 "$OUT_ROOT" || exit 1
RUN_ID="$(date -u '+%Y%m%dT%H%M%SZ')-pid$$"
RUN_DIR="$OUT_ROOT/$RUN_ID"
install -d -o root -g root -m 0700 "$RUN_DIR" || exit 1

MONITOR_LOG="$RUN_DIR/monitor.log"
TIMELINE_JSONL="$RUN_DIR/timeline.jsonl"
STATUS_OBSERVABILITY="$RUN_DIR/status-observability.json"
FINAL_SUMMARY="$RUN_DIR/final-summary.json"

if [ "$PRINT_RUN_DIR" = "true" ]; then
  printf '%s\n' "$RUN_DIR"
fi

{
  printf 'schema_version=dadooh-c15.3.1-visual-transition-timeline.v1\n'
  printf 'started_at_utc=%s\n' "$(utc_now)"
  printf 'duration_sec=%s\n' "$DURATION_SEC"
  printf 'interval_sec=%s\n' "$INTERVAL_SEC"
  printf 'guardrails=config_not_read seed_not_read nm_profiles_not_read secrets_not_published writer_not_called\n'
} > "$MONITOR_LOG"

PLAYER_LOG_CATEGORY="$(last_player_log_category)"

python3 - "$STATUS_OBSERVABILITY" <<'PY'
import json
import pathlib
import os
import glob
import sys

target = pathlib.Path(sys.argv[1])
paths = {
    "splash_status_dir": pathlib.Path("/tmp/dadooh-splash").is_dir(),
    "public_status": pathlib.Path("/tmp/dadooh-status/status.json").is_file(),
    "player_status": pathlib.Path("/tmp/kiosky-status.json").is_file(),
    "launcher_status_data": pathlib.Path("/data/state/kiosky-player/launcher-status.json").is_file(),
    "launcher_status_tmp": pathlib.Path("/tmp/kiosky-launcher-status.json").is_file(),
    "session_status": pathlib.Path("/tmp/dadooh-c10-6-open-settings-session/session-status.json").is_file(),
    "session_trace": pathlib.Path("/tmp/c15-session.trace").is_file(),
    "debug_data_root": pathlib.Path("/data/state/totem-debug").is_dir(),
    "framebuffer_device": pathlib.Path("/dev/fb0").exists(),
    "cache_media_api_public_status": False,
}
payload = {
    "schema_version": "dadooh-c15.3.1-status-observability.v1",
    "status_observability": "partial" if (
        paths["public_status"] and paths["player_status"] and paths["launcher_status_data"]
    ) else "insufficient",
    "sources": paths,
    "config_read": False,
    "seed_read": False,
    "networkmanager_profiles_read": False,
    "writer_called": False,
    "raw_logs_written": False,
}
target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(target, 0o600)
PY

sample_index=0
end_at=$(( $(monotonic_seconds) + DURATION_SEC ))
while [ "$(monotonic_seconds)" -lt "$end_at" ]; do
  sample_index=$((sample_index + 1))
  uptime_s="$(monotonic_seconds)"
  wall_clock="$(utc_now)"
  boot_id="$(boot_id_value)"
  nm_active="$(service_active_bool NetworkManager.service)"
  network_connected="$(network_connected_category)"
  ssh_active="$(ssh_active_bool)"
  player_active="$(service_active_bool kiosky-player.service)"
  mpv_present="$(process_name_present_bool mpv)"
  kiosk_present="$(process_present_bool 'kiosk.py')"
  openvt_present="$(process_present_bool 'openvt')"
  open_settings_active="$(service_active_bool totem-open-settings.service)"
  if [ -e /run/totem/settings-session.lock ]; then
    session_lock="true"
  else
    session_lock="false"
  fi
  splash_status="$(latest_splash_status)"
  if [ "$splash_status" != "none" ]; then
    splash_mode="$(safe_json_field "$splash_status" mode)"
    splash_rendered="$(safe_json_field "$splash_status" rendered)"
  else
    splash_mode="none"
    splash_rendered="unknown"
  fi
  public_state="$(safe_json_field /tmp/dadooh-status/status.json public_state)"
  playback_state="$(safe_json_field /tmp/kiosky-status.json playback_state)"
  launcher_state="$(safe_json_field /data/state/kiosky-player/launcher-status.json state)"
  if [ "$launcher_state" = "unknown" ]; then
    launcher_state="$(safe_json_field /tmp/kiosky-launcher-status.json state)"
  fi
  last_phase="$(last_trace_phase)"
  last_player_category="$PLAYER_LOG_CATEGORY"
  expected_screen="$(expected_screen_state "$splash_mode" "$public_state" "$playback_state" "$launcher_state" "$player_active" "$mpv_present" "$kiosk_present" "$session_lock" "$open_settings_active")"
  append_json_sample "$TIMELINE_JSONL"
  sync "$TIMELINE_JSONL" >/dev/null 2>&1 || true
  sleep "$INTERVAL_SEC"
done

python3 - "$TIMELINE_JSONL" "$STATUS_OBSERVABILITY" "$FINAL_SUMMARY" <<'PY'
import json
import pathlib
import sys
from collections import Counter

timeline = pathlib.Path(sys.argv[1])
observability_path = pathlib.Path(sys.argv[2])
target = pathlib.Path(sys.argv[3])

samples = []
if timeline.is_file():
    with timeline.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                pass

screens = Counter(str(sample.get("expected_screen", "unknown")) for sample in samples)
playback_values = Counter(str(sample.get("playback_state", "unknown")) for sample in samples)
black_possible_samples = screens.get("player_black_possible", 0)
max_black_run = 0
current_black_run = 0
for sample in samples:
    if sample.get("expected_screen") == "player_black_possible":
        current_black_run += 1
    else:
        max_black_run = max(max_black_run, current_black_run)
        current_black_run = 0
max_black_run = max(max_black_run, current_black_run)

try:
    observability = json.loads(observability_path.read_text(encoding="utf-8"))
except Exception:
    observability = {}

payload = {
    "schema_version": "dadooh-c15.3.1-visual-transition-summary.v1",
    "sample_count": len(samples),
    "first_sample_uptime_sec": samples[0].get("monotonic_uptime_sec") if samples else None,
    "last_sample_uptime_sec": samples[-1].get("monotonic_uptime_sec") if samples else None,
    "boot_id_changed": len({sample.get("boot_id") for sample in samples}) > 1 if samples else "unknown",
    "screen_counts": dict(sorted(screens.items())),
    "playback_state_counts": dict(sorted(playback_values.items())),
    "black_interval_observed": black_possible_samples > 0,
    "black_interval_duration_sec": max_black_run if black_possible_samples > 0 else 0,
    "playback_started_after_black": bool(
        black_possible_samples > 0 and any(sample.get("playback_state") == "playing" for sample in samples)
    ),
    "ssh_remained_active": all(sample.get("ssh_active") is True for sample in samples) if samples else "unknown",
    "network_remained_connected": all(sample.get("network_connected") is True for sample in samples) if samples else "unknown",
    "player_active_all_samples": all(sample.get("kiosky_player_active") is True for sample in samples) if samples else "unknown",
    "mpv_present_any": any(sample.get("mpv_process_present") is True for sample in samples),
    "kiosk_present_any": any(sample.get("kiosk_process_present") is True for sample in samples),
    "status_observability": observability.get("status_observability", "unknown"),
    "guardrails": {
        "config_read": False,
        "seed_read": False,
        "networkmanager_profiles_read": False,
        "writer_called": False,
        "real_config_written": False,
        "raw_logs_written": False,
    },
}
target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
target.chmod(0o600)
PY

{
  printf 'finished_at_utc=%s\n' "$(utc_now)"
  printf 'final_summary=%s\n' "$FINAL_SUMMARY"
} >> "$MONITOR_LOG"
sync "$RUN_DIR" >/dev/null 2>&1 || true
