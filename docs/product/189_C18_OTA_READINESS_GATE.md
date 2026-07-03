# 189 — C18.OTA-READINESS-GATE

Rodada de proteção do OTA C18. Objetivo: permitir evolução rápida do wizard/core
sem criar um caminho acidental para regredir o playback/hwdecode validado na
golden atual `1u`.

## Decisão

- OTA C18 imediato = `totem-core` **manual/operator-triggered**.
- `kiosky-player`, MPV e `/opt/totem/hwdecode` ficam **congelados fora do OTA**.
- Imagem C18 nova deve nascer com `/data/updates/policy.json` restritivo:
  `device_track="c18-hwdecode"`, `allowed_components=["totem-core"]`,
  `allow_downgrade=false`.
- `totem-update-agent.timer` nasce desabilitado; auto-pull fica fora de escopo
  até hardening posterior.
- O service de update aponta para
  `apply-github-latest --component totem-core --repo dadoohai/orange_pi_totem`
  e exige policy presente.

## Estado vivo / proximo gate

| Item | Estado |
| --- | --- |
| Golden atual | `c18-hwdecode-lab-1u`, fonte canonica em `docs/evidence/c18-update-validation/current-golden.json` |
| OTA comum | somente `totem-core`, manual/operator-triggered |
| Freeze publico | `kiosky-player` e `player-runtime` seguem `rc=44` em apply/rollback/reconcile publicos; na imagem `1u`, o hardening de `kiosky-player reconcile` foi provado em hardware com `rc=44` |
| M6 `/data` historico | `20260608T011301Z`: evidenciou A->B->A de `player-runtime` em `/data`, reboot controlado, adocao B por `/data`, deep-health e rollback para A sob golden `1t`; apos o bump para `1u`, nao e autorizacao `decisive` atual |
| M6 `/data` decisivo atual | Bundle `1x`: `20260610T072826Z` evidenciou A2->B2->cold-boot->A2 de `player-runtime` em `/data`; teardown dirs `20260610T052324Z`, `20260610T185956Z` e `20260611T050939Z` cobrem teardown/relaunch repetido, req#4 fresh-IPC exercitado e parada SIGTERM saudavel do Python-kiosk; release gate host `decisive` verde com a tripla explicita da imagem `1x` |
| H1.5 homologation pilot | Caminho intermediario controlado por `scripts/qa/c18_player_runtime_pilot_readiness_gate.py`: `channel=homologation`, `ring=pilot`, entrega assistida, autorizacao formal, preflight com public freeze `rc=44`, pacote alvo e P0 power-loss seletivo. O alvo corrente `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1` esta pronto para piloto assistido em `docs/evidence/c18-update-validation/20260618T041500Z-pilot-readiness-final-9bebaf1/pilot-readiness-final.json`. A evidencia `20260616T232546Z-current-pilot-readiness-5b2128c`, com `20260612T195516Z-pilot-readiness-traceability-refresh-c16fb3e`, fica preservada como historico; apos a evidencia negativa `docs/evidence/c18-update-validation/20260617T174316Z-h2-powerloss-after-payload-staged-mpv-stuck-135f397/`, `c16fb3e` nao e mais RC corrente aceitavel para piloto. |
| Evidencia 1u | offline `20260608T024500Z-1u-offline-build`, cold-boot HW `20260608T035330Z-1u-coldboot-deep-health` |
| Power-loss fisico | O P0 seletivo historico do pacote `c16fb3e` cobria 5/17, mas a tentativa fisica `after_payload_staged` preservada em `20260617T174316Z-h2-powerloss-after-payload-staged-mpv-stuck-135f397` bloqueia esse alvo: MPV ficou em uma midia enquanto o status avancou. Para o alvo `9bebaf1`, o preflight `docs/evidence/c18-update-validation/20260618T024300Z-h2-powerloss-board-preflight-after-topology-prep-p0-9bebaf1/` precedeu a sessao fisica, e o P0 seletivo do piloto (`pilot_powerloss_p0`) passou nos 5 checkpoints em `docs/evidence/c18-update-validation/20260618T034601Z-pilot-p0-powerloss-9bebaf1/`. A validacao target-current final passou, a topologia foi restaurada para M6, e o preflight H2 power-loss corrente foi renovado em `docs/evidence/c18-update-validation/20260618T095819Z-h2-powerloss-board-preflight-after-target-health-9bebaf1/`. Isso libera piloto assistido e prepara nova sessao H2, mas nao libera H2: a matriz completa 17/17 continua incompleta. |
| Power-loss fisico 2026-07-03 | Nova sessao H2 acumulou 5 checkpoints adicionais verdes para `9bebaf1` (`after_payload_staged`, `after_release_dir_created`, `after_extract`, `after_state_verifying`, `after_health_passed`), totalizando 10/17 com os 5 P0 anteriores. A campanha parou em `after_release_tree_fsync`: o resume voltou para o baseline verificado `m6-a`, mas o deep-health detectou status avancando enquanto MPV ficou em uma unica midia. Evidencia em `docs/evidence/c18-update-validation/20260703T012000Z-h2-powerloss-after-release-tree-fsync-blocked-status-mpv-mismatch-9bebaf1/`; decisao de retomada em `docs/evidence/c18-update-validation/20260703T013918Z-h2-powerloss-baseline-m6a-hold-9bebaf1/`. Nao contar esse checkpoint como verde; faltam 7 checkpoints e a matriz H2 segue bloqueada. |
| Server-side/signature | Familia atual do pacote `9bebaf1` esta verde em `20260617T191658Z-server-side-current-mpv-stuck-fix-9bebaf1`; gate offline valida artefatos reais, assinaturas/trust-anchor, audit log, auto-pull off, allowlist/staged rollout e component binding, sem publicar release |
| Rastreabilidade dos gates | Release gate decisivo git-guarda os diretorios coldboot/data; H1 atual `20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80`; para o alvo `9bebaf1`, H2 readiness atual esta em `docs/evidence/c18-update-validation/20260618T101740Z-current-h2-readiness-head-0401375-9bebaf1/h2-readiness.json` e continua vermelho somente por power-loss 17/17, soak 24h, stable promotion e decisao formal de thaw |
| Playback usuario | O alvo `9bebaf1` tem evidencia funcional curta e 10 minutos em placa real; `docs/evidence/c18-update-validation/user-level-10min-20260617T215450Z-9bebaf1/` passou apos calibracao de IPC, com 9 midias observadas, sem restart, sem falha de render e sem padrao de midia presa. |
| Gate macro pre-H2 | `scripts/qa/c18_ota_macro_governance_gate.py` agrega H1, pilot readiness, H2 vermelho e diagnostico read-only em snapshot governado; nao substitui H2, nao reabre janela expirada e nao autoriza producao. O snapshot corrente pos-P0 esta em `docs/evidence/c18-update-validation/20260618T102246Z-current-macro-governance-head-3fb8dc2-9bebaf1/`, aponta para o pilot gate final e para o diagnostico read-only pos-P0 `docs/evidence/c18-update-validation/20260618T084958Z-board-readonly-diagnostics-current-d0a11c7-9bebaf1/`; snapshots anteriores permanecem historicos. |
| Retomada operacional | `scripts/qa/c18_ota_operational_resume_gate.py` precisa ficar verde antes de qualquer nova execucao na placa; snapshots versionados de retomada provam apenas a janela em que foram coletados. O snapshot verde inicial `docs/evidence/c18-update-validation/20260618T044700Z-operational-resume-current-after-pilot-p0-9bebaf1/` fica historico, e o refresh `docs/evidence/c18-update-validation/20260618T082930Z-operational-resume-refresh-8541841-9bebaf1/` renovou o preflight read-only e passou com `repo_clean=true` e `tracked_inputs=true`. O estado default atual continua bloqueado em `docs/evidence/c18-update-validation/20260618T102725Z-operational-resume-default-blocked-head-f47d0f8-9bebaf1/` sem autorizacao/preflight atuais, sem autorizar H2/producao. |
| Diagnostico operacional | Snapshot publico C18/C7 de `field-data` e coletor read-only de display/player estao gateados no repo; a evidencia fresca pos-P0 `docs/evidence/c18-update-validation/20260618T084958Z-board-readonly-diagnostics-current-d0a11c7-9bebaf1/` mostra appliance `player_running`, `privacy_scan=ok`, config content nao lido, e display `unknown`; a evidencia historica `20260612T183722Z-board-readonly-diagnostics-17a1f9d` permanece rastreavel |
| Proximo gate H2 | checkpoints restantes de power-loss/torn-write, soak/endurance, promocao stable e decisao final antes de qualquer caminho `stable`/producao |
| Ainda nao provado | public thaw, GitHub/auto-pull, `stable`, producao, matriz completa de power-loss fisico e soak/endurance |

## Golden atual (2026-06-08)

Marco de referência para continuidade C18/delivery:

