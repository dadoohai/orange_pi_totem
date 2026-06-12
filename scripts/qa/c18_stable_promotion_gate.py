#!/usr/bin/env python3
"""Default-deny C18 stable promotion evidence gate.

This gate validates the evidence file required before a C18 `stable` release can
be built or published. It does not publish, enable auto-pull, promote by itself,
or thaw player-runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from c18_player_runtime_powerloss_evidence_gate import (
    ALL_MATRIX_CHECKPOINTS as EVIDENCE_GATE_POWERLOSS_CHECKPOINTS,
    MANIFEST_SCHEMA as POWERLOSS_MANIFEST_SCHEMA,
    SEMANTICALLY_VALIDATED_CHECKPOINTS as SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS,
)
from c18_server_side_publish_governance_gate import evaluate as evaluate_server_side_gate


SCHEMA = "dadooh.c18.stable_promotion.v1"
GATE_SCHEMA = "dadooh.c18.stable_promotion_gate.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_GATE_SCHEMA = "dadooh.c18.ota.release_gate.v1"
SOAK_SCHEMA = "dadooh.c18.playback.soak.v1"
THAW_DECISION_SCHEMA = "dadooh.c18.player_runtime.thaw_decision.v1"
MIN_SOAK_DURATION_SEC = 24 * 60 * 60
REQUIRED_POWERLOSS_CHECKPOINTS = (
    "after_payload_staged",
    "after_release_dir_created",
    "after_extract",
    "after_state_verifying",
    "after_health_passed",
    "after_release_tree_fsync",
    "after_marker_written",
    "after_previous_symlink",
    "after_current_symlink",
    "after_state_success",
    "before_stage_cleanup",
    "rollback_after_identify_links",
    "rollback_after_current_to_previous",
    "rollback_after_previous_removed",
    "rollback_after_quarantine",
    "rollback_after_current_unlinked",
    "rollback_after_state_success",
)
REQUIRED_TRUE_FIELDS = (
    "approved",
    "physical_homologation_passed",
    "powerloss_matrix_passed",
    "powerloss_semantics_complete",
    "soak_endurance_passed",
    "server_side_governance_passed",
    "release_gate_passed",
    "h2_readiness_passed",
    "explicit_operator_decision",
)
REQUIRED_STRING_FIELDS = (
    "operator",
    "rollback_owner",
)
REQUIRED_SHA256_FIELDS = (
    "release_gate_sha256",
    "h2_readiness_sha256",
    "server_side_evidence_sha256",
    "server_side_trust_anchor_evidence_sha256",
    "soak_summary_sha256",
    "powerloss_matrix_sha256",
)
NON_CLAIMS = (
    "this_gate_does_not_publish_releases",
    "this_gate_does_not_enable_auto_pull",
    "this_gate_does_not_thaw_player_runtime",
)


def read_json(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"json_error:{type(exc).__name__}"]
    if not isinstance(data, dict):
        return {}, ["json_not_object"]
    return data, []


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def step(passed: bool, blockers: list[str], **details: Any) -> dict[str, Any]:
    return {
        "passed": passed,
        "blockers": blockers,
        **details,
    }


def powerloss_matrix_sha256(run_dirs: list[Path]) -> str:
    entries: list[dict[str, str]] = []
    for run_dir in sorted(run_dirs, key=lambda item: str(item)):
        files = (item for item in run_dir.rglob("*") if item.is_file())
        for path in sorted(files, key=lambda item: str(item.relative_to(run_dir))):
            entries.append({
                "run_dir": run_dir.name,
                "file": str(path.relative_to(run_dir)),
                "sha256": sha256_file(path),
            })
    return sha256_json(entries)


def h2_input_bundle_sha256(args: argparse.Namespace, evidence_hashes: dict[str, str]) -> str:
    bundle = {
        "h1_release_gate_sha256": evidence_hashes.get("release_gate_sha256"),
        "powerloss_matrix_sha256": evidence_hashes.get("powerloss_matrix_sha256"),
        "server_side_evidence_sha256": evidence_hashes.get("server_side_evidence_sha256"),
        "server_side_trust_anchor_evidence_sha256": evidence_hashes.get("server_side_trust_anchor_evidence_sha256"),
        "soak_summary_sha256": evidence_hashes.get("soak_summary_sha256"),
        "operator_thaw_decision_sha256": (
            sha256_file(args.operator_thaw_decision)
            if args.operator_thaw_decision is not None and args.operator_thaw_decision.is_file()
            else None
        ),
        "expect_image_tag": args.expect_image_tag,
        "expect_image_sha256": args.expect_image_sha256,
        "expect_image_marker_sha256": args.expect_image_marker_sha256,
    }
    return sha256_json(bundle)


def expected_hashes_from_args(args: argparse.Namespace) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if args.release_gate_summary is not None and args.release_gate_summary.is_file():
        hashes["release_gate_sha256"] = sha256_file(args.release_gate_summary)
    if args.server_side_evidence is not None and args.server_side_evidence.is_file():
        hashes["server_side_evidence_sha256"] = sha256_file(args.server_side_evidence)
    trust_anchor = getattr(args, "server_side_trust_anchor_evidence", None)
    if trust_anchor is not None and trust_anchor.is_file():
        hashes["server_side_trust_anchor_evidence_sha256"] = sha256_file(trust_anchor)
    if args.soak_summary is not None and args.soak_summary.is_file():
        hashes["soak_summary_sha256"] = sha256_file(args.soak_summary)
    if args.powerloss_evidence_dir:
        hashes["powerloss_matrix_sha256"] = powerloss_matrix_sha256(list(args.powerloss_evidence_dir))
    if {
        "release_gate_sha256",
        "server_side_evidence_sha256",
        "server_side_trust_anchor_evidence_sha256",
        "soak_summary_sha256",
        "powerloss_matrix_sha256",
    }.issubset(hashes):
        hashes["h2_readiness_sha256"] = h2_input_bundle_sha256(args, hashes)
    return hashes


def read_artifact(path: Path | None, label: str) -> tuple[dict[str, Any], list[str]]:
    if path is None:
        return {}, [f"{label}_missing"]
    return read_json(path)


def evaluate_release_gate_summary(path: Path | None) -> dict[str, Any]:
    data, errors = read_artifact(path, "release_gate_summary")
    blockers = list(errors)
    if not errors:
        if data.get("schema") != RELEASE_GATE_SCHEMA:
            blockers.append("release_gate_summary_schema")
        if data.get("passed") is not True:
            blockers.append("release_gate_summary_not_passed")
        repo = data.get("repo") if isinstance(data.get("repo"), dict) else {}
        if repo.get("dirty") is True:
            blockers.append("release_gate_summary_repo_dirty")
    return step(not blockers, blockers, evidence_path=str(path) if path is not None else None)


def soak_total_duration(summary: dict[str, Any]) -> float:
    policy = summary.get("collection_policy")
    counters = summary.get("counters")
    if isinstance(policy, dict):
        try:
            return float(policy.get("cycles", 0)) * float(policy.get("cycle_duration_sec", 0))
        except Exception:
            return 0.0
    if isinstance(counters, dict):
        try:
            return float(counters.get("duration_sec", 0))
        except Exception:
            return 0.0
    return 0.0


def evaluate_soak_summary(path: Path | None) -> dict[str, Any]:
    data, errors = read_artifact(path, "soak_summary")
    blockers = list(errors)
    duration = 0.0
    if not errors:
        if data.get("schema") != SOAK_SCHEMA:
            blockers.append("soak_summary_schema")
        if data.get("passed") is not True:
            blockers.append("soak_summary_not_passed")
        duration = soak_total_duration(data)
        if duration < MIN_SOAK_DURATION_SEC:
            blockers.append("soak_summary_duration_below_24h")
        counters = data.get("counters") if isinstance(data.get("counters"), dict) else {}
        for key in ("max_panfrost_faults_delta", "max_mmc_timeout_reset_delta", "max_ext4_errors_delta"):
            if counters.get(key) not in (0, 0.0):
                blockers.append(f"soak_summary_{key}_nonzero_or_missing")
    return step(not blockers, blockers, evidence_path=str(path) if path is not None else None, duration_sec=duration)


def manifest_image_errors(
    manifest: dict[str, Any],
    *,
    expect_image_tag: str | None,
    expect_image_sha256: str | None,
    expect_image_marker_sha256: str | None,
) -> list[str]:
    errors: list[str] = []
    if expect_image_tag is None:
        errors.append("powerloss_expected_image_tag_required")
    elif manifest.get("image_tag") != expect_image_tag:
        errors.append("powerloss_image_tag_mismatch_or_missing")
    if expect_image_sha256 is None:
        errors.append("powerloss_expected_image_sha256_required")
    elif manifest.get("image_sha256") != expect_image_sha256:
        errors.append("powerloss_image_sha256_mismatch_or_missing")
    if expect_image_marker_sha256 is None:
        errors.append("powerloss_expected_image_marker_sha256_required")
    elif manifest.get("image_marker_sha256") != expect_image_marker_sha256:
        errors.append("powerloss_image_marker_sha256_mismatch_or_missing")
    return errors


def powerloss_semantics_ledger() -> dict[str, Any]:
    required = set(REQUIRED_POWERLOSS_CHECKPOINTS)
    evidence_gate_matrix = set(EVIDENCE_GATE_POWERLOSS_CHECKPOINTS)
    semantically_validated = required & set(SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS)
    return {
        "required_checkpoints": list(REQUIRED_POWERLOSS_CHECKPOINTS),
        "evidence_gate_matrix_checkpoints": sorted(evidence_gate_matrix),
        "semantically_validated_checkpoints": sorted(semantically_validated),
        "semantics_not_implemented_checkpoints": sorted(required - semantically_validated),
        "evidence_gate_contract_mismatch": sorted(required ^ evidence_gate_matrix),
    }


def run_powerloss_gate(run_dir: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "python3",
            "scripts/qa/c18_player_runtime_powerloss_evidence_gate.py",
            "--run-dir",
            str(run_dir),
            "--json",
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    )
    payload: dict[str, Any] = {}
    if proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = {}
    return {
        "passed": proc.returncode == 0 and payload.get("passed") is True,
        "returncode": proc.returncode,
        "stderr_tail": proc.stderr[-800:],
        "gate": payload,
    }


def evaluate_powerloss_matrix(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    checkpoint_dirs: dict[str, str] = {}
    gate_results: dict[str, dict[str, Any]] = {}
    duplicate_checkpoints: list[str] = []
    semantics_ledger = powerloss_semantics_ledger()
    if semantics_ledger["evidence_gate_contract_mismatch"]:
        blockers.append("powerloss_matrix_contract_mismatch")
    if semantics_ledger["semantics_not_implemented_checkpoints"]:
        blockers.append("powerloss_checkpoint_semantics_incomplete")
    for run_dir in args.powerloss_evidence_dir or []:
        data, errors = read_json(run_dir / "evidence-manifest.json")
        checkpoint = data.get("checkpoint")
        if data.get("schema") != POWERLOSS_MANIFEST_SCHEMA:
            errors.append("powerloss_manifest_schema")
        if not isinstance(checkpoint, str) or not checkpoint:
            errors.append("powerloss_manifest_checkpoint_missing")
            checkpoint = f"unknown:{run_dir.name}"
        if checkpoint in checkpoint_dirs:
            duplicate_checkpoints.append(str(checkpoint))
        checkpoint_dirs[str(checkpoint)] = str(run_dir)
        errors.extend(
            manifest_image_errors(
                data,
                expect_image_tag=args.expect_image_tag,
                expect_image_sha256=args.expect_image_sha256,
                expect_image_marker_sha256=args.expect_image_marker_sha256,
            )
        )
        gate = run_powerloss_gate(run_dir)
        gate_results[str(checkpoint)] = {
            "dir": str(run_dir),
            "manifest_errors": errors,
            "gate_passed": gate["passed"],
            "gate_returncode": gate["returncode"],
            "gate_stderr_tail": gate["stderr_tail"],
        }
        if errors:
            blockers.extend(f"{checkpoint}:{error}" for error in errors)
        if not gate["passed"]:
            blockers.append(f"{checkpoint}:powerloss_gate_failed")
    missing = sorted(set(REQUIRED_POWERLOSS_CHECKPOINTS) - set(checkpoint_dirs))
    extra = sorted(set(checkpoint_dirs) - set(REQUIRED_POWERLOSS_CHECKPOINTS))
    if missing:
        blockers.append("powerloss_matrix_incomplete")
    if extra:
        blockers.append("powerloss_unknown_checkpoint")
    if duplicate_checkpoints:
        blockers.append("powerloss_duplicate_checkpoint")
    return step(
        not blockers,
        blockers,
        observed_checkpoints=sorted(checkpoint_dirs),
        missing_checkpoints=missing,
        extra_checkpoints=extra,
        duplicate_checkpoints=sorted(set(duplicate_checkpoints)),
        semantics_ledger=semantics_ledger,
        gate_results=gate_results,
    )


def evaluate_server_side_artifact(args: argparse.Namespace) -> dict[str, Any]:
    if args.server_side_evidence is None:
        return step(False, ["server_side_evidence_missing"])
    trusted_keys = list(getattr(args, "server_side_trusted_key_pem", []) or [])
    if not trusted_keys:
        return step(False, ["server_side_trusted_key_pem_missing"], evidence_path=str(args.server_side_evidence))
    result = evaluate_server_side_gate(
        args.server_side_evidence,
        trusted_key_pems=trusted_keys,
        trust_anchor_evidence=args.server_side_trust_anchor_evidence,
    )
    blockers = list(result.get("blockers", []))
    return step(
        not blockers,
        blockers,
        evidence_path=str(args.server_side_evidence),
        gate_result=result,
    )


def evaluate_operator_decision(path: Path | None) -> dict[str, Any]:
    data, errors = read_artifact(path, "operator_thaw_decision")
    blockers = list(errors)
    if not errors:
        if data.get("schema") != THAW_DECISION_SCHEMA:
            blockers.append("operator_thaw_decision_schema")
        if data.get("approved") is not True:
            blockers.append("operator_thaw_decision_not_approved")
        if data.get("acknowledges_h2_evidence") is not True:
            blockers.append("operator_thaw_decision_missing_h2_ack")
    return step(not blockers, blockers, evidence_path=str(path) if path is not None else None)


def evaluate_artifact_semantics(args: argparse.Namespace) -> dict[str, Any]:
    checks = {
        "release_gate_summary": evaluate_release_gate_summary(args.release_gate_summary),
        "powerloss_matrix": evaluate_powerloss_matrix(args),
        "soak_summary": evaluate_soak_summary(args.soak_summary),
        "server_side_governance": evaluate_server_side_artifact(args),
        "operator_thaw_decision": evaluate_operator_decision(args.operator_thaw_decision),
    }
    blockers = [
        f"{name}:{blocker}"
        for name, result in checks.items()
        for blocker in result.get("blockers", [])
    ]
    return {
        "passed": not blockers,
        "checks": checks,
        "blockers": blockers,
    }


def validate_data(data: dict[str, Any],
                  *,
                  evidence_path: str | None = None,
                  expected_hashes: dict[str, str] | None = None,
                  require_expected_hashes: bool = False,
                  artifact_semantics: dict[str, Any] | None = None) -> dict[str, Any]:
    blockers: list[str] = []
    resolved_expected_hashes = expected_hashes or {}
    if data.get("schema") != SCHEMA:
        blockers.append("stable_promotion_schema")
    if data.get("component") != "totem-core":
        blockers.append("stable_promotion_component_not_totem_core")
    if data.get("channel") != "stable":
        blockers.append("stable_promotion_channel_not_stable")
    for key in REQUIRED_TRUE_FIELDS:
        if data.get(key) is not True:
            blockers.append(f"stable_promotion_{key}_missing_or_false")
    for key in REQUIRED_STRING_FIELDS:
        if not isinstance(data.get(key), str) or not data.get(key).strip():
            blockers.append(f"stable_promotion_{key}_missing")
    for key in REQUIRED_SHA256_FIELDS:
        if not is_sha256(data.get(key)):
            blockers.append(f"stable_promotion_{key}_missing_or_invalid")
    if data.get("auto_pull_enabled") is not False:
        blockers.append("stable_promotion_auto_pull_enabled")
    if data.get("public_player_runtime_thaw") is True:
        blockers.append("stable_promotion_public_player_runtime_thaw_enabled")
    if require_expected_hashes:
        missing_expected = sorted(set(REQUIRED_SHA256_FIELDS) - set(resolved_expected_hashes))
        if missing_expected:
            blockers.append("stable_promotion_expected_hashes_missing")
            blockers.extend(f"stable_promotion_expected_hash_missing:{field}" for field in missing_expected)
    for field, expected in resolved_expected_hashes.items():
        if data.get(field) != expected:
            blockers.append(f"stable_promotion_{field}_mismatch")
    if artifact_semantics is not None:
        blockers.extend(f"stable_promotion_artifact_semantics:{blocker}" for blocker in artifact_semantics.get("blockers", []))
    return {
        "schema": GATE_SCHEMA,
        "passed": not blockers,
        "result_claim": "stable_promotion_evidence_ready" if not blockers else "stable_promotion_evidence_blocked",
        "evidence_path": evidence_path,
        "expected_hashes": resolved_expected_hashes,
        "artifact_semantics": artifact_semantics,
        "blockers": blockers,
        "non_claims": list(NON_CLAIMS),
    }


def evaluate(path: Path | None,
             *,
             expected_hashes: dict[str, str] | None = None,
             require_expected_hashes: bool = False,
             artifact_semantics: dict[str, Any] | None = None) -> dict[str, Any]:
    if path is None:
        return {
            "schema": GATE_SCHEMA,
            "passed": False,
            "result_claim": "stable_promotion_evidence_blocked",
            "evidence_path": None,
            "blockers": ["missing_stable_promotion_evidence"],
            "non_claims": list(NON_CLAIMS),
        }
    data, errors = read_json(path)
    if errors:
        return {
            "schema": GATE_SCHEMA,
            "passed": False,
            "result_claim": "stable_promotion_evidence_blocked",
            "evidence_path": str(path),
            "blockers": errors,
            "non_claims": list(NON_CLAIMS),
        }
    return validate_data(
        data,
        evidence_path=str(path),
        expected_hashes=expected_hashes,
        require_expected_hashes=require_expected_hashes,
        artifact_semantics=artifact_semantics,
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def valid_fixture() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "component": "totem-core",
        "channel": "stable",
        "approved": True,
        "physical_homologation_passed": True,
        "powerloss_matrix_passed": True,
        "powerloss_semantics_complete": True,
        "soak_endurance_passed": True,
        "server_side_governance_passed": True,
        "release_gate_passed": True,
        "h2_readiness_passed": True,
        "explicit_operator_decision": True,
        "operator": "operator-prod-01",
        "rollback_owner": "rollback-owner-01",
        "release_gate_sha256": "a" * 64,
        "h2_readiness_sha256": "b" * 64,
        "server_side_evidence_sha256": "c" * 64,
        "server_side_trust_anchor_evidence_sha256": "f" * 64,
        "soak_summary_sha256": "d" * 64,
        "powerloss_matrix_sha256": "e" * 64,
        "auto_pull_enabled": False,
        "public_player_runtime_thaw": False,
    }


def semantic_args_fixture(root: Path) -> argparse.Namespace:
    release_gate = root / "release-gate.json"
    server_side = root / "server-side.json"
    trusted_key = root / "trusted-key.pub.pem"
    trust_anchor = root / "trust-anchor.json"
    soak = root / "soak.json"
    operator = root / "operator.json"
    write_json(release_gate, {
        "schema": RELEASE_GATE_SCHEMA,
        "passed": True,
        "repo": {"dirty": False},
    })
    write_json(server_side, {"schema": "dadooh.c18.server_side_publish_governance.v1"})
    trusted_key.write_text("PUBLIC KEY PLACEHOLDER\n", encoding="utf-8")
    write_json(trust_anchor, {"schema": "dadooh.c18.server_side_trust_anchor.v1"})
    write_json(soak, {
        "schema": SOAK_SCHEMA,
        "passed": True,
        "collection_policy": {"cycles": 24, "cycle_duration_sec": 60 * 60},
        "counters": {
            "max_panfrost_faults_delta": 0,
            "max_mmc_timeout_reset_delta": 0,
            "max_ext4_errors_delta": 0,
        },
    })
    write_json(operator, {
        "schema": THAW_DECISION_SCHEMA,
        "approved": True,
        "acknowledges_h2_evidence": True,
    })
    powerloss_dirs: list[Path] = []
    for checkpoint in REQUIRED_POWERLOSS_CHECKPOINTS:
        run_dir = root / "powerloss" / checkpoint
        write_json(run_dir / "evidence-manifest.json", {
            "schema": POWERLOSS_MANIFEST_SCHEMA,
            "checkpoint": checkpoint,
            "image_tag": "c18-hwdecode-lab-1x",
            "image_sha256": "1" * 64,
            "image_marker_sha256": "2" * 64,
        })
        powerloss_dirs.append(run_dir)
    return argparse.Namespace(
        release_gate_summary=release_gate,
        server_side_evidence=server_side,
        server_side_trusted_key_pem=[trusted_key],
        server_side_trust_anchor_evidence=trust_anchor,
        soak_summary=soak,
        powerloss_evidence_dir=powerloss_dirs,
        operator_thaw_decision=operator,
        expect_image_tag="c18-hwdecode-lab-1x",
        expect_image_sha256="1" * 64,
        expect_image_marker_sha256="2" * 64,
    )


def stable_fixture_bound_to_args(args: argparse.Namespace) -> dict[str, Any]:
    data = valid_fixture()
    data.update(expected_hashes_from_args(args))
    return data


class StablePromotionGateSelfTest(unittest.TestCase):
    def test_complete_fixture_passes(self) -> None:
        result = validate_data(valid_fixture())
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_missing_evidence_denies(self) -> None:
        result = evaluate(None)
        self.assertFalse(result["passed"])
        self.assertIn("missing_stable_promotion_evidence", result["blockers"])

    def test_minimal_approved_json_denies(self) -> None:
        result = validate_data({"schema": SCHEMA, "approved": True})
        self.assertFalse(result["passed"])
        self.assertIn("stable_promotion_component_not_totem_core", result["blockers"])
        self.assertIn("stable_promotion_h2_readiness_passed_missing_or_false", result["blockers"])

    def test_auto_pull_or_public_thaw_denies(self) -> None:
        data = valid_fixture()
        data["auto_pull_enabled"] = True
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("stable_promotion_auto_pull_enabled", result["blockers"])

        data = valid_fixture()
        data["public_player_runtime_thaw"] = True
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("stable_promotion_public_player_runtime_thaw_enabled", result["blockers"])

    def test_file_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stable.json"
            write_json(path, valid_fixture())
            result = evaluate(path)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_artifact_binding_required_when_requested(self) -> None:
        data = valid_fixture()
        result = validate_data(data, require_expected_hashes=True)
        self.assertFalse(result["passed"])
        self.assertIn("stable_promotion_expected_hashes_missing", result["blockers"])
        self.assertIn("stable_promotion_expected_hash_missing:server_side_evidence_sha256", result["blockers"])

    def test_hash_binding_denies_stale_evidence(self) -> None:
        data = valid_fixture()
        result = validate_data(
            data,
            expected_hashes={"server_side_evidence_sha256": "0" * 64},
        )
        self.assertFalse(result["passed"])
        self.assertIn("stable_promotion_server_side_evidence_sha256_mismatch", result["blockers"])

        data = valid_fixture()
        result = validate_data(
            data,
            expected_hashes={"server_side_trust_anchor_evidence_sha256": "0" * 64},
        )
        self.assertFalse(result["passed"])
        self.assertIn("stable_promotion_server_side_trust_anchor_evidence_sha256_mismatch", result["blockers"])

    def test_hash_binding_passes_when_expected_matches(self) -> None:
        data = valid_fixture()
        result = validate_data(
            data,
            expected_hashes={
                "server_side_evidence_sha256": data["server_side_evidence_sha256"],
                "server_side_trust_anchor_evidence_sha256": data["server_side_trust_anchor_evidence_sha256"],
            },
        )
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_h2_readiness_hash_is_derived_from_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            release_gate = tmp_path / "release-gate.json"
            server_side = tmp_path / "server-side.json"
            trust_anchor = tmp_path / "trust-anchor.json"
            soak = tmp_path / "soak.json"
            powerloss_dir = tmp_path / "powerloss"
            powerloss_dir.mkdir()
            write_json(release_gate, {"release": True})
            write_json(server_side, {"server_side": True})
            write_json(trust_anchor, {"trust_anchor": True})
            write_json(soak, {"duration": "24h"})
            write_json(powerloss_dir / "manifest.json", {"checkpoint": "after_current_symlink"})
            args = argparse.Namespace(
                release_gate_summary=release_gate,
                server_side_evidence=server_side,
                server_side_trust_anchor_evidence=trust_anchor,
                soak_summary=soak,
                powerloss_evidence_dir=[powerloss_dir],
                operator_thaw_decision=None,
                expect_image_tag="c18-hwdecode-lab-1x",
                expect_image_sha256="1" * 64,
                expect_image_marker_sha256="2" * 64,
            )
            hashes = expected_hashes_from_args(args)
        self.assertIn("h2_readiness_sha256", hashes)
        self.assertEqual(hashes["h2_readiness_sha256"], h2_input_bundle_sha256(args, hashes))

    def test_artifact_semantics_pass_with_real_validators_mocked_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = semantic_args_fixture(Path(tmp))
            data = stable_fixture_bound_to_args(args)
            with (
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
                mock.patch(__name__ + ".evaluate_server_side_gate", return_value={"passed": True, "blockers": []}),
            ):
                semantics = evaluate_artifact_semantics(args)
                result = validate_data(
                    data,
                    expected_hashes=expected_hashes_from_args(args),
                    require_expected_hashes=True,
                    artifact_semantics=semantics,
                )
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_hash_consistent_fake_artifacts_do_not_promote_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = semantic_args_fixture(Path(tmp))
            write_json(args.release_gate_summary, {"schema": "fake", "passed": True})
            write_json(args.server_side_evidence, {"schema": "fake", "passed": True})
            args.powerloss_evidence_dir = args.powerloss_evidence_dir[:1]
            data = stable_fixture_bound_to_args(args)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                semantics = evaluate_artifact_semantics(args)
                result = validate_data(
                    data,
                    expected_hashes=expected_hashes_from_args(args),
                    require_expected_hashes=True,
                    artifact_semantics=semantics,
                )
        self.assertFalse(result["passed"])
        self.assertIn(
            "stable_promotion_artifact_semantics:release_gate_summary:release_gate_summary_schema",
            result["blockers"],
        )
        self.assertIn(
            "stable_promotion_artifact_semantics:powerloss_matrix:powerloss_matrix_incomplete",
            result["blockers"],
        )
        self.assertTrue(
            any(blocker.startswith("stable_promotion_artifact_semantics:server_side_governance:")
                for blocker in result["blockers"])
        )

    def test_server_side_trusted_key_is_required_for_stable_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = semantic_args_fixture(Path(tmp))
            args.server_side_trusted_key_pem = []
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                semantics = evaluate_artifact_semantics(args)
        self.assertFalse(semantics["passed"])
        self.assertIn("server_side_governance:server_side_trusted_key_pem_missing", semantics["blockers"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate C18 stable promotion evidence.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--release-gate-summary", type=Path, default=None)
    parser.add_argument("--server-side-evidence", type=Path, default=None)
    parser.add_argument("--server-side-trusted-key-pem", type=Path, action="append", default=[])
    parser.add_argument("--server-side-trust-anchor-evidence", type=Path, default=None)
    parser.add_argument("--soak-summary", type=Path, default=None)
    parser.add_argument("--powerloss-evidence-dir", type=Path, action="append", default=[])
    parser.add_argument("--operator-thaw-decision", type=Path, default=None)
    parser.add_argument("--expect-image-tag", default=None)
    parser.add_argument("--expect-image-sha256", default=None)
    parser.add_argument("--expect-image-marker-sha256", default=None)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(StablePromotionGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = evaluate(
        args.evidence,
        expected_hashes=expected_hashes_from_args(args),
        require_expected_hashes=True,
        artifact_semantics=evaluate_artifact_semantics(args),
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} blockers={len(result['blockers'])}")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
