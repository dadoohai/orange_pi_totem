# C18 production image prod6 build - 20260710T154410Z

Negative offline build evidence for the M5 exact-target `player-runtime`
auto-pull candidate. The builder passed, but independent inspection found a
production blocker that the original checks did not cover.

## Result

- round: `C18.IMAGE-PROD.6`
- image tag: `c18-hwdecode-prod-6`
- image version: `c18.image-prod.6`
- repo commit: `24bbe136adf70a10e7417316592e99949ae8eb64`
- image sha256:
  `1d0e9348cd67e3b425abe461a150f2e27c9d4bf1a33dfe0146aaf82dd7f3edae`
- image bytes: `1971322880`
- original offline validation: passed (insufficient / false-green)
- independent artifact decision: **BLOCKED / DO NOT FLASH**
- blocker: enabled `totem-open-settings.service` still called
  `totem_settings_lab_apply_policy.sh`, which can emit lab-only/non-production
  policy and can prevent the wizard from opening on a clean production seed

## Scope That Did Pass

- C22 exact-target authorization is embedded; latest/prerelease/downgrade are
  disabled;
- private firstboot, Wi-Fi/identity markers and historical lab claims are
  absent;
- no SSH host key is embedded; a production oneshot generates device-unique
  keys before SSH starts;
- machine-id is empty for first-boot generation;
- player seed has no API key, station/environment identity or token;
- no real config, player-runtime current/previous or verified marker is
  pre-seeded;
- totem-core and player-runtime production timers remain separate.

These checks do not override the settings-service blocker. `prod6` is retained
only as negative evidence; `prod7` must replace the service with the production
policy writer, remove the lab helper and enforce both conditions in the image
validator.

## Accepted Risk And Non-Claims

- shared root password SSH access remains enabled for first-scale support;
  per-device credentials remain M6;
- the image was not flashed or booted by this evidence;
- real timer auto-pull, no-op and both rollback swaps still require the board;
- this evidence does not authorize broad latest, future player-runtime targets,
  rollout groups or device attestation.