- **Imagem gravável golden:** `c18-hwdecode-lab-1u`;
- **Arquivo:**
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1u_minimal.img`;
- **sha256:**
  `57cd3e1620820c14ff9b297850386d7d95a1979b2f06201ff082526b8ffd13dd`;
- **Tamanho:** `1971322880` bytes;
- **Estado:** golden de laboratorio/delivery, ainda `final_image=false` e nao
  `stable`/batch de producao;
- **Estado runtime esperado apos aplicar OTA de homologacao atual:**
  `totem-core` em
  `c18.ota-core-config-missing-20260603T150429Z-2a7a327`, com `previous` no
  embed `c17.6-environment-input-20260514T211247Z`;
- **Player/runtime esperado:** fallback de imagem, sem `/data/player-runtime/current`
  e sem `/data/apps/kiosky-player/current`; `hwdec-current=v4l2request-copy`,
  `vo-configured=true`, `NRestarts=0`;
- **Update posture:** OTA manual somente para `totem-core`; auto-pull desligado;
  `kiosky-player` e `player-runtime` bloqueados com `rc=44` ate thaw explicito.
- **Evidencia hardware 1u cold-boot:**
  `docs/evidence/c18-update-validation/20260608T035330Z-1u-coldboot-deep-health/`,
  com discriminadores pre/post boot, `boot_id_changed=true`,
  `btime_changed=true`, config real escrita via handoff/writer, service ativo,
  `NRestarts=0`, fallback `/opt`, freeze publico `rc=44` para
  `player-runtime` e `kiosky-player`, e deep-health `passed=true`.

Nota de escopo pos-M6: a `1u` prova em hardware o follow-up de governanca que
faltava apos a `1t`: `reconcile --component kiosky-player` publico retorna
`rc=44`. Isso nao abre thaw publico de `player-runtime` nem muda o canal de
producao.

Marco M6 historico de `/data`: a evidencia
`docs/evidence/c18-update-validation/20260608T011301Z-1t-player-runtime-m6-data-coldboot-trial/`
foi aceita pelo release gate em modo `decisive` na rodada em que a golden era
`1t`. Ela prova o fluxo lab-only A->B->A de `player-runtime` em `/data`, com
reboot controlado, B adotada de `/data/player-runtime/current`, deep-health do
candidato B e rollback para A real em `/data`. Apos o bump para golden `1u`, o
gate passou a rejeitar essa evidencia `1t` como autorizacao `decisive`
corrente. Hoje essa autorizacao decisiva viva ja foi restaurada pelo bundle
`1x` descrito abaixo, sem promover a `1x` como golden de recovery/delivery.
Esse marco `1t` nao abre thaw publico, publish GitHub, auto-pull, `stable`,
producao, power-loss fisico nem soak.

Ou seja: para recovery/baseline validado de laboratorio, partir da imagem `1u`.
A `1t` permanece como golden historica e como base do M6 A->B->A anterior; a
`1u` substitui a `1t` para delivery/lab porque embarca e prova o hardening
pos-M6 de reconcile publico sem regredir playback, enquanto a M6 decisiva
corrente de `player-runtime` esta pinada ao bundle `1x`.

Marco M6 decisivo atual de `/data`: as evidencias
`docs/evidence/c18-update-validation/20260610T072826Z-1x-m6-coldboot/` e
`docs/evidence/c18-update-validation/20260610T072826Z-1x-m6-data/`, junto com
os teardown dirs `20260610T052324Z-1x-teardown`,
`20260610T185956Z-1x-teardown-fresh-ipc-probe` e
`20260611T050939Z-1x-production-stop`, foram aceitas pelo release gate host em
modo `decisive` pinado a `c18-hwdecode-lab-1x`. Elas provam o fluxo lab-only
A2->B2->cold-boot->A2 de `player-runtime` em `/data`, com B2 adotada de
`/data/player-runtime/current`, deep-health, teardown/relaunch repetido,
req#4 fresh-IPC exercitado, parada SIGTERM saudavel do Python-kiosk via IPC
quit, rollback para A2 real em `/data` e deep-health pos-rollback. Esse marco
restaura a autorizacao decisiva lab de `player-runtime`; ele nao muda a fonte
canonica de recovery/delivery (`current-golden.json`, hoje `1u`) sem uma
promocao propria de baseline/fallback da `1x`.

Nota: `1k`, `1l`, `1m`, `1n`, `1o`, `1q`, `1r`, `1s` e `1t` permanecem como
golden historicas anteriores. O `player-runtime` continua congelado no fluxo
publico (`rc=44`).

## Promocao 1r (offline + hardware)

O commit `86e8fa0` fecha o follow-up da auditoria sobre falso-positivo
multi-segmento do deep-health e abort-safety do trial persistente. Por tocar
arquivos da imagem, foi gerada uma nova candidata e validada em placa.

- **Imagem candidata/golden:** `c18-hwdecode-lab-1r`;
- **Arquivo:**
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1r_minimal.img`;
- **Copia para gravacao no Windows:**
  `/mnt/d/images_orange/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1r_minimal.img`;
- **sha256:**
  `23ef26b4cdbd6c35643fdc41d8666da33dd259b387af05864c8f063506f7711c`;
- **Tamanho:** `1971322880` bytes;
- **Validacao offline:** `OFFLINE_VALIDATION_PASSED=True`,
  `artifact_promoted=true`, `totem_core_ota_ready=true`,
  `player_runtime_sandbox_passed=true`, `player_runtime_release_gate_passed=true`,
  `player_runtime_ota_still_frozen=true`,
  `no_player_runtime_current_embedded=true`,
  `no_legacy_kiosky_player_current_embedded=true`, `fsck_clean=true`;
- **Evidencia offline:** `docs/evidence/c18-update-validation/20260605T011600Z-1r-offline-build/`;
- **Validacao hardware:** marker `1r`, policy restrita a `totem-core`, timer
  desligado, service de update apontando para `totem-core`, drop-in do player
  com reconcile autorizado, config real escrita via writer a partir do seed,
  player fallback de imagem ativo, sem `/data/player-runtime/current` e sem
  `/data/apps/kiosky-player/current`, `kiosky-player` e `player-runtime`
  bloqueados com `rc=44` no fluxo publico, e deep-health de servico
  `passed=true` com 45 amostras, 4 segmentos avaliaveis, 0 segmentos falhos,
  `hwdec-current=v4l2request-copy`, `media_load_failed=0`, `mpv_restart=0`,
  `NRestarts_delta=0`, panfrost/mmc/ext4 `0`;
- **Evidencia hardware:** `docs/evidence/c18-update-validation/20260605T045500Z-1r-service-deep-health/`;
- **Mudanca load-bearing:** deep-health exige progresso em todos os segmentos
  avaliaveis, e o harness de trial persistente registra `current` pre/post,
  faz rollback lab com `--quarantine-current` em aborto apos promote e reinicia
  `kiosky-player.service`;
- **Status:** promovida a golden de laboratorio/delivery. Ainda
  `final_image=false`, nao stable, nao batch de producao, nao thaw publico de
  `player-runtime`, e nao prova trial persistente de `player-runtime` em
  `/data`.

## Promocao 1s (offline + hardware + cold-boot)

O commit `8aa04b2` prepara a imagem `c18-hwdecode-lab-1s` a partir do
hardening `02f3be7`, que fecha os gates pre-cold-boot/power-loss apontados apos
o trial A->B->A:

- `kiosky-player.service` passa a declarar `RequiresMountsFor=/data` e
  `After=local-fs.target` antes do reconcile de boot;
- `totem-updatectl` fsynca a arvore de release antes de escrever marker/promover;
- `reconcile` rejeita release "torn" por `tree_sha_mismatch` e cai para `/opt`;
- o deep-health rejeita segmento final curto sem progresso comprovado.

