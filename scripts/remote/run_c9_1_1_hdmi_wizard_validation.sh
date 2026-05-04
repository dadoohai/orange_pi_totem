#!/usr/bin/env bash
set -euo pipefail

HOST="root@192.168.18.115"
PREPARE_ONLY="0"
ALLOW_TEMPORARY_PLAYER_STOP="0"
REMOTE_TTY="2"

usage() {
  cat <<'USAGE'
Usage:
  run_c9_1_1_hdmi_wizard_validation.sh [host] [--prepare-only] [--allow-temporary-player-stop] [--tty N]

Modes:
  --prepare-only
      Copy scripts, run self-tests, inspect console/service readiness and write
      sanitized evidence. Does not launch the wizard and does not stop service.

  --allow-temporary-player-stop
      Allows the remote script to stop kiosky-player.service temporarily if it
      is active, run the local HDMI wizard, then restore the previous service
      state. Use only after explicit human authorization.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only)
      PREPARE_ONLY="1"
      ;;
    --allow-temporary-player-stop)
      ALLOW_TEMPORARY_PLAYER_STOP="1"
      ;;
    --tty)
      shift
      if [ "$#" -eq 0 ]; then
        echo "error: --tty requires a number" >&2
        exit 2
      fi
      REMOTE_TTY="$1"
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

case "$REMOTE_TTY" in
  ''|*[!0-9]*)
    echo "error: --tty must be a numeric virtual terminal" >&2
    exit 2
    ;;
esac

REMOTE_DIR="/tmp/dadooh-c9-1-1"
REMOTE_WIZARD_OUT_DIR="/tmp/dadooh-c9-1-1-local-wizard-hdmi"
REMOTE_EVIDENCE_DIR="/tmp/dadooh-c9-1-1-hdmi-validation"
REMOTE_CONTRACT_ALLOW_OUT_DIR="/tmp/dadooh-c9-1-1-contract-allow-mock"
REMOTE_CONTRACT_REAL_OUT_DIR="/tmp/dadooh-c9-1-1-contract-real-dry-run"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_WIZARD="$REPO_ROOT/scripts/board/totem_setup_local_wizard.py"
LOCAL_SERVER="$REPO_ROOT/scripts/board/totem_setup_minimal_server.py"
LOCAL_CONTRACT="$REPO_ROOT/scripts/board/totem_config_contract_validate.py"

if [ ! -f "$LOCAL_WIZARD" ]; then
  echo "error: missing $LOCAL_WIZARD" >&2
  exit 1
fi
if [ ! -f "$LOCAL_SERVER" ]; then
  echo "error: missing $LOCAL_SERVER" >&2
  exit 1
fi
if [ ! -f "$LOCAL_CONTRACT" ]; then
  echo "error: missing $LOCAL_CONTRACT" >&2
  exit 1
fi

echo "Preparing $REMOTE_DIR on $HOST"
ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' && chmod 700 '$REMOTE_DIR'"

echo "Copying C9.1.1 wizard validation inputs to $HOST:$REMOTE_DIR"
scp "$LOCAL_WIZARD" "$LOCAL_SERVER" "$LOCAL_CONTRACT" "$HOST:$REMOTE_DIR/"

echo "Running C9.1.1 HDMI wizard validation on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_WIZARD_OUT_DIR='$REMOTE_WIZARD_OUT_DIR' REMOTE_EVIDENCE_DIR='$REMOTE_EVIDENCE_DIR' REMOTE_CONTRACT_ALLOW_OUT_DIR='$REMOTE_CONTRACT_ALLOW_OUT_DIR' REMOTE_CONTRACT_REAL_OUT_DIR='$REMOTE_CONTRACT_REAL_OUT_DIR' PREPARE_ONLY='$PREPARE_ONLY' ALLOW_TEMPORARY_PLAYER_STOP='$ALLOW_TEMPORARY_PLAYER_STOP' REMOTE_TTY='$REMOTE_TTY' bash -s" <<'REMOTE_SH'
set -euo pipefail

