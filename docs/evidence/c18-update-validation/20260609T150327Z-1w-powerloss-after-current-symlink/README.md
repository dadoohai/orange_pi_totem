# C18 player-runtime power-loss trial: after_current_symlink

This evidence records an operator-attended physical power-loss trial for the C18 `player-runtime` lab path.

## Scope proven

- Board marker used for trial context: `c18-hwdecode-lab-1w-image` (pre-checked by SSH before arming; this evidence directory does not include a standalone raw marker-read artifact).
- Harness commit: `5c4f09d` (`C18: hold player service during powerloss apply health`).
- Checkpoint armed: `after_current_symlink` during lab apply.
- Candidate at cut: `c18.player-runtime-powerloss-b3-20260609T150100Z-5c4f09d`.
- Restore target: `c18.player-runtime-m6-a-20260609T0418Z-7107a55-r2`.
- The checkpoint artifact was fsynced before the operator cut power.
- After power returned, the board adopted B3 from `/data/player-runtime/current`, passed deep-health before reconcile, passed reconcile as current-verified, passed deep-health after reconcile, then rolled back to A and passed deep-health after restore.
- Public `player-runtime` apply/rollback/reconcile remained frozen (`rc=44`) in the lab rollback/reconcile sidecars.

## Non-claims

- This covers only the `after_current_symlink` checkpoint.
- It does not prove power-loss safety for extract, marker write, previous symlink, rollback checkpoints, long soak, production/stable rollout, server-side publish enforcement, or public thaw.
- It does not make `player-runtime` publicly available; this remains lab-only evidence.

## Key files

- `powerloss-checkpoint/checkpoint.json`: persisted checkpoint and runtime snapshot at cut.
- `powerloss-summary.json`: resume verdict and rollback restore summary.
- `resume/*-health/playback-deep-health-public.json`: deep-health summaries before reconcile, after reconcile, and after restore.
- `resume/*-adoption.json`: launcher adoption identity checks.
- `resume/reconcile.json` and `resume/restore-rollback.json`: lab reconcile and restore rollback results.
- `evidence-manifest.json`: SHA-256 manifest for committed evidence files.
