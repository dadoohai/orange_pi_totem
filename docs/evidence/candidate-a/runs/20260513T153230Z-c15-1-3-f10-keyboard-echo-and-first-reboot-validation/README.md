# C15.1.3 - F10 keyboard echo and first reboot validation

```text
c15_1_3_status=passed
board_accessed_via_ssh=true
controlled_reboot_executed=true
poweroff_executed=false
power_cut_tested=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
read_only_touched=false
kernel_touched=false
wifi_touched=false
networkmanager_touched=false
player_code_changed=false
secrets_published=false
c12_readonly_blocked=true
c12_4_blocked=true

keyboard_echo_before=true
keyboard_echo_after=false
keyboard_echo_cause=tty_echo_enabled_before_f10_hold
tty_guard_applied_before_f10=true
stty_echo_off_before_f10=true
active_vt_guarded=true

warm_f10_after_fix_passed=true
first_f10_after_reboot_passed=true
terminal_login_visible_after_reboot=false
config_missing_returns_during_wizard=false
trap_signal_seen=false
session_lock_cleanup_ok=true
player_restore_ok=true

firstboot_gate_raw_tty_output_removed=true
cold_boot_context_tested=controlled_reboot_only
true_power_cycle_tested=false

ready_for_image_rebuild=true
ready_for_c16_player_audit=true
```

## Summary

C15.1.2 left two blockers: visible keyboard echo during F10 hold and the lack
of first-attempt validation after a controlled boot. C15.1.3 resolved both in
the lab runtime.

Pre-fix diagnosis showed the appliance visual VT had `echo` enabled before the
operator held F10. The existing one-shot guard did not keep the VT state
pinned. The final hotfix adds a small persistent `totem-visual-tty-guard`
systemd service and updates `totem_visual_tty_guard.sh --hold` so it opens the
reserved VTs, applies `-echo -icanon`, and then sleeps without periodically
rewriting terminal state while the wizard owns the VT.

An intermediate version that reapplied the guard periodically removed keyboard
echo but caused continuous SVG blinking and an early return to the player. That
variant was not accepted. The final version removes periodic reapply and was
the one validated below.

## Pre-Fix Classification

```text
foreground_vt=tty2
tty2_echo_before_fix=enabled
guard_non_hold_reapply_result=not_persistent
keyboard_echo_cause=tty_echo_enabled_before_f10_hold
```

## Hotfix Applied

Files installed on the board:

```text
/opt/totem/bin/totem_visual_tty_guard.sh
/etc/systemd/system/totem-visual-tty-guard.service
/etc/systemd/system/kiosky-player.service
/etc/systemd/system/totem-settings-trigger.service
/etc/systemd/system/totem-open-settings.service
```

Services were reloaded with `systemctl daemon-reload`; the visual TTY guard was
enabled and started. No reboot was used until the authorized controlled reboot
step.

## Warm F10 After Fix

Final warm validation, after removing periodic reapply:

```text
pre_guard_active=active
pre_player_active=active
pre_trigger_active=active
pre_session_lock=absent
pre_fgconsole=2
pre_tty2_echo_off=true
trace_seen=true
openvt_exited=true
WIZARD_RC=8
trap_signal_seen=false
screens_count=8
last_screen=06-complete
writer_called=true
writer_rc=0
writer_result=passed
real_config_written=true
backup_created=true
session_lock=absent
player_active=active
operator_keyboard_echo_seen=false
operator_terminal_login_seen=false
operator_continuous_blink_seen=false
operator_early_player_return_seen=false
operator_config_missing_return_seen=false
```

## Controlled Reboot

Exactly one controlled reboot was executed:

```text
command=systemctl reboot
poweroff_executed=false
power_cut_tested=false
```

Post-boot sanitized state before the first F10:

```text
kiosky_player_active=active
settings_trigger_active=active
open_settings_active=inactive
update_timer_active=active
visual_tty_guard_active=active
visual_tty_guard_enabled=enabled
getty_tty1=inactive_disabled
getty_tty2=inactive_disabled
getty_tty3=inactive_disabled
serial_getty=active_enabled
foreground_vt=tty1
tty1_echo_off=true
tty2_echo_off=true
session_lock=absent
firstboot_gate_raw_strings=absent
```

One unrelated board unit was failed after boot:

```text
failed_unit=aw859a-bluetooth.service
wizard_path_impact=none_observed
```

## First F10 After Reboot

```text
first_f10_after_reboot_passed=true
trace_seen=true
openvt_exited=true
WIZARD_RC=8
trap_signal_seen=false
screens_count=8
last_screen=06-complete
writer_called=true
writer_rc=0
writer_result=passed
real_config_written=true
backup_created=true
session_lock=absent
player_active=active
open_settings_final=inactive
service_deactivated_successfully=true
operator_result=funcionou
terminal_login_visible_after_reboot=false
keyboard_echo_after=false
config_missing_returns_during_wizard=false
```

## Decision

```text
c15_1_3_status=passed
ready_for_image_rebuild=true
ready_for_c16_player_audit=true
c16_started=false
```

C16/player audit is now unblocked, but it was not started in this round.
