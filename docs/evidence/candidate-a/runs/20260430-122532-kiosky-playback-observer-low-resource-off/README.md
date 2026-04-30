# Kiosky playback observer low-resource off

Data: 2026-04-30

## Objetivo

Rodar o `kiosky-player` real, sem `systemd`, com `low_resource_mode=false` e
`mpv_query_uses_fresh_ipc=true`, para verificar se as quatro midias que ficavam
paradas passam a avancar `time-pos` e `estimated-frame-number` durante o app.

Host usado: redigido.

Paths reais, URLs, API keys, identificadores privados, nomes privados e payloads
privados: nao publicados.

## Checkout usado

- `kiosky-player`: `8c3b420 Add fresh IPC query probe option`
- Branch local verificada: `appliance-v0.1`
- Worktree local do `kiosky-player`: limpo antes do deploy

## Config confirmada

A config privada foi atualizada sem imprimir o conteudo. Somente os campos
permitidos foram alterados/confirmados, mantendo os demais campos intactos.

| Campo | Valor esperado | Status |
| --- | --- | --- |
| `low_resource_mode` | `false` | OK |
| `mpv_query_uses_fresh_ipc` | `true` | OK |
| `watchdog_interval_sec` | `10` | OK |
| `mpv_watchdog_ping_failures_before_restart` | `2` | OK |
| `mpv_watchdog_grace_after_load_sec` | `0` | OK |
| `mpv_watchdog_grace_after_restart_sec` | `0` | OK |
| `mpv_ipc_timeout_sec` | `2.0` | OK |
| `mpv_startup_timeout_sec` | `10.0` | OK |
| `hwdec` | `auto-safe` | OK |
| `mpv_log_file` | `/tmp/kiosky/mpv.log` | OK |
| `mpv_msg_level` | `all=v` | OK |
| `mpv_debug_events` | `true` | OK |
| owner/mode | `root:totem`, `0640` | OK |

## MPV observado

O log do MPV confirmou que `low_resource_mode=false` removeu as flags
low-resource suspeitas da rodada anterior. A linha de comando observada nao
incluiu:

- `--profile=low-latency`
- `--correct-pts=no`
- `--video-sync=audio`
- `--framedrop=decoder+vo`
- `--vd-lavc-threads=1`

Ainda permaneceram no perfil do app:

- `--keep-open=yes`
- `--loop-file=inf`
- `--image-display-duration=inf`
- leitura da config global do MPV, sem `--no-config`

Essas diferencas agora sao mais relevantes porque o perfil simples da rodada
`20260430-115507-mpv-flags-progress-probe` usava `--no-config`, `--vo=gpu`,
`--gpu-context=drm`, `--ao=null` e nao usava o bloco `keep-open`/`loop-file`.

## Metricas do app

| Metrica | Valor |
| --- | ---: |
| `app-run` exit code | 124 |
| MPV process started | 1 |
| MPV IPC command timeout | 0 |
| MPV IPC ping failed | 0 |
| MPV IPC ping ok | 30 |
| Restarting MPV | 0 |
| Failed to load media | 0 |
| MPV loadfile returned error | 0 |

O exit code `124` e esperado pelo `timeout 300s`.

## Metricas do observador externo

| Metrica | Valor |
| --- | ---: |
| Amostras totais | 299 |
| IPC success | 296 |
| IPC timeout | 0 |
| IPC error | 3 |
| Aliases unicos | 5 |

Os erros IPC externos foram dois `missing_socket` no inicio e um
`ConnectionResetError` no encerramento pelo timeout. Nao houve timeout de IPC.

## Resultado por alias

