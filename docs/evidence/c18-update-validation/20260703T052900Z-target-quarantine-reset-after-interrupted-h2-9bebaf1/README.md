# C18 target quarantine reset after interrupted H2 - 9bebaf1

This is a lab-only quarantine reset after the interrupted/blocked H2 rollback
work on 2026-07-03.

Result:

- `quarantine-reset.json` passed.
- Exactly one quarantine entry for
  `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1` was removed.
- `current` and `previous` links were unchanged.
- Public `player-runtime` apply, rollback and reconcile stayed frozen with
  `rc=44`.
- The remaining unrelated historical `m6-b2` quarantine was preserved.

Non-claims:

- not production;
- not `stable`;
- not public thaw;
- not power-loss evidence;
- not 24h soak;
- not a rollback checkpoint.
