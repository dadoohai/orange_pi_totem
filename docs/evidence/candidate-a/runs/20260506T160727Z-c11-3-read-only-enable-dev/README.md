# C11.3 read-only enablement dev evidence

Data: 2026-05-06

Commit sob teste: `a74c59b Apply C11.2 read-only mitigations`

## Comandos

- `scripts/remote/run_c11_3_read_only_enablement_dev.sh --prepare-only`
- `scripts/remote/run_c11_3_read_only_enablement_dev.sh root@<dev-board> --inspect`
- `scripts/remote/run_c11_3_read_only_enablement_dev.sh root@<dev-board> --dry-run-enable`

## Resultado

- dev_only: `true`
- test_board_touched: `false`
- mechanism_detected: `armbian_config_module_overlayfs`
- risk_level: `blocked_missing_overlayroot_package`
- package_install_required: `true`
- can_enable_without_package_install: `false`
- enable_executed: `false`
- reboot_executed: `false`
- power_cut_tested: `false`
- poweroff_executed: `false`
- writer_called: `false`
- real_config_read: `false`
- real_config_written: `false`
- wifi_changed: `false`
- networkmanager_profiles_changed: `false`
- packages_installed: `false`
- raw_logs_published: `false`
- secrets_published: `false`

## Read-only

- read_only_enabled: `false`
- overlay_active: `false`
- protected_root_write_blocked: `false`
- writable_paths_ok: `true`
- rollback_available: `false`
- ready_for_c11_4: `false`

## Estado Final

- service_final: `active/enabled`
- public_state: `player_running`
- playback: `playing`
- systemctl_failed_count: `0`

## Decisao

C11.3 nao habilitou root read-only porque o mecanismo oficial detectado exige
`overlayroot`, que nao esta presente. A rodada nao instalou pacotes por regra.

Proximo passo deve decidir entre:

- autorizar uma rodada especifica para instalar/aprovisionar `overlayroot` sem
  `apt upgrade`;
- ou gerar uma imagem base que ja contenha o mecanismo oficial;
- ou escolher outro mecanismo read-only/overlay com desenho separado.

## Proibido e Nao Incluido

Nao ha logs brutos, config real, API key, API URL real, environment_id, SSID,
senha, IP, MAC, DNS, gateway, hostname, nomes de perfil NetworkManager ou
payloads nesta evidencia.
