# 192 - C18 Homologation RC

Status em 2026-06-16: **Homologation RC pronta para piloto assistido**,
com retomada operacional e readiness atual rerodados sobre autorizacao/preflight
frescos. Producao/stable continuam bloqueados por H2.

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
| `totem-core` | OTA C18 comum: wizard, splash, status, writer, validadores, helpers e settings | Funcional como OTA manual/operator-triggered; policy, timer, freeze, downgrade, rollback e allowlist de payload cobertos no gate e no device-side |
| `player-runtime` | `kiosk.py`, launcher do player, flags de MPV, timing/sync/duracao/playlist | Funcional somente como piloto assistido em `homologation`; a frente e mais ampla, mas o payload C18-aware atual esta restrito a `kiosk.py`; nao e public thaw |
| `media-system` | MPV, ffmpeg, hwdecode, panfrost, wrapper, HDMI/display, kernel, DTB, U-Boot e BSP | Congelado nesta RC; guardrails executaveis bloqueiam vazamento para OTA comum; qualquer mudanca exige imagem/homologacao propria |
| `field-data` | config real, seed, midia, cache, playlist e estado local | Operacional em `/data`; guardrails executaveis bloqueiam vazamento para release de software; snapshot publico C18/C7 coleta apenas estado sanitizado e metadados, com evidencia read-only em placa |
| `server-side/publish` | server-side/signature, trust anchor, lista de assets, allowlist, staged rollout e audit | Verde para os artefatos de homologacao atuais; nao publica, nao promove `stable`, nao liga auto-pull e nao abre thaw publico |
| `H2/prod` | gates de producao/stable, power-loss 17/17, soak 24h, stable promotion e decisao formal de thaw | Intencionalmente vermelho antes de H2; nenhuma conclusao de producao pode ser inferida da RC ou do piloto assistido |

## Roots canonicos de artefatos

| Frente | Root canonico | Regra C18 |
| --- | --- | --- |
| `player-runtime` | `releases/player-runtime` | Root do pacote homologation atual e dos artefatos server-side do `player-runtime`; qualquer pacote novo precisa passar no `c18_player_runtime_release_gate.py` e nos gates do canal. |
| `totem-core` | `releases/core-updates` | Root historico/canonico de pacotes core. Artefatos antigos que nao passam no gate C18 atual sao apenas historicos; pacote C18 novo deve ser regenerado e passar `c18_ota_release_gate.py --package-manifest ... --package-payload ...`. |
| `totem-core` | `releases/totem-core` | Nao e root canonico nesta linha; nao usar para RC C18. |
| `kiosky-player` legado | `releases/app-updates` | Historico C14/kiosky; nao usar para C18 OTA/RC, `player-runtime`, `stable` ou producao. |

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
  `docs/evidence/c18-update-validation/20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80/h1-release-gate.json`;
- autorizacao operacional atual:
  `docs/evidence/c18-update-validation/20260616T231448Z-operational-resume-current-2320950/pilot-authorization.json`;
- retomada operacional atual:
  `docs/evidence/c18-update-validation/20260616T231448Z-operational-resume-current-2320950/`;
- pilot readiness atual:
  `docs/evidence/c18-update-validation/20260616T232546Z-current-pilot-readiness-5b2128c/pilot-readiness.json`;
- autorizacao/readiness de 2026-06-12, preservados como rastreabilidade
  historica:
  `docs/evidence/c18-update-validation/20260612T195336Z-pilot-authorization-traceability-refresh/pilot-authorization.json`,
  `docs/evidence/c18-update-validation/20260612T195516Z-pilot-readiness-traceability-refresh-c16fb3e/pilot-readiness.json`;
- snapshot H2 atual, vermelho apenas pelos blockers de producao:
  `docs/evidence/c18-update-validation/20260617T003916Z-current-h2-readiness-c16fb3e/h2-readiness.json`;
- server-side/signature atual:
  `docs/evidence/c18-update-validation/20260617T001804Z-server-side-current-c16fb3e/`;
  `server-side-governance-gate.json` verde para `player-runtime`, trust anchor
  externo verificado e lista de 14 assets assinados/atestados hash-bound; nao
  publica, nao promove `stable`, nao liga auto-pull e nao abre thaw;
