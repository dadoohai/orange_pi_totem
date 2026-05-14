# 164 - C17.3 - Visual Polish Image Validation

## Status

```text
c17_3_status=blocked
image_built=true
kernel_reused=true
kernel_rebuild_executed=false
c17_2_visual_polish_embedded=true
card_written=false
single_board_validated=false
full_setup_flow_passed=false
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c18_player_audit=false
```

C17.3 consolidates the C17.2 visual design pass into a private homologation
image. The image was generated and validated offline, but clean-board runtime
validation is still pending because card writing is performed manually with
Armbian Imager.

## Image

```text
image_tag=c17-3-homolog-visual-polish
image_version=c17.3
image_sha256=022e541a102424badc1bf539872696fed971f34e2fd8ed224b143527141e4ea2
artifact_private=true
final_image=false
homologation_shipping_image=true
not_for_production=true
not_for_distribution=true
visual_design_system_version=c17.2-appliance-ui.v1
c12_readonly_blocked=true
c12_4_blocked=true
```

The derivation reused the validated C14.2.1 base and did not invoke Armbian
Build, apt, pip, kernel tooling, U-Boot, DTB or BSP changes. The appliance
layer now includes the C17.2 wizard, splash and public-status visual polish.

## Offline Result

```text
wizard_visual_polish_present=true
splash_visual_polish_present=true
status_visual_polish_present=true
c14_updater_embedded=true
c15_fixes_embedded=true
c15_3_2_startup_feedback_embedded=true
kiosky_player_embedded=true
seed_permissions_ok=true
seed_content_published=false
no_real_config_embedded=true
qa_artifacts_not_installed=true
splash_does_not_chmod_tmp=true
```

The C17.2 mini design system is present in the generated appliance scripts:
dark appliance surfaces, consistent panels/cards, accent rails, footer action
chips and public support/status language.

## Clean-Board Result

Runtime validation has not run yet:

```text
card_written=false
single_board_validated=false
visual_polish_visible_on_hdmi=unknown
old_visual_style_seen=unknown
black_screen_without_feedback_observed=unknown
writer_passed=false
player_restore_ok=false
playback_state_after_restore=not_tested
```

The remaining action is to flash the image manually with Armbian Imager, boot a
clean board, complete the F10 wizard while observing HDMI and collect sanitized
SSH evidence.

## Gates

```text
gate_api_cache_content=passed
gate_wifi_negative=passed
gate_update_ux=passed
gate_wizard_visual_consistency=passed
critical_screens_below_4=false
worst_screen=wifi_list
worst_screen_score=4.3
worst_journey=T_estado_sem_cache
worst_journey_score=3.6
```

These gates passed offline through the executable C16.2/C17.2 harness and image
rootfs inspection. They still need clean-board confirmation for HDMI perception
and full setup restore.

## Decision

C17.3 is not released for batch flash, dispatch or C18:

```text
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c18_player_audit=false
```

The initial blocker was pending manual clean-board validation. After manual
flash and boot, C17.3 exposed a first-boot pre-config visual/F10 blocker:
first boot showed a black HDMI screen, F10 did not respond, and recovery needed
a physical power cycle. On the second boot the wizard opened after F10, but
later the operator saw the public configuration-pending/status surface instead
of the wizard while the writer had not run. See:

```text
docs/product/165_C17_3_FIRST_BOOT_VISUAL_F10_BLOCKER.md
docs/evidence/candidate-a/runs/20260514T165343Z-c17-3-first-boot-visual-f10-blocker/
```

## Remaining Limits

HDMI/camera capture remains required before scale. C12 read-only and C12.4
power-cut testing remain blocked and were not touched.
