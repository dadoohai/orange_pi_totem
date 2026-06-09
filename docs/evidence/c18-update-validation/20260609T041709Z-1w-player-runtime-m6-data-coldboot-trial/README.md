# C18 1w player-runtime M6 data cold-boot trial

This directory records the decisive lab-only M6 trial for `c18-hwdecode-lab-1w`.

## Scope proven

- Image: `c18-hwdecode-lab-1w`
- Image SHA256: `0070561e3a714eeb4543beb9930f9801c344161f9123c57a78a92431713bc39e`
- Image marker SHA256: `74701b5a91b74b067aa3434802b61d4f4fa5ea4dce5db7e60ca99989ecf077cf`
- Repo commit: `7107a55933497a7c60bb0ebad5f978249d3b16f2`
- Flow: A -> B -> cold boot with B selected from `/data` -> rollback to A -> reconcile.
- The host release gate accepted this evidence in decisive mode: see `m6-release-gate-host.json`.

The candidate B health window proved HW decode (`v4l2request-copy`), frame progress, single candidate MPV, clean candidate teardown, and zero panfrost fault delta. The cold-boot and rollback service windows also passed deep-health.

## Non-claims

- Public `player-runtime` OTA remains frozen.
- Public `kiosky-player` OTA remains frozen.
- This does not claim stable/production publish, auto-pull, GitHub release safety, physical power-loss safety, or soak/endurance.
- The on-board M6 run deferred the final release gate because the board does not carry the host git environment; the decisive gate was run on the host after copying the sanitized evidence.
