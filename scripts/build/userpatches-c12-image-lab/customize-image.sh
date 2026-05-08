#!/usr/bin/env bash
set -euo pipefail

RELEASE="${1:-}"
LINUXFAMILY="${2:-}"
BOARD="${3:-}"
BUILD_DESKTOP="${4:-}"
ARCH="${5:-}"

log() {
  printf '[dadooh-c12-image-lab] %s\n' "$*"
}

require_file() {
  if [ ! -f "$1" ]; then
    echo "missing required file: $1" >&2
    exit 1
  fi
}

main() {
  if [ "$BOARD" != "orangepizero3" ]; then
    echo "unsupported board for C12 image lab: $BOARD" >&2
    exit 1
  fi
  if [ "$RELEASE" != "bookworm" ]; then
    echo "unsupported release for C12 image lab: $RELEASE" >&2
    exit 1
  fi

  local overlay_root="/tmp/overlay"
  local repo_root="$overlay_root/orange_pi_totem"
  local app_root="$overlay_root/kiosky-player"
  local lab_root="$overlay_root/c12-image-lab/rootfs"
  local image_lab_state="/data/state/totem-read-only-image-lab"
  local lab_firstboot_marker="/etc/dadooh/image-lab-firstboot-autoconfig.present"

  require_file "$repo_root/scripts/board/install_totem_appliance.sh"
  require_file "$repo_root/scripts/board/totem_appliance_manifest.json"
  require_file "$app_root/kiosk.py"
  require_file "$lab_root/opt/totem/bin/totem_lab_firstboot_autoconfig.sh"
  require_file "$lab_root/etc/systemd/system/totem-lab-firstboot-autoconfig.service"

  log "applying appliance layer"
  "$repo_root/scripts/board/install_totem_appliance.sh" \
    --apply \
    --repo-root "$repo_root" \
    --out-dir /tmp/dadooh-c12-image-lab-installer \
    --manage-running-services

  log "installing pinned kiosky-player tree"
  rm -rf /opt/totem/kiosky-player
  install -d -m 0755 -o root -g root /opt/totem/kiosky-player
  cp -a "$app_root"/. /opt/totem/kiosky-player/
  find /opt/totem/kiosky-player -type d -exec chmod 0755 {} +
  find /opt/totem/kiosky-player -type f -exec chmod 0644 {} +
  find /opt/totem/kiosky-player -type f -name '*.sh' -exec chmod 0755 {} +
  chown -R root:root /opt/totem/kiosky-player

  log "installing image-lab firstboot autoconfig service"
  install -m 0755 -o root -g root \
    "$lab_root/opt/totem/bin/totem_lab_firstboot_autoconfig.sh" \
    /opt/totem/bin/totem_lab_firstboot_autoconfig.sh
  install -m 0644 -o root -g root \
    "$lab_root/etc/systemd/system/totem-lab-firstboot-autoconfig.service" \
    /etc/systemd/system/totem-lab-firstboot-autoconfig.service
  systemctl --no-reload enable totem-lab-firstboot-autoconfig.service

  log "configuring volatile journald policy"
  install -d -m 0755 -o root -g root /etc/systemd/journald.conf.d
  cat > /etc/systemd/journald.conf.d/10-dadooh-volatile.conf <<'EOF'
[Journal]
Storage=volatile
RuntimeMaxUse=32M
ForwardToSyslog=no
EOF
  chmod 0644 /etc/systemd/journald.conf.d/10-dadooh-volatile.conf

  log "configuring overlayroot in image before final Armbian initramfs generation"
  require_file /etc/overlayroot.conf
  cp -a /etc/overlayroot.conf /etc/overlayroot.conf.c12-image-lab-base
  python3 - <<'PY'
from pathlib import Path
path = Path("/etc/overlayroot.conf")
lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
out = []
seen_overlayroot = False
seen_cfgdisk = False
for line in lines:
    stripped = line.strip()
    if stripped.startswith("overlayroot="):
        out.append('overlayroot="tmpfs"')
        seen_overlayroot = True
    elif stripped.startswith("overlayroot_cfgdisk="):
        out.append('overlayroot_cfgdisk="disabled"')
        seen_cfgdisk = True
    else:
        out.append(line)
if not seen_overlayroot:
    out.append('overlayroot="tmpfs"')
if not seen_cfgdisk:
    out.append('overlayroot_cfgdisk="disabled"')
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
  chmod 0644 /etc/overlayroot.conf

  log "ensuring overlayroot boot arg is present"
  require_file /boot/armbianEnv.txt
  python3 - <<'PY'
from pathlib import Path

path = Path("/boot/armbianEnv.txt")
lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
out = []
seen_extraargs = False
for line in lines:
    if line.startswith("extraargs="):
        tokens = [token for token in line.split("=", 1)[1].split() if not token.startswith("overlayroot=")]
        tokens.append("overlayroot=tmpfs")
        out.append("extraargs=" + " ".join(tokens))
        seen_extraargs = True
    else:
        out.append(line)
if not seen_extraargs:
    out.append("extraargs=overlayroot=tmpfs")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
  chmod 0644 /boot/armbianEnv.txt

  log "installing overlayroot initramfs validation marker"
  install -d -m 0755 -o root -g root /etc/initramfs-tools/hooks
  cat > /etc/initramfs-tools/hooks/dadooh-c12-overlayroot-marker <<'EOF'
#!/bin/sh
set -e

case "$1" in
  prereqs) echo ""; exit 0 ;;
