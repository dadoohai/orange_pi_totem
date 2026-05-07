# C12.1.4 - Rebuild Image-Lab Firstboot Autoconfig

Data: 2026-05-07

## Resultado

- build_success: `true`
- image_path:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-4_minimal.img`
- sha256:
  `405d4891e62d018862008f3bfdf00e02123b551351655147ec7448b803ccca14`
- firstboot_autoconfig_included: `true`
- firstboot_conf_private_validated: `true`
- overlayroot_included: `true`
- initramfs_generated_after_overlayroot: `true`
- initramfs_source: `cache_hit_with_overlayroot_hooks`
- secret_scan_result: `pass`
- ready_for_card_write: `true`

## Firstboot Conf Privado

Validado sem imprimir valores:

- file_exists: `true`
- file_secure: `true`
- parent_secure: `true`
- owner_current_user: `true`
- is_symlink: `false`
- outside_repo: `true`
- placeholders_present: `false`
- required_fields_present: `true`
- network_path_present: `true`
- can_build_with_lab_firstboot: `true`

## Artefatos

- build_log_exists: `true`
- package_manifest_created: `true`
- integration_manifest_created: `true`
- firstboot_gate_included: `true`
- open_settings_cleanup_included: `true`
- read_only_assertion_included: `true`
- lab_firstboot_boot_validatable: `true`

## Guardrails

- boards_touched: `false`
- card_written: `false`
- writer_called: `false`
- config_real_included: `false`
- wifi_changed: `false`
- secrets_published: `false`
