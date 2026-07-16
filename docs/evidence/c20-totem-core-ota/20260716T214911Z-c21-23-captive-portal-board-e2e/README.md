# C21.23 Captive Portal Detection Board E2E

## Claim

C21.23 is a homologation-only `totem-core` candidate that closes M9 item 7:

- detects positive captive-portal evidence without following redirects;
- keeps ambiguous failures distinct from portal evidence;
- blocks environment/review/commit while portal access is pending;
- gives the operator retry, network-change and exit paths.

It is not a browser implementation, stable promotion, public release, new
reference image or proof against a physical captive portal.

## Identity

- Version: `c21.23-captive-portal-detection-20260716T214621Z-3e5dbf8`
- Package source: `3e5dbf8f2c4022b74c123576dae31bb53a0f6199`
- Package commit: `225b40f`
- Payload SHA-256: `90990b123c8f4f21260ede05dbb742a4a5122616d11bf1f2045c68a93bbde6e3`
- Manifest SHA-256: `2e64d4722c670f9d6c62e4fbaf35c32818db98c350e6caab3fd772f591dfd2c8`
- Channel: `homologation`
- Board baseline before apply: C21.22

## Results

- Clean-source and exact-package release gates passed `84/84`.
- Replay passed 12 scenarios, 55 assertions and 62 screens without touching
  NetworkManager, the writer, the board or a backend.
- The gallery rendered 123/123 PNG files with no rendering failure or major UI
  blocker; the four portal states were visually inspected.
- Two pre-board and two final independent reviews found no unresolved blocker.
- Stable policy rejected the homologation package with rc `41`.
- Governed apply, rollback to C21.22 and reapply passed with rc `0`.
- Installed updater, wizard and Wi-Fi adapter self-tests passed.
- The post-documentation policy suite passed `81/81`.
- The wizard's asynchronous runtime collector returned `online`,
  `transport=ethernet` and `captive_portal=not_detected` on the normal lab
  network without publishing network identifiers or probe material.
- Installed wizard/adapter hashes matched the exact package.
- Player remained active with zero restarts; Ethernet and Wi-Fi remained
  connected.
- Stable policy and the production update timer were restored byte-for-byte.
- A post-reapply observation preserved C21.23 current, C21.22 previous, player,
  network, timer and policy state.

The direct cache API initially returned `unknown` when invoked with its runtime
disabled. This is the expected idle behavior. Repeating through the same
runtime enable/poll/disable lifecycle used by the wizard produced the valid
snapshot above.

## Honest Limits

- No physical or emulated captive portal was available in this run.
- The browser/authentication vertical remains M9.8 and may require a new image.
- No Wi-Fi profile, credential, player runtime, display, kernel, updater,
  systemd unit or public release was changed.
- The package was applied locally under a temporary homologation policy. It was
  not published or consumed by the public stable timer.
- The updater's legacy top-level `state.updated_at` remained stale while
  `current.applied_at_utc`, `last_operation`, symlinks and live state advanced
  correctly. This is recorded as a non-blocking observation, not used as proof.

## Evidence Map

- `gates/`: clean-source and exact-package release gates.
- `package/`: exact manifest and package hashes.
- `board/`: policy block, apply, rollback, reapply, installed tests, sanitized
  connectivity and final state.
- `offboard/`: deterministic replay evidence.
- `visual/`: reviewed landscape/portrait portal screens and gallery summaries.
- `audits/`: independent blocker and board-operation reviews.
