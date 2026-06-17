# C18 H2 Power-Loss Checkpoint Runbook

Run one checkpoint at a time. A checkpoint is not evidence until physical
power has been removed after `CUT_POWER_NOW`, the board has booted again,
the resume command has passed, and the evidence gate has accepted the
pulled directory.

Do not use remote reboot as a substitute for power loss.

## Preflight Before Physical Session

Collect this preflight from board stdout into a local file, then run the
offline gate against the matrix plan. Do not start physical cuts if the
gate is red.

The collector execution is read-only: it inspects board/package/image
state and prints JSON to stdout. The `scp`/`rm` lines below only stage and
remove a temporary collector copy under `/tmp`; they are not power-loss
evidence, do not create checkpoint evidence, and may be skipped when the
collector is already present in the bundle.

```sh
scp scripts/board/c18_player_runtime_h2_powerloss_preflight_collect.py root@192.168.18.131:/tmp/c18_player_runtime_h2_powerloss_preflight_collect.py
ssh root@192.168.18.131 \
  "cd '/data/c18-powerloss-bundle-3eb06f1' && \
   PYTHONDONTWRITEBYTECODE=1 \
   PYTHONPATH='/data/c18-powerloss-bundle-3eb06f1/scripts/board' \
   python3 -B /tmp/c18_player_runtime_h2_powerloss_preflight_collect.py \
     --bundle-dir '/data/c18-powerloss-bundle-3eb06f1' \
     --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1' \
     --canary-media '/data/media/c18-canary-h264.mp4' \
     --image-marker '/etc/dadooh/image-build.json' \
     --json" \
  > 'docs/evidence/c18-update-validation/20260617T193921Z-h2-powerloss-board-preflight-mpv-stuck-fix-9bebaf1/board-preflight.json'
ssh root@192.168.18.131 \
  "rm -f /tmp/c18_player_runtime_h2_powerloss_preflight_collect.py"
python3 scripts/qa/c18_player_runtime_h2_powerloss_preflight_gate.py \
  --preflight 'docs/evidence/c18-update-validation/20260617T193921Z-h2-powerloss-board-preflight-mpv-stuck-fix-9bebaf1/board-preflight.json' \
  --matrix-plan 'docs/evidence/c18-update-validation/20260617T193720Z-h2-powerloss-matrix-plan-mpv-stuck-fix-9bebaf1/powerloss-matrix-plan.json' \
  --expect-image-tag 'c18-hwdecode-lab-1x' \
  --expect-image-marker-sha256 '59739f57cdb3f79ac4c8ce5e5e1f9c4aa6d9dae58f704010f8423e66abe2bb9e' \
  --max-age-sec 1800 \
  --json
```

## 1. after_payload_staged

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none required by the plan.

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_payload_staged' \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_payload_staged/trial' \
  --startup-wait-sec 12 \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_payload_staged/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `1/17`.

## 2. after_release_dir_created

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none required by the plan.

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_release_dir_created' \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_release_dir_created/trial' \
  --startup-wait-sec 12 \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_release_dir_created/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `2/17`.

## 3. after_extract

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none required by the plan.

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_extract' \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_extract/trial' \
  --startup-wait-sec 12 \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_extract/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `3/17`.

## 4. after_state_verifying

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none required by the plan.

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_state_verifying' \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_state_verifying/trial' \
  --startup-wait-sec 12 \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_state_verifying/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `4/17`.

## 5. after_health_passed

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none required by the plan.

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_health_passed' \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_health_passed/trial' \
  --startup-wait-sec 12 \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_health_passed/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `5/17`.

## 6. after_release_tree_fsync

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none required by the plan.

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_release_tree_fsync' \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_release_tree_fsync/trial' \
  --startup-wait-sec 12 \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_release_tree_fsync/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `6/17`.

## 7. after_marker_written

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none required by the plan.

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_marker_written' \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_marker_written/trial' \
  --startup-wait-sec 12 \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_marker_written/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `7/17`.

## 8. after_previous_symlink

- Phase: `apply`
- Setup precondition: `old-current-present-and-different-from-target`
- Requires custom setup: `true`
- Expected resume version: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints
- after_previous_symlink is reachable only when an old current exists and differs from the target

Manual setup before arm:
- Use only a lab image or a board state that has been backed up for destructive H2 trials.
- Before arming, verify that the data current runtime exists and is the expected previous version, not the target package.
- Do not run this checkpoint immediately after a successful target apply; restore an old current first or use a freshly imaged/prepared board.
- Record the pre-arm current/previous topology in the checkpoint evidence notes before physical cut.

