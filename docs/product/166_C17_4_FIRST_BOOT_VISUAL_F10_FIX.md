# 166 - C17.4 - First Boot Visual/F10 Fix

Status: blocked pending clean-board validation

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

Pending:

- manual card write via Armbian Imager;
- clean-board first boot without config;
- first F10 response on first boot;
- HDMI confirmation that wizard remains visually exclusive;
- writer/player restore after completing the wizard.

## Decision

`ready_for_batch_flash=false`

`ready_for_dispatch=false`

`ready_for_c18_player_audit=false`

C17.4 must continue with a manually flashed clean card. C18 remains closed until
the first-boot pre-config journey passes on HDMI.
