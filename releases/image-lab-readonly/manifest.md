# Image Lab Read-only Manifest

Data: 2026-05-06

Status:

- `image_lab_readonly=true`
- `final_image=false`
- `image_built=true`
- `image_version=c12.1.6`
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
- `ready_for_next_card_write=true`
- `c12_1_3_strategy=lab_autoconfig_required`
- `ready_for_c12_1_4_rebuild=false`
- `c12_1_4_status=blocked`
- `c12_1_4_blocker=lab_firstboot_autoconfig_not_effective`
- `c12_1_4_firstboot_conf_private_validated=true`
- `c12_1_4_image_built=true`
- `c12_3_3_status=blocked`
- `c12_3_3_blocker=lab_firstboot_autoconfig_not_effective`
- `c12_1_5_status=passed`
- `c12_1_5_rootfs_inspection_added=true`
- `c12_1_6_status=passed`
- `c12_1_6_rootfs_firstboot_autoconfig_proven=true`
- `c12_1_6_lab_bootstrap_service_included=true`
- `ready_for_c12_2_2_card_write=false`
- `ready_for_c12_2_3_card_write=true`
- `c12_3_4_status=blocked`
- `c12_3_4_boot_success=true`
- `c12_3_4_ssh_available=true`
- `c12_3_4_firstboot_bootstrap=passed`
- `c12_3_4_read_only_enabled=false`
- `c12_3_4_overlay_active=false`
- `c12_3_4_root_fstype=ext4_rw`
- `c12_3_4_blocker=IMAGE_LAB_READ_ONLY_NOT_ACTIVE`
- `c12_3_4_candidate_only=CANDIDATE_ONLY_EXPECTED_WITHOUT_PRIVATE_VALUES`
- `ready_for_c12_4=false`
- `ready_for_c12_1_7=true`
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

## C12.1.4 Rebuild Artifacts

C12.1.4 validou o `firstboot.conf` privado fora do Git sem imprimir valores e
gerou a nova imagem-lab bootavel em laboratorio.

- c12_1_4_build_commit: `7e74ebf`
- c12_1_4_source_head: `9e3945c`
- c12_1_4_firstboot_conf_private_validated: `true`
- c12_1_4_build_success: `true`
- c12_1_4_blocker: `lab_firstboot_autoconfig_not_effective`
- image_version: `c12.1.4`
- image_file:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-4_minimal.img`
- image_checksum_file:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-4_minimal.img.sha256`
- image_sha256:
  `405d4891e62d018862008f3bfdf00e02123b551351655147ec7448b803ccca14`
- build_log_file:
  `/home/builder/totem-os/armbian-build-v25.11/output/logs/log-build-7f1e148a-583b-48af-b701-1fc2396d067b.log`
- package_manifest_file:
  `releases/image-lab-readonly/package-manifest-c12-1-4.txt`
- read_only_integration_manifest_file:
  `releases/image-lab-readonly/read-only-integration-manifest-c12-1-4.txt`
- overlayroot_included: `true`
- initramfs_generated_after_overlayroot: `true`
- initramfs_source: `cache_hit_with_overlayroot_hooks`
- firstboot_gate_included: `true`
- lab_firstboot_autoconfig: `true`
- lab_firstboot_boot_validatable: `true`
- open_settings_cleanup_included: `true`
- read_only_assertion_required: `true`
- c12_1_4_card_written: `false`
- c12_1_4_boards_touched: `false`
- ready_for_c12_2_2_card_write: `false`

## C12.3.3 Firstboot Autoconfig Blocker

C12.1.4 foi gravada e bootada. O fallback visual funcionou, mas mostrou:

```text
Bootstrap tecnico pendente
```

Isso provou que a imagem nao ficou muda, mas tambem provou que o autoconfig de
laboratorio nao foi efetivo no boot. A imagem C12.1.4 nao deve ser reutilizada
como artefato boot-validavel.

Classificacao:

```text
lab_firstboot_autoconfig_not_effective
```

## C12.1.5 Rootfs Inspection

C12.1.5 inspecionou offline a imagem C12.1.4 sem tocar placas ou cartoes. O
resultado foi:

- `rootfs_firstboot_autoconfig_proven=true`;
- `rootfs_lab_bootstrap_proven=false`;
- `ready_for_card_write_by_rootfs=false`.

Causa: o arquivo privado foi incorporado como `/root/.not_logged_in_yet`, mas
essa configuracao e consumida pelo `armbian-firstlogin`, que depende de login
interativo. Nao havia servico lab autonomo para aplicar rede/senha/usuario antes
do `totem-firstboot-gate`.

## C12.1.6 Rebuild Artifacts

C12.1.6 corrige C12.1.4 adicionando um servico lab autonomo de firstboot e
endurecendo a validacao para inspecionar o rootfs real da imagem.

- image_version: `c12.1.6`
- image_file:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-6_minimal.img`
- image_checksum_file:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-6_minimal.img.sha256`
- image_sha256:
  `b64808a7ce23d7c19422c816ca558605d39b495019ecac0bb480345bff711a67`
- build_log_file:
  `/home/builder/totem-os/armbian-build-v25.11/output/logs/log-build-299de716-0d1f-451c-a145-0edd7fd955c6.log`
- package_manifest_file:
  `releases/image-lab-readonly/package-manifest-c12-1-6.txt`
- read_only_integration_manifest_file:
  `releases/image-lab-readonly/read-only-integration-manifest-c12-1-6.txt`
- overlayroot_included: `true`
- initramfs_generated_after_overlayroot: `true`
- initramfs_source: `cache_hit_with_overlayroot_hooks`
- rootfs_firstboot_autoconfig_proven: `true`
- lab_firstboot_bootstrap_service_included: `true`
- lab_firstboot_bootstrap_service_enabled: `true`
- lab_firstboot_bootstrap_service_ordered_before_gate: `true`
- rootfs_ready_for_card_write: `true`
- card_written: `true`
- boards_touched: `true`
- ready_for_c12_2_3_card_write: `true`

## C12.3.4 Boot Validation C12.1.6

A imagem C12.1.6 foi gravada e bootada em placa de teste. Resultado:

- boot_success: `true`
- ssh_available: `true`
- firstboot_marker_present: `false`
- lab_bootstrap_state: `complete`
- public_state: `config_missing`
- config_real_present: `false`
- config_missing_visual_ok: `true`
- f10_opened_settings_observed_by_human: `true`
- visual_candidate_generated: `true`
- writer_called: `false`
- real_config_written: `false`
- session_lock_present: `false`
- systemctl_failed_count: `1`
- failed_unit_category: `console_setup`

Read-only/overlay:

- overlayroot_config: `overlayroot=tmpfs`
- overlayroot_hooks_present: `true`
- overlay_active: `false`
- read_only_enabled: `false`
- root_fstype: `ext4`
- root_write_blocked: `false`
- data_tmp_run_writable: `true`

Classificacao:

```text
IMAGE_LAB_READ_ONLY_NOT_ACTIVE
CANDIDATE_ONLY_EXPECTED_WITHOUT_PRIVATE_VALUES
UX_AMBIGUOUS_CANDIDATE_ONLY
```

C12.4 provisionamento real nao deve comecar enquanto read-only/overlay estiver
inativo. O proximo passo recomendado e C12.1.7 para diagnosticar por que a
imagem contem configuracao/hook overlayroot, mas o boot ainda monta root como
`ext4 rw`.

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
