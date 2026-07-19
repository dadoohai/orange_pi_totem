# Final deep-health boundary assessment

The first 60-second final health window is retained as negative evidence in
`health-final/`.

## Observed facts

- The collector reported only `motion_frame_progress_ok` and
  `playback_progressed` as failed.
- All 57 samples used `v4l2request-copy` and the expected MPV path.
- `time_pos_progressed=true`; MPV restart, service restart, media-load failure,
  panfrost fault, MMC reset, and ext4 error counters were all zero.
- Five complete motion-media episodes had sustained increasing frame numbers.
- The two rejected episodes were boundary-only samples: one sample without a
  coherent frame immediately before a frame reset, and one final sample with
  frame `1` at the exact end of the collection window.

This makes the negative result a window-boundary classification failure, not
evidence of stopped playback. The raw TSV and all sidecars remain committed so
the conclusion is independently reproducible.

## Corroboration

- `health-after-apply/`: passed after physical C26.17 apply.
- `health-after-rollback/`: passed after physical rollback to C26.16.
- `health-final-retry/`: passed after reapply of C26.17 with 28/28 expected
  hardware-decode samples, five media aliases, and zero failed episodes.

## Disposition

This does not block the byte-identical `totem-core` stable alignment. A future
health-gate hardening round should model terminal one-sample transition
boundaries explicitly, with adversarial fixtures that still reject a player
that is genuinely stuck.
