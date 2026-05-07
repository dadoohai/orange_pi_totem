# C12.1.7 - Overlayroot Activation Diagnose

Data: 2026-05-07

## Escopo

- image_version: `c12.1.6`
- running_board_inspected: `true`
- image_artifact_inspected: `true`
- host: `lab_board_redacted`
- secrets_published: `false`
- raw_logs_published: `false`
- writer_called: `false`
- real_config_written: `false`
- wifi_changed: `false`
- reboot_executed: `false`
- poweroff_executed: `false`

## Sistema Bootado

- overlayroot_config_present_running: `true`
- overlayroot_config_category_running: `tmpfs`
- read_only_enabled: `false`
- overlay_active: `false`
- root_write_blocked: `false`
- root_fstype: `ext4`
- uinitrd_size_category_running: `nonempty`
- boot_args_overlay_present: `false`
- systemctl_failed_count: `1`
- console_setup_failed: `true`
- public_state: `config_missing`

## Artefato da Imagem

- overlayroot_config_present_image: `true`
- overlayroot_config_category_image: `tmpfs`
- initrd_img_contains_overlayroot: `true`
- initrd_img_contains_overlay_module: `true`
- boot_uses_uinitrd: `true`
- boot_uses_initrd_img: `false`
- uinitrd_size_category_image: `empty`
- uinitrd_contains_overlayroot: `false`
- build_log_initrd_cache_hit: `true`
- build_log_updated_initramfs: `false`

## Comparacao

- initramfs_contains_overlayroot: `true`
- uinitrd_updated: `false`
- overlay_active: `false`
- read_only_enabled: `false`
- root_write_blocked: `false`
- initramfs_log_driver_lookup_failed: `false`
- cause_category: `UINITRD_NOT_UPDATED`
- recommended_fix:
  `rebuild_c12_1_8_with_nonempty_uInitrd_generated_from_overlayroot_initrd_or_fix_boot_script`
- next_step: `C12.1.8 rebuild image-lab overlayroot boot initrd fix`

## Decisao

C12.4 continua bloqueado. C12.1.8 deve corrigir a geracao/validacao do
`uInitrd` da imagem-lab antes de nova gravacao/boot validation.
