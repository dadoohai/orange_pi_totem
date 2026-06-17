# C18 player-runtime service adoption and health - mpv stuck fix

Post-apply board validation for:

- version: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`
- current link: `releases/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`
- kiosk.py sha256: `7bc2384b6d4b81a7222d84cc89ef7e53dac18248c410e51041d9ee49a448f413`
- tree sha256: `995b0483655c449ead1e679380a61e9f7c90778173f60f34af7a78b25114ba1b`

Result:

- `service-adoption.json`: `passed=true`, selected source `data`, marker valid, running kiosk hash matches marker;
- `service-health.json`: `passed=true`;
- samples: 114;
- MPV/status aliases observed: 9 / 9;
- `status_advanced_without_mpv=false`;
- hwdec expected samples: 113;
- panfrost fault delta: 0;
- media load failures: 0;
- service/process MPV count: single.

This proves the service adopted the newly promoted data runtime and completed a short real-playback health run after the governed board lab apply.

Non-claims:

- not production;
- not stable;
- not public player-runtime thaw;
- not auto-pull;
- not server-side publish/signature/attestation;
- not 24h soak;
- not H2 17/17 power-loss completion;
- not pilot authorization by itself.
