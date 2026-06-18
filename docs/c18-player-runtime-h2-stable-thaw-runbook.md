# C18 Player-Runtime H2 Stable/Thaw Runbook

Runbook final para quando o piloto assistido ja tiver passado e a rodada quiser
avaliar H2/stable/producao. Ele nao antecipa producao: sem power-loss 17/17,
sem soak 24h e sem decisao humana real, os gates devem continuar vermelhos.

## Ordem Canonica

1. Completar e commitar a matriz fisica power-loss 17/17.
2. Rodar e commitar o soak 24h com a mesma configuracao candidata.
3. Manter a familia server-side/signature verde, atual e hash-bound para o pacote alvo.
4. Gerar rascunhos fail-closed de stable promotion e thaw decision.
5. Preencher os JSONs finais somente depois de H2 estar pronto para revisao.
6. Rodar `c18_stable_promotion_gate.py`.
7. Rodar `c18_player_runtime_h2_readiness_gate.py`.
8. So depois disso qualquer decisao de execucao/publicacao pode ser discutida.

Antes de uma sessao fisica de power-loss, rode o preflight H2 da placa:
`scripts/board/c18_player_runtime_h2_powerloss_preflight_collect.py` no board e
`scripts/qa/c18_player_runtime_h2_powerloss_preflight_gate.py` off-board contra
o plano da matriz. Esse passo evita iniciar cortes com pacote, imagem,
evidence root ou topologia errados, mas nao conta como power-loss nem substitui
os 17 diretórios reais validados pelo evidence gate.

Depois de cada sessao fisica, puxar o diretorio de evidencia para
`docs/evidence/c18-update-validation/`, validar off-board com o gate
correspondente, confirmar que todos os arquivos relevantes estao rastreados por
Git e commitar antes de rodar qualquer gate final. Evidencia local em `/data`
sem commit nao deve ser usada para H2/stable.

## Regra De Pacote

No desenho C18 atual, nao gerar manifest `player-runtime channel=stable`. O alvo
de pacote continua sendo o release homologation validado, por exemplo
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`. `stable` aparece
nos artefatos de promocao, decisao e policy, nao como manifest stable do
`player-runtime`.

Tambem nao usar `releases/app-updates` como alternativa para atualizar
`kiosky-player` ou `player-runtime`: esse root e historico C14/kiosky e nao e
caminho C18 corrente. Mudancas nesses roots devem ser tratadas como frente
`player-runtime` governada, com release gate proprio, H2/stable/thaw quando
aplicavel, e nunca como OTA comum de `totem-core`.

## Soak 24h

Na placa, com o player real rodando a configuracao candidata:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/board/c18_playback_soak_collect.py \
  --cycles 24 \
  --cycle-duration-sec 3600 \
  --evidence-scope endurance-candidate \
  --output-dir /data/evidence/c18-playback-soak-24h-<utc> \
  --match-process-ipc \
  --json
```

O resumo aceito pelo H2 precisa ser `dadooh.c18.playback.soak.v1`, cobrir no
minimo 24h e manter zerados os contadores criticos de restart, media failure,
panfrost, mmc e ext4.

## Rascunhos Fail-Closed

Depois de existir power-loss 17/17, soak 24h e server-side/signature real, gere
os rascunhos:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_player_runtime_stable_decision_draft_build.py \
  --output-dir docs/evidence/c18-update-validation/<utc>-h2-stable-thaw-drafts-9bebaf1 \
  --h1-release-gate-summary docs/evidence/c18-update-validation/20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80/h1-release-gate.json \
  --release-gate-summary releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/c18-player-runtime-release-gate.json \
  --server-side-evidence releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/c18-server-side-publish-governance.json \
  --server-side-current-dir docs/evidence/c18-update-validation/20260617T191658Z-server-side-current-mpv-stuck-fix-9bebaf1 \
  --server-side-trust-anchor-evidence docs/evidence/c18-update-validation/20260617T191658Z-server-side-governance-mpv-stuck-fix-9bebaf1/c18-server-side-trust-anchor.json \
  --soak-summary docs/evidence/c18-update-validation/<soak-24h-dir>/soak-summary.json \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/<checkpoint-01> \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/<checkpoint-02> \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/<...17-checkpoints...> \
  --expect-image-tag c18-hwdecode-lab-1x \
  --expect-image-sha256 1a853f569b5da9e856439897c95612d719fd3059f12349fa1040a6350c3df2f2 \
  --expect-image-marker-sha256 59739f57cdb3f79ac4c8ce5e5e1f9c4aa6d9dae58f704010f8423e66abe2bb9e \
  --json
