# C18 Pilot P0 Power-Loss Run Card

This is the short operator card for the five physical power-loss checkpoints
that unblock the assisted pilot gate for target
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

It does not replace `operator-runbook.md`, does not execute board commands and
does not claim H2 or 17/17. Use it only to avoid scanning the full 17-checkpoint
runbook during the pilot P0 session.

## Preconditions

- Board SSH is reachable at `root@192.168.18.131`.
- Board bundle exists at `/data/c18-powerloss-bundle-3eb06f1`.
- Board evidence root is `/data/c18-evidence/h2-mpv-stuck-fix-9bebaf1`.
- Latest H2 power-loss preflight gate is green.
- Physical power can be removed after `CUT_POWER_NOW`.
- Remote reboot is not acceptable evidence.

If the preflight is blocked only because target `9bebaf1` is already linked as
current, do not arm a checkpoint from that topology. Run the guarded fresh apply
topology prep from `operator-runbook.md`, then rerun preflight and proceed only
from green. The evidence
`docs/evidence/c18-update-validation/20260617T225708Z-h2-powerloss-board-preflight-target-linked-9bebaf1/`
records this expected target-linked state after user-level validation.

## Required Pilot P0 Checkpoints

Run one checkpoint at a time. For each checkpoint:

1. Run its setup command when the full runbook has one.
2. Run its arm command.
3. Wait for `CUT_POWER_NOW`.
4. Remove physical power.
5. Restore power and wait for SSH.
6. Run its resume command.
7. Do not start the next checkpoint until resume passes.

The required checkpoints are:

| Order | Checkpoint | Full runbook section | Phase |
| --- | --- | --- | --- |
| 1 | `after_current_symlink` | `## 9. after_current_symlink` | apply |
| 2 | `rollback_after_current_to_previous` | `## 13. rollback_after_current_to_previous` | rollback |
| 3 | `rollback_after_previous_removed` | `## 14. rollback_after_previous_removed` | rollback |
| 4 | `rollback_after_quarantine` | `## 15. rollback_after_quarantine` | rollback |
| 5 | `rollback_after_state_success` | `## 17. rollback_after_state_success` | rollback |

## After The Five Runs

Pull and validate only the pilot P0 evidence:

```sh
docs/evidence/c18-update-validation/20260617T193720Z-h2-powerloss-operator-runbook-mpv-stuck-fix-9bebaf1/pull-and-validate-pilot-p0-evidence.sh \
  root@192.168.18.131 \
  docs/evidence/c18-update-validation/<fresh-utc>-pilot-p0-powerloss-9bebaf1
```

Then run the pilot readiness gate with the five pulled evidence directories.
The gate must still not claim production, stable, public thaw, 17/17 or 24h
soak.
