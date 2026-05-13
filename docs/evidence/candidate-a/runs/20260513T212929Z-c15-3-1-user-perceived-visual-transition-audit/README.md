# C15.3.1 - User-perceived visual transition audit

```text
c15_3_1_status=passed
decision=passed_with_p1_feedback_gap
manual_interaction_required=false
operator_keypress_required=false
board_accessed_via_ssh=true
timeline_monitor_created=true
timeline_monitor_executed=true
timeline_monitor_run=/data/state/totem-debug/c15-3-1/20260513T213308Z-pid9978
visual_journey_mapped=true
screen_intent_map_created=true
status_observability=partial
black_interval_observed=true
timeline_black_interval_observed=false
black_interval_duration_sec=unknown
black_interval_cause=unknown
feedback_visible_during_wait=false
player_restart_executed=false
framebuffer_available=true
framebuffer_capture_attempted=false
framebuffer_capture_succeeded=false
fb0_capture_may_not_reflect_mpv_drm=true
hdmi_capture_required_for_final_perception=true
p0_items_count=0
p1_items_count=3
p2_items_count=3
ready_for_c15_3_2_feedback_fix=true
ready_for_c16_player_audit=false
```

## Runtime Summary

The SSH-only monitor was run without opening the wizard, without calling writer,
without rebooting, and without restarting the player.

```text
sample_count=72
timeline_window_sec=178
screen_counts.player_playing=72
playback_state_counts.playing=72
ssh_remained_active=true
network_remained_connected=true
player_active_all_samples=true
mpv_present_any=true
kiosk_present_any=true
boot_id_changed=false
timeline_black_interval_observed=false
```

The transient black interval was observed previously during C15.2.4 clean-board
setup after "Iniciando player"; it was not reproduced during this passive
monitor run. The cause remains `unknown` from SSH-only evidence, with likely
mechanisms limited to media/cache/API wait, first-frame readiness, or the
splash-to-MPV handoff.

## Observability

```text
status_observability=partial
```

Available public/safe signals:

- splash status;
- launcher status;
- aggregated public status;
- player playback status;
- session trace when settings is used;
- process and service booleans.

Missing public/safe signals:

- waiting for playlist/API;
- waiting for media/cache;
- first frame ready;
- MPV/DRM handoff readiness.

## Backlog

P0:

- none.

P1:

- add visible feedback between `Iniciando player` and first playback frame;
- add public-safe startup readiness categories for API/playlist/media/cache;
- keep or replace the startup splash until a safe readiness signal exists,
  without fighting MPV/DRM once playback owns HDMI.

P2:

- HDMI/camera perception QA;
- broader wizard visual PDCA;
- polish/microcopy/motion after the state model is reliable.

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
player_code_changed=false
c16_started=false
c12_readonly_blocked=true
c12_4_blocked=true
```

## Artifacts

```text
runtime/final-summary.json
runtime/status-observability.json
```
