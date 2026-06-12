# 192 - C18 Homologation RC

Status em 2026-06-12: **Homologation RC pronta para piloto assistido**.

Este documento consolida o norte macro da C18 apos o fechamento do gate de
piloto. Ele nao substitui `docs/UPDATE_CONTRACT.md`; apenas torna explicito o
estado de entrega: OTA funcional em homologacao, com producao/stable ainda
bloqueados pelos gates H2.

## Objetivo

Fechar uma C18 Homologation RC: OTA C18 funcional ponta a ponta em
homologacao, com:

- `totem-core` como OTA manual comum;
- `player-runtime` somente no caminho assistido de piloto;
- manifest `channel=homologation`;
- ring operacional `pilot`;
- freeze publico preservado com `rc=44`;
- rollback pronto;
- gates verdes para homologacao;
- evidencia versionada e auditavel.

Producao, `stable`, auto-pull e public thaw permanecem bloqueados.

## Matriz de responsabilidade

| Frente | Responsabilidade | Estado da RC |
| --- | --- | --- |
| `totem-core` | OTA C18 comum: wizard, splash, status, writer, validadores, helpers e settings | Funcional como OTA manual/operator-triggered; policy, timer, freeze, downgrade e rollback cobertos pelo release gate |
| `player-runtime` | `kiosk.py`, launcher do player, flags de MPV, timing/sync/duracao/playlist | Funcional somente como piloto assistido em `homologation`; nao e public thaw |
| `media-system` | MPV, ffmpeg, hwdecode, panfrost, wrapper, HDMI/display, kernel, DTB, U-Boot e BSP | Congelado nesta RC; qualquer mudanca exige imagem/homologacao propria |
| `field-data` | config real, seed, midia, cache, playlist e estado local | Operacional em `/data`; nao e release de software |

## Evidencia de fechamento

Pacote alvo de `player-runtime`:

- versao: `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`;
- componente: `player-runtime`;
- canal: `homologation`;
- source commit: `c16fb3ed01f0ce25c8203e5fe1d60baf60a75749`;
- payload sha256:
  `d74a552f364de0e454a01a6fe839a1581d16c1b74acb357dc92c28a3ec0524a7`.

Evidencia principal:

- H1 decisivo:
  `docs/evidence/c18-update-validation/20260611T192940Z-1x-h1-decisive-release-gate-refresh/h1-release-gate.json`;
- autorizacao:
  `docs/evidence/c18-update-validation/20260611T182922Z-board-lab-apply-c16fb3e/pilot-authorization-h1-refresh.json`;
- observacao/preflight da placa:
  `docs/evidence/c18-update-validation/20260611T182922Z-board-lab-apply-c16fb3e/board-preflight-post-apply-observation.json`;
- fechamento final:
  `docs/evidence/c18-update-validation/20260612T040055Z-pilot-readiness-final-c16fb3e/pilot-readiness-final.json`.

P0 power-loss seletivo contado para piloto:

- `after_current_symlink`;
- `rollback_after_current_to_previous`;
- `rollback_after_previous_removed`;
- `rollback_after_quarantine`;
- `rollback_after_state_success`.

## Verificacao off-board

Comandos rerodados em 2026-06-12 sobre a arvore limpa da RC:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_release_gate.py --json
```

Resultado: `passed=true`.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_player_runtime_release_gate.py \
  --manifest releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json \
  --payload releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz
```

