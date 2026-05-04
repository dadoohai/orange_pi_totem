#!/usr/bin/env bash
set -euo pipefail

HOST="root@192.168.18.115"
MODE="prepare-only"
REMOTE_TTY="2"
RUN_TIMEOUT_SEC="1800"
CONVERGE_SEC="180"
REMOTE_DIR="/tmp/dadooh-c10-2"
REMOTE_OUT_DIR="/tmp/dadooh-c10-2-config-missing-recovery"
REMOTE_WIZARD_OUT_DIR="/tmp/dadooh-c10-2-visual-wizard"
REMOTE_HANDOFF_OUT_DIR="/tmp/dadooh-c10-2-handoff"
REMOTE_WRITER_OUT_DIR="/tmp/dadooh-c10-2-writer"
REMOTE_PRIVATE_VALUES="/tmp/dadooh-c10-2-private/private-values.json"
PRIVATE_SOURCE_MODE="tmp-file"
PROFILE_NAME="dadooh-c9-8-wifi-persistent"
CONFIRM_PHRASE="CONFIRMO CONFIG_MISSING REAL C10.2 COM WRITER"
DRY_RUN_CONFIRM_PHRASE="CONFIRMO CONFIG_MISSING DRY RUN C10.2 COM PAUSA DO PLAYER"
SOURCE_CONFIRM_PHRASE="CONFIRMO USAR CONFIG ATIVA COMO FONTE PRIVADA C10.2"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_2_config_missing_visual_recovery.sh [host] [--prepare-only|--preflight|--run-config-missing-dry-run|--run-config-missing-real-write-start] [--private-values /tmp/.../private-values.json] [--private-values-from-active-config] [--tty N] [--timeout-sec N] [--converge-sec N]

Modes:
  --prepare-only
      Copy scripts to /tmp and run non-invasive self-tests.

  --preflight
      Collect a sanitized snapshot only. Does not read or write real config.

  --run-config-missing-dry-run
      Requires exact human confirmation. Pauses player, runs a temporary
      launcher copy with KIOSKY_CONFIG_PATH pointing to a missing /tmp file,
      opens the visual wizard, builds a private candidate, and validates C5.1
      real-dry-run. Does not write /data/config.

  --run-config-missing-real-write-start
      Requires exact human confirmation. Runs the same config_missing visual
      recovery flow, then calls the guarded writer to write /data/config/config.json
      and restores the player.

  --private-values-from-active-config
      Requires an additional exact confirmation before use. Reads only private
      endpoint/credential categories from the active config and writes a
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
    --run-config-missing-dry-run)
      MODE="run-config-missing-dry-run"
      ;;
    --run-config-missing-real-write-start)
      MODE="run-config-missing-real-write-start"
      ;;
    --private-values)
      shift
      REMOTE_PRIVATE_VALUES="${1:-}"
      ;;
    --private-values-from-active-config)
      PRIVATE_SOURCE_MODE="active-config"
      REMOTE_PRIVATE_VALUES="/tmp/dadooh-c10-2-private-from-active/private-values.json"
      ;;
    --tty)
      shift
      REMOTE_TTY="${1:-}"
      ;;
    --timeout-sec)
      shift
      RUN_TIMEOUT_SEC="${1:-}"
      ;;
    --converge-sec)
      shift
      CONVERGE_SEC="${1:-}"
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
  prepare-only|preflight|run-config-missing-dry-run|run-config-missing-real-write-start)
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

case "$CONVERGE_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --converge-sec must be a positive integer" >&2
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

LOCAL_LAUNCHER="$BOARD_DIR/kiosky_service_launcher.sh"
LOCAL_VISUAL_WIZARD="$BOARD_DIR/totem_setup_visual_wizard.py"
LOCAL_MINIMAL_SERVER="$BOARD_DIR/totem_setup_minimal_server.py"
LOCAL_CONTRACT="$BOARD_DIR/totem_config_contract_validate.py"
LOCAL_WIFI_ADAPTER="$BOARD_DIR/totem_wifi_nm_adapter.py"
LOCAL_STATUS_AGGREGATE="$BOARD_DIR/totem_status_aggregate.py"
LOCAL_STATUS_RENDER="$BOARD_DIR/totem_status_render_preview.py"
LOCAL_HANDOFF="$BOARD_DIR/totem_visual_setup_writer_handoff.py"
LOCAL_WRITER="$BOARD_DIR/totem_config_writer_real.py"

