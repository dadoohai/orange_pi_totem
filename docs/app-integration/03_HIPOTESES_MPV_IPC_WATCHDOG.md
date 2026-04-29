# Hipoteses MPV IPC e watchdog

Data da analise: 2026-04-29

## Resumo executivo

A base A da Orange Pi continua parecendo saudavel. As duas rodadas recentes mostram que o MPV inicia de forma consistente e cria o socket IPC em todas as geracoes observadas. O problema aparece depois do startup: o watchdog pinga o IPC, uma unica falha de ping vira restart imediato, e esse restart compete com o `playback_loop` durante ou perto de transicoes de midia.

A hipotese mais forte nao e "MPV nao sobe". O padrao mais provavel e uma combinacao de:

- watchdog reiniciando MPV apos uma unica falha de `ping`;
- watchdog rodando em paralelo com `loadfile` e fechando o socket enquanto outra thread ainda tenta usar o IPC;
- MPV ficando pouco responsivo durante reproducao/transicao em DRM/KMS, o que transforma o ping em falso positivo.

O teste A/B com `mpv_ipc_timeout_sec=5` enfraquece a hipotese de timeout puramente agressivo. O timeout maior reduziu levemente pings falhos, mas manteve 31 restarts e piorou falhas de `loadfile`.

Nao ha evidencia forte, nos artefatos analisados, de problema sistemico de kernel/SD, permissao DRM, systemd, sync, telemetria, hotkeys ou UI de configuracao.

## Escopo da analise

Esta analise usou apenas codigo local e artefatos locais ja coletados:

- `orange_pi_totem`: branch `foundation-v0.1`.
- `kiosky-player`: `/home/builder/kiosky-player`, branch `appliance-v0.1`, commit `7a5f75c`.
- Rodada `20260429-172733-kiosky-manual-probe-generation-logs`.
- Rodada `20260429-174349-kiosky-manual-probe-ipc-timeout-5s`.

Nao foi usado SSH, nenhum comando foi executado na Orange Pi, `kiosk.py` nao foi iniciado, MPV nao foi iniciado, nenhum pacote foi instalado e nenhum artefato bruto foi apagado.

## Fatos observados

### Rodada com logs por geracao

- `MPV IPC startup wait complete`: 32/32.
- `MPV process started`: 32.
- `Restarting MPV`: 31.
- `MPV IPC unresponsive`: 21.
- `MPV IPC command timeout`: 27.
- `MPV IPC ping failed`: 21.
- `MPV IPC ping ok`: 1.
- `Failed to load media`: 10.
- `MPV loadfile returned error`: 10.
- `MPV loadfile result`: 28 sucessos.
- `Media load retry failed`: 0.
- Falhas de load concentradas em 2 aliases sanitizados.
- 10 geracoes MPV foram curtas, menores que 12 KiB, sem referencia a midia no log bruto.
- Status final sanitizado: `playback_state=playing`, `playlist_size=5`, `mpv_running=true`, `consecutive_failures=0`, `blocked_media_count=0`.

### Rodada A/B com timeout IPC 5s

- `MPV IPC startup wait complete`: 32/32.
- `MPV process started`: 32.
- `Restarting MPV`: 31.
- `MPV IPC unresponsive`: 18.
- `MPV IPC command timeout`: 22.
- `MPV IPC ping failed`: 18.
- `MPV IPC ping ok`: 1.
- `Failed to load media`: 13.
- `MPV loadfile returned error`: 15.
- `MPV loadfile result`: 24 sucessos.
- `Media load retry failed`: 2.
- Falhas de load espalhadas por mais aliases sanitizados.
- Status final sanitizado continuou favoravel.

### Fatos de codigo relevantes

- `MPVController._open_ipc()` espera o socket aparecer e conecta no socket Unix; nas rodadas, esse passo passou em todas as 32 geracoes.
- `MPVController._send()` usa `_ipc_lock` para serializar comandos IPC, mas `restart()` / `_stop_locked()` fecham o IPC sem adquirir esse lock.
- `MPVController.ping()` usa `get_property idle-active` com resposta esperada e timeout `mpv_ipc_timeout_sec`.
- `watchdog()` chama `mpv.ensure_running()`, executa um unico `mpv.ping()` e reinicia imediatamente se o ping retorna falso.
- `playback_loop()` tambem chama `mpv.ensure_running()`, executa `mpv.load_file()`, e se falhar chama `mpv.restart(reason=media_load_failed:...)` e tenta carregar de novo.
- Nao ha flag de "transicao em andamento" nem supressao do watchdog durante `loadfile`.
- Nao ha contador de falhas consecutivas de ping antes de reiniciar.
- `mpv_ipc_timeout_sec` e usado para ping e `loadfile` com resposta quando `mpv_debug_events=true`.
- `watchdog_interval_sec=10` explica a cadencia de restarts: intervalo de watchdog + timeout IPC + custo de restart.
- `media_load_retry_cooldown_sec` so atua quando o segundo `loadfile`, apos restart, tambem falha.
- `sync_enabled=false` no perfil appliance; quando falso, o `playback_loop` desativa resync, daily zero e checkpoints UTC.
- `hotkeys_enabled=false`, `config_ui_enabled=false`, `telemetry_enabled=false` e `preload_next=false` no perfil appliance.
- `hwdec=auto-safe` e `mpv_msg_level=all=v` estavam ativos nas rodadas instrumentadas.

