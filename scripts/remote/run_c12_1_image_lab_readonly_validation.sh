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
  --validate-artifacts Validate C12.1 local image artifacts.

This runner is intentionally local-only in C12.0-prep. It must not SSH into
boards, write cards, build final images, enable read-only, call writer, change
Wi-Fi/NetworkManager, install packages or publish secrets.
USAGE
}

ARTIFACTS_ENV="${C12_1_ARTIFACTS_ENV:-}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --checklist) MODE="checklist" ;;
    --validate-manifest) MODE="validate-manifest" ;;
    --validate-artifacts) MODE="validate-artifacts" ;;
    --artifacts-env)
      shift
      ARTIFACTS_ENV="${1:-}"
      ;;
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
  grep -q '`card_written=false`' "$IMAGE_LAB_MANIFEST"
  grep -Eq '`image_built=(true|false)`' "$IMAGE_LAB_MANIFEST"
  grep -Eq '`ready_for_c12_2_(card_write|board_validation)=(true|false)`' "$IMAGE_LAB_MANIFEST"
}

validate_artifacts() {
  if [ -z "$ARTIFACTS_ENV" ] || [ ! -f "$ARTIFACTS_ENV" ]; then
    echo "error: missing --artifacts-env path" >&2
    exit 2
  fi
  # shellcheck disable=SC1090
  source "$ARTIFACTS_ENV"

  test -f "${image_file:?}"
  test -f "${image_checksum_file:?}"
  test -f "${build_log_file:?}"
  test -f "${package_manifest_file:?}"
  test -f "${integration_manifest_file:?}"

  sha256sum -c "$image_checksum_file" >/dev/null
  grep -q '^package=overlayroot ' "$package_manifest_file"
  grep -q '^package=mpv ' "$package_manifest_file"
  grep -q '^package=ffmpeg ' "$package_manifest_file"
  grep -q '^package=python3-requests ' "$package_manifest_file"
  grep -q '^package=network-manager ' "$package_manifest_file"
  grep -q '^overlayroot_included=true$' "$integration_manifest_file"
  grep -q '^card_written=false$' "$integration_manifest_file"
  grep -q '^boards_touched=false$' "$integration_manifest_file"
  grep -q 'Installing AGGREGATED_PACKAGES_IMAGE packages.*overlayroot' "$build_log_file"
  grep -q 'Updated initramfs' "$build_log_file"

  if grep -Eiq '(api_key|private-values|wifi password|ssid password|environment_id real|config\.candidate\.private)' \
    "$ARTIFACTS_ENV" "$package_manifest_file" "$integration_manifest_file"; then
    echo "error: textual artifact secret scan failed" >&2
    exit 1
  fi
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
  validate-artifacts)
    validate_artifacts
    printf 'c12_1_image_lab_artifacts=ok\n'
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
