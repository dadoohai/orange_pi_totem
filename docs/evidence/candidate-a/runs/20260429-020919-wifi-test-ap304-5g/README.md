# Rodada 20260429-020919 - Wi-Fi cliente 5G

Status: aprovado para validacao de Wi-Fi cliente com conexao NetworkManager existente.

## Objetivo

Validar Wi-Fi cliente na imagem Candidato A sem desconectar Ethernet, sem registrar senha e sem criar conexao nova durante a rodada automatizada.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts executados:

- `scripts/board/wifi_client_test.sh "<conexao-wifi-redigida>"`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefatos brutos copiados localmente:

- `wifi-client-20260429-020901-0300.tar.gz`
- `totem-diag-20260429-020914-0300.tar.gz`

Os arquivos `.tar.gz` sao evidencia bruta e nao devem ser commitados no repositorio publico. Eles podem conter SSID, BSSID, IPs locais, IPv6, hostname, UUIDs do NetworkManager e detalhes de logs.

## Resultado

- `nmcli connection up`: sucesso, `exit_code=0`.
- `wlan0`: conectado usando conexao Wi-Fi existente.
- Endereco em `wlan0`: recebido com sucesso.
- Ping via Wi-Fi: `ping -I wlan0 -c 4 1.1.1.1` com 4/4 respostas e 0% de perda.
- DNS: `getent hosts deb.debian.org` retornou resultado com sucesso. Observacao: este teste usa a resolucao do sistema e pode passar pela rota geral, portanto o ping com `-I wlan0` e a evidencia principal do caminho Wi-Fi.
- Ethernet `end0`: permaneceu conectada durante o teste.
- NetworkManager: ativacao do Wi-Fi concluida; DHCP4 e DHCP6 registrados; senha permaneceu oculta como `<hidden>` nos logs.
- `systemctl --failed`: `0 loaded units listed`.
- `kernel tainted`: `1024`, observado e aceito nesta fase de validacao.

## Filtro Critico

Nao foram observados:

- `Internal error: Oops`
- `kernel panic`
- `EXT4-fs error`
- `Aborting journal`
- `Remounting filesystem read-only`
- `mmc timeout/reset`

O filtro amplo do kernel ainda mostra mensagens conhecidas de boot como `thermal_sys` e `Error applying setting, reverse things back` para UART/SPI/MMC, sem impacto critico observado nesta rodada.

## Conclusao

Wi-Fi cliente aprovado nesta rodada: `wlan0` conectou, recebeu endereco, respondeu ping via interface Wi-Fi e a Ethernet permaneceu conectada.
