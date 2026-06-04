# C18 Display Blackout Conclusion - 2026-06-04

## Decision

The black-screen event is classified as `sink_hung_board_healthy`.

The board-side pipeline stayed healthy: player alive, one MPV process, hardware
decode active, frames advancing, KMS active, and the HDMI/TCON clock branch
enabled at the active mode rate. Video recovered only after a hard power cycle
of the display/sink, with the board untouched.

This is not evidence of an OTA, totem-core, player-runtime, MPV, panfrost, or
KMS regression.

## Key Evidence

- Board uptime stayed continuous through the recovery test.
- MPV process stayed the same and `NRestarts` stayed zero.
- MPV IPC showed `hwdec-current=v4l2request-copy`, `current-vo=gpu`,
  `vo-configured=true`, and frame counters advancing.
- KMS had an active CRTC, connected HDMI connector, and a plane covering the
  active `1360x768` mode.
- `clk_summary` showed display and HDMI clocks enabled at the mode rate.
- A power event caused a large burst of HDMI HPD events, but the burst ended and
  the board continued operating.
- A manual TV-side hard power cycle produced normal plugout/plugin events and
  restored video without board reboot or service restart.

## Red Herring

Do not use `tmds_char_rate=0` from the DRM state file as proof that HDMI output
is dead on this BSP. In this incident it stayed zero while `clk_summary` and the
active mode showed the HDMI clock path was live.

## Product Implications

Current C18 deep-health is a playback/decode health check. It is necessary for
OTA safety, but it is not a physical-display visibility proof.

A future display diagnostic can classify:

- `display_ok`: playback, scanout, and sink signals are coherent.
- `sink_hung_board_healthy`: playback and scanout are healthy, but the sink
  appears nonresponsive or recently suffered HPD noise.
- `pipeline_stalled`: playback or scanout has stopped while the sink is present.
- `no_sink`: HDMI is disconnected or EDID/HPD is absent.

For `sink_hung_board_healthy`, do not reboot the board automatically. Prefer
telemetry and an operator-facing instruction to power-cycle the display/sink.
Any future display nudge must be rate-limited, logged, and proven safe.

## OTA Impact

No OTA/player-runtime work is blocked by this incident. Keep the display
collector as backlog and return to the C18 update validation path.
