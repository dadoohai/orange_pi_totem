#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
REMOTE_TTY="2"
RUN_TIMEOUT_SEC="1800"
PREVIEW_SEC="12"
TRIGGER_TIMEOUT_SEC="120"
REMOTE_DIR="/tmp/dadooh-c10-6-open-settings"
REMOTE_OUT_DIR="/tmp/dadooh-c10-6-open-settings-from-player"
REMOTE_WIZARD_OUT_DIR="/tmp/dadooh-c10-6-visual-wizard"
REMOTE_HANDOFF_OUT_DIR="/tmp/dadooh-c10-6-handoff"
REMOTE_PRIVATE_VALUES="/tmp/dadooh-c10-6-private/private-values.json"
PRIVATE_SOURCE_MODE="tmp-file"
SOURCE_CONFIRM_PHRASE="CONFIRMO USAR CONFIG ATIVA COMO FONTE PRIVADA C10.6"
PAUSE_CONFIRM_PHRASE="CONFIRMO C10.6 ABRIR CONFIGURACOES COM PAUSA DO PLAYER"
DRY_RUN_CONFIRM_PHRASE="CONFIRMO CONFIGURACOES DRY RUN C10.6 COM PAUSA DO PLAYER"
REAL_WRITE_CONFIRM_PHRASE="CONFIRMO CONFIGURACOES WRITER REAL C10.6"
TRIGGER_UNIT="dadooh-settings-trigger.service"
REQUEST_DIR="/run/dadooh-settings"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_6_open_settings_from_player.sh <host> [mode] [--tty N] [--timeout-sec N] [--preview-sec N]

Modes:
  --prepare-only
      Copy scripts to /tmp and run non-invasive checks.

  --preview-open-settings
      Requires confirmation. Pauses the player, previews the existing visual
      settings wizard, then restores the player.

  --run-open-cancel
      Requires confirmation. Opens the existing visual wizard from the running
      player and expects cancellation.

  --run-open-complete-dry-run
      Requires confirmation. Opens the visual wizard, generates a candidate,
      performs private handoff/C5.1 real-dry-run, and does not call writer.

  --install-trigger-temporary
      Installs a temporary systemd service under /run that detects local
      settings shortcuts.
      It is not enabled persistently.

  --uninstall-trigger-temporary
      Stops/removes the temporary trigger unit and request file.

  --run-trigger-local-human
      Installs the temporary trigger, asks a human to hold Ctrl+I or F10 for
      5 seconds, then opens the visual wizard directly.

  --run-trigger-f12-human
      Compatibility alias for --run-trigger-local-human. F12 is still accepted
      as a fallback by the trigger, but Ctrl+I and F10 are the documented V0
      shortcuts.

  --run-open-complete-real-write
      Requires confirmation and delegates to the already validated C10.4 writer
      runner. This wrapper does not reimplement writer behavior.

Private source options for dry-run:
  --private-values /tmp/.../private-values.json
  --private-values-from-active-config
      Requires exact confirmation before reading only approved private endpoint
      categories from the active config into a restricted temporary file.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --preview-open-settings) MODE="preview-open-settings" ;;
    --run-open-cancel) MODE="run-open-cancel" ;;
    --run-open-complete-dry-run) MODE="run-open-complete-dry-run" ;;
    --install-trigger-temporary) MODE="install-trigger-temporary" ;;
    --uninstall-trigger-temporary) MODE="uninstall-trigger-temporary" ;;
    --run-trigger-local-human) MODE="run-trigger-local-human" ;;
    --run-trigger-f12-human) MODE="run-trigger-local-human" ;;
    --run-open-complete-real-write) MODE="run-open-complete-real-write" ;;
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
    --trigger-timeout-sec)
      shift
      TRIGGER_TIMEOUT_SEC="${1:-}"
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
  prepare-only|preview-open-settings|run-open-cancel|run-open-complete-dry-run|install-trigger-temporary|uninstall-trigger-temporary|run-trigger-local-human|run-open-complete-real-write)
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

