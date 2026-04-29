# Rodada 20260429-144234 - kiosky-player manual probe

Status: primeiro teste manual controlado do `kiosky-player` concluido como usuario `totem`, sem systemd da aplicacao.

## Objetivo

Executar o `kiosky-player` manualmente na base minima validada da Orange Pi Zero 3, usando a config privada ja criada fora do Git em `/data/config/config.json`, para verificar comportamento inicial do app com MPV/DRM-KMS sem ativar systemd da aplicacao.

## Execucao

Host usado: `root@[ip-local-redigido]`

Scripts executados:

- `scripts/board/setup_runtime_tmp.sh`
- `scripts/board/kiosky_manual_probe.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

Artefatos brutos principais:

- `kiosky-manual-20260429-143320-0300.tar.gz`
- `totem-diag-20260429-144151-0300.tar.gz`

O pull com padroes amplos tambem copiou diagnosticos antigos ainda presentes em `/root/totem-diag`. A analise desta rodada usa o artefato do probe `20260429-143320-0300` e o diagnostico `20260429-144151-0300`.

Os arquivos `.tar.gz` sao evidencia bruta e nao devem ser commitados no repositorio publico.

## Config

- `/data/config/config.json` foi validado com `python3 -m json.tool` antes do run.
- O conteudo da config nao foi impresso.
- A checagem de placeholders bloqueantes retornou exit code `0`.

## Resultado Do App

Comando auditado:

```text
runuser -u totem -- env PYTHONDONTWRITEBYTECODE=1 XDG_RUNTIME_DIR=/tmp/kiosky timeout 300s python3 /opt/totem/kiosky-player/kiosk.py --config /data/config/config.json
```

Resultado:

- `app-run` retornou exit code `124`.
- Interpretacao: timeout esperado do probe, pois o app permaneceu rodando durante a janela controlada de 300 segundos e recebeu `Signal 15` ao final.
- `stderr` do app ficou vazio.
- O log registrou `Playlist updated: 5 items`.
- O log registrou reproducoes durante a janela do teste.
- O log tambem registrou avisos frequentes de `MPV IPC unresponsive` e algumas reinicializacoes/falhas de carregamento de midia. Isto deve ser investigado antes de teste longo e antes de qualquer ativacao por systemd, mas nao impediu o run controlado de permanecer ativo ate o timeout.

## Dados Gerados

- Midias em `/data/media/kiosky-player`: antes `0`, depois `5` arquivos, totalizando `19.877.088` bytes.
- Estado em `/data/state/kiosky-player`: antes `0`, depois `3` arquivos, totalizando `4.973` bytes.
- Arquivo `/tmp/kiosky-status.json`: criado e copiado para o artefato.
- Status sanitizado no snapshot: `playback_state=playing`, `playlist_size=5`, `mpv_running=true`.

O README nao reproduz URLs, nomes privados de midia, identificadores de campanha ou qualquer conteudo da config.

## Analise dos avisos MPV/IPC

Analise feita localmente a partir dos artefatos extraidos em `/tmp/totem-kiosky-manual-review`, sem executar nada na placa.

Analise complementar: [02_ANALISE_PRIMEIRO_RUN_KIOSKY.md](../../../../app-integration/02_ANALISE_PRIMEIRO_RUN_KIOSKY.md).

- Janela do `app-run`: de aproximadamente 14:33:22 a 14:38:25, com `Signal 15` registrado ao final por causa do timeout controlado.
- `MPV IPC unresponsive`: 21 ocorrencias no stdout do app, aproximadamente entre 14:33:35 e 14:38:23.
- A cadencia foi frequente, perto de um aviso a cada 13-14 segundos durante boa parte do run.
- Cada aviso de IPC foi registrado com `restarting`, indicando restart interno do MPV pelo watchdog do app.
- `Failed to load media, restarting MPV`: 5 ocorrencias, aproximadamente em 14:35:23, 14:36:05, 14:36:33, 14:37:43 e 14:38:10.
- As linhas de falha de load nao imprimem identificador de midia. Pela sequencia sanitizada, elas ocorreram em transicoes de playlist antes de retries bem-sucedidos, nao como falha definitiva de uma unica midia.
- Todas as 5 midias da playlist apareceram em linhas `Playing` durante o run; cada alias sanitizado de midia apareceu 6 vezes.
- O app continuou rodando depois dos avisos: houve novas linhas `Playing` apos as falhas, e o encerramento ocorreu por timeout do probe.
- O status final sanitizado indicava `playback_state=playing`, `playlist_size=5`, `mpv_running=true`, `consecutive_failures=0`, `blocked_media_count=0`, `last_poll_error=null` e `last_render_error=null`.
- A observacao humana de tela preta ou retorno ao terminal e compativel com restarts/falhas de load do MPV, mas a causa nao fica concluida pelos artefatos porque nao ha captura de tela e o stderr/stdout do MPV foram descartados pelo app.
- O filtro de kernel/display permaneceu igual antes/depois no probe, sem novo erro de DRM/HDMI associado ao run.

## Escrita Em /opt

A auditoria com marcador temporal nao encontrou escrita em `/opt/totem/kiosky-player` apos o inicio do app.

## Processos Remanescentes

- Antes do teste: nenhum processo real `kiosk.py` ou `mpv` do usuario `totem`.
- Depois do timeout: nenhum processo real `kiosk.py` ou `mpv` do usuario `totem`.
- A lista global depois do teste mostrou apenas o proprio comando `pgrep` como self-match, sem processo remanescente real.

## Kernel E Servicos

- `systemctl --failed` antes e depois do probe: `0 loaded units listed`.
- O filtro critico nao mostrou `Oops`, `panic`, `EXT4-fs error`, `Aborting journal`, `Remounting filesystem read-only`, `mmc timeout/reset` ou alerta de `voltage`.
- O filtro critico ainda mostrou mensagens conhecidas de boot com `Error applying setting, reverse things back` para UART/SPI/MMC.

## Observacao Humana

Midia fisicamente visivel na tela: confirmado pelo operador.

Observacao visual sanitizada:

- Algumas midias do app apareceram fisicamente na tela durante o run.
- Tambem houve momentos de tela preta ou retorno ao terminal.
- Esta observacao e registro humano de bancada; a causa nao fica concluida somente pelos artefatos.

## Escopo Negativo Confirmado

- Nenhum comando `apt` foi executado.
- Nenhum pacote foi instalado.
- A config privada nao foi editada nem impressa.
- Nao houve novo deploy do app.
- Nenhum servico systemd da aplicacao foi instalado, habilitado ou iniciado.
- Nenhum servico foi alterado.
- Midia/cache/state nao foram apagados.
- Nenhum commit foi feito nesta rodada.

## Recomendacao

Classificar a rodada como aprovada para o objetivo de primeiro run manual controlado: o app iniciou como `totem`, usou a config privada, criou cache/estado/status, permaneceu ativo ate o timeout e nao deixou processos remanescentes.

Como os avisos de IPC/restart foram frequentes, nao liberar ainda teste longo nem ativacao por systemd. O proximo passo recomendado e um segundo teste manual curto e direcionado, ainda sem systemd, com mais instrumentacao de MPV/IPC e, se necessario, teste isolado das midias associadas aos retries de load por alias sanitizado.
