#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
OUTPUT_DIR="/tmp/dadooh-c12-2-card-write-image-lab"
FLASH_COMPLETED="false"
IMAGER_VERIFICATION_COMPLETED="false"
TARGET_CARD_NOTE="not_recorded"

EXPECTED_SHA256="1b6f5573262d501ae2df6bc3338b56432c8994d4444308caf00347829df08fe2"
IMAGE_PATH="/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab_minimal.img"
CHECKSUM_PATH="${IMAGE_PATH}.sha256"
BUILD_LOG_PATH="/home/builder/totem-os/armbian-build-v25.11/output/logs/log-build-29bced66-eed1-4f2c-8d0e-d2ad34f794b5.log"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_2_card_write_checklist.sh [mode] [options]

Modes:
  --prepare-only                 Validate repo-local prerequisites only.
  --verify-image                 Verify C12.1 image/checksum/manifests.
  --record-manual-flash          Record sanitized manual Armbian Imager result.
  --summary                      Print the C12.2 card-write checklist.

Options for --record-manual-flash:
  --flash-completed true|false
  --imager-verification-completed true|false
  --target-card-note TEXT        Sanitized note only, no serials/secrets.
  --output-dir PATH              Defaults to /tmp/dadooh-c12-2-card-write-image-lab

This runner is local/checklist-only. It must not access boards, write cards,
execute poweroff/reboot, provision config, call writer, change Wi-Fi or publish
secrets. The actual flash is done manually with Armbian Imager on Windows.
USAGE
}

die() {
  echo "error: $*" >&2
  exit 1
}

bool_arg() {
  case "${1:-}" in
    true|false) printf '%s' "$1" ;;
    *) die "expected true or false, got: ${1:-<empty>}" ;;
  esac
}

sanitize_note() {
  printf '%s' "${1:-not_recorded}" \
    | tr -cd 'A-Za-z0-9 _.,:=+-' \
    | cut -c1-120
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --verify-image) MODE="verify-image" ;;
    --record-manual-flash) MODE="record-manual-flash" ;;
    --summary) MODE="summary" ;;
    --flash-completed)
      shift
      FLASH_COMPLETED="$(bool_arg "${1:-}")"
      ;;
    --imager-verification-completed)
      shift
      IMAGER_VERIFICATION_COMPLETED="$(bool_arg "${1:-}")"
      ;;
    --target-card-note)
      shift
      TARGET_CARD_NOTE="$(sanitize_note "${1:-}")"
      ;;
    --output-dir)
      shift
      OUTPUT_DIR="${1:-}"
      ;;
    --help|-h) usage; exit 0 ;;
    *) echo "error: unsupported argument $1" >&2; usage; exit 2 ;;
  esac
  shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MANIFEST="$REPO_ROOT/releases/image-lab-readonly/manifest.md"
PACKAGE_MANIFEST="$REPO_ROOT/releases/image-lab-readonly/package-manifest-c12-1.txt"
INTEGRATION_MANIFEST="$REPO_ROOT/releases/image-lab-readonly/read-only-integration-manifest-c12-1.txt"

verify_image() {
  test -f "$IMAGE_PATH" || die "image not found: $IMAGE_PATH"
  test -f "$CHECKSUM_PATH" || die "checksum file not found: $CHECKSUM_PATH"
  test -f "$BUILD_LOG_PATH" || die "build log not found: $BUILD_LOG_PATH"
  test -f "$MANIFEST" || die "image-lab manifest not found"
  test -f "$PACKAGE_MANIFEST" || die "package manifest not found"
  test -f "$INTEGRATION_MANIFEST" || die "integration manifest not found"

  actual_sha="$(sha256sum "$IMAGE_PATH" | awk '{print $1}')"
  [ "$actual_sha" = "$EXPECTED_SHA256" ] || die "sha256 mismatch"
  sha256sum -c "$CHECKSUM_PATH" >/dev/null

  grep -q '^package=overlayroot ' "$PACKAGE_MANIFEST"
  grep -q '^overlayroot_included=true$' "$INTEGRATION_MANIFEST"
  grep -q '^initramfs_generated_after_overlayroot=true$' "$INTEGRATION_MANIFEST"
  grep -Eq '`card_written=(true|false)`' "$MANIFEST"
  grep -Eq '`boards_touched=(true|false)`' "$MANIFEST"

  if grep -Eiq '(api_key|private-values|wifi password|ssid password|config\.candidate\.private|environment_id real)' \
    "$PACKAGE_MANIFEST" "$INTEGRATION_MANIFEST" "$MANIFEST"; then
    die "textual artifact secret scan failed"
  fi

  printf 'image_exists=true\n'
  printf 'sha256_verified_before_flash=true\n'
  printf 'build_log_exists=true\n'
  printf 'package_manifest_exists=true\n'
  printf 'overlayroot_included=true\n'
  printf 'initramfs_generated_after_overlayroot=true\n'
}

record_manual_flash() {
  verify_image >/dev/null
  mkdir -p "$OUTPUT_DIR"
  chmod 700 "$OUTPUT_DIR"
  status_file="$OUTPUT_DIR/card-write-status.json"
  cat >"$status_file" <<JSON
{
  "schema_version": 1,
  "image_path": "$IMAGE_PATH",
  "sha256_expected": "$EXPECTED_SHA256",
  "sha256_verified_before_flash": true,
  "imager_tool": "Armbian Imager Windows",
  "flash_completed": $FLASH_COMPLETED,
  "imager_verification_completed": $IMAGER_VERIFICATION_COMPLETED,
  "target_card_note": "$TARGET_CARD_NOTE",
  "card_written": $FLASH_COMPLETED,
  "board_booted": false,
  "secrets_included": false,
  "config_real_included": false
}
JSON
  chmod 600 "$status_file"
  printf 'manual_flash_record=%s\n' "$status_file"
}

case "$MODE" in
  prepare-only)
    git -C "$REPO_ROOT" diff --check
    bash -n "$0"
    test -f "$MANIFEST"
    printf 'c12_2_prepare_only=ok\n'
    ;;
  verify-image)
    verify_image
    ;;
  record-manual-flash)
    record_manual_flash
    ;;
  summary)
    cat <<CHECKLIST
C12.2 card-write checklist:
- verify image SHA256 before copying/flashing;
- use Armbian Imager on Windows;
- select local/custom image, not a downloaded replacement;
- use only a new or disposable test card;
- do not use the damaged dev card;
- do not use the functional dev card;
- do not boot or SSH into any board unless a later C12.3 gate authorizes it;
- wait for Armbian Imager flash and verification to complete;
- record only sanitized card notes, not serials or secrets.

Image:
$IMAGE_PATH

Expected SHA256:
$EXPECTED_SHA256
CHECKLIST
    ;;
  *) die "unsupported mode $MODE" ;;
esac
