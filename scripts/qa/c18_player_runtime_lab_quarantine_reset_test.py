#!/usr/bin/env python3
"""Tests for the C18 player-runtime lab quarantine reset harness."""

from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RESET_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_lab_quarantine_reset.py"
RELEASE_GATE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_release_gate.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reset = load_module(RESET_PATH, "c18_player_runtime_lab_quarantine_reset_under_test")
release_gate = load_module(RELEASE_GATE_PATH, "c18_player_runtime_release_gate_for_reset_test")


class C18PlayerRuntimeLabQuarantineResetTest(unittest.TestCase):
    def make_package(self, root: Path, version: str, suffix: str = "target") -> tuple[Path, Path, dict]:
        source = release_gate.SNAPSHOT_KIOSK.read_text(encoding="utf-8") + f"\n# quarantine reset test {suffix}\n"
        payload = release_gate.write_payload(root, version, source)
        manifest = release_gate.write_manifest(root, version, payload)
        identity = reset.payload_identity(json.loads(manifest.read_text(encoding="utf-8")), payload)
        return manifest, payload, identity

    def seed_state(
        self,
        data_root: Path,
        out: Path,
        quarantine: list[dict],
        *,
        current_link: str = "releases/runtime-current",
        previous_link: str = "releases/runtime-previous",
    ) -> None:
        reset.configure_updatectl_for_lab(data_root, out / "policy.json")
        reset.updatectl.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        reset.updatectl._write_state({
            "schema": reset.updatectl.SCHEMA_STATE,
            "component": "player-runtime",
            "current": {"version": current_link.split("/")[-1]},
            "previous": {"version": previous_link.split("/")[-1]} if previous_link else None,
            "quarantine": quarantine,
        })
        reset.updatectl.CURRENT_LINK.parent.mkdir(parents=True, exist_ok=True)
        reset.updatectl.CURRENT_LINK.symlink_to(current_link)
        if previous_link:
            reset.updatectl.PREVIOUS_LINK.symlink_to(previous_link)

    def run_reset(self, args: list[str]) -> int:
        old_lab = os.environ.get(reset.LAB_ENV)
        try:
            os.environ[reset.LAB_ENV] = "1"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return reset.main(args)
        finally:
            if old_lab is None:
                os.environ.pop(reset.LAB_ENV, None)
            else:
                os.environ[reset.LAB_ENV] = old_lab

    def write_setup_contention_evidence(self, root: Path, identity: dict) -> Path:
        health_dir = root / "failed-candidate-health"
        (health_dir / "health").mkdir(parents=True, exist_ok=True)
        (health_dir / "candidate-health-result.json").write_text(json.dumps({
            "schema": "dadooh.c18.playback.deep_health.v1",
            "candidate_version": identity["version"],
            "passed": False,
            "failure_reasons": sorted(reset.SETUP_CONTENTION_FAILURE_REASONS),
            "checks": {"service_active": True},
            "counters": {"total_mpv_count": 2},
        }, sort_keys=True) + "\n", encoding="utf-8")
        (health_dir / "health" / "deep-health-process.json").write_text(json.dumps({
            "mpv_count": 1,
            "total_mpv_count": 2,
        }, sort_keys=True) + "\n", encoding="utf-8")
        (health_dir / "mpv.log").write_text(
            "Failed to acquire DRM master: Permission denied\n"
            "Error opening/initializing the selected video_out (--vo) device.\n",
            encoding="utf-8",
        )
        return health_dir

    def write_no_canary_retry_evidence(
        self,
        root: Path,
        identity: dict,
        *,
        progressed: bool = False,
        canary_used: bool = False,
    ) -> Path:
        health_dir = root / "failed-no-canary-health"
        health_dir.mkdir(parents=True, exist_ok=True)
        failures = sorted(reset.NO_CANARY_FAILURE_REASONS)
        counters = {
            "playlist_size_max": 0,
            "mpv_count": 0,
            "ipc_success": 0,
            "hwdec_expected_samples": 0,
            "vo_configured_true_samples": 0,
        }
        if progressed:
            counters["mpv_count"] = 1
        (health_dir / "candidate-health-result.json").write_text(json.dumps({
            "schema": "dadooh.c18.playback.deep_health.v1",
            "candidate_version": identity["version"],
            "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
            "observed_tree_sha256": identity["tree_sha256"],
            "canary_media_used": canary_used,
            "passed": False,
            "failure_reasons": failures,
            "checks": {
                "media_load_failed_zero": True,
                "panfrost_faults_delta_zero": True,
                "ext4_errors_zero": True,
                "mmc_timeout_reset_zero": True,
            },
            "counters": counters,
            "candidate_teardown": {
                "gpu_faults_delta": 0,
                "stop": {
                    "method": "none",
                    "returncode": 2,
                },
            },
        }, sort_keys=True) + "\n", encoding="utf-8")
        return health_dir

    def write_harness_ipc_drm_retry_evidence(
        self,
        root: Path,
        identity: dict,
        *,
        include_drm_marker: bool = True,
        include_af_unix_marker: bool = True,
        ipc_success: int = 0,
    ) -> Path:
        health_dir = root / "failed-harness-ipc-drm-health"
        health_dir.mkdir(parents=True, exist_ok=True)
        (health_dir / "candidate-health-result.json").write_text(json.dumps({
            "schema": "dadooh.c18.playback.deep_health.v1",
            "candidate_version": identity["version"],
            "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
            "observed_tree_sha256": identity["tree_sha256"],
            "canary_media_used": True,
            "passed": False,
            "failure_reasons": sorted(reset.HARNESS_IPC_DRM_FAILURE_REASONS),
            "checks": {
                "media_load_failed_zero": True,
                "panfrost_faults_delta_zero": True,
                "ext4_errors_zero": True,
                "mmc_timeout_reset_zero": True,
            },
            "counters": {
                "playlist_size_max": 1,
                "mpv_count": 0,
                "total_mpv_count": 1,
                "ipc_success": ipc_success,
                "hwdec_expected_samples": 0,
                "status_failure_samples": 12,
            },
            "candidate_teardown": {
                "gpu_faults_delta": 0,
                "stop": {
                    "method": "none",
                    "returncode": 3,
                },
            },
        }, sort_keys=True) + "\n", encoding="utf-8")
        drm = "Failed to acquire DRM master: Permission denied\n" if include_drm_marker else ""
        af_unix = "AF_UNIX path too long\n" if include_af_unix_marker else ""
        (health_dir / "mpv-g001.log").write_text(
            "Could not create IPC socket\n"
            + af_unix
            + drm
            + "Error opening/initializing the VO window.\n",
            encoding="utf-8",
        )
        (health_dir / "kiosk.log").write_text(
            "MPV IPC fresh command failed error="
            + ("AF_UNIX path too long" if include_af_unix_marker else "permission denied")
            + "\n",
            encoding="utf-8",
        )
        return health_dir

    def test_guard_blocks_without_env_and_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, _identity = self.make_package(root, "runtime-reset-guard")
            old_lab = os.environ.pop(reset.LAB_ENV, None)
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    rc = reset.main([
                        "--manifest", str(manifest),
                        "--payload", str(payload),
                        "--reset-scope", "p0_isolation_reset",
                        "--reason", "unit",
                    ])
            finally:
                if old_lab is not None:
                    os.environ[reset.LAB_ENV] = old_lab
            self.assertEqual(rc, 44)

    def test_removes_only_matching_target_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-target")
            _other_manifest, _other_payload, other_identity = self.make_package(root, "runtime-reset-other", "other")
            data_root = root / "data"
            out = root / "out"
            self.seed_state(
                data_root,
                out,
                [
                    {**identity, "reason": "physical_powerloss_trial"},
                    {**other_identity, "reason": "unrelated"},
                ],
            )

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_isolation_reset",
                "--reason", "unit-repeat-p0",
            ])

            self.assertEqual(rc, 0)
            after = reset.updatectl._read_state()
            entries = reset.updatectl._quarantine_entries(after)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["version"], other_identity["version"])
            self.assertEqual(reset.updatectl._read_symlink_target(reset.updatectl.CURRENT_LINK), "releases/runtime-current")
            self.assertEqual(reset.updatectl._read_symlink_target(reset.updatectl.PREVIOUS_LINK), "releases/runtime-previous")
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["removed_count"], 1)
            self.assertTrue(result["public_cli_apply_still_frozen"]["frozen"])
            self.assertTrue(result["public_cli_rollback_still_frozen"]["frozen"])
            self.assertTrue(result["public_cli_reconcile_still_frozen"]["frozen"])

    def test_rejects_reset_when_target_is_linked_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-active")
            data_root = root / "data"
            out = root / "out"
            self.seed_state(
                data_root,
                out,
                [{**identity, "reason": "physical_powerloss_trial"}],
                current_link="releases/runtime-reset-active",
            )

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_isolation_reset",
                "--reason", "unit-repeat-p0",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("target_linked_active", result["blockers"])
            self.assertEqual(result["active_links"], ["current"])

    def test_arm_timeout_scope_removes_previous_linked_target_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-previous-only")
            data_root = root / "data"
            out = root / "out"
            self.seed_state(
                data_root,
                out,
                [{**identity, "reason": "physical_powerloss_trial"}],
                current_link="releases/runtime-reset-bridge",
                previous_link="releases/runtime-reset-previous-only",
            )

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "h2_rollback_arm_timeout_previous_linked",
                "--reason", "unit-arm-timeout-previous-linked",
            ])

            self.assertEqual(rc, 0)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(entries, [])
            self.assertEqual(reset.updatectl._read_symlink_target(reset.updatectl.CURRENT_LINK), "releases/runtime-reset-bridge")
            self.assertEqual(reset.updatectl._read_symlink_target(reset.updatectl.PREVIOUS_LINK), "releases/runtime-reset-previous-only")
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["active_links"], ["previous"])
            self.assertTrue(result["previous_linked_reset_allowed"])

    def test_arm_timeout_scope_still_rejects_current_linked_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-current-timeout")
            data_root = root / "data"
            out = root / "out"
            self.seed_state(
                data_root,
                out,
                [{**identity, "reason": "physical_powerloss_trial"}],
                current_link="releases/runtime-reset-current-timeout",
                previous_link="releases/runtime-reset-bridge",
            )

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "h2_rollback_arm_timeout_previous_linked",
                "--reason", "unit-arm-timeout-current-linked",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("target_linked_active", result["blockers"])
            self.assertEqual(result["active_links"], ["current"])
            self.assertFalse(result["previous_linked_reset_allowed"])

    def test_rejects_non_powerloss_quarantine_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-healthfail")
            data_root = root / "data"
            out = root / "out"
            self.seed_state(data_root, out, [{**identity, "reason": "candidate_health_failed"}])

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_isolation_reset",
                "--reason", "unit-repeat-p0",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("target_quarantine_reason_not_allowed", result["blockers"])
            self.assertEqual(result["removed_count"], 0)

    def test_rejects_lab_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = release_gate.write_payload(
                root,
                "runtime-reset-lab-channel",
                release_gate.SNAPSHOT_KIOSK.read_text(encoding="utf-8"),
            )
            manifest = release_gate.write_manifest(root, "runtime-reset-lab-channel", payload, {"channel": "lab"})
            data_root = root / "data"
            out = root / "out"

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_isolation_reset",
                "--reason", "unit-repeat-p0",
            ])

            self.assertEqual(rc, 42)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("manifest_channel_not_homologation", result["blockers"])

    def test_pre_freeze_failure_does_not_mutate_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-prefreeze")
            data_root = root / "data"
            out = root / "out"
            self.seed_state(data_root, out, [{**identity, "reason": "physical_powerloss_trial"}])
            original = reset.public_cli_freeze
            reset.public_cli_freeze = lambda data_root, action: {"returncode": 0, "frozen": False}
            try:
                rc = self.run_reset([
                    "--lab-only-quarantine-reset",
                    "--manifest", str(manifest),
                    "--payload", str(payload),
                    "--data-root", str(data_root),
                    "--output-dir", str(out),
                    "--reset-scope", "p0_isolation_reset",
                    "--reason", "unit-repeat-p0",
                ])
            finally:
                reset.public_cli_freeze = original

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("public_cli_not_frozen_before_reset", result["blockers"])
            self.assertEqual(result["removed_count"], 0)

    def test_setup_contention_retry_requires_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-contention-missing")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.SETUP_CONTENTION_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_setup_contention_retry",
                "--reason", "unit-contention-retry",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("setup_contention_evidence_missing", result["blockers"])
            self.assertEqual(result["removed_count"], 0)

    def test_setup_contention_retry_removes_matching_quarantine_with_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-contention")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.SETUP_CONTENTION_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_setup_contention_evidence(root, identity)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_setup_contention_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-contention-retry",
            ])

            self.assertEqual(rc, 0)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(entries, [])
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["removed_count"], 1)
            self.assertEqual(result["setup_contention_evidence"]["total_mpv_count"], 2)

    def test_no_canary_retry_requires_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-no-canary-missing")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.NO_CANARY_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_no_canary_retry",
                "--reason", "unit-no-canary-retry",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("no_canary_retry_evidence_missing", result["blockers"])
            self.assertEqual(result["removed_count"], 0)

    def test_no_canary_retry_removes_matching_quarantine_with_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-no-canary")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.NO_CANARY_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_no_canary_retry_evidence(root, identity)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_no_canary_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-no-canary-retry",
            ])

            self.assertEqual(rc, 0)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(entries, [])
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["removed_count"], 1)
            self.assertEqual(result["no_canary_retry_evidence"]["playlist_size_max"], 0)

    def test_no_canary_retry_rejects_if_candidate_started_playback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-no-canary-started")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.NO_CANARY_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_no_canary_retry_evidence(root, identity, progressed=True)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_no_canary_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-no-canary-retry",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("no_canary_retry_mpv_process_started", result["blockers"])
            self.assertEqual(result["removed_count"], 0)

    def test_no_canary_retry_rejects_if_canary_was_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-no-canary-with-canary")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.NO_CANARY_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_no_canary_retry_evidence(root, identity, canary_used=True)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_no_canary_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-no-canary-retry",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("no_canary_retry_canary_was_used", result["blockers"])
            self.assertEqual(result["removed_count"], 0)

    def test_harness_ipc_drm_retry_removes_matching_quarantine_with_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-harness-ipc-drm")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.HARNESS_IPC_DRM_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_harness_ipc_drm_retry_evidence(root, identity)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_harness_ipc_drm_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-harness-ipc-drm-retry",
            ])

            self.assertEqual(rc, 0)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(entries, [])
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["removed_count"], 1)
            self.assertTrue(result["harness_ipc_drm_retry_evidence"]["af_unix_path_too_long"])
            self.assertTrue(result["harness_ipc_drm_retry_evidence"]["drm_master_permission_denied"])

    def test_harness_ipc_drm_retry_rejects_without_drm_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-harness-no-marker")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.HARNESS_IPC_DRM_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_harness_ipc_drm_retry_evidence(root, identity, include_drm_marker=False)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_harness_ipc_drm_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-harness-ipc-drm-retry",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("harness_ipc_drm_retry_drm_marker_missing", result["blockers"])
            self.assertEqual(result["removed_count"], 0)

    def test_harness_ipc_drm_retry_rejects_without_af_unix_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-harness-no-af-unix")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.HARNESS_IPC_DRM_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_harness_ipc_drm_retry_evidence(root, identity, include_af_unix_marker=False)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_harness_ipc_drm_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-harness-ipc-drm-retry",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("harness_ipc_drm_retry_af_unix_marker_missing", result["blockers"])
            self.assertEqual(result["removed_count"], 0)

    def test_harness_ipc_drm_retry_rejects_ipc_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-harness-ipc-success")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.HARNESS_IPC_DRM_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_harness_ipc_drm_retry_evidence(root, identity, ipc_success=1)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_harness_ipc_drm_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-harness-ipc-drm-retry",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("harness_ipc_drm_retry_ipc_success_seen", result["blockers"])
            self.assertEqual(result["removed_count"], 0)

    def test_post_freeze_failure_reverts_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-postfreeze")
            data_root = root / "data"
            out = root / "out"
            self.seed_state(data_root, out, [{**identity, "reason": "physical_powerloss_trial"}])
            calls = {"count": 0}
            original = reset.public_cli_freeze

            def fake_freeze(data_root, action):
                calls["count"] += 1
                return {"returncode": 44 if calls["count"] <= 3 else 0, "frozen": calls["count"] <= 3}

            reset.public_cli_freeze = fake_freeze
            try:
                rc = self.run_reset([
                    "--lab-only-quarantine-reset",
                    "--manifest", str(manifest),
                    "--payload", str(payload),
                    "--data-root", str(data_root),
                    "--output-dir", str(out),
                    "--reset-scope", "p0_isolation_reset",
                    "--reason", "unit-repeat-p0",
                ])
            finally:
                reset.public_cli_freeze = original

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("public_cli_not_frozen_after_reset", result["blockers"])
            self.assertTrue(result["reverted"])

    def test_fails_when_target_is_not_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, _identity = self.make_package(root, "runtime-reset-absent")
            data_root = root / "data"
            out = root / "out"
            reset.configure_updatectl_for_lab(data_root, out / "policy.json")
            reset.updatectl.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            reset.updatectl._write_state({"schema": reset.updatectl.SCHEMA_STATE, "component": "player-runtime", "quarantine": []})

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_isolation_reset",
                "--reason", "unit-repeat-p0",
            ])

            self.assertEqual(rc, 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertFalse(result["passed"])
            self.assertEqual(result["removed_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
