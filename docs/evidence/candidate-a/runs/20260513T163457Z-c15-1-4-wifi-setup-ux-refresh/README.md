# C15.1.4 - Wi-Fi setup UX refresh

Date: 2026-05-13
Branch: `foundation-v0.1`

## Required Fields

```text
c15_1_4_status=passed
board_accessed_via_ssh=true
secrets_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
poweroff_executed=false
power_cut_tested=false
read_only_touched=false
kernel_touched=false
wifi_real_changed=true
networkmanager_touched_only_by_wizard=true
player_code_changed=false
c16_started=false
c12_readonly_blocked=true
c12_4_blocked=true

wifi_ux:
- paginated_wifi_list=true
- wifi_refresh_interval_sec=10
- wifi_auto_refresh=true
- wifi_manual_refresh_key=R
- wifi_sorted_by_signal=true
- signal_strength_visible=true
- signal_percent_visible=true
- signal_bars_visible=true
- signal_bucket_visible=true
- duplicate_ssid_grouping=true
- selected_network_preserved_on_refresh=true
- password_hidden_by_default=true
- password_show_toggle_available=true
- password_show_toggle_key=F2/V
- password_written_to_public_artifacts=false
- ssid_written_to_public_artifacts=false
- bssid_mac_ip_dns_visible=false

tests:
- wizard_self_test_passed=true
- adapter_self_test_passed=true
- preview_generated=true
- physical_wifi_screen_tested=true
- physical_password_toggle_tested=true

ready_for_image_rebuild=true
ready_for_c16_player_audit=true
```

## Sanitized Validation

Local validation:

```text
python3 -m py_compile scripts/board/totem_setup_visual_wizard.py scripts/board/totem_wifi_nm_adapter.py: passed
python3 scripts/board/totem_setup_visual_wizard.py --self-test: passed
python3 scripts/board/totem_wifi_nm_adapter.py --self-test: passed
python3 -m json.tool scripts/board/totem_appliance_manifest.json: passed
python3 scripts/board/totem_setup_visual_wizard.py --wifi-list-preview: passed
preview_status_sanitized=true
```

Board hotfix validation:

```text
hotfix_applied_to_board=true
board_wizard_self_test_passed=true
board_adapter_self_test_passed=true
preview_screen_count=6
preview_status_sanitized=true
```

Physical wizard validation:

```text
wifi_pages_observed=2
wifi_network_count_observed=10
signal_percent_visible=true
password_toggle_initial_f2_only_failed=true
password_toggle_f2_v_hotfix_applied=true
password_toggle_retest_passed=true
terminal_login_visible=false
keyboard_echo_visible=false
config_missing_returns_during_wizard=false
trace_available=true
trace_openvt_exited=true
trace_trap_signal=false
session_lock_cleanup_ok=true
player_restore_ok=true
totem_open_settings_final=inactive
kiosky_player_final=active
```

Real Wi-Fi apply happened only through the normal local wizard flow:

```text
wifi_apply_attempted=true
wifi_apply_result=passed
wifi_activation_result=success
network_changed=true
writer_called=true
writer_rc=0
writer_result=passed
real_config_written=true
backup_created=true
config_real_present=true
```

No SSID, Wi-Fi password, BSSID, MAC, IP, DNS, API value, token, private seed, real config content, raw logs, media, or cache content is included here.

## Notes

The operator also observed two legacy UX issues outside this C15.1.4 acceptance scope:

- the wizard screen is text-heavy;
- holding Backspace can queue repeated screen redraws and blink until the key repeat backlog drains.

Those were not treated as C15.1.4 blockers because the requested Wi-Fi list, signal clarity, refresh, and password visibility controls passed after the F2/V hotfix.
