#!/usr/bin/env python3
"""Validate sanitized C18 player-runtime rehearsal evidence before commit."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.player_runtime.evidence_gate.v1"

ALLOWED_PATTERNS = (
    "README.md",
    "evidence-manifest.json",
    "package/*.manifest.json",
    "package/player-runtime-release-gate.json",
    "lab-apply.json",
    "lab-rollback.json",
    "lab-reconcile.json",
    "candidate-health-result.json",
    "candidate-health/playback-deep-health-public.json",
    "candidate-health/playback-samples.tsv",
    "candidate-health/status-samples.ndjson",
    "candidate-health/deep-health-systemd.json",
    "candidate-health/deep-health-process.json",
    "candidate-health/deep-health-kernel.json",
    "candidate-health/deep-health-player-counters.json",
    "verified-marker.json",
    "service-after-restart/launcher-adoption.json",
    "service-after-restart/playback-deep-health-public.json",
    "service-after-restart/playback-samples.tsv",
    "service-after-restart/status-samples.ndjson",
    "service-after-restart/deep-health-systemd.json",
    "service-after-restart/deep-health-process.json",
    "service-after-restart/deep-health-kernel.json",
    "service-after-restart/deep-health-player-counters.json",
    "service-before-apply/launcher-adoption.json",
    "service-before-apply/playback-deep-health-public.json",
    "service-before-apply/playback-samples.tsv",
    "service-before-apply/status-samples.ndjson",
    "service-before-apply/deep-health-systemd.json",
    "service-before-apply/deep-health-process.json",
    "service-before-apply/deep-health-kernel.json",
    "service-before-apply/deep-health-player-counters.json",
    "service-after-rollback/launcher-adoption.json",
    "service-after-rollback/playback-deep-health-public.json",
    "service-after-rollback/playback-samples.tsv",
    "service-after-rollback/status-samples.ndjson",
    "service-after-rollback/deep-health-systemd.json",
    "service-after-rollback/deep-health-process.json",
    "service-after-rollback/deep-health-kernel.json",
    "service-after-rollback/deep-health-player-counters.json",
    "qa/evidence-gate.json",
    "qa/evidence-leak-scan.txt",
)

FORBIDDEN_BASENAMES = {
    ".env",
    "candidate-config.json",
    "config.json",
    "kiosk.log",
    "mpv.log",
    "playlist_last.json",
    "seed.json",
}

FORBIDDEN_SUFFIXES = (".tar.gz", ".tgz", ".log", ".key", ".token", ".secret")
FORBIDDEN_DIRS = {"raw", "extracted", "media_cache", "runtime", "state"}

LEAK_PATTERNS = (
    ("url", re.compile(r"https?://", re.I)),
    ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("mac", re.compile(r"\b[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}\b")),
    ("data_config_path", re.compile(r"/data/config\b")),
    ("data_media_path", re.compile(r"/data/media\b")),
    ("tmp_media_path", re.compile(r"/tmp/[^\s\"']+\.(?:mp4|mkv|mov|webm|avi|m4v)\b", re.I)),
    ("api_key", re.compile(r"api_key\s*[:=]", re.I)),
    ("authorization", re.compile(r"authorization\s*:", re.I)),
    ("bearer", re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]+", re.I)),
    ("password", re.compile(r"password\s*[:=]", re.I)),
    ("ssid", re.compile(r"ssid\s*[:=]", re.I)),
    ("environment_id", re.compile(r"environment_id\s*[:=]", re.I)),
)

PLAYBACK_SCHEMA = "dadooh.c18.playback.deep_health.v1"
UPDATE_MANIFEST_SCHEMA = "dadooh.totem.update.v1"
PLAYER_RUNTIME_MARKER_SCHEMA = "dadooh.c18.player_runtime.verified.v1"
PLAYER_RUNTIME_ADOPTION_SCHEMA = "dadooh.c18.player_runtime.adoption.v1"
RELEASE_GATE_SCHEMA = "dadooh.c18.player_runtime.release_gate.v1"
LAB_APPLY_SCHEMA = "dadooh.c18.player_runtime.lab_apply.v1"
LAB_ROLLBACK_SCHEMA = "dadooh.c18.player_runtime.lab_rollback.v1"

REQUIRED_HEALTH_CHECKS = (
    "samples_present",
    "service_active",
    "single_mpv",
    "mpv_path_c18_stack",
    "hwdec_expected_present",
    "hwdec_no_unexpected",
    "vo_configured_present",
    "vo_configured_no_unexpected",
    "ipc_success_present",
    "ipc_stable_after_success",
    "estimated_frame_present",
    "playback_progressed",
    "media_load_failed_present",
    "media_load_failed_zero",
    "mpv_restart_present",
    "mpv_restart_zero",
    "panfrost_faults_present",
    "panfrost_faults_zero",
    "mmc_timeout_reset_present",
    "mmc_timeout_reset_zero",
    "ext4_errors_present",
    "ext4_errors_zero",
    "nrestarts_delta_present",
    "nrestarts_stable",
    "status_no_failures",
)


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def allowed(rel_path: str) -> bool:
    return any(fnmatch.fnmatch(rel_path, pattern) for pattern in ALLOWED_PATTERNS)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{label}_read_error:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{label}_not_object")
        return {}
    return data


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def is_hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(rf"[0-9a-f]{{{length}}}", value))


def nested(data: dict[str, Any], *keys: str) -> Any:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def validate_evidence_manifest(run_dir: Path, files: list[str]) -> list[str]:
    errors: list[str] = []
    manifest_path = run_dir / "evidence-manifest.json"
    if not manifest_path.is_file():
        return ["missing_required:evidence-manifest.json"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"manifest_read_error:{type(exc).__name__}"]
    if not isinstance(manifest, dict):
        return ["manifest_not_object"]
    if manifest.get("schema") not in {
        "dadooh.c18.update_validation.evidence_manifest.v1",
        "dadooh.c18.player_runtime.evidence_manifest.v1",
    }:
        errors.append("manifest_invalid_schema")
    artifacts = manifest.get("artifacts")
    if artifacts is None:
        artifacts = manifest.get("files")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("manifest_missing_artifacts")
        return errors
    present = set(files)
    declared: list[str] = []
    for item in artifacts:
        if not isinstance(item, dict):
            errors.append("manifest_artifact_not_object")
            continue
        rel_path = str(item.get("file") or "")
        if not rel_path:
            errors.append("manifest_artifact_missing_file")
            continue
        if rel_path == "evidence-manifest.json":
            errors.append("manifest_must_not_hash_itself")
            continue
        if rel_path in declared:
            errors.append(f"manifest_artifact_duplicate:{rel_path}")
            continue
        declared.append(rel_path)
        if rel_path not in present:
            errors.append(f"manifest_artifact_missing:{rel_path}")
            continue
        path = run_dir / rel_path
        expected_bytes = item.get("bytes")
        expected_sha = item.get("sha256")
        if expected_bytes != path.stat().st_size:
            errors.append(f"manifest_artifact_bytes_mismatch:{rel_path}")
        if expected_sha != sha256_file(path):
            errors.append(f"manifest_artifact_sha_mismatch:{rel_path}")
    expected_declared = present - {"evidence-manifest.json"}
    if set(declared) != expected_declared:
        for rel_path in sorted(expected_declared - set(declared)):
            errors.append(f"manifest_artifact_undeclared:{rel_path}")
        for rel_path in sorted(set(declared) - expected_declared):
            errors.append(f"manifest_artifact_unexpected:{rel_path}")
    if not any(path.startswith("package/") and path.endswith(".manifest.json") for path in declared):
        errors.append("manifest_missing_package_manifest_artifact")
    if "verified-marker.json" not in declared:
        errors.append("manifest_missing_verified_marker_artifact")
    if "lab-apply.json" not in declared or "lab-rollback.json" not in declared:
        errors.append("manifest_missing_trial_operation_artifacts")
    for key in ("image_tag", "image_sha256", "image_marker_path", "image_marker_bytes", "image_marker_sha256"):
        if key not in manifest:
            errors.append(f"manifest_missing_{key}")
    if "image_tag" in manifest and (not isinstance(manifest.get("image_tag"), str) or not manifest.get("image_tag")):
        errors.append("manifest_invalid_image_tag")
    if "image_sha256" in manifest and not is_sha256(manifest.get("image_sha256")):
        errors.append("manifest_invalid_image_sha256")
    if ("image_tag" in manifest) != ("image_sha256" in manifest):
        errors.append("manifest_image_tag_sha_must_be_paired")
    if "image_marker_path" in manifest:
        marker_path = manifest.get("image_marker_path")
        marker_bytes = manifest.get("image_marker_bytes")
        marker_sha = manifest.get("image_marker_sha256")
        if not isinstance(marker_path, str) or not marker_path.startswith("/etc/dadooh/"):
            errors.append("manifest_invalid_image_marker_path")
        if not isinstance(marker_bytes, int) or marker_bytes <= 0:
            errors.append("manifest_invalid_image_marker_bytes")
        if not is_sha256(marker_sha):
            errors.append("manifest_invalid_image_marker_sha256")
    for key in ("repo_commit", "repo_tree", "repo_dirty"):
        if key not in manifest:
            errors.append(f"manifest_missing_{key}")
    if "repo_commit" in manifest and not is_hex(manifest.get("repo_commit"), 40):
        errors.append("manifest_invalid_repo_commit")
    if "repo_tree" in manifest and not is_hex(manifest.get("repo_tree"), 40):
        errors.append("manifest_invalid_repo_tree")
    if "repo_dirty" in manifest:
        if not isinstance(manifest.get("repo_dirty"), bool):
            errors.append("manifest_invalid_repo_dirty")
        elif manifest.get("repo_dirty") is not False:
            errors.append("manifest_repo_dirty")
    if "repo_exact_tag" in manifest and manifest.get("repo_exact_tag") is not None and not isinstance(manifest.get("repo_exact_tag"), str):
        errors.append("manifest_invalid_repo_exact_tag")
    return errors


def validate_repo_identity(evidence_manifest: dict[str, Any], package_manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    repo_commit = evidence_manifest.get("repo_commit")
    if not is_hex(repo_commit, 40):
        return errors
    evidence_source_commit = evidence_manifest.get("source_commit")
    package_source_commit = package_manifest.get("source_commit")
    if is_hex(evidence_source_commit, 40) and repo_commit != evidence_source_commit:
        errors.append("manifest_repo_commit_evidence_source_mismatch")
    if is_hex(package_source_commit, 40) and repo_commit != package_source_commit:
        errors.append("manifest_repo_commit_package_source_mismatch")
    return errors


def validate_package_contract(run_dir: Path) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    manifests = sorted((run_dir / "package").glob("*.manifest.json"))
    if len(manifests) != 1:
        return [f"package_manifest_count:{len(manifests)}"], {}
    manifest = load_json_object(manifests[0], "package_manifest", errors)
    if manifest.get("schema") != UPDATE_MANIFEST_SCHEMA:
        errors.append("package_manifest_schema")
    if manifest.get("component") != "player-runtime":
        errors.append("package_manifest_component")
    if manifest.get("channel") not in {"lab", "homologation"}:
        errors.append("package_manifest_channel")
    if not manifest.get("version"):
        errors.append("package_manifest_version")
    if not is_sha256(manifest.get("payload_sha256")):
        errors.append("package_manifest_payload_sha256")
    if not is_hex(manifest.get("source_commit"), 40):
        errors.append("package_manifest_source_commit")
    if not isinstance(manifest.get("created_at_utc"), str) or not manifest.get("created_at_utc"):
        errors.append("package_manifest_created_at_utc")
    requires = manifest.get("requires")
    if not isinstance(requires, dict):
        errors.append("package_manifest_requires")
    else:
        if requires.get("device_track") != "c18-hwdecode":
            errors.append("package_manifest_device_track")
        if requires.get("media_stack_id") != "c18-hwdecode-v4l2request-copy":
            errors.append("package_manifest_media_stack")
        if requires.get("mpv_wrapper") != "/opt/totem/bin/totem-mpv-hwdecode":
            errors.append("package_manifest_mpv_wrapper")
        if requires.get("hwdec") != "v4l2request-copy":
            errors.append("package_manifest_hwdec")
    gate = load_json_object(run_dir / "package" / "player-runtime-release-gate.json", "release_gate", errors)
    if gate.get("schema") != RELEASE_GATE_SCHEMA:
        errors.append("release_gate_schema")
    if gate.get("passed") is not True:
        errors.append("release_gate_not_passed")
    gate_payload = gate.get("payload")
    if not isinstance(gate_payload, dict):
        errors.append("release_gate_payload_missing")
    else:
        if not is_sha256(gate_payload.get("kiosk_py_sha256")):
            errors.append("release_gate_kiosk_py_sha256")
        if not is_sha256(gate_payload.get("tree_sha256")):
            errors.append("release_gate_tree_sha256")
    return errors, manifest


def validate_playback_summary(run_dir: Path, rel_path: str, label: str) -> list[str]:
    errors: list[str] = []
    data = load_json_object(run_dir / rel_path, label, errors)
    if data.get("schema") != PLAYBACK_SCHEMA:
        errors.append(f"{label}_schema")
    if data.get("passed") is not True:
        errors.append(f"{label}_not_passed")
    if data.get("failure_reasons") not in ([], None):
        errors.append(f"{label}_failure_reasons_not_empty")
    checks = data.get("checks")
    if not isinstance(checks, dict):
        errors.append(f"{label}_checks_missing")
    else:
        for key in REQUIRED_HEALTH_CHECKS:
            if checks.get(key) is not True:
                errors.append(f"{label}_check_failed:{key}")
    counters = data.get("counters")
    if not isinstance(counters, dict):
        errors.append(f"{label}_counters_missing")
    else:
        if int(counters.get("samples") or 0) <= 0:
            errors.append(f"{label}_samples_empty")
        positive_steps = int(counters.get("estimated_frame_positive_steps") if counters.get("estimated_frame_positive_steps") is not None else 0)
        required_steps = int(counters.get("estimated_frame_required_steps") if counters.get("estimated_frame_required_steps") is not None else 2)
        trailing_steps = int(counters.get("estimated_frame_trailing_nonprogress_steps") if counters.get("estimated_frame_trailing_nonprogress_steps") is not None else 999)
        if positive_steps < required_steps:
            errors.append(f"{label}_frame_steps_insufficient")
        if trailing_steps > 1:
            errors.append(f"{label}_frame_trailing_stall")
    return errors


def validate_marker(run_dir: Path, package_manifest: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    marker = load_json_object(run_dir / "verified-marker.json", "verified_marker", errors)
    if marker.get("schema") != PLAYER_RUNTIME_MARKER_SCHEMA:
        errors.append("verified_marker_schema")
    if marker.get("verdict") != "verified":
        errors.append("verified_marker_verdict")
    if package_manifest and marker.get("version") != package_manifest.get("version"):
        errors.append("verified_marker_version_mismatch")
    for key in ("payload_sha256", "kiosk_py_sha256", "tree_sha256"):
        if not is_sha256(marker.get(key)):
            errors.append(f"verified_marker_{key}")
    if nested(marker, "deep_health", "passed") is not True:
        errors.append("verified_marker_deep_health_not_passed")
    if nested(marker, "deep_health", "observed_kiosk_py_sha256") != marker.get("kiosk_py_sha256"):
        errors.append("verified_marker_observed_kiosk_mismatch")
    if nested(marker, "deep_health", "observed_tree_sha256") != marker.get("tree_sha256"):
        errors.append("verified_marker_observed_tree_mismatch")
    return errors, marker


def validate_lab_apply(run_dir: Path, package_manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    data = load_json_object(run_dir / "lab-apply.json", "lab_apply", errors)
    if data.get("schema") != LAB_APPLY_SCHEMA:
        errors.append("lab_apply_schema")
    if data.get("component") != "player-runtime":
        errors.append("lab_apply_component")
    if package_manifest and data.get("version") != package_manifest.get("version"):
        errors.append("lab_apply_version_mismatch")
    if data.get("rc") != 0 or data.get("passed") is not True:
        errors.append("lab_apply_not_passed")
    if data.get("device_data_root") is not True:
        errors.append("lab_apply_not_device_data_root")
    for field in ("public_cli_apply_still_frozen", "public_cli_reconcile_still_frozen"):
        freeze = data.get(field)
        if not isinstance(freeze, dict) or freeze.get("returncode") != 44 or freeze.get("frozen") is not True:
            errors.append(f"lab_apply_{field}_not_frozen")
    return errors


def validate_lab_rollback(run_dir: Path, package_manifest: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    data = load_json_object(run_dir / "lab-rollback.json", "lab_rollback", errors)
    if data.get("schema") != LAB_ROLLBACK_SCHEMA:
        errors.append("lab_rollback_schema")
    if data.get("component") != "player-runtime":
        errors.append("lab_rollback_component")
    if data.get("passed") is not True:
        errors.append("lab_rollback_not_passed")
    op = data.get("operation")
    if not isinstance(op, dict):
        errors.append("lab_rollback_operation_missing")
        return errors, data
    if op.get("action") != "rollback" or op.get("rc") != 0 or op.get("result") != "ok":
        errors.append("lab_rollback_operation_not_ok")
    if op.get("quarantine_current") is not True:
        errors.append("lab_rollback_quarantine_current_required")
    before = op.get("before")
    after = op.get("after")
    if not isinstance(before, dict) or not before.get("current_link"):
        errors.append("lab_rollback_missing_before_current")
    if package_manifest and isinstance(before, dict) and not str(before.get("current_link", "")).endswith(str(package_manifest.get("version"))):
        errors.append("lab_rollback_before_current_version_mismatch")
    if not isinstance(after, dict):
        errors.append("lab_rollback_missing_after")
    elif after.get("current_link") == (before or {}).get("current_link"):
        errors.append("lab_rollback_current_not_changed")
    if not op.get("rolled_back_to"):
        errors.append("lab_rollback_missing_rolled_back_to")
    for field in ("public_cli_apply_still_frozen", "public_cli_rollback_still_frozen", "public_cli_reconcile_still_frozen"):
        freeze = data.get(field)
        if not isinstance(freeze, dict) or freeze.get("returncode") != 44 or freeze.get("frozen") is not True:
            errors.append(f"lab_rollback_{field}_not_frozen")
    return errors, data


def validate_candidate_result(run_dir: Path, marker: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    data = load_json_object(run_dir / "candidate-health-result.json", "candidate_health_result", errors)
    if data.get("schema") != PLAYBACK_SCHEMA:
        errors.append("candidate_health_result_schema")
    if data.get("candidate_health_schema") != "dadooh.c18.player_runtime.candidate_health.v1":
        errors.append("candidate_health_result_candidate_schema")
    if data.get("passed") is not True:
        errors.append("candidate_health_result_not_passed")
    if marker:
        if data.get("observed_kiosk_py_sha256") != marker.get("kiosk_py_sha256"):
            errors.append("candidate_health_result_kiosk_mismatch")
        if data.get("observed_tree_sha256") != marker.get("tree_sha256"):
            errors.append("candidate_health_result_tree_mismatch")
    if not data.get("candidate_run_user") or data.get("candidate_run_user") == "root":
        errors.append("candidate_health_result_run_user_unsafe")
    return errors


def validate_adoption(run_dir: Path,
                      rel_path: str,
                      label: str,
                      expected_source: str,
                      expected_version: str | None) -> list[str]:
    errors: list[str] = []
    data = load_json_object(run_dir / rel_path, label, errors)
    if data.get("schema") != PLAYER_RUNTIME_ADOPTION_SCHEMA:
        errors.append(f"{label}_schema")
    if data.get("passed") is not True:
        errors.append(f"{label}_not_passed")
    if data.get("selected_source") != expected_source:
        errors.append(f"{label}_source_mismatch")
    if expected_version and data.get("selected_version") != expected_version:
        errors.append(f"{label}_version_mismatch")
    if expected_source == "data":
        if data.get("marker_valid") is not True:
            errors.append(f"{label}_marker_invalid")
        if data.get("running_identity_matches_marker") is not True:
            errors.append(f"{label}_identity_mismatch")
    return errors


def validate_semantics(run_dir: Path) -> list[str]:
    errors: list[str] = []
    evidence_manifest = load_json_object(run_dir / "evidence-manifest.json", "evidence_manifest", errors)
    readme = load_json_object(run_dir / "README.md", "readme", errors)
    rollback_expectation = (
        evidence_manifest.get("rollback_expectation")
        or readme.get("rollback_expectation")
        or "image-fallback-or-previous"
    )
    non_claims = readme.get("non_claims")
    if not isinstance(non_claims, list):
        errors.append("readme_non_claims_missing")
        non_claims = []
    for item in (
        "public_thaw",
        "github_publish",
        "auto_pull",
        "stable_or_production",
        "power_loss_safety",
        "cold_boot_adoption",
        "server_side_gate",
        "soak_endurance",
    ):
        if item not in non_claims:
            errors.append(f"readme_non_claim_missing:{item}")
    if rollback_expectation not in {"image-fallback-or-previous", "image-fallback", "data-previous"}:
        errors.append("rollback_expectation_invalid")
        rollback_expectation = "image-fallback-or-previous"
    package_errors, package_manifest = validate_package_contract(run_dir)
    errors.extend(package_errors)
    errors.extend(validate_repo_identity(evidence_manifest, package_manifest))
    marker_errors, marker = validate_marker(run_dir, package_manifest)
    errors.extend(marker_errors)
    release_gate = load_json_object(run_dir / "package" / "player-runtime-release-gate.json", "release_gate", errors)
    gate_payload = release_gate.get("payload") if isinstance(release_gate.get("payload"), dict) else {}
    if gate_payload:
        if gate_payload.get("kiosk_py_sha256") != marker.get("kiosk_py_sha256"):
            errors.append("release_gate_marker_kiosk_sha_mismatch")
        if gate_payload.get("tree_sha256") != marker.get("tree_sha256"):
            errors.append("release_gate_marker_tree_sha_mismatch")
    errors.extend(validate_lab_apply(run_dir, package_manifest))
    rollback_errors, rollback = validate_lab_rollback(run_dir, package_manifest)
    errors.extend(rollback_errors)
    errors.extend(validate_candidate_result(run_dir, marker))
    errors.extend(validate_playback_summary(run_dir, "candidate-health/playback-deep-health-public.json", "candidate_health"))
    before_adoption: dict[str, Any] = {}
    before_version: str | None = None
    before_tree: str | None = None
    if rollback_expectation == "data-previous":
        errors.extend(validate_playback_summary(run_dir, "service-before-apply/playback-deep-health-public.json", "service_before_apply"))
        errors.extend(validate_adoption(
            run_dir,
            "service-before-apply/launcher-adoption.json",
            "service_before_apply_adoption",
            "data",
            None,
        ))
        before_adoption = load_json_object(
            run_dir / "service-before-apply" / "launcher-adoption.json",
            "service_before_apply_adoption",
            errors,
        )
        before_version = before_adoption.get("selected_version") if isinstance(before_adoption.get("selected_version"), str) else None
        before_tree = before_adoption.get("marker_tree_sha256") if is_sha256(before_adoption.get("marker_tree_sha256")) else None
        if not before_version or before_version == "image_fallback":
            errors.append("data_previous_missing_before_version")
        if not before_tree:
            errors.append("data_previous_missing_before_tree_sha")
        if before_tree and marker.get("tree_sha256") == before_tree:
            errors.append("data_previous_candidate_tree_sha_matches_previous")
        lab_apply = load_json_object(run_dir / "lab-apply.json", "lab_apply", errors)
        apply_after = lab_apply.get("after") if isinstance(lab_apply.get("after"), dict) else {}
        previous_link = str(apply_after.get("previous_link") or "")
        state_previous_version = apply_after.get("state_previous_version")
        if before_version and not previous_link.endswith(before_version):
            errors.append("data_previous_apply_previous_link_mismatch")
        if before_version and state_previous_version != before_version:
            errors.append("data_previous_apply_previous_state_mismatch")
    errors.extend(validate_playback_summary(run_dir, "service-after-restart/playback-deep-health-public.json", "service_after_restart"))
    errors.extend(validate_playback_summary(run_dir, "service-after-rollback/playback-deep-health-public.json", "service_after_rollback"))
    expected_version = str(package_manifest.get("version")) if package_manifest else None
    errors.extend(validate_adoption(
        run_dir,
        "service-after-restart/launcher-adoption.json",
        "service_after_restart_adoption",
        "data",
        expected_version,
    ))
    rolled_to = nested(rollback, "operation", "rolled_back_to")
    if rollback_expectation == "image-fallback" and rolled_to != "image_fallback":
        errors.append("image_fallback_rollback_expected")
    if rollback_expectation == "data-previous":
        if not before_version:
            errors.append("data_previous_rollback_missing_before_version")
        elif rolled_to != before_version:
            errors.append("data_previous_rollback_target_mismatch")
        expected_rolled_to = nested(rollback, "operation", "expected_rolled_to")
        if expected_rolled_to != before_version:
            errors.append("data_previous_rollback_expectation_missing")
    rollback_expected_source = "fallback" if rolled_to == "image_fallback" else "data"
    rollback_expected_version = None if rollback_expected_source == "fallback" else str(rolled_to)
    errors.extend(validate_adoption(
        run_dir,
        "service-after-rollback/launcher-adoption.json",
        "service_after_rollback_adoption",
        rollback_expected_source,
        rollback_expected_version,
    ))
    return errors


def validate(run_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    files: list[str] = []
    if not run_dir.is_dir():
        return {
            "schema": SCHEMA,
            "passed": False,
            "errors": [f"run_dir_not_found:{run_dir}"],
            "files": [],
        }

    for path in sorted(run_dir.rglob("*")):
        rel_path = rel(path, run_dir)
        parts = set(Path(rel_path).parts)
        if path.is_dir():
            if parts & FORBIDDEN_DIRS:
                errors.append(f"forbidden_dir:{rel_path}")
            continue
        files.append(rel_path)
        if parts & FORBIDDEN_DIRS:
            errors.append(f"file_under_forbidden_dir:{rel_path}")
        if path.name in FORBIDDEN_BASENAMES:
            errors.append(f"forbidden_file:{rel_path}")
        if path.name.endswith(FORBIDDEN_SUFFIXES):
            errors.append(f"forbidden_suffix:{rel_path}")
        if not allowed(rel_path):
            errors.append(f"unexpected_file:{rel_path}")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"read_error:{rel_path}:{type(exc).__name__}")
            continue
        for label, pattern in LEAK_PATTERNS:
            if pattern.search(text):
                errors.append(f"leak_pattern:{label}:{rel_path}")

    required = {
        "README.md",
        "evidence-manifest.json",
        "lab-apply.json",
        "lab-rollback.json",
        "candidate-health-result.json",
        "candidate-health/playback-deep-health-public.json",
        "candidate-health/playback-samples.tsv",
        "candidate-health/status-samples.ndjson",
        "candidate-health/deep-health-systemd.json",
        "candidate-health/deep-health-process.json",
        "candidate-health/deep-health-kernel.json",
        "candidate-health/deep-health-player-counters.json",
        "verified-marker.json",
        "service-after-restart/launcher-adoption.json",
        "service-after-restart/playback-deep-health-public.json",
        "service-after-restart/playback-samples.tsv",
        "service-after-restart/status-samples.ndjson",
        "service-after-restart/deep-health-systemd.json",
        "service-after-restart/deep-health-process.json",
        "service-after-restart/deep-health-kernel.json",
        "service-after-restart/deep-health-player-counters.json",
        "service-after-rollback/launcher-adoption.json",
        "service-after-rollback/playback-deep-health-public.json",
        "service-after-rollback/playback-samples.tsv",
        "service-after-rollback/status-samples.ndjson",
        "service-after-rollback/deep-health-systemd.json",
        "service-after-rollback/deep-health-process.json",
        "service-after-rollback/deep-health-kernel.json",
        "service-after-rollback/deep-health-player-counters.json",
    }
    present = set(files)
    for rel_path in sorted(required - present):
        errors.append(f"missing_required:{rel_path}")
    errors.extend(validate_evidence_manifest(run_dir, files))
    if not errors:
        errors.extend(validate_semantics(run_dir))

    return {
        "schema": SCHEMA,
        "passed": not errors,
        "errors": errors,
        "files": files,
    }


def self_test() -> None:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="c18-evidence-gate-") as tmp:
        root = Path(tmp)
        run = root / "run"
        version = "c18.player-runtime-lab-self-test"
        payload_sha = "a" * 64
        kiosk_sha = "b" * 64
        tree_sha = "c" * 64
        source_commit = "d" * 40
        image_sha = "1" * 64
        image_marker_sha = "2" * 64

        def put(rel_path: str, payload: Any) -> None:
            path = run / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(payload, str):
                path.write_text(payload, encoding="utf-8")
            else:
                path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        checks = {key: True for key in REQUIRED_HEALTH_CHECKS}
        counters = {
            "samples": 4,
            "estimated_frame_positive_steps": 3,
            "estimated_frame_required_steps": 2,
            "estimated_frame_trailing_nonprogress_steps": 0,
        }
        health_summary = {
            "schema": PLAYBACK_SCHEMA,
            "passed": True,
            "failure_reasons": [],
            "checks": checks,
            "counters": counters,
        }
        package_manifest = {
            "schema": UPDATE_MANIFEST_SCHEMA,
            "component": "player-runtime",
            "version": version,
            "channel": "homologation",
            "created_at_utc": "2026-06-05T00:00:00Z",
            "source_commit": source_commit,
            "payload": "dadooh-player-runtime-self-test.tar.gz",
            "payload_sha256": payload_sha,
            "requires": {
                "device_track": "c18-hwdecode",
                "media_stack_id": "c18-hwdecode-v4l2request-copy",
                "mpv_wrapper": "/opt/totem/bin/totem-mpv-hwdecode",
                "hwdec": "v4l2request-copy",
            },
        }
        marker = {
            "schema": PLAYER_RUNTIME_MARKER_SCHEMA,
            "verdict": "verified",
            "version": version,
            "payload_sha256": payload_sha,
            "kiosk_py_sha256": kiosk_sha,
            "tree_sha256": tree_sha,
            "deep_health": {
                "passed": True,
                "observed_kiosk_py_sha256": kiosk_sha,
                "observed_tree_sha256": tree_sha,
            },
        }
        freeze = {"returncode": 44, "frozen": True}
        put("README.md", {
            "schema": "dadooh.c18.player_runtime.trial_readme.v1",
            "artifact_id": "self-test",
            "component": "player-runtime",
            "version": version,
            "scope": "lab-only persistent /data trial",
            "rollback_expectation": "image-fallback",
            "claims": [
                "local_package_apply",
                "verified_marker_adoption",
                "service_deep_health_after_restart",
                "rollback_to_image_fallback",
                "service_deep_health_after_rollback",
            ],
            "non_claims": [
                "public_thaw",
                "github_publish",
                "auto_pull",
                "stable_or_production",
                "power_loss_safety",
                "cold_boot_adoption",
                "server_side_gate",
                "soak_endurance",
                "rollback_A_to_B_previous_data_release",
            ],
        })
        put("package/dadooh-player-runtime-demo.manifest.json", package_manifest)
        put("package/player-runtime-release-gate.json", {
            "schema": RELEASE_GATE_SCHEMA,
            "passed": True,
            "payload": {
                "kiosk_py_sha256": kiosk_sha,
                "tree_sha256": tree_sha,
            },
        })
        put("lab-apply.json", {
            "schema": LAB_APPLY_SCHEMA,
            "component": "player-runtime",
            "version": version,
            "rc": 0,
            "passed": True,
            "device_data_root": True,
            "public_cli_apply_still_frozen": freeze,
            "public_cli_reconcile_still_frozen": freeze,
        })
        put("lab-rollback.json", {
            "schema": LAB_ROLLBACK_SCHEMA,
            "component": "player-runtime",
            "passed": True,
            "operation": {
                "action": "rollback",
                "rc": 0,
                "result": "ok",
                "quarantine_current": True,
                "rolled_back_to": "image_fallback",
                "before": {"current_link": f"releases/{version}", "previous_link": None},
                "after": {"current_link": None, "previous_link": None},
            },
            "public_cli_apply_still_frozen": freeze,
            "public_cli_rollback_still_frozen": freeze,
            "public_cli_reconcile_still_frozen": freeze,
        })
        put("candidate-health-result.json", {
            **health_summary,
            "candidate_health_schema": "dadooh.c18.player_runtime.candidate_health.v1",
            "observed_kiosk_py_sha256": kiosk_sha,
            "observed_tree_sha256": tree_sha,
            "candidate_run_user": "totem",
        })
        put("candidate-health/playback-deep-health-public.json", health_summary)
        put("service-after-restart/playback-deep-health-public.json", health_summary)
        put("service-after-rollback/playback-deep-health-public.json", health_summary)
        put("verified-marker.json", marker)
        put("service-after-restart/launcher-adoption.json", {
            "schema": PLAYER_RUNTIME_ADOPTION_SCHEMA,
            "passed": True,
            "selected_source": "data",
            "selected_version": version,
            "marker_valid": True,
            "running_identity_matches_marker": True,
        })
        put("service-after-rollback/launcher-adoption.json", {
            "schema": PLAYER_RUNTIME_ADOPTION_SCHEMA,
            "passed": True,
            "selected_source": "fallback",
            "selected_version": "image_fallback",
            "marker_valid": False,
            "running_identity_matches_marker": False,
        })
        for rel_path in (
            "candidate-health/playback-samples.tsv",
            "candidate-health/status-samples.ndjson",
            "candidate-health/deep-health-systemd.json",
            "candidate-health/deep-health-process.json",
            "candidate-health/deep-health-kernel.json",
            "candidate-health/deep-health-player-counters.json",
            "service-after-restart/playback-samples.tsv",
            "service-after-restart/status-samples.ndjson",
            "service-after-restart/deep-health-systemd.json",
            "service-after-restart/deep-health-process.json",
            "service-after-restart/deep-health-kernel.json",
            "service-after-restart/deep-health-player-counters.json",
            "service-after-rollback/playback-samples.tsv",
            "service-after-rollback/status-samples.ndjson",
            "service-after-rollback/deep-health-systemd.json",
            "service-after-rollback/deep-health-process.json",
            "service-after-rollback/deep-health-kernel.json",
            "service-after-rollback/deep-health-player-counters.json",
            "qa/evidence-leak-scan.txt",
        ):
            put(rel_path, "{}\n")
        def update_readme_expectation(expectation: str) -> None:
            readme = json.loads((run / "README.md").read_text(encoding="utf-8"))
            readme["rollback_expectation"] = expectation
            if expectation == "data-previous":
                readme["claims"] = [
                    "local_package_apply",
                    "verified_marker_adoption",
                    "service_deep_health_after_restart",
                    "rollback_to_data_previous",
                    "service_deep_health_after_rollback",
                ]
                readme["non_claims"] = [
                    "public_thaw",
                    "github_publish",
                    "auto_pull",
                    "stable_or_production",
                    "power_loss_safety",
                    "cold_boot_adoption",
                    "server_side_gate",
                    "soak_endurance",
                ]
            else:
                readme["claims"] = [
                    "local_package_apply",
                    "verified_marker_adoption",
                    "service_deep_health_after_restart",
                    "rollback_to_image_fallback",
                    "service_deep_health_after_rollback",
                ]
                readme["non_claims"] = [
                    "public_thaw",
                    "github_publish",
                    "auto_pull",
                    "stable_or_production",
                    "power_loss_safety",
                    "cold_boot_adoption",
                    "server_side_gate",
                    "soak_endurance",
                    "rollback_A_to_B_previous_data_release",
                ]
            (run / "README.md").write_text(json.dumps(readme, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        def refresh_manifest(rollback_expectation: str | None = None) -> None:
            artifacts = []
            for path in sorted(run.rglob("*")):
                if path.is_file() and rel(path, run) != "evidence-manifest.json":
                    artifacts.append({
                        "file": rel(path, run),
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    })
            manifest_payload = {
                "schema": "dadooh.c18.player_runtime.evidence_manifest.v1",
                "artifact_id": "self-test",
                "source_commit": source_commit,
                "image_tag": "c18-hwdecode-lab-self-test",
                "image_sha256": image_sha,
                "image_marker_path": "/etc/dadooh/c18-hwdecode-lab-self-test-image",
                "image_marker_bytes": 128,
                "image_marker_sha256": image_marker_sha,
                "repo_commit": source_commit,
                "repo_tree": "f" * 40,
                "repo_dirty": False,
                "repo_exact_tag": None,
                "artifacts": artifacts,
            }
            if rollback_expectation:
                manifest_payload["rollback_expectation"] = rollback_expectation
            (run / "evidence-manifest.json").write_text(
                json.dumps(manifest_payload, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )

        refresh_manifest("image-fallback")
        ok = validate(run)
        assert ok["passed"], ok
        previous_version = "self-test-previous"
        previous_tree_sha = "e" * 64
        update_readme_expectation("data-previous")
        for rel_path in (
            "service-before-apply/playback-samples.tsv",
            "service-before-apply/status-samples.ndjson",
            "service-before-apply/deep-health-systemd.json",
            "service-before-apply/deep-health-process.json",
            "service-before-apply/deep-health-kernel.json",
            "service-before-apply/deep-health-player-counters.json",
        ):
            put(rel_path, "{}\n")
        put("service-before-apply/playback-deep-health-public.json", health_summary)
        put("service-before-apply/launcher-adoption.json", {
            "schema": PLAYER_RUNTIME_ADOPTION_SCHEMA,
            "passed": True,
            "selected_source": "data",
            "selected_version": previous_version,
            "marker_valid": True,
            "marker_tree_sha256": previous_tree_sha,
            "running_identity_matches_marker": True,
        })
        lab_apply = json.loads((run / "lab-apply.json").read_text(encoding="utf-8"))
        lab_apply["after"] = {
            "previous_link": f"releases/{previous_version}",
            "state_previous_version": previous_version,
        }
        put("lab-apply.json", lab_apply)
        lab_rollback = json.loads((run / "lab-rollback.json").read_text(encoding="utf-8"))
        lab_rollback["operation"]["expected_rolled_to"] = previous_version
        refresh_manifest("data-previous")
        bad_previous = validate(run)
        assert not bad_previous["passed"], bad_previous
        assert any("data_previous_rollback_target_mismatch" in item for item in bad_previous["errors"]), bad_previous
        lab_rollback["operation"]["rolled_back_to"] = previous_version
        lab_rollback["operation"]["after"] = {
            "current_link": f"releases/{previous_version}",
            "previous_link": None,
        }
        put("lab-rollback.json", lab_rollback)
        put("service-after-rollback/launcher-adoption.json", {
            "schema": PLAYER_RUNTIME_ADOPTION_SCHEMA,
            "passed": True,
            "selected_source": "data",
            "selected_version": previous_version,
            "marker_valid": True,
            "running_identity_matches_marker": True,
        })
        refresh_manifest("data-previous")
        good_previous = validate(run)
        assert good_previous["passed"], good_previous
        manifest_missing_image = json.loads((run / "evidence-manifest.json").read_text(encoding="utf-8"))
        manifest_missing_image.pop("image_tag", None)
        (run / "evidence-manifest.json").write_text(
            json.dumps(manifest_missing_image, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        missing_image = validate(run)
        assert not missing_image["passed"], missing_image
        assert "manifest_missing_image_tag" in missing_image["errors"], missing_image
        refresh_manifest("data-previous")
        manifest_missing_repo = json.loads((run / "evidence-manifest.json").read_text(encoding="utf-8"))
        manifest_missing_repo.pop("repo_commit", None)
        (run / "evidence-manifest.json").write_text(
            json.dumps(manifest_missing_repo, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        missing_repo = validate(run)
        assert not missing_repo["passed"], missing_repo
        assert "manifest_missing_repo_commit" in missing_repo["errors"], missing_repo
        refresh_manifest("data-previous")
        manifest_with_repo_mismatch = json.loads((run / "evidence-manifest.json").read_text(encoding="utf-8"))
        manifest_with_repo_mismatch["repo_commit"] = "f" * 40
        (run / "evidence-manifest.json").write_text(
            json.dumps(manifest_with_repo_mismatch, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        repo_mismatch = validate(run)
        assert not repo_mismatch["passed"], repo_mismatch
        assert "manifest_repo_commit_package_source_mismatch" in repo_mismatch["errors"], repo_mismatch
        refresh_manifest("data-previous")
        manifest_with_dirty_repo = json.loads((run / "evidence-manifest.json").read_text(encoding="utf-8"))
        manifest_with_dirty_repo["repo_commit"] = "f" * 40
        manifest_with_dirty_repo["repo_tree"] = "1" * 40
        manifest_with_dirty_repo["repo_dirty"] = True
        (run / "evidence-manifest.json").write_text(
            json.dumps(manifest_with_dirty_repo, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        dirty_repo = validate(run)
        assert not dirty_repo["passed"], dirty_repo
        assert "manifest_repo_dirty" in dirty_repo["errors"], dirty_repo
        update_readme_expectation("image-fallback")
        lab_rollback["operation"]["rolled_back_to"] = "image_fallback"
        lab_rollback["operation"]["expected_rolled_to"] = None
        lab_rollback["operation"]["after"] = {"current_link": None, "previous_link": None}
        put("lab-rollback.json", lab_rollback)
        put("service-after-rollback/launcher-adoption.json", {
            "schema": PLAYER_RUNTIME_ADOPTION_SCHEMA,
            "passed": True,
            "selected_source": "fallback",
            "selected_version": "image_fallback",
            "marker_valid": False,
            "running_identity_matches_marker": False,
        })
        refresh_manifest("image-fallback")
        empty_health = run / "candidate-health" / "playback-deep-health-public.json"
        empty_health.write_text("{}\n", encoding="utf-8")
        refresh_manifest("image-fallback")
        empty_failed = validate(run)
        assert not empty_failed["passed"], empty_failed
        assert any("candidate_health_not_passed" in item or "candidate_health_schema" in item for item in empty_failed["errors"]), empty_failed
        empty_health.write_text(json.dumps(health_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        refresh_manifest("image-fallback")
        bad = run / "candidate-health" / "candidate-config.json"
        bad.write_text('{"api_key":"SECRET","media":"/data/media/private.mp4"}\n', encoding="utf-8")
        failed = validate(run)
        assert not failed["passed"], failed
        assert any("forbidden_file" in item for item in failed["errors"]), failed
        assert any("leak_pattern" in item for item in failed["errors"]), failed


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        if not args.json:
            print("self-test: ok")
        return 0
    if args.run_dir is None:
        print("missing --run-dir", file=sys.stderr)
        return 2
    result = validate(args.run_dir)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"evidence_gate_passed={str(bool(result['passed'])).lower()}")
        for error in result["errors"]:
            print(error, file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
