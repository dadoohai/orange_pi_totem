# C17.8.1 Wizard UX Operation Model

c17_8_1_status=passed
hardware_available=false
orange_pi_available=false
board_accessed_via_ssh=false
card_written=false
image_built=false

wizard_flow_audited=true
navigation_contract_created=true
wizard_text_simplified=true
wizard_steps_reduced_or_justified=true
primary_actions_standardized=true
back_navigation_standardized=true
b_ctrl_b_removed_as_primary_instruction=true
input_replay_created=true
input_replay_scenarios_count=7
input_replay_passed=true
gallery_generated=true
png_render_available=false

footer_consistency_score=4.6
primary_action_clarity_score=4.5
back_action_clarity_score=4.5
critical_screens_below_4=false
operator_confusion_risk=medium

totem_core_package_needed=true
ready_for_c17_8_2_totem_core_package=true
ready_for_hardware_wizard_validation=true
ready_for_c18_player_work=true

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
c18_player_code_changed=false

## Artifacts

- `wizard-replay/trace.json`
- `wizard-replay/assertions.json`
- `wizard-replay/summary.json`
- `wizard-replay/summary.md`
- `wizard-replay/screens/*.svg`
- `ui-gallery/run-summary.json`
- `ui-gallery/ux-review-rubric.json`
- `ui-gallery/visual-metrics.json`
- `ui-gallery/gallery/*.svg`

## Replay Scenarios

- `happy_path_synthetic`: passed
- `back_navigation`: passed
- `environment_invalid_uuid`: passed
- `environment_edit_middle`: passed
- `wifi_wrong_password_fake`: passed
- `api_unavailable_fake`: passed
- `cancel_flow`: passed

## Validation

- `python3 scripts/sim/run_wizard_input_replay.py --out-dir /tmp/c17-8-1-wizard-replay`: passed
- `python3 scripts/qa/generate_ui_ux_gallery.py --out-dir /tmp/c17-8-1-ui-gallery`: passed
- `python3 scripts/board/totem_setup_visual_wizard.py --self-test`: passed

## Decision

C17.8.1 passed locally. The wizard now has a documented navigation contract,
shorter Enter/Esc-first footers, B/Ctrl+B removed from primary instructions,
real input replay and generated UX artifacts. Because runtime wizard files
changed, C17.8.2 should package this as a totem-core update before hardware
validation.
