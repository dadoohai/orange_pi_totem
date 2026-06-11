# C18 player-runtime HW teardown/panfrost gate — design

Status: DESIGN (lab-only, fail-closed). No public thaw, stable/prod, GitHub auto-pull,
or server-side publish is granted or implied by this document. Golden baseline = `1u`;
current decisive player-runtime H1 evidence is pinned to `1x`. player-runtime and kiosky-player
public update verbs remain frozen (`rc=44`).

## Why this gate exists (grounded, not inferred)

The repo's own canonical milestone is the 1v "teardown failure" evidence
(`docs/evidence/c18-update-validation/20260609T014031Z-1v-player-runtime-teardown-failure/README.md`):

> "prove, on hardware, that **repeated MPV teardown/relaunch AND the production service
> restart path complete with `panfrost_faults_delta == 0`** … the runtime fix must still
> be proven by a new image and M6 run."

Three facts establish the gate's shape (each verified by reading code + adversarial refutation,
high confidence):

1. **The panfrost runtime fix is the wrapper, not C1.** `build_manifest.json:195` attributes
   the panfrost fix to `fix_wrapper_hwdec_copy` (forces `v4l2request-copy`). `SOURCE.json`
   frames C1 fresh-IPC as the *"if needed"* fallback within a broader graceful-quit strategy.

2. **The fresh-IPC (C1) path is a narrow `_ipc is None` corner, not the panfrost-relevant
   teardown path.** In steady-state teardown (`restart()`, SIGTERM, repeated relaunch) `_ipc`
   is a live handle, so `_request_quit` (`kiosk.py:1586-1592`) takes the **persistent**
   `_send(["quit"])` branch. The only writers of `self._ipc=None` are `__init__` and
   `_close_ipc_locked`, and **no path nulls `_ipc` while the mpv process stays alive**
   (exhaustively confirmed). The fresh branch is reachable only at the `start_ipc_timeout`
   corner, where `_stop_locked` fires immediately against a not-yet-connectable socket →
   fresh-IPC **fails → SIGTERM**. The fresh-IPC *success* path is therefore effectively
   **unreachable in production**, and `_start_locked:1655-1656` ("start_ipc_unavailable") is
   dead/defensive code today.

3. **Therefore the gate must be measurement-based and path-agnostic** — it measures
   `panfrost_faults_delta == 0` across repeated teardown/relaunch + a real service restart,
   regardless of which quit path fires. Forcing the fresh-IPC path is a *secondary* check, not
   the centerpiece.

Decision (operator-confirmed 2026-06-09): **measurement-based gate; GR4 secondary; no change
to frozen `kiosk.py`.**

## Requirements (GR*) and how each is met

| ID  | Requirement | Mechanism |
| --- | --- | --- |
| GR1 | ≥2 launch/teardown cycles in the SAME boot | Harness runs N≥2 cycles in one boot; every `cycle.json.boot_id` must equal `teardown-summary.boot_id` (the powerloss boot-transition check, **inverted** to require equality). |
| GR2 | panfrost delta ZERO per teardown window | The gate is the **measurer, not a trust-the-JSON checker**: it RECOMPUTES per-window fault counts from the manifest-bound `kernel-before/after.txt` with `GPU_FAULT_RE` and rejects any `cycle.json` scalar that disagrees. It enforces **ABSOLUTE zero** (no matched fault line in any window — honoring the deep-health `panfrost_faults_zero` contract from raw text, not the trusted boolean) AND `gpu_faults_delta == 0` AND `gpu_faults_delta_anomalous == False`, requires `kernel-before/after.txt` per cycle, and binds `new_fault_lines_sanitized` to the recomputed tail. |
| GR3 | REAL service restart path exercised | ≥1 cycle must have `kind == "service_restart"` (driven via `systemctl restart kiosky-player.service`), and its teardown window is measured like any other cycle. |
| GR4 | a case that forces `_ipc is None` (fresh-IPC) | **Secondary, optional.** `fresh_ipc_probe.json` forces `_ipc is None` via a short `mpv_startup_timeout_sec` (the `start_ipc_timeout` corner) and records, honestly, whether the C1 `_fresh_ipc_command` was reached and whether it `fresh_sent` or `fresh_failed_fallback_sigterm`. GR4b (fresh-IPC quit SUCCESS against a live socket) is an explicit **NON-CLAIM**. |
| GR5 | sanitized, manifest-bound, reproducible evidence | Cloned verbatim from the powerloss gate: bidirectional manifest binding (per-file `bytes`+`sha256`), 40-hex `source_commit`, full sanitization (private IP / secret patterns / sensitive JSON keys / symlink reject / zero-size). |
| GR6 | gates FAIL CLOSED on missing/untracked evidence | Evidence gate fails on missing required files / manifest mismatch. Release gate adds `teardown_evidence_git_guard` (clone of the powerloss git-guard: rejects untracked + git-ignored + manifest-not-tracked) and, in **decisive** mode, a `failed_internal_step` when no teardown evidence dir is supplied. |

