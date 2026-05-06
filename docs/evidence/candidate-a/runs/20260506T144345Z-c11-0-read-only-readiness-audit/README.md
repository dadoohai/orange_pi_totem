# C11.0 - Read-only Readiness Audit

Data: 2026-05-06

Commit em teste: `258ebf7 Add C10.10.2 shutdown UX`.

## Comandos

```bash
git fetch origin
git checkout foundation-v0.1
git pull origin foundation-v0.1
git status --short
git log --oneline -30
git diff --check

bash -n scripts/board/install_totem_appliance.sh
bash -n scripts/board/verify_totem_appliance.sh
python3 -m json.tool scripts/board/totem_appliance_manifest.json
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test

scripts/remote/run_c11_0_read_only_readiness_audit.sh <dev-board> --prepare-only
scripts/remote/run_c11_0_read_only_readiness_audit.sh <dev-board> --audit-dev
scripts/remote/run_c11_0_read_only_readiness_audit.sh <dev-board> --summary
```

## Resultado Dev

- audit_altered_board: `false`
- read_only_enabled: `false`
- poweroff_executed: `false`
- reboot_executed: `false`
- writer_called: `false`
- real_config_read: `false`
- real_config_written: `false`
- wifi_changed: `false`
- packages_installed: `false`
- raw_logs_published: `false`
- public_state: `player_running`
- playback: `playing`
- services_active_enabled: `true`
- NRestarts: `0`
- systemctl_failed_count: `0`
- root_read_only_ready: `false`
- ready_for_read_only_enablement: `false`
- ready_for_c11_1_policy: `true`

## Classificacao

- `NEEDS_DATA_PATH`: `9`
- `NEEDS_TMP_PATH`: `2`
- `OK_FOR_READ_ONLY`: `1`
- `NEEDS_ETC_EXCEPTION`: `2`
- `NEEDS_NETWORKMANAGER_POLICY`: `1`
- `NEEDS_LOG_POLICY`: `1`
- `NEEDS_VAR_POLICY`: `2`

## Blockers

- NetworkManager policy para perfis Wi-Fi em `/etc/NetworkManager/system-connections`.
- Journald/log policy com `/var/log/journal` presente.

## Decisao

C11.0 nao libera enablement de root read-only. C11.1 pode iniciar como rodada
de politica/mitigacao para NetworkManager, journald/logs e excecoes `/var`,
`/etc` e `/boot`.

## Privacidade

Este README nao inclui config real, secrets, SSID, senha, IP, MAC, DNS,
gateway, hostname, payloads ou logs brutos.
