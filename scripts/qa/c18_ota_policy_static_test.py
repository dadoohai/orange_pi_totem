#!/usr/bin/env python3
"""C18 OTA static policy checks.

These checks are offline-only. They prove the repo no longer relies on an
operator-created policy file or on the legacy kiosky-player update service.
"""

from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "scripts" / "board" / "totem_update_policy.json"
SERVICE_PATH = REPO_ROOT / "scripts" / "board" / "systemd" / "totem-update-agent.service"
MANIFEST_PATH = REPO_ROOT / "scripts" / "board" / "totem_appliance_manifest.json"
EMBED_PATH = REPO_ROOT / "scripts" / "build" / "totem_core_image_embed.py"
BUILD_CORE_PATH = REPO_ROOT / "scripts" / "deploy" / "build_totem_core_release_package.sh"
PUBLISH_CORE_PATH = REPO_ROOT / "scripts" / "deploy" / "publish_totem_core_github_release.sh"
BUILD_PLAYER_RUNTIME_PATH = REPO_ROOT / "scripts" / "deploy" / "build_player_runtime_release_package.sh"
UPDATECTL_PATH = REPO_ROOT / "scripts" / "board" / "totem_updatectl.py"
BOOTSTRAP_C17_5_PATH = REPO_ROOT / "scripts" / "remote" / "bootstrap_c17_5_totem_core_on_board.sh"
DERIVE_C17_7_PATH = REPO_ROOT / "scripts" / "build" / "derive_c17_7_totem_core_embedded_image.py"
BUILD_PLAYER_PATH = REPO_ROOT / "scripts" / "deploy" / "build_kiosky_player_release_package.sh"
PUBLISH_PLAYER_PATH = REPO_ROOT / "scripts" / "deploy" / "publish_kiosky_player_github_release.sh"
RELEASE_GATE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_ota_release_gate.py"
CONFIG_CONTRACT_PATH = REPO_ROOT / "scripts" / "board" / "totem_config_contract_validate.py"
APP_INTEGRATION_CONFIG_PATH = REPO_ROOT / "docs" / "app-integration" / "config.homologation-v0.1.example.json"
MANUAL_KIOSKY_DOC_PATH = REPO_ROOT / "docs" / "app-integration" / "01_TESTE_MANUAL_KIOSKY_PLAYER.md"
MPV_CONTROLLER_PROBE_PATH = REPO_ROOT / "scripts" / "board" / "mpv_controller_playlist_probe.sh"
PLAYBACK_OBSERVER_PATH = REPO_ROOT / "scripts" / "board" / "kiosky_playback_observer_probe.sh"
SERVICE_OBSERVER_PATH = REPO_ROOT / "scripts" / "board" / "kiosky_service_observer_probe.sh"
COLDBOOT_STATE_COLLECTOR_PATH = REPO_ROOT / "scripts" / "board" / "c18_coldboot_state_collect.py"
PLAYBACK_HEALTH_COLLECTOR_PATH = REPO_ROOT / "scripts" / "board" / "c18_playback_health_collect.py"
PLAYER_RUNTIME_CANDIDATE_HEALTH_PATH = REPO_ROOT / "scripts" / "board" / "c18_player_runtime_candidate_health.py"
PLAYER_RUNTIME_LAB_APPLY_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_lab_apply.py"
PLAYER_RUNTIME_LAB_ROLLBACK_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_lab_rollback.py"
PLAYER_RUNTIME_ADOPTION_PROBE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_adoption_probe.py"
COLDBOOT_EVIDENCE_GATE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_coldboot_evidence_gate.py"
PLAYER_RUNTIME_EVIDENCE_GATE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_evidence_gate.py"
PLAYER_RUNTIME_PERSISTENT_TRIAL_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_persistent_trial.py"
KIOSKY_LAUNCHER_PATH = REPO_ROOT / "scripts" / "board" / "totem-kiosky-launcher.sh"
KIOSKY_LAUNCHER_DROPIN_PATH = (
    REPO_ROOT / "scripts" / "board" / "systemd" / "kiosky-player.service.d" / "20-dadooh-launcher.conf"
)
TIMER_PATH = REPO_ROOT / "scripts" / "board" / "systemd" / "totem-update-agent.timer"
ROADMAP_PATH = REPO_ROOT / "docs" / "04_ROADMAP_PRODUTO_TESTES_ATUALIZACAO_MONITORAMENTO.md"
POLICY_DOC_PATH = REPO_ROOT / "docs" / "05_POLITICA_DE_ATUALIZACAO.md"
UPDATE_CONTRACT_PATH = REPO_ROOT / "docs" / "UPDATE_CONTRACT.md"
UPDATE_AUTHORIZATION_HEALTH_PATH = REPO_ROOT / "docs" / "UPDATE_AUTHORIZATION_HEALTH.md"
README_PATH = REPO_ROOT / "README.md"
DOC_INDEX_PATH = REPO_ROOT / "docs" / "00_INDICE_E_PLANO_ESTRATEGICO.md"
DOC188_PATH = REPO_ROOT / "docs" / "product" / "188_C18_STATUS_E_CONTINUIDADE.md"
DOC189_PATH = REPO_ROOT / "docs" / "product" / "189_C18_OTA_READINESS_GATE.md"
DOC190_PATH = REPO_ROOT / "docs" / "product" / "190_C18_PROD_ORIENTATION.md"
DOC191_PATH = REPO_ROOT / "docs" / "product" / "191_C18_OTA_OPERATING_MODEL.md"
EVIDENCE_CURRENT_DEEP_HEALTH_DIR = (
    REPO_ROOT / "docs" / "evidence" / "c18-update-validation" / "20260605T093008Z-1t-coldboot-deep-health"
)
EVIDENCE_CURRENT_PLAYER_RUNTIME_TRIAL_DIR = (
    REPO_ROOT / "docs" / "evidence" / "c18-update-validation" / "20260605T052805Z-1r-player-runtime-data-trial"
)
EVIDENCE_CURRENT_PLAYER_RUNTIME_ABA_TRIAL_DIR = (
    REPO_ROOT / "docs" / "evidence" / "c18-update-validation" / "20260605T060200Z-1r-player-runtime-data-aba-trial"
)
EVIDENCE_CURRENT_IMAGE_SHA256 = "7ab5a582f2ce51f13338be8ad4a68a15cb736007f617a49456704c5c45cefec6"
EVIDENCE_PLAYER_RUNTIME_TRIAL_IMAGE_SHA256 = "23ef26b4cdbd6c35643fdc41d8666da33dd259b387af05864c8f063506f7711c"
LEGACY_C14_REMOTE_SCRIPTS = (
    REPO_ROOT / "scripts" / "remote" / "deploy_kiosky_player.sh",
    REPO_ROOT / "scripts" / "remote" / "bootstrap_c14_1_1_on_board.sh",
    REPO_ROOT / "scripts" / "remote" / "validate_c14_2_1_clean_board.sh",
    REPO_ROOT / "scripts" / "remote" / "run_c14_1_1_github_releases_pull_deploy_mvp.sh",
    REPO_ROOT / "scripts" / "remote" / "apply_c14_1_1_release_on_board.sh",
    REPO_ROOT / "scripts" / "remote" / "rollback_c14_1_1_on_board.sh",
    REPO_ROOT / "scripts" / "remote" / "test_rollback_c14_1_1_on_board.sh",
)
LEGACY_C18_REMOTE_BYPASS_SCRIPTS = (
    REPO_ROOT / "scripts" / "remote" / "apply_c15_1_1_session_hotfix.sh",
    REPO_ROOT / "scripts" / "remote" / "bootstrap_c17_5_totem_core_on_board.sh",
    REPO_ROOT / "scripts" / "remote" / "push_and_run.sh",
)


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

    def test_player_runtime_launcher_path_is_governed(self) -> None:
        launcher = KIOSKY_LAUNCHER_PATH.read_text(encoding="utf-8")
        dropin = KIOSKY_LAUNCHER_DROPIN_PATH.read_text(encoding="utf-8")
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        dirs = {
            item["path"]
            for item in manifest.get("paths", [])
            if isinstance(item, dict) and item.get("type") == "dir"
        }

        self.assertIn("/data/player-runtime/current", launcher)
        self.assertIn(".release_verified.json", launcher)
        self.assertIn("kiosk_sha_mismatch", launcher)
        self.assertIn("tree_sha_mismatch", launcher)
        self.assertIn("quarantined", launcher)
        self.assertIn("data app dir present but not verified; falling back", launcher)
        self.assertNotIn("/data/apps/kiosky-player/current", launcher)
        self.assertIn("/data/player-runtime/current/kiosk.py", dropin)
        self.assertIn("C18_PLAYER_RUNTIME_RECONCILE=1", dropin)
        self.assertIn("--allow-player-runtime-maintenance", dropin)
        self.assertIn("reconcile --component player-runtime", dropin)
        self.assertIn("ExecStartPre=-+/usr/bin/env C18_PLAYER_RUNTIME_RECONCILE=1", dropin)
        self.assertIn("prefixed with `+`", dropin)
        self.assertIn("while reconcile must manage /data/player-runtime", dropin)
        self.assertIn("root-owned state", dropin)
        self.assertIn("non-fatal, explicitly authorized player-runtime reconcile", dropin)
        self.assertIn("RequiresMountsFor=/data", dropin)
        self.assertIn("After=local-fs.target", dropin)
        self.assertNotIn("ExecStartPre=-/usr/bin/env C18_PLAYER_RUNTIME_RECONCILE=1", dropin)
        self.assertNotIn("/data/apps/kiosky-player/current", dropin)
        self.assertIn("/data/player-runtime", dirs)
        self.assertIn("/data/player-runtime/releases", dirs)
        self.assertNotIn("/data/apps/kiosky-player", dirs)
        self.assertNotIn("/data/apps/kiosky-player/releases", dirs)

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
        self.assertNotIn("totem-kiosky-launcher.sh", core_files_block)
        self.assertNotIn("bash -n bin/kiosky_service_launcher.sh", build)
        self.assertNotIn("bash -n bin/totem-kiosky-launcher.sh", build)

    def test_totem_core_publish_targets_manifest_source_commit(self) -> None:
        publish = PUBLISH_CORE_PATH.read_text(encoding="utf-8")
        self.assertIn('SOURCE_COMMIT="$(read_json "$MANIFEST" source_commit)"', publish)
        self.assertIn("manifest source_commit is not a full SHA", publish)
        self.assertIn("git ls-remote --tags", publish)
        self.assertIn("--target \"$SOURCE_COMMIT\"", publish)
        self.assertIn("--verify-tag", publish)
        self.assertIn("does not point to manifest source_commit", publish)
        self.assertIn("c18-ota-release-gate.json", publish)
        self.assertIn("TMP_GATE_EVIDENCE", publish)
        self.assertIn('BASE_REF="${C18_OTA_BASE_REF:-}"', publish)
        self.assertIn("missing --base-ref", publish)
        self.assertIn('--base-ref "$BASE_REF"', publish)
        self.assertIn("--json >\"$TMP_GATE_EVIDENCE\"", publish)
        self.assertNotIn("c18_ota_release_gate.py\" \\\n  --package-manifest \"$MANIFEST\" \\\n  --package-payload \"$PAYLOAD\" \\\n  --json >/dev/null", publish)

    def test_stable_channel_requires_promotion_evidence(self) -> None:
        build = BUILD_CORE_PATH.read_text(encoding="utf-8")
        publish = PUBLISH_CORE_PATH.read_text(encoding="utf-8")
        for script in (build, publish):
            self.assertIn("ALLOW_C18_STABLE_PROMOTION", script)
            self.assertIn("dadooh.c18.stable_promotion.v1", script)
            self.assertIn("approved", script)
        self.assertIn("--stable-promotion-evidence", build)
        self.assertIn("c18-stable-promotion-evidence.json", publish)
        self.assertIn("stable_promotion_evidence_sha256", publish)
        self.assertIn("stable evidence sha256 mismatch", publish)
        self.assertIn("ACTUAL_STABLE_EVIDENCE_SHA", publish)

    def test_image_embed_keeps_player_launcher_fixed_to_image(self) -> None:
        embed = EMBED_PATH.read_text(encoding="utf-8")
        core_files_block = embed.split("CORE_FILES = [", 1)[1].split("]", 1)[0]
        self.assertNotIn("kiosky_service_launcher.sh", core_files_block)
        self.assertNotIn("totem-kiosky-launcher.sh", core_files_block)
        self.assertIn("IMAGE_FIXED_PLAYER_FILES", embed)
        self.assertIn("IMAGE_FIXED_PLAYER_SYSTEMD_FILES", embed)
        self.assertIn('"kiosky_service_launcher.sh"', embed)
        self.assertIn('"totem-kiosky-launcher.sh"', embed)
        self.assertIn("20-dadooh-launcher.conf", embed)
        self.assertIn("image_fixed_player_dropin_reconciles_player_runtime", embed)
        self.assertIn("not_totem_core_wrapper", embed)

    def test_historical_bootstrap_and_c17_7_embed_do_not_wrap_player_launcher(self) -> None:
        bootstrap = BOOTSTRAP_C17_5_PATH.read_text(encoding="utf-8")
        for block in bootstrap.split("CORE_FILES=(")[1:]:
            self.assertNotIn("kiosky_service_launcher.sh", block.split(")", 1)[0])
        self.assertIn("player-runtime and is fixed by the image", bootstrap)

        c17_7 = DERIVE_C17_7_PATH.read_text(encoding="utf-8")
        core_files_block = c17_7.split("CORE_FILES = [", 1)[1].split("]", 1)[0]
        self.assertNotIn("kiosky_service_launcher.sh", core_files_block)
        self.assertNotIn("totem-kiosky-launcher.sh", core_files_block)
        self.assertIn("IMAGE_FIXED_PLAYER_FILES", c17_7)
        self.assertIn("image_fixed_player_launcher_not_totem_core_wrapper", c17_7)

    def test_updatectl_contract_blocks_ambiguous_policy_and_requires_created_at(self) -> None:
        updatectl = UPDATECTL_PATH.read_text(encoding="utf-8")
        self.assertIn('"player-runtime": "player-runtime OTA is frozen', updatectl)
        self.assertIn("PLAYER_RUNTIME_MARKER_SCHEMA", updatectl)
        self.assertIn("_apply_player_runtime_from_manifest_path_unfrozen", updatectl)
        self.assertIn("_write_player_runtime_marker", updatectl)
        self.assertIn("_player_runtime_is_quarantined", updatectl)
        self.assertIn("PLAYER_RUNTIME_RECONCILE_ENV", updatectl)
        self.assertIn("--allow-player-runtime-maintenance", updatectl)
        self.assertIn("player_runtime_reconcile_guard_required", updatectl)
        self.assertIn("health did not observe candidate kiosk.py identity", updatectl)
        self.assertIn("def _fsync_release_tree", updatectl)
        self.assertIn("_fsync_release_tree(dest)", updatectl)
        self.assertLess(
            updatectl.index("_fsync_release_tree(release_dir)"),
            updatectl.index("marker = _write_player_runtime_marker(release_dir, manifest, identity, health)"),
        )
        self.assertIn('"created_at_utc"', updatectl)
        self.assertIn("manifest created_at_utc must be an ISO-8601 UTC timestamp", updatectl)
        self.assertNotIn('raw.get("allowed_components", ["kiosky-player", "totem-core"])', updatectl)
        self.assertIn("C18 operational OTA must pass --component totem-core", updatectl)
        self.assertIn("C18 OTA must pass --component totem-core", updatectl)
        required_bin_block = updatectl.split("TOTEM_CORE_REQUIRED_BIN = (", 1)[1].split(")", 1)[0]
        self.assertNotIn("kiosky_service_launcher.sh", required_bin_block)

    def test_config_contract_seals_c18_mpv_path(self) -> None:
        contract = CONFIG_CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn('C18_HWDECODE_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"', contract)
        self.assertIn("validate_c18_mpv_path_contract", contract)
        self.assertIn("must_preserve_c18_hwdecode_wrapper", contract)
        self.assertIn("must preserve C18 HW-decode wrapper", contract)
        self.assertIn('for bad_mpv_path in ("mpv", "/usr/bin/mpv", "relative/mpv", "")', contract)
        self.assertIn('"/usr/bin/mpv"', contract)

    def test_c18_docs_and_probes_do_not_default_to_stock_mpv(self) -> None:
        for path in (APP_INTEGRATION_CONFIG_PATH, MANUAL_KIOSKY_DOC_PATH):
            text = path.read_text(encoding="utf-8")
            self.assertIn('/opt/totem/bin/totem-mpv-hwdecode', text)
            self.assertNotIn('"mpv_path": "mpv"', text)

        probe = MPV_CONTROLLER_PROBE_PATH.read_text(encoding="utf-8")
        self.assertIn("MPV_CONTROLLER_PROBE_MPV_PATH", probe)
        self.assertIn("/opt/totem/bin/totem-mpv-hwdecode", probe)
        self.assertNotIn('"mpv_path": "mpv"', probe)

    def test_player_release_scripts_are_frozen_by_default(self) -> None:
        for path in (BUILD_PLAYER_PATH, PUBLISH_PLAYER_PATH):
            script = path.read_text(encoding="utf-8")
            self.assertIn("ALLOW_C18_FROZEN_PLAYER_RELEASE", script)
            self.assertIn("kiosky-player OTA", script)
            self.assertIn("is frozen for C18", script)
            self.assertIn("legacy lab reproduction bypass", script)
            self.assertIn("not approval for a C18-aware player-runtime release", script)
        publish = PUBLISH_PLAYER_PATH.read_text(encoding="utf-8")
        build = BUILD_PLAYER_PATH.read_text(encoding="utf-8")
        self.assertIn("legacy kiosky-player C18 builder only supports lab or homologation", build)
        self.assertIn("legacy kiosky-player stable releases are blocked for C18", publish)
        self.assertIn("legacy kiosky-player C18 publisher only supports lab or homologation", publish)
        self.assertIn("manifest component must be kiosky-player", publish)
        self.assertIn("manifest source_commit is not a full SHA", publish)
        self.assertIn("manifest created_at_utc must be an ISO-8601 UTC timestamp", publish)
        self.assertIn("will reject apply with rc=44", publish)
        self.assertNotIn("totem-updatectl apply-github-latest --repo ${REPO}", publish)

    def test_c18_status_doc_188_keeps_board_identifiers_redacted(self) -> None:
        doc = DOC188_PATH.read_text(encoding="utf-8")
        ipv4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        mac = re.compile(r"\b[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}\b")
        self.assertIsNone(ipv4.search(doc))
        self.assertIsNone(mac.search(doc))
        self.assertIn("<board-ip-redacted>", doc)

    def test_c18_docs_keep_1t_as_current_golden(self) -> None:
        current_tag = "c18-hwdecode-lab-1t"
        current_sha = EVIDENCE_CURRENT_IMAGE_SHA256
        legacy_sha_1s = "bc0a39cf0cc4502acb7f9b4726589449288783fa4d44821593ab15c4c2c1967f"
        legacy_sha_1r = EVIDENCE_PLAYER_RUNTIME_TRIAL_IMAGE_SHA256
        legacy_sha_1q = "d487bf33737d5af4ba4bbf7859163cf21f0762ef4c5180f2aed3685e4aa5c009"
        legacy_sha_1o = "07f9ee4f3f870f0fdb083eba7992a24b166939c768fc962e44a18d781117b164"
        legacy_sha_1n = "29fac35be322416ddd2e93caddb50396bff325e2fba5d219309c2f37f6349f7c"
        legacy_sha_1m = "d932eadba28f8fac5b737bed750d6dba2732064b79877601ceb0ed3f113a7d8c"
        legacy_sha_1l = "146b430972b61523cf943f467b94ccf56697843a48147ec5b1839db3583b1ad3"
        legacy_sha_1j = "995d0a90e6449f8f8e8e58f788fb38ba9196dacb4312cb28ecbd6041cda1c152"
        for path in (README_PATH, UPDATE_AUTHORIZATION_HEALTH_PATH, DOC188_PATH, DOC189_PATH, DOC190_PATH):
            text = path.read_text(encoding="utf-8")
            self.assertIn(current_tag, text)
        for path in (UPDATE_AUTHORIZATION_HEALTH_PATH, DOC188_PATH, DOC189_PATH, DOC190_PATH):
            text = path.read_text(encoding="utf-8")
            self.assertIn(current_sha, text)
        index = DOC_INDEX_PATH.read_text(encoding="utf-8")
        self.assertIn("docs/product/189_C18_OTA_READINESS_GATE.md", index)
        self.assertIn("baseline live continua em `189`", index)
        operating_model = DOC191_PATH.read_text(encoding="utf-8")
        self.assertIn("docs/UPDATE_CONTRACT.md", operating_model)
        self.assertIn("--package-payload <release-dir>/dadooh-totem-core-<version>.tar.gz", operating_model)
        doc189 = DOC189_PATH.read_text(encoding="utf-8")
        self.assertNotIn("partir da imagem `1l`", doc189)
        self.assertNotIn("Tratar `c18-hwdecode-lab-1m` como baseline", doc189)
        self.assertIn(legacy_sha_1s, doc189)
        self.assertIn(legacy_sha_1m, doc189)
        self.assertIn(legacy_sha_1n, doc189)
        self.assertIn(legacy_sha_1o, doc189)
        self.assertIn(legacy_sha_1q, doc189)
        self.assertIn(legacy_sha_1r, doc189)
        self.assertIn("20260605T093008Z-1t-coldboot-deep-health", doc189)
        doc188_top = DOC188_PATH.read_text(encoding="utf-8").split("---", 1)[0]
        self.assertNotIn(legacy_sha_1l, doc188_top)
        doc190_top = DOC190_PATH.read_text(encoding="utf-8").split("## Baseline", 1)[0]
        self.assertNotIn(legacy_sha_1j, doc190_top)

    def test_c18_current_hardware_evidence_is_public_and_passing(self) -> None:
        public_path = EVIDENCE_CURRENT_DEEP_HEALTH_DIR / "playback-deep-health-public.json"
        if not public_path.exists():
            public_path = EVIDENCE_CURRENT_DEEP_HEALTH_DIR / "deep-health" / "playback-deep-health-public.json"
        public = json.loads(public_path.read_text(encoding="utf-8"))
        privacy = json.loads((EVIDENCE_CURRENT_DEEP_HEALTH_DIR / "privacy-scan.json").read_text(encoding="utf-8"))
        manifest = json.loads((EVIDENCE_CURRENT_DEEP_HEALTH_DIR / "evidence-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(public["schema"], "dadooh.c18.playback.deep_health.v1")
        self.assertTrue(public["passed"])
        self.assertEqual(public["failure_reasons"], [])
        counters = public["counters"]
        self.assertGreaterEqual(counters["samples"], 20)
        self.assertEqual(counters["hwdec_expected_samples"], counters["samples"])
        self.assertEqual(counters["hwdec_unexpected_samples"], 0)
        self.assertTrue(counters["estimated_frame_progressed"])
        self.assertGreaterEqual(counters["estimated_frame_evaluable_segments"], 1)
        self.assertEqual(counters["estimated_frame_failed_segments"], 0)
        self.assertGreaterEqual(counters["unique_aliases"], 2)
        self.assertGreaterEqual(counters["status_unique_aliases"], 2)
        self.assertGreaterEqual(counters["mpv_unique_aliases"], 2)
        self.assertTrue(counters["status_transitions_observed"])
        self.assertTrue(counters["mpv_media_transitions_observed"])
        self.assertEqual(counters["media_load_failed"], 0)
        self.assertEqual(counters["mpv_restart"], 0)
        self.assertEqual(counters["nrestarts_delta"], 0)
        self.assertEqual(counters["panfrost_faults"], 0)
        self.assertEqual(counters["mmc_timeout_reset"], 0)
        self.assertEqual(counters["ext4_errors"], 0)
        self.assertEqual(counters["total_mpv_count"], 1)
        self.assertTrue(privacy.get("passed", privacy.get("result") == "passed"))
        if "scan_counts" in privacy:
            self.assertTrue(all(value == 0 for value in privacy["scan_counts"].values()))
        else:
            self.assertEqual(privacy.get("hits"), [])
        self.assertIn(
            manifest["schema"],
            {"dadooh.c18.update_validation.evidence_manifest.v1", "dadooh.c18.hardware_evidence.v1"},
        )
        self.assertEqual(manifest["image_tag"], "c18-hwdecode-lab-1t")
        self.assertEqual(manifest["image_sha256"], EVIDENCE_CURRENT_IMAGE_SHA256)
        manifest_items = manifest.get("artifacts", manifest.get("files", []))
        manifest_files = {item["file"]: item for item in manifest_items}
        privacy_files = {item["file"]: item for item in privacy.get("files", [])}
        for file_name, metadata in manifest_files.items():
            path = EVIDENCE_CURRENT_DEEP_HEALTH_DIR / file_name
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            expected_size = metadata.get("bytes", metadata.get("size"))
            self.assertEqual(path.stat().st_size, expected_size)
            self.assertEqual(digest, metadata["sha256"])
            if privacy_files:
                self.assertIn(file_name, privacy_files)
        if EVIDENCE_CURRENT_DEEP_HEALTH_DIR.name.endswith("1t-coldboot-deep-health"):
            coldboot = json.loads((EVIDENCE_CURRENT_DEEP_HEALTH_DIR / "boot-state-public.json").read_text(encoding="utf-8"))
            self.assertTrue(coldboot["boot"]["boot_id_changed"])
            self.assertTrue(coldboot["boot"]["btime_changed"])
            self.assertEqual(coldboot["boot"]["post_uptime_bucket"], "lt_5m")
            self.assertTrue(coldboot["systemd"]["requires_data_mount"])
            self.assertIn("/data", coldboot["systemd"]["requires_mounts_for"])
            self.assertTrue(coldboot["systemd"]["after_contains_local_fs"])
            self.assertTrue(coldboot["systemd"]["exec_start_pre_reconcile_present"])
            self.assertEqual(coldboot["systemd"]["nrestarts"], 0)
            self.assertEqual(coldboot["player_runtime"]["selected_source"], "fallback")
            self.assertFalse(coldboot["player_runtime"]["current_present"])
            self.assertEqual(coldboot["update_safety"]["public_player_runtime_rollback_rc"], 44)
            self.assertEqual(coldboot["update_safety"]["public_player_runtime_reconcile_rc"], 44)
            self.assertEqual(coldboot["update_safety"]["public_kiosky_player_rollback_rc"], 44)
            self.assertEqual(coldboot["update_safety"]["boot_player_runtime_reconcile_rc"], 0)
            self.assertFalse(coldboot["privacy"]["raw_boot_id_persisted"])
            self.assertFalse(coldboot["privacy"]["raw_mount_source_persisted"])
        evidence_gate = importlib.util.spec_from_file_location("c18_player_runtime_evidence_gate", PLAYER_RUNTIME_EVIDENCE_GATE_PATH)
        self.assertIsNotNone(evidence_gate)
        module = importlib.util.module_from_spec(evidence_gate)
        assert evidence_gate and evidence_gate.loader
        evidence_gate.loader.exec_module(module)
        leaks = []
        for path in sorted(EVIDENCE_CURRENT_DEEP_HEALTH_DIR.rglob("*")):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for label, pattern in module.LEAK_PATTERNS:
                if pattern.search(text):
                    leaks.append(f"{label}:{path.relative_to(EVIDENCE_CURRENT_DEEP_HEALTH_DIR).as_posix()}")
        self.assertEqual(leaks, [])

    def test_c18_coldboot_evidence_collector_and_gate_are_wired(self) -> None:
        collector = COLDBOOT_STATE_COLLECTOR_PATH.read_text(encoding="utf-8")
        gate = COLDBOOT_EVIDENCE_GATE_PATH.read_text(encoding="utf-8")
        release_gate = RELEASE_GATE_PATH.read_text(encoding="utf-8")
        self.assertIn("dadooh.c18.coldboot_state.v2", collector)
        self.assertIn("dadooh.c18.coldboot_pre_state.v1", collector)
        self.assertIn("--capture-pre-state", collector)
        self.assertIn("--pre-state", collector)
        self.assertIn("pre_state_reference", collector)
        self.assertIn("image_identity", collector)
        self.assertIn("marker_sha256", collector)
        self.assertIn("/opt/totem/kiosky-player/kiosk.py", collector)
        self.assertNotIn("/opt/totem/player-runtime/kiosk.py", collector)
        self.assertIn("--mechanical-action", collector)
        self.assertIn("--transition-flow", collector)
        self.assertIn("boot_id_changed", collector)
        self.assertIn("post_uptime_seconds", collector)
        self.assertIn("findmnt", collector)
        self.assertIn("source_kind", collector)
        self.assertIn("critical-chain", collector)
        self.assertIn("raw_mount_source_persisted", collector)
        self.assertIn("dadooh.c18.coldboot_state.v2", gate)
        self.assertIn("dadooh.c18.coldboot_pre_state.v1", gate)
        self.assertIn("--require-pre-state", gate)
        self.assertIn("--expect-image-tag", gate)
        self.assertIn("--expect-transition-flow", gate)
        self.assertIn("--forbid-controlled-reboot", gate)
        self.assertIn("pre_state_nonce_mismatch", gate)
        self.assertIn("pre_state_sha256_mismatch", gate)
        self.assertIn("pre_state_stale_or_after_post_boot", gate)
        self.assertIn("pre_state_capture_time_inconsistent", gate)
        self.assertIn("pre_state_file_path_unsafe", gate)
        self.assertIn("controlled_reboot_used", gate)
        self.assertIn("fallback_kiosk_missing", gate)
        self.assertIn("image_marker_sha256_missing", gate)
        self.assertIn("image_marker_changed_across_boot", gate)
        self.assertIn("pre_boot_id_hash_missing", gate)
        self.assertIn("btime_not_changed", gate)
        self.assertIn("boot_id_not_changed", gate)
        self.assertIn("pre_hash == post_hash", gate)
        self.assertIn("post_btime <= pre_btime", gate)
        self.assertIn("boot_time_capture_inconsistent", gate)
        self.assertIn("post_uptime_too_high", gate)
        self.assertIn("requires_mounts_for_data_missing", gate)
        self.assertIn("adoption_probe_missing", gate)
        self.assertIn("running_identity_matches_marker", gate)
        self.assertIn("uuid_source", gate)
        self.assertIn("raw_uuid", gate)
        self.assertIn("raw_block_device", gate)
        self.assertIn("privacy_leak", gate)
        self.assertIn("CURRENT_COLDBOOT_EVIDENCE_DIR", release_gate)
        self.assertIn("c18_coldboot_evidence_current", release_gate)
        self.assertIn("20260605T093008Z-1t-coldboot-deep-health", release_gate)
        self.assertIn("c18_coldboot_evidence_gate.py", release_gate)
        result = subprocess.run(
            ["python3", str(COLDBOOT_EVIDENCE_GATE_PATH), "--self-test"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run(
            [
                "python3",
                str(COLDBOOT_EVIDENCE_GATE_PATH),
                "--run-dir",
                str(EVIDENCE_CURRENT_DEEP_HEALTH_DIR),
                "--expect-selected-source",
                "fallback",
                "--json",
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_c18_player_runtime_fault_hooks_and_corrupt_state_fail_closed_are_wired(self) -> None:
        updatectl = UPDATECTL_PATH.read_text(encoding="utf-8")
        self.assertIn("PLAYER_RUNTIME_FAULT_HOOK", updatectl)
        self.assertIn("after_marker_written", updatectl)
        self.assertIn("after_current_symlink", updatectl)
        self.assertIn("rollback_after_current_to_previous", updatectl)
        self.assertIn("state_file_corrupt_fail_closed", updatectl)
        self.assertIn("_gc_player_runtime_invalid_orphan_releases", updatectl)
        self.assertIn("_fsync_release_tree(release_dir)", updatectl)

    def test_c18_player_runtime_future_trial_records_repo_identity(self) -> None:
        trial = PLAYER_RUNTIME_PERSISTENT_TRIAL_PATH.read_text(encoding="utf-8")
        evidence_gate = PLAYER_RUNTIME_EVIDENCE_GATE_PATH.read_text(encoding="utf-8")
        self.assertIn("def repo_identity", trial)
        self.assertIn("repo_info = repo_identity()", trial)
        self.assertLess(trial.index("repo_info = repo_identity()"), trial.index("evidence_dir = args.evidence_dir"))
        self.assertIn("repo_commit", trial)
        self.assertIn("repo_tree", trial)
        self.assertIn("repo_dirty", trial)
        self.assertIn("repo_exact_tag", trial)
        self.assertIn("manifest_repo_commit_package_source_mismatch", evidence_gate)
        self.assertIn("manifest_invalid_repo_commit", evidence_gate)
        self.assertIn("manifest_invalid_repo_tree", evidence_gate)
        self.assertIn("manifest_invalid_repo_dirty", evidence_gate)
        self.assertIn("manifest_repo_dirty", evidence_gate)

    def test_c18_current_player_runtime_data_trial_evidence_is_public_and_passing(self) -> None:
        evidence_dir = EVIDENCE_CURRENT_PLAYER_RUNTIME_TRIAL_DIR
        result = subprocess.run(
            [
                "python3",
                str(PLAYER_RUNTIME_EVIDENCE_GATE_PATH),
                "--run-dir",
                str(evidence_dir),
                "--json",
            ],
            cwd=REPO_ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        gate = json.loads(result.stdout)
        self.assertTrue(gate["passed"])
        self.assertEqual(gate["errors"], [])

        manifest = json.loads((evidence_dir / "evidence-manifest.json").read_text(encoding="utf-8"))
        readme = json.loads((evidence_dir / "README.md").read_text(encoding="utf-8"))
        lab_apply = json.loads((evidence_dir / "lab-apply.json").read_text(encoding="utf-8"))
        lab_rollback = json.loads((evidence_dir / "lab-rollback.json").read_text(encoding="utf-8"))
        restart_adoption = json.loads(
            (evidence_dir / "service-after-restart" / "launcher-adoption.json").read_text(encoding="utf-8")
        )
        rollback_adoption = json.loads(
            (evidence_dir / "service-after-rollback" / "launcher-adoption.json").read_text(encoding="utf-8")
        )
        release_gate = json.loads((evidence_dir / "package" / "player-runtime-release-gate.json").read_text(encoding="utf-8"))
        marker = json.loads((evidence_dir / "verified-marker.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["artifact_scope"], "player-runtime-persistent-data-lab-trial")
        self.assertEqual(manifest["component"], "player-runtime")
        self.assertEqual(manifest["channel"], "homologation")
        self.assertEqual(manifest["source_commit"], "1562cd37ec933107c5ccf5bc363a156d0b7fb988")
        self.assertEqual(manifest["rollback_expectation"], "image-fallback")
        self.assertEqual(
            manifest["payload_sha256"],
            "057d25e61e2876629145cd0bdabebe27bdf14d2699e595ca5de2da73f67ffafe",
        )
        self.assertEqual(release_gate["payload"]["kiosk_py_sha256"], marker["kiosk_py_sha256"])
        self.assertEqual(release_gate["payload"]["tree_sha256"], marker["tree_sha256"])
        self.assertIn("rollback_to_image_fallback", readme["claims"])
        self.assertIn("rollback_A_to_B_previous_data_release", readme["non_claims"])
        self.assertNotIn("public_thaw", readme["claims"])
        self.assertIn("public_thaw", readme["non_claims"])
        self.assertIn("stable_or_production", readme["non_claims"])
        self.assertIn("power_loss_safety", readme["non_claims"])
        self.assertIn("cold_boot_adoption", readme["non_claims"])
        self.assertIn("server_side_gate", readme["non_claims"])
        self.assertIn("soak_endurance", readme["non_claims"])

        self.assertTrue(lab_apply["device_data_root"])
        self.assertEqual(lab_apply["rc"], 0)
        self.assertFalse(lab_apply["github_used"])
        self.assertFalse(lab_apply["network_required"])
        self.assertEqual(lab_apply["public_cli_apply_still_frozen"]["returncode"], 44)
        self.assertEqual(lab_apply["public_cli_reconcile_still_frozen"]["returncode"], 44)

        self.assertTrue(restart_adoption["passed"])
        self.assertEqual(restart_adoption["selected_source"], "data")
        self.assertEqual(restart_adoption["selected_version"], manifest["version"])
        self.assertTrue(restart_adoption["marker_valid"])
        self.assertTrue(restart_adoption["running_identity_matches_marker"])
        self.assertEqual(restart_adoption["data_process_count"], 1)
        self.assertEqual(restart_adoption["fallback_process_count"], 0)

        rollback_operation = lab_rollback["operation"]
        self.assertEqual(rollback_operation["rc"], 0)
        self.assertEqual(rollback_operation["rolled_back_to"], "image_fallback")
        self.assertTrue(rollback_operation["quarantine_current"])
        self.assertFalse(rollback_operation["after"]["current_exists"])
        self.assertFalse(rollback_operation["after"]["previous_exists"])
        self.assertTrue(rollback_adoption["passed"])
        self.assertEqual(rollback_adoption["selected_source"], "fallback")
        self.assertEqual(rollback_adoption["selected_version"], "image_fallback")

        for relative in (
            "candidate-health/playback-deep-health-public.json",
            "service-after-restart/playback-deep-health-public.json",
            "service-after-rollback/playback-deep-health-public.json",
        ):
            public = json.loads((evidence_dir / relative).read_text(encoding="utf-8"))
            self.assertTrue(public["passed"], relative)
            counters = public["counters"]
            self.assertGreaterEqual(counters["samples"], 20)
            self.assertEqual(counters["estimated_frame_failed_segments"], 0)
            self.assertEqual(counters["hwdec_unexpected_samples"], 0)
            self.assertEqual(counters["media_load_failed"], 0)
            self.assertEqual(counters["mpv_restart"], 0)
            self.assertEqual(counters["panfrost_faults"], 0)
            self.assertEqual(counters["mmc_timeout_reset"], 0)
            self.assertEqual(counters["ext4_errors"], 0)
            self.assertEqual(counters["total_mpv_count"], 1)

    def test_c18_current_player_runtime_data_previous_trial_evidence_is_public_and_passing(self) -> None:
        evidence_dir = EVIDENCE_CURRENT_PLAYER_RUNTIME_ABA_TRIAL_DIR
        result = subprocess.run(
            [
                "python3",
                str(PLAYER_RUNTIME_EVIDENCE_GATE_PATH),
                "--run-dir",
                str(evidence_dir),
                "--json",
            ],
            cwd=REPO_ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        gate = json.loads(result.stdout)
        self.assertTrue(gate["passed"])
        self.assertEqual(gate["errors"], [])

        manifest = json.loads((evidence_dir / "evidence-manifest.json").read_text(encoding="utf-8"))
        readme = json.loads((evidence_dir / "README.md").read_text(encoding="utf-8"))
        lab_apply = json.loads((evidence_dir / "lab-apply.json").read_text(encoding="utf-8"))
        lab_rollback = json.loads((evidence_dir / "lab-rollback.json").read_text(encoding="utf-8"))
        before_adoption = json.loads(
            (evidence_dir / "service-before-apply" / "launcher-adoption.json").read_text(encoding="utf-8")
        )
        restart_adoption = json.loads(
            (evidence_dir / "service-after-restart" / "launcher-adoption.json").read_text(encoding="utf-8")
        )
        rollback_adoption = json.loads(
            (evidence_dir / "service-after-rollback" / "launcher-adoption.json").read_text(encoding="utf-8")
        )
        release_gate = json.loads((evidence_dir / "package" / "player-runtime-release-gate.json").read_text(encoding="utf-8"))
        marker = json.loads((evidence_dir / "verified-marker.json").read_text(encoding="utf-8"))

        version_a = "c18.player-runtime-ab-a-20260605T055913Z-8edcd1c"
        version_b = "c18.player-runtime-ab-b-20260605T055913Z-8edcd1c"

        self.assertEqual(manifest["artifact_scope"], "player-runtime-persistent-data-lab-trial")
        self.assertEqual(manifest["component"], "player-runtime")
        self.assertEqual(manifest["channel"], "homologation")
        self.assertEqual(manifest["source_commit"], "8edcd1ce4a2f1d92513ba55b6288c8169165af91")
        self.assertEqual(manifest["rollback_expectation"], "data-previous")
        self.assertEqual(manifest["version"], version_b)
        self.assertEqual(manifest["image_tag"], "c18-hwdecode-lab-1r")
        self.assertEqual(manifest["image_sha256"], EVIDENCE_PLAYER_RUNTIME_TRIAL_IMAGE_SHA256)
        self.assertEqual(
            manifest["payload_sha256"],
            "4185d7059087d79ba3bb16e52b1b5a3bfe50e4d3f83eadb131b6e7a256f7fe59",
        )
        self.assertEqual(release_gate["payload"]["kiosk_py_sha256"], marker["kiosk_py_sha256"])
        self.assertEqual(release_gate["payload"]["tree_sha256"], marker["tree_sha256"])
        self.assertEqual(marker["version"], version_b)
        self.assertEqual(marker["tree_sha256"], restart_adoption["marker_tree_sha256"])
        self.assertEqual(marker["kiosk_py_sha256"], restart_adoption["marker_kiosk_py_sha256"])
        self.assertNotEqual(before_adoption["marker_tree_sha256"], marker["tree_sha256"])
        self.assertNotEqual(before_adoption["marker_kiosk_py_sha256"], marker["kiosk_py_sha256"])

        self.assertIn("rollback_to_data_previous", readme["claims"])
        self.assertNotIn("rollback_to_image_fallback", readme["claims"])
        self.assertNotIn("public_thaw", readme["claims"])
        self.assertIn("public_thaw", readme["non_claims"])
        self.assertIn("github_publish", readme["non_claims"])
        self.assertIn("auto_pull", readme["non_claims"])
        self.assertIn("stable_or_production", readme["non_claims"])
        self.assertIn("power_loss_safety", readme["non_claims"])
        self.assertIn("cold_boot_adoption", readme["non_claims"])
        self.assertIn("server_side_gate", readme["non_claims"])
        self.assertIn("soak_endurance", readme["non_claims"])

        self.assertTrue(before_adoption["passed"])
        self.assertEqual(before_adoption["selected_source"], "data")
        self.assertEqual(before_adoption["selected_version"], version_a)
        self.assertEqual(before_adoption["current_link"], f"releases/{version_a}")
        self.assertTrue(before_adoption["marker_valid"])
        self.assertTrue(before_adoption["running_identity_matches_marker"])
        self.assertEqual(before_adoption["data_process_count"], 1)
        self.assertEqual(before_adoption["fallback_process_count"], 0)

        self.assertTrue(lab_apply["device_data_root"])
        self.assertEqual(lab_apply["rc"], 0)
        self.assertFalse(lab_apply["github_used"])
        self.assertFalse(lab_apply["network_required"])
        self.assertEqual(lab_apply["public_cli_apply_still_frozen"]["returncode"], 44)
        self.assertEqual(lab_apply["public_cli_reconcile_still_frozen"]["returncode"], 44)
        self.assertEqual(lab_apply["before"]["current_link"], f"releases/{version_a}")
        self.assertFalse(lab_apply["before"]["previous_exists"])
        self.assertEqual(lab_apply["after"]["current_link"], f"releases/{version_b}")
        self.assertEqual(lab_apply["after"]["previous_link"], f"releases/{version_a}")
        self.assertEqual(lab_apply["after"]["state_current_version"], version_b)
        self.assertEqual(lab_apply["after"]["state_previous_version"], version_a)

        self.assertTrue(restart_adoption["passed"])
        self.assertEqual(restart_adoption["selected_source"], "data")
        self.assertEqual(restart_adoption["selected_version"], version_b)
        self.assertEqual(restart_adoption["previous_link"], f"releases/{version_a}")
        self.assertTrue(restart_adoption["marker_valid"])
        self.assertTrue(restart_adoption["running_identity_matches_marker"])
        self.assertEqual(restart_adoption["data_process_count"], 1)
        self.assertEqual(restart_adoption["fallback_process_count"], 0)

        rollback_operation = lab_rollback["operation"]
        self.assertEqual(rollback_operation["rc"], 0)
        self.assertEqual(rollback_operation["expected_rolled_to"], version_a)
        self.assertEqual(rollback_operation["rolled_back_to"], version_a)
        self.assertNotEqual(rollback_operation["rolled_back_to"], "image_fallback")
        self.assertTrue(rollback_operation["quarantine_current"])
        self.assertEqual(rollback_operation["before"]["current_link"], f"releases/{version_b}")
        self.assertEqual(rollback_operation["before"]["previous_link"], f"releases/{version_a}")
        self.assertEqual(rollback_operation["after"]["current_link"], f"releases/{version_a}")
        self.assertFalse(rollback_operation["after"]["previous_exists"])
        self.assertEqual(rollback_operation["after"]["state_current_version"], version_a)
        self.assertIsNone(rollback_operation["after"]["state_previous_version"])
        self.assertEqual(lab_rollback["public_cli_apply_still_frozen"]["returncode"], 44)
        self.assertEqual(lab_rollback["public_cli_reconcile_still_frozen"]["returncode"], 44)
        self.assertEqual(lab_rollback["public_cli_rollback_still_frozen"]["returncode"], 44)

        self.assertTrue(rollback_adoption["passed"])
        self.assertEqual(rollback_adoption["selected_source"], "data")
        self.assertEqual(rollback_adoption["selected_version"], version_a)
        self.assertEqual(rollback_adoption["current_link"], f"releases/{version_a}")
        self.assertTrue(rollback_adoption["marker_valid"])
        self.assertTrue(rollback_adoption["running_identity_matches_marker"])
        self.assertEqual(rollback_adoption["data_process_count"], 1)
        self.assertEqual(rollback_adoption["fallback_process_count"], 0)

        for relative in (
            "candidate-health/playback-deep-health-public.json",
            "service-before-apply/playback-deep-health-public.json",
            "service-after-restart/playback-deep-health-public.json",
            "service-after-rollback/playback-deep-health-public.json",
        ):
            public = json.loads((evidence_dir / relative).read_text(encoding="utf-8"))
            self.assertTrue(public["passed"], relative)
            counters = public["counters"]
            checks = public["checks"]
            self.assertGreaterEqual(counters["samples"], 20)
            self.assertGreaterEqual(counters["estimated_frame_positive_steps"], counters["estimated_frame_required_steps"])
            self.assertEqual(counters["estimated_frame_failed_segments"], 0)
            self.assertEqual(counters["estimated_frame_trailing_nonprogress_steps"], 0)
            self.assertEqual(counters["hwdec_unexpected_samples"], 0)
            self.assertEqual(counters["media_load_failed"], 0)
            self.assertEqual(counters["mpv_restart"], 0)
            self.assertEqual(counters["panfrost_faults"], 0)
            self.assertEqual(counters["mmc_timeout_reset"], 0)
            self.assertEqual(counters["ext4_errors"], 0)
            self.assertEqual(counters["total_mpv_count"], 1)
            self.assertTrue(checks["hwdec_no_unexpected"], relative)
            self.assertTrue(checks["estimated_frame_present"], relative)
            self.assertTrue(checks["playback_progressed"], relative)

    def test_legacy_kiosky_player_builder_rejects_stable_even_with_bypass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="c18-kiosky-builder-stable-") as tmp:
            root = Path(tmp)
            repo = root / "kiosky-player"
            out = root / "out"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "C18 Test"], cwd=repo, check=True)
            (repo / "kiosk.py").write_text("print('ok')\n", encoding="utf-8")
            subprocess.run(["git", "add", "kiosk.py"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            env = os.environ.copy()
            env["ALLOW_C18_FROZEN_PLAYER_RELEASE"] = "1"
            result = subprocess.run(
                [
                    str(BUILD_PLAYER_PATH),
                    "--prepare-only",
                    "--channel=stable",
                    f"--kiosky-repo={repo}",
                    f"--out-base={out}",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("stable", result.stdout + result.stderr)

    def test_player_runtime_builder_is_lab_only_and_gated(self) -> None:
        script = BUILD_PLAYER_RUNTIME_PATH.read_text(encoding="utf-8")
        self.assertIn('COMPONENT="player-runtime"', script)
        self.assertIn("c18_player_runtime_release_gate.py", script)
        self.assertIn("lab builder only supports lab or homologation", script)
        self.assertIn("--lab-variant", script)
        self.assertIn("c18_player_runtime_lab_variant", script)
        self.assertIn('BUILD_DIR="$(mktemp -d -t player-runtime-build-XXXXXX)"', script)
        self.assertIn('TMP_PAYLOAD_PATH="$BUILD_DIR/$PAYLOAD_NAME"', script)
        self.assertIn('TMP_MANIFEST_PATH="$BUILD_DIR/$MANIFEST_NAME"', script)
        self.assertIn("--manifest", script)
        self.assertIn("--payload", script)
        self.assertIn('mv -f "$TMP_PAYLOAD_PATH" "$PAYLOAD_PATH"', script)
        self.assertLess(script.index('"$RELEASE_GATE"'), script.index('mv -f "$TMP_PAYLOAD_PATH" "$PAYLOAD_PATH"'))
        self.assertIn("does not publish", script)
        self.assertNotIn("gh release create", script)
        self.assertNotIn("ALLOW_C18_FROZEN_PLAYER_RELEASE", script)

        gate = (REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_release_gate.py").read_text(encoding="utf-8")
        self.assertIn("player-runtime stable releases are blocked", gate)

    def test_legacy_c14_remote_scripts_are_guarded_as_bypass(self) -> None:
        for path in LEGACY_C14_REMOTE_SCRIPTS:
            script = path.read_text(encoding="utf-8")
            self.assertIn("LEGACY C14 / BYPASS ONLY", script)
            self.assertIn("docs/UPDATE_CONTRACT.md", script)
            self.assertIn("ALLOW_LEGACY_C14_UPDATE_BYPASS", script)
            self.assertIn("legacy C14 update bypass is disabled for C18", script)

    def test_legacy_remote_bypass_scripts_are_guarded(self) -> None:
        for path in LEGACY_C18_REMOTE_BYPASS_SCRIPTS:
            script = path.read_text(encoding="utf-8")
            self.assertIn("LAB/BYPASS", script)
            self.assertIn("docs/UPDATE_CONTRACT.md", script)
            self.assertIn("ALLOW_LEGACY_C18_REMOTE_BYPASS", script)
            self.assertIn("legacy remote bypass is disabled for C18", script)

    def test_historical_docs_and_timer_point_to_c18_contract(self) -> None:
        roadmap = ROADMAP_PATH.read_text(encoding="utf-8")
        self.assertIn("Nota C18", roadmap)
        self.assertIn("UPDATE_CONTRACT.md", roadmap)
        self.assertIn("OTA C18 comum", roadmap)

        policy_doc = POLICY_DOC_PATH.read_text(encoding="utf-8")
        self.assertIn("OTA comum atual usa", policy_doc)
        self.assertIn("kiosky-player/current` e legado/congelado", policy_doc)

        timer = TIMER_PATH.read_text(encoding="utf-8")
        self.assertIn("Disabled legacy", timer)
        self.assertIn("C18 manual OTA only", timer)
        self.assertIn("timer disabled", timer)

    def test_update_contract_declares_c18_config_and_deep_health(self) -> None:
        contract = UPDATE_CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("Contrato De Config C18", contract)
        self.assertIn("/opt/totem/bin/totem-mpv-hwdecode", contract)
        self.assertIn("Deep-Health De Playback", contract)
        self.assertIn("hwdec-current=v4l2request-copy", contract)
        self.assertIn("media_load_failed=0", contract)
        self.assertIn("ALLOW_LEGACY_C18_REMOTE_BYPASS", contract)

    def test_playback_observers_collect_c18_decode_properties(self) -> None:
        for path in (PLAYBACK_OBSERVER_PATH, SERVICE_OBSERVER_PATH):
            script = path.read_text(encoding="utf-8")
            self.assertIn('C18_HWDECODE_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"', script)
            self.assertIn("mpv_path_c18_contract", script)
            self.assertIn("DECODE_HEALTH_RC", script)
            self.assertIn("check_decode_health_summary", script)
            self.assertIn("post-c18-decode-health", script)
            self.assertIn('"hwdec-current"', script)
            self.assertIn('"vo-configured"', script)
            self.assertIn("hwdec_current", script)
            self.assertIn("vo_configured", script)
            self.assertIn('hwdec_expected = "v4l2request-copy"', script)
            self.assertIn("hwdec_ok_samples", script)
            self.assertIn("hwdec_unexpected_samples", script)
            self.assertIn("vo_configured_true_samples", script)
            self.assertIn("ipc_timeout_after_first_success", script)
            self.assertIn('"time-pos"', script)
            self.assertIn('"estimated-frame-number"', script)
            self.assertIn("def progressed(values):", script)
            self.assertIn("time_pos_progressed", script)
            self.assertIn("estimated_frame_progressed", script)
            self.assertIn("status_failure_samples", script)
            self.assertIn("c18_decode_health_passed", script)

        summary = (REPO_ROOT / "scripts" / "board" / "c18_playback_health_summary.py").read_text(encoding="utf-8")
        self.assertIn("def sustained_progress_stats(", summary)
        self.assertIn("def frame_progress_segments(", summary)
        self.assertIn("MIN_FRAME_PROGRESS_DELTAS", summary)
        self.assertIn("MAX_TRAILING_NONPROGRESS_DELTAS", summary)
        self.assertIn("estimated_frame_trailing_nonprogress_steps", summary)

        service_observer = SERVICE_OBSERVER_PATH.read_text(encoding="utf-8")
        self.assertIn("c18_playback_health_summary.py", service_observer)
        self.assertIn("deep-health-systemd.json", service_observer)
        self.assertIn("deep-health-process.json", service_observer)
        self.assertIn("deep-health-kernel.json", service_observer)
        self.assertIn("deep-health-player-counters.json", service_observer)
        self.assertIn("playback-deep-health-public.json", service_observer)
        self.assertIn("post-c18-playback-deep-health", service_observer)
        self.assertIn("mmc.*(timeout|timed out|reset|I/O error)", service_observer)
        self.assertNotIn("mmc.*(timeout|reset|error)", service_observer)

        collector = PLAYBACK_HEALTH_COLLECTOR_PATH.read_text(encoding="utf-8")
        self.assertIn("c18_playback_health_summary", collector)
        self.assertIn("sanitize_poll_error", collector)
        self.assertIn('"polling_disabled"', collector)
        self.assertIn("playback-samples.tsv", collector)
        self.assertIn("deep-health-systemd.json", collector)
        self.assertIn("deep-health-process.json", collector)
        self.assertIn("deep-health-kernel.json", collector)
        self.assertIn("deep-health-player-counters.json", collector)
        self.assertIn("playback-deep-health-public.json", collector)
        self.assertIn("journalctl\", \"-k\", \"-b\"", collector)
        self.assertIn("EXT4-fs error|Aborting journal|Remounting filesystem read-only", collector)
        self.assertNotIn("systemctl stop", collector)
        self.assertNotIn("systemctl restart", collector)
        self.assertNotIn("systemctl start", collector)

        candidate = PLAYER_RUNTIME_CANDIDATE_HEALTH_PATH.read_text(encoding="utf-8")
        self.assertIn("C18_PLAYER_RUNTIME_CANDIDATE_HEALTH_LAB_ONLY", candidate)
        self.assertIn("--lab-only-candidate-runner", candidate)
        self.assertIn("config_ui_enabled", candidate)
        self.assertIn("observed_kiosk_py_sha256", candidate)
        self.assertIn("observed_tree_sha256", candidate)
        self.assertNotIn("PLAYER_RUNTIME_LAB_THAW_ENABLED = True", candidate)

        lab_apply = PLAYER_RUNTIME_LAB_APPLY_PATH.read_text(encoding="utf-8")
        self.assertIn("C18_PLAYER_RUNTIME_LAB_APPLY", lab_apply)
        self.assertIn("C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT", lab_apply)
        self.assertIn("--lab-only-apply", lab_apply)
        self.assertIn("--allow-device-data-root", lab_apply)
        self.assertIn('work_dir / "data"', lab_apply)
        self.assertIn("public_cli_apply_still_frozen", lab_apply)
        self.assertIn("release_gate.validate_release", lab_apply)
        self.assertIn("candidate_health.run_candidate_health", lab_apply)
        self.assertIn("public_cli_reconcile_still_frozen", lab_apply)
        self.assertNotIn("apply-github-latest", lab_apply)
        self.assertNotIn("gh release", lab_apply)

        candidate_health = PLAYER_RUNTIME_CANDIDATE_HEALTH_PATH.read_text(encoding="utf-8")
        self.assertIn("candidate health refuses to run candidate kiosk.py as root", candidate_health)
        self.assertIn("candidate_run_user", candidate_health)
        self.assertIn("candidate-health-result.json", candidate_health)

        lab_rollback = PLAYER_RUNTIME_LAB_ROLLBACK_PATH.read_text(encoding="utf-8")
        self.assertIn("C18_PLAYER_RUNTIME_LAB_ROLLBACK", lab_rollback)
        self.assertIn("C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT", lab_rollback)
        self.assertIn("--lab-only-rollback", lab_rollback)
        self.assertIn("--allow-device-data-root", lab_rollback)
        self.assertIn("_rollback_player_runtime_unfrozen", lab_rollback)
        self.assertIn("_reconcile_player_runtime_state", lab_rollback)
        self.assertIn("public_cli_rollback_still_frozen", lab_rollback)
        self.assertIn("public_cli_reconcile_still_frozen", lab_rollback)
        self.assertIn("--expect-rolled-to", lab_rollback)
        self.assertIn("expected_rolled_to", lab_rollback)
        self.assertIn("current_link", lab_rollback)
        self.assertIn("previous_link", lab_rollback)
        self.assertIn("rolled_back_to", lab_rollback)
        self.assertIn("quarantine_current", lab_rollback)
        self.assertNotIn("apply-github-latest", lab_rollback)
        self.assertNotIn("gh release", lab_rollback)

        adoption_probe = PLAYER_RUNTIME_ADOPTION_PROBE_PATH.read_text(encoding="utf-8")
        self.assertIn("dadooh.c18.player_runtime.adoption.v1", adoption_probe)
        self.assertIn("selected_source", adoption_probe)
        self.assertIn("running_identity_matches_marker", adoption_probe)
        self.assertNotIn("api_key", adoption_probe)

        evidence_gate = PLAYER_RUNTIME_EVIDENCE_GATE_PATH.read_text(encoding="utf-8")
        self.assertIn("ALLOWED_PATTERNS", evidence_gate)
        self.assertIn("evidence-manifest.json", evidence_gate)
        self.assertIn("sha256_file", evidence_gate)
        self.assertIn("validate_evidence_manifest", evidence_gate)
        self.assertIn("validate_semantics", evidence_gate)
        self.assertIn("validate_lab_apply", evidence_gate)
        self.assertIn("validate_adoption", evidence_gate)
        self.assertIn("lab_rollback_quarantine_current_required", evidence_gate)
        self.assertIn("data_previous_rollback_target_mismatch", evidence_gate)
        self.assertIn("release_gate_marker_tree_sha_mismatch", evidence_gate)
        self.assertIn("manifest_image_tag_sha_must_be_paired", evidence_gate)
        self.assertIn("playback-samples.tsv", evidence_gate)
        self.assertIn("service-after-rollback", evidence_gate)
        self.assertIn("status-samples.ndjson", evidence_gate)
        self.assertIn("candidate-config.json", evidence_gate)
        self.assertIn("LEAK_PATTERNS", evidence_gate)
        self.assertIn("/data/media", evidence_gate)
        self.assertIn("api_key", evidence_gate)
        self.assertIn("--self-test", evidence_gate)

        persistent_trial = PLAYER_RUNTIME_PERSISTENT_TRIAL_PATH.read_text(encoding="utf-8")
        self.assertIn("C18_PLAYER_RUNTIME_PERSISTENT_TRIAL", persistent_trial)
        self.assertIn("c18_player_runtime_lab_apply.py", persistent_trial)
        self.assertIn("c18_player_runtime_lab_rollback.py", persistent_trial)
        self.assertIn("c18_player_runtime_adoption_probe.py", persistent_trial)
        self.assertIn("c18_player_runtime_evidence_gate.py", persistent_trial)
        self.assertIn("public_thaw", persistent_trial)
        self.assertIn("--rollback-expectation", persistent_trial)
        self.assertIn("data_previous_trial_requires_distinct_tree_sha", persistent_trial)
        self.assertIn("service-before-apply", persistent_trial)
        self.assertIn("pre_trial_current_target", persistent_trial)
        self.assertIn("--image-tag", persistent_trial)
        self.assertIn("--image-sha256", persistent_trial)
        self.assertIn("--image-marker-file", persistent_trial)
        self.assertIn("abort-cleanup.json", persistent_trial)
        self.assertIn("--quarantine-current", persistent_trial)
        self.assertIn("run_systemctl_result(\"stop\")", persistent_trial)
        self.assertIn("run_systemctl_result(\"restart\")", persistent_trial)
        self.assertIn("time.sleep(max(args.startup_wait_sec, 0.0))", persistent_trial)
        self.assertIn("package_evidence_dir.mkdir(parents=True, exist_ok=True)", persistent_trial)
        self.assertNotIn("def run_systemctl(", persistent_trial)
        self.assertNotIn("run_systemctl(\"restart\")", persistent_trial)
        self.assertIn("signal.SIGTERM", persistent_trial)

        update_auth = UPDATE_AUTHORIZATION_HEALTH_PATH.read_text(encoding="utf-8")
        self.assertIn("c18_player_runtime_lab_rollback.py", update_auth)
        self.assertIn("C18_PLAYER_RUNTIME_LAB_ROLLBACK", update_auth)
        self.assertIn("c18_player_runtime_evidence_gate.py", update_auth)
        self.assertIn("abort-cleanup.json", update_auth)
        self.assertIn("boot reconcile nao", update_auth)

    def test_release_gate_blocks_player_runtime_diff(self) -> None:
        gate = RELEASE_GATE_PATH.read_text(encoding="utf-8")
        self.assertIn("totem_config_contract_self_test", gate)
        self.assertIn("PLAYER_RUNTIME_DIFF_PATHS", gate)
        self.assertIn('"scripts/board/kiosky_service_launcher.sh"', gate)
        self.assertIn("player_runtime_diff_guard", gate)
        self.assertIn("--base-ref", gate)
        self.assertIn("C18_OTA_BASE_REF", gate)
        self.assertIn("merge-base", gate)
        self.assertIn("requires image/homologation", gate)

    def test_release_gate_base_ref_catches_committed_player_runtime_diff(self) -> None:
        spec = importlib.util.spec_from_file_location("c18_ota_release_gate_test", RELEASE_GATE_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)  # type: ignore[union-attr]

        with tempfile.TemporaryDirectory(prefix="c18-base-ref-gate-") as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "C18 Test"], cwd=root, check=True)
            protected = root / "player-runtime" / "kiosky-player" / "kiosk.py"
            protected.parent.mkdir(parents=True)
            protected.write_text("print('base')\n", encoding="utf-8")
            ordinary = root / "scripts" / "board" / "totem_status_render_preview.py"
            ordinary.parent.mkdir(parents=True)
            ordinary.write_text("print('base')\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()

            ordinary.write_text("print('ordinary')\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "ordinary"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            old_root = gate.REPO_ROOT
            try:
                gate.REPO_ROOT = root
                self.assertTrue(gate.player_runtime_diff_guard(base)["passed"])
                protected.write_text("print('protected')\n", encoding="utf-8")
                subprocess.run(["git", "add", "."], cwd=root, check=True)
                subprocess.run(["git", "commit", "-m", "protected"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                result = gate.player_runtime_diff_guard(base)
                self.assertFalse(result["passed"])
                self.assertIn("player-runtime/kiosky-player/kiosk.py", result["stdout_tail"])
            finally:
                gate.REPO_ROOT = old_root

    def test_player_runtime_lab_apply_guards_are_executable(self) -> None:
        missing_manifest = Path(tempfile.gettempdir()) / "c18-missing-player-runtime.manifest.json"
        missing_payload = Path(tempfile.gettempdir()) / "c18-missing-player-runtime.tar.gz"
        base_cmd = [
            "python3",
            str(PLAYER_RUNTIME_LAB_APPLY_PATH),
            "--manifest",
            str(missing_manifest),
            "--payload",
            str(missing_payload),
        ]

        no_lab = subprocess.run(
            [*base_cmd, "--json"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(no_lab.returncode, 44)

        env = {"PATH": os.environ.get("PATH", ""), "C18_PLAYER_RUNTIME_LAB_APPLY": "1"}
        for guarded_arg in (
            ["--lab-only-apply", "--data-root", "/data/foo"],
            ["--lab-only-apply", "--output-dir", "/data/foo"],
        ):
            proc = subprocess.run(
                [*base_cmd, *guarded_arg, "--json"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 43, proc.stderr)
            self.assertIn("device_data_root_guard_required", proc.stderr)

    def test_player_runtime_lab_rollback_guards_are_executable(self) -> None:
        base_cmd = [
            "python3",
            str(PLAYER_RUNTIME_LAB_ROLLBACK_PATH),
        ]

        no_lab = subprocess.run(
            [*base_cmd, "--json"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(no_lab.returncode, 44)

        env = {"PATH": os.environ.get("PATH", ""), "C18_PLAYER_RUNTIME_LAB_ROLLBACK": "1"}
        for guarded_arg in (
            ["--lab-only-rollback", "--data-root", "/data/foo"],
            ["--lab-only-rollback", "--output-dir", "/data/foo"],
        ):
            proc = subprocess.run(
                [*base_cmd, *guarded_arg, "--json"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(proc.returncode, 43, proc.stderr)
            self.assertIn("device_data_root_guard_required", proc.stderr)

    def test_player_runtime_evidence_gate_self_test_passes(self) -> None:
        proc = subprocess.run(
            ["python3", str(PLAYER_RUNTIME_EVIDENCE_GATE_PATH), "--self-test"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
