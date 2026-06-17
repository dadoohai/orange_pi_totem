#!/usr/bin/env python3
"""Build fail-closed C18 player-runtime stable/thaw decision drafts.

The generated JSON files are scaffolds for the future H2/stable decision. They
are hash-bound to the supplied evidence, but they are intentionally not approved:
operator fields are empty, decision booleans are false, and the thaw window is
invalid until filled by an operator after H2 is actually green.

This tool does not publish releases, enable auto-pull, thaw player-runtime, or
override the public rc=44 freeze.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import c18_player_runtime_thaw_decision_gate as thaw_gate  # noqa: E402
import c18_stable_promotion_gate as stable_gate  # noqa: E402


STABLE_DRAFT_NAME = "c18-stable-promotion-draft.json"
THAW_DRAFT_NAME = "c18-player-runtime-thaw-decision-draft.json"
README_NAME = "README.md"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hashes(args: argparse.Namespace) -> dict[str, str]:
    return stable_gate.expected_hashes_from_args(args)


def target_from_server_side(args: argparse.Namespace) -> dict[str, str]:
    target, errors = stable_gate.thaw_decision_expected_target_from_args(args)
    if errors:
        raise ValueError(";".join(errors))
    return target


def build_stable_draft(args: argparse.Namespace) -> dict[str, Any]:
    hashes = stable_hashes(args)
    data: dict[str, Any] = {
        "schema": stable_gate.SCHEMA,
        "component": "player-runtime",
        "channel": "stable",
        "approved": False,
        "physical_homologation_passed": False,
        "powerloss_matrix_passed": False,
        "powerloss_semantics_complete": False,
        "soak_endurance_passed": False,
        "server_side_governance_passed": False,
        "release_gate_passed": False,
        "h2_readiness_passed": False,
        "explicit_operator_decision": False,
        "operator": "",
        "rollback_owner": "",
        "auto_pull_enabled": False,
        "public_player_runtime_thaw": False,
        "draft_status": "not_approved_template",
        "non_claims": [
            "this_draft_does_not_authorize_stable",
            "this_draft_does_not_publish_releases",
            "this_draft_does_not_enable_auto_pull",
            "this_draft_does_not_thaw_player_runtime",
            "this_draft_requires_h2_green_before_approval",
        ],
    }
    for field in stable_gate.REQUIRED_SHA256_FIELDS:
        data[field] = hashes.get(field, "")
    return data


def build_thaw_draft(args: argparse.Namespace, stable_promotion_sha256: str) -> dict[str, Any]:
    target = target_from_server_side(args)
    hashes = {
        key: value
        for key, value in stable_hashes(args).items()
        if key in thaw_gate.REQUIRED_HASH_FIELDS
    }
    hashes["stable_promotion_evidence_sha256"] = stable_promotion_sha256
    data: dict[str, Any] = {
        "schema": thaw_gate.SCHEMA,
        "component": "player-runtime",
        "channel": "stable",
        "approved": False,
        "acknowledges_h2_evidence": False,
        "explicit_operator_decision": False,
        "rollback_ready": False,
        "auto_pull_enabled": False,
        "thaw_execution_performed": False,
        "operator": "",
        "rollback_owner": "",
        "target_package_version": target["package_version"],
        "target_source_commit": target["source_commit"],
        "target_payload_sha256": target["payload_sha256"],
        "window": {
            "start_utc": "",
            "end_utc": "",
        },
        "non_claims": list(thaw_gate.REQUIRED_NON_CLAIMS),
        "draft_status": "not_approved_template",
    }
    for field in thaw_gate.REQUIRED_HASH_FIELDS:
        data[field] = hashes.get(field, "")
    return data


def validate_powerloss_inputs(run_dirs: list[Path]) -> list[str]:
    blockers: list[str] = []
    checkpoints: list[str] = []
    seen: set[str] = set()
    for run_dir in run_dirs:
        if not run_dir.is_dir():
            blockers.append(f"powerloss_dir_missing:{run_dir}")
            continue
        manifest_path = run_dir / "evidence-manifest.json"
        if not manifest_path.is_file():
            blockers.append(f"powerloss_manifest_missing:{run_dir}")
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            blockers.append(f"powerloss_manifest_json_error:{run_dir}:{type(exc).__name__}")
            continue
        if not isinstance(manifest, dict):
            blockers.append(f"powerloss_manifest_not_object:{run_dir}")
            continue
        if manifest.get("schema") != stable_gate.POWERLOSS_MANIFEST_SCHEMA:
            blockers.append(f"powerloss_manifest_schema:{run_dir}")
        checkpoint = manifest.get("checkpoint")
        if not isinstance(checkpoint, str) or not checkpoint:
            blockers.append(f"powerloss_manifest_checkpoint_missing:{run_dir}")
            continue
        checkpoints.append(checkpoint)
        if checkpoint in seen:
            blockers.append(f"powerloss_duplicate_checkpoint:{checkpoint}")
        seen.add(checkpoint)
    missing = sorted(set(stable_gate.REQUIRED_POWERLOSS_CHECKPOINTS) - set(checkpoints))
    extra = sorted(set(checkpoints) - set(stable_gate.REQUIRED_POWERLOSS_CHECKPOINTS))
    if missing:
        blockers.append("powerloss_matrix_incomplete")
        blockers.extend(f"powerloss_checkpoint_missing:{checkpoint}" for checkpoint in missing)
    if extra:
        blockers.append("powerloss_unknown_checkpoint")
        blockers.extend(f"powerloss_checkpoint_unknown:{checkpoint}" for checkpoint in extra)
    return blockers


def validate_artifact_inputs(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    file_fields = (
        "release_gate_summary",
        "server_side_evidence",
        "server_side_trust_anchor_evidence",
        "soak_summary",
    )
    for field in file_fields:
        path = getattr(args, field)
        if path is None:
            blockers.append(f"{field}_missing")
        elif not path.is_file():
            blockers.append(f"{field}_not_file:{path}")
    current_dir = getattr(args, "server_side_current_dir", None)
    if current_dir is None:
        blockers.append("server_side_current_dir_missing")
    elif not current_dir.is_dir():
        blockers.append(f"server_side_current_dir_not_dir:{current_dir}")
    elif not (current_dir / "evidence-manifest.json").is_file():
        blockers.append(f"server_side_current_manifest_not_file:{current_dir / 'evidence-manifest.json'}")
    blockers.extend(validate_powerloss_inputs(list(args.powerloss_evidence_dir or [])))
    return blockers


def blocked_result(args: argparse.Namespace, blockers: list[str]) -> dict[str, Any]:
    return {
        "schema": "dadooh.c18.player_runtime.stable_decision_draft_build.v1",
        "passed": False,
        "authorization_passed": False,
        "stable_authorized": False,
        "thaw_authorized": False,
        "result_claim": "stable_thaw_decision_drafts_blocked",
        "output_dir": str(args.output_dir),
        "blockers": blockers,
        "non_claims": [
            "this_tool_does_not_authorize_stable",
            "this_tool_does_not_thaw_player_runtime",
            "this_tool_does_not_publish_releases",
            "this_tool_does_not_enable_auto_pull",
            "this_tool_does_not_override_freeze_rc_44",
        ],
    }


def validate_draft_shape(
    stable_draft: dict[str, Any],
    thaw_draft: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    stable_result = stable_gate.validate_data(
        stable_draft,
        expected_component="player-runtime",
        expected_hashes=stable_hashes(args),
        require_expected_hashes=True,
    )
    target = target_from_server_side(args)
    thaw_hashes = {
        key: thaw_draft[key]
        for key in thaw_gate.REQUIRED_HASH_FIELDS
        if isinstance(thaw_draft.get(key), str) and thaw_draft[key]
    }
    thaw_result = thaw_gate.validate_data(
        thaw_draft,
        expected_hashes=thaw_hashes,
        require_expected_hashes=True,
        expected_package_version=target["package_version"],
        expected_source_commit=target["source_commit"],
        expected_payload_sha256=target["payload_sha256"],
    )
    stable_unexpected = [
        blocker
        for blocker in stable_result["blockers"]
        if blocker.endswith("_mismatch")
        or blocker.endswith("_missing_or_invalid")
        or blocker == "stable_promotion_expected_hashes_missing"
    ]
    thaw_unexpected = [
        blocker
        for blocker in thaw_result["blockers"]
        if blocker.endswith("_mismatch")
        or blocker.endswith("_missing_or_invalid")
        or blocker == "thaw_decision_expected_hashes_missing"
    ]
    return {
        "stable_gate_passed": stable_result["passed"],
        "stable_expected_fail_blockers": stable_result["blockers"],
        "stable_unexpected_blockers": stable_unexpected,
        "thaw_gate_passed": thaw_result["passed"],
        "thaw_expected_fail_blockers": thaw_result["blockers"],
        "thaw_unexpected_blockers": thaw_unexpected,
        "passed": (
            stable_result["passed"] is False
            and thaw_result["passed"] is False
            and not stable_unexpected
            and not thaw_unexpected
        ),
    }


def write_readme(path: Path, args: argparse.Namespace, stable_path: Path, thaw_path: Path, validation: dict[str, Any]) -> None:
    text = f"""# C18 player-runtime stable/thaw decision drafts

