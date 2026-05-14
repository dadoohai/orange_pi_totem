#!/usr/bin/env bash
set -u

umask 077

STATUS_SVG="${1:-/tmp/dadooh-status/status.svg}"
MPV_BIN="${TOTEM_STATUS_RENDERER_MPV_BIN:-mpv}"
TOTEM_SETTINGS_SESSION_LOCK="${TOTEM_SETTINGS_SESSION_LOCK:-/run/totem/settings-session.lock}"

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

stop_mpv() {
  STOP_REQUESTED=1

  if [ -n "$MPV_PID" ] && kill -0 "$MPV_PID" >/dev/null 2>&1; then
    kill -TERM "$MPV_PID" >/dev/null 2>&1 || true
    wait "$MPV_PID" 2>/dev/null || true
  fi

  MPV_PID=""
}

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
