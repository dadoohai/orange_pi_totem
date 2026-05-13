# 143 - C15.2.1 - Image UI/UX fixes clean-board validation

## Status

```text
c15_2_1_status=blocked
image_built=true
offline_validation_passed=true
clean_board_validation=blocked
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c16_player_audit=false
```

C15.2.1 generated a private homologation image that consolidated the C15 wizard
and UX fixes over the C14.2.1 shipping homologation base:

```text
image_version=c15.2.1
artifact_private=true
final_image=false
homologation_shipping_image=true
not_for_production=true
not_for_distribution=true
c12_readonly_blocked=true
c12_4_blocked=true
```

Image artifact:

```text
Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c15-2-1-homolog-ui-ux-fixes_minimal.img
sha256=ed6b74a37dd4213143ff456959a3a9ddb47d9a66046768131872932930dbf053
```

## Build Method

The normal C14.2.1 wrapper still expects Docker. Docker was unavailable in this
host, so C15.2.1 used a narrower derivation path:

```text
scripts/build/derive_c15_2_1_homolog_image.py
```

The script copies the already validated C14.2.1 private homologation image and
uses `debugfs` to replace only the appliance-layer files listed in
`totem_appliance_manifest.json`. It does not alter kernel, U-Boot, DTB, BSP,
partitioning, packages, apt, pip, Wi-Fi, NetworkManager, or player code.

Offline validation confirmed:

- C15.1.3 visual TTY guard and F10 path embedded;
- C15.1.4 Wi-Fi pagination, refresh, signal display, and password toggle
  embedded;
- C15.1.5 wizard text/debounce/splash fixes embedded;
- C15.1.6 QA evidence/gallery not installed into the appliance rootfs;
- C14.2.1 pull updater and update timer preserved;
- private homologation seed present with expected permissions, without printing
  content;
- `/data/config/config.json` not embedded;
- `/tmp` remains `1777`.

## Clean-Board Result

The image was manually flashed to one clean board and booted. The operator
started the first wizard flow. Wi-Fi connected, but while entering the
environment value the wizard exited and the screen returned to `config_missing`.

This blocks C15.2.1 clean-board validation:

```text
single_board_validated=false
first_f10_clean_board_passed=false
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c16_player_audit=false
```

The failure is not classified as a regression. C15.2.2 classifies it as a latent
clean-board setup bug caused by wall-clock timeout handling during Wi-Fi/NTP
time correction.

## Decision

C15.2.1 remains a built and offline-valid image, but it is not ready for batch
flash or dispatch. C16/player remains blocked until a clean-board validation
passes without a forced recovery path.

## Follow-Up

C15.2.2 fixes the wizard timeout and password toggle issues, but remains blocked
because a later post-wizard black-screen/SSH-loss window required a physical
power cycle.