Do not run the arm command until the custom setup has been completed and recorded.

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_previous_symlink' \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_previous_symlink/trial' \
  --startup-wait-sec 12 \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_previous_symlink/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `8/17`.

## 9. after_current_symlink

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none required by the plan.

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_current_symlink' \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_current_symlink/trial' \
  --startup-wait-sec 12 \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_current_symlink/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `9/17`.

## 10. after_state_success

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none required by the plan.

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_state_success' \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_state_success/trial' \
  --startup-wait-sec 12 \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/after_state_success/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `10/17`.

## 11. before_stage_cleanup

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none required by the plan.

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'before_stage_cleanup' \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/before_stage_cleanup/trial' \
  --startup-wait-sec 12 \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/before_stage_cleanup/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `11/17`.

## 12. rollback_after_identify_links

- Phase: `rollback`
- Setup precondition: `target-current-over-expected-previous`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- requires target as current and previous as the expected old active runtime before arm
- requires --quarantine-current so the checkpoint records quarantined_current=true
- standard fresh lab apply setup is used so target-over-previous topology is explicit
- resume is expected to see fallback before reconcile and data previous after reconcile

Setup before arm:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
mkdir -p '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_identify_links/setup'
C18_PLAYER_RUNTIME_LAB_APPLY=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_lab_apply.py \
  --lab-only-apply \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --data-root /data \
  --allow-device-data-root \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --output-dir '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_identify_links/setup/apply' \
  --startup-wait-sec 12 \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_identify_links/setup/lab-apply.json'
python3 scripts/qa/c18_player_runtime_adoption_probe.py \
  --data-root /data \
  --expected-source data \
  --expected-version 'c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1' \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_identify_links/setup/service-adoption.json'
python3 scripts/board/c18_playback_health_collect.py \
  --duration-sec 60 \
  --interval-sec 1 \
  --output-dir '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_identify_links/setup/service-health' \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_identify_links/setup/service-health.json'
```

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-rollback \
  --checkpoint 'rollback_after_identify_links' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_identify_links/trial' \
  --quarantine-current \
  --expect-rolled-to 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_identify_links/trial' \
  --expected-source fallback \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `12/17`.

## 13. rollback_after_current_to_previous

- Phase: `rollback`
- Setup precondition: `target-current-over-expected-previous`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence

Setup before arm:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
mkdir -p '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_current_to_previous/setup'
C18_PLAYER_RUNTIME_LAB_APPLY=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_lab_apply.py \
  --lab-only-apply \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --data-root /data \
  --allow-device-data-root \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --output-dir '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_current_to_previous/setup/apply' \
  --startup-wait-sec 12 \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_current_to_previous/setup/lab-apply.json'
python3 scripts/qa/c18_player_runtime_adoption_probe.py \
  --data-root /data \
  --expected-source data \
  --expected-version 'c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1' \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_current_to_previous/setup/service-adoption.json'
python3 scripts/board/c18_playback_health_collect.py \
  --duration-sec 60 \
  --interval-sec 1 \
  --output-dir '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_current_to_previous/setup/service-health' \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_current_to_previous/setup/service-health.json'
```

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-rollback \
  --checkpoint 'rollback_after_current_to_previous' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_current_to_previous/trial' \
  --quarantine-current \
  --expect-rolled-to 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_current_to_previous/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `13/17`.

## 14. rollback_after_previous_removed

- Phase: `rollback`
- Setup precondition: `target-current-over-expected-previous`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- postcheck.txt is required by the evidence gate

Setup before arm:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
mkdir -p '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_previous_removed/setup'
C18_PLAYER_RUNTIME_LAB_APPLY=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_lab_apply.py \
  --lab-only-apply \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --data-root /data \
  --allow-device-data-root \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --output-dir '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_previous_removed/setup/apply' \
  --startup-wait-sec 12 \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_previous_removed/setup/lab-apply.json'
python3 scripts/qa/c18_player_runtime_adoption_probe.py \
  --data-root /data \
  --expected-source data \
  --expected-version 'c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1' \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_previous_removed/setup/service-adoption.json'
python3 scripts/board/c18_playback_health_collect.py \
  --duration-sec 60 \
  --interval-sec 1 \
  --output-dir '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_previous_removed/setup/service-health' \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_previous_removed/setup/service-health.json'
