# C18 H2 Power-Loss Campaign Hold: baseline m6-a status/MPV mismatch

This record preserves the current macro state after the 2026-07-03 H2
power-loss round for target `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

## Outcome

- Accumulated power-loss evidence now covers 10/17 checkpoints: 5 historical
  pilot/P0 checkpoints plus 5 new H2 checkpoints from this round.
- The campaign stopped at `after_release_tree_fsync`.
- The failed checkpoint is not counted as passing H2 evidence.
- The board was recovered by a controlled service restart and post-restart
  health passed, but that recovery is operational only.

## RCA summary

The target package `9bebaf1` contains MPV current-path verification before
publishing public status. The active fallback baseline on the board,
`c18.player-runtime-m6-a-20260610T0501Z-29ff33b`, does not contain that guard.

After the physical cut at `after_release_tree_fsync`, the board returned to the
verified `m6-a` baseline. Deep-health then observed public status advancing
through multiple media aliases while MPV remained on a single media. This is the
same class of user-visible loop/stuck-media failure that C18 must prevent.

## Decisions

- Do not relax `status_mpv_path_aligned`.
- Do not count a service restart recovery as H2 power-loss success.
- Keep H2/prod blocked until the failed checkpoint is rerun cleanly.
- Use `--recover-on-health-failure` only to return the board to an operable
  state and collect diagnostics; the power-loss gate rejects recovery as a pass.

## Next resume point

Remaining checkpoints:

- `after_release_tree_fsync`
- `after_marker_written`
- `after_previous_symlink`
- `after_state_success`
- `before_stage_cleanup`
- `rollback_after_identify_links`
- `rollback_after_current_unlinked`

Before resuming cuts, decide the baseline strategy: either prove the old `m6-a`
baseline can stay user-healthy after this interruption class, or run a governed
campaign path whose starting runtime already includes the `9bebaf1` status/MPV
alignment guard. Production/stable still also require full 17/17, 24h soak,
stable promotion, and formal thaw decision.
