# C18 service deep-health after IPC calibration

Target package: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`

Purpose: validate the calibrated playback deep-health rule on the physical
board, using service mode without `--match-process-ipc`.

Outcome:

- `playback-health-3min.rc` is `0`.
- `playback-health-3min.json` has `passed=true` and no `failure_reasons`.
- Adoption before and after health passed for the target package.
- `kiosky-player.service` stayed active with `NRestarts=0`.
- `/data/player-runtime/current` stayed on the target release.
- `/data/player-runtime/previous` stayed on the prior release for rollback.
- Playback covered 9 aliases with MPV/status alignment, frame/time progress,
  no MPV restart, no media-load failure, and no kernel GPU/storage deltas.
- One transient `missing_socket` IPC sample was tolerated; timeout and
  non-`missing_socket` IPC errors remain blockers, and MPV stuck-on-old-media
  remains covered by `status_mpv_path_aligned`.

This is not a P0 power-loss result, not a 24h soak, and not an H2/stable
production claim.
