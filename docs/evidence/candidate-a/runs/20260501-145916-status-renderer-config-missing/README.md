# Status Renderer Config Missing - Dev Board

Date: 2026-05-01

## Objective

Validate A1.4: experimental Dadooh status renderer for `config_missing`,
without running the renderer together with the main player MPV.

Only the development board was used. The homologation board was not touched.

## Implementation

A1.4 added `totem_status_renderer.sh`, a small MPV-based renderer for the
public status SVG. The launcher starts it only when the player must not run,
initially in `config_missing`.

The renderer uses explicit DRM/KMS output flags:

- `--vo=gpu`
- `--gpu-context=drm`
- `--ao=null`

The renderer does not start `kiosk.py`, does not read private config, does not
access the network and does not write under the application directory.

## Config Missing Test

The test used a temporary service override pointing to a missing config path.
The real private config was not removed, edited or printed.

Observed while the override was active:

- Service active: `active`
- Public state: `config_missing`
- Public display flag: `true`
- Public config state: `missing`
- Public player state: `not_started`
- Public service state: `active`
- Public error code: `CONFIG_MISSING`
- `status.json` generated: yes
- `status.svg` generated: yes
- `kiosk.py` process count: `0`
- Main player MPV count: `0`
- Renderer script count: `1`
- Renderer MPV count: `1`
- `systemctl --failed`: `0`
- Sanitization check: OK

This confirms the player did not run together with the renderer in
`config_missing`.

## Human Observation

Operator confirmation: observed.

The screen showed Dadooh/configuration pending or an equivalent status screen.

## Restore To Player

After the visual validation, the temporary override was removed and the service
was restarted.

Observed after restore:

- Public state: `player_running`
- Public display flag: `true`
- Public config state: `valid`
- Public player state: `running`
- Public service state: `active`
- Public error code: `None`
- App playback state: `playing`
- App MPV running flag: `true`
- `kiosk.py` process count: `1`
- Main player MPV count: `1`
- Renderer script count: `0`
- Renderer MPV count: `0`
- Service active: `active`
- `systemctl --failed`: `0`

This confirms the renderer was stopped before the player took over the display
again.

## Short Observer

Read-only observer against the existing player after restore:

- Duration: `180s`
- Samples: `180`
- IPC success: `180`
- IPC timeout: `0`
- IPC error: `0`
- Unique media aliases observed: `5`
- Alias transitions observed: `20`
- Aliases advancing: `5/5`
- Playing samples: `180`
- MPV running samples: `180`

The observer artifact is raw and intentionally ignored by Git.

## System Health

- `systemctl --failed`: `0`
- Kernel critical filter: `0`
- Sanitization check for public status files: OK

## Artifacts

Raw artifacts pulled into this directory and intentionally not tracked:

- `kiosky-service-observer-20260501-145422-0300.tar.gz`
- `totem-diag-20260501-145852-0300.tar.gz`

## Conclusion

Approved.

A1.4 displayed the public Dadooh status screen in `config_missing`, kept the
player stopped while the renderer was active, and restored cleanly to
`player_running` with the renderer stopped.

## Next Steps

- Review the launcher and renderer diff before commit.
- Keep `player_error` disabled until a dedicated validation is planned.
- Refine the SVG layout in A3 without changing the DRM/KMS process ordering.
