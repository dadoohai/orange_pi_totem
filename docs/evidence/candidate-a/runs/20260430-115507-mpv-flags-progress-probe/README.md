# MPV flags progress probe

Data: 2026-04-30

## Objetivo

Testar isoladamente as quatro midias que nao avancaram na rodada `20260430-113008-kiosky-playback-observer`, sem iniciar `kiosk.py`, comparando as flags atuais do app contra variacoes controladas.

Host usado: redigido.

Paths reais, URLs, API keys, identificadores privados, nomes privados e payloads privados: nao publicados.

## Midias testadas

Aliases sanitizados:

- `<media-path:fece6ae2c0>`
- `<media-path:89207012a7>`
- `<media-path:8f9272521c>`
- `<media-path:c406539999>`

Os paths reais foram resolvidos internamente na placa a partir dos hashes sanitizados e nao foram publicados.

## Variacoes

| Variacao | Descricao |
| --- | --- |
| A | Flags app/low-resource atuais |
| B | Igual A, mas sem `--correct-pts=no` |
| C | Igual A, mas sem `--video-sync=audio` |
| D | Perfil simples, proximo ao teste MPV direto aprovado |

Resumo das diferencas:

- A usa `--profile=low-latency`, `--video-sync=audio`, `--correct-pts=no`, `--framedrop=decoder+vo`, `--loop-file=inf`, `--keep-open=yes`, `--vd-lavc-threads=1` e filtros bilinear.
- B remove somente `--correct-pts=no`.
- C remove somente `--video-sync=audio`.
- D usa `--no-config`, `--vo=gpu`, `--gpu-context=drm`, `--ao=null`, `--hwdec=auto-safe` e nao usa o bloco low-resource do app.

Cada combinacao foi observada por 10s via IPC curto, com amostragem de `time-pos`, `estimated-frame-number`, `pause`, `idle-active`, `eof-reached` e `duration`.

## Resultado

| Alias | Variacao | Time-pos avancou | Frame avancou | Pause true | Idle true | EOF true | Exit code |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| `<media-path:89207012a7>` | A | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:89207012a7>` | B | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:89207012a7>` | C | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:89207012a7>` | D | Sim | Sim | Nao | Nao | Nao | 0 |
| `<media-path:8f9272521c>` | A | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:8f9272521c>` | B | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:8f9272521c>` | C | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:8f9272521c>` | D | Sim | Sim | Nao | Sim | Nao | 0 |
| `<media-path:c406539999>` | A | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:c406539999>` | B | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:c406539999>` | C | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:c406539999>` | D | Sim | Sim | Nao | Nao | Nao | 0 |
| `<media-path:fece6ae2c0>` | A | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:fece6ae2c0>` | B | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:fece6ae2c0>` | C | Nao | Nao | Nao | Nao | Nao | 0 |
| `<media-path:fece6ae2c0>` | D | Sim | Sim | Nao | Sim | Nao | 0 |

Detalhe numerico:

| Alias | A delta time/frame | B delta time/frame | C delta time/frame | D delta time/frame |
| --- | ---: | ---: | ---: | ---: |
| `<media-path:89207012a7>` | 0.000s / 0 | 0.033s / 1 | 0.033s / 1 | 9.000s / 269 |
| `<media-path:8f9272521c>` | 0.042s / 1 | 0.000s / 0 | 0.000s / 0 | 8.125s / 194 |
| `<media-path:c406539999>` | 0.033s / 1 | 0.000s / 0 | 0.000s / 0 | 8.700s / 261 |
| `<media-path:fece6ae2c0>` | 0.000s / 0 | 0.000s / 0 | 0.042s / 1 | 4.750s / 114 |

## Interpretacao

O comportamento da rodada anterior foi reproduzido isoladamente: com as flags app/low-resource atuais, as quatro midias ficam praticamente no primeiro frame, mesmo com `pause=false`, `idle-active=false`, `eof-reached=false` e `loadfile` bem-sucedido.

Remover somente `--correct-pts=no` nao resolveu. Remover somente `--video-sync=audio` tambem nao resolveu. Portanto, essas flags isoladas nao explicam o problema inteiro.

O perfil simples fez as quatro midias avancarem `time-pos` e `estimated-frame-number`. A causa fica concentrada no conjunto de flags low-resource/app, nao nos arquivos em si nem no IPC. Os candidatos mais fortes para a proxima rodada sao o bloco low-resource como um todo e, dentro dele, `--profile=low-latency`, `--framedrop=decoder+vo`, `--vd-lavc-threads=1`, filtros bilinear/interpolation e a combinacao com `--loop-file=inf` / `--keep-open=yes`.

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
- `journalctl -k -p crit`: sem entradas.
- O filtro amplo capturou apenas linhas de boot do tipo `Error applying setting, reverse things back` e governors thermal; sem criterio bloqueador.

## Recomendacao

Proximo passo recomendado, sem `systemd`:

1. Fazer A/B no `kiosky-player` com `low_resource_mode=false`, mantendo `mpv_query_uses_fresh_ipc=true`.
2. Se isso resolver, reintroduzir flags uma a uma para isolar a menor mudanca: testar primeiro `--framedrop=decoder+vo`, depois `--profile=low-latency`, depois `--vd-lavc-threads=1`.
3. Manter `--correct-pts=no` e `--video-sync=audio` como suspeitas secundarias: elas nao resolveram isoladamente nesta matriz.
4. Considerar remover `--loop-file=inf` / `--keep-open=yes` em uma rodada separada se o bloco low-resource sozinho nao explicar tudo.
