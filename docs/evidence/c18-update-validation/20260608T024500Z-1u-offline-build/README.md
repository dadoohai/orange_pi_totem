# C18 1u Offline Build Evidence

This directory records the offline derivation evidence for
`c18-hwdecode-lab-1u`.

## Scope

- Proves the image was derived offline from the governed C18 deriver and passed
  repository validation gates before hardware flashing.
- Proves the candidate uses a distinct image identity from the then-current
  golden `1t`, so post-M6 hardware validation is traceable.
- Does not prove hardware playback, HDMI output, `kiosky-player reconcile`
  behavior on-device, physical power-loss, soak, public thaw, stable, or
  production readiness.
- This directory alone did not promote `1u` to golden. `1u` was promoted only
  after the hardware evidence in
  `20260608T035330Z-1u-coldboot-deep-health`.

## Artifact

- Image:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1u_minimal.img`
- Windows copy:
  `/mnt/d/images_orange/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1u_minimal.img`
- SHA256:
  `57cd3e1620820c14ff9b297850386d7d95a1979b2f06201ff082526b8ffd13dd`
- Size: `1971322880` bytes
- Source repo commit: `58457740661b557877e06f53b932b133d62838cb`
- Source repo tree: `0713c9c61893d0c049425bf72d2714f83fc3e1ff`
- Source repo dirty: `false`

## Result

- `OFFLINE_VALIDATION_PASSED=True`
- `artifact_promoted=true`
- `hardware_validation_required=true`
- `card_written=false`
- `board_touched=false` for this offline-only directory.
- `ssh_used=false` for this offline-only directory.

Load-bearing checks include `totem_core_ota_ready=true`,
`player_runtime_sandbox_passed=true`, `player_runtime_release_gate_passed=true`,
`player_runtime_ota_still_frozen=true`, no embedded
`/data/player-runtime/current`, no embedded legacy
`/data/apps/kiosky-player/current`, and clean fsck.

## Next Hardware Check

Hardware validation for this candidate proved the post-M6 repo delta,
especially `reconcile --component kiosky-player` returning `rc=44`, while
preserving playback deep-health and the public freeze posture. See:

- `docs/evidence/c18-update-validation/20260608T035330Z-1u-coldboot-deep-health/`

## Files

- `build_manifest.json`: full derivation manifest.
- `offline_validation.json`: boolean validation matrix.
- `build.log`: concise derivation log.
