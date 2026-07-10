# C22 player-runtime package roundtrip

- Data: 2026-07-10
- Alvo: `c18.player-runtime-homolog-20260710-c22-c023eae`
- Payload SHA256: `4b5ee5435be0fb3d21d0cf3661c5eac94a9348aa77e1cd8f5613d5ee66740e16`
- Resultado: `passed=true`

O pacote `homologation` foi validado e exercitado na placa lab pela rota local
governada, sem GitHub, publicacao externa ou alteracao da autorizacao de
auto-pull.

Sequencia comprovada:

1. apply C22, deep-health verde e playback real verde;
2. rollback para o C21 anterior, com playback real verde;
3. reapply do mesmo C22 verificado, novo deep-health verde e playback real
   verde.

Estado final:

- `current`: C22 `c023eae`;
- `previous`: C21 image-transcode `50919f5`;
- `kiosky-player.service`: ativo, `NRestarts=0`;
- MPV: `v4l2request-copy`, VO configurado e nao idle;
- CLI publico de apply/rollback/reconcile: congelado em `rc=44`.

O timer de `player-runtime` foi restaurado ao estado inicial, ativo, mas sua
autorizacao ainda aponta para `9bebaf1`; por isso o servico periodico permanece
`failed` apos a rejeicao segura de downgrade. Reancorar autorizacao e timer e o
marco M5, nao parte deste roundtrip.

Non-claims: nao e `stable`, rollout publico, nova autorizacao de auto-pull nem
prova de zero frame preto em todas as transicoes.
