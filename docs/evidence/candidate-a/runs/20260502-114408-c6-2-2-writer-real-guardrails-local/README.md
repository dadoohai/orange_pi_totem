# C6.2.2 writer real guardrails - local

Data: 2026-05-02

## Objetivo

Validar localmente C6.2.2: o writer continua seguro por padrao em `/tmp` e
passa a ter guardrails para modo real futuro, sem executar escrita em `/data`.

## Escopo

- Modo: local.
- Placa: nao acessada.
- SSH: nao usado.
- Escrita real: nao executada.
- `/data`: nao escrito.
- Token real: nao usado.
- Candidata real: nao usada.

## Comandos rodados

```sh
python3 scripts/board/totem_config_writer_real.py --help
python3 scripts/board/totem_config_writer_real.py --self-test
```

Candidata sintetica temporaria criada em `/tmp`, com `api_key` sintetica nao
impressa:

```sh
python3 - <<'PY'
# criou /tmp/dadooh-c6-2-2-private/candidate.synthetic.json
# api_key sintetica gerada localmente com secrets.token_hex(24).upper()
# api_key nao impressa
PY
```

Escrita simulada normal:

```sh
python3 scripts/board/totem_config_writer_real.py \
  --candidate /tmp/dadooh-c6-2-2-private/candidate.synthetic.json \
  --dest /tmp/dadooh-c6-2-2-real-guardrails-simulated/data/config/config.json \
  --backup-dir /tmp/dadooh-c6-2-2-real-guardrails-simulated/backups \
  --out-dir /tmp/dadooh-c6-2-2-real-guardrails-simulated/out
```

Inspecoes em `/tmp`:

```sh
find /tmp/dadooh-c6-2-2-real-guardrails-simulated/out -maxdepth 1 -type f -printf '%f\n' | sort
stat -c '%a %n' /tmp/dadooh-c6-2-2-real-guardrails-simulated/out /tmp/dadooh-c6-2-2-real-guardrails-simulated/out/*
stat -c '%a %n' /tmp/dadooh-c6-2-2-real-guardrails-simulated/data/config/config.json
```

Scan sanitizado:

```sh
python3 - <<'PY'
# comparou api_key sintetica contra writer-status.json e summary.txt
# nao imprimiu api_key
PY
```

## Self-test

Resultado:

```text
self-test: ok
```

Casos cobertos pelo self-test:

- sem `--enable-real-write`, destino `/data/config/config.json` falha;
- flags reais incompletas falham;
- com todas as flags, o path real aprovado e aceito apenas na validacao interna
  de guardrail;
- destino real diferente de `/data/config/config.json` falha;
- backup-dir real fora de `/data/config/backups` falha;
- candidata em repositorio falha, quando detectavel;
- candidata em `/data` falha;
- candidata em `/opt` falha;
- modo padrao em `/tmp` continua passando;
- backup e rollback simulados continuam cobertos;
- nada e escrito em `/data`.

## Escrita simulada em /tmp

Resultado:

```text
C6.2.2 guarded writer artifacts generated under /tmp/dadooh-c6-2-2-real-guardrails-simulated/out
writer-status.json
summary.txt
write: passed
backup_created: false
rollback_attempted: false
```

Arquivos no out-dir:

```text
summary.txt
writer-status.json
```

Permissoes observadas:

```text
700 /tmp/dadooh-c6-2-2-real-guardrails-simulated/out
600 /tmp/dadooh-c6-2-2-real-guardrails-simulated/out/summary.txt
600 /tmp/dadooh-c6-2-2-real-guardrails-simulated/out/writer-status.json
600 /tmp/dadooh-c6-2-2-real-guardrails-simulated/data/config/config.json
```

Scan:

```text
api-key-scan: ok
```

## Guardrails de modo real

C6.2.2 adiciona as flags:

- `--enable-real-write`;
- `--confirm-service-stopped`;
- `--confirm-human-approved-real-write`.

O self-test validou os guardrails de modo real sem chamar o fluxo operacional
de escrita real. O modo real nao foi executado.

## Privacidade

Confirmacoes:

- `api_key` sintetica nao foi impressa;
- `api_key` sintetica nao apareceu em `summary.txt`;
- `api_key` sintetica nao apareceu em `writer-status.json`;
- candidata sintetica nao foi copiada para o out-dir;
- backup nao foi copiado para evidencia;
- nenhum token real foi usado;
- nenhuma `api_url` real foi usada ou publicada;
- nenhum `environment_id` real foi usado ou publicado;
- nenhum `station_id` real foi usado ou publicado.

## Confirmacoes operacionais

- Nada foi escrito em `/data`.
- `/data/config/config.json` nao foi lido.
- `/data/config/config.json` nao foi escrito.
- `/data/config` nao foi criado.
- Config real nao foi lida nem alterada.
- Modo real nao foi executado.
- Launcher nao foi alterado.
- Renderer nao foi alterado.
- `systemd` nao foi alterado.
- `kiosky-player` nao foi alterado.
- NetworkManager nao foi alterado.
- `nmcli` nao foi executado.
- Nenhum comando de Wi-Fi, hotspot, portal, MPV ou backend foi executado.
- Nenhum pacote foi instalado.

## Conclusao

C6.2.2 passou localmente:

- comportamento padrao em `/tmp` preservado;
- flags reais aparecem no `--help`;
- self-test cobre guardrails sem escrever em `/data`;
- escrita simulada em `/tmp` passou;
- saidas permaneceram sanitizadas.

## Bloqueios antes de C6.3A

- aprovacao humana explicita para escrita real;
- placa de desenvolvimento confirmada;
- `kiosky-player.service` parado e verificado no prompt C6.3A;
- candidata real privada criada fora do Codex;
- token/`api_key` real fora do Codex;
- backup real em `/data/config/backups` aprovado;
- owner/group/mode reais validados;
- rollback real aprovado;
- evidencia sanitizada aprovada.
