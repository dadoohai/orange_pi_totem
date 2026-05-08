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
  local lab_firstboot_mode_file="$lab_root/etc/dadooh/c12-lab-firstboot-mode"
  local homologation_seed_src="$lab_root/data/state/totem-settings/private-values.seed.json"
  local homologation_seed_marker_src="$lab_root/data/state/totem-settings/homologation-seed.enabled"
  local homologation_seed_policy_src="$lab_root/etc/dadooh/c13-homologation-private-seed"

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
  install -d -m 0755 -o root -g root /etc/dadooh
  if [ -f "$lab_firstboot_mode_file" ]; then
    install -m 0644 -o root -g root "$lab_firstboot_mode_file" /etc/dadooh/c12-lab-firstboot-mode
  else
    cat > /etc/dadooh/c12-lab-firstboot-mode <<'EOF'
lab_firstboot_mode=unknown
artifact_private=false
final_image=false
firstboot_conf_committed=false
firstboot_conf_contents_published=false
ready_for_c12_2_7_card_write=false
ready_for_c12_3_boot_ssh_validation=false
require_manual_firstboot=true
EOF
    chmod 0644 /etc/dadooh/c12-lab-firstboot-mode
  fi
  install -m 0755 -o root -g root \
    "$lab_root/opt/totem/bin/totem_lab_firstboot_autoconfig.sh" \
    /opt/totem/bin/totem_lab_firstboot_autoconfig.sh
  install -m 0644 -o root -g root \
    "$lab_root/etc/systemd/system/totem-lab-firstboot-autoconfig.service" \
    /etc/systemd/system/totem-lab-firstboot-autoconfig.service
  systemctl --no-reload enable totem-lab-firstboot-autoconfig.service

  if [ -f "$homologation_seed_src" ]; then
    log "installing private homologation seed marker and seed"
    install -d -m 0700 -o root -g root /data/state/totem-settings
    install -m 0600 -o root -g root \
      "$homologation_seed_src" \
      /data/state/totem-settings/private-values.seed.json
    if [ -f "$homologation_seed_marker_src" ]; then
      install -m 0644 -o root -g root \
        "$homologation_seed_marker_src" \
        /data/state/totem-settings/homologation-seed.enabled
    else
      cat > /data/state/totem-settings/homologation-seed.enabled <<'EOF'
homologation_private_seed_enabled=true
final_image=false
artifact_private=true
not_for_production=true
not_for_distribution=true
seed_content_published=false
EOF
      chmod 0644 /data/state/totem-settings/homologation-seed.enabled
    fi
    if [ -f "$homologation_seed_policy_src" ]; then
      install -m 0644 -o root -g root \
        "$homologation_seed_policy_src" \
        /etc/dadooh/c13-homologation-private-seed
    fi
  fi

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

  log "recording overlayfs built-in kernel expectation"
  cat > /etc/dadooh/c12-overlayfs-kernel-policy <<'EOF'
kernel_overlayfs_builtin_required=true
required_kernel_config=CONFIG_OVERLAY_FS=y
overlayroot_module_initramfs_path_status=blocked
module_loading_hooks_used=false
modular_overlay_fallback_hooks_present=false
diagnostic_initramfs_hooks_present=false
EOF
  chmod 0644 /etc/dadooh/c12-overlayfs-kernel-policy

  log "disabling Debian backports apt suite for image-lab build stability"
  if [ -f /etc/apt/sources.list.d/debian.sources ]; then
    python3 - <<'PY'
from pathlib import Path

path = Path("/etc/apt/sources.list.d/debian.sources")
lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
out = []
changed = False
for line in lines:
    if line.startswith("Suites:"):
        head, values = line.split(":", 1)
        suites = [suite for suite in values.split() if suite != "bookworm-backports"]
        new_line = f"{head}: {' '.join(suites)}"
        changed = changed or new_line != line
        out.append(new_line)
    else:
        out.append(line)
path.write_text("\n".join(out) + "\n", encoding="utf-8")
marker = Path("/etc/dadooh/c13-homologation-build-apt-policy")
marker.write_text(
    "debian_backports_disabled_for_image_lab_build=true\n"
    "reason=avoid_qemu_chroot_apt_memory_error\n"
    "final_image=false\n",
    encoding="utf-8",
)
marker.chmod(0o644)
if not changed:
    raise SystemExit("debian_backports_suite_not_found")
