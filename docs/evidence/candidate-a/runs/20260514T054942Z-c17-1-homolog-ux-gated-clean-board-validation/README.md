# C17.1 Homolog UX-Gated Clean-Board Validation

## Status

```text
c17_1_status=passed
image_built=true
image_file=/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c17-1-homolog-ux-gated_minimal.img
image_sha256=017a28e8bd2841b2f46dc9cb70f2d166963f36908ccc6503d14d104babb4940e
kernel_reused=true
kernel_rebuild_executed=false

artifact_private=true
final_image=false
homologation_shipping_image=true

c14_updater_embedded=true
c15_fixes_embedded=true
c15_3_2_startup_feedback_embedded=true
c16_2_harness_present=true
qa_artifacts_not_installed=true

card_written=true
single_board_validated=true
full_setup_flow_passed=true
writer_passed=true
player_restore_ok=true
ssh_active_after_writer=true
network_connected_after_writer=true
loading_content_feedback_visible=true
playback_state_after_restore=playing

gate_api_cache_content=passed
gate_wifi_negative=passed
gate_update_ux=passed
gate_wizard_visual_consistency=passed
hdmi_camera_required_before_scale=true
hdmi_camera_required_before_c17=false

pull_update_timer_enabled=true
totem_updatectl_status_ok=true

scheduler_changed=false
sync_changed=false
duration_changed=false
playlist_logic_changed=false
loop_logic_changed=false
exposure_time_ms_changed=false
c18_started=false

ready_for_batch_flash=true
ready_for_dispatch=true
ready_for_c18_player_audit=true
```

## Runtime Snapshot

```text
board_accessed_via_ssh=true
config_real_present_after_writer=true
config_real_read=false
session_lock_present_after_writer=false
kiosky_player_active_after_writer=true
networkmanager_active_after_writer=true
ssh_active_after_writer=true
open_settings_active_after_writer=false
visual_tty_guard_active=true
update_timer_active=true
mpv_process_present=true
public_status_classification=state:player_running,playback_state:playing
homologation_seed_present=true
homologation_seed_mode=600
homologation_seed_owner=root:root
qa_scripts_installed=false
docs_evidence_installed=false
failed_units_count=1
failed_units_names_sanitized=console-setup.service
```

The remaining failed unit is not part of the kiosk/player/update path and did
not block the wizard, SSH, NetworkManager, MPV or player restore.

## C16.2 Gate Evidence

```text
c16_2_harness_smoke=passed
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
gallery_generated=true
gallery_screen_count=53
png_render_available=false
```

Negative API/cache/content, Wi-Fi negative and update UX paths were validated
through the C16.2 synthetic harness, SVG gallery and safe public status checks.
No destructive fault injection was applied on the configured clean board.

## Guardrails

```text
secrets_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
read_only_touched=false
kernel_touched=false
wifi_touched_only_by_wizard=true
networkmanager_touched_only_by_wizard=true
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