WIZARD="$REMOTE_DIR/totem_setup_local_wizard.py"
SERVER="$REMOTE_DIR/totem_setup_minimal_server.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
STATUS_FILE="$REMOTE_EVIDENCE_DIR/status.json"
SUMMARY_FILE="$REMOTE_EVIDENCE_DIR/summary.txt"
SERVICE_WAS_ACTIVE="0"
SERVICE_STOPPED_BY_SCRIPT="0"
SERVICE_RESTORED="1"
WIZARD_EXIT_CODE="not_run"
RESULT="started"
ABORT_REASON=""
OPENVT_AVAILABLE="false"
CHVT_AVAILABLE="false"
CURRENT_VT="unknown"
PLAYER_PROCESS_COUNT_BEFORE="0"
PLAYER_PROCESS_COUNT_AFTER="0"
MPV_PROCESS_COUNT_BEFORE="0"
MPV_PROCESS_COUNT_AFTER="0"
SERVICE_ACTIVE_BEFORE="unknown"
SERVICE_ACTIVE_AFTER="unknown"
SERVICE_ENABLED_BEFORE="unknown"
SERVICE_ENABLED_AFTER="unknown"
CANDIDATE_GENERATED="false"
CONTRACT_ALLOW_MOCK_VALID="false"
CONTRACT_REAL_DRY_RUN_EXPECTED_FAILURE="false"

