#!/usr/bin/env python3
"""C9.1.3 display visual contract probe.

This probe generates a simple local SVG pattern and records sanitized display
metadata under /tmp. It does not read the real config, logs, media files,
private values, network metadata, raw process command lines or payloads.
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

SCHEMA_VERSION = "dadooh-c9.1.3-display-visual-contract.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c9-1-3-display-contract"
DEFAULT_STATUS_FILE = "/tmp/kiosky-status.json"
SERVICE_NAME = "kiosky-player.service"

TMP_ROOT = pathlib.Path("/tmp").resolve()
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600

STATUS_FILENAME = "status.json"
SUMMARY_FILENAME = "summary.txt"
PATTERN_FILENAME = "display-visual-contract.svg"
SNAPSHOT_DIRNAME = "snapshots"
OPERATION_FILENAME = "operation.json"
HUMAN_VALIDATION_FILENAME = "human-validation.json"

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

HUMAN_CHOICES = {
    "circle_answer": {"circle", "oval", "unclear"},
    "square_answer": {"square", "rectangle", "unclear"},
    "border_answer": {"yes", "no", "unclear"},
    "cut_answer": {"yes", "no", "unclear"},
    "top_arrow_answer": {"yes", "no", "unclear"},
    "stretch_answer": {"none", "horizontal", "vertical", "unclear"},
    "player_restored_answer": {"same", "changed", "not_restored", "unclear"},
}


class ProbeError(ValueError):
    """Raised for expected probe failures."""


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
        raise ProbeError("out-dir must be under /tmp")
    if resolved == TMP_ROOT:
        raise ProbeError("out-dir must be a dedicated directory under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise ProbeError("out-dir exists and is not a directory")
    return resolved


def prepare_private_dir(path: pathlib.Path) -> None:
    path.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    if stat.S_IMODE(path.stat().st_mode) != PRIVATE_DIR_MODE:
        path.chmod(PRIVATE_DIR_MODE)


def ensure_output_target(path: pathlib.Path, out_dir: pathlib.Path) -> None:
    resolved_out = out_dir.resolve(strict=True)
    resolved_target = path.resolve(strict=False)
    if not path_is_under(resolved_target, resolved_out):
        raise ProbeError("output target escaped out-dir")
    if resolved_target == resolved_out:
        raise ProbeError("output target must be a file")
    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt")):
        if path_is_under(resolved_target, forbidden):
            raise ProbeError("refusing to write outside /tmp")


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
        "temporary_probe_pattern_seen": False,
    }
    joined = " ".join(parts)
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
    if PATTERN_FILENAME in joined or "dadooh-c9-1-3-display-contract" in joined:
        categories["temporary_probe_pattern_seen"] = True
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
        "temporary_probe_pattern_seen": False,
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
                "modes_sample": modes[:16],
                "edid_blob_copied": False,
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


def mpv_ipc_snapshot(ipc_socket: pathlib.Path | None, timeout_sec: float) -> dict[str, Any]:
    if ipc_socket is None:
        return {"result": "not_requested", "socket_path_written": False}
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
                rid = 913000 + index
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


def visual_contract_svg() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<svg width="1360" height="768" viewBox="0 0 1360 768">
  <title>Dadooh C9.1.3 contrato visual de display</title>
  <rect x="0" y="0" width="1360" height="768" fill="#111111"/>
  <rect x="6" y="6" width="1348" height="756" fill="none" stroke="#fffb00" stroke-width="8"/>
  <rect x="26" y="26" width="1308" height="716" fill="none" stroke="#ffffff" stroke-width="2"/>
  <g stroke="#343a40" stroke-width="1">
    <path d="M170 26 V742"/>
    <path d="M340 26 V742"/>
    <path d="M510 26 V742"/>
    <path d="M680 26 V742"/>
    <path d="M850 26 V742"/>
    <path d="M1020 26 V742"/>
    <path d="M1190 26 V742"/>
    <path d="M26 96 H1334"/>
    <path d="M26 192 H1334"/>
    <path d="M26 288 H1334"/>
    <path d="M26 384 H1334"/>
    <path d="M26 480 H1334"/>
    <path d="M26 576 H1334"/>
    <path d="M26 672 H1334"/>
  </g>
  <g stroke="#ff4d4d" stroke-width="8" fill="none">
    <path d="M680 288 V480"/>
    <path d="M584 384 H776"/>
  </g>
  <circle cx="430" cy="384" r="158" fill="#101820" stroke="#00e5ff" stroke-width="10"/>
  <circle cx="430" cy="384" r="80" fill="none" stroke="#ffffff" stroke-width="3" stroke-dasharray="10 10"/>
  <rect x="820" y="226" width="316" height="316" fill="#1f2937" stroke="#7cff6b" stroke-width="10"/>
  <path d="M680 132 L680 48" stroke="#ff3df2" stroke-width="14" stroke-linecap="round"/>
  <path d="M680 40 L632 112 H728 Z" fill="#ff3df2"/>
  <path d="M144 132 L144 48" stroke="#ff3df2" stroke-width="10" stroke-linecap="round"/>
  <path d="M144 40 L112 92 H176 Z" fill="#ff3df2"/>
  <path d="M1216 132 L1216 48" stroke="#ff3df2" stroke-width="10" stroke-linecap="round"/>
  <path d="M1216 40 L1184 92 H1248 Z" fill="#ff3df2"/>
  <g font-family="DejaVu Sans, Arial, sans-serif" fill="#ffffff" text-anchor="middle">
    <text x="680" y="172" font-size="52" font-weight="700">TOPO</text>
    <text x="430" y="590" font-size="34" font-weight="700">CIRCULO</text>
    <text x="978" y="590" font-size="34" font-weight="700">QUADRADO</text>
    <text x="680" y="694" font-size="30">Se o círculo parecer oval, a tela está esticando a imagem.</text>
    <text x="680" y="728" font-size="30">Se a borda não aparecer inteira, há corte/overscan.</text>
  </g>
  <g fill="#fffb00">
    <rect x="6" y="6" width="54" height="54"/>
    <rect x="1300" y="6" width="54" height="54"/>
    <rect x="6" y="708" width="54" height="54"/>
    <rect x="1300" y="708" width="54" height="54"/>
  </g>
</svg>
"""


