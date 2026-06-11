# C18 mid-decode SIGTERM probe — consolidated round spec (option (a)-narrow)

Status: CONSOLIDATED IMPLEMENTATION CONTRACT (round opened by the operator 2026-06-10).
Produced by a 5-front investigation + 2 adversarial red-teams (robustness, productivity),
both APPROVE_WITH_CHANGES — all blockers incorporated below. Findings verified through
HEAD `aa33576` before implementation landing; live HEAD must still be resolved by git.
No thaw; freeze `rc=44` intact; gate extension STRICTLY ADD-ONLY. Policy memos
in §8 are DRAFT until the operator ratifies (they change nothing until then).

## 1. The gap (verified, with the decisive datum)

- Production SIGTERM-mid-decode is exactly one code path: `kiosk.py:1612-1650`
  (`_stop_locked`: fire-and-forget IPC quit → 5s wait → `os.killpg(SIGTERM)` `:1629` →
  5s → SIGKILL `:1639`; straight-to-SIGTERM if the quit WRITE fails). Mature-mpv callers:
  watchdog `ipc_unresponsive` `:2669`, `media_load_failed` restarts `:3142`, service stop
  `:3438/:3511`. systemd never signals mpv (`KillMode=mixed`,
  `20-dadooh-launcher.conf:20-32`).
- No current harness signals a DECODING mpv (cycles = kiosk-mediated ipc_quit; candidate
  teardown SIGTERMs the KIOSK; the exercised corner SIGTERMs an embryonic mpv).
- **Measured contamination datum (drives the design):** committed 1v evidence
  (`20260609T014031Z-1v-player-runtime-teardown-failure/c18-mpv-relaunch-*.tgz`) shows
  `fault_delta=2` on 3 of 5 LAUNCHES — mpv launch/relaunch inside a measurement window is
  a REAL fault vector. The probe window must contain ONE teardown and ZERO launches.

## 2. Producer contract (PINNED — guardian decision, operator veto window open)

- **Placement:** new optional trial flag `--with-mid-decode-sigterm-probe` (fresh-IPC
  precedent; same sealed run-dir → manifest/sanitization/image-binding free; release-gate
  steps are per-DIR so an in-dir artifact adds ZERO steps). Probe runs AFTER the cycles
  (and after the fresh-IPC probe if any), BEFORE postcheck/seal; own try/except (cycles'
  evidence never lost) + own `finally` on ALL exit paths.
- **Staging:** kiosk-hosted ISOLATED instance of the adopted runtime — reuse the HW-proven
  machinery (`candidate_config` + canary playlist + pre-created dirs + run-user preflight +
  unique workspace/ipc_path). Production service STOPPED during the probe (DRM master),
  prior state recorded.
- **Hybrid teardown (red-team fast-path, adopted):** after decode-confirm, **SIGKILL the
  ISOLATED KIOSK first** (SIGKILL, not SIGTERM, so its handler cannot ipc_quit mpv; mpv
  survives — own session/pgroup via `start_new_session`, `kiosk.py:1676`), THEN open the
  kernel window and SIGTERM mpv. This removes the measured relaunch-in-window vector
  (`ensure_running` dies with the kiosk) while leaving mpv's kernel-side decode state
  (DRM/V4L2/GEM under active decode — the panfrost thesis surface) untouched. Recorded
  honestly: `kiosk_killed_before_signal=true` + non-claim that the kiosk-alive production
  sequence (incl. auto-relaunch) is covered by the trial cycles, not by this probe.
- **Window placement:** kernel-before captured AFTER decode-confirm, then a FINAL
  IPC re-sample/freshness check immediately before the signal (or equivalent timing proof);
  `last-sample-to-signal` MUST be ≤1s and the gate must RED if the kernel-before capture
  made the sample stale. Also re-check `/proc/<pid>` alive + `os.getpgid(pid)==pid`
  immediately before signal. Signal = `os.killpg(mpv_pgid, SIGTERM)` (production parity `:1629`);
  mirror the 5s escalation — **escalation to SIGKILL = outcome
  `mpv_did_not_exit_after_sigterm` → gate RED** (an escalation IS the dangerous-class
  signal, never silently tolerated); settle ≥ `--settle-sec`; kernel-after; `signal.monotonic`
  must fall inside `[monotonic_before, monotonic_after]`; delta
  recomputed from kernel TEXT (signed; ABSOLUTE-zero both windows); window strictly AFTER
  the last cycle window (gate-enforced, `mid_decode_probe_window_overlaps_cycles`).