## Matriz de hipoteses

| Hipotese | Probabilidade | Evidencias a favor | Evidencias contra | Trechos/funcoes do codigo relacionados | Teste minimo para validar | Risco de testar | Impacto esperado se confirmada |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Watchdog reinicia MPV apos uma unica falha de ping | Alta | `watchdog()` reinicia imediatamente quando `mpv.ping()` retorna falso; 21 pings falhos viraram 21 restarts na rodada baseline; com timeout 5s ainda houve 18 restarts por IPC; status final continuou `playing`, sugerindo possiveis falsos positivos. | Pode haver travamento real do IPC em parte dos casos; so 1 ping OK em cada rodada. | `watchdog()`; `MPVController.ping()`; `MPVController.restart()`. | Alterar somente a politica do watchdog para exigir 2 falhas consecutivas de ping antes de restart e repetir probe curto de 300s. | Recuperacao de travamento real fica atrasada por um ciclo de watchdog. | Queda grande de `Restarting MPV reason=ipc_unresponsive`; reducao indireta de falhas `loadfile`; menos tela preta/retorno ao terminal. |
| Watchdog roda durante `loadfile`/transicao e compete com `playback_loop` | Alta | Logs mostram `loadfile` pendente perto de ping timeout; depois o watchdog reinicia e aparecem `Bad file descriptor`, timeout de `loadfile` ou IPC indisponivel; `restart()` fecha IPC sem adquirir `_ipc_lock`; ha double-restart quando watchdog reinicia e em seguida o `playback_loop` reinicia por `media_load_failed`. | Tambem ha pings falhos durante midia longa, nao apenas na borda de transicao. | `MPVController._send()`; `_recv_response()`; `_close_ipc()`; `_stop_locked()`; `restart()`; `watchdog()`; `playback_loop()`. | Alterar somente a serializacao de restart/stop para respeitar a operacao IPC em curso. Repetir probe curto. | Pode atrasar restart enquanto um comando IPC espera timeout. | `Bad file descriptor` deve cair a zero; falhas de load causadas por corrida devem cair; restarts duplos devem desaparecer. |
| Timeout IPC agressivo | Media | Baseline tinha pings falhos com mediana de 2,004s, exatamente o timeout de 2s; `loadfile` com erro tinha mediana de 1,653s. | A/B com 5s reduziu pouco `IPC unresponsive` (21 -> 18) e manteve 31 restarts; `Failed to load media` piorou (10 -> 13) e surgiram 2 retries falhos. | `_ipc_timeout()`; `_send()`; `_recv_response()`; `ping()`; `load_file()`. | Nao priorizar novo aumento. Se necessario, testar somente timeout depois de corrigir watchdog/concorrencia. | Teste com timeout maior aumenta tempo de tela preta e mascara corrida. | Se confirmado isoladamente, pings falhos cairiam muito sem aumentar falhas de load; isso nao aconteceu no A/B. |
| `_recv_response()` ou parsing de respostas/eventos do MPV falhando | Media | `_recv_response()` descarta linhas que nao correspondem ao `request_id` atual; usa `time.time()` e nao `monotonic`; nao registra eventos descartados; respostas atrasadas podem ficar no buffer ate serem descartadas em comando posterior. | Ha um unico comando com resposta por vez via `_ipc_lock`; comandos bem-sucedidos respondem rapidamente; os erros observados se correlacionam mais com timeout/restart/fechamento do socket. | `_send()`; `_recv_response()`. | Instrumentar somente contagem de eventos/respostas descartadas e IDs vistos, sem imprimir payloads. Probe curto. | Log extra pode aumentar volume, mas baixo se agregado. | Se confirmado, ajuste de parser/observabilidade reduziria timeouts falsos sem mexer no watchdog. |
| MPV fica ocupado durante load/transicao ou reproducao e nao responde ao ping | Alta | Socket IPC sempre aparece; pings falham depois do startup; aumento para 5s ainda encontra MPV sem resposta; MPV pode continuar exibindo ou recuperar depois, pois status final fica `playing`; falhas ocorrem perto de transicoes e tambem durante midia longa. | Sem telemetria direta de MPV no momento exato do ping; os logs MPV nao provam travamento interno. | `ping()`; `load_file()`; `watchdog()`; `playback_loop()`. | Histerese no watchdog: nao reiniciar no primeiro ping falho e registrar se o ping seguinte volta a OK. Probe curto. | Pode atrasar recuperacao de hang real. | Se confirmado, o player deve tocar com menos restarts mesmo que alguns pings falhem. |
| Midia especifica problematica | Media | Na rodada baseline, `Failed to load media` ficou concentrado em 2 aliases sanitizados. | No A/B com timeout 5s as falhas se espalharam por todos os aliases; todas as 5 midias tocaram em logs; falhas muitas vezes acontecem apos watchdog fechar IPC. | `playback_loop()`; `media_load_retry_cooldown_sec`; `media_load_log_context()`. | Depois de estabilizar watchdog/IPC, repetir probe curto e ver se falhas continuam nos mesmos aliases. So entao testar midias isoladas com MPV manual. | Baixo, desde que nao publique nomes/URLs/payloads. | Se confirmada, recodificar/remover midia problematica reduziria `loadfile` failure, mas nao explicaria todos os pings. |
| `hwdec=auto-safe` causa overhead ou falha | Media | Logs MPV mostram tentativas de hwdec/CUDA/VAAPI indisponiveis e fallback para software; `DR failed - disabling` e `Using software decoding` se repetem; startup/restart frequente amplifica esse custo. | O IPC aparece em todas as geracoes; MPV manual DRM/KMS funcionou; o problema principal se correlaciona mais com watchdog/IPC. | `build_mpv_args()`; config `hwdec`; `low_resource_mode` e `--hwdec-codecs`. | A/B curto alterando somente `hwdec` para desabilitado, mantendo timeouts e watchdog conforme a variante em teste. | Pode aumentar CPU se algum decode por hardware estivesse funcionando; deve ser curto. | Se confirmado, menos warnings/custo de decode e menos timeouts durante reproducao. |
| `mpv_msg_level=all=v` / logging piora comportamento | Baixa a media | Logs por geracao somaram 1,44 MiB e 1,26 MiB em 5 minutos; verbose logging aumenta trabalho e I/O em `/tmp`. | Volume nao e alto para explicar 31 restarts; logging e efeito amplificado pelos restarts, nao causa clara; `mpv_msg_level` nao deve gerar eventos IPC por si so. | `build_mpv_args()`; `mpv_log_file`; `mpv_msg_level`; `mpv_debug_events`. | A/B curto alterando somente `mpv_msg_level` para vazio, mantendo captura minima do app. | Menor visibilidade diagnostica na rodada. | Se confirmado, reduzir logging diminuiria timeouts sem mexer em watchdog/hwdec. |
| `sync_enabled` / sincronismo interfere | Baixa | O codigo de sync pode forcar resync/hard resync quando ativo. | Perfil appliance e docs da rodada indicam `sync_enabled=false`; quando falso, o loop limpa flags de sync e nao executa NTP/resync. | `playback_loop()`; `run_ntp_sync_command()`; config `sync_enabled`. | Nenhum teste agora; apenas manter `sync_enabled=false` nas variantes. | Nulo. | Pouco impacto esperado nesta fase. |
| Telemetry/config UI/hotkeys interferem | Baixa | Sao threads/recursos adicionais quando ativos; config UI poderia chamar `mpv.set_property()`. | Perfil appliance desativa `telemetry_enabled`, `config_ui_enabled` e `hotkeys_enabled`; `ConfigServer.start()` retorna cedo; `telemetry_worker()` retorna cedo; hotkeys nao criam conf quando desativadas. | `ConfigServer.start()`; `telemetry_worker()`; `ensure_hotkey_conf()`; `build_mpv_args()`. | Nenhum teste agora; manter desativado. | Nulo. | Pouco impacto esperado. |
| Bug de permissoes/DRM | Baixa | MPV roda em DRM/KMS em ambiente minimo; logs tem ruido de TTY/VT e DRM. | MPV manual aprovado como root e `totem`; app inicia MPV 32/32; display/DRM kernel antes/depois sem novo erro; `systemctl --failed=0`. | `build_mpv_args()`; grupos `video`/`render` validados em rodadas anteriores. | Nenhum teste agora; so reavaliar se aparecer erro DRM novo em logs. | Baixo. | Se confirmado, exigiria ajuste de permissao/display, mas evidencias atuais nao apontam para isso. |
| Problema sistemico/kernel/SD | Baixa | Qualquer instabilidade de I/O/kernel poderia afetar MPV. | Rodadas nao mostram `Oops`, `panic`, erro EXT4, remount read-only, `mmc timeout/reset` ou servicos falhados; base A ja passou por validacoes de boot/rede/stress leve. | Fora do `kiosky-player`; evidencias em diagnostics da base. | Nenhum teste agora; continuar checando filtros criticos nos probes curtos. | Baixo. | Se confirmado, mudaria foco para base OS/hardware, mas probabilidade atual e baixa. |

