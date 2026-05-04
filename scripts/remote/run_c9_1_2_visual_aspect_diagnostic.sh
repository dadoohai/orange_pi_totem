#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-root@192.168.18.115}"
MODE="read-only"

usage() {
  cat <<'USAGE'
Usage:
  run_c9_1_2_visual_aspect_diagnostic.sh [host] [--read-only|--stop-start]

Modes:
  --read-only
      Copy the C9.1.2 diagnostic to /tmp and collect phase-a-current only.
      Does not stop/start services.

  --stop-start
      Collect phase-b-before-stop, stop/start kiosky-player.service, wait for
      active player/MPV, then collect phase-b-after-start. Use only after the
      required explicit human authorization.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --read-only)
      MODE="read-only"
      ;;
    --stop-start)
      MODE="stop-start"
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

REMOTE_DIR="/tmp/dadooh-c9-1-2"
REMOTE_OUT_DIR="/tmp/dadooh-c9-1-2-visual-aspect"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_DIAG="$REPO_ROOT/scripts/board/totem_visual_aspect_diagnostic.py"

if [ ! -f "$LOCAL_DIAG" ]; then
  echo "error: missing $LOCAL_DIAG" >&2
  exit 1
fi

echo "Preparing $REMOTE_DIR on $HOST"
ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' && chmod 700 '$REMOTE_DIR'"

echo "Copying C9.1.2 visual aspect diagnostic to $HOST:$REMOTE_DIR"
scp "$LOCAL_DIAG" "$HOST:$REMOTE_DIR/"

echo "Running C9.1.2 visual aspect diagnostic on the board ($MODE)"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' MODE='$MODE' bash -s" <<'REMOTE_SH'
set -euo pipefail

DIAG="$REMOTE_DIR/totem_visual_aspect_diagnostic.py"
OPERATION_STATUS="$REMOTE_OUT_DIR/phase-b-operation.json"
OPERATION_SUMMARY="$REMOTE_OUT_DIR/phase-b-operation-summary.txt"
SERVICE_WAS_ACTIVE="false"
STOP_PERFORMED="false"
START_PERFORMED="false"
RESTORE_ATTEMPTED="false"
RESTORE_OK="false"
OPERATION_RESULT="not_run"
ABORT_REASON=""

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

