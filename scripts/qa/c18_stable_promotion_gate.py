#!/usr/bin/env python3
"""Default-deny C18 stable promotion evidence gate.

This gate validates the evidence file required before a C18 `stable` release can
be built or published. It does not publish, enable auto-pull, promote by itself,
or thaw player-runtime.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.stable_promotion.v1"
GATE_SCHEMA = "dadooh.c18.stable_promotion_gate.v1"
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
    "release_gate_sha256",
    "h2_readiness_sha256",
    "server_side_evidence_sha256",
    "soak_summary_sha256",
    "powerloss_matrix_sha256",
)
NON_CLAIMS = (
    "this_gate_does_not_publish_releases",
    "this_gate_does_not_enable_auto_pull",
    "this_gate_does_not_thaw_player_runtime",
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


def validate_data(data: dict[str, Any], *, evidence_path: str | None = None) -> dict[str, Any]:
    blockers: list[str] = []
    if data.get("schema") != SCHEMA:
        blockers.append("stable_promotion_schema")
    if data.get("component") != "totem-core":
        blockers.append("stable_promotion_component_not_totem_core")
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
    return {
        "schema": GATE_SCHEMA,
        "passed": not blockers,
        "result_claim": "stable_promotion_evidence_ready" if not blockers else "stable_promotion_evidence_blocked",
        "evidence_path": evidence_path,
        "blockers": blockers,
        "non_claims": list(NON_CLAIMS),
    }


def evaluate(path: Path | None) -> dict[str, Any]:
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
    return validate_data(data, evidence_path=str(path))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def valid_fixture() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "component": "totem-core",
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
        "release_gate_sha256": "a" * 64,
        "h2_readiness_sha256": "b" * 64,
        "server_side_evidence_sha256": "c" * 64,
        "soak_summary_sha256": "d" * 64,
        "powerloss_matrix_sha256": "e" * 64,
        "auto_pull_enabled": False,
        "public_player_runtime_thaw": False,
    }


class StablePromotionGateSelfTest(unittest.TestCase):
    def test_complete_fixture_passes(self) -> None:
        result = validate_data(valid_fixture())
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate C18 stable promotion evidence.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(StablePromotionGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = evaluate(args.evidence)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} blockers={len(result['blockers'])}")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
