#!/usr/bin/env bash
set -euo pipefail

HOST="root@192.168.18.115"
MODE="prepare-only"
REMOTE_DIR="/tmp/dadooh-c9-5-wifi"
REMOTE_OUT_DIR="/tmp/dadooh-c9-5-wifi-readonly"
TIMEOUT_SEC="3"

usage() {
  cat <<'USAGE'
Usage:
  run_c9_5_wifi_readonly_plan.sh [host] [--prepare-only|--read-only|--plan] [--timeout-sec N]

Modes:
  --prepare-only
      Copy the C9.5 adapter to /tmp and run its self-test on the board.
      Does not stop services, does not read real config, and does not alter network.

  --read-only
      Run the adapter in read-only mode and write sanitized artifacts under /tmp.
      Does not collect credentials, does not call writer, and does not alter network.

  --plan
      Generate the sanitized future apply plan under /tmp.
      Does not collect credentials, does not enable apply, and does not alter network.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only)
      MODE="prepare-only"
      ;;
    --read-only)
      MODE="read-only"
      ;;
    --plan)
      MODE="plan"
      ;;
    --timeout-sec)
      shift
      if [ "$#" -eq 0 ]; then
        echo "error: --timeout-sec requires a number" >&2
        exit 2
      fi
      TIMEOUT_SEC="$1"
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
  prepare-only|read-only|plan)
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_ADAPTER="$REPO_ROOT/scripts/board/totem_wifi_nm_adapter.py"

if [ ! -f "$LOCAL_ADAPTER" ]; then
  echo "error: missing $LOCAL_ADAPTER" >&2
  exit 1
fi

echo "Preparing $REMOTE_DIR on $HOST"
ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR'"

echo "Copying C9.5 Wi-Fi read-only adapter to $HOST:$REMOTE_DIR"
scp "$LOCAL_ADAPTER" "$HOST:$REMOTE_DIR/"

echo "Running C9.5 adapter self-test on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail

ADAPTER="$REMOTE_DIR/totem_wifi_nm_adapter.py"
SELF_TEST_OUT="$REMOTE_OUT_DIR/self-test"

umask 077
chmod 700 "$REMOTE_DIR" "$REMOTE_OUT_DIR"
python3 "$ADAPTER" --self-test --out-dir "$SELF_TEST_OUT"

echo "remote C9.5 prepare checks: ok"
REMOTE_PREP

if [ "$MODE" = "prepare-only" ]; then
  echo "C9.5 prepare-only complete. Evidence dir reserved: $REMOTE_OUT_DIR"
  exit 0
fi

echo "Running C9.5 $MODE on the board without operational changes"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' TIMEOUT_SEC='$TIMEOUT_SEC' MODE='$MODE' bash -s" <<'REMOTE_RUN'
set -euo pipefail

ADAPTER="$REMOTE_DIR/totem_wifi_nm_adapter.py"
RUN_OUT="$REMOTE_OUT_DIR/$MODE"
STDOUT_JSON="$RUN_OUT/stdout.json"
SERVICE_STATUS="$RUN_OUT/service-status.json"

umask 077
mkdir -p "$RUN_OUT"
chmod 700 "$RUN_OUT"

if [ "$MODE" = "read-only" ]; then
  python3 "$ADAPTER" --read-only --timeout-sec "$TIMEOUT_SEC" --out-dir "$RUN_OUT" >"$STDOUT_JSON"
elif [ "$MODE" = "plan" ]; then
  python3 "$ADAPTER" --plan --timeout-sec "$TIMEOUT_SEC" --out-dir "$RUN_OUT" >"$STDOUT_JSON"
else
  echo "error: unsupported remote mode" >&2
  exit 2
fi
chmod 600 "$STDOUT_JSON"

SERVICE_ACTIVE="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
SERVICE_ENABLED="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"
NRESTARTS="$(systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null || true)"
python3 - "$SERVICE_STATUS" "$SERVICE_ACTIVE" "$SERVICE_ENABLED" "$NRESTARTS" <<'PY'
import json
import os
import pathlib
import stat
import sys

path = pathlib.Path(sys.argv[1])
payload = {
    "service_active": sys.argv[2] or "unknown",
    "service_enabled": sys.argv[3] or "unknown",
    "nrestarts": sys.argv[4] or "unknown",
    "service_changed": False,
    "network_changed": False,
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "player_changed_by_runner": False,
    "mpv_changed_by_runner": False,
}
tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, path)
os.chmod(path, 0o600)
assert stat.S_IMODE(path.stat().st_mode) == 0o600
PY

python3 - "$RUN_OUT" "$MODE" <<'PY'
import json
import pathlib
import stat
import sys

run_out = pathlib.Path(sys.argv[1])
mode = sys.argv[2]
expected = ["status.json", "summary.txt", "stdout.json", "service-status.json"]
if mode == "plan":
    expected.append("plan.json")
assert stat.S_IMODE(run_out.stat().st_mode) == 0o700
for name in expected:
    path = run_out / name
    assert path.exists(), name
    assert stat.S_IMODE(path.stat().st_mode) == 0o600, name

status = json.loads((run_out / "status.json").read_text(encoding="utf-8"))
assert status["privacy_flags"]["network_changed"] is False
assert status["privacy_flags"]["credentials_collected"] is False
assert status["privacy_flags"]["ssid_written"] is False
assert status["privacy_flags"]["password_written"] is False
assert status["privacy_flags"]["ip_written"] is False
assert status["privacy_flags"]["mac_written"] is False
assert status["privacy_flags"]["dns_written"] is False
assert status["privacy_flags"]["nmcli_modify_called"] is False
assert status["privacy_flags"]["writer_called"] is False
assert status["privacy_flags"]["real_config_read"] is False
assert status["privacy_flags"]["real_config_written"] is False
if mode == "plan":
    plan = json.loads((run_out / "plan.json").read_text(encoding="utf-8"))
    assert plan["apply_enabled"] is False
    assert plan["target_network"] == "redacted"
    assert plan["credentials_source"] == "not_collected_in_c9_5"

print(f"remote C9.5 {mode}: ok")
PY
REMOTE_RUN
