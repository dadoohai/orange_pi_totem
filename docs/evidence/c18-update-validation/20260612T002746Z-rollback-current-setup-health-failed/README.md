# C18 rollback_after_current_to_previous setup health failure

Status: diagnostic evidence only. No power-loss checkpoint was armed and no pilot/H2 claim is made by this directory.

During preparation for `rollback_after_current_to_previous`, the board was reset to A (`c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`) and attempted to reapply the verified B target (`c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`) from `previous`. Candidate health failed before the power-loss arm step, so the run stopped without requesting a physical cut.

The first linked-previous harness version incorrectly quarantined B on this setup health failure. Commit `546a2c4` changes linked-previous reapply failures to fail closed without quarantining the verified previous target. The board remediation evidence in `remediation/unquarantine-linked-previous.json` removes only the B quarantine entry created by that failed setup and leaves the older unrelated quarantine intact.

Non-claims: no P0 checkpoint, no production readiness, no stable promotion, no public thaw.
