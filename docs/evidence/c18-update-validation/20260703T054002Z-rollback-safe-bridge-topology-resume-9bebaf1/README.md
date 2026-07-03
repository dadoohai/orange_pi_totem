# C18 rollback-safe bridge topology - 9bebaf1

This evidence records the board transition from the old rollback topology to a
rollback-safe `previous` topology.

Final board state:

- `current`: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.
- `previous`: `c18.player-runtime-homolog-20260703-baseline-bridge-8ac1c63`.
- remaining quarantine: historical `m6-b2` only.

What passed:

- target adoption and service health before the bridge operation;
- bridge lab apply;
- bridge service adoption and 90s service health;
- target reapply from linked previous;
- final target service adoption and 120s service health.

Both bridge and final target service-health windows passed with one MPV,
`v4l2request-copy`, frame progress, media transitions, `media_load_failed=0`,
`mpv_restart=0`, and no watchdog recovery during the health window.

The committed subset intentionally excludes raw candidate logs/config/cache from
the board. It keeps only lab-apply summaries, adoption summaries, public health
artifacts, and candidate health/teardown summaries.

Non-claims:

- not production;
- not `stable`;
- not auto-pull;
- not public thaw;
- not a power-loss checkpoint by itself;
- not 24h soak.
