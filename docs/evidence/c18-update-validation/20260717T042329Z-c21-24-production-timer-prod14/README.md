# C21.24 production timer on prod14

Resultado: a release publica C21.24 foi adotada automaticamente pela placa
`prod14` e completou o roundtrip governado sem regressao observada no OTA.

## Escopo provado

- o timer real disparou em `2026-07-17T04:23:29Z`, baixou a release publica e
  aplicou C21.24 a partir do GitHub;
- o gate pos-timer passou sem blockers;
- uma segunda execucao foi no-op e preservou byte a byte `state.json`, os
  links `current`/`previous` e a invocacao do player;
- rollback governado para C21.23, restauracao remota para C21.24 e os dois
  gates de roundtrip passaram;
- o player permaneceu ativo com `NRestarts=0` e o freeze publico de
  `player-runtime` permaneceu em `rc=44` em todas as coletas;
- apos reboot, C21.24 continuou atual, o timer continuou habilitado/ativo,
  C25B foi reconciliado como verificado e nao havia unidade systemd falha.

## HDMI desconectado

O deep-health pos-reboot foi preservado como evidencia negativa, nao como gate
verde. O conector reportou `disconnected`; por contrato, o launcher ficou em
`display_missing` e nao iniciou MPV. Isso explica integralmente os checks de
playback vermelhos e nao contradiz o roundtrip do totem-core. Playback visual
continua parte da validacao pos-flash da prod15 com HDMI conectado.

## Non-claims

- nao valida visualmente playback sem HDMI;
- nao constroi nem aprova a prod15;
- nao autoriza outro alvo de player-runtime nem remove seu freeze publico;
- nao altera MPV, ffmpeg, kernel, imagem base, midia ou configuracao.
