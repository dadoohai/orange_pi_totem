#!/usr/bin/env python3
"""Validate a formal C18 playback soak exception.

This gate does not convert a failed soak into a clean soak. It validates an
explicit, target-bound business exception for one failed soak whose failure mode
is known and documented. The consuming H2/stable gates must keep reporting the
exception as an exception, not as clean endurance evidence.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.playback.soak_exception.v1"
GATE_SCHEMA = "dadooh.c18.playback.soak_exception_gate.v1"
SOAK_SCHEMA = "dadooh.c18.playback.soak.v1"
OPERATOR_EVENT_SCHEMA = "dadooh.c18.playback.soak.operator_event.v1"
COMPONENT = "player-runtime"
EXCEPTION_REASON = "hdmi_sink_unavailable_during_soak"
ALLOWED_FAILURE_REASONS = frozenset({"cycle_failed", "hwdec_expected_ratio_below_min"})
MIN_SOAK_DURATION_SEC = 24 * 60 * 60
REQUIRED_NON_CLAIMS = (
    "this_exception_does_not_make_the_soak_clean",
    "this_exception_is_not_a_generic_soak_bypass",
    "this_exception_does_not_publish_releases",
    "this_exception_does_not_enable_auto_pull",
    "this_exception_does_not_execute_public_thaw",
    "this_exception_is_bound_to_one_target_and_one_soak",
)
REQUIRED_COUNTER_ZERO_FIELDS = (
    "max_panfrost_faults_delta",
    "max_mmc_timeout_reset_delta",
    "max_ext4_errors_delta",
    "max_mpv_restart",
    "max_nrestarts_delta",
    "max_media_load_failed",
)


def read_json(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"json_error:{type(exc).__name__}"]
    if not isinstance(data, dict):
        return {}, ["json_not_object"]
    return data, []


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def is_source_commit(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def parse_local_offset(value: Any) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def soak_total_duration(summary: dict[str, Any]) -> float:
    policy = summary.get("collection_policy")
    counters = summary.get("counters")
    if isinstance(policy, dict):
        try:
            return float(policy.get("cycles", 0)) * float(policy.get("cycle_duration_sec", 0))
        except Exception:
            return 0.0
    if isinstance(counters, dict):
        try:
            return float(counters.get("duration_sec", 0))
        except Exception:
            return 0.0
    return 0.0


def validate_soak_summary(summary: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if summary.get("schema") != SOAK_SCHEMA:
        blockers.append("soak_exception_summary_schema")
    if summary.get("passed") is not False:
        blockers.append("soak_exception_summary_must_remain_failed")
    duration = soak_total_duration(summary)
    if duration < MIN_SOAK_DURATION_SEC:
        blockers.append("soak_exception_summary_duration_below_24h")
    failure_reasons = summary.get("failure_reasons")
    if not isinstance(failure_reasons, list) or not failure_reasons:
        blockers.append("soak_exception_summary_failure_reasons_missing")
        failure_reasons = []
    unexpected = sorted({str(item) for item in failure_reasons} - ALLOWED_FAILURE_REASONS)
    if unexpected:
        blockers.extend(f"soak_exception_summary_unexpected_failure_reason:{item}" for item in unexpected)
    counters = summary.get("counters") if isinstance(summary.get("counters"), dict) else {}
    for key in REQUIRED_COUNTER_ZERO_FIELDS:
        if counters.get(key) not in (0, 0.0):
            blockers.append(f"soak_exception_summary_{key}_nonzero_or_missing")
    return blockers


def validate_operator_event(event: dict[str, Any], *, expected_version: str | None) -> list[str]:
    blockers: list[str] = []
    if event.get("schema") != OPERATOR_EVENT_SCHEMA:
        blockers.append("soak_exception_operator_event_schema")
    if event.get("component") != COMPONENT:
        blockers.append("soak_exception_operator_event_component")
    if expected_version is not None and event.get("version") != expected_version:
        blockers.append("soak_exception_operator_event_version_mismatch")
    if event.get("classification") != "negative_for_clean_h2_soak_positive_for_runtime_resilience":
        blockers.append("soak_exception_operator_event_classification")
    expected_gate = event.get("expected_gate_result") if isinstance(event.get("expected_gate_result"), dict) else {}
    if expected_gate.get("clean_h2_soak") is not False:
        blockers.append("soak_exception_operator_event_clean_h2_claim")
    window = event.get("hdmi_disconnect_inferred_window_local")
    if not isinstance(window, dict):
        blockers.append("soak_exception_operator_event_disconnect_window_missing")
    else:
        start = parse_local_offset(window.get("start"))
        end = parse_local_offset(window.get("end"))
        if start is None or end is None or end < start:
            blockers.append("soak_exception_operator_event_disconnect_window_invalid")
    if parse_local_offset(event.get("hdmi_reconnect_kernel_event_local")) is None:
        blockers.append("soak_exception_operator_event_reconnect_kernel_missing")
    non_claims = event.get("non_claims")
    if not isinstance(non_claims, list):
        blockers.append("soak_exception_operator_event_non_claims_missing")
        non_claims = []
    for item in ("not_clean_constant_hdmi_soak", "not_h2_green", "not_stable_promotion", "not_public_thaw"):
        if item not in {str(value) for value in non_claims}:
            blockers.append(f"soak_exception_operator_event_non_claim_missing:{item}")
    return blockers


def validate_data(
    data: dict[str, Any],
    *,
    evidence_path: str | None = None,
    soak_summary: dict[str, Any] | None = None,
    operator_event: dict[str, Any] | None = None,
    expected_soak_summary_sha256: str | None = None,
    expected_operator_event_sha256: str | None = None,
    expected_package_version: str | None = None,
    expected_source_commit: str | None = None,
    expected_payload_sha256: str | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    if data.get("schema") != SCHEMA:
        blockers.append("soak_exception_schema")
    if data.get("component") != COMPONENT:
        blockers.append("soak_exception_component_not_player_runtime")
    if data.get("exception_reason") != EXCEPTION_REASON:
        blockers.append("soak_exception_reason")
    if data.get("accepted") is not True:
        blockers.append("soak_exception_not_accepted")
    if data.get("explicit_business_decision") is not True:
        blockers.append("soak_exception_missing_business_decision")
    if data.get("clean_soak_passed") is not False:
        blockers.append("soak_exception_clean_soak_claim")
    if data.get("failed_soak_accepted") is not True:
        blockers.append("soak_exception_failed_soak_not_accepted")
    if data.get("auto_pull_enabled") is not False:
        blockers.append("soak_exception_auto_pull_enabled")
    if data.get("public_thaw_executed") is not False:
        blockers.append("soak_exception_public_thaw_executed")
    if data.get("production_rollout_started") is not False:
        blockers.append("soak_exception_rollout_already_started")
    for key in ("operator", "rollback_owner", "risk_owner"):
        if not isinstance(data.get(key), str) or not data.get(key).strip():
            blockers.append(f"soak_exception_{key}_missing")
    if not isinstance(data.get("target_package_version"), str) or not data.get("target_package_version"):
        blockers.append("soak_exception_target_package_version_missing")
    if not is_source_commit(data.get("target_source_commit")):
        blockers.append("soak_exception_target_source_commit_missing_or_invalid")
    if not is_sha256(data.get("target_payload_sha256")):
        blockers.append("soak_exception_target_payload_sha256_missing_or_invalid")
    if expected_package_version is not None and data.get("target_package_version") != expected_package_version:
        blockers.append("soak_exception_target_package_version_mismatch")
    if expected_source_commit is not None and data.get("target_source_commit") != expected_source_commit:
        blockers.append("soak_exception_target_source_commit_mismatch")
    if expected_payload_sha256 is not None and data.get("target_payload_sha256") != expected_payload_sha256:
        blockers.append("soak_exception_target_payload_sha256_mismatch")
    for key in ("soak_summary_sha256", "operator_event_sha256"):
        if not is_sha256(data.get(key)):
            blockers.append(f"soak_exception_{key}_missing_or_invalid")
    if expected_soak_summary_sha256 is not None and data.get("soak_summary_sha256") != expected_soak_summary_sha256:
        blockers.append("soak_exception_soak_summary_sha256_mismatch")
    if expected_operator_event_sha256 is not None and data.get("operator_event_sha256") != expected_operator_event_sha256:
        blockers.append("soak_exception_operator_event_sha256_mismatch")
    non_claims = data.get("non_claims")
    if not isinstance(non_claims, list):
        blockers.append("soak_exception_non_claims_missing")
        non_claims = []
    missing_non_claims = sorted(set(REQUIRED_NON_CLAIMS) - {str(item) for item in non_claims})
    blockers.extend(f"soak_exception_non_claim_missing:{item}" for item in missing_non_claims)
    if soak_summary is not None:
        blockers.extend(validate_soak_summary(soak_summary))
    if operator_event is not None:
        blockers.extend(validate_operator_event(operator_event, expected_version=data.get("target_package_version")))
    return {
        "schema": GATE_SCHEMA,
        "passed": not blockers,
        "result_claim": "soak_exception_accepted" if not blockers else "soak_exception_blocked",
        "evidence_path": evidence_path,
        "blockers": blockers,
        "non_claims": [
            "this_gate_does_not_make_the_soak_clean",
            "this_gate_does_not_publish_releases",
            "this_gate_does_not_enable_auto_pull",
            "this_gate_does_not_execute_public_thaw",
        ],
    }


def evaluate(
    evidence: Path | None,
    *,
    soak_summary: Path | None = None,
    operator_event: Path | None = None,
    expected_package_version: str | None = None,
    expected_source_commit: str | None = None,
    expected_payload_sha256: str | None = None,
) -> dict[str, Any]:
    if evidence is None:
        return {
            "schema": GATE_SCHEMA,
            "passed": False,
            "result_claim": "soak_exception_blocked",
            "evidence_path": None,
            "blockers": ["missing_soak_exception_evidence"],
            "non_claims": [
                "this_gate_does_not_make_the_soak_clean",
                "this_gate_does_not_publish_releases",
                "this_gate_does_not_enable_auto_pull",
                "this_gate_does_not_execute_public_thaw",
            ],
        }
    data, blockers = read_json(evidence)
    summary_data = None
    event_data = None
    expected_summary_sha = None
    expected_event_sha = None
    if soak_summary is not None:
        if not soak_summary.is_file():
            blockers.append("soak_exception_soak_summary_not_file")
        else:
            summary_data, summary_errors = read_json(soak_summary)
            blockers.extend(f"soak_exception_summary:{item}" for item in summary_errors)
            expected_summary_sha = sha256_file(soak_summary)
    if operator_event is not None:
        if not operator_event.is_file():
            blockers.append("soak_exception_operator_event_not_file")
        else:
            event_data, event_errors = read_json(operator_event)
            blockers.extend(f"soak_exception_operator_event:{item}" for item in event_errors)
            expected_event_sha = sha256_file(operator_event)
    result = validate_data(
        data,
        evidence_path=str(evidence),
        soak_summary=summary_data,
        operator_event=event_data,
        expected_soak_summary_sha256=expected_summary_sha,
        expected_operator_event_sha256=expected_event_sha,
        expected_package_version=expected_package_version,
        expected_source_commit=expected_source_commit,
        expected_payload_sha256=expected_payload_sha256,
    )
    result["blockers"] = blockers + result["blockers"]
    result["passed"] = not result["blockers"]
    result["result_claim"] = "soak_exception_accepted" if result["passed"] else "soak_exception_blocked"
    return result


def valid_soak_summary() -> dict[str, Any]:
    return {
        "schema": SOAK_SCHEMA,
        "passed": False,
        "collection_policy": {"cycles": 24, "cycle_duration_sec": 3600},
        "failure_reasons": ["cycle_failed", "hwdec_expected_ratio_below_min"],
        "counters": {
            "max_panfrost_faults_delta": 0,
            "max_mmc_timeout_reset_delta": 0,
            "max_ext4_errors_delta": 0,
            "max_mpv_restart": 0,
            "max_nrestarts_delta": 0,
            "max_media_load_failed": 0,
        },
    }


def valid_operator_event(version: str) -> dict[str, Any]:
    return {
        "schema": OPERATOR_EVENT_SCHEMA,
        "component": COMPONENT,
        "version": version,
        "classification": "negative_for_clean_h2_soak_positive_for_runtime_resilience",
        "hdmi_disconnect_inferred_window_local": {
            "start": "2026-07-03T20:19:58-03:00",
            "end": "2026-07-03T20:20:00-03:00",
        },
        "hdmi_reconnect_kernel_event_local": "2026-07-04T16:29:54-03:00",
        "expected_gate_result": {"clean_h2_soak": False},
        "non_claims": [
            "not_clean_constant_hdmi_soak",
            "not_h2_green",
            "not_stable_promotion",
            "not_public_thaw",
            "not_production_authorization",
        ],
    }


def valid_exception(*, summary_sha: str = "a" * 64, event_sha: str = "b" * 64) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "component": COMPONENT,
        "exception_reason": EXCEPTION_REASON,
        "accepted": True,
        "explicit_business_decision": True,
        "clean_soak_passed": False,
        "failed_soak_accepted": True,
        "operator": "operator-prod-01",
        "rollback_owner": "rollback-owner-01",
        "risk_owner": "product-owner-01",
        "target_package_version": "c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1",
        "target_source_commit": "9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522",
        "target_payload_sha256": "d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0",
        "soak_summary_sha256": summary_sha,
        "operator_event_sha256": event_sha,
        "auto_pull_enabled": False,
        "public_thaw_executed": False,
        "production_rollout_started": False,
        "non_claims": list(REQUIRED_NON_CLAIMS),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class SoakExceptionGateSelfTest(unittest.TestCase):
    def test_missing_evidence_fails_closed(self) -> None:
        result = evaluate(None)
        self.assertFalse(result["passed"])
        self.assertIn("missing_soak_exception_evidence", result["blockers"])

    def test_complete_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "soak-summary.json"
            event = root / "operator-event.json"
            write_json(summary, valid_soak_summary())
            version = "c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1"
            write_json(event, valid_operator_event(version))
            evidence = root / "exception.json"
            write_json(evidence, valid_exception(summary_sha=sha256_file(summary), event_sha=sha256_file(event)))
            result = evaluate(
                evidence,
                soak_summary=summary,
                operator_event=event,
                expected_package_version=version,
                expected_source_commit="9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522",
                expected_payload_sha256="d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0",
            )
        self.assertTrue(result["passed"], result)

    def test_clean_soak_claim_fails(self) -> None:
        data = valid_exception()
        data["clean_soak_passed"] = True
        result = validate_data(data, soak_summary=valid_soak_summary(), operator_event=valid_operator_event(data["target_package_version"]))
        self.assertFalse(result["passed"])
        self.assertIn("soak_exception_clean_soak_claim", result["blockers"])

    def test_failed_summary_must_have_only_allowed_failure_reasons(self) -> None:
        summary = valid_soak_summary()
        summary["failure_reasons"] = ["cycle_failed", "mpv_restart_detected"]
        result = validate_data(valid_exception(), soak_summary=summary, operator_event=valid_operator_event(valid_exception()["target_package_version"]))
        self.assertFalse(result["passed"])
        self.assertIn("soak_exception_summary_unexpected_failure_reason:mpv_restart_detected", result["blockers"])

    def test_hash_mismatch_fails(self) -> None:
        result = validate_data(
            valid_exception(summary_sha="0" * 64),
            expected_soak_summary_sha256="1" * 64,
        )
        self.assertFalse(result["passed"])
        self.assertIn("soak_exception_soak_summary_sha256_mismatch", result["blockers"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--soak-summary", type=Path)
    parser.add_argument("--operator-event", type=Path)
    parser.add_argument("--expected-package-version")
    parser.add_argument("--expected-source-commit")
    parser.add_argument("--expected-payload-sha256")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(SoakExceptionGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = evaluate(
        args.evidence,
        soak_summary=args.soak_summary,
        operator_event=args.operator_event,
        expected_package_version=args.expected_package_version,
        expected_source_commit=args.expected_source_commit,
        expected_payload_sha256=args.expected_payload_sha256,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} blockers={len(result['blockers'])}")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
