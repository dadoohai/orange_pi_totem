# C18 H2 Power-Loss Board Harness Hash Audit

Read-only hash audit of the board-side scripts that the H2 physical
power-loss runbook uses to arm/resume checkpoints or prepare custom setup.

Result:

- `board-harness-hashes.json`: `passed=true`;
- `result_claim=h2_powerloss_board_harness_hashes_aligned`;
- host and credentials are not persisted;
- H2 evidence root `/data/c18-evidence/h2-c16fb3e` was absent, so no pending
  H2 checkpoint directories were present during this observation.

The audit intentionally excludes the board copy of
`scripts/qa/c18_player_runtime_powerloss_evidence_gate.py`: pulled checkpoint
directories are validated off-board by the current local evidence gate, not by
the board bundle copy.

Non-claims:

- this is not power-loss evidence;
- this does not claim 17/17;
- this does not arm or resume trials;
- this does not replace a physical power cut;
- this does not authorize `stable` or production;
- this does not thaw `player-runtime`;
- this does not satisfy 24h soak.
