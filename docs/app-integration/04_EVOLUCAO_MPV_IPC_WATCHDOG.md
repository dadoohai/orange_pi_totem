# Evolucao MPV IPC e watchdog

Data: 2026-04-29

## Resumo executivo

O Candidato A continua nao homologado para producao. A base OS permanece saudavel nas rodadas do `kiosky-player`: `systemctl --failed` ficou em `0 loaded units listed`, nao houve `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`, e a auditoria nao encontrou escrita em `/opt/totem/kiosky-player` apos o inicio do app.

O bloqueio atual nao e boot, filesystem, NetworkManager, DRM/KMS basico ou startup do socket IPC do MPV. O bloqueio esta na integracao app-MPV: o IPC fica pouco responsivo durante o run, o watchdog transforma falhas de ping em restarts, e os restarts competem com `loadfile`/transicoes.

As rodadas recentes confirmaram dois pontos:

- Watchdog agressivo era parte do problema: exigir 2 falhas consecutivas reduziu fortemente o churn de MPV.
- Corrida IPC/restart era parte do problema: serializar fechamento de IPC com comandos zerou `Bad file descriptor` e `MPV IPC command send failed`.

Mesmo assim, `MPV IPC ping failed`, `MPV IPC command timeout` e `MPV IPC unresponsive` continuam frequentes. O proximo teste recomendado e um A/B curto com `mpv_watchdog_ping_failures_before_restart=999`, mantendo os demais campos constantes, para observar se reiniciar por ping IPC e destrutivo demais.

## Linha do tempo

| Rodada | Objetivo | Leitura |
| --- | --- | --- |
| `20260429-144234` primeiro run manual | Validar app manual como `totem`, config privada e caminhos `/data`/`/tmp` | App iniciou, baixou midias, criou estado/status e exibiu algumas midias; aprovado com ressalvas por IPC/restart frequente |
| Analise do primeiro run | Revisar artefatos sem executar nada na placa | 21 `MPV IPC unresponsive`, 5 `Failed to load media`; hipotese inicial: watchdog/IPC/restart |
| `20260429-164413` instrumentado | Habilitar log MPV e eventos debug | Persistiram 31 restarts/32 processos MPV; falhas de load aumentaram para 10 |
| `20260429-172733` logs por geracao | Preservar `mpv-g*.log` por restart | IPC startup completo em 32/32 geracoes; problema deslocado para responsividade posterior |
| `20260429-174349` timeout IPC 5s | Testar se timeout IPC de 2s era agressivo demais | Reduziu levemente timeouts, mas manteve 31 restarts/32 processos e piorou falhas de load |
| `20260429-194954` watchdog threshold 2 | Exigir 2 falhas de ping antes de restart | Reduziu restarts/processos/falhas de load; confirmou watchdog agressivo como fator |
| `20260429-202035` threshold 2 + reset por geracao | Corrigir contador para nao atravessar geracoes MPV | Semantica corrigida, ganho pequeno; restaram timeouts e `Bad file descriptor` |
| `20260429-210204` coordenacao IPC/restart | Serializar fechamento de IPC com comandos em andamento | Zerou `Bad file descriptor` e command send failed; reduziu falhas de load, mas ping IPC segue ruim |

## Tabela comparativa

`n/d` significa que a metrica nao foi publicada no README sanitizado da rodada.

| Rodada | `Restarting MPV` | `MPV process started` | `MPV IPC unresponsive` | `MPV IPC command timeout` | `MPV IPC command send failed` | `Bad file descriptor` | `Failed to load media` | `Media load retry failed` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Primeiro run manual `20260429-144234` | n/d | n/d | 21 | n/d | n/d | n/d | 5 | n/d |
| Instrumentado `20260429-164413` | 31 | 32 | 21 | 25 | 6 | n/d | 10 | 0 |
| Logs por geracao `20260429-172733` | 31 | 32 | 21 | 27 | 4 | n/d | 10 | 0 |
| Timeout IPC 5s `20260429-174349` | 31 | 32 | 18 | 22 | 10 | n/d | 13 | 2 |
| Watchdog threshold 2 `20260429-194954` | 18 | 19 | 11 | 30 | 0 | n/d | 7 | 0 |
| Threshold 2 + reset geracao `20260429-202035` | 17 | 18 | 10 | 28 | 3 | 3 | 7 | 1 |
| Coordenacao IPC/restart `20260429-210204` | 13 | 14 | 11 | 24 | 0 | 0 | 2 | 0 |

## Interpretacao tecnica

O primeiro run provou que o app consegue operar no ambiente minimo: leu a config privada, rodou como `totem`, baixou midias, escreveu em `/data`, criou status em `/tmp` e exibiu conteudo. O problema apareceu como instabilidade operacional do MPV controlado por IPC, nao como falha de deploy ou de permissao basica.

Os logs por geracao foram decisivos porque mostraram `MPV IPC startup wait complete` em todas as geracoes instrumentadas. Isso enfraquece a tese de "MPV nao sobe" ou "socket IPC nao aparece". A falha acontece depois, quando o app tenta comandar ou pingar o MPV durante reproducao/transicao.