- **PID chain (no `get_property('pid')` dependency — removes the last on-board unknown):**
  kiosk.log `MPV process started pid=` (`kiosk.py:1685-1690`) + `/proc/<pid>/exe ==
  /opt/totem/hwdecode/bin/mpv` (wrapper execs mpv, PID preserved) + `/proc/<pid>/cmdline`
  contains the unique `--input-ipc-server` path + `os.getpgid(pid)==pid` + `/proc/<pid>/stat`
  starttime stable from decode-confirm through the signal. The IPC `pid` property is
  opportunistic corroboration only.
- **Attempts:** artifact is attempts-ARRAY-shaped (each attempt its own non-overlapping
  window) so N is a runbook pin, not a schema change. Recommended N=2 (~+90s board time;
  pre-empts the predictable "one sample is thin" audit round-trip). Operator pins N.
- **Cleanup `finally` (ALL exit paths, ordered):** kill isolated kiosk (KILL) →
  `_kill_probe_orphans(ws)` → barrier: pgrep-mpv-empty + `fuser /dev/dri` (ported from
  `c18_mpv_relaunch_teardown_probe.py:337-352`) → `systemctl start` → `is-active` poll
  ≤30s (NO re-issue loops — `StartLimitBurst=5`; at most ONE `reset-failed` retry; record
  `settings-session.lock` state) → `service-restore.json` → **REQUIRED post-restore
  deep-health** into the probe dir (the only check distinguishing "restored" from
  "restored-but-black"; ~35s). Restore failure → `service_restored=false` + CRITICAL
  stderr + runbook manual-recovery line (`systemctl start kiosky-player.service`).
- **Preflight BEFORE stopping the production service:** `/run/totem/settings-session.lock`
  ABSENT (service start is a legitimate no-op while it exists —
  `kiosky-player.service:5`) + canary exists/normalized + staging complete. Never enter
  the riskiest window with a dead-on-arrival setup.
- **Honest failure outcomes (all RED, evidence preserved):**
  `production_mpv_still_running`, `decode_not_confirmed`, `mpv_exited_before_signal`,
  `mpv_did_not_exit_after_sigterm`, probe-error artifact (analog of
  `fresh_ipc_probe_not_forced`).

## 3. Decode-confirmation contract (SINGLE — shared by producer and gate)

Poll 0.5s on the unique ipc_path (raw-socket helper precedent,
`c18_mpv_relaunch_teardown_probe.py:110-148`), deadline 30s, ≤3 loop-wrap retries.
CONFIRMED iff ALL of:
- ≥3 samples ≥0.5s apart with `estimated-frame-number` STRICTLY increasing;
- `time-pos` advance ≥0.2s across the window;
- `hwdec-current` == `v4l2request-copy` (EQUALITY with deep-health `EXPECTED_HWDEC`,
  `c18_playback_health_summary.py:15` — NEVER substring: `v4l2request` would also match
  the non-copy mode this project moved AWAY from);
- `vo-configured == true`; `idle-active`/`pause`/`eof-reached` all false;
- freshness: last sample ≤1s before the signal.
- mid-decode margin: the final sample must not be at EOF/loop boundary (`duration - time-pos`
  margin, or equivalent long-canary proof).
All samples persisted to `decode-samples.ndjson` (single format), each bound to
boot_id + monotonic, coherent with `window_anchor` and signal monotonic. The gate
RECOMPUTES the predicate from the samples and REDs on attestation/recompute mismatch
(`mid_decode_probe_decode_claim_text_mismatch`). Thresholds sit ~4x under the
HW-measured rate (+0.83s time-pos, +25 frames per ~1.2s @30fps, committed 1v samples).

## 4. Artifact & schema

- Root: `mid_decode_sigterm_probe.json`, schema
  `dadooh.c18.player_runtime.teardown_mid_decode_sigterm_probe.v1`; sidecar dir
  `mid-decode-sigterm-probe/` {per-attempt kernel-before/after, `decode-samples.ndjson`,
  probe kiosk.log tail (sanitized), `service-restore.json`, post-restore deep-health}.
  Sidecars auto-sealed/sanitized by existing seal machinery.
