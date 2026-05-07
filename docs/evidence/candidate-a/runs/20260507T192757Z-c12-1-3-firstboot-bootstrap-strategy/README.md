# C12.1.3 - Firstboot Bootstrap Strategy

Data: 2026-05-07

## Resultado

- c12_3_2_blocked: `true`
- cause: `firstboot_bootstrap_missing_or_invalid`
- strategy_selected: `lab_autoconfig_required`
- boards_touched_by_this_round: `false`
- card_written_by_this_round: `false`
- secrets_published: `false`

## Observacao C12.3.2

- black_screen_seen: `true`
- f10_reached_raw_console: `true`
- ssh_available: `false`
- wifi_configured: `false`
- dadooh_ui_available: `false`
- wizard_freeze_classification: `not_applicable`

## Mudancas

- build_requires_private_lab_firstboot_for_board_validation: `true`
- firstboot_template_updated: `true`
- firstboot_gate_fallback_notice_added: `true`
- artifact_validation_requires_lab_autoconfig: `true`
- next_step: `C12.1.4 rebuild with lab autoconfig`

## Guardrails

- config_real_included: `false`
- writer_called: `false`
- wifi_changed: `false`
- read_only_post_install_attempted: `false`
- power_cut_tested: `false`
