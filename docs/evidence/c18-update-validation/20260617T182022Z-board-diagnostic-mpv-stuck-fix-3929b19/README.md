# C18 Board Diagnostic - MPV Stuck Fix

This directory preserves a board-only diagnostic validation of the local
`kiosk.py` fix after the `c16fb3e` target was blocked by MPV-stuck evidence.

Diagnostic action:

- active runtime before patch:
  `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`;
- active `kiosk.py` before patch:
  `f88515378cf647ce067789f223f68ccdfd8f5705a6f3ff8aa25bb4674e949310`;
- diagnostic `kiosk.py` after patch:
  `7bc2384b6d4b81a7222d84cc89ef7e53dac18248c410e51041d9ee49a448f413`;
- service restarted once after replacing `kiosk.py`;
- deep-health duration: 240 seconds;
- deep-health result: `passed=true`;
- MPV aliases observed: `9`;
- status aliases observed: `9`;
- status advanced without MPV transition: `false`;
- MPV media transitions observed: `true`;
- comparable samples: `223`.

Interpretation:

- this is positive diagnostic evidence for the local fix direction;
- this does not create or validate a new player-runtime package;
- this does not accept any H2 power-loss checkpoint;
- this does not claim pilot readiness, 17/17 power-loss, 24h soak, stable,
  production, public thaw, publish or auto-pull;
- a new governed target package must still be built and validated from a clean
  source/evidence chain.