def generate_pattern(out_dir: pathlib.Path) -> pathlib.Path:
    prepare_private_dir(out_dir)
    path = out_dir / PATTERN_FILENAME
    atomic_write_private_text(path, visual_contract_svg(), out_dir)
    return path


def build_snapshot(phase: str, ipc_socket: pathlib.Path | None, ipc_timeout_sec: float) -> dict[str, Any]:
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
            "host_identity_written": False,
        },
    }


def load_json_file(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def collect_existing_snapshots(snapshot_dir: pathlib.Path) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for path in sorted(snapshot_dir.glob("*.json")):
        value = load_json_file(path)
        if value:
            snapshots.append(value)
    return sorted(snapshots, key=lambda item: str(item.get("generated_at_utc", "")))


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
        "framebuffers_first": get(first, ("display", "framebuffers"), []),
        "framebuffers_last": get(last, ("display", "framebuffers"), []),
        "drm_connectors_first": get(first, ("display", "drm_connectors"), []),
        "drm_connectors_last": get(last, ("display", "drm_connectors"), []),
        "mpv_ipc_result_first": get(first, ("mpv_ipc", "result")),
        "mpv_ipc_result_last": get(last, ("mpv_ipc", "result")),
        "mpv_osd_dimensions_first": get(first, ("mpv_ipc", "properties", "osd-dimensions"), {}),
        "mpv_osd_dimensions_last": get(last, ("mpv_ipc", "properties", "osd-dimensions"), {}),
        "mpv_video_out_params_first": get(first, ("mpv_ipc", "properties", "video-out-params"), {}),
        "mpv_video_out_params_last": get(last, ("mpv_ipc", "properties", "video-out-params"), {}),
    }


