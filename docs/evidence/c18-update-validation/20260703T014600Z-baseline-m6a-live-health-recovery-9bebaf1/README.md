# C18 baseline m6-a live health recovery

This evidence was collected after the H2 power-loss campaign hold. It checks the
live `m6-a` baseline without applying a new player-runtime package.

## Result

- Pre-restart health failed.
- Controlled `systemctl restart kiosky-player.service` was issued.
- Post-restart health passed.
- This is operational recovery evidence only; it does not count as H2
  power-loss evidence and does not unblock production.

## Practical meaning

The board can be restored to healthy playback by restarting the service, but the
baseline can still enter an unhealthy status/MPV alignment state. Do not resume
physical power-loss cuts until the baseline strategy is decided and the failed
`after_release_tree_fsync` checkpoint can be rerun cleanly.
