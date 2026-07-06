# C18 Display Profile D1 - Baseline

Collected read-only on the lab board on 2026-07-06.

## Result

- Board public state: `player_running`.
- Player playback state: `playing`.
- Generic display status classification: `unknown`.
- Display profile baseline classification: `edid_missing_low_mode_fallback`.
- HDMI connector is connected and enabled, but the EDID summary reports `0` bytes.
- Available modes reported by DRM: `1024x768, 800x600, 848x480, 640x480`.
- No `video=...` HDMI mode override is present in the sanitized cmdline summary.

## Interpretation

This is a display negotiation/profile issue: the board and player are alive, but
the display did not provide useful EDID and the stack fell back to low modes.
This evidence does not justify changing player-runtime or forcing resolution by
OTA common. It supports the next step: test a small display matrix and only then
decide whether a lab image with a forced HDMI mode is needed.

## Files

- `board-readonly/`: legacy read-only diagnostics accepted by the existing gate.
- `c18-display-profile-baseline.json`: D1 display-profile baseline accepted by
  `scripts/qa/c18_display_profile_baseline_gate.py`.

## Non-Claims

- No service was restarted.
- No resolution was forced.
- No raw EDID, framebuffer, config content, media, journal or network data is included.
- This is not playback decode health, H2, stable, production, auto-pull or thaw evidence.
