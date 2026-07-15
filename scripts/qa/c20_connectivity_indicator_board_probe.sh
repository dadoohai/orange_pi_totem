#!/usr/bin/env bash
set -euo pipefail

ARTIFACT_DIR="${1:-/tmp/c20-connectivity-indicator-probe}"
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

case "$ARTIFACT_DIR" in
  /tmp/?*) ;;
  *) echo "artifact directory must be a new path below /tmp" >&2; exit 2 ;;
esac
test ! -e "$ARTIFACT_DIR"
install -d -m 0700 "$ARTIFACT_DIR" "$ARTIFACT_DIR/captures" "$ARTIFACT_DIR/screens"
LOG="$ARTIFACT_DIR/probe.log"
: >"$LOG"

log() {
  printf '%s %s\n' "$(date -Is)" "$*" | tee -a "$LOG"
}

capture_frame() {
  local name="$1"
  ffmpeg -hide_banner -loglevel error -f fbdev -i /dev/fb0 -frames:v 1 -update 1 \
    "$ARTIFACT_DIR/captures/$name.jpg" >>"$LOG" 2>&1
  sha256sum "$ARTIFACT_DIR/captures/$name.jpg" >>"$LOG"
}

assert_online_indicator() {
  local name="$1" dimensions width height raw_path
  dimensions="$(cat /sys/class/graphics/fb0/virtual_size)"
  width="${dimensions%,*}"
  height="${dimensions#*,}"
  raw_path="$ARTIFACT_DIR/captures/$name.rgb24"
  ffmpeg -hide_banner -loglevel error -f fbdev -i /dev/fb0 -frames:v 1 \
    -pix_fmt rgb24 -f rawvideo "$raw_path" >>"$LOG" 2>&1
  python3 - "$raw_path" "$ARTIFACT_DIR/$name-pixel-check.json" "$width" "$height" <<'PY'
import json
import pathlib
import sys

raw_path = pathlib.Path(sys.argv[1])
width = int(sys.argv[3])
height = int(sys.argv[4])
if width < 1024 or height < 768:
    raise RuntimeError("framebuffer_too_small_for_landscape_probe")
raw = raw_path.read_bytes()
if len(raw) != width * height * 3:
    raise RuntimeError("unexpected_rgb24_size")
x_offset = (width - 1024) // 2
y_offset = (height - 768) // 2
x_start, x_end = x_offset + 704, x_offset + 780
y_start, y_end = y_offset + 34, y_offset + 68
green = bytes.fromhex("22c55e")
cyan = bytes.fromhex("22d3ee")
port_inner = bytes.fromhex("0f2533")
green_pixels = 0
cyan_pixels = 0
port_inner_pixels = 0
region_bytes = bytearray()
for y in range(y_start, y_end):
    row_start = (y * width + x_start) * 3
    row_end = (y * width + x_end) * 3
    row = raw[row_start:row_end]
    region_bytes.extend(row)
    green_pixels += sum(row[index:index + 3] == green for index in range(0, len(row), 3))
    cyan_pixels += sum(row[index:index + 3] == cyan for index in range(0, len(row), 3))
for y in range(y_offset + 44, y_offset + 54):
    row_start = (y * width + x_offset + 716) * 3
    row_end = (y * width + x_offset + 738) * 3
    row = raw[row_start:row_end]
    port_inner_pixels += sum(row[index:index + 3] == port_inner for index in range(0, len(row), 3))
result = {
    "schema": "dadooh.c20.connectivity_indicator_pixel_check.v1",
    "framebuffer": {"width": width, "height": height},
    "region": {"x_start": x_start, "x_end": x_end, "y_start": y_start, "y_end": y_end},
    "green_online_pixels": green_pixels,
    "cyan_ethernet_pixels": cyan_pixels,
    "ethernet_port_inner_pixels": port_inner_pixels,
    "passed": green_pixels >= 50 and cyan_pixels >= 200 and port_inner_pixels >= 120,
}
result_path = pathlib.Path(sys.argv[2])
region_path = result_path.with_suffix(".rgb24")
region_path.write_bytes(bytes(region_bytes))
result["region_rgb24_path"] = region_path.name
result["region_rgb24_bytes"] = len(region_bytes)
result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if not result["passed"]:
    raise RuntimeError("online_ethernet_indicator_not_presented")
PY
  rm -f "$raw_path"
}

