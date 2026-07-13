# C25B Final - Exact Package Board Evidence

## Claim

The exact C25B homologation package was validated on the lab board as a
reversible `player-runtime` candidate. It handled motion media, static-frame
semantics, `content_unavailable`, controlled MPV recovery, rollback to C23 and
governed reapply. Public player-runtime mutation remained frozen.

```text
version=c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4
source_commit=54308e4a09ef693dbfb3d6b31ce9626908ca0c16
payload_sha256=b6e1a58b6434107a5af43d27bc07f19b0255bcc58c86deac59be6acc2742b70d
kiosk_py_sha256=7b67003a450902ddd4ea5d8c9f11653a43b9e55df0c45ccd4496be08188df3f0
tree_sha256=a7baf69dc249c39b2f6f8653873171fa8d799c814acbe8bc95c3eeed2c7136fc
channel=homologation
release_gate=passed
content_unavailable_live_probe=passed
controlled_mpv_recovery=passed
rollback_c23_health_reapply=passed
final_service_health=passed
public_rollback_probe=rc44
```

## Results

- The exact candidate presented `content_unavailable` through the active MPV
  path with a valid frame, VO, dimensions and `v4l2request-copy`; the service
  was restored active with no systemd restart.
- Controlled MPV exit exposed the `player_error` recovery surface, returned to
  media and added no Panfrost fault or service restart.
- Governed rollback made C23 current; settled C23 health passed. Governed
  linked-previous reapply then restored the exact C25B package after candidate
  health passed.
- Final service health passed 45 checks across 40 samples and two proven motion
  episodes, with no tolerated or failed episode, media-load failure, MPV
  restart, service restart or new Panfrost fault.
- Candidate, rollback-target and final-service evidence all had IPC success
  from the first sample. The validator separately rejects startup IPC outage
  beyond six samples or six seconds, any timeout and any non-missing-socket
  startup error.
- An observation window ending at the first frame of a new episode was rejected
  as inconclusive. A complete subsequent window passed, preserving fail-closed
  behavior.

## Evidence Map

- `package-identity.json`: manifest, payload and source identity.
- `content-unavailable-live-probe.json`: live MPV/status proof and lifecycle.
- `recovery-live-probe.json`: controlled recovery and return to media.
- `governed-rollback.json`: exact rollback and public freeze probes.
- `c23-health-after-rollback.json`: settled service health on the rollback target.
- `governed-reapply.json`: exact linked-previous reapply and candidate health.
- `final-service-health.json`: final live service health.
- `inconclusive-terminal-window-negative.json`: expected fail-closed negative.
- `board-final-state.json`: final current/previous/service/quarantine state.
- `validation-gates.json`: final repo-side test and gate results.
- `evidence-manifest.json`: SHA256 binding for this evidence set.

## Non-Claims

- This is homologation evidence, not `stable`, public auto-pull or public thaw.
- It does not replace the next image-bound reference-image validation.
- MPV path/VO/frame evidence is not an optical HDMI-camera measurement.
- No raw config, credential, media URL, media payload or customer identity is
  included.
