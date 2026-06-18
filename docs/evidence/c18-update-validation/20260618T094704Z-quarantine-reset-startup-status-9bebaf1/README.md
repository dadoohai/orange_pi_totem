# C18 quarantine reset - startup status retry

Governed lab-only quarantine reset for
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1` after a candidate
startup-status false positive.

Result:

- `quarantine-reset.json`: `passed=true`;
- reset scope: `lab_candidate_startup_status_retry`;
- one quarantine entry for the target was removed;
- the rejected candidate had exactly `failure_reasons=["status_no_failures"]`;
- re-evaluating the same candidate artifacts with the corrected candidate-mode
  rule passed;
- public player-runtime apply, rollback and reconcile remained frozen with
  `rc=44`;
- current/previous links were not changed by the reset.

This reset allowed one controlled retry after proving that the quarantine entry
came from the startup-status false positive. It did not apply, rollback,
publish, promote `stable`, authorize production or thaw public
`player-runtime`.
