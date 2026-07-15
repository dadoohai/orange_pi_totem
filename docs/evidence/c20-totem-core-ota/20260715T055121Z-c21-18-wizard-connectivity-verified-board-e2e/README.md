# C21.18 connectivity indicator board E2E

## Claim

C21.18 is a homologation-only accumulated `totem-core` candidate. It presents
the verified active transport and bounded Dadooh-service reachability in the
wizard without changing network state. It is not a stable promotion, image
release, generic Internet monitor, speed test, CDN/media-health proof or 24h
soak.

## Identity

- Version: `c21.18-wizard-connectivity-verified-20260715T045523Z-3bdbd18`
- Package source: `3bdbd1868693c3ffabcb7a5183c3a05b001d9c46`
- Payload SHA-256: `c408e671d130470b978e8246a4fa522ef16c831777202eac8c6ab14b716dbcfa`
- Manifest SHA-256: `e61120f7179391cc76cc6d8c3f802c727064605b32c98ea9753a1d66cc2e2d54`
- Channel: `homologation`
- Public reference unchanged: `prod14` + C25B + C21.12 stable

## Results

- Generic and exact-package release gates: `84/84`, zero failures.
- Stable policy rejected prerelease apply with rc `41`.
- Governed apply, rollback to C21.13 and reapply: rc `0`.
- Final board: current C21.18, previous C21.13, stable policy/timer restored,
  player active, settings inactive and player restarts `0`.
- Visual probe: Ethernet glyph and `OK` proven by framebuffer pixels on both
  orientation and Wi-Fi steps; config, retained context and network hashes did
  not change; cancel called no writer and restored playback.
- Resource observation: 600 seconds, RSS 44816..44820 KiB, FDs 6..12, one
  screen, zero refresh files and at most two threads.
- Exact refresh observation: three distinct service-probe processes in 60
  seconds; config, context, network, player restart count and playback state
  were preserved.

## Playback summary RCA

The original service-mode collection failed only
`unclassified_media_bounded_to_startup`: MPV had advanced to a new item for
three samples while public status still named the previous item. During those
samples frames advanced, `v4l2request-copy` and VO remained valid, and the next
sample aligned to the exact MPV path. The original negative summary is retained
under `board/health/transition-classification-negative/`.

The summary contract was reconciled narrowly: only a forward, contiguous,
bounded transition with alignment before and after, one new alias, valid local
decode evidence and sustained frame progress is accepted. Sequence and timing
must also remain contiguous across both aligned boundary samples. A terminal,
detached or non-progressing run remains denied. The unchanged raw board
artifacts were re-evaluated in
`board/health/transition-classification-reconciled.json` and passed with three
explicitly accounted transition samples.

`c18_playback_health_summary.py` is image-fixed and deliberately excluded from
`totem-core`. This correction is therefore a required input to the next
reference image; C21.18 did not silently replace the board copy.

## Non-claims and debt

- The 600-second run is not a 24h soak and cannot exclude slower leaks.
- The fixed health probe proves only bounded Dadooh-service reachability.
- C21.16 and C21.17 were superseded before board apply and never promoted.
- Real Wi-Fi apply child-process lifecycle remains separately recorded for
  future hardening; this read-only indicator does not execute that path.
- The harness `child_count` column inspects only the leader task and is
  informational. Bounded probe-process evidence comes from the exact
  `probe_pid` samples (three distinct, non-overlapping processes), together
  with the thread, FD, RSS and cleanup checks.
