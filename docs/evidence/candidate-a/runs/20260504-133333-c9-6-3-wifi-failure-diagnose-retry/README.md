# C9.6.3 Wi-Fi failure diagnose/retry

Data: 2026-05-04

Commit base: `ae55df8`

## Comandos

- `git status --short`
- `git diff --check`
- `bash -n scripts/remote/run_c9_6_1_wifi_local_console_apply.sh`
- `python3 scripts/board/totem_wifi_nm_adapter.py --self-test`
- `python3 scripts/board/totem_wifi_local_credentials_tty.py --self-test`
- `scripts/remote/run_c9_6_1_wifi_local_console_apply.sh <host> --prepare-only`
- `scripts/remote/run_c9_6_1_wifi_local_console_apply.sh <host> --diagnose-last-failure`
- `scripts/remote/run_c9_6_1_wifi_local_console_apply.sh <host> --local-console-preflight`
- `scripts/remote/run_c9_6_1_wifi_local_console_apply.sh <host> --local-console-diagnose-retry-with-player-pause`

## Diagnostico da Falha Anterior

- NetworkManager disponivel: `true`;
- nmcli disponivel: `true`;
- Wi-Fi device presente: `true`;
- ativacao tentada: `true`;
- resultado: `failure`;
- categoria publica: `nm_activation_failed_generic`;
- rollback status: `attempted`;
- perfil dedicado final: ausente;
- secrets-file removido: `true`.

## Retentativa C9.6.3

- confirmacao humana: recebida;
- player pausado temporariamente: sim;
- TTY local: usado;
- credenciais: digitadas localmente no totem;
- apply real: tentado;
- resultado da ativacao: `failure`;
- categoria publica final: `nm_activation_failed_generic`;
- rollback status: `attempted`;
- rollback efetivo: `success`;
- perfil dedicado final: ausente;
- network_changed: `true`;
- secrets-file final: ausente.

## Retentativa Adicional com Outra Rede

- confirmacao humana: recebida;
- apply real: tentado;
- resultado da ativacao: `failure`;
- categoria publica final: `nm_activation_failed_generic`;
- rollback status: `attempted`;
- rollback efetivo: `success`;
- perfil dedicado final: ausente;
- network_changed: `true`;
- secrets-file final: ausente;
- servico final: `active/enabled`;
- `NRestarts`: `0`;
- playback final: `playing`;
- SSH: acessivel.

## Retentativa Efetiva Apos Correcao Estreita

- correcao aplicada: verificacao do perfil dedicado por `connection.id` e
  origem do perfil mantida durante a ativacao;
- confirmacao humana: recebida;
- player pausado temporariamente: sim;
- credenciais: digitadas localmente no totem;
- apply real: tentado;
- resultado da ativacao: `success`;
- categoria publica final: `none`;
- rollback status: `attempted`;
- rollback efetivo: `success`;
- perfil dedicado final: ausente;
- network_changed: `true`;
- secrets-file final: ausente;
- SSH: acessivel.

## Estado Final

- servico: `active/enabled`;
- `NRestarts`: `0`;
- public_state: `unknown`;
- playback: `playing`;
- processos finais: player `1`, MPV `1`, renderer `0`, setup `0`;
- SSH: acessivel.

## Garantias

- config real nao foi lida;
- config real nao foi escrita;
- writer nao foi chamado;
- hotspot nao foi criado;
- portal nao foi criado;
- reboot nao foi chamado;
- SSID, senha, IP, MAC, BSSID, gateway, DNS, hostname, nome de conexao, UUID,
  api_key, api_url real, environment_id real e logs brutos nao foram publicados.

## Proximo Passo

C9.7 pode integrar o resultado Wi-Fi controlado ao Setup Produto Local V0, ainda
sem hotspot/portal e sem writer/config real.
