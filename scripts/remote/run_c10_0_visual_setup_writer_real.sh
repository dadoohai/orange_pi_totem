#!/usr/bin/env bash
set -euo pipefail

HOST="root@192.168.1.147"
MODE="prepare-only"
REMOTE_TTY="2"
RUN_TIMEOUT_SEC="1800"
REMOTE_DIR="/tmp/dadooh-c10-0"
REMOTE_OUT_DIR="/tmp/dadooh-c10-setup-writer-run"
REMOTE_WIZARD_OUT_DIR="/tmp/dadooh-c10-visual-wizard"
REMOTE_HANDOFF_OUT_DIR="/tmp/dadooh-c10-setup-writer"
REMOTE_WRITER_OUT_DIR="/tmp/dadooh-c10-writer-real"
REMOTE_PRIVATE_VALUES="/tmp/dadooh-c10-private/private-values.json"
PRIVATE_SOURCE_MODE="tmp-file"
PROFILE_NAME="dadooh-c9-8-wifi-persistent"
CONFIRM_PHRASE="CONFIRMO ESCRITA REAL CONFIG C10.0"
SOURCE_CONFIRM_PHRASE="CONFIRMO USAR CONFIG ATIVA COMO FONTE PRIVADA C10.0"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_0_visual_setup_writer_real.sh [host] [--prepare-only|--preflight|--run-dry-run|--run-real-write-start] [--private-values /tmp/.../private-values.json] [--private-values-from-active-config] [--tty N] [--timeout-sec N]

Modes:
  --prepare-only
      Copy scripts to /tmp and run non-invasive self-tests.

  --preflight
      Inspect only sanitized readiness categories. Does not read/write real config.

  --run-dry-run
      Generate a scripted visual candidate, inject approved private values from
      a restricted /tmp file, and run C5.1 real-dry-run. Does not write /data.

  --run-real-write-start
      Requires exact human confirmation. Pauses kiosky-player.service, runs the
      visual wizard on HDMI/TTY, validates a private candidate, calls the guarded
      real writer, restores service, and records sanitized evidence.

  --private-values-from-active-config
      Requires an additional exact confirmation before use. Reads only the
      private endpoint/credential categories from the active config and writes a
      restricted temporary private-values file under /tmp without printing them.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only)
      MODE="prepare-only"
      ;;
    --preflight)
      MODE="preflight"
      ;;
    --run-dry-run)
      MODE="run-dry-run"
      ;;
    --run-real-write-start)
      MODE="run-real-write-start"
      ;;
    --private-values)
      shift
      REMOTE_PRIVATE_VALUES="${1:-}"
      ;;
    --private-values-from-active-config)
      PRIVATE_SOURCE_MODE="active-config"
      REMOTE_PRIVATE_VALUES="/tmp/dadooh-c10-private-from-active/private-values.json"
      ;;
    --tty)
      shift
      REMOTE_TTY="${1:-}"
      ;;
    --timeout-sec)
      shift
      RUN_TIMEOUT_SEC="${1:-}"
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
  prepare-only|preflight|run-dry-run|run-real-write-start)
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
LOCAL_SERVER="$BOARD_DIR/totem_setup_minimal_server.py"
LOCAL_CONTRACT="$BOARD_DIR/totem_config_contract_validate.py"
LOCAL_WIFI_ADAPTER="$BOARD_DIR/totem_wifi_nm_adapter.py"
LOCAL_STATUS_AGGREGATE="$BOARD_DIR/totem_status_aggregate.py"
LOCAL_STATUS_RENDER="$BOARD_DIR/totem_status_render_preview.py"
LOCAL_HANDOFF="$BOARD_DIR/totem_visual_setup_writer_handoff.py"
LOCAL_WRITER="$BOARD_DIR/totem_config_writer_real.py"

for path in \
  "$LOCAL_VISUAL_WIZARD" "$LOCAL_WIZARD" "$LOCAL_SERVER" "$LOCAL_CONTRACT" "$LOCAL_WIFI_ADAPTER" \
  "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_HANDOFF" "$LOCAL_WRITER"
do
  if [ ! -f "$path" ]; then
    echo "error: missing local input" >&2
    exit 1
  fi
done

echo "Preparing C10.0 visual setup writer workspace on $HOST"
ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR'"

