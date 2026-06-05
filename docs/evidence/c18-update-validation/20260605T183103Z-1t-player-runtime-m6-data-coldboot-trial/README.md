# C18 player-runtime M6 data cold-boot trial

This directory stores sanitized evidence for the first decisive C18 M6
player-runtime `/data` cold-boot trial on golden image `c18-hwdecode-lab-1t`.

Result: passed. The host-side C18 OTA release gate was run in decisive mode and
reported `passed=true`.

Scope proven:

- lab-only A -> B apply with verified `/data/player-runtime/current`;
- real reboot with B adopted from `/data`;
- deep-health passed for B after cold boot;
- rollback restored A from `/data` previous, not image fallback;
- service deep-health passed after rollback;
- public `player-runtime` CLI remained frozen with rc=44.

Important non-claims:

- no public thaw;
- no GitHub publish or auto-pull;
- no stable/production authorization;
- no physical power-loss test;
- no soak/endurance claim.

Operational notes:

- An earlier attempt used a canary under `/data/state`, which the candidate
  health contract correctly rejected; the successful run used `/tmp`.
- A second attempt reused already quarantined B content; the updater correctly
  rejected it by `tree_sha256_quarantined`. The successful run used unique A/B
  payload content without clearing quarantine.
- Raw logs and temporary runtime directories were intentionally not archived in
  this evidence directory.
