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
  local image_lab_state="/data/state/totem-read-only-image-lab"

  require_file "$repo_root/scripts/board/install_totem_appliance.sh"
  require_file "$repo_root/scripts/board/totem_appliance_manifest.json"
  require_file "$app_root/kiosk.py"

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
  "armbian_firstboot_autoconfig_present": $(test -s /root/.not_logged_in_yet && grep -q 'PRESET_ROOT_PASSWORD=' /root/.not_logged_in_yet && echo true || echo false),
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