O A/B com timeout IPC 5s reduziu alguns timeouts, mas nao reduziu restarts nem processos MPV. Como tambem piorou `loadfile`, timeout agressivo isolado deixou de ser a explicacao principal.

A politica `mpv_watchdog_ping_failures_before_restart=2` confirmou que reiniciar no primeiro ping falho era destrutivo: restarts cairam de 31 para 18 e processos MPV de 32 para 19. O reset por geracao corrigiu a semantica do contador, mas nao resolveu a responsividade.

A coordenacao IPC/restart confirmou a corrida de fechamento de socket: `Bad file descriptor` caiu de 3 para 0 e `MPV IPC command send failed` caiu de 3 para 0. Como `Failed to load media` tambem caiu de 7 para 2, parte relevante das falhas de load vinha de restart competindo com comandos IPC.

## O que foi descartado ou enfraquecido

- Startup do IPC como causa principal: enfraquecido por 32/32 startups completos na rodada com logs por geracao e 14/14 na rodada de coordenacao.
- Timeout IPC puramente agressivo: enfraquecido pelo A/B de 5s, que manteve 31 restarts e piorou falhas de load.
- Systemd da aplicacao: fora da causa atual, porque todas as rodadas foram manuais e nenhum service foi habilitado/iniciado.
- Xorg, Wayland, compositor e Chromium: fora da causa atual, porque MPV manual e app usam DRM/KMS direto.
- Kernel/SD/filesystem como causa principal: baixa prioridade enquanto os filtros criticos continuam limpos.
- Config UI, hotkeys, telemetria e sync: baixa prioridade nas rodadas atuais porque ficaram desativados no perfil testado.

## O que foi confirmado

- O app manual opera nos caminhos esperados: `/opt/totem/kiosky-player` para codigo, `/data/config/config.json` para config privada, `/data/media/kiosky-player` para midia, `/data/state/kiosky-player` para estado e `/tmp/kiosky-status.json` para status.
- A camada OS nao apresentou regressao durante os probes.
- MPV via DRM/KMS continua sendo o caminho tecnico principal.
- Watchdog agressivo contribui para o churn de MPV.
- Fechamento/restart do IPC precisava respeitar comandos em andamento.
- A serializacao IPC/restart reduziu fortemente falhas de load e eliminou `Bad file descriptor`.

## Problema remanescente

O ponto aberto e a responsividade do ping IPC. Na melhor rodada ate agora, `MPV IPC ping failed` ficou em 23, `MPV IPC command timeout` em 24 e `MPV IPC unresponsive` em 11 durante 300 segundos. Mesmo com menos falhas de load e sem `Bad file descriptor`, ainda ha restarts demais para liberar teste longo ou systemd.

## Proximo A/B recomendado

Executar uma rodada curta, ainda sem systemd, mantendo constantes:

- codigo com coordenacao IPC/restart ja deployada;
- `mpv_ipc_timeout_sec=2.0`;
- `mpv_startup_timeout_sec=10.0`;
- `hwdec=auto-safe`;
- `mpv_log_file=/tmp/kiosky/mpv.log`;
- `mpv_msg_level=all=v`;
- `mpv_debug_events=true`;
- playlist/midias e demais campos operacionais.

Alterar somente:

```text
mpv_watchdog_ping_failures_before_restart=999
```

Leitura esperada: se `Restarting MPV`, `MPV process started`, `Failed to load media` e observacao de tela melhorarem sem deixar o player parado, entao reiniciar por ping IPC estava destrutivo demais. Se o player parar de exibir, status final degradar ou processos ficarem remanescentes, entao o ping falho estava detectando travamento real em parte dos casos.

## Criterios para liberar teste mais longo

Liberar teste manual mais longo somente depois de um A/B curto demonstrar:

- `Bad file descriptor=0`.
- `MPV IPC command send failed=0`.
- `Media load retry failed=0`.
- `Failed to load media` zero ou raro, sempre com recuperacao imediata.
- `Restarting MPV` baixo e explicavel; alvo inicial: no maximo 1 ou 2 restarts em 300s.
- Nenhum retorno recorrente ao terminal e nenhuma tela preta prolongada observada.
- Status final `playback_state=playing`, `mpv_running=true`, `consecutive_failures=0` e `blocked_media_count=0`.
- Nenhum processo real `kiosk.py` ou `mpv` remanescente depois do timeout.
- `systemctl --failed` em `0 loaded units listed`.
- Sem `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`.
- Nenhuma escrita em `/opt/totem/kiosky-player`.

## Criterios para liberar systemd futuramente

Systemd da aplicacao continua bloqueado. A liberacao futura deve exigir:

- Pelo menos uma rodada curta estavel com a politica de watchdog definida.
- Um teste manual mais longo aprovado com os criterios acima.
- Encerramento limpo sem processos remanescentes.
- Criacao idempotente de runtime/status/IPC, preferencialmente formalizada na unit com `RuntimeDirectory` ou decisao equivalente documentada.
- Logs e status sem secrets, URLs privadas, payloads, nomes de campanha ou conteudo da config privada em arquivos versionados.
- `systemctl --failed=0` antes e depois dos testes.
- Nenhum erro critico de kernel, filesystem ou MMC.
- Decisao explicita de unit futura, sem misturar enable/start de systemd com a investigacao de estabilidade do player.
