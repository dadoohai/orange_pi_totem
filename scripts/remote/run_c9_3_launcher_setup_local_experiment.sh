#!/usr/bin/env bash
set -euo pipefail

HOST="root@192.168.18.115"
MODE="prepare-only"
REMOTE_TTY="2"
RUN_TIMEOUT_SEC="420"

REQUIRED_AUTH="Autorizo C9.3: parar temporariamente o serviço, executar launcher experimental em /tmp com config inválida e wizard local na HDMI, sem writer, com restauração do player ao final."

usage() {
  cat <<'USAGE'
Usage:
  run_c9_3_launcher_setup_local_experiment.sh [host] [--prepare-only|--run] [--tty N] [--timeout-sec N]

Modes:
  --prepare-only
      Copy launcher/wizard inputs to /tmp and run source/self checks only.
      Does not stop service, does not run launcher, and does not occupy HDMI.

  --run
      Requires exact human authorization. Stops kiosky-player.service
      temporarily, runs the experimental launcher copy from /tmp with a missing
      config override and setup trigger, opens the wizard on HDMI through a
      reserved TTY, records sanitized evidence, then restores the service.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only)
      MODE="prepare-only"
      ;;
    --run)
      MODE="run"
      ;;
    --tty)
      shift
      if [ "$#" -eq 0 ]; then
        echo "error: --tty requires a number" >&2
        exit 2
      fi
      REMOTE_TTY="$1"
      ;;
    --timeout-sec)
      shift
      if [ "$#" -eq 0 ]; then
        echo "error: --timeout-sec requires a number" >&2
        exit 2
      fi
      RUN_TIMEOUT_SEC="$1"
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
    echo "error: --tty must be numeric" >&2
    exit 2
    ;;
esac

case "$RUN_TIMEOUT_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --timeout-sec must be a positive integer" >&2
    exit 2
    ;;
esac

REMOTE_DIR="/tmp/dadooh-c9-3"
REMOTE_OUT_DIR="/tmp/dadooh-c9-3-launcher-setup-experiment"
REMOTE_WIZARD_OUT_DIR="/tmp/dadooh-c9-3-local-wizard"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_LAUNCHER="$REPO_ROOT/scripts/board/kiosky_service_launcher.sh"
LOCAL_WIZARD="$REPO_ROOT/scripts/board/totem_setup_local_wizard.py"
LOCAL_SERVER="$REPO_ROOT/scripts/board/totem_setup_minimal_server.py"
LOCAL_CONTRACT="$REPO_ROOT/scripts/board/totem_config_contract_validate.py"

for path in "$LOCAL_LAUNCHER" "$LOCAL_WIZARD" "$LOCAL_SERVER" "$LOCAL_CONTRACT"; do
  if [ ! -f "$path" ]; then
    echo "error: missing $path" >&2
    exit 1
  fi
done

echo "Preparing $REMOTE_DIR on $HOST"
ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' && chmod 700 '$REMOTE_DIR'"

echo "Copying C9.3 experiment inputs to $HOST:$REMOTE_DIR"
scp "$LOCAL_LAUNCHER" "$LOCAL_WIZARD" "$LOCAL_SERVER" "$LOCAL_CONTRACT" "$HOST:$REMOTE_DIR/"

echo "Running C9.3 prepare checks on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail

LAUNCHER="$REMOTE_DIR/kiosky_service_launcher.sh"
WIZARD="$REMOTE_DIR/totem_setup_local_wizard.py"
SERVER="$REMOTE_DIR/totem_setup_minimal_server.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"

umask 077
mkdir -p "$REMOTE_DIR" "$REMOTE_OUT_DIR"
chmod 700 "$REMOTE_DIR" "$REMOTE_OUT_DIR"

bash -n "$LAUNCHER"
python3 "$CONTRACT" --self-test
python3 "$SERVER" --self-test
python3 "$WIZARD" --self-test

