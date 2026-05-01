# Status Aggregator Refresh HDMI Validation - Dev Board

Date: 2026-05-01

## Objective

Validate A1.2.1 on the development board: periodic best-effort status
aggregator refresh while the player child process is alive.

The goal was to confirm that the aggregate status converges to
`player_running` after HDMI reconnection, without visual renderer, without
extra MPV process, and without direct `/dev/dri` access.

Homologation board was not used.

## A1.2.1 Refresh

The launcher now keeps a refresh loop alive only while the player child is
alive. The loop calls the existing status aggregator using the existing timeout
guard. It is stopped when the child exits and also during launcher shutdown.

Variables used:

- `TOTEM_STATUS_REFRESH_SEC`: default `5`
- `TOTEM_STATUS_AGGREGATOR_TIMEOUT_SEC`: default `2`

The refresh remains best-effort: aggregator failure or timeout does not stop the
launcher or player.

## Artifacts

- `status-hdmi-observer-20260501-131759-0300.tar.gz` - raw short observer artifact, intentionally ignored by Git.
- `totem-diag-20260501-132105-0300.tar.gz` - raw diagnostic artifact, intentionally ignored by Git.

## Local Validation Before SSH

- `bash -n scripts/board/kiosky_service_launcher.sh`: OK
- `bash scripts/board/smoke_launcher_status_integration.sh`: OK
- `python3 -m py_compile scripts/board/totem_status_aggregate.py`: OK
- `python3 -m py_compile scripts/board/totem_status_render_preview.py`: OK
- `git diff --check`: OK

The smoke test covered:

- `/tmp` rejected as aggregator output directory;
- `/tmp/dadooh-status-test` accepted;
- missing aggregator does not break launcher status writes;
- slow aggregator times out without breaking launcher flow;
- periodic refresh calls the aggregator more than once while a fake child is
  alive;
- refresh loop stops after the child exits.

## HDMI Connected After Deploy

After deploying A1.2.1 and restarting `kiosky-player.service`:

- Service enabled: `enabled`
- Service active: `active`
- Public aggregate state: `player_running`
- Public display flag: `true`
- Public config state: `valid`
- Public player state: `running`
- Public service state: `active`
- Public error code: `None`
- Launcher state: `running`
- Launcher display flag: `true`
- App playback state: `playing`
- App MPV running flag: `true`
- `status.json` generated: yes
- `status.svg` generated: yes
- `kiosk.py` process count: `1`
- `mpv` process count: `1`
- DRM connector count reported as connected: `1`
- Failed units: `0`
- Sanitization check: OK

## Boot Without HDMI

After operator disconnected HDMI, the development board was rebooted.

- Service enabled: `enabled`
- Service active: `active`
- Public aggregate state: `display_missing`
- Public display flag: `false`
- Public config state: `unknown`
- Public player state: `not_started`
- Public service state: `active`
- Public error code: `DISPLAY_MISSING`
- Launcher state: `display_missing`
- Launcher display flag: `false`
- `status.json` generated: yes
- `status.svg` generated: yes
- `kiosk.py` process count: `0`
- `mpv` process count: `0`
- DRM connector count reported as connected: `0`
- Failed units: `0`
- Direct kernel critical query: no entries
- Sanitization check: OK

## HDMI Reconnection

After operator reconnected HDMI:

- Service active: `active`
- Public aggregate state: `player_running`
- Public display flag: `true`
- Public config state: `valid`
- Public player state: `running`
- Public service state: `active`
- Public error code: `None`
- Public message: `Exibicao em andamento`
- Public action hint: `Nenhuma acao necessaria.`
- Launcher state: `running`
- Launcher display flag: `true`
- App playback state: `playing`
- App MPV running flag: `true`
- `status.json` generated: yes
- `status.svg` generated: yes
- `kiosk.py` process count: `1`
- `mpv` process count: `1`
- DRM connector count reported as connected: `1`
- Failed units: `0`
- Kernel critical entries: `0`
- Sanitization check: OK

Result: the aggregate status converged to `player_running` after reconnection.

## Short Observer

Read-only observer against the existing MPV IPC:

- Duration: `180s`
- Samples: `180`
- IPC success: `180`
- IPC timeout: `0`
- IPC error: `0`
- Unique media aliases observed: `5`
- Alias transitions observed: `19`
- `5/5` aliases advanced: `true`
- Playing samples: `180`
- MPV running samples: `180`

The observer did not start a new player or renderer.

## Sanitization

The status JSON/SVG checks looked for private status fields and sensitive
patterns:

- `api_key`: not found
- `api_url`: not found
- `environment_id`: not found
- `station_id`: not found
- private IPv4 patterns: not found
- private local paths in public status output: not found

Raw diagnostic and observer archives were kept out of Git.

## Conclusion

A1.2.1 fixed the freshness issue found in
`20260501-123806-status-aggregator-hdmi-missing`: after HDMI reconnection, the
player starts, app status reaches `playing`, MPV remains active, and the
aggregate status now converges to `player_running`.

The HDMI-missing path remains correct: no app or MPV process is started while
the display is absent, and the aggregate status stays `display_missing`.

## Recommended Next Step

Review the A1.2.1 launcher diff and this evidence. After review, commit the
code, docs, and sanitized README only. Do not add raw `.tar.gz` artifacts.
