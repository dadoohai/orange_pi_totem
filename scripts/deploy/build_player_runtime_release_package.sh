#!/usr/bin/env bash
# C18 - Build a lab-only player-runtime release package.
#
# This creates a C18-aware player-runtime payload from the governed snapshot in
# this repository. It does not publish, does not touch a board, and does not
# thaw the device-side rc=44 guard.

set -euo pipefail

CHANNEL="${CHANNEL:-homologation}"
OUT_BASE="${OUT_BASE:-releases/player-runtime}"
SOURCE_REPO_FULL="${SOURCE_REPO_FULL:-dadoohai/orange_pi_totem}"
COMPONENT="player-runtime"
VERSION_OVERRIDE="${VERSION:-}"
MODE="build-package"
ALLOW_DIRTY=0
LAB_VARIANT="${LAB_VARIANT:-}"

while [[ $# -gt 0 ]]; do
  arg="$1"
  case "$arg" in
    --prepare-only) MODE="prepare-only" ;;
    --build-package) MODE="build-package" ;;
    --allow-dirty) ALLOW_DIRTY=1 ;;
    --version=*) VERSION_OVERRIDE="${arg#*=}" ;;
    --version) shift; VERSION_OVERRIDE="${1:-}" ;;
    --channel=*) CHANNEL="${arg#*=}" ;;
    --channel) shift; CHANNEL="${1:-}" ;;
    --out-base=*) OUT_BASE="${arg#*=}" ;;
    --out-base) shift; OUT_BASE="${1:-}" ;;
    --lab-variant=*) LAB_VARIANT="${arg#*=}" ;;
    --lab-variant) shift; LAB_VARIANT="${1:-}" ;;
    -h|--help)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *)
      echo "FATAL: unknown arg: $arg" >&2
      exit 2
      ;;
  esac
  shift
done

