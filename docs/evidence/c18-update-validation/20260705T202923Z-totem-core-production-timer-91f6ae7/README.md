# C18 totem-core production timer evidence

Run started after the production image was physically flashed and booted on the lab board.

- Local boot marker noted: 2026-07-05 16:51:06 -03.
- Board IP: 192.168.18.131.
- Image marker: c18-hwdecode-prod-1 / c18.image-prod.1.
- Timer trigger observed: 2026-07-05 16:58:43 -03.
- Applied release: totem-core-c18.ota-core-prod-20260705T184013Z-ccaf5a1.
- Applied version: c18.ota-core-prod-20260705T184013Z-ccaf5a1.
- Rollback target: c17.6-environment-input-20260514T211247Z.

Evidence:

- `post-timer-summary.json`: live board collection after production auto-pull.
- `post-timer-gate.json`: offline gate result for the post-timer collection.
- `post-rollback-summary.json`: live board collection after governed totem-core rollback.
- `production-timer-complete-gate.json`: offline gate result for timer plus rollback.

Result:

- Production timer was enabled and active.
- The timer applied the expected stable totem-core release.
- Governed rollback returned to the embedded totem-core version.
- `kiosky-player.service` stayed active with `NRestarts=0` in both collections.
- Public player-runtime rollback remained frozen with rc=44.

Non-claims:

- This does not thaw player-runtime.
- This does not update media-system, kernel, MPV or ffmpeg.
- This does not publish a new release.
- This does not prove player-runtime auto-pull.
