#!/usr/bin/env bash
set -euo pipefail

MODE="wait"
MARKER="/root/.not_logged_in_yet"
OUT_DIR="/run/dadooh-firstboot-gate"
REMOTE_TTY="2"
POLL_SEC="5"

usage() {
  cat <<'USAGE'
Usage:
  totem_firstboot_gate.sh [--wait|--status|--self-test]

Blocks Dadooh product services while the Armbian technical first-login marker
exists. This prevents the product wizard/F10 flow from competing with Armbian
first-login on image-lab boots. It does not configure users, passwords,
networking, config.json, writer or Wi-Fi.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --wait) MODE="wait" ;;
    --status) MODE="status" ;;
    --self-test) MODE="self-test" ;;
    --marker)
      shift
      MARKER="${1:-}"
      ;;
    --out-dir)
      shift
      OUT_DIR="${1:-}"
      ;;
    --tty)
      shift
      REMOTE_TTY="${1:-}"
      ;;
    --poll-sec)
      shift
      POLL_SEC="${1:-}"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "error: unsupported argument $1" >&2
      exit 2
      ;;
  esac
  shift
done

case "$OUT_DIR" in
  /run/*|/tmp/*) ;;
  *) echo "error: --out-dir must be under /run or /tmp" >&2; exit 2 ;;
esac
case "$REMOTE_TTY" in
  ''|*[!0-9]*|0) echo "error: --tty must be a positive integer" >&2; exit 2 ;;
esac
case "$POLL_SEC" in
  ''|*[!0-9]*|0) echo "error: --poll-sec must be a positive integer" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPLASH="$SCRIPT_DIR/totem_visual_splash.py"
TTY_DEVICE="/dev/tty$REMOTE_TTY"
STATUS_OUT="$OUT_DIR/status.json"

if [ "$MODE" = "self-test" ]; then
  bash -n "$0"
  printf 'self-test: ok\n'
  exit 0
fi

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR" 2>/dev/null || true

write_status() {
  local state="$1"
  python3 - "$STATUS_OUT" "$state" "$MARKER" <<'PY'
import json
import os
import pathlib
import sys
import time

target = pathlib.Path(sys.argv[1])
marker = pathlib.Path(sys.argv[3])
payload = {
    "schema_version": "dadooh-c12-image-lab-firstboot-gate.v1",
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "state": sys.argv[2],
    "armbian_first_login_pending": marker.exists(),
    "product_services_blocked": marker.exists(),
    "secrets_embedded": False,
    "config_real_embedded": False,
    "writer_called": False,
    "wifi_changed": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
PY
}

show_firstboot_splash() {
  if [ -e "$TTY_DEVICE" ]; then
    command -v chvt >/dev/null 2>&1 && chvt "$REMOTE_TTY" >/dev/null 2>&1 || true
    printf '\033c\033[2J\033[3J\033[H\033[?25l' > "$TTY_DEVICE" 2>/dev/null || true
  fi
  if [ -f "$SPLASH" ]; then
    env TERM=linux PYTHONPATH="$SCRIPT_DIR" python3 "$SPLASH" firstboot \
      --status-out "$OUT_DIR/splash-status.json" \
      <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
  fi
}

if [ "$MODE" = "status" ]; then
  write_status status
  exit 0
fi

while [ -e "$MARKER" ]; do
  write_status waiting
  show_firstboot_splash || true
  sleep "$POLL_SEC"
done

write_status complete
