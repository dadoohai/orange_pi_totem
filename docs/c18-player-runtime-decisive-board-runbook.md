# C18 player-runtime — decisive board session run-book (H1)

Status: OPERATOR RUN-BOOK (board-session mechanics only). Produces the fresh decisive
evidence that the release gate requires to consider player-runtime lab→homologation.
No thaw is performed by this run-book; freeze stays `rc=44`.

This run-book makes the scarce board session **decisive on first capture**. Do NOT skip the
pre-flight: a wrong image-identity triple or an uncommitted evidence file silently red-fails
the decisive gate and forces a second board trip.

## What the decisive gate demands (so the session is sufficient)
`c18_ota_release_gate.py --player-runtime-evidence-mode decisive` requires, from a CLEAN repo
tree, ALL of:
- `--player-runtime-data-coldboot-evidence-dir` (from M6, `selected_source=data`, real reboot);
- `--player-runtime-data-evidence-dir` (from M6, image-pinned);
- `--player-runtime-teardown-evidence-dir` (from the teardown trial — ≥2 same-boot cycles,
  ≥1 real `systemctl restart`, absolute-zero panfrost per window, freeze `rc=44` postcheck);
- the image-identity triple `--expect-image-tag/-sha256/-marker-sha256` matching the image
  ACTUALLY on the board; and every evidence file **git-tracked** (the git-guard rejects
  untracked/ignored).

## Pre-flight (off-board — do before touching the board)
1. **Bake the image** from the current `foundation-v0.1` HEAD (includes the teardown harness
   and the `mpv_path` boot guard). Record its identity triple:
   - `IMAGE_TAG` (e.g. `c18-hwdecode-lab-1x`), `IMAGE_SHA256`, `MARKER_SHA256` (`/etc/dadooh`
     image marker). **This is the D2 decision** — these three values are the contract between
     the board image and every gate invocation below. (The repo golden is `1u`; if the board
     runs a different image, pass its real triple here — do NOT rely on the `1u` defaults.)
2. **Build the two DISTINCT A/B player-runtime packages** that M6 `arm` consumes
   (`--manifest-a/-b` + `--payload-a/-b`, versions MUST differ) via
   `scripts/deploy/build_player_runtime_release_package.sh` (lab-only; runs the player-runtime
   release gate; does not publish or thaw). Pick a local canary video for `--canary-media`.
3. **Dry-run the gate wiring** off-board with synthetic fixtures to confirm GREEN end-to-end
   before spending board time: build a teardown run-dir via the harness self-test path and run
   `c18_player_runtime_teardown_evidence_gate.py --self-test` (31/31) and the harness
   `--self-test` (9/9).

## Evidence root — CRITICAL (board A/B diagnosis 2026-06-10)
Use a single persistent evidence root the **`totem` user can traverse**:
`EVID=/data/totem-diag/<run-id>` (run `install -d -m 0755 /data/totem-diag` first; pick a `<run-id>`
like the image tag + timestamp).
- **Never use `/root/totem-diag` for M6/candidate-health.** `/root` is `0700`: the candidate-health
  runner drops to `totem` (setuid), so a work-dir under `/root` is unreachable — the candidate dies
  before it can even open its log, which previously surfaced as a generic all-checks-failed health
  failure. The runner now PRE-FLIGHTS run_user accessibility and fails fast with
  `candidate_setup_inaccessible_to_run_user` (and captures the candidate's stdout/stderr as evidence
  instead of DEVNULL) — but the real fix is to place the evidence root where `totem` can reach it.
  `/data` is `0755` and persists the reboot (M6 `arm`→`resume` both need it).
- `/root` stays acceptable ONLY for root-only diagnostics never executed as `totem`.

## On the board (single session; mind panfrost baseline cross-contamination)
Order matters: run the **teardown trial first (no reboot)**, then M6 (which reboots).

### Step 1 — Teardown trial (≥2 same-boot cycles, ≥1 real service restart)
```sh
C18_PLAYER_RUNTIME_TEARDOWN_TRIAL=1 python3 scripts/board/c18_player_runtime_teardown_trial.py \
  --cycles 3 --with-fresh-ipc-probe \
  --board-image-marker "$IMAGE_TAG" --source-commit "$(git -C <repo> rev-parse HEAD)" \
  --run-root "$EVID"
```
Produces a teardown run-dir (cycle-00 = `service_restart`, rest `relaunch`), per-cycle
kernel-before/after + deep-health + the freeze postcheck (`rc=44`).

**`--board-image-marker "$IMAGE_TAG"` is REQUIRED** and must be the exact image tag (or the
`<tag>-image` form). The decisive gate's `teardown_evidence_image_guard` binds the teardown
evidence to the same image as the coldboot/data evidence and **fails closed** if it diverges,
shares only a prefix (`...-1u` vs `...-1u9`), or is omitted (the harness default marker has no
version suffix and is rejected on purpose).

