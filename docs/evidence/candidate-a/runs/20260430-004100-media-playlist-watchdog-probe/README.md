# Media playlist watchdog probe

Data: 2026-04-30

## Objetivo

Simular melhor a cadencia real do app, ainda sem iniciar `kiosk.py`:

- playlist completa com 5 midias;
- duracoes configuradas observadas pelo player;
- `loadfile` sequencial via MPV IPC;
- pings IPC concorrentes a cada 10s, simulando o watchdog;
- sem restart automatico nesta primeira versao.

Host usado: redigido.

Paths reais de midia: nao publicados.

## Aliases e duracoes

| Indice | Alias sanitizado | Duracao configurada |
| ---: | --- | ---: |
| 1 | `<media-path:fece6ae2c0>` | 5100 ms |
| 2 | `<media-path:89207012a7>` | 7000 ms |
| 3 | `<media-path:e7efe47f02>` | 10000 ms |
| 4 | `<media-path:8f9272521c>` | 8600 ms |
| 5 | `<media-path:c406539999>` | 15100 ms |

Alias suspeito:

- `media-c3a1e9fd9a` / `<media-path:e7efe47f02>`

## Validacao antes da rodada

| Comando | Resultado |
| --- | --- |
| `bash -n scripts/board/media_playlist_watchdog_probe.sh` | OK |
| `bash -n scripts/board/*.sh scripts/remote/*.sh` | OK, validado por loop arquivo a arquivo |
| `git diff --check` | OK |

## Artefatos analisados

Probe:

- `media-playlist-watchdog-20260430-003943-0300.tar.gz`

Diagnostico:

- `totem-diag-20260430-004046-0300.tar.gz`

Arquivos principais:

- `playlist-spec-public.tsv`
- `orchestrator-summary.tsv`
- `loadfile-results.tsv`
- `ping-results.tsv`
- `state-results.tsv`
- `mpv-playlist-watchdog.log`
- `post-systemctl-failed.stdout.txt`
- `post-journalctl-kernel-critical-filter.stdout.txt`

## Sumario do orquestrador

| Metrica | Valor |
| --- | ---: |
| Itens de playlist | 5 |
| `loadfile` success | 5 |
| `loadfile` timeout | 0 |
| `loadfile` outros erros | 0 |
| Ping success | 5 |
| Ping timeout | 0 |
| Ping outros erros | 0 |

## Resultado dos loadfiles

| Indice | Alias sanitizado | Duracao configurada | Exit code | Tempo IPC | Resposta IPC | Timeout IPC |
| ---: | --- | ---: | ---: | ---: | --- | --- |
| 1 | `<media-path:fece6ae2c0>` | 5100 ms | 0 | 801 ms | `success`, playlist entry 1 | Nao |
| 2 | `<media-path:89207012a7>` | 7000 ms | 0 | 1 ms | `success`, playlist entry 2 | Nao |
| 3 | `<media-path:e7efe47f02>` | 10000 ms | 0 | 3 ms | `success`, playlist entry 3 | Nao |
| 4 | `<media-path:8f9272521c>` | 8600 ms | 0 | 1 ms | `success`, playlist entry 4 | Nao |
| 5 | `<media-path:c406539999>` | 15100 ms | 0 | 1 ms | `success`, playlist entry 5 | Nao |

A midia suspeita nao falhou: o `loadfile` retornou `success` em 3 ms.

## Resultado dos pings concorrentes

| Seq | Fase registrada | Alias da fase | Tempo desde inicio | Exit code | Tempo IPC | Resultado |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 1 | `none` | `none` | 803 ms | 0 | 802 ms | `success=false` |
| 2 | item 2 | `<media-path:89207012a7>` | 10805 ms | 0 | 1 ms | `success=false` |
| 3 | item 3 | `<media-path:e7efe47f02>` | 20808 ms | 0 | 1 ms | `success=false` |
| 4 | item 4 | `<media-path:8f9272521c>` | 30810 ms | 0 | 1 ms | `success=false` |
| 5 | item 5 | `<media-path:c406539999>` | 40813 ms | 0 | 2 ms | `success=false` |

