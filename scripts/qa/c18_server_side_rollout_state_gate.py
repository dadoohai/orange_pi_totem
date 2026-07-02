#!/usr/bin/env python3
"""Validate C18 server-side rollout state before H2/stable.

This gate validates a concrete, hash-bound rollout/allowlist state artifact. It
does not publish releases, enable auto-pull, promote stable, advance rollout, or
thaw player-runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.server_side_rollout_state.v1"
GATE_SCHEMA = "dadooh.c18.server_side_rollout_state_gate.v1"
RESULT_READY = "server_side_rollout_paused_pre_h2"
RESULT_BLOCKED = "server_side_rollout_state_blocked"
DEFAULT_STAGE = "paused_pre_h2"
DEFAULT_STATE = "paused"
DEFAULT_TARGET = {
    "version": "c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1",
    "component": "player-runtime",
    "channel": "homologation",
    "source_commit": "9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522",
    "payload_sha256": "d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0",
}
ALLOWED_TOP_LEVEL_FIELDS = (
    "schema",
    "passed",
    "result_claim",
    "target_package",
    "state",
    "current_stage",
    "rollout_enabled",
    "auto_pull_enabled",
    "percentage",
    "allowlist",
    "allowlist_count",
    "allowlist_identity",
    "empty_allowlist_blocks",
    "operator_window_active",
    "raw_device_ids_persisted",
    "stage_advance_allowed",
    "input_hashes",
    "non_claims",
)
FORBIDDEN_RAW_ID_KEYS = {
    "serial",
    "mac",
    "ip",
    "private_ip",
    "hostname",
    "ssid",
    "environment_id",
    "device_id",
    "email",
}
FORBIDDEN_POSITIVE_CLAIMS = (
    "published",
    "stable_authorized",
    "thaw_authorized",
    "operator_approved",
    "rollout_started",
    "production_authorized",
    "public_thaw",
)
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
MAC_RE = re.compile(r"\b[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}\b")
PRIVATE_IP_RE = re.compile(r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")
REQUIRED_NON_CLAIMS = (
    "this_state_does_not_publish_releases",
    "this_state_does_not_enable_auto_pull",
    "this_state_does_not_promote_stable",
    "this_state_does_not_thaw_player_runtime",
    "this_state_does_not_authorize_production",
    "this_state_does_not_advance_rollout",
    "this_state_does_not_replace_h2",
    "this_state_does_not_replace_powerloss_17_17",
    "this_state_does_not_replace_soak_24h",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path, blockers: list[str], label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append(f"{label}_json_read_failed:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        blockers.append(f"{label}_not_object")
        return {}
    return data


def scan_raw_identity(value: Any, blockers: list[str], path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}"
            if key in FORBIDDEN_RAW_ID_KEYS:
                blockers.append(f"rollout_state_raw_identifier_key:{key_path}")
            if key in FORBIDDEN_POSITIVE_CLAIMS and item is True:
                blockers.append(f"rollout_state_forbidden_positive_claim:{key_path}")
            scan_raw_identity(item, blockers, key_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            scan_raw_identity(item, blockers, f"{path}[{index}]")
    elif isinstance(value, str):
        if EMAIL_RE.search(value):
            blockers.append(f"rollout_state_raw_identifier_email:{path}")
        if MAC_RE.search(value):
            blockers.append(f"rollout_state_raw_identifier_mac:{path}")
        if PRIVATE_IP_RE.search(value):
            blockers.append(f"rollout_state_raw_identifier_private_ip:{path}")


def expected_target_from_args(args: argparse.Namespace) -> dict[str, str]:
    return {
        "version": args.expect_version,
        "component": args.expect_component,
        "channel": args.expect_channel,
        "source_commit": args.expect_source_commit,
        "payload_sha256": args.expect_payload_sha256,
    }


def validate_rollout_state(
    state_path: Path,
    *,
    server_side_evidence: Path | None = None,
    server_side_governance_gate: Path | None = None,
    server_side_asset_list: Path | None = None,
    expected_target: dict[str, str] | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    data = read_json(state_path, blockers, "rollout_state")
    expected = expected_target or DEFAULT_TARGET
    if not data:
        blockers.append("rollout_state_empty")
    else:
        if sorted(data) != sorted(ALLOWED_TOP_LEVEL_FIELDS):
            blockers.append("rollout_state_unexpected_or_missing_fields")
        scan_raw_identity(data, blockers)
        if data.get("schema") != SCHEMA:
            blockers.append("rollout_state_schema")
        if data.get("passed") is not True:
            blockers.append("rollout_state_not_passed")
        if data.get("result_claim") != RESULT_READY:
            blockers.append("rollout_state_result_claim")
        target = data.get("target_package") if isinstance(data.get("target_package"), dict) else {}
        for key, value in expected.items():
            if target.get(key) != value:
                blockers.append(f"rollout_state_target_{key}_mismatch")
        if data.get("rollout_enabled") is not False:
            blockers.append("rollout_state_rollout_enabled_not_false")
        if data.get("auto_pull_enabled") is not False:
            blockers.append("rollout_state_auto_pull_enabled_not_false")
        if data.get("state") != DEFAULT_STATE:
            blockers.append("rollout_state_state_not_paused")
        if data.get("current_stage") != DEFAULT_STAGE:
            blockers.append("rollout_state_current_stage_not_paused_pre_h2")
        if data.get("percentage") != 0:
            blockers.append("rollout_state_percentage_not_zero")
        if data.get("operator_window_active") is not False:
            blockers.append("rollout_state_operator_window_active_not_false")
        if data.get("raw_device_ids_persisted") is not False:
            blockers.append("rollout_state_raw_device_ids_persisted_not_false")
        if data.get("stage_advance_allowed") is not False:
            blockers.append("rollout_state_stage_advance_allowed_not_false")
        allowlist = data.get("allowlist")
        if allowlist != []:
            blockers.append("rollout_state_allowlist_not_empty")
        if data.get("allowlist_count") != 0:
            blockers.append("rollout_state_allowlist_count_not_zero")
        if data.get("allowlist_identity") != "sha256":
            blockers.append("rollout_state_allowlist_identity_not_sha256")
        if data.get("empty_allowlist_blocks") is not True:
            blockers.append("rollout_state_empty_allowlist_blocks_not_true")
        input_hashes = data.get("input_hashes") if isinstance(data.get("input_hashes"), dict) else {}
        if server_side_evidence is not None:
            if not server_side_evidence.is_file() or server_side_evidence.is_symlink():
                blockers.append("rollout_state_server_side_evidence_missing_or_symlink")
            elif input_hashes.get("server_side_evidence_sha256") != sha256_file(server_side_evidence):
                blockers.append("rollout_state_server_side_evidence_sha256_mismatch")
        if server_side_governance_gate is not None:
            if not server_side_governance_gate.is_file() or server_side_governance_gate.is_symlink():
                blockers.append("rollout_state_governance_gate_missing_or_symlink")
            elif input_hashes.get("server_side_governance_gate_sha256") != sha256_file(server_side_governance_gate):
                blockers.append("rollout_state_governance_gate_sha256_mismatch")
        if server_side_asset_list is not None:
            if not server_side_asset_list.is_file() or server_side_asset_list.is_symlink():
                blockers.append("rollout_state_asset_list_missing_or_symlink")
            elif input_hashes.get("server_side_asset_list_sha256") != sha256_file(server_side_asset_list):
                blockers.append("rollout_state_asset_list_sha256_mismatch")
        non_claims = set(data.get("non_claims") if isinstance(data.get("non_claims"), list) else [])
        for claim in REQUIRED_NON_CLAIMS:
            if claim not in non_claims:
                blockers.append(f"rollout_state_non_claim_missing:{claim}")
    return {
        "schema": GATE_SCHEMA,
        "passed": not blockers,
        "result_claim": RESULT_READY if not blockers else RESULT_BLOCKED,
        "blockers": sorted(set(blockers)),
        "state": str(state_path),
        "target_package": expected,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def valid_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    server_side_evidence = root / "server-side-governance.json"
    governance_gate = root / "server-side-governance-gate.json"
    asset_list = root / "server-side-asset-list.json"
    state = root / "server-side-rollout-state.json"
    write_json(server_side_evidence, {"schema": "fixture", "target": DEFAULT_TARGET})
    write_json(governance_gate, {"schema": "fixture", "passed": True})
    write_json(asset_list, {"schema": "fixture", "assets": []})
    write_json(state, {
        "schema": SCHEMA,
        "passed": True,
        "result_claim": RESULT_READY,
        "target_package": DEFAULT_TARGET,
        "state": DEFAULT_STATE,
        "rollout_enabled": False,
        "auto_pull_enabled": False,
        "current_stage": DEFAULT_STAGE,
        "percentage": 0,
        "allowlist": [],
        "allowlist_count": 0,
        "allowlist_identity": "sha256",
        "empty_allowlist_blocks": True,
        "operator_window_active": False,
        "raw_device_ids_persisted": False,
        "stage_advance_allowed": False,
        "input_hashes": {
            "server_side_evidence_sha256": sha256_file(server_side_evidence),
            "server_side_governance_gate_sha256": sha256_file(governance_gate),
            "server_side_asset_list_sha256": sha256_file(asset_list),
        },
        "non_claims": list(REQUIRED_NON_CLAIMS),
    })
    return state, server_side_evidence, governance_gate, asset_list


class RolloutStateGateSelfTest(unittest.TestCase):
    def test_valid_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state, evidence, gate, assets = valid_fixture(Path(tmp))
            result = validate_rollout_state(
                state,
                server_side_evidence=evidence,
                server_side_governance_gate=gate,
                server_side_asset_list=assets,
            )
        self.assertTrue(result["passed"], msg=result)

    def test_empty_state_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "server-side-rollout-state.json"
            write_json(state, {})
            result = validate_rollout_state(state)
        self.assertFalse(result["passed"])
        self.assertIn("rollout_state_empty", result["blockers"])

    def test_active_rollout_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state, evidence, gate, assets = valid_fixture(Path(tmp))
            data = json.loads(state.read_text(encoding="utf-8"))
            data["rollout_enabled"] = True
            data["percentage"] = 1
            data["current_stage"] = "pilot_allowlist"
            write_json(state, data)
            result = validate_rollout_state(
                state,
                server_side_evidence=evidence,
                server_side_governance_gate=gate,
                server_side_asset_list=assets,
            )
        self.assertFalse(result["passed"])
        self.assertIn("rollout_state_rollout_enabled_not_false", result["blockers"])
        self.assertIn("rollout_state_current_stage_not_paused_pre_h2", result["blockers"])

    def test_allowlist_and_raw_ids_deny(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state, evidence, gate, assets = valid_fixture(Path(tmp))
            data = json.loads(state.read_text(encoding="utf-8"))
            data["allowlist"] = ["sha256:" + "1" * 64]
            data["allowlist_count"] = 1
            data["raw_device_ids_persisted"] = True
            write_json(state, data)
            result = validate_rollout_state(
                state,
                server_side_evidence=evidence,
                server_side_governance_gate=gate,
                server_side_asset_list=assets,
            )
        self.assertFalse(result["passed"])
        self.assertIn("rollout_state_allowlist_not_empty", result["blockers"])
        self.assertIn("rollout_state_allowlist_count_not_zero", result["blockers"])
        self.assertIn("rollout_state_raw_device_ids_persisted_not_false", result["blockers"])

    def test_raw_identifiers_and_positive_claims_deny(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state, evidence, gate, assets = valid_fixture(Path(tmp))
            data = json.loads(state.read_text(encoding="utf-8"))
            data["published"] = True
            data["hostname"] = "board.local"
            data["allowlist"] = ["192.168.18.131"]
            write_json(state, data)
            result = validate_rollout_state(
                state,
                server_side_evidence=evidence,
                server_side_governance_gate=gate,
                server_side_asset_list=assets,
            )
        self.assertFalse(result["passed"])
        self.assertIn("rollout_state_unexpected_or_missing_fields", result["blockers"])
        self.assertIn("rollout_state_forbidden_positive_claim:$.published", result["blockers"])
        self.assertIn("rollout_state_raw_identifier_key:$.hostname", result["blockers"])
        self.assertIn("rollout_state_raw_identifier_private_ip:$.allowlist[0]", result["blockers"])

    def test_hash_mismatch_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state, evidence, gate, assets = valid_fixture(Path(tmp))
            evidence.write_text("tampered\n", encoding="utf-8")
            result = validate_rollout_state(
                state,
                server_side_evidence=evidence,
                server_side_governance_gate=gate,
                server_side_asset_list=assets,
            )
        self.assertFalse(result["passed"])
        self.assertIn("rollout_state_server_side_evidence_sha256_mismatch", result["blockers"])

    def test_target_mismatch_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state, evidence, gate, assets = valid_fixture(Path(tmp))
            data = json.loads(state.read_text(encoding="utf-8"))
            data["target_package"]["payload_sha256"] = "0" * 64
            write_json(state, data)
            result = validate_rollout_state(
                state,
                server_side_evidence=evidence,
                server_side_governance_gate=gate,
                server_side_asset_list=assets,
            )
        self.assertFalse(result["passed"])
        self.assertIn("rollout_state_target_payload_sha256_mismatch", result["blockers"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate C18 server-side rollout state.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--server-side-evidence", type=Path, default=None)
    parser.add_argument("--server-side-governance-gate", type=Path, default=None)
    parser.add_argument("--server-side-asset-list", type=Path, default=None)
    parser.add_argument("--expect-version", default=DEFAULT_TARGET["version"])
    parser.add_argument("--expect-component", default=DEFAULT_TARGET["component"])
    parser.add_argument("--expect-channel", default=DEFAULT_TARGET["channel"])
    parser.add_argument("--expect-source-commit", default=DEFAULT_TARGET["source_commit"])
    parser.add_argument("--expect-payload-sha256", default=DEFAULT_TARGET["payload_sha256"])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(RolloutStateGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if args.state is None:
        result = {
            "schema": GATE_SCHEMA,
            "passed": False,
            "result_claim": RESULT_BLOCKED,
            "blockers": ["rollout_state_missing"],
        }
    else:
        result = validate_rollout_state(
            args.state,
            server_side_evidence=args.server_side_evidence,
            server_side_governance_gate=args.server_side_governance_gate,
            server_side_asset_list=args.server_side_asset_list,
            expected_target=expected_target_from_args(args),
        )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} blockers={len(result['blockers'])}")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
