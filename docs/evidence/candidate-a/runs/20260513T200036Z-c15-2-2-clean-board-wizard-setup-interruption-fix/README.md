# C15.2.2 - Clean-board wizard setup interruption fix

Run identifier: `20260513T200036Z-c15-2-2-clean-board-wizard-setup-interruption-fix`

## Status

```text
c15_2_2_status=blocked
failure_type=pre_existing_untested_clean_board_bug
image_under_test=c15.2.1
image_sha256=ed6b74a37dd4213143ff456959a3a9ddb47d9a66046768131872932930dbf053

initial_evidence_collected_before_second_f10=true
wizard_clean_board_exit_cause=service_timeout
wizard_clean_board_exit_detail=wall_clock_jump_after_wifi_caused_false_openvt_deadline
last_trace_phase=openvt_still_running_after_deadline
trap_signal_seen=false
openvt_exited=false
wizard_rc=unavailable_initial_failure
config_missing_returned=true
failure_after_wifi=true
failure_during_environment_input=true

password_toggle_printable_v_removed=true
password_accepts_lowercase_v=true
password_accepts_uppercase_v=true
password_show_toggle_key=F2
password_show_toggle_fallback_key=Ctrl+P
password_not_logged=true

hotfix_applied_to_board=true
hotfix_applied_to_repo=true
f10_retest_passed=false
environment_input_survived=true
writer_passed=true
session_lock_cleanup_ok=true
player_restore_ok=true
post_wizard_black_screen_observed=true
ssh_lost_after_retest=true
forced_power_cycle_required=true
post_power_cycle_player_playing=true

ready_for_image_rebuild=false
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c16_player_audit=false
```

## Guardrails

```text
secrets_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
poweroff_executed=false
power_cut_tested=true
read_only_touched=false
kernel_touched=false
wifi_real_changed_only_by_existing_wizard_state=true
networkmanager_touched_only_by_existing_wizard_state=true
player_code_changed=false
c16_started=false
c12_readonly_blocked=true
c12_4_blocked=true
```

## Initial Failure Classification

C15.2.1 image build and offline validation passed, but clean-board validation
blocked during the first real setup. The operator connected Wi-Fi, then while
typing the environment value the wizard returned to `config_missing`.

Initial forensics were collected before pressing F10 again. The trace showed:

```text
last_trace_phase=openvt_still_running_after_deadline
openvt_exited=false
trap_signal_seen=false
```

The service status showed the settings session process was killed after the
deadline handling path. The trace timestamps jumped from the board's initial
pre-NTP date to the real date after Wi-Fi. The session was using wall-clock
`date +%s` for its openvt deadline, so NTP/time correction made the interactive
session look older than its timeout.

Classification:

```text
wizard_clean_board_exit_cause=service_timeout
detail=wall_clock_jump_after_wifi_caused_false_openvt_deadline
```

This is not treated as a regression. It is a latent clean-board setup bug that
was not covered by the prior hot-board and heuristic UI/UX validation.

## Hotfix

Changed the F10 settings session to use monotonic uptime from `/proc/uptime`
for openvt timeout tracking. This avoids false timeout after Wi-Fi/NTP time
steps.

Changed password visibility behavior:

- simple printable `V`/`v` no longer toggles password visibility;
- `v` and `V` remain normal password characters;
- F2 remains the advertised show/hide key;
- Ctrl+P is accepted as a non-printable fallback;
- public status/evidence still do not include password or SSID values.

Files changed in the repo:

```text
scripts/board/totem_open_settings_session.sh
scripts/board/totem_setup_visual_wizard.py
scripts/board/totem_appliance_manifest.json
scripts/qa/generate_ui_ux_gallery.py
scripts/build/derive_c15_2_1_homolog_image.py
```

The same session and wizard scripts were applied to the board under
`/opt/totem/bin/`.

## Retest Result

After hotfix and trace cleanup, the operator pressed F10 once and completed the
wizard. The retest validated:

```text
environment_input_survived=true
password_accepts_lowercase_v=true
password_accepts_uppercase_v=true
password_show_toggle_key=F2
writer_passed=true
real_config_written=true
session_lock_cleanup_ok=true
```

Post-retest trace/status after recovery showed:

```text
openvt_timeout_clock=monotonic
openvt_exited=true
wizard_rc=8
writer_rc=0
writer_result=passed
playback_state=playing
public_state=player_running
config_real_present=true
```

However, immediately after the operator completed the wizard, HDMI showed a
black screen and SSH became unreachable. The operator recovered with a physical
power cycle. Because the round required no power cut and the black-screen/network
loss window could not be collected before recovery, C15.2.2 remains blocked even
though the original wizard interruption and password-toggle bugs were fixed.

## Decision

```text
ready_for_image_rebuild=false
ready_for_batch_flash=false
ready_for_dispatch=false
ready_for_c16_player_audit=false
```

Next work should classify the post-wizard black screen / SSH-loss window before
building another image. C16/player remains blocked.

## Commands Run

Local:

```text
git status --short
git log --oneline -150
git diff --check
bash -n scripts/board/totem_visual_tty_guard.sh
bash -n scripts/board/totem_firstboot_gate.sh
bash -n scripts/board/totem_open_settings_session.sh
bash -n scripts/board/kiosky_service_launcher.sh || true
bash -n scripts/build/run_c14_2_1_build_shipping_homolog_image.sh || true
bash -n scripts/remote/validate_c14_2_1_clean_board.sh || true
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_updatectl.py self-test || true
python3 -m json.tool scripts/board/totem_appliance_manifest.json >/dev/null
python3 -m py_compile scripts/board/totem_setup_visual_wizard.py scripts/qa/generate_ui_ux_gallery.py scripts/build/derive_c15_2_1_homolog_image.py
```

Board:

```text
initial sanitized forensics before second F10
scp hotfix scripts to /tmp
install hotfix scripts to /opt/totem/bin
bash -n /opt/totem/bin/totem_open_settings_session.sh
python3 /opt/totem/bin/totem_setup_visual_wizard.py --self-test
systemctl daemon-reload
systemctl reset-failed totem-open-settings.service
trace cleanup before retest
post-power-cycle sanitized runtime collection
```

The local `totem_updatectl.py self-test` still returns the known non-appliance
permission error for `/data` in this host context and was intentionally run with
`|| true`.

## Prohibited Data

No SSH password, GitHub token, API key, real API URL, environment identifier,
SSID, Wi-Fi password, private seed contents, real config contents, NetworkManager
profiles, IP, MAC, DNS, raw logs, media cache, or private media were included in
this evidence.
