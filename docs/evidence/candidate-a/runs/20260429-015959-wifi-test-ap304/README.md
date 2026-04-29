# Rodada 20260429-015959 - Wi-Fi cliente test-ap304

Status: conectividade Wi-Fi observada com ressalva. O comando solicitado para subir a conexao `test-ap304` retornou conexao desconhecida, mas `wlan0` ficou conectado por uma conexao Wi-Fi relacionada ja existente/ativa e passou no ping via interface.

## Objetivo

Validar Wi-Fi cliente sem desconectar Ethernet, usando uma conexao NetworkManager previamente criada manualmente na placa.

## Scripts executados

- `scripts/board/wifi_snapshot.sh`
- `scripts/board/wifi_client_test.sh "test-ap304"`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

## Artefatos brutos locais

Artefatos novos relevantes desta rodada:

- `wifi-snapshot-20260429-015925-0300.tar.gz`
- `wifi-client-20260429-015938-0300.tar.gz`
- `totem-diag-20260429-015951-0300.tar.gz`

Os comandos de pull tambem copiaram artefatos antigos que ainda existiam em `/root/totem-diag/`, porque os filtros usados foram `wifi-*.tar.gz` e `totem-diag-*.tar.gz`.

Os `.tar.gz` brutos podem conter SSIDs, BSSIDs, IPs, IPv6, hostname, UUIDs e logs do NetworkManager. Nao devem ser commitados no repositorio publico.

## Resultado Wi-Fi

- Conexao solicitada: `test-ap304`.
- Resultado do `nmcli connection up`: falhou com `conexao desconhecida`, exit code `10`.
- `wlan0` conectou: sim, observado apos o teste.
- Conexao ativa em `wlan0`: redigida.
- `wlan0` recebeu IP: sim.
- Ping via `wlan0`: aprovado, `4 transmitted, 4 received, 0% packet loss`.
- DNS: `getent hosts deb.debian.org` retornou resultado. Observacao: DNS pode usar a rota geral do sistema e nao prova, sozinho, que a consulta saiu pela interface Wi-Fi.
- Ethernet: permaneceu conectada em `end0`.

Interpretacao: a conectividade Wi-Fi da placa funcionou, mas a conexao nominal `test-ap304` nao foi encontrada pelo NetworkManager no momento do `nmcli connection up`. A rodada valida conectividade por `wlan0`, mas ainda pede ajuste/confirmacao do nome da conexao salva para rastreabilidade perfeita.

## Diagnostico Geral

- `systemctl --failed`: `0 loaded units listed`.
- Kernel tainted: `1024`, observado e esperado nesta fase.
- Filtro critico de kernel: sem `Oops`, `kernel panic`, `EXT4-fs error`, `Aborting journal`, `Remounting filesystem read-only` ou `mmc timeout/reset`.
- Mensagens conhecidas `Error applying setting, reverse things back` para UART/SPI/MMC continuam presentes no boot, sem impacto critico observado.

## Proximos passos sugeridos

- Conferir o nome exato da conexao salva no NetworkManager e repetir o teste com esse nome.
- Ajustar a documentacao da rodada seguinte para registrar a conexao redigida, sem expor SSID real.
- Usar filtro mais especifico no `pull_artifacts.sh` para copiar apenas os arquivos da rodada nova.
