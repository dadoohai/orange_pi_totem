# MPVController playlist probe

Data: 2026-04-30

## Objetivo

Executar a mesma playlist de 5 midias da rodada `media_playlist_watchdog_probe`, mas usando o `MPVController` real do `kiosky-player`, sem iniciar o `main` de `kiosk.py`, sem API, sem systemd da aplicacao e sem alterar cache/state.

Host usado: redigido.

Paths reais de midia: nao publicados.

## Codigo usado

`kiosky-player`: branch `appliance-v0.1`, commit `719ceb6 Add MPV watchdog grace windows`.

Confirmado no checkout local antes do deploy:

- coordenacao IPC/restart presente;
- `mpv_watchdog_ping_failures_before_restart` presente;
- reset do contador por geracao presente;
- logs MPV por geracao presentes;
- grace window presente.

## Aliases e duracoes

| Indice | Alias sanitizado | Duracao configurada |
| ---: | --- | ---: |
| 1 | `<media-path:fece6ae2c0>` | 5100 ms |
| 2 | `<media-path:89207012a7>` | 7000 ms |
| 3 | `<media-path:e7efe47f02>` | 10000 ms |
| 4 | `<media-path:8f9272521c>` | 8600 ms |
| 5 | `<media-path:c406539999>` | 15100 ms |

## Validacao local antes da rodada

| Comando | Resultado |
| --- | --- |
| `bash -n scripts/board/mpv_controller_playlist_probe.sh` | OK |
| `bash -n scripts/board/*.sh scripts/remote/*.sh` | OK |
| `git diff --check` | OK |

## Artefatos analisados

- `mpv-controller-playlist-20260430-010826-0300.tar.gz`
- `totem-diag-20260430-011040-0300.tar.gz`

Arquivos principais:

- `summary.tsv`
- `loadfile-results.tsv`
- `ping-results.tsv`
- `state-results.tsv`
- `controller-probe.stdout.txt`
- `controller-probe.stderr.txt`
- `mpv-controller-probe.log`
- `mpv-current.log`
- `mpv-generation-logs/controller-probe-mpv-g001.log`
- `post-systemctl-failed.stdout.txt`
- `post-journalctl-kernel-critical-filter.stdout.txt`

## Sumario

| Metrica | Valor |
| --- | ---: |
| Itens de playlist | 5 |
| `load_file` success | 5 |
| `load_file` timeout | 0 |
| `load_file` error | 0 |
| Ping success | 1 |
| Ping timeout | 7 |
| Ping error | 0 |
| State success | 0 |
| State timeout | 20 |
| State error | 0 |
| Excecoes do probe | 0 |
| Restart count | 0 |
| Geracao inicial/final | 1 / 1 |
| PID inicial/final | 66867 / 66867 |
| MPV rodando antes do stop | Sim |
| Logs MPV por geracao | 1 |

## Resultado dos load_file

| Indice | Alias sanitizado | Duracao configurada | Resultado | Tempo |
| ---: | --- | ---: | --- | ---: |
| 1 | `<media-path:fece6ae2c0>` | 5100 ms | success | 4 ms |
| 2 | `<media-path:89207012a7>` | 7000 ms | success | 7 ms |
| 3 | `<media-path:e7efe47f02>` | 10000 ms | success | 8 ms |
| 4 | `<media-path:8f9272521c>` | 8600 ms | success | 6 ms |
| 5 | `<media-path:c406539999>` | 15100 ms | success | 39 ms |

Todos os `load_file()` foram executados na geracao 1, PID 66867, com `current_log_file=controller-probe-mpv-g001.log`.

## Resultado dos pings

| Seq | Fase | Resultado | Tempo |
| ---: | --- | --- | ---: |
| 1 | `none` | success | 5 ms |
| 2 | item 1 | timeout | 3121 ms |
| 3 | item 2 | timeout | 3021 ms |
| 4 | item 3 | timeout | 2005 ms |
| 5 | item 3 | timeout | 2032 ms |
| 6 | item 4 | timeout | 2005 ms |
| 7 | item 5 | timeout | 2005 ms |
| 8 | item 5 | timeout | 2005 ms |

Nao houve restart automatico quando o ping falhou. A geracao e o PID permaneceram constantes.

## Estado via MPVController

As leituras de `idle-active`, `time-pos`, `duration` e `eof-reached` apos cada item totalizaram 20 chamadas. Todas deram timeout via `MPVController.get_property()`.

## Evidencia MPV

O log MPV mostrou abertura das 5 midias, todas na mesma geracao. Evidencia sanitizada:

| Indice | Evidencia |
| ---: | --- |
| 1 | `Opening done: <media-path:fece6ae2c0>`; h264 480x704 24.000fps |
| 2 | `Opening done: <media-path:89207012a7>`; h264 1080x1920 30.000fps |
| 3 | `Opening done: <media-path:e7efe47f02>`; h264 1080x1920 30.000fps |
| 4 | `Opening done: <media-path:8f9272521c>`; hevc 720x1280 24.000fps |
| 5 | `Opening done: <media-path:c406539999>`; h264 480x848 30.000fps |

Ruido nao fatal observado no log MPV:

- `DR failed - disabling`.
- `Loading failed` em tentativas de suporte grafico/decoding, com fallback posterior.

## Systemd e kernel

`systemctl --failed` apos o probe:

```text
0 loaded units listed.
```

Filtro critico de kernel no artefato do probe:

- Sem linhas.

Filtro critico de kernel no diagnostico final:

- Sem linhas reais.

Nao houve evidencia de `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`.

## Observacao humana da tela

Nao realizada nesta rodada. A evidencia disponivel e por retorno do `MPVController`, logs do controller, logs MPV e diagnostico do sistema.

## Comparacao com media_playlist_watchdog_probe

Na rodada `20260430-004100-media-playlist-watchdog-probe`, o controle manual de IPC com uma conexao nova por comando teve:

- `loadfile` success: 5;
- `loadfile` timeout: 0;
- ping success: 5;
- ping timeout: 0.

Nesta rodada com `MPVController` real:

- `load_file` success: 5;
- `load_file` timeout: 0;
- ping success: 1;
- ping timeout: 7;
- state timeout: 20;
- restart: 0.

A diferenca forte e o uso do controlador real com socket persistente, `_send()`, `_recv_response()`, `request_id`, buffer interno e lock do controller. A midia suspeita continuou abrindo com sucesso.

## Interpretacao

O problema foi reproduzido parcialmente dentro do `MPVController` real: nao como falha de `load_file`, mas como perda de responsividade para `ping()` e `get_property()` apos o inicio da reproducao. Isso desloca o foco para a implementacao de IPC do controller, especialmente socket persistente, `_recv_response()`, descarte de eventos/respostas, `request_id`, buffer e timeout.

Como nao houve restart nesta rodada, a camada de restart/watchdog nao foi necessaria para produzir os timeouts de ping. No app completo, esses timeouts provavelmente viram churn porque o watchdog interpreta `ping()` falso como IPC unresponsive.

## Recomendacao

Proximo passo recomendado, sem executar nesta rodada:

1. Instrumentar `MPVController._recv_response()` para registrar contadores sanitizados de linhas descartadas, eventos sem `request_id`, respostas com `request_id` diferente e tamanho do buffer.
2. Fazer um A/B pequeno no controller: ping/get_property usando conexao IPC curta por comando versus socket persistente atual.
3. Se a conexao curta resolver pings sem quebrar `load_file`, ajustar `ping()` ou `_send()` para isolar comandos de watchdog do socket persistente usado pelo playback.
