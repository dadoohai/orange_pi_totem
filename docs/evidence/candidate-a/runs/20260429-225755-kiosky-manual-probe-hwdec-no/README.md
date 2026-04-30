# Rodada 20260429-225755 - kiosky-player manual probe com hwdec=no

Status: teste manual curto A/B do `kiosky-player` concluido como usuario `totem`, ainda sem systemd da aplicacao.

## Objetivo

Testar se desabilitar `hwdec` reduz custo/ruido de decode e melhora a estabilidade MPV IPC. A variavel principal desta rodada foi `hwdec=no`, mantendo a coordenacao IPC/restart ja aprovada e voltando `watchdog_interval_sec` para o baseline.

## Codigo e config

Checkout local do `kiosky-player`: branch `appliance-v0.1`.

Commit deployado: `9bdb38c Serialize MPV IPC close with commands`.

Confirmacao da config privada, sem imprimir conteudo do arquivo:

- `watchdog_interval_sec`: OK, baseline desta rodada.
- `mpv_watchdog_ping_failures_before_restart`: OK.
- `mpv_ipc_timeout_sec`: OK.
- `mpv_startup_timeout_sec`: OK.
- `hwdec`: OK, variante desabilitada desta rodada.
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

- `kiosky-manual-20260429-225240-0300.tar.gz`
- `totem-diag-20260429-225750-0300.tar.gz`

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
- `app-run.stdout.txt`: 49.146 bytes.
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
- `MPV IPC command timeout`: 24.
- `MPV IPC command send failed`: 0.
- `MPV IPC unresponsive`: 10.
- `MPV IPC ping failed`: 22, contando a linha original `MPV IPC ping failed generation=`.
- `MPV IPC ping ok`: 2.
- `MPV IPC ping failed below restart threshold`: 12.
- `Restarting MPV`: 13.
- `MPV process started`: 14.
- `Failed to load media`: 3.
- `MPV loadfile returned error`: 3.
- `Media load retry failed`: 0.
- `Playing media`: 30.

Contagens auxiliares:

- `Restarting MPV reason=ipc_unresponsive`: 10.
- `Restarting MPV reason=media_load_failed`: 3.
- `MPV IPC startup wait complete`: 14/14.
- `MPV loadfile result`: 30 sucessos.

Distribuicao sanitizada:

- `Playing media`: 5 aliases sanitizados, 6 ocorrencias cada.
- Falhas de load: 3 ocorrencias em 1 alias sanitizado.

## Comparacao

| Metrica | 20260429-210204 coord. IPC/restart | 20260429-224248 watchdog 17s | `hwdec=no` |
| --- | ---: | ---: | ---: |
| `Bad file descriptor` | 0 | 0 | 0 |
| `MPV IPC command timeout` | 24 | 19 | 24 |
| `MPV IPC command send failed` | 0 | 0 | 0 |
| `MPV IPC unresponsive` | 11 | 6 | 10 |
| `MPV IPC ping failed` | 23 | 15 | 22 |
| `MPV IPC ping ok` | 1 | 1 | 2 |
| `MPV IPC ping failed below restart threshold` | 12 | 9 | 12 |
| `Restarting MPV` | 13 | 11 | 13 |
| `MPV process started` | 14 | 12 | 14 |
| `Failed to load media` | 2 | 5 | 3 |
| `MPV loadfile returned error` | 2 | 5 | 3 |
| `Media load retry failed` | 0 | 0 | 0 |
| `Playing media` | 30 | 30 | 30 |

Leitura:

- A corrida de fechamento de socket continuou ausente: `Bad file descriptor` e `MPV IPC command send failed` ficaram em 0.
- Contra a rodada de coordenacao IPC/restart, `hwdec=no` nao reduziu `MPV IPC command timeout`, `Restarting MPV` nem `MPV process started`.
- Contra a rodada `watchdog_interval_sec=17`, `hwdec=no` piorou timeout, ping e churn, mas reduziu `Failed to load media` de 5 para 3.
- O resultado nao sustenta `hwdec=no` como solucao final para a instabilidade IPC/watchdog.

## Logs MPV por geracao

Captura do probe:

- `pre-existing-mpv.log`: presente, 42.979 bytes, copiado sem imprimir conteudo.
- `pre-existing-mpv-generation-logs`: 19 arquivos listados como pre-existentes.
- `mpv.log` pos-run: 42.965 bytes, copiado sem imprimir conteudo.
- `mpv-generation-logs/`: 14 arquivos `mpv-g*.log` capturados.
- Tamanho total dos logs por geracao: 898.360 bytes.
- 1 geracao capturada ficou abaixo de 12 KiB.

Agregados sanitizados dos logs MPV:

- `playback restart complete`: 35.
- `audio=eof, video=playing`: 11.
- `DR failed - disabling`: 32.
- `Using software decoding`: 64.

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

Nao adotar `hwdec=no` como solucao final nesta fase. A rodada ficou essencialmente equivalente a coordenacao IPC/restart para timeout e churn, com pequena piora em falha de load contra essa referencia.

Proximo passo recomendado: isolar a midia associada as falhas de `loadfile` em um teste manual especifico, ou implementar instrumentacao/politica de grace window do watchdog durante transicoes de midia. A politica final deve atacar transicao e decisao de restart, nao apenas `hwdec` ou intervalo fixo do watchdog.