- Fields: `attempts[]` (each: `window_anchor{boot_id, monotonic_before/after}`,
  `decode_confirm{samples_n, frame_first/last, hwdec_current, last_sample_monotonic}`,
  `signal{name:"SIGTERM", target:"mpv_pgid", delivered, monotonic}`,
  `mpv_exit{exited, waited_ms, escalated}` (escalated must be false),
  `gpu_faults_before/after/delta`), `production_service{stopped, restored,
  deep_health_passed}`, `kiosk_killed_before_signal:true`, `wrapper{path, sha256}` +
  `cfg_hwdec` (audit chain: candidate_config leaves hwdec='auto'; active hwdec rests on
  the wrapper's last-wins trailing args — record it), `claim` (CLOSED enum:
  `mid_decode_sigterm_panfrost_window_measured`), `non_claims` MUST contain pinned
  strings: `GR4b`; healthy-not-wedged disclaimer (probe = HEALTHY decoding mpv; the
  production fallback typically fires on a wedged/`ipc_unresponsive` mpv whose
  kernel-side state may differ); no-kiosk-alive disclaimer (no IPC-quit prelude,
  watchdog/ensure_running, auto-relaunch, or kiosk-mediated waitpid in the probe window);
  `N=<n>` single-image; production-timing unmeasured.
- `summary` gains `mid_decode_probe_present:true` — **NEW RUNS ONLY; never backfill
  committed dirs** (manifest sha binding forbids it).
- Producer-attested vs recomputed fields labeled in-artifact (same trust classes as the
  kernel windows: the gate proves internal consistency; commits provide repo provenance and
  immutability, not proof that the journal was HW-captured).

## 5. Gate extension (STRICTLY ADD-ONLY)

- Hook: `validate_mid_decode_probe(...)` called from `validate_semantics` (next to
  `:550-551`). Presence logic (the add-only crux): `present = artifact.is_file()`;
  `attested = (summary.get('mid_decode_probe_present') is True)`; RED on XOR mismatch;
  silent return when both absent. **DO NOT clone the bidirectional `:418` pattern —
  measured: it REDs BOTH committed dirs** (their 9-key summaries lack the key).
- When present, fail-closed validators: window completeness (both kernel files,
  same-boot, finite positive width, strictly after last cycle window); delta==0
  RECOMPUTED from text mirroring `:356-380` (scalar/text binding, superset anchoring,
  absolute-zero both windows); decode confirmed AND recomputed from ndjson; SIGTERM
  attestation (`target` must be mpv_pgid, NEVER kiosk; `delivered=true`;
  `signal.monotonic` inside the kernel window); attempts must be strictly non-overlapping;
  mpv exited
  WITHOUT escalation; closed claim enum (anything else →
  `mid_decode_probe_unknown_claim`); pinned non-claim strings present; service restored
  + post-restore deep-health passed. JSON/NDJSON parsing must reject NaN/Infinity and all
  non-finite numeric values with the same fail-closed policy as the existing gate loader
  (including `decode-samples.ndjson`, not only JSON sidecars).
- Historical note: this was true for the original mid-decode landing. The follow-up
  production-stop hardening now changes the release gate: decisive mode requires at least one
  teardown dir with `production_stop_probe`, so production-stop is no longer optional.
- Historical regression locks (same commit): fixture lock asserting BOTH committed dirs
  (`20260610T052324Z-1x-teardown`, `20260610T185956Z-1x-teardown-fresh-ipc-probe`)
  validate `errors==[]` with byte-identical evidence-gate output; `write_fixture` gains
  `with_mid_decode=False` default (all existing fixtures byte-identical); baseline
  37/37 and decisive 46/46 re-run locally at that historical point.

## 6. Pin semantics (recorded HERE before landing; for external-auditor ratification)

- Historical "existing invocations stay byte-identical" — operational reading, ratified wording:
  **evidence-gate stdout byte-identical for the existing committed dirs + release-gate
  step NAMES/COUNTS/VERDICTS identical per invocation (37/37, 43/43, 46/46).** Self-test
  stdout tails ("Ran N tests") re-pin at the landing commit — unavoidable for ANY tested
  change, because the trial/gate/static self-tests are TEST_COMMANDS steps INSIDE the
  baseline 37 (verified by import).
- Current post-production-stop-hardening pins: baseline 37/37; decisive minimum with the
  production-stop teardown dir is 44/44; current full 1x bundle with all three teardown dirs
  is 50/50. Decisive invocations without production-stop now fail closed.

## 7. Landing plan (ONE commit) + verification + board session shape

- ONE commit: trial flag + gate extension + self-tests + runbook updates (probe
  invocation line, preflight block, manual-recovery line, surprise-RED protocol,
	  pre-written post-session decisive command with all three teardown dirs + the 1x
	  triple, new self-test counts replacing 39/39+15/15 at `runbook`, eyeball step
  EXTENDED to the probe windows) + ledger pointer update. A harness-only landing is
  FORBIDDEN: the trial self-validates with the real gate (`trial:787-794`), so probe
  artifacts would seal "green" without semantic validation.