echo "Copying C10.0 inputs to temporary board workspace"
scp \
  "$LOCAL_VISUAL_WIZARD" "$LOCAL_WIZARD" "$LOCAL_SERVER" "$LOCAL_CONTRACT" "$LOCAL_WIFI_ADAPTER" \
  "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_HANDOFF" "$LOCAL_WRITER" \
  "$HOST:$REMOTE_DIR/"

echo "Running C10.0 prepare checks on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail

VISUAL="$REMOTE_DIR/totem_setup_visual_wizard.py"
WIZARD="$REMOTE_DIR/totem_setup_local_wizard.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
WIFI_ADAPTER="$REMOTE_DIR/totem_wifi_nm_adapter.py"
HANDOFF="$REMOTE_DIR/totem_visual_setup_writer_handoff.py"
WRITER="$REMOTE_DIR/totem_config_writer_real.py"
SCRIPTED_OUT="$REMOTE_OUT_DIR/prepare-scripted-visual"

umask 077
rm -rf "$SCRIPTED_OUT"
mkdir -p "$REMOTE_DIR" "$REMOTE_OUT_DIR"
chmod 700 "$REMOTE_DIR" "$REMOTE_OUT_DIR"

python3 "$CONTRACT" --self-test
python3 "$WIFI_ADAPTER" --self-test --out-dir "$REMOTE_OUT_DIR/adapter-self-test"
python3 "$WIZARD" --self-test
python3 "$VISUAL" --self-test
python3 "$HANDOFF" --self-test
python3 "$WRITER" --self-test
python3 "$VISUAL" \
  --scripted \
  --environment-id ENV-C10-PREPARE-SMOKE \
  --rotation-key landscape \
  --network-step configured_wifi \
  --out-dir "$SCRIPTED_OUT" >/dev/null

echo "remote C10.0 prepare checks: ok"
REMOTE_PREP

if [ "$MODE" = "prepare-only" ]; then
  echo "C10.0 prepare-only complete. Evidence dir reserved: $REMOTE_OUT_DIR"
  exit 0
fi

