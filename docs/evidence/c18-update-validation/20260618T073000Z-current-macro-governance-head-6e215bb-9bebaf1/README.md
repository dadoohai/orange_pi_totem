# C18 current macro governance refresh at 6e215bb - 9bebaf1

Purpose: re-run `scripts/qa/c18_ota_macro_governance_gate.py --json` after
refreshing the H2 readiness snapshot with server-side current asset-path
hardening.

Result:

- `passed=true`
- `result_claim=c18_homologation_governance_ready_pre_h2`
- H2 input points to
  `docs/evidence/c18-update-validation/20260618T072806Z-current-h2-readiness-head-3458cba-9bebaf1/h2-readiness.json`
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
