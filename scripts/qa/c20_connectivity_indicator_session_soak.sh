#!/usr/bin/env bash
set -euo pipefail

ARTIFACT_DIR="${1:-/tmp/c20-connectivity-session-soak}"
DURATION_SEC="${2:-600}"
INTERVAL_SEC="${3:-5}"
WIZARD_DIR="/tmp/dadooh-c10-6-2-visual-wizard"
SESSION_DIR="/tmp/dadooh-c10-6-2-open-settings/session"
REQUEST_DIR="/run/dadooh-settings"
LOCK_DIR="/run/totem/settings-session.lock"
KEY_HELPER="/tmp/c20_uinput_key_sequence.py"
EXPECTED_KEY_HELPER_SHA256="b076857006a2ec0e9d87e183d2806f026564c47f23d2d066bc0ff601f6953b23"
PLAYER_SERVICE="kiosky-player.service"
SETTINGS_SERVICE="totem-open-settings.service"
CONFIG_PATH="/data/config/config.json"
CONTEXT_PATH="/data/state/totem-settings/last-settings.json"
APPLY_POLICY_PATH="/run/dadooh-settings/apply-policy.json"

case "$DURATION_SEC:$INTERVAL_SEC" in
  *[!0-9:]*|:*|*:) echo "duration and interval must be positive integers" >&2; exit 2 ;;
esac
test "$DURATION_SEC" -ge 60
test "$DURATION_SEC" -le 600
test "$INTERVAL_SEC" -ge 1
test "$INTERVAL_SEC" -le 30

case "$ARTIFACT_DIR" in
  /tmp/?*) ;;
  *) echo "artifact directory must be a new path below /tmp" >&2; exit 2 ;;
esac
test ! -e "$ARTIFACT_DIR"
install -d -m 0700 "$ARTIFACT_DIR" "$ARTIFACT_DIR/captures"
SAMPLES="$ARTIFACT_DIR/samples.csv"
LOG="$ARTIFACT_DIR/soak.log"
: >"$LOG"
printf 'elapsed_sec,pid,rss_kb,fd_count,thread_count,child_count,screen_count,refresh_file_count,probe_pid\n' >"$SAMPLES"

log() {
  printf '%s %s\n' "$(date -Is)" "$*" | tee -a "$LOG"
}

capture_frame() {
  local name="$1"
  ffmpeg -hide_banner -loglevel error -f fbdev -i /dev/fb0 -frames:v 1 -update 1 \
    "$ARTIFACT_DIR/captures/$name.jpg" >>"$LOG" 2>&1
  sha256sum "$ARTIFACT_DIR/captures/$name.jpg" >>"$LOG"
}

