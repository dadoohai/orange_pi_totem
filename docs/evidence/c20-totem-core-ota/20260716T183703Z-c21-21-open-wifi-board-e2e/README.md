# C21.21 Open Wi-Fi board E2E

## Claim

C21.21 is a homologation-only `totem-core` candidate that implements ordinary
open Wi-Fi networks without a password. It preserves the protected Wi-Fi flow,
requires IPv4 before success and uses the existing transactional rollback.

The package and OTA roundtrip are approved. Association with a real open AP is
still pending because no such network was available during this run.

It is not a stable promotion, public release, captive-portal implementation or
new reference image.

## Identity

- Version: `c21.21-open-wifi-20260716T171724Z-4b294c8`
- Package source: `4b294c8c95e7d7715d9f0abdce5cab1e8f2dcf34`
- Payload SHA-256: `87a7f8c65ec4f3e0e84b1bad5cb99bab1672472f6bca773e10b1931b7fd79683`
- Manifest SHA-256: `9e6a8e78f612c9e645227d0707fea736546c9b0424e100bde31093597ed6729d`
- Channel: `homologation`
- Board baseline before apply: C21.20

## Results

- Clean-source and exact-package release gates passed `84/84`.
- Adapter and wizard self-tests passed off-board and from the installed package.
- Replay passed 11 scenarios and 38 assertions without calling NetworkManager.
- Visual review covered selection, progress, restored failure and success.
- Stable policy rejected the homologation package with rc `41`.
- Governed apply, rollback to C21.20 and reapply passed with rc `0`.
- The board finished with C21.21 current and C21.20 previous.
- Player remained active with zero restarts.
- Ethernet and the existing protected Wi-Fi remained connected.
- Stable policy and the production update timer were restored.

## Behavior Implemented

- Open networks are labeled `Aberta | Sem senha`.
- Selecting an open network skips password entry.
- Open profiles omit `[wifi-security]`, WPA and PSK.
- Unknown security fails closed through the protected path.
- Open and protected networks sharing an SSID remain distinct selections.
- Activation without IPv4 fails and restores the prior profile exactly.
- Retry after an open-network failure does not ask for a password.
- Success claims a local Wi-Fi link and explicitly does not claim internet.
- SSID and credential values remain absent from public artifacts.

## Honest Limits

- No real open AP was available, so this run did not prove radio association,
  DHCP and persistence against physical open-network hardware.
- The board OTA roundtrip intentionally did not replace the current network.
- Captive portal detection and a temporary browser remain later M9 items.
- Detailed internet-state and failure-category UX remain M9 items 4 through 6.
- The package was applied locally under a temporary homologation policy. It was
  not published or consumed by the public stable timer.

## Evidence Map

- `gates/`: clean-source and exact-package release gates.
- `package/`: exact manifest and package hashes.
- `board/`: stable block, apply, rollback, reapply, self-tests and final state.
- `offboard/replay/`: deterministic keyboard-flow assertions.
- `offboard/visual/`: reviewed open-network screens.
- `audits/`: independent security, UX and final claim reviews.
