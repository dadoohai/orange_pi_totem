# Kiosky playback observer - explicit MPV output

Data: 2026-04-30

## Objetivo

Validar no `kiosky-player` real, ainda sem `systemd`, a configuracao candidata
derivada da matriz `20260430-125237-mpv-remaining-flags-matrix`:

```text
mpv_query_uses_fresh_ipc=true
mpv_vo=gpu
mpv_gpu_context=drm
mpv_ao=null
low_resource_mode=false
```

Host usado: redigido.

Paths reais, URLs, API keys, identificadores privados, nomes privados e payloads
privados: nao publicados.

## Checkout usado

- `kiosky-player`: `c71318a Add configurable MPV output flags`
- Branch local verificada: `appliance-v0.1`
- Worktree local do `kiosky-player`: limpo antes do deploy

O checkout contem suporte a:

- `mpv_vo`
- `mpv_gpu_context`
- `mpv_ao`
- `mpv_query_uses_fresh_ipc`

## Campos alterados/confirmados

A config privada foi atualizada sem imprimir o conteudo. Somente os campos
permitidos foram alterados/confirmados, mantendo os demais campos intactos.

| Campo | Valor esperado | Status |
| --- | --- | --- |
| `mpv_query_uses_fresh_ipc` | `true` | OK |
| `mpv_vo` | `gpu` | OK |
| `mpv_gpu_context` | `drm` | OK |
| `mpv_ao` | `null` | OK |
| `low_resource_mode` | `false` | OK |
| `watchdog_interval_sec` | `10` | OK |
| `mpv_watchdog_ping_failures_before_restart` | `2` | OK |
| `mpv_watchdog_grace_after_load_sec` | `0` | OK |
| `mpv_watchdog_grace_after_restart_sec` | `0` | OK |
| `mpv_ipc_timeout_sec` | `2.0` | OK |
| `mpv_startup_timeout_sec` | `10.0` | OK |
| `hwdec` | `auto-safe` | OK |
| `mpv_log_file` | `/tmp/kiosky/mpv.log` | OK |
| `mpv_msg_level` | `all=v` | OK |
| `mpv_debug_events` | `true` | OK |
| owner/mode | `root:totem`, `0640` | OK |

O log MPV confirmou a presenca de:

```text
--vo=gpu --gpu-context=drm --ao=null
```

## Execucao

Scripts executados:

