# C15.1.5 - Wizard UX redraw and startup feedback

```text
c15_1_5_status=passed
board_accessed_via_ssh=true
secrets_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
poweroff_executed=false
power_cut_tested=false
read_only_touched=false
kernel_touched=false
wifi_real_changed=true
networkmanager_touched_only_by_wizard=true
player_code_changed=false
c16_started=false
c12_readonly_blocked=true
c12_4_blocked=true
```

## UX Text

```text
wizard_text_simplified=true
max_panel_items_enforced=true
footer_simplified=true
operator_text_density_accepted=unknown
operator_text_density_acceptance_note=accepted_as_milestone_with_pdca_followup
```

## Input Redraw

```text
backspace_blinking_before=true
backspace_blinking_after=false
input_render_debounce_enabled=true
repeated_backspace_coalesced=true
max_render_rate_limited=true
input_stabilizes_under_500ms=true
password_not_logged=true
```

## Startup Feedback

```text
splash_boot_available=true
splash_player_available=true
splash_setup_available=true
splash_saving_available=true
splash_config_pending_available=true
startup_dead_moment_reduced=true
controlled_reboot_executed=false
startup_feedback_after_reboot_tested=false
splash_player_orientation_changed=true
splash_player_orientation_fix_in_repo=true
splash_player_orientation_hotfix_applied=true
splash_player_orientation_retest=runtime_sanity_passed_physical_retest_pending
wizard_visual_pdca_followup=true
```

## Tests

```text
wizard_self_test_passed=true
splash_self_test_passed=true
adapter_self_test_passed=true
preview_generated=true
physical_backspace_test_passed=true
physical_ux_review_passed=true
physical_transition_test_passed=true
```

```text
ready_for_image_rebuild=true
ready_for_c16_player_audit=true
```

## Implementation Notes

C15.1.5 reduced operator-facing copy in the visual wizard, capped panel bullets
at three items, constrained subtitles to one visual line, and shortened footers.
Text input now coalesces rapid Backspace/typing batches and limits redraw cadence
to about 10 fps. The password field remains hidden by default and keeps `F2/V`
as the local-only show/hide toggle.

Startup feedback was extended with public splash modes for `boot`, `player`,
`setup`, `saving`, and `config_pending`. The launcher and player unit now render
short static feedback during controlled gaps before handing the screen back to
the player or status renderer.

A hotfix regression was found during validation: writing splash status directly
under `/tmp` caused the splash helper to chmod `/tmp` to private mode, preventing
the `totem` user from using the MPV runtime directory. The fix keeps `/tmp`
world-sticky, writes splash status under `/tmp/dadooh-splash/...`, and updates
the splash helper so it never chmods `/tmp` itself. The board was repaired to
`/tmp` mode `1777`.

## Board Validation

Hotfix was applied to the board without reboot, poweroff, apt, pip, upgrade,
read-only, kernel, U-Boot, DTB, BSP, rootfs, player code, or C16 changes.

Sanitized technical result after the repaired hotfix:

```text
kiosky-player.service=active
totem-settings-trigger.service=active
totem-open-settings.service=inactive
totem-update-agent.timer=active
failed_count=1
failed_unit=aw859a-bluetooth.service
tmp_mode=1777
session_lock_present=false
mpv_present=true
trace_exists=true
trace_openvt_exited=true
trace_trap_signal=false
writer_called=true
writer_rc=0
writer_result=passed
real_config_written=true
backup_created=true
player_restore_ok=true
```

The operator accepted this as the C15.1.5 milestone. Backspace behavior improved:
holding Backspace now stops immediately after release, without the previous
long visual backlog. The wizard text density is still not ideal, but improved
enough for this milestone and should move to visual PDCA cycles instead of
blocking this reliability/continuity card.

The transition feedback appeared, but a new visual issue was observed: the final
`Inicializando player` splash briefly changed to another orientation before MPV
entered with the correct orientation again. This was treated as a C15.1.5
regression and fixed in the repo before commit by removing duplicate player
splash renders:
the player unit no longer draws a second `player` splash, the launcher skips its
own player splash when the F10 session already rendered one with the selected
rotation, and cleanup no longer draws over an already-active player.

This final splash-orientation patch was applied to the already-running lab board
after SSH returned. Runtime sanity after the final hotfix confirmed that the
effective `kiosky-player.service` no longer has a `totem_visual_splash.py player`
`ExecStartPre`, the player remains active, MPV is present, `/tmp` is `1777`, and
the session lock is absent. The next physical F10 pass should still observe the
transition visually, but the duplicate render source was removed on-device.

The remaining visual PDCA follow-up is for the whole wizard interface: layout,
copy, visual hierarchy, and real-use inspection cycles. It is not a splash
follow-up.

## Classification

```text
ux_text_density=too_verbose_before_fix
input_redraw_issue=redraw_per_key_and_input_queue_backlog
startup_dead_moment_cause=splash_not_called_before_player
milestone_decision=accepted_with_wizard_visual_pdca_followup
```

## Privacy

No SSH password, token, real API value, environment identifier, real SSID,
Wi-Fi password, private seed, real config content, NetworkManager profile,
IP/MAC/DNS, raw extensive log, media, or cache content is included here.
