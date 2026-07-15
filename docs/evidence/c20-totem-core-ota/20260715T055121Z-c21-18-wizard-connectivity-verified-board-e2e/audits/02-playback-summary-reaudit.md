# Playback-summary re-audit

The first patch was blocked independently for two fail-open cases:

- frame regressions could be counted as aggregate positive progress;
- missing `rel_sec` values could be interpreted as a zero-second run.

The final implementation additionally requires contiguous positive sequence
numbers, present non-negative strictly increasing timestamps, the existing
sample/time bounds, one forward alias, motion/decode evidence before and after,
monotonic frames and sustained progress. It never reclassifies the unknown rows
as content evidence.

Independent re-audit verdict after the first remediation: zero blockers within
that audit scope. The reviewer reproduced the two original attacks and
confirmed they failed. Invalid sequence, regressive, negative, missing or
over-limit timing, missing/frozen/reset frames, invalid local evidence,
status-ahead, terminal and oversized runs also failed. The fixture suite then
passed `105/105`; no audit changes were made.

A later independent final-behavior audit widened the adversarial boundary and
found that the aligned samples immediately before and after the unknown run
were not included in sequence/time continuity validation. That later finding,
its correction and the final zero-blocker re-audit are recorded in
`03-final-behavior-audit.md`.