### Guardian extra: invariant static check

A static check (`c18_player_runtime_teardown_static_test.py`) parses `kiosk.py` and asserts the
invariant that makes GR4b unreachable today:

- the only `self._ipc = …` assignments are the known 4 sites
  (`__init__` None, `_open_ipc` pipe, `_open_ipc` sock, `_close_ipc_locked` None); and
- `_open_ipc(` is called only from `_start_locked` (no IPC-reconnect path).

If a future change adds an IPC reconnect, or nulls `_ipc` on a send failure without killing the
proc, the fresh-IPC SUCCESS path would become live (untested) — this check FAILS, flagging that
GR4 then needs real proof. It does not modify `kiosk.py`.

## Evidence run-dir layout

```
<run-dir>/
  evidence-manifest.json          # schema dadooh.c18.teardown.evidence_manifest.v1
  README.md
  teardown-summary.json           # schema dadooh.c18.player_runtime.teardown_trial.v1
  setup/service-state-before.json
  cycles/
    cycle-00/                      # >=2 cycle dirs, zero-padded, consecutive
      cycle.json                   # schema dadooh.c18.player_runtime.teardown_cycle.v1
      kernel-before.txt            # sanitized journalctl -k GPU-fault lines (pre-launch)
      kernel-after.txt             # sanitized (post-teardown settle, cursor-anchored)
      health/playback-deep-health-public.json   # schema dadooh.c18.playback.deep_health.v1
    cycle-01/ ...
  fresh_ipc_probe.json            # OPTIONAL (GR4 secondary)
  postcheck.txt
```

### `teardown-summary.json`
`schema, passed(bool), boot_id(str), btime(int), cycles_count(int>=2),
service_restart_cycle_indices(list[int], len>=1), cycles(list[{index,kind,gpu_faults_delta,passed}]),
gr4_secondary_present(bool), non_claims(list[str])`

### `cycles/cycle-NN/cycle.json`
`schema, index(int), kind("relaunch"|"service_restart"), boot_id(str==summary.boot_id),
gpu_faults_before(int), gpu_faults_after(int), gpu_faults_delta(int, SIGNED/un-clamped),
gpu_faults_delta_anomalous(bool), window_anchor{boot_id, monotonic_before, monotonic_after},
stop{method, returncode, elapsed_ms}, process_exited(bool),
new_fault_lines_sanitized(list[str], <=20), passed(bool)`

`passed` ⟺ `gpu_faults_delta==0 AND not gpu_faults_delta_anomalous AND process_exited AND health.passed`.

### `fresh_ipc_probe.json` (GR4 secondary, optional)
`schema, forced_ipc_none(true), forcing_method("short_mpv_startup_timeout_sec"),
code_path_reached(bool), observed_log("MPV IPC fresh command sent command=quit" |
"MPV IPC fresh command failed command=quit"), outcome("fresh_sent"|"fresh_failed_fallback_sigterm"),
process_exited(bool), non_claim(str)`

Gate honesty check: `outcome=="fresh_sent"` ⟺ observed_log is the "sent" line; this probe NEVER
gates `passed` on GR4b. A `non_claim` string is required.

## Fail-closed behaviour (the point of the gate)

The gate emits `{schema, passed, errors[], run_dir, files[]}` and exits non-zero unless `errors`
is empty. It fails closed on, at minimum:

- `teardown-summary.json` missing/!schema/!passed; `cycles_count < 2`; no `service_restart` cycle.
- any cycle `boot_id != summary.boot_id` (not same boot); `gpu_faults_delta != 0`;
  `gpu_faults_delta_anomalous == True`; `process_exited != True`.
- per-cycle deep-health missing a `HEALTH_CHECKS` key or any check not `True`
  (incl. `panfrost_faults_zero` AND `panfrost_faults_delta_zero`).
