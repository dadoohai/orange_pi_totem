# 140 - C15.1.4 - Wi-Fi setup UX refresh

Status: **passed**
Date: 2026-05-13
Branch: `foundation-v0.1`
Preceding card: `C15.1.3`

## Context

C15.1.3 passed the F10 reliability work and unblocked the next image rebuild.
Before starting C15.2.1, C15.1.4 was opened to improve the Wi-Fi setup screen in
the visual wizard. C16/player work was not started.

## Change

The Wi-Fi list now uses a paginated local screen instead of showing only the
first visible entries. It keeps the existing NetworkManager adapter boundary and
does not alter player code.

Implemented behavior:

- Up/Down scroll the selection across the full list.
- PageUp/PageDown move by one visual page when the terminal emits those keys.
- `R` refreshes immediately.
- The list auto-refreshes every 10 seconds while the operator stays on the Wi-Fi
  list screen.
- Refresh preserves the selected network by local SSID when still present; if it
  disappears, the selection stays near the previous index and a local notice is
  shown.
- Networks are sorted by descending signal and duplicate SSIDs are grouped by
  the strongest signal.
- Empty SSIDs are hidden.
- Signal is shown locally as numeric percent, bars, and a text bucket.
- Open networks are labelled `Aberta`; secured networks are labelled
  `Protegida`.
- Wi-Fi password input remains hidden by default.
- `F2` and `V` both toggle local password visibility. `V` is the fallback for
  consoles that do not deliver function keys consistently.

The adapter allowlist was extended only for read-only Wi-Fi listing with
`nmcli -t -f SSID,SIGNAL,SECURITY device wifi list --rescan yes`. It does not
connect, disconnect, restart NetworkManager, alter profiles, or change Wi-Fi by
itself. Real Wi-Fi changes still happen only through the already-gated wizard
apply flow.

## Privacy

Real SSID and password may appear only on the HDMI wizard screen during local
operation. They are not written to product docs, evidence, public status, or
summaries. Public metadata remains count/bucket/result based.

The synthetic preview uses test network names only in private preview SVGs and
keeps the preview status sanitized.

## Validation

Local checks passed:

```text
python3 -m py_compile scripts/board/totem_setup_visual_wizard.py scripts/board/totem_wifi_nm_adapter.py
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 -m json.tool scripts/board/totem_appliance_manifest.json
python3 scripts/board/totem_setup_visual_wizard.py --wifi-list-preview
```

Board hotfix was applied to:

```text
/opt/totem/bin/totem_setup_visual_wizard.py
/opt/totem/bin/totem_wifi_nm_adapter.py
```

Board self-tests passed after the hotfix. The physical test confirmed:

```text
paginated_wifi_list=true
wifi_pages_observed=2
wifi_network_count_observed=10
signal_percent_visible=true
password_toggle_available=true
password_toggle_key=F2/V
password_toggle_retest_passed=true
terminal_login_visible=false
keyboard_echo_visible=false
config_missing_returns_during_wizard=false
trace_openvt_exited=true
trace_trap_signal=false
session_lock_cleanup_ok=true
player_restore_ok=true
```

The operator completed the wizard and the existing writer path passed:

```text
wifi_apply_attempted=true
wifi_apply_result=passed
writer_called=true
writer_rc=0
writer_result=passed
real_config_written=true
backup_created=true
```

No `kiosky-player` files were changed. No apt, pip, upgrade, reboot, poweroff,
power cut, read-only, kernel, U-Boot, DTB, BSP, or rootfs work was performed.

## Follow-Ups

Two non-blocking legacy UX issues were observed and should be handled in a
separate card:

- the wizard has too much instructional text on several screens;
- holding Backspace can queue repeated redraws, causing visible blinking until
  the input backlog drains.

They were not mixed into C15.1.4 because the Wi-Fi screen refresh, navigation,
signal clarity, and password toggle acceptance criteria passed.

## Decision

```text
c15_1_4_status=passed
ready_for_image_rebuild=true
ready_for_c16_player_audit=true
c16_started=false
```

C15.2.1 image rebuild can proceed. C16/player audit remains unstarted, but it is
still unblocked for the next card.

## Evidence

`docs/evidence/candidate-a/runs/20260513T163457Z-c15-1-4-wifi-setup-ux-refresh/`