copy_latest_screen() {
  local name="$1"
  local expected_suffix="${2:-}" latest
  latest="$(find "$WIZARD_DIR/screens" -maxdepth 1 -type f -name '*.svg' \
    -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)"
  test -n "$latest"
  if test -n "$expected_suffix"; then
    case "$(basename "$latest")" in
      *"$expected_suffix") ;;
      *) return 1 ;;
    esac
  fi
  cp "$latest" "$ARTIFACT_DIR/screens/$name-$(basename "$latest")"
  grep -o 'id="connectivity-indicator"[^>]*' "$latest" \
    >"$ARTIFACT_DIR/$name-source-screen-connectivity.txt" || true
}

wait_for_wizard() {
  local index
  for index in $(seq 1 30); do
    if pgrep -af 'totem_setup_visual_wizard.py' >"$ARTIFACT_DIR/wizard-process.txt"; then
      log "wizard_seen_at=${index}s"
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
    if ! pgrep -af 'totem_setup_visual_wizard.py' >/dev/null 2>&1 \
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
    --reason c20-connectivity-indicator-probe-final >>"$LOG" 2>&1 || cleanup_failed=1
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
test -f "$CONFIG_PATH"
test -f "$CONTEXT_PATH"
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

{
  date -Is
  printf 'player='; systemctl is-active "$PLAYER_SERVICE"
  printf 'settings='; systemctl is-active "$SETTINGS_SERVICE" || true
  printf 'config_sha256=%s\n' "$CONFIG_SHA_BEFORE"
  printf 'context_sha256=%s\n' "$CONTEXT_SHA_BEFORE"
  printf 'player_restarts=%s\n' "$PLAYER_RESTARTS_BEFORE"
  printf 'network_state_sha256=%s\n' "$NETWORK_STATE_SHA_BEFORE"
} >"$ARTIFACT_DIR/state.before.txt"

systemctl reset-failed "$SETTINGS_SERVICE" >>"$LOG" 2>&1 || true
systemctl start "$PLAYER_SERVICE" >>"$LOG" 2>&1
rm -rf "$WIZARD_DIR"

log "start_settings"
systemctl start "$SETTINGS_SERVICE" >"$ARTIFACT_DIR/settings-start.stdout" \
  2>"$ARTIFACT_DIR/settings-start.stderr" &

wait_for_wizard
capture_frame "01-initial"
copy_latest_screen "01-initial"

sleep 3
capture_frame "02-connected"
copy_latest_screen "02-connected"
assert_online_indicator "02-connected"

"$KEY_HELPER" --keys up,right --delay-sec 0.3 >"$ARTIFACT_DIR/navigation.txt"
sleep 1
capture_frame "03-connection-step"
copy_latest_screen "03-connection-step" "-02-connection.svg"
assert_online_indicator "03-connection-step"

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
  --reason c20-connectivity-indicator-probe-success >>"$LOG" 2>&1 || true
systemctl reset-failed "$SETTINGS_SERVICE" >>"$LOG" 2>&1 || true
systemctl start "$PLAYER_SERVICE" >>"$LOG" 2>&1
sleep 4

python3 - "$ARTIFACT_DIR/connectivity-live.json" <<'PY'
import importlib.util
import json
import pathlib
import sys

source = pathlib.Path("/data/core/totem/current/bin/totem_wifi_nm_adapter.py")
spec = importlib.util.spec_from_file_location("c20_connectivity_probe", source)
if spec is None or spec.loader is None:
    raise RuntimeError("adapter_import_failed")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
indicator = module.collect_connectivity_indicator(timeout_sec=2.0)
if indicator.get("internet") != "online":
    raise RuntimeError("dadooh_service_not_reachable")
if indicator.get("transport") != "ethernet":
    raise RuntimeError("verified_ethernet_transport_missing")
if indicator.get("guardrails", {}).get("external_connectivity_probe") is not True:
    raise RuntimeError("service_probe_not_executed")
path = pathlib.Path(sys.argv[1])
path.write_text(json.dumps(indicator, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

CONFIG_SHA_AFTER="$(sha256sum "$CONFIG_PATH" | awk '{print $1}')"
CONTEXT_SHA_AFTER="$(sha256sum "$CONTEXT_PATH" | awk '{print $1}')"
PLAYER_RESTARTS_AFTER="$(systemctl show "$PLAYER_SERVICE" -p NRestarts --value)"
NETWORK_STATE_SHA_AFTER="$({
  /usr/bin/nmcli -t -f UUID,TYPE,DEVICE connection show --active
  /usr/sbin/ip -j -4 route show table main default
} | LC_ALL=C sort | sha256sum | awk '{print $1}')"
SETTINGS_ACTIVE="$(systemctl is-active "$SETTINGS_SERVICE" 2>/dev/null || true)"
SETTINGS_FAILED="$(systemctl is-failed "$SETTINGS_SERVICE" 2>/dev/null || true)"

{
  date -Is
  printf 'player='; systemctl is-active "$PLAYER_SERVICE"
  printf 'settings=%s\n' "$SETTINGS_ACTIVE"
  printf 'settings_failed=%s\n' "$SETTINGS_FAILED"
  printf 'config_sha256=%s\n' "$CONFIG_SHA_AFTER"
  printf 'context_sha256=%s\n' "$CONTEXT_SHA_AFTER"
  printf 'player_restarts=%s\n' "$PLAYER_RESTARTS_AFTER"
  printf 'network_state_sha256=%s\n' "$NETWORK_STATE_SHA_AFTER"
  printf 'settings_lock='; test -e "$LOCK_DIR" && echo present || echo absent
  printf 'settings_request='; test -e "$REQUEST_DIR/request.json" && echo present || echo absent
} >"$ARTIFACT_DIR/state.after.txt"

test "$CONFIG_SHA_AFTER" = "$CONFIG_SHA_BEFORE"
test "$CONTEXT_SHA_AFTER" = "$CONTEXT_SHA_BEFORE"
test "$PLAYER_RESTARTS_AFTER" = "$PLAYER_RESTARTS_BEFORE"
test "$NETWORK_STATE_SHA_AFTER" = "$NETWORK_STATE_SHA_BEFORE"
test "$(systemctl is-active "$PLAYER_SERVICE")" = "active"
test "$SETTINGS_ACTIVE" = "inactive"
test "$SETTINGS_FAILED" = "inactive"
test ! -e "$LOCK_DIR"
test ! -e "$REQUEST_DIR/request.json"
test ! -e "$APPLY_POLICY_PATH"

python3 - "$ARTIFACT_DIR/result.json" <<'PY'
import json
import pathlib
import sys

result = {
    "schema": "dadooh.c20.connectivity_indicator_board_probe.v1",
    "passed": True,
    "checks": {
        "online_ethernet_presented": True,
        "connection_step_reached": True,
        "live_service_probe_online": True,
        "config_preserved": True,
        "retained_context_preserved": True,
        "network_state_preserved": True,
        "cancel_without_writer_or_network_change": True,
        "playback_processes_restored": True,
        "player_restored": True,
        "settings_cleanup_complete": True,
    },
}
pathlib.Path(sys.argv[1]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

trap - EXIT INT TERM HUP
printf 'visual_probe=passed\n'
