# C11.2 read-only mitigation apply evidence

Data: 2026-05-06

Commit sob teste: `a73b7fe Add C11.1 read-only policy plan`

## Comandos

- `scripts/remote/run_c11_2_read_only_mitigation_apply.sh --prepare-only`
- `scripts/remote/run_c11_2_read_only_mitigation_apply.sh root@<dev-board> --inspect`
- `scripts/remote/run_c11_2_read_only_mitigation_apply.sh root@<dev-board> --dry-run`
- `scripts/remote/run_c11_2_read_only_mitigation_apply.sh root@<dev-board> --apply-dev --confirm "<confirmation>"`
- `scripts/remote/run_c11_2_read_only_mitigation_apply.sh root@<dev-board> --verify`
- `scripts/remote/run_c11_2_read_only_mitigation_apply.sh root@<dev-board> --reboot-check --confirm "<confirmation>"`

## Escopo

- dev_only: `true`
- test_board_touched: `false`
- read_only_enabled: `false`
- power_cut_tested: `false`
- poweroff_executed: `false`
- reboot_executed: `true`
- writer_called: `false`
- real_config_read: `false`
- real_config_written: `false`
- wifi_changed: `false`
- networkmanager_profiles_changed: `false`
- packages_installed: `false`
- raw_logs_published: `false`
- secrets_published: `false`

## Mitigacoes

- journald_policy: `volatile`
- journald_dropin_present: `true`
- var_policy: `runtime_state_policy_recorded`
- networkmanager_policy: `maintenance_window_policy_recorded`
- boot_etc_policy: `installer_maintenance_only_policy_recorded`
- backups_created: `true`
- rollback_available: `true`
- apply_executed: `true`

## Resultado Pos-Reboot

- root_read_only_ready: `false`
- ready_for_read_only_enablement: `false`
- ready_for_c11_3_enablement: `true`
- service_final: `active/enabled`
- NRestarts: `0`
- public_state: `player_running`
- playback: `playing`
- systemctl_failed_count: `0`

## Proibido e Nao Incluido

Nao ha logs brutos, config real, API key, API URL real, environment_id, SSID,
senha, IP, MAC, DNS, gateway, hostname, nomes de perfil NetworkManager ou
payloads nesta evidencia.
