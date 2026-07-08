# C20.8 Clock All Steps Preview

Status: offline preview before OTA board apply.

Change:

- The header metadata slot is now dedicated only to date/time or `Hora nao ajustada`.
- The `Tela` step no longer renders `Layout paisagem/retrato` in that slot.
- Orientation remains visible in the step body and preview.
- No time, timezone, NTP, RTC or systemd configuration is changed.

Validation:

- `python3 -B scripts/board/totem_setup_visual_wizard.py --self-test` passed.
- `python3 -B scripts/sim/run_wizard_input_replay.py --out-dir /tmp/c20-8-clock-all-steps-replay` passed.
- `previews/0001-01-orientation.png` shows the clock in the `Tela` step.
