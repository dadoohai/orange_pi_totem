# C12.3.5 Boot Read-only Wizard Classification

Data: 2026-05-07

## Escopo

Validacao diagnostica da imagem-lab C12.1.8 em placa de bancada. O host foi
tratado como lab host sanitizado; nenhum IP, segredo, config real, SSID, senha
ou log bruto foi publicado.

## Resultado

- image_version: `c12.1.8`
- boot_success: `true`
- ssh_available: `true`
- lab_bootstrap_state: `complete`
- firstboot_marker_present: `false`
- public_state: `config_missing`
- config_real_present: `false`
- config_missing_visual_ok: `true`

## Read-only

- overlayroot_config_present: `true`
- overlayroot_value_category: `tmpfs`
- boot_script_uses_uinitrd: `true`
- initrd_marker_c12_1_8_visible: `true`
- initrd_overlayroot_hook_visible: `true`
- initrd_overlay_module_visible: `true`
- read_only_enabled: `false`
- overlay_active: `false`
- root_write_blocked: `false`
- root_fstype: `ext4`
- data_tmp_run_writable: `true`
- journald_volatile: `true`

Classificacao:

```text
IMAGE_LAB_READ_ONLY_NOT_ACTIVE
```

## Wizard

- candidate_generated: `true`
- candidate_files_count: `1`
- writer_called: `false`
- real_config_written: `false`
- c5_1_allow_mock_passed: `true`
- c5_1_real_dry_run_executed: `false`
- real_dry_run_failure_reason: `not_run`
- final_state_after_wizard: `config_missing`

Classificacao:

```text
CANDIDATE_ONLY_EXPECTED_WITHOUT_PRIVATE_VALUES
UX_AMBIGUOUS_CANDIDATE_ONLY
```

## Servicos

- kiosky_player_service: `active/enabled`
- totem_settings_trigger_service: `active/enabled`
- totem_open_settings_service: `inactive/static/result_success`
- totem_firstboot_gate_service: `inactive/enabled/result_success`
- systemctl_failed_count: `1`
- systemctl_failed_categories: `console_setup`

## Guardrails

- writer_invoked_by_runner: `false`
- real_config_changed_by_runner: `false`
- wifi_changed_by_runner: `false`
- packages_installed_by_runner: `false`
- reboot_executed: `false`
- poweroff_executed: `false`
- secrets_published: `false`
- raw_logs_published: `false`

## Decisao

C12.4 permanece bloqueado. O comportamento do wizard e esperado para
candidate-only sem private-values, mas a UX ainda e ambigua. O blocker principal
e read-only/overlay nao ativo.
