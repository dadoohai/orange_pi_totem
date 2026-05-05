#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
REMOTE_DIR="/tmp/dadooh-c10-6-1-persistent-trigger"
REMOTE_OUT_DIR="/tmp/dadooh-c10-6-1-persistent-trigger-evidence"
REMOTE_SESSION_STATUS="/tmp/dadooh-c10-6-persistent-open-settings/session/session-status.json"
TRIGGER_UNIT="totem-settings-trigger.service"
OPEN_UNIT="totem-open-settings.service"
REBOOT_CONFIRM_PHRASE="CONFIRMO REBOOT C10.6.1 TRIGGER PERSISTENTE"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_6_1_persistent_settings_trigger.sh <host> [mode]

Modes:
  --prepare-only
  --install-trigger
  --status
  --run-human-f10
  --reboot-check
  --rollback-trigger
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --install-trigger) MODE="install-trigger" ;;
    --status) MODE="status" ;;
    --run-human-f10) MODE="run-human-f10" ;;
    --reboot-check) MODE="reboot-check" ;;
    --rollback-trigger) MODE="rollback-trigger" ;;
    --help|-h) usage; exit 0 ;;
    *) HOST="$1" ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|install-trigger|status|run-human-f10|reboot-check|rollback-trigger) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ -z "$HOST" ]; then
  echo "error: host is required" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BOARD_DIR="$REPO_ROOT/scripts/board"

LOCAL_TRIGGER="$BOARD_DIR/totem_settings_trigger.py"
LOCAL_SESSION="$BOARD_DIR/totem_open_settings_session.sh"
LOCAL_VISUAL_WIZARD="$BOARD_DIR/totem_setup_visual_wizard.py"
LOCAL_VISUAL_SPLASH="$BOARD_DIR/totem_visual_splash.py"
LOCAL_CONTRACT="$BOARD_DIR/totem_config_contract_validate.py"
LOCAL_WIFI_ADAPTER="$BOARD_DIR/totem_wifi_nm_adapter.py"
LOCAL_STATUS_AGGREGATE="$BOARD_DIR/totem_status_aggregate.py"
LOCAL_STATUS_RENDER="$BOARD_DIR/totem_status_render_preview.py"
LOCAL_MINIMAL_SERVER="$BOARD_DIR/totem_setup_minimal_server.py"
LOCAL_LOCAL_WIZARD="$BOARD_DIR/totem_setup_local_wizard.py"
LOCAL_TRIGGER_UNIT="$BOARD_DIR/totem-settings-trigger.service"
LOCAL_OPEN_UNIT="$BOARD_DIR/totem-open-settings.service"

for path in \
  "$LOCAL_TRIGGER" "$LOCAL_SESSION" "$LOCAL_VISUAL_WIZARD" "$LOCAL_VISUAL_SPLASH" "$LOCAL_CONTRACT" \
  "$LOCAL_WIFI_ADAPTER" "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_MINIMAL_SERVER" \
  "$LOCAL_LOCAL_WIZARD" "$LOCAL_TRIGGER_UNIT" "$LOCAL_OPEN_UNIT"
do
  if [ ! -f "$path" ]; then
    echo "error: missing local input $path" >&2
    exit 1
  fi
done

copy_workspace() {
  ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR'"
  scp \
    "$LOCAL_TRIGGER" "$LOCAL_SESSION" "$LOCAL_VISUAL_WIZARD" "$LOCAL_VISUAL_SPLASH" "$LOCAL_CONTRACT" \
    "$LOCAL_WIFI_ADAPTER" "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_MINIMAL_SERVER" \
    "$LOCAL_LOCAL_WIZARD" "$LOCAL_TRIGGER_UNIT" "$LOCAL_OPEN_UNIT" \
    "$HOST:$REMOTE_DIR/" >/dev/null
  ssh "$HOST" "chmod +x '$REMOTE_DIR/totem_settings_trigger.py' '$REMOTE_DIR/totem_open_settings_session.sh'"
}

