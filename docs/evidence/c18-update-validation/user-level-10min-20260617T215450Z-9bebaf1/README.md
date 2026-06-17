# C18 user-level 10 minute playback check - 9bebaf1

Purpose: validate the currently installed homologation package against the
user-visible loop/stuck-media risk observed on the board.

Scope:

- board: `root@192.168.18.131`
- package: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`
- mode: currently running `kiosky-player.service`
- duration: 600 seconds
- collector: `scripts/board/c18_playback_health_collect.py`

Functional result: PASS.

Observed user-level signals:

- service stayed active;
- playback progressed;
- 9 media aliases observed;
- single MPV process;
- 0 MPV restarts;
- 0 systemd restarts;
- 0 media load failures;
- 0 status failures;
- 0 disk, MMC or panfrost fault deltas;
- no stuck-media pattern observed.

The original `playback-deep-health-public.json` was produced before IPC
calibration and failed only `ipc_stable_after_success`: 3 transient
`missing_socket` samples among 555 samples, with at most 2 consecutive samples.
Those samples occurred during media/frame transition states and did not coincide
with user-visible playback failure.

`playback-deep-health-public-after-ipc-calibration.json` is the same collected
artifact set evaluated with the calibrated duration-aware IPC threshold. It
passes while still rejecting IPC timeouts, non-`missing_socket` IPC errors,
excessive sparse socket loss, more than 2 consecutive missing-socket samples,
MPV restarts, media load failures and stuck-media/status divergence.

This is a homologation/user-level signal, not a production/H2 claim. Full H2
still requires the remaining production-only gates.
