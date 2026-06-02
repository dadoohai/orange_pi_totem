#!/usr/bin/env python3
"""C18 tests for OTA freeze, downgrade policy and incoming cleanup."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UPDATECTL_PATH = REPO_ROOT / "scripts" / "board" / "totem_updatectl.py"

spec = importlib.util.spec_from_file_location("totem_updatectl_c18_test", UPDATECTL_PATH)
assert spec and spec.loader
updatectl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updatectl)


def configure_temp(root: Path, component: str = "totem-core") -> None:
    data_root = root / "data"
    updatectl.DATA_ROOT = data_root
    updatectl.UPDATES_DIR = data_root / "updates"
    updatectl.POLICY_FILE = updatectl.UPDATES_DIR / "policy.json"
    updatectl.LOG_DIR = data_root / "logs"
    updatectl.LOG_FILE = updatectl.LOG_DIR / "totem-update.log"
    updatectl.TOKEN_FILE = data_root / "secrets" / "github-release-token"
    updatectl.configure_component(component)


def policy(*, allow_downgrade: bool = False) -> dict:
    return {
        "schema": "dadooh.totem.update.policy.v1",
        "device_channel": "stable",
        "allowed_components": ["totem-core"],
        "allow_prerelease": False,
        "allow_downgrade": allow_downgrade,
    }


def manifest(version: str, sha: str = "a" * 64, *, created_at: str | None = "2026-06-02T10:00:00Z") -> dict:
    data: dict[str, object] = {
        "schema": "dadooh.totem.update.v1",
        "component": "totem-core",
        "version": version,
        "channel": "stable",
        "payload": f"dadooh-totem-core-{version}.tar.gz",
        "payload_sha256": sha,
        "payload_bytes": 1,
        "entrypoint": "bin/totem_setup_visual_wizard.py",
        "requires": {"device": "orangepizero3", "base_image_min": "c17.4.2"},
        "updates": ["test"],
    }
    if created_at is not None:
        data["created_at_utc"] = created_at
    return data


class C18UpdatectlFreezeDowngradeGcTest(unittest.TestCase):
    def test_kiosky_player_apply_local_is_frozen_before_manifest_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "kiosky-player")
            args = argparse.Namespace(component="kiosky-player", manifest=str(root / "missing.json"), payload="")
            rc = updatectl.cmd_apply_local(args)
            self.assertEqual(rc, 44)
            self.assertFalse((root / "data" / "apps" / "kiosky-player").exists())

    def test_downgrade_rejects_previous_identity_without_policy_permission(self) -> None:
        state = {
            "current": {
                "version": "core-new",
                "payload_sha256": "b" * 64,
                "manifest_created_at_utc": "2026-06-02T11:00:00Z",
            },
            "previous": {
                "version": "core-old",
                "payload_sha256": "a" * 64,
                "manifest_created_at_utc": "2026-06-02T10:00:00Z",
            },
        }
        ok, reason = updatectl._downgrade_policy_allows_manifest(policy(), manifest("core-old"), state)
        self.assertFalse(ok)
        self.assertEqual(reason, "downgrade_not_allowed_by_policy")

    def test_downgrade_allows_previous_identity_when_policy_allows(self) -> None:
        state = {
            "current": {"version": "core-new", "payload_sha256": "b" * 64},
            "previous": {"version": "core-old", "payload_sha256": "a" * 64},
        }
        ok, reason = updatectl._downgrade_policy_allows_manifest(
            policy(allow_downgrade=True),
            manifest("core-old"),
            state,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "previous_identity_allowed_by_policy")

    def test_same_version_different_sha_is_always_rejected(self) -> None:
        state = {"current": {"version": "core-a", "payload_sha256": "b" * 64}}
        ok, reason = updatectl._downgrade_policy_allows_manifest(
            policy(allow_downgrade=True),
            manifest("core-a", sha="a" * 64),
            state,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "current_version_payload_sha256_mismatch")

    def test_older_created_at_is_rejected_without_downgrade_permission(self) -> None:
        state = {
            "current": {
                "version": "core-new",
                "payload_sha256": "b" * 64,
                "manifest_created_at_utc": "2026-06-02T12:00:00Z",
            }
        }
        ok, reason = updatectl._downgrade_policy_allows_manifest(
            policy(),
            manifest("core-unknown-old", created_at="2026-06-02T11:59:59Z"),
            state,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "downgrade_not_allowed_by_policy")

    def test_missing_candidate_created_at_is_rejected_when_current_has_created_at(self) -> None:
        state = {
            "current": {
                "version": "core-new",
                "payload_sha256": "b" * 64,
                "manifest_created_at_utc": "2026-06-02T12:00:00Z",
            }
        }
        ok, reason = updatectl._downgrade_policy_allows_manifest(
            policy(),
            manifest("core-no-date", created_at=None),
            state,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "candidate_created_at_required_to_rule_out_downgrade")

    def test_cleanup_stage_removes_only_requested_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "totem-core")
            stage = updatectl.INCOMING_DIR / "core-stage"
            other = updatectl.INCOMING_DIR / "other-stage"
            stage.mkdir(parents=True)
            other.mkdir(parents=True)
            (stage / "payload").write_text("x", encoding="utf-8")
            (other / "payload").write_text("y", encoding="utf-8")

            updatectl._cleanup_stage(stage)

            self.assertFalse(stage.exists())
            self.assertTrue(other.is_dir())

    def test_cleanup_stage_refuses_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "totem-core")
            outside = root / "outside"
            outside.mkdir()
            stage = updatectl.INCOMING_DIR / "escape"
            stage.parent.mkdir(parents=True)
            stage.symlink_to(outside, target_is_directory=True)

            updatectl._cleanup_stage(stage)

            self.assertTrue(outside.is_dir())
            self.assertTrue(stage.is_symlink())

    def test_apply_sha_mismatch_cleans_payload_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "totem-core")
            updatectl.POLICY_FILE.parent.mkdir(parents=True)
            updatectl.POLICY_FILE.write_text(json.dumps(policy(), sort_keys=True) + "\n", encoding="utf-8")
            pkg_dir = root / "pkg"
            pkg_dir.mkdir()
            bad_payload = pkg_dir / "dadooh-totem-core-core-bad.tar.gz"
            bad_payload.write_bytes(b"bad")
            bad_manifest = manifest("core-bad", sha="a" * 64)
            manifest_path = pkg_dir / "dadooh-totem-core-core-bad.manifest.json"
            manifest_path.write_text(json.dumps(bad_manifest, sort_keys=True) + "\n", encoding="utf-8")

            rc = updatectl._apply_from_manifest_path(
                manifest_path,
                payload_url=None,
                source="local-test",
                payload_path_override=bad_payload,
            )

            self.assertEqual(rc, 6)
            self.assertFalse((updatectl.INCOMING_DIR / "core-bad").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
