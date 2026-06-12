# C18 P0 power-loss: rollback_after_state_success

Controlled homologation/pilot evidence for the C18 player-runtime package.

- Checkpoint: `rollback_after_state_success`
- Candidate: `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`
- Expected active after resume: `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`
- Board image marker: `c18-hwdecode-lab-1x`
- Scope: P0 selective pilot readiness only
- Non-claims: not production, not stable, not public thaw, not auto-pull, not 24h soak, not full 17/17 matrix

Result summary:

- Physical power was cut at `CUT_POWER_NOW` for `rollback_after_state_success`.
- Resume passed with a changed boot id.
- The service adopted the expected active runtime before and after reconcile.
- Playback health passed before and after reconcile.
- The candidate runtime remained quarantined with reason `physical_powerloss_trial`.
- Final state has no previous runtime link/version.
- Public player-runtime apply, rollback, and reconcile stayed frozen with rc 44.

Primary files:

- `setup/lab-apply.json`
- `setup/service-adoption.json`
- `setup/apply/candidate-health/health/playback-deep-health-public.json`
- `trial/powerloss-checkpoint/checkpoint.json`
- `trial/powerloss-summary.json`
- `trial/resume/reconcile.json`
- `trial/resume/post-reconcile-state.json`
- `postcheck.txt`
- `evidence-manifest.json`