- Historical off-board verification checklist (before that board time): both self-tests green;
  NEW gate vs both committed dirs → `errors==[]` byte-identical; baseline 37/37;
  decisive 46/46 with the 1x triple at that point. Current post-production-stop hardening
  counts are recorded in §6 above.
- Board session (ONLY after the operator's pre-session ratifications, §8): ONE new
  trial run = 3 cycles + mid-decode probe; **OMIT `--with-fresh-ipc-probe`** (corner
  already evidenced in the committed 185956Z dir; a re-run adds time + failure surface,
  zero knowledge). In-session feedback: the trial validates its own dir with the REAL
  gate on-board — a probe RED is visible immediately and a same-session re-run is
  possible.
- Surprise-RED protocol (pre-agreed, mirror of `plan.md:109-114`): a NONZERO mid-decode
  panfrost delta is a MEASURED fact — dir stays on-board as diagnostic (NOT committed
  green), session continues, NEVER grounds to relax delta==0/absolute-zero; it reopens
  ledger option (b) as the data-informed path.

## 8. Policy memos (DRAFT — change nothing until the operator ratifies)

- **fresh_sent/GR4b — recommend Option I:** keep the gate fail-closed indefinitely; a
  surprise `fresh_sent` = red dir kept on-board as diagnostic, session continues;
  revisit ledger option (b) only on a dirty (a)-result. Options II (pre-authorized gate
  evolution) and III (deliberate success probe) rejected: II specifies acceptance for an
  event observed zero times and opens the widest claim-inflation channel; III is a
  biased retry-until-race protocol against an embryonic (non-decoding) mpv — irrelevant
  to the dangerous class — and drags II in anyway. **Ratification is MANDATORY before
  the next board session** (`plan.md:109-114`).
- **D2/H2 golden split — Option B formalized:** keep `1u` golden for
  recovery/delivery and treat `1x` as the current decisive player-runtime evidence bundle
  only. The ledger row is no longer LATENT, stale `1w` current-decisive wording is
  rejected by `c18_ota_policy_static_test`, and the full `1x` triple is pinned in the
  contract. LOUD: no unconditional release-gate step was added, so baseline 37/37 stays
  stable. Carry-over remains: 1x image FILE + SHA256SUMS-class provenance is required
  before `1x` carries any golden/H2 baseline claim.
- **Operator decision message (remaining board items):** (a) probe design — the
  hybrid in §2 is PINNED by the guardian with the 1v 3/5-launch-fault datum; veto window
  open; (b) fresh_sent Option I ratification (pre-session MANDATORY); (c) N attempts pin
  (recommended 2). D2 Option B is already formalized.

## 9. Cut from this round (productivity, zero robustness loss)

Dual-design variant flag; second same-boot relaunch launch (trial cycles already
evidence relaunch-after-teardown); powerloss image-binding (deferred carry-over);
fresh-IPC probe re-run on the next session; `get_property('pid')` critical-path
dependency. Open-question inflation resolved: converged items (gate form, escalation⇒RED,
`summary.passed` stays cycles-only, naming/schema) are CLOSED here, not re-surfaced.

Carry-overs unchanged: D1 matcher deny-by-default + clean-board corpus; raw journal
slice preservation; candidate-health catch-all except (boundary — explicit authorization
required); server-side hardening (LATER).

## 10. 2026-06-11 addendum: production-faithful follow-up

The first hardware execution of the hybrid probe produced real panfrost faults
and was archived as
`docs/evidence/c18-update-validation/20260611T035143Z-1x-mid-decode-sigterm-failed/`.
The run is diagnostic, not decisive: the first kernel fault appeared after the
isolated kiosk was SIGKILLed and before the explicit SIGTERM was delivered to
the orphaned mpv process. It proves a real GPU fault in an orphaned mid-decode
lab window, but it must not be read as proof that the production kiosk stop path
causes the same fault.

The follow-up contract is now `--with-production-stop-probe`:

- keep the kiosk/controller alive;
- confirm mpv is actively decoding with `v4l2request-copy`;
- open the panfrost window;
- deliver SIGTERM directly to the Python kiosk process, matching the signal that
  the production launcher ultimately forwards to its child;
- let `kiosk.py` run `_stop_locked()`, recording whether it used IPC quit or
  reached the mpv SIGTERM fallback;
- treat mpv SIGTERM fallback as a subclaim only when explicitly logged.

This does not replace the historical hybrid probe; it narrows the next claim to
the direct Python kiosk healthy stop path. The full launcher/systemd cgroup
cleanup path remains a non-claim unless a later probe exercises it explicitly.
