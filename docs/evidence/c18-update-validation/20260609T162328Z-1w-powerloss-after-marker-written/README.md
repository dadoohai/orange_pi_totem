# C18 player-runtime power-loss trial: after_marker_written

This evidence records an operator-attended physical power-loss trial for the C18 `player-runtime` lab apply path.

## Scope proven

- Harness/source commit: `8e8ab86` (`C18: add rollback powerloss checkpoint evidence`).
- Candidate at cut: `c18.player-runtime-powerloss-b9-20260609T162147Z-8e8ab86`.
- Existing active release: `c18.player-runtime-m6-a-20260609T0418Z-7107a55-r2`.
- Checkpoint armed: `after_marker_written` during lab apply.
- Reaching this checkpoint proves the candidate B9 release tree passed the apply control flow up to verified marker write/fsync, but `current` still pointed to A.
- The checkpoint artifact was fsynced before the operator cut power.
- After power returned, the board continued adopting A from `/data/player-runtime/current`, passed deep-health before reconcile, passed reconcile as current-verified, and passed deep-health after reconcile.
- Public `player-runtime` apply/rollback/reconcile remained frozen (`rc=44`) in the lab reconcile sidecar and in the final board post-check.

## Expected partial state

This checkpoint intentionally proves that a verified marker alone is not promotion. Without `current -> B`, the launcher and reconcile must keep A selected.

## Non-claims

- This covers only the `after_marker_written` checkpoint.
- It does not prove cleanup of the verified-but-unlinked B9 release, later apply checkpoints, rollback checkpoints, long soak, production/stable rollout, server-side publish enforcement, or public thaw.
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
