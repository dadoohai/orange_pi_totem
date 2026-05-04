#!/usr/bin/env bash
set -euo pipefail

HOST="root@192.168.1.147"
MODE="prepare-only"
REMOTE_DIR="/tmp/dadooh-c10-1"
REMOTE_OUT_DIR="/tmp/dadooh-c10-1-reboot-autoboot"
PROFILE_NAME="dadooh-c9-8-wifi-persistent"
SSH_WAIT_SEC="300"
CONVERGE_SEC="180"
CONFIRM_PHRASE="CONFIRMO REBOOT CONTROLADO C10.1"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_1_reboot_autoboot_config_real.sh [host] [--prepare-only|--preflight|--reboot-autoboot] [--ssh-wait-sec N] [--converge-sec N]

Modes:
  --prepare-only
      Copy read-only helpers to /tmp and run non-invasive self-tests.

  --preflight
      Collect a sanitized snapshot only. Does not read or write the real config.

  --reboot-autoboot
      Requires exact human confirmation, performs one controlled reboot, waits
      for SSH, then validates sanitized autoboot state.
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
    --reboot-autoboot)
      MODE="reboot-autoboot"
      ;;
    --ssh-wait-sec)
      shift
      SSH_WAIT_SEC="${1:-}"
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
  prepare-only|preflight|reboot-autoboot)
    ;;
  *)
    echo "error: unsupported mode $MODE" >&2
    exit 2
    ;;
esac

case "$SSH_WAIT_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --ssh-wait-sec must be a positive integer" >&2
    exit 2
    ;;
esac

case "$CONVERGE_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --converge-sec must be a positive integer" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BOARD_DIR="$REPO_ROOT/scripts/board"

LOCAL_STATUS_AGGREGATE="$BOARD_DIR/totem_status_aggregate.py"
LOCAL_STATUS_RENDER="$BOARD_DIR/totem_status_render_preview.py"
LOCAL_HANDOFF="$BOARD_DIR/totem_visual_setup_writer_handoff.py"
LOCAL_VISUAL_WIZARD="$BOARD_DIR/totem_setup_visual_wizard.py"
LOCAL_MINIMAL_SERVER="$BOARD_DIR/totem_setup_minimal_server.py"
LOCAL_CONTRACT="$BOARD_DIR/totem_config_contract_validate.py"
LOCAL_WIFI_ADAPTER="$BOARD_DIR/totem_wifi_nm_adapter.py"

for path in \
  "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_HANDOFF" \
  "$LOCAL_VISUAL_WIZARD" "$LOCAL_MINIMAL_SERVER" "$LOCAL_CONTRACT" "$LOCAL_WIFI_ADAPTER"
do
  if [ ! -f "$path" ]; then
    echo "error: missing local input" >&2
    exit 1
  fi
done

prepare_workspace() {
  echo "Preparing C10.1 reboot/autoboot workspace on target board"
  ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR'"

  echo "Copying C10.1 read-only helpers to temporary board workspace"
  scp \
    "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_HANDOFF" \
    "$LOCAL_VISUAL_WIZARD" "$LOCAL_MINIMAL_SERVER" "$LOCAL_CONTRACT" "$LOCAL_WIFI_ADAPTER" \
    "$HOST:$REMOTE_DIR/" >/dev/null
}

