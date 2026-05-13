# 146 - C15.2.4 - Clean-board image validation

## Status

```text
c15_2_4_status=passed
image_built=true
kernel_reused=true
kernel_rebuild_executed=false
single_board_validated=true
full_setup_flow_passed=true
ready_for_batch_flash=true
ready_for_dispatch=true
ready_for_c16_player_audit=true
c16_started=false
```

C15.2.4 consolidates the C15 wizard/UX reliability work into a fresh private
homologation image and validates it on a clean board.

## Image

```text
image_version=c15.2.4
image_tag=c15-2-4-homolog-clean-board-fixes
artifact_private=true
final_image=false
homologation_shipping_image=true
not_for_production=true
not_for_distribution=true
c12_readonly_blocked=true
c12_4_blocked=true
sha256=e36b86004c75663fd4c3d14d8ed8b6186f102c8b644e7dbc4351ca734036dca9
```

The image was derived from the validated C14.2.1 private homologation image by
replacing only the manifest-managed appliance files. Kernel, U-Boot, DTB, BSP,
package set, apt, pip, read-only/C12, and player code were not changed.

## Embedded Fixes

Offline validation confirmed:

- C14 pull updater and update timer are preserved;
- C15.1.3 visual TTY guard is embedded and enabled;
- C15.1.4 Wi-Fi pagination, refresh, signal display, and hidden password flow
  are embedded;
- C15.1.5 text simplification, Backspace debounce, and splash feedback are
  embedded;
- C15.2.2 monotonic `openvt` timeout is embedded;
- printable `V`/`v` are accepted as password characters;
- password visibility no longer uses printable `V`;
- F2 is the advertised password show/hide key, with Ctrl+P as fallback;
- C15.2.3 monitor exists only in the repo and is not installed or enabled by
  default in the image;
- QA/evidence/gallery artifacts are not installed in the appliance rootfs;
- private seed is present with expected permissions without publishing content;
- no real config is embedded.

## Clean Board Result

The operator flashed one clean board and ran first setup via F10. The wizard did
not exit during configuration. The environment input survived after Wi-Fi/time
sync. The writer passed. The session lock was cleaned. The player was restored.
SSH and NetworkManager remained active.

Runtime evidence:

```text
wizard_rc=8
handoff_rc=0
writer_rc=0
writer_result=passed
real_config_written=true
service_active=active
public_state=player_running
playback=playing
ssh_active_after_writer=true
network_connected_after_writer=true
session_lock_present=false
tty1_echo=false
tty2_echo=false
tmp_permissions=1777
totem_updatectl_status_ok=true
```

The operator observed the expected save/start-player splash sequence. A
transient black interval appeared while entering the player after first setup,
then the player was running and SSH remained available. This is not the C15.2.2
failure mode because there was no SSH loss and no recovery was required. It is
recorded as a player/startup follow-up for the next audit stage.

One non-blocking failed unit, `console-setup.service`, was present with a
sanitized `setupcon` temporary file error. It did not block keyboard input,
wizard operation, SSH, NetworkManager, player restore, or playback.

## Decision

C15.2.4 passes clean-board image validation:

```text
ready_for_batch_flash=true
ready_for_dispatch=true
ready_for_c16_player_audit=true
```

C16/player audit may now be opened separately. No C16 work was started in this
card.

Follow-up: C15.3.1 audited the user-perceived visual transition before C16 and
recommended a C15.3.2 feedback fix for the transient pre-player black interval.

## Evidence

`docs/evidence/candidate-a/runs/20260513T210628Z-c15-2-4-clean-board-image-validation/`
