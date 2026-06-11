#!/usr/bin/env python3
"""Validate C18 player-runtime physical power-loss evidence.

This gate is intentionally narrower than the M6 evidence gate: it validates a
single operator-attended power-loss checkpoint directory. It does not claim
public thaw, stable/prod readiness, long soak, or full checkpoint coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.player_runtime.powerloss_evidence_gate.v1"
MANIFEST_SCHEMA = "dadooh.c18.powerloss.evidence_manifest.v1"
TRIAL_SCHEMA = "dadooh.c18.player_runtime.powerloss_trial.v1"
LAB_APPLY_SCHEMA = "dadooh.c18.player_runtime.lab_apply.v1"
LAB_ROLLBACK_SCHEMA = "dadooh.c18.player_runtime.lab_rollback.v1"
ADOPTION_SCHEMA = "dadooh.c18.player_runtime.adoption.v1"
PLAYBACK_SCHEMA = "dadooh.c18.playback.deep_health.v1"
POST_RECONCILE_STATE_SCHEMA = "dadooh.c18.player_runtime.powerloss.post_reconcile_state.v1"

PRIVATE_IP_RE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
SECRET_TEXT_PATTERNS = (
    ("github_token", re.compile(r"\b(?:github_pat_|gh[opsu]_[A-Za-z0-9_]{12,})")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I)),
    ("authorization_header", re.compile(r"\bAuthorization\s*:\s*\S+", re.I)),
    ("password_value", re.compile(r"\bpassword\s*[:=]\s*['\"]?[^'\"\s,}]+", re.I)),
)
SENSITIVE_KEY_PARTS = ("api_key", "token", "password", "secret", "ssid", "environment_id")

HEALTH_CHECKS = (
    "samples_present",
    "service_active",
    "single_mpv",
    "mpv_path_c18_stack",
    "hwdec_expected_present",
    "hwdec_no_unexpected",
    "estimated_frame_present",
    "playback_progressed",
    "media_load_failed_zero",
    "mpv_restart_zero",
    "panfrost_faults_zero",
    "panfrost_faults_delta_zero",
    "mmc_timeout_reset_zero",
    "ext4_errors_zero",
    "nrestarts_stable",
    "status_no_failures",
)
ALL_MATRIX_CHECKPOINTS = {
    "after_payload_staged",
    "after_release_dir_created",
    "after_extract",
    "after_state_verifying",
    "after_health_passed",
    "after_release_tree_fsync",
    "after_current_symlink",
    "after_marker_written",
    "after_previous_symlink",
    "after_state_success",
    "before_stage_cleanup",
    "rollback_after_identify_links",
    "rollback_after_current_to_previous",
    "rollback_after_previous_removed",
    "rollback_after_quarantine",
    "rollback_after_current_unlinked",
    "rollback_after_state_success",
}
APPLY_CHECKPOINTS = {
    "after_payload_staged",
    "after_release_dir_created",
    "after_extract",
    "after_state_verifying",
    "after_health_passed",
    "after_release_tree_fsync",
    "after_current_symlink",
    "after_marker_written",
    "after_previous_symlink",
    "after_state_success",
    "before_stage_cleanup",
}
SEMANTICALLY_VALIDATED_CHECKPOINTS = {
    "after_current_symlink",
    "after_marker_written",
    "after_previous_symlink",
    "rollback_after_current_to_previous",
    "rollback_after_previous_removed",
    "rollback_after_quarantine",
    "rollback_after_state_success",
}
POSTCHECK_REQUIRED_CHECKPOINTS = {
    "rollback_after_previous_removed",
    "rollback_after_quarantine",
    "rollback_after_state_success",
}
SUMMARY_PREVIOUS_LINK_ALLOWED_CHECKPOINTS = {
    "after_current_symlink",
    "after_marker_written",
    "after_previous_symlink",
    "rollback_after_current_to_previous",
}


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{label}_json_error:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{label}_not_object")
        return {}
    return data


def nested(data: dict[str, Any], *keys: str) -> Any:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def link_version(link: Any) -> str | None:
    if not isinstance(link, str) or not link:
        return None
    return link.rsplit("/", 1)[-1]


def sensitive_json_values(value: Any, *, key_path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            lower = str(key).lower()
            if any(part in lower for part in SENSITIVE_KEY_PARTS):
                if child not in ("", None, [], {}, "null"):
                    hits.append(child_path)
            hits.extend(sensitive_json_values(child, key_path=child_path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            hits.extend(sensitive_json_values(child, key_path=f"{key_path}[{idx}]"))
    return hits


def validate_files(run_dir: Path, errors: list[str]) -> list[str]:
    files: list[str] = []
    for path in sorted(run_dir.rglob("*")):
        rel_path = rel(path, run_dir)
        if path.is_symlink():
            errors.append(f"symlink_not_allowed:{rel_path}")
            continue
        if path.is_dir():
            continue
        files.append(rel_path)
        if path.stat().st_size == 0:
            errors.append(f"zero_size_file:{rel_path}")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"read_error:{rel_path}:{type(exc).__name__}")
            continue
        if PRIVATE_IP_RE.search(text):
            errors.append(f"private_ip_leak:{rel_path}")
        for label, pattern in SECRET_TEXT_PATTERNS:
            if pattern.search(text):
                errors.append(f"secret_pattern:{label}:{rel_path}")
        if path.suffix == ".json":
            data = load_json(path, errors, rel_path)
            for hit in sensitive_json_values(data):
                errors.append(f"sensitive_json_value:{rel_path}:{hit}")
        elif path.suffix == ".ndjson":
            for line_no, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    json.loads(line)
                except Exception as exc:
                    errors.append(f"ndjson_parse_error:{rel_path}:{line_no}:{type(exc).__name__}")
                    break
    return files


def validate_manifest(run_dir: Path, files: list[str], errors: list[str]) -> dict[str, Any]:
    manifest = load_json(run_dir / "evidence-manifest.json", errors, "evidence_manifest")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        errors.append("manifest_schema")
    for key in ("artifact_id", "component", "checkpoint", "board_image_marker", "source_commit"):
        if not isinstance(manifest.get(key), str) or not manifest.get(key):
            errors.append(f"manifest_missing_{key}")
    if manifest.get("component") != "player-runtime":
        errors.append("manifest_component")
    if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("source_commit", ""))):
        errors.append("manifest_source_commit")
    artifacts = manifest.get("files")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("manifest_files_missing")
        return manifest
    declared: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            errors.append("manifest_file_entry_not_object")
            continue
        name = item.get("file")
        if not isinstance(name, str) or not name or name.startswith("/") or ".." in Path(name).parts:
            errors.append(f"manifest_bad_file:{name}")
            continue
        declared[name] = item
        path = run_dir / name
        if not path.is_file():
            errors.append(f"manifest_file_missing:{name}")
            continue
        if item.get("bytes") != path.stat().st_size:
            errors.append(f"manifest_bytes_mismatch:{name}")
        if item.get("sha256") != sha256_file(path):
            errors.append(f"manifest_sha256_mismatch:{name}")
    actual = set(files) - {"evidence-manifest.json"}
    declared_set = set(declared)
    for extra in sorted(actual - declared_set):
        errors.append(f"manifest_undeclared_file:{extra}")
    for missing in sorted(declared_set - actual):
        errors.append(f"manifest_declared_absent:{missing}")
    return manifest


def validate_freeze(data: dict[str, Any], label: str, errors: list[str]) -> None:
    for field in (
        "public_cli_apply_still_frozen",
        "public_cli_rollback_still_frozen",
        "public_cli_reconcile_still_frozen",
    ):
        if field not in data and field == "public_cli_rollback_still_frozen":
            continue
        value = data.get(field)
        if not isinstance(value, dict):
            errors.append(f"{label}_{field}_missing")
        elif value.get("returncode") != 44 or value.get("frozen") is not True:
            errors.append(f"{label}_{field}_not_frozen")


def validate_adoption(data: dict[str, Any],
                      label: str,
                      errors: list[str],
                      *,
                      expected_source: str,
                      expected_version: str | None) -> None:
    if data.get("schema") != ADOPTION_SCHEMA:
        errors.append(f"{label}_schema")
    if data.get("passed") is not True:
        errors.append(f"{label}_not_passed")
    if data.get("selected_source") != expected_source:
        errors.append(f"{label}_source")
    if expected_version and data.get("selected_version") != expected_version:
        errors.append(f"{label}_version")
    if expected_source == "data":
        if data.get("marker_valid") is not True:
            errors.append(f"{label}_marker_invalid")
        if data.get("running_identity_matches_marker") is not True:
            errors.append(f"{label}_identity_mismatch")


def validate_health(data: dict[str, Any], label: str, errors: list[str]) -> None:
    if data.get("schema") != PLAYBACK_SCHEMA:
        errors.append(f"{label}_schema")
    if data.get("passed") is not True:
        errors.append(f"{label}_not_passed")
    if data.get("failure_reasons") not in ([], None):
        errors.append(f"{label}_failure_reasons")
    checks = data.get("checks")
    if not isinstance(checks, dict):
        errors.append(f"{label}_checks_missing")
        return
    for check in HEALTH_CHECKS:
        if check not in checks:
            errors.append(f"{label}_check_missing:{check}")
        elif checks.get(check) is not True:
            errors.append(f"{label}_check_failed:{check}")


def validate_adoption_sidecar(run_dir: Path,
                              rel_path: str,
                              summary_data: dict[str, Any],
                              label: str,
                              errors: list[str],
                              *,
                              expected_source: str,
                              expected_version: str | None) -> None:
    sidecar = load_json(run_dir / rel_path, errors, label)
    validate_adoption(sidecar, label, errors, expected_source=expected_source, expected_version=expected_version)
    if sidecar != summary_data:
        errors.append(f"{label}_summary_sidecar_mismatch")


def validate_setup(run_dir: Path, manifest: dict[str, Any], errors: list[str]) -> None:
    if manifest.get("checkpoint") in APPLY_CHECKPOINTS and not (run_dir / "setup" / "lab-apply.json").exists():
        return
    candidate = manifest.get("setup_candidate_version")
    expected = manifest.get("expected_active_version")
    apply_data = load_json(run_dir / "setup" / "lab-apply.json", errors, "setup_lab_apply")
    if apply_data.get("schema") != LAB_APPLY_SCHEMA:
        errors.append("setup_lab_apply_schema")
    if apply_data.get("passed") is not True or apply_data.get("rc") != 0:
        errors.append("setup_lab_apply_not_passed")
    if candidate and apply_data.get("version") != candidate:
        errors.append("setup_lab_apply_candidate_mismatch")
    if nested(apply_data, "after", "state_current_version") != candidate:
        errors.append("setup_after_state_current_not_candidate")
    if expected and nested(apply_data, "after", "state_previous_version") != expected:
        errors.append("setup_after_state_previous_not_expected")
    validate_freeze(apply_data, "setup_lab_apply", errors)

    adoption = load_json(run_dir / "setup" / "service-adoption.json", errors, "setup_service_adoption")
    validate_adoption(adoption, "setup_service_adoption", errors, expected_source="data", expected_version=candidate)
    service_health = load_json(
        run_dir / "setup" / "apply" / "candidate-health" / "health" / "playback-deep-health-public.json",
        errors,
        "setup_candidate_health",
    )
    validate_health(service_health, "setup_candidate_health", errors)


def validate_rollback_previous_removed(checkpoint: dict[str, Any],
                                       summary: dict[str, Any],
                                       manifest: dict[str, Any],
                                       errors: list[str]) -> None:
    expected = manifest.get("expected_active_version")
    candidate = manifest.get("setup_candidate_version")
    runtime = checkpoint.get("runtime_snapshot") if isinstance(checkpoint.get("runtime_snapshot"), dict) else {}
    context = checkpoint.get("context") if isinstance(checkpoint.get("context"), dict) else {}
    if link_version(runtime.get("current_link")) != expected:
        errors.append("checkpoint_current_not_expected_active")
    if runtime.get("previous_link") is not None:
        errors.append("checkpoint_previous_link_should_be_absent")
    if runtime.get("state_current_version") != candidate:
        errors.append("checkpoint_state_current_should_still_be_candidate")
    if runtime.get("state_previous_version") != expected:
        errors.append("checkpoint_state_previous_should_still_be_expected")
    if link_version(context.get("current")) != expected:
        errors.append("checkpoint_context_current_not_expected")
    if link_version(context.get("previous")) != candidate:
        errors.append("checkpoint_context_previous_not_candidate")
    if manifest.get("rollback_expectation") != "data-current-after-previous-removed":
        errors.append("manifest_rollback_expectation")
    if summary.get("restore_rollback") is not None:
        errors.append("summary_restore_rollback_unexpected")


def validate_after_current_symlink(checkpoint: dict[str, Any],
                                   manifest: dict[str, Any],
                                   errors: list[str]) -> None:
    runtime = checkpoint.get("runtime_snapshot") if isinstance(checkpoint.get("runtime_snapshot"), dict) else {}
    context = checkpoint.get("context") if isinstance(checkpoint.get("context"), dict) else {}
    last_operation = runtime.get("last_operation") if isinstance(runtime.get("last_operation"), dict) else {}
    context_version = context.get("version") or link_version(context.get("current"))
    expected = manifest.get("expected_active_version") or context_version
    if checkpoint.get("action") != "apply":
        errors.append("checkpoint_action_not_apply")
    if not isinstance(expected, str) or not expected:
        errors.append("checkpoint_expected_version_missing")
    if context_version != expected:
        errors.append("checkpoint_context_version_not_expected")
    if link_version(runtime.get("current_link")) != expected:
        errors.append("checkpoint_current_not_expected_active")
    # This checkpoint is intentionally between symlink flip and state success.
    if runtime.get("state_current_version") == expected:
        errors.append("checkpoint_state_already_promoted")
    if last_operation.get("type") != "apply" or last_operation.get("status") != "verifying":
        errors.append("checkpoint_last_operation_not_verifying_apply")
    if last_operation.get("version") != expected:
        errors.append("checkpoint_last_operation_version_mismatch")


def validate_rollback_current_to_previous(checkpoint: dict[str, Any],
                                          manifest: dict[str, Any],
                                          errors: list[str]) -> None:
    expected = manifest.get("expected_active_version")
    candidate = manifest.get("setup_candidate_version")
    runtime = checkpoint.get("runtime_snapshot") if isinstance(checkpoint.get("runtime_snapshot"), dict) else {}
    context = checkpoint.get("context") if isinstance(checkpoint.get("context"), dict) else {}
    if checkpoint.get("action") != "rollback":
        errors.append("checkpoint_action_not_rollback")
    if not isinstance(expected, str) or not expected:
        errors.append("manifest_expected_active_version_missing")
    if not isinstance(candidate, str) or not candidate:
        errors.append("manifest_setup_candidate_version_missing")
    if link_version(runtime.get("current_link")) != expected:
        errors.append("checkpoint_current_not_expected_active")
    if link_version(runtime.get("previous_link")) != expected:
        errors.append("checkpoint_previous_link_not_old_previous")
    if runtime.get("state_current_version") != candidate:
        errors.append("checkpoint_state_current_should_still_be_candidate")
    if runtime.get("state_previous_version") != expected:
        errors.append("checkpoint_state_previous_should_still_be_expected")
    if link_version(context.get("current")) != expected:
        errors.append("checkpoint_context_current_not_expected")
    if link_version(context.get("previous")) != candidate:
        errors.append("checkpoint_context_previous_not_candidate")
def validate_rollback_after_quarantine(run_dir: Path,
                                       checkpoint: dict[str, Any],
                                       summary: dict[str, Any],
                                       manifest: dict[str, Any],
                                       errors: list[str]) -> None:
    expected = manifest.get("expected_active_version")
    candidate = manifest.get("setup_candidate_version")
    runtime = checkpoint.get("runtime_snapshot") if isinstance(checkpoint.get("runtime_snapshot"), dict) else {}
    context = checkpoint.get("context") if isinstance(checkpoint.get("context"), dict) else {}
    quarantined = context.get("quarantined") if isinstance(context.get("quarantined"), dict) else {}
    if link_version(runtime.get("current_link")) != expected:
        errors.append("checkpoint_current_not_expected_active")
    if runtime.get("previous_link") is not None:
        errors.append("checkpoint_previous_link_should_be_absent")
    if runtime.get("state_current_version") != candidate:
        errors.append("checkpoint_state_current_should_still_be_candidate")
    if runtime.get("state_previous_version") != expected:
        errors.append("checkpoint_state_previous_should_still_be_expected")
    if link_version(context.get("current")) != expected:
        errors.append("checkpoint_context_current_not_expected")
    if quarantined.get("version") != candidate:
        errors.append("checkpoint_quarantined_not_candidate")
    for key in ("payload_sha256", "tree_sha256", "kiosk_py_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(quarantined.get(key, ""))):
            errors.append(f"checkpoint_quarantined_{key}_missing")
    if manifest.get("rollback_expectation") != "data-current-after-quarantine":
        errors.append("manifest_rollback_expectation")
    if summary.get("restore_rollback") is not None:
        errors.append("summary_restore_rollback_unexpected")

    post_state = load_json(
        run_dir / "trial" / "resume" / "post-reconcile-state.json",
        errors,
        "post_reconcile_state",
    )
    if post_state.get("schema") != POST_RECONCILE_STATE_SCHEMA:
        errors.append("post_reconcile_state_schema")
    if post_state.get("current_version") != expected:
        errors.append("post_reconcile_state_current")
    if post_state.get("expected_quarantine_version") != candidate:
        errors.append("post_reconcile_state_expected_quarantine")
    if post_state.get("quarantine_match_present") is not True:
        errors.append("post_reconcile_state_quarantine_missing")
    quarantine_match = post_state.get("quarantine_match") if isinstance(post_state.get("quarantine_match"), dict) else {}
    if quarantine_match.get("version") != candidate:
        errors.append("post_reconcile_state_quarantine_version")
    for key in ("payload_sha256", "tree_sha256", "kiosk_py_sha256"):
        if quarantined.get(key) != quarantine_match.get(key):
            errors.append(f"post_reconcile_state_quarantine_{key}_mismatch")


def validate_rollback_after_state_success(run_dir: Path,
                                          checkpoint: dict[str, Any],
                                          summary: dict[str, Any],
                                          manifest: dict[str, Any],
                                          errors: list[str]) -> None:
    expected = manifest.get("expected_active_version")
    candidate = manifest.get("setup_candidate_version")
    runtime = checkpoint.get("runtime_snapshot") if isinstance(checkpoint.get("runtime_snapshot"), dict) else {}
    context = checkpoint.get("context") if isinstance(checkpoint.get("context"), dict) else {}
    last_operation = runtime.get("last_operation") if isinstance(runtime.get("last_operation"), dict) else {}
    if link_version(runtime.get("current_link")) != expected:
        errors.append("checkpoint_current_not_expected_active")
    if runtime.get("previous_link") is not None:
        errors.append("checkpoint_previous_link_should_be_absent")
    if runtime.get("state_current_version") != expected:
        errors.append("checkpoint_state_current_not_expected")
    if runtime.get("state_previous_version") is not None:
        errors.append("checkpoint_state_previous_should_be_absent")
    if link_version(context.get("current")) != expected:
        errors.append("checkpoint_context_current_not_expected")
    if last_operation.get("type") != "rollback" or last_operation.get("status") != "success":
        errors.append("checkpoint_last_operation_not_successful_rollback")
    if last_operation.get("rolled_back_to") != expected:
        errors.append("checkpoint_last_operation_rolled_to_mismatch")
    if last_operation.get("quarantined_current") is not True:
        errors.append("checkpoint_last_operation_missing_quarantine")
    if manifest.get("rollback_expectation") != "data-current-after-state-success":
        errors.append("manifest_rollback_expectation")
    if summary.get("restore_rollback") is not None:
        errors.append("summary_restore_rollback_unexpected")
    if (run_dir / "trial" / "arm-timeout.json").exists():
        errors.append("arm_timeout_present")
    if (run_dir / "trial" / "arm-result.json").exists():
        errors.append("arm_result_present")

    post_state = load_json(
        run_dir / "trial" / "resume" / "post-reconcile-state.json",
        errors,
        "post_reconcile_state",
    )
    if post_state.get("schema") != POST_RECONCILE_STATE_SCHEMA:
        errors.append("post_reconcile_state_schema")
    if post_state.get("current_version") != expected:
        errors.append("post_reconcile_state_current")
    if post_state.get("previous_version") is not None:
        errors.append("post_reconcile_state_previous_should_be_absent")
    if post_state.get("expected_quarantine_version") != candidate:
        errors.append("post_reconcile_state_expected_quarantine")
    if post_state.get("quarantine_match_present") is not True:
        errors.append("post_reconcile_state_quarantine_missing")
    quarantine_match = post_state.get("quarantine_match") if isinstance(post_state.get("quarantine_match"), dict) else {}
    if quarantine_match.get("version") != candidate:
        errors.append("post_reconcile_state_quarantine_version")
    checkpoint_quarantine = {}
    for entry in runtime.get("quarantine") if isinstance(runtime.get("quarantine"), list) else []:
        if isinstance(entry, dict) and entry.get("version") == candidate:
            checkpoint_quarantine = entry
            break
    if not checkpoint_quarantine:
        errors.append("checkpoint_quarantine_candidate_missing")
    for key in ("payload_sha256", "tree_sha256", "kiosk_py_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(quarantine_match.get(key, ""))):
            errors.append(f"post_reconcile_state_quarantine_{key}_missing")
        if checkpoint_quarantine and checkpoint_quarantine.get(key) != quarantine_match.get(key):
            errors.append(f"post_reconcile_state_quarantine_{key}_mismatch")


def validate_boot_transition(checkpoint: dict[str, Any],
                             summary: dict[str, Any],
                             errors: list[str]) -> None:
    pre = checkpoint.get("boot_state_at_checkpoint") if isinstance(checkpoint.get("boot_state_at_checkpoint"), dict) else {}
    post = summary.get("boot_state_at_resume") if isinstance(summary.get("boot_state_at_resume"), dict) else {}
    pre_boot = pre.get("boot_id")
    post_boot = post.get("boot_id")
    if not isinstance(pre_boot, str) or not pre_boot:
        errors.append("boot_state_pre_boot_id_missing")
    if not isinstance(post_boot, str) or not post_boot:
        errors.append("boot_state_post_boot_id_missing")
    if isinstance(pre_boot, str) and isinstance(post_boot, str) and pre_boot == post_boot:
        errors.append("boot_state_boot_id_not_changed")
    pre_btime = pre.get("btime")
    post_btime = post.get("btime")
    if not isinstance(pre_btime, int):
        errors.append("boot_state_pre_btime_missing")
    if not isinstance(post_btime, int):
        errors.append("boot_state_post_btime_missing")
    if isinstance(pre_btime, int) and isinstance(post_btime, int) and post_btime < pre_btime:
        errors.append("boot_state_btime_regressed")
    post_uptime = post.get("uptime_sec")
    if not isinstance(post_uptime, (int, float)):
        errors.append("boot_state_post_uptime_missing")


def validate_semantics(run_dir: Path, manifest: dict[str, Any], errors: list[str]) -> None:
    trial_prefix = "trial" if (run_dir / "trial" / "powerloss-checkpoint" / "checkpoint.json").is_file() else ""
    def evidence_path(rel_path: str) -> Path:
        return run_dir / trial_prefix / rel_path if trial_prefix else run_dir / rel_path

    checkpoint = load_json(evidence_path("powerloss-checkpoint/checkpoint.json"), errors, "checkpoint")
    summary = load_json(evidence_path("powerloss-summary.json"), errors, "powerloss_summary")
    reconcile = load_json(evidence_path("resume/reconcile.json"), errors, "resume_reconcile")
    expected = manifest.get("expected_active_version")
    if not expected and manifest.get("checkpoint") == "after_current_symlink":
        context = checkpoint.get("context") if isinstance(checkpoint.get("context"), dict) else {}
        expected = context.get("version") or link_version(context.get("current"))

    if checkpoint.get("schema") != TRIAL_SCHEMA or summary.get("schema") != TRIAL_SCHEMA:
        errors.append("trial_schema")
    if checkpoint.get("checkpoint") != manifest.get("checkpoint"):
        errors.append("checkpoint_manifest_mismatch")
    if manifest.get("checkpoint") not in ALL_MATRIX_CHECKPOINTS:
        errors.append(f"unsupported_checkpoint:{manifest.get('checkpoint')}")
    elif manifest.get("checkpoint") not in SEMANTICALLY_VALIDATED_CHECKPOINTS:
        errors.append(f"checkpoint_semantics_not_implemented:{manifest.get('checkpoint')}")
    if checkpoint.get("operator_instruction") != "CUT_POWER_NOW":
        errors.append("checkpoint_operator_instruction")
    if summary.get("passed") is not True:
        errors.append("summary_not_passed")
    before = summary.get("before_reconcile") if isinstance(summary.get("before_reconcile"), dict) else {}
    after = summary.get("after_reconcile") if isinstance(summary.get("after_reconcile"), dict) else {}
    validate_adoption(before, "before_reconcile", errors, expected_source="data", expected_version=expected)
    validate_adoption(after, "after_reconcile", errors, expected_source="data", expected_version=expected)
    validate_adoption_sidecar(
        run_dir,
        f"{trial_prefix + '/' if trial_prefix else ''}resume/before-reconcile-adoption.json",
        before,
        "before_reconcile_adoption_sidecar",
        errors,
        expected_source="data",
        expected_version=expected,
    )
    validate_adoption_sidecar(
        run_dir,
        f"{trial_prefix + '/' if trial_prefix else ''}resume/after-reconcile-adoption.json",
        after,
        "after_reconcile_adoption_sidecar",
        errors,
        expected_source="data",
        expected_version=expected,
    )
    checkpoint_name = manifest.get("checkpoint")
    if (
        checkpoint_name not in SUMMARY_PREVIOUS_LINK_ALLOWED_CHECKPOINTS
        and (before.get("previous_link") is not None or after.get("previous_link") is not None)
    ):
        errors.append("summary_previous_link_should_be_absent")
    if summary.get("before_reconcile_health_passed") is not True:
        errors.append("before_reconcile_health_not_passed")
    if summary.get("after_reconcile_health_passed") is not True:
        errors.append("after_reconcile_health_not_passed")
    if reconcile.get("schema") != LAB_ROLLBACK_SCHEMA:
        errors.append("resume_reconcile_schema")
    if reconcile.get("passed") is not True:
        errors.append("resume_reconcile_not_passed")
    if nested(reconcile, "operation", "result") != "current_verified":
        errors.append("resume_reconcile_result")
    validate_freeze(reconcile, "resume_reconcile", errors)
    validate_health(
        load_json(
            run_dir / "trial" / "resume" / "before-reconcile-health" / "playback-deep-health-public.json",
            errors,
            "before_reconcile_health",
        ) if trial_prefix else load_json(
            run_dir / "resume" / "before-reconcile-health" / "playback-deep-health-public.json",
            errors,
            "before_reconcile_health",
        ),
        "before_reconcile_health",
        errors,
    )
    validate_health(
        load_json(
            run_dir / "trial" / "resume" / "after-reconcile-health" / "playback-deep-health-public.json",
            errors,
            "after_reconcile_health",
        ) if trial_prefix else load_json(
            run_dir / "resume" / "after-reconcile-health" / "playback-deep-health-public.json",
            errors,
            "after_reconcile_health",
        ),
        "after_reconcile_health",
        errors,
    )
    if manifest.get("checkpoint") == "after_current_symlink":
        validate_after_current_symlink(checkpoint, manifest, errors)
    elif manifest.get("checkpoint") == "rollback_after_current_to_previous":
        validate_rollback_current_to_previous(checkpoint, manifest, errors)
    elif manifest.get("checkpoint") == "rollback_after_previous_removed":
        validate_rollback_previous_removed(checkpoint, summary, manifest, errors)
    elif manifest.get("checkpoint") == "rollback_after_quarantine":
        validate_rollback_after_quarantine(run_dir, checkpoint, summary, manifest, errors)
    elif manifest.get("checkpoint") == "rollback_after_state_success":
        validate_boot_transition(checkpoint, summary, errors)
        validate_rollback_after_state_success(run_dir, checkpoint, summary, manifest, errors)

    postcheck = run_dir / "postcheck.txt"
    if not postcheck.is_file():
        if manifest.get("checkpoint") in POSTCHECK_REQUIRED_CHECKPOINTS:
            errors.append("postcheck_missing")
    else:
        text = postcheck.read_text(encoding="utf-8", errors="replace")
        for required in (
            "BOOT_ID=",
            "UPTIME=",
            "SERVICE_ACTIVE=active",
            "TIMER_ENABLED=disabled",
            "STRICT_GPU_FAULTS=0",
            "PUBLIC_PLAYER_RUNTIME_APPLY_LOCAL_RC=44",
            "PUBLIC_PLAYER_RUNTIME_ROLLBACK_RC=44",
            "PUBLIC_PLAYER_RUNTIME_RECONCILE_RC=44",
        ):
            if required not in text:
                errors.append(f"postcheck_missing:{required}")


def validate(run_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    if not run_dir.is_dir():
        return {"schema": SCHEMA, "passed": False, "errors": [f"run_dir_not_found:{run_dir}"], "files": []}
    files = validate_files(run_dir, errors)
    manifest = validate_manifest(run_dir, files, errors)
    validate_setup(run_dir, manifest, errors)
    validate_semantics(run_dir, manifest, errors)
    return {
        "schema": SCHEMA,
        "passed": not errors,
        "errors": errors,
        "run_dir": str(run_dir),
        "checkpoint": manifest.get("checkpoint"),
        "files": sorted(files),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def make_health() -> dict[str, Any]:
    return {
        "schema": PLAYBACK_SCHEMA,
        "passed": True,
        "failure_reasons": [],
        "checks": {key: True for key in HEALTH_CHECKS},
    }


def write_fixture(root: Path) -> None:
    expected = "runtime-a"
    candidate = "runtime-b"
    write_json(root / "setup/lab-apply.json", {
        "schema": LAB_APPLY_SCHEMA,
        "passed": True,
        "rc": 0,
        "version": candidate,
        "after": {"state_current_version": candidate, "state_previous_version": expected},
        "public_cli_apply_still_frozen": {"returncode": 44, "frozen": True},
        "public_cli_reconcile_still_frozen": {"returncode": 44, "frozen": True},
    })
    adoption = {
        "schema": ADOPTION_SCHEMA,
        "passed": True,
        "selected_source": "data",
        "selected_version": candidate,
        "marker_valid": True,
        "running_identity_matches_marker": True,
    }
    write_json(root / "setup/service-adoption.json", adoption)
    write_json(root / "setup/apply/candidate-health/health/playback-deep-health-public.json", make_health())
    checkpoint = {
        "schema": TRIAL_SCHEMA,
        "action": "rollback",
        "checkpoint": "rollback_after_previous_removed",
        "operator_instruction": "CUT_POWER_NOW",
        "context": {"current": f"releases/{expected}", "previous": f"releases/{candidate}"},
        "runtime_snapshot": {
            "current_link": f"releases/{expected}",
            "previous_link": None,
            "state_current_version": candidate,
            "state_previous_version": expected,
        },
    }
    write_json(root / "trial/powerloss-checkpoint/checkpoint.json", checkpoint)
    a_adoption = dict(adoption, selected_version=expected, previous_link=None)
    write_json(root / "trial/resume/before-reconcile-adoption.json", a_adoption)
    write_json(root / "trial/resume/after-reconcile-adoption.json", a_adoption)
    for label in ("before", "after"):
        write_json(root / f"trial/resume/{label}-reconcile-health/playback-deep-health-public.json", make_health())
    reconcile = {
        "schema": LAB_ROLLBACK_SCHEMA,
        "passed": True,
        "operation": {"result": "current_verified"},
        "public_cli_apply_still_frozen": {"returncode": 44, "frozen": True},
        "public_cli_rollback_still_frozen": {"returncode": 44, "frozen": True},
        "public_cli_reconcile_still_frozen": {"returncode": 44, "frozen": True},
    }
    write_json(root / "trial/resume/reconcile.json", reconcile)
    summary = {
        "schema": TRIAL_SCHEMA,
        "passed": True,
        "checkpoint": checkpoint,
        "before_reconcile": a_adoption,
        "after_reconcile": a_adoption,
        "before_reconcile_health_passed": True,
        "after_reconcile_health_passed": True,
        "reconcile": reconcile,
        "restore_rollback": None,
    }
    write_json(root / "trial/powerloss-summary.json", summary)
    (root / "postcheck.txt").write_text(
        "BOOT_ID=00000000-0000-4000-8000-000000000000\nUPTIME=42.0\n"
        "SERVICE_ACTIVE=active\nTIMER_ENABLED=disabled\nSTRICT_GPU_FAULTS=0\n"
        "PUBLIC_PLAYER_RUNTIME_APPLY_LOCAL_RC=44\nPUBLIC_PLAYER_RUNTIME_ROLLBACK_RC=44\n"
        "PUBLIC_PLAYER_RUNTIME_RECONCILE_RC=44\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text("# fixture\n", encoding="utf-8")
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "evidence-manifest.json":
            files.append({
                "file": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    write_json(root / "evidence-manifest.json", {
        "schema": MANIFEST_SCHEMA,
        "artifact_id": "fixture",
        "component": "player-runtime",
        "checkpoint": "rollback_after_previous_removed",
        "board_image_marker": "c18-fixture",
        "source_commit": "a" * 40,
        "setup_candidate_version": candidate,
        "expected_active_version": expected,
        "rollback_expectation": "data-current-after-previous-removed",
        "files": files,
    })


class PowerlossEvidenceGateSelfTest(unittest.TestCase):
    def refresh_manifest_files(self, root: Path) -> None:
        manifest_path = root / "evidence-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"] = []
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.name != "evidence-manifest.json":
                manifest["files"].append({
                    "file": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                })
        write_json(manifest_path, manifest)

    def test_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            self.assertTrue(validate(root)["passed"])

    def test_hash_tamper_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            (root / "README.md").write_text("# tampered\n", encoding="utf-8")
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertIn("manifest_sha256_mismatch:README.md", result["errors"])

    def test_bad_checkpoint_state_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            path = root / "trial/powerloss-checkpoint/checkpoint.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["runtime_snapshot"]["previous_link"] = "releases/runtime-b"
            write_json(path, data)
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertIn("checkpoint_previous_link_should_be_absent", result["errors"])

    def test_secret_value_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            path = root / "setup/secret.json"
            write_json(path, {"api_key": "abc123"})
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertIn("sensitive_json_value:setup/secret.json:api_key", result["errors"])

    def test_unknown_checkpoint_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            manifest_path = root / "evidence-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["checkpoint"] = "rollback_after_future_unknown"
            write_json(manifest_path, manifest)
            checkpoint_path = root / "trial/powerloss-checkpoint/checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["checkpoint"] = "rollback_after_future_unknown"
            write_json(checkpoint_path, checkpoint)
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertIn("unsupported_checkpoint:rollback_after_future_unknown", result["errors"])

    def test_known_matrix_checkpoint_without_semantics_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            manifest_path = root / "evidence-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["checkpoint"] = "after_extract"
            write_json(manifest_path, manifest)
            checkpoint_path = root / "trial/powerloss-checkpoint/checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["checkpoint"] = "after_extract"
            write_json(checkpoint_path, checkpoint)
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertNotIn("unsupported_checkpoint:after_extract", result["errors"])
            self.assertIn("checkpoint_semantics_not_implemented:after_extract", result["errors"])

    def test_after_current_symlink_requires_cut_before_state_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            shutil.rmtree(root / "setup")
            expected = "runtime-b"
            previous = "runtime-a"
            checkpoint_path = root / "trial/powerloss-checkpoint/checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint.update({
                "action": "apply",
                "checkpoint": "after_current_symlink",
                "context": {"version": expected, "current": f"releases/{expected}"},
                "runtime_snapshot": {
                    "current_link": f"releases/{expected}",
                    "previous_link": f"releases/{previous}",
                    "state_current_version": previous,
                    "state_previous_version": None,
                    "last_operation": {
                        "type": "apply",
                        "status": "verifying",
                        "version": expected,
                    },
                },
            })
            write_json(checkpoint_path, checkpoint)
            summary_path = root / "trial/powerloss-summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["checkpoint"] = checkpoint
            for label in ("before_reconcile", "after_reconcile"):
                summary[label]["selected_version"] = expected
                summary[label]["previous_link"] = f"releases/{previous}"
            write_json(summary_path, summary)
            for rel_path in (
                "trial/resume/before-reconcile-adoption.json",
                "trial/resume/after-reconcile-adoption.json",
            ):
                sidecar = json.loads((root / rel_path).read_text(encoding="utf-8"))
                sidecar["selected_version"] = expected
                sidecar["previous_link"] = f"releases/{previous}"
                write_json(root / rel_path, sidecar)
            manifest_path = root / "evidence-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["checkpoint"] = "after_current_symlink"
            manifest["expected_active_version"] = expected
            write_json(manifest_path, manifest)
            self.refresh_manifest_files(root)
            self.assertTrue(validate(root)["passed"])

            checkpoint["runtime_snapshot"]["state_current_version"] = expected
            write_json(checkpoint_path, checkpoint)
            self.refresh_manifest_files(root)
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertIn("checkpoint_state_already_promoted", result["errors"])

    def test_rollback_after_current_to_previous_requires_pre_state_not_yet_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            expected = "runtime-a"
            candidate = "runtime-b"
            checkpoint_path = root / "trial/powerloss-checkpoint/checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint.update({
                "action": "rollback",
                "checkpoint": "rollback_after_current_to_previous",
                "context": {
                    "current": f"releases/{expected}",
                    "previous": f"releases/{candidate}",
                },
                "runtime_snapshot": {
                    "current_link": f"releases/{expected}",
                    "previous_link": f"releases/{expected}",
                    "state_current_version": candidate,
                    "state_previous_version": expected,
                },
            })
            write_json(checkpoint_path, checkpoint)
            summary_path = root / "trial/powerloss-summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["checkpoint"] = checkpoint
            for label in ("before_reconcile", "after_reconcile"):
                summary[label]["previous_link"] = f"releases/{expected}"
            write_json(summary_path, summary)
            for rel_path in (
                "trial/resume/before-reconcile-adoption.json",
                "trial/resume/after-reconcile-adoption.json",
            ):
                sidecar = json.loads((root / rel_path).read_text(encoding="utf-8"))
                sidecar["previous_link"] = f"releases/{expected}"
                write_json(root / rel_path, sidecar)
            manifest_path = root / "evidence-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["checkpoint"] = "rollback_after_current_to_previous"
            write_json(manifest_path, manifest)
            self.refresh_manifest_files(root)
            self.assertTrue(validate(root)["passed"])

            checkpoint["runtime_snapshot"]["state_current_version"] = expected
            write_json(checkpoint_path, checkpoint)
            self.refresh_manifest_files(root)
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertIn("checkpoint_state_current_should_still_be_candidate", result["errors"])

    def test_required_postcheck_fails_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            (root / "postcheck.txt").unlink()
            manifest_path = root / "evidence-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"] = [
                item for item in manifest["files"] if item.get("file") != "postcheck.txt"
            ]
            write_json(manifest_path, manifest)
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertIn("postcheck_missing", result["errors"])

    def test_adoption_sidecar_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            path = root / "trial/resume/before-reconcile-adoption.json"
            sidecar = json.loads(path.read_text(encoding="utf-8"))
            sidecar["selected_version"] = "runtime-other"
            write_json(path, sidecar)
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertIn("before_reconcile_adoption_sidecar_version", result["errors"])
            self.assertIn("before_reconcile_adoption_sidecar_summary_sidecar_mismatch", result["errors"])

    def test_missing_health_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            path = root / "trial/resume/before-reconcile-health/playback-deep-health-public.json"
            health = json.loads(path.read_text(encoding="utf-8"))
            del health["checks"]["panfrost_faults_delta_zero"]
            write_json(path, health)
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertIn("before_reconcile_health_check_missing:panfrost_faults_delta_zero", result["errors"])

    def test_rollback_after_quarantine_requires_post_state_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            checkpoint_path = root / "trial/powerloss-checkpoint/checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["checkpoint"] = "rollback_after_quarantine"
            checkpoint["context"] = {
                "current": "releases/runtime-a",
                "quarantined": {
                    "version": "runtime-b",
                    "payload_sha256": "b" * 64,
                    "tree_sha256": "c" * 64,
                    "kiosk_py_sha256": "d" * 64,
                },
            }
            write_json(checkpoint_path, checkpoint)
            summary_path = root / "trial/powerloss-summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["checkpoint"] = checkpoint
            write_json(summary_path, summary)
            write_json(root / "trial/resume/post-reconcile-state.json", {
                "schema": POST_RECONCILE_STATE_SCHEMA,
                "current_version": "runtime-a",
                "expected_quarantine_version": "runtime-b",
                "quarantine_match_present": True,
                "quarantine_match": {
                    "version": "runtime-b",
                    "payload_sha256": "b" * 64,
                    "tree_sha256": "c" * 64,
                    "kiosk_py_sha256": "d" * 64,
                },
            })
            manifest_path = root / "evidence-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["checkpoint"] = "rollback_after_quarantine"
            manifest["rollback_expectation"] = "data-current-after-quarantine"
            manifest["files"] = []
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.name != "evidence-manifest.json":
                    manifest["files"].append({
                        "file": path.relative_to(root).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    })
            write_json(manifest_path, manifest)
            self.assertTrue(validate(root)["passed"])

            post_state_path = root / "trial/resume/post-reconcile-state.json"
            post_state = json.loads(post_state_path.read_text(encoding="utf-8"))
            post_state["quarantine_match"]["tree_sha256"] = "e" * 64
            write_json(post_state_path, post_state)
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertIn("post_reconcile_state_quarantine_tree_sha256_mismatch", result["errors"])

    def test_rollback_after_state_success_requires_final_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            checkpoint_path = root / "trial/powerloss-checkpoint/checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["checkpoint"] = "rollback_after_state_success"
            checkpoint["context"] = {"current": "releases/runtime-a"}
            checkpoint["runtime_snapshot"] = {
                "current_link": "releases/runtime-a",
                "previous_link": None,
                "state_current_version": "runtime-a",
                "state_previous_version": None,
                "last_operation": {
                    "type": "rollback",
                    "status": "success",
                    "rolled_back_to": "runtime-a",
                    "quarantined_current": True,
                },
                "quarantine": [{
                    "version": "runtime-b",
                    "payload_sha256": "b" * 64,
                    "tree_sha256": "c" * 64,
                    "kiosk_py_sha256": "d" * 64,
                }],
            }
            checkpoint["boot_state_at_checkpoint"] = {
                "boot_id": "00000000-0000-4000-8000-000000000001",
                "btime": 1000,
                "uptime_sec": 120.0,
            }
            write_json(checkpoint_path, checkpoint)
            summary_path = root / "trial/powerloss-summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["checkpoint"] = checkpoint
            summary["boot_state_at_resume"] = {
                "boot_id": "00000000-0000-4000-8000-000000000002",
                "btime": 1010,
                "uptime_sec": 12.0,
            }
            write_json(summary_path, summary)
            write_json(root / "trial/resume/post-reconcile-state.json", {
                "schema": POST_RECONCILE_STATE_SCHEMA,
                "current_version": "runtime-a",
                "previous_version": None,
                "expected_quarantine_version": "runtime-b",
                "quarantine_match_present": True,
                "quarantine_match": {
                    "version": "runtime-b",
                    "payload_sha256": "b" * 64,
                    "tree_sha256": "c" * 64,
                    "kiosk_py_sha256": "d" * 64,
                },
            })
            manifest_path = root / "evidence-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["checkpoint"] = "rollback_after_state_success"
            manifest["rollback_expectation"] = "data-current-after-state-success"
            manifest["files"] = []
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.name != "evidence-manifest.json":
                    manifest["files"].append({
                        "file": path.relative_to(root).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    })
            write_json(manifest_path, manifest)
            self.assertTrue(validate(root)["passed"])

            checkpoint["runtime_snapshot"]["last_operation"]["quarantined_current"] = False
            write_json(checkpoint_path, checkpoint)
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertIn("checkpoint_last_operation_missing_quarantine", result["errors"])

    def test_rollback_after_state_success_requires_boot_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            checkpoint_path = root / "trial/powerloss-checkpoint/checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["checkpoint"] = "rollback_after_state_success"
            checkpoint["context"] = {"current": "releases/runtime-a"}
            checkpoint["runtime_snapshot"] = {
                "current_link": "releases/runtime-a",
                "previous_link": None,
                "state_current_version": "runtime-a",
                "state_previous_version": None,
                "last_operation": {
                    "type": "rollback",
                    "status": "success",
                    "rolled_back_to": "runtime-a",
                    "quarantined_current": True,
                },
                "quarantine": [{
                    "version": "runtime-b",
                    "payload_sha256": "b" * 64,
                    "tree_sha256": "c" * 64,
                    "kiosk_py_sha256": "d" * 64,
                }],
            }
            checkpoint["boot_state_at_checkpoint"] = {
                "boot_id": "00000000-0000-4000-8000-000000000001",
                "btime": 1000,
                "uptime_sec": 120.0,
            }
            write_json(checkpoint_path, checkpoint)
            summary_path = root / "trial/powerloss-summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["checkpoint"] = checkpoint
            summary["boot_state_at_resume"] = dict(checkpoint["boot_state_at_checkpoint"])
            write_json(summary_path, summary)
            write_json(root / "trial/resume/post-reconcile-state.json", {
                "schema": POST_RECONCILE_STATE_SCHEMA,
                "current_version": "runtime-a",
                "previous_version": None,
                "expected_quarantine_version": "runtime-b",
                "quarantine_match_present": True,
                "quarantine_match": {
                    "version": "runtime-b",
                    "payload_sha256": "b" * 64,
                    "tree_sha256": "c" * 64,
                    "kiosk_py_sha256": "d" * 64,
                },
            })
            manifest_path = root / "evidence-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["checkpoint"] = "rollback_after_state_success"
            manifest["rollback_expectation"] = "data-current-after-state-success"
            manifest["files"] = []
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.name != "evidence-manifest.json":
                    manifest["files"].append({
                        "file": path.relative_to(root).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    })
            write_json(manifest_path, manifest)
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertIn("boot_state_boot_id_not_changed", result["errors"])

    def test_rollback_after_state_success_rejects_arm_timeout_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            checkpoint_path = root / "trial/powerloss-checkpoint/checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["checkpoint"] = "rollback_after_state_success"
            checkpoint["context"] = {"current": "releases/runtime-a"}
            checkpoint["runtime_snapshot"] = {
                "current_link": "releases/runtime-a",
                "previous_link": None,
                "state_current_version": "runtime-a",
                "state_previous_version": None,
                "last_operation": {
                    "type": "rollback",
                    "status": "success",
                    "rolled_back_to": "runtime-a",
                    "quarantined_current": True,
                },
                "quarantine": [{
                    "version": "runtime-b",
                    "payload_sha256": "b" * 64,
                    "tree_sha256": "c" * 64,
                    "kiosk_py_sha256": "d" * 64,
                }],
            }
            checkpoint["boot_state_at_checkpoint"] = {
                "boot_id": "00000000-0000-4000-8000-000000000001",
                "btime": 1000,
                "uptime_sec": 120.0,
            }
            write_json(checkpoint_path, checkpoint)
            summary_path = root / "trial/powerloss-summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["checkpoint"] = checkpoint
            summary["boot_state_at_resume"] = {
                "boot_id": "00000000-0000-4000-8000-000000000002",
                "btime": 1010,
                "uptime_sec": 12.0,
            }
            write_json(summary_path, summary)
            write_json(root / "trial/resume/post-reconcile-state.json", {
                "schema": POST_RECONCILE_STATE_SCHEMA,
                "current_version": "runtime-a",
                "previous_version": None,
                "expected_quarantine_version": "runtime-b",
                "quarantine_match_present": True,
                "quarantine_match": {
                    "version": "runtime-b",
                    "payload_sha256": "b" * 64,
                    "tree_sha256": "c" * 64,
                    "kiosk_py_sha256": "d" * 64,
                },
            })
            write_json(root / "trial/arm-timeout.json", {
                "schema": TRIAL_SCHEMA,
                "phase": "arm-rollback",
                "passed": False,
                "checkpoint_reached": True,
            })
            manifest_path = root / "evidence-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["checkpoint"] = "rollback_after_state_success"
            manifest["rollback_expectation"] = "data-current-after-state-success"
            manifest["files"] = []
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.name != "evidence-manifest.json":
                    manifest["files"].append({
                        "file": path.relative_to(root).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    })
            write_json(manifest_path, manifest)
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertIn("arm_timeout_present", result["errors"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate C18 player-runtime power-loss evidence.")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(PowerlossEvidenceGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if args.run_dir is None:
        raise SystemExit("--run-dir is required unless --self-test is used")
    result = validate(args.run_dir)
    print(json.dumps(result, indent=2 if args.json else None, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
