#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-root@192.168.18.115}"
REMOTE_DIR="/tmp/dadooh-c9-1"
REMOTE_OUT_DIR="/tmp/dadooh-c9-1-local-wizard"
REMOTE_CONTRACT_ALLOW_OUT_DIR="/tmp/dadooh-c9-1-contract-allow-mock"
REMOTE_CONTRACT_REAL_OUT_DIR="/tmp/dadooh-c9-1-contract-real-dry-run"

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

echo "Copying C9.1 local wizard and dependencies to $HOST:$REMOTE_DIR"
scp "$LOCAL_WIZARD" "$LOCAL_SERVER" "$LOCAL_CONTRACT" "$HOST:$REMOTE_DIR/"

echo "Running C9.1 local wizard smoke test on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_CONTRACT_ALLOW_OUT_DIR='$REMOTE_CONTRACT_ALLOW_OUT_DIR' REMOTE_CONTRACT_REAL_OUT_DIR='$REMOTE_CONTRACT_REAL_OUT_DIR' bash -s" <<'REMOTE_SH'
set -euo pipefail

WIZARD="$REMOTE_DIR/totem_setup_local_wizard.py"
SERVER="$REMOTE_DIR/totem_setup_minimal_server.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
PROCESS_BEFORE="$REMOTE_DIR/process-before.json"
PROCESS_AFTER="$REMOTE_DIR/process-after.json"

umask 077
mkdir -p "$REMOTE_DIR"
chmod 700 "$REMOTE_DIR"
rm -rf "$REMOTE_OUT_DIR"
rm -rf "$REMOTE_CONTRACT_ALLOW_OUT_DIR"
rm -rf "$REMOTE_CONTRACT_REAL_OUT_DIR"

snapshot_player_processes() {
  python3 - <<'PY'
import json
import pathlib

snapshot = []
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
        snapshot.append({"pid": int(proc.name), "category": "mpv"})
    elif "kiosk.py" in lower or "kiosky-player" in lower:
        snapshot.append({"pid": int(proc.name), "category": "kiosky-player"})
print(json.dumps(sorted(snapshot, key=lambda item: (item["category"], item["pid"])), sort_keys=True))
PY
}

snapshot_player_processes >"$PROCESS_BEFORE"

python3 "$CONTRACT" --self-test
python3 "$SERVER" --self-test
python3 "$WIZARD" --self-test

python3 "$WIZARD" \
  --scripted \
  --environment-key loja-a \
  --rotation-key portrait_left \
  --out-dir "$REMOTE_OUT_DIR"

python3 "$CONTRACT" \
  --candidate "$REMOTE_OUT_DIR/candidate-config.json" \
  --allow-mock \
  --out-dir "$REMOTE_CONTRACT_ALLOW_OUT_DIR"

if python3 "$CONTRACT" \
  --candidate "$REMOTE_OUT_DIR/candidate-config.json" \
  --real-dry-run \
  --out-dir "$REMOTE_CONTRACT_REAL_OUT_DIR"; then
  echo "error: real-dry-run unexpectedly passed for mock/local C9.1 candidate" >&2
  exit 1
else
  rc="$?"
  if [ "$rc" -ne 2 ]; then
    echo "error: real-dry-run failed with unexpected exit code $rc" >&2
    exit "$rc"
  fi
fi

python3 - <<'PY'
import json
import os
import pathlib
import stat

out_dir = pathlib.Path(os.environ["REMOTE_OUT_DIR"])
allow_out_dir = pathlib.Path(os.environ["REMOTE_CONTRACT_ALLOW_OUT_DIR"])
real_out_dir = pathlib.Path(os.environ["REMOTE_CONTRACT_REAL_OUT_DIR"])
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

candidate = json.loads((out_dir / "candidate-config.json").read_text(encoding="utf-8"))
status = json.loads((out_dir / "status.json").read_text(encoding="utf-8"))
combined = (out_dir / "status.json").read_text(encoding="utf-8") + "\n" + (
    out_dir / "summary.txt"
).read_text(encoding="utf-8")

if status["schema_version"] != "dadooh-c9.1-local-setup-wizard.v1":
    raise AssertionError("C9.1 status schema mismatch")
if status["state"] != "candidate_ready":
    raise AssertionError("wizard did not generate candidate_ready status")
if status["interface"]["mode"] != "local_hdmi_keyboard_controlled":
    raise AssertionError("wizard status did not record local interface")
if status["interface"]["free_shell_available"] is not False:
    raise AssertionError("wizard status did not keep free_shell_available=false")
if status["interface"]["chromium_used"] is not False:
    raise AssertionError("wizard status did not keep chromium_used=false")
if status["contract_validation"]["allow_mock"]["valid"] is not True:
    raise AssertionError("wizard status did not record allow-mock pass")
if status["contract_validation"]["real_dry_run_expected_failure"] is not True:
    raise AssertionError("wizard status did not mark expected real-dry-run failure")

if candidate.get("environment_id") != "ENV-MOCK-LOJA-A":
    raise AssertionError("wizard candidate did not use selected mock environment")
if candidate.get("rotation_deg") != 270:
    raise AssertionError("wizard candidate did not preserve selected rotation")
if candidate.get("setup_source") != "c9.1-local-wizard-hdmi-keyboard-no-wifi":
    raise AssertionError("wizard candidate did not record C9.1 setup_source")
if candidate.get("setup_interface") != "local_hdmi_keyboard_controlled":
    raise AssertionError("wizard candidate did not record local setup interface")
if "display_rotation_degrees" in candidate:
    raise AssertionError("wizard candidate kept legacy rotation field")

for key in (
    "real_config_read",
    "real_config_written",
    "writer_called",
    "data_written",
    "opt_written",
    "commands_executed",
    "systemctl_called",
    "service_changed",
    "player_started",
    "player_stopped",
    "mpv_called",
    "network_external_access",
    "nmcli_called",
    "network_changed",
    "wifi_changed",
    "hotspot_created",
):
    if status["guardrails"][key] is not False:
        raise AssertionError(f"wizard guardrail {key} was not false")

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

allow_status = json.loads((allow_out_dir / "validation-status.json").read_text(encoding="utf-8"))
real_status = json.loads((real_out_dir / "validation-status.json").read_text(encoding="utf-8"))
if allow_status["valid"] is not True:
    raise AssertionError("C5.1 allow-mock did not pass for C9.1 candidate")
if real_status["valid"] is not False:
    raise AssertionError("C5.1 real-dry-run did not fail as expected for C9.1 candidate")
if not real_status["placeholder_findings"]:
    raise AssertionError("C5.1 real-dry-run did not record placeholder findings")

for validation_dir in (allow_out_dir, real_out_dir):
    if stat.S_IMODE(validation_dir.stat().st_mode) != 0o700:
        raise AssertionError(f"{validation_dir} mode is not 0700")
    for name in ("validation-status.json", "summary.txt"):
        path = validation_dir / name
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise AssertionError(f"{path} mode is not 0600")
        resolved = path.resolve(strict=True)
        if not str(resolved).startswith("/tmp/"):
            raise AssertionError(f"{path} escaped /tmp")
PY

snapshot_player_processes >"$PROCESS_AFTER"
if ! cmp -s "$PROCESS_BEFORE" "$PROCESS_AFTER"; then
  echo "error: player or MPV process snapshot changed during C9.1 smoke" >&2
  echo "before: $(cat "$PROCESS_BEFORE")" >&2
  echo "after: $(cat "$PROCESS_AFTER")" >&2
  exit 1
fi

echo "remote C9.1 smoke: ok"
REMOTE_SH