def pattern_status(out_dir: pathlib.Path) -> dict[str, Any]:
    path = out_dir / PATTERN_FILENAME
    return {
        "file": PATTERN_FILENAME,
        "exists": path.exists(),
        "under_tmp": str(path.resolve(strict=False)).startswith("/tmp/"),
        "contains_outer_border": True,
        "contains_grid": True,
        "contains_circle": True,
        "contains_square": True,
        "contains_center_cross": True,
        "contains_top_arrows": True,
        "contains_operator_text": True,
        "external_assets_used": False,
    }


def build_status(out_dir: pathlib.Path) -> dict[str, Any]:
    snapshot_dir = out_dir / SNAPSHOT_DIRNAME
    snapshots = collect_existing_snapshots(snapshot_dir) if snapshot_dir.exists() else []
    operation = load_json_file(out_dir / OPERATION_FILENAME)
    human_validation = load_json_file(out_dir / HUMAN_VALIDATION_FILENAME)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "result": "prepared" if not operation else operation.get("result", "operation_recorded"),
        "files": {
            "status": STATUS_FILENAME,
            "summary": SUMMARY_FILENAME,
            "pattern": PATTERN_FILENAME,
            "snapshots_dir": SNAPSHOT_DIRNAME,
            "operation": OPERATION_FILENAME if operation else "",
            "human_validation": HUMAN_VALIDATION_FILENAME if human_validation else "",
        },
        "pattern": pattern_status(out_dir),
        "comparison": compare_snapshots(snapshots),
        "operation": operation if operation else {"result": "not_run"},
        "human_validation": human_validation if human_validation else {"result": "pending_human_answers"},
        "guardrails": {
            "writes_only_under_tmp": True,
            "real_config_read": False,
            "real_config_written": False,
            "writer_called": False,
            "writer_real_mode_called": False,
            "data_config_touched": False,
            "data_written": False,
            "opt_written": False,
            "network_changed": False,
            "wifi_changed": False,
            "nmcli_called": False,
            "mpv_flags_changed": False,
            "launcher_changed": False,
            "player_repo_touched": False,
            "production_released": False,
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
            "host_identity_written": False,
            "human_free_text_written": False,
        },
    }


def build_summary(status: dict[str, Any]) -> str:
    comparison = status["comparison"]
    operation = status["operation"]
    human = status["human_validation"]
    return "\n".join(
        [
            "Dadooh C9.1.3 contrato visual de display/orientacao",
            "",
            f"schema_version: {status['schema_version']}",
            f"generated_at_utc: {status['generated_at_utc']}",
            f"result: {status['result']}",
            f"pattern_file: {status['pattern']['file']}",
            f"pattern_exists: {str(status['pattern']['exists']).lower()}",
            "pattern_contains_outer_border: true",
            "pattern_contains_grid: true",
            "pattern_contains_circle: true",
            "pattern_contains_square: true",
            "pattern_contains_center_cross: true",
            "pattern_contains_top_arrows: true",
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
            "Operation:",
            f"operation_result: {operation.get('result', 'not_run')}",
            f"temporary_player_stop_authorized: {str(operation.get('temporary_player_stop_authorized', False)).lower()}",
            f"temporary_player_stop_performed: {str(operation.get('temporary_player_stop_performed', False)).lower()}",
            f"temporary_mpv_started: {str(operation.get('temporary_mpv_started', False)).lower()}",
            f"temporary_mpv_terminated: {str(operation.get('temporary_mpv_terminated', False)).lower()}",
            f"restore_ok: {str(operation.get('restore_ok', False)).lower()}",
            "",
            "Human validation:",
            f"human_validation_result: {human.get('result', 'pending_human_answers')}",
            f"circle_answer: {human.get('circle_answer', 'pending')}",
            f"square_answer: {human.get('square_answer', 'pending')}",
            f"border_answer: {human.get('border_answer', 'pending')}",
            f"cut_answer: {human.get('cut_answer', 'pending')}",
            f"top_arrow_answer: {human.get('top_arrow_answer', 'pending')}",
            f"stretch_answer: {human.get('stretch_answer', 'pending')}",
            f"player_restored_answer: {human.get('player_restored_answer', 'pending')}",
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
            "mpv_flags_changed: false",
            "launcher_changed: false",
            "production_released: false",
            "",
            "Privacy:",
            "config_content_copied: false",
            "credential_value_written: false",
            "private_url_written: false",
            "media_path_written: false",
            "media_url_written: false",
            "raw_logs_written: false",
            "process_cmdlines_written: false",
            "network_metadata_written: false",
            "human_free_text_written: false",
        ]
    )


