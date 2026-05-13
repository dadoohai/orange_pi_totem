# C15.1.2 - Wizard reliability battery + firstboot tty leak fix

Run identifier: `20260513T143957Z-c15-1-2-wizard-reliability-battery`
Date: 2026-05-13
Branch: `foundation-v0.1`
Board: lab Orange Pi Zero 3, accessed via SSH

## Required Fields

```text
c15_1_2_status=blocked
board_accessed_via_ssh=true
secrets_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
poweroff_executed=false
power_cut_tested=false
read_only_touched=false
kernel_touched=false
wifi_touched=false
networkmanager_touched=false
player_code_changed=false
c16_started=false
c12_readonly_blocked=true
c12_4_blocked=true

firstboot_tty_leak_fix_applied=true
firstboot_raw_tty_output_removed=true
warm_runtime_f10_battery_passed=true
cold_boot_context_tested=false

test_count=5
test_1_status=blocked
test_2_status=blocked
test_3_status=blocked
test_4_status=blocked
test_5_status=blocked

all_tests_passed=false
unclassified_failures=0
trace_available_for_all_tests=true
trap_signal_seen=false
session_lock_cleanup_ok=true
player_restore_ok=true
tty_login_visible=false
keyboard_echo_visible=true
config_missing_returns_during_wizard=false
ready_for_image_rebuild=false
ready_for_c16_player_audit=false
```

## Result

C15.1.2 is **blocked**, not passed.

The warm-runtime wizard flow passed 5/5 by trace, systemd evidence, and
operator observation: every F10 session reached `openvt_exited`, returned
`WIZARD_RC=8`, called the writer, wrote real config through the approved wizard
flow, cleaned the session lock, restored `kiosky-player.service`, and did not
show a terminal/login.

The card cannot close because the observed acceptance gap is broader than the
successful warm-runtime flow:

1. The operator confirmed that pressing F10 still shows typed characters over
   the SVG before the screen refresh clears them. This is classified as:

```text
failure_classification=keyboard_echo_persisted
```

2. The earlier "wizard exits by itself", "terminal/login appears", and
   "falls back to config_missing" symptoms are most frequently perceived just
   after the board has powered on. This battery did not reboot or power-cycle
   the board by restriction, so that cold-boot/first-attempt context remains
   unexercised in this run.

The keyboard echo is a classified blocker, not an unclassified failure. The
cold-boot context gap is recorded as not tested, not as passed. No blind fix was
attempted after the classification.

## Firstboot TTY Leak Minimal Fix

Changed `scripts/board/totem_firstboot_gate.sh` and applied the same file to the
board at `/opt/totem/bin/totem_firstboot_gate.sh`.

The normal firstboot gate path no longer prints raw text to `/dev/tty2`. It now
clears the reserved VT, hides the cursor, and lets the splash renderer own the
visual path. If the renderer fails, the fallback clears the VT without printing
raw HDMI text. SSH and serial console behavior were preserved.

Validation:

```text
local_bash_n_totem_firstboot_gate=ok
local_self_test_totem_firstboot_gate=ok
board_bash_n_totem_firstboot_gate=ok
board_sha256=7769af7caf0da9f1c50f3e80ccb31ff03aa632a00958ebee1ea99210647aabe7
raw_firstboot_strings_removed_from_board_script=true
```

No reboot was executed, so the firstboot visual fix was applied and inspected
but not cold-boot validated.

## Instrumentation

The board already had C15 instrumentation in
`/opt/totem/bin/totem_open_settings_session.sh`:

- `c15_trace`
- traps for `TERM`, `INT`, and `HUP`
- phase trace points for `session_sh_start`, `before_getty_stop`,
  `before_show_transition_1`, `after_show_transition_1`,
  `before_systemctl_stop_kiosky`, `after_systemctl_stop_kiosky`,
  `after_drain_wait`, `before_openvt`, `openvt_started`, `openvt_exited`,
  and `after_wizard`

No `trap_signal` appeared in any of the five traces.

## Runtime Snapshot

Pre-battery runtime was sanitized and did not read private config or seed
contents.

```text
kiosky-player.service=active
totem-settings-trigger.service=active
totem-open-settings.service=inactive
totem-update-agent.timer=active
systemctl_failed_count=0
getty@tty1.service=inactive disabled
getty@tty2.service=inactive disabled
getty@tty3.service=inactive disabled
serial-getty@ttyS0.service=active enabled
fgconsole=2
session_lock=absent
```

