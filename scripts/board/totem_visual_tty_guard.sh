#!/usr/bin/env bash
set -euo pipefail

MODE="quiet"
HOLD="false"
TTYS=()

usage() {
  cat <<'USAGE'
Usage:
  totem_visual_tty_guard.sh [--quiet|--clear] [--hold] [--tty N ...]

Applies visual-console guardrails for the appliance HDMI UI. It disables
terminal echo/canonical input on selected VTs, hides the cursor and optionally
clears the screen. It does not read input, does not log keystrokes, does not
touch config, Wi-Fi, NetworkManager or writer state.

With --hold, it keeps the selected VTs open after the initial guard. This
preserves no-echo mode before any foreground TTY program is running without
rewriting terminal state while the wizard owns the VT.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --quiet)
      MODE="quiet"
      ;;
    --clear)
      MODE="clear"
      ;;
    --hold)
      HOLD="true"
      ;;
    --tty)
      shift
      TTYS+=("${1:-}")
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

case "$MODE" in
  quiet|clear) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ "${#TTYS[@]}" -eq 0 ]; then
  TTYS=(1 2)
fi

for tty in "${TTYS[@]}"; do
  case "$tty" in
    ''|*[!0-9]*|0)
      echo "error: --tty must be a positive integer" >&2
      exit 2
      ;;
  esac
done

apply_guard() {
  local tty="$1"
  local device="/dev/tty$tty"
  [ -e "$device" ] || return 0
  /usr/bin/stty -F "$device" -echo -icanon min 0 time 0 2>/dev/null || true
  printf '\033[?25l' > "$device" 2>/dev/null || true
  if [ "$MODE" = "clear" ]; then
    if command -v setterm >/dev/null 2>&1; then
      TERM=linux setterm --clear all --cursor off > "$device" 2>/dev/null || true
    fi
    printf '\033[?25l\033[2J\033[3J\033[H' > "$device" 2>/dev/null || true
    sleep 0.05
    printf '\033[?25l\033[2J\033[3J\033[H' > "$device" 2>/dev/null || true
  fi
  /usr/bin/stty -F "$device" -echo -icanon min 0 time 0 2>/dev/null || true
}

for tty in "${TTYS[@]}"; do
  apply_guard "$tty"
done

if [ "$HOLD" != "true" ]; then
  exit 0
fi

HELD_FDS=()
for tty in "${TTYS[@]}"; do
  device="/dev/tty$tty"
  [ -e "$device" ] || continue
  if exec {fd}<>"$device"; then
    HELD_FDS+=("$fd")
  fi
done

if [ "${#HELD_FDS[@]}" -eq 0 ]; then
  exit 0
fi

for tty in "${TTYS[@]}"; do
  apply_guard "$tty"
done

cleanup() {
  local fd
  for fd in "${HELD_FDS[@]}"; do
    exec {fd}>&- || true
  done
}
trap 'cleanup; exit 0' TERM INT HUP

while :; do
  sleep 3600 &
  wait "$!" || true
done
