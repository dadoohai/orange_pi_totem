# C18 current macro governance snapshot: ab6ad5f

This snapshot records the current C18 macro-governance aggregate gate after the
H2 readiness snapshot was refreshed to require the current server-side
validation snapshot.

Result: `passed=true`,
`result_claim=c18_homologation_governance_ready_pre_h2`.

Accepted inputs:

- H1 traceability remains decisive and image-bound to `c18-hwdecode-lab-1x`;
- current pilot readiness remains `homologation_pilot_ready` for
  `channel=homologation`, `ring=pilot` and package `c16fb3e`;
- current H2 readiness is red only for the expected production blockers and is
  now bound to the current server-side validation snapshot;
- read-only board diagnostics evidence is accepted;
- current server-side publish governance evidence is accepted and hash-bound;
- repo clean and tracked-input guards passed when this JSON was generated.

Expected H2 blockers preserved:

- `full_physical_powerloss_matrix:powerloss_matrix_incomplete`;
- `soak_endurance_24h:missing_24h_soak_summary`;
- `stable_promotion_authorization:missing_stable_promotion_evidence`;
- `explicit_operator_thaw_decision:missing_operator_thaw_decision`.

Non-claims: this snapshot does not reopen expired pilot windows, authorize
production, promote `stable`, enable auto-pull, publish releases, thaw public
`player-runtime`, satisfy 24h soak, satisfy power-loss 17/17 or replace H2
readiness.
