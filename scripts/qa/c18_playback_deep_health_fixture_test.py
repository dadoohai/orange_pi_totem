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
import c18_player_runtime_candidate_health as candidate_health


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

    def test_rejects_decode_stall_when_time_advances_but_frame_is_frozen(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            row["estimated_frame_number"] = "275"
        fixture.write_rows(rows)
        result = self.assert_fails_with(fixture, "playback_progressed")
        self.assertTrue(result["counters"]["time_pos_progressed"])
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

    def test_candidate_mode_tolerates_polling_disabled_status_only(self) -> None:
        fixture = self.with_case()
        rows = fixture.rows()
        for row in rows:
            snapshot = json.loads(row["status_snapshot_json"])
            snapshot["last_poll_error"] = "present"
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

    def test_collector_matches_candidate_ipc_argv(self) -> None:
        ipc = Path("/tmp/c18-candidate/mpv.sock")
        self.assertTrue(collector.argv_matches_ipc([f"--input-ipc-server={ipc}"], ipc))
        self.assertTrue(collector.argv_matches_ipc(["--input-ipc-server", str(ipc)], ipc))
        self.assertFalse(collector.argv_matches_ipc(["--input-ipc-server=/tmp/other.sock"], ipc))

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
