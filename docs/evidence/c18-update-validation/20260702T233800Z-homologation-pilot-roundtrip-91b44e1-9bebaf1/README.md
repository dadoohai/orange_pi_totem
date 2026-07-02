# C18 Homologation Pilot Roundtrip - 2026-07-02

Curated public evidence for the assisted homologation pilot roundtrip of
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

What was exercised on the lab board:

- guarded lab apply of the `9bebaf1` player-runtime target;
- candidate health during apply;
- service adoption of the target after restart;
- service playback health on the target;
- guarded rollback to `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`;
- service adoption and playback health after rollback;
- governed topology reset to restore the board to the initial shape:
  `current=m6-a`, no `previous`, target release directory absent;
- public player-runtime rollback still frozen with `rc=44`.

This is homologation evidence only. It does not authorize production, stable,
auto-pull, public thaw, power-loss 17/17, 24h soak, or H2 readiness.
