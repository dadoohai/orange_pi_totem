#!/usr/bin/env python3
"""Validate a C5.1 config candidate contract without operational side effects.

This tool reads only the candidate file provided by --candidate, writes only
validation artifacts under /tmp, never copies the candidate config to output,
and does not access network, NetworkManager, systemd, MPV, /data, or /opt.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import posixpath
import re
import shutil
import stat
import sys
import tempfile
from typing import Any
from urllib.parse import urlparse


SCHEMA_VERSION = "dadooh-c5-config-contract-validate.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c5-config-contract-validate"

STATUS_FILENAME = "validation-status.json"
SUMMARY_FILENAME = "summary.txt"

MOCK_API_URL = "https://api.example.invalid/search"
MOCK_API_KEY = "API_KEY_MOCK_NOT_FOR_PRODUCTION"
MOCK_ENVIRONMENT_ID = "ENVIRONMENT_ID_MOCK"
MOCK_STATION_ID = "STATION_ID_MOCK"

REQUIRED_CONFIG_FIELDS: dict[str, type | tuple[type, ...]] = {
    "api_url": str,
    "api_key": str,
    "environment_id": str,
    "station_id": str,
    "cache_dir": str,
    "state_dir": str,
    "status_file": str,
    "ipc_path": str,
    "runtime_dir": str,
    "strict_paths_enabled": bool,
    "mpv_query_uses_fresh_ipc": bool,
    "mpv_vo": str,
    "mpv_gpu_context": str,
    "mpv_ao": str,
    "low_resource_mode": bool,
}

PATH_RULES: dict[str, tuple[str, ...]] = {
    "cache_dir": ("/data/media",),
    "state_dir": ("/data/state",),
    "status_file": ("/tmp",),
    "ipc_path": ("/tmp",),
    "runtime_dir": ("/tmp",),
}

OPTIONAL_PATH_RULES: dict[str, tuple[str, ...]] = {
    "log_file": ("/data/logs",),
    "mpv_log_file": ("/tmp", "/data/logs"),
}

ENVIRONMENT_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
PLACEHOLDER_LABEL_RE = re.compile(r"(?:mock|test|example|placeholder|replace)", re.IGNORECASE)
PROHIBITED_ID_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url", re.compile(r"https?://", re.IGNORECASE)),
    ("api_key", re.compile(r"api[_-]?key", re.IGNORECASE)),
    ("token", re.compile(r"token", re.IGNORECASE)),
    ("secret", re.compile(r"secret", re.IGNORECASE)),
    ("password", re.compile(r"password", re.IGNORECASE)),
    ("senha", re.compile(r"senha", re.IGNORECASE)),
    ("private_path", re.compile(r"/(?:data|opt|home)/", re.IGNORECASE)),
    ("slash", re.compile(r"/")),
)


class ValidationError(ValueError):
    """Raised for expected validation failures."""


def require_tmp_dir(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    resolved = path.resolve(strict=False)
    tmp_root = pathlib.Path("/tmp").resolve()

    try:
        resolved.relative_to(tmp_root)
    except ValueError as exc:
        raise ValidationError("out-dir must be under /tmp") from exc

    if resolved == tmp_root:
        raise ValidationError("out-dir must be a dedicated directory under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise ValidationError("out-dir exists and is not a directory")
    return resolved


def prepare_out_dir(path: pathlib.Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != 0o700:
        path.chmod(0o700)


def ensure_output_target(path: pathlib.Path, out_dir: pathlib.Path) -> None:
    resolved_out_dir = out_dir.resolve(strict=True)
    resolved_target = path.resolve(strict=False)
    try:
        resolved_target.relative_to(resolved_out_dir)
    except ValueError as exc:
        raise ValidationError("output target escaped out-dir") from exc

    if resolved_target == resolved_out_dir:
        raise ValidationError("output target must be a file")

    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt")):
        try:
            resolved_target.relative_to(forbidden)
        except ValueError:
            continue
        raise ValidationError("refusing to write outside /tmp")


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
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
            text=True,
        )
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
        path.chmod(0o600)
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
    atomic_write_private_text(path, json.dumps(value, indent=2, sort_keys=True), out_dir)


def normalize_candidate_path(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValidationError("candidate file not found") from exc

    if not resolved.is_file():
        raise ValidationError("candidate must be a file")

    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt")):
        try:
            resolved.relative_to(forbidden)
        except ValueError:
            continue
        raise ValidationError("refusing to read candidate from /data or /opt")

    return resolved


def load_candidate(path: pathlib.Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValidationError("candidate is not valid JSON") from exc
    except OSError as exc:
        raise ValidationError("candidate could not be read") from exc

    if not isinstance(value, dict):
        raise ValidationError("candidate JSON root must be an object")
    return value


def is_under_or_equal(raw_value: str, allowed_root: str) -> bool:
    if "\x00" in raw_value:
        return False
    normalized = posixpath.normpath(raw_value)
    if not normalized.startswith("/"):
        return False
    root = posixpath.normpath(allowed_root)
    return normalized == root or normalized.startswith(root.rstrip("/") + "/")


def validate_path_field(
    config: dict[str, Any],
    field: str,
    allowed_roots: tuple[str, ...],
    *,
    optional: bool = False,
) -> tuple[dict[str, str], dict[str, str] | None]:
    if field not in config:
        if optional:
            return {"field": field, "status": "not_present"}, None
        return {"field": field, "status": "missing"}, {"field": field, "reason": "missing"}

    value = config[field]
    if optional and value == "":
        return {"field": field, "status": "empty_allowed"}, None
    if not isinstance(value, str):
        return {"field": field, "status": "invalid", "reason": "not_a_string"}, {
            "field": field,
            "reason": "must be a string",
        }
    if not value:
        return {"field": field, "status": "invalid", "reason": "empty"}, {
            "field": field,
            "reason": "must not be empty",
        }
    if any(is_under_or_equal(value, root) for root in allowed_roots):
        return {"field": field, "status": "ok"}, None
    return {"field": field, "status": "invalid", "reason": "outside_allowed_roots"}, {
        "field": field,
        "reason": "outside allowed roots",
    }


def validate_environment_like_id(raw_value: Any, field: str) -> tuple[dict[str, Any], dict[str, str] | None]:
    status: dict[str, Any] = {
        "present": isinstance(raw_value, str) and bool(raw_value.strip()),
        "valid": False,
        "placeholder_detected": raw_value in {MOCK_ENVIRONMENT_ID, MOCK_STATION_ID},
        "reason": "not_checked",
    }

    if not isinstance(raw_value, str):
        status["reason"] = "not_a_string"
        return status, {"field": field, "reason": "must be a string"}

    value = raw_value.strip()
    if not value:
        status["reason"] = "empty"
        return status, {"field": field, "reason": "must not be empty"}
    if len(value) < 3:
        status["reason"] = "too_short"
        return status, {"field": field, "reason": "must have at least 3 characters"}
    if len(value) > 128:
        status["reason"] = "too_long"
        return status, {"field": field, "reason": "must have at most 128 characters"}
    if re.search(r"\s", value):
        status["reason"] = "contains_whitespace"
        return status, {"field": field, "reason": "must not contain whitespace"}

    for label, pattern in PROHIBITED_ID_PATTERNS:
        if pattern.search(value):
            status["reason"] = f"contains_{label}"
            return status, {"field": field, "reason": f"must not contain {label}"}

    if not ENVIRONMENT_ID_RE.fullmatch(value):
        status["reason"] = "outside_allowlist"
        return status, {"field": field, "reason": "contains characters outside allowlist"}

    status["valid"] = True
    status["reason"] = "ok"
    return status, None


def api_url_uses_invalid_domain(raw_value: str) -> bool:
    parsed = urlparse(raw_value)
    hostname = parsed.hostname or ""
    return hostname == "invalid" or hostname.endswith(".invalid")


def detect_api_key_placeholder(raw_value: Any) -> bool:
    if not isinstance(raw_value, str):
        return False
    if raw_value == MOCK_API_KEY:
        return True
    return bool(PLACEHOLDER_LABEL_RE.search(raw_value))


def append_invalid(invalid_fields: list[dict[str, str]], field: str, reason: str) -> None:
    invalid_fields.append({"field": field, "reason": reason})


def build_base_status(mode: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "valid": False,
        "missing_fields": [],
        "invalid_fields": [],
        "placeholder_findings": [],
        "path_findings": [],
        "api_key_present": False,
        "api_key_placeholder_detected": False,
        "environment_id_status": {
            "present": False,
            "valid": False,
            "placeholder_detected": False,
            "reason": "not_checked",
        },
        "station_id_status": {
            "present": False,
            "valid": False,
            "placeholder_detected": False,
            "reason": "not_checked",
        },
        "privacy_flags": {
            "candidate_config_copied": False,
            "api_key_value_written": False,
            "real_config_read": False,
            "data_written": False,
            "network_access": False,
            "systemctl_called": False,
            "nmcli_called": False,
            "mpv_called": False,
        },
    }


def validate_candidate_config(config: dict[str, Any], mode: str) -> dict[str, Any]:
    status = build_base_status(mode)
    missing_fields = sorted(set(REQUIRED_CONFIG_FIELDS) - set(config))
    invalid_fields: list[dict[str, str]] = []
    placeholder_findings: list[dict[str, str]] = []
    path_findings: list[dict[str, str]] = []

    for field in missing_fields:
        append_invalid(invalid_fields, field, "missing required field")

    for field, expected_type in REQUIRED_CONFIG_FIELDS.items():
        if field not in config:
            continue
        if not isinstance(config[field], expected_type):
            append_invalid(invalid_fields, field, "invalid type")
            continue
        if expected_type is str and not config[field].strip():
            append_invalid(invalid_fields, field, "must not be empty")

    for field, roots in PATH_RULES.items():
        finding, invalid = validate_path_field(config, field, roots)
        path_findings.append(finding)
        if invalid is not None:
            invalid_fields.append(invalid)

    for field, roots in OPTIONAL_PATH_RULES.items():
        finding, invalid = validate_path_field(config, field, roots, optional=True)
        path_findings.append(finding)
        if invalid is not None:
            invalid_fields.append(invalid)

    api_key = config.get("api_key")
    api_key_present = isinstance(api_key, str) and bool(api_key.strip())
    api_key_placeholder = detect_api_key_placeholder(api_key)
    status["api_key_present"] = api_key_present
    status["api_key_placeholder_detected"] = api_key_placeholder
    if api_key_placeholder:
        placeholder_findings.append(
            {
                "field": "api_key",
                "reason": "placeholder_detected",
                "action": "allowed" if mode == "allow-mock" else "blocked",
            }
        )

    api_url = config.get("api_url")
    if isinstance(api_url, str):
        if api_url == MOCK_API_URL:
            placeholder_findings.append(
                {
                    "field": "api_url",
                    "reason": "known_mock_url",
                    "action": "allowed" if mode == "allow-mock" else "blocked",
                }
            )
        elif api_url_uses_invalid_domain(api_url):
            placeholder_findings.append(
                {
                    "field": "api_url",
                    "reason": "invalid_domain",
                    "action": "allowed" if mode == "allow-mock" else "blocked",
                }
            )

    environment_status, environment_invalid = validate_environment_like_id(
        config.get("environment_id"),
        "environment_id",
    )
    station_status, station_invalid = validate_environment_like_id(config.get("station_id"), "station_id")
    status["environment_id_status"] = environment_status
    status["station_id_status"] = station_status
    if environment_invalid is not None:
        invalid_fields.append(environment_invalid)
    if station_invalid is not None:
        invalid_fields.append(station_invalid)

    if environment_status["placeholder_detected"]:
        placeholder_findings.append(
            {
                "field": "environment_id",
                "reason": "known_mock_identifier",
                "action": "allowed" if mode == "allow-mock" else "blocked",
            }
        )
    if station_status["placeholder_detected"]:
        placeholder_findings.append(
            {
                "field": "station_id",
                "reason": "known_mock_identifier",
                "action": "allowed" if mode == "allow-mock" else "blocked",
            }
        )

    if mode == "real-dry-run":
        if not api_key_present:
            append_invalid(invalid_fields, "api_key", "required in real-dry-run")
        if api_key_placeholder:
            append_invalid(invalid_fields, "api_key", "placeholder blocked in real-dry-run")
        if isinstance(api_url, str):
            if api_url == MOCK_API_URL:
                append_invalid(invalid_fields, "api_url", "known mock URL blocked in real-dry-run")
            if api_url_uses_invalid_domain(api_url):
                append_invalid(invalid_fields, "api_url", ".invalid domain blocked in real-dry-run")
        if config.get("environment_id") == MOCK_ENVIRONMENT_ID:
            append_invalid(invalid_fields, "environment_id", "known mock identifier blocked in real-dry-run")
        if config.get("station_id") == MOCK_STATION_ID:
            append_invalid(invalid_fields, "station_id", "known mock identifier blocked in real-dry-run")

    status["missing_fields"] = missing_fields
    status["invalid_fields"] = invalid_fields
    status["placeholder_findings"] = placeholder_findings
    status["path_findings"] = path_findings
    status["valid"] = not missing_fields and not invalid_fields
    return status


def build_summary(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Dadooh C5.1 config contract validator",
            "",
            f"schema_version: {status['schema_version']}",
            f"mode: {status['mode']}",
            f"valid: {str(status['valid']).lower()}",
            f"missing_fields_count: {len(status['missing_fields'])}",
            f"invalid_fields_count: {len(status['invalid_fields'])}",
            f"placeholder_findings_count: {len(status['placeholder_findings'])}",
            f"api_key_present: {str(status['api_key_present']).lower()}",
            "api_key_value_written: false",
            "candidate_config_copied: false",
            "real_config_read: false",
            "data_written: false",
            "network_access: false",
            "systemctl_called: false",
            "nmcli_called: false",
            "mpv_called: false",
        ]
    )


def write_validation_artifacts(out_dir: pathlib.Path, status: dict[str, Any]) -> None:
    prepare_out_dir(out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_summary(status), out_dir)


def file_mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def build_mock_candidate() -> dict[str, Any]:
    return {
        "api_url": MOCK_API_URL,
        "api_key": MOCK_API_KEY,
        "environment_id": MOCK_ENVIRONMENT_ID,
        "station_id": MOCK_STATION_ID,
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


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_invalid(config: dict[str, Any], mode: str, message: str) -> dict[str, Any]:
    status = validate_candidate_config(config, mode)
    assert_true(not status["valid"], message)
    return status


def run_self_test() -> None:
    test_dir = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c5-1-validator-self-test-", dir="/tmp"))
    try:
        mock_candidate = build_mock_candidate()

        allow_status = validate_candidate_config(mock_candidate, "allow-mock")
        assert_true(allow_status["valid"], "mock candidate should pass allow-mock")

        real_status = assert_invalid(
            mock_candidate,
            "real-dry-run",
            "mock candidate should fail real-dry-run",
        )
        assert_true(real_status["api_key_placeholder_detected"], "mock api_key placeholder not detected")

        missing = dict(mock_candidate)
        del missing["api_url"]
        assert_invalid(missing, "allow-mock", "missing required field should fail")

        invalid_cache = dict(mock_candidate)
        invalid_cache["cache_dir"] = "/tmp/cache"
        assert_invalid(invalid_cache, "allow-mock", "cache_dir outside /data/media should fail")

        invalid_status_file = dict(mock_candidate)
        invalid_status_file["status_file"] = "/data/state/status.json"
        assert_invalid(invalid_status_file, "allow-mock", "status_file outside /tmp should fail")

        empty_api_key = dict(mock_candidate)
        empty_api_key["api_key"] = ""
        assert_invalid(empty_api_key, "real-dry-run", "empty api_key should fail real-dry-run")

        mock_api_key = dict(mock_candidate)
        mock_api_key["api_url"] = "https://api.example.com/search"
        mock_api_key["environment_id"] = "ENVIRONMENT_ID_REALISH"
        mock_api_key["station_id"] = "STATION_ID_REALISH"
        assert_invalid(mock_api_key, "real-dry-run", "mock api_key should fail real-dry-run")

        invalid_url = dict(mock_candidate)
        invalid_url["api_key"] = "realish-value-without-placeholder-label"
        invalid_url["environment_id"] = "ENVIRONMENT_ID_REALISH"
        invalid_url["station_id"] = "STATION_ID_REALISH"
        assert_invalid(invalid_url, "real-dry-run", ".invalid api_url should fail real-dry-run")

        invalid_environment = dict(mock_candidate)
        invalid_environment["environment_id"] = "bad environment"
        assert_invalid(invalid_environment, "allow-mock", "invalid environment_id should fail")

        try:
            require_tmp_dir("/var/tmp/dadooh-c5-1-validator")
        except ValidationError:
            pass
        else:
            raise AssertionError("out-dir outside /tmp should fail")

        out_dir = require_tmp_dir(str(test_dir / "out"))
        write_validation_artifacts(out_dir, allow_status)
        assert_true(file_mode(out_dir) == 0o700, "out-dir permission should be 700")
        for name in (STATUS_FILENAME, SUMMARY_FILENAME):
            path = out_dir / name
            assert_true(file_mode(path) == 0o600, f"{name} permission should be 600")
            content = path.read_text(encoding="utf-8")
            assert_true(mock_candidate["api_key"] not in content, "api_key value leaked to validator output")
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a config candidate contract in C5.1 dry-run mode.",
        allow_abbrev=False,
    )
    parser.add_argument("--candidate", help="Candidate JSON file to validate. Refuses /data and /opt.")
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}",
    )
    parser.add_argument("--allow-mock", action="store_true", help="Allow known C5 mock placeholders.")
    parser.add_argument("--real-dry-run", action="store_true", help="Reject placeholders as C6 preparation.")
    parser.add_argument("--self-test", action="store_true", help="Run local self-tests under /tmp and exit.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0

        if args.allow_mock == args.real_dry_run:
            raise ValidationError("choose exactly one of --allow-mock or --real-dry-run")
        if not args.candidate:
            raise ValidationError("--candidate is required unless --self-test is used")

        mode = "allow-mock" if args.allow_mock else "real-dry-run"
        out_dir = require_tmp_dir(args.out_dir)
        candidate_path = normalize_candidate_path(args.candidate)
        config = load_candidate(candidate_path)
        status = validate_candidate_config(config, mode)
        write_validation_artifacts(out_dir, status)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except AssertionError:
        print("error: self-test failed", file=sys.stderr)
        return 1
    except OSError:
        print("error: failed to write validation artifacts", file=sys.stderr)
        return 1

    print(f"C5.1 validation artifacts generated under {out_dir}")
    print(STATUS_FILENAME)
    print(SUMMARY_FILENAME)
    print(f"validation: {'passed' if status['valid'] else 'failed'}")
    return 0 if status["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
