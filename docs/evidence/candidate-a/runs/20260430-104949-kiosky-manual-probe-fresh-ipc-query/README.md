# Kiosky manual probe - fresh IPC query

Data: 2026-04-30

## Objetivo

Executar um A/B curto do `kiosky-player` manual, ainda sem systemd da aplicacao, ativando apenas a opcao experimental `mpv_query_uses_fresh_ipc=true`. O objetivo era verificar se `ping()` e `get_property()` com uma conexao IPC curta por comando eliminam os timeouts observados quando essas consultas usam o socket persistente do `MPVController`.

Host usado: redigido.

Paths reais, URLs, API keys, identificadores privados, nomes de campanha e payloads privados: nao publicados.

## Codigo e config

Checkout local do `kiosky-player`: branch `appliance-v0.1`.

Commit deployado: `8c3b420 Add fresh IPC query probe option`.

Campos da config privada alterados nesta rodada, sem imprimir o conteudo do arquivo:

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
- `scripts/board/kiosky_manual_probe.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefatos novos principais analisados:

- `kiosky-manual-20260430-104316-0300.tar.gz`
- `totem-diag-20260430-104931-0300.tar.gz`

Observacao: o pull com `kiosky-manual-*.tar.gz` tambem copiou artefatos antigos ainda presentes em `/root/totem-diag`. A analise desta rodada usa somente os dois artefatos novos listados acima.

## Resultado do app

`app-run`:

- Exit code: `124`.
- Interpretacao: timeout esperado do probe de 300 segundos, com encerramento controlado ao final.
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
- `uptime_sec=298`

## Contagens MPV/IPC

| Metrica | Contagem |
| --- | ---: |
| `Bad file descriptor` | 0 |
| `MPV IPC command timeout` | 0 |
| `MPV IPC command send failed` | 0 |
| `MPV IPC unresponsive` | 0 |
| `MPV IPC ping failed` | 0 |
| `MPV IPC ping ok` | 30 |
| `MPV IPC fresh query begin` | 30 |
| `MPV IPC fresh query timeout` | 0 |
| `MPV IPC fresh query ok` | 30 |
| `Restarting MPV` | 0 |
| `MPV process started` | 1 |
| `Failed to load media` | 0 |
| `MPV loadfile returned error` | 0 |
| `Media load retry failed` | 0 |
| `Playing media` | 33 |

Leitura: a rodada eliminou os timeouts de comando, falhas de ping, restarts e falhas de `loadfile` observados nas rodadas anteriores, mantendo uma unica geracao MPV durante o probe.

## Logs MPV

- `mpv.log` pos-run: copiado sem imprimir conteudo bruto.
- Logs por geracao: 1 arquivo, `mpv-g001.log`.
- Total dos logs por geracao: 341777 bytes.
- O log MPV mostrou `loadfile` e abertura recorrente das 5 midias usando aliases sanitizados.
- Ruido recorrente nao fatal: `DR failed - disabling` e `Loading failed` em caminhos de aceleracao/fallback, sem impedir reproducao nem consultas IPC.

## Comparacao

| Metrica | 20260429-210204 IPC/restart coordination | 20260430-011115 MPVController playlist probe | Fresh IPC query |
| --- | ---: | ---: | ---: |
| `Bad file descriptor` | 0 | n/a | 0 |
| `MPV IPC command timeout` | 24 | n/a | 0 |
| `MPV IPC command send failed` | 0 | n/a | 0 |
| `MPV IPC unresponsive` | 11 | n/a | 0 |
| `MPV IPC ping failed` | 23 | n/a | 0 |
| `MPV IPC ping ok` | 1 | n/a | 30 |
| `MPV IPC fresh query ok` | n/a | n/a | 30 |
| `MPV IPC fresh query timeout` | n/a | n/a | 0 |
| `Restarting MPV` | 13 | 0 | 0 |
| `MPV process started` | 14 | 1 | 1 |
| `Failed to load media` | 2 | n/a | 0 |
| `MPV loadfile returned error` | 2 | n/a | 0 |
| `Media load retry failed` | 0 | n/a | 0 |
| `Playing media` | 30 | n/a | 33 |
| `load_file` success | n/a | 5 | sem falhas observadas |
| Ping timeout | n/a | 7 | 0 |
| State/get_property timeout | n/a | 20 | 0 observado no watchdog |

Comparacao qualitativa:

- Contra `20260429-210204`, a opcao fresh IPC query removeu o churn de watchdog: `Restarting MPV` caiu de 13 para 0 e `MPV process started` de 14 para 1.
- Contra `20260430-011115`, a hipotese foi confirmada: consultas por conexao curta responderam, enquanto o probe do controller com consulta no socket persistente tinha 7 timeouts de ping e 20 timeouts de estado.
- `load_file()` continuou usando o caminho persistente; nao houve falha de load nesta rodada.

## Escrita em /opt

A auditoria com marcador temporal nao encontrou escrita em `/opt/totem/kiosky-player` apos o inicio do app.

## Processos remanescentes

- `post-processes-totem`: vazio.
- `post-processes-all`: somente self-match do comando `pgrep`, sem processo real remanescente de `kiosk.py` ou `mpv`.

## Systemd e kernel

`systemctl --failed` apos o probe:

```text
0 loaded units listed.
```

`systemctl --failed` no diagnostico final:

```text
0 loaded units listed.
```

Filtro critico de kernel:

- Sem `Oops`.
- Sem `panic`.
- Sem erro EXT4.
- Sem remount read-only.
- Sem `mmc timeout/reset`.
- O filtro capturou linhas de boot do tipo `Error applying setting, reverse things back` e registros de governors thermal; nao houve criterio bloqueador da rodada.

## Observacao humana da tela

Nao realizada nesta rodada. A evidencia disponivel e por logs do app, status final, logs MPV e diagnostico do sistema.

## Recomendacao

A opcao `mpv_query_uses_fresh_ipc=true` deve ser mantida como candidata principal para estabilizar o watchdog. Proximo passo recomendado, sem executar nesta rodada:

1. Repetir um teste manual mais longo com a mesma configuracao para confirmar que os 0 timeouts de ping se sustentam por mais ciclos.
2. Se o teste longo mantiver `Restarting MPV=0`, `Failed to load media=0` e `systemctl --failed=0`, preparar a etapa seguinte de validacao manual antes de liberar systemd.
3. Manter `load_file()` no socket persistente por enquanto, ja que nao houve falha de load nesta rodada.
