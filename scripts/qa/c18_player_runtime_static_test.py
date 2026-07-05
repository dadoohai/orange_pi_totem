#!/usr/bin/env python3
"""C18 player-runtime static governance checks.

This is an offline guard for the governed C18 player snapshot. It does not
enable player OTA and must stay separate from the ordinary totem-core OTA path.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import py_compile
import re
import subprocess
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
INNER_LAUNCHER_PATH = REPO_ROOT / "scripts" / "board" / "kiosky_service_launcher.sh"
CONFIG_CONTRACT_VALIDATOR_PATH = REPO_ROOT / "scripts" / "board" / "totem_config_contract_validate.py"
CURRENT_GOLDEN_PATH = REPO_ROOT / "docs" / "evidence" / "c18-update-validation" / "current-golden.json"
CURRENT_GOLDEN = json.loads(CURRENT_GOLDEN_PATH.read_text(encoding="utf-8"))
C18_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
EXPECTED_SNAPSHOT_SHA256 = "7bc2384b6d4b81a7222d84cc89ef7e53dac18248c410e51041d9ee49a448f413"
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

    def wait_for_current_path(self, _path: str) -> bool:
        return False

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
        self.assertEqual(patches["DEFAULT_CONFIG.preload_next"]["to"], False)

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
        with tempfile.TemporaryDirectory(prefix="c18-playback-cache-index-") as tmp:
            cfg = {
                "state_dir": tmp,
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
