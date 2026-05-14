# 168 - C17.4.2 - Settings Restore Clean Image Validation

Status: passed clean-card validation

C17.4.1 passed as a hotfix on the already configured board. C17.4.2 packages
that restore-order fix into a new private homologation image so the complete
first-configuration journey can be validated from a clean card.

This remains outside C18. No scheduler, sync, duration, playlist, loop or
`exposure_time_ms` logic was changed.

## Image

Image:
`/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c17-4-2-settings-restore-clean_minimal.img`

SHA256:
`184ecdff1da3fc5f2f819b9be1a67da9e3cfaa87b8bdede7badddf2c1a22c5af`

The image was derived offline from the validated private base image. Armbian
Build, apt, pip, kernel tooling, U-Boot, DTB and BSP were not invoked.

## Embedded Fix

The C17.4.1 settings restore fix is embedded:

- `release_session_lock_for_restore` runs before player restore;
- `restore_service` refuses to start the player while the settings lock exists;
- `write_final_status` avoids a long player wait while the lock exists;
- the static restore-order check passes;
- C17.4 first-boot/F10/visual ownership changes are preserved;
- C17.2 visual polish and C15.3.2 loading-content feedback are preserved.

## Offline Validation

Offline rootfs validation passed:

- `artifact_private=true`;
- `final_image=false`;
- `homologation_shipping_image=true`;
- kernel reused;
- C17.4.1 restore-order checks passed;
- C14 updater, C15 UX fixes, C16/C17 gates and C17.2 visual polish remain
  present where expected;
- QA/evidence artifacts are not installed into the appliance layer.

## Runtime Status

Clean-card runtime validation passed after manual flashing through Armbian
Imager.

Operator HDMI observation confirmed:

- first boot did not stay black;
- pre-config/config_missing feedback appeared;
- config_missing was legible and did not show the previous overlap;
- F10 opened the wizard on the first boot.

Sanitized SSH/runtime evidence confirmed:

- writer passed;
- real config was written without publishing contents;
- settings lock was removed before player restore;
- `kiosky-player.service` was not skipped by the session-lock condition;
- `totem-open-settings.service` finished instead of staying `activating`;
- player service became active about 2 seconds after write/config completion;
- playback reached `playing`;
- SSH and NetworkManager remained active.

Observed latency:

- writer/config completion to player active: about 2 seconds;
- writer/config completion to playback `playing`: about 32 seconds.

The longer playback time was content/media availability after restore, not a
settings-lock restore delay.

## Clean-Card Criteria

The next validation must prove:

1. first boot shows pre-config feedback and does not stay black;
2. F10 opens the wizard on the first boot;
3. the wizard owns the visual surface while settings are active;
4. writer passes;
5. the settings lock is removed before player restore;
6. the player is not skipped by the ConditionPathExists guard;
7. `totem-open-settings.service` does not remain activating;
8. player restore is fast;
9. SSH and NetworkManager remain active;
10. playback reaches `playing` or `loading_content` followed by `playing`.

## Decision

`c17_4_2_status=passed`

`ready_for_batch_flash=true`

`ready_for_dispatch=true`

`ready_for_c18_player_audit=true`

C18 can open after this point, but C17.4.2 does not start C18 and did not
change scheduler, sync, duration, playlist, loop or `exposure_time_ms`.

## Follow-Up

C17.5 was opened before C18 to add a `totem-core` remote update MVP for
wizard/configurator/splash/status changes. That allows C17.6 to deliver the
`environment_id` UX update remotely instead of rebuilding the full image for
each small UI change.
