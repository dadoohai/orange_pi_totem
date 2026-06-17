# C18 pilot preflight - mpv-stuck-fix-9bebaf1

This directory records the assisted-pilot authorization and read-only board
preflight for the corrected homologation `player-runtime` package:

- version: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`;
- component: `player-runtime`;
- channel: `homologation`;
- ring: `pilot`;
- source commit: `9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522`.

Result:

- `board-preflight.json`: `passed=true`;
- `pilot-authorization.json`: formal pilot authorization for operator-assisted
  delivery with rollback owner and sanitized allowlisted device hash.

The preflight proves the board is in the expected homologation posture:

- policy channel `homologation`;
- `allow_prerelease=true`;
- allowed public OTA component remains `totem-core`;
- update timer disabled and inactive;
- public `player-runtime` apply/rollback/reconcile still frozen with `rc=44`;
- image marker is `c18-hwdecode-lab-1x`;
- service active with C18 MPV/hwdec path observed.

Non-claims: this evidence does not authorize production, promote `stable`,
enable auto-pull, publish releases, thaw public `player-runtime`, satisfy 24h
soak, or satisfy the 17/17 power-loss matrix.
