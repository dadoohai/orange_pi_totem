# C18 P0 power-loss prep - c16fb3e homologation target

Status: prep only. This does not claim any P0 checkpoint, pilot readiness, H2,
stable, production, auto-pull, public thaw, or physical power-loss coverage.

## Prepared target

- Repo head: `a0dcb13fd78da826be2b33820bd11d254ba72368`
- Board bundle: `/data/c18-p0-bundle-a0dcb13fd78d`
- Bundle archive: `/data/c18-p0-bundle-a0dcb13fd78d.tar.gz`
- Bundle SHA256: `e4ed9293e6fa8ac53a08509b091e8428cf413ac99dd6ea2185774dea488436ea`
- Target version: `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`
- Target payload SHA256: `d74a552f364de0e454a01a6fe839a1581d16c1b74acb357dc92c28a3ec0524a7`
- Canary media: `/data/media/c18-canary-h264.mp4`

Board snapshot at prep:

- host: `orangepizero3`
- service: `kiosky-player.service active`
- current: `releases/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`
- previous: `releases/c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`
- quarantine count: `1`

On-board self-tests passed:

- `scripts/qa/c18_player_runtime_powerloss_trial.py --self-test`
- `scripts/qa/c18_player_runtime_powerloss_evidence_gate.py --self-test`

## P0 checkpoints still required

- `after_current_symlink`
- `rollback_after_current_to_previous`
- `rollback_after_previous_removed`
- `rollback_after_quarantine`
- `rollback_after_state_success`

The harness is intentionally physical. A valid P0 run must arm a checkpoint,
persist `CUT_POWER_NOW`, have power removed from the board, boot again, then run
the `resume` phase. A remote `reboot` or `systemctl reboot` is not acceptable
evidence for this gate.

## Board command skeleton

Run from the board, inside the prepared bundle:

```sh
cd /data/c18-p0-bundle-a0dcb13fd78d
PKG_DIR=releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e
MANIFEST="$PKG_DIR/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.manifest.json"
PAYLOAD="$PKG_DIR/dadooh-player-runtime-c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e.tar.gz"
CANARY=/data/media/c18-canary-h264.mp4
TARGET=c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e
PREVIOUS=c18.player-runtime-m6-a2-20260610T072826Z-29ff33b
```

For `after_current_symlink`, start from `PREVIOUS`, then arm apply:

```sh
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-apply \
  --checkpoint after_current_symlink \
  --manifest "$MANIFEST" \
  --payload "$PAYLOAD" \
  --canary-media "$CANARY" \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root /data/c18-evidence/p0-c16fb3e-after_current_symlink/trial \
  --allow-reapply-linked-previous \
  --startup-wait-sec 12 \
  --json
```

After physical power is restored:

```sh
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root /data/c18-evidence/p0-c16fb3e-after_current_symlink/trial \
  --expected-source data \
  --expected-version "$TARGET" \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile "$TARGET" \
  --startup-wait-sec 12 \
  --json
```

For each rollback checkpoint, prepare a fresh target-over-previous setup first,
then arm rollback:

```sh
CP=<rollback_checkpoint>
mkdir -p "/data/c18-evidence/p0-c16fb3e-$CP/setup"

C18_PLAYER_RUNTIME_LAB_APPLY=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_lab_apply.py \
  --lab-only-apply \
  --manifest "$MANIFEST" \
  --payload "$PAYLOAD" \
  --data-root /data \
  --allow-device-data-root \
  --canary-media "$CANARY" \
  --output-dir "/data/c18-evidence/p0-c16fb3e-$CP/setup/apply" \
  --allow-reapply-linked-previous \
  --startup-wait-sec 12 \
  --json > "/data/c18-evidence/p0-c16fb3e-$CP/setup/lab-apply.json"

python3 scripts/qa/c18_player_runtime_adoption_probe.py \
  --data-root /data \
  --expected-source data \
  --expected-version "$TARGET" \
  --json > "/data/c18-evidence/p0-c16fb3e-$CP/setup/service-adoption.json"

python3 scripts/board/c18_playback_health_collect.py \
  --duration-sec 45 \
  --interval-sec 1 \
  --output-dir "/data/c18-evidence/p0-c16fb3e-$CP/setup/service-health" \
  --json > "/data/c18-evidence/p0-c16fb3e-$CP/setup/service-health.json"
```

Then arm rollback:

```sh
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase arm-rollback \
  --checkpoint "$CP" \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root "/data/c18-evidence/p0-c16fb3e-$CP/trial" \
  --quarantine-current \
  --expect-rolled-to "$PREVIOUS" \
  --json
```

After physical power is restored:

```sh
C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_powerloss_trial.py \
  --phase resume \
  --data-root /data \
  --allow-device-data-root \
  --evidence-root "/data/c18-evidence/p0-c16fb3e-$CP/trial" \
  --expected-source data \
  --expected-version "$PREVIOUS" \
  --expected-source-after-reconcile data \
  --expected-version-after-reconcile "$PREVIOUS" \
  --startup-wait-sec 12 \
  --json
```

Each final committed P0 evidence directory must also include:

- a `setup/` directory for rollback checkpoints;
- `postcheck.txt` where required by the gate;
- `trial/resume/post-reconcile-state.json` for `rollback_after_quarantine` and
  `rollback_after_state_success`;
- `evidence-manifest.json` with every file declared by bytes and SHA256;
- target package binding fields:
  - `target_package_version`
  - `target_payload_sha256`

Minimum `postcheck.txt` fields for the rollback checkpoints that require it:

```text
BOOT_ID=<boot-id-after-resume>
UPTIME=<uptime-sec-after-resume>
SERVICE_ACTIVE=active
TIMER_ENABLED=disabled
STRICT_GPU_FAULTS=0
PUBLIC_PLAYER_RUNTIME_APPLY_LOCAL_RC=44
PUBLIC_PLAYER_RUNTIME_ROLLBACK_RC=44
PUBLIC_PLAYER_RUNTIME_RECONCILE_RC=44
```

Only after all five directories pass
`scripts/qa/c18_player_runtime_powerloss_evidence_gate.py --run-dir ... --json`
should the pilot readiness gate be rerun.
