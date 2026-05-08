#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARM_BUILD_DIR="${ARM_BUILD_DIR:-/home/builder/totem-os/armbian-build-v25.11}"
KIOSKY_PLAYER_DIR="${KIOSKY_PLAYER_DIR:-/home/builder/kiosky-player}"
USERPATCHES_TEMPLATE="$REPO_ROOT/scripts/build/userpatches-c12-image-lab"
LAB_FIRSTBOOT_CONF="${C12_LAB_FIRSTBOOT_CONF:-}"
LAB_FIRSTBOOT_CONF_KIND="${C12_LAB_FIRSTBOOT_CONF_KIND:-private}"
REQUIRE_LAB_FIRSTBOOT_CONF="${C12_REQUIRE_LAB_FIRSTBOOT_CONF:-0}"
KERNEL_OVERLAYFS_BUILTIN="${C12_KERNEL_OVERLAYFS_BUILTIN:-0}"
KERNEL_CONFIG_NAME="${C12_KERNEL_CONFIG_NAME:-linux-sunxi64-current}"
KERNEL_CONFIG_SOURCE="${C12_KERNEL_CONFIG_SOURCE:-$ARM_BUILD_DIR/config/kernel/$KERNEL_CONFIG_NAME.config}"
RUN_ROOT="${C12_1_RUN_ROOT:-/tmp/dadooh-c12-1-image-lab-readonly}"
TIMESTAMP="${C12_1_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${C12_1_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-1-build-image-lab-readonly}"
CONFIG_NAME="c12-image-lab-readonly"
IMAGE_TAG="${C12_IMAGE_TAG:-}"
IMAGE_VERSION="${C12_IMAGE_VERSION:-${IMAGE_TAG//-/.}}"
if [ -z "$IMAGE_VERSION" ]; then
  IMAGE_VERSION="c12.1.11"
fi
if [ -n "$IMAGE_TAG" ]; then
  IMAGE_SUFFIX_MARKER="${C12_IMAGE_SUFFIX_MARKER:-c12-ro-lab-$IMAGE_TAG}"
else
  IMAGE_SUFFIX_MARKER="${C12_IMAGE_SUFFIX_MARKER:-c12-ro-lab-${IMAGE_VERSION//./-}}"
fi
EXPECTED_ARMBIAN_REF="e172058"
EXPECTED_KIOSKY_COMMIT="c71318a64c08e47b8426f1388b95f21364d57123"

lab_firstboot_mode() {
  case "$LAB_FIRSTBOOT_CONF_KIND" in
    synthetic) printf 'synthetic_no_secret\n' ;;
    private) printf 'private_disposable_lab\n' ;;
    *) printf 'unknown\n' ;;
  esac
}

lab_firstboot_artifact_private() {
  [ "$LAB_FIRSTBOOT_CONF_KIND" = "private" ] && printf 'true\n' || printf 'false\n'
}

lab_firstboot_requires_manual_firstboot() {
  [ "$LAB_FIRSTBOOT_CONF_KIND" = "synthetic" ] && printf 'true\n' || printf 'false\n'
}

lab_firstboot_ready_for_ssh_validation() {
  [ "$LAB_FIRSTBOOT_CONF_KIND" = "private" ] && printf 'true\n' || printf 'false\n'
}

usage() {
  cat <<'USAGE'
Usage:
  run_c12_1_build_image_lab_readonly.sh [mode]

Modes:
  --prepare-only
  --check-build-env
  --clone-or-check-armbian-build
  --prepare-userpatches
  --build-image
  --collect-artifacts
  --summary

Environment:
  ARM_BUILD_DIR=/home/builder/totem-os/armbian-build-v25.11
  KIOSKY_PLAYER_DIR=/home/builder/kiosky-player
  C12_1_OUT_DIR=/tmp/...
  C12_LAB_FIRSTBOOT_CONF=/private/path/firstboot.conf
      Private Armbian first-login preset for lab images. Required for the next
      board-bootable image-lab because C12.3.2 proved that the firstboot gate
      alone leaves no useful SSH/UI path on a fresh card.
  C12_LAB_FIRSTBOOT_CONF_KIND=private|synthetic
      Classify the provided firstboot.conf without printing values. Use
      synthetic for non-secret fixtures created only to exercise image-lab
      bootstrap behavior.
  C12_REQUIRE_LAB_FIRSTBOOT_CONF=1
      Refuse to build if C12_LAB_FIRSTBOOT_CONF is missing. Use this for
      C12.1.4+ board-validation images.
  C12_IMAGE_VERSION=c12.1.11
      Image-lab version marker used in artifact names and manifests.
  C12_IMAGE_TAG=c12-1-9
      Explicit artifact tag required for new builds. The script refuses to
      build when this is absent, and refuses to overwrite an existing image
      whose name already contains the resolved tag.
  C12_KERNEL_OVERLAYFS_BUILTIN=1
      Prepare a full Armbian kernel config userpatch with CONFIG_OVERLAY_FS=y.
      This is the C12.1.11 image-lab experiment; it keeps overlayroot but
      avoids loading overlay.ko as a module in initramfs.
  C12_KERNEL_CONFIG_NAME=linux-sunxi64-current
      Kernel config name expected by Armbian Build. The generated userpatch is
      userpatches/$C12_KERNEL_CONFIG_NAME.config.
  C12_KERNEL_CONFIG_SOURCE=/path/to/full/kernel/config
      Optional source for the complete kernel config. Defaults to Armbian
      Build's config/kernel/$C12_KERNEL_CONFIG_NAME.config.

Rules:
  - local build only;
  - no board SSH;
  - no card writing;
  - no production image claim;
  - no real config, secrets, SSID/password, media cache or raw logs in artifacts.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --check-build-env) MODE="check-build-env" ;;
    --clone-or-check-armbian-build) MODE="clone-or-check-armbian-build" ;;
    --prepare-userpatches) MODE="prepare-userpatches" ;;
    --build-image) MODE="build-image" ;;
    --collect-artifacts) MODE="collect-artifacts" ;;
    --summary) MODE="summary" ;;
    --help|-h) usage; exit 0 ;;
    *) echo "error: unsupported argument: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

