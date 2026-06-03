#!/usr/bin/env bash
# C18 - totem-kiosky-launcher
#
# Chooses which kiosk.py to run:
#   - /data/player-runtime/current/kiosk.py  (future C18-aware slot)
#   - /opt/totem/kiosky-player/kiosk.py      (fallback shipped in image)
#
# Then delegates to the existing kiosky_service_launcher.sh (which provides
# the watchdog, status writer, setup-trigger plumbing, etc.).  We pass the
# chosen app directory via KIOSKY_APP_DIR, which the launcher reads.
#
# This script:
#   - Never prints secrets.
#   - Only logs version/source (sanitised) and resolved path.
#   - Exits non-zero only on missing fallback; otherwise lets the underlying
#     launcher own its own retry/backoff behaviour.

set -u

FALLBACK_APP_DIR="${TOTEM_KIOSKY_FALLBACK_APP_DIR:-/opt/totem/kiosky-player}"
DATA_APP_DIR="${TOTEM_KIOSKY_DATA_APP_DIR:-/data/player-runtime/current}"
INNER_LAUNCHER="${TOTEM_KIOSKY_INNER_LAUNCHER:-/opt/totem/bin/kiosky_service_launcher.sh}"

stamp() { date '+%Y-%m-%dT%H:%M:%S%z'; }
log() { printf '%s totem-kiosky-launcher[%s]: %s\n' "$(stamp)" "$$" "$*"; }

source_label="fallback"
chosen_dir="$FALLBACK_APP_DIR"

if [[ -L "$DATA_APP_DIR" || -d "$DATA_APP_DIR" ]]; then
  # Resolve symlink target (may be relative)
  if [[ -L "$DATA_APP_DIR" ]]; then
    target="$(readlink "$DATA_APP_DIR" 2>/dev/null || true)"
  else
    target="$DATA_APP_DIR"
  fi

  # Sanity: kiosk.py must exist on the resolved dir
  if [[ -f "$DATA_APP_DIR/kiosk.py" ]]; then
    chosen_dir="$DATA_APP_DIR"
    # Derive a short version label from the symlink target basename
    if [[ -n "$target" ]]; then
      version_label="$(basename "$target")"
    else
      version_label="current"
    fi
    source_label="data:${version_label}"
  else
    log "data app dir present but kiosk.py missing; falling back" \
        "data_app_dir=$DATA_APP_DIR"
  fi
fi

if [[ ! -f "$chosen_dir/kiosk.py" ]]; then
  log "FATAL: no kiosk.py available (data=$DATA_APP_DIR fallback=$FALLBACK_APP_DIR)"
  exit 78
fi

if [[ ! -x "$INNER_LAUNCHER" && ! -f "$INNER_LAUNCHER" ]]; then
  log "FATAL: inner launcher missing at $INNER_LAUNCHER"
  exit 79
fi

log "kiosk_source=${source_label} kiosk_dir=${chosen_dir}"
export KIOSKY_APP_DIR="$chosen_dir"

# Delegate: exec preserves systemd ownership of the PID.
exec /usr/bin/env bash "$INNER_LAUNCHER"