case "$REMOTE_TTY" in ''|*[!0-9]*|0) echo "error: --tty must be a positive integer" >&2; exit 2 ;; esac
case "$RUN_TIMEOUT_SEC" in ''|*[!0-9]*|0) echo "error: --timeout-sec must be a positive integer" >&2; exit 2 ;; esac
case "$PREVIEW_SEC" in ''|*[!0-9]*|0) echo "error: --preview-sec must be a positive integer" >&2; exit 2 ;; esac
case "$TRIGGER_TIMEOUT_SEC" in ''|*[!0-9]*|0) echo "error: --trigger-timeout-sec must be a positive integer" >&2; exit 2 ;; esac
case "$REMOTE_PRIVATE_VALUES" in /tmp/*) ;; *) echo "error: --private-values must be under /tmp on the board" >&2; exit 2 ;; esac
case "$PRIVATE_SOURCE_MODE" in tmp-file|active-config) ;; *) echo "error: unsupported private source mode" >&2; exit 2 ;; esac

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
LOCAL_TRIGGER="$BOARD_DIR/totem_settings_trigger.py"
LOCAL_SESSION="$BOARD_DIR/totem_open_settings_session.sh"
LOCAL_C10_4_RUNNER="$SCRIPT_DIR/run_c10_4_product_surface_writer_real.sh"

for path in \
  "$LOCAL_VISUAL_WIZARD" "$LOCAL_WIZARD" "$LOCAL_MINIMAL_SERVER" "$LOCAL_CONTRACT" "$LOCAL_WIFI_ADAPTER" \
  "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_HANDOFF" "$LOCAL_SPLASH" "$LOCAL_TRIGGER" "$LOCAL_SESSION"
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
    "$LOCAL_VISUAL_WIZARD" "$LOCAL_WIZARD" "$LOCAL_MINIMAL_SERVER" "$LOCAL_CONTRACT" "$LOCAL_WIFI_ADAPTER" \
    "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_HANDOFF" "$LOCAL_SPLASH" "$LOCAL_TRIGGER" "$LOCAL_SESSION" \
    "$HOST:$REMOTE_DIR/" >/dev/null
  ssh "$HOST" "chmod +x '$REMOTE_DIR/totem_open_settings_session.sh' '$REMOTE_DIR/totem_settings_trigger.py'"
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
TRIGGER="$REMOTE_DIR/totem_settings_trigger.py"
SESSION="$REMOTE_DIR/totem_open_settings_session.sh"
SCRIPTED_OUT="$REMOTE_OUT_DIR/prepare-scripted-visual"
umask 077
rm -rf "$SCRIPTED_OUT"
mkdir -p "$REMOTE_OUT_DIR" "$SCRIPTED_OUT"
chmod 700 "$REMOTE_OUT_DIR" "$SCRIPTED_OUT"
bash -n "$SESSION"
python3 "$CONTRACT" --self-test
python3 "$WIFI_ADAPTER" --self-test --out-dir "$REMOTE_OUT_DIR/adapter-self-test" >/dev/null
python3 "$WIZARD" --self-test
python3 "$VISUAL" --self-test
python3 "$HANDOFF" --self-test
python3 "$SPLASH" --self-test
python3 "$TRIGGER" --self-test
python3 "$VISUAL" \
  --scripted \
  --environment-id ENV-C10-6-OPEN-SETTINGS \
  --rotation-key landscape \
  --network-step configured_wifi \
  --out-dir "$SCRIPTED_OUT" >/dev/null
python3 "$CONTRACT" --candidate "$SCRIPTED_OUT/config.candidate.json" --allow-mock --out-dir "$REMOTE_OUT_DIR/prepare-allow" >/dev/null
echo "remote C10.6 prepare checks: ok"
REMOTE_PREP
}

install_trigger() {
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REQUEST_DIR='$REQUEST_DIR' TRIGGER_TIMEOUT_SEC='$TRIGGER_TIMEOUT_SEC' TRIGGER_UNIT='$TRIGGER_UNIT' bash -s" <<'REMOTE_INSTALL'
set -euo pipefail
umask 077
mkdir -p "$REQUEST_DIR" /run/systemd/system
chmod 700 "$REQUEST_DIR"
cat > "/run/systemd/system/$TRIGGER_UNIT" <<UNIT
[Unit]
Description=Dadooh C10.6 temporary settings trigger

[Service]
Type=simple
ExecStart=/usr/bin/python3 $REMOTE_DIR/totem_settings_trigger.py --wait-once --request-dir $REQUEST_DIR --hold-sec 5 --timeout-sec $TRIGGER_TIMEOUT_SEC
Restart=no
StandardOutput=null
StandardError=null
UNIT
chmod 600 "/run/systemd/system/$TRIGGER_UNIT"
systemctl daemon-reload
rm -f "$REQUEST_DIR/request.json" "$REQUEST_DIR/trigger-status.json" "$REQUEST_DIR/summary.txt"
echo "temporary_trigger_installed=true"
echo "persistent_enabled=false"
REMOTE_INSTALL
}

uninstall_trigger() {
  ssh "$HOST" "REQUEST_DIR='$REQUEST_DIR' TRIGGER_UNIT='$TRIGGER_UNIT' bash -s" <<'REMOTE_UNINSTALL'
set -euo pipefail
systemctl stop "$TRIGGER_UNIT" >/dev/null 2>&1 || true
rm -f "/run/systemd/system/$TRIGGER_UNIT"
systemctl daemon-reload
rm -f "$REQUEST_DIR/request.json" "$REQUEST_DIR/trigger-status.json" "$REQUEST_DIR/summary.txt" 2>/dev/null || true
rmdir "$REQUEST_DIR" 2>/dev/null || true
echo "temporary_trigger_installed=false"
REMOTE_UNINSTALL
}

run_session() {
  local session_mode="$1"
  local expected="$2"
  local suffix="$3"
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_WIZARD_OUT_DIR='$REMOTE_WIZARD_OUT_DIR' REMOTE_TTY='$REMOTE_TTY' RUN_TIMEOUT_SEC='$RUN_TIMEOUT_SEC' PREVIEW_SEC='$PREVIEW_SEC' SESSION_MODE='$session_mode' EXPECTED='$expected' SUFFIX='$suffix' bash -s" <<'REMOTE_SESSION'
set -euo pipefail
"$REMOTE_DIR/totem_open_settings_session.sh" \
  --mode "$SESSION_MODE" \
  --expect "$EXPECTED" \
  --tty "$REMOTE_TTY" \
  --timeout-sec "$RUN_TIMEOUT_SEC" \
  --preview-sec "$PREVIEW_SEC" \
  --out-dir "$REMOTE_OUT_DIR/$SUFFIX" \
  --wizard-out-dir "$REMOTE_WIZARD_OUT_DIR-$SUFFIX"
REMOTE_SESSION
}

prepare_private_from_active_config_if_needed() {
  if [ "$PRIVATE_SOURCE_MODE" != "active-config" ]; then
    return 0
  fi
  confirm_exact "$SOURCE_CONFIRM_PHRASE" "O dry-run usara a config ativa apenas como fonte privada temporaria. Valores nao serao impressos."
  ssh "$HOST" "REMOTE_PRIVATE_VALUES='$REMOTE_PRIVATE_VALUES' bash -s" <<'REMOTE_PRIVATE'
set -euo pipefail
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
REMOTE_PRIVATE
}

run_handoff_dry_run() {
  local suffix="$1"
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_WIZARD_OUT_DIR='$REMOTE_WIZARD_OUT_DIR' REMOTE_HANDOFF_OUT_DIR='$REMOTE_HANDOFF_OUT_DIR' REMOTE_PRIVATE_VALUES='$REMOTE_PRIVATE_VALUES' PRIVATE_SOURCE_MODE='$PRIVATE_SOURCE_MODE' SUFFIX='$suffix' bash -s" <<'REMOTE_HANDOFF'
set -euo pipefail
HANDOFF="$REMOTE_DIR/totem_visual_setup_writer_handoff.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
WIZARD_OUT="$REMOTE_WIZARD_OUT_DIR-$SUFFIX"
HANDOFF_OUT="$REMOTE_HANDOFF_OUT_DIR-$SUFFIX"
RUN_OUT="$REMOTE_OUT_DIR/$SUFFIX"
mkdir -p "$HANDOFF_OUT" "$RUN_OUT/validate-real"
chmod 700 "$HANDOFF_OUT" "$RUN_OUT" "$RUN_OUT/validate-real"
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
python3 "$HANDOFF" \
  --source-candidate "$WIZARD_OUT/config.candidate.json" \
  --private-values "$REMOTE_PRIVATE_VALUES" \
  --out-dir "$HANDOFF_OUT" \
  --confirm-private-values-approved >/dev/null
python3 "$CONTRACT" \
  --candidate "$HANDOFF_OUT/config.candidate.private.json" \
  --real-dry-run \
  --out-dir "$RUN_OUT/validate-real" >/dev/null
rm -f "$HANDOFF_OUT/config.candidate.private.json" "$WIZARD_OUT/config.candidate.json"
if [ "$PRIVATE_SOURCE_MODE" = "active-config" ]; then
  rm -rf "$(dirname "$REMOTE_PRIVATE_VALUES")"
fi
python3 - "$RUN_OUT/dry-run-status.json" "$HANDOFF_OUT/setup-status.json" <<'PY'
import json
import os
import pathlib
import stat
import sys
target = pathlib.Path(sys.argv[1])
handoff = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
payload = {
    "schema_version": "dadooh-c10.6-open-settings-dry-run.v1",
    "dry_run_result": "passed" if handoff.get("result") == "passed" else "unknown",
    "private_real_dry_run_passed": bool(handoff.get("contract_validation", {}).get("private_real_dry_run", {}).get("valid")),
    "writer_called": False,
    "real_config_written": False,
    "private_values_published": False,
    "raw_logs_written": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
REMOTE_HANDOFF
}

wait_for_trigger_request() {
  ssh "$HOST" "REQUEST_DIR='$REQUEST_DIR' TRIGGER_UNIT='$TRIGGER_UNIT' TRIGGER_TIMEOUT_SEC='$TRIGGER_TIMEOUT_SEC' bash -s" <<'REMOTE_WAIT'
set -euo pipefail
rm -f "$REQUEST_DIR/request.json" "$REQUEST_DIR/trigger-status.json" "$REQUEST_DIR/summary.txt" 2>/dev/null || true
systemctl start "$TRIGGER_UNIT"
deadline=$(( $(date +%s) + TRIGGER_TIMEOUT_SEC + 10 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  if [ -f "$REQUEST_DIR/request.json" ]; then
    python3 - "$REQUEST_DIR/request.json" <<'PY'
import json
import pathlib
import sys
data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
if data.get("trigger_type") not in {"keyboard_ctrl_i_hold", "keyboard_f10_hold", "keyboard_f12_hold"} or data.get("action") != "open_settings":
    raise SystemExit("unexpected_request")
print("trigger_detected=true")
PY
    exit 0
  fi
  if ! systemctl is-active --quiet "$TRIGGER_UNIT"; then
    break
  fi
  sleep 1
done
systemctl status "$TRIGGER_UNIT" --no-pager >/dev/null 2>&1 || true
echo "trigger_detected=false" >&2
exit 124
REMOTE_WAIT
}

prepare_workspace
run_prepare_checks

case "$MODE" in
  prepare-only)
    echo "C10.6 prepare-only complete. Evidence dir reserved: $REMOTE_OUT_DIR"
    ;;
  preview-open-settings)
    confirm_exact "$PAUSE_CONFIRM_PHRASE" "HDMI/tela e teclado local devem estar conectados. O player sera pausado temporariamente para abrir Configuracoes."
    run_session preview preview preview-open-settings
    ;;
  run-open-cancel)
    confirm_exact "$PAUSE_CONFIRM_PHRASE" "Abra Configuracoes do Totem e cancele no wizard. O player deve voltar sem alterar config."
    run_session interactive cancelled run-open-cancel
    ;;
  run-open-complete-dry-run)
    prepare_private_from_active_config_if_needed
    confirm_exact "$DRY_RUN_CONFIRM_PHRASE" "Complete o wizard visual. O fluxo roda handoff/C5.1 real-dry-run e nao chama writer."
    run_session interactive candidate_ready run-open-complete-dry-run
    run_handoff_dry_run run-open-complete-dry-run
    ;;
  install-trigger-temporary)
    install_trigger
    ;;
  uninstall-trigger-temporary)
    uninstall_trigger
    ;;
  run-trigger-local-human)
    confirm_exact "$PAUSE_CONFIRM_PHRASE" "Segure Ctrl+I ou F10 por 5 segundos no teclado local. O wizard abrira diretamente; cancele nele para este teste."
    install_trigger
    echo "Aguardando Ctrl+I ou F10 segurado por 5 segundos no teclado local..."
    wait_for_trigger_request
    run_session interactive any run-trigger-local-human
    uninstall_trigger
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
