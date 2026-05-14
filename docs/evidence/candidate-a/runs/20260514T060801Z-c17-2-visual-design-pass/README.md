# C17.2 Visual Design Pass

## Status

```text
c17_2_status=passed
runtime_changed=false
board_accessed_via_ssh=false
manual_interaction_required=false
visual_design_system_created=true
visual_polish_applied=true
gallery_generated=true
gallery_screen_count=53
png_render_available=false
c16_2_harness_before_run=true
c16_2_harness_after_run=true
worst_screen_before=wifi_list
worst_screen_after=wifi_list
worst_screen_score_before=4.3
worst_screen_score_after=4.3
worst_journey_before=T
worst_journey_after=T
worst_journey_score_before=3.6
worst_journey_score_after=3.6
critical_screens_below_4=false
visual_scores_regressed=false
ready_for_c17_3_image_rebuild=true
ready_for_c18_player_audit=false
```

## What Changed

```text
visual_design_system_version=c17.2-appliance-ui.v1
wizard_svg_polished=true
splash_runtime_and_preview_polished=true
public_status_svg_polished=true
synthetic_gallery_polished=true
image_generated=false
board_hotfix_applied=false
```

The pass standardized dark appliance surfaces, active accent rails, selected
cards, info panels, primary-action footers, splash panels and public status
support guidance. It did not alter flow behavior.

## Gallery

```text
gallery_dir=docs/evidence/candidate-a/runs/20260514T060801Z-c17-2-visual-design-pass/gallery/gallery/
gallery_required_screens_present=true
svg_count=53
png_count=0
png_render_available=false
```

PNG rendering was not available without installing dependencies.

## C16.2 Rubric

```text
before_run=/tmp/c17-2-before
after_run=docs/evidence/candidate-a/runs/20260514T060801Z-c17-2-visual-design-pass/after
c16_2_status_after=passed
p0_items_count_after=0
p1_items_count_after=5
synthetic_user_runs_count_after=75
journeys_scored_count_after=15
screens_scored_count_after=25
```

The structural C16.2 rubric stayed stable. It does not fully score pixel-level
visual polish, so the correct gate reading is no regression plus generated SVG
evidence for review.

## Guardrails

```text
secrets_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
poweroff_executed=false
power_cut_tested=false
read_only_touched=false
kernel_touched=false
wifi_real_changed=false
networkmanager_touched=false
writer_called=false
real_config_written=false
scheduler_changed=false
sync_changed=false
duration_changed=false
loop_changed=false
exposure_time_ms_changed=false
c18_started=false
c12_readonly_blocked=true
c12_4_blocked=true
```