write_evidence() {
  RESULT="$1" \
  ABORT_REASON="$2" \
  PREPARE_ONLY="$PREPARE_ONLY" \
  ALLOW_TEMPORARY_PLAYER_STOP="$ALLOW_TEMPORARY_PLAYER_STOP" \
  REMOTE_TTY="$REMOTE_TTY" \
  OPENVT_AVAILABLE="$OPENVT_AVAILABLE" \
  CHVT_AVAILABLE="$CHVT_AVAILABLE" \
  CURRENT_VT="$CURRENT_VT" \
  SERVICE_ACTIVE_BEFORE="$SERVICE_ACTIVE_BEFORE" \
  SERVICE_ACTIVE_AFTER="$SERVICE_ACTIVE_AFTER" \
  SERVICE_ENABLED_BEFORE="$SERVICE_ENABLED_BEFORE" \
  SERVICE_ENABLED_AFTER="$SERVICE_ENABLED_AFTER" \
  SERVICE_STOPPED_BY_SCRIPT="$SERVICE_STOPPED_BY_SCRIPT" \
  SERVICE_RESTORED="$SERVICE_RESTORED" \
  PLAYER_PROCESS_COUNT_BEFORE="$PLAYER_PROCESS_COUNT_BEFORE" \
  PLAYER_PROCESS_COUNT_AFTER="$PLAYER_PROCESS_COUNT_AFTER" \
  MPV_PROCESS_COUNT_BEFORE="$MPV_PROCESS_COUNT_BEFORE" \
  MPV_PROCESS_COUNT_AFTER="$MPV_PROCESS_COUNT_AFTER" \
  WIZARD_EXIT_CODE="$WIZARD_EXIT_CODE" \
  CANDIDATE_GENERATED="$CANDIDATE_GENERATED" \
  CONTRACT_ALLOW_MOCK_VALID="$CONTRACT_ALLOW_MOCK_VALID" \
  CONTRACT_REAL_DRY_RUN_EXPECTED_FAILURE="$CONTRACT_REAL_DRY_RUN_EXPECTED_FAILURE" \
  REMOTE_WIZARD_OUT_DIR="$REMOTE_WIZARD_OUT_DIR" \
  REMOTE_EVIDENCE_DIR="$REMOTE_EVIDENCE_DIR" \
  python3 - <<'PY'
import datetime
import json
import os
import pathlib
import stat

evidence_dir = pathlib.Path(os.environ["REMOTE_EVIDENCE_DIR"])
evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
if stat.S_IMODE(evidence_dir.stat().st_mode) != 0o700:
    evidence_dir.chmod(0o700)

def bool_env(name):
    return os.environ.get(name) == "1" or os.environ.get(name) == "true"

def int_env(name):
    try:
        return int(os.environ.get(name, "0"))
    except ValueError:
        return 0

status = {
    "schema_version": "dadooh-c9.1.1-hdmi-wizard-human-validation.v1",
    "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    "result": os.environ["RESULT"],
    "abort_reason": os.environ["ABORT_REASON"],
    "mode": {
        "prepare_only": bool_env("PREPARE_ONLY"),
        "launch_requested": not bool_env("PREPARE_ONLY"),
        "human_validation_required": True,
    },
    "console": {
        "requested_virtual_terminal": int_env("REMOTE_TTY"),
        "current_virtual_terminal_observed": os.environ["CURRENT_VT"],
        "openvt_available": os.environ["OPENVT_AVAILABLE"] == "true",
        "chvt_available": os.environ["CHVT_AVAILABLE"] == "true",
    },
    "service": {
        "active_before": os.environ["SERVICE_ACTIVE_BEFORE"],
        "active_after": os.environ["SERVICE_ACTIVE_AFTER"],
        "enabled_before": os.environ["SERVICE_ENABLED_BEFORE"],
        "enabled_after": os.environ["SERVICE_ENABLED_AFTER"],
        "temporary_stop_authorized": bool_env("ALLOW_TEMPORARY_PLAYER_STOP"),
        "temporary_stop_performed": bool_env("SERVICE_STOPPED_BY_SCRIPT"),
        "previous_state_restored": bool_env("SERVICE_RESTORED"),
    },
    "process_categories": {
        "player_before_count": int_env("PLAYER_PROCESS_COUNT_BEFORE"),
        "player_after_count": int_env("PLAYER_PROCESS_COUNT_AFTER"),
        "mpv_before_count": int_env("MPV_PROCESS_COUNT_BEFORE"),
        "mpv_after_count": int_env("MPV_PROCESS_COUNT_AFTER"),
        "pids_written": False,
        "cmdlines_written": False,
    },
    "wizard": {
        "exit_code": os.environ["WIZARD_EXIT_CODE"],
        "candidate_generated": bool_env("CANDIDATE_GENERATED"),
        "out_dir": os.environ["REMOTE_WIZARD_OUT_DIR"],
        "out_dir_under_tmp": os.environ["REMOTE_WIZARD_OUT_DIR"].startswith("/tmp/"),
    },
    "contract_validation": {
        "allow_mock_valid": bool_env("CONTRACT_ALLOW_MOCK_VALID"),
        "real_dry_run_expected_failure": bool_env("CONTRACT_REAL_DRY_RUN_EXPECTED_FAILURE"),
    },
    "human_checklist": {
        "screen_legible": "pending_human_answer",
        "looks_like_product_or_terminal": "pending_human_answer",
        "keyboard_navigation_works": "pending_human_answer",
        "environment_orientation_review_understood": "pending_human_answer",
        "technical_language_too_high": "pending_human_answer",
        "operator_can_cancel_or_exit": "pending_human_answer",
        "candidate_generated_under_tmp": bool_env("CANDIDATE_GENERATED"),
    },
    "guardrails": {
        "writes_only_under_tmp": True,
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "data_config_touched": False,
        "data_written": False,
        "opt_written": False,
        "network_changed": False,
        "wifi_changed": False,
        "hotspot_created": False,
        "nmcli_called": False,
        "backend_called": False,
        "launcher_integrated": False,
        "config_missing_auto_start_changed": False,
        "permanent_service_change": False,
    },
    "privacy": {
        "candidate_payload_copied": False,
        "private_values_used": False,
        "private_values_written": False,
        "environment_identifier_raw_written": False,
        "credential_value_written": False,
        "private_url_written": False,
        "network_metadata_written": False,
        "raw_logs_written": False,
    },
}

summary = "\n".join([
    "Dadooh C9.1.1 validacao humana do wizard local HDMI",
    "",
    f"schema_version: {status['schema_version']}",
    f"generated_at_utc: {status['generated_at_utc']}",
    f"result: {status['result']}",
    f"abort_reason: {status['abort_reason']}",
    f"prepare_only: {str(status['mode']['prepare_only']).lower()}",
    f"requested_virtual_terminal: {status['console']['requested_virtual_terminal']}",
    f"openvt_available: {str(status['console']['openvt_available']).lower()}",
    f"temporary_stop_authorized: {str(status['service']['temporary_stop_authorized']).lower()}",
    f"temporary_stop_performed: {str(status['service']['temporary_stop_performed']).lower()}",
    f"previous_state_restored: {str(status['service']['previous_state_restored']).lower()}",
    f"wizard_exit_code: {status['wizard']['exit_code']}",
    f"candidate_generated: {str(status['wizard']['candidate_generated']).lower()}",
    f"allow_mock_valid: {str(status['contract_validation']['allow_mock_valid']).lower()}",
    f"real_dry_run_expected_failure: {str(status['contract_validation']['real_dry_run_expected_failure']).lower()}",
    "",
    "Human checklist:",
    "screen_legible: pending_human_answer",
    "looks_like_product_or_terminal: pending_human_answer",
    "keyboard_navigation_works: pending_human_answer",
    "environment_orientation_review_understood: pending_human_answer",
    "technical_language_too_high: pending_human_answer",
    "operator_can_cancel_or_exit: pending_human_answer",
    "",
    "Guardrails:",
    "writes_only_under_tmp: true",
    "real_config_read: false",
    "real_config_written: false",
    "writer_called: false",
    "data_config_touched: false",
    "data_written: false",
    "opt_written: false",
    "network_changed: false",
    "wifi_changed: false",
    "hotspot_created: false",
    "launcher_integrated: false",
    "config_missing_auto_start_changed: false",
    "permanent_service_change: false",
    "",
    "Privacy:",
    "candidate_payload_copied: false",
    "private_values_used: false",
    "credential_value_written: false",
    "private_url_written: false",
    "raw_logs_written: false",
])

status_path = evidence_dir / "status.json"
summary_path = evidence_dir / "summary.txt"
status_path.write_text(json.dumps(status, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
summary_path.write_text(summary + "\n", encoding="utf-8")
status_path.chmod(0o600)
summary_path.chmod(0o600)
PY
}

service_active() {
  systemctl is-active kiosky-player.service 2>/dev/null || true
}

service_enabled() {
  systemctl is-enabled kiosky-player.service 2>/dev/null || true
}

count_process_categories() {
  python3 - <<'PY'
import pathlib

player = 0
mpv = 0
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    try:
        cmdline = (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
        comm = (proc / "comm").read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        continue
    lower = f"{comm} {cmdline}".lower()
    if "mpv" in lower:
        mpv += 1
    if "kiosk.py" in lower or "kiosky-player" in lower:
        player += 1
print(f"{player} {mpv}")
PY
}

refresh_observations_before() {
  if command -v openvt >/dev/null 2>&1; then
    OPENVT_AVAILABLE="true"
  fi
  if command -v chvt >/dev/null 2>&1; then
    CHVT_AVAILABLE="true"
  fi
  if [ -r /sys/class/tty/tty0/active ]; then
    CURRENT_VT="$(cat /sys/class/tty/tty0/active 2>/dev/null || echo unknown)"
  fi
  SERVICE_ACTIVE_BEFORE="$(service_active)"
  SERVICE_ENABLED_BEFORE="$(service_enabled)"
  set -- $(count_process_categories)
  PLAYER_PROCESS_COUNT_BEFORE="$1"
  MPV_PROCESS_COUNT_BEFORE="$2"
  if [ "$SERVICE_ACTIVE_BEFORE" = "active" ]; then
    SERVICE_WAS_ACTIVE="1"
  fi
}

refresh_observations_after() {
  SERVICE_ACTIVE_AFTER="$(service_active)"
  SERVICE_ENABLED_AFTER="$(service_enabled)"
  set -- $(count_process_categories)
  PLAYER_PROCESS_COUNT_AFTER="$1"
  MPV_PROCESS_COUNT_AFTER="$2"
}

restore_service_if_needed() {
  if [ "$SERVICE_STOPPED_BY_SCRIPT" = "1" ] && [ "$SERVICE_WAS_ACTIVE" = "1" ]; then
    systemctl start kiosky-player.service
    for _ in $(seq 1 30); do
      if [ "$(service_active)" = "active" ]; then
        SERVICE_RESTORED="1"
        return 0
      fi
      sleep 1
    done
    return 1
  fi
  SERVICE_RESTORED="1"
}

on_exit() {
  rc="$?"
  if [ "$SERVICE_STOPPED_BY_SCRIPT" = "1" ] && [ "$SERVICE_RESTORED" != "1" ]; then
    restore_service_if_needed || true
  fi
  refresh_observations_after || true
  if [ "$RESULT" = "started" ]; then
    if [ "$rc" -eq 0 ]; then
      RESULT="passed"
    else
      RESULT="failed"
      ABORT_REASON="unexpected_exit_${rc}"
    fi
  fi
  write_evidence "$RESULT" "$ABORT_REASON" || true
  exit "$rc"
}
trap on_exit EXIT

umask 077
mkdir -p "$REMOTE_DIR" "$REMOTE_EVIDENCE_DIR"
chmod 700 "$REMOTE_DIR" "$REMOTE_EVIDENCE_DIR"
rm -rf "$REMOTE_WIZARD_OUT_DIR" "$REMOTE_CONTRACT_ALLOW_OUT_DIR" "$REMOTE_CONTRACT_REAL_OUT_DIR"

python3 "$CONTRACT" --self-test
python3 "$SERVER" --self-test
python3 "$WIZARD" --self-test

refresh_observations_before

if [ "$OPENVT_AVAILABLE" != "true" ]; then
  RESULT="blocked"
  ABORT_REASON="openvt_unavailable"
  exit 20
fi

if [ "$PREPARE_ONLY" = "1" ]; then
  RESULT="prepared"
  ABORT_REASON="prepare_only_no_launch"
  exit 0
fi

  if [ "$SERVICE_WAS_ACTIVE" = "1" ] || [ "$PLAYER_PROCESS_COUNT_BEFORE" != "0" ] || [ "$MPV_PROCESS_COUNT_BEFORE" != "0" ]; then
  if [ "$ALLOW_TEMPORARY_PLAYER_STOP" != "1" ]; then
    RESULT="blocked"
    ABORT_REASON="temporary_player_stop_requires_human_authorization"
    exit 20
  fi
  SERVICE_RESTORED="0"
  systemctl stop kiosky-player.service
  SERVICE_STOPPED_BY_SCRIPT="1"
  for _ in $(seq 1 30); do
    if [ "$(service_active)" != "active" ]; then
      break
    fi
    sleep 1
  done
  if [ "$(service_active)" = "active" ]; then
    RESULT="failed"
    ABORT_REASON="service_did_not_stop"
    exit 1
  fi
fi

echo "C9.1.1: wizard will appear on HDMI virtual terminal $REMOTE_TTY."
echo "Use USB keyboard: arrows or j/k, Enter, b on review, q/Esc to cancel."
echo "SSH session will wait until the operator exits the wizard."

set +e
openvt -c "$REMOTE_TTY" -s -f -w -- env TERM=linux python3 "$WIZARD" --out-dir "$REMOTE_WIZARD_OUT_DIR"
WIZARD_RC="$?"
set -e
WIZARD_EXIT_CODE="$WIZARD_RC"

if [ "$WIZARD_RC" -ne 0 ]; then
  RESULT="failed"
  ABORT_REASON="wizard_exit_${WIZARD_RC}"
  exit "$WIZARD_RC"
fi

if [ ! -f "$REMOTE_WIZARD_OUT_DIR/candidate-config.json" ]; then
  RESULT="failed"
  ABORT_REASON="candidate_not_generated"
  exit 1
fi
CANDIDATE_GENERATED="true"

python3 "$CONTRACT" \
  --candidate "$REMOTE_WIZARD_OUT_DIR/candidate-config.json" \
  --allow-mock \
  --out-dir "$REMOTE_CONTRACT_ALLOW_OUT_DIR"
CONTRACT_ALLOW_MOCK_VALID="true"

if python3 "$CONTRACT" \
  --candidate "$REMOTE_WIZARD_OUT_DIR/candidate-config.json" \
  --real-dry-run \
  --out-dir "$REMOTE_CONTRACT_REAL_OUT_DIR"; then
  RESULT="failed"
  ABORT_REASON="real_dry_run_unexpectedly_passed"
  exit 1
else
  rc="$?"
  if [ "$rc" -ne 2 ]; then
    RESULT="failed"
    ABORT_REASON="real_dry_run_unexpected_exit_${rc}"
    exit "$rc"
  fi
fi
CONTRACT_REAL_DRY_RUN_EXPECTED_FAILURE="true"

python3 - <<'PY'
import json
import os
import pathlib
import stat

out_dir = pathlib.Path(os.environ["REMOTE_WIZARD_OUT_DIR"])
expected = {"candidate-config.json", "status.json", "summary.txt"}
if stat.S_IMODE(out_dir.stat().st_mode) != 0o700:
    raise AssertionError("wizard out-dir mode is not 0700")
actual = {path.name for path in out_dir.iterdir() if path.is_file()}
if expected - actual:
    raise AssertionError(f"missing wizard artifacts: {sorted(expected - actual)}")
for name in expected:
    path = out_dir / name
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise AssertionError(f"{name} mode is not 0600")
    resolved = path.resolve(strict=True)
    if not str(resolved).startswith("/tmp/"):
        raise AssertionError(f"{name} escaped /tmp")
    if str(resolved).startswith("/data/") or str(resolved).startswith("/opt/"):
        raise AssertionError(f"{name} was written outside /tmp")

status = json.loads((out_dir / "status.json").read_text(encoding="utf-8"))
if status["schema_version"] != "dadooh-c9.1-local-setup-wizard.v1":
    raise AssertionError("wizard status schema mismatch")
if status["interface"]["free_shell_available"] is not False:
    raise AssertionError("wizard status did not keep free shell blocked")
if status["guardrails"]["real_config_written"] is not False:
    raise AssertionError("wizard status did not keep real_config_written false")
if status["guardrails"]["writer_called"] is not False:
    raise AssertionError("wizard status did not keep writer_called false")

combined = (out_dir / "status.json").read_text(encoding="utf-8") + "\n" + (
    out_dir / "summary.txt"
).read_text(encoding="utf-8")
for forbidden in (
    "ENV-MOCK-LOJA-A",
    "ENV-MOCK-RECEPCAO",
    "ENV-MOCK-VITRINE",
    "Ambiente Loja A - TESTE",
    "API_KEY_MOCK_NOT_FOR_PRODUCTION",
    "https://api.example.invalid/search",
    "api_key",
    "api_url",
    "token",
    "secret",
    "password",
    "senha",
    "ssid",
    "hostname",
    "gateway",
    "raw_payload",
):
    if forbidden.lower() in combined.lower():
        raise AssertionError(f"wizard status/summary leaked forbidden text: {forbidden}")
PY

restore_service_if_needed
RESULT="passed"
ABORT_REASON=""
REMOTE_SH
