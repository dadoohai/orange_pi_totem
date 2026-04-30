# Media transition suspect probe

Data: 2026-04-30

## Objetivo

Testar manualmente uma transicao controlada, sem iniciar `kiosk.py`, usando uma unica instancia do MPV via IPC:

```text
midia controle inicial -> midia suspeita -> midia controle final
```

O objetivo era verificar se o alias suspeito falha quando carregado por `loadfile` depois de uma midia anterior conhecida como boa.

Host usado: redigido.

Paths reais de midia: nao publicados.

## Aliases usados

| Papel | Alias de midia | Path sanitizado | Tamanho | Tipo | Observacao |
| --- | --- | --- | ---: | --- | --- |
| Controle inicial | `media-cc8cc834f6` | `<media-path:89207012a7>` | 15197894 bytes | `.mp4` | Nao apareceu em `Failed to load media` nas rodadas analisadas |
| Suspeita | `media-c3a1e9fd9a` | `<media-path:e7efe47f02>` | 1449280 bytes | `.mp4` | Concentrou as falhas anteriores de `loadfile` |
| Controle final | `media-402b5e6c8f` | `<media-path:8f9272521c>` | 752257 bytes | `.mp4` | Nao apareceu em `Failed to load media` nas rodadas analisadas |

## Script usado

Script criado:

- `scripts/board/media_transition_probe.sh`

Validacoes locais antes da execucao:

| Comando | Resultado |
| --- | --- |
| `bash -n scripts/board/media_transition_probe.sh` | OK |
| `bash -n scripts/board/*.sh scripts/remote/*.sh` | OK, validado por loop arquivo a arquivo |
| `git diff --check` | OK |

O script:

- aceita exatamente 3 paths locais absolutos;
- rejeita argumento com `://`;
- rejeita path fora de `/data/media/kiosky-player`;
- cria `/tmp/kiosky` quando necessario;
- inicia MPV uma vez como usuario `totem`;
- usa `--idle=yes` e `--input-ipc-server=/tmp/kiosky/transition-mpv.sock`;
- envia `loadfile` sequencial via IPC;
- espera 12s depois de cada `loadfile`;
- registra tempo de resposta, exit code e resposta IPC;
- captura log MPV e gera `.tar.gz` em `/root/totem-diag`;
- nao inicia `kiosk.py`;
- nao altera config privada;
- nao altera cache/state do player.

## Artefatos analisados

Probe:

- `media-transition-20260430-001025-0300.tar.gz`

Diagnostico:

- `totem-diag-20260430-001118-0300.tar.gz`

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
| Controle inicial | `<media-path:89207012a7>` | 0 | 805 ms | `success`, playlist entry 1 | Nao |
| Suspeita | `<media-path:e7efe47f02>` | 0 | 3 ms | `success`, playlist entry 2 | Nao |
| Controle final | `<media-path:8f9272521c>` | 0 | 2 ms | `success`, playlist entry 3 | Nao |

Todos os `loadfile` retornaram `success`. A falha anterior de `loadfile` do alias suspeito nao foi reproduzida neste probe manual.

## Estado apos cada etapa

| Papel | Estado apos espera | Leitura |
| --- | --- | --- |
| Controle inicial | `idle-active=false`, `time-pos=11.966667`, `duration=16.064218`, `eof-reached=false` | Ainda estava tocando apos 12s; a transicao para o suspeito foi forcada antes de EOF |
| Suspeita | `idle-active=true`; demais propriedades indisponiveis por idle | A midia terminou antes da consulta de estado apos 12s |
| Controle final | `idle-active=true`; demais propriedades indisponiveis por idle | A midia terminou antes da consulta de estado apos 12s |

Observacao: o controle inicial tem duracao real observada pelo MPV maior que a duracao configurada no player. Esta rodada ainda e valida como teste de transicao forcada por IPC, mas nao reproduz exatamente a cadencia configurada do `kiosky-player`.

## Evidencia no log MPV

O log MPV mostrou abertura das tres midias:

| Papel | Evidencia sanitizada |
| --- | --- |
| Controle inicial | `Opening done: <media-path:89207012a7>`; video h264 1080x1920 30.000fps |
| Suspeita | `Opening done: <media-path:e7efe47f02>`; video h264 1080x1920 30.000fps |
| Controle final | `Opening done: <media-path:8f9272521c>`; video hevc 720x1280 24.000fps |

Ruido nao fatal observado:

- `Read error (Connection reset by peer)` em conexoes IPC que foram fechadas pelo cliente apos a resposta.
- `Write error (Broken pipe)` ao encerrar MPV via `quit`.
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

Este probe enfraquece a hipotese de que o alias suspeito falhe simplesmente por vir depois de uma midia boa e receber `loadfile` por IPC. A transicao manual `controle -> suspeita -> controle` passou, com resposta IPC rapida para o alias suspeito.

A diferenca principal em relacao ao app e que este probe nao executa `playback_loop`, watchdog, reinicios de MPV, estado de playlist, reuso do controlador Python do app nem os pings concorrentes. Portanto, a suspeita volta para a camada de coordenacao do app: concorrencia entre `loadfile`, watchdog, restart e temporizacao real da playlist.

## Recomendacao

Nao tratar a midia como causa isolada.

Proximo teste recomendado, sem executar nesta rodada:

1. Criar um probe manual com a cadencia real do app, usando as duracoes configuradas em vez de espera fixa de 12s.
2. Adicionar pings IPC concorrentes durante as janelas de transicao, simulando o watchdog.
3. Repetir a sequencia completa da playlist por alguns ciclos, ainda sem `kiosk.py`.
4. Se esse probe tambem passar, instrumentar o `kiosky-player` para registrar sobreposicao temporal entre `watchdog.ping`, `loadfile` e `restart` por geracao.