```

Os arquivos gerados devem falhar fechado ate serem preenchidos por operador:

- `c18-stable-promotion-draft.json`;
- `c18-player-runtime-thaw-decision-draft.json`;
- `README.md`.

Antes do H2, o mesmo builder deve continuar bloqueando sem escrever rascunhos
quando faltar soak 24h ou a matriz power-loss 17/17. O snapshot negativo
pre-H2 de `9bebaf1` esta versionado em
`docs/evidence/c18-update-validation/20260618T045000Z-stable-thaw-draft-build-blocked-pre-h2-9bebaf1/`:
ele usa os artefatos reais de H1, release gate e server-side, mas aponta o
soak 24h para um caminho ausente e fornece apenas os 5 checkpoints P0 do
piloto. O resultado esperado e `passed=false`,
`result_claim=stable_thaw_decision_drafts_blocked`,
`stable_authorized=false`, `thaw_authorized=false` e nenhum diretorio de saida
criado. Esse snapshot nao reduz nenhum blocker H2 e nao autoriza stable, thaw,
publish, auto-pull ou producao.

## Campos Finais

`c18-stable-promotion-evidence.json` precisa manter:

```json
{
  "schema": "dadooh.c18.stable_promotion.v1",
  "component": "player-runtime",
  "channel": "stable",
  "approved": true,
  "physical_homologation_passed": true,
  "powerloss_matrix_passed": true,
  "powerloss_semantics_complete": true,
  "soak_endurance_passed": true,
  "server_side_governance_passed": true,
  "release_gate_passed": true,
  "h2_readiness_passed": true,
  "explicit_operator_decision": true,
  "operator": "<operator-id>",
  "rollback_owner": "<rollback-owner-id>",
  "h1_release_gate_sha256": "<sha256>",
  "release_gate_sha256": "<sha256>",
  "h2_readiness_sha256": "<sha256>",
  "server_side_evidence_sha256": "<sha256>",
  "server_side_current_snapshot_sha256": "<sha256>",
  "server_side_trust_anchor_evidence_sha256": "<sha256>",
  "soak_summary_sha256": "<sha256>",
  "powerloss_matrix_sha256": "<sha256>",
  "auto_pull_enabled": false,
  "public_player_runtime_thaw": false
}
```

O campo `h1_release_gate_sha256` e o hash do H1 decisivo OTA, enquanto
`release_gate_sha256` e o hash do release gate do pacote `player-runtime`
`c18-player-runtime-release-gate.json`. O campo `h2_readiness_sha256` e o hash
do conjunto de entradas H2 calculado pelos gates
`c18_stable_promotion_gate.py` e `c18_player_runtime_h2_readiness_gate.py`; ele
nao e o hash do artefato final `h2-readiness-final.json` salvo no diretorio de
fechamento.

`c18-player-runtime-thaw-decision.json` precisa manter janela UTC curta, no
maximo 4h:

```json
{
  "schema": "dadooh.c18.player_runtime.thaw_decision.v1",
  "component": "player-runtime",
  "channel": "stable",
  "approved": true,
  "acknowledges_h2_evidence": true,
  "explicit_operator_decision": true,
  "rollback_ready": true,
  "auto_pull_enabled": false,
  "thaw_execution_performed": false,
  "operator": "<operator-id>",
  "rollback_owner": "<rollback-owner-id>",
  "target_package_version": "c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1",
  "target_source_commit": "9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522",
  "target_payload_sha256": "d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0",
  "h1_release_gate_sha256": "<sha256>",
  "release_gate_sha256": "<sha256>",
  "powerloss_matrix_sha256": "<sha256>",
  "soak_summary_sha256": "<sha256>",
  "server_side_evidence_sha256": "<sha256>",
  "server_side_current_snapshot_sha256": "<sha256>",
  "server_side_trust_anchor_evidence_sha256": "<sha256>",
  "stable_promotion_evidence_sha256": "<sha256>",
  "window": {
    "start_utc": "<YYYY-MM-DDTHH:MM:SSZ>",
    "end_utc": "<YYYY-MM-DDTHH:MM:SSZ>"
  },
  "non_claims": [
    "this_decision_does_not_execute_thaw",
    "this_decision_does_not_publish_releases",
    "this_decision_does_not_enable_auto_pull",
    "this_decision_does_not_override_freeze_rc_44_by_itself",
    "this_decision_requires_h2_green"
  ]
}
```

## Gates Finais

Stable promotion:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_stable_promotion_gate.py \
  --expected-component player-runtime \
  --evidence docs/evidence/c18-update-validation/<final-dir>/c18-stable-promotion-evidence.json \
  --h1-release-gate-summary docs/evidence/c18-update-validation/20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80/h1-release-gate.json \
  --release-gate-summary releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/c18-player-runtime-release-gate.json \
  --server-side-evidence releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/c18-server-side-publish-governance.json \
  --server-side-current-dir docs/evidence/c18-update-validation/20260617T191658Z-server-side-current-mpv-stuck-fix-9bebaf1 \
  --server-side-trusted-key-pem docs/evidence/c18-update-validation/20260617T191658Z-server-side-governance-mpv-stuck-fix-9bebaf1/c18-server-side-release-signing-key.pub.pem \
  --server-side-trust-anchor-evidence docs/evidence/c18-update-validation/20260617T191658Z-server-side-governance-mpv-stuck-fix-9bebaf1/c18-server-side-trust-anchor.json \
  --soak-summary docs/evidence/c18-update-validation/<soak-24h-dir>/soak-summary.json \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/<checkpoint-01> \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/<...17-checkpoints...> \
  --operator-thaw-decision docs/evidence/c18-update-validation/<final-dir>/c18-player-runtime-thaw-decision.json \
  --expect-image-tag c18-hwdecode-lab-1x \
  --expect-image-sha256 1a853f569b5da9e856439897c95612d719fd3059f12349fa1040a6350c3df2f2 \
  --expect-image-marker-sha256 59739f57cdb3f79ac4c8ce5e5e1f9c4aa6d9dae58f704010f8423e66abe2bb9e \
  --json
```

