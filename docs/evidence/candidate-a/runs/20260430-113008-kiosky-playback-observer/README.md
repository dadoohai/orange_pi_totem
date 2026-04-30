# Kiosky playback observer

Data: 2026-04-30

## Objetivo

Observar a progressao real de playback durante o `kiosky-player` completo, ainda sem `systemd`, usando consultas MPV IPC externas em conexao curta e independente do `MPVController` do app.

Host usado: redigido.

Paths reais, URLs, API keys, identificadores privados, nomes de campanha e payloads privados: nao publicados.

## Codigo e config

`kiosky-player`: branch `appliance-v0.1`.

Commit deployado: `8c3b420 Add fresh IPC query probe option`.

Config privada confirmada antes da execucao, sem imprimir valores sensiveis:

| Campo | Resultado |
| --- | --- |
| `mpv_query_uses_fresh_ipc` | OK |
| `watchdog_interval_sec` | OK |
| `mpv_watchdog_ping_failures_before_restart` | OK |
| `mpv_watchdog_grace_after_load_sec` | OK |
| `mpv_watchdog_grace_after_restart_sec` | OK |
| `mpv_ipc_timeout_sec` | OK |
| `mpv_startup_timeout_sec` | OK |
| `hwdec` | OK |
| `mpv_log_file` | OK |
| `mpv_msg_level` | OK |
| `mpv_debug_events` | OK |
| owner `root:totem` | OK |
| mode `0640` | OK |

## Execucao

Scripts executados:

