# C11.3.4 read-only mechanism decision

Data: 2026-05-06

## Scope

Rodada documental e de inspecao read-only. Nenhuma placa recebeu enable,
reboot, poweroff, writer, alteracao de Wi-Fi ou alteracao de config real.

## Repository

- head: `dc5e417`
- branch: `foundation-v0.1`
- c11_3_3_present=true

## Dev Sanity

- dev_touched_operationally=false
- dev_sanity_ok=true
- dev_read_only_enabled=false
- dev_overlay_active=false
- dev_overlayroot_disabled=true
- dev_public_state=player_running
- dev_playback=running
- dev_services_active_enabled=true
- dev_systemctl_failed_count=0
- dev_kernel_critical_filter_count=2

## Test Sanity

- test_inspection_only=true
- test_read_only_enabled=false
- test_overlay_active=false
- test_rollback_complete=true
- test_overlayroot_installed=true
- test_overlayroot_disabled=true
- test_public_state=display_missing
- test_display_missing_reason=hdmi_connected_to_dev
- test_services_active_enabled=true
- test_systemctl_failed_count=0
- test_kernel_critical_filter_count=2

## Mechanism Diagnosis

- mechanism_attempted=overlayroot
- result=not_activated
- package_present=true
- overlayroot_chroot_present=true
- initramfs_hook_present=true
- initramfs_overlay_module_present=true
- runtime_overlay_supported=true
- uinitrd_present=true
- initramfs_error_category=initramfs_overlay_driver_lookup_failed
- raw_logs_published=false

## Decision

- decision=c12_image_integrated_overlay_lab_required
- next_step=C12.0-prep
- c11_4_blocked=true
- read_only_enabled=false
- power_cut_tested=false

## Guardrails

- config_real_published=false
- secrets_published=false
- ssid_password_published=false
- ip_mac_dns_published=false
- logs_raw_published=false
