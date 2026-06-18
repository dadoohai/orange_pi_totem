# C18 target-current final service-stopped validation - 9bebaf1

Sanitized board evidence for the final service-stopped lab apply of
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

Result:

- `lab-apply.json`: `passed=true`, `rc=0`;
- before apply: current was
  `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`;
- after apply: current was
  `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`;
- after apply: previous was
  `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`;
- candidate health passed with target kiosk/tree identity
  `7bc2384b6d4b81a7222d84cc89ef7e53dac18248c410e51041d9ee49a448f413` /
  `995b0483655c449ead1e679380a61e9f7c90778173f60f34af7a78b25114ba1b`;
- service playback after restart passed with one MPV, hwdecode present, VO
  configured, playback progressed, no MPV restart and no media load failures;
- public player-runtime apply/reconcile stayed frozen with `rc=44`;
- no GitHub or network fetch was used by the lab apply.

This is user-level board evidence that the target can be applied under the
assisted lab path and run real playback after service restart.

Non-claims:

- not production;
- not `stable`;
- not auto-pull;
- not public player-runtime thaw;
- not server-side publish;
- not power-loss 17/17;
- not 24h soak.
