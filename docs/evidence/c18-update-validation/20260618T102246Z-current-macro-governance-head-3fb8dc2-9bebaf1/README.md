# C18 current macro governance refresh at 3fb8dc2 - 9bebaf1

Purpose: re-run `scripts/qa/c18_ota_macro_governance_gate.py --json` from a
clean tree after reanchoring the macro gate to the current H2 readiness
snapshot.

Result:

- `passed=true`
- `result_claim=c18_homologation_governance_ready_pre_h2`
- H2 input points to
  `docs/evidence/c18-update-validation/20260618T101740Z-current-h2-readiness-head-0401375-9bebaf1/h2-readiness.json`
- server-side input points to
  `docs/evidence/c18-update-validation/20260617T191658Z-server-side-current-mpv-stuck-fix-9bebaf1/`

Scope:

- authorizes only the governed pre-H2/homologation posture;
- does not authorize production;
- does not promote `stable`;
- does not enable auto-pull;
- does not thaw `player-runtime` publicly;
- does not replace the full 17/17 physical power-loss matrix;
- does not replace the 24h soak/endurance run;
- does not replace stable-promotion evidence or a formal thaw decision.
