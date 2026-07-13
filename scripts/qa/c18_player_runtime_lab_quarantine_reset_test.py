#!/usr/bin/env python3
"""Tests for the C18 player-runtime lab quarantine reset harness."""

from __future__ import annotations

import importlib.util
import contextlib
import csv
import io
import json
import os
import shutil
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

    def write_setup_contention_evidence(
        self,
        root: Path,
        identity: dict,
        *,
        include_optional_absolute_faults: bool = False,
        clean_delta: bool = True,
        include_panfrost_policy_check: bool = True,
        panfrost_policy_clean: bool = False,
        include_storage_presence: bool = True,
        include_drm_marker: bool = True,
    ) -> Path:
        health_dir = root / "failed-candidate-health"
        (health_dir / "health").mkdir(parents=True, exist_ok=True)
        failures = set(reset.SETUP_CONTENTION_FAILURE_REASONS)
        checks = {"service_active": True}
        if include_optional_absolute_faults:
            failures.update(reset.SETUP_CONTENTION_OPTIONAL_ABSOLUTE_FAULT_REASONS)
            checks.update({
                "panfrost_faults_delta_present": True,
                "panfrost_faults_delta_zero": clean_delta,
                "ext4_errors_zero": True,
                "mmc_timeout_reset_zero": True,
            })
            if include_panfrost_policy_check:
                checks["panfrost_faults_clean_for_policy"] = panfrost_policy_clean
            if include_storage_presence:
                checks.update({
                    "ext4_errors_present": True,
                    "mmc_timeout_reset_present": True,
                })
        (health_dir / "candidate-health-result.json").write_text(json.dumps({
            "schema": "dadooh.c18.playback.deep_health.v1",
            "candidate_version": identity["version"],
            "passed": False,
            "failure_reasons": sorted(failures),
            "checks": checks,
            "counters": {"total_mpv_count": 2},
        }, sort_keys=True) + "\n", encoding="utf-8")
        (health_dir / "health" / "deep-health-process.json").write_text(json.dumps({
            "mpv_count": 1,
            "total_mpv_count": 2,
        }, sort_keys=True) + "\n", encoding="utf-8")
        (health_dir / "mpv.log").write_text(
            ("Failed to acquire DRM master: Permission denied\n" if include_drm_marker else "")
            + "Error opening/initializing the selected video_out (--vo) device.\n",
            encoding="utf-8",
        )
        return health_dir

    def write_prior_panfrost_absolute_evidence(
        self,
        root: Path,
        identity: dict,
        *,
        panfrost_delta: int = 0,
    ) -> Path:
        health_dir = root / "failed-prior-panfrost-health"
        health_dir.mkdir(parents=True, exist_ok=True)
        checks = {check: True for check in reset.PRIOR_PANFROST_FUNCTIONAL_CHECKS}
        checks.update({
            "panfrost_faults_zero": False,
            "panfrost_faults_clean_for_policy": False,
            "panfrost_faults_delta_zero": panfrost_delta == 0,
        })
        (health_dir / "candidate-health-result.json").write_text(json.dumps({
            "schema": "dadooh.c18.playback.deep_health.v1",
            "candidate_version": identity["version"],
            "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
            "observed_tree_sha256": identity["tree_sha256"],
            "passed": False,
            "failure_reasons": sorted(reset.PRIOR_PANFROST_ABSOLUTE_FAILURE_REASONS),
            "checks": checks,
            "counters": {
                "panfrost_fault_policy": "absolute",
                "panfrost_faults": 4,
                "panfrost_faults_start": 4,
                "panfrost_faults_delta": panfrost_delta,
                "ext4_errors_delta": 0,
                "mmc_timeout_reset_delta": 0,
                "mpv_count": 1,
                "total_mpv_count": 1,
                "ipc_success": 45,
                "hwdec_expected_samples": 45,
                "vo_configured_true_samples": 45,
                "media_load_failed": 0,
                "mpv_restart": 0,
                "nrestarts_delta": 0,
            },
            "candidate_teardown": {
                "passed": True,
                "gpu_faults_delta": 0,
                "process_stopped_cleanly": True,
                "stop": {
                    "method": "sigterm",
                    "returncode": 0,
                },
            },
        }, sort_keys=True) + "\n", encoding="utf-8")
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

    def write_canary_display_contention_evidence(
        self,
        root: Path,
        identity: dict,
        *,
        total_mpv_count: int = 2,
        ipc_success: int = 30,
        c25_surface_shape: bool = False,
        include_drm_marker: bool = True,
    ) -> Path:
        health_dir = root / "failed-canary-display-contention-health"
        (health_dir / "health").mkdir(parents=True, exist_ok=True)
        (health_dir / "candidate-health-result.json").write_text(json.dumps({
            "schema": "dadooh.c18.playback.deep_health.v1",
            "candidate_version": identity["version"],
            "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
            "observed_tree_sha256": identity["tree_sha256"],
            "canary_media_used": True,
            "passed": False,
            "failure_reasons": sorted(
                reset.C25_SURFACE_DISPLAY_CONTENTION_FAILURE_REASONS
                if c25_surface_shape
                else reset.SETUP_CONTENTION_FAILURE_REASONS
            ),
            "candidate_startup_surface_health_required": c25_surface_shape,
            "checks": {
                "service_active": not c25_surface_shape,
                "media_load_failed_zero": True,
                "panfrost_faults_delta_zero": True,
                "ext4_errors_zero": True,
                "mmc_timeout_reset_zero": True,
            },
            "counters": {
                "playlist_size_max": 1,
                "mpv_count": 0 if c25_surface_shape else 1,
                "total_mpv_count": 1 if c25_surface_shape else total_mpv_count,
                "ipc_success": ipc_success,
                "hwdec_expected_samples": 0,
                "vo_configured_true_samples": 0,
                "media_load_failed": 0,
                "status_failure_samples": 0,
            },
            "candidate_teardown": {
                "gpu_faults_delta": 0,
                "stop": {
                    "method": "none" if c25_surface_shape else "sigterm",
                    "returncode": 3 if c25_surface_shape else 0,
                },
            },
        }, sort_keys=True) + "\n", encoding="utf-8")
        (health_dir / "health" / "deep-health-process.json").write_text(json.dumps({
            "mpv_count": 0 if c25_surface_shape else 1,
            "total_mpv_count": 1 if c25_surface_shape else total_mpv_count,
        }, sort_keys=True) + "\n", encoding="utf-8")
        (health_dir / "mpv-g001.log").write_text(
            (
                "Failed to acquire DRM master: Permission denied\n"
                "Error opening/initializing the selected video_out (--vo) device.\n"
                if include_drm_marker
                else "video output unavailable\n"
            ),
            encoding="utf-8",
        )
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

    def write_surface_warmup_evidence(
        self,
        root: Path,
        identity: dict,
        *,
        freeze_motion: bool = False,
    ) -> Path:
        candidate_dir = root / "failed-surface-warmup-health"
        health_dir = candidate_dir / "health"
        fixture_dir = REPO_ROOT / "scripts" / "board" / "testdata" / "c18_playback_health" / "pass"
        shutil.copytree(fixture_dir, health_dir)
        runtime_dir = candidate_dir / "runtime"
        runtime_dir.mkdir(parents=True)
        surface_path = runtime_dir / "startup-feedback-c25-visible-state-loading-test.mp4"
        surface_path.write_bytes(b"surface")
        surface_alias = reset.playback_collect.safe_path_alias(str(surface_path))

        samples_path = health_dir / "playback-samples.tsv"
        with samples_path.open("r", encoding="utf-8", newline="") as fh:
            base_rows = list(csv.DictReader(fh, delimiter="\t"))
        rows: list[dict[str, str]] = []
        for index in range(2):
            row = base_rows[0].copy()
            row["seq"] = str(index + 1)
            row["rel_sec"] = str(index)
            row["current_alias"] = surface_alias
            row["path_alias"] = surface_alias
            row["duration"] = "0.04"
            row["estimated_frame_number"] = "0"
            row["status_current_alias"] = ""
            row["status_path_alias"] = ""
            row["status_current_index"] = ""
            row["video_params_json"] = json.dumps({"dw": 1280, "dh": 720}, separators=(",", ":"))
            rows.append(row)
        for index, source in enumerate(base_rows, start=3):
            row = source.copy()
            row["seq"] = str(index)
            row["rel_sec"] = str(index - 1)
            row["duration"] = "30.0"
            row["video_params_json"] = json.dumps({"dw": 1280, "dh": 720}, separators=(",", ":"))
            if freeze_motion:
                row["estimated_frame_number"] = "99"
            rows.append(row)
        with samples_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, delimiter="\t", fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        (health_dir / "systemd.json").replace(health_dir / "deep-health-systemd.json")
        systemd = json.loads((health_dir / "deep-health-systemd.json").read_text(encoding="utf-8"))
        systemd["target_mode"] = "candidate"
        (health_dir / "deep-health-systemd.json").write_text(json.dumps(systemd) + "\n", encoding="utf-8")
        (health_dir / "process.json").replace(health_dir / "deep-health-process.json")
        process = json.loads((health_dir / "deep-health-process.json").read_text(encoding="utf-8"))
        process["process_filter"] = "input-ipc-server"
        (health_dir / "deep-health-process.json").write_text(json.dumps(process) + "\n", encoding="utf-8")
        (health_dir / "kernel.json").replace(health_dir / "deep-health-kernel.json")
        kernel = json.loads((health_dir / "deep-health-kernel.json").read_text(encoding="utf-8"))
        kernel.update({"panfrost_faults_start": 0, "panfrost_faults_delta": 0})
        (health_dir / "deep-health-kernel.json").write_text(json.dumps(kernel) + "\n", encoding="utf-8")
        (health_dir / "player-counters.json").replace(health_dir / "deep-health-player-counters.json")

        true_checks = {
            "samples_present": True,
            "ipc_success_present": True,
            "ipc_stable_after_success": True,
            "hwdec_expected_present": True,
            "hwdec_no_unexpected": True,
            "vo_configured_present": True,
            "vo_configured_no_unexpected": True,
            "estimated_frame_present": True,
            "playback_progressed": False,
            "status_no_failures": True,
            "transitions_observed_when_required": True,
            "status_mpv_path_aligned": True,
            "service_active": True,
            "nrestarts_delta_present": True,
            "nrestarts_stable": True,
            "single_mpv": True,
            "candidate_process_filtered": True,
            "mpv_path_c18_stack": True,
            "media_load_failed_present": True,
            "media_load_failed_zero": True,
            "mpv_restart_present": True,
            "mpv_restart_zero": True,
            "panfrost_faults_delta_present": True,
            "panfrost_faults_delta_zero": True,
            "ext4_errors_zero": True,
            "mmc_timeout_reset_zero": True,
            "candidate_startup_surface_local_evidence": True,
            "candidate_teardown_process_stopped_cleanly": True,
            "candidate_teardown_gpu_fault_delta_zero": True,
        }
        (candidate_dir / "candidate-health-result.json").write_text(json.dumps({
            "candidate_version": identity["version"],
            "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
            "observed_tree_sha256": identity["tree_sha256"],
            "canary_media_used": True,
            "candidate_startup_surface_health_required": True,
            "passed": False,
            "failure_reasons": ["playback_progressed"],
            "expected": {"panfrost_fault_policy": "delta"},
            "checks": true_checks,
            "counters": {
                "media_load_failed": 0,
                "mpv_restart": 0,
                "nrestarts_delta": 0,
            },
            "candidate_teardown": {
                "passed": True,
                "process_stopped_cleanly": True,
                "gpu_faults_delta": 0,
                "stop": {"method": "sigterm", "returncode": 0},
            },
        }, sort_keys=True) + "\n", encoding="utf-8")
        return candidate_dir

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

    def test_setup_contention_retry_allows_optional_absolute_panfrost_reasons_when_delta_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-contention-absolute")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(
                reset.SETUP_CONTENTION_FAILURE_REASONS
                | reset.SETUP_CONTENTION_OPTIONAL_ABSOLUTE_FAULT_REASONS
            ))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_setup_contention_evidence(
                root,
                identity,
                include_optional_absolute_faults=True,
            )

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_setup_contention_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-contention-absolute-retry",
            ])

            self.assertEqual(rc, 0)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["removed_count"], 1)

    def test_setup_contention_retry_rejects_optional_absolute_panfrost_without_clean_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-contention-dirty")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(
                reset.SETUP_CONTENTION_FAILURE_REASONS
                | reset.SETUP_CONTENTION_OPTIONAL_ABSOLUTE_FAULT_REASONS
            ))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_setup_contention_evidence(
                root,
                identity,
                include_optional_absolute_faults=True,
                clean_delta=False,
            )

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_setup_contention_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-contention-dirty-retry",
            ])

            self.assertEqual(rc, 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("setup_contention_panfrost_delta_not_clean_or_missing", result["blockers"])

    def test_setup_contention_retry_rejects_optional_absolute_panfrost_without_storage_presence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-contention-missing-storage")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(
                reset.SETUP_CONTENTION_FAILURE_REASONS
                | reset.SETUP_CONTENTION_OPTIONAL_ABSOLUTE_FAULT_REASONS
            ))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_setup_contention_evidence(
                root,
                identity,
                include_optional_absolute_faults=True,
                include_storage_presence=False,
            )

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_setup_contention_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-contention-missing-storage-retry",
            ])

            self.assertEqual(rc, 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("setup_contention_storage_fault_seen_or_missing", result["blockers"])

    def test_setup_contention_retry_rejects_optional_absolute_panfrost_without_policy_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-contention-missing-policy")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(
                reset.SETUP_CONTENTION_FAILURE_REASONS
                | reset.SETUP_CONTENTION_OPTIONAL_ABSOLUTE_FAULT_REASONS
            ))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_setup_contention_evidence(
                root,
                identity,
                include_optional_absolute_faults=True,
                include_panfrost_policy_check=False,
            )

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_setup_contention_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-contention-missing-policy-retry",
            ])

            self.assertEqual(rc, 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("setup_contention_panfrost_delta_not_clean_or_missing", result["blockers"])

    def test_setup_contention_retry_rejects_without_drm_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-contention-no-drm")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.SETUP_CONTENTION_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_setup_contention_evidence(root, identity, include_drm_marker=False)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_setup_contention_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-contention-no-drm-retry",
            ])

            self.assertEqual(rc, 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("setup_contention_drm_master_marker_missing", result["blockers"])

    def test_prior_panfrost_absolute_retry_removes_matching_quarantine_with_clean_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-prior-panfrost")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.PRIOR_PANFROST_ABSOLUTE_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_prior_panfrost_absolute_evidence(root, identity)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_prior_panfrost_absolute_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-prior-panfrost-retry",
            ])

            self.assertEqual(rc, 0)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["removed_count"], 1)
            self.assertEqual(
                result["prior_panfrost_absolute_retry_evidence"]["panfrost_faults_delta"],
                0,
            )

    def test_prior_panfrost_absolute_retry_rejects_nonzero_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-prior-panfrost-dirty")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.PRIOR_PANFROST_ABSOLUTE_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_prior_panfrost_absolute_evidence(root, identity, panfrost_delta=1)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_prior_panfrost_absolute_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-prior-panfrost-retry",
            ])

            self.assertEqual(rc, 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("prior_panfrost_absolute_functional_checks_missing", result["blockers"])
            self.assertIn("prior_panfrost_absolute_panfrost_delta_nonzero", result["blockers"])

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

    def test_canary_display_contention_retry_requires_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-canary-contention-missing")
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
                "--reset-scope", "lab_canary_display_contention_retry",
                "--reason", "unit-canary-contention-retry",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("canary_display_contention_evidence_missing", result["blockers"])
            self.assertEqual(result["removed_count"], 0)

    def test_canary_display_contention_retry_removes_matching_quarantine_with_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-canary-contention")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.SETUP_CONTENTION_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_canary_display_contention_evidence(root, identity)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_canary_display_contention_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-canary-contention-retry",
            ])

            self.assertEqual(rc, 0)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(entries, [])
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["removed_count"], 1)
            evidence = result["canary_display_contention_retry_evidence"]
            self.assertTrue(evidence["canary_media_used"])
            self.assertEqual(evidence["total_mpv_count"], 2)
            self.assertEqual(evidence["ipc_success"], 30)

    def test_canary_display_contention_retry_rejects_without_second_mpv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-canary-contention-single")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.SETUP_CONTENTION_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_canary_display_contention_evidence(root, identity, total_mpv_count=1)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_canary_display_contention_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-canary-contention-retry",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("canary_display_contention_total_mpv_not_contended", result["blockers"])
            self.assertIn("target_quarantine_reason_not_allowed", result["blockers"])
            self.assertEqual(result["removed_count"], 0)

    def test_canary_display_contention_retry_accepts_c25_surface_failure_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-c25-surface-contention")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.C25_SURFACE_DISPLAY_CONTENTION_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_canary_display_contention_evidence(
                root,
                identity,
                c25_surface_shape=True,
            )

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_canary_display_contention_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-c25-surface-contention-retry",
            ])

            self.assertEqual(rc, 0)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            evidence = result["canary_display_contention_retry_evidence"]
            self.assertEqual(evidence["failure_shape"], "c25_surface_contention")
            self.assertTrue(evidence["drm_master_permission_denied"])

    def test_canary_display_contention_retry_rejects_c25_shape_without_drm_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-c25-surface-no-drm")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.C25_SURFACE_DISPLAY_CONTENTION_FAILURE_REASONS))
            self.seed_state(data_root, out, [{**identity, "reason": reason}])
            health_dir = self.write_canary_display_contention_evidence(
                root,
                identity,
                c25_surface_shape=True,
                include_drm_marker=False,
            )

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_canary_display_contention_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-c25-surface-contention-retry",
            ])

            self.assertEqual(rc, 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("canary_display_contention_drm_marker_missing", result["blockers"])
            self.assertEqual(result["removed_count"], 0)

    def test_canary_display_contention_retry_rejects_generic_quarantine_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-canary-contention-generic")
            data_root = root / "data"
            out = root / "out"
            self.seed_state(data_root, out, [{**identity, "reason": "physical_powerloss_trial"}])
            health_dir = self.write_canary_display_contention_evidence(root, identity)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_canary_display_contention_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-canary-contention-retry",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("target_quarantine_reason_not_allowed", result["blockers"])
            self.assertEqual(result["removed_count"], 0)

    def test_canary_display_contention_retry_rejects_current_linked_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-canary-contention-current")
            data_root = root / "data"
            out = root / "out"
            reason = ",".join(sorted(reset.SETUP_CONTENTION_FAILURE_REASONS))
            self.seed_state(
                data_root,
                out,
                [{**identity, "reason": reason}],
                current_link="releases/runtime-reset-canary-contention-current",
            )
            health_dir = self.write_canary_display_contention_evidence(root, identity)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_canary_display_contention_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-canary-contention-retry",
            ])

            self.assertEqual(rc, 1)
            entries = reset.updatectl._quarantine_entries(reset.updatectl._read_state())
            self.assertEqual(len(entries), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("target_linked_active", result["blockers"])
            self.assertEqual(result["active_links"], ["current"])
            self.assertEqual(result["removed_count"], 0)

    def test_surface_warmup_retry_removes_exact_false_negative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-surface-warmup")
            data_root = root / "data"
            out = root / "out"
            self.seed_state(data_root, out, [{**identity, "reason": "playback_progressed"}])
            health_dir = self.write_surface_warmup_evidence(root, identity)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_c25_surface_warmup_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-c25-surface-warmup-retry",
            ])

            self.assertEqual(rc, 0)
            self.assertEqual(reset.updatectl._quarantine_entries(reset.updatectl._read_state()), [])
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            evidence = result["surface_warmup_retry_evidence"]
            self.assertTrue(result["passed"])
            self.assertTrue(evidence["reevaluated_passed"])
            self.assertEqual(evidence["surface_sample_count"], 2)
            self.assertEqual(evidence["motion_sample_count"], 5)

    def test_surface_warmup_retry_rejects_actual_motion_stall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-surface-motion-stall")
            data_root = root / "data"
            out = root / "out"
            self.seed_state(data_root, out, [{**identity, "reason": "playback_progressed"}])
            health_dir = self.write_surface_warmup_evidence(root, identity, freeze_motion=True)

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "lab_c25_surface_warmup_retry",
                "--failed-candidate-health-dir", str(health_dir),
                "--reason", "unit-c25-surface-warmup-retry",
            ])

            self.assertEqual(rc, 1)
            self.assertEqual(len(reset.updatectl._quarantine_entries(reset.updatectl._read_state())), 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertIn("surface_warmup_reevaluated_not_passing", result["blockers"])
            self.assertIn("surface_warmup_motion_not_progressing", result["blockers"])
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
