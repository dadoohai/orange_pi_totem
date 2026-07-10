# C18 M5 production auto-pull C22

Resultado historico v1: `player_runtime_production_autopull_evidence_ready`,
sem blockers para a mecanica exata.

Escopo:

- imagem: `c18-hwdecode-prod-7` / `c18.image-prod.7`;
- alvo remoto exato: `c18.player-runtime-homolog-20260710-c22-c023eae`;
- baseline rollback-safe:
  `c18.player-runtime-homolog-20260703-baseline-bridge-8ac1c63`;
- timer real: `totem-player-runtime-update-agent.timer`;
- updater SHA-256:
  `5497d66cb570e8e5b32f8f1d30898e667f83e620c3c2d65cf4ccfaeaeb6eebe4`.

Sequencia observada:

1. `pre`: bridge ativo, C22 ausente dos links, timer ativo, health verde.
2. Timer disparou em `2026-07-10T19:05:39Z` e buscou a tag exata no GitHub.
3. `post_apply`: C22 ativo, bridge anterior, unit `rc=0`, health verde.
4. `noop`: nova invocacao sem mudar state, links ou marker.
5. `rollback`: bridge ativo, C22 anterior, restart e health verdes.
6. `restored`: C22 ativo, bridge anterior, restart e health verdes.

As cinco fases preservaram o bloqueio publico `rc=44`, timer ativo, um unico
MPV total, progresso de frames e hardware decode esperado. C21 `50919f5`,
rejeitado na preparacao, permaneceu em quarantine; C22 nao foi quarentenado.

`m5-evidence-gate.json` liga os snapshots aos hashes do pacote, manifest,
release gate, autorizacao e evidencia de publicacao exata.

## Reavaliacao posterior

O snapshot `restored` tambem preservou em seu journal um `media_load_failed`
entre as janelas curtas, e falhas iguais voltaram depois da coleta. A RCA esta
em `docs/evidence/c22-playback-ipc-backpressure/20260710T193847Z-verified-rca/`.

O gate atual classifica este conjunto como `mechanics_passed=true` e
`product_distribution_cleanliness_passed=false`: os 30 segundos finais nao
substituem a janela continua de 10 minutos agora exigida. A evidencia original
nao foi reescrita nem descartada; sua claim ficou explicitamente limitada.

Non-claims: nao autoriza `latest` amplo, outros alvos futuros, release direto do
repo legado `kiosky-player`, grupos/canary, assinatura no device ou atualizacao
de `media-system`.
