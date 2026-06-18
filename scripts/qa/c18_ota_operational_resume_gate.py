#!/usr/bin/env python3
"""Validate fresh C18 operational inputs before resuming a homologation pilot.

The macro-governance gate proves that the committed RC snapshot is coherent.
This gate answers a different question: whether an operator may resume an
operational pilot now. It requires a current authorization window and a fresh
board preflight. It does not run SSH, collect board state, apply, rollback,
publish, promote stable, complete H2, or thaw player-runtime.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.ota_operational_resume_gate.v1"
MACRO_SCHEMA = "dadooh.c18.ota_macro_governance_gate.v1"
AUTHORIZATION_SCHEMA = "dadooh.c18.homologation_pilot_authorization.v1"
PREFLIGHT_SCHEMA = "dadooh.c18.homologation_pilot_preflight.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MACRO_SUMMARY = (
    REPO_ROOT
    / "docs/evidence/c18-update-validation/20260618T074900Z-current-macro-governance-head-ad4095b-9bebaf1/macro-governance.json"
)
TARGET_PACKAGE_VERSION = "c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1"
TARGET_SOURCE_COMMIT = "9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522"
TARGET_PAYLOAD_SHA256 = "d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0"
EXPECTED_IMAGE_TAG = "c18-hwdecode-lab-1x"
EXPECTED_IMAGE_SHA256 = "1a853f569b5da9e856439897c95612d719fd3059f12349fa1040a6350c3df2f2"
EXPECTED_IMAGE_MARKER_SHA256 = "59739f57cdb3f79ac4c8ce5e5e1f9c4aa6d9dae58f704010f8423e66abe2bb9e"
EXPECTED_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
EXPECTED_HWDEC = "v4l2request-copy"
EXPECTED_H2_BLOCKERS = (
    "full_physical_powerloss_matrix:powerloss_matrix_incomplete",
    "soak_endurance_24h:missing_24h_soak_summary",
    "stable_promotion_authorization:missing_stable_promotion_evidence",
    "explicit_operator_thaw_decision:missing_operator_thaw_decision",
)
REQUIRED_AUTH_NON_CLAIMS = (
    "no_production",
    "no_stable",
    "no_auto_pull",
    "no_24h_soak",
    "no_powerloss_17_17",
    "no_signature_or_attestation",
    "no_public_thaw",
)
NON_CLAIMS = (
    "this_gate_does_not_reopen_expired_pilot_windows",
    "this_gate_does_not_use_snapshot_as_operational_authorization",
    "this_gate_does_not_run_ssh_or_board_commands",
    "this_gate_does_not_apply_or_rollback_player_runtime",
    "this_gate_does_not_authorize_production",
    "this_gate_does_not_promote_stable",
    "this_gate_does_not_enable_auto_pull",
    "this_gate_does_not_publish_releases",
    "this_gate_does_not_thaw_public_player_runtime",
    "this_gate_does_not_satisfy_24h_soak",
    "this_gate_does_not_satisfy_powerloss_17_17",
    "this_gate_does_not_replace_h2_readiness",
)

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DEVICE_HASH_RE = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")


def step(passed: bool, blockers: list[str], **details: Any) -> dict[str, Any]:
    return {"passed": passed, "blockers": sorted(set(blockers)), **details}


def read_json(path: Path | None, blockers: list[str], label: str) -> dict[str, Any]:
    if path is None:
        blockers.append(f"{label}_missing")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append(f"{label}_json_error:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        blockers.append(f"{label}_not_object")
        return {}
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_utc(raw: Any) -> dt.datetime | None:
    if not isinstance(raw, str) or not raw.endswith("Z"):
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw[:-1] + "+00:00")
    except ValueError:
        return None
    if parsed.utcoffset() != dt.timedelta(0):
        return None
    return parsed


def format_utc(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def now_from_args(args: argparse.Namespace) -> dt.datetime | None:
    if args.now_utc:
        return parse_utc(args.now_utc)
    return dt.datetime.now(dt.timezone.utc)


def normalized_device_hash(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    match = DEVICE_HASH_RE.fullmatch(raw)
    if not match:
        return None
    return match.group(1)


def is_sha1(raw: Any) -> bool:
    return isinstance(raw, str) and SHA1_RE.fullmatch(raw) is not None


def is_sha256(raw: Any) -> bool:
    return isinstance(raw, str) and SHA256_RE.fullmatch(raw) is not None


def nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def bool_false(value: Any) -> bool:
    return value is False or value in ("false", "False", "disabled", "inactive", 44)


def freeze_ok(value: Any) -> bool:
    if isinstance(value, dict):
        return value.get("returncode") == 44 and value.get("frozen") is True
    return value == 44


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
    return step(not blockers, blockers, changed_paths=lines[:50], stderr_tail=stderr[-1000:] if rc != 0 else "")


def tracked_input_guard(paths: list[Path]) -> dict[str, Any]:
    blockers: list[str] = []
    tracked: list[str] = []
    untracked: list[str] = []
    ignored: list[str] = []
    outside: list[str] = []
    missing: list[str] = []
    for path in paths:
        rel = repo_relative(path)
        if rel is None:
            blockers.append("input_outside_repo")
            outside.append(str(path))
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
            tracked.append(tracked_err[-1000:])
        if ignored_lines:
            blockers.append("input_ignored_files_present")
            ignored.extend(ignored_lines[:20])
        if untracked_lines:
            blockers.append("input_untracked_files_present")
            untracked.extend(untracked_lines[:20])
        if path.is_file() and rel not in set(tracked_lines):
            blockers.append("input_file_not_tracked")
        tracked.extend(tracked_lines[:50])
    return step(
        not blockers,
        blockers,
        paths=sorted(set(tracked))[:200],
        missing=missing,
        outside_repo=outside,
        untracked=untracked[:50],
        ignored=ignored[:50],
    )


def evaluate_macro(path: Path | None) -> tuple[dict[str, Any], dict[str, Any]]:
    blockers: list[str] = []
    data = read_json(path, blockers, "macro_governance")
    if not data:
        return step(False, blockers, summary_path=str(path) if path else None), {}
    if data.get("schema") != MACRO_SCHEMA:
        blockers.append("macro_schema")
    if data.get("passed") is not True:
        blockers.append("macro_not_passed")
    if data.get("result_claim") != "c18_homologation_governance_ready_pre_h2":
        blockers.append("macro_result_claim")
    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    if target.get("package_version") != TARGET_PACKAGE_VERSION:
        blockers.append("macro_target_package_version")
    if target.get("source_commit") != TARGET_SOURCE_COMMIT:
        blockers.append("macro_target_source_commit")
    if target.get("payload_sha256") != TARGET_PAYLOAD_SHA256:
        blockers.append("macro_target_payload_sha256")
    if target.get("channel") != "homologation" or target.get("ring") != "pilot":
        blockers.append("macro_target_channel_ring")
    if target.get("image_tag") != EXPECTED_IMAGE_TAG:
        blockers.append("macro_target_image_tag")
    h2 = nested(data, "checks", "h2_preproduction_block")
    if not isinstance(h2, dict) or h2.get("passed") is not True:
        blockers.append("macro_h2_block_state_missing")
    else:
        if h2.get("result_claim") != "h2_readiness_blocked":
            blockers.append("macro_h2_result_claim")
        if sorted(h2.get("blockers_actual") if isinstance(h2.get("blockers_actual"), list) else []) != sorted(EXPECTED_H2_BLOCKERS):
            blockers.append("macro_h2_blockers_not_exact")
    if nested(data, "checks", "pilot_readiness", "authorization_window", "snapshot_only") is not True:
        blockers.append("macro_pilot_window_not_snapshot_only")
    non_claims = set(data.get("non_claims") if isinstance(data.get("non_claims"), list) else [])
    if "this_gate_does_not_reopen_expired_pilot_windows" not in non_claims:
        blockers.append("macro_non_claim_no_reopen_missing")
    return step(
        not blockers,
        blockers,
        summary_path=str(path) if path else None,
        evaluated_at_utc=data.get("evaluated_at_utc"),
        target=target,
    ), data


def authorization_window(data: dict[str, Any]) -> tuple[dt.datetime | None, dt.datetime | None]:
    window = data.get("window") if isinstance(data.get("window"), dict) else {}
    start = parse_utc(window.get("start_utc") or data.get("window_start_utc"))
    end = parse_utc(window.get("end_utc") or data.get("window_end_utc"))
    return start, end


def authorization_device_hashes(data: dict[str, Any], blockers: list[str]) -> list[str]:
    raw_devices = data.get("allowlisted_devices") or data.get("devices")
    hashes: list[str] = []
    if not isinstance(raw_devices, list) or not raw_devices:
        blockers.append("authorization_devices_missing")
        return hashes
    for index, item in enumerate(raw_devices):
        if not isinstance(item, dict):
            blockers.append(f"authorization_device_not_object:{index}")
            continue
        device_hash = normalized_device_hash(item.get("device_hash") or item.get("hash"))
        if device_hash is None:
            blockers.append(f"authorization_device_hash_invalid:{index}")
        else:
            hashes.append(device_hash)
        for raw_key in ("serial", "mac", "ip", "private_ip", "hostname", "ssid", "environment_id"):
            if raw_key in item:
                blockers.append(f"authorization_device_raw_identifier:{raw_key}")
    return hashes


def evaluate_authorization(
    path: Path | None,
    *,
    now_utc: dt.datetime | None,
    max_window_sec: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    blockers: list[str] = []
    data = read_json(path, blockers, "current_pilot_authorization")
    if not data:
        return step(False, blockers, authorization_path=str(path) if path else None, device_hashes=[]), {}
    if data.get("schema") != AUTHORIZATION_SCHEMA:
        blockers.append("authorization_schema")
    if data.get("approved") is not True:
        blockers.append("authorization_not_approved")
    if data.get("ring") != "pilot":
        blockers.append("authorization_ring_not_pilot")
    if data.get("channel") != "homologation":
        blockers.append("authorization_channel_not_homologation")
    if data.get("operator_assisted_delivery") is not True and data.get("delivery_mode") != "operator_assisted":
        blockers.append("authorization_operator_assisted_missing")
    if data.get("rollback_ready") is not True:
        blockers.append("authorization_rollback_ready_missing")
    source = (
        data.get("expected_package_source_commit")
        or data.get("package_source_commit")
        or data.get("expected_source_commit")
        or data.get("source_commit")
    )
    if source != TARGET_SOURCE_COMMIT:
        blockers.append("authorization_source_commit_mismatch")
    h1_head = data.get("expected_h1_repo_head") or data.get("h1_repo_head")
    if not is_sha1(h1_head):
        blockers.append("authorization_h1_repo_head_invalid")
    start, end = authorization_window(data)
    if start is None or end is None:
        blockers.append("authorization_window_invalid")
    elif end <= start:
        blockers.append("authorization_window_not_positive")
    elif now_utc is None:
        blockers.append("authorization_now_invalid")
    else:
        if (end - start).total_seconds() > max_window_sec:
            blockers.append("authorization_window_too_long")
        if now_utc < start:
            blockers.append("authorization_window_not_started")
        if now_utc > end:
            blockers.append("authorization_window_expired")
    non_claims = set(data.get("non_claims") if isinstance(data.get("non_claims"), list) else [])
    for claim in REQUIRED_AUTH_NON_CLAIMS:
        if claim not in non_claims:
            blockers.append(f"authorization_non_claim_missing:{claim}")
    claims = data.get("claims") if isinstance(data.get("claims"), list) else []
    for claim in claims:
        if claim in {"production", "stable", "auto_pull", "public_thaw", "powerloss_17_17", "soak_24h"}:
            blockers.append(f"authorization_forbidden_claim:{claim}")
    device_hashes = authorization_device_hashes(data, blockers)
    return step(
        not blockers,
        blockers,
        authorization_path=str(path) if path else None,
        source_commit=source,
        h1_repo_head=h1_head,
        window_start_utc=format_utc(start),
        window_end_utc=format_utc(end),
        evaluated_at_utc=format_utc(now_utc),
        max_window_sec=max_window_sec,
        device_hashes=device_hashes,
    ), data


def preflight_image_field(data: dict[str, Any], key: str) -> Any:
    image = data.get("image") if isinstance(data.get("image"), dict) else {}
    aliases = {
        "tag": ("tag", "image_tag", "observed_marker_tag"),
        "sha256": ("sha256", "image_sha256"),
        "marker_sha256": ("marker_sha256", "image_marker_sha256", "observed_marker_sha256"),
    }
    for alias in aliases[key]:
        if alias in image:
            return image.get(alias)
        if alias in data:
            return data.get(alias)
    return None


def evaluate_preflight(
    path: Path | None,
    *,
    now_utc: dt.datetime | None,
    max_age_sec: int,
    expected_stage: str,
    authorized_device_hashes: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    blockers: list[str] = []
    data = read_json(path, blockers, "current_board_preflight")
    if not data:
        return step(False, blockers, preflight_path=str(path) if path else None), {}
    if data.get("schema") != PREFLIGHT_SCHEMA:
        blockers.append("preflight_schema")
    if data.get("passed") is not True:
        blockers.append("preflight_not_passed")
    stage = data.get("stage") or data.get("operation_stage")
    if stage != expected_stage:
        blockers.append("preflight_stage_mismatch")
    collected = parse_utc(data.get("collected_at_utc") or data.get("created_at_utc"))
    age_sec: float | None = None
    if collected is None:
        blockers.append("preflight_collected_at_invalid")
    elif now_utc is None:
        blockers.append("preflight_now_invalid")
    else:
        age_sec = (now_utc - collected).total_seconds()
        if age_sec < -60:
            blockers.append("preflight_collected_in_future")
        if age_sec > max_age_sec:
            blockers.append("preflight_stale")
    device_hash = normalized_device_hash(data.get("device_hash") or nested(data, "device", "hash"))
    if device_hash is None:
        blockers.append("preflight_device_hash_invalid")
    elif authorized_device_hashes and device_hash not in authorized_device_hashes:
        blockers.append("preflight_device_not_authorized")
    source_commit = data.get("source_commit") or nested(data, "repo", "head")
    if source_commit != TARGET_SOURCE_COMMIT:
        blockers.append("preflight_source_commit_mismatch")
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    if policy.get("schema") != "dadooh.totem.update.policy.v1":
        blockers.append("preflight_policy_schema")
    if policy.get("device_track") != "c18-hwdecode":
        blockers.append("preflight_policy_device_track_not_c18_hwdecode")
    if policy.get("device_channel") != "homologation":
        blockers.append("preflight_policy_not_homologation")
    if policy.get("allow_prerelease") is not True:
        blockers.append("preflight_allow_prerelease_not_true")
    if policy.get("allow_downgrade") is not False:
        blockers.append("preflight_allow_downgrade_not_false")
    if policy.get("allowed_components") != ["totem-core"]:
        blockers.append("preflight_allowed_components_not_totem_core")
    timer = data.get("timer") if isinstance(data.get("timer"), dict) else {}
    if not bool_false(timer.get("enabled", data.get("timer_enabled"))):
        blockers.append("preflight_timer_enabled_not_false")
    if not bool_false(timer.get("active", data.get("timer_active"))):
        blockers.append("preflight_timer_active_not_false")
    public_freeze = data.get("public_freeze") if isinstance(data.get("public_freeze"), dict) else data
    for label, aliases in {
        "apply_local": ("apply_local", "apply", "public_cli_apply_still_frozen"),
        "rollback": ("rollback", "public_cli_rollback_still_frozen"),
        "reconcile": ("reconcile", "public_cli_reconcile_still_frozen"),
    }.items():
        value = next((public_freeze.get(alias) for alias in aliases if isinstance(public_freeze, dict) and alias in public_freeze), None)
        if not freeze_ok(value):
            blockers.append(f"preflight_public_freeze_{label}_not_rc44")
    if preflight_image_field(data, "tag") != EXPECTED_IMAGE_TAG:
        blockers.append("preflight_image_tag_mismatch")
    if preflight_image_field(data, "sha256") != EXPECTED_IMAGE_SHA256:
        blockers.append("preflight_image_sha256_mismatch")
    if preflight_image_field(data, "marker_sha256") != EXPECTED_IMAGE_MARKER_SHA256:
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
    return step(
        not blockers,
        blockers,
        preflight_path=str(path) if path else None,
        stage=stage,
        expected_stage=expected_stage,
        collected_at_utc=format_utc(collected),
        max_age_sec=max_age_sec,
        age_sec=int(age_sec) if age_sec is not None else None,
        device_hash=device_hash,
        source_commit=source_commit,
    ), data


def evaluate(args: argparse.Namespace, *, require_repo_clean: bool = True) -> dict[str, Any]:
    now_utc = now_from_args(args)
    macro_result, _macro_data = evaluate_macro(args.macro_governance_summary)
    auth_result, _auth_data = evaluate_authorization(
        args.authorization,
        now_utc=now_utc,
        max_window_sec=args.max_authorization_window_sec,
    )
    preflight_result, _preflight_data = evaluate_preflight(
        args.preflight,
        now_utc=now_utc,
        max_age_sec=args.max_preflight_age_sec,
        expected_stage=args.expected_preflight_stage,
        authorized_device_hashes=auth_result.get("device_hashes") if isinstance(auth_result.get("device_hashes"), list) else [],
    )
    checks: dict[str, dict[str, Any]] = {
        "macro_governance_snapshot": macro_result,
        "current_pilot_authorization": auth_result,
        "current_board_preflight": preflight_result,
    }
    if require_repo_clean:
        inputs = [path for path in (args.macro_governance_summary, args.authorization, args.preflight) if path is not None]
        checks["repo_clean"] = repo_clean_guard()
        checks["tracked_inputs"] = tracked_input_guard(inputs)
    blockers = [
        f"{name}:{blocker}"
        for name, result in checks.items()
        for blocker in result.get("blockers", [])
    ]
    passed = not blockers
    return {
        "schema": SCHEMA,
        "evaluated_at_utc": format_utc(now_utc),
        "passed": passed,
        "result_claim": "c18_operational_resume_ready" if passed else "c18_operational_resume_blocked",
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
        "non_claims": list(NON_CLAIMS),
    }


def fixture_auth(root: Path, *, start: str, end: str, device_hash: str = "a" * 64) -> Path:
    path = root / "authorization.json"
    write_json(path, {
        "schema": AUTHORIZATION_SCHEMA,
        "approved": True,
        "ring": "pilot",
        "channel": "homologation",
        "operator_assisted_delivery": True,
        "rollback_ready": True,
        "operator": "operator-01",
        "rollback_owner": "rollback-owner-01",
        "expected_package_source_commit": TARGET_SOURCE_COMMIT,
        "expected_h1_repo_head": "b" * 40,
        "window": {"start_utc": start, "end_utc": end},
        "allowlisted_devices": [{"device_hash": "sha256:" + device_hash, "label": "pilot-01"}],
        "non_claims": list(REQUIRED_AUTH_NON_CLAIMS),
    })
    return path


def fixture_preflight(root: Path, *, collected: str, stage: str = "pre_apply", device_hash: str = "a" * 64) -> Path:
    path = root / "preflight.json"
    write_json(path, {
        "schema": PREFLIGHT_SCHEMA,
        "passed": True,
        "stage": stage,
        "collected_at_utc": collected,
        "device_hash": "sha256:" + device_hash,
        "source_commit": TARGET_SOURCE_COMMIT,
        "policy": {
            "schema": "dadooh.totem.update.policy.v1",
            "device_track": "c18-hwdecode",
            "device_channel": "homologation",
            "allow_prerelease": True,
            "allow_downgrade": False,
            "allowed_components": ["totem-core"],
        },
        "timer": {"enabled": False, "active": False},
        "public_freeze": {
            "apply_local": {"returncode": 44, "frozen": True},
            "rollback": {"returncode": 44, "frozen": True},
            "reconcile": {"returncode": 44, "frozen": True},
        },
        "image": {
            "tag": EXPECTED_IMAGE_TAG,
            "sha256": EXPECTED_IMAGE_SHA256,
            "marker_sha256": EXPECTED_IMAGE_MARKER_SHA256,
        },
        "player_runtime": {
            "mpv_path": EXPECTED_WRAPPER,
            "hwdec": EXPECTED_HWDEC,
        },
    })
    return path


def fixture_macro(root: Path, *, passed: bool = True, h2_blockers: list[str] | None = None) -> Path:
    path = root / "macro.json"
    h2_actual = list(EXPECTED_H2_BLOCKERS if h2_blockers is None else h2_blockers)
    write_json(path, {
        "schema": MACRO_SCHEMA,
        "passed": passed,
        "result_claim": "c18_homologation_governance_ready_pre_h2" if passed else "c18_macro_governance_blocked",
        "evaluated_at_utc": "2026-06-16T12:00:00Z",
        "target": {
            "component": "player-runtime",
            "package_version": TARGET_PACKAGE_VERSION,
            "source_commit": TARGET_SOURCE_COMMIT,
            "channel": "homologation",
            "ring": "pilot",
            "payload_sha256": TARGET_PAYLOAD_SHA256,
            "image_tag": EXPECTED_IMAGE_TAG,
        },
        "checks": {
            "h2_preproduction_block": {
                "passed": True,
                "result_claim": "h2_readiness_blocked",
                "blockers_actual": h2_actual,
            },
            "pilot_readiness": {
                "authorization_window": {"snapshot_only": True},
            },
        },
        "blockers": [],
        "non_claims": ["this_gate_does_not_reopen_expired_pilot_windows"],
    })
    return path


def fixture_args(root: Path, *, now: str = "2026-06-16T12:00:00Z") -> argparse.Namespace:
    return argparse.Namespace(
        macro_governance_summary=fixture_macro(root),
        authorization=fixture_auth(root, start="2026-06-16T10:00:00Z", end="2026-06-16T14:00:00Z"),
        preflight=fixture_preflight(root, collected="2026-06-16T11:30:00Z"),
        now_utc=now,
        max_preflight_age_sec=4 * 60 * 60,
        max_authorization_window_sec=24 * 60 * 60,
        expected_preflight_stage="pre_apply",
        allow_dirty_repo=True,
    )


class OperationalResumeGateSelfTest(unittest.TestCase):
    def evaluate_fixture(self, args: argparse.Namespace) -> dict[str, Any]:
        return evaluate(args, require_repo_clean=False)

    def test_valid_fresh_inputs_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.evaluate_fixture(fixture_args(Path(tmp)))
        self.assertTrue(result["passed"], result["blockers"])
        self.assertEqual(result["result_claim"], "c18_operational_resume_ready")

    def test_missing_current_inputs_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = fixture_args(Path(tmp))
            args.authorization = None
            args.preflight = None
            result = self.evaluate_fixture(args)
        self.assertFalse(result["passed"])
        self.assertIn("current_pilot_authorization:current_pilot_authorization_missing", result["blockers"])
        self.assertIn("current_board_preflight:current_board_preflight_missing", result["blockers"])

    def test_expired_authorization_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = fixture_args(root)
            args.authorization = fixture_auth(root, start="2026-06-15T10:00:00Z", end="2026-06-15T14:00:00Z")
            result = self.evaluate_fixture(args)
        self.assertFalse(result["passed"])
        self.assertIn("current_pilot_authorization:authorization_window_expired", result["blockers"])

    def test_stale_preflight_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = fixture_args(root)
            args.preflight = fixture_preflight(root, collected="2026-06-15T11:30:00Z")
            result = self.evaluate_fixture(args)
        self.assertFalse(result["passed"])
        self.assertIn("current_board_preflight:preflight_stale", result["blockers"])

    def test_post_apply_preflight_does_not_resume_pre_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = fixture_args(root)
            args.preflight = fixture_preflight(root, collected="2026-06-16T11:30:00Z", stage="post_apply_observation")
            result = self.evaluate_fixture(args)
        self.assertFalse(result["passed"])
        self.assertIn("current_board_preflight:preflight_stage_mismatch", result["blockers"])

    def test_preflight_device_must_be_authorized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = fixture_args(root)
            args.preflight = fixture_preflight(root, collected="2026-06-16T11:30:00Z", device_hash="c" * 64)
            result = self.evaluate_fixture(args)
        self.assertFalse(result["passed"])
        self.assertIn("current_board_preflight:preflight_device_not_authorized", result["blockers"])

    def test_macro_snapshot_must_preserve_h2_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = fixture_args(root)
            args.macro_governance_summary = fixture_macro(root, h2_blockers=[])
            result = self.evaluate_fixture(args)
        self.assertFalse(result["passed"])
        self.assertIn("macro_governance_snapshot:macro_h2_blockers_not_exact", result["blockers"])

    def test_repo_clean_and_tracked_inputs_are_required_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = fixture_args(Path(tmp))
            original_repo_clean = globals()["repo_clean_guard"]
            original_tracked = globals()["tracked_input_guard"]
            try:
                globals()["repo_clean_guard"] = lambda: step(False, ["repo_dirty"])
                globals()["tracked_input_guard"] = lambda _paths: step(False, ["input_file_not_tracked"])
                result = evaluate(args, require_repo_clean=True)
            finally:
                globals()["repo_clean_guard"] = original_repo_clean
                globals()["tracked_input_guard"] = original_tracked
        self.assertFalse(result["passed"])
        self.assertIn("repo_clean:repo_dirty", result["blockers"])
        self.assertIn("tracked_inputs:input_file_not_tracked", result["blockers"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--macro-governance-summary", type=Path, default=DEFAULT_MACRO_SUMMARY)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--now-utc")
    parser.add_argument("--max-preflight-age-sec", type=int, default=4 * 60 * 60)
    parser.add_argument("--max-authorization-window-sec", type=int, default=24 * 60 * 60)
    parser.add_argument("--expected-preflight-stage", default="pre_apply")
    parser.add_argument("--allow-dirty-repo", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(OperationalResumeGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = evaluate(args, require_repo_clean=not args.allow_dirty_repo)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} result_claim={result['result_claim']}")
        for blocker in result["blockers"]:
            print(f"blocker={blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
