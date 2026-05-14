# 169 - C17.5 - Totem-Core Remote Update MVP

Status: passed

C17.4.2 passed clean-card validation and could have opened C18 from a purely
functional image perspective. C17.5 was opened first because the next UX
iteration is the `environment_id` field, and rebuilding/flashing images for
small wizard/configurator changes is too slow.

C17.5 does not start C18 and does not change scheduler, sync, duration,
playlist, loop or `exposure_time_ms`.

## Decision

`c17_5_status=passed`

`ready_for_c17_6_environment_input_update=true`

`ready_for_c18_player_audit=false`

C17.6 should deliver the environment input UX as the first `totem-core` update.

## Component

New component:

`component=totem-core`

The updater keeps the existing schema:

`schema=dadooh.totem.update.v1`

This was chosen to reuse the C14 GitHub Releases flow, manifest SHA validation,
atomic `current`/`previous` symlink model and rollback behavior.

## Difference From Kiosky-Player Updates

`kiosky-player` updates replace the Python player app under:

`/data/apps/kiosky-player`

and restart `kiosky-player.service` for health validation.

`totem-core` updates replace appliance UI/configuration helpers under:

`/data/core/totem`

and do not restart the player unless a caller later decides that is necessary.
The MVP scope is wizard/configurator, splash, status helpers, Wi-Fi adapter,
config contract validator, firstboot/pre-config helpers and settings-session
scripts.

Out of scope for this MVP:

- systemd unit updates;
- kernel, U-Boot, DTB or BSP;
- NetworkManager updates;
- updater self-update;
- read-only/C12;
- player timing/sync/duration/loop.

## Layout

Runtime layout:

```text
/data/core/totem/releases/<version>/
/data/core/totem/current -> releases/<version>
/data/core/totem/previous -> releases/<previous>
/data/core/totem/state.json
```

Fallback layout:

```text
/opt/totem/core-fallback/bin/<script>
```

Wrappers in `/opt/totem/bin` dispatch to:

1. `/data/core/totem/current/bin/<script>` when present;
2. `/opt/totem/core-fallback/bin/<script>` otherwise.

Python wrappers are Python files so existing calls like
`python3 /opt/totem/bin/totem_setup_visual_wizard.py` continue to work.

## Safety Rules

`totem-updatectl` now supports:

```text
status --component totem-core
self-test --component totem-core
apply-github-latest --component totem-core --repo dadoohai/orange_pi_totem
apply-local --component totem-core <manifest>
rollback --component totem-core
```

For `totem-core`, apply is blocked when:

- `/run/totem/settings-session.lock` exists;
- `totem-open-settings.service` is active or activating;
- a settings trigger request exists.

Health checks run before activation:

- visual wizard self-test;
- Wi-Fi adapter self-test;
- splash self-test;
- config contract self-test;
- shell syntax checks;
- C17.4.1 restore-order static check.

## Package

Good package:

`c17.5-core-mvp-20260514T204200Z`

Payload SHA256:

`8a7724382b1c786caaf957d90bf35d79271cb777352ddc23993a0d0df72843e2`

GitHub release:

`totem-core-c17.5-core-mvp-20260514T204200Z`

A first package, `c17.5-core-mvp-20260514T202900Z`, was superseded before board
apply because the splash self-test had a stale filename assertion for
`config_pending`.

## Board Validation

Bootstrap was applied to the C17.4.2 board over SSH. It did not call writer,
did not alter real config, did not alter Wi-Fi, did not reboot and did not run
apt or pip.

Validation passed:

- fallback installed and tested;
- wrappers installed;
- `totem-updatectl self-test --component totem-core` passed;
- GitHub release discovery passed;
- remote apply passed;
- rollback to fallback passed;
- good release was reapplied;
- wrapper route confirmed `/data/core/totem/current/bin`;
- fallback route confirmed `/opt/totem/core-fallback/bin`;
- settings lock guard blocked apply;
- short settings preview opened the wizard and restored player;
- writer was not called;
- real config was not written;
- playback was still `playing` after preview restore.

## Limitations

The F10 key itself was not physically pressed during C17.5. The same
`totem_open_settings_session.sh` path was exercised with a controlled preview
session and the wizard opened without writing config.

Systemd unit update and updater self-update remain out of scope. If a future
change requires unit ordering changes, that should be an image or a separate
conservative remote-update design, not this MVP.
