# C18 Display Blackout Evidence - 2026-06-04

Read-only evidence captured before reboot/restart after a reported physical
black screen. The board was still reachable over SSH and the user confirmed the
cable/display path worked with other computers.

## Final Classification

`sink_hung_board_healthy`

Follow-up testing recovered video by hard power-cycling only the display/sink.
The board was not rebooted, the player process stayed alive, and systemd did not
restart the kiosk. This makes the incident a display/sink firmware hang, not a
C18 playback, OTA, or player-runtime regression.

## Interpretation

- Player/update path looked healthy: `kiosky-player` active, `NRestarts=0`, one
  MPV process from `/opt/totem/hwdecode/bin/mpv`, `vo=gpu`,
  `hwdec-current=v4l2request-copy`, and frame/time counters progressing.
- HDMI/KMS also looked active from the kernel point of view: connector
  `connected/enabled/DPMS On`, EDID present, active CRTC, and a plane with a
  framebuffer covering `1360x768`.
- Later clock/debug evidence showed the HDMI/TCON clock branch enabled at the
  active mode rate, and the TV-side hard power cycle restored video with the
  board untouched.
- The driver field `tmds_char_rate=0` was a red herring on this BSP. Use
  `clk_summary`, active CRTC mode, framebuffer flip, and MPV progress instead.

## Cause

Most likely class: the display/sink firmware hung after the same power event
that generated HDMI HPD noise. The board continued decoding and scanning out
video. The sink required a hard power cycle.

## Follow-up

Do not block the C18 OTA/player-runtime delivery track on this incident.

Add a small read-only display-blackout collector later, ideally as a totem-core
diagnostic, that captures:

- connector status, enabled, DPMS, EDID hash and active mode;
- `/sys/kernel/debug/dri/*/state` filtered to connector/CRTC/plane/fb fields;
- MPV IPC properties already used by deep-health;
- display clock branch state from `clk_summary`;
- HDMI HPD event counts/rate over monotonic time;
- optional framebuffer/screenshot/luma evidence only if it can be collected
  without disrupting playback or leaking media.

Self-heal should not reboot the board for this class. The useful response is
telemetry/alerting, and at most a rate-limited display nudge if a future
implementation proves it is safe. The known recovery was a sink-side hard power
cycle.
