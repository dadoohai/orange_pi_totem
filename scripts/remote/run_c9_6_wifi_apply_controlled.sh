#!/usr/bin/env bash
set -euo pipefail

HOST="root@192.168.1.147"
MODE="prepare-only"
REMOTE_DIR="/tmp/dadooh-c9-6-wifi"
REMOTE_OUT_DIR="/tmp/dadooh-c9-6-wifi-apply"
TIMEOUT_SEC="15"
PROFILE_NAME="dadooh-c9-6-wifi-test"
SECRETS_FILE=""
ALLOW_SSH_RISK="false"

CONFIRM_PHRASE="CONFIRMO APPLY WIFI REAL C9.6 EM BANCADA"

usage() {
  cat <<'USAGE'
Usage:
  run_c9_6_wifi_apply_controlled.sh [host] [--prepare-only|--preflight-apply|--apply-rollback-after-test|--apply-keep-profile] [options]

Options:
  --timeout-sec N
  --profile-name NAME
  --secrets-file PATH
  --allow-ssh-risk-with-local-console-confirmed

Modes:
  --prepare-only
      Copy the adapter to /tmp and run self-test only. Does not alter network.

  --preflight-apply
      Run sanitized preflight for real apply. Does not alter network.

  --apply-rollback-after-test
      Requires exact human confirmation and a restricted temporary secrets file.
      Attempts the dedicated Wi-Fi profile and rolls it back after the test.

  --apply-keep-profile
      Optional mode. Requires exact human confirmation and keeps only the
      dedicated product profile after successful apply.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only)
      MODE="prepare-only"
      ;;
    --preflight-apply)
      MODE="preflight-apply"
      ;;
    --apply-rollback-after-test)
      MODE="apply-rollback-after-test"
      ;;
    --apply-keep-profile)
      MODE="apply-keep-profile"
      ;;
    --timeout-sec)
      shift
      if [ "$#" -eq 0 ]; then
        echo "error: --timeout-sec requires a number" >&2
        exit 2
      fi
      TIMEOUT_SEC="$1"
      ;;
    --profile-name)
      shift
      if [ "$#" -eq 0 ]; then
        echo "error: --profile-name requires a value" >&2
        exit 2
      fi
      PROFILE_NAME="$1"
      ;;
    --secrets-file)
      shift
      if [ "$#" -eq 0 ]; then
        echo "error: --secrets-file requires a path" >&2
        exit 2
      fi
      SECRETS_FILE="$1"
      ;;
    --allow-ssh-risk-with-local-console-confirmed)
      ALLOW_SSH_RISK="true"
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
  prepare-only|preflight-apply|apply-rollback-after-test|apply-keep-profile)
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
  echo "error: missing adapter" >&2
  exit 1
fi

echo "Preparing C9.6 Wi-Fi workspace on $HOST"
ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR'"

echo "Copying C9.6 Wi-Fi adapter to temporary board workspace"
scp "$LOCAL_ADAPTER" "$HOST:$REMOTE_DIR/"

echo "Running C9.6 adapter self-test on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail

ADAPTER="$REMOTE_DIR/totem_wifi_nm_adapter.py"
SELF_TEST_OUT="$REMOTE_OUT_DIR/self-test"

umask 077
chmod 700 "$REMOTE_DIR" "$REMOTE_OUT_DIR"
python3 "$ADAPTER" --self-test --out-dir "$SELF_TEST_OUT"

echo "remote C9.6 prepare checks: ok"
REMOTE_PREP

if [ "$MODE" = "prepare-only" ]; then
  echo "C9.6 prepare-only complete. Evidence dir reserved: $REMOTE_OUT_DIR"
  exit 0
fi

if [ "$MODE" = "apply-rollback-after-test" ] || [ "$MODE" = "apply-keep-profile" ]; then
  if [ -z "$SECRETS_FILE" ]; then
    echo "error: apply requires --secrets-file pointing to a restricted temporary file on the board" >&2
    exit 2
  fi
  echo
  echo "Before real Wi-Fi apply, type exactly:"
  echo "$CONFIRM_PHRASE"
  printf '> '
  IFS= read -r AUTH_TEXT
  if [ "$AUTH_TEXT" != "$CONFIRM_PHRASE" ]; then
    echo "Authorization text did not match. Aborting before apply." >&2
    exit 20
  fi
fi

echo "Running C9.6 $MODE on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' TIMEOUT_SEC='$TIMEOUT_SEC' MODE='$MODE' PROFILE_NAME='$PROFILE_NAME' SECRETS_FILE='$SECRETS_FILE' ALLOW_SSH_RISK='$ALLOW_SSH_RISK' CONFIRM_PHRASE='$CONFIRM_PHRASE' bash -s" <<'REMOTE_RUN'
set -euo pipefail

