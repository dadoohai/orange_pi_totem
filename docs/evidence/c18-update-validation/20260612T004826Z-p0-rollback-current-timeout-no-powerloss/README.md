# C18 P0 rollback_current_to_previous timeout diagnostic

This directory is diagnostic evidence only. It is not a valid P0 power-loss
checkpoint and must not be passed to the pilot readiness gate.

Checkpoint reached:

- checkpoint: `rollback_after_current_to_previous`
- action: `rollback`
- instruction emitted: `CUT_POWER_NOW`
- arm result: `power_cut_not_observed_before_timeout:rollback_after_current_to_previous`
- checkpoint boot id: `21333b78-0137-43b5-b2a8-464466555e37`
- resume boot id: `21333b78-0137-43b5-b2a8-464466555e37`

Outcome:

- No physical power-loss was observed before timeout.
- The transient rollback state was reconciled back to the image/data A runtime.
- The retry must be rearmed from a clean state and collected in a separate
  evidence directory.

Non-claims:

- no P0 checkpoint completion
- no pilot readiness advancement
- no public thaw
- no stable or production readiness
