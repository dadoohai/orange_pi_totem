# C10.6.2 - Apply settings from F10

Date: 2026-05-05

Commit under test: `ae6c658` plus local C10.6.2 patch.

## Commands

```bash
git status --short
git log --oneline -12
git diff --check
bash -n scripts/remote/run_c10_6_1_persistent_settings_trigger.sh
python3 scripts/board/totem_settings_trigger.py --self-test
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_visual_setup_writer_handoff.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
scripts/remote/run_c10_6_2_apply_settings_from_f10.sh root@192.168.1.147 --prepare-only
scripts/remote/run_c10_6_2_apply_settings_from_f10.sh root@192.168.1.147 --diagnose-current-flow
scripts/remote/run_c10_6_2_apply_settings_from_f10.sh root@192.168.1.147 --run-f10-cancel
scripts/remote/run_c10_6_2_apply_settings_from_f10.sh root@192.168.1.147 --run-f10-apply-dry-run
scripts/remote/run_c10_6_2_apply_settings_from_f10.sh root@192.168.1.147 --run-f10-apply-real
scripts/remote/run_c10_6_2_apply_settings_from_f10.sh root@192.168.1.147 --verify-orientation-propagation
```

## Results

- `f10_opened_settings=true`
- `cancel_result=returned_to_player`
- `dry_run_result=passed`
- `writer_called=true`
- `real_config_written=true`
- `backup_created=true`
- `expected_rotation_deg=270`
- `active_config_rotation_deg_matches=true`
- `orientation_json_updated=true`
- `orientation_json_rotation_matches=true`
- `splash_orientation_matches=true`
- `apply_policy_present_final=false`
- `media_orientation_matches=true`
- `shell_flash_seen=false`
- `service_final=active/enabled`
- `NRestarts=0`
- `public_state=player_running`
- `playback=playing`
- `player=1`
- `MPV=1`
- `renderer=0`
- `setup=0`

## Guardrails

- `wifi_changed=false`
- `networkmanager_changed=false`
- `hotspot_created=false`
- `portal_created=false`
- `root_read_only_enabled=false`
- `power_cut_tested=false`
- `raw_logs_written=false`
- no config, backup, private candidate, API value, environment identifier, SSID,
  password, IP, MAC, DNS, gateway, hostname or raw log is included here.

## Notes

The automated check confirms propagation to active config, public orientation
contract and splash. Human HDMI observation confirmed media orientation and no
shell/login flash. No screenshot or raw media path is copied into evidence.