write_operation_evidence() {
  mkdir -p "$REMOTE_OUT_DIR"
  chmod 700 "$REMOTE_OUT_DIR"
  OPERATION_RESULT="$OPERATION_RESULT" \
  ABORT_REASON="$ABORT_REASON" \
  SERVICE_WAS_ACTIVE="$SERVICE_WAS_ACTIVE" \
  STOP_PERFORMED="$STOP_PERFORMED" \
  START_PERFORMED="$START_PERFORMED" \
  RESTORE_ATTEMPTED="$RESTORE_ATTEMPTED" \
  RESTORE_OK="$RESTORE_OK" \
  SERVICE_ACTIVE_AFTER="$(service_active)" \
  SERVICE_ENABLED_AFTER="$(service_enabled)" \
  SERVICE_NRESTARTS_AFTER="$(nrestarts)" \
  OPERATION_STATUS="$OPERATION_STATUS" \
  OPERATION_SUMMARY="$OPERATION_SUMMARY" \
  python3 - <<'PY'
import datetime
import json
import os
import pathlib
import stat

status_path = pathlib.Path(os.environ["OPERATION_STATUS"])
summary_path = pathlib.Path(os.environ["OPERATION_SUMMARY"])
status = {
    "schema_version": "dadooh-c9.1.2-stop-start-operation.v1",
    "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    "result": os.environ["OPERATION_RESULT"],
    "abort_reason": os.environ["ABORT_REASON"],
    "service_was_active": os.environ["SERVICE_WAS_ACTIVE"] == "true",
    "stop_performed": os.environ["STOP_PERFORMED"] == "true",
    "start_performed": os.environ["START_PERFORMED"] == "true",
    "restore_attempted": os.environ["RESTORE_ATTEMPTED"] == "true",
    "restore_ok": os.environ["RESTORE_OK"] == "true",
    "service_active_after": os.environ["SERVICE_ACTIVE_AFTER"],
    "service_enabled_after": os.environ["SERVICE_ENABLED_AFTER"],
    "service_nrestarts_after": os.environ["SERVICE_NRESTARTS_AFTER"],
    "human_authorization_required": True,
    "guardrails": {
        "config_read": False,
        "config_written": False,
        "writer_called": False,
        "data_config_touched": False,
        "network_changed": False,
        "wifi_changed": False,
        "nmcli_called": False,
        "player_repo_touched": False,
    },
    "privacy": {
        "raw_logs_written": False,
        "process_cmdlines_written": False,
        "media_path_written": False,
        "private_values_written": False,
    },
}
summary = "\n".join([
    "Dadooh C9.1.2 stop/start controlado para diagnostico visual",
    "",
    f"schema_version: {status['schema_version']}",
    f"generated_at_utc: {status['generated_at_utc']}",
    f"result: {status['result']}",
    f"abort_reason: {status['abort_reason']}",
    f"service_was_active: {str(status['service_was_active']).lower()}",
    f"stop_performed: {str(status['stop_performed']).lower()}",
    f"start_performed: {str(status['start_performed']).lower()}",
    f"restore_ok: {str(status['restore_ok']).lower()}",
    f"service_active_after: {status['service_active_after']}",
    f"service_enabled_after: {status['service_enabled_after']}",
    f"service_nrestarts_after: {status['service_nrestarts_after']}",
    "",
    "Guardrails:",
    "config_read: false",
    "config_written: false",
    "writer_called: false",
    "data_config_touched: false",
    "network_changed: false",
    "wifi_changed: false",
    "nmcli_called: false",
    "player_repo_touched: false",
])
status_path.write_text(json.dumps(status, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
summary_path.write_text(summary + "\n", encoding="utf-8")
status_path.chmod(0o600)
summary_path.chmod(0o600)
if stat.S_IMODE(status_path.parent.stat().st_mode) != 0o700:
    status_path.parent.chmod(0o700)
PY
}

restore_if_needed() {
  if [ "$MODE" = "stop-start" ] && [ "$SERVICE_WAS_ACTIVE" = "true" ] && [ "$(service_active)" != "active" ]; then
    RESTORE_ATTEMPTED="true"
    systemctl start kiosky-player.service || true
    START_PERFORMED="true"
    for _ in $(seq 1 45); do
      if [ "$(service_active)" = "active" ]; then
        RESTORE_OK="true"
        return 0
      fi
      sleep 1
    done
    return 1
  fi
  RESTORE_OK="true"
}

on_exit() {
  rc="$?"
  if [ "$MODE" = "stop-start" ]; then
    restore_if_needed || true
    if [ "$OPERATION_RESULT" = "not_run" ] && [ "$rc" -eq 0 ]; then
      OPERATION_RESULT="passed"
    elif [ "$OPERATION_RESULT" = "not_run" ]; then
      OPERATION_RESULT="failed"
      ABORT_REASON="unexpected_exit_${rc}"
    fi
    write_operation_evidence || true
  fi
  exit "$rc"
}
trap on_exit EXIT

umask 077
mkdir -p "$REMOTE_DIR" "$REMOTE_OUT_DIR"
chmod 700 "$REMOTE_DIR" "$REMOTE_OUT_DIR"

python3 "$DIAG" --self-test

if [ "$MODE" = "read-only" ]; then
  python3 "$DIAG" --phase phase-a-current --out-dir "$REMOTE_OUT_DIR"
  echo "remote C9.1.2 phase A read-only: ok"
  exit 0
fi

if [ "$MODE" != "stop-start" ]; then
  echo "error: unknown mode $MODE" >&2
  exit 2
fi

if [ "$(service_active)" = "active" ]; then
  SERVICE_WAS_ACTIVE="true"
else
  OPERATION_RESULT="blocked"
  ABORT_REASON="service_not_active_before_stop_start"
  exit 20
fi

python3 "$DIAG" --phase phase-b-before-stop --out-dir "$REMOTE_OUT_DIR"

systemctl stop kiosky-player.service
STOP_PERFORMED="true"
for _ in $(seq 1 30); do
  if [ "$(service_active)" != "active" ]; then
    break
  fi
  sleep 1
done
if [ "$(service_active)" = "active" ]; then
  OPERATION_RESULT="failed"
  ABORT_REASON="service_did_not_stop"
  exit 1
fi

systemctl start kiosky-player.service
START_PERFORMED="true"
RESTORE_ATTEMPTED="true"
for _ in $(seq 1 60); do
  if [ "$(service_active)" = "active" ]; then
    set -- $(strict_counts)
    if [ "${1:-0}" -ge 1 ] && [ "${2:-0}" -ge 1 ]; then
      RESTORE_OK="true"
      break
    fi
  fi
  sleep 1
done
if [ "$RESTORE_OK" != "true" ]; then
  OPERATION_RESULT="failed"
  ABORT_REASON="service_or_player_did_not_restore"
  exit 1
fi

python3 "$DIAG" --phase phase-b-after-start --out-dir "$REMOTE_OUT_DIR"
OPERATION_RESULT="passed"
echo "remote C9.1.2 phase B stop/start: ok"
REMOTE_SH