- `scripts/remote/deploy_kiosky_player.sh`
- `scripts/board/setup_runtime_tmp.sh`
- `scripts/board/kiosky_playback_observer_probe.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefatos novos analisados:

- `kiosky-playback-observer-20260430-112412-0300.tar.gz`
- `totem-diag-20260430-112959-0300.tar.gz`

`app-run`:

- Exit code: `124`.
- Interpretacao: timeout esperado do probe de 300 segundos.
- `app-run.stderr.txt`: 0 linhas.
- `app-run.stdout.txt`: 229 linhas.

Observacao: o pull amplo de `totem-diag-*.tar.gz` listou artefatos historicos da placa; a copia foi interrompida antes de transferir historico, e foi puxado somente o diagnostico novo desta rodada.

## Metricas MPV/IPC

| Metrica | Contagem |
| --- | ---: |
| `MPV IPC command timeout` | 0 |
| `MPV IPC ping failed` | 0 |
| `MPV IPC ping ok` | 30 |
| `MPV IPC unresponsive` | 0 |
| `Restarting MPV` | 0 |
| `MPV process started` | 1 |
| `Failed to load media` | 0 |
| `MPV loadfile returned error` | 0 |
| `MPV IPC fresh query ok` | 30 |
| `MPV IPC fresh query timeout` | 0 |
| `Bad file descriptor` | 0 |
| `Media load retry failed` | 0 |
| `Playing media` | 33 |

Observador externo:

| Metrica | Valor |
| --- | ---: |
| Amostras totais | 294 |
| IPC externo `success` | 291 |
| IPC externo `timeout` | 0 |
| IPC externo `error` | 3 |
| Aliases observados | 5 |

Os 3 erros do observador foram `missing_socket` em bordas de startup/shutdown, nao timeouts de MPV durante reproducao.

## Progressao por alias

| Alias sanitizado | Duracao configurada | Duration MPV | Time-pos inicial | Time-pos final | Time-pos avancou | Frame avancou | Pause true | Idle true | EOF true | Amostras |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | ---: |
| `media-95c1895f82` / `<media-path:fece6ae2c0>` | 5.100s | 5.132s | 0.000s | 0.042s | Nao | Nao | Nao | Nao | Nao | 35 |
| `media-cc8cc834f6` / `<media-path:89207012a7>` | 7.000s | 16.064s | 0.033s | 0.033s | Nao | Nao | Nao | Nao | Nao | 49 |
| `media-c3a1e9fd9a` / `<media-path:e7efe47f02>` | 10.000s | 10.000s | 0.467s | 9.067s | Sim | Sim | Nao | Nao | Nao | 63 |
| `media-402b5e6c8f` / `<media-path:8f9272521c>` | 8.600s | 8.568s | 0.042s | 0.042s | Nao | Nao | Nao | Nao | Nao | 54 |
| `media-63e22e276f` / `<media-path:c406539999>` | 15.100s | 15.070s | 0.033s | 0.033s | Nao | Nao | Nao | Nao | Nao | 90 |

Leituras adicionais:

- `estimated-frame-number` avancou apenas em `media-c3a1e9fd9a` / `<media-path:e7efe47f02>`, com delta maximo de 264 frames dentro de um segmento.
- Os quatro aliases restantes ficaram essencialmente no primeiro frame, embora `pause=false`, `idle-active=false` e `eof-reached=false`.
- `media-cc8cc834f6` / `<media-path:89207012a7>` tem divergencia forte: duracao configurada de 7.000s contra duration MPV de 16.064s.
- Nos demais aliases, a duracao configurada ficou proxima da duration observada pelo MPV.

## Observacao humana

Observacao informada para orientar esta rodada: mesmo com IPC estabilizado, as midias apareciam na tela, mas a maioria parecia estatica; apenas uma parecia reproduzir claramente como video.

Esta rodada confirma essa percepcao no nivel MPV: somente um alias teve progressao clara de tempo e frames.

## Interpretacao

O problema principal desta rodada nao e mais IPC, restart ou `loadfile`: esses indicadores ficaram zerados, com uma unica geracao MPV durante os 300s.

Quatro aliases nao apresentaram progressao real de `time-pos` nem de `estimated-frame-number` durante o app, apesar de o MPV nao estar pausado nem idle. Isso aponta para video efetivamente parado no inicio sob as opcoes usadas pelo app, ou para arquivos cujo conteudo/timeline se comporta como quadro estatico nesse caminho de reproducao.

Nao houve evidencia de "tempo avancando mas visual parecendo estatico" para a maioria das midias. A unica midia com tempo e frames avancando foi `media-c3a1e9fd9a` / `<media-path:e7efe47f02>`, que tambem e a que melhor explica a observacao de uma midia claramente animada.

A troca por duracao configurada tambem existe. Para `media-cc8cc834f6` / `<media-path:89207012a7>`, o app troca apos 7s configurados, enquanto o MPV reporta 16.064s de duration. Isso e uma divergencia real, mas nessa rodada essa midia tambem nao avancou de frame, entao a divergencia de duracao nao explica sozinha a aparencia estatica.

## Systemd, kernel e processos

`systemctl --failed` apos o probe e no diagnostico final:

```text
0 loaded units listed.
```

Filtro critico de kernel:

- Sem `Oops`.
- Sem `panic`.
- Sem erro EXT4.
- Sem remount read-only.
- Sem `mmc timeout/reset`.
- `journalctl -k -p crit`: sem entradas.
- O filtro amplo capturou apenas linhas de boot do tipo `Error applying setting, reverse things back` e governors thermal; sem criterio bloqueador.

Processos remanescentes:

- `post-processes-totem`: vazio.
- `post-processes-all`: somente self-match do `pgrep`, sem processo real remanescente de `kiosk.py` ou `mpv`.

Escrita em `/opt`:

- `post-opt-newer-marker`: vazio.

## Recomendacao

Proximo passo recomendado, sem `systemd`:

1. Rodar probe isolado das quatro midias sem progressao usando exatamente as opcoes MPV do app, incluindo perfil low-resource, `--correct-pts=no`, `--video-sync=audio`, `--framedrop=decoder+vo`, `--keep-open=yes` e `--loop-file=inf`.
2. Fazer A/B removendo primeiro `--correct-pts=no` ou desativando `low_resource_mode`, mantendo os mesmos arquivos e a mesma saida DRM/KMS.
3. Corrigir a politica de duracao para `media-cc8cc834f6` / `<media-path:89207012a7>` ou decidir explicitamente que a duracao configurada deve cortar antes do EOF real.
4. Manter `mpv_query_uses_fresh_ipc=true`, pois a estabilidade de IPC/watchdog se manteve nesta rodada.
