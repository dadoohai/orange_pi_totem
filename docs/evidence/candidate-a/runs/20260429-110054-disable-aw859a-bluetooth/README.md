# Rodada 20260429-110054 - Desabilitar AW859A Bluetooth

Status: aprovado para desabilitar `aw859a-bluetooth.service` sem regressao observada em Wi-Fi cliente.

## Objetivo

Desabilitar somente `aw859a-bluetooth.service`, limpar o estado falhado, coletar diagnostico, validar Wi-Fi, fazer reboot limpo e repetir a validacao pos-reboot.

## Execucao

Host usado: `root@[ip-local-redigido]`

Comandos e scripts executados:

- `systemctl --failed`
- `systemctl status aw859a-bluetooth.service --no-pager -l`
- `nmcli device status`
- `rfkill list`
- `systemctl disable --now aw859a-bluetooth.service`
- `systemctl reset-failed aw859a-bluetooth.service`
- `scripts/board/collect_diag.sh`
- `scripts/board/wifi_snapshot.sh`
- `scripts/board/wifi_client_test.sh "<conexao-wifi-redigida>"`
- `sync && systemctl reboot`
- `scripts/board/collect_diag.sh`
- `scripts/board/wifi_snapshot.sh`
- `scripts/board/wifi_client_test.sh "<conexao-wifi-redigida>"`
- `scripts/remote/pull_artifacts.sh`

Nao foi usado `systemctl mask`.

Artefatos brutos copiados localmente:

- `totem-diag-20260429-105750-0300.tar.gz`
- `totem-diag-20260429-110005-0300.tar.gz`
- `wifi-snapshot-20260429-105800-0300.tar.gz`
- `wifi-snapshot-20260429-110016-0300.tar.gz`
- `wifi-client-20260429-105826-0300.tar.gz`
- `wifi-client-20260429-110036-0300.tar.gz`

Os arquivos `.tar.gz` sao evidencia bruta e nao devem ser commitados no repositorio publico. Eles podem conter SSID, BSSID, IPs locais, IPv6, hostname, UUIDs do NetworkManager e logs detalhados.

## Estado Antes

- `systemctl --failed`: 1 unidade falhada.
- Unidade falhada: `aw859a-bluetooth.service`.
- Estado da unidade: `enabled` e `failed`.
- Falha observada: processo `hciattach_opi` encerrado com `status=11/SEGV`.
- Wi-Fi `wlan0`: conectado em conexao NetworkManager existente.
- `rfkill`: Wi-Fi e Bluetooth sem bloqueio soft/hard.

## Estado Apos Disable/Reset

- Comando executado: `systemctl disable --now aw859a-bluetooth.service`.
- Comando executado: `systemctl reset-failed aw859a-bluetooth.service`.
- `systemctl --failed`: `0 loaded units listed`.
- `systemctl is-enabled aw859a-bluetooth.service`: `disabled`.
- `systemctl is-active aw859a-bluetooth.service`: `inactive`.

## Estado Pos-Reboot

- Sistema voltou apos reboot limpo.
- `systemctl --failed`: `0 loaded units listed`.
- `aw859a-bluetooth.service`: `disabled`.
- `aw859a-bluetooth.service`: `inactive`.
- `kernel tainted`: `1024`, observado e aceito nesta fase.
- Filtro critico do kernel sem `Internal error: Oops`.
- Filtro critico do kernel sem `kernel panic`.
- Filtro critico do kernel sem `EXT4-fs error`.
- Filtro critico do kernel sem `Aborting journal`.
- Filtro critico do kernel sem `Remounting filesystem read-only`.
- Filtro critico do kernel sem `mmc timeout/reset`.

O filtro amplo do kernel ainda mostra mensagens conhecidas de boot como `thermal_sys` e `Error applying setting, reverse things back` para UART/SPI/MMC, sem impacto critico observado nesta rodada.

## Wi-Fi

Antes do reboot:

- `wlan0`: conectado com conexao NetworkManager existente.
- `wifi_client_test.sh`: sucesso.
- `ping -I wlan0 -c 4 1.1.1.1`: 4/4 respostas, 0% de perda.

Apos reboot:

- `wlan0`: reconectou com conexao NetworkManager existente.
- `wifi_client_test.sh`: sucesso.
- `ping -I wlan0 -c 4 1.1.1.1`: 4/4 respostas, 0% de perda.

Nesta bancada, `end0` aparece como nao disponivel e o acesso foi mantido por Wi-Fi.

## Observacoes

- `rfkill` ainda pode listar hardware Bluetooth mesmo com o servico AW859A desabilitado. Isso indica presenca do controlador/hardware, nao que a unidade userland esteja ativa.
- Como `disable` resolveu o estado falhado e sobreviveu ao reboot, `mask` nao foi necessario nesta rodada.
- Nenhum pacote foi instalado.
- Nenhum app foi iniciado.
- MPV nao foi iniciado.
- Nenhum servico systemd da aplicacao foi ativado.

## Conclusao

`aw859a-bluetooth.service` foi desabilitado com sucesso, o failed state foi limpo, o sistema voltou apos reboot com `systemctl --failed = 0`, e o Wi-Fi cliente continuou funcionando com ping via `wlan0` sem perda.
