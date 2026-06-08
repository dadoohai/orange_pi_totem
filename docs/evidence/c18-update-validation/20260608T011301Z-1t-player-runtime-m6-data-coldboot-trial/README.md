# C18 player-runtime M6 decisive data cold-boot trial

This directory stores sanitized evidence for the C18 M6 player-runtime
`/data` cold-boot trial on golden image `c18-hwdecode-lab-1t`.

Result: passed under the current C18 OTA release gate in decisive mode.

Scope proven:

- lab-only A -> B apply with verified `/data/player-runtime/current`;
- real reboot with B adopted from `/data`;
- deep-health passed for B after cold boot;
- rollback restored A from `/data` previous, not image fallback;
- service deep-health passed after rollback;
- host release gate accepted the archived evidence in decisive mode;
- public `player-runtime` CLI remained frozen with rc=44.

Important non-claims:

- no public thaw;
- no GitHub publish or auto-pull;
- no stable/production authorization;
- no physical power-loss test;
- no soak/endurance claim.

Operational notes:

- Two earlier attempts in this round were intentionally not reused as decisive
  evidence: one exposed `repo_dirty: null` in the M6 repo identity handoff, and
  one correctly rejected a canary path outside the allowed roots.
- The successful run used commit `ac59f7f1fe887fe694fe41e5c0896ef2ecf63ca2`
  after both harness fixes were committed and release-gated.
- Raw logs and temporary runtime directories were intentionally not archived in
  this evidence directory.
