# 165 - C17.3 - First Boot Visual/F10 Blocker

## Status

```text
c17_3_status=blocked
failure_area=first_boot_pre_config_visual_and_f10
failure_type=clean_board_first_boot_visual_dead_state
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c18_player_audit=false
next_step=C17.4_FIRST_BOOT_PRE_CONFIG_VISUAL_AND_F10_FIX
```

C17.3 was generated, committed and pushed as a private homologation image with
the C17.2 visual polish embedded. The image was then written manually with
Armbian Imager to a clean card and booted on the lab board.

## Observed Failure

Before any Wi-Fi or config existed, the first clean boot stayed on a black HDMI
screen. Holding F10 did not open setup. SSH was unavailable because Wi-Fi had
not yet been configured. The operator recovered only by cycling physical power.
This was an emergency recovery, not a planned power-cut test and not C12.4.

After the physical cycle, HDMI showed a blue missing-configuration splash with
overlapped/misformatted text, then another `config_missing` SVG with dark
blue/orange styling. F10 worked on this second boot, the wizard opened, and the
operator rotated the display and connected Wi-Fi. SSH then became available.

During continuation, before writer, the operator reported that the wizard was
not visible anymore. The HDMI surface was a dark blue/orange configuration
pending screen. Runtime state showed `totem-open-settings.service` still
activating and `totem_setup_visual_wizard.py` still running on tty2, but
`kiosky-player.service`, `totem_status_renderer.sh` and MPV were also running
and showing public `config_missing` status. The practical user journey was
blocked: the writer was not called and no real config existed.

## Evidence Summary

```text
black_screen_before_first_f10=true
f10_no_response_on_first_boot=true
startup_feedback_before_config_visible=false
emergency_physical_power_cycle_recovery=true
planned_power_cut_tested=false
c12_4_power_cut_tested=false
splash_after_power_cycle_visible=true
misformatted_config_missing_splash_after_reboot=true
second_boot_f10_opened_wizard=true
wifi_connected_by_wizard=true
ssh_available_after_wifi=true
writer_called_before_collection=false
config_real_present_before_writer=false
functional_flow_after_second_boot=blocked
```

The failed first boot has no retained journal:

```text
first_boot_logs_available=false
first_boot_failure_evidence_source=human_observation_only
```

The current boot showed enough to classify a live second blocker:

```text
totem-open-settings.service=activating
totem_setup_visual_wizard.py=running_on_tty2
kiosky-player.service=active
totem_status_renderer.sh=running
mpv_status_renderer_running=true
public_state=config_missing
session_lock_present=true
config_real_present=false
```

## Cause Classification

```text
first_boot_black_screen_cause=unknown
f10_no_response_cause=unknown
misformatted_splash_cause=unknown
second_boot_wizard_visibility_cause=status_renderer_or_kiosky_restarted_during_open_settings_session
```

The first-boot root cause cannot be claimed without a retained journal or HDMI
capture. Plausible areas for C17.4 are firstboot visual service ordering,
settings trigger/F10 readiness, DRM/HDMI readiness and first-boot initialization
race. The second-boot visibility issue has stronger evidence: the setup session
and wizard process were alive while the public status renderer/MPV was also
alive and visible.

## Not C18

This is not a C18/player timing/sync/duration/loop problem. The blocking
failure happened before configuration, before Wi-Fi existed on first boot and
before normal player content. The visible post-recovery issue is still the
setup/status surface, not media playback, cache, API or loop behavior.

## Decision

C17.3 cannot be released for batch flashing or dispatch:

```text
c17_3_first_boot_user_journey_blocked=true
c17_3_functional_after_second_boot=false
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c18_player_audit=false
ready_for_c17_4_first_boot_fix=true
```

C17.4 should fix and prove first-boot pre-config visual/F10 behavior. C18
remains closed until the clean-board setup journey is reliable again.
