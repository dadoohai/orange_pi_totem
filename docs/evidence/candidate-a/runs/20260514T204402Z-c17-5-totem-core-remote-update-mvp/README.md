# C17.5 Totem-Core Remote Update MVP

c17_5_status=passed
totem_core_component_defined=true
totem_core_layout_created=true
totem_core_wrappers_created=true
totem_core_fallback_available=true
totem_updatectl_multi_component=true
totem_core_package_built=true
totem_core_manifest_created=true
totem_core_payload_sha256_valid=true
totem_core_release_published=true
totem_core_apply_remote_tested=true
totem_core_apply_local_tested=true
totem_core_rollback_tested=true

board_bootstrap_applied=true
board_accessed_via_ssh=true
settings_lock_guard_enforced=true
apply_blocked_when_settings_active=true
wizard_uses_data_current=true
wizard_fallback_to_opt_tested=true
f10_after_bootstrap_passed=true
physical_f10_keypress_tested=false
settings_preview_session_passed=true

ready_for_c17_6_environment_input_update=true
ready_for_c18_player_audit=false

package_version=c17.5-core-mvp-20260514T204200Z
payload_sha256=8a7724382b1c786caaf957d90bf35d79271cb777352ddc23993a0d0df72843e2
github_release_tag=totem-core-c17.5-core-mvp-20260514T204200Z
github_release_published=true
superseded_package_version=c17.5-core-mvp-20260514T202900Z
superseded_reason=splash_self_test_expected_old_config_pending_index

## Validation Notes

The C17.5 updater reused schema `dadooh.totem.update.v1` with
`component=totem-core`.

The board was booted from the already validated C17.4.2 image. Bootstrap
installed:

- `/opt/totem/core-fallback/bin`;
- wrappers in `/opt/totem/bin`;
- `/data/core/totem/releases`;
- multi-component `totem-updatectl`.

Remote GitHub release apply passed. Rollback to fallback passed. The same good
release was reapplied so the final board state uses
`/data/core/totem/current/bin`.

The settings lock guard was tested with a synthetic lock path and blocked apply
with return code 40 before payload activation.

The wizard path was validated through a short settings preview session:

- `visual_wizard_opened=true`;
- `writer_called=false`;
- `real_config_written=false`;
- `service_active=active`;
- `playback=playing`.

No real config contents, SSID, Wi-Fi password, IP, MAC, DNS, token, private seed
or NetworkManager profile was read or published.

## Guardrails

secrets_published=false
api_key_published=false
api_url_published=false
environment_id_published=false
ssid_published=false
wifi_password_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
read_only_touched=false
kernel_touched=false
wifi_real_changed=false
networkmanager_touched=false
writer_called=false
real_config_written=false
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
