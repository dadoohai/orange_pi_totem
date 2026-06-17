# C18 H2 Power-Loss Board Preflight Fresh

Fresh read-only board preflight collected after the board had been rebooted and
multiple days had elapsed, before any new H2 physical power-loss checkpoint
execution.

Result:

- `board-preflight.json`: collector `passed=true`;
- `board-preflight-gate.json`: `passed=true`;
- `result_claim=h2_powerloss_board_preflight_accepted`;
- collected from board at `2026-06-17T07:15:17Z`;
- target package:
  `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`;
- matrix plan:
  `docs/evidence/c18-update-validation/20260617T020912Z-h2-powerloss-matrix-plan-custom-setup-c16fb3e/powerloss-matrix-plan.json`.

Confirmed conditions:

- package channel is `homologation`;
- payload sha256 matches the manifest and the matrix target;
- policy is `homologation`, `allow_prerelease=true`, `allow_downgrade=false`;
- `allowed_components=["totem-core"]`;
- update timer is disabled and inactive;
- player service is active;
- image marker is `c18-hwdecode-lab-1x`;
- evidence root for pending checkpoints is not present and has a writable parent;
- target release is not linked as `current` or `previous`;
- target release is not quarantined.

Custom setup checkpoints remain explicit:

- `after_previous_symlink`;
- `rollback_after_current_unlinked`.

Non-claims:

- this is not physical power-loss evidence;
- this does not claim 17/17;
- this does not arm or resume any trial;
- this does not replace a physical power cut;
- this does not apply or rollback `player-runtime`;
- this does not authorize `stable` or production;
- this does not thaw `player-runtime`;
- this does not satisfy 24h soak;
- this does not complete H2 readiness.
