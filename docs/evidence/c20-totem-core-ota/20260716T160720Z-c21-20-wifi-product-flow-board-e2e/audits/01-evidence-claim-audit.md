# Independent evidence and claim audit

Verdict: **GO**, zero blockers.

## Findings

- Non-blocker: the saved release-gate JSONs were generated before the final
  evidence commit. The generic gate belongs to source commit `1d36dd3`, and the
  package gate belongs to package commit `3d7b6e2`. The later delta contains
  documentation, evidence and release artifacts, not runtime code.
- Non-blocker resolved during sealing: the initial audit found that the
  persistent-state claim only had a boolean assertion. The final evidence now
  includes `board/visual/persistent-hash-proof.json`, with sanitized matching
  before/after hashes.
- Non-blocker resolved during sealing: the initial audit found this directory
  empty and `result.json` pending. This report is the independent audit being
  preserved.

## Checks

- The package source commit is an ancestor of the evidence HEAD.
- Evidence and release manifests are byte-identical.
- Payload SHA-256 is
  `e7812eb6737182ab95b0f43259e19d156c74dc5a21553795d5817c26dee060a0`.
- Manifest SHA-256 is
  `25329f346610b843aaa0eeef7f1380308ebab604735876d0905f2ddfdada8136`.
- Both saved gates passed all `84/84` checks.
- Stable policy rejected the homologation package with rc `41`.
- Apply, rollback and reapply returned rc `0`.
- Final state shows C21.20 current, C21.19 previous, player active with zero
  restarts, settings inactive, stable policy restored, timer active, Ethernet
  connected and Wi-Fi connected.
- The real framebuffer captures show only Ethernet, the current Wi-Fi and the
  option to choose another network. Bench mode is absent.
- Targeted privacy inspection found no credential, token, SSID value, IP
  address or raw NetworkManager profile.

Open Wi-Fi, captive portal, stable publication and a new reference image remain
explicit non-claims.
