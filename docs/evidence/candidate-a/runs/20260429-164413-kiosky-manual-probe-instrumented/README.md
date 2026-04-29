# Rodada 20260429-164413 - kiosky-player manual probe instrumentado

Status: segundo teste manual curto do `kiosky-player` concluido como usuario `totem`, ainda sem systemd da aplicacao.

## Objetivo

Repetir o teste manual controlado do `kiosky-player` na Orange Pi Zero 3 Candidato A, agora com instrumentacao de MPV/IPC habilitada na config privada da placa, para entender os avisos `MPV IPC unresponsive` e as falhas de `loadfile`.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts executados:

- `scripts/remote/deploy_kiosky_player.sh`
- `scripts/board/setup_runtime_tmp.sh`
- `scripts/board/kiosky_manual_probe.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefatos brutos principais analisados:

- `kiosky-manual-20260429-163852-0300.tar.gz`
- `totem-diag-20260429-164403-0300.tar.gz`

O pull com padroes amplos tambem copiou artefatos antigos ainda presentes em `/root/totem-diag`. A analise desta rodada usa somente os dois artefatos acima.

Os arquivos `.tar.gz`, `raw/` e `extracted/` sao evidencia bruta e nao devem ser commitados no repositorio publico.

## Codigo e config

- Checkout local do `kiosky-player`: branch `appliance-v0.1`.
- Commit deployado: `affcdd2 Add MPV diagnostics instrumentation`.
- A config privada em `/data/config/config.json` foi atualizada na placa sem imprimir conteudo ou secrets.
- Foram alterados somente os campos de diagnostico:
  - `mpv_log_file=/tmp/kiosky/mpv.log`
  - `mpv_msg_level=all=v`
  - `mpv_debug_events=true`
- `python3 -m json.tool /data/config/config.json >/dev/null` passou.
- Permissoes da config apos a escrita: owner `root:totem`, modo `0640`.

## Resultado do app

Comando auditado pelo probe:

```text
runuser -u totem -- env PYTHONDONTWRITEBYTECODE=1 XDG_RUNTIME_DIR=/tmp/kiosky timeout 300s python3 /opt/totem/kiosky-player/kiosk.py --config /data/config/config.json
```

Resultado:

- `app-run` retornou exit code `124`.
- Interpretacao: timeout esperado do probe de 300 segundos, pois houve `Signal 15` ao final.
- `app-run.stderr.txt`: 0 bytes.
- `app-run.stdout.txt`: 36.453 bytes.
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

## MPV/IPC

Comparacao com a primeira rodada:

- `MPV IPC unresponsive`: 21 ocorrencias nesta rodada; nao reduziu em relacao as 21 ocorrencias da primeira rodada.
- `Failed to load media, restarting MPV`: 10 ocorrencias nesta rodada; persistiu e aumentou em relacao as 5 ocorrencias da primeira rodada.
- `MPV IPC ping failed`: 21 ocorrencias.
- `MPV IPC command timeout`: 25 ocorrencias.
- `MPV IPC command send failed`: 6 ocorrencias.
- `MPV loadfile returned error`: 10 ocorrencias.
- `Restarting MPV`: 31 ocorrencias.
- `MPV process started`: 32 ocorrencias.
- `MPV IPC ping ok`: 1 ocorrencia.

Associacao sanitizada das falhas de load:

- As 10 falhas de `Failed to load media, restarting MPV` ficaram concentradas em 2 aliases sanitizados de midia.
- Distribuicao sanitizada: `alias_4=5`, `alias_5=5`.
- As outras 3 midias nao apareceram nas falhas de load.
- Todas as 5 midias apareceram em linhas `Playing media`.
- Nao houve `Media load retry failed` nem entrada em cooldown definitivo.

Hipotese atual:

- O problema principal continua parecendo ser responsividade IPC/restart do MPV durante o run, nao falha definitiva de download ou API.
- As falhas de load ocorreram em duas midias especificas e frequentemente perto de timeouts de `ping`/restart, sugerindo corrida entre watchdog, restart do MPV e transicao de midia.
- Como o status final ficou `playing` e `mpv_running=true`, o app se recuperou dentro da janela curta, mas a frequencia de restart ainda e alta demais para liberar teste longo ou systemd.

## mpv.log

Captura do log:

- `pre-existing-mpv.log`: ausente; `/tmp/kiosky/mpv.log` nao existia antes da rodada.
- Antes do run, o probe truncou/criou `/tmp/kiosky/mpv.log`.
- Depois do run, `mpv.log` foi copiado para o artefato sem imprimir conteudo.
- Tamanho capturado: 53.459 bytes.
- Linhas capturadas: 667.

Resumo sanitizado:

- O log mostra MPV `0.35.1` com `vo=gpu`/DRM-KMS e atividade de GPU/DRM.
- Contagem de niveis no log: `debug=439`, `verbose=222`, `info=2`, `warning=1`, `error=3`.
- Mensagens relevantes:
  - MPV nao conseguiu abrir TTY para controle de VT; terminal switching ficou indisponivel.
  - Tentativas de hardware decode por CUDA/VAAPI falharam; isto e esperado/irrelevante para CUDA na placa, mas adiciona ruido e possivel custo de inicializacao.
  - Ha indicios de uso de video/GPU/DRM e pelo menos um restart de playback no processo capturado.
- Limitacao importante: o `mpv.log` aparenta conter apenas a ultima invocacao do MPV, porque `--log-file=/tmp/kiosky/mpv.log` foi sobrescrito a cada restart. O stdout instrumentado do app e a melhor fonte para a contagem completa dos 32 processos MPV desta rodada.

## Dados gerados e persistencia

- `/data/media/kiosky-player`: antes 5 arquivos / 19.877.088 bytes; depois 5 arquivos / 19.877.088 bytes.
- `/data/state/kiosky-player`: antes 3 arquivos / 4.973 bytes; depois 3 arquivos / 4.973 bytes.
- `/tmp/kiosky-status.json`: existia antes e depois; copia preservada no artefato bruto.

## Escrita em /opt

A auditoria com marcador temporal nao encontrou escrita em `/opt/totem/kiosky-player` apos o inicio do app.

## Processos remanescentes

- Antes do teste: nenhum processo real `kiosk.py` ou `mpv` do usuario `totem`.
- Depois do timeout: nenhum processo real `kiosk.py` ou `mpv` do usuario `totem`.
- A lista global depois do teste mostrou apenas o proprio comando `pgrep` como self-match, sem processo remanescente real.

## Kernel e systemd

- `systemctl --failed` apos o probe: `0 loaded units listed`.
- `systemctl --failed` no diagnostico consolidado: `0 loaded units listed`.
- `/proc/sys/kernel/tainted`: `1024`, valor ja observado anteriormente nesta fase.
- Kernel `6.12.58-current-sunxi64`.
- Armbian `25.11.1`.

Filtro critico de kernel:

- Sem `Internal error: Oops`.
- Sem `kernel panic`.
- Sem `EXT4-fs error`.
- Sem `Aborting journal`.
- Sem `Remounting filesystem read-only`.
- Sem `mmc timeout/reset`.
- O filtro ainda mostra mensagens conhecidas de boot `Error applying setting, reverse things back` para UART/SPI/MMC e registros normais de `thermal_sys`.

## Escopo negativo confirmado

- Nenhum comando `apt` foi executado.
- Nenhum pacote foi instalado.
- Nenhum servico systemd da aplicacao foi habilitado ou iniciado.
- Nenhum cache, midia ou estado foi apagado.
- Nenhum conteudo da config privada foi impresso.
- Nenhum segredo de API, URL privada, identificador privado, nome de campanha ou payload privado foi publicado neste README.
- Nenhum commit foi feito.

## Recomendacao

Nao liberar teste longo nem systemd da aplicacao com esta rodada. A instrumentacao confirmou que o problema de IPC continua frequente e que as falhas de load se concentram em duas midias sanitizadas, embora o app termine a janela curta em estado `playing`/`mpv_running=true` e sem bloqueadores de kernel ou systemd.

Proximo passo recomendado: ajustar a instrumentacao para preservar logs MPV por geracao/restart, ou capturar stdout/stderr do MPV por geracao, e repetir um teste curto. Em seguida, se a correlacao confirmar corrida de IPC/restart, testar uma variante controlada com timeout IPC/watchdog menos agressivo ou com `hwdec` desabilitado temporariamente, ainda sem systemd e sem teste longo.
