# C18 player-runtime power-loss trial: rollback_after_current_to_previous

This evidence records an operator-attended physical power-loss trial for the C18 `player-runtime` lab rollback path.

## Scope proven

- Harness/source commit: `b8691b7` (`C18: add player-runtime powerloss checkpoint evidence`).
- Setup candidate: `c18.player-runtime-powerloss-b8-20260609T155522Z-b8691b7`.
- Restore target: `c18.player-runtime-m6-a-20260609T0418Z-7107a55-r2`.
- Setup started from a clean boot with `GPU_FAULT_PRE=0`, applied B8 under the lab-only path, then validated B8 as `/data` current with deep-health passing.
- Checkpoint armed: `rollback_after_current_to_previous` during lab rollback.
- The checkpoint artifact was fsynced after rollback repointed `current` to A and before rollback finalized the remaining state.
- After power returned, the board adopted A from `/data/player-runtime/current`, passed deep-health before reconcile, passed reconcile as current-verified, and passed deep-health after reconcile.
- Public `player-runtime` apply/rollback/reconcile remained frozen (`rc=44`) in the lab reconcile sidecar and in the final board post-check.

## Expected partial state

At this checkpoint, `current` has already moved back to A while rollback bookkeeping is not complete. The observed `previous -> A` duplication is expected for this checkpoint and is not a claim that rollback completed every later cleanup step.

## Non-claims

- This covers only the `rollback_after_current_to_previous` checkpoint.
- It does not prove rollback checkpoints after previous removal/quarantine/state-success, apply checkpoints before `current`, long soak, production/stable rollout, server-side publish enforcement, or public thaw.
- It does not make `player-runtime` publicly available; this remains lab-only evidence.

## Key files

- `setup/lab-apply.json`: B8 lab apply verdict.
- `setup/service-adoption.json`: service adoption identity for B8 before rollback.
- `setup/service-health/playback-deep-health-public.json`: B8 service deep-health before rollback.
- `trial/powerloss-checkpoint/checkpoint.json`: persisted checkpoint and runtime snapshot at cut.
- `trial/powerloss-summary.json`: resume verdict.
- `trial/resume/*-health/playback-deep-health-public.json`: deep-health summaries before and after reconcile.
- `trial/resume/*-adoption.json`: launcher adoption identity checks for A.
- `trial/resume/reconcile.json`: lab reconcile result and freeze sidecars.
- `postcheck.txt`: final live board state after resume.
- `evidence-manifest.json`: SHA-256 manifest for committed evidence files.
