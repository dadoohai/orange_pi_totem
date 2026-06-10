# C18 player-runtime — thaw continuation plan & gate ledger

Status: H1 MAIN PATH PROVEN ON HW (no thaw, no stable/publish). Baseline: HEAD `f1aa879`,
tree clean. Gates, ALWAYS pinned to their invocation: baseline `c18_ota_release_gate.py`
(no evidence args) = 37/37; DECISIVE `--player-runtime-evidence-mode decisive` with the 3
evidence dirs + the image-`1x` triple = 43/43 (the 6 extra steps are the decisive-evidence
validation; 43/43 is the CANONICAL communication number). Each ADDITIONAL teardown dir adds
3 validation steps: with BOTH committed teardown dirs (original + fresh-ipc-probe) the same
invocation is 46/46. The probe itself adds ZERO steps (a teardown dir with or without
`fresh_ipc_probe.json` validates at the same step count). Freeze `rc=44` intact. Golden = `1u`; the decisive evidence is image `1x`
(the H2 split below). Canonical claim while req#4 is open: "main path proven on HW;
fresh-IPC corner deferred (non-claim)" -- NEVER "H1 closed". Off-board critical path
A1/A2/A3/A5 committed; decisive bundle committed at `f1aa879`.

This is the single authoritative ledger of what stands between the committed
teardown/panfrost detector and a safe player-runtime thaw, plus the ordered
continuation path. Grounded in code/contract; cross-checked by a 5-front
investigation (2026-06-09).

## Two horizons (thaw is not one decision)

- **H1 — player-runtime lab→homologation:** prove, on hardware, that a governed
  `/data/player-runtime/current` release decodes (v4l2request-copy), tears down
  clean (panfrost zero), and adopts/rolls back correctly. The nearest milestone.
