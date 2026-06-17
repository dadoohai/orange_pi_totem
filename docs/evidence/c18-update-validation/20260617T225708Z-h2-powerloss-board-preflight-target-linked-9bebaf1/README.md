# C18 H2 power-loss preflight - target already linked

Purpose: preserve the current read-only board state before the physical P0
session. This snapshot was collected after the user-level playback validation
of target `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

Result: expected BLOCKED preflight.

The board is healthy and the target package is installed, but the H2 power-loss
preflight gate correctly blocks fresh apply checkpoints while the target is
already linked as `/data/player-runtime/current`.

Gate blockers:

- `runtime_topology:topology_target_linked_blocks_apply_checkpoints`
- `runtime_topology:topology_after_previous_symlink_current_already_target`
- `runtime_topology:topology_target_release_dir_exists_for_fresh_apply`

Operational meaning:

- do not arm P0 from this topology;
- do not treat this as product playback failure;
- run the guarded fresh apply topology prep from the full runbook only at the
  start of the physical P0 session;
- rerun the preflight gate after topology prep and proceed only from a green
  preflight.

Non-claims:

- this is not power-loss evidence;
- this does not claim H2, 17/17, production, stable, public thaw or 24h soak;
- this does not execute topology reset, apply, rollback, arm, resume or power
  removal.

