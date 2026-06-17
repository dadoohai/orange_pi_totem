# C18 lab quarantine reset - no-canary retry

Governed lab reset for target `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

The prior apply attempt ran without `--canary-media`, produced an empty candidate playlist, failed closed, and quarantined the target. This reset removed exactly that quarantine entry after verifying:

- target identity matched the manifest/payload;
- candidate health evidence showed `canary_media_used=false`;
- playlist size was 0;
- no MPV playback, hwdec, IPC success, GPU fault delta, or storage fault was observed;
- current/previous links were unchanged;
- public apply/rollback/reconcile remained frozen.

Result: `passed=true`, `removed_count=1`.

Non-claims: not apply, not rollback, not production, not stable, not public thaw, not H2 evidence.