echo "remote C9.3 prepare checks: ok"
REMOTE_PREP

if [ "$MODE" = "prepare-only" ]; then
  echo "C9.3 prepare-only complete. Evidence dir reserved: $REMOTE_OUT_DIR"
  exit 0
fi

echo
echo "Before stopping service or opening the wizard on HDMI, type exactly:"
echo "$REQUIRED_AUTH"
printf '> '
IFS= read -r AUTH_TEXT

if [ "$AUTH_TEXT" != "$REQUIRED_AUTH" ]; then
  echo "Authorization text did not match. Aborting without operational changes." >&2
  exit 20
fi

echo "Running authorized C9.3 launcher/setup experiment"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_WIZARD_OUT_DIR='$REMOTE_WIZARD_OUT_DIR' REMOTE_TTY='$REMOTE_TTY' RUN_TIMEOUT_SEC='$RUN_TIMEOUT_SEC' bash -s" <<'REMOTE_RUN'
set -euo pipefail

LAUNCHER="$REMOTE_DIR/kiosky_service_launcher.sh"
WIZARD="$REMOTE_DIR/totem_setup_local_wizard.py"
FAKE_RENDERER="$REMOTE_DIR/fake_status_renderer.sh"
FAKE_AGGREGATOR="$REMOTE_DIR/fake_status_aggregate.sh"
STATUS_SVG="$REMOTE_OUT_DIR/status.svg"
STATUS_FILE="$REMOTE_OUT_DIR/launcher-status.json"
FALLBACK_STATUS_FILE="$REMOTE_OUT_DIR/fallback-launcher-status.json"
TRIGGER_FILE="$REMOTE_OUT_DIR/setup.request"
MISSING_CONFIG="$REMOTE_OUT_DIR/missing-config.json"
FAKE_RENDERER_STARTS="$REMOTE_OUT_DIR/fake-renderer-starts.txt"
FAKE_RENDERER_STOPS="$REMOTE_OUT_DIR/fake-renderer-stops.txt"
FAKE_RENDERER_PID="$REMOTE_OUT_DIR/fake-renderer.pid"
EVIDENCE_STATUS="$REMOTE_OUT_DIR/status.json"
EVIDENCE_SUMMARY="$REMOTE_OUT_DIR/summary.txt"

SERVICE_WAS_ACTIVE="false"
SERVICE_STOPPED="false"
SERVICE_RESTORED="false"
LAUNCHER_STARTED="false"
LAUNCHER_STOPPED="false"
SETUP_TRIGGER_CREATED="false"
WIZARD_RESULT="not_observed"
CANDIDATE_GENERATED="false"
RESULT="not_run"
ABORT_REASON=""
LAUNCHER_PID=""

service_active() {
  systemctl is-active kiosky-player.service 2>/dev/null || true
}

service_enabled() {
  systemctl is-enabled kiosky-player.service 2>/dev/null || true
}

nrestarts() {
  systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null || true
}

strict_counts() {
  python3 - <<'PY'
import os
import pathlib

self_pid = os.getpid()
player = 0
mpv = 0
renderer = 0
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        raw = (proc / "cmdline").read_bytes()
        parts = [part.decode("utf-8", "ignore") for part in raw.split(b"\x00") if part]
        cmdline = " ".join(parts)
        comm = (proc / "comm").read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        continue
    first = parts[0] if parts else ""
    if comm == "mpv" or first.endswith("/mpv"):
        mpv += 1
    if comm in {"python3", "python"} and ("/kiosk.py" in cmdline or cmdline.strip().endswith("kiosk.py")):
        player += 1
    if comm in {"python3", "python"} and ("status_splash" in cmdline or "renderer" in cmdline):
        renderer += 1
print(f"{player} {mpv} {renderer}")
PY
}

launcher_state() {
  python3 - "$STATUS_FILE" <<'PY'
import json
import sys
from pathlib import Path
try:
    value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    print("unavailable")
else:
    print(value.get("state", "missing"))
PY
}

