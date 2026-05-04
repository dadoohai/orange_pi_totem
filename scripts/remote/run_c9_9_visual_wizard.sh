#!/usr/bin/env bash
set -euo pipefail

HOST="root@192.168.1.147"
MODE="prepare-only"
REMOTE_TTY="2"
RUN_TIMEOUT_SEC="1800"
PREVIEW_SEC="14"
REMOTE_DIR="/tmp/dadooh-c9-9"
REMOTE_OUT_DIR="/tmp/dadooh-c9-9-visual-wizard-run"
REMOTE_WIZARD_OUT_DIR="/tmp/dadooh-c9-9-visual-wizard"
PROFILE_NAME="dadooh-c9-8-wifi-persistent"
CONFIRM_PHRASE="CONFIRMO C9.9 WIZARD VISUAL COM PAUSA DO PLAYER"

usage() {
  cat <<'USAGE'
Usage:
  run_c9_9_visual_wizard.sh [host] [--prepare-only|--preview-screens|--run-cancel|--run-complete-existing-wifi|--run-complete-with-wifi-persistent] [--tty N] [--timeout-sec N]

Modes:
  --prepare-only
      Copy C9.9 inputs to /tmp and run non-interactive checks.

  --preview-screens
      Requires exact human confirmation. Pauses the player, displays the
      visual screen preview on HDMI, then restores the player.

  --run-cancel
      Requires exact human confirmation. Pauses the player, opens the visual
      wizard on HDMI/TTY, expects operator cancellation, then restores.

  --run-complete-existing-wifi
      Requires exact human confirmation. Runs the visual wizard using the
      existing dedicated Wi-Fi option, then restores.

  --run-complete-with-wifi-persistent
      Optional C9.9 path. Requires exact human confirmation and local HDMI
      credential entry to reconfigure the dedicated Wi-Fi profile.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only)
      MODE="prepare-only"
      ;;
    --preview-screens)
      MODE="preview-screens"
      ;;
    --run-cancel)
      MODE="run-cancel"
      ;;
    --run-complete-existing-wifi)
      MODE="run-complete-existing-wifi"
      ;;
    --run-complete-with-wifi-persistent)
      MODE="run-complete-with-wifi-persistent"
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
  prepare-only|preview-screens|run-cancel|run-complete-existing-wifi|run-complete-with-wifi-persistent)
    ;;
  *)
    echo "error: unsupported mode $MODE" >&2
    exit 2
    ;;
esac

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BOARD_DIR="$REPO_ROOT/scripts/board"

LOCAL_VISUAL_WIZARD="$BOARD_DIR/totem_setup_visual_wizard.py"
LOCAL_WIZARD="$BOARD_DIR/totem_setup_local_wizard.py"
LOCAL_SERVER="$BOARD_DIR/totem_setup_minimal_server.py"
LOCAL_CONTRACT="$BOARD_DIR/totem_config_contract_validate.py"
LOCAL_WIFI_ADAPTER="$BOARD_DIR/totem_wifi_nm_adapter.py"
LOCAL_STATUS_AGGREGATE="$BOARD_DIR/totem_status_aggregate.py"
LOCAL_STATUS_RENDER="$BOARD_DIR/totem_status_render_preview.py"

for path in "$LOCAL_VISUAL_WIZARD" "$LOCAL_WIZARD" "$LOCAL_SERVER" "$LOCAL_CONTRACT" "$LOCAL_WIFI_ADAPTER" "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER"; do
  if [ ! -f "$path" ]; then
    echo "error: missing local input" >&2
    exit 1
  fi
done

echo "Preparing C9.9 visual wizard workspace on $HOST"
ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR'"

echo "Copying C9.9 inputs to temporary board workspace"
scp "$LOCAL_VISUAL_WIZARD" "$LOCAL_WIZARD" "$LOCAL_SERVER" "$LOCAL_CONTRACT" "$LOCAL_WIFI_ADAPTER" "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$HOST:$REMOTE_DIR/"

echo "Running C9.9 prepare checks on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail

VISUAL="$REMOTE_DIR/totem_setup_visual_wizard.py"
WIZARD="$REMOTE_DIR/totem_setup_local_wizard.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
WIFI_ADAPTER="$REMOTE_DIR/totem_wifi_nm_adapter.py"
PREVIEW_OUT="$REMOTE_OUT_DIR/preview"
SCRIPTED_OUT="$REMOTE_OUT_DIR/scripted-existing-wifi"
ALLOW_OUT="$REMOTE_OUT_DIR/validate-allow"
REAL_OUT="$REMOTE_OUT_DIR/validate-real"

