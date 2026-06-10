# C18 player-runtime — thaw continuation plan & gate ledger

Status: PLANNING (no thaw, no stable/publish). Baseline: HEAD `62f60cd`, tree clean,
release gate 37/37. Freeze `rc=44` intact. Golden = `1u`. Off-board critical path
A1/A2/A3/A5 committed (see commits `83e3228`/`e875e21`/`4ed4829`/`62f60cd`).

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
- Freeze `rc=44` symmetric across apply/rollback/reconcile for both components.
- Deep-health evaluator + lab-thaw M6 mechanics + decisive release-gate cross-link: proven.

## Gate ledger

| Gate | Status | Horizon / critical path |
| --- | --- | --- |
| Verify-then-promote + launcher fail-closed boot gate (inv. i/ii; reconcile ExecStartPre is non-fatal repair) | **PROVEN (structural)** | foundation |
| Launcher fail-closed adoption (sha/tree/deep_health/quarantine) | **PROVEN** | foundation |
| Freeze `rc=44` symmetric; lab-thaw M6; decisive cross-link; deep-health eval | **PROVEN** | foundation |
| Baseline image deep-health on HW (`1u`) | **PROVEN** | foundation |
| HW teardown/panfrost detector (the gate) | **BUILT-NOT-RUN** | **H1 — ON (nearest)** |
| Teardown harness `run_trial()` capture path | **ABSENT (off-board gap)** | H1 — ON |
| M6 ↔ teardown ↔ decisive-release-gate integration | **ABSENT (off-board gap)** | H1 — ON |
| GPU-fault matcher recall calibration vs real board | **OPEN (needs board corpus)** | H1 — adjacent |
| `mpv_path`/config-real boot-time assertion (baseline-regression vector) | **ABSENT** | H1 — adjacent (baseline) |
| H2 image-identity split (`1u` golden vs `1w` decisive pin) | **LATENT/UNRESOLVED** | evidence-integrity precondition |
| Offline power-loss matrix (7/17 boundaries) | **PARTIAL (by design)** | PARALLEL/FUTURE |
| Physical power-cut (apply/rollback) | **ABSENT** | LATER (homologation) |
| 24h soak/endurance | **ABSENT** | LATER (production) |
| player-runtime stable-promotion authorization | **ABSENT** | LATER (production) |
| Server-side publish gate / signature / auto-pull | **ABSENT** | LATER (production) |
| Thaw barriers (`:123` toggle + `:967` stable block) → evidence-bound gate | **DESIGN-ONLY** | gating mechanism |

## Critical path

### A. OFF-BOARD now (parallelizable; converts the scarce board trip into a thin, decisive step)
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