esac

mkdir -p "${DESTDIR}/etc/dadooh"
cat > "${DESTDIR}/etc/dadooh/c12-overlayroot-initramfs-marker" <<'MARKER'
c12_overlayroot_initramfs_marker=present
overlayroot_config_expected=tmpfs
MARKER
EOF
  chmod 0755 /etc/initramfs-tools/hooks/dadooh-c12-overlayroot-marker

  log "installing overlay module path fix for initramfs runtime"
  cat > /etc/initramfs-tools/hooks/dadooh-c12-overlay-module-path <<'EOF'
#!/bin/sh
set -e

case "$1" in
  prereqs) echo ""; exit 0 ;;
esac

. /usr/share/initramfs-tools/hook-functions

manual_add_modules overlay || true

KERNEL="${version:-$(uname -r)}"
SRC_BASE="/usr/lib/modules/$KERNEL"
DEST_BASE="${DESTDIR}/lib/modules/$KERNEL"
SRC_OVERLAY_DIR="$SRC_BASE/kernel/fs/overlayfs"
DEST_OVERLAY_DIR="$DEST_BASE/kernel/fs/overlayfs"

mkdir -p "$DEST_OVERLAY_DIR"
copied=false
for module in "$SRC_OVERLAY_DIR"/overlay.ko "$SRC_OVERLAY_DIR"/overlay.ko.*; do
  [ -f "$module" ] || continue
  cp -p "$module" "$DEST_OVERLAY_DIR/$(basename "$module")"
  copied=true
done

mkdir -p "$DEST_BASE"
for metadata in \
  modules.dep modules.dep.bin modules.alias modules.alias.bin \
  modules.builtin modules.builtin.bin modules.builtin.modinfo \
  modules.order modules.symbols modules.symbols.bin modules.softdep; do
  [ -f "$SRC_BASE/$metadata" ] || continue
  cp -p "$SRC_BASE/$metadata" "$DEST_BASE/$metadata"
done

mkdir -p "${DESTDIR}/etc/dadooh"
cat > "${DESTDIR}/etc/dadooh/c12-overlay-module-path-marker" <<MARKER
c12_overlay_module_path_marker=present
kernel=$KERNEL
overlay_module_copied=$copied
expected_path=/lib/modules/$KERNEL/kernel/fs/overlayfs/overlay.ko
discovery_paths=/lib/modules/$KERNEL,/usr/lib/modules/$KERNEL,modules.dep,find
MARKER
EOF
  chmod 0755 /etc/initramfs-tools/hooks/dadooh-c12-overlay-module-path

  log "installing overlay module load hook"
  install -d -m 0755 -o root -g root /etc/initramfs-tools/scripts/init-top
  cat > /etc/initramfs-tools/scripts/init-top/dadooh-force-overlay <<'EOF'
#!/bin/sh
PREREQ=""
prereqs() { echo "$PREREQ"; }
case "$1" in
  prereqs) prereqs; exit 0 ;;
esac

OUT="/run/initramfs/dadooh-overlay-load.status"
mkdir -p /run/initramfs

contains_overlay() {
  [ -r /proc/filesystems ] && grep -qw overlay /proc/filesystems 2>/dev/null
}

