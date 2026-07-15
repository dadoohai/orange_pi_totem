# Final Independent Audit

Target: `463823f21e429e8c2ca6fa2b4df5f56f3fe168af`.

## Auditor A - Package And Claim

Verdict: blocked.

The auditor independently confirmed package identity, `84/84` release gate,
`81/81` policy tests, self-tests, stable policy denial, apply/rollback/reapply,
preserved state hashes, real framebuffer captures, SHA256SUMS and absence of
secrets. It also compared all 18 payload executables to source commit
`0c08a26` with zero mismatch.

Blocker: `default_route_devices_from_text()` accepted malformed route rows that
had destination zero but either lacked `RTF_UP` or carried a nonzero mask. With
an active Wi-Fi device and cached `full` connectivity, those rows still yielded
`internet=online`. The central review reproduced both cases.

Residuals, not additional blockers for homologation:

- the visual E2E coincided with the preserved Panfrost event and one partial
  framebuffer capture, although six later cycles were clean;
- two sandbox fields are declarative rather than independently measured; the
  auditor compensated by comparing payload bytes directly to Git.

## Auditor B - Bounds, Panfrost And Rollback

Verdict before the parser finding: zero blockers for the narrow claim.

This auditor stress-tested the resource design and confirmed one replaceable
cache, no queue/thread/history, a fixed 64-file screen ring, two refresh slots,
a circular IPC identifier and a shared command deadline. It correctly limited
the claim to architectural boundedness, not a physical 24-hour run.

It classified the Panfrost event as an explicit residual and confirmed that
the transaction proved `C21.15 -> C21.14 -> C21.15`, not a direct rollback to
C21.12. The docs preserve that distinction.

## Central Decision

The route parser finding is valid and strikes the central correction claimed
by C21.15. It overrides the earlier zero-blocker review. C21.15 is blocked and
must not be promoted or treated as the accumulated homologation candidate.
