# Status Aggregator HDMI Missing/Reconnection - Dev Board

Date: 2026-05-01

## Objective

Validate HDMI disconnect/reconnect behavior on the development board with the A1.2 status aggregator integrated into the launcher, without visual renderer, without extra MPV process, and without direct DRM device access.

Homologation board was not used.

## Artifacts

- `status-hdmi-observer-20260501-123259-0300.tar.gz` - raw short observer artifact, intentionally ignored by Git.
- `totem-diag-20260501-123757-0300.tar.gz` - raw diagnostic artifact, intentionally ignored by Git.

## Initial State With HDMI Connected

- Service enabled: `enabled`
- Service active: `active`
- Failed units: `0`
- Launcher state: `running`
- Launcher display flag: `true`
- Public aggregate state: `player_running`
- Public display flag: `true`
- Public config state: `valid`
- Public player state: `running`
- Public service state: `active`
- Public error code: `None`
- Public message: `Exibicao em andamento`
- Public action hint: `Nenhuma acao necessaria.`
- `status.json` generated: yes
- `status.svg` generated: yes
- `kiosk.py` process count: `1`
- `mpv` process count: `1`
- DRM connector count reported as connected: `1`
- Sanitization check: OK

## Boot Without HDMI

After operator disconnected HDMI, the development board was rebooted.

- Service enabled: `enabled`
- Service active: `active`
- Failed units: `0`
- Launcher state: `display_missing`
- Launcher display flag: `false`
- Public aggregate state: `display_missing`
- Public display flag: `false`
- Public config state: `unknown`
- Public player state: `not_started`
- Public service state: `active`
- Public error code: `DISPLAY_MISSING`
- Public message: `Tela nao detectada`
- Public action hint: `Verifique o cabo HDMI e a energia da tela.`
- `status.json` generated: yes
- `status.svg` generated: yes
- `kiosk.py` process count: `0`
- `mpv` process count: `0`
- DRM connector count reported as connected: `0`
- Launcher logged one `display_missing` event and no `starting_app` event before HDMI reconnection.
- Aggregator warning count: `0`
- Kernel critical entries: `0`
- Sanitization check: OK

## HDMI Reconnection

After operator reconnected HDMI:

- Launcher state: `running`
- Launcher display flag: `true`
- DRM connector count reported as connected: `1`
- `status.json` generated: yes
- `status.svg` generated: yes
- `kiosk.py` process count: `1`
- `mpv` process count: `1`
- App playback state: `playing`
- App MPV running flag: `true`
- Failed units: `0`
- Kernel critical entries: none reported by the direct critical query.
- Sanitization check: OK

Important deviation:

- Public aggregate state remained `starting_player` after reconnection, even while the launcher was `running`, app playback was `playing`, and MPV was running.
- Observed public fields after reconnection:
  - `state=starting_player`
  - `display_connected=True`
  - `player_state=starting`
  - `service_state=active`
  - `error_code=None`

This suggests the A1.2 aggregator call happens before the player status file has converged to `playing`, and there is no later refresh while the child process keeps running.

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

The status JSON/SVG checks looked for private status fields and sensitive patterns:

- `api_key`: not found
- `api_url`: not found
- `environment_id`: not found
- `station_id`: not found
- private IPv4 patterns: not found
- private local paths in public status output: not found

Raw diagnostic and observer archives were kept out of Git.

## Conclusion

HDMI-missing boot behavior is correct for A1.2: the launcher stays active, reports `display_missing`, does not start `kiosk.py` or MPV, generates aggregate status files, and does not enter an aggressive restart loop.

HDMI reconnection restarts the player path correctly: the launcher returns to `running`, the app reports `playing`, MPV is running, IPC is healthy, and media aliases advance.

The status aggregator did not converge back to `player_running` after reconnection. This is a product-visible state freshness issue and should be fixed before testing this path on homologation.

## Recommended Next Step

Implement a small A1.2.1 hardening change: after launching the player, perform one or more delayed best-effort aggregator refreshes, or run a lightweight periodic refresh while the child process is alive. Keep the existing timeout, warning rate limit, no renderer, no extra MPV, and no DRM access.
