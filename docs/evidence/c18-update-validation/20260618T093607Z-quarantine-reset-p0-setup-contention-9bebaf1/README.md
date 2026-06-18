# C18 quarantine reset - active service contention

Governed lab-only quarantine reset for
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

Result:

- `quarantine-reset.json`: `passed=true`;
- reset scope: `p0_setup_contention_retry`;
- one quarantine entry for the target was removed;
- the failed candidate evidence showed active-service contention with
  `total_mpv_count=2`;
- public player-runtime apply, rollback and reconcile remained frozen with
  `rc=44`;
- current/previous links were not changed by the reset.

This reset allowed a controlled retry after a failed setup attempt. It did not
apply, rollback, publish, promote `stable`, authorize production or thaw public
`player-runtime`.
