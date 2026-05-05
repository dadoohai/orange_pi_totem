#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
REMOTE_DIR="/tmp/dadooh-c10-6-2-apply-settings"
REMOTE_OUT_DIR="/tmp/dadooh-c10-6-2-apply-settings-evidence"
REMOTE_SESSION_STATUS="/tmp/dadooh-c10-6-2-open-settings/session/session-status.json"
POLICY_PATH="/run/dadooh-settings/apply-policy.json"
PRIVATE_VALUES="/tmp/dadooh-c10-6-2-private/private-values.json"
SOURCE_CONFIRM_PHRASE="CONFIRMO USAR CONFIG ATIVA COMO FONTE PRIVADA C10.6.2"
DRY_RUN_CONFIRM_PHRASE="CONFIRMO DRY RUN CONFIGURACOES DO TOTEM C10.6.2"
REAL_CONFIRM_PHRASE="CONFIRMO SALVAR CONFIGURACOES DO TOTEM C10.6.2"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_6_2_apply_settings_from_f10.sh <host> [mode]

Modes:
  --prepare-only
  --diagnose-current-flow
  --run-f10-cancel
  --run-f10-apply-dry-run
  --run-f10-apply-real
  --verify-orientation-propagation
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --diagnose-current-flow) MODE="diagnose-current-flow" ;;
    --run-f10-cancel) MODE="run-f10-cancel" ;;
    --run-f10-apply-dry-run) MODE="run-f10-apply-dry-run" ;;
    --run-f10-apply-real) MODE="run-f10-apply-real" ;;
    --verify-orientation-propagation) MODE="verify-orientation-propagation" ;;
    --help|-h) usage; exit 0 ;;
    *) HOST="$1" ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|diagnose-current-flow|run-f10-cancel|run-f10-apply-dry-run|run-f10-apply-real|verify-orientation-propagation) ;;
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
LOCAL_TRIGGER_UNIT="$BOARD_DIR/totem-settings-trigger.service"
LOCAL_OPEN_UNIT="$BOARD_DIR/totem-open-settings.service"
LOCAL_VISUAL_WIZARD="$BOARD_DIR/totem_setup_visual_wizard.py"
LOCAL_SPLASH="$BOARD_DIR/totem_visual_splash.py"
LOCAL_HANDOFF="$BOARD_DIR/totem_visual_setup_writer_handoff.py"
LOCAL_WRITER="$BOARD_DIR/totem_config_writer_real.py"
LOCAL_CONTRACT="$BOARD_DIR/totem_config_contract_validate.py"
LOCAL_WIFI="$BOARD_DIR/totem_wifi_nm_adapter.py"
LOCAL_AGGREGATE="$BOARD_DIR/totem_status_aggregate.py"
LOCAL_STATUS_RENDER="$BOARD_DIR/totem_status_render_preview.py"
LOCAL_MINIMAL_SERVER="$BOARD_DIR/totem_setup_minimal_server.py"
LOCAL_LOCAL_WIZARD="$BOARD_DIR/totem_setup_local_wizard.py"

for path in \
  "$LOCAL_TRIGGER" "$LOCAL_SESSION" "$LOCAL_TRIGGER_UNIT" "$LOCAL_OPEN_UNIT" "$LOCAL_VISUAL_WIZARD" \
  "$LOCAL_SPLASH" "$LOCAL_HANDOFF" "$LOCAL_WRITER" "$LOCAL_CONTRACT" "$LOCAL_WIFI" "$LOCAL_AGGREGATE" \
  "$LOCAL_STATUS_RENDER" "$LOCAL_MINIMAL_SERVER" "$LOCAL_LOCAL_WIZARD"
do
  if [ ! -f "$path" ]; then
    echo "error: missing local input $path" >&2
    exit 1
  fi
done

copy_workspace() {
  ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR'"
  scp \
    "$LOCAL_TRIGGER" "$LOCAL_SESSION" "$LOCAL_TRIGGER_UNIT" "$LOCAL_OPEN_UNIT" "$LOCAL_VISUAL_WIZARD" \
    "$LOCAL_SPLASH" "$LOCAL_HANDOFF" "$LOCAL_WRITER" "$LOCAL_CONTRACT" "$LOCAL_WIFI" "$LOCAL_AGGREGATE" \
    "$LOCAL_STATUS_RENDER" "$LOCAL_MINIMAL_SERVER" "$LOCAL_LOCAL_WIZARD" \
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
python3 "$REMOTE_DIR/totem_visual_setup_writer_handoff.py" --self-test
python3 "$REMOTE_DIR/totem_config_writer_real.py" --self-test
python3 "$REMOTE_DIR/totem_wifi_nm_adapter.py" --self-test --out-dir "$REMOTE_OUT_DIR/wifi-self-test" >/dev/null
python3 "$REMOTE_DIR/totem_config_contract_validate.py" --self-test
echo "remote C10.6.2 prepare checks: ok"
REMOTE_PREP
}

