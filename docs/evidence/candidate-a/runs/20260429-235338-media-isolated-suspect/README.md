# Media isolated suspect probe

Data: 2026-04-29

## Objetivo

Validar o script `media_isolated_probe.sh` e executar um teste isolado da midia suspeita sem iniciar `kiosk.py`, sem ativar systemd, sem alterar configuracao privada e sem apagar midia/cache/state.

Midia testada:

- Alias sanitizado de midia: `media-c3a1e9fd9a`
- Path sanitizado: `<media-path:e7efe47f02>`
- Path real: nao publicado
- Tipo/extensao: `.mp4`
- Tamanho: 1449280 bytes
- Codec: h264
- Resolucao: 1080x1920
- FPS: 30
- Duracao observada por `ffprobe`: 10.000000s
- Duracao configurada no player: 10000 ms

Host usado: redigido.

## Validacao do script

O script foi revisado e ajustado antes da execucao final.

Confirmacoes:

- aceita apenas path local absoluto;
- rejeita argumento com `://`;
- rejeita path fora de `/data/media/kiosky-player`;
- executa MPV como usuario `totem`;
- nao inicia `kiosk.py`;
- nao altera cache/state do player;
- nao apaga midia/cache/state;
- usa timeout de 60s por padrao;
- captura logs MPV em runtime e copia para o artefato;
- gera artefato `.tar.gz` em `/root/totem-diag`;
- nao publica o path real da midia nos metadados seguros do script.

Validacoes locais:

| Comando | Resultado |
| --- | --- |
| `bash -n scripts/board/media_isolated_probe.sh` | OK |
| `bash -n scripts/board/*.sh scripts/remote/*.sh` | OK, validado por loop arquivo a arquivo |
| `git diff --check` | OK |

## Artefatos analisados

Artefato final do probe isolado:

- `media-isolated-20260429-235535-0300.tar.gz`

Diagnostico final:

- `totem-diag-20260429-235604-0300.tar.gz`

Observacao: houve uma primeira execucao anterior (`media-isolated-20260429-235301-0300`) que validou exit codes, mas nao preservou os logs MPV porque o log estava apontado para um diretorio inacessivel ao usuario `totem`. O script foi corrigido e a analise abaixo usa a execucao final `20260429-235535`.

## Summary.tsv

| Etapa | Exit code | Resultado |
| --- | ---: | --- |
| `pre-systemctl-failed` | 0 | OK |
| `pre-command-mpv` | 0 | OK |
| `media-stat-sanitized` | 0 | OK |
| `media-ffprobe` | 0 | OK |
| `mpv-isolated-vo-null-totem` | 0 | OK |
| `mpv-vo-null-log-copy` | 0 | Log copiado, 11687 bytes |
| `mpv-isolated-drm-totem` | 0 | OK |
| `mpv-drm-log-copy` | 0 | Log copiado, 46307 bytes |
| `post-systemctl-failed` | 0 | OK |
| `post-journalctl-kernel-critical-filter` | 0 | OK |

## Resultado vo=null

Comando sanitizado:

- MPV como `totem`
- `--vo=null`
- `--ao=null`
- timeout 60s
- log MPV capturado

Resultado:

- Exit code: 0
- Inicio: `2026-04-29T23:55:36-0300`
- Fim: `2026-04-29T23:55:47-0300`
- Conclusao: MPV decodificou a midia e saiu por EOF antes do timeout.
- `stderr`: vazio
- Log MPV: `mpv-vo-null.log`, 11687 bytes

Linhas relevantes sanitizadas:

- Video observado: h264 1080x1920 30.000fps
- Saida: `Exiting... (End of file)`

Nao houve erro fatal de container ou decode no teste `vo=null`.

## Resultado DRM/KMS

Comando sanitizado:

- MPV como `totem`
- `--vo=gpu`
- `--gpu-context=drm`
- `--ao=null`
- `--hwdec=auto-safe`
- timeout 60s
- log MPV capturado

Resultado:

- Exit code: 0
- Inicio: `2026-04-29T23:55:47-0300`
- Fim: `2026-04-29T23:55:59-0300`
- Conclusao: MPV tocou a midia via DRM/KMS e saiu por EOF antes do timeout.
- `stderr`: `Cannot load libcuda.so.1`
- Log MPV: `mpv-drm.log`, 46307 bytes

Linhas relevantes sanitizadas:

- Video observado: h264 1080x1920 30.000fps
- Saida: `Exiting... (End of file)`
- Warnings/ruidos nao fatais observados:
  - `Failed to set up VT switcher`
  - `Failed to load CUDA symbols`
  - `Cannot load libcuda.so.1`
  - `DR failed - disabling`

Esses avisos nao impediram playback: o exit code foi 0 e o MPV chegou a EOF.

## Systemd e kernel

`systemctl --failed` antes/depois do probe:

```text
0 loaded units listed.
```

Filtro critico de kernel no artefato do probe:

- Sem linhas.

Filtro critico de kernel no diagnostico final:

- Sem linhas reais.

Nao houve evidencia de `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`.

## Observacao humana da tela

Observacao posterior do operador: visualmente essa midia sempre aparece na tela e nao houve problema visual aparente nela nas rodadas anteriores. Isso reforca que a falha registrada como `loadfile` pode estar ligada a outra midia, ao estado anterior do MPV, ou a transicao para esse alias, e nao necessariamente ao arquivo isolado.

## Interpretacao

O teste isolado nao confirma corrupcao da midia. Pelo contrario: a midia suspeita decodificou com `vo=null`, tocou via DRM/KMS como usuario `totem` e terminou por EOF em ambos os testes.

Isso enfraquece a hipotese de arquivo intrinsecamente invalido. A concentracao de falhas no alias `media-c3a1e9fd9a` ainda e relevante, mas agora parece mais provavel que o problema esteja na transicao para essa midia dentro do app, na midia imediatamente anterior, na resposta IPC ao `loadfile`, ou na interacao com watchdog/restart durante a playlist.

## Recomendacao

Nao remover nem recodificar a midia com base apenas nas falhas anteriores.

Proximo teste recomendado:

1. Criar um probe manual de transicao controlada, ainda sem `kiosk.py`.
2. Tocar uma midia conhecida boa.
3. Enviar `loadfile` para `media-c3a1e9fd9a` via IPC MPV.
4. Tocar uma proxima midia conhecida boa.
5. Capturar tempos de resposta do IPC, log MPV e exit codes.

Se a transicao controlada passar, o foco volta para a camada do app: concorrencia entre `playback_loop`, watchdog e restart, em vez de problema de arquivo.
