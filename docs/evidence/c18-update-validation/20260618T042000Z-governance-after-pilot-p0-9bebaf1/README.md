# C18 governance after pilot P0 - superseded aggregate

Purpose: record the macro governance state after the five assisted pilot P0
power-loss checkpoints were validated and the final pilot readiness gate passed.

Superseded status:

- this aggregate is retained as historical evidence only;
- its `macro-governance-after-p0.json` and
  `pre-soak-scale-governance-after-p0.json` were generated before the final
  default reanchor and still reference older current macro/H2 snapshots;
- use
  `docs/evidence/c18-update-validation/20260618T043100Z-current-macro-governance-after-pilot-p0-9bebaf1/`
  as the current macro snapshot;
- use
  `docs/evidence/c18-update-validation/20260618T043200Z-pre-soak-scale-governance-after-pilot-p0-9bebaf1/`
  as the current pre-soak snapshot;
- use
  `docs/evidence/c18-update-validation/20260618T043000Z-current-h2-readiness-after-pilot-p0-9bebaf1/`
  as the current H2 readiness snapshot.

Results:

- `macro-governance-after-p0.json`: passed with
  `c18_homologation_governance_ready_pre_h2`, but is superseded by the current
  macro snapshot above.
- `pre-soak-scale-governance-after-p0.json`: passed with
  `c18_ota_pre_soak_scale_governance_ready`, but is superseded by the current
  pre-soak snapshot above.
- `h2-readiness-after-pilot-p0.json`: intentionally blocked with
  `h2_readiness_blocked`, but is superseded by the current H2 snapshot above.

Current H2 blockers:

- full physical power-loss matrix is still incomplete;
- 24h soak evidence is missing;
- stable promotion evidence is missing;
- explicit operator thaw decision is missing.

Non-claims:

- this does not authorize production;
- this does not promote stable;
- this does not enable auto-pull;
- this does not thaw public player-runtime;
- this does not replace the future 24h soak or full 17/17 H2 power-loss matrix.
