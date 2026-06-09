# C18 player-runtime power-loss trial: after_previous_symlink

This evidence records an operator-attended physical power-loss trial for the C18 `player-runtime` lab apply path.

## Scope proven

- Harness/source commit: `3519319` (`C18: add marker powerloss checkpoint evidence`).
- Candidate at cut: `c18.player-runtime-powerloss-b10-20260609T164158Z-3519319`.
- Existing active release: `c18.player-runtime-m6-a-20260609T0418Z-7107a55-r2`.
- Checkpoint armed: `after_previous_symlink` during lab apply.
- Reaching this checkpoint proves the apply control flow had already persisted `previous -> A`, while `current` still pointed to A and the candidate B10 was still only the verifying release.
- The checkpoint artifact was fsynced before the operator cut power.
- After power returned, the board continued adopting A from `/data/player-runtime/current`, passed deep-health before reconcile, passed reconcile as current-verified, and passed deep-health after reconcile.
- Public `player-runtime` apply/rollback/reconcile remained frozen (`rc=44`) in the lab reconcile sidecar and in the final board post-check.

## Expected partial state

This checkpoint intentionally proves that writing `previous -> A` is not promotion. Without `current -> B`, the launcher and reconcile must keep A selected.

## Non-claims

- This covers only the `after_previous_symlink` checkpoint.
- It does not prove cleanup of the verified-but-unlinked B10 release, later apply checkpoints, rollback checkpoints, long soak, production/stable rollout, server-side publish enforcement, or public thaw.
- It does not make `player-runtime` publicly available; this remains lab-only evidence.

## Key files

- `powerloss-checkpoint/checkpoint.json`: persisted checkpoint and runtime snapshot at cut.
- `powerloss-summary.json`: resume verdict.
- `resume/*-health/playback-deep-health-public.json`: deep-health summaries before and after reconcile.
- `resume/*-adoption.json`: launcher adoption identity checks for A.
- `resume/reconcile.json`: lab reconcile result and freeze sidecars.
- `raw/apply/candidate-health/`: raw candidate logs/samples captured before the cut. Some summary sidecars were intentionally not retained because the physical cut interrupted their final write; this evidence relies on the fsynced checkpoint and resume verdict, not on those partial sidecars.
- `postcheck.txt`: final live board state after resume.
- `evidence-manifest.json`: SHA-256 manifest for committed evidence files.
