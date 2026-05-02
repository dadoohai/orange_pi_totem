#!/usr/bin/env python3
"""Generate a C5 mock player config candidate under /tmp only.

This tool is intentionally non-operational. It does not read the real config,
does not access the network, does not call system tools, and never writes to
/data. Appliance paths may appear as future config strings in the mock JSON,
but they are not created, read, or written.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import os
import pathlib
import re
import shutil
import stat
import sys
import tempfile
from typing import Any


SCHEMA_VERSION = "dadooh-c5-config-writer-mock.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c5-config-writer-mock"

CONFIG_FILENAME = "config.candidate.mock.json"
STATUS_FILENAME = "writer-status.json"
SUMMARY_FILENAME = "summary.txt"

MOCK_API_URL = "https://api.example.invalid/search"
MOCK_API_KEY = "API_KEY_MOCK_NOT_FOR_PRODUCTION"
DEFAULT_ENVIRONMENT_ID = "ENVIRONMENT_ID_MOCK"
DEFAULT_STATION_ID = "STATION_ID_MOCK"

ENVIRONMENT_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
SAFE_DISPLAY_RE = re.compile(r"\b(?:MOCK|EXAMPLE|TEST|PLACEHOLDER)\b", re.IGNORECASE)

PROHIBITED_ENVIRONMENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("URL", re.compile(r"https?://", re.IGNORECASE)),
    ("api_key", re.compile(r"api[_-]?key", re.IGNORECASE)),
    ("token", re.compile(r"token", re.IGNORECASE)),
    ("secret", re.compile(r"secret", re.IGNORECASE)),
    ("password", re.compile(r"password", re.IGNORECASE)),
    ("senha", re.compile(r"senha", re.IGNORECASE)),
    ("private path", re.compile(r"/(?:data|opt|home)/", re.IGNORECASE)),
    ("slash", re.compile(r"/")),
)

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


class ValidationError(ValueError):
    """Raised for expected C5 validation failures."""


def utc_timestamp() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat().replace("+00:00", "Z")


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
    atomic_write_private_text(
        path,
        json.dumps(value, indent=2, sort_keys=True),
        out_dir,
    )


def validate_environment_id(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        raise ValidationError("environment_id must not be empty")
    if len(value) < 3:
        raise ValidationError("environment_id must have at least 3 characters")
    if len(value) > 128:
        raise ValidationError("environment_id must have at most 128 characters")
    if re.search(r"\s", value):
        raise ValidationError("environment_id must not contain whitespace")

    for label, pattern in PROHIBITED_ENVIRONMENT_PATTERNS:
        if pattern.search(value):
            raise ValidationError(f"environment_id must not contain {label}")

    if not ENVIRONMENT_ID_RE.fullmatch(value):
        raise ValidationError("environment_id contains characters outside the allowlist")
    return value


def validate_station_id(raw_value: str | None) -> str:
    if raw_value is None:
        return DEFAULT_STATION_ID
    value = validate_environment_id(raw_value)
    return value


def display_value(value: str) -> str:
    if value in {DEFAULT_ENVIRONMENT_ID, DEFAULT_STATION_ID}:
        return value
    if SAFE_DISPLAY_RE.search(value):
        return value
    return "<redacted>"


def build_mock_config(environment_id: str, station_id: str) -> dict[str, Any]:
    return {
        "api_url": MOCK_API_URL,
        "api_key": MOCK_API_KEY,
        "environment_id": environment_id,
        "station_id": station_id,
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


def validate_candidate_schema(config: dict[str, Any]) -> None:
    missing = sorted(set(REQUIRED_CONFIG_FIELDS) - set(config))
    if missing:
        raise ValidationError("mock config is missing required fields")

    for key, expected_type in REQUIRED_CONFIG_FIELDS.items():
        if not isinstance(config[key], expected_type):
            raise ValidationError("mock config has invalid field types")

    if config["api_url"] != MOCK_API_URL:
        raise ValidationError("mock config api_url is not the approved placeholder")
    if config["api_key"] != MOCK_API_KEY:
        raise ValidationError("mock config api_key is not the approved placeholder")
    validate_environment_id(config["environment_id"])
    validate_environment_id(config["station_id"])


def build_status(
    *,
    generated_at: str,
    out_dir: pathlib.Path,
    environment_id: str,
    station_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "mode": "mock",
        "out_dir": str(out_dir),
        "files": {
            "config_candidate": CONFIG_FILENAME,
            "writer_status": STATUS_FILENAME,
            "summary": SUMMARY_FILENAME,
        },
        "validation": {
            "environment_id": "format_validated_only",
            "backend_validation": "not_checked",
            "schema_minimum": "validated",
        },
        "inputs": {
            "environment_id": display_value(environment_id),
            "station_id": display_value(station_id),
            "api_key": MOCK_API_KEY,
            "api_url": MOCK_API_URL,
        },
        "guardrails": {
            "writes_only_under_tmp": True,
            "real_config_read": False,
            "real_config_written": False,
            "data_written": False,
            "network_access": False,
            "systemctl_called": False,
            "nmcli_called": False,
            "mpv_called": False,
        },
        "privacy": {
            "real_secrets_allowed": False,
            "real_api_key_allowed": False,
            "real_environment_id_allowed_in_evidence": False,
            "raw_backend_payload_allowed": False,
        },
    }


def build_summary(
    *,
    generated_at: str,
    out_dir: pathlib.Path,
    environment_id: str,
    station_id: str,
) -> str:
    return "\n".join(
        [
            "Dadooh C5 config writer mock",
            "",
            f"Generated at UTC: {generated_at}",
            f"Output directory: {out_dir}",
            "Mode: mock only",
            "",
            "Inputs:",
            f"- environment_id: {display_value(environment_id)}",
            f"- station_id: {display_value(station_id)}",
            f"- api_url: {MOCK_API_URL}",
            f"- api_key: {MOCK_API_KEY}",
            "",
            "Generated files:",
            f"- {CONFIG_FILENAME}",
            f"- {STATUS_FILENAME}",
            f"- {SUMMARY_FILENAME}",
            "",
            "Guardrails:",
            "- wrote only under /tmp",
            "- did not write /data/config/config.json",
            "- did not create, read, or write /data paths",
            "- did not read real config",
            "- did not call network, nmcli, systemctl, or MPV",
            "- launcher, renderer, systemd, and kiosky-player were not altered",
            "",
            "Note: /data paths inside config.candidate.mock.json are strings for future C6 shape only.",
        ]
    )


def write_mock_artifacts(out_dir: pathlib.Path, environment_id: str, station_id: str) -> list[pathlib.Path]:
    prepare_out_dir(out_dir)
    generated_at = utc_timestamp()
    config = build_mock_config(environment_id, station_id)
    validate_candidate_schema(config)

    status = build_status(
        generated_at=generated_at,
        out_dir=out_dir,
        environment_id=environment_id,
        station_id=station_id,
    )
    summary = build_summary(
        generated_at=generated_at,
        out_dir=out_dir,
        environment_id=environment_id,
        station_id=station_id,
    )

    paths = [
        out_dir / CONFIG_FILENAME,
        out_dir / STATUS_FILENAME,
        out_dir / SUMMARY_FILENAME,
    ]
    atomic_write_private_json(paths[0], config, out_dir)
    atomic_write_private_json(paths[1], status, out_dir)
    atomic_write_private_text(paths[2], summary, out_dir)
    return paths


def assert_raises(fn: Any) -> None:
    try:
        fn()
    except ValidationError:
        return
    raise AssertionError("expected validation failure")


def file_mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def run_self_test() -> None:
    assert validate_environment_id(f" {DEFAULT_ENVIRONMENT_ID} ") == DEFAULT_ENVIRONMENT_ID
    assert_raises(lambda: validate_environment_id(" "))
    assert_raises(lambda: validate_environment_id("ab"))
    assert_raises(lambda: validate_environment_id("A" * 129))
    assert_raises(lambda: validate_environment_id("ENVIRONMENT ID MOCK"))
    assert_raises(lambda: validate_environment_id("https://api.example.invalid/search"))
    assert_raises(lambda: validate_environment_id("/data/config/config.json"))
    assert_raises(lambda: validate_environment_id("token-MOCK"))
    assert_raises(lambda: validate_environment_id("secret-MOCK"))
    assert_raises(lambda: validate_environment_id("api_key-MOCK"))
    assert_raises(lambda: validate_environment_id("senha-MOCK"))
    assert_raises(lambda: require_tmp_dir("/var/tmp/dadooh-c5-config-writer-mock"))

    test_dir = pathlib.Path(f"/tmp/dadooh-c5-config-writer-mock-self-test-{os.getpid()}")
    if test_dir.exists():
        shutil.rmtree(test_dir)

    try:
        out_dir = require_tmp_dir(str(test_dir))
        generated = write_mock_artifacts(
            out_dir,
            DEFAULT_ENVIRONMENT_ID,
            DEFAULT_STATION_ID,
        )
        expected_names = {CONFIG_FILENAME, STATUS_FILENAME, SUMMARY_FILENAME}
        actual_names = {path.name for path in generated}
        if actual_names != expected_names:
            raise AssertionError("mock writer generated unexpected files")
        if file_mode(out_dir) != 0o700:
            raise AssertionError("out-dir permission is not 700")
        for path in generated:
            if file_mode(path) != 0o600:
                raise AssertionError("generated file permission is not 600")
            path.resolve(strict=True).relative_to(out_dir.resolve(strict=True))
            if str(path.resolve(strict=True)).startswith("/data/"):
                raise AssertionError("generated artifact escaped to /data")

        with (out_dir / CONFIG_FILENAME).open("r", encoding="utf-8") as handle:
            config = json.load(handle)
        validate_candidate_schema(config)
    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a local C5 mock config candidate under /tmp only.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}",
    )
    parser.add_argument(
        "--environment-id",
        help="Mock environment_id to validate and place in the candidate config.",
    )
    parser.add_argument(
        "--station-id",
        help="Optional mock station_id. Default: STATION_ID_MOCK",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run local validation tests and exit.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0

        if args.environment_id is None:
            raise ValidationError("--environment-id is required unless --self-test is used")

        out_dir = require_tmp_dir(args.out_dir)
        environment_id = validate_environment_id(args.environment_id)
        station_id = validate_station_id(args.station_id)
        generated = write_mock_artifacts(out_dir, environment_id, station_id)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except AssertionError:
        print("error: self-test failed", file=sys.stderr)
        return 1
    except OSError:
        print("error: failed to write mock artifacts", file=sys.stderr)
        return 1

    print(f"C5 mock config artifacts generated under {out_dir}")
    for path in generated:
        print(path.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