for path in \
  "$LOCAL_LAUNCHER" "$LOCAL_VISUAL_WIZARD" "$LOCAL_MINIMAL_SERVER" "$LOCAL_CONTRACT" \
  "$LOCAL_WIFI_ADAPTER" "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_HANDOFF" "$LOCAL_WRITER"
do
  if [ ! -f "$path" ]; then
    echo "error: missing local input" >&2
    exit 1
  fi
done

prepare_workspace() {
  echo "Preparing C10.2 config_missing recovery workspace on target board"
  ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR'"

  echo "Copying C10.2 inputs to temporary board workspace"
  scp \
    "$LOCAL_LAUNCHER" "$LOCAL_VISUAL_WIZARD" "$LOCAL_MINIMAL_SERVER" "$LOCAL_CONTRACT" \
    "$LOCAL_WIFI_ADAPTER" "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_HANDOFF" "$LOCAL_WRITER" \
    "$HOST:$REMOTE_DIR/" >/dev/null
}

run_remote_prepare_checks() {
  echo "Running C10.2 prepare checks on the board"
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail

LAUNCHER="$REMOTE_DIR/kiosky_service_launcher.sh"
VISUAL="$REMOTE_DIR/totem_setup_visual_wizard.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
WIFI_ADAPTER="$REMOTE_DIR/totem_wifi_nm_adapter.py"
HANDOFF="$REMOTE_DIR/totem_visual_setup_writer_handoff.py"
WRITER="$REMOTE_DIR/totem_config_writer_real.py"
SCRIPTED_OUT="$REMOTE_OUT_DIR/prepare-scripted-visual"

umask 077
rm -rf "$SCRIPTED_OUT"
mkdir -p "$REMOTE_DIR" "$REMOTE_OUT_DIR" "$SCRIPTED_OUT"
chmod 700 "$REMOTE_DIR" "$REMOTE_OUT_DIR" "$SCRIPTED_OUT"
chmod +x "$LAUNCHER" "$VISUAL" "$CONTRACT" "$WIFI_ADAPTER" "$HANDOFF" "$WRITER" 2>/dev/null || true

bash -n "$LAUNCHER"
python3 "$CONTRACT" --self-test
python3 "$WIFI_ADAPTER" --self-test --out-dir "$REMOTE_OUT_DIR/adapter-self-test" >/dev/null
python3 "$VISUAL" --self-test
python3 "$HANDOFF" --self-test
python3 "$WRITER" --self-test
python3 "$VISUAL" \
  --scripted \
  --environment-id ENV-C10-2-PREPARE-SMOKE \
  --rotation-key landscape \
  --network-step configured_wifi \
  --out-dir "$SCRIPTED_OUT" >/dev/null

echo "remote C10.2 prepare checks: ok"
REMOTE_PREP
}

