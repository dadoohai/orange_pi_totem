#!/usr/bin/env bash
set -u

umask 077

STATUS_SVG="${1:-/tmp/dadooh-status/status.svg}"
MPV_BIN="${TOTEM_STATUS_RENDERER_MPV_BIN:-mpv}"
TOTEM_SETTINGS_SESSION_LOCK="${TOTEM_SETTINGS_SESSION_LOCK:-/run/totem/settings-session.lock}"
TOTEM_PUBLIC_ORIENTATION_PATH="${TOTEM_PUBLIC_ORIENTATION_PATH:-/data/state/totem-display/orientation.json}"

MPV_PID=""
STOP_REQUESTED=0

stamp() {
  date '+%Y-%m-%dT%H:%M:%S%z'
}

log() {
  printf '%s totem_status_renderer[%s]: %s\n' "$(stamp)" "$$" "$*"
}

settings_session_active() {
  [ -e "$TOTEM_SETTINGS_SESSION_LOCK" ]
}

process_alive() {
  local pid="$1"
  local state=""

  [ -n "$pid" ] || return 1
  kill -0 "$pid" >/dev/null 2>&1 || return 1
  if [ -r "/proc/$pid/stat" ]; then
    state="$(sed -n 's/^[^)]*) \([^ ]\).*/\1/p' "/proc/$pid/stat" 2>/dev/null || true)"
    [ "$state" = "Z" ] && return 1
  fi
  return 0
}

read_public_rotation() {
  python3 - "$TOTEM_PUBLIC_ORIENTATION_PATH" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
try:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise ValueError("invalid orientation source")
    data = json.loads(path.read_text(encoding="utf-8"))
    value = int(data.get("rotation_deg", 0)) % 360
    if value not in {0, 90, 180, 270}:
        raise ValueError("invalid rotation")
except Exception:
    value = 0
print(value)
PY
}

stop_mpv() {
  STOP_REQUESTED=1

  if [ -n "$MPV_PID" ] && kill -0 "$MPV_PID" >/dev/null 2>&1; then
    kill -TERM "$MPV_PID" >/dev/null 2>&1 || true
    wait "$MPV_PID" 2>/dev/null || true
  fi

  MPV_PID=""
}

if [ "$STATUS_SVG" = "--self-test" ]; then
  SELF_TEST_DIR="$(mktemp -d /tmp/dadooh-status-renderer-self-test.XXXXXX)"
  trap 'rm -rf "$SELF_TEST_DIR"' EXIT
  TOTEM_PUBLIC_ORIENTATION_PATH="$SELF_TEST_DIR/orientation.json"
  printf '{"rotation_deg": 90}\n' >"$TOTEM_PUBLIC_ORIENTATION_PATH"
  [ "$(read_public_rotation)" = "90" ]
  printf '{"rotation_deg": 45}\n' >"$TOTEM_PUBLIC_ORIENTATION_PATH"
  [ "$(read_public_rotation)" = "0" ]
  rm -f "$TOTEM_PUBLIC_ORIENTATION_PATH"
  [ "$(read_public_rotation)" = "0" ]
  printf 'self-test: ok\n'
  exit 0
fi

case "$STATUS_SVG" in
  *://*|-*)
    log "invalid_status_svg"
    exit 2
    ;;
esac

if [ ! -r "$STATUS_SVG" ] || [ ! -f "$STATUS_SVG" ]; then
  log "status_svg_unavailable"
  exit 1
fi

if settings_session_active; then
  log "settings_session_active renderer_not_started"
  exit 0
fi

if ! command -v "$MPV_BIN" >/dev/null 2>&1; then
  log "mpv_unavailable"
  exit 1
fi

trap stop_mpv TERM INT

ROTATION_DEG="$(read_public_rotation)"

"$MPV_BIN" \
  --no-config \
  --fs \
  --force-window=yes \
  --loop-file=inf \
  --image-display-duration=inf \
  --keep-open=yes \
  --no-terminal \
  --no-osc \
  --osd-level=0 \
  --input-terminal=no \
  --input-default-bindings=no \
  --input-vo-keyboard=no \
  --cursor-autohide=always \
  --vo=gpu \
  --gpu-context=drm \
  --video-rotate="$ROTATION_DEG" \
  --ao=null \
  -- "$STATUS_SVG" &
MPV_PID="$!"

while process_alive "$MPV_PID"; do
  if settings_session_active; then
    log "settings_session_active stopping_renderer"
    STOP_REQUESTED=1
    kill -TERM "$MPV_PID" >/dev/null 2>&1 || true
    wait "$MPV_PID" 2>/dev/null || true
    MPV_PID=""
    exit 0
  fi
  sleep 1
done

wait "$MPV_PID" 2>/dev/null
rc="$?"
MPV_PID=""

if [ "$STOP_REQUESTED" -ne 0 ]; then
  exit 0
fi

exit "$rc"
