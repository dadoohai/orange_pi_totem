#!/usr/bin/env python3
"""Validate C18 player-runtime thaw decision evidence.

This gate validates an operator decision artifact. It does not thaw
player-runtime, publish releases, enable auto-pull, or override the public
freeze. The decision must be bound to the target release and to the H2 evidence
families that justify a future public thaw.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.player_runtime.thaw_decision.v1"
GATE_SCHEMA = "dadooh.c18.player_runtime.thaw_decision_gate.v1"
COMPONENT = "player-runtime"
MAX_THAW_WINDOW_SEC = 4 * 60 * 60
REQUIRED_HASH_FIELDS = (
    "h1_release_gate_sha256",
    "release_gate_sha256",
    "powerloss_matrix_sha256",
    "soak_summary_sha256",
    "server_side_evidence_sha256",
    "server_side_current_snapshot_sha256",
    "server_side_trust_anchor_evidence_sha256",
    "stable_promotion_evidence_sha256",
)
REQUIRED_NON_CLAIMS = (
    "this_decision_does_not_execute_thaw",
    "this_decision_does_not_publish_releases",
    "this_decision_does_not_enable_auto_pull",
    "this_decision_does_not_override_freeze_rc_44_by_itself",
    "this_decision_requires_h2_green",
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


def is_source_commit(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def parse_utc(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    return parsed.astimezone(dt.timezone.utc)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def validate_window(data: dict[str, Any], now_utc: dt.datetime | None) -> list[str]:
    blockers: list[str] = []
    window = data.get("window") if isinstance(data.get("window"), dict) else {}
    start = parse_utc(window.get("start_utc"))
    end = parse_utc(window.get("end_utc"))
    if start is None:
        blockers.append("thaw_decision_window_start_invalid")
    if end is None:
        blockers.append("thaw_decision_window_end_invalid")
    if start is not None and end is not None:
        if end <= start:
            blockers.append("thaw_decision_window_not_forward")
        elif (end - start).total_seconds() > MAX_THAW_WINDOW_SEC:
            blockers.append("thaw_decision_window_too_long")
        if now_utc is not None:
            now = now_utc.astimezone(dt.timezone.utc)
            if now < start or now > end:
                blockers.append("thaw_decision_window_inactive")
    return blockers


def validate_data(
    data: dict[str, Any],
    *,
    evidence_path: str | None = None,
    expected_hashes: dict[str, str] | None = None,
    require_expected_hashes: bool = False,
    expected_package_version: str | None = None,
    expected_source_commit: str | None = None,
    expected_payload_sha256: str | None = None,
    now_utc: dt.datetime | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    expected = expected_hashes or {}
    if data.get("schema") != SCHEMA:
        blockers.append("thaw_decision_schema")
    if data.get("component") != COMPONENT:
        blockers.append("thaw_decision_component_not_player_runtime")
    if data.get("channel") != "stable":
        blockers.append("thaw_decision_channel_not_stable")
    if data.get("approved") is not True:
        blockers.append("thaw_decision_not_approved")
    if data.get("acknowledges_h2_evidence") is not True:
        blockers.append("thaw_decision_missing_h2_ack")
    if data.get("explicit_operator_decision") is not True:
        blockers.append("thaw_decision_missing_explicit_operator_decision")
    if data.get("rollback_ready") is not True:
        blockers.append("thaw_decision_rollback_ready_missing_or_false")
    if data.get("auto_pull_enabled") is not False:
        blockers.append("thaw_decision_auto_pull_enabled")
    if data.get("thaw_execution_performed") is not False:
        blockers.append("thaw_decision_execution_already_performed")
    for key in ("operator", "rollback_owner"):
        if not isinstance(data.get(key), str) or not data.get(key).strip():
            blockers.append(f"thaw_decision_{key}_missing")
    if not isinstance(data.get("target_package_version"), str) or not data.get("target_package_version").strip():
        blockers.append("thaw_decision_target_package_version_missing")
    if not is_source_commit(data.get("target_source_commit")):
        blockers.append("thaw_decision_target_source_commit_missing_or_invalid")
    if not is_sha256(data.get("target_payload_sha256")):
        blockers.append("thaw_decision_target_payload_sha256_missing_or_invalid")
    if expected_package_version is not None and data.get("target_package_version") != expected_package_version:
        blockers.append("thaw_decision_target_package_version_mismatch")
    if expected_source_commit is not None and data.get("target_source_commit") != expected_source_commit:
        blockers.append("thaw_decision_target_source_commit_mismatch")
    if expected_payload_sha256 is not None and data.get("target_payload_sha256") != expected_payload_sha256:
        blockers.append("thaw_decision_target_payload_sha256_mismatch")
    for field in REQUIRED_HASH_FIELDS:
        if not is_sha256(data.get(field)):
            blockers.append(f"thaw_decision_{field}_missing_or_invalid")
    if require_expected_hashes:
        missing_expected = sorted(set(REQUIRED_HASH_FIELDS) - set(expected))
        if missing_expected:
            blockers.append("thaw_decision_expected_hashes_missing")
            blockers.extend(f"thaw_decision_expected_hash_missing:{field}" for field in missing_expected)
    for field, value in expected.items():
        if field in REQUIRED_HASH_FIELDS and data.get(field) != value:
            blockers.append(f"thaw_decision_{field}_mismatch")
    non_claims = data.get("non_claims")
    if not isinstance(non_claims, list):
        blockers.append("thaw_decision_non_claims_missing")
        non_claims = []
    missing_non_claims = sorted(set(REQUIRED_NON_CLAIMS) - {str(item) for item in non_claims})
    blockers.extend(f"thaw_decision_non_claim_missing:{item}" for item in missing_non_claims)
    blockers.extend(validate_window(data, now_utc))
    return {
        "schema": GATE_SCHEMA,
        "passed": not blockers,
        "result_claim": "thaw_decision_ready" if not blockers else "thaw_decision_blocked",
        "evidence_path": evidence_path,
        "expected_hashes": expected,
        "blockers": blockers,
        "non_claims": [
            "this_gate_does_not_thaw_player_runtime",
            "this_gate_does_not_publish_or_fetch_releases",
            "this_gate_does_not_override_freeze_rc_44",
        ],
    }


def evaluate(
    path: Path | None,
    *,
    expected_hashes: dict[str, str] | None = None,
    require_expected_hashes: bool = False,
    expected_package_version: str | None = None,
    expected_source_commit: str | None = None,
    expected_payload_sha256: str | None = None,
    now_utc: dt.datetime | None = None,
) -> dict[str, Any]:
    if path is None:
        return {
            "schema": GATE_SCHEMA,
            "passed": False,
            "result_claim": "thaw_decision_blocked",
            "evidence_path": None,
            "blockers": ["missing_operator_thaw_decision"],
            "non_claims": [
                "this_gate_does_not_thaw_player_runtime",
                "this_gate_does_not_publish_or_fetch_releases",
                "this_gate_does_not_override_freeze_rc_44",
            ],
        }
    data, errors = read_json(path)
    if errors:
        return {
            "schema": GATE_SCHEMA,
            "passed": False,
            "result_claim": "thaw_decision_blocked",
            "evidence_path": str(path),
            "blockers": errors,
            "non_claims": [
                "this_gate_does_not_thaw_player_runtime",
                "this_gate_does_not_publish_or_fetch_releases",
                "this_gate_does_not_override_freeze_rc_44",
            ],
        }
    return validate_data(
        data,
        evidence_path=str(path),
        expected_hashes=expected_hashes,
        require_expected_hashes=require_expected_hashes,
        expected_package_version=expected_package_version,
        expected_source_commit=expected_source_commit,
        expected_payload_sha256=expected_payload_sha256,
        now_utc=now_utc if now_utc is not None else utc_now(),
    )


def valid_fixture(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema": SCHEMA,
        "component": COMPONENT,
        "channel": "stable",
        "approved": True,
        "acknowledges_h2_evidence": True,
        "explicit_operator_decision": True,
        "rollback_ready": True,
        "auto_pull_enabled": False,
        "thaw_execution_performed": False,
        "operator": "operator-prod-01",
        "rollback_owner": "rollback-owner-01",
        "target_package_version": "c18.player-runtime-stable-test",
        "target_source_commit": "a" * 40,
        "target_payload_sha256": "b" * 64,
        "h1_release_gate_sha256": "0" * 64,
        "release_gate_sha256": "c" * 64,
        "powerloss_matrix_sha256": "d" * 64,
        "soak_summary_sha256": "e" * 64,
        "server_side_evidence_sha256": "f" * 64,
        "server_side_current_snapshot_sha256": "9" * 64,
        "server_side_trust_anchor_evidence_sha256": "1" * 64,
        "stable_promotion_evidence_sha256": "2" * 64,
        "window": {
            "start_utc": "2099-01-01T10:00:00Z",
            "end_utc": "2099-01-01T14:00:00Z",
        },
        "non_claims": list(REQUIRED_NON_CLAIMS),
    }
    data.update(overrides)
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ThawDecisionGateSelfTest(unittest.TestCase):
    def test_complete_fixture_passes(self) -> None:
        data = valid_fixture()
        result = validate_data(
            data,
            expected_hashes={field: data[field] for field in REQUIRED_HASH_FIELDS},
            require_expected_hashes=True,
            now_utc=dt.datetime(2099, 1, 1, 12, 0, tzinfo=dt.timezone.utc),
        )
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_missing_evidence_denies(self) -> None:
        result = evaluate(None)
        self.assertFalse(result["passed"])
        self.assertIn("missing_operator_thaw_decision", result["blockers"])

    def test_minimal_boolean_decision_denies(self) -> None:
        result = validate_data({"schema": SCHEMA, "approved": True, "acknowledges_h2_evidence": True})
        self.assertFalse(result["passed"])
        self.assertIn("thaw_decision_component_not_player_runtime", result["blockers"])
        self.assertIn("thaw_decision_release_gate_sha256_missing_or_invalid", result["blockers"])

    def test_expected_hash_mismatch_denies(self) -> None:
        data = valid_fixture()
        result = validate_data(
            data,
            expected_hashes={"server_side_evidence_sha256": "0" * 64},
            now_utc=dt.datetime(2099, 1, 1, 12, 0, tzinfo=dt.timezone.utc),
        )
        self.assertFalse(result["passed"])
        self.assertIn("thaw_decision_server_side_evidence_sha256_mismatch", result["blockers"])

        result = validate_data(
            data,
            expected_hashes={"server_side_current_snapshot_sha256": "0" * 64},
            now_utc=dt.datetime(2099, 1, 1, 12, 0, tzinfo=dt.timezone.utc),
        )
        self.assertFalse(result["passed"])
        self.assertIn("thaw_decision_server_side_current_snapshot_sha256_mismatch", result["blockers"])

    def test_window_and_execution_guards_deny(self) -> None:
        data = valid_fixture(auto_pull_enabled=True, thaw_execution_performed=True)
        result = validate_data(
            data,
            now_utc=dt.datetime(2100, 1, 1, 12, 0, tzinfo=dt.timezone.utc),
        )
        self.assertFalse(result["passed"])
        self.assertIn("thaw_decision_auto_pull_enabled", result["blockers"])
        self.assertIn("thaw_decision_execution_already_performed", result["blockers"])
        self.assertIn("thaw_decision_window_inactive", result["blockers"])

    def test_long_window_denies(self) -> None:
        data = valid_fixture(window={
            "start_utc": "2099-01-01T00:00:00Z",
            "end_utc": "2099-01-02T00:00:01Z",
        })
        result = validate_data(
            data,
            now_utc=dt.datetime(2099, 1, 1, 12, 0, tzinfo=dt.timezone.utc),
        )
        self.assertFalse(result["passed"])
        self.assertIn("thaw_decision_window_too_long", result["blockers"])

    def test_file_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "thaw-decision.json"
            write_json(path, valid_fixture())
            result = evaluate(
                path,
                now_utc=dt.datetime(2099, 1, 1, 12, 0, tzinfo=dt.timezone.utc),
            )
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--expected-h1-release-gate-sha256")
    parser.add_argument("--expected-release-gate-sha256")
    parser.add_argument("--expected-powerloss-matrix-sha256")
    parser.add_argument("--expected-soak-summary-sha256")
    parser.add_argument("--expected-server-side-evidence-sha256")
    parser.add_argument("--expected-server-side-current-snapshot-sha256")
    parser.add_argument("--expected-server-side-trust-anchor-evidence-sha256")
    parser.add_argument("--expected-stable-promotion-evidence-sha256")
    parser.add_argument("--expected-package-version")
    parser.add_argument("--expected-source-commit")
    parser.add_argument("--expected-payload-sha256")
    parser.add_argument("--now-utc")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def expected_hashes_from_cli(args: argparse.Namespace) -> dict[str, str]:
    mapping = {
        "h1_release_gate_sha256": args.expected_h1_release_gate_sha256,
        "release_gate_sha256": args.expected_release_gate_sha256,
        "powerloss_matrix_sha256": args.expected_powerloss_matrix_sha256,
        "soak_summary_sha256": args.expected_soak_summary_sha256,
        "server_side_evidence_sha256": args.expected_server_side_evidence_sha256,
        "server_side_current_snapshot_sha256": args.expected_server_side_current_snapshot_sha256,
        "server_side_trust_anchor_evidence_sha256": args.expected_server_side_trust_anchor_evidence_sha256,
        "stable_promotion_evidence_sha256": args.expected_stable_promotion_evidence_sha256,
    }
    return {key: value for key, value in mapping.items() if isinstance(value, str) and value}


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ThawDecisionGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    now = parse_utc(args.now_utc) if args.now_utc else None
    result = evaluate(
        args.evidence,
        expected_hashes=expected_hashes_from_cli(args),
        require_expected_hashes=True,
        expected_package_version=args.expected_package_version,
        expected_source_commit=args.expected_source_commit,
        expected_payload_sha256=args.expected_payload_sha256,
        now_utc=now,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} blockers={len(result['blockers'])}")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
