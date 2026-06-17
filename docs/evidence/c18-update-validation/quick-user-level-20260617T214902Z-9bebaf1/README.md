# C18 quick user-level playback check - 9bebaf1

Purpose: fast, non-destructive validation that the currently installed
`player-runtime` homologation package is usable at user level on the board.

Scope:

- board: `root@192.168.18.131`
- package: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`
- mode: currently running `kiosky-player.service`
- duration: 120 seconds
- collector: `scripts/board/c18_playback_health_collect.py`

Result: PASS.

Functional signals:

- service active;
- playback progressed;
- 9 media aliases observed;
- single MPV process;
- 0 MPV restarts;
- 0 systemd restarts;
- 0 media load failures;
- 0 status failures;
- 0 disk, MMC or panfrost fault deltas;
- no stuck-media pattern observed.

This is not a production/H2 claim. It is a user-level homologation signal used
to prioritize practical playback behavior before longer production-only gates
such as 24h soak and full 17/17 power-loss coverage.
