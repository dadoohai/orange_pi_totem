# Independent playback-summary RCA

Verdict: the raw board evidence did not demonstrate a product or playback
failure. It exposed a medium-severity evidence-tool inconsistency.

Facts independently verified:

- the collector classifies only paths matching status `current_item` or
  `next_item`;
- three mid-run samples had MPV on a new path while status still named the old
  item, then status recovered to that exact MPV path;
- frames advanced `17 -> 50 -> 84 -> 114`, HW decode was
  `v4l2request-copy`, VO was configured and dimensions were valid;
- `status_mpv_path_aligned` accepted the same bounded transition, while the
  startup-only unknown-media check rejected it;
- existing fixtures did not cross the current typed collector schema with the
  transition-lag path.

Accepted central action: reconcile only bounded, forward, locally healthy and
fully recovered transition rows; keep terminal, stalled, reverse/status-ahead,
unbounded or locally invalid rows fail-closed. The original negative artifact
must remain preserved.
