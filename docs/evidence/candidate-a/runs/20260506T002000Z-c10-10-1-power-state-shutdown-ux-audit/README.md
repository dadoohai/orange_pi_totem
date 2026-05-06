# C10.10.1 Power State / Shutdown UX Audit

Timestamp UTC: 2026-05-06T00:20:00Z

## Scope

Read-only audit of the incident where the second board showed black HDMI and no
SSH after a normal shutdown, then recovered after physical power cycle.

## Repository

- branch: `foundation-v0.1`
- head_at_start: `72bdebac203de1596f7fbafb9213a6a55eb233d3`
- head_title: `Add C10.10 installable bench RC package`

## Commands

- `git status --short`
- `git log --oneline -25`
- `git diff --check`
- `bash -n scripts/remote/run_c10_10_1_power_state_audit.sh`
- `scripts/remote/run_c10_10_1_power_state_audit.sh <second-board-host> --summary --local-out-dir /tmp/dadooh-c10-10-1-power-state-audit/...`

No reboot or poweroff command was executed by this audit.

## Incident

- incident_observed: `true`
- ssh_unavailable_before_power_cycle: `true`
- hdmi_black_before_power_cycle: `true`
- power_cycle_restored: `true`

## Current State After Power Cycle

- public_state: `player_running`
- playback: `playing`
- human_observed_media_after_power_cycle: `true`
- kiosky_player_service: `active/enabled`
- totem_settings_trigger_service: `active/enabled`
- totem_open_settings_service: `inactive/static`
- dadooh_visual_splash_service: `active/enabled`
- service_nrestarts: `0`
- systemctl_failed_count: `0`
- kernel_critical_filter_count: `0`
- player_process_count: `1`
- mpv_process_count: `1`
- renderer_process_count: `0`
- setup_process_count: `0`
- session_lock_present: `false`
- request_present: `false`
- config_real_present: `true`
- config_permissions_ok: `true`
- dedicated_wifi_present: `true`
- orientation_json_present: `true`

## Previous Boot Postmortem

- journal_previous_boot_available: `true`
- previous_boot_shutdown_markers_present: `true`
- previous_boot_clean_shutdown_without_reboot: `true`
- previous_boot_had_clean_poweroff: `true`
- previous_boot_reached_poweroff_target: `false`
- previous_boot_had_reboot_marker: `false`
- previous_boot_had_kernel_panic: `false`
- previous_boot_had_ext4_error: `false`
- previous_boot_had_mmc_error: `false`
- previous_boot_end_category: `clean_poweroff`
- clean_poweroff_detected: `true`
- ext4_error_detected: `false`
- mmc_error_detected: `false`
- kernel_critical_filter_count_previous: `0`

## Classification

- incident_classification: `POWER_STATE_EXPECTED_BUT_UX_UNCLEAR`
- installable_bench_rc_status: `valid_with_shutdown_ux_followup`
- blocked_reason: `none`
- recommendation: `C10.10.2 Shutdown UX`

## Sanitization

- raw_logs_published: `false`
- config_content_published: `false`
- secrets_published: `false`
- private_values_published: `false`
- network_identifiers_published: `false`
- payloads_published: `false`
- reboot_called: `false`
- poweroff_called: `false`
- writer_called: `false`
- wifi_changed: `false`
- packages_installed: `false`

## Conclusion

The observed black screen/no SSH state is consistent with a clean shutdown or
halted board that requires physical power cycle to boot again. It is not
classified as a boot failure in this evidence. The installable bench RC remains
valid, but C11.0 read-only readiness should wait for C10.10.2 Shutdown UX.
