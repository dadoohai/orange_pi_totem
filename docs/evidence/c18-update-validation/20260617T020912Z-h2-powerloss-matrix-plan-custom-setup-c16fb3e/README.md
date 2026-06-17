# C18 H2 Power-Loss Matrix Plan - Custom Setup Guard

Offline planning artifact for the `player-runtime` homologation package
`c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`.

This directory is not physical power-loss evidence. It records the current H2
matrix state and emits board command skeletons for the remaining physical
checkpoints.

## Result

- Schema: `dadooh.c18.player_runtime.powerloss_matrix_plan.v1`
- Result claim: `powerloss_matrix_plan_incomplete`
- Covered checkpoints: 5/17
- Missing checkpoints: 12/17
- Blockers in the planner itself: none

## Covered

- `after_current_symlink`
- `rollback_after_current_to_previous`
- `rollback_after_previous_removed`
- `rollback_after_quarantine`
- `rollback_after_state_success`

## Missing

- `after_payload_staged`
- `after_release_dir_created`
- `after_extract`
- `after_state_verifying`
- `after_health_passed`
- `after_release_tree_fsync`
- `after_marker_written`
- `after_previous_symlink`
- `after_state_success`
- `before_stage_cleanup`
- `rollback_after_identify_links`
- `rollback_after_current_unlinked`

## Custom Setup Guard

The plan now emits explicit `manual_setup_instructions` for:

- `after_previous_symlink`;
- `rollback_after_current_unlinked`.

The operator runbook builder must fail closed when a checkpoint declares
`requires_custom_setup=true` without either setup commands or manual setup
instructions.

## Non-Claims

- No 17/17 power-loss claim.
- No physical power cut claim.
- No boot transition claim.
- No health/reconcile/adoption pass claim.
- No H2 readiness, stable, production, publish/fetch, or public thaw claim.
- No customer data preparation claim.