case "$OUT_DIR" in
  /tmp/*) ;;
  *) echo "error: C12_1_OUT_DIR must be under /tmp" >&2; exit 2 ;;
esac

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"

repo_head() {
  git -C "$REPO_ROOT" rev-parse HEAD
}

repo_branch() {
  git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD
}

ensure_clean_repo_for_build() {
  git -C "$REPO_ROOT" diff --check
}

check_armbian_build() {
  if [ ! -d "$ARM_BUILD_DIR/.git" ]; then
    echo "error: Armbian Build tree not found at $ARM_BUILD_DIR" >&2
    echo "blocker=armbian_build_tree_missing" > "$OUT_DIR/blocker.env"
    exit 1
  fi
  local ref branch status
  ref="$(git -C "$ARM_BUILD_DIR" rev-parse --short HEAD)"
  branch="$(git -C "$ARM_BUILD_DIR" rev-parse --abbrev-ref HEAD)"
  status="$(git -C "$ARM_BUILD_DIR" status --short)"
  {
    printf 'armbian_build_dir=%s\n' "$ARM_BUILD_DIR"
    printf 'armbian_build_ref=%s\n' "$ref"
    printf 'armbian_build_branch=%s\n' "$branch"
    printf 'armbian_build_dirty=%s\n' "$([ -n "$status" ] && echo true || echo false)"
  } > "$OUT_DIR/armbian-build.env"
  if [ "$ref" != "$EXPECTED_ARMBIAN_REF" ]; then
    echo "error: expected Armbian Build $EXPECTED_ARMBIAN_REF, got $ref" >&2
    echo "blocker=armbian_build_ref_mismatch" > "$OUT_DIR/blocker.env"
    exit 1
  fi
}

check_kiosky_player() {
  if [ ! -d "$KIOSKY_PLAYER_DIR/.git" ]; then
    echo "error: kiosky-player repo not found at $KIOSKY_PLAYER_DIR" >&2
    echo "blocker=kiosky_player_tree_missing" > "$OUT_DIR/blocker.env"
    exit 1
  fi
  local ref status
  ref="$(git -C "$KIOSKY_PLAYER_DIR" rev-parse HEAD)"
  status="$(git -C "$KIOSKY_PLAYER_DIR" status --short)"
  {
    printf 'kiosky_player_dir=%s\n' "$KIOSKY_PLAYER_DIR"
    printf 'kiosky_player_commit=%s\n' "$ref"
    printf 'kiosky_player_dirty=%s\n' "$([ -n "$status" ] && echo true || echo false)"
  } > "$OUT_DIR/kiosky-player.env"
  if [ "$ref" != "$EXPECTED_KIOSKY_COMMIT" ]; then
    echo "error: expected kiosky-player $EXPECTED_KIOSKY_COMMIT, got $ref" >&2
    echo "blocker=kiosky_player_ref_mismatch" > "$OUT_DIR/blocker.env"
    exit 1
  fi
  if [ -n "$status" ]; then
    echo "error: kiosky-player tree is dirty; refusing to embed it" >&2
    echo "blocker=kiosky_player_dirty" > "$OUT_DIR/blocker.env"
    exit 1
  fi
}

check_armbian_python_tools() {
  local site_packages="$ARM_BUILD_DIR/cache/pip/base/lib/python3.12/site-packages"
  if [ ! -d "$site_packages" ]; then
    echo "error: Armbian Build pip cache missing at $site_packages" >&2
    echo "blocker=armbian_python_tools_cache_missing" > "$OUT_DIR/blocker.env"
    exit 1
  fi
  if ! PYTHONPATH="$site_packages" python3 - <<'PY'
import pygments  # noqa: F401
import rich.syntax  # noqa: F401
PY
  then
    echo "error: Armbian Build Python tools cache is missing pygments/rich.syntax dependencies" >&2
    echo "blocker=armbian_python_tools_missing_pygments" > "$OUT_DIR/blocker.env"
    exit 1
  fi
}

require_explicit_image_tag() {
  if [ -z "$IMAGE_TAG" ]; then
    echo "error: C12_IMAGE_TAG is required for image builds, for example C12_IMAGE_TAG=c12-1-9" >&2
    echo "blocker=c12_image_tag_missing" > "$OUT_DIR/blocker.env"
    exit 1
  fi
  case "$IMAGE_TAG" in
    *[!A-Za-z0-9._-]*)
      echo "error: C12_IMAGE_TAG contains unsupported characters" >&2
      echo "blocker=c12_image_tag_invalid" > "$OUT_DIR/blocker.env"
      exit 1
      ;;
  esac
}

ensure_image_tag_available() {
  require_explicit_image_tag
  local existing
  existing="$(find "$ARM_BUILD_DIR/output/images" -maxdepth 1 -type f -name "*$IMAGE_SUFFIX_MARKER*.img" -print -quit 2>/dev/null || true)"
  if [ -n "$existing" ]; then
    echo "error: image artifact already exists for tag $IMAGE_TAG" >&2
    echo "blocker=c12_image_tag_already_exists" > "$OUT_DIR/blocker.env"
    {
      printf 'image_tag=%s\n' "$IMAGE_TAG"
      printf 'image_suffix_marker=%s\n' "$IMAGE_SUFFIX_MARKER"
      printf 'existing_image=%s\n' "$existing"
    } > "$OUT_DIR/image-tag-conflict.env"
    exit 1
  fi
}

check_build_env() {
  if ! command -v docker >/dev/null; then
    echo "error: docker command not found; Armbian Build image-lab build cannot run in this environment" >&2
    echo "blocker=docker_missing" > "$OUT_DIR/blocker.env"
    exit 1
  fi
  if ! docker info >/dev/null; then
    echo "error: docker daemon unavailable; Armbian Build image-lab build cannot run in this environment" >&2
    echo "blocker=docker_daemon_unavailable" > "$OUT_DIR/blocker.env"
    exit 1
  fi
  command -v git >/dev/null
  command -v rsync >/dev/null
  check_armbian_python_tools
  local free_kb
  free_kb="$(df -Pk "$ARM_BUILD_DIR" | awk 'NR==2 {print $4}')"
  if [ "${free_kb:-0}" -lt 52428800 ]; then
    echo "error: less than 50GB free for image build" >&2
    echo "blocker=build_disk_space_low" > "$OUT_DIR/blocker.env"
    exit 1
  fi
  {
    printf 'docker_version=%s\n' "$(docker --version | sed 's/,//g')"
    printf 'docker_server=%s\n' "$(docker info --format '{{.ServerVersion}}')"
    printf 'nproc=%s\n' "$(nproc)"
    printf 'free_kb=%s\n' "$free_kb"
  } > "$OUT_DIR/build-env.env"
}

prepare_overlay_repo() {
  local target="$ARM_BUILD_DIR/userpatches/overlay/orange_pi_totem"
  rm -rf "$target"
  mkdir -p "$target/scripts/board"
  install -m 0755 "$REPO_ROOT/scripts/board/install_totem_appliance.sh" "$target/scripts/board/install_totem_appliance.sh"
  install -m 0755 "$REPO_ROOT/scripts/board/verify_totem_appliance.sh" "$target/scripts/board/verify_totem_appliance.sh"
  install -m 0644 "$REPO_ROOT/scripts/board/totem_appliance_manifest.json" "$target/scripts/board/totem_appliance_manifest.json"
  python3 - "$REPO_ROOT" "$target" <<'PY'
import json
import shutil
import sys
from pathlib import Path

repo = Path(sys.argv[1])
target = Path(sys.argv[2])
manifest = json.loads((repo / "scripts/board/totem_appliance_manifest.json").read_text(encoding="utf-8"))
sources = set()
for section in ("bin_scripts", "extra_files", "systemd_units"):
    for item in manifest.get(section, []):
        source = item.get("source")
        if source:
            sources.add(source)
for source in sorted(sources):
    src = repo / source
    if not src.exists() or not src.is_file():
        raise SystemExit(f"missing manifest source: {source}")
    dst = target / source
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
PY
  mkdir -p "$target/releases/installable-rc" "$target/releases/image-lab-readonly"
  install -m 0644 "$REPO_ROOT/releases/installable-rc/manifest.md" \
    "$target/releases/installable-rc/manifest.md"
  install -m 0644 "$REPO_ROOT/releases/image-lab-readonly/manifest.md" \
    "$target/releases/image-lab-readonly/manifest.md"
  printf '%s\n' "$(repo_head)" > "$target/.orange_pi_totem_commit"
  printf '%s\n' "$(repo_branch)" > "$target/.orange_pi_totem_branch"
  git -C "$REPO_ROOT" status --short | wc -l > "$target/.orange_pi_totem_dirty_entries"
}

prepare_overlay_kiosky() {
  local target="$ARM_BUILD_DIR/userpatches/overlay/kiosky-player"
  rm -rf "$target"
  mkdir -p "$target/scripts"
  install -m 0644 "$KIOSKY_PLAYER_DIR/kiosk.py" "$target/kiosk.py"
  install -m 0644 "$KIOSKY_PLAYER_DIR/requirements.txt" "$target/requirements.txt"
  if [ -f "$KIOSKY_PLAYER_DIR/scripts/run.sh" ]; then
    install -m 0755 "$KIOSKY_PLAYER_DIR/scripts/run.sh" "$target/scripts/run.sh"
  fi
  printf '%s\n' "$EXPECTED_KIOSKY_COMMIT" > "$target/.kiosky_player_commit"
}

prepare_overlay_image_lab() {
  local target="$ARM_BUILD_DIR/userpatches/overlay/c12-image-lab"
  rm -rf "$target"
  mkdir -p "$target"
  cp -a "$USERPATCHES_TEMPLATE/lab-rootfs" "$target/rootfs"
  install -d -m 0755 "$target/rootfs/etc/dadooh"
  if [ -f "$OUT_DIR/firstboot-policy.env" ]; then
    grep -E '^(lab_firstboot_mode|artifact_private|final_image|firstboot_conf_committed|firstboot_conf_contents_published|ready_for_c12_2_7_card_write|ready_for_c12_3_boot_ssh_validation|require_manual_firstboot)=' \
      "$OUT_DIR/firstboot-policy.env" > "$target/rootfs/etc/dadooh/c12-lab-firstboot-mode"
  else
    {
      printf 'lab_firstboot_mode=unknown\n'
      printf 'artifact_private=false\n'
      printf 'final_image=false\n'
      printf 'firstboot_conf_committed=false\n'
      printf 'firstboot_conf_contents_published=false\n'
      printf 'ready_for_c12_2_7_card_write=false\n'
      printf 'ready_for_c12_3_boot_ssh_validation=false\n'
      printf 'require_manual_firstboot=true\n'
    } > "$target/rootfs/etc/dadooh/c12-lab-firstboot-mode"
  fi
  find "$target/rootfs" -type d -exec chmod 0755 {} +
  find "$target/rootfs" -type f -exec chmod 0644 {} +
  find "$target/rootfs" -type f -name '*.sh' -exec chmod 0755 {} +
}

prepare_lab_firstboot_conf() {
  local target="$ARM_BUILD_DIR/userpatches/firstboot.conf"
  rm -f "$target"
  case "$REQUIRE_LAB_FIRSTBOOT_CONF" in
    0|1) ;;
    *) echo "error: C12_REQUIRE_LAB_FIRSTBOOT_CONF must be 0 or 1" >&2; exit 2 ;;
  esac
  case "$LAB_FIRSTBOOT_CONF_KIND" in
    private|synthetic) ;;
    *) echo "error: C12_LAB_FIRSTBOOT_CONF_KIND must be private or synthetic" >&2; exit 2 ;;
  esac
  if [ -z "$LAB_FIRSTBOOT_CONF" ]; then
    if [ "$REQUIRE_LAB_FIRSTBOOT_CONF" = "1" ]; then
      echo "error: C12_LAB_FIRSTBOOT_CONF is required for board-bootable image-lab builds" >&2
      echo "blocker=lab_firstboot_conf_missing_required" > "$OUT_DIR/blocker.env"
      exit 1
    fi
    {
      printf 'lab_firstboot_autoconfig=false\n'
      printf 'lab_firstboot_mode=missing\n'
      printf 'lab_firstboot_boot_validatable=false\n'
      printf 'lab_firstboot_conf_required_for_board_boot=true\n'
      printf 'lab_firstboot_policy=not_board_boot_validatable_without_private_autoconfig\n'
      printf 'artifact_private=false\n'
      printf 'final_image=false\n'
      printf 'firstboot_conf_committed=false\n'
      printf 'firstboot_conf_contents_published=false\n'
      printf 'ready_for_c12_2_7_card_write=false\n'
      printf 'ready_for_c12_3_boot_ssh_validation=false\n'
      printf 'require_manual_firstboot=true\n'
      printf 'ready_for_board_boot=false\n'
    } > "$OUT_DIR/firstboot-policy.env"
    return 0
  fi
  if [ ! -f "$LAB_FIRSTBOOT_CONF" ]; then
    echo "error: C12_LAB_FIRSTBOOT_CONF does not exist" >&2
    echo "blocker=lab_firstboot_conf_missing" > "$OUT_DIR/blocker.env"
    exit 1
  fi
  case "$(realpath "$LAB_FIRSTBOOT_CONF")" in
    "$REPO_ROOT"/*)
      echo "error: C12_LAB_FIRSTBOOT_CONF must live outside the repo" >&2
      echo "blocker=lab_firstboot_conf_inside_repo" > "$OUT_DIR/blocker.env"
      exit 1
      ;;
  esac
  python3 - "$LAB_FIRSTBOOT_CONF" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="replace")
required = [
    "PRESET_NET_CHANGE_DEFAULTS",
    "PRESET_NET_ETHERNET_ENABLED",
    "PRESET_NET_WIFI_ENABLED",
    "PRESET_CONNECT_WIRELESS",
    "SET_LANG_BASED_ON_LOCATION",
    "PRESET_LOCALE",
    "PRESET_TIMEZONE",
    "PRESET_USER_SHELL",
    "PRESET_ROOT_PASSWORD",
    "PRESET_USER_NAME",
    "PRESET_USER_PASSWORD",
    "PRESET_DEFAULT_REALNAME",
]
missing = [key for key in required if not re.search(rf"^\s*{re.escape(key)}=", text, re.M)]
if missing:
    raise SystemExit("lab_firstboot_conf_missing_required_keys")

values = {}
for match in re.finditer(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$", text, re.M):
    raw = match.group(2).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        raw = raw[1:-1]
    values[match.group(1)] = raw

for placeholder in (
    "REPLACE_WITH_PRIVATE_LAB_ROOT_PASSWORD",
    "REPLACE_WITH_PRIVATE_LAB_USER_PASSWORD",
    "REPLACE_WITH_PRIVATE_LAB_WIFI_SSID",
    "REPLACE_WITH_PRIVATE_LAB_WIFI_PASSWORD",
    "RootPassword",
    "UserPassword",
    "MySSID",
    "MyWiFiKEY",
):
    if placeholder in text:
        raise SystemExit("lab_firstboot_conf_contains_placeholder")

if values.get("PRESET_NET_CHANGE_DEFAULTS") != "1":
    raise SystemExit("lab_firstboot_conf_must_configure_network")
ethernet_enabled = values.get("PRESET_NET_ETHERNET_ENABLED") == "1"
wifi_enabled = values.get("PRESET_NET_WIFI_ENABLED") == "1"
if not ethernet_enabled and not wifi_enabled:
    raise SystemExit("lab_firstboot_conf_has_no_network_path")
if wifi_enabled:
    for key in ("PRESET_NET_WIFI_SSID", "PRESET_NET_WIFI_KEY", "PRESET_NET_WIFI_COUNTRYCODE"):
        if not values.get(key):
            raise SystemExit("lab_firstboot_conf_missing_wifi_value")
PY
  install -m 0600 "$LAB_FIRSTBOOT_CONF" "$target"
  {
    printf 'lab_firstboot_autoconfig=true\n'
    printf 'lab_firstboot_mode=%s\n' "$(lab_firstboot_mode)"
    printf 'lab_firstboot_boot_validatable=%s\n' "$(lab_firstboot_ready_for_ssh_validation)"
    printf 'lab_firstboot_conf_copied_to_userpatches=true\n'
    printf 'lab_firstboot_conf_source_private=%s\n' "$([ "$LAB_FIRSTBOOT_CONF_KIND" = "private" ] && echo true || echo false)"
    printf 'lab_firstboot_conf_source_synthetic=%s\n' "$([ "$LAB_FIRSTBOOT_CONF_KIND" = "synthetic" ] && echo true || echo false)"
    printf 'lab_firstboot_secret_values_published=false\n'
    printf 'artifact_private=%s\n' "$(lab_firstboot_artifact_private)"
    printf 'final_image=false\n'
    printf 'firstboot_conf_committed=false\n'
    printf 'firstboot_conf_contents_published=false\n'
    printf 'ready_for_c12_2_7_card_write=true\n'
    printf 'ready_for_c12_3_boot_ssh_validation=%s\n' "$(lab_firstboot_ready_for_ssh_validation)"
    printf 'require_manual_firstboot=%s\n' "$(lab_firstboot_requires_manual_firstboot)"
    printf 'lab_firstboot_policy=%s\n' "$([ "$LAB_FIRSTBOOT_CONF_KIND" = "synthetic" ] && echo synthetic_armbian_firstboot_autoconfig_for_lab_boot || echo private_armbian_firstboot_autoconfig_required_for_lab_boot)"
    printf 'ready_for_board_boot=true\n'
  } > "$OUT_DIR/firstboot-policy.env"
}

prepare_kernel_overlayfs_builtin_config() {
  case "$KERNEL_OVERLAYFS_BUILTIN" in
    0|1) ;;
    *) echo "error: C12_KERNEL_OVERLAYFS_BUILTIN must be 0 or 1" >&2; exit 2 ;;
  esac

  local target="$ARM_BUILD_DIR/userpatches/$KERNEL_CONFIG_NAME.config"
  if [ "$KERNEL_OVERLAYFS_BUILTIN" != "1" ]; then
    {
      printf 'kernel_overlayfs_builtin_requested=false\n'
      printf 'kernel_config_userpatch_prepared=false\n'
      printf 'kernel_config_name=%s\n' "$KERNEL_CONFIG_NAME"
      printf 'required_kernel_config=CONFIG_OVERLAY_FS=y\n'
      printf 'ready_for_c12_1_11_build=false\n'
    } > "$OUT_DIR/kernel-config-policy.env"
    return 0
  fi

  if [ "$KERNEL_CONFIG_NAME" != "linux-sunxi64-current" ]; then
    echo "error: unexpected C12_KERNEL_CONFIG_NAME=$KERNEL_CONFIG_NAME" >&2
    echo "blocker=kernel_config_name_mismatch" > "$OUT_DIR/blocker.env"
    exit 1
  fi
  if [ ! -f "$KERNEL_CONFIG_SOURCE" ]; then
    echo "error: kernel config source missing: $KERNEL_CONFIG_SOURCE" >&2
    echo "blocker=kernel_config_source_missing" > "$OUT_DIR/blocker.env"
    exit 1
  fi

  python3 - "$KERNEL_CONFIG_SOURCE" "$target" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
out = []
seen = False
for line in lines:
    if line.startswith("CONFIG_OVERLAY_FS=") or line.startswith("# CONFIG_OVERLAY_FS is not set"):
        if not seen:
            out.append("CONFIG_OVERLAY_FS=y")
            seen = True
        continue
    out.append(line)
if not seen:
    out.append("CONFIG_OVERLAY_FS=y")
text = "\n".join(out) + "\n"
if "CONFIG_OVERLAY_FS=y\n" not in text:
    raise SystemExit("kernel_config_overlayfs_builtin_not_set")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(text, encoding="utf-8")
target.chmod(0o644)
PY

  {
    printf 'kernel_overlayfs_builtin_requested=true\n'
    printf 'kernel_config_userpatch_prepared=true\n'
    printf 'kernel_config_name=%s\n' "$KERNEL_CONFIG_NAME"
    printf 'kernel_config_userpatch=%s\n' "$target"
    printf 'kernel_config_source=armbian_build_config_kernel\n'
    printf 'required_kernel_config=CONFIG_OVERLAY_FS=y\n'
    printf 'kernel_config_overlayfs_builtin=true\n'
    printf 'overlayroot_module_initramfs_path_status=blocked\n'
    printf 'ready_for_c12_1_11_build=true\n'
  } > "$OUT_DIR/kernel-config-policy.env"
}

prepare_userpatches() {
  require_explicit_image_tag
  check_armbian_build
  check_kiosky_player
  install -m 0644 "$USERPATCHES_TEMPLATE/config-c12-image-lab-readonly.conf" \
    "$ARM_BUILD_DIR/userpatches/config-$CONFIG_NAME.conf"
  python3 - "$ARM_BUILD_DIR/userpatches/config-$CONFIG_NAME.conf" "$IMAGE_SUFFIX_MARKER" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
suffix = sys.argv[2]
text = path.read_text(encoding="utf-8")
text = re.sub(
    r'C12_IMAGE_SUFFIX_MARKER:-c12-ro-lab-[A-Za-z0-9_.-]+',
    f'C12_IMAGE_SUFFIX_MARKER:-{suffix}',
    text,
)
path.write_text(text, encoding="utf-8")
PY
  install -m 0755 "$USERPATCHES_TEMPLATE/customize-image.sh" \
    "$ARM_BUILD_DIR/userpatches/customize-image.sh"
  prepare_lab_firstboot_conf
  prepare_kernel_overlayfs_builtin_config
  prepare_overlay_repo
  prepare_overlay_kiosky
  prepare_overlay_image_lab
  find "$ARM_BUILD_DIR/userpatches/overlay" -type f | sort > "$OUT_DIR/userpatches-files.txt"
  {
    printf 'config=%s\n' "$ARM_BUILD_DIR/userpatches/config-$CONFIG_NAME.conf"
    printf 'customize=%s\n' "$ARM_BUILD_DIR/userpatches/customize-image.sh"
    printf 'firstboot_conf_present=%s\n' "$([ -f "$ARM_BUILD_DIR/userpatches/firstboot.conf" ] && echo true || echo false)"
    printf 'kernel_overlayfs_builtin_requested=%s\n' "$KERNEL_OVERLAYFS_BUILTIN"
    printf 'kernel_config_name=%s\n' "$KERNEL_CONFIG_NAME"
    printf 'kernel_config_userpatch_present=%s\n' "$([ -f "$ARM_BUILD_DIR/userpatches/$KERNEL_CONFIG_NAME.config" ] && echo true || echo false)"
    printf 'overlay_repo=%s\n' "$ARM_BUILD_DIR/userpatches/overlay/orange_pi_totem"
    printf 'overlay_kiosky=%s\n' "$ARM_BUILD_DIR/userpatches/overlay/kiosky-player"
  } > "$OUT_DIR/userpatches.env"
}

build_image() {
  prepare_userpatches
  ensure_image_tag_available
  local before_file="$OUT_DIR/images-before.txt"
  local after_file="$OUT_DIR/images-after.txt"
  find "$ARM_BUILD_DIR/output/images" -maxdepth 1 -type f -printf '%T@ %p\n' 2>/dev/null | sort > "$before_file" || true
  (
    cd "$ARM_BUILD_DIR"
    export LANG=C.UTF-8
    export LC_ALL=C.UTF-8
    export TERM=xterm-256color
    export C12_IMAGE_SUFFIX_MARKER="$IMAGE_SUFFIX_MARKER"
    ./compile.sh build "$CONFIG_NAME" PREFER_DOCKER=yes FORCE_USE_RAMDISK=no
  ) 2>&1 | tee "$OUT_DIR/build-wrapper.log"
  find "$ARM_BUILD_DIR/output/images" -maxdepth 1 -type f -printf '%T@ %p\n' 2>/dev/null | sort > "$after_file" || true
}

collect_artifacts() {
  require_explicit_image_tag
  check_armbian_build
  prepare_lab_firstboot_conf
  prepare_kernel_overlayfs_builtin_config
  local image
  image="$(find "$ARM_BUILD_DIR/output/images" -maxdepth 1 -type f -name "*$IMAGE_SUFFIX_MARKER*.img" -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {print $2}')"
  if [ -z "$image" ] || [ ! -f "$image" ]; then
    echo "error: C12 image artifact not found" >&2
    echo "blocker=c12_image_not_found" > "$OUT_DIR/blocker.env"
    exit 1
  fi
  local checksum="$image.sha256"
  sha256sum "$image" > "$checksum"
  local pkg_manifest="$OUT_DIR/package-manifest.txt"
  {
    printf 'package=overlayroot source=userpatch-c12-image-lab\n'
    printf 'package=mpv source=userpatch-c12-image-lab\n'
    printf 'package=ffmpeg source=userpatch-c12-image-lab\n'
    printf 'package=python3-requests source=userpatch-c12-image-lab\n'
    printf 'package=network-manager source=userpatch-c12-image-lab-or-armbian-networking-stack\n'
    find "$ARM_BUILD_DIR/output/debs" -maxdepth 1 -type f -printf 'debian_artifact=%f\n' 2>/dev/null | sort
  } > "$pkg_manifest"
  local build_log
  build_log="$(find "$ARM_BUILD_DIR/output/logs" -maxdepth 1 -type f -name 'log-build-*.log' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {print $2}')"
  local integration_manifest="$OUT_DIR/read-only-integration-manifest.txt"
  local rootfs_validation="$OUT_DIR/rootfs-validation.env"
  local initramfs_after_overlayroot="unknown"
  local initramfs_source="unknown"
  local lab_firstboot_autoconfig="false"
  local lab_firstboot_boot_validatable="false"
  local lab_firstboot_mode="unknown"
  local lab_firstboot_policy="unknown"
  local ready_for_board_boot="false"
  local ready_for_c12_2_7_card_write="false"
  local ready_for_c12_3_boot_ssh_validation="false"
  local require_manual_firstboot="true"
  local artifact_private="false"
  local firstboot_conf_committed="false"
  local firstboot_conf_contents_published="false"
  if [ -f "$OUT_DIR/firstboot-policy.env" ]; then
    # shellcheck disable=SC1090
    source "$OUT_DIR/firstboot-policy.env"
  fi
  if [ -f "$OUT_DIR/kernel-config-policy.env" ]; then
    # shellcheck disable=SC1090
    source "$OUT_DIR/kernel-config-policy.env"
  fi
  python3 "$REPO_ROOT/scripts/build/inspect_c12_image_rootfs.py" \
    "$image" \
    --require-lab-bootstrap-service \
    --out "$rootfs_validation"
  # shellcheck disable=SC1090
  source "$rootfs_validation"
  if [ -n "${build_log:-}" ] &&
    grep -q 'Installing AGGREGATED_PACKAGES_IMAGE packages.*overlayroot' "$build_log" &&
    grep -q 'Updated initramfs' "$build_log"; then
    initramfs_after_overlayroot="true"
    initramfs_source="updated_initramfs"
  elif [ -n "${build_log:-}" ] &&
    grep -q 'Installing AGGREGATED_PACKAGES_IMAGE packages.*overlayroot' "$build_log" &&
    grep -q 'initrd cache hit' "$build_log" &&
    grep -q '/usr/share/initramfs-tools/hooks/overlayroot' "$ARM_BUILD_DIR/cache/initrd/initrd.manifest-6.12.58-current-sunxi64.last.manifest" &&
    grep -q '/usr/share/initramfs-tools/scripts/init-bottom/overlayroot' "$ARM_BUILD_DIR/cache/initrd/initrd.manifest-6.12.58-current-sunxi64.last.manifest"; then
    initramfs_after_overlayroot="true"
    initramfs_source="cache_hit_with_overlayroot_hooks"
  fi
  {
    printf 'overlayroot_included=%s\n' "$(grep -q '^package=overlayroot ' "$pkg_manifest" && echo true || echo false)"
    printf 'image_version=%s\n' "$IMAGE_VERSION"
    printf 'image_suffix_c12_ro_lab=%s\n' "$(basename "$image" | grep -q 'c12-ro-lab' && echo true || echo false)"
    printf 'image_suffix_version_marker=%s\n' "$(basename "$image" | grep -q "$IMAGE_SUFFIX_MARKER" && echo true || echo false)"
    printf 'initramfs_generated_after_overlayroot=%s\n' "$initramfs_after_overlayroot"
    printf 'initramfs_source=%s\n' "$initramfs_source"
    printf 'initrd_img_exists=%s\n' "$initrd_img_exists"
    printf 'initrd_contains_overlayroot_hook=%s\n' "$initrd_contains_overlayroot_hook"
    printf 'initrd_contains_overlay_module=%s\n' "$initrd_contains_overlay_module"
    printf 'initrd_contains_overlay_module_effective_path=%s\n' "$initrd_contains_overlay_module_effective_path"
    printf 'initrd_contains_overlay_load_hook=%s\n' "$initrd_contains_overlay_load_hook"
    printf 'initrd_contains_c12_overlayroot_marker=%s\n' "$initrd_contains_c12_overlayroot_marker"
    printf 'initrd_contains_c12_overlay_module_path_marker=%s\n' "$initrd_contains_c12_overlay_module_path_marker"
    printf 'uinitrd_exists=%s\n' "$uinitrd_exists"
    printf 'uinitrd_nonempty=%s\n' "$uinitrd_nonempty"
    printf 'uinitrd_payload_extracted=%s\n' "$uinitrd_payload_extracted"
    printf 'uinitrd_payload_matches_initrd_img=%s\n' "$uinitrd_payload_matches_initrd_img"
    printf 'uinitrd_contains_overlayroot_hook=%s\n' "$uinitrd_contains_overlayroot_hook"
    printf 'uinitrd_contains_overlay_module=%s\n' "$uinitrd_contains_overlay_module"
    printf 'uinitrd_contains_overlay_module_effective_path=%s\n' "$uinitrd_contains_overlay_module_effective_path"
    printf 'uinitrd_contains_overlay_load_hook=%s\n' "$uinitrd_contains_overlay_load_hook"
    printf 'uinitrd_contains_c12_overlayroot_marker=%s\n' "$uinitrd_contains_c12_overlayroot_marker"
    printf 'uinitrd_contains_c12_overlay_module_path_marker=%s\n' "$uinitrd_contains_c12_overlay_module_path_marker"
    printf 'uinitrd_generated_after_overlayroot=%s\n' "$uinitrd_generated_after_overlayroot"
    printf 'uinitrd_generated_after_initrd_img=%s\n' "$uinitrd_generated_after_initrd_img"
    printf 'boot_script_uses_uinitrd=%s\n' "$boot_script_uses_uinitrd"
    printf 'effective_boot_initramfs_valid=%s\n' "$effective_boot_initramfs_valid"
    printf 'initrd_lib_symlink_to_usr_lib=%s\n' "$initrd_lib_symlink_to_usr_lib"
    printf 'uinitrd_lib_symlink_to_usr_lib=%s\n' "$uinitrd_lib_symlink_to_usr_lib"
    printf 'effective_initramfs_lib_symlink_to_usr_lib=%s\n' "$effective_initramfs_lib_symlink_to_usr_lib"
    printf 'overlay_module_effective_path_present=%s\n' "$overlay_module_effective_path_present"
    printf 'overlay_module_usr_path_present=%s\n' "$overlay_module_usr_path_present"
    printf 'modules_dep_effective_path_present=%s\n' "$modules_dep_effective_path_present"
    printf 'modules_alias_effective_path_present=%s\n' "$modules_alias_effective_path_present"
    printf 'modules_dep_references_overlay=%s\n' "$modules_dep_references_overlay"
    printf 'modprobe_present_in_initramfs=%s\n' "$modprobe_present_in_initramfs"
    printf 'insmod_present_in_initramfs=%s\n' "$insmod_present_in_initramfs"
    printf 'overlay_module_discoverable_in_initramfs=%s\n' "$overlay_module_discoverable_in_initramfs"
    printf 'overlay_module_discovery_method=%s\n' "$overlay_module_discovery_method"
    printf 'fallback_hook_dynamic_path=%s\n' "$fallback_hook_dynamic_path"
    printf 'overlay_load_hook_uses_effective_path=%s\n' "$overlay_load_hook_uses_effective_path"
    printf 'effective_boot_initramfs_overlay_resolvable=%s\n' "$effective_boot_initramfs_overlay_resolvable"
    printf 'kernel_overlayfs_builtin_required=true\n'
    printf 'kernel_overlayfs_builtin_requested=%s\n' "${kernel_overlayfs_builtin_requested:-false}"
    printf 'kernel_config_name=%s\n' "${kernel_config_name:-$KERNEL_CONFIG_NAME}"
    printf 'kernel_config_userpatch_prepared=%s\n' "${kernel_config_userpatch_prepared:-false}"
    printf 'kernel_config_overlayfs_builtin=%s\n' "${kernel_config_overlayfs_builtin:-false}"
    printf 'rootfs_kernel_config_overlayfs_builtin=%s\n' "$kernel_config_overlayfs_builtin"
    printf 'overlayroot_module_initramfs_path_status=%s\n' "${overlayroot_module_initramfs_path_status:-blocked}"
    printf 'overlayroot_with_overlayfs_builtin_next=true\n'
    printf 'overlay_module_required=false\n'
    printf 'overlayfs_builtin_expected=true\n'
    printf 'root_write_blocked_not_required=true\n'
    printf 'readonly_semantics_expected=overlayroot_tmpfs\n'
    printf 'root_test_write_nonpersistent_required=true\n'
    printf 'data_test_write_persistent_required=true\n'
    printf 'modular_overlay_fallback_hooks_present=%s\n' "$modular_overlay_fallback_hooks_present"
    printf 'diagnostic_initramfs_hooks_present=%s\n' "$diagnostic_initramfs_hooks_present"
    printf 'readonly_semantics_validation_required=true\n'
    printf 'firstboot_gate_included=true\n'
    printf 'rootfs_firstboot_autoconfig_proven=%s\n' "$rootfs_firstboot_autoconfig_proven"
    printf 'lab_firstboot_bootstrap_service_included=%s\n' "$lab_bootstrap_script_present"
    printf 'lab_firstboot_bootstrap_service_enabled=%s\n' "$lab_bootstrap_enabled"
    printf 'lab_firstboot_bootstrap_service_ordered_before_gate=%s\n' "$lab_bootstrap_runs_before_gate"
    printf 'gate_expected_path_matches=%s\n' "$gate_expected_path_matches"
    printf 'open_settings_cleanup_included=true\n'
    printf 'settings_trigger_stale_lock_cleanup_included=true\n'
    printf 'read_only_assertion_required=true\n'
    printf 'lab_firstboot_autoconfig=%s\n' "$lab_firstboot_autoconfig"
    printf 'lab_firstboot_mode=%s\n' "$lab_firstboot_mode"
    printf 'lab_firstboot_boot_validatable=%s\n' "$lab_firstboot_boot_validatable"
    printf 'artifact_private=%s\n' "$artifact_private"
    printf 'final_image=false\n'
    printf 'firstboot_conf_committed=%s\n' "$firstboot_conf_committed"
    printf 'firstboot_conf_contents_published=%s\n' "$firstboot_conf_contents_published"
    printf 'ready_for_c12_2_7_card_write=%s\n' "$ready_for_c12_2_7_card_write"
    printf 'ready_for_c12_3_boot_ssh_validation=%s\n' "$ready_for_c12_3_boot_ssh_validation"
    printf 'require_manual_firstboot=%s\n' "$require_manual_firstboot"
    printf 'rootfs_ready_for_card_write=%s\n' "$ready_for_card_write_by_rootfs"
    printf 'lab_firstboot_policy=%s\n' "$lab_firstboot_policy"
    printf 'ready_for_board_boot=%s\n' "$ready_for_card_write_by_rootfs"
    printf 'card_written=false\n'
    printf 'boards_touched=false\n'
  } > "$integration_manifest"
  {
    printf 'image_version=%s\n' "$IMAGE_VERSION"
    printf 'image_file=%s\n' "$image"
    printf 'image_checksum_file=%s\n' "$checksum"
    printf 'build_log_file=%s\n' "${build_log:-unknown}"
    printf 'package_manifest_file=%s\n' "$pkg_manifest"
    printf 'integration_manifest_file=%s\n' "$integration_manifest"
    printf 'rootfs_validation_file=%s\n' "$rootfs_validation"
    printf 'orange_pi_totem_commit=%s\n' "$(repo_head)"
    printf 'kiosky_player_pin=%s\n' "$EXPECTED_KIOSKY_COMMIT"
    if [ -f "$OUT_DIR/firstboot-policy.env" ]; then
      cat "$OUT_DIR/firstboot-policy.env"
    fi
    if [ -f "$OUT_DIR/kernel-config-policy.env" ]; then
      cat "$OUT_DIR/kernel-config-policy.env"
    fi
  } > "$OUT_DIR/artifacts.env"
}

summary() {
  mkdir -p "$OUT_DIR"
  {
    printf '# C12.1 image-lab local summary\n\n'
    printf '%s\n' "- repo_head: \`$(repo_head)\`"
    printf '%s\n' "- repo_branch: \`$(repo_branch)\`"
    printf '%s\n' "- armbian_build_dir: \`$ARM_BUILD_DIR\`"
    printf '%s\n' '- kiosky_player_dir: `<sanitized>`'
    printf '%s\n' '- boards_touched: `false`'
    printf '%s\n' '- card_written: `false`'
    printf '%s\n' '- final_image: `false`'
    if [ -f "$OUT_DIR/artifacts.env" ]; then
      sed 's/^/- /' "$OUT_DIR/artifacts.env"
    fi
    if [ -f "$OUT_DIR/blocker.env" ]; then
      sed 's/^/- /' "$OUT_DIR/blocker.env"
    fi
  } > "$OUT_DIR/README.md"
  chmod 600 "$OUT_DIR/README.md"
  printf 'summary=%s\n' "$OUT_DIR/README.md"
}

case "$MODE" in
  prepare-only)
    ensure_clean_repo_for_build
    bash -n "$0"
    bash -n "$REPO_ROOT/scripts/remote/run_c12_1_image_lab_readonly_validation.sh"
    python3 -m json.tool "$REPO_ROOT/scripts/board/totem_appliance_manifest.json" >/dev/null
    python3 -m json.tool "$REPO_ROOT/scripts/board/totem_read_only_policy.json" >/dev/null
    printf 'c12_1_build_prepare_only=ok\n'
    ;;
  check-build-env)
    check_build_env
    check_armbian_build
    check_kiosky_player
    printf 'c12_1_build_env=ok\n'
    ;;
  clone-or-check-armbian-build)
    check_armbian_build
    printf 'armbian_build=ok\n'
    ;;
  prepare-userpatches)
    prepare_userpatches
    printf 'userpatches_prepared=%s\n' "$ARM_BUILD_DIR/userpatches"
    ;;
  build-image)
    check_build_env
    build_image
    collect_artifacts
    summary
    ;;
  collect-artifacts)
    collect_artifacts
    summary
    ;;
  summary)
    summary
    ;;
  *)
    echo "error: unsupported mode: $MODE" >&2
    usage >&2
    exit 2
    ;;
esac
