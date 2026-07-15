# Playback-summary re-audit

The first patch was blocked independently for two fail-open cases:

- frame regressions could be counted as aggregate positive progress;
- missing `rel_sec` values could be interpreted as a zero-second run.

The final implementation additionally requires contiguous positive sequence
numbers, present non-negative strictly increasing timestamps, the existing
sample/time bounds, one forward alias, motion/decode evidence before and after,
monotonic frames and sustained progress. It never reclassifies the unknown rows
as content evidence.

Independent re-audit verdict: zero blockers. The reviewer reproduced the two
original attacks and confirmed they now fail. Invalid sequence, regressive,
negative, missing or over-limit timing, missing/frozen/reset frames, invalid
local evidence, status-ahead, terminal and oversized runs also failed. The
fixture suite passed `105/105`; no audit changes were made.
