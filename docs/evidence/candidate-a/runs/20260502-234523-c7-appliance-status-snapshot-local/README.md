# C7.0 - appliance status snapshot local/offline

Data: 2026-05-02

## Objetivo

Validar localmente o contrato e o script C7.0 de diagnostico/status sanitizado
do appliance, sem placa e sem acoes operacionais.

## Modo local/offline

Esta rodada foi executada somente no checkout local.

Nao houve:

- SSH;
- acesso a placa;
- comando remoto;
- `systemctl`;
- `journalctl`;
- `nmcli`;
- start/stop/restart de servico;
- observer em placa;
- leitura de config real;
- escrita em `/data`;
- acesso a rede.

## Fixtures sinteticas

O `--self-test` criou fixtures sinteticas sob `/tmp`, incluindo casos com
valores privados em campos desconhecidos e valores suspeitos em campos
allowlisted.

Ao final do self-test, foi deixada uma fixture sanitizada para execucao manual:

```text
/tmp/dadooh-c7-selftest-root
```

Essa fixture contem status publico sintetico, status de player sintetico e um
arquivo de config fixture usado somente por metadados. O conteudo desse arquivo
nao foi lido pelo snapshot.

## Comandos rodados

```sh
python3 -m py_compile scripts/board/totem_appliance_status_snapshot.py
python3 scripts/board/totem_appliance_status_snapshot.py --help
python3 scripts/board/totem_appliance_status_snapshot.py --self-test
python3 scripts/board/totem_appliance_status_snapshot.py --root /tmp/dadooh-c7-selftest-root --out-dir /tmp/dadooh-c7-appliance-status
find /tmp/dadooh-c7-appliance-status -maxdepth 1 -type f -printf '%f\n' | sort
stat -c '%a %n' /tmp/dadooh-c7-appliance-status /tmp/dadooh-c7-appliance-status/*
```

## Arquivos gerados em /tmp

```text
/tmp/dadooh-c7-appliance-status/appliance-status.json
/tmp/dadooh-c7-appliance-status/summary.txt
```

Os JSONs e summaries gerados em `/tmp` nao foram versionados.

## Permissoes

Resultado observado:

```text
700 /tmp/dadooh-c7-appliance-status
600 /tmp/dadooh-c7-appliance-status/appliance-status.json
600 /tmp/dadooh-c7-appliance-status/summary.txt
```

## Resultado do snapshot

Resultado agregado da fixture sanitizada:

- `privacy_scan`: `ok`;
- status publico: presente;
- status do player: presente;
- metadados de config: presentes;
- `public_state`: `player_running`;
- `public_config_state`: `valid`;
- `public_player_state`: `running`;
- `public_service_state`: `active`;
- `playback_state`: `playing`;
- `mpv_running`: `true`;
- `playlist_size_present`: `true`;
- `current_index_present`: `true`;
- `last_poll_success_present`: `true`;
- `config_file_exists`: `true`;
- `config_file_content_read`: `false`;
- `service_observed`: `unknown`;
- `renderer_active`: `unknown`;
- `kiosk_active`: `unknown`;
- `mpv_process_count`: `unknown`;
- warnings: nenhuma.

## Self-test

O self-test passou.

Casos cobertos:

- status publico limpo;
- status do player limpo;
- status bruto com valores privados em campos desconhecidos;
- campo allowlisted com valor suspeito;
- metadados de config sem abrir conteudo;
- out-dir fora de `/tmp` recusado;
- fontes ausentes gerando `unavailable`/`unknown`.

## Sanitizacao

Nenhum valor privado foi publicado nesta evidencia.

O self-test verificou que valores privados em campos desconhecidos nao aparecem
na saida. Quando valor allowlisted suspeito foi injetado, o snapshot marcou
`privacy_scan=failed` e manteve a saida sanitizada.

## Config

`config_file_content_read=false`.

O script usa metadados do arquivo de config relativo ao `--root` e nao abre seu
conteudo. Nesta rodada, o `--root` apontou para fixture em `/tmp`, nao para a
raiz real do sistema.

## Conclusao

C7.0 passou localmente como contrato + snapshot offline. A implementacao gera
artefatos restritos em `/tmp`, usa allowlist, nao copia status bruto completo,
nao le config real e trata fontes ausentes como estado desconhecido ou
indisponivel.

Esta rodada nao e homologacao, nao toca placa e nao substitui observer
prolongado.

## Proximos passos para C7.1

- Revisao humana do contrato C7.0 e do script.
- Definir roteiro C7.1 read-only em placa antes de qualquer execucao.
- Se processos forem observados em C7.1, publicar apenas contagens/booleanos
  sanitizados.
- Se `systemd` for observado em fase futura, usar somente campos allowlisted e
  nunca publicar journal bruto.
- Manter config real, backups, logs brutos e status bruto completo fora de
  evidencias.
