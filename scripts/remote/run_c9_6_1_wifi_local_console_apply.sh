#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
REMOTE_DIR="/tmp/dadooh-c9-6-1-wifi"
REMOTE_OUT_DIR="/tmp/dadooh-c9-6-1-local-console-apply"
REMOTE_SECRETS_DIR="/tmp/dadooh-c9-6-local-secrets"
TIMEOUT_SEC="45"
REMOTE_TTY="2"
PROFILE_NAME="dadooh-c9-6-wifi-test"
OPERATOR_WINDOW_SEC="900"
CONFIRM_PHRASE="CONFIRMO APPLY WIFI REAL C9.6 COM CONSOLE LOCAL"
PAUSE_CONFIRM_PHRASE="CONFIRMO PAUSAR PLAYER PARA APPLY WIFI C9.6.2"

usage() {
  cat <<'USAGE'
Usage:
  run_c9_6_1_wifi_local_console_apply.sh [host] [--prepare-only|--local-console-preflight|--local-console-apply-rollback-after-test|--local-console-apply-with-player-pause] [options]

Options:
  --timeout-sec N
  --tty N
  --profile-name NAME
  --operator-window-sec N

Modes:
  --prepare-only
      Copy scripts to /tmp and run self-tests only. Does not alter network.

  --local-console-preflight
      Opens the local TTY and runs sanitized preflight with local console
      confirmed. Does not alter network.

  --local-console-apply-rollback-after-test
      Requires exact human confirmation. Opens the local TTY, asks Wi-Fi
      credentials on the totem only, runs real apply with rollback-after-test.

  --local-console-apply-with-player-pause
      C9.6.2. Requires exact human confirmation. Pauses kiosky-player.service,
      verifies HDMI is free, opens the local TTY, runs real apply with
      rollback-after-test, and restores the service at the end.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only)
      MODE="prepare-only"
      ;;
    --operator-window-sec)
      shift
      if [ "$#" -eq 0 ]; then
        echo "error: --operator-window-sec requires a number" >&2
        exit 2
      fi
      OPERATOR_WINDOW_SEC="$1"
      ;;
    --local-console-preflight)
      MODE="local-console-preflight"
      ;;
    --local-console-apply-rollback-after-test)
      MODE="local-console-apply-rollback-after-test"
      ;;
    --local-console-apply-with-player-pause)
      MODE="local-console-apply-with-player-pause"
      ;;
    --timeout-sec)
      shift
      if [ "$#" -eq 0 ]; then
        echo "error: --timeout-sec requires a number" >&2
        exit 2
      fi
      TIMEOUT_SEC="$1"
      ;;
    --tty)
      shift
      if [ "$#" -eq 0 ]; then
        echo "error: --tty requires a number" >&2
        exit 2
      fi
      REMOTE_TTY="$1"
      ;;
    --profile-name)
      shift
      if [ "$#" -eq 0 ]; then
        echo "error: --profile-name requires a value" >&2
        exit 2
      fi
      PROFILE_NAME="$1"
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
  prepare-only|local-console-preflight|local-console-apply-rollback-after-test|local-console-apply-with-player-pause)
    ;;
  *)
    echo "error: unsupported mode $MODE" >&2
    exit 2
    ;;
esac

case "$TIMEOUT_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --timeout-sec must be a positive integer" >&2
    exit 2
    ;;
esac

case "$REMOTE_TTY" in
  ''|*[!0-9]*|0)
    echo "error: --tty must be a positive integer" >&2
    exit 2
    ;;
esac

case "$OPERATOR_WINDOW_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --operator-window-sec must be a positive integer" >&2
    exit 2
    ;;
esac

if [ -z "$HOST" ]; then
  echo "error: host is required" >&2
  usage >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_ADAPTER="$REPO_ROOT/scripts/board/totem_wifi_nm_adapter.py"
LOCAL_TTY="$REPO_ROOT/scripts/board/totem_wifi_local_credentials_tty.py"

