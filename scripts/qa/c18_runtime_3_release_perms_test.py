#!/usr/bin/env python3
"""C18.RUNTIME.3 — extracted releases must be traversable/readable by the non-root
service user (`totem`).

Regression guard for the bug found on the C17.4.2 board: the updater extracted
release dirs as 0700 root:root, so the `totem` service user could not traverse
`/data/apps/kiosky-player/current/kiosk.py`. The launcher then logged
"kiosk.py missing; falling back" and ran /opt, so pulled releases never took
effect. Fixtures are local; no GitHub, no device state.
"""

from __future__ import annotations

import importlib.util
import io
import os
import stat
import tarfile
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UPDATECTL_PATH = REPO_ROOT / "scripts" / "board" / "totem_updatectl.py"

spec = importlib.util.spec_from_file_location("totem_updatectl", UPDATECTL_PATH)
assert spec and spec.loader
updatectl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updatectl)


def _make_payload(path: Path) -> None:
    """A release tarball whose members carry restrictive perms (0600 file, 0700 dir)."""
    with tarfile.open(path, "w:gz") as tf:
        data = b"print('player')\n"
        ti = tarfile.TarInfo("kiosk.py")
        ti.size = len(data)
        ti.mode = 0o600
        tf.addfile(ti, io.BytesIO(data))

        td = tarfile.TarInfo("sub")
        td.type = tarfile.DIRTYPE
        td.mode = 0o700
        tf.addfile(td)

        d2 = b"asset"
        ti2 = tarfile.TarInfo("sub/data.bin")
        ti2.size = len(d2)
        ti2.mode = 0o600
        tf.addfile(ti2, io.BytesIO(d2))


class ReleasePermsTest(unittest.TestCase):
    def test_extracted_release_is_world_traversable_after_fix(self) -> None:
        old_umask = os.umask(0o077)  # reproduce the restrictive-umask condition
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                payload = root / "payload.tar.gz"
                _make_payload(payload)

                release_dir = root / "releases" / "v1"
                release_dir.mkdir(parents=True)  # 0700 under umask 077 = the bug
                self.assertEqual(
                    stat.S_IMODE(release_dir.stat().st_mode) & 0o005, 0,
                    "precondition: release dir starts NOT other-traversable",
                )

                updatectl._safe_extract_tar(payload, release_dir)

                # release dir + subdir must be other-traversable+readable (a+rX)
                self.assertEqual(stat.S_IMODE(release_dir.stat().st_mode) & 0o005, 0o005,
                                 "release dir must be o+rx for the service user")
                self.assertEqual(stat.S_IMODE((release_dir / "sub").stat().st_mode) & 0o005, 0o005,
                                 "subdir must be o+rx")
                # files must be other-readable
                self.assertEqual(stat.S_IMODE((release_dir / "kiosk.py").stat().st_mode) & 0o004, 0o004,
                                 "kiosk.py must be o+r")
                self.assertEqual(stat.S_IMODE((release_dir / "sub" / "data.bin").stat().st_mode) & 0o004, 0o004,
                                 "nested file must be o+r")
                # must NOT grant world-write, and non-executable files stay non-exec
                self.assertEqual(stat.S_IMODE(release_dir.stat().st_mode) & 0o002, 0,
                                 "must not be world-writable")
                self.assertEqual(stat.S_IMODE((release_dir / "kiosk.py").stat().st_mode) & 0o111, 0,
                                 "non-executable file must not gain execute bits")
        finally:
            os.umask(old_umask)

    def test_safe_extract_rejects_symlink_and_hardlink_members(self) -> None:
        for link_type in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            with self.subTest(link_type=link_type):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    payload = root / "payload.tar.gz"
                    with tarfile.open(payload, "w:gz") as tf:
                        data = b"ok\n"
                        ti = tarfile.TarInfo("regular.txt")
                        ti.size = len(data)
                        tf.addfile(ti, io.BytesIO(data))

                        link = tarfile.TarInfo("link")
                        link.type = link_type
                        link.linkname = "regular.txt"
                        tf.addfile(link)

                    with self.assertRaisesRegex(RuntimeError, "unsupported tar member type"):
                        updatectl._safe_extract_tar(payload, root / "out")


if __name__ == "__main__":
    unittest.main(verbosity=2)
