# C25B Player H264 - Governed Board Evidence

## Claim

The exact `player-runtime` homologation package below was applied, exercised,
rolled back to C23, and reapplied through the guarded linked-previous path on
the lab board. Loading, content-unavailable and player-recovery surfaces are
MPV-owned H.264 frames; no second DRM owner was introduced.

```text
version=c18.player-runtime-homolog-20260713-c25b-recovery-8ce9bb8
source_commit=8ce9bb8f4a3bcb2873c229ef6791008eca1b57c2
payload_sha256=962346c2fd9df78a555ae767ab4562161c307ce9a4497c63ee38c4c5608f5cff
channel=homologation
board_apply=passed
mpv_recovery_surface=passed
rollback_to_c23=passed
linked_previous_reapply=passed
final_service_health=passed
```

## Results

- Candidate health: 45/45 samples with `v4l2request-copy`, zero status
  failures, zero MPV restarts and zero new Panfrost faults.
- Controlled MPV IPC quit: recovery status persisted immediately; the
  `player_error` asset was observed directly in MPV at `1.495 s`; normal media
  was healthy again at `4.379 s`; the systemd service did not restart.
- Exact rollback: C23 became `current`, C25B became `previous`, and 30-second
  C23 service health passed.
- A normal reapply of linked `previous` was denied with rc=45. The explicit
  `--allow-reapply-linked-previous` path then revalidated and promoted the
  exact C25B identity.
- Final live health: 30/30 samples, four observed media aliases, hardware
  decode in every sample, zero status failures and zero new Panfrost faults.
- Public apply, rollback and reconcile remained frozen with rc=44 during the
  rollback proof.

## Evidence Map

- `package/`: exact manifest and recomputed release gate.
- `apply/`: first final-package apply and candidate health.
- `recovery/`: 250 ms recovery samples with sanitized MPV path classes.
- `rollback/`: guarded rollback and C23 health.
- `reapply-denied/`: expected default-deny result without the explicit
  linked-previous authorization.
- `reapply/`: guarded exact reapply and candidate health.
- `final/`: service health after the complete sequence.
- `visual/`: generated-frame contact sheets inspected for landscape and
  portrait layout. They prove renderer output, not physical HDMI pixels.

## Non-Claims

- This is homologation evidence, not a `stable` release or public thaw.
- It does not enable public player-runtime auto-pull.
- It does not replace the image-bound launcher or next-reference-image work.
- It does not claim HDMI camera-level absence of every sub-second transition.
- No raw config, API credential, media URL, media payload or customer ID is
  included.
