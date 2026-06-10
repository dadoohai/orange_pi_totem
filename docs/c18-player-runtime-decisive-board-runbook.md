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
3. **Dry-run the gate wiring** off-board with synthetic fixtures to confirm GREEN end-to-end
   before spending board time: build a teardown run-dir via the harness self-test path and run
   `c18_player_runtime_teardown_evidence_gate.py --self-test` (31/31) and the harness
   `--self-test` (9/9).

## On the board (single session; mind panfrost baseline cross-contamination)
Order matters: run the **teardown trial first (no reboot)**, then M6 (which reboots).

### Step 1 — Teardown trial (≥2 same-boot cycles, ≥1 real service restart)
```sh
C18_PLAYER_RUNTIME_TEARDOWN_TRIAL=1 python3 scripts/board/c18_player_runtime_teardown_trial.py \
  --cycles 3 --with-fresh-ipc-probe \
  --board-image-marker "$IMAGE_TAG" --source-commit "$(git -C <repo> rev-parse HEAD)" \
  --run-root /root/totem-diag
```
Produces a teardown run-dir (cycle-00 = `service_restart`, rest `relaunch`), per-cycle
kernel-before/after + deep-health + the freeze postcheck (`rc=44`).

### Step 2 — Clean-board GPU-fault corpus + EYEBALL (matcher recall is the weak link)
```sh
journalctl -k -b --no-pager --output=short-monotonic > /root/totem-diag/clean-board-kernel.txt
grep -iE 'panfrost|lima|mali' /root/totem-diag/clean-board-kernel.txt   # inspect by hand
```
Confirm a genuinely clean teardown produced ZERO real GPU-fault lines, AND that no
`panfrost|lima|mali` fault wording slipped past `GPU_FAULT_RE` (if one did, widen the matcher /
switch to deny-by-default before trusting GREEN — this is the D1 calibration).

### Step 3 — M6 coldboot trial, DEFERRED gate (one operator reboot)
```sh
C18_PLAYER_RUNTIME_M6_COLDBOOT_TRIAL=1 python3 scripts/qa/c18_player_runtime_m6_coldboot_trial.py \
  --defer-release-gate  <...arm args...>      # arm phase: captures pre-state, writes deferred marker
# --- operator performs the real power-cycle / reboot when instructed ---
#   resume phase validates boot_id/btime changed + /data adoption, writes coldboot + data evidence
```
`--defer-release-gate` is MANDATORY: without it M6 runs its own gate WITHOUT the teardown dir and
red-fails with `c18_player_runtime_teardown_evidence_required`.

## Off-board — assemble and run the single decisive gate
4. Copy the three evidence dirs (teardown, M6 coldboot, M6 data) into the repo tree under
   `docs/evidence/c18-update-validation/`, then **`git add`** them (the git-guard rejects any
   untracked / `.gitignore`d file and requires every manifest entry tracked). Keep the tree
   otherwise clean.
5. Run ONE combined decisive gate from the CLEAN tree:
```sh
python3 scripts/qa/c18_ota_release_gate.py --player-runtime-evidence-mode decisive \
  --player-runtime-data-coldboot-evidence-dir docs/evidence/c18-update-validation/<m6-coldboot> \
  --player-runtime-data-evidence-dir          docs/evidence/c18-update-validation/<m6-data> \
  --player-runtime-teardown-evidence-dir      docs/evidence/c18-update-validation/<teardown> \
  --expect-image-tag "$IMAGE_TAG" --expect-image-sha256 "$IMAGE_SHA256" \
  --expect-image-marker-sha256 "$MARKER_SHA256" --json
```
6. Only if **GREEN**, commit the evidence. A failure here is the gate doing its job — read the
   `errors`, fix the cause (image-triple mismatch, an untracked file, a real panfrost fault, a
   non-`service_restart` cycle, etc.), re-run; do NOT relax the gate.

## What this session does and does NOT establish
- DOES: a fresh, image-pinned decisive bundle proving repeated teardown/relaunch + a real service
  restart are panfrost-clean and `/data` cold-boot adoption works on hardware. Supersedes the
  stale `1w` decisive authorization (which predates the teardown requirement).
- DOES NOT: physical power-cut durability, 24h soak, or any thaw. Those are later gates. Thaw
  remains a separate, explicitly-authorized step (`:123`/`:967`), not part of this run.