## Hipoteses descartadas ou de baixa prioridade

- Startup IPC do MPV: baixa prioridade, porque `MPV IPC startup wait complete` foi 32/32 nas duas rodadas.
- Systemd da aplicacao: fora de causa nesta fase, porque os runs foram manuais e ainda sem service habilitado/iniciado.
- Sync/sincronismo: baixa prioridade, porque `sync_enabled=false` e `sync_ntp_command=""` no perfil appliance.
- Telemetria, UI de configuracao e hotkeys: baixa prioridade, porque estao desativadas no perfil appliance.
- Permissoes DRM como causa principal: baixa prioridade, porque MPV manual funcionou como `totem` e o app cria processo/socket em todas as geracoes.
- Kernel/SD como causa principal: baixa prioridade, porque os filtros criticos dos diagnosticos permanecem limpos.

## Proximos testes recomendados

1. Mudar somente a politica do watchdog para nao reiniciar MPV apos uma unica falha de ping.

   Variante minima: exigir 2 falhas consecutivas de `ping` antes de `mpv.restart(reason="ipc_unresponsive")`, mantendo `mpv_ipc_timeout_sec=2`, `mpv_startup_timeout_sec=10`, `hwdec=auto-safe`, `mpv_msg_level=all=v` e `mpv_debug_events=true`.

   Melhora: `Restarting MPV reason=ipc_unresponsive` cai fortemente, `MPV process started` fica muito abaixo de 32, `Failed to load media` nao aumenta e `Media load retry failed` fica zero.

   Piora: pings falhos continuam consecutivos, MPV para de exibir midia, status final deixa de ficar `playing` ou `mpv_running=true`, ou aumenta tempo de tela preta.

