# C12.1 Build Image-Lab Read-only

Data: 2026-05-06

## Resultado

- build_env_ok: true
- armbian_build_ref: `e172058`
- armbian_build_version: `v25.11`
- build_started: true
- build_success: true
- image_path: `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab_minimal.img`
- checksum_sha256: `1b6f5573262d501ae2df6bc3338b56432c8994d4444308caf00347829df08fe2`
- checksum_file: `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab_minimal.img.sha256`
- build_log_file: `/home/builder/totem-os/armbian-build-v25.11/output/logs/log-build-29bced66-eed1-4f2c-8d0e-d2ad34f794b5.log`
- package_manifest_created: true
- overlayroot_included: true
- initramfs_generated_after_overlayroot: true
- secret_scan_result: pass_textual_artifacts
- ready_for_card_write: true

## Guardrails

- boards_touched: false
- card_written: false
- final_image: false
- config_real_embedded: false
- secrets_embedded: false
- wifi_credentials_embedded: false
- media_cache_embedded: false
- writer_called: false
- read_only_enabled_on_installed_board: false

## Observacoes

O primeiro build abortou por pressao de memoria ao usar rootfs em tmpfs. O
runner foi ajustado para `FORCE_USE_RAMDISK=no`, e a repeticao gerou a imagem
com sucesso. O log de build confirmou instalacao de `overlayroot` e
`update-initramfs` apos a presenca do pacote na imagem.
