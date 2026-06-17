# C18 user-level playback observation

Target package: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`

This evidence captures a fast user-level validation on the physical board after
the target package was applied successfully with the player service stopped
only for the apply step.

Outcome:

- Apply/adoption of the target package passed.
- Live board state after observation still selected the target package from
  `/data/player-runtime/current`.
- `kiosky-player.service` remained active with `NRestarts=0`.
- The 10-minute and 3-minute playback observations both showed media
  progression across 9 aliases, frame/time progression, no player restart, no
  media load failure, no kernel storage/GPU fault counters, and no status
  advance while MPV was stuck on an old path.
- The user-visible stuck-loop symptom was not reproduced.

Important limitation:

- The strict deep-health gate remains red because it treats transient
  `missing_socket` IPC samples as failures. That is preserved as a real
  harness/gate issue, not hidden as success.
- This is not a P0 power-loss result, not a 24h soak, and not an H2/stable
  production claim.

Machine-readable summary: `user-level-observation-summary.json`.
