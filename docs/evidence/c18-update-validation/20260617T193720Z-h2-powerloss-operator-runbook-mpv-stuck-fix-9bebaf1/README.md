# C18 H2 Power-Loss Operator Runbook

Generated: `2026-06-17T19:43:49Z`

This directory is not physical power-loss evidence. It is an operator aid built
from the offline matrix plan so the remaining H2 checkpoints can be run one at a
time without losing the non-claims.

## State

- Covered checkpoints in the source plan: 0/17
- Missing checkpoints in the source plan: 17/17
- Board bundle dir: `/data/c18-powerloss-bundle-3eb06f1`
- Board evidence root: `/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1`
- Canary media: `/data/media/c18-canary-h264.mp4`

## Files

- `operator-runbook.md`: per-checkpoint setup, arm and resume commands.
- `pull-and-validate-evidence.sh`: optional pull/validation helper; edit host/path first.
  It refuses a `<utc>` placeholder and refuses to reuse an existing local root.
- `operator-runbook-manifest.json`: machine-readable summary of this runbook.

Run the H2 board preflight gate before starting a physical checkpoint session.
The preflight is not power-loss evidence; it only checks the board/package/image
and session topology against the matrix plan.

## Non-Claims

- `this_runbook_is_not_powerloss_evidence`
- `this_runbook_does_not_claim_17_17`
- `this_runbook_does_not_execute_board_commands`
- `this_runbook_does_not_pull_or_validate_evidence_by_itself`
- `this_runbook_does_not_replace_physical_power_cut`
- `this_runbook_does_not_authorize_stable_or_production`
- `this_runbook_does_not_thaw_player_runtime`
- `this_runbook_does_not_publish_or_fetch_releases`
- `remote_reboot_is_not_acceptable_powerloss_evidence`
