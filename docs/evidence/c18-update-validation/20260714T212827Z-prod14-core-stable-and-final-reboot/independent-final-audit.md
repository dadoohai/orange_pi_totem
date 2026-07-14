# Independent final audit

Data: 2026-07-14. Escopo: decidir se `prod14 + C25B + C21.12` pode substituir
`prod8 + C23` como referencia de distribuicao. Tres auditores independentes
GPT-5.5 xhigh trabalharam somente no escopo atual e nao editaram o repo.

## Vereditos

- Evidencia offline: GO, zero blockers. Recomputou checksums, validou 65 JSONs,
  reexecutou o gate M5 do player, os gates apply/rollback/restored do core e o
  gate de promotion stable.
- Placa viva read-only: GO, zero blockers. Confirmou marker prod14, chaves SSH,
  config presente, C21.12/C20.14, C25B sem previous, dois timers ativos,
  player com zero restart, um MPV com `v4l2request-copy`, quadros avancando,
  zero unit falhada e nenhuma quarentena.
- Claim e direcao macro: GO, zero blockers. Confirmou que os non-claims limitam
  futuros players, `latest` amplo, frota/telemetria, assinatura no device,
  media-system e o caso de ativacao/F5.

O gate global `c18_ota_release_gate.py --json` tambem passou com exit `0` no
commit `a676ff9`, repo limpo.

## Diagnosticos nao bloqueantes

- O gate operacional rodado depois do reboot permanece vermelho somente por
  ausencia, no boot novo, do journal do apply. Ele nao foi apresentado como
  verde; os gates nas fases aplicaveis passaram.
- Alguns sidecars estaticos de deep-health repetem hashes de campanhas
  anteriores, mas samples, snapshots, summaries e gates decisivos sao novos.
- O timer do core disparou novamente as `2026-07-14T21:39:45Z`; executou
  `apply_noop_already_current` e nao mudou `state.json`.
- O runbook citava um nome generico de resumo pos-reboot; foi alinhado aos dois
  arquivos realmente usados, core e player.

## Decisao central

Promover `prod14 + C25B + C21.12` como referencia de distribuicao. O GO e
estreito: nao autoriza futuros alvos de player, rollout amplo por grupos ou
afirma que a pendencia visual de ativacao/F5 foi resolvida.