H2 readiness:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_player_runtime_h2_readiness_gate.py \
  --h1-release-gate-summary docs/evidence/c18-update-validation/20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80/h1-release-gate.json \
  --player-runtime-release-gate-summary releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/c18-player-runtime-release-gate.json \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/<checkpoint-01> \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/<...17-checkpoints...> \
  --soak-summary docs/evidence/c18-update-validation/<soak-24h-dir>/soak-summary.json \
  --stable-promotion-evidence docs/evidence/c18-update-validation/<final-dir>/c18-stable-promotion-evidence.json \
  --server-side-evidence releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/c18-server-side-publish-governance.json \
  --server-side-current-dir docs/evidence/c18-update-validation/20260617T191658Z-server-side-current-mpv-stuck-fix-9bebaf1 \
  --server-side-trusted-key-pem docs/evidence/c18-update-validation/20260617T191658Z-server-side-governance-mpv-stuck-fix-9bebaf1/c18-server-side-release-signing-key.pub.pem \
  --server-side-trust-anchor-evidence docs/evidence/c18-update-validation/20260617T191658Z-server-side-governance-mpv-stuck-fix-9bebaf1/c18-server-side-trust-anchor.json \
  --operator-thaw-decision docs/evidence/c18-update-validation/<final-dir>/c18-player-runtime-thaw-decision.json \
  --expect-image-tag c18-hwdecode-lab-1x \
  --expect-image-sha256 1a853f569b5da9e856439897c95612d719fd3059f12349fa1040a6350c3df2f2 \
  --expect-image-marker-sha256 59739f57cdb3f79ac4c8ce5e5e1f9c4aa6d9dae58f704010f8423e66abe2bb9e \
  --json
```

O diretorio final versionado deve conter, no minimo:

- `c18-stable-promotion-evidence.json`;
- `c18-player-runtime-thaw-decision.json`;
- `h2-readiness-final.json`;
- README com non-claims e hashes.
