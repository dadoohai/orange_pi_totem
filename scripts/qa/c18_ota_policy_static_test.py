#!/usr/bin/env python3
"""C18 OTA static policy checks.

These checks are offline-only. They prove the repo no longer relies on an
operator-created policy file or on the legacy kiosky-player update service.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "scripts" / "board" / "totem_update_policy.json"
SERVICE_PATH = REPO_ROOT / "scripts" / "board" / "systemd" / "totem-update-agent.service"
MANIFEST_PATH = REPO_ROOT / "scripts" / "board" / "totem_appliance_manifest.json"
EMBED_PATH = REPO_ROOT / "scripts" / "build" / "totem_core_image_embed.py"
BUILD_CORE_PATH = REPO_ROOT / "scripts" / "deploy" / "build_totem_core_release_package.sh"
PUBLISH_CORE_PATH = REPO_ROOT / "scripts" / "deploy" / "publish_totem_core_github_release.sh"
UPDATECTL_PATH = REPO_ROOT / "scripts" / "board" / "totem_updatectl.py"
BOOTSTRAP_C17_5_PATH = REPO_ROOT / "scripts" / "remote" / "bootstrap_c17_5_totem_core_on_board.sh"
DERIVE_C17_7_PATH = REPO_ROOT / "scripts" / "build" / "derive_c17_7_totem_core_embedded_image.py"
BUILD_PLAYER_PATH = REPO_ROOT / "scripts" / "deploy" / "build_kiosky_player_release_package.sh"
PUBLISH_PLAYER_PATH = REPO_ROOT / "scripts" / "deploy" / "publish_kiosky_player_github_release.sh"
RELEASE_GATE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_ota_release_gate.py"


class C18OtaPolicyStaticTest(unittest.TestCase):
    def test_canonical_policy_restricts_to_totem_core(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(policy["schema"], "dadooh.totem.update.policy.v1")
        self.assertEqual(policy["allowed_components"], ["totem-core"])
        self.assertEqual(policy["device_track"], "c18-hwdecode")
        self.assertFalse(policy["allow_downgrade"])
        self.assertIn(policy["device_channel"], {"lab", "homologation", "stable"})

    def test_update_agent_service_targets_totem_core_repo(self) -> None:
        service = SERVICE_PATH.read_text(encoding="utf-8")
        self.assertIn("ConditionPathExists=/data/updates/policy.json", service)
        self.assertIn("apply-github-latest --component totem-core --repo dadoohai/orange_pi_totem", service)
        self.assertNotIn("dadoohai/kiosky-player", service)

    def test_timer_is_manifested_disabled(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        units = {
            item["target"]: item
            for item in manifest.get("systemd_units", [])
            if isinstance(item, dict) and item.get("target")
        }
        timer = units["/etc/systemd/system/totem-update-agent.timer"]
        self.assertIs(timer.get("enabled"), False)
        self.assertEqual(timer.get("active_expected_on_dev"), "inactive")

    def test_image_embed_writes_policy_service_and_disables_timer(self) -> None:
        embed = EMBED_PATH.read_text(encoding="utf-8")
        self.assertIn('UPDATE_POLICY_TARGET = "/data/updates/policy.json"', embed)
        self.assertIn("totem_update_policy.json", embed)
        self.assertIn("totem-update-agent.service", embed)
        self.assertIn("totem-update-agent.timer", embed)
        self.assertIn("totem_core_update_timer_disabled", embed)
        self.assertIn("totem_core_update_policy_restricts_core", embed)

    def test_totem_core_ota_payload_excludes_player_launcher(self) -> None:
        build = BUILD_CORE_PATH.read_text(encoding="utf-8")
        core_files_block = build.split("CORE_FILES=(", 1)[1].split(")", 1)[0]
        self.assertNotIn("kiosky_service_launcher.sh", core_files_block)
        self.assertNotIn("bash -n bin/kiosky_service_launcher.sh", build)

    def test_totem_core_publish_targets_manifest_source_commit(self) -> None:
        publish = PUBLISH_CORE_PATH.read_text(encoding="utf-8")
        self.assertIn('SOURCE_COMMIT="$(read_json "$MANIFEST" source_commit)"', publish)
        self.assertIn("manifest source_commit is not a full SHA", publish)
        self.assertIn("git ls-remote --tags", publish)
        self.assertIn("--target \"$SOURCE_COMMIT\"", publish)
        self.assertIn("--verify-tag", publish)
        self.assertIn("does not point to manifest source_commit", publish)

    def test_image_embed_keeps_player_launcher_fixed_to_image(self) -> None:
        embed = EMBED_PATH.read_text(encoding="utf-8")
        core_files_block = embed.split("CORE_FILES = [", 1)[1].split("]", 1)[0]
        self.assertNotIn("kiosky_service_launcher.sh", core_files_block)
        self.assertIn("IMAGE_FIXED_PLAYER_FILES", embed)
        self.assertIn("not_totem_core_wrapper", embed)

    def test_historical_bootstrap_and_c17_7_embed_do_not_wrap_player_launcher(self) -> None:
        bootstrap = BOOTSTRAP_C17_5_PATH.read_text(encoding="utf-8")
        for block in bootstrap.split("CORE_FILES=(")[1:]:
            self.assertNotIn("kiosky_service_launcher.sh", block.split(")", 1)[0])
        self.assertIn("player-runtime and is fixed by the image", bootstrap)

        c17_7 = DERIVE_C17_7_PATH.read_text(encoding="utf-8")
        core_files_block = c17_7.split("CORE_FILES = [", 1)[1].split("]", 1)[0]
        self.assertNotIn("kiosky_service_launcher.sh", core_files_block)
        self.assertIn("IMAGE_FIXED_PLAYER_FILES", c17_7)
        self.assertIn("image_fixed_player_launcher_not_totem_core_wrapper", c17_7)

    def test_updatectl_contract_blocks_ambiguous_policy_and_requires_created_at(self) -> None:
        updatectl = UPDATECTL_PATH.read_text(encoding="utf-8")
        self.assertIn('"created_at_utc"', updatectl)
        self.assertIn("manifest created_at_utc must be an ISO-8601 UTC timestamp", updatectl)
        self.assertNotIn('raw.get("allowed_components", ["kiosky-player", "totem-core"])', updatectl)
        required_bin_block = updatectl.split("TOTEM_CORE_REQUIRED_BIN = (", 1)[1].split(")", 1)[0]
        self.assertNotIn("kiosky_service_launcher.sh", required_bin_block)

    def test_player_release_scripts_are_frozen_by_default(self) -> None:
        for path in (BUILD_PLAYER_PATH, PUBLISH_PLAYER_PATH):
            script = path.read_text(encoding="utf-8")
            self.assertIn("ALLOW_C18_FROZEN_PLAYER_RELEASE", script)
            self.assertIn("kiosky-player OTA", script)
            self.assertIn("is frozen for C18", script)

    def test_release_gate_blocks_player_runtime_diff(self) -> None:
        gate = RELEASE_GATE_PATH.read_text(encoding="utf-8")
        self.assertIn("PLAYER_RUNTIME_DIFF_PATHS", gate)
        self.assertIn('"scripts/board/kiosky_service_launcher.sh"', gate)
        self.assertIn("player_runtime_diff_guard", gate)
        self.assertIn("requires image/homologation", gate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