Status: draft only, not approved.

Generated files:

- `{stable_path.name}`: `dadooh.c18.stable_promotion.v1` scaffold for `player-runtime`.
- `{thaw_path.name}`: `dadooh.c18.player_runtime.thaw_decision.v1` scaffold bound to the stable draft hash.

These drafts must fail their gates until an operator fills the decision fields
after H2 is genuinely green. Do not flip booleans without rerunning the gates
over the real evidence paths.
Both drafts include `server_side_current_snapshot_sha256` so stable/thaw stays
bound to the current server-side validation snapshot, not just to raw release
evidence.

`passed=true` from this builder only means the drafts were written and confirmed
fail-closed. It is not stable authorization, thaw authorization, publish
authorization, or permission to enable auto-pull.

Required sequence:

1. Complete and commit the full 17/17 physical power-loss matrix.
2. Complete and commit the 24h soak summary.
3. Keep server-side/signature evidence green, current, and hash-bound to the target package.
4. Fill the stable promotion decision, then regenerate or update the thaw
   decision so `stable_promotion_evidence_sha256` matches the final stable file.
5. Run `scripts/qa/c18_stable_promotion_gate.py` with all real artifact paths and
   `--expected-component player-runtime`.
6. Run `scripts/qa/c18_player_runtime_h2_readiness_gate.py` with the same artifact
   family and the approved thaw decision.

