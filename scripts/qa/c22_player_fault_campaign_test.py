#!/usr/bin/env python3
"""C22 offline player fault-campaign tests."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = REPO_ROOT / "scripts" / "sim" / "run_player_fault_campaign.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("c22_player_fault_campaign", HARNESS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load harness: {HARNESS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = load_harness()


class C22PlayerFaultCampaignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = harness.run_campaign()

    def scenario(self, name: str) -> dict:
        for scenario in self.report["scenarios"]:
            if scenario["name"] == name:
                return scenario
        self.fail(f"missing scenario: {name}")

    def expectation(self, scenario_name: str, expectation_name: str) -> dict:
        scenario = self.scenario(scenario_name)
        for expectation in scenario["expectations"]:
            if expectation["name"] == expectation_name:
                return expectation
        self.fail(f"missing expectation: {scenario_name}:{expectation_name}")

    def assertExpectationPassed(self, scenario_name: str, expectation_name: str) -> None:
        item = self.expectation(scenario_name, expectation_name)
        self.assertTrue(item["passed"], item.get("details"))

    def test_cli_emits_sanitized_json(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(HARNESS_PATH), "--compact"],
            cwd=str(REPO_ROOT),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema"], harness.SCHEMA)
        serialized = json.dumps(payload, sort_keys=True)
        self.assertNotIn("https://", serialized)
        self.assertNotIn("http://", serialized)
        self.assertNotIn("mock://", serialized)
        self.assertNotIn("offline-test-key", serialized)
        self.assertEqual(payload["offline"]["network"], "fake_requests_only")
        self.assertEqual(payload["offline"]["board"], "not_touched")
        self.assertEqual(payload["offline"]["mpv"], "not_started")

    def test_mixed_video_image_playlist_is_adopted(self) -> None:
        self.assertExpectationPassed("mixed_video_image_playlist", "adopted_two_items")
        self.assertExpectationPassed("mixed_video_image_playlist", "contains_video_and_image")
        self.assertExpectationPassed("mixed_video_image_playlist", "playlist_state_persisted")

    def test_content_length_truncated_download_is_rejected(self) -> None:
        self.assertExpectationPassed("download_truncated_with_content_length", "rejected_truncated_download")

    def test_no_content_length_truncated_download_is_rejected(self) -> None:
        self.assertExpectationPassed("download_truncated_without_content_length", "rejected_truncated_download")

    def test_http_200_invalid_body_is_rejected(self) -> None:
        self.assertExpectationPassed("http_200_invalid_body", "rejected_invalid_media_body")

    def test_corrupt_existing_sidecar_is_rebuilt_and_accepted(self) -> None:
        self.assertExpectationPassed("corrupt_existing_sidecar", "rebuilt_corrupt_sidecar")
        self.assertExpectationPassed("corrupt_existing_sidecar", "accepted_rebuilt_sidecar")

    def test_incomplete_playlist_preserves_lkg_and_marks_failed_adoption(self) -> None:
        self.assertExpectationPassed(
            "incomplete_playlist_preserves_last_known_good",
            "preserved_last_known_good",
        )
        self.assertExpectationPassed(
            "incomplete_playlist_preserves_last_known_good",
            "explicit_failed_adoption_state",
        )

    def test_empty_api_preserves_availability_and_marks_stale_empty(self) -> None:
        self.assertExpectationPassed("empty_api_preserves_availability", "preserved_available_content")
        self.assertExpectationPassed("empty_api_preserves_availability", "explicit_stale_empty_state")

    def test_legacy_partial_playlist_cannot_report_false_green(self) -> None:
        self.assertExpectationPassed("legacy_partial_playlist_stays_stale", "adopted_available_item")
        self.assertExpectationPassed("legacy_partial_playlist_stays_stale", "partial_adoption_not_false_green")

    def test_recovery_to_valid_playlist_is_adopted(self) -> None:
        self.assertExpectationPassed("recovery_to_valid_playlist", "adopted_recovery_playlist")
        self.assertExpectationPassed("recovery_to_valid_playlist", "recovery_contains_video_and_image")


if __name__ == "__main__":
    unittest.main(verbosity=2)
