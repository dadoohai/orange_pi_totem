#!/usr/bin/env python3
"""Validate C18 player-runtime production auto-pull authorization.

Offline-only gate. It validates the flat authorization contract consumed by
scripts/board/totem_updatectl.py::_load_player_runtime_production_authorization
and binds it to the exact manifest, payload, and release-gate artifacts.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import c18_player_runtime_release_gate as release_gate  # noqa: E402


SCHEMA = "dadooh.c18.player_runtime.production_autopull_authorization.v1"
GATE_SCHEMA = "dadooh.c18.player_runtime.production_autopull_authorization_gate.v1"
COMPONENT = "player-runtime"
CHANNEL = "homologation"
DEVICE_TRACK = "c18-hwdecode"
PRODUCTION_REPO = "dadoohai/orange_pi_totem"
ROLL_OUT_MODE = "simple_global"
RELEASE_GATE_SCHEMA = "dadooh.c18.player_runtime.release_gate.v1"
MANIFEST_SCHEMA = "dadooh.totem.update.v1"
CANONICAL_RELEASE_GATE_ASSET_NAME = "c18-player-runtime-release-gate.json"
TOP_LEVEL_FIELDS = frozenset({
    "schema",
    "enabled",
    "component",
    "auto_pull_enabled",
    "allow_latest",
    "allow_prerelease",
    "allow_downgrade",
    "repo",
    "tag_name",
    "version",
    "channel",
    "device_track",
    "source_commit",
    "payload_sha256",
    "manifest_sha256",
    "release_gate_asset_name",
    "release_gate_sha256",
    "business_decision",
    "non_claims",
})
BUSINESS_DECISION_FIELDS = frozenset({
    "risk_accepted",
    "rollout_mode",
    "operator",
    "rollback_owner",
    "accepted_at_local_date",
})
REQUIRED_NON_CLAIMS = (
    "not_latest_broad",
    "not_future_player_runtime_targets",
    "not_kiosky_player_legacy_release_path",
    "not_media_system_update",
    "not_dashboard_or_canary_groups",
    "not_device_side_signature_enforcement",
)
GATE_NON_CLAIMS = (
    "this_gate_does_not_publish_releases",
    "this_gate_does_not_fetch_releases",
    "this_gate_does_not_modify_device_policy_or_timer",
    "this_gate_does_not_apply_player_runtime",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
LOCAL_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, blockers: list[str], label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append(f"{label}_json_error:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        blockers.append(f"{label}_json_not_object")
        return {}
    return data


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def is_git_sha(value: Any) -> bool:
    return isinstance(value, str) and GIT_SHA_RE.fullmatch(value) is not None


def parse_local_date(value: Any) -> dt.date | None:
    if not isinstance(value, str) or LOCAL_DATE_RE.fullmatch(value) is None:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def require_regular_file(path: Path | None, blockers: list[str], label: str) -> bool:
    if path is None:
        blockers.append(f"{label}_missing")
        return False
    if path.is_symlink() or not path.is_file():
        blockers.append(f"{label}_missing_or_symlink")
        return False
    return True


def expected_authorization_from_artifacts(
    manifest_path: Path | None,
    payload_path: Path | None,
    release_gate_path: Path | None,
    *,
    operator: str = "operator-prod-01",
    rollback_owner: str = "rollback-owner-01",
    accepted_at_local_date: str = "2026-07-05",
    rollout_mode: str = ROLL_OUT_MODE,
) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    if not all((
        require_regular_file(manifest_path, blockers, "manifest"),
        require_regular_file(payload_path, blockers, "payload"),
        require_regular_file(release_gate_path, blockers, "release_gate"),
    )):
        return {}, blockers
    assert manifest_path is not None
    assert payload_path is not None
    assert release_gate_path is not None

    manifest = read_json(manifest_path, blockers, "manifest")
    release_data = read_json(release_gate_path, blockers, "release_gate")
    if blockers:
        return {}, blockers

    try:
        expected_release_gate = release_gate.validate_release(manifest_path, payload_path)
    except Exception as exc:
        blockers.append(f"release_gate_validation_failed:{type(exc).__name__}:{exc}")
        expected_release_gate = {}

    if expected_release_gate and release_data != expected_release_gate:
        blockers.append("release_gate_semantics_mismatch")

    if manifest.get("schema") != MANIFEST_SCHEMA:
        blockers.append("manifest_schema")
    if manifest.get("component") != COMPONENT:
        blockers.append("manifest_component_not_player_runtime")
    if manifest.get("channel") != CHANNEL:
        blockers.append("manifest_channel_not_homologation")
    if manifest.get("payload") != payload_path.name:
        blockers.append("manifest_payload_name_mismatch")
    if manifest.get("payload_sha256") != sha256_file(payload_path):
        blockers.append("manifest_payload_sha256_mismatch")
    if not is_git_sha(manifest.get("source_commit")):
        blockers.append("manifest_source_commit_missing_or_invalid")
    if manifest.get("source_dirty") is not False:
        blockers.append("manifest_source_dirty_not_false")
    if not isinstance(manifest.get("version"), str) or not manifest["version"]:
        blockers.append("manifest_version_missing")
    if not isinstance(manifest.get("source_repo"), str) or not manifest["source_repo"]:
        blockers.append("manifest_source_repo_missing")
    elif manifest.get("source_repo") != PRODUCTION_REPO:
        blockers.append("manifest_source_repo_not_production_repo")
    requires = manifest.get("requires") if isinstance(manifest.get("requires"), dict) else {}
    if requires.get("device_track") != DEVICE_TRACK:
        blockers.append("manifest_device_track_mismatch")

    if release_data.get("schema") != RELEASE_GATE_SCHEMA:
        blockers.append("release_gate_schema")
    if release_data.get("passed") is not True:
        blockers.append("release_gate_not_passed")
    if release_data.get("component") != COMPONENT:
        blockers.append("release_gate_component_not_player_runtime")
    package = release_data.get("package") if isinstance(release_data.get("package"), dict) else {}
    release_manifest = release_data.get("manifest") if isinstance(release_data.get("manifest"), dict) else {}
    if package.get("manifest") != manifest_path.name:
        blockers.append("release_gate_manifest_name_mismatch")
    if package.get("payload") != payload_path.name:
        blockers.append("release_gate_payload_name_mismatch")
    if package.get("source_commit") != manifest.get("source_commit"):
        blockers.append("release_gate_source_commit_mismatch")
    if package.get("payload_sha256") != manifest.get("payload_sha256"):
        blockers.append("release_gate_payload_sha256_mismatch")
    if package.get("channel") != CHANNEL:
        blockers.append("release_gate_channel_not_homologation")
    if release_manifest.get("version") != manifest.get("version"):
        blockers.append("release_gate_manifest_version_mismatch")
    if release_manifest.get("source_commit") != manifest.get("source_commit"):
        blockers.append("release_gate_manifest_source_commit_mismatch")
    if release_manifest.get("payload_sha256") != manifest.get("payload_sha256"):
        blockers.append("release_gate_manifest_payload_sha256_mismatch")
    if release_manifest.get("channel") != CHANNEL:
        blockers.append("release_gate_manifest_channel_not_homologation")
    if release_gate_path.name != CANONICAL_RELEASE_GATE_ASSET_NAME:
        blockers.append("release_gate_asset_name_not_canonical")

    if blockers:
        return {}, blockers

    version = manifest["version"]
    return {
        "schema": SCHEMA,
        "enabled": True,
        "component": COMPONENT,
        "auto_pull_enabled": True,
        "allow_latest": False,
        "allow_prerelease": False,
        "allow_downgrade": False,
        "repo": manifest["source_repo"],
        "tag_name": f"player-runtime-{version}",
        "version": version,
        "channel": CHANNEL,
        "device_track": DEVICE_TRACK,
        "source_commit": manifest["source_commit"],
        "payload_sha256": manifest["payload_sha256"],
        "manifest_sha256": sha256_file(manifest_path),
        "release_gate_asset_name": release_gate_path.name,
        "release_gate_sha256": sha256_file(release_gate_path),
        "business_decision": {
            "risk_accepted": True,
            "rollout_mode": rollout_mode,
            "operator": operator,
            "rollback_owner": rollback_owner,
            "accepted_at_local_date": accepted_at_local_date,
        },
        "non_claims": list(REQUIRED_NON_CLAIMS),
    }, []


def validate_business_decision(data: dict[str, Any], blockers: list[str]) -> None:
    decision = data.get("business_decision")
    if not isinstance(decision, dict):
        blockers.append("authorization_business_decision_missing_or_invalid")
        return
    missing = sorted(BUSINESS_DECISION_FIELDS - set(decision))
    extra = sorted(set(decision) - BUSINESS_DECISION_FIELDS)
    blockers.extend(f"authorization_business_decision_missing_field:{field}" for field in missing)
    blockers.extend(f"authorization_business_decision_unexpected_field:{field}" for field in extra)
    if decision.get("risk_accepted") is not True:
        blockers.append("authorization_business_decision_risk_not_accepted")
    if decision.get("rollout_mode") != ROLL_OUT_MODE:
        blockers.append("authorization_business_decision_rollout_mode")
    for key in ("operator", "rollback_owner"):
        if not isinstance(decision.get(key), str) or not decision[key].strip():
            blockers.append(f"authorization_business_decision_{key}_missing")
    if parse_local_date(decision.get("accepted_at_local_date")) is None:
        blockers.append("authorization_business_decision_accepted_at_local_date_invalid")


def validate_authorization_data(
    data: dict[str, Any],
    *,
    expected: dict[str, Any] | None,
    evidence_path: str | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(data, dict):
        data = {}
        blockers.append("authorization_json_not_object")

    missing = sorted(TOP_LEVEL_FIELDS - set(data))
    extra = sorted(set(data) - TOP_LEVEL_FIELDS)
    blockers.extend(f"authorization_missing_field:{field}" for field in missing)
    blockers.extend(f"authorization_unexpected_field:{field}" for field in extra)

    if data.get("schema") != SCHEMA:
        blockers.append("authorization_schema")
    for key in ("enabled", "auto_pull_enabled"):
        if data.get(key) is not True:
            blockers.append(f"authorization_{key}_not_true")
    if data.get("component") != COMPONENT:
        blockers.append("authorization_component_not_player_runtime")
    if data.get("channel") != CHANNEL:
        blockers.append("authorization_channel_not_homologation")
    if data.get("device_track") != DEVICE_TRACK:
        blockers.append("authorization_device_track_mismatch")
    for key in ("allow_latest", "allow_prerelease", "allow_downgrade"):
        if data.get(key) is not False:
            blockers.append(f"authorization_{key}_not_false")
    for key in ("repo", "tag_name", "version", "release_gate_asset_name"):
        if not isinstance(data.get(key), str) or not data[key]:
            blockers.append(f"authorization_{key}_missing_or_invalid")
    if isinstance(data.get("version"), str) and data.get("tag_name") != f"player-runtime-{data['version']}":
        blockers.append("authorization_tag_name_version_mismatch")
    if not is_git_sha(data.get("source_commit")):
        blockers.append("authorization_source_commit_missing_or_invalid")
    for key in ("payload_sha256", "manifest_sha256", "release_gate_sha256"):
        if not is_sha256(data.get(key)):
            blockers.append(f"authorization_{key}_missing_or_invalid")
    if data.get("release_gate_asset_name") != CANONICAL_RELEASE_GATE_ASSET_NAME:
        blockers.append("authorization_release_gate_asset_name_not_canonical")

    validate_business_decision(data, blockers)

    non_claims = data.get("non_claims")
    if not isinstance(non_claims, list) or not all(isinstance(item, str) for item in non_claims):
        blockers.append("authorization_non_claims_missing_or_invalid")
    elif set(non_claims) != set(REQUIRED_NON_CLAIMS) or len(non_claims) != len(REQUIRED_NON_CLAIMS):
        blockers.append("authorization_non_claims_not_canonical")

    if expected is None:
        blockers.append("authorization_expected_contract_missing")
    elif not expected:
        blockers.append("authorization_expected_contract_invalid")
    else:
        for key in sorted(TOP_LEVEL_FIELDS - {"business_decision", "non_claims"}):
            if data.get(key) != expected.get(key):
                blockers.append(f"authorization_{key}_mismatch")
    return {
        "schema": GATE_SCHEMA,
        "passed": not blockers,
        "result_claim": (
            "production_autopull_authorization_ready"
            if not blockers
            else "production_autopull_authorization_blocked"
        ),
        "evidence_path": evidence_path,
        "expected": expected or {},
        "authorization": data,
        "blockers": blockers,
        "non_claims": list(GATE_NON_CLAIMS),
    }


def evaluate(
    authorization: Path | None,
    *,
    manifest: Path | None,
    payload: Path | None,
    release_gate_path: Path | None,
) -> dict[str, Any]:
    auth_blockers: list[str] = []
    if not require_regular_file(authorization, auth_blockers, "authorization"):
        data: dict[str, Any] = {}
    else:
        assert authorization is not None
        data = read_json(authorization, auth_blockers, "authorization")
    decision = data.get("business_decision") if isinstance(data.get("business_decision"), dict) else {}
    expected, artifact_blockers = expected_authorization_from_artifacts(
        manifest,
        payload,
        release_gate_path,
        operator=str(decision.get("operator") or "operator-missing"),
        rollback_owner=str(decision.get("rollback_owner") or "rollback-owner-missing"),
        accepted_at_local_date=str(decision.get("accepted_at_local_date") or "1970-01-01"),
        rollout_mode=str(decision.get("rollout_mode") or ROLL_OUT_MODE),
    )
    result = validate_authorization_data(
        data,
        expected=expected if not artifact_blockers else {},
        evidence_path=str(authorization) if authorization is not None else None,
    )
    blockers = artifact_blockers + auth_blockers + result["blockers"]
    return {
        "schema": GATE_SCHEMA,
        "passed": not blockers,
        "result_claim": (
            "production_autopull_authorization_ready"
            if not blockers
            else "production_autopull_authorization_blocked"
        ),
        "authorization_path": str(authorization) if authorization is not None else None,
        "inputs": {
            "manifest": str(manifest) if manifest is not None else None,
            "payload": str(payload) if payload is not None else None,
            "release_gate": str(release_gate_path) if release_gate_path is not None else None,
        },
        "input_hashes": {
            label: sha256_file(path)
            for label, path in (
                ("authorization_sha256", authorization),
                ("manifest_sha256", manifest),
                ("payload_sha256", payload),
                ("release_gate_sha256", release_gate_path),
            )
            if path is not None and path.is_file() and not path.is_symlink()
        },
        "expected": expected,
        "blockers": blockers,
        "non_claims": list(GATE_NON_CLAIMS),
    }


def write_fixture_artifacts(root: Path, *, version: str = "c18.player-runtime-homolog-test") -> tuple[Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    payload = release_gate.write_payload(root, version, release_gate.SNAPSHOT_KIOSK.read_text(encoding="utf-8"))
    manifest = release_gate.write_manifest(root, version, payload)
    release_gate_path = root / CANONICAL_RELEASE_GATE_ASSET_NAME
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_data["source_repo"] = "dadoohai/orange_pi_totem"
    write_json(manifest, manifest_data)
    write_json(release_gate_path, release_gate.validate_release(manifest, payload))
    return manifest, payload, release_gate_path


class ProductionAutopullAuthorizationGateSelfTest(unittest.TestCase):
    def test_complete_flat_object_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, release_path = write_fixture_artifacts(root)
            expected, blockers = expected_authorization_from_artifacts(manifest, payload, release_path)
            self.assertFalse(blockers)
            auth = root / "authorization.json"
            write_json(auth, expected)
            result = evaluate(auth, manifest=manifest, payload=payload, release_gate_path=release_path)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_missing_authorization_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, release_path = write_fixture_artifacts(root)
            result = evaluate(None, manifest=manifest, payload=payload, release_gate_path=release_path)
        self.assertFalse(result["passed"])
        self.assertIn("authorization_missing", result["blockers"])

    def test_empty_object_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, release_path = write_fixture_artifacts(root)
            auth = root / "authorization.json"
            write_json(auth, {})
            result = evaluate(auth, manifest=manifest, payload=payload, release_gate_path=release_path)
        self.assertFalse(result["passed"])
        self.assertIn("authorization_schema", result["blockers"])
        self.assertIn("authorization_missing_field:enabled", result["blockers"])
        self.assertIn("authorization_business_decision_missing_or_invalid", result["blockers"])

    def test_nested_legacy_object_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, release_path = write_fixture_artifacts(root)
            auth = root / "authorization.json"
            write_json(auth, {
                "schema": SCHEMA,
                "component": COMPONENT,
                "authorization_scope": "production_autopull_exact_target",
                "approved": True,
                "risk_accepted": True,
                "target": {"version": "c18.player-runtime-old"},
                "non_claims": list(REQUIRED_NON_CLAIMS),
            })
            result = evaluate(auth, manifest=manifest, payload=payload, release_gate_path=release_path)
        self.assertFalse(result["passed"])
        self.assertIn("authorization_unexpected_field:target", result["blockers"])
        self.assertIn("authorization_missing_field:enabled", result["blockers"])

    def test_hash_tamper_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, release_path = write_fixture_artifacts(root)
            expected, blockers = expected_authorization_from_artifacts(manifest, payload, release_path)
            self.assertFalse(blockers)
            expected["release_gate_sha256"] = "0" * 64
            auth = root / "authorization.json"
            write_json(auth, expected)
            result = evaluate(auth, manifest=manifest, payload=payload, release_gate_path=release_path)
        self.assertFalse(result["passed"])
        self.assertIn("authorization_release_gate_sha256_mismatch", result["blockers"])

    def test_different_target_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_manifest, old_payload, old_release = write_fixture_artifacts(root / "old", version="c18.player-runtime-old")
            new_manifest, new_payload, new_release = write_fixture_artifacts(root / "new", version="c18.player-runtime-new")
            old_expected, blockers = expected_authorization_from_artifacts(old_manifest, old_payload, old_release)
            self.assertFalse(blockers)
            auth = root / "authorization.json"
            write_json(auth, old_expected)
            result = evaluate(auth, manifest=new_manifest, payload=new_payload, release_gate_path=new_release)
        self.assertFalse(result["passed"])
        self.assertIn("authorization_version_mismatch", result["blockers"])
        self.assertIn("authorization_tag_name_mismatch", result["blockers"])

    def test_business_decision_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, release_path = write_fixture_artifacts(root)
            expected, blockers = expected_authorization_from_artifacts(manifest, payload, release_path)
            self.assertFalse(blockers)
            expected["business_decision"]["risk_accepted"] = False
            auth = root / "authorization.json"
            write_json(auth, expected)
            result = evaluate(auth, manifest=manifest, payload=payload, release_gate_path=release_path)
        self.assertFalse(result["passed"])
        self.assertIn("authorization_business_decision_risk_not_accepted", result["blockers"])

    def test_release_gate_tamper_denies_even_if_authorization_hash_was_old(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, release_path = write_fixture_artifacts(root)
            expected, blockers = expected_authorization_from_artifacts(manifest, payload, release_path)
            self.assertFalse(blockers)
            auth = root / "authorization.json"
            write_json(auth, expected)
            release_data = json.loads(release_path.read_text(encoding="utf-8"))
            release_data["package"]["source_commit"] = "0" * 40
            write_json(release_path, release_data)
            result = evaluate(auth, manifest=manifest, payload=payload, release_gate_path=release_path)
        self.assertFalse(result["passed"])
        self.assertIn("release_gate_semantics_mismatch", result["blockers"])
        self.assertIn("release_gate_source_commit_mismatch", result["blockers"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--release-gate", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProductionAutopullAuthorizationGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = evaluate(
        args.authorization,
        manifest=args.manifest,
        payload=args.payload,
        release_gate_path=args.release_gate,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} result_claim={result['result_claim']}")
        for blocker in result["blockers"]:
            print(f"blocker={blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
