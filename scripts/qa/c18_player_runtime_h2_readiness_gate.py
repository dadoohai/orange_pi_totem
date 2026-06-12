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
import datetime as dt
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from c18_player_runtime_powerloss_evidence_gate import (
    ALL_MATRIX_CHECKPOINTS as EVIDENCE_GATE_POWERLOSS_CHECKPOINTS,
    SEMANTICALLY_VALIDATED_CHECKPOINTS as SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS,
)
from c18_stable_promotion_gate import evaluate as evaluate_stable_promotion_gate
from c18_server_side_publish_governance_gate import evaluate as evaluate_server_side_gate
from c18_server_side_publish_governance_gate import write_fixture_release as write_server_side_fixture_release
from c18_player_runtime_thaw_decision_gate import evaluate as evaluate_thaw_decision_gate


REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA = "dadooh.c18.player_runtime.h2_readiness.v1"
POWERLOSS_MANIFEST_SCHEMA = "dadooh.c18.powerloss.evidence_manifest.v1"
SOAK_SCHEMA = "dadooh.c18.playback.soak.v1"
RELEASE_GATE_SCHEMA = "dadooh.c18.ota.release_gate.v1"
STABLE_PROMOTION_SCHEMA = "dadooh.c18.stable_promotion.v1"
SERVER_SIDE_SCHEMA = "dadooh.c18.server_side_publish_governance.v1"
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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def utc_z(delta: dt.timedelta = dt.timedelta()) -> str:
    value = dt.datetime.now(dt.timezone.utc).replace(microsecond=0) + delta
    return value.isoformat().replace("+00:00", "Z")


def is_hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(ch in "0123456789abcdef" for ch in value)


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
        "expect_image_tag": args.expect_image_tag,
        "expect_image_sha256": args.expect_image_sha256,
        "expect_image_marker_sha256": args.expect_image_marker_sha256,
    }
    return sha256_json(bundle)


def stable_expected_hashes(args: argparse.Namespace) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if args.h1_release_gate_summary is not None and args.h1_release_gate_summary.is_file():
        hashes["release_gate_sha256"] = sha256_file(args.h1_release_gate_summary)
    if args.server_side_evidence is not None and args.server_side_evidence.is_file():
        hashes["server_side_evidence_sha256"] = sha256_file(args.server_side_evidence)
    trust_anchor = getattr(args, "server_side_trust_anchor_evidence", None)
    if trust_anchor is not None and trust_anchor.is_file():
        hashes["server_side_trust_anchor_evidence_sha256"] = sha256_file(trust_anchor)
    if args.soak_summary is not None and args.soak_summary.is_file():
        hashes["soak_summary_sha256"] = sha256_file(args.soak_summary)
    if args.powerloss_evidence_dir:
        hashes["powerloss_matrix_sha256"] = powerloss_matrix_sha256(list(args.powerloss_evidence_dir))
    hashes["h2_readiness_sha256"] = h2_input_bundle_sha256(args, hashes)
    return hashes


def thaw_decision_expected_hashes(args: argparse.Namespace) -> dict[str, str]:
    hashes = {
        key: value
        for key, value in stable_expected_hashes(args).items()
        if key in {
            "release_gate_sha256",
            "powerloss_matrix_sha256",
            "soak_summary_sha256",
            "server_side_evidence_sha256",
            "server_side_trust_anchor_evidence_sha256",
        }
    }
    stable = getattr(args, "stable_promotion_evidence", None)
    if stable is not None and stable.is_file():
        hashes["stable_promotion_evidence_sha256"] = sha256_file(stable)
    return hashes


def release_asset_relative_path(raw: Any) -> Path | None:
    if not isinstance(raw, str) or not raw or raw.startswith("/"):
        return None
    candidate = Path(raw)
    if ".." in candidate.parts:
        return None
    return candidate


