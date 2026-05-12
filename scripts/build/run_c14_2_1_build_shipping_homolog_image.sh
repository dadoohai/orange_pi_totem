#!/usr/bin/env bash
# C14.2.1 — Build the shipping homologation image with the C14.1.1 pull
# updater embedded and the totem-update-agent.timer enabled.
#
# This script is a *thin wrapper* over the already-validated C12.1 runner
# (scripts/build/run_c12_1_build_image_lab_readonly.sh).  It does NOT change
# kernel config, board, release, or any BSP/U-Boot/DTB knob.  It only
# preconfigures the env vars so that the C14.2.1 image is tagged correctly
# and inherits the homologation private seed + lab firstboot conf from C13.1.3.
#
# The C14.1.1 binaries (totem-updatectl, totem-kiosky-launcher.sh, the
# kiosky-player drop-in, totem-update-agent.{service,timer}) are embedded
# automatically via the existing appliance manifest, which was extended by
# the same commit that introduces this runner.
#
# Required inputs (env or args):
#   --homolog-private-values <path-outside-repo>
#       Same private seed file used by C13.1.3.  Will be copied 0600 root:root
#       into /data/state/totem-settings/private-values.seed.json on the image.
#       Content is never printed/persisted by this script.
#
#   --lab-firstboot-conf <path-outside-repo>
#       Private Armbian firstboot.conf used for SSH-validatable lab images.
#
# Optional inputs (env or args):
#   --mode <prepare-only|check-build-env|clone-or-check-armbian-build|
#           prepare-userpatches|build-image|collect-artifacts|summary|full>
#       What to run (default: prepare-only).  `full` chains
#       check-build-env → clone-or-check-armbian-build →
#       prepare-userpatches → build-image → collect-artifacts → summary.
#   --confirm-private-homolog-image
#       Set the explicit confirmation flag required by the C13 embedding path.
#
# Restrictions enforced by the underlying runner / this wrapper:
#   - no apt upgrade / full-upgrade / dist-upgrade / armbian-upgrade;
#   - no apt install of unpinned packages;
#   - no pip install on device or in chroot;
#   - no kernel config change;
#   - no U-Boot / DTB / BSP change;
#   - no Wi-Fi / NetworkManager change;
#   - no secret printed.
#
# Output (when --mode build-image / collect-artifacts succeeds):
#   image file:   armbian-build-v25.11/output/images/
#                   Armbian-..._6.12.58-c12-ro-lab-c14-2-1-shipping-homolog_minimal.img
#   sha256 file:  same path + .sha256
#   collect manifest under $C14_2_1_OUT_DIR/

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INNER_RUNNER="$REPO_ROOT/scripts/build/run_c12_1_build_image_lab_readonly.sh"
[[ -x "$INNER_RUNNER" ]] || { echo "FATAL: inner runner not found: $INNER_RUNNER" >&2; exit 2; }

# --- Defaults --------------------------------------------------------------
C14_IMAGE_TAG="${C14_IMAGE_TAG:-c14-2-1-shipping-homolog}"
C14_IMAGE_VERSION="${C14_IMAGE_VERSION:-c14.2.1}"
C14_IMAGE_SUFFIX_MARKER="${C14_IMAGE_SUFFIX_MARKER:-c12-ro-lab-${C14_IMAGE_TAG}}"
C14_HOMOLOG_PRIVATE_VALUES="${C14_HOMOLOG_PRIVATE_VALUES:-${C13_HOMOLOG_PRIVATE_VALUES:-}}"
C14_LAB_FIRSTBOOT_CONF="${C14_LAB_FIRSTBOOT_CONF:-${C13_LAB_FIRSTBOOT_CONF:-}}"
C14_CONFIRM_PRIVATE_HOMOLOG_IMAGE="${C14_CONFIRM_PRIVATE_HOMOLOG_IMAGE:-0}"
C14_2_1_RUN_ROOT="${C14_2_1_RUN_ROOT:-/tmp/dadooh-c14-2-1-shipping-homolog}"
C14_2_1_TIMESTAMP="${C14_2_1_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
C14_2_1_OUT_DIR="${C14_2_1_OUT_DIR:-${C14_2_1_RUN_ROOT}/${C14_2_1_TIMESTAMP}-c14-2-1-shipping-homolog}"
MODE="prepare-only"

usage() {
  sed -n '2,46p' "$0"
}

# --- Arg parse -------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --homolog-private-values) shift; C14_HOMOLOG_PRIVATE_VALUES="${1:-}";;
    --homolog-private-values=*) C14_HOMOLOG_PRIVATE_VALUES="${1#*=}";;
    --lab-firstboot-conf) shift; C14_LAB_FIRSTBOOT_CONF="${1:-}";;
    --lab-firstboot-conf=*) C14_LAB_FIRSTBOOT_CONF="${1#*=}";;
    --mode) shift; MODE="${1:-prepare-only}";;
    --mode=*) MODE="${1#*=}";;
    --confirm-private-homolog-image) C14_CONFIRM_PRIVATE_HOMOLOG_IMAGE=1;;
    --image-tag=*) C14_IMAGE_TAG="${1#*=}";;
    --image-version=*) C14_IMAGE_VERSION="${1#*=}";;
    -h|--help) usage; exit 0;;
    *) echo "FATAL: unknown arg: $1" >&2; exit 2;;
  esac
  shift
done

