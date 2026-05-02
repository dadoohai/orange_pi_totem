# C4.1 Wi-Fi controlled bench run - aborted safely

Data: 2026-05-01

## Objetivo

Executar a primeira rodada C4.1 de Wi-Fi real controlado em bancada na placa de
desenvolvimento, preservando Ethernet, evitando publicacao de dados sensiveis e
removendo o perfil de teste descartavel ao final.

Esta rodada foi abortada com seguranca antes de inserir senha. O perfil de
teste foi removido e a Ethernet permaneceu preservada.

## Escopo

- Placa: desenvolvimento.
- Placa de homologacao: fora do escopo.
- Rede: teste, sem SSID real publicado.
- Senha: nao inserida.
- Internet/backend externo: fora do escopo.
- Hotspot e portal: fora do escopo.
- Artefatos brutos remotos: nao versionados.

## Comandos executados

Comandos locais:

```sh
python3 scripts/board/totem_wifi_readonly_snapshot.py --help
python3 scripts/board/totem_wifi_readonly_snapshot.py --self-test
```

Preparacao remota com alvo sanitizado:

```sh
scp scripts/board/totem_wifi_readonly_snapshot.py <dev-board>:/tmp/totem_wifi_readonly_snapshot.py
ssh <dev-board> 'python3 /tmp/totem_wifi_readonly_snapshot.py --self-test'
ssh <dev-board> 'python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c4-wifi-before'
```

Comando mutavel executado com placeholders:

```sh
nmcli connection add type wifi ifname "*" con-name WIFI_TEST_CONNECTION_NAME ssid WIFI_TEST_SSID
```

Abortado antes de:

```sh
nmcli --ask connection up WIFI_TEST_CONNECTION_NAME
```

Motivo do aborto: o comando poderia solicitar senha e nao havia canal seguro
para inseri-la sem risco de registro em chat, terminal copiado, historico, log
ou evidencia.

Rollback executado:

```sh
nmcli connection delete WIFI_TEST_CONNECTION_NAME
```

Snapshot final:

```sh
ssh <dev-board> 'python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c4-wifi-final'
```

## C3 before

Permissoes:

```text
700 /tmp/dadooh-c4-wifi-before
600 /tmp/dadooh-c4-wifi-before/status.json
600 /tmp/dadooh-c4-wifi-before/summary.txt
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

Nao houve snapshot intermediario `after`, porque a rodada foi abortada antes de
inserir senha e antes de tentar conexao Wi-Fi.

## C3 final

Permissoes:

```text
700 /tmp/dadooh-c4-wifi-final
600 /tmp/dadooh-c4-wifi-final/status.json
600 /tmp/dadooh-c4-wifi-final/summary.txt
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

## Rollback

O perfil de teste criado nesta rodada foi removido pelo nome placeholder
`WIFI_TEST_CONNECTION_NAME`. Nenhuma conexao antiga foi removida ou modificada.
Ethernet nao foi alterada.

## Confirmacoes operacionais

- C4.1 foi abortada com seguranca antes de inserir senha.
- Senha nao foi inserida.
- Perfil de teste foi removido.
- Ethernet permaneceu preservada: `ethernet_connected=true` antes e final.
- NetworkManager foi observado: `networkmanager_observed=true` antes e final.
- Nada foi escrito em `/data`.
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

C4.1 nao concluiu teste de conexao Wi-Fi porque foi abortada corretamente antes
de qualquer insercao de credencial. A parte executada passou pelo rollback
esperado: o perfil descartavel foi removido e a Ethernet permaneceu preservada.

## Bloqueios remanescentes

- Definir um metodo seguro de insercao de senha que nao registre valor em
  comando, chat, historico, script, arquivo ou evidencia.
- Repetir C4.1 somente quando o metodo de segredo estiver aprovado.
- Manter internet/backend externo fora da proxima tentativa, salvo decisao
  separada.