def thaw_decision_expected_target(args: argparse.Namespace) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    target: dict[str, str] = {}
    server_side = getattr(args, "server_side_evidence", None)
    if server_side is None or not server_side.is_file():
        return target, ["thaw_decision_expected_target_server_side_missing"]
    evidence = read_json(server_side, errors, "server_side_evidence_for_thaw_target")
    assets = evidence.get("release_assets") if isinstance(evidence.get("release_assets"), dict) else {}
    manifest_rel = release_asset_relative_path(assets.get("manifest"))
    if manifest_rel is None:
        return target, errors + ["thaw_decision_expected_target_manifest_path_invalid_or_missing"]
    manifest_path = server_side.parent / manifest_rel
    if not manifest_path.is_file():
        return target, errors + ["thaw_decision_expected_target_manifest_missing"]
    manifest_errors: list[str] = []
    manifest = read_json(manifest_path, manifest_errors, "server_side_manifest_for_thaw_target")
    errors.extend(manifest_errors)
    version = manifest.get("version")
    source_commit = manifest.get("source_commit")
    payload_sha256 = manifest.get("payload_sha256")
    if isinstance(version, str) and version.strip():
        target["package_version"] = version
    else:
        errors.append("thaw_decision_expected_target_package_version_missing")
    if is_hex(source_commit, 40):
        target["source_commit"] = source_commit
    else:
        errors.append("thaw_decision_expected_target_source_commit_missing_or_invalid")
    if is_hex(payload_sha256, 64):
        target["payload_sha256"] = payload_sha256
    else:
        errors.append("thaw_decision_expected_target_payload_sha256_missing_or_invalid")
    return target, errors


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
    step_items = [item for item in steps if isinstance(item, dict)] if isinstance(steps, list) else []
    step_names = [item.get("name") for item in step_items]
    if not any(
        str(item.get("name")).startswith("c18_player_runtime_teardown_evidence:")
        and item.get("passed") is True
        for item in step_items
    ):
        blockers.append("h1_teardown_evidence_step_missing")
    if not any(
        str(item.get("name")).startswith("c18_player_runtime_data_evidence")
        and item.get("passed") is True
        for item in step_items
    ):
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


