# C18 fresh user-level playback check - 9bebaf1

Purpose: preserve a short, current, user-visible playback signal after the
final static-check alignment commit `9acc7f0`.

Scope:

- board: `root@192.168.18.131`
- package: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`
- source commit of package: `9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522`
- runtime link observed before collection:
  `/data/player-runtime/releases/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`
- mode: currently running `kiosky-player.service`
- duration: 120 seconds
- collector: `scripts/board/c18_playback_health_collect.py`

Functional result: PASS.

Observed user-level signals:

- service stayed active;
- playback progressed;
- 9 media aliases observed;
- single MPV process;
- expected hwdecode stack observed;
- 0 MPV restarts;
- 0 systemd restarts;
- 0 media load failures;
- 0 status failure samples;
- 0 disk, MMC or panfrost fault deltas;
- no stuck-media/status divergence observed.

This is homologation/user-level evidence. It does not claim H2, production,
stable, public thaw, 17/17 power-loss or 24h soak.
