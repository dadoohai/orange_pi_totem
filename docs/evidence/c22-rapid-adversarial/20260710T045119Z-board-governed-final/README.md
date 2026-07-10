# C22 rapid media fault trial - final

- Data: 2026-07-10
- Schema: `dadooh.c22.rapid_media_fault_trial.v1`
- Resultado: `passed=true`
- Placa restaurada: `production_player_healthy_after_restore=true`

O trial executou somente com config, cache, API e midias sinteticas em `/tmp`.
O servico e os timers foram pausados e restaurados pelo coletor. Configuracao,
midia, symlinks e quarentena reais mantiveram identidade; apenas timestamps de
estado operacional puderam mudar com o restart e a retomada do timer.

Principais resultados no relatorio:

- API 500, lista vazia e download truncado retiveram last-known-good em
  reproducao, com status, MPV e KMS observados;
- sidecar corrompido foi reconstruido e passou decode do primeiro frame;
- 3 aliases e 8 transicoes reais do MPV foram observados;
- 20 capturas KMS validas, sem preto persistente;
- mismatch status/MPV teve sequencia maxima de 2 amostras;
- recuperacao e player real pos-restauracao ficaram verdes.

Aviso preservado: `kmsgrab` continuo nao atravessa a troca de formato DRM
`NV12/AR24`. O relatorio nao faz claim de zero frame preto sem captura HDMI.

Arquivos:

- `c22_rapid_media_fault_trial_report.json`: resumo governado e sanitizado;
- `samples.ndjson`: amostras sanitizadas de status, IPC e KMS.
