#!/usr/bin/env python3
"""C18 player-runtime static governance checks.

This is an offline guard for the governed C18 player snapshot. It does not
enable player OTA and must stay separate from the ordinary totem-core OTA path.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYER_DIR = REPO_ROOT / "player-runtime" / "kiosky-player"
KIOSK_PATH = PLAYER_DIR / "kiosk.py"
SOURCE_PATH = PLAYER_DIR / "SOURCE.json"
DERIVE_C18_PATH = REPO_ROOT / "scripts" / "build" / "derive_c18_image_lab_1_hwdecode.py"
RELEASE_GATE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_ota_release_gate.py"
LAB_THAW_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_lab_thaw.py"
CANDIDATE_HEALTH_PATH = REPO_ROOT / "scripts" / "board" / "c18_player_runtime_candidate_health.py"
PLAYER_RUNTIME_BUILDER_PATH = REPO_ROOT / "scripts" / "deploy" / "build_player_runtime_release_package.sh"
UPDATECTL_PATH = REPO_ROOT / "scripts" / "board" / "totem_updatectl.py"
PLAYER_RUNTIME_RELEASE_GATE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_release_gate.py"
PLAYER_RUNTIME_EVIDENCE_GATE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_evidence_gate.py"
PLAYER_RUNTIME_COLDBOOT_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_m6_coldboot_trial.py"
INNER_LAUNCHER_PATH = REPO_ROOT / "scripts" / "board" / "kiosky_service_launcher.sh"
CONFIG_CONTRACT_VALIDATOR_PATH = REPO_ROOT / "scripts" / "board" / "totem_config_contract_validate.py"
STATUS_AGGREGATE_PATH = REPO_ROOT / "scripts" / "board" / "totem_status_aggregate.py"
CURRENT_GOLDEN_PATH = REPO_ROOT / "docs" / "evidence" / "c18-update-validation" / "current-golden.json"
CURRENT_GOLDEN = json.loads(CURRENT_GOLDEN_PATH.read_text(encoding="utf-8"))
C18_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
EXPECTED_SNAPSHOT_SHA256 = "7b67003a450902ddd4ea5d8c9f11653a43b9e55df0c45ccd4496be08188df3f0"
EXPECTED_UPSTREAM_SHA256 = "38ecb0de3bfa4367d3ed61a173d2eb3210659026b8104f5c058881ca84470072"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source() -> dict:
    return json.loads(SOURCE_PATH.read_text(encoding="utf-8"))


def load_kiosk_module():
    spec = importlib.util.spec_from_file_location("c18_kiosk_under_test", KIOSK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load kiosk.py spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_status_aggregate_module():
    board_dir = str(STATUS_AGGREGATE_PATH.parent)
    sys.path.insert(0, board_dir)
    try:
        spec = importlib.util.spec_from_file_location("c18_status_aggregate_under_test", STATUS_AGGREGATE_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError("failed to load totem_status_aggregate.py spec")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(board_dir)


@contextlib.contextmanager
def stub_startup_surface_video(kiosk):
    original = kiosk.write_startup_feedback_video

    def write_stub(cfg: dict, state: str = "waiting_for_content") -> str:
        path = Path(kiosk.startup_feedback_video_path(cfg, state))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"c25-test-surface")
        return str(path)

    kiosk.write_startup_feedback_video = write_stub
    try:
        yield
    finally:
        kiosk.write_startup_feedback_video = original


class FakeProc:
    def __init__(self, wait_results: list[object]) -> None:
        self.pid = 1234
        self.wait_results = list(wait_results)
        self.wait_timeouts: list[float] = []
        self._poll: int | None = None

    def poll(self) -> int | None:
        return self._poll

    def wait(self, timeout: float) -> int:
        self.wait_timeouts.append(timeout)
        result = self.wait_results.pop(0)
        if result == "timeout":
            raise subprocess.TimeoutExpired(["mpv"], timeout)
        self._poll = int(result)
        return self._poll

    def terminate(self) -> None:
        self._poll = -15

    def kill(self) -> None:
        self._poll = -9


class FakePreloadMPV:
    def __init__(
        self,
        *,
        playlist_next: bool = True,
        playlist_remove: bool = True,
        wait_results: list[bool] | None = None,
    ) -> None:
        self.playlist_next_result = playlist_next
        self.playlist_remove_result = playlist_remove
        self.wait_results = list(wait_results if wait_results is not None else [True, True])
        self.removed: list[int] = []

    def playlist_next(self) -> bool:
        return self.playlist_next_result

    def playlist_remove(self, index: int) -> bool:
        self.removed.append(index)
        return self.playlist_remove_result

    def wait_for_current_path(self, _path: str) -> bool:
        if not self.wait_results:
            return False
        return self.wait_results.pop(0)

    def generation(self) -> int:
        return 1

    def pid(self) -> int:
        return 1234


class FakeMismatchMPV:
    def __init__(self) -> None:
        self.load_calls: list[str] = []
        self.restart_reasons: list[str] = []
        self.append_calls: list[str] = []

    def ensure_running(self) -> None:
        return None

    def generation(self) -> int:
        return 1

    def wait_for_current_path(self, _path: str, timeout: float | None = None) -> bool:
        return False

    def wait_for_local_frame_evidence(self, _path: str, **_kwargs: object) -> bool:
        return False

    def process_guard(self):
        return contextlib.nullcontext()

    def load_file(self, path: str, alias: str = "") -> bool:
        self.load_calls.append(f"{path}|{alias}")
        return True

    def seek_absolute(self, _seconds: float) -> bool:
        return True

    def set_property(self, _name: str, _value: object) -> bool:
        return True

    def append_file(self, path: str) -> bool:
        self.append_calls.append(path)
        return True

    def restart(self, reason: str = "restart") -> None:
        self.restart_reasons.append(reason)

    def is_running(self) -> bool:
        return True

    def pid(self) -> int:
        return 1234


class FakeSurfaceMPV:
    def __init__(self) -> None:
        self.current_generation = 1
        self.load_calls: list[str] = []
        self.current_path_matches = True

    def generation(self) -> int:
        return self.current_generation

    def ensure_running(self) -> None:
        return None

    def is_running(self) -> bool:
        return True

    def pid(self) -> int:
        return 1234

    def load_file(self, path: str, alias: str = "") -> bool:
        self.load_calls.append(f"{path}|{alias}")
        return True

    def wait_for_local_frame_evidence(self, _path: str, **_kwargs: object) -> bool:
        return self.current_path_matches

    def wait_for_current_path(self, _path: str, timeout: float | None = None) -> bool:
        return self.current_path_matches

    def process_guard(self):
        return contextlib.nullcontext()


class FakeGenerationRecoveryMPV:
    def __init__(self) -> None:
        self.current_generation = 1
        self.running = True
        self.load_calls: list[str] = []
        self.frame_checks = 0

    def ensure_running(self) -> None:
        if not self.running:
            self.running = True
            self.current_generation += 1

    def is_running(self) -> bool:
        return self.running

    def generation(self) -> int:
        return self.current_generation

    def wait_for_current_path(self, _path: str, timeout: float | None = None) -> bool:
        return True

    def wait_for_local_frame_evidence(self, path: str, **_kwargs: object) -> bool:
        if "startup-feedback" in path:
            return True
        self.frame_checks += 1
        if self.frame_checks == 1:
            self.running = False
        return True

    def process_guard(self):
        return contextlib.nullcontext()

    def load_file(self, path: str, alias: str = "") -> bool:
        self.load_calls.append(f"{path}|{alias}")
        return True

    def seek_absolute(self, _seconds: float) -> bool:
        return True

    def set_property(self, _name: str, _value: object) -> bool:
        return True

    def append_file(self, _path: str) -> bool:
        return True

    def pid(self) -> int:
        return 1234


class FakeStillFrameMPV:
    def __init__(self) -> None:
        self.load_calls: list[str] = []
        self.frame_require_progress: list[bool] = []

    def ensure_running(self) -> None:
        return None

    def is_running(self) -> bool:
        return True

    def generation(self) -> int:
        return 1

    def wait_for_current_path(self, _path: str, timeout: float | None = None) -> bool:
        return True

    def wait_for_local_frame_evidence(self, path: str, **kwargs: object) -> bool:
        if "startup-feedback" in path:
            return True
        require_progress = bool(kwargs.get("require_progress", True))
        self.frame_require_progress.append(require_progress)
        return not require_progress

    def process_guard(self):
        return contextlib.nullcontext()

    def load_file(self, path: str, alias: str = "") -> bool:
        self.load_calls.append(f"{path}|{alias}")
        return True

    def seek_absolute(self, _seconds: float) -> bool:
        return True

    def set_property(self, _name: str, _value: object) -> bool:
        return True

    def append_file(self, _path: str) -> bool:
        return True

    def pid(self) -> int:
        return 1234


class StopOnMismatchStatus:
    def __init__(self, stop_event: threading.Event) -> None:
        self.start_time = time.time()
        self.stop_event = stop_event
        self.updates: list[dict[str, object]] = []
        self._data: dict[str, object] = {}

    def update(self, **kwargs: object) -> None:
        self.updates.append(dict(kwargs))
        self._data.update(kwargs)
        if kwargs.get("content_state") == "media_path_mismatch":
            self.stop_event.set()

    def snapshot(self) -> dict[str, object]:
        return dict(self._data)


class StopOnRecoveredStatus(StopOnMismatchStatus):
    def __init__(self, stop_event: threading.Event) -> None:
        super().__init__(stop_event)
        self.saw_recovery = False

    def update(self, **kwargs: object) -> None:
        super().update(**kwargs)
        if kwargs.get("error_code") == "player_recovering":
            self.saw_recovery = True
        if self.saw_recovery and kwargs.get("content_state") == "playing":
            self.stop_event.set()


class StopOnPlayingStatus(StopOnMismatchStatus):
    def update(self, **kwargs: object) -> None:
        super().update(**kwargs)
        if kwargs.get("content_state") == "playing":
            self.stop_event.set()


class FakeDeadMPV:
    def __init__(self) -> None:
        self.ensure_calls = 0

    def ensure_running(self) -> None:
        self.ensure_calls += 1

    def is_running(self) -> bool:
        return False

    def generation(self) -> int:
        return 0

    def pid(self) -> None:
        return None


class C18PlayerRuntimeStaticTest(unittest.TestCase):
    def test_source_metadata_is_frozen_not_ota_release(self) -> None:
        data = source()
        self.assertEqual(data["schema"], "dadooh.c18.player_runtime.source.v1")
        self.assertEqual(data["component"], "player-runtime")
        self.assertIs(data["apply_enabled"], False)
        self.assertEqual(data["snapshot"]["path"], "player-runtime/kiosky-player/kiosk.py")
        self.assertEqual(data["snapshot"]["sha256"], EXPECTED_SNAPSHOT_SHA256)
        self.assertEqual(data["upstream"]["repo"], "dadoohai/kiosky-player")
        self.assertEqual(data["upstream"]["sha256_before_c18_patch"], EXPECTED_UPSTREAM_SHA256)
        self.assertEqual(data["image_source"]["image_tag"], "c18-hwdecode-lab-1i")
        self.assertIn("not an OTA player release", " ".join(data["notes"]))
        patches = {patch["field"]: patch for patch in data["patches"]}
        self.assertEqual(patches["DEFAULT_CONFIG.mpv_path"]["to"], C18_WRAPPER)
        self.assertEqual(
            patches["MPVController._stop_locked"]["to"],
            "request MPV IPC quit, including fresh IPC fallback, before signal fallback",
        )
        self.assertEqual(
            patches["MPVController.load_file/preload_next"]["to"],
            "fresh IPC path verification before trusting loadfile or preloaded playlist-next",
        )
        self.assertEqual(
            patches["MPVController fresh IPC transport"]["to"],
            "startup probe closes immediately and every control command uses a serialized fresh request/response",
        )
        self.assertEqual(patches["DEFAULT_CONFIG.preload_next"]["to"], False)
        self.assertEqual(
            patches["download_media/media_items_from_saved/media_items_from_cache"]["to"],
            "still images are prepared as local H.264 MP4 sidecars before playlist admission",
        )

    def test_snapshot_sha_matches_source_metadata(self) -> None:
        self.assertEqual(sha256_file(KIOSK_PATH), source()["snapshot"]["sha256"])
        self.assertEqual(sha256_file(KIOSK_PATH), EXPECTED_SNAPSHOT_SHA256)

    def test_snapshot_compiles_and_has_no_debugfs_banner(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c18-player-runtime-pycompile-") as tmp:
            py_compile.compile(str(KIOSK_PATH), cfile=str(Path(tmp) / "kiosk.pyc"), doraise=True)
        text = KIOSK_PATH.read_text(encoding="utf-8")
        self.assertNotIn("debugfs 1.", text)
        self.assertNotIn("debugfs:", text)

    def test_snapshot_preserves_c18_hwdecode_wrapper_contract(self) -> None:
        text = KIOSK_PATH.read_text(encoding="utf-8")
        self.assertIn(f'"mpv_path": "{C18_WRAPPER}",', text)
        self.assertNotIn('"mpv_path": "mpv"', text)
        self.assertNotIn('"mpv_path": "/usr/bin/mpv"', text)
        self.assertIn('cfg["mpv_path"]', text)
        self.assertIn('"--hwdec-codecs=h264,mpeg4,mpeg2video"', text)
        self.assertIn('"--no-osc"', text)
        self.assertIn('"preload_next": False,', text)
        self.assertIn('"loadfile", path, "replace"', text)
        self.assertIn("def wait_for_current_path", text)
        self.assertIn("MPV loadfile verification failed", text)
        self.assertIn("MPV playlist-next verification failed", text)
        self.assertIn("MPV playlist-next post-cleanup verification failed", text)

    def test_public_surfaces_use_product_copy_without_internal_causes(self) -> None:
        kiosk = load_kiosk_module()
        cases = {
            "waiting_for_content": "Carregando conteúdo",
            "error_no_content": "Conteúdo ainda não disponível",
            "error_player_start": "Recuperando a exibição",
        }
        for state, expected_title in cases.items():
            svg = kiosk.build_startup_feedback_svg(state)
            self.assertIn(expected_title, svg)
            self.assertIn('data-visual-system="c25-visible-state-ui.v1"', svg)
            self.assertNotIn("STATUS:", svg)
            self.assertNotIn(state, svg)
            self.assertNotRegex(svg.lower(), r"\b(api|cache|internet|playlist|mpv)\b")
            portrait_svg = kiosk.build_startup_feedback_svg(state, width=720, height=1280)
            self.assertIn('viewBox="0 0 720 1280"', portrait_svg)
            self.assertIn(expected_title.split()[0], portrait_svg)
            self.assertNotRegex(portrait_svg.lower(), r"\b(api|cache|internet|playlist|mpv)\b")
            video_filter = kiosk.build_startup_feedback_video_filter(state)
            self.assertIn(expected_title, video_filter)
            self.assertNotRegex(video_filter.lower(), r"\b(api|cache|internet|playlist|mpv)\b")

    def test_public_surface_video_builder_emits_atomic_h264_contract(self) -> None:
        kiosk = load_kiosk_module()
        with tempfile.TemporaryDirectory(prefix="c18-public-surface-video-") as tmp:
            cfg = {
                "runtime_dir": tmp,
                "rotation_deg": 0,
                "startup_feedback_render_timeout_sec": 999,
            }
            commands: list[list[str]] = []
            timeouts: list[object] = []
            original_run = kiosk.subprocess.run
            original_probe = kiosk.probe_startup_feedback_video

            class Result:
                returncode = 0
                stdout = b""
                stderr = b""

            def fake_run(command: list[str], **_kwargs: object) -> Result:
                commands.append(command)
                timeouts.append(_kwargs.get("timeout"))
                Path(command[-1]).write_bytes(b"h264-mp4")
                return Result()

            kiosk.subprocess.run = fake_run
            kiosk.probe_startup_feedback_video = lambda *_args, **_kwargs: (True, "ok")
            try:
                path = kiosk.write_startup_feedback_video(cfg, "waiting_for_content")
                cached = kiosk.write_startup_feedback_video(cfg, "waiting_for_content")
            finally:
                kiosk.subprocess.run = original_run
                kiosk.probe_startup_feedback_video = original_probe

        self.assertEqual(path, cached)
        self.assertEqual(len(commands), 1)
        self.assertEqual(timeouts, [10])
        command = commands[0]
        self.assertIn("libx264", command)
        self.assertIn("-frames:v", command)
        self.assertIn("drawtext=", command[command.index("-vf") + 1])
        self.assertIn("c25-visible-state-h264-v1", path)
        self.assertTrue(path.endswith("-1280x720.mp4"))

    def test_public_surface_cache_identity_tracks_renderer_contract(self) -> None:
        kiosk = load_kiosk_module()
        cfg = {"runtime_dir": "/tmp/c18-surface-identity", "rotation_deg": 0}
        state_paths = {
            kiosk.startup_feedback_video_path(cfg, state)
            for state in ("waiting_for_content", "error_no_content", "error_player_start")
        }
        self.assertEqual(len(state_paths), 3)
        original_title = kiosk.PUBLIC_SURFACE_PRESETS["loading_content"]["title"]
        first = kiosk.startup_feedback_video_path(cfg, "waiting_for_content")
        try:
            kiosk.PUBLIC_SURFACE_PRESETS["loading_content"]["title"] = "Copy alterada"
            second = kiosk.startup_feedback_video_path(cfg, "waiting_for_content")
        finally:
            kiosk.PUBLIC_SURFACE_PRESETS["loading_content"]["title"] = original_title
        self.assertNotEqual(first, second)

    def test_public_surface_probe_is_strict_even_when_media_probe_is_disabled(self) -> None:
        kiosk = load_kiosk_module()
        original_run = kiosk.subprocess.run
        commands: list[list[str]] = []
        timeouts: list[object] = []

        class Result:
            returncode = 0
            stdout = json.dumps(
                {
                    "streams": [
                        {
                            "codec_type": "video",
                            "codec_name": "h264",
                            "width": 1280,
                            "height": 720,
                            "pix_fmt": "yuv420p",
                            "nb_read_frames": "1",
                        }
                    ]
                }
            ).encode("utf-8")
            stderr = b""

        def fake_run(command: list[str], **kwargs: object) -> Result:
            commands.append(command)
            timeouts.append(kwargs.get("timeout"))
            return Result()

        kiosk.subprocess.run = fake_run
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4") as surface:
                surface.write(b"h264")
                surface.flush()
                valid, reason = kiosk.probe_startup_feedback_video(
                    {
                        "media_probe_enabled": False,
                        "startup_feedback_render_timeout_sec": 999,
                    },
                    surface.name,
                    width=1280,
                    height=720,
                )
        finally:
            kiosk.subprocess.run = original_run

        self.assertTrue(valid, reason)
        self.assertEqual(len(commands), 2)
        self.assertEqual(timeouts, [4, 4])

    def test_public_surface_probe_rejects_contract_mismatches(self) -> None:
        kiosk = load_kiosk_module()
        original_run = kiosk.subprocess.run
        payload: dict[str, object] = {}

        class Result:
            returncode = 0
            stderr = b""

            @property
            def stdout(self) -> bytes:
                return json.dumps(payload).encode("utf-8")

        kiosk.subprocess.run = lambda *_args, **_kwargs: Result()
        valid_video = {
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1280,
            "height": 720,
            "pix_fmt": "yuv420p",
            "nb_read_frames": "1",
        }
        cases = {
            "surface_contract_dimensions_mismatch": [{**valid_video, "width": 640}],
            "surface_contract_pixel_format_mismatch": [{**valid_video, "pix_fmt": "yuv444p"}],
            "surface_contract_frame_count_mismatch": [{**valid_video, "nb_read_frames": "2"}],
            "surface_contract_audio_present": [valid_video, {"codec_type": "audio"}],
        }
        try:
            for expected_reason, streams in cases.items():
                with self.subTest(expected_reason=expected_reason):
                    payload.clear()
                    payload["streams"] = streams
                    with tempfile.NamedTemporaryFile(suffix=".mp4") as surface:
                        surface.write(b"h264")
                        surface.flush()
                        valid, reason = kiosk.probe_startup_feedback_video(
                            {},
                            surface.name,
                            width=1280,
                            height=720,
                        )
                    self.assertFalse(valid)
                    self.assertEqual(reason, expected_reason)
        finally:
            kiosk.subprocess.run = original_run

    def test_desired_public_surface_preserves_media_and_stratifies_failures(self) -> None:
        kiosk = load_kiosk_module()
        self.assertIsNone(
            kiosk.desired_startup_feedback_state(
                {"first_frame_ready": True, "playback_state": "playing"}
            )
        )
        self.assertEqual(
            kiosk.desired_startup_feedback_state(
                {"first_frame_ready": False, "content_state": "media_load_failed"}
            ),
            "error_no_content",
        )
        self.assertEqual(
            kiosk.desired_startup_feedback_state(
                {"first_frame_ready": False, "error_code": "player_recovering"}
            ),
            "error_player_start",
        )

    def test_public_surface_is_loaded_once_per_state_and_mpv_generation(self) -> None:
        kiosk = load_kiosk_module()
        with stub_startup_surface_video(kiosk), tempfile.TemporaryDirectory(prefix="c18-public-surface-") as tmp:
            cfg = {"runtime_dir": tmp, "startup_feedback_enabled": True}
            status = kiosk.StatusState()
            status.update(black_screen_risk_reason="waiting_for_content")
            mpv = FakeSurfaceMPV()
            self.assertTrue(kiosk.show_startup_feedback_once(mpv, cfg, status, "waiting_for_content"))
            self.assertIsNone(status.snapshot().get("black_screen_risk_reason"))
            self.assertTrue(kiosk.show_startup_feedback_once(mpv, cfg, status, "waiting_for_media"))
            self.assertEqual(len(mpv.load_calls), 1)
            status.update(black_screen_risk_reason="api_playlist_wait")
            self.assertTrue(kiosk.show_startup_feedback_once(mpv, cfg, status, "waiting_for_content"))
            self.assertIsNone(status.snapshot().get("black_screen_risk_reason"))
            self.assertEqual(
                status.snapshot().get("public_surface_evidence"),
                "mpv_path_vo_frame_available",
            )
            mpv.current_path_matches = False
            self.assertFalse(kiosk.show_startup_feedback_once(mpv, cfg, status, "waiting_for_content"))
            self.assertEqual(len(mpv.load_calls), 2)
            mpv.current_path_matches = True
            mpv.current_generation += 1
            self.assertTrue(kiosk.show_startup_feedback_once(mpv, cfg, status, "waiting_for_content"))
            self.assertEqual(len(mpv.load_calls), 3)
            self.assertTrue(kiosk.show_startup_feedback_once(mpv, cfg, status, "error_no_content"))
            self.assertEqual(len(mpv.load_calls), 4)

    def test_initial_surface_prewarms_recovery_without_replacing_visible_frame(self) -> None:
        kiosk = load_kiosk_module()
        with stub_startup_surface_video(kiosk), tempfile.TemporaryDirectory(prefix="c18-public-prewarm-") as tmp:
            cfg = {"runtime_dir": tmp, "startup_feedback_enabled": True}
            status = kiosk.StatusState()
            mpv = FakeSurfaceMPV()
            self.assertTrue(kiosk.show_initial_feedback_and_prewarm_recovery(mpv, cfg, status))
            self.assertEqual(len(mpv.load_calls), 1)
            self.assertEqual(
                mpv.load_calls[0].split("|", 1)[0],
                kiosk.startup_feedback_video_path(cfg, "waiting_for_content"),
            )
            self.assertTrue(Path(kiosk.startup_feedback_video_path(cfg, "error_player_start")).is_file())

    def test_local_frame_evidence_rejects_path_only_and_accepts_vo_frame(self) -> None:
        kiosk = load_kiosk_module()
        controller = kiosk.MPVController(
            {"ipc_path": "/tmp/c18-frame.sock", "mpv_log_file": "/tmp/c18-frame.log"}
        )
        controller.current_path = lambda **_kwargs: "/data/media/a.mp4"
        path_only = {
            "vo-configured": False,
            "estimated-frame-number": None,
            "time-pos": None,
            "video-params": None,
        }
        controller.get_property = lambda name, **_kwargs: path_only.get(name)
        self.assertFalse(controller.wait_for_local_frame_evidence("/data/media/a.mp4", timeout=0))

        static_frame = {
            "vo-configured": True,
            "estimated-frame-number": 0,
            "time-pos": 0.0,
            "video-params": {"w": 1920, "h": 1080},
        }
        controller.get_property = lambda name, **_kwargs: static_frame.get(name)
        self.assertFalse(controller.wait_for_local_frame_evidence("/data/media/a.mp4", timeout=0.06))
        self.assertTrue(
            controller.wait_for_local_frame_evidence(
                "/data/media/a.mp4",
                timeout=0,
                require_progress=False,
            )
        )

        clock_only = dict(static_frame, **{"estimated-frame-number": None})
        controller.get_property = lambda name, **_kwargs: clock_only.get(name)
        self.assertFalse(
            controller.wait_for_local_frame_evidence(
                "/data/media/a.mp4",
                timeout=0,
                require_progress=False,
            )
        )

        frame_queries = 0

        def advancing_property(name: str, **_kwargs: object) -> object:
            nonlocal frame_queries
            if name == "estimated-frame-number":
                frame_queries += 1
                return frame_queries - 1
            return static_frame.get(name)

        controller.get_property = advancing_property
        self.assertTrue(controller.wait_for_local_frame_evidence("/data/media/a.mp4", timeout=0.2))

        controller._generation = 1
        original_current_path = controller.current_path
        path_queries = 0

        def generation_changing_path(**kwargs: object) -> str:
            nonlocal path_queries
            path_queries += 1
            if path_queries == 1:
                controller._generation = 2
            return original_current_path(**kwargs)

        controller.current_path = generation_changing_path
        self.assertFalse(
            controller.wait_for_local_frame_evidence(
                "/data/media/a.mp4",
                timeout=0.2,
                expected_generation=1,
            )
        )

    def test_process_guard_is_the_restart_lock_and_enforces_exclusion(self) -> None:
        kiosk = load_kiosk_module()
        controller = kiosk.MPVController(
            {"ipc_path": "/tmp/c18-guard.sock", "mpv_log_file": "/tmp/c18-guard.log"}
        )
        guard = controller.process_guard()
        self.assertIs(guard, controller._lock)
        acquired = threading.Event()

        def acquire_same_guard() -> None:
            with controller.process_guard():
                acquired.set()

        guard.acquire()
        thread = threading.Thread(target=acquire_same_guard)
        thread.start()
        try:
            self.assertFalse(acquired.wait(timeout=0.05))
        finally:
            guard.release()
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertTrue(acquired.is_set())

    def test_player_surface_and_public_aggregate_converge(self) -> None:
        kiosk = load_kiosk_module()
        aggregate = load_status_aggregate_module()
        launcher = {"state": "running", "display_connected": True, "last_app_exit_code": None}
        with stub_startup_surface_video(kiosk), tempfile.TemporaryDirectory(prefix="c18-public-truth-") as tmp:
            cfg = {"runtime_dir": tmp, "startup_feedback_enabled": True}
            status = kiosk.StatusState()
            mpv = FakeSurfaceMPV()

            self.assertTrue(kiosk.show_startup_feedback_once(mpv, cfg, status, "error_no_content"))
            self.assertEqual(
                aggregate.build_status(
                    launcher_status=launcher,
                    player_status=status.snapshot(),
                    state_override=None,
                )["state"],
                "content_unavailable",
            )

            kiosk.mark_player_recovering(status, "test_restart")
            self.assertTrue(kiosk.show_startup_feedback_once(mpv, cfg, status, "error_player_start"))
            self.assertEqual(
                aggregate.build_status(
                    launcher_status=launcher,
                    player_status=status.snapshot(),
                    state_override=None,
                )["state"],
                "player_error",
            )

            status.update(
                playback_state="playing",
                player_state="playing",
                mpv_running=True,
                first_frame_ready=True,
                current_item={"path": str(KIOSK_PATH)},
                public_surface_state="media",
                error_code=None,
            )
            self.assertEqual(
                aggregate.build_status(
                    launcher_status=launcher,
                    player_status=status.snapshot(),
                    state_override=None,
                )["state"],
                "player_running",
            )

    def test_snapshot_has_single_default_mpv_path_assignment(self) -> None:
        text = KIOSK_PATH.read_text(encoding="utf-8")
        defaults = re.findall(r'"mpv_path"\s*:\s*"([^"]+)"', text)
        self.assertEqual(defaults, [C18_WRAPPER])

    def test_mpv_stop_uses_ipc_quit_with_signal_fallbacks(self) -> None:
        kiosk = load_kiosk_module()

        def make_controller(
            proc: FakeProc,
            send_result: bool,
            *,
            fresh_result: bool = True,
            ipc: object | None = object(),
        ):
            controller = kiosk.MPVController({"ipc_path": "/tmp/c18-fake.sock", "mpv_log_file": "/tmp/c18-fake.log"})
            controller._proc = proc
            controller._ipc = ipc
            sent: list[dict] = []
            controller._send = lambda payload, **_kwargs: sent.append(payload) or send_result
            fresh_sent: list[list[object]] = []
            controller._fresh_ipc_command = lambda command, **_kwargs: fresh_sent.append(command) or fresh_result
            closed: list[str] = []
            controller._close_ipc = lambda reason="cleanup", log_context=False: closed.append(reason)
            return controller, sent, fresh_sent, closed

        original_killpg = kiosk.os.killpg
        signals: list[tuple[int, int]] = []
        kiosk.os.killpg = lambda pid, sig: signals.append((pid, sig))
        try:
            clean_proc = FakeProc([0])
            clean, sent, fresh_sent, closed = make_controller(clean_proc, True)
            clean._stop_locked(reason="clean")
            self.assertEqual(sent, [{"command": ["quit"]}])
            self.assertEqual(fresh_sent, [])
            self.assertEqual(signals, [])
            self.assertEqual(clean_proc.wait_timeouts, [5])
            self.assertEqual(closed, ["clean"])

            no_ipc_proc = FakeProc([0])
            no_ipc, sent, fresh_sent, _closed = make_controller(no_ipc_proc, True, ipc=None)
            no_ipc._stop_locked(reason="no_ipc")
            self.assertEqual(sent, [])
            self.assertEqual(fresh_sent, [["quit"]])
            self.assertEqual(signals, [])
            self.assertEqual(no_ipc_proc.wait_timeouts, [5])

            signals.clear()
            no_ipc_fail_proc = FakeProc([0])
            no_ipc_fail, sent, fresh_sent, _closed = make_controller(no_ipc_fail_proc, True, fresh_result=False, ipc=None)
            no_ipc_fail._stop_locked(reason="no_ipc_fail")
            self.assertEqual(sent, [])
            self.assertEqual(fresh_sent, [["quit"]])
            self.assertEqual(signals, [(1234, kiosk.signal.SIGTERM)])
            self.assertEqual(no_ipc_fail_proc.wait_timeouts, [5])

            signals.clear()
            stuck_proc = FakeProc(["timeout", "timeout", -9])
            stuck, sent, fresh_sent, _closed = make_controller(stuck_proc, True)
            stuck._stop_locked(reason="stuck")
            self.assertEqual(sent, [{"command": ["quit"]}])
            self.assertEqual(fresh_sent, [])
            self.assertEqual(signals, [(1234, kiosk.signal.SIGTERM), (1234, kiosk.signal.SIGKILL)])
            self.assertEqual(stuck_proc.wait_timeouts, [5, 5, 5])
        finally:
            kiosk.os.killpg = original_killpg

    def test_fresh_ipc_startup_probe_is_not_retained(self) -> None:
        kiosk = load_kiosk_module()

        class FakeSocket:
            def __init__(self) -> None:
                self.closed = False
                self.connected_to = None

            def settimeout(self, _timeout: float) -> None:
                return None

            def connect(self, path: str) -> None:
                self.connected_to = path

            def close(self) -> None:
                self.closed = True

        fake_socket = FakeSocket()
        controller = kiosk.MPVController(
            {
                "ipc_path": "/tmp/c18-fresh-start.sock",
                "mpv_log_file": "/tmp/c18-fresh-start.log",
                "mpv_query_uses_fresh_ipc": True,
                "mpv_startup_timeout_sec": 0.1,
            }
        )
        original_exists = kiosk.os.path.exists
        original_socket = kiosk.socket.socket
        kiosk.os.path.exists = lambda path: path == "/tmp/c18-fresh-start.sock"
        kiosk.socket.socket = lambda *_args, **_kwargs: fake_socket
        try:
            self.assertTrue(controller._open_ipc())
        finally:
            kiosk.os.path.exists = original_exists
            kiosk.socket.socket = original_socket

        self.assertEqual(fake_socket.connected_to, "/tmp/c18-fresh-start.sock")
        self.assertTrue(fake_socket.closed)
        self.assertIsNone(controller._ipc)

    def test_fresh_ipc_running_process_does_not_require_persistent_socket(self) -> None:
        kiosk = load_kiosk_module()
        controller = kiosk.MPVController(
            {
                "ipc_path": "/tmp/c18-fresh-running.sock",
                "mpv_log_file": "/tmp/c18-fresh-running.log",
                "mpv_query_uses_fresh_ipc": True,
            }
        )
        controller._proc = FakeProc([])
        controller._ipc = None
        controller._fresh_ipc_get_property = lambda *_args, **_kwargs: {"error": "success", "data": False}
        stopped: list[str] = []
        controller._stop_locked = lambda reason="stop": stopped.append(reason)

        self.assertTrue(controller._start_locked())
        self.assertEqual(stopped, [])

    def test_fresh_ipc_mode_routes_control_commands_away_from_persistent_socket(self) -> None:
        kiosk = load_kiosk_module()

        class PoisonPersistentSocket:
            def sendall(self, _data: bytes) -> None:
                raise AssertionError("fresh IPC mode must not write to the persistent socket")

        controller = kiosk.MPVController(
            {
                "ipc_path": "/tmp/c18-fresh-command.sock",
                "mpv_log_file": "/tmp/c18-fresh-command.log",
                "mpv_query_uses_fresh_ipc": True,
            }
        )
        controller._ipc = PoisonPersistentSocket()
        controller._ipc_socket = True
        commands: list[list[object]] = []

        def fresh_query(command: list[object], **_kwargs: object) -> dict[str, object]:
            commands.append(command)
            return {"error": "success"}

        controller._fresh_ipc_query = fresh_query
        controller.wait_for_current_path = lambda *_args, **_kwargs: True

        self.assertTrue(controller.load_file("/data/media/a.mp4", alias="media-a"))
        self.assertTrue(controller.append_file("/data/media/b.mp4"))
        self.assertTrue(controller.playlist_next())
        self.assertTrue(controller.playlist_remove(0))
        self.assertTrue(controller.set_property("pause", False))
        self.assertTrue(controller.seek_absolute(1.5))
        self.assertEqual(
            commands,
            [
                ["loadfile", "/data/media/a.mp4", "replace"],
                ["loadfile", "/data/media/b.mp4", "append"],
                ["playlist-next", "force"],
                ["playlist-remove", 0],
                ["set_property", "pause", False],
                ["seek", 1.5, "absolute+exact"],
            ],
        )

        controller._fresh_ipc_query = lambda *_args, **_kwargs: {"error": "failure"}
        self.assertFalse(controller.playlist_next())

    def test_preloaded_advance_requires_cleanup_and_post_cleanup_verification(self) -> None:
        kiosk = load_kiosk_module()
        item = kiosk.MediaItem(
            url="cache://next.mp4",
            duration_ms=1000,
            path="/data/media/next.mp4",
            campaign_id="",
            campaign_name="",
        )

        ok_mpv = FakePreloadMPV(wait_results=[True, True])
        self.assertTrue(kiosk.advance_to_preloaded_media(ok_mpv, item, 1, 1000))
        self.assertEqual(ok_mpv.removed, [0])

        cleanup_fail = FakePreloadMPV(playlist_remove=False, wait_results=[True])
        self.assertFalse(kiosk.advance_to_preloaded_media(cleanup_fail, item, 1, 1000))
        self.assertEqual(cleanup_fail.removed, [0])

        post_cleanup_mismatch = FakePreloadMPV(wait_results=[True, False])
        self.assertFalse(kiosk.advance_to_preloaded_media(post_cleanup_mismatch, item, 1, 1000))
        self.assertEqual(post_cleanup_mismatch.removed, [0])

    def test_playback_loop_blocks_status_when_mpv_path_does_not_match_item(self) -> None:
        kiosk = load_kiosk_module()
        stop_event = threading.Event()
        status = StopOnMismatchStatus(stop_event)
        status._data.update(
            {
                "current_index": 7,
                "current_item": {"path": "/data/media/old.mp4"},
                "next_item": {"path": "/data/media/next-old.mp4"},
            }
        )
        state = kiosk.PlaylistState()
        item = kiosk.MediaItem(
            url="cache://stuck.mp4",
            duration_ms=25,
            path="/data/media/stuck.mp4",
            campaign_id="campaign-1",
            campaign_name="Campaign 1",
        )
        self.assertTrue(state.update([item], "fixture"))
        with stub_startup_surface_video(kiosk), tempfile.TemporaryDirectory(
            prefix="c18-playback-cache-index-"
        ) as tmp:
            cfg = {
                "state_dir": tmp,
                "runtime_dir": tmp,
                "sync_enabled": False,
                "preload_next": False,
                "media_load_retry_cooldown_sec": 5,
            }
            mpv = FakeMismatchMPV()

            kiosk.playback_loop(cfg, threading.Lock(), state, status, mpv, kiosk.CacheIndex(cfg), stop_event)

        current_item_updates = [update for update in status.updates if "current_item" in update]
        self.assertEqual([update["current_item"] for update in current_item_updates], [None])
        self.assertTrue(any(update.get("content_state") == "media_path_mismatch" for update in status.updates))
        self.assertIsNone(status.snapshot().get("current_index"))
        self.assertIsNone(status.snapshot().get("current_item"))
        self.assertIsNone(status.snapshot().get("next_item"))
        self.assertTrue(mpv.restart_reasons)
        self.assertEqual(mpv.append_calls, [])

    def test_playback_loop_exposes_recovery_when_mpv_generation_changes(self) -> None:
        kiosk = load_kiosk_module()
        stop_event = threading.Event()
        status = StopOnRecoveredStatus(stop_event)
        state = kiosk.PlaylistState()
        item = kiosk.MediaItem(
            url="cache://current.mp4",
            duration_ms=10000,
            path="/data/media/current.mp4",
            campaign_id="campaign-1",
            campaign_name="Campaign 1",
        )
        self.assertTrue(state.update([item], "fixture"))
        with stub_startup_surface_video(kiosk), tempfile.TemporaryDirectory(prefix="c18-generation-recovery-") as tmp:
            cfg = {
                "state_dir": tmp,
                "runtime_dir": tmp,
                "startup_feedback_enabled": True,
                "sync_enabled": False,
                "preload_next": False,
            }
            mpv = FakeGenerationRecoveryMPV()
            persisted: list[dict[str, object]] = []
            original_write_status_once = kiosk.write_status_once
            kiosk.write_status_once = lambda _cfg, current: persisted.append(current.snapshot()) or True
            try:
                kiosk.playback_loop(
                    cfg,
                    threading.Lock(),
                    state,
                    status,
                    mpv,
                    kiosk.CacheIndex(cfg),
                    stop_event,
                )
            finally:
                kiosk.write_status_once = original_write_status_once

        self.assertEqual(mpv.current_generation, 2)
        self.assertEqual(mpv.frame_checks, 2)
        self.assertTrue(any("startup-feedback:error_player_start" in call for call in mpv.load_calls))
        media_load_calls = [call for call in mpv.load_calls if "/data/media/current.mp4" in call]
        self.assertEqual(len(media_load_calls), 2)
        self.assertEqual(status.snapshot().get("content_state"), "playing")
        self.assertEqual(status.snapshot().get("public_surface_presented_state"), "media")
        self.assertEqual(status.snapshot().get("public_surface_generation"), 2)
        self.assertIsNone(status.snapshot().get("error_code"))
        recovery_without_surface = next(
            index
            for index, snapshot in enumerate(persisted)
            if snapshot.get("playback_state") == "recovering"
            and snapshot.get("public_surface_presented_state") is None
        )
        recovery_with_surface = next(
            index
            for index, snapshot in enumerate(persisted)
            if snapshot.get("playback_state") == "recovering"
            and snapshot.get("public_surface_presented_state") == "player_error"
            and snapshot.get("public_surface_evidence") == "mpv_path_vo_frame_available"
        )
        self.assertLess(recovery_without_surface, recovery_with_surface)

    def test_playback_loop_accepts_single_frame_still_sidecar_without_progress(self) -> None:
        kiosk = load_kiosk_module()
        stop_event = threading.Event()
        status = StopOnPlayingStatus(stop_event)
        state = kiosk.PlaylistState()
        item = kiosk.MediaItem(
            url="cache://current.png",
            duration_ms=1000,
            path="/data/media/current.png.h264.mp4",
            campaign_id="campaign-1",
            campaign_name="Campaign 1",
            source_path="/data/media/current.png",
        )
        self.assertTrue(kiosk.is_still_image_item(item))
        self.assertEqual(
            kiosk.media_frame_evidence_policy(item),
            (False, "mpv_path_vo_frame_available"),
        )
        self.assertTrue(state.update([item], "fixture"))
        with tempfile.TemporaryDirectory(prefix="c18-still-frame-policy-") as tmp:
            cfg = {
                "state_dir": tmp,
                "runtime_dir": tmp,
                "startup_feedback_enabled": True,
                "sync_enabled": False,
                "preload_next": False,
            }
            mpv = FakeStillFrameMPV()
            result = kiosk.playback_loop(
                cfg,
                threading.Lock(),
                state,
                status,
                mpv,
                kiosk.CacheIndex(cfg),
                stop_event,
            )

        self.assertIsNone(result)
        self.assertEqual(mpv.frame_require_progress, [False])
        self.assertEqual(status.snapshot().get("content_state"), "playing")
        self.assertEqual(
            status.snapshot().get("first_frame_evidence"),
            "mpv_path_vo_frame_available",
        )
        self.assertNotEqual(status.snapshot().get("content_state"), "media_frame_not_ready")

    def test_playback_loop_exits_after_bounded_mpv_recovery_failures(self) -> None:
        kiosk = load_kiosk_module()
        state = kiosk.PlaylistState()
        item = kiosk.MediaItem(
            url="cache://current.mp4",
            duration_ms=10000,
            path="/data/media/current.mp4",
            campaign_id="campaign-1",
            campaign_name="Campaign 1",
        )
        self.assertTrue(state.update([item], "fixture"))
        with tempfile.TemporaryDirectory(prefix="c18-dead-mpv-") as tmp:
            cfg = {
                "state_dir": tmp,
                "sync_enabled": False,
                "preload_next": False,
                "mpv_recovery_max_attempts": 2,
            }
            status = kiosk.StatusState()
            mpv = FakeDeadMPV()
            failure = kiosk.playback_loop(
                cfg,
                threading.Lock(),
                state,
                status,
                mpv,
                kiosk.CacheIndex(cfg),
                threading.Event(),
            )

        self.assertEqual(failure, "mpv_recovery_exhausted")
        self.assertEqual(mpv.ensure_calls, 2)
        self.assertEqual(status.snapshot().get("player_state"), "error")
        self.assertEqual(status.snapshot().get("error_code"), "player_start_failed")

    def test_empty_playlist_also_exits_after_bounded_mpv_recovery_failures(self) -> None:
        kiosk = load_kiosk_module()
        state = kiosk.PlaylistState()
        with tempfile.TemporaryDirectory(prefix="c18-empty-dead-mpv-") as tmp:
            cfg = {
                "state_dir": tmp,
                "sync_enabled": False,
                "mpv_recovery_max_attempts": 2,
            }
            status = kiosk.StatusState()
            mpv = FakeDeadMPV()
            failure = kiosk.playback_loop(
                cfg,
                threading.Lock(),
                state,
                status,
                mpv,
                kiosk.CacheIndex(cfg),
                threading.Event(),
            )

        self.assertEqual(failure, "mpv_recovery_exhausted")
        self.assertEqual(mpv.ensure_calls, 2)
        self.assertEqual(status.snapshot().get("black_screen_risk_reason"), "mpv_recovery_exhausted")

    def test_empty_playlist_exits_when_public_surface_cannot_be_presented(self) -> None:
        kiosk = load_kiosk_module()
        state = kiosk.PlaylistState()
        with stub_startup_surface_video(kiosk), tempfile.TemporaryDirectory(
            prefix="c18-empty-surface-fail-"
        ) as tmp:
            cfg = {
                "state_dir": tmp,
                "runtime_dir": tmp,
                "sync_enabled": False,
                "startup_feedback_max_attempts": 2,
            }
            status = kiosk.StatusState()
            mpv = FakeSurfaceMPV()
            mpv.current_path_matches = False
            original_sleep = kiosk.time.sleep
            kiosk.time.sleep = lambda _seconds: None
            try:
                failure = kiosk.playback_loop(
                    cfg,
                    threading.Lock(),
                    state,
                    status,
                    mpv,
                    kiosk.CacheIndex(cfg),
                    threading.Event(),
                )
            finally:
                kiosk.time.sleep = original_sleep

        self.assertEqual(failure, "public_surface_recovery_exhausted")
        self.assertEqual(status.snapshot().get("player_state"), "error")
        self.assertEqual(status.snapshot().get("startup_feedback_failure_count"), 2)

    def test_still_image_prepare_creates_h264_sidecar_for_c18_mpv(self) -> None:
        kiosk = load_kiosk_module()
        with tempfile.TemporaryDirectory(prefix="c18-image-transcode-") as tmp:
            source = Path(tmp) / "media.png"
            source.write_bytes(b"fake-png")
            calls: list[list[str]] = []

            def fake_run(command: list[str], **_kwargs: object) -> object:
                calls.append(command)
                Path(command[-1]).write_bytes(b"fake-h264")
                return object()

            original_run = kiosk.subprocess.run
            kiosk.subprocess.run = fake_run
            try:
                cfg = {
                    "media_probe_enabled": False,
                    "image_transcode_ffmpeg_path": "/usr/bin/ffmpeg",
                    "image_transcode_timeout_sec": 5,
                }
                playback_path = kiosk.prepare_media_file_for_playback(cfg, str(source), 5000)
                self.assertEqual(playback_path, f"{source}.h264.mp4")
                self.assertEqual(Path(playback_path).read_bytes(), b"fake-h264")
                self.assertEqual(len(calls), 1)
                self.assertIn("-c:v", calls[0])
                self.assertIn("libx264", calls[0])
                self.assertIn("-f", calls[0])
                self.assertEqual(calls[0][calls[0].index("-f") + 1], "mp4")

                reused_path = kiosk.prepare_media_file_for_playback(cfg, str(source), 5000)
                self.assertEqual(reused_path, playback_path)
                self.assertEqual(len(calls), 1)
            finally:
                kiosk.subprocess.run = original_run

    def test_download_media_uses_h264_sidecar_for_cached_png(self) -> None:
        kiosk = load_kiosk_module()
        with tempfile.TemporaryDirectory(prefix="c18-download-image-transcode-") as tmp:
            cache_dir = Path(tmp) / "cache"
            state_dir = Path(tmp) / "state"
            cache_dir.mkdir()
            state_dir.mkdir()
            url = "https://example.invalid/media/current.png"
            source = Path(kiosk.cache_path(str(cache_dir), url))
            source.write_bytes(b"fake-png")

            def fake_run(command: list[str], **_kwargs: object) -> object:
                Path(command[-1]).write_bytes(b"fake-h264")
                return object()

            original_run = kiosk.subprocess.run
            kiosk.subprocess.run = fake_run
            try:
                cfg = {
                    "cache_dir": str(cache_dir),
                    "state_dir": str(state_dir),
                    "media_probe_enabled": False,
                    "image_transcode_ffmpeg_path": "/usr/bin/ffmpeg",
                    "image_transcode_timeout_sec": 5,
                }
                cache_index = kiosk.CacheIndex(cfg)
                items = kiosk.download_media(
                    cfg,
                    [{
                        "url": url,
                        "duration_ms": 5000,
                        "campaign_id": "campaign-1",
                        "campaign_name": "Campaign 1",
                    }],
                    cache_index,
                )
            finally:
                kiosk.subprocess.run = original_run

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].path, f"{source}.h264.mp4")
            self.assertEqual(items[0].source_path, str(source))
            index_meta = cache_index.snapshot()[items[0].path]
            self.assertEqual(index_meta["source_path"], str(source))
            self.assertEqual(index_meta["url"], url)

    def test_corrupt_existing_image_sidecar_is_rebuilt_before_reuse(self) -> None:
        kiosk = load_kiosk_module()
        with tempfile.TemporaryDirectory(prefix="c18-image-sidecar-rebuild-") as tmp:
            source = Path(tmp) / "media.png"
            sidecar = Path(f"{source}.h264.mp4")
            source.write_bytes(b"source-image")
            sidecar.write_bytes(b"corrupt-sidecar")
            os.utime(sidecar, (source.stat().st_mtime + 1, source.stat().st_mtime + 1))
            calls: list[list[str]] = []

            def fake_run(command: list[str], **_kwargs: object) -> object:
                calls.append(command)
                if command[0] == "/usr/bin/ffprobe":
                    target = Path(command[-1])
                    if target == sidecar:
                        return subprocess.CompletedProcess(command, 1, stdout=b"", stderr=b"bad")
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout=b'{"streams":[{"codec_type":"video","codec_name":"h264","width":1280,"height":720}]}',
                        stderr=b"",
                    )
                if "-f" in command and command[command.index("-f") + 1] == "null":
                    return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")
                Path(command[-1]).write_bytes(b"rebuilt-h264")
                return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

            original_run = kiosk.subprocess.run
            kiosk.subprocess.run = fake_run
            try:
                cfg = {
                    "media_probe_enabled": True,
                    "media_probe_ffprobe_path": "/usr/bin/ffprobe",
                    "media_probe_ffmpeg_path": "/usr/bin/ffmpeg",
                    "media_probe_timeout_sec": 5,
                    "image_transcode_ffmpeg_path": "/usr/bin/ffmpeg",
                    "image_transcode_timeout_sec": 5,
                }
                playback_path = kiosk.prepare_media_file_for_playback(cfg, str(source), 5000)
            finally:
                kiosk.subprocess.run = original_run

            self.assertEqual(playback_path, str(sidecar))
            self.assertEqual(sidecar.read_bytes(), b"rebuilt-h264")
            self.assertEqual(sum(1 for call in calls if call[0] == "/usr/bin/ffmpeg"), 2)
            self.assertEqual(sum(1 for call in calls if call[0] == "/usr/bin/ffprobe"), 2)

    def test_media_probe_rejects_empty_and_non_video_payloads(self) -> None:
        kiosk = load_kiosk_module()
        with tempfile.TemporaryDirectory(prefix="c18-media-probe-") as tmp:
            empty = Path(tmp) / "empty.mp4"
            empty.write_bytes(b"")
            self.assertEqual(kiosk.probe_media_file({}, str(empty)), (False, "file_empty"))

            invalid = Path(tmp) / "invalid.mp4"
            invalid.write_bytes(b"not-media")
            original_run = kiosk.subprocess.run
            kiosk.subprocess.run = lambda command, **kwargs: subprocess.CompletedProcess(
                command,
                0,
                stdout=b'{"streams":[{"codec_type":"audio","codec_name":"aac"}]}',
                stderr=b"",
            )
            try:
                self.assertEqual(kiosk.probe_media_file({}, str(invalid)), (False, "video_stream_missing"))
            finally:
                kiosk.subprocess.run = original_run

    def test_media_probe_rejects_ffprobe_false_green_when_first_frame_cannot_decode(self) -> None:
        kiosk = load_kiosk_module()
        with tempfile.TemporaryDirectory(prefix="c18-media-decode-probe-") as tmp:
            truncated = Path(tmp) / "truncated.mp4"
            truncated.write_bytes(b"truncated-but-ffprobe-visible")

            def fake_run(command: list[str], **_kwargs: object) -> object:
                if command[0] == "/usr/bin/ffprobe":
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout=b'{"streams":[{"codec_type":"video","codec_name":"h264","width":1280,"height":720}]}',
                        stderr=b"decode warnings ignored by ffprobe",
                    )
                return subprocess.CompletedProcess(command, 1, stdout=b"", stderr=b"corrupt input packet")

            original_run = kiosk.subprocess.run
            kiosk.subprocess.run = fake_run
            try:
                self.assertEqual(
                    kiosk.probe_media_file({}, str(truncated)),
                    (False, "first_frame_decode_failed"),
                )
            finally:
                kiosk.subprocess.run = original_run

    def test_incomplete_playlist_is_explicitly_stale_while_last_known_good_remains(self) -> None:
        kiosk = load_kiosk_module()
        with tempfile.TemporaryDirectory(prefix="c18-playlist-incomplete-") as tmp:
            cfg = dict(kiosk.DEFAULT_CONFIG)
            cfg.update({
                "cache_dir": str(Path(tmp) / "cache"),
                "state_dir": str(Path(tmp) / "state"),
                "poll_interval_sec": 1,
                "require_full_download_before_switch": True,
                "telemetry_enabled": False,
            })
            state = kiosk.PlaylistState()
            previous = kiosk.MediaItem("", 1000, "/tmp/previous.mp4", "old", "Old")
            state.update([previous], "previous")
            status = kiosk.StatusState()
            stop_event = threading.Event()
            raw_items = [
                {"url": f"https://invalid.example/{index}.mp4", "duration_ms": 1000}
                for index in range(3)
            ]
            downloaded = [
                kiosk.MediaItem("", 1000, f"/tmp/{index}.mp4", str(index), str(index))
                for index in range(2)
            ]
            original_fetch = kiosk.fetch_media_list
            original_download = kiosk.download_media
            kiosk.fetch_media_list = lambda _cfg: raw_items

            def fake_download(*_args: object, **_kwargs: object) -> list[object]:
                stop_event.set()
                return downloaded

            kiosk.download_media = fake_download
            try:
                kiosk.poller(
                    cfg,
                    threading.Lock(),
                    threading.Event(),
                    state,
                    status,
                    kiosk.CacheIndex(cfg),
                    stop_event,
                )
            finally:
                kiosk.fetch_media_list = original_fetch
                kiosk.download_media = original_download

            current, _ = state.get()
            snapshot = status.snapshot()
            self.assertEqual(current, [previous])
            self.assertEqual(snapshot["playlist_update_state"], "download_incomplete_retaining_last_known_good")
            self.assertIs(snapshot["content_stale"], True)
            self.assertEqual(snapshot["content_stale_reason"], "playlist_download_incomplete")
            self.assertEqual(snapshot["failed_media_count"], 1)
            self.assertIsNone(snapshot["last_poll_error"])

    def test_partial_playlist_adoption_stays_explicitly_stale_when_legacy_policy_allows_it(self) -> None:
        kiosk = load_kiosk_module()
        with tempfile.TemporaryDirectory(prefix="c18-playlist-partial-") as tmp:
            cfg = dict(kiosk.DEFAULT_CONFIG)
            cfg.update({
                "cache_dir": str(Path(tmp) / "cache"),
                "state_dir": str(Path(tmp) / "state"),
                "poll_interval_sec": 1,
                "require_full_download_before_switch": False,
                "telemetry_enabled": False,
            })
            state = kiosk.PlaylistState()
            status = kiosk.StatusState()
            stop_event = threading.Event()
            raw_items = [
                {"url": f"https://invalid.example/{index}.mp4", "duration_ms": 1000}
                for index in range(2)
            ]
            downloaded = [kiosk.MediaItem("", 1000, "/tmp/0.mp4", "0", "0")]
            original_fetch = kiosk.fetch_media_list
            original_download = kiosk.download_media
            kiosk.fetch_media_list = lambda _cfg: raw_items

            def fake_download(*_args: object, **_kwargs: object) -> list[object]:
                stop_event.set()
                return downloaded

            kiosk.download_media = fake_download
            try:
                kiosk.poller(
                    cfg,
                    threading.Lock(),
                    threading.Event(),
                    state,
                    status,
                    kiosk.CacheIndex(cfg),
                    stop_event,
                )
            finally:
                kiosk.fetch_media_list = original_fetch
                kiosk.download_media = original_download

            current, _ = state.get()
            snapshot = status.snapshot()
            self.assertEqual(current, downloaded)
            self.assertEqual(snapshot["playlist_update_state"], "partial_playlist_applied")
            self.assertIs(snapshot["content_stale"], True)
            self.assertEqual(snapshot["content_stale_reason"], "partial_playlist")
            self.assertEqual(snapshot["pending_playlist_size"], 2)
            self.assertEqual(snapshot["failed_media_count"], 1)

    def test_telemetry_payload_exposes_playlist_adoption_health(self) -> None:
        kiosk = load_kiosk_module()
        status = kiosk.StatusState().snapshot()
        status.update({
            "playlist_update_state": "download_incomplete_retaining_last_known_good",
            "pending_playlist_size": 3,
            "failed_media_count": 1,
            "content_stale": True,
            "content_stale_reason": "playlist_download_incomplete",
        })
        payload = kiosk.build_telemetry_payload({}, status, "healthcheck", "warning")
        self.assertEqual(payload["playlistUpdateState"], "download_incomplete_retaining_last_known_good")
        self.assertEqual(payload["pendingPlaylistSize"], 3)
        self.assertEqual(payload["failedMediaCount"], 1)
        self.assertIs(payload["contentStale"], True)
        self.assertEqual(payload["contentStaleReason"], "playlist_download_incomplete")
        self.assertEqual(payload["metrics"]["pendingEntries"], 1)

    def test_empty_api_playlist_is_explicitly_stale_while_last_known_good_remains(self) -> None:
        kiosk = load_kiosk_module()
        with tempfile.TemporaryDirectory(prefix="c18-playlist-empty-") as tmp:
            cfg = dict(kiosk.DEFAULT_CONFIG)
            cfg.update({
                "cache_dir": str(Path(tmp) / "cache"),
                "state_dir": str(Path(tmp) / "state"),
                "poll_interval_sec": 1,
                "allow_empty_playlist_from_api": False,
                "telemetry_enabled": False,
            })
            state = kiosk.PlaylistState()
            previous = kiosk.MediaItem("", 1000, "/tmp/previous.mp4", "old", "Old")
            state.update([previous], "previous")
            status = kiosk.StatusState()
            stop_event = threading.Event()
            original_fetch = kiosk.fetch_media_list

            def fake_fetch(_cfg: object) -> list[object]:
                stop_event.set()
                return []

            kiosk.fetch_media_list = fake_fetch
            try:
                kiosk.poller(
                    cfg,
                    threading.Lock(),
                    threading.Event(),
                    state,
                    status,
                    kiosk.CacheIndex(cfg),
                    stop_event,
                )
            finally:
                kiosk.fetch_media_list = original_fetch

            current, _ = state.get()
            snapshot = status.snapshot()
            self.assertEqual(current, [previous])
            self.assertEqual(snapshot["playlist_update_state"], "api_empty_retaining_last_known_good")
            self.assertIs(snapshot["content_stale"], True)
            self.assertEqual(snapshot["content_stale_reason"], "api_empty_playlist")

    def test_saved_playlist_preserves_image_source_and_playback_paths(self) -> None:
        kiosk = load_kiosk_module()
        with tempfile.TemporaryDirectory(prefix="c18-saved-image-paths-") as tmp:
            cache_dir = Path(tmp) / "cache"
            state_dir = Path(tmp) / "state"
            cache_dir.mkdir()
            state_dir.mkdir()
            source = cache_dir / "media.png"
            playback = cache_dir / "media.png.h264.mp4"
            source.write_bytes(b"fake-png")
            playback.write_bytes(b"fake-h264")
            cfg = {
                "cache_dir": str(cache_dir),
                "state_dir": str(state_dir),
                "media_probe_enabled": False,
            }
            item = kiosk.MediaItem(
                url="https://example.invalid/media/current.png",
                duration_ms=5000,
                path=str(playback),
                campaign_id="campaign-1",
                campaign_name="Campaign 1",
                source_path=str(source),
            )
            kiosk.save_playlist_state(cfg, [item], "fixture")
            self.assertEqual(kiosk.saved_playlist_paths(cfg), {str(source), str(playback)})

            raw_items, _fingerprint, _saved_at = kiosk.load_playlist_state(cfg)
            restored, payload = kiosk.media_items_from_saved(cfg, raw_items)
            self.assertEqual(len(restored), 1)
            self.assertEqual(restored[0].path, str(playback))
            self.assertEqual(restored[0].source_path, str(source))
            self.assertEqual(payload[0]["source_path"], str(source))

    def test_c18_deriver_uses_governed_snapshot(self) -> None:
        derive = DERIVE_C18_PATH.read_text(encoding="utf-8")
        current_tag = CURRENT_GOLDEN["image_tag"]
        current_suffix = current_tag.rsplit("-", maxsplit=1)[-1]
        self.assertTrue(current_tag.startswith("c18-hwdecode-lab-1"))
        self.assertEqual(CURRENT_GOLDEN["image_version"], f"c18.image-lab.{current_suffix}")
        self.assertEqual(CURRENT_GOLDEN["image_marker_path"], f"/etc/dadooh/{current_tag}-image")
        self.assertIn("CURRENT_GOLDEN_PATH", derive)
        self.assertIn('TAG = str(CURRENT_GOLDEN["image_tag"])', derive)
        self.assertIn('VERSION = str(CURRENT_GOLDEN["image_version"])', derive)
        self.assertIn('MARKER = str(CURRENT_GOLDEN["image_marker_path"])', derive)
        self.assertIn('ap.add_argument("--image-tag"', derive)
        self.assertIn("TAG = args.image_tag", derive)
        self.assertIn("VERSION = args.image_version or image_version_for_tag(TAG)", derive)
        self.assertIn('MARKER = args.image_marker or f"/etc/dadooh/{TAG}-image"', derive)
        self.assertIn('"round": round_name', derive)
        self.assertIn("=== {round_name} RESULT ===", derive)
        self.assertIn("1s (golden delivery before boot-state evidence and crash-boundary gates)", derive)
        self.assertIn("1t (golden delivery before post-M6 reconcile freeze hardware proof)", derive)
        self.assertIn("1u (golden delivery before physical power-loss/soak/server-side gates)", derive)
        self.assertIn("1p (boot reconcile ran as totem", derive)
        self.assertIn("1q (golden delivery before multi-segment deep-health gate", derive)
        self.assertIn("1r (golden delivery before cold-boot/power-loss pre-hardening gates", derive)
        self.assertIn("1s (golden delivery before boot-state evidence and crash-boundary gates", derive)
        self.assertIn("player_runtime_boot_state_evidence_gate", derive)
        self.assertIn("player_runtime_fault_injection_gate", derive)
        self.assertIn("player_runtime_reconcile_corrupt_state_fail_closed", derive)
        self.assertIn('PLAYER_RUNTIME_KIOSK = REPO_ROOT / "player-runtime" / "kiosky-player" / "kiosk.py"', derive)
        self.assertIn("PLAYER_RUNTIME_KIOSK_SHA256", derive)
        self.assertIn(f'PLAYER_RUNTIME_KIOSK_SHA256 = "{EXPECTED_SNAPSHOT_SHA256}"', derive)
        self.assertIn("PLAYER_RUNTIME_REQUIRED_PATCHES", derive)
        self.assertIn("PLAYER_RUNTIME_TEARDOWN_TOKENS", derive)
        self.assertIn("validate_player_runtime_snapshot", derive)
        self.assertIn("player-runtime kiosk.py teardown governance mismatch", derive)
        self.assertIn("player_runtime_snapshot_governed", derive)

    def test_c18_deriver_promotes_artifacts_only_after_offline_validation(self) -> None:
        derive = DERIVE_C18_PATH.read_text(encoding="utf-8")
        self.assertIn("OUT_SHA = Path(str(OUT_IMAGE) + \".sha256\")", derive)
        self.assertIn("tempfile.mkstemp", derive)
        self.assertIn("build_sha.write_text", derive)
        self.assertIn("os.replace(build_image, OUT_IMAGE)", derive)
        self.assertIn('R4_UPDATECTL = REPO_ROOT / "scripts" / "board" / "totem_updatectl.py"', derive)
        self.assertIn("def repo_identity()", derive)
        self.assertIn('"repo_commit": git_text("rev-parse", "HEAD")', derive)
        self.assertIn('"repo_tree": git_text("rev-parse", "HEAD^{tree}")', derive)
        self.assertIn('"repo_dirty": bool(status)', derive)
        self.assertIn("--allow-dirty", derive)
        self.assertIn("source repo dirty; commit first", derive)
        self.assertIn("**repo", derive)
        self.assertIn("out_dir.mkdir(parents=True, exist_ok=True)", derive)
        self.assertIn("for target in {work, out_dir}", derive)
        self.assertIn("offline validation failed; final image/sha256 not promoted", derive)
        self.assertLess(derive.index("offline_ok = all("), derive.index("os.replace(build_image, OUT_IMAGE)"))
        self.assertNotIn("shutil.copy2(BASE_IMAGE, OUT_IMAGE)", derive)
        self.assertNotIn("(Path(str(OUT_IMAGE) + \".sha256\")).write_text", derive)

    def test_common_ota_gate_tracks_player_runtime_boundary(self) -> None:
        gate = RELEASE_GATE_PATH.read_text(encoding="utf-8")
        self.assertIn('"scripts/qa/c18_player_runtime_static_test.py"', gate)
        self.assertIn('"scripts/qa/c18_player_runtime_lab_thaw.py"', gate)
        self.assertIn('"player-runtime/kiosky-player/kiosk.py"', gate)
        self.assertIn('"player-runtime/kiosky-player/SOURCE.json"', gate)
        self.assertIn("c18_player_runtime_static", gate)

    def test_candidate_health_sets_explicit_panfrost_fault_policy(self) -> None:
        candidate_health = CANDIDATE_HEALTH_PATH.read_text(encoding="utf-8")
        self.assertIn('panfrost_fault_policy: str = "absolute"', candidate_health)
        self.assertIn('choices=("absolute", "delta")', candidate_health)
        self.assertIn("panfrost_fault_policy=panfrost_fault_policy", candidate_health)
        self.assertIn('"startup_feedback_enabled": require_startup_surface_health', candidate_health)
        self.assertIn('"candidate_startup_surface_local_evidence"', candidate_health)

    def test_candidate_surface_health_requirement_preserves_historical_packages(self) -> None:
        candidate_health = load_candidate_health_module()
        historical = {
            "requires": {
                "updater_features": ["c18-player-runtime-verify-then-promote-v1"]
            }
        }
        c25 = {
            "requires": {
                "updater_features": [
                    "c18-player-runtime-verify-then-promote-v1",
                    "c25-player-surface-health-v1",
                ]
            }
        }
        self.assertFalse(candidate_health.manifest_requires_startup_surface_health(historical))
        self.assertTrue(candidate_health.manifest_requires_startup_surface_health(c25))
        with tempfile.TemporaryDirectory(prefix="c18-candidate-config-") as tmp:
            work = Path(tmp)
            historical_cfg = candidate_health.candidate_config(
                None,
                work / "historical",
            )
            c25_cfg = candidate_health.candidate_config(
                None,
                work / "c25",
                require_startup_surface_health=True,
            )
        self.assertFalse(historical_cfg["startup_feedback_enabled"])
        self.assertTrue(c25_cfg["startup_feedback_enabled"])

    def test_c25_surface_health_is_bound_from_builder_to_evidence(self) -> None:
        feature = "c25-player-surface-health-v1"
        for path in (
            PLAYER_RUNTIME_BUILDER_PATH,
            UPDATECTL_PATH,
            PLAYER_RUNTIME_RELEASE_GATE_PATH,
            PLAYER_RUNTIME_EVIDENCE_GATE_PATH,
            PLAYER_RUNTIME_COLDBOOT_PATH,
        ):
            self.assertIn(feature, path.read_text(encoding="utf-8"), str(path))
        builder = PLAYER_RUNTIME_BUILDER_PATH.read_text(encoding="utf-8")
        self.assertIn('python3 "$STATIC_GATE"', builder)

    def test_lab_thaw_wrapper_is_guarded_and_m6_based(self) -> None:
        thaw = LAB_THAW_PATH.read_text(encoding="utf-8")
        self.assertIn("C18_PLAYER_RUNTIME_LAB_THAW", thaw)
        self.assertIn("C18_PLAYER_RUNTIME_M6_COLDBOOT_TRIAL", thaw)
        self.assertIn("c18_player_runtime_m6_coldboot_trial.py", thaw)
        self.assertIn("load_current_golden", thaw)
        self.assertIn("validate_release(args.manifest_a", thaw)
        self.assertIn("validate_release(args.manifest_b", thaw)
        self.assertIn('"public_cli_thawed": False', thaw)
        self.assertIn('"stable_allowed": False', thaw)


class C18LauncherConfigBaselineGuardTest(unittest.TestCase):
    """Boot-time fail-closed guard: the EFFECTIVE config must not lower HW decode.

    Exercises the real config_valid() from kiosky_service_launcher.sh end-to-end
    so a field config ("config-real") that overrides mpv_path to a non-wrapper
    binary is REJECTED (player does not start), while an absent mpv_path or the
    C18 HW-decode wrapper is ACCEPTED. This closes the baseline-regression vector
    that hit "1h" without going through the release path.
    """

    BASE_CONFIG = {
        "api_url": "https://api.example.invalid/search",
        "api_key": "replace-with-api-key",
        "environment_id": "replace-with-environment-id",
        "cache_dir": "/data/media/kiosky-player",
        "state_dir": "/data/state/kiosky-player",
        "status_file": "/tmp/kiosky-status.json",
        "ipc_path": "/tmp/kiosky/mpv.sock",
        "preload_next": False,
    }

    def _config_valid_rc(self, config_text: str, *, with_validator: bool = True) -> int:
        with tempfile.TemporaryDirectory(prefix="c18-config-valid-guard-") as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(config_text, encoding="utf-8")
            validator = (
                str(CONFIG_CONTRACT_VALIDATOR_PATH)
                if with_validator
                else str(Path(tmp) / "absent-validator.py")
            )
            env = os.environ.copy()
            env.update(
                {
                    "KIOSKY_LAUNCHER_SOURCE_ONLY": "1",
                    "KIOSKY_CONFIG_PATH": str(config_path),
                    "TOTEM_CONFIG_CONTRACT_VALIDATOR": validator,
                    "TOTEM_C18_HWDECODE_WRAPPER": C18_WRAPPER,
                    "PYTHONDONTWRITEBYTECODE": "1",
                }
            )
            script = f'. "{INNER_LAUNCHER_PATH}"; config_valid; exit "$?"'
            proc = subprocess.run(
                ["bash", "-c", script],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )
            return proc.returncode

    def _config_with(self, **overrides: object) -> str:
        config = dict(self.BASE_CONFIG)
        config.update(overrides)
        return json.dumps(config, indent=2, sort_keys=True)

    def test_absent_mpv_path_is_accepted(self) -> None:
        self.assertEqual(self._config_valid_rc(self._config_with()), 0)

    def test_wrapper_mpv_path_is_accepted(self) -> None:
        self.assertEqual(self._config_valid_rc(self._config_with(mpv_path=C18_WRAPPER)), 0)

    def test_preload_next_true_is_rejected_at_boot(self) -> None:
        self.assertEqual(self._config_valid_rc(self._config_with(preload_next=True)), 1)

    def test_baseline_lowering_mpv_path_is_rejected(self) -> None:
        for bad in ("mpv", "/usr/bin/mpv", "relative/mpv", "", "/opt/totem/bin/totem-mpv-hwdecode-x"):
            with self.subTest(mpv_path=bad):
                self.assertEqual(
                    self._config_valid_rc(self._config_with(mpv_path=bad)),
                    1,
                    f"mpv_path {bad!r} must be rejected (fail-closed)",
                )

    def test_non_string_mpv_path_is_rejected(self) -> None:
        # A non-string mpv_path is a contract violation, not a benign absence.
        self.assertEqual(self._config_valid_rc('{"mpv_path": 123}'), 1)

    def test_unreadable_config_fails_closed(self) -> None:
        self.assertEqual(self._config_valid_rc("{ not valid json"), 1)

    def test_guard_is_fail_closed_when_validator_is_absent(self) -> None:
        # The inline fallback must still enforce the contract if the shipped
        # validator cannot be loaded, so the guard never fails open.
        self.assertEqual(
            self._config_valid_rc(self._config_with(mpv_path="mpv"), with_validator=False),
            1,
        )
        self.assertEqual(
            self._config_valid_rc(self._config_with(mpv_path=C18_WRAPPER), with_validator=False),
            0,
        )
        self.assertEqual(
            self._config_valid_rc(self._config_with(), with_validator=False),
            0,
        )

    def test_launcher_reuses_shipped_contract_validator(self) -> None:
        text = INNER_LAUNCHER_PATH.read_text(encoding="utf-8")
        self.assertIn("validate_c18_mpv_path_contract", text)
        self.assertIn("TOTEM_CONFIG_CONTRACT_VALIDATOR", text)


def load_candidate_health_module():
    spec = importlib.util.spec_from_file_location(
        "c18_candidate_health_under_test", CANDIDATE_HEALTH_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load candidate_health spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CandidateHealthAccessPreflightTest(unittest.TestCase):
    """Regression for the 2026-06-10 board A/B diagnosis: the candidate-health runner must
    (a) capture the candidate's stdout/stderr instead of DEVNULL, and (b) fail with an explicit
    SETUP error when the run_user cannot reach the candidate workspace (the /root-0700 trap that
    previously surfaced as a generic all-checks-failed health failure)."""

    @classmethod
    def setUpClass(cls) -> None:
        import pwd

        cls.ch = load_candidate_health_module()
        cls.run_user = pwd.getpwuid(os.getuid())

    def test_targets_cover_required_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work_root = Path(td) / "wr"
            work_root.mkdir()
            cfg = self.ch.candidate_config(None, work_root)
            release_dir = Path(td) / "release"
            release_dir.mkdir()
            (release_dir / "kiosk.py").write_text("print('x')\n", encoding="utf-8")
            config_path = work_root / "candidate-config.json"
            config_path.write_text("{}", encoding="utf-8")
            canary = Path(td) / "c.mp4"
            canary.write_text("x", encoding="utf-8")
            labels = {
                label
                for (label, _p, _m) in self.ch.access_check_targets(
                    cfg, release_dir, work_root, config_path, canary
                )
            }
            for required in (
                "release_dir_traverse",
                "release_kiosk_py_read",
                "work_root_write",
                "config_path_read",
                "state_dir_write",
                "runtime_dir_write",
                "ipc_dir_write",
                "log_dir_write",
                "mpv_log_dir_write",
                "status_dir_write",
                "canary_media_read",
            ):
                self.assertIn(required, labels)
            labels_no_canary = {
                label
                for (label, _p, _m) in self.ch.access_check_targets(
                    cfg, release_dir, work_root, config_path, None
                )
            }
            self.assertNotIn("canary_media_read", labels_no_canary)

    def test_all_accessible_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            kiosk = base / "kiosk.py"
            kiosk.write_text("print('x')\n", encoding="utf-8")
            cfg_path = base / "config.json"
            cfg_path.write_text("{}", encoding="utf-8")
            targets = [
                ("release_dir_traverse", base, os.X_OK),
                ("release_kiosk_py_read", kiosk, os.R_OK),
                ("work_root_write", base, os.W_OK | os.X_OK),
                ("config_path_read", cfg_path, os.R_OK),
            ]
            self.assertEqual(self.ch.access_failures_as_user(targets, self.run_user), [])

    def test_nonexistent_target_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bogus = Path(td) / "nope" / "kiosk.py"
            failures = self.ch.access_failures_as_user(
                [("release_kiosk_py_read", bogus, os.R_OK)], self.run_user
            )
            self.assertIn("release_kiosk_py_read", failures)

    @unittest.skipIf(
        os.geteuid() == 0,
        "root traverses 0700 dirs; the non-traversable case is meaningful only unprivileged",
    )
    def test_workdir_under_nontraversable_dir_reported(self) -> None:
        # Reproduce the board trap: a work_root beneath a non-traversable directory.
        with tempfile.TemporaryDirectory() as td:
            blocked = Path(td) / "blocked"
            inner = blocked / "work"
            inner.mkdir(parents=True)
            os.chmod(blocked, 0o000)
            try:
                failures = self.ch.access_failures_as_user(
                    [("work_root_write", inner, os.W_OK | os.X_OK)], self.run_user
                )
                self.assertIn("work_root_write", failures)
            finally:
                os.chmod(blocked, 0o755)

    def test_setup_failure_result_names_setup_error(self) -> None:
        identity = {"kiosk_py_sha256": "a", "tree_sha256": "b", "version": "v"}
        result = self.ch.setup_failure_result(
            identity, self.run_user, True, ["work_root_write", "work_root_write"]
        )
        self.assertIs(result["passed"], False)
        self.assertEqual(
            result["failure_reasons"], ["candidate_setup_inaccessible_to_run_user"]
        )
        self.assertEqual(result["setup_error"], "candidate_setup_inaccessible_to_run_user")
        self.assertEqual(result["inaccessible_targets"], ["work_root_write"])
        self.assertIs(result["checks"]["candidate_setup_accessible_to_run_user"], False)

    def test_source_captures_candidate_streams_not_devnull(self) -> None:
        text = CANDIDATE_HEALTH_PATH.read_text(encoding="utf-8")
        self.assertIn("candidate-stderr.txt", text)
        self.assertIn("candidate-stdout.txt", text)
        self.assertNotIn("stdout=subprocess.DEVNULL", text)
        self.assertNotIn("stderr=subprocess.DEVNULL", text)
        self.assertIn("candidate_setup_inaccessible_to_run_user", text)

    def test_candidate_health_supplies_isolated_watchdog_state_to_collector(self) -> None:
        text = CANDIDATE_HEALTH_PATH.read_text(encoding="utf-8")
        self.assertIn('watchdog_state=work_root / "status-mpv-watchdog.json"', text)
        self.assertIn("access_failures_as_user", text)
        # The setup failure must RAISE (so the apply path aborts via deep_health_exception without
        # quarantining the identity), not return passed=False (which would quarantine).
        self.assertIn("class CandidateSetupInaccessibleError", text)
        self.assertIn("raise CandidateSetupInaccessibleError", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
