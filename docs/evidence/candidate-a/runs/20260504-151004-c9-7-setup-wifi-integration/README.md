# C9.7 Setup Wi-Fi Integration

Data: 2026-05-04

Commit base: `2701e22`

## Comandos

- `git status --short`
- `git log --oneline -5`
- `git diff --check`
- `bash -n scripts/remote/run_c9_6_1_wifi_local_console_apply.sh`
- `bash -n scripts/remote/run_c9_7_setup_wifi_integration.sh`
- `python3 scripts/board/totem_wifi_nm_adapter.py --self-test`
- `python3 scripts/board/totem_wifi_local_credentials_tty.py --self-test`
- `python3 scripts/board/totem_setup_local_wizard.py --self-test`
- `python3 scripts/board/totem_config_contract_validate.py --self-test`
- `scripts/remote/run_c9_7_setup_wifi_integration.sh <host> --prepare-only`
- `scripts/remote/run_c9_7_setup_wifi_integration.sh <host> --run-wifi-test-scripted`
- `scripts/remote/run_c9_7_setup_wifi_integration.sh <host> --run-cancel`
- `scripts/remote/run_c9_7_setup_wifi_integration.sh <host> --run-complete-with-wifi-rollback-after-test`

## Cancelamento

- wizard apareceu em HDMI/TTY;
- cancelamento solicitado no teclado local;
- candidata nao gerada;
- servico restaurado: `active/enabled`;
- `NRestarts`: `0`;
- `public_state`: `player_running`;
- player/MPV ativos ao final;
- renderer/setup ausentes ao final.

## Conclusao com Wi-Fi

- wizard C9.7 exibiu a opcao `Testar Wi-Fi agora`;
- credenciais digitadas localmente no totem;
- apply Wi-Fi real: tentado;
- resultado de ativacao: `success`;
- rollback-after-test: `success`;
- perfil dedicado final: ausente;
- secrets-file final: ausente;
- candidata gerada: sim;
- C5.1 `--allow-mock`: passou;
- C5.1 `--real-dry-run`: falhou como esperado por mock/placeholders;
- `network_changed`: `true`;
- SSH permaneceu acessivel.

## Estado Final Tardio

- servico: `active/enabled`;
- `NRestarts`: `0`;
- `public_state`: `player_running`;
- playback: `playing`;
- processos finais: player `1`, MPV `1`, renderer `0`, setup `0`;
- perfil dedicado final: ausente.

## Garantias

- config real nao foi lida;
- config real nao foi escrita;
- writer nao foi chamado;
- hotspot nao foi criado;
- portal nao foi criado;
- reboot nao foi chamado;
- `kiosky-player` nao foi alterado;
- SSID, senha, IP, MAC, BSSID, gateway, DNS, hostname, nome de conexao, UUID,
  api_key, api_url real, environment_id real e logs brutos nao foram
  publicados.

## Observacao

Uma tentativa completa anterior expirou enquanto o operador digitava o ambiente
longo. O runner foi ajustado para janela maior e cleanup explicito do wizard
C9.7 em timeout; em seguida a conclusao passou.
