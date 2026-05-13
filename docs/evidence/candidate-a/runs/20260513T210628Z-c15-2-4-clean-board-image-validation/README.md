# C15.2.4 - Clean-board image validation

Run identifier: `20260513T210628Z-c15-2-4-clean-board-image-validation`

## Status

```text
c15_2_4_status=passed
image_built=true
image_file=/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c15-2-4-homolog-clean-board-fixes_minimal.img
image_sha256=e36b86004c75663fd4c3d14d8ed8b6186f102c8b644e7dbc4351ca734036dca9
kernel_reused=true
kernel_rebuild_executed=false

artifact_private=true
final_image=false
homologation_shipping_image=true
not_for_production=true
not_for_distribution=true

c14_updater_embedded=true
c15_1_3_embedded=true
c15_1_4_embedded=true
c15_1_5_embedded=true
c15_2_2_embedded=true
c15_2_3_monitor_not_enabled_by_default=true
qa_artifacts_not_installed=true

visual_tty_guard_active_runtime=true
tty1_echo_off_runtime=true
tty2_echo_off_runtime=true
tmp_permissions_1777=true

openvt_timeout_monotonic=true
password_v_chars_allowed=true
password_toggle_printable_v_removed=true
password_show_toggle_key=F2

wifi_ux_functional=true
backspace_debounce_functional=true
splash_feedback_functional=true

card_written=true
card_write_method=manual_operator
single_board_validated=true
first_f10_clean_board_passed=true
full_setup_flow_passed=true
environment_input_survived=true
writer_passed=true
session_lock_cleanup_ok=true
player_restore_ok=true
ssh_active_after_writer=true
network_connected_after_writer=true
post_wizard_black_screen_observed=true
post_wizard_black_screen_persistent=false
post_wizard_black_screen_detail=transient_first_player_start_or_media_wait
playback_state_after_restore=playing

pull_update_timer_enabled=true
totem_updatectl_status_ok=true

ready_for_batch_flash=true
ready_for_dispatch=true
ready_for_c16_player_audit=true
```

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
player_code_changed=false
c16_started=false
poweroff_executed=false
power_cut_tested=false
planned_power_cut_tested=false
c12_4_power_cut_tested=false
c12_readonly_blocked=true
c12_4_blocked=true
```

## Offline Validation

C15.2.4 was derived from the already validated C14.2.1 private homologation
image by replacing only the appliance-layer files listed in
`totem_appliance_manifest.json`. Kernel, U-Boot, DTB, BSP, rootfs package set,
apt, pip, read-only/C12, and player code were not changed.

Offline validation passed:

```text
image_name_contains_c15_2_4=true
c15_marker_present=true
visual_tty_guard_enabled=true
visual_tty_guard_holds_tty1_tty2=true
firstboot_raw_tty_output_removed=true
wifi_pagination_present=true
wifi_refresh_10s_present=true
wifi_signal_present=true
wifi_password_toggle_present=true
openvt_timeout_monotonic=true
password_v_chars_allowed=true
password_toggle_printable_v_removed=true
password_show_toggle_f2_ctrlp=true
backspace_debounce_present=true
splash_feedback_present=true
splash_status_path_safe=true
splash_does_not_chmod_tmp=true
pull_updater_present=true
pull_update_timer_enabled=true
seed_present=true
seed_permissions_ok=true
no_real_config_embedded=true
qa_generator_not_installed=true
docs_evidence_not_installed=true
c15_2_3_monitor_not_installed=true
c15_2_3_monitor_not_enabled=true
```

The generated image SHA256 is:

```text
e36b86004c75663fd4c3d14d8ed8b6186f102c8b644e7dbc4351ca734036dca9
```

## Clean Board Runtime

The operator manually flashed one clean board and completed the first F10 setup.
The wizard did not exit during configuration. The UI showed saving configuration
and then starting player. A transient black interval occurred while entering the
player after first setup, but SSH stayed available and playback later reported
`playing`.

Sanitized runtime collection after setup:

```text
image_marker_present=true
image_marker_version_ok=true
kiosky_player_active=active
networkmanager_active=active
ssh_active=active
visual_tty_guard_active=active
visual_tty_guard_enabled=enabled
settings_trigger_active=active
update_timer_active=active
update_timer_enabled=enabled
fgconsole=2
tty1_echo=false
tty2_echo=false
tmp_permissions=1777
seed_present=true
seed_permissions_ok=true
config_real_present=true
session_lock_present=false
mpv_present=true
kiosk_present=true
network_connected_after_writer=true
playback_state=playing
monitor_installed_default=false
monitor_service_present=false
totem_updatectl_executable=true
totem_updatectl_status_rc=0
totem_updatectl_status_ok=true
```

Session status after the first setup:

```text
session_status_found=true
wizard_rc=8
handoff_rc=0
writer_rc=0
writer_called=true
writer_result=passed
real_config_written=true
service_restore_attempted=true
service_active=active
public_state=player_running
playback=playing
setup_cancelled=false
visual_wizard_opened=true
visual_candidate_generated=true
```

One unrelated failed unit was observed:

```text
failed_units_count=1
failed_units_sanitized=console-setup.service
console_setup_result=exit-code
console_setup_detail=sanitized_setupcon_tmpkbd_missing
console_setup_blocking=false
```

The failed unit did not block F10, local keyboard input, SSH, NetworkManager,
player startup, or playback. It is recorded as a follow-up hygiene item, not as
a C15.2.4 blocker.

## Transient Black Interval

The operator observed a black screen for a while after the "Iniciando player"
splash. The board remained reachable by SSH and later reported:

```text
ssh_active_after_writer=true
network_connected_after_writer=true
player_restore_ok=true
playback_state_after_restore=playing
```

This is not the C15.2.2 failure mode because SSH did not drop and recovery was
not required. It is recorded as:

```text
post_wizard_black_screen_observed=true
post_wizard_black_screen_persistent=false
post_wizard_black_screen_detail=transient_first_player_start_or_media_wait
```

Player/startup behavior can now be opened in the next audit stage. No C16/player
work was started in this card.

## Decision

```text
ready_for_batch_flash=true
ready_for_dispatch=true
ready_for_c16_player_audit=true
c16_started=false
```

C15.2.4 proves the clean image no longer depends on manual hotfixes for the
wizard setup path. It is ready for controlled batch flash/private dispatch and
for opening the next player audit card.

## Commands Run

Local:

```text
git status --short
git log --oneline -200
git diff --check
bash -n scripts/board/totem_visual_tty_guard.sh
bash -n scripts/board/totem_firstboot_gate.sh
bash -n scripts/board/totem_open_settings_session.sh
bash -n scripts/board/kiosky_service_launcher.sh
bash -n scripts/build/run_c14_2_1_build_shipping_homolog_image.sh
bash -n scripts/remote/validate_c14_2_1_clean_board.sh
bash -n scripts/remote/c15_2_3_post_wizard_monitor.sh
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_updatectl.py self-test || true
python3 -m json.tool scripts/board/totem_appliance_manifest.json >/dev/null
python3 scripts/build/derive_c15_2_4_homolog_image.py --out-dir ... --image-tag c15-2-4-homolog-clean-board-fixes --image-version c15.2.4
lsblk -o NAME,PATH,RM,RO,SIZE,TYPE,FSTYPE,MOUNTPOINTS,MODEL,SERIAL,TRAN
```

Board:

```text
sanitized runtime collection after operator clean-board setup
/opt/totem/bin/totem-updatectl status
sanitized console-setup.service status collection
```

The local `totem_updatectl.py self-test` still returns the known non-appliance
permission error for `/data` in this host context and was intentionally run with
`|| true`.

## Prohibited Data

No SSH password, GitHub token, API key, real API URL, environment identifier,
SSID, Wi-Fi password, private seed contents, real config contents, NetworkManager
profiles, IP, MAC, DNS, raw logs, media cache, or private media were included in
this evidence.