for path in "$LOCAL_ADAPTER" "$LOCAL_TTY"; do
  if [ ! -f "$path" ]; then
    echo "error: missing local script" >&2
    exit 1
  fi
done

echo "Preparing C9.6.1 local console workspace on $HOST"
ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR' '$REMOTE_SECRETS_DIR' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR' '$REMOTE_SECRETS_DIR'"

echo "Copying C9.6.1 scripts to temporary board workspace"
scp "$LOCAL_ADAPTER" "$LOCAL_TTY" "$HOST:$REMOTE_DIR/"

echo "Running C9.6.1 prepare checks on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail

ADAPTER="$REMOTE_DIR/totem_wifi_nm_adapter.py"
LOCAL_TTY="$REMOTE_DIR/totem_wifi_local_credentials_tty.py"

umask 077
chmod 700 "$REMOTE_DIR" "$REMOTE_OUT_DIR"
command -v openvt >/dev/null
python3 "$ADAPTER" --self-test --out-dir "$REMOTE_OUT_DIR/adapter-self-test"
python3 "$LOCAL_TTY" --self-test --out-dir "$REMOTE_OUT_DIR/tty-self-test"

echo "remote C9.6.1 prepare checks: ok"
REMOTE_PREP

if [ "$MODE" = "prepare-only" ]; then
  echo "C9.6.1 prepare-only complete. Evidence dir reserved: $REMOTE_OUT_DIR"
  exit 0
fi

if [ "$MODE" = "local-console-apply-rollback-after-test" ]; then
  echo
  echo "HDMI/tela e teclado local devem estar conectados. SSH pode cair durante o teste."
  echo "Before real Wi-Fi apply, type exactly:"
  echo "$CONFIRM_PHRASE"
  printf '> '
  IFS= read -r AUTH_TEXT
  if [ "$AUTH_TEXT" != "$CONFIRM_PHRASE" ]; then
    echo "Authorization text did not match. Aborting before apply." >&2
    exit 20
  fi
fi

if [ "$MODE" = "local-console-apply-with-player-pause" ]; then
  echo
  echo "HDMI/tela e teclado local devem estar conectados. O player sera pausado temporariamente."
  echo "Before pausing the player and running real Wi-Fi apply, type exactly:"
  echo "$PAUSE_CONFIRM_PHRASE"
  printf '> '
  IFS= read -r AUTH_TEXT
  if [ "$AUTH_TEXT" != "$PAUSE_CONFIRM_PHRASE" ]; then
    echo "Authorization text did not match. Aborting before service pause." >&2
    exit 20
  fi
fi

echo "Running C9.6.1 $MODE on local console"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_SECRETS_DIR='$REMOTE_SECRETS_DIR' TIMEOUT_SEC='$TIMEOUT_SEC' MODE='$MODE' REMOTE_TTY='$REMOTE_TTY' PROFILE_NAME='$PROFILE_NAME' OPERATOR_WINDOW_SEC='$OPERATOR_WINDOW_SEC' bash -s" <<'REMOTE_RUN'
set -euo pipefail

ADAPTER="$REMOTE_DIR/totem_wifi_nm_adapter.py"
LOCAL_TTY="$REMOTE_DIR/totem_wifi_local_credentials_tty.py"
RUN_OUT="$REMOTE_OUT_DIR/$MODE"
FINAL_STATUS="$RUN_OUT/final-status.json"
PID_FILE="$RUN_OUT/openvt.pid"

umask 077
mkdir -p "$RUN_OUT" "$REMOTE_SECRETS_DIR"
chmod 700 "$RUN_OUT" "$REMOTE_SECRETS_DIR"

