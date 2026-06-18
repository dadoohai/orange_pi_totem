# 192 - C18 Homologation RC

Status em 2026-06-18: **Homologation RC reancorada em `9bebaf1`, piloto
assistido liberado, H2/producao ainda bloqueados**. O alvo corrigido
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1` passou release
gate, lab apply/adoption/deep-health curto, server-side governance, preflight
H2 apos reset/topologia e P0 power-loss seletivo assistido. Producao/stable
continuam bloqueados por H2.

A evidencia
`docs/evidence/c18-update-validation/20260617T174316Z-h2-powerloss-after-payload-staged-mpv-stuck-135f397/`
preserva uma tentativa fisica `after_payload_staged` em que a adocao antes do
reconcile passou, mas o deep-health falhou com `status_mpv_path_aligned`: o MPV
permaneceu em 1 alias de midia enquanto o status publico avancou por 4 aliases
(`status_advanced_without_mpv=true`). Portanto, o pacote
`c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e` fica historico e
bloqueado como alvo final H2/piloto. A trilha corrente usa o alvo corrigido
`9bebaf1`; o piloto assistido foi liberado somente depois do P0 seletivo
commitado e do snapshot macro pos-P0 reancorado.

Este documento consolida o norte macro da C18 para a RC de homologacao. Ele nao
substitui `docs/UPDATE_CONTRACT.md`; apenas torna explicito o estado de
entrega: OTA funcional em laboratorio/homologacao controlada, com piloto
assistido pronto e producao/stable ainda bloqueados pelos gates H2.

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
| `player-runtime` | `kiosk.py`, launcher do player, flags de MPV, timing/sync/duracao/playlist | Alvo `9bebaf1` funcional em lab apply/adoption/deep-health curto e server-side; piloto assistido liberado pelo P0 seletivo; a frente e mais ampla, mas o payload C18-aware atual esta restrito a `kiosk.py`; nao e public thaw |
| `media-system` | MPV, ffmpeg, hwdecode, panfrost, wrapper, HDMI/display, kernel, DTB, U-Boot e BSP | Congelado nesta RC; guardrails executaveis bloqueiam vazamento para OTA comum; qualquer mudanca exige imagem/homologacao propria |
| `field-data` | config real, seed, midia, cache, playlist e estado local | Operacional em `/data`; guardrails executaveis bloqueiam vazamento para release de software; snapshot publico C18/C7 coleta apenas estado sanitizado e metadados, com evidencia read-only em placa |
| `server-side/publish` | server-side/signature, trust anchor, lista de assets, allowlist, staged rollout e audit | Verde para os artefatos de homologacao `9bebaf1`; nao publica, nao promove `stable`, nao liga auto-pull e nao abre thaw publico |
| `H2/prod` | gates de producao/stable, power-loss 17/17, soak 24h, stable promotion e decisao formal de thaw | Intencionalmente vermelho antes de H2; nenhuma conclusao de producao pode ser inferida da RC ou do piloto assistido |

## Roots canonicos de artefatos

| Frente | Root canonico | Regra C18 |
| --- | --- | --- |
| `player-runtime` | `releases/player-runtime` | Root do pacote homologation atual e dos artefatos server-side do `player-runtime`; qualquer pacote novo precisa passar no `c18_player_runtime_release_gate.py` e nos gates do canal. |
| `totem-core` | `releases/core-updates` | Root historico/canonico de pacotes core. Artefatos antigos que nao passam no gate C18 atual sao apenas historicos; pacote C18 novo deve ser regenerado e passar `c18_ota_release_gate.py --package-manifest ... --package-payload ...`. |
| `totem-core` | `releases/totem-core` | Nao e root canonico nesta linha; nao usar para RC C18. |
| `kiosky-player` legado | `releases/app-updates` | Historico C14/kiosky; nao usar para C18 OTA/RC, `player-runtime`, `stable` ou producao. |

## Evidencia de fechamento

Pacote alvo corrente de `player-runtime`:

- versao: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`;
- componente: `player-runtime`;
- canal: `homologation`;
- source commit: `9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522`;
- payload sha256:
  `d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0`.

Evidencia principal:

- H1 decisivo:
  `docs/evidence/c18-update-validation/20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80/h1-release-gate.json`;
