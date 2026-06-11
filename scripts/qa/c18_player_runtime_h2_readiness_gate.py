#!/usr/bin/env python3
"""Default-deny H2 readiness evaluator for C18 player-runtime thaw.

This is an offline governance gate, not a thaw switch. It aggregates the
evidence families that must exist before a public player-runtime thaw can be
considered: H1 decisive release evidence, the full physical power-loss matrix,
long soak, server-side publish/signature governance, stable-promotion approval,
and an explicit operator thaw decision. Missing evidence is a blocker.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA = "dadooh.c18.player_runtime.h2_readiness.v1"
POWERLOSS_MANIFEST_SCHEMA = "dadooh.c18.powerloss.evidence_manifest.v1"
SOAK_SCHEMA = "dadooh.c18.playback.soak.v1"
RELEASE_GATE_SCHEMA = "dadooh.c18.ota.release_gate.v1"
STABLE_PROMOTION_SCHEMA = "dadooh.c18.stable_promotion.v1"
SERVER_SIDE_SCHEMA = "dadooh.c18.server_side_publish_governance.v1"
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

NON_CLAIMS = (
    "this_gate_does_not_thaw_player_runtime",
    "this_gate_does_not_publish_or_fetch_releases",
    "this_gate_does_not_override_freeze_rc_44",
    "this_gate_does_not_promote_stable_without_operator_decision",
)


def read_json(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{label}_json_error:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{label}_not_object")
        return {}
    return data


def bool_field(data: dict[str, Any], key: str) -> bool:
    return data.get(key) is True


def step(passed: bool, blockers: list[str], **details: Any) -> dict[str, Any]:
    return {
        "passed": passed,
        "blockers": blockers,
        **details,
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
        "stdout_tail": proc.stdout[-800:],
        "stderr_tail": proc.stderr[-800:],
        "gate": payload,
    }


def evaluate_h1(summary_path: Path | None) -> dict[str, Any]:
    blockers: list[str] = []
    if summary_path is None:
        return step(False, ["missing_h1_decisive_release_gate_summary"])
    errors: list[str] = []
    summary = read_json(summary_path, errors, "h1_release_gate_summary")
    blockers.extend(errors)
    if summary.get("schema") != RELEASE_GATE_SCHEMA:
        blockers.append("h1_release_gate_schema")
    if summary.get("passed") is not True:
        blockers.append("h1_release_gate_not_passed")
    data_evidence = summary.get("player_runtime_data_evidence")
    if not isinstance(data_evidence, dict):
        blockers.append("h1_player_runtime_data_evidence_missing")
    else:
        if data_evidence.get("mode") != "decisive":
            blockers.append("h1_player_runtime_data_evidence_not_decisive")
        if data_evidence.get("status") != "passed":
            blockers.append("h1_player_runtime_data_evidence_not_passed")
    steps = summary.get("steps")
    step_names = [item.get("name") for item in steps if isinstance(item, dict)] if isinstance(steps, list) else []
    if not any(str(name).startswith("c18_player_runtime_teardown_evidence:") for name in step_names):
        blockers.append("h1_teardown_evidence_step_missing")
    if not any(str(name).startswith("c18_player_runtime_data_evidence") for name in step_names):
        blockers.append("h1_data_evidence_step_missing")
    return step(not blockers, blockers, summary_path=str(summary_path), step_count=len(step_names))


def manifest_image_errors(
    manifest: dict[str, Any],
    *,
    expect_image_tag: str | None,
    expect_image_sha256: str | None,
    expect_image_marker_sha256: str | None,
) -> list[str]:
    errors: list[str] = []
    if expect_image_tag is not None:
        if manifest.get("image_tag") != expect_image_tag:
            errors.append("powerloss_image_tag_mismatch_or_missing")
    if expect_image_sha256 is not None:
        if manifest.get("image_sha256") != expect_image_sha256:
            errors.append("powerloss_image_sha256_mismatch_or_missing")
    if expect_image_marker_sha256 is not None:
        if manifest.get("image_marker_sha256") != expect_image_marker_sha256:
            errors.append("powerloss_image_marker_sha256_mismatch_or_missing")
    return errors


def evaluate_powerloss(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    checkpoint_dirs: dict[str, str] = {}
    gate_results: dict[str, dict[str, Any]] = {}
    duplicate_checkpoints: list[str] = []
    for run_dir in args.powerloss_evidence_dir or []:
        errors: list[str] = []
        manifest = read_json(run_dir / "evidence-manifest.json", errors, f"{run_dir.name}_manifest")
        checkpoint = manifest.get("checkpoint")
        if manifest.get("schema") != POWERLOSS_MANIFEST_SCHEMA:
            errors.append("powerloss_manifest_schema")
        if not isinstance(checkpoint, str) or not checkpoint:
            errors.append("powerloss_manifest_checkpoint_missing")
            checkpoint = f"unknown:{run_dir.name}"
        if checkpoint in checkpoint_dirs:
            duplicate_checkpoints.append(str(checkpoint))
        checkpoint_dirs[str(checkpoint)] = str(run_dir)
        errors.extend(
            manifest_image_errors(
                manifest,
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
        required_checkpoints=list(REQUIRED_POWERLOSS_CHECKPOINTS),
        observed_checkpoints=sorted(checkpoint_dirs),
        missing_checkpoints=missing,
        extra_checkpoints=extra,
        duplicate_checkpoints=sorted(set(duplicate_checkpoints)),
        gate_results=gate_results,
    )


def soak_total_duration(summary: dict[str, Any]) -> float:
    policy = summary.get("collection_policy")
    counters = summary.get("counters")
    if isinstance(policy, dict):
        try:
            cycles = float(policy.get("cycles", 0))
            duration = float(policy.get("cycle_duration_sec", 0))
            return cycles * duration
        except Exception:
            return 0.0
    if isinstance(counters, dict):
        try:
            return float(counters.get("duration_sec", 0))
        except Exception:
            return 0.0
    return 0.0


def evaluate_soak(summary_path: Path | None) -> dict[str, Any]:
    blockers: list[str] = []
    if summary_path is None:
        return step(False, ["missing_24h_soak_summary"])
    errors: list[str] = []
    summary = read_json(summary_path, errors, "soak_summary")
    blockers.extend(errors)
    if summary.get("schema") != SOAK_SCHEMA:
        blockers.append("soak_schema")
    if summary.get("passed") is not True:
        blockers.append("soak_not_passed")
    duration = soak_total_duration(summary)
    if duration < MIN_SOAK_DURATION_SEC:
        blockers.append("soak_duration_below_24h")
    counters = summary.get("counters") if isinstance(summary.get("counters"), dict) else {}
    for key in ("max_panfrost_faults_delta", "max_mmc_timeout_reset_delta", "max_ext4_errors_delta"):
        if counters.get(key) not in (0, 0.0):
            blockers.append(f"soak_{key}_nonzero_or_missing")
    return step(not blockers, blockers, summary_path=str(summary_path), duration_sec=duration)


def evaluate_stable_promotion(path: Path | None) -> dict[str, Any]:
    blockers: list[str] = []
    if path is None:
        return step(False, ["missing_stable_promotion_evidence"])
    errors: list[str] = []
    data = read_json(path, errors, "stable_promotion_evidence")
    blockers.extend(errors)
    if data.get("schema") != STABLE_PROMOTION_SCHEMA:
        blockers.append("stable_promotion_schema")
    if data.get("approved") is not True:
        blockers.append("stable_promotion_not_approved")
    for key in ("physical_homologation_passed", "powerloss_matrix_passed", "soak_endurance_passed", "server_side_governance_passed"):
        if data.get(key) is not True:
            blockers.append(f"stable_promotion_{key}_missing_or_false")
    return step(not blockers, blockers, evidence_path=str(path))


def evaluate_server_side(path: Path | None) -> dict[str, Any]:
    blockers: list[str] = []
    if path is None:
        return step(False, ["missing_server_side_publish_governance"])
    errors: list[str] = []
    data = read_json(path, errors, "server_side_publish_governance")
    blockers.extend(errors)
    if data.get("schema") != SERVER_SIDE_SCHEMA:
        blockers.append("server_side_schema")
    for key in ("publish_gate_enforced", "release_assets_verified", "signature_or_attestation_present", "auto_pull_policy_defined"):
        if data.get(key) is not True:
            blockers.append(f"server_side_{key}_missing_or_false")
    return step(not blockers, blockers, evidence_path=str(path))


def evaluate_operator_decision(path: Path | None) -> dict[str, Any]:
    blockers: list[str] = []
    if path is None:
        return step(False, ["missing_operator_thaw_decision"])
    errors: list[str] = []
    data = read_json(path, errors, "operator_thaw_decision")
    blockers.extend(errors)
    if data.get("schema") != THAW_DECISION_SCHEMA:
        blockers.append("operator_thaw_decision_schema")
    if data.get("approved") is not True:
        blockers.append("operator_thaw_decision_not_approved")
    if data.get("acknowledges_h2_evidence") is not True:
        blockers.append("operator_thaw_decision_missing_h2_ack")
    return step(not blockers, blockers, evidence_path=str(path))


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    checks = {
        "h1_decisive_bundle": evaluate_h1(args.h1_release_gate_summary),
        "full_physical_powerloss_matrix": evaluate_powerloss(args),
        "soak_endurance_24h": evaluate_soak(args.soak_summary),
        "stable_promotion_authorization": evaluate_stable_promotion(args.stable_promotion_evidence),
        "server_side_publish_governance": evaluate_server_side(args.server_side_evidence),
        "explicit_operator_thaw_decision": evaluate_operator_decision(args.operator_thaw_decision),
    }
    blockers = [
        f"{name}:{blocker}"
        for name, result in checks.items()
        for blocker in result.get("blockers", [])
    ]
    return {
        "schema": SCHEMA,
        "passed": not blockers,
        "result_claim": "h2_readiness_all_required_evidence_present" if not blockers else "h2_readiness_blocked",
        "checks": checks,
        "blockers": blockers,
        "non_claims": list(NON_CLAIMS),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fixture_manifest(root: Path, checkpoint: str) -> Path:
    run_dir = root / checkpoint
    run_dir.mkdir(parents=True)
    write_json(run_dir / "evidence-manifest.json", {
        "schema": POWERLOSS_MANIFEST_SCHEMA,
        "component": "player-runtime",
        "checkpoint": checkpoint,
        "image_tag": "c18-hwdecode-lab-test",
        "image_sha256": "a" * 64,
        "image_marker_sha256": "b" * 64,
        "source_commit": "c" * 40,
        "files": [],
    })
    return run_dir


def complete_args(root: Path) -> argparse.Namespace:
    h1 = root / "release-gate.json"
    write_json(h1, {
        "schema": RELEASE_GATE_SCHEMA,
        "passed": True,
        "player_runtime_data_evidence": {"mode": "decisive", "status": "passed"},
        "steps": [
            {"name": "c18_player_runtime_data_evidence"},
            {"name": "c18_player_runtime_teardown_evidence:1"},
        ],
    })
    soak = root / "soak-summary.json"
    write_json(soak, {
        "schema": SOAK_SCHEMA,
        "passed": True,
        "collection_policy": {"cycles": 24, "cycle_duration_sec": 3600},
        "counters": {
            "max_panfrost_faults_delta": 0,
            "max_mmc_timeout_reset_delta": 0,
            "max_ext4_errors_delta": 0,
        },
    })
    stable = root / "stable.json"
    write_json(stable, {
        "schema": STABLE_PROMOTION_SCHEMA,
        "approved": True,
        "physical_homologation_passed": True,
        "powerloss_matrix_passed": True,
        "soak_endurance_passed": True,
        "server_side_governance_passed": True,
    })
    server = root / "server.json"
    write_json(server, {
        "schema": SERVER_SIDE_SCHEMA,
        "publish_gate_enforced": True,
        "release_assets_verified": True,
        "signature_or_attestation_present": True,
        "auto_pull_policy_defined": True,
    })
    operator = root / "operator.json"
    write_json(operator, {
        "schema": THAW_DECISION_SCHEMA,
        "approved": True,
        "acknowledges_h2_evidence": True,
    })
    dirs = [fixture_manifest(root / "powerloss", checkpoint) for checkpoint in REQUIRED_POWERLOSS_CHECKPOINTS]
    return argparse.Namespace(
        h1_release_gate_summary=h1,
        powerloss_evidence_dir=dirs,
        soak_summary=soak,
        stable_promotion_evidence=stable,
        server_side_evidence=server,
        operator_thaw_decision=operator,
        expect_image_tag="c18-hwdecode-lab-test",
        expect_image_sha256="a" * 64,
        expect_image_marker_sha256="b" * 64,
    )


class H2ReadinessGateSelfTest(unittest.TestCase):
    def test_default_denies_every_required_family(self) -> None:
        args = argparse.Namespace(
            h1_release_gate_summary=None,
            powerloss_evidence_dir=[],
            soak_summary=None,
            stable_promotion_evidence=None,
            server_side_evidence=None,
            operator_thaw_decision=None,
            expect_image_tag=None,
            expect_image_sha256=None,
            expect_image_marker_sha256=None,
        )
        result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn("explicit_operator_thaw_decision:missing_operator_thaw_decision", result["blockers"])
        self.assertIn("this_gate_does_not_thaw_player_runtime", result["non_claims"])

    def test_complete_fixture_passes_when_each_powerloss_dir_gate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_missing_one_powerloss_checkpoint_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            args.powerloss_evidence_dir = args.powerloss_evidence_dir[:-1]
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn("full_physical_powerloss_matrix:powerloss_matrix_incomplete", result["blockers"])

    def test_short_soak_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            write_json(args.soak_summary, {
                "schema": SOAK_SCHEMA,
                "passed": True,
                "collection_policy": {"cycles": 1, "cycle_duration_sec": 300},
                "counters": {
                    "max_panfrost_faults_delta": 0,
                    "max_mmc_timeout_reset_delta": 0,
                    "max_ext4_errors_delta": 0,
                },
            })
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn("soak_endurance_24h:soak_duration_below_24h", result["blockers"])

    def test_hash_only_server_side_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            write_json(args.server_side_evidence, {
                "schema": SERVER_SIDE_SCHEMA,
                "publish_gate_enforced": True,
                "release_assets_verified": True,
                "signature_or_attestation_present": False,
                "auto_pull_policy_defined": True,
            })
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn(
            "server_side_publish_governance:server_side_signature_or_attestation_present_missing_or_false",
            result["blockers"],
        )

    def test_failed_powerloss_subgate_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": False, "returncode": 1, "stderr_tail": "bad"}):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertTrue(any(blocker.endswith(":powerloss_gate_failed") for blocker in result["blockers"]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate C18 player-runtime H2 public-thaw readiness.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--h1-release-gate-summary", type=Path, default=None)
    parser.add_argument("--powerloss-evidence-dir", type=Path, action="append", default=[])
    parser.add_argument("--soak-summary", type=Path, default=None)
    parser.add_argument("--stable-promotion-evidence", type=Path, default=None)
    parser.add_argument("--server-side-evidence", type=Path, default=None)
    parser.add_argument("--operator-thaw-decision", type=Path, default=None)
    parser.add_argument("--expect-image-tag", default=None)
    parser.add_argument("--expect-image-sha256", default=None)
    parser.add_argument("--expect-image-marker-sha256", default=None)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(H2ReadinessGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = evaluate(args)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} blockers={len(result['blockers'])}")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