- **Imagem candidata/golden:** `c18-hwdecode-lab-1s`;
- **Arquivo:**
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1s_minimal.img`;
- **Copia para gravacao no Windows:**
  `/mnt/d/images_orange/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1s_minimal.img`;
- **sha256:**
  `bc0a39cf0cc4502acb7f9b4726589449288783fa4d44821593ab15c4c2c1967f`;
- **Tamanho:** `1971322880` bytes;
- **Validacao offline:** `OFFLINE_VALIDATION_PASSED=True`,
  `artifact_promoted=true`, `totem_core_ota_ready=true`,
  `player_runtime_sandbox_passed=true`, `player_runtime_release_gate_passed=true`,
  `player_runtime_ota_still_frozen=true`,
  `no_player_runtime_current_embedded=true`,
  `no_legacy_kiosky_player_current_embedded=true`, `fsck_clean=true`;
- **Evidencia offline:** `docs/evidence/c18-update-validation/20260605T040600Z-1s-offline-build/`;
- **Validacao hardware pos-config:** marker `1s`, policy restrita a
  `totem-core`, timer desligado, config real escrita via
  contract/handoff/writer a partir do seed de homologacao local, sem publicar
  valores privados, player fallback de imagem ativo, sem
  `/data/player-runtime/current` e sem `/data/apps/kiosky-player/current`,
  `player-runtime` bloqueado com `rc=44` em apply, rollback e reconcile, e
  deep-health de servico `passed=true` com `hwdec-current=v4l2request-copy`,
  um MPV, `media_load_failed=0`, `mpv_restart=0`, `NRestarts_delta=0`,
  panfrost/mmc/ext4 `0`;
- **Evidencia hardware pos-config:**
  `docs/evidence/c18-update-validation/20260605T043000Z-1s-service-deep-health/`;
- **Validacao hardware cold-boot:** reboot controlado, service ativo com
  `NRestarts=0`, drop-in efetivo com `RequiresMountsFor=/data` e
  `After=local-fs.target`, boot reconcile autorizado antes do launcher,
  launcher selecionando fallback `/opt`, policy/freeze/timer preservados,
  ausencia de `/data/player-runtime/current` e deep-health pos-boot
  `passed=true`;
- **Evidencia hardware cold-boot:**
  `docs/evidence/c18-update-validation/20260605T043400Z-1s-coldboot-deep-health/`;
- **Status:** promovida a golden de laboratorio/delivery. Ainda
  `final_image=false`, nao stable, nao batch de producao, nao thaw publico de
  `player-runtime`, nao GitHub publish de player, nao auto-pull, nao soak e nao
  prova corte de energia/power-loss durante apply ou rollback.

## Primeiro trial persistente de player-runtime em `/data` (1r)

Com a `1r` em hardware e a config real escrita via SSH a partir do seed, foi
executado o primeiro ensaio lab-only persistente de `player-runtime` em
`/data`, ainda sem descongelar o CLI publico:

- **Pacote local:** `c18.player-runtime-lab-20260605T052721Z-1562cd3`;
- **Componente/canal:** `player-runtime`, `homologation`;
- **source_commit do pacote:** `1562cd37ec933107c5ccf5bc363a156d0b7fb988`;
- **payload_sha256:**
  `057d25e61e2876629145cd0bdabebe27bdf14d2699e595ca5de2da73f67ffafe`;
- **Evidencia auditavel:**
  `docs/evidence/c18-update-validation/20260605T052805Z-1r-player-runtime-data-trial/`;
- **Gate da evidencia:** `c18_player_runtime_evidence_gate.py` passou sobre os
  bytes versionados, com allowlist, hashes, scan de vazamento e validacao
  semantica dos artefatos;
- **Adocao:** apos apply e restart do servico, o probe registrou
  `selected_source=data`, `current_link` apontando para a release testada,
  marker valido, `running_identity_matches_marker=true` e 1 processo de
  `/data`;
- **Deep-health pos-restart:** `passed=true`, 45 amostras, 6 segmentos
  avaliaveis, 0 segmentos falhos, `hwdec-current=v4l2request-copy`,
  `media_load_failed=0`, `mpv_restart=0`, `NRestarts_delta=0`,
  panfrost/mmc/ext4 `0`;
- **Rollback:** rollback lab-only com `quarantine_current=true`, retorno para
  `image_fallback`, sem `current`/`previous` persistentes restantes e
  deep-health pos-rollback `passed=true`;
- **Freeze publico:** apply/rollback/reconcile publicos de `player-runtime` e
  `kiosky-player` continuam bloqueados com `rc=44`.

O que este marco **nao** afirma: thaw publico, GitHub publish, auto-pull,
stable/producao, durabilidade sob corte de energia, cold-boot adoption, ou
rollback A->B entre duas releases persistentes em `/data`. Como foi o primeiro
apply persistente, nao havia `previous` de `/data`; o rollback validado foi para
o fallback de imagem. O manifest de evidencia deste trial tambem nao preenche
`image_tag`/`image_sha256`; o harness posterior passa a aceitar esses campos e
o proximo ensaio deve usa-los junto com `--rollback-expectation data-previous`.
O evidence gate passa a comparar o `tree_sha256` do release gate com o marker
adotado e a rejeitar uma evidencia A->B que volte para `image_fallback`.

## Trial A->B->A persistente de player-runtime em `/data` (1r)

Depois do primeiro trial persistente, foi executado um ensaio lab-only A->B->A
com duas releases locais de `player-runtime`, ainda sem descongelar o CLI
publico:

- **Release A ja ativa em `/data`:**
  `c18.player-runtime-ab-a-20260605T055913Z-8edcd1c`;
- **Release B candidata:**
  `c18.player-runtime-ab-b-20260605T055913Z-8edcd1c`;
- **Componente/canal:** `player-runtime`, `homologation`;
- **source_commit dos pacotes:** `8edcd1ce4a2f1d92513ba55b6288c8169165af91`;
- **payload_sha256 de B:**
  `4185d7059087d79ba3bb16e52b1b5a3bfe50e4d3f83eadb131b6e7a256f7fe59`;
- **tree_sha256 de A:**
  `8297de825b75cdec494fa0a9ec37f538046a8d2c6568a6c6b6ff6628194e2ba2`;
- **tree_sha256 de B:**
  `2e8aeb5e8ec90cd0555c59275cb670b03ca25349410dd8bc57ff9d3037431edc`;
- **Imagem de base registrada no manifest:** `c18-hwdecode-lab-1r`,
  sha256
  `23ef26b4cdbd6c35643fdc41d8666da33dd259b387af05864c8f063506f7711c`;
- **Evidencia auditavel:**
  `docs/evidence/c18-update-validation/20260605T060200Z-1r-player-runtime-data-aba-trial/`;
- **Gate da evidencia:** `c18_player_runtime_evidence_gate.py` passou sobre os
  bytes versionados, e `c18_ota_policy_static_test.py` fixa as assercoes
  especificas de A->B->A.

O que foi provado:

- antes do apply, A estava ativa em `/data/player-runtime/current`, com marker
  valido, identidade do processo batendo com o marker e deep-health
  `passed=true`;
- o apply lab-only promoveu B, registrou `previous=A` no symlink e no state,
  e manteve o CLI publico congelado com `rc=44`;
- apos restart, o servico adotou B por `/data`, com marker/hash validos,
  1 processo de `/data`, 0 de fallback e deep-health `passed=true`;
- o rollback lab-only usou `expected_rolled_to=A`, quarentenou B e retornou
  para A como `previous` real, nao para `image_fallback`;
- apos rollback e restart, o servico readotou A por `/data`, com deep-health
  `passed=true`;
- depois da coleta, a placa foi limpa com rollback lab-only adicional para
  `image_fallback`; o launcher voltou a logar `kiosk_source=fallback`.

O que este marco **nao** afirma: thaw publico, GitHub publish, auto-pull,
stable/producao, cold-boot adoption, durabilidade sob corte de energia,
power-loss no meio do apply/rollback, soak/endurance ou gate server-side de
publicacao.

## Hardening pre-cold-boot/power-loss apos ABA

A auditoria critica do marco ABA aprovou a evidencia, mas apontou dois riscos
que precisam estar na imagem antes de exercitar cold boot ou interrupcao fisica:

- o `ExecStartPre` de reconcile roda como root e mexe em `/data`, entao o
  drop-in do `kiosky-player.service` passa a exigir `RequiresMountsFor=/data`
  e `After=local-fs.target`;
- a release `player-runtime` extraida passa por fsync estrito de arquivos e
  diretorios antes de ser marcada como verificada e promovida;
- o reconcile ja rejeita release "torn" por `tree_sha_mismatch`; o teste
  `test_player_runtime_torn_release_falls_back_on_reconcile` fixa esse
  fail-closed;
- o deep-health passa a rejeitar segmento final curto sem progresso comprovado,
  fechando a cauda residual do caso multi-segmento.

Essas mudancas foram embarcadas na `1s` e validadas em cold-boot do baseline de
imagem/fallback. Isso ainda nao prova cold-boot com
`/data/player-runtime/current` verificado nem interrupcao/power-loss no meio de
apply/rollback. Elas nao descongelam o CLI publico e nao mudam as
nao-afirmacoes do ABA.

## Follow-up pos-1s: evidencia de boot e crash-boundary offline

Apos a convergencia da auditoria da `1s`, o repo passou a preparar a proxima
rodada de laboratorio sem alterar a golden declarada:

- novo coletor `scripts/board/c18_coldboot_state_collect.py`, read-only por
  padrao, gera `boot-state-public.json` no schema
  `dadooh.c18.coldboot_state.v2`;
- novo gate `scripts/qa/c18_coldboot_evidence_gate.py` exige discriminadores
  de boot (`boot_id` hasheado, `btime`, uptime pos-boot), estado de mount de
  `/` e `/data`, contrato systemd do player e ausencia de vazamentos antes de
  aceitar uma evidencia como cold-boot;
- quando uma evidencia cold-boot reivindicar adocao real de `/data`, o gate
  tambem exige `launcher-adoption.json` com processo, marker valido e identidade
  rodando batendo com o marker; presenca de `kiosk.py` em `/data/current` nao
  basta;
- `totem_updatectl.py` ganhou fault-injection de teste no caminho real de
  apply/rollback de `player-runtime`, permitindo provar offline que interrupcoes
  em fronteiras de extract, health, marker, symlink e rollback terminam em
  `current` verificado ou fallback `/opt`;
- reconcile de `player-runtime` agora falha fechado se `state.json` estiver
  corrompido e faz GC conservador de releases invalidas/orfas nao ligadas por
  `current`/`previous`;
- a quarentena de rollback passa a ser persistida antes do ponto de falha
  injetavel, reduzindo risco de readocao automatica apos crash.

Isso ainda nao e prova fisica de corte de energia nem cold-boot com uma release
real em `/data/player-runtime/current`. E um gate offline novo para reduzir o
espaco de descoberta antes do proximo ensaio em hardware.

A imagem correspondente foi derivada e validada em placa como
`c18-hwdecode-lab-1t`. Ela embarca o coletor/gate de boot-state e os
hooks/testes de crash-boundary e passa a substituir a `1s` como golden de
laboratorio/delivery:

- **Imagem candidata/golden:** `c18-hwdecode-lab-1t`;
- **Arquivo WSL:**
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1t_minimal.img`;
- **Copia para gravacao:**
  `/mnt/d/images_orange/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1t_minimal.img`;
- **SHA-256:** `7ab5a582f2ce51f13338be8ad4a68a15cb736007f617a49456704c5c45cefec6`;
- **Validacao offline:** `OFFLINE_VALIDATION_PASSED=True`,
  `artifact_promoted=true`, `board_touched=false`, `ssh_used=false`;
- **Validacao hardware:** marker `1t` presente; config real ajustada ao contrato
  C18 (`mpv_path=/opt/totem/bin/totem-mpv-hwdecode`) pelo writer guardado;
  `kiosky-player.service` ativo com `NRestarts=0`; MPV efetivo em
  `/opt/totem/hwdecode/bin/mpv`; freeze publico `rc=44` para
  `player-runtime` apply/rollback/reconcile e para `kiosky-player` rollback;
  boot reconcile autorizado `rc=0`; coldboot gate `passed=true`;
  deep-health `passed=true`;
- **Evidencia hardware:** `docs/evidence/c18-update-validation/20260605T093008Z-1t-coldboot-deep-health/`;
- **Nao-afirmacao:** ainda falta validar cold-boot com
  `/data/player-runtime/current` verificado, corte de energia fisico durante
  apply/rollback, thaw publico, auto-pull, stable/producao e soak.