- lab apply/adoption/deep-health curto do alvo corrigido:
  `docs/evidence/c18-update-validation/20260617T185552Z-service-adoption-health-mpv-stuck-fix-4235e07/`;
- autorizacao/preflight/pilot readiness do alvo corrigido:
  `docs/evidence/c18-update-validation/20260617T192801Z-pilot-preflight-mpv-stuck-fix-9bebaf1/`;
- pilot readiness final pos-P0:
  `docs/evidence/c18-update-validation/20260618T041500Z-pilot-readiness-final-9bebaf1/pilot-readiness-final.json`;
- autorizacao/readiness de 2026-06-12, preservados como rastreabilidade
  historica:
  `docs/evidence/c18-update-validation/20260612T195336Z-pilot-authorization-traceability-refresh/pilot-authorization.json`,
  `docs/evidence/c18-update-validation/20260612T195516Z-pilot-readiness-traceability-refresh-c16fb3e/pilot-readiness.json`;
- snapshot H2 atual pos-P0, vermelho apenas pelos blockers de producao:
  `docs/evidence/c18-update-validation/20260618T043000Z-current-h2-readiness-after-pilot-p0-9bebaf1/h2-readiness.json`;
- server-side/signature atual:
  `docs/evidence/c18-update-validation/20260617T191658Z-server-side-current-mpv-stuck-fix-9bebaf1/`;
  `server-side-governance-gate.json` verde para `player-runtime`, trust anchor
  externo verificado e lista de 14 assets assinados/atestados hash-bound; nao
  publica, nao promove `stable`, nao liga auto-pull e nao abre thaw;
- plano/runbook H2 power-loss do alvo corrigido:
  `docs/evidence/c18-update-validation/20260617T193720Z-h2-powerloss-matrix-plan-mpv-stuck-fix-9bebaf1/`,
  `docs/evidence/c18-update-validation/20260617T193720Z-h2-powerloss-operator-runbook-mpv-stuck-fix-9bebaf1/`;
- preflight H2 read-only da placa antes da sessao P0:
  `docs/evidence/c18-update-validation/20260618T024300Z-h2-powerloss-board-preflight-after-topology-prep-p0-9bebaf1/`;
- evidencia P0 power-loss seletiva do piloto:
  `docs/evidence/c18-update-validation/20260618T034601Z-pilot-p0-powerloss-9bebaf1/`;
- gate macro pre-H2:
  `scripts/qa/c18_ota_macro_governance_gate.py` agrega os snapshots versionados
  e nao substitui H2, nao reabre janela de piloto expirada e nao autoriza
  producao. O gate corrente esta reancorado em `9bebaf1` e no pilot readiness
  final pos-P0; isso libera somente o piloto assistido, nao H2/producao;
- snapshot macro versionado:
  o snapshot `docs/evidence/c18-update-validation/20260617T064617Z-current-macro-governance-a761a67/`
  fica historico de `c16fb3e`; o snapshot corrente
  `docs/evidence/c18-update-validation/20260618T043100Z-current-macro-governance-after-pilot-p0-9bebaf1/`
  esta verde pre-H2 e aponta para o pilot readiness final pos-P0, sem liberar
  producao;
- snapshot pre-soak scale governance:
  `docs/evidence/c18-update-validation/20260617T065222Z-pre-soak-scale-governance-6937b26/`;
  snapshot historico de `c16fb3e`. O snapshot corrente pos-P0
  `docs/evidence/c18-update-validation/20260618T043200Z-pre-soak-scale-governance-after-pilot-p0-9bebaf1/`
  esta verde para governanca pre-soak/pre-H2 e continua sem substituir soak 24h
  ou power-loss 17/17;
- playback em nivel usuario:
  `docs/evidence/c18-update-validation/user-level-10min-20260617T215450Z-9bebaf1/`
  preserva 10 minutos de placa real com 9 midias observadas, zero restart,
  zero falha de render e sem padrao de midia presa;
- playback fresco pos-alinhamento:
  `docs/evidence/c18-update-validation/user-level-fresh-20260617T2234Z-9bebaf1/`
  preserva 120 segundos de placa real no runtime corrente, com 9 midias
  observadas, hwdecode esperado, zero restart, zero falha de midia e sem
  divergencia status/MPV;
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

P0 power-loss seletivo exigido para piloto do alvo `9bebaf1`:

- `after_current_symlink`;
- `rollback_after_current_to_previous`;
- `rollback_after_previous_removed`;
- `rollback_after_quarantine`;
- `rollback_after_state_success`.

No estado atual, esses 5 checkpoints estao coletados, manifestados, rastreados
e aceitos para `9bebaf1` em
`docs/evidence/c18-update-validation/20260618T034601Z-pilot-p0-powerloss-9bebaf1/`.

## Verificacao off-board

Comandos atuais para o alvo `9bebaf1` em arvore limpa:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_release_gate.py --json
```

Resultado: `passed=true`.
Em modo decisivo, os diretorios coldboot/data de `player-runtime` agora tambem
sao git-guardados; H2 readiness exige arvore limpa e inputs rastreados antes de
qualquer leitura de readiness.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_player_runtime_release_gate.py \
  --manifest releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json \
  --payload releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz
```

Resultado: `passed=true`.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_player_runtime_pilot_readiness_gate.py \
  --package-manifest releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json \
  --package-payload releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz \
  --h1-release-gate-summary docs/evidence/c18-update-validation/20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80/h1-release-gate.json \
  --authorization docs/evidence/c18-update-validation/20260617T192801Z-pilot-preflight-mpv-stuck-fix-9bebaf1/pilot-authorization.json \
  --preflight docs/evidence/c18-update-validation/20260617T192801Z-pilot-preflight-mpv-stuck-fix-9bebaf1/board-preflight.json \
  --expect-image-tag c18-hwdecode-lab-1x \
  --expect-image-sha256 1a853f569b5da9e856439897c95612d719fd3059f12349fa1040a6350c3df2f2 \
  --expect-image-marker-sha256 59739f57cdb3f79ac4c8ce5e5e1f9c4aa6d9dae58f704010f8423e66abe2bb9e \
  --expect-source-commit 9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522 \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/20260618T034601Z-pilot-p0-powerloss-9bebaf1/after_current_symlink \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/20260618T034601Z-pilot-p0-powerloss-9bebaf1/rollback_after_current_to_previous \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/20260618T034601Z-pilot-p0-powerloss-9bebaf1/rollback_after_previous_removed \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/20260618T034601Z-pilot-p0-powerloss-9bebaf1/rollback_after_quarantine \
  --powerloss-evidence-dir docs/evidence/c18-update-validation/20260618T034601Z-pilot-p0-powerloss-9bebaf1/rollback_after_state_success \
  --json
```

Resultado atual: `passed=true`, `result_claim=homologation_pilot_ready`.

Como agregador pre-H2, o gate macro default atual esta reancorado no pilot
readiness final pos-P0:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_macro_governance_gate.py --json
```

Resultado esperado: `passed=true`,
`result_claim=c18_homologation_governance_ready_pre_h2`. Esse resultado nao e
claim de H2/producao; ele prova apenas que H1, piloto assistido, H2 vermelho,
server-side e docs estao coerentes.

