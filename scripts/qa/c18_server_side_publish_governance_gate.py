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
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from c18_player_runtime_release_gate import (
    SNAPSHOT_KIOSK,
    validate_release as validate_player_runtime_release,
    write_manifest as write_player_runtime_manifest,
    write_payload as write_player_runtime_payload,
)


SCHEMA = "dadooh.c18.server_side_publish_governance.v1"
ALLOWED_CHANNELS = ("lab", "homologation", "stable")
EXPECTED_COMPONENT_SCOPE = ("totem-core", "player-runtime")
FORBIDDEN_COMPONENT_SCOPES = ("kiosky-player", "media-system", "field-data")
RELEASE_GATE_SCHEMA_BY_COMPONENT = {
    "totem-core": "dadooh.c18.ota.release_gate.v1",
    "player-runtime": "dadooh.c18.player_runtime.release_gate.v1",
}
RELEASE_GATE_TOOL_BY_COMPONENT = {
    "totem-core": "scripts/qa/c18_ota_release_gate.py",
    "player-runtime": "scripts/qa/c18_player_runtime_release_gate.py",
}
REQUIRED_SIGNED_OR_ATTESTED_ASSETS = (
    "manifest",
    "payload",
    "c18-ota-release-gate",
    "audit-log",
)
REQUIRED_AUDIT_HASHED_ASSETS = (
    "manifest",
    "payload",
    "c18-ota-release-gate",
)
REQUIRED_ATTESTATION_COVERS = (
    "asset_sha256",
    "release_set_sha256",
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
    "stable_promotion_evaluated",
)
LEGACY_AUDIT_EVENT_ALIASES = {
    "stable_promoted": "stable_promotion_evaluated",
}
SERVER_SIDE_EVIDENCE_FILENAME = "c18-server-side-publish-governance.json"
FIXTURE_MANIFEST_NAME = "dadooh-totem-core-server-fixture.manifest.json"
FIXTURE_PAYLOAD_NAME = "dadooh-totem-core-server-fixture.tar.gz"
FIXTURE_RELEASE_GATE_NAME = "c18-ota-release-gate.json"
PLAYER_RUNTIME_FIXTURE_RELEASE_GATE_NAME = "c18-player-runtime-release-gate.json"
FIXTURE_AUDIT_LOG_NAME = "audit-log.ndjson"
SIGNED_FIXTURE_MANIFEST_NAME = "dadooh-totem-core-signed-release.manifest.json"
SIGNED_FIXTURE_PAYLOAD_NAME = "dadooh-totem-core-signed-release.tar.gz"
SIGNATURE_SCHEMA = "dadooh.c18.asset_signature.v1"
ATTESTATION_SCHEMA = "dadooh.c18.asset_attestation.v1"
TRUST_ANCHOR_SCHEMA = "dadooh.c18.server_side_trust_anchor.v1"
SIGNATURE_ALGORITHM = "openssl-dgst-sha256-rsa-pkcs1-v1_5"
TRUST_ANCHOR_PURPOSE = "c18_server_side_release_signing"
TRUST_ANCHOR_PUBLIC_KEY_ALGORITHM = "rsa"
TRUST_ANCHOR_ALLOWED_FIELDS = (
    "schema",
    "purpose",
    "trusted_key_spki_sha256",
    "public_key_algorithm",
    "signature_algorithm",
    "scope",
    "selected_by",
    "key_owner",
    "selected_at_utc",
    "private_key_material_present",
    "non_claims",
)
TRUST_ANCHOR_SCOPE_FIELDS = ("components", "channels")
REQUIRED_TRUST_ANCHOR_NON_CLAIMS = (
    "this_evidence_does_not_assert_pki_chain",
    "this_evidence_does_not_publish_releases",
    "this_evidence_does_not_enable_auto_pull",
    "this_evidence_does_not_promote_stable",
    "this_evidence_does_not_thaw_player_runtime",
)
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
ALLOWED_TOP_LEVEL_FIELDS = (
    "schema",
    "test_fixture",
    "publish_gate_enforced",
    "release_assets_verified",
    "signature_or_attestation_present",
    "auto_pull_policy_defined",
    "auto_pull_default_disabled",
    "auto_pull_enabled",
    "channel_governance_defined",
    "channels",
    "channel_inheritance_allowed",
    "stable_requires_promotion",
    "allowlist_controls_defined",
    "staged_rollout_defined",
    "rollback_policy_defined",
    "audit_trail_defined",
    "public_player_runtime_thaw_requires_h2",
    "component_scope",
    "forbidden_component_scopes",
    "signed_or_attested_assets",
    "release_assets",
    "publish_gate",
    "asset_attestations",
    "channel_policy",
    "auto_pull_policy",
    "component_policy",
    "allowlist_policy",
    "staged_rollout_policy",
    "rollback_policy",
    "audit_trail",
)
AUDIT_FORBIDDEN_POSITIVE_CLAIMS = (
    "promotion_performed",
    "auto_pull_enabled",
    "public_player_runtime_thaw",
)
ATTESTATION_PROOF_ALLOWED_FIELDS = (
    "schema",
    "subject_asset",
    "subject_sha256",
    "release_set_sha256",
    "source_commit",
    "component",
    "channel",
    "created_at_utc",
    "covers",
    "signer",
)
SIGNATURE_PROOF_ALLOWED_FIELDS = (
    "schema",
    "subject_asset",
    "subject_sha256",
    "release_set_sha256",
    "source_commit",
    "component",
    "channel",
    "created_at_utc",
    "covers",
    "signature_algorithm",
    "trusted_key_sha256",
    "signature_file",
)
ALLOWED_SECRET_FIELD_PATHS = frozenset({
    "$.audit_trail.secret_redaction_required",
})
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I)
SECRET_FIELD_RE = re.compile(r"(secret|token|private_key)", re.I)


def is_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(HASH_RE.fullmatch(value))


def is_git_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(GIT_SHA_RE.fullmatch(value))


def safe_id(value: Any) -> bool:
    return isinstance(value, str) and bool(SAFE_ID_RE.fullmatch(value))


def secret_json_paths(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, str):
        return [path] if PRIVATE_KEY_RE.search(value) else []
    if isinstance(value, dict):
        hits: list[str] = []
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if SECRET_FIELD_RE.search(str(key)) and child_path not in ALLOWED_SECRET_FIELD_PATHS:
                hits.append(child_path)
            hits.extend(secret_json_paths(child, child_path))
        return hits
    if isinstance(value, list):
        hits = []
        for index, child in enumerate(value):
            hits.extend(secret_json_paths(child, f"{path}[{index}]"))
        return hits
    return []


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


