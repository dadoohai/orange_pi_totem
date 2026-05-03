#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-root@192.168.18.115}"
REMOTE_DIR="/tmp/dadooh-c8"
REMOTE_OUT_DIR="/tmp/dadooh-c8-setup-minimo"
REMOTE_PREFLIGHT_OUT_DIR="/tmp/dadooh-c8-5-preflight"
REMOTE_REAL_SYNTHETIC_OUT_DIR="/tmp/dadooh-c8-5-1-real-synthetic"
REMOTE_PRIVATE_VALUES_DIR="/tmp/dadooh-c8-6-private"
REMOTE_PRIVATE_HANDOFF_OUT_DIR="/tmp/dadooh-c8-6-handoff-preflight"
REMOTE_PORT="${C8_REMOTE_PORT:-${C8_1_REMOTE_PORT:-8766}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_SERVER="$REPO_ROOT/scripts/board/totem_setup_minimal_server.py"
LOCAL_CONTRACT="$REPO_ROOT/scripts/board/totem_config_contract_validate.py"
LOCAL_PREFLIGHT="$REPO_ROOT/scripts/board/totem_setup_writer_preflight.py"
LOCAL_REAL_SYNTHETIC="$REPO_ROOT/scripts/board/totem_setup_real_synthetic_candidate.py"
LOCAL_PRIVATE_HANDOFF="$REPO_ROOT/scripts/board/totem_setup_private_handoff_preflight.py"

if [ ! -f "$LOCAL_SERVER" ]; then
  echo "error: missing $LOCAL_SERVER" >&2
  exit 1
fi
if [ ! -f "$LOCAL_CONTRACT" ]; then
  echo "error: missing $LOCAL_CONTRACT" >&2
  exit 1
fi
if [ ! -f "$LOCAL_PREFLIGHT" ]; then
  echo "error: missing $LOCAL_PREFLIGHT" >&2
  exit 1
fi
if [ ! -f "$LOCAL_REAL_SYNTHETIC" ]; then
  echo "error: missing $LOCAL_REAL_SYNTHETIC" >&2
  exit 1
fi
if [ ! -f "$LOCAL_PRIVATE_HANDOFF" ]; then
  echo "error: missing $LOCAL_PRIVATE_HANDOFF" >&2
  exit 1
fi

echo "Preparing $REMOTE_DIR on $HOST"
ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' && chmod 700 '$REMOTE_DIR'"

echo "Copying C8 setup server, C5.1 validator and C8.5/C8.6 scripts to $HOST:$REMOTE_DIR"
scp "$LOCAL_SERVER" "$LOCAL_CONTRACT" "$LOCAL_PREFLIGHT" "$LOCAL_REAL_SYNTHETIC" "$LOCAL_PRIVATE_HANDOFF" "$HOST:$REMOTE_DIR/"

echo "Running C8.6 self-test and smoke test on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_PREFLIGHT_OUT_DIR='$REMOTE_PREFLIGHT_OUT_DIR' REMOTE_REAL_SYNTHETIC_OUT_DIR='$REMOTE_REAL_SYNTHETIC_OUT_DIR' REMOTE_PRIVATE_VALUES_DIR='$REMOTE_PRIVATE_VALUES_DIR' REMOTE_PRIVATE_HANDOFF_OUT_DIR='$REMOTE_PRIVATE_HANDOFF_OUT_DIR' REMOTE_PORT='$REMOTE_PORT' bash -s" <<'REMOTE_SH'
set -euo pipefail

SERVER="$REMOTE_DIR/totem_setup_minimal_server.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
PREFLIGHT="$REMOTE_DIR/totem_setup_writer_preflight.py"
REAL_SYNTHETIC="$REMOTE_DIR/totem_setup_real_synthetic_candidate.py"
PRIVATE_HANDOFF="$REMOTE_DIR/totem_setup_private_handoff_preflight.py"
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
rm -rf "$REMOTE_PREFLIGHT_OUT_DIR"
rm -rf "$REMOTE_REAL_SYNTHETIC_OUT_DIR"
rm -rf "$REMOTE_PRIVATE_VALUES_DIR"
rm -rf "$REMOTE_PRIVATE_HANDOFF_OUT_DIR"

