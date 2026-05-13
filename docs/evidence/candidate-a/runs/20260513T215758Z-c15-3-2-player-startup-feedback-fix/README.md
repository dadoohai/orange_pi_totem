# C15.3.2 - Player startup feedback fix

```text
c15_3_2_status=passed
startup_feedback_fix_result=fixed_with_player_status_bridge
feedback_state_added=true
public_startup_status_added=true
loading_content_screen_available=true
player_restart_tested=true
player_restart_health_ok=true
timeline_monitor_executed=true
feedback_visible_during_wait=true
black_interval_without_feedback_possible=false
avoids_mpv_drm_fight=true
```

## Scope

C15.3.2 implements a minimal feedback bridge between `Iniciando player` and
the first reliable player/content state. The fix is hybrid:

- player status/placeholder bridge in `kiosky-player`;
- core public status aggregation/rendering for `loading_content`;
- a C15.3.2 startup-feedback monitor.

The player change is limited to status and a static MPV placeholder. It does
not change scheduler, sync, duration, playlist ordering, loop behavior, or
`exposure_time_ms`.

## Runtime Validation

The hotfix was applied to the board and validated by restarting only
`kiosky-player.service`, with the monitor active.

```text
monitor_run=/data/state/totem-debug/c15-3-2/20260513T215758Z-pid18477
sample_count=38
loading_content_state_seen=true
loading_content_feedback_visible=true
playback_state_counts.waiting_for_content=2
playback_state_counts.playing=36
startup_phase_counts.waiting_for_api=2
startup_phase_counts.playing=36
ssh_remained_active=true
network_remained_connected=true
player_active_all_samples=true
mpv_present_any=true
kiosk_present_any=true
boot_id_changed=false
```

Final runtime state:

```text
kiosky_player_active=active
networkmanager_active=active
ssh_active=active
public_state=player_running
playback_state=playing
startup_phase=playing
content_state=playing
first_frame_ready=true
session_lock_present=false
```

`failed_units_count=1` remained from the known non-blocking console setup
hygiene issue already recorded in C15.2.4. It did not affect the player restart
test, SSH, NetworkManager, playback, or the startup feedback bridge.

## Classification

```text
player_code_changed=true
player_code_change_scope=other
player_code_change_scope_detail=status_public_and_placeholder_feedback_only
scheduler_changed=false
sync_changed=false
duration_changed=false
playlist_logic_changed=false
loop_logic_changed=false
c16_started=false
```

The implementation writes safe startup fields such as `startup_phase`,
`content_state`, `startup_feedback_state`, `startup_feedback_visible`, and
`first_frame_ready`. During startup, MPV displays a local static
`Carregando conteudo` placeholder until real content is loaded. Once playback is
reported as `playing`, the player owns the display normally.

## Decision

```text
ready_for_image_rebuild=true
ready_for_c16_player_audit=true
```

C16 remains unopened in this card. The next image rebuild should include both
the totem core changes and the updated `kiosky-player` status/feedback bridge.

## Guardrails

```text
secrets_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
poweroff_executed=false
power_cut_tested=false
read_only_touched=false
kernel_touched=false
wifi_real_changed=false
networkmanager_touched=false
writer_called=false
real_config_written=false
c12_readonly_blocked=true
c12_4_blocked=true
```

## Artifacts

```text
runtime/final-summary.json
runtime/runtime-status.json
```
