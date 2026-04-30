# Rodada 20260429-215201 - kiosky-player manual probe com coordenacao IPC/restart

Status: teste manual curto A/B do `kiosky-player` concluido como usuario `totem`, ainda sem systemd da aplicacao.

## Objetivo

Executar uma nova rodada curta usando somente o codigo corrigido do `kiosky-player` que serializa fechamento de IPC com comandos em andamento. A configuracao foi mantida igual a rodada anterior relevante, sem alterar timeout, `hwdec`, logging ou politica do watchdog.

## Codigo e config

Checkout local do `kiosky-player`: branch `appliance-v0.1`.

Commit deployado: `9bdb38c Serialize MPV IPC close with commands`.

Confirmacao da config privada, sem imprimir conteudo do arquivo:

- `mpv_watchdog_ping_failures_before_restart`: OK.
- `mpv_ipc_timeout_sec`: OK.
- `mpv_startup_timeout_sec`: OK.
- `hwdec`: OK.
- `mpv_log_file`: OK.
- `mpv_msg_level`: OK.
- `mpv_debug_events`: OK.
- Permissoes: OK.
- Correcao de config necessaria nesta rodada: nao.

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

- `kiosky-manual-20260429-214640-0300.tar.gz`
- `totem-diag-20260429-215157-0300.tar.gz`

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
- `app-run.stdout.txt`: 48.474 bytes.
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
- `MPV IPC unresponsive`: 11.
- `MPV IPC ping failed`: 23, contando a linha original `MPV IPC ping failed generation=`.
- `MPV IPC ping ok`: 1.
- `Restarting MPV`: 13.
- `MPV process started`: 14.
- `Failed to load media`: 2.
- `MPV loadfile returned error`: 2.
- `Media load retry failed`: 0.

Contagens auxiliares:

- `MPV IPC ping failed below restart threshold`: 12.
- `MPV IPC ping failure counter reset after generation change`: 1.
- `Restarting MPV reason=ipc_unresponsive`: 11.
- `Restarting MPV reason=media_load_failed`: 2.
- `MPV IPC startup wait complete`: 14/14.
- `MPV loadfile result`: 30 sucessos.

Distribuicao sanitizada:

- `Playing media`: 5 aliases sanitizados, 6 ocorrencias cada.
- Falhas de load: 2 ocorrencias em 1 alias sanitizado.
- Motivos de restart: `ipc_unresponsive=11`, `media_load_failed=2`.

## Comparacao com 20260429-202035

| Metrica | Threshold 2 + reset geracao | Coordenacao IPC/restart |
| --- | ---: | ---: |
| `Bad file descriptor` | 3 | 0 |
| `MPV IPC command timeout` | 28 | 24 |
| `MPV IPC command send failed` | 3 | 0 |
| `MPV IPC unresponsive` | 10 | 11 |
| `MPV IPC ping failed` | 23 | 23 |
| `MPV IPC ping ok` | 1 | 1 |
| `Restarting MPV` | 17 | 13 |
| `MPV process started` | 18 | 14 |
| `Failed to load media` | 7 | 2 |
| `MPV loadfile returned error` | 8 | 2 |
| `Media load retry failed` | 1 | 0 |

Leitura:

- A coordenacao IPC/restart manteve o sintoma esperado zerado: `Bad file descriptor` ficou em 0 e `MPV IPC command send failed` ficou em 0.
- O churn do MPV melhorou contra a referencia: `Restarting MPV` caiu de 17 para 13 e `MPV process started` de 18 para 14.
- Falhas de load tambem melhoraram: `Failed to load media` caiu de 7 para 2, `MPV loadfile returned error` caiu de 8 para 2 e `Media load retry failed` caiu de 1 para 0.
- A responsividade do ping IPC ainda nao esta resolvida: `MPV IPC ping failed` ficou em 23 e `MPV IPC unresponsive` ficou em 11.

## Logs MPV por geracao

Captura do probe:

- `pre-existing-mpv.log`: presente, 42.979 bytes, copiado sem imprimir conteudo.
- `pre-existing-mpv-generation-logs`: 19 arquivos listados como pre-existentes.
- `mpv.log` pos-run: 42.979 bytes, copiado sem imprimir conteudo.
- `mpv-generation-logs/`: 14 arquivos `mpv-g*.log` capturados.
- Tamanho total dos logs por geracao: 933.410 bytes.
- 1 geracao capturada ficou abaixo de 12 KiB.

Agregados sanitizados dos logs MPV:

- `playback restart complete`: 34.
- `audio=eof, video=playing`: 11.
- `DR failed - disabling`: 31.
- `Using software decoding`: 62.

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

Nao liberar systemd da aplicacao ainda, mas esta rodada reforca que a coordenacao IPC/restart corrigiu a corrida de fechamento de socket.

Proximo passo recomendado: manter a coordenacao IPC/restart e fazer uma rodada separada focada em responsividade de ping do MPV, sem misturar variaveis. A opcao mais direta e testar uma mudanca pequena na politica do watchdog para tratar `ping` como sinal menos destrutivo durante reproducao/transicao, por exemplo registrar a falha e atrasar restart quando o player acabou de carregar midia ou quando a geracao acabou de mudar. Outra opcao, em rodada separada, e testar `hwdec` desabilitado para reduzir custo/ruido de decode, mantendo a coordenacao IPC/restart ja aprovada.
