# C12.3.11 - Initramfs Insmod Error Classification

Data: 2026-05-08

## Scope

- board: `lab_board`
- dev_board_touched=false
- old_test_board_touched=false
- writer_called=false
- real_config_written=false
- wifi_changed=false
- packages_installed=false
- poweroff_executed=false
- raw_logs_published=false

## Diagnostic

- hook_installed=true
- diagnostic_hook_in_initrd=true
- update_initramfs_ok=true
- uinitrd_regenerated=true
- reboot_executed=true
- ssh_returned=true
- diagnostic_collected=true
- rollback_executed=true
- diagnostic_hook_present_after=false

## Findings

- overlay_ko_exists_post_boot=true
- overlay_ko_file_type_post_boot=plain_ko
- overlay_ko_size_bucket_post_boot=small
- vermagic_match_post_boot=true
- dependencies_detected=[]
- dependencies_present=not_applicable
- modules_dep_references_overlay_post_boot=true
- modprobe_overlay_post_boot_works=true

## Initramfs Runtime Result

- overlay_ko_exists=false
- overlay_ko_file_type=missing
- vermagic_match=unknown
- dependencies_present=unknown
- modules_dep_references_overlay=false
- modprobe_overlay_result=zero
- proc_filesystems_has_overlay_after_modprobe=false
- insmod_overlay_attempted=false
- insmod_overlay_result=missing
- insmod_stderr_category=missing
- dmesg_category=no_message
- read_only_enabled=false
- overlay_active=false
- root_write_blocked=false
- data_writable=true
- tmp_writable=true
- run_writable=true
- systemctl_failed_count=1

## Classification

- cause_category=OVERLAY_MODULE_PATH_MISMATCH
- next_step=C12_1_10_REBUILD_WITH_EFFECTIVE_MODULE_PATH
- ready_for_c12_4=false

## Notes

No raw stderr/dmesg was published. The expected insmod error could not be
classified directly because the diagnostic proved `overlay.ko` was not
resolvable in the initramfs runtime path, so `insmod` was not attempted in this
cycle.
