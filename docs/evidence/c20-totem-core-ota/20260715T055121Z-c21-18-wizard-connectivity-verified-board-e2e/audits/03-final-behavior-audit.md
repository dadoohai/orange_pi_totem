# Final behavior audit

The independent final audit confirmed the real board playback trace was
healthy and reproducible, but initially found one blocker in the evidence
tool: sequence and relative-time continuity covered only the unknown run, not
the aligned samples that bounded it. Missing or detached boundary values could
therefore make a synthetic invalid transition appear bounded.

The central remediation extended both validations across the complete window:
aligned-before, unknown run and aligned-after. Six negative cases were added:
missing sequence before/after, detached sequence, missing time before/after and
detached timing.

Independent re-audit at `d522e22` reproduced all six attacks. Every attack
failed closed with no accepted transition, while the unchanged board evidence
still passed and accounted exactly for samples 35, 36 and 37. The focused
fixture suite passed `106/106`.

Verdict: zero behavior blockers after remediation.

Harness note: `child_count` reads only the process-leader task and is not an
authoritative count for a worker-thread-spawned process. The resource claim is
instead supported by the exact `probe_pid` observations (three distinct,
non-overlapping probe processes), bounded threads/FDs/RSS/files and successful
session cleanup. This is future harness debt, not a product blocker.
