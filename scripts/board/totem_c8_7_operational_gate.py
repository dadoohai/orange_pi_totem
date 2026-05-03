#!/usr/bin/env python3
"""C8.7 final operational gate before real setup -> writer/config write.

This read-only gate inspects board metadata, writer guardrail readiness, and
the sanitized C8.6/C8.6.1 handoff state. It writes only /tmp artifacts, never
reads config contents, never writes /data or /opt, never calls the C6 writer in
real mode, and never changes service/player/network state.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import os
import pathlib
import pwd
import grp
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable


SCHEMA_VERSION = "dadooh-c8.7-operational-gate.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c8-7-operational-gate"
DEFAULT_C8_HANDOFF_OUT_DIR = "/tmp/dadooh-c8-6-handoff-preflight"
DEFAULT_PRIVATE_VALUES = "/tmp/dadooh-c8-6-private/private-values.json"
DEFAULT_WRITER_SCRIPT = "scripts/board/totem_config_writer_real.py"

STATUS_FILENAME = "operational-gate-status.json"
SUMMARY_FILENAME = "summary.txt"

TMP_ROOT = pathlib.Path("/tmp").resolve()
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
SERVICE_NAME = "kiosky-player.service"
ACTIVE_CONFIG_PATH = pathlib.Path("/data/config/config.json")
CONFIG_DIR = pathlib.Path("/data/config")
BACKUP_DIR = pathlib.Path("/data/config/backups")
APP_USER = "totem"
REAL_OWNER = "root"
REAL_GROUP = "totem"
WRITER_REQUIRED_TOKENS = (
    "--enable-real-write",
    "--confirm-service-stopped",
    "--confirm-human-approved-real-write",
    "/data/config/config.json",
    "/data/config/backups",
)
READ_ONLY_SYSTEMCTL_COMMANDS = (
    ("systemctl", "is-active", SERVICE_NAME),
    ("systemctl", "is-enabled", SERVICE_NAME),
)
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


class OperationalGateError(ValueError):
    """Raised for expected C8.7 gate failures."""


ServiceObserver = Callable[[], dict[str, Any]]
ProcessObserver = Callable[[], dict[str, Any]]


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


def require_tmp_dir(raw_path: str, label: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    raw_absolute = absolute_no_resolve(raw_path)
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise OperationalGateError(f"{label} must be under /tmp")

    resolved = path.resolve(strict=False)
    if not path_is_under(resolved, TMP_ROOT):
        raise OperationalGateError(f"{label} must resolve under /tmp")
    if resolved == TMP_ROOT:
        raise OperationalGateError(f"{label} must be a dedicated directory under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise OperationalGateError(f"{label} exists and is not a directory")
    return resolved


def normalize_tmp_path(raw_path: str, label: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    raw_absolute = absolute_no_resolve(raw_path)
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise OperationalGateError(f"{label} must be under /tmp")
    return path.resolve(strict=False)


def prepare_private_dir(path: pathlib.Path) -> None:
    path.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    if stat.S_IMODE(path.stat().st_mode) != PRIVATE_DIR_MODE:
        path.chmod(PRIVATE_DIR_MODE)


def ensure_output_target(path: pathlib.Path, out_dir: pathlib.Path) -> None:
    resolved_out = out_dir.resolve(strict=True)
    resolved_target = path.resolve(strict=False)
    if not path_is_under(resolved_target, resolved_out):
        raise OperationalGateError("output target escaped out-dir")
    if resolved_target == resolved_out:
        raise OperationalGateError("output target must be a file")
    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt")):
        if path_is_under(resolved_target, forbidden):
            raise OperationalGateError("refusing to write outside /tmp")


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
        raise OperationalGateError(f"{label} is not valid JSON") from exc
    except OSError as exc:
        raise OperationalGateError(f"{label} could not be read") from exc
    if not isinstance(value, dict):
        raise OperationalGateError(f"{label} JSON root must be an object")
    return value


def mode_string(mode: int) -> str:
    return oct(stat.S_IMODE(mode))


def owner_name(uid: int) -> str:
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return "unknown"


def group_name(gid: int) -> str:
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return "unknown"


def file_type_from_mode(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symlink"
    return "other"


def inspect_path_metadata(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        st = path.lstat()
    except FileNotFoundError:
        return {
            "label": label,
            "exists": False,
            "type": "missing",
            "mode": "missing",
            "owner": "missing",
            "group": "missing",
            "content_read": False,
            "raw_path_written": False,
            "symlink": False,
        }
    except OSError:
        return {
            "label": label,
            "exists": False,
            "type": "unavailable",
            "mode": "unavailable",
            "owner": "unavailable",
            "group": "unavailable",
            "content_read": False,
            "raw_path_written": False,
            "symlink": False,
        }

    return {
        "label": label,
        "exists": True,
        "type": file_type_from_mode(st.st_mode),
        "mode": mode_string(st.st_mode),
        "owner": owner_name(st.st_uid),
        "group": group_name(st.st_gid),
        "content_read": False,
        "raw_path_written": False,
        "symlink": stat.S_ISLNK(st.st_mode),
    }


def user_exists(name: str) -> bool:
    try:
        pwd.getpwnam(name)
    except KeyError:
        return False
    return True


def group_exists(name: str) -> bool:
    try:
        grp.getgrnam(name)
    except KeyError:
        return False
    return True


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
        raise OperationalGateError("systemctl command outside read-only allowlist")
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

    return {
        "available": True,
        "state": normalize_systemctl_state(completed.stdout),
        "returncode_category": "zero" if completed.returncode == 0 else "nonzero",
    }


def observe_service() -> dict[str, Any]:
    active = run_read_only_systemctl(("systemctl", "is-active", SERVICE_NAME))
    enabled = run_read_only_systemctl(("systemctl", "is-enabled", SERVICE_NAME))
    return {
        "name": SERVICE_NAME,
        "read_only_observed": bool(active["available"] or enabled["available"]),
        "active_state": active["state"],
        "enabled_state": enabled["state"],
        "stop_or_start_called": False,
        "state_change_command_called": False,
    }


def process_matches(label: str, cmdline: str) -> str | None:
    combined = f"{label} {cmdline}".lower()
    if "mpv" in combined:
        return "mpv"
    if "kiosk.py" in combined or "kiosky-player" in combined:
        return "kiosky_player"
    return None


def observe_processes() -> dict[str, Any]:
    counts = {"kiosky_player": 0, "mpv": 0}
    try:
        entries = list(pathlib.Path("/proc").iterdir())
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
    return {"observed": True, "counts": counts, "total_relevant_processes": sum(counts.values())}


def inspect_board_metadata(
    *,
    service_observer: ServiceObserver,
    process_observer: ProcessObserver,
) -> dict[str, Any]:
    config_dir = inspect_path_metadata(CONFIG_DIR, "config_dir")
    active_config = inspect_path_metadata(ACTIVE_CONFIG_PATH, "active_config")
    backup_dir = inspect_path_metadata(BACKUP_DIR, "backup_dir")
    data_root = inspect_path_metadata(pathlib.Path("/data"), "data_root")

    backup_ready = bool(backup_dir["exists"] and backup_dir["type"] == "directory")
    backup_can_be_created = bool(
        not backup_dir["exists"]
        and config_dir["exists"]
        and config_dir["type"] == "directory"
        and group_exists(REAL_GROUP)
        and user_exists(REAL_OWNER)
    )

    return {
        "service": service_observer(),
        "processes": process_observer(),
        "paths": {
            "data_root": data_root,
            "config_dir": config_dir,
            "active_config": active_config,
            "backup_dir": backup_dir,
        },
        "identity": {
            "app_user_exists": user_exists(APP_USER),
            "real_owner_exists": user_exists(REAL_OWNER),
            "real_group_exists": group_exists(REAL_GROUP),
        },
        "backup": {
            "backup_dir_ready": backup_ready,
            "backup_dir_can_be_created_by_writer": backup_can_be_created,
            "backup_content_read": False,
        },
        "config_content_read": False,
        "data_written": False,
        "opt_written": False,
    }


def inspect_writer_readiness(writer_script_raw: str, writer_self_test_status: str) -> dict[str, Any]:
    path = pathlib.Path(writer_script_raw).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        return {
            "script_present": False,
            "script_read": False,
            "required_real_mode_flags_present": False,
            "self_test_status": writer_self_test_status,
            "ready": False,
        }
    if not resolved.is_file():
        return {
            "script_present": False,
            "script_read": False,
            "required_real_mode_flags_present": False,
            "self_test_status": writer_self_test_status,
            "ready": False,
        }
    try:
        content = resolved.read_text(encoding="utf-8")
    except OSError:
        content = ""
    required_tokens_present = all(token in content for token in WRITER_REQUIRED_TOKENS)
    return {
        "script_present": True,
        "script_read": True,
        "required_real_mode_flags_present": required_tokens_present,
        "self_test_status": writer_self_test_status,
        "ready": required_tokens_present and writer_self_test_status == "passed",
        "writer_real_mode_called": False,
        "enable_real_write_used": False,
        "raw_script_path_written": False,
    }


def inspect_c8_private_handoff(c8_handoff_out_dir_raw: str, private_values_raw: str) -> dict[str, Any]:
    out_dir = normalize_tmp_path(c8_handoff_out_dir_raw, "C8.6 handoff out-dir")
    private_values = normalize_tmp_path(private_values_raw, "private values")
    status_path = out_dir / "handoff-preflight-status.json"
    private_candidate = out_dir / "candidate-private.json"
    status_present = status_path.exists()
    cleanup_schema = False
    cleanup_executed = False
    private_real_dry_run_passed = False
    writer_blocked = False
    private_files_remaining_count = 2

    if status_present:
        try:
            status = load_json_object(status_path, "C8.6 cleanup status")
        except OperationalGateError:
            status = {}
        cleanup_schema = status.get("schema_version") == "dadooh-c8.6.1-private-handoff-cleanup.v1"
        cleanup = status.get("cleanup", {})
        previous = status.get("previous_preflight", {})
        writer_handoff = status.get("writer_handoff", {})
        cleanup_executed = bool(cleanup.get("executed"))
        private_real_dry_run_passed = bool(previous.get("private_real_dry_run_passed"))
        writer_blocked = bool(writer_handoff.get("writer_real_write_blocked"))
        raw_count = cleanup.get("private_files_remaining_count")
        if isinstance(raw_count, int):
            private_files_remaining_count = raw_count

    private_candidate_exists = private_candidate.exists()
    private_values_exists = private_values.exists()
    if not private_candidate_exists and not private_values_exists:
        private_files_remaining_count = 0

    return {
        "status_present": status_present,
        "cleanup_schema_valid": cleanup_schema,
        "cleanup_executed": cleanup_executed,
        "private_real_dry_run_passed_before_cleanup": private_real_dry_run_passed,
        "writer_real_write_blocked": writer_blocked,
        "private_candidate_remaining": private_candidate_exists,
        "private_input_remaining": private_values_exists,
        "private_files_remaining_count": private_files_remaining_count,
        "status_content_copied": False,
        "private_values_read": False,
        "private_candidate_read": False,
    }


def build_go_no_go(board: dict[str, Any], writer: dict[str, Any], handoff: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    mandatory_next_actions = [
        "obter aprovacao humana explicita para escrita real",
        "preparar candidata privada real sob /tmp fora do repo",
        "parar ou bloquear kiosky-player.service e confirmar inactive",
        "executar writer C6 com flags completas somente na rodada real aprovada",
        "preservar backup/rollback e evidencia sanitizada",
    ]

    paths = board["paths"]
    identity = board["identity"]
    service = board["service"]

    if not writer["ready"]:
        blockers.append("writer_c6_guardrails_not_confirmed")
    if not handoff["cleanup_schema_valid"] or not handoff["cleanup_executed"]:
        blockers.append("c8_6_cleanup_not_confirmed")
    if not handoff["private_real_dry_run_passed_before_cleanup"]:
        blockers.append("c8_6_private_real_dry_run_not_confirmed")
    if handoff["private_files_remaining_count"] != 0:
        blockers.append("private_temp_files_remaining")
    if not paths["config_dir"]["exists"] or paths["config_dir"]["type"] != "directory":
        blockers.append("real_config_parent_missing")
    if not identity["real_owner_exists"] or not identity["real_group_exists"]:
        blockers.append("real_owner_or_group_missing")
    if not identity["app_user_exists"]:
        warnings.append("app_user_not_observed")
    if not paths["active_config"]["exists"]:
        warnings.append("active_config_absent_first_write_has_no_previous_config_backup")
    if not board["backup"]["backup_dir_ready"] and not board["backup"]["backup_dir_can_be_created_by_writer"]:
        blockers.append("backup_dir_not_ready_and_not_creatable_by_writer")
    if service["active_state"] == "active":
        warnings.append("service_currently_active_must_be_stopped_in_real_write_round")

    return {
        "decision": "go_for_next_real_write_round" if not blockers else "no_go_until_blockers_resolved",
        "next_round_can_be_first_real_write_attempt": not blockers,
        "immediate_real_write_allowed_now": False,
        "blockers": blockers,
        "warnings": warnings,
        "mandatory_next_actions": mandatory_next_actions,
        "human_approval_still_required": True,
        "service_stop_still_required": True,
        "real_write_executed": False,
    }


def build_status(
    *,
    generated_at: str,
    board: dict[str, Any],
    writer: dict[str, Any],
    handoff: dict[str, Any],
) -> dict[str, Any]:
    go_no_go = build_go_no_go(board, writer, handoff)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "result": "passed",
        "phase": "operational_gate_completed",
        "board_read_only_inspection": board,
        "writer_readiness": writer,
        "c8_private_handoff": handoff,
        "go_no_go": go_no_go,
        "future_real_execution": {
            "script": "totem_config_writer_real.py",
            "candidate_must_be_private_tmp": True,
            "dest_exact_match_required": True,
            "backup_dir_exact_match_required": True,
            "flags_required_count": 3,
            "service_must_be_stopped_or_blocked": True,
            "human_approval_required": True,
            "cleanup_after_preflight_required": True,
            "evidence_must_be_sanitized": True,
        },
        "guardrails": {
            "writes_only_under_tmp": True,
            "real_config_content_read": False,
            "backup_content_read": False,
            "data_written": False,
            "opt_written": False,
            "writer_real_mode_called": False,
            "enable_real_write_used": False,
            "systemctl_read_only_called": True,
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
            "private_values_read": False,
            "private_values_copied_to_status": False,
            "private_values_copied_to_summary": False,
            "candidate_private_read": False,
            "candidate_private_copied_to_status": False,
            "candidate_private_copied_to_summary": False,
            "active_config_content_read": False,
            "active_config_content_copied": False,
            "backup_content_read": False,
            "backup_content_copied": False,
            "raw_service_output_written": False,
            "raw_process_output_written": False,
        },
        "artifacts": {
            "status": STATUS_FILENAME,
            "summary": SUMMARY_FILENAME,
        },
    }


def build_summary(status: dict[str, Any]) -> str:
    board = status["board_read_only_inspection"]
    writer = status["writer_readiness"]
    handoff = status["c8_private_handoff"]
    go_no_go = status["go_no_go"]
    paths = board["paths"]
    return "\n".join(
        [
            "Dadooh C8.7 operational gate",
            "",
            f"schema_version: {status['schema_version']}",
            f"generated_at_utc: {status['generated_at_utc']}",
            f"result: {status['result']}",
            f"phase: {status['phase']}",
            f"decision: {go_no_go['decision']}",
            f"next_round_can_be_first_real_write_attempt: {str(go_no_go['next_round_can_be_first_real_write_attempt']).lower()}",
            "immediate_real_write_allowed_now: false",
            f"blockers_count: {len(go_no_go['blockers'])}",
            f"warnings_count: {len(go_no_go['warnings'])}",
            f"service_active_state_category: {board['service']['active_state']}",
            f"service_enabled_state_category: {board['service']['enabled_state']}",
            f"player_relevant_processes_count: {board['processes']['total_relevant_processes']}",
            f"config_dir_exists: {str(paths['config_dir']['exists']).lower()}",
            f"active_config_exists: {str(paths['active_config']['exists']).lower()}",
            f"active_config_type: {paths['active_config']['type']}",
            f"active_config_mode: {paths['active_config']['mode']}",
            f"active_config_owner: {paths['active_config']['owner']}",
            f"active_config_group: {paths['active_config']['group']}",
            f"backup_dir_exists: {str(paths['backup_dir']['exists']).lower()}",
            f"backup_dir_ready: {str(board['backup']['backup_dir_ready']).lower()}",
            "backup_dir_can_be_created_by_writer: "
            f"{str(board['backup']['backup_dir_can_be_created_by_writer']).lower()}",
            f"writer_guardrails_ready: {str(writer['ready']).lower()}",
            f"writer_self_test_status: {writer['self_test_status']}",
            f"c8_private_real_dry_run_passed_before_cleanup: {str(handoff['private_real_dry_run_passed_before_cleanup']).lower()}",
            f"c8_cleanup_executed: {str(handoff['cleanup_executed']).lower()}",
            f"private_files_remaining_count: {handoff['private_files_remaining_count']}",
            "",
            "Guardrails:",
            "writes_only_under_tmp: true",
            "real_config_content_read: false",
            "backup_content_read: false",
            "data_written: false",
            "opt_written: false",
            "writer_real_mode_called: false",
            "enable_real_write_used: false",
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
            "private_values_read: false",
            "candidate_private_read: false",
            "active_config_content_read: false",
            "backup_content_read: false",
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


def assert_sanitized_outputs(out_dir: pathlib.Path) -> None:
    text = output_text(out_dir)
    for marker in SENSITIVE_OUTPUT_MARKERS:
        if marker in text.lower():
            raise OperationalGateError("privacy scan blocked sensitive marker in operational gate output")


def write_outputs(out_dir: pathlib.Path, status: dict[str, Any]) -> None:
    prepare_private_dir(out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_summary(status), out_dir)
    assert_sanitized_outputs(out_dir)


def run_gate(
    *,
    out_dir_raw: str,
    c8_handoff_out_dir_raw: str,
    private_values_raw: str,
    writer_script_raw: str,
    writer_self_test_status: str,
    service_observer: ServiceObserver = observe_service,
    process_observer: ProcessObserver = observe_processes,
) -> dict[str, Any]:
    out_dir = require_tmp_dir(out_dir_raw, "out-dir")
    if writer_self_test_status not in {"passed", "failed", "not-run"}:
        raise OperationalGateError("writer self-test status must be passed, failed, or not-run")
    board = inspect_board_metadata(service_observer=service_observer, process_observer=process_observer)
    writer = inspect_writer_readiness(writer_script_raw, writer_self_test_status)
    handoff = inspect_c8_private_handoff(c8_handoff_out_dir_raw, private_values_raw)
    status = build_status(generated_at=utc_timestamp(), board=board, writer=writer, handoff=handoff)
    write_outputs(out_dir, status)
    return status


def file_mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def write_private_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    prepare_private_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")
    path.chmod(PRIVATE_FILE_MODE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_raises_gate(fn: Any, message: str) -> None:
    try:
        fn()
    except OperationalGateError:
        return
    raise AssertionError(message)


def fake_service_observer() -> dict[str, Any]:
    return {
        "name": SERVICE_NAME,
        "read_only_observed": True,
        "active_state": "inactive",
        "enabled_state": "enabled",
        "stop_or_start_called": False,
        "state_change_command_called": False,
    }


def fake_process_observer() -> dict[str, Any]:
    return {
        "observed": True,
        "counts": {"kiosky_player": 0, "mpv": 0},
        "total_relevant_processes": 0,
    }


def run_self_test() -> None:
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c8-7-operational-gate-self-test-", dir="/tmp"))
    try:
        handoff_out = root / "handoff"
        private_dir = root / "private"
        writer_script = root / "writer" / "totem_config_writer_real.py"
        out_dir = root / "out"
        prepare_private_dir(handoff_out)
        prepare_private_dir(private_dir)
        prepare_private_dir(writer_script.parent)
        cleanup_status = {
            "schema_version": "dadooh-c8.6.1-private-handoff-cleanup.v1",
            "cleanup": {"executed": True, "private_files_remaining_count": 0},
            "previous_preflight": {"private_real_dry_run_passed": True},
            "writer_handoff": {"writer_real_write_blocked": True},
        }
        write_private_json(handoff_out / "handoff-preflight-status.json", cleanup_status)
        writer_script.write_text("\n".join(WRITER_REQUIRED_TOKENS) + "\n", encoding="utf-8")
        writer_script.chmod(PRIVATE_FILE_MODE)

        status = run_gate(
            out_dir_raw=str(out_dir),
            c8_handoff_out_dir_raw=str(handoff_out),
            private_values_raw=str(private_dir / "private-values.json"),
            writer_script_raw=str(writer_script),
            writer_self_test_status="passed",
            service_observer=fake_service_observer,
            process_observer=fake_process_observer,
        )
        assert_true(status["result"] == "passed", "gate should pass")
        assert_true(status["writer_readiness"]["ready"], "writer should be marked ready")
        assert_true(status["c8_private_handoff"]["cleanup_executed"], "C8 cleanup should be observed")
        assert_true(
            status["c8_private_handoff"]["private_files_remaining_count"] == 0,
            "private files should be absent",
        )
        assert_true(not status["go_no_go"]["immediate_real_write_allowed_now"], "immediate real write should be false")
        assert_true(file_mode(out_dir) == PRIVATE_DIR_MODE, "out-dir mode should be 700")
        for name in (STATUS_FILENAME, SUMMARY_FILENAME):
            path = out_dir / name
            assert_true(path.exists(), f"{name} should exist")
            assert_true(file_mode(path) == PRIVATE_FILE_MODE, f"{name} mode should be 600")
            text = path.read_text(encoding="utf-8")
            for marker in SENSITIVE_OUTPUT_MARKERS:
                assert_true(marker not in text.lower(), f"{name} leaked marker {marker}")
        for key in (
            "real_config_content_read",
            "backup_content_read",
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

        assert_raises_gate(
            lambda: run_gate(
                out_dir_raw="/var/tmp/dadooh-c8-7",
                c8_handoff_out_dir_raw=str(handoff_out),
                private_values_raw=str(private_dir / "private-values.json"),
                writer_script_raw=str(writer_script),
                writer_self_test_status="passed",
                service_observer=fake_service_observer,
                process_observer=fake_process_observer,
            ),
            "out-dir outside /tmp should fail",
        )
        missing_writer_status = run_gate(
            out_dir_raw=str(root / "out-missing-writer"),
            c8_handoff_out_dir_raw=str(handoff_out),
            private_values_raw=str(private_dir / "private-values.json"),
            writer_script_raw=str(root / "missing-writer.py"),
            writer_self_test_status="passed",
            service_observer=fake_service_observer,
            process_observer=fake_process_observer,
        )
        assert_true(not missing_writer_status["writer_readiness"]["ready"], "missing writer should not be ready")
        assert_true(
            "writer_c6_guardrails_not_confirmed" in missing_writer_status["go_no_go"]["blockers"],
            "missing writer should be a blocker",
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run C8.7 read-only operational gate before real setup -> writer/config write.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}",
    )
    parser.add_argument(
        "--c8-handoff-out-dir",
        default=DEFAULT_C8_HANDOFF_OUT_DIR,
        help=f"C8.6 handoff out-dir under /tmp. Default: {DEFAULT_C8_HANDOFF_OUT_DIR}",
    )
    parser.add_argument(
        "--private-values",
        default=DEFAULT_PRIVATE_VALUES,
        help=f"Private values path to confirm cleanup. Default: {DEFAULT_PRIVATE_VALUES}",
    )
    parser.add_argument(
        "--writer-script",
        default=DEFAULT_WRITER_SCRIPT,
        help=f"C6 writer script path to inspect. Default: {DEFAULT_WRITER_SCRIPT}",
    )
    parser.add_argument(
        "--writer-self-test-status",
        choices=("passed", "failed", "not-run"),
        default="not-run",
        help="Result of a separate writer self-test. The gate does not call writer real mode.",
    )
    parser.add_argument("--self-test", action="store_true", help="Run local C8.7 self-tests under /tmp and exit.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0
        status = run_gate(
            out_dir_raw=args.out_dir,
            c8_handoff_out_dir_raw=args.c8_handoff_out_dir,
            private_values_raw=args.private_values,
            writer_script_raw=args.writer_script,
            writer_self_test_status=args.writer_self_test_status,
        )
    except OperationalGateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except AssertionError:
        print("error: self-test failed", file=sys.stderr)
        return 1
    except OSError:
        print("error: failed to write C8.7 artifacts", file=sys.stderr)
        return 1

    print(f"C8.7 operational gate artifacts generated under {args.out_dir}")
    print(STATUS_FILENAME)
    print(SUMMARY_FILENAME)
    print(f"decision: {status['go_no_go']['decision']}")
    print("real-write: not-executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
