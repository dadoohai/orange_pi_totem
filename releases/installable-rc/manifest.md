# Installable Bench RC Manifest

Data: 2026-05-05

Status:

- `installable_bench_rc=true`
- `final_image=false`
- `read_only=false`
- `power_cut_tested=false`
- `long_test=false`
- `ready_for_c11_readiness=true`
- `c10_10_1_power_state_audit=POWER_STATE_EXPECTED_BUT_UX_UNCLEAR`
- `c10_10_2_shutdown_ux=passed_no_poweroff_executed`
- `shutdown_ux_followup_required=false`
- `c11_0_read_only_readiness_audit=needs_policy_before_enablement`
- `c11_1_read_only_policy=policy_defined_not_applied`
- `c11_2_read_only_mitigation=applied_on_dev_not_read_only`
- `c11_3_read_only_enablement=blocked_missing_overlayroot_package`
- `c11_3_1_overlayroot_prereq=installed_on_dev_not_enabled`
- `c11_3_2_read_only_enable_dev=blocked_overlayroot_not_activated`
- `c11_3_3_overlayroot_mechanism_lab=blocked_initramfs_driver_lookup`
- `root_read_only_ready=false`
- `ready_for_read_only_enablement=false`
- `ready_for_c11_1_policy=false`
- `ready_for_c11_2_enablement=true`
- `ready_for_c11_3_enablement=true`
- `ready_for_c11_3_2_enablement=blocked_after_retest`
- `ready_for_c11_4=false`
- `ready_for_c12_image=false`

## Orange Pi Totem

- repository: `dadoohai/orange_pi_totem`
- branch: `foundation-v0.1`
- validated_base_commit: `2b8c620eb7827bc286e08d6c8d4e9df63a593801`
- c10_10_package_commit: `72bdebac203de1596f7fbafb9213a6a55eb233d3`
- release_policy: C10.10.2 closes the shutdown UX follow-up for the installable
  bench RC. This is still not a final image.

## Kiosky-player Pin

- repository: `dadoohai/kiosky-player`
- ref: `appliance-v0.1`
- commit: `c71318a64c08e47b8426f1388b95f21364d57123`
- install_path: `/opt/totem/kiosky-player`
- policy: install/export this exact tree, excluding `.git`, private config,
  environment files, media cache and secrets.

## Principal Scripts

- `scripts/board/totem_appliance_manifest.json`
- `scripts/board/install_totem_appliance.sh`
- `scripts/board/verify_totem_appliance.sh`
- `scripts/board/totem_private_values_prepare.py`
- `scripts/board/totem_open_settings_session.sh`
- `scripts/board/totem_setup_visual_wizard.py`
- `scripts/board/totem_visual_setup_writer_handoff.py`
- `scripts/board/totem_visual_splash.py`
- `scripts/board/totem_status_aggregate.py`
- `scripts/board/totem_status_render_preview.py`
- `scripts/board/totem_config_contract_validate.py`
- `scripts/board/totem_config_writer_real.py`
- `scripts/board/totem_read_only_policy.json`
- `scripts/board/verify_totem_read_only_policy.sh`
- `scripts/remote/run_c10_9_second_board_clean_install.sh`
- `scripts/remote/run_c10_9_1_second_board_provision.sh`
- `scripts/remote/run_c11_0_read_only_readiness_audit.sh`
- `scripts/remote/run_c11_1_read_only_policy_probe.sh`
- `scripts/remote/run_c11_2_read_only_mitigation_apply.sh`
- `scripts/remote/run_c11_3_read_only_enablement_dev.sh`
- `scripts/remote/run_c11_3_1_overlayroot_prereq.sh`
- `scripts/remote/run_c11_3_2_read_only_enable_dev.sh`
- `scripts/remote/run_c11_3_3_overlayroot_mechanism_lab.sh`

## Units

- `scripts/board/kiosky-player.service`
- `scripts/board/totem-settings-trigger.service`
- `scripts/board/totem-open-settings.service`
- `scripts/board/dadooh-visual-splash.service`

## Runtime Minimo

- `python3`
- `mpv`
- `ffmpeg`
- `python3-requests`
- `NetworkManager`

Read-only prerequisite for C11/C12 image:

- package: `overlayroot`;
- command: `overlayroot-chroot`;
- initramfs script: `/usr/share/initramfs-tools/scripts/init-bottom/overlayroot`;
- install flag: `--install-readonly-prereqs`;
- policy: exact package only, `--no-upgrade`, no broad upgrades.

Runtime install policy:

- explicit packages only;
- `apt-get install --no-install-recommends` when authorized;
- no `apt upgrade`;
- no `apt full-upgrade`;
- no `apt dist-upgrade`;
- no `armbian-upgrade`;
- no desktop, Chromium, Xorg, Wayland or compositor.

## Dados Que Entram

