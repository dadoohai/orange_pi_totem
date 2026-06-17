# C18 H2 Power-Loss Board Preflight - MPV Stuck Fix

Read-only board preflight before a physical power-loss session. This is not power-loss evidence and does not make H2 green.

- preflight_passed: `True`
- preflight_result_claim: `h2_powerloss_board_preflight_collected`
- gate_exit_code: `1`
- gate_passed: `False`
- gate_result_claim: `h2_powerloss_board_preflight_blocked`
- captured_at_utc: `2026-06-17T19:40:30Z`
- target_package_version: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`
- source_commit: `9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522`
- payload_sha256: `d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0`
- image_tag: `c18-hwdecode-lab-1x`
- bundle_dir: `/data/c18-powerloss-bundle-3eb06f1`
- evidence_root: `/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1`

## Gate blockers

- `runtime_topology:topology_target_linked_blocks_apply_checkpoints`
- `runtime_topology:topology_after_previous_symlink_current_already_target`
- `runtime_topology:topology_target_release_dir_exists_for_fresh_apply`

## Interpretation

The board, package, policy, timer, wrappers and canary are visible and the read-only collector passed. The offline preflight gate blocks the physical matrix session because the target package is already linked as current, so fresh apply checkpoints require topology reset/custom setup before arming.

## Non-claims

- `this_preflight_is_not_powerloss_evidence`
- `this_preflight_does_not_claim_17_17`
- `this_preflight_does_not_arm_or_resume_trials`
- `this_preflight_does_not_replace_physical_power_cut`
- `this_preflight_does_not_create_or_modify_evidence`
- `this_preflight_does_not_apply_or_rollback_player_runtime`
- `this_preflight_does_not_probe_or_prove_public_freeze_rc44`
- `this_preflight_does_not_authorize_stable_or_production`
- `this_preflight_does_not_thaw_player_runtime`
- `this_preflight_does_not_publish_or_fetch_releases`
