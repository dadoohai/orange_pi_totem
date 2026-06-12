#!/usr/bin/env python3
"""Generate a sanitized C7 appliance status snapshot.

C7.0 is deliberately local/offline and read-only. It reads only local status
JSON files when present, observes config metadata with stat only, writes
restricted artifacts under /tmp, and never calls network, systemd, journal,
NetworkManager, MPV, /opt or /data writers.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import os
import pathlib
import pwd
import grp
import re
import shutil
import stat
import sys
import tempfile
from typing import Any


SCHEMA_VERSION = "dadooh-c7-appliance-status.v0"
C18_GOVERNANCE_SCHEMA = "dadooh.c18.appliance_public_state.governance.v1"
C18_RESULT_CLAIM = "read_only_appliance_public_state_collected"
DEFAULT_OUT_DIR = "/tmp/dadooh-c7-appliance-status"
DEFAULT_ROOT = "/"
SELFTEST_ROOT = pathlib.Path("/tmp/dadooh-c7-selftest-root")

STATUS_FILENAME = "appliance-status.json"
SUMMARY_FILENAME = "summary.txt"

TMP_ROOT = pathlib.Path("/tmp").resolve()
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
MAX_STATUS_FILE_BYTES = 64 * 1024
MAX_SAFE_STRING_LEN = 80

PUBLIC_STATUS_REL = pathlib.Path("tmp/dadooh-status/status.json")
PLAYER_STATUS_REL = pathlib.Path("tmp/kiosky-status.json")
CONFIG_FILE_REL = pathlib.Path("data/config/config.json")

PUBLIC_STATES = {
    "booting",
    "display_missing",
    "config_missing",
    "starting_player",
    "player_running",
    "player_error",
    "maintenance_placeholder",
}
CONFIG_STATES = {"unknown", "missing", "invalid", "valid"}
PLAYER_STATES = {"unknown", "not_started", "starting", "running", "error", "stopped"}
SERVICE_STATES = {"unknown", "inactive", "activating", "active", "failed"}
PLAYBACK_STATES = {
    "unknown",
    "idle",
    "playing",
    "buffering",
    "paused",
    "stopped",
    "error",
    "failed",
}
ERROR_CODE_RE = re.compile(r"^[A-Z0-9_:-]{1,64}$")
TIMESTAMP_RE = re.compile(r"^[0-9T:+_.Z -]{1,64}$")

SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"\btoken\b", re.IGNORECASE),
    re.compile(r"\bsecret\b", re.IGNORECASE),
    re.compile(r"\bpassword\b", re.IGNORECASE),
    re.compile(r"\bpasswd\b", re.IGNORECASE),
    re.compile(r"\bsenha\b", re.IGNORECASE),
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\bbearer\b", re.IGNORECASE),
    re.compile(r"/data/media(?:/|\b)", re.IGNORECASE),
    re.compile(r"/data/config(?:/|\b)", re.IGNORECASE),
    re.compile(r"/opt/totem(?:/|\b)", re.IGNORECASE),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b", re.IGNORECASE),
    re.compile(r"\bssid\b", re.IGNORECASE),
    re.compile(r"\bbssid\b", re.IGNORECASE),
    re.compile(r"\bgateway\b", re.IGNORECASE),
    re.compile(r"\bdns\b", re.IGNORECASE),
    re.compile(r"\bhost(?:name)?\b", re.IGNORECASE),
    re.compile(r"\bmac\b", re.IGNORECASE),
)


class SnapshotError(ValueError):
    """Raised for expected C7 snapshot failures."""


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
        raise SnapshotError("out-dir must be under /tmp")
    if resolved == TMP_ROOT:
        raise SnapshotError("out-dir must be a dedicated directory under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise SnapshotError("out-dir exists and is not a directory")
    return resolved


def prepare_out_dir(path: pathlib.Path) -> None:
    path.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    if stat.S_IMODE(path.stat().st_mode) != PRIVATE_DIR_MODE:
        path.chmod(PRIVATE_DIR_MODE)


def ensure_output_target(path: pathlib.Path, out_dir: pathlib.Path) -> None:
    resolved_out = out_dir.resolve(strict=True)
    resolved_target = path.resolve(strict=False)
    if not path_is_under(resolved_target, resolved_out):
        raise SnapshotError("output target escaped out-dir")
    if resolved_target == resolved_out:
        raise SnapshotError("output target must be a file")


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


def contains_private_pattern(value: str) -> bool:
    return any(pattern.search(value) for pattern in SENSITIVE_PATTERNS)


def assert_output_safe(text: str) -> None:
    if contains_private_pattern(text):
        raise SnapshotError("privacy scan blocked unsafe output")


def safe_json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def read_status_json(path: pathlib.Path) -> tuple[str, dict[str, Any] | None]:
    try:
        st = path.lstat()
    except FileNotFoundError:
        return "unavailable", None
    except OSError:
        return "invalid", None

    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return "invalid", None
    if st.st_size > MAX_STATUS_FILE_BYTES:
        return "invalid", None

    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return "invalid", None

    if not isinstance(value, dict):
        return "invalid", None
    return "present", value


def root_join(root: pathlib.Path, rel: pathlib.Path) -> pathlib.Path:
    return root / rel


def warning_add(warnings: set[str], code: str) -> None:
    warnings.add(code)


def sanitize_string(
    value: Any,
    *,
    default: str = "unknown",
    allowed: set[str] | None = None,
    warnings: set[str],
    privacy_failed: list[bool],
    code: str = "FIELD_REDACTED",
) -> str:
    if not isinstance(value, str):
        return default

    text = value.strip()
    if not text:
        return default
    if len(text) > MAX_SAFE_STRING_LEN or contains_private_pattern(text):
        privacy_failed[0] = True
        warning_add(warnings, code)
        return default

    normalized = text.lower()
    if allowed is not None:
        if normalized not in allowed:
            warning_add(warnings, "FIELD_OUTSIDE_ALLOWLIST")
            return default
        return normalized
    return text


def sanitize_error_code(
    value: Any,
    *,
    warnings: set[str],
    privacy_failed: list[bool],
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > MAX_SAFE_STRING_LEN or contains_private_pattern(text):
        privacy_failed[0] = True
        warning_add(warnings, "FIELD_REDACTED")
        return None
    if not ERROR_CODE_RE.fullmatch(text):
        warning_add(warnings, "FIELD_OUTSIDE_ALLOWLIST")
        return None
    return text


def sanitize_timestamp(
    value: Any,
    *,
    warnings: set[str],
    privacy_failed: list[bool],
) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > MAX_SAFE_STRING_LEN or contains_private_pattern(text):
        privacy_failed[0] = True
        warning_add(warnings, "FIELD_REDACTED")
        return None
    if not TIMESTAMP_RE.fullmatch(text):
        warning_add(warnings, "FIELD_OUTSIDE_ALLOWLIST")
        return None
    return text


def sanitize_bool(value: Any) -> bool | str:
    if isinstance(value, bool):
        return value
    return "unknown"


def safe_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def owner_group_category(st: os.stat_result) -> str:
    try:
        owner = pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        owner = "unknown"
    try:
        group = grp.getgrgid(st.st_gid).gr_name
    except KeyError:
        group = "unknown"

    known = {
        ("root", "root"): "root_root",
        ("root", "totem"): "root_totem",
        ("totem", "totem"): "totem_totem",
    }
    return known.get((owner, group), "other")


def config_metadata(path: pathlib.Path, warnings: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "config_file_exists": False,
        "config_file_mode": None,
        "config_file_owner_group_category": "unknown",
        "config_file_content_read": False,
        "source_status": "unavailable",
    }
    try:
        st = path.lstat()
    except FileNotFoundError:
        return result
    except OSError:
        result["source_status"] = "invalid"
        return result

    result["config_file_exists"] = True
    if stat.S_ISLNK(st.st_mode):
        result["source_status"] = "invalid"
        warning_add(warnings, "CONFIG_METADATA_NOT_REGULAR_FILE")
        return result
    if not stat.S_ISREG(st.st_mode):
        result["source_status"] = "invalid"
        warning_add(warnings, "CONFIG_METADATA_NOT_REGULAR_FILE")
        return result

    result["source_status"] = "present"
    result["config_file_mode"] = f"{stat.S_IMODE(st.st_mode):03o}"
    result["config_file_owner_group_category"] = owner_group_category(st)
    return result


def build_snapshot(root: pathlib.Path) -> dict[str, Any]:
    warnings: set[str] = set()
    privacy_failed = [False]

    public_status_state, public_status = read_status_json(root_join(root, PUBLIC_STATUS_REL))
    player_status_state, player_status = read_status_json(root_join(root, PLAYER_STATUS_REL))
    config_meta = config_metadata(root_join(root, CONFIG_FILE_REL), warnings)

    public_state = "unknown"
    public_config_state = "unknown"
    public_player_state = "unknown"
    public_service_state = "unknown"
    public_display_connected: bool | str = "unknown"
    public_error_code: str | None = None
    public_updated_at: str | None = None

    if public_status is not None:
        public_state = sanitize_string(
            public_status.get("state", public_status.get("public_state")),
            allowed=PUBLIC_STATES,
            warnings=warnings,
            privacy_failed=privacy_failed,
        )
        public_config_state = sanitize_string(
            public_status.get("config_state"),
            allowed=CONFIG_STATES,
            warnings=warnings,
            privacy_failed=privacy_failed,
        )
        public_player_state = sanitize_string(
            public_status.get("player_state"),
            allowed=PLAYER_STATES,
            warnings=warnings,
            privacy_failed=privacy_failed,
        )
        public_service_state = sanitize_string(
            public_status.get("service_state"),
            allowed=SERVICE_STATES,
            warnings=warnings,
            privacy_failed=privacy_failed,
        )
        public_display_connected = sanitize_bool(public_status.get("display_connected"))
        public_error_code = sanitize_error_code(
            public_status.get("error_code"),
            warnings=warnings,
            privacy_failed=privacy_failed,
        )
        public_updated_at = sanitize_timestamp(
            public_status.get("updated_at"),
            warnings=warnings,
            privacy_failed=privacy_failed,
        )

    playback_state = "unknown"
    mpv_running: bool | str = "unknown"
    playlist_size_value: int | None = None
    current_index_value: int | None = None
    last_poll_success_value: bool | str = "unknown"
    consecutive_failures_value: int | None = None

    playlist_size_present = False
    current_index_present = False
    last_poll_success_present = False
    consecutive_failures_present = False

    if player_status is not None:
        playback_state = sanitize_string(
            player_status.get("playback_state"),
            allowed=PLAYBACK_STATES,
            warnings=warnings,
            privacy_failed=privacy_failed,
        )
        mpv_running = sanitize_bool(player_status.get("mpv_running"))
        playlist_size_value = safe_nonnegative_int(player_status.get("playlist_size"))
        playlist_size_present = playlist_size_value is not None
        current_index_value = safe_nonnegative_int(player_status.get("current_index"))
        current_index_present = current_index_value is not None
        last_poll_success_present = "last_poll_success" in player_status
        last_poll_success_value = sanitize_bool(player_status.get("last_poll_success"))
        consecutive_failures_value = safe_nonnegative_int(player_status.get("consecutive_failures"))
        consecutive_failures_present = consecutive_failures_value is not None

        for key in ("playlist_size", "current_index", "consecutive_failures"):
            if key in player_status and safe_nonnegative_int(player_status.get(key)) is None:
                warning_add(warnings, "NUMERIC_FIELD_IGNORED")

    if public_status_state == "invalid":
        warning_add(warnings, "PUBLIC_STATUS_INVALID")
    if player_status_state == "invalid":
        warning_add(warnings, "PLAYER_STATUS_INVALID")

    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "c18_governance": {
            "schema": C18_GOVERNANCE_SCHEMA,
            "responsibility": "field-data",
            "result_claim": C18_RESULT_CLAIM,
            "collection_mode": "local_offline_read_only",
            "reads_config_content": False,
            "copies_raw_player_status": False,
            "copies_raw_public_status": False,
            "reads_media": False,
            "reads_network": False,
            "reads_journal": False,
            "executes_commands": False,
            "writes_only_under_tmp": True,
            "not_ota_release_payload": True,
            "not_player_runtime_release": True,
            "not_system_image_release": True,
            "not_h2_or_production_readiness": True,
        },
        "generated_at": utc_timestamp(),
        "source_presence": {
            "public_status": public_status_state,
            "player_status": player_status_state,
            "config_file": config_meta.pop("source_status"),
            "processes": "not_observed",
            "service": "not_observed",
        },
        "public_state": public_state,
        "public_config_state": public_config_state,
        "public_player_state": public_player_state,
        "public_service_state": public_service_state,
        "public_display_connected": public_display_connected,
        "public_error_code": public_error_code,
        "public_updated_at": public_updated_at,
        "launcher_state": public_state,
        "launcher_display_connected": public_display_connected,
        "playback_state": playback_state,
        "mpv_running": mpv_running,
        "playlist_size_present": playlist_size_present,
        "playlist_size_value": playlist_size_value,
        "current_index_present": current_index_present,
        "current_index_value": current_index_value,
        "last_poll_success_present": last_poll_success_present,
        "last_poll_success_value": last_poll_success_value,
        "consecutive_failures_present": consecutive_failures_present,
        "consecutive_failures_value": consecutive_failures_value,
        **config_meta,
        "service_observed": "unknown",
        "renderer_active": "unknown",
        "kiosk_active": "unknown",
        "mpv_process_count": "unknown",
        "privacy_scan": "failed" if privacy_failed[0] else "ok",
        "warnings": sorted(warnings),
    }

    return snapshot


def build_summary(snapshot: dict[str, Any]) -> str:
    def summary_value(value: Any) -> str:
        if isinstance(value, bool):
            return str(value).lower()
        return str(value)

    lines = [
        "Dadooh C7 appliance status snapshot",
        "",
        f"schema_version: {snapshot['schema_version']}",
        f"c18_governance_schema: {snapshot['c18_governance']['schema']}",
        f"c18_result_claim: {snapshot['c18_governance']['result_claim']}",
        f"c18_responsibility: {snapshot['c18_governance']['responsibility']}",
        f"generated_at: {snapshot['generated_at']}",
        f"privacy_scan: {snapshot['privacy_scan']}",
        f"public_status_source: {snapshot['source_presence']['public_status']}",
        f"player_status_source: {snapshot['source_presence']['player_status']}",
        f"config_file_source: {snapshot['source_presence']['config_file']}",
        f"public_state: {snapshot['public_state']}",
        f"public_config_state: {snapshot['public_config_state']}",
        f"public_player_state: {snapshot['public_player_state']}",
        f"public_service_state: {snapshot['public_service_state']}",
        f"playback_state: {snapshot['playback_state']}",
        f"mpv_running: {summary_value(snapshot['mpv_running'])}",
        f"playlist_size_present: {str(snapshot['playlist_size_present']).lower()}",
        f"current_index_present: {str(snapshot['current_index_present']).lower()}",
        f"last_poll_success_present: {str(snapshot['last_poll_success_present']).lower()}",
        f"config_file_exists: {str(snapshot['config_file_exists']).lower()}",
        f"config_file_mode: {snapshot['config_file_mode']}",
        f"config_file_owner_group_category: {snapshot['config_file_owner_group_category']}",
        f"config_file_content_read: {str(snapshot['config_file_content_read']).lower()}",
        f"service_observed: {snapshot['service_observed']}",
        f"renderer_active: {snapshot['renderer_active']}",
        f"kiosk_active: {snapshot['kiosk_active']}",
        f"mpv_process_count: {snapshot['mpv_process_count']}",
        "network_access: false",
        "commands_executed: false",
        "writes_only_under_tmp: true",
        "not_ota_release_payload: true",
        "not_h2_or_production_readiness: true",
    ]
    if snapshot["warnings"]:
        lines.append("warnings: " + ",".join(snapshot["warnings"]))
    else:
        lines.append("warnings: none")
    return "\n".join(lines)


def write_artifacts(snapshot: dict[str, Any], out_dir: pathlib.Path) -> None:
    prepare_out_dir(out_dir)
    status_json = safe_json_dumps(snapshot)
    summary = build_summary(snapshot)
    assert_output_safe(status_json)
    assert_output_safe(summary)
    atomic_write_private_text(out_dir / STATUS_FILENAME, status_json, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, summary, out_dir)


def run_snapshot(*, root_raw: str, out_dir_raw: str) -> dict[str, Any]:
    out_dir = require_tmp_dir(out_dir_raw)
    root = pathlib.Path(root_raw).expanduser().resolve(strict=False)
    snapshot = build_snapshot(root)
    write_artifacts(snapshot, out_dir)
    return snapshot


def write_json_fixture(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def write_text_fixture(path: pathlib.Path, value: str, mode: int = 0o600) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    path.chmod(mode)


def read_output_text(out_dir: pathlib.Path) -> str:
    return (out_dir / STATUS_FILENAME).read_text(encoding="utf-8") + "\n" + (
        out_dir / SUMMARY_FILENAME
    ).read_text(encoding="utf-8")


def load_output_json(out_dir: pathlib.Path) -> dict[str, Any]:
    with (out_dir / STATUS_FILENAME).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise AssertionError("snapshot output is not an object")
    return value


def make_case_root(base: pathlib.Path, name: str) -> tuple[pathlib.Path, pathlib.Path]:
    root = base / name / "root"
    out = base / name / "out"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root, out


def assert_no_private_output(out_dir: pathlib.Path) -> None:
    assert_output_safe(read_output_text(out_dir))


def create_persistent_selftest_root() -> None:
    if SELFTEST_ROOT.exists():
        resolved = SELFTEST_ROOT.resolve(strict=False)
        if not path_is_under(resolved, TMP_ROOT):
            raise AssertionError("persistent self-test root escaped /tmp")
        shutil.rmtree(SELFTEST_ROOT)

    write_json_fixture(
        SELFTEST_ROOT / PUBLIC_STATUS_REL,
        {
            "schema_version": "totem-status.v0",
            "updated_at": "2026-05-02T00:00:00Z",
            "state": "player_running",
            "display_connected": True,
            "config_state": "valid",
            "player_state": "running",
            "service_state": "active",
            "error_code": None,
        },
    )
    write_json_fixture(
        SELFTEST_ROOT / PLAYER_STATUS_REL,
        {
            "playback_state": "playing",
            "mpv_running": True,
            "playlist_size": 3,
            "current_index": 1,
            "last_poll_success": True,
            "consecutive_failures": 0,
        },
    )
    write_text_fixture(
        SELFTEST_ROOT / CONFIG_FILE_REL,
        '{"fixture":"metadata only"}\n',
        mode=0o640,
    )


def run_self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="dadooh-c7-selftest-", dir="/tmp") as tmp:
        base = pathlib.Path(tmp)

        root, out = make_case_root(base, "public-clean")
        write_json_fixture(
            root / PUBLIC_STATUS_REL,
            {
                "schema_version": "totem-status.v0",
                "updated_at": "2026-05-02T00:00:00Z",
                "state": "config_missing",
                "display_connected": True,
                "config_state": "missing",
                "player_state": "not_started",
                "service_state": "active",
                "error_code": "CONFIG_MISSING",
            },
        )
        run_snapshot(root_raw=str(root), out_dir_raw=str(out))
        data = load_output_json(out)
        assert data["public_state"] == "config_missing"
        assert data["c18_governance"]["schema"] == C18_GOVERNANCE_SCHEMA
        assert data["c18_governance"]["responsibility"] == "field-data"
        assert data["c18_governance"]["result_claim"] == C18_RESULT_CLAIM
        assert data["c18_governance"]["reads_config_content"] is False
        assert data["c18_governance"]["not_ota_release_payload"] is True
        assert data["c18_governance"]["not_h2_or_production_readiness"] is True
        assert data["privacy_scan"] == "ok"
        assert_no_private_output(out)

        root, out = make_case_root(base, "player-clean")
        write_json_fixture(
            root / PLAYER_STATUS_REL,
            {
                "playback_state": "playing",
                "mpv_running": True,
                "playlist_size": 5,
                "current_index": 2,
                "last_poll_success": True,
                "consecutive_failures": 0,
            },
        )
        run_snapshot(root_raw=str(root), out_dir_raw=str(out))
        data = load_output_json(out)
        assert data["playback_state"] == "playing"
        assert data["playlist_size_present"] is True
        assert data["current_index_present"] is True
        assert data["privacy_scan"] == "ok"
        assert_no_private_output(out)

        root, out = make_case_root(base, "unknown-private-fields")
        write_json_fixture(
            root / PLAYER_STATUS_REL,
            {
                "playback_state": "playing",
                "mpv_running": True,
                "playlist_size": 1,
                "current_index": 0,
                "last_poll_success": False,
                "private_payload": {
                    "credential_name": "ignored",
                    "url_value": "https://private.invalid/api",
                    "path_value": "/data/media/customer/file.mp4",
                },
                "api_key": "IGNORED_VALUE",
            },
        )
        run_snapshot(root_raw=str(root), out_dir_raw=str(out))
        data = load_output_json(out)
        assert data["privacy_scan"] == "ok"
        output = read_output_text(out)
        assert "IGNORED_VALUE" not in output
        assert "private.invalid" not in output
        assert_no_private_output(out)

        root, out = make_case_root(base, "allowlisted-private-value")
        write_json_fixture(
            root / PUBLIC_STATUS_REL,
            {
                "state": "https://private.invalid/status",
                "display_connected": True,
                "config_state": "valid",
                "player_state": "running",
                "service_state": "active",
                "error_code": "PLAYER_EXITED",
            },
        )
        write_json_fixture(
            root / PLAYER_STATUS_REL,
            {
                "playback_state": "Bearer private-value",
                "mpv_running": True,
            },
        )
        run_snapshot(root_raw=str(root), out_dir_raw=str(out))
        data = load_output_json(out)
        assert data["privacy_scan"] == "failed"
        assert data["public_state"] == "unknown"
        assert data["playback_state"] == "unknown"
        assert_no_private_output(out)

        root, out = make_case_root(base, "config-metadata")
        write_text_fixture(
            root / CONFIG_FILE_REL,
            "SHOULD_NOT_BE_READ https://private.invalid /data/config\n",
            mode=0o640,
        )
        run_snapshot(root_raw=str(root), out_dir_raw=str(out))
        data = load_output_json(out)
        assert data["config_file_exists"] is True
        assert data["config_file_content_read"] is False
        output = read_output_text(out)
        assert "SHOULD_NOT_BE_READ" not in output
        assert_no_private_output(out)

        root, _out = make_case_root(base, "out-dir-blocked")
        try:
            run_snapshot(root_raw=str(root), out_dir_raw="/home/dadooh-c7-outside")
        except SnapshotError:
            pass
        else:
            raise AssertionError("out-dir outside /tmp was accepted")

        root, out = make_case_root(base, "no-sources")
        run_snapshot(root_raw=str(root), out_dir_raw=str(out))
        data = load_output_json(out)
        assert data["source_presence"]["public_status"] == "unavailable"
        assert data["source_presence"]["player_status"] == "unavailable"
        assert data["source_presence"]["config_file"] == "unavailable"
        assert data["public_state"] == "unknown"
        assert data["privacy_scan"] == "ok"
        assert_no_private_output(out)

    create_persistent_selftest_root()
    print(f"self-test ok; sanitized fixture root: {SELFTEST_ROOT}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a sanitized C7 appliance status snapshot.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Output directory under /tmp.")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="Root directory for fixture-relative reads.")
    parser.add_argument("--self-test", action="store_true", help="Run local self-tests using /tmp fixtures.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        return run_self_test()

    try:
        snapshot = run_snapshot(root_raw=args.root, out_dir_raw=args.out_dir)
    except SnapshotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(pathlib.Path(args.out_dir).expanduser().resolve(strict=False) / STATUS_FILENAME)
    print(pathlib.Path(args.out_dir).expanduser().resolve(strict=False) / SUMMARY_FILENAME)
    if snapshot["privacy_scan"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
