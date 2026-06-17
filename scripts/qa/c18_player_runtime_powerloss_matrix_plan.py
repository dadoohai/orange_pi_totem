#!/usr/bin/env python3
"""Plan C18 player-runtime H2 physical power-loss matrix collection.

This tool is intentionally a planner, not evidence. It reads the target
player-runtime package plus already committed power-loss evidence directories,
reports which of the H2 17/17 checkpoints are target-bound and passing, and
emits board command skeletons for the missing physical checkpoints.
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


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "dadooh.c18.player_runtime.powerloss_matrix_plan.v1"
MANIFEST_SCHEMA = "dadooh.totem.update.v1"
POWERLOSS_MANIFEST_SCHEMA = "dadooh.c18.powerloss.evidence_manifest.v1"

REQUIRED_CHECKPOINTS = (
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
APPLY_CHECKPOINTS = (
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
)
ROLLBACK_CHECKPOINTS = tuple(item for item in REQUIRED_CHECKPOINTS if item.startswith("rollback_"))
PILOT_CHECKPOINTS = (
    "after_current_symlink",
    "rollback_after_current_to_previous",
    "rollback_after_previous_removed",
    "rollback_after_quarantine",
    "rollback_after_state_success",
)
APPLY_TARGET_AFTER_RESUME = {
    "after_current_symlink",
    "after_state_success",
    "before_stage_cleanup",
}
ROLLBACK_FALLBACK_BEFORE = {"rollback_after_identify_links", "rollback_after_current_unlinked"}
ROLLBACK_FALLBACK_AFTER = {"rollback_after_current_unlinked"}
ROLLBACK_SPECIAL_SETUP = {"rollback_after_current_unlinked"}
POSTCHECK_REQUIRED = {
    "rollback_after_previous_removed",
    "rollback_after_quarantine",
    "rollback_after_state_success",
}
POST_RECONCILE_STATE_REQUIRED = {
    "rollback_after_quarantine",
    "rollback_after_state_success",
}
NON_CLAIMS = (
    "this_plan_is_not_powerloss_evidence",
    "this_plan_does_not_claim_17_17",
    "this_plan_does_not_execute_board_commands",
    "this_plan_does_not_create_powerloss_artifacts",
    "this_plan_does_not_claim_checkpoint_reached",
    "this_plan_does_not_claim_boot_transition",
    "this_plan_does_not_claim_health_reconcile_or_adoption",
    "this_plan_does_not_replace_physical_power_cut",
    "this_plan_does_not_authorize_stable_or_production",
    "this_plan_does_not_thaw_player_runtime",
    "this_plan_does_not_publish_or_fetch_releases",
    "this_plan_does_not_prepare_customer_data_for_destructive_tests",
)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json_not_object:{path}")
    return data


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def load_package(manifest_path: Path, payload_path: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    blockers: list[str] = []
    if manifest.get("schema") != MANIFEST_SCHEMA:
        blockers.append("package_manifest_schema")
    if manifest.get("component") != "player-runtime":
        blockers.append("package_component_not_player_runtime")
    if manifest.get("channel") != "homologation":
        blockers.append("package_channel_not_homologation")
    if manifest.get("payload") != payload_path.name:
        blockers.append("package_payload_name_mismatch")
    return {
        "manifest_path": str(manifest_path),
        "payload_path": str(payload_path),
        "version": manifest.get("version"),
        "source_commit": manifest.get("source_commit"),
        "payload_sha256": manifest.get("payload_sha256"),
        "channel": manifest.get("channel"),
        "blockers": blockers,
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


def evidence_manifest(run_dir: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    path = run_dir / "evidence-manifest.json"
    if not path.is_file():
        return {}, ["evidence_manifest_missing"]
    try:
        data = read_json(path)
    except Exception as exc:
        return {}, [f"evidence_manifest_json:{type(exc).__name__}"]
    if data.get("schema") != POWERLOSS_MANIFEST_SCHEMA:
        errors.append("evidence_manifest_schema")
    return data, errors


def image_binding_errors(manifest: dict[str, Any], args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    for attr, key, label in (
        ("expect_image_tag", "image_tag", "image_tag"),
        ("expect_image_sha256", "image_sha256", "image_sha256"),
        ("expect_image_marker_sha256", "image_marker_sha256", "image_marker_sha256"),
    ):
        expected = getattr(args, attr)
        if expected is not None and manifest.get(key) != expected:
            errors.append(f"{label}_mismatch")
    return errors


def evaluate_evidence_dir(run_dir: Path, package: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    manifest, errors = evidence_manifest(run_dir)
    checkpoint = manifest.get("checkpoint")
    gate = run_powerloss_gate(run_dir) if not errors else {"passed": False, "returncode": None, "stderr_tail": "", "gate": {}}
    binding_errors = list(errors)
    if checkpoint not in REQUIRED_CHECKPOINTS:
        binding_errors.append("checkpoint_not_in_h2_matrix")
    if manifest.get("source_commit") != package.get("source_commit"):
        binding_errors.append("source_commit_mismatch")
    if manifest.get("target_package_version") != package.get("version"):
        binding_errors.append("target_package_version_mismatch")
    if manifest.get("target_payload_sha256") != package.get("payload_sha256"):
        binding_errors.append("target_payload_sha256_mismatch")
    binding_errors.extend(image_binding_errors(manifest, args))
    if gate.get("passed") is not True:
        binding_errors.append("powerloss_gate_failed")
    return {
        "dir": str(run_dir),
        "checkpoint": checkpoint,
        "pilot_checkpoint": checkpoint in PILOT_CHECKPOINTS,
        "gate_passed": gate.get("passed") is True,
        "gate_returncode": gate.get("returncode"),
        "binding_errors": binding_errors,
        "target_bound": not binding_errors,
    }


def board_path(board_bundle_dir: str, local_path: str) -> str:
    local = Path(local_path)
    if local.is_absolute():
        try:
            rel = local.relative_to(REPO_ROOT)
        except ValueError:
            rel = Path(local.name)
    elif ".." not in local.parts:
        rel = local
    else:
        rel = Path(local.name)
    return f"{board_bundle_dir.rstrip('/')}/{rel.as_posix()}"


def command_block(lines: list[str]) -> list[str]:
    return [line.rstrip() for line in lines if line.rstrip()]


def apply_resume_expected(checkpoint: str, target: str, previous: str) -> str:
    return target if checkpoint in APPLY_TARGET_AFTER_RESUME else previous


def rollback_resume_sources(checkpoint: str) -> tuple[str, str]:
    before = "fallback" if checkpoint in ROLLBACK_FALLBACK_BEFORE else "data"
    after = "fallback" if checkpoint in ROLLBACK_FALLBACK_AFTER else "data"
    return before, after


def plan_commands(checkpoint: str, package: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    target = str(package.get("version") or "${TARGET_VERSION}")
    previous = args.previous_version or "${PREVIOUS_VERSION}"
    manifest = board_path(args.board_bundle_dir, str(package["manifest_path"]))
    payload = board_path(args.board_bundle_dir, str(package["payload_path"]))
    evidence_root = f"{args.board_evidence_root.rstrip('/')}/{checkpoint}"
    common_env = "C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1"
    if checkpoint in APPLY_CHECKPOINTS:
        expected = apply_resume_expected(checkpoint, target, previous)
        arm = command_block([
            f"cd {shell_quote(args.board_bundle_dir)}",
            f"{common_env} \\",
            "python3 scripts/qa/c18_player_runtime_powerloss_trial.py \\",
            "  --phase arm-apply \\",
            f"  --checkpoint {shell_quote(checkpoint)} \\",
            f"  --manifest {shell_quote(manifest)} \\",
            f"  --payload {shell_quote(payload)} \\",
            f"  --canary-media {shell_quote(args.canary_media)} \\",
            "  --data-root /data \\",
            "  --allow-device-data-root \\",
            f"  --evidence-root {shell_quote(evidence_root + '/trial')} \\",
            f"  --startup-wait-sec {args.startup_wait_sec:g} \\",
            "  --json",
        ])
        resume = command_block([
            f"cd {shell_quote(args.board_bundle_dir)}",
            f"{common_env} \\",
            "python3 scripts/qa/c18_player_runtime_powerloss_trial.py \\",
            "  --phase resume \\",
            "  --data-root /data \\",
            "  --allow-device-data-root \\",
            f"  --evidence-root {shell_quote(evidence_root + '/trial')} \\",
            "  --expected-source data \\",
            f"  --expected-version {shell_quote(expected)} \\",
            "  --expected-source-after-reconcile data \\",
            f"  --expected-version-after-reconcile {shell_quote(expected)} \\",
            f"  --startup-wait-sec {args.startup_wait_sec:g} \\",
            "  --json",
        ])
        result = {
            "checkpoint": checkpoint,
            "phase": "apply",
            "requires_physical_cut": True,
            "requires_custom_setup": checkpoint == "after_previous_symlink",
            "setup_precondition": (
                "old-current-present-and-different-from-target"
                if checkpoint == "after_previous_symlink"
                else "standard-target-apply"
            ),
            "arm": arm,
            "resume_after_power_restore": resume,
            "expected_resume_version": expected,
            "notes": [
                "physical power must be removed only after CUT_POWER_NOW is printed and persisted",
                "remote reboot is not acceptable evidence",
                "fresh apply path is required for payload staging, release directory, and extract checkpoints",
            ] + (
                [
                    "after_previous_symlink is reachable only when an old current exists and differs from the target",
                ]
                if checkpoint == "after_previous_symlink"
                else []
            ),
        }
        if checkpoint == "after_previous_symlink":
            result["manual_setup_instructions"] = [
                "Use only a lab image or a board state that has been backed up for destructive H2 trials.",
                "Before arming, verify that the data current runtime exists and is the expected previous version, not the target package.",
                "Do not run this checkpoint immediately after a successful target apply; restore an old current first or use a freshly imaged/prepared board.",
                "Record the pre-arm current/previous topology in the checkpoint evidence notes before physical cut.",
            ]
        return result
    before_source, after_source = rollback_resume_sources(checkpoint)
    setup = command_block([
        f"cd {shell_quote(args.board_bundle_dir)}",
        f"mkdir -p {shell_quote(evidence_root + '/setup')}",
        "C18_PLAYER_RUNTIME_LAB_APPLY=1 C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1 \\",
        "python3 scripts/qa/c18_player_runtime_lab_apply.py \\",
        "  --lab-only-apply \\",
        f"  --manifest {shell_quote(manifest)} \\",
        f"  --payload {shell_quote(payload)} \\",
        "  --data-root /data \\",
        "  --allow-device-data-root \\",
        f"  --canary-media {shell_quote(args.canary_media)} \\",
        f"  --output-dir {shell_quote(evidence_root + '/setup/apply')} \\",
        f"  --startup-wait-sec {args.startup_wait_sec:g} \\",
        f"  --json > {shell_quote(evidence_root + '/setup/lab-apply.json')}",
        "python3 scripts/qa/c18_player_runtime_adoption_probe.py \\",
        "  --data-root /data \\",
        "  --expected-source data \\",
        f"  --expected-version {shell_quote(target)} \\",
        f"  --json > {shell_quote(evidence_root + '/setup/service-adoption.json')}",
        "python3 scripts/board/c18_playback_health_collect.py \\",
        f"  --duration-sec {args.duration_sec:g} \\",
        f"  --interval-sec {args.interval_sec:g} \\",
        f"  --output-dir {shell_quote(evidence_root + '/setup/service-health')} \\",
        f"  --json > {shell_quote(evidence_root + '/setup/service-health.json')}",
    ])
    custom_setup_required = checkpoint in ROLLBACK_SPECIAL_SETUP
    if custom_setup_required:
        setup = []
    arm = command_block([
        f"cd {shell_quote(args.board_bundle_dir)}",
        f"{common_env} \\",
        "python3 scripts/qa/c18_player_runtime_powerloss_trial.py \\",
        "  --phase arm-rollback \\",
        f"  --checkpoint {shell_quote(checkpoint)} \\",
        "  --data-root /data \\",
        "  --allow-device-data-root \\",
        f"  --evidence-root {shell_quote(evidence_root + '/trial')} \\",
        "  --quarantine-current \\",
    ])
    if checkpoint != "rollback_after_current_unlinked":
        arm.append(f"  --expect-rolled-to {shell_quote(previous)} \\")
    arm.append("  --json")
    resume_lines = [
        f"cd {shell_quote(args.board_bundle_dir)}",
        f"{common_env} \\",
        "python3 scripts/qa/c18_player_runtime_powerloss_trial.py \\",
        "  --phase resume \\",
        "  --data-root /data \\",
        "  --allow-device-data-root \\",
        f"  --evidence-root {shell_quote(evidence_root + '/trial')} \\",
        f"  --expected-source {before_source} \\",
    ]
    if before_source == "data":
        resume_lines.append(f"  --expected-version {shell_quote(previous)} \\")
    resume_lines.extend([
        f"  --expected-source-after-reconcile {after_source} \\",
    ])
    if after_source == "data":
        resume_lines.append(f"  --expected-version-after-reconcile {shell_quote(previous)} \\")
    resume_lines.extend([
        f"  --startup-wait-sec {args.startup_wait_sec:g} \\",
        "  --json",
    ])
    notes = [
        "physical power must be removed only after CUT_POWER_NOW is printed and persisted",
        "remote reboot is not acceptable evidence",
    ]
    if checkpoint in POSTCHECK_REQUIRED:
        notes.append("postcheck.txt is required by the evidence gate")
    if checkpoint in POST_RECONCILE_STATE_REQUIRED:
        notes.append("trial/resume/post-reconcile-state.json is required by the evidence gate")
    if checkpoint == "rollback_after_identify_links":
        notes.extend([
            "requires target as current and previous as the expected old active runtime before arm",
            "requires --quarantine-current so the checkpoint records quarantined_current=true",
            "standard fresh lab apply setup is used so target-over-previous topology is explicit",
            "resume is expected to see fallback before reconcile and data previous after reconcile",
        ])
    if checkpoint == "rollback_after_current_unlinked":
        notes.extend([
            "requires target as current with previous symlink absent and state previous absent before arm",
            "generic target-over-previous setup is intentionally not emitted for this checkpoint",
            "arm command is reachable only when rollback has no previous runtime to adopt",
            "rollback result is expected to be image_fallback, not previous",
            "prepare only on a lab image or after backing up device state",
        ])
    expected_rolled_to = "image_fallback" if checkpoint == "rollback_after_current_unlinked" else previous
    result = {
        "checkpoint": checkpoint,
        "phase": "rollback",
        "requires_physical_cut": True,
        "requires_custom_setup": custom_setup_required,
        "setup_precondition": (
            "target-current-without-previous-link-or-state"
            if custom_setup_required
            else "target-current-over-expected-previous"
        ),
        "setup_before_arm": setup,
        "arm": arm,
        "resume_after_power_restore": command_block(resume_lines),
        "expected_before_resume_source": before_source,
        "expected_after_reconcile_source": after_source,
        "expected_rolled_to": expected_rolled_to,
        "notes": notes,
    }
    if checkpoint == "rollback_after_current_unlinked":
        result["manual_setup_instructions"] = [
            "Use only a lab image or a board state that has been backed up for destructive H2 trials.",
            "Prepare target as the data current runtime, then remove the previous symlink and any state previous pointer before arming.",
            "Confirm the rollback topology is target-current-without-previous-link-or-state before running the arm command.",
            "Record the pre-arm current/previous/state topology in the checkpoint evidence notes before physical cut.",
        ]
    return result


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    package = load_package(args.package_manifest, args.package_payload)
    evidence_results = [
        evaluate_evidence_dir(run_dir, package, args)
        for run_dir in args.evidence_dir
    ]
    coverage: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for item in evidence_results:
        checkpoint = item.get("checkpoint")
        if not item.get("target_bound") or checkpoint not in REQUIRED_CHECKPOINTS:
            continue
        if checkpoint in coverage:
            duplicates.append(str(checkpoint))
            continue
        coverage[str(checkpoint)] = item
    missing = [checkpoint for checkpoint in REQUIRED_CHECKPOINTS if checkpoint not in coverage]
    blockers = list(package.get("blockers", []))
    if duplicates:
        blockers.append("duplicate_target_bound_checkpoint")
    if args.previous_version is None and any(checkpoint in ROLLBACK_CHECKPOINTS for checkpoint in missing):
        blockers.append("previous_version_required_for_rollback_commands")
    commands = [
        plan_commands(checkpoint, package, args)
        for checkpoint in missing
    ]
    return {
        "schema": SCHEMA,
        "passed": not missing and not blockers,
        "result_claim": "powerloss_matrix_plan_complete" if not missing and not blockers else "powerloss_matrix_plan_incomplete",
        "target_package": package,
        "required_checkpoints": list(REQUIRED_CHECKPOINTS),
        "covered_checkpoints": sorted(coverage),
        "missing_checkpoints": missing,
        "existing_evidence": evidence_results,
        "duplicate_target_bound_checkpoints": sorted(set(duplicates)),
        "blockers": blockers,
        "board": {
            "bundle_dir": args.board_bundle_dir,
            "evidence_root": args.board_evidence_root,
            "canary_media": args.canary_media,
            "previous_version": args.previous_version,
        },
        "commands_for_missing_checkpoints": commands,
        "non_claims": list(NON_CLAIMS),
    }


class PowerlossMatrixPlanSelfTest(unittest.TestCase):
    def test_board_path_preserves_safe_relative_package_paths(self) -> None:
        self.assertEqual(
            board_path("/data/c18-bundle", "releases/player-runtime/v1/manifest.json"),
            "/data/c18-bundle/releases/player-runtime/v1/manifest.json",
        )
        self.assertEqual(
            board_path("/data/c18-bundle", "../manifest.json"),
            "/data/c18-bundle/manifest.json",
        )

    def test_missing_matrix_emits_non_claims_and_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = root / "dadooh-player-runtime-test.tar.gz"
            payload.write_bytes(b"fixture\n")
            manifest = root / "dadooh-player-runtime-test.manifest.json"
            manifest.write_text(json.dumps({
                "schema": MANIFEST_SCHEMA,
                "component": "player-runtime",
                "version": "test",
                "channel": "homologation",
                "source_commit": "a" * 40,
                "payload": payload.name,
                "payload_sha256": "b" * 64,
            }), encoding="utf-8")
            args = argparse.Namespace(
                package_manifest=manifest,
                package_payload=payload,
                evidence_dir=[],
                expect_image_tag=None,
                expect_image_sha256=None,
                expect_image_marker_sha256=None,
                board_bundle_dir="/data/c18-test-bundle",
                board_evidence_root="/data/c18-evidence/h2-test",
                canary_media="/data/media/c18-canary-h264.mp4",
                previous_version="previous",
                startup_wait_sec=12.0,
                duration_sec=45.0,
                interval_sec=1.0,
            )
            result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["missing_checkpoints"]), 17)
        self.assertIn("this_plan_is_not_powerloss_evidence", result["non_claims"])
        self.assertIn("this_plan_does_not_execute_board_commands", result["non_claims"])
        self.assertIn("CUT_POWER_NOW", " ".join(result["commands_for_missing_checkpoints"][0]["notes"]))
        self.assertEqual(result["commands_for_missing_checkpoints"][0]["phase"], "apply")
        rollback = [item for item in result["commands_for_missing_checkpoints"] if item["checkpoint"] == "rollback_after_current_unlinked"][0]
        self.assertTrue(rollback["requires_custom_setup"])
        self.assertIn("manual_setup_instructions", rollback)
        self.assertEqual(rollback["expected_before_resume_source"], "fallback")
        self.assertEqual(rollback["expected_after_reconcile_source"], "fallback")
        self.assertEqual(rollback["expected_rolled_to"], "image_fallback")
        previous = [item for item in result["commands_for_missing_checkpoints"] if item["checkpoint"] == "after_previous_symlink"][0]
        self.assertTrue(previous["requires_custom_setup"])
        self.assertIn("manual_setup_instructions", previous)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--package-manifest", type=Path)
    parser.add_argument("--package-payload", type=Path)
    parser.add_argument("--evidence-dir", type=Path, action="append", default=[])
    parser.add_argument("--expect-image-tag")
    parser.add_argument("--expect-image-sha256")
    parser.add_argument("--expect-image-marker-sha256")
    parser.add_argument("--board-bundle-dir", default="/data/c18-h2-powerloss-bundle")
    parser.add_argument("--board-evidence-root", default="/data/c18-evidence/h2-powerloss")
    parser.add_argument("--canary-media", default="/data/media/c18-canary-h264.mp4")
    parser.add_argument("--previous-version")
    parser.add_argument("--startup-wait-sec", type=float, default=12.0)
    parser.add_argument("--duration-sec", type=float, default=45.0)
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(PowerlossMatrixPlanSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if args.package_manifest is None or args.package_payload is None:
        raise SystemExit("--package-manifest and --package-payload are required unless --self-test is used")
    result = evaluate(args)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif not result["passed"]:
        print("\n".join(result["missing_checkpoints"]), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