### Step 2 — Clean-board GPU-fault corpus + EYEBALL (matcher recall is the weak link)
```sh
journalctl -k -b --no-pager --output=short-monotonic > "$EVID/clean-board-kernel.txt"
grep -iE 'panfrost|lima|mali' "$EVID/clean-board-kernel.txt"   # inspect by hand
```
Confirm a genuinely clean teardown produced ZERO real GPU-fault lines, AND that no
`panfrost|lima|mali` fault wording slipped past `GPU_FAULT_RE` (if one did, widen the matcher /
switch to deny-by-default before trusting GREEN — this is the D1 calibration).

### Step 3 — M6 coldboot trial, DEFERRED gate (one operator reboot)
`--defer-release-gate` is MANDATORY in both phases: without it M6 runs its own gate WITHOUT the
teardown dir and red-fails with `c18_player_runtime_teardown_evidence_required`. The always-required
args are `--phase`, `--evidence-root`, `--image-tag`, `--image-sha256`, `--image-marker-file`; `arm`
additionally requires the two DISTINCT A/B packages and a canary video (built in pre-flight).

Arm (captures pre-state, writes the deferred marker, applies A→B in `/data`):
```sh
C18_PLAYER_RUNTIME_M6_COLDBOOT_TRIAL=1 python3 scripts/qa/c18_player_runtime_m6_coldboot_trial.py \
  --phase arm --defer-release-gate --allow-device-data-root --data-root /data \
  --evidence-root "$EVID/m6" \
  --image-tag "$IMAGE_TAG" --image-sha256 "$IMAGE_SHA256" --image-marker-file /etc/dadooh/<image-marker> \
  --manifest-a <A.manifest.json> --payload-a <A.tar.gz> \
  --manifest-b <B.manifest.json> --payload-b <B.tar.gz> \
  --canary-media <local-video-under-/tmp-or-/data> --json
```
`--- operator performs the real power-cycle / reboot when instructed ---`

Resume (validates boot_id/btime changed + `/data` adoption; writes the coldboot + data evidence dirs):
```sh
C18_PLAYER_RUNTIME_M6_COLDBOOT_TRIAL=1 python3 scripts/qa/c18_player_runtime_m6_coldboot_trial.py \
  --phase resume --defer-release-gate --allow-device-data-root --data-root /data \
  --evidence-root "$EVID/m6" \
  --image-tag "$IMAGE_TAG" --image-sha256 "$IMAGE_SHA256" --image-marker-file /etc/dadooh/<image-marker> --json
```

## Off-board — assemble and run the single decisive gate
4. Copy the three evidence dirs (teardown, M6 coldboot, M6 data) into the repo tree under
   `docs/evidence/c18-update-validation/`, sanitize-check, and **COMMIT them** (not just
   `git add`). The git-guard requires every evidence file git-TRACKED, AND `repo_clean_guard`
   reds on staged-but-uncommitted files — so a `git add` alone leaves the tree "dirty" and the
   gate cannot go green. Only a COMMIT satisfies both; committed/reproducible evidence IS the
   anti-fabrication backstop (the gate cannot prove the journal was HW-captured). Committing
   first does NOT bless the evidence — the gate below is what validates it.
5. Run ONE combined decisive gate from the now-clean tree:
```sh
python3 scripts/qa/c18_ota_release_gate.py --player-runtime-evidence-mode decisive \
  --player-runtime-data-coldboot-evidence-dir docs/evidence/c18-update-validation/<m6-coldboot> \
  --player-runtime-data-evidence-dir          docs/evidence/c18-update-validation/<m6-data> \
  --player-runtime-teardown-evidence-dir      docs/evidence/c18-update-validation/<teardown> \
  --expect-image-tag "$IMAGE_TAG" --expect-image-sha256 "$IMAGE_SHA256" \
  --expect-image-marker-sha256 "$MARKER_SHA256" --json
```
6. A **GREEN** gate is the decisive proof — treat the run as decisive ONLY on green. A **RED**
   gate is the gate doing its job: the committed evidence failed validation (image-triple
   mismatch, a real panfrost fault, a non-`service_restart` cycle, an untracked/zero-size sidecar,
   etc.). Do NOT relax the gate — read the `errors`, fix the cause, re-capture if needed, amend or
   replace the evidence commit, and re-run.

## What this session does and does NOT establish
- DOES: a fresh, image-pinned decisive bundle proving repeated teardown/relaunch + a real service
  restart are panfrost-clean and `/data` cold-boot adoption works on hardware. Supersedes the
  stale `1w` decisive authorization (which predates the teardown requirement).
- DOES NOT: physical power-cut durability, 24h soak, or any thaw. Those are later gates. Thaw
  remains a separate, explicitly-authorized step (`:123`/`:967`), not part of this run.
