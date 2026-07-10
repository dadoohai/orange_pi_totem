# C18 production image prod7 build - 20260710T162615Z

Offline build evidence for the M5 exact-target `player-runtime` auto-pull
candidate that replaces the blocked prod5 and prod6 artifacts.

## Result

- round: `C18.IMAGE-PROD.7`
- image tag: `c18-hwdecode-prod-7`
- image version: `c18.image-prod.7`
- repo commit: `17b58c0a2943a27c62f7ebfd2c47284d88fd34c8`
- image SHA256: `c82c69341b4e1306899ae149d25a0c8953b42ee081291928adee8614d5b5b0b7`
- image bytes: `1971322880`
- offline validation: passed

## Closed Blockers

- no private firstboot, lab Wi-Fi identity or embedded SSH host key;
- device-unique SSH host keys are generated before SSH starts;
- production wizard service uses real QR mode and the production write policy;
- lab/homologation policy helper is absent from the image;
- clean devices wait for authorized QR credentials before a real write;
- configured devices preserve and use the active private configuration;
- embedded `totem-core` is bound to the committed C21.8 package, source commit
  and payload hash rather than mislabeled as C17.6;
- C22 player-runtime authorization is exact-target; broad `latest`, prerelease
  and downgrade remain disabled.

## Remaining Board Proof

The image has not yet been flashed. Real first boot, QR/save, player playback,
timer auto-apply, no-op, authorized rollback and restore remain board-only M5
checks. Shared root-password SSH remains the explicitly accepted first-scale
risk; per-device credentials remain M6.
