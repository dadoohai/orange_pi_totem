#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-root@192.168.18.115}"
REMOTE_DIR="/tmp/dadooh-c8-1"
REMOTE_OUT_DIR="/tmp/dadooh-c8-1-setup-minimo"
REMOTE_PORT="${C8_1_REMOTE_PORT:-8766}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_SERVER="$REPO_ROOT/scripts/board/totem_setup_minimal_server.py"
LOCAL_CONTRACT="$REPO_ROOT/scripts/board/totem_config_contract_validate.py"

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

echo "Copying C8.1 server and C5.1 validator to $HOST:$REMOTE_DIR"
scp "$LOCAL_SERVER" "$LOCAL_CONTRACT" "$HOST:$REMOTE_DIR/"

echo "Running C8.1 self-test and smoke test on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_PORT='$REMOTE_PORT' bash -s" <<'REMOTE_SH'
set -euo pipefail

SERVER="$REMOTE_DIR/totem_setup_minimal_server.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
STDOUT_FILE="$REMOTE_DIR/server.stdout"
STDERR_FILE="$REMOTE_DIR/server.stderr"
PID_FILE="$REMOTE_DIR/server.pid"

cleanup() {
  if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "${pid:-}" ] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  fi
}
trap cleanup EXIT INT TERM

umask 077
mkdir -p "$REMOTE_DIR"
chmod 700 "$REMOTE_DIR"
rm -rf "$REMOTE_OUT_DIR"

python3 "$CONTRACT" --self-test
python3 "$SERVER" --self-test

python3 "$SERVER" \
  --bind 127.0.0.1 \
  --port "$REMOTE_PORT" \
  --out-dir "$REMOTE_OUT_DIR" >"$STDOUT_FILE" 2>"$STDERR_FILE" &
server_pid="$!"
echo "$server_pid" >"$PID_FILE"

python3 - <<'PY'
import json
import os
import pathlib
import stat
import time
import urllib.error
import urllib.request

port = os.environ["REMOTE_PORT"]
out_dir = pathlib.Path(os.environ["REMOTE_OUT_DIR"])
base = f"http://127.0.0.1:{port}"
environment_id = "ENV-C8-1-REMOTE-MOCK"

last_error = None
for _ in range(40):
    try:
        html = urllib.request.urlopen(base, timeout=1).read().decode("utf-8")
        if "Configuracao pendente" not in html:
            raise AssertionError("HTML did not contain expected public text")
        break
    except Exception as exc:
        last_error = exc
        time.sleep(0.25)
else:
    raise AssertionError(f"server did not become ready: {last_error}")

payload = json.dumps({"environment_id": environment_id, "rotation": 90}).encode("utf-8")
request = urllib.request.Request(
    base + "/api/candidate",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
response = json.loads(urllib.request.urlopen(request, timeout=5).read().decode("utf-8"))
if response.get("ok") is not True:
    raise AssertionError(f"candidate request failed: {response}")

expected = {
    "candidate-config.json",
    "status.json",
    "summary.txt",
}
actual = {path.name for path in out_dir.iterdir() if path.is_file()}
if expected - actual:
    raise AssertionError(f"missing artifacts: {sorted(expected - actual)}")

if stat.S_IMODE(out_dir.stat().st_mode) != 0o700:
    raise AssertionError("out-dir mode is not 0700")

for name in expected:
    path = out_dir / name
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise AssertionError(f"{name} mode is not 0600")
    resolved = path.resolve(strict=True)
    if not str(resolved).startswith("/tmp/"):
        raise AssertionError(f"{name} escaped /tmp")
    if str(resolved).startswith("/data/") or str(resolved).startswith("/opt/"):
        raise AssertionError(f"{name} was written outside /tmp")

combined = (out_dir / "status.json").read_text(encoding="utf-8") + "\n" + (
    out_dir / "summary.txt"
).read_text(encoding="utf-8")
if environment_id in combined:
    raise AssertionError("status/summary leaked raw environment_id")
for forbidden in (
    "API_KEY_MOCK_NOT_FOR_PRODUCTION",
    "https://api.example.invalid/search",
):
    if forbidden in combined:
        raise AssertionError("status/summary leaked placeholder credential or URL")

status = json.loads((out_dir / "status.json").read_text(encoding="utf-8"))
guardrails = status["guardrails"]
if guardrails["data_written"] is not False:
    raise AssertionError("status did not keep data_written=false")
if guardrails["opt_written"] is not False:
    raise AssertionError("status did not keep opt_written=false")
if guardrails["systemctl_called"] is not False:
    raise AssertionError("status did not keep systemctl_called=false")
if guardrails["nmcli_called"] is not False:
    raise AssertionError("status did not keep nmcli_called=false")
if guardrails["mpv_called"] is not False:
    raise AssertionError("status did not keep mpv_called=false")

candidate = json.loads((out_dir / "candidate-config.json").read_text(encoding="utf-8"))
if candidate.get("rotation_deg") != 90:
    raise AssertionError("candidate did not use rotation_deg=90")
if "display_rotation_degrees" in candidate:
    raise AssertionError("candidate kept legacy rotation field")

print("remote smoke: ok")
PY

python3 "$CONTRACT" \
  --candidate "$REMOTE_OUT_DIR/candidate-config.json" \
  --allow-mock \
  --out-dir "$REMOTE_DIR/contract-allow-mock"

if python3 "$CONTRACT" \
  --candidate "$REMOTE_OUT_DIR/candidate-config.json" \
  --real-dry-run \
  --out-dir "$REMOTE_DIR/contract-real-dry-run"; then
  echo "error: C8.1 candidate unexpectedly passed real-dry-run" >&2
  exit 1
fi

cleanup
if kill -0 "$server_pid" >/dev/null 2>&1; then
  echo "error: server still running after cleanup" >&2
  exit 1
fi

echo "remote artifacts:"
echo "$REMOTE_DIR"
echo "$REMOTE_OUT_DIR"
REMOTE_SH
