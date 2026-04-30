# Homologacao board 2 - classificacao de midias

Data: 2026-04-30

## Objetivo

Auditar a playlist real da placa de homologacao v0.1-rc1 para distinguir itens
de video, imagem estatica e desconhecidos. A auditoria foi motivada pela rodada
`20260430-172509-homologation-rc1-board2-observer`, em que o app rodou por
300 segundos com metricas internas limpas, mas o observer externo recebeu
`property unavailable` para `time-pos` e `estimated-frame-number`.

Placa: homologacao, IP redigido.

Paths reais, URLs privadas, API keys, identificadores privados, nomes privados
e payloads privados nao foram publicados.

## Artefatos

Artefatos brutos copiados para esta pasta:

- `playlist-media-classification-20260430-174802-0300.tar.gz`
- `playlist-media-classification-20260430-174830-0300.tar.gz`
- `totem-diag-20260430-171407-0300.tar.gz`
- `totem-diag-20260430-172459-0300.tar.gz`
- `totem-diag-20260430-174844-0300.tar.gz`

A analise usa `playlist-media-classification-20260430-174830-0300.tar.gz`. A
rodada `174802` foi superseded localmente porque uma regra inicial classificava
`hevc` em `.mp4` como imagem; isso foi corrigido antes da analise final.

Os conteudos extraidos foram analisados localmente em `extracted/`, que deve
permanecer ignorado pelo Git.

## Resumo

| Metrica | Valor |
| --- | ---: |
| Total de itens na playlist | 15 |
| Arquivos locais resolvidos | 15 |
| Videos com progresso esperado | 15 |
| Imagens estaticas | 0 |
| Desconhecidos | 0 |
| `ffprobe` disponivel | sim |
| Fonte preferida usada | `playlist_last.json` |
| `cache_index.json` presente | sim |

## Classificacao por alias

| Alias | Tipo classificado | Extensao | Tamanho bytes | Codec | Resolucao | FPS | Duracao config | Duracao real | Criterio esperado |
| --- | --- | --- | ---: | --- | --- | ---: | ---: | ---: | --- |
| `<media-path:fece6ae2c0>` | `video_progress_expected` | `.mp4` | 705184 | h264 | 480x704 | 24 | 5.100s | 5.131610s | `time-pos` e frame devem avancar |
| `<media-path:89207012a7>` | `video_progress_expected` | `.mp4` | 15197894 | h264 | 1080x1920 | 30 | 7.000s | 16.064218s | `time-pos` e frame devem avancar |
| `<media-path:e7efe47f02>` | `video_progress_expected` | `.mp4` | 1449280 | h264 | 1080x1920 | 30 | 10.000s | 10.000000s | `time-pos` e frame devem avancar |
| `<media-path:8f9272521c>` | `video_progress_expected` | `.mp4` | 752257 | hevc | 720x1280 | 24 | 8.600s | 8.568186s | `time-pos` e frame devem avancar |
| `<media-path:c406539999>` | `video_progress_expected` | `.mp4` | 1772473 | h264 | 480x848 | 30 | 15.100s | 15.069751s | `time-pos` e frame devem avancar |
| `<media-path:b46ef64c86>` | `video_progress_expected` | `.mp4` | 681484 | h264 | 480x864 | 24 | 5.100s | 5.131610s | `time-pos` e frame devem avancar |
| `<media-path:c58db4e1cc>` | `video_progress_expected` | `.mp4` | 2049253 | h264 | 360x640 | 23.976024 | 30.800s | 30.805000s | `time-pos` e frame devem avancar |
| `<media-path:97100fcdae>` | `video_progress_expected` | `.mp4` | 476811 | h264 | 480x688 | 30 | 5.100s | 5.061950s | `time-pos` e frame devem avancar |
| `<media-path:47a2783e11>` | `video_progress_expected` | `.mp4` | 1206242 | h264 | 360x640 | 23.976024 | 18.000s | 17.995458s | `time-pos` e frame devem avancar |
| `<media-path:70272d6fff>` | `video_progress_expected` | `.mp4` | 1050186 | h264 | 360x640 | 24 | 14.100s | 14.101000s | `time-pos` e frame devem avancar |
| `<media-path:31af3d58a2>` | `video_progress_expected` | `.mp4` | 443106 | h264 | 480x848 | 29.743590 | 3.900s | 3.900000s | `time-pos` e frame devem avancar |
| `<media-path:019653682e>` | `video_progress_expected` | `.mp4` | 679443 | h264 | 360x640 | 24 | 9.100s | 9.131000s | `time-pos` e frame devem avancar |
| `<media-path:f45759145c>` | `video_progress_expected` | `.mp4` | 18588311 | h264 | 1080x1920 | 25 | 10.000s | 10.000000s | `time-pos` e frame devem avancar |
| `<media-path:b99d7d9575>` | `video_progress_expected` | `.mp4` | 727477 | h264 | 480x720 | 24 | 5.100s | 5.131610s | `time-pos` e frame devem avancar |
| `<media-path:9e48f6362b>` | `video_progress_expected` | `.mp4` | 700683 | h264 | 480x720 | 24 | 5.000s | 5.041667s | `time-pos` e frame devem avancar |