run_remote_preflight() {
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_PRIVATE_VALUES='$REMOTE_PRIVATE_VALUES' PRIVATE_SOURCE_MODE='$PRIVATE_SOURCE_MODE' PROFILE_NAME='$PROFILE_NAME' bash -s" <<'REMOTE_PREFLIGHT'
set -euo pipefail

PREFLIGHT_OUT="$REMOTE_OUT_DIR/preflight"
PREFLIGHT_STATUS="$PREFLIGHT_OUT/preflight-status.json"
AGGREGATE="$REMOTE_DIR/totem_status_aggregate.py"

umask 077
rm -rf "$PREFLIGHT_OUT"
mkdir -p "$PREFLIGHT_OUT"
chmod 700 "$PREFLIGHT_OUT"

refresh_public_status() {
  if [ -f /opt/totem/bin/totem_status_aggregate.py ]; then
    PYTHONPATH=/opt/totem/bin python3 /opt/totem/bin/totem_status_aggregate.py >/dev/null 2>&1 || true
  else
    PYTHONPATH="$REMOTE_DIR" python3 "$AGGREGATE" >/dev/null 2>&1 || true
  fi
}

refresh_public_status

python3 - "$PREFLIGHT_STATUS" "$REMOTE_PRIVATE_VALUES" "$PROFILE_NAME" "$PRIVATE_SOURCE_MODE" <<'PY'
import json
import os
import pathlib
import stat
import subprocess
import sys

target = pathlib.Path(sys.argv[1])
private_values = pathlib.Path(sys.argv[2])
profile_name = sys.argv[3]
private_source_mode = sys.argv[4]

def run(args):
    try:
        completed = subprocess.run(args, check=False, capture_output=True, text=True, timeout=3)
    except Exception:
        return "unknown"
    value = (completed.stdout or "").strip().lower()
    return value if value else "unknown"

def count_processes():
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
    return counts

def json_value(path, key):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "unknown"
    if key == "public_state":
        value = data.get("public_state") or data.get("state")
    else:
        value = data.get(key)
    return value if isinstance(value, str) else "unknown"

def private_metadata(path):
    payload = {
        "exists": False,
        "under_tmp": str(path).startswith("/tmp/"),
        "is_symlink": False,
        "parent_mode_0700": False,
        "file_mode_0600": False,
        "ready": False,
        "contents_read": False,
        "raw_path_written": False,
    }
    try:
        payload["is_symlink"] = path.is_symlink()
        payload["exists"] = path.exists()
        if path.exists() and not path.is_symlink():
            payload["parent_mode_0700"] = stat.S_IMODE(path.parent.stat().st_mode) == 0o700
            payload["file_mode_0600"] = stat.S_IMODE(path.stat().st_mode) == 0o600
            payload["ready"] = payload["under_tmp"] and payload["parent_mode_0700"] and payload["file_mode_0600"]
    except OSError:
        payload["ready"] = False
    return payload

def dedicated_profile_present():
    try:
        completed = subprocess.run(
            ["nmcli", "-t", "-f", "connection.id", "connection", "show", profile_name],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return "unknown"
    return completed.returncode == 0

payload = {
    "schema_version": "dadooh-c10.0-preflight.v1",
    "mode": "preflight",
    "service_active": run(["systemctl", "is-active", "kiosky-player.service"]),
    "service_enabled": run(["systemctl", "is-enabled", "kiosky-player.service"]),
    "nrestarts": run(["systemctl", "show", "kiosky-player.service", "-p", "NRestarts", "--value"]),
    "public_state": json_value(pathlib.Path("/tmp/dadooh-status/status.json"), "public_state"),
    "playback": json_value(pathlib.Path("/tmp/kiosky-status.json"), "playback_state"),
    "process_counts": count_processes(),
    "dedicated_wifi_profile_present": dedicated_profile_present(),
    "private_values": private_metadata(private_values),
    "private_source_mode": private_source_mode,
    "active_config_source_requested": private_source_mode == "active-config",
    "active_config_contents_read": False,
    "active_config_values_published": False,
    "real_write_allowed_now": False,
    "real_write_requires_confirmation": True,
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "wifi_changed": False,
    "hotspot_created": False,
    "portal_created": False,
    "raw_logs_written": False,
}
payload["real_write_allowed_now"] = bool(payload["private_values"]["ready"])

tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
REMOTE_PREFLIGHT
}

if [ "$MODE" = "preflight" ]; then
  run_remote_preflight
  echo "C10.0 preflight complete. Evidence: $REMOTE_OUT_DIR/preflight"
  exit 0
fi

confirm_active_config_private_source_if_needed() {
  if [ "$PRIVATE_SOURCE_MODE" != "active-config" ]; then
    return 0
  fi
  echo
  echo "A fonte privada sera extraida localmente da config ativa, sem publicar valores."
  echo "Esta leitura e restrita a endpoint/credencial e so escreve um arquivo temporario sob /tmp."
  echo "Before reading active config as private source, type exactly:"
  echo "$SOURCE_CONFIRM_PHRASE"
  printf '> '
  IFS= read -r SOURCE_AUTH_TEXT
  if [ "$SOURCE_AUTH_TEXT" != "$SOURCE_CONFIRM_PHRASE" ]; then
    echo "Private source authorization text did not match. Aborting before reading active config." >&2
    exit 21
  fi
}

if [ "$MODE" = "run-dry-run" ]; then
  confirm_active_config_private_source_if_needed
  echo "Running C10.0 dry-run on the board"
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_PRIVATE_VALUES='$REMOTE_PRIVATE_VALUES' PRIVATE_SOURCE_MODE='$PRIVATE_SOURCE_MODE' REMOTE_WIZARD_OUT_DIR='$REMOTE_WIZARD_OUT_DIR' REMOTE_HANDOFF_OUT_DIR='$REMOTE_HANDOFF_OUT_DIR' bash -s" <<'REMOTE_DRY'
set -euo pipefail

VISUAL="$REMOTE_DIR/totem_setup_visual_wizard.py"
HANDOFF="$REMOTE_DIR/totem_visual_setup_writer_handoff.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
DRY_OUT="$REMOTE_OUT_DIR/dry-run"
DRY_STATUS="$DRY_OUT/dry-run-status.json"
WIZARD_OUT="$REMOTE_WIZARD_OUT_DIR-dry-run"
HANDOFF_OUT="$REMOTE_HANDOFF_OUT_DIR-dry-run"

umask 077
rm -rf "$DRY_OUT" "$WIZARD_OUT" "$HANDOFF_OUT"
mkdir -p "$DRY_OUT" "$WIZARD_OUT" "$HANDOFF_OUT"
chmod 700 "$DRY_OUT" "$WIZARD_OUT" "$HANDOFF_OUT"

if [ "$PRIVATE_SOURCE_MODE" = "active-config" ]; then
  python3 - "$REMOTE_PRIVATE_VALUES" <<'PY'
import json
import os
import pathlib
import stat
import sys
target = pathlib.Path(sys.argv[1])
active = pathlib.Path("/data/config/config.json")
target_parent = target.parent
if not str(target).startswith("/tmp/"):
    raise SystemExit("private_values_target_not_tmp")
if target.exists() or target.is_symlink():
    target.unlink()
target_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
if stat.S_IMODE(target_parent.stat().st_mode) != 0o700:
    target_parent.chmod(0o700)
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

python3 "$VISUAL" \
  --scripted \
  --environment-id ENV-C10-DRY-RUN-SMOKE \
  --rotation-key landscape \
  --network-step configured_wifi \
  --out-dir "$WIZARD_OUT" >/dev/null

python3 "$HANDOFF" \
  --source-candidate "$WIZARD_OUT/config.candidate.json" \
  --private-values "$REMOTE_PRIVATE_VALUES" \
  --out-dir "$HANDOFF_OUT" \
  --confirm-private-values-approved >/dev/null

python3 "$CONTRACT" \
  --candidate "$HANDOFF_OUT/config.candidate.private.json" \
  --real-dry-run \
  --out-dir "$DRY_OUT/validate-real" >/dev/null

rm -f "$HANDOFF_OUT/config.candidate.private.json"
if [ "$PRIVATE_SOURCE_MODE" = "active-config" ]; then
  rm -rf "$(dirname "$REMOTE_PRIVATE_VALUES")"
fi

python3 - "$DRY_STATUS" "$HANDOFF_OUT/setup-status.json" "$PRIVATE_SOURCE_MODE" <<'PY'
import json
import os
import pathlib
import stat
import sys

target = pathlib.Path(sys.argv[1])
handoff_status = pathlib.Path(sys.argv[2])
private_source_mode = sys.argv[3]
status = {}
try:
    status = json.loads(handoff_status.read_text(encoding="utf-8"))
except Exception:
    status = {}
payload = {
    "schema_version": "dadooh-c10.0-dry-run.v1",
    "mode": "run-dry-run",
    "result": "passed" if status.get("result") == "passed" else "unknown",
    "visual_candidate_generated": True,
    "private_candidate_real_dry_run_passed": bool(
        status.get("contract_validation", {}).get("private_real_dry_run", {}).get("valid")
    ),
    "private_candidate_removed": True,
    "private_source_mode": private_source_mode,
    "active_config_read_for_private_source": private_source_mode == "active-config",
    "active_config_values_published": False,
    "private_source_temp_removed": private_source_mode == "active-config",
    "writer_called": False,
    "real_config_read": False,
    "real_config_written": False,
    "service_changed": False,
    "wifi_changed": False,
    "private_values_public": False,
    "raw_logs_written": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
REMOTE_DRY
  echo "C10.0 dry-run complete. Evidence: $REMOTE_OUT_DIR/dry-run"
  exit 0
fi

confirm_active_config_private_source_if_needed

echo
echo "HDMI/tela e teclado local devem estar conectados. O player sera pausado temporariamente."
echo "A config real sera escrita somente pelo writer guardado, se o real-dry-run passar."
echo "Valores privados nao serao exibidos, copiados para evidencia ou impressos."
echo "Before pausing the player and writing real config, type exactly:"
echo "$CONFIRM_PHRASE"
printf '> '
IFS= read -r AUTH_TEXT
if [ "$AUTH_TEXT" != "$CONFIRM_PHRASE" ]; then
  echo "Authorization text did not match. Aborting before service pause." >&2
  exit 20
fi

echo "Running authorized C10.0 visual setup -> writer real -> start player"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_PRIVATE_VALUES='$REMOTE_PRIVATE_VALUES' PRIVATE_SOURCE_MODE='$PRIVATE_SOURCE_MODE' REMOTE_WIZARD_OUT_DIR='$REMOTE_WIZARD_OUT_DIR' REMOTE_HANDOFF_OUT_DIR='$REMOTE_HANDOFF_OUT_DIR' REMOTE_WRITER_OUT_DIR='$REMOTE_WRITER_OUT_DIR' REMOTE_TTY='$REMOTE_TTY' RUN_TIMEOUT_SEC='$RUN_TIMEOUT_SEC' PROFILE_NAME='$PROFILE_NAME' bash -s" <<'REMOTE_REAL'
set -euo pipefail

VISUAL="$REMOTE_DIR/totem_setup_visual_wizard.py"
HANDOFF="$REMOTE_DIR/totem_visual_setup_writer_handoff.py"
WRITER="$REMOTE_DIR/totem_config_writer_real.py"
AGGREGATE="$REMOTE_DIR/totem_status_aggregate.py"
RUN_OUT="$REMOTE_OUT_DIR/real-write-start"
FINAL_STATUS="$RUN_OUT/final-status.json"
WIZARD_OUT="$REMOTE_WIZARD_OUT_DIR"
HANDOFF_OUT="$REMOTE_HANDOFF_OUT_DIR"
WRITER_OUT="$REMOTE_WRITER_OUT_DIR"
ACTIVE_CONFIG="/data/config/config.json"
WIZARD_RC="not_run"
WRITER_RC="not_run"
HANDOFF_RC="not_run"
SERVICE_STOP_ATTEMPTED="false"
SERVICE_RESTORE_ATTEMPTED="false"
WRITER_CALLED="false"
REAL_CONFIG_WRITTEN="false"
PRIVATE_CANDIDATE_REMOVED="false"
SOURCE_CANDIDATE_REMOVED="false"
SCREENS_REMOVED="false"
ACTIVE_CONFIG_PRIVATE_SOURCE_USED="false"
PRIVATE_SOURCE_TEMP_REMOVED="false"
INITIAL_SERVICE_ACTIVE="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
INITIAL_SERVICE_ENABLED="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"

umask 077
rm -rf "$RUN_OUT" "$WIZARD_OUT" "$HANDOFF_OUT" "$WRITER_OUT"
mkdir -p "$RUN_OUT" "$WIZARD_OUT" "$HANDOFF_OUT" "$WRITER_OUT"
chmod 700 "$RUN_OUT" "$WIZARD_OUT" "$HANDOFF_OUT" "$WRITER_OUT"

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
    if key == "public_state":
        value = data.get("public_state") or data.get("state")
    else:
        value = data.get(key)
    print(value if isinstance(value, str) else "unknown")
except Exception:
    print("unknown")
PY
}

wait_player_running() {
  for _ in $(seq 1 60); do
    refresh_public_status
    state="$(read_json_value /tmp/dadooh-status/status.json public_state)"
    playback="$(read_json_value /tmp/kiosky-status.json playback_state)"
    set -- $(process_counts)
    if [ "$state" = "player_running" ] && [ "$playback" = "playing" ] && [ "${1:-0}" -ge 1 ] && [ "${2:-0}" -ge 1 ] && [ "${3:-0}" -eq 0 ] && [ "${4:-0}" -eq 0 ]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

validate_private_values_metadata() {
  python3 - "$REMOTE_PRIVATE_VALUES" <<'PY'
import pathlib
import stat
import sys
path = pathlib.Path(sys.argv[1])
if not str(path).startswith("/tmp/") or path.is_symlink() or not path.exists():
    raise SystemExit("private_values_not_ready")
if path.parent.is_symlink():
    raise SystemExit("private_values_parent_symlink")
if stat.S_IMODE(path.parent.stat().st_mode) != 0o700:
    raise SystemExit("private_values_parent_not_0700")
if stat.S_IMODE(path.stat().st_mode) != 0o600:
    raise SystemExit("private_values_file_not_0600")
PY
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
target_parent = target.parent
if not str(target).startswith("/tmp/"):
    raise SystemExit("private_values_target_not_tmp")
if target.exists() or target.is_symlink():
    target.unlink()
target_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
if stat.S_IMODE(target_parent.stat().st_mode) != 0o700:
    target_parent.chmod(0o700)
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

cleanup_private_artifacts() {
  if [ -f "$HANDOFF_OUT/config.candidate.private.json" ]; then
    rm -f "$HANDOFF_OUT/config.candidate.private.json" || true
  fi
  if [ ! -e "$HANDOFF_OUT/config.candidate.private.json" ]; then
    PRIVATE_CANDIDATE_REMOVED="true"
  fi
  if [ -f "$WIZARD_OUT/config.candidate.json" ]; then
    rm -f "$WIZARD_OUT/config.candidate.json" || true
  fi
  if [ ! -e "$WIZARD_OUT/config.candidate.json" ]; then
    SOURCE_CANDIDATE_REMOVED="true"
  fi
  if [ -d "$WIZARD_OUT/screens" ]; then
    rm -rf "$WIZARD_OUT/screens" || true
  fi
  if [ ! -d "$WIZARD_OUT/screens" ]; then
    SCREENS_REMOVED="true"
  fi
  if [ "$PRIVATE_SOURCE_MODE" = "active-config" ]; then
    rm -rf "$(dirname "$REMOTE_PRIVATE_VALUES")" || true
    if [ ! -e "$REMOTE_PRIVATE_VALUES" ]; then
      PRIVATE_SOURCE_TEMP_REMOVED="true"
    fi
  fi
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

write_final_status() {
  wait_player_running || true
  TOTEM_READ_OK="unknown"
  TOTEM_WRITE_BLOCKED="unknown"
  if id totem >/dev/null 2>&1 && [ -e "$ACTIVE_CONFIG" ]; then
    if runuser -u totem -- test -r "$ACTIVE_CONFIG"; then
      TOTEM_READ_OK="true"
    else
      TOTEM_READ_OK="false"
    fi
    if runuser -u totem -- test -w "$ACTIVE_CONFIG"; then
      TOTEM_WRITE_BLOCKED="false"
    else
      TOTEM_WRITE_BLOCKED="true"
    fi
  fi
  python3 - "$FINAL_STATUS" "$RUN_OUT" "$WIZARD_OUT" "$HANDOFF_OUT" "$WRITER_OUT" \
    "$WIZARD_RC" "$HANDOFF_RC" "$WRITER_RC" "$WRITER_CALLED" "$REAL_CONFIG_WRITTEN" \
    "$INITIAL_SERVICE_ACTIVE" "$INITIAL_SERVICE_ENABLED" "$SERVICE_STOP_ATTEMPTED" "$SERVICE_RESTORE_ATTEMPTED" \
    "$(systemctl is-active kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null || true)" \
    "$(read_json_value /tmp/dadooh-status/status.json public_state)" \
    "$(read_json_value /tmp/kiosky-status.json playback_state)" \
    "$TOTEM_READ_OK" "$TOTEM_WRITE_BLOCKED" "$PRIVATE_CANDIDATE_REMOVED" "$SOURCE_CANDIDATE_REMOVED" "$SCREENS_REMOVED" \
    "$PRIVATE_SOURCE_MODE" "$ACTIVE_CONFIG_PRIVATE_SOURCE_USED" "$PRIVATE_SOURCE_TEMP_REMOVED" <<'PY'
import grp
import json
import os
import pathlib
import pwd
import stat
import sys

target = pathlib.Path(sys.argv[1])
run_out = pathlib.Path(sys.argv[2])
wizard_out = pathlib.Path(sys.argv[3])
handoff_out = pathlib.Path(sys.argv[4])
writer_out = pathlib.Path(sys.argv[5])
wizard_rc = sys.argv[6]
handoff_rc = sys.argv[7]
writer_rc = sys.argv[8]
writer_called = sys.argv[9] == "true"
real_config_written = sys.argv[10] == "true"
initial_active = sys.argv[11] or "unknown"
initial_enabled = sys.argv[12] or "unknown"
service_stop_attempted = sys.argv[13] == "true"
service_restore_attempted = sys.argv[14] == "true"
service_active = sys.argv[15] or "unknown"
service_enabled = sys.argv[16] or "unknown"
nrestarts = sys.argv[17] or "unknown"
public_state = sys.argv[18] or "unknown"
playback = sys.argv[19] or "unknown"
totem_read_ok = sys.argv[20]
totem_write_blocked = sys.argv[21]
private_candidate_removed = sys.argv[22] == "true"
source_candidate_removed = sys.argv[23] == "true"
screens_removed = sys.argv[24] == "true"
private_source_mode = sys.argv[25]
active_config_private_source_used = sys.argv[26] == "true"
private_source_temp_removed = sys.argv[27] == "true"

def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

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

writer_status = load_json(writer_out / "writer-status.json")
handoff_status = load_json(handoff_out / "setup-status.json")
setup_status = load_json(wizard_out / "setup-status.json")
active_config = pathlib.Path("/data/config/config.json")
config_meta = {
    "exists": active_config.exists(),
    "mode": None,
    "owner_root": False,
    "group_totem": False,
    "content_copied": False,
}
if active_config.exists():
    st = active_config.stat()
    config_meta["mode"] = f"{stat.S_IMODE(st.st_mode):04o}"[-4:]
    try:
        config_meta["owner_root"] = pwd.getpwuid(st.st_uid).pw_name == "root"
    except KeyError:
        config_meta["owner_root"] = False
    try:
        config_meta["group_totem"] = grp.getgrgid(st.st_gid).gr_name == "totem"
    except KeyError:
        config_meta["group_totem"] = False

payload = {
    "schema_version": "dadooh-c10.0-visual-setup-writer-real-run.v1",
    "mode": "run-real-write-start",
    "wizard_rc": wizard_rc,
    "handoff_rc": handoff_rc,
    "writer_rc": writer_rc,
    "wizard_candidate_generated": bool(setup_status),
    "private_candidate_real_dry_run_passed": bool(
        handoff_status.get("contract_validation", {}).get("private_real_dry_run", {}).get("valid")
    ),
    "writer_called": writer_called,
    "writer_result": writer_status.get("result", "not_available"),
    "real_config_written": real_config_written,
    "backup_created": bool(writer_status.get("backup", {}).get("created", False)),
    "rollback_attempted": bool(writer_status.get("rollback", {}).get("attempted", False)),
    "rollback_restored": bool(writer_status.get("rollback", {}).get("restored", False)),
    "permissions_ok": bool(
        config_meta["exists"] and config_meta["mode"] == "0640" and config_meta["owner_root"] and config_meta["group_totem"]
    ),
    "active_config": config_meta,
    "totem_read_ok": totem_read_ok == "true",
    "totem_write_blocked": totem_write_blocked == "true",
    "private_candidate_removed": private_candidate_removed,
    "source_candidate_removed": source_candidate_removed,
    "screens_removed": screens_removed,
    "private_source_mode": private_source_mode,
    "active_config_read_for_private_source": active_config_private_source_used,
    "active_config_values_published": False,
    "private_source_temp_removed": private_source_temp_removed,
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
    "dedicated_wifi_profile_present": "unknown",
    "real_config_read": active_config_private_source_used,
    "real_config_read_authorized_for_private_source": active_config_private_source_used,
    "post_write_validation_read": bool(writer_status.get("guardrails", {}).get("post_write_active_config_read", False)),
    "wifi_changed": False,
    "hotspot_created": False,
    "portal_created": False,
    "kiosky_player_repo_changed": False,
    "credential_values_published": False,
    "private_endpoint_published": False,
    "environment_identifier_raw_published": False,
    "config_content_published": False,
    "backup_content_published": False,
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
  cleanup_private_artifacts || true
  restore_service || true
  write_final_status || true
  exit "$rc"
}
trap on_exit EXIT INT TERM HUP

prepare_private_values_from_active_config_if_requested
validate_private_values_metadata

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
set -e

if [ ! -f "$WIZARD_OUT/config.candidate.json" ]; then
  echo "candidate_not_generated" >&2
  exit 44
fi

set +e
python3 "$HANDOFF" \
  --source-candidate "$WIZARD_OUT/config.candidate.json" \
  --private-values "$REMOTE_PRIVATE_VALUES" \
  --out-dir "$HANDOFF_OUT" \
  --confirm-private-values-approved >/dev/null
HANDOFF_RC="$?"
set -e
if [ "$HANDOFF_RC" != "0" ]; then
  echo "private_handoff_failed" >&2
  exit 45
fi

if [ ! -f "$HANDOFF_OUT/config.candidate.private.json" ]; then
  echo "private_candidate_not_generated" >&2
  exit 46
fi

WRITER_CALLED="true"
set +e
python3 "$WRITER" \
  --candidate "$HANDOFF_OUT/config.candidate.private.json" \
  --dest /data/config/config.json \
  --backup-dir /data/config/backups \
  --out-dir "$WRITER_OUT" \
  --enable-real-write \
  --confirm-service-stopped \
  --confirm-human-approved-real-write >/dev/null
WRITER_RC="$?"
set -e
if [ "$WRITER_RC" != "0" ]; then
  echo "writer_failed" >&2
  exit 47
fi

REAL_CONFIG_WRITTEN="true"
cleanup_private_artifacts || true
restore_service || true
wait_player_running || true
write_final_status
exit 0
REMOTE_REAL

echo "C10.0 real-write-start run complete. Evidence: $REMOTE_OUT_DIR/real-write-start"
