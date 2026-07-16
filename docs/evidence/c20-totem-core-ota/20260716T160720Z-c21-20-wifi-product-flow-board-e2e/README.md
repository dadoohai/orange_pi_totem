# C21.20 Wi-Fi product flow board E2E

## Claim

C21.20 is a homologation-only accumulated `totem-core` candidate. It closes
M9 items 1 and 2: the connection choices shown to the user now reflect the
verified state of the current session, and the protected Wi-Fi path is shorter
while preserving retry context and the transactional rollback base proven by
C21.19.

It is not a stable promotion, public OTA release or new reference image.

## Identity

- Version: `c21.20-wifi-product-flow-20260716T154014Z-1d36dd3`
- Package source: `1d36dd34ea26a4fa1fdfeda047a7aa69c1f10920`
- Payload SHA-256: `e7812eb6737182ab95b0f43259e19d156c74dc5a21553795d5817c26dee060a0`
- Manifest SHA-256: `25329f346610b843aaa0eeef7f1380308ebab604735876d0905f2ddfdada8136`
- Channel: `homologation`
- Public reference unchanged: `prod14` + C25B + C21.12 stable

## Results

- The clean source and exact-package release gates passed `84/84`.
- Stable policy rejected the homologation package with rc `41`.
- Governed apply, rollback to C21.19 and reapply of C21.20 passed with rc `0`.
- The installed wizard rendered three real choices on the board: active
  Ethernet, active product Wi-Fi and selection of another Wi-Fi network.
- Production mode did not expose the bench-only option.
- The real visual session exited without changing product configuration,
  private settings, OTA policy or the NetworkManager profile. Sanitized
  before/after hashes bind this claim.
- The board finished with C21.20 current, C21.19 previous, player active with
  zero restarts, settings inactive, stable policy restored and the stable
  update timer enabled and active.
- Wizard and Wi-Fi adapter self-tests passed on the installed candidate.

## Product behavior closed

- A connection already in use is offered only when live state proves it.
- Bench mode is absent from the production surface.
- Protected Wi-Fi goes from network selection to password/connect, then
  progress and success or a recoverable failure.
- Success advances automatically after a short confirmation.
- Failure retains the network list and selected network, while the persisted
  artifact keeps the password masked.
- Old persisted status cannot make a new settings session claim that it
  changed or restored Wi-Fi.

## Honest limits

- Open Wi-Fi remains explicitly unavailable and is M9 item 3.
- This visual board run did not enter a new password or replace the active
  network. The transactional positive and rollback-on-failure hardware proof
  belongs to C21.19; C21.20 preserves that adapter and changes the product
  journey around it.
- Captive portal, detailed failure categories and browser support remain later
  M9 items.
- The candidate was applied locally under a temporary homologation policy. It
  was not published or consumed by the public stable timer.
- No credential, SSID value, IP address, token or raw NetworkManager profile
  is included in this evidence.
- The supported product path serializes settings sessions before the wizard is
  launched. The fixed legacy temporary secrets path is still recorded as
  defense-in-depth hardening for unsupported direct privileged invocation.

## Evidence map

- `package/`: exact manifest and package hashes.
- `gates/`: clean-source and exact-package release-gate results.
- `board/transaction/`: stable block, apply, rollback, reapply and final state.
- `board/visual/`: real framebuffer captures and sanitized UI assertions.
- `board/self-tests/`: installed wizard and adapter self-tests.
- `audits/`: evidence audit, focused code audit, full-path tie-break and central
  decision.