write_final_status() {
  python3 - "$RUN_OUT" "$FINAL_STATUS" "$MODE" "${OPENVT_RC:-not_run}" <<'PY'
import json
import os
import pathlib
import stat
import sys

run_out = pathlib.Path(sys.argv[1])
final_status = pathlib.Path(sys.argv[2])
mode = sys.argv[3]
openvt_rc = sys.argv[4]

counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    lowered = [part.lower() for part in parts]
    basenames = [pathlib.Path(part).name.lower() for part in parts]
    if "totem_setup_local_wizard.py" in basenames or "totem_wifi_local_credentials_tty.py" in basenames:
        counts["setup"] += 1
    if any("totem_status_renderer" in name for name in basenames):
        counts["renderer"] += 1
    if any(name == "mpv" for name in basenames):
        counts["mpv"] += 1
    if "kiosk.py" in basenames:
        counts["player"] += 1

adapter_status = {}
status_path = run_out / "status.json"
if status_path.exists():
    try:
        adapter_status = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        adapter_status = {}

service_active = os.popen("systemctl is-active kiosky-player.service 2>/dev/null").read().strip() or "unknown"
service_enabled = os.popen("systemctl is-enabled kiosky-player.service 2>/dev/null").read().strip() or "unknown"
nrestarts = os.popen("systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null").read().strip() or "unknown"
dedicated_profile_present = os.system("nmcli -t -f NAME connection show dadooh-c9-6-wifi-test >/dev/null 2>&1") == 0
dedicated_profile_present = os.system("nmcli -t -f NAME connection show dadooh-c9-6-wifi-test >/dev/null 2>&1") == 0

public_state = "unknown"
try:
    status_data = json.loads(pathlib.Path("/tmp/dadooh-status/status.json").read_text(encoding="utf-8"))
    value = status_data.get("public_state")
    if isinstance(value, str):
        public_state = value
except Exception:
    pass

playback = "unknown"
try:
    playback_data = json.loads(pathlib.Path("/tmp/kiosky-status.json").read_text(encoding="utf-8"))
    value = playback_data.get("playback_state")
    if isinstance(value, str):
        playback = value
except Exception:
    pass

payload = {
    "mode": mode,
    "openvt_rc": openvt_rc,
    "service_active": service_active,
    "service_enabled": service_enabled,
    "nrestarts": nrestarts,
    "public_state": public_state,
    "playback": playback,
    "process_counts": counts,
    "apply_attempted": bool(adapter_status.get("wifi_activation_attempted", False)),
    "network_changed": bool(adapter_status.get("network_changed", False)),
    "ssh_path_category": adapter_status.get("ssh_path_category", "unknown"),
    "ssh_path_risk_acknowledged": bool(adapter_status.get("ssh_path_risk_acknowledged", False)),
    "local_console_confirmed": bool(adapter_status.get("local_console_confirmed", False)),
    "wifi_activation_result": adapter_status.get("wifi_activation_result", "not_applicable"),
    "rollback_status": adapter_status.get("rollback_status", "not_applicable"),
    "dedicated_profile_present_after": dedicated_profile_present,
    "rollback_effective_result": (
        "success"
        if adapter_status.get("wifi_activation_attempted") and not dedicated_profile_present
        else "failure"
        if adapter_status.get("wifi_activation_attempted") and dedicated_profile_present
        else "not_applicable"
    ),
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "player_changed_by_runner": False,
    "mpv_changed_by_runner": False,
    "service_changed_by_runner": False,
}

tmp = final_status.with_name(f".{final_status.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, final_status)
os.chmod(final_status, 0o600)

assert stat.S_IMODE(run_out.stat().st_mode) == 0o700
assert stat.S_IMODE(final_status.stat().st_mode) == 0o600
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

require_apply_artifacts() {
  python3 - "$RUN_OUT" <<'PY'
import json
import pathlib
import sys

run_out = pathlib.Path(sys.argv[1])
local_status_path = run_out / "local-console-status.json"
adapter_status_path = run_out / "status.json"

if not local_status_path.exists():
    print("missing_local_console_status", file=sys.stderr)
    raise SystemExit(30)

local_status = json.loads(local_status_path.read_text(encoding="utf-8"))
if local_status.get("credentials_collected") is not True:
    print("credentials_not_collected", file=sys.stderr)
    raise SystemExit(31)

if not adapter_status_path.exists():
    print("missing_adapter_status", file=sys.stderr)
    raise SystemExit(32)

adapter_status = json.loads(adapter_status_path.read_text(encoding="utf-8"))
if adapter_status.get("wifi_activation_attempted") is not True:
    print("apply_not_attempted", file=sys.stderr)
    raise SystemExit(33)

print("apply_artifacts_present")
PY
}

if [ "$MODE" = "local-console-preflight" ]; then
  set +e
  setsid openvt -c "$REMOTE_TTY" -s -f -w -- \
    env TERM=linux /usr/bin/python3 "$LOCAL_TTY" \
      --preflight-only \
      --adapter-path "$ADAPTER" \
      --out-dir "$RUN_OUT" \
      --secrets-dir "$REMOTE_SECRETS_DIR" \
      --profile-name "$PROFILE_NAME" \
      --timeout-sec "$TIMEOUT_SEC" \
      --auto-exit-sec 5 >"$RUN_OUT/openvt.out" 2>"$RUN_OUT/openvt.err"
  OPENVT_RC="$?"
  set -e
  chmod 600 "$RUN_OUT/openvt.out" "$RUN_OUT/openvt.err" 2>/dev/null || true
  write_final_status >/dev/null
  if [ "$OPENVT_RC" -ne 0 ] && { [ ! -s "$RUN_OUT/status.json" ] || [ ! -s "$RUN_OUT/preflight.json" ]; }; then
    echo "remote C9.6.1 local-console-preflight: failed openvt_rc=$OPENVT_RC" >&2
    exit "$OPENVT_RC"
  fi
  echo "remote C9.6.1 local-console-preflight: ok"
  exit 0
fi

if [ "$MODE" = "local-console-apply-with-player-pause" ]; then
  WRAPPER="$RUN_OUT/c9-6-2-player-pause-wrapper.sh"
  WRAPPER_DONE="$RUN_OUT/wrapper.done"
  cat >"$WRAPPER" <<'WRAPPER_SH'
#!/usr/bin/env bash
set -euo pipefail

FINAL_STATUS="$RUN_OUT/final-status.json"
INITIAL_STATUS="$RUN_OUT/initial-status.json"
PAUSED_STATUS="$RUN_OUT/paused-status.json"
POST_APPLY_STATUS="$RUN_OUT/post-apply-status.json"
OPENVT_PID_FILE="$RUN_OUT/openvt.pid"
WRAPPER_DONE="$RUN_OUT/wrapper.done"
OPENVT_RC="not_run"
OPENVT_PID=""
SERVICE_PAUSED="false"
SERVICE_STOP_ATTEMPTED="false"
SERVICE_RESTORE_ATTEMPTED="false"
INITIAL_SERVICE_ACTIVE="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
INITIAL_SERVICE_ENABLED="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"

snapshot() {
  local target="$1"
  local phase="$2"
  local wrapper_rc="${3:-0}"
  python3 - "$RUN_OUT" "$target" "$MODE" "$phase" "$OPENVT_RC" \
    "$SERVICE_STOP_ATTEMPTED" "$SERVICE_PAUSED" "$SERVICE_RESTORE_ATTEMPTED" \
    "$INITIAL_SERVICE_ACTIVE" "$INITIAL_SERVICE_ENABLED" "$wrapper_rc" <<'PY'
import json
import os
import pathlib
import stat
import sys

run_out = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
mode = sys.argv[3]
phase = sys.argv[4]
openvt_rc = sys.argv[5]
service_stop_attempted = sys.argv[6] == "true"
service_paused = sys.argv[7] == "true"
service_restore_attempted = sys.argv[8] == "true"
initial_service_active = sys.argv[9] or "unknown"
initial_service_enabled = sys.argv[10] or "unknown"
wrapper_rc = sys.argv[11]

counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    basenames = [pathlib.Path(part).name.lower() for part in parts]
    if "totem_setup_local_wizard.py" in basenames or "totem_wifi_local_credentials_tty.py" in basenames:
        counts["setup"] += 1
    if any("totem_status_renderer" in name for name in basenames):
        counts["renderer"] += 1
    if any(name == "mpv" for name in basenames):
        counts["mpv"] += 1
    if "kiosk.py" in basenames:
        counts["player"] += 1

adapter_status = {}
status_path = run_out / "status.json"
if status_path.exists():
    try:
        adapter_status = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        adapter_status = {}

service_active = os.popen("systemctl is-active kiosky-player.service 2>/dev/null").read().strip() or "unknown"
service_enabled = os.popen("systemctl is-enabled kiosky-player.service 2>/dev/null").read().strip() or "unknown"
nrestarts = os.popen("systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null").read().strip() or "unknown"

public_state = "unknown"
try:
    status_data = json.loads(pathlib.Path("/tmp/dadooh-status/status.json").read_text(encoding="utf-8"))
    value = status_data.get("public_state")
    if isinstance(value, str):
        public_state = value
except Exception:
    pass

playback = "unknown"
try:
    playback_data = json.loads(pathlib.Path("/tmp/kiosky-status.json").read_text(encoding="utf-8"))
    value = playback_data.get("playback_state")
    if isinstance(value, str):
        playback = value
except Exception:
    pass

apply_attempted = bool(adapter_status.get("wifi_activation_attempted", False))
payload = {
    "mode": mode,
    "phase": phase,
    "wrapper_rc": wrapper_rc,
    "openvt_rc": openvt_rc,
    "initial_service_active": initial_service_active,
    "initial_service_enabled": initial_service_enabled,
    "service_active": service_active,
    "service_enabled": service_enabled,
    "nrestarts": nrestarts,
    "public_state": public_state,
    "playback": playback,
    "process_counts": counts,
    "player_pause_requested": True,
    "service_stop_attempted": service_stop_attempted,
    "service_paused": service_paused,
    "service_restore_attempted": service_restore_attempted,
    "apply_attempted": apply_attempted,
    "network_changed": bool(adapter_status.get("network_changed", False)) or apply_attempted,
    "ssh_path_category": adapter_status.get("ssh_path_category", "unknown"),
    "ssh_path_risk_acknowledged": bool(adapter_status.get("ssh_path_risk_acknowledged", False)),
    "local_console_confirmed": bool(adapter_status.get("local_console_confirmed", False)),
    "wifi_activation_result": adapter_status.get("wifi_activation_result", "not_applicable"),
    "rollback_status": adapter_status.get("rollback_status", "not_applicable"),
    "dedicated_profile_present_after": dedicated_profile_present,
    "rollback_effective_result": (
        "success"
        if apply_attempted and not dedicated_profile_present
        else "failure"
        if apply_attempted and dedicated_profile_present
        else "not_applicable"
    ),
    "dedicated_profile_touched": bool(adapter_status.get("wifi_profile_created", False))
    or bool(adapter_status.get("wifi_activation_attempted", False)),
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "player_changed_by_runner": service_stop_attempted,
    "mpv_changed_by_runner": service_stop_attempted,
    "service_changed_by_runner": service_stop_attempted,
    "hotspot_created": False,
    "portal_created": False,
    "reboot_called": False,
    "network_identifiers_published": False,
    "credential_values_published": False,
}

tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
assert stat.S_IMODE(run_out.stat().st_mode) == 0o700
assert stat.S_IMODE(target.stat().st_mode) == 0o600
PY
}

restore_service() {
  if [ "$SERVICE_PAUSED" = "true" ]; then
    SERVICE_RESTORE_ATTEMPTED="true"
    if [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
      systemctl enable kiosky-player.service >/dev/null 2>&1 || true
    fi
    if [ "$INITIAL_SERVICE_ACTIVE" = "active" ] || [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
      systemctl start kiosky-player.service >/dev/null 2>&1 || true
    fi
    sleep 12
    SERVICE_PAUSED="false"
  fi
}

kill_openvt_if_running() {
  if [ -n "${OPENVT_PID:-}" ] && kill -0 "$OPENVT_PID" 2>/dev/null; then
    kill -TERM "-$OPENVT_PID" 2>/dev/null || kill -TERM "$OPENVT_PID" 2>/dev/null || true
    sleep 3
    kill -KILL "-$OPENVT_PID" 2>/dev/null || kill -KILL "$OPENVT_PID" 2>/dev/null || true
  fi
}

safe_manual_rollback() {
  /usr/bin/python3 "$ADAPTER" \
    --rollback-last \
    --profile-name "$PROFILE_NAME" \
    --timeout-sec "$TIMEOUT_SEC" \
    --out-dir "$RUN_OUT" >/dev/null 2>&1 || true
}

on_exit() {
  local rc="$?"
  trap - EXIT INT TERM HUP
  kill_openvt_if_running
  if [ "$OPENVT_RC" = "124" ]; then
    safe_manual_rollback
  fi
  restore_service
  snapshot "$FINAL_STATUS" "final" "$rc" || true
  printf '%s\n' "$rc" >"$WRAPPER_DONE"
  chmod 600 "$WRAPPER_DONE" 2>/dev/null || true
  exit "$rc"
}
trap on_exit EXIT INT TERM HUP

snapshot "$INITIAL_STATUS" "initial" "0"

SERVICE_STOP_ATTEMPTED="true"
systemctl stop kiosky-player.service >/dev/null 2>&1
SERVICE_PAUSED="true"

for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 2
  snapshot "$PAUSED_STATUS" "paused" "0"
  if /usr/bin/python3 - "$PAUSED_STATUS" <<'PY'
import json
import pathlib
import sys

status = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
counts = status.get("process_counts", {})
raise SystemExit(0 if all(counts.get(key) == 0 for key in ("player", "mpv", "renderer", "setup")) else 1)
PY
  then
    break
  fi
done

/usr/bin/python3 - "$PAUSED_STATUS" <<'PY'
import json
import pathlib
import sys

status = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
counts = status.get("process_counts", {})
if not all(counts.get(key) == 0 for key in ("player", "mpv", "renderer", "setup")):
    print("hdmi_not_free_after_player_pause", file=sys.stderr)
    raise SystemExit(42)
PY

set +e
setsid openvt -c "$REMOTE_TTY" -s -f -w -- \
  env TERM=linux /usr/bin/python3 "$LOCAL_TTY" \
    --apply-rollback-after-test \
    --adapter-path "$ADAPTER" \
    --out-dir "$RUN_OUT" \
    --secrets-dir "$REMOTE_SECRETS_DIR" \
    --profile-name "$PROFILE_NAME" \
    --timeout-sec "$TIMEOUT_SEC" \
    --auto-exit-sec 20 >/dev/null 2>&1 &
OPENVT_PID="$!"
echo "$OPENVT_PID" >"$OPENVT_PID_FILE"
chmod 600 "$OPENVT_PID_FILE"

limit=$((TIMEOUT_SEC + OPERATOR_WINDOW_SEC))
elapsed=0
while kill -0 "$OPENVT_PID" 2>/dev/null && [ "$elapsed" -lt "$limit" ]; do
  sleep 2
  elapsed=$((elapsed + 2))
done

if kill -0 "$OPENVT_PID" 2>/dev/null; then
  OPENVT_RC="124"
  kill_openvt_if_running
else
  wait "$OPENVT_PID"
  OPENVT_RC="$?"
fi
set -e

snapshot "$POST_APPLY_STATUS" "post_apply" "$OPENVT_RC"

/usr/bin/python3 - "$RUN_OUT" <<'PY'
import json
import pathlib
import sys

run_out = pathlib.Path(sys.argv[1])
local_status_path = run_out / "local-console-status.json"
adapter_status_path = run_out / "status.json"
if not local_status_path.exists():
    print("missing_local_console_status", file=sys.stderr)
    raise SystemExit(30)
local_status = json.loads(local_status_path.read_text(encoding="utf-8"))
if local_status.get("credentials_collected") is not True:
    print("credentials_not_collected", file=sys.stderr)
    raise SystemExit(31)
if not adapter_status_path.exists():
    print("missing_adapter_status", file=sys.stderr)
    raise SystemExit(32)
adapter_status = json.loads(adapter_status_path.read_text(encoding="utf-8"))
if adapter_status.get("wifi_activation_attempted") is not True:
    print("apply_not_attempted", file=sys.stderr)
    raise SystemExit(33)
PY

exit 0
WRAPPER_SH
  chmod 700 "$WRAPPER"

  ADAPTER="$ADAPTER" \
  LOCAL_TTY="$LOCAL_TTY" \
  RUN_OUT="$RUN_OUT" \
  MODE="$MODE" \
  REMOTE_SECRETS_DIR="$REMOTE_SECRETS_DIR" \
  REMOTE_TTY="$REMOTE_TTY" \
  PROFILE_NAME="$PROFILE_NAME" \
  TIMEOUT_SEC="$TIMEOUT_SEC" \
  setsid "$WRAPPER" >/dev/null 2>&1 &
  WRAPPER_PID="$!"
  echo "$WRAPPER_PID" >"$RUN_OUT/wrapper.pid"
  chmod 600 "$RUN_OUT/wrapper.pid"

  limit=$((TIMEOUT_SEC + OPERATOR_WINDOW_SEC + 120))
  elapsed=0
  while kill -0 "$WRAPPER_PID" 2>/dev/null && [ "$elapsed" -lt "$limit" ]; do
    sleep 2
    elapsed=$((elapsed + 2))
  done

  if kill -0 "$WRAPPER_PID" 2>/dev/null; then
    kill -TERM "-$WRAPPER_PID" 2>/dev/null || kill -TERM "$WRAPPER_PID" 2>/dev/null || true
    sleep 5
  fi

  WRAPPER_RC="0"
  if kill -0 "$WRAPPER_PID" 2>/dev/null; then
    kill -KILL "-$WRAPPER_PID" 2>/dev/null || kill -KILL "$WRAPPER_PID" 2>/dev/null || true
    WRAPPER_RC="124"
  else
    wait "$WRAPPER_PID" || WRAPPER_RC="$?"
  fi

  if [ -s "$FINAL_STATUS" ]; then
    cat "$FINAL_STATUS"
  else
    OPENVT_RC="$WRAPPER_RC" write_final_status
  fi

  if [ "$WRAPPER_RC" != "0" ]; then
    exit "$WRAPPER_RC"
  fi
  require_apply_artifacts >/dev/null
  echo "remote C9.6.2 local-console-apply-with-player-pause: ok"
  exit 0
fi

setsid openvt -c "$REMOTE_TTY" -s -f -w -- \
  env TERM=linux /usr/bin/python3 "$LOCAL_TTY" \
    --apply-rollback-after-test \
    --adapter-path "$ADAPTER" \
    --out-dir "$RUN_OUT" \
    --secrets-dir "$REMOTE_SECRETS_DIR" \
    --profile-name "$PROFILE_NAME" \
    --timeout-sec "$TIMEOUT_SEC" \
    --auto-exit-sec 20 >/dev/null 2>&1 &
OPENVT_PID="$!"
echo "$OPENVT_PID" >"$PID_FILE"
chmod 600 "$PID_FILE"

limit=$((TIMEOUT_SEC + 180))
elapsed=0
while kill -0 "$OPENVT_PID" 2>/dev/null && [ "$elapsed" -lt "$limit" ]; do
  sleep 2
  elapsed=$((elapsed + 2))
done

write_final_status >/dev/null
require_apply_artifacts >/dev/null
echo "remote C9.6.1 local-console-apply-rollback-after-test: ok"
REMOTE_RUN
