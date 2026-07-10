#!/usr/bin/env python3
"""Local tests for the C22 rapid media-fault trial harness."""

from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = REPO_ROOT / "scripts" / "board" / "c22_rapid_media_fault_trial.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("c22_rapid_media_fault_trial", HARNESS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load harness: {HARNESS_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


harness = load_harness()


class C22RapidMediaFaultTrialTest(unittest.TestCase):
    def test_parser_defaults_two_production_timers_and_tmp_output(self) -> None:
        args = harness.parse_args(["--self-test", "--output-dir", "/tmp/c22-local-test"])
        self.assertTrue(args.self_test)
        self.assertEqual(args.timers, list(harness.DEFAULT_TIMERS))
        self.assertEqual(args.service, harness.DEFAULT_SERVICE)
        self.assertEqual(harness.require_tmp_output_dir(args.output_dir), Path("/tmp/c22-local-test"))

    def test_parser_requires_exactly_two_timer_overrides(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                harness.parse_args(["--self-test", "--timer", "one.timer"])
        args = harness.parse_args(["--self-test", "--timer", "a.timer", "--timer", "b.timer"])
        self.assertEqual(args.timers, ["a.timer", "b.timer"])

    def test_output_dir_contract_rejects_data_and_tmp_root(self) -> None:
        with self.assertRaises(harness.TrialError):
            harness.require_tmp_output_dir("/data/c22")
        with self.assertRaises(harness.TrialError):
            harness.require_tmp_output_dir("/tmp")
        accepted = harness.require_tmp_output_dir("/tmp/c22-contract")
        self.assertTrue(str(accepted).startswith("/tmp/"))

    def test_config_contract_uses_only_tmp_and_localhost(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c22-config-contract-", dir="/tmp") as tmp:
            work = Path(tmp) / "work"
            cfg = harness.build_trial_config(
                work_dir=work,
                api_url="http://127.0.0.1:54321/api/search",
                mpv_path="/opt/totem/bin/totem-mpv-hwdecode",
                ffmpeg_path="/usr/bin/ffmpeg",
                ffprobe_path="/usr/bin/ffprobe",
            )
        for key in ("cache_dir", "state_dir", "ipc_path", "runtime_dir", "status_file", "log_file", "mpv_log_file"):
            self.assertTrue(str(cfg[key]).startswith("/tmp/"), key)
        serialized = json.dumps(cfg, sort_keys=True)
        self.assertNotIn("/data/config", serialized)
        self.assertNotIn("/data/media", serialized)
        self.assertTrue(cfg["api_url"].startswith("http://127.0.0.1:"))
        self.assertFalse(cfg["telemetry_enabled"])
        self.assertFalse(cfg["config_ui_enabled"])
        self.assertFalse(cfg["sync_enabled"])

    def test_config_rejects_non_localhost_backend(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c22-config-contract-", dir="/tmp") as tmp:
            with self.assertRaises(harness.TrialError):
                harness.build_trial_config(
                    work_dir=Path(tmp) / "work",
                    api_url="https://api.example.invalid/search",
                    mpv_path="/opt/totem/bin/totem-mpv-hwdecode",
                    ffmpeg_path="/usr/bin/ffmpeg",
                    ffprobe_path="/usr/bin/ffprobe",
                )

    def test_retaining_lkg_predicate_requires_active_playback(self) -> None:
        predicate = harness.retaining_lkg_state_is("api_error_retaining_last_known_good")
        transitioning = {
            "playlist_update_state": "api_error_retaining_last_known_good",
            "playback_state": "preparing_first_frame",
            "first_frame_ready": False,
            "playlist_size": 3,
            "mpv_running": True,
            "current_item": {"path_alias": "<path:a>"},
        }
        self.assertFalse(predicate(transitioning))
        transitioning.update(playback_state="playing", first_frame_ready=True)
        self.assertTrue(predicate(transitioning))

    def test_systemd_controller_restores_only_previously_active_units(self) -> None:
        runner = harness.FakeSystemctlRunner()
        controller = harness.SystemdController(harness.DEFAULT_SERVICE, list(harness.DEFAULT_TIMERS), runner=runner)
        controller.quiesce()
        self.assertEqual(controller.after_stop[harness.DEFAULT_SERVICE].active_state, "inactive")
        self.assertEqual(controller.after_stop[harness.DEFAULT_TIMERS[0]].active_state, "inactive")
        restoration = controller.restore()
        self.assertTrue(restoration["restored_active_state"])
        self.assertIn(["systemctl", "stop", harness.DEFAULT_TIMERS[0]], runner.calls)
        self.assertIn(["systemctl", "stop", harness.DEFAULT_TIMERS[1]], runner.calls)
        self.assertIn(["systemctl", "stop", harness.DEFAULT_SERVICE], runner.calls)
        self.assertIn(["systemctl", "start", harness.DEFAULT_SERVICE], runner.calls)
        self.assertIn(["systemctl", "start", harness.DEFAULT_TIMERS[0]], runner.calls)
        self.assertNotIn(["systemctl", "start", harness.DEFAULT_TIMERS[1]], runner.calls)
        self.assertEqual(controller.nrestarts_delta(), 0)

    def test_post_restore_health_retries_transient_missing_ipc(self) -> None:
        class FakeSystemd:
            service = harness.DEFAULT_SERVICE
            initial = {service: harness.UnitState(service, active_state="active")}

            @staticmethod
            def unit_state(unit: str) -> object:
                return harness.UnitState(unit, active_state="active")

        with tempfile.TemporaryDirectory(prefix="c22-restore-health-", dir="/tmp") as tmp:
            status_path = Path(tmp) / "status.json"
            status_path.write_text(
                json.dumps({
                    "playback_state": "playing",
                    "first_frame_ready": True,
                    "playlist_size": 1,
                    "mpv_running": True,
                    "current_item": {"path": "/tmp/media.mp4"},
                }),
                encoding="utf-8",
            )
            old_status_path = harness.DEFAULT_STATUS_FILE
            old_ipc = harness.ipc_query_many
            old_kms = harness.kms_capture
            old_sleep = harness.time.sleep
            calls = {"ipc": 0}

            def fake_ipc(*_args: object, **_kwargs: object) -> dict:
                calls["ipc"] += 1
                if calls["ipc"] == 1:
                    return {"result": "error", "error": "missing_socket", "values": {}, "prop_errors": {}}
                return {"result": "success", "error": "", "values": {}, "prop_errors": {}}

            harness.DEFAULT_STATUS_FILE = status_path
            harness.ipc_query_many = fake_ipc
            harness.kms_capture = lambda *_args, **_kwargs: {"result": "success", "error": ""}
            harness.time.sleep = lambda _seconds: None
            try:
                result = harness.collect_post_restore_health(FakeSystemd(), 0, "/usr/bin/ffmpeg", timeout_sec=1)
            finally:
                harness.DEFAULT_STATUS_FILE = old_status_path
                harness.ipc_query_many = old_ipc
                harness.kms_capture = old_kms
                harness.time.sleep = old_sleep

        self.assertTrue(result["passed"], result)
        self.assertGreaterEqual(calls["ipc"], 2)

    def test_sanitizers_remove_status_paths_and_urls(self) -> None:
        raw = {
            "playback_state": "playing",
            "playlist_update_state": "playlist_applied",
            "playlist_size": 1,
            "current_item": {
                "url": "http://127.0.0.1:1234/media/private.mp4",
                "path": "/tmp/c22/media/private.mp4",
                "source_path": "/tmp/c22/media/private.png",
                "campaign_name": "private name",
                "duration_ms": 1200,
            },
        }
        safe = harness.sanitize_status(raw)
        serialized = json.dumps(safe, sort_keys=True)
        self.assertNotIn("/tmp/c22/media/private.mp4", serialized)
        self.assertNotIn("http://127.0.0.1:1234/media/private.mp4", serialized)
        self.assertIn("path_alias", serialized)
        self.assertIn("source_path_alias", serialized)

    def test_continuous_kms_sequence_measures_black_streaks(self) -> None:
        black = bytes([0, 0, 0, 255] * 2)
        bright = bytes([255, 255, 255, 255] * 2)
        original_run = harness.subprocess.run
        harness.subprocess.run = lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [],
            0,
            stdout=bright + black + black + bright,
            stderr=b"",
        )
        try:
            result = harness.kms_capture_sequence("/usr/bin/ffmpeg", 1.0, fps=10, width=2, height=1)
        finally:
            harness.subprocess.run = original_run

        self.assertEqual(result["result"], "success")
        self.assertEqual(result["frames"], 4)
        self.assertEqual(result["black_frames"], 2)
        self.assertEqual(result["max_consecutive_black_frames"], 2)
        self.assertEqual(result["max_black_duration_ms"], 200)

    def test_privacy_scan_blocks_real_config_media_and_external_backend(self) -> None:
        for payload in (
            {"path": "/data/config/config.json"},
            {"path": "/data/media/asset.mp4"},
            {"api": "https://api.example.invalid/search"},
            {"api_key": "secret"},
        ):
            with self.assertRaises(harness.PrivacyError):
                harness.assert_public_json_safe(payload)
        harness.assert_public_json_safe({"api": "http://127.0.0.1:1234/api/search", "path": "<path:abc>"})

    def test_protected_metadata_ignores_only_expected_operational_mtime(self) -> None:
        operational = harness.alias("/data/player-runtime/state.json", "path")
        strict = harness.alias("/data/config", "path")
        before = {
            operational: {"exists": True, "size": 10, "mtime_ns": 1},
            strict: {"exists": True, "size": 20, "mtime_ns": 1},
        }
        after = {
            operational: {"exists": True, "size": 10, "mtime_ns": 2},
            strict: {"exists": True, "size": 20, "mtime_ns": 1},
        }
        self.assertTrue(harness.protected_metadata_unchanged(before, after))
        after[strict]["mtime_ns"] = 2
        self.assertFalse(harness.protected_metadata_unchanged(before, after))

    def test_evaluate_trial_contract_passes_self_test_samples(self) -> None:
        runner = harness.FakeSystemctlRunner()
        controller = harness.SystemdController(harness.DEFAULT_SERVICE, list(harness.DEFAULT_TIMERS), runner=runner)
        controller.quiesce()
        restoration = controller.restore()
        scenario_results = {
            name: {"condition_met": True}
            for name in ("mixed", "api_500", "empty_playlist", "truncated_download", "sidecar_rebuild", "recovery")
        }
        scenario_results["mixed"]["continuous_kms"] = {
            "result": "success",
            "frames": 120,
            "unique_frame_hashes": 3,
            "black_frames": 0,
            "max_black_duration_ms": 0,
        }
        recovery_good = next(
            sample["status"] for sample in harness.make_self_test_samples()
            if sample["scenario"] == "recovery"
        )
        scenario_results["recovery"]["condition_status"] = recovery_good
        scenario_results["recovery"]["final_status"] = {
            **recovery_good,
            "playback_state": "preparing_first_frame",
            "first_frame_ready": False,
        }
        result = harness.evaluate_trial(
            samples=harness.make_self_test_samples(),
            scenario_results=scenario_results,
            systemd=controller,
            restoration=restoration,
            forbidden_before={"p": {"exists": False}},
            forbidden_after={"p": {"exists": False}},
            sidecar={"rebuilt": True, "ffprobe_h264_ok": True, "first_frame_decode_ok": True},
            process_stop={"method": "sigterm", "returncode": 0},
            post_restore_health={"passed": True},
        )
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["failure_reasons"], [])
        self.assertGreaterEqual(result["counters"]["mixed_mpv_unique_aliases"], 3)
        self.assertEqual(result["counters"]["kms_raw_black_valid_media_samples"], 0)

    def test_evaluate_trial_rejects_black_kms_and_missing_recovery(self) -> None:
        runner = harness.FakeSystemctlRunner()
        controller = harness.SystemdController(harness.DEFAULT_SERVICE, list(harness.DEFAULT_TIMERS), runner=runner)
        controller.quiesce()
        restoration = controller.restore()
        samples = harness.make_self_test_samples()
        blackened = 0
        for sample in samples:
            if sample["scenario"] == "mixed":
                sample["kms"]["raw_black"] = True
                sample["kms"]["luma_avg"] = 0.0
                blackened += 1
                if blackened == 2:
                    break
        scenario_results = {
            name: {"condition_met": True}
            for name in ("mixed", "api_500", "empty_playlist", "truncated_download", "sidecar_rebuild", "recovery")
        }
        scenario_results["mixed"]["continuous_kms"] = {
            "result": "success",
            "frames": 120,
            "unique_frame_hashes": 3,
            "black_frames": 0,
            "max_black_duration_ms": 0,
        }
        result = harness.evaluate_trial(
            samples=samples,
            scenario_results=scenario_results,
            systemd=controller,
            restoration=restoration,
            forbidden_before={"p": {"exists": False}},
            forbidden_after={"p": {"exists": False}},
            sidecar={"rebuilt": True, "ffprobe_h264_ok": True, "first_frame_decode_ok": True},
            process_stop={"method": "sigterm", "returncode": 0},
            post_restore_health={"passed": True},
        )
        self.assertFalse(result["passed"])
        self.assertIn("no_persistent_raw_black_samples", result["failure_reasons"])

    def test_evaluate_trial_rejects_stale_status_without_active_lkg_playback(self) -> None:
        runner = harness.FakeSystemctlRunner()
        controller = harness.SystemdController(harness.DEFAULT_SERVICE, list(harness.DEFAULT_TIMERS), runner=runner)
        controller.quiesce()
        restoration = controller.restore()
        scenario_results = {
            name: {"condition_met": True}
            for name in ("mixed", "api_500", "empty_playlist", "truncated_download", "sidecar_rebuild", "recovery")
        }
        scenario_results["mixed"]["continuous_kms"] = {
            "result": "success",
            "frames": 120,
            "unique_frame_hashes": 3,
            "black_frames": 0,
            "max_black_duration_ms": 0,
        }
        expected = {
            "api_500": ("api_error_retaining_last_known_good", "api_error"),
            "empty_playlist": ("api_empty_retaining_last_known_good", "api_empty_playlist"),
            "truncated_download": (
                "download_incomplete_retaining_last_known_good",
                "playlist_download_incomplete",
            ),
        }
        for scenario, (state, reason) in expected.items():
            stopped_status = {
                "playlist_update_state": state,
                "content_stale": True,
                "content_stale_reason": reason,
                "playlist_size": 0,
                "playback_state": "waiting_for_media",
                "first_frame_ready": False,
                "mpv_running": False,
                "current_item": {},
            }
            scenario_results[scenario]["condition_status"] = stopped_status
            scenario_results[scenario]["final_status"] = dict(stopped_status)

        result = harness.evaluate_trial(
            samples=harness.make_self_test_samples(),
            scenario_results=scenario_results,
            systemd=controller,
            restoration=restoration,
            forbidden_before={"p": {"exists": False}},
            forbidden_after={"p": {"exists": False}},
            sidecar={"rebuilt": True, "ffprobe_h264_ok": True, "first_frame_decode_ok": True},
            process_stop={"method": "sigterm", "returncode": 0},
            post_restore_health={"passed": True},
        )

        self.assertFalse(result["passed"])
        for scenario in expected:
            self.assertIn(f"{scenario}_lkg_playback_remains_active", result["failure_reasons"])

    def test_evaluate_trial_rejects_frequent_nonconsecutive_status_mpv_mismatch(self) -> None:
        runner = harness.FakeSystemctlRunner()
        controller = harness.SystemdController(harness.DEFAULT_SERVICE, list(harness.DEFAULT_TIMERS), runner=runner)
        controller.quiesce()
        restoration = controller.restore()
        samples = harness.make_self_test_samples()
        for index in (0, 2, 4, 9, 10):
            samples[index]["ipc"]["path_alias"] = f"<path:mismatch-{index}>"
        scenario_results = {
            name: {"condition_met": True}
            for name in ("mixed", "api_500", "empty_playlist", "truncated_download", "sidecar_rebuild", "recovery")
        }
        scenario_results["mixed"]["continuous_kms"] = {
            "result": "success",
            "frames": 120,
            "unique_frame_hashes": 3,
            "black_frames": 0,
            "max_black_duration_ms": 0,
        }

        result = harness.evaluate_trial(
            samples=samples,
            scenario_results=scenario_results,
            systemd=controller,
            restoration=restoration,
            forbidden_before={"p": {"exists": False}},
            forbidden_after={"p": {"exists": False}},
            sidecar={"rebuilt": True, "ffprobe_h264_ok": True, "first_frame_decode_ok": True},
            process_stop={"method": "sigterm", "returncode": 0},
            post_restore_health={"passed": True},
        )

        self.assertFalse(result["passed"])
        self.assertIn("status_mpv_aligned", result["failure_reasons"])
        self.assertLess(result["counters"]["status_mpv_mismatch_allowed"], 5)
        self.assertLessEqual(result["counters"]["status_mpv_max_consecutive_mismatch"], 2)

    def test_evaluate_trial_reports_drm_format_change_as_measurement_warning(self) -> None:
        runner = harness.FakeSystemctlRunner()
        controller = harness.SystemdController(harness.DEFAULT_SERVICE, list(harness.DEFAULT_TIMERS), runner=runner)
        controller.quiesce()
        restoration = controller.restore()
        scenario_results = {
            name: {"condition_met": True}
            for name in ("mixed", "api_500", "empty_playlist", "truncated_download", "sidecar_rebuild", "recovery")
        }
        scenario_results["mixed"]["continuous_kms"] = {
            "result": "error",
            "error": "continuous_kmsgrab_failed",
        }
        result = harness.evaluate_trial(
            samples=harness.make_self_test_samples(),
            scenario_results=scenario_results,
            systemd=controller,
            restoration=restoration,
            forbidden_before={"p": {"exists": False}},
            forbidden_after={"p": {"exists": False}},
            sidecar={"rebuilt": True, "ffprobe_h264_ok": True, "first_frame_decode_ok": True},
            process_stop={"method": "sigterm", "returncode": 0},
            post_restore_health={"passed": True},
        )
        self.assertTrue(result["passed"], result)
        self.assertIn("continuous_kms_unavailable_across_drm_format_change", result["warnings"])

    def test_cli_self_test_outputs_contract_json(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(HARNESS_PATH), "--self-test"],
            cwd=str(REPO_ROOT),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema"], harness.SELF_TEST_SCHEMA)
        self.assertTrue(payload["passed"], payload)
        serialized = json.dumps(payload, sort_keys=True)
        self.assertNotIn("/data/config", serialized)
        self.assertNotIn("/data/media", serialized)
        self.assertNotIn("https://api.", serialized)


if __name__ == "__main__":
    unittest.main(verbosity=2)
