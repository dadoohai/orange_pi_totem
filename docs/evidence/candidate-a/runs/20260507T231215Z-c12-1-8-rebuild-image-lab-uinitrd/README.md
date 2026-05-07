# C12.1.8 Rebuild Image-Lab uInitrd

Data: 2026-05-07

## Resultado

- cause_from_c12_1_7: `UINITRD_NOT_UPDATED`
- fix_applied: `initramfs_marker_plus_effective_uinitrd_validation`
- build_success: `true`
- image_version: `c12.1.8`
- image_path:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-8_minimal.img`
- sha256:
  `7fbc9a0abc39d39b5fc0803d5f935baaf1795bddc6707e18dbf1d7c804ad830d`
- build_log:
  `/home/builder/totem-os/armbian-build-v25.11/output/logs/log-build-2a197de8-ef86-4e09-8ec0-61bc0fa180b0.log`
- package_manifest:
  `releases/image-lab-readonly/package-manifest-c12-1-8.txt`
- integration_manifest:
  `releases/image-lab-readonly/read-only-integration-manifest-c12-1-8.txt`

## Validacao Offline

- overlayroot_included: `true`
- initrd_img_exists: `true`
- initrd_contains_overlayroot_hook: `true`
- initrd_contains_overlay_module: `true`
- initrd_contains_c12_overlayroot_marker: `true`
- uinitrd_exists: `true`
- uinitrd_nonempty: `true`
- uinitrd_payload_extracted: `true`
- uinitrd_payload_matches_initrd_img: `true`
- uinitrd_contains_overlayroot_hook: `true`
- uinitrd_contains_overlay_module: `true`
- uinitrd_contains_c12_overlayroot_marker: `true`
- uinitrd_generated_after_overlayroot: `true`
- uinitrd_generated_after_initrd_img: `true`
- boot_script_uses_uinitrd: `true`
- effective_boot_initramfs_valid: `true`
- firstboot_autoconfig_valid: `true`
- secret_scan_result: `passed`
- card_written: `false`
- boards_touched: `false`
- ready_for_card_write: `true`

## Guardrails

- placas_tocadas: `false`
- cartao_gravado: `false`
- writer_called: `false`
- config_real_embedded: `false`
- wifi_networkmanager_changed: `false`
- final_image: `false`
- secrets_published: `false`

## Proximo Passo

`C12.2.4` deve gravar a imagem C12.1.8 em cartao de teste. `C12.4` continua
bloqueado ate a validacao em placa provar read-only ativo.
