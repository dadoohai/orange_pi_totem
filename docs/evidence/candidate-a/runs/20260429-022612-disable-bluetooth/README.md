# Rodada 20260429-022612 - Desabilitar Bluetooth

Status: aprovado para desabilitar Bluetooth sem regressao observada em boot, servicos ou Wi-Fi cliente.

## Objetivo

Desabilitar `bluetooth.service`, fazer reboot limpo e verificar se a imagem Candidato A continua sem falhas criticas, com Ethernet ativa e Wi-Fi cliente funcional.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts e acoes executadas:

- `scripts/board/disable_bluetooth.sh`
- `scripts/board/collect_diag.sh`
- `sync && systemctl reboot`
- `scripts/board/collect_diag.sh`
- `scripts/board/wifi_client_test.sh "<conexao-wifi-redigida>"`
- `scripts/remote/pull_artifacts.sh`

Artefatos brutos copiados localmente:

- `bluetooth-disable-20260429-022417-0300.tar.gz`
- `totem-diag-20260429-022424-0300.tar.gz`
- `totem-diag-20260429-022543-0300.tar.gz`
- `wifi-client-20260429-022552-0300.tar.gz`

Os arquivos `.tar.gz` sao evidencia bruta e nao devem ser commitados no repositorio publico. Eles podem conter IPs locais, IPv6, hostname, SSID, nomes de conexao, UUIDs do NetworkManager e logs detalhados.

## Bluetooth

Estado antes:

- `bluetooth.service`: enabled.
- `bluetooth.service`: active.

Acao:

- `systemctl disable --now bluetooth`
- `exit_code=0`

Estado depois da acao:

- `bluetooth.service`: disabled.
- `bluetooth.service`: inactive.
- Parada do servico registrada como sucesso.

Apos reboot, o sistema voltou e a coleta pos-reboot foi executada com sucesso. O `rfkill` ainda lista controladores Bluetooth, incluindo `hci0`, o que indica presenca do hardware/driver; isso nao significa que o servico userland esteja habilitado.

## Resultado Pos-Reboot

- `systemctl --failed`: `0 loaded units listed`.
- `kernel tainted`: `1024`, observado e aceito nesta fase.
- Filtro critico do kernel sem `Internal error: Oops`.
- Filtro critico do kernel sem `kernel panic`.
- Filtro critico do kernel sem `EXT4-fs error`.
- Filtro critico do kernel sem `Aborting journal`.
- Filtro critico do kernel sem `Remounting filesystem read-only`.
- Filtro critico do kernel sem `mmc timeout/reset`.
- Nao apareceu log `Bluetooth: hci0` no filtro critico do kernel pos-reboot.

O filtro amplo do kernel ainda mostra mensagens conhecidas de boot como `thermal_sys` e `Error applying setting, reverse things back` para UART/SPI/MMC, sem impacto critico observado nesta rodada.

## Wi-Fi Apos Desabilitar Bluetooth

- `wlan0`: conectou usando conexao NetworkManager existente.
- `wlan0`: recebeu IP.
- `ping -I wlan0 -c 4 1.1.1.1`: sucesso, 4/4 respostas e 0% de perda.
- Ethernet `end0`: permaneceu conectada.

## Conclusao

Bluetooth foi desabilitado com sucesso, o sistema voltou apos reboot limpo, nao houve servicos falhados, o filtro critico permaneceu limpo para os criterios de bloqueio e o Wi-Fi cliente continuou funcional.