| Alias | Duracao config | Duracao MPV | Time-pos inicial | Time-pos final | Time avancou | Frame inicial | Frame final | Frame avancou | Pause true | Idle true | EOF true | Amostras |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- | --- | ---: |
| `<media-path:fece6ae2c0>` | 5.100s | 5.131610s | 0.000000 | 0.041667 | Nao | 0 | 1 | Nao | Nao | Nao | Nao | 38 |
| `<media-path:89207012a7>` | 7.000s | 16.064218s | 0.033333 | 0.033333 | Nao | 1 | 1 | Nao | Nao | Nao | Nao | 48 |
| `<media-path:e7efe47f02>` | 10.000s | 10.000000s | 0.466667 | 8.900000 | Sim | 14 | 267 | Sim | Nao | Nao | Nao | 70 |
| `<media-path:8f9272521c>` | 8.600s | 8.568186s | 0.041667 | 0.041667 | Nao | 1 | 1 | Nao | Nao | Nao | Nao | 50 |
| `<media-path:c406539999>` | 15.100s | 15.069751s | 0.033333 | 0.033333 | Nao | 1 | 1 | Nao | Nao | Nao | Nao | 90 |

## Comparacao com a rodada 20260430-113008

| Alias | 20260430-113008 | low_resource_mode=false |
| --- | --- | --- |
| `<media-path:fece6ae2c0>` | Nao avancou | Nao avancou |
| `<media-path:89207012a7>` | Nao avancou | Nao avancou |
| `<media-path:e7efe47f02>` | Avancou | Avancou |
| `<media-path:8f9272521c>` | Nao avancou | Nao avancou |
| `<media-path:c406539999>` | Nao avancou | Nao avancou |

O padrao ficou essencialmente igual ao observado antes: somente
`<media-path:e7efe47f02>` avancou `time-pos` e frame. Os quatro aliases
problematicos continuaram em `pause=false`, `idle-active=false` e
`eof-reached=false`, mas presos no inicio.

## Duracao e troca de midia

O alias `<media-path:89207012a7>` tem duracao configurada menor que a duracao
MPV observada: 7.000s contra 16.064218s. O app portanto troca essa midia antes
do EOF real. Para os demais aliases, a duracao configurada bate de perto com a
duracao observada pelo MPV.

Essa divergencia de duracao nao explica sozinha o travamento visual, porque
`<media-path:fece6ae2c0>`, `<media-path:8f9272521c>` e
`<media-path:c406539999>` tambem nao avancaram mesmo com duracoes configuradas
proximas da duracao real.

## Observacao humana de tela

Nao houve observacao humana direta da tela nesta rodada. A interpretacao acima
vem do observador externo via IPC curto e dos logs sanitizados do app/MPV.

## Systemd e kernel

`systemctl --failed` apos o probe e no diagnostico final:

```text
0 loaded units listed.
```

Filtro critico de kernel:

- Sem `Oops`.
- Sem `panic`.
- Sem erro EXT4.
- Sem remount read-only.
- Sem `mmc timeout/reset`.
- O filtro amplo capturou apenas linhas de boot do tipo `Error applying setting,
  reverse things back` e registros de governors thermal; sem criterio bloqueador.

## Interpretacao

`low_resource_mode=false` nao resolveu o problema no app real. A rodada tambem
mostrou que as flags low-resource mais fortes realmente sairam da linha de
comando, entao a causa provavel agora esta nas diferencas restantes entre o
perfil do app e o perfil simples que avancou no probe isolado.

As principais suspeitas restantes sao:

- `--keep-open=yes`
- `--loop-file=inf`
- `--image-display-duration=inf`
- ausencia de `--no-config`
- diferencas explicitas de saida/audio do perfil simples: `--vo=gpu`,
  `--gpu-context=drm`, `--ao=null`

IPC, watchdog, `loadfile`, DRM/KMS basico e os arquivos de midia continuam sem
evidencia de serem a causa primaria.

## Recomendacao

Proximo passo recomendado, sem `systemd`: criar uma matriz pequena no MPV
isolado e/ou no app com toggles para as diferencas restantes:

1. Perfil app atual com `low_resource_mode=false`, mas sem `--loop-file=inf`.
2. Igual ao anterior, tambem sem `--keep-open=yes`.
3. Igual ao anterior, tambem sem `--image-display-duration=inf`.
4. Perfil app atual com `--no-config`.
5. Perfil app atual adicionando explicitamente `--vo=gpu --gpu-context=drm --ao=null`.

Se uma dessas variacoes fizer os quatro aliases avancarem, aplicar o menor ajuste
no `kiosky-player` e repetir o observer do app real por 300s.
