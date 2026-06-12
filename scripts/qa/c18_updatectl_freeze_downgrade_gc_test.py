#!/usr/bin/env python3
"""C18 tests for OTA freeze, downgrade policy and incoming cleanup."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
import shutil
import tarfile
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


def player_runtime_manifest(
    version: str,
    *,
    hwdec: str = "v4l2request-copy",
    channel: str = "homologation",
) -> dict:
    return {
        "schema": "dadooh.totem.update.v1",
        "component": "player-runtime",
        "version": version,
        "channel": channel,
        "created_at_utc": "2026-06-02T10:00:00Z",
        "source_dirty": False,
        "payload": f"dadooh-player-runtime-{version}.tar.gz",
        "payload_sha256": "a" * 64,
        "payload_bytes": 1,
        "entrypoint": "kiosk.py",
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
            "hwdec": hwdec,
            "vo": "gpu",
            "gpu_context": "drm",
            "deep_health_schema": "dadooh.c18.playback.deep_health.v1",
        },
    }


def player_runtime_policy(*, allow_downgrade: bool = False) -> dict:
    raw = policy(allow_downgrade=allow_downgrade)
    raw["allowed_components"] = ["player-runtime"]
    raw["device_channel"] = "homologation"
    raw["allow_prerelease"] = True
    return raw


def write_player_runtime_policy(root: Path, *, allow_downgrade: bool = False) -> None:
    updatectl.POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
    updatectl.POLICY_FILE.write_text(
        json.dumps(player_runtime_policy(allow_downgrade=allow_downgrade), sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_verified_player_runtime_release(version: str, *, kiosk_text: str | None = None) -> tuple[Path, dict, dict]:
    release = updatectl.RELEASES_DIR / version
    release.mkdir(parents=True, exist_ok=True)
    (release / "kiosk.py").write_text(kiosk_text or f'print("{version}")\n', encoding="utf-8")
    raw_manifest = player_runtime_manifest(version)
    raw_manifest["payload_sha256"] = hashlib.sha256(version.encode("utf-8")).hexdigest()
    identity = updatectl._player_runtime_identity(release, raw_manifest)
    health = {
        "schema": updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
        "passed": True,
        "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
        "observed_tree_sha256": identity["tree_sha256"],
        "artifact_id": f"unit-{version}",
    }
    updatectl._write_player_runtime_marker(release, raw_manifest, identity, health)
    return release, raw_manifest, identity


def write_player_runtime_payload(root: Path, version: str, *, kiosk_text: str | None = None) -> tuple[Path, Path]:
    pkg = root / "pkg" / version
    src = pkg / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "kiosk.py").write_text(kiosk_text or f'print("{version}")\n', encoding="utf-8")
    payload = pkg / f"dadooh-player-runtime-{version}.tar.gz"
    with tarfile.open(payload, "w:gz") as tf:
        tf.add(src / "kiosk.py", arcname="kiosk.py")
    raw_manifest = player_runtime_manifest(version)
    raw_manifest["payload_sha256"] = updatectl._sha256_file(payload)
    raw_manifest["payload_bytes"] = payload.stat().st_size
    manifest_path = pkg / f"dadooh-player-runtime-{version}.manifest.json"
    manifest_path.write_text(json.dumps(raw_manifest, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path, payload


def passing_player_runtime_health(release_dir: Path, identity: dict) -> dict:
    return {
        "schema": updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
        "passed": True,
        "failure_reasons": [],
        "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
        "observed_tree_sha256": identity["tree_sha256"],
        "artifact_id": f"unit-health-{identity['version']}",
    }


class InjectedPowerCut(BaseException):
    pass


class C18UpdatectlFreezeDowngradeGcTest(unittest.TestCase):
    def test_kiosky_player_apply_local_is_frozen_before_manifest_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "kiosky-player")
            args = argparse.Namespace(component="kiosky-player", manifest=str(root / "missing.json"), payload="")
            rc = updatectl.cmd_apply_local(args)
            self.assertEqual(rc, 44)
            self.assertFalse((root / "data" / "apps" / "kiosky-player").exists())

    def test_kiosky_player_rollback_is_frozen_before_state_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "kiosky-player")
            args = argparse.Namespace(component="kiosky-player")
            rc = updatectl.cmd_rollback(args)
            self.assertEqual(rc, 44)
            self.assertFalse((root / "data" / "apps" / "kiosky-player").exists())

    def test_kiosky_player_reconcile_is_frozen_before_dir_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "kiosky-player")
            args = argparse.Namespace(component="kiosky-player", allow_player_runtime_maintenance=False)
            rc = updatectl.cmd_reconcile(args)
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

    def test_player_runtime_apply_url_and_github_are_frozen_before_io(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "player-runtime")
            rc_url = updatectl.cmd_apply_manifest_url(
                argparse.Namespace(component="player-runtime", url="https://example.invalid/manifest.json")
            )
            rc_gh = updatectl.cmd_apply_github_latest(
                argparse.Namespace(component="player-runtime", repo="dadoohai/example", dry_run=False)
            )
            self.assertEqual(rc_url, 44)
            self.assertEqual(rc_gh, 44)
            self.assertFalse((root / "data" / "player-runtime").exists())

    def test_player_runtime_rollback_is_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "player-runtime")
            args = argparse.Namespace(component="player-runtime")
            rc = updatectl.cmd_rollback(args)
            self.assertEqual(rc, 44)

    def test_player_runtime_reconcile_requires_explicit_maintenance_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "player-runtime")
            current = root / "data" / "player-runtime" / "releases" / "runtime-a"
            current.mkdir(parents=True)
            updatectl.CURRENT_LINK.parent.mkdir(parents=True, exist_ok=True)
            updatectl.CURRENT_LINK.symlink_to("releases/runtime-a")

            args = argparse.Namespace(component="player-runtime", allow_player_runtime_maintenance=False)
            rc = updatectl.cmd_reconcile(args)

            self.assertEqual(rc, 44)
            self.assertEqual(updatectl._read_symlink_target(updatectl.CURRENT_LINK), "releases/runtime-a")

    def test_player_runtime_reconcile_requires_both_flag_and_env(self) -> None:
        for name, env_value, allow_flag in (
            ("env_only", "1", False),
            ("flag_only", None, True),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                configure_temp(root, "player-runtime")
                current = root / "data" / "player-runtime" / "releases" / "runtime-a"
                current.mkdir(parents=True)
                updatectl.CURRENT_LINK.parent.mkdir(parents=True, exist_ok=True)
                updatectl.CURRENT_LINK.symlink_to("releases/runtime-a")

                old = os.environ.get(updatectl.PLAYER_RUNTIME_RECONCILE_ENV)
                try:
                    if env_value is None:
                        os.environ.pop(updatectl.PLAYER_RUNTIME_RECONCILE_ENV, None)
                    else:
                        os.environ[updatectl.PLAYER_RUNTIME_RECONCILE_ENV] = env_value
                    args = argparse.Namespace(
                        component="player-runtime",
                        allow_player_runtime_maintenance=allow_flag,
                    )
                    rc = updatectl.cmd_reconcile(args)
                finally:
                    if old is None:
                        os.environ.pop(updatectl.PLAYER_RUNTIME_RECONCILE_ENV, None)
                    else:
                        os.environ[updatectl.PLAYER_RUNTIME_RECONCILE_ENV] = old

                self.assertEqual(rc, 44)
                self.assertEqual(updatectl._read_symlink_target(updatectl.CURRENT_LINK), "releases/runtime-a")

    def test_player_runtime_reconcile_authorized_boot_hygiene_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "player-runtime")
            current = root / "data" / "player-runtime" / "releases" / "runtime-a"
            current.mkdir(parents=True)
            (current / "kiosk.py").write_text("print('unmarked')\n", encoding="utf-8")
            updatectl.CURRENT_LINK.parent.mkdir(parents=True, exist_ok=True)
            updatectl.CURRENT_LINK.symlink_to("releases/runtime-a")

            old = os.environ.get(updatectl.PLAYER_RUNTIME_RECONCILE_ENV)
            os.environ[updatectl.PLAYER_RUNTIME_RECONCILE_ENV] = "1"
            try:
                args = argparse.Namespace(component="player-runtime", allow_player_runtime_maintenance=True)
                rc = updatectl.cmd_reconcile(args)
            finally:
                if old is None:
                    os.environ.pop(updatectl.PLAYER_RUNTIME_RECONCILE_ENV, None)
                else:
                    os.environ[updatectl.PLAYER_RUNTIME_RECONCILE_ENV] = old

            self.assertEqual(rc, 0)
            self.assertFalse(updatectl.CURRENT_LINK.exists())
            state = updatectl._read_state()
            self.assertEqual(state["last_operation"]["status"], "image_fallback")

    def test_totem_core_rollback_to_image_fallback_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "totem-core")
            updatectl._ensure_dirs()
            release = updatectl.RELEASES_DIR / "core-current"
            release.mkdir(parents=True)
            updatectl._atomic_symlink("releases/core-current", updatectl.CURRENT_LINK)

            rc = updatectl.cmd_rollback(argparse.Namespace(component="totem-core"))

            self.assertEqual(rc, 0)
            self.assertFalse(updatectl.CURRENT_LINK.exists())
            self.assertEqual(updatectl._read_symlink_target(updatectl.PREVIOUS_LINK), "releases/core-current")
            state = updatectl._read_state()
            self.assertEqual(state["last_operation"]["rolled_back_to"], "fallback")

    def test_policy_may_name_player_runtime_but_apply_stays_frozen(self) -> None:
        raw = policy()
        raw["allowed_components"] = ["totem-core", "player-runtime"]
        normalised = updatectl._normalise_policy(raw)
        self.assertEqual(normalised["allowed_components"], ["player-runtime", "totem-core"])

    def test_player_runtime_manifest_requires_media_stack_contract(self) -> None:
        raw_policy = policy()
        raw_policy["allowed_components"] = ["player-runtime"]
        raw_policy["device_channel"] = "homologation"
        raw_policy["allow_prerelease"] = True
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

    def test_player_runtime_manifest_blocks_stable_on_device(self) -> None:
        good_policy = updatectl._normalise_policy(player_runtime_policy())
        with self.assertRaisesRegex(RuntimeError, "stable channel is blocked"):
            updatectl._validate_manifest(
                player_runtime_manifest("player-stable", channel="stable"),
                policy=good_policy,
                component="player-runtime",
            )

    def test_player_runtime_manifest_requires_runtime_updater_feature(self) -> None:
        good_policy = updatectl._normalise_policy(player_runtime_policy())
        candidate = player_runtime_manifest("player-missing-feature")
        candidate["requires"]["updater_features"] = [
            item for item in candidate["requires"]["updater_features"]
            if item != "c18-player-runtime-verify-then-promote-v1"
        ]
        with self.assertRaisesRegex(RuntimeError, "player-runtime manifest missing required updater features"):
            updatectl._validate_manifest(
                candidate,
                policy=good_policy,
                component="player-runtime",
            )

    def test_player_runtime_manifest_rejects_dirty_source(self) -> None:
        good_policy = updatectl._normalise_policy(player_runtime_policy())
        candidate = player_runtime_manifest("player-dirty-source")
        candidate["source_dirty"] = True
        with self.assertRaisesRegex(RuntimeError, "source_dirty must be false"):
            updatectl._validate_manifest(
                candidate,
                policy=good_policy,
                component="player-runtime",
            )

    def test_player_runtime_same_version_different_sha_is_rejected(self) -> None:
        state = {"current": {"version": "runtime-a", "payload_sha256": "b" * 64}}
        candidate = player_runtime_manifest("runtime-a")
        candidate["payload_sha256"] = "a" * 64
        ok, reason = updatectl._downgrade_policy_allows_manifest(
            policy(allow_downgrade=True),
            candidate,
            state,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "current_version_payload_sha256_mismatch")

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

    def test_player_runtime_lab_reapply_promotes_exact_previous_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "player-runtime")
            write_player_runtime_policy(root)
            updatectl._ensure_dirs()
            _release_a, manifest_a, identity_a = write_verified_player_runtime_release("runtime-a")
            _release_b, manifest_b, identity_b = write_verified_player_runtime_release("runtime-b")
            updatectl._atomic_symlink("releases/runtime-a", updatectl.CURRENT_LINK)
            updatectl._atomic_symlink("releases/runtime-b", updatectl.PREVIOUS_LINK)
            updatectl._write_state({
                "schema": updatectl.SCHEMA_STATE,
                "component": "player-runtime",
                "current": {
                    "version": "runtime-a",
                    "payload_sha256": manifest_a["payload_sha256"],
                    "kiosk_py_sha256": identity_a["kiosk_py_sha256"],
                    "tree_sha256": identity_a["tree_sha256"],
                },
                "previous": {
                    "version": "runtime-b",
                    "payload_sha256": manifest_b["payload_sha256"],
                    "kiosk_py_sha256": identity_b["kiosk_py_sha256"],
                    "tree_sha256": identity_b["tree_sha256"],
                    "manifest_created_at_utc": manifest_b["created_at_utc"],
                },
            })

            old_thaw = updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED
            old_health = updatectl.PLAYER_RUNTIME_HEALTH_HOOK
            try:
                updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
                updatectl.PLAYER_RUNTIME_HEALTH_HOOK = lambda _release, identity: {
                    "schema": updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
                    "passed": True,
                    "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
                    "observed_tree_sha256": identity["tree_sha256"],
                    "artifact_id": "unit-linked-previous-reapply",
                }
                rc = updatectl._apply_player_runtime_linked_previous_unfrozen(
                    manifest_b,
                    source="unit-reapply",
                )
            finally:
                updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = old_thaw
                updatectl.PLAYER_RUNTIME_HEALTH_HOOK = old_health

            self.assertEqual(rc, 0)
            self.assertEqual(updatectl._read_symlink_target(updatectl.CURRENT_LINK), "releases/runtime-b")
            self.assertEqual(updatectl._read_symlink_target(updatectl.PREVIOUS_LINK), "releases/runtime-a")
            state = updatectl._read_state()
            self.assertEqual((state.get("current") or {}).get("version"), "runtime-b")
            self.assertEqual((state.get("previous") or {}).get("version"), "runtime-a")
            self.assertTrue((state.get("current") or {}).get("lab_reapply_linked_previous"))
            ok, reason = updatectl._downgrade_policy_allows_manifest(
                updatectl._load_update_policy(),
                manifest_b,
                state,
            )
            self.assertTrue(ok)
            self.assertEqual(reason, "same_current_identity")

    def test_player_runtime_lab_reapply_setup_rejects_previous_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "player-runtime")
            write_player_runtime_policy(root)
            updatectl._ensure_dirs()
            _release_a, manifest_a, identity_a = write_verified_player_runtime_release("runtime-a")
            _release_b, manifest_b, identity_b = write_verified_player_runtime_release("runtime-b")
            updatectl._atomic_symlink("releases/runtime-a", updatectl.CURRENT_LINK)
            updatectl._atomic_symlink("releases/runtime-b", updatectl.PREVIOUS_LINK)
            updatectl._write_state({
                "schema": updatectl.SCHEMA_STATE,
                "component": "player-runtime",
                "current": {
                    "version": "runtime-a",
                    "payload_sha256": manifest_a["payload_sha256"],
                    "kiosk_py_sha256": identity_a["kiosk_py_sha256"],
                    "tree_sha256": identity_a["tree_sha256"],
                },
                "previous": {
                    "version": "runtime-b",
                    "payload_sha256": "f" * 64,
                    "kiosk_py_sha256": identity_b["kiosk_py_sha256"],
                    "tree_sha256": identity_b["tree_sha256"],
                },
            })

            old_thaw = updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED
            try:
                updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
                rc = updatectl._apply_player_runtime_linked_previous_unfrozen(manifest_b)
            finally:
                updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = old_thaw

            self.assertEqual(rc, 45)
            self.assertEqual(updatectl._read_symlink_target(updatectl.PREVIOUS_LINK), "releases/runtime-b")
            self.assertEqual((updatectl._read_state().get("previous") or {}).get("payload_sha256"), "f" * 64)

    def test_player_runtime_lab_reapply_health_failure_does_not_quarantine_verified_previous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "player-runtime")
            write_player_runtime_policy(root)
            updatectl._ensure_dirs()
            _release_a, manifest_a, identity_a = write_verified_player_runtime_release("runtime-a")
            _release_b, manifest_b, identity_b = write_verified_player_runtime_release("runtime-b")
            updatectl._atomic_symlink("releases/runtime-a", updatectl.CURRENT_LINK)
            updatectl._atomic_symlink("releases/runtime-b", updatectl.PREVIOUS_LINK)
            updatectl._write_state({
                "schema": updatectl.SCHEMA_STATE,
                "component": "player-runtime",
                "current": {
                    "version": "runtime-a",
                    "payload_sha256": manifest_a["payload_sha256"],
                    "kiosk_py_sha256": identity_a["kiosk_py_sha256"],
                    "tree_sha256": identity_a["tree_sha256"],
                },
                "previous": {
                    "version": "runtime-b",
                    "payload_sha256": manifest_b["payload_sha256"],
                    "kiosk_py_sha256": identity_b["kiosk_py_sha256"],
                    "tree_sha256": identity_b["tree_sha256"],
                },
            })

            old_thaw = updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED
            old_health = updatectl.PLAYER_RUNTIME_HEALTH_HOOK
            try:
                updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
                updatectl.PLAYER_RUNTIME_HEALTH_HOOK = lambda _release, identity: {
                    "schema": updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
                    "passed": False,
                    "failure_reasons": ["unit_transient_health_probe"],
                    "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
                    "observed_tree_sha256": identity["tree_sha256"],
                    "artifact_id": "unit-linked-previous-reapply-fail",
                }
                rc = updatectl._apply_player_runtime_linked_previous_unfrozen(
                    manifest_b,
                    source="unit-reapply",
                )
            finally:
                updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = old_thaw
                updatectl.PLAYER_RUNTIME_HEALTH_HOOK = old_health

            self.assertEqual(rc, 10)
            self.assertEqual(updatectl._read_symlink_target(updatectl.CURRENT_LINK), "releases/runtime-a")
            self.assertEqual(updatectl._read_symlink_target(updatectl.PREVIOUS_LINK), "releases/runtime-b")
            state = updatectl._read_state()
            self.assertEqual(updatectl._quarantine_entries(state), [])
            self.assertEqual((state.get("current") or {}).get("version"), "runtime-a")
            self.assertEqual((state.get("previous") or {}).get("version"), "runtime-b")
            self.assertEqual((state.get("last_operation") or {}).get("status"), "candidate_rejected")
            self.assertFalse((state.get("last_operation") or {}).get("quarantined_current"))

    def test_same_version_different_sha_is_always_rejected(self) -> None:
        state = {"current": {"version": "core-a", "payload_sha256": "b" * 64}}
        ok, reason = updatectl._downgrade_policy_allows_manifest(
            policy(allow_downgrade=True),
            manifest("core-a", sha="a" * 64),
            state,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "current_version_payload_sha256_mismatch")

    def test_player_runtime_marker_is_sha_bound_and_quarantine_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "player-runtime")
            release = root / "data" / "player-runtime" / "releases" / "runtime-a"
            release.mkdir(parents=True)
            (release / "kiosk.py").write_text('print("ok")\n', encoding="utf-8")
            raw_manifest = player_runtime_manifest("runtime-a")
            identity = updatectl._player_runtime_identity(release, raw_manifest)
            health = {
                "schema": updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
                "passed": True,
                "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
                "observed_tree_sha256": identity["tree_sha256"],
                "artifact_id": "unit",
            }
            updatectl._write_player_runtime_marker(release, raw_manifest, identity, health)
            ok, reason, _marker = updatectl._validate_player_runtime_marker(release, {"quarantine": []})
            self.assertTrue(ok, reason)

            (release / "kiosk.py").write_text('print("tampered")\n', encoding="utf-8")
            ok, reason, _marker = updatectl._validate_player_runtime_marker(release, {"quarantine": []})
            self.assertFalse(ok)
            self.assertEqual(reason, "kiosk_sha_mismatch")

    def test_player_runtime_torn_release_falls_back_on_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "player-runtime")
            release = root / "data" / "player-runtime" / "releases" / "runtime-a"
            release.mkdir(parents=True)
            (release / "kiosk.py").write_text('print("ok")\n', encoding="utf-8")
            (release / "asset.txt").write_text("asset\n", encoding="utf-8")
            raw_manifest = player_runtime_manifest("runtime-a")
            identity = updatectl._player_runtime_identity(release, raw_manifest)
            health = {
                "schema": updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
                "passed": True,
                "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
                "observed_tree_sha256": identity["tree_sha256"],
                "artifact_id": "unit",
            }
            updatectl._write_player_runtime_marker(release, raw_manifest, identity, health)
            updatectl._atomic_symlink("releases/runtime-a", updatectl.CURRENT_LINK)
            updatectl._write_state({
                "component": "player-runtime",
                "schema": updatectl.SCHEMA_STATE,
                "current": dict(identity),
            })

            (release / "asset.txt").unlink()
            rc, result = updatectl._reconcile_player_runtime_state(
                "unit_torn_release",
                allow_maintenance=True,
            )

            self.assertEqual(rc, 0)
            self.assertEqual(result["status"], "image_fallback")
            self.assertIsNone(result["current_link"])
            self.assertEqual(updatectl._read_symlink_target(updatectl.CURRENT_LINK), None)
            state = updatectl._read_state()
            self.assertIsNone(state["current"])
            self.assertEqual(result["reject_reason"], "tree_sha_mismatch")
            self.assertFalse(release.exists())

    def test_player_runtime_torn_current_adopts_verified_previous_and_discards_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "player-runtime")
            previous, _prev_manifest, _prev_identity = write_verified_player_runtime_release("runtime-a")
            current, _cur_manifest, _cur_identity = write_verified_player_runtime_release("runtime-b")
            (current / "asset.txt").write_text("asset\n", encoding="utf-8")
            raw_manifest = player_runtime_manifest("runtime-b")
            identity = updatectl._player_runtime_identity(current, raw_manifest)
            health = {
                "schema": updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
                "passed": True,
                "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
                "observed_tree_sha256": identity["tree_sha256"],
                "artifact_id": "unit-runtime-b",
            }
            updatectl._write_player_runtime_marker(current, raw_manifest, identity, health)
            updatectl._atomic_symlink("releases/runtime-a", updatectl.PREVIOUS_LINK)
            updatectl._atomic_symlink("releases/runtime-b", updatectl.CURRENT_LINK)

            (current / "asset.txt").unlink()
            rc, result = updatectl._reconcile_player_runtime_state(
                "unit_torn_current_with_previous",
                allow_maintenance=True,
            )

            self.assertEqual(rc, 0)
            self.assertEqual(result["status"], "previous_adopted")
            self.assertEqual(updatectl._read_symlink_target(updatectl.CURRENT_LINK), "releases/runtime-a")
            self.assertTrue(previous.is_dir())
            self.assertFalse(current.exists())

    def test_player_runtime_corrupt_state_fails_closed_even_with_verified_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configure_temp(root, "player-runtime")
            current, _manifest, _identity = write_verified_player_runtime_release("runtime-a")
            updatectl._atomic_symlink("releases/runtime-a", updatectl.CURRENT_LINK)
            updatectl.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            updatectl.STATE_FILE.write_text("{not-json", encoding="utf-8")

            rc, result = updatectl._reconcile_player_runtime_state(
                "unit_state_corruption",
                allow_maintenance=True,
            )

            self.assertEqual(rc, 0)
            self.assertEqual(result["status"], "image_fallback")
            self.assertEqual(result["reject_reason"], "state_file_corrupt_fail_closed")
            self.assertIsNone(updatectl._read_symlink_target(updatectl.CURRENT_LINK))
            self.assertFalse(current.exists())
            state = updatectl._read_state()
            self.assertIsNone(state["current"])
            self.assertIsNone(state["previous"])

    def test_player_runtime_quarantine_is_content_based(self) -> None:
        state: dict = {}
        identity = {
            "version": "runtime-a",
            "payload_sha256": "a" * 64,
            "kiosk_py_sha256": "b" * 64,
            "tree_sha256": "c" * 64,
        }
        updatectl._quarantine_player_runtime_identity(state, identity, "unit")
        same_content_new_version = dict(identity)
        same_content_new_version["version"] = "runtime-b"
        ok, reason = updatectl._player_runtime_is_quarantined(same_content_new_version, state)
        self.assertTrue(ok)
        self.assertIn(reason, {"payload_sha256_quarantined", "tree_sha256_quarantined"})

    def test_player_runtime_apply_fault_injection_never_adopts_unverified_release(self) -> None:
        labels = [
            "after_payload_staged",
            "after_release_dir_created",
            "after_extract",
            "after_state_verifying",
            "after_health_passed",
            "after_release_tree_fsync",
            "after_marker_written",
            "after_previous_symlink",
            "after_current_symlink",
            "after_state_success",
            "before_stage_cleanup",
        ]
        for label in labels:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                configure_temp(root, "player-runtime")
                write_player_runtime_policy(root)
                write_verified_player_runtime_release("runtime-a")
                updatectl._atomic_symlink("releases/runtime-a", updatectl.CURRENT_LINK)
                updatectl._write_state({
                    "component": "player-runtime",
                    "schema": updatectl.SCHEMA_STATE,
                    "current": {"version": "runtime-a"},
                })
                manifest_path, payload_path = write_player_runtime_payload(root, "runtime-b")
                seen: list[str] = []

                def fault_hook(observed: str, _context: dict) -> None:
                    seen.append(observed)
                    if observed == label:
                        raise InjectedPowerCut(label)

                old_thaw = updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED
                old_health = updatectl.PLAYER_RUNTIME_HEALTH_HOOK
                old_fault = updatectl.PLAYER_RUNTIME_FAULT_HOOK
                try:
                    updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
                    updatectl.PLAYER_RUNTIME_HEALTH_HOOK = passing_player_runtime_health
                    updatectl.PLAYER_RUNTIME_FAULT_HOOK = fault_hook
                    with self.assertRaises(InjectedPowerCut):
                        updatectl._apply_from_manifest_path_unfrozen(
                            manifest_path,
                            payload_url=None,
                            source="unit-fault",
                            payload_path_override=payload_path,
                        )
                finally:
                    updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = old_thaw
                    updatectl.PLAYER_RUNTIME_HEALTH_HOOK = old_health
                    updatectl.PLAYER_RUNTIME_FAULT_HOOK = old_fault

                self.assertIn(label, seen)
                rc, _result = updatectl._reconcile_player_runtime_state(
                    f"unit_apply_fault_{label}",
                    allow_maintenance=True,
                )
                self.assertEqual(rc, 0)
                current = updatectl._read_symlink_target(updatectl.CURRENT_LINK)
                if current:
                    ok, reason, _marker = updatectl._validate_player_runtime_marker(
                        updatectl.APP_BASE / current,
                        updatectl._read_state(),
                    )
                    self.assertTrue(ok, f"{label}: {reason}")

    def test_player_runtime_rollback_fault_injection_never_keeps_quarantined_current(self) -> None:
        labels = [
            "rollback_after_identify_links",
            "rollback_after_current_to_previous",
            "rollback_after_previous_removed",
            "rollback_after_quarantine",
            "rollback_after_state_success",
        ]
        for label in labels:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                configure_temp(root, "player-runtime")
                write_verified_player_runtime_release("runtime-a")
                _current, _manifest, current_identity = write_verified_player_runtime_release("runtime-b")
                updatectl._atomic_symlink("releases/runtime-a", updatectl.PREVIOUS_LINK)
                updatectl._atomic_symlink("releases/runtime-b", updatectl.CURRENT_LINK)
                updatectl._write_state({
                    "component": "player-runtime",
                    "schema": updatectl.SCHEMA_STATE,
                    "current": {"version": "runtime-b"},
                    "previous": {"version": "runtime-a"},
                })
                seen: list[str] = []

                def fault_hook(observed: str, _context: dict) -> None:
                    seen.append(observed)
                    if observed == label:
                        raise InjectedPowerCut(label)

                old_thaw = updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED
                old_fault = updatectl.PLAYER_RUNTIME_FAULT_HOOK
                try:
                    updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
                    updatectl.PLAYER_RUNTIME_FAULT_HOOK = fault_hook
                    with self.assertRaises(InjectedPowerCut):
                        updatectl._rollback_player_runtime_unfrozen(
                            reason="unit_fault",
                            quarantine_current=True,
                        )
                finally:
                    updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = old_thaw
                    updatectl.PLAYER_RUNTIME_FAULT_HOOK = old_fault

                self.assertIn(label, seen)
                rc, _result = updatectl._reconcile_player_runtime_state(
                    f"unit_rollback_fault_{label}",
                    allow_maintenance=True,
                )
                self.assertEqual(rc, 0)
                current = updatectl._read_symlink_target(updatectl.CURRENT_LINK)
                if current:
                    ok, reason, _marker = updatectl._validate_player_runtime_marker(
                        updatectl.APP_BASE / current,
                        updatectl._read_state(),
                    )
                    self.assertTrue(ok, f"{label}: {reason}")
                    self.assertNotEqual(current, "releases/runtime-b")
                quarantined, _reason = updatectl._player_runtime_is_quarantined(
                    current_identity,
                    updatectl._read_state(),
                )
                self.assertTrue(quarantined)

    def test_player_runtime_rollback_fault_without_previous_fails_closed_to_image(self) -> None:
        for label in (
            "rollback_after_identify_links",
            "rollback_after_current_unlinked",
            "rollback_after_quarantine",
            "rollback_after_state_success",
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                configure_temp(root, "player-runtime")
                _current, _manifest, current_identity = write_verified_player_runtime_release("runtime-b")
                updatectl._atomic_symlink("releases/runtime-b", updatectl.CURRENT_LINK)
                updatectl._write_state({
                    "component": "player-runtime",
                    "schema": updatectl.SCHEMA_STATE,
                    "current": {"version": "runtime-b"},
                    "previous": None,
                })
                seen: list[str] = []

                def fault_hook(observed: str, _context: dict) -> None:
                    seen.append(observed)
                    if observed == label:
                        raise InjectedPowerCut(label)

                old_thaw = updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED
                old_fault = updatectl.PLAYER_RUNTIME_FAULT_HOOK
                try:
                    updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
                    updatectl.PLAYER_RUNTIME_FAULT_HOOK = fault_hook
                    with self.assertRaises(InjectedPowerCut):
                        updatectl._rollback_player_runtime_unfrozen(
                            reason="unit_fault_no_previous",
                            quarantine_current=True,
                        )
                finally:
                    updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = old_thaw
                    updatectl.PLAYER_RUNTIME_FAULT_HOOK = old_fault

                self.assertIn(label, seen)
                rc, _result = updatectl._reconcile_player_runtime_state(
                    f"unit_rollback_no_previous_fault_{label}",
                    allow_maintenance=True,
                )
                self.assertEqual(rc, 0)
                self.assertIsNone(updatectl._read_symlink_target(updatectl.CURRENT_LINK))
                quarantined, _reason = updatectl._player_runtime_is_quarantined(
                    current_identity,
                    updatectl._read_state(),
                )
                self.assertTrue(quarantined)

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

    def test_totem_core_apply_rejects_payload_outside_device_allowlist(self) -> None:
        forbidden = [
            "bin/kiosky_service_launcher.sh",
            "bin/totem-kiosky-launcher.sh",
            "data/media/playlist.json",
            "opt/totem/bin/totem-mpv-hwdecode",
            "health/extra.json",
            "manifest-fragment/extra.json",
        ]
        for index, forbidden_name in enumerate(forbidden):
            with self.subTest(forbidden_name=forbidden_name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                configure_temp(root, "totem-core")
                updatectl.POLICY_FILE.parent.mkdir(parents=True)
                updatectl.POLICY_FILE.write_text(json.dumps(policy(), sort_keys=True) + "\n", encoding="utf-8")
                pkg_dir = root / "pkg"
                pkg_dir.mkdir()
                version = f"core-bad-scope-{index}"
                payload_path = pkg_dir / f"dadooh-totem-core-{version}.tar.gz"
                with tarfile.open(payload_path, "w:gz") as tf:
                    for name, content in {
                        "bin/totem_setup_visual_wizard.py": b"print('ok')\n",
                        forbidden_name: b"forbidden\n",
                    }.items():
                        info = tarfile.TarInfo(name)
                        info.size = len(content)
                        tf.addfile(info, fileobj=io.BytesIO(content))
                raw_manifest = manifest(version, sha=updatectl._sha256_file(payload_path))
                manifest_path = pkg_dir / f"dadooh-totem-core-{version}.manifest.json"
                manifest_path.write_text(json.dumps(raw_manifest, sort_keys=True) + "\n", encoding="utf-8")

                rc = updatectl._apply_from_manifest_path(
                    manifest_path,
                    payload_url=None,
                    source="local-test",
                    payload_path_override=payload_path,
                )

                self.assertEqual(rc, 7)
                self.assertFalse((updatectl.INCOMING_DIR / version).exists())
                self.assertFalse((updatectl.RELEASES_DIR / version).exists())
                self.assertIsNone(updatectl._read_symlink_target(updatectl.CURRENT_LINK))


def _load_candidate_health():
    ch_path = REPO_ROOT / "scripts" / "board" / "c18_player_runtime_candidate_health.py"
    spec_ch = importlib.util.spec_from_file_location("c18_candidate_health_quar_test", ch_path)
    assert spec_ch and spec_ch.loader
    mod = importlib.util.module_from_spec(spec_ch)
    spec_ch.loader.exec_module(mod)
    return mod


class C18CandidateSetupFailNoQuarantineTest(unittest.TestCase):
    """Regression (2026-06-10 board A/B): a candidate-health SETUP failure (workspace unreachable
    by the run_user) must abort the apply FAIL-CLOSED via deep_health_exception (rc=13) WITHOUT
    quarantining the candidate identity — while a REAL health failure (passed=False) must still
    quarantine. The setup error must also be persisted to candidate-health-result.json."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ch = _load_candidate_health()

    def _apply_with_hook(self, root: Path, version: str, hook):
        configure_temp(root, "player-runtime")
        write_player_runtime_policy(root)
        manifest_path, payload_path = write_player_runtime_payload(root, version)
        old_thaw = updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED
        old_health = updatectl.PLAYER_RUNTIME_HEALTH_HOOK
        try:
            updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
            updatectl.PLAYER_RUNTIME_HEALTH_HOOK = hook
            return updatectl._apply_from_manifest_path_unfrozen(
                manifest_path,
                payload_url=None,
                source="unit-setupfail-test",
                payload_path_override=payload_path,
            )
        finally:
            updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = old_thaw
            updatectl.PLAYER_RUNTIME_HEALTH_HOOK = old_health

    def test_setup_fail_aborts_rc13_without_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def setup_fail_hook(release_dir, identity):
                raise self.ch.CandidateSetupInaccessibleError("unit setup inaccessible")

            rc = self._apply_with_hook(root, "runtime-setupfail", setup_fail_hook)
            # deep_health_exception path → fail-closed abort, no promotion.
            self.assertEqual(rc, 13)
            state = updatectl._read_state()
            # The candidate identity MUST NOT be quarantined for an environment problem.
            self.assertEqual(updatectl._quarantine_entries(state), [])
            self.assertFalse(updatectl._read_symlink_target(updatectl.CURRENT_LINK))

    def test_real_health_fail_still_quarantines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def health_fail_hook(release_dir, identity):
                return {
                    "schema": updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
                    "passed": False,
                    "failure_reasons": ["playback_progressed"],
                    "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
                    "observed_tree_sha256": identity["tree_sha256"],
                }

            rc = self._apply_with_hook(root, "runtime-healthfail", health_fail_hook)
            # A genuine health failure still quarantines (no current → rc=11).
            self.assertEqual(rc, 11)
            state = updatectl._read_state()
            self.assertEqual(len(updatectl._quarantine_entries(state)), 1)

    def test_run_candidate_health_setup_fail_writes_artifact_and_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = root / "release"
            release.mkdir()
            (release / "kiosk.py").write_text('print("x")\n', encoding="utf-8")
            work = root / "work"
            identity = {"kiosk_py_sha256": "k", "tree_sha256": "t", "version": "v"}
            orig = self.ch.access_failures_as_user
            self.ch.access_failures_as_user = lambda targets, run_user: [
                "release_kiosk_py_read",
                "work_root_write",
            ]
            try:
                with self.assertRaises(self.ch.CandidateSetupInaccessibleError):
                    self.ch.run_candidate_health(release, identity, output_dir=work)
            finally:
                self.ch.access_failures_as_user = orig
            result_path = work / "candidate-health-result.json"
            self.assertTrue(result_path.exists())
            data = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertIs(data["passed"], False)
            self.assertEqual(data["setup_error"], "candidate_setup_inaccessible_to_run_user")
            self.assertEqual(
                sorted(data["inaccessible_targets"]),
                ["release_kiosk_py_read", "work_root_write"],
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