Nao houve timeout de ping. O primeiro ping coincidiu com o inicio do primeiro `loadfile` e levou 802 ms, mas respondeu com sucesso.

## Estado apos cada midia

| Indice | Alias sanitizado | Estado apos espera configurada |
| ---: | --- | --- |
| 1 | `<media-path:fece6ae2c0>` | `idle-active=true`; propriedades de tempo indisponiveis por idle |
| 2 | `<media-path:89207012a7>` | `idle-active=false`; `time-pos=6.866667`; `duration=16.064218`; `eof-reached=false` |
| 3 | `<media-path:e7efe47f02>` | `idle-active=false`; `time-pos=9.866667`; `duration=10.0`; `eof-reached=false` |
| 4 | `<media-path:8f9272521c>` | `idle-active=true`; propriedades de tempo indisponiveis por idle |
| 5 | `<media-path:c406539999>` | `idle-active=true`; propriedades de tempo indisponiveis por idle |

Observacao: o item 2 tem duracao real observada pelo MPV maior que a duracao configurada. Isso reforca que a cadencia do player pode forcar transicoes antes do EOF para algumas midias.

## Evidencia no log MPV

O log MPV mostrou abertura das cinco midias:

| Indice | Evidencia sanitizada |
| ---: | --- |
| 1 | `Opening done: <media-path:fece6ae2c0>`; video h264 480x704 24.000fps |
| 2 | `Opening done: <media-path:89207012a7>`; video h264 1080x1920 30.000fps |
| 3 | `Opening done: <media-path:e7efe47f02>`; video h264 1080x1920 30.000fps |
| 4 | `Opening done: <media-path:8f9272521c>`; video hevc 720x1280 24.000fps |
| 5 | `Opening done: <media-path:c406539999>`; video h264 480x848 30.000fps |

Ruido nao fatal observado:

- `Write error (Broken pipe)` e `Read error (Connection reset by peer)` em conexoes IPC fechadas pelo cliente.
- `DR failed - disabling`.
- `Failed to set up VT switcher`.

Esses eventos nao impediram os `loadfile` nem os pings: todos retornaram `success`.

## Systemd e kernel

`systemctl --failed` depois do probe:

```text
0 loaded units listed.
```

Filtro critico de kernel no artefato do probe:

- Sem linhas.

Filtro critico de kernel no diagnostico final:

- Sem linhas reais.

Nao houve evidencia de `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`.

## Observacao humana da tela

Pendente: registrar se a tela exibiu visualmente as cinco midias na ordem esperada.

## Interpretacao

Este probe ainda nao reproduziu os sintomas do app. Mesmo com playlist completa, duracoes configuradas e pings IPC concorrentes a cada 10s, nao houve timeout de ping nem timeout de `loadfile`.

A midia suspeita passou novamente. A diferenca relevante que ainda resta em relacao ao `kiosky-player` e a ausencia de restart automatico, estado interno do `playback_loop`, retries, contadores por geracao e a propria implementacao Python do controlador MPV do app.

## Recomendacao

Nao tratar a midia como causa isolada.

Proximo passo recomendado:

1. Instrumentar o `kiosky-player` para registrar, por geracao, timestamps relativos de `loadfile`, `watchdog.ping`, `ping timeout`, `restart` e `MPV process started`.
2. Registrar tambem a midia anterior e a proxima midia por alias sanitizado quando `loadfile` falhar.
3. Repetir uma rodada curta com a configuracao baseline mais promissora: coordenacao IPC/restart, `mpv_watchdog_ping_failures_before_restart=2`, `watchdog_interval_sec=10`, `mpv_ipc_timeout_sec=2.0`, `hwdec=auto-safe`, sem grace window fixa.
