# C18 Mid-Decode SIGTERM Diagnostic Failure

This directory is a FAILED diagnostic Track A run on image
`c18-hwdecode-lab-1x`. It is intentionally non-decisive and must not be used as
thaw, stable, publish, or player-runtime authorization evidence.

- Raw gate input: `raw-run/`
- Producer: `scripts/board/c18_player_runtime_teardown_trial.py`
- Validator: `scripts/qa/c18_player_runtime_teardown_evidence_gate.py`
- Run rc: `1`

The main teardown cycles stayed green, but the mid-decode probe recorded real
panfrost faults:

- `Unhandled Page fault`
- `JOB_BUS_FAULT`
- `gpu sched timeout`
- `BO has no sgt`

Important scope note: the first panfrost line appears inside the probe window
after the isolated kiosk process was killed and before the explicit SIGTERM was
delivered to the orphaned mpv process. This proves a real GPU fault in the
mid-decode teardown isolation window, but it must not be over-read as proof that
the explicit mpv SIGTERM path alone caused the fault.

Current claim: H1 remains open. This artifact is diagnostic evidence for the
next design decision. The next decisive probe should be production-faithful:
keep the kiosk/controller alive, signal the same process path production uses,
and record whether the kiosk stopped mpv via IPC quit or reached the SIGTERM
fallback. A split kiosk-kill/mpv-signal probe is useful only as follow-up
diagnostics for this failed run, not as product authorization evidence.
