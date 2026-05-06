# C11.1 read-only policy mitigation evidence

Data: 2026-05-06

Commit sob teste: `35f8439 Add C11.0 read-only readiness audit`

## Comandos

- `scripts/remote/run_c11_1_read_only_policy_probe.sh --prepare-only`
- `scripts/remote/run_c11_1_read_only_policy_probe.sh root@<dev-board> --probe-dev`
- `scripts/remote/run_c11_1_read_only_policy_probe.sh --summary`

## Resultado

- dev_probe_passed: `true`
- test_board_touched: `false`
- read_only_enabled: `false`
- poweroff_executed: `false`
- reboot_executed: `false`
- writer_called: `false`
- real_config_read: `false`
- real_config_written: `false`
- wifi_changed: `false`
- networkmanager_changed: `false`
- packages_installed: `false`
- raw_logs_published: `false`
- secrets_published: `false`

## Politicas

- networkmanager_policy: `nm_profiles_maintenance_window`
- journald_policy: `journald_volatile_product_logs_data`
- boot_policy: `boot_guardrails_maintenance_only`
- etc_policy: `etc_installer_maintenance_only`
- var_policy: `volatile_or_overlay_runtime_state_to_validate_in_c11_2`

## Readiness

- root_read_only_ready: `false`
- ready_for_read_only_enablement: `false`
- ready_for_c11_2_enablement: `true`
- blockers_remaining: `0`

## Estado Dev

- service_final: `active/enabled`
- NRestarts: `0`
- public_state: `player_running`
- playback: `playing`
- systemctl_failed_count: `0`

## Proibido e Nao Incluido

Nao ha config real, API key, API URL real, environment_id, SSID, senha, IP,
MAC, DNS, gateway, hostname, nomes de perfil NetworkManager, logs brutos ou
payloads nesta evidencia.
