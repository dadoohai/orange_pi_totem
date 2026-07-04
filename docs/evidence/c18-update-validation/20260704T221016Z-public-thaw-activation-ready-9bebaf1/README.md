# C18 player-runtime public thaw activation readiness - 9bebaf1

This snapshot validates that the already approved H2/stable/thaw evidence is
ready for a separate operational activation step for the C18 player-runtime
target:

- package: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`
- source commit: `9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522`
- payload SHA256: `d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0`
- evaluated at: `2026-07-04T22:10:16Z`

Result:

- `passed=true`
- `result_claim=public_thaw_activation_ready`
- `blockers=[]`

This is still not the execution itself. It does not publish a release, fetch a
release, enable auto-pull, execute public thaw, mutate a device, or override the
public `rc=44` freeze by itself.

Important scope:

- the clean 24h soak remains `clean_soak_passed=false`;
- H2 is green because the HDMI-event soak was accepted by explicit business
  exception for this exact target;
- the package manifest remains `channel=homologation`;
- the stable decision remains `channel=stable`;
- auto-pull remains disabled.
