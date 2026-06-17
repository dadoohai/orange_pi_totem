# C18 H2 power-loss topology reset - mpv stuck fix 9bebaf1

Result: `passed=true`, `result_claim=player_runtime_lab_topology_reset_prepared`.

This board-side lab-only reset prepared `/data/player-runtime` for a fresh H2/P0
power-loss apply session against
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

What changed on the board:

- before: `current -> releases/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`;
- after: `current -> releases/c18.player-runtime-m6-a-20260610T0501Z-29ff33b`;
- `previous` absent;
- target release dir removed after marker/identity prevalidation;
- public player-runtime apply/rollback/reconcile still returned frozen `rc=44`;
- service restarted and adoption probe passed on `m6-a`.

Non-claims:

- not power-loss evidence;
- not 17/17;
- not pilot authorization;
- not stable or production;
- not public thaw;
- no fetch/publish.

