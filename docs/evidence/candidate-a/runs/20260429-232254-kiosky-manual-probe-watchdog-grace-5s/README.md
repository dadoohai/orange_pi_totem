# Rodada 20260429-232254 - kiosky-player manual probe com watchdog grace 5s

Status: teste manual curto A/B do `kiosky-player` concluido como usuario `totem`, ainda sem systemd da aplicacao.

## Objetivo

Testar uma janela moderada de graca do watchdog durante transicoes do MPV: 5 segundos apos `loadfile` e 5 segundos apos start/restart. A intencao era reduzir falsos positivos do watchdog durante transicoes, sem adotar `watchdog_interval_sec=17` como solucao final.

## Codigo e config

Checkout local do `kiosky-player`: branch `appliance-v0.1`.

Commit deployado: `719ceb6 Add MPV watchdog grace windows`.

Confirmacao da config privada, sem imprimir conteudo do arquivo:

- `watchdog_interval_sec`: OK, baseline desta rodada.
- `mpv_watchdog_ping_failures_before_restart`: OK.
- `mpv_watchdog_grace_after_load_sec`: OK, variante 5s desta rodada.
- `mpv_watchdog_grace_after_restart_sec`: OK, variante 5s desta rodada.
- `mpv_ipc_timeout_sec`: OK.
- `mpv_startup_timeout_sec`: OK.
- `hwdec`: OK.
- `mpv_log_file`: OK.
- `mpv_msg_level`: OK.
- `mpv_debug_events`: OK.
- Permissoes: `root:totem`, modo `0640`, OK.

Nenhum segredo, URL privada, identificador privado, nome de campanha ou payload privado foi publicado.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts executados:

