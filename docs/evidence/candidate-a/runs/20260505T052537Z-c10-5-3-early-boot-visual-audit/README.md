# C10.5.3 Early Boot Visual Leak Audit

Data UTC: 2026-05-05T05:25:37Z

Commit base: `4cf6861 Add C10.5.2 visual guardrails`

## Comandos

```bash
git status --short
git log --oneline -10
git diff --check
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
bash -n scripts/remote/run_c10_5_2_visual_guard_boot_shutdown.sh
bash -n scripts/remote/run_c10_5_3_early_boot_visual_audit.sh
scripts/remote/run_c10_5_3_early_boot_visual_audit.sh <board-host> --prepare-only
scripts/remote/run_c10_5_3_early_boot_visual_audit.sh <board-host> --inspect
scripts/remote/run_c10_5_3_early_boot_visual_audit.sh <board-host> --plan
scripts/remote/run_c10_5_3_early_boot_visual_audit.sh <board-host> --apply-reversible-boot-quiet
scripts/remote/run_c10_5_3_early_boot_visual_audit.sh <board-host> --reboot-visual-check
```

## Inspecao Antes

- arquivo de boot reconhecido: `true`;
- categoria de console Armbian: `both`;
- categoria de verbosity Armbian: `normal`;
- getty visivel: `not_active`;
- splash service: `active/enabled`;
- servico player: `active/enabled`;
- `systemctl_failed_count=0`;
- writer chamado: `false`;
- config real lida/escrita: `false`;
- Wi-Fi alterado: `false`.

## Plano

Mudancas planejadas e reversiveis:

- `verbosity=0`;
- `console=serial`;
- `loglevel=0`;
- `rd.systemd.show_status=false`;
- `logo.nologo`.

Nao foi desabilitado fsck.

## Aplicacao

- mudancas aplicadas: `true`;
- backup criado: `true`;
- permissoes de backup restritas: `true`;
- rollback disponivel: `true`;
- categoria de console depois: `serial`;
- categoria de verbosity depois: `quiet`;
- reboot requerido: `true`.

## Reboot Visual

- reboot executado: `true`;
- SSH voltou: `true`;
- tempo ate SSH: `8s`;
- observacao humana: vazamento visual sumiu;
- `early_boot_linux_visible=none`;
- `visible_phase=none`;
- `duration_bucket=none`;
- `rollback_needed=false`.

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
- `kernel_critical_filter_count=0`.

## Guardrails

- config real lida: `false`;
- config real escrita: `false`;
- writer chamado: `false`;
- Wi-Fi/NetworkManager alterado: `false`;
- root read-only habilitado: `false`;
- corte seco executado: `false`;
- logs brutos escritos: `false`;
- dados sensiveis publicados: `false`.

## Proximo Passo

C10.6 - Modo Manutencao Local V0.
