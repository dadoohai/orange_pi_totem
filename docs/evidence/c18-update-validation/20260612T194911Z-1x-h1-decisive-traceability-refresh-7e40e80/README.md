# C18 H1 decisive traceability refresh

This evidence records a clean rerun of `c18_ota_release_gate.py --player-runtime-evidence-mode decisive` after adding git traceability guards for the player-runtime coldboot/data evidence inputs.

Result: `passed=true`, `step_count=66`, repo `7e40e80789229de1aed5d736a504803a09f97f54`, tree `759097c149943e4d67e808c5fef96be19186fbb7`.

The decisive bundle remains pinned to image `c18-hwdecode-lab-1x` with sha256 `1a853f569b5da9e856439897c95612d719fd3059f12349fa1040a6350c3df2f2` and marker sha256 `59739f57cdb3f79ac4c8ce5e5e1f9c4aa6d9dae58f704010f8423e66abe2bb9e`.

Non-claims: this is not H2 readiness, not stable/prod, not public thaw, not auto-pull/publish, not 24h soak, and not the full 17/17 physical power-loss matrix.