Final runtime after test 5:

```text
kiosky-player.service=active
totem-settings-trigger.service=active
totem-open-settings.service=inactive
totem-update-agent.timer=active
systemctl_failed_count=0
session_lock=absent
playback_state=playing
```

## Battery Summary

Intervals used:

- test 1: immediate after clean pre-check
- test 2: after the operator was ready; more than the required 30 seconds
- test 3: after the required 1 minute
- test 4: after the required 5 minutes
- test 5: after the required 10 minutes

All five attempts started from:

```text
kiosky-player.service active=active
totem-settings-trigger.service active=active
totem-open-settings.service active=inactive
session_lock=false
```

### Test 1

```text
trace_start=2026-05-13T14:07:40Z
openvt_exited=true
wizard_rc=8
screens_rendered=6
writer_called=true
writer_rc=0
writer_result=passed
real_config_written=true
backup_created=true
trap_signal_seen=false
service_result=success
journal_deactivated_successfully=true
session_lock=absent
kiosky-player.service=active
public_state=player_running
playback_state=playing
status=blocked
blocker=keyboard_echo_persisted
```

Screens:

```text
0001-01-orientation.svg
0002-01-orientation-confirm.svg
0003-02-connection.svg
0004-03-environment.svg
0005-05-review.svg
0006-06-complete.svg
```

### Test 2

```text
trace_start=2026-05-13T14:13:29Z
openvt_exited=true
wizard_rc=8
screens_rendered=10
writer_called=true
writer_rc=0
writer_result=passed
real_config_written=true
backup_created=true
trap_signal_seen=false
service_result=success
journal_deactivated_successfully=true
session_lock=absent
kiosky-player.service=active
public_state=player_running
playback_state=playing
status=blocked
blocker=keyboard_echo_persisted
```

### Test 3

```text
trace_start=2026-05-13T14:18:21Z
openvt_exited=true
wizard_rc=8
screens_rendered=6
writer_called=true
writer_rc=0
writer_result=passed
real_config_written=true
backup_created=true
trap_signal_seen=false
service_result=success
journal_deactivated_successfully=true
session_lock=absent
kiosky-player.service=active
public_state=player_running
playback_state=playing
status=blocked
blocker=keyboard_echo_persisted
```

### Test 4

```text
trace_start=2026-05-13T14:25:48Z
openvt_exited=true
wizard_rc=8
screens_rendered=8
writer_called=true
writer_rc=0
writer_result=passed
real_config_written=true
backup_created=true
trap_signal_seen=false
service_result=success
journal_deactivated_successfully=true
session_lock=absent
kiosky-player.service=active
public_state=player_running
playback_state=playing
status=blocked
blocker=keyboard_echo_persisted
```

### Test 5

```text
trace_start=2026-05-13T14:37:38Z
openvt_exited=true
wizard_rc=8
screens_rendered=8
writer_called=true
writer_rc=0
writer_result=passed
real_config_written=true
backup_created=true
trap_signal_seen=false
service_result=success
journal_deactivated_successfully=true
session_lock=absent
kiosky-player.service=active
public_state=player_running
playback_state=playing
status=blocked
blocker=keyboard_echo_persisted
```

## Classification

```text
SIGTERM_external_unknown=false
service_race_with_config_missing=false
openvt_exit_unexpected=false
wizard_rc_unexpected=false
player_restore_failed=false
lock_cleanup_failed=false
tty_leak_persisted=unknown
keyboard_echo_persisted=true
other_classified=false
```

Notes:

- The C15.1.1 SIGTERM did not recur.
- `config_missing` did not return during the wizard in any of the five runs.
- No terminal/login was visible during the five F10 attempts.
- The firstboot raw `/dev/tty2` print path was removed, but not cold-boot
  validated because reboot/power-cycle was not performed.
- The keyboard echo remains visible during F10 activation and is the blocker.

## Decisions

```text
c15_1_2_closure=blocked_keyboard_echo_persisted_and_cold_boot_context_not_tested
c15_1_1_remains=partial-validated
image_rebuild_released=false
c15_1_3_or_c14_2_2_rebuild_allowed=false
c16_player_audit_allowed=false
c16_blocked_until_c15_1_2_passed=true
```

No changes were made to `kiosky-player/kiosk.py`, player sync, MPV flags,
Wi-Fi, NetworkManager, read-only, kernel, U-Boot, DTB, BSP, or rootfs.
