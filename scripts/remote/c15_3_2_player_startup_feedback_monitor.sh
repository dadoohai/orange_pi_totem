#!/usr/bin/env bash
set -u

OUT_ROOT="/data/state/totem-debug/c15-3-2"
DURATION_SEC="180"
INTERVAL_SEC="1"
PRINT_RUN_DIR="false"

usage() {
  cat <<'USAGE'
Usage:
  c15_3_2_player_startup_feedback_monitor.sh [--duration-sec N] [--interval-sec N] [--out-root /data/state/...] [--print-run-dir]

Records sanitized player startup feedback state to persistent /data storage.
It does not read real config, seed, NetworkManager profiles, SSID, passwords,
IP, MAC, DNS, media URLs, or raw logs.
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
  /data/state/totem-debug/c15-3-2|/data/state/totem-debug/c15-3-2/*)
    ;;
  *)
    echo "error: --out-root must be under /data/state/totem-debug/c15-3-2" >&2
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

latest_splash_mode() {
  if [ ! -d /tmp/dadooh-splash ]; then
    printf 'none'
    return
  fi
  status_path="$(find /tmp/dadooh-splash -type f -name status.json -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr \
    | awk 'NR==1 {print $2}')"
  if [ -n "$status_path" ]; then
    safe_json_field "$status_path" mode
  else
    printf 'none'
  fi
}

expected_user_visible_state() {
  playback_state="$1"
  startup_phase="$2"
  feedback_visible="$3"
  public_state="$4"
  mpv_present="$5"
  kiosk_present="$6"

  case "$startup_phase" in
    player_starting)
      printf 'starting_player'
      return
      ;;
    waiting_for_api|waiting_for_playlist|waiting_for_media_cache|waiting_for_media|waiting_for_content|preparing_first_frame|loading_content)
      if [ "$feedback_visible" = "true" ]; then
        printf 'loading_content'
      else
        printf 'loading_content_status_only'
      fi
      return
      ;;
  esac
  case "$playback_state" in
    waiting_for_api|waiting_for_playlist|waiting_for_media_cache|waiting_for_media|waiting_for_content|preparing_first_frame|loading_content)
      if [ "$feedback_visible" = "true" ]; then
        printf 'loading_content'
      else
        printf 'loading_content_status_only'
      fi
      return
      ;;
  esac
  if [ "$playback_state" = "playing" ] || [ "$public_state" = "player_running" ]; then
    printf 'playing'
    return
  fi
  if [ "$mpv_present" = "true" ] && [ "$kiosk_present" = "true" ]; then
    printf 'unknown_player_visible'
  else
    printf 'unknown'
  fi
}

append_json_sample() {
  target="$1"
  python3 - "$target" \
    "$sample_index" "$uptime_s" "$wall_clock" "$boot_id" "$nm_active" "$network_connected" \
    "$ssh_active" "$player_active" "$mpv_present" "$kiosk_present" "$public_state" \
    "$playback_state" "$startup_phase" "$content_state" "$feedback_state" "$feedback_visible" \
    "$first_frame_ready" "$splash_mode" "$expected_state" <<'PY'
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
    "public_state",
    "playback_state",
    "startup_phase",
    "content_state",
    "startup_feedback_state",
    "startup_feedback_visible",
    "first_frame_ready",
    "splash_mode",
    "expected_user_visible_state",
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

TIMELINE_JSONL="$RUN_DIR/timeline.jsonl"
FINAL_SUMMARY="$RUN_DIR/final-summary.json"
MONITOR_LOG="$RUN_DIR/monitor.log"

if [ "$PRINT_RUN_DIR" = "true" ]; then
  printf '%s\n' "$RUN_DIR"
fi

{
  printf 'schema_version=dadooh-c15.3.2-player-startup-feedback-monitor.v1\n'
  printf 'started_at_utc=%s\n' "$(utc_now)"
  printf 'duration_sec=%s\n' "$DURATION_SEC"
  printf 'interval_sec=%s\n' "$INTERVAL_SEC"
  printf 'guardrails=config_not_read seed_not_read nm_profiles_not_read secrets_not_published writer_not_called\n'
} > "$MONITOR_LOG"

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
  public_state="$(safe_json_field /tmp/dadooh-status/status.json public_state)"
  if [ "$public_state" = "unknown" ]; then
    public_state="$(safe_json_field /tmp/dadooh-status/status.json state)"
  fi
  playback_state="$(safe_json_field /tmp/kiosky-status.json playback_state)"
  startup_phase="$(safe_json_field /tmp/kiosky-status.json startup_phase)"
  content_state="$(safe_json_field /tmp/kiosky-status.json content_state)"
  feedback_state="$(safe_json_field /tmp/kiosky-status.json startup_feedback_state)"
  feedback_visible="$(safe_json_field /tmp/kiosky-status.json startup_feedback_visible)"
  first_frame_ready="$(safe_json_field /tmp/kiosky-status.json first_frame_ready)"
  splash_mode="$(latest_splash_mode)"
  expected_state="$(expected_user_visible_state "$playback_state" "$startup_phase" "$feedback_visible" "$public_state" "$mpv_present" "$kiosk_present")"
  append_json_sample "$TIMELINE_JSONL"
  sync "$TIMELINE_JSONL" >/dev/null 2>&1 || true
  sleep "$INTERVAL_SEC"
done

python3 - "$TIMELINE_JSONL" "$FINAL_SUMMARY" <<'PY'
import json
import pathlib
import sys
from collections import Counter

timeline = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
samples = []
if timeline.is_file():
    with timeline.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                pass

visible_counts = Counter(str(sample.get("expected_user_visible_state", "unknown")) for sample in samples)
playback_counts = Counter(str(sample.get("playback_state", "unknown")) for sample in samples)
startup_counts = Counter(str(sample.get("startup_phase", "unknown")) for sample in samples)
loading_samples = [
    sample for sample in samples
    if sample.get("expected_user_visible_state") in {"loading_content", "loading_content_status_only"}
]
payload = {
    "schema_version": "dadooh-c15.3.2-player-startup-feedback-summary.v1",
    "sample_count": len(samples),
    "first_sample_uptime_sec": samples[0].get("monotonic_uptime_sec") if samples else None,
    "last_sample_uptime_sec": samples[-1].get("monotonic_uptime_sec") if samples else None,
    "boot_id_changed": len({sample.get("boot_id") for sample in samples}) > 1 if samples else "unknown",
    "expected_user_visible_state_counts": dict(sorted(visible_counts.items())),
    "playback_state_counts": dict(sorted(playback_counts.items())),
    "startup_phase_counts": dict(sorted(startup_counts.items())),
    "loading_content_state_seen": bool(loading_samples),
    "loading_content_feedback_visible": any(sample.get("startup_feedback_visible") is True for sample in loading_samples),
    "playing_seen": any(sample.get("playback_state") == "playing" for sample in samples),
    "ssh_remained_active": all(sample.get("ssh_active") is True for sample in samples) if samples else "unknown",
    "network_remained_connected": all(sample.get("network_connected") is True for sample in samples) if samples else "unknown",
    "player_active_all_samples": all(sample.get("kiosky_player_active") is True for sample in samples) if samples else "unknown",
    "mpv_present_any": any(sample.get("mpv_process_present") is True for sample in samples),
    "kiosk_present_any": any(sample.get("kiosk_process_present") is True for sample in samples),
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
