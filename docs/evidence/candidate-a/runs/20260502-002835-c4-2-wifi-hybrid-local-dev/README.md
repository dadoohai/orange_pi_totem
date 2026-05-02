# C4.2 Wi-Fi hybrid/local bench run - aborted before connection

Data: 2026-05-02

## Objetivo

Executar a rodada C4.2 em modelo hibrido/local para Wi-Fi controlado em
bancada, preservando Ethernet e mantendo qualquer credencial fora do Codex.

Esta rodada foi abortada antes da acao local porque nao havia terminal local
seguro para inserir credencial fora do Codex. Nenhuma tentativa de Wi-Fi foi
feita. Codex rodou apenas diagnosticos C3 read-only e registrou evidencia
sanitizada.

## Escopo

- Placa: desenvolvimento.
- Placa de homologacao: fora do escopo.
- Rede: teste, sem SSID real publicado.
- Senha: nao enviada ao Codex.
- Etapa sensivel: prevista para humano local, fora do agente.
- Internet/backend externo: fora do escopo.
- Hotspot e portal: fora do escopo.
- Artefatos brutos remotos: nao versionados.

## Comandos executados pelo Codex

Comandos locais:

```sh
python3 scripts/board/totem_wifi_readonly_snapshot.py --help
python3 scripts/board/totem_wifi_readonly_snapshot.py --self-test
```

Preparacao remota com alvo sanitizado:

```sh
scp scripts/board/totem_wifi_readonly_snapshot.py <dev-board>:/tmp/totem_wifi_readonly_snapshot.py
ssh <dev-board> 'python3 /tmp/totem_wifi_readonly_snapshot.py --self-test'
```

Snapshots C3 read-only:

```sh
ssh <dev-board> 'python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c4-2-wifi-before'
ssh <dev-board> 'python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c4-2-wifi-after'
ssh <dev-board> 'python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c4-2-wifi-final'
```

Verificacao read-only sanitizada do perfil placeholder:

```sh
ssh <dev-board> '<read-only check for WIFI_TEST_CONNECTION_NAME>'
```

Codex nao executou `nmcli --ask connection up`, nao recebeu senha, nao pediu
senha e nao executou comando que solicitasse senha Wi-Fi.

## Resposta humana sanitizada

Resposta usada para a Fase B:

```text
Abortado antes de conectar.
```

Confirmacao posterior do humano:

```text
Nenhum perfil de teste foi criado localmente.
```

Contexto operacional informado pelo humano:

```text
C4.2 foi abortado antes da acao local porque nao havia terminal local seguro para inserir credencial fora do Codex.
Nenhuma tentativa de Wi-Fi foi feita.
Player seguia em execucao.
Ethernet preservada.
Nada escrito em /data.
```

## C3 before

Permissoes:

```text
700 /tmp/dadooh-c4-2-wifi-before
600 /tmp/dadooh-c4-2-wifi-before/status.json
600 /tmp/dadooh-c4-2-wifi-before/summary.txt
```

Campos agregados:

| Campo | Valor |
| --- | --- |
| `schema_version` | `dadooh-c3-wifi-readonly.v1` |
| `nmcli_available` | `true` |
| `ip_available` | `true` |
| `iw_available` | `true` |
| `networkmanager_observed` | `true` |
| `ethernet_connected` | `true` |
| `wifi_device_count` | `1` |
| `wifi_connected` | `true` |
| `has_local_ip` | `true` |
| `has_default_route` | `true` |
| `dns_state` | `not_checked` |
| `internet_state` | `not_checked` |
| `backend_state` | `not_checked` |
| `warnings` | `[]` |

Privacidade: `privacy-scan-before: ok`.

## C3 after

Permissoes:

```text
700 /tmp/dadooh-c4-2-wifi-after
600 /tmp/dadooh-c4-2-wifi-after/status.json
600 /tmp/dadooh-c4-2-wifi-after/summary.txt
```

Campos agregados:

