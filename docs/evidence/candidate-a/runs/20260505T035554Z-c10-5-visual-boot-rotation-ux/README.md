# C10.5 Visual Boot/Rotation UX

Data UTC: 2026-05-05T03:55:54Z

Commit base: `72bf3ed Add C10.4 product surface writer flow`

## Comandos

- `git diff --check`
- `bash -n scripts/remote/run_c10_5_visual_boot_rotation.sh`
- `python3 scripts/board/totem_setup_visual_wizard.py --self-test`
- `python3 scripts/board/totem_visual_splash.py --self-test`
- `python3 scripts/board/totem_wifi_nm_adapter.py --self-test`
- `python3 scripts/board/totem_config_contract_validate.py --self-test`
- `scripts/remote/run_c10_5_visual_boot_rotation.sh <board-host> --prepare-only`

## Resultado

- `prepare-only`: passou.
- Preview/validacao humana HDMI: passou parcialmente.
- Texto tecnico de login/getty: removido durante o runner visual ao pausar temporariamente o getty da TTY de produto.
- Input do wizard: voltou a responder com uma unica tecla.
- Splash de transicao: exibiu tela Dadooh limpa; ainda e estatico e nao substitui animacao futura.
- Rotacao: preview e confirmacao funcionam, `rotation_deg` continua na candidata; rotacao fisica completa da UI foi descartada nesta rodada por distorcer texto.

## Estado Operacional

- Writer chamado: `false`.
- Config real lida: `false`.
- Config real escrita: `false`.
- Wi-Fi/NetworkManager alterado: `false`.
- Root read-only habilitado: `false`.
- Corte seco executado: `false`.
- Guardrails persistentes de boot aplicados: `false`.
- Reboot visual executado: `false`.

## Pendencias

- Aplicar guardrails persistentes de boot/getty/splash somente com confirmacao humana explicita.
- Validar reboot visual depois de aplicar guardrails persistentes.
- Implementar loading/animacao de produto para substituir splash estatico.
- Implementar rotacao visual completa do wizard em uma camada de renderizacao que nao distorca texto.