- `scripts/remote/deploy_kiosky_player.sh`
- `scripts/board/setup_runtime_tmp.sh`
- `scripts/board/kiosky_manual_probe.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefatos brutos principais analisados:

- `kiosky-manual-20260429-231738-0300.tar.gz`
- `totem-diag-20260429-232250-0300.tar.gz`

O pull com padroes amplos tambem copiou artefatos antigos ainda presentes em `/root/totem-diag`. A analise desta rodada usa somente os dois artefatos acima.

Os arquivos `.tar.gz` e `extracted/` sao evidencia bruta e nao devem ser commitados no repositorio publico.

## Resultado do app

Comando auditado pelo probe:

```text
runuser -u totem -- env PYTHONDONTWRITEBYTECODE=1 XDG_RUNTIME_DIR=/tmp/kiosky timeout 300s python3 /opt/totem/kiosky-player/kiosk.py --config /data/config/config.json
```

Resultado:

- `app-run` retornou exit code `124`.
- Interpretacao: timeout esperado do probe de 300 segundos, com encerramento controlado ao final.
- `app-run.stderr.txt`: 0 bytes.
- `app-run.stdout.txt`: 52.251 bytes.
- `Playing media`: 30 linhas.
- Status final sanitizado:
  - `playback_state=playing`
  - `playlist_size=5`
  - `mpv_running=true`
  - `consecutive_failures=0`
  - `blocked_media_count=0`
  - `last_poll_error=null`
  - `last_render_error=null`

Observacao humana de tela:

- Midia fisicamente visivel na tela: pendente de observacao humana.
- Tela preta ou retorno ao terminal: pendente de observacao humana.

## Contagens MPV/IPC

Contagens desta rodada:

- `Bad file descriptor`: 0.
- `MPV IPC command timeout`: 30.
- `MPV IPC command send failed`: 0.
- `MPV IPC unresponsive`: 5.
- `MPV IPC ping failed`: 24, contando a linha original `MPV IPC ping failed generation=`.
- `MPV IPC ping ok`: 1.
- `MPV IPC ping failed below restart threshold`: 7.
- `restart suppressed reason=within_grace_after_load`: 12.
- `restart suppressed reason=within_grace_after_restart`: 0.
- `Restarting MPV`: 11.
- `MPV process started`: 12.
- `Failed to load media`: 6.
- `MPV loadfile returned error`: 6.
- `Media load retry failed`: 0.
- `Playing media`: 30.

Contagens auxiliares:

- `Restarting MPV reason=ipc_unresponsive`: 5.
- `Restarting MPV reason=media_load_failed`: 6.
- `MPV IPC startup wait complete`: 12/12.
- `MPV loadfile result`: 30 sucessos.
- `MPV watchdog grace window expired`: 6.

Distribuicao sanitizada:

- `Playing media`: 5 aliases sanitizados, 6 ocorrencias cada.
- Falhas de load: 6 ocorrencias em 1 alias sanitizado.

## Comparacao

| Metrica | 20260429-210204 coord. IPC/restart | 20260429-224248 watchdog 17s | Grace 5s |
| --- | ---: | ---: | ---: |
| `Bad file descriptor` | 0 | 0 | 0 |
| `MPV IPC command timeout` | 24 | 19 | 30 |
| `MPV IPC command send failed` | 0 | 0 | 0 |
| `MPV IPC unresponsive` | 11 | 6 | 5 |
| `MPV IPC ping failed` | 23 | 15 | 24 |
| `MPV IPC ping ok` | 1 | 1 | 1 |
| `MPV IPC ping failed below restart threshold` | 12 | 9 | 7 |
| `restart suppressed reason=within_grace_after_load` | 0* | 0* | 12 |
| `restart suppressed reason=within_grace_after_restart` | 0* | 0* | 0 |
| `Restarting MPV` | 13 | 11 | 11 |
| `MPV process started` | 14 | 12 | 12 |
| `Failed to load media` | 2 | 5 | 6 |
| `MPV loadfile returned error` | 2 | 5 | 6 |
| `Media load retry failed` | 0 | 0 | 0 |
| `Playing media` | 30 | 30 | 30 |

`*` As rodadas de comparacao nao tinham a instrumentacao de grace window; a contagem e tratada como 0 porque a mensagem nao existia.

Leitura:

- A nova politica atuou: houve 12 pings falhos com restart suprimido dentro da janela apos `loadfile`.
- Nao houve supressao pela janela apos restart/start.
- O resultado nao e melhora geral. `MPV IPC unresponsive` caiu para 5 e `Restarting MPV` ficou em 11, mas `MPV IPC command timeout` subiu para 30 e `Failed to load media` subiu para 6.
- A rodada reforca que suprimir restart durante transicao reduz parte do churn, mas pode deixar o IPC degradado tempo suficiente para piorar `loadfile`.

## Logs MPV por geracao

Captura do probe:

- `pre-existing-mpv.log`: presente, 42.965 bytes, copiado sem imprimir conteudo.
- `pre-existing-mpv-generation-logs`: 19 arquivos listados como pre-existentes.
- `mpv.log` pos-run: 74.951 bytes, copiado sem imprimir conteudo.
- `mpv-generation-logs/`: 12 arquivos `mpv-g*.log` capturados.
- Tamanho total dos logs por geracao: 906.680 bytes.
- 0 geracoes capturadas ficaram abaixo de 12 KiB.

Agregados sanitizados dos logs MPV:

- `playback restart complete`: 36.
- `audio=eof, video=playing`: 12.
- `DR failed - disabling`: 36.
- `Using software decoding`: 72.

## Dados e persistencia

- `/data/media/kiosky-player`: preservado; este README nao publica nomes de arquivo nem caminhos privados.
- `/data/state/kiosky-player`: preservado; este README nao publica conteudo privado.
- `/tmp/kiosky-status.json`: copiado antes e depois do run, analisado apenas pelos campos sanitizados de status.

## Escrita em /opt

A auditoria com marcador temporal nao encontrou escrita em `/opt/totem/kiosky-player` apos o inicio do app.

## Processos remanescentes

- Depois do timeout: nenhum processo real `kiosk.py` ou `mpv` do usuario `totem`.
- A lista global depois do teste mostrou apenas o proprio comando `pgrep` como self-match, sem processo remanescente real.

## Kernel e systemd

- `systemctl --failed` apos o probe: `0 loaded units listed`.
- `systemctl --failed` no diagnostico consolidado: `0 loaded units listed`.
- Filtro critico de kernel no probe: sem ocorrencias.
- Filtro critico de kernel no diagnostico consolidado: sem `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`.

## Escopo negativo confirmado

- Nenhum comando `apt` foi executado.
- Nenhum pacote foi instalado.
- Nenhum servico systemd da aplicacao foi habilitado ou iniciado.
- Nenhum cache, midia ou estado foi apagado.
- Nenhum conteudo da config privada foi impresso.
- Nenhum segredo, URL privada, identificador privado, nome de campanha ou payload privado foi publicado neste README.
- Nenhum commit foi feito durante a execucao da rodada.

## Recomendacao

Nao adotar grace window fixa de 5s como politica final. A mudanca reduziu restarts por `ipc_unresponsive`, mas piorou `command timeout` e falha de `loadfile`.

Proximo passo recomendado: trocar a janela fixa por uma politica mais seletiva, por exemplo suprimir apenas o primeiro ping falho apos `loadfile` e permitir restart se houver timeout real de `loadfile`, ou isolar a midia associada as falhas de load em teste manual especifico antes de novo ajuste de watchdog.
