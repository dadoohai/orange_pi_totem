# C18 target-current health attempt - 9bebaf1

Collected at `2026-06-18T09:11:34Z` during an assisted lab attempt to make
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1` current on the
board and run candidate deep-health.

Result: `FAIL`, candidate rejected by the lab apply harness with `rc=10`. The
board remained on `c18.player-runtime-m6-a-20260610T0501Z-29ff33b` before and
after the attempt.

Failure reasons from candidate deep-health:

- `hwdec_expected_present`
- `vo_configured_present`
- `vo_configured_no_unexpected`
- `estimated_frame_present`
- `playback_progressed`

Useful signal:

- Public `player-runtime` CLI apply/reconcile remained frozen with `rc=44`.
- The lab apply recorded `candidate_rejected` and restored/kept the previous
  current runtime topology.
- No GitHub or network fetch was used by the lab apply.

Interpretation: this evidence preserves a failed target-current attempt, not a
proved target package defect. Diagnostic sidecars from the failed health hook
were intentionally excluded from the committed subset. The next proving step is
to repeat the target-current validation with the service stopped, then restart
the service and collect user-level playback health on the target.

Non-claims:

- Does not validate the target package as current.
- Does not prove root cause.
- Does not authorize pilot execution by itself.
- Does not authorize production, stable promotion, auto-pull, or public thaw.
- Does not satisfy power-loss 17/17 or 24h soak.

Raw logs, runtime config, and local state files were intentionally excluded from
the committed subset.
