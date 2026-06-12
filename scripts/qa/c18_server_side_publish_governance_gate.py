#!/usr/bin/env python3
"""Default-deny C18 server-side publish governance gate.

This gate validates the evidence family consumed by H2 for publish/signature
governance. It does not publish, fetch, enable auto-pull, promote stable, or
thaw player-runtime.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.server_side_publish_governance.v1"
ALLOWED_CHANNELS = ("lab", "homologation", "stable")
REQUIRED_TRUE_FIELDS = (
    "publish_gate_enforced",
    "release_assets_verified",
    "signature_or_attestation_present",
    "auto_pull_policy_defined",
    "auto_pull_default_disabled",
    "channel_governance_defined",
    "stable_requires_promotion",
    "allowlist_controls_defined",
    "staged_rollout_defined",
    "rollback_policy_defined",
    "audit_trail_defined",
    "public_player_runtime_thaw_requires_h2",
)
NON_CLAIMS = (
    "this_gate_does_not_publish_releases",
    "this_gate_does_not_enable_auto_pull",
    "this_gate_does_not_promote_stable",
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


def validate_data(data: dict[str, Any], *, evidence_path: str | None = None) -> dict[str, Any]:
    blockers: list[str] = []
    if data.get("schema") != SCHEMA:
        blockers.append("server_side_schema")
    for key in REQUIRED_TRUE_FIELDS:
        if data.get(key) is not True:
            blockers.append(f"server_side_{key}_missing_or_false")
    if data.get("auto_pull_enabled") is True:
        blockers.append("server_side_auto_pull_enabled")
    channels = data.get("channels")
    if channels is not None:
        if channels != list(ALLOWED_CHANNELS):
            blockers.append("server_side_channels_not_exact")
    if data.get("channel_inheritance_allowed") is True:
        blockers.append("server_side_channel_inheritance_allowed")
    component_scope = data.get("component_scope")
    if component_scope is not None:
        if not isinstance(component_scope, list) or "totem-core" not in component_scope:
            blockers.append("server_side_component_scope_missing_totem_core")
    signed_assets = data.get("signed_or_attested_assets")
    if signed_assets is not None:
        if not isinstance(signed_assets, list) or len(signed_assets) < 3:
            blockers.append("server_side_signed_or_attested_assets_incomplete")
    return {
        "schema": "dadooh.c18.server_side_publish_governance_gate.v1",
        "passed": not blockers,
        "result_claim": "server_side_publish_governance_ready" if not blockers else "server_side_publish_governance_blocked",
        "evidence_path": evidence_path,
        "blockers": blockers,
        "non_claims": list(NON_CLAIMS),
    }


def evaluate(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "schema": "dadooh.c18.server_side_publish_governance_gate.v1",
            "passed": False,
            "result_claim": "server_side_publish_governance_blocked",
            "evidence_path": None,
            "blockers": ["missing_server_side_publish_governance"],
            "non_claims": list(NON_CLAIMS),
        }
    data, errors = read_json(path)
    if errors:
        return {
            "schema": "dadooh.c18.server_side_publish_governance_gate.v1",
            "passed": False,
            "result_claim": "server_side_publish_governance_blocked",
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
        "publish_gate_enforced": True,
        "release_assets_verified": True,
        "signature_or_attestation_present": True,
        "auto_pull_policy_defined": True,
        "auto_pull_default_disabled": True,
        "auto_pull_enabled": False,
        "channel_governance_defined": True,
        "channels": list(ALLOWED_CHANNELS),
        "channel_inheritance_allowed": False,
        "stable_requires_promotion": True,
        "allowlist_controls_defined": True,
        "staged_rollout_defined": True,
        "rollback_policy_defined": True,
        "audit_trail_defined": True,
        "public_player_runtime_thaw_requires_h2": True,
        "component_scope": ["totem-core", "player-runtime"],
        "signed_or_attested_assets": [
            "manifest",
            "payload",
            "c18-ota-release-gate",
        ],
    }


class ServerSidePublishGovernanceGateSelfTest(unittest.TestCase):
    def test_complete_fixture_passes(self) -> None:
        result = validate_data(valid_fixture())
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
        self.assertIn("this_gate_does_not_enable_auto_pull", result["non_claims"])

    def test_missing_evidence_denies(self) -> None:
        result = evaluate(None)
        self.assertFalse(result["passed"])
        self.assertIn("missing_server_side_publish_governance", result["blockers"])

    def test_signature_or_attestation_required(self) -> None:
        data = valid_fixture()
        data["signature_or_attestation_present"] = False
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_signature_or_attestation_present_missing_or_false", result["blockers"])

    def test_auto_pull_must_remain_disabled_by_default(self) -> None:
        data = valid_fixture()
        data["auto_pull_enabled"] = True
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_auto_pull_enabled", result["blockers"])

    def test_channel_inheritance_denies(self) -> None:
        data = valid_fixture()
        data["channel_inheritance_allowed"] = True
        result = validate_data(data)
        self.assertFalse(result["passed"])
        self.assertIn("server_side_channel_inheritance_allowed", result["blockers"])

    def test_file_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "server-side.json"
            write_json(path, valid_fixture())
            result = evaluate(path)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate C18 server-side publish governance evidence.")
    parser.add_argument("--evidence", type=Path, default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ServerSidePublishGovernanceGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = evaluate(args.evidence)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif not result["passed"]:
        print("\n".join(result["blockers"]), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
