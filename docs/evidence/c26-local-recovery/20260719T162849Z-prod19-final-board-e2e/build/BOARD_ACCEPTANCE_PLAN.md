# Prod19 C26 board acceptance

Target image SHA256:
`991ee90b8c042cbd1424c29f8c5062668c3125c999a24e32c01f14d9b4ec1ebc`.

The campaign starts only after the exact image is manually flashed.

## 1. Identity and clean boot

- confirm prod19 marker and build identity;
- confirm the external production support credential works and the old
  credential does not;
- confirm `current=C26.16`, `previous=C26.15`, exact state and healthy links;
- confirm no real config or forged player-runtime state came from the image;
- confirm firstboot, player, update policies and timers are healthy.

## 2. Onboarding and playback

- open the real F10 wizard and inspect the production UI;
- activate the lab totem, select an environment and save configuration;
- confirm config validation, credential/environment binding and return to
  playback;
- run real deep health with expected `v4l2request-copy`, advancing frames,
  no media-load failures and no player restart.

## 3. Local recovery actions

- open F10 and confirm `Reiniciar`, `Desligar` and `Restaurar` are visible only
  when their runtime guards are healthy;
- prove restart returns automatically with config and policy preserved;
- prove restore revokes the exact old activation, clears only declared local
  product state, returns to onboarding and blocks stale playback;
- reactivate and confirm the old token remains refused and the new activation
  works;
- prove poweroff stops the board and requires manual power restoration.

## 4. OTA and interruption safety

- run installed C26 self-tests and the adversarial transaction matrix;
- rollback C26.16 to C26.15 and return to C26.16 through the governed updater;
- confirm tampered/untrusted slot and active settings/reset locks fail closed;
- observe the core and exact-target player-runtime timers without broad latest,
  downgrade or prerelease behavior;
- confirm final player health and a clean, internally consistent update state.

## 5. Closeout

- store sanitized commands, before/after state and visual evidence;
- independently audit the board evidence;
- update the C26 plan and OTA source of truth;
- promote prod19 only if every required check above is proved.

No API key, token, password, SSID or customer payload may enter the evidence.
