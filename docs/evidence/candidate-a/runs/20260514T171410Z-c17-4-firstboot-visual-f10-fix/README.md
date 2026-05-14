# C17.4 First Boot Visual/F10 Fix

c17_4_status=blocked
image_built=true
image_file=/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c17-4-firstboot-visual-f10-fix_minimal.img
image_sha256=9e9092fb7dcb04a06e1617ad048042305a285373c19261b0dd10bc96c0975058
kernel_reused=true
kernel_rebuild_executed=false

previous_c17_3_blocker=true
first_boot_black_screen_fixed=false
startup_feedback_before_config_visible=false
f10_ready_on_first_boot=false
first_f10_opens_wizard=false
misformatted_splash_fixed=true
config_missing_text_overlap=false
wizard_surface_exclusive=false
status_renderer_respects_session_lock=true
kiosky_player_not_drawing_during_settings=true

hotfix_applied_to_board=false
card_written=false
single_board_validated=false
full_setup_flow_passed=false
writer_passed=false
player_restore_ok=false
ssh_active_after_writer=false
network_connected_after_writer=false
loading_content_feedback_visible=false

ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c18_player_audit=false

secrets_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
read_only_touched=false
kernel_touched=false
wifi_touched_only_by_wizard=false
networkmanager_touched_only_by_wizard=false
poweroff_executed=false
power_cut_tested=false
planned_power_cut_tested=false
c12_4_power_cut_tested=false
scheduler_changed=false
sync_changed=false
duration_changed=false
loop_changed=false
exposure_time_ms_changed=false
c12_readonly_blocked=true
c12_4_blocked=true

## Scope

C17.4 fixed the known C17.3 visual ownership defect offline and produced a new
private homologation image. The status remains blocked because a clean board has
not yet been written and booted with this image.

## Offline Validation

- C17.4 derivation passed rootfs validation.
- `kiosky-player.service` is no longer blocked by `network-online.target` before
  pre-config feedback.
- `kiosky-player.service` has `ConditionPathExists=!/run/totem/settings-session.lock`.
- Status renderer checks the settings-session lock before start and exits if
  the lock appears while rendering.
- Launcher blocks public splash/status/player drawing while the lock exists.
- Splash preview separates `Dadooh`, `Configuracao pendente` and `Pressione F10`
  into non-overlapping lines.
- C16.2 synthetic UX smoke passed after the change.

## Image Validation

Offline validation artifact:

`offline-build/c17-4-offline-validation.json`

Kernel was reused and no kernel rebuild was executed.

## Pending Clean-Board Gate

The next validation must use a manually flashed clean card:

1. Boot with no config.
2. Confirm HDMI is not black before F10.
3. Confirm pre-config feedback is visible and not overlapped.
4. Hold F10 and confirm wizard opens on the first attempt.
5. Confirm status renderer does not cover the wizard.
6. Complete wizard only after the first-boot evidence is collected.
