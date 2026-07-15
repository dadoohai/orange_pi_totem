# Independent Re-audits

## C21.14 Final Audit

Verdict: blocked before promotion.

The independent auditor reproduced two defects in the committed candidate:

1. active Wi-Fi plus cached `full` connectivity could report `online` without
   a default route;
2. the fallback MPV IPC request identifier grew without a fixed bound.

It also identified composable read timeouts as a non-blocking latency risk.
C21.14 was superseded without stable promotion.

## Corrected Source Re-audit

Target: `0c08a26ec1be2d1bd5973b56ac47f48e4f4f0167`.

Verdict: zero blockers; approved to package for homologation.

The same auditor directly reproduced:

- no route plus cached `full` connectivity returns unknown, not online;
- a verified route returns online;
- the request identifier wraps from `2147483647` to `1`;
- four deliberately slow read commands share an approximately one second
  total budget rather than four independent seconds;
- no unrelated semantic regression in the touched paths.

## Panfrost Follow-up

An independent read-only review found no direct regression vector between the
C21.15 source delta and the framebuffer/settings teardown path. It also found
that a zero-delta health window alone could not explain the historical event,
so the event must remain explicit and RCA must not be claimed.

The recommended official settings stop probe was then run three times in
addition to three wizard open/cancel cycles. No new Panfrost event occurred.
This supports retaining the observation as residual risk rather than silently
discarding it; it does not make the execution clean or provide an RCA.

## Closing Audit Decision

Two independent auditors reviewed commit `463823f`. The bounded-resource audit
found no blocker for the narrow claim, while preserving the Panfrost event and
the lab-only rollback target as residuals. The general adversarial audit found
a new blocker in default-route parsing: routes without `RTF_UP` or with a
nonzero mask were still accepted.

The central review reproduced both malformed inputs and accepted the blocker.
C21.15 is therefore blocked despite its successful board roundtrip. The full
closing findings are recorded in `final-independent-audit.md`.
