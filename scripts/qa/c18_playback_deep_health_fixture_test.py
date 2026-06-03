#!/usr/bin/env python3
"""Fixture tests for the C18 playback deep-health summary."""

from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "board"))

import c18_playback_health_summary as health
import c18_playback_health_collect as collector


FIXTURE = REPO_ROOT / "scripts" / "board" / "testdata" / "c18_playback_health" / "pass"


class Fixture:
    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="c18-playback-health-fixture-")
        self.root = Path(self.tmp.name)
        shutil.copytree(FIXTURE, self.root / "case")
        self.case = self.root / "case"

    def close(self) -> None:
        self.tmp.cleanup()

    def path(self, name: str) -> Path:
        return self.case / name

    def read_json(self, name: str) -> dict:
        return json.loads(self.path(name).read_text(encoding="utf-8"))

    def write_json(self, name: str, data: dict) -> None:
        self.path(name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def mutate_json(self, name: str, **updates: object) -> None:
        data = self.read_json(name)
        data.update(updates)
        self.write_json(name, data)

    def rows(self) -> list[dict[str, str]]:
        with self.path("playback-samples.tsv").open("r", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh, delimiter="\t"))

    def write_rows(self, rows: list[dict[str, str]]) -> None:
        with self.path("playback-samples.tsv").open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, delimiter="\t", fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def result(self) -> dict:
        return health.evaluate(
            samples_path=self.path("playback-samples.tsv"),
            systemd_path=self.path("systemd.json"),
            process_path=self.path("process.json"),
            kernel_path=self.path("kernel.json"),
            player_counters_path=self.path("player-counters.json"),
        )


class C18PlaybackDeepHealthFixtureTest(unittest.TestCase):
    def with_case(self) -> Fixture:
        fixture = Fixture()
        self.addCleanup(fixture.close)
        return fixture

    def assert_fails_with(self, fixture: Fixture, reason: str) -> dict:
        result = fixture.result()
        self.assertFalse(result["passed"])
        self.assertIn(reason, result["failure_reasons"])
        return result

    def test_pass_fixture(self) -> None:
        result = self.with_case().result()
        self.assertTrue(result["passed"])
        self.assertEqual(result["failure_reasons"], [])
        self.assertEqual(result["counters"]["unique_aliases"], 2)

    def test_rejects_bad_hwdec(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row["hwdec_current"] = "no"
        fixture.write_rows(rows)
        self.assert_fails_with(fixture, "hwdec_no_unexpected")

    def test_rejects_stock_mpv_path(self) -> None:
        fixture = self.with_case()
        fixture.mutate_json("process.json", mpv_path="/usr/bin/mpv")
        self.assert_fails_with(fixture, "mpv_path_c18_stack")

    def test_rejects_ipc_timeout_after_success(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        rows[1]["ipc_result"] = "timeout"
        fixture.write_rows(rows)
        self.assert_fails_with(fixture, "ipc_stable_after_success")

    def test_rejects_wrong_mpv_count(self) -> None:
        fixture = self.with_case()
        fixture.mutate_json("process.json", mpv_count=2)
        self.assert_fails_with(fixture, "single_mpv")

    def test_rejects_media_load_failed_and_mpv_restart(self) -> None:
        fixture = self.with_case()
        fixture.mutate_json("player-counters.json", media_load_failed=1, mpv_restart=1)
        result = fixture.result()
        self.assertFalse(result["passed"])
        self.assertIn("media_load_failed_zero", result["failure_reasons"])
        self.assertIn("mpv_restart_zero", result["failure_reasons"])

    def test_rejects_kernel_fault_counters(self) -> None:
        fixture = self.with_case()
        fixture.mutate_json("kernel.json", panfrost_faults=1, mmc_timeout_reset=1, ext4_errors=1)
        result = fixture.result()
        self.assertFalse(result["passed"])
        self.assertIn("panfrost_faults_zero", result["failure_reasons"])
        self.assertIn("mmc_timeout_reset_zero", result["failure_reasons"])
        self.assertIn("ext4_errors_zero", result["failure_reasons"])

    def test_rejects_missing_ext4_counter(self) -> None:
        fixture = self.with_case()
        kernel = fixture.read_json("kernel.json")
        kernel.pop("ext4_errors", None)
        fixture.write_json("kernel.json", kernel)
        self.assert_fails_with(fixture, "ext4_errors_present")

    def test_non_destructive_collector_static_contract(self) -> None:
        source = (REPO_ROOT / "scripts" / "board" / "c18_playback_health_collect.py").read_text(encoding="utf-8")
        self.assertNotIn("systemctl stop", source)
        self.assertNotIn("systemctl restart", source)
        self.assertNotIn("systemctl start", source)
        self.assertNotIn("truncate", source)
        self.assertIn("playback-deep-health-public.json", source)
        self.assertIn("health.evaluate", source)

    def test_collector_aliases_do_not_echo_sensitive_paths_or_urls(self) -> None:
        url = "https://media.example.invalid/private/file.mp4?api_key=SECRET"
        path = "/data/media/kiosky-player/private-file.mp4"
        self.assertNotIn("https://", collector.safe_path_alias(url))
        self.assertNotIn("api_key", collector.safe_path_alias(url))
        self.assertNotIn("private-file", collector.safe_path_alias(path))
        self.assertTrue(collector.media_alias(path, url).startswith("media-"))

    def test_rejects_status_failure_and_missing_transition(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row["current_alias"] = "media-a"
        rows[1]["status_playback_state"] = "error"
        fixture.write_rows(rows)
        result = fixture.result()
        self.assertFalse(result["passed"])
        self.assertIn("status_no_failures", result["failure_reasons"])
        self.assertIn("transitions_observed_when_required", result["failure_reasons"])

    def test_output_does_not_echo_redaction_poison_values(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        poison = "https://media.example.invalid/private?api_key=SECRET SSID=Corp 192.168.1.10 AA:BB:CC:DD:EE:FF"
        rows[0]["current_alias"] = poison
        rows[0]["status_snapshot_json"] = json.dumps(
            {
                "present": True,
                "playlist_size": 2,
                "consecutive_failures": 0,
                "blocked_media_count": 0,
                "last_poll_error": "null",
                "last_render_error": "null",
                "black_screen_risk_reason": "null",
                "url": poison,
            },
            separators=(",", ":"),
        )
        fixture.write_rows(rows)
        payload = json.dumps(fixture.result(), sort_keys=True)
        for forbidden in ("https://", "api_key", "SECRET", "SSID", "192.168.", "AA:BB"):
            self.assertNotIn(forbidden, payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
