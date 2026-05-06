# C11.3.1 overlayroot prerequisite

- commit_under_test: `ede002c`
- dev_board_validated: `true`
- test_board_touched: `false`
- package_name: `overlayroot`
- mechanism_detected: `armbian_config_module_overlayfs`
- package_known_to_apt_cache: `true`
- dry_run_safe: `true`
- would_install_count: `3`
- would_upgrade_count: `0`
- would_remove_count: `0`
- would_touch_kernel_packages: `false`
- kernel_packages_held: `true`
- installed: `true`
- overlayroot_available_after: `false`
- overlayroot_chroot_available_after: `true`
- overlayroot_initramfs_script_present_after: `true`
- can_enable_without_package_install: `true`
- upgrades_attempted: `false`
- read_only_enabled: `false`
- poweroff_executed: `false`
- reboot_executed: `false`
- power_cut_tested: `false`
- writer_called: `false`
- real_config_read: `false`
- real_config_written: `false`
- wifi_changed: `false`
- networkmanager_profiles_changed: `false`
- packages_installed: `true`
- public_state: `player_running`
- playback: `playing`
- systemctl_failed_count: `0`
- ready_for_c11_3_2_enablement: `true`

## Commands

```bash
scripts/remote/run_c11_3_1_overlayroot_prereq.sh --prepare-only
scripts/remote/run_c11_3_1_overlayroot_prereq.sh <dev-board> --inspect
scripts/remote/run_c11_3_1_overlayroot_prereq.sh <dev-board> --apt-policy
scripts/remote/run_c11_3_1_overlayroot_prereq.sh <dev-board> --dry-run-install
scripts/remote/run_c11_3_1_overlayroot_prereq.sh <dev-board> --install-prereq
scripts/remote/run_c11_3_1_overlayroot_prereq.sh <dev-board> --verify-prereq
```

No raw apt logs, config, secrets, SSID/password, IP/MAC/DNS, hostname or
NetworkManager profile names are included here.
