# C18 Current Runtime User-Level Playback Diagnostic

A fresh non-destructive 120 second playback deep-health collection found a current runtime playback/status divergence on the board.

## Result

- Deep-health result: FAIL.
- Failure reason: `status_mpv_path_aligned`.
- Runtime actually current on the board after collection: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`.
- Target package `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1` was not the current runtime during this observation.
- Service stayed active: `True`.
- Playback progressed: `True`.
- Single MPV process: `True`.
- Expected hwdecode observed: `True`.
- MPV unique aliases: `1`.
- Status unique aliases: `9`.
- Status advanced without MPV: `true`.
- Status/MPV mismatch samples: `105` of `120`.
- Media load failures: `0`; MPV restarts: `0`; systemd restarts delta: `0`.

## Interpretation

This preserves a user-level functional issue on the board's current runtime/baseline. It does not prove the `9bebaf1` package is defective, because that package was not current when the evidence was collected. It does mean the next physical H2 session should not assume the board's current baseline is healthy without a fresh target apply/topology check.

## Non-Claims

- This does not prove root cause.
- This does not validate the target package.
- This does not authorize production.
- This does not promote stable.
- This does not thaw public player-runtime.
- This does not satisfy power-loss 17/17 or soak 24h.
