#!/usr/bin/env python3
"""C6.2/C6.2.2 guarded real config writer.

This is the first reusable writer shape for the real config flow, but C6.2 is
deliberately constrained to /tmp. It validates a local candidate with the C5.1
real-dry-run contract, writes the active config atomically to a simulated
destination, creates a restricted backup when replacing an existing config, and
rolls back on critical post-write failure.

C6.2.2 adds guarded support for a future real destination. Real writes require
multiple explicit flags and only allow /data/config/config.json with a restricted
backup directory. The self-test still writes only under /tmp.

It never accesses the network, never calls systemctl/nmcli/MPV, and never prints
the api_key/token value.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import grp
import json
import os
import pathlib
import pwd
import re
import secrets
import shutil
import socket
import stat
import sys
import tempfile
import urllib.parse as urllib_parse
import uuid
from dataclasses import dataclass
from typing import Any

sys.dont_write_bytecode = True

import totem_config_contract_validate as contract


SCHEMA_VERSION = "dadooh-c6.2.2-config-writer-real-guardrails.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c6-config-writer-real-sim"

STATUS_FILENAME = "writer-status.json"
SUMMARY_FILENAME = "summary.txt"

ACTIVE_CONFIG_MODE = 0o600
REAL_ACTIVE_CONFIG_MODE = 0o640
PRIVATE_FILE_MODE = 0o600
PRIVATE_DIR_MODE = 0o700

FORBIDDEN_CANDIDATE_ROOTS = (pathlib.Path("/data"), pathlib.Path("/opt"))
FORBIDDEN_REAL_CANDIDATE_ROOTS = (
    pathlib.Path("/data"),
    pathlib.Path("/opt"),
    pathlib.Path("/home"),
)
TMP_ROOT = pathlib.Path("/tmp").resolve()
REAL_DEST_PATH = pathlib.Path("/data/config/config.json")
REAL_BACKUP_DIR = pathlib.Path("/data/config/backups")
REAL_FILE_OWNER = "root"
REAL_FILE_GROUP = "totem"

PRODUCT_RESET_SCHEMA_VERSION = "dadooh-c26a-product-reset.v1"
PRODUCT_RESET_STATE_REL = pathlib.Path("state/totem-appliance/product-reset")
PRODUCT_RESET_GRAVEYARD_REL = PRODUCT_RESET_STATE_REL / "graveyard"
PRODUCT_RESET_INTENT_FILENAME = "intent.json"
PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME = "pending-credential.json"
PRODUCT_RESET_RECEIPT_FILENAME = "receipt.json"
PRODUCT_RESET_GC_PENDING_FILENAME = "gc-pending.json"
PRODUCT_RESET_HOMOLOGATION_SEED_DISABLED_FILENAME = "homologation-seed-disabled.json"
PRODUCT_RESET_RECREATE_MODE = 0o750
PRODUCT_RESET_CONFIG_FILE_MODE = REAL_ACTIVE_CONFIG_MODE
PRODUCT_RESET_CONFIG_SCAN_MAX_ENTRIES = 4096
PRODUCT_RESET_REAL_OWNER = "totem"
PRODUCT_RESET_REAL_GROUP = "totem"
PRODUCT_RESET_REAL_DATA_ROOT = pathlib.Path("/data")
PRODUCT_RESET_FIXED_DOMAINS = (
    pathlib.Path("config"),
    pathlib.Path("media/kiosky-player"),
    pathlib.Path("state/kiosky-player"),
    pathlib.Path("spool/kiosky-player"),
    pathlib.Path("logs/kiosky-player"),
)
PRODUCT_RESET_LAST_SETTINGS_REL = pathlib.Path("state/totem-settings/last-settings.json")
PRODUCT_RESET_HOMOLOGATION_SEED_REL = pathlib.Path(
    "state/totem-settings/private-values.seed.json"
)
PRODUCT_RESET_FINALIZE_RESULTS = ("revoked", "not_device_activation")
PRODUCT_RESET_ACTIONS = (
    "start",
    "resume",
    "reconcile",
    "status",
    "finalize-after-revocation",
    "complete-onboarding",
    "gc",
)
PRODUCT_RESET_FAULT_PHASES = (
    "state_prepared",
    "credential_written",
    "intent_written",
    "graveyard_prepared",
    "homologation_seed_delete_prepared",
    "homologation_seed_disabled_marker_written",
    "homologation_seed_removed",
    "config_moved",
    "config_recreated",
    "media_kiosky_player_moved",
    "media_kiosky_player_recreated",
    "state_kiosky_player_moved",
    "state_kiosky_player_recreated",
    "spool_kiosky_player_moved",
    "spool_kiosky_player_recreated",
    "logs_kiosky_player_moved",
    "logs_kiosky_player_recreated",
    "last_settings_moved",
    "local_complete",
)
PRODUCT_RESET_FINALIZE_FAULT_PHASES = (
    "receipt_written",
    "credential_unlinked",
    "intent_unlinked",
)
PRODUCT_RESET_ONBOARDING_FAULT_PHASES = (
    "gc_pending_written",
    "onboarding_receipt_unlinked",
)
PRODUCT_RESET_GC_FAULT_PHASES = (
    "gc_graveyard_removed",
    "gc_pending_unlinked",
)
PRODUCT_RESET_INTENT_PHASES = frozenset(
    (
        "intent_written",
        "homologation_seed_delete_prepared",
        "homologation_seed_disabled_marker_written",
        "homologation_seed_removed",
        "config_moved",
        "config_recreated",
        "media_kiosky_player_moved",
        "media_kiosky_player_recreated",
        "state_kiosky_player_moved",
        "state_kiosky_player_recreated",
        "spool_kiosky_player_moved",
        "spool_kiosky_player_recreated",
        "logs_kiosky_player_moved",
        "logs_kiosky_player_recreated",
        "last_settings_moved",
        "local_complete",
    )
)


class WriterError(ValueError):
    """Raised for expected C6.2 writer failures."""


@dataclass(frozen=True)
class WriterPaths:
    candidate: pathlib.Path
    dest: pathlib.Path
    backup_dir: pathlib.Path
    out_dir: pathlib.Path
    real_write_enabled: bool


@dataclass(frozen=True)
class ProductResetContext:
    data_root: pathlib.Path
    allow_test_root: bool
    owner_uid: int
    owner_gid: int
    owner_applier: Any | None = None
    fingerprint_provider: Any | None = None
    fault_after: str | None = None


def utc_timestamp() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def backup_timestamp() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def path_is_under(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def absolute_no_resolve(raw_path: str) -> pathlib.Path:
    return pathlib.Path(os.path.abspath(str(pathlib.Path(raw_path).expanduser())))


def reject_raw_forbidden_path(raw_path: str, label: str) -> None:
    raw = pathlib.Path(raw_path).expanduser()
    if not raw.is_absolute():
        return
    absolute = absolute_no_resolve(raw_path)
    for root in FORBIDDEN_CANDIDATE_ROOTS:
        if path_is_under(absolute, root):
            raise WriterError(f"refusing {label} under {root}")


def require_tmp_dir(raw_path: str, label: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    raw_absolute = absolute_no_resolve(raw_path)
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise WriterError(f"{label} must be under /tmp")

    resolved = path.resolve(strict=False)

    if not path_is_under(resolved, TMP_ROOT):
        raise WriterError(f"{label} must be under /tmp")
    if resolved == TMP_ROOT:
        raise WriterError(f"{label} must be a dedicated directory under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise WriterError(f"{label} exists and is not a directory")
    return resolved


def require_tmp_file(raw_path: str, label: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    raw_absolute = absolute_no_resolve(raw_path)
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise WriterError(f"{label} must be under /tmp")

    resolved = path.resolve(strict=False)

    if not path_is_under(resolved, TMP_ROOT):
        raise WriterError(f"{label} must be under /tmp")
    if resolved == TMP_ROOT:
        raise WriterError(f"{label} must be a file under /tmp")
    if resolved.exists() and resolved.is_dir():
        raise WriterError(f"{label} exists and is a directory")
    return resolved


def normalize_candidate_path(raw_path: str) -> pathlib.Path:
    reject_raw_forbidden_path(raw_path, "candidate")
    path = pathlib.Path(raw_path).expanduser()
    resolved = path.resolve(strict=False)

    for root in FORBIDDEN_CANDIDATE_ROOTS:
        if path_is_under(resolved, root):
            raise WriterError(f"refusing candidate under {root}")

    try:
        strict_resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise WriterError("candidate file not found") from exc

    for root in FORBIDDEN_CANDIDATE_ROOTS:
        if path_is_under(strict_resolved, root):
            raise WriterError(f"refusing candidate under {root}")

    if not strict_resolved.is_file():
        raise WriterError("candidate must be a file")
    return strict_resolved


def path_is_in_repository(path: pathlib.Path) -> bool:
    current = path if path.is_dir() else path.parent
    for candidate in (current, *current.parents):
        # Release/test workspaces may leave /tmp/.git behind. Real candidates
        # are required to live under /tmp, so only nested repo markers matter.
        if candidate == TMP_ROOT:
            continue
        if (candidate / ".git").exists():
            return True
    return False


def normalize_real_candidate_path(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    if not path.is_absolute():
        raise WriterError("real candidate path must be absolute")

    raw_absolute = absolute_no_resolve(raw_path)
    for root in FORBIDDEN_REAL_CANDIDATE_ROOTS:
        if path_is_under(raw_absolute, root):
            raise WriterError(f"refusing real candidate under {root}")
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise WriterError("real candidate must be under /tmp")

    try:
        strict_resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise WriterError("candidate file not found") from exc

    for root in FORBIDDEN_REAL_CANDIDATE_ROOTS:
        if path_is_under(strict_resolved, root):
            raise WriterError(f"refusing real candidate under {root}")
    if not path_is_under(strict_resolved, TMP_ROOT):
        raise WriterError("real candidate must resolve under /tmp")
    if path_is_in_repository(strict_resolved):
        raise WriterError("refusing real candidate inside repository")
    if not strict_resolved.is_file():
        raise WriterError("candidate must be a file")
    return strict_resolved


def normalize_exact_real_path(
    raw_path: str,
    expected: pathlib.Path,
    label: str,
    *,
    check_symlinks: bool,
) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    if not path.is_absolute():
        raise WriterError(f"{label} must be an absolute path")

    raw_absolute = pathlib.Path(os.path.normpath(os.path.abspath(str(path))))
    if raw_absolute != expected:
        raise WriterError(f"{label} must be {expected}")

    if check_symlinks:
        resolved = path.resolve(strict=False)
        if resolved != expected:
            raise WriterError(f"{label} symlink escapes approved path")

    return expected


def real_flags_complete(
    *,
    enable_real_write: bool,
    confirm_service_stopped: bool,
    confirm_human_approved_real_write: bool,
) -> bool:
    return enable_real_write and confirm_service_stopped and confirm_human_approved_real_write


def validate_writer_paths(
    *,
    candidate_raw: str,
    dest_raw: str,
    backup_dir_raw: str | None,
    out_dir_raw: str,
    enable_real_write: bool = False,
    confirm_service_stopped: bool = False,
    confirm_human_approved_real_write: bool = False,
    check_real_symlinks: bool = True,
) -> WriterPaths:
    out_dir = require_tmp_dir(out_dir_raw, "out-dir")
    real_flag_values = (enable_real_write, confirm_service_stopped, confirm_human_approved_real_write)
    any_real_flag = any(real_flag_values)
    real_write = real_flags_complete(
        enable_real_write=enable_real_write,
        confirm_service_stopped=confirm_service_stopped,
        confirm_human_approved_real_write=confirm_human_approved_real_write,
    )

    if any_real_flag and not real_write:
        raise WriterError(
            "real write requires --enable-real-write, --confirm-service-stopped, "
            "and --confirm-human-approved-real-write"
        )

    if real_write:
        candidate_path = normalize_real_candidate_path(candidate_raw)
        dest = normalize_exact_real_path(dest_raw, REAL_DEST_PATH, "dest", check_symlinks=check_real_symlinks)
        backup_dir = normalize_exact_real_path(
            backup_dir_raw or str(REAL_BACKUP_DIR),
            REAL_BACKUP_DIR,
            "backup-dir",
            check_symlinks=check_real_symlinks,
        )
        return WriterPaths(
            candidate=candidate_path,
            dest=dest,
            backup_dir=backup_dir,
            out_dir=out_dir,
            real_write_enabled=True,
        )

    candidate_path = normalize_candidate_path(candidate_raw)
    dest = require_tmp_file(dest_raw, "dest")
    backup_dir = require_tmp_dir(backup_dir_raw, "backup-dir") if backup_dir_raw else require_tmp_dir(
        str(dest.parent / "backups"),
        "backup-dir",
    )
    return WriterPaths(
        candidate=candidate_path,
        dest=dest,
        backup_dir=backup_dir,
        out_dir=out_dir,
        real_write_enabled=False,
    )


def prepare_private_dir(path: pathlib.Path) -> None:
    path.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    if stat.S_IMODE(path.stat().st_mode) != PRIVATE_DIR_MODE:
        path.chmod(PRIVATE_DIR_MODE)


def apply_real_ownership(path: pathlib.Path) -> None:
    try:
        shutil.chown(path, user=REAL_FILE_OWNER, group=REAL_FILE_GROUP)
    except (LookupError, OSError) as exc:
        raise WriterError("could not apply real owner/group root:totem") from exc


def apply_mode_and_owner(path: pathlib.Path, mode: int, *, real_write_enabled: bool) -> None:
    if real_write_enabled:
        apply_real_ownership(path)
    path.chmod(mode)


def prepare_active_parent(dest: pathlib.Path, *, real_write_enabled: bool) -> None:
    if not real_write_enabled:
        prepare_private_dir(dest.parent)
        return

    if not dest.parent.exists():
        raise WriterError("real dest parent must already exist")
    if not dest.parent.is_dir():
        raise WriterError("real dest parent is not a directory")
    if dest.parent.is_symlink():
        raise WriterError("real dest parent must not be a symlink")


def prepare_backup_dir(path: pathlib.Path, *, real_write_enabled: bool) -> None:
    if not real_write_enabled:
        prepare_private_dir(path)
        return

    if path.exists() and not path.is_dir():
        raise WriterError("real backup-dir exists and is not a directory")
    path.mkdir(mode=PRIVATE_DIR_MODE, parents=False, exist_ok=True)
    apply_mode_and_owner(path, PRIVATE_DIR_MODE, real_write_enabled=True)
    fsync_directory(path.parent)


def fsync_directory(path: pathlib.Path, *, required: bool = False) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if required:
            raise WriterError("product_reset_directory_fsync_failed") from exc
        return
    try:
        try:
            os.fsync(fd)
        except OSError as exc:
            if required:
                raise WriterError("product_reset_directory_fsync_failed") from exc
            raise
    finally:
        os.close(fd)


def ensure_output_target(path: pathlib.Path, out_dir: pathlib.Path) -> None:
    resolved_out = out_dir.resolve(strict=True)
    resolved_target = path.resolve(strict=False)
    if not path_is_under(resolved_target, resolved_out):
        raise WriterError("output target escaped out-dir")
    if resolved_target == resolved_out:
        raise WriterError("output target must be a file")


def atomic_write_text(path: pathlib.Path, content: str, out_dir: pathlib.Path) -> None:
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


def atomic_write_json(path: pathlib.Path, value: dict[str, Any], out_dir: pathlib.Path) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True), out_dir)


def load_json_file(path: pathlib.Path, *, label: str) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError as exc:
        raise WriterError(f"{label} is not valid JSON") from exc
    except OSError as exc:
        raise WriterError(f"{label} could not be read") from exc

    if not isinstance(value, dict):
        raise WriterError(f"{label} JSON root must be an object")
    return value


def validate_real_dry_run(config: dict[str, Any]) -> dict[str, Any]:
    return contract.validate_candidate_config(config, "real-dry-run")


def config_payload(config: dict[str, Any]) -> bytes:
    return (json.dumps(config, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_write_active_config(
    dest: pathlib.Path,
    config: dict[str, Any],
    *,
    mode: int,
    real_write_enabled: bool,
) -> None:
    payload = config_payload(config)
    tmp_name: str | None = None
    fd: int | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{dest.name}.", suffix=".tmp", dir=str(dest.parent))
        os.fchmod(fd, mode)
        if real_write_enabled:
            apply_real_ownership(pathlib.Path(tmp_name))
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, dest)
        tmp_name = None
        apply_mode_and_owner(dest, mode, real_write_enabled=real_write_enabled)
        fsync_directory(dest.parent)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def copy_file_private_atomic(
    src: pathlib.Path,
    dst: pathlib.Path,
    mode: int,
    *,
    real_write_enabled: bool,
) -> None:
    tmp_name: str | None = None
    fd: int | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{dst.name}.", suffix=".tmp", dir=str(dst.parent))
        os.fchmod(fd, mode)
        if real_write_enabled:
            apply_real_ownership(pathlib.Path(tmp_name))
        with src.open("rb") as source, os.fdopen(fd, "wb") as target:
            fd = None
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
        os.replace(tmp_name, dst)
        tmp_name = None
        apply_mode_and_owner(dst, mode, real_write_enabled=real_write_enabled)
        fsync_directory(dst.parent)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def create_backup(dest: pathlib.Path, backup_dir: pathlib.Path, *, real_write_enabled: bool) -> pathlib.Path:
    backup_name = f"{dest.name}.{backup_timestamp()}.{os.getpid()}.bak"
    backup_path = backup_dir / backup_name
    copy_file_private_atomic(dest, backup_path, PRIVATE_FILE_MODE, real_write_enabled=real_write_enabled)
    return backup_path


def restore_backup(
    backup_path: pathlib.Path,
    dest: pathlib.Path,
    *,
    mode: int,
    real_write_enabled: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "attempted": True,
        "backup_available": backup_path.exists(),
        "restored": False,
        "restored_valid": False,
    }
    if not backup_path.exists():
        result["reason"] = "backup_missing"
        return result

    copy_file_private_atomic(backup_path, dest, mode, real_write_enabled=real_write_enabled)
    restored_config = load_json_file(dest, label="restored config")
    restored_status = validate_real_dry_run(restored_config)
    result["restored"] = True
    result["restored_valid"] = bool(restored_status["valid"])
    if not restored_status["valid"]:
        result["reason"] = "restored_config_failed_validation"
    return result


def safe_unlink(path: pathlib.Path) -> bool:
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def file_mode_string(path: pathlib.Path) -> str | None:
    if not path.exists():
        return None
    return f"{stat.S_IMODE(path.stat().st_mode):03o}"


def build_base_status(generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "mode": "c6.2.2-real-writer-simulated",
        "result": "failed",
        "phase": "not_started",
        "validation": {
            "contract_mode": "real-dry-run",
            "pre_write_valid": False,
            "post_write_valid": False,
            "api_key_present": False,
            "placeholder_detected": False,
            "missing_fields_count": 0,
            "invalid_fields_count": 0,
            "placeholder_findings_count": 0,
        },
        "write": {
            "attempted": False,
            "active_config_written": False,
            "atomic_rename_completed": False,
            "fsync_file_completed": False,
            "fsync_directory_completed": False,
            "active_config_mode": None,
        },
        "backup": {
            "previous_config_existed": False,
            "created": False,
            "mode": None,
        },
        "rollback": {
            "attempted": False,
            "backup_available": False,
            "restored": False,
            "restored_valid": False,
            "active_removed_without_backup": False,
        },
        "real_write": {
            "enabled": False,
            "service_stop_confirmed_by_operator": False,
            "human_approved_real_write": False,
            "dest_exact_match": False,
            "backup_dir_exact_match": False,
            "candidate_private_tmp": False,
            "expected_owner": None,
            "expected_group": None,
            "expected_active_config_mode": None,
            "backup_dir_approved": False,
        },
        "privacy": {
            "api_key_value_written_to_status": False,
            "api_key_value_written_to_summary": False,
            "candidate_config_copied_to_output": False,
            "backup_content_copied_to_output": False,
        },
        "guardrails": {
            "writes_only_under_tmp": True,
            "dest_under_tmp": False,
            "backup_dir_under_tmp": False,
            "out_dir_under_tmp": True,
            "candidate_from_data_or_opt_refused": True,
            "candidate_from_home_or_repo_refused_in_real_mode": True,
            "real_config_read": False,
            "post_write_active_config_read": False,
            "data_written": False,
            "network_access": False,
            "systemctl_called": False,
            "nmcli_called": False,
            "mpv_called": False,
        },
        "artifacts": {
            "writer_status": STATUS_FILENAME,
            "summary": SUMMARY_FILENAME,
        },
    }


def apply_validation_to_status(status: dict[str, Any], validation: dict[str, Any], prefix: str) -> None:
    status["validation"][f"{prefix}_valid"] = bool(validation["valid"])
    status["validation"]["api_key_present"] = bool(validation["api_key_present"])
    status["validation"]["placeholder_detected"] = bool(validation["api_key_placeholder_detected"]) or bool(
        validation["placeholder_findings"]
    )
    status["validation"]["missing_fields_count"] = len(validation["missing_fields"])
    status["validation"]["invalid_fields_count"] = len(validation["invalid_fields"])
    status["validation"]["placeholder_findings_count"] = len(validation["placeholder_findings"])


def build_summary(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Dadooh C6.2.2 config writer real guarded",
            "",
            f"schema_version: {status['schema_version']}",
            f"mode: {status['mode']}",
            f"result: {status['result']}",
            f"phase: {status['phase']}",
            f"contract_mode: {status['validation']['contract_mode']}",
            f"pre_write_valid: {str(status['validation']['pre_write_valid']).lower()}",
            f"post_write_valid: {str(status['validation']['post_write_valid']).lower()}",
            f"api_key_present: {str(status['validation']['api_key_present']).lower()}",
            f"placeholder_detected: {str(status['validation']['placeholder_detected']).lower()}",
            f"missing_fields_count: {status['validation']['missing_fields_count']}",
            f"invalid_fields_count: {status['validation']['invalid_fields_count']}",
            f"placeholder_findings_count: {status['validation']['placeholder_findings_count']}",
            f"write_attempted: {str(status['write']['attempted']).lower()}",
            f"active_config_written: {str(status['write']['active_config_written']).lower()}",
            f"atomic_rename_completed: {str(status['write']['atomic_rename_completed']).lower()}",
            f"active_config_mode: {status['write']['active_config_mode']}",
            f"backup_previous_config_existed: {str(status['backup']['previous_config_existed']).lower()}",
            f"backup_created: {str(status['backup']['created']).lower()}",
            f"backup_mode: {status['backup']['mode']}",
            f"rollback_attempted: {str(status['rollback']['attempted']).lower()}",
            f"rollback_restored: {str(status['rollback']['restored']).lower()}",
            f"rollback_restored_valid: {str(status['rollback']['restored_valid']).lower()}",
            f"real_write_enabled: {str(status['real_write']['enabled']).lower()}",
            "service_stop_confirmed_by_operator: "
            f"{str(status['real_write']['service_stop_confirmed_by_operator']).lower()}",
            f"human_approved_real_write: {str(status['real_write']['human_approved_real_write']).lower()}",
            f"real_dest_exact_match: {str(status['real_write']['dest_exact_match']).lower()}",
            f"real_backup_dir_exact_match: {str(status['real_write']['backup_dir_exact_match']).lower()}",
            f"real_candidate_private_tmp: {str(status['real_write']['candidate_private_tmp']).lower()}",
            f"expected_active_config_mode: {status['real_write']['expected_active_config_mode']}",
            "api_key_value_written_to_status: false",
            "api_key_value_written_to_summary: false",
            "candidate_config_copied_to_output: false",
            "backup_content_copied_to_output: false",
            "real_config_read: false",
            f"post_write_active_config_read: {str(status['guardrails']['post_write_active_config_read']).lower()}",
            f"data_written: {str(status['guardrails']['data_written']).lower()}",
            "network_access: false",
            "systemctl_called: false",
            "nmcli_called: false",
            "mpv_called: false",
        ]
    )


def write_status_artifacts(out_dir: pathlib.Path, status: dict[str, Any]) -> None:
    prepare_private_dir(out_dir)
    atomic_write_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_text(out_dir / SUMMARY_FILENAME, build_summary(status), out_dir)


def run_writer(
    *,
    candidate_raw: str,
    dest_raw: str,
    backup_dir_raw: str | None,
    out_dir_raw: str,
    enable_real_write: bool = False,
    confirm_service_stopped: bool = False,
    confirm_human_approved_real_write: bool = False,
    simulate_post_write_failure: bool = False,
) -> dict[str, Any]:
    generated_at = utc_timestamp()
    out_dir = require_tmp_dir(out_dir_raw, "out-dir")
    prepare_private_dir(out_dir)
    status = build_base_status(generated_at)

    backup_path: pathlib.Path | None = None
    dest: pathlib.Path | None = None
    try:
        status["phase"] = "argument_validation"
        paths = validate_writer_paths(
            candidate_raw=candidate_raw,
            dest_raw=dest_raw,
            backup_dir_raw=backup_dir_raw,
            out_dir_raw=out_dir_raw,
            enable_real_write=enable_real_write,
            confirm_service_stopped=confirm_service_stopped,
            confirm_human_approved_real_write=confirm_human_approved_real_write,
        )
        candidate_path = paths.candidate
        dest = paths.dest
        backup_dir = paths.backup_dir
        out_dir = paths.out_dir
        active_config_mode = REAL_ACTIVE_CONFIG_MODE if paths.real_write_enabled else ACTIVE_CONFIG_MODE

        if paths.real_write_enabled:
            status["mode"] = "c6.2.2-real-write-guarded"
            status["real_write"].update(
                {
                    "enabled": True,
                    "service_stop_confirmed_by_operator": True,
                    "human_approved_real_write": True,
                    "dest_exact_match": dest == REAL_DEST_PATH,
                    "backup_dir_exact_match": backup_dir == REAL_BACKUP_DIR,
                    "candidate_private_tmp": path_is_under(candidate_path, TMP_ROOT),
                    "expected_owner": REAL_FILE_OWNER,
                    "expected_group": REAL_FILE_GROUP,
                    "expected_active_config_mode": f"{REAL_ACTIVE_CONFIG_MODE:03o}",
                    "backup_dir_approved": backup_dir == REAL_BACKUP_DIR,
                }
            )
            status["guardrails"]["writes_only_under_tmp"] = False
            status["guardrails"]["dest_under_tmp"] = False
            status["guardrails"]["backup_dir_under_tmp"] = False
        else:
            status["guardrails"]["dest_under_tmp"] = True
            status["guardrails"]["backup_dir_under_tmp"] = True
            status["real_write"]["expected_active_config_mode"] = f"{ACTIVE_CONFIG_MODE:03o}"

        status["phase"] = "candidate_load"
        candidate = load_json_file(candidate_path, label="candidate")

        status["phase"] = "pre_write_validation"
        pre_status = validate_real_dry_run(candidate)
        apply_validation_to_status(status, pre_status, "pre_write")
        if not pre_status["valid"]:
            status["result"] = "failed"
            write_status_artifacts(out_dir, status)
            raise WriterError("candidate failed real-dry-run validation")

        status["phase"] = "prepare_destination"
        prepare_active_parent(dest, real_write_enabled=paths.real_write_enabled)
        prepare_backup_dir(backup_dir, real_write_enabled=paths.real_write_enabled)

        status["backup"]["previous_config_existed"] = dest.exists()
        if dest.exists():
            status["phase"] = "backup"
            backup_path = create_backup(dest, backup_dir, real_write_enabled=paths.real_write_enabled)
            status["backup"]["created"] = True
            status["backup"]["mode"] = file_mode_string(backup_path)

        status["phase"] = "atomic_write"
        status["write"]["attempted"] = True
        atomic_write_active_config(
            dest,
            candidate,
            mode=active_config_mode,
            real_write_enabled=paths.real_write_enabled,
        )
        status["write"]["active_config_written"] = True
        status["write"]["atomic_rename_completed"] = True
        status["write"]["fsync_file_completed"] = True
        status["write"]["fsync_directory_completed"] = True
        status["write"]["active_config_mode"] = file_mode_string(dest)
        status["guardrails"]["data_written"] = paths.real_write_enabled

        status["phase"] = "post_write_validation"
        written_candidate = load_json_file(dest, label="active simulated config")
        status["guardrails"]["post_write_active_config_read"] = True
        post_status = validate_real_dry_run(written_candidate)
        if simulate_post_write_failure:
            post_status = dict(post_status)
            post_status["valid"] = False
        apply_validation_to_status(status, post_status, "post_write")
        if not post_status["valid"]:
            status["phase"] = "rollback"
            if backup_path is not None:
                rollback = restore_backup(
                    backup_path,
                    dest,
                    mode=active_config_mode,
                    real_write_enabled=paths.real_write_enabled,
                )
                status["rollback"].update(rollback)
                status["write"]["active_config_mode"] = file_mode_string(dest)
            else:
                status["rollback"]["attempted"] = True
                status["rollback"]["backup_available"] = False
                status["rollback"]["active_removed_without_backup"] = safe_unlink(dest)
                status["write"]["active_config_mode"] = file_mode_string(dest)
            status["result"] = "failed"
            write_status_artifacts(out_dir, status)
            raise WriterError("post-write validation failed")

        status["phase"] = "completed"
        status["result"] = "passed"
        try:
            write_status_artifacts(out_dir, status)
        except OSError:
            # The active config is already atomically written and revalidated.
            # Losing local evidence must not be reported to the user as a failed write.
            print("warning: config_saved_status_artifact_unavailable", file=sys.stderr)
        return status
    except Exception:
        if dest is not None and status["phase"] not in {"completed", "rollback"}:
            status["write"]["active_config_mode"] = file_mode_string(dest)
        if status["phase"] not in {"pre_write_validation", "post_write_validation", "rollback"}:
            status["result"] = "failed"
            try:
                write_status_artifacts(out_dir, status)
            except OSError:
                pass
        raise


def product_reset_fault(ctx: ProductResetContext, phase: str) -> None:
    if ctx.fault_after == phase:
        raise WriterError(f"product_reset_fault:{phase}")


def canonical_uuid4(raw_value: str | None, *, generate: bool) -> str:
    if raw_value is None:
        if generate:
            return str(uuid.uuid4())
        raise WriterError("product_reset_operation_id_required")
    if not isinstance(raw_value, str):
        raise WriterError("product_reset_operation_id_invalid")
    value = raw_value.strip()
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise WriterError("product_reset_operation_id_invalid") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise WriterError("product_reset_operation_id_invalid")
    return value


def product_reset_require_exact_keys(value: dict[str, Any], expected: set[str], error: str) -> None:
    if set(value) != expected:
        raise WriterError(error)


def product_reset_require_strict_bool(value: Any, error: str) -> bool:
    if type(value) is not bool:
        raise WriterError(error)
    return value


def product_reset_require_optional_bool(value: Any, error: str) -> bool | None:
    if value is None:
        return None
    return product_reset_require_strict_bool(value, error)


def product_reset_require_nonempty_string(value: Any, error: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise WriterError(error)
    return value


def product_reset_phase_for_rel(rel: pathlib.Path, suffix: str) -> str:
    return f"{str(rel).replace('/', '_').replace('-', '_')}_{suffix}"


def product_reset_owner_ids() -> tuple[int, int]:
    try:
        return pwd.getpwnam(PRODUCT_RESET_REAL_OWNER).pw_uid, grp.getgrnam(PRODUCT_RESET_REAL_GROUP).gr_gid
    except KeyError as exc:
        raise WriterError("product_reset_owner_lookup_failed") from exc


def build_product_reset_context(
    *,
    data_root_raw: str,
    allow_test_root: bool = False,
    require_real_confirmation: bool = False,
    enable_real_write: bool = False,
    confirm_service_stopped: bool = False,
    owner_uid: int | None = None,
    owner_gid: int | None = None,
    owner_applier: Any | None = None,
    fingerprint_provider: Any | None = None,
    fault_after: str | None = None,
) -> ProductResetContext:
    if allow_test_root:
        data_root = require_tmp_dir(data_root_raw, "product-reset-data-root")
        data_root.mkdir(mode=PRODUCT_RESET_RECREATE_MODE, parents=True, exist_ok=True)
    else:
        raw_absolute = pathlib.Path(os.path.normpath(os.path.abspath(str(pathlib.Path(data_root_raw).expanduser()))))
        if raw_absolute != PRODUCT_RESET_REAL_DATA_ROOT:
            raise WriterError("product_reset_data_root_must_be_/data")
        if require_real_confirmation and not (enable_real_write and confirm_service_stopped):
            raise WriterError("product_reset_real_confirmation_required")
        try:
            root_stat = os.lstat(raw_absolute)
        except FileNotFoundError as exc:
            raise WriterError("product_reset_data_root_missing") from exc
        if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
            raise WriterError("product_reset_data_root_untrusted")
        data_root = raw_absolute

    try:
        root_stat = os.lstat(data_root)
    except FileNotFoundError as exc:
        raise WriterError("product_reset_data_root_missing") from exc
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise WriterError("product_reset_data_root_untrusted")

    if owner_uid is None or owner_gid is None:
        if allow_test_root:
            owner_uid = os.getuid()
            owner_gid = os.getgid()
        else:
            owner_uid, owner_gid = product_reset_owner_ids()

    return ProductResetContext(
        data_root=data_root,
        allow_test_root=allow_test_root,
        owner_uid=int(owner_uid),
        owner_gid=int(owner_gid),
        owner_applier=owner_applier,
        fingerprint_provider=fingerprint_provider,
        fault_after=fault_after,
    )


def product_reset_rel_path(ctx: ProductResetContext, rel: pathlib.Path, label: str) -> pathlib.Path:
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise WriterError(f"product_reset_untrusted_path:{label}")
    current = ctx.data_root
    for part in rel.parts[:-1]:
        current = current / part
        try:
            current_stat = os.lstat(current)
        except FileNotFoundError:
            break
        if stat.S_ISLNK(current_stat.st_mode) or not stat.S_ISDIR(current_stat.st_mode):
            raise WriterError(f"product_reset_untrusted_path:{label}")
    return ctx.data_root / rel


def product_reset_existing_path_type(path: pathlib.Path) -> str:
    try:
        path_stat = os.lstat(path)
    except FileNotFoundError:
        return "missing"
    mode = path_stat.st_mode
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISDIR(mode):
        return "dir"
    if stat.S_ISREG(mode):
        return "file"
    return "other"


def product_reset_require_existing_dir(path: pathlib.Path, label: str) -> None:
    path_type = product_reset_existing_path_type(path)
    if path_type != "dir":
        raise WriterError(f"product_reset_untrusted_path:{label}")


def product_reset_require_dir_shape(
    path: pathlib.Path,
    label: str,
    *,
    mode: int | None = None,
    uid: int | None = None,
    gid: int | None = None,
) -> None:
    product_reset_require_existing_dir(path, label)
    path_stat = os.lstat(path)
    if mode is not None and stat.S_IMODE(path_stat.st_mode) != mode:
        raise WriterError(f"product_reset_untrusted_path:{label}")
    if uid is not None and path_stat.st_uid != uid:
        raise WriterError(f"product_reset_untrusted_path:{label}")
    if gid is not None and path_stat.st_gid != gid:
        raise WriterError(f"product_reset_untrusted_path:{label}")


def product_reset_require_file_shape(
    path: pathlib.Path,
    label: str,
    *,
    mode: int,
    uid: int | None,
    gid: int | None,
    require_single_link: bool = False,
) -> None:
    product_reset_checked_file(path, label)
    path_stat = os.lstat(path)
    if stat.S_IMODE(path_stat.st_mode) != mode:
        raise WriterError(f"product_reset_bad_mode:{label}")
    if uid is not None and path_stat.st_uid != uid:
        raise WriterError(f"product_reset_untrusted_path:{label}")
    if gid is not None and path_stat.st_gid != gid:
        raise WriterError(f"product_reset_untrusted_path:{label}")
    if require_single_link and path_stat.st_nlink != 1:
        raise WriterError(f"product_reset_untrusted_path:{label}")


def product_reset_source_owner_ids(ctx: ProductResetContext) -> tuple[int, int]:
    if ctx.allow_test_root:
        return os.getuid(), os.getgid()
    return ctx.owner_uid, ctx.owner_gid


def product_reset_config_file_owner_ids(ctx: ProductResetContext) -> tuple[int, int]:
    if ctx.allow_test_root:
        return os.getuid(), os.getgid()
    root_uid, _root_gid = product_reset_root_owned_ids()
    return root_uid, ctx.owner_gid


def product_reset_root_owned_ids() -> tuple[int, int]:
    return 0, 0


def product_reset_prepare_dir(
    path: pathlib.Path,
    mode: int,
    *,
    label: str,
    parents: bool = True,
    apply_owner: bool = False,
    ctx: ProductResetContext | None = None,
) -> None:
    path_type = product_reset_existing_path_type(path)
    if path_type in {"symlink", "file", "other"}:
        raise WriterError(f"product_reset_untrusted_path:{label}")
    path.mkdir(mode=mode, parents=parents, exist_ok=True)
    if apply_owner:
        if ctx is None:
            raise WriterError("product_reset_owner_context_missing")
        if ctx.owner_applier is not None:
            ctx.owner_applier(path, ctx.owner_uid, ctx.owner_gid)
        elif not ctx.allow_test_root:
            os.chown(path, ctx.owner_uid, ctx.owner_gid)
    path.chmod(mode)
    fsync_directory(path.parent, required=True)


def product_reset_prepare_private_state_dir(ctx: ProductResetContext, path: pathlib.Path, label: str) -> None:
    path_type = product_reset_existing_path_type(path)
    if path_type in {"symlink", "file", "other"}:
        raise WriterError(f"product_reset_untrusted_path:{label}")
    if path_type == "dir":
        product_reset_require_private_state_dir(ctx, path, label)
        return

    path.mkdir(mode=PRIVATE_DIR_MODE, parents=False, exist_ok=False)
    path.chmod(PRIVATE_DIR_MODE)
    if not ctx.allow_test_root:
        root_uid, root_gid = product_reset_root_owned_ids()
        product_reset_require_dir_shape(path, label, mode=PRIVATE_DIR_MODE, uid=root_uid, gid=root_gid)
    fsync_directory(path.parent, required=True)


def product_reset_require_private_state_dir(ctx: ProductResetContext, path: pathlib.Path, label: str) -> None:
    if ctx.allow_test_root:
        product_reset_require_dir_shape(path, label, mode=PRIVATE_DIR_MODE)
        return
    root_uid, root_gid = product_reset_root_owned_ids()
    product_reset_require_dir_shape(path, label, mode=PRIVATE_DIR_MODE, uid=root_uid, gid=root_gid)


def product_reset_state_dir(ctx: ProductResetContext) -> pathlib.Path:
    return product_reset_rel_path(ctx, PRODUCT_RESET_STATE_REL, "state")


def product_reset_graveyard_root(ctx: ProductResetContext) -> pathlib.Path:
    return product_reset_rel_path(ctx, PRODUCT_RESET_GRAVEYARD_REL, "graveyard")


def product_reset_intent_path(ctx: ProductResetContext) -> pathlib.Path:
    return product_reset_state_dir(ctx) / PRODUCT_RESET_INTENT_FILENAME


def product_reset_pending_credential_path(ctx: ProductResetContext) -> pathlib.Path:
    return product_reset_state_dir(ctx) / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME


def product_reset_receipt_path(ctx: ProductResetContext) -> pathlib.Path:
    return product_reset_state_dir(ctx) / PRODUCT_RESET_RECEIPT_FILENAME


def product_reset_gc_pending_path(ctx: ProductResetContext) -> pathlib.Path:
    return product_reset_state_dir(ctx) / PRODUCT_RESET_GC_PENDING_FILENAME


def product_reset_homologation_seed_disabled_path(ctx: ProductResetContext) -> pathlib.Path:
    return product_reset_state_dir(ctx) / PRODUCT_RESET_HOMOLOGATION_SEED_DISABLED_FILENAME


def product_reset_require_state_parent(ctx: ProductResetContext, state_dir: pathlib.Path) -> None:
    if ctx.allow_test_root:
        product_reset_require_existing_dir(state_dir.parent, "state-parent")
    else:
        root_uid, root_gid = product_reset_root_owned_ids()
        product_reset_require_dir_shape(state_dir.parent, "state-parent", mode=0o755, uid=root_uid, gid=root_gid)


def product_reset_prepare_state(ctx: ProductResetContext) -> pathlib.Path:
    state_dir = product_reset_state_dir(ctx)
    product_reset_require_state_parent(ctx, state_dir)
    product_reset_prepare_private_state_dir(ctx, state_dir, "state")
    return state_dir


def product_reset_checked_file(path: pathlib.Path, label: str) -> None:
    path_type = product_reset_existing_path_type(path)
    if path_type != "file":
        raise WriterError(f"product_reset_untrusted_path:{label}")


def product_reset_atomic_write_json(path: pathlib.Path, value: dict[str, Any], mode: int) -> None:
    product_reset_require_existing_dir(path.parent, "write-parent")
    path_type = product_reset_existing_path_type(path)
    if path_type in {"symlink", "dir", "other"}:
        raise WriterError("product_reset_untrusted_path:write-target")
    if path_type == "file" and os.lstat(path).st_nlink != 1:
        raise WriterError("product_reset_untrusted_path:write-target")
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    tmp_name: str | None = None
    fd: int | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
        path.chmod(mode)
        fsync_directory(path.parent, required=True)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def product_reset_load_json(path: pathlib.Path, *, label: str, private_mode: int | None = None) -> dict[str, Any]:
    product_reset_checked_file(path, label)
    path_stat = os.lstat(path)
    if path_stat.st_nlink != 1:
        raise WriterError(f"product_reset_untrusted_path:{label}")
    if private_mode is not None and stat.S_IMODE(path_stat.st_mode) != private_mode:
        raise WriterError(f"product_reset_bad_mode:{label}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError as exc:
        raise WriterError(f"product_reset_bad_json:{label}") from exc
    except OSError as exc:
        raise WriterError(f"product_reset_read_failed:{label}") from exc
    if not isinstance(value, dict):
        raise WriterError(f"product_reset_bad_json:{label}")
    return value


def product_reset_write_intent(ctx: ProductResetContext, intent: dict[str, Any]) -> None:
    product_reset_atomic_write_json(product_reset_intent_path(ctx), intent, PRIVATE_FILE_MODE)


def product_reset_validate_intent(value: dict[str, Any]) -> dict[str, Any]:
    expected_fields = {
        "schema_version",
        "operation_id",
        "created_at_utc",
        "updated_at_utc",
        "phase",
        "credential_captured",
        "device_fingerprint_captured",
        "domains",
        "last_settings",
        "homologation_seed",
        "privacy",
    }
    phase = value.get("phase")
    if phase == "local_complete":
        expected_fields.add("completed_at_utc")
    product_reset_require_exact_keys(value, expected_fields, "product_reset_intent_invalid")
    if value.get("schema_version") != PRODUCT_RESET_SCHEMA_VERSION:
        raise WriterError("product_reset_intent_invalid")
    operation_id = canonical_uuid4(value.get("operation_id"), generate=False)
    product_reset_require_nonempty_string(value.get("created_at_utc"), "product_reset_intent_invalid")
    product_reset_require_nonempty_string(value.get("updated_at_utc"), "product_reset_intent_invalid")
    if phase not in PRODUCT_RESET_INTENT_PHASES:
        raise WriterError("product_reset_intent_invalid")
    if phase == "local_complete":
        product_reset_require_nonempty_string(value.get("completed_at_utc"), "product_reset_intent_invalid")
    if not product_reset_require_strict_bool(value.get("credential_captured"), "product_reset_intent_invalid"):
        raise WriterError("product_reset_intent_invalid")
    if not product_reset_require_strict_bool(value.get("device_fingerprint_captured"), "product_reset_intent_invalid"):
        raise WriterError("product_reset_intent_invalid")
    domains = value.get("domains")
    if not isinstance(domains, dict):
        raise WriterError("product_reset_intent_invalid")
    product_reset_require_exact_keys(
        domains,
        {str(rel) for rel in PRODUCT_RESET_FIXED_DOMAINS},
        "product_reset_intent_invalid",
    )
    for rel in PRODUCT_RESET_FIXED_DOMAINS:
        item = domains.get(str(rel))
        if not isinstance(item, dict):
            raise WriterError("product_reset_intent_invalid")
        product_reset_require_exact_keys(item, {"moved", "recreated", "source_existed"}, "product_reset_intent_invalid")
        moved = product_reset_require_strict_bool(item.get("moved"), "product_reset_intent_invalid")
        recreated = product_reset_require_strict_bool(item.get("recreated"), "product_reset_intent_invalid")
        product_reset_require_optional_bool(item.get("source_existed"), "product_reset_intent_invalid")
        if recreated and not moved:
            raise WriterError("product_reset_intent_invalid")
    last_settings = value.get("last_settings")
    if not isinstance(last_settings, dict):
        raise WriterError("product_reset_intent_invalid")
    product_reset_require_exact_keys(last_settings, {"moved", "source_existed"}, "product_reset_intent_invalid")
    product_reset_require_strict_bool(last_settings.get("moved"), "product_reset_intent_invalid")
    product_reset_require_optional_bool(last_settings.get("source_existed"), "product_reset_intent_invalid")
    homologation_seed = value.get("homologation_seed")
    if not isinstance(homologation_seed, dict):
        raise WriterError("product_reset_intent_invalid")
    product_reset_require_exact_keys(
        homologation_seed,
        {"delete_prepared", "disabled_marker_written", "removed", "source_existed"},
        "product_reset_intent_invalid",
    )
    delete_prepared = product_reset_require_strict_bool(
        homologation_seed.get("delete_prepared"),
        "product_reset_intent_invalid",
    )
    seed_removed = product_reset_require_strict_bool(
        homologation_seed.get("removed"),
        "product_reset_intent_invalid",
    )
    disabled_marker_written = product_reset_require_strict_bool(
        homologation_seed.get("disabled_marker_written"),
        "product_reset_intent_invalid",
    )
    seed_existed = product_reset_require_optional_bool(
        homologation_seed.get("source_existed"),
        "product_reset_intent_invalid",
    )
    if seed_removed and not delete_prepared:
        raise WriterError("product_reset_intent_invalid")
    if disabled_marker_written and not delete_prepared:
        raise WriterError("product_reset_intent_invalid")
    if seed_removed and not disabled_marker_written:
        raise WriterError("product_reset_intent_invalid")
    if delete_prepared != (seed_existed is not None):
        raise WriterError("product_reset_intent_invalid")
    if phase == "local_complete" and not seed_removed:
        raise WriterError("product_reset_intent_invalid")
    privacy = value.get("privacy")
    if not isinstance(privacy, dict):
        raise WriterError("product_reset_intent_invalid")
    product_reset_require_exact_keys(
        privacy,
        {
            "secret_written_to_intent",
            "api_url_written_to_intent",
            "environment_written_to_intent",
            "station_written_to_intent",
        },
        "product_reset_intent_invalid",
    )
    for privacy_value in privacy.values():
        if product_reset_require_strict_bool(privacy_value, "product_reset_intent_invalid"):
            raise WriterError("product_reset_intent_invalid")
    value["operation_id"] = operation_id
    return value


def product_reset_new_intent(operation_id: str) -> dict[str, Any]:
    return {
        "schema_version": PRODUCT_RESET_SCHEMA_VERSION,
        "operation_id": operation_id,
        "created_at_utc": utc_timestamp(),
        "updated_at_utc": utc_timestamp(),
        "phase": "intent_written",
        "credential_captured": True,
        "device_fingerprint_captured": True,
        "domains": {
            str(rel): {
                "moved": False,
                "recreated": False,
                "source_existed": None,
            }
            for rel in PRODUCT_RESET_FIXED_DOMAINS
        },
        "last_settings": {
            "moved": False,
            "source_existed": None,
        },
        "homologation_seed": {
            "delete_prepared": False,
            "disabled_marker_written": False,
            "removed": False,
            "source_existed": None,
        },
        "privacy": {
            "secret_written_to_intent": False,
            "api_url_written_to_intent": False,
            "environment_written_to_intent": False,
            "station_written_to_intent": False,
        },
    }


def product_reset_write_intent_phase(ctx: ProductResetContext, intent: dict[str, Any], phase: str) -> None:
    intent["phase"] = phase
    intent["updated_at_utc"] = utc_timestamp()
    product_reset_write_intent(ctx, intent)


def product_reset_device_fingerprint(
    *,
    hostname: str | None = None,
    machine_id: str | None = None,
) -> str:
    actual_hostname = hostname if hostname is not None else (socket.gethostname() or "totem")
    actual_machine_id = machine_id
    if actual_machine_id is None:
        actual_machine_id = ""
        for candidate in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                actual_machine_id = pathlib.Path(candidate).read_text(encoding="utf-8").strip()
                if actual_machine_id:
                    break
            except Exception:
                continue
    seed = f"{actual_hostname}:{actual_machine_id or 'no-machine-id'}"
    digest = uuid.uuid5(uuid.NAMESPACE_DNS, seed).hex[:12]
    safe_hostname = re.sub(r"[^a-zA-Z0-9_.-]", "-", actual_hostname)[:48] or "totem"
    return f"{safe_hostname}-{digest}"


def product_reset_current_fingerprint(ctx: ProductResetContext) -> str:
    if ctx.fingerprint_provider is not None:
        raw_value = ctx.fingerprint_provider()
        if not isinstance(raw_value, str):
            raise WriterError("product_reset_fingerprint_invalid")
        value = raw_value
    else:
        value = product_reset_device_fingerprint()
    if not value or value.strip() != value or len(value) > 200:
        raise WriterError("product_reset_fingerprint_invalid")
    return value


def product_reset_validate_https_api_url(value: Any) -> str:
    if not isinstance(value, str):
        raise WriterError("product_reset_api_url_invalid")
    raw = value.strip()
    if not raw or raw != value:
        raise WriterError("product_reset_api_url_invalid")
    try:
        parsed = urllib_parse.urlsplit(raw)
        _port = parsed.port
    except ValueError as exc:
        raise WriterError("product_reset_api_url_invalid") from exc
    if parsed.scheme != "https" or not parsed.netloc or not parsed.hostname:
        raise WriterError("product_reset_api_url_invalid")
    if parsed.username or parsed.password or parsed.fragment:
        raise WriterError("product_reset_api_url_invalid")
    return raw


def product_reset_validate_api_key(value: Any) -> str:
    if not isinstance(value, str):
        raise WriterError("product_reset_api_key_invalid")
    raw = value.strip()
    if raw != value or len(raw) < 16 or len(raw) > 4096:
        raise WriterError("product_reset_api_key_invalid")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        raise WriterError("product_reset_api_key_invalid")
    lowered = raw.lower()
    if "placeholder" in lowered or "preencher" in lowered or "mock" in lowered:
        raise WriterError("product_reset_api_key_invalid")
    return raw


def canonical_uuid(raw_value: Any, label: str) -> str:
    if not isinstance(raw_value, str):
        raise WriterError(f"product_reset_{label}_invalid")
    value = raw_value.strip()
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise WriterError(f"product_reset_{label}_invalid") from exc
    if str(parsed) != value:
        raise WriterError(f"product_reset_{label}_invalid")
    return value


def product_reset_capture_active_credential(ctx: ProductResetContext, operation_id: str) -> dict[str, Any]:
    active_path = product_reset_rel_path(ctx, pathlib.Path("config/config.json"), "active-config")
    active_config = product_reset_load_json(active_path, label="active-config")
    api_url = product_reset_validate_https_api_url(active_config.get("api_url"))
    api_key = product_reset_validate_api_key(active_config.get("api_key"))
    credential: dict[str, Any] = {
        "schema_version": PRODUCT_RESET_SCHEMA_VERSION,
        "operation_id": operation_id,
        "captured_at_utc": utc_timestamp(),
        "api_url": api_url,
        "api_key": api_key,
        "device_fingerprint": product_reset_current_fingerprint(ctx),
    }
    api_token_id = active_config.get("api_token_id")
    if api_token_id is not None:
        credential["api_token_id"] = canonical_uuid(api_token_id, "api_token_id")
    return credential


def product_reset_validate_pending_credential(value: dict[str, Any]) -> dict[str, Any]:
    expected_fields = {
        "schema_version",
        "operation_id",
        "captured_at_utc",
        "api_url",
        "api_key",
        "device_fingerprint",
    }
    if "api_token_id" in value:
        expected_fields.add("api_token_id")
    product_reset_require_exact_keys(value, expected_fields, "product_reset_pending_credential_invalid")
    if value.get("schema_version") != PRODUCT_RESET_SCHEMA_VERSION:
        raise WriterError("product_reset_pending_credential_invalid")
    value["operation_id"] = canonical_uuid4(value.get("operation_id"), generate=False)
    product_reset_require_nonempty_string(value.get("captured_at_utc"), "product_reset_pending_credential_invalid")
    value["api_url"] = product_reset_validate_https_api_url(value.get("api_url"))
    value["api_key"] = product_reset_validate_api_key(value.get("api_key"))
    fingerprint = value.get("device_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint or fingerprint.strip() != fingerprint or len(fingerprint) > 200:
        raise WriterError("product_reset_fingerprint_invalid")
    if "api_token_id" in value:
        value["api_token_id"] = canonical_uuid(value.get("api_token_id"), "api_token_id")
    if "environment_id" in value or "station_id" in value:
        raise WriterError("product_reset_pending_credential_invalid")
    return value


def product_reset_graveyard_path(ctx: ProductResetContext, operation_id: str) -> pathlib.Path:
    op = canonical_uuid4(operation_id, generate=False)
    return product_reset_rel_path(ctx, PRODUCT_RESET_GRAVEYARD_REL / op, "graveyard-op")


def product_reset_list_graveyard_ids(ctx: ProductResetContext) -> list[str]:
    graveyard_root = product_reset_graveyard_root(ctx)
    if product_reset_existing_path_type(graveyard_root) == "missing":
        return []
    if ctx.allow_test_root:
        product_reset_require_dir_shape(graveyard_root, "graveyard", mode=PRIVATE_DIR_MODE)
    else:
        root_uid, root_gid = product_reset_root_owned_ids()
        product_reset_require_dir_shape(graveyard_root, "graveyard", mode=PRIVATE_DIR_MODE, uid=root_uid, gid=root_gid)
    ids: list[str] = []
    for entry in sorted(graveyard_root.iterdir(), key=lambda item: item.name):
        entry_type = product_reset_existing_path_type(entry)
        if entry_type != "dir":
            raise WriterError("product_reset_graveyard_untrusted")
        if ctx.allow_test_root:
            product_reset_require_dir_shape(entry, "graveyard-op", mode=PRIVATE_DIR_MODE)
        else:
            root_uid, root_gid = product_reset_root_owned_ids()
            product_reset_require_dir_shape(entry, "graveyard-op", mode=PRIVATE_DIR_MODE, uid=root_uid, gid=root_gid)
        ids.append(canonical_uuid4(entry.name, generate=False))
    return ids


def product_reset_prepare_graveyard(ctx: ProductResetContext, operation_id: str) -> pathlib.Path:
    graveyard_root = product_reset_graveyard_root(ctx)
    product_reset_prepare_private_state_dir(ctx, graveyard_root, "graveyard")
    existing_ids = product_reset_list_graveyard_ids(ctx)
    if any(existing_id != operation_id for existing_id in existing_ids):
        raise WriterError("product_reset_graveyard_gc_required")
    op_dir = product_reset_graveyard_path(ctx, operation_id)
    product_reset_prepare_private_state_dir(ctx, op_dir, "graveyard-op")
    return op_dir


def product_reset_mount_points(
    mountinfo_path: pathlib.Path = pathlib.Path("/proc/self/mountinfo"),
) -> tuple[pathlib.Path, ...]:
    try:
        raw_lines = mountinfo_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise WriterError("product_reset_mountinfo_unavailable") from exc

    mount_points: list[pathlib.Path] = []
    escape_pattern = re.compile(r"\\([0-7]{3})")
    for raw_line in raw_lines:
        fields = raw_line.split()
        if len(fields) < 10 or "-" not in fields[6:]:
            raise WriterError("product_reset_mountinfo_invalid")
        decoded = escape_pattern.sub(lambda match: chr(int(match.group(1), 8)), fields[4])
        if "\\" in decoded or not decoded.startswith("/"):
            raise WriterError("product_reset_mountinfo_invalid")
        normalized = pathlib.Path(os.path.normpath(decoded))
        if str(normalized) != decoded:
            raise WriterError("product_reset_mountinfo_invalid")
        mount_points.append(normalized)
    if not mount_points:
        raise WriterError("product_reset_mountinfo_invalid")
    return tuple(mount_points)


def product_reset_require_no_mounts_below(
    path: pathlib.Path,
    *,
    mount_points: tuple[pathlib.Path, ...] | None = None,
) -> None:
    target = absolute_no_resolve(str(path))
    points = product_reset_mount_points() if mount_points is None else mount_points
    for mount_point in points:
        if mount_point == target or path_is_under(mount_point, target):
            raise WriterError("product_reset_graveyard_contains_mount")


def product_reset_remove_graveyard(ctx: ProductResetContext, operation_id: str) -> bool:
    graveyard_root = product_reset_graveyard_root(ctx)
    if product_reset_existing_path_type(graveyard_root) == "missing":
        return False
    product_reset_require_private_state_dir(ctx, graveyard_root, "graveyard")
    graveyard_path = product_reset_graveyard_path(ctx, operation_id)
    path_type = product_reset_existing_path_type(graveyard_path)
    if path_type == "missing":
        return False
    if path_type != "dir":
        raise WriterError("product_reset_graveyard_untrusted")
    product_reset_require_private_state_dir(ctx, graveyard_path, "graveyard-op")
    if not shutil.rmtree.avoids_symlink_attacks:
        raise WriterError("product_reset_graveyard_cleanup_unsupported")
    product_reset_require_no_mounts_below(graveyard_path)
    shutil.rmtree(graveyard_path)
    fsync_directory(graveyard_root, required=True)
    return True


def product_reset_prepare_graveyard_parent(path: pathlib.Path) -> None:
    product_reset_prepare_dir(path.parent, PRIVATE_DIR_MODE, label="graveyard-parent")


def product_reset_sanitize_graveyard_config(ctx: ProductResetContext, operation_id: str) -> None:
    config_dir = product_reset_graveyard_path(ctx, operation_id) / "config"
    path_type = product_reset_existing_path_type(config_dir)
    if path_type == "missing":
        return
    if path_type != "dir" or not shutil.rmtree.avoids_symlink_attacks:
        raise WriterError("product_reset_graveyard_config_untrusted")
    product_reset_require_no_mounts_below(config_dir)
    shutil.rmtree(config_dir)
    fsync_directory(config_dir.parent, required=True)
    product_reset_prepare_dir(config_dir, PRIVATE_DIR_MODE, label="graveyard-config", parents=False)
    product_reset_atomic_write_json(
        config_dir / "config.json",
        {
            "schema_version": "dadooh.c26.product-reset-redacted.v1",
            "product_reset_redacted": True,
        },
        PRIVATE_FILE_MODE,
    )


def product_reset_recreate_domain(ctx: ProductResetContext, path: pathlib.Path, label: str) -> None:
    path_type = product_reset_existing_path_type(path)
    if path_type in {"symlink", "file", "other"}:
        raise WriterError(f"product_reset_untrusted_path:{label}")
    product_reset_require_existing_dir(path.parent, f"{label}-parent")
    product_reset_prepare_dir(
        path,
        PRODUCT_RESET_RECREATE_MODE,
        label=label,
        parents=False,
        apply_owner=True,
        ctx=ctx,
    )


def product_reset_move_domain(ctx: ProductResetContext, intent: dict[str, Any], operation_id: str, rel: pathlib.Path) -> None:
    key = str(rel)
    item = intent["domains"][key]
    source = product_reset_rel_path(ctx, rel, key)
    target = product_reset_graveyard_path(ctx, operation_id) / rel
    moved_phase = product_reset_phase_for_rel(rel, "moved")
    recreated_phase = product_reset_phase_for_rel(rel, "recreated")

    if not item["moved"]:
        source_type = product_reset_existing_path_type(source)
        target_type = product_reset_existing_path_type(target)
        if source_type == "missing":
            if target_type in {"symlink", "file", "other"}:
                raise WriterError(f"product_reset_untrusted_path:{key}")
            item["source_existed"] = target_type == "dir"
        elif source_type == "dir":
            if target_type != "missing":
                raise WriterError("product_reset_domain_conflict")
            product_reset_prepare_graveyard_parent(target)
            os.replace(source, target)
            fsync_directory(source.parent, required=True)
            fsync_directory(target.parent, required=True)
            item["source_existed"] = True
        else:
            raise WriterError(f"product_reset_untrusted_path:{key}")
        if rel == pathlib.Path("config"):
            product_reset_sanitize_graveyard_config(ctx, operation_id)
        item["moved"] = True
        product_reset_write_intent_phase(ctx, intent, moved_phase)
        product_reset_fault(ctx, moved_phase)
    elif rel == pathlib.Path("config"):
        product_reset_sanitize_graveyard_config(ctx, operation_id)

    if not item["recreated"]:
        product_reset_recreate_domain(ctx, source, key)
        item["recreated"] = True
        product_reset_write_intent_phase(ctx, intent, recreated_phase)
        product_reset_fault(ctx, recreated_phase)


def product_reset_move_last_settings(ctx: ProductResetContext, intent: dict[str, Any], operation_id: str) -> None:
    item = intent["last_settings"]
    source = product_reset_rel_path(ctx, PRODUCT_RESET_LAST_SETTINGS_REL, "last-settings")
    target = product_reset_graveyard_path(ctx, operation_id) / PRODUCT_RESET_LAST_SETTINGS_REL
    source_type = product_reset_existing_path_type(source)
    target_type = product_reset_existing_path_type(target)
    if source_type not in {"missing", "file"} or target_type not in {"missing", "file"}:
        raise WriterError("product_reset_untrusted_path:last-settings")
    if item["moved"]:
        if source_type != "missing" or target_type != "missing":
            raise WriterError("product_reset_last_settings_reappeared")
        return
    item["source_existed"] = source_type == "file" or target_type == "file"
    if source_type == "file":
        source.unlink()
        fsync_directory(source.parent, required=True)
    if target_type == "file":
        target.unlink()
        fsync_directory(target.parent, required=True)
    item["moved"] = True
    product_reset_write_intent_phase(ctx, intent, "last_settings_moved")
    product_reset_fault(ctx, "last_settings_moved")


def product_reset_homologation_seed_owner_ids(ctx: ProductResetContext) -> tuple[int, int]:
    if ctx.allow_test_root:
        return os.getuid(), os.getgid()
    return product_reset_root_owned_ids()


def product_reset_validate_homologation_seed_disabled_marker(
    marker: dict[str, Any],
) -> dict[str, Any]:
    product_reset_require_exact_keys(
        marker,
        {"schema_version", "disabled", "disabled_at_utc", "first_operation_id"},
        "product_reset_homologation_seed_disabled_marker_invalid",
    )
    if marker.get("schema_version") != PRODUCT_RESET_SCHEMA_VERSION:
        raise WriterError("product_reset_homologation_seed_disabled_marker_invalid")
    if not product_reset_require_strict_bool(
        marker.get("disabled"),
        "product_reset_homologation_seed_disabled_marker_invalid",
    ):
        raise WriterError("product_reset_homologation_seed_disabled_marker_invalid")
    product_reset_require_nonempty_string(
        marker.get("disabled_at_utc"),
        "product_reset_homologation_seed_disabled_marker_invalid",
    )
    marker["first_operation_id"] = canonical_uuid4(
        marker.get("first_operation_id"),
        generate=False,
    )
    return marker


def product_reset_load_homologation_seed_disabled_marker(
    ctx: ProductResetContext,
) -> dict[str, Any] | None:
    marker_path = product_reset_homologation_seed_disabled_path(ctx)
    if product_reset_existing_path_type(marker_path) == "missing":
        return None
    marker = product_reset_load_json(
        marker_path,
        label="homologation-seed-disabled",
        private_mode=PRIVATE_FILE_MODE,
    )
    return product_reset_validate_homologation_seed_disabled_marker(marker)


def product_reset_ensure_homologation_seed_disabled_marker(
    ctx: ProductResetContext,
    operation_id: str,
) -> None:
    if product_reset_load_homologation_seed_disabled_marker(ctx) is not None:
        return
    marker = {
        "schema_version": PRODUCT_RESET_SCHEMA_VERSION,
        "disabled": True,
        "disabled_at_utc": utc_timestamp(),
        "first_operation_id": canonical_uuid4(operation_id, generate=False),
    }
    product_reset_atomic_write_json(
        product_reset_homologation_seed_disabled_path(ctx),
        marker,
        PRIVATE_FILE_MODE,
    )


def product_reset_require_homologation_seed_disabled(ctx: ProductResetContext) -> None:
    if product_reset_load_homologation_seed_disabled_marker(ctx) is None:
        raise WriterError("product_reset_homologation_seed_disabled_marker_missing")
    seed_path = product_reset_rel_path(
        ctx,
        PRODUCT_RESET_HOMOLOGATION_SEED_REL,
        "homologation-seed",
    )
    if product_reset_existing_path_type(seed_path) != "missing":
        raise WriterError("product_reset_homologation_seed_reappeared")


def product_reset_remove_homologation_seed(
    ctx: ProductResetContext,
    intent: dict[str, Any],
) -> None:
    item = intent["homologation_seed"]
    seed_path = product_reset_rel_path(
        ctx,
        PRODUCT_RESET_HOMOLOGATION_SEED_REL,
        "homologation-seed",
    )
    seed_type = product_reset_existing_path_type(seed_path)
    if seed_type not in {"missing", "file"}:
        raise WriterError("product_reset_untrusted_path:homologation-seed")
    if item["removed"]:
        if seed_type != "missing":
            raise WriterError("product_reset_homologation_seed_reappeared")
        return

    if not item["delete_prepared"]:
        if seed_type == "file":
            seed_uid, seed_gid = product_reset_homologation_seed_owner_ids(ctx)
            product_reset_require_file_shape(
                seed_path,
                "homologation-seed",
                mode=PRIVATE_FILE_MODE,
                uid=seed_uid,
                gid=seed_gid,
                require_single_link=True,
            )
        item["source_existed"] = seed_type == "file"
        item["delete_prepared"] = True
        product_reset_write_intent_phase(ctx, intent, "homologation_seed_delete_prepared")
        product_reset_fault(ctx, "homologation_seed_delete_prepared")
    elif item["source_existed"] is False and seed_type != "missing":
        raise WriterError("product_reset_homologation_seed_reappeared")

    product_reset_ensure_homologation_seed_disabled_marker(ctx, intent["operation_id"])
    if not item["disabled_marker_written"]:
        item["disabled_marker_written"] = True
        product_reset_write_intent_phase(
            ctx,
            intent,
            "homologation_seed_disabled_marker_written",
        )
        product_reset_fault(ctx, "homologation_seed_disabled_marker_written")

    if seed_type == "file":
        seed_path.unlink()
        fsync_directory(seed_path.parent, required=True)
    item["removed"] = True
    product_reset_write_intent_phase(ctx, intent, "homologation_seed_removed")
    product_reset_fault(ctx, "homologation_seed_removed")


def product_reset_preflight_source_domain(ctx: ProductResetContext, path: pathlib.Path, label: str) -> None:
    owner_uid, owner_gid = product_reset_source_owner_ids(ctx)
    product_reset_require_dir_shape(
        path,
        label,
        mode=PRODUCT_RESET_RECREATE_MODE,
        uid=owner_uid,
        gid=owner_gid,
    )


def product_reset_preflight_config_tree(ctx: ProductResetContext, config_dir: pathlib.Path) -> None:
    config_path = config_dir / "config.json"
    config_uid, config_gid = product_reset_config_file_owner_ids(ctx)
    product_reset_require_file_shape(
        config_path,
        "active-config",
        mode=PRODUCT_RESET_CONFIG_FILE_MODE,
        uid=config_uid,
        gid=config_gid,
        require_single_link=True,
    )

    pending_dirs = [config_dir]
    scanned_entries = 0
    while pending_dirs:
        current = pending_dirs.pop()
        try:
            directory = os.scandir(current)
        except OSError as exc:
            raise WriterError("product_reset_config_scan_failed") from exc
        with directory:
            for entry in directory:
                scanned_entries += 1
                if scanned_entries > PRODUCT_RESET_CONFIG_SCAN_MAX_ENTRIES:
                    raise WriterError("product_reset_config_scan_limit")
                try:
                    entry_stat = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    raise WriterError("product_reset_config_scan_failed") from exc
                if stat.S_ISLNK(entry_stat.st_mode):
                    raise WriterError("product_reset_untrusted_path:config")
                if stat.S_ISDIR(entry_stat.st_mode):
                    if stat.S_IMODE(entry_stat.st_mode) & 0o022:
                        raise WriterError("product_reset_bad_mode:config")
                    pending_dirs.append(pathlib.Path(entry.path))
                    continue
                if not stat.S_ISREG(entry_stat.st_mode) or entry_stat.st_nlink != 1:
                    raise WriterError("product_reset_untrusted_path:config")
                if stat.S_IMODE(entry_stat.st_mode) & 0o027:
                    raise WriterError("product_reset_bad_mode:config")


def product_reset_require_empty_recreated_domain(path: pathlib.Path, label: str) -> None:
    try:
        with os.scandir(path) as entries:
            if next(entries, None) is not None:
                raise WriterError(f"product_reset_domain_reappeared:{label}")
    except WriterError:
        raise
    except OSError as exc:
        raise WriterError(f"product_reset_domain_scan_failed:{label}") from exc


def product_reset_preflight_sources(ctx: ProductResetContext, intent: dict[str, Any]) -> None:
    for rel in PRODUCT_RESET_FIXED_DOMAINS:
        item = intent["domains"][str(rel)]
        source = product_reset_rel_path(ctx, rel, str(rel))
        source_type = product_reset_existing_path_type(source)
        if item["moved"]:
            if source_type in {"symlink", "file", "other"}:
                raise WriterError(f"product_reset_untrusted_path:{rel}")
            if source_type == "dir":
                product_reset_preflight_source_domain(ctx, source, str(rel))
                product_reset_require_empty_recreated_domain(source, str(rel))
            continue
        if source_type == "missing":
            continue
        if source_type != "dir":
            raise WriterError(f"product_reset_untrusted_path:{rel}")
        product_reset_preflight_source_domain(ctx, source, str(rel))
        if rel == pathlib.Path("config"):
            product_reset_preflight_config_tree(ctx, source)

    last_item = intent["last_settings"]
    if not last_item["moved"]:
        last_path = product_reset_rel_path(ctx, PRODUCT_RESET_LAST_SETTINGS_REL, "last-settings")
        last_type = product_reset_existing_path_type(last_path)
        if last_type not in {"missing", "file"}:
            raise WriterError("product_reset_untrusted_path:last-settings")
        if last_type == "file":
            owner_uid, owner_gid = product_reset_source_owner_ids(ctx)
            product_reset_require_file_shape(
                last_path,
                "last-settings",
                mode=PRIVATE_FILE_MODE,
                uid=owner_uid,
                gid=owner_gid,
                require_single_link=True,
            )

    seed_item = intent["homologation_seed"]
    seed_path = product_reset_rel_path(
        ctx,
        PRODUCT_RESET_HOMOLOGATION_SEED_REL,
        "homologation-seed",
    )
    seed_type = product_reset_existing_path_type(seed_path)
    seed_disabled_marker = product_reset_load_homologation_seed_disabled_marker(ctx)
    if seed_type not in {"missing", "file"}:
        raise WriterError("product_reset_untrusted_path:homologation-seed")
    seed_delete_may_be_incomplete = (
        seed_item["delete_prepared"]
        and seed_item["source_existed"] is True
        and not seed_item["removed"]
    )
    if seed_disabled_marker is not None and seed_type != "missing" and not seed_delete_may_be_incomplete:
        raise WriterError("product_reset_homologation_seed_reappeared")
    if seed_item["disabled_marker_written"] and seed_disabled_marker is None:
        raise WriterError("product_reset_homologation_seed_disabled_marker_missing")
    if seed_item["removed"]:
        if seed_type != "missing":
            raise WriterError("product_reset_homologation_seed_reappeared")
    elif seed_item["delete_prepared"] and seed_item["source_existed"] is False:
        if seed_type != "missing":
            raise WriterError("product_reset_homologation_seed_reappeared")
    elif seed_type == "file":
        seed_uid, seed_gid = product_reset_homologation_seed_owner_ids(ctx)
        product_reset_require_file_shape(
            seed_path,
            "homologation-seed",
            mode=PRIVATE_FILE_MODE,
            uid=seed_uid,
            gid=seed_gid,
            require_single_link=True,
        )


def product_reset_pending_without_intent(ctx: ProductResetContext) -> dict[str, Any] | None:
    pending_path = product_reset_pending_credential_path(ctx)
    if product_reset_existing_path_type(pending_path) == "missing":
        return None
    pending = product_reset_load_json(pending_path, label="pending-credential", private_mode=PRIVATE_FILE_MODE)
    return product_reset_validate_pending_credential(pending)


def product_reset_load_intent(ctx: ProductResetContext) -> dict[str, Any] | None:
    intent_path = product_reset_intent_path(ctx)
    if product_reset_existing_path_type(intent_path) == "missing":
        return None
    intent = product_reset_load_json(intent_path, label="intent", private_mode=PRIVATE_FILE_MODE)
    return product_reset_validate_intent(intent)


def product_reset_noop_status() -> dict[str, Any]:
    return {
        "schema_version": PRODUCT_RESET_SCHEMA_VERSION,
        "code": "noop",
        "operation_id": None,
        "phase": "no_intent",
        "local_complete": False,
        "pending_credential": False,
        "graveyard_count": 0,
        "receipt_present": False,
        "gc_pending": False,
        "secret_public": False,
        "api_url_public": False,
        "environment_public": False,
        "station_public": False,
    }


def product_reset_public_status(ctx: ProductResetContext) -> dict[str, Any]:
    state_dir = product_reset_state_dir(ctx)
    if product_reset_existing_path_type(state_dir) == "missing":
        return product_reset_noop_status()
    product_reset_require_state_parent(ctx, state_dir)
    product_reset_require_private_state_dir(ctx, state_dir, "state")
    intent = product_reset_load_intent(ctx)
    pending_exists = product_reset_existing_path_type(product_reset_pending_credential_path(ctx)) != "missing"
    receipt_exists = product_reset_existing_path_type(product_reset_receipt_path(ctx)) != "missing"
    gc_pending = product_reset_load_gc_pending(ctx)
    if intent is None:
        pending = product_reset_pending_without_intent(ctx)
        if pending is None:
            if receipt_exists:
                receipt = product_reset_load_any_receipt(ctx)
                if receipt is None:
                    raise WriterError("product_reset_receipt_invalid")
                receipt_operation_id = receipt["operation_id"]
                return {
                    "schema_version": PRODUCT_RESET_SCHEMA_VERSION,
                    "code": "ok",
                    "operation_id": receipt_operation_id,
                    "phase": "finalized",
                    "local_complete": True,
                    "pending_credential": False,
                    "finalize_result": receipt.get("result"),
                    "graveyard_count": len(product_reset_list_graveyard_ids(ctx)),
                    "receipt_present": True,
                    "gc_pending": gc_pending is not None,
                    "secret_public": False,
                    "api_url_public": False,
                    "environment_public": False,
                    "station_public": False,
                }
            status = product_reset_noop_status()
            status["graveyard_count"] = len(product_reset_list_graveyard_ids(ctx))
            status["receipt_present"] = receipt_exists
            status["gc_pending"] = gc_pending is not None
            if gc_pending is not None:
                status.update(
                    {
                        "code": "ok",
                        "operation_id": gc_pending["operation_id"],
                        "phase": "gc_pending",
                        "local_complete": True,
                    }
                )
            return status
        return {
            "schema_version": PRODUCT_RESET_SCHEMA_VERSION,
            "code": "pending_revocation",
            "operation_id": pending["operation_id"],
            "phase": "credential_written_no_intent",
            "local_complete": False,
            "pending_credential": True,
            "graveyard_count": len(product_reset_list_graveyard_ids(ctx)),
            "receipt_present": receipt_exists,
            "gc_pending": gc_pending is not None,
            "secret_public": False,
            "api_url_public": False,
            "environment_public": False,
            "station_public": False,
        }
    phase = str(intent.get("phase") or "unknown")
    local_complete = phase == "local_complete"
    return {
        "schema_version": PRODUCT_RESET_SCHEMA_VERSION,
        "code": "pending_revocation" if pending_exists else "ok",
        "operation_id": intent["operation_id"],
        "phase": phase,
        "local_complete": local_complete,
        "pending_credential": pending_exists,
        "graveyard_count": len(product_reset_list_graveyard_ids(ctx)),
        "receipt_present": receipt_exists,
        "gc_pending": gc_pending is not None,
        "secret_public": False,
        "api_url_public": False,
        "environment_public": False,
        "station_public": False,
    }


def product_reset_start_or_resume(
    ctx: ProductResetContext,
    *,
    operation_id_raw: str | None,
    start: bool,
) -> dict[str, Any]:
    state_dir = product_reset_state_dir(ctx)
    if not start and product_reset_existing_path_type(state_dir) == "missing":
        return product_reset_noop_status()
    product_reset_prepare_state(ctx)

    intent = product_reset_load_intent(ctx)
    pending = product_reset_pending_without_intent(ctx)
    receipt = product_reset_load_any_receipt(ctx)
    gc_pending = product_reset_load_gc_pending(ctx)
    graveyard_ids = product_reset_list_graveyard_ids(ctx)
    if gc_pending is not None:
        if intent is not None or pending is not None:
            raise WriterError("product_reset_gc_state_conflict")
        if receipt is not None and receipt["operation_id"] != gc_pending["operation_id"]:
            raise WriterError("product_reset_gc_target_mismatch")
        if receipt is None:
            if graveyard_ids != [gc_pending["operation_id"]]:
                raise WriterError("product_reset_gc_target_mismatch")
            if start:
                raise WriterError("product_reset_gc_pending")
            return product_reset_public_status(ctx)
    elif intent is None and pending is None and receipt is None and graveyard_ids:
        if start:
            raise WriterError("product_reset_graveyard_gc_required")
        return product_reset_public_status(ctx)
    if receipt is not None:
        receipt_operation_id = receipt["operation_id"]
        if intent is not None:
            if intent["operation_id"] != receipt_operation_id:
                raise WriterError("product_reset_operation_id_mismatch")
            if intent.get("phase") != "local_complete":
                raise WriterError("product_reset_receipt_before_local_complete")
            completed = product_reset_complete_finalize_from_receipt(
                ctx,
                operation_id=receipt_operation_id,
                result=None,
            )
            if completed is None:
                raise WriterError("product_reset_receipt_invalid")
            return completed
        if pending is not None:
            if pending["operation_id"] != receipt_operation_id:
                raise WriterError("product_reset_operation_id_mismatch")
            completed = product_reset_complete_finalize_from_receipt(
                ctx,
                operation_id=receipt_operation_id,
                result=None,
            )
            if completed is None:
                raise WriterError("product_reset_receipt_invalid")
            return completed
        if start:
            raise WriterError("product_reset_onboarding_pending")
        return product_reset_public_status(ctx)

    if intent is not None:
        operation_id = intent["operation_id"]
        if operation_id_raw is not None and canonical_uuid4(operation_id_raw, generate=False) != operation_id:
            raise WriterError("product_reset_operation_id_mismatch")
        if pending is None:
            if intent.get("phase") != "intent_written" or any(
                item["moved"] or item["recreated"] for item in intent["domains"].values()
            ) or intent["last_settings"]["moved"] or intent["homologation_seed"]["delete_prepared"]:
                raise WriterError("product_reset_pending_credential_missing")
            product_reset_preflight_sources(ctx, intent)
            credential = product_reset_capture_active_credential(ctx, operation_id)
            product_reset_atomic_write_json(
                product_reset_pending_credential_path(ctx), credential, PRIVATE_FILE_MODE
            )
            product_reset_fault(ctx, "credential_written")
    else:
        if pending is not None:
            operation_id = pending["operation_id"]
            if operation_id_raw is not None and canonical_uuid4(operation_id_raw, generate=False) != operation_id:
                raise WriterError("product_reset_operation_id_mismatch")
            intent = product_reset_new_intent(operation_id)
            product_reset_write_intent(ctx, intent)
            product_reset_fault(ctx, "intent_written")
        elif not start:
            return product_reset_noop_status()
        else:
            operation_id = canonical_uuid4(operation_id_raw, generate=True)
            # Keep the first security check before reading or persisting the old secret.
            intent = product_reset_new_intent(operation_id)
            product_reset_preflight_sources(ctx, intent)
            credential = product_reset_capture_active_credential(ctx, operation_id)
            # The durable intent is the point after which firstboot must resume the reset.
            product_reset_write_intent(ctx, intent)
            product_reset_fault(ctx, "state_prepared")
            product_reset_atomic_write_json(
                product_reset_pending_credential_path(ctx), credential, PRIVATE_FILE_MODE
            )
            product_reset_fault(ctx, "credential_written")
            product_reset_fault(ctx, "intent_written")

    product_reset_preflight_sources(ctx, intent)
    product_reset_prepare_graveyard(ctx, operation_id)
    product_reset_fault(ctx, "graveyard_prepared")
    product_reset_remove_homologation_seed(ctx, intent)

    for rel in PRODUCT_RESET_FIXED_DOMAINS:
        product_reset_move_domain(ctx, intent, operation_id, rel)
    product_reset_move_last_settings(ctx, intent, operation_id)

    if intent.get("phase") != "local_complete":
        intent["completed_at_utc"] = utc_timestamp()
        product_reset_write_intent_phase(ctx, intent, "local_complete")
        product_reset_fault(ctx, "local_complete")
    return product_reset_public_status(ctx)


def product_reset_unlink_private_file(path: pathlib.Path, label: str) -> bool:
    path_type = product_reset_existing_path_type(path)
    if path_type == "missing":
        return False
    if path_type != "file":
        raise WriterError(f"product_reset_untrusted_path:{label}")
    path.unlink()
    fsync_directory(path.parent, required=True)
    return True


def product_reset_validate_receipt(
    receipt: dict[str, Any],
    *,
    operation_id: str,
    result: str | None,
) -> dict[str, Any]:
    expected_fields = {
        "schema_version",
        "operation_id",
        "result",
        "finalized_at_utc",
        "local_complete",
        "pending_credential_removed",
        "privacy",
    }
    product_reset_require_exact_keys(receipt, expected_fields, "product_reset_receipt_invalid")
    if receipt.get("schema_version") != PRODUCT_RESET_SCHEMA_VERSION:
        raise WriterError("product_reset_receipt_invalid")
    receipt_operation_id = canonical_uuid4(receipt.get("operation_id"), generate=False)
    if receipt_operation_id != operation_id:
        raise WriterError("product_reset_operation_id_mismatch")
    receipt_result = receipt.get("result")
    if receipt_result not in PRODUCT_RESET_FINALIZE_RESULTS:
        raise WriterError("product_reset_receipt_invalid")
    if result is not None and receipt_result != result:
        raise WriterError("product_reset_result_mismatch")
    product_reset_require_nonempty_string(receipt.get("finalized_at_utc"), "product_reset_receipt_invalid")
    if not product_reset_require_strict_bool(receipt.get("local_complete"), "product_reset_receipt_invalid"):
        raise WriterError("product_reset_receipt_invalid")
    if product_reset_require_strict_bool(receipt.get("pending_credential_removed"), "product_reset_receipt_invalid"):
        raise WriterError("product_reset_receipt_invalid")
    privacy = receipt.get("privacy")
    if not isinstance(privacy, dict):
        raise WriterError("product_reset_receipt_invalid")
    product_reset_require_exact_keys(
        privacy,
        {
            "secret_written_to_receipt",
            "api_url_written_to_receipt",
            "environment_written_to_receipt",
            "station_written_to_receipt",
        },
        "product_reset_receipt_invalid",
    )
    for privacy_value in privacy.values():
        if product_reset_require_strict_bool(privacy_value, "product_reset_receipt_invalid"):
            raise WriterError("product_reset_receipt_invalid")
    receipt["operation_id"] = receipt_operation_id
    return receipt


def product_reset_load_any_receipt(ctx: ProductResetContext) -> dict[str, Any] | None:
    receipt_path = product_reset_receipt_path(ctx)
    if product_reset_existing_path_type(receipt_path) == "missing":
        return None
    receipt = product_reset_load_json(receipt_path, label="receipt", private_mode=PRIVATE_FILE_MODE)
    operation_id = canonical_uuid4(receipt.get("operation_id"), generate=False)
    return product_reset_validate_receipt(receipt, operation_id=operation_id, result=None)


def product_reset_load_receipt(
    ctx: ProductResetContext,
    *,
    operation_id: str,
    result: str | None,
) -> dict[str, Any] | None:
    receipt_path = product_reset_receipt_path(ctx)
    if product_reset_existing_path_type(receipt_path) == "missing":
        return None
    receipt = product_reset_load_json(receipt_path, label="receipt", private_mode=PRIVATE_FILE_MODE)
    return product_reset_validate_receipt(receipt, operation_id=operation_id, result=result)


def product_reset_validate_gc_pending(value: dict[str, Any]) -> dict[str, Any]:
    product_reset_require_exact_keys(
        value,
        {"schema_version", "operation_id", "queued_at_utc"},
        "product_reset_gc_pending_invalid",
    )
    if value.get("schema_version") != PRODUCT_RESET_SCHEMA_VERSION:
        raise WriterError("product_reset_gc_pending_invalid")
    value["operation_id"] = canonical_uuid4(value.get("operation_id"), generate=False)
    product_reset_require_nonempty_string(
        value.get("queued_at_utc"),
        "product_reset_gc_pending_invalid",
    )
    return value


def product_reset_load_gc_pending(ctx: ProductResetContext) -> dict[str, Any] | None:
    marker_path = product_reset_gc_pending_path(ctx)
    if product_reset_existing_path_type(marker_path) == "missing":
        return None
    marker = product_reset_load_json(marker_path, label="gc-pending", private_mode=PRIVATE_FILE_MODE)
    return product_reset_validate_gc_pending(marker)


def product_reset_queue_gc(ctx: ProductResetContext, operation_id: str) -> dict[str, Any]:
    operation_id = canonical_uuid4(operation_id, generate=False)
    graveyard_ids = product_reset_list_graveyard_ids(ctx)
    if graveyard_ids != [operation_id]:
        raise WriterError("product_reset_gc_target_mismatch")
    existing = product_reset_load_gc_pending(ctx)
    if existing is not None:
        if existing["operation_id"] != operation_id:
            raise WriterError("product_reset_gc_target_mismatch")
        return existing
    marker = {
        "schema_version": PRODUCT_RESET_SCHEMA_VERSION,
        "operation_id": operation_id,
        "queued_at_utc": utc_timestamp(),
    }
    product_reset_atomic_write_json(product_reset_gc_pending_path(ctx), marker, PRIVATE_FILE_MODE)
    return marker


def product_reset_finalized_status(ctx: ProductResetContext, operation_id: str, result: str) -> dict[str, Any]:
    return {
        "schema_version": PRODUCT_RESET_SCHEMA_VERSION,
        "code": "ok",
        "operation_id": operation_id,
        "phase": "finalized",
        "local_complete": True,
        "pending_credential": product_reset_existing_path_type(product_reset_pending_credential_path(ctx)) != "missing",
        "finalize_result": result,
        "graveyard_count": len(product_reset_list_graveyard_ids(ctx)),
        "receipt_present": True,
        "gc_pending": product_reset_load_gc_pending(ctx) is not None,
        "secret_public": False,
        "api_url_public": False,
        "environment_public": False,
        "station_public": False,
    }


def product_reset_complete_finalize_from_receipt(
    ctx: ProductResetContext,
    *,
    operation_id: str,
    result: str | None,
) -> dict[str, Any] | None:
    receipt = product_reset_load_receipt(ctx, operation_id=operation_id, result=result)
    if receipt is None:
        return None
    product_reset_require_homologation_seed_disabled(ctx)
    pending_path = product_reset_pending_credential_path(ctx)
    if product_reset_existing_path_type(pending_path) != "missing":
        pending = product_reset_pending_without_intent(ctx)
        if pending is not None and pending["operation_id"] != operation_id:
            raise WriterError("product_reset_operation_id_mismatch")
        product_reset_unlink_private_file(pending_path, "pending-credential")
        product_reset_fault(ctx, "credential_unlinked")
    intent_path = product_reset_intent_path(ctx)
    if product_reset_existing_path_type(intent_path) != "missing":
        intent = product_reset_load_intent(ctx)
        if intent is not None and intent["operation_id"] != operation_id:
            raise WriterError("product_reset_operation_id_mismatch")
        product_reset_unlink_private_file(intent_path, "intent")
        product_reset_fault(ctx, "intent_unlinked")
    return product_reset_finalized_status(ctx, operation_id, str(receipt["result"]))


def product_reset_finalize(
    ctx: ProductResetContext,
    *,
    operation_id_raw: str | None,
    result: str | None,
) -> dict[str, Any]:
    operation_id = canonical_uuid4(operation_id_raw, generate=False)
    if result not in PRODUCT_RESET_FINALIZE_RESULTS:
        raise WriterError("product_reset_result_invalid")
    state_dir = product_reset_state_dir(ctx)
    if product_reset_existing_path_type(state_dir) == "missing":
        raise WriterError("product_reset_no_active_intent")
    product_reset_prepare_state(ctx)
    intent = product_reset_load_intent(ctx)
    pending_path = product_reset_pending_credential_path(ctx)
    receipt_path = product_reset_receipt_path(ctx)
    finalized_from_receipt = product_reset_complete_finalize_from_receipt(ctx, operation_id=operation_id, result=result)
    if finalized_from_receipt is not None:
        return product_reset_finalized_status(ctx, operation_id, str(finalized_from_receipt["finalize_result"]))

    if intent is None:
        if (
            product_reset_existing_path_type(pending_path) != "missing"
            or product_reset_existing_path_type(receipt_path) != "missing"
        ):
            raise WriterError("product_reset_no_active_intent")
        raise WriterError("product_reset_no_active_intent")
    if intent["operation_id"] != operation_id:
        raise WriterError("product_reset_operation_id_mismatch")
    if intent.get("phase") != "local_complete":
        raise WriterError("product_reset_local_not_complete")
    product_reset_preflight_sources(ctx, intent)

    receipt = {
        "schema_version": PRODUCT_RESET_SCHEMA_VERSION,
        "operation_id": operation_id,
        "result": result,
        "finalized_at_utc": utc_timestamp(),
        "local_complete": True,
        "pending_credential_removed": False,
        "privacy": {
            "secret_written_to_receipt": False,
            "api_url_written_to_receipt": False,
            "environment_written_to_receipt": False,
            "station_written_to_receipt": False,
        },
    }
    product_reset_atomic_write_json(receipt_path, receipt, PRIVATE_FILE_MODE)
    product_reset_fault(ctx, "receipt_written")
    finalized = product_reset_complete_finalize_from_receipt(ctx, operation_id=operation_id, result=result)
    if finalized is None:
        raise WriterError("product_reset_receipt_invalid")
    return product_reset_finalized_status(ctx, operation_id, result)


def product_reset_complete_onboarding(ctx: ProductResetContext) -> dict[str, Any]:
    state_dir = product_reset_state_dir(ctx)
    if product_reset_existing_path_type(state_dir) == "missing":
        return product_reset_noop_status()
    product_reset_prepare_state(ctx)
    intent = product_reset_load_intent(ctx)
    pending = product_reset_pending_without_intent(ctx)
    receipt = product_reset_load_any_receipt(ctx)
    if intent is not None or pending is not None:
        raise WriterError("product_reset_onboarding_not_ready")
    if receipt is None:
        return product_reset_noop_status()
    product_reset_require_homologation_seed_disabled(ctx)
    product_reset_validate_new_onboarding_config(ctx)
    gc_pending = product_reset_queue_gc(ctx, receipt["operation_id"])
    product_reset_fault(ctx, "gc_pending_written")
    product_reset_unlink_private_file(product_reset_receipt_path(ctx), "receipt")
    product_reset_fault(ctx, "onboarding_receipt_unlinked")
    return {
        "schema_version": PRODUCT_RESET_SCHEMA_VERSION,
        "code": "ok",
        "operation_id": receipt["operation_id"],
        "phase": "onboarding_complete",
        "local_complete": True,
        "pending_credential": False,
        "graveyard_count": len(product_reset_list_graveyard_ids(ctx)),
        "receipt_present": False,
        "gc_pending": gc_pending["operation_id"] == receipt["operation_id"],
        "secret_public": False,
        "api_url_public": False,
        "environment_public": False,
        "station_public": False,
    }


def product_reset_validate_new_onboarding_config(ctx: ProductResetContext) -> None:
    config_dir = product_reset_rel_path(ctx, pathlib.Path("config"), "config")
    config_path = config_dir / "config.json"
    if product_reset_existing_path_type(config_path) == "missing":
        raise WriterError("product_reset_onboarding_config_missing")
    try:
        product_reset_preflight_source_domain(ctx, config_dir, "config")
        product_reset_preflight_config_tree(ctx, config_dir)
        candidate = product_reset_load_json(
            config_path,
            label="active-config",
            private_mode=PRODUCT_RESET_CONFIG_FILE_MODE,
        )
        validation = validate_real_dry_run(candidate)
    except WriterError as exc:
        raise WriterError("product_reset_onboarding_config_invalid") from exc
    if validation.get("valid") is not True:
        raise WriterError("product_reset_onboarding_config_invalid")


def product_reset_gc(ctx: ProductResetContext, *, max_remove: int) -> dict[str, Any]:
    if max_remove != 1:
        raise WriterError("product_reset_gc_bound_invalid")
    state_dir = product_reset_state_dir(ctx)
    if product_reset_existing_path_type(state_dir) == "missing":
        result = product_reset_noop_status()
        result["code"] = "ok"
        result["phase"] = "gc"
        result["graveyards_removed"] = 0
        return result
    product_reset_prepare_state(ctx)
    if (
        product_reset_load_intent(ctx) is not None
        or product_reset_pending_without_intent(ctx) is not None
        or product_reset_load_any_receipt(ctx) is not None
    ):
        raise WriterError("product_reset_gc_state_conflict")
    gc_pending = product_reset_load_gc_pending(ctx)
    if gc_pending is None:
        result = product_reset_public_status(ctx)
        result["code"] = "ok"
        result["phase"] = "gc"
        result["graveyards_removed"] = 0
        return result
    operation_id = gc_pending["operation_id"]
    graveyard_ids = product_reset_list_graveyard_ids(ctx)
    if graveyard_ids not in ([], [operation_id]):
        raise WriterError("product_reset_gc_target_mismatch")
    removed = 1 if product_reset_remove_graveyard(ctx, operation_id) else 0
    product_reset_fault(ctx, "gc_graveyard_removed")
    product_reset_unlink_private_file(product_reset_gc_pending_path(ctx), "gc-pending")
    product_reset_fault(ctx, "gc_pending_unlinked")
    result = product_reset_public_status(ctx)
    result["code"] = "ok"
    result["phase"] = "gc"
    result["graveyards_removed"] = removed
    result["gc_pending"] = False
    return result


def product_reset_cli_exit_code(status: dict[str, Any]) -> int:
    if status.get("code") == "noop":
        return 11
    if status.get("pending_credential") or status.get("code") == "pending_revocation":
        return 10
    return 0


def product_reset_print_status(status: dict[str, Any]) -> None:
    ordered_keys = (
        "code",
        "operation_id",
        "phase",
        "local_complete",
        "pending_credential",
        "finalize_result",
        "graveyard_count",
        "graveyards_removed",
        "receipt_present",
        "gc_pending",
        "secret_public",
        "api_url_public",
        "environment_public",
        "station_public",
    )
    for key in ordered_keys:
        if key in status:
            value = status[key]
            if isinstance(value, bool):
                rendered = str(value).lower()
            elif value is None:
                rendered = "none"
            else:
                rendered = str(value)
            print(f"product_reset_{key}={rendered}")


def file_mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def synthetic_api_key() -> str:
    return secrets.token_hex(24).upper()


def build_synthetic_candidate() -> dict[str, Any]:
    return {
        "api_url": "https://api.sandbox.localhost/search",
        "api_key": synthetic_api_key(),
        "environment_id": "ENVIRONMENT_ALPHA_001",
        "station_id": "STATION_ALPHA_001",
        "cache_dir": "/data/media/kiosky-player",
        "state_dir": "/data/state/kiosky-player",
        "status_file": "/tmp/kiosky-status.json",
        "ipc_path": "/tmp/kiosky/mpv.sock",
        "runtime_dir": "/tmp/kiosky",
        "strict_paths_enabled": True,
        "preload_next": False,
        "mpv_query_uses_fresh_ipc": True,
        "mpv_vo": "gpu",
        "mpv_gpu_context": "drm",
        "mpv_ao": "null",
        "low_resource_mode": False,
    }


def write_self_test_candidate(path: pathlib.Path, config: dict[str, Any]) -> None:
    prepare_private_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, sort_keys=True)
        handle.write("\n")
    path.chmod(PRIVATE_FILE_MODE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_raises_writer_error(fn: Any, message: str) -> None:
    try:
        fn()
    except WriterError:
        return
    raise AssertionError(message)


def assert_raises_writer_error_code(fn: Any, code: str, message: str) -> None:
    try:
        fn()
    except WriterError as exc:
        assert_true(str(exc) == code, message)
        return
    raise AssertionError(message)


def product_reset_self_test_uuid(index: int) -> str:
    return f"00000000-0000-4000-8000-{index:012x}"


def product_reset_self_test_prepare_dir(path: pathlib.Path, mode: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(mode)


def product_reset_self_test_write_text(path: pathlib.Path, content: str, mode: int = PRIVATE_FILE_MODE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)


def product_reset_self_test_write_json(path: pathlib.Path, value: dict[str, Any], mode: int = PRIVATE_FILE_MODE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(mode)


def product_reset_self_test_write_new_config(data: pathlib.Path, index: int) -> None:
    candidate = build_synthetic_candidate()
    candidate.update(
        {
            "api_url": f"https://api{index}.example.com/search",
            "api_key": f"NEW_CONFIG_SECRET_{index:04d}_1234567890",
            "environment_id": f"NEW_ENVIRONMENT_{index:04d}",
            "station_id": f"NEW_STATION_{index:04d}",
        }
    )
    product_reset_self_test_write_json(data / "config/config.json", candidate, PRODUCT_RESET_CONFIG_FILE_MODE)


def product_reset_self_test_fixture(root: pathlib.Path, index: int) -> dict[str, Any]:
    data = root / f"data-{index}"
    product_reset_self_test_prepare_dir(data, 0o755)
    parent_modes = {
        pathlib.Path("media"): 0o711,
        pathlib.Path("state"): 0o755,
        pathlib.Path("spool"): 0o751,
        pathlib.Path("logs"): 0o715,
        pathlib.Path("state/totem-appliance"): 0o755,
    }
    for rel, mode in parent_modes.items():
        product_reset_self_test_prepare_dir(data / rel, mode)

    active_config = build_synthetic_candidate()
    active_config.update(
        {
            "api_url": "https://reset.example.invalid/search",
            "api_key": f"RESET_SECRET_VALUE_{index:02d}_1234567890",
            "api_token_id": f"33333333-4444-4555-8666-{index:012x}",
            "environment_id": "11111111-2222-4333-8444-555555555555",
            "station_id": "22222222-3333-4444-8555-666666666666",
        }
    )
    for rel in PRODUCT_RESET_FIXED_DOMAINS:
        product_reset_self_test_prepare_dir(data / rel, PRODUCT_RESET_RECREATE_MODE)
        product_reset_self_test_write_text(data / rel / "marker.txt", f"moved:{rel}\n")
    product_reset_self_test_write_json(data / "config/config.json", active_config, REAL_ACTIVE_CONFIG_MODE)
    product_reset_self_test_prepare_dir(data / "config/backups", PRIVATE_DIR_MODE)
    product_reset_self_test_write_json(
        data / "config/backups/old-config.json",
        active_config,
        PRIVATE_FILE_MODE,
    )
    product_reset_self_test_write_json(
        data / PRODUCT_RESET_LAST_SETTINGS_REL,
        {
            "screen": "settings",
            "rotation_deg": 90,
            "api_key": active_config["api_key"],
            "environment_id": active_config["environment_id"],
            "station_id": active_config["station_id"],
        },
    )
    homologation_seed_secret = f"HOMOLOGATION_SEED_SECRET_{index:04d}_1234567890"
    product_reset_self_test_write_json(
        data / PRODUCT_RESET_HOMOLOGATION_SEED_REL,
        {
            "api_url": "https://homologation-seed.example.invalid/search",
            "api_key": homologation_seed_secret,
            "station_id": f"HOMOLOGATION_STATION_{index:04d}",
        },
    )
    preserved_files = (
        pathlib.Path("wifi/connection.nmconnection"),
        pathlib.Path("state/totem-settings/orientation.json"),
        pathlib.Path("core/releases/current"),
        pathlib.Path("ota/releases/current"),
        pathlib.Path("state/quarantine/quarantine.json"),
        pathlib.Path("state/tokens/token.json"),
        pathlib.Path("canary/healthy"),
        pathlib.Path("state/totem-appliance/manifest-owned.txt"),
    )
    for rel in preserved_files:
        product_reset_self_test_write_text(data / rel, f"preserved:{rel}\n")
    return {
        "data": data,
        "active_config": active_config,
        "homologation_seed_secret": homologation_seed_secret,
        "parent_modes": parent_modes,
        "preserved_files": preserved_files,
    }


def product_reset_self_test_context(
    data: pathlib.Path,
    *,
    owner_calls: list[tuple[pathlib.Path, int, int]] | None = None,
    fault_after: str | None = None,
) -> ProductResetContext:
    def fake_chown(path: pathlib.Path, uid: int, gid: int) -> None:
        if owner_calls is not None:
            owner_calls.append((path.relative_to(data), uid, gid))

    return build_product_reset_context(
        data_root_raw=str(data),
        allow_test_root=True,
        owner_uid=1234,
        owner_gid=5678,
        owner_applier=fake_chown,
        fingerprint_provider=lambda: "fixture-host-000000000000",
        fault_after=fault_after,
    )


def product_reset_assert_no_forbidden_values(value: Any, forbidden_values: tuple[str, ...], message: str) -> None:
    content = json.dumps(value, sort_keys=True)
    for forbidden in forbidden_values:
        assert_true(forbidden not in content, message)


def product_reset_files_containing(data: pathlib.Path, needle: str) -> list[pathlib.Path]:
    matches: list[pathlib.Path] = []
    for path in sorted(data.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if needle in content:
            matches.append(path.relative_to(data))
    return matches


def run_product_reset_smoke_self_test() -> None:
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c26a-product-reset-smoke-", dir="/tmp"))
    try:
        fsync_directory(root, required=True)
        fsync_directory(root / "missing-best-effort")
        assert_raises_writer_error_code(
            lambda: fsync_directory(root / "missing-required", required=True),
            "product_reset_directory_fsync_failed",
            "product reset directory fsync must fail closed",
        )
        fixture = product_reset_self_test_fixture(root, 200)
        data = fixture["data"]
        operation_id = product_reset_self_test_uuid(200)
        ctx = product_reset_self_test_context(data)
        started = product_reset_start_or_resume(ctx, operation_id_raw=operation_id, start=True)
        assert_true(started["phase"] == "local_complete", "product reset smoke should complete local reset")
        state_dir = data / PRODUCT_RESET_STATE_REL
        assert_true(
            (state_dir / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME).exists(),
            "product reset smoke should retain pending credential",
        )
        finalized = product_reset_finalize(ctx, operation_id_raw=operation_id, result="revoked")
        assert_true(finalized["phase"] == "finalized", "product reset smoke should finalize")
        assert_true(
            not (state_dir / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME).exists(),
            "product reset smoke should remove pending credential",
        )
        product_reset_self_test_write_new_config(data, 200)
        completed = product_reset_complete_onboarding(ctx)
        assert_true(
            completed["phase"] == "onboarding_complete",
            "product reset smoke should complete onboarding",
        )
        assert_true(completed["gc_pending"], "product reset smoke should defer bulk cleanup")
        gc_status = product_reset_gc(ctx, max_remove=1)
        assert_true(gc_status["graveyards_removed"] == 1, "product reset smoke should clean exact graveyard")
        assert_true(product_reset_public_status(ctx)["code"] == "noop", "product reset smoke should clear handoff")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_product_reset_self_test() -> None:
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c26a-product-reset-self-test-", dir="/tmp"))
    try:
        expected_digest = uuid.uuid5(uuid.NAMESPACE_DNS, "fixture host:machine-id-fixture").hex[:12]
        assert_true(
            product_reset_device_fingerprint(hostname="fixture host", machine_id="machine-id-fixture")
            == f"fixture-host-{expected_digest}",
            "product reset fingerprint should match visual wizard algorithm",
        )
        assert_raises_writer_error(
            lambda: canonical_uuid4("00000000-0000-1000-8000-000000000001", generate=False),
            "non-v4 operation id should fail",
        )
        assert_raises_writer_error(
            lambda: canonical_uuid4("00000000-0000-4000-8000-00000000000A", generate=False),
            "non-canonical operation id should fail",
        )
        strict_intent = product_reset_new_intent(product_reset_self_test_uuid(100))
        strict_intent["domains"]["config"]["moved"] = 1
        assert_raises_writer_error(
            lambda: product_reset_validate_intent(strict_intent),
            "intent booleans must reject integer coercion",
        )
        strict_receipt = {
            "schema_version": PRODUCT_RESET_SCHEMA_VERSION,
            "operation_id": product_reset_self_test_uuid(100),
            "result": "revoked",
            "finalized_at_utc": utc_timestamp(),
            "local_complete": 1,
            "pending_credential_removed": False,
            "privacy": {
                "secret_written_to_receipt": False,
                "api_url_written_to_receipt": False,
                "environment_written_to_receipt": False,
                "station_written_to_receipt": False,
            },
        }
        assert_raises_writer_error(
            lambda: product_reset_validate_receipt(
                strict_receipt,
                operation_id=product_reset_self_test_uuid(100),
                result="revoked",
            ),
            "receipt booleans must reject integer coercion",
        )
        strict_receipt["local_complete"] = True
        strict_receipt["unexpected"] = False
        assert_raises_writer_error(
            lambda: product_reset_validate_receipt(
                strict_receipt,
                operation_id=product_reset_self_test_uuid(100),
                result="revoked",
            ),
            "receipt keys must be exact",
        )
        assert_raises_writer_error(
            lambda: build_product_reset_context(
                data_root_raw=str(root / "not-real"),
                enable_real_write=True,
                confirm_service_stopped=True,
            ),
            "CLI product reset root should reject non-/data outside self-test injection",
        )

        mountinfo_path = root / "mountinfo"
        mount_target = root / "graveyard-target"
        product_reset_self_test_prepare_dir(mount_target, PRIVATE_DIR_MODE)
        mountinfo_path.write_text(
            "1 0 0:1 / / rw - ext4 /dev/root rw\n"
            f"2 1 0:2 / {mount_target}/nested rw - tmpfs tmpfs rw\n",
            encoding="utf-8",
        )
        parsed_mounts = product_reset_mount_points(mountinfo_path)
        assert_raises_writer_error_code(
            lambda: product_reset_require_no_mounts_below(
                mount_target,
                mount_points=parsed_mounts,
            ),
            "product_reset_graveyard_contains_mount",
            "graveyard cleanup must reject an internal mountpoint",
        )

        bad_state_fixture = product_reset_self_test_fixture(root, 101)
        bad_state_dir = bad_state_fixture["data"] / PRODUCT_RESET_STATE_REL
        product_reset_self_test_prepare_dir(bad_state_dir, 0o755)
        assert_raises_writer_error(
            lambda: product_reset_start_or_resume(
                product_reset_self_test_context(bad_state_fixture["data"]),
                operation_id_raw=product_reset_self_test_uuid(101),
                start=True,
            ),
            "precreated product-reset state with wrong mode should fail closed",
        )
        bad_graveyard_fixture = product_reset_self_test_fixture(root, 102)
        bad_graveyard_state = bad_graveyard_fixture["data"] / PRODUCT_RESET_STATE_REL
        bad_graveyard = bad_graveyard_fixture["data"] / PRODUCT_RESET_GRAVEYARD_REL
        product_reset_self_test_prepare_dir(bad_graveyard_state, PRIVATE_DIR_MODE)
        product_reset_self_test_prepare_dir(bad_graveyard, 0o755)
        assert_raises_writer_error(
            lambda: product_reset_start_or_resume(
                product_reset_self_test_context(bad_graveyard_fixture["data"]),
                operation_id_raw=product_reset_self_test_uuid(102),
                start=True,
            ),
            "precreated graveyard with wrong mode should fail closed",
        )
        assert_true(
            (bad_graveyard_fixture["data"] / "config/config.json").exists(),
            "bad graveyard trust check should not move active config",
        )

        noop_fixture = product_reset_self_test_fixture(root, 1)
        noop_ctx = product_reset_self_test_context(noop_fixture["data"])
        noop_resume = product_reset_start_or_resume(noop_ctx, operation_id_raw=None, start=False)
        assert_true(noop_resume["code"] == "noop", "resume without intent should be noop")
        assert_true(product_reset_cli_exit_code(noop_resume) == 11, "noop resume should use exit 11")
        noop_status = product_reset_public_status(noop_ctx)
        assert_true(noop_status["code"] == "noop", "status without intent should be noop")

        invalid_cases: tuple[tuple[str, Any, Any], ...] = (
            ("api_url", "http://reset.example.invalid/search", None),
            ("api_url", "https://user:pass@reset.example.invalid/search", None),
            ("api_key", "placeholder", None),
            ("api_token_id", "not-a-uuid", None),
            ("fingerprint", None, lambda: "x" * 201),
        )
        for offset, (field, value, fingerprint_provider) in enumerate(invalid_cases, start=110):
            invalid_fixture = product_reset_self_test_fixture(root, offset)
            invalid_data = invalid_fixture["data"]
            if field != "fingerprint":
                invalid_config = dict(invalid_fixture["active_config"])
                invalid_config[field] = value
                product_reset_self_test_write_json(invalid_data / "config/config.json", invalid_config, REAL_ACTIVE_CONFIG_MODE)
            invalid_ctx = build_product_reset_context(
                data_root_raw=str(invalid_data),
                allow_test_root=True,
                owner_uid=1234,
                owner_gid=5678,
                owner_applier=lambda _path, _uid, _gid: None,
                fingerprint_provider=fingerprint_provider or (lambda: "fixture-host-000000000000"),
            )
            assert_raises_writer_error(
                lambda ctx=invalid_ctx, op=product_reset_self_test_uuid(offset): product_reset_start_or_resume(
                    ctx,
                    operation_id_raw=op,
                    start=True,
                ),
                f"invalid product reset credential should fail before data move: {field}",
            )
            assert_true((invalid_data / "config/config.json").exists(), f"invalid {field} should preserve config")
            assert_true(not (invalid_data / PRODUCT_RESET_STATE_REL / PRODUCT_RESET_INTENT_FILENAME).exists(), f"invalid {field} should not write intent")
            assert_true(not (invalid_data / PRODUCT_RESET_STATE_REL / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME).exists(), f"invalid {field} should not write pending credential")

        insecure_dir_fixture = product_reset_self_test_fixture(root, 115)
        insecure_dir_data = insecure_dir_fixture["data"]
        (insecure_dir_data / "media/kiosky-player").chmod(0o777)
        assert_raises_writer_error(
            lambda: product_reset_start_or_resume(
                product_reset_self_test_context(insecure_dir_data),
                operation_id_raw=product_reset_self_test_uuid(115),
                start=True,
            ),
            "world-writable fixed domain must fail preflight",
        )
        assert_true(
            not (insecure_dir_data / PRODUCT_RESET_STATE_REL / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME).exists(),
            "insecure directory must fail before capturing the credential",
        )

        insecure_file_fixture = product_reset_self_test_fixture(root, 116)
        insecure_file_data = insecure_file_fixture["data"]
        (insecure_file_data / "config/config.json").chmod(0o666)
        assert_raises_writer_error(
            lambda: product_reset_start_or_resume(
                product_reset_self_test_context(insecure_file_data),
                operation_id_raw=product_reset_self_test_uuid(116),
                start=True,
            ),
            "world-writable active config must fail preflight",
        )
        assert_true(
            not (insecure_file_data / PRODUCT_RESET_STATE_REL / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME).exists(),
            "insecure config mode must fail before capturing the credential",
        )

        hardlink_fixture = product_reset_self_test_fixture(root, 117)
        hardlink_data = hardlink_fixture["data"]
        os.link(hardlink_data / "config/config.json", hardlink_data / "config-secret-link.json")
        assert_raises_writer_error(
            lambda: product_reset_start_or_resume(
                product_reset_self_test_context(hardlink_data),
                operation_id_raw=product_reset_self_test_uuid(117),
                start=True,
            ),
            "hardlinked active config must fail before the old secret can survive reset",
        )
        assert_true(
            not (hardlink_data / PRODUCT_RESET_STATE_REL / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME).exists(),
            "hardlinked config must fail before capturing the credential",
        )

        fixture = product_reset_self_test_fixture(root, 2)
        data = fixture["data"]
        operation_id = product_reset_self_test_uuid(2)
        owner_calls: list[tuple[pathlib.Path, int, int]] = []
        ctx = product_reset_self_test_context(data, owner_calls=owner_calls)
        status = product_reset_start_or_resume(ctx, operation_id_raw=operation_id, start=True)
        assert_true(status["phase"] == "local_complete", "product reset should complete local reset")
        assert_true(status["pending_credential"], "local complete should retain pending credential")
        assert_true(product_reset_cli_exit_code(status) == 10, "local complete pending revocation should use exit 10")
        assert_raises_writer_error_code(
            lambda: product_reset_complete_onboarding(ctx),
            "product_reset_onboarding_not_ready",
            "onboarding completion must reject an active intent or pending credential",
        )

        state_dir = data / PRODUCT_RESET_STATE_REL
        graveyard_op = data / PRODUCT_RESET_GRAVEYARD_REL / operation_id
        assert_true(file_mode(state_dir) == PRIVATE_DIR_MODE, "product reset state dir should be 0700")
        assert_true(file_mode(graveyard_op) == PRIVATE_DIR_MODE, "product reset graveyard op dir should be 0700")
        assert_true(file_mode(state_dir / PRODUCT_RESET_INTENT_FILENAME) == PRIVATE_FILE_MODE, "product reset intent should be 0600")
        assert_true(file_mode(state_dir / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME) == PRIVATE_FILE_MODE, "pending credential should be 0600")
        for rel, mode in fixture["parent_modes"].items():
            assert_true(file_mode(data / rel) == mode, f"preserved parent mode changed for {rel}")
        for rel in PRODUCT_RESET_FIXED_DOMAINS:
            assert_true((data / rel).is_dir(), f"recreated domain missing: {rel}")
            assert_true(file_mode(data / rel) == PRODUCT_RESET_RECREATE_MODE, f"recreated domain mode should be 0750: {rel}")
        assert_true(
            sorted(call[0] for call in owner_calls) == sorted(PRODUCT_RESET_FIXED_DOMAINS),
            "recreated domains should receive injected owner calls",
        )
        assert_true(all(uid == 1234 and gid == 5678 for _path, uid, gid in owner_calls), "owner injection used wrong ids")

        for rel in fixture["preserved_files"]:
            assert_true((data / rel).exists(), f"preserved file missing after reset: {rel}")
        for rel in PRODUCT_RESET_FIXED_DOMAINS:
            if rel == pathlib.Path("config"):
                assert_true(
                    not (graveyard_op / rel / "marker.txt").exists(),
                    "graveyard config should not retain the old marker",
                )
                assert_true(
                    not (graveyard_op / rel / "backups").exists(),
                    "graveyard config should not retain old backups",
                )
            else:
                assert_true((graveyard_op / rel / "marker.txt").exists(), f"domain not moved to graveyard: {rel}")
        assert_true(not (data / PRODUCT_RESET_LAST_SETTINGS_REL).exists(), "last settings should move out of active state")
        assert_true(
            not (data / PRODUCT_RESET_HOMOLOGATION_SEED_REL).exists(),
            "homologation seed should be unlinked before active config moves",
        )
        seed_disabled_path = state_dir / PRODUCT_RESET_HOMOLOGATION_SEED_DISABLED_FILENAME
        assert_true(
            file_mode(seed_disabled_path) == PRIVATE_FILE_MODE,
            "homologation seed disabled marker should be private and durable",
        )
        assert_true(
            not (graveyard_op / PRODUCT_RESET_LAST_SETTINGS_REL).exists(),
            "last settings should be deleted instead of archived",
        )
        assert_true(
            len(list((data / PRODUCT_RESET_GRAVEYARD_REL).iterdir())) == 1,
            "exactly one graveyard operation should exist",
        )

        active = fixture["active_config"]
        forbidden = (
            active["api_key"],
            active["api_url"],
            active["api_token_id"],
            active["environment_id"],
            active["station_id"],
        )
        intent = product_reset_load_json(state_dir / PRODUCT_RESET_INTENT_FILENAME, label="intent", private_mode=PRIVATE_FILE_MODE)
        pending = product_reset_load_json(
            state_dir / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME,
            label="pending-credential",
            private_mode=PRIVATE_FILE_MODE,
        )
        product_reset_assert_no_forbidden_values(intent, forbidden, "intent leaked private reset values")
        product_reset_assert_no_forbidden_values(status, forbidden, "status leaked private reset values")
        assert_true(pending["api_key"] == active["api_key"], "pending credential should retain api_key")
        assert_true(pending["api_url"] == active["api_url"], "pending credential should retain api_url")
        assert_true(pending["api_token_id"] == active["api_token_id"], "pending credential should retain api_token_id")
        assert_true("environment_id" not in pending and "station_id" not in pending, "pending credential should omit environment/station")
        sanitized_graveyard_config = product_reset_load_json(graveyard_op / "config/config.json", label="graveyard-config")
        product_reset_assert_no_forbidden_values(
            sanitized_graveyard_config,
            forbidden,
            "graveyard config leaked private reset values",
        )
        assert_true(
            product_reset_files_containing(data, active["api_key"])
            == [PRODUCT_RESET_STATE_REL / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME],
            "api_key should exist only in pending credential after local reset",
        )
        assert_true(product_reset_files_containing(data, active["api_url"]) == [PRODUCT_RESET_STATE_REL / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME], "api_url should exist only in pending credential after local reset")
        assert_true(product_reset_files_containing(data, active["environment_id"]) == [], "environment_id should not leak after local reset")
        assert_true(product_reset_files_containing(data, active["station_id"]) == [], "station_id should not leak after local reset")
        assert_true(
            product_reset_files_containing(data, fixture["homologation_seed_secret"]) == [],
            "homologation seed secret must be sanitized instead of archived",
        )
        assert_true(not (data / "config/config.json").exists(), "old active config must never be restored")

        reappeared_fixture = product_reset_self_test_fixture(root, 121)
        reappeared_data = reappeared_fixture["data"]
        reappeared_op = product_reset_self_test_uuid(121)
        assert_raises_writer_error(
            lambda: product_reset_start_or_resume(
                product_reset_self_test_context(reappeared_data, fault_after="config_moved"),
                operation_id_raw=reappeared_op,
                start=True,
            ),
            "config-moved fault should leave a resumable journal",
        )
        product_reset_self_test_prepare_dir(
            reappeared_data / "config",
            PRODUCT_RESET_RECREATE_MODE,
        )
        product_reset_self_test_write_json(
            reappeared_data / "config/config.json",
            reappeared_fixture["active_config"],
            PRODUCT_RESET_CONFIG_FILE_MODE,
        )
        assert_raises_writer_error_code(
            lambda: product_reset_start_or_resume(
                product_reset_self_test_context(reappeared_data),
                operation_id_raw=None,
                start=False,
            ),
            "product_reset_domain_reappeared:config",
            "a moved domain must not accept stale data that reappears after a cut",
        )

        unsanitized_fixture = product_reset_self_test_fixture(root, 120)
        unsanitized_data = unsanitized_fixture["data"]
        unsanitized_op = product_reset_self_test_uuid(120)
        unsanitized_ctx = product_reset_self_test_context(unsanitized_data, fault_after="graveyard_prepared")
        assert_raises_writer_error(
            lambda: product_reset_start_or_resume(unsanitized_ctx, operation_id_raw=unsanitized_op, start=True),
            "setup fault should leave intent and graveyard before moves",
        )
        unsanitized_target = unsanitized_data / PRODUCT_RESET_GRAVEYARD_REL / unsanitized_op / "config"
        product_reset_self_test_prepare_dir(unsanitized_target.parent, PRIVATE_DIR_MODE)
        os.replace(unsanitized_data / "config", unsanitized_target)
        resumed_unsanitized = product_reset_start_or_resume(
            product_reset_self_test_context(unsanitized_data),
            operation_id_raw=None,
            start=False,
        )
        assert_true(resumed_unsanitized["phase"] == "local_complete", "unsanitized moved config should reconcile")
        unsanitized_graveyard_config = product_reset_load_json(
            unsanitized_target / "config.json",
            label="unsanitized-graveyard-config",
        )
        product_reset_assert_no_forbidden_values(
            unsanitized_graveyard_config,
            (
                unsanitized_fixture["active_config"]["api_key"],
                unsanitized_fixture["active_config"]["api_url"],
                unsanitized_fixture["active_config"]["api_token_id"],
                unsanitized_fixture["active_config"]["environment_id"],
                unsanitized_fixture["active_config"]["station_id"],
            ),
            "resume should sanitize config moved before prior power cut",
        )

        resume_status = product_reset_start_or_resume(ctx, operation_id_raw=operation_id, start=True)
        assert_true(resume_status["phase"] == "local_complete", "same-op start should be idempotent")
        assert_true(not (data / "config/config.json").exists(), "idempotent resume restored old config")
        assert_raises_writer_error(
            lambda: product_reset_start_or_resume(ctx, operation_id_raw=product_reset_self_test_uuid(3), start=True),
            "different concurrent operation should fail",
        )
        extra_graveyard = data / PRODUCT_RESET_GRAVEYARD_REL / product_reset_self_test_uuid(4)
        product_reset_self_test_prepare_dir(extra_graveyard, PRIVATE_DIR_MODE)
        assert_raises_writer_error(
            lambda: product_reset_start_or_resume(ctx, operation_id_raw=operation_id, start=False),
            "second graveyard should be rejected until explicit GC",
        )
        shutil.rmtree(extra_graveyard)

        assert_raises_writer_error(
            lambda: product_reset_finalize(
                ctx,
                operation_id_raw=product_reset_self_test_uuid(5),
                result="revoked",
            ),
            "finalize with different op should fail",
        )
        assert_raises_writer_error(
            lambda: product_reset_finalize(ctx, operation_id_raw=operation_id, result=None),
            "finalize without result should fail",
        )
        product_reset_self_test_write_json(
            data / PRODUCT_RESET_HOMOLOGATION_SEED_REL,
            {"api_key": "REINTRODUCED_HOMOLOGATION_SEED_SECRET"},
        )
        assert_raises_writer_error_code(
            lambda: product_reset_finalize(ctx, operation_id_raw=operation_id, result="revoked"),
            "product_reset_homologation_seed_reappeared",
            "reintroduced homologation seed must block finalization",
        )
        (data / PRODUCT_RESET_HOMOLOGATION_SEED_REL).unlink()
        finalized = product_reset_finalize(ctx, operation_id_raw=operation_id, result="revoked")
        assert_true(finalized["phase"] == "finalized", "finalize should write finalized status")
        assert_true(product_reset_cli_exit_code(finalized) == 0, "finalized status should use exit 0")
        assert_true(not (state_dir / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME).exists(), "finalize should remove pending credential")
        assert_true(not (state_dir / PRODUCT_RESET_INTENT_FILENAME).exists(), "finalize should clear intent guard")
        receipt_path = state_dir / PRODUCT_RESET_RECEIPT_FILENAME
        assert_true(file_mode(receipt_path) == PRIVATE_FILE_MODE, "receipt should be 0600")
        assert_true(graveyard_op.exists(), "finalize must leave bulk cleanup outside the user path")
        assert_true(
            not (state_dir / PRODUCT_RESET_GC_PENDING_FILENAME).exists(),
            "finalize must not queue cleanup before new onboarding is valid",
        )
        receipt = product_reset_load_json(receipt_path, label="receipt", private_mode=PRIVATE_FILE_MODE)
        product_reset_assert_no_forbidden_values(receipt, forbidden, "receipt leaked private reset values")
        finalized_again = product_reset_finalize(ctx, operation_id_raw=operation_id, result="revoked")
        assert_true(finalized_again["phase"] == "finalized", "finalize should be idempotent for same op")
        assert_raises_writer_error(
            lambda: product_reset_finalize(ctx, operation_id_raw=operation_id, result="not_device_activation"),
            "finalize with same op but different result should fail after receipt",
        )
        finalized_status = product_reset_public_status(ctx)
        assert_true(finalized_status["phase"] == "finalized", "status should report finalized receipt")
        reboot_before_onboarding = product_reset_start_or_resume(ctx, operation_id_raw=None, start=False)
        assert_true(reboot_before_onboarding["phase"] == "finalized", "reboot before onboarding must retain receipt handoff")
        assert_raises_writer_error_code(
            lambda: product_reset_start_or_resume(
                ctx,
                operation_id_raw=product_reset_self_test_uuid(3),
                start=True,
            ),
            "product_reset_onboarding_pending",
            "new reset must be gated by the persisted onboarding receipt",
        )
        assert_raises_writer_error(
            lambda: product_reset_gc(ctx, max_remove=0),
            "GC bound of zero should fail",
        )
        assert_raises_writer_error_code(
            lambda: product_reset_gc(ctx, max_remove=1),
            "product_reset_gc_state_conflict",
            "GC must not run while the onboarding receipt still owns the graveyard",
        )
        assert_true(graveyard_op.exists(), "unmarked graveyard must remain fail closed")
        assert_raises_writer_error_code(
            lambda: product_reset_complete_onboarding(ctx),
            "product_reset_onboarding_config_missing",
            "onboarding completion must require a newly written config",
        )
        product_reset_self_test_write_json(
            data / "config/config.json",
            {"api_key": "INVALID_NEW_CONFIG"},
            PRODUCT_RESET_CONFIG_FILE_MODE,
        )
        assert_raises_writer_error_code(
            lambda: product_reset_complete_onboarding(ctx),
            "product_reset_onboarding_config_invalid",
            "onboarding completion must reject an invalid new config",
        )
        product_reset_self_test_write_new_config(data, 1)
        onboarding_complete = product_reset_complete_onboarding(ctx)
        assert_true(onboarding_complete["phase"] == "onboarding_complete", "onboarding completion should clear the receipt")
        assert_true(not receipt_path.exists(), "onboarding completion should remove the receipt")
        assert_true(onboarding_complete["gc_pending"], "onboarding completion should queue bulk cleanup")
        gc_pending_path = state_dir / PRODUCT_RESET_GC_PENDING_FILENAME
        assert_true(file_mode(gc_pending_path) == PRIVATE_FILE_MODE, "GC marker should be 0600")
        assert_true(
            product_reset_public_status(ctx)["phase"] == "gc_pending",
            "completed onboarding should expose bounded background cleanup",
        )
        assert_true(
            product_reset_complete_onboarding(ctx)["code"] == "noop",
            "onboarding completion must be idempotent when receipt is absent",
        )

        product_reset_self_test_write_json(data / "config/config.json", build_synthetic_candidate(), REAL_ACTIVE_CONFIG_MODE)
        assert_raises_writer_error_code(
            lambda: product_reset_start_or_resume(
                ctx,
                operation_id_raw=product_reset_self_test_uuid(3),
                start=True,
            ),
            "product_reset_gc_pending",
            "a second reset must wait for the single pending cleanup",
        )
        gc_status = product_reset_gc(ctx, max_remove=1)
        assert_true(gc_status["graveyards_removed"] == 1, "GC should remove exactly its marked graveyard")
        assert_true(not graveyard_op.exists(), "GC should remove the exact completed graveyard")
        assert_true(not gc_pending_path.exists(), "GC should clear its marker only after deletion")
        assert_true(product_reset_public_status(ctx)["code"] == "noop", "GC should clear reset state")
        assert_true(
            seed_disabled_path.exists(),
            "GC must preserve the durable homologation seed tombstone",
        )

        second_active = build_synthetic_candidate()
        second_active.update(
            {
                "api_url": "https://second-reset.example.invalid/search",
                "api_key": "SECOND_RESET_SECRET_VALUE_1234567890",
                "api_token_id": "33333333-4444-4555-8666-000000000003",
            }
        )
        product_reset_self_test_write_json(data / "config/config.json", second_active, REAL_ACTIVE_CONFIG_MODE)
        second_operation_id = product_reset_self_test_uuid(3)
        second_reset = product_reset_start_or_resume(ctx, operation_id_raw=second_operation_id, start=True)
        assert_true(second_reset["phase"] == "local_complete", "second reset should start after onboarding handoff")
        second_finalized = product_reset_finalize(ctx, operation_id_raw=second_operation_id, result="revoked")
        assert_true(second_finalized["phase"] == "finalized", "second reset should finalize without prior receipt mismatch")
        assert_true(
            (data / PRODUCT_RESET_GRAVEYARD_REL / second_operation_id).exists(),
            "second finalized graveyard should remain private until onboarding succeeds",
        )
        product_reset_self_test_write_new_config(data, 2)
        assert_true(
            product_reset_complete_onboarding(ctx)["phase"] == "onboarding_complete",
            "second receipt should complete onboarding independently",
        )
        assert_true(
            product_reset_gc(ctx, max_remove=1)["graveyards_removed"] == 1,
            "second reset cleanup should remain bounded to one exact operation",
        )

        nda_fixture = product_reset_self_test_fixture(root, 6)
        nda_ctx = product_reset_self_test_context(nda_fixture["data"])
        nda_op = product_reset_self_test_uuid(6)
        product_reset_start_or_resume(nda_ctx, operation_id_raw=nda_op, start=True)
        nda_finalized = product_reset_finalize(nda_ctx, operation_id_raw=nda_op, result="not_device_activation")
        assert_true(nda_finalized["finalize_result"] == "not_device_activation", "finalize should accept not_device_activation")

        for offset, finalize_fault in enumerate(PRODUCT_RESET_FINALIZE_FAULT_PHASES, start=130):
            finalize_fixture = product_reset_self_test_fixture(root, offset)
            finalize_data = finalize_fixture["data"]
            finalize_op = product_reset_self_test_uuid(offset)
            product_reset_start_or_resume(
                product_reset_self_test_context(finalize_data),
                operation_id_raw=finalize_op,
                start=True,
            )
            assert_raises_writer_error(
                lambda fault=finalize_fault, op=finalize_op, data_root=finalize_data: product_reset_finalize(
                    product_reset_self_test_context(data_root, fault_after=fault),
                    operation_id_raw=op,
                    result="revoked",
                ),
                f"finalize fault phase {finalize_fault} should raise",
            )
            fault_state = finalize_data / PRODUCT_RESET_STATE_REL
            assert_true((fault_state / PRODUCT_RESET_RECEIPT_FILENAME).exists(), f"{finalize_fault} should leave receipt")
            if finalize_fault == "receipt_written":
                assert_true((fault_state / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME).exists(), "receipt fault should keep credential")
                assert_true((fault_state / PRODUCT_RESET_INTENT_FILENAME).exists(), "receipt fault should keep intent")
            elif finalize_fault == "credential_unlinked":
                assert_true(not (fault_state / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME).exists(), "credential fault should remove credential")
                assert_true((fault_state / PRODUCT_RESET_INTENT_FILENAME).exists(), "credential fault should keep intent")
            elif finalize_fault == "intent_unlinked":
                assert_true(not (fault_state / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME).exists(), "intent fault should remove credential")
                assert_true(not (fault_state / PRODUCT_RESET_INTENT_FILENAME).exists(), "intent fault should remove intent")
            if finalize_fault in {"receipt_written", "credential_unlinked"}:
                recovered_finalize = product_reset_start_or_resume(
                    product_reset_self_test_context(finalize_data),
                    operation_id_raw=finalize_op,
                    start=False,
                )
            else:
                recovered_finalize = product_reset_finalize(
                    product_reset_self_test_context(finalize_data),
                    operation_id_raw=finalize_op,
                    result="revoked",
                )
            assert_true(recovered_finalize["phase"] == "finalized", f"{finalize_fault} should recover finalized")
            assert_true(not (fault_state / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME).exists(), f"{finalize_fault} should not leave credential")
            assert_true(not (fault_state / PRODUCT_RESET_INTENT_FILENAME).exists(), f"{finalize_fault} should not leave intent")
            cleanup_recovery = product_reset_finalize(
                product_reset_self_test_context(finalize_data),
                operation_id_raw=finalize_op,
                result="revoked",
            )
            assert_true(cleanup_recovery["phase"] == "finalized", f"{finalize_fault} cleanup should be idempotent")
            assert_true(
                (finalize_data / PRODUCT_RESET_GRAVEYARD_REL / finalize_op).exists(),
                f"{finalize_fault} should not put bulk deletion on finalize path",
            )
            product_reset_self_test_write_new_config(finalize_data, offset)
            assert_true(
                product_reset_complete_onboarding(product_reset_self_test_context(finalize_data))["phase"]
                == "onboarding_complete",
                f"{finalize_fault} should retain a completable receipt",
            )
            assert_true(
                product_reset_gc(product_reset_self_test_context(finalize_data), max_remove=1)["graveyards_removed"]
                == 1,
                f"{finalize_fault} should retain one exact deferred cleanup",
            )

        for offset, onboarding_fault in enumerate(PRODUCT_RESET_ONBOARDING_FAULT_PHASES, start=150):
            onboarding_fixture = product_reset_self_test_fixture(root, offset)
            onboarding_data = onboarding_fixture["data"]
            onboarding_op = product_reset_self_test_uuid(offset)
            onboarding_ctx = product_reset_self_test_context(onboarding_data)
            product_reset_start_or_resume(onboarding_ctx, operation_id_raw=onboarding_op, start=True)
            product_reset_finalize(onboarding_ctx, operation_id_raw=onboarding_op, result="revoked")
            product_reset_self_test_write_new_config(onboarding_data, offset)
            assert_raises_writer_error(
                lambda fault=onboarding_fault, data_root=onboarding_data: product_reset_complete_onboarding(
                    product_reset_self_test_context(data_root, fault_after=fault)
                ),
                f"onboarding fault phase {onboarding_fault} should raise",
            )
            onboarding_state = onboarding_data / PRODUCT_RESET_STATE_REL
            assert_true(
                (onboarding_state / PRODUCT_RESET_GC_PENDING_FILENAME).exists(),
                f"{onboarding_fault} should leave exact GC marker",
            )
            if onboarding_fault == "gc_pending_written":
                assert_true(
                    (onboarding_state / PRODUCT_RESET_RECEIPT_FILENAME).exists(),
                    "GC marker fault should retain onboarding receipt",
                )
                recovered_onboarding = product_reset_complete_onboarding(
                    product_reset_self_test_context(onboarding_data)
                )
                assert_true(
                    recovered_onboarding["phase"] == "onboarding_complete",
                    "GC marker fault should resume onboarding completion",
                )
            else:
                assert_true(
                    not (onboarding_state / PRODUCT_RESET_RECEIPT_FILENAME).exists(),
                    "receipt unlink fault should have cleared onboarding guard",
                )
            assert_true(
                product_reset_public_status(product_reset_self_test_context(onboarding_data))["phase"]
                == "gc_pending",
                f"{onboarding_fault} should preserve deferred cleanup",
            )
            product_reset_gc(product_reset_self_test_context(onboarding_data), max_remove=1)

        for offset, gc_fault in enumerate(PRODUCT_RESET_GC_FAULT_PHASES, start=160):
            gc_fixture = product_reset_self_test_fixture(root, offset)
            gc_data = gc_fixture["data"]
            gc_op = product_reset_self_test_uuid(offset)
            gc_ctx = product_reset_self_test_context(gc_data)
            product_reset_start_or_resume(gc_ctx, operation_id_raw=gc_op, start=True)
            product_reset_finalize(gc_ctx, operation_id_raw=gc_op, result="revoked")
            product_reset_self_test_write_new_config(gc_data, offset)
            product_reset_complete_onboarding(gc_ctx)
            assert_raises_writer_error(
                lambda fault=gc_fault, data_root=gc_data: product_reset_gc(
                    product_reset_self_test_context(data_root, fault_after=fault),
                    max_remove=1,
                ),
                f"GC fault phase {gc_fault} should raise",
            )
            recovered_gc = product_reset_gc(product_reset_self_test_context(gc_data), max_remove=1)
            assert_true(recovered_gc["phase"] == "gc", f"{gc_fault} should recover idempotently")
            assert_true(
                not (gc_data / PRODUCT_RESET_GRAVEYARD_REL / gc_op).exists(),
                f"{gc_fault} should not leave the exact graveyard after retry",
            )
            assert_true(
                not (gc_data / PRODUCT_RESET_STATE_REL / PRODUCT_RESET_GC_PENDING_FILENAME).exists(),
                f"{gc_fault} should clear the marker only after exact deletion",
            )

        symlink_fixture = product_reset_self_test_fixture(root, 7)
        symlink_data = symlink_fixture["data"]
        shutil.rmtree(symlink_data / "media/kiosky-player")
        os.symlink("/tmp", symlink_data / "media/kiosky-player")
        symlink_ctx = product_reset_self_test_context(symlink_data)
        symlink_op = product_reset_self_test_uuid(7)
        assert_raises_writer_error(
            lambda: product_reset_start_or_resume(symlink_ctx, operation_id_raw=symlink_op, start=True),
            "symlink fixed domain should fail before data moves",
        )
        assert_true((symlink_data / "config/config.json").exists(), "symlink preflight should not move config first")
        (symlink_data / "media/kiosky-player").unlink()
        product_reset_self_test_prepare_dir(symlink_data / "media/kiosky-player", PRODUCT_RESET_RECREATE_MODE)
        product_reset_self_test_write_text(symlink_data / "media/kiosky-player/marker.txt", "repaired\n")
        repaired = product_reset_start_or_resume(symlink_ctx, operation_id_raw=symlink_op, start=True)
        assert_true(repaired["phase"] == "local_complete", "resume after symlink repair should complete")

        missing_parent_fixture = product_reset_self_test_fixture(root, 8)
        shutil.rmtree(missing_parent_fixture["data"] / "state/totem-appliance")
        missing_parent_ctx = product_reset_self_test_context(missing_parent_fixture["data"])
        assert_raises_writer_error(
            lambda: product_reset_start_or_resume(
                missing_parent_ctx,
                operation_id_raw=product_reset_self_test_uuid(8),
                start=True,
            ),
            "missing appliance state parent should fail closed",
        )

        for offset, fault_phase in enumerate(PRODUCT_RESET_FAULT_PHASES, start=20):
            fault_fixture = product_reset_self_test_fixture(root, offset)
            fault_data = fault_fixture["data"]
            fault_op = product_reset_self_test_uuid(offset)
            fault_ctx = product_reset_self_test_context(fault_data, fault_after=fault_phase)
            assert_raises_writer_error(
                lambda ctx=fault_ctx, op=fault_op: product_reset_start_or_resume(ctx, operation_id_raw=op, start=True),
                f"fault phase {fault_phase} should raise",
            )
            fault_state = fault_data / PRODUCT_RESET_STATE_REL
            assert_true(
                (fault_state / PRODUCT_RESET_INTENT_FILENAME).exists(),
                f"fault phase {fault_phase} must leave durable intent for boot recovery",
            )
            if fault_phase == "state_prepared":
                assert_true(
                    not (fault_state / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME).exists(),
                    "state_prepared fault should happen before the pending credential is written",
                )
                assert_true(
                    (fault_data / "config/config.json").exists(),
                    "state_prepared fault should happen before the active config moves",
                )
            resume_ctx = product_reset_self_test_context(fault_data)
            recovered = product_reset_start_or_resume(resume_ctx, operation_id_raw=None, start=False)
            assert_true(recovered["phase"] == "local_complete", f"fault phase {fault_phase} should recover")
            assert_true(
                product_reset_files_containing(fault_data, fault_fixture["active_config"]["api_key"])
                == [PRODUCT_RESET_STATE_REL / PRODUCT_RESET_PENDING_CREDENTIAL_FILENAME],
                f"fault phase {fault_phase} leaked api_key outside pending credential",
            )
            assert_true(
                product_reset_files_containing(fault_data, fault_fixture["homologation_seed_secret"]) == [],
                f"fault phase {fault_phase} retained homologation seed secret after recovery",
            )
            assert_true(not (fault_data / "config/config.json").exists(), f"fault phase {fault_phase} restored old config")

        for path in root.rglob("*"):
            assert_true(not str(path.resolve(strict=False)).startswith("/data/"), "product reset self-test wrote under /data")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_self_test() -> None:
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c6-2-writer-self-test-", dir="/tmp"))
    try:
        run_product_reset_smoke_self_test()

        mock_status = validate_real_dry_run(contract.build_mock_candidate())
        assert_true(not mock_status["valid"], "C5 mock candidate should fail real-dry-run")

        synthetic = build_synthetic_candidate()
        synthetic_status = validate_real_dry_run(synthetic)
        assert_true(synthetic_status["valid"], "synthetic candidate should pass real-dry-run")

        unsafe_mpv_path = dict(synthetic)
        unsafe_mpv_path["mpv_path"] = "mpv"
        unsafe_mpv_status = validate_real_dry_run(unsafe_mpv_path)
        assert_true(not unsafe_mpv_status["valid"], "writer contract should reject unsafe C18 mpv_path")

        candidate = root / "candidate" / "config.synthetic.json"
        write_self_test_candidate(candidate, synthetic)

        assert_raises_writer_error(
            lambda: validate_writer_paths(
                candidate_raw=str(candidate),
                dest_raw="/data/config/config.json",
                backup_dir_raw="/data/config/backups",
                out_dir_raw=str(root / "out-real-no-flags"),
                check_real_symlinks=False,
            ),
            "real dest without --enable-real-write should fail",
        )
        assert_raises_writer_error(
            lambda: validate_writer_paths(
                candidate_raw=str(candidate),
                dest_raw="/data/config/config.json",
                backup_dir_raw="/data/config/backups",
                out_dir_raw=str(root / "out-real-incomplete-flags"),
                enable_real_write=True,
                confirm_service_stopped=True,
                confirm_human_approved_real_write=False,
                check_real_symlinks=False,
            ),
            "real dest with incomplete flags should fail",
        )
        real_guardrail_paths = validate_writer_paths(
            candidate_raw=str(candidate),
            dest_raw="/data/config/config.json",
            backup_dir_raw="/data/config/backups",
            out_dir_raw=str(root / "out-real-path-guardrail"),
            enable_real_write=True,
            confirm_service_stopped=True,
            confirm_human_approved_real_write=True,
            check_real_symlinks=False,
        )
        assert_true(real_guardrail_paths.real_write_enabled, "complete flags should enable real guardrail mode")
        assert_true(real_guardrail_paths.dest == REAL_DEST_PATH, "real guardrail should accept only exact dest")
        assert_true(
            real_guardrail_paths.backup_dir == REAL_BACKUP_DIR,
            "real guardrail should accept only approved backup-dir",
        )
        assert_raises_writer_error(
            lambda: validate_writer_paths(
                candidate_raw=str(candidate),
                dest_raw="/data/config/other.json",
                backup_dir_raw="/data/config/backups",
                out_dir_raw=str(root / "out-real-wrong-dest"),
                enable_real_write=True,
                confirm_service_stopped=True,
                confirm_human_approved_real_write=True,
                check_real_symlinks=False,
            ),
            "real dest different from /data/config/config.json should fail",
        )
        assert_raises_writer_error(
            lambda: validate_writer_paths(
                candidate_raw=str(candidate),
                dest_raw="/data/config/config.json",
                backup_dir_raw="/data/backups",
                out_dir_raw=str(root / "out-real-wrong-backup"),
                enable_real_write=True,
                confirm_service_stopped=True,
                confirm_human_approved_real_write=True,
                check_real_symlinks=False,
            ),
            "real backup-dir outside approved path should fail",
        )
        fake_repo = root / "fake-repo"
        (fake_repo / ".git").mkdir(parents=True)
        repo_candidate = fake_repo / "candidate.real.json"
        write_self_test_candidate(repo_candidate, synthetic)
        assert_raises_writer_error(
            lambda: validate_writer_paths(
                candidate_raw=str(repo_candidate),
                dest_raw="/data/config/config.json",
                backup_dir_raw="/data/config/backups",
                out_dir_raw=str(root / "out-real-repo-candidate"),
                enable_real_write=True,
                confirm_service_stopped=True,
                confirm_human_approved_real_write=True,
                check_real_symlinks=False,
            ),
            "real candidate in repository should fail",
        )
        assert_raises_writer_error(
            lambda: validate_writer_paths(
                candidate_raw="/data/config/candidate.real.json",
                dest_raw="/data/config/config.json",
                backup_dir_raw="/data/config/backups",
                out_dir_raw=str(root / "out-real-data-candidate"),
                enable_real_write=True,
                confirm_service_stopped=True,
                confirm_human_approved_real_write=True,
                check_real_symlinks=False,
            ),
            "real candidate under /data should fail",
        )
        assert_raises_writer_error(
            lambda: validate_writer_paths(
                candidate_raw="/opt/dadooh/candidate.real.json",
                dest_raw="/data/config/config.json",
                backup_dir_raw="/data/config/backups",
                out_dir_raw=str(root / "out-real-opt-candidate"),
                enable_real_write=True,
                confirm_service_stopped=True,
                confirm_human_approved_real_write=True,
                check_real_symlinks=False,
            ),
            "real candidate under /opt should fail",
        )

        assert_raises_writer_error(
            lambda: run_writer(
                candidate_raw=str(candidate),
                dest_raw="/var/tmp/dadooh-c6-2/config.json",
                backup_dir_raw=None,
                out_dir_raw=str(root / "out-dest-fail"),
            ),
            "dest outside /tmp should fail",
        )
        assert_raises_writer_error(
            lambda: run_writer(
                candidate_raw=str(candidate),
                dest_raw=str(root / "sim" / "config.json"),
                backup_dir_raw="/var/tmp/dadooh-c6-2-backups",
                out_dir_raw=str(root / "out-backup-fail"),
            ),
            "backup-dir outside /tmp should fail",
        )
        assert_raises_writer_error(
            lambda: run_writer(
                candidate_raw="/data/config/config.json",
                dest_raw=str(root / "sim" / "config.json"),
                backup_dir_raw=None,
                out_dir_raw=str(root / "out-data-candidate-fail"),
            ),
            "candidate under /data should fail",
        )
        assert_raises_writer_error(
            lambda: run_writer(
                candidate_raw="/opt/dadooh/config.json",
                dest_raw=str(root / "sim" / "config.json"),
                backup_dir_raw=None,
                out_dir_raw=str(root / "out-opt-candidate-fail"),
            ),
            "candidate under /opt should fail",
        )

        mock_candidate = root / "candidate" / "config.mock.json"
        write_self_test_candidate(mock_candidate, contract.build_mock_candidate())
        mock_dest = root / "mock-fail" / "config.json"
        assert_raises_writer_error(
            lambda: run_writer(
                candidate_raw=str(mock_candidate),
                dest_raw=str(mock_dest),
                backup_dir_raw=None,
                out_dir_raw=str(root / "out-mock-fail"),
            ),
            "C5 mock candidate should fail operational writer",
        )
        assert_true(not mock_dest.exists(), "failed pre-validation should not write dest")

        dest = root / "simulated" / "data" / "config" / "config.json"
        backup_dir = root / "simulated" / "backups"
        out_dir = root / "out"
        status = run_writer(
            candidate_raw=str(candidate),
            dest_raw=str(dest),
            backup_dir_raw=str(backup_dir),
            out_dir_raw=str(out_dir),
        )
        assert_true(status["result"] == "passed", "writer should pass with synthetic candidate")
        assert_true(dest.exists(), "atomic write should create dest")
        assert_true(file_mode(dest) == ACTIVE_CONFIG_MODE, "active simulated config mode should be 600")
        assert_true(file_mode(out_dir) == PRIVATE_DIR_MODE, "out-dir mode should be 700")
        for name in (STATUS_FILENAME, SUMMARY_FILENAME):
            path = out_dir / name
            assert_true(file_mode(path) == PRIVATE_FILE_MODE, f"{name} mode should be 600")
            content = path.read_text(encoding="utf-8")
            assert_true(synthetic["api_key"] not in content, "synthetic api_key leaked to status/summary")

        evidence_failure_dest = root / "evidence-failure" / "config.json"
        original_write_status_artifacts = globals()["write_status_artifacts"]
        try:
            def fail_status_artifacts(_out_dir: pathlib.Path, _status: dict[str, Any]) -> None:
                raise OSError("synthetic evidence write failure")

            globals()["write_status_artifacts"] = fail_status_artifacts
            evidence_failure_status = run_writer(
                candidate_raw=str(candidate),
                dest_raw=str(evidence_failure_dest),
                backup_dir_raw=str(root / "evidence-failure-backups"),
                out_dir_raw=str(root / "out-evidence-failure"),
            )
        finally:
            globals()["write_status_artifacts"] = original_write_status_artifacts
        assert_true(evidence_failure_status["result"] == "passed", "evidence failure must not undo valid config")
        assert_true(
            load_json_file(evidence_failure_dest, label="evidence failure active config") == synthetic,
            "evidence failure must preserve the validated active config",
        )

        replacement = build_synthetic_candidate()
        replacement["station_id"] = "STATION_ALPHA_002"
        replacement_candidate = root / "candidate" / "config.replacement.json"
        write_self_test_candidate(replacement_candidate, replacement)
        status = run_writer(
            candidate_raw=str(replacement_candidate),
            dest_raw=str(dest),
            backup_dir_raw=str(backup_dir),
            out_dir_raw=str(root / "out-backup"),
        )
        assert_true(status["backup"]["previous_config_existed"], "backup should detect previous config")
        assert_true(status["backup"]["created"], "backup should be created")
        backup_files = sorted(backup_dir.glob("*.bak"))
        assert_true(bool(backup_files), "backup file should exist")
        for backup in backup_files:
            assert_true(file_mode(backup) == PRIVATE_FILE_MODE, "backup mode should be 600")

        before_rollback = dest.read_bytes()
        rollback_candidate = build_synthetic_candidate()
        rollback_candidate["station_id"] = "STATION_ALPHA_003"
        rollback_candidate_path = root / "candidate" / "config.rollback-trigger.json"
        write_self_test_candidate(rollback_candidate_path, rollback_candidate)
        assert_raises_writer_error(
            lambda: run_writer(
                candidate_raw=str(rollback_candidate_path),
                dest_raw=str(dest),
                backup_dir_raw=str(backup_dir),
                out_dir_raw=str(root / "out-rollback"),
                simulate_post_write_failure=True,
            ),
            "simulated post-write failure should raise",
        )
        assert_true(dest.read_bytes() == before_rollback, "rollback should restore previous active config")
        rollback_status = load_json_file(root / "out-rollback" / STATUS_FILENAME, label="rollback status")
        assert_true(rollback_status["rollback"]["restored"], "rollback status should mark restored")
        assert_true(rollback_status["rollback"]["restored_valid"], "rollback status should mark restored valid")
        rollback_summary = (root / "out-rollback" / SUMMARY_FILENAME).read_text(encoding="utf-8")
        assert_true(rollback_candidate["api_key"] not in rollback_summary, "rollback summary leaked api_key")

        generated_paths = [candidate, repo_candidate, mock_candidate, replacement_candidate, rollback_candidate_path, dest]
        generated_paths.extend(root.rglob(STATUS_FILENAME))
        generated_paths.extend(root.rglob(SUMMARY_FILENAME))
        generated_paths.extend(backup_dir.glob("*.bak"))
        for path in generated_paths:
            assert_true(not str(path.resolve(strict=False)).startswith("/data/"), "self-test wrote under /data")
    finally:
        shutil.rmtree(root, ignore_errors=True)

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "C6.2/C6.2.2 guarded config writer. Default mode writes only under /tmp; "
            "future real writes require explicit confirmation flags."
        ),
        allow_abbrev=False,
    )
    parser.add_argument("--candidate", help="Candidate JSON file. Refuses /data and /opt.")
    parser.add_argument(
        "--dest",
        help=(
            "Active config destination. Default mode requires /tmp. Real mode allows only "
            "/data/config/config.json."
        ),
    )
    parser.add_argument(
        "--backup-dir",
        help=(
            "Optional backup directory. Default mode requires /tmp. Real mode allows only "
            "/data/config/backups."
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Status output directory under /tmp. Default: {DEFAULT_OUT_DIR}",
    )
    parser.add_argument(
        "--enable-real-write",
        action="store_true",
        help="Enable future real-write guardrails. Requires both confirmation flags.",
    )
    parser.add_argument(
        "--confirm-service-stopped",
        action="store_true",
        help="Operator confirmation that kiosky-player.service is stopped. Does not call systemctl.",
    )
    parser.add_argument(
        "--confirm-human-approved-real-write",
        action="store_true",
        help="Operator confirmation that a human approved the real write.",
    )
    parser.add_argument("--product-reset-start", action="store_true", help="C26A: start local product reset.")
    parser.add_argument("--product-reset-resume", action="store_true", help="C26A: resume/reconcile local product reset.")
    parser.add_argument("--product-reset-status", action="store_true", help="C26A: print sanitized product-reset status.")
    parser.add_argument("--product-reset-finalize", action="store_true", help="C26A: finalize after credential revocation.")
    parser.add_argument(
        "--product-reset-complete-onboarding",
        action="store_true",
        help="C26A: clear finalized onboarding handoff after a new config was applied.",
    )
    parser.add_argument(
        "--confirm-product-reset-new-config-applied",
        action="store_true",
        help="Operator confirmation that the new configuration was applied successfully.",
    )
    parser.add_argument("--product-reset-gc", action="store_true", help="C26A: explicitly garbage collect old reset graveyards.")
    parser.add_argument(
        "--product-reset-data-root",
        default=str(PRODUCT_RESET_REAL_DATA_ROOT),
        help="C26A data root. Production accepts only /data; self-test injects /tmp internally.",
    )
    parser.add_argument("--product-reset-operation-id", help="C26A canonical UUIDv4 operation id.")
    parser.add_argument(
        "--product-reset-result",
        choices=PRODUCT_RESET_FINALIZE_RESULTS,
        help="C26A finalize result: revoked or not_device_activation.",
    )
    parser.add_argument(
        "--confirm-human-approved-product-reset",
        action="store_true",
        help="Operator confirmation that a human approved starting product reset.",
    )
    parser.add_argument(
        "--product-reset-gc-max",
        type=int,
        default=1,
        help="C26A GC bound. Only the exact value 1 is accepted.",
    )
    parser.add_argument(
        "--confirm-product-reset-background-gc",
        action="store_true",
        help="Confirm background deletion of the exact durable C26 GC marker target.",
    )
    parser.add_argument("--self-test", action="store_true", help="Run bounded package health tests under /tmp and exit.")
    parser.add_argument(
        "--extended-self-test",
        action="store_true",
        help="Run the exhaustive C26 product-reset fault matrix under /tmp and exit.",
    )
    return parser.parse_args(argv)


def selected_product_reset_actions(args: argparse.Namespace) -> list[str]:
    actions: list[str] = []
    if args.product_reset_start:
        actions.append("start")
    if args.product_reset_resume:
        actions.append("resume")
    if args.product_reset_status:
        actions.append("status")
    if args.product_reset_finalize:
        actions.append("finalize")
    if args.product_reset_complete_onboarding:
        actions.append("complete-onboarding")
    if args.product_reset_gc:
        actions.append("gc")
    return actions


def run_product_reset_cli(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    actions = selected_product_reset_actions(args)
    if len(actions) != 1:
        raise WriterError("product_reset_action_required")
    action = actions[0]
    mutating = action in {"start", "resume", "finalize", "complete-onboarding", "gc"}
    if action == "start":
        if not (args.enable_real_write and args.confirm_service_stopped):
            raise WriterError("product_reset_real_confirmation_required")
        if not args.confirm_human_approved_product_reset:
            raise WriterError("product_reset_human_confirmation_required")
    elif action in {"resume", "finalize"}:
        if not (args.enable_real_write and args.confirm_service_stopped):
            raise WriterError("product_reset_real_confirmation_required")
    elif action == "complete-onboarding":
        if not (args.enable_real_write and args.confirm_service_stopped):
            raise WriterError("product_reset_real_confirmation_required")
        if not args.confirm_product_reset_new_config_applied:
            raise WriterError("product_reset_onboarding_confirmation_required")
    elif action == "gc" and not (
        args.enable_real_write and args.confirm_product_reset_background_gc
    ):
        raise WriterError("product_reset_gc_confirmation_required")

    ctx = build_product_reset_context(
        data_root_raw=args.product_reset_data_root,
        require_real_confirmation=mutating and action != "gc",
        enable_real_write=args.enable_real_write,
        confirm_service_stopped=args.confirm_service_stopped,
    )
    if action == "start":
        status = product_reset_start_or_resume(ctx, operation_id_raw=args.product_reset_operation_id, start=True)
    elif action == "resume":
        status = product_reset_start_or_resume(ctx, operation_id_raw=args.product_reset_operation_id, start=False)
    elif action == "status":
        status = product_reset_public_status(ctx)
    elif action == "finalize":
        status = product_reset_finalize(
            ctx,
            operation_id_raw=args.product_reset_operation_id,
            result=args.product_reset_result,
        )
    elif action == "complete-onboarding":
        status = product_reset_complete_onboarding(ctx)
    elif action == "gc":
        status = product_reset_gc(ctx, max_remove=args.product_reset_gc_max)
    else:
        raise WriterError("product_reset_action_required")
    return status, product_reset_cli_exit_code(status)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.self_test and args.extended_self_test:
            raise WriterError("self_test_mode_ambiguous")
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0
        if args.extended_self_test:
            run_product_reset_self_test()
            print("extended-self-test: ok")
            return 0

        product_reset_actions = selected_product_reset_actions(args)
        if product_reset_actions:
            status, exit_code = run_product_reset_cli(args)
            product_reset_print_status(status)
            return exit_code

        if not args.candidate:
            raise WriterError("--candidate is required unless --self-test is used")
        if not args.dest:
            raise WriterError("--dest is required unless --self-test is used")

        status = run_writer(
            candidate_raw=args.candidate,
            dest_raw=args.dest,
            backup_dir_raw=args.backup_dir,
            out_dir_raw=args.out_dir,
            enable_real_write=args.enable_real_write,
            confirm_service_stopped=args.confirm_service_stopped,
            confirm_human_approved_real_write=args.confirm_human_approved_real_write,
        )
    except WriterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except AssertionError:
        print("error: self-test failed", file=sys.stderr)
        return 1
    except OSError:
        print("error: failed to write simulated config artifacts", file=sys.stderr)
        return 1

    print(f"C6.2.2 guarded writer artifacts generated under {args.out_dir}")
    print(STATUS_FILENAME)
    print(SUMMARY_FILENAME)
    print(f"write: {'passed' if status['result'] == 'passed' else 'failed'}")
    print(f"backup_created: {str(status['backup']['created']).lower()}")
    print(f"rollback_attempted: {str(status['rollback']['attempted']).lower()}")
    return 0 if status["result"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