umask 077
rm -rf "$PREVIEW_OUT" "$SCRIPTED_OUT" "$ALLOW_OUT" "$REAL_OUT"
mkdir -p "$REMOTE_DIR" "$REMOTE_OUT_DIR"
chmod 700 "$REMOTE_DIR" "$REMOTE_OUT_DIR"

python3 "$CONTRACT" --self-test
python3 "$WIFI_ADAPTER" --self-test --out-dir "$REMOTE_OUT_DIR/adapter-self-test"
python3 "$WIZARD" --self-test
python3 "$VISUAL" --self-test
python3 "$VISUAL" --preview-screens --out-dir "$PREVIEW_OUT" >/dev/null
python3 "$VISUAL" \
  --scripted \
  --environment-id ENV-C9-9-VISUAL-SMOKE \
  --rotation-key landscape \
  --network-step configured_wifi \
  --out-dir "$SCRIPTED_OUT" >/dev/null
python3 "$CONTRACT" --candidate "$SCRIPTED_OUT/config.candidate.json" --allow-mock --out-dir "$ALLOW_OUT" >/dev/null
if python3 "$CONTRACT" --candidate "$SCRIPTED_OUT/config.candidate.json" --real-dry-run --out-dir "$REAL_OUT" >/dev/null; then
  echo "error: real-dry-run unexpectedly passed" >&2
  exit 1
fi
python3 - "$SCRIPTED_OUT/setup-status.json" <<'PY'
import json
import pathlib
import sys
status = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
network = status.get("network", {})
interface = status.get("interface", {})
assert interface.get("mode") == "local_visual_mpv_drm_keyboard_controlled"
assert interface.get("linux_prompt_visible") is False
assert interface.get("chromium_used") is False
assert network.get("network_step") == "existing_configured_wifi"
assert network.get("dedicated_profile_persistent") is True
PY

echo "remote C9.9 prepare checks: ok"
REMOTE_PREP

if [ "$MODE" = "prepare-only" ]; then
  echo "C9.9 prepare-only complete. Evidence dir reserved: $REMOTE_OUT_DIR"
  exit 0
fi

echo
echo "HDMI/tela e teclado local devem estar conectados. O player sera pausado temporariamente."
echo "O operador nao deve ver shell; credenciais, se pedidas, entram apenas no totem."
echo "Before pausing the player and opening C9.9 visual setup, type exactly:"
echo "$CONFIRM_PHRASE"
printf '> '
IFS= read -r AUTH_TEXT
if [ "$AUTH_TEXT" != "$CONFIRM_PHRASE" ]; then
  echo "Authorization text did not match. Aborting before service pause." >&2
  exit 20
fi

EXPECTED_RESULT="candidate_ready"
EXPECTED_NETWORK_STEP="existing_configured_wifi"
if [ "$MODE" = "run-cancel" ]; then
  EXPECTED_RESULT="cancelled"
  EXPECTED_NETWORK_STEP="not_required"
elif [ "$MODE" = "preview-screens" ]; then
  EXPECTED_RESULT="preview"
  EXPECTED_NETWORK_STEP="not_required"
elif [ "$MODE" = "run-complete-with-wifi-persistent" ]; then
  EXPECTED_NETWORK_STEP="wifi_persistent"
fi

echo "Running authorized C9.9 visual wizard on local console"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_WIZARD_OUT_DIR='$REMOTE_WIZARD_OUT_DIR' REMOTE_TTY='$REMOTE_TTY' RUN_TIMEOUT_SEC='$RUN_TIMEOUT_SEC' PREVIEW_SEC='$PREVIEW_SEC' EXPECTED_RESULT='$EXPECTED_RESULT' EXPECTED_NETWORK_STEP='$EXPECTED_NETWORK_STEP' MODE='$MODE' PROFILE_NAME='$PROFILE_NAME' bash -s" <<'REMOTE_RUN'
set -euo pipefail

VISUAL="$REMOTE_DIR/totem_setup_visual_wizard.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
AGGREGATE="$REMOTE_DIR/totem_status_aggregate.py"
RUN_OUT="$REMOTE_OUT_DIR/$MODE"
FINAL_STATUS="$RUN_OUT/final-status.json"
WIZARD_OUT="$REMOTE_WIZARD_OUT_DIR"
WIZARD_RC="not_run"
SERVICE_STOP_ATTEMPTED="false"
SERVICE_RESTORE_ATTEMPTED="false"
INITIAL_SERVICE_ACTIVE="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
INITIAL_SERVICE_ENABLED="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"

umask 077
rm -rf "$RUN_OUT" "$WIZARD_OUT"
mkdir -p "$RUN_OUT" "$WIZARD_OUT"
chmod 700 "$RUN_OUT" "$WIZARD_OUT"

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
    joined = " ".join(parts)
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

