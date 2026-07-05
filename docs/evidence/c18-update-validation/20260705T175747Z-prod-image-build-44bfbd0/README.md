# C18 production image build - 20260705T175747Z

This evidence records the offline build of the first C18 production image
candidate.

## Result

- round: `C18.IMAGE-PROD.1`
- image tag: `c18-hwdecode-prod-1`
- image version: `c18.image-prod.1`
- repo commit: `44bfbd0df7d82306425a4296c498794ec87f266a`
- image file:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-prod-1_minimal.img`
- image sha256:
  `9b10788031b9bf4884cd49169799b56d995fa56f8cb185c846bb7b485e1dc89e`
- offline validation: passed

## Production Scope

- `artifact_private=false`
- `final_image=true`
- `production_image=true`
- `totem_core_embed_profile=production`
- production policy source: `totem_update_policy_production.json`
- `totem-core` update timer: enabled
- `player-runtime` kiosk snapshot:
  `7bc2384b6d4b81a7222d84cc89ef7e53dac18248c410e51041d9ee49a448f413`

## Non-Claims

- board was not touched during this build;
- image was not flashed or booted yet;
- real timer auto-pull was not exercised yet;
- no `totem-core` stable release was created by this evidence.