```

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-rollback \
  --checkpoint 'rollback_after_previous_removed' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_previous_removed/trial' \
  --quarantine-current \
  --expect-rolled-to 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_previous_removed/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `14/17`.

## 15. rollback_after_quarantine

- Phase: `rollback`
- Setup precondition: `target-current-over-expected-previous`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- postcheck.txt is required by the evidence gate
- trial/resume/post-reconcile-state.json is required by the evidence gate

Setup before arm:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
mkdir -p '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_quarantine/setup'
C18_PLAYER_RUNTIME_LAB_APPLY=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_lab_apply.py \
  --lab-only-apply \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --data-root /data \
  --allow-device-data-root \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --output-dir '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_quarantine/setup/apply' \
  --startup-wait-sec 12 \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_quarantine/setup/lab-apply.json'
python3 scripts/qa/c18_player_runtime_adoption_probe.py \
  --data-root /data \
  --expected-source data \
  --expected-version 'c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1' \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_quarantine/setup/service-adoption.json'
python3 scripts/board/c18_playback_health_collect.py \
  --duration-sec 60 \
  --interval-sec 1 \
  --output-dir '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_quarantine/setup/service-health' \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_quarantine/setup/service-health.json'
```

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-rollback \
  --checkpoint 'rollback_after_quarantine' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_quarantine/trial' \
  --quarantine-current \
  --expect-rolled-to 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_quarantine/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `15/17`.

## 16. rollback_after_current_unlinked

- Phase: `rollback`
- Setup precondition: `target-current-without-previous-link-or-state`
- Requires custom setup: `true`
- Expected resume version: `image_fallback`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- requires target as current with previous symlink absent and state previous absent before arm
- generic target-over-previous setup is intentionally not emitted for this checkpoint
- arm command is reachable only when rollback has no previous runtime to adopt
- rollback result is expected to be image_fallback, not previous
- prepare only on a lab image or after backing up device state

Manual setup before arm:
- Use only a lab image or a board state that has been backed up for destructive H2 trials.
- Prepare target as the data current runtime, then remove the previous symlink and any state previous pointer before arming.
- Confirm the rollback topology is target-current-without-previous-link-or-state before running the arm command.
- Record the pre-arm current/previous/state topology in the checkpoint evidence notes before physical cut.

Do not run the arm command until the custom setup has been completed and recorded.

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-rollback \
  --checkpoint 'rollback_after_current_unlinked' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_current_unlinked/trial' \
  --quarantine-current \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_current_unlinked/trial' \
  --expected-source fallback \
  --expected-source-after-reconcile fallback \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `16/17`.

## 17. rollback_after_state_success

- Phase: `rollback`
- Setup precondition: `target-current-over-expected-previous`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- postcheck.txt is required by the evidence gate
- trial/resume/post-reconcile-state.json is required by the evidence gate

Setup before arm:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
mkdir -p '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_state_success/setup'
C18_PLAYER_RUNTIME_LAB_APPLY=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_lab_apply.py \
  --lab-only-apply \
  --manifest '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.manifest.json' \
  --payload '/data/c18-powerloss-bundle-3eb06f1/releases/player-runtime/c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1/dadooh-player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1.tar.gz' \
  --data-root /data \
  --allow-device-data-root \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --output-dir '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_state_success/setup/apply' \
  --startup-wait-sec 12 \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_state_success/setup/lab-apply.json'
python3 scripts/qa/c18_player_runtime_adoption_probe.py \
  --data-root /data \
  --expected-source data \
  --expected-version 'c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1' \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_state_success/setup/service-adoption.json'
python3 scripts/board/c18_playback_health_collect.py \
  --duration-sec 60 \
  --interval-sec 1 \
  --output-dir '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_state_success/setup/service-health' \
  --json > '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_state_success/setup/service-health.json'
```

Arm command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-rollback \
  --checkpoint 'rollback_after_state_success' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_state_success/trial' \
  --quarantine-current \
  --expect-rolled-to 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-powerloss-bundle-3eb06f1'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1/rollback_after_state_success/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a-20260610T0501Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `17/17`.

## Final Validation

After all missing checkpoints are collected and copied into a local evidence
directory, rerun the H2 readiness gate with all 17 physical power-loss
evidence directories. H2 must remain blocked until 17/17 power-loss, soak
24h, stable promotion, and formal thaw decision are all present.

Non-claims:

- `this_runbook_is_not_powerloss_evidence`
- `this_runbook_does_not_claim_17_17`
- `this_runbook_does_not_execute_board_commands`
- `this_runbook_does_not_pull_or_validate_evidence_by_itself`
- `this_runbook_does_not_replace_physical_power_cut`
- `this_runbook_does_not_authorize_stable_or_production`
- `this_runbook_does_not_thaw_player_runtime`
- `this_runbook_does_not_publish_or_fetch_releases`
- `remote_reboot_is_not_acceptable_powerloss_evidence`
