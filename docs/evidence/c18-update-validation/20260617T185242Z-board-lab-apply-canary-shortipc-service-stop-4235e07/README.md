# C18 player-runtime board lab apply - mpv stuck fix

Lab-only apply of:

- version: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`
- source commit: `9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522`
- payload sha256: `d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0`
- kiosk.py sha256: `7bc2384b6d4b81a7222d84cc89ef7e53dac18248c410e51041d9ee49a448f413`
- tree sha256: `995b0483655c449ead1e679380a61e9f7c90778173f60f34af7a78b25114ba1b`

Result:

- `lab-apply.json`: `passed=true`, `rc=0`;
- `current_link=releases/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`;
- public player-runtime apply/reconcile stayed frozen with rc 44;
- `service-control.txt` records `kiosky-player.service` stopped before candidate health and restarted active after apply.

Context:

- Earlier attempts in this round intentionally remained fail-closed:
  - no-canary candidate run;
  - long AF_UNIX socket path plus active-service DRM contention;
  - external IPC directory access preflight.
- The retry path used governed lab quarantine resets and did not edit state manually.

Non-claims:

- not production;
- not stable;
- not public player-runtime thaw;
- not auto-pull;
- not server-side publish/signature/attestation;
- not 24h soak;
- not H2 17/17 power-loss completion;
- not pilot authorization by itself.
