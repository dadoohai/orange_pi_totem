# C18 player-runtime — thaw continuation plan & gate ledger

Status: H1 TEARDOWN/PANFROST EVIDENCE COMPLETE FOR THE CURRENT LAB SCOPE (no thaw,
no stable/publish). Baseline ANCHOR: `6871f21`
— by construction this ledger commits AT-OR-AFTER its anchor, so the anchor may sit one
commit behind the live HEAD; ALWAYS resolve the real HEAD via `git rev-parse` (the resume
rituals do). Tree clean at anchor time. Gates, ALWAYS pinned to their invocation: baseline `c18_ota_release_gate.py`
(no evidence args) = 37/37. After the production-stop hardening, DECISIVE
`--player-runtime-evidence-mode decisive` requires at least one teardown dir with a
`production_stop_probe`; the minimum decisive invocation (M6 coldboot + data + one
production-stop teardown dir + the image-`1x` triple) is the current H1 gate target. The two
older non-production-stop teardown dirs remain historical/diagnostic inputs and are not part
of the current decisive H1 bundle because the stricter status/MPV alignment recomputation
rejects their long or unexplained transition lags. Freeze `rc=44` intact. Golden = `1u`; the
decisive evidence is image `1x` (the H2 split below). Canonical claim NOW: "H1 lab-scope
evidence is complete for the measured paths: main teardown/M6 path + req#4 reachability +
healthy Python-kiosk SIGTERM stop via IPC quit, all image-bound to `1x` and panfrost-delta
clean under the matcher." Inline caveats: GR4b fresh-IPC success, mpv-SIGTERM fallback,
wedged/ipc_unresponsive cleanup, full launcher/systemd cgroup cleanup, power-loss/soak,
server-side publish, stable promotion, and public thaw remain NON-CLAIMS.

This is the single authoritative ledger of what stands between the committed
teardown/panfrost detector and a safe player-runtime thaw, plus the ordered
continuation path. Grounded in code/contract; cross-checked by a 5-front
investigation (2026-06-09).

## Two horizons (thaw is not one decision)

- **H1 — player-runtime lab→homologation:** prove, on hardware, that a governed
  `/data/player-runtime/current` release decodes (v4l2request-copy), tears down
  clean (panfrost zero), and adopts/rolls back correctly. The nearest milestone.
- **H2 — stable/production thaw:** strictly higher bar — H1 green plus full
  17/17 physical power-loss matrix, 24h soak, explicit operator thaw,
  approved `dadooh.c18.stable_promotion.v1`, stable policy, server-side
  publish/signature governance with operational trust evidence, physical
  homologation, and defined rollback. CI expansion and image-A/B remain future
  hardening; signing/server-side governance is an H2 blocker before `stable`/prod.

## Structural foundation (PROVEN — not open work)

The two core invariants hold **by construction** and were re-verified this round:
- (i) a BAD release never becomes active; (ii) a DEGRADED runtime never returns on its own.
- Apply-time: verify-then-promote — deep_health passes (`totem_updatectl.py:1839`),
  identity is re-checked post-health (`:1861-1903`), marker is written (`:1909`), and
  ONLY THEN `current` flips (`:1934`). (Audit-verified ordering.)
- Boot-time: **one fail-closed gate — the launcher** — plus a *non-fatal* reconcile
  repair. The launcher `totem-kiosky-launcher.sh:96-117` recomputes `kiosk_py_sha256`
  + `tree_sha256`, requires `verdict=verified` + `deep_health` passed + not-quarantined,
  else falls back to `/opt` (`:122/:144`). The reconcile `ExecStartPre` is wired `-+`
  (`20-dadooh-launcher.conf:33`) — its failure is IGNORED by systemd, so it is a repair
  step, not a second gate. Invariants (i)/(ii) still hold by construction (verify-then-
  promote + the launcher). (This corrects the stale "launcher only `-f`" note — the
  launcher IS fail-closed now.)
