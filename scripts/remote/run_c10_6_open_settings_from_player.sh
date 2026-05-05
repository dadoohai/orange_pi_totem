#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
REMOTE_TTY="2"
RUN_TIMEOUT_SEC="1800"
PREVIEW_SEC="12"
REMOTE_DIR="/tmp/dadooh-c10-6-open-settings"
REMOTE_OUT_DIR="/tmp/dadooh-c10-6-open-settings-from-player"
REMOTE_WIZARD_OUT_DIR="/tmp/dadooh-c10-6-visual-wizard"
REMOTE_HANDOFF_OUT_DIR="/tmp/dadooh-c10-6-handoff"
REMOTE_PRIVATE_VALUES="/tmp/dadooh-c10-6-private/private-values.json"
PRIVATE_SOURCE_MODE="tmp-file"
PROFILE_NAME="dadooh-c9-8-wifi-persistent"
PAUSE_CONFIRM_PHRASE="CONFIRMO C10.6 ABRIR CONFIGURACOES COM PAUSA DO PLAYER"
DRY_RUN_CONFIRM_PHRASE="CONFIRMO CONFIGURACOES DRY RUN C10.6 COM PAUSA DO PLAYER"
SOURCE_CONFIRM_PHRASE="CONFIRMO USAR CONFIG ATIVA COMO FONTE PRIVADA C10.6"
REAL_WRITE_CONFIRM_PHRASE="CONFIRMO CONFIGURACOES WRITER REAL C10.6"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_6_open_settings_from_player.sh <host> [mode] [--tty N] [--timeout-sec N] [--preview-sec N]

Modes:
  --prepare-only
      Copy scripts to /tmp and run non-invasive checks. Does not touch service,
      config, writer or Wi-Fi.

  --preview-open-settings
      Requires confirmation. Shows the visual setup preview with the player
      paused and then restores the player.

  --run-open-cancel
      Requires confirmation. Opens the real visual setup from the running
      player, expects the operator to cancel, then restores the player.

  --run-open-complete-dry-run
      Requires confirmation. Opens visual setup, generates a candidate and
      performs private handoff/C5.1 real-dry-run. Does not call writer and does
      not write /data/config.

  --run-open-complete-real-write
      Requires confirmation and delegates to the already validated C10.4 writer
      runner. This wrapper does not reimplement writer behavior.

Private source options for --run-open-complete-dry-run:
  --private-values /tmp/.../private-values.json
  --private-values-from-active-config
      Requires the exact source confirmation before reading only approved
      endpoint/credential categories from the active config into a restricted
      temporary file. Values are never printed.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only)
      MODE="prepare-only"
      ;;
    --preview-open-settings)
      MODE="preview-open-settings"
      ;;
    --run-open-cancel)
      MODE="run-open-cancel"
      ;;
    --run-open-complete-dry-run)
      MODE="run-open-complete-dry-run"
      ;;
    --run-open-complete-real-write)
      MODE="run-open-complete-real-write"
      ;;
    --private-values)
      shift
      REMOTE_PRIVATE_VALUES="${1:-}"
      ;;
    --private-values-from-active-config)
      PRIVATE_SOURCE_MODE="active-config"
      REMOTE_PRIVATE_VALUES="/tmp/dadooh-c10-6-private-from-active/private-values.json"
      ;;
    --tty)
      shift
      REMOTE_TTY="${1:-}"
      ;;
    --timeout-sec)
      shift
      RUN_TIMEOUT_SEC="${1:-}"
      ;;
    --preview-sec)
      shift
      PREVIEW_SEC="${1:-}"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      HOST="$1"
      ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|preview-open-settings|run-open-cancel|run-open-complete-dry-run|run-open-complete-real-write)
    ;;
  *)
    echo "error: unsupported mode $MODE" >&2
    exit 2
    ;;
esac

if [ -z "$HOST" ]; then
  echo "error: host is required; pass it explicitly, for example root@<board-host>" >&2
  exit 2
fi

case "$REMOTE_TTY" in
  ''|*[!0-9]*|0)
    echo "error: --tty must be a positive integer" >&2
    exit 2
    ;;
esac

case "$RUN_TIMEOUT_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --timeout-sec must be a positive integer" >&2
    exit 2
    ;;
esac

case "$PREVIEW_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --preview-sec must be a positive integer" >&2
    exit 2
    ;;
esac

