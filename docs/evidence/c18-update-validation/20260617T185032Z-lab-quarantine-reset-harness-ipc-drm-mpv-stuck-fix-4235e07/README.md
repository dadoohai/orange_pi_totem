# C18 lab quarantine reset - harness IPC/DRM retry

Governed lab reset for target `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

The prior canary apply attempt failed closed because the harness used a long AF_UNIX socket path and the active service still held DRM. This reset removed exactly that quarantine entry after verifying:

- target identity matched the manifest/payload;
- canary media was used;
- logs contained `AF_UNIX path too long`;
- logs contained `Failed to acquire DRM master: Permission denied`;
- no GPU fault delta or storage fault was observed;
- current/previous links were unchanged;
- public apply/rollback/reconcile remained frozen.

Result: `passed=true`, `removed_count=1`.

Non-claims: not apply, not rollback, not production, not stable, not public thaw, not H2 evidence.
