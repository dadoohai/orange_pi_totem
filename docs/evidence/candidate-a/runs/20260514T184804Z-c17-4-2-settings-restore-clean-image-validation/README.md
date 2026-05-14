# C17.4.2 Settings Restore Clean Image Validation

c17_4_2_status=passed
blocker=none
image_built=true
image_file=/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c17-4-2-settings-restore-clean_minimal.img
image_sha256=184ecdff1da3fc5f2f819b9be1a67da9e3cfaa87b8bdede7badddf2c1a22c5af
kernel_reused=true
kernel_rebuild_executed=false

artifact_private=true
final_image=false
homologation_shipping_image=true

previous_c17_4_1_passed=true
c17_4_1_fix_embedded=true
restore_order_static_check_passed=true

card_written=true
single_board_validated=true
full_setup_flow_passed=true

first_boot_black_screen_fixed=true
startup_feedback_before_config_visible=true
f10_ready_on_first_boot=true
first_f10_opens_wizard=true
misformatted_splash_fixed=true
config_missing_text_overlap=false
wizard_surface_exclusive=true
status_renderer_respects_session_lock=true
kiosky_player_not_drawing_during_settings=true

writer_passed=true
real_config_written=true
session_lock_cleanup_ok=true
lock_removed_before_restore=true
restore_service_called_after_lock_removed=true
restore_called_while_lock_exists=false
kiosky_player_condition_skipped=false
totem_open_settings_service_stuck_activating=false
session_done=true
player_restore_ok=true
ssh_active_after_writer=true
network_connected_after_writer=true
loading_content_feedback_visible=unknown
playback_state_after_restore=playing

writer_done_to_player_active_sec=2
writer_done_to_playing_sec=32
restore_latency_within_30s=true
restore_latency_within_10s=true

old_orange_config_missing_style_seen=false
old_orange_config_missing_style_severity=none
visual_backlog_next=none

gate_api_cache_content=passed
gate_wifi_negative=passed
gate_update_ux=passed
gate_wizard_visual_consistency=passed

pull_update_timer_enabled=true
totem_updatectl_status_ok=true

ready_for_batch_flash=true
ready_for_dispatch=true
ready_for_c18_player_audit=true

## Offline Result

The offline derivation passed. The rootfs validation confirmed the C17.4.1
restore-order fix is embedded: the settings lock is released before player
restore, `restore_service` refuses to start while the lock still exists, and
the final-status path does not enter a long player wait while the lock exists.

## Clean-Card Runtime Result

Clean-card validation passed after manual flashing through Armbian Imager.

Operator HDMI observation:

- first boot did not stay black;
- pre-config/config_missing feedback was visible and legible;
- F10 opened the wizard on the first boot;
- no config_missing text overlap was observed.

Sanitized SSH/runtime collection:

- wizard/settings session was active before writer;
- `session_lock_present=true` while the wizard owned the visual surface;
- `kiosky-player.service=inactive` while settings were active;
- config was absent before writer and present after writer;
- writer result was `passed`;
- settings lock was released before player restore;
- `kiosky-player.service` became active about 2 seconds after config/write;
- `totem-open-settings.service` finished instead of remaining activating;
- SSH and NetworkManager remained active;
- playback reached `playing`.

The first clean-card image with C17.4.1 embedded therefore passes the C17.4.2
settings restore gate. Batch flash, dispatch and C18 player audit are now
unblocked from the C17 first-configuration path.

Guardrails:
secrets_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
read_only_touched=false
kernel_touched=false
wifi_touched_only_by_wizard=true
networkmanager_touched_only_by_wizard=true
poweroff_executed=false
power_cut_tested=false
planned_power_cut_tested=false
c12_4_power_cut_tested=false
scheduler_changed=false
sync_changed=false
duration_changed=false
loop_changed=false
exposure_time_ms_changed=false
c12_readonly_blocked=true
c12_4_blocked=true
