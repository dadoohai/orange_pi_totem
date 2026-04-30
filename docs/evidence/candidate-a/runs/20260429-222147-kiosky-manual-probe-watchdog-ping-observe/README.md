# Rodada 20260429-222147 - kiosky-player manual probe observando ping IPC

Status: teste manual curto A/B do `kiosky-player` concluido como usuario `totem`, ainda sem systemd da aplicacao.

## Objetivo

Executar uma rodada curta sem mudar codigo para testar se reiniciar o MPV por falha de ping IPC e destrutivo demais. A politica do watchdog foi ajustada para praticamente desativar restart por ping dentro da janela de 300s, elevando `mpv_watchdog_ping_failures_before_restart` para `999`.

## Codigo e config

Checkout local do `kiosky-player`: branch `appliance-v0.1`.

Commit deployado: `9bdb38c Serialize MPV IPC close with commands`.

Campos privados alterados ou confirmados, sem imprimir conteudo da config:

- `mpv_watchdog_ping_failures_before_restart`: alterado para o modo de observacao desta rodada.
- `mpv_ipc_timeout_sec`: mantido no valor esperado.
- `mpv_startup_timeout_sec`: mantido no valor esperado.
- `hwdec`: mantido no valor esperado.
- `mpv_log_file`: mantido no valor esperado.
- `mpv_msg_level`: mantido no valor esperado.
- `mpv_debug_events`: mantido no valor esperado.
- Permissoes: OK.

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

- `kiosky-manual-20260429-221625-0300.tar.gz`
- `totem-diag-20260429-222141-0300.tar.gz`

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
- `app-run.stdout.txt`: 46.521 bytes.
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
- `MPV IPC command timeout`: 29.
- `MPV IPC command send failed`: 0.
- `MPV IPC unresponsive`: 0.
- `MPV IPC ping failed`: 23, contando a linha original `MPV IPC ping failed generation=`.
- `MPV IPC ping ok`: 3.
- `MPV IPC ping failed below restart threshold`: 23.
- `Restarting MPV`: 6.
- `MPV process started`: 7.
- `Failed to load media`: 6.
- `MPV loadfile returned error`: 6.
- `Media load retry failed`: 0.

Contagens auxiliares:

- `Restarting MPV reason=ipc_unresponsive`: 0.
- `Restarting MPV reason=media_load_failed`: 6.
- `MPV IPC startup wait complete`: 7/7.
- `MPV loadfile result`: 30 sucessos.

Distribuicao sanitizada:

- `Playing media`: 5 aliases sanitizados.
- Falhas de load: 6 ocorrencias em 1 alias sanitizado.
- Motivos de restart: `media_load_failed=6`.

## Comparacao com 20260429-210204

| Metrica | Coordenacao IPC/restart | Ping observe threshold alto |
| --- | ---: | ---: |
| `Bad file descriptor` | 0 | 0 |
| `MPV IPC command timeout` | 24 | 29 |
| `MPV IPC command send failed` | 0 | 0 |
| `MPV IPC unresponsive` | 11 | 0 |
| `MPV IPC ping failed` | 23 | 23 |
| `MPV IPC ping ok` | 1 | 3 |
| `MPV IPC ping failed below restart threshold` | 12 | 23 |
| `Restarting MPV` | 13 | 6 |
| `MPV process started` | 14 | 7 |
| `Failed to load media` | 2 | 6 |
| `MPV loadfile returned error` | 2 | 6 |
| `Media load retry failed` | 0 | 0 |

Leitura:

- A corrida de fechamento de socket continuou ausente: `Bad file descriptor` ficou em 0 e `MPV IPC command send failed` ficou em 0.
- O threshold alto impediu restart por ping: `MPV IPC unresponsive` caiu de 11 para 0 e todos os 23 pings falhos ficaram abaixo do threshold.
- O churn do MPV caiu: `Restarting MPV` caiu de 13 para 6 e `MPV process started` de 14 para 7.
- O resultado nao e uma melhora geral: `MPV IPC command timeout` subiu de 24 para 29 e falhas de load subiram de 2 para 6.
- A rodada sugere que restart imediato por ping e agressivo, mas simplesmente desativar restart por ping deixa o IPC degradado por mais tempo e piora loadfile.

## Logs MPV por geracao

Captura do probe:

- `pre-existing-mpv.log`: presente, 42.979 bytes, copiado sem imprimir conteudo.
- `pre-existing-mpv-generation-logs`: 19 arquivos listados como pre-existentes.
- `mpv.log` pos-run: 75.871 bytes, copiado sem imprimir conteudo.
- `mpv-generation-logs/`: 7 arquivos `mpv-g*.log` capturados.
- Tamanho total dos logs por geracao: 633.955 bytes.
- 0 geracoes capturadas ficaram abaixo de 12 KiB.

Agregados sanitizados dos logs MPV:

- `playback restart complete`: 38.
- `audio=eof, video=playing`: 14.
- `DR failed - disabling`: 36.
- `Using software decoding`: 72.

## Dados e persistencia

- `/data/media/kiosky-player`: preservado; o README nao publica nomes de arquivo nem caminhos privados.
- `/data/state/kiosky-player`: preservado; o README nao publica conteudo privado.
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

Nao adotar `mpv_watchdog_ping_failures_before_restart=999` como politica final. A rodada reduz reinicios por ping, mas aumenta timeouts de comando e falhas de load.

Proximo passo recomendado: manter a coordenacao IPC/restart e substituir a decisao binaria de restart por ping por uma politica intermediaria. Uma variante promissora e aplicar cooldown ou janela de graca para ping durante transicoes de midia/geracao, mas ainda permitir restart quando comandos reais como `loadfile` continuam dando timeout.
