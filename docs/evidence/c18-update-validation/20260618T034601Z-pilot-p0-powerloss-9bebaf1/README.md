# C18 pilot P0 power-loss evidence

Purpose: record the five attended physical power-loss checkpoints required by
the C18 homologation pilot gate for target
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

Result: all five checkpoint evidence gates passed locally.

Validated checkpoints:

- `after_current_symlink`
- `rollback_after_current_to_previous`
- `rollback_after_previous_removed`
- `rollback_after_quarantine`
- `rollback_after_state_success`

Files:

- `<checkpoint>/evidence-manifest.json`: package, image and file binding for
  each checkpoint.
- `<checkpoint>/trial/...`: checkpoint, boot-transition, reconcile and health
  sidecars pulled from the board.
- `_validation/*powerloss-evidence-gate.json`: offline gate result for each
  checkpoint.
- `_validation/*powerloss-manifest-build.json`: local manifest build result for
  each checkpoint.

Sanitization:

- interrupted raw collection residue and zero-byte auxiliary files were not
  included in the committed checkpoint directories;
- the committed evidence is the gate-consumed proof: checkpoint state, real boot
  transition, reconcile result, adoption, playback health, freeze checks and
  postcheck where required.

Non-claims:

- this is pilot P0 evidence only;
- this does not claim full H2 power-loss 17/17 coverage;
- this does not claim production, stable, public thaw, auto-pull or 24h soak.
