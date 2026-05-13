# 144 - C15.2.2 - Clean-board wizard setup interruption fix

## Status

```text
c15_2_2_status=blocked
failure_type=pre_existing_untested_clean_board_bug
ready_for_image_rebuild=false
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c16_player_audit=false
c16_started=false
```

C15.2.2 was opened after C15.2.1 clean-board validation exposed a real setup
flow bug that was not covered by hot-board tests or the C15.1.6 heuristic UI/UX
review.

## C15.2.1 Finding

C15.2.1 built and passed offline validation, but the clean-board wizard exited
while the operator typed the environment value after Wi-Fi connected. This is
not treated as a regression. It is a latent clean-board setup bug.

Initial forensics showed the session never reached `openvt_exited`. Instead it
hit the deadline path:

```text
last_trace_phase=openvt_still_running_after_deadline
wizard_clean_board_exit_cause=service_timeout
```

The clean board booted with an initial pre-NTP clock, then Wi-Fi connection
corrected system time. The settings session used wall-clock `date +%s` to decide
whether the interactive `openvt` process had exceeded its timeout. After the
clock step, the wizard appeared older than `TIMEOUT_SEC` and was killed even
though the operator was still in the flow.

## Fixes

The F10 settings session now uses monotonic uptime from `/proc/uptime` for the
openvt timeout deadline. Network/NTP clock steps no longer shorten the operator
session.

Password visibility was also corrected:

- simple printable `V`/`v` is no longer a show/hide shortcut;
- `v` and `V` are accepted as normal password characters;
- F2 is the advertised show/hide key;
- Ctrl+P is accepted as a non-printable fallback;
- public status and evidence still do not include passwords or SSIDs.

Updated files:

```text
scripts/board/totem_open_settings_session.sh
scripts/board/totem_setup_visual_wizard.py
scripts/board/totem_appliance_manifest.json
scripts/qa/generate_ui_ux_gallery.py
scripts/build/derive_c15_2_1_homolog_image.py
```

## Validation

Local self-tests and syntax checks passed. The known local-only
`totem_updatectl.py self-test` `/data` permission error remains unchanged and
was run with `|| true`.

The hotfix was applied to the already flashed board. On retest, the operator
confirmed:

```text
environment_input_survived=true
password_accepts_lowercase_v=true
password_accepts_uppercase_v=true
password_show_toggle_key=F2
writer_passed=true
```

Post-recovery runtime evidence showed:

```text
openvt_timeout_clock=monotonic
openvt_exited=true
wizard_rc=8
writer_rc=0
writer_result=passed
real_config_written=true
session_lock_cleanup_ok=true
public_state=player_running
playback_state=playing
```

## Remaining Blocker

After the operator completed the retest, HDMI showed a black screen and SSH
became unreachable. Recovery required a physical power cycle. After the board
returned, the service state showed the writer had passed and the player was
playing, but the black-screen/SSH-loss window itself could not be collected
before recovery.

Because C15.2.2 required no power cut and this new window remains unclassified,
the card stays blocked:

```text
post_wizard_black_screen_observed=true
ssh_lost_after_retest=true
emergency_physical_power_cycle_recovery=true
planned_power_cut_tested=false
c12_4_power_cut_tested=false
c15_2_2_status=blocked
```

## Decision

The wizard interruption and password-toggle bugs are fixed, but a new
post-wizard black-screen/SSH-loss blocker must be classified before generating a
new image. C16/player remains blocked.

## C15.2.3 Follow-Up

C15.2.3 added persistent post-wizard monitoring and repeated the F10/writer flow.
The black-screen/SSH-loss window did not reproduce: SSH, NetworkManager, player,
MPV, playback, and session cleanup stayed healthy through `post_restore_t+30s`
and `session_done`. C15.2.3 therefore releases a new image rebuild attempt, but
batch flash, dispatch, and C16 remain blocked until the rebuilt image passes
clean-board validation.

## Evidence

`docs/evidence/candidate-a/runs/20260513T200036Z-c15-2-2-clean-board-wizard-setup-interruption-fix/`