PY
  fi

  log "recording lab firstboot bootstrap state"
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
  local lab_firstboot_mode artifact_private ready_for_ssh require_manual_firstboot ready_for_card_write
  local homologation_private_values_embedded seed_content_published not_for_production not_for_distribution
  lab_firstboot_mode="$(awk -F= '$1=="lab_firstboot_mode" {print $2}' /etc/dadooh/c12-lab-firstboot-mode 2>/dev/null | tail -n1)"
  artifact_private="$(awk -F= '$1=="artifact_private" {print $2}' /etc/dadooh/c12-lab-firstboot-mode 2>/dev/null | tail -n1)"
  ready_for_ssh="$(awk -F= '$1=="ready_for_c12_3_boot_ssh_validation" {print $2}' /etc/dadooh/c12-lab-firstboot-mode 2>/dev/null | tail -n1)"
  require_manual_firstboot="$(awk -F= '$1=="require_manual_firstboot" {print $2}' /etc/dadooh/c12-lab-firstboot-mode 2>/dev/null | tail -n1)"
  ready_for_card_write="$(awk -F= '$1=="ready_for_c12_2_7_card_write" {print $2}' /etc/dadooh/c12-lab-firstboot-mode 2>/dev/null | tail -n1)"
  case "$lab_firstboot_mode" in synthetic_no_secret|private_disposable_lab) ;; *) lab_firstboot_mode="unknown" ;; esac
  case "$artifact_private" in true|false) ;; *) artifact_private=false ;; esac
  homologation_private_values_embedded="$(test -f /data/state/totem-settings/private-values.seed.json && echo true || echo false)"
  if [ "$homologation_private_values_embedded" = "true" ]; then
    artifact_private=true
  fi
  seed_content_published=false
  not_for_production=true
  not_for_distribution=true
  case "$ready_for_ssh" in true|false) ;; *) ready_for_ssh=false ;; esac
  case "$require_manual_firstboot" in true|false) ;; *) require_manual_firstboot=true ;; esac
  case "$ready_for_card_write" in true|false) ;; *) ready_for_card_write=false ;; esac
  cat > "$image_lab_state/integration.json" <<EOF
{
  "schema_version": 1,
  "image_lab": "c12-readonly",
  "board": "$BOARD",
  "release": "$RELEASE",
  "linuxfamily": "$LINUXFAMILY",
  "arch": "$ARCH",
  "overlayroot_configured_in_image": true,
  "kernel_overlayfs_builtin_required": true,
  "overlayroot_module_initramfs_path_status": "blocked",
  "module_loading_hooks_used": false,
  "modular_overlay_fallback_hooks_present": false,
  "diagnostic_initramfs_hooks_present": false,
  "final_armbian_initramfs_expected_after_customize": true,
  "armbian_firstboot_gate_installed": true,
  "armbian_firstboot_autoconfig_present": $(test -f "$lab_firstboot_marker" && echo true || echo false),
  "lab_firstboot_mode": "$lab_firstboot_mode",
  "artifact_private": $artifact_private,
  "final_image": false,
  "not_for_production": $not_for_production,
  "not_for_distribution": $not_for_distribution,
  "homologation_private_values_embedded": $homologation_private_values_embedded,
  "homologation_seed_path": "/data/state/totem-settings/private-values.seed.json",
  "homologation_seed_content_published": $seed_content_published,
  "firstboot_conf_committed": false,
  "firstboot_conf_contents_published": false,
  "ready_for_c12_3_boot_ssh_validation": $ready_for_ssh,
  "require_manual_firstboot": $require_manual_firstboot,
  "ready_for_c12_2_7_card_write": $ready_for_card_write,
  "lab_firstboot_bootstrap_service_present": true,
  "lab_firstboot_bootstrap_service_enabled": true,
  "image_lab_boot_validatable_with_private_firstboot": $ready_for_ssh,
  "secrets_embedded": $homologation_private_values_embedded,
  "secrets_published": false,
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