- Freeze `rc=44` for both components: symmetric across apply/rollback; reconcile has an
  EXPLICIT authorized-maintenance escape (`--allow-player-runtime-maintenance` + env,
  pre-existing since `b766b4a`) that performs state-hygiene only (adopts only
  marker-verified releases or falls back to the image; installs no code). The public
  no-flag reconcile stays rc=44. ("Symmetric" tout court was imprecise.)
- Deep-health evaluator + lab-thaw M6 mechanics + decisive release-gate cross-link: proven.

## Gate ledger

| Gate | Status | Horizon / critical path |
| --- | --- | --- |
| Verify-then-promote + launcher fail-closed boot gate (inv. i/ii; reconcile ExecStartPre is non-fatal repair) | **PROVEN (structural)** | foundation |
| Launcher fail-closed adoption (sha/tree/deep_health/quarantine) | **PROVEN** | foundation |
| Freeze `rc=44` symmetric; lab-thaw M6; decisive cross-link; deep-health eval | **PROVEN** | foundation |
| Baseline image deep-health on HW (`1u`) | **PROVEN** | foundation |
| HW teardown/panfrost detector (the gate) | **RUN + PASS on HW** (image `1x`, bundle at `f1aa879`; 3 same-boot cycles, real restart, delta 0) | H1 main path — DONE |
| Teardown harness `run_trial()` capture path | **DONE** (landed + HW-run) | H1 main path — DONE |
| M6 ↔ teardown ↔ decisive-release-gate integration | **DONE** (decisive gate 43/43 at `f1aa879`: M6 A2→B2 arm/controlled-reboot/resume/rollback on `1x`) | H1 main path — DONE |
| **fresh-IPC corner (req#4) exercised on HW** | **EXERCISED on HW (2026-06-10)**: probe forced the corner on the adopted runtime (staged 0.01s; healthy-mpv socket-up ≈0.03s); C1 fresh quit ran (proc alive + `_ipc=None`) and honestly fell back to SIGTERM (`fresh_failed_fallback_sigterm`, gens 1+2). Evidence `…185956Z-1x-teardown-fresh-ipc-probe` remains diagnostic for reachability; under the stricter current status/MPV alignment recomputation it is not part of the green decisive H1 bundle. GR4b (fresh SUCCESS) stays NON-CLAIM by policy. | **H1 — req#4 EXERCISED (reachability + honest fallback; NOT "fix proven")** |
| **Healthy Python-kiosk SIGTERM stop while decoding** | **PROVEN on HW (2026-06-11)**: `production_stop_probe` confirms mpv decoding with `v4l2request-copy`, SIGTERM delivered to `kiosk_pid`, kiosk used IPC quit, no mpv SIGTERM/SIGKILL fallback, `panfrost_delta=0`, mpv gone after kiosk exit, service restored, post-restore deep-health re-derived from sidecars. Evidence `…050939Z-1x-production-stop`, archived at `02e4380`; release gate now requires at least one production-stop teardown dir in decisive mode. | **H1 measured stop path — DONE for the healthy Python-kiosk/IPC-quit path** |
| GPU-fault matcher recall calibration vs real board | **OPEN/ADJACENT**: green means no matcher-covered fault wording appeared in the captured windows; unknown future wording still needs corpus calibration before production claims. | H1-adjacent / H2 hardening |
| `mpv_path`/config-real boot-time assertion (baseline-regression vector) | **DONE** (boot guard landed `4ed4829`; adoption proven on HW) | H1 — adjacent (baseline) |
| H2 image-identity split (`1u` golden vs `1x` decisive evidence) | **FORMALIZED (Option B)**: `current-golden.json` remains `1u` for recovery/delivery baseline; H1 decisive player-runtime evidence is image-bound to `1x` and does not promote baseline/fallback | evidence-integrity precondition — DONE for H1 |
| Offline power-loss semantics matrix (17/17) | **DONE (off-board)**: producer arms 17/17; evidence gate has semantic validators for every required checkpoint and H2 reports an empty `semantics_not_implemented_checkpoints` ledger. This does not replace physical evidence. | H2 governance foundation — DONE |
| Physical power-cut (apply/rollback) | **PARTIAL**: P0 selective set is complete for pilot (5/17); H2 still requires the remaining 12 physical checkpoints. | H2 physical validation |
| 24h soak/endurance | **ABSENT** | LATER (production) |
| player-runtime stable-promotion authorization | **GATE PARAMETERIZED (off-board, default-deny)**: `stable_promotion.v1` now supports `expected_component=player-runtime`; H2 rejects `totem-core` stable evidence for player-runtime thaw. Stable/H2 now consume a dedicated `dadooh.c18.player_runtime.thaw_decision.v1` artifact via `scripts/qa/c18_player_runtime_thaw_decision_gate.py`, so a boolean operator approval is not enough. Real approved stable + thaw-decision evidence is still absent. | H2 production evidence |
| Server-side publish gate / signature / auto-pull | **GATE HARDENED (off-board, default-deny for prod)**: evidence gate now rejects boolean-only claims, symlink/out-of-dir assets and fixture evidence; it requires artifact-bound manifest/payload/release-gate/audit-log files, per-asset attestation proofs or detached signatures, channel, auto-pull, allowlist, staged rollout, rollback and audit log structure. Detached signatures are verified offline with an explicit external trust key, SPKI DER fingerprint, canonical JSON proof, release-set hash, and separate trust-anchor evidence hash-bound by H2/stable. H2 for `player-runtime` consumes this with `expected_component=player-runtime`, so `totem-core` server-side evidence cannot satisfy the player-runtime thaw. The local `player-runtime` builder now preserves `c18-player-runtime-release-gate.json` next to payload/manifest as the future server-side signing input. Real production signing evidence is still absent. | H2 production evidence |
| Homologation pilot readiness (H1.5) | **DONE (off-board, default-deny)**: `scripts/qa/c18_player_runtime_pilot_readiness_gate.py` authorizes only `ring=pilot`, `channel=homologation`, operator-assisted delivery, allowlisted hashed devices, board preflight, and P0 power-loss subset. It keeps `stable`, auto-pull, public thaw, 24h soak, 17/17 power-loss, and signature/attestation as non-claims. | H1.5 controlled pilot / governance |
| H2 readiness evaluator | **DONE (off-board, default-deny)**: `scripts/qa/c18_player_runtime_h2_readiness_gate.py` aggregates H1 decisive evidence, 17/17 physical power-loss checkpoints, 24h soak, server-side publish/signature governance, stable-promotion evidence, and explicit operator thaw decision validated by the dedicated thaw-decision gate. It reports blockers; it does not thaw. | H2 planning / governance |
| Public thaw barriers (`:123` toggle + `:967` stable block) | **ACTIVATION DESIGN-ONLY**: the operator decision artifact gate exists, but the public thaw execution path remains a separate authorized step. | gating mechanism |

## Critical path

### Front #1 — mid-decode / production-stop panfrost window (H1 lab scope closed)

Converged statement (2026-06-10; auditor refutation + 3 independent static verifiers, HEAD
`f1aa879`): the `_fresh_ipc_command(["quit"])` CALL-SITE **is production-reachable** via the
`start_ipc_timeout` corner — `_start_locked` → Popen ok → `_open_ipc` timeout →
`_stop_locked` → `_request_quit` with proc alive + `_ipc is None`. Production callers: boot
`start()`, watchdog `ensure_running`/`restart ipc_unresponsive`, playback `media_load_failed`
restarts. No config gate: `mpv_query_uses_fresh_ipc` gates QUERIES only; the quit fallback is
unconditional. That reachability question is now answered on HW: req#4 is EXERCISED, not
"fix proven." The follow-up H1 window was narrowed and measured as the healthy Python-kiosk
SIGTERM path while mpv was actively decoding; GR4b remains a non-claim.

Work order:
1. **[DONE on board 2026-06-10]** The probe staged the corner
   END-TO-END on an ISOLATED kiosk instance of the adopted runtime (production service
   untouched; probe runs after all cycles so its noise lands outside the fault windows):
   workspace dirs PRE-CREATED before the access preflight, an OFFLINE CANARY PLAYLIST
   (REQUIRED — `--fresh-ipc-probe-canary-media`, video under /tmp or /data/media; without
   content the kiosk exits `no_content` rc=2 BEFORE `mpv.start()` and the corner is
   unreachable), and a staged short `mpv_startup_timeout_sec` (default 0.05s). Sanitized
   probe artifacts are sealed inside the run dir (re-derivable). Off-board-tested against a
   fake kiosk that only emits the fresh line when staging is complete; the board run
   validated the REAL kiosk reaching the corner. Previously the probe
   only restarted the service: on a healthy board the corner was never reached and the gate
   red-failed (`fresh_ipc_probe_code_path_not_reached`).
2. **[LANDED off-board]** `forced_ipc_none` is no longer hardcoded: it reflects REAL staging
   (regression-tested); staging failures (kiosk/canary missing, workspace inaccessible,
   probe exception) degrade to an honest not-forced artifact + probe-error file, WITHOUT
   losing the cycles' evidence. An un-staged probe REDs the gate (`fresh_ipc_probe_not_forced`).
3. **[POLICY STILL FAIL-CLOSED]** Gate policy for a GENUINE
   `fresh_sent`: today it is rejected by design (`fresh_ipc_probe_success_path_unreachable_claim`,
   test-locked) so a success can never be silently read as "GR4b proven". If the board ever
   yields a genuine success, the gate REDs and a human decides. Current protocol: keep
   fail-closed; treat a success as a NEW fact → preserve evidence as diagnostic →
   authorized gate evolution.
4. **[DONE on board 2026-06-10]** Trial ran with
   `--with-fresh-ipc-probe`: attempt #1 (0.05s) revealed a HEALTHY mpv exposes its IPC
   socket in ~0.03s (corner not fired — gate honestly REDed; kept on-board as diagnostic);
   attempt #2 (0.01s) forced the corner deterministically — `code_path_reached=true`,
   `fresh_failed_fallback_sigterm` with the real ENOENT log (generations 1 AND 2), 3 cycles
   panfrost delta=0 under the then-current teardown gate. Evidence committed:
   `docs/evidence/c18-update-validation/20260610T185956Z-1x-teardown-fresh-ipc-probe`.
   Empirical implication for decision (c): the live race band is ~10–30ms after the staged
   deadline — a deliberate success-path probe APPEARS feasible (single-datum estimate,
   timeout ≈0.02s; socket-up jitter uncharacterized), and remains gate-rejected by policy
   until the operator decides. For PRODUCTION (10s timeout) the same datum NARROWS the
   late-but-up band (healthy mpv is far inside 10s; a 10s-stalled mpv likely never exposes
   the socket) — inference from one datum, not proof.
   **SCOPE NOTE (external audit 2026-06-10):** the `panfrost delta=0` above covers the 3
   `ipc_quit` cycles ONLY. The corner's own SIGTERM teardown has NO kernel window of its
   own (the probe runs after the cycles by design; its mpv is embryonic — tens of ms old,
   no decoder/VO active — so a zero delta is the expected-by-construction outcome, but it
   is REASONING + the wrapper thesis, NOT a measured claim). `probe-kiosk-log-tail.txt` is
   a producer-copied excerpt of the probe kiosk.log (same producer-attested class as the
   placeholder kernel windows). What the probe PROVES: req#4 reachability + honest SIGTERM
   fallback. What it does NOT prove: GR4b (fix efficacy) — structurally out of this probe's
   reach at 0.01s AND under the current gate policy — nor corner GPU-cleanliness.
   What this closes: milestone (a) — the corner-never-exercised blocker is RETIRED. The
   claim beyond "main path proven + req#4 exercised (GR4b non-claim)" awaited the external
   auditor's ratification AND item 5 below. Closing the H1 lab-scope evidence is NOT thaw:
   H2 + the future gates
   (physical power-loss, soak, server-side) still stand.
5. **[DONE on board 2026-06-11 — evidence committed at `02e4380`]** The operator
   opened this round in direct response to the (a)-narrow proposal ("vamos abrir a
   próxima rodada então", 2026-06-10). Scope was narrowed after the diagnostic hybrid RED:
   measure the healthy Python-kiosk stop path that production ultimately signals, with mpv
   already decoding, production service stopped/restored by the harness, and GR4b kept a
   NON-CLAIM. Plan CONSOLIDATED by
   a 5-front investigation + 2 adversarial red-teams (both APPROVE_WITH_CHANGES,
   incorporated): **docs/c18-mid-decode-probe-round-spec.md** records the detector contract
   and the 2026-06-11 addendum. Board run `20260611T050939Z-1x-production-stop` passed:
   decode confirmed (`v4l2request-copy`, frames advancing), SIGTERM to `kiosk_pid`, IPC quit
   requested, no mpv SIGTERM fallback, no escalation, `panfrost_delta=0`, mpv no longer
   alive after kiosk exit, service restored, post-restore deep-health green. Subsequent gate
   hardening made this production-stop evidence mandatory in decisive mode and re-derives
   post-restore health from sidecars. Non-claims: mpv-SIGTERM fallback, wedged/IPC-unresponsive
   cleanup, launcher/systemd cgroup cleanup, GR4b success, H2/thaw.

### A. OFF-BOARD (completed this cycle; kept for the record)
1. **Implement teardown harness `run_trial()` capture** (currently a stub): drive N≥2
   same-boot cycles + ≥1 real `systemctl restart kiosky-player`, capture per-cycle
   `journalctl -k -b --output=short-monotonic` GPU-fault windows + boot_id/monotonic
   anchors + per-cycle deep-health + optional fresh-IPC probe, seal manifest. Extend
   `--self-test` to exercise orchestration against journalctl/systemctl shims.
2. **Wire M6 ↔ teardown ↔ decisive gate**: one host-side orchestration that produces
   both evidence dirs and runs `c18_ota_release_gate.py --player-runtime-evidence-mode
   decisive` with `--player-runtime-data-coldboot-evidence-dir` + `--…-teardown-evidence-dir`.
   Prove GREEN end-to-end off-board with synthetic-but-realistic fixtures (dry-run).
3. **`mpv_path` boot-time assertion**: reject/repair a config whose `mpv_path` ≠
   `/opt/totem/bin/totem-mpv-hwdecode` at launcher/ExecStartPre; sandbox-tested. Closes
   the one structural baseline-regression vector (the 1h class).
4. **Matcher tooling**: 3-matcher diff (production / candidate_health / teardown) + a
   clean-board-corpus capture method (committed fixture) so recall is tunable; default
   greedy-now (reversible) and design deny-by-default for after the corpus exists.
5. **Image-identity triple — HARD pre-board blocker (audit-promoted).** Before the board
   trip, fix a single agreed `(image_tag, image_sha256, marker_sha256)` that matches the
   image ACTUALLY on the board, and thread it into every gate invocation
   (`--expect-image-tag/-sha256/-marker-sha256`). The decisive gate defaults these to the
   `1u` golden (`c18_ota_release_gate.py:724`) and the coldboot gate hard-fails on
   `image_tag_mismatch` — a mismatch silently red-fails the decisive run and forces a
   SECOND board trip. Off-board fix: thread the explicit triple + add a release-gate
   cross-check that the decisive bundle (coldboot + data + teardown + powerloss markers)
   is internally image-consistent. NOTE: *building a new image to unify the `1u` golden with
   the `1x` decisive evidence (D2 options A/C) is OVERSCOPED for H1* — only the explicit
   evidence triple needs to be right. The prior `1w` "decisive authorization" is STALE vs
   the current gate (it predates the production-stop teardown requirement); the `1x` board
   bundle is the FRESH decisive H1 evidence.
6. **This ledger doc** (done) + write the **operator run-book** (board-session mechanics
   ONLY — a broad production run-book is H2 overscope). Track A completed: teardown trial
   (same-boot cycles + production-stop probe, no reboot), committed evidence, clean-tree
   decisive release gate reusing the committed `1x` M6 dirs and the current valid
   production-stop teardown dir.
   M6 arm/reboot/resume is only for an explicitly authorized full image recapture and must
   use `--defer-release-gate`.
7. *(Parallel/FUTURE — NOT H1; do not spend critical-path effort here)* extend the offline
   power-loss matrix + launcher torn-tree negative test + matrix-scope doc. Power-loss
   evidence is NOT required by the decisive gate (`c18_ota_release_gate.py:751`, optional);
   the launcher is already proven fail-closed.

### B. BOARD (Track A completed; next board work is H2)
- Track A teardown evidence is committed and gate-passing. If a new image is baked, recapture
  M6 and every image-pinned teardown dir instead of mixing with `1x` evidence.
- Next board work can be either the H1.5 pilot below, if explicitly authorized,
  or H2: physical power-cut/torn-write and 24h soak.

### B2. HOMOLOGATION PILOT (H1.5, controlled, not production)

An intermediate pilot can run before H2 only when the new pilot gate is green.
Scope: `channel=homologation`, operational `ring=pilot`, operator-assisted
delivery, hashed allowlisted devices, explicit rollback owner/window, board
preflight with policy homologation + `allow_prerelease=true`, timer off, public
freeze `rc=44`, expected image/marker identity, and P0 power-loss subset:
`after_current_symlink`, `rollback_after_current_to_previous`,
`rollback_after_previous_removed`, `rollback_after_quarantine`, and
`rollback_after_state_success`.

Runbook: `docs/c18-player-runtime-homologation-pilot-runbook.md`.

Non-claims remain explicit: no production, no stable, no auto-pull, no 24h soak,
no 17/17 power-loss, no signature/attestation, and no public thaw.

### C. LATER (production / H2, gated on H1)
- H2 readiness gate is available off-board and fails closed until every required family
  is present: full 17/17 power-loss matrix, 24h soak, server-side publish/signature
  governance, stable-promotion approval, and explicit operator thaw decision. It is an
  evaluator, not a public thaw mechanism.
- player-runtime stable-promotion authorization evidence: schema/gate support exists
  via `expected_component=player-runtime`; the explicit thaw decision is now a
  separate artifact-bound gate requiring stable channel, operator, rollback owner,
  window, hashes for H2/stable evidence, auto-pull off, no execution performed and
  explicit non-claims. Production still needs real approved evidence.
- player-runtime build artifact traceability: the local builder preserves
  `c18-player-runtime-release-gate.json` beside payload/manifest after validating
  the gate is green, so a future server-side publish/signature run has a real
  release-gate artifact to bind. The current homologation release
  `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1` carries
  `c18-player-runtime-release-gate.json` next to its manifest/payload. This is
  release-gate traceability only; it is not production publication by itself.
- server-side publish governance gate / signature / auto-pull hardening:
  `scripts/qa/c18_server_side_publish_governance_gate.py` valida a evidencia
  `dadooh.c18.server_side_publish_governance.v1` antes do H2 consumi-la; ela
  precisa apontar para artefatos reais no diretorio da release e o gate confere
  hashes contra manifest, payload, resumo do release gate, provas de
  attestation/assinatura e log de auditoria, rejeitando symlink/out-of-dir e
  fixture fora do self-test. Assinatura usa prova JSON canonica, fingerprint
  SPKI DER da chave publica, `release_set_sha256`, chave publica externa via
  `--trusted-key-pem` e evidencia `dadooh.c18.server_side_trust_anchor.v1` via
  `--trust-anchor-evidence`; H2/stable carregam o hash dessa evidencia para
  impedir troca silenciosa da chave. Essa evidencia nao afirma cadeia PKI,
  rejeita campos extras que afirmem PKI e rejeita symlink em qualquer componente
  do caminho da chave ou do trust anchor. O H2 de `player-runtime` passa
  `expected_component=player-runtime`; manifest/release gate de `totem-core`
  ficam bloqueados para essa familia.
  Para o pacote atual
  `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`,
  a familia server-side esta materializada em
  `docs/evidence/c18-update-validation/20260617T191658Z-server-side-current-mpv-stuck-fix-9bebaf1/`
  e o H2 consome essa evidencia com `server_side_publish_governance` verde.
  Isso nao publica release, nao liga auto-pull, nao promove stable e nao e
  publicacao/producao real. Em `2026-07-04`, a decisao stable/thaw e o H2 final
  foram fechados por excecao formal para o soak HDMI-event; a ativacao publica
  segue sendo uma etapa operacional separada.
- stable promotion no caminho CLI/build/publish valida artefatos
  semanticamente, nao apenas hashes: release gate verde, matriz power-loss
  17/17 verde, soak 24h, server-side assinado com trust key externa + trust
  anchor, e decisao de operador aprovada.
- Public thaw activation through `:123`/`:967` remains a separate authorized step;
  the landed thaw-decision gate validates the operator artifact and does not execute
  thaw.

## OTA responsibility snapshot (2026-07-04 — H2 pre-production)

| Frente OTA | Estado atual | Falta |
| --- | --- | --- |
| totem-core | Operacional e mais maduro; policy/freeze/timer/downgrade governados; release gate geral verde na RC; payload protegido por allowlist exata no gate e no device-side antes de extrair/promover | Hardening de producao/stable quando a frente H2 for aberta |
| player-runtime | Homologation RC corrente `9bebaf1` segue congelada no caminho publico (`rc=44`) e agora tem H2 final verde por excecao formal de negocio no snapshot `20260704T214500Z-h2-readiness-business-exception-9bebaf1`: matriz fisica power-loss 17/17 verde, server-side/signature verde, stable promotion verde, thaw decision verde e tracked inputs verdes. O soak de 24h em `20260704T195822Z-soak-24h-hdmi-event-9bebaf1` continua negativo para H2 limpo (`passed=false`), mas foi aceito explicitamente para este alvo pela evidencia `20260704T212428Z-soak-exception-business-release-9bebaf1`. A foto `20260704T221016Z-public-thaw-activation-ready-9bebaf1` validou a prontidao de ativacao. A publicacao GitHub Release foi executada pela rota guardada e registrada em `20260704T224754Z-player-runtime-github-release-published-9bebaf1`, sem executar public thaw na placa e sem habilitar auto-pull. O alvo `c16fb3e` fica historico/bloqueado pela evidencia negativa `20260617T174316Z-h2-powerloss-after-payload-staged-mpv-stuck-135f397` | Executar a etapa operacional separada de consumo/thaw de `player-runtime` na placa/rota de cliente, sem usar publisher de `totem-core`, scripts legados, auto-pull ou manifest stable inventado |
| kiosky-player | Continua congelado; protegido pelo mesmo freeze público (rc=44); build/publish historicos seguem bloqueados por padrao e, mesmo com bypass lab, recusam media/cache/config/data/secrets, systemd, `/opt`, MPV/ffmpeg e modulos | Não é frente de thaw; depende da governança do player-runtime |
| media-system / field-data | Fora do ciclo de release atual, mas agora protegidos por guardrails executaveis na matriz de responsabilidade, no gate de `player-runtime`, nos scripts legados e na allowlist device-side de `totem-core`; `field-data` ja tem snapshot publico C18/C7 gateado e evidencia read-only de placa em `20260612T183722Z-board-readonly-diagnostics-17a1f9d` | Para `media-system`, manter trilha propria de imagem/homologacao; para `field-data`, evoluir evidencia operacional somente sem transformar config/midia/cache em release de software |
| server-side/publish | Gate offline endurecido: evidencia fraca/booleans nao basta; exige artefatos reais hash-bound, sem symlink/out-of-dir, provas de attestation ou assinatura destacada, canais, auto-pull off, allowlist, staged rollout, rollback e auditoria; assinatura confere trust key externa, fingerprint SPKI DER, release-set hash e trust-anchor evidence separada/hash-bound; H2 de `player-runtime` exige `component=player-runtime`; trust key/anchor rejeitam symlink em qualquer componente do caminho e claims PKI extras; fixture nao passa fora de self-test; evidencia atual esta verde para o pacote `9bebaf1` em `20260617T191658Z-server-side-current-mpv-stuck-fix-9bebaf1` | Criar/usar somente uma rota explicita de publicacao/ativacao de `player-runtime`; nao reaproveitar publisher `totem-core` nem scripts legados |
| power-loss/soak | Power-loss fisico H2 fechado: 17/17 checkpoints observados e aceitos pelo H2 readiness gate. Soak 24h com evento HDMI coletado em `20260704T195822Z-soak-24h-hdmi-event-9bebaf1`: nao fecha H2 limpo, mas preserva evidencia de que a aplicacao permaneceu viva sem restart, sem panfrost delta, sem MMC timeout/reset delta e sem ext4 delta. Em `20260704T212428Z-soak-exception-business-release-9bebaf1`, o produto aceitou formalmente essa evidencia como excecao para o alvo `9bebaf1`. Trilhas historicas superseded, preservadas para auditoria: `20260618T080037Z-h2-powerloss-matrix-plan-5of17-9bebaf1` e `20260618T080100Z-h2-powerloss-operator-runbook-remaining-12-9bebaf1` | Nenhum novo power-loss/soak e requisito para este alvo, salvo decisao futura de substituir a excecao por soak limpo |

Estado: Homologation RC de `player-runtime` corrente e `9bebaf1`: H2 final
esta verde por excecao formal de negocio no snapshot
`20260704T214500Z-h2-readiness-business-exception-9bebaf1`. O funil documentado
foi cumprido nesta ordem: soak aceito por excecao -> stable promotion ->
decisao explicita de thaw -> H2 final -> discussao de ativacao/publicacao
separada. A publicacao GitHub Release de `player-runtime` foi executada em
`20260704T224754Z-player-runtime-github-release-published-9bebaf1`, sem inferir
auto-pull, sem usar publisher de `totem-core` e sem converter automaticamente o
pacote homologation em manifest stable. A etapa restante e o consumo/thaw
operacional na placa/rota de cliente, mantendo esses limites explicitos.

## Decision points that genuinely need the operator (everything else proceeds)
- **D1 — Matcher policy:** greedy-now (reversible, fail-closed on known wordings) for the
  first decisive run vs block until a deny-by-default allowlist from a real clean-board
  corpus. Bears on invariant (i). *Default: greedy-now + build the tunable tooling; revisit
  on the board.*
- **D2 — H2 end-state:** **Option B formalized for H1** — keep `1u` as the
  recovery/delivery golden in `current-golden.json`, and treat `1x` as the current decisive
  player-runtime evidence bundle only. Future options remain explicit board work: (A) bump
  golden→`1x` or (C) supersede with a new unified image.
- **D3 — `mpv_path` boot gate as hard thaw-prereq vs parallel hardening.** *Default: build
  it now (protects the baseline); labeling is the operator's call but building doesn't block.*
- **D4 — Board availability** + whether to batch teardown + power-cut + soak in one session.
- **D5 — Landing the thaw-barrier conversion** (`:123`/`:967`): sensitive; design only,
  operator authorizes landing.
