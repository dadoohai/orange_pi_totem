# C17.4.1 Settings Lock Restore Fix

c17_4_1_status=passed
previous_c17_4_blocker=POST_WRITER_RESTORE_LATENCY_LOCK_ORDER

hotfix_applied_to_board=true
hotfix_applied_to_repo=true
restore_failure_wait_guard_static_check=true

lock_removed_before_restore=true
restore_service_called_after_lock_removed=true
restore_called_while_lock_exists=false
kiosky_player_condition_skipped=false
totem_open_settings_service_stuck_activating=false
session_done=true

writer_passed=true
session_lock_cleanup_ok=true
player_restore_ok=true
ssh_active_after_writer=true
network_connected_after_writer=true
loading_content_feedback_visible=true
playback_state_after_restore=playing

writer_done_to_player_active_sec=2
writer_done_to_playing_sec=5
restore_latency_within_30s=true
restore_latency_within_10s=true

ready_for_c17_4_2_image_rebuild=true
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c18_player_audit=false

secrets_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
read_only_touched=false
kernel_touched=false
wifi_touched_only_by_wizard=false
networkmanager_touched_only_by_wizard=false
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

## Current Restore Order

- lock_created_at=settings_session_start
- writer_done_at=writer_status_completed
- release_session_lock_at=after_wizard_writer_saving_before_restore
- restore_service_called_at=after_release_session_lock
- player_start_requested_at=after_release_session_lock
- player_condition_skipped=false

## Cause

C17.4 called `restore_service` before removing the settings-session lock. The
player unit correctly refused to start while that lock existed, then the session
waited for player state before removing the lock. That produced a long
post-writer delay until the service cleanup path finally removed the lock and
restored the player.

## Fix

C17.4.1 adds an explicit `release_session_lock_for_restore` phase in the normal
successful session path. After the wizard and writer finish, the request and
session lock are removed, the release is traced, and only then is the player
restore requested.

`restore_service` also has a guard: if the lock still exists, it records the
blocked condition and returns without trying to start the player or entering a
long wait.

## Runtime Retest

The hotfix was applied to the current board without reboot, poweroff, Wi-Fi
changes, config reads or manual writer invocation. The retest used the normal
F10/settings flow.

Observed sanitized sequence:

- F10 opened the settings service.
- Lock became present while the wizard/settings surface was active.
- Writer passed and a real config was written.
- The lock was released before restore.
- `kiosky-player.service` started without a ConditionPathExists skip.
- Loading-content feedback appeared.
- Public state reached player running.
- Playback reached playing.
- SSH and NetworkManager stayed active.

Observed latency:

- writer done to player active: about 2 seconds.
- writer done to playing: about 5 seconds.

After the successful runtime retest, the same script received one additional
failure-path guard so `write_final_status` also skips the long player wait if a
lock still exists. That guard does not change the successful restore path; it
was installed on the board and covered by the static restore-order check.

## Decision

C17.4.1 passed as a hotfix validation. It does not release batch flash or
dispatch by itself because the fix is not yet in a clean rebuilt image.
C17.4.2 should rebuild the image with this fix and validate on a clean card.
