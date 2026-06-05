# C18 1s Offline Build Evidence

This directory records the offline derivation evidence for
`c18-hwdecode-lab-1s`.

## Scope

- Proves the image was derived offline and passed the repository validation
  gates before hardware flashing.
- Does not prove hardware playback, HDMI output, cold-boot adoption, or
  power-loss behavior.
- This directory alone did not promote `1s`; promotion required the later
  hardware evidence recorded in
  `../20260605T043000Z-1s-service-deep-health/` and
  `../20260605T043400Z-1s-coldboot-deep-health/`.

## Artifact

- Image:
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1s_minimal.img`
- Windows copy:
  `/mnt/d/images_orange/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1s_minimal.img`
- SHA256:
  `bc0a39cf0cc4502acb7f9b4726589449288783fa4d44821593ab15c4c2c1967f`
- Size: `1971322880` bytes

## Result

- `OFFLINE_VALIDATION_PASSED=True`
- `artifact_promoted=true`
- `hardware_validation_required=true`
- `card_written=false`
- `board_touched=false`
- `ssh_used=false`

Load-bearing checks include `totem_core_ota_ready=true`,
`player_runtime_sandbox_passed=true`, `player_runtime_release_gate_passed=true`,
`player_runtime_ota_still_frozen=true`, no embedded
`/data/player-runtime/current`, no embedded legacy
`/data/apps/kiosky-player/current`, no pre-forged player-runtime marker, and
clean fsck.

## Files

- `build_manifest.json`: full derivation manifest.
- `offline_validation.json`: boolean validation matrix.
- `build.log`: concise derivation log.