Nota pos-auditoria: a `1t` segue como golden historica de laboratorio, mas a evidencia
cold-boot da `1t` prova consistencia interna dos discriminadores e nao
autenticidade criptografica. Para o proximo trial `/data`, o repo agora exige um
handoff mais forte: `pre-state-public.json` mecanico antes do reboot,
`boot-state-public.json` referenciando esse pre-state por `sha256`/nonce,
identidade da imagem pelo marker em `/etc/dadooh`, e manifesto com
`repo_commit`/`repo_tree`/`repo_dirty=false`. O gate forte deve usar
`--require-pre-state`; se a rodada reivindicar power-cycle fisico, tambem deve
usar `--forbid-controlled-reboot`.

Nota pos-auditoria `d60661b`: para evidencia cold-boot que seleciona `/data`,
ou demonstra `/data` por marker/probe, o modo forte deixa de ser disciplina
manual e passa a ser fail-closed: sem pre-state forte e sem identidade esperada
de imagem, o gate reprova mesmo sob `--expect-selected-source=any`. O gate de
evidencia `player-runtime` tambem exige identidade de repo e imagem no manifesto
e compara `repo_commit` com o `source_commit` do pacote. A golden corrente fica
em `docs/evidence/c18-update-validation/current-golden.json`; gates e testes
devem ler essa fonte unica para evitar drift no proximo bump. O runner
persistente continua sendo um trial warm de apply/rollback; cold-boot `/data`
decisivo usa o M-6 de duas fases. Para essa rodada, o release gate deve rodar
com `--player-runtime-evidence-mode decisive`,
`--player-runtime-data-coldboot-evidence-dir` e
`--player-runtime-data-evidence-dir`; nesse modo os dois artefatos sao
obrigatorios, a imagem e pinada contra a golden, e o marker/version/tree/kiosk
sao cruzados entre warm e cold-boot. Sem modo `decisive`, o gate segue validando
apenas o baseline historico `fallback`.

## Marco M-6 antigo: `/data` cold-boot de player-runtime

O trial M-6 foi executado em hardware com a golden `c18-hwdecode-lab-1t`,
sem descongelar o CLI publico de `player-runtime`.

- **Commit do runner/pacotes:** `695298f`;
- **Pacote A:** `c18.player-runtime-m6-a-20260605T183103Z-m6-695298f-retry2`;
- **Pacote B:** `c18.player-runtime-m6-b-20260605T183103Z-m6-695298f-retry2`;
- **Evidencia auditavel:**
  `docs/evidence/c18-update-validation/20260605T183103Z-1t-player-runtime-m6-data-coldboot-trial/`;
- **Resultado historico:** o gate legado aceitou a evidencia em modo `decisive`
  na epoca. O gate atual e mais estrito e exige
  `requires.updater_features` com
  `c18-player-runtime-verify-then-promote-v1`; esta evidencia antiga nao deve
  ser usada como autorizacao `decisive` atual;
- **Prova:** apply A -> apply B, B adotado de
  `/data/player-runtime/current` apos reboot real, deep-health de B passado,
  rollback para A via `/data` previous, deep-health pos-rollback passado, e
  freeze publico `rc=44` preservado;
- **Nao-afirmacao:** ainda nao e thaw publico, nao publica em GitHub, nao
  habilita auto-pull/stable/producao, nao prova corte fisico de energia e nao
  substitui soak/endurance.

Aprendizados operacionais do M-6: o candidate-health rejeitou corretamente
canario fora do contrato (`/data/state/...`, aceito apenas em `/tmp` ou
`/data/media`); e a quarentena por `tree_sha256` bloqueou reuso de B com mesmo
conteudo, exigindo payloads A/B unicos para novas rodadas sem limpar
quarentena.

## Candidata 1p (offline; descartada em hardware)

O commit `cbc51da` fecha a camada necessaria para um trial persistente
auditavel de `player-runtime` em `/data`, sem descongelar o CLI publico:

- health de candidato iniciado como root passa a executar o `kiosk.py` candidato
  como usuario nao-root (`totem` por padrao);
- `totem_updatectl.py` recompila a identidade do release depois do deep-health e
  antes do marker/promote, rejeitando mutacao pos-health;
- rollback lab pode quarentenar o `current` testado para impedir readocao
  automatica do candidato revertido;
- novo `c18_player_runtime_adoption_probe.py` prova se o servico adotou
  `/data/player-runtime/current` ou fallback `/opt`;
- novo `c18_player_runtime_persistent_trial.py` orquestra apply local,
  deep-health do candidato, restart, prova de adocao, rollback, prova
  pos-rollback e manifesto de evidencia;
- `c18_player_runtime_evidence_gate.py` passou a validar semantica dos
  artefatos, hashes e privacidade, nao apenas allowlist de arquivos.

Por tocar arquivos da imagem, foi gerada candidata offline:

- **Imagem candidata:** `c18-hwdecode-lab-1p`;
- **Arquivo:**
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1p_minimal.img`;
- **sha256:**
  `4b772435fd7b32340f3db5a1d69ecd7f9ba843e6964a285077e4266298430008`;
- **Tamanho:** `1971322880` bytes;
- **Validacao offline:** `offline_validation_passed=true`,
  `player_runtime_sandbox_passed=true`, `player_runtime_release_gate_passed=true`,
  `totem_core_ota_ready=true`, `no_player_runtime_current_embedded=true`,
  `no_legacy_kiosky_player_current_embedded=true`;
- **Validacao hardware:** NO-GO. A placa confirmou marker/policy/timer/freeze,
  mas o `ExecStartPre` de reconcile rodava sob `User=totem` e falhava com
  permissao em `/data/player-runtime`, mascarado pelo prefixo nao-fatal `-`.
  Como a higiene de boot nao estava efetiva, `1p` nao vira golden e nao deve
  ser usada para trial persistente em `/data`.

## Promocao 1q (offline + hardware)

`1q` substitui `1p` sem abrir o fluxo publico de `player-runtime`: o drop-in do
player agora usa `ExecStartPre=-+/usr/bin/env ... reconcile --component
player-runtime ...`, mantendo o comando nao-fatal, mas executando a higiene de
estado com privilegio suficiente para gerenciar `/data/player-runtime`, que e
root-owned na imagem. Os testes estaticos e a validacao offline passaram a
travar esse detalhe para evitar regressao silenciosa.

- **Imagem candidata:** `c18-hwdecode-lab-1q`;
- **Arquivo:**
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1q_minimal.img`;
- **sha256:**
  `d487bf33737d5af4ba4bbf7859163cf21f0762ef4c5180f2aed3685e4aa5c009`;
- **Tamanho:** `1971322880` bytes;
- **Validacao offline:** `offline_validation_passed=true`,
  `image_fixed_player_dropin_reconciles_player_runtime=true`,
  `player_runtime_sandbox_passed=true`, `player_runtime_release_gate_passed=true`,
  `totem_core_ota_ready=true`, `no_player_runtime_current_embedded=true`,
  `no_legacy_kiosky_player_current_embedded=true`;
- **Validacao hardware:** marker `1q`, policy restrita a `totem-core`, timer
  desligado, service de update apontando para `totem-core`, drop-in do player
  com `ExecStartPre=-+... reconcile --component player-runtime
  --allow-player-runtime-maintenance`, reconcile de boot `noop` sem erro de
  permissao, config real escrita via writer a partir do seed, player fallback de
  imagem ativo, `kiosky-player` e `player-runtime` bloqueados com `rc=44` no
  fluxo publico, e deep-health de servico `passed=true` com progresso de frame,
  `hwdec-current=v4l2request-copy`, `media_load_failed=0`, `mpv_restart=0`,
  `NRestarts_delta=0`, panfrost/mmc/ext4 `0`.
- **Evidencia auditavel:** `docs/evidence/c18-update-validation/20260605T025337Z-1q-service-deep-health/`.
- **Status:** promovida a golden de laboratorio/delivery; ainda
  `final_image=false`, nao stable e nao batch de producao.

## Promocao 1m (offline + hardware)

Os commits pós-golden `31b1245`, `93354fb` e `dc21a37` fecham follow-ups de
auditoria que vivem em arquivos da imagem: deep-health com progresso de frame
obrigatorio, freeze simetrico de rollback para componentes congelados,
documentacao encontravel dos health gates, teste de rollback `totem-core` e
guarda de sanitizacao do doc 188. Por isso a proxima candidata de imagem e
`c18-hwdecode-lab-1m`, promovida a golden de laboratorio/delivery apos
validacao em placa.

