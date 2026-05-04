# C9.6.2 Wi-Fi apply com pausa do player

Data: 2026-05-04

Commit base: `9d6d8ce`

## Comandos

- `python3 scripts/board/totem_wifi_nm_adapter.py --self-test`
- `python3 scripts/board/totem_wifi_local_credentials_tty.py --self-test`
- `bash -n scripts/remote/run_c9_6_1_wifi_local_console_apply.sh`
- `git diff --check`
- `scripts/remote/run_c9_6_1_wifi_local_console_apply.sh <host> --prepare-only`
- `scripts/remote/run_c9_6_1_wifi_local_console_apply.sh <host> --local-console-preflight`
- `scripts/remote/run_c9_6_1_wifi_local_console_apply.sh <host> --local-console-apply-with-player-pause`

## Resultado

- pausa do `kiosky-player.service`: executada com confirmacao humana;
- TTY local: apareceu depois da pausa do player;
- credenciais: digitadas localmente no totem;
- apply real: tentado;
- resultado de ativacao Wi-Fi: `failure`;
- rollback: tentado;
- perfil dedicado ao fim: ausente;
- rede alterada durante tentativa: `true`;
- servico final: `active/enabled`;
- `NRestarts`: `0`;
- playback final: `playing`;
- processos finais: player `1`, MPV `1`, renderer `0`, setup `0`;
- SSH permaneceu acessivel.
- arquivo temporario de credenciais: removido sem leitura apos a rodada.

## Garantias Observadas

- config real nao foi lida;
- config real nao foi escrita;
- writer nao foi chamado;
- hotspot nao foi criado;
- portal nao foi criado;
- reboot nao foi chamado;
- senha, SSID, IP, MAC, BSSID, gateway, DNS, hostname e UUID nao foram
  publicados nesta evidencia.

## Pendencia

O runner executou o apply, mas saiu com rc `31` porque o status local sobrescreveu
`credentials_collected` ao registrar `apply_attempted`. O bug foi corrigido no
script local para preservar campos ja coletados. O resultado de rede desta
rodada continua valido como tentativa real com rollback e restauracao do player.
