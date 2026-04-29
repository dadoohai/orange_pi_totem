# Rodada 20260429-172733 - kiosky-player manual probe com logs por geracao

Status: teste manual curto do `kiosky-player` concluido como usuario `totem`, ainda sem systemd da aplicacao.

## Objetivo

Executar nova rodada curta e instrumentada do `kiosky-player` na Orange Pi Zero 3 Candidato A, usando o `kiosky-player` com preservacao de logs MPV por geracao/restart, para entender melhor os avisos IPC e os restarts do MPV.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts executados:

- `scripts/remote/deploy_kiosky_player.sh`
- `scripts/board/setup_runtime_tmp.sh`
- `scripts/board/kiosky_manual_probe.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefatos brutos principais analisados:

- `kiosky-manual-20260429-172210-0300.tar.gz`
- `totem-diag-20260429-172720-0300.tar.gz`

O pull com padroes amplos tambem copiou artefatos antigos ainda presentes em `/root/totem-diag`. A analise desta rodada usa somente os dois artefatos acima.

Os arquivos `.tar.gz`, `raw/` e `extracted/` sao evidencia bruta e nao devem ser commitados no repositorio publico.

## Codigo e config

- Checkout local do `kiosky-player`: branch `appliance-v0.1`.
- Commit deployado: `7a5f75c Preserve MPV logs by generation`.
- Config privada validada com `python3 -m json.tool`, sem imprimir conteudo.
- Permissoes da config observadas: owner `root:totem`, modo `0640`.
- Campos de diagnostico confirmados sem expor secrets:
  - `mpv_log_file`: OK
  - `mpv_msg_level`: OK
  - `mpv_debug_events`: OK

## Resultado do app

Comando auditado pelo probe:

```text
runuser -u totem -- env PYTHONDONTWRITEBYTECODE=1 XDG_RUNTIME_DIR=/tmp/kiosky timeout 300s python3 /opt/totem/kiosky-player/kiosk.py --config /data/config/config.json
```

Resultado:

- `app-run` retornou exit code `124`.
- Interpretacao: timeout esperado do probe de 300 segundos, com `Signal 15` ao final.
- `app-run.stderr.txt`: 0 bytes.
- `app-run.stdout.txt`: 57.734 bytes.
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

Contagens desta rodada:

- `MPV IPC unresponsive`: 21 ocorrencias.
- `MPV IPC command timeout`: 27 ocorrencias.
- `MPV IPC command send failed`: 4 ocorrencias.
- `MPV IPC ping failed`: 21 ocorrencias.
- `MPV IPC ping ok`: 1 ocorrencia.
- `Restarting MPV`: 31 ocorrencias.
- `MPV process started`: 32 ocorrencias.
- `MPV IPC startup wait begin`: 32 ocorrencias.
- `MPV IPC startup wait complete`: 32 ocorrencias.
- `Failed to load media, restarting MPV`: 10 ocorrencias.
- `MPV loadfile returned error`: 10 ocorrencias.
- `MPV loadfile result`: 28 sucessos.
- `Media load retry failed`: 0 ocorrencias.

Distribuicao sanitizada:

- `Playing media`: `alias_1=6`, `alias_2=6`, `alias_3=6`, `alias_4=5`, `alias_5=5`.
- Falhas de load: `alias_4=5`, `alias_5=5`.
- Motivos de restart: `ipc_unresponsive=21`, `media_load_failed:alias_4=5`, `media_load_failed:alias_5=5`.

Duracoes observadas nos logs do app:

- Startup wait ate IPC aparecer: 32/32 completaram; mediana aproximada `0,710s`.
- Ping com falha: 21 ocorrencias; mediana aproximada `2,004s`, coerente com timeout IPC de 2s.
- Ping OK: 1 ocorrencia; `0,025s`.
- `loadfile` com sucesso: 28 ocorrencias; mediana aproximada `0,026s`.
- `loadfile` com erro: 10 ocorrencias; mediana aproximada `1,653s`.

Interpretacao: o socket IPC apareceu em todas as geracoes, entao o problema nao parece ser falha de startup do IPC. A falha continua concentrada em responsividade posterior do IPC, com pings atingindo o timeout e `loadfile` falhando nos mesmos dois aliases sanitizados.

## Logs MPV por geracao

Captura do probe:

- `pre-existing-mpv.log`: presente, 53.459 bytes, copiado sem imprimir conteudo.
- `mpv.log` pos-run: 53.479 bytes, copiado sem imprimir conteudo.
- `mpv-generation-logs/`: 32 arquivos `mpv-g*.log` capturados.
- Tamanho total dos logs por geracao: 1.442.264 bytes.
- `pre-existing-mpv-generation-logs`: nenhum `mpv-g*.log` pre-existente listado antes da rodada.

Resumo sanitizado dos logs por geracao:

- Foram preservados `mpv-g001.log` a `mpv-g032.log`.
- 22 geracoes registraram referencias a arquivos de midia locais dentro do log bruto.
- 10 geracoes foram curtas, menores que 12 KiB, sem referencia a arquivo de midia no log bruto: `mpv-g003`, `mpv-g005`, `mpv-g009`, `mpv-g011`, `mpv-g015`, `mpv-g017`, `mpv-g021`, `mpv-g023`, `mpv-g027`, `mpv-g029`.
- 30 ocorrencias de `playback restart complete` aparecem distribuidas em 22 geracoes.
- 8 ocorrencias indicaram `audio=eof, video=playing`, em 6 geracoes.
- As mensagens de erro/warning do MPV se repetem principalmente em startup:
  - falha de controle de TTY/VT em 22 geracoes;
  - tentativas CUDA/VAAPI/hwdec indisponiveis em varias geracoes;
  - mensagens de `DR failed - disabling` em 22 geracoes.

Hipotese atual baseada nos logs por geracao:

- Como todas as 32 geracoes completaram o startup wait do IPC, o MPV inicia e cria socket IPC de forma consistente.
- Os restarts frequentes parecem ocorrer depois do startup, quando o watchdog pinga o IPC e nao recebe resposta dentro de 2s.
- As geracoes curtas sem midia sugerem processos encerrados antes de o MPV chegar a carregar/reproduzir midia, coerente com corrida entre watchdog/restart e transicoes de playlist.
- Os warnings de CUDA/VAAPI/TTY sao ruido recorrente do MPV no ambiente DRM/KMS minimo; eles podem adicionar custo de startup, mas sozinhos nao explicam a falha porque o IPC aparece em todas as geracoes e varias geracoes reproduzem midia.

## Comparacao com rodada anterior

Rodada anterior instrumentada: `20260429-164413-kiosky-manual-probe-instrumented`.

- `MPV IPC unresponsive`: 21 -> 21, sem melhora.
- `MPV IPC command timeout`: 25 -> 27, leve piora.
- `MPV IPC command send failed`: 6 -> 4, leve melhora.
- `Restarting MPV`: 31 -> 31, sem melhora.
- `MPV process started`: 32 -> 32, sem melhora.
- `MPV IPC ping ok`: 1 -> 1, sem melhora.
- `Failed to load media`: 10 -> 10, sem melhora.
- Principal melhora desta rodada: diagnostico, porque os 32 logs MPV por geracao foram preservados.

## Dados e persistencia

- `/data/media/kiosky-player`: 5 arquivos / 19.877.088 bytes antes e depois.
- `/data/state/kiosky-player`: 3 arquivos / 4.973 bytes antes e depois.
- `/tmp/kiosky-status.json`: copiado antes e depois no artefato bruto.

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
- Nenhum segredo, URL privada, identificador privado, nome de campanha ou payload privado foi publicado neste README.
- Nenhum commit foi feito nesta rodada.

## Recomendacao

Nao liberar teste longo nem systemd da aplicacao. A rodada confirmou que preservar logs por geracao funciona, mas nao mostrou melhora operacional: o padrao de IPC unresponsive, restart e falha de load continua frequente.

Proximo passo recomendado: fazer uma rodada A/B curta, ainda sem systemd, alterando apenas um fator de controle por vez. A primeira variante sugerida e aumentar o timeout IPC/watchdog para reduzir falsos positivos de ping; se persistir, testar `hwdec` temporariamente desabilitado para reduzir ruido/custo de inicializacao de decode no MPV. Em ambas as variantes, manter captura de `mpv-g*.log` por geracao e observacao humana temporizada da tela.
