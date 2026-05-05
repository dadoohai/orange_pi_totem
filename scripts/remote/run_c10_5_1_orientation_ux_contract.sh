#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
REMOTE_TTY="${REMOTE_TTY:-2}"
RUN_TIMEOUT_SEC="${RUN_TIMEOUT_SEC:-1800}"
PREVIEW_SEC="${PREVIEW_SEC:-14}"
REMOTE_DIR="${REMOTE_DIR:-/tmp/dadooh-c10-5-1}"
REMOTE_OUT_DIR="${REMOTE_OUT_DIR:-/tmp/dadooh-c10-5-1-orientation-ux-contract}"
REMOTE_WIZARD_OUT_DIR="${REMOTE_WIZARD_OUT_DIR:-/tmp/dadooh-c10-5-1-visual-wizard}"
PROFILE_NAME="${PROFILE_NAME:-dadooh-c9-8-wifi-persistent}"
PAUSE_CONFIRM_PHRASE="${PAUSE_CONFIRM_PHRASE:-CONFIRMO C10.5.1 ORIENTATION UX COM PAUSA DO PLAYER}"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_5_1_orientation_ux_contract.sh <host> [mode] [--tty N] [--timeout-sec N]

Modes:
  --prepare-only
      Copy scripts to /tmp and run self-tests. Does not touch service, Wi-Fi or config.

  --preview-orientation-flow
      Requires confirmation. Pauses player, previews orientation flow, restores service.

  --run-cancel
      Requires confirmation. Pauses player, opens wizard, expects cancel, restores service.

  --run-complete-portrait
      Requires confirmation. Pauses player, expects a completed candidate with portrait rotation.

  --run-complete-landscape
      Requires confirmation. Pauses player, expects a completed candidate with landscape rotation.

  --preview-splash-orientations
      Requires confirmation. Pauses player, renders public splash in 0/90/270/180, restores service.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only)
      MODE="prepare-only"
      ;;
    --preview-orientation-flow)
      MODE="preview-orientation-flow"
      ;;
    --run-cancel)
      MODE="run-cancel"
      ;;
    --run-complete-portrait)
      MODE="run-complete-portrait"
      ;;
    --run-complete-landscape)
      MODE="run-complete-landscape"
      ;;
    --preview-splash-orientations)
      MODE="preview-splash-orientations"
      ;;
    --tty)
      shift
      REMOTE_TTY="${1:-}"
      ;;
    --timeout-sec)
      shift
      RUN_TIMEOUT_SEC="${1:-}"
      ;;
    --preview-sec)
      shift
      PREVIEW_SEC="${1:-}"
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
  prepare-only|preview-orientation-flow|run-cancel|run-complete-portrait|run-complete-landscape|preview-splash-orientations)
    ;;
  *)
    echo "error: unsupported mode $MODE" >&2
    exit 2
    ;;
esac

if [ -z "$HOST" ]; then
  echo "error: host is required; pass it explicitly, for example root@<board-host>" >&2
  exit 2
fi

case "$REMOTE_TTY" in
  ''|*[!0-9]*|0)
    echo "error: --tty must be a positive integer" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BASE_RUNNER="$SCRIPT_DIR/run_c10_5_visual_boot_rotation.sh"
SPLASH="$REPO_ROOT/scripts/board/totem_visual_splash.py"

confirm_exact() {
  local expected="$1"
  local prompt="$2"
  echo "$prompt"
  echo "Type exactly: $expected"
  IFS= read -r typed
  if [ "$typed" != "$expected" ]; then
    echo "confirmation_mismatch" >&2
    exit 4
  fi
}

base_runner() {
  env \
    REMOTE_DIR="$REMOTE_DIR" \
    REMOTE_OUT_DIR="$REMOTE_OUT_DIR" \
    REMOTE_WIZARD_OUT_DIR="$REMOTE_WIZARD_OUT_DIR" \
    REMOTE_TTY="$REMOTE_TTY" \
    RUN_TIMEOUT_SEC="$RUN_TIMEOUT_SEC" \
    PREVIEW_SEC="$PREVIEW_SEC" \
    PROFILE_NAME="$PROFILE_NAME" \
    PAUSE_CONFIRM_PHRASE="$PAUSE_CONFIRM_PHRASE" \
    "$BASE_RUNNER" "$HOST" "$@"
}

