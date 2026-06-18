#!/usr/bin/env python3
"""Default-deny C18 stable promotion evidence gate.

This gate validates the evidence file required before a C18 `stable` release can
be built or published. It does not publish, enable auto-pull, promote by itself,
or thaw player-runtime.
"""

from __future__ import annotations

import argparse
import datetime as dt
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
from c18_player_runtime_thaw_decision_gate import evaluate as evaluate_thaw_decision_gate
from c18_server_side_publish_governance_gate import evaluate as evaluate_server_side_gate
from c18_server_side_publish_governance_gate import write_fixture_release as write_server_side_fixture_release
from c18_server_side_rollout_state_gate import validate_rollout_state


SCHEMA = "dadooh.c18.stable_promotion.v1"
GATE_SCHEMA = "dadooh.c18.stable_promotion_gate.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_GATE_SCHEMA = "dadooh.c18.ota.release_gate.v1"
PLAYER_RUNTIME_RELEASE_GATE_SCHEMA = "dadooh.c18.player_runtime.release_gate.v1"
SERVER_SIDE_CURRENT_SCHEMA = "dadooh.c18.server_side_current_validation_snapshot.v1"
SERVER_SIDE_GATE_SCHEMA = "dadooh.c18.server_side_publish_governance_gate.v1"
SERVER_SIDE_ASSET_LIST_SCHEMA = "dadooh.c18.server_side_publish_asset_list.v1"
STABLE_PROMOTION_COMPONENTS = ("totem-core", "player-runtime")
RELEASE_GATE_SCHEMA_BY_COMPONENT = {
    "totem-core": RELEASE_GATE_SCHEMA,
    "player-runtime": PLAYER_RUNTIME_RELEASE_GATE_SCHEMA,
}
SOAK_SCHEMA = "dadooh.c18.playback.soak.v1"
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
    "h1_release_gate_sha256",
    "release_gate_sha256",
    "h2_readiness_sha256",
    "server_side_evidence_sha256",
    "server_side_current_snapshot_sha256",
    "server_side_trust_anchor_evidence_sha256",
    "soak_summary_sha256",
    "powerloss_matrix_sha256",
)
NON_CLAIMS = (
    "this_gate_does_not_publish_releases",
    "this_gate_does_not_enable_auto_pull",
    "this_gate_does_not_thaw_player_runtime",
)
REQUIRED_SERVER_SIDE_CURRENT_FILES = (
    "README.md",
    "server-side-governance-gate.json",
    "server-side-asset-list.json",
    "server-side-rollout-state.json",
    "server-side-rollout-state-gate.json",
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


def is_git_sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def component_blocker(expected_component: str) -> str:
    return f"stable_promotion_component_not_{expected_component.replace('-', '_')}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def directory_tree_sha256(root: Path) -> str:
    entries: list[dict[str, Any]] = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
        entries.append({
            "file": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return sha256_json(entries)


def repo_rel(path: Path) -> str | None:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return None


def server_side_asset_base(run_dir: Path) -> Path:
    try:
        run_dir.resolve(strict=False).relative_to(REPO_ROOT.resolve())
    except ValueError:
        return run_dir.parent
    return REPO_ROOT


def validate_server_side_current_asset_records(run_dir: Path, asset_records: list[Any], blockers: list[str]) -> None:
    base = server_side_asset_base(run_dir)
    for index, item in enumerate(asset_records):
        if not isinstance(item, dict):
            blockers.append(f"server_side_current_asset_record_not_object:{index}")
            continue
        raw_path = item.get("path")
        if (
            not isinstance(raw_path, str)
            or not raw_path
            or raw_path.startswith("/")
            or ".." in Path(raw_path).parts
        ):
            blockers.append(f"server_side_current_asset_record_path_invalid:{index}")
            continue
        path = base / raw_path
        if path.is_symlink() or not path.is_file():
            blockers.append(f"server_side_current_asset_missing_or_symlink:{raw_path}")
            continue
        if item.get("bytes") != path.stat().st_size:
            blockers.append(f"server_side_current_asset_bytes_mismatch:{raw_path}")
        if item.get("sha256") != sha256_file(path):
            blockers.append(f"server_side_current_asset_sha256_mismatch:{raw_path}")


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
        "h1_release_gate_sha256": evidence_hashes.get("h1_release_gate_sha256"),
        "release_gate_sha256": evidence_hashes.get("release_gate_sha256"),
        "powerloss_matrix_sha256": evidence_hashes.get("powerloss_matrix_sha256"),
        "server_side_evidence_sha256": evidence_hashes.get("server_side_evidence_sha256"),
        "server_side_current_snapshot_sha256": evidence_hashes.get("server_side_current_snapshot_sha256"),
        "server_side_trust_anchor_evidence_sha256": evidence_hashes.get("server_side_trust_anchor_evidence_sha256"),
        "soak_summary_sha256": evidence_hashes.get("soak_summary_sha256"),
        "expect_image_tag": args.expect_image_tag,
        "expect_image_sha256": args.expect_image_sha256,
        "expect_image_marker_sha256": args.expect_image_marker_sha256,
    }
    return sha256_json(bundle)


def expected_hashes_from_args(args: argparse.Namespace) -> dict[str, str]:
    hashes: dict[str, str] = {}
    h1_release_gate = getattr(args, "h1_release_gate_summary", None)
    if h1_release_gate is not None and h1_release_gate.is_file():
        hashes["h1_release_gate_sha256"] = sha256_file(h1_release_gate)
    if args.release_gate_summary is not None and args.release_gate_summary.is_file():
        hashes["release_gate_sha256"] = sha256_file(args.release_gate_summary)
    if args.server_side_evidence is not None and args.server_side_evidence.is_file():
        hashes["server_side_evidence_sha256"] = sha256_file(args.server_side_evidence)
    server_side_current = getattr(args, "server_side_current_dir", None)
    if server_side_current is not None and server_side_current.is_dir():
        hashes["server_side_current_snapshot_sha256"] = directory_tree_sha256(server_side_current)
    trust_anchor = getattr(args, "server_side_trust_anchor_evidence", None)
    if trust_anchor is not None and trust_anchor.is_file():
        hashes["server_side_trust_anchor_evidence_sha256"] = sha256_file(trust_anchor)
    if args.soak_summary is not None and args.soak_summary.is_file():
        hashes["soak_summary_sha256"] = sha256_file(args.soak_summary)
    if args.powerloss_evidence_dir:
        hashes["powerloss_matrix_sha256"] = powerloss_matrix_sha256(list(args.powerloss_evidence_dir))
    if {
        "h1_release_gate_sha256",
        "release_gate_sha256",
        "server_side_evidence_sha256",
        "server_side_current_snapshot_sha256",
        "server_side_trust_anchor_evidence_sha256",
        "soak_summary_sha256",
        "powerloss_matrix_sha256",
    }.issubset(hashes):
        hashes["h2_readiness_sha256"] = h2_input_bundle_sha256(args, hashes)
    return hashes


def thaw_decision_expected_hashes_from_args(args: argparse.Namespace) -> dict[str, str]:
    hashes = {
        key: value
        for key, value in expected_hashes_from_args(args).items()
        if key in {
            "release_gate_sha256",
            "h1_release_gate_sha256",
            "powerloss_matrix_sha256",
            "soak_summary_sha256",
            "server_side_evidence_sha256",
            "server_side_current_snapshot_sha256",
            "server_side_trust_anchor_evidence_sha256",
        }
    }
    stable = getattr(args, "evidence", None)
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


def thaw_decision_expected_target_from_args(args: argparse.Namespace) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    target: dict[str, str] = {}
    server_side = getattr(args, "server_side_evidence", None)
    if server_side is None or not server_side.is_file():
        return target, ["thaw_decision_expected_target_server_side_missing"]
    evidence, read_errors = read_json(server_side)
    errors.extend(f"server_side_evidence_for_thaw_target_{error}" for error in read_errors)
    assets = evidence.get("release_assets") if isinstance(evidence.get("release_assets"), dict) else {}
    manifest_rel = release_asset_relative_path(assets.get("manifest"))
    if manifest_rel is None:
        return target, errors + ["thaw_decision_expected_target_manifest_path_invalid_or_missing"]
    manifest_path = server_side.parent / manifest_rel
    if not manifest_path.is_file():
        return target, errors + ["thaw_decision_expected_target_manifest_missing"]
    manifest, manifest_errors = read_json(manifest_path)
    errors.extend(f"server_side_manifest_for_thaw_target_{error}" for error in manifest_errors)
    version = manifest.get("version")
    source_commit = manifest.get("source_commit")
    payload_sha256 = manifest.get("payload_sha256")
    if isinstance(version, str) and version.strip():
        target["package_version"] = version
    else:
        errors.append("thaw_decision_expected_target_package_version_missing")
    if is_git_sha(source_commit):
        target["source_commit"] = source_commit
    else:
        errors.append("thaw_decision_expected_target_source_commit_missing_or_invalid")
    if is_sha256(payload_sha256):
        target["payload_sha256"] = payload_sha256
    else:
        errors.append("thaw_decision_expected_target_payload_sha256_missing_or_invalid")
    return target, errors


def read_artifact(path: Path | None, label: str) -> tuple[dict[str, Any], list[str]]:
    if path is None:
        return {}, [f"{label}_missing"]
    return read_json(path)


def evaluate_release_gate_summary(path: Path | None, *, expected_component: str = "totem-core") -> dict[str, Any]:
    data, errors = read_artifact(path, "release_gate_summary")
    blockers = list(errors)
    if not errors:
        expected_schema = RELEASE_GATE_SCHEMA_BY_COMPONENT.get(expected_component)
        if expected_schema is None:
            blockers.append("release_gate_summary_expected_component_invalid")
        elif data.get("schema") != expected_schema:
            blockers.append("release_gate_summary_schema")
        if data.get("passed") is not True:
            blockers.append("release_gate_summary_not_passed")
        repo = data.get("repo") if isinstance(data.get("repo"), dict) else {}
        if repo.get("dirty") is True:
            blockers.append("release_gate_summary_repo_dirty")
    return step(not blockers, blockers, evidence_path=str(path) if path is not None else None)


def evaluate_h1_release_gate_summary(path: Path | None) -> dict[str, Any]:
    data, errors = read_artifact(path, "h1_release_gate_summary")
    blockers = list(errors)
    if not errors:
        if data.get("schema") != RELEASE_GATE_SCHEMA:
            blockers.append("h1_release_gate_summary_schema")
        if data.get("passed") is not True:
            blockers.append("h1_release_gate_summary_not_passed")
        repo = data.get("repo") if isinstance(data.get("repo"), dict) else {}
        if repo.get("dirty") is True:
            blockers.append("h1_release_gate_summary_repo_dirty")
        evidence = data.get("player_runtime_data_evidence")
        if not isinstance(evidence, dict):
            blockers.append("h1_release_gate_summary_player_runtime_data_missing")
        else:
            if evidence.get("mode") != "decisive":
                blockers.append("h1_release_gate_summary_player_runtime_data_not_decisive")
            if evidence.get("status") != "passed":
                blockers.append("h1_release_gate_summary_player_runtime_data_not_passed")
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
    expect_payload_sha256: str | None,
) -> list[str]:
    errors: list[str] = []
    if expect_payload_sha256 is None:
        errors.append("powerloss_expected_payload_sha256_required")
    elif manifest.get("target_payload_sha256") != expect_payload_sha256:
        errors.append("powerloss_target_payload_sha256_mismatch_or_missing")
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
    expected_target, target_errors = thaw_decision_expected_target_from_args(args)
    expected_payload_sha256 = expected_target.get("payload_sha256")
    blockers.extend(f"powerloss_expected_target:{error}" for error in target_errors)
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
                expect_payload_sha256=expected_payload_sha256,
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


def evaluate_server_side_artifact(args: argparse.Namespace, *, expected_component: str = "totem-core") -> dict[str, Any]:
    if args.server_side_evidence is None:
        return step(False, ["server_side_evidence_missing"])
    trusted_keys = list(getattr(args, "server_side_trusted_key_pem", []) or [])
    if not trusted_keys:
        return step(False, ["server_side_trusted_key_pem_missing"], evidence_path=str(args.server_side_evidence))
    result = evaluate_server_side_gate(
        args.server_side_evidence,
        expected_component=expected_component,
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


def evaluate_server_side_current_snapshot(args: argparse.Namespace, *, expected_component: str = "totem-core") -> dict[str, Any]:
    run_dir = getattr(args, "server_side_current_dir", None)
    if run_dir is None:
        return step(False, ["server_side_current_snapshot_missing"])
    blockers: list[str] = []
    manifest, errors = read_json(run_dir / "evidence-manifest.json")
    blockers.extend(f"server_side_current_manifest_{error}" for error in errors)
    if not errors:
        if manifest.get("schema") != SERVER_SIDE_CURRENT_SCHEMA:
            blockers.append("server_side_current_manifest_schema")
        if manifest.get("passed") is not True:
            blockers.append("server_side_current_not_passed")
        if manifest.get("result_claim") != "server_side_publish_governance_ready":
            blockers.append("server_side_current_result_claim")
        target = manifest.get("target_package") if isinstance(manifest.get("target_package"), dict) else {}
        if target.get("component") != expected_component:
            blockers.append("server_side_current_component")
        if target.get("channel") != "homologation":
            blockers.append("server_side_current_channel")
        inputs = manifest.get("inputs") if isinstance(manifest.get("inputs"), dict) else {}
        if args.server_side_evidence is not None:
            expected = repo_rel(args.server_side_evidence) or str(args.server_side_evidence)
            if inputs.get("server_side_evidence") != expected:
                blockers.append("server_side_current_input_server_side_evidence_mismatch")
        if args.release_gate_summary is not None and args.release_gate_summary.is_file():
            expected_release_gate_sha256 = sha256_file(args.release_gate_summary)
            if inputs.get("expected_release_gate_sha256") != expected_release_gate_sha256:
                blockers.append("server_side_current_input_release_gate_sha256_mismatch")
        if args.server_side_trust_anchor_evidence is not None:
            expected = repo_rel(args.server_side_trust_anchor_evidence) or str(args.server_side_trust_anchor_evidence)
            if inputs.get("trust_anchor_evidence") != expected:
                blockers.append("server_side_current_input_trust_anchor_mismatch")
        trusted_keys = list(getattr(args, "server_side_trusted_key_pem", []) or [])
        if len(trusted_keys) == 1:
            expected = repo_rel(trusted_keys[0]) or str(trusted_keys[0])
            if inputs.get("trusted_key_pem") != expected:
                blockers.append("server_side_current_input_trusted_key_mismatch")
        elif trusted_keys:
            blockers.append("server_side_current_input_trusted_key_count_unsupported")
        files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
        for filename in REQUIRED_SERVER_SIDE_CURRENT_FILES:
            path = run_dir / filename
            entry = next((item for item in files if isinstance(item, dict) and item.get("file") == filename), None)
            if not path.is_file():
                blockers.append(f"server_side_current_file_missing:{filename}")
                continue
            if entry is None:
                blockers.append(f"server_side_current_manifest_file_missing:{filename}")
                continue
            if entry.get("sha256") != sha256_file(path):
                blockers.append(f"server_side_current_file_sha256_mismatch:{filename}")
            if entry.get("bytes") != path.stat().st_size:
                blockers.append(f"server_side_current_file_bytes_mismatch:{filename}")
    gate, gate_errors = read_json(run_dir / "server-side-governance-gate.json")
    blockers.extend(f"server_side_current_gate_{error}" for error in gate_errors)
    if not gate_errors:
        if gate.get("schema") != SERVER_SIDE_GATE_SCHEMA:
            blockers.append("server_side_current_gate_schema")
        if gate.get("passed") is not True:
            blockers.append("server_side_current_gate_not_passed")
        if gate.get("result_claim") != "server_side_publish_governance_ready":
            blockers.append("server_side_current_gate_result_claim")
    assets, asset_errors = read_json(run_dir / "server-side-asset-list.json")
    blockers.extend(f"server_side_current_asset_list_{error}" for error in asset_errors)
    if not asset_errors:
        if assets.get("schema") != SERVER_SIDE_ASSET_LIST_SCHEMA:
            blockers.append("server_side_current_asset_list_schema")
        asset_records = assets.get("asset_records") if isinstance(assets.get("asset_records"), list) else []
        if len(asset_records) != 14:
            blockers.append("server_side_current_asset_count_not_14")
        else:
            validate_server_side_current_asset_records(run_dir, asset_records, blockers)
    rollout_gate, rollout_gate_errors = read_json(run_dir / "server-side-rollout-state-gate.json")
    blockers.extend(f"server_side_current_rollout_gate_{error}" for error in rollout_gate_errors)
    if not rollout_gate_errors:
        if rollout_gate.get("schema") != "dadooh.c18.server_side_rollout_state_gate.v1":
            blockers.append("server_side_current_rollout_gate_schema")
        if rollout_gate.get("passed") is not True:
            blockers.append("server_side_current_rollout_gate_not_passed")
        if rollout_gate.get("result_claim") != "server_side_rollout_paused_pre_h2":
            blockers.append("server_side_current_rollout_gate_result_claim")
        if rollout_gate.get("blockers") != []:
            blockers.append("server_side_current_rollout_gate_has_blockers")
    rollout_result = validate_rollout_state(
        run_dir / "server-side-rollout-state.json",
        server_side_evidence=args.server_side_evidence,
        server_side_governance_gate=run_dir / "server-side-governance-gate.json",
        server_side_asset_list=run_dir / "server-side-asset-list.json",
        expected_target={
            "version": target.get("version", ""),
            "component": expected_component,
            "channel": "homologation",
            "source_commit": target.get("source_commit", ""),
            "payload_sha256": target.get("payload_sha256", ""),
        },
    )
    if rollout_result.get("passed") is not True:
        blockers.extend(f"server_side_current_rollout_state:{item}" for item in rollout_result.get("blockers", []))
    return step(
        not blockers,
        blockers,
        run_dir=str(run_dir),
        snapshot_sha256=directory_tree_sha256(run_dir) if run_dir.is_dir() else None,
    )


def evaluate_operator_decision(args: argparse.Namespace) -> dict[str, Any]:
    expected_target, target_errors = thaw_decision_expected_target_from_args(args)
    result = evaluate_thaw_decision_gate(
        args.operator_thaw_decision,
        expected_hashes=thaw_decision_expected_hashes_from_args(args),
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
        gate_result=result,
        expected_target=expected_target,
        expected_target_errors=target_errors,
    )


def evaluate_artifact_semantics(args: argparse.Namespace) -> dict[str, Any]:
    expected_component = getattr(args, "expected_component", "totem-core")
    checks = {
        "h1_decisive_bundle": evaluate_h1_release_gate_summary(
            getattr(args, "h1_release_gate_summary", None),
        ),
        "release_gate_summary": evaluate_release_gate_summary(
            args.release_gate_summary,
            expected_component=expected_component,
        ),
        "powerloss_matrix": evaluate_powerloss_matrix(args),
        "soak_summary": evaluate_soak_summary(args.soak_summary),
        "server_side_governance": evaluate_server_side_artifact(
            args,
            expected_component=expected_component,
        ),
        "server_side_current_snapshot": evaluate_server_side_current_snapshot(
            args,
            expected_component=expected_component,
        ),
        "operator_thaw_decision": evaluate_operator_decision(args),
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
                  expected_component: str = "totem-core",
                  expected_hashes: dict[str, str] | None = None,
                  require_expected_hashes: bool = False,
                  artifact_semantics: dict[str, Any] | None = None) -> dict[str, Any]:
    blockers: list[str] = []
    resolved_expected_hashes = expected_hashes or {}
    if data.get("schema") != SCHEMA:
        blockers.append("stable_promotion_schema")
    if expected_component not in STABLE_PROMOTION_COMPONENTS:
        blockers.append("stable_promotion_expected_component_invalid")
    elif data.get("component") != expected_component:
        blockers.append(component_blocker(expected_component))
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
             expected_component: str = "totem-core",
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
        expected_component=expected_component,
        expected_hashes=expected_hashes,
        require_expected_hashes=require_expected_hashes,
        artifact_semantics=artifact_semantics,
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_z(delta: dt.timedelta = dt.timedelta()) -> str:
    value = dt.datetime.now(dt.timezone.utc).replace(microsecond=0) + delta
    return value.isoformat().replace("+00:00", "Z")


def valid_fixture(*, component: str = "totem-core") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "component": component,
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
        "h1_release_gate_sha256": "0" * 64,
        "release_gate_sha256": "a" * 64,
        "h2_readiness_sha256": "b" * 64,
        "server_side_evidence_sha256": "c" * 64,
        "server_side_current_snapshot_sha256": "9" * 64,
        "server_side_trust_anchor_evidence_sha256": "f" * 64,
        "soak_summary_sha256": "d" * 64,
        "powerloss_matrix_sha256": "e" * 64,
        "auto_pull_enabled": False,
        "public_player_runtime_thaw": False,
    }


def semantic_args_fixture(root: Path) -> argparse.Namespace:
    h1_release_gate = root / "h1-release-gate.json"
    release_gate = root / "release-gate.json"
    server_side = write_server_side_fixture_release(root / "server-side-release", component="totem-core")
    server_side_evidence = json.loads(server_side.read_text(encoding="utf-8"))
    manifest_rel = server_side_evidence["release_assets"]["manifest"]
    server_manifest = json.loads((server_side.parent / manifest_rel).read_text(encoding="utf-8"))
    server_side_current = root / "server-side-current"
    server_side_current.mkdir(parents=True)
    (server_side_current / "README.md").write_text("server-side current fixture\n", encoding="utf-8")
    write_json(server_side_current / "server-side-governance-gate.json", {
        "schema": SERVER_SIDE_GATE_SCHEMA,
        "passed": True,
        "result_claim": "server_side_publish_governance_ready",
        "blockers": [],
    })
    release_dir = root / "release"
    release_dir.mkdir()
    asset_records = []
    for index in range(14):
        path = release_dir / f"asset-{index}.json"
        write_json(path, {"fixture_asset": index})
        asset_records.append({
            "path": f"release/asset-{index}.json",
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    write_json(server_side_current / "server-side-asset-list.json", {
        "schema": SERVER_SIDE_ASSET_LIST_SCHEMA,
        "asset_records": asset_records,
    })
    write_json(server_side_current / "server-side-rollout-state.json", {
        "schema": "dadooh.c18.server_side_rollout_state.v1",
        "passed": True,
        "result_claim": "server_side_rollout_paused_pre_h2",
        "target_package": {
            "version": server_manifest["version"],
            "component": "totem-core",
            "channel": server_manifest["channel"],
            "source_commit": server_manifest["source_commit"],
            "payload_sha256": server_manifest["payload_sha256"],
        },
        "state": "paused",
        "rollout_enabled": False,
        "auto_pull_enabled": False,
        "current_stage": "paused_pre_h2",
        "percentage": 0,
        "allowlist": [],
        "allowlist_count": 0,
        "allowlist_identity": "sha256",
        "empty_allowlist_blocks": True,
        "operator_window_active": False,
        "raw_device_ids_persisted": False,
        "stage_advance_allowed": False,
        "input_hashes": {
            "server_side_evidence_sha256": sha256_file(server_side),
            "server_side_governance_gate_sha256": sha256_file(server_side_current / "server-side-governance-gate.json"),
            "server_side_asset_list_sha256": sha256_file(server_side_current / "server-side-asset-list.json"),
        },
        "non_claims": [
            "this_state_does_not_publish_releases",
            "this_state_does_not_enable_auto_pull",
            "this_state_does_not_promote_stable",
            "this_state_does_not_thaw_player_runtime",
            "this_state_does_not_authorize_production",
            "this_state_does_not_advance_rollout",
            "this_state_does_not_replace_h2",
            "this_state_does_not_replace_powerloss_17_17",
            "this_state_does_not_replace_soak_24h",
        ],
    })
    write_json(server_side_current / "server-side-rollout-state-gate.json", validate_rollout_state(
        server_side_current / "server-side-rollout-state.json",
        server_side_evidence=server_side,
        server_side_governance_gate=server_side_current / "server-side-governance-gate.json",
        server_side_asset_list=server_side_current / "server-side-asset-list.json",
        expected_target={
            "version": server_manifest["version"],
            "component": "totem-core",
            "channel": server_manifest["channel"],
            "source_commit": server_manifest["source_commit"],
            "payload_sha256": server_manifest["payload_sha256"],
        },
    ))
    trusted_key = root / "trusted-key.pub.pem"
    trust_anchor = root / "trust-anchor.json"
    soak = root / "soak.json"
    operator = root / "operator.json"
    stable = root / "stable.json"
    write_json(h1_release_gate, {
        "schema": RELEASE_GATE_SCHEMA,
        "passed": True,
        "repo": {"dirty": False},
        "player_runtime_data_evidence": {"mode": "decisive", "status": "passed"},
    })
    write_json(release_gate, {
        "schema": RELEASE_GATE_SCHEMA,
        "passed": True,
        "repo": {"dirty": False},
    })
    trusted_key.write_text("PUBLIC KEY PLACEHOLDER\n", encoding="utf-8")
    write_json(trust_anchor, {"schema": "dadooh.c18.server_side_trust_anchor.v1"})
    current_files = []
    for filename in REQUIRED_SERVER_SIDE_CURRENT_FILES:
        path = server_side_current / filename
        current_files.append({"file": filename, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    write_json(server_side_current / "evidence-manifest.json", {
        "schema": SERVER_SIDE_CURRENT_SCHEMA,
        "passed": True,
        "result_claim": "server_side_publish_governance_ready",
        "target_package": {
            "version": server_manifest["version"],
            "component": "totem-core",
            "channel": server_manifest["channel"],
            "source_commit": server_manifest["source_commit"],
            "payload_sha256": server_manifest["payload_sha256"],
        },
        "inputs": {
            "server_side_evidence": str(server_side),
            "trusted_key_pem": str(trusted_key),
            "trust_anchor_evidence": str(trust_anchor),
            "expected_release_gate_sha256": sha256_file(release_gate),
        },
        "files": current_files,
    })
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
    powerloss_dirs: list[Path] = []
    for checkpoint in REQUIRED_POWERLOSS_CHECKPOINTS:
        run_dir = root / "powerloss" / checkpoint
        write_json(run_dir / "evidence-manifest.json", {
            "schema": POWERLOSS_MANIFEST_SCHEMA,
            "checkpoint": checkpoint,
            "target_payload_sha256": server_manifest["payload_sha256"],
            "image_tag": "c18-hwdecode-lab-1x",
            "image_sha256": "1" * 64,
            "image_marker_sha256": "2" * 64,
        })
        powerloss_dirs.append(run_dir)
    args = argparse.Namespace(
        evidence=stable,
        h1_release_gate_summary=h1_release_gate,
        release_gate_summary=release_gate,
        server_side_evidence=server_side,
        server_side_current_dir=server_side_current,
        server_side_trusted_key_pem=[trusted_key],
        server_side_trust_anchor_evidence=trust_anchor,
        soak_summary=soak,
        powerloss_evidence_dir=powerloss_dirs,
        operator_thaw_decision=operator,
        expect_image_tag="c18-hwdecode-lab-1x",
        expect_image_sha256="1" * 64,
        expect_image_marker_sha256="2" * 64,
    )
    write_json(stable, stable_fixture_bound_to_args(args))
    target, target_errors = thaw_decision_expected_target_from_args(args)
    if target_errors:
        raise AssertionError(f"fixture target metadata errors: {target_errors}")
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
        **thaw_decision_expected_hashes_from_args(args),
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


def stable_fixture_bound_to_args(args: argparse.Namespace) -> dict[str, Any]:
    data = valid_fixture()
    data.update(expected_hashes_from_args(args))
    return data


class StablePromotionGateSelfTest(unittest.TestCase):
    def test_complete_fixture_passes(self) -> None:
        result = validate_data(valid_fixture())
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_player_runtime_fixture_passes_when_expected(self) -> None:
        result = validate_data(
            valid_fixture(component="player-runtime"),
            expected_component="player-runtime",
        )
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_totem_core_stable_evidence_does_not_satisfy_player_runtime(self) -> None:
        result = validate_data(valid_fixture(), expected_component="player-runtime")
        self.assertFalse(result["passed"])
        self.assertIn("stable_promotion_component_not_player_runtime", result["blockers"])

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

        data = valid_fixture()
        result = validate_data(
            data,
            expected_hashes={"server_side_current_snapshot_sha256": "0" * 64},
        )
        self.assertFalse(result["passed"])
        self.assertIn("stable_promotion_server_side_current_snapshot_sha256_mismatch", result["blockers"])

    def test_hash_binding_passes_when_expected_matches(self) -> None:
        data = valid_fixture()
        result = validate_data(
            data,
            expected_hashes={
                "server_side_evidence_sha256": data["server_side_evidence_sha256"],
                "server_side_current_snapshot_sha256": data["server_side_current_snapshot_sha256"],
                "server_side_trust_anchor_evidence_sha256": data["server_side_trust_anchor_evidence_sha256"],
            },
        )
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_h2_readiness_hash_is_derived_from_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            h1_release_gate = tmp_path / "h1-release-gate.json"
            release_gate = tmp_path / "release-gate.json"
            server_side = tmp_path / "server-side.json"
            trust_anchor = tmp_path / "trust-anchor.json"
            server_side_current = tmp_path / "server-side-current"
            soak = tmp_path / "soak.json"
            powerloss_dir = tmp_path / "powerloss"
            server_side_current.mkdir()
            powerloss_dir.mkdir()
            write_json(h1_release_gate, {"h1": True})
            write_json(release_gate, {"release": True})
            write_json(server_side, {"server_side": True})
            write_json(trust_anchor, {"trust_anchor": True})
            write_json(server_side_current / "evidence-manifest.json", {"current": True})
            write_json(soak, {"duration": "24h"})
            write_json(powerloss_dir / "manifest.json", {"checkpoint": "after_current_symlink"})
            args = argparse.Namespace(
                h1_release_gate_summary=h1_release_gate,
                release_gate_summary=release_gate,
                server_side_evidence=server_side,
                server_side_current_dir=server_side_current,
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

    def test_operator_thaw_target_must_match_server_side_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = semantic_args_fixture(Path(tmp))
            operator = json.loads(args.operator_thaw_decision.read_text(encoding="utf-8"))
            operator["target_source_commit"] = "0" * 40
            write_json(args.operator_thaw_decision, operator)
            with (
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
                mock.patch(__name__ + ".evaluate_server_side_gate", return_value={"passed": True, "blockers": []}),
            ):
                semantics = evaluate_artifact_semantics(args)
        self.assertFalse(semantics["passed"])
        self.assertIn(
            "operator_thaw_decision:thaw_decision_target_source_commit_mismatch",
            semantics["blockers"],
        )

    def test_powerloss_matrix_must_match_server_side_target_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = semantic_args_fixture(Path(tmp))
            manifest_path = args.powerloss_evidence_dir[0] / "evidence-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["target_payload_sha256"] = "f" * 64
            write_json(manifest_path, manifest)
            with (
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
                mock.patch(__name__ + ".evaluate_server_side_gate", return_value={"passed": True, "blockers": []}),
            ):
                semantics = evaluate_artifact_semantics(args)
        self.assertFalse(semantics["passed"])
        self.assertIn(
            f"powerloss_matrix:{args.powerloss_evidence_dir[0].name}:powerloss_target_payload_sha256_mismatch_or_missing",
            semantics["blockers"],
        )

    def test_server_side_trusted_key_is_required_for_stable_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = semantic_args_fixture(Path(tmp))
            args.server_side_trusted_key_pem = []
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                semantics = evaluate_artifact_semantics(args)
        self.assertFalse(semantics["passed"])
        self.assertIn("server_side_governance:server_side_trusted_key_pem_missing", semantics["blockers"])

    def test_server_side_current_asset_records_must_match_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = semantic_args_fixture(Path(tmp))
            asset_path = Path(tmp) / "release" / "asset-0.json"
            asset_path.write_text('{"tampered":true}\n', encoding="utf-8")
            with (
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
                mock.patch(__name__ + ".evaluate_server_side_gate", return_value={"passed": True, "blockers": []}),
            ):
                semantics = evaluate_artifact_semantics(args)
        self.assertFalse(semantics["passed"])
        self.assertIn(
            "server_side_current_snapshot:server_side_current_asset_sha256_mismatch:release/asset-0.json",
            semantics["blockers"],
        )

    def test_server_side_current_rollout_state_must_be_paused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = semantic_args_fixture(Path(tmp))
            state_path = args.server_side_current_dir / "server-side-rollout-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["rollout_enabled"] = True
            write_json(state_path, state)
            with (
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
                mock.patch(__name__ + ".evaluate_server_side_gate", return_value={"passed": True, "blockers": []}),
            ):
                semantics = evaluate_artifact_semantics(args)
        self.assertFalse(semantics["passed"])
        self.assertIn(
            "server_side_current_snapshot:server_side_current_rollout_state:rollout_state_rollout_enabled_not_false",
            semantics["blockers"],
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate C18 stable promotion evidence.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--expected-component", choices=STABLE_PROMOTION_COMPONENTS, default="totem-core")
    parser.add_argument("--h1-release-gate-summary", type=Path, default=None)
    parser.add_argument("--release-gate-summary", type=Path, default=None)
    parser.add_argument("--server-side-evidence", type=Path, default=None)
    parser.add_argument("--server-side-current-dir", type=Path, default=None)
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
        expected_component=args.expected_component,
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