Resultado: `passed=true`.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_player_runtime_pilot_readiness_gate.py \
  --package-manifest releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json \
  --package-payload releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz \
  --h1-release-gate-summary docs/evidence/c18-update-validation/20260611T192940Z-1x-h1-decisive-release-gate-refresh/h1-release-gate.json \
  --authorization docs/evidence/c18-update-validation/20260611T182922Z-board-lab-apply-c16fb3e/pilot-authorization-h1-refresh.json \
  --preflight docs/evidence/c18-update-validation/20260611T182922Z-board-lab-apply-c16fb3e/board-preflight-post-apply-observation.json \
  --preflight-stage post_apply_observation \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/20260612T001436Z-p0-after-current-symlink-c16fb3e \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/20260612T010313Z-p0-rollback-current-to-previous-c16fb3e \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/20260612T012322Z-p0-rollback-after-previous-removed-c16fb3e \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/20260612T025112Z-p0-rollback-after-quarantine-c16fb3e \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/20260612T035520Z-p0-rollback-after-state-success-c16fb3e \
  --expect-image-tag c18-hwdecode-lab-1x \
  --expect-image-sha256 1a853f569b5da9e856439897c95612d719fd3059f12349fa1040a6350c3df2f2 \
  --expect-image-marker-sha256 59739f57cdb3f79ac4c8ce5e5e1f9c4aa6d9dae58f704010f8423e66abe2bb9e \
  --expect-source-commit c16fb3ed01f0ce25c8203e5fe1d60baf60a75749 \
  --json
```

Resultado: `passed=true`, `result_claim=homologation_pilot_ready`.

O H2 readiness gate tambem foi rerodado e permaneceu vermelho pelos bloqueios
esperados:

- matriz fisica power-loss 17/17 incompleta;
- soak 24h ausente;
- stable promotion ausente;
- evidencia real de governanca server-side/signature ausente;
- decisao explicita de thaw ausente.

A semantica de validacao power-loss esta completa no gate off-board: 17/17
checkpoints possuem validadores. O que ainda falta para H2 e a evidencia fisica
dos 12 checkpoints restantes.

## Limites da RC

Esta RC nao autoriza:

- producao;
- `stable`;
- auto-pull;
- public thaw de `player-runtime`;
- publicacao server-side;
- evidencia real assinada/attested para producao;
- substituir soak 24h;
- substituir matriz power-loss 17/17.

A autorizacao do piloto e baseada em janela. Se a execucao operacional ocorrer
fora da janela registrada no JSON de autorizacao, criar nova autorizacao
versionada antes de aplicar em placa ou cliente.

## Proxima rodada

1. Usar esta RC em piloto assistido, com device allowlist, operador presente e
   rollback owner definido.
2. Preservar evidencia de apply, health, rollback e qualquer incidente.
3. Se houver loop/restart/`media_load_failed`, parar o piloto e coletar
   incidente antes de continuar.
4. Depois do piloto, abrir H2: 17/17 power-loss, soak 24h, server-side/signature,
   stable promotion e decisao formal de thaw.

Nota pos-RC: a familia server-side/signature deve passar por
`scripts/qa/c18_server_side_publish_governance_gate.py` antes de ser consumida
pelo H2. Esse gate e offline, nao publica releases nem habilita auto-pull, e
agora rejeita evidencia apenas declaratoria: exige artefatos reais no diretorio
da release, sem symlink/out-of-dir, provas de attestation/assinatura com hashes
conferidos, audit-log hash-bound, canal, auto-pull off, allowlist, staged
rollout, rollback e auditoria. Assinatura destacada e verificada offline com
prova JSON canonica, fingerprint SPKI DER da chave publica, `release_set_sha256`,
chave publica externa via `--trusted-key-pem` e evidencia de trust anchor
separada via `--trust-anchor-evidence`; H2/stable carregam o hash dessa
evidencia. Essa evidencia nao afirma cadeia PKI, rejeita claims PKI extras e
rejeita symlink em qualquer componente do caminho da chave ou do trust anchor.
Fixture nao passa fora de self-test; producao ainda exige evidencia real
assinada com chave operacional.
O H2 tambem reporta um ledger de semantica da matriz power-loss. Na RC atual
esse ledger esta completo; para producao ainda falta coletar e commitar os 12
checkpoints fisicos restantes.
Stable tambem fica atras de `scripts/qa/c18_stable_promotion_gate.py`; evidencia
minima com apenas `approved=true` nao autoriza build nem publish stable, e no H2
os hashes declarados precisam bater com as evidencias consumidas. Nos scripts de
build/publish stable, o gate deve receber os caminhos dos artefatos reais; usar
somente `--evidence` falha fechado.