## Duracao configurada versus real

Quatorze itens possuem duracao configurada proxima da duracao real medida por
`ffprobe`. O alias `<media-path:89207012a7>` continua sendo excecao conhecida:
duracao configurada de `7.000s` contra duracao real de `16.064218s`. Mesmo
assim, ele e video e deve apresentar progressao de `time-pos` e frames durante
a janela configurada.

## Cruzamento com o observer anterior

Na rodada `20260430-172509-homologation-rc1-board2-observer`:

- os 15 aliases da playlist apareceram em `status-samples`;
- todos os 15 aliases estao classificados como `video_progress_expected`;
- nenhum alias e imagem estatica;
- nenhum alias e `unknown`;
- nenhum alias tem justificativa de tipo de midia para aceitar
  `property unavailable` em `time-pos` ou `estimated-frame-number`.

Resumo por alias no observer anterior:

| Alias | Tipo | Amostras do alias | `time-pos` numerico | Frame numerico | `time-pos unavailable` | `frame unavailable` |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `<media-path:019653682e>` | video | 11 | 0 | 0 | 11 | 11 |
| `<media-path:31af3d58a2>` | video | 4 | 0 | 0 | 4 | 4 |
| `<media-path:47a2783e11>` | video | 33 | 0 | 0 | 32 | 32 |
| `<media-path:70272d6fff>` | video | 24 | 0 | 0 | 23 | 23 |
| `<media-path:89207012a7>` | video | 14 | 0 | 0 | 14 | 14 |
| `<media-path:8f9272521c>` | video | 14 | 0 | 0 | 14 | 14 |
| `<media-path:97100fcdae>` | video | 9 | 0 | 0 | 9 | 9 |
| `<media-path:9e48f6362b>` | video | 5 | 0 | 0 | 5 | 5 |
| `<media-path:b46ef64c86>` | video | 9 | 0 | 0 | 9 | 9 |
| `<media-path:b99d7d9575>` | video | 5 | 0 | 0 | 5 | 5 |
| `<media-path:c406539999>` | video | 34 | 0 | 0 | 34 | 34 |
| `<media-path:c58db4e1cc>` | video | 59 | 0 | 0 | 59 | 59 |
| `<media-path:e7efe47f02>` | video | 20 | 0 | 0 | 18 | 18 |
| `<media-path:f45759145c>` | video | 9 | 0 | 0 | 8 | 8 |
| `<media-path:fece6ae2c0>` | video | 9 | 0 | 0 | 9 | 9 |

As diferencas entre quantidade de amostras do alias e contagem de
`property unavailable` em alguns itens correspondem a amostras com timeout
parcial do observador externo, nao a progressao numerica.

## Conclusao

A hipotese de playlist mista com imagens nao explica o bloqueio do observer.
A playlist real da placa de homologacao tem 15 itens locais, todos classificados
como videos por extensao, stream de video, codec, resolucao e duracao real.

Portanto, a rodada anterior continua bloqueada para aprovacao integral da RC1:
ha videos que deveriam comprovar avanco de `time-pos` e
`estimated-frame-number`, mas o observer externo recebeu `property unavailable`
para esses campos.

Isso ainda nao prova tela preta ou falha visual do app, porque as metricas
internas do app ficaram limpas. A falha comprovada e de validacao: o criterio
obrigatorio de progressao por video nao foi satisfeito na placa de homologacao.

## Recomendacao

1. Ajustar o observer para validar videos e imagens separadamente, mantendo
   `time-pos`/frame obrigatorios para `video_progress_expected`.
2. Repetir o observer de 300 segundos na placa de homologacao com a mesma
   config candidata.
3. Se `property unavailable` persistir para videos, bloquear a RC1 ate
   identificar se a causa esta na instrumentacao IPC, no MPV/DRM da segunda
   placa ou na reproducao real.
4. Nao avancar para teste manual longo nem validacao de `systemd` antes de
   obter comprovacao de progressao para os videos.
