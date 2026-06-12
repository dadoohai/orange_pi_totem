# C18 H2 Power-Loss Checkpoint Runbook

Run one checkpoint at a time. A checkpoint is not evidence until physical
power has been removed after `CUT_POWER_NOW`, the board has booted again,
the resume command has passed, and the evidence gate has accepted the
pulled directory.

Do not use remote reboot as a substitute for power loss.

## Preflight Before Physical Session

Collect this read-only preflight from board stdout into a local file, then
run the offline gate against the matrix plan. Do not start physical cuts if
the gate is red.

```sh
scp scripts/board/c18_player_runtime_h2_powerloss_preflight_collect.py <board-host>:/tmp/c18_player_runtime_h2_powerloss_preflight_collect.py
ssh <board-host> \
  "cd '/data/c18-p0-bundle-a0dcb13fd78d' && \
   PYTHONDONTWRITEBYTECODE=1 \
   PYTHONPATH='/data/c18-p0-bundle-a0dcb13fd78d/scripts/board' \
   python3 -B /tmp/c18_player_runtime_h2_powerloss_preflight_collect.py \
     --bundle-dir '/data/c18-p0-bundle-a0dcb13fd78d' \
     --evidence-root '/data/c18-evidence/h2-c16fb3e' \
     --canary-media '/data/media/c18-canary-h264.mp4' \
     --json" \
  > 'docs/evidence/c18-update-validation/<utc>-h2-powerloss-board-preflight.json'
ssh <board-host> \
  "rm -f /tmp/c18_player_runtime_h2_powerloss_preflight_collect.py"
python3 scripts/qa/c18_player_runtime_h2_powerloss_preflight_gate.py \
  --preflight 'docs/evidence/c18-update-validation/<utc>-h2-powerloss-board-preflight.json' \
  --matrix-plan 'docs/evidence/c18-update-validation/20260612T131426Z-h2-powerloss-matrix-plan-c16fb3e/powerloss-matrix-plan.json' \
  --expect-image-tag 'c18-hwdecode-lab-1x' \
  --expect-image-marker-sha256 '59739f57cdb3f79ac4c8ce5e5e1f9c4aa6d9dae58f704010f8423e66abe2bb9e' \
  --json
```

## 1. after_payload_staged

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none emitted by the plan.

Arm command:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_payload_staged' \
  --manifest '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json' \
  --payload '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_payload_staged/trial' \
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
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_payload_staged/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `1/12`.

## 2. after_release_dir_created

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none emitted by the plan.

Arm command:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_release_dir_created' \
  --manifest '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json' \
  --payload '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_release_dir_created/trial' \
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
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_release_dir_created/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `2/12`.

## 3. after_extract

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none emitted by the plan.

Arm command:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_extract' \
  --manifest '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json' \
  --payload '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_extract/trial' \
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
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_extract/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `3/12`.

## 4. after_state_verifying

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none emitted by the plan.

Arm command:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_state_verifying' \
  --manifest '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json' \
  --payload '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_state_verifying/trial' \
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
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_state_verifying/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `4/12`.

## 5. after_health_passed

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none emitted by the plan.

Arm command:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_health_passed' \
  --manifest '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json' \
  --payload '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_health_passed/trial' \
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
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_health_passed/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `5/12`.

## 6. after_release_tree_fsync

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none emitted by the plan.

Arm command:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_release_tree_fsync' \
  --manifest '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json' \
  --payload '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_release_tree_fsync/trial' \
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
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_release_tree_fsync/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `6/12`.

## 7. after_marker_written

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none emitted by the plan.

Arm command:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_marker_written' \
  --manifest '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json' \
  --payload '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_marker_written/trial' \
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
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_marker_written/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `7/12`.

## 8. after_previous_symlink

