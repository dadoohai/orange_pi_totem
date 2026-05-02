# C4 Wi-Fi hybrid human SSH run

Data: 2026-05-02

## Objetivo

Executar nova tentativa C4 em modelo hibrido/local, conforme C4.3, usando
canal humano SSH fora do Codex para qualquer etapa sensivel de Wi-Fi.

Codex ficou restrito a C3 antes/depois/final e a evidencia sanitizada. A etapa
sensivel foi executada fora do Codex pelo humano.

## Escopo

- Placa: desenvolvimento.
- Placa de homologacao: fora do escopo.
- Rede: teste, sem SSID real publicado.
- Senha: nao enviada ao Codex.
- Nome real de conexao: nao enviado ao Codex.
- Output bruto: nao enviado ao Codex.
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
ssh <dev-board> 'python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c4-hybrid-before'
ssh <dev-board> 'python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c4-hybrid-after'
ssh <dev-board> 'python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c4-hybrid-final'
```

Codex nao executou `nmcli connection add`, `nmcli connection up`,
`nmcli --ask`, `nmtui`, `nmcli connection down`, `nmcli connection delete` ou
qualquer outro comando mutavel de Wi-Fi.

## Respostas humanas sanitizadas

Resposta usada para a Fase B:

```text
Wi-Fi de teste conectado.
```

Resposta usada para a Fase D:

```text
Configuração de teste mantida por decisão humana.
```

## C3 before

Permissoes:

```text
700 /tmp/dadooh-c4-hybrid-before
600 /tmp/dadooh-c4-hybrid-before/status.json
600 /tmp/dadooh-c4-hybrid-before/summary.txt
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
700 /tmp/dadooh-c4-hybrid-after
600 /tmp/dadooh-c4-hybrid-after/status.json
600 /tmp/dadooh-c4-hybrid-after/summary.txt
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
700 /tmp/dadooh-c4-hybrid-final
600 /tmp/dadooh-c4-hybrid-final/status.json
600 /tmp/dadooh-c4-hybrid-final/summary.txt
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

## Resultado agregado

- Resposta humana sanitizada: Wi-Fi de teste conectado.
- C3 antes/depois/final manteve `ethernet_connected=true`.
- C3 antes/depois/final manteve `networkmanager_observed=true`.
- C3 antes/depois/final manteve `warnings=[]`.
- Internet e backend nao foram testados.
- SSID, senha, IP, gateway, hostname, MAC, BSSID, DNS real e nome real de
  conexao nao foram publicados.

## Estado final

Estado final informado pelo humano:

```text
Configuração de teste mantida por decisão humana.
```

Codex nao removeu perfil remotamente nesta rodada.

## Confirmacoes operacionais

- Codex nao recebeu senha.
- Codex nao recebeu SSID real.
- Codex nao recebeu nome real de conexao.
- Codex nao recebeu output bruto.
- Codex nao executou comando mutavel de Wi-Fi.
- Humano executou a etapa sensivel fora do Codex.
- Ethernet permaneceu preservada: `ethernet_connected=true` antes, depois e
  final.
- Nada foi escrito em `/data` pelos comandos executados pelo Codex.
- `/data/config/config.json` nao foi escrito pelos comandos executados pelo
  Codex.
- Launcher, renderer, `systemd` e `kiosky-player` nao foram alterados.
- Nenhum hotspot foi criado pelo Codex.
- Nenhum portal foi criado pelo Codex.
- Nenhum `apt` foi executado.
- Nenhum `ping`, `curl`, `wget` ou backend externo foi executado pelo Codex.
- Artefatos brutos remotos nao foram versionados.

## Privacidade

Nao foram publicados:

- output bruto;
- SSID real;
- senha;
- IP;
- gateway;
- hostname;
- MAC;
- BSSID;
- DNS real;
- nome real de conexao;
- URLs;
- secrets;
- payloads;
- paths privados.

## Conclusao

A rodada C4 hibrida com canal humano SSH fora do Codex passou no processo de
seguranca da credencial: Codex nao recebeu segredo nem executou comandos
mutaveis de Wi-Fi.

O resultado operacional informado pelo humano foi Wi-Fi de teste conectado, com
configuracao de teste mantida por decisao humana. Ethernet permaneceu
preservada nos tres snapshots C3.

## Proximos bloqueios

- Decidir quando a configuracao de teste devera ser removida ou promovida para
  fluxo controlado posterior.
- Manter internet/backend externo fora do escopo ate decisao separada.
- Se houver nova rodada, continuar usando apenas respostas humanas sanitizadas
  e C3 para evidencia agregada.