install_runtime() {
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' bash -s" <<'REMOTE_INSTALL'
set -euo pipefail
ROLLBACK_DIR="/data/state/dadooh-c10-6-2-apply-settings-rollback"
mkdir -p "$ROLLBACK_DIR/files" /opt/totem/bin /etc/systemd/system
chmod 700 "$ROLLBACK_DIR" "$ROLLBACK_DIR/files"
for path in \
  /opt/totem/bin/totem_settings_trigger.py \
  /opt/totem/bin/totem_open_settings_session.sh \
  /opt/totem/bin/totem_setup_visual_wizard.py \
  /opt/totem/bin/totem_visual_splash.py \
  /opt/totem/bin/totem_visual_setup_writer_handoff.py \
  /opt/totem/bin/totem_config_writer_real.py \
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
install -m 0755 "$REMOTE_DIR/totem_visual_setup_writer_handoff.py" /opt/totem/bin/totem_visual_setup_writer_handoff.py
install -m 0755 "$REMOTE_DIR/totem_config_writer_real.py" /opt/totem/bin/totem_config_writer_real.py
install -m 0755 "$REMOTE_DIR/totem_config_contract_validate.py" /opt/totem/bin/totem_config_contract_validate.py
install -m 0755 "$REMOTE_DIR/totem_wifi_nm_adapter.py" /opt/totem/bin/totem_wifi_nm_adapter.py
install -m 0755 "$REMOTE_DIR/totem_status_aggregate.py" /opt/totem/bin/totem_status_aggregate.py
install -m 0755 "$REMOTE_DIR/totem_status_render_preview.py" /opt/totem/bin/totem_status_render_preview.py
install -m 0755 "$REMOTE_DIR/totem_setup_minimal_server.py" /opt/totem/bin/totem_setup_minimal_server.py
install -m 0755 "$REMOTE_DIR/totem_setup_local_wizard.py" /opt/totem/bin/totem_setup_local_wizard.py
install -m 0644 "$REMOTE_DIR/totem-settings-trigger.service" /etc/systemd/system/totem-settings-trigger.service
install -m 0644 "$REMOTE_DIR/totem-open-settings.service" /etc/systemd/system/totem-open-settings.service
systemctl daemon-reload
systemctl disable totem-open-settings.service >/dev/null 2>&1 || true
systemctl enable totem-settings-trigger.service >/dev/null
systemctl restart totem-settings-trigger.service
echo "runtime_installed=true"
REMOTE_INSTALL
}

write_policy() {
  local mode="$1"
  local dry_confirmed="$2"
  local real_confirmed="$3"
  local active_confirmed="$4"
  ssh "$HOST" "POLICY_PATH='$POLICY_PATH' PRIVATE_VALUES='$PRIVATE_VALUES' POLICY_MODE='$mode' DRY_CONFIRMED='$dry_confirmed' REAL_CONFIRMED='$real_confirmed' ACTIVE_CONFIRMED='$active_confirmed' bash -s" <<'REMOTE_POLICY'
set -euo pipefail
python3 - "$POLICY_PATH" "$PRIVATE_VALUES" "$POLICY_MODE" "$DRY_CONFIRMED" "$REAL_CONFIRMED" "$ACTIVE_CONFIRMED" <<'PY'
import json
import os
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
private_values = sys.argv[2]
mode = sys.argv[3]
dry_confirmed = sys.argv[4] == "true"
real_confirmed = sys.argv[5] == "true"
active_confirmed = sys.argv[6] == "true"
path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
payload = {
    "schema_version": "dadooh-c10.6.2-apply-policy.v1",
    "mode": mode,
    "private_source": "active-config" if mode in {"dry-run", "real-write"} else "none",
    "private_values_path": private_values,
    "active_config_private_source_confirmed": active_confirmed,
    "dry_run_confirmed": dry_confirmed,
    "real_write_confirmed": real_confirmed,
}
tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, path)
os.chmod(path, 0o600)
PY
REMOTE_POLICY
}

clear_policy_and_status() {
  ssh "$HOST" "POLICY_PATH='$POLICY_PATH' REMOTE_SESSION_STATUS='$REMOTE_SESSION_STATUS' bash -s" <<'REMOTE_CLEAR'
set -euo pipefail
rm -f "$POLICY_PATH" /run/dadooh-settings/request.json /run/dadooh-settings/trigger-status.json /run/dadooh-settings/summary.txt 2>/dev/null || true
rm -rf /tmp/dadooh-c10-6-2-open-settings /tmp/dadooh-c10-6-2-visual-wizard /tmp/dadooh-c10-6-2-handoff /tmp/dadooh-c10-6-2-writer /tmp/dadooh-c10-6-2-private 2>/dev/null || true
REMOTE_CLEAR
}

