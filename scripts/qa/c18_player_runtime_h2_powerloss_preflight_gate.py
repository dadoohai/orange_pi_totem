#!/usr/bin/env python3
"""Validate C18 H2 power-loss board preflight against the matrix plan.

This is an offline gate for a read-only board preflight. It does not count as
physical power-loss evidence, does not move H2 to green, and does not replace
the per-checkpoint evidence gate. Its purpose is to fail fast before an
operator starts a destructive physical session on the wrong board, package,
image, or topology.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.player_runtime.h2_powerloss_board_preflight_gate.v1"
PREFLIGHT_SCHEMA = "dadooh.c18.player_runtime.h2_powerloss_board_preflight.v1"
PLAN_SCHEMA = "dadooh.c18.player_runtime.powerloss_matrix_plan.v1"
PACKAGE_SCHEMA = "dadooh.totem.update.v1"
POLICY_SCHEMA = "dadooh.totem.update.policy.v1"
EXPECTED_MPV_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
EXPECTED_HWDECODE_MPV = "/opt/totem/hwdecode/bin/mpv"
APPLY_CHECKPOINTS = {
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
}
LINKED_TARGET_STILL_REACHABLE_APPLY = {"after_payload_staged"}
REQUIRED_NON_CLAIMS = {
    "this_preflight_is_not_powerloss_evidence",
    "this_preflight_does_not_claim_17_17",
    "this_preflight_does_not_arm_or_resume_trials",
    "this_preflight_does_not_replace_physical_power_cut",
    "this_preflight_does_not_create_or_modify_evidence",
    "this_preflight_does_not_apply_or_rollback_player_runtime",
    "this_preflight_does_not_probe_or_prove_public_freeze_rc44",
    "this_preflight_does_not_authorize_stable_or_production",
    "this_preflight_does_not_thaw_player_runtime",
    "this_preflight_does_not_publish_or_fetch_releases",
}
NON_CLAIMS = (
    "this_gate_does_not_claim_powerloss_evidence",
    "this_gate_does_not_claim_17_17",
    "this_gate_does_not_run_board_commands",
    "this_gate_does_not_authorize_stable_or_production",
    "this_gate_does_not_thaw_player_runtime",
)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json_not_object:{path}")
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


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def is_sha1(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


def plan_missing_checkpoints(plan: dict[str, Any]) -> list[str]:
    missing = plan.get("missing_checkpoints")
    if not isinstance(missing, list):
        return []
    return [str(item) for item in missing if isinstance(item, str) and item]


def target_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    target = plan.get("target_package")
    return target if isinstance(target, dict) else {}


def board_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    board = plan.get("board")
    return board if isinstance(board, dict) else {}


def check_equal(blockers: list[str], label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        blockers.append(label)


def validate_plan(plan: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    target = target_from_plan(plan)
    board = board_from_plan(plan)
    missing = plan_missing_checkpoints(plan)
    if plan.get("schema") != PLAN_SCHEMA:
        blockers.append("matrix_plan_schema")
    if not missing:
        blockers.append("matrix_plan_missing_checkpoints_missing")
    if target.get("channel") != "homologation":
        blockers.append("matrix_plan_target_not_homologation")
    if not isinstance(target.get("version"), str) or not target.get("version"):
        blockers.append("matrix_plan_target_version_missing")
    if not is_sha1(target.get("source_commit")):
        blockers.append("matrix_plan_target_source_commit_invalid")
    if not is_sha256(target.get("payload_sha256")):
        blockers.append("matrix_plan_target_payload_sha256_invalid")
    for key in ("bundle_dir", "evidence_root", "canary_media"):
        if not isinstance(board.get(key), str) or not board.get(key):
            blockers.append(f"matrix_plan_board_{key}_missing")
    return blockers, {
        "target": target,
        "board": board,
        "missing_checkpoints": missing,
        "missing_apply_checkpoints": [item for item in missing if item in APPLY_CHECKPOINTS],
    }


def validate_package(preflight: dict[str, Any], target: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    package = preflight.get("target_package") if isinstance(preflight.get("target_package"), dict) else {}
    check_equal(blockers, "package_schema", package.get("manifest_schema"), PACKAGE_SCHEMA)
    check_equal(blockers, "package_component_not_player_runtime", package.get("component"), "player-runtime")
    check_equal(blockers, "package_channel_not_homologation", package.get("channel"), "homologation")
    check_equal(blockers, "package_version_mismatch", package.get("version"), target.get("version"))
    check_equal(blockers, "package_source_commit_mismatch", package.get("source_commit"), target.get("source_commit"))
    check_equal(blockers, "package_payload_sha256_mismatch", package.get("payload_sha256"), target.get("payload_sha256"))
    check_equal(blockers, "package_payload_sha256_actual_mismatch", package.get("payload_sha256_actual"), target.get("payload_sha256"))
    if package.get("payload_sha256_matches_manifest") is not True:
        blockers.append("package_payload_sha256_not_verified")
    if package.get("manifest_present") is not True:
        blockers.append("package_manifest_missing")
    if package.get("payload_present") is not True:
        blockers.append("package_payload_missing")
    return blockers


def validate_board_paths(preflight: dict[str, Any], board: dict[str, Any], missing: list[str]) -> list[str]:
    blockers: list[str] = []
    board_paths = preflight.get("board_paths") if isinstance(preflight.get("board_paths"), dict) else {}
    for key in ("bundle_dir", "evidence_root", "canary_media"):
        check_equal(blockers, f"board_path_{key}_mismatch", board_paths.get(key), board.get(key))
    bundle = preflight.get("bundle") if isinstance(preflight.get("bundle"), dict) else {}
    canary = preflight.get("canary_media") if isinstance(preflight.get("canary_media"), dict) else {}
    evidence_root = preflight.get("evidence_root") if isinstance(preflight.get("evidence_root"), dict) else {}
    if bundle.get("is_dir") is not True:
        blockers.append("bundle_dir_missing")
    if canary.get("is_file") is not True:
        blockers.append("canary_media_missing")
    if evidence_root.get("exists") is True and evidence_root.get("is_dir") is not True:
        blockers.append("evidence_root_not_dir")
    if evidence_root.get("parent_exists") is not True or evidence_root.get("parent_is_dir") is not True:
        blockers.append("evidence_root_parent_missing")
    if evidence_root.get("parent_writable") is not True:
        blockers.append("evidence_root_parent_not_writable")
    children = evidence_root.get("direct_child_dirs")
    if isinstance(children, list):
        contaminating = sorted(set(str(item) for item in children) & set(missing))
        if contaminating:
            blockers.append("evidence_root_contains_pending_checkpoint_dirs")
    return blockers


def validate_policy_systemd(preflight: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    policy = preflight.get("policy") if isinstance(preflight.get("policy"), dict) else {}
    if policy.get("schema") != POLICY_SCHEMA:
        blockers.append("policy_schema")
    if policy.get("device_track") != "c18-hwdecode":
        blockers.append("policy_device_track_not_c18_hwdecode")
    if policy.get("device_channel") != "homologation":
        blockers.append("policy_not_homologation")
    if policy.get("allow_prerelease") is not True:
        blockers.append("policy_allow_prerelease_not_true")
    if policy.get("allow_downgrade") is not False:
        blockers.append("policy_allow_downgrade_not_false")
    if policy.get("allowed_components") != ["totem-core"]:
        blockers.append("policy_allowed_components_not_totem_core")
    systemd = preflight.get("systemd") if isinstance(preflight.get("systemd"), dict) else {}
    timer = systemd.get("update_timer") if isinstance(systemd.get("update_timer"), dict) else {}
    service = systemd.get("player_service") if isinstance(systemd.get("player_service"), dict) else {}
    if timer.get("enabled") is not False:
        blockers.append("update_timer_enabled")
    if timer.get("active") is not False:
        blockers.append("update_timer_active")
    if service.get("active") is not True:
        blockers.append("player_service_not_active")
    return blockers


def validate_image_wrappers(preflight: dict[str, Any], args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    image = preflight.get("image") if isinstance(preflight.get("image"), dict) else {}
    if image.get("marker_present") is not True:
        blockers.append("image_marker_missing")
    if args.expect_image_tag and image.get("image_tag") != args.expect_image_tag:
        blockers.append("image_tag_mismatch")
    if args.expect_image_marker_sha256 and image.get("marker_sha256") != args.expect_image_marker_sha256:
        blockers.append("image_marker_sha256_mismatch")
    wrappers = preflight.get("wrappers") if isinstance(preflight.get("wrappers"), dict) else {}
    if wrappers.get("expected_mpv_wrapper") != EXPECTED_MPV_WRAPPER:
        blockers.append("expected_mpv_wrapper_mismatch")
    if wrappers.get("expected_hwdecode_mpv") != EXPECTED_HWDECODE_MPV:
        blockers.append("expected_hwdecode_mpv_mismatch")
    mpv_wrapper = wrappers.get("mpv_wrapper") if isinstance(wrappers.get("mpv_wrapper"), dict) else {}
    hwdecode_mpv = wrappers.get("hwdecode_mpv") if isinstance(wrappers.get("hwdecode_mpv"), dict) else {}
    if mpv_wrapper.get("is_file") is not True or mpv_wrapper.get("executable") is not True:
        blockers.append("mpv_wrapper_missing_or_not_executable")
    if hwdecode_mpv.get("is_file") is not True or hwdecode_mpv.get("executable") is not True:
        blockers.append("hwdecode_mpv_missing_or_not_executable")
    return blockers


def validate_runtime_topology(preflight: dict[str, Any], analysis: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    player = preflight.get("player_runtime") if isinstance(preflight.get("player_runtime"), dict) else {}
    topology = preflight.get("runtime_topology") if isinstance(preflight.get("runtime_topology"), dict) else {}
    missing_apply = analysis["missing_apply_checkpoints"]
    if player.get("data_current_marker_verified") is not True:
        blockers.append("current_player_runtime_marker_not_verified")
    if topology.get("state_read_error"):
        blockers.append("runtime_state_read_error")
    linked_target = bool(topology.get("target_is_current_link") or topology.get("target_is_previous_link"))
    blocked_apply = [
        checkpoint
        for checkpoint in missing_apply
        if checkpoint not in LINKED_TARGET_STILL_REACHABLE_APPLY
    ] if linked_target else []
    if blocked_apply:
        blockers.append("topology_target_linked_blocks_apply_checkpoints")
    if "after_previous_symlink" in missing_apply:
        current_link = topology.get("current_link")
        target_link = topology.get("target_link")
        if not isinstance(current_link, str) or not current_link:
            blockers.append("topology_after_previous_symlink_requires_existing_current")
        elif target_link and current_link == target_link:
            blockers.append("topology_after_previous_symlink_current_already_target")
    if missing_apply and topology.get("target_release_dir_exists") is True:
        blockers.append("topology_target_release_dir_exists_for_fresh_apply")
    if topology.get("target_quarantined") is True and analysis["missing_checkpoints"]:
        blockers.append("topology_target_quarantined_requires_lab_reset")
    return blockers, {
        "target_linked": linked_target,
        "target_quarantined": topology.get("target_quarantined") is True,
        "blocked_apply_checkpoints_when_target_linked": blocked_apply,
        "missing_apply_checkpoints": missing_apply,
        "requires_custom_setup_checkpoints": [
            checkpoint
            for checkpoint in analysis["missing_checkpoints"]
            if checkpoint == "rollback_after_current_unlinked"
        ],
    }


def validate_freshness(
    preflight: dict[str, Any],
    args: argparse.Namespace,
    now_utc: dt.datetime | None,
) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    max_age_sec = args.max_age_sec
    raw_captured = (
        preflight.get("captured_at_utc")
        or preflight.get("collected_at_utc")
        or preflight.get("created_at_utc")
    )
    collected = parse_utc(raw_captured)
    age_sec: int | None = None
    if max_age_sec is not None:
        if max_age_sec < 0:
            blockers.append("preflight_max_age_invalid")
        if collected is None:
            blockers.append("preflight_captured_at_invalid")
        elif now_utc is None:
            blockers.append("preflight_now_invalid")
        else:
            age = (now_utc - collected).total_seconds()
            age_sec = int(age)
            if age < -60:
                blockers.append("preflight_captured_in_future")
            if max_age_sec >= 0 and age > max_age_sec:
                blockers.append("preflight_stale")
    return blockers, {
        "required": max_age_sec is not None,
        "captured_at_utc": raw_captured if isinstance(raw_captured, str) else None,
        "evaluated_at_utc": format_utc(now_utc),
        "max_age_sec": max_age_sec,
        "age_sec": age_sec,
    }


def evaluate(preflight_path: Path, matrix_plan_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    errors: list[str] = []
    try:
        preflight = read_json(preflight_path)
    except Exception as exc:
        preflight = {}
        errors.append(f"preflight_read_failed:{type(exc).__name__}")
    try:
        plan = read_json(matrix_plan_path)
    except Exception as exc:
        plan = {}
        errors.append(f"matrix_plan_read_failed:{type(exc).__name__}")
    plan_blockers, analysis = validate_plan(plan)
    blockers.extend(errors)
    blockers.extend(f"matrix_plan:{blocker}" for blocker in plan_blockers)
    if preflight.get("schema") != PREFLIGHT_SCHEMA:
        blockers.append("preflight_schema")
    if preflight.get("passed") is not True:
        blockers.append("preflight_not_passed")
    if preflight.get("collection_mode") != "read_only_preflight":
        blockers.append("preflight_collection_mode_not_read_only")
    non_claims = set(str(item) for item in preflight.get("non_claims", []) if isinstance(item, str))
    missing_non_claims = sorted(REQUIRED_NON_CLAIMS - non_claims)
    if missing_non_claims:
        blockers.append("preflight_non_claims_missing")
    target = analysis["target"]
    board = analysis["board"]
    now_utc = now_from_args(args)
    freshness_blockers, freshness = validate_freshness(preflight, args, now_utc)
    blockers.extend(freshness_blockers)
    blockers.extend(f"target_package:{blocker}" for blocker in validate_package(preflight, target))
    blockers.extend(f"board_paths:{blocker}" for blocker in validate_board_paths(
        preflight,
        board,
        analysis["missing_checkpoints"],
    ))
    blockers.extend(f"policy_systemd:{blocker}" for blocker in validate_policy_systemd(preflight))
    blockers.extend(f"image_wrappers:{blocker}" for blocker in validate_image_wrappers(preflight, args))
    topology_blockers, topology_analysis = validate_runtime_topology(preflight, analysis)
    blockers.extend(f"runtime_topology:{blocker}" for blocker in topology_blockers)
    return {
        "schema": SCHEMA,
        "evaluated_at_utc": format_utc(now_utc),
        "passed": not blockers,
        "result_claim": (
            "h2_powerloss_board_preflight_accepted"
            if not blockers
            else "h2_powerloss_board_preflight_blocked"
        ),
        "preflight": str(preflight_path),
        "matrix_plan": str(matrix_plan_path),
        "target_package": {
            "version": target.get("version"),
            "source_commit": target.get("source_commit"),
            "payload_sha256": target.get("payload_sha256"),
        },
        "matrix": {
            "missing_checkpoints": analysis["missing_checkpoints"],
            "missing_apply_checkpoints": analysis["missing_apply_checkpoints"],
        },
        "freshness": freshness,
        "topology_analysis": topology_analysis,
        "missing_preflight_non_claims": missing_non_claims,
        "blockers": blockers,
        "non_claims": list(NON_CLAIMS),
    }


def fixture_plan(root: Path) -> Path:
    path = root / "powerloss-matrix-plan.json"
    write_json(path, {
        "schema": PLAN_SCHEMA,
        "target_package": {
            "version": "c18.player-runtime-test",
            "source_commit": "a" * 40,
            "payload_sha256": "b" * 64,
            "channel": "homologation",
        },
        "board": {
            "bundle_dir": "/data/c18-bundle",
            "evidence_root": "/data/c18-evidence/h2-test",
            "canary_media": "/data/media/c18-canary.mp4",
        },
        "missing_checkpoints": ["after_release_dir_created", "after_previous_symlink"],
    })
    return path


def fixture_preflight(root: Path) -> Path:
    path = root / "board-preflight.json"
    write_json(path, {
        "schema": PREFLIGHT_SCHEMA,
        "passed": True,
        "captured_at_utc": "2026-06-16T11:30:00Z",
        "collection_mode": "read_only_preflight",
        "target_package": {
            "manifest_schema": PACKAGE_SCHEMA,
            "component": "player-runtime",
            "channel": "homologation",
            "version": "c18.player-runtime-test",
            "source_commit": "a" * 40,
            "payload_sha256": "b" * 64,
            "payload_sha256_actual": "b" * 64,
            "payload_sha256_matches_manifest": True,
            "manifest_present": True,
            "payload_present": True,
        },
        "board_paths": {
            "bundle_dir": "/data/c18-bundle",
            "evidence_root": "/data/c18-evidence/h2-test",
            "canary_media": "/data/media/c18-canary.mp4",
        },
        "bundle": {"is_dir": True},
        "canary_media": {"is_file": True},
        "evidence_root": {
            "exists": False,
            "is_dir": False,
            "parent_exists": True,
            "parent_is_dir": True,
            "parent_writable": True,
            "direct_child_dirs": [],
        },
        "policy": {
            "schema": POLICY_SCHEMA,
            "device_track": "c18-hwdecode",
            "device_channel": "homologation",
            "allow_prerelease": True,
            "allow_downgrade": False,
            "allowed_components": ["totem-core"],
        },
        "systemd": {
            "update_timer": {"enabled": False, "active": False},
            "player_service": {"active": True},
        },
        "image": {
            "marker_present": True,
            "image_tag": "c18-hwdecode-lab-test",
            "marker_sha256": "c" * 64,
        },
        "player_runtime": {"data_current_marker_verified": True},
        "runtime_topology": {
            "state_read_error": None,
            "current_link": "releases/previous",
            "previous_link": None,
            "target_link": "releases/c18.player-runtime-test",
            "target_release_dir_exists": False,
            "target_is_current_link": False,
            "target_is_previous_link": False,
            "target_quarantined": False,
        },
        "wrappers": {
            "expected_mpv_wrapper": EXPECTED_MPV_WRAPPER,
            "expected_hwdecode_mpv": EXPECTED_HWDECODE_MPV,
            "mpv_wrapper": {"is_file": True, "executable": True},
            "hwdecode_mpv": {"is_file": True, "executable": True},
        },
        "non_claims": sorted(REQUIRED_NON_CLAIMS),
    })
    return path


def fixture_args() -> argparse.Namespace:
    return argparse.Namespace(
        expect_image_tag="c18-hwdecode-lab-test",
        expect_image_marker_sha256="c" * 64,
        max_age_sec=None,
        now_utc=None,
    )


class H2PowerlossPreflightGateSelfTest(unittest.TestCase):
    def test_accepts_clean_target_bound_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = evaluate(fixture_preflight(root), fixture_plan(root), fixture_args())
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
        self.assertIn("this_gate_does_not_claim_17_17", result["non_claims"])

    def test_rejects_target_linked_for_post_payload_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preflight = fixture_preflight(root)
            data = read_json(preflight)
            data["runtime_topology"]["target_is_current_link"] = True
            data["runtime_topology"]["current_link"] = "releases/c18.player-runtime-test"
            write_json(preflight, data)
            result = evaluate(preflight, fixture_plan(root), fixture_args())
        self.assertFalse(result["passed"])
        self.assertIn("runtime_topology:topology_target_linked_blocks_apply_checkpoints", result["blockers"])

    def test_rejects_target_quarantined_before_matrix_setup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preflight = fixture_preflight(root)
            data = read_json(preflight)
            data["runtime_topology"]["target_quarantined"] = True
            write_json(preflight, data)
            result = evaluate(preflight, fixture_plan(root), fixture_args())
        self.assertFalse(result["passed"])
        self.assertIn("runtime_topology:topology_target_quarantined_requires_lab_reset", result["blockers"])

    def test_rejects_existing_target_release_dir_for_fresh_apply_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preflight = fixture_preflight(root)
            data = read_json(preflight)
            data["runtime_topology"]["target_release_dir_exists"] = True
            write_json(preflight, data)
            result = evaluate(preflight, fixture_plan(root), fixture_args())
        self.assertFalse(result["passed"])
        self.assertIn("runtime_topology:topology_target_release_dir_exists_for_fresh_apply", result["blockers"])

    def test_rejects_stable_or_wrong_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preflight = fixture_preflight(root)
            data = read_json(preflight)
            data["target_package"]["channel"] = "stable"
            data["policy"]["allowed_components"] = ["totem-core", "player-runtime"]
            write_json(preflight, data)
            result = evaluate(preflight, fixture_plan(root), fixture_args())
        self.assertFalse(result["passed"])
        self.assertIn("target_package:package_channel_not_homologation", result["blockers"])
        self.assertIn("policy_systemd:policy_allowed_components_not_totem_core", result["blockers"])

    def test_rejects_pending_checkpoint_dir_contamination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preflight = fixture_preflight(root)
            data = read_json(preflight)
            data["evidence_root"]["exists"] = True
            data["evidence_root"]["is_dir"] = True
            data["evidence_root"]["direct_child_dirs"] = ["after_release_dir_created"]
            write_json(preflight, data)
            result = evaluate(preflight, fixture_plan(root), fixture_args())
        self.assertFalse(result["passed"])
        self.assertIn("board_paths:evidence_root_contains_pending_checkpoint_dirs", result["blockers"])

    def test_requires_explicit_non_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preflight = fixture_preflight(root)
            data = read_json(preflight)
            data["non_claims"] = []
            write_json(preflight, data)
            result = evaluate(preflight, fixture_plan(root), fixture_args())
        self.assertFalse(result["passed"])
        self.assertIn("preflight_non_claims_missing", result["blockers"])

    def test_accepts_fresh_preflight_when_max_age_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = fixture_args()
            args.max_age_sec = 4 * 60 * 60
            args.now_utc = "2026-06-16T12:00:00Z"
            result = evaluate(fixture_preflight(root), fixture_plan(root), args)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
        self.assertTrue(result["freshness"]["required"])
        self.assertEqual(result["freshness"]["age_sec"], 1800)

    def test_rejects_stale_preflight_when_max_age_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = fixture_args()
            args.max_age_sec = 4 * 60 * 60
            args.now_utc = "2026-06-16T16:00:01Z"
            result = evaluate(fixture_preflight(root), fixture_plan(root), args)
        self.assertFalse(result["passed"])
        self.assertIn("preflight_stale", result["blockers"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--matrix-plan", type=Path)
    parser.add_argument("--expect-image-tag", required=False)
    parser.add_argument("--expect-image-marker-sha256", required=False)
    parser.add_argument(
        "--max-age-sec",
        type=int,
        help="Require the preflight capture to be no older than this many seconds.",
    )
    parser.add_argument(
        "--now-utc",
        help="Override evaluation time for tests/repro, formatted as YYYY-MM-DDTHH:MM:SSZ.",
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(H2PowerlossPreflightGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if args.preflight is None or args.matrix_plan is None:
        raise SystemExit("--preflight and --matrix-plan are required unless --self-test is used")
    result = evaluate(args.preflight, args.matrix_plan, args)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} result={result['result_claim']}")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