Como agregador pre-soak para escala:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_pre_soak_scale_governance_gate.py --json
```

Resultado esperado: `passed=true`,
`result_claim=c18_ota_pre_soak_scale_governance_ready`. Esse gate agrega docs de
responsabilidade, H2 vermelho, server-side atual, preflight H2 power-loss,
retomada operacional default-deny e release gate; nao substitui H2 nem
autorizacao operacional fresca.

Para qualquer retomada operacional apos pausa, reboot da placa ou passagem de
dias, o gate de retomada deve ser o ultimo check antes de mexer na placa:

O preflight fresco deve ser coletado na placa com
`scripts/board/c18_homologation_pilot_preflight_collect.py` copiado para
`/tmp`, usando `stage=pre_apply`, o device hash sanitizado allowlistado e os
hashes esperados do pacote `9bebaf1`. Esse coletor valida policy/timer, imagem,
stack `mpv`/`hwdec` e freeze publico `rc=44`; ele nao usa o reconcile de
manutencao autorizado.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_operational_resume_gate.py \
  --macro-governance-summary <novo-macro-governance-9bebaf1.json> \
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

Snapshot atual de readiness do piloto para `9bebaf1`:
`docs/evidence/c18-update-validation/20260617T192801Z-pilot-preflight-mpv-stuck-fix-9bebaf1/`.
Resultado: bloqueado somente por P0, com H1 decisivo rastreavel, autorizacao,
preflight `pre_apply`, package/source binding, repo clean e tracked inputs
verdes. Esse snapshot nao reduz nenhum blocker H2.

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

O snapshot H2 rastreavel do alvo `9bebaf1` esta versionado em
`docs/evidence/c18-update-validation/20260618T043000Z-current-h2-readiness-after-pilot-p0-9bebaf1/`:
`h1_decisive_bundle=true`, `server_side_publish_governance=true`,
`repo_clean=true` e `tracked_inputs=true`; `passed=false` continua correto para
producao.

A semantica de validacao power-loss esta completa no gate off-board: 17/17
checkpoints possuem validadores. O que ainda falta para H2 e a evidencia fisica
dos 17 checkpoints do alvo `9bebaf1`. O planner
`docs/evidence/c18-update-validation/20260617T193720Z-h2-powerloss-matrix-plan-mpv-stuck-fix-9bebaf1/`
permanece como plano completo da matriz, com instrucoes
manuais explicitas para checkpoints de setup customizado e sem reivindicar
evidencia fisica.
O runbook operacional gerado em
`docs/evidence/c18-update-validation/20260617T193720Z-h2-powerloss-operator-runbook-mpv-stuck-fix-9bebaf1/`
organiza esses 17 checkpoints para operador, com comandos arm/resume e helper
de pull/validacao. O builder bloqueia checkpoint `requires_custom_setup` sem
comandos ou instrucoes manuais; o helper recusa placeholder `<utc>`/diretorio
local existente para evitar mistura de evidencia, materializa o manifest local
exigido pelo evidence gate, fixa o marker de imagem esperado no preflight e
injeta binding de payload/imagem para H2. O runbook tambem nao e evidencia
fisica e nao substitui corte real de energia.
O runbook inclui uma etapa previa de preflight H2: coletar estado read-only da
placa com `scripts/board/c18_player_runtime_h2_powerloss_preflight_collect.py`
e validar com `scripts/qa/c18_player_runtime_h2_powerloss_preflight_gate.py`
contra o plano da matriz. Esse gate bloqueia placa/pacote/topologia errados
antes da sessao fisica, mas nao conta checkpoint e nao reduz os blockers H2.
O snapshot `20260617T193921Z-h2-powerloss-board-preflight-mpv-stuck-fix-9bebaf1`
coletou board/bundle saudaveis, porem bloqueou corretamente porque o target ja
estava linkado como `current` e a release dir do alvo existia. O reset
controlado
`20260617T201430Z-h2-powerloss-topology-reset-mpv-stuck-fix-9bebaf1` restaurou
`current` para `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`, removeu a
release dir do alvo e manteve o freeze publico `rc=44`. O preflight usado para
a sessao P0 esta versionado em
`docs/evidence/c18-update-validation/20260618T024300Z-h2-powerloss-board-preflight-after-topology-prep-p0-9bebaf1/`.
Ele nao conta checkpoint power-loss e nao reduz os blockers H2 por si so; os 5
checkpoints P0 do piloto contam no gate de piloto e aparecem como subconjunto
observado no H2 readiness pos-P0.

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

1. Executar piloto assistido somente dentro de autorizacao/preflight atuais e
   frescos, com rollback owner definido e evidencia commitada.
2. Antes de qualquer nova sessao fisica, recoletar preflight H2 se a janela de
   frescor expirar ou se o estado da placa mudar.
3. Abrir H2 completo apenas depois do piloto: 17/17 power-loss, soak 24h,
   stable promotion e decisao formal de thaw.
4. Preservar evidencia de apply, health, rollback e qualquer incidente.
5. Manter `stable`, producao, auto-pull e public thaw bloqueados ate H2 verde.

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
Para o pacote `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`,
essa familia ja esta materializada em
`docs/evidence/c18-update-validation/20260617T191658Z-server-side-governance-mpv-stuck-fix-9bebaf1/`
e o snapshot corrente esta em
`docs/evidence/c18-update-validation/20260617T191658Z-server-side-current-mpv-stuck-fix-9bebaf1/`.
O H2 reporta `server_side_publish_governance=true`; isso nao publica release,
nao habilita auto-pull, nao promove stable e nao abre producao.
O H2 tambem reporta um ledger de semantica da matriz power-loss. Na RC atual
esse ledger esta completo; para producao ainda falta coletar e commitar os 17
checkpoints fisicos do alvo `9bebaf1`.
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