wait_for_f10_session() {
  local label="$1"
  echo "Segure F10 por 5 segundos no teclado local para $label."
  ssh "$HOST" "REMOTE_SESSION_STATUS='$REMOTE_SESSION_STATUS' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_WAIT'
set -euo pipefail
if ! systemctl is-active --quiet totem-settings-trigger.service; then
  echo "trigger_service_not_active" >&2
  exit 30
fi
deadline=$(( $(date +%s) + 900 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  if [ -f "$REMOTE_SESSION_STATUS" ]; then
    python3 - "$REMOTE_SESSION_STATUS" <<'PY'
import json, pathlib, sys
data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print(json.dumps({
  "f10_opened_settings": bool(data.get("visual_wizard_opened")),
  "setup_cancelled": bool(data.get("setup_cancelled")),
  "apply_mode": data.get("apply_mode"),
  "writer_called": bool(data.get("writer_called", False)),
  "real_config_written": bool(data.get("real_config_written", False)),
  "backup_created": bool(data.get("backup_created", False)),
  "expected_rotation_deg": data.get("expected_rotation_deg"),
  "active_config_rotation_deg_matches": data.get("active_config_rotation_deg_matches"),
  "orientation_json_updated": bool(data.get("orientation_json_updated", False)),
  "orientation_json_rotation_matches": bool(data.get("orientation_json_rotation_matches", False)),
  "service_final": f"{data.get('service_active')}/{data.get('service_enabled')}",
  "nrestarts": data.get("nrestarts"),
  "public_state": data.get("public_state"),
  "playback": data.get("playback"),
  "process_counts": data.get("process_counts"),
  "wifi_changed": bool(data.get("wifi_changed", False)),
  "raw_logs_written": bool(data.get("raw_logs_written", False)),
}, indent=2, sort_keys=True))
PY
    exit 0
  fi
  sleep 2
done
echo "f10_session_timeout" >&2
exit 124
REMOTE_WAIT
}

diagnose_current_flow() {
  ssh "$HOST" "REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_SESSION_STATUS='$REMOTE_SESSION_STATUS' POLICY_PATH='$POLICY_PATH' bash -s" <<'REMOTE_DIAG'
set -euo pipefail
OUT="$REMOTE_OUT_DIR/diagnose-current-flow"
mkdir -p "$OUT"
chmod 700 "$OUT"
python3 - "$OUT/diagnose-status.json" "$REMOTE_SESSION_STATUS" "$POLICY_PATH" <<'PY'
import json
import os
import pathlib
import stat
import subprocess
import sys

target = pathlib.Path(sys.argv[1])
session_status = pathlib.Path(sys.argv[2])
policy_path = pathlib.Path(sys.argv[3])

def load(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def unit_file_contains(token):
    try:
        text = pathlib.Path("/etc/systemd/system/totem-open-settings.service").read_text(encoding="utf-8")
    except Exception:
        return False
    return token in text

def run(args):
    try:
        p = subprocess.run(args, check=False, capture_output=True, text=True, timeout=4)
    except Exception:
        return "unknown"
    return (p.stdout or "").strip() or "unknown"

last = load(session_status)
orientation = load(pathlib.Path("/data/state/totem-display/orientation.json"))
payload = {
    "schema_version": "dadooh-c10.6.2-diagnose-current-flow.v1",
    "installed_open_session_supports_policy": unit_file_contains("--apply-policy-path"),
    "installed_open_session_supports_handoff": unit_file_contains("--handoff-out-dir"),
    "last_session_available": bool(last),
    "last_writer_called": bool(last.get("writer_called", False)),
    "last_real_config_written": bool(last.get("real_config_written", False)),
    "last_candidate_generated": bool(last.get("visual_candidate_generated", False)),
    "last_rotation_deg_present": isinstance(last.get("rotation_degrees"), int) or isinstance(last.get("selected_rotation_deg"), int),
    "last_handoff_private_real_dry_run_passed": bool(last.get("private_candidate_real_dry_run_passed", False)),
    "last_active_config_rotation_deg_matches": last.get("active_config_rotation_deg_matches", "unknown"),
    "orientation_json_present": bool(orientation),
    "orientation_json_allowlisted_keys": sorted(orientation.keys()) if orientation else [],
    "orientation_json_has_sensitive_fields": any(k in orientation for k in ("api_key", "api_url", "environment_id", "ssid", "password", "senha")),
    "splash_reads_public_orientation_by_default": True,
    "player_restart_after_write_required": True,
    "trigger_service_active": run(["systemctl", "is-active", "totem-settings-trigger.service"]),
    "open_service_enabled": run(["systemctl", "is-enabled", "totem-open-settings.service"]),
    "apply_policy_present": policy_path.exists(),
    "raw_values_published": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
REMOTE_DIAG
}

verify_orientation() {
  ssh "$HOST" "REMOTE_SESSION_STATUS='$REMOTE_SESSION_STATUS' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_VERIFY'
set -euo pipefail
OUT="$REMOTE_OUT_DIR/verify-orientation-propagation"
mkdir -p "$OUT"
chmod 700 "$OUT"
python3 - "$OUT/verify-status.json" "$REMOTE_SESSION_STATUS" <<'PY'
import json
import os
import pathlib
import subprocess
import sys

target = pathlib.Path(sys.argv[1])
session_status = pathlib.Path(sys.argv[2])

def load(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def run(args):
    try:
        p = subprocess.run(args, check=False, capture_output=True, text=True, timeout=4)
    except Exception:
        return "unknown"
    return (p.stdout or "").strip() or "unknown"

session = load(session_status)
orientation = load(pathlib.Path("/data/state/totem-display/orientation.json"))
expected = session.get("expected_rotation_deg")
active_match = session.get("active_config_rotation_deg_matches", "unknown")
payload = {
    "schema_version": "dadooh-c10.6.2-orientation-propagation-verify.v1",
    "expected_rotation_deg": expected,
    "active_config_rotation_deg_matches": active_match,
    "orientation_json_updated": bool(session.get("orientation_json_updated", False)),
    "orientation_json_rotation_matches": bool(session.get("orientation_json_rotation_matches", False)),
    "orientation_json_allowlisted_keys": sorted(orientation.keys()) if orientation else [],
    "splash_orientation_matches": bool(session.get("orientation_json_rotation_matches", False)),
    "media_orientation_matches": "requires_human_observation",
    "service_active": run(["systemctl", "is-active", "kiosky-player.service"]),
    "service_enabled": run(["systemctl", "is-enabled", "kiosky-player.service"]),
    "nrestarts": run(["systemctl", "show", "kiosky-player.service", "-p", "NRestarts", "--value"]),
    "public_state": (load(pathlib.Path("/tmp/dadooh-status/status.json")).get("public_state") or load(pathlib.Path("/tmp/dadooh-status/status.json")).get("state") or "unknown"),
    "playback": load(pathlib.Path("/tmp/kiosky-status.json")).get("playback_state", "unknown"),
    "raw_values_published": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
REMOTE_VERIFY
}

if [ "$MODE" != "prepare-only" ]; then
  copy_workspace
  run_prepare
  install_runtime
else
  copy_workspace
  run_prepare
  echo "C10.6.2 prepare-only complete"
  exit 0
fi

case "$MODE" in
  diagnose-current-flow)
    diagnose_current_flow
    ;;
  run-f10-cancel)
    clear_policy_and_status
    wait_for_f10_session "abrir Configuracoes e cancelar"
    ;;
  run-f10-apply-dry-run)
    echo "Dry-run com fonte privada ativa exige confirmacoes explicitas."
    echo "Type exactly:"
    echo "$SOURCE_CONFIRM_PHRASE"
    printf '> '
    IFS= read -r SOURCE_AUTH
    if [ "$SOURCE_AUTH" != "$SOURCE_CONFIRM_PHRASE" ]; then
      echo "Authorization text did not match. Aborting before reading active config." >&2
      exit 20
    fi
    echo "Type exactly:"
    echo "$DRY_RUN_CONFIRM_PHRASE"
    printf '> '
    IFS= read -r DRY_AUTH
    if [ "$DRY_AUTH" != "$DRY_RUN_CONFIRM_PHRASE" ]; then
      echo "Authorization text did not match. Aborting before F10 dry-run." >&2
      exit 21
    fi
    clear_policy_and_status
    write_policy "dry-run" "true" "false" "true"
    wait_for_f10_session "abrir Configuracoes e concluir dry-run"
    ;;
  run-f10-apply-real)
    echo "Escrita real com fonte privada ativa exige confirmacoes explicitas."
    echo "Type exactly:"
    echo "$SOURCE_CONFIRM_PHRASE"
    printf '> '
    IFS= read -r SOURCE_AUTH
    if [ "$SOURCE_AUTH" != "$SOURCE_CONFIRM_PHRASE" ]; then
      echo "Authorization text did not match. Aborting before reading active config." >&2
      exit 20
    fi
    echo "Type exactly:"
    echo "$REAL_CONFIRM_PHRASE"
    printf '> '
    IFS= read -r REAL_AUTH
    if [ "$REAL_AUTH" != "$REAL_CONFIRM_PHRASE" ]; then
      echo "Authorization text did not match. Aborting before F10 real write." >&2
      exit 21
    fi
    clear_policy_and_status
    write_policy "real-write" "false" "true" "true"
    wait_for_f10_session "abrir Configuracoes e salvar"
    ;;
  verify-orientation-propagation)
    verify_orientation
    ;;
esac
