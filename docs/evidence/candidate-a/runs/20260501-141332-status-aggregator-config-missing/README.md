# Status Aggregator Config Missing - Dev Board

Date: 2026-05-01

## Objective

Validate A1.3: safe `config_missing` detection in the launcher before starting
the player.

The test used only the development board. Homologation was not touched.

## Implementation Scope

A1.3 adds a local launcher check before `kiosky-player` is started. The check
confirms that the config file exists, is readable, is valid JSON, has an object
as its root, and contains essential non-empty fields.

The launcher does not print config content, field values, API URLs, keys,
environment identifiers, station identifiers, media paths, or payloads.

If the config check fails while HDMI is connected, the launcher:

- writes raw launcher state `config_missing`;
- calls the status aggregator;
- keeps the service `active`;
- does not start `kiosk.py`;
- does not start MPV;
- retries periodically.

No visual renderer was started.

## Local Validation

Commands run locally before SSH:

- `bash -n scripts/board/kiosky_service_launcher.sh`
- `bash scripts/board/smoke_launcher_status_integration.sh`
- `python3 -m py_compile scripts/board/totem_status_aggregate.py`
- `python3 -m py_compile scripts/board/totem_status_render_preview.py`
- `git diff --check`

All passed.

The smoke test covered:

- missing config path produces aggregate `config_missing`;
- app fake is not called when config is missing;
- `/tmp` is rejected as aggregator output directory;
- subdirectory under `/tmp` is accepted;
- missing aggregator does not break launcher status writes;
- slow aggregator times out without breaking launcher flow;
- periodic refresh still aggregates `running` while a fake child is alive and
  stops after the child exits.

## Board Test

The board test used a temporary service environment override pointing to a
missing config path under `/tmp`. The real config was not removed, edited, read
aloud, or printed.

Observed state while override was active:

- Service enabled: `enabled`
- Service active: `active`
- Public aggregate state: `config_missing`
- Public display flag: `true`
- Public config state: `missing`
- Public player state: `not_started`
- Public service state: `active`
- Public error code: `CONFIG_MISSING`
- Launcher state: `config_missing`
- Launcher display flag: `true`
- `status.json` generated: yes
- `status.svg` generated: yes
- `kiosk.py` process count: `0`
- `mpv` process count: `0`
- DRM connector count reported as connected: `1`
- Failed units: `0`
- Sanitization check: OK

## Restore Check

After the config-missing validation, the temporary override was removed and the
service was restarted.

Observed restored state:

- Service active: `active`
- Public aggregate state: `player_running`
- Public player state: `running`
- App playback state: `playing`
- App MPV running flag: `true`
- `kiosk.py` process count: `1`
- `mpv` process count: `1`
- Failed units: `0`
- Kernel critical entries: `0`

## Sanitization

The public status files were checked for sensitive field names and private
patterns. No private values were printed or copied into this README.

Raw artifacts were not collected for this run.

## Conclusion

A1.3 behaved as intended on the development board: with HDMI connected and a
missing config override, the service stayed active, the aggregate status became
`config_missing`, and neither `kiosk.py` nor MPV was started.

After removing the temporary override, the appliance returned to normal
`player_running` behavior.

## Recommended Next Step

Review the A1.3 launcher diff and smoke test. After review, commit the launcher,
docs, and this sanitized README only.
