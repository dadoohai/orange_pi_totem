# C18 H2 power-loss preflight before P0

Target package: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`

Purpose: check whether the board can start the physical P0 apply checkpoints
after the IPC health calibration and user-level validation.

Outcome:

- Board image marker is present and matches `c18-hwdecode-lab-1x`.
- Policy remains `device_channel=homologation`,
  `allow_prerelease=true`, `allowed_components=["totem-core"]`.
- Bundle, target manifest/payload, canary media, wrapper and hwdecode MPV are
  present.
- The offline preflight gate is red only because the runtime topology is no
  longer a fresh-apply baseline:
  - target is already `/data/player-runtime/current`;
  - target release directory already exists;
  - previous points to the M6-A rollback release.

Decision:

- Do not arm P0 apply checkpoints from this topology.
- Before `after_current_symlink` or other fresh apply checkpoints, reset the
  topology back to baseline M6-A, verify a fresh preflight, then ask the
  operator for the physical cut only after `CUT_POWER_NOW`.

This is not power-loss evidence and does not claim H2 readiness.
