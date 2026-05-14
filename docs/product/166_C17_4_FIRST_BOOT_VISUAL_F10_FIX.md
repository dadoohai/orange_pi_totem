# 166 - C17.4 - First Boot Visual/F10 Fix

Status: blocked by post-writer restore latency after clean-board runtime

C17.4 addresses the C17.3 blocker in the first energization / first
configuration journey. C17.3 failed before normal player operation: first boot
without config showed black HDMI, F10 did not open settings, recovery required
an emergency physical power cycle, and the second boot later showed the public
status renderer while the settings session lock was still active.

This is not C18. No scheduler, sync, duration, playlist, loop or
`exposure_time_ms` logic was changed.

## Cause Classification

Confirmed second-boot cause:

- `status_renderer_or_kiosky_restarted_during_open_settings_session`

The C17.3 runtime had `totem_setup_visual_wizard.py` alive on `tty2`,
`session_lock_present=true`, and `kiosky-player.service`/status MPV active at
the same time. That means the public config-missing/status surface could take
over HDMI while the wizard still owned the settings session.

Probable first-boot contributors:

- `first_boot_race_before_services`
- `hdmi_drm_not_ready`
- `network_online_wait_before_preconfig_feedback`

The original first boot had no retained journal, so these remain hypotheses.
C17.4 instruments first-boot phases under
`/data/state/totem-debug/c17-4-firstboot/` with sanitized events only.

Splash formatting cause:

- `text_layout_overflow`

The framebuffer splash used a panel that was too short for the C17.2 typography
scale, allowing title/message overlap in `config_pending`.

Confirmed C17.4 runtime blocker:

- `POST_WRITER_RESTORE_LATENCY_LOCK_ORDER`

The manually flashed C17.4 clean card fixed the C17.3 first-boot symptoms:
pre-config HDMI was visible, the initial splash did not overlap text, F10
responded on first boot, and the wizard opened with exclusive visual ownership.
After the wizard completed, the writer passed and a real config was created,
but the first post-writer snapshot still showed the settings-session lock
present and `kiosky-player.service` inactive. Without any additional operator
action, the screen later advanced to loading content and then playback.

The service did not restore promptly because the normal session path calls
`restore_service` while the settings-session lock is still present. The C17.4
unit then correctly skips `kiosky-player.service` because
`ConditionPathExists=!/run/totem/settings-session.lock` is unmet. The script
waits for player state before removing the lock, so restore is delayed until
the session finally exits and post-service cleanup can start the player.

## Ownership Rules

| State | Visual owner | F10 active | Public status allowed |
| --- | --- | --- | --- |
| boot/pre-config | boot splash, then launcher config_pending | after settings trigger starts | yes, only before settings session |
| config_missing | launcher/status renderer | yes | yes |
| settings opening | open-settings session | yes, already consumed | no |
| wizard active | `openvt` wizard on tty2 | session already active | no |
| saving | open-settings session | no | no |
| player starting/loading | launcher/player | yes | yes |
| player playing | player | yes | no status overlay |

Invariant: `/run/totem/settings-session.lock` means the wizard/settings session
has exclusive visual ownership. The launcher and status renderer must not draw
public config_missing/status screens while that lock exists.

## Changes

- `kiosky-player.service` no longer waits for `network-online.target` before
  pre-config feedback. It starts after `NetworkManager.service` and
  `totem-settings-trigger.service`, and is skipped while the settings-session
  lock exists.
- `kiosky_service_launcher.sh` checks `settings-session.lock` before public
  splash/status/player drawing and records sanitized C17.4 trace events.
- `totem_status_renderer.sh` refuses to start while the lock exists and exits if
  the lock appears while MPV is showing a status SVG.
- `totem_open_settings_session.sh` makes the lock visible as public metadata,
  records sanitized events, and releases the lock before restoring the player.
- `totem-firstboot-gate.service` runs even when the Armbian marker is absent, so
  it can leave sanitized first-boot instrumentation.
- `dadooh-visual-splash.service` waits briefly for framebuffer readiness.
- `totem_visual_splash.py` uses a taller panel and bounded title/message layout
  to remove config_pending overlap.

## Image

Generated private homologation image:

`/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c17-4-firstboot-visual-f10-fix_minimal.img`

SHA256:

`9e9092fb7dcb04a06e1617ad048042305a285373c19261b0dd10bc96c0975058`

Offline validation passed and kernel was reused. No Armbian Build, apt, pip or
kernel rebuild was invoked.

## Validation State

Passed offline:

- self-tests for wizard, Wi-Fi adapter, splash, config contract and updatectl;
- C16.2 synthetic UX harness;
- SVG gallery generation;
- C17.4 image derivation validation;
- rootfs checks for session-lock ownership rules;
- splash layout preview with separated title/message lines.

Passed on the clean board:

- manual card write via Armbian Imager;
- first boot without config showed visible pre-config feedback;
- first F10 response opened the wizard;
- initial splash text overlap was fixed;
- wizard visual ownership held while the settings session was active;
- status renderer, MPV and public config-missing surface did not draw over the
  wizard;
- writer passed and created the real config.

Eventually passed on the clean board, but too late:

- settings-session lock cleanup eventually completed;
- player restore eventually completed;
- public state reached player running;
- playback reached playing.

Blocked on product/UX timing:

- the player restore appeared only after a long delay without additional
  operator action;
- the loading-content transition was perceived as sudden;
- the post-writer restore order is not reliable enough for batch/dispatch.

Minor visual backlog:

- old orange `config_missing` style still appears after the initial C17.4
  splash. It did not block the flow and remains P2:
  `CONFIG_MISSING_STYLE_CONSISTENCY`.

## Decision

`ready_for_batch_flash=false`

`ready_for_dispatch=false`

`ready_for_c18_player_audit=false`

C17.4 must continue with a manually flashed clean card. C18 remains closed until
post-writer cleanup and player restore pass promptly on HDMI.

Next step:

`C17_4_1_SETTINGS_LOCK_RESTORE_LATENCY_FIX`

## C17.4.1 Follow-up

C17.4.1 implemented and hotfix-tested the settings lock restore ordering fix.
The normal successful settings path now removes the session lock before
requesting player restore, and `restore_service` refuses to start while the
lock still exists. Runtime retest passed with writer-to-player-active latency
around 2 seconds and writer-to-playing latency around 5 seconds.

C17.4 remains blocked for batch/dispatch because the fix still needs to be
rebuilt into a clean image and validated as C17.4.2.
