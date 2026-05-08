# C12.3.15 - Initramfs Overlay Load Failure

Data: 2026-05-08

## Scope

- host: `lab_board`
- dev board touched: `false`
- old test board touched: `false`
- writer_called: `false`
- real_config_written: `false`
- wifi_changed: `false`
- packages_installed: `false`
- poweroff_executed: `false`
- raw_logs_published: `false`

## Inspect

- overlay_ko_nonempty_uinitrd: `true`
- modules_dep_references_overlay_uinitrd: `true`
- modinfo_vermagic_match: `true`
- dependencies_present_in_uinitrd: `not_applicable`
- read_only_enabled: `false`
- overlay_active: `false`
- root_fstype: `ext4`

## Diagnostic Hook

- hook_installed: `true`
- diagnostic_hook_in_initrd: `true`
- rollback_available: `true`
- update_initramfs_exit_code_bucket: `zero`
- uinitrd_regenerated: `true`

## Reboot Diagnostic

- reboot_executed: `true`
- ssh_returned: `true`
- proc_mounted: `true`
- overlay_ko_exists: `true`
- overlay_ko_nonempty: `true`
- overlay_ko_file_type: `plain_ko`
- module_path_kernel_matches: `true`
- modules_dep_references_overlay: `false`
- dependencies_present: `unknown`
- vermagic_match: `unknown`
- modprobe_result: `zero`
- overlay_in_proc_after_modprobe: `false`
- insmod_result: `nonzero`
- insmod_error_category: `unknown`
- dmesg_category: `no_message`
- overlay_in_proc_after_insmod: `false`
- mount_overlay_attempted: `false`
- mount_overlay_result: `not_attempted`

## Runtime State After Diagnostic Boot

- read_only_enabled: `false`
- overlay_active: `false`
- root_write_blocked: `false`
- root_fstype: `ext4`
- data_writable: `true`
- tmp_writable: `true`
- run_writable: `true`
- public_state: `config_missing`
- systemctl_failed_count: `0`

## Rollback

- rollback_executed: `true`
- diagnostic_hook_present_after: `false`
- update_initramfs_exit_code_bucket: `zero`
- uinitrd_regenerated: `true`

## Classification

The module is no longer empty or missing in the image artifact. It is present and
nonempty, the rootfs-side module matches the booted kernel, and there are no
declared module dependencies. Inside initramfs, however:

- `modprobe overlay` returns zero;
- `overlay` does not appear in `/proc/filesystems`;
- `insmod overlay.ko` returns nonzero;
- no stderr or dmesg category is available;
- overlay mount is not attempted because the module never registers.

Cause category:

```text
INITRAMFS_MODULE_LOADING_UNSUPPORTED
```

Next step:

```text
ADR_UPDATE_READONLY_MECHANISM_DECISION
```

C12.1.11 is not ready to start as a simple rebuild. The overlayroot-via-module
path should be treated as blocked until a kernel/module compatibility or
alternative mechanism decision is made.

