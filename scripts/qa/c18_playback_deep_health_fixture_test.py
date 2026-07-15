#!/usr/bin/env python3
"""Fixture tests for the C18 playback deep-health summary."""

from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "board"))

import c18_playback_health_summary as health
import c18_playback_health_collect as collector
import c18_player_runtime_candidate_health as candidate_health


FIXTURE = REPO_ROOT / "scripts" / "board" / "testdata" / "c18_playback_health" / "pass"
VALID_VIDEO_PARAMS = json.dumps({"dw": 1280, "dh": 720}, separators=(",", ":"))


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
        watchdog_path = self.path("watchdog.json")
        return health.evaluate(
            samples_path=self.path("playback-samples.tsv"),
            systemd_path=self.path("systemd.json"),
            process_path=self.path("process.json"),
            kernel_path=self.path("kernel.json"),
            player_counters_path=self.path("player-counters.json"),
            watchdog_path=watchdog_path if watchdog_path.exists() else None,
        )

    def result_with_panfrost_policy(self, policy: str) -> dict:
        return health.evaluate(
            samples_path=self.path("playback-samples.tsv"),
            systemd_path=self.path("systemd.json"),
            process_path=self.path("process.json"),
            kernel_path=self.path("kernel.json"),
            player_counters_path=self.path("player-counters.json"),
            panfrost_fault_policy=policy,
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

    def typed_row(
        self,
        template: dict[str, str],
        *,
        seq: int,
        kind: str,
        alias: str,
        frame: str,
        playlist_size: int = 1,
        status_aligned: bool = True,
    ) -> dict[str, str]:
        row = template.copy()
        row["seq"] = str(seq)
        row["rel_sec"] = str(seq - 1)
        row["current_path_kind"] = kind
        row["current_alias"] = f"<media-path:{alias}>"
        row["path_alias"] = f"<media-path:{alias}>"
        row["estimated_frame_number"] = frame
        row["video_params_json"] = VALID_VIDEO_PARAMS
        row["duration"] = "0.04" if kind == "public_surface" else "30.0"
        if status_aligned:
            row["status_current_alias"] = f"media-{alias}"
            row["status_path_alias"] = f"<media-path:{alias}>"
            row["status_current_index"] = "0"
        else:
            row["status_current_alias"] = ""
            row["status_path_alias"] = ""
            row["status_current_index"] = ""
        snapshot = json.loads(row["status_snapshot_json"])
        snapshot["playlist_size"] = playlist_size
        row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
        return row

    def write_ipc_error_rows(self, fixture: Fixture, indexes: list[int], reason: str) -> None:
        rows = fixture.rows()
        for row in rows:
            row.setdefault("ipc_error", "")
        while len(rows) < 8:
            row = rows[-1].copy()
            row["seq"] = str(len(rows) + 1)
            row["rel_sec"] = str(float(rows[-1]["rel_sec"]) + 1)
            row["time_pos"] = str(float(rows[-1].get("time_pos") or 0) + 1)
            row["estimated_frame_number"] = str(int(float(rows[-1].get("estimated_frame_number") or 0)) + 30)
            rows.append(row)
        for index in indexes:
            rows[index]["ipc_result"] = "error"
            rows[index]["ipc_error"] = reason
            rows[index]["path_alias"] = ""
            rows[index]["filename_alias"] = ""
            rows[index]["time_pos"] = ""
            rows[index]["estimated_frame_number"] = ""
            rows[index]["hwdec_current"] = ""
            rows[index]["vo_configured"] = ""
        fixture.write_rows(rows)

    def write_initial_ipc_rows(
        self,
        fixture: Fixture,
        errors: list[tuple[str, str]],
        *,
        interval_sec: float = 1.0,
    ) -> None:
        content_rows = fixture.rows()
        for row in content_rows:
            row.setdefault("ipc_error", "")
        startup_rows: list[dict[str, str]] = []
        template = content_rows[0]
        for offset, (result, error) in enumerate(errors):
            row = template.copy()
            row["seq"] = str(offset + 1)
            row["rel_sec"] = str(offset * interval_sec)
            row["ipc_result"] = result
            row["ipc_error"] = error
            row["current_alias"] = ""
            row["path_alias"] = ""
            row["filename_alias"] = ""
            row["time_pos"] = ""
            row["estimated_frame_number"] = ""
            row["hwdec_current"] = ""
            row["vo_configured"] = ""
            row["video_params_json"] = "{}"
            row["status_playback_state"] = "player_starting"
            row["status_current_alias"] = ""
            row["status_path_alias"] = ""
            row["status_current_index"] = ""
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["playback_state"] = "player_starting"
            snapshot["current_item"] = None
            snapshot["next_item"] = None
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
            startup_rows.append(row)
        for offset, row in enumerate(content_rows, start=len(startup_rows) + 1):
            row["seq"] = str(offset)
            row["rel_sec"] = str((offset - 1) * interval_sec)
        fixture.write_rows(startup_rows + content_rows)

    def write_long_run_ipc_error_rows(self, fixture: Fixture, indexes: list[int], reason: str) -> None:
        source_rows = fixture.rows()
        rows = []
        for index in range(555):
            row = source_rows[index % len(source_rows)].copy()
            row.setdefault("ipc_error", "")
            row["seq"] = str(index + 1)
            row["rel_sec"] = str(index)
            rows.append(row)
        for index in indexes:
            rows[index]["ipc_result"] = "error"
            rows[index]["ipc_error"] = reason
            rows[index]["path_alias"] = ""
            rows[index]["filename_alias"] = ""
            rows[index]["time_pos"] = ""
            rows[index]["estimated_frame_number"] = ""
            rows[index]["hwdec_current"] = ""
            rows[index]["vo_configured"] = ""
        fixture.write_rows(rows)

    def write_status_mpv_alignment_rows(
        self,
        fixture: Fixture,
        samples: list[tuple[str, str, str, str]],
    ) -> None:
        template = fixture.rows()[0]
        item_by_index: dict[int, tuple[str, str]] = {}
        for status_alias, status_path_alias, status_index, _mpv_path_alias in samples:
            item_by_index.setdefault(int(status_index), (status_alias, status_path_alias))
        item_by_path = {status_path_alias: (status_alias, status_path_alias) for status_alias, status_path_alias in item_by_index.values()}
        forward_next_by_index: dict[int, tuple[str, str]] = {}
        for _status_alias, status_path_alias, status_index, mpv_path_alias in samples:
            if mpv_path_alias and mpv_path_alias != status_path_alias:
                forward_next_by_index.setdefault(
                    int(status_index),
                    item_by_path.get(mpv_path_alias, ("", mpv_path_alias)),
                )
        ordered_indexes = sorted(item_by_index)
        next_by_index: dict[int, tuple[str, str]] = {}
        if ordered_indexes:
            for offset, status_index in enumerate(ordered_indexes):
                next_index = ordered_indexes[(offset + 1) % len(ordered_indexes)]
                next_by_index[status_index] = forward_next_by_index.get(status_index, item_by_index[next_index])
        rows = []
        for index, (status_alias, status_path_alias, status_index, mpv_path_alias) in enumerate(samples, start=1):
            status_index_int = int(status_index)
            row = template.copy()
            row["seq"] = str(index)
            row["rel_sec"] = str(index - 1)
            row["time_pos"] = f"{index - 1}.10"
            row["estimated_frame_number"] = str(index * 30)
            row["current_alias"] = mpv_path_alias
            row["path_alias"] = mpv_path_alias
            row["filename_alias"] = ""
            row["status_current_alias"] = status_alias
            row["status_path_alias"] = status_path_alias
            row["status_current_index"] = status_index
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["playlist_size"] = max(len(ordered_indexes), 1)
            snapshot["current_index"] = status_index_int
            snapshot["current_item"] = {
                "alias": status_alias,
                "path_alias": status_path_alias,
                "duration_ms": 10000,
                "offset_ms": 0,
                "started_at_present": True,
            }
            next_alias, next_path_alias = next_by_index.get(status_index_int, ("", ""))
            snapshot["next_item"] = {
                "alias": next_alias,
                "path_alias": next_path_alias,
                "duration_ms": 10000,
            }
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
            rows.append(row)
        fixture.write_rows(rows)

    def test_pass_fixture(self) -> None:
        result = self.with_case().result()
        self.assertTrue(result["passed"])
        self.assertEqual(result["failure_reasons"], [])
        self.assertEqual(result["counters"]["unique_aliases"], 2)
        self.assertEqual(result["counters"]["mpv_unique_aliases"], 2)
        self.assertEqual(result["counters"]["status_unique_aliases"], 2)
        self.assertGreater(result["counters"]["status_mpv_comparable_samples"], 0)
        self.assertEqual(result["counters"]["status_mpv_mismatch_samples"], 0)

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

    def test_accepts_bounded_initial_missing_socket_before_success(self) -> None:
        fixture = self.with_case()
        self.write_initial_ipc_rows(
            fixture,
            [("error", "missing_socket"), ("error", "missing_socket")],
        )

        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertTrue(result["checks"]["ipc_startup_bounded"])
        self.assertEqual(result["counters"]["ipc_startup_samples_before_first_success"], 2)

    def test_rejects_unbounded_initial_missing_socket_before_success(self) -> None:
        fixture = self.with_case()
        self.write_initial_ipc_rows(
            fixture,
            [("error", "missing_socket")] * 7,
        )

        result = self.assert_fails_with(fixture, "ipc_startup_bounded")
        self.assertEqual(result["counters"]["ipc_startup_samples_before_first_success"], 7)

    def test_rejects_initial_timeout_or_non_missing_socket_error(self) -> None:
        for initial in (("timeout", "socket_timeout"), ("error", "ConnectionRefusedError")):
            with self.subTest(initial=initial):
                fixture = self.with_case()
                self.write_initial_ipc_rows(fixture, [initial])
                self.assert_fails_with(fixture, "ipc_startup_bounded")

    def test_rejects_slow_initial_missing_socket_before_success(self) -> None:
        fixture = self.with_case()
        self.write_initial_ipc_rows(
            fixture,
            [("error", "missing_socket"), ("error", "missing_socket")],
            interval_sec=4.0,
        )

        result = self.assert_fails_with(fixture, "ipc_startup_bounded")
        self.assertGreater(result["counters"]["ipc_startup_span_seconds"], 6.0)

    def test_rejects_invalid_initial_ipc_timing(self) -> None:
        for timing in ("non_finite", "negative", "descending"):
            with self.subTest(timing=timing):
                fixture = self.with_case()
                self.write_initial_ipc_rows(
                    fixture,
                    [("error", "missing_socket"), ("error", "missing_socket")],
                )
                rows = fixture.rows()
                if timing == "non_finite":
                    rows[0]["rel_sec"] = "nan"
                elif timing == "negative":
                    rows[0]["rel_sec"] = "-2"
                    rows[1]["rel_sec"] = "-1"
                    rows[2]["rel_sec"] = "0"
                else:
                    rows[0]["rel_sec"] = "1"
                    rows[1]["rel_sec"] = "0"
                    rows[2]["rel_sec"] = "2"
                fixture.write_rows(rows)
                self.assert_fails_with(fixture, "ipc_startup_bounded")

    def test_accepts_single_transient_missing_socket_after_success(self) -> None:
        fixture = self.with_case()
        self.write_ipc_error_rows(fixture, [1], "missing_socket")
        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertEqual(result["counters"]["ipc_error_after_first_success"], 1)
        self.assertEqual(result["counters"]["ipc_missing_socket_after_first_success"], 1)
        self.assertEqual(result["counters"]["ipc_other_error_after_first_success"], 0)
        self.assertNotIn("ipc_stable_after_success", result["failure_reasons"])

    def test_accepts_bounded_transient_missing_socket_burst_after_success(self) -> None:
        fixture = self.with_case()
        self.write_ipc_error_rows(fixture, [1, 2], "missing_socket")
        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertEqual(result["counters"]["ipc_missing_socket_after_first_success"], 2)
        self.assertEqual(result["counters"]["ipc_missing_socket_max_consecutive_after_first_success"], 2)
        self.assertNotIn("ipc_stable_after_success", result["failure_reasons"])

    def test_accepts_sparse_long_run_transient_missing_socket_after_success(self) -> None:
        fixture = self.with_case()
        self.write_long_run_ipc_error_rows(fixture, [83, 407, 408], "missing_socket")
        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertEqual(result["counters"]["ipc_missing_socket_after_first_success"], 3)
        self.assertEqual(result["counters"]["ipc_missing_socket_allowed_after_first_success"], 3)
        self.assertEqual(result["counters"]["ipc_missing_socket_max_consecutive_after_first_success"], 2)
        self.assertNotIn("ipc_stable_after_success", result["failure_reasons"])

    def test_rejects_excessive_sparse_long_run_missing_socket_after_success(self) -> None:
        fixture = self.with_case()
        self.write_long_run_ipc_error_rows(fixture, [83, 200, 350, 500], "missing_socket")
        result = self.assert_fails_with(fixture, "ipc_stable_after_success")
        self.assertEqual(result["counters"]["ipc_missing_socket_after_first_success"], 4)
        self.assertEqual(result["counters"]["ipc_missing_socket_allowed_after_first_success"], 3)

    def test_rejects_excessive_missing_socket_after_success(self) -> None:
        fixture = self.with_case()
        self.write_ipc_error_rows(fixture, [1, 2, 3], "missing_socket")
        result = self.assert_fails_with(fixture, "ipc_stable_after_success")
        self.assertEqual(result["counters"]["ipc_missing_socket_after_first_success"], 3)

    def test_rejects_non_missing_socket_ipc_error_after_success(self) -> None:
        fixture = self.with_case()
        self.write_ipc_error_rows(fixture, [1], "connection_reset")
        result = self.assert_fails_with(fixture, "ipc_stable_after_success")
        self.assertEqual(result["counters"]["ipc_other_error_after_first_success"], 1)

    def test_transient_missing_socket_does_not_mask_mpv_stuck_on_old_media(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-b", "<media-path:b>", "1", "<media-path:a>"),
                ("media-b", "<media-path:b>", "1", "<media-path:a>"),
                ("media-b", "<media-path:b>", "1", "<media-path:a>"),
            ],
        )
        rows = fixture.rows()
        for row in rows:
            row.setdefault("ipc_error", "")
        rows[2]["ipc_result"] = "error"
        rows[2]["ipc_error"] = "missing_socket"
        rows[2]["path_alias"] = ""
        rows[2]["filename_alias"] = ""
        rows[2]["time_pos"] = ""
        rows[2]["estimated_frame_number"] = ""
        rows[2]["hwdec_current"] = ""
        rows[2]["vo_configured"] = ""
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "status_mpv_path_aligned")
        self.assertTrue(result["checks"]["ipc_stable_after_success"])
        self.assertEqual(result["counters"]["ipc_missing_socket_after_first_success"], 1)
        self.assertTrue(result["counters"]["status_advanced_without_mpv"])

    def test_rejects_wrong_mpv_count(self) -> None:
        fixture = self.with_case()
        fixture.mutate_json("process.json", mpv_count=2)
        self.assert_fails_with(fixture, "single_mpv")

    def test_rejects_decode_stall_when_time_advances_but_frame_is_frozen(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row["estimated_frame_number"] = "275"
        fixture.write_rows(rows)
        result = self.assert_fails_with(fixture, "playback_progressed")
        self.assertTrue(result["counters"]["time_pos_progressed"])
        self.assertFalse(result["counters"]["estimated_frame_progressed"])

    def test_rejects_short_frame_burst_then_stall(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        template = rows[0].copy()
        snapshot = json.loads(template["status_snapshot_json"])
        snapshot["playlist_size"] = 1
        generated = []
        for index, frame in enumerate(("100", "130", "160", "160", "160", "160", "160", "160"), start=1):
            row = template.copy()
            row["seq"] = str(index)
            row["rel_sec"] = str(index - 1)
            row["time_pos"] = f"{index - 1}.10"
            row["current_alias"] = "media-a"
            row["estimated_frame_number"] = frame
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
            generated.append(row)
        fixture.write_rows(generated)
        result = self.assert_fails_with(fixture, "playback_progressed")
        self.assertTrue(result["counters"]["time_pos_progressed"])
        self.assertFalse(result["counters"]["estimated_frame_progressed"])
        self.assertGreater(result["counters"]["estimated_frame_trailing_nonprogress_steps"], 1)

    def test_frame_progress_uses_mpv_item_while_status_lags_transition(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
            ],
        )
        rows = fixture.rows()
        frames = ("100", "130", "160", "91", "", "24", "59", "91", "121", "151")
        for row, frame in zip(rows, frames):
            row["estimated_frame_number"] = frame
        fixture.write_rows(rows)

        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertTrue(result["checks"]["status_mpv_path_aligned"])
        self.assertTrue(result["checks"]["playback_progressed"])
        self.assertEqual(result["counters"]["estimated_frame_failed_segments"], 0)

    def test_status_jitter_cannot_hide_frozen_mpv_frames(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for index, row in enumerate(rows):
            row["estimated_frame_number"] = "275"
            row["status_current_alias"] = f"media-status-{index % 2}"
            row["status_path_alias"] = f"<media-path:status-{index % 2}>"
            row["status_current_index"] = str(index % 2)
        fixture.write_rows(rows)

        result = fixture.result()
        self.assertFalse(result["checks"]["playback_progressed"])
        self.assertFalse(result["counters"]["estimated_frame_progressed"])

    def test_rejects_missing_frame_progress_evidence(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row["estimated_frame_number"] = ""
        fixture.write_rows(rows)
        result = self.assert_fails_with(fixture, "estimated_frame_present")
        self.assertIn("playback_progressed", result["failure_reasons"])

    def test_candidate_process_filter_allows_ambient_live_mpv(self) -> None:
        fixture = self.with_case()
        fixture.mutate_json("systemd.json", target_mode="candidate", candidate_pid_present=True)
        fixture.mutate_json(
            "process.json",
            mpv_count=1,
            total_mpv_count=2,
            process_filter="input-ipc-server",
        )
        self.assertTrue(fixture.result()["passed"])

    def test_service_mode_rejects_filtered_or_extra_mpv_evidence(self) -> None:
        fixture = self.with_case()
        fixture.mutate_json("systemd.json", target_mode="service")
        fixture.mutate_json("process.json", mpv_count=1, total_mpv_count=2, process_filter="input-ipc-server")
        result = fixture.result()
        self.assertFalse(result["passed"])
        self.assertIn("service_process_unfiltered", result["failure_reasons"])
        self.assertIn("service_single_total_mpv", result["failure_reasons"])

    def test_service_mode_requires_total_mpv_count_evidence(self) -> None:
        fixture = self.with_case()
        process = fixture.read_json("process.json")
        process.pop("total_mpv_count", None)
        fixture.write_json("process.json", process)
        self.assert_fails_with(fixture, "service_total_mpv_count_present")

    def test_rejects_status_transition_when_mpv_path_repeats(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for index, row in enumerate(rows):
            row["current_alias"] = "<media-path:same-cache>"
            row["path_alias"] = "<media-path:same-cache>"
            row["status_current_alias"] = "media-a" if index < 3 else "media-b"
            row["status_path_alias"] = "<media-path:a>" if index < 3 else "<media-path:b>"
            row["status_current_index"] = "0" if index < 3 else "1"
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "status_mpv_path_aligned")
        self.assertEqual(result["counters"]["unique_aliases"], 2)
        self.assertEqual(result["counters"]["mpv_unique_aliases"], 1)
        self.assertEqual(result["counters"]["status_unique_aliases"], 2)
        self.assertFalse(result["counters"]["mpv_media_transitions_observed"])
        self.assertTrue(result["counters"]["status_transitions_observed"])
        self.assertGreater(result["counters"]["status_mpv_max_consecutive_mismatches"], 2)

    def test_rejects_transition_required_without_status_mpv_comparable_samples(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row["status_current_alias"] = ""
            row["status_path_alias"] = ""
            row["status_current_index"] = ""
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "status_mpv_path_aligned")
        self.assertEqual(result["counters"]["status_mpv_comparable_samples"], 0)
        self.assertEqual(result["counters"]["mpv_unique_aliases"], 2)

    def test_current_alias_status_fallback_is_not_mpv_alignment_evidence(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row["path_alias"] = ""
            row["filename_alias"] = ""
            row["current_alias"] = row["status_path_alias"]
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "status_mpv_path_aligned")
        self.assertEqual(result["counters"]["status_mpv_comparable_samples"], 0)

    def test_rejects_repeated_short_status_mpv_mismatches(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        statuses = [
            ("media-a", "<media-path:a>", "0"),
            ("media-a", "<media-path:a>", "0"),
            ("media-a", "<media-path:a>", "0"),
            ("media-b", "<media-path:b>", "1"),
            ("media-b", "<media-path:b>", "1"),
            ("media-a", "<media-path:a>", "0"),
            ("media-a", "<media-path:a>", "0"),
            ("media-a", "<media-path:a>", "0"),
            ("media-b", "<media-path:b>", "1"),
            ("media-b", "<media-path:b>", "1"),
        ]
        rows = []
        for index, (status_alias, status_path_alias, status_index) in enumerate(statuses, start=1):
            row = template.copy()
            row["seq"] = str(index)
            row["rel_sec"] = str(index - 1)
            row["time_pos"] = f"{index - 1}.10"
            row["estimated_frame_number"] = str(index * 30)
            row["current_alias"] = "<media-path:a>"
            row["path_alias"] = "<media-path:a>"
            row["status_current_alias"] = status_alias
            row["status_path_alias"] = status_path_alias
            row["status_current_index"] = status_index
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["playlist_size"] = 2
            snapshot["current_index"] = int(status_index)
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
            rows.append(row)
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "status_mpv_path_aligned")
        self.assertEqual(result["counters"]["status_mpv_comparable_samples"], 10)
        self.assertEqual(result["counters"]["status_mpv_mismatch_samples"], 4)
        self.assertEqual(result["counters"]["status_mpv_max_consecutive_mismatches"], 2)
        self.assertEqual(result["counters"]["status_mpv_max_allowed_mismatch_samples"], 2)
        self.assertGreater(result["counters"]["status_mpv_unexplained_mismatch_runs"], 0)

    def test_accepts_bounded_status_mpv_transition_lag(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
            ],
        )

        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertEqual(result["failure_reasons"], [])
        self.assertEqual(result["counters"]["status_mpv_mismatch_samples"], 2)
        self.assertEqual(result["counters"]["status_mpv_transition_lag_runs"], 1)
        self.assertEqual(result["counters"]["status_mpv_unexplained_mismatch_runs"], 0)

    def test_terminal_status_mpv_lag_is_aligned_but_not_playback_proof(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
            ],
        )

        result = fixture.result()
        self.assertFalse(result["passed"])
        self.assertTrue(result["checks"]["status_mpv_path_aligned"])
        self.assertFalse(result["checks"]["motion_frame_progress_ok"])
        self.assertEqual(result["counters"]["status_mpv_transition_lag_runs"], 1)
        self.assertEqual(result["counters"]["status_mpv_terminal_transition_lag_runs"], 1)

    def test_accepts_initial_status_mpv_transition_lag(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:c>"),
            ],
        )

        result = fixture.result()
        self.assertTrue(result["checks"]["status_mpv_path_aligned"])
        self.assertNotIn("status_mpv_path_aligned", result["failure_reasons"])
        self.assertEqual(result["counters"]["status_mpv_initial_transition_lag_runs"], 1)

    def test_rejects_initial_status_mpv_lag_without_later_alignment(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
            ],
        )

        result = self.assert_fails_with(fixture, "status_mpv_path_aligned")
        self.assertEqual(result["counters"]["status_mpv_initial_transition_lag_runs"], 0)
        self.assertEqual(result["counters"]["status_mpv_unexplained_mismatch_runs"], 1)

    def test_accepts_many_bounded_status_mpv_transition_lag_runs(self) -> None:
        fixture = self.with_case()
        samples = [("media-a", "<media-path:a>", "0", "<media-path:a>")]
        for _ in range(10):
            samples.extend(
                [
                    ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                    ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                    ("media-b", "<media-path:b>", "1", "<media-path:a>"),
                    ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ]
            )
        self.write_status_mpv_alignment_rows(fixture, samples)

        result = fixture.result()
        self.assertTrue(result["checks"]["status_mpv_path_aligned"])
        self.assertNotIn("status_mpv_path_aligned", result["failure_reasons"])
        self.assertEqual(result["counters"]["status_mpv_unexplained_mismatch_runs"], 0)
        self.assertGreater(
            result["counters"]["status_mpv_transition_lag_runs"],
            result["counters"]["status_mpv_max_allowed_transition_lag_runs"],
        )

    def test_accepts_bounded_chained_status_mpv_transition_lag(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:c>"),
            ],
        )

        result = fixture.result()
        self.assertTrue(result["checks"]["status_mpv_path_aligned"])
        self.assertNotIn("status_mpv_path_aligned", result["failure_reasons"])
        self.assertEqual(result["counters"]["status_mpv_chained_transition_lag_runs"], 1)
        self.assertEqual(result["counters"]["status_mpv_unexplained_mismatch_runs"], 0)

    def test_accepts_forward_status_lag_to_later_alignment(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:d>"),
                ("media-c", "<media-path:c>", "2", "<media-path:d>"),
                ("media-g", "<media-path:g>", "3", "<media-path:g>"),
                ("media-g", "<media-path:g>", "3", "<media-path:g>"),
            ],
        )

        result = fixture.result()
        self.assertTrue(result["checks"]["status_mpv_path_aligned"])
        self.assertNotIn("status_mpv_path_aligned", result["failure_reasons"])
        self.assertGreaterEqual(result["counters"]["status_mpv_forward_status_lag_runs"], 1)
        self.assertEqual(result["counters"]["status_mpv_unexplained_mismatch_runs"], 0)

    def test_accepts_three_segment_forward_status_lag_with_later_alignment(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:d>"),
                ("media-c", "<media-path:c>", "2", "<media-path:d>"),
                ("media-d", "<media-path:d>", "3", "<media-path:d>"),
                ("media-d", "<media-path:d>", "3", "<media-path:d>"),
            ],
        )

        result = fixture.result()
        self.assertTrue(result["checks"]["status_mpv_path_aligned"])
        self.assertNotIn("status_mpv_path_aligned", result["failure_reasons"])
        self.assertEqual(result["counters"]["status_mpv_forward_status_lag_runs"], 1)
        self.assertEqual(result["counters"]["status_mpv_forward_status_lag_samples"], 7)
        self.assertEqual(result["counters"]["status_mpv_unexplained_mismatch_runs"], 0)

    def test_accepts_final_bridge_when_status_skips_short_intermediate_item(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-b", "<media-path:b>", "1", "<media-path:d>"),
                ("media-d", "<media-path:d>", "3", "<media-path:d>"),
                ("media-d", "<media-path:d>", "3", "<media-path:d>"),
            ],
        )

        result = fixture.result()
        self.assertTrue(result["checks"]["status_mpv_path_aligned"])
        self.assertNotIn("status_mpv_path_aligned", result["failure_reasons"])
        self.assertEqual(result["counters"]["status_mpv_forward_status_lag_runs"], 1)
        self.assertEqual(result["counters"]["status_mpv_unexplained_mismatch_runs"], 0)

    def test_accepts_terminal_chained_forward_status_lag(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:d>"),
            ],
        )

        result = fixture.result()
        self.assertTrue(result["checks"]["status_mpv_path_aligned"])
        self.assertNotIn("status_mpv_path_aligned", result["failure_reasons"])
        self.assertEqual(result["counters"]["status_mpv_forward_status_lag_runs"], 1)
        self.assertEqual(result["counters"]["status_mpv_forward_status_lag_samples"], 6)

    def test_rejects_unbounded_chained_status_mpv_transition_lag(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:d>"),
                ("media-d", "<media-path:d>", "3", "<media-path:e>"),
                ("media-e", "<media-path:e>", "4", "<media-path:e>"),
            ],
        )

        result = self.assert_fails_with(fixture, "status_mpv_path_aligned")
        self.assertEqual(result["counters"]["status_mpv_chained_transition_lag_runs"], 0)
        self.assertEqual(result["counters"]["status_mpv_unexplained_mismatch_runs"], 1)

    def test_rejects_forward_status_lag_without_next_item_proof(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
            ],
        )
        rows = fixture.rows()
        for row in rows:
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot.pop("next_item", None)
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "status_mpv_path_aligned")
        self.assertEqual(result["counters"]["status_mpv_forward_status_lag_runs"], 0)
        self.assertEqual(result["counters"]["status_mpv_unexplained_mismatch_runs"], 1)

    def test_rejects_too_many_terminal_forward_status_lag_segments(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:d>"),
            ],
        )

        result = self.assert_fails_with(fixture, "status_mpv_path_aligned")
        self.assertEqual(result["counters"]["status_mpv_forward_status_lag_runs"], 0)
        self.assertEqual(result["counters"]["status_mpv_unexplained_mismatch_runs"], 1)

    def test_rejects_long_status_mpv_transition_lag(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-a", "<media-path:a>", "0", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
            ],
        )

        result = self.assert_fails_with(fixture, "status_mpv_path_aligned")
        self.assertEqual(result["counters"]["status_mpv_mismatch_samples"], 6)
        self.assertEqual(result["counters"]["status_mpv_long_transition_lag_runs"], 1)

    def test_rejects_status_mpv_mismatch_outside_transition_edge(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-c", "<media-path:c>", "2", "<media-path:b>"),
                ("media-c", "<media-path:c>", "2", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
                ("media-b", "<media-path:b>", "1", "<media-path:b>"),
            ],
        )

        result = self.assert_fails_with(fixture, "status_mpv_path_aligned")
        self.assertEqual(result["counters"]["status_mpv_unexplained_mismatch_runs"], 1)

    def test_rejects_multisegment_stall_even_when_last_segment_progresses(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = []
        fieldnames = list(template.keys())
        for field in ("status_current_alias", "status_current_index"):
            if field not in fieldnames:
                fieldnames.append(field)

        for index in range(30):
            row = {field: "" for field in fieldnames}
            row.update(template)
            row["seq"] = str(index + 1)
            row["rel_sec"] = str(index)
            row["current_alias"] = "media-cache-a"
            row["status_current_alias"] = "media-first"
            row["status_current_index"] = "0"
            row["time_pos"] = f"{index}.10"
            row["estimated_frame_number"] = "999"
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["playlist_size"] = 2
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
            rows.append(row)

        for offset, frame in enumerate(("10", "40", "70"), start=1):
            row = {field: "" for field in fieldnames}
            row.update(template)
            row["seq"] = str(30 + offset)
            row["rel_sec"] = str(30 + offset - 1)
            row["current_alias"] = "media-cache-b"
            row["status_current_alias"] = "media-second"
            row["status_current_index"] = "1"
            row["time_pos"] = f"{offset}.10"
            row["estimated_frame_number"] = frame
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["playlist_size"] = 2
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
            rows.append(row)

        with fixture.path("playback-samples.tsv").open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, delimiter="\t", fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        result = self.assert_fails_with(fixture, "playback_progressed")
        self.assertTrue(result["counters"]["time_pos_progressed"])
        self.assertGreaterEqual(result["counters"]["estimated_frame_evaluable_segments"], 2)
        self.assertEqual(result["counters"]["estimated_frame_failed_segments"], 1)

    def test_rejects_short_final_segment_without_proven_progress(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = []
        fieldnames = list(template.keys())
        for field in ("status_current_alias", "status_current_index"):
            if field not in fieldnames:
                fieldnames.append(field)

        for index, frame in enumerate(("10", "40", "70", "100"), start=1):
            row = {field: "" for field in fieldnames}
            row.update(template)
            row["seq"] = str(index)
            row["rel_sec"] = str(index - 1)
            row["current_alias"] = "media-cache-a"
            row["status_current_alias"] = "media-first"
            row["status_current_index"] = "0"
            row["time_pos"] = f"{index - 1}.10"
            row["estimated_frame_number"] = frame
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["playlist_size"] = 2
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
            rows.append(row)

        for offset in range(2):
            row = {field: "" for field in fieldnames}
            row.update(template)
            row["seq"] = str(5 + offset)
            row["rel_sec"] = str(4 + offset)
            row["current_alias"] = "media-cache-b"
            row["status_current_alias"] = "media-second"
            row["status_current_index"] = "1"
            row["time_pos"] = f"{4 + offset}.10"
            row["estimated_frame_number"] = "999"
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["playlist_size"] = 2
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
            rows.append(row)

        with fixture.path("playback-samples.tsv").open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, delimiter="\t", fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        result = self.assert_fails_with(fixture, "playback_progressed")
        self.assertEqual(result["counters"]["estimated_frame_evaluable_segments"], 1)
        self.assertEqual(result["counters"]["estimated_frame_short_segments"], 1)
        self.assertEqual(result["counters"]["estimated_frame_failed_segments"], 1)

    def test_candidate_mode_tolerates_polling_disabled_status_only(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["last_poll_error"] = "polling_disabled"
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
        fixture.write_rows(rows)

        service_result = fixture.result()
        self.assertFalse(service_result["passed"])
        self.assertIn("status_no_failures", service_result["failure_reasons"])

        fixture.mutate_json("systemd.json", target_mode="candidate", candidate_pid_present=True)
        fixture.mutate_json("process.json", process_filter="input-ipc-server")
        candidate_result = fixture.result()
        self.assertTrue(candidate_result["checks"]["status_no_failures"])
        self.assertNotIn("status_no_failures", candidate_result["failure_reasons"])

    def test_candidate_mode_tolerates_startup_black_screen_risk_only(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        rows[0]["status_playback_state"] = "player_starting"
        snapshot = json.loads(rows[0]["status_snapshot_json"])
        snapshot["playback_state"] = "player_starting"
        snapshot["black_screen_risk_reason"] = "present"
        rows[0]["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
        fixture.write_rows(rows)

        service_result = fixture.result()
        self.assertFalse(service_result["passed"])
        self.assertIn("status_no_failures", service_result["failure_reasons"])

        fixture.mutate_json("systemd.json", target_mode="candidate", candidate_pid_present=True)
        fixture.mutate_json("process.json", process_filter="input-ipc-server")
        candidate_result = fixture.result()
        self.assertTrue(candidate_result["checks"]["status_no_failures"])
        self.assertNotIn("status_no_failures", candidate_result["failure_reasons"])

    def test_candidate_mode_rejects_black_screen_risk_after_startup(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        snapshot = json.loads(rows[0]["status_snapshot_json"])
        snapshot["playback_state"] = "playing"
        snapshot["black_screen_risk_reason"] = "present"
        rows[0]["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
        fixture.write_rows(rows)
        fixture.mutate_json("systemd.json", target_mode="candidate", candidate_pid_present=True)
        fixture.mutate_json("process.json", process_filter="input-ipc-server")
        self.assert_fails_with(fixture, "status_no_failures")

    def test_candidate_mode_rejects_generic_poll_error_presence(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["last_poll_error"] = "present"
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
        fixture.write_rows(rows)
        fixture.mutate_json("systemd.json", target_mode="candidate", candidate_pid_present=True)
        fixture.mutate_json("process.json", process_filter="input-ipc-server")
        self.assert_fails_with(fixture, "status_no_failures")

    def test_rejects_media_load_failed_and_mpv_restart(self) -> None:
        fixture = self.with_case()
        fixture.mutate_json("player-counters.json", media_load_failed=1, mpv_restart=1)
        result = fixture.result()
        self.assertFalse(result["passed"])
        self.assertIn("media_load_failed_zero", result["failure_reasons"])
        self.assertIn("mpv_restart_zero", result["failure_reasons"])

    def test_rejects_watchdog_recovery_during_health_window(self) -> None:
        fixture = self.with_case()
        fixture.write_json("watchdog.json", {
            "schema": "dadooh.c18.playback.deep_health.watchdog.v1",
            "event_changed_during_window": True,
            "action_during_window": "realign_mpv_to_status",
            "start": {"exists": False},
            "end": {
                "exists": True,
                "event": {
                    "schema": "dadooh.player.status_mpv_watchdog.v1",
                    "action": "realign_mpv_to_status",
                    "reason": "status_advanced_without_mpv",
                    "recorded_at_utc": "2026-07-03T04:00:00Z",
                },
            },
        })
        result = fixture.result()
        self.assertFalse(result["passed"])
        self.assertIn("status_mpv_watchdog_recovery_absent", result["failure_reasons"])
        self.assertEqual(
            result["counters"]["status_mpv_watchdog_action_during_window"],
            "realign_mpv_to_status",
        )

    def test_ignores_prior_watchdog_recovery_outside_health_window(self) -> None:
        fixture = self.with_case()
        fixture.write_json("watchdog.json", {
            "schema": "dadooh.c18.playback.deep_health.watchdog.v1",
            "event_changed_during_window": False,
            "action_during_window": "",
            "start": {
                "exists": True,
                "event": {
                    "schema": "dadooh.player.status_mpv_watchdog.v1",
                    "action": "realign_mpv_to_status",
                    "reason": "status_advanced_without_mpv",
                    "recorded_at_utc": "2026-07-03T03:00:00Z",
                },
            },
            "end": {
                "exists": True,
                "event": {
                    "schema": "dadooh.player.status_mpv_watchdog.v1",
                    "action": "realign_mpv_to_status",
                    "reason": "status_advanced_without_mpv",
                    "recorded_at_utc": "2026-07-03T03:00:00Z",
                },
            },
        })
        self.assertTrue(fixture.result()["passed"])

    def test_rejects_kernel_fault_counters(self) -> None:
        fixture = self.with_case()
        fixture.mutate_json("kernel.json", panfrost_faults=1, mmc_timeout_reset=1, ext4_errors=1)
        result = fixture.result()
        self.assertFalse(result["passed"])
        self.assertIn("panfrost_faults_zero", result["failure_reasons"])
        self.assertIn("mmc_timeout_reset_zero", result["failure_reasons"])
        self.assertIn("ext4_errors_zero", result["failure_reasons"])

    def test_rejects_panfrost_fault_delta(self) -> None:
        fixture = self.with_case()
        fixture.mutate_json("kernel.json", panfrost_faults=0, panfrost_faults_start=0, panfrost_faults_delta=1)
        result = fixture.result()
        self.assertFalse(result["passed"])
        self.assertIn("panfrost_faults_delta_zero", result["failure_reasons"])

    def test_delta_policy_allows_prior_attributed_panfrost_faults(self) -> None:
        fixture = self.with_case()
        fixture.mutate_json("kernel.json", panfrost_faults=2, panfrost_faults_start=2, panfrost_faults_delta=0)
        absolute = fixture.result()
        self.assertFalse(absolute["passed"])
        self.assertIn("panfrost_faults_zero", absolute["failure_reasons"])

        delta = fixture.result_with_panfrost_policy("delta")
        self.assertTrue(delta["passed"])
        self.assertEqual(delta["failure_reasons"], [])
        self.assertEqual(delta["expected"]["panfrost_fault_policy"], "delta")

    def test_delta_policy_still_rejects_new_panfrost_faults(self) -> None:
        fixture = self.with_case()
        fixture.mutate_json("kernel.json", panfrost_faults=3, panfrost_faults_start=2, panfrost_faults_delta=1)
        result = fixture.result_with_panfrost_policy("delta")
        self.assertFalse(result["passed"])
        self.assertIn("panfrost_faults_delta_zero", result["failure_reasons"])

    def test_rejects_missing_ext4_counter(self) -> None:
        fixture = self.with_case()
        kernel = fixture.read_json("kernel.json")
        kernel.pop("ext4_errors", None)
        fixture.write_json("kernel.json", kernel)
        self.assert_fails_with(fixture, "ext4_errors_present")

    def test_rejects_missing_restart_and_fault_counter_evidence(self) -> None:
        fixture = self.with_case()
        systemd = fixture.read_json("systemd.json")
        systemd.pop("nrestarts_delta", None)
        fixture.write_json("systemd.json", systemd)

        kernel = fixture.read_json("kernel.json")
        kernel.pop("panfrost_faults", None)
        kernel.pop("mmc_timeout_reset", None)
        fixture.write_json("kernel.json", kernel)

        counters = fixture.read_json("player-counters.json")
        counters.pop("media_load_failed", None)
        counters.pop("mpv_restart", None)
        fixture.write_json("player-counters.json", counters)

        result = fixture.result()
        self.assertFalse(result["passed"])
        for reason in (
            "nrestarts_delta_present",
            "panfrost_faults_present",
            "mmc_timeout_reset_present",
            "media_load_failed_present",
            "mpv_restart_present",
        ):
            self.assertIn(reason, result["failure_reasons"])

    def test_non_destructive_collector_static_contract(self) -> None:
        source = (REPO_ROOT / "scripts" / "board" / "c18_playback_health_collect.py").read_text(encoding="utf-8")
        self.assertNotIn("systemctl stop", source)
        self.assertNotIn("systemctl restart", source)
        self.assertNotIn("systemctl start", source)
        self.assertNotIn("truncate", source)
        self.assertIn("playback-deep-health-public.json", source)
        self.assertIn("health.evaluate", source)
        self.assertIn("--target-mode", source)
        self.assertIn("--match-process-ipc", source)
        self.assertIn("process_filter", source)
        self.assertIn("deep-health-watchdog.json", source)
        self.assertIn("watchdog_state_snapshot", source)
        self.assertIn("journalctl", source)
        self.assertIn("journal_media_load_failed", source)

    def test_collector_matches_candidate_ipc_argv(self) -> None:
        ipc = Path("/tmp/c18-candidate/mpv.sock")
        self.assertTrue(collector.argv_matches_ipc([f"--input-ipc-server={ipc}"], ipc))
        self.assertTrue(collector.argv_matches_ipc(["--input-ipc-server", str(ipc)], ipc))
        self.assertFalse(collector.argv_matches_ipc(["--input-ipc-server=/tmp/other.sock"], ipc))

    def test_collector_counts_service_journal_player_events(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c18-player-counters-") as tmp:
            root = Path(tmp)
            mpv_log = root / "mpv.log"
            gen_dir = root / "gen"
            gen_dir.mkdir()
            mpv_log.write_text("local media_load_failed\n", encoding="utf-8")
            journal = "Restarting MPV reason=media_load_failed:media-123\n"
            proc = mock.Mock(returncode=0, stdout=journal)
            with mock.patch.object(collector, "run", return_value=proc):
                counters = collector.count_player_log_counters(
                    mpv_log,
                    gen_dir,
                    service="kiosky-player.service",
                    start_utc="2026-07-03T04:43:05Z",
                    end_utc="2026-07-03T04:53:05Z",
                )
        self.assertEqual(counters["file_media_load_failed"], 1)
        self.assertEqual(counters["journal_media_load_failed"], 1)
        self.assertEqual(counters["journal_mpv_restart"], 1)
        self.assertEqual(counters["media_load_failed"], 2)
        self.assertEqual(counters["mpv_restart"], 1)

    def test_collector_fails_closed_when_service_journal_unavailable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c18-player-counters-") as tmp:
            root = Path(tmp)
            mpv_log = root / "mpv.log"
            gen_dir = root / "gen"
            gen_dir.mkdir()
            mpv_log.write_text("", encoding="utf-8")
            proc = mock.Mock(returncode=1, stdout="")
            with mock.patch.object(collector, "run", return_value=proc):
                counters = collector.count_player_log_counters(
                    mpv_log,
                    gen_dir,
                    service="kiosky-player.service",
                    start_utc="2026-07-03T04:43:05Z",
                    end_utc="2026-07-03T04:53:05Z",
                )
        self.assertTrue(counters["journal_query_failed"])
        self.assertEqual(counters["media_load_failed"], -1)
        self.assertEqual(counters["mpv_restart"], -1)

    def test_candidate_health_config_is_isolated_and_sanitized(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c18-candidate-config-") as tmp:
            root = Path(tmp)
            template = root / "template.json"
            template.write_text(
                json.dumps(
                    {
                        "api_url": "https://private.example.invalid/api?api_key=SECRET",
                        "api_key": "SECRET",
                        "environment_id": "ENV_SECRET",
                        "telemetry_token": "TOKEN_SECRET",
                        "custom_secret": "CUSTOM_SECRET",
                        "config_ui_enabled": True,
                        "cache_dir": "/data/media/kiosky-player",
                        "ipc_path": "/tmp/kiosky/mpv.sock",
                    }
                ),
                encoding="utf-8",
            )
            cfg = candidate_health.candidate_config(template, root / "work")
            self.assertEqual(cfg["api_key"], "")
            self.assertEqual(cfg["environment_id"], "")
            self.assertEqual(cfg["telemetry_token"], "")
            self.assertFalse(cfg["telemetry_enabled"])
            self.assertFalse(cfg["config_ui_enabled"])
            self.assertTrue(str(cfg["cache_dir"]).startswith(str(root / "work")))
            self.assertTrue(str(cfg["ipc_path"]).startswith(str(root / "work")))
            self.assertNotIn("custom_secret", cfg)
            payload = json.dumps(cfg, sort_keys=True)
            for forbidden in ("SECRET", "ENV_SECRET", "TOKEN_SECRET", "CUSTOM_SECRET", "private.example"):
                self.assertNotIn(forbidden, payload)

    def test_candidate_health_uses_short_tmp_ipc_path_for_long_workdir(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c18-candidate-config-") as tmp:
            root = Path(tmp)
            short_work = root / "work"
            short_cfg = candidate_health.candidate_config(None, short_work)
            self.assertTrue(str(short_cfg["ipc_path"]).startswith(str(short_work)))

            long_work = root / ("x" * 96) / ("y" * 32)
            long_cfg = candidate_health.candidate_config(None, long_work)
            ipc_path = Path(str(long_cfg["ipc_path"]))
            self.assertTrue(str(ipc_path).startswith("/tmp/c18-pr-ipc-"))
            self.assertLess(len(str(ipc_path)), candidate_health.UNIX_SOCKET_PATH_SOFT_LIMIT)
            self.assertFalse(ipc_path.parent.exists())
            candidate_health.prepare_candidate_ipc_path(ipc_path, os.getuid(), os.getgid())
            self.assertTrue(ipc_path.parent.is_dir())
            candidate_health.cleanup_candidate_ipc_path(long_cfg, long_work)
            self.assertFalse(ipc_path.parent.exists())

    def test_candidate_health_canary_playlist_is_explicit_and_isolated(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c18-candidate-canary-") as tmp:
            root = Path(tmp)
            canary = root / "clip.mp4"
            canary.write_bytes(b"not-a-real-video-for-playlist-shape")
            cfg = candidate_health.candidate_config(None, root / "work")
            normalized = candidate_health.normalize_canary_media(canary)
            self.assertEqual(normalized, canary.resolve())
            candidate_health.write_canary_playlist(cfg, normalized)

            state = json.loads((Path(cfg["state_dir"]) / "playlist_last.json").read_text(encoding="utf-8"))
            self.assertEqual(state["version"], 1)
            self.assertEqual(len(state["playlist"]), 1)
            self.assertEqual(state["playlist"][0]["path"], str(canary.resolve()))
            self.assertEqual(state["playlist"][0]["duration_ms"], cfg["default_duration_ms"])

            public_config = json.dumps(cfg, sort_keys=True)
            self.assertNotIn(str(canary), public_config)

    def test_candidate_health_canary_outlives_observation_window(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c18-candidate-canary-window-") as tmp:
            root = Path(tmp)
            canary = root / "clip.mp4"
            canary.write_bytes(b"not-a-real-video-for-playlist-shape")
            cfg = candidate_health.candidate_config(None, root / "work")
            duration_ms = candidate_health.canary_exposure_duration_ms(
                cfg,
                duration_sec=30,
                interval_sec=1,
                startup_wait_sec=8,
            )

            self.assertEqual(duration_ms, 40000)
            candidate_health.write_canary_playlist(
                cfg,
                canary.resolve(),
                duration_ms=duration_ms,
            )
            state = json.loads(
                (Path(cfg["state_dir"]) / "playlist_last.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["playlist"][0]["duration_ms"], 40000)

            cfg["default_duration_ms"] = 45000
            self.assertEqual(
                candidate_health.canary_exposure_duration_ms(
                    cfg,
                    duration_sec=30,
                    interval_sec=1,
                    startup_wait_sec=8,
                ),
                45000,
            )

    def test_candidate_health_run_path_uses_window_bound_canary_duration(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c18-candidate-canary-callsite-") as tmp:
            root = Path(tmp)
            release = root / "release"
            release.mkdir()
            canary = root / "clip.mp4"
            canary.write_bytes(b"not-a-real-video-for-playlist-shape")
            identity = {
                "version": "fixture",
                "payload_sha256": "0" * 64,
                "kiosk_py_sha256": "1" * 64,
                "tree_sha256": "2" * 64,
            }
            with (
                mock.patch.object(candidate_health, "write_canary_playlist") as write_playlist,
                mock.patch.object(
                    candidate_health,
                    "candidate_run_user",
                    side_effect=RuntimeError("stop-after-canary-playlist"),
                ),
                self.assertRaisesRegex(RuntimeError, "stop-after-canary-playlist"),
            ):
                candidate_health.run_candidate_health(
                    release,
                    identity,
                    canary_media=canary,
                    output_dir=root / "work",
                    duration_sec=30,
                    interval_sec=1,
                    startup_wait_sec=8,
                )

            self.assertEqual(write_playlist.call_count, 1)
            self.assertEqual(write_playlist.call_args.kwargs["duration_ms"], 40000)

    def test_candidate_health_canary_rejects_private_or_unsupported_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c18-candidate-canary-") as tmp:
            root = Path(tmp)
            unsupported = root / "clip.txt"
            unsupported.write_text("nope", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                candidate_health.normalize_canary_media(unsupported)
            with self.assertRaises(RuntimeError):
                candidate_health.normalize_canary_media(Path("/data/config/config.json"))
            outside_allowed = root / "clip.mp4"
            outside_allowed.write_bytes(b"video-shape")
            previous_roots = candidate_health.CANARY_MEDIA_ALLOWED_ROOTS
            candidate_health.CANARY_MEDIA_ALLOWED_ROOTS = (root / "allowed",)
            try:
                with self.assertRaises(RuntimeError) as raised:
                    candidate_health.normalize_canary_media(outside_allowed)
                self.assertNotIn(str(outside_allowed), str(raised.exception))
            finally:
                candidate_health.CANARY_MEDIA_ALLOWED_ROOTS = previous_roots

    def test_candidate_health_env_is_minimal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c18-candidate-env-") as tmp:
            env = candidate_health.minimal_candidate_env(Path(tmp))
            self.assertIn("PATH", env)
            self.assertIn("HOME", env)
            self.assertIn("TMPDIR", env)
            self.assertIn("XDG_RUNTIME_DIR", env)
            self.assertEqual(env.get("KIOSKY_TELEMETRY_TOKEN"), "")
            for forbidden in ("GITHUB_TOKEN", "HTTP_PROXY", "HTTPS_PROXY", "TOTEM_DATA_ROOT", "SSHPASS"):
                self.assertNotIn(forbidden, env)

    def test_candidate_health_cli_requires_lab_guard(self) -> None:
        rc = candidate_health.main(["--release-dir", str(REPO_ROOT / "player-runtime" / "kiosky-player"), "--json"])
        self.assertEqual(rc, 44)

    def test_collector_aliases_do_not_echo_sensitive_paths_or_urls(self) -> None:
        url = "https://media.example.invalid/private/file.mp4?api_key=SECRET"
        path = "/data/media/kiosky-player/private-file.mp4"
        self.assertNotIn("https://", collector.safe_path_alias(url))
        self.assertNotIn("api_key", collector.safe_path_alias(url))
        self.assertNotIn("private-file", collector.safe_path_alias(path))
        self.assertTrue(collector.media_alias(path, url).startswith("media-"))

    def test_collector_classifies_paths_without_exposing_them(self) -> None:
        self.assertEqual(
            collector.classify_current_path(
                "/tmp/private/startup-feedback-c25-visible-state-h264-v1-loading_content-0123456789abcdef-1280x720.mp4"
            ),
            "public_surface",
        )
        self.assertEqual(
            collector.classify_current_path(
                "/tmp/private/startup-feedback-c25-visible-state-h264-v1-content_unavailable-0123456789abcdef-1280x720.mp4"
            ),
            "public_surface",
        )
        still_path = "/data/media/private-campaign.png.h264.mp4"
        still_item = collector.sanitize_item({"path": still_path, "source_path": "/data/media/private-campaign.png"})
        self.assertEqual(collector.classify_current_path(still_path, still_item), "still_image_sidecar")
        motion_path = "/data/media/private-campaign.mp4"
        motion_item = collector.sanitize_item({"path": motion_path})
        self.assertEqual(collector.classify_current_path(motion_path, motion_item), "motion_media")
        self.assertEqual(collector.classify_current_path(motion_path, {}, motion_item), "motion_media")
        self.assertEqual(collector.classify_current_path(motion_path, {}), "unclassified_media")
        spoof_path = "/data/media/real-video.png.h264.mp4"
        spoof_item = collector.sanitize_item({"path": spoof_path})
        self.assertEqual(collector.classify_current_path(spoof_path, spoof_item), "motion_media")
        mismatched_item = collector.sanitize_item({"path": motion_path, "source_path": "/data/media/poster.png"})
        self.assertEqual(collector.classify_current_path(motion_path, mismatched_item), "motion_media")
        surface_name = "startup-feedback-c25-visible-state-h264-v1-loading_content-0123456789abcdef-1280x720.mp4"
        self.assertEqual(
            collector.classify_current_path(f"/data/media/{surface_name}", {}),
            "unclassified_media",
        )
        surface_collision = f"/tmp/private/{surface_name}"
        surface_collision_item = collector.sanitize_item({"path": surface_collision})
        self.assertEqual(
            collector.classify_current_path(surface_collision, surface_collision_item),
            "motion_media",
        )
        self.assertEqual(collector.classify_current_path(""), "unclassified_media")

    def test_public_surface_warmup_does_not_fail_advancing_motion_media(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = []
        for index in range(2):
            row = template.copy()
            row["seq"] = str(index + 1)
            row["rel_sec"] = str(index)
            row["current_path_kind"] = "public_surface"
            row["current_alias"] = "<media-path:surface>"
            row["path_alias"] = "<media-path:surface>"
            row["status_current_alias"] = ""
            row["status_path_alias"] = ""
            row["status_current_index"] = ""
            row["estimated_frame_number"] = "0"
            row["video_params_json"] = VALID_VIDEO_PARAMS
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["playlist_size"] = 1
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
            rows.append(row)
        for offset, frame in enumerate(("10", "40", "70", "100"), start=2):
            row = template.copy()
            row["seq"] = str(offset + 1)
            row["rel_sec"] = str(offset)
            row["current_path_kind"] = "motion_media"
            row["current_alias"] = "<media-path:motion>"
            row["path_alias"] = "<media-path:motion>"
            row["status_current_alias"] = "media-motion"
            row["status_path_alias"] = "<media-path:motion>"
            row["status_current_index"] = "0"
            row["estimated_frame_number"] = frame
            row["video_params_json"] = VALID_VIDEO_PARAMS
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["playlist_size"] = 1
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
            rows.append(row)
        fixture.write_rows(rows)

        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertEqual(result["counters"]["public_surface_samples"], 2)
        self.assertEqual(result["counters"]["motion_media_samples"], 4)

    def test_still_sidecar_accepts_available_frame_without_progress(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row["current_path_kind"] = "still_image_sidecar"
            row["estimated_frame_number"] = "0"
            row["video_params_json"] = VALID_VIDEO_PARAMS
        fixture.write_rows(rows)

        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertTrue(result["checks"]["playback_progressed"])
        self.assertTrue(result["counters"]["still_image_frame_available"])
        self.assertEqual(result["counters"]["motion_media_samples"], 0)

    def test_public_surface_alone_never_proves_playback(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row["current_path_kind"] = "public_surface"
            row["estimated_frame_number"] = "0"
            row["video_params_json"] = VALID_VIDEO_PARAMS
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "playback_progressed")
        self.assertEqual(result["counters"]["motion_media_samples"], 0)
        self.assertEqual(result["counters"]["still_image_sidecar_samples"], 0)

    def test_explicit_motion_media_still_requires_frame_progress(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row["current_path_kind"] = "motion_media"
            row["estimated_frame_number"] = "275"
            row["video_params_json"] = VALID_VIDEO_PARAMS
        fixture.write_rows(rows)

        self.assert_fails_with(fixture, "playback_progressed")

    def test_unclassified_media_alone_never_proves_playback(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row["current_path_kind"] = "unclassified_media"
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "playback_progressed")
        self.assertEqual(result["counters"]["unclassified_media_samples"], len(rows))

    def test_current_schema_missing_mpv_path_fails_closed(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row["current_path_kind"] = ""
            row["path_alias"] = ""
            row["filename_alias"] = ""
        fixture.write_rows(rows)

        result = fixture.result()
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["unclassified_media_bounded_to_startup"])
        self.assertEqual(result["counters"]["unclassified_media_samples"], len(rows))

    def test_unclassified_media_after_content_fails_closed(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(template, seq=index, kind="motion_media", alias="motion", frame=str(index * 30))
            for index in range(1, 4)
        ]
        rows.append(
            self.typed_row(template, seq=4, kind="unclassified_media", alias="unknown", frame="120")
        )
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "unclassified_media_bounded_to_startup")
        self.assertEqual(result["counters"]["unclassified_media_samples"], 1)

    def test_accepts_progressing_unclassified_forward_transition_with_recovery(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:c>"),
                ("media-a", "<media-path:a>", "0", "<media-path:c>"),
                ("media-a", "<media-path:a>", "0", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:c>"),
                ("media-c", "<media-path:c>", "2", "<media-path:c>"),
            ],
        )
        rows = fixture.rows()
        for row in rows:
            row["current_path_kind"] = "motion_media"
            row["video_params_json"] = VALID_VIDEO_PARAMS
        for row in rows[3:6]:
            row["current_path_kind"] = "unclassified_media"
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["next_item"] = {
                "alias": "media-b",
                "path_alias": "<media-path:b>",
                "duration_ms": 3900,
            }
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
        fixture.write_rows(rows)

        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertTrue(result["checks"]["unclassified_media_bounded_to_startup"])
        self.assertEqual(result["counters"]["unclassified_media_samples"], 3)
        self.assertEqual(
            result["counters"]["unclassified_media_bounded_transition_samples"],
            3,
        )

    def test_rejects_unclassified_forward_transition_without_recovery(self) -> None:
        fixture = self.with_case()
        self.write_status_mpv_alignment_rows(
            fixture,
            [
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                ("media-a", "<media-path:a>", "0", "<media-path:c>"),
                ("media-a", "<media-path:a>", "0", "<media-path:c>"),
                ("media-a", "<media-path:a>", "0", "<media-path:c>"),
            ],
        )
        rows = fixture.rows()
        for row in rows:
            row["current_path_kind"] = "motion_media"
            row["video_params_json"] = VALID_VIDEO_PARAMS
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["playlist_size"] = 2
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
        for row in rows[3:6]:
            row["current_path_kind"] = "unclassified_media"
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "unclassified_media_bounded_to_startup")
        self.assertEqual(result["counters"]["unclassified_media_samples"], 3)
        self.assertEqual(
            result["counters"]["unclassified_media_bounded_transition_samples"],
            0,
        )

    def test_rejects_unclassified_transition_with_reset_or_missing_timing(self) -> None:
        for malformed in ("frame_reset", "missing_timing"):
            with self.subTest(malformed=malformed):
                fixture = self.with_case()
                self.write_status_mpv_alignment_rows(
                    fixture,
                    [
                        ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                        ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                        ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                        ("media-a", "<media-path:a>", "0", "<media-path:c>"),
                        ("media-a", "<media-path:a>", "0", "<media-path:c>"),
                        ("media-a", "<media-path:a>", "0", "<media-path:c>"),
                        ("media-c", "<media-path:c>", "2", "<media-path:c>"),
                        ("media-c", "<media-path:c>", "2", "<media-path:c>"),
                        ("media-c", "<media-path:c>", "2", "<media-path:c>"),
                    ],
                )
                rows = fixture.rows()
                for row in rows:
                    row["current_path_kind"] = "motion_media"
                    row["video_params_json"] = VALID_VIDEO_PARAMS
                for row in rows[3:6]:
                    row["current_path_kind"] = "unclassified_media"
                if malformed == "frame_reset":
                    rows[3]["estimated_frame_number"] = "0"
                    rows[4]["estimated_frame_number"] = "30"
                    rows[5]["estimated_frame_number"] = "0"
                else:
                    for row in rows[3:6]:
                        row["rel_sec"] = ""
                fixture.write_rows(rows)

                result = self.assert_fails_with(
                    fixture,
                    "unclassified_media_bounded_to_startup",
                )
                self.assertEqual(
                    result["counters"]["unclassified_media_bounded_transition_samples"],
                    0,
                )

    def test_rejects_unclassified_transition_with_invalid_boundaries(self) -> None:
        malformed_cases = (
            "before_seq_missing",
            "after_seq_missing",
            "detached_sequence",
            "before_time_missing",
            "after_time_missing",
            "detached_timing",
        )
        for malformed in malformed_cases:
            with self.subTest(malformed=malformed):
                fixture = self.with_case()
                self.write_status_mpv_alignment_rows(
                    fixture,
                    [
                        ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                        ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                        ("media-a", "<media-path:a>", "0", "<media-path:a>"),
                        ("media-a", "<media-path:a>", "0", "<media-path:c>"),
                        ("media-a", "<media-path:a>", "0", "<media-path:c>"),
                        ("media-a", "<media-path:a>", "0", "<media-path:c>"),
                        ("media-c", "<media-path:c>", "2", "<media-path:c>"),
                        ("media-c", "<media-path:c>", "2", "<media-path:c>"),
                        ("media-c", "<media-path:c>", "2", "<media-path:c>"),
                    ],
                )
                rows = fixture.rows()
                for row in rows:
                    row["current_path_kind"] = "motion_media"
                    row["video_params_json"] = VALID_VIDEO_PARAMS
                for row in rows[3:6]:
                    row["current_path_kind"] = "unclassified_media"
                if malformed == "before_seq_missing":
                    rows[2]["seq"] = ""
                elif malformed == "after_seq_missing":
                    rows[6]["seq"] = ""
                elif malformed == "detached_sequence":
                    for offset, row in enumerate(rows[3:6], start=100):
                        row["seq"] = str(offset)
                elif malformed == "before_time_missing":
                    rows[2]["rel_sec"] = ""
                elif malformed == "after_time_missing":
                    rows[6]["rel_sec"] = ""
                else:
                    for offset, row in enumerate(rows[3:6], start=1000):
                        row["rel_sec"] = str(offset)
                fixture.write_rows(rows)

                result = self.assert_fails_with(
                    fixture,
                    "unclassified_media_bounded_to_startup",
                )
                self.assertEqual(
                    result["counters"]["unclassified_media_bounded_transition_samples"],
                    0,
                )

    def test_bounded_unclassified_startup_before_proven_content_is_allowed(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(
                template,
                seq=1,
                kind="public_surface",
                alias="surface",
                frame="0",
                status_aligned=False,
            )
        ]
        for seq in range(2, 7):
            row = self.typed_row(
                template,
                seq=seq,
                kind="unclassified_media",
                alias="candidate-warmup",
                frame=str((seq - 2) * 15),
                status_aligned=False,
            )
            row["status_playback_state"] = "waiting_for_content"
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["playback_state"] = "waiting_for_content"
            snapshot["current_item"] = None
            row["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
            rows.append(row)
        rows.extend(
            self.typed_row(template, seq=seq, kind="motion_media", alias="motion", frame=str(seq * 30))
            for seq in range(7, 11)
        )
        fixture.write_rows(rows)

        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertTrue(result["checks"]["unclassified_media_bounded_to_startup"])

    def test_two_sample_motion_episode_with_progress_is_proven(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(
                template,
                seq=index,
                kind="motion_media",
                alias="motion-a",
                frame=str(index * 30),
                playlist_size=2,
            )
            for index in range(1, 4)
        ]
        rows.extend(
            self.typed_row(
                template,
                seq=4 + offset,
                kind="motion_media",
                alias="motion-b",
                frame=frame,
                playlist_size=2,
            )
            for offset, frame in enumerate(("120", "150"))
        )
        fixture.write_rows(rows)

        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertEqual(result["counters"]["motion_media_proven_episodes"], 2)

    def test_one_sample_motion_after_sequence_gap_fails_closed(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(template, seq=index, kind="motion_media", alias="motion", frame=str(index * 30))
            for index in range(1, 4)
        ]
        rows.append(
            self.typed_row(template, seq=5, kind="motion_media", alias="motion", frame="120")
        )
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "motion_frame_progress_ok")
        self.assertEqual(result["counters"]["motion_media_failed_episodes"], 1)

    def test_terminal_one_sample_motion_after_normal_transition_fails_closed(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(
                template,
                seq=index,
                kind="motion_media",
                alias="motion-a",
                frame=str(index * 30),
                playlist_size=2,
            )
            for index in range(1, 4)
        ]
        rows.append(
            self.typed_row(
                template,
                seq=4,
                kind="motion_media",
                alias="motion-b",
                frame="120",
                playlist_size=2,
            )
        )
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "motion_frame_progress_ok")
        self.assertEqual(result["counters"]["motion_media_tolerated_boundary_episodes"], 0)

    def test_terminal_ipc_interruption_fails_terminal_health(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row.setdefault("ipc_error", "")
        terminal = rows[-1].copy()
        terminal["seq"] = str(len(rows) + 1)
        terminal["rel_sec"] = str(float(rows[-1]["rel_sec"]) + 1)
        terminal["ipc_result"] = "error"
        terminal["ipc_error"] = "missing_socket"
        terminal["estimated_frame_number"] = ""
        terminal["hwdec_current"] = ""
        terminal["vo_configured"] = ""
        rows.append(terminal)
        fixture.write_rows(rows)

        result = fixture.result()
        self.assertFalse(result["passed"])
        self.assertTrue(result["checks"]["ipc_stable_after_success"])
        self.assertFalse(result["checks"]["terminal_sample_success"])
        self.assertFalse(result["checks"]["terminal_playback_healthy"])

    def test_short_motion_after_surface_is_tolerated_only_after_later_proof(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(template, seq=index, kind="motion_media", alias="motion-a", frame=str(index * 30))
            for index in range(1, 4)
        ]
        rows.append(
            self.typed_row(
                template,
                seq=4,
                kind="public_surface",
                alias="surface",
                frame="0",
                status_aligned=False,
            )
        )
        rows.append(
            self.typed_row(template, seq=5, kind="motion_media", alias="motion-b", frame="30")
        )
        rows.extend(
            self.typed_row(template, seq=seq, kind="motion_media", alias="motion-c", frame=str(seq * 30))
            for seq in range(6, 9)
        )
        fixture.write_rows(rows)

        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertEqual(result["counters"]["motion_media_tolerated_boundary_episodes"], 1)
        self.assertTrue(result["checks"]["public_surface_recovery_ok"])

    def test_short_motion_between_proven_stills_is_bounded(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(template, seq=1, kind="still_image_sidecar", alias="still-a", frame="0"),
            self.typed_row(template, seq=2, kind="motion_media", alias="brief-motion", frame="30"),
            self.typed_row(template, seq=3, kind="still_image_sidecar", alias="still-b", frame="0"),
        ]
        fixture.write_rows(rows)

        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertEqual(result["counters"]["motion_media_tolerated_boundary_episodes"], 1)

    def test_bounded_ipc_bridge_accepts_collector_shaped_missing_socket_rows(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(template, seq=1, kind="motion_media", alias="motion-a", frame="0"),
            self.typed_row(template, seq=2, kind="motion_media", alias="motion-a", frame="30"),
            self.typed_row(template, seq=3, kind="motion_media", alias="motion-b", frame="0"),
            self.typed_row(template, seq=4, kind="unclassified_media", alias="motion-b", frame=""),
            self.typed_row(template, seq=5, kind="motion_media", alias="motion-b", frame="1"),
            self.typed_row(template, seq=6, kind="unclassified_media", alias="motion-b", frame=""),
            self.typed_row(template, seq=7, kind="motion_media", alias="motion-b", frame="2"),
            self.typed_row(template, seq=8, kind="motion_media", alias="motion-c", frame="0"),
            self.typed_row(template, seq=9, kind="motion_media", alias="motion-c", frame="30"),
        ]
        for row in rows:
            row.setdefault("ipc_error", "")
        for index in (3, 5):
            rows[index]["ipc_result"] = "error"
            rows[index]["ipc_error"] = "missing_socket"
            rows[index]["current_alias"] = ""
            rows[index]["path_alias"] = ""
            rows[index]["filename_alias"] = ""
            rows[index]["hwdec_current"] = ""
            rows[index]["vo_configured"] = ""
            rows[index]["video_params_json"] = "{}"
        fixture.write_rows(rows)

        result = fixture.result()
        self.assertTrue(result["passed"])
        self.assertTrue(result["checks"]["ipc_stable_after_success"])
        self.assertEqual(result["counters"]["motion_media_tolerated_boundary_episodes"], 3)
        self.assertEqual(result["counters"]["motion_media_failed_episodes"], 0)

    def test_invalid_frame_numbers_never_count_as_local_evidence(self) -> None:
        for invalid in ("-1", "nan", "inf"):
            with self.subTest(invalid=invalid):
                fixture = self.with_case()
                rows = fixture.rows()
                for row in rows:
                    row["current_path_kind"] = "still_image_sidecar"
                    row["estimated_frame_number"] = invalid
                    row["video_params_json"] = VALID_VIDEO_PARAMS
                fixture.write_rows(rows)

                result = self.assert_fails_with(fixture, "estimated_frame_values_valid")
                self.assertIn("still_frame_availability_ok", result["failure_reasons"])

    def test_invalid_motion_frame_sample_fails_even_with_other_progress(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        rows[-1]["estimated_frame_number"] = "inf"
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "estimated_frame_values_valid")
        self.assertEqual(result["counters"]["invalid_frame_number_samples"], 1)

    def test_episode_local_evidence_must_exist_in_one_sample(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(template, seq=index, kind="still_image_sidecar", alias="still", frame="")
            for index in range(1, 5)
        ]
        rows[0]["estimated_frame_number"] = "0"
        rows[0]["hwdec_current"] = ""
        rows[0]["vo_configured"] = "false"
        rows[0]["video_params_json"] = "{}"
        rows[1]["hwdec_current"] = "v4l2request-copy"
        rows[1]["vo_configured"] = "false"
        rows[1]["video_params_json"] = "{}"
        rows[2]["hwdec_current"] = ""
        rows[2]["vo_configured"] = "true"
        rows[2]["video_params_json"] = "{}"
        rows[3]["hwdec_current"] = ""
        rows[3]["vo_configured"] = "false"
        rows[3]["video_params_json"] = VALID_VIDEO_PARAMS
        fixture.write_rows(rows)

        self.assert_fails_with(fixture, "still_frame_availability_ok")

    def test_motion_progress_uses_only_locally_complete_samples(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(template, seq=1, kind="motion_media", alias="motion", frame="0"),
            self.typed_row(template, seq=2, kind="motion_media", alias="motion", frame="30"),
        ]
        rows[0]["hwdec_current"] = ""
        rows[0]["vo_configured"] = "false"
        rows[0]["video_params_json"] = "{}"
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "motion_frame_progress_ok")
        self.assertEqual(result["counters"]["motion_media_proven_episodes"], 0)

    def test_long_episode_cannot_collapse_into_one_tolerated_sample(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(template, seq=1, kind="motion_media", alias="motion-a", frame="0"),
            self.typed_row(template, seq=2, kind="motion_media", alias="motion-a", frame="30"),
        ]
        for seq in range(3, 9):
            row = self.typed_row(template, seq=seq, kind="motion_media", alias="motion-b", frame="0")
            if seq > 3:
                row["hwdec_current"] = ""
                row["vo_configured"] = "false"
                row["video_params_json"] = "{}"
            rows.append(row)
        rows.extend(
            [
                self.typed_row(template, seq=9, kind="motion_media", alias="motion-c", frame="0"),
                self.typed_row(template, seq=10, kind="motion_media", alias="motion-c", frame="30"),
            ]
        )
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "motion_frame_progress_ok")
        self.assertEqual(result["counters"]["motion_media_tolerated_boundary_episodes"], 0)
        self.assertEqual(result["counters"]["motion_media_failed_episodes"], 1)

    def test_repeated_frame_resets_cannot_compose_tolerated_singletons(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(template, seq=1, kind="motion_media", alias="motion-a", frame="0"),
            self.typed_row(template, seq=2, kind="motion_media", alias="motion-a", frame="30"),
        ]
        rows.extend(
            self.typed_row(
                template,
                seq=seq,
                kind="motion_media",
                alias="motion-b",
                frame=str(10 - seq),
            )
            for seq in range(3, 8)
        )
        rows.extend(
            [
                self.typed_row(template, seq=8, kind="motion_media", alias="motion-c", frame="0"),
                self.typed_row(template, seq=9, kind="motion_media", alias="motion-c", frame="30"),
            ]
        )
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "motion_frame_progress_ok")
        self.assertEqual(result["counters"]["motion_media_tolerated_boundary_episodes"], 0)
        self.assertEqual(result["counters"]["motion_media_failed_episodes"], 5)

    def test_mixed_playlist_rejects_still_without_frame(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(template, seq=index, kind="motion_media", alias="motion", frame=str(index * 30), playlist_size=2)
            for index in range(1, 4)
        ]
        rows.append(
            self.typed_row(template, seq=4, kind="still_image_sidecar", alias="still", frame="", playlist_size=2)
        )
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "still_frame_availability_ok")
        self.assertIn("playback_progressed", result["failure_reasons"])
        self.assertEqual(result["counters"]["still_image_failed_episodes"], 1)

    def test_each_still_episode_requires_its_own_frame(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(template, seq=index, kind="still_image_sidecar", alias="still-a", frame="0", playlist_size=2)
            for index in range(1, 4)
        ]
        rows.append(
            self.typed_row(template, seq=4, kind="still_image_sidecar", alias="still-b", frame="", playlist_size=2)
        )
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "still_frame_availability_ok")
        self.assertEqual(result["counters"]["still_image_episodes"], 2)
        self.assertEqual(result["counters"]["still_image_failed_episodes"], 1)

    def test_public_surface_does_not_satisfy_content_transition(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(
                template,
                seq=1,
                kind="public_surface",
                alias="surface",
                frame="0",
                playlist_size=2,
                status_aligned=False,
            )
        ]
        rows.extend(
            self.typed_row(
                template,
                seq=index,
                kind="motion_media",
                alias="only-content",
                frame=str(index * 30),
                playlist_size=2,
            )
            for index in range(2, 6)
        )
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "transitions_observed_when_required")
        self.assertEqual(result["counters"]["mpv_content_unique_aliases"], 1)
        self.assertEqual(result["counters"]["public_surface_episodes"], 1)

    def test_public_surface_breaks_motion_progress_episode(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(template, seq=index, kind="motion_media", alias="motion", frame=str(index * 30))
            for index in range(1, 4)
        ]
        rows.append(
            self.typed_row(
                template,
                seq=4,
                kind="public_surface",
                alias="surface",
                frame="0",
                status_aligned=False,
            )
        )
        rows.extend(
            self.typed_row(template, seq=index, kind="motion_media", alias="motion", frame="99")
            for index in range(5, 7)
        )
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "motion_frame_progress_ok")
        self.assertIn("playback_progressed", result["failure_reasons"])
        self.assertEqual(result["counters"]["motion_media_episodes"], 2)
        self.assertEqual(result["counters"]["motion_media_failed_episodes"], 1)

    def test_observed_public_surface_requires_its_own_frame(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(
                template,
                seq=1,
                kind="public_surface",
                alias="surface",
                frame="",
                status_aligned=False,
            )
        ]
        rows.extend(
            self.typed_row(template, seq=index, kind="motion_media", alias="motion", frame=str(index * 30))
            for index in range(2, 6)
        )
        fixture.write_rows(rows)

        result = self.assert_fails_with(fixture, "public_surface_availability_ok")
        self.assertTrue(result["checks"]["playback_progressed"])
        self.assertEqual(result["counters"]["public_surface_failed_episodes"], 1)

    def test_terminal_public_surface_requires_proven_content_recovery(self) -> None:
        fixture = self.with_case()
        template = fixture.rows()[0]
        rows = [
            self.typed_row(template, seq=index, kind="motion_media", alias="motion", frame=str(index * 30))
            for index in range(1, 4)
        ]
        surface = self.typed_row(
            template,
            seq=4,
            kind="public_surface",
            alias="recovery",
            frame="0",
            status_aligned=False,
        )
        surface["status_playback_state"] = "recovering"
        snapshot = json.loads(surface["status_snapshot_json"])
        snapshot["playback_state"] = "recovering"
        surface["status_snapshot_json"] = json.dumps(snapshot, separators=(",", ":"))
        rows.append(surface)
        fixture.write_rows(rows)

        result = fixture.result()
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["public_surface_recovery_ok"])
        self.assertFalse(result["checks"]["terminal_playback_healthy"])

    def test_rejects_status_failure_and_missing_transition(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row["current_alias"] = "media-a"
            row["path_alias"] = "<media-path:a>"
            row["status_current_alias"] = "media-a"
            row["status_path_alias"] = "<media-path:a>"
            row["status_current_index"] = "0"
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
