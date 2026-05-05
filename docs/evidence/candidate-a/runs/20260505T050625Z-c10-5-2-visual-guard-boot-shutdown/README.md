# C10.5.2 Visual Guard + Boot/Shutdown Guardrails

Data UTC: 2026-05-05T05:06:25Z

Commit base: `9637d76 Add C10.5.1 orientation UX contract`

## Comandos

```bash
git status --short
git log --oneline -10
git diff --check
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
bash -n scripts/remote/run_c10_5_1_orientation_ux_contract.sh
bash -n scripts/remote/run_c10_5_visual_boot_rotation.sh
bash -n scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh
scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh <board-host> --prepare-only
scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh <board-host> --inspect
scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh <board-host> --preview-transition-splash
scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh <board-host> --transition-stress-short
scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh <board-host> --apply-visual-guardrails
scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh <board-host> --reboot-visual-check
```

## Resultado

- `--prepare-only`: passou;
- `--inspect`: passou;
- `--preview-transition-splash`: passou;
- `--transition-stress-short`: passou;
- guardrails persistentes aplicados: `true`;
- rollback state presente: `true`;
- reboot visual executado: `true`;
- SSH voltou: `true`;
- runner C10.5 herdado encerrou cedo na coleta final por reset de SSH durante
  subida da porta; snapshot sanitizado manual pos-reboot passou e o retry do
  runner foi corrigido nesta rodada.

## Estado Final

- servico: `active/enabled`;
- `NRestarts=0`;
- `public_state=player_running`;
- playback `playing`;
- player=1;
- MPV=1;
- renderer=0;
- setup=0;
- `systemctl_failed_count=0`;
- `kernel_critical_filter_count=1`;
- splash service: `active/enabled`.

## Guardrails

- config real lida: `false`;
- config real escrita: `false`;
- writer chamado: `false`;
- Wi-Fi/NetworkManager alterado: `false`;
- root read-only habilitado: `false`;
- corte seco executado: `false`;
- logs brutos escritos: `false`;
- dados sensiveis publicados: `false`.

## Orientacao

- contrato publico allowlisted implementado;
- arquivo publico persistente ainda ausente neste snapshot porque nenhum fluxo
  de wizard confirmou orientacao durante o reboot visual C10.5.2;
- splash usa esse arquivo quando existir e cai para paisagem padrao quando ele
  nao existe.

## Observacao Visual

Observacao humana pos-reboot:

- ainda apareceu rapidamente um texto tecnico tipo Armbian/fsck com contagem de
  `files`/`blocks` durante a inicializacao inicial;
- logo depois surgiu o splash Dadooh `Inicializando`;
- isso indica reducao do vazamento, mas nao eliminacao completa da janela muito
  cedo de boot antes do splash de produto.

Classificacao: residual early-boot fsck/console text. Nao foi desabilitado nesta
rodada porque isso exigiria mexer mais fundo em politica de fsck/initramfs/boot
antes do corte read-only.

## Proximo Passo

C10.6 - Modo Manutencao Local V0, mantendo os guardrails visuais aplicados e
rollback disponivel.