run_remote_prepare_checks() {
  echo "Running C10.1 prepare checks on the board"
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail

HANDOFF="$REMOTE_DIR/totem_visual_setup_writer_handoff.py"
VISUAL="$REMOTE_DIR/totem_setup_visual_wizard.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
WIFI_ADAPTER="$REMOTE_DIR/totem_wifi_nm_adapter.py"

umask 077
mkdir -p "$REMOTE_DIR" "$REMOTE_OUT_DIR"
chmod 700 "$REMOTE_DIR" "$REMOTE_OUT_DIR"

python3 "$HANDOFF" --self-test
python3 "$VISUAL" --self-test
python3 "$CONTRACT" --self-test
python3 "$WIFI_ADAPTER" --self-test --out-dir "$REMOTE_OUT_DIR/wifi-adapter-self-test" >/dev/null

echo "remote C10.1 prepare checks: ok"
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
import re
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
KERNEL_CRITICAL_PATTERN = re.compile(
    r"oops|panic|ext4-fs error|aborting journal|remounting filesystem read-only|mmc.*timeout|mmc.*reset",
    re.IGNORECASE,
)


def run(args: list[str], timeout: int = 3) -> tuple[int | None, str]:
    try:
        completed = subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None, "unknown"
    return completed.returncode, (completed.stdout or "").strip()


def run_shell(command: str, timeout: int = 5) -> tuple[int | None, str]:
    try:
        completed = subprocess.run(
            ["bash", "-lc", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:
        return None, "unknown"
    return completed.returncode, (completed.stdout or "").strip()


def refresh_public_status() -> None:
    opt_aggregate = pathlib.Path("/opt/totem/bin/totem_status_aggregate.py")
    if opt_aggregate.exists():
        subprocess.run(
            ["python3", str(opt_aggregate)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return
    if aggregate.exists():
        env = dict(os.environ)
        env["PYTHONPATH"] = str(remote_dir)
        subprocess.run(
            ["python3", str(aggregate)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            env=env,
        )


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
            parts = [
                part.decode("utf-8", "ignore")
                for part in (proc / "cmdline").read_bytes().split(b"\0")
                if part
            ]
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
    mode = stat.S_IMODE(st.st_mode)
    payload["mode_0640"] = mode == 0o640
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


def system_failed_count() -> int | str:
    rc, output = run_shell("systemctl --failed --no-legend --plain 2>/dev/null | sed '/^$/d' | wc -l")
    if rc is None:
        return "unknown"
    try:
        return int(output.strip())
    except ValueError:
        return "unknown"


def kernel_critical_count() -> int | str:
    rc, output = run_shell(
        "journalctl -k -b --no-pager --output=short-iso 2>/dev/null | "
        "grep -Ei 'oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset' | wc -l",
        timeout=8,
    )
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
service_active = run(["systemctl", "is-active", "kiosky-player.service"])[1] or "unknown"
service_enabled = run(["systemctl", "is-enabled", "kiosky-player.service"])[1] or "unknown"
nrestarts = run(["systemctl", "show", "kiosky-player.service", "-p", "NRestarts", "--value"])[1] or "unknown"
failed_count = system_failed_count()
critical_count = kernel_critical_count()

payload = {
    "schema_version": "dadooh-c10.1-reboot-autoboot-status.v1",
    "phase": phase,
    "service_active": service_active,
    "service_enabled": service_enabled,
    "nrestarts": nrestarts,
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
    "kiosky_player_repo_changed": False,
    "player_mpv_changed_outside_autoboot": False,
    "reboot_called": phase == "post-reboot",
    "read_only_not_enabled": True,
    "power_cut_not_tested": True,
    "raw_logs_written": False,
    "config_content_published": False,
    "backup_content_published": False,
    "private_values_published": False,
    "network_identifiers_published": False,
    "environment_identifier_raw_published": False,
    "read_only_readiness": {
        "root_read_only_still_blocked": True,
        "power_cut_still_blocked": True,
        "networkmanager_policy_needed": True,
        "journald_policy_needed": True,
        "var_lib_and_etc_audit_needed": True,
        "data_cache_config_on_expected_path": True,
        "tmp_runtime_on_expected_path": True,
    },
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

wait_for_ssh_down() {
  local tcp_host="${HOST#*@}"
  tcp_host="${tcp_host%%:*}"
  local deadline=$(( $(date +%s) + 60 ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    if ! timeout 3 bash -c ":</dev/tcp/$tcp_host/22" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 0
}

wait_for_ssh_up() {
  local tcp_host="${HOST#*@}"
  tcp_host="${tcp_host%%:*}"
  local deadline=$(( $(date +%s) + SSH_WAIT_SEC ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    if timeout 5 bash -c ":</dev/tcp/$tcp_host/22" >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  return 1
}

prepare_workspace
run_remote_prepare_checks

if [ "$MODE" = "prepare-only" ]; then
  echo "C10.1 prepare-only complete. Evidence dir reserved: $REMOTE_OUT_DIR"
  exit 0
fi

if [ "$MODE" = "preflight" ]; then
  collect_snapshot "preflight" "false"
  echo "C10.1 preflight complete. Evidence: $REMOTE_OUT_DIR/preflight"
  exit 0
fi

echo "Collecting sanitized pre-reboot snapshot"
collect_snapshot "pre-reboot" "false"

echo
echo "Reboot controlado C10.1 vai reiniciar a placa uma vez."
echo "Nao habilita root read-only, nao executa corte seco, nao escreve config e nao chama writer."
echo "Before rebooting, type exactly:"
echo "$CONFIRM_PHRASE"
printf '> '
IFS= read -r AUTH_TEXT
if [ "$AUTH_TEXT" != "$CONFIRM_PHRASE" ]; then
  echo "Authorization text did not match. Aborting before reboot." >&2
  exit 20
fi

echo "Issuing controlled reboot"
REBOOT_STARTED_AT="$(date +%s)"
set +e
ssh "$HOST" "sync; (sleep 1; systemctl reboot) >/dev/null 2>&1 &" >/dev/null
REBOOT_SSH_RC="$?"
set -e
if [ "$REBOOT_SSH_RC" -ne 0 ]; then
  echo "warning: SSH command returned during reboot request; continuing wait" >&2
fi

wait_for_ssh_down || true
if ! wait_for_ssh_up; then
  echo "error: SSH did not return within wait window" >&2
  exit 30
fi
SSH_RETURNED_AT="$(date +%s)"
SECONDS_UNTIL_SSH=$(( SSH_RETURNED_AT - REBOOT_STARTED_AT ))
echo "SSH returned after ${SECONDS_UNTIL_SSH}s"

prepare_workspace
echo "Collecting sanitized post-reboot snapshot"
collect_snapshot "post-reboot" "true"

ssh "$HOST" "REMOTE_OUT_DIR='$REMOTE_OUT_DIR' SECONDS_UNTIL_SSH='$SECONDS_UNTIL_SSH' bash -s" <<'REMOTE_META'
set -euo pipefail
python3 - "$REMOTE_OUT_DIR/post-reboot/status.json" "$SECONDS_UNTIL_SSH" <<'PY'
import json
import os
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
seconds_until_ssh = int(sys.argv[2])
data = json.loads(path.read_text(encoding="utf-8"))
data["seconds_until_ssh_available"] = seconds_until_ssh
tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, path)
os.chmod(path, 0o600)
print(json.dumps(data, indent=2, sort_keys=True))
PY
REMOTE_META

echo "C10.1 reboot-autoboot complete. Evidence: $REMOTE_OUT_DIR/post-reboot"