validate_latest_rotation() {
  local expected_kind="$1"
  ssh "$HOST" "REMOTE_OUT_DIR='$REMOTE_OUT_DIR' EXPECTED_KIND='$expected_kind' bash -s" <<'REMOTE_VALIDATE'
set -euo pipefail
python3 - "$REMOTE_OUT_DIR/run-complete-existing-wifi/final-status.json" "$EXPECTED_KIND" <<'PY'
import json
import pathlib
import sys
status_path = pathlib.Path(sys.argv[1])
expected_kind = sys.argv[2]
if not status_path.exists():
    raise SystemExit("final_status_missing")
data = json.loads(status_path.read_text(encoding="utf-8"))
rotation = data.get("rotation_degrees")
if expected_kind == "portrait" and rotation not in (90, 270):
    raise SystemExit("portrait_rotation_not_observed")
if expected_kind == "landscape" and rotation not in (0, 180):
    raise SystemExit("landscape_rotation_not_observed")
if data.get("real_config_written") is not False or data.get("writer_called") is not False:
    raise SystemExit("guardrail_violation")
print(json.dumps({
    "rotation_degrees": rotation,
    "expected_kind": expected_kind,
    "validation_result": "passed",
    "real_config_written": False,
    "writer_called": False,
}, indent=2, sort_keys=True))
PY
REMOTE_VALIDATE
}

preview_splash_orientations() {
  confirm_exact "$PAUSE_CONFIRM_PHRASE" "HDMI/tela e teclado local devem estar conectados. O player sera pausado temporariamente."
  if [ ! -f "$SPLASH" ]; then
    echo "error: missing splash script" >&2
    exit 1
  fi
  ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR/splash-orientations' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR' '$REMOTE_OUT_DIR/splash-orientations'"
  scp "$SPLASH" "$HOST:$REMOTE_DIR/"
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_TTY='$REMOTE_TTY' PREVIEW_SEC='$PREVIEW_SEC' bash -s" <<'REMOTE_SPLASH'
set -euo pipefail
SPLASH="$REMOTE_DIR/totem_visual_splash.py"
RUN_OUT="$REMOTE_OUT_DIR/splash-orientations"
TTY_DEVICE="/dev/tty$REMOTE_TTY"
INITIAL_ACTIVE="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
INITIAL_ENABLED="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"
restore_service() {
  if [ "$INITIAL_ENABLED" = "enabled" ]; then
    systemctl enable kiosky-player.service >/dev/null 2>&1 || true
  fi
  if [ "$INITIAL_ACTIVE" = "active" ] || [ "$INITIAL_ENABLED" = "enabled" ]; then
    systemctl start kiosky-player.service >/dev/null 2>&1 || true
  fi
}
trap 'restore_service' EXIT INT TERM HUP
systemctl stop kiosky-player.service >/dev/null 2>&1 || true
command -v chvt >/dev/null 2>&1 && chvt "$REMOTE_TTY" >/dev/null 2>&1 || true
for rotation in 0 90 270 180; do
  env TERM=linux python3 "$SPLASH" preparing \
    --rotation-deg "$rotation" \
    --status-out "$RUN_OUT/splash-$rotation-status.json" \
    <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
  sleep 2
done
python3 - "$RUN_OUT/final-status.json" <<'PY'
import json
import os
import pathlib
import stat
import sys
target = pathlib.Path(sys.argv[1])
items = []
for path in sorted(target.parent.glob("splash-*-status.json")):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    items.append({
        "rotation_deg": data.get("rotation_deg", "unknown"),
        "layout_mode": data.get("layout_mode", "unknown"),
        "orientation_contract_supported": data.get("orientation_contract_supported", False),
    })
payload = {
    "schema_version": "dadooh-c10.5.1-splash-orientation-preview.v1",
    "validation_result": "previewed",
    "items": items,
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "wifi_changed": False,
    "network_identifiers_published": False,
    "raw_logs_written": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
REMOTE_SPLASH
}

case "$MODE" in
  prepare-only)
    base_runner --prepare-only
    ;;
  preview-orientation-flow)
    base_runner --preview-orientation-flow
    ;;
  run-cancel)
    base_runner --run-cancel
    ;;
  run-complete-portrait)
    echo "Complete o wizard escolhendo uma orientacao em retrato."
    base_runner --run-complete-existing-wifi
    validate_latest_rotation "portrait"
    ;;
  run-complete-landscape)
    echo "Complete o wizard escolhendo uma orientacao em paisagem."
    base_runner --run-complete-existing-wifi
    validate_latest_rotation "landscape"
    ;;
  preview-splash-orientations)
    preview_splash_orientations
    ;;
esac

echo "C10.5.1 orientation UX contract mode complete: $MODE"
