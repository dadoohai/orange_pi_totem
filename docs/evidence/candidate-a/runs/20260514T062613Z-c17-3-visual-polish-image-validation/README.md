# C17.3 Visual Polish Image Validation

## Status

```text
c17_3_status=blocked
image_built=true
image_file=/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c17-3-homolog-visual-polish_minimal.img
image_sha256=022e541a102424badc1bf539872696fed971f34e2fd8ed224b143527141e4ea2
kernel_reused=true
kernel_rebuild_executed=false

artifact_private=true
final_image=false
homologation_shipping_image=true

c17_2_visual_polish_embedded=true
visual_design_system_version=c17.2-appliance-ui.v1
wizard_visual_polish_present=true
splash_visual_polish_present=true
status_visual_polish_present=true

card_written=false
single_board_validated=false
full_setup_flow_passed=false
writer_passed=false
player_restore_ok=false
ssh_active_after_writer=false
network_connected_after_writer=false
loading_content_feedback_visible=false
playback_state_after_restore=not_tested

visual_polish_visible_on_hdmi=unknown
old_visual_style_seen=unknown
major_visual_issue_observed=false
black_screen_without_feedback_observed=unknown

gate_api_cache_content=passed
gate_wifi_negative=passed
gate_update_ux=passed
gate_wizard_visual_consistency=passed
hdmi_camera_required_before_scale=true
hdmi_camera_required_before_c17=false

pull_update_timer_enabled=true
totem_updatectl_status_ok=false

scheduler_changed=false
sync_changed=false
duration_changed=false
playlist_logic_changed=false
loop_logic_changed=false
exposure_time_ms_changed=false
c18_started=false

ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c18_player_audit=false
```

## Blocker

C17.3 is blocked only at the clean-board stage. The project writes cards
manually with Armbian Imager, and no card was written from the builder. Runtime
SSH, HDMI visual confirmation, wizard completion, writer and player restore
remain pending until a manually flashed C17.3 card boots on the lab board.

## Offline Image Evidence

```text
image_tag=c17-3-homolog-visual-polish
image_version=c17.3
c17_2_visual_polish_embedded=true
c14_updater_present=true
c14_update_agent_timer_enabled=true
c15_fixes_embedded=true
c15_3_2_startup_feedback_embedded=true
kiosky_player_embedded=true
seed_present=true
seed_permissions_ok=true
seed_content_published=false
no_real_config_embedded=true
qa_generator_not_installed=true
c16_2_harness_not_installed=true
docs_evidence_not_installed=true
splash_does_not_chmod_tmp=true
c12_readonly_blocked=true
c12_4_blocked=true
```

The image was derived offline from the validated C14.2.1 base. It did not run
Armbian Build, apt, pip, kernel tooling or a board probe. The existing
kernel/BSP path was reused.

## C16/C17 Gate Evidence

```text
c16_2_harness_post_image=passed
synthetic_user_runs_count=75
journeys_scored_count=15
screens_scored_count=25
p0_items_count=0
p1_items_count=5
worst_journey=T_estado_sem_cache
worst_journey_score=3.6
worst_screen=wifi_list
worst_screen_score=4.3
critical_screens_below_4=false
visual_scores_regressed=false
gallery_generated=true
gallery_screen_count=53
png_render_available=false
```

API/cache/content, Wi-Fi negative, update UX and wizard visual consistency were
validated offline through the C16.2/C17.2 harness and image-rootfs checks. No
destructive runtime fault injection was applied.

## Guardrails

```text
secrets_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
read_only_touched=false
kernel_touched=false
wifi_touched_only_by_wizard=false
networkmanager_touched_only_by_wizard=false
wifi_real_changed=false
networkmanager_touched=false
poweroff_executed=false
power_cut_tested=false
planned_power_cut_tested=false
c12_4_power_cut_tested=false
c12_readonly_blocked=true
c12_4_blocked=true
private_seed_content_read=false
real_config_content_read=false
networkmanager_profiles_read=false
raw_logs_published=false
writer_called_by_probe=false
update_apply_called=false
```

## Next Step

Flash exactly this image manually with Armbian Imager, boot one clean board and
continue C17.3 runtime validation over sanitized SSH plus HDMI observation.
