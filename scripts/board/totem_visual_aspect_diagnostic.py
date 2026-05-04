#!/usr/bin/env python3
"""C9.1.2 visual aspect diagnostic with sanitized read-only snapshots.

The diagnostic writes only under /tmp, reads only public/runtime metadata, and
does not read the real config, logs, media files, backups or private values. MPV
IPC queries are limited to allowlisted geometry/playback properties and never
request path, filename, playlist or metadata.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import os
import pathlib
import socket
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any


sys.dont_write_bytecode = True

SCHEMA_VERSION = "dadooh-c9.1.2-visual-aspect-diagnostic.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c9-1-2-visual-aspect"
DEFAULT_STATUS_FILE = "/tmp/kiosky-status.json"
DEFAULT_MPV_IPC_SOCKET = "/tmp/kiosky/mpv.sock"
SERVICE_NAME = "kiosky-player.service"

TMP_ROOT = pathlib.Path("/tmp").resolve()
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600

STATUS_FILENAME = "status.json"
SUMMARY_FILENAME = "summary.txt"
SNAPSHOT_DIRNAME = "snapshots"

MPV_ALLOWLISTED_PROPERTIES: tuple[str, ...] = (
    "width",
    "height",
    "dwidth",
    "dheight",
    "video-params",
    "video-out-params",
    "osd-dimensions",
    "fullscreen",
    "pause",
    "time-pos",
)


class DiagnosticError(ValueError):
    """Raised for expected diagnostic failures."""


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
        raise DiagnosticError("out-dir must be under /tmp")
    if resolved == TMP_ROOT:
        raise DiagnosticError("out-dir must be a dedicated directory under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise DiagnosticError("out-dir exists and is not a directory")
    return resolved


def prepare_private_dir(path: pathlib.Path) -> None:
    path.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    if stat.S_IMODE(path.stat().st_mode) != PRIVATE_DIR_MODE:
        path.chmod(PRIVATE_DIR_MODE)


def ensure_output_target(path: pathlib.Path, out_dir: pathlib.Path) -> None:
    resolved_out = out_dir.resolve(strict=True)
    resolved_target = path.resolve(strict=False)
    if not path_is_under(resolved_target, resolved_out):
        raise DiagnosticError("output target escaped out-dir")
    if resolved_target == resolved_out:
        raise DiagnosticError("output target must be a file")
    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt")):
        if path_is_under(resolved_target, forbidden):
            raise DiagnosticError("refusing to write outside /tmp")


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


def atomic_write_private_json(path: pathlib.Path, value: dict[str, Any], out_dir: pathlib.Path) -> None:
    atomic_write_private_text(path, json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True), out_dir)


def read_text(path: pathlib.Path, *, limit: int = 160) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return "unavailable"
    return text[:limit] if text else ""


def run_readonly_command(args: list[str], timeout_sec: float = 2.0) -> str:
    try:
        proc = subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout_sec,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    text = proc.stdout.strip()
    return text[:200] if text else ""


def service_snapshot() -> dict[str, Any]:
    return {
        "name": SERVICE_NAME,
        "active": run_readonly_command(["systemctl", "is-active", SERVICE_NAME]),
        "enabled": run_readonly_command(["systemctl", "is-enabled", SERVICE_NAME]),
        "sub_state": run_readonly_command(["systemctl", "show", SERVICE_NAME, "-p", "SubState", "--value"]),
        "nrestarts": run_readonly_command(["systemctl", "show", SERVICE_NAME, "-p", "NRestarts", "--value"]),
        "read_only_observation": True,
    }


def command_categories(parts: list[str]) -> dict[str, bool]:
    categories = {
        "vo_gpu_seen": False,
        "gpu_context_drm_seen": False,
        "ao_null_seen": False,
        "fullscreen_flag_seen": False,
        "geometry_flag_seen": False,
        "video_unscaled_flag_seen": False,
        "screen_flag_seen": False,
        "input_ipc_server_seen": False,
    }
    for part in parts:
        if part == "--vo=gpu" or part.startswith("--vo=gpu"):
            categories["vo_gpu_seen"] = True
        elif part == "--gpu-context=drm" or part.startswith("--gpu-context=drm"):
            categories["gpu_context_drm_seen"] = True
        elif part == "--ao=null" or part.startswith("--ao=null"):
            categories["ao_null_seen"] = True
        elif part in {"--fullscreen", "--fs"}:
            categories["fullscreen_flag_seen"] = True
        elif part.startswith("--geometry"):
            categories["geometry_flag_seen"] = True
        elif part.startswith("--video-unscaled"):
            categories["video_unscaled_flag_seen"] = True
        elif part.startswith("--screen"):
            categories["screen_flag_seen"] = True
        elif part.startswith("--input-ipc-server"):
            categories["input_ipc_server_seen"] = True
    return categories


def process_snapshot() -> dict[str, Any]:
    counts = {
        "player": 0,
        "mpv": 0,
        "renderer": 0,
    }
    mpv_categories = {
        "vo_gpu_seen": False,
        "gpu_context_drm_seen": False,
        "ao_null_seen": False,
        "fullscreen_flag_seen": False,
        "geometry_flag_seen": False,
        "video_unscaled_flag_seen": False,
        "screen_flag_seen": False,
        "input_ipc_server_seen": False,
    }
    self_pid = os.getpid()
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == self_pid:
            continue
        try:
            raw = (proc / "cmdline").read_bytes()
            parts = [part.decode("utf-8", "ignore") for part in raw.split(b"\x00") if part]
            cmdline = " ".join(parts)
            comm = (proc / "comm").read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            continue
        first = parts[0] if parts else ""
        if comm == "mpv" or first.endswith("/mpv"):
            counts["mpv"] += 1
            for key, value in command_categories(parts).items():
                mpv_categories[key] = mpv_categories[key] or value
        if comm in {"python3", "python"} and ("/kiosk.py" in cmdline or cmdline.strip().endswith("kiosk.py")):
            counts["player"] += 1
        if comm in {"python3", "python"} and ("status_splash" in cmdline or "renderer" in cmdline):
            counts["renderer"] += 1
    return {
        "counts": counts,
        "mpv_command_categories": mpv_categories,
        "pids_written": False,
        "cmdlines_written": False,
    }


def framebuffer_snapshot() -> list[dict[str, str]]:
    frames: list[dict[str, str]] = []
    for path in sorted(pathlib.Path("/sys/class/graphics").glob("fb*")):
        frames.append(
            {
                "name": path.name,
                "virtual_size": read_text(path / "virtual_size"),
                "modes": read_text(path / "modes"),
                "bits_per_pixel": read_text(path / "bits_per_pixel"),
                "rotate": read_text(path / "rotate"),
            }
        )
    return frames


def drm_snapshot() -> list[dict[str, Any]]:
    connectors: list[dict[str, Any]] = []
    for path in sorted(pathlib.Path("/sys/class/drm").glob("card*-*")):
        status_path = path / "status"
        if not status_path.exists():
            continue
        modes_text = read_text(path / "modes", limit=4096)
        modes = [line.strip() for line in modes_text.splitlines() if line.strip() and line.strip() != "unavailable"]
        connectors.append(
            {
                "name": path.name,
                "status": read_text(status_path),
                "enabled": read_text(path / "enabled"),
                "modes_count": len(modes),
                "first_mode": modes[0] if modes else "",
                "preferred_mode_not_inferred": True,
            }
        )
    return connectors


def display_snapshot() -> dict[str, Any]:
    return {
        "active_tty": read_text(pathlib.Path("/sys/class/tty/tty0/active")),
        "framebuffers": framebuffer_snapshot(),
        "drm_connectors": drm_snapshot(),
    }


def load_public_status(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"present": False}
    except Exception:
        return {"present": True, "parse_error": True}
    if not isinstance(value, dict):
        return {"present": True, "parse_error": True}

    safe: dict[str, Any] = {"present": True}
    for key in (
        "state",
        "status",
        "playback",
        "playback_state",
        "mpv_running",
        "renderer_running",
        "playlist_size",
        "current_index",
        "consecutive_failures",
        "blocked_media_count",
        "uptime_sec",
    ):
        item = value.get(key)
        if item is None or isinstance(item, (str, bool, int, float)):
            safe[key] = item

    current_item = value.get("current_item")
    if isinstance(current_item, dict):
        current_safe: dict[str, Any] = {}
        for key in ("duration_ms", "offset_ms"):
            item = current_item.get(key)
            if item is None or isinstance(item, (str, bool, int, float)):
                current_safe[key] = item
        current_safe["path_written"] = False
        current_safe["url_written"] = False
        current_safe["metadata_written"] = False
        safe["current_item"] = current_safe
    return safe


def safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return None


def sanitize_dimensions_dict(value: Any, allowed_keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key in allowed_keys:
        if key in value:
            item = value.get(key)
            if item is None or isinstance(item, (str, bool, int, float)):
                safe[key] = item
    return safe


def sanitize_mpv_property(prop: str, value: Any) -> Any:
    if prop in {"width", "height", "dwidth", "dheight", "fullscreen", "pause", "time-pos"}:
        return safe_scalar(value)
    if prop in {"video-params", "video-out-params"}:
        return sanitize_dimensions_dict(
            value,
            (
                "w",
                "h",
                "dw",
                "dh",
                "aspect",
                "par",
                "rotate",
                "pixelformat",
                "hw-pixelformat",
            ),
        )
    if prop == "osd-dimensions":
        return sanitize_dimensions_dict(value, ("w", "h", "aspect", "par", "mt", "mb", "ml", "mr"))
    return None


def mpv_ipc_snapshot(ipc_socket: pathlib.Path, timeout_sec: float) -> dict[str, Any]:
    if not str(ipc_socket).startswith("/tmp/"):
        return {"result": "blocked", "reason": "ipc_socket_outside_tmp", "socket_path_written": False}
    if not ipc_socket.exists():
        return {"result": "error", "reason": "missing_socket", "socket_path_written": False}

    start = time.monotonic()
    responses: dict[str, Any] = {}
    errors: dict[str, str] = {}
    rid_to_prop: dict[int, str] = {}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_sec)
            sock.connect(str(ipc_socket))
            for index, prop in enumerate(MPV_ALLOWLISTED_PROPERTIES, start=1):
                rid = 910000 + index
                rid_to_prop[rid] = prop
                payload = {"command": ["get_property", prop], "request_id": rid}
                sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))

            buffer = ""
            deadline = start + timeout_sec
            while len(responses) < len(rid_to_prop) and time.monotonic() < deadline:
                sock.settimeout(max(deadline - time.monotonic(), 0.05))
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    break
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                    except Exception:
                        continue
                    prop = rid_to_prop.get(item.get("request_id"))
                    if prop is None:
                        continue
                    errors[prop] = str(item.get("error", "missing-error"))
                    responses[prop] = sanitize_mpv_property(prop, item.get("data"))
    except socket.timeout:
        return {
            "result": "timeout",
            "reason": "socket_timeout",
            "elapsed_ms": int(round((time.monotonic() - start) * 1000)),
            "properties": responses,
            "property_errors": errors,
            "socket_path_written": False,
        }
    except OSError as exc:
        return {
            "result": "error",
            "reason": type(exc).__name__,
            "elapsed_ms": int(round((time.monotonic() - start) * 1000)),
            "properties": responses,
            "property_errors": errors,
            "socket_path_written": False,
        }

    result = "success" if len(responses) == len(rid_to_prop) else "partial"
    return {
        "result": result,
        "reason": "" if result == "success" else "partial_response",
        "elapsed_ms": int(round((time.monotonic() - start) * 1000)),
        "properties": responses,
        "property_errors": errors,
        "allowlisted_properties": list(MPV_ALLOWLISTED_PROPERTIES),
        "socket_path_written": False,
    }


def build_snapshot(phase: str, ipc_socket: pathlib.Path, ipc_timeout_sec: float) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "phase": phase,
        "service": service_snapshot(),
        "processes": process_snapshot(),
        "display": display_snapshot(),
        "public_status": load_public_status(pathlib.Path(DEFAULT_STATUS_FILE)),
        "mpv_ipc": mpv_ipc_snapshot(ipc_socket, ipc_timeout_sec),
        "guardrails": {
            "read_only_snapshot": True,
            "real_config_read": False,
            "real_config_written": False,
            "writer_called": False,
            "data_config_touched": False,
            "data_written": False,
            "opt_written": False,
            "network_changed": False,
            "wifi_changed": False,
            "nmcli_called": False,
            "mpv_process_started_by_diagnostic": False,
            "service_state_changed_by_snapshot": False,
        },
        "privacy": {
            "config_content_copied": False,
            "candidate_payload_copied": False,
            "private_values_used": False,
            "private_values_written": False,
            "environment_value_raw_written": False,
            "credential_value_written": False,
            "private_url_written": False,
            "media_path_written": False,
            "media_url_written": False,
            "raw_logs_written": False,
            "process_cmdlines_written": False,
            "network_metadata_written": False,
        },
    }


def load_existing_status(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def compare_snapshots(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    if not snapshots:
        return {"snapshots_count": 0}

    first = snapshots[0]
    last = snapshots[-1]

    def get(obj: dict[str, Any], path: tuple[str, ...], default: Any = None) -> Any:
        cur: Any = obj
        for key in path:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(key)
        return cur

    return {
        "snapshots_count": len(snapshots),
        "phases": [str(item.get("phase", "")) for item in snapshots],
        "service_active_first": get(first, ("service", "active")),
        "service_active_last": get(last, ("service", "active")),
        "service_enabled_first": get(first, ("service", "enabled")),
        "service_enabled_last": get(last, ("service", "enabled")),
        "nrestarts_first": get(first, ("service", "nrestarts")),
        "nrestarts_last": get(last, ("service", "nrestarts")),
        "player_count_first": get(first, ("processes", "counts", "player")),
        "player_count_last": get(last, ("processes", "counts", "player")),
        "mpv_count_first": get(first, ("processes", "counts", "mpv")),
        "mpv_count_last": get(last, ("processes", "counts", "mpv")),
        "renderer_count_first": get(first, ("processes", "counts", "renderer")),
        "renderer_count_last": get(last, ("processes", "counts", "renderer")),
        "active_tty_first": get(first, ("display", "active_tty")),
        "active_tty_last": get(last, ("display", "active_tty")),
        "mpv_ipc_result_first": get(first, ("mpv_ipc", "result")),
        "mpv_ipc_result_last": get(last, ("mpv_ipc", "result")),
        "mpv_osd_dimensions_first": get(first, ("mpv_ipc", "properties", "osd-dimensions"), {}),
        "mpv_osd_dimensions_last": get(last, ("mpv_ipc", "properties", "osd-dimensions"), {}),
        "mpv_video_out_params_first": get(first, ("mpv_ipc", "properties", "video-out-params"), {}),
        "mpv_video_out_params_last": get(last, ("mpv_ipc", "properties", "video-out-params"), {}),
    }


def build_status(out_dir: pathlib.Path, snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "result": "snapshots_recorded",
        "out_dir": str(out_dir),
        "snapshot_files": [f"{SNAPSHOT_DIRNAME}/{item.get('phase')}.json" for item in snapshots],
        "comparison": compare_snapshots(snapshots),
        "guardrails": {
            "writes_only_under_tmp": True,
            "real_config_read": False,
            "real_config_written": False,
            "writer_called": False,
            "data_config_touched": False,
            "data_written": False,
            "opt_written": False,
            "network_changed": False,
            "wifi_changed": False,
            "nmcli_called": False,
            "mpv_process_started_by_diagnostic": False,
            "service_state_changed_by_snapshot": False,
        },
        "privacy": {
            "config_content_copied": False,
            "private_values_used": False,
            "environment_value_raw_written": False,
            "credential_value_written": False,
            "private_url_written": False,
            "media_path_written": False,
            "media_url_written": False,
            "raw_logs_written": False,
            "process_cmdlines_written": False,
            "network_metadata_written": False,
        },
    }


def build_summary(status: dict[str, Any]) -> str:
    comparison = status["comparison"]
    return "\n".join(
        [
            "Dadooh C9.1.2 diagnostico de proporcao visual",
            "",
            f"schema_version: {status['schema_version']}",
            f"generated_at_utc: {status['generated_at_utc']}",
            f"result: {status['result']}",
            f"snapshots_count: {comparison.get('snapshots_count')}",
            f"phases: {','.join(comparison.get('phases', []))}",
            f"service_active_first: {comparison.get('service_active_first')}",
            f"service_active_last: {comparison.get('service_active_last')}",
            f"service_enabled_first: {comparison.get('service_enabled_first')}",
            f"service_enabled_last: {comparison.get('service_enabled_last')}",
            f"nrestarts_first: {comparison.get('nrestarts_first')}",
            f"nrestarts_last: {comparison.get('nrestarts_last')}",
            f"player_count_first: {comparison.get('player_count_first')}",
            f"player_count_last: {comparison.get('player_count_last')}",
            f"mpv_count_first: {comparison.get('mpv_count_first')}",
            f"mpv_count_last: {comparison.get('mpv_count_last')}",
            f"renderer_count_first: {comparison.get('renderer_count_first')}",
            f"renderer_count_last: {comparison.get('renderer_count_last')}",
            f"active_tty_first: {comparison.get('active_tty_first')}",
            f"active_tty_last: {comparison.get('active_tty_last')}",
            f"mpv_ipc_result_first: {comparison.get('mpv_ipc_result_first')}",
            f"mpv_ipc_result_last: {comparison.get('mpv_ipc_result_last')}",
            "",
            "Guardrails:",
            "writes_only_under_tmp: true",
            "real_config_read: false",
            "real_config_written: false",
            "writer_called: false",
            "data_config_touched: false",
            "data_written: false",
            "opt_written: false",
            "network_changed: false",
            "wifi_changed: false",
            "nmcli_called: false",
            "service_state_changed_by_snapshot: false",
            "",
            "Privacy:",
            "config_content_copied: false",
            "private_values_used: false",
            "credential_value_written: false",
            "private_url_written: false",
            "media_path_written: false",
            "media_url_written: false",
            "raw_logs_written: false",
            "process_cmdlines_written: false",
        ]
    )


def collect_existing_snapshots(snapshot_dir: pathlib.Path) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for path in sorted(snapshot_dir.glob("*.json")):
        value = load_existing_status(path)
        if value:
            snapshots.append(value)
    return snapshots


def assert_sanitized_text(out_dir: pathlib.Path) -> None:
    text_parts: list[str] = []
    for path in [out_dir / STATUS_FILENAME, out_dir / SUMMARY_FILENAME, *(out_dir / SNAPSHOT_DIRNAME).glob("*.json")]:
        if path.exists() and path.is_file():
            text_parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    text = "\n".join(text_parts).lower()
    for marker in (
        "api_key",
        "api_url",
        "environment_id",
        "token",
        "secret",
        "password",
        "senha",
        "/data/config/config.json",
        "/data/media/",
        "raw_payload",
        "http://",
        "https://",
    ):
        if marker in text:
            raise DiagnosticError(f"privacy scan blocked marker: {marker}")


def write_snapshot(out_dir: pathlib.Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    prepare_private_dir(out_dir)
    snapshot_dir = out_dir / SNAPSHOT_DIRNAME
    prepare_private_dir(snapshot_dir)
    phase = str(snapshot["phase"])
    if not phase or "/" in phase or phase in {".", ".."}:
        raise DiagnosticError("invalid phase")
    atomic_write_private_json(snapshot_dir / f"{phase}.json", snapshot, out_dir)
    snapshots = collect_existing_snapshots(snapshot_dir)
    status = build_status(out_dir, snapshots)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_summary(status), out_dir)
    assert_sanitized_text(out_dir)
    return status


def file_mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_raises(func, message: str) -> None:
    try:
        func()
    except Exception:
        return
    raise AssertionError(message)


def run_self_test() -> None:
    assert_raises(lambda: require_tmp_dir("/var/tmp/dadooh-c9-1-2"), "out-dir outside /tmp should fail")
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c9-1-2-self-test-", dir="/tmp"))
    try:
        out_dir = require_tmp_dir(str(root / "out"))
        snapshot = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": utc_timestamp(),
            "phase": "self-test-a",
            "service": {"active": "active", "enabled": "enabled", "nrestarts": "0"},
            "processes": {"counts": {"player": 1, "mpv": 1, "renderer": 0}},
            "display": {"active_tty": "tty1"},
            "mpv_ipc": {
                "result": "success",
                "properties": {
                    "width": 1080,
                    "height": 1920,
                    "dwidth": 432,
                    "dheight": 768,
                    "osd-dimensions": {"w": 1360, "h": 768},
                },
                "socket_path_written": False,
            },
            "guardrails": {"real_config_read": False},
            "privacy": {"media_path_written": False},
        }
        status = write_snapshot(out_dir, snapshot)
        assert_true(status["comparison"]["snapshots_count"] == 1, "one snapshot should be recorded")
        assert_true(file_mode(out_dir) == PRIVATE_DIR_MODE, "out-dir should be 0700")
        assert_true(file_mode(out_dir / SNAPSHOT_DIRNAME) == PRIVATE_DIR_MODE, "snapshot dir should be 0700")
        for path in (out_dir / STATUS_FILENAME, out_dir / SUMMARY_FILENAME, out_dir / SNAPSHOT_DIRNAME / "self-test-a.json"):
            assert_true(path.exists(), f"{path.name} should exist")
            assert_true(file_mode(path) == PRIVATE_FILE_MODE, f"{path.name} should be 0600")

        snapshot_b = dict(snapshot)
        snapshot_b["phase"] = "self-test-b"
        snapshot_b["display"] = {"active_tty": "tty2"}
        status_b = write_snapshot(out_dir, snapshot_b)
        assert_true(status_b["comparison"]["snapshots_count"] == 2, "two snapshots should be recorded")
        assert_true(status_b["comparison"]["active_tty_first"] == "tty1", "first tty should be recorded")
        assert_true(status_b["comparison"]["active_tty_last"] == "tty2", "last tty should be recorded")
        assert_raises(
            lambda: atomic_write_private_text(pathlib.Path("/data/c9-1-2"), "x", out_dir),
            "writing under /data should fail",
        )
    finally:
        import shutil

        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect sanitized C9.1.2 visual aspect snapshots.",
        allow_abbrev=False,
    )
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--phase", default="phase-a-current", help="Snapshot phase label.")
    parser.add_argument("--ipc-socket", default=DEFAULT_MPV_IPC_SOCKET, help="MPV IPC socket under /tmp.")
    parser.add_argument("--ipc-timeout-sec", type=float, default=1.0, help="MPV IPC timeout in seconds.")
    parser.add_argument("--self-test", action="store_true", help="Run local self-tests under /tmp and exit.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0
        out_dir = require_tmp_dir(args.out_dir)
        ipc_socket = pathlib.Path(args.ipc_socket).expanduser().resolve(strict=False)
        snapshot = build_snapshot(args.phase, ipc_socket, args.ipc_timeout_sec)
        write_snapshot(out_dir, snapshot)
        print(f"C9.1.2 visual aspect snapshot written under {out_dir}")
        print(STATUS_FILENAME)
        print(SUMMARY_FILENAME)
        print(f"{SNAPSHOT_DIRNAME}/{args.phase}.json")
        return 0
    except DiagnosticError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except AssertionError:
        print("error: self-test failed", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
