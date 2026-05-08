# C12.3.16 - Read-only Mechanism Decision Update

Data: 2026-05-08

## Scope

- boards_touched=false
- card_written=false
- image_built=false
- writer_called=false
- config_real_read=false
- config_real_written=false
- wifi_changed=false
- poweroff_executed=false
- power_cut_tested=false
- secrets_published=false

## Decision

- decision=overlayroot_with_overlayfs_builtin_next
- module_path_abandoned=true
- overlayroot_retained=true
- required_kernel_config=CONFIG_OVERLAY_FS=y
- c12_4_blocked=true

## Validation Criteria

- validation_criteria_updated=true
- root_write_blocked_no_longer_required=true
- overlay_active_required=true
- root_mount_type_overlay_required=true
- root_test_file_persisted_after_reboot=false
- data_test_file_persisted_after_reboot=true
- readonly_semantics_valid_required=true

## Build Preparation

- armbian_kernel_config_name=linux-sunxi64-current.config
- kernel_config_source=armbian_build_config_kernel
- partial_kconfig_fragment_used=false
- ready_for_c12_1_11_build=true

## Prohibitions Observed

No raw logs, real config, private credentials, network identifiers or firstboot
private content were included.
