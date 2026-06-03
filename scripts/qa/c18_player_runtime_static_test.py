#!/usr/bin/env python3
"""C18 player-runtime static governance checks.

This is an offline guard for the governed C18 player snapshot. It does not
enable player OTA and must stay separate from the ordinary totem-core OTA path.
"""

from __future__ import annotations

import hashlib
import json
import py_compile
import re
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYER_DIR = REPO_ROOT / "player-runtime" / "kiosky-player"
KIOSK_PATH = PLAYER_DIR / "kiosk.py"
SOURCE_PATH = PLAYER_DIR / "SOURCE.json"
DERIVE_C18_PATH = REPO_ROOT / "scripts" / "build" / "derive_c18_image_lab_1_hwdecode.py"
RELEASE_GATE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_ota_release_gate.py"
C18_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
EXPECTED_SNAPSHOT_SHA256 = "ee1e24c34108c05aac1d92b4759f2c504d4158656b1f6ae010d93558e3892167"
EXPECTED_UPSTREAM_SHA256 = "38ecb0de3bfa4367d3ed61a173d2eb3210659026b8104f5c058881ca84470072"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source() -> dict:
    return json.loads(SOURCE_PATH.read_text(encoding="utf-8"))


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

    def test_c18_deriver_uses_governed_snapshot(self) -> None:
        derive = DERIVE_C18_PATH.read_text(encoding="utf-8")
        self.assertIn('TAG = "c18-hwdecode-lab-1l"', derive)
        self.assertIn('VERSION = "c18.image-lab.1l"', derive)
        self.assertIn('MARKER = "/etc/dadooh/c18-hwdecode-lab-1l-image"', derive)
        self.assertIn('PLAYER_RUNTIME_KIOSK = REPO_ROOT / "player-runtime" / "kiosky-player" / "kiosk.py"', derive)
        self.assertIn("PLAYER_RUNTIME_KIOSK_SHA256", derive)
        self.assertIn("governed player-runtime kiosk.py", derive)
        self.assertIn("player_runtime_snapshot_governed", derive)

    def test_c18_deriver_promotes_artifacts_only_after_offline_validation(self) -> None:
        derive = DERIVE_C18_PATH.read_text(encoding="utf-8")
        self.assertIn("OUT_SHA = Path(str(OUT_IMAGE) + \".sha256\")", derive)
        self.assertIn("tempfile.mkstemp", derive)
        self.assertIn("build_sha.write_text", derive)
        self.assertIn("os.replace(build_image, OUT_IMAGE)", derive)
        self.assertIn("offline validation failed; final image/sha256 not promoted", derive)
        self.assertLess(derive.index("offline_ok = all("), derive.index("os.replace(build_image, OUT_IMAGE)"))
        self.assertNotIn("shutil.copy2(BASE_IMAGE, OUT_IMAGE)", derive)
        self.assertNotIn("(Path(str(OUT_IMAGE) + \".sha256\")).write_text", derive)

    def test_common_ota_gate_tracks_player_runtime_boundary(self) -> None:
        gate = RELEASE_GATE_PATH.read_text(encoding="utf-8")
        self.assertIn('"scripts/qa/c18_player_runtime_static_test.py"', gate)
        self.assertIn('"player-runtime/kiosky-player/kiosk.py"', gate)
        self.assertIn('"player-runtime/kiosky-player/SOURCE.json"', gate)
        self.assertIn("c18_player_runtime_static", gate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
