# C12.3.14 - Overlay Module Packaging Lab

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

## Initial Inspect

- read_only_enabled: `false`
- overlay_active: `false`
- root_fstype: `ext4`
- overlayroot_conf_category: `tmpfs`
- cmdline_overlayroot_tmpfs_present: `true`
- runtime_proc_filesystems_contains_overlay: `true`
- current_overlay_load_status: `load_failed`
- current_modprobe_rc: `0`
- current_insmod_rc: `1`
- current_overlay_module_path_found: `true`

## H1 - manual_add_modules

- h1_result: `runtime_failed`
- hypothesis: `manual_add_modules`
- overlay_module_nonempty_in_initramfs: `true`
- modules_dep_references_overlay: `true`
- uinitrd_regenerated: `true`
- update_initramfs_exit_code_bucket: `zero`
- preboot_validation_passed: `true`
- reboot_executed: `true`
- ssh_returned: `true`
- read_only_enabled: `false`
- overlay_active: `false`
- root_write_blocked: `false`
- root_fstype: `ext4`
- data_writable: `true`
- tmp_writable: `true`
- run_writable: `true`
- public_state: `config_missing`
- systemctl_failed_count: `0`
- rollback_executed: `true`

## H2 - explicit_copy

- h2_result: `runtime_failed`
- hypothesis: `explicit_copy`
- overlay_module_nonempty_in_initramfs: `true`
- modules_dep_references_overlay: `true`
- uinitrd_regenerated: `true`
- update_initramfs_exit_code_bucket: `zero`
- preboot_validation_passed: `true`
- reboot_executed: `true`
- ssh_returned: `true`
- read_only_enabled: `false`
- overlay_active: `false`
- root_write_blocked: `false`
- root_fstype: `ext4`
- data_writable: `true`
- tmp_writable: `true`
- run_writable: `true`
- public_state: `config_missing`
- systemctl_failed_count: `0`
- rollback_executed: `true`

## Classification

C12.3.14 disproves the immediate packaging-only hypothesis. Both H1 and H2
produced a nonempty `overlay.ko` in initramfs and coherent `modules.dep`, but
the boot still reported:

- overlay_load_status: `load_failed`
- modprobe_rc: `0`
- insmod_rc: `1`
- overlay_in_proc: `false`

Current classification:

```text
OVERLAY_MODULE_PACKAGING_FIXED_BUT_LOAD_STILL_FAILS
```

The previous C12.3.13 classification
`OVERLAY_MODULE_EMPTY_OR_STUB_IN_INITRAMFS` is superseded for the current lab
state. The remaining blocker is not proven to be simple module packaging.

## Next Step

Recommended next step:

```text
C12.3.15_INITRAMFS_LOAD_FAILURE_WITH_NONEMPTY_MODULE
```

C12.4 remains blocked until the real boot validates:

- read_only_enabled: `true`;
- overlay_active: `true`;
- root_write_blocked: `true`;
- `/data`, `/tmp` and `/run` writable.

