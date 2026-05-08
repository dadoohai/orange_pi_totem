# C12.1.11 Build Image-lab Overlayfs Built-in

Data: 2026-05-08

## Resultado

- build_success: `false`;
- image_built: `false`;
- image_path: `not_created`;
- sha256: `not_created`;
- CONFIG_OVERLAY_FS_y: `true`;
- kernel_built: `true`;
- kernel_packaged: `true`;
- overlayroot_included: `not_final_image_validated`;
- overlayroot_configured: `not_final_image_validated`;
- uInitrd_valid: `not_final_image_validated`;
- journald_volatile: `not_final_image_validated`;
- data_layout_present: `not_final_image_validated`;
- secret_scan_result: `no_secrets_published`;
- card_written: `false`;
- boards_touched: `false`;
- ssh_used: `false`;
- writer_called: `false`;
- ready_for_card_write: `false`.

## Firstboot Mode

- lab_firstboot_mode: `private_disposable_lab`;
- artifact_private: `true`;
- final_image: `false`;
- firstboot_conf_committed: `false`;
- firstboot_conf_contents_published: `false`;
- ready_for_c12_3_boot_ssh_validation: `true`;
- require_manual_firstboot: `false`.

O conteudo do arquivo privado nao foi publicado nesta evidencia.

## Build Failure

- failure_category: `BUILD_HOST_CHROOT_APT_MEMORY_ERROR`;
- apt_update_inside_image_failed: `true`;
- apt_error_category: `cannot_allocate_memory_while_reading_backports_inrelease`;
- failed_phase: `rootfs_image_apt_lists_update_after_customization`;
- armbian_build_log: `output/logs/log-build-25b85e2a-888e-4f84-9f3d-8ef835c80d4b.log`;
- wrapper_log: `/tmp/dadooh-c12-1-image-lab-readonly/20260508T155912Z-c12-1-build-image-lab-readonly/build-wrapper.log`.

## Guardrails

- dev_board_touched: `false`;
- test_board_touched: `false`;
- card_written: `false`;
- poweroff_executed: `false`;
- writer_called: `false`;
- config_real_included: `false`;
- secrets_published: `false`;
- raw_logs_published: `false`.

## Decisao

C12.1.11 ainda nao gerou imagem gravavel. C12.2.7 nao pode comecar ate uma nova
execucao produzir imagem, checksum e validacao offline.
