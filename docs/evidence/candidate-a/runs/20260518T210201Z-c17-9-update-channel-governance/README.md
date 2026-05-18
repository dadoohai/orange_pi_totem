# C17.9 update channel governance

c17_9_status=passed
hardware_available=false
orange_pi_available=false
board_accessed_via_ssh=false
card_written=false
image_built=false
github_release_published=false
remote_publish_skipped=true

update_channels_defined=true
device_channel_policy_defined=true
manifest_channel_contract_defined=true
default_device_channel=stable

totem_updatectl_channel_filtering=true
component_filtering_required=true
prerelease_policy_defined=true
draft_release_ignored=true
invalid_manifest_ignored=true
dry_run_supported=true

channel_policy_tests_created=true
channel_policy_tests_passed=true
channel_policy_tests_count=13
sandbox_channel_guard_tested=true

stable_device_blocks_lab=true
stable_device_blocks_homologation=true
stable_device_accepts_stable=true
component_cross_apply_blocked=true

ready_for_c18_3_player_rc_package=true
ready_for_totem_core_publish=false
hardware_homologation_required=true

Guardrails:
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

## Results

Policy: exact-channel only.

- `stable` accepts only `stable` and rejects prerelease.
- `homologation` accepts only `homologation`; prerelease must be allowed by
  policy.
- `lab` accepts only `lab`; prerelease must be allowed by policy.

Updater changes:

- `channel` is now a required manifest field.
- `/data/updates/policy.json` defines device channel policy.
- Missing/invalid policy fails closed to stable.
- GitHub selection ignores drafts, incompatible prereleases, wrong component,
  invalid manifests and incompatible channels.
- `list-github --dry-run` and `apply-github-latest --dry-run` are available for
  safe selection checks.

Sandbox:

- `apply_local_passed=true`
- `rollback_passed=true`
- `wrapper_fallback_passed=true`
- `settings_lock_guard_passed=true`
- `channel_guard_incompatible_blocked=true`
- `writes_outside_sim_detected=false`

No GitHub Release, tag, board apply, card write, SSH, image build, apt or pip
operation was performed.
