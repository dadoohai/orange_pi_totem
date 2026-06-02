#!/usr/bin/env python3
"""C17.9 synthetic tests for update channel governance.

The fixtures are local only. They do not call GitHub, do not publish releases,
and do not touch device state.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
UPDATECTL_PATH = REPO_ROOT / "scripts" / "board" / "totem_updatectl.py"

spec = importlib.util.spec_from_file_location("totem_updatectl", UPDATECTL_PATH)
assert spec and spec.loader
updatectl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updatectl)


def policy(channel: str, *, allow_prerelease: bool = False) -> dict:
    return {
        "schema": "dadooh.totem.update.policy.v1",
        "device_channel": channel,
        "device_track": "c18-hwdecode",
        "allowed_components": ["kiosky-player", "totem-core"],
        "allow_prerelease": allow_prerelease,
        "allow_downgrade": False,
    }


def manifest(component: str, version: str, channel: str, **overrides: object) -> dict:
    payload = f"dadooh-{component}-{version}.tar.gz"
    data: dict[str, object] = {
        "schema": "dadooh.totem.update.v1",
        "component": component,
        "version": version,
        "channel": channel,
        "payload": payload,
        "payload_sha256": "a" * 64,
        "payload_bytes": 10,
        "created_at_utc": "2026-05-18T10:00:00Z",
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
        "source_repo": "synthetic/repo",
        "source_branch": "test",
        "source_commit": "0" * 40,
    }
    if component == "kiosky-player":
        data["entrypoint"] = "kiosk.py"
    else:
        data["entrypoint"] = "bin/totem_setup_visual_wizard.py"
        data["updates"] = ["wizard"]
    data.update(overrides)
    return data


def release(tag: str, component: str, version: str, channel: str,
            *, draft: bool = False, prerelease: bool = False,
            published_at: str = "2026-05-18T10:00:00Z",
            manifest_override: dict | None = None,
            omit_manifest_asset: bool = False) -> dict:
    assets = [
        {
            "name": f"dadooh-{component}-{version}.tar.gz",
            "browser_download_url": f"https://example.invalid/{tag}/payload",
            "size": 10,
        }
    ]
    if not omit_manifest_asset:
        assets.insert(
            0,
            {
                "name": f"dadooh-{component}-{version}.manifest.json",
                "browser_download_url": f"https://example.invalid/{tag}/manifest",
                "size": 10,
            },
        )
    return {
        "tag_name": tag,
        "draft": draft,
        "prerelease": prerelease,
        "published_at": published_at,
        "assets": assets,
        "manifest": manifest_override if manifest_override is not None else manifest(component, version, channel),
    }


def selected_tag(releases: list[dict], device_policy: dict, component: str) -> str | None:
    result = updatectl.select_update_release(releases, device_policy, component)
    selected = result.get("release")
    return selected.get("tag_name") if isinstance(selected, dict) else None


class UpdateChannelPolicyTest(unittest.TestCase):
    def test_stable_device_does_not_select_lab(self) -> None:
        releases = [release("lab-new", "kiosky-player", "1.2.0", "lab")]
        self.assertIsNone(selected_tag(releases, policy("stable"), "kiosky-player"))

    def test_stable_device_does_not_select_homologation(self) -> None:
        releases = [release("homolog-new", "kiosky-player", "1.2.0", "homologation", prerelease=True)]
        self.assertIsNone(selected_tag(releases, policy("stable"), "kiosky-player"))

    def test_stable_device_selects_stable(self) -> None:
        releases = [release("stable-ok", "kiosky-player", "1.0.0", "stable")]
        self.assertEqual(selected_tag(releases, policy("stable"), "kiosky-player"), "stable-ok")

    def test_homologation_device_selects_homologation_when_allowed(self) -> None:
        releases = [
            release("lab-newer", "totem-core", "2.0.0", "lab", prerelease=True, published_at="2026-05-18T12:00:00Z"),
            release("homolog-ok", "totem-core", "1.1.0", "homologation", prerelease=True, published_at="2026-05-18T11:00:00Z"),
            release("stable-old", "totem-core", "1.0.0", "stable", published_at="2026-05-18T10:00:00Z"),
        ]
        self.assertEqual(
            selected_tag(releases, policy("homologation", allow_prerelease=True), "totem-core"),
            "homolog-ok",
        )

    def test_homologation_device_does_not_select_lab_conservative_policy(self) -> None:
        releases = [release("lab-only", "totem-core", "2.0.0", "lab", prerelease=True)]
        self.assertIsNone(
            selected_tag(releases, policy("homologation", allow_prerelease=True), "totem-core")
        )

    def test_lab_device_selects_lab_when_allowed(self) -> None:
        releases = [release("lab-ok", "totem-core", "2.0.0", "lab", prerelease=True)]
        self.assertEqual(selected_tag(releases, policy("lab", allow_prerelease=True), "totem-core"), "lab-ok")

    def test_component_filter_blocks_totem_core_for_kiosky_player(self) -> None:
        releases = [release("core-stable", "totem-core", "1.0.0", "stable")]
        self.assertIsNone(selected_tag(releases, policy("stable"), "kiosky-player"))

    def test_component_filter_blocks_kiosky_player_for_totem_core(self) -> None:
        releases = [release("player-stable", "kiosky-player", "1.0.0", "stable")]
        self.assertIsNone(selected_tag(releases, policy("stable"), "totem-core"))

    def test_release_without_valid_manifest_is_ignored(self) -> None:
        bad_schema = manifest("kiosky-player", "1.1.0", "stable", schema="wrong.schema")
        releases = [
            release("bad", "kiosky-player", "1.1.0", "stable", manifest_override=bad_schema),
            release("good", "kiosky-player", "1.0.0", "stable", published_at="2026-05-18T09:00:00Z"),
        ]
        self.assertEqual(selected_tag(releases, policy("stable"), "kiosky-player"), "good")

    def test_manifest_with_wrong_device_track_is_ignored(self) -> None:
        bad_req = {
            "device": "orangepizero3",
            "base_image_min": "c17.4.2",
            "device_track": "future-display-track",
            "updater_features": ["c18-track-v1"],
        }
        bad_manifest = manifest("totem-core", "2.0.0", "stable", requires=bad_req)
        releases = [
            release("bad-track", "totem-core", "2.0.0", "stable", manifest_override=bad_manifest),
            release("good-track", "totem-core", "1.0.0", "stable", published_at="2026-05-18T09:00:00Z"),
        ]
        self.assertEqual(selected_tag(releases, policy("stable"), "totem-core"), "good-track")

    def test_manifest_with_unknown_requires_key_is_ignored(self) -> None:
        bad_req = {
            "device": "orangepizero3",
            "base_image_min": "c17.4.2",
            "device_track": "c18-hwdecode",
            "updater_features": ["c18-track-v1"],
            "requires_new_systemd_unit": True,
        }
        bad_manifest = manifest("totem-core", "2.0.0", "stable", requires=bad_req)
        releases = [
            release("unknown-requires", "totem-core", "2.0.0", "stable", manifest_override=bad_manifest),
            release("good", "totem-core", "1.0.0", "stable", published_at="2026-05-18T09:00:00Z"),
        ]
        self.assertEqual(selected_tag(releases, policy("stable"), "totem-core"), "good")

    def test_manifest_with_unsupported_updater_feature_is_ignored(self) -> None:
        bad_req = {
            "device": "orangepizero3",
            "base_image_min": "c17.4.2",
            "device_track": "c18-hwdecode",
            "updater_features": ["c18-track-v1", "future-updater-v9"],
        }
        bad_manifest = manifest("totem-core", "2.0.0", "stable", requires=bad_req)
        releases = [
            release("unsupported-feature", "totem-core", "2.0.0", "stable", manifest_override=bad_manifest),
            release("good", "totem-core", "1.0.0", "stable", published_at="2026-05-18T09:00:00Z"),
        ]
        self.assertEqual(selected_tag(releases, policy("stable"), "totem-core"), "good")

    def test_manifest_without_sha_is_ignored(self) -> None:
        missing_sha = manifest("kiosky-player", "1.1.0", "stable")
        missing_sha.pop("payload_sha256")
        releases = [
            release("missing-sha", "kiosky-player", "1.1.0", "stable", manifest_override=missing_sha),
            release("good", "kiosky-player", "1.0.0", "stable", published_at="2026-05-18T09:00:00Z"),
        ]
        self.assertEqual(selected_tag(releases, policy("stable"), "kiosky-player"), "good")

    def test_draft_release_is_ignored(self) -> None:
        releases = [
            release("draft", "kiosky-player", "1.1.0", "stable", draft=True),
            release("good", "kiosky-player", "1.0.0", "stable", published_at="2026-05-18T09:00:00Z"),
        ]
        self.assertEqual(selected_tag(releases, policy("stable"), "kiosky-player"), "good")

    def test_prerelease_requires_policy_permission(self) -> None:
        releases = [
            release("stable-prerelease", "kiosky-player", "1.1.0", "stable", prerelease=True),
            release("stable-normal", "kiosky-player", "1.0.0", "stable", published_at="2026-05-18T09:00:00Z"),
        ]
        self.assertEqual(selected_tag(releases, policy("stable"), "kiosky-player"), "stable-normal")

    def test_dry_run_selection_does_not_mutate_state_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = root / "current"
            previous = root / "previous"
            current.symlink_to("releases/current")
            previous.symlink_to("releases/previous")
            before = (current.readlink(), previous.readlink(), sorted(root.iterdir()))

            result = updatectl.select_update_release(
                [release("stable-ok", "kiosky-player", "1.0.0", "stable")],
                policy("stable"),
                "kiosky-player",
            )

            after = (current.readlink(), previous.readlink(), sorted(root.iterdir()))
            self.assertIsNotNone(result.get("release"))
            self.assertEqual(before, after)

    def test_github_release_listing_paginates(self) -> None:
        calls: list[str] = []
        original = updatectl._http_get_json

        def fake_get_json(url: str) -> list[dict]:
            calls.append(url)
            page = parse_qs(urlparse(url).query).get("page", [""])[0]
            if page == "1":
                return [{"tag_name": f"release-{i}"} for i in range(100)]
            if page == "2":
                return [{"tag_name": "release-100"}]
            return []

        try:
            updatectl._http_get_json = fake_get_json
            releases = updatectl._gh_list_releases("example/repo")
        finally:
            updatectl._http_get_json = original

        self.assertEqual(len(releases), 101)
        self.assertEqual(len(calls), 2)
        self.assertIn("per_page=100", calls[0])
        self.assertIn("page=1", calls[0])
        self.assertIn("page=2", calls[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
