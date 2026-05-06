# C10.10.2 - Shutdown UX

Data: 2026-05-06

Commit em teste: `b5b5d7c` mais patch local C10.10.2 ainda nao commitado.

## Comandos

```bash
git status --short
git log --oneline -25
git diff --check
bash -n scripts/board/install_totem_appliance.sh
bash -n scripts/board/verify_totem_appliance.sh
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test

scripts/remote/run_c10_10_2_shutdown_ux.sh <dev-board> --prepare-only
scripts/remote/run_c10_10_2_shutdown_ux.sh <dev-board> --inspect
scripts/remote/run_c10_10_2_shutdown_ux.sh <dev-board> --preview-shutdown-screen
scripts/remote/run_c10_10_2_shutdown_ux.sh <dev-board> --simulate-shutdown-flow-no-poweroff
scripts/remote/run_c10_10_2_shutdown_ux.sh <dev-board> --apply-dev
scripts/remote/run_c10_10_2_shutdown_ux.sh <dev-board> --simulate-shutdown-flow-no-poweroff

scripts/remote/run_c10_10_2_shutdown_ux.sh <test-board> --prepare-only
scripts/remote/run_c10_10_2_shutdown_ux.sh <test-board> --inspect
scripts/remote/run_c10_10_2_shutdown_ux.sh <test-board> --apply-test-refresh
scripts/remote/run_c10_10_2_shutdown_ux.sh <test-board> --preview-shutdown-screen
scripts/remote/run_c10_10_2_shutdown_ux.sh <test-board> --simulate-shutdown-flow-no-poweroff
```

## Resultado

- dev_preview_passed: `true`
- test_preview_passed: `true`
- poweroff_executed: `false`
- message_mentions_power_cycle: `true`
- reboot_vs_shutdown_documented: `true`
- shutdown_screen_rendered: `true`
- dev_final_service: `active/enabled`
- test_final_service: `active/enabled`
- dev_public_state: `player_running`
- test_public_state: `player_running`
- dev_playback: `playing`
- test_playback: `playing`
- dev_NRestarts: `0`
- test_NRestarts: `0`
- dev_player_mpv_active: `true`
- test_player_mpv_active: `true`
- renderer_setup_absent_final: `true`
- config_real_changed: `false`
- writer_called: `false`
- wifi_changed: `false`
- packages_installed: `false`
- read_only_enabled: `false`
- power_cut_tested: `false`

## Observacao

A primeira tentativa na segunda placa ficou bloqueada porque o HDMI estava
desconectado e o estado publico era `display_missing`. Depois de reconectar
HDMI, a validacao passou com display conectado e retorno para `player_running`.

## Privacidade

Este README nao inclui config real, secrets, SSID, senha, IP, MAC, DNS,
gateway, hostname, payloads ou logs brutos.
