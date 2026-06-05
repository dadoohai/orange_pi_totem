# C18 1o Service Deep-Health Evidence

Sanitized hardware evidence for promoting `c18-hwdecode-lab-1o` from offline
candidate to the current lab/delivery golden.

- Board image marker: `c18-hwdecode-lab-1o`.
- Config source: real config written from the private seed through the C18
  writer path; private values are not included here.
- Collection mode: non-destructive service observation, 30 seconds, no player
  stop/restart during collection.
- Artifact id: `c18-1o-deep-health-20260605T003747Z-service`.
- Image sha256:
  `07f9ee4f3f870f0fdb083eba7992a24b166939c768fc962e44a18d781117b164`.
- Result: `passed=true`, `failure_reasons=[]`.
- Key counters: `samples=22`, `ipc_success=22`,
  `estimated_frame_progressed=true`, `hwdec_expected_samples=22`,
  `hwdec_unexpected_samples=0`, `media_load_failed=0`, `mpv_restart=0`,
  `nrestarts_delta=0`, `panfrost_faults=0`, `mmc_timeout_reset=0`,
  `ext4_errors=0`, `total_mpv_count=1`.
- Evidence manifest: `evidence-manifest.json`.
- Privacy scan: `privacy-scan.json`, result `passed`, zero matches for
  `api_key`, `api_url`, `environment_id`, token/secret/password/SSID, URL,
  IPv4, or MAC patterns.

These artifacts prove the image-level baseline service path, not a persistent
`player-runtime` OTA thaw. Public apply/rollback for `kiosky-player` and
`player-runtime` remains frozen with `rc=44`.