case "$REMOTE_PRIVATE_VALUES" in
  /tmp/*)
    ;;
  *)
    echo "error: --private-values must be under /tmp on the board" >&2
    exit 2
    ;;
esac

case "$PRIVATE_SOURCE_MODE" in
  tmp-file|active-config)
    ;;
  *)
    echo "error: unsupported private source mode" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BOARD_DIR="$REPO_ROOT/scripts/board"

LOCAL_VISUAL_WIZARD="$BOARD_DIR/totem_setup_visual_wizard.py"
LOCAL_WIZARD="$BOARD_DIR/totem_setup_local_wizard.py"
LOCAL_MINIMAL_SERVER="$BOARD_DIR/totem_setup_minimal_server.py"
LOCAL_CONTRACT="$BOARD_DIR/totem_config_contract_validate.py"
LOCAL_WIFI_ADAPTER="$BOARD_DIR/totem_wifi_nm_adapter.py"
LOCAL_STATUS_AGGREGATE="$BOARD_DIR/totem_status_aggregate.py"
LOCAL_STATUS_RENDER="$BOARD_DIR/totem_status_render_preview.py"
LOCAL_HANDOFF="$BOARD_DIR/totem_visual_setup_writer_handoff.py"
LOCAL_SPLASH="$BOARD_DIR/totem_visual_splash.py"
LOCAL_C10_4_RUNNER="$SCRIPT_DIR/run_c10_4_product_surface_writer_real.sh"

for path in \
  "$LOCAL_VISUAL_WIZARD" "$LOCAL_WIZARD" "$LOCAL_CONTRACT" "$LOCAL_WIFI_ADAPTER" \
  "$LOCAL_MINIMAL_SERVER" "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_HANDOFF" "$LOCAL_SPLASH"
do
  if [ ! -f "$path" ]; then
    echo "error: missing local input $path" >&2
    exit 1
  fi
done

confirm_exact() {
  local phrase="$1"
  local reason="$2"
  echo
  echo "$reason"
  echo "Type exactly:"
  echo "$phrase"
  printf '> '
  IFS= read -r AUTH_TEXT
  if [ "$AUTH_TEXT" != "$phrase" ]; then
    echo "Authorization text did not match. Aborting." >&2
    exit 20
  fi
}

prepare_workspace() {
  echo "Preparing C10.6 open-settings workspace on target board"
  ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR'"

  echo "Copying C10.6 inputs to temporary board workspace"
  scp \
    "$LOCAL_VISUAL_WIZARD" "$LOCAL_WIZARD" "$LOCAL_CONTRACT" "$LOCAL_WIFI_ADAPTER" \
    "$LOCAL_MINIMAL_SERVER" "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_HANDOFF" "$LOCAL_SPLASH" \
    "$HOST:$REMOTE_DIR/" >/dev/null
}

run_prepare_checks() {
  echo "Running C10.6 prepare checks on the board"
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail

VISUAL="$REMOTE_DIR/totem_setup_visual_wizard.py"
WIZARD="$REMOTE_DIR/totem_setup_local_wizard.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
WIFI_ADAPTER="$REMOTE_DIR/totem_wifi_nm_adapter.py"
HANDOFF="$REMOTE_DIR/totem_visual_setup_writer_handoff.py"
SPLASH="$REMOTE_DIR/totem_visual_splash.py"
SCRIPTED_OUT="$REMOTE_OUT_DIR/prepare-scripted-visual"

umask 077
rm -rf "$SCRIPTED_OUT"
mkdir -p "$REMOTE_DIR" "$REMOTE_OUT_DIR" "$SCRIPTED_OUT"
chmod 700 "$REMOTE_DIR" "$REMOTE_OUT_DIR" "$SCRIPTED_OUT"

python3 "$CONTRACT" --self-test
python3 "$WIFI_ADAPTER" --self-test --out-dir "$REMOTE_OUT_DIR/adapter-self-test" >/dev/null
python3 "$WIZARD" --self-test
python3 "$VISUAL" --self-test
python3 "$HANDOFF" --self-test
python3 "$SPLASH" --self-test
python3 "$VISUAL" \
  --scripted \
  --environment-id ENV-C10-6-OPEN-SETTINGS \
  --rotation-key landscape \
  --network-step configured_wifi \
  --out-dir "$SCRIPTED_OUT" >/dev/null
python3 "$CONTRACT" --candidate "$SCRIPTED_OUT/config.candidate.json" --allow-mock --out-dir "$REMOTE_OUT_DIR/prepare-allow" >/dev/null
if python3 "$CONTRACT" --candidate "$SCRIPTED_OUT/config.candidate.json" --real-dry-run --out-dir "$REMOTE_OUT_DIR/prepare-real" >/dev/null; then
  echo "error: prepare real-dry-run unexpectedly passed with placeholders" >&2
  exit 1
fi
python3 - "$SCRIPTED_OUT/setup-status.json" <<'PY'
import json
import pathlib
import sys
status = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
interface = status.get("interface", {})
network = status.get("network", {})
assert interface.get("mode") == "local_visual_mpv_drm_keyboard_controlled"
assert interface.get("linux_prompt_visible") is False
assert network.get("network_step") == "existing_configured_wifi"
PY

echo "remote C10.6 prepare checks: ok"
REMOTE_PREP
}

run_open_settings() {
  local remote_mode="$1"
  local expected_result="$2"
  local expected_network_step="$3"
  local confirm_phrase="$4"
  local confirm_reason="$5"

  confirm_exact "$confirm_phrase" "$confirm_reason"
  ssh "$HOST" \
    "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_WIZARD_OUT_DIR='$REMOTE_WIZARD_OUT_DIR' REMOTE_HANDOFF_OUT_DIR='$REMOTE_HANDOFF_OUT_DIR' REMOTE_PRIVATE_VALUES='$REMOTE_PRIVATE_VALUES' PRIVATE_SOURCE_MODE='$PRIVATE_SOURCE_MODE' REMOTE_TTY='$REMOTE_TTY' RUN_TIMEOUT_SEC='$RUN_TIMEOUT_SEC' PREVIEW_SEC='$PREVIEW_SEC' MODE='$remote_mode' EXPECTED_RESULT='$expected_result' EXPECTED_NETWORK_STEP='$expected_network_step' bash -s" <<'REMOTE_RUN'
set -euo pipefail

VISUAL="$REMOTE_DIR/totem_setup_visual_wizard.py"
HANDOFF="$REMOTE_DIR/totem_visual_setup_writer_handoff.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
AGGREGATE="$REMOTE_DIR/totem_status_aggregate.py"
SPLASH="$REMOTE_DIR/totem_visual_splash.py"
RUN_OUT="$REMOTE_OUT_DIR/$MODE"
FINAL_STATUS="$RUN_OUT/final-status.json"
WIZARD_OUT="$REMOTE_WIZARD_OUT_DIR-$MODE"
HANDOFF_OUT="$REMOTE_HANDOFF_OUT_DIR-$MODE"
TTY_DEVICE="/dev/tty$REMOTE_TTY"
GETTY_UNITS=("getty@tty1.service" "getty@tty${REMOTE_TTY}.service")
WIZARD_RC="not_run"
HANDOFF_RC="not_run"
PRIVATE_SOURCE_TEMP_REMOVED="false"
ACTIVE_CONFIG_PRIVATE_SOURCE_USED="false"
SERVICE_STOP_ATTEMPTED="false"
SERVICE_RESTORE_ATTEMPTED="false"
WRITER_CALLED="false"
REAL_CONFIG_WRITTEN="false"
INITIAL_SERVICE_ACTIVE="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
INITIAL_SERVICE_ENABLED="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"
declare -A GETTY_ACTIVE
declare -A GETTY_ENABLED

umask 077
rm -rf "$RUN_OUT" "$WIZARD_OUT" "$HANDOFF_OUT"
mkdir -p "$RUN_OUT" "$WIZARD_OUT" "$HANDOFF_OUT"
chmod 700 "$RUN_OUT" "$WIZARD_OUT" "$HANDOFF_OUT"

for unit in "${GETTY_UNITS[@]}"; do
  GETTY_ACTIVE["$unit"]="$(systemctl is-active "$unit" 2>/dev/null || true)"
  GETTY_ENABLED["$unit"]="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
done

process_counts() {
  python3 - <<'PY'
import os
import pathlib
counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    names = [pathlib.Path(part).name.lower() for part in parts]
    if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
        counts["setup"] += 1
    if any("totem_status_renderer" in name for name in names):
        counts["renderer"] += 1
    if any(name == "mpv" for name in names):
        counts["mpv"] += 1
    if "kiosk.py" in names:
        counts["player"] += 1
print(f"{counts['player']} {counts['mpv']} {counts['renderer']} {counts['setup']}")
PY
}

refresh_public_status() {
  if [ -f /opt/totem/bin/totem_status_aggregate.py ]; then
    PYTHONPATH=/opt/totem/bin python3 /opt/totem/bin/totem_status_aggregate.py >/dev/null 2>&1 || true
  else
    PYTHONPATH="$REMOTE_DIR" python3 "$AGGREGATE" >/dev/null 2>&1 || true
  fi
}

read_json_value() {
  local path="$1"
  local key="$2"
  python3 - "$path" "$key" <<'PY'
import json
import pathlib
import sys
try:
    data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    key = sys.argv[2]
    value = data.get("public_state") or data.get("state") if key == "public_state" else data.get(key)
    print(value if isinstance(value, str) else "unknown")
except Exception:
    print("unknown")
PY
}

wait_player_running() {
  for _ in $(seq 1 90); do
    refresh_public_status
    state="$(read_json_value /tmp/dadooh-status/status.json public_state)"
    playback="$(read_json_value /tmp/kiosky-status.json playback_state)"
    set -- $(process_counts)
    if [ "$state" = "player_running" ] && [ "$playback" = "playing" ] && [ "${1:-0}" -ge 1 ] && [ "${2:-0}" -ge 1 ] && [ "${3:-0}" -eq 0 ] && [ "${4:-0}" -eq 0 ]; then
      return 0
    fi
    sleep 2
  done
  return 1
}

show_transition() {
  local mode="$1"
  command -v chvt >/dev/null 2>&1 && chvt "$REMOTE_TTY" >/dev/null 2>&1 || true
  printf '\033c\033[2J\033[3J\033[H\033[?25l' > "$TTY_DEVICE" 2>/dev/null || true
  env TERM=linux python3 "$SPLASH" "$mode" --status-out "$RUN_OUT/splash-$mode-status.json" <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
}

restore_getty() {
  for unit in "${GETTY_UNITS[@]}"; do
    if [ "${GETTY_ENABLED[$unit]}" = "enabled" ]; then
      systemctl enable "$unit" >/dev/null 2>&1 || true
    else
      systemctl disable "$unit" >/dev/null 2>&1 || true
    fi
    if [ "${GETTY_ACTIVE[$unit]}" = "active" ]; then
      systemctl start "$unit" >/dev/null 2>&1 || true
    else
      systemctl stop "$unit" >/dev/null 2>&1 || true
    fi
  done
}

restore_service() {
  SERVICE_RESTORE_ATTEMPTED="true"
  if [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
    systemctl enable kiosky-player.service >/dev/null 2>&1 || true
  fi
  if [ "$INITIAL_SERVICE_ACTIVE" = "active" ] || [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
    show_transition player || true
    systemctl start kiosky-player.service >/dev/null 2>&1 || true
  fi
}

kill_visual_if_running() {
  python3 - "$VISUAL" "$WIZARD_OUT" <<'PY'
import os
import pathlib
import signal
import sys
import time
visual = sys.argv[1]
out = sys.argv[2]
pids = []
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == os.getpid():
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    joined = " ".join(parts)
    if visual in joined or out in joined:
        pids.append(int(proc.name))
for pid in pids:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
time.sleep(2)
for pid in pids:
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
PY
}

cleanup_private_source() {
  if [ "$PRIVATE_SOURCE_MODE" = "active-config" ]; then
    rm -rf "$(dirname "$REMOTE_PRIVATE_VALUES")" || true
    if [ ! -e "$REMOTE_PRIVATE_VALUES" ]; then
      PRIVATE_SOURCE_TEMP_REMOVED="true"
    fi
  fi
}

prepare_private_values_from_active_config_if_requested() {
  if [ "$PRIVATE_SOURCE_MODE" != "active-config" ]; then
    return 0
  fi
  ACTIVE_CONFIG_PRIVATE_SOURCE_USED="true"
  python3 - "$REMOTE_PRIVATE_VALUES" <<'PY'
import json
import os
import pathlib
import stat
import sys
target = pathlib.Path(sys.argv[1])
active = pathlib.Path("/data/config/config.json")
if not str(target).startswith("/tmp/"):
    raise SystemExit("private_values_target_not_tmp")
target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
if stat.S_IMODE(target.parent.stat().st_mode) != 0o700:
    target.parent.chmod(0o700)
with active.open("r", encoding="utf-8") as handle:
    config = json.load(handle)
payload = {}
for field in ("api_url", "api_key", "station_id"):
    value = config.get(field)
    if isinstance(value, str) and value.strip():
        payload[field] = value.strip()
if "api_url" not in payload or "api_key" not in payload:
    raise SystemExit("active_config_missing_private_categories")
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
PY
}

validate_private_values_if_needed() {
  if [ "$MODE" != "run-open-complete-dry-run" ]; then
    return 0
  fi
  python3 - "$REMOTE_PRIVATE_VALUES" <<'PY'
import pathlib
import stat
import sys
path = pathlib.Path(sys.argv[1])
if not str(path).startswith("/tmp/") or path.is_symlink() or not path.exists():
    raise SystemExit("private_values_not_ready")
if stat.S_IMODE(path.parent.stat().st_mode) != 0o700 or stat.S_IMODE(path.stat().st_mode) != 0o600:
    raise SystemExit("private_values_not_restricted")
PY
}

write_final_status() {
  wait_player_running || true
  python3 - "$FINAL_STATUS" "$RUN_OUT" "$WIZARD_OUT" "$HANDOFF_OUT/setup-status.json" \
    "$MODE" "$EXPECTED_RESULT" "$EXPECTED_NETWORK_STEP" "$WIZARD_RC" "$HANDOFF_RC" \
    "$INITIAL_SERVICE_ACTIVE" "$INITIAL_SERVICE_ENABLED" "$SERVICE_STOP_ATTEMPTED" "$SERVICE_RESTORE_ATTEMPTED" \
    "$(systemctl is-active kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null || true)" \
    "$(read_json_value /tmp/dadooh-status/status.json public_state)" \
    "$(read_json_value /tmp/kiosky-status.json playback_state)" \
    "$WRITER_CALLED" "$REAL_CONFIG_WRITTEN" "$PRIVATE_SOURCE_MODE" "$ACTIVE_CONFIG_PRIVATE_SOURCE_USED" "$PRIVATE_SOURCE_TEMP_REMOVED" <<'PY'
import json
import os
import pathlib
import stat
import sys

target = pathlib.Path(sys.argv[1])
run_out = pathlib.Path(sys.argv[2])
wizard_out = pathlib.Path(sys.argv[3])
handoff_status_path = pathlib.Path(sys.argv[4])
mode = sys.argv[5]
expected_result = sys.argv[6]
expected_network_step = sys.argv[7]
wizard_rc = sys.argv[8]
handoff_rc = sys.argv[9]
initial_active = sys.argv[10] or "unknown"
initial_enabled = sys.argv[11] or "unknown"
service_stop_attempted = sys.argv[12] == "true"
service_restore_attempted = sys.argv[13] == "true"
service_active = sys.argv[14] or "unknown"
service_enabled = sys.argv[15] or "unknown"
nrestarts = sys.argv[16] or "unknown"
public_state = sys.argv[17] or "unknown"
playback = sys.argv[18] or "unknown"
writer_called = sys.argv[19] == "true"
real_config_written = sys.argv[20] == "true"
private_source_mode = sys.argv[21]
active_config_private_source_used = sys.argv[22] == "true"
private_source_temp_removed = sys.argv[23] == "true"

def load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}

setup_status = load_json(wizard_out / "setup-status.json")
handoff_status = load_json(handoff_status_path)
network = setup_status.get("network") if isinstance(setup_status.get("network"), dict) else {}
validation = setup_status.get("validation") if isinstance(setup_status.get("validation"), dict) else {}
interface = setup_status.get("interface") if isinstance(setup_status.get("interface"), dict) else {}
counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    names = [pathlib.Path(part).name.lower() for part in parts]
    if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
        counts["setup"] += 1
    if any("totem_status_renderer" in name for name in names):
        counts["renderer"] += 1
    if any(name == "mpv" for name in names):
        counts["mpv"] += 1
    if "kiosk.py" in names:
        counts["player"] += 1

payload = {
    "schema_version": "dadooh-c10.6-open-settings-from-player.v1",
    "mode": mode,
    "expected_result": expected_result,
    "wizard_rc": wizard_rc,
    "handoff_rc": handoff_rc,
    "visual_wizard_opened": (wizard_out / "screens").exists() or bool(setup_status) or (wizard_out / "setup-cancelled.json").exists(),
    "visual_candidate_generated": (wizard_out / "config.candidate.json").exists(),
    "setup_cancelled": (wizard_out / "setup-cancelled.json").exists(),
    "private_handoff_passed": handoff_status.get("result") == "passed",
    "private_real_dry_run_passed": bool(
        handoff_status.get("contract_validation", {}).get("private_real_dry_run", {}).get("valid")
    ),
    "orientation_category": {0: "landscape", 90: "portrait_right", 180: "inverted", 270: "portrait_left"}.get(
        validation.get("rotation_degrees"), "unknown"
    ),
    "rotation_degrees": validation.get("rotation_degrees", "unknown"),
    "network_step": network.get("network_step", "unknown"),
    "network_step_expected": expected_network_step,
    "wifi_networks_found_count": network.get("wifi_networks_found_count", "unknown"),
    "selected_network_present": bool(network.get("selected_network_present", False)),
    "selected_network_signal_bucket": network.get("selected_network_signal_bucket", "unknown"),
    "selected_network_security_present": network.get("selected_network_security_present", "unknown"),
    "linux_prompt_visible": bool(interface.get("linux_prompt_visible", False)),
    "service_initial_active": initial_active,
    "service_initial_enabled": initial_enabled,
    "service_stop_attempted": service_stop_attempted,
    "service_restore_attempted": service_restore_attempted,
    "service_active": service_active,
    "service_enabled": service_enabled,
    "nrestarts": nrestarts,
    "public_state": public_state,
    "playback": playback,
    "process_counts": counts,
    "writer_called": writer_called,
    "real_config_written": real_config_written,
    "real_config_read": active_config_private_source_used,
    "real_config_read_authorized_for_private_source": active_config_private_source_used,
    "private_source_mode": private_source_mode,
    "private_source_temp_removed": private_source_temp_removed,
    "wifi_changed": False,
    "networkmanager_changed": False,
    "hotspot_created": False,
    "portal_created": False,
    "kiosky_player_repo_changed": False,
    "root_read_only_enabled": False,
    "power_cut_tested": False,
    "credential_values_published": False,
    "network_identifiers_published": False,
    "environment_identifier_raw_published": False,
    "config_content_published": False,
    "raw_logs_written": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
assert stat.S_IMODE(run_out.stat().st_mode) == 0o700
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

on_exit() {
  rc="$?"
  trap - EXIT INT TERM HUP
  kill_visual_if_running || true
  cleanup_private_source || true
  restore_service || true
  write_final_status || true
  restore_getty || true
  exit "$rc"
}
trap on_exit EXIT INT TERM HUP

for unit in "${GETTY_UNITS[@]}"; do
  systemctl stop "$unit" >/dev/null 2>&1 || true
done

prepare_private_values_from_active_config_if_requested
validate_private_values_if_needed

show_transition setup || true
if [ "$INITIAL_SERVICE_ACTIVE" = "active" ] || [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
  SERVICE_STOP_ATTEMPTED="true"
  systemctl stop kiosky-player.service >/dev/null 2>&1 || true
  for _ in $(seq 1 30); do
    set -- $(process_counts)
    if [ "${1:-0}" -eq 0 ] && [ "${2:-0}" -eq 0 ] && [ "${3:-0}" -eq 0 ] && [ "${4:-0}" -eq 0 ]; then
      break
    fi
    sleep 1
  done
fi
show_transition setup || true

set -- $(process_counts)
if [ "${1:-0}" -ne 0 ] || [ "${2:-0}" -ne 0 ] || [ "${3:-0}" -ne 0 ] || [ "${4:-0}" -ne 0 ]; then
  echo "hdmi_not_free_after_player_pause" >&2
  exit 42
fi

set +e
if [ "$MODE" = "preview-open-settings" ]; then
  setsid openvt -c "$REMOTE_TTY" -s -f -w -- \
    env TERM=linux PYTHONPATH="$REMOTE_DIR" /usr/bin/python3 "$VISUAL" \
      --out-dir "$WIZARD_OUT" --preview-screens --show-preview --auto-exit-sec "$PREVIEW_SEC" >/dev/null 2>&1
  WIZARD_RC="$?"
else
  setsid openvt -c "$REMOTE_TTY" -s -f -w -- \
    env TERM=linux PYTHONPATH="$REMOTE_DIR" /usr/bin/python3 "$VISUAL" \
      --out-dir "$WIZARD_OUT" >/dev/null 2>&1 &
  OPENVT_PID="$!"
  deadline=$(( $(date +%s) + RUN_TIMEOUT_SEC ))
  while kill -0 "$OPENVT_PID" 2>/dev/null && [ "$(date +%s)" -lt "$deadline" ]; do
    sleep 2
  done
  if kill -0 "$OPENVT_PID" 2>/dev/null; then
    kill -TERM "-$OPENVT_PID" 2>/dev/null || kill -TERM "$OPENVT_PID" 2>/dev/null || true
    sleep 3
    kill -KILL "-$OPENVT_PID" 2>/dev/null || kill -KILL "$OPENVT_PID" 2>/dev/null || true
    kill_visual_if_running || true
    WIZARD_RC="124"
  else
    wait "$OPENVT_PID"
    WIZARD_RC="$?"
  fi
fi
set -e

if [ "$EXPECTED_RESULT" = "preview" ]; then
  if [ ! -d "$WIZARD_OUT/screens" ]; then
    echo "preview_not_generated" >&2
    exit 41
  fi
elif [ "$EXPECTED_RESULT" = "cancelled" ]; then
  if [ ! -f "$WIZARD_OUT/setup-cancelled.json" ] && [ "$WIZARD_RC" != "130" ]; then
    echo "expected_cancel_not_observed" >&2
    exit 43
  fi
elif [ "$EXPECTED_RESULT" = "candidate_ready" ]; then
  if [ ! -f "$WIZARD_OUT/config.candidate.json" ]; then
    echo "candidate_not_generated" >&2
    exit 44
  fi
  python3 "$HANDOFF" \
    --source-candidate "$WIZARD_OUT/config.candidate.json" \
    --private-values "$REMOTE_PRIVATE_VALUES" \
    --out-dir "$HANDOFF_OUT" \
    --confirm-private-values-approved >/dev/null
  HANDOFF_RC="0"
  python3 "$CONTRACT" \
    --candidate "$HANDOFF_OUT/config.candidate.private.json" \
    --real-dry-run \
    --out-dir "$RUN_OUT/validate-real" >/dev/null
  rm -f "$HANDOFF_OUT/config.candidate.private.json" "$WIZARD_OUT/config.candidate.json" || true
else
  echo "unsupported_expected_result" >&2
  exit 2
fi

restore_service || true
wait_player_running || true
write_final_status
restore_getty || true
trap - EXIT INT TERM HUP
exit 0
REMOTE_RUN
}

prepare_workspace
run_prepare_checks

case "$MODE" in
  prepare-only)
    echo "C10.6 prepare-only complete. Evidence dir reserved: $REMOTE_OUT_DIR"
    ;;
  preview-open-settings)
    run_open_settings \
      "preview-open-settings" \
      "preview" \
      "not_required" \
      "$PAUSE_CONFIRM_PHRASE" \
      "HDMI/tela e teclado local devem estar conectados. O player sera pausado temporariamente para abrir Configuracoes."
    ;;
  run-open-cancel)
    run_open_settings \
      "run-open-cancel" \
      "cancelled" \
      "not_required" \
      "$PAUSE_CONFIRM_PHRASE" \
      "Abra Configuracoes do Totem e cancele no wizard. O player deve voltar sem alterar config."
    ;;
  run-open-complete-dry-run)
    if [ "$PRIVATE_SOURCE_MODE" = "active-config" ]; then
      confirm_exact "$SOURCE_CONFIRM_PHRASE" "O dry-run usara a config ativa apenas como fonte privada temporaria. Valores nao serao impressos."
    fi
    run_open_settings \
      "run-open-complete-dry-run" \
      "candidate_ready" \
      "existing_configured_wifi" \
      "$DRY_RUN_CONFIRM_PHRASE" \
      "Complete o wizard visual. O fluxo roda handoff/C5.1 real-dry-run e nao chama writer."
    ;;
  run-open-complete-real-write)
    confirm_exact "$REAL_WRITE_CONFIRM_PHRASE" "C10.6 abre Configuracoes; a escrita real permanece delegada ao runner C10.4 guardado."
    if [ ! -x "$LOCAL_C10_4_RUNNER" ]; then
      echo "error: C10.4 writer runner is not executable" >&2
      exit 1
    fi
    exec "$LOCAL_C10_4_RUNNER" "$HOST" --run-real-write-start --tty "$REMOTE_TTY" --timeout-sec "$RUN_TIMEOUT_SEC"
    ;;
esac
