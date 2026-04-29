# Rodada 20260429-174349 - kiosky-player manual probe A/B timeout IPC 5s

Status: teste manual curto A/B do `kiosky-player` concluido como usuario `totem`, ainda sem systemd da aplicacao.

## Objetivo

Executar uma rodada curta alterando apenas os timeouts de IPC/startup do MPV, mantendo `hwdec=auto-safe`, para testar se os restarts observados nas rodadas anteriores eram falsos positivos causados por timeout IPC agressivo.

## Variacao A/B

Campos temporariamente alterados na config privada da placa, sem imprimir o conteudo do arquivo:

- `mpv_ipc_timeout_sec`: alterado para a variante A/B.
- `mpv_startup_timeout_sec`: alterado para a variante A/B.

Campos mantidos conforme rodada anterior:

- `hwdec=auto-safe`.
- `mpv_log_file=/tmp/kiosky/mpv.log`.
- `mpv_msg_level=all=v`.
- `mpv_debug_events=true`.

Os demais campos da config privada foram preservados. A validacao imprimiu apenas OK/FAIL dos campos alterados e nao publicou conteudo sensivel.

Observacao operacional: ao final desta rodada, a config privada da placa permanece com os timeouts da variante A/B ate que seja alterada novamente.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts executados:

- `scripts/board/setup_runtime_tmp.sh`
- `scripts/board/kiosky_manual_probe.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefatos brutos principais analisados:

- `kiosky-manual-20260429-173821-0300.tar.gz`
- `totem-diag-20260429-174336-0300.tar.gz`

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
- `app-run.stdout.txt`: 57.545 bytes.
- `Playing media`: 24 linhas.
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

- `MPV IPC unresponsive`: 18.
- `MPV IPC command timeout`: 22.
- `MPV IPC ping failed`: 18.
- `MPV IPC ping ok`: 1.
- `Restarting MPV`: 31.
- `MPV process started`: 32.
- `Failed to load media`: 13.
- `MPV loadfile returned error`: 15.
- `MPV loadfile result`: 24 sucessos.
- `Media load retry failed`: 2.
- `MPV IPC command send failed`: 10.
- `MPV IPC startup wait complete`: 32/32.

Distribuicao sanitizada:

- `Playing media`: `alias_1=6`, `alias_2=4`, `alias_3=4`, `alias_4=5`, `alias_5=5`.
- Falhas de load: `alias_1=1`, `alias_2=2`, `alias_3=4`, `alias_4=3`, `alias_5=3`.
- Motivos de restart: `ipc_unresponsive=18`, `media_load_failed=13` distribuidos entre os aliases sanitizados.

Duracoes observadas:

- Startup wait ate IPC aparecer: 32/32 completaram; mediana aproximada `0,710s`.
- Ping com falha: 18 ocorrencias; mediana aproximada `5,007s`, coerente com timeout IPC da variante.
- Ping OK: 1 ocorrencia; `0,002s`.
- `loadfile` com sucesso: 24 ocorrencias; mediana aproximada `0,009s`.
- `loadfile` com erro: 15 ocorrencias; mediana aproximada `3,259s`.

## Comparacao com rodada anterior

Rodada anterior de referencia: `20260429-172733-kiosky-manual-probe-generation-logs`.

| Metrica | Rodada anterior | Timeout IPC 5s | Leitura |
| --- | ---: | ---: | --- |
| `MPV IPC unresponsive` | 21 | 18 | leve melhora |
| `MPV IPC command timeout` | 27 | 22 | melhora |
| `MPV IPC ping failed` | 21 | 18 | leve melhora |
| `MPV IPC ping ok` | 1 | 1 | sem melhora |
| `Restarting MPV` | 31 | 31 | sem melhora |
| `MPV process started` | 32 | 32 | sem melhora |
| `Failed to load media` | 10 | 13 | piora |
| `MPV loadfile returned error` | 10 | 15 | piora |
| `Media load retry failed` | 0 | 2 | piora |

Interpretacao: aumentar o timeout IPC reduziu parcialmente os timeouts/pings falhos, mas nao reduziu o numero total de restarts nem a quantidade de processos MPV iniciados. Tambem piorou o comportamento de `loadfile`, com falhas espalhadas por mais aliases e duas falhas de retry. Portanto, a hipotese de falso positivo puramente causado por timeout agressivo fica enfraquecida.

## Logs MPV por geracao

Captura do probe:

- `pre-existing-mpv.log`: presente, 53.479 bytes, copiado sem imprimir conteudo.
- `mpv.log` pos-run: 10.069 bytes, copiado sem imprimir conteudo.
- `mpv-generation-logs/`: 32 arquivos `mpv-g*.log` capturados.
- Tamanho total dos logs por geracao: 1.261.346 bytes.
- Antes do run havia 32 logs por geracao da rodada anterior listados como pre-existentes; o probe capturou somente os novos logs pelo marcador desta rodada.

Resumo sanitizado dos logs por geracao:

- Foram preservados `mpv-g001.log` a `mpv-g032.log`.
- 14 geracoes foram curtas, menores que 12 KiB.
- Os logs continuam mostrando o padrao recorrente de inicializacao MPV em DRM/KMS, com ruido de TTY/VT e tentativas CUDA/VAAPI/hwdec indisponiveis.
- Agregados sanitizados: `playback restart complete=28`, `audio=eof, video=playing=7`, referencias locais de midia no bruto em 152 ocorrencias, sem publicar caminhos ou nomes privados neste README.

## Dados e persistencia

- `/data/media/kiosky-player`: 5 arquivos / 19.877.088 bytes depois do run.
- `/data/state/kiosky-player`: 3 arquivos / 4.973 bytes depois do run.
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

Nao liberar teste longo nem systemd da aplicacao. A variante com timeout IPC maior nao resolveu o problema principal: os restarts permaneceram no mesmo patamar e as falhas de load pioraram.

Proximo passo recomendado: fazer uma nova rodada A/B curta, ainda sem systemd, revertendo ou documentando explicitamente os timeouts antes do teste e alterando apenas `hwdec` para uma variante sem hardware decode. Manter captura de `mpv-g*.log` por geracao e observacao humana temporizada da tela.