log() { printf '[build_player_runtime_release_package] %s\n' "$*"; }
die() { printf '[build_player_runtime_release_package] FATAL: %s\n' "$*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SNAPSHOT="$REPO_ROOT/player-runtime/kiosky-player/kiosk.py"
RELEASE_GATE="$REPO_ROOT/scripts/qa/c18_player_runtime_release_gate.py"

[[ -f "$SNAPSHOT" ]] || die "governed player-runtime snapshot not found: $SNAPSHOT"
[[ -f "$RELEASE_GATE" ]] || die "player-runtime release gate not found: $RELEASE_GATE"
[[ "$CHANNEL" =~ ^(lab|homologation)$ ]] || die "unsupported channel: $CHANNEL (player-runtime lab builder only supports lab or homologation)"

pushd "$REPO_ROOT" >/dev/null
SOURCE_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
SOURCE_COMMIT="$(git rev-parse HEAD)"
SOURCE_COMMIT_SHORT="$(git rev-parse --short=7 HEAD)"
DIRTY=0
if ! git diff --quiet || ! git diff --cached --quiet; then
  DIRTY=1
fi
popd >/dev/null

if [[ "$DIRTY" -eq 1 && "$ALLOW_DIRTY" -eq 0 ]]; then
  die "orange_pi_totem working tree is dirty (use --allow-dirty for lab package experiments)"
fi

if [[ -z "$VERSION_OVERRIDE" ]]; then
  VERSION="c18.player-runtime-lab-$(date -u +%Y%m%dT%H%M%SZ)-${SOURCE_COMMIT_SHORT}"
else
  VERSION="$VERSION_OVERRIDE"
fi
[[ "$VERSION" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] || die "unsafe version: $VERSION"
[[ -z "$LAB_VARIANT" || "$LAB_VARIANT" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || die "unsafe lab variant: $LAB_VARIANT"

case "$OUT_BASE" in
  /*) OUT_ROOT="$OUT_BASE" ;;
  *) OUT_ROOT="$REPO_ROOT/$OUT_BASE" ;;
esac
OUT_DIR="$OUT_ROOT/$VERSION"
PAYLOAD_NAME="dadooh-${COMPONENT}-${VERSION}.tar.gz"
MANIFEST_NAME="dadooh-${COMPONENT}-${VERSION}.manifest.json"
PAYLOAD_PATH="$OUT_DIR/$PAYLOAD_NAME"
MANIFEST_PATH="$OUT_DIR/$MANIFEST_NAME"
NOW_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

log "component       = $COMPONENT"
log "version         = $VERSION"
log "channel         = $CHANNEL"
log "source_repo     = $SOURCE_REPO_FULL"
log "source_branch   = $SOURCE_BRANCH"
log "source_commit   = $SOURCE_COMMIT"
log "dirty           = $DIRTY"
log "lab_variant     = ${LAB_VARIANT:-none}"
log "out_dir         = $OUT_DIR"
log "mode            = $MODE"

if [[ "$MODE" == "prepare-only" ]]; then
  log "prepare_only=true"
  log "would_build_payload=${PAYLOAD_PATH}"
  log "would_build_manifest=${MANIFEST_PATH}"
  exit 0
fi

STAGE_DIR="$(mktemp -d -t player-runtime-stage-XXXXXX)"
BUILD_DIR="$(mktemp -d -t player-runtime-build-XXXXXX)"
TMP_PAYLOAD_PATH="$BUILD_DIR/$PAYLOAD_NAME"
TMP_MANIFEST_PATH="$BUILD_DIR/$MANIFEST_NAME"
cleanup() { rm -rf "$STAGE_DIR" "$BUILD_DIR"; }
trap cleanup EXIT

install -d -m 0755 "$STAGE_DIR"
install -m 0644 "$SNAPSHOT" "$STAGE_DIR/kiosk.py"
if [[ -n "$LAB_VARIANT" ]]; then
  printf '\n# c18_player_runtime_lab_variant=%s\n' "$LAB_VARIANT" >>"$STAGE_DIR/kiosk.py"
fi

tar -C "$STAGE_DIR" -czf "$TMP_PAYLOAD_PATH" kiosk.py
PAYLOAD_SHA256="$(sha256sum "$TMP_PAYLOAD_PATH" | awk '{print $1}')"
PAYLOAD_BYTES="$(wc -c <"$TMP_PAYLOAD_PATH" | tr -d ' ')"

python3 - "$TMP_MANIFEST_PATH" <<PY
import json
import sys

manifest = {
    "schema": "dadooh.totem.update.v1",
    "component": "${COMPONENT}",
    "version": "${VERSION}",
    "channel": "${CHANNEL}",
    "created_at_utc": "${NOW_UTC}",
    "source_repo": "${SOURCE_REPO_FULL}",
    "source_branch": "${SOURCE_BRANCH}",
    "source_commit": "${SOURCE_COMMIT}",
    "source_dirty": bool(${DIRTY}),
    "lab_variant": "${LAB_VARIANT}",
    "payload": "${PAYLOAD_NAME}",
    "payload_sha256": "${PAYLOAD_SHA256}",
    "payload_bytes": ${PAYLOAD_BYTES},
    "requires": {
        "device": "orangepizero3",
        "base_image_min": "c17.4.2",
        "device_track": "c18-hwdecode",
        "media_stack_id": "c18-hwdecode-v4l2request-copy",
        "mpv_wrapper": "/opt/totem/bin/totem-mpv-hwdecode",
        "hwdec": "v4l2request-copy",
        "vo": "gpu",
        "gpu_context": "drm",
        "deep_health_schema": "dadooh.c18.playback.deep_health.v1",
    },
    "entrypoint": "kiosk.py",
    "updates": ["kiosk.py"],
    "health_checks": [
        "player_runtime_release_gate",
        "playback_deep_health",
        "marker_identity_match",
    ],
}
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, sort_keys=True)
    fh.write("\\n")
PY

python3 -m json.tool "$TMP_MANIFEST_PATH" >/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 "$RELEASE_GATE" \
  --manifest "$TMP_MANIFEST_PATH" \
  --payload "$TMP_PAYLOAD_PATH" \
  >/dev/null

mkdir -p "$OUT_DIR"
mv -f "$TMP_PAYLOAD_PATH" "$PAYLOAD_PATH"
mv -f "$TMP_MANIFEST_PATH" "$MANIFEST_PATH"

log "build_package=true"
log "payload_path=${PAYLOAD_PATH}"
log "manifest_path=${MANIFEST_PATH}"
log "payload_sha256=${PAYLOAD_SHA256}"
log "payload_bytes=${PAYLOAD_BYTES}"
