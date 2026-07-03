# C18 target 9bebaf1 live apply and short health

This evidence records a governed lab/homologation apply of
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1` on the live board
after the H2 power-loss campaign was held on baseline `m6-a`.

## Result

- Lab apply passed and promoted `9bebaf1` to `/data/player-runtime/current`.
- The previous runtime became `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`.
- The live service adopted the target and the running `kiosk.py` hash matched the
  verified marker.
- Public `player-runtime` apply/rollback/reconcile stayed frozen with `rc=44`.
- A 180s service deep-health passed with 9 media aliases observed, frame
  progress, `status_mpv_path_aligned=true`, and no MPV restart, media-load
  failure, panfrost, mmc, or ext4 errors.
- After a physical reboot requested by the operator, a 60s post-reboot
  deep-health also passed with frame progress, `status_mpv_path_aligned=true`,
  and no MPV restart, media-load failure, panfrost, mmc, or ext4 errors.

## Non-claims

This is not H2 power-loss evidence, not 24h soak, not stable promotion, not
production readiness, and not public player-runtime thaw.
