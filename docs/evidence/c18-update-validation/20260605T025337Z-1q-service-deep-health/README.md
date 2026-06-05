# C18 1q Service Deep-Health Evidence

Sanitized hardware evidence for promoting `c18-hwdecode-lab-1q` from offline
candidate to the current lab/delivery golden.

- Board image marker: `c18-hwdecode-lab-1q`.
- Config source: real config written from the private seed through the C18
  writer path; private values are not included here.
- Collection mode: non-destructive service observation, 30 seconds, no player
  stop/restart during collection.
- Artifact id: `c18-1q-deep-health-current-fixed`.
- Image sha256:
  `d487bf33737d5af4ba4bbf7859163cf21f0762ef4c5180f2aed3685e4aa5c009`.
- Result: `passed=true`,
  `failure_reasons=[]`.
- Key counters: `samples=30`,
  `ipc_success=30`,
  `unique_aliases=4`,
  `estimated_frame_progressed=true`,
  `estimated_frame_positive_steps=4`,
  `hwdec_expected_samples=30`,
  `hwdec_unexpected_samples=0`,
  `media_load_failed=0`,
  `mpv_restart=0`,
  `nrestarts_delta=0`,
  `panfrost_faults=0`,
  `mmc_timeout_reset=0`,
  `ext4_errors=0`,
  `total_mpv_count=1`.
- Evidence manifest: `evidence-manifest.json`.
- Privacy scan: `privacy-scan.json`, result `passed`, zero matches for
  `api_key`, `api_url`, `environment_id`, token/secret/password/SSID, URL,
  IPv4, or MAC patterns.

This run also exposed and fixed a test-tooling false negative: transition
identity must prefer the sanitized status item identity when the MPV cache path
repeats across playlist items. The image behavior did not change; the evaluator
used for this evidence includes that fix.

These artifacts prove the image-level baseline service path, not a persistent
`player-runtime` OTA thaw. Public apply/rollback/reconcile for `kiosky-player`
and `player-runtime` remains frozen with `rc=44`.