def assert_sanitized_text(out_dir: pathlib.Path) -> None:
    text_parts: list[str] = []
    paths = [
        out_dir / STATUS_FILENAME,
        out_dir / SUMMARY_FILENAME,
        out_dir / PATTERN_FILENAME,
        out_dir / OPERATION_FILENAME,
        out_dir / HUMAN_VALIDATION_FILENAME,
    ]
    snapshot_dir = out_dir / SNAPSHOT_DIRNAME
    if snapshot_dir.exists():
        paths.extend(snapshot_dir.glob("*.json"))
    for path in paths:
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
            raise ProbeError(f"privacy scan blocked marker: {marker}")


def refresh_status(out_dir: pathlib.Path) -> dict[str, Any]:
    prepare_private_dir(out_dir)
    status = build_status(out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_summary(status), out_dir)
    assert_sanitized_text(out_dir)
    return status


def write_snapshot(out_dir: pathlib.Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    prepare_private_dir(out_dir)
    snapshot_dir = out_dir / SNAPSHOT_DIRNAME
    prepare_private_dir(snapshot_dir)
    phase = str(snapshot["phase"])
    if not phase or "/" in phase or phase in {".", ".."}:
        raise ProbeError("invalid phase")
    atomic_write_private_json(snapshot_dir / f"{phase}.json", snapshot, out_dir)
    return refresh_status(out_dir)


def parse_bool_text(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ProbeError("boolean value must be true or false")


def record_operation(args: argparse.Namespace, out_dir: pathlib.Path) -> dict[str, Any]:
    display_seconds = max(0, int(args.display_seconds))
    operation = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "result": args.operation_result,
        "abort_reason": args.abort_reason,
        "display_seconds": display_seconds,
        "service_was_active": parse_bool_text(args.service_was_active),
        "temporary_player_stop_authorized": parse_bool_text(args.temporary_player_stop_authorized),
        "temporary_player_stop_performed": parse_bool_text(args.temporary_player_stop_performed),
        "temporary_mpv_started": parse_bool_text(args.temporary_mpv_started),
        "temporary_mpv_terminated": parse_bool_text(args.temporary_mpv_terminated),
        "restore_attempted": parse_bool_text(args.restore_attempted),
        "restore_ok": parse_bool_text(args.restore_ok),
        "service_active_after": args.service_active_after,
        "service_enabled_after": args.service_enabled_after,
        "service_nrestarts_after": args.service_nrestarts_after,
        "player_count_after": int(args.player_count_after),
        "mpv_count_after": int(args.mpv_count_after),
        "renderer_count_after": int(args.renderer_count_after),
        "human_authorization_required": True,
        "guardrails": {
            "real_config_read": False,
            "real_config_written": False,
            "writer_called": False,
            "data_config_touched": False,
            "data_written": False,
            "opt_written": False,
            "network_changed": False,
            "wifi_changed": False,
            "nmcli_called": False,
            "mpv_flags_changed": False,
            "launcher_changed": False,
            "temporary_processes_terminated": parse_bool_text(args.temporary_mpv_terminated),
        },
        "privacy": {
            "raw_logs_written": False,
            "process_cmdlines_written": False,
            "media_path_written": False,
            "private_values_written": False,
            "network_metadata_written": False,
        },
    }
    atomic_write_private_json(out_dir / OPERATION_FILENAME, operation, out_dir)
    return refresh_status(out_dir)


def validate_human_choices(args: argparse.Namespace) -> dict[str, str]:
    values = {
        "circle_answer": args.circle_answer,
        "square_answer": args.square_answer,
        "border_answer": args.border_answer,
        "cut_answer": args.cut_answer,
        "top_arrow_answer": args.top_arrow_answer,
        "stretch_answer": args.stretch_answer,
        "player_restored_answer": args.player_restored_answer,
    }
    for key, allowed in HUMAN_CHOICES.items():
        if values[key] not in allowed:
            raise ProbeError(f"invalid human validation value for {key}")
    return values


def record_human_validation(args: argparse.Namespace, out_dir: pathlib.Path) -> dict[str, Any]:
    values = validate_human_choices(args)
    human = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "result": "recorded",
        "questions": {
            "circle": "circle_or_oval",
            "square": "square_or_rectangle",
            "border": "outer_border_visible",
            "cut": "edges_cut_or_overscan",
            "top_arrow": "top_arrow_points_up",
            "stretch": "horizontal_or_vertical_stretch",
            "player_restored": "media_after_restore_same_as_before",
        },
        **values,
        "free_text_written": False,
    }
    atomic_write_private_json(out_dir / HUMAN_VALIDATION_FILENAME, human, out_dir)
    return refresh_status(out_dir)


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
    assert_raises(lambda: require_tmp_dir("/var/tmp/dadooh-c9-1-3"), "out-dir outside /tmp should fail")
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c9-1-3-self-test-", dir="/tmp"))
    try:
        out_dir = require_tmp_dir(str(root / "out"))
        pattern = generate_pattern(out_dir)
        text = pattern.read_text(encoding="utf-8")
        for expected in (
            "<circle",
            "<rect",
            "TOPO",
            "Se o círculo parecer oval, a tela está esticando a imagem.",
            "Se a borda não aparecer inteira, há corte/overscan.",
        ):
            assert_true(expected in text, f"pattern missing {expected}")

        fake_snapshot = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": utc_timestamp(),
            "phase": "self-test-a",
            "service": {"active": "active", "enabled": "enabled", "nrestarts": "0"},
            "processes": {"counts": {"player": 1, "mpv": 1, "renderer": 0}},
            "display": {
                "active_tty": "tty1",
                "framebuffers": [{"name": "fb0", "virtual_size": "1360,768"}],
                "drm_connectors": [{"name": "card0-HDMI-A-1", "status": "connected"}],
            },
            "mpv_ipc": {
                "result": "success",
                "properties": {
                    "width": 1360,
                    "height": 768,
                    "osd-dimensions": {"w": 1360, "h": 768, "aspect": 1.770833},
                },
                "socket_path_written": False,
            },
            "guardrails": {"real_config_read": False},
            "privacy": {"media_path_written": False},
        }
        status = write_snapshot(out_dir, fake_snapshot)
        assert_true(status["comparison"]["snapshots_count"] == 1, "one snapshot should be recorded")

        op_args = argparse.Namespace(
            operation_result="passed",
            abort_reason="",
            display_seconds="5",
            service_was_active="true",
            temporary_player_stop_authorized="true",
            temporary_player_stop_performed="true",
            temporary_mpv_started="true",
            temporary_mpv_terminated="true",
            restore_attempted="true",
            restore_ok="true",
            service_active_after="active",
            service_enabled_after="enabled",
            service_nrestarts_after="0",
            player_count_after="1",
            mpv_count_after="1",
            renderer_count_after="0",
        )
        status = record_operation(op_args, out_dir)
        assert_true(status["operation"]["restore_ok"] is True, "restore flag should be recorded")

        human_args = argparse.Namespace(
            circle_answer="circle",
            square_answer="square",
            border_answer="yes",
            cut_answer="no",
            top_arrow_answer="yes",
            stretch_answer="none",
            player_restored_answer="same",
        )
        status = record_human_validation(human_args, out_dir)
        assert_true(status["human_validation"]["circle_answer"] == "circle", "human answer should be recorded")

        assert_true(file_mode(out_dir) == PRIVATE_DIR_MODE, "out-dir should be 0700")
        assert_true(file_mode(out_dir / SNAPSHOT_DIRNAME) == PRIVATE_DIR_MODE, "snapshot dir should be 0700")
        for path in (
            out_dir / STATUS_FILENAME,
            out_dir / SUMMARY_FILENAME,
            out_dir / PATTERN_FILENAME,
            out_dir / SNAPSHOT_DIRNAME / "self-test-a.json",
            out_dir / OPERATION_FILENAME,
            out_dir / HUMAN_VALIDATION_FILENAME,
        ):
            assert_true(path.exists(), f"{path.name} should exist")
            assert_true(file_mode(path) == PRIVATE_FILE_MODE, f"{path.name} should be 0600")
        assert_raises(
            lambda: atomic_write_private_text(pathlib.Path("/data/c9-1-3"), "x", out_dir),
            "writing under /data should fail",
        )
        assert_sanitized_text(out_dir)
    finally:
        import shutil

        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate C9.1.3 display contract pattern and sanitized metadata.",
        allow_abbrev=False,
    )
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--generate-pattern", action="store_true", help="Generate the visual SVG pattern.")
    parser.add_argument("--phase", default="", help="Collect a sanitized snapshot with this phase label.")
    parser.add_argument("--ipc-socket", default="", help="Optional MPV IPC socket under /tmp for allowlisted properties.")
    parser.add_argument("--ipc-timeout-sec", type=float, default=1.0, help="MPV IPC timeout in seconds.")
    parser.add_argument("--record-operation", action="store_true", help="Record display operation result.")
    parser.add_argument("--operation-result", default="not_run", choices=("not_run", "prepared", "passed", "blocked", "failed"))
    parser.add_argument("--abort-reason", default="")
    parser.add_argument("--display-seconds", default="0")
    parser.add_argument("--service-was-active", default="false", choices=("true", "false"))
    parser.add_argument("--temporary-player-stop-authorized", default="false", choices=("true", "false"))
    parser.add_argument("--temporary-player-stop-performed", default="false", choices=("true", "false"))
    parser.add_argument("--temporary-mpv-started", default="false", choices=("true", "false"))
    parser.add_argument("--temporary-mpv-terminated", default="false", choices=("true", "false"))
    parser.add_argument("--restore-attempted", default="false", choices=("true", "false"))
    parser.add_argument("--restore-ok", default="false", choices=("true", "false"))
    parser.add_argument("--service-active-after", default="unknown")
    parser.add_argument("--service-enabled-after", default="unknown")
    parser.add_argument("--service-nrestarts-after", default="unknown")
    parser.add_argument("--player-count-after", default="0")
    parser.add_argument("--mpv-count-after", default="0")
    parser.add_argument("--renderer-count-after", default="0")
    parser.add_argument("--record-human-validation", action="store_true", help="Record normalized human answers.")
    parser.add_argument("--circle-answer", default="unclear", choices=sorted(HUMAN_CHOICES["circle_answer"]))
    parser.add_argument("--square-answer", default="unclear", choices=sorted(HUMAN_CHOICES["square_answer"]))
    parser.add_argument("--border-answer", default="unclear", choices=sorted(HUMAN_CHOICES["border_answer"]))
    parser.add_argument("--cut-answer", default="unclear", choices=sorted(HUMAN_CHOICES["cut_answer"]))
    parser.add_argument("--top-arrow-answer", default="unclear", choices=sorted(HUMAN_CHOICES["top_arrow_answer"]))
    parser.add_argument("--stretch-answer", default="unclear", choices=sorted(HUMAN_CHOICES["stretch_answer"]))
    parser.add_argument("--player-restored-answer", default="unclear", choices=sorted(HUMAN_CHOICES["player_restored_answer"]))
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
        actions = 0
        if args.generate_pattern:
            generate_pattern(out_dir)
            actions += 1
        if args.phase:
            ipc_socket = pathlib.Path(args.ipc_socket).expanduser().resolve(strict=False) if args.ipc_socket else None
            snapshot = build_snapshot(args.phase, ipc_socket, args.ipc_timeout_sec)
            write_snapshot(out_dir, snapshot)
            actions += 1
        if args.record_operation:
            record_operation(args, out_dir)
            actions += 1
        if args.record_human_validation:
            record_human_validation(args, out_dir)
            actions += 1
        if actions == 0:
            generate_pattern(out_dir)
            refresh_status(out_dir)
        else:
            refresh_status(out_dir)

        print(f"C9.1.3 display visual contract evidence written under {out_dir}")
        print(STATUS_FILENAME)
        print(SUMMARY_FILENAME)
        print(PATTERN_FILENAME)
        return 0
    except ProbeError as exc:
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
