# C18 player-runtime power-loss trial: rollback_after_quarantine

This evidence records an operator-attended physical power-loss trial for the C18 `player-runtime` lab rollback path.

## Scope proven

- Harness/source commit: `fe04918` (`C18: add player-runtime powerloss evidence gate`).
- Setup candidate: `c18.player-runtime-powerloss-b14-20260609T174704Z-fe04918`.
- Existing good release A: `c18.player-runtime-m6-a-20260609T0418Z-7107a55-r2`.
- Setup phase applied B14 over A, restarted `kiosky-player.service`, verified service adoption from `/data`, and collected green service deep-health.
- Checkpoint armed: `rollback_after_quarantine` during lab rollback with `--quarantine-current`.
- The checkpoint artifact was fsynced after rollback repointed `current -> A`, removed `previous`, and recorded B14 in quarantine, but before rollback wrote final success state.
- After power returned, the board adopted A from `/data/player-runtime/current`, with `previous` absent, passed deep-health before reconcile, passed reconcile as current-verified, and passed deep-health after reconcile.
- `trial/resume/post-reconcile-state.json` proves the B14 quarantine entry survived reboot and reconcile, with the same version and hashes captured at the checkpoint.
- Public `player-runtime` apply/rollback/reconcile remained frozen (`rc=44`) in the lab reconcile sidecar and in the final board post-check.

## Expected partial state

This checkpoint intentionally proves that rollback remains recoverable after the candidate has been quarantined. At cut time, `current` already points back to A, `previous` is absent, and state bookkeeping can still reflect the interrupted rollback. Reconcile must trust the verified `current` marker, keep A selected, and retain the B14 quarantine record.

## Non-claims

- This covers only the `rollback_after_quarantine` checkpoint.
- It does not prove `rollback_after_state_success`, remaining apply checkpoints, long soak, production/stable rollout, server-side publish enforcement, or public thaw.
- It does not make `player-runtime` publicly available; this remains lab-only evidence.

## Key files

- `setup/lab-apply.json`: lab apply of B14 over A and public freeze sidecars.
- `setup/service-adoption.json`: service adoption identity check for B14 before rollback.
- `setup/apply/candidate-health/`: candidate B14 health artifacts before promotion.
- `setup/service-health/`: service health after B14 adoption.
- `trial/powerloss-checkpoint/checkpoint.json`: persisted rollback checkpoint and runtime snapshot at cut.
- `trial/powerloss-summary.json`: resume verdict.
- `trial/resume/post-reconcile-state.json`: filtered state sidecar proving the B14 quarantine entry after reconcile.
- `trial/resume/*-health/playback-deep-health-public.json`: deep-health summaries before and after reconcile.
- `trial/resume/*-adoption.json`: launcher adoption identity checks for A.
- `trial/resume/reconcile.json`: lab reconcile result and freeze sidecars.
- `postcheck.txt`: final live board state after resume.
- `evidence-manifest.json`: SHA-256 manifest for committed evidence files.
