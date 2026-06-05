# C18 1r Service Deep-Health Evidence

Sanitized hardware evidence for promoting `c18-hwdecode-lab-1r` from offline
candidate to the current lab/delivery golden.

- Board image marker: `c18-hwdecode-lab-1r`.
- Config source: real config written from the private seed through the C18
  writer path; private values are not included here.
- Collection mode: non-destructive service observation, 45 seconds, no player
  stop/restart during collection.
- Artifact id: `c18-1r-service-deep-health`.
- Image sha256:
  `23ef26b4cdbd6c35643fdc41d8666da33dd259b387af05864c8f063506f7711c`.
- Result: `passed=true`,
  `failure_reasons=[]`.
- Key counters: `samples=45`,
  `ipc_success=45`,
  `unique_aliases=4`,
  `status_unique_aliases=4`,
  `mpv_unique_aliases=4`,
  `status_transitions_observed=true`,
  `mpv_media_transitions_observed=true`,
  `estimated_frame_progressed=true`,
  `estimated_frame_evaluable_segments=4`,
  `estimated_frame_failed_segments=0`,
  `estimated_frame_positive_steps=11`,
  `hwdec_expected_samples=45`,
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

The hardware probe also confirmed the C18 update posture after config was
written: policy restricts updates to `totem-core`, `totem-update-agent.timer` is
disabled/inactive, the update service targets `dadoohai/orange_pi_totem` with
`--component totem-core`, no `/data/player-runtime/current` or legacy
`/data/apps/kiosky-player/current` is present, and public apply/rollback/reconcile
for `kiosky-player` and `player-runtime` still returns `rc=44`.

These artifacts prove the image-level baseline service path, not a persistent
`player-runtime` OTA thaw. A persistent `/data/player-runtime/current` trial
must still produce its own evidence package and pass
`scripts/qa/c18_player_runtime_evidence_gate.py`.