- gate macro pre-H2:
  `scripts/qa/c18_ota_macro_governance_gate.py` agrega os snapshots acima com
  `docs/evidence/c18-update-validation/20260612T183722Z-board-readonly-diagnostics-17a1f9d`
  e prova que a governanca de homologacao esta coerente; nao substitui H2,
  nao reabre janela de piloto expirada e nao autoriza producao;
- snapshot macro versionado:
  `docs/evidence/c18-update-validation/20260617T011150Z-current-macro-governance-ab6ad5f/`;
- snapshot pre-soak scale governance:
  `docs/evidence/c18-update-validation/20260617T015640Z-pre-soak-scale-governance-c8b0566/`;
  `scripts/qa/c18_ota_pre_soak_scale_governance_gate.py` verde em arvore
  limpa, com release gate interno verde, H2 ainda vermelho pelos blockers
  esperados e non-claims explicitos para producao, `stable`, auto-pull, thaw,
  soak 24h e power-loss 17/17;
- observacao/preflight da placa:
  `docs/evidence/c18-update-validation/20260611T182922Z-board-lab-apply-c16fb3e/board-preflight-post-apply-observation.json`;
- fechamento original da RC, superseded pelo refresh rastreavel:
  `docs/evidence/c18-update-validation/20260612T040055Z-pilot-readiness-final-c16fb3e/pilot-readiness-final.json`;
- diagnostico read-only de placa:
  `docs/evidence/c18-update-validation/20260612T183722Z-board-readonly-diagnostics-17a1f9d/`;
  esta evidencia registra appliance `player_running`, `privacy_scan=ok`,
  config content nao lido e display `unknown` porque o sysfs da placa tem HDMI
  `connected`/`enabled` com modos, mas sem `mode` observavel. Ela nao e
  deep-health, power-loss, soak, H2, stable, producao, publish, auto-pull ou
  thaw.

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
Em modo decisivo, os diretorios coldboot/data de `player-runtime` agora tambem
sao git-guardados; H2 readiness exige arvore limpa e inputs rastreados antes de
qualquer leitura de readiness.

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
  --h1-release-gate-summary docs/evidence/c18-update-validation/20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80/h1-release-gate.json \
  --authorization docs/evidence/c18-update-validation/20260612T195336Z-pilot-authorization-traceability-refresh/pilot-authorization.json \
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

Como agregador pre-H2, o snapshot macro tambem deve passar:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_macro_governance_gate.py --json
```

Resultado esperado: `passed=true`,
`result_claim=c18_homologation_governance_ready_pre_h2`. Esse resultado e
somente de governanca/snapshot: ele carrega a janela antiga como
`snapshot_only`, nao como autorizacao operacional viva.

Como agregador pre-soak para escala, o snapshot atual tambem deve passar:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_pre_soak_scale_governance_gate.py --json
```

Resultado esperado: `passed=true`,
`result_claim=c18_ota_pre_soak_scale_governance_ready`. Quando usado para gerar
evidencia final do retrato atual, rodar com `--run-release-gate` em arvore
limpa. Esse gate agrega docs de responsabilidade, H2 vermelho, server-side
atual, preflight H2 power-loss, retomada operacional default-deny e release
gate; nao substitui H2 nem autorizacao operacional fresca.

Para qualquer retomada operacional apos pausa, reboot da placa ou passagem de
dias, o gate de retomada deve ser o ultimo check antes de mexer na placa:

O preflight fresco deve ser coletado na placa com
`scripts/board/c18_homologation_pilot_preflight_collect.py` copiado para
`/tmp`, usando `stage=pre_apply`, o device hash sanitizado allowlistado e os
hashes esperados do pacote `c16fb3e`. Esse coletor valida policy/timer, imagem,
stack `mpv`/`hwdec` e freeze publico `rc=44`; ele nao usa o reconcile de
manutencao autorizado.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_operational_resume_gate.py \
  --macro-governance-summary docs/evidence/c18-update-validation/20260617T011150Z-current-macro-governance-ab6ad5f/macro-governance.json \
  --authorization <nova-autorizacao-da-janela-atual.json> \
  --preflight <novo-preflight-pre_apply-da-placa.json> \
  --json
