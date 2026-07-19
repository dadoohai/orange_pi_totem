#!/usr/bin/env python3
"""Validate C18 production-image totem-core auto-pull timer evidence.

This gate is offline-only. It validates evidence collected from a board booted
from the production image. It does not SSH, publish releases, mutate a board,
or authorize player-runtime thaw.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.totem_core.production_timer_collect.v1"
GATE_SCHEMA = "dadooh.c18.totem_core.production_timer_evidence_gate.v1"
DEFAULT_EXPECTED_IMAGE_TAG = "c18-hwdecode-prod-1"
DEFAULT_EXPECTED_IMAGE_VERSION = "c18.image-prod.1"
DEFAULT_EXPECTED_RELEASE_TAG = "totem-core-c18.ota-core-prod-20260705T184013Z-ccaf5a1"
DEFAULT_EXPECTED_VERSION = "c18.ota-core-prod-20260705T184013Z-ccaf5a1"
DEFAULT_EXPECTED_ROLLBACK_VERSION = "c17.6-environment-input-20260514T211247Z"
DEFAULT_EXPECTED_PAYLOAD_SHA256 = "613d9d6d1099636d7ca956c72e3927d502f1281068f8b0830b2d5f3ba2af0355"
DEFAULT_EXPECTED_SOURCE_COMMIT = "ccaf5a11775d122dd08512c9f5cf1e3027e5a29b"
REQUIRED_NON_CLAIMS = (
    "does_not_thaw_player_runtime",
    "does_not_update_media_system",
    "does_not_publish_release",
)
TIMER_EVENT_MAX_SKEW_SECONDS = 120
JOURNAL_UTC_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\b")
TIMER_UTC_RE = re.compile(r"^(?:[A-Za-z]{3}\s+)?(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+UTC$")


def load_json(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"summary_json_error:{type(exc).__name__}"]
    if not isinstance(data, dict):
        return {}, ["summary_not_object"]
    return data, []


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def str_field(value: Any) -> str:
    return value if isinstance(value, str) else ""


def bool_string_false_or_absent(value: Any) -> bool:
    return value in (None, "", False, "false", "False", "0", 0)


def truthy_marker(value: Any) -> bool:
    return value in (True, "true", "True", "1", 1)


def parse_timer_utc(value: str) -> dt.datetime | None:
    match = TIMER_UTC_RE.fullmatch(value.strip())
    if match is None:
        return None
    try:
        return dt.datetime.fromisoformat(f"{match.group(1)}T{match.group(2)}+00:00")
    except ValueError:
        return None


def correlated_journal_event(
    lines: list[str],
    *,
    trigger: dt.datetime,
    required_fragments: tuple[str, ...],
) -> bool:
    for line in lines:
        if not all(fragment in line for fragment in required_fragments):
            continue
        match = JOURNAL_UTC_RE.search(line)
        if match is None:
            continue
        try:
            observed = dt.datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
        except ValueError:
            continue
        elapsed = (observed - trigger).total_seconds()
        if 0 <= elapsed <= TIMER_EVENT_MAX_SKEW_SECONDS:
            return True
    return False


def validate_summary(
    data: dict[str, Any],
    *,
    expected_image_tag: str,
    expected_image_version: str,
    expected_release_tag: str,
    expected_version: str,
    expected_payload_sha256: str,
    expected_source_commit: str,
    max_player_restarts: int,
) -> list[str]:
    blockers: list[str] = []
    if data.get("schema") != SCHEMA:
        blockers.append("summary_schema_mismatch")

    non_claims = set(str(item) for item in as_list(data.get("non_claims")))
    for claim in REQUIRED_NON_CLAIMS:
        if claim not in non_claims:
            blockers.append(f"missing_non_claim:{claim}")

    marker = as_dict(data.get("image_marker"))
    marker_fields = as_dict(marker.get("fields"))
    if marker.get("exists") is not True:
        blockers.append("production_image_marker_missing")
    if marker_fields.get("image_tag") != expected_image_tag:
        blockers.append("production_image_tag_mismatch")
    if marker_fields.get("image_version") != expected_image_version:
        blockers.append("production_image_version_mismatch")
    if not truthy_marker(marker_fields.get("final_image")):
        blockers.append("production_marker_final_image_not_true")
    if marker_fields.get("artifact_private") not in ("false", False):
        blockers.append("production_marker_artifact_private_not_false")
    if not bool_string_false_or_absent(marker_fields.get("not_for_production")):
        blockers.append("production_marker_not_for_production_true")
    if not bool_string_false_or_absent(marker_fields.get("not_for_distribution")):
        blockers.append("production_marker_not_for_distribution_true")

    policy = as_dict(data.get("policy"))
    if policy.get("device_channel") != "stable":
        blockers.append("policy_channel_not_stable")
    if policy.get("device_track") != "c18-hwdecode":
        blockers.append("policy_track_not_c18_hwdecode")
    if policy.get("allow_prerelease") is not False:
        blockers.append("policy_allow_prerelease_not_false")
    if policy.get("allow_downgrade") is not False:
        blockers.append("policy_allow_downgrade_not_false")
    if policy.get("allowed_components") != ["totem-core"]:
        blockers.append("policy_allowed_components_not_totem_core_only")

    timer = as_dict(data.get("timer"))
    if timer.get("enabled_raw") != "enabled":
        blockers.append("timer_not_enabled")
    if timer.get("active_raw") != "active":
        blockers.append("timer_not_active")
    timer_show = as_dict(timer.get("show"))
    last_trigger = str_field(timer_show.get("LastTriggerUSec"))
    if not last_trigger or last_trigger in {"n/a", "0", "0us"}:
        blockers.append("timer_last_trigger_missing")

    service = as_dict(data.get("service"))
    service_show = as_dict(service.get("show"))
    result = str_field(service_show.get("Result"))
    exec_status = str_field(service_show.get("ExecMainStatus"))
    if result and result != "success":
        blockers.append("update_agent_service_result_not_success")
    if exec_status and exec_status != "0":
        blockers.append("update_agent_service_exec_status_not_zero")
    journal = "\n".join(str(item) for item in as_list(service.get("journal_tail")))
    if expected_release_tag not in journal:
        blockers.append("service_journal_missing_expected_release_tag")
    if "apply_success" not in journal and "already_current" not in journal:
        blockers.append("service_journal_missing_apply_success_or_noop")
    journal_lines = [str(item) for item in as_list(service.get("journal_tail"))]
    trigger_utc = parse_timer_utc(last_trigger)
    if trigger_utc is None:
        blockers.append("timer_last_trigger_unparseable")
    else:
        if not correlated_journal_event(
            journal_lines,
            trigger=trigger_utc,
            required_fragments=(expected_release_tag,),
        ):
            blockers.append("timer_expected_release_event_not_correlated")
        success_correlated = correlated_journal_event(
            journal_lines,
            trigger=trigger_utc,
            required_fragments=("apply_success", expected_version),
        ) or correlated_journal_event(
            journal_lines,
            trigger=trigger_utc,
            required_fragments=("already_current", expected_version),
        )
        if not success_correlated:
            blockers.append("timer_success_event_not_correlated")

    status = as_dict(data.get("totem_core_status"))
    state = as_dict(status.get("state"))
    current = as_dict(state.get("current"))
    if status.get("service_active") is not True:
        blockers.append("totem_core_status_service_not_active")
    if current.get("version") != expected_version:
        blockers.append("totem_core_current_version_mismatch")
    if current.get("payload_sha256") != expected_payload_sha256:
        blockers.append("totem_core_current_payload_sha256_mismatch")
    if current.get("channel") != "stable":
        blockers.append("totem_core_current_channel_not_stable")
    if expected_release_tag not in str_field(current.get("source")):
        blockers.append("totem_core_current_source_missing_release_tag")
    if current.get("source_commit") != expected_source_commit:
        blockers.append("totem_core_current_source_commit_mismatch")

    self_test = as_dict(data.get("totem_core_self_test"))
    if self_test.get("self_test") is not True:
        blockers.append("totem_core_self_test_not_true")
    checks = as_dict(self_test.get("checks"))
    for name, passed in checks.items():
        if passed is not True:
            blockers.append(f"totem_core_self_test_check_failed:{name}")

    player = as_dict(data.get("player_service"))
    if player.get("active_raw") != "active":
        blockers.append("player_service_not_active")
    try:
        restarts = int(player.get("nrestarts"))
    except Exception:
        restarts = max_player_restarts + 1
    if restarts > max_player_restarts:
        blockers.append("player_service_restarted")

    freeze = as_dict(data.get("player_runtime_freeze_probe"))
    if freeze.get("ran") is not True:
        blockers.append("player_runtime_freeze_probe_missing")
    elif freeze.get("returncode") != 44:
        blockers.append("player_runtime_freeze_probe_rc_not_44")

    return blockers


def validate_rollback_summary(
    data: dict[str, Any],
    *,
    expected_image_tag: str,
    expected_image_version: str,
    expected_release_tag: str,
    expected_version: str,
    expected_rollback_version: str,
    max_player_restarts: int,
) -> list[str]:
    blockers: list[str] = []
    if data.get("schema") != SCHEMA:
        blockers.append("rollback_summary_schema_mismatch")

    marker = as_dict(data.get("image_marker"))
    marker_fields = as_dict(marker.get("fields"))
    if marker.get("exists") is not True:
        blockers.append("rollback_production_image_marker_missing")
    if marker_fields.get("image_tag") != expected_image_tag:
        blockers.append("rollback_production_image_tag_mismatch")
    if marker_fields.get("image_version") != expected_image_version:
        blockers.append("rollback_production_image_version_mismatch")
    if not truthy_marker(marker_fields.get("final_image")):
        blockers.append("rollback_production_marker_final_image_not_true")

    policy = as_dict(data.get("policy"))
    if policy.get("device_channel") != "stable":
        blockers.append("rollback_policy_channel_not_stable")
    if policy.get("allowed_components") != ["totem-core"]:
        blockers.append("rollback_policy_allowed_components_not_totem_core_only")

    status = as_dict(data.get("totem_core_status"))
    state = as_dict(status.get("state"))
    current = as_dict(state.get("current"))
    previous = as_dict(state.get("previous"))
    last_operation = as_dict(state.get("last_operation"))
    if status.get("service_active") is not True:
        blockers.append("rollback_totem_core_status_service_not_active")
    if current.get("version") != expected_rollback_version:
        blockers.append("rollback_current_version_mismatch")
    if previous.get("version") != expected_version:
        blockers.append("rollback_previous_version_not_stable_release")
    if expected_release_tag not in str_field(previous.get("source")):
        blockers.append("rollback_previous_source_missing_release_tag")
    if last_operation.get("type") != "rollback":
        blockers.append("rollback_last_operation_type_not_rollback")
    if last_operation.get("status") != "success":
        blockers.append("rollback_last_operation_status_not_success")
    if last_operation.get("rolled_back_to") != expected_rollback_version:
        blockers.append("rollback_last_operation_target_mismatch")

    self_test = as_dict(data.get("totem_core_self_test"))
    if self_test.get("self_test") is not True:
        blockers.append("rollback_totem_core_self_test_not_true")

    player = as_dict(data.get("player_service"))
    if player.get("active_raw") != "active":
        blockers.append("rollback_player_service_not_active")
    try:
        restarts = int(player.get("nrestarts"))
    except Exception:
        restarts = max_player_restarts + 1
    if restarts > max_player_restarts:
        blockers.append("rollback_player_service_restarted")

    freeze = as_dict(data.get("player_runtime_freeze_probe"))
    if freeze.get("ran") is not True:
        blockers.append("rollback_player_runtime_freeze_probe_missing")
    elif freeze.get("returncode") != 44:
        blockers.append("rollback_player_runtime_freeze_probe_rc_not_44")

    return blockers


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    data, blockers = load_json(args.summary)
    if not blockers:
        blockers.extend(validate_summary(
            data,
            expected_image_tag=args.expected_image_tag,
            expected_image_version=args.expected_image_version,
            expected_release_tag=args.expected_release_tag,
            expected_version=args.expected_version,
            expected_payload_sha256=args.expected_payload_sha256,
            expected_source_commit=args.expected_source_commit,
            max_player_restarts=args.max_player_restarts,
        ))
    rollback_summary = getattr(args, "rollback_summary", None)
    if rollback_summary is not None:
        rollback_data, rollback_errors = load_json(rollback_summary)
        blockers.extend(rollback_errors)
        if not rollback_errors:
            blockers.extend(validate_rollback_summary(
                rollback_data,
                expected_image_tag=args.expected_image_tag,
                expected_image_version=args.expected_image_version,
                expected_release_tag=args.expected_release_tag,
                expected_version=args.expected_version,
                expected_rollback_version=args.expected_rollback_version,
                max_player_restarts=args.max_player_restarts,
            ))
    return {
        "schema": GATE_SCHEMA,
        "passed": not blockers,
        "result_claim": "totem_core_production_timer_ready" if not blockers else "totem_core_production_timer_blocked",
        "summary": str(args.summary),
        "rollback_summary": str(rollback_summary) if rollback_summary is not None else None,
        "expected_image_tag": args.expected_image_tag,
        "expected_release_tag": args.expected_release_tag,
        "expected_version": args.expected_version,
        "expected_rollback_version": args.expected_rollback_version,
        "blockers": blockers,
        "non_claims": list(REQUIRED_NON_CLAIMS),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ProductionTimerGateSelfTest(unittest.TestCase):
    def fixture(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "non_claims": list(REQUIRED_NON_CLAIMS),
            "image_marker": {
                "exists": True,
                "fields": {
                    "image_tag": DEFAULT_EXPECTED_IMAGE_TAG,
                    "image_version": DEFAULT_EXPECTED_IMAGE_VERSION,
                    "artifact_private": "false",
                    "final_image": "true",
                },
            },
            "policy": {
                "device_channel": "stable",
                "device_track": "c18-hwdecode",
                "allowed_components": ["totem-core"],
                "allow_prerelease": False,
                "allow_downgrade": False,
            },
            "timer": {
                "enabled_raw": "enabled",
                "active_raw": "active",
                "show": {"LastTriggerUSec": "Sun 2026-07-05 18:58:00 UTC"},
            },
            "service": {
                "show": {"Result": "success", "ExecMainStatus": "0"},
                "journal_tail": [
                    f"2026-07-05T18:58:01Z INFO apply_start source=github:dadoohai/orange_pi_totem:{DEFAULT_EXPECTED_RELEASE_TAG}",
                    f"2026-07-05T18:58:20Z INFO apply_success version={DEFAULT_EXPECTED_VERSION}",
                ],
            },
            "totem_core_status": {
                "service_active": True,
                "state": {
                    "current": {
                        "version": DEFAULT_EXPECTED_VERSION,
                        "channel": "stable",
                        "payload_sha256": DEFAULT_EXPECTED_PAYLOAD_SHA256,
                        "source": f"github:dadoohai/orange_pi_totem:{DEFAULT_EXPECTED_RELEASE_TAG}",
                        "source_commit": DEFAULT_EXPECTED_SOURCE_COMMIT,
                    }
                },
            },
            "totem_core_self_test": {"self_test": True, "checks": {"component_base_exists": True}},
            "player_service": {"active_raw": "active", "nrestarts": "0"},
            "player_runtime_freeze_probe": {"ran": True, "returncode": 44},
        }

    def rollback_fixture(self) -> dict[str, Any]:
        payload = self.fixture()
        state = payload["totem_core_status"]["state"]
        state["previous"] = state["current"]
        state["current"] = {
            "version": DEFAULT_EXPECTED_ROLLBACK_VERSION,
            "source": "image_embed",
        }
        state["last_operation"] = {
            "type": "rollback",
            "status": "success",
            "rolled_back_to": DEFAULT_EXPECTED_ROLLBACK_VERSION,
        }
        payload["service"]["journal_tail"] = []
        return payload

    def run_fixture(self, payload: dict[str, Any], rollback_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.json"
            write_json(path, payload)
            rollback_path = None
            if rollback_payload is not None:
                rollback_path = Path(tmp) / "rollback-summary.json"
                write_json(rollback_path, rollback_payload)
            args = argparse.Namespace(
                summary=path,
                rollback_summary=rollback_path,
                expected_image_tag=DEFAULT_EXPECTED_IMAGE_TAG,
                expected_image_version=DEFAULT_EXPECTED_IMAGE_VERSION,
                expected_release_tag=DEFAULT_EXPECTED_RELEASE_TAG,
                expected_version=DEFAULT_EXPECTED_VERSION,
                expected_rollback_version=DEFAULT_EXPECTED_ROLLBACK_VERSION,
                expected_payload_sha256=DEFAULT_EXPECTED_PAYLOAD_SHA256,
                expected_source_commit=DEFAULT_EXPECTED_SOURCE_COMMIT,
                max_player_restarts=0,
            )
            return evaluate(args)

    def test_valid_fixture_passes(self) -> None:
        result = self.run_fixture(self.fixture())
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2))

    def test_valid_fixture_with_rollback_passes(self) -> None:
        result = self.run_fixture(self.fixture(), self.rollback_fixture())
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2))

    def test_lab_marker_denies(self) -> None:
        payload = self.fixture()
        payload["image_marker"]["fields"]["image_tag"] = "c18-hwdecode-lab-1x"
        payload["image_marker"]["fields"]["final_image"] = "false"
        result = self.run_fixture(payload)
        self.assertFalse(result["passed"])
        self.assertIn("production_image_tag_mismatch", result["blockers"])
        self.assertIn("production_marker_final_image_not_true", result["blockers"])

    def test_timer_disabled_denies(self) -> None:
        payload = self.fixture()
        payload["timer"]["enabled_raw"] = "disabled"
        payload["timer"]["active_raw"] = "inactive"
        payload["timer"]["show"]["LastTriggerUSec"] = "n/a"
        result = self.run_fixture(payload)
        self.assertFalse(result["passed"])
        self.assertIn("timer_not_enabled", result["blockers"])
        self.assertIn("timer_not_active", result["blockers"])
        self.assertIn("timer_last_trigger_missing", result["blockers"])

    def test_wrong_release_denies(self) -> None:
        payload = self.fixture()
        payload["totem_core_status"]["state"]["current"]["version"] = "old"
        payload["totem_core_status"]["state"]["current"]["payload_sha256"] = "0" * 64
        result = self.run_fixture(payload)
        self.assertFalse(result["passed"])
        self.assertIn("totem_core_current_version_mismatch", result["blockers"])
        self.assertIn("totem_core_current_payload_sha256_mismatch", result["blockers"])

    def test_manual_service_event_after_old_timer_denies(self) -> None:
        payload = self.fixture()
        payload["timer"]["show"]["LastTriggerUSec"] = "Sun 2026-07-05 17:55:23 UTC"
        payload["service"]["journal_tail"] = [
            f"2026-07-05T20:17:23Z INFO apply_start source=github:dadoohai/orange_pi_totem:{DEFAULT_EXPECTED_RELEASE_TAG}",
            f"2026-07-05T20:17:40Z INFO apply_success version={DEFAULT_EXPECTED_VERSION}",
        ]
        result = self.run_fixture(payload)
        self.assertFalse(result["passed"])
        self.assertIn("timer_expected_release_event_not_correlated", result["blockers"])
        self.assertIn("timer_success_event_not_correlated", result["blockers"])

    def test_journal_without_machine_timestamp_denies(self) -> None:
        payload = self.fixture()
        payload["service"]["journal_tail"] = [
            f"INFO apply_start source=github:dadoohai/orange_pi_totem:{DEFAULT_EXPECTED_RELEASE_TAG}",
            f"INFO apply_success version={DEFAULT_EXPECTED_VERSION}",
        ]
        result = self.run_fixture(payload)
        self.assertFalse(result["passed"])
        self.assertIn("timer_expected_release_event_not_correlated", result["blockers"])
        self.assertIn("timer_success_event_not_correlated", result["blockers"])

    def test_service_event_before_timer_trigger_denies(self) -> None:
        payload = self.fixture()
        payload["timer"]["show"]["LastTriggerUSec"] = "Sun 2026-07-05 18:59:00 UTC"
        payload["service"]["journal_tail"] = [
            f"2026-07-05T18:58:01Z INFO apply_start source=github:dadoohai/orange_pi_totem:{DEFAULT_EXPECTED_RELEASE_TAG}",
            f"2026-07-05T18:58:20Z INFO apply_success version={DEFAULT_EXPECTED_VERSION}",
        ]
        result = self.run_fixture(payload)
        self.assertFalse(result["passed"])
        self.assertIn("timer_expected_release_event_not_correlated", result["blockers"])
        self.assertIn("timer_success_event_not_correlated", result["blockers"])

    def test_missing_freeze_probe_denies(self) -> None:
        payload = self.fixture()
        payload["player_runtime_freeze_probe"] = {"ran": False}
        result = self.run_fixture(payload)
        self.assertFalse(result["passed"])
        self.assertIn("player_runtime_freeze_probe_missing", result["blockers"])

    def test_player_restart_denies(self) -> None:
        payload = self.fixture()
        payload["player_service"]["nrestarts"] = "1"
        result = self.run_fixture(payload)
        self.assertFalse(result["passed"])
        self.assertIn("player_service_restarted", result["blockers"])

    def test_rollback_wrong_target_denies(self) -> None:
        rollback = self.rollback_fixture()
        rollback["totem_core_status"]["state"]["current"]["version"] = "wrong"
        result = self.run_fixture(self.fixture(), rollback)
        self.assertFalse(result["passed"])
        self.assertIn("rollback_current_version_mismatch", result["blockers"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate C18 production totem-core timer evidence.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--rollback-summary", type=Path)
    parser.add_argument("--expected-image-tag", default=DEFAULT_EXPECTED_IMAGE_TAG)
    parser.add_argument("--expected-image-version", default=DEFAULT_EXPECTED_IMAGE_VERSION)
    parser.add_argument("--expected-release-tag", default=DEFAULT_EXPECTED_RELEASE_TAG)
    parser.add_argument("--expected-version", default=DEFAULT_EXPECTED_VERSION)
    parser.add_argument("--expected-rollback-version", default=DEFAULT_EXPECTED_ROLLBACK_VERSION)
    parser.add_argument("--expected-payload-sha256", default=DEFAULT_EXPECTED_PAYLOAD_SHA256)
    parser.add_argument("--expected-source-commit", default=DEFAULT_EXPECTED_SOURCE_COMMIT)
    parser.add_argument("--max-player-restarts", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProductionTimerGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if args.summary is None:
        raise SystemExit("missing --summary")
    result = evaluate(args)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} blockers={len(result['blockers'])}")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
