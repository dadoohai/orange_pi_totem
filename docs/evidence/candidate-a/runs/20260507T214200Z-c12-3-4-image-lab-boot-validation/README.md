# C12.3.4 - Image-Lab Boot Validation

Data: 2026-05-07

## Escopo

- image_version: `c12.1.6`
- host: `test_board_redacted`
- boot_success: `true`
- ssh_available: `true`
- password_published: `false`
- secrets_published: `false`
- raw_logs_published: `false`
- poweroff_executed: `false`
- reboot_executed: `false`
- writer_called_by_runner: `false`
- config_real_written_by_runner: `false`
- wifi_changed_by_runner: `false`

## Firstboot

- firstboot_marker_present: `false`
- lab_firstboot_marker_present: `true`
- lab_bootstrap_status_present: `true`
- lab_bootstrap_state: `complete`
- lab_bootstrap_marker_removed: `true`
- lab_bootstrap_network_apply_attempted: `true`
- private_firstboot_data_published: `false`

## Read-only

- read_only_enabled: `false`
- overlay_active: `false`
- root_fstype: `ext4`
- root_write_blocked: `false`
- data_writable: `true`
- tmp_writable: `true`
- run_writable: `true`
- journald_volatile: `true`

Classificacao:

```text
IMAGE_LAB_READ_ONLY_NOT_ACTIVE
```

## Produto

- public_state: `config_missing`
- playback: `unknown`
- config_real_present: `false`
- config_missing_visual_ok: `true`
- stuck_starting_player: `false`
- shell_seen: `unknown`
- orientation_json_present: `true`

Processos:

- player: `0`
- MPV: `1`
- renderer: `1`
- setup: `0`

Servicos:

- kiosky-player.service: `active/enabled`
- totem-settings-trigger.service: `active/enabled`
- totem-open-settings.service: `inactive/static`
- totem-firstboot-gate.service: `inactive/enabled`
- totem-lab-firstboot-autoconfig.service: `inactive/enabled`
- systemctl_failed_count: `1`
- failed_unit_category: `console_setup`

## Wizard

- f10_opened_settings_observed_by_human: `true`
- f10_cancel_result: `not_executed_in_runner`
- session_status_present: `true`
- apply_mode: `candidate-only`
- visual_wizard_opened: `true`
- visual_candidate_generated: `true`
- setup_cancelled: `false`
- writer_called: `false`
- real_config_written: `false`
- candidate_files_count: `1`
- session_lock_present: `false`
- request_present: `false`

Classificacao:

```text
CANDIDATE_ONLY_EXPECTED_WITHOUT_PRIVATE_VALUES
UX_AMBIGUOUS_CANDIDATE_ONLY
```

## Decisao

- ready_for_c12_4: `false`
- next_recommended_step: `C12.1.7`

Motivo: a imagem C12.1.6 resolveu firstboot/bootstrap e candidate-only foi
classificado, mas root read-only/overlay continua inativo no boot.