- **Imagem candidata:** `c18-hwdecode-lab-1m`;
- **Arquivo:**
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1m_minimal.img`;
- **sha256:**
  `d932eadba28f8fac5b737bed750d6dba2732064b79877601ceb0ed3f113a7d8c`;
- **Tamanho:** `1971322880` bytes;
- **Validacao offline:** `OFFLINE_VALIDATION_PASSED=True`,
  `artifact_promoted=true`, `totem_core_ota_ready=true`,
  `player_runtime_ota_still_frozen=true`, `player_runtime_release_gate_passed=true`,
  `player_runtime_sandbox_passed=true`;
- **Validacao hardware:** marker `1m`, policy restrita a `totem-core`, timer
  desligado, service de update apontando para `totem-core`, `reconcile` no
  `kiosky-player.service`, config real escrita via writer a partir do seed,
  `kiosky-player` e `player-runtime` bloqueados com `rc=44` em apply e
  rollback, OTA GitHub `totem-core` apply/rollback/reapply aprovado, e
  deep-health final `passed=true` com MPV da stack C18, HW decode
  `v4l2request-copy`, progresso de frame, `media_load_failed=0`,
  `mpv_restart=0`, panfrost/mmc/ext4 `0`.
- **Status:** golden de laboratorio/delivery; ainda `final_image=false`, nao
  stable e nao batch de producao.

## Implementação no repo

- `scripts/board/totem_update_policy.json`: policy canônica C18 lab/homologation.
- `scripts/board/systemd/totem-update-agent.service`: alvo `totem-core`, com
  `ConditionPathExists=/data/updates/policy.json`.
- `scripts/board/totem_appliance_manifest.json`: timer manifestado como
  `enabled=false`.
- `scripts/build/totem_core_image_embed.py`: escreve policy/service/timer e
  remove o symlink `timers.target.wants/totem-update-agent.timer` na rootfs.
- `scripts/board/totem_updatectl.py`: bloqueia apply de `kiosky-player`, aplica
  regra conservadora de downgrade, limpa staging em `incoming`, pagina releases
  do GitHub, falha fechada sem policy e rejeita manifests/payloads com contrato
  C18 incompleto ou tipos de tar inseguros.
- `scripts/qa/c18_ota_release_gate.py`: gate offline unico para merge/publicacao
  de `totem-core`, incluindo pacote real quando informado.

## Gates

- Testes estáticos de policy/service/timer.
- Testes unitários de freeze, downgrade e GC de staging.
- Sandbox `totem-core` apply/rollback/settings-lock.
- Validacao offline + hardware da imagem corrente deve comprovar policy
  presente, timer desligado, service apontando para `totem-core`, sem config
  real embutida, `player-runtime` ainda congelado e launcher adotando `/data`
  apenas com marker verificado.

## Contrato futuro de OTA

Toda release C18 nova de `totem-core` deve declarar no manifest:

- `requires.base_image_min="c17.4.2"` para esta linha;
- `requires.device_track="c18-hwdecode"`;
- `requires.updater_features` contendo `c18-freeze-kiosky-player-v1`,
  `c18-rollback-reapply-v1`, `c18-safe-payload-v1` e `c18-track-v1`.

Updater `1h+` que nao encontrar esses campos, nao entender uma chave nova em
`requires`, encontrar track diferente, base incompatível, feature ausente ou
feature desconhecida deve rejeitar a release. Se uma mudanca futura precisar
novo updater, nova unit, novo pacote do sistema, player/MPV/hwdecode ou reboot
para se tornar verdadeira, ela nao pertence ao OTA normal de `totem-core`; deve
vir como nova imagem ou release ponte explicitamente homologada.

## Estado live, imagens e OTA smoke (2026-06-02)

- Imagem gerada: `c18-hwdecode-lab-1e`
  (`sha256=b782421c684783bdeba029c90b014f3a469888d34d69caf524e5a69d88dff211`),
  ainda `final_image=false` / lab privada.
- Base C17.4.2 lida de `/mnt/d/images_orange`; symlink local mantido em
  `armbian-build-v25.11/output/images/` para o deriver continuar reprodutivel.
- Validação offline da rootfs: policy presente, timer sem wants symlink,
  service apontando para `totem-core`, `totem-core` current/fallback presentes,
  `state.json` com `manifest_created_at_utc`, fsck limpo.
- Validação em placa limpa apos flash:
  - marker `c18-hwdecode-lab-1e` presente;
  - `totem-update-agent.timer` `disabled`/`inactive`;
  - `totem-update-agent.service` aponta para
    `--component totem-core --repo dadoohai/orange_pi_totem`;
  - `/data/updates/policy.json` permite somente `totem-core`;
  - `/data/apps/kiosky-player/current` ausente; player usa fallback C18 em
    `/opt/totem/kiosky-player`.
- Config real aplicada via seed de homologacao local, sem publicar valores
  privados: `/data/config/config.json` criado pelo writer guardado; artefatos
  temporarios privados removidos.
- Player pos-config: `player_running`, `playback=playing`, display conectado,
  `NRestarts=0`.
- MPV pos-config: processo em `/opt/totem/hwdecode/bin/mpv` via wrapper C18,
  `--vo=gpu --gpu-context=drm --hwdec=v4l2request-copy`,
  `hwdec-current=v4l2request-copy`, `vo-configured=true`.
- Amostra curta de playback pos-config: 2 trocas de item, `failures=0`,
  `NRestarts=0`, RSS ~118 MB, CPU ~45% de um core nos itens amostrados.
- Guarda de regressao confirmada: `apply-local --component kiosky-player`
  falha com `rc=44` (`component_frozen_for_ota`), independente da policy.
- Residuo conhecido fora do escopo C18: `console-setup.service` falhado no boot
  por setup de fonte/keymap; nao afetou player/OTA e nao deve abrir frente agora.
- Release homologation publicada para smoke manual:
  `totem-core-c18.ota-core-smoke-20260602T190718Z-8a1d640`.
  Manifest: `component=totem-core`, `channel=homologation`,
  `source_branch=foundation-v0.1`, `source_commit=8a1d640...`,
  `source_dirty=false`, `payload_sha256=a8e67c3112fb31e6f4718ac97e4c7a39f5a56e72bf8bf833febcd62f25d09674`.
- `apply-github-latest --dry-run` selecionou exatamente essa release e nao
  mudou estado.
- `apply-github-latest` manual passou: `current` virou
  `c18.ota-core-smoke-20260602T190718Z-8a1d640`, `previous` virou o embed
  `c17.6-environment-input-20260514T211247Z`, policy continuou somente
  `totem-core`, timer continuou desligado, player continuou `active`,
  `NRestarts=0`.
- Rollback real passou para o embed C17.6. A primeira tentativa de reapply
  encontrou bug real no guard de downgrade (`rc=45`) porque a release mais nova
  estava em `previous`.
- Hotfix do updater aplicado in-place na placa lab (backup preservado em
  `/opt/totem/bin/totem-updatectl.pre-c18fix-*`) e incorporado ao repo:
  - reapply de `previous` e mais novo que `current` e permitido com
    `allow_downgrade=false`;
  - versoes/payloads de manifest agora rejeitam `.`/`..`, path traversal,
    path absoluto/subdiretorio e payload fora do nome esperado.
- Repeticao apos hotfix: rollback para C17.6 + reapply GitHub da release C18
  passou com `allow_downgrade=false`; placa terminou em `current=C18 smoke`,
  `previous=C17.6 embed`, player `active`, `NRestarts=0`, timer `disabled`.
- Build offline subsequente gerou `c18-hwdecode-lab-1f` (nao reusar o nome
  `1e`, pois o conteudo do updater mudou apos a imagem `1e` ja ter sido
  gravada/validada).
  - Arquivo:
    `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1f_minimal.img`
  - `sha256=bbcf59950324f6629db56c0d542ce03f25bd8f6ad3b38fb60127d2d219da793f`
  - Tamanho: `1971322880` bytes.
  - `OFFLINE_VALIDATION_PASSED=True`; `totem_core_ota_ready=true`; policy
    presente; timer desligado; service apontando para `totem-core`; sem config
    real embutida.
  - Ainda nao foi validada em hardware como flash limpo.
- Auditoria independente pos-1f apontou P1 de endurecimento antes de campo:
  manifest sem track/features ainda passava no device, `base_image_min` era
  apenas tipado, policy ausente permitia default e tar aceitava links. Esses
  pontos foram tratados no lote `1g`; por isso `1f` fica como validação limpa de
  config/playback, nao como proxima base de campo.
- Build offline subsequente gerou `c18-hwdecode-lab-1g` como endurecimento
  intermediario. A auditoria de governanca seguinte apontou uma fronteira ainda
  porosa: `kiosky_service_launcher.sh` estava no payload/fallback de
  `totem-core`, permitindo que uma OTA de core alterasse o start do player. Por
  isso `1g` foi supersedida antes de validacao em hardware.
  - Arquivo:
    `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1g_minimal.img`
  - `sha256=e6c59038f6141454261e8313ef9dc028782fec13ffcbf42331a23464548defa1`
  - Tamanho: `1971322880` bytes.
  - `OFFLINE_VALIDATION_PASSED=True`; `totem_core_ota_ready=true`; policy
    presente; timer desligado; service apontando para `totem-core`; sem config
    real embutida.
  - Ainda nao foi validada em hardware como flash limpo.
- Build offline subsequente gerou `c18-hwdecode-lab-1h` como fechamento da
  fronteira `totem-core`/`player-runtime`. A validação em placa limpa mostrou
  que a imagem estava correta no contrato OTA, mas o seed de homologacao ainda
  continha `mpv_path="mpv"`; ao gravar a config real, isso sobrescrevia o
  wrapper C18 e fazia o player subir com `/usr/bin/mpv` e
  `hwdec-current=no`. Por isso `1h` foi supersedida antes de virar baseline.
  - Arquivo:
    `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1h_minimal.img`
  - `sha256=778b60b86ea7487e1d4661c3f53f17c598894274fdf76b629d671c80865f8393`
  - Tamanho: `1971322880` bytes.
  - `OFFLINE_VALIDATION_PASSED=True`; `totem_core_ota_ready=true`; policy
    presente; timer desligado; service apontando para `totem-core`; sem config
    real embutida.
  - Contrato de fronteira validado offline:
    `image_fixed_player_kiosky_service_launcher.sh_not_totem_core_wrapper=true`
    e `totem_core_release_excludes_kiosky_service_launcher.sh=true`.
  - Validada em hardware somente ate o achado do seed; nao usar como proxima
    base de campo.
- Build offline subsequente gerou `c18-hwdecode-lab-1i`.
  - Arquivo:
    `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1i_minimal.img`
  - `sha256=5944f284fec4025b021413608a7bc98034a088046d742c09496e634a37074c4e`
  - Tamanho: `1971322880` bytes.
  - `OFFLINE_VALIDATION_PASSED=True`; `totem_core_ota_ready=true`; policy
    presente; timer desligado; service apontando para `totem-core`; sem config
    real embutida.
  - Contrato de fronteira validado offline:
    `image_fixed_player_kiosky_service_launcher.sh_not_totem_core_wrapper=true`
    e `totem_core_release_excludes_kiosky_service_launcher.sh=true`.
  - Seed de homologacao preserva HW decode:
    `homologation_seed_mpv_path_points_to_wrapper=true`.
  - Validada em hardware como flash limpo:
    - marker `c18-hwdecode-lab-1i` presente;
    - policy presente e restrita a `totem-core`;
    - `totem-update-agent.timer` `disabled`/`inactive`;
    - service de update apontando para
      `--component totem-core --repo dadoohai/orange_pi_totem`;
    - `kiosky_service_launcher.sh` fixo na imagem, fora do payload
      `totem-core`;
    - `/data/apps/kiosky-player/current` ausente.
  - Config real aplicada via writer a partir do seed local de homologacao, sem
    publicar valores privados. A config ativa preservou
    `mpv_path=/opt/totem/bin/totem-mpv-hwdecode`.
  - Player pos-config:
    - processo MPV em `/opt/totem/hwdecode/bin/mpv`;
    - `hwdec-current=v4l2request-copy`;
    - `media_load_failed=0`;
    - `NRestarts=0`;
    - sem erros panfrost na amostra curta.
  - OTA local de `totem-core` validado na placa com pacote gerado do commit
    `e56fddb`: apply, rollback e reapply passaram; o player permaneceu ativo e
    com HW decode apos cada etapa.
  - Release GitHub de homologacao publicada e validada end-to-end:
    `totem-core-c18.ota-core-1i-github-smoke-20260603T012036Z-09ba8d1`.
    - Manifest: `component=totem-core`, `channel=homologation`,
      `source_commit=09ba8d15154b15ff83569ce0acbab50258121366`,
      `source_dirty=false`.
    - Payload SHA256:
      `e57dd720d21e429fae8271a153913ee96db5c0576e38df97be74f94a8a436254`.
    - Dry-run na placa selecionou exatamente essa release e retornou
      `state_changed=false`.
    - Apply GitHub, rollback e reapply GitHub passaram; ao final a placa ficou
      em `current=c18.ota-core-1i-github-smoke-20260603T012036Z-09ba8d1` e
      `previous=c17.5-core-mvp-20260602-231123-e56fddb`.
    - O player permaneceu `active`, `NRestarts=0`, MPV em
      `/opt/totem/hwdecode/bin/mpv`, `hwdec-current=v4l2request-copy`,
      `media_load_failed=0`, sem erros panfrost/mmc na janela de validacao.
  - Tentativa de OTA de `kiosky-player` continuou bloqueada com
    `rc=44` (`component_frozen_for_ota`).
- Build offline subsequente gerou `c18-hwdecode-lab-1j`.
  - Arquivo:
    `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1j_minimal.img`
  - `sha256=995d0a90e6449f8f8e8e58f788fb38ba9196dacb4312cb28ecbd6041cda1c152`
  - Tamanho: `1971322880` bytes.
  - `OFFLINE_VALIDATION_PASSED=True`; `totem_core_ota_ready=true`; policy
    presente; timer desligado; service apontando para `totem-core`; sem config
    real embutida.
  - Delta sobre `1i`: `totem-kiosky-launcher.sh` tambem e arquivo fixo de
    imagem/player-runtime, fora do payload `totem-core`; o default do launcher
    agora usa `/data/player-runtime/current`, e o caminho legado
    `/data/apps/kiosky-player/current` nao sombreia mais o player validado.
  - Contrato de fronteira validado offline:
    `image_fixed_player_kiosky_service_launcher.sh_not_totem_core_wrapper=true`,
    `image_fixed_player_totem-kiosky-launcher.sh_not_totem_core_wrapper=true`,
    `totem_core_release_excludes_kiosky_service_launcher.sh=true` e
    `totem_core_release_excludes_totem-kiosky-launcher.sh=true`.
  - Validada em hardware como flash limpo:
    - marker `c18-hwdecode-lab-1j` presente;
    - policy presente e restrita a `totem-core`;
    - `totem-update-agent.timer` `disabled`/`inactive`;
    - service de update apontando para
      `--component totem-core --repo dadoohai/orange_pi_totem`;
    - `totem-kiosky-launcher.sh` fixo na imagem, usando
      `/data/player-runtime/current` e sem default para
      `/data/apps/kiosky-player/current`;
    - `/data/player-runtime/current` ausente e
      `/data/apps/kiosky-player/current` ausente, portanto player usa fallback
      validado da imagem;
    - config real escrita via writer guardado a partir do seed local de
      homologacao, sem publicar valores privados; config ativa ficou
      `0640 root:totem` e preservou
      `mpv_path=/opt/totem/bin/totem-mpv-hwdecode`;
    - player pos-config em playback `playing`, IPC ativo,
      `hwdec-current=v4l2request-copy`, `vo-configured=true`, `NRestarts=0`;
    - deep-health de playback passou em hardware:
      `hwdec_no_unexpected=true`, `media_load_failed_zero=true`,
      `panfrost_faults_zero=true`, `mmc_timeout_reset_zero=true`,
      `single_mpv=true`, `playback_progressed=true`,
      `transitions_observed_when_required=true`;
    - probes temporarios de deep-health foram removidos da placa apos a coleta.
  - Contrato OTA pos-flash:
    - `apply-local --component kiosky-player` bloqueado com `rc=44`;
    - `apply-local --component player-runtime` bloqueado com `rc=44`;
    - antes da nova publicacao, `apply-github-latest --component totem-core
      --dry-run` retornou `rc=0` e selecionou a release de homologacao 1i, sem
      aplicar mudanca.
- Release GitHub de homologacao publicada a partir do HEAD `1e040c0` e validada
  end-to-end na placa `1j`:
  `totem-core-c18.ota-core-1j-github-smoke-20260603T142540Z-1e040c0`.
  - Manifest: `component=totem-core`, `channel=homologation`,
    `source_branch=foundation-v0.1`,
    `source_commit=1e040c0672d08606717b8048313194afc50d8c86`,
    `source_dirty=false`.
  - Payload SHA256:
    `d3073d2e3756b9ae102be216831ad3b6b363ba7d7b580e852e46d7d4f7c92856`.
  - Gate de release passou com o pacote antes da publicacao; a release foi
    publicada como prerelease e a tag aponta para o `source_commit`.
  - Dry-run na placa selecionou exatamente essa release e retornou
    `state_changed=false`.
  - Apply GitHub passou: `current` virou
    `c18.ota-core-1j-github-smoke-20260603T142540Z-1e040c0`, `previous` ficou
    `c17.6-environment-input-20260514T211247Z`, player permaneceu `playing`,
    `hwdec-current=v4l2request-copy`, `NRestarts=0`, `media_load_failed=0`.
  - Rollback passou para o embed C17.6; `previous` virou a release 1j, player
    permaneceu `playing`, `hwdec-current=v4l2request-copy`, `NRestarts=0`,
    `media_load_failed=0`.
  - Reapply GitHub passou; ao final a placa ficou em `current` na release 1j e
    `previous` no embed C17.6, com player `playing`,
    `hwdec-current=v4l2request-copy`, `vo-configured=true`, `NRestarts=0`,
    `media_load_failed=0`.
- Release GitHub de homologacao com mudanca funcional pequena de `totem-core`
  publicada a partir do HEAD `2a7a327` e validada end-to-end na placa `1j`:
  `totem-core-c18.ota-core-config-missing-20260603T150429Z-2a7a327`.
  - Escopo: somente status preview publico de `config_missing` em
    `totem_status_render_preview.py`, com self-test novo no pacote/gate. Nao
    toca player, launchers, MPV/hwdecode, updater, units, policy, Wi-Fi real ou
    field-data.
  - Manifest: `component=totem-core`, `channel=homologation`,
    `source_branch=foundation-v0.1`,
    `source_commit=2a7a3272cd49a2e0742d2a4ad070de588771877d`,
    `source_dirty=false`.
  - Payload SHA256:
    `908bb4dc38e2b19f94cdf1f9cdacbaa6e7f2a5d546e21747882bc93d5eed9d4d`.
  - Gate de release passou com o pacote antes da publicacao; a release foi
    publicada como prerelease e a tag aponta para o `source_commit`.
  - Dry-run na placa selecionou exatamente essa release e retornou
    `state_changed=false`.
  - Apply GitHub passou: `current` virou
    `c18.ota-core-config-missing-20260603T150429Z-2a7a327`, `previous` ficou
    `c18.ota-core-1j-github-smoke-20260603T142540Z-1e040c0`;
    o arquivo ativo em `/data/core/totem/current/bin` continha a nova copia
    publica de `config_missing`, `totem_status_render_preview.py --self-test`
    passou, player permaneceu `active`, `hwdec-current=v4l2request-copy`,
    `vo-configured=true`, `NRestarts=0`.
  - Rollback passou para a release 1j; a copia nova saiu do slot `current`,
    player permaneceu `active`, `hwdec-current=v4l2request-copy`,
    `vo-configured=true`, `NRestarts=0`.
  - Reapply GitHub passou; ao final a placa ficou em `current` na release
    `c18.ota-core-config-missing-20260603T150429Z-2a7a327` e `previous` na
    release 1j, timer `disabled/inactive`, player `active`,
    `hwdec-current=v4l2request-copy`, `vo-configured=true`, `NRestarts=0`.
  - Tentativas de apply de `kiosky-player` e `player-runtime` continuaram
    bloqueadas com `rc=44`.
- Build offline subsequente gerou `c18-hwdecode-lab-1k` como candidata da
  fundacao de thaw seguro do `player-runtime`.
  - Arquivo:
    `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1k_minimal.img`
  - `sha256=d0aae1e0dc234be1d9071b7f88d913b1dfb0f89d980904e9c2dc9291e648ac5e`
  - Tamanho: `1971322880` bytes.
  - `OFFLINE_VALIDATION_PASSED=True`; `totem_core_ota_ready=true`;
    `player_runtime_release_gate_passed=true`;
    `player_runtime_sandbox_passed=true`.
  - Delta sobre `1j`: imagem inclui launcher com marker `.release_verified.json`
    sha-bound, `kiosk_py_sha256`, `tree_sha256`, `deep_health.passed`,
    quarentena, fallback fail-closed para `/opt`, reconcile/state hygiene,
    lab-thaw guard e primitivas verify-then-promote para homologacao futura.
  - Checks offline adicionais: service `kiosky-player` roteado pelo
    `totem-kiosky-launcher.sh`; sem `/data/player-runtime/current`; sem
    `/data/apps/kiosky-player/current`; sem marker pre-forjado em `/data`;
    `player-runtime` e `kiosky-player` continuam congelados no fluxo publico
    (`rc=44`).
  - Validada em hardware como flash limpo em 2026-06-03:
    - marker `c18-hwdecode-lab-1k` presente;
    - policy presente e restrita a `totem-core`;
    - `totem-update-agent.timer` `disabled`/`inactive`;
    - service de update apontando para
      `--component totem-core --repo dadoohai/orange_pi_totem`;
    - `kiosky-player.service` roteado por `totem-kiosky-launcher.sh`;
    - `/data/player-runtime/current` e `/data/apps/kiosky-player/current`
      ausentes; player usa fallback validado da imagem;
    - config real escrita via writer guardado a partir do seed local de
      homologacao, sem publicar valores privados; config ativa ficou
      `0640 root:totem` e preservou
      `mpv_path=/opt/totem/bin/totem-mpv-hwdecode`;
    - player pos-config em playback `playing`, playlist com 9 itens,
      `hwdec-current=v4l2request-copy`, `vo-configured=true`,
      `video-codec=H.264`, `NRestarts=0`;
    - contadores da janela: `media_load_failed=0`, `mpv_restart=0`,
      panfrost fault real `0`, `mmc_timeout/reset=0`, erros EXT4/IO `0`;
    - `apply-github-latest`/rollback/reapply de `totem-core` passaram na placa;
      ao final `current=c18.ota-core-config-missing-20260603T150429Z-2a7a327`
      e `previous=c17.6-environment-input-20260514T211247Z`;
    - tentativas de apply de `kiosky-player` e `player-runtime` continuaram
      bloqueadas com `rc=44`.

## Continuidade pos-compactacao

1. Tratar `c18-hwdecode-lab-1u` como baseline de laboratorio/delivery validada
   para a frente OTA/manual, ainda `final_image=false`; `1t` permanece historica.
2. Fluxo manual de release GitHub `totem-core` validado na 1n com mudanca real
   de aplicacao, rollback e reapply; as golden posteriores herdam esse contrato
   e adicionam validacao de imagem/deep-health com evidencia auditavel.
   Proximas mudancas de wizard/core devem seguir este gate antes de aplicar em
   placa, mantendo
   auto-pull desligado e `kiosky-player`/`player-runtime` congelados ate thaw
   explicito.
3. Proxima frente da jornada de delivery: preparar a liberacao controlada de
   `player-runtime` sem descongelar producao. Frentes de display, Wi-Fi aberta,
   cursor/UX de wizard e acesso de manutencao ficam adiadas ate o delivery estar
   pleno.

## Marco 2026-06-03 — Fundacao De Thaw Seguro Do Player-Runtime

- O `player-runtime` continua congelado no CLI publico (`rc=44`), mas o repo
  agora contem primitivas reais e testaveis para um thaw futuro de laboratorio:
  verify-then-promote, marker `.release_verified.json` sha-bound, fallback
  fail-closed para `/opt`, quarentena por identidade de conteudo e rollback
  interno de `player-runtime`.
- O launcher de player nao adota mais `/data/player-runtime/current` apenas por
  existir `kiosk.py`: ele recomputa `kiosk_py_sha256` e `tree_sha256`, valida o
  marker escrito pelo updater e recusa identidade quarentenada. Qualquer duvida
  volta para `/opt/totem/kiosky-player`.
- O gate de `player-runtime` passou a rejeitar `hwdec="no"`, `mpv_path`
  inseguro, args MPV perigosos literais dentro de `build_mpv_args`
  (`--script`, config externo, YTDL, IPC/hwdec hard-coded inseguro), marker
  pre-forjado, paths de controle/imagem e payload SHA adulterado.
- O sandbox de `player-runtime` deixou de provar uma copia da mecanica e passou
  a chamar as primitivas reais do updater com health hook injetavel. Ele valida:
  apply A/B, rollback roundtrip, marker corrompido -> `/opt`, health que observa
  fallback rejeitado, falha com previous e sem previous, hygiene/reconcile de
  `state.json`, `/data` sem marker caindo para `/opt`, e freeze preservado.
- O boot adoption seguro fica no launcher: ele valida marker/hash/quarentena no
  momento de escolher `/data` ou `/opt`. O `reconcile` do updater e higiene
  explicita para state/symlink drift, nao a barreira primaria de boot. Por
  poder mexer em symlink/state de `player-runtime`, o comando de manutencao
  passa a exigir `--allow-player-runtime-maintenance` +
  `C18_PLAYER_RUNTIME_RECONCILE=1`; o `ExecStartPre` da imagem fornece essa
  autorizacao de forma explicita e nao-fatal.
- Ja existe builder local lab-only de `player-runtime`
  (`scripts/deploy/build_player_runtime_release_package.sh`) e collector real
  nao destrutivo (`scripts/board/c18_playback_health_collect.py`). Ainda nao ha
  publisher, thaw em hardware nem health hook de candidato isolado. O sandbox
  prova fluxo/estado com health hook injetavel; nao prova decode real de uma
  release candidata em hardware nem durabilidade sob corte de energia. Esses sao
  os proximos gates antes de qualquer release real de player.
- Auditoria adversarial pos-1k confirmou dividas pre-thaw que **nao afetam a
  golden enquanto `rc=44` estiver ativo**, mas bloqueiam qualquer thaw real:
  validar os args efetivos entregues ao `Popen` (nao so strings literais em
  `build_mpv_args`), impedir mutacao de `cfg["hwdec"]`/`args` fora do caminho
  controlado, ligar `reconcile` em boot ou documentar formalmente o launcher
  como reconcile primario, e fazer o deriver abortar/limpar artefato se a
  validacao offline falhar.
- Rodada repo-side pos-1k fechou essas tres dividas imediatas sem descongelar o
  componente: o gate de `player-runtime` agora valida o caminho efetivo
  `build_mpv_args -> subprocess.Popen(args, ...)` e cobre bypasses de args/cfg;
  o drop-in do player executa `reconcile --component player-runtime` como
  `ExecStartPre=-...` nao-fatal; e o deriver constroi em arquivo temporario,
  promovendo `.img/.sha256` final apenas depois de `offline_ok`. Por mudar
  conteudo de imagem, a proxima candidata passa a ser `c18-hwdecode-lab-1l`; a
  `1k` permanece golden validada.
- Build offline da candidata `c18-hwdecode-lab-1l` passou:
  `OFFLINE_VALIDATION_PASSED=True`, `artifact_promoted=true`,
  `sha256=146b430972b61523cf943f467b94ccf56697843a48147ec5b1839db3583b1ad3`.
  Validacao em hardware como flash limpo tambem passou: marker `1l`, drop-in
  com `reconcile` efetivo, policy restrita a `totem-core`, timer desligado,
  config real escrita pelo writer, playback em HW decode
  `v4l2request-copy`, `media_load_failed=0`, `mpv_restart=0`, faults
  panfrost/mmc/ext4 `0`, OTA GitHub `totem-core`
  dry-run/apply/rollback/reapply aprovado, e `kiosky-player`/`player-runtime`
  ainda bloqueados com `rc=44`. Naquele marco, a `1l` substituiu a `1k` como
  golden de laboratorio/delivery da epoca.
- Rodada seguinte de entrega adicionou e validou em hardware o collector
  nao-destrutivo de deep-health sobre a `1l`, sem alterar servico/config:
  janela curta de 45s com `45/45` amostras IPC bem-sucedidas,
  `hwdec-current=v4l2request-copy`, `vo-configured=true`, 3 aliases observados,
  `NRestarts_delta=0`, `media_load_failed=0`, `mpv_restart=0`,
  panfrost/mmc/ext4 `0`, servico ainda `active` apos a coleta. Tambem adicionou
  limpeza de release candidata rejeitada no fluxo interno de `player-runtime`,
  guard contra sobrescrever releases ja ligadas como `current`/`previous`, e
  builder local lab-only de pacote `player-runtime` que so promove artefatos
  apos o gate passar, mantendo o CLI publico congelado com `rc=44`.
- Rodada de governanca seguinte manteve o foco em velocidade segura: o gate
  C18 ganhou `--base-ref` para pegar mudanca commitada em paths
  `player-runtime`/image-fixed, `stable` passou a falhar fechado sem evidencia
  de promocao aprovada, o publisher de `totem-core` preserva
  `c18-ota-release-gate.json` como evidencia, o builder/gate de
  `player-runtime` rejeitam canal `stable`, e o sandbox de `player-runtime`
  agora aceita um pacote real gerado pelo builder alem dos pacotes sinteticos.
  Auditoria subsequente fechou dois pontos load-bearing desse publish: o
  publisher agora exige `--base-ref`/`C18_OTA_BASE_REF` em vez de tratar como
  recomendacao, e compara o SHA da evidencia stable publicada com
  `stable_promotion_evidence_sha256` declarado no manifest.
- Frente seguinte iniciou a ponte para health real de `player-runtime` sem thaw
  publico: o collector ganhou modo `candidate` e filtro de processo por
  `--input-ipc-server`, permitindo coexistir com o MPV do servico vivo; foi
  adicionado o runner lab-only
  `scripts/board/c18_player_runtime_candidate_health.py`, que exige
  `C18_PLAYER_RUNTIME_CANDIDATE_HEALTH_LAB_ONLY=1` +
  `--lab-only-candidate-runner`, cria config temporaria sanitizada e devolve
  hashes observados do release candidato. Isso ainda nao prova DRM/HW em placa
  nem descongela `player-runtime`; e a base para a proxima validacao de
  hardware controlada.
- Foi adicionado tambem o harness
  `scripts/qa/c18_player_runtime_lab_apply.py`: local-only, exige
  `C18_PLAYER_RUNTIME_LAB_APPLY=1` + `--lab-only-apply`, roda o gate do pacote,
  injeta o health hook e confirma que o CLI publico continua `rc=44`. Ele nao
  usa GitHub, timer, policy permanente nem auto-pull; usa `data_root`
  temporario por padrao e so toca `/data` com
  `--allow-device-data-root` + `C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1`.
  Serve para a primeira validacao lab de apply real de candidato, ainda antes de
  qualquer thaw publico.
- A rodada pos-1n acrescentou o escape simetrico
  `scripts/qa/c18_player_runtime_lab_rollback.py`: local-only, exige
  `C18_PLAYER_RUNTIME_LAB_ROLLBACK=1` + `--lab-only-rollback`, roda rollback ou
  reconcile interno de `player-runtime`, registra links `current`/`previous`
  antes/depois, confirma que o CLI publico continua bloqueado com `rc=44`, e so
  toca `/data` com
  `--allow-device-data-root` + `C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1`.
  Esse harness e pre-condicao antes de qualquer ensaio persistente em
  `/data/player-runtime/current`.
- Auditoria adversarial pos-harness encontrou dois buracos pequenos mas
  load-bearing antes de thaw: o deep-health aceitava `time_pos` avancando mesmo
  com `estimated_frame_number` congelado, e `rollback --component kiosky-player`
  nao seguia o mesmo freeze `rc=44` do apply. A correcao consolidada exige
  progresso de frame estimado presente/avancando, presence-guard para contadores
  de falha, freeze de rollback para todo componente em `OTA_FROZEN_COMPONENTS`,
  e bloqueio de `stable` nos scripts historicos de release de `kiosky-player`.
- Marco pos-1m: primeiro `player-runtime` lab apply real em hardware passou sem
  descongelar o CLI publico. Foi gerado pacote local homologation a partir do
  snapshot governado (`c18.player-runtime-lab-20260604T030359Z-0059de4`), o
  harness rodou com `C18_PLAYER_RUNTIME_LAB_APPLY=1`, `data_root` temporario em
  `/tmp`, `github_used=false`, `network_required=false`,
  `device_data_root=false`, e confirmou `public_cli_apply_still_frozen rc=44`.
  O candidato foi validado com canario local offline, marker
  `.release_verified.json` `verdict=verified`, MPV da stack C18,
  `hwdec-current=v4l2request-copy`, `vo-configured=true`, progresso de frame,
  `media_load_failed=0`, `mpv_restart=0`, panfrost/mmc/ext4 `0`. Em hardware,
  o candidato precisou de janela controlada com `kiosky-player.service` parado
  para liberar DRM master; o servico foi religado e o deep-health do player
  normal passou ao final.
- Marco pos-1n / commit `3af11d4`: o apply lab-only foi repetido em hardware a
  partir da golden `1n`, com pacote local homologation
  `c18.player-runtime-lab-20260604T155628Z-3af11d4`
  (`payload_sha256=d87bbd6439c6d4ee4c8197fa54ba003fba87a4716a664f943734323e30c50c0d`).
  Alem do apply `rc=0` em `data_root` temporario sob `/tmp`, a rodada executou
  o novo harness `c18_player_runtime_lab_rollback.py`: rollback `rc=0`,
  reconcile `rc=0`, `public_cli_apply_still_frozen=true` e
  `public_cli_rollback_still_frozen=true`. O deep-health do candidato aprovou
  todos os checks publicos, incluindo `hwdec_expected_present`,
  `hwdec_no_unexpected`, `mpv_path_c18_stack`, `playback_progressed`,
  `media_load_failed_zero`, `mpv_restart_zero`, panfrost/mmc/ext4 `0`. A
  coleta longa do servico real apos restart tambem passou, com uma transicao
  observada e 1 MPV. Nada tocou `/data/player-runtime/current`, GitHub, timer ou
  policy permanente. Ressalva de governanca: essa rodada foi registrada como
  resumo de sessao, nao como pacote de evidencia versionado; ela autoriza
  preparar o proximo ensaio, mas nao deve ser usada sozinha para destravar thaw
  ou homologacao. O proximo ensaio persistente precisa preservar os artefatos
  sanitizados que lastreiam `passed=true` e exercitar rollback real sobre o
  mesmo `data_root` que recebeu o candidato. A proxima rodada deve usar o
  orquestrador lab-only `scripts/qa/c18_player_runtime_persistent_trial.py`
  para produzir `candidate-health-result.json`, `launcher-adoption.json`,
  `service-after-restart/`, `service-after-rollback/` e
  `evidence-manifest.json`. A evidencia deve passar por
  `scripts/qa/c18_player_runtime_evidence_gate.py --run-dir <dir>` antes de ser
  versionada; esse gate agora valida semantica, hashes e privacidade, nao
  apenas presenca de arquivos.

## Fora de escopo

- Ligar auto-pull.
- OTA de `kiosky-player`/MPV/hwdecode.
- Soak 24h.
- Rotação 270.
- Read-only/C12.
- Kernel/U-Boot/DTB/BSP, pacotes NetworkManager e `apt upgrade`.

## Promocao 1n (offline + hardware)

Apos a golden `1m`, a rodada `1f378a9` fechou mais um caso de fault-injection
pre-thaw: se o health hook interno do `player-runtime` levantar excecao, o
updater agora rejeita o candidato, preserva o `current` anterior, limpa
release/stage e registra `candidate_rejected` sem promover nem quarentenar
automaticamente uma falha de harness/ambiente. O sandbox passou a cobrir
`health_hook_exception_keeps_previous_current` e
`health_hook_exception_cleans_release_and_stage`.

Por tocar `totem_updatectl.py`, essa correcao exigiu nova imagem antes de
validacao em placa. A candidata offline gerada e validada em hardware foi:

- **Imagem candidata:** `c18-hwdecode-lab-1n`;
- **Arquivo:**
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1n_minimal.img`;
- **sha256:**
  `29fac35be322416ddd2e93caddb50396bff325e2fba5d219309c2f37f6349f7c`;