# --- Validation ------------------------------------------------------------
say() { printf '[run_c14_2_1] %s\n' "$*"; }
die() { printf '[run_c14_2_1] FATAL %s\n' "$*" >&2; exit 1; }

if [[ "$MODE" != "prepare-only" && "$MODE" != "check-build-env" \
   && "$MODE" != "summary" ]]; then
  if [[ -z "$C14_HOMOLOG_PRIVATE_VALUES" ]]; then
    die "missing --homolog-private-values <path-outside-repo>"
  fi
  if [[ ! -f "$C14_HOMOLOG_PRIVATE_VALUES" ]]; then
    die "homolog private values file does not exist: $C14_HOMOLOG_PRIVATE_VALUES"
  fi
  if [[ -z "$C14_LAB_FIRSTBOOT_CONF" ]]; then
    die "missing --lab-firstboot-conf <path-outside-repo>"
  fi
  if [[ ! -f "$C14_LAB_FIRSTBOOT_CONF" ]]; then
    die "lab firstboot conf does not exist: $C14_LAB_FIRSTBOOT_CONF"
  fi
fi

# Refuse to start if the private files are inside the repo root (defensive).
case "$C14_HOMOLOG_PRIVATE_VALUES" in
  "$REPO_ROOT"/*)
    die "private seed must NOT live inside the repo: $C14_HOMOLOG_PRIVATE_VALUES" ;;
esac
case "$C14_LAB_FIRSTBOOT_CONF" in
  "$REPO_ROOT"/*)
    die "lab firstboot conf must NOT live inside the repo: $C14_LAB_FIRSTBOOT_CONF" ;;
esac

mkdir -p "$C14_2_1_OUT_DIR"

# --- Compose env for inner runner -----------------------------------------
export C13_IMAGE_TAG="$C14_IMAGE_TAG"
export C13_IMAGE_VERSION="$C14_IMAGE_VERSION"
export C12_IMAGE_SUFFIX_MARKER="$C14_IMAGE_SUFFIX_MARKER"
export C13_EMBED_HOMOLOG_PRIVATE_VALUES=1
export C13_HOMOLOG_PRIVATE_VALUES="$C14_HOMOLOG_PRIVATE_VALUES"
export C13_LAB_FIRSTBOOT_CONF="$C14_LAB_FIRSTBOOT_CONF"
export C13_LAB_FIRSTBOOT_CONF_KIND="private"
export C13_REQUIRE_LAB_FIRSTBOOT_CONF=1
export C13_KERNEL_OVERLAYFS_BUILTIN=1
export C13_CONFIRM_PRIVATE_HOMOLOG_IMAGE="$C14_CONFIRM_PRIVATE_HOMOLOG_IMAGE"
# Direct the inner runner's run dir at our own out dir so logs sit together.
export C12_1_OUT_DIR="$C14_2_1_OUT_DIR/inner-c12-1"
export C12_1_RUN_ROOT="$C14_2_1_RUN_ROOT/inner-c12-1"
export C12_1_TIMESTAMP="$C14_2_1_TIMESTAMP"

say "image_tag=$C14_IMAGE_TAG"
say "image_version=$C14_IMAGE_VERSION"
say "image_suffix_marker=$C14_IMAGE_SUFFIX_MARKER"
say "homolog_private_values=<set, content NOT printed>"
say "lab_firstboot_conf=<set, content NOT printed>"
say "mode=$MODE"
say "out_dir=$C14_2_1_OUT_DIR"

run_inner() {
  local m="$1"
  say "--- inner runner: --$m ---"
  "$INNER_RUNNER" "--$m"
}

case "$MODE" in
  prepare-only)
    run_inner prepare-only
    ;;
  full)
    run_inner check-build-env
    run_inner clone-or-check-armbian-build
    run_inner prepare-userpatches
    run_inner build-image
    run_inner collect-artifacts
    run_inner summary
    ;;
  *)
    run_inner "$MODE"
    ;;
esac

# Print a sanitised post-run summary
{
  echo "c14_2_1_status=$(test "$MODE" = "full" -o "$MODE" = "collect-artifacts" \
                        -o "$MODE" = "summary" && echo "ran" || echo "$MODE")"
  echo "c14_image_tag=${C14_IMAGE_TAG}"
  echo "c14_image_version=${C14_IMAGE_VERSION}"
  echo "c14_image_suffix_marker=${C14_IMAGE_SUFFIX_MARKER}"
  echo "homologation_shipping_image=true"
  echo "artifact_private=true"
  echo "final_image=false"
  echo "not_for_production=true"
  echo "not_for_distribution=true"
  echo "pull_updater_embedded=true"
  echo "pull_update_timer_enabled=true"
  echo "update_timer_on_boot=10min"
  echo "update_timer_interval=6h"
  echo "update_timer_randomized_delay=10min"
  echo "github_repo=dadoohai/kiosky-player"
  echo "update_channel=homologation"
  echo "git_pull_used_on_device=false"
  echo "apt_update_executed=false"
  echo "apt_upgrade_executed=false"
  echo "pip_install_executed=false"
  echo "kernel_config_changed=false"
  echo "kernel_recompiled=unknown"
  echo "c12_readonly_blocked=true"
  echo "c12_4_blocked=true"
} > "$C14_2_1_OUT_DIR/c14-2-1-summary.txt"

say "summary=$C14_2_1_OUT_DIR/c14-2-1-summary.txt"
