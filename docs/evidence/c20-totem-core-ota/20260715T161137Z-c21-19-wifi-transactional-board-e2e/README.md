# C21.19 transactional Wi-Fi board E2E

## Claim

C21.19 is a homologation-only accumulated `totem-core` candidate. It makes the
persistent product Wi-Fi profile transactional: a successful connection is
kept, while activation or IPv4 failure restores the exact previous profile.
The board roundtrip, positive and negative Wi-Fi paths, visual cancel flow,
reboot persistence and playback were exercised on hardware.

It is not a stable promotion, public OTA release or new reference image.

## Identity

- Version: `c21.19-wifi-transactional-20260715T145334Z-a214648`
- Package source: `a214648540cf8a11791cffdb9d25bf7d57196f01`
- Payload SHA-256: `c9f743106203fb87809ce5f36f13b115bcf1fb553b1ba825ec8f40c918f706cf`
- Manifest SHA-256: `2c483d223605233771f5a34746fcfbc01b3afc24acc81e3340b732ac13ca6402`
- Channel: `homologation`
- Public reference unchanged: `prod14` + C25B + C21.12 stable

## Results

- The clean source and exact package release gates passed `84/84` before board
  apply.
- Stable policy rejected the homologation package with rc `41`.
- Governed apply, rollback to C21.18 and reapply of C21.19 passed with rc `0`.
- A real SSID containing two trailing spaces connected, acquired IPv4 and was
  retained as the persistent product profile in mode `0600` with autoconnect.
- A deliberately nonexistent SSID failed and restored the exact prior profile;
  Ethernet, Wi-Fi and Dadooh health remained available.
- The installed wizard opened through its governed systemd session, rendered
  the current Wi-Fi option on the real framebuffer and canceled without
  changing config, retained context or NetworkManager profile hashes.
- The reboot changed `boot_id` and preserved C21.19 as current, C21.18 as
  previous, stable policy, enabled/active timer, both network links and the
  exact whitespace-bearing Wi-Fi profile.
- Post-reboot playback passed over 104 samples and five media aliases with
  frame progress, `v4l2request-copy`, aligned status/MPV, zero player restarts,
  zero media failures and zero GPU/MMC/ext4 deltas.

## Playback diagnostic correction

The first two pre-reboot collections remain negative for their real reasons.
The third contained one sample where MPV had completed a short chained
transition before public status caught up; subsequent aligned samples proved
continuous frame progress. Commit `c075a55` accepts only that final single
unknown hop when both boundaries, forward chain, local decode evidence,
sequence, timing and recovery progress are proven. R1 and R2 remain red while
the unchanged R3 artifacts become green.

`c18_playback_health_summary.py` is image-fixed and is not part of the C21.19
`totem-core` payload. Commit `c075a55` is therefore an input to the next
reference image, not a silent change on this board. The board's existing
summary independently passed the clean post-reboot collection.

## Honest limits

- The dynamic uinput keyboard created by the QA helper was not observed by the
  already-running F10 daemon. The visual flow therefore used the governed
  `totem-open-settings.service`. This round does not re-claim the physical F10
  trigger, which was outside the Wi-Fi code delta.
- The positive Wi-Fi test proves the available lab access point, not every AP,
  captive portal, RF condition or driver failure in the field.
- C21.19 was applied locally under temporary homologation policy. It was not
  published or consumed by the public stable timer.
- No credential, SSID value, API key, IP address or raw NetworkManager profile
  is included in this evidence.

## Evidence map

- `package/`: exact manifest and package hashes.
- `board/transaction/`: blocked stable apply, apply/rollback/reapply and timer
  restoration.
- `board/wifi/`: sanitized positive and rollback-on-failure results.
- `board/visual/`: real framebuffer captures and unchanged before/after hashes.
- `board/health/`: preserved negative runs, narrow reconciliation and clean
  post-reboot collection.
- `board/post-reboot/`: final state, sanitized profile proof and updater status.
- `audits/`: independent adversarial reviews.
- `gates/`: clean generic and exact-package release-gate results.
