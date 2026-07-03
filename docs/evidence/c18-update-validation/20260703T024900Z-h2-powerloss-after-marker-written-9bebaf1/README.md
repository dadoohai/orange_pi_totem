# C18 H2 power-loss after_marker_written

This evidence records a physical power cut at `after_marker_written` for
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

## Result

- The checkpoint was reached after candidate health, release tree fsync, and
  verified marker write.
- The operator cut physical power at `CUT_POWER_NOW`.
- Resume observed a new boot and kept `current=m6-a`.
- Adoption and deep-health passed before and after reconcile.
- Public player-runtime apply/rollback/reconcile stayed frozen with `rc=44`.
- `c18_player_runtime_powerloss_evidence_gate.py` passed for this directory.

## Non-claims

This covers only `after_marker_written`. It does not complete H2, does not
claim 17/17 power-loss coverage, does not claim soak, stable, production, or
public player-runtime thaw.
