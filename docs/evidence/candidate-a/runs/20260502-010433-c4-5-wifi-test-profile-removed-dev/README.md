# C4.5 Wi-Fi test profile removed

Data: 2026-05-02

## Objetivo

Registrar o fechamento pos-C4.2 depois da remocao local da configuracao Wi-Fi
de teste pelo humano, fora do Codex, e validar por diagnostico C3 read-only que
a placa segue saudavel.

## Contexto

- C4.2 conectou Wi-Fi de teste por humano fora do Codex.
- A configuracao de teste havia sido mantida por decisao humana.
- Agora o humano removeu localmente o perfil/configuracao de teste.
- Codex nao executou remocao de perfil.
- Codex nao executou comando mutavel de rede.

Resposta humana sanitizada:

```text
Perfil de teste removido.
```

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

Snapshot C3 final read-only:

```sh
ssh <dev-board> 'python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c4-5-wifi-removed-final'
```

Codex nao executou `nmcli connection up`, `nmcli connection down`,
`nmcli connection modify`, `nmcli connection delete`, `nmcli device
disconnect`, `nmtui` ou qualquer outro comando mutavel de rede.

## C3 final

Permissoes:

```text
700 /tmp/dadooh-c4-5-wifi-removed-final
600 /tmp/dadooh-c4-5-wifi-removed-final/status.json
600 /tmp/dadooh-c4-5-wifi-removed-final/summary.txt
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

## Confirmacoes operacionais

- Remocao do perfil/configuracao de teste foi informada pelo humano.
- Codex nao executou remocao.
- Codex nao executou comando mutavel de rede.
- Ethernet permaneceu preservada: `ethernet_connected=true`.
- NetworkManager foi observado: `networkmanager_observed=true`.
- C3 final manteve `warnings=[]`.
- Nada foi escrito em `/data` pelos comandos executados pelo Codex.
- `/data/config/config.json` nao foi escrito pelos comandos executados pelo
  Codex.
- Launcher, renderer, `systemd` e `kiosky-player` nao foram alterados.
- Internet/backend externo nao foram testados.
- Artefatos brutos remotos nao foram versionados.

## Privacidade

Nao foram publicados:

- status.json bruto;
- summary.txt bruto;
- saida bruta de `nmcli`, `ip` ou `iw`;
- lista de conexoes;
- nome real do perfil removido;
- SSID real;
- senha;
- IP;
- gateway;
- hostname;
- MAC;
- BSSID;
- DNS real;
- URLs;
- secrets;
- payloads;
- paths privados.

## Conclusao

O estado de teste Wi-Fi foi removido por acao humana local, fora do Codex. A
placa voltou a estado sem configuracao de teste intencional persistente,
conforme informado pelo humano.

O C3 final permaneceu saudavel: Ethernet preservada, NetworkManager observado,
warnings vazios e privacidade OK. Internet/backend continuam fora do escopo.
