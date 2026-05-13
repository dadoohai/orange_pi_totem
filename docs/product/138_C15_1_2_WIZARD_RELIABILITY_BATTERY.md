# 138 - C15.1.2 - Wizard reliability battery

Status: **blocked** (`keyboard_echo_persisted`)
Date: 2026-05-13
Branch: `foundation-v0.1`
Preceding card: `C15.1.1`

## Context

C15.1.1 was only partial-validated. Test #1 failed with
`code=killed status=15/TERM` and the cause remained unclassified because the
trace was not yet active. Test #2 passed with C15 instrumentation enabled.

C15.1.2 was created to run a five-attempt physical F10 battery, classify any
failure by trace, and decide whether a C15.1.3/C14.2.2 image rebuild could be
released. It also included the smallest firstboot gate fix for raw tty output.

## Firstboot Gate Fix

`scripts/board/totem_firstboot_gate.sh` no longer writes appliance-facing raw
text to `/dev/tty2` in the normal firstboot gate path. It clears the VT, hides
the cursor, and lets `totem_visual_splash.py firstboot` own the visual path. If
the renderer fails, the fallback clears the VT without printing text on HDMI.

The same hotfix was applied to the board at
`/opt/totem/bin/totem_firstboot_gate.sh` without reboot.

Validation:

- local `bash -n`: ok
- local `--self-test`: ok
- board `bash -n`: ok
- board sha256:
  `7769af7caf0da9f1c50f3e80ccb31ff03aa632a00958ebee1ea99210647aabe7`

The fix was not cold-boot validated because this round did not reboot or
power-cycle the board.

## Battery Result

The warm-runtime wizard flow passed 5/5 by trace:

| Test | Result by trace | Screens | Writer | Lock | Player |
| --- | --- | ---: | --- | --- | --- |
| 1 | `openvt_exited`, `WIZARD_RC=8` | 6 | `writer_rc=0`, `passed` | absent | active |
| 2 | `openvt_exited`, `WIZARD_RC=8` | 10 | `writer_rc=0`, `passed` | absent | active |
| 3 | `openvt_exited`, `WIZARD_RC=8` | 6 | `writer_rc=0`, `passed` | absent | active |
| 4 | `openvt_exited`, `WIZARD_RC=8` | 8 | `writer_rc=0`, `passed` | absent | active |
| 5 | `openvt_exited`, `WIZARD_RC=8` | 8 | `writer_rc=0`, `passed` | absent | active |

Across all five:

- `trap_signal` did not appear.
- The C15.1.1 SIGTERM did not return.
- `totem-open-settings.service` deactivated successfully.
- `kiosky-player.service` was restored to active.
- The session lock was absent after cleanup.
- `config_missing` did not return during the wizard.
- Terminal/login did not appear.
- No player code was changed.

## Blocker

The operator confirmed that pressing F10 still shows keyboard characters
overwritten on top of the SVG before the screen refresh clears them. That means
the visual acceptance criterion "no keyboard echo" did not pass.

Classification:

```text
keyboard_echo_persisted=true
unclassified_failures=0
```

This is distinct from the wizard exiting by itself or a terminal/login leak
during a warm-runtime F10 session. The wizard did not exit by itself during this
five-run battery, and terminal/login did not appear.

The operator also clarified that the original "wizard exits by itself",
"terminal/login appears", or "falls back to config_missing" symptoms are most
often perceived immediately after the board has powered on. This round did not
reboot or power-cycle by restriction, so that cold-boot/first-attempt context
was not exercised and must not be treated as passed.

## Decision

```text
c15_1_2_status=blocked
warm_runtime_f10_battery_passed=true
cold_boot_context_tested=false
ready_for_image_rebuild=false
ready_for_c16_player_audit=false
c15_1_1_remains=partial-validated
c16_started=false
c16_blocked_until_c15_1_2_passed=true
```

Do not start C16/player yet. Do not rebuild C15.1.3/C14.2.2 as a released
image from this result. The next C15 action should address the F10 keyboard echo
path deliberately, then rerun the reliability battery or a narrower acceptance
test as appropriate.

## Evidence

`docs/evidence/candidate-a/runs/20260513T143957Z-c15-1-2-wizard-reliability-battery/`
