# C18 1s Cold-Boot Deep-Health Evidence

Sanitized hardware evidence for validating `c18-hwdecode-lab-1s` after a
controlled reboot.

## Scope

- Board image marker: `c18-hwdecode-lab-1s`.
- Image SHA256:
  `bc0a39cf0cc4502acb7f9b4726589449288783fa4d44821593ab15c4c2c1967f`.
- The service booted from the image fallback player; no
  `/data/player-runtime/current` or legacy `/data/apps/kiosky-player/current`
  was present.
- The systemd drop-in was present with `RequiresMountsFor=/data` and
  `After=local-fs.target`; boot reconcile ran as an explicitly authorized
  non-fatal `ExecStartPre`.
- This proves cold-boot service playback/deep-health and boot reconcile
  ordering for the image baseline. It does not prove power-loss safety, public
  `player-runtime` thaw, GitHub publish, auto-pull, stable/production
  readiness, or soak endurance.

## Result

- `coldboot-state.json`: marker present, timer disabled/inactive, policy freeze
  preserved, `player-runtime` public apply/rollback/reconcile all returned
  `rc=44`, and the active MPV executable was `/opt/totem/hwdecode/bin/mpv`.
- `playback-deep-health-public.json`: `passed=true`.
- `hwdec-current`: `v4l2request-copy`.
- `mpv_count=1`, `total_mpv_count=1`.
- `media_load_failed=0`, `mpv_restart=0`, `NRestarts_delta=0`.
- `panfrost_faults=0`, `mmc_timeout_reset=0`, `ext4_errors=0`.
- Frame progress and playback transitions observed.
- Privacy scan: `passed=true`.

## Files

- `coldboot-state.json`: sanitized boot-state summary.
- `playback-deep-health-public.json`: sanitized deep-health verdict.
- `playback-samples.tsv` and `status-samples.ndjson`: sanitized samples with
  media/path aliases only.
- `deep-health-*.json`: sanitized sidecars.
- `evidence-manifest.json`: file hashes and scope metadata.
- `privacy-scan.json`: leak scan result.
