# 139 - C15.1.3 - F10 keyboard echo and first reboot validation

Status: **passed**
Date: 2026-05-13
Branch: `foundation-v0.1`
Preceding card: `C15.1.2`

## Context

C15.1.2 was blocked even though the warm-runtime wizard battery passed 5/5 by
trace. The remaining blockers were:

- `keyboard_echo_persisted=true`
- `cold_boot_context_tested=false`

C15.1.3 fixed the keyboard echo path and validated the first physical F10
attempt after one authorized controlled reboot.

## Change

The root cause was classified as:

```text
keyboard_echo_cause=tty_echo_enabled_before_f10_hold
```

Before the fix, the visual VT was active but still had terminal echo enabled
before the operator held F10. The existing guard was a one-shot operation and
did not keep the VT state pinned.

The fix adds `totem-visual-tty-guard.service`, a small persistent systemd
service that starts before the player, settings trigger, and open-settings
service. It runs:

```text
totem_visual_tty_guard.sh --quiet --hold --tty 1 --tty 2
```

`--hold` opens the selected VTs, applies `-echo -icanon`, and then sleeps while
holding the descriptors. It does not read keys, log input, touch network state,
or alter player code. An initial periodic-reapply variant was rejected because
it caused SVG blinking during the wizard; the final implementation does not
rewrite terminal state while the wizard owns the VT.

## Validation

Warm F10 after the final fix:

| Check | Result |
| --- | --- |
| `stty` echo off before F10 | passed |
| Wizard opens | passed |
| Keyboard echo visible | no |
| Terminal/login visible | no |
| Continuous SVG blinking | no |
| Early return to player before completion | no |
| `config_missing` returns during wizard | no |
| Trace reaches `openvt_exited` | passed |
| `WIZARD_RC=8` | passed |
| Writer result | `passed` |
| Session lock cleanup | passed |
| Player restore | passed |

One controlled reboot was then executed with `systemctl reboot`. After SSH
returned, the first physical F10 attempt passed:

| Check | Result |
| --- | --- |
| Player active before F10 | passed |
| Trigger active before F10 | passed |
| Visual TTY guard active/enabled | passed |
| Active VT guarded | passed |
| `tty1` and `tty2` echo off | passed |
| Terminal/login after reboot | no |
| Keyboard echo after reboot | no |
| Wizard first attempt after reboot | passed |
| Trace reaches `openvt_exited` | passed |
| `WIZARD_RC=8` | passed |
| Screens include `06-complete` | passed |
| Writer result | `passed` |
| Session lock cleanup | passed |
| Player restore | passed |

The firstboot gate raw tty output removal from C15.1.2 remains in place. The
controlled reboot confirmed no terminal/login was observed in the validated
path. A true power-cycle test was not performed.

## Decision

```text
c15_1_3_status=passed
ready_for_image_rebuild=true
ready_for_c16_player_audit=true
c16_started=false
poweroff_executed=false
power_cut_tested=false
player_code_changed=false
```

C15 can now release the next image rebuild. C16/player audit is unblocked, but
was not started in this card.

Follow-up: C15.1.4 was opened before the image rebuild to refresh the Wi-Fi setup
UX. It passed and kept C15.2.1 image rebuild readiness true. See
`docs/product/140_C15_1_4_WIFI_SETUP_UX_REFRESH.md`.

## Evidence

`docs/evidence/candidate-a/runs/20260513T153230Z-c15-1-3-f10-keyboard-echo-and-first-reboot-validation/`
