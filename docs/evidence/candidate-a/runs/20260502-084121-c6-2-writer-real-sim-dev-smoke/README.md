# C6.2.1 config writer real simulado - dev smoke

Data: 2026-05-02

## Objetivo

Validar C6.2.1 na placa de desenvolvimento: executar o writer real simulado no
ambiente real da Orange Pi, ainda somente em `/tmp`, sem token real, sem config
real e sem iniciar player.

## Escopo

- Placa: desenvolvimento, sem publicar IP ou hostname.
- Modo: simulado em `/tmp`.
- Scripts copiados somente para `/tmp`.
- Candidata sintetica nao-secret criada somente em `/tmp`.
- Config ativa simulada escrita somente em `/tmp`.
- Nenhum artefato JSON remoto foi versionado.

C6.2.1 nao e C6.3. C6.2.1 nao escreve `/data/config/config.json`.

## Comandos executados

Validacao local antes da placa:

```sh
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_config_writer_real.py --help
python3 scripts/board/totem_config_writer_real.py --self-test
```

Copias para a placa de desenvolvimento, com alvo sanitizado:

```sh
scp scripts/board/totem_config_contract_validate.py scripts/board/totem_config_writer_real.py <dev-board>:/tmp/
```

Self-tests na placa:

```sh
ssh <dev-board> 'cd /tmp && python3 /tmp/totem_config_contract_validate.py --self-test && python3 /tmp/totem_config_writer_real.py --self-test'
```

Criacao de candidata sintetica na placa:

```sh
ssh <dev-board> 'python3 - <<PY
# criou /tmp/dadooh-c6-2-dev-smoke/candidate.synthetic.json
# api_key sintetica criada localmente com secrets.token_hex(24).upper()
# api_key nao impressa
PY'
```

Writer simulado na placa:

```sh
ssh <dev-board> 'python3 /tmp/totem_config_writer_real.py \
  --candidate /tmp/dadooh-c6-2-dev-smoke/candidate.synthetic.json \
  --dest /tmp/dadooh-c6-2-dev-smoke/data/config/config.json \
  --backup-dir /tmp/dadooh-c6-2-dev-smoke/backups \
  --out-dir /tmp/dadooh-c6-2-dev-smoke/out'
```

Inspecoes somente em `/tmp`:

```sh
ssh <dev-board> 'find /tmp/dadooh-c6-2-dev-smoke/out -maxdepth 1 -type f -printf "%f\n" | sort'
ssh <dev-board> 'stat -c "%a %n" /tmp/dadooh-c6-2-dev-smoke/out /tmp/dadooh-c6-2-dev-smoke/out/*'
ssh <dev-board> 'stat -c "%a %n" /tmp/dadooh-c6-2-dev-smoke/data/config/config.json'
```

Inspecao sanitizada dos artefatos:

```sh
ssh <dev-board> 'python3 - <<PY
# verificou writer-status.json e summary.txt sem imprimir conteudo da config
# comparou a api_key sintetica local contra os artefatos sanitizados
PY'
```

## Self-tests

Resultado local:

```text
self-test: ok
self-test: ok
```

Resultado na placa:

```text
self-test: ok
self-test: ok
```

## Candidata sintetica nao-secret

A candidata temporaria foi criada na placa em:

```text
/tmp/dadooh-c6-2-dev-smoke/candidate.synthetic.json
```

Valores publicaveis:

- `api_url`: `https://api.sandbox.localhost/search`;
- `environment_id`: `ENVIRONMENT_ALPHA_001`;
- `station_id`: `STATION_ALPHA_001`;
- demais campos: conforme contrato C5.1.

O valor de `api_key` foi sintetico, gerado localmente na placa, nao real e nao
foi impresso nesta evidencia.

## Destinos simulados

- Config ativa simulada:
  `/tmp/dadooh-c6-2-dev-smoke/data/config/config.json`;
- Backup-dir simulado:
  `/tmp/dadooh-c6-2-dev-smoke/backups`;
- Out-dir:
  `/tmp/dadooh-c6-2-dev-smoke/out`.

## Resultado do writer

Saida sanitizada:

```text
C6.2 simulated writer artifacts generated under /tmp/dadooh-c6-2-dev-smoke/out
writer-status.json
summary.txt
write: passed
backup_created: false
rollback_attempted: false
```

Status sanitizado:

```text
result: passed
pre_write_valid: True
post_write_valid: True
api_key_present: True
placeholder_detected: False
candidate_config_copied_to_output: False
backup_content_copied_to_output: False
data_written: False
real_config_read: False
network_access: False
systemctl_called: False
nmcli_called: False
mpv_called: False
api-key-scan: ok
```

A rodada operacional nao tinha config simulada anterior, portanto nao criou
backup. Backup e rollback continuam cobertos pelo self-test do writer.

## Arquivos e permissoes

Arquivos no out-dir:

```text
summary.txt
writer-status.json
```

Permissoes observadas:

```text
700 /tmp/dadooh-c6-2-dev-smoke/out
600 /tmp/dadooh-c6-2-dev-smoke/out/summary.txt
600 /tmp/dadooh-c6-2-dev-smoke/out/writer-status.json
600 /tmp/dadooh-c6-2-dev-smoke/data/config/config.json
```

## Privacidade

Confirmacoes:

- `api_key` sintetica nao apareceu em `summary.txt`;
- `api_key` sintetica nao apareceu em `writer-status.json`;
- writer registrou apenas `api_key_present=true` e
  `placeholder_detected=false`;
- candidata sintetica nao foi copiada para o out-dir;
- conteudo de backup nao foi copiado para evidencia;
- conteudo da config simulada nao foi publicado;
- nenhum token real foi usado;
- nenhuma `api_url` privada foi usada ou publicada;
- nenhum `environment_id` real foi usado ou publicado;
- nenhum `station_id` real foi usado ou publicado;
- IP, hostname e credencial SSH nao foram publicados nesta evidencia.

## Confirmacoes operacionais

- Nada foi escrito em `/data`.
- `/data/config/config.json` nao foi lido.
- `/data/config/config.json` nao foi escrito.
- `/data/config` nao foi criado.
- Config real nao foi lida nem alterada.
- Launcher nao foi alterado.
- Renderer nao foi alterado.
- `systemd` nao foi alterado.
- `kiosky-player` nao foi alterado.
- NetworkManager nao foi alterado.
- `nmcli` nao foi executado.
- Nenhum comando de Wi-Fi, hotspot, portal, MPV ou backend foi executado.
- Nenhum pacote foi instalado.

## Conclusao

C6.2.1 foi aprovado como smoke test na placa de desenvolvimento:

- scripts C5.1/C6.2 rodaram em `/tmp`;
- self-tests na placa passaram;
- writer simulado passou;
- config ativa simulada foi criada em `/tmp` com mode `600`;
- saidas foram sanitizadas;
- nada foi escrito em `/data`.

## Bloqueios antes de C6.3

- Dados reais por canal local privado, fora de Codex/Git/evidencia.
- Owner/group/mode reais definidos e validados.
- `/data/config` validado na placa de desenvolvimento.
- Decisao sobre servico/launcher antes da escrita real.
- Rollback real aprovado.
- Evidencia sanitizada aprovada.
