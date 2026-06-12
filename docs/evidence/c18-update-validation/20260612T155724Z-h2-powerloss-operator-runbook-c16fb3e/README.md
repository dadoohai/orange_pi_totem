# C18 H2 Power-Loss Operator Runbook

Generated: `2026-06-12T15:57:24Z`

This directory is not physical power-loss evidence. It is an operator aid built
from the offline matrix plan so the remaining H2 checkpoints can be run one at a
time without losing the non-claims.

## State

- Covered checkpoints in the source plan: 5/17
- Missing checkpoints in the source plan: 12/17
- Board bundle dir: `/data/c18-p0-bundle-a0dcb13fd78d`
- Board evidence root: `/data/c18-evidence/h2-c16fb3e`
- Canary media: `/data/media/c18-canary-h264.mp4`

## Files

- `operator-runbook.md`: per-checkpoint setup, arm and resume commands.
- `pull-and-validate-evidence.sh`: optional pull/validation helper; edit host/path first.
- `operator-runbook-manifest.json`: machine-readable summary of this runbook.

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
