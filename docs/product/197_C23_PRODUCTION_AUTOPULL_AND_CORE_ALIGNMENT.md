# 197 - C23 production auto-pull e alinhamento do core

Estado em 2026-07-11: fechado na imagem `c18-hwdecode-prod-8`.

## O que está operacional

- `totem-core`: auto-pull stable público ativo; `latest` alinhado em C21.10;
- `player-runtime`: C23 aplicado pelo timer de produção, com no-op, rollback e
  restauração já provados;
- imagem prod8: C21.9 embutido como baseline e C21.10 adotado remotamente;
- rollback local continua disponível e testado para os dois componentes;
- `player-runtime` permanece bloqueado no CLI público (`rc=44`), sem thaw por
  inferência;
- MPV/kernel/hwdecode continuam fora do OTA comum.

## Fechamentos desta rodada

O roundtrip de C23 está em
`docs/evidence/c18-update-validation/20260711T175205Z-prod8-m5-production-autopull-c23/`.

O alinhamento stable de `totem-core` está em
`docs/evidence/c18-update-validation/20260711T213618Z-totem-core-stable-alignment-prod8/`.

A release C21.10 não muda o comportamento do produto em relação ao C21.9 da
imagem. Ela corrige o ponteiro remoto antigo que era recusado com `rc=45` e
deixa novas placas prod8 capazes de convergir pelo timer normal.

## Regra para as próximas entregas

- wizard, setup, status e lógica operacional: pacote `totem-core` stable;
- player e reprodução: pacote `player-runtime` exato, governado separadamente;
- MPV, ffmpeg, kernel, DTB e imagem base: nova imagem, não OTA comum;
- mídia, playlist, configuração e cache: dados operacionais, não release.

Toda nova release precisa manter gate verde, rollback conhecido, teste de
no-op e prova em placa antes de substituir o `latest`. Não reabrir C21.10 para
novo escopo: a próxima mudança funcional recebe nova versão e nova evidência.

## Limites honestos

Este fechamento não cria rollout por grupos, dashboard de frota ou assinatura
no dispositivo. Também não transforma atualização de imagem/kernel em OTA.
Esses itens seguem como evolução de escala, sem invalidar o auto-pull
operacional agora fechado.
