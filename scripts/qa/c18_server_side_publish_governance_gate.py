#!/usr/bin/env python3
"""Default-deny C18 server-side publish governance gate.

This gate validates the evidence family consumed by H2 for publish/signature
governance. It does not publish, fetch, enable auto-pull, promote stable, or
thaw player-runtime.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.server_side_publish_governance.v1"
ALLOWED_CHANNELS = ("lab", "homologation", "stable")
EXPECTED_COMPONENT_SCOPE = ("totem-core", "player-runtime")
FORBIDDEN_COMPONENT_SCOPES = ("kiosky-player", "media-system", "field-data")
REQUIRED_SIGNED_OR_ATTESTED_ASSETS = (
    "manifest",
    "payload",
    "c18-ota-release-gate",
)
REQUIRED_ATTESTATION_COVERS = (
    "asset_sha256",
    "source_commit",
    "component",
    "channel",
    "created_at_utc",
)
REQUIRED_AUTO_PULL_ENABLE_REQUIRES = (
    "stable_promotion",
    "signature_or_attestation",
    "allowlist_match",
    "staged_rollout_active",
    "operator_rollback_owner",
)
REQUIRED_ROLLOUT_STAGES = (
    "operator_canary",
    "pilot_allowlist",
    "stable_canary",
    "stable_batch",
)
REQUIRED_AUDIT_EVENTS = (
    "release_created",
    "asset_attested",
    "channel_selected",
    "allowlist_evaluated",
    "rollout_stage_changed",
    "rollback_triggered",
    "stable_promoted",
)
SERVER_SIDE_EVIDENCE_FILENAME = "c18-server-side-publish-governance.json"
FIXTURE_MANIFEST_NAME = "dadooh-totem-core-server-fixture.manifest.json"
FIXTURE_PAYLOAD_NAME = "dadooh-totem-core-server-fixture.tar.gz"
FIXTURE_RELEASE_GATE_NAME = "c18-ota-release-gate.json"
FIXTURE_AUDIT_LOG_NAME = "audit-log.ndjson"
REQUIRED_TRUE_FIELDS = (
    "publish_gate_enforced",
    "release_assets_verified",
    "signature_or_attestation_present",
    "auto_pull_policy_defined",
    "auto_pull_default_disabled",
    "channel_governance_defined",
    "stable_requires_promotion",
    "allowlist_controls_defined",
    "staged_rollout_defined",
    "rollback_policy_defined",
    "audit_trail_defined",
    "public_player_runtime_thaw_requires_h2",
)
NON_CLAIMS = (
    "this_gate_does_not_publish_releases",
    "this_gate_does_not_enable_auto_pull",
    "this_gate_does_not_promote_stable",
    "this_gate_does_not_thaw_player_runtime",
)
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def is_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(HASH_RE.fullmatch(value))


def require_true(data: dict[str, Any], key: str, blockers: list[str], prefix: str) -> None:
    if data.get(key) is not True:
        blockers.append(f"{prefix}_{key}_missing_or_false")


def require_false(data: dict[str, Any], key: str, blockers: list[str], label: str) -> None:
    if data.get(key) is not False:
        blockers.append(label)


def require_exact_list(data: dict[str, Any],
                       key: str,
                       expected: tuple[str, ...],
                       blockers: list[str],
                       label: str) -> None:
    if data.get(key) != list(expected):
        blockers.append(label)


def validate_publish_gate(data: dict[str, Any], blockers: list[str]) -> None:
    gate = data.get("publish_gate") if isinstance(data.get("publish_gate"), dict) else {}
    if not gate:
        blockers.append("server_side_publish_gate_missing")
        return
    if gate.get("tool") != "scripts/qa/c18_ota_release_gate.py":
        blockers.append("server_side_publish_gate_tool")
    for key in ("required", "passed_required", "base_ref_required", "dirty_repo_denied", "package_assets_bound"):
        require_true(gate, key, blockers, "server_side_publish_gate")
    if gate.get("evidence_asset") != "c18-ota-release-gate":
        blockers.append("server_side_publish_gate_evidence_asset")


def validate_asset_attestations(data: dict[str, Any], blockers: list[str]) -> None:
    signed_assets = data.get("signed_or_attested_assets")
    if signed_assets != list(REQUIRED_SIGNED_OR_ATTESTED_ASSETS):
        blockers.append("server_side_signed_or_attested_assets_incomplete")
    attestations = data.get("asset_attestations")
    if not isinstance(attestations, list) or len(attestations) != len(REQUIRED_SIGNED_OR_ATTESTED_ASSETS):
        blockers.append("server_side_asset_attestations_incomplete")
        return
    seen: set[str] = set()
    for item in attestations:
        if not isinstance(item, dict):
            blockers.append("server_side_asset_attestation_not_object")
            continue
        asset = item.get("asset")
        if asset not in REQUIRED_SIGNED_OR_ATTESTED_ASSETS:
            blockers.append(f"server_side_asset_attestation_unexpected:{asset}")
            continue
        if asset in seen:
            blockers.append(f"server_side_asset_attestation_duplicate:{asset}")
        seen.add(asset)
        if not is_hash(item.get("sha256")):
            blockers.append(f"server_side_asset_attestation_sha256_invalid:{asset}")
        if item.get("attestation_type") not in ("signature", "attestation"):
            blockers.append(f"server_side_asset_attestation_type_invalid:{asset}")
        if not isinstance(item.get("signer"), str) or not item.get("signer"):
            blockers.append(f"server_side_asset_attestation_signer_missing:{asset}")
        signature_hash = item.get("signature_sha256") or item.get("attestation_sha256")
        if not is_hash(signature_hash):
            blockers.append(f"server_side_asset_attestation_proof_hash_invalid:{asset}")
        if item.get("covers") != list(REQUIRED_ATTESTATION_COVERS):
            blockers.append(f"server_side_asset_attestation_covers_not_exact:{asset}")
    missing = set(REQUIRED_SIGNED_OR_ATTESTED_ASSETS) - seen
    for asset in sorted(missing):
        blockers.append(f"server_side_asset_attestation_missing:{asset}")


def validate_channel_policy(data: dict[str, Any], blockers: list[str]) -> None:
    policy = data.get("channel_policy") if isinstance(data.get("channel_policy"), dict) else {}
    if not policy:
        blockers.append("server_side_channel_policy_missing")
        return
    require_exact_list(policy, "allowed_channels", ALLOWED_CHANNELS, blockers, "server_side_channel_policy_allowed_channels")
    require_false(policy, "channel_inheritance_allowed", blockers, "server_side_channel_policy_inheritance_allowed")
    for key in (
        "stable_requires_promotion",
        "homologation_requires_prerelease",
        "lab_is_internal_only",
        "unknown_channel_denied",
    ):
        require_true(policy, key, blockers, "server_side_channel_policy")


def validate_auto_pull_policy(data: dict[str, Any], blockers: list[str]) -> None:
    policy = data.get("auto_pull_policy") if isinstance(data.get("auto_pull_policy"), dict) else {}
    if not policy:
        blockers.append("server_side_auto_pull_policy_missing")
        return
    for key in ("defined", "default_disabled"):
        require_true(policy, key, blockers, "server_side_auto_pull_policy")
    require_false(policy, "enabled", blockers, "server_side_auto_pull_policy_enabled")
    require_false(policy, "default_enabled", blockers, "server_side_auto_pull_policy_default_enabled")
    require_exact_list(
        policy,
        "enable_requires",
        REQUIRED_AUTO_PULL_ENABLE_REQUIRES,
        blockers,
        "server_side_auto_pull_policy_enable_requires",
    )


def validate_component_policy(data: dict[str, Any], blockers: list[str]) -> None:
    policy = data.get("component_policy") if isinstance(data.get("component_policy"), dict) else {}
    if not policy:
        blockers.append("server_side_component_policy_missing")
        return
    require_exact_list(policy, "allowed_components", EXPECTED_COMPONENT_SCOPE, blockers, "server_side_component_policy_allowed")
    require_exact_list(policy, "forbidden_components", FORBIDDEN_COMPONENT_SCOPES, blockers, "server_side_component_policy_forbidden")
    require_true(policy, "exact_scope_required", blockers, "server_side_component_policy")
    require_false(policy, "component_inheritance_allowed", blockers, "server_side_component_policy_inheritance_allowed")


def validate_allowlist_policy(data: dict[str, Any], blockers: list[str]) -> None:
    policy = data.get("allowlist_policy") if isinstance(data.get("allowlist_policy"), dict) else {}
    if not policy:
        blockers.append("server_side_allowlist_policy_missing")
        return
    if policy.get("device_identity") != "sha256":
        blockers.append("server_side_allowlist_policy_device_identity")
    require_exact_list(policy, "required_for_channels", ("homologation", "stable"), blockers, "server_side_allowlist_policy_required_channels")
    for key in ("default_deny", "empty_allowlist_blocks", "operator_window_required"):
        require_true(policy, key, blockers, "server_side_allowlist_policy")
    require_false(policy, "raw_device_ids_persisted", blockers, "server_side_allowlist_policy_raw_device_ids_persisted")


def validate_staged_rollout_policy(data: dict[str, Any], blockers: list[str]) -> None:
    policy = data.get("staged_rollout_policy") if isinstance(data.get("staged_rollout_policy"), dict) else {}
    if not policy:
        blockers.append("server_side_staged_rollout_policy_missing")
        return
    require_exact_list(policy, "stages", REQUIRED_ROLLOUT_STAGES, blockers, "server_side_staged_rollout_policy_stages")
    for key in ("default_paused", "manual_advance_required", "rollback_on_health_failure", "audit_before_advance"):
        require_true(policy, key, blockers, "server_side_staged_rollout_policy")
    if policy.get("initial_percentage") != 0:
        blockers.append("server_side_staged_rollout_policy_initial_percentage")


def validate_rollback_policy(data: dict[str, Any], blockers: list[str]) -> None:
    policy = data.get("rollback_policy") if isinstance(data.get("rollback_policy"), dict) else {}
    if not policy:
        blockers.append("server_side_rollback_policy_missing")
        return
    for key in (
        "rollback_owner_required",
        "previous_release_preserved",
        "quarantine_supported",
        "image_fallback_documented",
        "rollback_audit_required",
    ):
        require_true(policy, key, blockers, "server_side_rollback_policy")


def validate_audit_trail(data: dict[str, Any], blockers: list[str]) -> None:
    audit = data.get("audit_trail") if isinstance(data.get("audit_trail"), dict) else {}
    if not audit:
        blockers.append("server_side_audit_trail_missing")
        return
    for key in ("append_only", "actor_recorded", "timestamp_recorded", "artifact_hashes_recorded", "secret_redaction_required"):
        require_true(audit, key, blockers, "server_side_audit_trail")
    require_exact_list(audit, "required_events", REQUIRED_AUDIT_EVENTS, blockers, "server_side_audit_trail_required_events")


def read_json(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"json_error:{type(exc).__name__}"]
    if not isinstance(data, dict):
        return {}, ["json_not_object"]
    return data, []


def sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value or value.startswith("/"):
        return None
    if ".." in Path(value).parts:
        return None
    return value


def release_asset_paths(data: dict[str, Any], release_dir: Path, blockers: list[str]) -> dict[str, Path]:
    assets = data.get("release_assets") if isinstance(data.get("release_assets"), dict) else {}
    if not assets:
        blockers.append("server_side_release_assets_missing")
        return {}
    expected_keys = {
        "manifest": "manifest",
        "payload": "payload",
        "c18-ota-release-gate": "release_gate",
        "audit-log": "audit_log",
    }
    paths: dict[str, Path] = {}
    for asset, field in expected_keys.items():
        relative = rel_path(assets.get(field))
        if relative is None:
            blockers.append(f"server_side_release_asset_path_invalid:{asset}")
            continue
        path = release_dir / relative
        if not path.is_file():
            blockers.append(f"server_side_release_asset_missing:{asset}")
            continue
        paths[asset] = path
    return paths


def attestation_by_asset(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in data.get("asset_attestations") if isinstance(data.get("asset_attestations"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("asset"), str):
            out[item["asset"]] = item
    return out


def validate_attestation_proof_file(item: dict[str, Any],
                                    *,
                                    release_dir: Path,
                                    manifest: dict[str, Any],
                                    blockers: list[str]) -> None:
    asset = item.get("asset")
    proof_rel = rel_path(item.get("proof_file"))
    if proof_rel is None:
        blockers.append(f"server_side_asset_attestation_proof_file_invalid:{asset}")
        return
    proof_path = release_dir / proof_rel
    if not proof_path.is_file():
        blockers.append(f"server_side_asset_attestation_proof_file_missing:{asset}")
        return
    proof_hash = sha256_file(proof_path)
    expected_hash = item.get("signature_sha256") or item.get("attestation_sha256")
    if proof_hash != expected_hash:
        blockers.append(f"server_side_asset_attestation_proof_hash_mismatch:{asset}")
    proof, errors = read_json(proof_path)
    if errors:
        blockers.append(f"server_side_asset_attestation_proof_json:{asset}")
        return
    if proof.get("schema") != "dadooh.c18.asset_attestation.v1":
        blockers.append(f"server_side_asset_attestation_proof_schema:{asset}")
    if proof.get("subject_asset") != asset:
        blockers.append(f"server_side_asset_attestation_proof_subject_asset:{asset}")
    if proof.get("subject_sha256") != item.get("sha256"):
        blockers.append(f"server_side_asset_attestation_proof_subject_sha256:{asset}")
    for key in ("source_commit", "component", "channel", "created_at_utc"):
        if proof.get(key) != manifest.get(key):
            blockers.append(f"server_side_asset_attestation_proof_{key}:{asset}")
    if proof.get("covers") != list(REQUIRED_ATTESTATION_COVERS):
        blockers.append(f"server_side_asset_attestation_proof_covers:{asset}")


def validate_release_gate_artifact(gate_path: Path,
                                   *,
                                   manifest_path: Path,
                                   payload_path: Path,
                                   manifest: dict[str, Any],
                                   payload_sha256: str,
                                   blockers: list[str]) -> None:
    gate, errors = read_json(gate_path)
    if errors:
        blockers.append("server_side_release_gate_json")
        return
    if gate.get("schema") != "dadooh.c18.ota.release_gate.v1":
        blockers.append("server_side_release_gate_schema")
    if gate.get("passed") is not True:
        blockers.append("server_side_release_gate_not_passed")
    package = gate.get("package") if isinstance(gate.get("package"), dict) else {}
    if not package:
        blockers.append("server_side_release_gate_package_missing")
        return
    if Path(str(package.get("manifest", ""))).name != manifest_path.name:
        blockers.append("server_side_release_gate_manifest_mismatch")
    if Path(str(package.get("payload", ""))).name != payload_path.name:
        blockers.append("server_side_release_gate_payload_mismatch")
    if package.get("payload_sha256") != payload_sha256:
        blockers.append("server_side_release_gate_payload_sha256_mismatch")
    if package.get("source_commit") != manifest.get("source_commit"):
        blockers.append("server_side_release_gate_source_commit_mismatch")
    if package.get("component") != manifest.get("component"):
        blockers.append("server_side_release_gate_component_mismatch")
    if package.get("channel") != manifest.get("channel"):
        blockers.append("server_side_release_gate_channel_mismatch")


def validate_audit_log(log_path: Path, data: dict[str, Any], blockers: list[str]) -> None:
    seen: set[str] = set()
    expected_hashes = {
        item.get("asset"): item.get("sha256")
        for item in data.get("asset_attestations", [])
        if isinstance(item, dict)
    }
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        blockers.append("server_side_audit_log_read_error")
        return
    if not lines:
        blockers.append("server_side_audit_log_empty")
        return
    for index, line in enumerate(lines, 1):
        try:
            item = json.loads(line)
        except Exception:
            blockers.append(f"server_side_audit_log_json:{index}")
            continue
        if not isinstance(item, dict):
            blockers.append(f"server_side_audit_log_not_object:{index}")
            continue
        event = item.get("event")
        if isinstance(event, str):
            seen.add(event)
            if event not in REQUIRED_AUDIT_EVENTS:
                blockers.append(f"server_side_audit_log_event_unexpected:{event}")
        else:
            blockers.append(f"server_side_audit_log_event_missing_value:{index}")
        if not isinstance(item.get("actor"), str) or not item.get("actor"):
            blockers.append(f"server_side_audit_log_actor:{index}")
        if not isinstance(item.get("at_utc"), str) or not item.get("at_utc").endswith("Z"):
            blockers.append(f"server_side_audit_log_at_utc:{index}")
        hashes = item.get("artifact_hashes") if isinstance(item.get("artifact_hashes"), dict) else {}
        for asset in REQUIRED_SIGNED_OR_ATTESTED_ASSETS:
            if not is_hash(hashes.get(asset)):
                blockers.append(f"server_side_audit_log_hash_missing:{event}:{asset}")
            elif hashes.get(asset) != expected_hashes.get(asset):
                blockers.append(f"server_side_audit_log_hash_mismatch:{event}:{asset}")
    for event in REQUIRED_AUDIT_EVENTS:
        if event not in seen:
            blockers.append(f"server_side_audit_log_event_missing:{event}")


def validate_release_artifacts(data: dict[str, Any],
                               *,
                               evidence_path: str | None,
                               release_dir: Path | None,
                               blockers: list[str]) -> None:
    if release_dir is None:
        blockers.append("server_side_release_dir_missing")
        return
    paths = release_asset_paths(data, release_dir, blockers)
    required = {"manifest", "payload", "c18-ota-release-gate", "audit-log"}
    if set(paths) != required:
        return
    manifest, errors = read_json(paths["manifest"])
    if errors:
        blockers.append("server_side_manifest_json")
        return
    if manifest.get("schema") != "dadooh.totem.update.v1":
        blockers.append("server_side_manifest_schema")
    if manifest.get("component") not in EXPECTED_COMPONENT_SCOPE:
        blockers.append("server_side_manifest_component_scope")
    if manifest.get("channel") not in ALLOWED_CHANNELS:
        blockers.append("server_side_manifest_channel")
    payload_sha256 = sha256_file(paths["payload"])
    if manifest.get("payload") != paths["payload"].name:
        blockers.append("server_side_manifest_payload_name_mismatch")
    if manifest.get("payload_sha256") != payload_sha256:
        blockers.append("server_side_manifest_payload_sha256_mismatch")
    asset_hashes = {
        "manifest": sha256_file(paths["manifest"]),
        "payload": payload_sha256,
        "c18-ota-release-gate": sha256_file(paths["c18-ota-release-gate"]),
    }
    attestations = attestation_by_asset(data)
    for asset, expected_hash in asset_hashes.items():
        item = attestations.get(asset)
        if item is None:
            blockers.append(f"server_side_asset_attestation_missing:{asset}")
            continue
        if item.get("sha256") != expected_hash:
            blockers.append(f"server_side_asset_attestation_sha256_mismatch:{asset}")
        validate_attestation_proof_file(item, release_dir=release_dir, manifest=manifest, blockers=blockers)
    validate_release_gate_artifact(
        paths["c18-ota-release-gate"],
        manifest_path=paths["manifest"],
        payload_path=paths["payload"],
        manifest=manifest,
        payload_sha256=payload_sha256,
        blockers=blockers,
    )
    validate_audit_log(paths["audit-log"], data, blockers)


def validate_data(data: dict[str, Any],
                  *,
                  evidence_path: str | None = None,
                  release_dir: Path | None = None) -> dict[str, Any]:
    blockers: list[str] = []
    if data.get("schema") != SCHEMA:
        blockers.append("server_side_schema")
    for key in REQUIRED_TRUE_FIELDS:
        if data.get(key) is not True:
            blockers.append(f"server_side_{key}_missing_or_false")
    if data.get("auto_pull_enabled") is not False:
        blockers.append("server_side_auto_pull_enabled")
    channels = data.get("channels")
    if channels != list(ALLOWED_CHANNELS):
        blockers.append("server_side_channels_not_exact")
    if data.get("channel_inheritance_allowed") is True:
        blockers.append("server_side_channel_inheritance_allowed")
    component_scope = data.get("component_scope")
    if component_scope != list(EXPECTED_COMPONENT_SCOPE):
        blockers.append("server_side_component_scope_not_exact")
    elif any(scope in component_scope for scope in FORBIDDEN_COMPONENT_SCOPES):
        blockers.append("server_side_forbidden_component_in_scope")
    forbidden_scopes = data.get("forbidden_component_scopes")
    if forbidden_scopes != list(FORBIDDEN_COMPONENT_SCOPES):
        blockers.append("server_side_forbidden_component_scopes_not_exact")
    validate_publish_gate(data, blockers)
    validate_asset_attestations(data, blockers)
    validate_channel_policy(data, blockers)
    validate_auto_pull_policy(data, blockers)
    validate_component_policy(data, blockers)
    validate_allowlist_policy(data, blockers)
    validate_staged_rollout_policy(data, blockers)
    validate_rollback_policy(data, blockers)
    validate_audit_trail(data, blockers)
    validate_release_artifacts(data, evidence_path=evidence_path, release_dir=release_dir, blockers=blockers)
    return {
        "schema": "dadooh.c18.server_side_publish_governance_gate.v1",
        "passed": not blockers,
        "result_claim": "server_side_publish_governance_ready" if not blockers else "server_side_publish_governance_blocked",
        "evidence_path": evidence_path,
        "blockers": blockers,
        "non_claims": list(NON_CLAIMS),
    }


def evaluate(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "schema": "dadooh.c18.server_side_publish_governance_gate.v1",
            "passed": False,
            "result_claim": "server_side_publish_governance_blocked",
            "evidence_path": None,
            "blockers": ["missing_server_side_publish_governance"],
            "non_claims": list(NON_CLAIMS),
        }
    data, errors = read_json(path)
    if errors:
        return {
            "schema": "dadooh.c18.server_side_publish_governance_gate.v1",
            "passed": False,
            "result_claim": "server_side_publish_governance_blocked",
            "evidence_path": str(path),
            "blockers": errors,
            "non_claims": list(NON_CLAIMS),
        }
    return validate_data(data, evidence_path=str(path), release_dir=path.parent)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def valid_fixture(*,
                  asset_hashes: dict[str, str] | None = None,
                  proof_hashes: dict[str, str] | None = None,
                  proof_files: dict[str, str] | None = None) -> dict[str, Any]:
    resolved_asset_hashes = asset_hashes or {
        "manifest": "a" * 64,
        "payload": "b" * 64,
        "c18-ota-release-gate": "c" * 64,
    }
    resolved_proof_hashes = proof_hashes or {
        asset: str(index + 1) * 64
        for index, asset in enumerate(REQUIRED_SIGNED_OR_ATTESTED_ASSETS)
    }
    resolved_proof_files = proof_files or {
        asset: f"attestations/{asset}.attestation.json"
        for asset in REQUIRED_SIGNED_OR_ATTESTED_ASSETS
    }
    return {
        "schema": SCHEMA,
        "publish_gate_enforced": True,
        "release_assets_verified": True,
        "signature_or_attestation_present": True,
        "auto_pull_policy_defined": True,
        "auto_pull_default_disabled": True,
        "auto_pull_enabled": False,
        "channel_governance_defined": True,
        "channels": list(ALLOWED_CHANNELS),
        "channel_inheritance_allowed": False,
        "stable_requires_promotion": True,
        "allowlist_controls_defined": True,
        "staged_rollout_defined": True,
        "rollback_policy_defined": True,
        "audit_trail_defined": True,
        "public_player_runtime_thaw_requires_h2": True,
        "component_scope": list(EXPECTED_COMPONENT_SCOPE),
        "forbidden_component_scopes": list(FORBIDDEN_COMPONENT_SCOPES),
        "signed_or_attested_assets": list(REQUIRED_SIGNED_OR_ATTESTED_ASSETS),
        "release_assets": {
            "manifest": FIXTURE_MANIFEST_NAME,
            "payload": FIXTURE_PAYLOAD_NAME,
            "release_gate": FIXTURE_RELEASE_GATE_NAME,
            "audit_log": FIXTURE_AUDIT_LOG_NAME,
        },
        "publish_gate": {
            "tool": "scripts/qa/c18_ota_release_gate.py",
            "required": True,
            "passed_required": True,
            "base_ref_required": True,
            "dirty_repo_denied": True,
            "package_assets_bound": True,
            "evidence_asset": "c18-ota-release-gate",
        },
        "asset_attestations": [
            {
                "asset": asset,
                "sha256": sha256,
                "attestation_type": "attestation",
                "signer": "c18-release-governance",
                "attestation_sha256": resolved_proof_hashes[asset],
                "proof_file": resolved_proof_files[asset],
                "covers": list(REQUIRED_ATTESTATION_COVERS),
            }
            for asset, sha256 in resolved_asset_hashes.items()
        ],
        "channel_policy": {
            "allowed_channels": list(ALLOWED_CHANNELS),
            "channel_inheritance_allowed": False,
            "stable_requires_promotion": True,
            "homologation_requires_prerelease": True,
            "lab_is_internal_only": True,
            "unknown_channel_denied": True,
        },
        "auto_pull_policy": {
            "defined": True,
            "enabled": False,
            "default_disabled": True,
            "default_enabled": False,
            "enable_requires": list(REQUIRED_AUTO_PULL_ENABLE_REQUIRES),
        },
        "component_policy": {
            "allowed_components": list(EXPECTED_COMPONENT_SCOPE),
            "forbidden_components": list(FORBIDDEN_COMPONENT_SCOPES),
            "exact_scope_required": True,
            "component_inheritance_allowed": False,
        },
        "allowlist_policy": {
            "device_identity": "sha256",
            "required_for_channels": ["homologation", "stable"],
            "default_deny": True,
            "empty_allowlist_blocks": True,
            "operator_window_required": True,
            "raw_device_ids_persisted": False,
        },
        "staged_rollout_policy": {
            "stages": list(REQUIRED_ROLLOUT_STAGES),
            "default_paused": True,
            "manual_advance_required": True,
            "rollback_on_health_failure": True,
            "audit_before_advance": True,
            "initial_percentage": 0,
        },
        "rollback_policy": {
            "rollback_owner_required": True,
            "previous_release_preserved": True,
            "quarantine_supported": True,
            "image_fallback_documented": True,
            "rollback_audit_required": True,
        },
        "audit_trail": {
            "append_only": True,
            "actor_recorded": True,
            "timestamp_recorded": True,
            "artifact_hashes_recorded": True,
            "secret_redaction_required": True,
            "required_events": list(REQUIRED_AUDIT_EVENTS),
        },
    }


def write_fixture_release(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    payload_path = root / FIXTURE_PAYLOAD_NAME
    payload_path.write_bytes(b"C18 server-side governance fixture payload\n")
    payload_sha256 = sha256_file(payload_path)
    manifest = {
        "schema": "dadooh.totem.update.v1",
        "component": "totem-core",
        "version": "server-fixture",
        "channel": "homologation",
        "payload": payload_path.name,
        "payload_sha256": payload_sha256,
        "source_commit": "a" * 40,
        "created_at_utc": "2026-06-12T00:00:00Z",
    }
    manifest_path = root / FIXTURE_MANIFEST_NAME
    write_json(manifest_path, manifest)
    release_gate = {
        "schema": "dadooh.c18.ota.release_gate.v1",
        "passed": True,
        "package": {
            "manifest": manifest_path.name,
            "payload": payload_path.name,
            "payload_sha256": payload_sha256,
            "source_commit": manifest["source_commit"],
            "component": manifest["component"],
            "channel": manifest["channel"],
        },
    }
    release_gate_path = root / FIXTURE_RELEASE_GATE_NAME
    write_json(release_gate_path, release_gate)
    asset_hashes = {
        "manifest": sha256_file(manifest_path),
        "payload": payload_sha256,
        "c18-ota-release-gate": sha256_file(release_gate_path),
    }
    proof_files = {
        asset: f"attestations/{asset}.attestation.json"
        for asset in REQUIRED_SIGNED_OR_ATTESTED_ASSETS
    }
    proof_hashes: dict[str, str] = {}
    for asset in REQUIRED_SIGNED_OR_ATTESTED_ASSETS:
        proof_path = root / proof_files[asset]
        write_json(proof_path, {
            "schema": "dadooh.c18.asset_attestation.v1",
            "subject_asset": asset,
            "subject_sha256": asset_hashes[asset],
            "source_commit": manifest["source_commit"],
            "component": manifest["component"],
            "channel": manifest["channel"],
            "created_at_utc": manifest["created_at_utc"],
            "covers": list(REQUIRED_ATTESTATION_COVERS),
            "signer": "c18-release-governance",
        })
        proof_hashes[asset] = sha256_file(proof_path)
    data = valid_fixture(
        asset_hashes=asset_hashes,
        proof_hashes=proof_hashes,
        proof_files=proof_files,
    )
    audit_path = root / FIXTURE_AUDIT_LOG_NAME
    audit_lines = [
        json.dumps({
            "event": event,
            "actor": "c18-release-governance",
            "at_utc": "2026-06-12T00:00:00Z",
            "artifact_hashes": asset_hashes,
        }, sort_keys=True)
        for event in REQUIRED_AUDIT_EVENTS
    ]
    audit_path.write_text("\n".join(audit_lines) + "\n", encoding="utf-8")
    evidence_path = root / SERVER_SIDE_EVIDENCE_FILENAME
    write_json(evidence_path, data)
    return evidence_path


class ServerSidePublishGovernanceGateSelfTest(unittest.TestCase):
    def test_complete_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate(write_fixture_release(Path(tmp)))
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
        self.assertIn("this_gate_does_not_enable_auto_pull", result["non_claims"])

    def test_missing_evidence_denies(self) -> None:
        result = evaluate(None)
        self.assertFalse(result["passed"])
        self.assertIn("missing_server_side_publish_governance", result["blockers"])

    def test_signature_or_attestation_required(self) -> None:
        data = valid_fixture()
        data["signature_or_attestation_present"] = False
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_signature_or_attestation_present_missing_or_false", result["blockers"])

    def test_boolean_only_evidence_denies(self) -> None:
        data = {
            key: True for key in REQUIRED_TRUE_FIELDS
        }
        data.update({
            "schema": SCHEMA,
            "auto_pull_enabled": False,
            "channels": list(ALLOWED_CHANNELS),
            "channel_inheritance_allowed": False,
            "component_scope": list(EXPECTED_COMPONENT_SCOPE),
            "forbidden_component_scopes": list(FORBIDDEN_COMPONENT_SCOPES),
            "signed_or_attested_assets": list(REQUIRED_SIGNED_OR_ATTESTED_ASSETS),
        })
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_publish_gate_missing", result["blockers"])
        self.assertIn("server_side_asset_attestations_incomplete", result["blockers"])
        self.assertIn("server_side_allowlist_policy_missing", result["blockers"])

    def test_asset_attestations_are_structural(self) -> None:
        data = valid_fixture()
        data["asset_attestations"][0]["sha256"] = "not-a-hash"
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_asset_attestation_sha256_invalid:manifest", result["blockers"])

        data = valid_fixture()
        data["asset_attestations"][1]["covers"] = ["asset_sha256"]
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_asset_attestation_covers_not_exact:payload", result["blockers"])

    def test_auto_pull_must_remain_disabled_by_default(self) -> None:
        data = valid_fixture()
        data["auto_pull_enabled"] = True
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_auto_pull_enabled", result["blockers"])

        data = valid_fixture()
        del data["auto_pull_enabled"]
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_auto_pull_enabled", result["blockers"])

        data = valid_fixture()
        data["auto_pull_policy"]["enabled"] = True
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_auto_pull_policy_enabled", result["blockers"])

    def test_channel_inheritance_denies(self) -> None:
        data = valid_fixture()
        data["channel_inheritance_allowed"] = True
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_channel_inheritance_allowed", result["blockers"])

        data = valid_fixture()
        data["channel_policy"]["channel_inheritance_allowed"] = True
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_channel_policy_inheritance_allowed", result["blockers"])

    def test_channels_and_signed_assets_are_required_exactly(self) -> None:
        data = valid_fixture()
        del data["channels"]
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_channels_not_exact", result["blockers"])

        data = valid_fixture()
        del data["signed_or_attested_assets"]
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_signed_or_attested_assets_incomplete", result["blockers"])

    def test_component_scope_must_be_exact_and_forbid_legacy_scopes(self) -> None:
        data = valid_fixture()
        data["component_scope"] = ["totem-core", "player-runtime", "kiosky-player"]
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_component_scope_not_exact", result["blockers"])

        data = valid_fixture()
        data["forbidden_component_scopes"] = ["kiosky-player"]
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_forbidden_component_scopes_not_exact", result["blockers"])

    def test_publish_allowlist_rollout_and_audit_are_enforced(self) -> None:
        data = valid_fixture()
        data["publish_gate"]["base_ref_required"] = False
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_publish_gate_base_ref_required_missing_or_false", result["blockers"])

        data = valid_fixture()
        data["allowlist_policy"]["raw_device_ids_persisted"] = True
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_allowlist_policy_raw_device_ids_persisted", result["blockers"])

        data = valid_fixture()
        data["staged_rollout_policy"]["stages"] = ["pilot_allowlist"]
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_staged_rollout_policy_stages", result["blockers"])

        data = valid_fixture()
        data["audit_trail"]["required_events"] = ["release_created"]
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_audit_trail_required_events", result["blockers"])

    def test_file_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_fixture_release(Path(tmp))
            result = evaluate(path)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_tampered_payload_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_fixture_release(Path(tmp))
            (Path(tmp) / FIXTURE_PAYLOAD_NAME).write_bytes(b"tampered\n")
            result = evaluate(path)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_manifest_payload_sha256_mismatch", result["blockers"])
        self.assertIn("server_side_asset_attestation_sha256_mismatch:payload", result["blockers"])

    def test_tampered_attestation_proof_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_fixture_release(Path(tmp))
            proof_path = Path(tmp) / "attestations" / "payload.attestation.json"
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            proof["subject_sha256"] = "0" * 64
            write_json(proof_path, proof)
            result = evaluate(path)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_asset_attestation_proof_hash_mismatch:payload", result["blockers"])
        self.assertIn("server_side_asset_attestation_proof_subject_sha256:payload", result["blockers"])

    def test_tampered_release_gate_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_fixture_release(Path(tmp))
            gate_path = Path(tmp) / FIXTURE_RELEASE_GATE_NAME
            gate = json.loads(gate_path.read_text(encoding="utf-8"))
            gate["package"]["payload_sha256"] = "0" * 64
            write_json(gate_path, gate)
            result = evaluate(path)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_asset_attestation_sha256_mismatch:c18-ota-release-gate", result["blockers"])
        self.assertIn("server_side_release_gate_payload_sha256_mismatch", result["blockers"])

    def test_audit_log_must_cover_required_events_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_fixture_release(Path(tmp))
            audit_path = Path(tmp) / FIXTURE_AUDIT_LOG_NAME
            audit_path.write_text(
                json.dumps({
                    "event": "release_created",
                    "actor": "c18-release-governance",
                    "at_utc": "2026-06-12T00:00:00Z",
                    "artifact_hashes": {
                        "manifest": "0" * 64,
                        "payload": "0" * 64,
                        "c18-ota-release-gate": "0" * 64,
                    },
                }, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = evaluate(path)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_audit_log_event_missing:stable_promoted", result["blockers"])
        self.assertIn("server_side_audit_log_hash_mismatch:release_created:payload", result["blockers"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate C18 server-side publish governance evidence.")
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ServerSidePublishGovernanceGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = evaluate(args.evidence)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif not result["passed"]:
        print("\n".join(result["blockers"]), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
