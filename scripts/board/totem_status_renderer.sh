#!/usr/bin/env bash
set -u

umask 077

STATUS_SVG="${1:-/tmp/dadooh-status/status.svg}"
MPV_BIN="${TOTEM_STATUS_RENDERER_MPV_BIN:-mpv}"

MPV_PID=""
STOP_REQUESTED=0

stamp() {
  date '+%Y-%m-%dT%H:%M:%S%z'
}

log() {
  printf '%s totem_status_renderer[%s]: %s\n' "$(stamp)" "$$" "$*"
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

wait "$MPV_PID"
rc="$?"
MPV_PID=""

if [ "$STOP_REQUESTED" -ne 0 ]; then
  exit 0
fi

exit "$rc"
