# Analise de midias problematicas

Data da analise: 2026-04-29

## Resumo executivo

As quatro rodadas locais analisadas apontam para um unico alias sanitizado associado a todas as falhas de `loadfile`: `media-c3a1e9fd9a`, com path local sanitizado `<media-path:e7efe47f02>`.

Esse alias falhou em todas as variantes recentes:

- 2 falhas na rodada `20260429-210204` com coordenacao IPC/restart.
- 5 falhas na rodada `20260429-224248` com `watchdog_interval_sec=17`.
- 3 falhas na rodada `20260429-225755` com `hwdec=no`.
- 6 falhas na rodada `20260429-232254` com grace window fixa de 5s.

Nenhum outro alias teve `Failed to load media` ou `MPV loadfile returned error` nessas quatro rodadas.

A leitura mais prudente e que existe uma midia claramente suspeita para teste isolado, mas ainda nao esta provado que o arquivo em si esteja corrompido. O mesmo alias tambem aparece como `Playing media` 6 vezes em cada rodada, indicando que a midia consegue tocar apos recuperacao/restart. A falha pode estar ligada ao custo de carregar essa midia, a um timeout de IPC durante a transicao para ela, ou a interacao dessa transicao com watchdog/restart.

## Escopo e metodo

Esta analise usou apenas artefatos locais ja coletados. Nao foi usado SSH, nenhum comando foi executado na Orange Pi, MPV nao foi iniciado, `kiosk.py` nao foi iniciado, nenhum pacote foi instalado e nenhum artefato bruto foi apagado.

Rodadas analisadas:

- `20260429-210204-kiosky-manual-probe-ipc-restart-coordination`
- `20260429-224248-kiosky-manual-probe-watchdog-interval-17s`
- `20260429-225755-kiosky-manual-probe-hwdec-no`
- `20260429-232254-kiosky-manual-probe-watchdog-grace-5s`

Artefatos principais usados:

- `app-run.stdout.txt`
- `mpv.log`
- `mpv-generation-logs/*.log`
- `post-data-media-files.stdout.txt`
- `post-kiosky-status.json`

Os aliases abaixo usam somente os identificadores ja sanitizados pelo `kiosky-player`:

- `alias=media-...`: alias de midia derivado da fonte usada pelo player.
- `<media-path:...>`: hash sanitizado do path local em `/data/media`.

Nenhum path completo, URL, nome de arquivo real, nome de campanha, payload privado ou identificador privado foi publicado neste documento.

## Tabela sanitizada por alias

| Alias de midia | Path local sanitizado | Tamanho local | Extensao | Duracao configurada | Video observado em logs MPV | Leitura |
| --- | --- | ---: | --- | ---: | --- | --- |
| `media-95c1895f82` | `<media-path:fece6ae2c0>` | 705184 bytes | `.mp4` | 5100 ms | h264 480x704 24.000fps | Sem falha nas rodadas analisadas |
| `media-cc8cc834f6` | `<media-path:89207012a7>` | 15197894 bytes | `.mp4` | 7000 ms | h264 1080x1920 30.000fps | Sem falha nas rodadas analisadas |
| `media-c3a1e9fd9a` | `<media-path:e7efe47f02>` | 1449280 bytes | `.mp4` | 10000 ms | h264 1080x1920 30.000fps | Suspeita principal |
| `media-402b5e6c8f` | `<media-path:8f9272521c>` | 752257 bytes | `.mp4` | 8600 ms | hevc 720x1280 24.000fps | Sem falha nas rodadas analisadas |
| `media-63e22e276f` | `<media-path:c406539999>` | 1772473 bytes | `.mp4` | 15100 ms | h264 480x848 30.000fps | Sem falha nas rodadas analisadas |

Observacoes:

- Todos os arquivos listados eram `.mp4` nos artefatos locais.
- Os dados de video vieram dos logs MPV sanitizados, correlacionando `Run command: loadfile` com a linha `Video --vid`.
- O alias suspeito tem resolucao vertical 1080x1920 e codec h264, mas outro alias tambem tem h264 1080x1920 sem falhas. Portanto, codec/resolucao sozinhos nao explicam a falha.
- O alias suspeito tem tamanho local relativamente pequeno para 1080x1920. Isso pode ser normal para conteudo curto/comprimido, mas vale verificar isoladamente.

## Frequencia por rodada

