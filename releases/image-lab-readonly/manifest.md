# Image Lab Read-only Manifest

Data: 2026-05-06

Status:

- `image_lab_readonly=true`
- `final_image=false`
- `image_built=true`
- `card_written=false`
- `boards_touched=false`
- `read_only_enabled_on_installed_board=false`
- `power_cut_tested=false`
- `long_test=false`
- `ready_for_c12_1_build=false`
- `ready_for_c12_2_card_write=true`
- `ready_for_c12_2_board_validation=true`
- `ready_for_c11_4=false`

## Purpose

This manifest defines the C12 image-lab target for validating root read-only as
part of the generated base image, not as a post-install patch on an already
provisioned board.

## Repository Baseline

- repository: `dadoohai/orange_pi_totem`
- branch: `foundation-v0.1`
- c12_0_prep_commit: `49778f6`
- c12_1_build_commit: `f07ff65`
- orange_pi_totem_build_head: `49778f61cb44d66d8ebccbad1b1a19d51d6c78ff`
- dev_board_status: `hardware_incident_pending_retest`
- dev_card_status: `lost_or_untrusted_after_smoke_heat_incident`
- previous_decision: `ADR-0011-root-read-only-overlay-mechanism`
- root_read_only_mechanism_decision:
  `c12_image_integrated_overlay_lab_required`

## Base Image Target

The image-lab should start from the same strategic base family used by the
foundation candidate:

- Armbian Build: `v25.11`
- Armbian Build commit used by foundation candidate: `e172058`
- board: `orangepizero3`
- release: `bookworm`
- branch: `current`
- kernel target: `6.12.58-current-sunxi64`
- U-Boot target: `2025.04`
- build: minimal, no desktop
- network stack: NetworkManager
- critical packages: kernel/DTB/U-Boot/BSP frozen

## C12.1 Build Artifacts

- image_file:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab_minimal.img`
- image_checksum_file:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab_minimal.img.sha256`
- image_sha256:
  `1b6f5573262d501ae2df6bc3338b56432c8994d4444308caf00347829df08fe2`
- build_log_file:
  `/home/builder/totem-os/armbian-build-v25.11/output/logs/log-build-29bced66-eed1-4f2c-8d0e-d2ad34f794b5.log`
- package_manifest_file:
  `releases/image-lab-readonly/package-manifest-c12-1.txt`
- read_only_integration_manifest_file:
  `releases/image-lab-readonly/read-only-integration-manifest-c12-1.txt`
- kiosky_player_pin: `c71318a64c08e47b8426f1388b95f21364d57123`
- overlayroot_included: `true`
- initramfs_generated_after_overlayroot: `true`

## C12.1.1 Artifact Preservation

- artifact_preserved_at_expected_path: `true`
- checksum_revalidated: `true`
- build_log_exists: `true`
- package_manifest_exists: `true`
- secret_scan_textual_artifacts: `pass`
- dev_card_incident_recorded: `true`
- ready_for_c12_2_card_write: `true`

The dev board/card incident is tracked as a physical media/hardware event until
proven otherwise. C12.2 must not use the damaged dev card and must not depend on
the dev board.

## Required Build-time Integration

The read-only lab image must integrate the read-only mechanism at build time:

- include package `overlayroot` in the image build;
- generate initramfs and `uInitrd` after `overlayroot` is present;
- configure the read-only mechanism in the generated image, not by patching an
  installed board;
- include journald volatile policy from C11.2;
- preserve `/data`, `/tmp` and `/run` as writable paths;
- keep NetworkManager profile policy explicit;
- keep `/boot` and `/etc` write operations limited to image build or controlled
  maintenance flows;
- keep secrets and real config out of the image.

## Expected Writable Paths

Persistent:

- `/data/config`
- `/data/state`
- `/data/media`
- `/data/logs`

Runtime:

- `/tmp`
- `/run`

Special policy:

- `/etc/NetworkManager/system-connections`
- `/boot`
- selected `/etc/systemd` files created by the image build

## Validation Gates

C12.1 can build the image-lab when:

- Armbian Build v25.11 tree is available;
- build host is prepared;
- image customization plan is checked in;
- no real config, API keys, Wi-Fi credentials or media cache are embedded.

C12.2 can write a test card only after C12.1 produces:

- image file;
- checksum;
- build log;
- generated package manifest;
- read-only integration manifest.

Board validation must prove:

- `read_only_enabled=true`;
- `overlay_active=true` or equivalent mechanism active;
- common root write is blocked;
- `/data`, `/tmp` and `/run` writable;
- player reaches `player_running`;
- F10 open/cancel works;
- rollback/offline recovery instructions exist.

Power-cut testing remains blocked until the read-only image passes normal boot,
reboot and smoke tests.

## Explicit Non-goals

- no final production image in C12.0-prep;
- no card writing in C12.0-prep;
- no board changes in C12.0-prep;
- no power cut;
- no apt broad upgrade;
- no desktop, Chromium, Xorg, Wayland or compositor;
- no secrets or real config embedded in the image.