python3 "$CONTRACT" --self-test
python3 "$SERVER" --self-test
python3 "$PREFLIGHT" --self-test
python3 "$REAL_SYNTHETIC" --self-test
python3 "$PRIVATE_HANDOFF" --self-test

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
mock_environment_id = "ENV-MOCK-LOJA-A"
manual_environment_id = "ENV-MOCK-MANUAL-REMOTE"

last_error = None
for _ in range(40):
    try:
        html = urllib.request.urlopen(base, timeout=1).read().decode("utf-8")
        expected_text = (
            "Configuracao pendente",
            "Selecionar ambiente",
            "Orientacao da tela",
            "Paisagem",
            "Retrato - giro para direita",
            "Paisagem invertida",
            "Retrato - giro para esquerda",
            "Manutenção",
            "Ações de teste para suporte",
        )
        if any(text not in html for text in expected_text):
            raise AssertionError("HTML did not contain expected public text")
        break
    except Exception as exc:
        last_error = exc
        time.sleep(0.25)
else:
    raise AssertionError(f"server did not become ready: {last_error}")

expected = {"candidate-config.json", "status.json", "summary.txt"}
maintenance_expected = {"maintenance-action-status.json", "maintenance-summary.txt"}

maintenance_catalog = json.loads(
    urllib.request.urlopen(base + "/api/maintenance-actions", timeout=5).read().decode("utf-8")
)
if maintenance_catalog.get("ok") is not True:
    raise AssertionError("maintenance actions catalog failed")
action_labels = {item["label"] for item in maintenance_catalog["actions"]}
if {"Reiniciar exibição", "Limpar configuração de teste"} - action_labels:
    raise AssertionError("maintenance catalog did not expose expected actions")

def player_process_snapshot():
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
            snapshot.append((int(proc.name), "mpv"))
        elif "kiosk.py" in lower or "kiosky-player" in lower:
            snapshot.append((int(proc.name), "kiosky-player"))
    return sorted(snapshot)

player_processes_before = player_process_snapshot()

