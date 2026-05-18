# C18.2 Player Duration Normalization

c18_2_status=passed
duration_contract_defined=true
canonical_duration_field=exposure_time_ms
aliases_supported=exposureTimeMs,exposureTimeSeconds
duration_field_supported=false
duration_field_policy=ignored_due_to_ambiguity
default_duration_overrides_api=false
duration_source_tracked=true

short_video_policy=repeat_to_fill_exposure
short_video_loop_intentional=true
mpv_loop_file_policy_documented=true

tests_added=true
tests_passed=true
player_code_changed=true
scheduler_changed=false
sync_changed=false
playlist_logic_changed=false
loop_changed=false
duration_changed=true

ready_for_c18_3_release_package=true
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

- `python3 -m py_compile kiosk.py tests/test_player_timing_simulation.py tests/fakes/player_simulation.py`
- `python3 -m unittest tests/test_player_timing_simulation.py`
- `python3 -m unittest discover -s tests`

## Scenario Results

- `image_respects_exposure_time_ms`: passed
- `video_shorter_than_exposure_policy_is_mpv_loop_until_window`: passed
- `missing_exposure_uses_default`: passed
- `exposure_time_ms_has_priority_over_aliases`: passed
- `exposure_time_ms_default_does_not_override_api_value`: passed
- `exposure_time_ms_alias_is_used`: passed
- `duration_source_is_propagated_to_downloaded_media_item`: passed
- `exposure_time_seconds_alias_is_converted_to_ms`: passed
- `invalid_duration_values_fall_back_to_default`: passed
- `ambiguous_duration_field_is_ignored`: passed
- `single_item_playlist_repeat_is_expected_cycle_behavior`: passed
- `multi_item_playlist_advances`: passed
- `api_empty_playlist_sets_waiting_for_media`: passed
- `api_timeout_does_not_crash_and_sets_safe_status`: passed
- `media_load_failure_advances_or_errors_cleanly`: passed
- `mpv_loop_flags_do_not_force_playlist_loop`: passed
- `sync_resync_does_not_restart_same_item_when_drift_is_stable`: passed

## Decision

C18.2 passed locally. The player now normalizes `exposure_time_ms`,
`exposureTimeMs` and `exposureTimeSeconds`, ignores ambiguous `duration`, tracks
the selected duration source and keeps short-video repeat inside the exposure
window as the documented policy. C18.3 can prepare a release package, while
Orange Pi hardware validation remains mandatory before production confidence.
