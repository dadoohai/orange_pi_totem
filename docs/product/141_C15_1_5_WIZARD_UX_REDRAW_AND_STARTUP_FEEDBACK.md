# 141 - C15.1.5 - Wizard UX redraw and startup feedback

## Status

```text
c15_1_5_status=passed
ready_for_image_rebuild=true
ready_for_c16_player_audit=true
c16_started=false
```

C15.1.4 passed the Wi-Fi UX refresh, but left three UX follow-ups before the
C15.2.1 image rebuild: excess operator text, visible redraw backlog when
holding Backspace, and weak feedback during startup/transitions.

## Changes

The wizard copy was reduced without changing the writer contract:

- panel content is capped at three items;
- subtitles are constrained to one short line;
- Wi-Fi, password, environment, review, and completion screens use shorter
  titles, footers, and action text.

Text fields now coalesce rapid Backspace/typing input and debounce full-screen
renders. The self-test covers repeated Backspace input and keeps the effective
render rate at or below 12 fps. `Enter`, `Esc`, `Ctrl+B`, `Ctrl+U`, max length,
hidden password, and `F2/V` password show/hide remain covered.

Startup feedback now uses the existing framebuffer splash for:

- `boot`;
- `player`;
- `setup`;
- `saving`;
- `config_pending`.

The player unit renders a short `player` splash before starting, and the
launcher can render `config_pending` or `player` feedback in controlled gaps.

## Hotfix Correction

During board validation, the first splash status path was written directly under
`/tmp`. The splash helper made the status parent private, which changed `/tmp`
to mode `0700` and prevented the `totem` user from creating/using MPV runtime
paths. This was corrected by:

- preventing the splash helper from chmodding `/tmp` itself;
- moving splash status files under `/tmp/dadooh-splash/...`;
- restoring board `/tmp` to mode `1777`;
- restarting `kiosky-player.service` to restore MPV.

After correction, the board had `kiosky-player.service=active`, MPV present,
`totem-open-settings.service=inactive`, and session lock absent.

## Validation

Local and on-board checks passed:

```text
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 -m json.tool scripts/board/totem_appliance_manifest.json
```

Offline previews were generated for simplified wizard screens, Wi-Fi/password
states, and splash modes. Public artifacts remained sanitized.

The physical wizard run reached `openvt_exited`, had no `trap_signal`, writer
passed, lock cleaned, and player restored. The operator confirmed that holding
Backspace improved and now stops immediately after release. The interface is
still not the desired final polish level, but it improved enough to close this
card as a milestone and continue visual PDCA in a follow-up.

One regression was observed during the transition back to player: the final
`Inicializando player` splash briefly changed to another orientation before MPV
entered with the correct orientation again. This was fixed in the repo before
commit by removing duplicate player splash renders. The F10 session remains
responsible for the post-wizard player splash because it knows the selected
rotation; the player unit no longer draws a second player splash; the launcher
skips its own player splash once when the F10 session already rendered it; and
cleanup no longer draws over an already-active player.

After SSH returned, the final splash-orientation patch was applied to the
running lab board as well. Runtime sanity confirmed the effective player unit no
longer has a `totem_visual_splash.py player` `ExecStartPre`, and the board stayed
with player active, MPV present, `/tmp` at `1777`, and no settings-session lock.
The next physical F10 pass should still observe the transition visually, but the
duplicate render source has been removed both in the repo and on-device.

## Decision

```text
ready_for_image_rebuild=true
ready_for_c16_player_audit=true
```

C15.2.1 image rebuild is released from the C15.1.5 side. C16/player remains
unstarted in this card, but remains eligible for the next audit card. Broader
wizard visual polish should be handled as a separate PDCA-style UX effort for
the full wizard interface, not for the splash.

## Evidence

`docs/evidence/candidate-a/runs/20260513T171852Z-c15-1-5-wizard-ux-redraw-startup-feedback/`
