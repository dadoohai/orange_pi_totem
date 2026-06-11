#!/usr/bin/env python3
"""Default-deny gate for assisted C18 player-runtime homologation pilot.

This gate creates an intermediate stop between H1 lab evidence and H2
stable/production readiness. It authorizes only an operator-assisted pilot on
``channel=homologation`` and ``ring=pilot``. It does not thaw the public updater,
does not publish or fetch releases, and does not claim stable/prod readiness.
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


REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA = "dadooh.c18.homologation_pilot_readiness.v1"
AUTHORIZATION_SCHEMA = "dadooh.c18.homologation_pilot_authorization.v1"
PREFLIGHT_SCHEMA = "dadooh.c18.homologation_pilot_preflight.v1"
H1_RELEASE_GATE_SCHEMA = "dadooh.c18.ota.release_gate.v1"
UPDATE_MANIFEST_SCHEMA = "dadooh.totem.update.v1"
POWERLOSS_MANIFEST_SCHEMA = "dadooh.c18.powerloss.evidence_manifest.v1"

EXPECTED_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
EXPECTED_HWDEC = "v4l2request-copy"
PREFLIGHT_STAGES = {"pre_apply", "post_apply_observation"}

PILOT_POWERLOSS_CHECKPOINTS = (
    "after_current_symlink",
    "rollback_after_current_to_previous",
    "rollback_after_previous_removed",
    "rollback_after_quarantine",
    "rollback_after_state_success",
)
H2_POWERLOSS_CHECKPOINTS = (
    "after_payload_staged",
    "after_release_dir_created",
    "after_extract",
    "after_state_verifying",
    "after_health_passed",
    "after_release_tree_fsync",
    "after_marker_written",
    "after_previous_symlink",
    "after_state_success",
    "before_stage_cleanup",
    "rollback_after_identify_links",
    "rollback_after_current_unlinked",
)
ALL_POWERLOSS_CHECKPOINTS = set(PILOT_POWERLOSS_CHECKPOINTS) | set(H2_POWERLOSS_CHECKPOINTS)

REQUIRED_NON_CLAIMS = (
    "no_production",
    "no_stable",
    "no_auto_pull",
    "no_24h_soak",
    "no_powerloss_17_17",
    "no_signature_or_attestation",
    "no_public_thaw",
)
GATE_NON_CLAIMS = (
    "this_gate_does_not_authorize_production",
    "this_gate_does_not_promote_stable",
    "this_gate_does_not_enable_auto_pull",
    "this_gate_does_not_satisfy_24h_soak",
    "this_gate_does_not_satisfy_powerloss_17_17",
    "this_gate_does_not_require_or_claim_signature_attestation",
    "this_gate_does_not_thaw_public_player_runtime",
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DEVICE_HASH_RE = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$")
PRIVATE_IP_RE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
MAC_RE = re.compile(r"\b[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}\b")
SECRET_RE = re.compile(r"(github_pat_|gh[opsu]_|Bearer\s+\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----)", re.I)


def step(passed: bool, blockers: list[str], **details: Any) -> dict[str, Any]:
    return {"passed": passed, "blockers": blockers, **details}


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


def parse_utc(raw: Any) -> dt.datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    value = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc)


def format_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def is_git_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(GIT_SHA_RE.fullmatch(value))


def normalized_device_hash(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = DEVICE_HASH_RE.fullmatch(value)
    return match.group(1) if match else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sanitized_id(value: Any) -> bool:
    if not isinstance(value, str) or not SAFE_ID_RE.fullmatch(value):
        return False
    return not (PRIVATE_IP_RE.search(value) or MAC_RE.search(value) or SECRET_RE.search(value) or "@" in value)


def nested(data: dict[str, Any], *keys: str) -> Any:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def bool_false(value: Any) -> bool:
    return value is False


def freeze_ok(value: Any) -> bool:
    return isinstance(value, dict) and value.get("returncode") == 44 and value.get("frozen") is True


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def repo_rel(path: Path) -> str | None:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return None


def repo_clean_guard() -> dict[str, Any]:
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    blockers: list[str] = []
    if proc.returncode != 0:
        blockers.append("git_status_failed")
    elif proc.stdout.strip():
        blockers.append("repo_dirty")
    return step(
        not blockers,
        blockers,
        stdout_tail=proc.stdout[-1200:],
        stderr_tail=proc.stderr[-1200:],
    )


def git_lines(args: list[str]) -> tuple[int, list[str], str]:
    proc = subprocess.run(
        args,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.returncode, [line for line in proc.stdout.splitlines() if line], proc.stderr


def tracked_input_guard(paths: list[Path]) -> dict[str, Any]:
    blockers: list[str] = []
    details: dict[str, Any] = {
        "paths": [str(path) for path in paths],
        "untracked": [],
        "ignored": [],
        "manifest_untracked_entries": [],
        "outside_repo": [],
    }
    for path in paths:
        rel = repo_rel(path)
        if rel is None:
            blockers.append("input_path_outside_repo")
            details["outside_repo"].append(str(path))
            continue
        target = rel
        if path.is_dir():
            tracked_rc, tracked_files, _tracked_err = git_lines(["git", "ls-files", "--", target])
            ignored_rc, ignored_files, _ignored_err = git_lines(["git", "ls-files", "--others", "--ignored", "--exclude-standard", "--", target])
            untracked_rc, untracked_files, _untracked_err = git_lines(["git", "ls-files", "--others", "--exclude-standard", "--", target])
            if tracked_rc != 0 or not tracked_files:
                blockers.append("input_dir_not_tracked")
                details["untracked"].append(target)
            if ignored_rc != 0:
                blockers.append("input_dir_ignored_scan_failed")
            elif ignored_files:
                blockers.append("input_dir_ignored_files_present")
                details["ignored"].extend(ignored_files[:20])
            if untracked_rc != 0:
                blockers.append("input_dir_untracked_scan_failed")
            elif untracked_files:
                blockers.append("input_dir_untracked_files_present")
                details["untracked"].extend(untracked_files[:20])
            manifest_path = path / "evidence-manifest.json"
            tracked_set = set(tracked_files)
            if manifest_path.exists():
                manifest_errors: list[str] = []
                manifest = read_json(manifest_path, manifest_errors, "tracked_input_manifest")
                if manifest_errors:
                    blockers.extend(manifest_errors)
                manifest_rel = f"{target}/evidence-manifest.json"
                if manifest_rel not in tracked_set:
                    blockers.append("input_manifest_not_tracked")
                    details["manifest_untracked_entries"].append(manifest_rel)
                manifest_files = manifest.get("files")
                if isinstance(manifest_files, list):
                    for item in manifest_files:
                        if not isinstance(item, dict) or not isinstance(item.get("file"), str):
                            continue
                        rel_file = f"{target}/{item['file']}"
                        if rel_file not in tracked_set:
                            blockers.append("input_manifest_entries_not_tracked")
                            details["manifest_untracked_entries"].append(rel_file)
        else:
            tracked_rc, _tracked_files, _tracked_err = git_lines(["git", "ls-files", "--error-unmatch", "--", target])
            if tracked_rc != 0:
                blockers.append("input_file_not_tracked")
                details["untracked"].append(target)
    return step(not blockers, sorted(set(blockers)), **details)


def require_expected_image_args(args: argparse.Namespace, blockers: list[str]) -> None:
    if not args.expect_image_tag:
        blockers.append("missing_expect_image_tag")
    if not is_sha256(args.expect_image_sha256):
        blockers.append("missing_or_invalid_expect_image_sha256")
    if not is_sha256(args.expect_image_marker_sha256):
        blockers.append("missing_or_invalid_expect_image_marker_sha256")


def evaluate_target_package(
    manifest_path: Path | None,
    payload_path: Path | None,
    expected_source_commit: str | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    if manifest_path is None:
        return step(False, ["missing_target_package_manifest"])
    errors: list[str] = []
    manifest = read_json(manifest_path, errors, "target_package_manifest")
    blockers.extend(errors)
    resolved_payload = payload_path
    if resolved_payload is None and isinstance(manifest.get("payload"), str):
        resolved_payload = manifest_path.parent / str(manifest.get("payload"))
    if manifest.get("schema") != UPDATE_MANIFEST_SCHEMA:
        blockers.append("target_package_schema")
    if manifest.get("component") != "player-runtime":
        blockers.append("target_package_component")
    if manifest.get("channel") != "homologation":
        blockers.append("target_package_channel_not_homologation")
    if manifest.get("channel") == "stable":
        blockers.append("target_package_stable_blocked")
    if manifest.get("source_dirty") is not False:
        blockers.append("target_package_source_dirty")
    if expected_source_commit and manifest.get("source_commit") != expected_source_commit:
        blockers.append("target_package_source_commit_mismatch")
    if parse_utc(manifest.get("created_at_utc")) is None:
        blockers.append("target_package_created_at_utc_invalid")
    version = manifest.get("version")
    if not isinstance(version, str) or not SAFE_ID_RE.fullmatch(version):
        blockers.append("target_package_version_invalid")
    payload_name = manifest.get("payload")
    if isinstance(version, str) and isinstance(payload_name, str):
        expected_payload = f"dadooh-player-runtime-{version}.tar.gz"
        if payload_name != expected_payload:
            blockers.append("target_package_payload_name_mismatch")
    else:
        blockers.append("target_package_payload_missing")
    if not is_sha256(manifest.get("payload_sha256")):
        blockers.append("target_package_payload_sha256_invalid")
    if resolved_payload is None or not resolved_payload.is_file():
        blockers.append("target_package_payload_missing_on_disk")
    elif is_sha256(manifest.get("payload_sha256")):
        if sha256_file(resolved_payload) != manifest.get("payload_sha256"):
            blockers.append("target_package_payload_sha256_mismatch")
    requires = manifest.get("requires")
    if not isinstance(requires, dict):
        blockers.append("target_package_requires_missing")
    else:
        if requires.get("device_track") != "c18-hwdecode":
            blockers.append("target_package_device_track")
        if requires.get("media_stack_id") != "c18-hwdecode-v4l2request-copy":
            blockers.append("target_package_media_stack")
        if requires.get("mpv_wrapper") != EXPECTED_WRAPPER:
            blockers.append("target_package_mpv_wrapper")
        if requires.get("hwdec") != EXPECTED_HWDEC:
            blockers.append("target_package_hwdec")
    return step(
        not blockers,
        blockers,
        manifest_path=str(manifest_path),
        payload_path=str(resolved_payload) if resolved_payload is not None else None,
        version=version,
        channel=manifest.get("channel"),
        payload_sha256=manifest.get("payload_sha256"),
    )


def evaluate_h1(summary_path: Path | None, args: argparse.Namespace, expected_h1_repo_head: str | None) -> dict[str, Any]:
    blockers: list[str] = []
    if summary_path is None:
        return step(False, ["missing_h1_release_gate_summary"])
    errors: list[str] = []
    summary = read_json(summary_path, errors, "h1_release_gate_summary")
    blockers.extend(errors)
    require_expected_image_args(args, blockers)
    if summary.get("schema") != H1_RELEASE_GATE_SCHEMA:
        blockers.append("h1_release_gate_schema")
    if summary.get("passed") is not True:
        blockers.append("h1_release_gate_not_passed")
    guardrails = summary.get("guardrails") if isinstance(summary.get("guardrails"), dict) else {}
    for key in ("github_used", "apt_used", "pip_used", "secrets_read", "media_read"):
        if guardrails.get(key) is not False:
            blockers.append(f"h1_guardrail_{key}_not_false")
    package = summary.get("package") if isinstance(summary.get("package"), dict) else None
    if package and package.get("channel") == "stable":
        blockers.append("h1_package_stable_not_allowed_for_pilot")
    data_evidence = summary.get("player_runtime_data_evidence")
    if not isinstance(data_evidence, dict):
        blockers.append("h1_player_runtime_data_evidence_missing")
        data_evidence = {}
    else:
        if data_evidence.get("mode") != "decisive":
            blockers.append("h1_player_runtime_data_evidence_not_decisive")
        if data_evidence.get("status") != "passed" or data_evidence.get("decisive") is not True:
            blockers.append("h1_player_runtime_data_evidence_not_passed")
        expected_pairs = (
            ("expected_image_tag", args.expect_image_tag, "h1_image_tag_mismatch"),
            ("expected_image_sha256", args.expect_image_sha256, "h1_image_sha256_mismatch"),
            ("expected_image_marker_sha256", args.expect_image_marker_sha256, "h1_image_marker_sha256_mismatch"),
        )
        for key, expected, blocker in expected_pairs:
            if expected and data_evidence.get(key) != expected:
                blockers.append(blocker)
    steps = summary.get("steps")
    step_items = [item for item in steps if isinstance(item, dict)] if isinstance(steps, list) else []
    step_names = [item.get("name") for item in step_items]
    for prefix, missing_blocker, not_passed_blocker in (
        (
            "c18_player_runtime_data_coldboot_evidence",
            "h1_data_coldboot_step_missing",
            "h1_data_coldboot_step_not_passed",
        ),
        ("c18_player_runtime_data_evidence", "h1_data_evidence_step_missing", "h1_data_evidence_step_not_passed"),
        (
            "c18_player_runtime_data_evidence_link",
            "h1_data_evidence_link_step_missing",
            "h1_data_evidence_link_step_not_passed",
        ),
        ("c18_player_runtime_teardown_evidence:", "h1_teardown_evidence_step_missing", "h1_teardown_evidence_step_not_passed"),
        (
            "c18_player_runtime_production_stop_teardown_required",
            "h1_production_stop_teardown_step_missing",
            "h1_production_stop_teardown_step_not_passed",
        ),
    ):
        matching_steps = [item for item in step_items if str(item.get("name")).startswith(prefix)]
        if not matching_steps:
            blockers.append(missing_blocker)
        elif not any(item.get("passed") is True for item in matching_steps):
            blockers.append(not_passed_blocker)
    repo = summary.get("repo") if isinstance(summary.get("repo"), dict) else {}
    if not expected_h1_repo_head:
        blockers.append("h1_expected_repo_head_missing")
    elif repo.get("head") != expected_h1_repo_head:
        blockers.append("h1_repo_head_mismatch_or_missing")
    return step(
        not blockers,
        blockers,
        summary_path=str(summary_path),
        step_count=len(step_names),
        h1_repo_head=repo.get("head"),
    )


def evaluate_authorization(path: Path | None, now_utc: dt.datetime | None) -> tuple[dict[str, Any], dict[str, Any]]:
    blockers: list[str] = []
    if path is None:
        return step(False, ["missing_pilot_authorization"]), {}
    errors: list[str] = []
    data = read_json(path, errors, "pilot_authorization")
    blockers.extend(errors)
    if data.get("schema") != AUTHORIZATION_SCHEMA:
        blockers.append("authorization_schema")
    if data.get("approved") is not True:
        blockers.append("authorization_not_approved")
    if data.get("ring") != "pilot":
        blockers.append("authorization_ring_not_pilot")
    if data.get("channel") != "homologation":
        blockers.append("authorization_channel_not_homologation")
    if data.get("operator_assisted_delivery") is not True and data.get("delivery_mode") != "operator_assisted":
        blockers.append("authorization_operator_assisted_delivery_missing")
    if data.get("rollback_ready") is not True:
        blockers.append("authorization_rollback_ready_missing")
    if not sanitized_id(data.get("operator")):
        blockers.append("authorization_operator_not_sanitized")
    if not sanitized_id(data.get("rollback_owner")):
        blockers.append("authorization_rollback_owner_not_sanitized")
    source_commit = (
        data.get("expected_package_source_commit")
        or data.get("package_source_commit")
        or data.get("expected_source_commit")
        or data.get("source_commit")
    )
    if not is_git_sha(source_commit):
        blockers.append("authorization_expected_source_commit_missing_or_invalid")
    h1_repo_head = data.get("expected_h1_repo_head") or data.get("h1_repo_head")
    if h1_repo_head is None:
        blockers.append("authorization_expected_h1_repo_head_missing_or_invalid")
    elif not is_git_sha(h1_repo_head):
        blockers.append("authorization_expected_h1_repo_head_missing_or_invalid")
    window = data.get("window") if isinstance(data.get("window"), dict) else {}
    start = parse_utc(window.get("start_utc") or data.get("window_start_utc"))
    end = parse_utc(window.get("end_utc") or data.get("window_end_utc"))
    if start is None or end is None:
        blockers.append("authorization_window_invalid")
    elif end <= start:
        blockers.append("authorization_window_not_positive")
    elif now_utc is None:
        blockers.append("authorization_now_invalid")
    else:
        if now_utc < start:
            blockers.append("authorization_window_not_started")
        if now_utc > end:
            blockers.append("authorization_window_expired")
    devices = data.get("allowlisted_devices") or data.get("devices")
    device_hashes: list[str] = []
    if not isinstance(devices, list) or not devices:
        blockers.append("authorization_devices_missing")
    else:
        for idx, item in enumerate(devices):
            if not isinstance(item, dict):
                blockers.append(f"authorization_device_not_object:{idx}")
                continue
            device_hash = normalized_device_hash(item.get("device_hash") or item.get("hash"))
            if device_hash is None:
                blockers.append(f"authorization_device_hash_invalid:{idx}")
            else:
                device_hashes.append(device_hash)
            for raw_key in ("serial", "mac", "ip", "private_ip", "hostname"):
                if raw_key in item:
                    blockers.append(f"authorization_device_raw_identifier:{raw_key}")
    non_claims = data.get("non_claims")
    if not isinstance(non_claims, list):
        blockers.append("authorization_non_claims_missing")
        non_claims = []
    for item in REQUIRED_NON_CLAIMS:
        if item not in non_claims:
            blockers.append(f"authorization_non_claim_missing:{item}")
    claims = data.get("claims") if isinstance(data.get("claims"), list) else []
    forbidden_claims = {"production", "stable", "auto_pull", "public_thaw", "powerloss_17_17", "soak_24h"}
    for claim in claims:
        if claim in forbidden_claims:
            blockers.append(f"authorization_forbidden_claim:{claim}")
    return step(
        not blockers,
        blockers,
        authorization_path=str(path),
        source_commit=source_commit,
        h1_repo_head=h1_repo_head,
        window_start_utc=format_utc(start) if start else None,
        window_end_utc=format_utc(end) if end else None,
        evaluated_at_utc=format_utc(now_utc) if now_utc else None,
        device_hashes=device_hashes,
    ), data


def get_image_field(data: dict[str, Any], key: str) -> Any:
    image = data.get("image") if isinstance(data.get("image"), dict) else {}
    aliases = {
        "tag": ("tag", "image_tag"),
        "sha256": ("sha256", "image_sha256"),
        "marker_sha256": ("marker_sha256", "image_marker_sha256"),
    }
    for alias in aliases[key]:
        if alias in image:
            return image.get(alias)
        if alias in data:
            return data.get(alias)
    return None


def evaluate_preflight(path: Path | None, args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    blockers: list[str] = []
    if path is None:
        return step(False, ["missing_board_preflight"]), {}
    errors: list[str] = []
    data = read_json(path, errors, "board_preflight")
    blockers.extend(errors)
    require_expected_image_args(args, blockers)
    if data.get("schema") != PREFLIGHT_SCHEMA:
        blockers.append("preflight_schema")
    if data.get("passed") is not True:
        blockers.append("preflight_not_passed")
    stage = data.get("stage") or data.get("operation_stage")
    expected_stage = getattr(args, "preflight_stage", None) or "pre_apply"
    if stage not in PREFLIGHT_STAGES:
        blockers.append("preflight_stage_missing_or_invalid")
    elif stage != expected_stage:
        blockers.append("preflight_stage_mismatch")
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    if policy.get("device_channel") != "homologation":
        blockers.append("preflight_policy_not_homologation")
    if policy.get("allow_prerelease") is not True:
        blockers.append("preflight_allow_prerelease_not_true")
    timer = data.get("timer") if isinstance(data.get("timer"), dict) else {}
    timer_enabled = timer.get("enabled", data.get("timer_enabled"))
    timer_active = timer.get("active", data.get("timer_active"))
    if not bool_false(timer_enabled):
        blockers.append("preflight_timer_enabled_not_false")
    if not bool_false(timer_active):
        blockers.append("preflight_timer_active_not_false")
    public_freeze = data.get("public_freeze") if isinstance(data.get("public_freeze"), dict) else data
    freeze_fields = {
        "apply_local": ("apply_local", "apply", "public_cli_apply_still_frozen"),
        "rollback": ("rollback", "public_cli_rollback_still_frozen"),
        "reconcile": ("reconcile", "public_cli_reconcile_still_frozen"),
    }
    for label, aliases in freeze_fields.items():
        value = next((public_freeze.get(alias) for alias in aliases if isinstance(public_freeze, dict) and alias in public_freeze), None)
        if not freeze_ok(value):
            blockers.append(f"preflight_public_freeze_{label}_not_rc44")
    if args.expect_image_tag and get_image_field(data, "tag") != args.expect_image_tag:
        blockers.append("preflight_image_tag_mismatch")
    if args.expect_image_sha256 and get_image_field(data, "sha256") != args.expect_image_sha256:
        blockers.append("preflight_image_sha256_mismatch")
    if args.expect_image_marker_sha256 and get_image_field(data, "marker_sha256") != args.expect_image_marker_sha256:
        blockers.append("preflight_image_marker_sha256_mismatch")
    runtime = data.get("player_runtime") if isinstance(data.get("player_runtime"), dict) else {}
    checks = runtime.get("checks") if isinstance(runtime.get("checks"), dict) else data.get("checks") if isinstance(data.get("checks"), dict) else {}
    mpv_path = runtime.get("mpv_path") or data.get("mpv_path")
    if mpv_path is not None:
        if mpv_path != EXPECTED_WRAPPER:
            blockers.append("preflight_mpv_path_not_c18_wrapper")
    elif checks.get("mpv_path_c18_stack") is not True:
        blockers.append("preflight_mpv_path_c18_stack_missing")
    hwdec = runtime.get("hwdec") or data.get("hwdec")
    if hwdec is not None:
        if hwdec != EXPECTED_HWDEC:
            blockers.append("preflight_hwdec_not_expected")
    elif checks.get("hwdec_expected_present") is not True:
        blockers.append("preflight_hwdec_expected_missing")
    device_hash = normalized_device_hash(data.get("device_hash") or nested(data, "device", "hash"))
    if device_hash is None:
        blockers.append("preflight_device_hash_missing_or_invalid")
    source_commit = data.get("source_commit") or nested(data, "repo", "head")
    if source_commit is None:
        blockers.append("preflight_source_commit_missing")
    elif not is_git_sha(source_commit):
        blockers.append("preflight_source_commit_invalid")
    return step(
        not blockers,
        blockers,
        preflight_path=str(path),
        stage=stage,
        expected_stage=expected_stage,
        device_hash=device_hash,
        source_commit=source_commit,
    ), data


def evaluate_authorization_preflight_link(auth_result: dict[str, Any], preflight_result: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    device_hash = preflight_result.get("device_hash")
    device_hashes = auth_result.get("device_hashes") if isinstance(auth_result.get("device_hashes"), list) else []
    if device_hash and device_hashes and device_hash not in device_hashes:
        blockers.append("preflight_device_not_authorized")
    auth_source = auth_result.get("source_commit")
    preflight_source = preflight_result.get("source_commit")
    if auth_source and not preflight_source:
        blockers.append("preflight_source_commit_missing")
    if auth_source and preflight_source and auth_source != preflight_source:
        blockers.append("preflight_source_commit_mismatch")
    return step(not blockers, blockers, authorized_device=device_hash, source_commit=auth_source)


def evaluate_source_expectation(args: argparse.Namespace, auth_result: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    expected = args.expect_source_commit
    auth_source = auth_result.get("source_commit")
    if expected:
        if not is_git_sha(expected):
            blockers.append("expect_source_commit_invalid")
        elif not auth_source:
            blockers.append("expect_source_commit_without_authorization_source")
        elif expected != auth_source:
            blockers.append("expect_source_commit_mismatch_authorization")
    return step(not blockers, blockers, expect_source_commit=expected, authorization_source_commit=auth_source)


def manifest_image_errors(
    manifest: dict[str, Any],
    *,
    expect_image_tag: str | None,
    expect_image_sha256: str | None,
    expect_image_marker_sha256: str | None,
    expected_source_commit: str | None,
) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema") != POWERLOSS_MANIFEST_SCHEMA:
        errors.append("powerloss_manifest_schema")
    if manifest.get("component") != "player-runtime":
        errors.append("powerloss_manifest_component")
    checkpoint = manifest.get("checkpoint")
    if not isinstance(checkpoint, str) or not checkpoint:
        errors.append("powerloss_manifest_checkpoint_missing")
    if expect_image_tag and manifest.get("image_tag") != expect_image_tag:
        errors.append("powerloss_image_tag_mismatch_or_missing")
    if expect_image_sha256 and manifest.get("image_sha256") != expect_image_sha256:
        errors.append("powerloss_image_sha256_mismatch_or_missing")
    if expect_image_marker_sha256 and manifest.get("image_marker_sha256") != expect_image_marker_sha256:
        errors.append("powerloss_image_marker_sha256_mismatch_or_missing")
    if expected_source_commit and manifest.get("source_commit") != expected_source_commit:
        errors.append("powerloss_source_commit_mismatch_or_missing")
    return errors


def manifest_package_errors(manifest: dict[str, Any], target_package: dict[str, Any] | None) -> list[str]:
    if not target_package:
        return []
    errors: list[str] = []
    version = target_package.get("version")
    payload_sha256 = target_package.get("payload_sha256")
    manifest_version = manifest.get("target_package_version") or manifest.get("package_version")
    manifest_payload_sha256 = manifest.get("target_payload_sha256") or manifest.get("package_payload_sha256")
    if version and manifest_version != version:
        errors.append("powerloss_target_package_version_mismatch_or_missing")
    if payload_sha256 and manifest_payload_sha256 != payload_sha256:
        errors.append("powerloss_target_payload_sha256_mismatch_or_missing")
    return errors


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


def run_incident_gate(run_dir: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "python3",
            "scripts/qa/c18_playback_incident_evidence_gate.py",
            "--run-dir",
            str(run_dir),
            "--require-recurrent",
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
        "passed": proc.returncode == 0 and payload.get("evidence_valid") is True and payload.get("pilot_hold") is not True,
        "evidence_valid": payload.get("evidence_valid"),
        "pilot_hold": payload.get("pilot_hold"),
        "hold_reasons": payload.get("hold_reasons") if isinstance(payload.get("hold_reasons"), list) else [],
        "errors": payload.get("errors") if isinstance(payload.get("errors"), list) else [],
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-800:],
        "stderr_tail": proc.stderr[-800:],
    }


def evaluate_incidents(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    results: dict[str, Any] = {}
    for run_dir in args.incident_evidence_dir or []:
        result = run_incident_gate(run_dir)
        results[str(run_dir)] = result
        if result.get("evidence_valid") is not True:
            blockers.append(f"incident_evidence_invalid:{run_dir}")
        if result.get("pilot_hold") is True:
            blockers.append(f"incident_pilot_hold:{run_dir}")
    return step(not blockers, blockers, incident_count=len(args.incident_evidence_dir or []), results=results)


def evaluate_powerloss(
    args: argparse.Namespace,
    expected_source_commit: str | None,
    target_package: dict[str, Any] | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    checkpoint_dirs: dict[str, str] = {}
    gate_results: dict[str, dict[str, Any]] = {}
    duplicate_checkpoints: list[str] = []
    h2_only_observed: list[str] = []
    for run_dir in args.powerloss_evidence_dir or []:
        errors: list[str] = []
        manifest = read_json(run_dir / "evidence-manifest.json", errors, f"{run_dir.name}_manifest")
        checkpoint = manifest.get("checkpoint")
        if isinstance(checkpoint, str) and checkpoint in checkpoint_dirs:
            duplicate_checkpoints.append(checkpoint)
        if isinstance(checkpoint, str) and checkpoint:
            checkpoint_dirs[checkpoint] = str(run_dir)
        errors.extend(
            manifest_image_errors(
                manifest,
                expect_image_tag=args.expect_image_tag,
                expect_image_sha256=args.expect_image_sha256,
                expect_image_marker_sha256=args.expect_image_marker_sha256,
                expected_source_commit=expected_source_commit,
            )
        )
        if checkpoint in PILOT_POWERLOSS_CHECKPOINTS:
            errors.extend(manifest_package_errors(manifest, target_package))
        if checkpoint in H2_POWERLOSS_CHECKPOINTS:
            h2_only_observed.append(str(checkpoint))
            gate_results[str(checkpoint)] = {
                "dir": str(run_dir),
                "pilot_counted": False,
                "manifest_warnings": errors,
                "gate_passed": None,
                "gate_returncode": None,
                "gate_stderr_tail": "",
            }
            continue
        elif checkpoint not in PILOT_POWERLOSS_CHECKPOINTS:
            errors.append(f"powerloss_unknown_or_non_pilot_checkpoint:{checkpoint}")
        gate = run_powerloss_gate(run_dir)
        gate_results[str(checkpoint)] = {
            "dir": str(run_dir),
            "pilot_counted": checkpoint in PILOT_POWERLOSS_CHECKPOINTS,
            "manifest_errors": errors,
            "gate_passed": gate["passed"],
            "gate_returncode": gate["returncode"],
            "gate_stderr_tail": gate["stderr_tail"],
        }
        if errors:
            blockers.extend(f"{checkpoint}:{error}" for error in errors)
        if checkpoint in PILOT_POWERLOSS_CHECKPOINTS and not gate["passed"]:
            blockers.append(f"{checkpoint}:powerloss_gate_failed")
    missing = sorted(set(PILOT_POWERLOSS_CHECKPOINTS) - set(checkpoint_dirs))
    if missing:
        blockers.append("pilot_powerloss_p0_incomplete")
    if duplicate_checkpoints:
        blockers.append("powerloss_duplicate_checkpoint")
    return step(
        not blockers,
        blockers,
        required_checkpoints=list(PILOT_POWERLOSS_CHECKPOINTS),
        observed_checkpoints=sorted(checkpoint_dirs),
        missing_checkpoints=missing,
        h2_only_observed=sorted(h2_only_observed),
        duplicate_checkpoints=sorted(set(duplicate_checkpoints)),
        gate_results=gate_results,
    )


def now_from_args(args: argparse.Namespace) -> dt.datetime | None:
    raw = getattr(args, "now_utc", None)
    if raw:
        return parse_utc(raw)
    return dt.datetime.now(dt.timezone.utc)


def evaluate(args: argparse.Namespace, *, require_repo_clean: bool = True) -> dict[str, Any]:
    now_utc = now_from_args(args)
    auth_result, auth_data = evaluate_authorization(args.authorization, now_utc)
    expected_source_commit = auth_result.get("source_commit")
    expected_h1_repo_head = auth_result.get("h1_repo_head")
    preflight_result, _preflight_data = evaluate_preflight(args.preflight, args)
    target_package = evaluate_target_package(args.package_manifest, args.package_payload, expected_source_commit)
    checks: dict[str, dict[str, Any]] = {
        "source_expectation": evaluate_source_expectation(args, auth_result),
        "target_package": target_package,
        "h1_decisive_bundle": evaluate_h1(args.h1_release_gate_summary, args, expected_h1_repo_head),
        "pilot_authorization": auth_result,
        "board_preflight": preflight_result,
        "authorization_preflight_link": evaluate_authorization_preflight_link(auth_result, preflight_result),
        "incident_evidence": evaluate_incidents(args),
        "pilot_powerloss_p0": evaluate_powerloss(args, expected_source_commit, target_package),
    }
    if require_repo_clean:
        input_paths = [
            path for path in (
                args.h1_release_gate_summary,
                args.package_manifest,
                args.package_payload,
                args.authorization,
                args.preflight,
                *(args.incident_evidence_dir or []),
                *(args.powerloss_evidence_dir or []),
            ) if path is not None
        ]
        checks["repo_clean"] = repo_clean_guard()
        checks["tracked_inputs"] = tracked_input_guard(input_paths)
    blockers = [
        f"{name}:{blocker}"
        for name, result in checks.items()
        for blocker in result.get("blockers", [])
    ]
    return {
        "schema": SCHEMA,
        "passed": not blockers,
        "result_claim": "homologation_pilot_ready" if not blockers else "homologation_pilot_blocked",
        "ring": "pilot" if auth_data.get("ring") == "pilot" else None,
        "channel": "homologation" if auth_data.get("channel") == "homologation" else None,
        "checks": checks,
        "blockers": blockers,
        "non_claims": list(GATE_NON_CLAIMS),
    }


def fixture_manifest(
    root: Path,
    checkpoint: str,
    *,
    image_tag: str,
    image_sha: str,
    marker_sha: str,
    source: str,
    package_version: str,
    payload_sha256: str,
) -> Path:
    run_dir = root / checkpoint
    run_dir.mkdir(parents=True)
    write_json(run_dir / "evidence-manifest.json", {
        "schema": POWERLOSS_MANIFEST_SCHEMA,
        "component": "player-runtime",
        "checkpoint": checkpoint,
        "image_tag": image_tag,
        "image_sha256": image_sha,
        "image_marker_sha256": marker_sha,
        "source_commit": source,
        "target_package_version": package_version,
        "target_payload_sha256": payload_sha256,
        "files": [],
    })
    return run_dir


def complete_args(root: Path) -> argparse.Namespace:
    image_tag = "c18-hwdecode-lab-pilot"
    image_sha = "1" * 64
    marker_sha = "2" * 64
    package_source = "a" * 40
    h1_repo_head = "b" * 40
    h1 = root / "h1-release-gate.json"
    write_json(h1, {
        "schema": H1_RELEASE_GATE_SCHEMA,
        "passed": True,
        "guardrails": {
            "github_used": False,
            "apt_used": False,
            "pip_used": False,
            "secrets_read": False,
            "media_read": False,
        },
        "repo": {"head": h1_repo_head, "tree": "c" * 40},
        "player_runtime_data_evidence": {
            "mode": "decisive",
            "status": "passed",
            "decisive": True,
            "expected_image_tag": image_tag,
            "expected_image_sha256": image_sha,
            "expected_image_marker_sha256": marker_sha,
        },
        "steps": [
            {"name": "c18_player_runtime_data_coldboot_evidence", "passed": True},
            {"name": "c18_player_runtime_data_evidence", "passed": True},
            {"name": "c18_player_runtime_data_evidence_link", "passed": True},
            {"name": "c18_player_runtime_production_stop_teardown_required", "passed": True},
            {"name": "c18_player_runtime_teardown_evidence:1", "passed": True},
        ],
    })
    auth = root / "pilot-authorization.json"
    device_hash = "3" * 64
    write_json(auth, {
        "schema": AUTHORIZATION_SCHEMA,
        "approved": True,
        "ring": "pilot",
        "channel": "homologation",
        "operator_assisted_delivery": True,
        "rollback_ready": True,
        "operator": "operator-pilot-01",
        "rollback_owner": "rollback-owner-01",
        "expected_package_source_commit": package_source,
        "expected_h1_repo_head": h1_repo_head,
        "window": {
            "start_utc": "2026-06-11T12:00:00Z",
            "end_utc": "2026-06-11T14:00:00Z",
        },
        "allowlisted_devices": [{"device_hash": f"sha256:{device_hash}", "label": "pilot-01"}],
        "non_claims": list(REQUIRED_NON_CLAIMS),
    })
    preflight = root / "board-preflight.json"
    freeze = {"returncode": 44, "frozen": True}
    write_json(preflight, {
        "schema": PREFLIGHT_SCHEMA,
        "passed": True,
        "stage": "pre_apply",
        "device_hash": device_hash,
        "source_commit": package_source,
        "policy": {"device_channel": "homologation", "allow_prerelease": True},
        "timer": {"enabled": False, "active": False},
        "public_freeze": {"apply_local": freeze, "rollback": freeze, "reconcile": freeze},
        "image": {"tag": image_tag, "sha256": image_sha, "marker_sha256": marker_sha},
        "player_runtime": {"mpv_path": EXPECTED_WRAPPER, "hwdec": EXPECTED_HWDEC},
    })
    version = f"c18.player-runtime-pilot-{package_source[:7]}"
    payload = root / f"dadooh-player-runtime-{version}.tar.gz"
    payload.write_bytes(b"pilot payload fixture\n")
    payload_sha256 = sha256_file(payload)
    package = root / f"{payload.stem}.manifest.json"
    write_json(package, {
        "schema": UPDATE_MANIFEST_SCHEMA,
        "component": "player-runtime",
        "version": version,
        "channel": "homologation",
        "created_at_utc": "2026-06-11T12:00:00Z",
        "source_commit": package_source,
        "source_dirty": False,
        "payload": payload.name,
        "payload_sha256": payload_sha256,
        "requires": {
            "device": "orangepizero3",
            "base_image_min": "c17.4.2",
            "device_track": "c18-hwdecode",
            "media_stack_id": "c18-hwdecode-v4l2request-copy",
            "mpv_wrapper": EXPECTED_WRAPPER,
            "hwdec": EXPECTED_HWDEC,
            "vo": "gpu",
            "gpu_context": "drm",
            "deep_health_schema": "dadooh.c18.playback.deep_health.v1",
            "updater_features": ["c18-player-runtime-verify-then-promote-v1"],
        },
    })
    powerloss_dirs = [
        fixture_manifest(
            root / "powerloss",
            checkpoint,
            image_tag=image_tag,
            image_sha=image_sha,
            marker_sha=marker_sha,
            source=package_source,
            package_version=version,
            payload_sha256=payload_sha256,
        )
        for checkpoint in PILOT_POWERLOSS_CHECKPOINTS
    ]
    return argparse.Namespace(
        package_manifest=package,
        package_payload=payload,
        h1_release_gate_summary=h1,
        authorization=auth,
        preflight=preflight,
        incident_evidence_dir=[],
        powerloss_evidence_dir=powerloss_dirs,
        preflight_stage="pre_apply",
        now_utc="2026-06-11T13:00:00Z",
        expect_image_tag=image_tag,
        expect_image_sha256=image_sha,
        expect_image_marker_sha256=marker_sha,
        expect_source_commit=None,
    )


class PilotReadinessGateSelfTest(unittest.TestCase):
    def test_default_denies_required_families(self) -> None:
        args = argparse.Namespace(
            h1_release_gate_summary=None,
            package_manifest=None,
            package_payload=None,
            authorization=None,
            preflight=None,
            incident_evidence_dir=[],
            powerloss_evidence_dir=[],
            expect_image_tag=None,
            expect_image_sha256=None,
            expect_image_marker_sha256=None,
            preflight_stage="pre_apply",
            now_utc="2026-06-11T13:00:00Z",
            expect_source_commit=None,
        )
        with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
            result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("pilot_authorization:missing_pilot_authorization", result["blockers"])
        self.assertIn("this_gate_does_not_thaw_public_player_runtime", result["non_claims"])

    def test_complete_fixture_passes_when_p0_powerloss_subgates_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_missing_authorization_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            args.authorization = None
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("pilot_authorization:missing_pilot_authorization", result["blockers"])

    def test_preflight_policy_must_be_homologation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.preflight.read_text(encoding="utf-8"))
            data["policy"]["device_channel"] = "stable"
            write_json(args.preflight, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("board_preflight:preflight_policy_not_homologation", result["blockers"])

    def test_preflight_source_commit_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.preflight.read_text(encoding="utf-8"))
            data.pop("source_commit")
            write_json(args.preflight, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("board_preflight:preflight_source_commit_missing", result["blockers"])
        self.assertIn("authorization_preflight_link:preflight_source_commit_missing", result["blockers"])

    def test_stable_target_manifest_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.package_manifest.read_text(encoding="utf-8"))
            data["channel"] = "stable"
            write_json(args.package_manifest, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("target_package:target_package_channel_not_homologation", result["blockers"])
        self.assertIn("target_package:target_package_stable_blocked", result["blockers"])

    def test_corrupt_target_payload_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            args.package_payload.write_bytes(b"tampered\n")
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("target_package:target_package_payload_sha256_mismatch", result["blockers"])

    def test_h1_image_mismatch_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.h1_release_gate_summary.read_text(encoding="utf-8"))
            data["player_runtime_data_evidence"]["expected_image_tag"] = "c18-wrong"
            write_json(args.h1_release_gate_summary, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("h1_decisive_bundle:h1_image_tag_mismatch", result["blockers"])

    def test_h1_repo_head_mismatch_denies_when_authorized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.h1_release_gate_summary.read_text(encoding="utf-8"))
            data["repo"]["head"] = "d" * 40
            write_json(args.h1_release_gate_summary, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("h1_decisive_bundle:h1_repo_head_mismatch_or_missing", result["blockers"])

    def test_authorization_h1_repo_head_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.authorization.read_text(encoding="utf-8"))
            data.pop("expected_h1_repo_head")
            write_json(args.authorization, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn(
            "pilot_authorization:authorization_expected_h1_repo_head_missing_or_invalid",
            result["blockers"],
        )
        self.assertIn("h1_decisive_bundle:h1_expected_repo_head_missing", result["blockers"])

    def test_authorization_window_must_be_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.authorization.read_text(encoding="utf-8"))
            data["window"] = {
                "start_utc": "2020-01-01T00:00:00Z",
                "end_utc": "2020-01-01T01:00:00Z",
            }
            write_json(args.authorization, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("pilot_authorization:authorization_window_expired", result["blockers"])

    def test_h1_required_steps_must_be_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.h1_release_gate_summary.read_text(encoding="utf-8"))
            for item in data["steps"]:
                if item["name"].startswith("c18_player_runtime_teardown_evidence:"):
                    item["passed"] = False
            write_json(args.h1_release_gate_summary, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("h1_decisive_bundle:h1_teardown_evidence_step_not_passed", result["blockers"])

    def test_preflight_stage_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.preflight.read_text(encoding="utf-8"))
            data.pop("stage")
            write_json(args.preflight, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("board_preflight:preflight_stage_missing_or_invalid", result["blockers"])

    def test_preflight_stage_must_match_expected_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.preflight.read_text(encoding="utf-8"))
            data["stage"] = "post_apply_observation"
            write_json(args.preflight, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("board_preflight:preflight_stage_mismatch", result["blockers"])

    def test_source_mismatch_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.package_manifest.read_text(encoding="utf-8"))
            data["source_commit"] = "b" * 40
            write_json(args.package_manifest, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("target_package:target_package_source_commit_mismatch", result["blockers"])

    def test_expect_source_commit_cannot_override_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            args.expect_source_commit = "b" * 40
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("source_expectation:expect_source_commit_mismatch_authorization", result["blockers"])

    def test_missing_p0_powerloss_checkpoint_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            args.powerloss_evidence_dir = args.powerloss_evidence_dir[:-1]
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("pilot_powerloss_p0:pilot_powerloss_p0_incomplete", result["blockers"])

    def test_h2_only_powerloss_dirs_are_observed_not_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            h2_dir = fixture_manifest(
                Path(tmp) / "powerloss",
                "after_extract",
                image_tag="wrong-image",
                image_sha="4" * 64,
                marker_sha="5" * 64,
                source="b" * 40,
                package_version="other-package",
                payload_sha256="6" * 64,
            )
            args.powerloss_evidence_dir.append(h2_dir)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}) as gate:
                result = evaluate(args, require_repo_clean=False)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
        self.assertIn("after_extract", result["checks"]["pilot_powerloss_p0"]["h2_only_observed"])
        self.assertIsNone(result["checks"]["pilot_powerloss_p0"]["gate_results"]["after_extract"]["gate_passed"])
        self.assertEqual(gate.call_count, len(PILOT_POWERLOSS_CHECKPOINTS))

    def test_p0_powerloss_must_match_target_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            manifest_path = args.powerloss_evidence_dir[0] / "evidence-manifest.json"
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["target_package_version"] = "different-version"
            write_json(manifest_path, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("pilot_powerloss_p0:after_current_symlink:powerloss_target_package_version_mismatch_or_missing", result["blockers"])

    def test_non_claims_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.authorization.read_text(encoding="utf-8"))
            data["non_claims"].remove("no_public_thaw")
            write_json(args.authorization, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("pilot_authorization:authorization_non_claim_missing:no_public_thaw", result["blockers"])

    def test_preflight_rejects_mpv_path_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.preflight.read_text(encoding="utf-8"))
            data["player_runtime"]["mpv_path"] = "/usr/bin/mpv"
            write_json(args.preflight, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("board_preflight:preflight_mpv_path_not_c18_wrapper", result["blockers"])

    def test_preflight_rejects_hwdec_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            data = json.loads(args.preflight.read_text(encoding="utf-8"))
            data["player_runtime"]["hwdec"] = "no"
            write_json(args.preflight, data)
            with mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn("board_preflight:preflight_hwdec_not_expected", result["blockers"])

    def test_repo_clean_and_tracked_inputs_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            with (
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
                mock.patch(__name__ + ".repo_clean_guard", return_value=step(False, ["repo_dirty"], stdout_tail="", stderr_tail="")),
                mock.patch(__name__ + ".tracked_input_guard", return_value=step(False, ["input_file_not_tracked"], paths=[])),
            ):
                result = evaluate(args, require_repo_clean=True)
        self.assertFalse(result["passed"])
        self.assertIn("repo_clean:repo_dirty", result["blockers"])
        self.assertIn("tracked_inputs:input_file_not_tracked", result["blockers"])

    def test_tracked_input_guard_rejects_ignored_dir_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "evidence-manifest.json", {"files": [{"file": "tracked.json"}]})

            def fake_git(args: list[str]) -> tuple[int, list[str], str]:
                if "--ignored" in args:
                    return 0, ["docs/evidence/run/raw.log"], ""
                if "--others" in args:
                    return 0, ["docs/evidence/run/new.json"], ""
                if "--error-unmatch" in args:
                    return 1, [], ""
                return 0, ["docs/evidence/run/evidence-manifest.json"], ""

            with (
                mock.patch(__name__ + ".repo_rel", return_value="docs/evidence/run"),
                mock.patch(__name__ + ".git_lines", side_effect=fake_git),
            ):
                result = tracked_input_guard([root])
        self.assertFalse(result["passed"])
        self.assertIn("input_dir_ignored_files_present", result["blockers"])
        self.assertIn("input_dir_untracked_files_present", result["blockers"])
        self.assertIn("input_manifest_entries_not_tracked", result["blockers"])

    def test_incident_evidence_hold_blocks_pilot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = complete_args(Path(tmp))
            incident = Path(tmp) / "incident"
            incident.mkdir()
            args.incident_evidence_dir = [incident]
            with (
                mock.patch(__name__ + ".run_powerloss_gate", return_value={"passed": True, "returncode": 0, "stderr_tail": ""}),
                mock.patch(__name__ + ".run_incident_gate", return_value={
                    "passed": False,
                    "evidence_valid": True,
                    "pilot_hold": True,
                    "hold_reasons": ["recurrent_loop_observed"],
                    "errors": [],
                    "returncode": 1,
                    "stdout_tail": "",
                    "stderr_tail": "",
                }),
            ):
                result = evaluate(args, require_repo_clean=False)
        self.assertFalse(result["passed"])
        self.assertIn(f"incident_evidence:incident_pilot_hold:{incident}", result["blockers"])

    def test_incident_gate_wrapper_requires_recurrent_mode(self) -> None:
        payload = {
            "evidence_valid": False,
            "pilot_hold": False,
            "errors": ["recurrent_events_missing"],
            "hold_reasons": [],
        }
        with mock.patch(
            __name__ + ".subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=1, stdout=json.dumps(payload), stderr=""),
        ) as run:
            result = run_incident_gate(Path("/tmp/incident-evidence"))
        argv = run.call_args.args[0]
        self.assertIn("--require-recurrent", argv)
        self.assertIn("--json", argv)
        self.assertFalse(result["passed"])
        self.assertIn("recurrent_events_missing", result["errors"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate C18 player-runtime homologation pilot readiness.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--package-manifest", type=Path, default=None)
    parser.add_argument("--package-payload", type=Path, default=None)
    parser.add_argument("--h1-release-gate-summary", type=Path, default=None)
    parser.add_argument("--authorization", type=Path, default=None)
    parser.add_argument("--preflight", type=Path, default=None)
    parser.add_argument("--incident-evidence-dir", type=Path, action="append", default=[])
    parser.add_argument("--powerloss-evidence-dir", type=Path, action="append", default=[])
    parser.add_argument("--expect-image-tag", default=None)
    parser.add_argument("--expect-image-sha256", default=None)
    parser.add_argument("--expect-image-marker-sha256", default=None)
    parser.add_argument("--expect-source-commit", default=None)
    parser.add_argument("--preflight-stage", choices=sorted(PREFLIGHT_STAGES), default="pre_apply")
    parser.add_argument("--now-utc", default=None, help="UTC instant for authorization-window evaluation; defaults to current time.")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(PilotReadinessGateSelfTest)
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
