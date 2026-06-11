# C18 player-runtime — decisive board session run-book (H1)

Status: OPERATOR RUN-BOOK (board-session mechanics only). Produces the fresh decisive
evidence that the release gate requires to consider player-runtime lab→homologation.
No thaw is performed by this run-book; freeze stays `rc=44`.

**Track A status (2026-06-11):** completed and committed. The current H1 lab-scope
evidence uses the existing 1x M6 bundle plus three teardown dirs: main teardown,
fresh-IPC reachability, and the healthy Python-kiosk production-stop probe. This
run-book is historical mechanics for recapture; the live state is in
`docs/c18-player-runtime-thaw-continuation-plan.md`.

This run-book makes the scarce board session **decisive on first capture**. Do NOT skip the
pre-flight: a wrong image-identity triple or an uncommitted evidence file silently red-fails
the decisive gate and forces a second board trip.

## Operator ratification gate
Historical for Track A: ratification happened before the board session. For any recapture,
use the same rule: keep success-surprise/fresh-IPC fail-closed, pin the image identity
triple first, and do not mix evidence from different images.

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
1. **Choose exactly one image path.**
   - Immediate Track A path: keep the already-running `1x` board image, copy the committed
     `scripts/qa` + `scripts/board` trees from the landing commit to `/data/totem-diag/scripts`,
     and set
     `SOURCE_COMMIT` to that landing commit. Use the real `1x` identity triple:
     `IMAGE_TAG`, `IMAGE_SHA256`, `MARKER_SHA256`.
   - Full recapture path: bake a new image from the current `foundation-v0.1` HEAD, boot it,
     record its new identity triple, and recapture M6. Do **not** combine a new-image teardown
     with the committed `1x` M6 dirs below; the evidence gates are image-pinned and will
     correctly reject that mix.
2. **For full M6 recapture only**, build the two DISTINCT A/B player-runtime packages that M6 `arm` consumes
   (`--manifest-a/-b` + `--payload-a/-b`, versions MUST differ) via
   `scripts/deploy/build_player_runtime_release_package.sh` (lab-only; runs the player-runtime
   release gate; does not publish or thaw). Skip this for the immediate Track A session that
   reuses the committed `1x` M6 evidence.
3. **Dry-run the gate wiring** off-board with synthetic fixtures to confirm GREEN end-to-end
   before spending board time: build a teardown run-dir via the harness self-test path and run
   `c18_player_runtime_teardown_evidence_gate.py --self-test` and the harness
   `--self-test`.

## Evidence root — CRITICAL (board A/B diagnosis 2026-06-10)
Use a single persistent evidence root the **`totem` user can traverse**:
`RUN_ID=<image-tag>-mid-decode-<timestamp>` and `EVID=/data/totem-diag/$RUN_ID`
(run `install -d -m 0755 /data/totem-diag` first).
- **Never use `/root/totem-diag` for M6/candidate-health.** `/root` is `0700`: the candidate-health
  runner drops to `totem` (setuid), so a work-dir under `/root` is unreachable — the candidate dies
  before it can even open its log, which previously surfaced as a generic all-checks-failed health
  failure. The runner now PRE-FLIGHTS run_user accessibility and fails fast with
  `candidate_setup_inaccessible_to_run_user` (and captures the candidate's stdout/stderr as evidence
  instead of DEVNULL) — but the real fix is to place the evidence root where `totem` can reach it.
  `/data` is `0755` and persists the reboot (M6 `arm`→`resume` both need it).
- `/root` stays acceptable ONLY for root-only diagnostics never executed as `totem`.

## On the board (historical Track A session; mind panfrost baseline cross-contamination)
Order matters for recapture: run the **teardown trial only** unless a full image/M6
recapture is explicitly authorized.

### Step 1 — Teardown trial + production-stop probe
Use a local H.264 canary long enough to leave at least 2s before EOF at signal time;
the safe default is 30s or longer. Regenerate `/tmp` canaries after every reboot.

```sh
SOURCE_COMMIT=<landing-commit-containing-the-production-stop-probe>
C18_PLAYER_RUNTIME_TEARDOWN_TRIAL=1 python3 /data/totem-diag/scripts/board/c18_player_runtime_teardown_trial.py \
  --cycles 3 --with-production-stop-probe \
  --production-stop-probe-attempts 1 \
  --production-stop-probe-canary-media /data/media/c18-canary-h264.mp4 \
  --board-image-marker "$IMAGE_TAG" --source-commit "$SOURCE_COMMIT" \
  --run-root "$EVID"
```
Produces a teardown run-dir (cycle-00 = `service_restart`, rest `relaunch`), per-cycle
kernel-before/after + deep-health + the freeze postcheck (`rc=44`) plus
`production_stop_probe.json`.

**Production-stop probe:** starts an isolated healthy kiosk instance of the adopted runtime,
confirms MPV is actively decoding (`hwdec-current == v4l2request-copy`), delivers SIGTERM to
the Python kiosk process, and lets `kiosk.py` stop MPV. The committed green run observed IPC
quit, no MPV SIGTERM/SIGKILL fallback, `panfrost_delta=0`, MPV gone after kiosk exit, and
post-restore deep-health green. It does NOT claim GR4b fresh-IPC success, fallback SIGTERM to
MPV, wedged/ipc_unresponsive cleanup, full launcher/systemd cgroup cleanup, soak, or thaw.

