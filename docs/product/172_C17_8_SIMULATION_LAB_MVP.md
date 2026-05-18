# 172 - C17.8 - Simulation Lab MVP

Status: passed

C17.8 creates a local simulation-first QA lab for the Orange Pi Totem appliance
while no Orange Pi Zero 3 is available. The round does not touch hardware, does
not write cards, does not build a new image, does not use SSH, and does not
start C18/player timing work.

## C17.7 status

C17.7 passou validacao offline/rootfs.

C17.7 nao foi validada em cartao limpo.

Sem Orange Pi disponivel, nao e possivel confirmar causa de nao boot.

C17.7 nao libera batch/dispatch/C18.

C17.7 deve ficar como:

`c17_7_status=offline_passed_hardware_unvalidated`

`ready_for_batch_flash=false`

`ready_for_dispatch=false`

`ready_for_c18_player_audit=false`

## Local audit

Repository branches matched the expected local state:

- `orange_pi_totem`: `foundation-v0.1`
- `kiosky-player`: `appliance-v0.1`

Both worktrees were clean before C17.8 edits. `git diff --check` passed in
`orange_pi_totem`.

Existing syntax/self-tests passed for wizard, Wi-Fi adapter, splash, config
contract, restore-order static check, appliance manifest JSON, `kiosk.py`
compile, and the `kiosky-player` unit suite.

The existing `totem_updatectl.py self-test` commands were allowed to continue by
the requested `|| true`, but both hit host permission on `/data`. C17.8 covers
the updater behavior through the sandbox instead of writing to real `/data`.

## Boot artifact diff

Script:

`scripts/qa/c17_8_compare_image_boot_artifacts.py`

Evidence:

`docs/evidence/candidate-a/runs/20260518T183230Z-c17-8-simulation-lab-mvp/boot-artifact-diff.json`

Result:

- `c17_4_2_image_found=true`
- `c17_7_image_found=true`
- `boot_partition_changed=false`
- `uboot_changed=false`
- `kernel_changed=false`
- `dtb_changed=false`
- `initrd_changed=false`
- `boot_script_changed=false`
- `rootfs_only_change=true`
- `boot_risk_level=low`

Conclusion: boot-critical artifacts matched between the validated C17.4.2 image
and the C17.7 image. The detected delta is rootfs/userland, mainly systemd
unit/wrapper/totem-core paths. This lowers local boot-risk suspicion, but does
not replace physical Orange Pi validation.

## Simulation sandbox

Scripts:

- `scripts/sim/prepare_totem_sim_sandbox.py`
- `scripts/sim/run_totem_core_sandbox.py`

Sandbox:

`.sim/totem`

Mode:

`sandbox_mode=repo_overlay`

Evidence:

`docs/evidence/candidate-a/runs/20260518T183230Z-c17-8-simulation-lab-mvp/totem-core-sandbox.json`

Result:

- `package_built=true`
- `package_built_by_release_script=true`
- `sha256_validated=true`
- `apply_local_passed=true`
- `current_symlink_updated=true`
- `previous_symlink_updated=true`
- `rollback_passed=true`
- `wrapper_current_passed=true`
- `wrapper_fallback_passed=true`
- `settings_lock_guard_passed=true`
- `writes_outside_sim_detected=false`
- `result=passed`

## Placeholders

The following harness stubs were created only as placeholders:

- `scripts/sim/run_wizard_input_replay.py`
- `scripts/sim/run_player_fake_mpv_api.py`

No broad wizard replay and no fake MPV/API player simulation were implemented in
this round.

## Decision

`c17_8_status=passed`

`ready_for_c17_8_1_wizard_replay=true`

`ready_for_c18_1_player_sim_audit=true`

`hardware_homologation_required=true`

C17.8 proves the local methodology is useful enough to continue. It does not
homologate C17.7 hardware behavior, does not release batch/dispatch, and does
not start C18 player timing/sync/duration/looping.