def canonical_audit_event(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return LEGACY_AUDIT_EVENT_ALIASES.get(value, value)


def audit_events_match(raw_events: Any) -> bool:
    if not isinstance(raw_events, list) or not all(isinstance(event, str) for event in raw_events):
        return False
    return [canonical_audit_event(event) for event in raw_events] == list(REQUIRED_AUDIT_EVENTS)


def validate_publish_gate(data: dict[str, Any], blockers: list[str], *, expected_component: str | None = None) -> None:
    gate = data.get("publish_gate") if isinstance(data.get("publish_gate"), dict) else {}
    if not gate:
        blockers.append("server_side_publish_gate_missing")
        return
    expected_tool = RELEASE_GATE_TOOL_BY_COMPONENT.get(expected_component) if expected_component else None
    if expected_tool is not None:
        if gate.get("tool") != expected_tool:
            blockers.append("server_side_publish_gate_tool")
    elif gate.get("tool") != "scripts/qa/c18_ota_release_gate.py":
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
        if item.get("attestation_type") == "signature" and not is_hash(item.get("proof_sha256")):
            blockers.append(f"server_side_asset_signature_proof_hash_invalid:{asset}")
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
    if not audit_events_match(audit.get("required_events")):
        blockers.append("server_side_audit_trail_required_events")


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


def sha256_bytes(raw: bytes) -> str:
    import hashlib

    return hashlib.sha256(raw).hexdigest()


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def release_set_sha256(asset_hashes: dict[str, str]) -> str:
    return sha256_bytes(canonical_json_bytes({
        "assets": [
            {"asset": asset, "sha256": asset_hashes[asset]}
            for asset in REQUIRED_SIGNED_OR_ATTESTED_ASSETS
        ],
    }))


def rel_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value or value.startswith("/"):
        return None
    if ".." in Path(value).parts:
        return None
    return value


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def has_symlink_component(path: Path, root: Path) -> bool:
    current = root
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    for part in parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def has_any_symlink_component(path: Path) -> bool:
    candidate = path if path.is_absolute() else Path.cwd() / path
    current = Path(candidate.anchor) if candidate.anchor else Path()
    for part in candidate.parts:
        if part == candidate.anchor or not part:
            continue
        current = current / part
        if current.is_symlink():
            return True
    return False


def resolve_release_file(raw: Any,
                         *,
                         release_dir: Path,
                         blockers: list[str],
                         asset: str,
                         path_invalid_blocker: str,
                         missing_blocker: str,
                         symlink_blocker: str,
                         outside_blocker: str) -> Path | None:
    relative = rel_path(raw)
    if relative is None:
        blockers.append(f"{path_invalid_blocker}:{asset}")
        return None
    try:
        release_root = release_dir.resolve(strict=True)
    except OSError:
        blockers.append("server_side_release_dir_missing")
        return None
    path = release_dir / relative
    if has_symlink_component(path, release_dir):
        blockers.append(f"{symlink_blocker}:{asset}")
        return None
    if not path.is_file():
        blockers.append(f"{missing_blocker}:{asset}")
        return None
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        blockers.append(f"{missing_blocker}:{asset}")
        return None
    if not is_relative_to(resolved, release_root):
        blockers.append(f"{outside_blocker}:{asset}")
        return None
    return path


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
        path = resolve_release_file(
            assets.get(field),
            release_dir=release_dir,
            blockers=blockers,
            asset=asset,
            path_invalid_blocker="server_side_release_asset_path_invalid",
            missing_blocker="server_side_release_asset_missing",
            symlink_blocker="server_side_release_asset_symlink",
            outside_blocker="server_side_release_asset_outside_release_dir",
        )
        if path is None:
            continue
        paths[asset] = path
    return paths


def attestation_by_asset(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in data.get("asset_attestations") if isinstance(data.get("asset_attestations"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("asset"), str):
            out[item["asset"]] = item
    return out


def public_key_spki_sha256(path: Path) -> str | None:
    if shutil.which("openssl") is None:
        return None
    proc = subprocess.run(
        ["openssl", "pkey", "-pubin", "-in", str(path), "-pubout", "-outform", "DER"],
        text=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        return None
    return sha256_bytes(proc.stdout)


def trusted_key_map(paths: list[Path] | None,
                    *,
                    release_dir: Path | None = None,
                    blockers: list[str] | None = None) -> dict[str, Path]:
    out: dict[str, Path] = {}
    release_root = release_dir.resolve(strict=True) if release_dir is not None and release_dir.exists() else None
    for path in paths or []:
        if has_any_symlink_component(path):
            if blockers is not None:
                blockers.append(f"server_side_trusted_key_symlink:{path}")
            continue
        if not path.is_file():
            if blockers is not None:
                blockers.append(f"server_side_trusted_key_missing:{path}")
            continue
        resolved = path.resolve(strict=True)
        if release_root is not None and is_relative_to(resolved, release_root):
            if blockers is not None:
                blockers.append(f"server_side_trusted_key_inside_release_dir:{path}")
            continue
        key_hash = public_key_spki_sha256(path)
        if key_hash is None:
            if blockers is not None:
                blockers.append(f"server_side_trusted_key_invalid:{path}")
            continue
        out[key_hash] = path
    return out


def validate_trust_anchor_evidence(path: Path | None,
                                   *,
                                   release_dir: Path | None,
                                   trusted_keys: dict[str, Path],
                                   blockers: list[str]) -> dict[str, Any] | None:
    if path is None:
        blockers.append("server_side_trust_anchor_evidence_missing")
        return None
    if has_any_symlink_component(path):
        blockers.append(f"server_side_trust_anchor_evidence_symlink:{path}")
        return None
    if not path.is_file():
        blockers.append(f"server_side_trust_anchor_evidence_missing:{path}")
        return None
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        blockers.append(f"server_side_trust_anchor_evidence_missing:{path}")
        return None
    if release_dir is not None and release_dir.exists():
        release_root = release_dir.resolve(strict=True)
        if is_relative_to(resolved, release_root):
            blockers.append(f"server_side_trust_anchor_evidence_inside_release_dir:{path}")
            return None
    raw = path.read_text(encoding="utf-8", errors="replace")
    if PRIVATE_KEY_RE.search(raw):
        blockers.append("server_side_trust_anchor_private_key_material_present")
    data, errors = read_json(path)
    if errors:
        blockers.extend(f"server_side_trust_anchor_{error}" for error in errors)
        return None
    if data.get("schema") != TRUST_ANCHOR_SCHEMA:
        blockers.append("server_side_trust_anchor_schema")
    if data.get("purpose") != TRUST_ANCHOR_PURPOSE:
        blockers.append("server_side_trust_anchor_purpose")
    if sorted(data) != sorted(TRUST_ANCHOR_ALLOWED_FIELDS):
        blockers.append("server_side_trust_anchor_unexpected_fields")
    key_sha = data.get("trusted_key_spki_sha256")
    if not is_hash(key_sha):
        blockers.append("server_side_trust_anchor_key_spki_sha256_missing_or_invalid")
    elif key_sha not in trusted_keys:
        blockers.append("server_side_trust_anchor_key_not_trusted")
    if data.get("public_key_algorithm") != TRUST_ANCHOR_PUBLIC_KEY_ALGORITHM:
        blockers.append("server_side_trust_anchor_public_key_algorithm")
    if data.get("signature_algorithm") != SIGNATURE_ALGORITHM:
        blockers.append("server_side_trust_anchor_signature_algorithm")
    scope = data.get("scope") if isinstance(data.get("scope"), dict) else {}
    if not scope:
        blockers.append("server_side_trust_anchor_scope_missing")
    elif sorted(scope) != sorted(TRUST_ANCHOR_SCOPE_FIELDS):
        blockers.append("server_side_trust_anchor_scope_unexpected_fields")
    allowed_components = scope.get("components")
    if allowed_components != list(EXPECTED_COMPONENT_SCOPE):
        blockers.append("server_side_trust_anchor_scope_components")
    allowed_channels = scope.get("channels")
    if (
        not isinstance(allowed_channels, list)
        or not allowed_channels
        or any(channel not in ALLOWED_CHANNELS for channel in allowed_channels)
    ):
        blockers.append("server_side_trust_anchor_scope_channels")
    for key in ("selected_by", "key_owner"):
        if not safe_id(data.get(key)):
            blockers.append(f"server_side_trust_anchor_{key}")
    if not isinstance(data.get("selected_at_utc"), str) or not data["selected_at_utc"].endswith("Z"):
        blockers.append("server_side_trust_anchor_selected_at_utc")
    if data.get("private_key_material_present") is not False:
        blockers.append("server_side_trust_anchor_private_key_material_not_false")
    if data.get("non_claims") != list(REQUIRED_TRUST_ANCHOR_NON_CLAIMS):
        blockers.append("server_side_trust_anchor_non_claims")
    if any(blocker.startswith("server_side_trust_anchor_") for blocker in blockers):
        return None
    return {
        "trusted_key_sha256": key_sha,
        "allowed_components": list(allowed_components),
        "allowed_channels": list(allowed_channels),
    }


def signature_payload(proof: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SIGNATURE_SCHEMA,
        "subject_asset": proof.get("subject_asset"),
        "subject_sha256": proof.get("subject_sha256"),
        "release_set_sha256": proof.get("release_set_sha256"),
        "source_commit": proof.get("source_commit"),
        "component": proof.get("component"),
        "channel": proof.get("channel"),
        "created_at_utc": proof.get("created_at_utc"),
        "covers": proof.get("covers"),
        "signature_algorithm": proof.get("signature_algorithm"),
        "trusted_key_sha256": proof.get("trusted_key_sha256"),
    }


def verify_openssl_signature(*,
                             public_key: Path,
                             signature_path: Path,
                             payload: bytes) -> bool:
    with tempfile.NamedTemporaryFile(prefix="c18-signature-payload-", delete=True) as fh:
        fh.write(payload)
        fh.flush()
        proc = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(public_key),
                "-signature",
                str(signature_path),
                fh.name,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    return proc.returncode == 0 and "Verified OK" in proc.stdout


def validate_common_proof_fields(item: dict[str, Any],
                                 *,
                                 proof: dict[str, Any],
                                 schema: str,
                                 manifest: dict[str, Any],
                                 expected_release_set_sha256: str,
                                 blockers: list[str]) -> None:
    asset = item.get("asset")
    if proof.get("schema") != schema:
        blockers.append(f"server_side_asset_attestation_proof_schema:{asset}")
    if proof.get("subject_asset") != asset:
        blockers.append(f"server_side_asset_attestation_proof_subject_asset:{asset}")
    if proof.get("subject_sha256") != item.get("sha256"):
        blockers.append(f"server_side_asset_attestation_proof_subject_sha256:{asset}")
    if proof.get("release_set_sha256") != expected_release_set_sha256:
        blockers.append(f"server_side_asset_attestation_proof_release_set_sha256:{asset}")
    for key in ("source_commit", "component", "channel", "created_at_utc"):
        if proof.get(key) != manifest.get(key):
            blockers.append(f"server_side_asset_attestation_proof_{key}:{asset}")
    if proof.get("covers") != list(REQUIRED_ATTESTATION_COVERS):
        blockers.append(f"server_side_asset_attestation_proof_covers:{asset}")


def validate_signature_proof_file(item: dict[str, Any],
                                  *,
                                  proof: dict[str, Any],
                                  release_dir: Path,
                                  trusted_keys: dict[str, Path],
                                  trust_anchor: dict[str, Any] | None,
                                  blockers: list[str]) -> None:
    asset = str(item.get("asset"))
    proof_hash = item.get("proof_sha256")
    if not is_hash(proof_hash):
        blockers.append(f"server_side_asset_signature_proof_hash_invalid:{asset}")
    elif sha256_bytes(canonical_json_bytes(proof)) != proof_hash:
        blockers.append(f"server_side_asset_signature_proof_hash_mismatch:{asset}")
    if proof.get("signature_algorithm") != SIGNATURE_ALGORITHM:
        blockers.append(f"server_side_asset_signature_algorithm:{asset}")
    signature_path = resolve_release_file(
        proof.get("signature_file"),
        release_dir=release_dir,
        blockers=blockers,
        asset=asset,
        path_invalid_blocker="server_side_asset_signature_file_invalid",
        missing_blocker="server_side_asset_signature_file_missing",
        symlink_blocker="server_side_asset_signature_file_symlink",
        outside_blocker="server_side_asset_signature_file_outside_release_dir",
    )
    if signature_path is None:
        return
    if sha256_file(signature_path) != item.get("signature_sha256"):
        blockers.append(f"server_side_asset_signature_hash_mismatch:{asset}")
    key_sha = proof.get("trusted_key_sha256")
    key_path = trusted_keys.get(key_sha) if isinstance(key_sha, str) else None
    if key_path is None:
        blockers.append(f"server_side_asset_signature_untrusted_key:{asset}")
        return
    if trust_anchor is not None:
        if key_sha != trust_anchor.get("trusted_key_sha256"):
            blockers.append(f"server_side_asset_signature_key_not_trust_anchor:{asset}")
        if proof.get("component") not in trust_anchor.get("allowed_components", []):
            blockers.append(f"server_side_asset_signature_component_not_allowed:{asset}")
        if proof.get("channel") not in trust_anchor.get("allowed_channels", []):
            blockers.append(f"server_side_asset_signature_channel_not_allowed:{asset}")
    if shutil.which("openssl") is None:
        blockers.append(f"server_side_asset_signature_openssl_missing:{asset}")
        return
    if not verify_openssl_signature(
        public_key=key_path,
        signature_path=signature_path,
        payload=canonical_json_bytes(signature_payload(proof)),
    ):
        blockers.append(f"server_side_asset_signature_verify_failed:{asset}")


def validate_attestation_proof_file(item: dict[str, Any],
                                    *,
                                    release_dir: Path,
                                    manifest: dict[str, Any],
                                    expected_release_set_sha256: str,
                                    trusted_keys: dict[str, Path],
                                    trust_anchor: dict[str, Any] | None,
                                    allow_test_fixtures: bool,
                                    blockers: list[str]) -> None:
    asset = item.get("asset")
    proof_path = resolve_release_file(
        item.get("proof_file"),
        release_dir=release_dir,
        blockers=blockers,
        asset=str(asset),
        path_invalid_blocker="server_side_asset_attestation_proof_file_invalid",
        missing_blocker="server_side_asset_attestation_proof_file_missing",
        symlink_blocker="server_side_asset_attestation_proof_file_symlink",
        outside_blocker="server_side_asset_attestation_proof_file_outside_release_dir",
    )
    if proof_path is None:
        return
    proof_hash = sha256_file(proof_path)
    proof, errors = read_json(proof_path)
    if errors:
        blockers.append(f"server_side_asset_attestation_proof_json:{asset}")
        return
    for hit in secret_json_paths(proof):
        blockers.append(f"server_side_asset_attestation_proof_secret_material:{asset}:{hit}")
    if item.get("attestation_type") == "signature":
        if sorted(proof) != sorted(SIGNATURE_PROOF_ALLOWED_FIELDS):
            blockers.append(f"server_side_asset_signature_proof_unexpected_fields:{asset}")
        validate_common_proof_fields(
            item,
            proof=proof,
            schema=SIGNATURE_SCHEMA,
            manifest=manifest,
            expected_release_set_sha256=expected_release_set_sha256,
            blockers=blockers,
        )
        validate_signature_proof_file(
            item,
            proof=proof,
            release_dir=release_dir,
            trusted_keys=trusted_keys,
            trust_anchor=trust_anchor,
            blockers=blockers,
        )
        return
    if sorted(proof) != sorted(ATTESTATION_PROOF_ALLOWED_FIELDS):
        blockers.append(f"server_side_asset_attestation_proof_unexpected_fields:{asset}")
    if proof_hash != item.get("attestation_sha256"):
        blockers.append(f"server_side_asset_attestation_proof_hash_mismatch:{asset}")
    validate_common_proof_fields(
        item,
        proof=proof,
        schema=ATTESTATION_SCHEMA,
        manifest=manifest,
        expected_release_set_sha256=expected_release_set_sha256,
        blockers=blockers,
    )
    if not allow_test_fixtures:
        blockers.append(f"server_side_asset_signature_required:{asset}")


def validate_release_gate_artifact(gate_path: Path,
                                   *,
                                   release_dir: Path,
                                   manifest_path: Path,
                                   payload_path: Path,
                                   manifest: dict[str, Any],
                                   payload_sha256: str,
                                   blockers: list[str]) -> None:
    gate, errors = read_json(gate_path)
    if errors:
        blockers.append("server_side_release_gate_json")
        return
    expected_schema = RELEASE_GATE_SCHEMA_BY_COMPONENT.get(str(manifest.get("component")))
    if expected_schema is None:
        blockers.append("server_side_release_gate_component_scope")
    elif gate.get("schema") != expected_schema:
        blockers.append("server_side_release_gate_schema")
    if gate.get("passed") is not True:
        blockers.append("server_side_release_gate_not_passed")
    package = gate.get("package") if isinstance(gate.get("package"), dict) else {}
    if not package:
        blockers.append("server_side_release_gate_package_missing")
        return
    if not package_path_matches(package.get("manifest"), expected_path=manifest_path, release_dir=release_dir):
        blockers.append("server_side_release_gate_manifest_mismatch")
    if not package_path_matches(package.get("payload"), expected_path=payload_path, release_dir=release_dir):
        blockers.append("server_side_release_gate_payload_mismatch")
    if package.get("payload_sha256") != payload_sha256:
        blockers.append("server_side_release_gate_payload_sha256_mismatch")
    if package.get("source_commit") != manifest.get("source_commit"):
        blockers.append("server_side_release_gate_source_commit_mismatch")
    if package.get("component") != manifest.get("component"):
        blockers.append("server_side_release_gate_component_mismatch")
    if package.get("channel") != manifest.get("channel"):
        blockers.append("server_side_release_gate_channel_mismatch")
    component = str(manifest.get("component"))
    if component == "player-runtime":
        validate_player_runtime_release_gate_artifact(
            gate,
            manifest_path=manifest_path,
            payload_path=payload_path,
            manifest=manifest,
            blockers=blockers,
        )
    elif component == "totem-core":
        validate_totem_core_release_gate_artifact(gate, blockers)


def validate_player_runtime_release_gate_artifact(gate: dict[str, Any],
                                                  *,
                                                  manifest_path: Path,
                                                  payload_path: Path,
                                                  manifest: dict[str, Any],
                                                  blockers: list[str]) -> None:
    if manifest.get("channel") == "stable":
        blockers.append("server_side_player_runtime_stable_release_gate_forbidden")
    try:
        recomputed = validate_player_runtime_release(manifest_path, payload_path)
    except Exception:
        blockers.append("server_side_player_runtime_release_gate_recompute_failed")
        return
    if sorted(gate) != sorted(recomputed):
        blockers.append("server_side_player_runtime_release_gate_unexpected_fields")
    if gate.get("component") != recomputed.get("component"):
        blockers.append("server_side_player_runtime_release_gate_component")
    if gate.get("manifest") != recomputed.get("manifest"):
        blockers.append("server_side_player_runtime_release_gate_manifest_summary_mismatch")
    if gate.get("payload") != recomputed.get("payload"):
        blockers.append("server_side_player_runtime_release_gate_payload_summary_mismatch")
    for key, value in recomputed.get("package", {}).items():
        package = gate.get("package") if isinstance(gate.get("package"), dict) else {}
        if package.get(key) != value:
            blockers.append(f"server_side_player_runtime_release_gate_package_{key}_mismatch")


def validate_totem_core_release_gate_artifact(gate: dict[str, Any], blockers: list[str]) -> None:
    repo = gate.get("repo") if isinstance(gate.get("repo"), dict) else {}
    if repo.get("dirty") is not False:
        blockers.append("server_side_totem_core_release_gate_repo_dirty")
    guardrails = gate.get("guardrails") if isinstance(gate.get("guardrails"), dict) else {}
    if guardrails.get("github_used") is not False:
        blockers.append("server_side_totem_core_release_gate_github_used")
    steps = gate.get("steps")
    if not isinstance(steps, list) or not steps:
        blockers.append("server_side_totem_core_release_gate_steps_missing")
    elif any(not isinstance(step, dict) or step.get("passed") is not True for step in steps):
        blockers.append("server_side_totem_core_release_gate_steps_not_all_passed")
    checks = gate.get("package", {}).get("checks") if isinstance(gate.get("package"), dict) else {}
    if not isinstance(checks, dict) or not checks:
        blockers.append("server_side_totem_core_release_gate_package_checks_missing")
    elif any(value is not True for value in checks.values()):
        blockers.append("server_side_totem_core_release_gate_package_checks_not_all_passed")


def package_path_matches(value: Any, *, expected_path: Path, release_dir: Path) -> bool:
    if not isinstance(value, str) or not value:
        return False
    expected = expected_path.resolve(strict=True)
    raw = Path(value)
    if raw.is_absolute():
        try:
            return raw.resolve(strict=True) == expected
        except OSError:
            return False
    relative = rel_path(value)
    if relative is None:
        return False
    try:
        candidate = (release_dir / relative).resolve(strict=True)
    except OSError:
        return False
    return candidate == expected


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
        raw_event = item.get("event")
        event = canonical_audit_event(raw_event)
        if event is not None:
            seen.add(event)
            if event not in REQUIRED_AUDIT_EVENTS:
                blockers.append(f"server_side_audit_log_event_unexpected:{raw_event}")
        else:
            blockers.append(f"server_side_audit_log_event_missing_value:{index}")
        for hit in secret_json_paths(item):
            blockers.append(f"server_side_audit_log_secret_material:{index}:{hit}")
        for key in AUDIT_FORBIDDEN_POSITIVE_CLAIMS:
            if item.get(key) is True:
                blockers.append(f"server_side_audit_log_forbidden_positive_claim:{event}:{key}")
        if not isinstance(item.get("actor"), str) or not item.get("actor"):
            blockers.append(f"server_side_audit_log_actor:{index}")
        if not isinstance(item.get("at_utc"), str) or not item.get("at_utc").endswith("Z"):
            blockers.append(f"server_side_audit_log_at_utc:{index}")
        hashes = item.get("artifact_hashes") if isinstance(item.get("artifact_hashes"), dict) else {}
        for asset in REQUIRED_AUDIT_HASHED_ASSETS:
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
                               expected_component: str | None,
                               allow_test_fixtures: bool,
                               trusted_keys: dict[str, Path],
                               trust_anchor: dict[str, Any] | None,
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
    if expected_component is not None and manifest.get("component") != expected_component:
        blockers.append("server_side_manifest_component_expected_mismatch")
    if manifest.get("channel") not in ALLOWED_CHANNELS:
        blockers.append("server_side_manifest_channel")
    if not is_git_sha(manifest.get("source_commit")):
        blockers.append("server_side_manifest_source_commit_invalid")
    if not allow_test_fixtures and (
        data.get("test_fixture") is True
        or manifest.get("version") == "server-fixture"
        or paths["payload"].name == FIXTURE_PAYLOAD_NAME
    ):
        blockers.append("server_side_fixture_evidence_not_allowed")
    payload_sha256 = sha256_file(paths["payload"])
    if manifest.get("payload") != paths["payload"].name:
        blockers.append("server_side_manifest_payload_name_mismatch")
    if manifest.get("payload_sha256") != payload_sha256:
        blockers.append("server_side_manifest_payload_sha256_mismatch")
    asset_hashes = {
        "manifest": sha256_file(paths["manifest"]),
        "payload": payload_sha256,
        "c18-ota-release-gate": sha256_file(paths["c18-ota-release-gate"]),
        "audit-log": sha256_file(paths["audit-log"]),
    }
    expected_release_set_sha256 = release_set_sha256(asset_hashes)
    attestations = attestation_by_asset(data)
    for asset, expected_hash in asset_hashes.items():
        item = attestations.get(asset)
        if item is None:
            blockers.append(f"server_side_asset_attestation_missing:{asset}")
            continue
        if item.get("sha256") != expected_hash:
            blockers.append(f"server_side_asset_attestation_sha256_mismatch:{asset}")
        validate_attestation_proof_file(
            item,
            release_dir=release_dir,
            manifest=manifest,
            expected_release_set_sha256=expected_release_set_sha256,
            trusted_keys=trusted_keys,
            trust_anchor=trust_anchor,
            allow_test_fixtures=allow_test_fixtures,
            blockers=blockers,
        )
    validate_release_gate_artifact(
        paths["c18-ota-release-gate"],
        release_dir=release_dir,
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
                  release_dir: Path | None = None,
                  expected_component: str | None = None,
                  allow_test_fixtures: bool = False,
                  trusted_keys: dict[str, Path] | None = None,
                  trusted_key_errors: list[str] | None = None,
                  trust_anchor: dict[str, Any] | None = None,
                  trust_anchor_errors: list[str] | None = None) -> dict[str, Any]:
    blockers: list[str] = []
    blockers.extend(trusted_key_errors or [])
    blockers.extend(trust_anchor_errors or [])
    resolved_trusted_keys = trusted_keys or {}
    unexpected_fields = sorted(set(data) - set(ALLOWED_TOP_LEVEL_FIELDS))
    if unexpected_fields:
        blockers.append("server_side_unexpected_fields")
        blockers.extend(f"server_side_unexpected_field:{key}" for key in unexpected_fields)
    for hit in secret_json_paths(data):
        blockers.append(f"server_side_secret_material_present:{hit}")
    if expected_component is not None and expected_component not in EXPECTED_COMPONENT_SCOPE:
        blockers.append("server_side_expected_component_invalid")
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
    validate_publish_gate(data, blockers, expected_component=expected_component)
    validate_asset_attestations(data, blockers)
    validate_channel_policy(data, blockers)
    validate_auto_pull_policy(data, blockers)
    validate_component_policy(data, blockers)
    validate_allowlist_policy(data, blockers)
    validate_staged_rollout_policy(data, blockers)
    validate_rollback_policy(data, blockers)
    validate_audit_trail(data, blockers)
    if not allow_test_fixtures and not resolved_trusted_keys:
        blockers.append("server_side_trusted_signature_verification_missing")
    if not allow_test_fixtures and trust_anchor is None:
        blockers.append("server_side_trust_anchor_evidence_missing_or_invalid")
    validate_release_artifacts(
        data,
        evidence_path=evidence_path,
        release_dir=release_dir,
        expected_component=expected_component,
        allow_test_fixtures=allow_test_fixtures,
        trusted_keys=resolved_trusted_keys,
        trust_anchor=trust_anchor,
        blockers=blockers,
    )
    return {
        "schema": "dadooh.c18.server_side_publish_governance_gate.v1",
        "passed": not blockers,
        "result_claim": "server_side_publish_governance_ready" if not blockers else "server_side_publish_governance_blocked",
        "evidence_path": evidence_path,
        "blockers": blockers,
        "non_claims": list(NON_CLAIMS),
    }


def evaluate(path: Path | None,
             *,
             expected_component: str | None = None,
             allow_test_fixtures: bool = False,
             trusted_key_pems: list[Path] | None = None,
             trust_anchor_evidence: Path | None = None) -> dict[str, Any]:
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
    trusted_key_errors: list[str] = []
    trusted_keys = trusted_key_map(
        trusted_key_pems,
        release_dir=path.parent,
        blockers=trusted_key_errors,
    )
    trust_anchor_errors: list[str] = []
    trust_anchor = None
    if not allow_test_fixtures:
        trust_anchor = validate_trust_anchor_evidence(
            trust_anchor_evidence,
            release_dir=path.parent,
            trusted_keys=trusted_keys,
            blockers=trust_anchor_errors,
        )
    return validate_data(
        data,
        evidence_path=str(path),
        release_dir=path.parent,
        expected_component=expected_component,
        allow_test_fixtures=allow_test_fixtures,
        trusted_keys=trusted_keys,
        trusted_key_errors=trusted_key_errors,
        trust_anchor=trust_anchor,
        trust_anchor_errors=trust_anchor_errors,
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def valid_fixture(*,
                  component: str = "totem-core",
                  asset_hashes: dict[str, str] | None = None,
                  proof_hashes: dict[str, str] | None = None,
                  proof_files: dict[str, str] | None = None,
                  test_fixture: bool = False) -> dict[str, Any]:
    resolved_asset_hashes = asset_hashes or {
        "manifest": "a" * 64,
        "payload": "b" * 64,
        "c18-ota-release-gate": "c" * 64,
        "audit-log": "d" * 64,
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
        "test_fixture": test_fixture,
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
            "tool": RELEASE_GATE_TOOL_BY_COMPONENT[component],
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


def write_fixture_release(root: Path,
                          *,
                          component: str = "totem-core",
                          release_gate_name: str = FIXTURE_RELEASE_GATE_NAME,
                          audit_events: tuple[str, ...] = REQUIRED_AUDIT_EVENTS) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if component == "player-runtime":
        version = "server-fixture"
        payload_path = write_player_runtime_payload(root, version, SNAPSHOT_KIOSK.read_text(encoding="utf-8"))
        manifest_path = write_player_runtime_manifest(root, version, payload_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload_sha256 = sha256_file(payload_path)
        release_gate = validate_player_runtime_release(manifest_path, payload_path)
    else:
        payload_path = root / FIXTURE_PAYLOAD_NAME
        payload_path.write_bytes(b"C18 server-side governance fixture payload\n")
        payload_sha256 = sha256_file(payload_path)
        manifest = {
            "schema": "dadooh.totem.update.v1",
            "component": component,
            "version": "server-fixture",
            "channel": "homologation",
            "payload": payload_path.name,
            "payload_sha256": payload_sha256,
            "source_commit": "a" * 40,
            "source_dirty": False,
            "created_at_utc": "2026-06-12T00:00:00Z",
        }
        manifest_path = root / FIXTURE_MANIFEST_NAME
        write_json(manifest_path, manifest)
        release_gate = {
            "schema": RELEASE_GATE_SCHEMA_BY_COMPONENT[component],
            "passed": True,
            "steps": [{"name": "fixture_release_gate", "passed": True}],
            "repo": {"dirty": False},
            "guardrails": {"github_used": False},
            "package": {
                "manifest": manifest_path.name,
                "payload": payload_path.name,
                "payload_sha256": payload_sha256,
                "source_commit": manifest["source_commit"],
                "component": manifest["component"],
                "channel": manifest["channel"],
                "checks": {"fixture_release_gate": True},
                "passed": True,
            },
        }
    release_gate_path = root / release_gate_name
    write_json(release_gate_path, release_gate)
    asset_hashes = {
        "manifest": sha256_file(manifest_path),
        "payload": payload_sha256,
        "c18-ota-release-gate": sha256_file(release_gate_path),
    }
    audit_path = root / FIXTURE_AUDIT_LOG_NAME
    audit_lines = [
        json.dumps({
            "event": event,
            "actor": "c18-release-governance",
            "at_utc": "2026-06-12T00:00:00Z",
            "artifact_hashes": asset_hashes,
        }, sort_keys=True)
        for event in audit_events
    ]
    audit_path.write_text("\n".join(audit_lines) + "\n", encoding="utf-8")
    asset_hashes["audit-log"] = sha256_file(audit_path)
    expected_release_set_sha256 = release_set_sha256(asset_hashes)
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
            "release_set_sha256": expected_release_set_sha256,
            "source_commit": manifest["source_commit"],
            "component": manifest["component"],
            "channel": manifest["channel"],
            "created_at_utc": manifest["created_at_utc"],
            "covers": list(REQUIRED_ATTESTATION_COVERS),
            "signer": "c18-release-governance",
        })
        proof_hashes[asset] = sha256_file(proof_path)
    data = valid_fixture(
        component=component,
        asset_hashes=asset_hashes,
        proof_hashes=proof_hashes,
        proof_files=proof_files,
        test_fixture=True,
    )
    data["audit_trail"]["required_events"] = list(audit_events)
    data["release_assets"] = {
        "manifest": manifest_path.name,
        "payload": payload_path.name,
        "release_gate": release_gate_path.name,
        "audit_log": audit_path.name,
    }
    evidence_path = root / SERVER_SIDE_EVIDENCE_FILENAME
    write_json(evidence_path, data)
    return evidence_path


def run_openssl(cmd: list[str]) -> None:
    subprocess.run(
        ["openssl", *cmd],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def sign_payload(private_key: Path, payload: bytes, signature_path: Path) -> None:
    with tempfile.NamedTemporaryFile(prefix="c18-signature-payload-", delete=True) as fh:
        fh.write(payload)
        fh.flush()
        run_openssl([
            "dgst",
            "-sha256",
            "-sign",
            str(private_key),
            "-out",
            str(signature_path),
            fh.name,
        ])


def write_signed_fixture_release(root: Path, *, component: str = "totem-core") -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    trust_dir = root.parent / f"{root.name}-trust"
    trust_dir.mkdir(parents=True, exist_ok=True)
    private_key = trust_dir / "c18-test-release-signing-key.pem"
    public_key = trust_dir / "c18-test-release-signing-key.pub.pem"
    run_openssl(["genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key)])
    run_openssl(["rsa", "-pubout", "-in", str(private_key), "-out", str(public_key)])
    public_key_sha256 = public_key_spki_sha256(public_key)
    if public_key_sha256 is None:
        raise RuntimeError("openssl could not derive public key fingerprint")

    if component == "player-runtime":
        version = "signed-release"
        payload_path = write_player_runtime_payload(root, version, SNAPSHOT_KIOSK.read_text(encoding="utf-8"))
        manifest_path = write_player_runtime_manifest(root, version, payload_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload_sha256 = sha256_file(payload_path)
        release_gate = validate_player_runtime_release(manifest_path, payload_path)
    else:
        payload_path = root / SIGNED_FIXTURE_PAYLOAD_NAME
        payload_path.write_bytes(b"C18 signed server-side governance fixture payload\n")
        payload_sha256 = sha256_file(payload_path)
        manifest = {
            "schema": "dadooh.totem.update.v1",
            "component": component,
            "version": "signed-release",
            "channel": "homologation",
            "payload": payload_path.name,
            "payload_sha256": payload_sha256,
            "source_commit": "b" * 40,
            "source_dirty": False,
            "created_at_utc": "2026-06-12T00:00:00Z",
        }
        manifest_path = root / SIGNED_FIXTURE_MANIFEST_NAME
        write_json(manifest_path, manifest)
        release_gate = {
            "schema": RELEASE_GATE_SCHEMA_BY_COMPONENT[component],
            "passed": True,
            "steps": [{"name": "fixture_release_gate", "passed": True}],
            "repo": {"dirty": False},
            "guardrails": {"github_used": False},
            "package": {
                "manifest": manifest_path.name,
                "payload": payload_path.name,
                "payload_sha256": payload_sha256,
                "source_commit": manifest["source_commit"],
                "component": manifest["component"],
                "channel": manifest["channel"],
                "checks": {"fixture_release_gate": True},
                "passed": True,
            },
        }
    release_gate_path = root / FIXTURE_RELEASE_GATE_NAME
    write_json(release_gate_path, release_gate)
    asset_hashes = {
        "manifest": sha256_file(manifest_path),
        "payload": payload_sha256,
        "c18-ota-release-gate": sha256_file(release_gate_path),
    }
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
    asset_hashes["audit-log"] = sha256_file(audit_path)
    expected_release_set_sha256 = release_set_sha256(asset_hashes)

    data = valid_fixture(component=component, asset_hashes=asset_hashes)
    data["release_assets"] = {
        "manifest": manifest_path.name,
        "payload": payload_path.name,
        "release_gate": release_gate_path.name,
        "audit_log": audit_path.name,
    }
    proof_files: dict[str, str] = {}
    proof_hashes: dict[str, str] = {}
    signature_hashes: dict[str, str] = {}
    for asset in REQUIRED_SIGNED_OR_ATTESTED_ASSETS:
        proof_files[asset] = f"signatures/{asset}.signature.json"
        signature_rel = f"signatures/{asset}.sig"
        proof = {
            "schema": SIGNATURE_SCHEMA,
            "subject_asset": asset,
            "subject_sha256": asset_hashes[asset],
            "release_set_sha256": expected_release_set_sha256,
            "source_commit": manifest["source_commit"],
            "component": manifest["component"],
            "channel": manifest["channel"],
            "created_at_utc": manifest["created_at_utc"],
            "covers": list(REQUIRED_ATTESTATION_COVERS),
            "signature_algorithm": SIGNATURE_ALGORITHM,
            "trusted_key_sha256": public_key_sha256,
            "signature_file": signature_rel,
        }
        signature_path = root / signature_rel
        signature_path.parent.mkdir(parents=True, exist_ok=True)
        sign_payload(private_key, canonical_json_bytes(signature_payload(proof)), signature_path)
        proof_path = root / proof_files[asset]
        write_json(proof_path, proof)
        proof_hashes[asset] = sha256_bytes(canonical_json_bytes(proof))
        signature_hashes[asset] = sha256_file(signature_path)
    data["asset_attestations"] = [
        {
            "asset": asset,
            "sha256": asset_hashes[asset],
            "attestation_type": "signature",
            "signer": "c18-release-governance",
            "signature_sha256": signature_hashes[asset],
            "proof_sha256": proof_hashes[asset],
            "proof_file": proof_files[asset],
            "covers": list(REQUIRED_ATTESTATION_COVERS),
        }
        for asset in REQUIRED_SIGNED_OR_ATTESTED_ASSETS
    ]
    evidence_path = root / SERVER_SIDE_EVIDENCE_FILENAME
    write_json(evidence_path, data)
    return evidence_path, public_key


def write_trust_anchor_evidence(path: Path,
                                *,
                                trusted_key_spki_sha256: str,
                                allowed_channels: list[str] | None = None) -> Path:
    write_json(path, {
        "schema": TRUST_ANCHOR_SCHEMA,
        "purpose": TRUST_ANCHOR_PURPOSE,
        "trusted_key_spki_sha256": trusted_key_spki_sha256,
        "public_key_algorithm": TRUST_ANCHOR_PUBLIC_KEY_ALGORITHM,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "scope": {
            "components": list(EXPECTED_COMPONENT_SCOPE),
            "channels": allowed_channels or ["homologation", "stable"],
        },
        "selected_by": "operator-release-01",
        "key_owner": "release-security-01",
        "selected_at_utc": "2026-06-12T00:00:00Z",
        "private_key_material_present": False,
        "non_claims": list(REQUIRED_TRUST_ANCHOR_NON_CLAIMS),
    })
    return path


def write_trust_anchor_for_key(path: Path, public_key: Path) -> Path:
    key_hash = public_key_spki_sha256(public_key)
    if key_hash is None:
        raise RuntimeError("openssl could not derive public key fingerprint")
    return write_trust_anchor_evidence(path, trusted_key_spki_sha256=key_hash)


class ServerSidePublishGovernanceGateSelfTest(unittest.TestCase):
    def test_complete_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate(write_fixture_release(Path(tmp)), allow_test_fixtures=True)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
        self.assertIn("this_gate_does_not_enable_auto_pull", result["non_claims"])

    def test_player_runtime_release_gate_filename_passes_as_logical_release_gate_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate(
                write_fixture_release(
                    Path(tmp),
                    component="player-runtime",
                    release_gate_name=PLAYER_RUNTIME_FIXTURE_RELEASE_GATE_NAME,
                ),
                expected_component="player-runtime",
                allow_test_fixtures=True,
            )
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_player_runtime_release_gate_filename_missing_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence_path = write_fixture_release(
                Path(tmp),
                component="player-runtime",
                release_gate_name=PLAYER_RUNTIME_FIXTURE_RELEASE_GATE_NAME,
            )
            (Path(tmp) / PLAYER_RUNTIME_FIXTURE_RELEASE_GATE_NAME).unlink()
            result = evaluate(
                evidence_path,
                expected_component="player-runtime",
                allow_test_fixtures=True,
            )
        self.assertFalse(result["passed"])
        self.assertIn("server_side_release_asset_missing:c18-ota-release-gate", result["blockers"])

    def test_fixture_denies_outside_self_test_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate(write_fixture_release(Path(tmp)))
        self.assertFalse(result["passed"])
        self.assertIn("server_side_fixture_evidence_not_allowed", result["blockers"])
        self.assertIn("server_side_trusted_signature_verification_missing", result["blockers"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_passes_with_external_trusted_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, public_key = write_signed_fixture_release(root / "release")
            trust_anchor = write_trust_anchor_for_key(root / "trust-anchor.json", public_key)
            result = evaluate(path, trusted_key_pems=[public_key], trust_anchor_evidence=trust_anchor)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_denies_without_trust_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path, public_key = write_signed_fixture_release(Path(tmp) / "release")
            result = evaluate(path, trusted_key_pems=[public_key])
        self.assertFalse(result["passed"])
        self.assertIn("server_side_trust_anchor_evidence_missing", result["blockers"])
        self.assertIn("server_side_trust_anchor_evidence_missing_or_invalid", result["blockers"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_denies_without_external_trusted_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path, _public_key = write_signed_fixture_release(Path(tmp) / "release")
            result = evaluate(path)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_trusted_signature_verification_missing", result["blockers"])
        self.assertIn("server_side_asset_signature_untrusted_key:payload", result["blockers"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_denies_untrusted_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, public_key = write_signed_fixture_release(root / "release")
            trust_anchor = write_trust_anchor_for_key(root / "trust-anchor.json", public_key)
            other_private = root / "other-private.pem"
            other_public = root / "other-public.pem"
            run_openssl(["genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(other_private)])
            run_openssl(["rsa", "-pubout", "-in", str(other_private), "-out", str(other_public)])
            result = evaluate(path, trusted_key_pems=[other_public], trust_anchor_evidence=trust_anchor)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_trust_anchor_key_not_trusted", result["blockers"])
        self.assertIn("server_side_asset_signature_untrusted_key:manifest", result["blockers"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_denies_trusted_key_inside_release_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "release"
            path, public_key = write_signed_fixture_release(root)
            trust_anchor = write_trust_anchor_for_key(root.parent / "trust-anchor.json", public_key)
            inside_key = root / public_key.name
            shutil.copyfile(public_key, inside_key)
            result = evaluate(path, trusted_key_pems=[inside_key], trust_anchor_evidence=trust_anchor)
        self.assertFalse(result["passed"])
        self.assertIn(f"server_side_trusted_key_inside_release_dir:{inside_key}", result["blockers"])
        self.assertIn("server_side_trust_anchor_key_not_trusted", result["blockers"])
        self.assertIn("server_side_asset_signature_untrusted_key:manifest", result["blockers"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_denies_trusted_key_parent_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            path, public_key = write_signed_fixture_release(tmp_path / "release")
            trust_anchor = write_trust_anchor_for_key(tmp_path / "trust-anchor.json", public_key)
            symlink_parent = tmp_path / "key-parent-link"
            symlink_parent.symlink_to(public_key.parent, target_is_directory=True)
            symlink_key = symlink_parent / public_key.name
            result = evaluate(path, trusted_key_pems=[symlink_key], trust_anchor_evidence=trust_anchor)
        self.assertFalse(result["passed"])
        self.assertIn(f"server_side_trusted_key_symlink:{symlink_key}", result["blockers"])
        self.assertIn("server_side_asset_signature_untrusted_key:manifest", result["blockers"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_denies_trust_anchor_inside_release_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "release"
            path, public_key = write_signed_fixture_release(root)
            trust_anchor = write_trust_anchor_for_key(root / "trust-anchor.json", public_key)
            result = evaluate(path, trusted_key_pems=[public_key], trust_anchor_evidence=trust_anchor)
        self.assertFalse(result["passed"])
        self.assertIn(f"server_side_trust_anchor_evidence_inside_release_dir:{trust_anchor}", result["blockers"])
        self.assertIn("server_side_trust_anchor_evidence_missing_or_invalid", result["blockers"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_denies_trust_anchor_parent_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            path, public_key = write_signed_fixture_release(tmp_path / "release")
            trust_anchor = write_trust_anchor_for_key(tmp_path / "trust-anchor.json", public_key)
            symlink_parent = tmp_path / "anchor-parent-link"
            symlink_parent.symlink_to(trust_anchor.parent, target_is_directory=True)
            symlink_anchor = symlink_parent / trust_anchor.name
            result = evaluate(path, trusted_key_pems=[public_key], trust_anchor_evidence=symlink_anchor)
        self.assertFalse(result["passed"])
        self.assertIn(f"server_side_trust_anchor_evidence_symlink:{symlink_anchor}", result["blockers"])
        self.assertIn("server_side_trust_anchor_evidence_missing_or_invalid", result["blockers"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_denies_trust_anchor_pki_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            path, public_key = write_signed_fixture_release(tmp_path / "release")
            trust_anchor = write_trust_anchor_for_key(tmp_path / "trust-anchor.json", public_key)
            payload = json.loads(trust_anchor.read_text(encoding="utf-8"))
            payload["pki_chain_verified"] = True
            write_json(trust_anchor, payload)
            result = evaluate(path, trusted_key_pems=[public_key], trust_anchor_evidence=trust_anchor)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_trust_anchor_unexpected_fields", result["blockers"])
        self.assertIn("server_side_trust_anchor_evidence_missing_or_invalid", result["blockers"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_denies_trust_anchor_key_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, public_key = write_signed_fixture_release(root / "release")
            other_private = root / "other-private.pem"
            other_public = root / "other-public.pem"
            run_openssl(["genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(other_private)])
            run_openssl(["rsa", "-pubout", "-in", str(other_private), "-out", str(other_public)])
            other_hash = public_key_spki_sha256(other_public)
            self.assertIsNotNone(other_hash)
            trust_anchor = write_trust_anchor_evidence(root / "trust-anchor.json", trusted_key_spki_sha256=str(other_hash))
            result = evaluate(path, trusted_key_pems=[public_key, other_public], trust_anchor_evidence=trust_anchor)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_asset_signature_key_not_trust_anchor:manifest", result["blockers"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_denies_trust_anchor_channel_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, public_key = write_signed_fixture_release(root / "release")
            key_hash = public_key_spki_sha256(public_key)
            self.assertIsNotNone(key_hash)
            trust_anchor = write_trust_anchor_evidence(
                root / "trust-anchor.json",
                trusted_key_spki_sha256=str(key_hash),
                allowed_channels=["stable"],
            )
            result = evaluate(path, trusted_key_pems=[public_key], trust_anchor_evidence=trust_anchor)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_asset_signature_channel_not_allowed:manifest", result["blockers"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_denies_tampered_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / "release"
            path, public_key = write_signed_fixture_release(root)
            trust_anchor = write_trust_anchor_for_key(tmp_path / "trust-anchor.json", public_key)
            (root / "signatures" / "payload.sig").write_bytes(b"tampered")
            result = evaluate(path, trusted_key_pems=[public_key], trust_anchor_evidence=trust_anchor)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_asset_signature_hash_mismatch:payload", result["blockers"])
        self.assertIn("server_side_asset_signature_verify_failed:payload", result["blockers"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_denies_tampered_release_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / "release"
            path, public_key = write_signed_fixture_release(root)
            trust_anchor = write_trust_anchor_for_key(tmp_path / "trust-anchor.json", public_key)
            proof_path = root / "signatures" / "payload.signature.json"
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            proof["release_set_sha256"] = "0" * 64
            write_json(proof_path, proof)
            result = evaluate(path, trusted_key_pems=[public_key], trust_anchor_evidence=trust_anchor)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_asset_attestation_proof_release_set_sha256:payload", result["blockers"])
        self.assertIn("server_side_asset_signature_proof_hash_mismatch:payload", result["blockers"])
        self.assertIn("server_side_asset_signature_verify_failed:payload", result["blockers"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_denies_tampered_proof_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / "release"
            path, public_key = write_signed_fixture_release(root)
            trust_anchor = write_trust_anchor_for_key(tmp_path / "trust-anchor.json", public_key)
            proof_path = root / "signatures" / "payload.signature.json"
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            proof["channel"] = "stable"
            write_json(proof_path, proof)
            result = evaluate(path, trusted_key_pems=[public_key], trust_anchor_evidence=trust_anchor)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_asset_attestation_proof_channel:payload", result["blockers"])
        self.assertIn("server_side_asset_signature_proof_hash_mismatch:payload", result["blockers"])
        self.assertIn("server_side_asset_signature_verify_failed:payload", result["blockers"])

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

    def test_main_evidence_rejects_unexpected_fields_and_secret_material(self) -> None:
        data = valid_fixture()
        data["operator_secret_token"] = "redacted"
        data["leaked_private_key"] = "-----BEGIN PRIVATE KEY-----\nredacted\n-----END PRIVATE KEY-----"
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_unexpected_fields", result["blockers"])
        self.assertIn("server_side_unexpected_field:operator_secret_token", result["blockers"])
        self.assertIn("server_side_unexpected_field:leaked_private_key", result["blockers"])
        self.assertIn("server_side_secret_material_present:$.operator_secret_token", result["blockers"])
        self.assertIn("server_side_secret_material_present:$.leaked_private_key", result["blockers"])

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
            result = evaluate(path, allow_test_fixtures=True)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_expected_component_accepts_matching_player_runtime_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_fixture_release(Path(tmp), component="player-runtime")
            result = evaluate(path, expected_component="player-runtime", allow_test_fixtures=True)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_expected_component_denies_totem_core_for_player_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_fixture_release(Path(tmp), component="totem-core")
            result = evaluate(path, expected_component="player-runtime", allow_test_fixtures=True)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_manifest_component_expected_mismatch", result["blockers"])
        self.assertIn("server_side_publish_gate_tool", result["blockers"])

    def test_manifest_source_commit_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_fixture_release(root, component="player-runtime")
            manifest_path = next(root.glob("dadooh-player-runtime-*.manifest.json"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.pop("source_commit")
            write_json(manifest_path, manifest)
            result = evaluate(path, expected_component="player-runtime", allow_test_fixtures=True)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_manifest_source_commit_invalid", result["blockers"])

    def test_tampered_payload_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_fixture_release(Path(tmp))
            (Path(tmp) / FIXTURE_PAYLOAD_NAME).write_bytes(b"tampered\n")
            result = evaluate(path, allow_test_fixtures=True)
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
            result = evaluate(path, allow_test_fixtures=True)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_asset_attestation_proof_hash_mismatch:payload", result["blockers"])
        self.assertIn("server_side_asset_attestation_proof_subject_sha256:payload", result["blockers"])

    def test_attestation_proof_rejects_unexpected_secret_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_fixture_release(root)
            evidence = json.loads(path.read_text(encoding="utf-8"))
            proof_path = root / "attestations" / "payload.attestation.json"
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            proof["operator_secret_token"] = "redacted"
            write_json(proof_path, proof)
            for item in evidence["asset_attestations"]:
                if item["asset"] == "payload":
                    item["attestation_sha256"] = sha256_file(proof_path)
            write_json(path, evidence)
            result = evaluate(path, allow_test_fixtures=True)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_asset_attestation_proof_secret_material:payload:$.operator_secret_token", result["blockers"])
        self.assertIn("server_side_asset_attestation_proof_unexpected_fields:payload", result["blockers"])

    def test_tampered_release_gate_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_fixture_release(Path(tmp))
            gate_path = Path(tmp) / FIXTURE_RELEASE_GATE_NAME
            gate = json.loads(gate_path.read_text(encoding="utf-8"))
            gate["package"]["payload_sha256"] = "0" * 64
            write_json(gate_path, gate)
            result = evaluate(path, allow_test_fixtures=True)
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
            result = evaluate(path, allow_test_fixtures=True)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_asset_attestation_sha256_mismatch:audit-log", result["blockers"])
        self.assertIn("server_side_audit_log_event_missing:stable_promotion_evaluated", result["blockers"])
        self.assertIn("server_side_audit_log_hash_mismatch:release_created:payload", result["blockers"])

    def test_legacy_stable_promoted_event_alias_remains_accepted_for_signed_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_fixture_release(
                Path(tmp),
                audit_events=(
                    "release_created",
                    "asset_attested",
                    "channel_selected",
                    "allowlist_evaluated",
                    "rollout_stage_changed",
                    "rollback_triggered",
                    "stable_promoted",
                ),
            )
            result = evaluate(path, allow_test_fixtures=True)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_audit_log_positive_claims_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_fixture_release(root)
            audit_path = root / FIXTURE_AUDIT_LOG_NAME
            lines = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
            lines[0]["promotion_performed"] = True
            lines[1]["auto_pull_enabled"] = True
            lines[2]["public_player_runtime_thaw"] = True
            lines[3]["operator_secret_token"] = "redacted"
            audit_path.write_text("\n".join(json.dumps(line, sort_keys=True) for line in lines) + "\n", encoding="utf-8")
            result = evaluate(path, allow_test_fixtures=True)
        self.assertFalse(result["passed"])
        self.assertIn(
            "server_side_audit_log_forbidden_positive_claim:release_created:promotion_performed",
            result["blockers"],
        )
        self.assertIn(
            "server_side_audit_log_forbidden_positive_claim:asset_attested:auto_pull_enabled",
            result["blockers"],
        )
        self.assertIn(
            "server_side_audit_log_forbidden_positive_claim:channel_selected:public_player_runtime_thaw",
            result["blockers"],
        )
        self.assertIn("server_side_audit_log_secret_material:4:$.operator_secret_token", result["blockers"])

    def test_totem_core_minimal_release_gate_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_fixture_release(root)
            gate_path = root / FIXTURE_RELEASE_GATE_NAME
            gate = json.loads(gate_path.read_text(encoding="utf-8"))
            write_json(gate_path, {
                "schema": gate["schema"],
                "passed": True,
                "package": {
                    "manifest": gate["package"]["manifest"],
                    "payload": gate["package"]["payload"],
                    "payload_sha256": gate["package"]["payload_sha256"],
                    "source_commit": gate["package"]["source_commit"],
                    "component": gate["package"]["component"],
                    "channel": gate["package"]["channel"],
                },
            })
            result = evaluate(path, allow_test_fixtures=True)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_totem_core_release_gate_steps_missing", result["blockers"])
        self.assertIn("server_side_totem_core_release_gate_repo_dirty", result["blockers"])
        self.assertIn("server_side_totem_core_release_gate_github_used", result["blockers"])
        self.assertIn("server_side_totem_core_release_gate_package_checks_missing", result["blockers"])

    def test_player_runtime_stable_or_minimal_release_gate_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_fixture_release(
                root,
                component="player-runtime",
                release_gate_name=PLAYER_RUNTIME_FIXTURE_RELEASE_GATE_NAME,
            )
            manifest_path = next(root.glob("dadooh-player-runtime-*.manifest.json"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["channel"] = "stable"
            write_json(manifest_path, manifest)
            gate_path = root / PLAYER_RUNTIME_FIXTURE_RELEASE_GATE_NAME
            gate = json.loads(gate_path.read_text(encoding="utf-8"))
            write_json(gate_path, {
                "schema": gate["schema"],
                "passed": True,
                "package": {
                    "manifest": gate["package"]["manifest"],
                    "payload": gate["package"]["payload"],
                    "payload_sha256": gate["package"]["payload_sha256"],
                    "source_commit": gate["package"]["source_commit"],
                    "component": gate["package"]["component"],
                    "channel": "stable",
                },
            })
            result = evaluate(path, expected_component="player-runtime", allow_test_fixtures=True)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_player_runtime_stable_release_gate_forbidden", result["blockers"])
        self.assertIn("server_side_player_runtime_release_gate_recompute_failed", result["blockers"])

    def test_release_assets_must_not_be_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_fixture_release(root)
            outside = root.parent / "outside-payload.txt"
            outside.write_text("outside\n", encoding="utf-8")
            payload = root / FIXTURE_PAYLOAD_NAME
            payload.unlink()
            payload.symlink_to(outside)
            result = evaluate(path, allow_test_fixtures=True)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_release_asset_symlink:payload", result["blockers"])

    def test_attestation_proofs_must_not_be_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_fixture_release(root)
            outside = root.parent / "outside-proof.json"
            outside.write_text("{}", encoding="utf-8")
            proof = root / "attestations" / "payload.attestation.json"
            proof.unlink()
            proof.symlink_to(outside)
            result = evaluate(path, allow_test_fixtures=True)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_asset_attestation_proof_file_symlink:payload", result["blockers"])

    def test_release_gate_package_paths_must_not_traverse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = write_fixture_release(root)
            gate_path = root / FIXTURE_RELEASE_GATE_NAME
            gate = json.loads(gate_path.read_text(encoding="utf-8"))
            gate["package"]["manifest"] = f"../outside/{FIXTURE_MANIFEST_NAME}"
            write_json(gate_path, gate)
            result = evaluate(path, allow_test_fixtures=True)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_release_gate_manifest_mismatch", result["blockers"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate C18 server-side publish governance evidence.")
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--expected-component", choices=EXPECTED_COMPONENT_SCOPE, default=None)
    parser.add_argument("--trusted-key-pem", type=Path, action="append", default=[])
    parser.add_argument("--trust-anchor-evidence", type=Path, default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ServerSidePublishGovernanceGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = evaluate(
        args.evidence,
        expected_component=args.expected_component,
        trusted_key_pems=args.trusted_key_pem,
        trust_anchor_evidence=args.trust_anchor_evidence,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif not result["passed"]:
        print("\n".join(result["blockers"]), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
