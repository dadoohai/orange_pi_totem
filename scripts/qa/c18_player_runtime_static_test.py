#!/usr/bin/env python3
"""C18 player-runtime static governance checks.

This is an offline guard for the governed C18 player snapshot. It does not
enable player OTA and must stay separate from the ordinary totem-core OTA path.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import py_compile
import re
import subprocess
import tempfile
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
CURRENT_GOLDEN_PATH = REPO_ROOT / "docs" / "evidence" / "c18-update-validation" / "current-golden.json"
CURRENT_GOLDEN = json.loads(CURRENT_GOLDEN_PATH.read_text(encoding="utf-8"))
C18_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
EXPECTED_SNAPSHOT_SHA256 = "06e1aadfe15f76d7284d2692dfe5987c9e3c8efd44e8486469b50cf309c246d4"
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
        self.assertIn('"loadfile", path, "replace"', text)

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
        self.assertIn('panfrost_fault_policy="absolute"', candidate_health)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
