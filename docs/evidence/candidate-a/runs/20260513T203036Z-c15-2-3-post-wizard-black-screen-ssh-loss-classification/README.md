# C15.2.3 - Post-wizard black-screen and SSH-loss classification

Run identifier: `20260513T203036Z-c15-2-3-post-wizard-black-screen-ssh-loss-classification`

## Status

```text
c15_2_3_status=passed
image_under_test=c15.2.1
previous_c15_2_2_service_timeout_fixed=true
previous_password_toggle_fixed=true

monitor_persistent_enabled=true
monitor_path=/data/state/totem-debug/c15-2-3/<20260513T202657Z-pid4113>
monitor_duration_sec=600
monitor_sample_count=329
post_wizard_failure_reproduced=false
ssh_lost_after_writer=false
hdmi_black_after_writer=false
emergency_physical_power_cycle_recovery=false
planned_power_cut_tested=false
c12_4_power_cut_tested=false

post_wizard_failure_cause=not_reproduced_in_monitored_retest
network_connected_before_writer=true
network_connected_after_writer=true
ssh_active_before_writer=true
ssh_active_after_writer=true
player_restore_done=true
public_state_after_restore=player_running
playback_state_after_restore=playing
mpv_present_after_restore=true
boot_id_changed=false
system_rebooted_spontaneously=false
oom_detected=false
kernel_panic_detected=false

hotfix_applied_to_board=true
hotfix_applied_to_repo=true
retest_after_hotfix_passed=true

ready_for_image_rebuild=true
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c16_player_audit=false
```

## Guardrails

```text
secrets_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
read_only_touched=false
kernel_touched=false
wifi_real_changed=false
networkmanager_touched_only_by_wizard=false
player_code_changed=false
c16_started=false
c12_readonly_blocked=true
c12_4_blocked=true
```

## Current State Before Reproduction

After the emergency recovery from C15.2.2, the board was reachable and stable:

```text
kiosky_player_active=active
networkmanager_active=active
ssh_active=active
visual_tty_guard_active=active
settings_trigger_active=active
update_timer_active=active
failed_units_count=0
config_real_present=true
session_lock_present=false
mpv_process_present=true
kiosk_process_present=true
network_connected_category=true
ip_connected_present=true
tmp_permissions=1777
data_writable=true
disk_free_category=used_lt_70pct
memory_free_category=free_ge_512mb
```

The only recent kernel log match in the sanitized check was normal watchdog
enablement during boot. No OOM or panic event was detected.

## Instrumentation

A persistent monitor was added and installed temporarily on the board:

```text
scripts/remote/c15_2_3_post_wizard_monitor.sh
```

It writes sanitized state to:

```text
/data/state/totem-debug/c15-2-3/<run-id>/
```

Files produced:

```text
monitor.log
phases.log
systemd-state.log
network-state.log
player-state.log
final-summary.json
```

The monitor records booleans/categories only. It does not read real config,
private seed, NetworkManager profiles, SSID, Wi-Fi password, IP, MAC, or DNS.

The settings session and visual wizard were instrumented to append sanitized
phase markers when the C15.2.3 monitor is active:

```text
wizard_started
wifi_step_entered
environment_input_entered
writer_start
writer_done
writer_result
session_cleanup_start
player_restore_start
player_restore_done
post_restore_t+5s
post_restore_t+15s
post_restore_t+30s
session_done
```

## Monitored Retest

The operator opened F10 and completed the wizard with the monitor active. The
operator reported that the flow appeared OK.

Sanitized phase evidence:

```text
wizard_started=true
wifi_step_entered=true
environment_input_entered=true
writer_start=true
writer_done=true
writer_result=0
player_restore_start=true
player_restore_done=true
post_restore_t+5s=active_playing
post_restore_t+15s=active_playing
post_restore_t+30s=active_playing
session_done=true
```

Runtime state after the retest:

```text
ssh_alive=true
kiosky_player_active=active
networkmanager_active=active
ssh_active=active
open_settings_active=inactive
settings_trigger_active=active
failed_units_count=0
session_lock_present=false
mpv_present=true
kiosk_present=true
playback_state=playing
```

Session status after the retest:

```text
wizard_rc=8
handoff_rc=0
writer_rc=0
writer_called=true
writer_result=passed
real_config_written=true
backup_created=true
service_restore_attempted=true
service_active=active
public_state=player_running
playback=playing
setup_cancelled=false
```

The monitor showed NetworkManager and SSH remained active before and after the
writer. The boot id did not change, so there was no spontaneous reboot observed.
The monitor finished normally:

```text
monitor_stopped_reason=normal_timeout
monitor_sample_count=329
config_read=false
seed_read=false
network_profiles_read=false
ip_mac_dns_logged=false
ssid_logged=false
wifi_password_logged=false
```

## Classification

The C15.2.2 post-wizard black-screen/SSH-loss window was not reproduced under
persistent monitoring.

```text
post_wizard_failure_cause=not_reproduced_in_monitored_retest
monitor_last_timestamp=post_restore_t+30s_and_session_done_observed
monitor_stopped_reason=normal_timeout
monitor_finished=true
network_connected_before_writer=true
network_connected_after_writer=true
ssh_active_before_writer=true
ssh_active_after_writer=true
player_restore_done=true
player_public_state_after_restore=player_running
playback_state_after_restore=playing
mpv_present_after_restore=true
system_rebooted_spontaneously=false
boot_id_changed=false
oom_detected=false
kernel_panic_detected=false
```

No corrective change was made to player code, NetworkManager, kernel, bootloader,
read-only state, or power behavior. The only code changes in this card are
diagnostic instrumentation and the C15.2.2 evidence nomenclature correction.

## Decision

```text
ready_for_image_rebuild=true
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c16_player_audit=false
```

C15.2.3 releases a new image rebuild attempt because the post-wizard failure was
not reproduced in a monitored retest and the previous C15.2.2 bugs are already
fixed. Batch flash, dispatch, and C16 remain blocked until a rebuilt image passes
clean-board validation.

## Commands Run

Local:

```text
git status --short
git log --oneline -180
git diff --check
bash -n scripts/board/totem_visual_tty_guard.sh
bash -n scripts/board/totem_firstboot_gate.sh
bash -n scripts/board/totem_open_settings_session.sh
bash -n scripts/board/kiosky_service_launcher.sh
bash -n scripts/build/run_c14_2_1_build_shipping_homolog_image.sh
bash -n scripts/remote/validate_c14_2_1_clean_board.sh
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_updatectl.py self-test || true
python3 -m json.tool scripts/board/totem_appliance_manifest.json >/dev/null
bash -n scripts/remote/c15_2_3_post_wizard_monitor.sh
python3 -m py_compile scripts/board/totem_setup_visual_wizard.py
```

Board:

```text
sanitized current-state collection
install C15.2.3 monitor/session/wizard instrumentation
bash -n /opt/totem/bin/c15_2_3_post_wizard_monitor.sh
bash -n /opt/totem/bin/totem_open_settings_session.sh
python3 /opt/totem/bin/totem_setup_visual_wizard.py --self-test
systemctl daemon-reload
start persistent monitor
clear /tmp/c15-session.trace
operator F10 wizard retest
sanitized monitor/status collection
```

The local `totem_updatectl.py self-test` still returns the known non-appliance
permission error for `/data` in this host context and was intentionally run with
`|| true`.

## Prohibited Data

No SSH password, GitHub token, API key, real API URL, environment identifier,
SSID, Wi-Fi password, private seed contents, real config contents, NetworkManager
profiles, IP, MAC, DNS, raw logs, media cache, or private media were included in
this evidence.
