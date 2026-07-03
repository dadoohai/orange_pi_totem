# C18 Status/MPV Watchdog Lab Overlay

This records a controlled lab overlay on the board for commit `5a79654`, which adds an external status/MPV watchdog in the fixed player supervisor path.

What was done:
- backed up the existing `/opt/totem/bin/kiosky_service_launcher.sh` hash;
- installed the new `kiosky_service_launcher.sh`;
- installed `/opt/totem/bin/totem_player_status_mpv_watchdog.py`;
- ran syntax/self-test checks on the board;
- restarted `kiosky-player.service`;
- collected 90s playback health.

Observed result:
- service stayed active;
- watchdog process was running against the current player child;
- playback health passed;
- `status_advanced_without_mpv=false`;
- `mpv_restart=0`;
- `NRestarts_delta=0`.

Non-claims:
- this is a lab overlay, not a flashed image identity;
- this does not make the previous `rollback_after_identify_links` power-loss checkpoint pass;
- this does not claim H2, stable, production, or public thaw;
- this does not prove recovery from a live mismatch event yet, only that the watchdog installs, runs, and does not disturb healthy playback.

Source archive sha256: `1d04c7941438a7c360b44ef25888f47d98542ff416f66bc5418e4070dbaddbb9`.
