# 167 - C17.4.1 - Settings Lock Restore Fix

Status: passed hotfix validation, pending C17.4.2 image rebuild

C17.4 fixed the first-boot and F10 user journey, but the post-writer restore
path still had a product blocker: after the writer passed, the player appeared
only after a long delay. This was classified as
`POST_WRITER_RESTORE_LATENCY_LOCK_ORDER`.

This remains outside C18. No scheduler, sync, duration, playlist, loop or
`exposure_time_ms` logic was changed.

## Cause

The normal successful settings path had this order:

1. Wizard/settings session acquired the visual session lock.
2. Wizard completed.
3. Writer passed.
4. `restore_service` was called while the lock still existed.
5. `kiosky-player.service` skipped start because
   `ConditionPathExists=!/run/totem/settings-session.lock` was unmet.
6. The script waited for player state before removing the lock.
7. The player eventually started only after service cleanup removed the lock.

## Fix

The successful session path now releases the settings lock before restoring the
player:

1. `writer_done`
2. `settings_visual_done`
3. `release_session_lock`
4. `restore_player_start`
5. `restore_player_done`
6. `session_done`

`restore_service` now also refuses to start the player while the lock exists,
recording the blocked condition instead of creating another long wait.
`write_final_status` has the same lock-aware guard for the failure path, so an
unreleased lock cannot create a second long wait while writing final session
metadata.

## Retest

The hotfix was applied to the current board without rebooting, powering off,
changing Wi-Fi, reading config content or invoking writer manually.

Runtime retest via the normal F10/settings path passed:

- writer passed;
- lock was removed before restore;
- player restore was requested after lock removal;
- `kiosky-player.service` was not skipped by the ConditionPathExists guard;
- `totem-open-settings.service` finished instead of staying activating;
- loading-content feedback appeared;
- playback reached playing;
- SSH and NetworkManager remained active.

Observed latency:

- writer done to player active: about 2 seconds;
- writer done to playing: about 5 seconds.

## Decision

`c17_4_1_status=passed`

`ready_for_c17_4_2_image_rebuild=true`

`ready_for_batch_flash=false`

`ready_for_dispatch=false`

`ready_for_c18_player_audit=false`

C17.4.2 should rebuild the image with this fix and validate the same flow on a
clean card before batch flash, dispatch or C18 can open.
