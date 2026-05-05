# C10.6.1 - Persistent Settings Trigger Evidence

Date: 2026-05-05
Base commit under test: `0e7602e`
Working tree: C10.6.1 changes under validation

## Commands

```bash
git status --short
git log --oneline -10
git diff --check
bash -n scripts/remote/run_c10_6_open_settings_from_player.sh
bash -n scripts/remote/run_c10_6_1_persistent_settings_trigger.sh
python3 scripts/board/totem_settings_trigger.py --self-test
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
scripts/remote/run_c10_6_1_persistent_settings_trigger.sh <host> --prepare-only
scripts/remote/run_c10_6_1_persistent_settings_trigger.sh <host> --install-trigger
scripts/remote/run_c10_6_1_persistent_settings_trigger.sh <host> --run-human-f10
scripts/remote/run_c10_6_1_persistent_settings_trigger.sh <host> --status
scripts/remote/run_c10_6_1_persistent_settings_trigger.sh <host> --reboot-check
scripts/remote/run_c10_6_1_persistent_settings_trigger.sh <host> --status
scripts/remote/run_c10_6_1_persistent_settings_trigger.sh <host> --run-human-f10
```

## Result

- trigger_service_installed=true
- trigger_service_enabled=true
- trigger_service_active=true
- trigger_type=keyboard_f10_hold
- f10_hold_detected=true
- settings_opened=true
- cancel_returned_to_player=true
- reboot_check=true
- trigger_service_active_after_reboot=true
- trigger_service_enabled_after_reboot=true
- service_final=active/enabled
- NRestarts=0
- public_state=player_running
- playback=playing
- player=1
- MPV=1
- renderer=0
- setup=0
- writer_called=false
- real_config_read=false
- real_config_written=false
- wifi_changed=false
- networkmanager_changed=false

## Privacy

No config content, API credentials, environment identifier, Wi-Fi identifier,
password, IP, MAC, DNS, raw logs or typed keys were included in this evidence.

## Conclusion

The persistent service is installed and enabled. After controlled reboot, F10
long-press opened Configuracoes without the runner starting the settings
session, cancellation returned to the player, and final state remained healthy.
