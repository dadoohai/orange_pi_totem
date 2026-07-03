# C18 H2 power-loss after_release_tree_fsync

This evidence records a physical power cut at `after_release_tree_fsync` for
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

## Result

- Topology was reset to `current=m6-a`, with no `previous`, before arming.
- The baseline pre-cut 60s health passed.
- The checkpoint was reached after candidate health and release tree fsync.
- The operator cut physical power at `CUT_POWER_NOW`.
- Resume observed a new boot and kept `current=m6-a`.
- Adoption and deep-health passed before and after reconcile.
- Public player-runtime apply/rollback/reconcile stayed frozen with `rc=44`.
- `c18_player_runtime_powerloss_evidence_gate.py` passed for this directory.

## Non-claims

This covers only `after_release_tree_fsync`. It does not complete H2, does not
claim 17/17 power-loss coverage, does not claim soak, stable, production, or
public player-runtime thaw.
