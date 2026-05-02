# C3 Wi-Fi readonly diagnostic - development board

Data: 2026-05-01

## Objetivo

Validar o diagnostico C3 Wi-Fi/read-only na placa de desenvolvimento antes de
qualquer C4. Esta rodada confirma que o script gera apenas estado agregado e
sanitizado, sem configurar Wi-Fi, sem alterar conexoes, sem criar hotspot, sem
testar internet/backend externo e sem escrever config real.

## Escopo

- Placa: desenvolvimento.
- Modo: read-only.
- Script copiado somente para `/tmp`.
- Saida gerada somente em `/tmp/dadooh-c3-wifi-readonly-dev`.
- Nenhum artefato bruto da placa foi adicionado ao repositorio.
- `status.json` e `summary.txt` remotos foram inspecionados, mas nao foram
  versionados.

## Comandos executados

Comandos locais antes da placa:

```sh
python3 scripts/board/totem_wifi_readonly_snapshot.py --help
python3 scripts/board/totem_wifi_readonly_snapshot.py --self-test
git status --short --untracked-files=all
```

Comandos na placa de desenvolvimento, com alvo sanitizado:

```sh
scp scripts/board/totem_wifi_readonly_snapshot.py <dev-board>:/tmp/totem_wifi_readonly_snapshot.py
ssh <dev-board> 'python3 /tmp/totem_wifi_readonly_snapshot.py --self-test'
ssh <dev-board> 'python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c3-wifi-readonly-dev'
ssh <dev-board> "find /tmp/dadooh-c3-wifi-readonly-dev -maxdepth 1 -type f -printf '%f\n' | sort"
ssh <dev-board> "stat -c '%a %n' /tmp/dadooh-c3-wifi-readonly-dev /tmp/dadooh-c3-wifi-readonly-dev/*"
```

Inspecao sanitizada adicional:

- scan local na placa por padroes de IP, MAC, URL, secrets e paths privados:
  `privacy-scan: ok`;
- leitura permitida dos campos agregados de `status.json`;
- verificacao de que `summary.txt` contem a linha de privacidade sobre omissao
  de saida bruta.

Nao foram executados manualmente `nmcli`, `ip` ou `iw`; essas leituras ficaram
restritas ao script C3 allowlisted.

## Resultado remoto

Self-test na placa:

```text
self-test: ok
```

Arquivos gerados:

```text
status.json
summary.txt
```

Permissoes observadas:

```text
700 /tmp/dadooh-c3-wifi-readonly-dev
600 /tmp/dadooh-c3-wifi-readonly-dev/status.json
600 /tmp/dadooh-c3-wifi-readonly-dev/summary.txt
```

Campos agregados permitidos:

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

## Privacidade

Inspecao de privacidade: aprovada.

Nao foram encontrados nos artefatos inspecionados:

- SSID real;
- senha;
- MAC;
- BSSID;
- IP real;
- gateway;
- hostname;
- nome de conexao NetworkManager;
- DNS real;
- URL privada;
- `api_key`;
- token;
- `environment_id` real;
- `station_id`;
- path real de midia;
- saida bruta de `nmcli`, `ip` ou `iw`.

## Confirmacoes operacionais

- Rodada permaneceu read-only.
- Nenhum comando mutavel de rede foi executado.
- Nenhum comando de `systemctl start/stop/restart/enable/disable` foi
  executado.
- Nenhum `apt` foi executado.
- Nenhum ping, curl, wget ou chamada HTTP externa foi executado.
- Nada foi escrito em `/data`.
- `/data/config/config.json` nao foi escrito.
- Launcher, renderer, `systemd` e `kiosky-player` nao foram alterados.

## Conclusao

C3 foi validado na placa de desenvolvimento com ferramentas de rede disponiveis
e sem warnings publicos. A rodada confirmou que o script publica somente estado
agregado e sanitizado, mantendo DNS, internet e backend como `not_checked`.

## Bloqueios antes de C4

- C4 precisa de plano humano separado antes de qualquer comando mutavel.
- Preservacao de Ethernet deve continuar como criterio obrigatorio.
- Rollback de NetworkManager deve ser documentado antes de conectar,
  desconectar, modificar ou criar perfis.
- Teste de internet/backend externo exige decisao propria, timeout e politica
  de privacidade.
- Evidencias de C4 nao podem publicar SSID, IP, gateway, hostname, nome de
  conexao, DNS real, secrets ou payloads.