**Do not pass `--with-fresh-ipc-probe` in this session.** The fresh-IPC reachability corner is
already evidenced by `20260610T185956Z-1x-teardown-fresh-ipc-probe`; re-running it adds board
time and failure surface without answering the remaining Track A question.

**`--board-image-marker "$IMAGE_TAG"` is REQUIRED** and must be the exact image tag (or the
`<tag>-image` form). The decisive gate's `teardown_evidence_image_guard` binds the teardown
evidence to the same image as the coldboot/data evidence and **fails closed** if it diverges,
shares only a prefix (`...-1u` vs `...-1u9`), or is omitted (the harness default marker has no
version suffix and is rejected on purpose).

### Step 2 — Clean-board GPU-fault corpus + EYEBALL (matcher recall is the weak link)
Keep this corpus **outside** the sealed `$EVID` run-dir. Files added under `$EVID` after the
trial manifest is sealed make the evidence gate RED, as intended.

```sh
CORPUS=/data/totem-diag/${RUN_ID}-clean-board-kernel.txt
journalctl -k -b --no-pager --output=short-monotonic > "$CORPUS"
grep -iE 'panfrost|lima|mali' "$CORPUS"   # inspect by hand
```
Confirm a genuinely clean teardown produced ZERO real GPU-fault lines, AND that no
`panfrost|lima|mali` fault wording slipped past `GPU_FAULT_RE` (if one did, widen the matcher /
switch to deny-by-default before trusting GREEN — this is the D1 calibration).

### Step 3 — M6 coldboot trial, DEFERRED gate (only for full bundle recapture)
Skip this step for the immediate Track A session. Use it only if the operator explicitly
decides to recapture the full 1x M6 bundle; otherwise reuse the committed 1x M6 evidence.

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
4. Copy the new Track A teardown dir into the repo tree under
   `docs/evidence/c18-update-validation/`, sanitize-check, and **COMMIT them** (not just
   `git add`). The git-guard requires every evidence file git-TRACKED, AND `repo_clean_guard`
   reds on staged-but-uncommitted files — so a `git add` alone leaves the tree "dirty" and the
   gate cannot go green. Only a COMMIT satisfies both; committed/reproducible evidence IS the
   anti-fabrication backstop (the gate cannot prove the journal was HW-captured). Committing
   first does NOT bless the evidence — the gate below is what validates it.
5. Run ONE combined decisive gate from the now-clean tree, using the existing 1x M6 dirs and
   all three teardown dirs (main teardown, fresh-IPC reachability, production-stop).
   This command is **only** for the immediate Track A path (`IMAGE_*` = `1x`). If a new image
   was baked, do not use this command shape with any `1x` evidence dir; recapture and substitute
   every image-pinned evidence dir that participates in the decisive bundle.
```sh
python3 scripts/qa/c18_ota_release_gate.py --player-runtime-evidence-mode decisive \
  --player-runtime-data-coldboot-evidence-dir docs/evidence/c18-update-validation/20260610T072826Z-1x-m6-coldboot \
  --player-runtime-data-evidence-dir          docs/evidence/c18-update-validation/20260610T072826Z-1x-m6-data \
  --player-runtime-teardown-evidence-dir      docs/evidence/c18-update-validation/20260610T052324Z-1x-teardown \
  --player-runtime-teardown-evidence-dir      docs/evidence/c18-update-validation/20260610T185956Z-1x-teardown-fresh-ipc-probe \
  --player-runtime-teardown-evidence-dir      docs/evidence/c18-update-validation/20260611T050939Z-1x-production-stop \
  --expect-image-tag "$IMAGE_TAG" --expect-image-sha256 "$IMAGE_SHA256" \
  --expect-image-marker-sha256 "$MARKER_SHA256" --json
```
6. A **GREEN** gate is the decisive proof — treat the run as decisive ONLY on green. A **RED**
   gate is the gate doing its job: the committed evidence failed validation (image-triple
   mismatch, a real panfrost fault, a non-`service_restart` cycle, an untracked/zero-size sidecar,
   etc.). Do NOT relax the gate — read the `errors`, fix the cause, re-capture if needed, amend or
   replace the evidence commit, and re-run.

Manual recovery if the Track A trial restores RED on the board: preserve `$EVID` first, then
start the service explicitly with `systemctl start kiosky-player.service`, verify it is active,
and run deep-health before any retry. Do not edit `current`/`previous` manually.

## What this session does and does NOT establish
- DOES: a fresh Track A teardown artifact proving the healthy Python-kiosk stop path is
  panfrost-clean for an actively decoding MPV, and a combined image-pinned decisive bundle
  reusing the existing 1x M6 evidence plus all teardown dirs. Supersedes the stale `1w`
  decisive authorization (which predates the teardown requirement).
- DOES NOT: physical power-cut durability, 24h soak, or any thaw. Those are later gates. Thaw
  remains a separate, explicitly-authorized step (`:123`/`:967`), not part of this run.