read_playback() {
  python3 - <<'PY'
import json
import pathlib
try:
    data = json.loads(pathlib.Path("/tmp/kiosky-status.json").read_text(encoding="utf-8"))
    value = data.get("playback_state")
    print(value if isinstance(value, str) else "unknown")
except Exception:
    print("unknown")
PY
}

read_public_state() {
  python3 - <<'PY'
import json
import pathlib
try:
    data = json.loads(pathlib.Path("/tmp/dadooh-status/status.json").read_text(encoding="utf-8"))
    value = data.get("public_state") or data.get("state")
    print(value if isinstance(value, str) else "unknown")
except Exception:
    print("unknown")
PY
}

wait_public_state() {
  for _ in $(seq 1 45); do
    refresh_public_status
    state="$(read_public_state)"
    if [ "$state" = "player_running" ]; then
      return 0
    fi
    set -- $(process_counts)
    playback="$(read_playback)"
    if [ "${1:-0}" -ge 1 ] && [ "${2:-0}" -ge 1 ] && [ "${3:-0}" -eq 0 ] && [ "${4:-0}" -eq 0 ] && [ "$playback" = "playing" ]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

dedicated_profile_present() {
  nmcli -t -f connection.id connection show "$PROFILE_NAME" >/dev/null 2>&1 && printf 'true' || printf 'false'
}

write_final_status() {
  wait_public_state || true
  python3 - "$FINAL_STATUS" "$RUN_OUT" "$WIZARD_OUT" "$MODE" "$EXPECTED_RESULT" "$EXPECTED_NETWORK_STEP" "$WIZARD_RC" \
    "$INITIAL_SERVICE_ACTIVE" "$INITIAL_SERVICE_ENABLED" "$SERVICE_STOP_ATTEMPTED" "$SERVICE_RESTORE_ATTEMPTED" \
    "$(systemctl is-active kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null || true)" \
    "$(read_public_state)" "$(read_playback)" "$(dedicated_profile_present)" <<'PY'
import json
import os
import pathlib
import stat
import sys

target = pathlib.Path(sys.argv[1])
run_out = pathlib.Path(sys.argv[2])
wizard_out = pathlib.Path(sys.argv[3])
mode = sys.argv[4]
expected = sys.argv[5]
expected_network_step = sys.argv[6]
wizard_rc = sys.argv[7]
initial_active = sys.argv[8] or "unknown"
initial_enabled = sys.argv[9] or "unknown"
service_stop_attempted = sys.argv[10] == "true"
service_restore_attempted = sys.argv[11] == "true"
service_active = sys.argv[12] or "unknown"
service_enabled = sys.argv[13] or "unknown"
nrestarts = sys.argv[14] or "unknown"
public_state = sys.argv[15] or "unknown"
playback = sys.argv[16] or "unknown"
dedicated_profile_present = sys.argv[17] == "true"

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

setup_status = {}
status_path = wizard_out / "setup-status.json"
if status_path.exists():
    try:
        setup_status = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        setup_status = {}
network = setup_status.get("network") if isinstance(setup_status.get("network"), dict) else {}
interface = setup_status.get("interface") if isinstance(setup_status.get("interface"), dict) else {}

candidate_present = (wizard_out / "config.candidate.json").exists()
cancelled = (wizard_out / "setup-cancelled.json").exists()
failed = (wizard_out / "setup-failed.json").exists()
screens_present = (wizard_out / "screens").is_dir() and any((wizard_out / "screens").glob("*.svg"))
if candidate_present:
    wizard_result = "candidate_ready"
elif cancelled:
    wizard_result = "cancelled"
elif screens_present and expected == "preview":
    wizard_result = "preview"
elif failed:
    wizard_result = "failed"
else:
    wizard_result = "not_observed"

payload = {
    "schema_version": "dadooh-c9.9-visual-wizard-run.v1",
    "mode": mode,
    "expected_result": expected,
    "expected_network_step": expected_network_step,
    "wizard_result": wizard_result,
    "wizard_rc": wizard_rc,
    "candidate_generated": candidate_present,
    "screens_generated": screens_present,
    "visual_renderer": interface.get("visual_renderer", "mpv_drm_svg" if screens_present else "unknown"),
    "linux_prompt_visible": bool(interface.get("linux_prompt_visible", False)),
    "service_active": service_active,
    "service_enabled": service_enabled,
    "service_initial_active": initial_active,
    "service_initial_enabled": initial_enabled,
    "service_stop_attempted": service_stop_attempted,
    "service_restore_attempted": service_restore_attempted,
    "nrestarts": nrestarts,
    "public_state": public_state,
    "playback": playback,
    "process_counts": counts,
    "network_step": network.get("network_step", "not_available"),
    "wifi_real_test_attempted": bool(network.get("wifi_real_test_attempted", False)),
    "wifi_activation_result": network.get("wifi_activation_result", "not_available"),
    "rollback_after_test": network.get("rollback_after_test", "not_available"),
    "dedicated_profile_present_final": dedicated_profile_present,
    "dedicated_profile_persistent": bool(network.get("dedicated_profile_persistent", dedicated_profile_present)),
    "network_changed": bool(network.get("network_changed", False)),
    "credentials_collected": bool(network.get("credentials_collected", False)),
    "secrets_file_removed": bool(network.get("secrets_file_removed", False)),
    "c5_allow_mock": "not_run",
    "c5_real_dry_run": "not_run",
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "hotspot_created": False,
    "portal_created": False,
    "reboot_called": False,
    "network_identifiers_published": False,
    "credential_values_published": False,
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

validate_candidate() {
  if [ ! -f "$WIZARD_OUT/config.candidate.json" ]; then
    return 0
  fi
  if python3 "$CONTRACT" --candidate "$WIZARD_OUT/config.candidate.json" --allow-mock --out-dir "$RUN_OUT/validate-allow" >/dev/null; then
    C5_ALLOW="passed"
  else
    C5_ALLOW="failed"
  fi
  if python3 "$CONTRACT" --candidate "$WIZARD_OUT/config.candidate.json" --real-dry-run --out-dir "$RUN_OUT/validate-real" >/dev/null; then
    C5_REAL="unexpected_pass"
  else
    C5_REAL="expected_failure"
  fi
  python3 - "$FINAL_STATUS" "$C5_ALLOW" "$C5_REAL" <<'PY'
import json
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
data["c5_allow_mock"] = sys.argv[2]
data["c5_real_dry_run"] = sys.argv[3]
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
path.chmod(0o600)
print(json.dumps(data, indent=2, sort_keys=True))
PY
}

restore_service() {
  SERVICE_RESTORE_ATTEMPTED="true"
  if [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
    systemctl enable kiosky-player.service >/dev/null 2>&1 || true
  fi
  if [ "$INITIAL_SERVICE_ACTIVE" = "active" ] || [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
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

on_exit() {
  rc="$?"
  trap - EXIT INT TERM HUP
  kill_visual_if_running || true
  restore_service || true
  write_final_status || true
  validate_candidate || true
  exit "$rc"
}
trap on_exit EXIT INT TERM HUP

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

set -- $(process_counts)
if [ "${1:-0}" -ne 0 ] || [ "${2:-0}" -ne 0 ] || [ "${3:-0}" -ne 0 ] || [ "${4:-0}" -ne 0 ]; then
  echo "hdmi_not_free_after_player_pause" >&2
  exit 42
fi

set +e
if [ "$MODE" = "preview-screens" ]; then
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
    echo "preview_screens_not_generated" >&2
    exit 41
  fi
elif [ "$EXPECTED_RESULT" = "cancelled" ]; then
  if [ ! -f "$WIZARD_OUT/setup-cancelled.json" ] && [ "$WIZARD_RC" != "130" ]; then
    echo "expected_cancel_not_observed" >&2
    exit 43
  fi
else
  if [ ! -f "$WIZARD_OUT/config.candidate.json" ]; then
    echo "candidate_not_generated" >&2
    exit 44
  fi
  python3 - "$WIZARD_OUT/setup-status.json" "$EXPECTED_NETWORK_STEP" <<'PY'
import json
import pathlib
import sys
status = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
expected_network_step = sys.argv[2]
interface = status.get("interface", {})
network = status.get("network", {})
if interface.get("mode") != "local_visual_mpv_drm_keyboard_controlled":
    raise SystemExit("visual_interface_not_recorded")
if interface.get("linux_prompt_visible") is not False:
    raise SystemExit("linux_prompt_visibility_not_false")
if interface.get("chromium_used") is not False or interface.get("desktop_used") is not False:
    raise SystemExit("desktop_or_browser_not_false")
if network.get("network_step") != expected_network_step:
    raise SystemExit("network_step_not_expected")
if expected_network_step == "existing_configured_wifi":
    if network.get("dedicated_profile_persistent") is not True:
        raise SystemExit("existing_wifi_not_recorded_persistent")
    if network.get("network_changed") is not False:
        raise SystemExit("existing_wifi_changed_network")
if expected_network_step == "wifi_persistent":
    if network.get("wifi_activation_result") != "success":
        raise SystemExit("wifi_activation_not_success")
    if network.get("dedicated_profile_persistent") is not True:
        raise SystemExit("persistent_profile_not_recorded")
    if network.get("secrets_file_removed") is not True:
        raise SystemExit("secrets_file_not_removed")
PY
fi

exit 0
REMOTE_RUN

echo "C9.9 visual wizard run complete. Evidence: $REMOTE_OUT_DIR"
