# C21.15 Bounded Connectivity Board E2E

Status: passed as a `totem-core` homologation candidate on 2026-07-15.

## Identity

- version: `c21.15-wizard-connectivity-bounded-20260715T011533Z-0c08a26`
- source commit: `0c08a26ec1be2d1bd5973b56ac47f48e4f4f0167`
- payload SHA256: `3e84358d6745b31e3232680b8d3e10c1048e5e81f8b7fca921e05dbd5deaefea`
- manifest SHA256: `c5505532aa0990c9cb4ade87f3d441789d850d9507b6ba1a947e6a47d516fdcd`
- board: `orangepizero3`, C18 prod14 reference image

## Result

- generic and package-bound release gates: `84/84`;
- stable policy rejected the prerelease with `rc=41` and no mutation;
- governed apply, rollback and reapply completed with `rc=0`;
- player stayed active with `NRestarts=0`;
- settings ended inactive and the update timer ended active/enabled;
- config, retained settings and production policy hashes were preserved;
- real keyboard E2E opened the wizard, reached review and cancelled back to
  playback;
- live read-only collection reported Ethernet plus verified default route and
  cached `full` connectivity without an external probe;
- the final delta health window passed with HW decode, advancing frames, one
  MPV and no player restart.

The board rollback target during this lab roundtrip was C21.14 because it was
the immediate previous release on the board. C21.14 remains superseded and is
not an approved stable fallback. C21.12 remains the distribution/stable return
reference until an explicit promotion decision.

## Audit Closure

The final audit of C21.14 found two blockers before promotion: it could report
`online` without a verified default route, and its MPV IPC request counter had
no fixed bound. C21.15 requires the route for a positive internet state, wraps
the counter, and applies one monotonic time budget to the entire read-only
network collection. The same auditor reproduced the adversarial cases and
reported zero blockers before this package was built.

## 24/7 Boundaries

- one in-memory snapshot is replaced in place;
- there is no thread, queue or connectivity history;
- all NetworkManager reads share one bounded collection deadline;
- framebuffer refresh creates no file, while fallback rendering reuses two
  files;
- session SVGs use a fixed ring of 64 files;
- MPV IPC request identifiers wrap at a fixed maximum;
- settings scratch paths are reset per session.

## Preserved Residual

The first absolute health collection preserved four pre-existing Panfrost
fault lines (two kernel events), including one event observed near the first
C21.15 visual session. Playback checks were otherwise green and the fault
delta during that collection was zero. Cause was not proven.

The follow-up ran three wizard open/cancel cycles and three official settings
stop probes. All six cycles added zero Panfrost events, retained
`NRestarts=0`, and the three official probes passed within their 15 second
limit. A subsequent delta health window passed. This bounds the observation;
it does not claim an RCA or claim that the historical event cannot recur.

## Non-Claims

- no stable promotion or public publication;
- no new reference image;
- no network mutation, rescan, speed test or external connectivity probe;
- no change to player-runtime, media-system, field data or OTA policy;
- no verified RCA for the preserved Panfrost event.
