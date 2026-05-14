# 171 - C17.7 - Totem-Core Embedded Image Build

Status: passed offline image build

C17.7 creates a new private homologation image that embeds the validated C17.6
`totem-core` update into the image itself. The goal is to stop depending on a
post-image bootstrap for wizard/configurator/splash evolution.

No board was touched in this round. No card was written. This is an offline
image build and rootfs validation only.

## Image

Image:

`/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c17-7-totem-core-embedded_minimal.img`

SHA256:

`69dfaa0c3454fa67a18d4e49c74f97343d4623b67826ed0cebb8eeb2e8081780`

The image was derived from the clean-card validated C17.4.2 image. Kernel,
U-Boot, DTB and BSP were reused. Armbian Build, apt, pip and kernel tooling were
not invoked.

## Embedded Totem-Core

The image now includes:

- `/data/core/totem/releases/c17.6-environment-input-20260514T211247Z`;
- `/data/core/totem/current` pointing at that release;
- `/data/core/totem/state.json` with sanitized image-embedded state;
- `/opt/totem/core-fallback/bin` with factory fallback scripts;
- wrappers in `/opt/totem/bin` for totem-core scripts;
- `totem-updatectl` multi-component support preserved;
- the C17.6 editable environment field, UUID validation and API/content
  preflight.

`dadooh-visual-splash.service` now calls
`/opt/totem/bin/totem_visual_splash.py`, so splash rendering also goes through
the totem-core wrapper path and can fall back to `/opt`.

## Offline Validation

The rootfs validation passed:

- C17.7 marker present;
- totem-core `current` symlink present;
- C17.6 wizard installed in `/data/core/totem/current`;
- fallback wizard installed under `/opt/totem/core-fallback/bin`;
- wrapper installed at `/opt/totem/bin/totem_setup_visual_wizard.py`;
- environment UUID/API/content validation code present;
- settings restore order fix still present;
- pull update timer still enabled;
- firstboot gate still enabled;
- private seed present with 0600 permissions;
- `/data/config/config.json` not embedded;
- QA/evidence artifacts not installed in the appliance rootfs.

## Decision

`c17_7_status=passed_offline_image_build`

`ready_for_c17_7_clean_card_validation=true`

`ready_for_batch_flash=false`

`ready_for_dispatch=false`

`ready_for_c18_player_audit=false`

Batch, dispatch and C18 remain gated until this C17.7 image is written to a
clean card and the first-boot/F10/wizard/writer/player restore path is validated
again.