- `scripts/remote/deploy_kiosky_player.sh`
- `scripts/board/setup_runtime_tmp.sh`
- `scripts/board/kiosky_playback_observer_probe.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefatos novos analisados:

- `kiosky-playback-observer-20260430-132611-0300.tar.gz`
- `totem-diag-20260430-133119-0300.tar.gz`

`app-run`:

- Exit code: `124`.
- Interpretacao: timeout esperado do probe de 300 segundos.
- `app-run.stderr.txt`: 0 linhas.
- `app-run.stdout.txt`: 229 linhas.

Status final sanitizado:

- `playback_state=playing`
- `playlist_size=5`
- `current_index=2`
- `mpv_running=true`
- `consecutive_failures=0`
- `blocked_media_count=0`
- `last_poll_error=null`
- `last_render_error=null`
- `black_screen_risk_reason=null`

## Metricas IPC/restart/loadfile

| Metrica | Valor |
| --- | ---: |
| `MPV IPC command timeout` | 0 |
| `MPV IPC ping failed` | 0 |
| `MPV IPC ping ok` | 30 |
| `MPV IPC fresh query ok` | 30 |
| `MPV IPC fresh query timeout` | 0 |
| `Restarting MPV` | 0 |
| `MPV process started` | 1 |
| `Failed to load media` | 0 |
| `MPV loadfile returned error` | 0 |
| `Bad file descriptor` | 0 |
| `Media load retry failed` | 0 |
| `Playing media` | 33 |

Observador externo:

| Metrica | Valor |
| --- | ---: |
| Amostras totais | 299 |
| IPC success | 297 |
| IPC timeout | 0 |
| IPC error | 2 |
| Aliases unicos | 5 |

Os dois erros do observador foram `missing_socket` no inicio do probe, antes da
disponibilidade do socket MPV. Nao houve timeout de IPC durante reproducao.

## Resultado por alias

| Alias | Duracao config | Duracao MPV | Time-pos inicial | Time-pos final | Time avancou | Frame inicial | Frame final | Frame avancou | Pause true | Idle true | EOF true | Amostras |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- | --- | ---: |
| `<media-path:fece6ae2c0>` | 5.100s | 5.131610s | 0.000000 | 4.875000 | Sim | 0 | 117 | Sim | Nao | Nao | Nao | 37 |
| `<media-path:89207012a7>` | 7.000s | 16.064218s | 0.000000 | 6.833333 | Sim | 0 | 205 | Sim | Nao | Nao | Nao | 49 |
| `<media-path:e7efe47f02>` | 10.000s | 10.000000s | 0.066667 | 9.866667 | Sim | 2 | 296 | Sim | Nao | Nao | Nao | 70 |
| `<media-path:8f9272521c>` | 8.600s | 8.568186s | 0.125000 | 8.250000 | Sim | 3 | 197 | Sim | Nao | Nao | Nao | 50 |
| `<media-path:c406539999>` | 15.100s | 15.069751s | 0.000000 | 14.733333 | Sim | 0 | 442 | Sim | Nao | Nao | Nao | 91 |

## Comparacao

| Alias | 20260430-113008 observer | 20260430-122532 low-resource off | 20260430-125237 V5 isolado | Esta rodada no app real |
| --- | --- | --- | --- | --- |
| `<media-path:fece6ae2c0>` | Nao avancou | Nao avancou | Nao testado | Avancou |
| `<media-path:89207012a7>` | Nao avancou | Nao avancou | Avancou | Avancou |
| `<media-path:e7efe47f02>` | Avancou | Avancou | Avancou | Avancou |
| `<media-path:8f9272521c>` | Nao avancou | Nao avancou | Avancou | Avancou |
| `<media-path:c406539999>` | Nao avancou | Nao avancou | Nao testado | Avancou |

Leitura:

- `mpv_query_uses_fresh_ipc=true` manteve IPC/watchdog/loadfile estaveis.
- `low_resource_mode=false` sozinho nao tinha resolvido na rodada anterior.
- A saida explicita `--vo=gpu --gpu-context=drm --ao=null` resolveu a falta de
  progressao observada nos aliases problematicos dentro do app real.
- A divergencia de duracao do alias `<media-path:89207012a7>` permanece:
  duracao configurada de 7.000s contra duration MPV de 16.064218s. Nesta rodada,
  porem, o tempo e os frames avancaram normalmente ate a troca configurada.

## Observacao humana de tela

Nao houve observacao humana direta da tela nesta rodada. A conclusao e baseada
no observer externo via IPC curto e nos logs sanitizados do app/MPV.

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
- O filtro amplo capturou apenas linhas de boot do tipo `Error applying setting,
  reverse things back` e registros de governors thermal; sem criterio bloqueador.

Processos remanescentes:

- `post-processes-totem`: vazio.
- Sem processo real remanescente de `kiosk.py` ou `mpv`.

Escrita em `/opt`:

- `post-opt-newer-marker`: vazio.

## Interpretacao

A configuracao candidata foi aprovada no observer curto do app real. Todos os
cinco aliases observados avancaram `time-pos` e `estimated-frame-number`, sem
pausa, idle ou EOF inesperado durante as janelas de reproducao.

O bloqueio visual anterior fica atribuido ao perfil de saida MPV nao explicito
no app. A menor mudanca candidata atual continua sendo manter:

```text
--vo=gpu --gpu-context=drm --ao=null
```

## Recomendacao

Proximo passo recomendado, sem liberar `systemd` ainda:

1. Rodar um teste manual mais longo do app real com a mesma configuracao.
2. Manter as mesmas metricas de aceite: IPC timeout 0, ping failed 0,
   restart 0, falha de load 0, todos os aliases avancando, `systemctl
   --failed=0` e filtro critico de kernel limpo.
3. Se o teste longo passar, preparar a rodada de validacao controlada da unit
   `systemd` da aplicacao.
