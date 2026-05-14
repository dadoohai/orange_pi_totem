# C17.4 First Boot Visual/F10 Runtime Continuation

c17_4_status=blocked
image_under_test=c17.4
image_sha256=9e9092fb7dcb04a06e1617ad048042305a285373c19261b0dd10bc96c0975058

card_written=true
single_board_validated=false

previous_c17_3_blocker=true
first_boot_black_screen_fixed=true
startup_feedback_before_config_visible=true
f10_ready_on_first_boot=true
first_f10_opens_wizard=true
misformatted_splash_fixed=true
config_missing_text_overlap=false
old_orange_config_missing_style_seen=true
old_orange_config_missing_style_severity=P2

wizard_surface_exclusive=true
status_renderer_respects_session_lock=true
kiosky_player_not_drawing_during_settings=true

full_setup_flow_passed=false
writer_passed=true
real_config_written=true
session_lock_cleanup_ok=true
session_lock_cleanup_latency_ok=false
player_restore_ok=true
player_restore_latency_ok=false
ssh_active_after_writer=true
network_connected_after_writer=true
loading_content_feedback_visible=true
playback_state_after_restore=playing
post_wizard_black_screen_observed=false
black_screen_without_feedback_observed=false

late_player_restore_observed=true
restore_recovered_without_operator_action=true
post_writer_restore_latency_seconds_observed_min=508
open_settings_elapsed_seconds_observed=1520
failure_category=POST_WRITER_RESTORE_LATENCY_LOCK_ORDER
failure_area=post_writer_settings_cleanup_and_player_restore_latency
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c18_player_audit=false

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

## Runtime Summary

The clean C17.4 card improved the C17.3 first-boot blocker:

- first boot showed visible pre-config feedback instead of black HDMI;
- the first visible splash no longer had overlapped text;
- F10 responded on first boot;
- the wizard opened;
- the wizard kept visual ownership while the settings session was active;
- public status renderer and MPV were not drawing over the wizard.

The remaining visible gap is the older orange `config_missing` style after the
initial splash. It did not block the flow and is classified as P2 visual
backlog: `CONFIG_MISSING_STYLE_CONSISTENCY`.

## Late Restore Observation

After the operator completed the wizard, the writer passed and a real config was
created. The first post-writer snapshot showed the settings-session lock still
present and the player service inactive. The operator then reported that
`Carregando conteudo` appeared without any additional action.

Sanitized systemd evidence showed:

- early post-writer snapshot:
  - `totem-open-settings.service=activating`;
  - `kiosky-player.service=inactive`;
  - `session_lock_present=true`;
  - `config_real_present=true`;
  - `wizard=0`;
  - `status_renderer=0`;
  - `mpv=0`;
- late snapshot:
  - `totem-open-settings.service=inactive`;
  - `kiosky-player.service=active`;
  - `session_lock_present=false`;
  - `public_state=player_running`;
  - `playback_state=playing`;
  - `mpv=1`;
- NetworkManager and SSH stayed active.

The decisive evidence is that `kiosky-player.service` was skipped twice by its
own condition because the settings-session lock still existed. The service only
started after the open-settings session finally exited and the lock was gone.

This refines the failure from a permanent restore block to a severe post-writer
restore latency/order bug. The functional state eventually reached
`playback_state=playing`, but the user-visible delay was long enough to remain a
C17.4 blocker.

## Decision

C17.4 remains blocked. Batch flash, dispatch and C18 player audit stay closed.
The next step should fix post-writer cleanup/restore ordering so the lock is
released before player restoration is requested, and remove the long waits that
currently delay the actual player start.
