# C18 player-runtime power-loss trial: rollback_after_state_success

This evidence records an operator-attended physical power-loss trial for the C18 `player-runtime` lab rollback path.

## Scope proven

- Harness/source commit: `57a552e` (`C18: harden state-success powerloss evidence`).
- Setup candidate: `c18.player-runtime-lab-20260609T191239Z-57a552e`.
- Existing good release A: `c18.player-runtime-m6-a-20260609T0418Z-7107a55-r2`.
- Setup phase applied B18 over A, restarted `kiosky-player.service`, verified service adoption from `/data`, and collected green service deep-health.
- Checkpoint armed: `rollback_after_state_success` during lab rollback with `--quarantine-current`.
- The checkpoint artifact was fsynced after rollback repointed `current -> A`, removed `previous`, recorded B18 in quarantine, and wrote final rollback `success` state.
- The operator cut physical power after `CUT_POWER_NOW`; `boot_state_at_checkpoint.boot_id` differs from `boot_state_at_resume.boot_id`.
- After power returned, the board adopted A from `/data/player-runtime/current`, with `previous` absent, passed deep-health before reconcile, passed reconcile as current-verified, and passed deep-health after reconcile.
- `trial/resume/post-reconcile-state.json` proves the B18 quarantine entry survived reboot and reconcile, with the same version and hashes captured at the checkpoint.
- `trial/resume/boot-journal-monotonic.txt` shows the boot-time maintenance reconcile/cleanup of B18 happened at monotonic `+14s` in the resume boot, before chrony stepped the clock by about 376s. The apparent `19:17:09Z` wall-clock on that reconcile is therefore pre-NTP boot time, not a pre-cut mutation.
- Public `player-runtime` apply/rollback/reconcile remained frozen (`rc=44`) in the lab reconcile sidecar and in the final board post-check.

## Expected final rollback state

This checkpoint proves the most complete rollback interruption point currently covered: rollback had already completed its persistent bookkeeping before the power cut. At cut time, `current` pointed back to A, `previous` was absent, `state.current` was A, `state.previous` was absent, `last_operation` was rollback `success`, and B18 was quarantined.

## Non-claims

- This covers only the `rollback_after_state_success` checkpoint.
- It does not prove every apply checkpoint, long soak, production/stable rollout, server-side publish enforcement, or public thaw.
- It does not make `player-runtime` publicly available; this remains lab-only evidence.

## Key files

- `setup/lab-apply.json`: lab apply of B18 over A and public freeze sidecars.
- `setup/service-adoption.json`: service adoption identity check for B18 before rollback.
- `setup/apply/candidate-health/`: candidate B18 health artifacts before promotion.
- `setup/service-health/`: service health after B18 adoption.
- `trial/powerloss-checkpoint/checkpoint.json`: persisted rollback checkpoint, boot-state-at-cut, runtime snapshot and B18 quarantine record.
- `trial/powerloss-summary.json`: resume verdict, boot-state-at-resume, adoption and reconcile summaries.
- `trial/resume/post-reconcile-state.json`: filtered state sidecar proving the B18 quarantine entry after reconcile.
- `trial/resume/boot-journal-monotonic.txt`: monotonic boot journal excerpt proving the B18 cleanup ran after the physical reboot.
- `trial/resume/*-health/playback-deep-health-public.json`: deep-health summaries before and after reconcile.
- `trial/resume/*-adoption.json`: launcher adoption identity checks for A.
- `trial/resume/reconcile.json`: lab reconcile result and freeze sidecars.
- `postcheck.txt`: final live board state after resume.
- `evidence-manifest.json`: SHA-256 manifest for committed evidence files.
