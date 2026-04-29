# Rodada 20260429-014815 - Wi-Fi cliente

Status: nao aprovado para Wi-Fi cliente nesta rodada. A Ethernet permaneceu conectada e o teste nao alterou conexoes salvas.

## Objetivo

Validar Wi-Fi cliente usando apenas uma conexao Wi-Fi ja existente no NetworkManager, sem desconectar Ethernet e sem registrar senha de rede.

## Scripts executados

- `scripts/board/wifi_snapshot.sh`
- `scripts/board/wifi_client_test.sh`
- `scripts/remote/pull_artifacts.sh`

## Artefatos brutos locais

- `wifi-snapshot-20260429-014702-0300.tar.gz`
- `wifi-client-20260429-014716-0300.tar.gz`
- `wifi-client-20260429-014729-0300.tar.gz`

Esses `.tar.gz` contem dados sensiveis como SSIDs, BSSIDs, IPs, hostname, nomes de conexao e logs do NetworkManager. Nao devem ser commitados no repositorio publico.

## Resultado

- Snapshot Wi-Fi: executado com sucesso.
- Teste sem argumento: retornou `64`, esperado, e gerou artefato com instrucoes/conexoes conhecidas.
- Conexao testada: conexao Wi-Fi existente redigida.
- `wlan0` conectou: nao.
- `wlan0` recebeu IP: nao.
- Ping via `wlan0`: falhou, `4 packets transmitted, 0 received`.
- DNS: `getent hosts deb.debian.org` funcionou, mas isso nao comprova Wi-Fi porque a Ethernet permaneceu ativa.
- Ethernet: permaneceu conectada em `end0`.
- NetworkManager: falha de ativacao Wi-Fi por `ssid-not-found` apos tempo de associacao.

## Estado observado

Antes e depois do teste, `end0` permaneceu conectado e `wlan0` permaneceu desconectado/dormant. A rota default continuou pela Ethernet.

O log do NetworkManager indica que a conexao Wi-Fi salva tinha segredo existente (`psk` oculto), mas a rede alvo da conexao salva nao foi encontrada durante a tentativa de associacao. Nenhuma senha foi solicitada ou registrada pelo script.

## Itens criticos

Nos artefatos Wi-Fi inspecionados nao apareceram `Oops`, `kernel panic`, `EXT4-fs error`, `Aborting journal`, `Remounting filesystem read-only` ou `mmc timeout/reset`. Esta rodada nao incluiu coleta completa de `journalctl -k`; para auditoria de kernel, usar `collect_diag.sh` em uma etapa separada.

## Proxima acao sugerida

Criar ou validar previamente uma conexao NetworkManager para a rede de teste correta em bancada controlada, sem registrar senha em logs ou no repositorio. Depois repetir `wifi_snapshot.sh`, `wifi_client_test.sh "<conexao-existente>"` e puxar somente `wifi-*.tar.gz` para nova rodada.
