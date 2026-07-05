# C18 player-runtime remote OTA M2 with HDMI

Date: 2026-07-05.

Claim: Marco 2 `player-runtime` remote consumption is proven in the lab under an operator-assisted window.

What passed:

- HDMI was connected before the run.
- The board consumed the exact GitHub Release tag
  `player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.
- Selection mode was exact tag, not latest.
- Release gate validation passed against payload SHA256
  `d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0`.
- Remote apply returned `rc=0` and promoted
  `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.
- Public player-runtime apply/reconcile stayed frozen with `rc=44`.
- Service restarted and playback deep-health passed with HW decode
  `v4l2request-copy`, one MPV, frame progress, no media load failure, no
  storage error, and no GPU fault delta.
- Lab rollback returned `rc=0` and rolled back to
  `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`.
- Rollback service health passed.
- The target was re-applied from linked previous and the final stabilized
  service health passed.
- Final state: current `player-runtime` is
  `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`, previous is
  `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`, service is active.

Important evidence:

- `c18-player-runtime-github-m2-hdmi-20260705T150628Z/evidence/github-apply.json`
- `c18-player-runtime-github-m2-hdmi-20260705T150628Z/evidence/lab-rollback.json`
- `c18-player-runtime-github-m2-hdmi-20260705T150628Z/evidence/restore-target-lab-reapply-linked-previous.json`
- `c18-player-runtime-github-m2-hdmi-20260705T150628Z/evidence/final-stabilized-service-health.json`
- `c18-player-runtime-github-m2-hdmi-20260705T150628Z/evidence/final-stabilized-status.json`

Evidence tarball:

- `c18-player-runtime-github-m2-hdmi-20260705T150628Z.tgz`
- SHA256: `aa89931dcedb69bfd0faf8bb51d8e0e34e80b28a637e3bb43aa2946e4af9819a`

Operational note:

- One intermediate restore command failed because the operator command parsed
  `github-apply.json` as pure JSON even though it contains a leading INFO log
  line. This did not corrupt the board: the service remained active, rollback
  health passed, then the manifest path was resolved from the extracted release
  directory and the target was restored successfully.
- A first final health immediately after restore saw one transient status
  failure sample. A follow-up stabilized 90s health passed cleanly and is the
  final health claim for this run.

Non-claims:

- This is not public thaw.
- This is not auto-pull.
- This is not staged rollout.
- This is not a stable-channel proof.
- This is not a new clean 24h soak claim.
- This does not validate `media-system`.