Non-claims:

- this draft does not authorize production;
- this draft does not promote `stable`;
- this draft does not thaw `player-runtime`;
- this draft does not publish releases;
- this draft does not enable auto-pull;
- this draft does not override public freeze `rc=44`.

Inputs:

- release gate: `{args.release_gate_summary}`
- server-side evidence: `{args.server_side_evidence}`
- server-side current snapshot: `{args.server_side_current_dir}`
- server-side trust anchor: `{args.server_side_trust_anchor_evidence}`
- soak summary: `{args.soak_summary}`
- power-loss dirs: `{len(args.powerloss_evidence_dir or [])}`

Draft validation:

- expected fail-closed: `{str(validation["passed"]).lower()}`
"""
    path.write_text(text, encoding="utf-8")


def build(args: argparse.Namespace) -> dict[str, Any]:
    input_blockers = validate_artifact_inputs(args)
    if input_blockers:
        return blocked_result(args, input_blockers)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    stable_path = output_dir / STABLE_DRAFT_NAME
    thaw_path = output_dir / THAW_DRAFT_NAME
    readme_path = output_dir / README_NAME
    stable_draft = build_stable_draft(args)
    write_json(stable_path, stable_draft)
    stable_sha = sha256_file(stable_path)
    thaw_draft = build_thaw_draft(args, stable_sha)
    write_json(thaw_path, thaw_draft)
    validation = validate_draft_shape(stable_draft, thaw_draft, args)
    write_readme(readme_path, args, stable_path, thaw_path, validation)
    return {
        "schema": "dadooh.c18.player_runtime.stable_decision_draft_build.v1",
        "passed": validation["passed"],
        "authorization_passed": False,
        "stable_authorized": False,
        "thaw_authorized": False,
        "drafts_are_expected_to_fail_gates": validation["passed"],
        "result_claim": (
            "stable_thaw_decision_drafts_written_fail_closed"
            if validation["passed"]
            else "stable_thaw_decision_drafts_invalid"
        ),
        "output_dir": str(output_dir),
        "stable_promotion_draft": str(stable_path),
        "stable_promotion_draft_sha256": stable_sha,
        "thaw_decision_draft": str(thaw_path),
        "thaw_decision_draft_sha256": sha256_file(thaw_path),
        "readme": str(readme_path),
        "validation": validation,
        "non_claims": [
            "this_tool_does_not_authorize_stable",
            "this_tool_does_not_thaw_player_runtime",
            "this_tool_does_not_publish_releases",
            "this_tool_does_not_enable_auto_pull",
            "this_tool_does_not_override_freeze_rc_44",
        ],
    }


def write_fixture_inputs(root: Path) -> argparse.Namespace:
    release_gate = root / "h1-release-gate.json"
    server_side_dir = root / "server-side"
    server_side_dir.mkdir(parents=True)
    server_side = server_side_dir / "c18-server-side-publish-governance.json"
    server_side_current = root / "server-side-current"
    manifest = server_side_dir / "manifest.json"
    trust_anchor = root / "trust-anchor.json"
    soak = root / "soak.json"
    output = root / "out"
    server_side_current.mkdir(parents=True)
    write_json(release_gate, {
        "schema": stable_gate.PLAYER_RUNTIME_RELEASE_GATE_SCHEMA,
        "passed": True,
        "repo": {"dirty": False},
    })
    write_json(manifest, {
        "version": "c18.player-runtime-stable-test",
        "source_commit": "a" * 40,
        "payload_sha256": "b" * 64,
    })
    write_json(server_side, {
        "schema": "dadooh.c18.server_side_publish_governance.v1",
        "release_assets": {"manifest": "manifest.json"},
    })
    write_json(server_side_current / "evidence-manifest.json", {
        "schema": "dadooh.c18.server_side_current_validation_snapshot.v1",
        "passed": True,
        "result_claim": "server_side_publish_governance_ready",
    })
    write_json(trust_anchor, {"schema": "dadooh.c18.server_side_trust_anchor.v1"})
    write_json(soak, {
        "schema": stable_gate.SOAK_SCHEMA,
        "passed": True,
        "collection_policy": {"cycles": 24, "cycle_duration_sec": 60 * 60},
        "counters": {
            "max_panfrost_faults_delta": 0,
            "max_mmc_timeout_reset_delta": 0,
            "max_ext4_errors_delta": 0,
        },
    })
    powerloss_dirs: list[Path] = []
    for checkpoint in stable_gate.REQUIRED_POWERLOSS_CHECKPOINTS:
        run_dir = root / "powerloss" / checkpoint
        write_json(run_dir / "evidence-manifest.json", {
            "schema": stable_gate.POWERLOSS_MANIFEST_SCHEMA,
            "checkpoint": checkpoint,
            "image_tag": "c18-hwdecode-lab-1x",
            "image_sha256": "1" * 64,
            "image_marker_sha256": "2" * 64,
        })
        powerloss_dirs.append(run_dir)
    return argparse.Namespace(
        output_dir=output,
        release_gate_summary=release_gate,
        server_side_evidence=server_side,
        server_side_current_dir=server_side_current,
        server_side_trusted_key_pem=[],
        server_side_trust_anchor_evidence=trust_anchor,
        soak_summary=soak,
        powerloss_evidence_dir=powerloss_dirs,
        expect_image_tag="c18-hwdecode-lab-1x",
        expect_image_sha256="1" * 64,
        expect_image_marker_sha256="2" * 64,
    )


class StableDecisionDraftBuildSelfTest(unittest.TestCase):
    def test_drafts_are_hash_bound_but_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = write_fixture_inputs(Path(tmp))
            result = build(args)
            self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
            self.assertEqual(result["result_claim"], "stable_thaw_decision_drafts_written_fail_closed")
            self.assertFalse(result["authorization_passed"])
            self.assertFalse(result["stable_authorized"])
            self.assertFalse(result["thaw_authorized"])
            self.assertTrue(result["drafts_are_expected_to_fail_gates"])
            stable = json.loads(Path(result["stable_promotion_draft"]).read_text(encoding="utf-8"))
            thaw = json.loads(Path(result["thaw_decision_draft"]).read_text(encoding="utf-8"))
            self.assertFalse(stable["approved"])
            self.assertFalse(thaw["approved"])
            self.assertEqual(stable["operator"], "")
            self.assertEqual(thaw["operator"], "")
            self.assertEqual(thaw["stable_promotion_evidence_sha256"], result["stable_promotion_draft_sha256"])
            self.assertEqual(thaw["target_package_version"], "c18.player-runtime-stable-test")
            self.assertIn("stable_promotion_approved_missing_or_false", result["validation"]["stable_expected_fail_blockers"])
            self.assertIn("thaw_decision_not_approved", result["validation"]["thaw_expected_fail_blockers"])
            self.assertFalse(result["validation"]["stable_unexpected_blockers"])
            self.assertFalse(result["validation"]["thaw_unexpected_blockers"])

    def test_missing_artifact_hash_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = write_fixture_inputs(Path(tmp))
            args.soak_summary.unlink()
            result = build(args)
            self.assertFalse(result["passed"])
            self.assertIn(f"soak_summary_not_file:{args.soak_summary}", result["blockers"])

    def test_missing_powerloss_dir_fails_before_writing_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = write_fixture_inputs(Path(tmp))
            args.powerloss_evidence_dir = [Path(tmp) / "missing-powerloss-dir"]
            result = build(args)
            self.assertFalse(result["passed"])
            self.assertIn(f"powerloss_dir_missing:{args.powerloss_evidence_dir[0]}", result["blockers"])
            self.assertIn("powerloss_matrix_incomplete", result["blockers"])
            self.assertFalse(args.output_dir.exists())


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--release-gate-summary", type=Path)
    parser.add_argument("--server-side-evidence", type=Path)
    parser.add_argument("--server-side-current-dir", type=Path)
    parser.add_argument("--server-side-trust-anchor-evidence", type=Path)
    parser.add_argument("--soak-summary", type=Path)
    parser.add_argument("--powerloss-evidence-dir", type=Path, action="append", default=[])
    parser.add_argument("--expect-image-tag")
    parser.add_argument("--expect-image-sha256")
    parser.add_argument("--expect-image-marker-sha256")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def require_args(args: argparse.Namespace) -> list[str]:
    missing: list[str] = []
    for name in (
        "output_dir",
        "release_gate_summary",
        "server_side_evidence",
        "server_side_current_dir",
        "server_side_trust_anchor_evidence",
        "soak_summary",
        "expect_image_tag",
        "expect_image_sha256",
        "expect_image_marker_sha256",
    ):
        if getattr(args, name) in (None, ""):
            missing.append(name)
    if not args.powerloss_evidence_dir:
        missing.append("powerloss_evidence_dir")
    return missing


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(StableDecisionDraftBuildSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    missing = require_args(args)
    if missing:
        result = {
            "schema": "dadooh.c18.player_runtime.stable_decision_draft_build.v1",
            "passed": False,
            "authorization_passed": False,
            "stable_authorized": False,
            "thaw_authorized": False,
            "result_claim": "stable_thaw_decision_drafts_blocked",
            "blockers": [f"missing_{name}" for name in missing],
        }
    else:
        try:
            result = build(args)
        except Exception as exc:
            result = {
                "schema": "dadooh.c18.player_runtime.stable_decision_draft_build.v1",
                "passed": False,
                "authorization_passed": False,
                "stable_authorized": False,
                "thaw_authorized": False,
                "result_claim": "stable_thaw_decision_drafts_blocked",
                "blockers": [f"{type(exc).__name__}:{exc}"],
            }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"passed={str(result['passed']).lower()} "
            f"authorization_passed={str(result.get('authorization_passed', False)).lower()} "
            f"result={result['result_claim']}"
        )
        for blocker in result.get("blockers", []):
            print(f"- {blocker}")
        if result.get("output_dir"):
            print(result["output_dir"])
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
