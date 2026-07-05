#!/usr/bin/env python3
"""Default-deny C18 totem-core stable promotion gate.

This gate is deliberately scoped to `totem-core`. It authorizes a stable
totem-core release for the production image auto-pull path; it does not thaw
player-runtime, authorize player-runtime stable releases, publish to GitHub, or
replace board validation of the production image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.totem_core_stable_promotion.v1"
GATE_SCHEMA = "dadooh.c18.totem_core_stable_promotion_gate.v1"
RELEASE_GATE_SCHEMA = "dadooh.c18.ota.release_gate.v1"
EVIDENCE_ALLOWED_FIELDS = frozenset({
    "schema",
    "component",
    "channel",
    "approved",
    "explicit_operator_decision",
    "rollback_ready",
    "auto_pull_enabled",
    "auto_pull_scope",
    "operator",
    "rollback_owner",
    "production_image_tag",
    "production_image_sha256",
    "production_image_build_manifest_sha256",
    "production_image_offline_validation_sha256",
    "non_claims",
})
FORBIDDEN_TRUE_KEYS = (
    "h2_green",
    "h2_passed",
    "media_system_update_authorized",
    "production_enabled",
    "production_ready",
    "player_runtime_auto_pull_enabled",
    "player_runtime_thaw",
    "player_runtime_thaw_enabled",
    "player_runtime_public_thaw",
    "player_runtime_stable_authorized",
    "public_thaw",
    "published",
    "release_published",
    "stable_authorized",
    "stable_publish_executed",
)
REQUIRED_NON_CLAIMS = (
    "this_does_not_publish_releases",
    "this_does_not_thaw_player_runtime",
    "this_does_not_authorize_player_runtime_stable",
    "this_does_not_update_media_system",
    "board_validation_still_required",
)


def read_json(path: Path | None, label: str) -> tuple[dict[str, Any], list[str]]:
    if path is None:
        return {}, [f"{label}_missing"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"{label}_json_error:{type(exc).__name__}"]
    if not isinstance(payload, dict):
        return {}, [f"{label}_not_object"]
    return payload, []


def sha256_file(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def iter_json_paths(value: Any, prefix: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    paths: list[tuple[tuple[str, ...], Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = (*prefix, str(key))
            paths.append((child, item))
            paths.extend(iter_json_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child = (*prefix, f"[{index}]")
            paths.append((child, item))
            paths.extend(iter_json_paths(item, child))
    return paths


def validate_evidence_schema(payload: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for field in sorted(set(payload) - EVIDENCE_ALLOWED_FIELDS):
        blockers.append(f"evidence_unknown_field:{field}")
    for path, value in iter_json_paths(payload):
        if path and path[-1] in FORBIDDEN_TRUE_KEYS and value is True:
            blockers.append(f"evidence_forbidden_true:{'.'.join(path)}")
    return blockers


def validate_image_build_manifest(
    payload: dict[str, Any],
    *,
    expected_tag: str | None,
    expected_sha256: str | None,
) -> list[str]:
    blockers: list[str] = []
    if payload.get("image_profile") != "production":
        blockers.append("image_build_manifest_not_production_profile")
    if payload.get("totem_core_embed_profile") != "production":
        blockers.append("image_build_manifest_totem_core_profile_not_production")
    if payload.get("artifact_private") is not False:
        blockers.append("image_build_manifest_artifact_private_not_false")
    if payload.get("final_image") is not True:
        blockers.append("image_build_manifest_final_image_not_true")
    if payload.get("production_image") is not True:
        blockers.append("image_build_manifest_production_image_not_true")
    if payload.get("offline_validation_passed") is not True:
        blockers.append("image_build_manifest_offline_validation_not_passed")
    if payload.get("ready_for_c18_production_candidate_validation") is not True:
        blockers.append("image_build_manifest_not_ready_for_production_candidate_validation")
    if payload.get("board_touched") is not False or payload.get("ssh_used") is not False:
        blockers.append("image_build_manifest_must_be_offline")
    if expected_tag and payload.get("image_tag") != expected_tag:
        blockers.append("image_build_manifest_tag_mismatch")
    if expected_sha256 and payload.get("image_sha256") != expected_sha256:
        blockers.append("image_build_manifest_sha256_mismatch")
    embed = payload.get("totem_core_embed") if isinstance(payload.get("totem_core_embed"), dict) else {}
    if embed.get("totem_core_update_timer_enabled") is not True:
        blockers.append("image_build_manifest_timer_not_enabled")
    if embed.get("totem_core_update_policy_source") != "totem_update_policy_production.json":
        blockers.append("image_build_manifest_policy_source_not_production")
    if payload.get("player_runtime_ota_still_frozen") is not True:
        blockers.append("image_build_manifest_player_runtime_not_frozen")
    return blockers


def validate_offline_validation(payload: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    required_true = (
        "marker_scope_matches_profile",
        "totem_core_ota_ready",
        "totem_in_video_group",
        "fsck_clean",
        "no_real_config_embedded",
        "no_player_runtime_marker_preforged",
    )
    for field in required_true:
        if payload.get(field) is not True:
            blockers.append(f"offline_validation_{field}_not_true")
    return blockers


def validate_release_gate_summary(payload: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if payload.get("schema") != RELEASE_GATE_SCHEMA:
        blockers.append("release_gate_summary_schema")
    if payload.get("passed") is not True:
        blockers.append("release_gate_summary_not_passed")
    repo = payload.get("repo") if isinstance(payload.get("repo"), dict) else {}
    if repo.get("dirty") is True:
        blockers.append("release_gate_summary_repo_dirty")
    return blockers


def validate_package_manifest(payload: dict[str, Any], *, evidence_sha256: str | None) -> list[str]:
    blockers: list[str] = []
    if payload.get("schema") != "dadooh.totem.update.v1":
        blockers.append("package_manifest_schema")
    if payload.get("component") != "totem-core":
        blockers.append("package_manifest_component_not_totem_core")
    if payload.get("channel") != "stable":
        blockers.append("package_manifest_channel_not_stable")
    if payload.get("source_dirty") is not False:
        blockers.append("package_manifest_source_dirty")
    if evidence_sha256 and payload.get("stable_promotion_evidence_sha256") != evidence_sha256:
        blockers.append("package_manifest_stable_evidence_sha256_mismatch")
    if not is_sha256(payload.get("payload_sha256")):
        blockers.append("package_manifest_payload_sha256_missing_or_invalid")
    return blockers


def evaluate(
    evidence_path: Path | None,
    *,
    production_image_build_manifest: Path | None = None,
    production_image_offline_validation: Path | None = None,
    package_manifest: Path | None = None,
    release_gate_summary: Path | None = None,
    expect_image_tag: str | None = None,
    expect_image_sha256: str | None = None,
) -> dict[str, Any]:
    evidence, blockers = read_json(evidence_path, "evidence")
    image_manifest, image_errors = read_json(production_image_build_manifest, "production_image_build_manifest")
    offline, offline_errors = read_json(production_image_offline_validation, "production_image_offline_validation")
    blockers.extend(image_errors)
    blockers.extend(offline_errors)

    evidence_sha = sha256_file(evidence_path)
    image_manifest_sha = sha256_file(production_image_build_manifest)
    offline_sha = sha256_file(production_image_offline_validation)

    if not blockers:
        blockers.extend(validate_evidence_schema(evidence))
        if evidence.get("schema") != SCHEMA:
            blockers.append("evidence_schema")
        if evidence.get("component") != "totem-core":
            blockers.append("evidence_component_not_totem_core")
        if evidence.get("channel") != "stable":
            blockers.append("evidence_channel_not_stable")
        for field in ("approved", "explicit_operator_decision", "rollback_ready"):
            if evidence.get(field) is not True:
                blockers.append(f"evidence_{field}_not_true")
        if evidence.get("auto_pull_enabled") is not True:
            blockers.append("evidence_auto_pull_enabled_not_true")
        if evidence.get("auto_pull_scope") != "totem-core-only":
            blockers.append("evidence_auto_pull_scope_not_totem_core_only")
        for field in ("operator", "rollback_owner"):
            if not isinstance(evidence.get(field), str) or not evidence[field].strip():
                blockers.append(f"evidence_{field}_missing")
        if evidence.get("production_image_tag") != expect_image_tag:
            blockers.append("evidence_production_image_tag_mismatch")
        if evidence.get("production_image_sha256") != expect_image_sha256:
            blockers.append("evidence_production_image_sha256_mismatch")
        if image_manifest_sha and evidence.get("production_image_build_manifest_sha256") != image_manifest_sha:
            blockers.append("evidence_image_manifest_sha256_mismatch")
        if offline_sha and evidence.get("production_image_offline_validation_sha256") != offline_sha:
            blockers.append("evidence_offline_validation_sha256_mismatch")
        non_claims = evidence.get("non_claims")
        if not isinstance(non_claims, list) or not set(REQUIRED_NON_CLAIMS).issubset(set(non_claims)):
            blockers.append("evidence_non_claims_missing")
        blockers.extend(validate_image_build_manifest(
            image_manifest,
            expected_tag=expect_image_tag,
            expected_sha256=expect_image_sha256,
        ))
        blockers.extend(validate_offline_validation(offline))

    if package_manifest is not None:
        package, package_errors = read_json(package_manifest, "package_manifest")
        blockers.extend(package_errors)
        if not package_errors:
            blockers.extend(validate_package_manifest(package, evidence_sha256=evidence_sha))
    if release_gate_summary is not None:
        release_gate, release_errors = read_json(release_gate_summary, "release_gate_summary")
        blockers.extend(release_errors)
        if not release_errors:
            blockers.extend(validate_release_gate_summary(release_gate))

    return {
        "schema": GATE_SCHEMA,
        "passed": not blockers,
        "result_claim": "totem_core_stable_promotion_ready" if not blockers else "totem_core_stable_promotion_blocked",
        "evidence_path": str(evidence_path) if evidence_path else None,
        "production_image_build_manifest": str(production_image_build_manifest) if production_image_build_manifest else None,
        "production_image_offline_validation": str(production_image_offline_validation) if production_image_offline_validation else None,
        "package_manifest": str(package_manifest) if package_manifest else None,
        "release_gate_summary": str(release_gate_summary) if release_gate_summary else None,
        "evidence_sha256": evidence_sha,
        "production_image_build_manifest_sha256": image_manifest_sha,
        "production_image_offline_validation_sha256": offline_sha,
        "blockers": blockers,
        "non_claims": list(REQUIRED_NON_CLAIMS),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class TotemCoreStablePromotionGateSelfTest(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path, Path, Path, Path]:
        image_manifest = root / "build_manifest.json"
        offline = root / "offline_validation.json"
        evidence = root / "stable.json"
        package = root / "manifest.json"
        release_gate = root / "release-gate.json"
        image_sha = "9" * 64
        image_tag = "c18-hwdecode-prod-1"
        write_json(image_manifest, {
            "image_profile": "production",
            "totem_core_embed_profile": "production",
            "artifact_private": False,
            "final_image": True,
            "production_image": True,
            "offline_validation_passed": True,
            "ready_for_c18_production_candidate_validation": True,
            "board_touched": False,
            "ssh_used": False,
            "image_tag": image_tag,
            "image_sha256": image_sha,
            "player_runtime_ota_still_frozen": True,
            "totem_core_embed": {
                "totem_core_update_timer_enabled": True,
                "totem_core_update_policy_source": "totem_update_policy_production.json",
            },
        })
        write_json(offline, {
            "marker_scope_matches_profile": True,
            "totem_core_ota_ready": True,
            "totem_in_video_group": True,
            "fsck_clean": True,
            "no_real_config_embedded": True,
            "no_player_runtime_marker_preforged": True,
        })
        write_json(evidence, {
            "schema": SCHEMA,
            "component": "totem-core",
            "channel": "stable",
            "approved": True,
            "explicit_operator_decision": True,
            "rollback_ready": True,
            "auto_pull_enabled": True,
            "auto_pull_scope": "totem-core-only",
            "operator": "operator-prod-01",
            "rollback_owner": "rollback-owner-01",
            "production_image_tag": image_tag,
            "production_image_sha256": image_sha,
            "production_image_build_manifest_sha256": sha256_file(image_manifest),
            "production_image_offline_validation_sha256": sha256_file(offline),
            "non_claims": list(REQUIRED_NON_CLAIMS),
        })
        write_json(package, {
            "schema": "dadooh.totem.update.v1",
            "component": "totem-core",
            "channel": "stable",
            "source_dirty": False,
            "payload_sha256": "a" * 64,
            "stable_promotion_evidence_sha256": sha256_file(evidence),
        })
        write_json(release_gate, {
            "schema": RELEASE_GATE_SCHEMA,
            "passed": True,
            "repo": {"dirty": False},
        })
        return evidence, image_manifest, offline, package, release_gate

    def test_complete_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence, image_manifest, offline, package, release_gate = self.fixture(Path(tmp))
            result = evaluate(
                evidence,
                production_image_build_manifest=image_manifest,
                production_image_offline_validation=offline,
                package_manifest=package,
                release_gate_summary=release_gate,
                expect_image_tag="c18-hwdecode-prod-1",
                expect_image_sha256="9" * 64,
            )
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_missing_evidence_denies(self) -> None:
        result = evaluate(None)
        self.assertFalse(result["passed"])
        self.assertIn("evidence_missing", result["blockers"])

    def test_player_runtime_thaw_claim_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence, image_manifest, offline, _package, _release_gate = self.fixture(Path(tmp))
            data = json.loads(evidence.read_text(encoding="utf-8"))
            data["player_runtime_public_thaw"] = True
            write_json(evidence, data)
            result = evaluate(
                evidence,
                production_image_build_manifest=image_manifest,
                production_image_offline_validation=offline,
                expect_image_tag="c18-hwdecode-prod-1",
                expect_image_sha256="9" * 64,
            )
        self.assertFalse(result["passed"])
        self.assertIn("evidence_forbidden_true:player_runtime_public_thaw", result["blockers"])

    def test_nested_positive_claim_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence, image_manifest, offline, _package, _release_gate = self.fixture(Path(tmp))
            data = json.loads(evidence.read_text(encoding="utf-8"))
            data["claims"] = {
                "player_runtime_public_thaw": True,
                "stable_authorized": True,
                "production_enabled": True,
            }
            write_json(evidence, data)
            result = evaluate(
                evidence,
                production_image_build_manifest=image_manifest,
                production_image_offline_validation=offline,
                expect_image_tag="c18-hwdecode-prod-1",
                expect_image_sha256="9" * 64,
            )
        self.assertFalse(result["passed"])
        self.assertIn("evidence_unknown_field:claims", result["blockers"])
        self.assertIn("evidence_forbidden_true:claims.player_runtime_public_thaw", result["blockers"])
        self.assertIn("evidence_forbidden_true:claims.stable_authorized", result["blockers"])
        self.assertIn("evidence_forbidden_true:claims.production_enabled", result["blockers"])

    def test_top_level_production_claim_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence, image_manifest, offline, _package, _release_gate = self.fixture(Path(tmp))
            data = json.loads(evidence.read_text(encoding="utf-8"))
            data["production_enabled"] = True
            write_json(evidence, data)
            result = evaluate(
                evidence,
                production_image_build_manifest=image_manifest,
                production_image_offline_validation=offline,
                expect_image_tag="c18-hwdecode-prod-1",
                expect_image_sha256="9" * 64,
            )
        self.assertFalse(result["passed"])
        self.assertIn("evidence_unknown_field:production_enabled", result["blockers"])
        self.assertIn("evidence_forbidden_true:production_enabled", result["blockers"])

    def test_non_production_image_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence, image_manifest, offline, _package, _release_gate = self.fixture(Path(tmp))
            data = json.loads(image_manifest.read_text(encoding="utf-8"))
            data["image_profile"] = "lab"
            write_json(image_manifest, data)
            result = evaluate(
                evidence,
                production_image_build_manifest=image_manifest,
                production_image_offline_validation=offline,
                expect_image_tag="c18-hwdecode-prod-1",
                expect_image_sha256="9" * 64,
            )
        self.assertFalse(result["passed"])
        self.assertIn("image_build_manifest_not_production_profile", result["blockers"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate C18 totem-core stable promotion evidence.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--production-image-build-manifest", type=Path)
    parser.add_argument("--production-image-offline-validation", type=Path)
    parser.add_argument("--package-manifest", type=Path)
    parser.add_argument("--release-gate-summary", type=Path)
    parser.add_argument("--expect-image-tag")
    parser.add_argument("--expect-image-sha256")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TotemCoreStablePromotionGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = evaluate(
        args.evidence,
        production_image_build_manifest=args.production_image_build_manifest,
        production_image_offline_validation=args.production_image_offline_validation,
        package_manifest=args.package_manifest,
        release_gate_summary=args.release_gate_summary,
        expect_image_tag=args.expect_image_tag,
        expect_image_sha256=args.expect_image_sha256,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} blockers={len(result['blockers'])}")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
