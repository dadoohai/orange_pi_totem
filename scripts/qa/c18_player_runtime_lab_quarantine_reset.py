#!/usr/bin/env python3
"""Lab-only quarantine reset for a C18 player-runtime target.

This is a governed bench reset for repeating physical P0 power-loss trials after
an intentionally quarantining rollback checkpoint. It removes only the
quarantine entry matching the validated manifest/payload identity. It does not
thaw the public updater CLI, publish, fetch, apply, rollback, or touch symlinks.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BOARD_DIR = REPO_ROOT / "scripts" / "board"
QA_DIR = REPO_ROOT / "scripts" / "qa"
sys.path.insert(0, str(BOARD_DIR))
sys.path.insert(0, str(QA_DIR))

import c18_player_runtime_release_gate as release_gate
import c18_playback_health_collect as playback_collect
import c18_playback_health_summary as playback_health
import totem_updatectl as updatectl


LAB_ENV = "C18_PLAYER_RUNTIME_LAB_QUARANTINE_RESET"
DEVICE_DATA_ENV = "C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT"
COMPONENT = "player-runtime"
SCHEMA = "dadooh.c18.player_runtime.lab_quarantine_reset.v1"
RESET_SCOPES = {
    "p0_rollback_after_quarantine",
    "p0_rollback_after_state_success",
    "p0_isolation_reset",
    "p0_setup_contention_retry",
    "lab_no_canary_retry",
    "lab_canary_display_contention_retry",
    "lab_harness_ipc_drm_retry",
    "lab_candidate_startup_status_retry",
    "lab_c25_surface_warmup_retry",
    "lab_prior_panfrost_absolute_retry",
    "h2_rollback_arm_timeout_previous_linked",
}
ALLOWED_QUARANTINE_REASONS = {"physical_powerloss_trial"}
ARM_TIMEOUT_PREVIOUS_LINKED_SCOPE = "h2_rollback_arm_timeout_previous_linked"
SETUP_CONTENTION_SCOPE = "p0_setup_contention_retry"
NO_CANARY_SCOPE = "lab_no_canary_retry"
CANARY_DISPLAY_CONTENTION_SCOPE = "lab_canary_display_contention_retry"
HARNESS_IPC_DRM_SCOPE = "lab_harness_ipc_drm_retry"
STARTUP_STATUS_SCOPE = "lab_candidate_startup_status_retry"
SURFACE_WARMUP_SCOPE = "lab_c25_surface_warmup_retry"
PRIOR_PANFROST_ABSOLUTE_SCOPE = "lab_prior_panfrost_absolute_retry"
SETUP_CONTENTION_FAILURE_REASONS = {
    "hwdec_expected_present",
    "vo_configured_present",
    "vo_configured_no_unexpected",
    "estimated_frame_present",
    "playback_progressed",
}
SETUP_CONTENTION_OPTIONAL_ABSOLUTE_FAULT_REASONS = {
    "panfrost_faults_zero",
    "panfrost_faults_clean_for_policy",
}
SETUP_CONTENTION_ALLOWED_FAILURE_REASONS = (
    SETUP_CONTENTION_FAILURE_REASONS | SETUP_CONTENTION_OPTIONAL_ABSOLUTE_FAULT_REASONS
)
C25_SURFACE_DISPLAY_CONTENTION_FAILURE_REASONS = {
    "candidate_startup_surface_local_evidence",
    "candidate_teardown_process_stopped_cleanly",
    "estimated_frame_present",
    "hwdec_expected_present",
    "ipc_stable_after_success",
    "mpv_path_c18_stack",
    "playback_progressed",
    "service_active",
    "single_mpv",
    "status_no_failures",
    "vo_configured_no_unexpected",
    "vo_configured_present",
}
NO_CANARY_FAILURE_REASONS = {
    "candidate_teardown_process_stopped_cleanly",
    "estimated_frame_present",
    "hwdec_expected_present",
    "ipc_success_present",
    "mpv_path_c18_stack",
    "playback_progressed",
    "service_active",
    "single_mpv",
    "vo_configured_present",
}
HARNESS_IPC_DRM_FAILURE_REASONS = {
    "candidate_teardown_process_stopped_cleanly",
    "estimated_frame_present",
    "hwdec_expected_present",
    "ipc_success_present",
    "mpv_path_c18_stack",
    "playback_progressed",
    "service_active",
    "single_mpv",
    "status_no_failures",
    "vo_configured_present",
}
STARTUP_STATUS_FAILURE_REASONS = {"status_no_failures"}
SURFACE_WARMUP_FAILURE_REASONS = {"playback_progressed"}
PRIOR_PANFROST_ABSOLUTE_FAILURE_REASONS = {
    "panfrost_faults_zero",
    "panfrost_faults_clean_for_policy",
}
PRIOR_PANFROST_FUNCTIONAL_CHECKS = {
    "candidate_process_filtered",
    "candidate_teardown_gpu_fault_delta_zero",
    "candidate_teardown_process_stopped_cleanly",
    "estimated_frame_present",
    "hwdec_expected_present",
    "hwdec_no_unexpected",
    "ipc_stable_after_success",
    "ipc_success_present",
    "media_load_failed_zero",
    "mmc_timeout_reset_present",
    "mmc_timeout_reset_zero",
    "mpv_path_c18_stack",
    "mpv_restart_present",
    "mpv_restart_zero",
    "nrestarts_delta_present",
    "nrestarts_stable",
    "panfrost_faults_delta_present",
    "panfrost_faults_delta_zero",
    "playback_progressed",
    "single_mpv",
    "status_mpv_path_aligned",
    "status_no_failures",
    "vo_configured_no_unexpected",
    "vo_configured_present",
}


def path_is_under(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    root_resolved = root.resolve()
    return resolved == root_resolved or root_resolved in resolved.parents


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def configure_updatectl_for_lab(data_root: Path, policy_path: Path) -> None:
    updatectl.DATA_ROOT = data_root
    updatectl.UPDATES_DIR = updatectl.DATA_ROOT / "updates"
    updatectl.POLICY_FILE = policy_path
    updatectl.LOG_DIR = updatectl.DATA_ROOT / "logs"
    updatectl.LOG_FILE = updatectl.LOG_DIR / "totem-update.log"
    updatectl.TOKEN_FILE = updatectl.DATA_ROOT / "secrets" / "github-release-token"
    updatectl.configure_component(COMPONENT)


def write_lab_policy(policy_path: Path, channel: str) -> None:
    if channel != "homologation":
        raise RuntimeError("quarantine reset only accepts homologation player-runtime packages")
    write_json(
        policy_path,
        {
            "schema": "dadooh.totem.update.policy.v1",
            "device_channel": channel,
            "device_track": "c18-hwdecode",
            "allowed_components": ["player-runtime", "totem-core"],
            "allow_prerelease": True,
            "allow_downgrade": False,
        },
    )


def public_cli_freeze(data_root: Path, action: str) -> dict[str, Any]:
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TOTEM_DATA_ROOT": str(data_root),
    }
    cmd = [sys.executable, str(BOARD_DIR / "totem_updatectl.py")]
    if action == "apply":
        missing = Path(tempfile.gettempdir()) / "c18-player-runtime-missing.manifest.json"
        cmd.extend(["apply-local", str(missing), "--component", COMPONENT])
    elif action == "rollback":
        cmd.extend(["rollback", "--component", COMPONENT])
    elif action == "reconcile":
        cmd.extend(["reconcile", "--component", COMPONENT])
    else:
        raise RuntimeError(f"unsupported public freeze action: {action}")
    proc = subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=30,
    )
    return {
        "returncode": proc.returncode,
        "frozen": proc.returncode == 44,
    }


def guarded_paths(args: argparse.Namespace, work_dir: Path, data_root: Path) -> tuple[bool, str]:
    touches_device_data = path_is_under(data_root, Path("/data")) or path_is_under(work_dir, Path("/data"))
    if touches_device_data and (
        not args.allow_device_data_root or os.environ.get(DEVICE_DATA_ENV) != "1"
    ):
        return False, f"device_data_root_guard_required: pass --allow-device-data-root and set {DEVICE_DATA_ENV}=1"
    return True, "ok"


def runtime_snapshot() -> dict[str, Any]:
    state: dict[str, Any] = {}
    try:
        state = updatectl._read_state()
    except Exception:
        state = {}
    quarantine = updatectl._quarantine_entries(state)
    return {
        "current_link": updatectl._read_symlink_target(updatectl.CURRENT_LINK),
        "previous_link": updatectl._read_symlink_target(updatectl.PREVIOUS_LINK),
        "current_exists": updatectl.CURRENT_LINK.exists() or updatectl.CURRENT_LINK.is_symlink(),
        "previous_exists": updatectl.PREVIOUS_LINK.exists() or updatectl.PREVIOUS_LINK.is_symlink(),
        "state_current_version": (state.get("current") or {}).get("version") if isinstance(state.get("current"), dict) else None,
        "state_previous_version": (state.get("previous") or {}).get("version") if isinstance(state.get("previous"), dict) else None,
        "last_operation": state.get("last_operation") if isinstance(state.get("last_operation"), dict) else None,
        "quarantine_count": len(quarantine),
        "quarantine_versions": sorted(str(entry.get("version") or "") for entry in quarantine),
    }


def payload_identity(manifest: dict[str, Any], payload: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c18-quarantine-reset-identity-") as tmp:
        release_dir = Path(tmp) / "release"
        release_dir.mkdir()
        updatectl._safe_extract_tar(payload, release_dir)
        return updatectl._player_runtime_identity(release_dir, manifest)


def identity_matches_target(entry: dict[str, Any], identity: dict[str, Any]) -> bool:
    if entry.get("version") != identity.get("version"):
        return False
    payload_match = bool(entry.get("payload_sha256")) and entry.get("payload_sha256") == identity.get("payload_sha256")
    tree_match = bool(entry.get("tree_sha256")) and entry.get("tree_sha256") == identity.get("tree_sha256")
    return payload_match or tree_match


def setup_contention_evidence(candidate_health_dir: Path | None, identity: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
    blockers: list[str] = []
    details: dict[str, Any] = {"candidate_health_dir": str(candidate_health_dir) if candidate_health_dir else None}
    if candidate_health_dir is None:
        return False, ["setup_contention_evidence_missing"], details
    result_path = candidate_health_dir / "candidate-health-result.json"
    process_path = candidate_health_dir / "health" / "deep-health-process.json"
    mpv_log_path = candidate_health_dir / "mpv.log"
    try:
        result = read_json(result_path)
    except Exception as exc:
        return False, [f"setup_contention_result_read_failed:{type(exc).__name__}"], details
    try:
        process = read_json(process_path)
    except Exception as exc:
        return False, [f"setup_contention_process_read_failed:{type(exc).__name__}"], details
    try:
        mpv_log = mpv_log_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return False, [f"setup_contention_mpv_log_read_failed:{type(exc).__name__}"], details

    failures = set(str(item) for item in (result.get("failure_reasons") or []))
    counters = result.get("counters") if isinstance(result.get("counters"), dict) else {}
    checks = result.get("checks") if isinstance(result.get("checks"), dict) else {}
    optional_absolute_faults = failures & SETUP_CONTENTION_OPTIONAL_ABSOLUTE_FAULT_REASONS
    details.update({
        "candidate_version": result.get("candidate_version"),
        "failure_reasons": sorted(failures),
        "optional_absolute_fault_reasons": sorted(optional_absolute_faults),
        "total_mpv_count": counters.get("total_mpv_count"),
        "process_total_mpv_count": process.get("total_mpv_count"),
        "service_active": checks.get("service_active"),
        "panfrost_faults_delta_present": checks.get("panfrost_faults_delta_present"),
        "panfrost_faults_delta_zero": checks.get("panfrost_faults_delta_zero"),
        "panfrost_faults_clean_for_policy": checks.get("panfrost_faults_clean_for_policy"),
        "panfrost_faults_clean_for_policy_present": "panfrost_faults_clean_for_policy" in checks,
        "ext4_errors_present": checks.get("ext4_errors_present"),
        "ext4_errors_zero": checks.get("ext4_errors_zero"),
        "mmc_timeout_reset_present": checks.get("mmc_timeout_reset_present"),
        "mmc_timeout_reset_zero": checks.get("mmc_timeout_reset_zero"),
    })
    if result.get("candidate_version") != identity.get("version"):
        blockers.append("setup_contention_candidate_version_mismatch")
    if result.get("passed") is not False:
        blockers.append("setup_contention_result_not_failed")
    if not SETUP_CONTENTION_FAILURE_REASONS.issubset(failures) or not failures <= SETUP_CONTENTION_ALLOWED_FAILURE_REASONS:
        blockers.append("setup_contention_failure_reasons_mismatch")
    if optional_absolute_faults:
        if (
            checks.get("panfrost_faults_delta_present") is not True
            or checks.get("panfrost_faults_delta_zero") is not True
            or "panfrost_faults_clean_for_policy" not in checks
        ):
            blockers.append("setup_contention_panfrost_delta_not_clean_or_missing")
        if (
            checks.get("ext4_errors_present") is not True
            or checks.get("ext4_errors_zero") is not True
            or checks.get("mmc_timeout_reset_present") is not True
            or checks.get("mmc_timeout_reset_zero") is not True
        ):
            blockers.append("setup_contention_storage_fault_seen_or_missing")
    if int(counters.get("total_mpv_count") or 0) < 2 or int(process.get("total_mpv_count") or 0) < 2:
        blockers.append("setup_contention_total_mpv_count")
    if checks.get("service_active") is not True:
        blockers.append("setup_contention_service_not_active")
    if "Failed to acquire DRM master: Permission denied" not in mpv_log:
        blockers.append("setup_contention_drm_master_marker_missing")
    if "Error opening/initializing the selected video_out" not in mpv_log:
        blockers.append("setup_contention_video_out_marker_missing")
    return not blockers, blockers, details


def setup_contention_reason_allowed(reason: str) -> bool:
    reasons = set(reason.split(","))
    return (
        SETUP_CONTENTION_FAILURE_REASONS.issubset(reasons)
        and reasons <= SETUP_CONTENTION_ALLOWED_FAILURE_REASONS
    )


def prior_panfrost_absolute_retry_evidence(
    candidate_health_dir: Path | None,
    identity: dict[str, Any],
) -> tuple[bool, list[str], dict[str, Any]]:
    blockers: list[str] = []
    details: dict[str, Any] = {"candidate_health_dir": str(candidate_health_dir) if candidate_health_dir else None}
    if candidate_health_dir is None:
        return False, ["prior_panfrost_absolute_evidence_missing"], details
    result_path = candidate_health_dir / "candidate-health-result.json"
    try:
        result = read_json(result_path)
    except Exception as exc:
        return False, [f"prior_panfrost_absolute_result_read_failed:{type(exc).__name__}"], details

    failures = set(str(item) for item in (result.get("failure_reasons") or []))
    checks = result.get("checks") if isinstance(result.get("checks"), dict) else {}
    counters = result.get("counters") if isinstance(result.get("counters"), dict) else {}
    teardown = result.get("candidate_teardown") if isinstance(result.get("candidate_teardown"), dict) else {}
    missing_functional = sorted(
        check for check in PRIOR_PANFROST_FUNCTIONAL_CHECKS if checks.get(check) is not True
    )
    details.update({
        "candidate_version": result.get("candidate_version"),
        "failure_reasons": sorted(failures),
        "panfrost_fault_policy": counters.get("panfrost_fault_policy"),
        "panfrost_faults": counters.get("panfrost_faults"),
        "panfrost_faults_start": counters.get("panfrost_faults_start"),
        "panfrost_faults_delta": counters.get("panfrost_faults_delta"),
        "ext4_errors_delta": counters.get("ext4_errors_delta"),
        "mmc_timeout_reset_delta": counters.get("mmc_timeout_reset_delta"),
        "mpv_count": counters.get("mpv_count"),
        "total_mpv_count": counters.get("total_mpv_count"),
        "ipc_success": counters.get("ipc_success"),
        "hwdec_expected_samples": counters.get("hwdec_expected_samples"),
        "vo_configured_true_samples": counters.get("vo_configured_true_samples"),
        "media_load_failed": counters.get("media_load_failed"),
        "mpv_restart": counters.get("mpv_restart"),
        "nrestarts_delta": counters.get("nrestarts_delta"),
        "teardown_passed": teardown.get("passed"),
        "teardown_gpu_faults_delta": teardown.get("gpu_faults_delta"),
        "missing_functional_checks": missing_functional,
    })
    if result.get("candidate_version") != identity.get("version"):
        blockers.append("prior_panfrost_absolute_candidate_version_mismatch")
    if result.get("observed_kiosk_py_sha256") != identity.get("kiosk_py_sha256"):
        blockers.append("prior_panfrost_absolute_kiosk_identity_mismatch")
    if result.get("observed_tree_sha256") != identity.get("tree_sha256"):
        blockers.append("prior_panfrost_absolute_tree_identity_mismatch")
    if result.get("passed") is not False:
        blockers.append("prior_panfrost_absolute_result_not_failed")
    if failures != PRIOR_PANFROST_ABSOLUTE_FAILURE_REASONS:
        blockers.append("prior_panfrost_absolute_failure_reasons_mismatch")
    if counters.get("panfrost_fault_policy") != "absolute":
        blockers.append("prior_panfrost_absolute_policy_not_absolute")
    if missing_functional:
        blockers.append("prior_panfrost_absolute_functional_checks_missing")
    if int(counters.get("panfrost_faults_delta") or 0) != 0:
        blockers.append("prior_panfrost_absolute_panfrost_delta_nonzero")
    if int(counters.get("ext4_errors_delta") or 0) != 0 or int(counters.get("mmc_timeout_reset_delta") or 0) != 0:
        blockers.append("prior_panfrost_absolute_storage_delta_nonzero")
    if int(counters.get("mpv_count") or 0) != 1 or int(counters.get("total_mpv_count") or 0) != 1:
        blockers.append("prior_panfrost_absolute_not_single_mpv")
    if int(counters.get("ipc_success") or 0) <= 0:
        blockers.append("prior_panfrost_absolute_no_ipc_success")
    if int(counters.get("hwdec_expected_samples") or 0) <= 0:
        blockers.append("prior_panfrost_absolute_no_hwdec_samples")
    if int(counters.get("vo_configured_true_samples") or 0) <= 0:
        blockers.append("prior_panfrost_absolute_no_vo_samples")
    if int(counters.get("media_load_failed") or 0) != 0 or int(counters.get("mpv_restart") or 0) != 0:
        blockers.append("prior_panfrost_absolute_runtime_fault_seen")
    if int(counters.get("nrestarts_delta") or 0) != 0:
        blockers.append("prior_panfrost_absolute_service_restart_seen")
    if teardown.get("passed") is not True or int(teardown.get("gpu_faults_delta") or 0) != 0:
        blockers.append("prior_panfrost_absolute_teardown_not_clean")
    return not blockers, blockers, details


def no_canary_retry_evidence(candidate_health_dir: Path | None, identity: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
    blockers: list[str] = []
    details: dict[str, Any] = {"candidate_health_dir": str(candidate_health_dir) if candidate_health_dir else None}
    if candidate_health_dir is None:
        return False, ["no_canary_retry_evidence_missing"], details
    result_path = candidate_health_dir / "candidate-health-result.json"
    try:
        result = read_json(result_path)
    except Exception as exc:
        return False, [f"no_canary_retry_result_read_failed:{type(exc).__name__}"], details

    failures = set(str(item) for item in (result.get("failure_reasons") or []))
    counters = result.get("counters") if isinstance(result.get("counters"), dict) else {}
    checks = result.get("checks") if isinstance(result.get("checks"), dict) else {}
    teardown = result.get("candidate_teardown") if isinstance(result.get("candidate_teardown"), dict) else {}
    stop = teardown.get("stop") if isinstance(teardown.get("stop"), dict) else {}
    details.update({
        "candidate_version": result.get("candidate_version"),
        "failure_reasons": sorted(failures),
        "canary_media_used": result.get("canary_media_used"),
        "playlist_size_max": counters.get("playlist_size_max"),
        "mpv_count": counters.get("mpv_count"),
        "ipc_success": counters.get("ipc_success"),
        "gpu_faults_delta": teardown.get("gpu_faults_delta"),
        "stop_returncode": stop.get("returncode"),
    })
    if result.get("candidate_version") != identity.get("version"):
        blockers.append("no_canary_retry_candidate_version_mismatch")
    if result.get("observed_kiosk_py_sha256") != identity.get("kiosk_py_sha256"):
        blockers.append("no_canary_retry_kiosk_identity_mismatch")
    if result.get("observed_tree_sha256") != identity.get("tree_sha256"):
        blockers.append("no_canary_retry_tree_identity_mismatch")
    if result.get("passed") is not False:
        blockers.append("no_canary_retry_result_not_failed")
    if result.get("canary_media_used") is not False:
        blockers.append("no_canary_retry_canary_was_used")
    if failures != NO_CANARY_FAILURE_REASONS:
        blockers.append("no_canary_retry_failure_reasons_mismatch")
    if int(counters.get("playlist_size_max") or 0) != 0:
        blockers.append("no_canary_retry_playlist_not_empty")
    if int(counters.get("mpv_count") or 0) != 0:
        blockers.append("no_canary_retry_mpv_process_started")
    if int(counters.get("ipc_success") or 0) != 0:
        blockers.append("no_canary_retry_ipc_success_seen")
    if int(counters.get("hwdec_expected_samples") or 0) != 0:
        blockers.append("no_canary_retry_hwdec_seen")
    if int(counters.get("vo_configured_true_samples") or 0) != 0:
        blockers.append("no_canary_retry_vo_seen")
    if checks.get("media_load_failed_zero") is not True:
        blockers.append("no_canary_retry_media_load_failures_seen")
    if checks.get("panfrost_faults_delta_zero") is not True:
        blockers.append("no_canary_retry_gpu_fault_delta_seen")
    if checks.get("ext4_errors_zero") is not True or checks.get("mmc_timeout_reset_zero") is not True:
        blockers.append("no_canary_retry_storage_fault_seen")
    if teardown.get("gpu_faults_delta") not in (0, None):
        blockers.append("no_canary_retry_teardown_gpu_fault_delta")
    if stop.get("method") != "none" or stop.get("returncode") != 2:
        blockers.append("no_canary_retry_candidate_exit_shape")
    return not blockers, blockers, details


def canary_display_contention_retry_evidence(
    candidate_health_dir: Path | None,
    identity: dict[str, Any],
) -> tuple[bool, list[str], dict[str, Any]]:
    blockers: list[str] = []
    details: dict[str, Any] = {"candidate_health_dir": str(candidate_health_dir) if candidate_health_dir else None}
    if candidate_health_dir is None:
        return False, ["canary_display_contention_evidence_missing"], details
    result_path = candidate_health_dir / "candidate-health-result.json"
    process_path = candidate_health_dir / "health" / "deep-health-process.json"
    try:
        result = read_json(result_path)
    except Exception as exc:
        return False, [f"canary_display_contention_result_read_failed:{type(exc).__name__}"], details
    try:
        process = read_json(process_path)
    except Exception as exc:
        return False, [f"canary_display_contention_process_read_failed:{type(exc).__name__}"], details
    try:
        combined_logs = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in sorted(candidate_health_dir.glob("mpv*.log"))
        )
    except Exception as exc:
        return False, [f"canary_display_contention_log_read_failed:{type(exc).__name__}"], details

    failures = set(str(item) for item in (result.get("failure_reasons") or []))
    counters = result.get("counters") if isinstance(result.get("counters"), dict) else {}
    checks = result.get("checks") if isinstance(result.get("checks"), dict) else {}
    teardown = result.get("candidate_teardown") if isinstance(result.get("candidate_teardown"), dict) else {}
    stop = teardown.get("stop") if isinstance(teardown.get("stop"), dict) else {}
    legacy_shape = failures == SETUP_CONTENTION_FAILURE_REASONS
    c25_surface_shape = failures == C25_SURFACE_DISPLAY_CONTENTION_FAILURE_REASONS
    details.update({
        "candidate_version": result.get("candidate_version"),
        "failure_reasons": sorted(failures),
        "canary_media_used": result.get("canary_media_used"),
        "playlist_size_max": counters.get("playlist_size_max"),
        "mpv_count": counters.get("mpv_count"),
        "total_mpv_count": counters.get("total_mpv_count"),
        "process_total_mpv_count": process.get("total_mpv_count"),
        "ipc_success": counters.get("ipc_success"),
        "status_failure_samples": counters.get("status_failure_samples"),
        "gpu_faults_delta": teardown.get("gpu_faults_delta"),
        "service_active": checks.get("service_active"),
        "failure_shape": (
            "legacy_canary_contention"
            if legacy_shape
            else "c25_surface_contention" if c25_surface_shape else "unexpected"
        ),
        "drm_master_permission_denied": "Failed to acquire DRM master: Permission denied" in combined_logs,
        "video_out_permission_denied": "Error opening/initializing the selected video_out" in combined_logs,
        "stop_method": stop.get("method"),
        "stop_returncode": stop.get("returncode"),
    })
    if result.get("candidate_version") != identity.get("version"):
        blockers.append("canary_display_contention_candidate_version_mismatch")
    if result.get("observed_kiosk_py_sha256") != identity.get("kiosk_py_sha256"):
        blockers.append("canary_display_contention_kiosk_identity_mismatch")
    if result.get("observed_tree_sha256") != identity.get("tree_sha256"):
        blockers.append("canary_display_contention_tree_identity_mismatch")
    if result.get("passed") is not False:
        blockers.append("canary_display_contention_result_not_failed")
    if result.get("canary_media_used") is not True:
        blockers.append("canary_display_contention_canary_missing")
    if not legacy_shape and not c25_surface_shape:
        blockers.append("canary_display_contention_failure_reasons_mismatch")
    if int(counters.get("playlist_size_max") or 0) < 1:
        blockers.append("canary_display_contention_playlist_missing")
    if legacy_shape:
        if int(counters.get("mpv_count") or 0) != 1:
            blockers.append("canary_display_contention_candidate_mpv_missing")
        if int(counters.get("total_mpv_count") or 0) < 2 or int(process.get("total_mpv_count") or 0) < 2:
            blockers.append("canary_display_contention_total_mpv_not_contended")
        if checks.get("service_active") is not True:
            blockers.append("canary_display_contention_service_not_active")
    elif c25_surface_shape:
        if result.get("candidate_startup_surface_health_required") is not True:
            blockers.append("canary_display_contention_c25_surface_not_required")
        if int(counters.get("hwdec_expected_samples") or 0) != 0:
            blockers.append("canary_display_contention_c25_hwdec_seen")
        if int(counters.get("vo_configured_true_samples") or 0) != 0:
            blockers.append("canary_display_contention_c25_vo_seen")
        if "Failed to acquire DRM master: Permission denied" not in combined_logs:
            blockers.append("canary_display_contention_drm_marker_missing")
        if "Error opening/initializing the selected video_out" not in combined_logs:
            blockers.append("canary_display_contention_video_out_marker_missing")
        if stop.get("method") != "none" or stop.get("returncode") != 3:
            blockers.append("canary_display_contention_c25_exit_shape")
    if int(counters.get("ipc_success") or 0) <= 0:
        blockers.append("canary_display_contention_no_ipc_success")
    if int(counters.get("media_load_failed") or 0) != 0 or checks.get("media_load_failed_zero") is not True:
        blockers.append("canary_display_contention_media_load_failed")
    if checks.get("panfrost_faults_delta_zero") is not True:
        blockers.append("canary_display_contention_gpu_fault_delta_seen")
    if checks.get("ext4_errors_zero") is not True or checks.get("mmc_timeout_reset_zero") is not True:
        blockers.append("canary_display_contention_storage_fault_seen")
    if teardown.get("gpu_faults_delta") not in (0, None):
        blockers.append("canary_display_contention_teardown_gpu_fault_delta")
    return not blockers, blockers, details


def harness_ipc_drm_retry_evidence(candidate_health_dir: Path | None, identity: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
    blockers: list[str] = []
    details: dict[str, Any] = {"candidate_health_dir": str(candidate_health_dir) if candidate_health_dir else None}
    if candidate_health_dir is None:
        return False, ["harness_ipc_drm_retry_evidence_missing"], details
    result_path = candidate_health_dir / "candidate-health-result.json"
    try:
        result = read_json(result_path)
    except Exception as exc:
        return False, [f"harness_ipc_drm_retry_result_read_failed:{type(exc).__name__}"], details
    try:
        combined_logs = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in sorted(candidate_health_dir.glob("mpv*.log"))
        )
        combined_logs += "\n" + (candidate_health_dir / "kiosk.log").read_text(
            encoding="utf-8", errors="replace"
        )
    except Exception as exc:
        return False, [f"harness_ipc_drm_retry_log_read_failed:{type(exc).__name__}"], details

    failures = set(str(item) for item in (result.get("failure_reasons") or []))
    counters = result.get("counters") if isinstance(result.get("counters"), dict) else {}
    checks = result.get("checks") if isinstance(result.get("checks"), dict) else {}
    teardown = result.get("candidate_teardown") if isinstance(result.get("candidate_teardown"), dict) else {}
    stop = teardown.get("stop") if isinstance(teardown.get("stop"), dict) else {}
    details.update({
        "candidate_version": result.get("candidate_version"),
        "failure_reasons": sorted(failures),
        "canary_media_used": result.get("canary_media_used"),
        "playlist_size_max": counters.get("playlist_size_max"),
        "mpv_count": counters.get("mpv_count"),
        "total_mpv_count": counters.get("total_mpv_count"),
        "ipc_success": counters.get("ipc_success"),
        "status_failure_samples": counters.get("status_failure_samples"),
        "gpu_faults_delta": teardown.get("gpu_faults_delta"),
        "stop_returncode": stop.get("returncode"),
        "af_unix_path_too_long": "AF_UNIX path too long" in combined_logs,
        "drm_master_permission_denied": "Failed to acquire DRM master: Permission denied" in combined_logs,
    })
    if result.get("candidate_version") != identity.get("version"):
        blockers.append("harness_ipc_drm_retry_candidate_version_mismatch")
    if result.get("observed_kiosk_py_sha256") != identity.get("kiosk_py_sha256"):
        blockers.append("harness_ipc_drm_retry_kiosk_identity_mismatch")
    if result.get("observed_tree_sha256") != identity.get("tree_sha256"):
        blockers.append("harness_ipc_drm_retry_tree_identity_mismatch")
    if result.get("passed") is not False:
        blockers.append("harness_ipc_drm_retry_result_not_failed")
    if result.get("canary_media_used") is not True:
        blockers.append("harness_ipc_drm_retry_canary_missing")
    if failures != HARNESS_IPC_DRM_FAILURE_REASONS:
        blockers.append("harness_ipc_drm_retry_failure_reasons_mismatch")
    if int(counters.get("playlist_size_max") or 0) < 1:
        blockers.append("harness_ipc_drm_retry_playlist_missing")
    if int(counters.get("ipc_success") or 0) != 0:
        blockers.append("harness_ipc_drm_retry_ipc_success_seen")
    if int(counters.get("hwdec_expected_samples") or 0) != 0:
        blockers.append("harness_ipc_drm_retry_hwdec_seen")
    if checks.get("media_load_failed_zero") is not True:
        blockers.append("harness_ipc_drm_retry_media_load_failures_seen")
    if checks.get("panfrost_faults_delta_zero") is not True:
        blockers.append("harness_ipc_drm_retry_gpu_fault_delta_seen")
    if checks.get("ext4_errors_zero") is not True or checks.get("mmc_timeout_reset_zero") is not True:
        blockers.append("harness_ipc_drm_retry_storage_fault_seen")
    if "AF_UNIX path too long" not in combined_logs:
        blockers.append("harness_ipc_drm_retry_af_unix_marker_missing")
    if "Failed to acquire DRM master: Permission denied" not in combined_logs:
        blockers.append("harness_ipc_drm_retry_drm_marker_missing")
    if "Error opening/initializing the VO window" not in combined_logs:
        blockers.append("harness_ipc_drm_retry_vo_marker_missing")
    if teardown.get("gpu_faults_delta") not in (0, None):
        blockers.append("harness_ipc_drm_retry_teardown_gpu_fault_delta")
    if stop.get("method") != "none" or stop.get("returncode") != 3:
        blockers.append("harness_ipc_drm_retry_candidate_exit_shape")
    return not blockers, blockers, details


def startup_status_retry_evidence(candidate_health_dir: Path | None, identity: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
    blockers: list[str] = []
    details: dict[str, Any] = {"candidate_health_dir": str(candidate_health_dir) if candidate_health_dir else None}
    if candidate_health_dir is None:
        return False, ["startup_status_retry_evidence_missing"], details
    result_path = candidate_health_dir / "candidate-health-result.json"
    status_samples_path = candidate_health_dir / "health" / "status-samples.ndjson"
    try:
        result = read_json(result_path)
    except Exception as exc:
        return False, [f"startup_status_retry_result_read_failed:{type(exc).__name__}"], details
    try:
        status_lines = [
            json.loads(line)
            for line in status_samples_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except Exception as exc:
        return False, [f"startup_status_retry_status_read_failed:{type(exc).__name__}"], details
    try:
        reevaluated = playback_health.evaluate(
            samples_path=candidate_health_dir / "health" / "playback-samples.tsv",
            systemd_path=candidate_health_dir / "health" / "deep-health-systemd.json",
            process_path=candidate_health_dir / "health" / "deep-health-process.json",
            kernel_path=candidate_health_dir / "health" / "deep-health-kernel.json",
            player_counters_path=candidate_health_dir / "health" / "deep-health-player-counters.json",
        )
    except Exception as exc:
        return False, [f"startup_status_retry_reevaluate_failed:{type(exc).__name__}"], details

    failures = set(str(item) for item in (result.get("failure_reasons") or []))
    counters = result.get("counters") if isinstance(result.get("counters"), dict) else {}
    checks = result.get("checks") if isinstance(result.get("checks"), dict) else {}
    false_checks = sorted(key for key, value in checks.items() if value is False)
    first_status = (
        status_lines[0].get("status")
        if status_lines and isinstance(status_lines[0], dict) and isinstance(status_lines[0].get("status"), dict)
        else {}
    )
    remaining_statuses = [
        item.get("status")
        for item in status_lines[1:]
        if isinstance(item, dict) and isinstance(item.get("status"), dict)
    ]
    details.update({
        "candidate_version": result.get("candidate_version"),
        "failure_reasons": sorted(failures),
        "false_checks": false_checks,
        "status_failure_samples": counters.get("status_failure_samples"),
        "first_playback_state": first_status.get("playback_state"),
        "first_black_screen_risk_reason": first_status.get("black_screen_risk_reason"),
        "reevaluated_passed": reevaluated.get("passed"),
        "reevaluated_failure_reasons": reevaluated.get("failure_reasons"),
        "total_mpv_count": counters.get("total_mpv_count"),
        "mpv_count": counters.get("mpv_count"),
    })
    if result.get("candidate_version") != identity.get("version"):
        blockers.append("startup_status_retry_candidate_version_mismatch")
    if result.get("observed_kiosk_py_sha256") != identity.get("kiosk_py_sha256"):
        blockers.append("startup_status_retry_kiosk_identity_mismatch")
    if result.get("observed_tree_sha256") != identity.get("tree_sha256"):
        blockers.append("startup_status_retry_tree_identity_mismatch")
    if result.get("passed") is not False:
        blockers.append("startup_status_retry_result_not_failed")
    if failures != STARTUP_STATUS_FAILURE_REASONS:
        blockers.append("startup_status_retry_failure_reasons_mismatch")
    if false_checks != ["status_no_failures"]:
        blockers.append("startup_status_retry_false_checks_mismatch")
    if int(counters.get("status_failure_samples") or 0) != 1:
        blockers.append("startup_status_retry_status_failure_count")
    if first_status.get("playback_state") != "player_starting":
        blockers.append("startup_status_retry_first_state_not_starting")
    if first_status.get("black_screen_risk_reason") in (None, "", "null", False):
        blockers.append("startup_status_retry_first_black_screen_marker_missing")
    if int(first_status.get("consecutive_failures") or 0) != 0:
        blockers.append("startup_status_retry_first_consecutive_failures")
    if int(first_status.get("blocked_media_count") or 0) != 0:
        blockers.append("startup_status_retry_first_blocked_media")
    for status in remaining_statuses:
        if status.get("black_screen_risk_reason") not in (None, "", "null", False):
            blockers.append("startup_status_retry_later_black_screen_marker")
            break
    if int(counters.get("total_mpv_count") or 0) != 1 or int(counters.get("mpv_count") or 0) != 1:
        blockers.append("startup_status_retry_not_single_mpv")
    if int(counters.get("media_load_failed") or 0) != 0:
        blockers.append("startup_status_retry_media_load_failed")
    if int(counters.get("mpv_restart") or 0) != 0:
        blockers.append("startup_status_retry_mpv_restart")
    if reevaluated.get("passed") is not True:
        blockers.append("startup_status_retry_reevaluated_not_passing")
    return not blockers, blockers, details


def surface_warmup_retry_evidence(
    candidate_health_dir: Path | None,
    identity: dict[str, Any],
) -> tuple[bool, list[str], dict[str, Any]]:
    blockers: list[str] = []
    details: dict[str, Any] = {"candidate_health_dir": str(candidate_health_dir) if candidate_health_dir else None}
    if candidate_health_dir is None:
        return False, ["surface_warmup_evidence_missing"], details

    result_path = candidate_health_dir / "candidate-health-result.json"
    samples_path = candidate_health_dir / "health" / "playback-samples.tsv"
    try:
        result = read_json(result_path)
        with samples_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            rows = list(reader)
            fieldnames = list(reader.fieldnames or [])
    except Exception as exc:
        return False, [f"surface_warmup_evidence_read_failed:{type(exc).__name__}"], details

    surface_files = sorted(
        (candidate_health_dir / "runtime").glob("startup-feedback-c25-visible-state-*.mp4")
    )
    surface_aliases = {playback_collect.safe_path_alias(str(path)) for path in surface_files}
    surface_rows = [row for row in rows if row.get("path_alias") in surface_aliases]
    motion_rows = [
        row
        for row in rows
        if row.get("ipc_result") == "success" and row.get("path_alias") not in surface_aliases
    ]
    for row in rows:
        row["current_path_kind"] = (
            "public_surface"
            if row.get("path_alias") in surface_aliases
            else "motion_media" if row.get("ipc_result") == "success" else ""
        )
    if "current_path_kind" not in fieldnames:
        fieldnames.append("current_path_kind")

    expected = result.get("expected") if isinstance(result.get("expected"), dict) else {}
    panfrost_policy = str(expected.get("panfrost_fault_policy") or "")
    try:
        with tempfile.TemporaryDirectory(prefix="c18-surface-warmup-reevaluate-") as tmp:
            corrected_samples = Path(tmp) / "playback-samples.tsv"
            with corrected_samples.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, delimiter="\t", fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            reevaluated = playback_health.evaluate(
                samples_path=corrected_samples,
                systemd_path=candidate_health_dir / "health" / "deep-health-systemd.json",
                process_path=candidate_health_dir / "health" / "deep-health-process.json",
                kernel_path=candidate_health_dir / "health" / "deep-health-kernel.json",
                player_counters_path=candidate_health_dir / "health" / "deep-health-player-counters.json",
                watchdog_path=(
                    candidate_health_dir / "health" / "deep-health-watchdog.json"
                    if (candidate_health_dir / "health" / "deep-health-watchdog.json").exists()
                    else None
                ),
                panfrost_fault_policy=panfrost_policy,
            )
    except Exception as exc:
        return False, [f"surface_warmup_reevaluate_failed:{type(exc).__name__}"], details

    failures = set(str(item) for item in (result.get("failure_reasons") or []))
    checks = result.get("checks") if isinstance(result.get("checks"), dict) else {}
    counters = result.get("counters") if isinstance(result.get("counters"), dict) else {}
    false_checks = sorted(key for key, value in checks.items() if value is False)
    teardown = result.get("candidate_teardown") if isinstance(result.get("candidate_teardown"), dict) else {}
    stop = teardown.get("stop") if isinstance(teardown.get("stop"), dict) else {}
    surface_shape_ok = bool(surface_rows) and all(
        row.get("ipc_result") == "success"
        and playback_health.as_float(row.get("estimated_frame_number")) is not None
        and 0 < (playback_health.as_float(row.get("duration")) or 0) <= 0.1
        for row in surface_rows
    )
    reevaluated_counters = (
        reevaluated.get("counters") if isinstance(reevaluated.get("counters"), dict) else {}
    )
    details.update({
        "candidate_version": result.get("candidate_version"),
        "failure_reasons": sorted(failures),
        "false_checks": false_checks,
        "surface_file_count": len(surface_files),
        "surface_sample_count": len(surface_rows),
        "motion_sample_count": len(motion_rows),
        "surface_shape_ok": surface_shape_ok,
        "panfrost_fault_policy": panfrost_policy,
        "reevaluated_passed": reevaluated.get("passed"),
        "reevaluated_failure_reasons": reevaluated.get("failure_reasons"),
        "reevaluated_motion_samples": reevaluated_counters.get("motion_media_samples"),
        "reevaluated_surface_samples": reevaluated_counters.get("public_surface_samples"),
        "reevaluated_frame_progressed": reevaluated_counters.get("estimated_frame_progressed"),
        "gpu_faults_delta": teardown.get("gpu_faults_delta"),
        "stop_method": stop.get("method"),
        "stop_returncode": stop.get("returncode"),
    })
    if result.get("candidate_version") != identity.get("version"):
        blockers.append("surface_warmup_candidate_version_mismatch")
    if result.get("observed_kiosk_py_sha256") != identity.get("kiosk_py_sha256"):
        blockers.append("surface_warmup_kiosk_identity_mismatch")
    if result.get("observed_tree_sha256") != identity.get("tree_sha256"):
        blockers.append("surface_warmup_tree_identity_mismatch")
    if result.get("passed") is not False:
        blockers.append("surface_warmup_result_not_failed")
    if failures != SURFACE_WARMUP_FAILURE_REASONS or false_checks != ["playback_progressed"]:
        blockers.append("surface_warmup_failure_shape_mismatch")
    if result.get("canary_media_used") is not True:
        blockers.append("surface_warmup_canary_missing")
    if result.get("candidate_startup_surface_health_required") is not True:
        blockers.append("surface_warmup_surface_not_required")
    if checks.get("candidate_startup_surface_local_evidence") is not True:
        blockers.append("surface_warmup_local_surface_evidence_missing")
    if not surface_files or not surface_shape_ok:
        blockers.append("surface_warmup_surface_samples_not_exact")
    if len(motion_rows) < 3:
        blockers.append("surface_warmup_motion_samples_insufficient")
    if panfrost_policy != "delta":
        blockers.append("surface_warmup_panfrost_policy_not_delta")
    if int(counters.get("media_load_failed") or 0) != 0 or int(counters.get("mpv_restart") or 0) != 0:
        blockers.append("surface_warmup_player_failures_seen")
    if int(counters.get("nrestarts_delta") or 0) != 0:
        blockers.append("surface_warmup_service_restart_seen")
    if checks.get("panfrost_faults_delta_zero") is not True:
        blockers.append("surface_warmup_gpu_fault_delta_seen")
    if checks.get("ext4_errors_zero") is not True or checks.get("mmc_timeout_reset_zero") is not True:
        blockers.append("surface_warmup_storage_fault_seen")
    if teardown.get("passed") is not True or teardown.get("process_stopped_cleanly") is not True:
        blockers.append("surface_warmup_teardown_not_clean")
    if teardown.get("gpu_faults_delta") != 0:
        blockers.append("surface_warmup_teardown_gpu_fault_delta")
    if stop.get("method") != "sigterm" or stop.get("returncode") != 0:
        blockers.append("surface_warmup_candidate_exit_shape")
    if reevaluated.get("passed") is not True:
        blockers.append("surface_warmup_reevaluated_not_passing")
    if int(reevaluated_counters.get("public_surface_samples") or 0) != len(surface_rows):
        blockers.append("surface_warmup_surface_classification_mismatch")
    if int(reevaluated_counters.get("motion_media_samples") or 0) != len(motion_rows):
        blockers.append("surface_warmup_motion_classification_mismatch")
    if reevaluated_counters.get("estimated_frame_progressed") is not True:
        blockers.append("surface_warmup_motion_not_progressing")
    return not blockers, blockers, details


def quarantine_reason_allowed(entry: dict[str, Any],
                              *,
                              reset_scope: str,
                              setup_contention_ok: bool,
                              no_canary_retry_ok: bool,
                              canary_display_contention_ok: bool,
                              harness_ipc_drm_retry_ok: bool,
                              startup_status_retry_ok: bool,
                              surface_warmup_retry_ok: bool,
                              prior_panfrost_absolute_ok: bool) -> bool:
    reason = str(entry.get("reason") or "")
    if reset_scope == SETUP_CONTENTION_SCOPE:
        return setup_contention_ok and setup_contention_reason_allowed(reason)
    if reset_scope == NO_CANARY_SCOPE:
        return no_canary_retry_ok and set(reason.split(",")) == NO_CANARY_FAILURE_REASONS
    if reset_scope == CANARY_DISPLAY_CONTENTION_SCOPE:
        return canary_display_contention_ok and set(reason.split(",")) in (
            SETUP_CONTENTION_FAILURE_REASONS,
            C25_SURFACE_DISPLAY_CONTENTION_FAILURE_REASONS,
        )
    if reset_scope == HARNESS_IPC_DRM_SCOPE:
        return harness_ipc_drm_retry_ok and set(reason.split(",")) == HARNESS_IPC_DRM_FAILURE_REASONS
    if reset_scope == STARTUP_STATUS_SCOPE:
        return startup_status_retry_ok and set(reason.split(",")) == STARTUP_STATUS_FAILURE_REASONS
    if reset_scope == SURFACE_WARMUP_SCOPE:
        return surface_warmup_retry_ok and set(reason.split(",")) == SURFACE_WARMUP_FAILURE_REASONS
    if reset_scope == PRIOR_PANFROST_ABSOLUTE_SCOPE:
        return prior_panfrost_absolute_ok and set(reason.split(",")) == PRIOR_PANFROST_ABSOLUTE_FAILURE_REASONS
    return reason in ALLOWED_QUARANTINE_REASONS


def matches_target(entry: dict[str, Any],
                   identity: dict[str, Any],
                   *,
                   reset_scope: str,
                   setup_contention_ok: bool,
                   no_canary_retry_ok: bool,
                   canary_display_contention_ok: bool,
                   harness_ipc_drm_retry_ok: bool,
                   startup_status_retry_ok: bool,
                   surface_warmup_retry_ok: bool,
                   prior_panfrost_absolute_ok: bool) -> bool:
    return identity_matches_target(entry, identity) and quarantine_reason_allowed(
        entry,
        reset_scope=reset_scope,
        setup_contention_ok=setup_contention_ok,
        no_canary_retry_ok=no_canary_retry_ok,
        canary_display_contention_ok=canary_display_contention_ok,
        harness_ipc_drm_retry_ok=harness_ipc_drm_retry_ok,
        startup_status_retry_ok=startup_status_retry_ok,
        surface_warmup_retry_ok=surface_warmup_retry_ok,
        prior_panfrost_absolute_ok=prior_panfrost_absolute_ok,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--lab-only-quarantine-reset", action="store_true")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--allow-device-data-root", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--reset-scope", choices=sorted(RESET_SCOPES), required=True)
    parser.add_argument("--failed-candidate-health-dir", type=Path)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.lab_only_quarantine_reset or os.environ.get(LAB_ENV) != "1":
        print(
            f"player_runtime_lab_quarantine_reset_guard_required: pass --lab-only-quarantine-reset and set {LAB_ENV}=1",
            file=sys.stderr,
        )
        return 44

    work_dir = args.output_dir or Path(tempfile.mkdtemp(prefix="c18-player-runtime-lab-quarantine-reset-"))
    data_root = args.data_root or (work_dir / "data")
    ok, guard_reason = guarded_paths(args, work_dir, data_root)
    if not ok:
        print(guard_reason, file=sys.stderr)
        return 43

    manifest = read_json(args.manifest)
    release_gate.validate_release(args.manifest, args.payload)
    identity = payload_identity(manifest, args.payload)
    channel = str(manifest.get("channel") or "")
    if channel != "homologation":
        result = {
            "schema": SCHEMA,
            "component": COMPONENT,
            "passed": False,
            "blockers": ["manifest_channel_not_homologation"],
            "version": identity.get("version"),
            "channel": channel,
            "target_identity": identity,
            "reset_scope": args.reset_scope,
            "reason": args.reason,
            "removed_count": 0,
            "data_root": str(data_root),
            "device_data_root": data_root.resolve() == Path("/data"),
            "output_dir": str(work_dir),
            "network_required": False,
            "github_used": False,
            "non_claims": [
                "not_a_public_thaw",
                "not_stable_or_production",
                "does_not_apply_or_rollback_runtime",
            ],
        }
        write_json(work_dir / "quarantine-reset.json", result)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("player_runtime_lab_quarantine_reset_passed=false")
        return 42
    policy_path = work_dir / "lab-policy.json"
    write_lab_policy(policy_path, channel)
    configure_updatectl_for_lab(data_root, policy_path)

    public_before = {
        "apply": public_cli_freeze(data_root, "apply"),
        "rollback": public_cli_freeze(data_root, "rollback"),
        "reconcile": public_cli_freeze(data_root, "reconcile"),
    }
    before_snapshot = runtime_snapshot()
    state = updatectl._read_state()
    before_quarantine = updatectl._quarantine_entries(state)
    setup_ok, setup_blockers, setup_details = setup_contention_evidence(
        args.failed_candidate_health_dir,
        identity,
    ) if args.reset_scope == SETUP_CONTENTION_SCOPE else (False, [], {})
    no_canary_ok, no_canary_blockers, no_canary_details = no_canary_retry_evidence(
        args.failed_candidate_health_dir,
        identity,
    ) if args.reset_scope == NO_CANARY_SCOPE else (False, [], {})
    canary_display_contention_ok, canary_display_contention_blockers, canary_display_contention_details = canary_display_contention_retry_evidence(
        args.failed_candidate_health_dir,
        identity,
    ) if args.reset_scope == CANARY_DISPLAY_CONTENTION_SCOPE else (False, [], {})
    harness_ipc_drm_ok, harness_ipc_drm_blockers, harness_ipc_drm_details = harness_ipc_drm_retry_evidence(
        args.failed_candidate_health_dir,
        identity,
    ) if args.reset_scope == HARNESS_IPC_DRM_SCOPE else (False, [], {})
    startup_status_ok, startup_status_blockers, startup_status_details = startup_status_retry_evidence(
        args.failed_candidate_health_dir,
        identity,
    ) if args.reset_scope == STARTUP_STATUS_SCOPE else (False, [], {})
    surface_warmup_ok, surface_warmup_blockers, surface_warmup_details = surface_warmup_retry_evidence(
        args.failed_candidate_health_dir,
        identity,
    ) if args.reset_scope == SURFACE_WARMUP_SCOPE else (False, [], {})
    prior_panfrost_ok, prior_panfrost_blockers, prior_panfrost_details = prior_panfrost_absolute_retry_evidence(
        args.failed_candidate_health_dir,
        identity,
    ) if args.reset_scope == PRIOR_PANFROST_ABSOLUTE_SCOPE else (False, [], {})
    target_link = f"releases/{identity.get('version')}"
    active_links = [
        name
        for name, link in (
            ("current", before_snapshot.get("current_link")),
            ("previous", before_snapshot.get("previous_link")),
        )
        if link == target_link
    ]
    previous_linked_reset_allowed = (
        args.reset_scope == ARM_TIMEOUT_PREVIOUS_LINKED_SCOPE
        and active_links == ["previous"]
        and before_snapshot.get("current_link") != target_link
        and before_snapshot.get("state_current_version") != identity.get("version")
    )
    matching_entries = [entry for entry in before_quarantine if identity_matches_target(entry, identity)]
    disallowed_entries = [
        entry for entry in matching_entries
        if not quarantine_reason_allowed(
            entry,
            reset_scope=args.reset_scope,
            setup_contention_ok=setup_ok,
            no_canary_retry_ok=no_canary_ok,
            canary_display_contention_ok=canary_display_contention_ok,
            harness_ipc_drm_retry_ok=harness_ipc_drm_ok,
            startup_status_retry_ok=startup_status_ok,
            surface_warmup_retry_ok=surface_warmup_ok,
            prior_panfrost_absolute_ok=prior_panfrost_ok,
        )
    ]
    removed = [
        entry for entry in matching_entries
        if quarantine_reason_allowed(
            entry,
            reset_scope=args.reset_scope,
            setup_contention_ok=setup_ok,
            no_canary_retry_ok=no_canary_ok,
            canary_display_contention_ok=canary_display_contention_ok,
            harness_ipc_drm_retry_ok=harness_ipc_drm_ok,
            startup_status_retry_ok=startup_status_ok,
            surface_warmup_retry_ok=surface_warmup_ok,
            prior_panfrost_absolute_ok=prior_panfrost_ok,
        )
    ]
    blockers: list[str] = []
    if not all(item["frozen"] for item in public_before.values()):
        blockers.append("public_cli_not_frozen_before_reset")
    if active_links and not previous_linked_reset_allowed:
        blockers.append("target_linked_active")
    if disallowed_entries:
        blockers.append("target_quarantine_reason_not_allowed")
    if not matching_entries:
        blockers.append("target_quarantine_not_found")
    blockers.extend(setup_blockers)
    blockers.extend(no_canary_blockers)
    blockers.extend(canary_display_contention_blockers)
    blockers.extend(harness_ipc_drm_blockers)
    blockers.extend(startup_status_blockers)
    blockers.extend(surface_warmup_blockers)
    blockers.extend(prior_panfrost_blockers)
    if blockers:
        still_quarantined, quarantine_reason = updatectl._player_runtime_is_quarantined(identity, state)
        after_snapshot = runtime_snapshot()
        result = {
            "schema": SCHEMA,
            "component": COMPONENT,
            "passed": False,
            "blockers": blockers,
            "version": identity.get("version"),
            "channel": channel,
            "target_identity": identity,
            "reset_scope": args.reset_scope,
            "reason": args.reason,
            "removed_count": 0,
            "removed_entries": [],
            "matching_disallowed_entries": disallowed_entries,
            "active_links": active_links,
            "previous_linked_reset_allowed": previous_linked_reset_allowed,
            "setup_contention_evidence": setup_details,
            "no_canary_retry_evidence": no_canary_details,
            "canary_display_contention_retry_evidence": canary_display_contention_details,
            "harness_ipc_drm_retry_evidence": harness_ipc_drm_details,
            "startup_status_retry_evidence": startup_status_details,
            "surface_warmup_retry_evidence": surface_warmup_details,
            "prior_panfrost_absolute_retry_evidence": prior_panfrost_details,
            "still_quarantined": still_quarantined,
            "quarantine_reason": quarantine_reason,
            "links_unchanged": (
                before_snapshot.get("current_link") == after_snapshot.get("current_link")
                and before_snapshot.get("previous_link") == after_snapshot.get("previous_link")
            ),
            "before": before_snapshot,
            "after": after_snapshot,
            "public_cli_apply_frozen_before_reset": public_before["apply"],
            "public_cli_rollback_frozen_before_reset": public_before["rollback"],
            "public_cli_reconcile_frozen_before_reset": public_before["reconcile"],
            "public_cli_apply_still_frozen": public_before["apply"],
            "public_cli_rollback_still_frozen": public_before["rollback"],
            "public_cli_reconcile_still_frozen": public_before["reconcile"],
            "data_root": str(data_root),
            "device_data_root": data_root.resolve() == Path("/data"),
            "output_dir": str(work_dir),
            "network_required": False,
            "github_used": False,
            "non_claims": [
                "not_a_public_thaw",
                "not_stable_or_production",
                "does_not_apply_or_rollback_runtime",
            ],
        }
        write_json(work_dir / "quarantine-reset.json", result)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("player_runtime_lab_quarantine_reset_passed=false")
        return 1

    removed_ids = {id(entry) for entry in removed}
    remaining = [entry for entry in before_quarantine if id(entry) not in removed_ids]
    if removed:
        started_at = updatectl._utcnow_iso()
        state["quarantine"] = remaining
        state["last_operation"] = {
            "type": "lab_quarantine_reset",
            "status": "success",
            "started_at_utc": started_at,
            "finished_at_utc": updatectl._utcnow_iso(),
            "version": identity.get("version"),
            "payload_sha256": identity.get("payload_sha256"),
            "tree_sha256": identity.get("tree_sha256"),
            "reason": args.reason,
            "reset_scope": args.reset_scope,
            "removed_count": len(removed),
            "non_claims": [
                "not_a_public_thaw",
                "not_stable_or_production",
                "does_not_apply_or_rollback_runtime",
            ],
        }
        updatectl._write_state(state)

    public_after = {
        "apply": public_cli_freeze(data_root, "apply"),
        "rollback": public_cli_freeze(data_root, "rollback"),
        "reconcile": public_cli_freeze(data_root, "reconcile"),
    }
    reverted = False
    post_blockers: list[str] = []
    if not all(item["frozen"] for item in public_after.values()):
        post_blockers.append("public_cli_not_frozen_after_reset")
        rollback_state = updatectl._read_state()
        rollback_state["quarantine"] = before_quarantine
        rollback_state["last_operation"] = {
            "type": "lab_quarantine_reset",
            "status": "reverted",
            "finished_at_utc": updatectl._utcnow_iso(),
            "version": identity.get("version"),
            "payload_sha256": identity.get("payload_sha256"),
            "tree_sha256": identity.get("tree_sha256"),
            "reason": args.reason,
            "reset_scope": args.reset_scope,
            "rollback_reason": "public_cli_not_frozen_after_reset",
        }
        updatectl._write_state(rollback_state)
        reverted = True
    after_snapshot = runtime_snapshot()
    after_state = updatectl._read_state()
    still_quarantined, quarantine_reason = updatectl._player_runtime_is_quarantined(identity, after_state)
    links_unchanged = (
        before_snapshot.get("current_link") == after_snapshot.get("current_link")
        and before_snapshot.get("previous_link") == after_snapshot.get("previous_link")
    )
    passed = (
        bool(removed)
        and not still_quarantined
        and links_unchanged
        and all(item["frozen"] for item in public_before.values())
        and all(item["frozen"] for item in public_after.values())
    )
    result = {
        "schema": SCHEMA,
        "component": COMPONENT,
        "passed": passed,
        "blockers": post_blockers,
        "version": identity.get("version"),
        "channel": channel,
        "target_identity": identity,
        "reset_scope": args.reset_scope,
        "reason": args.reason,
        "removed_count": len(removed),
        "removed_entries": removed,
        "matching_disallowed_entries": [],
        "active_links": active_links,
        "previous_linked_reset_allowed": previous_linked_reset_allowed,
        "setup_contention_evidence": setup_details,
        "no_canary_retry_evidence": no_canary_details,
        "canary_display_contention_retry_evidence": canary_display_contention_details,
        "harness_ipc_drm_retry_evidence": harness_ipc_drm_details,
        "startup_status_retry_evidence": startup_status_details,
        "surface_warmup_retry_evidence": surface_warmup_details,
        "prior_panfrost_absolute_retry_evidence": prior_panfrost_details,
        "reverted": reverted,
        "still_quarantined": still_quarantined,
        "quarantine_reason": quarantine_reason,
        "links_unchanged": links_unchanged,
        "before": before_snapshot,
        "after": after_snapshot,
        "public_cli_apply_frozen_before_reset": public_before["apply"],
        "public_cli_rollback_frozen_before_reset": public_before["rollback"],
        "public_cli_reconcile_frozen_before_reset": public_before["reconcile"],
        "public_cli_apply_still_frozen": public_after["apply"],
        "public_cli_rollback_still_frozen": public_after["rollback"],
        "public_cli_reconcile_still_frozen": public_after["reconcile"],
        "data_root": str(data_root),
        "device_data_root": data_root.resolve() == Path("/data"),
        "output_dir": str(work_dir),
        "network_required": False,
        "github_used": False,
        "non_claims": [
            "not_a_public_thaw",
            "not_stable_or_production",
            "does_not_apply_or_rollback_runtime",
        ],
    }
    write_json(work_dir / "quarantine-reset.json", result)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"player_runtime_lab_quarantine_reset_passed={str(bool(passed)).lower()}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
