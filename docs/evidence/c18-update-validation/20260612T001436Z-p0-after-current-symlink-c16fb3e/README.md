# C18 P0 power-loss - after_current_symlink - c16fb3e

Status: passed for the single `after_current_symlink` P0 checkpoint only.

This evidence records an operator-attended physical power cut after the player-runtime `current` symlink moved to the homologation target and before apply state success.

## Binding

- Checkpoint: `after_current_symlink`
- Target version: `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`
- Target payload SHA256: `d74a552f364de0e454a01a6fe839a1581d16c1b74acb357dc92c28a3ec0524a7`
- Target source commit: `c16fb3ed01f0ce25c8203e5fe1d60baf60a75749`
- Board image tag: `c18-hwdecode-lab-1x`
- Board image SHA256: `1a853f569b5da9e856439897c95612d719fd3059f12349fa1040a6350c3df2f2`
- Board image marker SHA256: `59739f57cdb3f79ac4c8ce5e5e1f9c4aa6d9dae58f704010f8423e66abe2bb9e`
- Harness commit: `c4369b7c11d147e3b2a2bd67b94f32373e059da1`

## Result

- Resume summary passed: `true`
- Boot at checkpoint: `9247c5ba-076b-4a58-872d-70d4597279ea`
- Boot at resume: `21333b78-0137-43b5-b2a8-464466555e37`
- Before reconcile selected version: `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`
- After reconcile selected version: `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`

## Non-claims

- Does not claim the full 17/17 power-loss matrix.
- Does not claim 24h soak.
- Does not claim stable or production readiness.
- Does not thaw public player-runtime OTA.
- Does not enable auto-pull or server-side publishing.
