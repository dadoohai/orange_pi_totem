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
PLAYBACK_HEALTH_COLLECTOR_PATH = REPO_ROOT / "scripts" / "board" / "c18_playback_health_collect.py"
PLAYER_RUNTIME_CANDIDATE_HEALTH_PATH = REPO_ROOT / "scripts" / "board" / "c18_player_runtime_candidate_health.py"
PLAYER_RUNTIME_LAB_APPLY_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_lab_apply.py"
PLAYER_RUNTIME_LAB_ROLLBACK_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_lab_rollback.py"
PLAYER_RUNTIME_ADOPTION_PROBE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_adoption_probe.py"
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
    REPO_ROOT / "docs" / "evidence" / "c18-update-validation" / "20260605T045500Z-1r-service-deep-health"
)
EVIDENCE_CURRENT_PLAYER_RUNTIME_TRIAL_DIR = (
    REPO_ROOT / "docs" / "evidence" / "c18-update-validation" / "20260605T052805Z-1r-player-runtime-data-trial"
)
EVIDENCE_CURRENT_IMAGE_SHA256 = "23ef26b4cdbd6c35643fdc41d8666da33dd259b387af05864c8f063506f7711c"
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

    def test_c18_docs_keep_1r_as_current_golden(self) -> None:
        current_tag = "c18-hwdecode-lab-1r"
        current_sha = EVIDENCE_CURRENT_IMAGE_SHA256
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
        self.assertIn(legacy_sha_1m, doc189)
        self.assertIn(legacy_sha_1n, doc189)
        self.assertIn(legacy_sha_1o, doc189)
        self.assertIn(legacy_sha_1q, doc189)
        self.assertIn("20260605T045500Z-1r-service-deep-health", doc189)
        doc188_top = DOC188_PATH.read_text(encoding="utf-8").split("---", 1)[0]
        self.assertNotIn(legacy_sha_1l, doc188_top)
        doc190_top = DOC190_PATH.read_text(encoding="utf-8").split("## Baseline", 1)[0]
        self.assertNotIn(legacy_sha_1j, doc190_top)

    def test_c18_current_hardware_evidence_is_public_and_passing(self) -> None:
        public = json.loads((EVIDENCE_CURRENT_DEEP_HEALTH_DIR / "playback-deep-health-public.json").read_text(encoding="utf-8"))
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
        self.assertEqual(privacy["schema"], "dadooh.c18.evidence.privacy_scan.v1")
        self.assertEqual(privacy["result"], "passed")
        self.assertTrue(all(value == 0 for value in privacy["scan_counts"].values()))
        self.assertEqual(manifest["schema"], "dadooh.c18.update_validation.evidence_manifest.v1")
        self.assertEqual(manifest["image_tag"], "c18-hwdecode-lab-1r")
        self.assertEqual(manifest["image_sha256"], EVIDENCE_CURRENT_IMAGE_SHA256)
        manifest_files = {item["file"]: item for item in manifest["artifacts"]}
        privacy_files = {item["file"]: item for item in privacy["files"]}
        for file_name, metadata in manifest_files.items():
            path = EVIDENCE_CURRENT_DEEP_HEALTH_DIR / file_name
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(path.stat().st_size, metadata["bytes"])
            self.assertEqual(digest, metadata["sha256"])
            self.assertIn(file_name, privacy_files)
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

        self.assertEqual(manifest["artifact_scope"], "player-runtime-persistent-data-lab-trial")
        self.assertEqual(manifest["component"], "player-runtime")
        self.assertEqual(manifest["channel"], "homologation")
        self.assertEqual(manifest["source_commit"], "1562cd37ec933107c5ccf5bc363a156d0b7fb988")
        self.assertEqual(
            manifest["payload_sha256"],
            "057d25e61e2876629145cd0bdabebe27bdf14d2699e595ca5de2da73f67ffafe",
        )
        self.assertNotIn("public_thaw", readme["claims"])
        self.assertIn("public_thaw", readme["non_claims"])
        self.assertIn("stable_or_production", readme["non_claims"])
        self.assertIn("power_loss_safety", readme["non_claims"])

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
        self.assertIn("pre_trial_current_target", persistent_trial)
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