- Phase: `apply`
- Setup precondition: `old-current-present-and-different-from-target`
- Requires custom setup: `true`
- Expected resume version: `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints
- after_previous_symlink is reachable only when an old current exists and differs from the target

Setup before arm: none emitted by the plan.

Arm command:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_previous_symlink' \
  --manifest '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json' \
  --payload '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_previous_symlink/trial' \
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
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_previous_symlink/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `8/12`.

## 9. after_state_success

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none emitted by the plan.

Arm command:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'after_state_success' \
  --manifest '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json' \
  --payload '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_state_success/trial' \
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
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/after_state_success/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `9/12`.

## 10. before_stage_cleanup

- Phase: `apply`
- Setup precondition: `standard-target-apply`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- fresh apply path is required for payload staging, release directory, and extract checkpoints

Setup before arm: none emitted by the plan.

Arm command:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint 'before_stage_cleanup' \
  --manifest '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json' \
  --payload '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz' \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/before_stage_cleanup/trial' \
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
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/before_stage_cleanup/trial' \
  --expected-source data \
  --expected-version 'c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `10/12`.

## 11. rollback_after_identify_links

- Phase: `rollback`
- Setup precondition: `target-current-over-expected-previous`
- Requires custom setup: `false`
- Expected resume version: `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`

Notes:
- physical power must be removed only after CUT_POWER_NOW is printed and persisted
- remote reboot is not acceptable evidence
- requires target as current and previous as the expected old active runtime before arm
- requires --quarantine-current so the checkpoint records quarantined_current=true
- standard fresh lab apply setup is used so target-over-previous topology is explicit
- resume is expected to see fallback before reconcile and data previous after reconcile

Setup before arm:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
mkdir -p '/data/c18-evidence/h2-c16fb3e/rollback_after_identify_links/setup'
C18_PLAYER_RUNTIME_LAB_APPLY=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_lab_apply.py \
  --lab-only-apply \
  --manifest '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json' \
  --payload '/data/c18-p0-bundle-a0dcb13fd78d/releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz' \
  --data-root /data \
  --allow-device-data-root \
  --canary-media '/data/media/c18-canary-h264.mp4' \
  --output-dir '/data/c18-evidence/h2-c16fb3e/rollback_after_identify_links/setup/apply' \
  --startup-wait-sec 12 \
  --json > '/data/c18-evidence/h2-c16fb3e/rollback_after_identify_links/setup/lab-apply.json'
python3 scripts/qa/c18_player_runtime_adoption_probe.py \
  --data-root /data \
  --expected-source data \
  --expected-version 'c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e' \
  --json > '/data/c18-evidence/h2-c16fb3e/rollback_after_identify_links/setup/service-adoption.json'
python3 scripts/board/c18_playback_health_collect.py \
  --duration-sec 45 \
  --interval-sec 1 \
  --output-dir '/data/c18-evidence/h2-c16fb3e/rollback_after_identify_links/setup/service-health' \
  --json > '/data/c18-evidence/h2-c16fb3e/rollback_after_identify_links/setup/service-health.json'
```

Arm command:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-rollback \
  --checkpoint 'rollback_after_identify_links' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/rollback_after_identify_links/trial' \
  --quarantine-current \
  --expect-rolled-to 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --json
```

Operator action:

1. Wait until the command prints `CUT_POWER_NOW`.
2. Remove physical power. Do not use remote reboot.
3. Restore power and wait for SSH.
4. Run the resume command below before starting the next checkpoint.

Resume command:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/rollback_after_identify_links/trial' \
  --expected-source fallback \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile 'c18.player-runtime-m6-a2-20260610T072826Z-29ff33b' \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `11/12`.

## 12. rollback_after_current_unlinked

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

Setup before arm: none emitted by the plan.

Arm command:

```sh
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-rollback \
  --checkpoint 'rollback_after_current_unlinked' \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/rollback_after_current_unlinked/trial' \
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
cd '/data/c18-p0-bundle-a0dcb13fd78d'
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root '/data/c18-evidence/h2-c16fb3e/rollback_after_current_unlinked/trial' \
  --expected-source fallback \
  --expected-source-after-reconcile fallback \
  --startup-wait-sec 12 \
  --json
```

Progress marker: `12/12`.

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
