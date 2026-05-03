#!/usr/bin/env python3
"""C8.5.1 generate a real-synthetic setup candidate under /tmp.

This tool proves the setup -> config path with locally generated non-production
values. It reads a C8 candidate from /tmp, writes a real-synthetic candidate
under /tmp, validates C5.1 real-dry-run, and writes sanitized status artifacts.
It never writes /data or /opt, never calls the C6 writer, and never calls
external commands.
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


SCHEMA_VERSION = "dadooh-c8.5.1-real-synthetic-candidate.v1"
DEFAULT_SOURCE_CANDIDATE = "/tmp/dadooh-c8-1-setup-minimo/candidate-config.json"
DEFAULT_OUT_DIR = "/tmp/dadooh-c8-5-1-real-synthetic"

REAL_SYNTHETIC_CANDIDATE_FILENAME = "candidate-real-synthetic.json"
STATUS_FILENAME = "real-synthetic-status.json"
SUMMARY_FILENAME = "summary.txt"

TMP_ROOT = pathlib.Path("/tmp").resolve()
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
SYNTHETIC_BACKEND_ENDPOINT = "https://api.sandbox.localhost/search"

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
NON_PRIVATE_METADATA_FIELDS = {
    "setup_source",
    "setup_environment_source",
    "setup_private_values_source",
}


class RealSyntheticError(ValueError):
    """Raised for expected C8.5.1 failures."""


def utc_timestamp() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def path_is_under(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def require_tmp_dir(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    resolved = path.resolve(strict=False)

    if not path_is_under(resolved, TMP_ROOT):
        raise RealSyntheticError("out-dir must be under /tmp")
    if resolved == TMP_ROOT:
        raise RealSyntheticError("out-dir must be a dedicated directory under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise RealSyntheticError("out-dir exists and is not a directory")
    return resolved


def normalize_source_candidate(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    raw_absolute = pathlib.Path(os.path.abspath(str(path)))
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise RealSyntheticError("source candidate must be under /tmp")

    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise RealSyntheticError("source candidate file not found") from exc

    if not path_is_under(resolved, TMP_ROOT):
        raise RealSyntheticError("source candidate must resolve under /tmp")
    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt")):
        if path_is_under(resolved, forbidden):
            raise RealSyntheticError(f"refusing source candidate under {forbidden}")
    if not resolved.is_file():
        raise RealSyntheticError("source candidate must be a file")
    return resolved


def prepare_private_dir(path: pathlib.Path) -> None:
    path.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    if stat.S_IMODE(path.stat().st_mode) != PRIVATE_DIR_MODE:
        path.chmod(PRIVATE_DIR_MODE)


def ensure_output_target(path: pathlib.Path, out_dir: pathlib.Path) -> None:
    resolved_out = out_dir.resolve(strict=True)
    resolved_target = path.resolve(strict=False)
    if not path_is_under(resolved_target, resolved_out):
        raise RealSyntheticError("output target escaped out-dir")
    if resolved_target == resolved_out:
        raise RealSyntheticError("output target must be a file")
    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt")):
        if path_is_under(resolved_target, forbidden):
            raise RealSyntheticError("refusing to write outside /tmp")


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
        raise RealSyntheticError(f"{label} is not valid JSON") from exc
    except OSError as exc:
        raise RealSyntheticError(f"{label} could not be read") from exc

    if not isinstance(value, dict):
        raise RealSyntheticError(f"{label} JSON root must be an object")
    return value


def generated_identifier(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(6).upper()}"


def generated_runtime_credential() -> str:
    return secrets.token_hex(24).upper()


def build_real_synthetic_candidate(source: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(source)
    candidate.update(
        {
            "api_url": SYNTHETIC_BACKEND_ENDPOINT,
            "api_key": generated_runtime_credential(),
            "environment_id": generated_identifier("ENV-APPROVED-SYNTH"),
            "setup_environment_source": "approved_synthetic_local",
            "setup_private_values_source": "local_generated_synthetic",
            "setup_source": "c8.5.1-real-synthetic-candidate",
        }
    )
    return candidate


def summarize_validation(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "valid": bool(status["valid"]),
        "missing_fields_count": len(status["missing_fields"]),
        "invalid_fields_count": len(status["invalid_fields"]),
        "placeholder_findings_count": len(status["placeholder_findings"]),
        "path_findings_count": len(status["path_findings"]),
        "credential_value_present": bool(status["api_key_present"]),
        "credential_placeholder_detected": bool(status["api_key_placeholder_detected"]),
        "environment_identifier_format_valid": bool(status["environment_id_status"]["valid"]),
        "station_identifier_optional_format_valid": bool(status["station_id_status"]["valid"]),
    }


def build_status(
    *,
    generated_at: str,
    source_candidate: dict[str, Any],
    real_candidate: dict[str, Any],
    source_allow_status: dict[str, Any],
    real_allow_status: dict[str, Any],
    real_dry_run_status: dict[str, Any],
) -> dict[str, Any]:
    required_count = len(contract.REQUIRED_CONFIG_FIELDS)
    present_required_count = sum(1 for field in contract.REQUIRED_CONFIG_FIELDS if field in real_candidate)
    handoff_fields_present_count = sum(
        1
        for field in ("rotation_deg", "setup_source", "setup_environment_source", "setup_private_values_source")
        if field in real_candidate
    )
    known_contract_fields = set(contract.REQUIRED_CONFIG_FIELDS) | set(contract.OPTIONAL_CONFIG_FIELDS)
    source_extra_fields_count = len(set(source_candidate) - known_contract_fields)
    real_extra_fields_count = len(set(real_candidate) - known_contract_fields)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "result": "passed",
        "phase": "real_synthetic_candidate_validated",
        "source_candidate": {
            "read_from_tmp": True,
            "allow_mock_valid": bool(source_allow_status["valid"]),
            "copied_to_output": False,
            "values_written_to_status": False,
            "extra_fields_count": source_extra_fields_count,
        },
        "real_synthetic_candidate": {
            "file": REAL_SYNTHETIC_CANDIDATE_FILENAME,
            "written_under_tmp": True,
            "required_contract_fields_count": required_count,
            "required_contract_fields_present_count": present_required_count,
            "handoff_fields_present_count": handoff_fields_present_count,
            "extra_fields_count": real_extra_fields_count,
            "values_written_to_status": False,
            "values_written_to_summary": False,
        },
        "origin": {
            "mode": "local_generated_synthetic",
            "human_private_input_used": False,
            "interactive_private_prompt_used": False,
            "values_from_git_or_docs": False,
            "values_from_terminal_log": False,
            "approved_for_real_write": False,
            "purpose": "prove_contract_shape_only",
        },
        "contract_validation": {
            "validator": "totem_config_contract_validate.py",
            "contract": "C5.1",
            "source_allow_mock": summarize_validation(source_allow_status),
            "real_synthetic_allow_mock": summarize_validation(real_allow_status),
            "real_synthetic_real_dry_run": summarize_validation(real_dry_run_status),
            "real_dry_run_passed": True,
            "placeholder_findings_cleared": len(real_dry_run_status["placeholder_findings"]) == 0,
        },
        "writer_handoff": {
            "candidate_ready_for_writer_validation": True,
            "candidate_ready_for_real_write": False,
            "writer_real_mode_called": False,
            "writer_simulated_write_called": False,
            "writer_real_write_blocked": True,
            "enable_real_write_used": False,
            "future_writer_must_validate_again": True,
            "future_writer_must_write_atomically": True,
            "future_writer_must_preserve_backup_and_rollback": True,
            "service_or_player_block_still_required": True,
            "human_approval_still_required": True,
        },
        "guardrails": {
            "writes_only_under_tmp": True,
            "real_config_read": False,
            "real_config_written": False,
            "source_candidate_read_from_data": False,
            "source_candidate_read_from_opt": False,
            "data_written": False,
            "opt_written": False,
            "commands_executed": False,
            "systemctl_called": False,
            "service_changed": False,
            "player_started": False,
            "player_stopped": False,
            "mpv_called": False,
            "network_external_access": False,
            "nmcli_called": False,
            "backend_called": False,
            "wifi_changed": False,
            "private_inputs_used": False,
        },
        "privacy": {
            "source_candidate_copied_to_output": False,
            "real_candidate_copied_to_status": False,
            "real_candidate_copied_to_summary": False,
            "credential_value_written_to_status": False,
            "credential_value_written_to_summary": False,
            "endpoint_value_written_to_status": False,
            "endpoint_value_written_to_summary": False,
            "environment_identifier_raw_written_to_status": False,
            "environment_identifier_raw_written_to_summary": False,
            "station_identifier_raw_written_to_status": False,
            "station_identifier_raw_written_to_summary": False,
            "paths_written_to_status": False,
            "paths_written_to_summary": False,
            "operator_input_copied_to_output": False,
        },
        "artifacts": {
            "real_synthetic_candidate": REAL_SYNTHETIC_CANDIDATE_FILENAME,
            "status": STATUS_FILENAME,
            "summary": SUMMARY_FILENAME,
        },
    }


def build_summary(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Dadooh C8.5.1 real synthetic candidate",
            "",
            f"schema_version: {status['schema_version']}",
            f"generated_at_utc: {status['generated_at_utc']}",
            f"result: {status['result']}",
            f"phase: {status['phase']}",
            "source_candidate_read_from_tmp: true",
            "source_allow_mock_valid: true",
            "origin_mode: local_generated_synthetic",
            "human_private_input_used: false",
            "interactive_private_prompt_used: false",
            "values_from_git_or_docs: false",
            "approved_for_real_write: false",
            "real_synthetic_candidate: candidate-real-synthetic.json",
            f"required_contract_fields_count: {status['real_synthetic_candidate']['required_contract_fields_count']}",
            "required_contract_fields_present_count: "
            f"{status['real_synthetic_candidate']['required_contract_fields_present_count']}",
            f"handoff_fields_present_count: {status['real_synthetic_candidate']['handoff_fields_present_count']}",
            f"extra_fields_count: {status['real_synthetic_candidate']['extra_fields_count']}",
            "real_synthetic_allow_mock_valid: "
            f"{str(status['contract_validation']['real_synthetic_allow_mock']['valid']).lower()}",
            "real_synthetic_real_dry_run_valid: "
            f"{str(status['contract_validation']['real_synthetic_real_dry_run']['valid']).lower()}",
            "placeholder_findings_cleared: "
            f"{str(status['contract_validation']['placeholder_findings_cleared']).lower()}",
            "candidate_ready_for_writer_validation: true",
            "candidate_ready_for_real_write: false",
            "writer_real_write_blocked: true",
            "writer_real_mode_called: false",
            "writer_simulated_write_called: false",
            "",
            "Guardrails:",
            "writes_only_under_tmp: true",
            "real_config_read: false",
            "real_config_written: false",
            "data_written: false",
            "opt_written: false",
            "commands_executed: false",
            "systemctl_called: false",
            "service_changed: false",
            "player_started: false",
            "player_stopped: false",
            "mpv_called: false",
            "network_external_access: false",
            "nmcli_called: false",
            "backend_called: false",
            "wifi_changed: false",
            "private_inputs_used: false",
            "",
            "Privacy:",
            "source_candidate_copied_to_output: false",
            "real_candidate_copied_to_status: false",
            "real_candidate_copied_to_summary: false",
            "credential_value_written_to_output: false",
            "endpoint_value_written_to_output: false",
            "environment_identifier_raw_written_to_output: false",
            "station_identifier_raw_written_to_output: false",
            "paths_written_to_output: false",
        ]
    )


def output_text(out_dir: pathlib.Path) -> str:
    parts = []
    for name in (STATUS_FILENAME, SUMMARY_FILENAME):
        path = out_dir / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def forbidden_text_variants(value: str) -> tuple[str, str]:
    escaped = json.dumps(value, ensure_ascii=True)[1:-1]
    return (value, escaped)


def assert_sanitized_outputs(out_dir: pathlib.Path, *candidates: dict[str, Any]) -> None:
    text = output_text(out_dir)
    for candidate in candidates:
        for field, value in candidate.items():
            if field in NON_PRIVATE_METADATA_FIELDS:
                continue
            if not isinstance(value, str) or not value:
                continue
            for variant in forbidden_text_variants(value):
                if variant and variant in text:
                    raise RealSyntheticError("privacy scan blocked candidate value in status/summary")

    for marker in SENSITIVE_OUTPUT_MARKERS:
        if marker in text.lower():
            raise RealSyntheticError("privacy scan blocked sensitive marker in status/summary")


def write_outputs(out_dir: pathlib.Path, real_candidate: dict[str, Any], status: dict[str, Any], source: dict[str, Any]) -> None:
    prepare_private_dir(out_dir)
    atomic_write_private_json(out_dir / REAL_SYNTHETIC_CANDIDATE_FILENAME, real_candidate, out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_summary(status), out_dir)
    assert_sanitized_outputs(out_dir, source, real_candidate)


def run_real_synthetic(source_raw: str, out_dir_raw: str) -> dict[str, Any]:
    out_dir = require_tmp_dir(out_dir_raw)
    source_path = normalize_source_candidate(source_raw)
    source = load_json_object(source_path, "source candidate")

    source_allow_status = contract.validate_candidate_config(source, "allow-mock")
    if not source_allow_status["valid"]:
        raise RealSyntheticError("source candidate failed C5.1 allow-mock validation")

    real_candidate = build_real_synthetic_candidate(source)
    real_allow_status = contract.validate_candidate_config(real_candidate, "allow-mock")
    real_dry_run_status = contract.validate_candidate_config(real_candidate, "real-dry-run")
    if not real_allow_status["valid"]:
        raise RealSyntheticError("real-synthetic candidate failed C5.1 allow-mock validation")
    if not real_dry_run_status["valid"]:
        raise RealSyntheticError("real-synthetic candidate failed C5.1 real-dry-run validation")
    if real_dry_run_status["placeholder_findings"]:
        raise RealSyntheticError("real-synthetic candidate still has placeholder findings")

    status = build_status(
        generated_at=utc_timestamp(),
        source_candidate=source,
        real_candidate=real_candidate,
        source_allow_status=source_allow_status,
        real_allow_status=real_allow_status,
        real_dry_run_status=real_dry_run_status,
    )
    write_outputs(out_dir, real_candidate, status, source)
    return status


def file_mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def build_c8_mock_candidate() -> dict[str, Any]:
    candidate = contract.build_mock_candidate()
    candidate["environment_id"] = "ENV-MOCK-LOJA-A"
    candidate["rotation_deg"] = 90
    candidate["setup_environment_source"] = "mock_list"
    candidate["setup_source"] = "c8.5.1-self-test-source"
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


def assert_raises_real_synthetic(fn: Any, message: str) -> None:
    try:
        fn()
    except RealSyntheticError:
        return
    raise AssertionError(message)


def run_self_test() -> None:
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c8-5-1-real-synthetic-self-test-", dir="/tmp"))
    try:
        source = build_c8_mock_candidate()
        source_path = root / "source" / "candidate-config.json"
        write_private_json(source_path, source)

        out_dir = root / "out"
        status = run_real_synthetic(str(source_path), str(out_dir))
        assert_true(status["result"] == "passed", "real-synthetic generation should pass")
        assert_true(
            status["contract_validation"]["real_synthetic_real_dry_run"]["valid"],
            "real-synthetic candidate should pass real-dry-run",
        )
        assert_true(status["writer_handoff"]["writer_real_write_blocked"], "writer real write should be blocked")
        assert_true(not status["writer_handoff"]["writer_real_mode_called"], "writer real mode should not be called")
        assert_true(file_mode(out_dir) == PRIVATE_DIR_MODE, "out-dir mode should be 700")

        real_candidate_path = out_dir / REAL_SYNTHETIC_CANDIDATE_FILENAME
        real_candidate = load_json_object(real_candidate_path, "real-synthetic candidate")
        assert_true(file_mode(real_candidate_path) == PRIVATE_FILE_MODE, "real candidate mode should be 600")
        assert_true(
            contract.validate_candidate_config(real_candidate, "real-dry-run")["valid"],
            "written real-synthetic candidate should pass C5.1 real-dry-run",
        )
        assert_true(real_candidate["rotation_deg"] == source["rotation_deg"], "rotation_deg should be preserved")
        assert_true(real_candidate["api_key"] != source["api_key"], "runtime credential should be replaced")
        assert_true(real_candidate["api_url"] != source["api_url"], "backend endpoint should be replaced")
        assert_true(real_candidate["station_id"] == source["station_id"], "optional station_id should be preserved")
        assert_true(real_candidate["environment_id"] != source["environment_id"], "environment should be replaced")

        source_without_station = dict(source)
        del source_without_station["station_id"]
        source_without_station_path = root / "source" / "candidate-without-station.json"
        write_private_json(source_without_station_path, source_without_station)
        status_without_station = run_real_synthetic(str(source_without_station_path), str(root / "out-no-station"))
        assert_true(
            status_without_station["contract_validation"]["real_synthetic_real_dry_run"]["valid"],
            "real-synthetic candidate without station_id should pass real-dry-run",
        )

        for name in (STATUS_FILENAME, SUMMARY_FILENAME):
            path = out_dir / name
            assert_true(path.exists(), f"{name} should exist")
            assert_true(file_mode(path) == PRIVATE_FILE_MODE, f"{name} mode should be 600")
            resolved = path.resolve(strict=True)
            assert_true(path_is_under(resolved, TMP_ROOT), f"{name} should be under /tmp")
            assert_true(not path_is_under(resolved, pathlib.Path("/data")), f"{name} wrote under /data")
            assert_true(not path_is_under(resolved, pathlib.Path("/opt")), f"{name} wrote under /opt")

        text = output_text(out_dir)
        for candidate in (source, real_candidate):
            for field, value in candidate.items():
                if field in NON_PRIVATE_METADATA_FIELDS:
                    continue
                if isinstance(value, str) and value:
                    for variant in forbidden_text_variants(value):
                        assert_true(variant not in text, "status/summary leaked candidate value")
        for marker in SENSITIVE_OUTPUT_MARKERS:
            assert_true(marker not in text.lower(), f"status/summary leaked marker {marker}")
        for key in (
            "real_config_read",
            "real_config_written",
            "data_written",
            "opt_written",
            "commands_executed",
            "systemctl_called",
            "service_changed",
            "player_started",
            "player_stopped",
            "mpv_called",
            "network_external_access",
            "nmcli_called",
            "backend_called",
            "wifi_changed",
            "private_inputs_used",
        ):
            assert_true(status["guardrails"][key] is False, f"guardrail {key} should be false")

        assert_raises_real_synthetic(
            lambda: run_real_synthetic(str(root / "missing" / "candidate.json"), str(root / "missing-out")),
            "missing source candidate should fail",
        )
        assert_raises_real_synthetic(
            lambda: run_real_synthetic(str(source_path), "/var/tmp/dadooh-c8-5-1"),
            "out-dir outside /tmp should fail",
        )
        invalid_source = dict(source)
        del invalid_source["cache_dir"]
        invalid_source_path = root / "source" / "invalid.json"
        write_private_json(invalid_source_path, invalid_source)
        assert_raises_real_synthetic(
            lambda: run_real_synthetic(str(invalid_source_path), str(root / "invalid-out")),
            "invalid source candidate should fail",
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and validate a C8.5.1 real-synthetic candidate under /tmp.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--source-candidate",
        default=DEFAULT_SOURCE_CANDIDATE,
        help=f"C8 source candidate under /tmp. Default: {DEFAULT_SOURCE_CANDIDATE}",
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}",
    )
    parser.add_argument("--self-test", action="store_true", help="Run local C8.5.1 self-tests under /tmp and exit.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0

        status = run_real_synthetic(args.source_candidate, args.out_dir)
    except RealSyntheticError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except AssertionError:
        print("error: self-test failed", file=sys.stderr)
        return 1
    except OSError:
        print("error: failed to write C8.5.1 artifacts", file=sys.stderr)
        return 1

    print(f"C8.5.1 real-synthetic artifacts generated under {args.out_dir}")
    print(REAL_SYNTHETIC_CANDIDATE_FILENAME)
    print(STATUS_FILENAME)
    print(SUMMARY_FILENAME)
    print(f"real-dry-run: {'passed' if status['contract_validation']['real_synthetic_real_dry_run']['valid'] else 'failed'}")
    print("writer-real: blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
