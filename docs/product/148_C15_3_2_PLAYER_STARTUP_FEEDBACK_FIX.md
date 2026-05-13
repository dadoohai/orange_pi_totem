# 148 - C15.3.2 - Player startup feedback fix

## Status

```text
c15_3_2_status=passed
decision=passed_feedback_fixed
startup_feedback_fix_result=fixed_with_player_status_bridge
ready_for_image_rebuild=true
ready_for_c16_player_audit=true
c16_started=false
```

C15.3.1 accepted the previous card as an audit, not a correction. It found no
P0, but it left a P1 user-perceived feedback gap: after `Iniciando player`, a
valid wait for content could look like a black-screen freeze.

C15.3.2 closes that P1 with a minimal startup feedback bridge.

## Implementation

The solution is hybrid:

- `kiosky-player` now exposes safe startup fields in `/tmp/kiosky-status.json`;
- the player renders a local static MPV placeholder saying `Carregando
  conteudo` while content is not yet in a reliable playback state;
- the totem core status aggregator understands `loading_content`;
- the totem status renderer can render the `loading_content` public state;
- `totem_visual_splash.py` includes a `loading_content` splash mode;
- a C15.3.2 monitor records the startup feedback timeline.

The player code change is limited to status and feedback:

```text
player_code_changed=true
player_code_change_scope=other
player_code_change_scope_detail=status_public_and_placeholder_feedback_only
scheduler_changed=false
sync_changed=false
duration_changed=false
playlist_logic_changed=false
loop_logic_changed=false
exposure_time_ms_changed=false
```

No playback scheduler, duration, sync, loop, playlist ordering, or media
selection semantics were changed.

## Public States

New/safe player startup fields:

- `status_schema_version=kiosky-player-status.v2`;
- `player_state`;
- `playback_state`;
- `startup_phase`;
- `startup_feedback_state`;
- `startup_feedback_visible`;
- `startup_feedback_display`;
- `content_state`;
- `first_frame_ready`;
- `first_content_load_accepted`.

Startup phases now include safe categories such as:

- `player_starting`;
- `waiting_for_api`;
- `waiting_for_playlist`;
- `waiting_for_media_cache`;
- `waiting_for_media`;
- `waiting_for_content`;
- `preparing_first_frame`;
- `playing`;
- `error_player_start`.

These fields are public-safe categories and booleans only. They do not include
private config, API values, network identifiers, SSID, Wi-Fi password, media
URLs, or raw logs.

## Validation

Local validation:

```text
python3 -m py_compile kiosk.py
python3 -m unittest discover -s tests
bash -n scripts/remote/c15_3_2_player_startup_feedback_monitor.sh
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 -m json.tool scripts/board/totem_appliance_manifest.json
python3 scripts/board/totem_status_aggregate.py --state-override loading_content
```

Board validation:

```text
hotfix_applied_to_board=true
player_restart_tested=true
writer_called=false
real_config_written=false
reboot_executed=false
poweroff_executed=false
```

The monitored restart produced:

```text
loading_content_state_seen=true
loading_content_feedback_visible=true
playback_state_counts.waiting_for_content=2
playback_state_counts.playing=36
ssh_remained_active=true
network_remained_connected=true
player_active_all_samples=true
boot_id_changed=false
```

The final runtime state was healthy:

```text
public_state=player_running
playback_state=playing
startup_phase=playing
content_state=playing
first_frame_ready=true
```

## Limitations

The validation was SSH/timeline based. HDMI/camera capture is still the best
final perception test for exact black-frame duration and flicker. This card
does, however, prove that a safe `loading_content` state and visible feedback
exist during startup, and that the player returns to `playing` without SSH or
network loss.

## Decision

C15.3.2 passes:

```text
ready_for_image_rebuild=true
ready_for_c16_player_audit=true
```

C16/player timing/sync/looping was not started. C12 read-only and C12.4 remain
blocked.

## Evidence

`docs/evidence/candidate-a/runs/20260513T215758Z-c15-3-2-player-startup-feedback-fix/`
