# C18.1 Player Timing Sync Loop Simulation Audit

c18_1_status=audit_only
hardware_available=false
orange_pi_available=false
board_accessed_via_ssh=false
card_written=false
image_built=false

player_model_mapped=true
api_payload_fields_mapped=true
duration_fields_mapped=true
playlist_model_mapped=true
mpv_commands_mapped=true
sync_model_mapped=true
status_model_mapped=true

fake_api_created=true
fake_mpv_created=true
fake_clock_created=true
unit_tests_added=true
unit_tests_passed=true
simulation_scenarios_count=11

timing_semantics_status=default_duration_overrides_api
looping_cause=mpv_loop_file
player_sim_confidence=high

player_code_changed=false
instrumentation_added=false
scheduler_changed=false
sync_changed=false
duration_changed=false
loop_changed=false
playlist_logic_changed=false

ready_for_c18_2_fix=true
ready_for_hardware_player_validation=true

## Guardrails

secrets_published=false
api_key_published=false
api_url_published=false
environment_id_published=false
ssid_published=false
wifi_password_published=false
media_urls_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
ssh_used=false
board_touched=false
kernel_touched=false
read_only_touched=false
writer_called=false
real_config_written=false
poweroff_executed=false
power_cut_tested=false
c12_readonly_blocked=true
c12_4_blocked=true

## Test Commands

- `python3 -m py_compile kiosk.py`
- `python3 -m unittest tests/test_player_timing_simulation.py`
- `python3 -m py_compile kiosk.py tests/test_player_timing_simulation.py tests/fakes/player_simulation.py`
- `python3 -m unittest discover -s tests`

## Scenario Results

- `image_respects_exposure_time_ms`: passed
- `video_shorter_than_exposure_policy_is_mpv_loop_until_window`: passed
- `missing_exposure_uses_default`: passed
- `camel_case_duration_fields_are_ignored_by_current_parser`: passed
- `single_item_playlist_repeat_is_expected_cycle_behavior`: passed
- `multi_item_playlist_advances`: passed
- `api_empty_playlist_sets_waiting_for_media`: passed
- `api_timeout_does_not_crash_and_sets_safe_status`: passed
- `media_load_failure_advances_or_errors_cleanly`: passed
- `mpv_loop_flags_do_not_force_playlist_loop`: passed
- `sync_resync_does_not_restart_same_item_when_drift_is_stable`: passed

## Decision

C18.1 produced a useful local simulation audit without changing player
production behavior. C18.2 should decide and implement targeted semantics for
duration field aliases and short-video loop policy before any kiosky-player
release.
