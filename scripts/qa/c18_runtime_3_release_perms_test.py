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
import json
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
    def test_player_runtime_base_dirs_are_traversable_after_ensure_dirs(self) -> None:
        old_umask = os.umask(0o077)
        saved = {
            "DATA_ROOT": updatectl.DATA_ROOT,
            "UPDATES_DIR": updatectl.UPDATES_DIR,
            "POLICY_FILE": updatectl.POLICY_FILE,
            "LOG_DIR": updatectl.LOG_DIR,
            "LOG_FILE": updatectl.LOG_FILE,
            "TOKEN_FILE": updatectl.TOKEN_FILE,
            "COMPONENT": updatectl.COMPONENT,
            "APP_BASE": updatectl.APP_BASE,
            "RELEASES_DIR": updatectl.RELEASES_DIR,
            "CURRENT_LINK": updatectl.CURRENT_LINK,
            "PREVIOUS_LINK": updatectl.PREVIOUS_LINK,
            "STATE_FILE": updatectl.STATE_FILE,
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                updatectl.DATA_ROOT = root / "data"
                updatectl.UPDATES_DIR = updatectl.DATA_ROOT / "updates"
                updatectl.POLICY_FILE = updatectl.UPDATES_DIR / "policy.json"
                updatectl.LOG_DIR = updatectl.DATA_ROOT / "logs"
                updatectl.LOG_FILE = updatectl.LOG_DIR / "totem-update.log"
                updatectl.TOKEN_FILE = updatectl.DATA_ROOT / "secrets" / "github-release-token"
                updatectl.configure_component("player-runtime")

                updatectl._ensure_dirs()

                self.assertEqual(stat.S_IMODE(updatectl.APP_BASE.stat().st_mode) & 0o005, 0o005)
                self.assertEqual(stat.S_IMODE(updatectl.RELEASES_DIR.stat().st_mode) & 0o005, 0o005)
        finally:
            os.umask(old_umask)
            for key, value in saved.items():
                setattr(updatectl, key, value)

    def test_player_runtime_internal_apply_normalizes_base_dirs(self) -> None:
        old_umask = os.umask(0o077)
        saved = {
            "DATA_ROOT": updatectl.DATA_ROOT,
            "UPDATES_DIR": updatectl.UPDATES_DIR,
            "POLICY_FILE": updatectl.POLICY_FILE,
            "LOG_DIR": updatectl.LOG_DIR,
            "LOG_FILE": updatectl.LOG_FILE,
            "TOKEN_FILE": updatectl.TOKEN_FILE,
            "COMPONENT": updatectl.COMPONENT,
            "APP_BASE": updatectl.APP_BASE,
            "RELEASES_DIR": updatectl.RELEASES_DIR,
            "CURRENT_LINK": updatectl.CURRENT_LINK,
            "PREVIOUS_LINK": updatectl.PREVIOUS_LINK,
            "STATE_FILE": updatectl.STATE_FILE,
            "PLAYER_RUNTIME_HEALTH_HOOK": updatectl.PLAYER_RUNTIME_HEALTH_HOOK,
            "PLAYER_RUNTIME_LAB_THAW_ENABLED": updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED,
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                updatectl.DATA_ROOT = root / "data"
                updatectl.UPDATES_DIR = updatectl.DATA_ROOT / "updates"
                updatectl.POLICY_FILE = updatectl.UPDATES_DIR / "policy.json"
                updatectl.LOG_DIR = updatectl.DATA_ROOT / "logs"
                updatectl.LOG_FILE = updatectl.LOG_DIR / "totem-update.log"
                updatectl.TOKEN_FILE = updatectl.DATA_ROOT / "secrets" / "github-release-token"
                updatectl.configure_component("player-runtime")
                updatectl.POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
                updatectl.POLICY_FILE.write_text(json.dumps({
                    "schema": "dadooh.totem.update.policy.v1",
                    "device_channel": "homologation",
                    "device_track": "c18-hwdecode",
                    "allowed_components": ["player-runtime", "totem-core"],
                    "allow_prerelease": True,
                    "allow_downgrade": False,
                }), encoding="utf-8")

                payload = root / "dadooh-player-runtime-runtime-perms-test.tar.gz"
                _make_payload(payload)
                manifest = root / "manifest.json"
                manifest.write_text(json.dumps({
                    "schema": "dadooh.totem.update.v1",
                    "component": "player-runtime",
                    "version": "runtime-perms-test",
                    "channel": "homologation",
                    "created_at_utc": "2026-06-05T00:00:00Z",
                    "source_repo": "dadoohai/orange_pi_totem",
                    "source_branch": "foundation-v0.1",
                    "source_commit": "1" * 40,
                    "source_dirty": False,
                    "payload": payload.name,
                    "payload_sha256": updatectl._sha256_file(payload),
                    "payload_bytes": payload.stat().st_size,
                    "requires": {
                        "device": "orangepizero3",
                        "base_image_min": "c17.4.2",
                        "device_track": "c18-hwdecode",
                        "updater_features": [
                            "c18-freeze-kiosky-player-v1",
                            "c18-rollback-reapply-v1",
                            "c18-safe-payload-v1",
                            "c18-track-v1",
                            "c18-player-runtime-verify-then-promote-v1",
                        ],
                        "media_stack_id": "c18-hwdecode-v4l2request-copy",
                        "mpv_wrapper": "/opt/totem/bin/totem-mpv-hwdecode",
                        "hwdec": "v4l2request-copy",
                        "vo": "gpu",
                        "gpu_context": "drm",
                        "deep_health_schema": "dadooh.c18.playback.deep_health.v1",
                    },
                    "entrypoint": "kiosk.py",
                    "updates": ["kiosk.py"],
                    "health_checks": ["playback_deep_health"],
                }), encoding="utf-8")

                updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
                updatectl.PLAYER_RUNTIME_HEALTH_HOOK = lambda _release_dir, _identity: {
                    "passed": False,
                    "failure_reasons": ["fixture_reject"],
                }

                rc = updatectl._apply_player_runtime_from_manifest_path_unfrozen(
                    manifest,
                    payload_url=None,
                    source="fixture",
                    payload_path_override=payload,
                )

                self.assertEqual(rc, 11)
                self.assertEqual(stat.S_IMODE(updatectl.APP_BASE.stat().st_mode) & 0o005, 0o005)
                self.assertEqual(stat.S_IMODE(updatectl.RELEASES_DIR.stat().st_mode) & 0o005, 0o005)
        finally:
            os.umask(old_umask)
            for key, value in saved.items():
                setattr(updatectl, key, value)

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
