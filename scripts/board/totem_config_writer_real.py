#!/usr/bin/env python3
"""C6.2 simulated real config writer.

This is the first reusable writer shape for the real config flow, but C6.2 is
deliberately constrained to /tmp. It validates a local candidate with the C5.1
real-dry-run contract, writes the active config atomically to a simulated
destination, creates a restricted backup when replacing an existing config, and
rolls back on critical post-write failure.

It never reads or writes /data, never touches /opt, never accesses the network,
and never prints the api_key/token value.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import os
import pathlib
import secrets
import shutil
import stat
import sys
import tempfile
from typing import Any

sys.dont_write_bytecode = True

import totem_config_contract_validate as contract


SCHEMA_VERSION = "dadooh-c6.2-config-writer-real-sim.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c6-config-writer-real-sim"

STATUS_FILENAME = "writer-status.json"
SUMMARY_FILENAME = "summary.txt"

ACTIVE_CONFIG_MODE = 0o600
PRIVATE_FILE_MODE = 0o600
PRIVATE_DIR_MODE = 0o700

FORBIDDEN_CANDIDATE_ROOTS = (pathlib.Path("/data"), pathlib.Path("/opt"))
TMP_ROOT = pathlib.Path("/tmp").resolve()


class WriterError(ValueError):
    """Raised for expected C6.2 writer failures."""


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


def reject_raw_forbidden_path(raw_path: str, label: str) -> None:
    raw = pathlib.Path(raw_path).expanduser()
    if not raw.is_absolute():
        return
    absolute = pathlib.Path(os.path.abspath(str(raw)))
    for root in FORBIDDEN_CANDIDATE_ROOTS:
        if path_is_under(absolute, root):
            raise WriterError(f"refusing {label} under {root}")


def require_tmp_dir(raw_path: str, label: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
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


def prepare_private_dir(path: pathlib.Path) -> None:
    path.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    if stat.S_IMODE(path.stat().st_mode) != PRIVATE_DIR_MODE:
        path.chmod(PRIVATE_DIR_MODE)


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


def atomic_write_active_config(dest: pathlib.Path, config: dict[str, Any]) -> None:
    prepare_private_dir(dest.parent)
    payload = config_payload(config)
    tmp_name: str | None = None
    fd: int | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{dest.name}.", suffix=".tmp", dir=str(dest.parent))
        os.fchmod(fd, ACTIVE_CONFIG_MODE)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, dest)
        tmp_name = None
        dest.chmod(ACTIVE_CONFIG_MODE)
        fsync_directory(dest.parent)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def copy_file_private_atomic(src: pathlib.Path, dst: pathlib.Path, mode: int) -> None:
    prepare_private_dir(dst.parent)
    tmp_name: str | None = None
    fd: int | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{dst.name}.", suffix=".tmp", dir=str(dst.parent))
        os.fchmod(fd, mode)
        with src.open("rb") as source, os.fdopen(fd, "wb") as target:
            fd = None
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
        os.replace(tmp_name, dst)
        tmp_name = None
        dst.chmod(mode)
        fsync_directory(dst.parent)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def create_backup(dest: pathlib.Path, backup_dir: pathlib.Path) -> pathlib.Path:
    backup_name = f"{dest.name}.{backup_timestamp()}.{os.getpid()}.bak"
    backup_path = backup_dir / backup_name
    copy_file_private_atomic(dest, backup_path, PRIVATE_FILE_MODE)
    return backup_path


def restore_backup(backup_path: pathlib.Path, dest: pathlib.Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "attempted": True,
        "backup_available": backup_path.exists(),
        "restored": False,
        "restored_valid": False,
    }
    if not backup_path.exists():
        result["reason"] = "backup_missing"
        return result

    copy_file_private_atomic(backup_path, dest, ACTIVE_CONFIG_MODE)
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
        "mode": "c6.2-real-writer-simulated",
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
            "real_config_read": False,
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
            "Dadooh C6.2 config writer real simulated",
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
            "api_key_value_written_to_status: false",
            "api_key_value_written_to_summary: false",
            "candidate_config_copied_to_output: false",
            "backup_content_copied_to_output: false",
            "real_config_read: false",
            "data_written: false",
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
        candidate_path = normalize_candidate_path(candidate_raw)
        dest = require_tmp_file(dest_raw, "dest")
        backup_dir = require_tmp_dir(backup_dir_raw, "backup-dir") if backup_dir_raw else require_tmp_dir(
            str(dest.parent / "backups"),
            "backup-dir",
        )
        status["guardrails"]["dest_under_tmp"] = True
        status["guardrails"]["backup_dir_under_tmp"] = True

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
        prepare_private_dir(dest.parent)
        prepare_private_dir(backup_dir)

        status["backup"]["previous_config_existed"] = dest.exists()
        if dest.exists():
            status["phase"] = "backup"
            backup_path = create_backup(dest, backup_dir)
            status["backup"]["created"] = True
            status["backup"]["mode"] = file_mode_string(backup_path)

        status["phase"] = "atomic_write"
        status["write"]["attempted"] = True
        atomic_write_active_config(dest, candidate)
        status["write"]["active_config_written"] = True
        status["write"]["atomic_rename_completed"] = True
        status["write"]["fsync_file_completed"] = True
        status["write"]["fsync_directory_completed"] = True
        status["write"]["active_config_mode"] = file_mode_string(dest)

        status["phase"] = "post_write_validation"
        written_candidate = load_json_file(dest, label="active simulated config")
        post_status = validate_real_dry_run(written_candidate)
        if simulate_post_write_failure:
            post_status = dict(post_status)
            post_status["valid"] = False
        apply_validation_to_status(status, post_status, "post_write")
        if not post_status["valid"]:
            status["phase"] = "rollback"
            if backup_path is not None:
                rollback = restore_backup(backup_path, dest)
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
        write_status_artifacts(out_dir, status)
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


def run_self_test() -> None:
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c6-2-writer-self-test-", dir="/tmp"))
    try:
        mock_status = validate_real_dry_run(contract.build_mock_candidate())
        assert_true(not mock_status["valid"], "C5 mock candidate should fail real-dry-run")

        synthetic = build_synthetic_candidate()
        synthetic_status = validate_real_dry_run(synthetic)
        assert_true(synthetic_status["valid"], "synthetic candidate should pass real-dry-run")

        candidate = root / "candidate" / "config.synthetic.json"
        write_self_test_candidate(candidate, synthetic)

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

        generated_paths = [candidate, mock_candidate, replacement_candidate, rollback_candidate_path, dest]
        generated_paths.extend(root.rglob(STATUS_FILENAME))
        generated_paths.extend(root.rglob(SUMMARY_FILENAME))
        generated_paths.extend(backup_dir.glob("*.bak"))
        for path in generated_paths:
            assert_true(not str(path.resolve(strict=False)).startswith("/data/"), "self-test wrote under /data")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="C6.2 simulated real config writer. C6.2 only writes under /tmp.",
        allow_abbrev=False,
    )
    parser.add_argument("--candidate", help="Candidate JSON file. Refuses /data and /opt.")
    parser.add_argument("--dest", help="Simulated active config destination. Must be under /tmp in C6.2.")
    parser.add_argument("--backup-dir", help="Optional simulated backup directory. Must be under /tmp in C6.2.")
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Status output directory under /tmp. Default: {DEFAULT_OUT_DIR}",
    )
    parser.add_argument("--self-test", action="store_true", help="Run local C6.2 self-tests under /tmp and exit.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0

        if not args.candidate:
            raise WriterError("--candidate is required unless --self-test is used")
        if not args.dest:
            raise WriterError("--dest is required unless --self-test is used")

        status = run_writer(
            candidate_raw=args.candidate,
            dest_raw=args.dest,
            backup_dir_raw=args.backup_dir,
            out_dir_raw=args.out_dir,
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

    print(f"C6.2 simulated writer artifacts generated under {args.out_dir}")
    print(STATUS_FILENAME)
    print(SUMMARY_FILENAME)
    print(f"write: {'passed' if status['result'] == 'passed' else 'failed'}")
    print(f"backup_created: {str(status['backup']['created']).lower()}")
    print(f"rollback_attempted: {str(status['rollback']['attempted']).lower()}")
    return 0 if status["result"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
