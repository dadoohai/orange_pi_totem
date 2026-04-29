# Rodada 20260429-202035 - kiosky-player manual probe watchdog threshold 2 com reset por geracao

Status: teste manual curto A/B do `kiosky-player` concluido como usuario `totem`, ainda sem systemd da aplicacao.

## Objetivo

Repetir a rodada A/B com `mpv_watchdog_ping_failures_before_restart=2` apos a correcao do `kiosky-player` que zera o contador de falhas do watchdog quando a geracao do MPV muda. A meta foi medir a politica real de 2 falhas consecutivas na mesma geracao, mantendo a mesma configuracao da rodada `20260429-194954`.

## Codigo e config

Checkout local do `kiosky-player`: branch `appliance-v0.1`.

Commit deployado: `fee4a8b Scope watchdog failures to MPV generation`.

Campos alterados/confirmados na config privada da placa, sem imprimir conteudo do arquivo:

- `mpv_watchdog_ping_failures_before_restart=2`
- `mpv_ipc_timeout_sec=2.0`
- `mpv_startup_timeout_sec=10.0`
- `hwdec=auto-safe`
- `mpv_log_file=/tmp/kiosky/mpv.log`
- `mpv_msg_level=all=v`
- `mpv_debug_events=true`

Os demais campos da config privada foram preservados. A validacao publicou apenas OK/FAIL dos campos acima e `stat`; nenhum segredo, URL privada, identificador privado, nome de campanha ou payload privado foi publicado.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts executados:

- `scripts/remote/deploy_kiosky_player.sh`
- `scripts/board/setup_runtime_tmp.sh`
- `scripts/board/kiosky_manual_probe.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefatos brutos principais analisados:

- `kiosky-manual-20260429-201508-0300.tar.gz`
- `totem-diag-20260429-202030-0300.tar.gz`

O pull com padroes amplos tambem copiou artefatos antigos ainda presentes em `/root/totem-diag`. A analise desta rodada usa somente os dois artefatos acima.

Os arquivos `.tar.gz`, `raw/` e `extracted/` sao evidencia bruta e nao devem ser commitados no repositorio publico.

## Resultado do app

Comando auditado pelo probe:

```text
runuser -u totem -- env PYTHONDONTWRITEBYTECODE=1 XDG_RUNTIME_DIR=/tmp/kiosky timeout 300s python3 /opt/totem/kiosky-player/kiosk.py --config /data/config/config.json
```

Resultado:

- `app-run` retornou exit code `124`.
- Interpretacao: timeout esperado do probe de 300 segundos, com encerramento controlado ao final.
- `app-run.stderr.txt`: 0 bytes.
- `app-run.stdout.txt`: 50.046 bytes.
- `Playing media`: 28 linhas.
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

- `MPV IPC unresponsive`: 10.
- `MPV IPC ping failed`: 23, contando a linha original `MPV IPC ping failed generation=`.
- `MPV IPC ping ok`: 1.
- `MPV IPC command timeout`: 28.
- `Restarting MPV`: 17.
- `MPV process started`: 18.
- `Failed to load media`: 7.
- `MPV loadfile returned error`: 8.
- `Media load retry failed`: 1.

Contagens auxiliares:

- `MPV IPC ping failed below restart threshold`: 13.
- `MPV IPC ping failure counter reset after generation change`: 3.
- `Restarting MPV reason=ipc_unresponsive`: 10.
- `Restarting MPV reason=media_load_failed`: 7.
- `MPV IPC command send failed`: 3.
- `MPV IPC startup wait complete`: 18/18.
- `MPV loadfile result`: 28 sucessos.

Distribuicao sanitizada:

- `Playing media`: 5 aliases sanitizados; quatro apareceram 6 vezes e um apareceu 4 vezes.
- Falhas de load: 3 aliases sanitizados, com distribuicao `3`, `2` e `2`.
- Motivos de restart: `ipc_unresponsive=10`, `media_load_failed=7`.

Observacao de implementacao vista nos logs:

- A nova mensagem `MPV IPC ping failure counter reset after generation change` apareceu 3 vezes.
- A correcao atuou como esperado: falhas de ping antes de uma troca de geracao deixaram de atravessar automaticamente para a geracao seguinte.
- Ainda ha `Bad file descriptor` em `loadfile`, o que mantem forte a hipotese de corrida entre watchdog/restart e comandos IPC do `playback_loop`.

## Comparacao

| Metrica | Baseline 20260429-172733 | Timeout 5s 20260429-174349 | Threshold 2 20260429-194954 | Threshold 2 + reset geracao |
| --- | ---: | ---: | ---: | ---: |
| `MPV IPC unresponsive` | 21 | 18 | 11 | 10 |
| `MPV IPC ping failed` | 21 | 18 | 23 | 23 |
| `MPV IPC ping ok` | 1 | 1 | 1 | 1 |
| `MPV IPC command timeout` | 27 | 22 | 30 | 28 |
| `Restarting MPV` | 31 | 31 | 18 | 17 |
| `MPV process started` | 32 | 32 | 19 | 18 |
| `Failed to load media` | 10 | 13 | 7 | 7 |
| `MPV loadfile returned error` | 10 | 15 | 7 | 8 |
| `Media load retry failed` | 0 | 2 | 0 | 1 |

Leitura:

- O reset por geracao trouxe melhora pequena sobre a variante threshold 2 anterior: menos 1 `ipc_unresponsive`, menos 1 restart e menos 1 processo MPV iniciado.
- A melhora grande em relacao ao baseline continua vindo da politica threshold 2: `Restarting MPV` ficou em 17 contra 31 no baseline.
- A responsividade IPC segue ruim: 23 falhas de ping e 28 command timeouts em 300s.
- A correcao confirmou a semantica correta do contador, mas nao resolve sozinha a instabilidade principal.

## Logs MPV por geracao

Captura do probe:

- `pre-existing-mpv.log`: presente, 66.309 bytes, copiado sem imprimir conteudo.
- `pre-existing-mpv-generation-logs`: 19 arquivos da rodada anterior listados como pre-existentes.
- `mpv.log` pos-run: 42.979 bytes, copiado sem imprimir conteudo.
- `mpv-generation-logs/`: 18 arquivos `mpv-g*.log` capturados.
- Tamanho total dos logs por geracao: 1.013.631 bytes.
- 4 geracoes capturadas ficaram abaixo de 12 KiB.

Agregados sanitizados dos logs MPV:

- `playback restart complete`: 34.
- `audio=eof, video=playing`: 10.
- `DR failed - disabling`: 32.
- `Using software decoding`: 64.

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
- Nenhum commit foi feito nesta rodada.

## Recomendacao

Nao liberar teste longo nem systemd da aplicacao ainda.

Proximo passo recomendado: atacar a coordenacao IPC/restart. A variante threshold 2 com reset por geracao confirmou melhora parcial, mas restaram timeouts frequentes e 3 falhas `Bad file descriptor` em `loadfile`. O proximo A/B deve garantir que `restart()` / `_stop_locked()` nao fechem o socket enquanto `_send()` / `_recv_response()` estao usando IPC, mantendo timeout, `hwdec`, logging e threshold constantes.
