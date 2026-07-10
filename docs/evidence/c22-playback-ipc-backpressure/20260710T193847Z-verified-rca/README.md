# C22 playback IPC backpressure RCA

Read-only live-board evidence collected on 2026-07-10 after the prod7 M5
roundtrip. The board was running C22 as `current`; OTA state was not changed.

## Verified sequence

- MPV PID `10475` remained alive while its Unix IPC `Send-Q` grew from `89088`
  bytes at `19:38:47Z` to `213504` bytes at `19:42:13Z`.
- At `19:42:12Z`, the next media switch timed out after about 2 seconds and
  emitted `media_load_failed`.
- The watchdog then observed IPC unresponsive and the MPV subprocess restarted;
  systemd `NRestarts` remained zero because the kiosk process stayed alive.
- The replacement MPV PID `11802` appeared with `Send-Q=0`, directly correlating
  process replacement with queue reset.
- Different valid media aliases fail across cycles, so the event is not bound to
  one corrupt file.

The runtime configuration used fresh connections for queries but retained an
unread persistent socket for control commands. MPV responses/events accumulated
on that client until backpressure blocked all IPC handling. This explains the
repeating user-visible sequence: playback, black/startup screen, internal MPV
restart, recovery, then recurrence minutes later.

## Files

- `ipc-backpressure-samples.tsv`: five-second PID, process age and socket queue
  samples spanning growth, failure and reset.
- `verified-event-journal.txt`: complete service journal for the measured event.
- `post-m5-playback-event-journal.txt`: earlier post-M5 failures with the same
  signature.
- `incident-summary.json`: read-only incident collector output.
- `live-state-after-event.txt`: player/OTA state after recovery.
- `m5-current-gate-recheck.json`: current gate re-evaluation preserving the
  exact OTA mechanics result while blocking product cleanliness for the short
  final window.

## Non-claims

This evidence verifies the failure mechanism. It does not by itself prove the
C23 correction, distribution readiness, stable promotion or public thaw. Those
require a governed C23 package and a continuous clean hardware window.
