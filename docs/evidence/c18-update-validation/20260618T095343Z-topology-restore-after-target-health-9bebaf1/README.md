# C18 topology restore after target-current validation - 9bebaf1

Governed lab-only topology restore after the successful target-current
validation of
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

Result:

- `topology-reset.json`: `passed=true`;
- before reset: current was the target and previous was M6;
- after reset: current was restored to
  `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`;
- after reset: previous was empty;
- target release dir was removed from the board runtime topology;
- public player-runtime apply, rollback and reconcile remained frozen with
  `rc=44`.

This prepared the board for the next H2 physical power-loss session. It does
not count as power-loss evidence and does not authorize production, `stable`,
auto-pull or public thaw.
