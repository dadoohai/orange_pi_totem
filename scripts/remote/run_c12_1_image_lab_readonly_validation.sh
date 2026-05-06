#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_1_image_lab_readonly_validation.sh [mode]

Modes:
  --prepare-only       Validate local repo prerequisites only.
  --checklist          Print the future image-lab validation checklist.
  --validate-manifest  Validate the C12 image-lab manifest exists.

This runner is intentionally local-only in C12.0-prep. It must not SSH into
boards, write cards, build final images, enable read-only, call writer, change
Wi-Fi/NetworkManager, install packages or publish secrets.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --checklist) MODE="checklist" ;;
    --validate-manifest) MODE="validate-manifest" ;;
    --help|-h) usage; exit 0 ;;
    *) echo "error: unsupported argument $1" >&2; usage; exit 2 ;;
  esac
  shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE_LAB_MANIFEST="$REPO_ROOT/releases/image-lab-readonly/manifest.md"

validate_manifest() {
  test -f "$IMAGE_LAB_MANIFEST"
  grep -q '`image_lab_readonly=true`' "$IMAGE_LAB_MANIFEST"
  grep -q '`image_built=false`' "$IMAGE_LAB_MANIFEST"
  grep -q '`card_written=false`' "$IMAGE_LAB_MANIFEST"
  grep -q '`ready_for_c12_1_build=true`' "$IMAGE_LAB_MANIFEST"
}

case "$MODE" in
  prepare-only)
    git -C "$REPO_ROOT" diff --check
    validate_manifest
    bash -n "$0"
    printf 'c12_1_image_lab_prepare_only=ok\n'
    ;;
  validate-manifest)
    validate_manifest
    printf 'c12_image_lab_manifest=ok\n'
    ;;
  checklist)
    cat <<'CHECKLIST'
C12.1 build checklist:
- recover or clone Armbian Build v25.11;
- confirm build commit/base;
- create userpatches for appliance/read-only;
- include overlayroot in image build;
- generate initramfs/uInitrd with overlayroot present;
- include journald volatile policy;
- include /data layout and appliance units/scripts;
- exclude real config, secrets, Wi-Fi credentials, media cache and raw logs;
- build image-lab only;
- produce checksum, build log and package manifest;
- do not write card until a separate C12.2 gate.

C12.2 board validation checklist:
- write only a test card after C12.1 artifacts pass;
- boot on test board, not dev reference;
- verify read_only_enabled=true;
- verify overlay_active=true or equivalent;
- verify root write blocked;
- verify /data, /tmp and /run writable;
- verify player_running/playback;
- verify F10 open/cancel;
- keep power cut blocked until read-only boot/reboot smoke passes.
CHECKLIST
    ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac
