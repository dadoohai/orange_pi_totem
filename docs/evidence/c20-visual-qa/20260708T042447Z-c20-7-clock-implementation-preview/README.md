# C20.7 Clock Implementation Preview

Status: offline implementation preview before OTA board apply.

Scope:

- `totem_setup_visual_wizard.py` renders date/time as passive header metadata.
- Step 0 preserves the layout note.
- Steps 1-4 render `DD/MM/YYYY HH:MM`.
- Implausible clock renders `Hora nao ajustada`.
- No time, timezone, NTP, RTC or systemd configuration is changed.

Validation:

- `python3 -B scripts/board/totem_setup_visual_wizard.py --self-test` passed.
- `python3 -B scripts/sim/run_wizard_input_replay.py --out-dir /tmp/c20-7-clock-replay` passed.
- PNG previews in `previews/` are browser-rendered offline artifacts, not board captures.
