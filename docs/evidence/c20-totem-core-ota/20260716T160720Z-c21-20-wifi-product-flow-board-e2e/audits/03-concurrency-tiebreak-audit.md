# Independent concurrency tie-break audit

Verdict: **NON-BLOCKER hardening**.

The shared temporary Wi-Fi secrets path is real. Two privileged callers that
launch the Python wizard directly could race by overwriting or removing the
same `secrets.json`.

The complete supported production path does not create that topology:

- `totem-open-settings.production.service` is a singleton `Type=oneshot` unit;
- the settings trigger starts that service, not the Python wizard directly;
- the trigger suppresses starts while the settings-session lock exists;
- `totem_open_settings_session.sh` acquires the lock atomically before scratch
  cleanup and before launching the wizard;
- a duplicate session exits with rc `23`;
- the wrapper also refuses to launch while another setup-wizard process exists;
- normal and stop-post cleanup remove leftover session state.

The fixed secrets path predates C21.20 and was introduced with the original
C9.9 visual wizard. It is therefore neither a C21.20 regression nor reachable
through normal product operation.

Follow-up hardening: key the secrets path by `TOTEM_SETTINGS_SESSION_ID` or
place it under the session-specific wizard output directory, then retain
cleanup support for the legacy path.

The audit used read-only repository inspection and no board or systemd action.
