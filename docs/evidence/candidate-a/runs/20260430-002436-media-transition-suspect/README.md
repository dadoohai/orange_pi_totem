# Media transition suspect probe

Data: 2026-04-30

## Objetivo

Executar um probe manual de transicao controlada, sem `kiosk.py`, usando uma unica instancia do MPV via IPC:

```text
controle bom -> suspeita -> controle bom
```

Host usado: redigido.

Paths reais de midia: nao publicados.

## Aliases usados

| Papel | Alias de midia | Path sanitizado | Tamanho | Tipo | Observacao |
| --- | --- | --- | ---: | --- | --- |
| Controle inicial | `media-cc8cc834f6` | `<media-path:89207012a7>` | 15197894 bytes | `.mp4` | Controle sem falhas de `loadfile` nas rodadas analisadas |
| Suspeita | `media-c3a1e9fd9a` | `<media-path:e7efe47f02>` | 1449280 bytes | `.mp4` | Alias que concentrou falhas anteriores de `loadfile` |
| Controle final | `media-402b5e6c8f` | `<media-path:8f9272521c>` | 752257 bytes | `.mp4` | Controle sem falhas de `loadfile` nas rodadas analisadas |

## Validacao antes da rodada

| Comando | Resultado |
| --- | --- |
| `bash -n scripts/board/media_transition_probe.sh` | OK |
| `bash -n scripts/board/*.sh scripts/remote/*.sh` | OK, validado por loop arquivo a arquivo |
| `git diff --check` | OK |

## Artefatos analisados

Probe:

- `media-transition-20260430-002339-0300.tar.gz`

Diagnostico:

- `totem-diag-20260430-002425-0300.tar.gz`

Arquivos principais:

- `summary.tsv`
- `loadfile-results.tsv`
- `state-results.tsv`
- `mpv-transition.log`
- `post-systemctl-failed.stdout.txt`
- `post-journalctl-kernel-critical-filter.stdout.txt`

## Resultado dos loadfiles

| Papel | Alias sanitizado | Exit code | Tempo IPC | Resposta IPC | Timeout IPC |
| --- | --- | ---: | ---: | --- | --- |
| Controle inicial | `<media-path:89207012a7>` | 0 | 817 ms | `success`, playlist entry 1 | Nao |
| Suspeita | `<media-path:e7efe47f02>` | 0 | 2 ms | `success`, playlist entry 2 | Nao |
| Controle final | `<media-path:8f9272521c>` | 0 | 1 ms | `success`, playlist entry 3 | Nao |

Todos os comandos IPC `loadfile` retornaram `success`. A falha anterior de `loadfile` do alias suspeito nao foi reproduzida neste probe manual.

## Estado apos cada etapa

| Papel | Estado apos espera | Leitura |
| --- | --- | --- |
| Controle inicial | `idle-active=false`, `time-pos=11.966667`, `duration=16.064218`, `eof-reached=false` | Ainda estava tocando apos 12s; a transicao para a suspeita foi forcada antes de EOF |
| Suspeita | `idle-active=true`; demais propriedades indisponiveis por idle | A midia terminou antes da consulta de estado apos 12s |
| Controle final | `idle-active=true`; demais propriedades indisponiveis por idle | A midia terminou antes da consulta de estado apos 12s |

Observacao: a espera fixa de 12s nao reproduz exatamente a cadencia configurada do `kiosky-player`. O controle inicial tem duracao real observada pelo MPV maior que a duracao configurada no player.

## Evidencia no log MPV

O log MPV mostrou abertura das tres midias:

| Papel | Evidencia sanitizada |
| --- | --- |
| Controle inicial | `Opening done: <media-path:89207012a7>`; video h264 1080x1920 30.000fps |
| Suspeita | `Opening done: <media-path:e7efe47f02>`; video h264 1080x1920 30.000fps |
| Controle final | `Opening done: <media-path:8f9272521c>`; video hevc 720x1280 24.000fps |

Ruido nao fatal observado:

- `Write error (Broken pipe)` / `Read error (Connection reset by peer)` em conexoes IPC fechadas pelo cliente ou no encerramento.
- `DR failed - disabling`.
- `Failed to set up VT switcher`.

Esses eventos nao impediram os `loadfile`: os tres comandos IPC retornaram `success`.

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

Pendente: registrar se a tela exibiu visualmente as tres midias na ordem esperada.

## Interpretacao

Este probe reforca que a midia suspeita nao falha simplesmente por ser carregada por `loadfile` via IPC depois de uma midia controle. O `loadfile` da suspeita respondeu em 2 ms com `success`, e o MPV abriu a midia no log.

A diferenca principal em relacao ao app continua sendo a ausencia de `playback_loop`, watchdog, restart, estado de playlist e pings concorrentes. Portanto, a investigacao deve voltar para a coordenacao temporal do app: `loadfile`, `watchdog.ping` e `restart`.

## Recomendacao

Nao tratar a midia como causa isolada.

Proximo teste recomendado, sem executar nesta rodada:

1. Criar um probe manual com cadencia real do app, usando as duracoes configuradas.
2. Adicionar pings IPC concorrentes durante as janelas de transicao para simular o watchdog.
3. Repetir a sequencia completa da playlist por alguns ciclos, ainda sem `kiosk.py`.
4. Se esse probe tambem passar, instrumentar o `kiosky-player` para correlacionar `watchdog.ping`, `loadfile` e `restart` por geracao.
