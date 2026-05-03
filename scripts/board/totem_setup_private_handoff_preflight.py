#!/usr/bin/env python3
"""C8.6 controlled private handoff preflight.

This tool prepares a temporary private setup candidate under /tmp, validates
C5.1 real-dry-run, observes service/player preconditions without changing
state, and writes sanitized status artifacts. It never writes /data or /opt,
never calls the C6 writer, never uses --enable-real-write, and never prints
private values.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any


sys.dont_write_bytecode = True

import totem_config_contract_validate as contract


SCHEMA_VERSION = "dadooh-c8.6-private-handoff-preflight.v1"
CLEANUP_SCHEMA_VERSION = "dadooh-c8.6.1-private-handoff-cleanup.v1"
DEFAULT_SOURCE_CANDIDATE = "/tmp/dadooh-c8-1-setup-minimo/candidate-config.json"
DEFAULT_PRIVATE_VALUES = "/tmp/dadooh-c8-6-private/private-values.json"
DEFAULT_OUT_DIR = "/tmp/dadooh-c8-6-handoff-preflight"

PRIVATE_CANDIDATE_FILENAME = "candidate-private.json"
STATUS_FILENAME = "handoff-preflight-status.json"
SUMMARY_FILENAME = "summary.txt"

TMP_ROOT = pathlib.Path("/tmp").resolve()
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
SERVICE_NAME = "kiosky-player.service"

REQUIRED_PRIVATE_VALUE_FIELDS = ("api_url", "api_key", "environment_id")
OPTIONAL_PRIVATE_VALUE_FIELDS = ("station_id",)
NON_PRIVATE_METADATA_FIELDS = {
    "setup_source",
    "setup_environment_source",
    "setup_private_values_source",
}
SENSITIVE_OUTPUT_MARKERS = (
    "api_key",
    "api_url",
    "token",
    "secret",
    "password",
    "senha",
    "ssid",
    "hostname",
    "gateway",
    "dns",
    " mac",
    "raw_payload",
)
READ_ONLY_SYSTEMCTL_COMMANDS = (
    ("systemctl", "is-active", SERVICE_NAME),
    ("systemctl", "is-enabled", SERVICE_NAME),
)


class PrivateHandoffError(ValueError):
    """Raised for expected C8.6 preflight failures."""


def utc_timestamp() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def path_is_under(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def path_is_in_repository(path: pathlib.Path) -> bool:
    current = path if path.is_dir() else path.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return True
    return False


def absolute_no_resolve(raw_path: str) -> pathlib.Path:
    return pathlib.Path(os.path.abspath(str(pathlib.Path(raw_path).expanduser())))


def require_tmp_dir(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    raw_absolute = absolute_no_resolve(raw_path)
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise PrivateHandoffError("out-dir must be under /tmp")

    resolved = path.resolve(strict=False)
    if not path_is_under(resolved, TMP_ROOT):
        raise PrivateHandoffError("out-dir must resolve under /tmp")
    if resolved == TMP_ROOT:
        raise PrivateHandoffError("out-dir must be a dedicated directory under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise PrivateHandoffError("out-dir exists and is not a directory")
    if path_is_in_repository(resolved):
        raise PrivateHandoffError("out-dir must not be inside a repository")
    return resolved


def normalize_tmp_file(raw_path: str, label: str, *, reject_repo: bool) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    raw_absolute = absolute_no_resolve(raw_path)
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise PrivateHandoffError(f"{label} must be under /tmp")

    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PrivateHandoffError(f"{label} file not found") from exc

    if not path_is_under(resolved, TMP_ROOT):
        raise PrivateHandoffError(f"{label} must resolve under /tmp")
    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt"), pathlib.Path("/home")):
        if path_is_under(resolved, forbidden):
            raise PrivateHandoffError(f"refusing {label} under {forbidden}")
    if reject_repo and path_is_in_repository(resolved):
        raise PrivateHandoffError(f"{label} must not be inside a repository")
    if not resolved.is_file():
        raise PrivateHandoffError(f"{label} must be a file")
    return resolved


def prepare_private_dir(path: pathlib.Path) -> None:
    path.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    if stat.S_IMODE(path.stat().st_mode) != PRIVATE_DIR_MODE:
        path.chmod(PRIVATE_DIR_MODE)


def ensure_output_target(path: pathlib.Path, out_dir: pathlib.Path) -> None:
    resolved_out = out_dir.resolve(strict=True)
    resolved_target = path.resolve(strict=False)
    if not path_is_under(resolved_target, resolved_out):
        raise PrivateHandoffError("output target escaped out-dir")
    if resolved_target == resolved_out:
        raise PrivateHandoffError("output target must be a file")
    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt")):
        if path_is_under(resolved_target, forbidden):
            raise PrivateHandoffError("refusing to write outside /tmp")


def fsync_directory(path: pathlib.Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_private_text(path: pathlib.Path, content: str, out_dir: pathlib.Path) -> None:
    ensure_output_target(path, out_dir)
    payload = content if content.endswith("\n") else content + "\n"
    tmp_name: str | None = None
    fd: int | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent), text=True)
        os.fchmod(fd, PRIVATE_FILE_MODE)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
        path.chmod(PRIVATE_FILE_MODE)
        fsync_directory(path.parent)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def atomic_write_private_json(path: pathlib.Path, value: dict[str, Any], out_dir: pathlib.Path) -> None:
    atomic_write_private_text(path, json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True), out_dir)


def load_json_object(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError as exc:
        raise PrivateHandoffError(f"{label} is not valid JSON") from exc
    except OSError as exc:
        raise PrivateHandoffError(f"{label} could not be read") from exc

    if not isinstance(value, dict):
        raise PrivateHandoffError(f"{label} JSON root must be an object")
    return value


def validate_private_values(value: dict[str, Any]) -> dict[str, str]:
    private_values: dict[str, str] = {}
    for field in REQUIRED_PRIVATE_VALUE_FIELDS:
        raw = value.get(field)
        if not isinstance(raw, str) or not raw.strip():
            raise PrivateHandoffError("required private value missing or invalid")
        private_values[field] = raw.strip()
    for field in OPTIONAL_PRIVATE_VALUE_FIELDS:
        raw = value.get(field)
        if raw is None:
            continue
        if not isinstance(raw, str):
            raise PrivateHandoffError("optional private value has invalid type")
        private_values[field] = raw.strip()
    return private_values


def build_private_candidate(source: dict[str, Any], private_values: dict[str, str]) -> dict[str, Any]:
    candidate = dict(source)
    for field in REQUIRED_PRIVATE_VALUE_FIELDS:
        candidate[field] = private_values[field]
    if private_values.get("station_id"):
        candidate["station_id"] = private_values["station_id"]
    candidate["setup_environment_source"] = "private_approved_local"
    candidate["setup_private_values_source"] = "private_tmp_file"
    candidate["setup_source"] = "c8.6-private-handoff-preflight"
    return candidate


def normalize_systemctl_state(raw_value: str) -> str:
    value = raw_value.strip().lower()
    allowed = {
        "active",
        "inactive",
        "failed",
        "activating",
        "deactivating",
        "reloading",
        "enabled",
        "disabled",
        "static",
        "masked",
        "indirect",
        "generated",
        "transient",
        "linked",
    }
    return value if value in allowed else "unknown"


def run_read_only_systemctl(args: tuple[str, ...]) -> dict[str, Any]:
    if args not in READ_ONLY_SYSTEMCTL_COMMANDS:
        raise PrivateHandoffError("systemctl command outside read-only allowlist")
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"available": False, "state": "unavailable", "returncode_category": "unavailable"}

    returncode_category = "zero" if completed.returncode == 0 else "nonzero"
    return {
        "available": True,
        "state": normalize_systemctl_state(completed.stdout),
        "returncode_category": returncode_category,
    }


def process_matches(label: str, cmdline: str) -> str | None:
    combined = f"{label} {cmdline}".lower()
    if "mpv" in combined:
        return "mpv"
    if "kiosk.py" in combined or "kiosky-player" in combined:
        return "kiosky_player"
    return None


def observe_player_processes() -> dict[str, Any]:
    counts = {"kiosky_player": 0, "mpv": 0}
    proc_root = pathlib.Path("/proc")
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return {"observed": False, "counts": counts, "total_relevant_processes": 0}

    for proc in entries:
        if not proc.name.isdigit():
            continue
        try:
            label = (proc / "comm").read_text(encoding="utf-8", errors="ignore").strip()
            cmdline = (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
        except OSError:
            continue
        match = process_matches(label, cmdline)
        if match is not None:
            counts[match] += 1

    return {
        "observed": True,
        "counts": counts,
        "total_relevant_processes": sum(counts.values()),
    }


def observe_runtime_preconditions() -> dict[str, Any]:
    active = run_read_only_systemctl(("systemctl", "is-active", SERVICE_NAME))
    enabled = run_read_only_systemctl(("systemctl", "is-enabled", SERVICE_NAME))
    processes = observe_player_processes()
    player_processes_present = processes["total_relevant_processes"] > 0
    service_active = active["state"] == "active"
    preconditions_clear_for_future_write = not service_active and not player_processes_present

    return {
        "service": {
            "name": SERVICE_NAME,
            "read_only_observed": bool(active["available"] or enabled["available"]),
            "active_state": active["state"],
            "enabled_state": enabled["state"],
            "state_change_command_called": False,
            "stop_or_start_called": False,
        },
        "player": {
            "processes_observed": bool(processes["observed"]),
            "relevant_processes_count": int(processes["total_relevant_processes"]),
            "process_detail_values_written": False,
        },
        "preconditions_clear_for_future_write": preconditions_clear_for_future_write,
        "abort_before_real_write": not preconditions_clear_for_future_write,
        "abort_reason_categories": []
        if preconditions_clear_for_future_write
        else ["service_or_player_not_blocked_or_not_confirmed"],
        "read_only_commands_executed": True,
        "state_changing_commands_executed": False,
    }


def summarize_validation(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "valid": bool(status["valid"]),
        "missing_fields_count": len(status["missing_fields"]),
        "invalid_fields_count": len(status["invalid_fields"]),
        "placeholder_findings_count": len(status["placeholder_findings"]),
        "path_findings_count": len(status["path_findings"]),
        "credential_present": bool(status["api_key_present"]),
        "credential_placeholder_detected": bool(status["api_key_placeholder_detected"]),
        "environment_identifier_format_valid": bool(status["environment_id_status"]["valid"]),
        "station_identifier_optional_format_valid": bool(status["station_id_status"]["valid"]),
    }


def build_status(
    *,
    generated_at: str,
    source_candidate: dict[str, Any],
    private_candidate: dict[str, Any],
    private_values: dict[str, str],
    source_allow_status: dict[str, Any],
    private_allow_status: dict[str, Any],
    private_real_status: dict[str, Any],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    required_count = len(contract.REQUIRED_CONFIG_FIELDS)
    present_required_count = sum(1 for field in contract.REQUIRED_CONFIG_FIELDS if field in private_candidate)
    known_contract_fields = set(contract.REQUIRED_CONFIG_FIELDS) | set(contract.OPTIONAL_CONFIG_FIELDS)
    private_extra_fields_count = len(set(private_candidate) - known_contract_fields)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "result": "passed",
        "phase": "private_handoff_preflight_completed",
        "authorization": {
            "private_values_source_approved_by_human": True,
            "real_write_approved": False,
            "human_approval_for_real_write_still_required": True,
            "abort_points_documented": True,
        },
        "source_candidate": {
            "read_from_tmp": True,
            "allow_mock_valid": bool(source_allow_status["valid"]),
            "copied_to_status": False,
            "copied_to_summary": False,
            "values_written_to_status": False,
            "values_written_to_summary": False,
        },
        "private_inputs": {
            "read_from_tmp": True,
            "inside_repository": False,
            "required_categories_present_count": len(REQUIRED_PRIVATE_VALUE_FIELDS),
            "optional_station_identifier_provided": "station_id" in private_values and bool(private_values["station_id"]),
            "values_written_to_status": False,
            "values_written_to_summary": False,
        },
        "private_candidate": {
            "file": PRIVATE_CANDIDATE_FILENAME,
            "written_under_tmp": True,
            "contains_private_values": True,
            "copied_to_status": False,
            "copied_to_summary": False,
            "values_written_to_status": False,
            "values_written_to_summary": False,
            "required_contract_fields_count": required_count,
            "required_contract_fields_present_count": present_required_count,
            "extra_fields_count": private_extra_fields_count,
        },
        "contract_validation": {
            "validator": "totem_config_contract_validate.py",
            "contract": "C5.1",
            "source_allow_mock": summarize_validation(source_allow_status),
            "private_allow_mock": summarize_validation(private_allow_status),
            "private_real_dry_run": summarize_validation(private_real_status),
            "private_real_dry_run_passed": True,
            "placeholder_findings_cleared": len(private_real_status["placeholder_findings"]) == 0,
        },
        "runtime_preconditions": runtime,
        "writer_handoff": {
            "candidate_ready_for_writer_validation": True,
            "candidate_ready_for_real_write": False,
            "writer_real_mode_called": False,
            "writer_simulated_write_called": False,
            "writer_real_write_blocked": True,
            "enable_real_write_used": False,
            "future_writer_must_validate_again": True,
            "future_writer_must_preserve_backup_and_rollback": True,
            "future_writer_requires_service_blocked": True,
            "future_writer_requires_human_approval": True,
            "handoff_decision": "preflight_only_abort_before_writer",
        },
        "guardrails": {
            "writes_only_under_tmp": True,
            "private_candidate_written_under_tmp": True,
            "real_config_read": False,
            "real_config_written": False,
            "data_written": False,
            "opt_written": False,
            "writer_real_mode_called": False,
            "enable_real_write_used": False,
            "systemctl_read_only_called": bool(runtime["read_only_commands_executed"]),
            "systemctl_state_change_called": False,
            "service_changed": False,
            "player_started": False,
            "player_stopped": False,
            "mpv_called": False,
            "network_external_access": False,
            "nmcli_called": False,
            "backend_called": False,
            "wifi_changed": False,
        },
        "privacy": {
            "private_values_copied_to_status": False,
            "private_values_copied_to_summary": False,
            "private_candidate_copied_to_status": False,
            "private_candidate_copied_to_summary": False,
            "credential_value_written_to_status": False,
            "credential_value_written_to_summary": False,
            "endpoint_value_written_to_status": False,
            "endpoint_value_written_to_summary": False,
            "environment_identifier_raw_written_to_status": False,
            "environment_identifier_raw_written_to_summary": False,
            "paths_written_to_status": False,
            "paths_written_to_summary": False,
            "raw_service_output_written": False,
            "raw_process_output_written": False,
        },
        "artifacts": {
            "private_candidate": PRIVATE_CANDIDATE_FILENAME,
            "status": STATUS_FILENAME,
            "summary": SUMMARY_FILENAME,
        },
    }


def build_summary(status: dict[str, Any]) -> str:
    runtime = status["runtime_preconditions"]
    return "\n".join(
        [
            "Dadooh C8.6 private handoff preflight",
            "",
            f"schema_version: {status['schema_version']}",
            f"generated_at_utc: {status['generated_at_utc']}",
            f"result: {status['result']}",
            f"phase: {status['phase']}",
            "private_values_source_approved_by_human: true",
            "real_write_approved: false",
            "private_candidate: candidate-private.json",
            "private_candidate_written_under_tmp: true",
            "private_candidate_values_written_to_summary: false",
            "required_private_categories_present_count: "
            f"{status['private_inputs']['required_categories_present_count']}",
            "optional_station_identifier_provided: "
            f"{str(status['private_inputs']['optional_station_identifier_provided']).lower()}",
            "source_allow_mock_valid: "
            f"{str(status['contract_validation']['source_allow_mock']['valid']).lower()}",
            "private_real_dry_run_valid: "
            f"{str(status['contract_validation']['private_real_dry_run']['valid']).lower()}",
            "placeholder_findings_cleared: "
            f"{str(status['contract_validation']['placeholder_findings_cleared']).lower()}",
            "service_read_only_observed: "
            f"{str(runtime['service']['read_only_observed']).lower()}",
            f"service_active_state_category: {runtime['service']['active_state']}",
            f"service_enabled_state_category: {runtime['service']['enabled_state']}",
            "player_processes_observed: "
            f"{str(runtime['player']['processes_observed']).lower()}",
            f"player_relevant_processes_count: {runtime['player']['relevant_processes_count']}",
            "preconditions_clear_for_future_write: "
            f"{str(runtime['preconditions_clear_for_future_write']).lower()}",
            "abort_before_real_write: "
            f"{str(runtime['abort_before_real_write']).lower()}",
            "writer_real_write_blocked: true",
            "writer_real_mode_called: false",
            "writer_simulated_write_called: false",
            "enable_real_write_used: false",
            "",
            "Guardrails:",
            "writes_only_under_tmp: true",
            "real_config_read: false",
            "real_config_written: false",
            "data_written: false",
            "opt_written: false",
            "systemctl_read_only_called: true",
            "systemctl_state_change_called: false",
            "service_changed: false",
            "player_started: false",
            "player_stopped: false",
            "mpv_called: false",
            "network_external_access: false",
            "nmcli_called: false",
            "backend_called: false",
            "wifi_changed: false",
            "",
            "Privacy:",
            "private_values_copied_to_output_status: false",
            "private_candidate_copied_to_status_or_summary: false",
            "credential_value_written_to_output: false",
            "endpoint_value_written_to_output: false",
            "environment_identifier_raw_written_to_output: false",
            "paths_written_to_output: false",
            "raw_service_output_written: false",
            "raw_process_output_written: false",
        ]
    )


def output_text(out_dir: pathlib.Path) -> str:
    parts = []
    for name in (STATUS_FILENAME, SUMMARY_FILENAME):
        path = out_dir / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def load_previous_sanitized_status(out_dir: pathlib.Path) -> dict[str, Any]:
    path = out_dir / STATUS_FILENAME
    if not path.exists():
        return {
            "status_present_before_cleanup": False,
            "private_real_dry_run_passed": False,
            "writer_real_write_blocked": False,
        }

    try:
        status = load_json_object(path, "previous status")
    except PrivateHandoffError:
        return {
            "status_present_before_cleanup": True,
            "private_real_dry_run_passed": False,
            "writer_real_write_blocked": False,
        }

    return {
        "status_present_before_cleanup": True,
        "private_real_dry_run_passed": bool(
            status.get("contract_validation", {}).get("private_real_dry_run", {}).get("valid")
        ),
        "writer_real_write_blocked": bool(status.get("writer_handoff", {}).get("writer_real_write_blocked")),
    }


def forbidden_text_variants(value: str) -> tuple[str, str]:
    escaped = json.dumps(value, ensure_ascii=True)[1:-1]
    return (value, escaped)


def assert_sanitized_outputs(
    out_dir: pathlib.Path,
    source_candidate: dict[str, Any],
    private_values: dict[str, str],
    private_candidate: dict[str, Any],
) -> None:
    text = output_text(out_dir)
    for candidate in (source_candidate, private_values, private_candidate):
        for field, value in candidate.items():
            if field in NON_PRIVATE_METADATA_FIELDS:
                continue
            if not isinstance(value, str) or not value:
                continue
            for variant in forbidden_text_variants(value):
                if variant and variant in text:
                    raise PrivateHandoffError("privacy scan blocked private value in status/summary")

    for marker in SENSITIVE_OUTPUT_MARKERS:
        if marker in text.lower():
            raise PrivateHandoffError("privacy scan blocked sensitive marker in status/summary")


def write_outputs(
    out_dir: pathlib.Path,
    private_candidate: dict[str, Any],
    status: dict[str, Any],
    source_candidate: dict[str, Any],
    private_values: dict[str, str],
) -> None:
    prepare_private_dir(out_dir)
    atomic_write_private_json(out_dir / PRIVATE_CANDIDATE_FILENAME, private_candidate, out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_summary(status), out_dir)
    assert_sanitized_outputs(out_dir, source_candidate, private_values, private_candidate)


def normalize_cleanup_target(raw_path: str, label: str, *, reject_repo: bool) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    raw_absolute = absolute_no_resolve(raw_path)
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise PrivateHandoffError(f"{label} cleanup target must be under /tmp")

    if not path.exists() and not path.is_symlink():
        return path.resolve(strict=False)

    resolved = path.resolve(strict=True)
    if not path_is_under(resolved, TMP_ROOT):
        raise PrivateHandoffError(f"{label} cleanup target must resolve under /tmp")
    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt"), pathlib.Path("/home")):
        if path_is_under(resolved, forbidden):
            raise PrivateHandoffError(f"refusing cleanup target under {forbidden}")
    if reject_repo and path_is_in_repository(resolved):
        raise PrivateHandoffError(f"{label} cleanup target must not be inside a repository")
    if resolved.is_dir():
        raise PrivateHandoffError(f"{label} cleanup target must be a file")
    return resolved


def cleanup_private_file(raw_path: str, label: str, *, reject_repo: bool) -> dict[str, Any]:
    path = pathlib.Path(raw_path).expanduser()
    normalize_cleanup_target(raw_path, label, reject_repo=reject_repo)
    existed_before = path.exists() or path.is_symlink()
    removed = False
    if existed_before:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        else:
            removed = True
    exists_after = path.exists() or path.is_symlink()
    return {
        "target": label,
        "existed_before": existed_before,
        "removed": removed,
        "exists_after": exists_after,
        "value_read": False,
        "raw_path_written": False,
    }


def build_cleanup_status(
    *,
    generated_at: str,
    previous_status: dict[str, Any],
    private_candidate_cleanup: dict[str, Any],
    private_input_cleanup: dict[str, Any],
) -> dict[str, Any]:
    private_files_remaining_count = sum(
        1
        for item in (private_candidate_cleanup, private_input_cleanup)
        if bool(item["exists_after"])
    )
    return {
        "schema_version": CLEANUP_SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "result": "passed",
        "phase": "private_artifacts_cleanup_completed",
        "previous_preflight": previous_status,
        "cleanup": {
            "executed": True,
            "explicit_confirmation_received": True,
            "private_candidate_removed": bool(private_candidate_cleanup["removed"]),
            "private_input_removed": bool(private_input_cleanup["removed"]),
            "private_files_remaining_count": private_files_remaining_count,
            "private_candidate": private_candidate_cleanup,
            "private_input": private_input_cleanup,
            "status_summary_preserved": True,
        },
        "writer_handoff": {
            "writer_real_mode_called": False,
            "writer_simulated_write_called": False,
            "writer_real_write_blocked": True,
            "enable_real_write_used": False,
            "handoff_decision": "cleanup_completed_abort_before_writer",
        },
        "guardrails": {
            "writes_only_under_tmp": True,
            "real_config_read": False,
            "real_config_written": False,
            "data_written": False,
            "opt_written": False,
            "writer_real_mode_called": False,
            "enable_real_write_used": False,
            "systemctl_read_only_called": False,
            "systemctl_state_change_called": False,
            "service_changed": False,
            "player_started": False,
            "player_stopped": False,
            "mpv_called": False,
            "network_external_access": False,
            "nmcli_called": False,
            "backend_called": False,
            "wifi_changed": False,
        },
        "privacy": {
            "private_values_read_during_cleanup": False,
            "private_candidate_read_during_cleanup": False,
            "private_values_copied_to_status": False,
            "private_values_copied_to_summary": False,
            "private_candidate_copied_to_status": False,
            "private_candidate_copied_to_summary": False,
            "credential_value_written_to_status": False,
            "credential_value_written_to_summary": False,
            "endpoint_value_written_to_status": False,
            "endpoint_value_written_to_summary": False,
            "environment_identifier_raw_written_to_status": False,
            "environment_identifier_raw_written_to_summary": False,
            "paths_written_to_status": False,
            "paths_written_to_summary": False,
        },
        "artifacts": {
            "status": STATUS_FILENAME,
            "summary": SUMMARY_FILENAME,
            "private_candidate_remaining": False,
            "private_input_remaining": False,
        },
    }


def build_cleanup_summary(status: dict[str, Any]) -> str:
    cleanup = status["cleanup"]
    previous = status["previous_preflight"]
    return "\n".join(
        [
            "Dadooh C8.6.1 private handoff cleanup",
            "",
            f"schema_version: {status['schema_version']}",
            f"generated_at_utc: {status['generated_at_utc']}",
            f"result: {status['result']}",
            f"phase: {status['phase']}",
            "cleanup_executed: true",
            "explicit_confirmation_received: true",
            f"previous_status_present: {str(previous['status_present_before_cleanup']).lower()}",
            f"previous_private_real_dry_run_passed: {str(previous['private_real_dry_run_passed']).lower()}",
            f"previous_writer_real_write_blocked: {str(previous['writer_real_write_blocked']).lower()}",
            f"private_candidate_removed: {str(cleanup['private_candidate_removed']).lower()}",
            f"private_input_removed: {str(cleanup['private_input_removed']).lower()}",
            f"private_files_remaining_count: {cleanup['private_files_remaining_count']}",
            "status_summary_preserved: true",
            "writer_real_write_blocked: true",
            "writer_real_mode_called: false",
            "enable_real_write_used: false",
            "",
            "Guardrails:",
            "writes_only_under_tmp: true",
            "real_config_read: false",
            "real_config_written: false",
            "data_written: false",
            "opt_written: false",
            "systemctl_read_only_called: false",
            "systemctl_state_change_called: false",
            "service_changed: false",
            "player_started: false",
            "player_stopped: false",
            "mpv_called: false",
            "network_external_access: false",
            "nmcli_called: false",
            "backend_called: false",
            "wifi_changed: false",
            "",
            "Privacy:",
            "private_values_read_during_cleanup: false",
            "private_candidate_read_during_cleanup: false",
            "private_values_copied_to_output: false",
            "private_candidate_copied_to_output: false",
            "credential_value_written_to_output: false",
            "endpoint_value_written_to_output: false",
            "environment_identifier_raw_written_to_output: false",
            "paths_written_to_output: false",
        ]
    )


def write_cleanup_outputs(out_dir: pathlib.Path, status: dict[str, Any]) -> None:
    prepare_private_dir(out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_cleanup_summary(status), out_dir)


def run_cleanup(
    private_values_raw: str,
    out_dir_raw: str,
    *,
    confirm_cleanup_private_artifacts: bool,
) -> dict[str, Any]:
    if not confirm_cleanup_private_artifacts:
        raise PrivateHandoffError("cleanup requires explicit confirmation")

    out_dir = require_tmp_dir(out_dir_raw)
    previous_status = load_previous_sanitized_status(out_dir)
    private_candidate_cleanup = cleanup_private_file(
        str(out_dir / PRIVATE_CANDIDATE_FILENAME),
        "private_candidate",
        reject_repo=False,
    )
    private_input_cleanup = cleanup_private_file(
        private_values_raw,
        "private_input",
        reject_repo=True,
    )
    status = build_cleanup_status(
        generated_at=utc_timestamp(),
        previous_status=previous_status,
        private_candidate_cleanup=private_candidate_cleanup,
        private_input_cleanup=private_input_cleanup,
    )
    write_cleanup_outputs(out_dir, status)
    return status


def run_preflight(
    source_raw: str,
    private_values_raw: str,
    out_dir_raw: str,
    *,
    confirm_private_values_approved: bool,
) -> dict[str, Any]:
    if not confirm_private_values_approved:
        raise PrivateHandoffError("private preflight requires explicit human approval")

    out_dir = require_tmp_dir(out_dir_raw)
    source_path = normalize_tmp_file(source_raw, "source candidate", reject_repo=False)
    private_values_path = normalize_tmp_file(private_values_raw, "private values", reject_repo=True)

    source_candidate = load_json_object(source_path, "source candidate")
    private_values = validate_private_values(load_json_object(private_values_path, "private values"))

    source_allow_status = contract.validate_candidate_config(source_candidate, "allow-mock")
    if not source_allow_status["valid"]:
        raise PrivateHandoffError("source candidate failed C5.1 allow-mock validation")

    private_candidate = build_private_candidate(source_candidate, private_values)
    private_allow_status = contract.validate_candidate_config(private_candidate, "allow-mock")
    private_real_status = contract.validate_candidate_config(private_candidate, "real-dry-run")
    if not private_allow_status["valid"]:
        raise PrivateHandoffError("private candidate failed C5.1 allow-mock validation")
    if not private_real_status["valid"]:
        raise PrivateHandoffError("private candidate failed C5.1 real-dry-run validation")
    if private_real_status["placeholder_findings"]:
        raise PrivateHandoffError("private candidate still has placeholder findings")

    runtime = observe_runtime_preconditions()
    status = build_status(
        generated_at=utc_timestamp(),
        source_candidate=source_candidate,
        private_candidate=private_candidate,
        private_values=private_values,
        source_allow_status=source_allow_status,
        private_allow_status=private_allow_status,
        private_real_status=private_real_status,
        runtime=runtime,
    )
    write_outputs(out_dir, private_candidate, status, source_candidate, private_values)
    return status


def file_mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def build_c8_mock_candidate() -> dict[str, Any]:
    candidate = contract.build_mock_candidate()
    candidate["environment_id"] = "ENV-MOCK-LOJA-A"
    candidate["rotation_deg"] = 90
    candidate["setup_environment_source"] = "mock_list"
    candidate["setup_source"] = "c8.6-self-test-source"
    return candidate


def write_private_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    prepare_private_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")
    path.chmod(PRIVATE_FILE_MODE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_raises_private_handoff(fn: Any, message: str) -> None:
    try:
        fn()
    except PrivateHandoffError:
        return
    raise AssertionError(message)


def run_self_test() -> None:
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c8-6-private-handoff-self-test-", dir="/tmp"))
    try:
        source = build_c8_mock_candidate()
        private_values = {
            "api_url": "https://api.sandbox.localhost/search",
            "api_key": "A1B2C3D4E5F60718293A4B5C6D7E8F90",
            "environment_id": "ENV-APPROVED-SELFTEST",
        }

        source_path = root / "source" / "candidate-config.json"
        private_values_path = root / "private" / "private-values.json"
        write_private_json(source_path, source)
        write_private_json(private_values_path, private_values)

        out_dir = root / "out"
        status = run_preflight(
            str(source_path),
            str(private_values_path),
            str(out_dir),
            confirm_private_values_approved=True,
        )
        assert_true(status["result"] == "passed", "private handoff should pass")
        assert_true(
            status["contract_validation"]["private_real_dry_run"]["valid"],
            "private candidate should pass real-dry-run",
        )
        assert_true(status["writer_handoff"]["writer_real_write_blocked"], "writer real write should be blocked")
        assert_true(not status["writer_handoff"]["writer_real_mode_called"], "writer real mode should not be called")
        assert_true(not status["writer_handoff"]["enable_real_write_used"], "enable real write should not be used")
        assert_true(file_mode(out_dir) == PRIVATE_DIR_MODE, "out-dir mode should be 700")

        private_candidate_path = out_dir / PRIVATE_CANDIDATE_FILENAME
        private_candidate = load_json_object(private_candidate_path, "private candidate")
        assert_true(file_mode(private_candidate_path) == PRIVATE_FILE_MODE, "private candidate mode should be 600")
        assert_true(
            contract.validate_candidate_config(private_candidate, "real-dry-run")["valid"],
            "written private candidate should pass real-dry-run",
        )
        assert_true(private_candidate["rotation_deg"] == source["rotation_deg"], "rotation_deg should be preserved")
        assert_true(private_candidate["api_url"] == private_values["api_url"], "endpoint should be applied")
        assert_true(private_candidate["api_key"] == private_values["api_key"], "credential should be applied")
        assert_true(
            private_candidate["environment_id"] == private_values["environment_id"],
            "environment identifier should be applied",
        )
        assert_true(private_candidate["station_id"] == source["station_id"], "optional station_id should be preserved")

        for name in (STATUS_FILENAME, SUMMARY_FILENAME):
            path = out_dir / name
            assert_true(path.exists(), f"{name} should exist")
            assert_true(file_mode(path) == PRIVATE_FILE_MODE, f"{name} mode should be 600")
            resolved = path.resolve(strict=True)
            assert_true(path_is_under(resolved, TMP_ROOT), f"{name} should be under /tmp")
            assert_true(not path_is_under(resolved, pathlib.Path("/data")), f"{name} wrote under /data")
            assert_true(not path_is_under(resolved, pathlib.Path("/opt")), f"{name} wrote under /opt")

        text = output_text(out_dir)
        for candidate in (source, private_values, private_candidate):
            for field, value in candidate.items():
                if field in NON_PRIVATE_METADATA_FIELDS:
                    continue
                if isinstance(value, str) and value:
                    for variant in forbidden_text_variants(value):
                        assert_true(variant not in text, "status/summary leaked private value")
        for marker in SENSITIVE_OUTPUT_MARKERS:
            assert_true(marker not in text.lower(), f"status/summary leaked marker {marker}")
        for key in (
            "real_config_read",
            "real_config_written",
            "data_written",
            "opt_written",
            "writer_real_mode_called",
            "enable_real_write_used",
            "systemctl_state_change_called",
            "service_changed",
            "player_started",
            "player_stopped",
            "mpv_called",
            "network_external_access",
            "nmcli_called",
            "backend_called",
            "wifi_changed",
        ):
            assert_true(status["guardrails"][key] is False, f"guardrail {key} should be false")

        cleanup_status = run_cleanup(
            str(private_values_path),
            str(out_dir),
            confirm_cleanup_private_artifacts=True,
        )
        assert_true(cleanup_status["result"] == "passed", "cleanup should pass")
        assert_true(cleanup_status["cleanup"]["executed"], "cleanup should be marked executed")
        assert_true(
            cleanup_status["cleanup"]["private_candidate_removed"],
            "cleanup should remove private candidate",
        )
        assert_true(cleanup_status["cleanup"]["private_input_removed"], "cleanup should remove private values")
        assert_true(
            cleanup_status["cleanup"]["private_files_remaining_count"] == 0,
            "cleanup should leave no private files",
        )
        assert_true(not private_candidate_path.exists(), "private candidate should be removed")
        assert_true(not private_values_path.exists(), "private values should be removed")
        remaining_files = {path.name for path in out_dir.iterdir() if path.is_file()}
        assert_true(
            remaining_files == {STATUS_FILENAME, SUMMARY_FILENAME},
            "cleanup should preserve only status and summary",
        )
        cleanup_text = output_text(out_dir)
        for candidate in (source, private_values, private_candidate):
            for field, value in candidate.items():
                if field in NON_PRIVATE_METADATA_FIELDS:
                    continue
                if isinstance(value, str) and value:
                    for variant in forbidden_text_variants(value):
                        assert_true(variant not in cleanup_text, "cleanup output leaked private value")
        for marker in SENSITIVE_OUTPUT_MARKERS:
            assert_true(marker not in cleanup_text.lower(), f"cleanup output leaked marker {marker}")
        for name in (STATUS_FILENAME, SUMMARY_FILENAME):
            path = out_dir / name
            assert_true(path.exists(), f"{name} should remain after cleanup")
            assert_true(file_mode(path) == PRIVATE_FILE_MODE, f"{name} mode should be 600 after cleanup")

        write_private_json(private_values_path, private_values)
        rerun_status = run_preflight(
            str(source_path),
            str(private_values_path),
            str(out_dir),
            confirm_private_values_approved=True,
        )
        assert_true(rerun_status["result"] == "passed", "private handoff should pass after cleanup rerun")

        assert_raises_private_handoff(
            lambda: run_cleanup(
                str(private_values_path),
                str(out_dir),
                confirm_cleanup_private_artifacts=False,
            ),
            "cleanup without confirmation should fail",
        )

        assert_raises_private_handoff(
            lambda: run_preflight(
                str(source_path),
                str(private_values_path),
                str(root / "out-no-confirm"),
                confirm_private_values_approved=False,
            ),
            "missing human approval should fail",
        )
        assert_raises_private_handoff(
            lambda: run_preflight(
                str(root / "missing" / "candidate.json"),
                str(private_values_path),
                str(root / "out-missing-source"),
                confirm_private_values_approved=True,
            ),
            "missing source candidate should fail",
        )
        assert_raises_private_handoff(
            lambda: run_preflight(
                str(source_path),
                str(root / "missing" / "private-values.json"),
                str(root / "out-missing-private"),
                confirm_private_values_approved=True,
            ),
            "missing private values should fail",
        )
        assert_raises_private_handoff(
            lambda: run_preflight(
                str(source_path),
                str(private_values_path),
                "/var/tmp/dadooh-c8-6",
                confirm_private_values_approved=True,
            ),
            "out-dir outside /tmp should fail",
        )

        invalid_private = dict(private_values)
        del invalid_private["api_key"]
        invalid_private_path = root / "private" / "invalid-private-values.json"
        write_private_json(invalid_private_path, invalid_private)
        assert_raises_private_handoff(
            lambda: run_preflight(
                str(source_path),
                str(invalid_private_path),
                str(root / "out-invalid-private"),
                confirm_private_values_approved=True,
            ),
            "missing required private value should fail",
        )

        repo_private_dir = root / "fake-repo"
        (repo_private_dir / ".git").mkdir(parents=True)
        repo_private_path = repo_private_dir / "private-values.json"
        write_private_json(repo_private_path, private_values)
        assert_raises_private_handoff(
            lambda: run_preflight(
                str(source_path),
                str(repo_private_path),
                str(root / "out-repo-private"),
                confirm_private_values_approved=True,
            ),
            "private values inside repo should fail",
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run C8.6 controlled private setup -> writer handoff preflight under /tmp.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--source-candidate",
        default=DEFAULT_SOURCE_CANDIDATE,
        help=f"C8 source candidate under /tmp. Default: {DEFAULT_SOURCE_CANDIDATE}",
    )
    parser.add_argument(
        "--private-values",
        default=DEFAULT_PRIVATE_VALUES,
        help=f"Private values JSON under /tmp and outside Git. Default: {DEFAULT_PRIVATE_VALUES}",
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}",
    )
    parser.add_argument(
        "--confirm-private-values-approved",
        action="store_true",
        help="Confirm human approval to read private values for this preflight only.",
    )
    parser.add_argument(
        "--cleanup-private-artifacts",
        action="store_true",
        help="Remove candidate-private.json and private-values.json, preserving sanitized status/summary.",
    )
    parser.add_argument(
        "--confirm-cleanup-private-artifacts",
        action="store_true",
        help="Confirm removal of private temporary artifacts under /tmp.",
    )
    parser.add_argument("--self-test", action="store_true", help="Run local C8.6/C8.6.1 self-tests under /tmp and exit.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0

        if args.cleanup_private_artifacts:
            status = run_cleanup(
                args.private_values,
                args.out_dir,
                confirm_cleanup_private_artifacts=args.confirm_cleanup_private_artifacts,
            )
        else:
            status = run_preflight(
                args.source_candidate,
                args.private_values,
                args.out_dir,
                confirm_private_values_approved=args.confirm_private_values_approved,
            )
    except PrivateHandoffError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except AssertionError:
        print("error: self-test failed", file=sys.stderr)
        return 1
    except OSError:
        print("error: failed to write C8.6 artifacts", file=sys.stderr)
        return 1

    print(f"C8.6 private handoff artifacts generated under {args.out_dir}")
    if not args.cleanup_private_artifacts:
        print(PRIVATE_CANDIDATE_FILENAME)
    print(STATUS_FILENAME)
    print(SUMMARY_FILENAME)
    if args.cleanup_private_artifacts:
        print("cleanup: completed")
    else:
        print(f"real-dry-run: {'passed' if status['contract_validation']['private_real_dry_run']['valid'] else 'failed'}")
    print("writer-real: blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
