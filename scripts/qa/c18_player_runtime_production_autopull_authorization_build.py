#!/usr/bin/env python3
"""Build flat C18 player-runtime production auto-pull authorization.

The builder is offline and fail-closed. It derives hashes and identity from the
exact manifest, payload, and release-gate artifacts, then writes the flat JSON
contract consumed by scripts/board/totem_updatectl.py.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import c18_player_runtime_production_autopull_authorization_gate as gate  # noqa: E402


BUILD_SCHEMA = "dadooh.c18.player_runtime.production_autopull_authorization_build.v1"


def required_arg_blockers(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    for name in (
        "manifest",
        "payload",
        "release_gate",
        "output",
        "operator",
        "rollback_owner",
        "accepted_at_local_date",
    ):
        if getattr(args, name) in (None, ""):
            blockers.append(f"missing_{name}")
    if args.risk_accepted is not True:
        blockers.append("risk_accepted_flag_missing")
    if args.accepted_at_local_date is not None and gate.parse_local_date(args.accepted_at_local_date) is None:
        blockers.append("accepted_at_local_date_invalid")
    if args.rollout_mode not in (None, "", gate.ROLL_OUT_MODE):
        blockers.append("rollout_mode_not_canonical")
    return blockers


def build_authorization(args: argparse.Namespace) -> dict[str, Any]:
    blockers = required_arg_blockers(args)
    if blockers:
        return blocked_result(args, blockers)

    expected, artifact_blockers = gate.expected_authorization_from_artifacts(
        args.manifest,
        args.payload,
        args.release_gate,
        operator=args.operator.strip(),
        rollback_owner=args.rollback_owner.strip(),
        accepted_at_local_date=args.accepted_at_local_date,
        rollout_mode=args.rollout_mode,
    )
    if artifact_blockers:
        return blocked_result(args, artifact_blockers)

    validation = gate.validate_authorization_data(expected, expected=expected)
    if not validation["passed"]:
        return blocked_result(args, validation["blockers"])

    assert args.output is not None
    gate.write_json(args.output, expected)
    return {
        "schema": BUILD_SCHEMA,
        "passed": True,
        "result_claim": "production_autopull_authorization_written",
        "authorization_path": str(args.output),
        "authorization_sha256": gate.sha256_file(args.output),
        "repo": expected["repo"],
        "tag_name": expected["tag_name"],
        "version": expected["version"],
        "source_commit": expected["source_commit"],
        "payload_sha256": expected["payload_sha256"],
        "manifest_sha256": expected["manifest_sha256"],
        "release_gate_asset_name": expected["release_gate_asset_name"],
        "release_gate_sha256": expected["release_gate_sha256"],
        "blockers": [],
        "non_claims": list(gate.GATE_NON_CLAIMS),
    }


def blocked_result(args: argparse.Namespace, blockers: list[str]) -> dict[str, Any]:
    return {
        "schema": BUILD_SCHEMA,
        "passed": False,
        "result_claim": "production_autopull_authorization_blocked",
        "authorization_path": str(args.output) if getattr(args, "output", None) is not None else None,
        "blockers": blockers,
        "non_claims": list(gate.GATE_NON_CLAIMS),
    }


def fixture_args(root: Path, *, risk_accepted: bool = True) -> argparse.Namespace:
    manifest, payload, release_path = gate.write_fixture_artifacts(root)
    return argparse.Namespace(
        manifest=manifest,
        payload=payload,
        release_gate=release_path,
        output=root / "production-autopull-authorization.json",
        operator="operator-prod-01",
        rollback_owner="rollback-owner-01",
        rollout_mode=gate.ROLL_OUT_MODE,
        accepted_at_local_date="2026-07-05",
        risk_accepted=risk_accepted,
        json=False,
    )


def load_updatectl_module() -> Any:
    path = REPO_ROOT / "scripts" / "board" / "totem_updatectl.py"
    spec = importlib.util.spec_from_file_location("totem_updatectl_for_authorization_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("totem_updatectl_import_spec_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProductionAutopullAuthorizationBuildSelfTest(unittest.TestCase):
    def test_builder_writes_gate_valid_flat_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = fixture_args(Path(tmp))
            result = build_authorization(args)
            self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
            data = json.loads(args.output.read_text(encoding="utf-8"))
            self.assertTrue(data["enabled"])
            self.assertTrue(data["auto_pull_enabled"])
            self.assertFalse(data["allow_latest"])
            self.assertFalse(data["allow_prerelease"])
            self.assertFalse(data["allow_downgrade"])
            self.assertNotIn("target", data)
            self.assertNotIn("authorization_scope", data)
            self.assertEqual(data["tag_name"], "player-runtime-" + data["version"])
            self.assertEqual(set(data["non_claims"]), set(gate.REQUIRED_NON_CLAIMS))
            gate_result = gate.evaluate(
                args.output,
                manifest=args.manifest,
                payload=args.payload,
                release_gate_path=args.release_gate,
            )
        self.assertTrue(gate_result["passed"], msg=json.dumps(gate_result, indent=2, sort_keys=True))

    def test_builder_output_is_accepted_by_updatectl_loader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = fixture_args(root)
            result = build_authorization(args)
            self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
            updatectl = load_updatectl_module()
            loaded = updatectl._load_player_runtime_production_authorization(args.output)
            self.assertEqual(loaded["version"], result["version"])
            empty = root / "empty.json"
            gate.write_json(empty, {})
            with self.assertRaisesRegex(RuntimeError, "player_runtime_authorization_fields"):
                updatectl._load_player_runtime_production_authorization(empty)
            nested = root / "nested.json"
            gate.write_json(nested, {
                "schema": gate.SCHEMA,
                "component": gate.COMPONENT,
                "authorization_scope": "production_autopull_exact_target",
                "approved": True,
                "risk_accepted": True,
                "target": {"version": result["version"]},
                "non_claims": list(gate.REQUIRED_NON_CLAIMS),
            })
            with self.assertRaisesRegex(RuntimeError, "player_runtime_authorization_fields"):
                updatectl._load_player_runtime_production_authorization(nested)

    def test_builder_requires_explicit_business_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = fixture_args(Path(tmp), risk_accepted=False)
            args.operator = ""
            args.accepted_at_local_date = ""
            result = build_authorization(args)
            self.assertFalse(result["passed"])
            self.assertIn("missing_operator", result["blockers"])
            self.assertIn("missing_accepted_at_local_date", result["blockers"])
            self.assertIn("risk_accepted_flag_missing", result["blockers"])
            self.assertFalse(args.output.exists())

    def test_builder_rejects_invalid_local_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = fixture_args(Path(tmp))
            args.accepted_at_local_date = "2026-7-5"
            result = build_authorization(args)
            self.assertFalse(result["passed"])
            self.assertIn("accepted_at_local_date_invalid", result["blockers"])
            self.assertFalse(args.output.exists())

    def test_builder_blocks_tampered_release_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = fixture_args(root)
            release_data = json.loads(args.release_gate.read_text(encoding="utf-8"))
            release_data["passed"] = False
            gate.write_json(args.release_gate, release_data)
            result = build_authorization(args)
            self.assertFalse(result["passed"])
            self.assertIn("release_gate_semantics_mismatch", result["blockers"])
            self.assertIn("release_gate_not_passed", result["blockers"])
            self.assertFalse(args.output.exists())

    def test_written_authorization_is_exact_target_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = fixture_args(root / "current")
            result = build_authorization(args)
            self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
            other_manifest, other_payload, other_release = gate.write_fixture_artifacts(
                root / "other",
                version="c18.player-runtime-other",
            )
            gate_result = gate.evaluate(
                args.output,
                manifest=other_manifest,
                payload=other_payload,
                release_gate_path=other_release,
            )
        self.assertFalse(gate_result["passed"])
        self.assertIn("authorization_version_mismatch", gate_result["blockers"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--release-gate", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--operator")
    parser.add_argument("--rollback-owner")
    parser.add_argument("--rollout-mode", default=gate.ROLL_OUT_MODE)
    parser.add_argument("--accepted-at-local-date")
    parser.add_argument("--risk-accepted", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProductionAutopullAuthorizationBuildSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = build_authorization(args)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} result_claim={result['result_claim']}")
        if result.get("authorization_path"):
            print(f"authorization={result['authorization_path']}")
        for blocker in result["blockers"]:
            print(f"blocker={blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
