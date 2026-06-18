# C18 H2 power-loss remaining-12 run card - 9bebaf1

Purpose: preserve the current execution card for the remaining physical H2
power-loss checkpoints after the assisted pilot P0 passed 5/17 and the board
preflight was refreshed.

Current state:

- target:
  `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`;
- pilot P0 evidence: 5/17 physical checkpoints accepted;
- fresh H2 board preflight:
  `docs/evidence/c18-update-validation/20260618T070400Z-h2-powerloss-board-preflight-fresh-after-reset-9bebaf1/`;
- H2 readiness remains blocked until the remaining 12 physical checkpoints,
  24h soak, stable promotion evidence and formal thaw decision are all present.

Execution guidance:

- use the full operator runbook in
  `docs/evidence/c18-update-validation/20260617T193720Z-h2-powerloss-operator-runbook-mpv-stuck-fix-9bebaf1/`;
- run one checkpoint at a time;
- use physical power cut only after the harness prints `CUT_POWER_NOW`;
- after power restore, resume, pull evidence, build manifest and run the
  evidence gate before starting the next checkpoint;
- keep `rollback_after_current_unlinked` last because it is the most
  destructive rollback topology.

Non-claims: this run card is not power-loss evidence, does not satisfy 17/17,
does not authorize production or `stable`, does not thaw `player-runtime`, does
not replace 24h soak and does not replace H2 readiness.
