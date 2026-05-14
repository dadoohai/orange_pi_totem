# 161 - C17.1 - Homolog UX-Gated Image Validation

## Status

```text
c17_1_status=passed
artifact_private=true
final_image=false
homologation_shipping_image=true
not_for_production=true
not_for_distribution=true
kernel_reused=true
kernel_rebuild_executed=false
card_written=true
single_board_validated=true
full_setup_flow_passed=true
ready_for_batch_flash=true
ready_for_dispatch=true
ready_for_c18_player_audit=true
```

C17.1 consolidated the C14 pull updater, the C15 visual setup fixes, the
C15.3.2 startup/loading feedback bridge and the C16.2 UX gates into a private
homologation image. The image remains a homologation artifact, not a production
or distribution image.

## Image

```text
image_tag=c17-1-homolog-ux-gated
image_version=c17.1
image_sha256=017a28e8bd2841b2f46dc9cb70f2d166963f36908ccc6503d14d104babb4940e
c14_updater_embedded=true
c15_fixes_embedded=true
c15_3_2_startup_feedback_embedded=true
c16_2_harness_present_on_builder=true
qa_artifacts_not_installed=true
c12_readonly_blocked=true
c12_4_blocked=true
```

The image was derived offline from the validated C14.2.1 base. It reused the
existing kernel/BSP path and did not run Armbian Build, apt, pip or kernel
tooling.

## Clean-Board Result

The clean board reached the visual wizard, completed Wi-Fi and setup through
the normal HDMI flow, wrote the real config via the wizard path and restored the
player. Runtime evidence was collected over SSH using sanitized probes only.

```text
writer_passed=true
config_real_present_after_writer=true
config_real_content_read=false
session_lock_present_after_writer=false
kiosky_player_active_after_writer=true
playback_state_after_restore=playing
mpv_process_present=true
ssh_active_after_writer=true
network_connected_after_writer=true
visual_tty_guard_active=true
pull_update_timer_enabled=true
totem_updatectl_status_ok=true
```

One non-kiosk failed unit was present: `console-setup.service`. It did not block
SSH, NetworkManager, the wizard, MPV, player restore or the update timer.

## C16.2 Gates

```text
gate_api_cache_content=passed
gate_wifi_negative=passed
gate_update_ux=passed
gate_wizard_visual_consistency=passed
hdmi_camera_required_before_scale=true
hdmi_camera_required_before_c17=false
```

The negative API/cache/content, Wi-Fi and update paths were validated through
the executable C16.2 synthetic user harness, the generated SVG gallery and safe
public-status checks. No destructive runtime fault injection was applied on the
configured board.

Wizard visual consistency passed through the C16.2 gallery/rubric gate:

```text
synthetic_user_runs_count=75
journeys_scored_count=15
screens_scored_count=25
p0_items_count=0
worst_journey=T_estado_sem_cache
worst_journey_score=3.6
worst_screen=wifi_list
worst_screen_score=4.3
critical_screens_below_4=false
```

## Decision

C17.1 is released for the homologation batch/dispatch step:

```text
ready_for_batch_flash=true
ready_for_dispatch=true
ready_for_c18_player_audit=true
```

C18 may open next for the player timing/sync/duration/loop audit. C17.1 did not
start C18 and did not alter scheduler, sync, duration, playlist, loop or
`exposure_time_ms`.

## Remaining Limits

HDMI/camera capture remains required before scale to prove perception-level
black-frame, flicker and transition quality. C12 read-only and C12.4 power-cut
testing remain blocked and were not touched in C17.1.

## C17.2 Follow-Up

C17.2 accepted C17.1 as functional image/gate validation but kept the perceived
UX line open. It created a mini visual design system and applied the first
explicit visual polish pass to wizard, splash and public status SVGs without
opening C18 or changing player timing/sync/duration/loop behavior.

```text
c17_2_status=passed
ready_for_c17_3_image_rebuild=true
ready_for_c18_player_audit=false
```

Evidence:

```text
docs/evidence/candidate-a/runs/20260514T054942Z-c17-1-homolog-ux-gated-clean-board-validation/
```
