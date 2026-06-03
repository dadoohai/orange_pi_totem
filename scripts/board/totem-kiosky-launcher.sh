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
PLAYER_RUNTIME_STATE_FILE="${TOTEM_PLAYER_RUNTIME_STATE_FILE:-/data/player-runtime/state.json}"

stamp() { date '+%Y-%m-%dT%H:%M:%S%z'; }
log() { printf '%s totem-kiosky-launcher[%s]: %s\n' "$(stamp)" "$$" "$*"; }

validate_player_runtime_release() {
  local app_dir="$1"
  local state_file="$2"
  /usr/bin/python3 - "$app_dir" "$state_file" <<'PY'
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

MARKER_NAME = ".release_verified.json"
MARKER_SCHEMA = "dadooh.c18.player_runtime.verified.v1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == MARKER_NAME:
            continue
        st = path.lstat()
        if stat.S_ISDIR(st.st_mode):
            continue
        if not stat.S_ISREG(st.st_mode):
            raise RuntimeError(f"unsupported_member:{rel}")
        h.update(rel.encode("utf-8") + b"\0")
        h.update(sha256_file(path).encode("ascii") + b"\0")
    return h.hexdigest()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def quarantined(marker: dict, state_path: Path) -> bool:
    if not state_path.exists():
        return False
    try:
        state = load_json(state_path)
    except Exception:
        raise RuntimeError("state_invalid")
    entries = state.get("quarantine") or state.get("quarantined_identities") or []
    if not isinstance(entries, list):
        raise RuntimeError("quarantine_invalid")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("tree_sha256") and entry.get("tree_sha256") == marker.get("tree_sha256"):
            return True
        if entry.get("payload_sha256") and entry.get("payload_sha256") == marker.get("payload_sha256"):
            return True
    return False


try:
    app = Path(sys.argv[1]).resolve()
    state_file = Path(sys.argv[2])
    kiosk = app / "kiosk.py"
    marker_path = app / MARKER_NAME
    if not kiosk.is_file():
        raise RuntimeError("kiosk_missing")
    marker = load_json(marker_path)
    if marker.get("schema") != MARKER_SCHEMA:
        raise RuntimeError("marker_schema")
    if marker.get("verdict") != "verified":
        raise RuntimeError("marker_not_verified")
    kiosk_sha = sha256_file(kiosk)
    if marker.get("kiosk_py_sha256") != kiosk_sha:
        raise RuntimeError("kiosk_sha_mismatch")
    current_tree = tree_hash(app)
    if marker.get("tree_sha256") != current_tree:
        raise RuntimeError("tree_sha_mismatch")
    deep = marker.get("deep_health")
    if not isinstance(deep, dict) or not deep.get("passed"):
        raise RuntimeError("deep_health_not_passed")
    if quarantined(marker, state_file):
        raise RuntimeError("quarantined")
    print("OK", marker.get("version") or "current")
except Exception as exc:
    print("INVALID", str(exc))
    sys.exit(1)
PY
}

source_label="fallback"
chosen_dir="$FALLBACK_APP_DIR"

if [[ -L "$DATA_APP_DIR" || -d "$DATA_APP_DIR" ]]; then
  # Resolve symlink target (may be relative)
  if [[ -L "$DATA_APP_DIR" ]]; then
    target="$(readlink "$DATA_APP_DIR" 2>/dev/null || true)"
  else
    target="$DATA_APP_DIR"
  fi

  validation="$(validate_player_runtime_release "$DATA_APP_DIR" "$PLAYER_RUNTIME_STATE_FILE" 2>/dev/null || true)"
  if [[ "$validation" == OK* ]]; then
    chosen_dir="$DATA_APP_DIR"
    # Derive a short version label from the symlink target basename
    if [[ -n "$target" ]]; then
      version_label="$(basename "$target")"
    else
      version_label="current"
    fi
    source_label="data:${version_label}"
  else
    log "data app dir present but not verified; falling back" \
        "data_app_dir=$DATA_APP_DIR reason=${validation:-validation_failed}"
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