- **Validacao offline:** `OFFLINE_VALIDATION_PASSED=True`,
  `artifact_promoted=true`, `totem_core_ota_ready=true`,
  `player_runtime_ota_still_frozen=true`, `player_runtime_release_gate_passed=true`,
  `player_runtime_sandbox_passed=true`;
- **Validacao hardware:** marker `1n`, policy restrita a `totem-core`, timer
  desligado, config real escrita via handoff/writer a partir do seed, player
  fallback de imagem ativo, `kiosky-player` e `player-runtime` bloqueados com
  `rc=44` em apply e rollback, OTA GitHub `totem-core` dry-run/apply/rollback/
  reapply aprovado, staging limpo, e deep-health final `passed=true` com
  `hwdec-current=v4l2request-copy`, progresso de frame, `media_load_failed=0`,
  `mpv_restart=0`, panfrost/mmc/ext4 `0`.
- **Status:** promovida a golden de laboratorio/delivery; ainda
  `final_image=false`, nao stable e nao batch de producao.

## Promocao 1o (offline + hardware, pos-guard/evidence-gate)

Apos a golden `1n`, o commit `b766b4a` fechou a lacuna de governanca do
`reconcile --component player-runtime`: o comando publico volta a ficar
congelado com `rc=44`, e a higiene de boot passa a exigir autorizacao explicita
(`--allow-player-runtime-maintenance` + `C18_PLAYER_RUNTIME_RECONCILE=1`) no
`ExecStartPre` da imagem. A mesma rodada tambem adicionou o gate de evidencia
sanitizada para o proximo ensaio persistente de `player-runtime`.