def submit_and_verify(payload_dict, expected_environment_id, expected_rotation, expected_mode, forbidden_names):
    payload = json.dumps(payload_dict).encode("utf-8")
    request = urllib.request.Request(
        base + "/api/candidate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    response = json.loads(urllib.request.urlopen(request, timeout=5).read().decode("utf-8"))
    if response.get("ok") is not True:
        raise AssertionError(f"candidate request failed: {response}")

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
    if expected_environment_id in combined:
        raise AssertionError("status/summary leaked raw environment_id")
    for forbidden in (
        "API_KEY_MOCK_NOT_FOR_PRODUCTION",
        "https://api.example.invalid/search",
        "api_key",
        "token",
        *forbidden_names,
    ):
        if forbidden.lower() in combined.lower():
            raise AssertionError(f"status/summary leaked forbidden text: {forbidden}")

    status = json.loads((out_dir / "status.json").read_text(encoding="utf-8"))
    if status["environment_selection"]["mode"] != expected_mode:
        raise AssertionError("status did not record expected environment mode")
    if status["contract_validation"]["allow_mock"]["valid"] is not True:
        raise AssertionError("status did not record allow-mock pass")
    if status["contract_validation"]["real_dry_run_expected_failure"] is not True:
        raise AssertionError("status did not record real-dry-run expected failure")

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
    if candidate.get("environment_id") != expected_environment_id:
        raise AssertionError("candidate did not contain expected environment_id")
    if candidate.get("rotation_deg") != expected_rotation:
        raise AssertionError("candidate did not use expected rotation_deg")
    if candidate.get("setup_environment_source") != expected_mode:
        raise AssertionError("candidate did not record expected environment source")
    if "display_rotation_degrees" in candidate:
        raise AssertionError("candidate kept legacy rotation field")

submit_and_verify(
    {"environment_mode": "mock", "environment_key": "loja-a", "rotation_key": "portrait_right"},
    mock_environment_id,
    90,
    "mock_list",
    ("Ambiente Loja A - TESTE",),
)

submit_and_verify(
    {"environment_mode": "manual", "environment_id": manual_environment_id, "rotation_key": "portrait_left"},
    manual_environment_id,
    270,
    "manual_advanced",
    ("Ambiente manual - TESTE",),
)

def post_json(path, payload_dict):
    payload = json.dumps(payload_dict).encode("utf-8")
    request = urllib.request.Request(
        base + path,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(request, timeout=5).read().decode("utf-8"))

def expect_bad_request(path, payload_dict, expected_error):
    payload = json.dumps(payload_dict).encode("utf-8")
    request = urllib.request.Request(
        base + path,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as exc:
        if exc.code != 400:
            raise AssertionError(f"expected HTTP 400, got {exc.code}") from exc
        body = json.loads(exc.read().decode("utf-8"))
        if body.get("ok") is not False:
            raise AssertionError(f"bad request response did not fail: {body}")
        if expected_error not in body.get("error", ""):
            raise AssertionError(f"unexpected bad request error: {body}")
        return
    raise AssertionError("request unexpectedly succeeded")

def forbidden_variants(value):
    return {value, json.dumps(value, ensure_ascii=True)[1:-1]}

def submit_maintenance(payload_dict, expected_action, confirmation_expected):
    response = post_json("/api/maintenance-action", payload_dict)
    if response.get("ok") is not True:
        raise AssertionError(f"maintenance request failed: {response}")
    if response.get("action") != expected_action:
        raise AssertionError("maintenance response action mismatch")
    if response.get("mock_only") is not True:
        raise AssertionError("maintenance response did not mark mock_only")

    actual = {path.name for path in out_dir.iterdir() if path.is_file()}
    if maintenance_expected - actual:
        raise AssertionError(f"missing maintenance artifacts: {sorted(maintenance_expected - actual)}")
    if stat.S_IMODE(out_dir.stat().st_mode) != 0o700:
        raise AssertionError("out-dir mode is not 0700 after maintenance action")

    for name in maintenance_expected:
        path = out_dir / name
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise AssertionError(f"{name} mode is not 0600")
        resolved = path.resolve(strict=True)
        if not str(resolved).startswith("/tmp/"):
            raise AssertionError(f"{name} escaped /tmp")
        if str(resolved).startswith("/data/") or str(resolved).startswith("/opt/"):
            raise AssertionError(f"{name} was written outside /tmp")

    status = json.loads((out_dir / "maintenance-action-status.json").read_text(encoding="utf-8"))
    if status["schema_version"] != "dadooh-c8.4.0-maintenance-action-mock-local.v1":
        raise AssertionError("maintenance status schema mismatch")
    if status["state"] != "maintenance_action_mock_recorded":
        raise AssertionError("maintenance status state mismatch")
    if status["action"]["id"] != expected_action:
        raise AssertionError("maintenance status action mismatch")
    if status["action"]["confirmation_received"] is not confirmation_expected:
        raise AssertionError("maintenance confirmation flag mismatch")
    if status["action"]["real_effect"] != "none":
        raise AssertionError("maintenance status did not keep real_effect none")

    guardrails = status["guardrails"]
    for key in (
        "real_config_read",
        "real_config_written",
        "data_written",
        "opt_written",
        "commands_executed",
        "systemctl_called",
        "service_changed",
        "player_process_changed",
        "player_restarted",
        "mpv_called",
        "backend_called",
        "nmcli_called",
        "network_changed",
        "reset_real_executed",
        "cache_deleted",
    ):
        if guardrails[key] is not False:
            raise AssertionError(f"maintenance guardrail {key} was not false")

    combined = (out_dir / "maintenance-action-status.json").read_text(encoding="utf-8") + "\n" + (
        out_dir / "maintenance-summary.txt"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "API_KEY_MOCK_NOT_FOR_PRODUCTION",
        "https://api.example.invalid/search",
        "api_key",
        "token",
        "secret",
        "password",
        "ssid",
        "hostname",
        "gateway",
        mock_environment_id,
        manual_environment_id,
    ):
        if forbidden.lower() in combined.lower():
            raise AssertionError(f"maintenance status/summary leaked forbidden text: {forbidden}")
    for variant in forbidden_variants("Entendo que esta é uma simulação e não apaga dados reais."):
        if variant in combined:
            raise AssertionError("maintenance status/summary leaked confirmation text")

submit_maintenance({"action": "restart_player_mock"}, "restart_player_mock", False)
submit_maintenance(
    {
        "action": "reset_config_mock",
        "confirmation": "Entendo que esta é uma simulação e não apaga dados reais.",
    },
    "reset_config_mock",
    True,
)
expect_bad_request("/api/maintenance-action", {"action": "reset_config_mock"}, "requires explicit simulation confirmation")
expect_bad_request("/api/maintenance-action", {"action": "factory_reset_real"}, "unknown maintenance action")

player_processes_after = player_process_snapshot()
if player_processes_after != player_processes_before:
    raise AssertionError("player or MPV process snapshot changed during mock maintenance smoke")

print("remote smoke: ok")
PY

python3 "$PREFLIGHT" \
  --candidate "$REMOTE_OUT_DIR/candidate-config.json" \
  --out-dir "$REMOTE_PREFLIGHT_OUT_DIR"

python3 - <<'PY'
import json
import os
import pathlib
import stat

out_dir = pathlib.Path(os.environ["REMOTE_PREFLIGHT_OUT_DIR"])
setup_out_dir = pathlib.Path(os.environ["REMOTE_OUT_DIR"])
expected = {"preflight-status.json", "summary.txt"}

if stat.S_IMODE(out_dir.stat().st_mode) != 0o700:
    raise AssertionError("preflight out-dir mode is not 0700")

actual = {path.name for path in out_dir.iterdir() if path.is_file()}
if expected - actual:
    raise AssertionError(f"missing preflight artifacts: {sorted(expected - actual)}")

for name in expected:
    path = out_dir / name
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise AssertionError(f"{name} mode is not 0600")
    resolved = path.resolve(strict=True)
    if not str(resolved).startswith("/tmp/"):
        raise AssertionError(f"{name} escaped /tmp")
    if str(resolved).startswith("/data/") or str(resolved).startswith("/opt/"):
        raise AssertionError(f"{name} was written outside /tmp")

status = json.loads((out_dir / "preflight-status.json").read_text(encoding="utf-8"))
if status["schema_version"] != "dadooh-c8.5.0-setup-writer-preflight.v1":
    raise AssertionError("preflight schema mismatch")
if status["result"] != "passed":
    raise AssertionError("preflight did not pass")
if status["contract_validation"]["allow_mock"]["valid"] is not True:
    raise AssertionError("preflight did not record allow-mock pass")
if status["contract_validation"]["real_dry_run"]["valid"] is not False:
    raise AssertionError("preflight did not record real-dry-run expected failure")
if status["contract_validation"]["real_dry_run_expected_failure"] is not True:
    raise AssertionError("preflight did not mark expected real-dry-run failure")
if status["writer_handoff"]["writer_real_write_blocked"] is not True:
    raise AssertionError("preflight did not block real writer")
if status["writer_handoff"]["writer_real_mode_called"] is not False:
    raise AssertionError("preflight called real writer mode")
if status["writer_handoff"]["writer_simulated_write_called"] is not False:
    raise AssertionError("preflight called simulated writer")

for key in (
    "real_config_read",
    "real_config_written",
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
    "backend_called",
    "wifi_changed",
    "private_values_used",
):
    if status["guardrails"][key] is not False:
        raise AssertionError(f"preflight guardrail {key} was not false")

candidate = json.loads((setup_out_dir / "candidate-config.json").read_text(encoding="utf-8"))
combined = (out_dir / "preflight-status.json").read_text(encoding="utf-8") + "\n" + (
    out_dir / "summary.txt"
).read_text(encoding="utf-8")
for value in candidate.values():
    if not isinstance(value, str) or not value:
        continue
    variants = {value, json.dumps(value, ensure_ascii=True)[1:-1]}
    if any(variant in combined for variant in variants):
        raise AssertionError("preflight status/summary leaked candidate value")

for forbidden in (
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
        raise AssertionError(f"preflight status/summary leaked forbidden marker: {forbidden}")
PY

python3 "$REAL_SYNTHETIC" \
  --source-candidate "$REMOTE_OUT_DIR/candidate-config.json" \
  --out-dir "$REMOTE_REAL_SYNTHETIC_OUT_DIR"

python3 "$CONTRACT" \
  --candidate "$REMOTE_REAL_SYNTHETIC_OUT_DIR/candidate-real-synthetic.json" \
  --real-dry-run \
  --out-dir "$REMOTE_DIR/contract-real-synthetic-real-dry-run"

python3 - <<'PY'
import json
import os
import pathlib
import stat

out_dir = pathlib.Path(os.environ["REMOTE_REAL_SYNTHETIC_OUT_DIR"])
setup_out_dir = pathlib.Path(os.environ["REMOTE_OUT_DIR"])
expected = {"candidate-real-synthetic.json", "real-synthetic-status.json", "summary.txt"}

if stat.S_IMODE(out_dir.stat().st_mode) != 0o700:
    raise AssertionError("real-synthetic out-dir mode is not 0700")

actual = {path.name for path in out_dir.iterdir() if path.is_file()}
if expected - actual:
    raise AssertionError(f"missing real-synthetic artifacts: {sorted(expected - actual)}")

for name in expected:
    path = out_dir / name
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise AssertionError(f"{name} mode is not 0600")
    resolved = path.resolve(strict=True)
    if not str(resolved).startswith("/tmp/"):
        raise AssertionError(f"{name} escaped /tmp")
    if str(resolved).startswith("/data/") or str(resolved).startswith("/opt/"):
        raise AssertionError(f"{name} was written outside /tmp")

source = json.loads((setup_out_dir / "candidate-config.json").read_text(encoding="utf-8"))
candidate = json.loads((out_dir / "candidate-real-synthetic.json").read_text(encoding="utf-8"))
status = json.loads((out_dir / "real-synthetic-status.json").read_text(encoding="utf-8"))

if status["schema_version"] != "dadooh-c8.5.1-real-synthetic-candidate.v1":
    raise AssertionError("real-synthetic schema mismatch")
if status["result"] != "passed":
    raise AssertionError("real-synthetic status did not pass")
if status["contract_validation"]["real_synthetic_real_dry_run"]["valid"] is not True:
    raise AssertionError("real-synthetic status did not record real-dry-run pass")
if status["contract_validation"]["placeholder_findings_cleared"] is not True:
    raise AssertionError("real-synthetic status did not clear placeholders")
if status["writer_handoff"]["writer_real_write_blocked"] is not True:
    raise AssertionError("real-synthetic did not block real writer")
if status["writer_handoff"]["writer_real_mode_called"] is not False:
    raise AssertionError("real-synthetic called real writer mode")
if status["writer_handoff"]["writer_simulated_write_called"] is not False:
    raise AssertionError("real-synthetic called simulated writer")
if candidate.get("rotation_deg") != source.get("rotation_deg"):
    raise AssertionError("real-synthetic candidate did not preserve rotation_deg")
for field in ("api_url", "api_key", "environment_id"):
    if candidate.get(field) == source.get(field):
        raise AssertionError(f"real-synthetic candidate did not replace {field}")
if candidate.get("station_id") != source.get("station_id"):
    raise AssertionError("real-synthetic candidate should preserve optional station_id")

for key in (
    "real_config_read",
    "real_config_written",
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
    "backend_called",
    "wifi_changed",
    "private_inputs_used",
):
    if status["guardrails"][key] is not False:
        raise AssertionError(f"real-synthetic guardrail {key} was not false")

combined = (out_dir / "real-synthetic-status.json").read_text(encoding="utf-8") + "\n" + (
    out_dir / "summary.txt"
).read_text(encoding="utf-8")
for value in list(source.values()) + list(candidate.values()):
    if not isinstance(value, str) or not value:
        continue
    if value in {
        source.get("setup_source"),
        source.get("setup_environment_source"),
        candidate.get("setup_source"),
        candidate.get("setup_environment_source"),
        candidate.get("setup_private_values_source"),
    }:
        continue
    variants = {value, json.dumps(value, ensure_ascii=True)[1:-1]}
    if any(variant in combined for variant in variants):
        raise AssertionError("real-synthetic status/summary leaked candidate value")

for forbidden in (
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
        raise AssertionError(f"real-synthetic status/summary leaked forbidden marker: {forbidden}")
PY

mkdir -p "$REMOTE_PRIVATE_VALUES_DIR"
chmod 700 "$REMOTE_PRIVATE_VALUES_DIR"
python3 - <<'PY'
import json
import os
import pathlib
import stat

private_dir = pathlib.Path(os.environ["REMOTE_PRIVATE_VALUES_DIR"])
path = private_dir / "private-values.json"
payload = {
    "api_url": "https://api.sandbox.localhost/search",
    "api_key": "B1C2D3E4F5061728394A5B6C7D8E9F01",
    "environment_id": "ENV-APPROVED-REMOTE",
}
with path.open("w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
    handle.write("\n")
path.chmod(0o600)
if stat.S_IMODE(private_dir.stat().st_mode) != 0o700:
    raise AssertionError("private values dir mode is not 0700")
if stat.S_IMODE(path.stat().st_mode) != 0o600:
    raise AssertionError("private values file mode is not 0600")
PY

service_state_before="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"

python3 "$PRIVATE_HANDOFF" \
  --source-candidate "$REMOTE_OUT_DIR/candidate-config.json" \
  --private-values "$REMOTE_PRIVATE_VALUES_DIR/private-values.json" \
  --out-dir "$REMOTE_PRIVATE_HANDOFF_OUT_DIR" \
  --confirm-private-values-approved

python3 "$CONTRACT" \
  --candidate "$REMOTE_PRIVATE_HANDOFF_OUT_DIR/candidate-private.json" \
  --real-dry-run \
  --out-dir "$REMOTE_DIR/contract-private-handoff-real-dry-run"

service_state_after="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
if [ "$service_state_after" != "$service_state_before" ]; then
  echo "error: service state changed during C8.6 preflight" >&2
  exit 1
fi

python3 - <<'PY'
import json
import os
import pathlib
import stat

out_dir = pathlib.Path(os.environ["REMOTE_PRIVATE_HANDOFF_OUT_DIR"])
setup_out_dir = pathlib.Path(os.environ["REMOTE_OUT_DIR"])
private_values_path = pathlib.Path(os.environ["REMOTE_PRIVATE_VALUES_DIR"]) / "private-values.json"
expected = {"candidate-private.json", "handoff-preflight-status.json", "summary.txt"}

if stat.S_IMODE(out_dir.stat().st_mode) != 0o700:
    raise AssertionError("private handoff out-dir mode is not 0700")

actual = {path.name for path in out_dir.iterdir() if path.is_file()}
if expected - actual:
    raise AssertionError(f"missing private handoff artifacts: {sorted(expected - actual)}")

for name in expected:
    path = out_dir / name
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise AssertionError(f"{name} mode is not 0600")
    resolved = path.resolve(strict=True)
    if not str(resolved).startswith("/tmp/"):
        raise AssertionError(f"{name} escaped /tmp")
    if str(resolved).startswith("/data/") or str(resolved).startswith("/opt/"):
        raise AssertionError(f"{name} was written outside /tmp")

source = json.loads((setup_out_dir / "candidate-config.json").read_text(encoding="utf-8"))
private_values = json.loads(private_values_path.read_text(encoding="utf-8"))
candidate = json.loads((out_dir / "candidate-private.json").read_text(encoding="utf-8"))
status = json.loads((out_dir / "handoff-preflight-status.json").read_text(encoding="utf-8"))

if status["schema_version"] != "dadooh-c8.6-private-handoff-preflight.v1":
    raise AssertionError("private handoff schema mismatch")
if status["result"] != "passed":
    raise AssertionError("private handoff status did not pass")
if status["authorization"]["private_values_source_approved_by_human"] is not True:
    raise AssertionError("private handoff did not record preflight approval")
if status["authorization"]["real_write_approved"] is not False:
    raise AssertionError("private handoff should not approve real write")
if status["contract_validation"]["private_real_dry_run"]["valid"] is not True:
    raise AssertionError("private handoff status did not record real-dry-run pass")
if status["contract_validation"]["placeholder_findings_cleared"] is not True:
    raise AssertionError("private handoff did not clear placeholders")
if status["writer_handoff"]["writer_real_write_blocked"] is not True:
    raise AssertionError("private handoff did not block real writer")
if status["writer_handoff"]["writer_real_mode_called"] is not False:
    raise AssertionError("private handoff called real writer mode")
if status["writer_handoff"]["enable_real_write_used"] is not False:
    raise AssertionError("private handoff used enable real write")
if candidate.get("rotation_deg") != source.get("rotation_deg"):
    raise AssertionError("private candidate did not preserve rotation_deg")
for field in ("api_url", "api_key", "environment_id"):
    if candidate.get(field) != private_values.get(field):
        raise AssertionError(f"private candidate did not apply {field}")
if candidate.get("station_id") != source.get("station_id"):
    raise AssertionError("private candidate should preserve optional station_id")

for key in (
    "real_config_read",
    "real_config_written",
    "data_written",
    "opt_written",
    "writer_real_mode_called",
    "enable_real_write_used",
    "systemctl_state_change_called",
    "service_changed",
    "player_started",
    "player_stopped",
    "mpv_called",
    "network_external_access",
    "nmcli_called",
    "backend_called",
    "wifi_changed",
):
    if status["guardrails"][key] is not False:
        raise AssertionError(f"private handoff guardrail {key} was not false")

combined = (out_dir / "handoff-preflight-status.json").read_text(encoding="utf-8") + "\n" + (
    out_dir / "summary.txt"
).read_text(encoding="utf-8")
for value in list(source.values()) + list(private_values.values()) + list(candidate.values()):
    if not isinstance(value, str) or not value:
        continue
    if value in {
        source.get("setup_source"),
        source.get("setup_environment_source"),
        candidate.get("setup_source"),
        candidate.get("setup_environment_source"),
        candidate.get("setup_private_values_source"),
    }:
        continue
    variants = {value, json.dumps(value, ensure_ascii=True)[1:-1]}
    if any(variant in combined for variant in variants):
        raise AssertionError("private handoff status/summary leaked private value")

for forbidden in (
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
        raise AssertionError(f"private handoff status/summary leaked forbidden marker: {forbidden}")
PY

python3 "$CONTRACT" \
  --candidate "$REMOTE_OUT_DIR/candidate-config.json" \
  --allow-mock \
  --out-dir "$REMOTE_DIR/contract-allow-mock"

if python3 "$CONTRACT" \
  --candidate "$REMOTE_OUT_DIR/candidate-config.json" \
  --real-dry-run \
  --out-dir "$REMOTE_DIR/contract-real-dry-run"; then
  echo "error: C8.4.0 candidate unexpectedly passed real-dry-run" >&2
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
