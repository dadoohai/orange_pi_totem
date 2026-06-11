# C18 player-runtime - homologation pilot runbook

Status: controlled homologation pilot only. This is the H1.5 path between the
H1 decisive lab bundle and H2 stable/production. It uses `channel=homologation`
and operational `ring=pilot`. It is operator-assisted, rollback-ready, and keeps
the public `player-runtime` updater frozen at `rc=44`.

This runbook does not authorize production, `stable`, auto-pull, public thaw,
24h soak claims, 17/17 power-loss claims, or signature/attestation claims.

## Required gate

The final off-board gate is:

```sh
python3 scripts/qa/c18_player_runtime_pilot_readiness_gate.py \
  --package-manifest <B.manifest.json> \
  --package-payload <B.tar.gz> \
  --h1-release-gate-summary <committed-h1-decisive-release-gate.json> \
  --authorization <committed-pilot-authorization.json> \
  --preflight <committed-board-preflight.json> \
  --powerloss-evidence-dir <committed-powerloss-after_current_symlink> \
  --powerloss-evidence-dir <committed-powerloss-rollback_after_current_to_previous> \
  --powerloss-evidence-dir <committed-powerloss-rollback_after_previous_removed> \
  --powerloss-evidence-dir <committed-powerloss-rollback_after_quarantine> \
  --powerloss-evidence-dir <committed-powerloss-rollback_after_state_success> \
  --expect-image-tag <image-tag> \
  --expect-image-sha256 <image-sha256> \
  --expect-image-marker-sha256 <image-marker-sha256> \
  --json
```

The gate is default-deny. It also requires a clean Git tree and tracked inputs.
Commit evidence first, then run the gate from the clean tree.

## Authorization evidence

Create a JSON document with schema
`dadooh.c18.homologation_pilot_authorization.v1`.

Minimum required fields:

```json
{
  "schema": "dadooh.c18.homologation_pilot_authorization.v1",
  "approved": true,
  "ring": "pilot",
  "channel": "homologation",
  "operator_assisted_delivery": true,
  "rollback_ready": true,
  "operator": "operator-pilot-01",
  "rollback_owner": "rollback-owner-01",
  "expected_source_commit": "<40-hex-commit>",
  "window": {
    "start_utc": "2026-06-11T12:00:00Z",
    "end_utc": "2026-06-11T14:00:00Z"
  },
  "allowlisted_devices": [
    {
      "device_hash": "sha256:<64-hex-hash>",
      "label": "pilot-01"
    }
  ],
  "non_claims": [
    "no_production",
    "no_stable",
    "no_auto_pull",
    "no_24h_soak",
    "no_powerloss_17_17",
    "no_signature_or_attestation",
    "no_public_thaw"
  ]
}
```

Do not include raw serials, MAC addresses, private IPs, SSIDs, environment IDs,
tokens, or customer identifiers. Hash device identity off-board and commit only
the hash plus a sanitized label.

## Board preflight

Collect preflight after the target board is configured for pilot and before any
apply.

Required facts:

- policy `device_channel=homologation`;
- `allow_prerelease=true`;
- update timer disabled and inactive;
- public `player-runtime` apply, rollback, and reconcile still return `rc=44`;
- image tag, image sha256, and image marker sha256 match the H1 bundle;
- `mpv_path=/opt/totem/bin/totem-mpv-hwdecode`;
- `hwdec=v4l2request-copy`;
- sanitized `device_hash`;
- source commit matches the authorization.

Suggested preflight JSON schema:

```json
{
  "schema": "dadooh.c18.homologation_pilot_preflight.v1",
  "passed": true,
  "device_hash": "sha256:<64-hex-hash>",
  "source_commit": "<40-hex-commit>",
  "policy": {
    "device_channel": "homologation",
    "allow_prerelease": true
  },
  "timer": {
    "enabled": false,
    "active": false
  },
  "public_freeze": {
    "apply_local": {"returncode": 44, "frozen": true},
    "rollback": {"returncode": 44, "frozen": true},
    "reconcile": {"returncode": 44, "frozen": true}
  },
  "image": {
    "tag": "<image-tag>",
    "sha256": "<image-sha256>",
    "marker_sha256": "<image-marker-sha256>"
  },
  "player_runtime": {
    "mpv_path": "/opt/totem/bin/totem-mpv-hwdecode",
    "hwdec": "v4l2request-copy"
  }
}
```

