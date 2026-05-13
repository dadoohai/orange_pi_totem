# 145 - C15.2.3 - Post-wizard black-screen and SSH-loss classification

## Status

```text
c15_2_3_status=passed
post_wizard_failure_reproduced=false
post_wizard_failure_cause=not_reproduced_in_monitored_retest
ready_for_image_rebuild=true
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c16_player_audit=false
c16_started=false
```

C15.2.3 was opened to classify the remaining C15.2.2 blocker: after the wizard
writer passed, HDMI had gone black and SSH became unreachable, requiring
emergency physical recovery.

## Prior Fixes

C15.2.2 already fixed the clean-board wizard interruption:

- root cause: `service_timeout`;
- detail: wall-clock jump after Wi-Fi/NTP made the `openvt` deadline expire;
- fix: timeout now uses monotonic uptime from `/proc/uptime`;
- password fix: printable `V`/`v` are normal password characters again, F2 is
  the advertised show/hide key, and Ctrl+P is the non-printable fallback.

That original bug remains classified as a latent clean-board setup bug, not a
regression.

## Instrumentation

C15.2.3 added a temporary persistent monitor:

```text
scripts/remote/c15_2_3_post_wizard_monitor.sh
```

The monitor writes sanitized state to `/data/state/totem-debug/c15-2-3/<run-id>/`
once per second. It tracks service booleans, player process presence, playback
state, NetworkManager connected category, SSH service state, session lock state,
boot id continuity, memory/disk buckets, and the last C15 trace phase.

The settings session and wizard now emit sanitized phase markers while the
monitor is active. The markers cover wizard start, Wi-Fi step, environment input,
writer start/done/result, cleanup, player restore, post-restore checkpoints, and
session completion.

No real config, private seed, NetworkManager profiles, SSID, Wi-Fi password, IP,
MAC, DNS, API key, API URL, or environment identifier is read or written to the
evidence.

## Retest Result

The operator opened F10 and completed the wizard with the monitor active. The
failure did not reproduce.

Observed monitor/session result:

```text
environment_input_entered=true
writer_rc=0
writer_result=passed
player_restore_done=true
post_restore_t+5s=playing
post_restore_t+15s=playing
post_restore_t+30s=playing
session_done=true
ssh_active_after_writer=true
network_connected_after_writer=true
session_lock_present=false
failed_units_count=0
boot_id_changed=false
system_rebooted_spontaneously=false
oom_detected=false
kernel_panic_detected=false
```

The board stayed reachable by SSH. NetworkManager stayed connected. MPV and the
kiosk process were present. Playback state returned to `playing`. The operator
reported that the HDMI flow appeared OK. The persistent monitor finished its
600-second window normally with 329 samples and no boot id change.

## Classification

The C15.2.2 black-screen/SSH-loss window is classified as:

```text
post_wizard_failure_cause=not_reproduced_in_monitored_retest
```

Because the monitored retest reached `post_restore_t+30s` and `session_done`
with SSH, NetworkManager, player, MPV, and playback still healthy, there is no
evidence of:

- NetworkManager disconnect/readdress during writer;
- SSH service stop;
- spontaneous reboot;
- OOM/resource exhaustion;
- kernel panic;
- session cleanup killing player or network;
- player restore failure.

## Decision

C15.2.3 is passed for classification and releases a new image rebuild attempt:

```text
ready_for_image_rebuild=true
```

Batch flash, dispatch, and C16/player audit remain blocked until the next image
is rebuilt and validated on a clean board:

```text
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c16_player_audit=false
c16_started=false
```

## C15.2.4 Follow-Up

C15.2.4 rebuilt the private homologation image with the C15.2.2/C15.2.3 fixes
embedded and passed clean-board validation. Batch flash/private dispatch and the
next C16/player audit are now unblocked by C15.

## Evidence

`docs/evidence/candidate-a/runs/20260513T203036Z-c15-2-3-post-wizard-black-screen-ssh-loss-classification/`