wait_for_wizard() {
  local index
  for index in $(seq 1 30); do
    if pgrep -f '^/usr/bin/python3 /data/core/totem/current/bin/totem_setup_visual_wizard.py( |$)' \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for_exit() {
  local index state
  for index in $(seq 1 45); do
    state="$(systemctl is-active "$SETTINGS_SERVICE" 2>/dev/null || true)"
    if ! pgrep -f '^/usr/bin/python3 /data/core/totem/current/bin/totem_setup_visual_wizard.py( |$)' \
      >/dev/null 2>&1 \
      && test "$state" = "inactive"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

cleanup() {
  local rc="${1:-1}"
  local cleanup_failed=0 index
  trap - EXIT INT TERM HUP
  if pgrep -f '^/usr/bin/python3 /data/core/totem/current/bin/totem_setup_visual_wizard.py( |$)' \
    >/dev/null 2>&1; then
    "$KEY_HELPER" --keys q --delay-sec 0.2 >>"$LOG" 2>&1 || cleanup_failed=1
    sleep 2
  fi
  systemctl stop "$SETTINGS_SERVICE" >>"$LOG" 2>&1 || cleanup_failed=1
  /opt/totem/bin/totem_open_settings_cleanup.sh \
    --reason c20-connectivity-session-soak-final >>"$LOG" 2>&1 || cleanup_failed=1
  systemctl reset-failed "$SETTINGS_SERVICE" >>"$LOG" 2>&1 || cleanup_failed=1
  systemctl start "$PLAYER_SERVICE" >>"$LOG" 2>&1 || cleanup_failed=1
  for index in $(seq 1 20); do
    test "$(systemctl is-active "$PLAYER_SERVICE" 2>/dev/null || true)" = "active" && break
    sleep 1
  done
  test "$(systemctl is-active "$PLAYER_SERVICE" 2>/dev/null || true)" = "active" || cleanup_failed=1
  test "$(systemctl is-active "$SETTINGS_SERVICE" 2>/dev/null || true)" = "inactive" || cleanup_failed=1
  test ! -e "$LOCK_DIR" || cleanup_failed=1
  test ! -e "$REQUEST_DIR/request.json" || cleanup_failed=1
  test ! -e "$APPLY_POLICY_PATH" || cleanup_failed=1
  printf 'original_rc=%s\ncleanup_passed=%s\n' "$rc" "$((cleanup_failed == 0))" \
    >"$ARTIFACT_DIR/cleanup-status.txt"
  if test "$cleanup_failed" -ne 0 && test "$rc" -eq 0; then
    rc=90
  fi
  exit "$rc"
}

test -x "$KEY_HELPER"
test "$(sha256sum "$KEY_HELPER" | awk '{print $1}')" = "$EXPECTED_KEY_HELPER_SHA256"
test -e /dev/fb0
test "$(systemctl is-active "$PLAYER_SERVICE" 2>/dev/null || true)" = "active"
test "$(systemctl is-active "$SETTINGS_SERVICE" 2>/dev/null || true)" = "inactive"
test ! -e "$LOCK_DIR"
test ! -e "$REQUEST_DIR/request.json"
test ! -e "$APPLY_POLICY_PATH"
test -z "$(pgrep -f '^/usr/bin/python3 /data/core/totem/current/bin/totem_setup_visual_wizard.py( |$)' || true)"

trap 'cleanup $?' EXIT
trap 'cleanup 130' INT
trap 'cleanup 143' TERM
trap 'cleanup 129' HUP
CONFIG_SHA_BEFORE="$(sha256sum "$CONFIG_PATH" | awk '{print $1}')"
CONTEXT_SHA_BEFORE="$(sha256sum "$CONTEXT_PATH" | awk '{print $1}')"
PLAYER_RESTARTS_BEFORE="$(systemctl show "$PLAYER_SERVICE" -p NRestarts --value)"
NETWORK_STATE_SHA_BEFORE="$({
  /usr/bin/nmcli -t -f UUID,TYPE,DEVICE connection show --active
  /usr/sbin/ip -j -4 route show table main default
} | LC_ALL=C sort | sha256sum | awk '{print $1}')"
JOURNAL_CURSOR="$(journalctl -n 0 --show-cursor 2>/dev/null | sed -n 's/^-- cursor: //p')"

systemctl reset-failed "$SETTINGS_SERVICE" >>"$LOG" 2>&1 || true
systemctl start "$PLAYER_SERVICE" >>"$LOG" 2>&1
rm -rf "$WIZARD_DIR"

log "start_settings duration_sec=$DURATION_SEC interval_sec=$INTERVAL_SEC"
systemctl start "$SETTINGS_SERVICE" >"$ARTIFACT_DIR/settings-start.stdout" \
  2>"$ARTIFACT_DIR/settings-start.stderr" &
wait_for_wizard
sleep 5
capture_frame "01-start"

START_MONOTONIC="$(cut -d' ' -f1 /proc/uptime)"
while true; do
  NOW_MONOTONIC="$(cut -d' ' -f1 /proc/uptime)"
  ELAPSED="$(awk -v now="$NOW_MONOTONIC" -v start="$START_MONOTONIC" 'BEGIN { printf "%d", now-start }')"
  PID="$(pgrep -fo '^/usr/bin/python3 /data/core/totem/current/bin/totem_setup_visual_wizard.py( |$)')"
  test -n "$PID"
  RSS_KB="$(awk '/^VmRSS:/ {print $2}' "/proc/$PID/status")"
  FD_COUNT="$(find "/proc/$PID/fd" -mindepth 1 -maxdepth 1 -printf . 2>/dev/null | wc -c)"
  THREAD_COUNT="$(awk '/^Threads:/ {print $2}' "/proc/$PID/status")"
  CHILD_COUNT="$(awk '{print NF}' "/proc/$PID/task/$PID/children")"
  CHILD_COUNT="${CHILD_COUNT:-0}"
  SCREEN_COUNT="$(find "$WIZARD_DIR/screens" -maxdepth 1 -type f -name '*.svg' 2>/dev/null | wc -l)"
  REFRESH_COUNT="$(find "$WIZARD_DIR/screens" -maxdepth 1 -type f -name 'connectivity-refresh-*.svg' 2>/dev/null | wc -l)"
  PROBE_PID="$(pgrep -fo '^/usr/bin/python3 -I -B /data/core/totem/releases/[^ /]+/bin/totem_wifi_nm_adapter.py --connectivity-probe-internal$' || true)"
  PROBE_PID="${PROBE_PID:-0}"
  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "$ELAPSED" "$PID" "$RSS_KB" "$FD_COUNT" "$THREAD_COUNT" "$CHILD_COUNT" \
    "$SCREEN_COUNT" "$REFRESH_COUNT" "$PROBE_PID" >>"$SAMPLES"
  if test "$ELAPSED" -ge "$DURATION_SEC"; then
    break
  fi
  REMAINING_SEC=$((DURATION_SEC - ELAPSED))
  SLEEP_SEC="$INTERVAL_SEC"
  if test "$SLEEP_SEC" -gt "$REMAINING_SEC"; then
    SLEEP_SEC="$REMAINING_SEC"
  fi
  sleep "$SLEEP_SEC"
