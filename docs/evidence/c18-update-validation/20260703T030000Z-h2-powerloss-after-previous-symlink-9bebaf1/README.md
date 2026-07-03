# C18 H2 power-loss after_previous_symlink

This evidence records a physical power cut at `after_previous_symlink` for
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

## Result

- Topology was reset to `current=m6-a`, with no `previous`, before arming.
- The checkpoint was reached after `previous` was linked to the old current and
  before promoting the target to `current`.
- The operator cut physical power at `CUT_POWER_NOW`.
- Resume observed a new boot and kept `current=m6-a`.
- Adoption and deep-health passed before and after reconcile.
- Public player-runtime apply/rollback/reconcile stayed frozen with `rc=44`.
- `c18_player_runtime_powerloss_evidence_gate.py` passed for this directory.

## Non-claims

This covers only `after_previous_symlink`. It does not complete H2, does not
claim 17/17 power-loss coverage, does not claim soak, stable, production, or
public player-runtime thaw.
