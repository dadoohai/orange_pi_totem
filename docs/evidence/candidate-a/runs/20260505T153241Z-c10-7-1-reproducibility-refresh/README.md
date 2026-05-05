# C10.7.1 - Reproducibility Refresh After C10.6.2

Date: 2026-05-05

Purpose: refresh C10.7 after C10.6.2 without repeating functional tests and
without operational changes.

## Commands

```bash
git status --short
git log --oneline -15
git diff --check
bash -n scripts/remote/run_c10_7_reproducibility_audit.sh
bash -n scripts/remote/run_c10_6_2_apply_settings_from_f10.sh
scripts/remote/run_c10_7_reproducibility_audit.sh root@192.168.1.147 --summary --out-dir /tmp/dadooh-c10-7-reproducibility-audit/20260505T153241Z-c10-7-1-refresh
```

Additional read-only observation was run to inspect only public fields, unit
states, process counts, `orientation.json` metadata and `/run/dadooh-settings`
file presence. It did not read `/data/config/config.json`.

## Repo State

HEAD during refresh:

```text
1089f8253c5ed1854f0d997bf05f73c87e75dbcf Fix F10 settings apply prefill flow
```

Required commits were present:

```text
ede0fbc Add C10.6.2 F10 settings apply flow
4d65f28 Add C10.7 reproducibility audit
```

Worktree status at start: clean.

## Read-only Board Snapshot

Confirmed without reading config real:

- `systemctl_failed_count=0`;
- `totem-settings-trigger.service=active/enabled`;
- `dadooh-visual-splash.service=active/enabled`;
- `orientation.json` exists;
- `orientation_json.schema_version=dadooh-display-orientation.v1`;
- `orientation_json.rotation_deg=270`;
- `orientation_json.orientation_label=portrait_left`;
- `orientation_json` metadata: `0644 root:root`;
- expected C10.6.2 board scripts were present in `/opt/totem/bin`;
- `apply-policy.json` was not present in `/run/dadooh-settings`;
- playback status file reported `playing`.

Transient state observed during refresh:

- `totem-open-settings.service=activating`;
- `kiosky-player.service=inactive/enabled`;
- setup process count was nonzero;
- `/run/dadooh-settings/session.lock` was present;
- public status was `maintenance_placeholder`.

This means C10.7.1 successfully incorporates the C10.6.2 reproducibility delta,
but this particular refresh should not be used as proof of final
`player_running` state. It likely overlapped with a local F10/open-settings
session. No recovery action was taken.

## C10.6.2 Delta Reflected

C10.8 must include:

- `scripts/remote/run_c10_6_2_apply_settings_from_f10.sh`;
- updated `totem_setup_visual_wizard.py`;
- updated `totem_open_settings_session.sh`;
- updated `totem-open-settings.service`;
- `totem-settings-trigger.service`;
- `totem-open-settings.service`;
- F10 persistent trigger flow;
- setup -> private handoff -> writer scripts;
- public `orientation.json` contract;
- splash/transition guardrails using `orientation.json`;
- `/run/dadooh-settings` runtime directory and cleanup policy;
- C10.6.2 docs and sanitized evidence as reference.

C10.8 must not embed:

- config real;
- API values;
- environment identifiers;
- station identifiers;
- SSID or Wi-Fi password;
- IP, MAC, DNS, gateway or hostname;
- private candidates;
- backups;
- raw logs;
- media cache/runtime state.

## Decision

C10.8 can start as installer implementation work, but its first preflight on
the dev board must be read-only and confirm the board is no longer in an
open-settings transient state:

- `kiosky-player.service=active/enabled`;
- `totem-open-settings.service=inactive/static`;
- no setup process;
- no stale `session.lock`;
- `public_state=player_running`;
- playback `playing`.

Do not use C10.8 to repair or finish a F10 session. If the transient state is
still present, resolve that as a separate operational/debugging task before
installing.

## Guardrails

C10.7.1 did not:

- run writer;
- read config real;
- write config real;
- alter Wi-Fi or NetworkManager;
- reboot;
- install packages;
- stop/start services;
- alter player or `kiosky-player`;
- use the second board/card;
- publish sensitive data.