ADAPTER="$REMOTE_DIR/totem_wifi_nm_adapter.py"
RUN_OUT="$REMOTE_OUT_DIR/$MODE"
STDOUT_JSON="$RUN_OUT/stdout.json"
FINAL_STATUS="$RUN_OUT/final-status.json"

umask 077
mkdir -p "$RUN_OUT"
chmod 700 "$RUN_OUT"

ALLOW_ARGS=()
if [ "$ALLOW_SSH_RISK" = "true" ]; then
  ALLOW_ARGS=(--allow-ssh-risk-with-local-console-confirmed)
fi

if [ "$MODE" = "preflight-apply" ]; then
  python3 "$ADAPTER" \
    --preflight-apply \
    --timeout-sec "$TIMEOUT_SEC" \
    --profile-name "$PROFILE_NAME" \
    --out-dir "$RUN_OUT" \
    "${ALLOW_ARGS[@]}" >"$STDOUT_JSON"
elif [ "$MODE" = "apply-rollback-after-test" ]; then
  python3 "$ADAPTER" \
    --apply \
    --enable-real-apply \
    --confirm-real-wifi-apply "$CONFIRM_PHRASE" \
    --secrets-file "$SECRETS_FILE" \
    --profile-name "$PROFILE_NAME" \
    --timeout-sec "$TIMEOUT_SEC" \
    --rollback-after-test \
    --out-dir "$RUN_OUT" \
    "${ALLOW_ARGS[@]}" >"$STDOUT_JSON"
elif [ "$MODE" = "apply-keep-profile" ]; then
  python3 "$ADAPTER" \
    --apply \
    --enable-real-apply \
    --confirm-real-wifi-apply "$CONFIRM_PHRASE" \
    --secrets-file "$SECRETS_FILE" \
    --profile-name "$PROFILE_NAME" \
    --timeout-sec "$TIMEOUT_SEC" \
    --keep-dedicated-profile \
    --out-dir "$RUN_OUT" \
    "${ALLOW_ARGS[@]}" >"$STDOUT_JSON"
else
  echo "error: unsupported remote mode" >&2
  exit 2
fi
chmod 600 "$STDOUT_JSON"

SERVICE_ACTIVE="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
SERVICE_ENABLED="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"
NRESTARTS="$(systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null || true)"

python3 - "$RUN_OUT" "$FINAL_STATUS" "$MODE" "$SERVICE_ACTIVE" "$SERVICE_ENABLED" "$NRESTARTS" <<'PY'
import json
import os
import pathlib
import stat
import sys

run_out = pathlib.Path(sys.argv[1])
final_status = pathlib.Path(sys.argv[2])
mode = sys.argv[3]

counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        raw = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "ignore").lower()
    except OSError:
        continue
    if "totem_setup_local_wizard.py" in raw:
        counts["setup"] += 1
    if "totem_status_renderer" in raw:
        counts["renderer"] += 1
    if "mpv" in raw:
        counts["mpv"] += 1
    if "kiosk.py" in raw:
        counts["player"] += 1

status_path = run_out / "status.json"
adapter_status = {}
if status_path.exists():
    adapter_status = json.loads(status_path.read_text(encoding="utf-8"))

payload = {
    "service_active": sys.argv[4] or "unknown",
    "service_enabled": sys.argv[5] or "unknown",
    "nrestarts": sys.argv[6] or "unknown",
    "process_counts": counts,
    "network_changed": bool(adapter_status.get("network_changed", False)),
    "rollback_status": adapter_status.get("rollback_status", "not_applicable"),
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "player_changed_by_runner": False,
    "mpv_changed_by_runner": False,
    "service_changed_by_runner": False,
    "mode": mode,
}
tmp = final_status.with_name(f".{final_status.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, final_status)
os.chmod(final_status, 0o600)

expected = ["status.json", "summary.txt", "stdout.json", "final-status.json"]
if mode == "preflight-apply":
    expected.append("preflight.json")
if mode.startswith("apply"):
    expected.append("preflight.json")
    if (run_out / "rollback.json").exists():
        expected.append("rollback.json")
assert stat.S_IMODE(run_out.stat().st_mode) == 0o700
for name in expected:
    path = run_out / name
    assert path.exists(), name
    assert stat.S_IMODE(path.stat().st_mode) == 0o600, name

print(f"remote C9.6 {mode}: ok")
PY
REMOTE_RUN
