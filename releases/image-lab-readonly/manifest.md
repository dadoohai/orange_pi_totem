# Image Lab Read-only Manifest

Data: 2026-05-06

Status:

- `image_lab_readonly=true`
- `final_image=false`
- `image_built=true`
- `image_version=c12.1.2`
- `previous_image_superseded=true`
- `card_written=true`
- `card_write_tool=Armbian Imager Windows`
- `card_write_verified=false`
- `ready_for_c12_3_board_boot=false`
- `boards_touched=true`
- `read_only_enabled_on_installed_board=false`
- `power_cut_tested=false`
- `long_test=false`
- `ready_for_c12_1_build=false`
- `ready_for_c12_2_card_write=false`
- `ready_for_c12_2_board_validation=false`
- `c12_3_boot_attempted=true`
- `c12_3_status=blocked`
- `blocker=open_settings_session_stale_and_firstboot_interference`
- `read_only_validated=false`
- `c12_3_1_session_reliability_patch=applied_pending_rebuild`
- `c12_3_1_firstboot_policy=gate_or_private_lab_autoconfig`
- `c12_3_1_read_only_assertion=required`
- `ready_for_c12_1_2_rebuild=false`
- `c12_1_2_build_status=passed`
- `ready_for_c12_2_1_card_write=false`
- `ready_for_c12_3_2_revalidation=false`
- `c12_3_2_status=blocked`
- `c12_3_2_blocker=firstboot_bootstrap_missing_or_invalid`
- `c12_3_2_ssh_available=false`
- `c12_3_2_dadooh_ui_available=false`
- `ready_for_next_card_write=false`
- `c12_1_3_strategy=lab_autoconfig_required`
- `ready_for_c12_1_4_rebuild=true`
- `c12_1_4_status=blocked`
- `c12_1_4_blocker=build_env_docker_missing`
- `c12_1_4_firstboot_conf_private_validated=true`
- `c12_1_4_image_built=false`
- `ready_for_c12_2_2_card_write=false`
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
- c12_1_2_build_commit: `aec03bc`
- c12_1_2_source_head: `aec03bc`
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
- c12_2_card_write_checklist_commit: `2a302cf`
- card_write_tool: `Armbian Imager Windows`
- card_write_verified: `false`
- ready_for_c12_3_board_boot: `false`
- c12_3_boot_started: `true`
- c12_3_boot_attempted: `true`
- c12_3_status: `blocked`
- c12_3_boot_state: `config_missing`
- c12_3_first_login_technical_required: `true`
- c12_3_freeze_classification: `open_settings_session_stale`
- c12_3_secondary_classification: `firstboot_interference`
- c12_3_ready_for_read_only_validation: `false`
- c12_3_blocker: `open_settings_session_stale_and_firstboot_interference`
- c12_3_1_session_cleanup: `applied_pending_rebuild`
- c12_3_1_firstboot_gate: `applied_pending_rebuild`
- c12_3_1_private_firstboot_autoconfig_template: `available`
- c12_3_1_read_only_assertion: `required`
- ready_for_c12_1_2_rebuild: `false`
- ready_for_c12_2_1_reflash: `true`
- ready_for_c12_3_2_revalidation: `false`

The dev board/card incident is tracked as a physical media/hardware event until
proven otherwise. C12.2 must not use the damaged dev card and must not depend on
the dev board.

## C12.1.2 Rebuild Artifacts

The C12.1 image is superseded for future flashing. C12.1.2 incorporates the
C12.3.1 fixes and is the only image-lab artifact allowed for C12.2.1.

- image_version: `c12.1.2`
- image_file:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-2_minimal.img`
- image_checksum_file:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-2_minimal.img.sha256`
- image_sha256:
  `a398399c139c3fee1b05860b216db7facfddd0ae1a57f681b229228390b7abd9`
- build_log_file:
  `/home/builder/totem-os/armbian-build-v25.11/output/logs/log-build-eef4830c-29a1-4a82-bd74-81ff23b65894.log`
- package_manifest_file:
  `releases/image-lab-readonly/package-manifest-c12-1-2.txt`
- read_only_integration_manifest_file:
  `releases/image-lab-readonly/read-only-integration-manifest-c12-1-2.txt`
- overlayroot_included: `true`
- initramfs_generated_after_overlayroot: `true`
- initramfs_source: `cache_hit_with_overlayroot_hooks`
- firstboot_gate_included: `true`
- open_settings_cleanup_included: `true`
- read_only_assertion_required: `true`
- card_written: `true`
- boards_touched: `true`
- ready_for_c12_2_1_card_write: `false`
- c12_3_2_status: `blocked`
- c12_3_2_blocker: `firstboot_bootstrap_missing_or_invalid`
- c12_3_2_ssh_available: `false`
- c12_3_2_dadooh_ui_available: `false`
- ready_for_next_card_write: `false`

## C12.3.2 Black Screen Firstboot Blocker

C12.1.2 foi gravada e bootada, mas ficou bloqueada antes de qualquer validacao
read-only:

- tela preta;
- F10 apareceu como sequencia de escape no console cru;
- wizard nao abriu;
- sem Wi-Fi configurado;
- sem SSH acessivel;
- sem diagnostico remoto ou mount WSL do cartao.

Classificacao:

```text
firstboot_bootstrap_missing_or_invalid
```

Decisao C12.1.3: a proxima imagem bootavel em laboratorio deve ser reconstruida
como C12.1.4 com autoconfig privado de firstboot fora do Git.

- c12_1_3_strategy: `lab_autoconfig_required`
- c12_1_4_requires_private_firstboot_conf: `true`
- build_flag_required: `C12_REQUIRE_LAB_FIRSTBOOT_CONF=1`
- firstboot_private_env: `C12_LAB_FIRSTBOOT_CONF=/path/privado/firstboot.conf`
- ready_for_c12_1_4_rebuild: `true`
- ready_for_next_card_write: `false`

## C12.1.4 Build Attempt

C12.1.4 validou o `firstboot.conf` privado fora do Git sem imprimir valores,
mas nao gerou imagem porque o ambiente de build atual nao tem Docker disponivel.

- c12_1_4_firstboot_conf_private_validated: `true`
- c12_1_4_build_success: `false`
- c12_1_4_blocker: `build_env_docker_missing`
- c12_1_4_image_file: `not_created`
- c12_1_4_sha256: `not_created`
- c12_1_4_lab_firstboot_autoconfig: `not_built`
- c12_1_4_card_written: `false`
- c12_1_4_boards_touched: `false`
- ready_for_c12_2_2_card_write: `false`

## C12.3.1 Reliability Gate

C12.3 boot validation is blocked. The first image-lab boot proved that Dadooh
starts and reaches `config_missing`, but it did not validate read-only because
root was observed as ext4 `rw` and the F10 settings session ended as stale
state after `totem-open-settings.service` was killed.

The next image-lab rebuild must include:

- open-settings `ExecStopPost` cleanup;
- stale lock cleanup in the trigger;
- firstboot gate while `/root/.not_logged_in_yet` exists;
- optional private `C12_LAB_FIRSTBOOT_CONF` outside Git for lab autoconfig;
- explicit read-only assertion before any C12.3.x success claim.

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