| Rodada | Alias | Playing media | Failed to load media | MPV loadfile returned error |
| --- | --- | ---: | ---: | ---: |
| `20260429-210204` | `media-95c1895f82` | 6 | 0 | 0 |
| `20260429-210204` | `media-cc8cc834f6` | 6 | 0 | 0 |
| `20260429-210204` | `media-c3a1e9fd9a` | 6 | 2 | 2 |
| `20260429-210204` | `media-402b5e6c8f` | 6 | 0 | 0 |
| `20260429-210204` | `media-63e22e276f` | 6 | 0 | 0 |
| `20260429-224248` | `media-95c1895f82` | 6 | 0 | 0 |
| `20260429-224248` | `media-cc8cc834f6` | 6 | 0 | 0 |
| `20260429-224248` | `media-c3a1e9fd9a` | 6 | 5 | 5 |
| `20260429-224248` | `media-402b5e6c8f` | 6 | 0 | 0 |
| `20260429-224248` | `media-63e22e276f` | 6 | 0 | 0 |
| `20260429-225755` | `media-95c1895f82` | 6 | 0 | 0 |
| `20260429-225755` | `media-cc8cc834f6` | 6 | 0 | 0 |
| `20260429-225755` | `media-c3a1e9fd9a` | 6 | 3 | 3 |
| `20260429-225755` | `media-402b5e6c8f` | 6 | 0 | 0 |
| `20260429-225755` | `media-63e22e276f` | 6 | 0 | 0 |
| `20260429-232254` | `media-95c1895f82` | 6 | 0 | 0 |
| `20260429-232254` | `media-cc8cc834f6` | 6 | 0 | 0 |
| `20260429-232254` | `media-c3a1e9fd9a` | 6 | 6 | 6 |
| `20260429-232254` | `media-402b5e6c8f` | 6 | 0 | 0 |
| `20260429-232254` | `media-63e22e276f` | 6 | 0 | 0 |

## Evidencia de midia suspeita

Ha uma midia claramente suspeita para o proximo teste isolado:

- Alias de midia: `media-c3a1e9fd9a`
- Path sanitizado: `<media-path:e7efe47f02>`
- Extensao/container observado: `.mp4`
- Tamanho local observado: 1449280 bytes
- Video observado: h264 1080x1920 30.000fps
- Duracao configurada no player: 10000 ms

Motivos:

- E o unico alias com `Failed to load media` nas quatro rodadas analisadas.
- E o unico alias com `MPV loadfile returned error` nas quatro rodadas analisadas.
- As falhas acompanham o mesmo path local sanitizado.
- A concentracao permanece mesmo quando se altera watchdog interval, grace window e `hwdec`.

Limite da conclusao:

- O alias tambem toca 6 vezes por rodada.
- Os erros sao timeouts/erros de `loadfile` via IPC, nao uma mensagem conclusiva de arquivo invalido.
- A falha pode depender do estado anterior do MPV ou da transicao dentro da playlist.

## Recomendacoes de teste isolado

1. Testar primeiro a midia `media-c3a1e9fd9a` isoladamente com MPV manual via DRM/KMS, como usuario `totem`, sem iniciar `kiosky-player`.
2. Rodar o teste por 60s ou ate o fim da midia, capturando log MPV dedicado.
3. Nao usar URL como entrada; usar somente o path local ja presente em `/data/media/kiosky-player`.
4. Nao alterar cache, state, playlist ou status do player.
5. Se o teste isolado falhar, repetir com `--hwdec=no` em uma segunda rodada separada.
6. Se o teste isolado passar, preparar uma rodada de transicao controlada: midia anterior conhecida boa -> midia suspeita -> proxima midia conhecida boa, ainda sem `kiosky-player`.
7. Se a transicao controlada passar, voltar a investigar IPC/watchdog no app, porque o arquivo isolado nao explicaria sozinho a falha.

## Script proposto

Foi preparado o script futuro `scripts/board/media_isolated_probe.sh`.

Uso previsto no board, em uma rodada futura:

```sh
./scripts/board/media_isolated_probe.sh /data/media/kiosky-player/<arquivo-local>
```

O script proposto:

- rejeita argumentos com `://`;
- exige path absoluto local;
- exige arquivo regular existente;
- roda MPV como usuario `totem`;
- usa DRM/KMS via `--vo=gpu --gpu-context=drm`;
- usa `--hwdec=auto-safe` por padrao, com override opcional por `MEDIA_ISOLATED_HWDEC`;
- limita a execucao a 60s por padrao, com override opcional por `MEDIA_ISOLATED_TIMEOUT_SEC`;
- captura log MPV em `/root/totem-diag`;
- nao inicia `kiosky-player`;
- nao escreve em `/data/state` nem altera cache do player;
- gera um `.tar.gz` em `/root/totem-diag`.

## Campos que nao devem ser publicados

Nao publicar em README publico, issue, PR ou comentario:

- path completo em `/data/media/kiosky-player`;
- nome real de arquivo;
- URLs de midia ou API;
- `api_key`;
- `api_url`;
- `environment_id`;
- `station_id`;
- nomes de campanha;
- payloads de playlist;
- conteudo bruto de `cache_index`;
- conteudo bruto de `playlist_last`;
- conteudo bruto de status se tiver identificadores privados;
- logs MPV brutos sem sanitizacao, porque podem conter paths locais reais.

## Proximo passo recomendado

Executar uma rodada isolada somente com `media-c3a1e9fd9a` / `<media-path:e7efe47f02>` usando o script proposto, sem systemd e sem `kiosky-player`.

Resultado esperado para destravar a decisao:

- Se MPV isolado falhar ou demorar perto do timeout, tratar a midia como candidata a recodificacao/remocao e repetir o teste apos trocar o arquivo.
- Se MPV isolado passar, testar transicao controlada envolvendo essa midia.
- Se transicao controlada tambem passar, a suspeita volta para a camada de IPC/watchdog do app, nao para a midia em si.
