# Estado Atual do Player MPV

> Nota historica: qualquer redeploy/update atual de player ou runtime de midia
> deve seguir [docs/UPDATE_CONTRACT.md](../UPDATE_CONTRACT.md).

Data: 2026-04-30

## Resumo executivo

A base A da Orange Pi Zero 3 continua saudavel e o caminho MPV direto via DRM/KMS segue valido. O `kiosky-player` roda manualmente como usuario `totem`, baixa midias, cria estado/status e nao mostrou regressao de sistema nas rodadas recentes.

O bloqueio curto app-MPV foi resolvido para a candidata atual. A opcao `mpv_query_uses_fresh_ipc=true` estabilizou consultas do watchdog e eliminou timeouts, falhas de ping, restarts e falhas de `loadfile` nas rodadas curtas. Com IPC estavel, o problema restante apareceu como falta de progressao real de `time-pos` e frame em alguns aliases, resolvida no app real ao explicitar a saida MPV.

A configuracao candidata aprovada para homologacao `v0.1-rc1` mantem:

```text
mpv_query_uses_fresh_ipc=true
mpv_vo=gpu
mpv_gpu_context=drm
mpv_ao=null
low_resource_mode=false
```

Essa combinacao passou no observer de 300s do app real na rodada `20260430-133130`, com todos os 5 aliases avancando `time-pos` e `estimated-frame-number`.

## Linha do tempo curta

| Rodada | Descoberta |
| --- | --- |
| MPV manual DRM/KMS | MPV direto funcionou como root e como `totem`, com confirmacao visual. |
| Primeiro app manual e rodadas instrumentadas | App funcionou, mas havia `MPV IPC unresponsive`, restarts e falhas de `loadfile`. |
| Coordenacao IPC/restart | Reduziu churn e zerou `Bad file descriptor`, mas ainda restaram timeouts de ping/estado. |
| Midia isolada e transicao controlada | Arquivo suspeito e transicao simples passaram fora do app. |
| Playlist watchdog sem app | Playlist completa com pings concorrentes passou sem timeouts de ping ou `loadfile`. |
| MPVController playlist probe | `load_file` passou, mas `ping()` e `get_property()` pelo socket persistente deram timeout. |
| Fresh IPC query | `mpv_query_uses_fresh_ipc=true` estabilizou IPC/watchdog/loadfile no app real. |
| Playback observer | Com IPC estavel, 4 aliases ficaram sem avancar `time-pos`/frame; 1 alias avancou. |
| Flags progress probe | Perfil simples avancou as 4 midias problematicas; perfil app/low-resource nao avancou. |
| `low_resource_mode=false` | Removeu flags low-resource fortes, mas nao resolveu no app real. |
| Remaining flags matrix | V5, com `--vo=gpu --gpu-context=drm --ao=null`, fez aliases problematicos avancarem. |
| Observer com saida MPV explicita | Commit `c71318a` passou no app real por 300s com IPC/loadfile estaveis e todos os aliases avancando. |

## O que foi descartado

- Midia corrompida como explicacao principal: a midia suspeita tocou isolada e transicoes simples passaram.
- DRM/KMS basico: MPV manual via DRM/KMS foi aprovado.
- IPC manual por conexao curta: playlist e pings concorrentes passaram fora do app.
- `low_resource_mode` isoladamente: desligar `low_resource_mode` removeu flags fortes, mas nao resolveu no app real.
- `--correct-pts=no` isolado: remover apenas essa flag nao resolveu.
- `--video-sync=audio` isolado: remover apenas essa flag nao resolveu.
- `--loop-file=inf`, `--keep-open=yes` e `--image-display-duration=inf` isolados: remover cada uma separadamente nao resolveu.
- Ausencia de `--no-config` isolada: adicionar apenas `--no-config` nao resolveu os aliases problematicos.

## O que foi confirmado

- `mpv_query_uses_fresh_ipc=true` estabiliza as consultas do watchdog no app real:
  - `MPV IPC command timeout=0`
  - `MPV IPC ping failed=0`
  - `Restarting MPV=0`
  - `Failed to load media=0`
- O problema visual observado depois disso corresponde a falta real de progressao de `time-pos`/frame em alguns aliases, nao apenas a uma impressao visual subjetiva.
- A saida explicita `--vo=gpu --gpu-context=drm --ao=null` faz os aliases problematicos avancarem na matriz isolada e no app real.
- O alias que ja avancava continuou avancando com a saida explicita.
- A rodada `20260430-133130` teve `MPV IPC command timeout=0`, `MPV IPC ping failed=0`, `Restarting MPV=0`, `Failed to load media=0` e todos os 5 aliases avancando tempo/frame.
- As rodadas recentes mantiveram `systemctl --failed` em `0 loaded units listed` e nao mostraram `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`.

## Configuracao candidata atual

Manter:

- MPV direto via DRM/KMS, sem desktop/compositor.
- `mpv_query_uses_fresh_ipc=true`.
- `mpv_vo=gpu`.
- `mpv_gpu_context=drm`.
- `mpv_ao=null`.
- `low_resource_mode=false`.
- Watchdog com intervalo e limites ja usados na rodada aprovada.
- Logs MPV por geracao durante validacao.

Nao alterar nesta etapa:

- API, credenciais ou identificadores privados.
- Cache, estado ou midias.
- Systemd da aplicacao.
- Politica de root read-only.

## Proximo teste obrigatorio

1. Provisionar a homologacao `v0.1-rc1` em uma segunda placa/cartao.
2. Redeployar o `kiosky-player` no commit `c71318a`, sem habilitar `systemd`.
3. Rodar o observer do app real por 300s.
4. Confirmar, por aliases sanitizados:
   - `MPV IPC command timeout=0`
   - `MPV IPC ping failed=0`
   - `Restarting MPV=0`
   - `Failed to load media=0`
   - todos os 5 aliases avancando `time-pos` e frame
   - `pause=false`, `idle-active=false` e sem EOF prematuro durante janelas esperadas
5. Confirmar `systemctl --failed=0` e filtro critico de kernel limpo.

## Criterios para liberar teste longo

Liberar teste manual observado de 30 a 60 minutos somente se a segunda placa/cartao repetir o observer de 300s com a configuracao candidata:

- mantiver IPC/watchdog/loadfile estaveis;
- fizer todos os 5 aliases avancarem;
- nao gerar processos remanescentes reais;
- nao escrever em `/opt` durante o app;
- mantiver `systemctl --failed=0`;
- nao mostrar `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`.

## Criterios para liberar systemd

Liberar unit `systemd` da aplicacao somente depois de:

1. Observer de 300s aprovado com saida explicita.
2. Teste manual mais longo aprovado sem regressao visual, IPC, kernel ou systemd.
3. Politica operacional de logs e artefatos definida.
4. Confirmacao de que cache, estado e config privada continuam fora do Git.
5. Plano de rollback documentado para a mudanca de runtime MPV.

Enquanto esses criterios nao forem atendidos, a aplicacao deve continuar validada manualmente, sem `systemctl enable/start` da unit do `kiosky-player`.
