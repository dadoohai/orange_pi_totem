# C17.8 Simulation Lab MVP

c17_8_status=passed
hardware_available=false
orange_pi_available=false
board_accessed_via_ssh=false
card_written=false
image_built=false

c17_7_status=offline_passed_hardware_unvalidated
c17_7_hardware_validation_required=true

boot_artifact_diff_created=true
boot_risk_level=low

sim_sandbox_created=true
sim_sandbox_mode=repo_overlay
totem_core_sandbox_tested=true
totem_core_apply_local_passed=true
totem_core_rollback_passed=true
totem_core_fallback_passed=true
totem_core_settings_lock_guard_passed=true

simulation_coverage_matrix_created=true
wizard_input_replay_stub_created=true
player_fake_mpv_api_stub_created=true

ready_for_c17_8_1_wizard_replay=true
ready_for_c18_1_player_sim_audit=true
hardware_homologation_required=true

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
c18_started=false

## Outputs

- `boot-artifact-diff.json`
- `totem-core-sandbox.json`

## Decision

The local simulation methodology is worth continuing. C17.7 remains
offline-passed/hardware-unvalidated and still requires Orange Pi clean-card
homologation before batch, dispatch or C18.
