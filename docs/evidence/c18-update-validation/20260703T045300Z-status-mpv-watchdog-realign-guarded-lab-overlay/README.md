# C18 status/MPV watchdog realign guard - lab overlay

This directory records a live board run with the updated status/MPV watchdog
and updated deep-health collector.

Key facts:

- The watchdog action during the collection window was `realign_mpv_to_status`.
- The player service stayed active and there was no systemd restart.
- The original collector undercounted player events because the MPV restart was
  present only in the service journal, not in the local MPV log files it scanned.
  The captured journal shows one `Restarting MPV` event in the collection
  window; do not use the original zero `mpv_restart` counter as a clean-health
  claim.
- Deep-health failed, as expected, because a watchdog recovery occurred during
  the evidence window.
- Deep-health also still failed `status_mpv_path_aligned`: the IPC realign
  reduced the operational blast radius, but did not make the old rollback
  runtime safe enough for H2 evidence.
- The new `deep-health-watchdog.json` sidecar captured the watchdog state before
  and after the run, and the summary rejected the evidence instead of letting
  the recovery mask the mismatch.

This is a governance/hardening result, not an H2 pass. It proves that
watchdog-assisted recovery is now visible to deep-health and keeps the
power-loss evidence red when recovery happens inside the collection window.
It also records why the collector was hardened afterward to count both local MPV
logs and the service journal for `media_load_failed` / `mpv_restart`.

Non-claims:

- Not an official H2 power-loss checkpoint pass.
- Not a flashed-image identity.
- Not stable or production readiness.
- Not public `player-runtime` thaw.
- Does not prove that watchdog realign solves the status/MPV loop.
- Does not remove the remaining H2 power-loss and 24h soak requirements.

Primary files:

- `guarded-realign-summary.json`
- `event/status-mpv-watchdog-state.json`
- `event/journal-watchdog-realign.txt`
- `health/deep-health-watchdog.json`
- `health/playback-deep-health-public.json`
- `health/playback-samples.tsv`
