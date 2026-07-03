# C18 H2 Power-Loss Campaign Start

This record preserves the starting context for the remaining C18 H2
power-loss campaign before physical board cuts resume.

## Starting Point

- UTC anchor: `2026-07-03T00:14:00Z`
- Repo HEAD: `7557c91f5cc6c0b29d49df8414d7ac4e585e63fb`
- Branch: `foundation-v0.1`
- Target source commit: `9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522`
- Target package: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`
- Last macro result: homologation pilot roundtrip passed, current board
  topology restored to the verified baseline runtime, and public
  `player-runtime` freeze remained `rc=44`.

## Mission

Close the remaining C18 H2 physical power-loss evidence front for
`player-runtime`, without converting homologation into production. The
campaign should prove that the board survives physical power removal at
all required update and rollback checkpoints.

## Matrix State

- Required H2 power-loss checkpoints: `17`
- Already covered checkpoints: `5`
- Remaining checkpoints to execute: `12`
- Matrix plan:
  `docs/evidence/c18-update-validation/20260618T080037Z-h2-powerloss-matrix-plan-5of17-9bebaf1/powerloss-matrix-plan.json`
- Operator runbook:
  `docs/evidence/c18-update-validation/20260618T080100Z-h2-powerloss-operator-runbook-remaining-12-9bebaf1/operator-runbook.md`

## Remaining Checkpoints

1. `after_payload_staged`
2. `after_release_dir_created`
3. `after_extract`
4. `after_state_verifying`
5. `after_health_passed`
6. `after_release_tree_fsync`
7. `after_marker_written`
8. `after_previous_symlink`
9. `after_state_success`
10. `before_stage_cleanup`
11. `rollback_after_identify_links`
12. `rollback_after_current_unlinked`

## Guardrails

- Use only governed C18 scripts for apply, rollback, topology reset,
  preflight, and evidence collection.
- Do not use remote reboot as a substitute for physical power loss.
- Cut power only after the harness prints and persists `CUT_POWER_NOW`.
- After every cut, wait for SSH, run the matching resume phase, verify
  service/playback health, and keep the board recoverable before moving
  to the next checkpoint.
- Do not publish, promote stable, enable auto-pull, or open public thaw.
- Keep credentials, private network details, and raw operational secrets
  out of committed evidence.

## Production Boundary

This campaign can close the physical power-loss portion of H2. Production
still remains blocked until the complete H2 gate is green, including the
24-hour soak, stable promotion evidence, and formal thaw/operator decision.