Por tocar `totem_updatectl.py`, drop-in systemd e scripts de deep-health, essa
rodada exigiu nova imagem antes de validacao em placa. A candidata offline
gerada e validada em hardware foi:

- **Imagem candidata:** `c18-hwdecode-lab-1o`;
- **Arquivo:**
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1o_minimal.img`;
- **sha256:**
  `07f9ee4f3f870f0fdb083eba7992a24b166939c768fc962e44a18d781117b164`;
- **Validacao offline:** `OFFLINE_VALIDATION_PASSED=True`,
  `artifact_promoted=true`, `totem_core_ota_ready=true`,
  `player_runtime_ota_still_frozen=true`, `player_runtime_release_gate_passed=true`,
  `player_runtime_sandbox_passed=true`, `ready_for_manual_card_flash=true`;
- **Validacao hardware:** marker `1o`, policy restrita a `totem-core`, timer
  desligado, service de update apontando para `totem-core`, `reconcile` no
  `kiosky-player.service` com autorizacao explicita de manutencao, config real
  escrita via writer a partir do seed, player fallback de imagem ativo,
  `kiosky-player` e `player-runtime` bloqueados com `rc=44` no fluxo publico,
  e deep-health de servico `passed=true` com progresso de frame,
  `hwdec-current=v4l2request-copy`, `media_load_failed=0`, `mpv_restart=0`,
  `NRestarts_delta=0`, panfrost/mmc/ext4 `0`.
- **Evidencia auditavel:** `docs/evidence/c18-update-validation/20260605T003747Z-1o-service-deep-health/`.
- **Status:** promovida a golden de laboratorio/delivery; ainda
  `final_image=false`, nao stable e nao batch de producao.