2. Mudar somente a coordenacao de IPC/restart.

   Variante minima: garantir que `restart()` / `_stop_locked()` nao fechem o socket enquanto `_send()` / `_recv_response()` estao usando o IPC. Nao mudar timeout, `hwdec` ou logging neste teste.

   Melhora: `MPV IPC command send failed ... Bad file descriptor` cai a zero, restarts duplos desaparecem e `Failed to load media` cai mesmo que algum ping ainda falhe.

   Piora: deadlock, parada sem restart, ou aumento claro de timeouts por comandos aguardando lock.

3. Mudar somente `hwdec` para uma variante sem hardware decode.

   Variante minima: `hwdec` vazio/desabilitado em probe curto, mantendo o restante igual a variante anterior aprovada. Nao mudar timeout, watchdog, logging ou midias no mesmo teste.

   Melhora: queda de timeouts IPC e falhas `loadfile`, menor ruido de hwdec nos logs MPV e nenhuma piora visual observada.

   Piora: aumento de CPU percebido, travamento de video, mais timeouts ou mais tela preta.

## Criterios para liberar teste mais longo

Liberar um teste manual mais longo somente depois de um probe curto demonstrar:

- `MPV IPC startup wait complete` continua 100%.
- `Restarting MPV` cai para valor baixo e explicavel; alvo inicial: no maximo 1 ou 2 restarts em 300s.
- `MPV IPC command send failed` com `Bad file descriptor` fica zero.
- `Media load retry failed` fica zero.
- `Failed to load media` fica zero ou raro, sempre com recuperacao imediata.
- Todas as midias esperadas aparecem em logs sanitizados e na tela.
- Status final segue `playback_state=playing`, `mpv_running=true`, `consecutive_failures=0`, `blocked_media_count=0`.
- Nenhum processo `kiosk.py` ou `mpv` remanescente apos timeout controlado.
- `systemctl --failed` permanece `0 loaded units listed`.
- Sem `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`.
- Nenhuma escrita em `/opt/totem/kiosky-player`.

## Criterios para liberar systemd no futuro

Systemd deve continuar bloqueado agora. A liberacao futura deve exigir:

- Pelo menos uma rodada curta estavel com watchdog/IPC corrigido.
- Um teste manual mais longo aprovado sem restarts recorrentes do MPV.
- Encerramento limpo sem processos remanescentes.
- Evidencia de que `/tmp/kiosky` e runtime/status/IPC sao criados de forma idempotente.
- Logs e status sem secrets, URLs completas, payloads privados ou nomes de campanha publicados.
- `systemctl --failed=0` antes e depois dos testes manuais.
- Nenhum erro critico de kernel, filesystem ou MMC.
- Decisao explicita de unit futura, sem misturar com teste de estabilidade do player.
