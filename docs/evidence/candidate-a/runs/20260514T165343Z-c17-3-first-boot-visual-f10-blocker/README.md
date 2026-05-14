# C17.3 First-Boot Visual/F10 Blocker

## Status

```text
c17_3_status=blocked
image_under_test=c17.3
card_written=true
single_board_validated=false

failure_area=first_boot_pre_config_visual_and_f10
failure_type=clean_board_first_boot_visual_dead_state
black_screen_before_first_f10=true
f10_no_response_on_first_boot=true
wifi_configured_before_failure=false
ssh_available_before_failure=false
startup_feedback_before_config_visible=false
emergency_physical_power_cycle_recovery=true
planned_power_cut_tested=false
c12_4_power_cut_tested=false

splash_after_power_cycle_visible=true
misformatted_config_missing_splash_after_reboot=true
second_boot_f10_opened_wizard=true
wizard_currently_open_at_collection=false
wifi_connected_by_wizard=true
ssh_available_after_wifi=true
writer_called_before_collection=false
config_real_present_before_writer=false

first_boot_logs_available=false
first_boot_failure_evidence_source=human_observation_only

first_boot_black_screen_cause=unknown
f10_no_response_cause=unknown
misformatted_splash_cause=unknown
second_boot_blocker=wizard_not_visible_status_screen_occluding_or_replacing_wizard

functional_flow_after_second_boot=blocked
writer_passed=not_run
player_restore_ok=not_run
ssh_active_after_writer=not_run
network_connected_after_writer=not_run

ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c18_player_audit=false
ready_for_c17_4_first_boot_fix=true
next_step=C17.4_FIRST_BOOT_PRE_CONFIG_VISUAL_AND_F10_FIX
```

## Human Observation

On the first clean boot of the C17.3 card, HDMI stayed black before any Wi-Fi
or config existed. Holding F10 did not open settings. Recovery required a
physical power cycle performed by the operator. This was not a planned power
cut test and does not count as C12.4.

After the physical power cycle, HDMI showed a blue missing-configuration splash
with visually overlapped/misformatted text, then another `config_missing` SVG
with dark blue/orange styling. F10 worked on this second boot, the wizard
opened, and the operator rotated the display and connected Wi-Fi. SSH then
became available.

During later continuation, the operator reported that the wizard was no longer
visible. HDMI was showing a dark blue/orange configuration-pending screen
instead. The wizard was therefore not practically open to the user at
collection/continuation time, and the writer was not called.

## Sanitized Runtime Snapshot

Collected over SSH after Wi-Fi was connected by the wizard and before writer:

```text
uptime_seconds=902.88
boot_id=b147ca37-5d3f-4695-ade6-cbd887a0c7c6
kiosky-player.service=active
NetworkManager=active
ssh.service=active
sshd.service=active
totem-visual-tty-guard.service=active
totem-settings-trigger.service=active
totem-open-settings.service=activating
totem-update-agent.timer=active
failed_units_count=1
failed_units_names_sanitized=console-setup.service
fgconsole=2
getty_tty1=inactive
getty_tty2=inactive
getty_tty3=inactive
config_real_present=false
seed_present=true
networkmanager_connected=true
session_lock_present=true
tmp_permissions=1777 root:root /tmp
public_state=config_missing
public_error_code=CONFIG_MISSING
playback_state=unknown
player_state=not_started
```

Relevant sanitized process state showed:

```text
totem_visual_tty_guard.sh holding tty1/tty2=true
totem_settings_trigger.py daemon=true
totem_open_settings_session.sh running=true
openvt tty2 running=true
totem_setup_visual_wizard.py running_on_tty2=true
kiosky_service_launcher.sh running=true
totem_status_renderer.sh running=true
mpv_status_renderer_running=true
```

This combination is inconsistent with the expected user-facing state: the
settings session and wizard process exist, but the HDMI surface seen by the
operator is the public `config_missing` status screen.

## Boot Log Availability

```text
journalctl_list_boots_current_only=true
first_boot_logs_available=false
first_boot_failure_evidence_source=human_observation_only
```

The failed first boot occurred before Wi-Fi/SSH was available and journald did
not expose an earlier boot after the physical recovery. Root cause for the
first black screen and first F10 no-response is therefore not confirmed.

## Current Boot Evidence

Current boot journals showed:

```text
totem-firstboot-gate.service=skipped_condition_path_exists_root_not_logged_in_yet
totem-open-settings.service=started_at_second_boot_f10_and_still_activating
kiosky-player.service=started_config_missing_status_then_stopped_for_settings_then_started_again_while_settings_session_still_active
NetworkManager_connected_after_wizard=true
ssh_active_after_wifi=true
```

The current boot supports a second blocker hypothesis: the status renderer/MPV
returned while `totem-open-settings.service` was still activating and the wizard
process still existed on tty2, hiding or replacing the wizard surface on HDMI.
That is a C17.4 setup/display-session issue, not C18/player timing.

## Classification

```text
first_boot_black_screen_cause=unknown
f10_no_response_cause=unknown
misformatted_splash_cause=unknown
second_boot_wizard_visibility_cause=status_renderer_or_kiosky_restarted_during_open_settings_session
```

The unknown classifications are intentional: the first failed boot has human
observation only and no retained journal. The second-boot visibility failure is
supported by live process/service state, but still needs a C17.4 fix/probe
before claiming exact root cause.

## Guardrails

```text
secrets_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
read_only_touched=false
kernel_touched=false
wifi_touched_only_by_wizard=true
networkmanager_touched_only_by_wizard=true
poweroff_executed=false
power_cut_tested=false
planned_power_cut_tested=false
c12_4_power_cut_tested=false
c12_readonly_blocked=true
c12_4_blocked=true
writer_called_by_probe=false
real_config_content_read=false
private_seed_content_read=false
networkmanager_profiles_read=false
raw_logs_published=false
c18_started=false
```

No config content, seed content, NetworkManager profile, SSID, password,
IP/MAC/DNS, API key, API URL, environment ID, media URL or raw long log was
published in this evidence.

## Decision

C17.3 remains blocked. Even if a later manual recovery made the player work,
the first clean-boot user journey is already blocked by black screen and F10
no-response before configuration. The live second-boot state adds a second
setup-session blocker: the wizard is not visible to the operator and writer did
not run.

```text
c17_3_first_boot_user_journey_blocked=true
c17_3_functional_after_second_boot=false
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c18_player_audit=false
ready_for_c17_4_first_boot_fix=true
```