If playback is already showing a repeated content loop or watchdog reset on a
specific media item, stop the pilot path and preserve runtime evidence. Record
the media label or backend ID, loop count before failure, and whether the log
shows `media_load_failed`, `MPV IPC unresponsive`, `Restarting MPV`, or only the
public "Dadooh iniciando player" recovery screen.

Use the read-only incident collector to produce a sanitized bundle while the
board remains in its live state:

```sh
python3 scripts/board/c18_playback_incident_collect.py \
  --operator-observed-label "<operator-visible-media-label>" \
  --operator-loop-count <count> \
  --operator-visible-recovery startup_screen \
  --operator-event loop_entered \
  --duration-sec 300 \
  --match-process-ipc \
  --classify-playlist \
  --json
```

If the same media recovers and later re-enters the loop, rerun against the same
`--output-dir` with `--operator-event loop_recovered` and then
`--operator-event loop_reentered`. Each run is preserved under
`runs/<run-id>/`. Commit the top-level `incident-summary.json`,
`operator-events.tsv`, and each relevant run's `incident-summary.json`,
`journal-signatures.ndjson`, and `deep-health/`; keep private artifacts off the
public evidence path unless a private audit explicitly requests them.

## Dry-run

Before touching `/data/player-runtime/current`, run the package gate and dry-run
the intended local package path off-board:

```sh
python3 scripts/qa/c18_player_runtime_release_gate.py \
  --manifest <B.manifest.json> \
  --payload <B.tar.gz> \
  --json
```

On board, keep the public updater frozen. Do not use GitHub, manifest URLs, or
auto-pull for `player-runtime`.

## Assisted apply

Apply only with the guarded lab harness and an operator present:

```sh
C18_PLAYER_RUNTIME_LAB_APPLY=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_lab_apply.py \
  --lab-only-apply \
  --manifest <B.manifest.json> \
  --payload <B.tar.gz> \
  --data-root /data \
  --allow-device-data-root \
  --canary-media <local-canary-video> \
  --output-dir <evidence-root>/apply \
  --json
```

After apply, restart the service, confirm data adoption, run short deep-health,
and verify public freeze still returns `rc=44`.

## Assisted rollback

Rollback is part of the pilot, not an emergency afterthought:

```sh
C18_PLAYER_RUNTIME_LAB_ROLLBACK=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \
python3 scripts/qa/c18_player_runtime_lab_rollback.py \
  --lab-only-rollback \
  --action rollback \
  --data-root /data \
  --allow-device-data-root \
  --quarantine-current \
  --expect-rolled-to <previous-version> \
  --output-dir <evidence-root>/rollback \
  --json
```

The rollback result must show the previous data release or image fallback
expected by the plan, service health after rollback, and public apply/rollback/
reconcile still frozen.

## P0 power-loss subset

For pilot, only the P0 subset is required:

- `after_current_symlink`;
- `rollback_after_current_to_previous`;
- `rollback_after_previous_removed`;
- `rollback_after_quarantine`;
- `rollback_after_state_success`.

The remaining 12 checkpoints stay H2/stable-production work. Extra H2 evidence
may be preserved, but the pilot gate does not claim 17/17 coverage.

Each P0 directory must pass:

```sh
python3 scripts/qa/c18_player_runtime_powerloss_evidence_gate.py \
  --run-dir <checkpoint-evidence-dir> \
  --json
```

For the final pilot gate, each counted P0 manifest must also bind to the target
package through `target_package_version` and `target_payload_sha256`.

## Evidence commit and final gate

Commit all sanitized evidence:

- target `player-runtime` homologation package manifest and payload;
- H1 decisive release-gate summary;
- pilot authorization JSON;
- board preflight JSON;
- the five P0 power-loss dirs;
- optional short deep-health/apply/rollback evidence referenced by the operator.

Then run the final pilot gate from a clean tree. A green result means only:
operator-assisted homologation pilot is ready for the allowlisted board(s) in
the approved window. It does not mean production, stable, public thaw, auto-pull,
24h soak, 17/17 power-loss, or signature/attestation readiness.