done

capture_frame "02-end"
"$KEY_HELPER" --keys q --delay-sec 0.2 >"$ARTIFACT_DIR/exit-key.txt"
wait_for_exit
test -f "$SESSION_DIR/session-status.json"
cp "$SESSION_DIR/session-status.json" "$ARTIFACT_DIR/session-status.json"
python3 - "$ARTIFACT_DIR/session-status.json" <<'PY'
import json
import pathlib
import sys

status = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
checks = {
    "setup_cancelled": status.get("setup_cancelled") is True,
    "writer_not_called": status.get("writer_called") is False,
    "real_config_not_written": status.get("real_config_written") is False,
    "wifi_not_changed": status.get("wifi_changed") is False,
    "networkmanager_not_changed": status.get("networkmanager_changed") is False,
    "playback_playing": status.get("playback") == "playing",
    "player_process_present": status.get("process_counts", {}).get("player") == 1,
    "mpv_process_present": status.get("process_counts", {}).get("mpv") == 1,
    "service_restored": status.get("service_active") == "active",
    "session_success": status.get("service_result_after") == "success",
}
if not all(checks.values()):
    raise RuntimeError(f"cancel_session_invalid:{checks}")
PY

/opt/totem/bin/totem_open_settings_cleanup.sh \
  --reason c20-connectivity-session-soak-success >>"$LOG" 2>&1 || true
systemctl reset-failed "$SETTINGS_SERVICE" >>"$LOG" 2>&1 || true
systemctl start "$PLAYER_SERVICE" >>"$LOG" 2>&1
sleep 4

if test -n "$JOURNAL_CURSOR"; then
  journalctl --after-cursor "$JOURNAL_CURSOR" --no-pager >"$ARTIFACT_DIR/journal.delta.log" || true
else
  : >"$ARTIFACT_DIR/journal.delta.log"
fi

python3 - "$SAMPLES" "$ARTIFACT_DIR/resource-summary.json" "$DURATION_SEC" <<'PY'
import csv
import json
import pathlib
import sys

samples_path = pathlib.Path(sys.argv[1])
rows = list(csv.DictReader(samples_path.open(encoding="utf-8")))
if len(rows) < 2:
    raise RuntimeError("insufficient_samples")

def values(name: str) -> list[int]:
    return [int(row[name]) for row in rows]

