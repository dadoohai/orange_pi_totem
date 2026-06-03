#!/usr/bin/env python3
"""C18 tests for OTA freeze, downgrade policy and incoming cleanup."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
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
        "device_track": "c18-hwdecode",
        "allowed_components": ["totem-core"],
        "allow_prerelease": False,
        "allow_downgrade": allow_downgrade,
    }


def manifest(
    version: str,
    sha: str = "a" * 64,
    *,
    created_at: str | None = "2026-06-02T10:00:00Z",
    payload: str | None = None,
) -> dict:
    data: dict[str, object] = {
        "schema": "dadooh.totem.update.v1",
        "component": "totem-core",
        "version": version,
        "channel": "stable",
        "payload": payload or f"dadooh-totem-core-{version}.tar.gz",
        "payload_sha256": sha,
        "payload_bytes": 1,
        "entrypoint": "bin/totem_setup_visual_wizard.py",
        "requires": {
            "device": "orangepizero3",
            "base_image_min": "c17.4.2",
            "device_track": "c18-hwdecode",
            "updater_features": [
                "c18-freeze-kiosky-player-v1",
                "c18-rollback-reapply-v1",
                "c18-safe-payload-v1",
                "c18-track-v1",
            ],
        },
        "updates": ["test"],
    }
    if created_at is not None:
        data["created_at_utc"] = created_at
    return data


def player_runtime_manifest(version: str, *, hwdec: str = "v4l2request-copy") -> dict:
    return {
        "schema": "dadooh.totem.update.v1",
        "component": "player-runtime",
        "version": version,
        "channel": "stable",
        "created_at_utc": "2026-06-02T10:00:00Z",
        "payload": f"dadooh-player-runtime-{version}.tar.gz",
        "payload_sha256": "a" * 64,
        "payload_bytes": 1,
        "entrypoint": "kiosk.py",
        "requires": {
            "device": "orangepizero3",
            "base_image_min": "c17.4.2",
            "device_track": "c18-hwdecode",
            "media_stack_id": "c18-hwdecode-v4l2request-copy",
            "mpv_wrapper": "/opt/totem/bin/totem-mpv-hwdecode",
            "hwdec": hwdec,
            "vo": "gpu",
            "gpu_context": "drm",
            "deep_health_schema": "dadooh.c18.playback.deep_health.v1",
        },
    }


class C18UpdatectlFreezeDowngradeGcTest(unittest.TestCase):
    def test_kiosky_player_apply_local_is_frozen_before_manifest_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "kiosky-player")
            args = argparse.Namespace(component="kiosky-player", manifest=str(root / "missing.json"), payload="")
            rc = updatectl.cmd_apply_local(args)
            self.assertEqual(rc, 44)
            self.assertFalse((root / "data" / "apps" / "kiosky-player").exists())

    def test_player_runtime_apply_local_is_frozen_before_manifest_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "player-runtime")
            args = argparse.Namespace(component="player-runtime", manifest=str(root / "missing.json"), payload="")
            rc = updatectl.cmd_apply_local(args)
            self.assertEqual(rc, 44)
            self.assertFalse((root / "data" / "player-runtime").exists())

    def test_player_runtime_rollback_is_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "player-runtime")
            args = argparse.Namespace(component="player-runtime")
            rc = updatectl.cmd_rollback(args)
            self.assertEqual(rc, 44)

    def test_policy_may_name_player_runtime_but_apply_stays_frozen(self) -> None:
        raw = policy()
        raw["allowed_components"] = ["totem-core", "player-runtime"]
        normalised = updatectl._normalise_policy(raw)
        self.assertEqual(normalised["allowed_components"], ["player-runtime", "totem-core"])

    def test_player_runtime_manifest_requires_media_stack_contract(self) -> None:
        raw_policy = policy()
        raw_policy["allowed_components"] = ["player-runtime"]
        good_policy = updatectl._normalise_policy(raw_policy)
        updatectl._validate_manifest(
            player_runtime_manifest("player-good"),
            policy=good_policy,
            component="player-runtime",
        )
        with self.assertRaisesRegex(RuntimeError, "requires hwdec"):
            updatectl._validate_manifest(
                player_runtime_manifest("player-bad", hwdec="no"),
                policy=good_policy,
                component="player-runtime",
            )

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

    def test_reapply_newer_previous_identity_after_rollback_is_allowed(self) -> None:
        state = {
            "current": {
                "version": "core-old",
                "payload_sha256": "a" * 64,
                "manifest_created_at_utc": "2026-06-02T10:00:00Z",
            },
            "previous": {
                "version": "core-new",
                "payload_sha256": "b" * 64,
                "manifest_created_at_utc": "2026-06-02T11:00:00Z",
            },
        }
        ok, reason = updatectl._downgrade_policy_allows_manifest(
            policy(),
            manifest("core-new", sha="b" * 64, created_at="2026-06-02T11:00:00Z"),
            state,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "previous_identity_not_older_than_current")

    def test_same_version_different_sha_is_always_rejected(self) -> None:
        state = {"current": {"version": "core-a", "payload_sha256": "b" * 64}}
        ok, reason = updatectl._downgrade_policy_allows_manifest(
            policy(allow_downgrade=True),
            manifest("core-a", sha="a" * 64),
            state,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "current_version_payload_sha256_mismatch")

    def test_manifest_rejects_release_dir_version_hazards(self) -> None:
        for version in (".", "..", "-bad", "bad/name", "bad..name", ""):
            with self.subTest(version=version):
                with self.assertRaisesRegex(RuntimeError, "unsafe version string"):
                    updatectl._validate_manifest(manifest(version), policy=policy(), component="totem-core")

    def test_manifest_rejects_payload_path_hazards(self) -> None:
        for payload_name in ("../evil.tar.gz", "/tmp/evil.tar.gz", "nested/evil.tar.gz", ".", "evil.tar.gz"):
            with self.subTest(payload=payload_name):
                with self.assertRaisesRegex(RuntimeError, "payload name"):
                    updatectl._validate_manifest(
                        manifest("core-safe", payload=payload_name),
                        policy=policy(),
                        component="totem-core",
                    )

    def test_totem_core_manifest_requires_track_features_and_supported_base(self) -> None:
        cases = [
            ("missing-track", lambda m: m["requires"].pop("device_track"), "requires device_track"),
            ("missing-features", lambda m: m["requires"].pop("updater_features"), "requires updater_features"),
            (
                "missing-one-feature",
                lambda m: m["requires"]["updater_features"].pop(),
                "missing required updater features",
            ),
            (
                "unsupported-base",
                lambda m: m["requires"].__setitem__("base_image_min", "future-image-line"),
                "base_image_min requirement not met",
            ),
        ]
        for name, mutate, pattern in cases:
            with self.subTest(name=name):
                data = manifest(f"core-{name}")
                mutate(data)
                with self.assertRaisesRegex(RuntimeError, pattern):
                    updatectl._validate_manifest(data, policy=policy(), component="totem-core")

    def test_manifest_requires_created_at_utc_timestamp(self) -> None:
        cases = [
            ("missing", lambda m: m.pop("created_at_utc"), "missing fields.*created_at_utc"),
            ("empty", lambda m: m.__setitem__("created_at_utc", ""), "created_at_utc"),
            ("invalid", lambda m: m.__setitem__("created_at_utc", "not-a-time"), "created_at_utc"),
            ("naive", lambda m: m.__setitem__("created_at_utc", "2026-06-02T10:00:00"), "created_at_utc"),
        ]
        for name, mutate, pattern in cases:
            with self.subTest(name=name):
                data = manifest(f"core-created-at-{name}")
                mutate(data)
                with self.assertRaisesRegex(RuntimeError, pattern):
                    updatectl._validate_manifest(data, policy=policy(), component="totem-core")

    def test_policy_without_allowed_components_fails_closed(self) -> None:
        raw = policy()
        raw.pop("allowed_components")
        with self.assertRaisesRegex(RuntimeError, "allowed_components"):
            updatectl._normalise_policy(raw)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "totem-core")
            updatectl.POLICY_FILE.parent.mkdir(parents=True)
            updatectl.POLICY_FILE.write_text(json.dumps(raw, sort_keys=True) + "\n", encoding="utf-8")
            loaded = updatectl._load_update_policy()
            self.assertEqual(loaded["allowed_components"], [])
            self.assertEqual(loaded["policy_source"], "invalid_file_fail_closed_stable")
            with self.assertRaisesRegex(RuntimeError, "component_not_allowed_by_policy"):
                updatectl._validate_manifest(manifest("core-policy-missing-allowlist"), component="totem-core")

    def test_missing_policy_fails_closed_for_totem_core(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "totem-core")
            loaded = updatectl._load_update_policy()
            self.assertEqual(loaded["allowed_components"], [])
            with self.assertRaisesRegex(RuntimeError, "component_not_allowed_by_policy"):
                updatectl._validate_manifest(manifest("core-no-policy"), component="totem-core")

    def test_totem_core_health_check_does_not_require_player_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release = Path(tmp) / "release"
            bin_dir = release / "bin"
            bin_dir.mkdir(parents=True)
            for name in updatectl.TOTEM_CORE_REQUIRED_BIN:
                source = REPO_ROOT / "scripts" / "board" / name
                self.assertNotEqual(name, "kiosky_service_launcher.sh")
                shutil.copy2(source, bin_dir / name)

            ok, reason = updatectl._totem_core_health_check(release)

            self.assertTrue(ok, reason)

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
