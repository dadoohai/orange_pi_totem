# C18 operational resume current snapshot

Status: `c18_operational_resume_ready` for the controlled
`player-runtime` homologation pilot target
`c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`.

This snapshot proves only that the operator-assisted pilot can resume now with
fresh governance inputs:

- current pilot authorization window: `2026-06-16T23:10:00Z` to
  `2026-06-17T03:10:00Z`;
- fresh board preflight collected at `2026-06-16T23:14:48Z`;
- board policy `homologation`, `allow_prerelease=true`, timer disabled;
- public `player-runtime` apply/rollback/reconcile still frozen with `rc=44`;
- image marker `c18-hwdecode-lab-1x`;
- runtime C18 mpv stack proven by process path `/opt/totem/hwdecode/bin/mpv`
  and `hwdec=v4l2request-copy`;
- operational resume gate regenerated with the current macro-governance snapshot
  and passed from clean repo commit
  `178c2714d2cdd00ac5410d9ef7ec6efbf2372dfb`.

Non-claims: this is not production, not `stable`, not auto-pull, not public
thaw, not 24h soak, not 17/17 power-loss, and not H2 readiness.