find_overlay_module() {
  KERNEL="$(uname -r 2>/dev/null || echo unknown)"
  OVERLAY_MODULE_PATH=""
  OVERLAY_MODULE_PATH_SOURCE="unknown"

  for module in \
    "/lib/modules/$KERNEL/kernel/fs/overlayfs/overlay.ko" \
    "/lib/modules/$KERNEL/kernel/fs/overlayfs/overlay.ko."* \
    "/usr/lib/modules/$KERNEL/kernel/fs/overlayfs/overlay.ko" \
    "/usr/lib/modules/$KERNEL/kernel/fs/overlayfs/overlay.ko."*; do
    [ -f "$module" ] || continue
    OVERLAY_MODULE_PATH="$module"
    OVERLAY_MODULE_PATH_SOURCE="static_fallback"
    return 0
  done

  for depfile in "/lib/modules/$KERNEL/modules.dep" "/usr/lib/modules/$KERNEL/modules.dep"; do
    [ -r "$depfile" ] || continue
    rel="$(grep -E '(^|/)overlay\.ko(\..*)?:' "$depfile" 2>/dev/null | head -n 1 | cut -d: -f1)"
    [ -n "$rel" ] || continue
    base="${depfile%/modules.dep}"
    for module in "$base/$rel" "/lib/modules/$KERNEL/$rel" "/usr/lib/modules/$KERNEL/$rel"; do
      [ -f "$module" ] || continue
      OVERLAY_MODULE_PATH="$module"
      OVERLAY_MODULE_PATH_SOURCE="modules_dep"
      return 0
    done
  done

  for root in "/usr/lib/modules/$KERNEL" "/lib/modules/$KERNEL"; do
    [ -d "$root" ] || continue
    module="$(find "$root" -type f \( -name 'overlay.ko' -o -name 'overlay.ko.*' \) 2>/dev/null | head -n 1)"
    [ -n "$module" ] || continue
    OVERLAY_MODULE_PATH="$module"
    OVERLAY_MODULE_PATH_SOURCE="find"
    return 0
  done

  return 1
}

status="not_attempted"
modprobe_rc="missing"
insmod_rc="missing"
overlay_path_found=false
overlay_path_source="unknown"

if command -v modprobe >/dev/null 2>&1; then
  modprobe overlay >/dev/null 2>&1
  modprobe_rc="$?"
fi

if contains_overlay; then
  status="loaded_by_modprobe"
else
  if find_overlay_module; then
    overlay_path_found=true
    overlay_path_source="$OVERLAY_MODULE_PATH_SOURCE"
    if command -v insmod >/dev/null 2>&1; then
      insmod "$OVERLAY_MODULE_PATH" >/dev/null 2>&1
      insmod_rc="$?"
    fi
    if contains_overlay; then
      status="loaded_by_insmod"
    fi
  fi
fi

if [ "$status" = "not_attempted" ]; then
  if contains_overlay; then
    status="already_available"
  elif [ "$overlay_path_found" = false ]; then
    status="overlay_path_missing"
  else
    status="load_failed"
  fi
fi

cat > "$OUT" <<STATUS
overlay_load_status=$status
modprobe_rc=$modprobe_rc
insmod_rc=$insmod_rc
overlay_module_path_found=$overlay_path_found
overlay_module_path_source=$overlay_path_source
overlay_in_proc=$(contains_overlay && echo true || echo false)
raw_logs_published=false
STATUS
exit 0
EOF
  chmod 0755 /etc/initramfs-tools/scripts/init-top/dadooh-force-overlay

  log "recording lab firstboot bootstrap state"
  install -d -m 0755 -o root -g root /etc/dadooh
  rm -f "$lab_firstboot_marker"
  if test -s /root/.not_logged_in_yet &&
    grep -q 'PRESET_ROOT_PASSWORD=' /root/.not_logged_in_yet &&
    ! grep -q 'REPLACE_WITH_PRIVATE_LAB_' /root/.not_logged_in_yet; then
    cat > "$lab_firstboot_marker" <<'EOF'
lab_firstboot_autoconfig_present=true
secrets_embedded=false
secret_values_published=false
EOF
    chmod 0644 "$lab_firstboot_marker"
  fi

  log "writing image-lab state"
  install -d -m 0700 -o root -g root "$image_lab_state"
  cat > "$image_lab_state/integration.json" <<EOF
{
  "schema_version": 1,
  "image_lab": "c12-readonly",
  "board": "$BOARD",
  "release": "$RELEASE",
  "linuxfamily": "$LINUXFAMILY",
  "arch": "$ARCH",
  "overlayroot_configured_in_image": true,
  "final_armbian_initramfs_expected_after_customize": true,
  "armbian_firstboot_gate_installed": true,
  "armbian_firstboot_autoconfig_present": $(test -f "$lab_firstboot_marker" && echo true || echo false),
  "lab_firstboot_bootstrap_service_present": true,
  "lab_firstboot_bootstrap_service_enabled": true,
  "image_lab_boot_validatable_with_private_firstboot": $(test -f "$lab_firstboot_marker" && echo true || echo false),
  "secrets_embedded": false,
  "config_real_embedded": false,
  "card_written_by_build": false
}
EOF
  chmod 0600 "$image_lab_state/integration.json"

  log "sanity checks"
  command -v overlayroot-chroot >/dev/null
  test -f /usr/share/initramfs-tools/scripts/init-bottom/overlayroot
  test -d /data/config
  test -d /data/state
  test -d /data/media
  test -d /data/logs

  log "completed"
}

main "$@"