collect_snapshot() {
  local phase="$1"
  local wait_convergence="$2"
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' PROFILE_NAME='$PROFILE_NAME' PHASE='$phase' WAIT_CONVERGENCE='$wait_convergence' CONVERGE_SEC='$CONVERGE_SEC' bash -s" <<'REMOTE_SNAPSHOT'
set -euo pipefail

SNAPSHOT_OUT="$REMOTE_OUT_DIR/$PHASE"
SNAPSHOT_STATUS="$SNAPSHOT_OUT/status.json"
AGGREGATE="$REMOTE_DIR/totem_status_aggregate.py"

umask 077
rm -rf "$SNAPSHOT_OUT"
mkdir -p "$SNAPSHOT_OUT"
chmod 700 "$SNAPSHOT_OUT"

python3 - "$SNAPSHOT_STATUS" "$PHASE" "$REMOTE_DIR" "$AGGREGATE" "$PROFILE_NAME" "$WAIT_CONVERGENCE" "$CONVERGE_SEC" <<'PY'
import grp
import json
import os
import pathlib
import pwd
import stat
import subprocess
import sys
import time
from typing import Any

target = pathlib.Path(sys.argv[1])
phase = sys.argv[2]
remote_dir = pathlib.Path(sys.argv[3])
aggregate = pathlib.Path(sys.argv[4])
profile_name = sys.argv[5]
wait_convergence = sys.argv[6] == "true"
converge_sec = int(sys.argv[7])

ACTIVE_CONFIG = pathlib.Path("/data/config/config.json")
PUBLIC_STATUS = pathlib.Path("/tmp/dadooh-status/status.json")
PLAYER_STATUS = pathlib.Path("/tmp/kiosky-status.json")


def run(args: list[str], timeout: int = 3) -> tuple[int | None, str]:
    try:
        completed = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None, "unknown"
    return completed.returncode, (completed.stdout or "").strip()


def run_shell(command: str, timeout: int = 6) -> tuple[int | None, str]:
    try:
        completed = subprocess.run(["bash", "-lc", command], check=False, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None, "unknown"
    return completed.returncode, (completed.stdout or "").strip()


def refresh_public_status() -> None:
    opt_aggregate = pathlib.Path("/opt/totem/bin/totem_status_aggregate.py")
    if opt_aggregate.exists():
        subprocess.run(["python3", str(opt_aggregate)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        return
    if aggregate.exists():
        env = dict(os.environ)
        env["PYTHONPATH"] = str(remote_dir)
        subprocess.run(["python3", str(aggregate)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, env=env)


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def json_string(path: pathlib.Path, key: str) -> str:
    data = load_json(path)
    if key == "public_state":
        value = data.get("public_state") or data.get("state")
    else:
        value = data.get(key)
    return value if isinstance(value, str) and value else "unknown"


def process_counts() -> dict[str, int]:
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


def config_metadata() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "present": ACTIVE_CONFIG.exists(),
        "mode_0640": False,
        "owner_root": False,
        "group_totem": False,
        "permissions_ok": False,
        "content_read": False,
        "content_published": False,
    }
    if not ACTIVE_CONFIG.exists():
        return payload
    try:
        st = ACTIVE_CONFIG.stat()
    except OSError:
        return payload
    payload["mode_0640"] = stat.S_IMODE(st.st_mode) == 0o640
    try:
        payload["owner_root"] = pwd.getpwuid(st.st_uid).pw_name == "root"
    except KeyError:
        payload["owner_root"] = False
    try:
        payload["group_totem"] = grp.getgrgid(st.st_gid).gr_name == "totem"
    except KeyError:
        payload["group_totem"] = False
    payload["permissions_ok"] = bool(payload["mode_0640"] and payload["owner_root"] and payload["group_totem"])
    return payload


def totem_access() -> dict[str, str | bool]:
    payload: dict[str, str | bool] = {"read_ok": "unknown", "write_blocked": "unknown", "content_read": False}
    rc, _ = run(["id", "totem"])
    if rc != 0 or not ACTIVE_CONFIG.exists():
        return payload
    read_rc, _ = run(["runuser", "-u", "totem", "--", "test", "-r", str(ACTIVE_CONFIG)])
    write_rc, _ = run(["runuser", "-u", "totem", "--", "test", "-w", str(ACTIVE_CONFIG)])
    payload["read_ok"] = read_rc == 0
    payload["write_blocked"] = write_rc != 0
    return payload


def dedicated_wifi_profile_present() -> bool | str:
    rc, _ = run(["nmcli", "-t", "-f", "connection.id", "connection", "show", profile_name])
    if rc is None:
        return "unknown"
    return rc == 0


def int_shell(command: str) -> int | str:
    rc, output = run_shell(command)
    if rc is None:
        return "unknown"
    try:
        return int(output.strip())
    except ValueError:
        return "unknown"


def current_status() -> tuple[str, str, dict[str, int]]:
    refresh_public_status()
    return (
        json_string(PUBLIC_STATUS, "public_state"),
        json_string(PLAYER_STATUS, "playback_state"),
        process_counts(),
    )


converged = False
converged_after_sec: int | None = None
if wait_convergence:
    start = time.monotonic()
    deadline = start + converge_sec
    while time.monotonic() <= deadline:
        state, playback, counts = current_status()
        if (
            state == "player_running"
            and playback == "playing"
            and counts.get("player", 0) >= 1
            and counts.get("mpv", 0) >= 1
            and counts.get("renderer", 0) == 0
            and counts.get("setup", 0) == 0
        ):
            converged = True
            converged_after_sec = int(time.monotonic() - start)
            break
        time.sleep(2)
else:
    current_status()

public_state, playback, counts = current_status()
failed_count = int_shell("systemctl --failed --no-legend --plain 2>/dev/null | sed '/^$/d' | wc -l")
critical_count = int_shell(
    "journalctl -k -b --no-pager --output=short-iso 2>/dev/null | "
    "grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset' | wc -l"
)

payload = {
    "schema_version": "dadooh-c10.2-config-missing-snapshot.v1",
    "phase": phase,
    "service_active": run(["systemctl", "is-active", "kiosky-player.service"])[1] or "unknown",
    "service_enabled": run(["systemctl", "is-enabled", "kiosky-player.service"])[1] or "unknown",
    "nrestarts": run(["systemctl", "show", "kiosky-player.service", "-p", "NRestarts", "--value"])[1] or "unknown",
    "public_state": public_state,
    "playback": playback,
    "process_counts": counts,
    "dedicated_wifi_profile_present": dedicated_wifi_profile_present(),
    "active_config": config_metadata(),
    "totem_access": totem_access(),
    "systemctl_failed_count": failed_count,
    "systemctl_failed_relevant_clear": failed_count == 0 if isinstance(failed_count, int) else "unknown",
    "kernel_critical_filter_count": critical_count,
    "kernel_critical_filter_clear": critical_count == 0 if isinstance(critical_count, int) else "unknown",
    "convergence_waited": wait_convergence,
    "converged": converged if wait_convergence else "not_requested",
    "converged_after_sec": converged_after_sec,
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "wifi_changed": False,
    "networkmanager_changed": False,
    "hotspot_created": False,
    "portal_created": False,
    "root_read_only_enabled": False,
    "power_cut_tested": False,
    "raw_logs_written": False,
    "config_content_published": False,
    "backup_content_published": False,
    "private_values_published": False,
    "network_identifiers_published": False,
    "environment_identifier_raw_published": False,
}

tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
REMOTE_SNAPSHOT
}

confirm_active_config_private_source_if_needed() {
  if [ "$PRIVATE_SOURCE_MODE" != "active-config" ]; then
    return 0
  fi
  echo
  echo "A fonte privada sera extraida localmente da config ativa, sem publicar valores."
  echo "Esta leitura e restrita a endpoint/credencial e grava apenas um arquivo temporario sob /tmp."
  echo "Before reading active config as private source, type exactly:"
  echo "$SOURCE_CONFIRM_PHRASE"
  printf '> '
  IFS= read -r SOURCE_AUTH_TEXT
  if [ "$SOURCE_AUTH_TEXT" != "$SOURCE_CONFIRM_PHRASE" ]; then
    echo "Private source authorization text did not match. Aborting before reading active config." >&2
    exit 21
  fi
}

run_config_missing_flow() {
  local write_mode="$1"
  local confirm_phrase="$2"

  confirm_active_config_private_source_if_needed

  echo
  echo "O player sera pausado temporariamente para executar o fluxo config_missing visual."
  echo "O override de config_missing sera apenas um caminho ausente sob /tmp no launcher temporario."
  echo "Nao altera Wi-Fi/NetworkManager, nao habilita read-only e nao executa reboot."
  echo "Before continuing, type exactly:"
  echo "$confirm_phrase"
  printf '> '
  IFS= read -r AUTH_TEXT
  if [ "$AUTH_TEXT" != "$confirm_phrase" ]; then
    echo "Authorization text did not match. Aborting before service pause." >&2
    exit 20
  fi

  echo "Running authorized C10.2 config_missing visual recovery flow"
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_WIZARD_OUT_DIR='$REMOTE_WIZARD_OUT_DIR' REMOTE_HANDOFF_OUT_DIR='$REMOTE_HANDOFF_OUT_DIR' REMOTE_WRITER_OUT_DIR='$REMOTE_WRITER_OUT_DIR' REMOTE_PRIVATE_VALUES='$REMOTE_PRIVATE_VALUES' PRIVATE_SOURCE_MODE='$PRIVATE_SOURCE_MODE' REMOTE_TTY='$REMOTE_TTY' RUN_TIMEOUT_SEC='$RUN_TIMEOUT_SEC' CONVERGE_SEC='$CONVERGE_SEC' PROFILE_NAME='$PROFILE_NAME' WRITE_MODE='$write_mode' bash -s" <<'REMOTE_RUN'
set -euo pipefail

LAUNCHER="$REMOTE_DIR/kiosky_service_launcher.sh"
VISUAL="$REMOTE_DIR/totem_setup_visual_wizard.py"
HANDOFF="$REMOTE_DIR/totem_visual_setup_writer_handoff.py"
WRITER="$REMOTE_DIR/totem_config_writer_real.py"
AGGREGATE="$REMOTE_DIR/totem_status_aggregate.py"
RUN_OUT="$REMOTE_OUT_DIR/$WRITE_MODE"
FINAL_STATUS="$RUN_OUT/final-status.json"
WIZARD_OUT="$REMOTE_WIZARD_OUT_DIR-$WRITE_MODE"
HANDOFF_OUT="$REMOTE_HANDOFF_OUT_DIR-$WRITE_MODE"
WRITER_OUT="$REMOTE_WRITER_OUT_DIR-$WRITE_MODE"
ACTIVE_CONFIG="/data/config/config.json"
MISSING_CONFIG="$RUN_OUT/missing-config.json"
LAUNCHER_STATUS="$RUN_OUT/launcher-status.json"
LAUNCHER_FALLBACK_STATUS="$RUN_OUT/fallback-launcher-status.json"
LAUNCHER_PUBLIC_STATUS="$RUN_OUT/public-status"
LAUNCHER_PLAYER_STATUS="$RUN_OUT/player-status.json"
LAUNCHER_PID=""
LAUNCHER_RC="not_run"
HANDOFF_RC="not_run"
WRITER_RC="not_run"
WRITER_CALLED="false"
REAL_CONFIG_WRITTEN="false"
SERVICE_STOP_ATTEMPTED="false"
SERVICE_RESTORE_ATTEMPTED="false"
OVERRIDE_APPLIED="false"
OVERRIDE_REMOVED="false"
VISUAL_CANDIDATE_GENERATED="false"
PRIVATE_CANDIDATE_REMOVED="false"
SOURCE_CANDIDATE_REMOVED="false"
SCREENS_REMOVED="false"
PRIVATE_SOURCE_TEMP_REMOVED="false"
ACTIVE_CONFIG_PRIVATE_SOURCE_USED="false"
INITIAL_SERVICE_ACTIVE="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
INITIAL_SERVICE_ENABLED="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"

umask 077
rm -rf "$RUN_OUT" "$WIZARD_OUT" "$HANDOFF_OUT" "$WRITER_OUT"
mkdir -p "$RUN_OUT" "$WIZARD_OUT" "$HANDOFF_OUT" "$WRITER_OUT" "$LAUNCHER_PUBLIC_STATUS"
chmod 700 "$RUN_OUT" "$WIZARD_OUT" "$HANDOFF_OUT" "$WRITER_OUT" "$LAUNCHER_PUBLIC_STATUS"
chmod +x "$LAUNCHER" "$VISUAL" "$HANDOFF" "$WRITER" 2>/dev/null || true

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
  local deadline=$(( $(date +%s) + CONVERGE_SEC ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
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
if target.exists() or target.is_symlink():
    target.unlink()
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

stop_launcher() {
  if [ -n "$LAUNCHER_PID" ] && kill -0 "$LAUNCHER_PID" >/dev/null 2>&1; then
    kill -TERM "$LAUNCHER_PID" >/dev/null 2>&1 || true
    for _ in $(seq 1 15); do
      if ! kill -0 "$LAUNCHER_PID" >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
    if kill -0 "$LAUNCHER_PID" >/dev/null 2>&1; then
      kill -KILL "$LAUNCHER_PID" >/dev/null 2>&1 || true
    fi
    wait "$LAUNCHER_PID" 2>/dev/null || true
  fi
  LAUNCHER_PID=""
  OVERRIDE_REMOVED="true"
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
    "$WRITE_MODE" "$LAUNCHER_RC" "$HANDOFF_RC" "$WRITER_RC" "$WRITER_CALLED" "$REAL_CONFIG_WRITTEN" \
    "$INITIAL_SERVICE_ACTIVE" "$INITIAL_SERVICE_ENABLED" "$SERVICE_STOP_ATTEMPTED" "$SERVICE_RESTORE_ATTEMPTED" \
    "$OVERRIDE_APPLIED" "$OVERRIDE_REMOVED" "$VISUAL_CANDIDATE_GENERATED" "$PRIVATE_CANDIDATE_REMOVED" \
    "$SOURCE_CANDIDATE_REMOVED" "$SCREENS_REMOVED" "$PRIVATE_SOURCE_MODE" "$ACTIVE_CONFIG_PRIVATE_SOURCE_USED" \
    "$PRIVATE_SOURCE_TEMP_REMOVED" "$TOTEM_READ_OK" "$TOTEM_WRITE_BLOCKED" \
    "$(systemctl is-active kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null || true)" \
    "$(read_json_value /tmp/dadooh-status/status.json public_state)" \
    "$(read_json_value /tmp/kiosky-status.json playback_state)" \
    "$(systemctl --failed --no-legend --plain 2>/dev/null | sed '/^$/d' | wc -l | tr -d ' ')" \
    "$(journalctl -k -b --no-pager --output=short-iso 2>/dev/null | grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset' | wc -l | tr -d ' ')" \
    "$PROFILE_NAME" <<'PY'
import grp
import json
import os
import pathlib
import pwd
import stat
import subprocess
import sys

target = pathlib.Path(sys.argv[1])
run_out = pathlib.Path(sys.argv[2])
wizard_out = pathlib.Path(sys.argv[3])
handoff_out = pathlib.Path(sys.argv[4])
writer_out = pathlib.Path(sys.argv[5])
write_mode = sys.argv[6]
launcher_rc = sys.argv[7]
handoff_rc = sys.argv[8]
writer_rc = sys.argv[9]
writer_called = sys.argv[10] == "true"
real_config_written = sys.argv[11] == "true"
initial_active = sys.argv[12] or "unknown"
initial_enabled = sys.argv[13] or "unknown"
service_stop_attempted = sys.argv[14] == "true"
service_restore_attempted = sys.argv[15] == "true"
override_applied = sys.argv[16] == "true"
override_removed = sys.argv[17] == "true"
visual_candidate_generated = sys.argv[18] == "true"
private_candidate_removed = sys.argv[19] == "true"
source_candidate_removed = sys.argv[20] == "true"
screens_removed = sys.argv[21] == "true"
private_source_mode = sys.argv[22]
active_config_private_source_used = sys.argv[23] == "true"
private_source_temp_removed = sys.argv[24] == "true"
totem_read_ok = sys.argv[25]
totem_write_blocked = sys.argv[26]
service_active = sys.argv[27] or "unknown"
service_enabled = sys.argv[28] or "unknown"
nrestarts = sys.argv[29] or "unknown"
public_state = sys.argv[30] or "unknown"
playback = sys.argv[31] or "unknown"
failed_count_raw = sys.argv[32] or "unknown"
kernel_count_raw = sys.argv[33] or "unknown"
profile_name = sys.argv[34]


def load_json(path: pathlib.Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def count_processes() -> dict[str, int]:
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


def int_or_unknown(value: str):
    try:
        return int(value)
    except ValueError:
        return "unknown"


def dedicated_wifi_profile_present() -> bool | str:
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


active_config = pathlib.Path("/data/config/config.json")
config_meta = {
    "present": active_config.exists(),
    "mode_0640": False,
    "owner_root": False,
    "group_totem": False,
    "permissions_ok": False,
    "content_read": False,
    "content_published": False,
}
if active_config.exists():
    st = active_config.stat()
    config_meta["mode_0640"] = stat.S_IMODE(st.st_mode) == 0o640
    try:
        config_meta["owner_root"] = pwd.getpwuid(st.st_uid).pw_name == "root"
    except KeyError:
        config_meta["owner_root"] = False
    try:
        config_meta["group_totem"] = grp.getgrgid(st.st_gid).gr_name == "totem"
    except KeyError:
        config_meta["group_totem"] = False
    config_meta["permissions_ok"] = bool(config_meta["mode_0640"] and config_meta["owner_root"] and config_meta["group_totem"])

writer_status = load_json(writer_out / "writer-status.json")
handoff_status = load_json(handoff_out / "setup-status.json")
setup_status = load_json(wizard_out / "setup-status.json")
failed_count = int_or_unknown(failed_count_raw)
kernel_count = int_or_unknown(kernel_count_raw)

payload = {
    "schema_version": "dadooh-c10.2-config-missing-visual-recovery-run.v1",
    "mode": write_mode,
    "config_missing_method": "temporary_launcher_config_path_under_tmp_missing_file",
    "override_applied": override_applied,
    "override_removed": override_removed,
    "launcher_rc": launcher_rc,
    "handoff_rc": handoff_rc,
    "writer_rc": writer_rc,
    "visual_candidate_generated": visual_candidate_generated or bool(setup_status),
    "private_candidate_real_dry_run_passed": bool(
        handoff_status.get("contract_validation", {}).get("private_real_dry_run", {}).get("valid")
    ),
    "writer_called": writer_called,
    "writer_result": writer_status.get("result", "not_called" if not writer_called else "not_available"),
    "real_config_written": real_config_written,
    "backup_created": bool(writer_status.get("backup", {}).get("created", False)),
    "permissions_ok": bool(config_meta["permissions_ok"]),
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
    "process_counts": count_processes(),
    "dedicated_wifi_profile_present": dedicated_wifi_profile_present(),
    "systemctl_failed_count": failed_count,
    "systemctl_failed_relevant_clear": failed_count == 0 if isinstance(failed_count, int) else "unknown",
    "kernel_critical_filter_count": kernel_count,
    "kernel_critical_filter_clear": kernel_count == 0 if isinstance(kernel_count, int) else "unknown",
    "real_config_read": active_config_private_source_used,
    "real_config_read_authorized_for_private_source": active_config_private_source_used,
    "post_write_validation_read": bool(writer_status.get("guardrails", {}).get("post_write_active_config_read", False)),
    "wifi_changed": False,
    "networkmanager_changed": False,
    "hotspot_created": False,
    "portal_created": False,
    "kiosky_player_repo_changed": False,
    "root_read_only_enabled": False,
    "power_cut_tested": False,
    "reboot_called": False,
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
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

on_exit() {
  rc="$?"
  trap - EXIT INT TERM HUP
  stop_launcher || true
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
  for _ in $(seq 1 45); do
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

OVERRIDE_APPLIED="true"
rm -f "$MISSING_CONFIG" "$LAUNCHER_PLAYER_STATUS" 2>/dev/null || true
PYTHONPATH="$REMOTE_DIR" \
KIOSKY_CONFIG_PATH="$MISSING_CONFIG" \
KIOSKY_CONFIG_RETRY_SEC=2 \
KIOSKY_APP_RESTART_SEC=2 \
KIOSKY_LAUNCHER_STATE_DIR="$RUN_OUT/state" \
KIOSKY_LAUNCHER_STATUS_FILE="$LAUNCHER_STATUS" \
KIOSKY_LAUNCHER_FALLBACK_STATUS_FILE="$LAUNCHER_FALLBACK_STATUS" \
TOTEM_PLAYER_STATUS_FILE="$LAUNCHER_PLAYER_STATUS" \
TOTEM_STATUS_AGGREGATOR="$AGGREGATE" \
TOTEM_STATUS_OUT_DIR="$LAUNCHER_PUBLIC_STATUS" \
TOTEM_STATUS_RENDERER=/bin/true \
TOTEM_SETUP_LOCAL_ENABLED=1 \
TOTEM_SETUP_LOCAL_AUTORUN_CONFIG_MISSING=1 \
TOTEM_SETUP_LOCAL_WIZARD="$VISUAL" \
TOTEM_SETUP_LOCAL_OUT_DIR="$WIZARD_OUT" \
TOTEM_SETUP_LOCAL_CANDIDATE_FILE=config.candidate.json \
TOTEM_SETUP_LOCAL_TTY="$REMOTE_TTY" \
TOTEM_SETUP_LOCAL_MAX_RUNS=1 \
bash "$LAUNCHER" >"$RUN_OUT/launcher.stdout" 2>"$RUN_OUT/launcher.stderr" &
LAUNCHER_PID="$!"

deadline=$(( $(date +%s) + RUN_TIMEOUT_SEC ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  if [ -f "$WIZARD_OUT/config.candidate.json" ]; then
    VISUAL_CANDIDATE_GENERATED="true"
    break
  fi
  if [ -f "$WIZARD_OUT/setup-cancelled.json" ]; then
    echo "wizard_cancelled" >&2
    exit 43
  fi
  if [ -f "$WIZARD_OUT/setup-failed.json" ]; then
    echo "wizard_failed" >&2
    exit 44
  fi
  if ! kill -0 "$LAUNCHER_PID" >/dev/null 2>&1; then
    wait "$LAUNCHER_PID" || LAUNCHER_RC="$?"
    LAUNCHER_PID=""
    echo "launcher_exited_before_candidate" >&2
    exit 45
  fi
  sleep 2
done

if [ "$VISUAL_CANDIDATE_GENERATED" != "true" ]; then
  echo "candidate_not_generated" >&2
  exit 46
fi

stop_launcher || true
LAUNCHER_RC="0"

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
  exit 47
fi

if [ ! -f "$HANDOFF_OUT/config.candidate.private.json" ]; then
  echo "private_candidate_not_generated" >&2
  exit 48
fi

if [ "$WRITE_MODE" = "run-config-missing-real-write-start" ]; then
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
    exit 49
  fi
  REAL_CONFIG_WRITTEN="true"
else
  WRITER_RC="not_run"
fi

cleanup_private_artifacts || true
restore_service || true
wait_player_running || true
write_final_status
exit 0
REMOTE_RUN
}

prepare_workspace
run_remote_prepare_checks

if [ "$MODE" = "prepare-only" ]; then
  echo "C10.2 prepare-only complete. Evidence dir reserved: $REMOTE_OUT_DIR"
  exit 0
fi

if [ "$MODE" = "preflight" ]; then
  collect_snapshot "preflight" "false"
  echo "C10.2 preflight complete. Evidence: $REMOTE_OUT_DIR/preflight"
  exit 0
fi

if [ "$MODE" = "run-config-missing-dry-run" ]; then
  run_config_missing_flow "$MODE" "$DRY_RUN_CONFIRM_PHRASE"
  echo "C10.2 config_missing dry-run complete. Evidence: $REMOTE_OUT_DIR/$MODE"
  exit 0
fi

run_config_missing_flow "$MODE" "$CONFIRM_PHRASE"
echo "C10.2 config_missing real-write-start complete. Evidence: $REMOTE_OUT_DIR/$MODE"
