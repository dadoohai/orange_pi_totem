# C12.2 Card Write Image-Lab

Data: 2026-05-07

## Resultado Atual

- image_exists: true
- sha256_expected:
  `1b6f5573262d501ae2df6bc3338b56432c8994d4444308caf00347829df08fe2`
- sha256_verified_before_flash: true
- build_log_exists: true
- package_manifest_exists: true
- image_lab_manifest_exists: true
- overlayroot_included: true
- initramfs_generated_after_overlayroot: true
- imager_tool: Armbian Imager Windows
- flash_completed: true
- imager_verification_completed: false
- card_written: true
- board_booted: true
- secrets_included: false
- config_real_included: false

## Artefato

- image_path:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab_minimal.img`
- build_log_exists: true
- package_manifest: `releases/image-lab-readonly/package-manifest-c12-1.txt`
- integration_manifest:
  `releases/image-lab-readonly/read-only-integration-manifest-c12-1.txt`

## Flash Manual

C12.2 padroniza Armbian Imager no Windows. O cartao foi gravado e a image-lab
foi bootada em C12.3. A verificacao visual do imager nao ficou registrada nesta
evidencia, portanto permanece `imager_verification_completed=false`.

Depois do flash, registrar:

- flash_completed: true/false
- imager_verification_completed: true/false
- target_card_label_or_note: sanitized

## Guardrails

- dev_board_used: false
- test_board_used: true
- boards_touched: true
- card_written: true
- image_rebuilt: false
- config_real_included: false
- secrets_included: false
- wifi_changed: false
