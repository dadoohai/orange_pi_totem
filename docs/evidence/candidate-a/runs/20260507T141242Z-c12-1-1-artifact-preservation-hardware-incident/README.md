# C12.1.1 Artifact Preservation + Hardware Incident

Data: 2026-05-07

## Resultado

- image_exists: true
- checksum_ok: true
- build_log_exists: true
- package_manifest_exists: true
- image_lab_manifest_exists: true
- overlayroot_included: true
- initramfs_generated_after_overlayroot: true
- secret_scan_textual_artifacts: pass
- card_written: false
- boards_touched: false
- dev_card_incident_recorded: true
- ready_for_c12_2: true

## Artefato

- image_path:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab_minimal.img`
- sha256:
  `1b6f5573262d501ae2df6bc3338b56432c8994d4444308caf00347829df08fe2`
- build_log_exists: true
- package_manifest: `releases/image-lab-readonly/package-manifest-c12-1.txt`
- integration_manifest:
  `releases/image-lab-readonly/read-only-integration-manifest-c12-1.txt`

## Incidente Fisico

- dev_card_smoke_or_heat_reported: true
- dev_card_status: lost_or_untrusted
- dev_board_status: hardware_incident_pending_retest
- software_fault_assumed: false

## Guardrails

- dev_board_used: false
- test_board_used: false
- card_written: false
- image_rebuilt: false
- config_real_read: false
- writer_called: false
- wifi_changed: false
- packages_installed: false
