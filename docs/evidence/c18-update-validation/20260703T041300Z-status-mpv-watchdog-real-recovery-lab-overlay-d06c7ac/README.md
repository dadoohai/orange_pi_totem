# C18 status/MPV watchdog real recovery - lab overlay

This directory records a live board event where the status/MPV watchdog
terminated the real `kiosky-player` process after detecting
`status_advanced_without_mpv`, and the launcher started a new player process.

Key facts:

- Board service stayed active.
- Watchdog action: `terminate_player_child`.
- Watchdog reason: `status_advanced_without_mpv`.
- Event recorded at: `2026-07-03T04:18:25Z`.
- A 90s health window that included the intervention failed, as expected,
  because it captured the stuck interval and restart.
- A 45s health window after recovery passed with `v4l2request-copy`, frames
  advancing, MPV/status aligned, no MPV restart, no systemd restart, and no
  kernel/storage deltas.

This is stronger than the prior fake mismatch test because it used the real
player process and real playback state on the board. It remains lab-overlay
evidence only.

Non-claims:

- Not an official H2 power-loss checkpoint pass.
- Not a flashed-image identity.
- Not stable or production readiness.
- Not public `player-runtime` thaw.
- Does not remove the remaining H2 power-loss and 24h soak requirements.

Primary files:

- `watchdog-real-recovery-summary.json`
- `event/status-mpv-watchdog-state.json`
- `event/journal-watchdog-recovery.txt`
- `health/c18-watchdog-real-recovery-health-clean/playback-deep-health-public.json`
- `health/c18-watchdog-post-recovery-health-45/playback-deep-health-public.json`
