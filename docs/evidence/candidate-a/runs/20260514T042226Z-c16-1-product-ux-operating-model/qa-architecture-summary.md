# C16.1 QA Architecture Summary

This run is offline only. It does not access the lab board, SSH, Wi-Fi,
NetworkManager, real config, writer, seed, media cache, or private values.

## Levels

- Level 1: SVG/offline gallery for copy, layout and density.
- Level 2: PNG/screenshot rendering when a converter is already available.
- Level 3: runtime status/timeline probes over SSH with sanitized signals.
- Level 4: framebuffer capture only when safe, with DRM/MPV limitations noted.
- Level 5: HDMI capture/camera for final perception of flicker and black gaps.
- Level 6: synthetic user review combining journey, screen, state and rubric.

Codex stays on the builder. The board should only run small probes when a
runtime validation card explicitly allows it.