rss = values("rss_kb")
fds = values("fd_count")
threads = values("thread_count")
children = values("child_count")
screens = values("screen_count")
refresh = values("refresh_file_count")
elapsed = values("elapsed_sec")
probe_pids = {value for value in values("probe_pid") if value > 0}
worker_sample_count = sum(value >= 2 for value in threads)
result = {
    "schema": "dadooh.c20.connectivity_session_soak.v1",
    "requested_duration_sec": int(sys.argv[3]),
    "observed_duration_sec": max(elapsed),
    "sample_count": len(rows),
    "rss_kb": {"first": rss[0], "last": rss[-1], "min": min(rss), "max": max(rss)},
    "fd_count": {"first": fds[0], "last": fds[-1], "max": max(fds)},
    "thread_count": {"first": threads[0], "last": threads[-1], "max": max(threads)},
    "child_count": {"first": children[0], "last": children[-1], "max": max(children)},
    "screen_count": {"first": screens[0], "last": screens[-1], "max": max(screens)},
    "refresh_file_count": {"first": refresh[0], "last": refresh[-1], "max": max(refresh)},
    "connectivity_worker_sample_count": worker_sample_count,
    "connectivity_probe_distinct_pids": sorted(probe_pids),
    "connectivity_probe_cycle_count": len(probe_pids),
}
checks = {
    "duration_reached": result["observed_duration_sec"] >= result["requested_duration_sec"],
    "duration_upper_bound": result["observed_duration_sec"] <= result["requested_duration_sec"] + 1,
    "rss_range_bounded_24mb": max(rss) - min(rss) <= 24 * 1024,
    "fd_growth_bounded": max(fds) <= fds[0] + 8,
    "thread_growth_bounded": max(threads) <= threads[0] + 4,
    "child_count_bounded": max(children) <= 4,
    "screen_ring_bounded": max(screens) <= 64,
    "refresh_files_bounded": max(refresh) <= 2,
    "connectivity_worker_observed": worker_sample_count >= 2,
    "multiple_exact_connectivity_probes_observed": len(probe_pids) >= 2,
}
result["checks"] = checks
result["resource_checks_passed"] = all(checks.values())
pathlib.Path(sys.argv[2]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if not result["resource_checks_passed"]:
    raise RuntimeError("bounded_session_checks_failed")
PY

CONFIG_SHA_AFTER="$(sha256sum "$CONFIG_PATH" | awk '{print $1}')"
CONTEXT_SHA_AFTER="$(sha256sum "$CONTEXT_PATH" | awk '{print $1}')"
PLAYER_RESTARTS_AFTER="$(systemctl show "$PLAYER_SERVICE" -p NRestarts --value)"
NETWORK_STATE_SHA_AFTER="$({
  /usr/bin/nmcli -t -f UUID,TYPE,DEVICE connection show --active
  /usr/sbin/ip -j -4 route show table main default
} | LC_ALL=C sort | sha256sum | awk '{print $1}')"

test "$CONFIG_SHA_AFTER" = "$CONFIG_SHA_BEFORE"
test "$CONTEXT_SHA_AFTER" = "$CONTEXT_SHA_BEFORE"
test "$PLAYER_RESTARTS_AFTER" = "$PLAYER_RESTARTS_BEFORE"
test "$NETWORK_STATE_SHA_AFTER" = "$NETWORK_STATE_SHA_BEFORE"
test "$(systemctl is-active "$PLAYER_SERVICE")" = "active"
test "$(systemctl is-active "$SETTINGS_SERVICE" 2>/dev/null || true)" = "inactive"
test "$(systemctl is-failed "$SETTINGS_SERVICE" 2>/dev/null || true)" = "inactive"
test ! -e "$LOCK_DIR"
test ! -e "$REQUEST_DIR/request.json"
test ! -e "$APPLY_POLICY_PATH"

{
  printf 'config_sha256_before=%s\n' "$CONFIG_SHA_BEFORE"
  printf 'config_sha256_after=%s\n' "$CONFIG_SHA_AFTER"
  printf 'context_sha256_before=%s\n' "$CONTEXT_SHA_BEFORE"
  printf 'context_sha256_after=%s\n' "$CONTEXT_SHA_AFTER"
  printf 'player_restarts_before=%s\n' "$PLAYER_RESTARTS_BEFORE"
  printf 'player_restarts_after=%s\n' "$PLAYER_RESTARTS_AFTER"
  printf 'network_state_sha256_before=%s\n' "$NETWORK_STATE_SHA_BEFORE"
  printf 'network_state_sha256_after=%s\n' "$NETWORK_STATE_SHA_AFTER"
  printf 'player='; systemctl is-active "$PLAYER_SERVICE"
  printf 'settings='; systemctl is-active "$SETTINGS_SERVICE" || true
  printf 'settings_failed='; systemctl is-failed "$SETTINGS_SERVICE" || true
} >"$ARTIFACT_DIR/final-state.txt"

python3 - "$ARTIFACT_DIR/resource-summary.json" "$ARTIFACT_DIR/result.json" <<'PY'
import json
import pathlib
import sys

resource = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
if resource.get("resource_checks_passed") is not True:
    raise RuntimeError("resource_summary_not_green")
result = {
    "schema": "dadooh.c20.connectivity_session_soak.v1",
    "passed": True,
    "resource_summary": resource,
    "final_checks": {
        "config_preserved": True,
        "retained_context_preserved": True,
        "network_state_preserved": True,
        "player_restarts_preserved": True,
        "player_restored": True,
        "settings_cleanup_complete": True,
        "cancel_without_writer_or_network_change": True,
        "playback_processes_restored": True,
    },
    "non_claims": [
        "not_a_24_hour_soak",
        "not_proof_against_slower_resource_leaks",
    ],
}
pathlib.Path(sys.argv[2]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

trap - EXIT INT TERM HUP
printf 'session_soak=passed\n'
