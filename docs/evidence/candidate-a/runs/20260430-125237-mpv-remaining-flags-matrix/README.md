# MPV remaining flags matrix

Data: 2026-04-30

## Objetivo

Testar, sem iniciar `kiosk.py`, as diferencas restantes entre o perfil MPV do
app com `low_resource_mode=false` e o perfil simples que ja havia reproduzido
video corretamente no teste isolado.

Paths reais, URLs, API keys, identificadores privados, nomes privados e payloads
privados: nao publicados.

## Aliases testados

| Alias | Papel na matriz |
| --- | --- |
| `<media-path:e7efe47f02>` | Midia que ja avancava no app |
| `<media-path:89207012a7>` | Midia H.264 que nao avancava no app |
| `<media-path:8f9272521c>` | Midia HEVC que nao avancava no app |

Os paths reais foram resolvidos internamente na placa a partir dos aliases
sanitizados e nao foram publicados.

## Variacoes

| Variacao | Descricao |
| --- | --- |
| V0 | Perfil app atual com `low_resource_mode=false` |
| V1 | V0 + `--no-config` |
| V2 | V0 sem `--loop-file=inf` |
| V3 | V0 sem `--keep-open=yes` |
| V4 | V0 sem `--image-display-duration=inf` |
| V5 | V0 + `--vo=gpu --gpu-context=drm --ao=null` |
| V6 | Perfil simples aprovado, controle positivo |

Cada combinacao foi observada por 9s via IPC curto, medindo `time-pos`,
`estimated-frame-number`, `pause`, `idle-active`, `eof-reached` e `duration`.

## Resultado

| Alias | Variacao | Time-pos avancou | Frame avancou | Pause | Idle | EOF | Exit code |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| `<media-path:e7efe47f02>` | V0 | Sim | Sim | Nao | Nao | Nao | 0 |
| `<media-path:e7efe47f02>` | V1 | Sim | Sim | Nao | Nao | Nao | 0 |
| `<media-path:e7efe47f02>` | V2 | Sim | Sim | Nao | Nao | Nao | 0 |
| `<media-path:e7efe47f02>` | V3 | Sim | Sim | Nao | Nao | Nao | 0 |
| `<media-path:e7efe47f02>` | V4 | Sim | Sim | Nao | Nao | Nao | 0 |
| `<media-path:e7efe47f02>` | V5 | Sim | Sim | Nao | Nao | Nao | 0 |
| `<media-path:e7efe47f02>` | V6 | Sim | Sim | Nao | Nao | Nao | 0 |
| `<media-path:89207012a7>` | V0 | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:89207012a7>` | V1 | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:89207012a7>` | V2 | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:89207012a7>` | V3 | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:89207012a7>` | V4 | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:89207012a7>` | V5 | Sim | Sim | Nao | Nao | Nao | 0 |
| `<media-path:89207012a7>` | V6 | Sim | Sim | Nao | Nao | Nao | 0 |
| `<media-path:8f9272521c>` | V0 | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:8f9272521c>` | V1 | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:8f9272521c>` | V2 | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:8f9272521c>` | V3 | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:8f9272521c>` | V4 | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:8f9272521c>` | V5 | Sim | Sim | Nao | Nao | Nao | 0 |
| `<media-path:8f9272521c>` | V6 | Sim | Sim | Nao | Nao | Nao | 0 |

Detalhe numerico relevante:

| Alias | V0 delta time/frame | V5 delta time/frame | V6 delta time/frame |
| --- | ---: | ---: | ---: |
| `<media-path:e7efe47f02>` | 8.000s / 240 | 7.667s / 230 | 7.633s / 229 |
| `<media-path:89207012a7>` | 0.033s / 1 | 8.000s / 240 | 7.600s / 228 |
| `<media-path:8f9272521c>` | 0.000s / 0 | 8.000s / 191 | 7.667s / 183 |

## Variacao que resolveu

V5 resolveu os dois aliases problematicos testados e nao quebrou o alias que ja
funcionava. V6 tambem funcionou, como controle positivo.

As variacoes abaixo nao resolveram os aliases problematicos:

- V1: adicionar apenas `--no-config`.
- V2: remover apenas `--loop-file=inf`.
- V3: remover apenas `--keep-open=yes`.
- V4: remover apenas `--image-display-duration=inf`.

## Menor alteracao candidata

A menor alteracao candidata identificada nesta matriz e adicionar ao perfil MPV
do app:

```text
--vo=gpu --gpu-context=drm --ao=null
```

Essa mudanca preserva o restante do perfil V0 e foi suficiente para fazer as
midias H.264 e HEVC problematicas avancarem `time-pos` e frame.

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

## Recomendacao

Proximo passo recomendado: aplicar no `kiosky-player` a saida explicita
`--vo=gpu --gpu-context=drm --ao=null`, manter `mpv_query_uses_fresh_ipc=true`,
redeployar e repetir o observer do app real por 300s.

Se a mudanca resolver no app real, fazer uma rodada menor para confirmar se o
trio inteiro e necessario ou se `--gpu-context=drm` combinado com `--vo=gpu` ja
basta. A mudanca operacional recomendada, ate haver esse refinamento, e aplicar
o trio validado por V5.
