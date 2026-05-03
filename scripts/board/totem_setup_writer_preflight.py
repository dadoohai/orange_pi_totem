#!/usr/bin/env python3
"""C8.5.0 preflight for setup -> writer/config handoff.

This tool reads a C8 setup candidate from /tmp, validates it with the C5.1
contract, confirms that real-dry-run is still blocked by mock placeholders, and
writes a sanitized handoff report under /tmp. It never calls the C6 writer in
real mode, never reads /data/config/config.json, never writes /data or /opt,
and never calls external commands.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import os
import pathlib
import shutil
import stat
import sys
import tempfile
from typing import Any


sys.dont_write_bytecode = True

import totem_config_contract_validate as contract


SCHEMA_VERSION = "dadooh-c8.5.0-setup-writer-preflight.v1"
DEFAULT_CANDIDATE = "/tmp/dadooh-c8-1-setup-minimo/candidate-config.json"
DEFAULT_OUT_DIR = "/tmp/dadooh-c8-5-preflight"

STATUS_FILENAME = "preflight-status.json"
SUMMARY_FILENAME = "summary.txt"

TMP_ROOT = pathlib.Path("/tmp").resolve()
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600

SETUP_HANDOFF_FIELDS = ("rotation_deg", "setup_source", "setup_environment_source")
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


class PreflightError(ValueError):
    """Raised for expected C8.5.0 preflight failures."""


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
        raise PreflightError("out-dir must be under /tmp")
    if resolved == TMP_ROOT:
        raise PreflightError("out-dir must be a dedicated directory under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise PreflightError("out-dir exists and is not a directory")
    return resolved


def normalize_candidate_path(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    raw_absolute = pathlib.Path(os.path.abspath(str(path)))
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise PreflightError("candidate must be under /tmp")

    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PreflightError("candidate file not found") from exc

    if not path_is_under(resolved, TMP_ROOT):
        raise PreflightError("candidate must resolve under /tmp")
    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt")):
        if path_is_under(resolved, forbidden):
            raise PreflightError(f"refusing candidate under {forbidden}")
    if not resolved.is_file():
        raise PreflightError("candidate must be a file")
    return resolved


def prepare_private_dir(path: pathlib.Path) -> None:
    path.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    if stat.S_IMODE(path.stat().st_mode) != PRIVATE_DIR_MODE:
        path.chmod(PRIVATE_DIR_MODE)


def ensure_output_target(path: pathlib.Path, out_dir: pathlib.Path) -> None:
    resolved_out = out_dir.resolve(strict=True)
    resolved_target = path.resolve(strict=False)
    if not path_is_under(resolved_target, resolved_out):
        raise PreflightError("output target escaped out-dir")
    if resolved_target == resolved_out:
        raise PreflightError("output target must be a file")
    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt")):
        if path_is_under(resolved_target, forbidden):
            raise PreflightError("refusing to write outside /tmp")


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


def load_candidate(path: pathlib.Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError as exc:
        raise PreflightError("candidate is not valid JSON") from exc
    except OSError as exc:
        raise PreflightError("candidate could not be read") from exc

    if not isinstance(value, dict):
        raise PreflightError("candidate JSON root must be an object")
    return value


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


def category_for_placeholder(finding: dict[str, str]) -> str:
    field = finding.get("field", "")
    if field == "api_key":
        return "runtime_credential_private_value_required"
    if field == "api_url":
        return "backend_endpoint_private_value_required"
    if field == "environment_id":
        return "environment_identity_private_value_required"
    return "other_private_value_required"


def candidate_uses_mock_environment(candidate: dict[str, Any]) -> bool:
    value = candidate.get("environment_id")
    if not isinstance(value, str):
        return False
    return value.startswith("ENV-MOCK-") or value in {contract.MOCK_ENVIRONMENT_ID}


def build_gap_report(candidate: dict[str, Any], real_status: dict[str, Any]) -> dict[str, Any]:
    categories = {category_for_placeholder(item) for item in real_status["placeholder_findings"]}
    if candidate_uses_mock_environment(candidate):
        categories.add("environment_selection_mock_catalog")

    return {
        "private_value_categories": sorted(categories),
        "private_value_categories_count": len(categories),
        "credential_private_value_required": "runtime_credential_private_value_required" in categories,
        "backend_endpoint_private_value_required": "backend_endpoint_private_value_required" in categories,
        "station_identity_optional_future": True,
        "environment_selection_still_mock": "environment_selection_mock_catalog" in categories,
        "writer_preconditions_missing": {
            "real_dry_run_valid": False,
            "private_values_available_from_secure_channel": False,
            "service_or_player_blocked_before_write": False,
            "rollback_backup_policy_confirmed": False,
            "human_approved_real_write": False,
        },
    }


def build_status(
    *,
    generated_at: str,
    candidate: dict[str, Any],
    allow_status: dict[str, Any],
    real_status: dict[str, Any],
) -> dict[str, Any]:
    gap_report = build_gap_report(candidate, real_status)
    required_count = len(contract.REQUIRED_CONFIG_FIELDS)
    present_required_count = sum(1 for field in contract.REQUIRED_CONFIG_FIELDS if field in candidate)
    handoff_present_count = sum(1 for field in SETUP_HANDOFF_FIELDS if field in candidate)
    known_contract_fields = set(contract.REQUIRED_CONFIG_FIELDS) | set(contract.OPTIONAL_CONFIG_FIELDS)
    extra_fields_count = len(set(candidate) - known_contract_fields)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "result": "passed",
        "phase": "preflight_completed",
        "candidate": {
            "exists": True,
            "read_from_tmp": True,
            "config_copied_to_output": False,
            "required_contract_fields_count": required_count,
            "required_contract_fields_present_count": present_required_count,
            "handoff_fields_present_count": handoff_present_count,
            "extra_fields_count": extra_fields_count,
            "raw_environment_identifier_written": False,
            "raw_paths_written": False,
        },
        "contract_validation": {
            "validator": "totem_config_contract_validate.py",
            "contract": "C5.1",
            "allow_mock": summarize_validation(allow_status),
            "real_dry_run": summarize_validation(real_status),
            "real_dry_run_expected_failure": True,
            "real_dry_run_failure_reason_categories_only": True,
        },
        "gap_report": gap_report,
        "writer_handoff": {
            "target": "C6 guarded writer",
            "writer_real_mode_called": False,
            "writer_simulated_write_called": False,
            "writer_real_write_blocked": True,
            "enable_real_write_used": False,
            "config_ready_for_real_writer": False,
            "handoff_decision": "blocked_until_private_values_and_preconditions",
            "candidate_partial_write_risk": "must_not_write_until_real_dry_run_passes",
            "future_writer_must_validate_again": True,
            "future_writer_must_write_atomically": True,
            "future_writer_must_preserve_backup_and_rollback": True,
        },
        "guardrails": {
            "writes_only_under_tmp": True,
            "real_config_read": False,
            "real_config_written": False,
            "candidate_read_from_data": False,
            "candidate_read_from_opt": False,
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
            "private_values_used": False,
        },
        "privacy": {
            "candidate_config_copied_to_output": False,
            "operator_input_copied_to_output": False,
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
            "preflight_status": STATUS_FILENAME,
            "summary": SUMMARY_FILENAME,
        },
    }


def build_summary(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Dadooh C8.5.0 setup writer preflight",
            "",
            f"schema_version: {status['schema_version']}",
            f"generated_at_utc: {status['generated_at_utc']}",
            f"result: {status['result']}",
            f"phase: {status['phase']}",
            "candidate_exists: true",
            "candidate_read_from_tmp: true",
            f"required_contract_fields_count: {status['candidate']['required_contract_fields_count']}",
            f"required_contract_fields_present_count: {status['candidate']['required_contract_fields_present_count']}",
            f"handoff_fields_present_count: {status['candidate']['handoff_fields_present_count']}",
            f"extra_fields_count: {status['candidate']['extra_fields_count']}",
            f"allow_mock_valid: {str(status['contract_validation']['allow_mock']['valid']).lower()}",
            "real_dry_run_valid: false",
            "real_dry_run_expected_failure: true",
            "private_value_categories_count: "
            f"{status['gap_report']['private_value_categories_count']}",
            "credential_private_value_required: "
            f"{str(status['gap_report']['credential_private_value_required']).lower()}",
            "backend_endpoint_private_value_required: "
            f"{str(status['gap_report']['backend_endpoint_private_value_required']).lower()}",
            "station_identity_optional_future: "
            f"{str(status['gap_report']['station_identity_optional_future']).lower()}",
            "environment_selection_still_mock: "
            f"{str(status['gap_report']['environment_selection_still_mock']).lower()}",
            "writer_real_write_blocked: true",
            "writer_real_mode_called: false",
            "writer_simulated_write_called: false",
            "config_ready_for_real_writer: false",
            "handoff_decision: blocked_until_private_values_and_preconditions",
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
            "nmcli_called: false",
            "backend_called: false",
            "wifi_changed: false",
            "private_values_used: false",
            "",
            "Privacy:",
            "candidate_config_copied_to_output: false",
            "operator_input_copied_to_output: false",
            "credential_value_written_to_output: false",
            "endpoint_value_written_to_output: false",
            "environment_identifier_raw_written_to_output: false",
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


def assert_sanitized_outputs(out_dir: pathlib.Path, candidate: dict[str, Any]) -> None:
    text = output_text(out_dir)
    for value in candidate.values():
        if not isinstance(value, str) or not value:
            continue
        for variant in forbidden_text_variants(value):
            if variant and variant in text:
                raise PreflightError("privacy scan blocked candidate value in preflight output")

    for marker in SENSITIVE_OUTPUT_MARKERS:
        if marker in text.lower():
            raise PreflightError("privacy scan blocked sensitive marker in preflight output")


def write_preflight_artifacts(out_dir: pathlib.Path, status: dict[str, Any], candidate: dict[str, Any]) -> None:
    prepare_private_dir(out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_summary(status), out_dir)
    assert_sanitized_outputs(out_dir, candidate)


def run_preflight(candidate_raw: str, out_dir_raw: str) -> dict[str, Any]:
    out_dir = require_tmp_dir(out_dir_raw)
    candidate_path = normalize_candidate_path(candidate_raw)
    candidate = load_candidate(candidate_path)

    allow_status = contract.validate_candidate_config(candidate, "allow-mock")
    real_status = contract.validate_candidate_config(candidate, "real-dry-run")

    if not allow_status["valid"]:
        raise PreflightError("candidate failed C5.1 allow-mock validation")
    if real_status["valid"]:
        raise PreflightError("candidate unexpectedly passed C5.1 real-dry-run")
    if not real_status["placeholder_findings"]:
        raise PreflightError("candidate failed real-dry-run without placeholder findings")

    status = build_status(
        generated_at=utc_timestamp(),
        candidate=candidate,
        allow_status=allow_status,
        real_status=real_status,
    )
    write_preflight_artifacts(out_dir, status, candidate)
    return status


def file_mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def build_c8_mock_candidate() -> dict[str, Any]:
    candidate = contract.build_mock_candidate()
    candidate["environment_id"] = "ENV-MOCK-LOJA-A"
    candidate["rotation_deg"] = 90
    candidate["setup_environment_source"] = "mock_list"
    candidate["setup_source"] = "c8.5.0-self-test-setup-candidate"
    return candidate


def write_private_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    prepare_private_dir(path.parent)
    payload = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(payload)
    path.chmod(PRIVATE_FILE_MODE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_raises_preflight(fn: Any, message: str) -> None:
    try:
        fn()
    except PreflightError:
        return
    raise AssertionError(message)


def run_self_test() -> None:
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c8-5-preflight-self-test-", dir="/tmp"))
    try:
        candidate = build_c8_mock_candidate()
        allow_status = contract.validate_candidate_config(candidate, "allow-mock")
        real_status = contract.validate_candidate_config(candidate, "real-dry-run")
        assert_true(allow_status["valid"], "C8 mock candidate should pass allow-mock")
        assert_true(not real_status["valid"], "C8 mock candidate should fail real-dry-run")
        assert_true(real_status["placeholder_findings"], "C8 mock candidate should expose placeholder findings")

        candidate_path = root / "candidate" / "candidate-config.json"
        write_private_json(candidate_path, candidate)

        out_dir = root / "out"
        status = run_preflight(str(candidate_path), str(out_dir))
        assert_true(status["result"] == "passed", "preflight should pass for C8 mock candidate")
        assert_true(status["contract_validation"]["allow_mock"]["valid"], "status should record allow-mock pass")
        assert_true(
            status["contract_validation"]["real_dry_run_expected_failure"],
            "status should record expected real-dry-run failure",
        )
        assert_true(status["writer_handoff"]["writer_real_write_blocked"], "writer real write should be blocked")
        assert_true(not status["writer_handoff"]["writer_real_mode_called"], "writer real mode should not be called")
        assert_true(file_mode(out_dir) == PRIVATE_DIR_MODE, "out-dir mode should be 700")
        for name in (STATUS_FILENAME, SUMMARY_FILENAME):
            path = out_dir / name
            assert_true(path.exists(), f"{name} should exist")
            assert_true(file_mode(path) == PRIVATE_FILE_MODE, f"{name} mode should be 600")
            resolved = path.resolve(strict=True)
            assert_true(path_is_under(resolved, TMP_ROOT), f"{name} should be under /tmp")
            assert_true(not path_is_under(resolved, pathlib.Path("/data")), f"{name} wrote under /data")
            assert_true(not path_is_under(resolved, pathlib.Path("/opt")), f"{name} wrote under /opt")

        text = output_text(out_dir)
        for value in candidate.values():
            if isinstance(value, str) and value:
                for variant in forbidden_text_variants(value):
                    assert_true(variant not in text, "preflight output leaked candidate value")
        for marker in SENSITIVE_OUTPUT_MARKERS:
            assert_true(marker not in text.lower(), f"preflight output leaked marker {marker}")
        assert_true(status["guardrails"]["data_written"] is False, "status should mark data_written false")
        assert_true(status["guardrails"]["opt_written"] is False, "status should mark opt_written false")
        assert_true(status["guardrails"]["commands_executed"] is False, "status should mark commands false")
        assert_true(status["guardrails"]["systemctl_called"] is False, "status should mark systemctl false")
        assert_true(status["guardrails"]["mpv_called"] is False, "status should mark mpv false")

        assert_raises_preflight(
            lambda: run_preflight(str(root / "missing" / "candidate-config.json"), str(root / "missing-out")),
            "missing candidate should fail",
        )
        assert_raises_preflight(
            lambda: run_preflight(str(candidate_path), "/var/tmp/dadooh-c8-5-preflight"),
            "out-dir outside /tmp should fail",
        )

        invalid_candidate = dict(candidate)
        del invalid_candidate["cache_dir"]
        invalid_path = root / "candidate" / "candidate-invalid.json"
        write_private_json(invalid_path, invalid_candidate)
        assert_raises_preflight(
            lambda: run_preflight(str(invalid_path), str(root / "invalid-out")),
            "invalid candidate should fail",
        )

        realish = dict(candidate)
        realish["api_url"] = "https://api.sandbox.localhost/search"
        realish["api_key"] = "RUNTIMEVALUEABC1234567890"
        realish["station_id"] = "STATION_REALISH_001"
        realish_path = root / "candidate" / "candidate-realish.json"
        write_private_json(realish_path, realish)
        assert_raises_preflight(
            lambda: run_preflight(str(realish_path), str(root / "realish-out")),
            "candidate that passes real-dry-run should fail this preflight stage",
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run C8.5.0 setup -> writer/config preflight under /tmp.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--candidate",
        default=DEFAULT_CANDIDATE,
        help=f"Candidate JSON under /tmp. Default: {DEFAULT_CANDIDATE}",
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}",
    )
    parser.add_argument("--self-test", action="store_true", help="Run local C8.5.0 self-tests under /tmp and exit.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0

        status = run_preflight(args.candidate, args.out_dir)
    except PreflightError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except AssertionError:
        print("error: self-test failed", file=sys.stderr)
        return 1
    except OSError:
        print("error: failed to write preflight artifacts", file=sys.stderr)
        return 1

    print(f"C8.5.0 preflight artifacts generated under {args.out_dir}")
    print(STATUS_FILENAME)
    print(SUMMARY_FILENAME)
    print(f"allow-mock: {'passed' if status['contract_validation']['allow_mock']['valid'] else 'failed'}")
    print("real-dry-run: expected-failure")
    print("writer-real: blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