| Campo | Valor |
| --- | --- |
| `schema_version` | `dadooh-c3-wifi-readonly.v1` |
| `nmcli_available` | `true` |
| `ip_available` | `true` |
| `iw_available` | `true` |
| `networkmanager_observed` | `true` |
| `ethernet_connected` | `true` |
| `wifi_device_count` | `1` |
| `wifi_connected` | `true` |
| `has_local_ip` | `true` |
| `has_default_route` | `true` |
| `dns_state` | `not_checked` |
| `internet_state` | `not_checked` |
| `backend_state` | `not_checked` |
| `warnings` | `[]` |

Privacidade: `privacy-scan-after: ok`.

## C3 final

Permissoes:

```text
700 /tmp/dadooh-c4-2-wifi-final
600 /tmp/dadooh-c4-2-wifi-final/status.json
600 /tmp/dadooh-c4-2-wifi-final/summary.txt
```

Campos agregados:

| Campo | Valor |
| --- | --- |
| `schema_version` | `dadooh-c3-wifi-readonly.v1` |
| `nmcli_available` | `true` |
| `ip_available` | `true` |
| `iw_available` | `true` |
| `networkmanager_observed` | `true` |
| `ethernet_connected` | `true` |
| `wifi_device_count` | `1` |
| `wifi_connected` | `true` |
| `has_local_ip` | `true` |
| `has_default_route` | `true` |
| `dns_state` | `not_checked` |
| `internet_state` | `not_checked` |
| `backend_state` | `not_checked` |
| `warnings` | `[]` |

Privacidade: `privacy-scan-final: ok`.

## Perfil de teste

Nenhum perfil de teste foi criado localmente, conforme confirmacao humana
sanitizada.

Uma verificacao read-only sanitizada confirmou:

- `WIFI_TEST_CONNECTION_NAME` nao encontrado;
- `WIFI_TEST_CONNECTION_NAME` nao estava ativo;
- nenhuma lista de conexoes foi publicada;
- nenhum nome real de conexao foi publicado.

Codex nao removeu perfil remotamente nesta rodada.

## Confirmacoes operacionais

- C4.2 foi abortada antes de conectar Wi-Fi.
- A rodada foi abortada porque nao havia terminal local seguro para inserir
  credencial fora do Codex.
- Nenhuma tentativa de Wi-Fi foi feita.
- Codex nao recebeu senha.
- Codex nao pediu senha.
- Codex nao executou comando que solicitasse senha.
- Humano nao enviou SSID real, senha ou output bruto ao Codex.
- Player seguia em execucao, conforme confirmacao humana sanitizada.
- Ethernet permaneceu preservada: `ethernet_connected=true` antes, depois e
  final.
- NetworkManager foi observado: `networkmanager_observed=true` antes, depois e
  final.
- Nada foi escrito em `/data` pelos comandos executados pelo Codex.
- `/data/config/config.json` nao foi escrito.
- Launcher, renderer, `systemd` e `kiosky-player` nao foram alterados.
- Nenhum hotspot foi criado.
- Nenhum portal foi criado.
- Nenhum `apt` foi executado.
- Nenhum `ping`, `curl`, `wget` ou backend externo foi executado.
- Artefatos brutos remotos nao foram versionados.

## Privacidade

Nao foram publicados:

- SSID real;
- senha;
- IP;
- gateway;
- hostname;
- MAC;
- BSSID;
- DNS real;
- nome real de conexao;
- outputs brutos;
- URLs;
- secrets;
- payloads;
- paths privados.

## Conclusao

C4.2 abortou com seguranca antes da acao local porque nao havia terminal local
seguro para inserir credencial fora do Codex. Nenhuma tentativa de conexao
Wi-Fi foi feita. O modelo hibrido/local preservou a regra principal:
credencial nao passou pelo Codex.

A rodada validou novamente a coleta C3 antes/depois/final e preservou Ethernet.
Nao validou conexao Wi-Fi, senha correta/incorreta, internet, backend ou
persistencia apos reboot.

## Bloqueios remanescentes

- Repetir C4.2 somente quando o humano estiver pronto para executar localmente
  a etapa sensivel sem enviar segredo ou output bruto ao Codex.
- Manter internet/backend externo fora da proxima tentativa, salvo decisao
  separada.
- Confirmar localmente qualquer perfil de teste com nome real, se for usado em
  tentativa futura, sem publicar o nome.
