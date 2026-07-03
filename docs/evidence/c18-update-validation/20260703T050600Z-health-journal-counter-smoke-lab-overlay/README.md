# C18 deep-health journal counter smoke - lab overlay

This directory records a short live-board deep-health run using the collector
that counts player events from both local MPV logs and the service journal.

Key facts:

- Collection window: `2026-07-03T05:05:04Z` to `2026-07-03T05:06:34Z`.
- `deep-health-player-counters.json` includes journal-derived fields:
  `journal_media_load_failed`, `journal_mpv_restart`, and
  `journal_query_failed`.
- The journal query succeeded (`journal_query_failed=false`).
- No watchdog recovery occurred during this short window.
- The player service stayed active with one MPV process and `v4l2request-copy`.

This is a smoke test for collector honesty after the earlier guarded realign
evidence exposed that local MPV log files alone can undercount player events.

Non-claims:

- Not an official H2 power-loss checkpoint pass.
- Not a 24h soak.
- Not stable or production readiness.
- Not public `player-runtime` thaw.
- Does not prove the old rollback runtime is safe for H2.

Primary files:

- `deep-health-player-counters.json`
- `deep-health-watchdog.json`
- `playback-deep-health-public.json`
- `playback-samples.tsv`
