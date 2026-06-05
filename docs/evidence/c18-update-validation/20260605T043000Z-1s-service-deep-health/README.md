# C18 1s Service Deep-Health Evidence

Sanitized hardware evidence for validating `c18-hwdecode-lab-1s` after flashing.

## Scope

- Board image marker: `c18-hwdecode-lab-1s`.
- Image SHA256:
  `bc0a39cf0cc4502acb7f9b4726589449288783fa4d44821593ab15c4c2c1967f`.
- Config was written from the homologation seed through the governed
  contract/handoff/writer path.
- Config values and private values are not included.
- This proves service playback/deep-health after config write. It does not prove
  power-loss safety, public `player-runtime` thaw, GitHub publish, auto-pull,
  stable/production readiness, or soak endurance.

## Result

- `playback-deep-health-public.json`: `passed=true`.
- `hwdec-current`: `v4l2request-copy`.
- `mpv_count=1`, `total_mpv_count=1`.
- `media_load_failed=0`, `mpv_restart=0`, `NRestarts_delta=0`.
- `panfrost_faults=0`, `mmc_timeout_reset=0`, `ext4_errors=0`.
- Frame progress and playback transitions observed.
- Privacy scan: `passed=true`.

## Files

- `config-write-public.json`: sanitized config-write summary.
- `playback-deep-health-public.json`: sanitized deep-health verdict.
- `playback-samples.tsv` and `status-samples.ndjson`: sanitized samples with
  media/path aliases only.
- `deep-health-*.json`: sanitized sidecars.
- `evidence-manifest.json`: file hashes and scope metadata.
- `privacy-scan.json`: leak scan result.
