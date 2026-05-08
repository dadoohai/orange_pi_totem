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
EXPECTED_IMAGE_VERSION="${C12_EXPECTED_IMAGE_VERSION:-c12.1.8}"
EXPECTED_IMAGE_SUFFIX="${C12_EXPECTED_IMAGE_SUFFIX:-c12-ro-lab-${EXPECTED_IMAGE_VERSION//./-}}"

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
  grep -Eq '`card_written=(true|false)`' "$IMAGE_LAB_MANIFEST"
  grep -Eq '`boards_touched=(true|false)`' "$IMAGE_LAB_MANIFEST"
  grep -Eq '`image_built=(true|false)`' "$IMAGE_LAB_MANIFEST"
  grep -Eq '`ready_for_c12_2_(card_write|board_validation)=(true|false)`' "$IMAGE_LAB_MANIFEST"
  grep -Eq '`c12_3_status=(blocked|not_started|passed)`|`c12_3_boot_started=(true|false)`' "$IMAGE_LAB_MANIFEST"
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
  test -f "${rootfs_validation_file:?}"

  sha256sum -c "$image_checksum_file" >/dev/null
  grep -q '^package=overlayroot ' "$package_manifest_file"
  grep -q '^package=mpv ' "$package_manifest_file"
  grep -q '^package=ffmpeg ' "$package_manifest_file"
  grep -q '^package=python3-requests ' "$package_manifest_file"
  grep -q '^package=network-manager ' "$package_manifest_file"
  grep -q '^overlayroot_included=true$' "$integration_manifest_file"
  grep -q "^image_version=$EXPECTED_IMAGE_VERSION$" "$integration_manifest_file"
  grep -q '^image_suffix_c12_ro_lab=true$' "$integration_manifest_file"
  basename "$image_file" | grep -q "$EXPECTED_IMAGE_SUFFIX"
  grep -q '^firstboot_gate_included=true$' "$integration_manifest_file"
  grep -q '^rootfs_firstboot_autoconfig_proven=true$' "$integration_manifest_file"
  grep -q '^lab_firstboot_bootstrap_service_included=true$' "$integration_manifest_file"
  grep -q '^lab_firstboot_bootstrap_service_enabled=true$' "$integration_manifest_file"
  grep -q '^lab_firstboot_bootstrap_service_ordered_before_gate=true$' "$integration_manifest_file"
  grep -q '^gate_expected_path_matches=true$' "$integration_manifest_file"
  grep -q '^open_settings_cleanup_included=true$' "$integration_manifest_file"
  grep -q '^settings_trigger_stale_lock_cleanup_included=true$' "$integration_manifest_file"
  grep -q '^read_only_assertion_required=true$' "$integration_manifest_file"
  grep -q '^lab_firstboot_autoconfig=true$' "$integration_manifest_file"
  grep -q '^lab_firstboot_boot_validatable=true$' "$integration_manifest_file"
  grep -q '^rootfs_ready_for_card_write=true$' "$integration_manifest_file"
  grep -q '^ready_for_board_boot=true$' "$integration_manifest_file"
  grep -q '^card_written=false$' "$integration_manifest_file"
  grep -q '^boards_touched=false$' "$integration_manifest_file"
  grep -q 'Installing AGGREGATED_PACKAGES_IMAGE packages.*overlayroot' "$build_log_file"
  grep -q '^initramfs_generated_after_overlayroot=true$' "$integration_manifest_file"
  if ! grep -q 'Updated initramfs' "$build_log_file"; then
    grep -q 'initrd cache hit' "$build_log_file"
    grep -q '^initramfs_source=cache_hit_with_overlayroot_hooks$' "$integration_manifest_file"
  fi
  grep -q '^initrd_img_exists=true$' "$integration_manifest_file"
  grep -q '^initrd_contains_overlayroot_hook=true$' "$integration_manifest_file"
  grep -q '^initrd_contains_overlay_module=true$' "$integration_manifest_file"
  grep -q '^initrd_contains_overlay_module_effective_path=true$' "$integration_manifest_file"
  grep -q '^initrd_contains_overlay_load_hook=true$' "$integration_manifest_file"
  grep -q '^initrd_contains_c12_overlayroot_marker=true$' "$integration_manifest_file"
  grep -q '^initrd_contains_c12_overlay_module_path_marker=true$' "$integration_manifest_file"
  grep -q '^uinitrd_exists=true$' "$integration_manifest_file"
  grep -q '^uinitrd_nonempty=true$' "$integration_manifest_file"
  grep -q '^uinitrd_payload_extracted=true$' "$integration_manifest_file"
  grep -q '^uinitrd_payload_matches_initrd_img=true$' "$integration_manifest_file"
  grep -q '^uinitrd_contains_overlayroot_hook=true$' "$integration_manifest_file"
  grep -q '^uinitrd_contains_overlay_module=true$' "$integration_manifest_file"
  grep -q '^uinitrd_contains_overlay_module_effective_path=true$' "$integration_manifest_file"
  grep -q '^uinitrd_contains_overlay_load_hook=true$' "$integration_manifest_file"
  grep -q '^uinitrd_contains_c12_overlayroot_marker=true$' "$integration_manifest_file"
  grep -q '^uinitrd_contains_c12_overlay_module_path_marker=true$' "$integration_manifest_file"
  grep -q '^uinitrd_generated_after_overlayroot=true$' "$integration_manifest_file"
  grep -q '^uinitrd_generated_after_initrd_img=true$' "$integration_manifest_file"
  grep -q '^boot_script_uses_uinitrd=true$' "$integration_manifest_file"
  grep -q '^effective_boot_initramfs_valid=true$' "$integration_manifest_file"
  grep -q '^overlay_module_effective_path_present=true$' "$integration_manifest_file"
  grep -q '^modules_dep_effective_path_present=true$' "$integration_manifest_file"
  grep -q '^modules_alias_effective_path_present=true$' "$integration_manifest_file"
  grep -q '^modules_dep_references_overlay=true$' "$integration_manifest_file"
  grep -q '^modprobe_present_in_initramfs=true$' "$integration_manifest_file"
  grep -q '^insmod_present_in_initramfs=true$' "$integration_manifest_file"
  grep -q '^overlay_load_hook_uses_effective_path=true$' "$integration_manifest_file"
  grep -q '^effective_boot_initramfs_overlay_resolvable=true$' "$integration_manifest_file"

  if grep -Eiq '(api_key|private-values|wifi password|ssid password|environment_id real|config\.candidate\.private)' \
    "$ARTIFACTS_ENV" "$package_manifest_file" "$integration_manifest_file"; then
    echo "error: textual artifact secret scan failed" >&2
    exit 1
  fi

  grep -q '^rootfs_firstboot_autoconfig_proven=true$' "$rootfs_validation_file"
  grep -q '^rootfs_lab_bootstrap_proven=true$' "$rootfs_validation_file"
  grep -q '^ready_for_card_write_by_rootfs=true$' "$rootfs_validation_file"
  grep -q '^effective_boot_initramfs_valid=true$' "$rootfs_validation_file"
  grep -q '^uinitrd_nonempty=true$' "$rootfs_validation_file"
  grep -q '^uinitrd_payload_matches_initrd_img=true$' "$rootfs_validation_file"
  grep -q '^uinitrd_generated_after_overlayroot=true$' "$rootfs_validation_file"
  grep -q '^uinitrd_generated_after_initrd_img=true$' "$rootfs_validation_file"
  grep -q '^overlay_module_effective_path_present=true$' "$rootfs_validation_file"
  grep -q '^modules_dep_references_overlay=true$' "$rootfs_validation_file"
  grep -q '^overlay_load_hook_uses_effective_path=true$' "$rootfs_validation_file"
  grep -q '^effective_boot_initramfs_overlay_resolvable=true$' "$rootfs_validation_file"
  grep -q '^private_values_published=false$' "$rootfs_validation_file"

  local rootfs_recheck
  rootfs_recheck="$(mktemp /tmp/dadooh-c12-rootfs-validation.XXXXXX.env)"
  python3 "$REPO_ROOT/scripts/build/inspect_c12_image_rootfs.py" \
    "$image_file" \
    --require-lab-bootstrap-service \
    --out "$rootfs_recheck"
  grep -q '^ready_for_card_write_by_rootfs=true$' "$rootfs_recheck"
  grep -q '^effective_boot_initramfs_valid=true$' "$rootfs_recheck"
  grep -q '^effective_boot_initramfs_overlay_resolvable=true$' "$rootfs_recheck"
  rm -f "$rootfs_recheck"
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
- provide private C12_LAB_FIRSTBOOT_CONF outside Git for every board-bootable
  image-lab build;
- build board-validation images with C12_REQUIRE_LAB_FIRSTBOOT_CONF=1;
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
- confirm the image was built with private lab firstboot autoconfig; an image
  without it is not board-boot-validatable after the C12.3.2 black-screen
  result;
- verify read_only_enabled=true;
- verify overlay_active=true or equivalent;
- verify root write blocked;
- verify /data, /tmp and /run writable;
- if root is ext4 rw, classify IMAGE_LAB_READ_ONLY_NOT_ACTIVE and stop before
  treating read-only validation as successful;
- verify player_running/playback;
- verify F10 open/cancel;
- verify stale /run/dadooh-settings/session.lock is absent after cancel/failure;
- keep power cut blocked until read-only boot/reboot smoke passes.
CHECKLIST
    ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac
