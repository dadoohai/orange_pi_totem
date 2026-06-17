# C18 H2 Power-Loss Partial Evidence - after_payload_staged

This directory preserves the first physical `after_payload_staged` resume
attempt after `CUT_POWER_NOW` was emitted and physical power was removed.

Result:

- checkpoint reached: `after_payload_staged`;
- checkpoint hit at: `2026-06-17T17:27:32Z`;
- adoption before reconcile: `passed=true`;
- health before reconcile: `passed=false`;
- failure reasons: `status_mpv_path_aligned`.

Interpretation:

- this is negative/diagnostic evidence only;
- this does not count the checkpoint as accepted;
- this does not claim 17/17 power-loss coverage;
- this does not authorize stable, production, public thaw, publish or auto-pull;
- this preserves the failed first resume before a calibrated rerun.