- missing required files (summary, ≥2 cycle dirs each with `cycle.json`+`health`+kernel-before/after,
  postcheck); manifest undeclared/absent/bytes/sha mismatch; sanitization leak; any symlink.
- `fresh_ipc_probe.json` present but dishonest (outcome/observed_log disagree) or missing `non_claim`.
- (release gate) untracked / git-ignored / manifest-not-tracked evidence; decisive mode with no
  teardown evidence dir.

## Known limitations (what this gate can and cannot prove)

These were surfaced by two adversarial red-team passes and are documented honestly
rather than papered over:

- **Fault-matcher recall is bounded.** `GPU_FAULT_RE` is intentionally greedy
  (fail-closed bias), but a panfrost/lima/mali fault whose wording it does not cover
  is invisible to GR2. The HW run (task #6) MUST validate the matcher against real
  clean-board journal output, and should consider switching to **deny-by-default**
  (flag any `panfrost|lima|mali` line not on a tuned benign allowlist) once real
  clean-board output is known. Until then, GR2's strength is bounded by the matcher.
- **The gate cannot prove the journal was captured on real hardware.** It validates
  structure, manifest binding, sanitization, and recomputes faults from the committed
  text — but the text itself is producer-supplied. The anti-fabrication backstop is the
  release-gate **git-guard** (untracked/ignored rejection + manifest-tracked) plus an
  **operator-attended commit** of reproducible-from-git evidence. A self-consistent but
  fabricated dir passes the gate in isolation; it does NOT pass the release gate without
  being git-tracked and committed by the operator.
- **`window_anchor` monotonics are producer attestations**, not cryptographically bound
  to journal-cursor positions. The gate enforces same-boot + strictly-increasing,
  non-touching, positive-width windows (rejecting duplicated/zero-width/reversed
  photocopies), but a producer that fabricates plausible increasing windows is not
  caught here — again, the git-guard + operator-attended commit are the backstop.

## NON-CLAIMS (honest; do not read any as closed)

- GR4b: fresh-IPC quit SUCCESS against a live socket is NOT proven (unreachable in production
  today); a `fresh_sent` outcome is rejected outright so it can never read as proven.
- Soak/endurance; torn-write/full power-loss matrix; server-side publish/signature; public thaw.
- A green gate **schema/self-test** off-board proves the gate logic, NOT teardown on hardware.
  Teardown/panfrost is proven only by a real HW run committed under this gate. The current
  committed H1 evidence satisfies that for image `1x`; any future image recapture must re-run
  M6 and every image-pinned teardown dir instead of reusing the `1x` evidence.

## Artifacts

- `scripts/qa/c18_player_runtime_teardown_evidence_gate.py` — consumer gate (+ `--self-test`).
- `scripts/qa/c18_player_runtime_teardown_static_test.py` — kiosk.py `_ipc` invariant static check.
- `scripts/board/c18_player_runtime_teardown_trial.py` — HW producer harness (+ `--self-test` for pure logic).
- `scripts/qa/c18_ota_release_gate.py` — wire git-guard + gate; decisive-mode required.

## Addendum 2026-06-10 — fresh-IPC reachability (convergence note; history above unchanged)

Static analysis (external-auditor refutation + 3 independent verifiers, HEAD `f1aa879`)
CONFIRMED the fresh-IPC quit CALL-SITE is production-reachable via the `start_ipc_timeout`
corner (production callers: boot `start()`, watchdog `ensure_running`/`restart
ipc_unresponsive`, playback `media_load_failed` restarts; `mpv_query_uses_fresh_ipc` gates
QUERIES only — the quit fallback is unconditional). This MATCHES this design (the corner was
always described as reachable above); what remains scoped + hedged is the SUCCESS outcome
("effectively unreachable … today"), i.e. a fresh quit against a late-but-up socket. That
hedge is now explicitly the thing the HW probe must test (continuation-plan Front #1), so
req#4 is PROVE, not retire-as-dead-code. The harness probe now stages the corner END-TO-END
(workspace pre-create + offline canary playlist + short `mpv_startup_timeout_sec`, isolated
instance of the adopted runtime; production service untouched) — off-board-tested against a
fake kiosk; the REAL kiosk reaching the corner is what the board session validates — and
`forced_ipc_none` reflects real staging (an un-staged probe REDs
`fresh_ipc_probe_not_forced`). Gate policy UNCHANGED: a genuine `fresh_sent` still REDs
(`fresh_ipc_probe_success_path_unreachable_claim`) pending an explicit operator decision.
