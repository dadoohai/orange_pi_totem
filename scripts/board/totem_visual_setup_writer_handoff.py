#!/usr/bin/env python3
"""C10.0 private handoff from visual setup candidate to the real writer.

This tool reads a visual setup candidate from /tmp, reads approved private
endpoint/credential values from a restricted /tmp file, builds a temporary
private candidate, and validates it with C5.1 real-dry-run. It never writes
/data or /opt, never calls systemctl, never calls the writer, and never prints
private values.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import stat
import sys
import tempfile
from typing import Any


sys.dont_write_bytecode = True

import totem_config_contract_validate as contract


SCHEMA_VERSION = "dadooh-c10.0-visual-setup-writer-handoff.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c10-setup-writer"
PRIVATE_CANDIDATE_FILENAME = "config.candidate.private.json"
STATUS_FILENAME = "setup-status.json"
SUMMARY_FILENAME = "summary.txt"

TMP_ROOT = pathlib.Path("/tmp").resolve()
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
REQUIRED_PRIVATE_FIELDS = ("api_key", "api_url", "environment_id")
OPTIONAL_PRIVATE_FIELDS = ("station_id", "api_token_id")
PRIVATE_METADATA_FIELDS = {
    "setup_source",
    "setup_interface",
    "setup_network_step",
    "setup_connectivity",
    "setup_wifi_activation_result",
    "setup_wifi_rollback_after_test",
    "setup_wifi_dedicated_profile_persistent",
    "setup_display_source",
    "setup_visual_renderer",
    "setup_environment_source",
    "setup_private_values_source",
    "setup_writer_handoff_source",
}
SENSITIVE_MARKER_RE = re.compile(
    r"(api[_-]?key|token|secret|password|senha|ssid|gateway|dns|bssid|hostname|uuid|mac)",
    re.IGNORECASE,
)


class HandoffError(ValueError):
    """Raised for expected C10.0 handoff failures."""


def path_is_under(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def path_is_in_repository(path: pathlib.Path) -> bool:
    current = path if path.is_dir() else path.parent
    for candidate in (current, *current.parents):
        if candidate == pathlib.Path("/tmp"):
            continue
        if (candidate / ".git").exists():
            return True
    return False


def absolute_no_resolve(raw_path: str) -> pathlib.Path:
    return pathlib.Path(os.path.abspath(str(pathlib.Path(raw_path).expanduser())))


def require_tmp_dir(raw_path: str, label: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    raw_absolute = absolute_no_resolve(raw_path)
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise HandoffError(f"{label} must be under /tmp")
    resolved = path.resolve(strict=False)
    if not path_is_under(resolved, TMP_ROOT):
        raise HandoffError(f"{label} must resolve under /tmp")
    if resolved == TMP_ROOT:
        raise HandoffError(f"{label} must be a dedicated directory under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise HandoffError(f"{label} exists and is not a directory")
    if path_is_in_repository(resolved):
        raise HandoffError(f"{label} must not be inside a repository")
    return resolved


def normalize_tmp_file(
    raw_path: str,
    label: str,
    *,
    reject_repo: bool,
    allow_homologation_seed: bool = False,
) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    raw_absolute = absolute_no_resolve(raw_path)
    homologation_seed = pathlib.Path("/data/state/totem-settings/private-values.seed.json")
    if allow_homologation_seed and label == "private values" and raw_absolute == homologation_seed:
        if path.is_symlink():
            raise HandoffError(f"{label} must not be a symlink")
        try:
            resolved_seed = path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise HandoffError(f"{label} file not found") from exc
        if resolved_seed != homologation_seed:
            raise HandoffError("homologation private seed path mismatch")
        if not resolved_seed.is_file():
            raise HandoffError(f"{label} must be a file")
        return resolved_seed
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise HandoffError(f"{label} must be under /tmp")
    if path.is_symlink():
        raise HandoffError(f"{label} must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise HandoffError(f"{label} file not found") from exc
    if not path_is_under(resolved, TMP_ROOT):
        raise HandoffError(f"{label} must resolve under /tmp")
    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt"), pathlib.Path("/home")):
        if path_is_under(resolved, forbidden):
            raise HandoffError(f"refusing {label} under {forbidden}")
    if reject_repo and path_is_in_repository(resolved):
        raise HandoffError(f"{label} must not be inside a repository")
    if not resolved.is_file():
        raise HandoffError(f"{label} must be a file")
    return resolved


def validate_restricted_private_file(path: pathlib.Path) -> None:
    if path.is_symlink():
        raise HandoffError("private values file must not be a symlink")
    if path.parent.is_symlink():
        raise HandoffError("private values parent must not be a symlink")
    parent_mode = stat.S_IMODE(path.parent.stat().st_mode)
    file_mode = stat.S_IMODE(path.stat().st_mode)
    if parent_mode & 0o077:
        raise HandoffError("private values parent must not grant group/other access")
    if file_mode & 0o077 or not (file_mode & 0o600):
        raise HandoffError("private values file must be mode 0600 or stricter")


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
        raise HandoffError("output target escaped out-dir")
    if resolved_target == resolved_out:
        raise HandoffError("output target must be a file")


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
        raise HandoffError(f"{label} is not valid JSON") from exc
    except OSError as exc:
        raise HandoffError(f"{label} could not be read") from exc
    if not isinstance(value, dict):
        raise HandoffError(f"{label} JSON root must be an object")
    return value


def validate_private_values(value: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for field in REQUIRED_PRIVATE_FIELDS:
        raw = value.get(field)
        if not isinstance(raw, str) or not raw.strip():
            raise HandoffError("required private category missing or invalid")
        result[field] = raw.strip()
    for field in OPTIONAL_PRIVATE_FIELDS:
        raw = value.get(field)
        if raw is None:
            continue
        if not isinstance(raw, str):
            raise HandoffError("optional private category has invalid type")
        if raw.strip():
            result[field] = raw.strip()
    return result


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


def build_private_candidate(
    source: dict[str, Any],
    private_values: dict[str, str],
    *,
    private_values_source: str,
) -> dict[str, Any]:
    candidate = dict(source)
    candidate["api_url"] = private_values["api_url"]
    candidate["api_key"] = private_values["api_key"]
    if private_values.get("station_id"):
        candidate["station_id"] = private_values["station_id"]
    if private_values.get("api_token_id"):
        candidate["api_token_id"] = private_values["api_token_id"]
    candidate["setup_source"] = "c10.0-visual-setup-writer-handoff"
    candidate["setup_private_values_source"] = private_values_source
    candidate["setup_writer_handoff_source"] = "visual_setup_candidate"
    return candidate


def require_private_environment_binding(
    source: dict[str, Any],
    private_values: dict[str, str],
) -> bool:
    private_environment = private_values["environment_id"]
    source_environment = source.get("environment_id")
    if (
        not isinstance(source_environment, str)
        or not source_environment.strip()
        or source_environment.strip() != private_environment
    ):
        raise HandoffError("private credential does not match selected environment")
    return True


def build_status(
    *,
    source_candidate: dict[str, Any],
    private_candidate: dict[str, Any],
    private_values: dict[str, str],
    source_allow_status: dict[str, Any],
    private_allow_status: dict[str, Any],
    private_real_status: dict[str, Any],
    private_environment_binding_verified: bool,
) -> dict[str, Any]:
    known_fields = set(contract.REQUIRED_CONFIG_FIELDS) | set(contract.OPTIONAL_CONFIG_FIELDS)
    return {
        "schema_version": SCHEMA_VERSION,
        "result": "passed",
        "phase": "private_candidate_ready_for_writer",
        "source_candidate": {
            "read_from_tmp": True,
            "allow_mock_valid": bool(source_allow_status["valid"]),
            "copied_to_status": False,
            "copied_to_summary": False,
            "environment_identifier_present": bool(source_candidate.get("environment_id")),
            "environment_identifier_raw_written": False,
            "rotation_degrees_present": "rotation_deg" in source_candidate,
            "values_written_to_public_artifacts": False,
        },
        "private_inputs": {
            "read_from_tmp": True,
            "parent_mode_0700": True,
            "file_mode_0600": True,
            "endpoint_present": bool(private_values.get("api_url")),
            "credential_present": bool(private_values.get("api_key")),
            "optional_station_identifier_provided": bool(private_values.get("station_id")),
            "environment_identifier_from_private_values_used": False,
            "environment_identifier_binding_verified": private_environment_binding_verified,
            "values_written_to_public_artifacts": False,
        },
        "private_candidate": {
            "file": PRIVATE_CANDIDATE_FILENAME,
            "written_under_tmp": True,
            "contains_private_values": True,
            "copied_to_status": False,
            "copied_to_summary": False,
            "required_contract_fields_present_count": sum(
                1 for field in contract.REQUIRED_CONFIG_FIELDS if field in private_candidate
            ),
            "extra_fields_count": len(set(private_candidate) - known_fields),
        },
        "contract_validation": {
            "validator": "totem_config_contract_validate.py",
            "source_allow_mock": summarize_validation(source_allow_status),
            "private_allow_mock": summarize_validation(private_allow_status),
            "private_real_dry_run": summarize_validation(private_real_status),
            "private_real_dry_run_passed": True,
            "placeholder_findings_cleared": len(private_real_status["placeholder_findings"]) == 0,
        },
        "writer_handoff": {
            "candidate_ready_for_writer_validation": True,
            "candidate_ready_for_real_write": True,
            "writer_real_mode_called": False,
            "writer_simulated_write_called": False,
            "enable_real_write_used": False,
            "future_writer_must_validate_again": True,
            "future_writer_must_preserve_backup_and_rollback": True,
            "future_writer_requires_service_blocked": True,
            "future_writer_requires_human_approval": True,
        },
        "guardrails": {
            "writes_only_under_tmp": True,
            "real_config_read": False,
            "real_config_written": False,
            "writer_called": False,
            "enable_real_write_used": False,
            "systemctl_called": False,
            "service_changed": False,
            "player_started": False,
            "player_stopped": False,
            "mpv_called": False,
            "network_external_access": False,
            "wifi_changed": False,
            "hotspot_created": False,
            "portal_created": False,
            "backend_called": False,
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
            "network_identifiers_written": False,
            "raw_logs_written": False,
        },
    }


def build_summary(status: dict[str, Any]) -> str:
    validation = status["contract_validation"]
    return "\n".join(
        [
            "Dadooh C10.0 visual setup writer handoff",
            "",
            f"schema_version: {status['schema_version']}",
            f"result: {status['result']}",
            f"phase: {status['phase']}",
            "source_candidate_read_from_tmp: true",
            "source_candidate_values_written_to_summary: false",
            "private_inputs_read_from_tmp: true",
            "private_values_written_to_summary: false",
            "private_candidate: config.candidate.private.json",
            "private_candidate_written_under_tmp: true",
            "private_candidate_values_written_to_summary: false",
            f"source_allow_mock_valid: {str(validation['source_allow_mock']['valid']).lower()}",
            f"private_real_dry_run_valid: {str(validation['private_real_dry_run']['valid']).lower()}",
            f"placeholder_findings_cleared: {str(validation['placeholder_findings_cleared']).lower()}",
            "writer_real_mode_called: false",
            "enable_real_write_used: false",
            "",
            "Guardrails:",
            "writes_only_under_tmp: true",
            "real_config_read: false",
            "real_config_written: false",
            "writer_called: false",
            "systemctl_called: false",
            "service_changed: false",
            "player_started: false",
            "player_stopped: false",
            "mpv_called: false",
            "wifi_changed: false",
            "hotspot_created: false",
            "portal_created: false",
            "",
            "Privacy:",
            "private_values_public: false",
            "private_candidate_copied_to_public_artifacts: false",
            "credential_value_public: false",
            "endpoint_value_public: false",
            "environment_identifier_raw_public: false",
            "network_identifiers_public: false",
            "raw_logs_written: false",
        ]
    )


def forbidden_text_variants(value: str) -> tuple[str, str]:
    escaped = json.dumps(value, ensure_ascii=True)[1:-1]
    return value, escaped


def public_artifact_text(out_dir: pathlib.Path) -> str:
    parts = []
    for name in (STATUS_FILENAME, SUMMARY_FILENAME):
        path = out_dir / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def assert_sanitized_public_artifacts(
    out_dir: pathlib.Path,
    source_candidate: dict[str, Any],
    private_values: dict[str, str],
) -> None:
    text = public_artifact_text(out_dir)
    forbidden_values: list[str] = []
    for value in private_values.values():
        if value:
            forbidden_values.append(value)
    for field, value in source_candidate.items():
        if field in PRIVATE_METADATA_FIELDS:
            continue
        if isinstance(value, str) and value:
            forbidden_values.append(value)
    for value in forbidden_values:
        for variant in forbidden_text_variants(value):
            if variant and variant in text:
                raise HandoffError("privacy scan blocked private value in status/summary")
    if SENSITIVE_MARKER_RE.search(text):
        raise HandoffError("privacy scan blocked sensitive marker in status/summary")


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
    assert_sanitized_public_artifacts(out_dir, source_candidate, private_values)


def run_handoff(
    *,
    source_candidate_raw: str,
    private_values_raw: str,
    out_dir_raw: str,
    confirm_private_values_approved: bool,
    allow_homologation_seed: bool = False,
) -> dict[str, Any]:
    if not confirm_private_values_approved:
        raise HandoffError("private handoff requires explicit approval")

    out_dir = require_tmp_dir(out_dir_raw, "out-dir")
    source_path = normalize_tmp_file(source_candidate_raw, "source candidate", reject_repo=False)
    private_values_path = normalize_tmp_file(
        private_values_raw,
        "private values",
        reject_repo=True,
        allow_homologation_seed=allow_homologation_seed,
    )
    validate_restricted_private_file(private_values_path)

    source_candidate = load_json_object(source_path, "source candidate")
    private_values = validate_private_values(load_json_object(private_values_path, "private values"))
    private_environment_binding_verified = require_private_environment_binding(
        source_candidate,
        private_values,
    )
    private_source = (
        "homologation_private_seed"
        if str(private_values_path) == "/data/state/totem-settings/private-values.seed.json"
        else "private_tmp_file"
    )
    private_candidate = build_private_candidate(
        source_candidate,
        private_values,
        private_values_source=private_source,
    )

    source_allow_status = contract.validate_candidate_config(source_candidate, "allow-mock")
    private_allow_status = contract.validate_candidate_config(private_candidate, "allow-mock")
    private_real_status = contract.validate_candidate_config(private_candidate, "real-dry-run")

    if not source_allow_status["valid"]:
        raise HandoffError("source candidate failed C5.1 allow-mock validation")
    if not private_allow_status["valid"]:
        raise HandoffError("private candidate failed C5.1 allow-mock validation")
    if not private_real_status["valid"]:
        raise HandoffError("private candidate failed C5.1 real-dry-run validation")
    if private_real_status["placeholder_findings"]:
        raise HandoffError("private candidate still has placeholder findings")

    status = build_status(
        source_candidate=source_candidate,
        private_candidate=private_candidate,
        private_values=private_values,
        source_allow_status=source_allow_status,
        private_allow_status=private_allow_status,
        private_real_status=private_real_status,
        private_environment_binding_verified=private_environment_binding_verified,
    )
    write_outputs(out_dir, private_candidate, status, source_candidate, private_values)
    return status


def write_json_file(path: pathlib.Path, value: dict[str, Any], *, mode: int = PRIVATE_FILE_MODE) -> None:
    prepare_private_dir(path.parent)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(mode)


def build_source_candidate() -> dict[str, Any]:
    candidate = contract.build_mock_candidate()
    candidate["environment_id"] = "ENV-C10-HANDOFF-SMOKE"
    candidate["rotation_deg"] = 90
    candidate["setup_source"] = "c10.0-self-test-source"
    return candidate


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_raises_handoff(fn: Any, message: str) -> None:
    try:
        fn()
    except HandoffError:
        return
    raise AssertionError(message)


def run_self_test() -> None:
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c10-handoff-self-test-", dir="/tmp"))
    try:
        source_path = root / "source" / "config.candidate.json"
        private_values_path = root / "private" / "private-values.json"
        write_json_file(source_path, build_source_candidate())
        write_json_file(
            private_values_path,
            {
                "api_url": "https://api.sandbox.localhost/search",
                "api_key": "REALISHVALUEABC1234567890",
                "station_id": "STATION-C10-HANDOFF-SMOKE",
                "environment_id": "ENV-C10-HANDOFF-SMOKE",
                "api_token_id": "33333333-4444-4555-8666-777777777777",
            },
        )
        assert_true(stat.S_IMODE(private_values_path.parent.stat().st_mode) == 0o700, "private dir should be 0700")
        assert_true(stat.S_IMODE(private_values_path.stat().st_mode) == 0o600, "private file should be 0600")

        assert_raises_handoff(
            lambda: run_handoff(
                source_candidate_raw=str(source_path),
                private_values_raw=str(private_values_path),
                out_dir_raw=str(root / "out-no-confirm"),
                confirm_private_values_approved=False,
            ),
            "handoff without confirmation should fail",
        )

        insecure_values = root / "insecure" / "private-values.json"
        write_json_file(insecure_values, {"api_url": "https://api.sandbox.localhost/search", "api_key": "REALISH"})
        insecure_values.chmod(0o644)
        assert_raises_handoff(
            lambda: run_handoff(
                source_candidate_raw=str(source_path),
                private_values_raw=str(insecure_values),
                out_dir_raw=str(root / "out-insecure"),
                confirm_private_values_approved=True,
            ),
            "insecure private file should fail",
        )

        repo = root / "repo"
        (repo / ".git").mkdir(parents=True)
        repo_values = repo / "private-values.json"
        write_json_file(repo_values, {"api_url": "https://api.sandbox.localhost/search", "api_key": "REALISH"})
        assert_raises_handoff(
            lambda: run_handoff(
                source_candidate_raw=str(source_path),
                private_values_raw=str(repo_values),
                out_dir_raw=str(root / "out-repo"),
                confirm_private_values_approved=True,
            ),
            "private file inside repository should fail",
        )

        unsafe_source_path = root / "source" / "config.unsafe-mpv-path.json"
        unsafe_source = build_source_candidate()
        unsafe_source["mpv_path"] = "mpv"
        write_json_file(unsafe_source_path, unsafe_source)
        assert_raises_handoff(
            lambda: run_handoff(
                source_candidate_raw=str(unsafe_source_path),
                private_values_raw=str(private_values_path),
                out_dir_raw=str(root / "out-unsafe-mpv-path"),
                confirm_private_values_approved=True,
            ),
            "handoff should reject unsafe C18 mpv_path before writer",
        )

        mismatched_values = root / "private-mismatched" / "private-values.json"
        write_json_file(
            mismatched_values,
            {
                "api_url": "https://api.sandbox.localhost/search",
                "api_key": "REALISHVALUEABC1234567890",
                "station_id": "STATION-C10-HANDOFF-SMOKE",
                "environment_id": "ENV-C10-HANDOFF-OTHER",
                "api_token_id": "33333333-4444-4555-8666-777777777777",
            },
        )
        assert_raises_handoff(
            lambda: run_handoff(
                source_candidate_raw=str(source_path),
                private_values_raw=str(mismatched_values),
                out_dir_raw=str(root / "out-mismatched-environment"),
                confirm_private_values_approved=True,
            ),
            "handoff should reject credentials bound to another environment",
        )

        unbound_values = root / "private-unbound" / "private-values.json"
        write_json_file(
            unbound_values,
            {
                "api_url": "https://api.sandbox.localhost/search",
                "api_key": "REALISHVALUEABC1234567890",
            },
        )
        assert_raises_handoff(
            lambda: run_handoff(
                source_candidate_raw=str(source_path),
                private_values_raw=str(unbound_values),
                out_dir_raw=str(root / "out-unbound-environment"),
                confirm_private_values_approved=True,
            ),
            "private source without environment binding should fail closed",
        )

        out_dir = root / "out"
        status = run_handoff(
            source_candidate_raw=str(source_path),
            private_values_raw=str(private_values_path),
            out_dir_raw=str(out_dir),
            confirm_private_values_approved=True,
        )
        assert_true(status["result"] == "passed", "handoff should pass")
        assert_true(status["contract_validation"]["private_real_dry_run_passed"], "real-dry-run should pass")
        assert_true(
            status["private_inputs"]["environment_identifier_binding_verified"],
            "private environment binding should be verified",
        )
        private_candidate = json.loads((out_dir / PRIVATE_CANDIDATE_FILENAME).read_text(encoding="utf-8"))
        assert_true(private_candidate["environment_id"] == "ENV-C10-HANDOFF-SMOKE", "wizard env should be preserved")
        assert_true(private_candidate["rotation_deg"] == 90, "rotation should be preserved")
        assert_true(private_candidate["api_key"] == "REALISHVALUEABC1234567890", "credential should be injected")
        assert_true(
            private_candidate["api_token_id"] == "33333333-4444-4555-8666-777777777777",
            "activation token identity should survive the private handoff",
        )
        assert_true(stat.S_IMODE((out_dir / PRIVATE_CANDIDATE_FILENAME).stat().st_mode) == 0o600, "private candidate should be 0600")
        assert_sanitized_public_artifacts(out_dir, build_source_candidate(), validate_private_values(load_json_object(private_values_path, "private values")))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a C10.0 private writer candidate from visual setup output.")
    parser.add_argument("--source-candidate", default="/tmp/dadooh-c9-9-visual-wizard/config.candidate.json")
    parser.add_argument("--private-values", default="/tmp/dadooh-c10-private/private-values.json")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--confirm-private-values-approved", action="store_true")
    parser.add_argument("--allow-homologation-seed", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        try:
            run_self_test()
        except AssertionError:
            print("error: self-test failed", file=sys.stderr)
            return 1
        except Exception:
            print("error: self-test failed", file=sys.stderr)
            return 1
        print("self-test: ok")
        return 0

    try:
        status = run_handoff(
            source_candidate_raw=args.source_candidate,
            private_values_raw=args.private_values,
            out_dir_raw=args.out_dir,
            confirm_private_values_approved=bool(args.confirm_private_values_approved),
            allow_homologation_seed=bool(args.allow_homologation_seed),
        )
    except HandoffError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