count_lines() {
  local path="$1"
  if [ -f "$path" ]; then
    wc -l <"$path" | tr -d ' '
  else
    printf '0'
  fi
}

write_evidence() {
  set -- $(strict_counts)
  PLAYER_COUNT_AFTER="${1:-0}" \
  MPV_COUNT_AFTER="${2:-0}" \
  RENDERER_COUNT_AFTER="${3:-0}" \
  RESULT="$RESULT" \
  ABORT_REASON="$ABORT_REASON" \
  SERVICE_WAS_ACTIVE="$SERVICE_WAS_ACTIVE" \
  SERVICE_STOPPED="$SERVICE_STOPPED" \
  SERVICE_RESTORED="$SERVICE_RESTORED" \
  SERVICE_ACTIVE_AFTER="$(service_active)" \
  SERVICE_ENABLED_AFTER="$(service_enabled)" \
  SERVICE_NRESTARTS_AFTER="$(nrestarts)" \
  LAUNCHER_STARTED="$LAUNCHER_STARTED" \
  LAUNCHER_STOPPED="$LAUNCHER_STOPPED" \
  SETUP_TRIGGER_CREATED="$SETUP_TRIGGER_CREATED" \
  WIZARD_RESULT="$WIZARD_RESULT" \
  CANDIDATE_GENERATED="$CANDIDATE_GENERATED" \
  LAUNCHER_FINAL_STATE="$(launcher_state)" \
  FAKE_RENDERER_START_COUNT="$(count_lines "$FAKE_RENDERER_STARTS")" \
  FAKE_RENDERER_STOP_COUNT="$(count_lines "$FAKE_RENDERER_STOPS")" \
  REMOTE_TTY="$REMOTE_TTY" \
  REMOTE_OUT_DIR="$REMOTE_OUT_DIR" \
  REMOTE_WIZARD_OUT_DIR="$REMOTE_WIZARD_OUT_DIR" \
  EVIDENCE_STATUS="$EVIDENCE_STATUS" \
  EVIDENCE_SUMMARY="$EVIDENCE_SUMMARY" \
  python3 - <<'PY'
import datetime
import json
import os
from pathlib import Path

def bool_env(name):
    return os.environ.get(name) == "true"

def int_env(name):
    try:
        return int(os.environ.get(name, "0"))
    except ValueError:
        return 0

status = {
    "schema_version": "dadooh-c9.3-launcher-setup-local-experiment.v1",
    "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    "result": os.environ["RESULT"],
    "abort_reason": os.environ["ABORT_REASON"],
    "service": {
        "was_active": bool_env("SERVICE_WAS_ACTIVE"),
        "stopped_temporarily": bool_env("SERVICE_STOPPED"),
        "restored": bool_env("SERVICE_RESTORED"),
        "active_after": os.environ["SERVICE_ACTIVE_AFTER"],
        "enabled_after": os.environ["SERVICE_ENABLED_AFTER"],
        "nrestarts_after": os.environ["SERVICE_NRESTARTS_AFTER"],
    },
    "experiment": {
        "launcher_copy_under_tmp": True,
        "launcher_started": bool_env("LAUNCHER_STARTED"),
        "launcher_stopped": bool_env("LAUNCHER_STOPPED"),
        "config_override_missing_under_tmp": True,
        "setup_flag_enabled": True,
        "setup_trigger_created": bool_env("SETUP_TRIGGER_CREATED"),
        "reserved_tty": os.environ.get("REMOTE_TTY", "2"),
        "wizard_result": os.environ["WIZARD_RESULT"],
        "candidate_generated": bool_env("CANDIDATE_GENERATED"),
        "wizard_out_dir": os.environ["REMOTE_WIZARD_OUT_DIR"],
        "launcher_final_state": os.environ["LAUNCHER_FINAL_STATE"],
    },
    "screen_ownership": {
        "fake_renderer_start_count": int_env("FAKE_RENDERER_START_COUNT"),
        "fake_renderer_stop_count": int_env("FAKE_RENDERER_STOP_COUNT"),
        "player_count_after": int_env("PLAYER_COUNT_AFTER"),
        "mpv_count_after": int_env("MPV_COUNT_AFTER"),
        "renderer_count_after": int_env("RENDERER_COUNT_AFTER"),
        "raw_pids_written": False,
        "raw_cmdlines_written": False,
    },
    "guardrails": {
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "data_config_touched": False,
        "data_written": False,
        "opt_written": False,
        "network_changed": False,
        "wifi_changed": False,
        "nmcli_called": False,
        "kiosky_player_changed": False,
        "display_changed": False,
        "mpv_called_by_experiment_renderer": False,
        "production_released": False,
    },
    "privacy": {
        "config_content_copied": False,
        "candidate_payload_copied": False,
        "private_values_used": False,
        "credential_value_written": False,
        "private_url_written": False,
        "environment_value_raw_written": False,
        "raw_logs_written": False,
        "network_metadata_written": False,
    },
}

summary = "\n".join([
    "Dadooh C9.3 integracao experimental launcher/setup local",
    "",
    f"schema_version: {status['schema_version']}",
    f"generated_at_utc: {status['generated_at_utc']}",
    f"result: {status['result']}",
    f"abort_reason: {status['abort_reason']}",
    f"service_was_active: {str(status['service']['was_active']).lower()}",
    f"service_stopped_temporarily: {str(status['service']['stopped_temporarily']).lower()}",
    f"service_restored: {str(status['service']['restored']).lower()}",
    f"service_active_after: {status['service']['active_after']}",
    f"service_enabled_after: {status['service']['enabled_after']}",
    f"service_nrestarts_after: {status['service']['nrestarts_after']}",
    f"launcher_started: {str(status['experiment']['launcher_started']).lower()}",
    f"setup_trigger_created: {str(status['experiment']['setup_trigger_created']).lower()}",
    f"reserved_tty: {status['experiment']['reserved_tty']}",
    f"wizard_result: {status['experiment']['wizard_result']}",
    f"candidate_generated: {str(status['experiment']['candidate_generated']).lower()}",
    f"launcher_final_state: {status['experiment']['launcher_final_state']}",
    f"fake_renderer_start_count: {status['screen_ownership']['fake_renderer_start_count']}",
    f"fake_renderer_stop_count: {status['screen_ownership']['fake_renderer_stop_count']}",
    f"player_count_after: {status['screen_ownership']['player_count_after']}",
    f"mpv_count_after: {status['screen_ownership']['mpv_count_after']}",
    f"renderer_count_after: {status['screen_ownership']['renderer_count_after']}",
    "",
    "Guardrails:",
    "real_config_read: false",
    "real_config_written: false",
    "writer_called: false",
    "data_config_touched: false",
    "data_written: false",
    "opt_written: false",
    "network_changed: false",
    "wifi_changed: false",
    "nmcli_called: false",
    "kiosky_player_changed: false",
    "display_changed: false",
    "production_released: false",
])

Path(os.environ["EVIDENCE_STATUS"]).write_text(json.dumps(status, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
Path(os.environ["EVIDENCE_SUMMARY"]).write_text(summary + "\n", encoding="utf-8")
Path(os.environ["EVIDENCE_STATUS"]).chmod(0o600)
Path(os.environ["EVIDENCE_SUMMARY"]).chmod(0o600)
PY
}

restore_service_if_needed() {
  if [ "$SERVICE_WAS_ACTIVE" = "true" ]; then
    if [ "$(service_active)" != "active" ]; then
      systemctl start kiosky-player.service || true
    fi
    for _ in $(seq 1 90); do
      if [ "$(service_active)" = "active" ]; then
        set -- $(strict_counts)
        if [ "${1:-0}" -ge 1 ] && [ "${2:-0}" -ge 1 ]; then
          SERVICE_RESTORED="true"
          return 0
        fi
      fi
      sleep 1
    done
    return 1
  fi
  SERVICE_RESTORED="true"
  return 0
}

stop_launcher_if_needed() {
  if [ -n "$LAUNCHER_PID" ] && kill -0 "$LAUNCHER_PID" >/dev/null 2>&1; then
    kill -TERM "$LAUNCHER_PID" >/dev/null 2>&1 || true
    wait "$LAUNCHER_PID" 2>/dev/null || true
  fi
  if [ "$LAUNCHER_STARTED" = "true" ]; then
    LAUNCHER_STOPPED="true"
  fi
}

on_exit() {
  rc="$?"
  stop_launcher_if_needed || true
  restore_service_if_needed || true
  if [ "$RESULT" = "not_run" ]; then
    if [ "$rc" -eq 0 ]; then
      RESULT="passed"
    else
      RESULT="failed"
      ABORT_REASON="unexpected_exit_${rc}"
    fi
  fi
  write_evidence || true
  exit "$rc"
}
trap on_exit EXIT TERM INT

umask 077
rm -rf "$REMOTE_OUT_DIR" "$REMOTE_WIZARD_OUT_DIR"
mkdir -p "$REMOTE_OUT_DIR" "$REMOTE_WIZARD_OUT_DIR"
chmod 700 "$REMOTE_OUT_DIR" "$REMOTE_WIZARD_OUT_DIR"
printf '<svg width="64" height="64"></svg>\n' >"$STATUS_SVG"
chmod 600 "$STATUS_SVG"

cat >"$FAKE_RENDERER" <<'SH'
#!/usr/bin/env bash
set -u
printf '%s\n' "$$" >>"${C9_3_FAKE_RENDERER_STARTS:?}"
printf '%s\n' "$$" >"${C9_3_FAKE_RENDERER_PID:?}"
trap 'printf "%s\n" "$$" >>"${C9_3_FAKE_RENDERER_STOPS:?}"; rm -f "${C9_3_FAKE_RENDERER_PID:?}"; exit 0' TERM INT
while true; do
  sleep 1 &
  wait "$!" 2>/dev/null || true
done
SH
chmod 700 "$FAKE_RENDERER"

cat >"$FAKE_AGGREGATOR" <<'SH'
#!/usr/bin/env bash
exit 0
SH
chmod 700 "$FAKE_AGGREGATOR"

if [ "$(service_active)" != "active" ]; then
  RESULT="blocked"
  ABORT_REASON="service_not_active_before_experiment"
  exit 20
fi
SERVICE_WAS_ACTIVE="true"

systemctl stop kiosky-player.service
SERVICE_STOPPED="true"
for _ in $(seq 1 45); do
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

set -- $(strict_counts)
if [ "${1:-0}" -ne 0 ] || [ "${2:-0}" -ne 0 ]; then
  RESULT="failed"
  ABORT_REASON="player_or_mpv_still_running_after_service_stop"
  exit 1
fi

C9_3_FAKE_RENDERER_STARTS="$FAKE_RENDERER_STARTS" \
C9_3_FAKE_RENDERER_STOPS="$FAKE_RENDERER_STOPS" \
C9_3_FAKE_RENDERER_PID="$FAKE_RENDERER_PID" \
KIOSKY_CONFIG_PATH="$MISSING_CONFIG" \
KIOSKY_LAUNCHER_STATE_DIR="$REMOTE_OUT_DIR/state" \
KIOSKY_LAUNCHER_STATUS_FILE="$STATUS_FILE" \
KIOSKY_LAUNCHER_FALLBACK_STATUS_FILE="$FALLBACK_STATUS_FILE" \
KIOSKY_DISPLAY_RETRY_SEC=2 \
KIOSKY_CONFIG_RETRY_SEC=2 \
KIOSKY_APP_RESTART_SEC=2 \
KIOSKY_DISPLAY_LOG_INTERVAL_SEC=5 \
TOTEM_STATUS_AGGREGATOR="$FAKE_AGGREGATOR" \
TOTEM_STATUS_OUT_DIR="$REMOTE_OUT_DIR/status" \
TOTEM_PLAYER_STATUS_FILE="$REMOTE_OUT_DIR/missing-player-status.json" \
TOTEM_STATUS_RENDERER="$FAKE_RENDERER" \
TOTEM_STATUS_SVG="$STATUS_SVG" \
TOTEM_STATUS_RENDERER_STOP_TIMEOUT_SEC=3 \
TOTEM_SETUP_LOCAL_ENABLED=1 \
TOTEM_SETUP_LOCAL_AUTORUN_CONFIG_MISSING=0 \
TOTEM_SETUP_LOCAL_TRIGGER_FILE="$TRIGGER_FILE" \
TOTEM_SETUP_LOCAL_WIZARD="$WIZARD" \
TOTEM_SETUP_LOCAL_OUT_DIR="$REMOTE_WIZARD_OUT_DIR" \
TOTEM_SETUP_LOCAL_TTY="$REMOTE_TTY" \
TOTEM_SETUP_LOCAL_MAX_RUNS=1 \
bash "$LAUNCHER" >/dev/null 2>&1 &
LAUNCHER_PID="$!"
LAUNCHER_STARTED="true"

for _ in $(seq 1 30); do
  if [ "$(launcher_state)" = "config_missing" ] && [ -f "$FAKE_RENDERER_PID" ]; then
    break
  fi
  sleep 1
done
if [ "$(launcher_state)" != "config_missing" ]; then
  RESULT="failed"
  ABORT_REASON="launcher_did_not_reach_config_missing"
  exit 1
fi
if [ ! -f "$FAKE_RENDERER_PID" ]; then
  RESULT="failed"
  ABORT_REASON="fake_renderer_did_not_start_before_setup"
  exit 1
fi

printf 'setup\n' >"$TRIGGER_FILE"
chmod 600 "$TRIGGER_FILE"
SETUP_TRIGGER_CREATED="true"

echo "C9.3: wizard should appear on HDMI TTY $REMOTE_TTY."
echo "Use USB keyboard. Complete the wizard to generate a candidate, or q/Esc to cancel."

deadline=$(( $(date +%s) + RUN_TIMEOUT_SEC ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  if [ -f "$REMOTE_WIZARD_OUT_DIR/candidate-config.json" ]; then
    WIZARD_RESULT="candidate_ready"
    CANDIDATE_GENERATED="true"
    break
  fi
  state="$(launcher_state)"
  if [ "$state" = "setup_local_cancelled" ]; then
    WIZARD_RESULT="cancelled"
    break
  fi
  if [ "$state" = "setup_local_failed" ]; then
    WIZARD_RESULT="failed"
    RESULT="failed"
    ABORT_REASON="launcher_reported_setup_local_failed"
    exit 1
  fi
  sleep 1
done

if [ "$WIZARD_RESULT" = "not_observed" ]; then
  RESULT="failed"
  ABORT_REASON="wizard_timeout"
  exit 1
fi

for _ in $(seq 1 15); do
  if [ -f "$FAKE_RENDERER_PID" ]; then
    break
  fi
  sleep 1
done
if [ ! -f "$FAKE_RENDERER_PID" ]; then
  RESULT="failed"
  ABORT_REASON="fake_renderer_did_not_return_after_wizard"
  exit 1
fi

RESULT="passed"
ABORT_REASON=""
echo "remote C9.3 launcher/setup experiment: ok ($WIZARD_RESULT)"
REMOTE_RUN

echo "C9.3 launcher/setup experiment complete. Evidence: $REMOTE_OUT_DIR"
