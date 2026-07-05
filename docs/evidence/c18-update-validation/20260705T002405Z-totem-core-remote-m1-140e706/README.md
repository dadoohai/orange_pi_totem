# C18 totem-core remote OTA M1

This evidence records Marco 1 from `docs/C18_OTA_OPERATIONAL_SOURCE_OF_TRUTH.md`:
the lab board consumed a fresh `totem-core` GitHub Release remotely, validated it,
applied it, stayed functional, and rolled back.

## Release

- Repo: `dadoohai/orange_pi_totem`
- Source commit: `140e7062a9cb14d427b11e916ae27f6fed8e686a`
- Version: `c18.ota-core-m1-20260705T001743Z-140e706`
- Tag: `totem-core-c18.ota-core-m1-20260705T001743Z-140e706`
- URL: `https://github.com/dadoohai/orange_pi_totem/releases/tag/totem-core-c18.ota-core-m1-20260705T001743Z-140e706`
- Channel: `homologation`
- Payload SHA256: `75165e7ad74243a968c86bee5f500fd50ea244372d31fb54b48b2d4566b2e986`
- GitHub assets: manifest, payload, `c18-ota-release-gate.json`

## Board Run

- Board time: dry-run at `2026-07-05T00:23:15Z`; captured apply/rollback at
  `2026-07-05T00:29:05Z` to `2026-07-05T00:29:17Z`
- Initial `totem-core`: `c17.6-environment-input-20260514T211247Z`
- Initial policy: `device_channel=homologation`, `allow_prerelease=true`, `allowed_components=["totem-core"]`
- Dry-run selected exactly tag `totem-core-c18.ota-core-m1-20260705T001743Z-140e706`
- Apply result: `rc=0`, current became `c18.ota-core-m1-20260705T001743Z-140e706`
- Post-apply: `totem-updatectl self-test` passed and `kiosky-player.service` stayed `active`
- Rollback result: `rc=0`, current returned to `c17.6-environment-input-20260514T211247Z`
- Post-rollback: `totem-updatectl self-test` passed and `kiosky-player.service` stayed `active`

## Evidence

- `release/package-gate.json`: local package gate for the fresh release package.
- `release/c18-ota-release-gate.json`: release gate evidence uploaded as a release asset.
- `release/dadooh-totem-core-*.manifest.json`: published manifest.
- `board/github-dry-run.json`: board-side remote release selection without state change.
- `board/apply.log`: raw board-side remote apply output.
- `board/apply.rc`: raw apply return code.
- `board/apply-result.json`: normalized apply result summary.
- `board/status-after-apply.json`: board state after apply.
- `board/rollback.log`: raw rollback output.
- `board/rollback.rc`: raw rollback return code.
- `board/rollback.json`: structured rollback output from the first successful run.
- `board/rollback-result.json`: normalized rollback result summary.
- `board/status-after-rollback.json`: board state after rollback.
- `board-evidence-tarball.sha256`: SHA256 of the evidence tarball collected from the board.

## Non-Claims

- This is a `totem-core` OTA proof, not a `player-runtime` consumption proof.
- This does not enable auto-pull, staged rollout, stable promotion, or public thaw.
- This does not validate MPV/ffmpeg/kernel/media-system updates.
- This package is a fresh mechanical proof from HEAD; it is not a functional wizard UX change.
- The board state `updated_at` field remained stale, but `last_operation`,
  `current`, `previous`, return codes and service health reflect the apply and
  rollback operations captured here.
