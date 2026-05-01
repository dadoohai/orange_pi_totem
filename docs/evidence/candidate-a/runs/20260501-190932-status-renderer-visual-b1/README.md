# Status Renderer Visual B1 - Dev Board

Date: 2026-05-01

## Objective

Validate B1: refined public `config_missing` visual screen for Dadooh, keeping
the renderer separate from the main player and preserving the Fase A process
ordering.

Only the development board was used. The homologation board was not touched.

## Visual Changes

B1 updates the public SVG status screen with:

- clear textual Dadooh brand;
- large "Configuração pendente" title;
- short non-technical message;
- public code `CONFIG_MISSING`;
- "Player parado com segurança";
- reserved "Configuração assistida" area marked as "Em breve";
- explicit text that no QR is active yet.

No functional QR code, Wi-Fi setup, hotspot, portal, backend activation,
operator config writing, reset, telemetry or `kiosky-player` change was added.

## Config Missing State

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

## Human Observation

Operator confirmation: observed.

The screen showed Dadooh, "Configuração pendente", a clear message for a
non-technical operator, "Player parado com segurança" and the public code
`CONFIG_MISSING`.

## Player And Renderer Separation

In `config_missing`, the renderer was active while:

- `kiosk.py=0`;
- main player MPV `0`;
- renderer MPV `1`.

After removing the temporary override and restarting the service:

- renderer script `0`;
- renderer MPV `0`;
- `kiosk.py=1`;
- main player MPV `1`.

This confirms the player and renderer did not run together in the validated
path.

## Restore To Player Running

After the visual validation, the temporary override was removed and the service
was restarted.

Observed after restore:

- Public state: `player_running`
- Public display flag: `true`
- Public config state: `valid`
- Public player state: `running`
- Public service state: `active`
- Public error code: `None`
- Service active: `active`
- `kiosk.py` process count: `1`
- Main player MPV count: `1`
- Renderer script count: `0`
- Renderer MPV count: `0`
- `systemctl --failed`: `0`

## Short Observer

Read-only observer against the restored player:

- Duration: `180s`
- Samples: `180`
- IPC success: `180`
- IPC timeout: `0`
- IPC error: `0`
- Unique MPV aliases observed: `5`
- Unique status aliases observed: `5`
- Alias transitions observed: `19`
- Aliases advancing: `5/5`
- Playing samples: `180`
- MPV running samples: `180`

The observer summary was sanitized and did not print config content, media
paths, URLs or private identifiers.

## System Health

- `systemctl --failed`: `0`
- Kernel priority `crit` count in current boot: `1`
- Kernel oops/panic/filesystem critical filter: `0`
- Kernel MMC timeout/reset filter: `0`
- Kernel voltage filter: `0`
- Kernel thermal filter: `4`
- Broad kernel fail/error filter: `9`

The broad kernel filter was not zero for the current boot. It did not prevent
restore to `player_running`, but the raw diagnostic bundle should be reviewed
before treating this as production evidence.

## Sanitization

Public status files and the observer summary passed the sensitive-term check for
the B1 validation scope.

No private config, API key, API URL, environment ID, station ID, SSID, private
URL, private payload, real media path or stack trace was published in this
README.

Raw diagnostic artifacts were generated on the development board and were not
copied into Git.

## Conclusion

Approved for B1 visual validation on the development board, with one operational
note: the current-boot kernel broad filter was nonzero and should be reviewed in
the raw diagnostic bundle before any production release decision.

The B1 visual screen met the UX goal, kept private data out of the public status
surface, and restored cleanly to the validated player path.

## Next Steps

- Review the code and documentation commit.
- Review raw board diagnostics for the nonzero kernel filter.
- Keep Wi-Fi, hotspot, QR activation, portal and operational maintenance out of
  B1.
- Keep `player_error` operational rendering disabled until a dedicated retry
  validation is planned.

