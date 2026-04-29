# Rodada 20260429-194954 - kiosky-player manual probe A/B watchdog threshold 2

Status: teste manual curto A/B do `kiosky-player` concluido como usuario `totem`, ainda sem systemd da aplicacao.

## Objetivo

Executar uma rodada curta alterando apenas a politica do watchdog para exigir 2 falhas consecutivas de ping IPC antes de reiniciar o MPV, mantendo timeout IPC em 2s, startup timeout em 10s, `hwdec=auto-safe` e diagnostico MPV verbose.

## Variacao A/B

Checkout local do `kiosky-player`: branch `appliance-v0.1`.

Commit deployado: `52836f3 Add configurable MPV watchdog ping threshold`.

Campos alterados/confirmados na config privada da placa, sem imprimir conteudo do arquivo:

- `mpv_watchdog_ping_failures_before_restart=2`
- `mpv_ipc_timeout_sec=2.0`
- `mpv_startup_timeout_sec=10.0`
- `hwdec=auto-safe`
- `mpv_log_file=/tmp/kiosky/mpv.log`
- `mpv_msg_level=all=v`
- `mpv_debug_events=true`

Os demais campos da config privada foram preservados. A validacao publicou apenas OK/FAIL dos campos acima e `stat`; nenhum segredo, URL privada ou identificador privado foi publicado.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts executados:

- `scripts/remote/deploy_kiosky_player.sh`
- `scripts/board/setup_runtime_tmp.sh`
- `scripts/board/kiosky_manual_probe.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefatos brutos principais analisados:

- `kiosky-manual-20260429-194422-0300.tar.gz`
- `totem-diag-20260429-194941-0300.tar.gz`

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
- `app-run.stdout.txt`: 50.042 bytes.
- `Playing media`: 30 linhas, com os 5 aliases sanitizados aparecendo 6 vezes cada.
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

- `MPV IPC unresponsive`: 11.
- `MPV IPC command timeout`: 30.
- `MPV IPC ping failed`: 23, usando a linha original `MPV IPC ping failed generation=` para manter comparacao com as rodadas anteriores.
- `MPV IPC ping ok`: 1.
- `Restarting MPV`: 18.
- `MPV process started`: 19.
- `Failed to load media`: 7.
- `MPV loadfile returned error`: 7.
- `Media load retry failed`: 0.

Contagens auxiliares:

- `MPV IPC ping failed below restart threshold`: 12.
- `Restarting MPV reason=ipc_unresponsive`: 11.
- `Restarting MPV reason=media_load_failed`: 7.
- `MPV IPC command send failed`: 0.
- `MPV IPC startup wait complete`: 19/19.
- `MPV loadfile result`: 30 sucessos.

Distribuicao sanitizada:

- `Playing media`: 5 aliases sanitizados, 6 ocorrencias cada.
- Falhas de load: 6 ocorrencias em um alias sanitizado e 1 ocorrencia em outro alias sanitizado.
- Motivos de restart: `ipc_unresponsive=11`, `media_load_failed=7`.

Observacao de implementacao vista nos logs:

- Em 7 dos 11 `ipc_unresponsive`, a geracao do MPV nao tinha uma falha `below restart threshold` anterior na mesma geracao.
- Isso sugere que o contador local de falhas consecutivas do watchdog sobrevive a reinicios do MPV causados por outro caminho, como `media_load_failed`.
- Na pratica, uma falha de ping antes de um restart por load pode fazer a proxima falha de ping em uma nova geracao contar como segunda falha consecutiva.

## Comparacao

| Metrica | Baseline 20260429-172733 | Timeout 5s 20260429-174349 | Watchdog threshold 2 |
| --- | ---: | ---: | ---: |
| `MPV IPC unresponsive` | 21 | 18 | 11 |
| `MPV IPC command timeout` | 27 | 22 | 30 |
| `MPV IPC ping failed` | 21 | 18 | 23 |
| `MPV IPC ping ok` | 1 | 1 | 1 |
| `Restarting MPV` | 31 | 31 | 18 |
| `MPV process started` | 32 | 32 | 19 |
| `Failed to load media` | 10 | 13 | 7 |
| `MPV loadfile returned error` | 10 | 15 | 7 |
| `Media load retry failed` | 0 | 2 | 0 |

Leitura:

- A variante threshold 2 melhorou o churn de MPV: `Restarting MPV` caiu de 31 para 18 e `MPV process started` de 32 para 19.
- Tambem reduziu falhas de load contra as duas rodadas de referencia.
- A responsividade IPC ainda nao esta boa: houve 23 falhas de ping e 30 command timeouts em 300s.
- A melhora e real, mas insuficiente para liberar teste longo ou systemd da aplicacao.

## Logs MPV por geracao

Captura do probe:

- `pre-existing-mpv.log`: ausente antes da rodada.
- `pre-existing-mpv-generation-logs`: 0 arquivos.
- `mpv.log` pos-run: 66.309 bytes, copiado sem imprimir conteudo.
- `mpv-generation-logs/`: 19 arquivos `mpv-g*.log` capturados.
- Tamanho total dos logs por geracao: 1.245.725 bytes.
- Nenhuma geracao capturada ficou abaixo de 12 KiB.
- Os 19 logs continham marcadores de reproducao/midia ou restart, sem publicar caminhos privados.

Agregados sanitizados dos logs MPV:

- `playback restart complete`: 37.
- `audio=eof, video=playing`: 12.
- `DR failed - disabling`: 39.
- `Using software decoding`: 76.
- `Failed to open VDPAU`: 0.
- `Could not open codec`: 0.

## Dados e persistencia

- `/data/media/kiosky-player`: preservado; o README nao publica nomes de arquivo nem caminhos privados.
- `/data/state/kiosky-player`: preservado; o README nao publica conteudo privado.
- `/tmp/kiosky-status.json`: copiado apos o run e analisado apenas pelos campos sanitizados de status.

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

Proximo passo recomendado: corrigir a politica do watchdog para zerar o contador de falhas quando a geracao do MPV muda ou quando qualquer restart do MPV ocorre por outro motivo, mantendo `mpv_watchdog_ping_failures_before_restart=2` e repetindo uma rodada curta. Isso testa a mesma hipotese com semantica mais fiel de "falhas consecutivas do mesmo MPV".

Se essa correcao ainda mantiver timeouts/restarts altos, o proximo teste deve atacar coordenacao IPC/restart: impedir que `restart()` feche o socket enquanto `_send()` / `_recv_response()` estao em operacao, mantendo timeouts, `hwdec` e logging constantes.