```

Resultado esperado para operar: `passed=true`,
`result_claim=c18_operational_resume_ready`. Com a autorizacao/preflight antigos,
o resultado correto em 2026-06-16 e vermelho:
`authorization_window_expired`, `preflight_stale` e `preflight_stage_mismatch`.
Snapshot versionado desse bloqueio:
`docs/evidence/c18-update-validation/20260616T224130Z-operational-resume-blocked-99c0af8/`.

Snapshot atual de retomada operacional:
`docs/evidence/c18-update-validation/20260616T231448Z-operational-resume-current-2320950/`.
Resultado: `passed=true`, `result_claim=c18_operational_resume_ready`, com
autorizacao vigente, preflight `pre_apply` fresco da placa, freeze publico
`rc=44`, policy homologation e stack C18 `mpv`/`hwdec` provada. Esse resultado
autoriza apenas continuidade assistida do piloto de homologacao; nao autoriza
producao, `stable`, auto-pull, thaw publico, soak 24h nem power-loss 17/17.

Snapshot atual de readiness do piloto:
`docs/evidence/c18-update-validation/20260616T232546Z-current-pilot-readiness-5b2128c/`.
Resultado: `passed=true`, `result_claim=homologation_pilot_ready`, usando o
mesmo pacote `c16fb3e`, H1 decisivo rastreavel, autorizacao vigente,
preflight `pre_apply` fresco e os cinco checkpoints P0 seletivos. Esse snapshot
substitui o readiness antigo apenas para a retomada operacional atual; ele nao
reduz nenhum blocker H2.

O H2 readiness gate tambem foi rerodado e permaneceu vermelho pelos bloqueios
esperados:

- matriz fisica power-loss 17/17 incompleta;
- soak 24h ausente;
- stable promotion ausente;
- decisao explicita de thaw ausente.

Blockers exatos preservados no gate macro:

- `full_physical_powerloss_matrix:powerloss_matrix_incomplete`;
- `soak_endurance_24h:missing_24h_soak_summary`;
- `stable_promotion_authorization:missing_stable_promotion_evidence`;
- `explicit_operator_thaw_decision:missing_operator_thaw_decision`.

O snapshot H2 rastreavel esta versionado em
`docs/evidence/c18-update-validation/20260617T003916Z-current-h2-readiness-c16fb3e/`:
`h1_decisive_bundle=true`, `server_side_publish_governance=true`,
`repo_clean=true` e `tracked_inputs=true`; `passed=false` continua correto para
producao.

A semantica de validacao power-loss esta completa no gate off-board: 17/17
checkpoints possuem validadores. O que ainda falta para H2 e a evidencia fisica
dos 12 checkpoints restantes. O planner
`docs/evidence/c18-update-validation/20260617T020912Z-h2-powerloss-matrix-plan-custom-setup-c16fb3e/`
registra a matriz atual como 5/17 coberta e 12/17 pendente, com instrucoes
manuais explicitas para checkpoints de setup customizado e sem reivindicar
evidencia fisica.
O runbook operacional gerado em
`docs/evidence/c18-update-validation/20260617T020912Z-h2-powerloss-operator-runbook-custom-setup-c16fb3e/`
organiza esses 12 checkpoints para operador, com comandos arm/resume e helper
de pull/validacao. O builder agora bloqueia checkpoint `requires_custom_setup`
sem comandos ou instrucoes manuais; o runbook tambem nao e evidencia fisica e
nao substitui corte real de energia.
O mesmo runbook agora inclui uma etapa previa de preflight H2: coletar estado
read-only da placa com
`scripts/board/c18_player_runtime_h2_powerloss_preflight_collect.py` e validar
com `scripts/qa/c18_player_runtime_h2_powerloss_preflight_gate.py` contra o
plano da matriz. Esse gate bloqueia placa/pacote/topologia errados antes da
sessao fisica, mas nao conta checkpoint e nao reduz os blockers H2.
Snapshot atual revalidado contra o plano com custom setup:
`docs/evidence/c18-update-validation/20260617T021300Z-h2-powerloss-board-preflight-current-custom-plan-c16fb3e/`;
ele reporta `after_previous_symlink` e `rollback_after_current_unlinked` como
checkpoints que exigem setup customizado.
Na rodada `20260612T163008Z`, o preflight bloqueou corretamente porque o target
`c16fb3e` ainda estava em quarentena. O reset lab-only
`20260612T163437Z-h2-powerloss-quarantine-reset-c16fb3e` removeu uma entrada do
target sem mudar links e mantendo CLI publico congelado. O preflight
`20260612T163650Z-h2-powerloss-board-preflight-after-reset-c16fb3e` ficou verde
para iniciar os 12 cortes fisicos restantes.
Depois da pausa/reboot multi-dia, o preflight atual
`20260616T235724Z-h2-powerloss-board-preflight-current-c16fb3e` reconfirmou a
placa no mesmo terreno seguro: pacote `c16fb3e`, imagem `c18-hwdecode-lab-1x`,
policy `homologation`, timer inativo/desabilitado, target nao linkado, target
nao quarentenado e raiz de evidencia H2 sem diretorios de checkpoint pendentes.
Esse snapshot tambem e apenas preflight: nao conta power-loss, nao reduz os 12
checkpoints fisicos pendentes e nao muda H2/stable/thaw.

Depois da auditoria de fronteiras, a RC tambem passou a ter defesa em
profundidade para payloads:

- `player-runtime` so aceita `kiosk.py` no release gate;
- build/publish legado de `kiosky-player` seguem congelados e recusam conteudo
  de media/data/system mesmo com bypass lab;
- `totem-core` tem allowlist exata no release gate e no `totem_updatectl.py`,
  antes de extrair/promover no device.

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
4. Depois do piloto, abrir H2: 17/17 power-loss, soak 24h, stable promotion e
   decisao formal de thaw.

Nota pos-RC: a familia server-side/signature passa por
`scripts/qa/c18_server_side_publish_governance_gate.py` antes de ser consumida
pelo H2. Esse gate e offline, nao publica releases nem habilita auto-pull, e
agora rejeita evidencia apenas declaratoria: exige artefatos reais no diretorio
da release, sem symlink/out-of-dir, provas de attestation/assinatura com hashes
conferidos, audit-log hash-bound, canal, auto-pull off, allowlist, staged
rollout, rollback e auditoria. Assinatura destacada e verificada offline com
prova JSON canonica, fingerprint SPKI DER da chave publica, `release_set_sha256`,
chave publica externa via `--trusted-key-pem` e evidencia de trust anchor
separada via `--trust-anchor-evidence`; H2/stable carregam o hash dessa
evidencia. Para H2 de `player-runtime`, o consumo e componente-amarrado:
evidencia server-side de `totem-core` nao fecha thaw de `player-runtime`. Essa
evidencia nao afirma cadeia PKI, rejeita claims PKI extras e
rejeita symlink em qualquer componente do caminho da chave ou do trust anchor.
Fixture nao passa fora de self-test; producao ainda exige evidencia real
assinada com chave operacional.
Para o pacote `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`,
essa familia ja esta materializada em
`docs/evidence/c18-update-validation/20260612T125127Z-server-side-governance-c16fb3e/`
e a lista repo-relative de assets/hashes esta em
`docs/evidence/c18-update-validation/20260612T172602Z-server-side-asset-list-c16fb3e/`.
O H2 reporta `server_side_publish_governance=true`; isso nao publica release,
nao habilita auto-pull, nao promove stable e nao abre producao.
O H2 tambem reporta um ledger de semantica da matriz power-loss. Na RC atual
esse ledger esta completo; para producao ainda falta coletar e commitar os 12
checkpoints fisicos restantes.
Stable tambem fica atras de `scripts/qa/c18_stable_promotion_gate.py`; evidencia
minima com apenas `approved=true` nao autoriza build nem publish stable, e no H2
os hashes declarados precisam bater com as evidencias consumidas. Nos scripts de
build/publish stable, o gate deve receber os caminhos dos artefatos reais; usar
somente `--evidence` falha fechado. Alem do hash binding, esses artefatos sao
validados semanticamente no caminho stable: release gate verde, power-loss 17/17
verde, soak 24h, server-side assinado com trust key externa + trust anchor, e
decisao de operador aprovada pelo gate dedicado
`scripts/qa/c18_player_runtime_thaw_decision_gate.py`. Essa decisao tambem e
artifact-bound, tem janela UTC maxima de 4h e nao executa thaw, nao publica
release e nao habilita auto-pull.
O scaffold operacional desses dois JSONs finais existe em
`scripts/qa/c18_player_runtime_stable_decision_draft_build.py`: ele apenas gera
rascunhos fail-closed, com hashes reais quando os artefatos forem fornecidos, e
nao substitui H2 verde nem decisao humana. `passed=true` nesse builder significa
somente que os rascunhos foram escritos e continuam reprovando nos gates como
esperado; nao significa stable autorizado, thaw autorizado ou publish liberado.
