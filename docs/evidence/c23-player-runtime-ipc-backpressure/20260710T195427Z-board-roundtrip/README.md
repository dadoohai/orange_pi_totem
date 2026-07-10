# C23 board round-trip and continuous playback

Date: 2026-07-10 UTC

Target:

- version: `c18.player-runtime-homolog-20260710-c23-ipc-fe4347c`
- source commit: `fe4347c81ccc40218c4763fbde68badbd30de2a3`
- health re-evaluator commit: `27972ed7e249da8bb2fbcf1660ecf2d0cdd1fa05`
- payload SHA256: `88471756039a492a6857c2b8c37fbac4a4ff56602f0934729960fc77d6d94f80`
- tree SHA256: `340e44ff7e441ec7863e1d660d66d03dfc1fe29d4195d6e52aa240025b35cf4f`

## Result

C23 passed the governed lab apply, rollback to C22, reapply from the linked
previous release and two continuous 10-minute playback observations. The
decisive clean observation covered 560 real samples and nine media aliases with
zero `media_load_failed`, MPV restart, systemd restart, watchdog action, IPC
error, IPC timeout, panfrost delta, MMC error or ext4 error.

The parallel socket observation covered 120 samples with one stable MPV PID,
`NRestarts=0` and `max_send_q=0` throughout. This directly closes the C22
backpressure failure, whose queue grew until MPV stopped responding.

Final board state:

- C23 `current`, C22 `previous`;
- C21 remains quarantined;
- player service active with one MPV and real playback;
- both update timers active;
- generic public `player-runtime` rollback still blocked with `rc=44`.

## Preserved negative evidence

The first candidate apply ran while the production player still owned DRM. The
candidate could not acquire display output, was rejected and C22 stayed active.
The scoped quarantine reset records that display-contention diagnosis. Repeating
the governed apply with the production service paused passed.

The first post-reapply 10-minute collector started before public status reached
`playing`; its first five samples were `waiting_for_content`, so it correctly
failed `status_no_failures` even though playback then stayed clean. The runbook
now requires `playing`, `mpv_running=true` and a current item before starting the
decisive window.

The second post-reapply collector originally failed only
`playback_progressed`. Raw samples showed that the health summarizer grouped MPV
frame counters by the lagging public-status item and mixed frames from two
different media at one transition. The original false-red result is preserved
in `final-clean-health-result.json`. Re-evaluation of the same immutable samples
after segmenting MPV frame progress by MPV media identity is preserved in
`final-clean-health-recheck.json` and passes with zero failed frame segments.
Regression tests retain rejection of frozen frames, short progress followed by
stall, and a stalled earlier media segment.

## Claims and limits

This evidence closes the C23 fix and board-local package round-trip. It does not
claim publication of the C23 exact-target GitHub release, production auto-pull
of C23, broad `latest`, fleet rollout, or a final prod8 image. Those are the next
separate operational steps.