def evaluate_powerloss(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    checkpoint_dirs: dict[str, str] = {}
    gate_results: dict[str, dict[str, Any]] = {}
    duplicate_checkpoints: list[str] = []
    semantics_ledger = powerloss_semantics_ledger()
    if args.expect_image_tag is None:
        blockers.append("powerloss_expected_image_tag_required")
    if args.expect_image_sha256 is None:
        blockers.append("powerloss_expected_image_sha256_required")
    if args.expect_image_marker_sha256 is None:
        blockers.append("powerloss_expected_image_marker_sha256_required")
    if semantics_ledger["evidence_gate_contract_mismatch"]:
        blockers.append("powerloss_matrix_contract_mismatch")
    if semantics_ledger["semantics_not_implemented_checkpoints"]:
        blockers.append("powerloss_checkpoint_semantics_incomplete")
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
        semantics_ledger=semantics_ledger,
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


def evaluate_stable_promotion(path: Path | None, *, expected_hashes: dict[str, str]) -> dict[str, Any]:
    if path is None:
        return step(False, ["missing_stable_promotion_evidence"])
    result = evaluate_stable_promotion_gate(
        path,
        expected_component="player-runtime",
        expected_hashes=expected_hashes,
        require_expected_hashes=True,
    )
    blockers = list(result.get("blockers", []))
    return step(
        not blockers,
        blockers,
        evidence_path=str(path),
        gate_result=result,
        expected_hashes=expected_hashes,
    )


def evaluate_server_side(path: Path | None,
                         *,
                         allow_test_fixtures: bool = False,
                         trusted_key_pems: list[Path] | None = None,
                         trust_anchor_evidence: Path | None = None) -> dict[str, Any]:
    if path is None:
        return step(False, ["missing_server_side_publish_governance"])
    result = evaluate_server_side_gate(
        path,
        expected_component="player-runtime",
        allow_test_fixtures=allow_test_fixtures,
        trusted_key_pems=trusted_key_pems,
        trust_anchor_evidence=trust_anchor_evidence,
    )
    blockers = list(result.get("blockers", []))
    return step(not blockers, blockers, evidence_path=str(path), gate_result=result)


def evaluate_operator_decision(args: argparse.Namespace) -> dict[str, Any]:
    expected_target, target_errors = thaw_decision_expected_target(args)
    decision_sha256 = (
        sha256_file(args.operator_thaw_decision)
        if args.operator_thaw_decision is not None and args.operator_thaw_decision.is_file()
        else None
    )
    result = evaluate_thaw_decision_gate(
        args.operator_thaw_decision,
        expected_hashes=thaw_decision_expected_hashes(args),
        require_expected_hashes=True,
        expected_package_version=expected_target.get("package_version"),
        expected_source_commit=expected_target.get("source_commit"),
        expected_payload_sha256=expected_target.get("payload_sha256"),
    )
    blockers = list(result.get("blockers", []))
    if args.operator_thaw_decision is not None:
        blockers.extend(target_errors)
    return step(
        not blockers,
        blockers,
        evidence_path=str(args.operator_thaw_decision) if args.operator_thaw_decision is not None else None,
        evidence_sha256=decision_sha256,
        gate_result=result,
        expected_target=expected_target,
        expected_target_errors=target_errors,
    )


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    expected_stable_hashes = stable_expected_hashes(args)
    allow_test_fixtures = bool(getattr(args, "allow_test_fixtures", False))
    checks = {
        "h1_decisive_bundle": evaluate_h1(args.h1_release_gate_summary),
        "full_physical_powerloss_matrix": evaluate_powerloss(args),
        "soak_endurance_24h": evaluate_soak(args.soak_summary),
        "stable_promotion_authorization": evaluate_stable_promotion(
            args.stable_promotion_evidence,
            expected_hashes=expected_stable_hashes,
        ),
        "server_side_publish_governance": evaluate_server_side(
            args.server_side_evidence,
            allow_test_fixtures=allow_test_fixtures,
            trusted_key_pems=getattr(args, "server_side_trusted_key_pem", []),
            trust_anchor_evidence=getattr(args, "server_side_trust_anchor_evidence", None),
        ),
        "explicit_operator_thaw_decision": evaluate_operator_decision(args),
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
            {"name": "c18_player_runtime_data_evidence", "passed": True},
            {"name": "c18_player_runtime_teardown_evidence:1", "passed": True},
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
    server = write_server_side_fixture_release(root / "server-side-release", component="player-runtime")
    trust_anchor = root / "server-side-trust-anchor.json"
    write_json(trust_anchor, {
        "schema": "dadooh.c18.server_side_trust_anchor.v1",
        "purpose": "c18_server_side_release_signing",
        "trusted_key_spki_sha256": "f" * 64,
        "public_key_algorithm": "rsa",
        "signature_algorithm": "openssl-dgst-sha256-rsa-pkcs1-v1_5",
        "scope": {
            "components": ["totem-core", "player-runtime"],
            "channels": ["homologation", "stable"],
        },
        "selected_by": "operator-release-01",
        "key_owner": "release-security-01",
        "selected_at_utc": "2026-06-12T00:00:00Z",
        "private_key_material_present": False,
        "non_claims": [
            "this_evidence_does_not_assert_pki_chain",
            "this_evidence_does_not_publish_releases",
            "this_evidence_does_not_enable_auto_pull",
            "this_evidence_does_not_promote_stable",
            "this_evidence_does_not_thaw_player_runtime",
        ],
    })
    dirs = [fixture_manifest(root / "powerloss", checkpoint) for checkpoint in REQUIRED_POWERLOSS_CHECKPOINTS]
    stable = root / "stable.json"
    operator = root / "operator.json"
    args = argparse.Namespace(
        h1_release_gate_summary=h1,
        powerloss_evidence_dir=dirs,
        soak_summary=soak,
        stable_promotion_evidence=stable,
        server_side_evidence=server,
        server_side_trust_anchor_evidence=trust_anchor,
        operator_thaw_decision=operator,
        expect_image_tag="c18-hwdecode-lab-test",
        expect_image_sha256="a" * 64,
        expect_image_marker_sha256="b" * 64,
        allow_test_fixtures=True,
        server_side_trusted_key_pem=[],
    )
    hashes = stable_expected_hashes(args)
    target, target_errors = thaw_decision_expected_target(args)
    if target_errors:
        raise AssertionError(f"fixture target metadata errors: {target_errors}")
    write_json(stable, {
        "schema": STABLE_PROMOTION_SCHEMA,
        "component": "player-runtime",
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
        "release_gate_sha256": hashes["release_gate_sha256"],
        "h2_readiness_sha256": hashes["h2_readiness_sha256"],
        "server_side_evidence_sha256": hashes["server_side_evidence_sha256"],
        "server_side_trust_anchor_evidence_sha256": hashes["server_side_trust_anchor_evidence_sha256"],
        "soak_summary_sha256": hashes["soak_summary_sha256"],
        "powerloss_matrix_sha256": hashes["powerloss_matrix_sha256"],
        "auto_pull_enabled": False,
        "public_player_runtime_thaw": False,
    })
    write_json(operator, {
        "schema": "dadooh.c18.player_runtime.thaw_decision.v1",
        "component": "player-runtime",
        "channel": "stable",
        "approved": True,
        "acknowledges_h2_evidence": True,
        "explicit_operator_decision": True,
        "rollback_ready": True,
        "auto_pull_enabled": False,
        "thaw_execution_performed": False,
        "operator": "operator-prod-01",
        "rollback_owner": "rollback-owner-01",
        "target_package_version": target["package_version"],
        "target_source_commit": target["source_commit"],
        "target_payload_sha256": target["payload_sha256"],
        **thaw_decision_expected_hashes(args),
        "window": {
            "start_utc": utc_z(dt.timedelta(minutes=-30)),
            "end_utc": utc_z(dt.timedelta(minutes=30)),
        },
        "non_claims": [
            "this_decision_does_not_execute_thaw",
            "this_decision_does_not_publish_releases",
            "this_decision_does_not_enable_auto_pull",
            "this_decision_does_not_override_freeze_rc_44_by_itself",
            "this_decision_requires_h2_green",
        ],
    })
    return args


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
            with (
                mock.patch(__name__ + ".SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS", set(REQUIRED_POWERLOSS_CHECKPOINTS)),
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
            ):
                result = evaluate(args)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_incomplete_powerloss_semantics_denies_even_with_all_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            incomplete = set(REQUIRED_POWERLOSS_CHECKPOINTS) - {"after_extract"}
            with (
                mock.patch(__name__ + ".SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS", incomplete),
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
            ):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn(
            "full_physical_powerloss_matrix:powerloss_checkpoint_semantics_incomplete",
            result["blockers"],
        )
        ledger = result["checks"]["full_physical_powerloss_matrix"]["semantics_ledger"]
        self.assertIn("after_extract", ledger["semantics_not_implemented_checkpoints"])
        self.assertIn("rollback_after_current_to_previous", ledger["semantically_validated_checkpoints"])

    def test_missing_one_powerloss_checkpoint_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            args.powerloss_evidence_dir = args.powerloss_evidence_dir[:-1]
            with (
                mock.patch(__name__ + ".SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS", set(REQUIRED_POWERLOSS_CHECKPOINTS)),
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
            ):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn("full_physical_powerloss_matrix:powerloss_matrix_incomplete", result["blockers"])

    def test_powerloss_image_expectations_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            args.expect_image_tag = None
            args.expect_image_sha256 = None
            args.expect_image_marker_sha256 = None
            with (
                mock.patch(__name__ + ".SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS", set(REQUIRED_POWERLOSS_CHECKPOINTS)),
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
            ):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn("full_physical_powerloss_matrix:powerloss_expected_image_tag_required", result["blockers"])
        self.assertIn("full_physical_powerloss_matrix:powerloss_expected_image_sha256_required", result["blockers"])
        self.assertIn("full_physical_powerloss_matrix:powerloss_expected_image_marker_sha256_required", result["blockers"])

    def test_h1_failed_decisive_steps_deny(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            h1 = json.loads(args.h1_release_gate_summary.read_text(encoding="utf-8"))
            for item in h1["steps"]:
                item["passed"] = False
            write_json(args.h1_release_gate_summary, h1)
            with (
                mock.patch(__name__ + ".SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS", set(REQUIRED_POWERLOSS_CHECKPOINTS)),
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
            ):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn("h1_decisive_bundle:h1_teardown_evidence_step_missing", result["blockers"])
        self.assertIn("h1_decisive_bundle:h1_data_evidence_step_missing", result["blockers"])

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
            with (
                mock.patch(__name__ + ".SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS", set(REQUIRED_POWERLOSS_CHECKPOINTS)),
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
            ):
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
            with (
                mock.patch(__name__ + ".SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS", set(REQUIRED_POWERLOSS_CHECKPOINTS)),
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
            ):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn(
            "server_side_publish_governance:server_side_signature_or_attestation_present_missing_or_false",
            result["blockers"],
        )

    def test_totem_core_server_side_evidence_cannot_satisfy_player_runtime_h2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = complete_args(root)
            args.server_side_evidence = write_server_side_fixture_release(
                root / "totem-core-server-side-release",
                component="totem-core",
            )
            stable = json.loads(args.stable_promotion_evidence.read_text(encoding="utf-8"))
            stable.update(stable_expected_hashes(args))
            write_json(args.stable_promotion_evidence, stable)
            with (
                mock.patch(__name__ + ".SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS", set(REQUIRED_POWERLOSS_CHECKPOINTS)),
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
            ):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn(
            "server_side_publish_governance:server_side_manifest_component_expected_mismatch",
            result["blockers"],
        )
        self.assertIn(
            "server_side_publish_governance:server_side_publish_gate_tool",
            result["blockers"],
        )

    def test_stable_promotion_hashes_must_match_current_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            stable = json.loads(args.stable_promotion_evidence.read_text(encoding="utf-8"))
            stable["server_side_evidence_sha256"] = "0" * 64
            write_json(args.stable_promotion_evidence, stable)
            with (
                mock.patch(__name__ + ".SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS", set(REQUIRED_POWERLOSS_CHECKPOINTS)),
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
            ):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn(
            "stable_promotion_authorization:stable_promotion_server_side_evidence_sha256_mismatch",
            result["blockers"],
        )

        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            stable = json.loads(args.stable_promotion_evidence.read_text(encoding="utf-8"))
            stable["server_side_trust_anchor_evidence_sha256"] = "0" * 64
            write_json(args.stable_promotion_evidence, stable)
            with (
                mock.patch(__name__ + ".SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS", set(REQUIRED_POWERLOSS_CHECKPOINTS)),
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
            ):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn(
            "stable_promotion_authorization:stable_promotion_server_side_trust_anchor_evidence_sha256_mismatch",
            result["blockers"],
        )

    def test_operator_thaw_target_must_match_server_side_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            operator = json.loads(args.operator_thaw_decision.read_text(encoding="utf-8"))
            operator["target_payload_sha256"] = "0" * 64
            write_json(args.operator_thaw_decision, operator)
            with (
                mock.patch(__name__ + ".SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS", set(REQUIRED_POWERLOSS_CHECKPOINTS)),
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
            ):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn(
            "explicit_operator_thaw_decision:thaw_decision_target_payload_sha256_mismatch",
            result["blockers"],
        )

    def test_totem_core_stable_evidence_cannot_satisfy_player_runtime_h2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            stable = json.loads(args.stable_promotion_evidence.read_text(encoding="utf-8"))
            stable["component"] = "totem-core"
            write_json(args.stable_promotion_evidence, stable)
            with (
                mock.patch(__name__ + ".SEMANTICALLY_VALIDATED_POWERLOSS_CHECKPOINTS", set(REQUIRED_POWERLOSS_CHECKPOINTS)),
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
            ):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn(
            "stable_promotion_authorization:stable_promotion_component_not_player_runtime",
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
    parser.add_argument("--server-side-trusted-key-pem", type=Path, action="append", default=[])
    parser.add_argument("--server-side-trust-anchor-evidence", type=Path, default=None)
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