- **H2 — stable/production thaw:** strictly higher bar — `ALLOW_C18_STABLE_PROMOTION=1`
  + approved `dadooh.c18.stable_promotion.v1`, stable policy, physical homologation,
  defined rollback. Gated on H1. CI / signing / image-A-B are explicitly
  "hardening futuro" (`UPDATE_CONTRACT.md:439-440`), off the immediate path.

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
| **fresh-IPC corner (req#4) exercised on HW** | **EXERCISED on HW (2026-06-10)**: probe forced the corner on the adopted runtime (staged 0.01s; healthy-mpv socket-up ≈0.03s); C1 fresh quit ran (proc alive + `_ipc=None`) and honestly fell back to SIGTERM (`fresh_failed_fallback_sigterm`, gens 1+2); teardown gate green on-board; evidence `…185956Z-1x-teardown-fresh-ipc-probe`. GR4b (fresh SUCCESS) stays NON-CLAIM by policy — operator decision (c) still pending for any success-path probing. OPEN GAP: the corner's own SIGTERM teardown has NO kernel window of its own (see Front #1 item 5) | **H1 — req#4 EXERCISED (reachability + honest fallback; NOT "fix proven"); corner panfrost window = open gap; pending external-auditor ratification** |
| GPU-fault matcher recall calibration vs real board | **OPEN (needs board corpus)** | H1 — adjacent |
| `mpv_path`/config-real boot-time assertion (baseline-regression vector) | **DONE** (boot guard landed `4ed4829`; adoption proven on HW) | H1 — adjacent (baseline) |
| H2 image-identity split (`1u` golden vs `1x` decisive evidence) | **LATENT/UNRESOLVED** (`1w` superseded by the fresh `1x` bundle) | evidence-integrity precondition |
| Offline power-loss matrix (7/17 boundaries) | **PARTIAL (by design)** | PARALLEL/FUTURE |
| Physical power-cut (apply/rollback) | **ABSENT** | LATER (homologation) |
| 24h soak/endurance | **ABSENT** | LATER (production) |
| player-runtime stable-promotion authorization | **ABSENT** | LATER (production) |
| Server-side publish gate / signature / auto-pull | **ABSENT** | LATER (production) |
| Thaw barriers (`:123` toggle + `:967` stable block) → evidence-bound gate | **DESIGN-ONLY** | gating mechanism |

## Critical path

### Front #1 — fresh-IPC corner (req#4): the remaining H1 item

Converged statement (2026-06-10; auditor refutation + 3 independent static verifiers, HEAD
`f1aa879`): the `_fresh_ipc_command(["quit"])` CALL-SITE **is production-reachable** via the
`start_ipc_timeout` corner — `_start_locked` → Popen ok → `_open_ipc` timeout →
`_stop_locked` → `_request_quit` with proc alive + `_ipc is None`. Production callers: boot
`start()`, watchdog `ensure_running`/`restart ipc_unresponsive`, playback `media_load_failed`
restarts. No config gate: `mpv_query_uses_fresh_ipc` gates QUERIES only; the quit fallback is
unconditional. What remains scoped + hedged (and is exactly what the HW probe tests) is the
SUCCESS outcome — a fresh quit against a late-but-up socket. **Therefore req#4 is PROVE, not
retire-as-dead-code.** The probe answers whether the C1 fix (`3cd3586`) avoids the SIGTERM
fallback in the `start_ipc_timeout` scenario.

Work order:
1. **[LANDED off-board — board validation PENDING]** The probe now stages the corner
   END-TO-END on an ISOLATED kiosk instance of the adopted runtime (production service
   untouched; probe runs after all cycles so its noise lands outside the fault windows):
   workspace dirs PRE-CREATED before the access preflight, an OFFLINE CANARY PLAYLIST
   (REQUIRED — `--fresh-ipc-probe-canary-media`, video under /tmp or /data/media; without
   content the kiosk exits `no_content` rc=2 BEFORE `mpv.start()` and the corner is
   unreachable), and a staged short `mpv_startup_timeout_sec` (default 0.05s). Sanitized
   probe artifacts are sealed inside the run dir (re-derivable). Off-board-tested against a
   fake kiosk that only emits the fresh line when staging is complete; the REAL kiosk
   reaching the corner is exactly what the board session validates. Previously the probe
   only restarted the service: on a healthy board the corner was never reached and the gate
   red-failed (`fresh_ipc_probe_code_path_not_reached`).
2. **[LANDED off-board]** `forced_ipc_none` is no longer hardcoded: it reflects REAL staging
   (regression-tested); staging failures (kiosk/canary missing, workspace inaccessible,
   probe exception) degrade to an honest not-forced artifact + probe-error file, WITHOUT
   losing the cycles' evidence. An un-staged probe REDs the gate (`fresh_ipc_probe_not_forced`).
3. **[OPERATOR DECISION — required BEFORE the board session]** Gate policy for a GENUINE
   `fresh_sent`: today it is rejected by design (`fresh_ipc_probe_success_path_unreachable_claim`,
   test-locked) so a success can never be silently read as "GR4b proven". If the board ever
   yields a genuine success, the gate REDs and a human decides. Pre-agree the protocol
   (recommended: keep fail-closed; treat a success as a NEW fact → preserve evidence as
   diagnostic → authorized gate evolution) so a success does not stall the session.
4. **[DONE on board 2026-06-10 — pending external-auditor ratification]** Trial ran with
   `--with-fresh-ipc-probe`: attempt #1 (0.05s) revealed a HEALTHY mpv exposes its IPC
   socket in ~0.03s (corner not fired — gate honestly REDed; kept on-board as diagnostic);
   attempt #2 (0.01s) forced the corner deterministically — `code_path_reached=true`,
   `fresh_failed_fallback_sigterm` with the real ENOENT log (generations 1 AND 2), 3 cycles
   panfrost delta=0, teardown gate green end-to-end. Evidence committed:
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
   claim beyond "main path proven + req#4 exercised (GR4b non-claim)" awaits the external
   auditor's ratification AND item 5 below. Closing H1 is NOT thaw: H2 + the future gates
   (physical power-loss, soak, server-side) still stand.
5. **[OPERATOR DECISION — wrapper×quit-path tension + corner panfrost window]** No current
   harness measures a SIGTERM against a DECODING mpv anywhere (cycles are `ipc_quit`; the
   candidate teardown SIGTERMs the KIOSK, which quits mpv cleanly; the corner SIGTERM hits
   an embryonic mpv). Options: (a) wrapper carries the panfrost thesis → measure panfrost
   around BOTH teardown kinds (ipc_quit + a real mid-decode SIGTERM) and retire GR4b as
   panfrost-irrelevant; (b) the quit method matters → add kernel-before/after capture to
   the probe (decision-neutral, cheap) + resolve real GR4b reachability (live socket) under
   an authorized gate evolution; (c) LAYERED reading — wrapper = primary fix (measured),
   quit-path = defense-in-depth at a rare corner → capture the probe kernel window (cheap)
   and keep GR4b non-claim. The kernel-window capture in the probe serves (a), (b) AND (c);
   it is implemented only after the operator picks, to avoid rework if (a) widens scope.

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
   is internally image-consistent. NOTE: *building a new image to reconcile the `1u`/`1w`
   label (D2 options A/C) is OVERSCOPED for H1* — only the triple needs to be right.
   The prior `1w` "decisive authorization" is STALE vs the current gate (it predates the
   teardown requirement); the board run produces FRESH decisive evidence.
6. **This ledger doc** (done) + write the **operator run-book** (board-session mechanics
   ONLY — a broad production run-book is H2 overscope). The run-book MUST sequence:
   teardown trial (≥2 same-boot cycles, no reboot) → M6 arm/reboot/resume **with
   `--defer-release-gate`** (else M6 red-fails demanding the teardown dir) → capture the
   clean-board `journalctl -k -b` corpus AND eyeball it for any `panfrost|lima|mali` line
   the matcher did NOT flag (recall is the gate's weakest link) → copy evidence into the
   repo tree → **COMMIT it** (not just `git add` — `repo_clean_guard` reds on staged files and
   the git-guard reds on untracked, so only a commit yields a clean, git-tracked tree) → run ONE
   host-side `c18_ota_release_gate.py --…-mode decisive` with all three evidence dirs.
7. *(Parallel/FUTURE — NOT H1; do not spend critical-path effort here)* extend the offline
   power-loss matrix + launcher torn-tree negative test + matrix-scope doc. Power-loss
   evidence is NOT required by the decisive gate (`c18_ota_release_gate.py:751`, optional);
   the launcher is already proven fail-closed.

### B. BOARD (single amortized session, when available)
- M6 (one operator reboot) + teardown (≥2 same-boot cycles + real service restart) +
  capture the clean-board journal corpus → evidence that passes the decisive release gate
  from a clean tree. Sequencing: teardown needs ≥2 cycles with NO reboot between; M6 needs
  one reboot — script the session so panfrost baselines don't cross-contaminate.
- *(batch)* physical power-cut + 24h soak.

### C. LATER (production / H2, gated on H1)
- player-runtime stable-promotion authorization schema (analog of `stable_promotion.v1`).
- server-side publish gate / signature / auto-pull hardening.
- DESIGN (not land) the `:123`/`:967` → evidence-bound thaw gate so thaw is a checked
  condition, not a hand-flip. Landing is a separate authorized step.

## OTA responsibility snapshot (2026-06-10 — converged with the external auditor)

| Frente OTA | Estado atual | Falta |
| --- | --- | --- |
| totem-core | Operacional e mais maduro; policy/freeze/timer/downgrade governados | Hardening de produção/stable (incl. `created_at` obrigatório) |
| player-runtime | Caminho principal provado em HW: apply A2/B2, coldboot, rollback, teardown sem panfrost | fresh-IPC req#4 (Front #1 acima), H2 golden 1u×1x, depois decisão de thaw |
| kiosky-player | Continua congelado; protegido pelo mesmo freeze público (rc=44) | Não é frente de thaw; depende da governança do player-runtime |
| media-system / field-data | Fora do ciclo atual | Trazer ao padrão de evidência quando priorizado |
| server-side/publish | Ausente por design; auto-pull/stable off | Publish gate, assinatura, canais |
| power-loss/soak | Parcial; reboot controlado provado, power-cut não | Power-cut físico, torn-write, soak 24h |

Estado: `f1aa879` limpo; placa estável; nenhuma execução em andamento; próxima frente
definida = fresh-IPC (aguardando OK do operador). Funil: fresh-IPC → H2 → decisão de thaw.

## Decision points that genuinely need the operator (everything else proceeds)
- **D1 — Matcher policy:** greedy-now (reversible, fail-closed on known wordings) for the
  first decisive run vs block until a deny-by-default allowlist from a real clean-board
  corpus. Bears on invariant (i). *Default: greedy-now + build the tunable tooling; revisit
  on the board.*
- **D2 — H2 end-state:** (A) bump golden→`1w` [board], (B) keep `1u` + formalize split
  [off-board, cheapest], (C) supersede with a new unified image [board]. *Default: do B
  groundwork now; final A/B/C deferred to board-session planning.*
- **D3 — `mpv_path` boot gate as hard thaw-prereq vs parallel hardening.** *Default: build
  it now (protects the baseline); labeling is the operator's call but building doesn't block.*
- **D4 — Board availability** + whether to batch teardown + power-cut + soak in one session.
- **D5 — Landing the thaw-barrier conversion** (`:123`/`:967`): sensitive; design only,
  operator authorizes landing.