run_prepare() {
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail
bash -n "$REMOTE_DIR/totem_open_settings_session.sh"
python3 "$REMOTE_DIR/totem_settings_trigger.py" --self-test
python3 "$REMOTE_DIR/totem_setup_visual_wizard.py" --self-test
python3 "$REMOTE_DIR/totem_visual_splash.py" --self-test
python3 "$REMOTE_DIR/totem_wifi_nm_adapter.py" --self-test --out-dir "$REMOTE_OUT_DIR/wifi-self-test" >/dev/null
python3 "$REMOTE_DIR/totem_config_contract_validate.py" --self-test
echo "remote C10.6.1 prepare checks: ok"
REMOTE_PREP
}

remote_status() {
  ssh "$HOST" "REMOTE_OUT_DIR='$REMOTE_OUT_DIR' TRIGGER_UNIT='$TRIGGER_UNIT' OPEN_UNIT='$OPEN_UNIT' bash -s" <<'REMOTE_STATUS'
set -euo pipefail
STATUS_DIR="$REMOTE_OUT_DIR/status"
STATUS="$STATUS_DIR/status.json"
mkdir -p "$STATUS_DIR"
chmod 700 "$STATUS_DIR"

refresh_public_status() {
  if [ -f /opt/totem/bin/totem_status_aggregate.py ]; then
    PYTHONPATH=/opt/totem/bin python3 /opt/totem/bin/totem_status_aggregate.py >/dev/null 2>&1 || true
  fi
}

refresh_public_status
python3 - "$STATUS" "$TRIGGER_UNIT" "$OPEN_UNIT" <<'PY'
import json
import os
import pathlib
import stat
import subprocess
import sys

target = pathlib.Path(sys.argv[1])
trigger_unit = sys.argv[2]
open_unit = sys.argv[3]

def run(args):
    try:
        completed = subprocess.run(args, check=False, capture_output=True, text=True, timeout=4)
    except Exception:
        return "unknown"
    return (completed.stdout or "").strip() or "unknown"

def service_state(unit):
    return {
        "active": run(["systemctl", "is-active", unit]),
        "enabled": run(["systemctl", "is-enabled", unit]),
    }

def read_status(path):
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def counts():
    result = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
    self_pid = os.getpid()
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == self_pid:
            continue
        try:
            parts = [p.decode("utf-8", "ignore") for p in (proc / "cmdline").read_bytes().split(b"\0") if p]
        except OSError:
            continue
        names = [pathlib.Path(part).name.lower() for part in parts]
        if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
            result["setup"] += 1
        if any("totem_status_renderer" in name for name in names):
            result["renderer"] += 1
        if any(name == "mpv" for name in names):
            result["mpv"] += 1
        if "kiosk.py" in names:
            result["player"] += 1
    return result

public_status = read_status("/tmp/dadooh-status/status.json")
playback_status = read_status("/tmp/kiosky-status.json")
trigger_state = service_state(trigger_unit)
open_state = service_state(open_unit)
payload = {
    "schema_version": "dadooh-c10.6.1-persistent-settings-trigger-status.v1",
    "trigger_service_installed": pathlib.Path(f"/etc/systemd/system/{trigger_unit}").exists(),
    "trigger_service_active": trigger_state["active"] == "active",
    "trigger_service_enabled": trigger_state["enabled"] == "enabled",
    "open_service_installed": pathlib.Path(f"/etc/systemd/system/{open_unit}").exists(),
    "open_service_active": open_state["active"],
    "open_service_enabled": open_state["enabled"],
    "kiosky_service_active": run(["systemctl", "is-active", "kiosky-player.service"]),
    "kiosky_service_enabled": run(["systemctl", "is-enabled", "kiosky-player.service"]),
    "nrestarts": run(["systemctl", "show", "kiosky-player.service", "-p", "NRestarts", "--value"]),
    "public_state": public_status.get("public_state") or public_status.get("state") or "unknown",
    "playback": playback_status.get("playback_state", "unknown"),
    "process_counts": counts(),
    "writer_called": False,
    "real_config_read": False,
    "real_config_written": False,
    "wifi_changed": False,
    "networkmanager_changed": False,
    "raw_logs_written": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
REMOTE_STATUS
}

install_trigger() {
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' bash -s" <<'REMOTE_INSTALL'
set -euo pipefail
ROLLBACK_DIR="/data/state/dadooh-c10-6-1-trigger-rollback"
mkdir -p "$ROLLBACK_DIR/files" /opt/totem/bin /etc/systemd/system
chmod 700 "$ROLLBACK_DIR" "$ROLLBACK_DIR/files"
for path in \
  /opt/totem/bin/totem_settings_trigger.py \
  /opt/totem/bin/totem_open_settings_session.sh \
  /opt/totem/bin/totem_setup_visual_wizard.py \
  /opt/totem/bin/totem_visual_splash.py \
  /opt/totem/bin/totem_config_contract_validate.py \
  /opt/totem/bin/totem_wifi_nm_adapter.py \
  /opt/totem/bin/totem_status_aggregate.py \
  /opt/totem/bin/totem_status_render_preview.py \
  /opt/totem/bin/totem_setup_minimal_server.py \
  /opt/totem/bin/totem_setup_local_wizard.py \
  /etc/systemd/system/totem-settings-trigger.service \
  /etc/systemd/system/totem-open-settings.service
do
  if [ -e "$path" ] && [ ! -e "$ROLLBACK_DIR/files/$(basename "$path").bak" ]; then
    cp -a "$path" "$ROLLBACK_DIR/files/$(basename "$path").bak"
  fi
done
install -m 0755 "$REMOTE_DIR/totem_settings_trigger.py" /opt/totem/bin/totem_settings_trigger.py
install -m 0755 "$REMOTE_DIR/totem_open_settings_session.sh" /opt/totem/bin/totem_open_settings_session.sh
install -m 0755 "$REMOTE_DIR/totem_setup_visual_wizard.py" /opt/totem/bin/totem_setup_visual_wizard.py
install -m 0755 "$REMOTE_DIR/totem_visual_splash.py" /opt/totem/bin/totem_visual_splash.py
install -m 0755 "$REMOTE_DIR/totem_config_contract_validate.py" /opt/totem/bin/totem_config_contract_validate.py
install -m 0755 "$REMOTE_DIR/totem_wifi_nm_adapter.py" /opt/totem/bin/totem_wifi_nm_adapter.py
install -m 0755 "$REMOTE_DIR/totem_status_aggregate.py" /opt/totem/bin/totem_status_aggregate.py
install -m 0755 "$REMOTE_DIR/totem_status_render_preview.py" /opt/totem/bin/totem_status_render_preview.py
install -m 0755 "$REMOTE_DIR/totem_setup_minimal_server.py" /opt/totem/bin/totem_setup_minimal_server.py
install -m 0755 "$REMOTE_DIR/totem_setup_local_wizard.py" /opt/totem/bin/totem_setup_local_wizard.py
install -m 0644 "$REMOTE_DIR/totem-settings-trigger.service" /etc/systemd/system/totem-settings-trigger.service
install -m 0644 "$REMOTE_DIR/totem-open-settings.service" /etc/systemd/system/totem-open-settings.service
python3 - <<'PY' > "$ROLLBACK_DIR/rollback-state.json"
import json, time
print(json.dumps({
  "schema_version": "dadooh-c10.6.1-trigger-rollback.v1",
  "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "rollback_available": True,
  "config_real_touched": False,
  "wifi_touched": False
}, indent=2, sort_keys=True))
PY
chmod 600 "$ROLLBACK_DIR/rollback-state.json"
systemctl daemon-reload
systemctl disable totem-open-settings.service >/dev/null 2>&1 || true
systemctl enable totem-settings-trigger.service >/dev/null
systemctl restart totem-settings-trigger.service
echo "trigger_service_installed=true"
echo "trigger_service_enabled=true"
REMOTE_INSTALL
}

rollback_trigger() {
  ssh "$HOST" "bash -s" <<'REMOTE_ROLLBACK'
set -euo pipefail
ROLLBACK_DIR="/data/state/dadooh-c10-6-1-trigger-rollback"
systemctl stop totem-settings-trigger.service >/dev/null 2>&1 || true
systemctl stop totem-open-settings.service >/dev/null 2>&1 || true
systemctl disable totem-settings-trigger.service >/dev/null 2>&1 || true
for name in totem-settings-trigger.service totem-open-settings.service; do
  if [ -e "$ROLLBACK_DIR/files/$name.bak" ]; then
    cp -a "$ROLLBACK_DIR/files/$name.bak" "/etc/systemd/system/$name"
  else
    rm -f "/etc/systemd/system/$name"
  fi
done
for name in \
  totem_settings_trigger.py \
  totem_open_settings_session.sh \
  totem_setup_visual_wizard.py \
  totem_visual_splash.py \
  totem_config_contract_validate.py \
  totem_wifi_nm_adapter.py \
  totem_status_aggregate.py \
  totem_status_render_preview.py \
  totem_setup_minimal_server.py \
  totem_setup_local_wizard.py
do
  if [ -e "$ROLLBACK_DIR/files/$name.bak" ]; then
    cp -a "$ROLLBACK_DIR/files/$name.bak" "/opt/totem/bin/$name"
  elif [ "$name" = "totem_settings_trigger.py" ] || [ "$name" = "totem_open_settings_session.sh" ]; then
    rm -f "/opt/totem/bin/$name"
  fi
done
systemctl daemon-reload
echo "rollback_trigger_done=true"
REMOTE_ROLLBACK
}

run_human_f10() {
  echo "Segure F10 por 5 segundos no teclado local. O wizard deve abrir sem runner iniciar sessao."
  ssh "$HOST" "REMOTE_SESSION_STATUS='$REMOTE_SESSION_STATUS' bash -s" <<'REMOTE_WAIT'
set -euo pipefail
if ! systemctl is-active --quiet totem-settings-trigger.service; then
  echo "trigger_service_not_active" >&2
  exit 30
fi
rm -rf /tmp/dadooh-c10-6-persistent-open-settings /tmp/dadooh-c10-6-persistent-visual-wizard
rm -f /run/dadooh-settings/request.json /run/dadooh-settings/trigger-status.json /run/dadooh-settings/summary.txt 2>/dev/null || true
deadline=$(( $(date +%s) + 240 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  if [ -f "$REMOTE_SESSION_STATUS" ]; then
    python3 - "$REMOTE_SESSION_STATUS" <<'PY'
import json, pathlib, sys
data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
if not data.get("visual_wizard_opened"):
    raise SystemExit("settings_not_opened")
if data.get("public_state") != "player_running" or data.get("playback") != "playing":
    raise SystemExit("player_not_restored")
print(json.dumps({
  "f10_hold_detected": True,
  "settings_opened": True,
  "cancel_returned_to_player": bool(data.get("setup_cancelled", False)),
  "service_final": f"{data.get('service_active')}/{data.get('service_enabled')}",
  "nrestarts": data.get("nrestarts"),
  "public_state": data.get("public_state"),
  "playback": data.get("playback"),
  "process_counts": data.get("process_counts"),
  "writer_called": data.get("writer_called", False),
  "real_config_read": data.get("real_config_read", False),
  "real_config_written": data.get("real_config_written", False),
  "wifi_changed": data.get("wifi_changed", False)
}, indent=2, sort_keys=True))
PY
    exit 0
  fi
  sleep 2
done
echo "f10_trigger_timeout" >&2
exit 124
REMOTE_WAIT
}

reboot_check() {
  echo
  echo "Reboot controlado C10.6.1 exige confirmacao humana explicita."
  echo "Type exactly:"
  echo "$REBOOT_CONFIRM_PHRASE"
  printf '> '
  IFS= read -r AUTH_TEXT
  if [ "$AUTH_TEXT" != "$REBOOT_CONFIRM_PHRASE" ]; then
    echo "Authorization text did not match. Aborting before reboot." >&2
    exit 20
  fi
  ssh "$HOST" "systemctl reboot" || true
  echo "Reboot solicitado. Aguarde SSH voltar e rode --status; depois rode --run-human-f10 para validar pos-boot."
}

copy_workspace
run_prepare

case "$MODE" in
  prepare-only)
    echo "C10.6.1 prepare-only complete"
    ;;
  install-trigger)
    install_trigger
    remote_status
    ;;
  status)
    remote_status
    ;;
  run-human-f10)
    run_human_f10
    remote_status
    ;;
  reboot-check)
    reboot_check
    ;;
  rollback-trigger)
    rollback_trigger
    remote_status
    ;;
esac
