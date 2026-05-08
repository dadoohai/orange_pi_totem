# C12.3.12 - Boot Validate C12.1.10

Data: 2026-05-08

## Scope

- board=lab_board
- image_version=c12.1.10
- boot_attempted=true
- ssh_available=true
- dev_board_touched=false
- old_test_board_touched=false
- writer_called=false
- real_config_written=false
- wifi_changed=false
- packages_installed=false
- poweroff_executed=false
- raw_logs_published=false

## Read-only

- read_only_enabled=false
- overlay_active=false
- root_write_blocked=false
- root_fstype=ext4
- cmdline_overlayroot_tmpfs_present=true
- armbian_env_overlayroot_present=true
- data_writable=true
- tmp_writable=true
- run_writable=true

## Overlay Hook

- overlay_status_present=true
- overlay_module_path_found=true
- overlay_module_path_source=static_fallback
- modprobe_rc=0
- insmod_rc=1
- overlay_in_proc_in_initramfs=false
- overlay_in_proc_after_boot=true
- read_only_failure_category=DYNAMIC_PATH_FOUND_INSMOD_FAILED

## Product / Visual

- public_state=config_missing
- config_real_present=false
- status_svg_exists=true
- status_svg_has_svg_tag=true
- status_svg_has_config_missing_text_category=true
- renderer_process_count=1
- MPV_process_count=1
- setup_process_count=0
- human_observed_black_screen=true
- visual_classification=CONFIG_MISSING_VISUAL_BLACK_SCREEN_WITH_RENDERER_ACTIVE

## Result

- c12_3_12_status=blocked
- ready_for_c12_4=false
- next_step=C12.3.13_DYNAMIC_PATH_INSMOD_ERROR_DIAGNOSTICS

No secrets, config real, SSID, password, IP/MAC/DNS or raw logs were published.
