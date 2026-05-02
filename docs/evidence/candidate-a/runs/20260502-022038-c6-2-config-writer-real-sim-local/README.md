# C6.2 config writer real simulado - local

Data: 2026-05-02

## Objetivo

Validar localmente C6.2: primeiro writer real reutilizavel, ainda em modo
simulado, com validacao C5.1 `real-dry-run`, escrita atomica, backup e rollback
somente em `/tmp`.

## Modo

- Modo: local/simulado.
- Placa: nao acessada.
- SSH: nao usado.
- Destino real `/data`: nao usado.
- Token real: nao usado.
- Backend/rede: nao acessados.

## Comandos rodados

```sh
python3 -m py_compile scripts/board/totem_config_writer_real.py
python3 scripts/board/totem_config_writer_real.py --help
python3 scripts/board/totem_config_writer_real.py --self-test
```

Candidata sintetica temporaria:

```sh
python3 - <<'PY'
# gerou /tmp/dadooh-c6-2-synthetic-candidate.json
# api_key sintetica criada com secrets.token_hex(24).upper()
# api_key nao impressa
PY
```

Rodada simulada:

```sh
python3 scripts/board/totem_config_writer_real.py \
  --candidate /tmp/dadooh-c6-2-synthetic-candidate.json \
  --dest /tmp/dadooh-c6-real-simulated/data/config/config.json \
  --backup-dir /tmp/dadooh-c6-real-simulated/backups \
  --out-dir /tmp/dadooh-c6-config-writer-real-sim
find /tmp/dadooh-c6-config-writer-real-sim -maxdepth 1 -type f -printf '%f\n' | sort
stat -c '%a %n' /tmp/dadooh-c6-config-writer-real-sim /tmp/dadooh-c6-config-writer-real-sim/*
stat -c '%a %n' /tmp/dadooh-c6-real-simulated/data/config/config.json
```

Inspecao sanitizada:

```sh
python3 - <<'PY'
# leu a api_key sintetica da candidata temporaria sob /tmp
# confirmou que ela nao aparece em writer-status.json nem summary.txt
PY
```

## Candidata sintetica nao-secret

A candidata temporaria foi criada em:

```text
/tmp/dadooh-c6-2-synthetic-candidate.json
```

Valores publicaveis usados:

- `api_url`: `https://api.sandbox.localhost/search`;
- `environment_id`: `ENVIRONMENT_ALPHA_001`;
- `station_id`: `STATION_ALPHA_001`;
- demais campos: conforme contrato C5.1.

O valor de `api_key` foi sintetico, gerado localmente, nao real e nao foi
impresso nesta evidencia.

## Destinos simulados

- Config ativa simulada:
  `/tmp/dadooh-c6-real-simulated/data/config/config.json`;
- Backup-dir simulado:
  `/tmp/dadooh-c6-real-simulated/backups`;
- Out-dir sanitizado:
  `/tmp/dadooh-c6-config-writer-real-sim`.

## Resultado self-test

```text
self-test: ok
```

Cobertura do self-test:

- candidata mock C5 falha em modo real;
- candidata sintetica passa;
- destino fora de `/tmp` falha;
- backup-dir fora de `/tmp` falha;
- candidata sob `/data` ou `/opt` falha;
- escrita atomica cria destino;
- backup e criado quando destino anterior existe;
- rollback restaura backup em falha simulada pos-escrita;
- summary/status nao contem a `api_key` sintetica;
- nenhum artefato gerado pelo self-test fica sob `/data`.

## Resultado da escrita simulada

Saida sanitizada:

```text
C6.2 simulated writer artifacts generated under /tmp/dadooh-c6-config-writer-real-sim
writer-status.json
summary.txt
write: passed
backup_created: false
rollback_attempted: false
```

Resumo sanitizado do status:

```text
result: passed
pre_write_valid: True
post_write_valid: True
api_key_present: True
placeholder_detected: False
active_config_mode: 600
backup_created: False
rollback_attempted: False
data_written: False
```

A rodada operacional nao tinha config simulada anterior, portanto nao criou
backup. Backup e rollback foram cobertos pelo self-test.

## Arquivos gerados em /tmp

Arquivos no out-dir:

```text
summary.txt
writer-status.json
```

Permissoes observadas:

```text
700 /tmp/dadooh-c6-config-writer-real-sim
600 /tmp/dadooh-c6-config-writer-real-sim/summary.txt
600 /tmp/dadooh-c6-config-writer-real-sim/writer-status.json
600 /tmp/dadooh-c6-real-simulated/data/config/config.json
```

## Privacidade

Confirmacoes:

- `api_key` sintetica nao apareceu em `summary.txt`;
- `api_key` sintetica nao apareceu em `writer-status.json`;
- writer registrou apenas `api_key_present=true` e
  `placeholder_detected=false`;
- candidata sintetica nao foi copiada para o out-dir;
- conteudo de backup nao foi copiado para evidencia;
- artefatos JSON de `/tmp` nao foram versionados;
- nenhum token real foi usado;
- nenhuma `api_url` privada foi usada ou publicada;
- nenhum `environment_id` real foi usado ou publicado;
- nenhum `station_id` real foi usado ou publicado.

Scan sanitizado:

```text
api-key-scan: ok
```

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

C6.2 local foi aprovado como writer real simulado:

- validacao C5.1 `real-dry-run` foi reutilizada;
- placeholders foram bloqueados;
- escrita atomica simulada passou;
- config ativa simulada foi gerada em `/tmp` com mode `600`;
- backup/rollback simulados foram cobertos por self-test;
- saidas foram sanitizadas;
- nada foi escrito em `/data`.

## Bloqueios antes de C6.3

- Dados reais por canal local privado, fora de Codex/Git/evidencia.
- Owner/group/mode reais definidos e validados.
- `/data/config` validado na placa de desenvolvimento.
- Decisao sobre servico/launcher antes da escrita real.
- Rollback real aprovado.
- Evidencia sanitizada aprovada.