- appliance scripts versionados;
- systemd units versionadas;
- manifest appliance;
- boot visual guardrails;
- public `orientation.json` contract/default;
- sanitized installed manifest;
- pinned `kiosky-player` tree.

## Dados Que Nao Entram

- `/data/config/config.json`;
- API key;
- real API URL;
- real environment identifier;
- station identifier;
- Wi-Fi SSID/password;
- IP, MAC, DNS, gateway or hostname;
- backups;
- raw logs;
- media cache;
- private candidate files;
- private-values files.

## Read-only Readiness

C11.0 auditou a placa dev sem alterar estado e concluiu:

- root read-only ainda nao esta pronto para habilitacao;
- paths mutaveis principais ja estao em `/data`, `/tmp` ou `/run`;
- blockers atuais:
  - `NetworkManager` em `/etc/NetworkManager/system-connections`;
  - journald/log policy em `/var/log/journal`;
- tambem precisam de politica: `/var/lib/systemd`,
  `/var/lib/NetworkManager`, `/etc/systemd/system` e `/boot/armbianEnv.txt`.

C11.1 definiu a politica concreta de mitigacao:

- NetworkManager: manter perfis no caminho nativo e permitir escrita somente em
  janela controlada de manutencao/configuracao;
- journald: usar politica volatil na imagem de produto;
- `/boot` e `/etc`: escrita somente por instalador/manutencao com backup e
  rollback;
- `/var`: validar estado runtime volatil/overlay em C11.2;
- `/data`, `/tmp` e `/run`: paths normais de escrita do produto.

O probe C11.1 rodou somente na placa dev e nao alterou estado operacional.
`ready_for_c11_2_enablement=true`, mas `root_read_only_ready=false` e
`ready_for_read_only_enablement=false` ate C11.2 aplicar as mitigacoes
reversiveis. Nao habilitar read-only nem executar corte seco ainda.

C11.2 aplicou mitigacoes reversiveis somente na placa dev:

- journald volatil por drop-in;
- rollback state em `/data/state/totem-read-only-mitigation`;
- politica pratica registrada para NetworkManager, `/var`, `/boot` e `/etc`;
- reboot controlado validado;
- placa teste nao tocada;
- Wi-Fi/NetworkManager, config real, writer, pacotes e `kiosky-player` nao
  alterados.

Resultado: `ready_for_c11_3_enablement=true`, com
`root_read_only_ready=false` e `ready_for_read_only_enablement=false` ate o
enablement real de root read-only/overlay.

C11.3 inspecionou o enablement read-only na dev e detectou o mecanismo
`armbian_config_module_overlayfs`, mas `overlayroot`/`overlayroot-chroot` nao
estao presentes. Como a rodada proibe instalar pacotes, o enablement foi
bloqueado com seguranca:

- `enable_executed=false`;
- `read_only_enabled=false`;
- `overlay_active=false`;
- `ready_for_c11_4=false`.

Proximo gate precisa decidir como aprovisionar o mecanismo oficial sem
`apt upgrade`, ou mover esse requisito para a imagem base.

C11.3.1 identificou `overlayroot` como pacote exato para o mecanismo oficial
do Armbian. Na dev, a instalacao controlada foi executada apos confirmacao e
disponibilizou `overlayroot-chroot` e o script de initramfs do pacote. O
dry-run previo foi seguro:
`would_upgrade_count=0`, `would_remove_count=0` e nenhum pacote
kernel/DTB/U-Boot/BSP seria tocado. O instalador agora declara
`--install-readonly-prereqs`; a imagem final C12 deve incluir esse pacote antes
do enablement read-only.


C11.3.2 executou reteste com fonte dedicada depois de recuperacao offline. A
falha anterior ficou `POWER_SUPPLY_CONFOUNDED`, mas o reteste confirmou que o
mecanismo atual nao ativou read-only: `ssh_returned=true`,
`read_only_enabled=false`, `overlay_active=false`, player final running e
rollback executado. C11.4 permanece bloqueado; read-only deve migrar para uma
nova estrategia em cartao separado ou imagem/base C12.


C11.3.3 moveu a investigacao para a placa teste. O pacote `overlayroot` foi
instalado na teste apos dry-run seguro e o enable/reboot de laboratorio voltou
por SSH, mas o overlay nao ativou: `read_only_enabled=false`,
`overlay_active=false`, causa sanitizada `initramfs_log_driver_lookup_failed`.
Rollback executado na teste. C11.4 continua bloqueado e a dev nao deve receber
novas tentativas diretas.

## Handoff

Runbook:

- `docs/product/90_PACOTE_INSTALAVEL_RC_BANCADA.md`

Evidence:

- `docs/evidence/candidate-a/runs/20260505T205432Z-c10-10-installable-rc-package/README.md`

Next gate:

- C11.3.2 read-only enablement after overlayroot prereq is installed.

Not next:

- final image generation;
- root read-only enablement;
- power-cut testing;
- long-run homologation.
