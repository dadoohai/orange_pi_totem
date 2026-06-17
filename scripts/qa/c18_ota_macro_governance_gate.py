#!/usr/bin/env python3
"""Validate the current C18 OTA macro-governance snapshot.

This is an offline aggregate gate. It consumes already-versioned evidence for
H1, homologation pilot readiness, H2 readiness, read-only board diagnostics and
current server-side publish governance. It does not re-open an expired pilot
window, run SSH, publish, promote stable, enable auto-pull, complete H2, or thaw
player-runtime.
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

import c18_board_readonly_diagnostics_evidence_gate as board_gate


SCHEMA = "dadooh.c18.ota_macro_governance_gate.v1"
H1_RELEASE_GATE_SCHEMA = "dadooh.c18.ota.release_gate.v1"
PILOT_READINESS_SCHEMA = "dadooh.c18.homologation_pilot_readiness.v1"
H2_READINESS_SCHEMA = "dadooh.c18.player_runtime.h2_readiness.v1"
BOARD_READONLY_GATE_SCHEMA = "dadooh.c18.board_readonly_diagnostics_evidence_gate.v1"
SERVER_SIDE_CURRENT_SCHEMA = "dadooh.c18.server_side_current_validation_snapshot.v1"
SERVER_SIDE_GATE_SCHEMA = "dadooh.c18.server_side_publish_governance_gate.v1"
SERVER_SIDE_ASSET_LIST_SCHEMA = "dadooh.c18.server_side_publish_asset_list.v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_PACKAGE_VERSION = "c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e"
TARGET_SOURCE_COMMIT = "c16fb3ed01f0ce25c8203e5fe1d60baf60a75749"
TARGET_PAYLOAD_SHA256 = "d74a552f364de0e454a01a6fe839a1581d16c1b74acb357dc92c28a3ec0524a7"
EXPECTED_IMAGE_TAG = "c18-hwdecode-lab-1x"
EXPECTED_IMAGE_SHA256 = "1a853f569b5da9e856439897c95612d719fd3059f12349fa1040a6350c3df2f2"
EXPECTED_IMAGE_MARKER_SHA256 = "59739f57cdb3f79ac4c8ce5e5e1f9c4aa6d9dae58f704010f8423e66abe2bb9e"

DEFAULT_H1_SUMMARY = (
    REPO_ROOT
    / "docs/evidence/c18-update-validation/20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80/h1-release-gate.json"
)
DEFAULT_PILOT_READINESS = (
    REPO_ROOT
    / "docs/evidence/c18-update-validation/20260616T232546Z-current-pilot-readiness-5b2128c/pilot-readiness.json"
)
DEFAULT_H2_READINESS = (
    REPO_ROOT
    / "docs/evidence/c18-update-validation/20260612T200457Z-h2-readiness-traceability-snapshot-c16fb3e/h2-readiness.json"
)
DEFAULT_BOARD_READONLY_DIR = (
    REPO_ROOT / "docs/evidence/c18-update-validation/20260612T183722Z-board-readonly-diagnostics-17a1f9d"
)
DEFAULT_SERVER_SIDE_CURRENT_DIR = (
    REPO_ROOT / "docs/evidence/c18-update-validation/20260617T001804Z-server-side-current-c16fb3e"
)
DEFAULT_DOCS = (
    REPO_ROOT / "docs/product/189_C18_OTA_READINESS_GATE.md",
    REPO_ROOT / "docs/product/191_C18_OTA_OPERATING_MODEL.md",
    REPO_ROOT / "docs/product/192_C18_HOMOLOGATION_RC.md",
    REPO_ROOT / "docs/UPDATE_AUTHORIZATION_HEALTH.md",
    REPO_ROOT / "docs/UPDATE_CONTRACT.md",
)

REQUIRED_H1_STEPS = (
    "c18_player_runtime_data_coldboot_evidence_git_guard:1",
    "c18_player_runtime_data_coldboot_evidence",
    "c18_player_runtime_data_evidence_git_guard:1",
    "c18_player_runtime_data_evidence",
    "c18_player_runtime_data_evidence_link",
    "c18_player_runtime_production_stop_teardown_required",
)
REQUIRED_PILOT_CHECKS = (
    "h1_decisive_bundle",
    "pilot_authorization",
    "authorization_preflight_link",
    "board_preflight",
    "pilot_powerloss_p0",
    "repo_clean",
    "tracked_inputs",
    "source_expectation",
    "target_package",
)
REQUIRED_PILOT_NON_CLAIMS = (
    "this_gate_does_not_authorize_production",
    "this_gate_does_not_promote_stable",
    "this_gate_does_not_enable_auto_pull",
    "this_gate_does_not_satisfy_24h_soak",
    "this_gate_does_not_satisfy_powerloss_17_17",
    "this_gate_does_not_require_or_claim_signature_attestation",
    "this_gate_does_not_thaw_public_player_runtime",
)
EXPECTED_H2_BLOCKERS = (
    "full_physical_powerloss_matrix:powerloss_matrix_incomplete",
    "soak_endurance_24h:missing_24h_soak_summary",
    "stable_promotion_authorization:missing_stable_promotion_evidence",
    "explicit_operator_thaw_decision:missing_operator_thaw_decision",
)
REQUIRED_H2_GREEN_CHECKS = (
    "h1_decisive_bundle",
    "server_side_publish_governance",
    "repo_clean",
    "tracked_inputs",
)
REQUIRED_H2_RED_CHECKS = (
    "full_physical_powerloss_matrix",
    "soak_endurance_24h",
    "stable_promotion_authorization",
    "explicit_operator_thaw_decision",
)
REQUIRED_SERVER_SIDE_FILES = (
    "README.md",
    "server-side-governance-gate.json",
    "server-side-asset-list.json",
)
REQUIRED_SERVER_SIDE_KEY_CHECKS = (
    "governance_gate_passed",
    "expected_component_player_runtime",
    "external_trust_anchor_verified",
    "signed_or_attested_assets_verified",
    "asset_list_hash_bound",
    "auto_pull_default_disabled",
    "allowlist_controls_defined",
    "staged_rollout_defined",
    "audit_trail_defined",
)
REQUIRED_SERVER_SIDE_NON_CLAIMS = (
    "this_snapshot_does_not_publish_releases",
    "this_snapshot_does_not_enable_auto_pull",
    "this_snapshot_does_not_promote_stable",
    "this_snapshot_does_not_thaw_player_runtime",
    "this_snapshot_does_not_complete_h2",
    "this_snapshot_does_not_replace_powerloss_17_17",
    "this_snapshot_does_not_replace_soak_24h",
    "this_snapshot_does_not_replace_stable_promotion_or_formal_thaw_decision",
)
REQUIRED_SERVER_SIDE_ASSET_NON_CLAIMS = (
    "this_list_does_not_publish_releases",
    "this_list_does_not_enable_auto_pull",
    "this_list_does_not_promote_stable",
    "this_list_does_not_thaw_player_runtime",
    "this_list_does_not_complete_h2",
    "this_list_does_not_replace_powerloss_17_17",
    "this_list_does_not_replace_soak_24h",
    "this_list_does_not_replace_stable_promotion_or_formal_thaw_decision",
)
REQUIRED_DOC_TOKENS = (
    "scripts/qa/c18_ota_macro_governance_gate.py",
    "docs/evidence/c18-update-validation/20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80/h1-release-gate.json",
    "docs/evidence/c18-update-validation/20260616T232546Z-current-pilot-readiness-5b2128c/pilot-readiness.json",
    "docs/evidence/c18-update-validation/20260616T233424Z-current-macro-governance-95d79ef/",
    "docs/evidence/c18-update-validation/20260616T231448Z-operational-resume-current-2320950/",
    "docs/evidence/c18-update-validation/20260612T200457Z-h2-readiness-traceability-snapshot-c16fb3e/h2-readiness.json",
    "docs/evidence/c18-update-validation/20260616T235724Z-h2-powerloss-board-preflight-current-c16fb3e/",
    "docs/evidence/c18-update-validation/20260617T001804Z-server-side-current-c16fb3e/",
    "docs/evidence/c18-update-validation/20260612T183722Z-board-readonly-diagnostics-17a1f9d",
    "pre-H2",
    "nao substitui H2",
    *EXPECTED_H2_BLOCKERS,
)
FORBIDDEN_DOC_TOKENS = (
    (
        "com evidencia final em\n"
        "`docs/evidence/c18-update-validation/20260612T195516Z-pilot-readiness-traceability-refresh-c16fb3e/`"
    ),
    (
        "autorizacao operacional refrescada para o H1 rastreavel em\n"
        "`docs/evidence/c18-update-validation/20260612T195336Z-pilot-authorization-traceability-refresh/pilot-authorization.json`"
    ),
)
NON_CLAIMS = (
    "this_gate_does_not_reopen_expired_pilot_windows",
    "this_gate_does_not_authorize_production",
    "this_gate_does_not_promote_stable",
    "this_gate_does_not_enable_auto_pull",
    "this_gate_does_not_publish_releases",
    "this_gate_does_not_thaw_public_player_runtime",
    "this_gate_does_not_satisfy_24h_soak",
    "this_gate_does_not_satisfy_powerloss_17_17",
    "this_gate_does_not_replace_h2_readiness",
)


def check(name: str, blockers: list[str], **details: Any) -> dict[str, Any]:
    return {
        "passed": not blockers,
        "blockers": sorted(set(blockers)),
        **details,
    }


def read_json(path: Path, blockers: list[str], label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append(f"{label}_json_read_failed:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        blockers.append(f"{label}_not_object")
        return {}
    return data


def sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def git_lines(cmd: list[str]) -> tuple[int, list[str], str]:
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.returncode, [line for line in proc.stdout.splitlines() if line], proc.stderr


def repo_relative(path: Path) -> str | None:
    try:
        return path.resolve(strict=False).relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return None


def repo_clean_guard() -> dict[str, Any]:
    rc, lines, stderr = git_lines(["git", "status", "--porcelain", "--untracked-files=normal"])
    blockers: list[str] = []
    if rc != 0:
        blockers.append("git_status_failed")
    elif lines:
        blockers.append("repo_dirty")
    return check(
        "repo_clean",
        blockers,
        changed_paths=lines[:50],
        stderr_tail=stderr[-1000:] if rc != 0 else "",
    )


def manifest_declared_paths(path: Path) -> list[str]:
    manifest_path = path / "evidence-manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    entries = manifest.get("files")
    if not isinstance(entries, list):
        entries = manifest.get("artifacts")
    declared: list[str] = []
    if isinstance(entries, list):
        for item in entries:
            if not isinstance(item, dict):
                continue
            raw = item.get("file") if isinstance(item.get("file"), str) else item.get("path")
            if isinstance(raw, str) and raw and not raw.startswith("/") and ".." not in Path(raw).parts:
                declared.append(raw)
    return declared


def tracked_input_guard(paths: list[Path]) -> dict[str, Any]:
    blockers: list[str] = []
    tracked_paths: list[str] = []
    untracked: list[str] = []
    ignored: list[str] = []
    outside_repo: list[str] = []
    missing: list[str] = []
    manifest_untracked_entries: list[str] = []

    for path in paths:
        rel = repo_relative(path)
        if rel is None:
            blockers.append("input_outside_repo")
            outside_repo.append(str(path))
            continue
        if not path.exists():
            blockers.append("input_missing")
            missing.append(rel)
            continue
        ignored_rc, ignored_lines, ignored_err = git_lines([
            "git",
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--",
            rel,
        ])
        untracked_rc, untracked_lines, untracked_err = git_lines([
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            rel,
        ])
        tracked_rc, tracked_lines, tracked_err = git_lines(["git", "ls-files", "--", rel])
        if ignored_rc != 0:
            blockers.append("git_ignored_scan_failed")
            ignored.append(ignored_err[-1000:])
        if untracked_rc != 0:
            blockers.append("git_untracked_scan_failed")
            untracked.append(untracked_err[-1000:])
        if tracked_rc != 0:
            blockers.append("git_tracked_scan_failed")
            tracked_paths.append(tracked_err[-1000:])
        if ignored_lines:
            blockers.append("input_ignored_files_present")
            ignored.extend(ignored_lines[:20])
        if untracked_lines:
            blockers.append("input_untracked_files_present")
            untracked.extend(untracked_lines[:20])
        if path.is_file() and rel not in set(tracked_lines):
            blockers.append("input_file_not_tracked")
        if path.is_dir() and not tracked_lines:
            blockers.append("input_dir_has_no_tracked_files")
        tracked_paths.extend(tracked_lines[:50])

        if path.is_dir():
            tracked_set = set(tracked_lines)
            manifest_rel = f"{rel}/evidence-manifest.json"
            declared = manifest_declared_paths(path)
            if declared and manifest_rel not in tracked_set:
                blockers.append("evidence_manifest_not_tracked")
                manifest_untracked_entries.append(manifest_rel)
            for item in declared:
                item_rel = f"{rel}/{item}"
                if item_rel not in tracked_set:
                    blockers.append("evidence_manifest_entries_not_tracked")
                    manifest_untracked_entries.append(item_rel)

    return check(
        "tracked_inputs",
        blockers,
        paths=sorted(set(tracked_paths))[:200],
        missing=missing,
        outside_repo=outside_repo,
        untracked=untracked[:50],
        ignored=ignored[:50],
        manifest_untracked_entries=sorted(set(manifest_untracked_entries))[:50],
    )


def h1_step_passed(summary: dict[str, Any], name: str) -> bool:
    for step in summary.get("steps") if isinstance(summary.get("steps"), list) else []:
        if isinstance(step, dict) and step.get("name") == name and step.get("passed") is True:
            return True
    return False


def evaluate_h1(summary_path: Path) -> dict[str, Any]:
    blockers: list[str] = []
    summary = read_json(summary_path, blockers, "h1")
    if not summary:
        return check("h1_traceability", blockers, summary_path=str(summary_path))
    if summary.get("schema") != H1_RELEASE_GATE_SCHEMA:
        blockers.append("h1_schema")
    if summary.get("passed") is not True:
        blockers.append("h1_not_passed")
    repo = summary.get("repo") if isinstance(summary.get("repo"), dict) else {}
    if repo.get("dirty") is not False:
        blockers.append("h1_repo_dirty")
    data = summary.get("player_runtime_data_evidence")
    if not isinstance(data, dict):
        blockers.append("h1_player_runtime_data_evidence_missing")
        data = {}
    expected_data = {
        "required": True,
        "decisive": True,
        "mode": "decisive",
        "status": "passed",
        "expected_image_tag": EXPECTED_IMAGE_TAG,
        "expected_image_sha256": EXPECTED_IMAGE_SHA256,
        "expected_image_marker_sha256": EXPECTED_IMAGE_MARKER_SHA256,
    }
    for key, expected in expected_data.items():
        if data.get(key) != expected:
            blockers.append(f"h1_data_{key}")
    for name in REQUIRED_H1_STEPS:
        if not h1_step_passed(summary, name):
            blockers.append(f"h1_step_missing_or_failed:{name}")
    teardown_steps = [
        item
        for item in summary.get("steps") if isinstance(summary.get("steps"), list)
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and item["name"].startswith("c18_player_runtime_teardown_evidence:")
        and item.get("passed") is True
    ]
    if not teardown_steps:
        blockers.append("h1_teardown_evidence_missing")
    return check(
        "h1_traceability",
        blockers,
        summary_path=repo_relative(summary_path) or str(summary_path),
        repo_head=repo.get("head"),
        step_count=len(summary.get("steps") if isinstance(summary.get("steps"), list) else []),
        data_evidence={
            "status": data.get("status"),
            "mode": data.get("mode"),
            "expected_image_tag": data.get("expected_image_tag"),
        },
        teardown_evidence_count=len(teardown_steps),
    )


def nested_check_passed(data: dict[str, Any], key: str) -> bool:
    checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    item = checks.get(key)
    return isinstance(item, dict) and item.get("passed") is True


def nested_check_blockers(data: dict[str, Any], key: str) -> list[str]:
    checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    item = checks.get(key)
    if not isinstance(item, dict):
        return []
    raw = item.get("blockers")
    return [str(value) for value in raw] if isinstance(raw, list) else []


def evaluate_pilot_readiness(path: Path) -> dict[str, Any]:
    blockers: list[str] = []
    data = read_json(path, blockers, "pilot")
    if not data:
        return check("pilot_readiness", blockers, summary_path=str(path))
    if data.get("schema") != PILOT_READINESS_SCHEMA:
        blockers.append("pilot_schema")
    if data.get("passed") is not True:
        blockers.append("pilot_not_passed")
    if data.get("result_claim") != "homologation_pilot_ready":
        blockers.append("pilot_result_claim")
    if data.get("ring") != "pilot":
        blockers.append("pilot_ring")
    if data.get("channel") != "homologation":
        blockers.append("pilot_channel")
    if data.get("blockers") != []:
        blockers.append("pilot_has_blockers")
    for key in REQUIRED_PILOT_CHECKS:
        if not nested_check_passed(data, key):
            blockers.append(f"pilot_check_missing_or_failed:{key}")
    non_claims = set(data.get("non_claims") if isinstance(data.get("non_claims"), list) else [])
    for claim in REQUIRED_PILOT_NON_CLAIMS:
        if claim not in non_claims:
            blockers.append(f"pilot_non_claim_missing:{claim}")

    checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    package = checks.get("target_package") if isinstance(checks.get("target_package"), dict) else {}
    if package.get("version") != TARGET_PACKAGE_VERSION:
        blockers.append("pilot_target_package_version")
    if package.get("channel") != "homologation":
        blockers.append("pilot_target_package_channel")
    if package.get("payload_sha256") != TARGET_PAYLOAD_SHA256:
        blockers.append("pilot_target_payload_sha256")
    source = checks.get("source_expectation") if isinstance(checks.get("source_expectation"), dict) else {}
    if source.get("expect_source_commit") != TARGET_SOURCE_COMMIT:
        blockers.append("pilot_expected_source_commit")
    if source.get("authorization_source_commit") != TARGET_SOURCE_COMMIT:
        blockers.append("pilot_authorization_source_commit")
    h1 = checks.get("h1_decisive_bundle") if isinstance(checks.get("h1_decisive_bundle"), dict) else {}
    if not str(h1.get("summary_path", "")).endswith(
        "20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80/h1-release-gate.json"
    ):
        blockers.append("pilot_h1_summary_path")
    auth = checks.get("pilot_authorization") if isinstance(checks.get("pilot_authorization"), dict) else {}
    return check(
        "pilot_readiness",
        blockers,
        summary_path=repo_relative(path) or str(path),
        target_package=package.get("version"),
        target_channel=package.get("channel"),
        source_commit=source.get("expect_source_commit"),
        authorization_window={
            "snapshot_only": True,
            "start": auth.get("window_start_utc"),
            "end": auth.get("window_end_utc"),
            "evaluated_at_utc": auth.get("evaluated_at_utc"),
        },
    )


def evaluate_h2_readiness(path: Path) -> dict[str, Any]:
    blockers: list[str] = []
    data = read_json(path, blockers, "h2")
    if not data:
        return check("h2_preproduction_block", blockers, summary_path=str(path))
    if data.get("schema") != H2_READINESS_SCHEMA:
        blockers.append("h2_schema")
    if data.get("passed") is not False:
        blockers.append("h2_must_remain_blocked_pre_production")
    if data.get("result_claim") != "h2_readiness_blocked":
        blockers.append("h2_result_claim")
    if sorted(data.get("blockers") if isinstance(data.get("blockers"), list) else []) != sorted(EXPECTED_H2_BLOCKERS):
        blockers.append("h2_blockers_not_exact")
    for key in REQUIRED_H2_GREEN_CHECKS:
        if not nested_check_passed(data, key):
            blockers.append(f"h2_green_check_missing_or_failed:{key}")
    for key in REQUIRED_H2_RED_CHECKS:
        if nested_check_passed(data, key):
            blockers.append(f"h2_prod_check_unexpectedly_green:{key}")
        nested = nested_check_blockers(data, key)
        if not nested:
            blockers.append(f"h2_prod_check_missing_blocker:{key}")
    return check(
        "h2_preproduction_block",
        blockers,
        summary_path=repo_relative(path) or str(path),
        result_claim=data.get("result_claim"),
        blockers_expected=list(EXPECTED_H2_BLOCKERS),
        blockers_actual=data.get("blockers") if isinstance(data.get("blockers"), list) else [],
    )


def evaluate_board_diagnostics(run_dir: Path) -> dict[str, Any]:
    result = board_gate.evaluate(run_dir)
    blockers: list[str] = []
    if result.get("schema") != BOARD_READONLY_GATE_SCHEMA:
        blockers.append("board_gate_schema")
    if result.get("passed") is not True:
        blockers.extend(f"board_gate:{item}" for item in result.get("blockers", []))
    if result.get("result_claim") != "board_readonly_diagnostics_evidence_accepted":
        blockers.append("board_gate_result_claim")
    non_claims = set(result.get("non_claims") if isinstance(result.get("non_claims"), list) else [])
    if "this_gate_does_not_complete_h2" not in non_claims:
        blockers.append("board_gate_h2_non_claim_missing")
    if "this_gate_does_not_publish_promote_stable_enable_auto_pull_or_thaw" not in non_claims:
        blockers.append("board_gate_publish_non_claim_missing")
    return check(
        "board_readonly_diagnostics",
        blockers,
        run_dir=repo_relative(run_dir) or str(run_dir),
        board_result_claim=result.get("result_claim"),
        board_blockers=result.get("blockers", []),
    )


def manifest_file_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = manifest.get("files")
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(entries, list):
        return out
    for item in entries:
        if not isinstance(item, dict):
            continue
        raw = item.get("file")
        if isinstance(raw, str):
            out[raw] = item
    return out


def validate_manifest_hashes(run_dir: Path, manifest: dict[str, Any], blockers: list[str]) -> None:
    entries = manifest_file_map(manifest)
    if set(entries) != set(REQUIRED_SERVER_SIDE_FILES):
        blockers.append("server_side_manifest_files_not_exact")
    for filename in REQUIRED_SERVER_SIDE_FILES:
        item = entries.get(filename)
        path = run_dir / filename
        if item is None:
            blockers.append(f"server_side_manifest_file_missing:{filename}")
            continue
        if path.is_symlink() or not path.is_file():
            blockers.append(f"server_side_file_missing_or_symlink:{filename}")
            continue
        if item.get("bytes") != path.stat().st_size:
            blockers.append(f"server_side_file_bytes_mismatch:{filename}")
        actual_hash = sha256_file(path)
        if item.get("sha256") != actual_hash:
            blockers.append(f"server_side_file_sha256_mismatch:{filename}")


def evaluate_server_side_current(run_dir: Path) -> dict[str, Any]:
    blockers: list[str] = []
    manifest_path = run_dir / "evidence-manifest.json"
    manifest = read_json(manifest_path, blockers, "server_side_manifest")
    if not manifest:
        return check("server_side_current", blockers, run_dir=str(run_dir))
    validate_manifest_hashes(run_dir, manifest, blockers)
    if manifest.get("schema") != SERVER_SIDE_CURRENT_SCHEMA:
        blockers.append("server_side_manifest_schema")
    if manifest.get("passed") is not True:
        blockers.append("server_side_manifest_not_passed")
    if manifest.get("result_claim") != "server_side_publish_governance_ready":
        blockers.append("server_side_manifest_result_claim")

    target = manifest.get("target_package") if isinstance(manifest.get("target_package"), dict) else {}
    if target.get("version") != TARGET_PACKAGE_VERSION:
        blockers.append("server_side_target_version")
    if target.get("component") != "player-runtime":
        blockers.append("server_side_target_component")
    if target.get("channel") != "homologation":
        blockers.append("server_side_target_channel")
    if target.get("source_commit") != TARGET_SOURCE_COMMIT:
        blockers.append("server_side_target_source_commit")
    if target.get("payload_sha256") != TARGET_PAYLOAD_SHA256:
        blockers.append("server_side_target_payload_sha256")

    key_checks = manifest.get("key_checks") if isinstance(manifest.get("key_checks"), dict) else {}
    for key in REQUIRED_SERVER_SIDE_KEY_CHECKS:
        if key_checks.get(key) is not True:
            blockers.append(f"server_side_key_check_missing_or_false:{key}")
    if key_checks.get("asset_count") != 14:
        blockers.append("server_side_asset_count")
    non_claims = set(manifest.get("non_claims") if isinstance(manifest.get("non_claims"), list) else [])
    for claim in REQUIRED_SERVER_SIDE_NON_CLAIMS:
        if claim not in non_claims:
            blockers.append(f"server_side_non_claim_missing:{claim}")

    gate = read_json(run_dir / "server-side-governance-gate.json", blockers, "server_side_gate")
    if gate:
        if gate.get("schema") != SERVER_SIDE_GATE_SCHEMA:
            blockers.append("server_side_gate_schema")
        if gate.get("passed") is not True:
            blockers.append("server_side_gate_not_passed")
        if gate.get("result_claim") != "server_side_publish_governance_ready":
            blockers.append("server_side_gate_result_claim")
        if gate.get("blockers") != []:
            blockers.append("server_side_gate_has_blockers")

    assets = read_json(run_dir / "server-side-asset-list.json", blockers, "server_side_assets")
    asset_count = 0
    if assets:
        if assets.get("schema") != SERVER_SIDE_ASSET_LIST_SCHEMA:
            blockers.append("server_side_asset_list_schema")
        asset_paths = assets.get("assets")
        asset_records = assets.get("asset_records")
        if not isinstance(asset_paths, list) or len(asset_paths) != 14:
            blockers.append("server_side_asset_list_count")
        else:
            asset_count = len(asset_paths)
        if not isinstance(asset_records, list) or len(asset_records) != 14:
            blockers.append("server_side_asset_records_count")
        else:
            record_paths = [item.get("path") for item in asset_records if isinstance(item, dict)]
            if record_paths != asset_paths:
                blockers.append("server_side_asset_records_path_order")
            for item in asset_records:
                if not isinstance(item, dict):
                    blockers.append("server_side_asset_record_not_object")
                    continue
                raw_path = item.get("path")
                if not isinstance(raw_path, str) or not raw_path or raw_path.startswith("/") or ".." in Path(raw_path).parts:
                    blockers.append("server_side_asset_record_path_invalid")
                if not isinstance(item.get("sha256"), str) or len(item["sha256"]) != 64:
                    blockers.append("server_side_asset_record_sha256_invalid")
                if not isinstance(item.get("bytes"), int) or item["bytes"] <= 0:
                    blockers.append("server_side_asset_record_bytes_invalid")
        asset_non_claims = set(assets.get("non_claims") if isinstance(assets.get("non_claims"), list) else [])
        for claim in REQUIRED_SERVER_SIDE_ASSET_NON_CLAIMS:
            if claim not in asset_non_claims:
                blockers.append(f"server_side_asset_non_claim_missing:{claim}")

    return check(
        "server_side_current",
        blockers,
        run_dir=repo_relative(run_dir) or str(run_dir),
        result_claim=manifest.get("result_claim"),
        asset_count=asset_count,
        target_package=target.get("version"),
    )


def evaluate_docs(doc_paths: list[Path]) -> dict[str, Any]:
    blockers: list[str] = []
    combined_parts: list[str] = []
    read_docs: list[str] = []
    for path in doc_paths:
        try:
            combined_parts.append(path.read_text(encoding="utf-8"))
            read_docs.append(repo_relative(path) or str(path))
        except Exception as exc:
            blockers.append(f"doc_read_failed:{path.name}:{type(exc).__name__}")
    combined = "\n".join(combined_parts)
    for token in REQUIRED_DOC_TOKENS:
        if token not in combined:
            blockers.append(f"doc_token_missing:{token}")
    for token in FORBIDDEN_DOC_TOKENS:
        if token in combined:
            blockers.append(f"doc_forbidden_stale_current_token:{token}")
    if "producao" not in combined or "stable" not in combined:
        blockers.append("doc_production_stable_scope_missing")
    return check("macro_docs", blockers, docs=read_docs)


def evaluate(
    *,
    h1_summary: Path,
    pilot_readiness: Path,
    h2_readiness: Path,
    board_readonly_dir: Path,
    server_side_current_dir: Path,
    docs: list[Path],
    require_repo_clean: bool = True,
) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {
        "h1_traceability": evaluate_h1(h1_summary),
        "pilot_readiness": evaluate_pilot_readiness(pilot_readiness),
        "h2_preproduction_block": evaluate_h2_readiness(h2_readiness),
        "board_readonly_diagnostics": evaluate_board_diagnostics(board_readonly_dir),
        "server_side_current": evaluate_server_side_current(server_side_current_dir),
        "macro_docs": evaluate_docs(docs),
    }
    if require_repo_clean:
        checks["repo_clean"] = repo_clean_guard()
        checks["tracked_inputs"] = tracked_input_guard([
            h1_summary.parent,
            pilot_readiness.parent,
            h2_readiness.parent,
            board_readonly_dir,
            server_side_current_dir,
            *docs,
        ])

    blockers = [
        f"{name}:{blocker}"
        for name, result in checks.items()
        for blocker in result.get("blockers", [])
    ]
    passed = not blockers
    return {
        "schema": SCHEMA,
        "evaluated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "passed": passed,
        "result_claim": (
            "c18_homologation_governance_ready_pre_h2"
            if passed
            else "c18_macro_governance_blocked"
        ),
        "target": {
            "component": "player-runtime",
            "package_version": TARGET_PACKAGE_VERSION,
            "source_commit": TARGET_SOURCE_COMMIT,
            "channel": "homologation",
            "ring": "pilot",
            "payload_sha256": TARGET_PAYLOAD_SHA256,
            "image_tag": EXPECTED_IMAGE_TAG,
        },
        "checks": checks,
        "blockers": sorted(set(blockers)),
        "h2_expected_blockers": list(EXPECTED_H2_BLOCKERS),
        "non_claims": list(NON_CLAIMS),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fixture_step(name: str, passed: bool = True) -> dict[str, Any]:
    return {"name": name, "passed": passed, "returncode": 0 if passed else 1, "stderr_tail": ""}


def write_fixture(root: Path) -> argparse.Namespace:
    h1_path = root / "h1-release-gate.json"
    pilot_path = root / "pilot-readiness.json"
    h2_path = root / "h2-readiness.json"
    board_dir = board_gate.valid_fixture(root)
    server_side_dir = root / "server-side-current"
    server_side_dir.mkdir(parents=True, exist_ok=True)
    docs = [root / f"doc-{index}.md" for index in range(5)]
    for path in docs:
        path.write_text(
            "\n".join([
                "scripts/qa/c18_ota_macro_governance_gate.py",
                "docs/evidence/c18-update-validation/20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80/h1-release-gate.json",
                "docs/evidence/c18-update-validation/20260616T232546Z-current-pilot-readiness-5b2128c/pilot-readiness.json",
                "docs/evidence/c18-update-validation/20260616T233424Z-current-macro-governance-95d79ef/",
                "docs/evidence/c18-update-validation/20260616T231448Z-operational-resume-current-2320950/",
                "docs/evidence/c18-update-validation/20260612T200457Z-h2-readiness-traceability-snapshot-c16fb3e/h2-readiness.json",
                "docs/evidence/c18-update-validation/20260616T235724Z-h2-powerloss-board-preflight-current-c16fb3e/",
                "docs/evidence/c18-update-validation/20260617T001804Z-server-side-current-c16fb3e/",
                "docs/evidence/c18-update-validation/20260612T183722Z-board-readonly-diagnostics-17a1f9d",
                "pre-H2",
                "nao substitui H2",
                *EXPECTED_H2_BLOCKERS,
                "producao stable",
            ]),
            encoding="utf-8",
        )

    h1_steps = [fixture_step(name) for name in REQUIRED_H1_STEPS]
    h1_steps.append(fixture_step("c18_player_runtime_teardown_evidence:1"))
    write_json(h1_path, {
        "schema": H1_RELEASE_GATE_SCHEMA,
        "passed": True,
        "repo": {"dirty": False, "head": "7e40e80789229de1aed5d736a504803a09f97f54"},
        "player_runtime_data_evidence": {
            "required": True,
            "decisive": True,
            "mode": "decisive",
            "status": "passed",
            "expected_image_tag": EXPECTED_IMAGE_TAG,
            "expected_image_sha256": EXPECTED_IMAGE_SHA256,
            "expected_image_marker_sha256": EXPECTED_IMAGE_MARKER_SHA256,
        },
        "steps": h1_steps,
    })

    pilot_checks = {name: {"passed": True, "blockers": []} for name in REQUIRED_PILOT_CHECKS}
    pilot_checks["target_package"].update({
        "version": TARGET_PACKAGE_VERSION,
        "channel": "homologation",
        "payload_sha256": TARGET_PAYLOAD_SHA256,
    })
    pilot_checks["source_expectation"].update({
        "expect_source_commit": TARGET_SOURCE_COMMIT,
        "authorization_source_commit": TARGET_SOURCE_COMMIT,
    })
    pilot_checks["h1_decisive_bundle"].update({
        "summary_path": "docs/evidence/c18-update-validation/20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80/h1-release-gate.json",
    })
    pilot_checks["pilot_authorization"].update({
        "window_start_utc": "2026-06-12T10:00:00Z",
        "window_end_utc": "2026-06-13T10:00:00Z",
        "evaluated_at_utc": "2026-06-12T19:54:53Z",
    })
    write_json(pilot_path, {
        "schema": PILOT_READINESS_SCHEMA,
        "passed": True,
        "result_claim": "homologation_pilot_ready",
        "ring": "pilot",
        "channel": "homologation",
        "blockers": [],
        "checks": pilot_checks,
        "non_claims": list(REQUIRED_PILOT_NON_CLAIMS),
    })

    h2_checks = {name: {"passed": True, "blockers": []} for name in REQUIRED_H2_GREEN_CHECKS}
    for blocker in EXPECTED_H2_BLOCKERS:
        key, reason = blocker.split(":", 1)
        h2_checks[key] = {"passed": False, "blockers": [reason]}
    write_json(h2_path, {
        "schema": H2_READINESS_SCHEMA,
        "passed": False,
        "result_claim": "h2_readiness_blocked",
        "blockers": list(EXPECTED_H2_BLOCKERS),
        "checks": h2_checks,
        "non_claims": [
            "this_gate_does_not_thaw_player_runtime",
            "this_gate_does_not_publish_or_fetch_releases",
            "this_gate_does_not_override_freeze_rc_44",
            "this_gate_does_not_promote_stable_without_operator_decision",
        ],
    })

    (server_side_dir / "README.md").write_text(
        "Server-side current validation fixture. Does not complete H2, publish, stable, thaw, 17/17 or soak.\n",
        encoding="utf-8",
    )
    write_json(server_side_dir / "server-side-governance-gate.json", {
        "schema": SERVER_SIDE_GATE_SCHEMA,
        "passed": True,
        "result_claim": "server_side_publish_governance_ready",
        "blockers": [],
        "non_claims": [
            "this_gate_does_not_publish_releases",
            "this_gate_does_not_enable_auto_pull",
            "this_gate_does_not_promote_stable",
            "this_gate_does_not_thaw_player_runtime",
        ],
    })
    asset_records = [
        {
            "path": f"release/asset-{index}.json",
            "bytes": 100 + index,
            "sha256": f"{index:064x}"[-64:],
        }
        for index in range(14)
    ]
    write_json(server_side_dir / "server-side-asset-list.json", {
        "schema": SERVER_SIDE_ASSET_LIST_SCHEMA,
        "assets": [item["path"] for item in asset_records],
        "asset_records": asset_records,
        "non_claims": list(REQUIRED_SERVER_SIDE_ASSET_NON_CLAIMS),
    })
    file_entries = []
    for filename in REQUIRED_SERVER_SIDE_FILES:
        path = server_side_dir / filename
        file_entries.append({
            "file": filename,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        })
    write_json(server_side_dir / "evidence-manifest.json", {
        "schema": SERVER_SIDE_CURRENT_SCHEMA,
        "collected_at_utc": "2026-06-17T00:18:04Z",
        "passed": True,
        "result_claim": "server_side_publish_governance_ready",
        "files": file_entries,
        "target_package": {
            "version": TARGET_PACKAGE_VERSION,
            "component": "player-runtime",
            "channel": "homologation",
            "source_commit": TARGET_SOURCE_COMMIT,
            "payload_sha256": TARGET_PAYLOAD_SHA256,
        },
        "key_checks": {
            **{key: True for key in REQUIRED_SERVER_SIDE_KEY_CHECKS},
            "asset_count": 14,
        },
        "non_claims": list(REQUIRED_SERVER_SIDE_NON_CLAIMS),
    })

    return argparse.Namespace(
        h1_summary=h1_path,
        pilot_readiness=pilot_path,
        h2_readiness=h2_path,
        board_readonly_dir=board_dir,
        server_side_current_dir=server_side_dir,
        docs=docs,
    )


class MacroGovernanceGateSelfTest(unittest.TestCase):
    def evaluate_fixture(self, fixture: argparse.Namespace) -> dict[str, Any]:
        return evaluate(
            h1_summary=fixture.h1_summary,
            pilot_readiness=fixture.pilot_readiness,
            h2_readiness=fixture.h2_readiness,
            board_readonly_dir=fixture.board_readonly_dir,
            server_side_current_dir=fixture.server_side_current_dir,
            docs=fixture.docs,
            require_repo_clean=False,
        )

    def test_valid_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write_fixture(Path(tmp))
            result = self.evaluate_fixture(fixture)
        self.assertTrue(result["passed"], result["blockers"])
        self.assertEqual(result["result_claim"], "c18_homologation_governance_ready_pre_h2")

    def test_pilot_channel_must_remain_homologation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write_fixture(Path(tmp))
            data = json.loads(fixture.pilot_readiness.read_text(encoding="utf-8"))
            data["channel"] = "stable"
            data["checks"]["target_package"]["channel"] = "stable"
            write_json(fixture.pilot_readiness, data)
            result = self.evaluate_fixture(fixture)
        self.assertFalse(result["passed"])
        self.assertIn("pilot_readiness:pilot_channel", result["blockers"])
        self.assertIn("pilot_readiness:pilot_target_package_channel", result["blockers"])

    def test_h2_must_remain_red_with_exact_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write_fixture(Path(tmp))
            data = json.loads(fixture.h2_readiness.read_text(encoding="utf-8"))
            data["passed"] = True
            data["blockers"] = []
            write_json(fixture.h2_readiness, data)
            result = self.evaluate_fixture(fixture)
        self.assertFalse(result["passed"])
        self.assertIn("h2_preproduction_block:h2_must_remain_blocked_pre_production", result["blockers"])
        self.assertIn("h2_preproduction_block:h2_blockers_not_exact", result["blockers"])

    def test_h2_missing_expected_blocker_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write_fixture(Path(tmp))
            data = json.loads(fixture.h2_readiness.read_text(encoding="utf-8"))
            data["blockers"] = data["blockers"][:-1]
            write_json(fixture.h2_readiness, data)
            result = self.evaluate_fixture(fixture)
        self.assertFalse(result["passed"])
        self.assertIn("h2_preproduction_block:h2_blockers_not_exact", result["blockers"])

    def test_h1_data_git_guard_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write_fixture(Path(tmp))
            data = json.loads(fixture.h1_summary.read_text(encoding="utf-8"))
            data["steps"] = [
                step
                for step in data["steps"]
                if step["name"] != "c18_player_runtime_data_evidence_git_guard:1"
            ]
            write_json(fixture.h1_summary, data)
            result = self.evaluate_fixture(fixture)
        self.assertFalse(result["passed"])
        self.assertIn(
            "h1_traceability:h1_step_missing_or_failed:c18_player_runtime_data_evidence_git_guard:1",
            result["blockers"],
        )

    def test_docs_must_name_macro_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write_fixture(Path(tmp))
            for path in fixture.docs:
                path.write_text("pre-H2 nao substitui H2 producao stable\n", encoding="utf-8")
            result = self.evaluate_fixture(fixture)
        self.assertFalse(result["passed"])
        self.assertIn(
            "macro_docs:doc_token_missing:scripts/qa/c18_ota_macro_governance_gate.py",
            result["blockers"],
        )

    def test_docs_reject_stale_current_pilot_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write_fixture(Path(tmp))
            fixture.docs[0].write_text(
                fixture.docs[0].read_text(encoding="utf-8")
                + "\ncom evidencia final em\n"
                "`docs/evidence/c18-update-validation/20260612T195516Z-pilot-readiness-traceability-refresh-c16fb3e/`\n",
                encoding="utf-8",
            )
            result = self.evaluate_fixture(fixture)
        self.assertFalse(result["passed"])
        self.assertTrue(
            any(item.startswith("macro_docs:doc_forbidden_stale_current_token:") for item in result["blockers"]),
            result["blockers"],
        )

    def test_board_overclaim_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write_fixture(Path(tmp))
            (fixture.board_readonly_dir / "README.md").write_text("H2 passed, stable production ready\n", encoding="utf-8")
            result = self.evaluate_fixture(fixture)
        self.assertFalse(result["passed"])
        self.assertTrue(any(item.startswith("board_readonly_diagnostics:board_gate:overclaim:") for item in result["blockers"]))

    def test_server_side_current_is_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write_fixture(Path(tmp))
            (fixture.server_side_current_dir / "server-side-asset-list.json").write_text("{}", encoding="utf-8")
            result = self.evaluate_fixture(fixture)
        self.assertFalse(result["passed"])
        self.assertIn(
            "server_side_current:server_side_file_sha256_mismatch:server-side-asset-list.json",
            result["blockers"],
        )

    def test_repo_clean_and_tracked_inputs_are_required_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = write_fixture(Path(tmp))
            with (
                mock.patch(__name__ + ".repo_clean_guard", return_value=check("repo_clean", ["repo_dirty"])),
                mock.patch(__name__ + ".tracked_input_guard", return_value=check("tracked_inputs", ["input_file_not_tracked"])),
            ):
                result = evaluate(
                    h1_summary=fixture.h1_summary,
                    pilot_readiness=fixture.pilot_readiness,
                    h2_readiness=fixture.h2_readiness,
                    board_readonly_dir=fixture.board_readonly_dir,
                    server_side_current_dir=fixture.server_side_current_dir,
                    docs=fixture.docs,
                    require_repo_clean=True,
                )
        self.assertFalse(result["passed"])
        self.assertIn("repo_clean:repo_dirty", result["blockers"])
        self.assertIn("tracked_inputs:input_file_not_tracked", result["blockers"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--h1-release-gate-summary", type=Path, default=DEFAULT_H1_SUMMARY)
    parser.add_argument("--pilot-readiness-summary", type=Path, default=DEFAULT_PILOT_READINESS)
    parser.add_argument("--h2-readiness-summary", type=Path, default=DEFAULT_H2_READINESS)
    parser.add_argument("--board-readonly-diagnostics-dir", type=Path, default=DEFAULT_BOARD_READONLY_DIR)
    parser.add_argument("--server-side-current-dir", type=Path, default=DEFAULT_SERVER_SIDE_CURRENT_DIR)
    parser.add_argument("--doc", action="append", type=Path, default=[])
    parser.add_argument("--allow-dirty-repo", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(MacroGovernanceGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1

    docs = args.doc if args.doc else list(DEFAULT_DOCS)
    result = evaluate(
        h1_summary=args.h1_release_gate_summary,
        pilot_readiness=args.pilot_readiness_summary,
        h2_readiness=args.h2_readiness_summary,
        board_readonly_dir=args.board_readonly_diagnostics_dir,
        server_side_current_dir=args.server_side_current_dir,
        docs=docs,
        require_repo_clean=not args.allow_dirty_repo,
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
