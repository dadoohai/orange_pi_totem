# C18 Display Blackout Evidence - 2026-06-04

Read-only evidence captured before reboot/restart after a reported physical
black screen. The board was still reachable over SSH and the user confirmed the
cable/display path worked with other computers.

## Interpretation

- Player/update path looked healthy: `kiosky-player` active, `NRestarts=0`, one
  MPV process from `/opt/totem/hwdecode/bin/mpv`, `vo=gpu`,
  `hwdec-current=v4l2request-copy`, and frame/time counters progressing.
- HDMI/KMS also looked active from the kernel point of view: connector
  `connected/enabled/DPMS On`, EDID present, active CRTC, and a plane with a
  framebuffer covering `1360x768`.
- This does not prove visible light on the panel. It proves that current
  deep-health is a playback/decode health check, not a physical scanout/sink
  health check.

## Working Hypothesis

Most likely class: display/DRM/sink/handshake issue after a power event, or a
black rendered frame despite healthy playback counters. It is not evidence of
an OTA/player-runtime regression.

## Follow-up

Do not block the C18 OTA/player-runtime delivery track on this incident. Add a
small read-only display-blackout collector later, ideally as a totem-core
diagnostic, that captures:

- connector status, enabled, DPMS, EDID hash and active mode;
- `/sys/kernel/debug/dri/*/state` filtered to connector/CRTC/plane/fb fields;
- MPV IPC properties already used by deep-health;
- optional framebuffer/screenshot/luma evidence if it can be collected without
  disrupting playback or leaking media.

Until then, classify this state as `playback_ok_scanout_unproven`.
