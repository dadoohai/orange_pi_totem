#!/usr/bin/env python3
"""Aggregate sanitized totem status and render a local SVG.

This A1.1 component is deliberately offline and non-invasive. It reads local
JSON status files when present, writes only under /tmp by default, and never
starts MPV, touches systemd, accesses /dev/dri or reaches the network.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile
import time
from typing import Any

from totem_status_render_preview import STATE_PRESETS, build_svg, sanitize_public_text, utc_timestamp


SCHEMA_VERSION = "totem-status.v1"
DEFAULT_PRIMARY_LAUNCHER_STATUS = pathlib.Path("/data/state/kiosky-player/launcher-status.json")
DEFAULT_FALLBACK_LAUNCHER_STATUS = pathlib.Path("/tmp/kiosky-launcher-status.json")
DEFAULT_PLAYER_STATUS = pathlib.Path("/tmp/kiosky-status.json")
DEFAULT_OUT_DIR = pathlib.Path("/tmp/dadooh-status")
DEFAULT_PUBLIC_ORIENTATION_PATH = pathlib.Path("/data/state/totem-display/orientation.json")
DEFAULT_PLAYER_STATUS_MAX_AGE_SEC = 20.0
MAX_STATUS_SOURCE_BYTES = 1024 * 1024
PLAYER_STATUS_SCHEMA = "kiosky-player-status.v2"

PUBLIC_PLAYBACK_STATES = {
    "unknown",
    "idle",
    "playing",
    "buffering",
    "player_starting",
    "waiting_for_content",
    "waiting_for_media",
    "waiting_sync_anchor",
    "preparing_first_frame",
    "starting",
    "recovering",
    "paused",
    "stopped",
    "error",
    "failed",
}
PUBLIC_STARTUP_PHASES = {
    "unknown",
    "player_starting",
    "waiting_for_api",
    "waiting_for_playlist",
    "waiting_for_media_cache",
    "waiting_for_media",
    "waiting_for_content",
    "preparing_first_frame",
    "error_no_content",
    "error_player_start",
    "playing",
}

PUBLIC_STATES = set(STATE_PRESETS)

SETUP_LAUNCHER_STATES = {
    "setup_local_requested",
    "setup_local_starting",
    "setup_local_running",
    "setup_local_cancelled",
    "setup_local_failed",
    "setup_candidate_ready",
}

STATE_MESSAGES = {
    "booting": {
        "error_code": None,
        "config_state": "unknown",
        "player_state": "not_started",
    },
    "display_missing": {
        "error_code": "DISPLAY_MISSING",
        "config_state": "unknown",
        "player_state": "not_started",
    },
    "config_missing": {
        "error_code": "CONFIG_MISSING",
        "config_state": "missing",
        "player_state": "not_started",
    },
    "starting_player": {
        "error_code": None,
        "config_state": "valid",
        "player_state": "starting",
    },
    "loading_content": {
        "error_code": None,
        "config_state": "valid",
        "player_state": "loading",
    },
    "content_unavailable": {
        "error_code": "CONTENT_UNAVAILABLE",
        "config_state": "valid",
        "player_state": "recovering",
    },
    "player_running": {
        "error_code": None,
        "config_state": "valid",
        "player_state": "running",
    },
    "player_error": {
        "error_code": "PLAYER_EXITED",
        "config_state": "valid",
        "player_state": "error",
    },
    "maintenance_placeholder": {
        "error_code": None,
        "config_state": "unknown",
        "player_state": "stopped",
    },
}


def load_json_source(path: pathlib.Path) -> tuple[dict[str, Any] | None, float | None]:
    try:
        if path.is_symlink():
            return None, None
        stat_result = path.stat()
        if not path.is_file() or stat_result.st_size <= 0 or stat_result.st_size > MAX_STATUS_SOURCE_BYTES:
            return None, None
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError:
        return None, None
    except (OSError, UnicodeError, ValueError, RecursionError, json.JSONDecodeError):
        return None, None

    if isinstance(value, dict):
        return value, stat_result.st_mtime
    return None, None


def load_json_if_present(path: pathlib.Path) -> dict[str, Any] | None:
    value, _mtime = load_json_source(path)
    return value


def source_is_fresh(mtime: float | None, *, now_epoch: float, max_age_sec: float) -> bool:
    if mtime is None or max_age_sec <= 0:
        return False
    age = now_epoch - mtime
    return -60.0 <= age <= max_age_sec


def read_public_rotation(path: pathlib.Path) -> int:
    data, _mtime = load_json_source(path)
    if not data:
        return 0
    raw = data.get("rotation_deg")
    if isinstance(raw, bool):
        return 0
    try:
        value = int(raw) % 360
    except (TypeError, ValueError):
        return 0
    return value if value in {0, 90, 180, 270} else 0


def bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def string_value(data: dict[str, Any] | None, key: str) -> str:
    if not data:
        return ""
    value = data.get(key)
    if isinstance(value, str):
        return value.strip().lower()
    return ""


def enum_value(data: dict[str, Any] | None, key: str, allowed: set[str]) -> str:
    value = string_value(data, key)
    return value if value in allowed else "unknown"


def player_status_schema_supported(player_status: dict[str, Any] | None) -> bool:
    return string_value(player_status, "status_schema_version") == PLAYER_STATUS_SCHEMA


def player_reports_running(player_status: dict[str, Any] | None) -> bool:
    if not player_status_schema_supported(player_status):
        return False

    playback_state = string_value(player_status, "playback_state")
    mpv_running = bool_or_none(player_status.get("mpv_running"))
    first_frame_ready = bool_or_none(player_status.get("first_frame_ready"))
    current_item = player_status.get("current_item")
    current_path = current_item.get("path") or current_item.get("source_path") if isinstance(current_item, dict) else None
    current_item_valid = False
    if isinstance(current_path, str) and current_path.startswith("/") and "\x00" not in current_path:
        try:
            media_path = pathlib.Path(current_path)
            current_item_valid = media_path.is_file() and not media_path.is_symlink()
        except OSError:
            current_item_valid = False
    return (
        playback_state == "playing"
        and mpv_running is True
        and first_frame_ready is True
        and current_item_valid
    )


def player_reports_loading_content(player_status: dict[str, Any] | None) -> bool:
    if not player_status_schema_supported(player_status):
        return False

    playback_state = string_value(player_status, "playback_state")
    player_state = string_value(player_status, "player_state")
    startup_phase = string_value(player_status, "startup_phase")
    feedback_state = string_value(player_status, "startup_feedback_state")
    content_state = string_value(player_status, "content_state")
    public_surface_state = string_value(player_status, "public_surface_state")

    if public_surface_state == "loading_content":
        return True

    loading_values = {
        "player_starting",
        "waiting_for_api",
        "waiting_for_playlist",
        "waiting_for_media_cache",
        "waiting_for_media",
        "waiting_for_content",
        "preparing_first_frame",
    }
    return any(
        value in loading_values
        for value in (playback_state, player_state, startup_phase, feedback_state, content_state)
    )


def player_reports_error(player_status: dict[str, Any] | None) -> bool:
    if not player_status_schema_supported(player_status):
        return False

    playback_state = string_value(player_status, "playback_state")
    player_state = string_value(player_status, "player_state")
    error_code = string_value(player_status, "error_code")
    public_surface_state = string_value(player_status, "public_surface_state")

    if public_surface_state == "player_error":
        return True
    if playback_state in {"error", "failed", "fatal"}:
        return True
    if player_state in {"error", "failed", "fatal"}:
        return True
    return error_code.startswith("player_") or error_code in {"unknown_error", "service_failed"}


def player_reports_content_unavailable(player_status: dict[str, Any] | None) -> bool:
    if not player_status_schema_supported(player_status) or bool_or_none(player_status.get("first_frame_ready")) is True:
        return False

    playback_state = string_value(player_status, "playback_state")
    player_state = string_value(player_status, "player_state")
    content_state = string_value(player_status, "content_state")
    playlist_update_state = string_value(player_status, "playlist_update_state")
    public_surface_state = string_value(player_status, "public_surface_state")
    try:
        consecutive_failures = int(player_status.get("consecutive_failures") or 0)
    except (TypeError, ValueError):
        consecutive_failures = 0

    if public_surface_state == "content_unavailable":
        return True
    if playback_state in {"error", "failed", "fatal", "recovering"}:
        return True
    if player_state in {"error", "failed", "fatal", "error_player_start"}:
        return True
    if content_state in {
        "all_media_temporarily_blocked",
        "api_error_retrying",
        "content_unavailable",
        "error_no_content",
        "invalid_playlist_timeline",
        "media_frame_not_ready",
        "media_load_failed",
        "media_path_mismatch",
        "offline_no_content",
    }:
        return True
    if playlist_update_state in {"offline_no_content", "failed", "error"}:
        return True
    return consecutive_failures >= 3


def infer_config_state(
    launcher_status: dict[str, Any] | None,
    player_status: dict[str, Any] | None,
    state: str,
) -> str:
    if state == "config_missing":
        return "missing"

    for data in (launcher_status, player_status):
        if data is None:
            continue
        raw_state = string_value(data, "config_state")
        if raw_state in {"missing", "invalid", "valid", "unknown"}:
            return raw_state
        if bool_or_none(data.get("config_missing")) is True:
            return "missing"
        if bool_or_none(data.get("config_valid")) is True:
            return "valid"

    return STATE_MESSAGES[state]["config_state"]


def infer_service_state(launcher_status: dict[str, Any] | None, state: str) -> str:
    if not launcher_status:
        return "unknown"

    raw_service_state = string_value(launcher_status, "service_state")
    if raw_service_state in {"unknown", "inactive", "activating", "active", "failed"}:
        return raw_service_state

    launcher_state = string_value(launcher_status, "state")
    if launcher_state in {"starting", "running", "display_missing", "app_exited", "config_missing"}:
        return "active"
    if launcher_state in SETUP_LAUNCHER_STATES:
        return "active"
    if launcher_state == "stopped":
        return "inactive"
    if state == "player_error":
        return "active"
    return "unknown"


def infer_display_connected(launcher_status: dict[str, Any] | None, state: str) -> bool | None:
    display_connected = bool_or_none(launcher_status.get("display_connected") if launcher_status else None)
    if display_connected is not None:
        return display_connected
    if state == "display_missing":
        return False
    return None


def infer_state(
    launcher_status: dict[str, Any] | None,
    player_status: dict[str, Any] | None,
    state_override: str | None,
    *,
    player_status_fresh: bool = True,
) -> str:
    if state_override:
        return state_override

    launcher_state = string_value(launcher_status, "state")
    launcher_display = bool_or_none(launcher_status.get("display_connected") if launcher_status else None)
    launcher_exit_code = launcher_status.get("last_app_exit_code") if launcher_status else None

    if launcher_state == "display_missing" or launcher_display is False:
        return "display_missing"
    if launcher_state == "starting":
        if launcher_display is True:
            return "starting_player"
        return "booting"
    if launcher_state == "stopped":
        if bool_or_none(launcher_status.get("maintenance_authorized") if launcher_status else None) is True:
            return "maintenance_placeholder"
        return "player_error"

    if launcher_state == "config_missing":
        return "config_missing"
    if launcher_state in SETUP_LAUNCHER_STATES:
        return "config_missing"
    if string_value(launcher_status, "config_state") == "missing":
        return "config_missing"
    if player_status_schema_supported(player_status) and string_value(player_status, "config_state") == "missing":
        return "config_missing"
    if bool_or_none(launcher_status.get("config_missing") if launcher_status else None) is True:
        return "config_missing"

    if launcher_state == "app_exited" or isinstance(launcher_exit_code, int):
        return "player_error"
    if launcher_state == "running" and not player_status_fresh:
        return "player_error"
    if not player_status_fresh:
        player_status = None
    if launcher_state == "running" and player_reports_error(player_status):
        return "player_error"

    if launcher_state == "running" and player_reports_content_unavailable(player_status):
        return "content_unavailable"

    if launcher_state == "running" and player_reports_running(player_status):
        return "player_running"

    if launcher_state == "running" and player_reports_loading_content(player_status):
        return "loading_content"

    if launcher_state == "running":
        return "starting_player"

    return "booting"


def build_status(
    *,
    launcher_status: dict[str, Any] | None,
    player_status: dict[str, Any] | None,
    state_override: str | None,
    player_status_fresh: bool = True,
    player_status_reason: str = "fresh",
) -> dict[str, Any]:
    state = infer_state(
        launcher_status,
        player_status,
        state_override,
        player_status_fresh=player_status_fresh,
    )
    public = STATE_MESSAGES[state]
    visual = STATE_PRESETS[state]
    effective_player_status = player_status if player_status_fresh else None
    config_state = infer_config_state(launcher_status, effective_player_status, state)
    playback_state = enum_value(effective_player_status, "playback_state", PUBLIC_PLAYBACK_STATES)
    startup_phase = enum_value(effective_player_status, "startup_phase", PUBLIC_STARTUP_PHASES)
    error_code = public["error_code"]
    if (
        state == "player_error"
        and string_value(launcher_status, "state") == "running"
        and not player_status_fresh
    ):
        error_code = "PLAYER_STATUS_STALE" if player_status_reason == "stale" else "PLAYER_STATUS_INVALID"

    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_timestamp(),
        "state": state,
        "display_connected": infer_display_connected(launcher_status, state),
        "network_state": "unknown",
        "config_state": config_state,
        "player_state": public["player_state"],
        "playback_state": playback_state,
        "player_startup_phase": startup_phase,
        "service_state": infer_service_state(launcher_status, state),
        "error_code": error_code,
        "public_message": sanitize_public_text(str(visual["message"])),
        "action_hint": sanitize_public_text(str(visual["hint"])),
        "device_label": "Totem",
        "version": {
            "image": "unknown",
            "launcher": "foundation-v0.1",
            "player": "unknown",
            "contract": SCHEMA_VERSION,
        },
    }


def resolve_launcher_status(path: pathlib.Path | None) -> dict[str, Any] | None:
    data, _mtime, _path = resolve_launcher_source(path)
    return data


def resolve_launcher_source(
    path: pathlib.Path | None,
) -> tuple[dict[str, Any] | None, float | None, pathlib.Path | None]:
    if path is not None:
        data, mtime = load_json_source(path)
        return data, mtime, path if data is not None else None

    primary, primary_mtime = load_json_source(DEFAULT_PRIMARY_LAUNCHER_STATUS)
    if primary is not None:
        return primary, primary_mtime, DEFAULT_PRIMARY_LAUNCHER_STATUS
    fallback, fallback_mtime = load_json_source(DEFAULT_FALLBACK_LAUNCHER_STATUS)
    return fallback, fallback_mtime, DEFAULT_FALLBACK_LAUNCHER_STATUS if fallback is not None else None


def require_tmp_dir(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    resolved = path.resolve()
    tmp_root = pathlib.Path("/tmp").resolve()
    try:
        resolved.relative_to(tmp_root)
    except ValueError as exc:
        raise ValueError("out-dir must be under /tmp") from exc
    if resolved == tmp_root:
        raise ValueError("out-dir must be a subdirectory under /tmp")
    return resolved


def write_text_atomic(path: pathlib.Path, content: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)


def render_status_svg(status: dict[str, Any], *, rotation_deg: int = 0) -> str:
    portrait = rotation_deg in {90, 270}
    return build_svg(
        state=status["state"],
        message=status["public_message"],
        action_hint=status["action_hint"],
        device_label=status.get("device_label") or "Totem",
        width=720 if portrait else 1280,
        height=1280 if portrait else 720,
    )


def run_self_test() -> None:
    launcher_running = {
        "state": "running",
        "display_connected": True,
        "last_app_exit_code": None,
    }
    playing = {
        "status_schema_version": "kiosky-player-status.v2",
        "playback_state": "playing",
        "player_state": "playing",
        "mpv_running": True,
        "first_frame_ready": True,
        "current_item": {"path": str(pathlib.Path(__file__).resolve())},
    }
    loading = {
        "status_schema_version": "kiosky-player-status.v2",
        "playback_state": "waiting_for_content",
        "player_state": "waiting_for_api",
        "startup_phase": "waiting_for_api",
        "content_state": "waiting_for_api",
        "mpv_running": True,
        "first_frame_ready": False,
        "current_item": None,
    }
    unavailable = dict(loading, content_state="api_error_retrying", consecutive_failures=3)

    assert build_status(
        launcher_status=launcher_running,
        player_status=playing,
        state_override=None,
    )["state"] == "player_running"
    assert build_status(
        launcher_status=launcher_running,
        player_status=dict(playing, status_schema_version="unknown-schema"),
        state_override=None,
    )["state"] == "starting_player"
    assert build_status(
        launcher_status=launcher_running,
        player_status=dict(playing, mpv_running="true"),
        state_override=None,
    )["state"] == "starting_player"
    assert build_status(
        launcher_status=launcher_running,
        player_status=dict(playing, current_item={"path": 7}),
        state_override=None,
    )["state"] == "starting_player"
    assert build_status(
        launcher_status=None,
        player_status=playing,
        state_override=None,
    )["state"] == "booting"
    assert build_status(
        launcher_status={"state": "display_missing", "display_connected": False},
        player_status=playing,
        state_override=None,
    )["state"] == "display_missing"
    assert build_status(
        launcher_status={"state": "starting", "display_connected": False},
        player_status=playing,
        state_override=None,
    )["state"] == "display_missing"
    assert build_status(
        launcher_status={"state": "app_exited", "display_connected": True, "last_app_exit_code": 2},
        player_status=playing,
        state_override=None,
    )["state"] == "player_error"
    assert build_status(
        launcher_status=launcher_running,
        player_status=dict(playing, first_frame_ready=False),
        state_override=None,
    )["state"] == "starting_player"
    assert build_status(
        launcher_status=launcher_running,
        player_status=dict(playing, current_item=None),
        state_override=None,
    )["state"] == "starting_player"
    unsafe_public = build_status(
        launcher_status=launcher_running,
        player_status=dict(
            playing,
            playback_state="https://example.invalid/?token=secret",
            startup_phase="api_key=secret",
        ),
        state_override=None,
    )
    assert unsafe_public["playback_state"] == "unknown"
    assert unsafe_public["player_startup_phase"] == "unknown"
    assert "secret" not in json.dumps(unsafe_public)
    assert build_status(
        launcher_status=launcher_running,
        player_status=loading,
        state_override=None,
    )["state"] == "loading_content"
    assert build_status(
        launcher_status=launcher_running,
        player_status=unavailable,
        state_override=None,
    )["state"] == "content_unavailable"
    assert build_status(
        launcher_status=launcher_running,
        player_status=dict(
            loading,
            public_surface_state="content_unavailable",
            content_state="content_unavailable",
            error_code=None,
        ),
        state_override=None,
    )["state"] == "content_unavailable"
    assert build_status(
        launcher_status=launcher_running,
        player_status=dict(
            loading,
            public_surface_state="player_error",
            content_state="player_recovering",
            error_code="player_recovering",
        ),
        state_override=None,
    )["state"] == "player_error"
    stale = build_status(
        launcher_status=launcher_running,
        player_status=playing,
        state_override=None,
        player_status_fresh=False,
        player_status_reason="stale",
    )
    assert stale["state"] == "player_error"
    assert stale["error_code"] == "PLAYER_STATUS_STALE"
    assert build_status(
        launcher_status={"state": "app_exited", "display_connected": True, "last_app_exit_code": 2},
        player_status=playing,
        state_override=None,
        player_status_fresh=False,
        player_status_reason="stale",
    )["error_code"] == "PLAYER_EXITED"

    config_svg = render_status_svg(
        build_status(launcher_status={"state": "config_missing"}, player_status=None, state_override=None)
    )
    assert "F10" in config_svg
    assert "Vamos configurar este totem" in config_svg
    for forbidden in ("CONFIG_MISSING", "PLAYER_EXITED", "STATUS DO TOTEM", "Sem dados privados"):
        assert forbidden not in config_svg
    portrait_config_svg = render_status_svg(
        build_status(launcher_status={"state": "config_missing"}, player_status=None, state_override=None),
        rotation_deg=90,
    )
    assert 'viewBox="0 0 720 1280"' in portrait_config_svg

    with tempfile.TemporaryDirectory(prefix="dadooh-status-source-") as raw_tmp:
        root = pathlib.Path(raw_tmp)
        source = root / "status.json"
        source.write_text('{"state":"running"}\n', encoding="utf-8")
        loaded, mtime = load_json_source(source)
        assert loaded == {"state": "running"}
        assert source_is_fresh(mtime, now_epoch=time.time(), max_age_sec=20)
        symlink = root / "status-link.json"
        symlink.symlink_to(source)
        assert load_json_source(symlink) == (None, None)
        source.write_text("{}" + (" " * (MAX_STATUS_SOURCE_BYTES + 1)), encoding="utf-8")
        assert load_json_source(source) == (None, None)
        source.write_bytes(b"\xff\xfe")
        assert load_json_source(source) == (None, None)
        orientation = root / "orientation.json"
        orientation.write_text('{"rotation_deg":90}\n', encoding="utf-8")
        assert read_public_rotation(orientation) == 90
        orientation.write_text('{"rotation_deg":45}\n', encoding="utf-8")
        assert read_public_rotation(orientation) == 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate sanitized Dadooh totem status.")
    parser.add_argument("--launcher-status", help="Launcher status JSON path. Defaults to /data then /tmp.")
    parser.add_argument("--player-status", default=str(DEFAULT_PLAYER_STATUS), help="Player status JSON path.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory under /tmp.")
    parser.add_argument(
        "--orientation-path",
        default=str(DEFAULT_PUBLIC_ORIENTATION_PATH),
        help="Public display orientation JSON path.",
    )
    parser.add_argument("--state-override", choices=sorted(PUBLIC_STATES), help="Force a public state for tests.")
    parser.add_argument(
        "--player-status-max-age-sec",
        type=float,
        default=DEFAULT_PLAYER_STATUS_MAX_AGE_SEC,
        help="Maximum accepted player status age before it is treated as stale.",
    )
    parser.add_argument("--self-test", action="store_true", help="Run reducer and source-safety tests.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if args.self_test:
        run_self_test()
        print("self-test: ok")
        return 0

    try:
        out_dir = require_tmp_dir(args.out_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    launcher_status_path = pathlib.Path(args.launcher_status).expanduser() if args.launcher_status else None
    player_status_path = pathlib.Path(args.player_status).expanduser()
    orientation_path = pathlib.Path(args.orientation_path).expanduser()

    launcher_status, launcher_mtime, _launcher_source = resolve_launcher_source(launcher_status_path)
    player_status, player_mtime = load_json_source(player_status_path)
    now_epoch = time.time()
    max_player_age = max(1.0, float(args.player_status_max_age_sec))
    player_status_fresh = source_is_fresh(
        player_mtime,
        now_epoch=now_epoch,
        max_age_sec=max_player_age,
    )
    player_status_reason = "fresh"
    if player_status is None:
        player_status_reason = "invalid"
        player_status_fresh = False
    elif not player_status_fresh:
        player_status_reason = "stale"
    elif launcher_mtime is not None and player_mtime is not None and player_mtime + 0.001 < launcher_mtime:
        player_status_reason = "previous_generation"
        player_status_fresh = False
    launcher_age = now_epoch - launcher_mtime if launcher_mtime is not None else None
    if (
        not player_status_fresh
        and string_value(launcher_status, "state") == "running"
        and launcher_age is not None
        and -60.0 <= launcher_age <= max_player_age
    ):
        player_status = None
        player_status_fresh = True
        player_status_reason = "starting_grace"
    status = build_status(
        launcher_status=launcher_status,
        player_status=player_status,
        state_override=args.state_override,
        player_status_fresh=player_status_fresh,
        player_status_reason=player_status_reason,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir.chmod(0o700)

    status_json = json.dumps(status, ensure_ascii=True, indent=2) + "\n"
    write_text_atomic(out_dir / "status.json", status_json)
    write_text_atomic(
        out_dir / "status.svg",
        render_status_svg(status, rotation_deg=read_public_rotation(orientation_path)),
    )

    print(out_dir / "status.json")
    print(out_dir / "status.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
