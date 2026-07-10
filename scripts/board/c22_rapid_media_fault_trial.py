#!/usr/bin/env python3
"""Run a rapid C22 media-fault trial against kiosk.py on a C18 board.

The real board path is intentionally isolated: it stops the production player
and update timers, runs the supplied kiosk.py with a temporary /tmp config,
serves a localhost-only API/media fixture, samples status/MPV/KMS, then restores
the original unit activity in a finally block and signal path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


SCHEMA = "dadooh.c22.rapid_media_fault_trial.v1"
SELF_TEST_SCHEMA = "dadooh.c22.rapid_media_fault_trial.self_test.v1"
DEFAULT_SERVICE = "kiosky-player.service"
DEFAULT_TIMERS = (
    "totem-update-agent.timer",
    "totem-player-runtime-update-agent.timer",
)
DEFAULT_UPDATE_SERVICES = (
    "totem-update-agent.service",
    "totem-player-runtime-update-agent.service",
)
DEFAULT_MPV_PATH = "/opt/totem/bin/totem-mpv-hwdecode"
DEFAULT_STATUS_FILE = Path("/tmp/kiosky-status.json")
DEFAULT_REAL_IPC_PATH = Path("/tmp/kiosky/mpv.sock")
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KIOSK_PATH = REPO_ROOT / "player-runtime" / "kiosky-player" / "kiosk.py"
TMP_ROOT = Path("/tmp").resolve()
PRIVATE_FILE_MODE = 0o600
PRIVATE_DIR_MODE = 0o700
MAX_STATUS_FILE_BYTES = 256 * 1024
IPC_PROPS = (
    "idle-active",
    "pause",
    "time-pos",
    "duration",
    "percent-pos",
    "eof-reached",
    "estimated-frame-number",
    "hwdec-current",
    "vo-configured",
    "filename",
    "path",
    "video-params",
)
FORBIDDEN_PATHS = (
    Path("/data/config"),
    Path("/data/media"),
    Path("/data/apps/kiosky-player/current"),
    Path("/data/apps/kiosky-player/previous"),
    Path("/data/state/kiosky-player"),
    Path("/data/player-runtime/current"),
    Path("/data/player-runtime/previous"),
    Path("/data/player-runtime/state.json"),
    Path("/data/player-runtime/quarantine"),
    Path("/data/quarantine"),
)
OPERATIONAL_MTIME_PATHS = (
    Path("/data/state/kiosky-player"),
    Path("/data/player-runtime/state.json"),
)
PRIVATE_PATTERNS = (
    re.compile(r"/data/config(?:/|\b)"),
    re.compile(r"/data/media(?:/|\b)"),
    re.compile(r"/data/apps/kiosky-player/(?:current|previous)(?:/|\b)"),
    re.compile(r"/data/quarantine(?:/|\b)"),
    re.compile(r"api[_-]?key", re.I),
    re.compile(r"\btoken\b", re.I),
    re.compile(r"\bsecret\b", re.I),
    re.compile(r"\bpassword\b", re.I),
    re.compile(r"https?://(?!127\.0\.0\.1(?::|/|$)|localhost(?::|/|$))", re.I),
)
VALID_MEDIA_SCENARIOS = {"mixed", "sidecar_rebuild", "recovery"}
FAULT_SCENARIOS = {"api_500", "empty_playlist", "truncated_download"}
KMS_BLACK_LUMA_THRESHOLD = 4.0
MAX_STATUS_MPV_MISMATCH_RATIO = 0.12
MAX_STATUS_MPV_MISMATCH_SAMPLES = 3
MAX_STATUS_MPV_MISMATCH_CEILING_RATIO = 0.35


class TrialError(RuntimeError):
    """Expected trial failure."""


class PrivacyError(TrialError):
    """Raised when a public artifact would expose private data."""


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha1_short(value: Any, length: int = 12) -> str:
    return hashlib.sha1(str(value).encode("utf-8"), usedforsecurity=False).hexdigest()[:length]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def alias(value: Any, prefix: str = "alias") -> str:
    raw = str(value or "")
    if not raw:
        return ""
    return f"{prefix}-{sha1_short(raw)}"


def sanitized_stderr_excerpt(data: bytes, limit: int = 800) -> str:
    text = data.decode("utf-8", "replace")[-limit:]
    text = re.sub(r"https?://\S+", "<url>", text)
    text = re.sub(r"/(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+", "<path>", text)
    return text.strip()


def media_alias(path: str = "", url: str = "") -> str:
    source = url or path or ""
    return alias(source, "media") if source else ""


def safe_path_alias(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    if "://" in value:
        return f"<url:{sha1_short(value)}>"
    if value.startswith("/"):
        return f"<path:{sha1_short(value)}>"
    return f"<name:{sha1_short(value)}>"


def path_is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def require_tmp_output_dir(raw_path: str | Path) -> Path:
    path = Path(raw_path).expanduser()
    resolved = path.resolve(strict=False)
    if resolved == TMP_ROOT:
        raise TrialError("output-dir must be a dedicated directory below /tmp")
    if not path_is_under(resolved, TMP_ROOT):
        raise TrialError("output-dir must be below /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise TrialError("output-dir exists and is not a directory")
    return resolved


def fsync_dir(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(str(path), flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_json_private(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    data = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    try:
        os.chmod(path, PRIVATE_FILE_MODE)
    except OSError:
        pass
    fsync_dir(path.parent)


def write_text_private(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(content)
        if not content.endswith("\n"):
            fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    try:
        os.chmod(path, PRIVATE_FILE_MODE)
    except OSError:
        pass
    fsync_dir(path.parent)


def compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def assert_public_json_safe(payload: Any) -> None:
    text = compact_json(payload)
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise PrivacyError(f"public report blocked by privacy pattern: {pattern.pattern}")


def read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return {"_parse_error": True}


def stat_public(path: Path) -> dict[str, Any]:
    try:
        st = path.lstat()
    except FileNotFoundError:
        return {"exists": False}
    except OSError:
        return {"exists": False, "stat_error": "present"}
    kind = "other"
    if path.is_symlink():
        kind = "symlink"
    elif path.is_dir():
        kind = "directory"
    elif path.is_file():
        kind = "file"
    result: dict[str, Any] = {
        "exists": True,
        "kind": kind,
        "mode": oct(st.st_mode & 0o7777),
        "size": int(st.st_size),
        "mtime_ns": int(st.st_mtime_ns),
    }
    if path.is_symlink():
        try:
            result["target_alias"] = alias(os.readlink(path), "target")
        except OSError:
            result["target_alias"] = "unreadable"
    return result


def sanitize_status_item(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    path = value.get("path") if isinstance(value.get("path"), str) else ""
    url = value.get("url") if isinstance(value.get("url"), str) else ""
    source_path = value.get("source_path") if isinstance(value.get("source_path"), str) else ""
    out: dict[str, Any] = {
        "alias": media_alias(path, url),
        "path_alias": safe_path_alias(path),
    }
    if source_path:
        out["source_path_alias"] = safe_path_alias(source_path)
    for key in ("duration_ms", "offset_ms"):
        if key in value:
            try:
                out[key] = int(value[key])
            except Exception:
                pass
    if isinstance(value.get("started_at"), str):
        out["started_at_present"] = True
    return out


def sanitize_status(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {"present": False}
    if not isinstance(raw, dict) or raw.get("_parse_error"):
        return {"present": True, "parse_error": True}
    current_item = sanitize_status_item(raw.get("current_item"))
    next_item = sanitize_status_item(raw.get("next_item"))
    safe: dict[str, Any] = {
        "present": True,
        "playback_state": raw.get("playback_state"),
        "player_state": raw.get("player_state"),
        "startup_phase": raw.get("startup_phase"),
        "content_state": raw.get("content_state"),
        "playlist_size": raw.get("playlist_size"),
        "playlist_update_state": raw.get("playlist_update_state"),
        "pending_playlist_size": raw.get("pending_playlist_size"),
        "failed_media_count": raw.get("failed_media_count"),
        "content_stale": raw.get("content_stale"),
        "content_stale_reason": raw.get("content_stale_reason"),
        "current_index": raw.get("current_index"),
        "mpv_running": raw.get("mpv_running"),
        "first_frame_ready": raw.get("first_frame_ready"),
        "first_content_load_accepted": raw.get("first_content_load_accepted"),
        "consecutive_failures": raw.get("consecutive_failures"),
        "blocked_media_count": raw.get("blocked_media_count"),
        "black_screen_risk_reason": "present" if raw.get("black_screen_risk_reason") else None,
        "last_poll_error": "present" if raw.get("last_poll_error") else None,
        "last_render_error": "present" if raw.get("last_render_error") else None,
        "current_item": current_item,
        "next_item": next_item,
    }
    return safe


def raw_status_for_private_local_status(path: Path) -> Any:
    try:
        st = path.lstat()
    except FileNotFoundError:
        return None
    if not path.is_file() or st.st_size > MAX_STATUS_FILE_BYTES:
        return {"_parse_error": True}
    return read_json_file(path)


def sanitize_video_params(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key in ("w", "h", "dw", "dh", "aspect", "par", "rotate", "pixelformat", "hw-pixelformat"):
        if key in value and (value[key] is None or isinstance(value[key], (str, int, float, bool))):
            safe[key] = value[key]
    return safe


def ipc_query_many(ipc_path: Path, timeout_sec: float) -> dict[str, Any]:
    if not ipc_path.exists():
        return {"result": "error", "error": "missing_socket", "elapsed_ms": 0, "values": {}, "prop_errors": {}}
    start = time.monotonic()
    responses: dict[str, Any] = {}
    prop_errors: dict[str, str] = {}
    rid_to_prop: dict[int, str] = {}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_sec)
            sock.connect(str(ipc_path))
            for index, prop in enumerate(IPC_PROPS, start=1):
                rid = 920000 + index
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
                        candidate = json.loads(line)
                    except Exception:
                        continue
                    prop = rid_to_prop.get(candidate.get("request_id"))
                    if not prop:
                        continue
                    responses[prop] = candidate.get("data")
                    prop_errors[prop] = str(candidate.get("error", "missing-error"))
    except socket.timeout:
        return {
            "result": "timeout",
            "error": "socket_timeout",
            "elapsed_ms": int((time.monotonic() - start) * 1000),
            "values": responses,
            "prop_errors": prop_errors,
        }
    except Exception as exc:
        return {
            "result": "error",
            "error": type(exc).__name__,
            "elapsed_ms": int((time.monotonic() - start) * 1000),
            "values": responses,
            "prop_errors": prop_errors,
        }
    result = "success" if len(responses) >= len(rid_to_prop) else "timeout"
    error = "" if result == "success" else "partial_response"
    return {
        "result": result,
        "error": error,
        "elapsed_ms": int((time.monotonic() - start) * 1000),
        "values": responses,
        "prop_errors": prop_errors,
    }


def sanitize_ipc(raw: dict[str, Any]) -> dict[str, Any]:
    values = raw.get("values") if isinstance(raw.get("values"), dict) else {}
    path = values.get("path") if isinstance(values.get("path"), str) else ""
    filename = values.get("filename") if isinstance(values.get("filename"), str) else ""
    return {
        "result": raw.get("result"),
        "error": raw.get("error"),
        "elapsed_ms": raw.get("elapsed_ms"),
        "path_alias": safe_path_alias(path),
        "filename_alias": safe_path_alias(filename),
        "current_alias": safe_path_alias(path) or safe_path_alias(filename),
        "time_pos": values.get("time-pos") if isinstance(values.get("time-pos"), (int, float, str)) else None,
        "duration": values.get("duration") if isinstance(values.get("duration"), (int, float, str)) else None,
        "percent_pos": values.get("percent-pos") if isinstance(values.get("percent-pos"), (int, float, str)) else None,
        "idle_active": values.get("idle-active") if isinstance(values.get("idle-active"), (bool, str)) else None,
        "pause": values.get("pause") if isinstance(values.get("pause"), (bool, str)) else None,
        "eof_reached": values.get("eof-reached") if isinstance(values.get("eof-reached"), (bool, str)) else None,
        "estimated_frame_number": (
            values.get("estimated-frame-number")
            if isinstance(values.get("estimated-frame-number"), (int, float, str))
            else None
        ),
        "hwdec_current": values.get("hwdec-current") if isinstance(values.get("hwdec-current"), str) else "",
        "vo_configured": values.get("vo-configured") if isinstance(values.get("vo-configured"), (bool, str)) else None,
        "video_params": sanitize_video_params(values.get("video-params")),
        "property_errors": raw.get("prop_errors") if isinstance(raw.get("prop_errors"), dict) else {},
    }


def kms_capture(ffmpeg_path: str, timeout_sec: float = 4.0) -> dict[str, Any]:
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "kmsgrab",
        "-i",
        "-",
        "-frames:v",
        "1",
        "-vf",
        "hwdownload,format=bgra",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_sec,
        )
    except FileNotFoundError:
        return {"result": "error", "error": "ffmpeg_missing", "elapsed_ms": 0}
    except subprocess.TimeoutExpired:
        return {"result": "timeout", "error": "kmsgrab_timeout", "elapsed_ms": int((time.monotonic() - start) * 1000)}
    except Exception as exc:
        return {"result": "error", "error": type(exc).__name__, "elapsed_ms": int((time.monotonic() - start) * 1000)}
    elapsed_ms = int((time.monotonic() - start) * 1000)
    data = proc.stdout or b""
    if proc.returncode != 0:
        return {
            "result": "error",
            "error": "ffmpeg_kmsgrab_failed",
            "elapsed_ms": elapsed_ms,
            "stderr_alias": alias((proc.stderr or b"").decode("utf-8", "replace")[-256:], "stderr"),
            "stderr_excerpt": sanitized_stderr_excerpt(proc.stderr or b""),
        }
    if len(data) < 16 or len(data) % 4 != 0:
        return {"result": "error", "error": "raw_bgra_unexpected_size", "elapsed_ms": elapsed_ms, "bytes": len(data)}
    pixel_count = len(data) // 4
    step = max(pixel_count // 4096, 1)
    luma_sum = 0.0
    samples = 0
    for index in range(0, pixel_count, step):
        offset = index * 4
        b = data[offset]
        g = data[offset + 1]
        r = data[offset + 2]
        luma_sum += (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
        samples += 1
    avg_luma = luma_sum / max(samples, 1)
    return {
        "result": "success",
        "error": "",
        "elapsed_ms": elapsed_ms,
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "luma_avg": round(avg_luma, 3),
        "sampled_pixels": samples,
        "raw_black": avg_luma <= KMS_BLACK_LUMA_THRESHOLD,
    }


def kms_capture_sequence(
    ffmpeg_path: str,
    duration_sec: float,
    fps: int = 10,
    width: int = 64,
    height: int = 36,
) -> dict[str, Any]:
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "kmsgrab",
        "-framerate",
        str(fps),
        "-i",
        "-",
        "-t",
        str(duration_sec),
        "-vf",
        f"hwdownload,format=bgra,scale={width}:{height}",
        "-pix_fmt",
        "bgra",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=duration_sec + 15.0,
        )
    except FileNotFoundError:
        return {"result": "error", "error": "ffmpeg_missing"}
    except subprocess.TimeoutExpired:
        return {"result": "timeout", "error": "continuous_kmsgrab_timeout"}
    except Exception as exc:
        return {"result": "error", "error": type(exc).__name__}

    elapsed_ms = int((time.monotonic() - started) * 1000)
    data = proc.stdout or b""
    frame_bytes = width * height * 4
    if proc.returncode != 0:
        return {
            "result": "error",
            "error": "continuous_kmsgrab_failed",
            "elapsed_ms": elapsed_ms,
            "stderr_alias": alias((proc.stderr or b"").decode("utf-8", "replace")[-256:], "stderr"),
            "stderr_excerpt": sanitized_stderr_excerpt(proc.stderr or b""),
        }
    if frame_bytes <= 0 or not data or len(data) % frame_bytes != 0:
        return {
            "result": "error",
            "error": "continuous_raw_bgra_unexpected_size",
            "elapsed_ms": elapsed_ms,
            "bytes": len(data),
        }

    luma_values: list[float] = []
    frame_hashes: set[str] = set()
    black_frames = 0
    black_streak = 0
    max_black_streak = 0
    for offset in range(0, len(data), frame_bytes):
        frame = data[offset : offset + frame_bytes]
        luma = sum(
            (0.2126 * frame[index + 2]) + (0.7152 * frame[index + 1]) + (0.0722 * frame[index])
            for index in range(0, frame_bytes, 4)
        ) / (frame_bytes // 4)
        luma_values.append(luma)
        frame_hashes.add(sha256_bytes(frame))
        if luma <= KMS_BLACK_LUMA_THRESHOLD:
            black_frames += 1
            black_streak += 1
            max_black_streak = max(max_black_streak, black_streak)
        else:
            black_streak = 0

    return {
        "result": "success",
        "error": "",
        "elapsed_ms": elapsed_ms,
        "fps": fps,
        "duration_sec": duration_sec,
        "frames": len(luma_values),
        "unique_frame_hashes": len(frame_hashes),
        "min_luma": round(min(luma_values), 3),
        "max_luma": round(max(luma_values), 3),
        "black_frames": black_frames,
        "max_consecutive_black_frames": max_black_streak,
        "max_black_duration_ms": int((max_black_streak / fps) * 1000),
    }


class CommandRunner:
    def __call__(self, args: list[str], timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )


@dataclass
class UnitState:
    name: str
    active_state: str = "unknown"
    sub_state: str = "unknown"
    load_state: str = "unknown"
    unit_file_state: str = "unknown"
    nrestarts: int | None = None

    @property
    def was_active(self) -> bool:
        return self.active_state == "active"

    def public(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "active_state": self.active_state,
            "sub_state": self.sub_state,
            "load_state": self.load_state,
            "unit_file_state": self.unit_file_state,
            "nrestarts": self.nrestarts,
        }


class SystemdController:
    def __init__(
        self,
        service: str,
        timers: list[str],
        update_services: list[str] | None = None,
        runner: Callable[[list[str], float], subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.service = service
        self.timers = list(timers)
        self.update_services = list(update_services or DEFAULT_UPDATE_SERVICES)
        self.units = [*self.timers, *self.update_services, self.service]
        self.runner = runner or CommandRunner()
        self.initial: dict[str, UnitState] = {}
        self.after_stop: dict[str, UnitState] = {}
        self.final: dict[str, UnitState] = {}
        self.actions: list[dict[str, Any]] = []

    def _run_systemctl(self, args: list[str], timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
        completed = self.runner(["systemctl", *args], timeout)
        self.actions.append(
            {
                "args": ["systemctl", *args],
                "returncode": completed.returncode,
                "stdout_alias": alias((completed.stdout or "")[-256:], "stdout") if completed.stdout else "",
                "stderr_alias": alias((completed.stderr or "")[-256:], "stderr") if completed.stderr else "",
            }
        )
        return completed

    def unit_state(self, unit: str) -> UnitState:
        keys = ("ActiveState", "SubState", "LoadState", "UnitFileState", "NRestarts")
        completed = self._run_systemctl(["show", unit, *sum([["-p", key] for key in keys], [])], timeout=10.0)
        raw: dict[str, str] = {}
        for line in (completed.stdout or "").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                raw[key] = value
        nrestarts: int | None = None
        try:
            nrestarts = int(raw.get("NRestarts", "")) if raw.get("NRestarts", "") != "" else None
        except ValueError:
            nrestarts = None
        return UnitState(
            name=unit,
            active_state=raw.get("ActiveState") or "unknown",
            sub_state=raw.get("SubState") or "unknown",
            load_state=raw.get("LoadState") or "unknown",
            unit_file_state=raw.get("UnitFileState") or "unknown",
            nrestarts=nrestarts,
        )

    def snapshot(self) -> dict[str, UnitState]:
        return {unit: self.unit_state(unit) for unit in self.units}

    def quiesce(self) -> None:
        self.initial = self.snapshot()
        active_updaters = [
            unit for unit in self.update_services
            if self.initial.get(unit) is not None and self.initial[unit].was_active
        ]
        if active_updaters:
            raise TrialError("update service active; refusing to interrupt OTA operation")
        for unit in self.timers:
            self._run_systemctl(["stop", unit], timeout=30.0)
        for unit in self.update_services:
            if self.unit_state(unit).was_active:
                raise TrialError("update service started while timers were being stopped")
        self._run_systemctl(["stop", self.service], timeout=45.0)
        self.after_stop = self.snapshot()
        units_still_active = [
            unit for unit in [*self.timers, self.service]
            if self.after_stop.get(unit) is not None and self.after_stop[unit].was_active
        ]
        if units_still_active:
            raise TrialError("failed to quiesce player/timers before isolated trial")

    def restore(self) -> dict[str, Any]:
        restore_actions: list[str] = []
        for unit in [self.service, *self.timers]:
            initial = self.initial.get(unit)
            if initial is not None and initial.was_active:
                self._run_systemctl(["start", unit], timeout=45.0)
                restore_actions.append(unit)
        self.final = self.snapshot() if self.initial else {}
        return {
            "attempted": bool(self.initial),
            "started_units": restore_actions,
            "initial": {key: value.public() for key, value in self.initial.items()},
            "after_stop": {key: value.public() for key, value in self.after_stop.items()},
            "final": {key: value.public() for key, value in self.final.items()},
            "restored_active_state": self.restored_active_state(),
        }

    def restored_active_state(self) -> bool:
        if not self.initial or not self.final:
            return False
        for unit, initial in self.initial.items():
            final = self.final.get(unit)
            if final is None:
                return False
            if initial.was_active and final.active_state != "active":
                return False
            if not initial.was_active and final.active_state == "active":
                return False
        return True

    def nrestarts_delta(self) -> int:
        initial = self.initial.get(self.service)
        final = self.final.get(self.service)
        if initial is None or final is None or initial.nrestarts is None or final.nrestarts is None:
            return 0
        return max(final.nrestarts - initial.nrestarts, 0)


@dataclass
class MediaFixture:
    name: str
    path: Path
    duration_ms: int
    media_type: str


def run_checked(args: list[str], timeout: float, label: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise TrialError(f"{label} failed rc={completed.returncode}: {(completed.stderr or completed.stdout)[-500:]}")
    return completed


def generate_synthetic_media(media_dir: Path, ffmpeg_path: str) -> dict[str, MediaFixture]:
    media_dir.mkdir(parents=True, exist_ok=True)
    fixtures = {
        "mixed_a": MediaFixture("mixed_a", media_dir / "mixed-a.mp4", 1200, "video"),
        "mixed_png": MediaFixture("mixed_png", media_dir / "mixed-still.png", 1200, "image"),
        "mixed_b": MediaFixture("mixed_b", media_dir / "mixed-b.mp4", 1200, "video"),
        "sidecar_png": MediaFixture("sidecar_png", media_dir / "sidecar-rebuild.png", 1200, "image"),
        "recovery_a": MediaFixture("recovery_a", media_dir / "recovery-a.mp4", 1200, "video"),
        "recovery_b": MediaFixture("recovery_b", media_dir / "recovery-b.mp4", 1200, "video"),
    }
    video_specs = [
        (fixtures["mixed_a"].path, "testsrc2=size=1280x720:rate=30", 1.4),
        (fixtures["mixed_b"].path, "smptebars=size=1280x720:rate=30", 1.4),
        (fixtures["recovery_a"].path, "testsrc=size=1280x720:rate=30", 1.4),
        (fixtures["recovery_b"].path, "color=c=0x22cc88:s=1280x720:rate=30", 1.4),
    ]
    for path, lavfi, duration_sec in video_specs:
        run_checked(
            [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                lavfi,
                "-t",
                str(duration_sec),
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-movflags",
                "+faststart",
                str(path),
            ],
            timeout=45.0,
            label=f"generate {path.name}",
        )
    image_specs = [
        (fixtures["mixed_png"].path, "color=c=0xffcc00:s=1280x720"),
        (fixtures["sidecar_png"].path, "color=c=0xff3355:s=1280x720"),
    ]
    for path, lavfi in image_specs:
        run_checked(
            [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                lavfi,
                "-frames:v",
                "1",
                str(path),
            ],
            timeout=30.0,
            label=f"generate {path.name}",
        )
    return fixtures


def api_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    campaigns: list[dict[str, Any]] = []
    for item in items:
        campaigns.append(
            {
                "id": item.get("campaign_id") or alias(item["url"], "campaign"),
                "name": item.get("campaign_name") or alias(item["url"], "name"),
                "status": "active",
                "exposure_time_ms": int(item.get("duration_ms") or 1200),
                "media_urls": [item["url"]],
            }
        )
    return {"units": [{"campaigns": campaigns}]}


class LocalFixtureServer:
    def __init__(self, fixtures: dict[str, MediaFixture]) -> None:
        self.fixtures = fixtures
        self.lock = threading.Lock()
        self.mode = "mixed"
        self.requests: list[dict[str, Any]] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.base_url = ""
        self.media_routes: dict[str, Path] = {}
        self.truncated_body = b"not-a-complete-media"

    def start(self) -> None:
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _fmt: str, *_args: Any) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802
                server_ref.handle_post(self)

            def do_GET(self) -> None:  # noqa: N802
                server_ref.handle_get(self)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        host, port = self._server.server_address[:2]
        self.base_url = f"http://{host}:{port}"
        self.media_routes = {
            "/media/mixed-a.mp4": self.fixtures["mixed_a"].path,
            "/media/mixed-still.png": self.fixtures["mixed_png"].path,
            "/media/mixed-b.mp4": self.fixtures["mixed_b"].path,
            "/media/sidecar-rebuild.png": self.fixtures["sidecar_png"].path,
            "/media/recovery-a.mp4": self.fixtures["recovery_a"].path,
            "/media/recovery-b.mp4": self.fixtures["recovery_b"].path,
        }
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def set_mode(self, mode: str) -> None:
        with self.lock:
            self.mode = mode

    def route_url(self, route: str) -> str:
        return f"{self.base_url}{route}"

    def playlist_for_mode(self, mode: str) -> list[dict[str, Any]]:
        if mode == "mixed":
            return [
                self.item("/media/mixed-a.mp4", "mixed-a"),
                self.item("/media/mixed-still.png", "mixed-png"),
                self.item("/media/mixed-b.mp4", "mixed-b"),
            ]
        if mode == "empty_playlist":
            return []
        if mode == "truncated_download":
            return [self.item("/media/truncated.mp4", "truncated")]
        if mode == "sidecar_rebuild":
            return [self.item("/media/sidecar-rebuild.png", "sidecar-png")]
        if mode == "recovery":
            return [
                self.item("/media/recovery-a.mp4", "recovery-a"),
                self.item("/media/recovery-b.mp4", "recovery-b"),
            ]
        return []

    def item(self, route: str, name: str) -> dict[str, Any]:
        return {
            "url": self.route_url(route),
            "duration_ms": 1200,
            "campaign_id": f"c22-{name}",
            "campaign_name": f"c22-{name}",
        }

    def handle_post(self, handler: BaseHTTPRequestHandler) -> None:
        length = int(handler.headers.get("Content-Length", "0") or "0")
        if length:
            handler.rfile.read(length)
        with self.lock:
            mode = self.mode
        self.requests.append({"method": "POST", "path": handler.path, "mode": mode, "ts": utc_now()})
        if handler.path != "/api/search":
            handler.send_error(HTTPStatus.NOT_FOUND)
            return
        if mode == "api_500":
            payload = b'{"error":"injected"}\n'
            handler.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(payload)))
            handler.end_headers()
            handler.wfile.write(payload)
            return
        body = json.dumps(api_payload(self.playlist_for_mode(mode))).encode("utf-8")
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def handle_get(self, handler: BaseHTTPRequestHandler) -> None:
        self.requests.append({"method": "GET", "path": handler.path, "mode": self.mode, "ts": utc_now()})
        if handler.path == "/media/truncated.mp4":
            body = self.truncated_body
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "video/mp4")
            handler.send_header("Content-Length", str(len(body) + 1000))
            handler.end_headers()
            handler.wfile.write(body)
            return
        path = self.media_routes.get(handler.path)
        if path is None:
            handler.send_error(HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        content_type = "image/png" if path.suffix.lower() == ".png" else "video/mp4"
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    def public_request_summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for entry in self.requests:
            key = f"{entry['method']}:{entry['mode']}"
            counts[key] = counts.get(key, 0) + 1
        return {"counts": counts, "total": len(self.requests)}


def cache_path(cache_dir: Path, url: str) -> Path:
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix or ".bin"
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8'), usedforsecurity=False).hexdigest()}{ext}"


def prepopulate_corrupt_sidecar(cache_dir: Path, source_png: Path, url: str) -> dict[str, Any]:
    dest = cache_path(cache_dir, url)
    sidecar = Path(f"{dest}.h264.mp4")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_png, dest)
    sidecar.write_bytes(b"corrupt-sidecar-not-mp4")
    now = time.time()
    os.utime(dest, (now - 10, now - 10))
    os.utime(sidecar, (now, now))
    return {
        "source_alias": safe_path_alias(str(dest)),
        "sidecar_alias": safe_path_alias(str(sidecar)),
        "before_sha256": sha256_file(sidecar),
    }


def ffprobe_ok(path: Path, ffprobe_path: str, required_codec: str = "") -> bool:
    command = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,codec_name,width,height",
        "-of",
        "json",
        str(path),
    ]
    try:
        proc = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    except Exception:
        return False
    if proc.returncode != 0:
        return False
    try:
        payload = json.loads((proc.stdout or b"{}").decode("utf-8", "replace"))
    except Exception:
        return False
    streams = payload.get("streams") if isinstance(payload, dict) else None
    if not isinstance(streams, list):
        return False
    videos = [item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"]
    if not videos:
        return False
    if required_codec and not any(str(item.get("codec_name") or "") == required_codec for item in videos):
        return False
    return any(int(item.get("width") or 0) > 0 and int(item.get("height") or 0) > 0 for item in videos)


def first_frame_decode_ok(path: Path, ffmpeg_path: str) -> bool:
    try:
        proc = subprocess.run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-v",
                "error",
                "-xerror",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-f",
                "null",
                "-",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
    except Exception:
        return False
    return proc.returncode == 0


def build_trial_config(
    *,
    work_dir: Path,
    api_url: str,
    mpv_path: str,
    ffmpeg_path: str,
    ffprobe_path: str,
) -> dict[str, Any]:
    cfg = {
        "api_url": api_url,
        "api_key": "c22-local-fixture-key",
        "environment_id": "c22-local-fixture-env",
        "only_standby": True,
        "search_in": "campaign",
        "include_descendants": True,
        "limit": 20,
        "poll_interval_sec": 2,
        "request_timeout_sec": 2,
        "default_duration_ms": 1200,
        "cache_dir": str(work_dir / "cache"),
        "state_dir": str(work_dir / "state"),
        "offline_fallback": True,
        "offline_max_age_hours": 0,
        "offline_ignore_max_age_when_no_network": True,
        "require_full_download_before_switch": True,
        "allow_empty_playlist_from_api": False,
        "disable_cleanup_when_offline": True,
        "cache_max_files": 0,
        "cache_max_bytes": 0,
        "min_free_space_bytes": 0,
        "max_download_bytes": 64 * 1024 * 1024,
        "mpv_path": mpv_path,
        "mpv_log_file": str(work_dir / "mpv.log"),
        "mpv_msg_level": "",
        "mpv_ipc_timeout_sec": 1.0,
        "mpv_startup_timeout_sec": 10.0,
        "mpv_load_verify_timeout_sec": 2.0,
        "mpv_debug_events": True,
        "mpv_query_uses_fresh_ipc": True,
        "mpv_vo": "",
        "mpv_gpu_context": "",
        "mpv_ao": "",
        "ipc_path": str(work_dir / "ipc" / "mpv.sock"),
        "runtime_dir": str(work_dir / "runtime"),
        "strict_paths_enabled": False,
        "rotation_deg": 0,
        "hotkeys_enabled": False,
        "config_ui_enabled": False,
        "low_resource_mode": False,
        "telemetry_enabled": False,
        "telemetry_url": "http://127.0.0.1/disabled-telemetry",
        "telemetry_token": "",
        "station_id": "",
        "preload_next": False,
        "mute": True,
        "lock_input": True,
        "hwdec": "auto",
        "log_file": str(work_dir / "kiosk.log"),
        "watchdog_interval_sec": 2,
        "mpv_watchdog_ping_failures_before_restart": 2,
        "mpv_watchdog_grace_after_load_sec": 1,
        "mpv_watchdog_grace_after_restart_sec": 1,
        "media_load_retry_cooldown_sec": 5,
        "media_probe_enabled": True,
        "media_probe_ffprobe_path": ffprobe_path,
        "media_probe_ffmpeg_path": ffmpeg_path,
        "media_probe_timeout_sec": 15,
        "image_transcode_enabled": True,
        "image_transcode_ffmpeg_path": ffmpeg_path,
        "image_transcode_timeout_sec": 45,
        "tmp_max_age_sec": 3600,
        "status_file": str(work_dir / "kiosky-status.json"),
        "status_interval_sec": 1,
        "startup_feedback_enabled": False,
        "cleanup_interval_sec": 300,
        "sync_enabled": False,
        "sync_ntp_command": "",
    }
    for key in ("cache_dir", "state_dir", "ipc_path", "runtime_dir", "log_file", "mpv_log_file", "status_file"):
        if not path_is_under(Path(str(cfg[key])), TMP_ROOT):
            raise TrialError(f"temporary config path escaped /tmp: {key}")
    if not str(cfg["api_url"]).startswith("http://127.0.0.1:"):
        raise TrialError("api_url must be localhost-only")
    return cfg


def minimal_env(work_dir: Path) -> dict[str, str]:
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONUNBUFFERED": "1",
        "KIOSKY_TELEMETRY_TOKEN": "",
        "HOME": str(work_dir / "home"),
        "TMPDIR": str(work_dir / "tmp"),
        "XDG_RUNTIME_DIR": str(work_dir / "xdg-runtime"),
        "XDG_CONFIG_HOME": str(work_dir / "xdg-config"),
    }
    for key in ("HOME", "TMPDIR", "XDG_RUNTIME_DIR", "XDG_CONFIG_HOME"):
        Path(env[key]).mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(env[key], PRIVATE_DIR_MODE)
        except OSError:
            pass
    return env


def launch_kiosk(kiosk_path: Path, config_path: Path, work_dir: Path) -> subprocess.Popen[str]:
    stdout_path = work_dir / "kiosk-stdout.txt"
    stderr_path = work_dir / "kiosk-stderr.txt"
    stdout = stdout_path.open("w", encoding="utf-8")
    stderr = stderr_path.open("w", encoding="utf-8")
    try:
        return subprocess.Popen(
            [sys.executable, str(kiosk_path), "--config", str(config_path)],
            cwd=str(work_dir),
            env=minimal_env(work_dir),
            text=True,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
    finally:
        stdout.close()
        stderr.close()


def terminate_process(proc: subprocess.Popen[str] | None, timeout_sec: float = 35.0) -> dict[str, Any]:
    if proc is None:
        return {"method": "none", "returncode": None}
    if proc.poll() is not None:
        return {"method": "already_exited", "returncode": proc.poll()}
    started = time.monotonic()
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        proc.wait(timeout=timeout_sec)
        return {
            "method": "sigterm",
            "returncode": proc.poll(),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    try:
        proc.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return {"method": "sigkill_timeout", "returncode": proc.poll()}
    return {
        "method": "sigkill",
        "returncode": proc.poll(),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }


@dataclass
class SampleCollector:
    output_dir: Path
    status_path: Path
    ipc_path: Path
    ffmpeg_path: str
    scenario_getter: Callable[[], str]
    interval_sec: float = 1.0
    ipc_timeout_sec: float = 0.8
    kms_timeout_sec: float = 4.0
    stop_event: threading.Event = field(default_factory=threading.Event)
    kms_pause_event: threading.Event = field(default_factory=threading.Event)
    samples: list[dict[str, Any]] = field(default_factory=list)
    _thread: threading.Thread | None = None

    def start(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self.interval_sec + self.kms_timeout_sec + 2.0, 5.0))

    def _run(self) -> None:
        path = self.output_dir / "samples.ndjson"
        seq = 0
        started = time.monotonic()
        while not self.stop_event.is_set():
            sample_start = time.monotonic()
            seq += 1
            scenario_name = self.scenario_getter()
            raw_status = raw_status_for_private_local_status(self.status_path)
            status = sanitize_status(raw_status)
            ipc_raw = ipc_query_many(self.ipc_path, self.ipc_timeout_sec)
            ipc = sanitize_ipc(ipc_raw)
            kms = (
                {"result": "covered_by_continuous_capture", "error": ""}
                if self.kms_pause_event.is_set()
                else kms_capture(self.ffmpeg_path, timeout_sec=self.kms_timeout_sec)
            )
            sample = {
                "seq": seq,
                "rel_sec": round(sample_start - started, 3),
                "utc": utc_now(),
                "scenario": scenario_name,
                "status": status,
                "ipc": ipc,
                "kms": kms,
            }
            assert_public_json_safe(sample)
            self.samples.append(sample)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(compact_json(sample) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            fsync_dir(path.parent)
            while not self.stop_event.is_set() and time.monotonic() - sample_start < self.interval_sec:
                time.sleep(min(0.1, self.interval_sec - (time.monotonic() - sample_start)))


@dataclass
class ScenarioController:
    current: str = "setup"
    lock: threading.Lock = field(default_factory=threading.Lock)

    def set(self, name: str) -> None:
        with self.lock:
            self.current = name

    def get(self) -> str:
        with self.lock:
            return self.current


def latest_status(status_path: Path) -> dict[str, Any]:
    return sanitize_status(raw_status_for_private_local_status(status_path))


def wait_for_condition(
    name: str,
    status_path: Path,
    predicate: Callable[[dict[str, Any]], bool],
    timeout_sec: float,
) -> tuple[bool, dict[str, Any]]:
    deadline = time.monotonic() + timeout_sec
    last = latest_status(status_path)
    while time.monotonic() < deadline:
        last = latest_status(status_path)
        if predicate(last):
            return True, last
        time.sleep(0.5)
    return False, last


def collect_post_restore_health(
    systemd: SystemdController,
    status_mtime_before: int,
    ffmpeg_path: str,
    timeout_sec: float = 60.0,
) -> dict[str, Any]:
    initial_service = systemd.initial.get(systemd.service)
    if initial_service is None or not initial_service.was_active:
        return {"passed": True, "expected_running": False, "reason": "service_initially_inactive"}

    deadline = time.monotonic() + timeout_sec
    fresh_status = False
    active = False
    status = latest_status(DEFAULT_STATUS_FILE)
    ipc = sanitize_ipc({"result": "error", "error": "not_collected", "values": {}, "prop_errors": {}})
    kms: dict[str, Any] = {"result": "error", "error": "not_collected"}
    while time.monotonic() < deadline:
        active = systemd.unit_state(systemd.service).was_active
        try:
            fresh_status = DEFAULT_STATUS_FILE.stat().st_mtime_ns > status_mtime_before
        except OSError:
            fresh_status = False
        status = latest_status(DEFAULT_STATUS_FILE)
        if active and fresh_status and playing_with_playlist(status, 1) and status.get("mpv_running") is True:
            ipc = sanitize_ipc(ipc_query_many(DEFAULT_REAL_IPC_PATH, 1.5))
            if ipc.get("result") == "success":
                kms = kms_capture(ffmpeg_path, timeout_sec=5.0)
                if kms.get("result") == "success":
                    break
        time.sleep(1.0)
    passed = (
        active
        and fresh_status
        and playing_with_playlist(status, 1)
        and status.get("mpv_running") is True
        and ipc.get("result") == "success"
        and kms.get("result") == "success"
    )
    return {
        "passed": passed,
        "expected_running": True,
        "service_active": active,
        "status_fresh": fresh_status,
        "status": status,
        "ipc": ipc,
        "kms": kms,
    }


def status_state_is(expected: str) -> Callable[[dict[str, Any]], bool]:
    def _predicate(status: dict[str, Any]) -> bool:
        return status.get("playlist_update_state") == expected
    return _predicate


def retaining_lkg_state_is(expected: str) -> Callable[[dict[str, Any]], bool]:
    def _predicate(status: dict[str, Any]) -> bool:
        return (
            status.get("playlist_update_state") == expected
            and playing_with_playlist(status, 1)
            and status.get("mpv_running") is True
        )
    return _predicate


def playing_with_playlist(status: dict[str, Any], min_size: int = 1) -> bool:
    return (
        status.get("playback_state") == "playing"
        and status.get("first_frame_ready") is True
        and int(status.get("playlist_size") or 0) >= min_size
        and bool((status.get("current_item") or {}).get("path_alias"))
    )


def scenario_samples(samples: list[dict[str, Any]], scenario: str) -> list[dict[str, Any]]:
    return [sample for sample in samples if sample.get("scenario") == scenario]


def sample_status_alias(sample: dict[str, Any]) -> str:
    status = sample.get("status") if isinstance(sample.get("status"), dict) else {}
    item = status.get("current_item") if isinstance(status.get("current_item"), dict) else {}
    return str(item.get("path_alias") or item.get("alias") or "")


def sample_mpv_alias(sample: dict[str, Any]) -> str:
    ipc = sample.get("ipc") if isinstance(sample.get("ipc"), dict) else {}
    return str(ipc.get("path_alias") or ipc.get("filename_alias") or "")


def count_alias_changes(aliases: list[str]) -> int:
    changes = 0
    prev = ""
    for item in aliases:
        if not item:
            continue
        if prev and item != prev:
            changes += 1
        prev = item
    return changes


def final_status_by_scenario(samples: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for sample in samples:
        scenario = str(sample.get("scenario") or "")
        if not scenario:
            continue
        status = sample.get("status") if isinstance(sample.get("status"), dict) else {}
        result[scenario] = status
    return result


def evaluate_trial(
    *,
    samples: list[dict[str, Any]],
    scenario_results: dict[str, Any],
    systemd: SystemdController,
    restoration: dict[str, Any],
    forbidden_before: dict[str, Any],
    forbidden_after: dict[str, Any],
    sidecar: dict[str, Any],
    process_stop: dict[str, Any],
    post_restore_health: dict[str, Any],
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    counters: dict[str, Any] = {}
    warnings: list[str] = []
    final_by_scenario = final_status_by_scenario(samples)
    condition_by_scenario: dict[str, dict[str, Any]] = {}
    for scenario, result in scenario_results.items():
        if not isinstance(result, dict):
            continue
        condition_status = result.get("condition_status")
        final_status = result.get("final_status")
        if isinstance(condition_status, dict):
            condition_by_scenario[scenario] = condition_status
        if isinstance(final_status, dict):
            final_by_scenario[scenario] = final_status

    mixed = scenario_samples(samples, "mixed")
    mixed_status_aliases = [sample_status_alias(sample) for sample in mixed if playing_with_playlist(sample.get("status", {}), 3)]
    mixed_mpv_aliases = [
        sample_mpv_alias(sample)
        for sample in mixed
        if sample.get("ipc", {}).get("result") == "success" and sample_mpv_alias(sample)
    ]
    counters["mixed_status_unique_aliases"] = len(set(mixed_status_aliases))
    counters["mixed_mpv_unique_aliases"] = len(set(mixed_mpv_aliases))
    counters["mixed_mpv_alias_changes"] = count_alias_changes(mixed_mpv_aliases)
    mixed_result = scenario_results.get("mixed") if isinstance(scenario_results.get("mixed"), dict) else {}
    mixed_continuous_kms = (
        mixed_result.get("continuous_kms")
        if isinstance(mixed_result.get("continuous_kms"), dict)
        else {}
    )
    mixed_sample_kms_hashes = {
        sample.get("kms", {}).get("sha256")
        for sample in mixed
        if sample.get("kms", {}).get("result") == "success" and sample.get("kms", {}).get("sha256")
    }
    continuous_kms_ok = mixed_continuous_kms.get("result") == "success"
    counters["mixed_kms_unique_hashes"] = (
        int(mixed_continuous_kms.get("unique_frame_hashes") or 0)
        if continuous_kms_ok
        else len(mixed_sample_kms_hashes)
    )
    counters["mixed_kms_black_frames"] = (
        int(mixed_continuous_kms.get("black_frames") or 0) if continuous_kms_ok else None
    )
    counters["mixed_kms_max_black_duration_ms"] = (
        int(mixed_continuous_kms.get("max_black_duration_ms") or 0) if continuous_kms_ok else None
    )
    checks["mixed_three_aliases_observed"] = counters["mixed_status_unique_aliases"] >= 3 or counters["mixed_mpv_unique_aliases"] >= 3
    checks["mixed_transitions_observed"] = counters["mixed_mpv_alias_changes"] >= 3 or count_alias_changes(mixed_status_aliases) >= 3
    checks["mixed_visual_changes_observed"] = counters["mixed_kms_unique_hashes"] >= 3
    if continuous_kms_ok:
        checks["mixed_continuous_kms_frame_delivery"] = int(mixed_continuous_kms.get("frames") or 0) >= 100
        checks["mixed_continuous_kms_no_visible_black_run"] = (
            int(mixed_continuous_kms.get("max_black_duration_ms") or 0) < 100
        )
    elif mixed_continuous_kms:
        warnings.append("continuous_kms_unavailable_across_drm_format_change")

    comparable = 0
    mismatches = 0
    mismatch_streak = 0
    max_mismatch_streak = 0
    previous_scenario = ""
    for sample in samples:
        if sample.get("scenario") not in VALID_MEDIA_SCENARIOS:
            continue
        scenario_name = str(sample.get("scenario") or "")
        if scenario_name != previous_scenario:
            mismatch_streak = 0
            previous_scenario = scenario_name
        status = sample.get("status") if isinstance(sample.get("status"), dict) else {}
        if status.get("playback_state") != "playing":
            continue
        status_alias = sample_status_alias(sample)
        mpv_alias = sample_mpv_alias(sample)
        if not status_alias or not mpv_alias:
            continue
        comparable += 1
        if status_alias != mpv_alias:
            mismatches += 1
            mismatch_streak += 1
            max_mismatch_streak = max(max_mismatch_streak, mismatch_streak)
        else:
            mismatch_streak = 0
    counters["status_mpv_comparable_samples"] = comparable
    counters["status_mpv_mismatch_samples"] = mismatches
    counters["status_mpv_max_consecutive_mismatch"] = max_mismatch_streak
    valid_mpv_transitions = 0
    for scenario_name in VALID_MEDIA_SCENARIOS:
        aliases = [
            sample_mpv_alias(sample)
            for sample in scenario_samples(samples, scenario_name)
            if sample.get("ipc", {}).get("result") == "success" and sample_mpv_alias(sample)
        ]
        valid_mpv_transitions += count_alias_changes(aliases)
    counters["status_mpv_valid_transitions"] = valid_mpv_transitions
    transition_allowance = min(
        valid_mpv_transitions + 2,
        max(
            MAX_STATUS_MPV_MISMATCH_SAMPLES,
            math.ceil(comparable * MAX_STATUS_MPV_MISMATCH_CEILING_RATIO),
        ),
    )
    mismatch_allowed = max(
        MAX_STATUS_MPV_MISMATCH_SAMPLES,
        int(comparable * MAX_STATUS_MPV_MISMATCH_RATIO),
        transition_allowance,
    )
    counters["status_mpv_mismatch_allowed"] = mismatch_allowed
    counters["status_mpv_mismatch_ceiling"] = math.ceil(
        comparable * MAX_STATUS_MPV_MISMATCH_CEILING_RATIO
    )
    checks["status_mpv_aligned"] = comparable > 0 and mismatches <= mismatch_allowed
    checks["status_mpv_mismatch_recovers_quickly"] = comparable > 0 and max_mismatch_streak <= 2

    valid_kms_samples = []
    black_kms_samples = []
    max_black_sample_streak = 0
    black_sample_streak = 0
    previous_kms_scenario = ""
    for sample in samples:
        if sample.get("scenario") not in VALID_MEDIA_SCENARIOS:
            continue
        status = sample.get("status") if isinstance(sample.get("status"), dict) else {}
        if status.get("playback_state") != "playing" or status.get("first_frame_ready") is not True:
            continue
        kms = sample.get("kms") if isinstance(sample.get("kms"), dict) else {}
        if kms.get("result") == "success":
            valid_kms_samples.append(sample)
            scenario_name = str(sample.get("scenario") or "")
            if scenario_name != previous_kms_scenario:
                black_sample_streak = 0
                previous_kms_scenario = scenario_name
            if kms.get("raw_black") is True:
                black_kms_samples.append(sample)
                black_sample_streak += 1
                max_black_sample_streak = max(max_black_sample_streak, black_sample_streak)
            else:
                black_sample_streak = 0
    counters["kms_success_valid_media_samples"] = len(valid_kms_samples)
    counters["kms_raw_black_valid_media_samples"] = len(black_kms_samples)
    counters["kms_max_consecutive_raw_black_samples"] = max_black_sample_streak
    checks["kms_present_when_valid_media"] = len(valid_kms_samples) > 0
    checks["no_persistent_raw_black_samples"] = max_black_sample_streak <= 1
    if black_kms_samples:
        warnings.append("isolated_raw_black_sample_requires_hdmi_or_optical_confirmation")

    expected_fault_states = {
        "api_500": ("api_error_retaining_last_known_good", "api_error"),
        "empty_playlist": ("api_empty_retaining_last_known_good", "api_empty_playlist"),
        "truncated_download": ("download_incomplete_retaining_last_known_good", "playlist_download_incomplete"),
    }
    for scenario, (state, reason) in expected_fault_states.items():
        observed = condition_by_scenario.get(scenario, final_by_scenario.get(scenario, {}))
        fault_samples = scenario_samples(samples, scenario)
        checks[f"{scenario}_explicit_retaining_lkg_status"] = (
            observed.get("playlist_update_state") == state
            and observed.get("content_stale") is True
            and observed.get("content_stale_reason") == reason
        )
        checks[f"{scenario}_not_false_playlist_applied"] = observed.get("playlist_update_state") != "playlist_applied"
        checks[f"{scenario}_lkg_playback_remains_active"] = (
            playing_with_playlist(observed, 1)
            and observed.get("mpv_running") is True
            and bool((observed.get("current_item") or {}).get("path_alias"))
        )
        checks[f"{scenario}_lkg_ipc_and_kms_observed"] = any(
            sample.get("ipc", {}).get("result") == "success"
            and sample.get("kms", {}).get("result") == "success"
            and sample.get("kms", {}).get("raw_black") is not True
            for sample in fault_samples
        )

    checks["sidecar_rebuilt"] = (
        bool(sidecar.get("rebuilt"))
        and bool(sidecar.get("ffprobe_h264_ok"))
        and bool(sidecar.get("first_frame_decode_ok"))
    )
    recovery = condition_by_scenario.get("recovery", final_by_scenario.get("recovery", {}))
    checks["recovery_playlist_valid"] = (
        recovery.get("playlist_update_state") in {"playlist_applied", "playlist_unchanged"}
        and recovery.get("content_stale") is False
        and playing_with_playlist(recovery, 2)
    )
    checks["kiosk_process_stopped"] = process_stop.get("method") in {"already_exited", "sigterm", "sigkill"} and process_stop.get("method") != "sigkill_timeout"
    checks["systemd_nrestarts_stable"] = systemd.nrestarts_delta() == 0
    checks["systemd_restored_final"] = bool(restoration.get("restored_active_state"))
    checks["production_player_healthy_after_restore"] = bool(post_restore_health.get("passed"))
    checks["protected_path_identity_unchanged"] = protected_metadata_unchanged(
        forbidden_before,
        forbidden_after,
    )

    for key, value in scenario_results.items():
        if isinstance(value, dict) and "condition_met" in value:
            checks[f"{key}_condition_met"] = bool(value["condition_met"])

    failure_reasons = [key for key, passed in checks.items() if not passed]
    return {
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
        "warnings": warnings,
        "checks": checks,
        "counters": counters,
    }


def public_initial_snapshot(systemd: SystemdController) -> dict[str, Any]:
    status_raw = raw_status_for_private_local_status(DEFAULT_STATUS_FILE)
    return {
        "collected_at_utc": utc_now(),
        "real_config_content_read": False,
        "forbidden_paths_stat_only": {alias(str(path), "path"): stat_public(path) for path in FORBIDDEN_PATHS},
        "production_status_public": sanitize_status(status_raw),
        "unit_state_before_quiesce": {key: value.public() for key, value in systemd.initial.items()},
    }


def forbidden_metadata_snapshot() -> dict[str, Any]:
    return {alias(str(path), "path"): stat_public(path) for path in FORBIDDEN_PATHS}


def protected_metadata_unchanged(before: dict[str, Any], after: dict[str, Any]) -> bool:
    operational_aliases = {alias(str(path), "path") for path in OPERATIONAL_MTIME_PATHS}

    def normalized(snapshot: dict[str, Any]) -> dict[str, Any]:
        result = json.loads(json.dumps(snapshot))
        for path_alias in operational_aliases:
            entry = result.get(path_alias)
            if isinstance(entry, dict):
                entry.pop("mtime_ns", None)
        return result

    return normalized(before) == normalized(after)


def scenario_summary(
    condition_met: bool,
    condition_status: dict[str, Any],
    final_status: dict[str, Any],
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    return {
        "condition_met": condition_met,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "condition_status": condition_status,
        "final_status": final_status,
    }


def run_trial(args: argparse.Namespace) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise TrialError("real board trial must run as root; use --self-test off-board")
    kiosk_path = Path(args.kiosk_path).expanduser().resolve(strict=True)
    output_dir = require_tmp_output_dir(args.output_dir or (TMP_ROOT / f"c22-rapid-media-fault-trial-{int(time.time())}"))
    output_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(output_dir, PRIVATE_DIR_MODE)
    work_dir = output_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(work_dir, PRIVATE_DIR_MODE)

    systemd = SystemdController(args.service, args.timers)
    server: LocalFixtureServer | None = None
    collector: SampleCollector | None = None
    proc: subprocess.Popen[str] | None = None
    scenario = ScenarioController()
    errors: list[str] = []
    scenario_results: dict[str, Any] = {}
    sidecar_report: dict[str, Any] = {}
    process_stop: dict[str, Any] = {"method": "none", "returncode": None}
    restoration: dict[str, Any] = {"attempted": False, "restored_active_state": False}
    post_restore_health: dict[str, Any] = {"passed": False, "reason": "not_collected"}
    forbidden_before = forbidden_metadata_snapshot()
    started = utc_now()

    def _handle_signal(sig: int, _frame: Any) -> None:
        errors.append(f"signal:{sig}")
        raise KeyboardInterrupt

    previous_handlers = {
        signal.SIGINT: signal.getsignal(signal.SIGINT),
        signal.SIGTERM: signal.getsignal(signal.SIGTERM),
    }
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    try:
        fixtures = generate_synthetic_media(work_dir / "fixture-media", args.ffmpeg_path)
        server = LocalFixtureServer(fixtures)
        server.start()
        cfg = build_trial_config(
            work_dir=work_dir,
            api_url=f"{server.base_url}/api/search",
            mpv_path=args.mpv_path,
            ffmpeg_path=args.ffmpeg_path,
            ffprobe_path=args.ffprobe_path,
        )
        for key in ("cache_dir", "state_dir", "runtime_dir", "ipc_path"):
            Path(str(cfg[key])).parent.mkdir(parents=True, exist_ok=True)
        write_json_private(work_dir / "trial-config.json", cfg)
        production_status_mtime_before = (
            DEFAULT_STATUS_FILE.stat().st_mtime_ns if DEFAULT_STATUS_FILE.is_file() else 0
        )
        systemd.quiesce()
        initial_snapshot = public_initial_snapshot(systemd)
        proc = launch_kiosk(kiosk_path, work_dir / "trial-config.json", work_dir)
        collector = SampleCollector(
            output_dir=output_dir,
            status_path=Path(str(cfg["status_file"])),
            ipc_path=Path(str(cfg["ipc_path"])),
            ffmpeg_path=args.ffmpeg_path,
            scenario_getter=scenario.get,
            interval_sec=args.sample_interval_sec,
            ipc_timeout_sec=args.ipc_timeout_sec,
            kms_timeout_sec=args.kms_timeout_sec,
        )
        collector.start()

        def run_named(
            name: str,
            mode: str,
            predicate: Callable[[dict[str, Any]], bool],
            timeout: float,
            hold_sec: float = 1.0,
            continuous_kms_sec: float = 0.0,
        ) -> dict[str, Any]:
            scenario.set(name)
            assert server is not None
            server.set_mode(mode)
            started_at = utc_now()
            ok, status = wait_for_condition(name, Path(str(cfg["status_file"])), predicate, timeout)
            continuous_kms: dict[str, Any] = {}
            if ok and continuous_kms_sec > 0:
                assert collector is not None
                collector.kms_pause_event.set()
                try:
                    continuous_kms = kms_capture_sequence(args.ffmpeg_path, continuous_kms_sec)
                finally:
                    collector.kms_pause_event.clear()
            if not continuous_kms or continuous_kms.get("result") != "success":
                # Leave at least one post-condition sample in the scenario bucket.
                time.sleep(max(hold_sec, args.sample_interval_sec, 1.0))
            result = scenario_summary(
                ok,
                status,
                latest_status(Path(str(cfg["status_file"]))),
                started_at,
                utc_now(),
            )
            if continuous_kms:
                result["continuous_kms"] = continuous_kms
            scenario_results[name] = result
            return result

        run_named(
            "mixed",
            "mixed",
            lambda status: (
                playing_with_playlist(status, 3)
                and status.get("playlist_update_state") in {"playlist_applied", "playlist_unchanged"}
                and status.get("content_stale") is False
            ),
            args.mixed_timeout_sec,
            hold_sec=12.0,
            continuous_kms_sec=12.0,
        )

        run_named(
            "api_500",
            "api_500",
            retaining_lkg_state_is("api_error_retaining_last_known_good"),
            args.fault_timeout_sec,
        )
        run_named(
            "empty_playlist",
            "empty_playlist",
            retaining_lkg_state_is("api_empty_retaining_last_known_good"),
            args.fault_timeout_sec,
        )
        run_named(
            "truncated_download",
            "truncated_download",
            retaining_lkg_state_is("download_incomplete_retaining_last_known_good"),
            args.fault_timeout_sec,
        )

        assert server is not None
        sidecar_url = server.route_url("/media/sidecar-rebuild.png")
        sidecar_report = prepopulate_corrupt_sidecar(Path(str(cfg["cache_dir"])), fixtures["sidecar_png"].path, sidecar_url)
        sidecar_path = Path(f"{cache_path(Path(str(cfg['cache_dir'])), sidecar_url)}.h264.mp4")
        run_named(
            "sidecar_rebuild",
            "sidecar_rebuild",
            lambda status: (
                playing_with_playlist(status, 1)
                and int(status.get("playlist_size") or 0) == 1
                and status.get("playlist_update_state") in {"playlist_applied", "playlist_unchanged"}
                and status.get("content_stale") is False
            ),
            args.sidecar_timeout_sec,
            hold_sec=2.0,
        )
        after_sha = sha256_file(sidecar_path) if sidecar_path.exists() else ""
        sidecar_report.update(
            {
                "after_sha256": after_sha,
                "rebuilt": bool(after_sha and after_sha != sidecar_report.get("before_sha256")),
                "ffprobe_h264_ok": ffprobe_ok(sidecar_path, args.ffprobe_path, required_codec="h264"),
                "first_frame_decode_ok": first_frame_decode_ok(sidecar_path, args.ffmpeg_path),
            }
        )

        run_named(
            "recovery",
            "recovery",
            lambda status: (
                playing_with_playlist(status, 2)
                and int(status.get("playlist_size") or 0) == 2
                and status.get("playlist_update_state") in {"playlist_applied", "playlist_unchanged"}
                and status.get("content_stale") is False
            ),
            args.recovery_timeout_sec,
            hold_sec=5.0,
        )
    except KeyboardInterrupt:
        errors.append("interrupted")
    except Exception as exc:
        errors.append(type(exc).__name__)
    finally:
        scenario.set("teardown")
        if collector is not None:
            collector.stop()
        process_stop = terminate_process(proc)
        if server is not None:
            server.stop()
        restoration = systemd.restore()
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)

    post_restore_health = collect_post_restore_health(
        systemd,
        production_status_mtime_before if "production_status_mtime_before" in locals() else 0,
        args.ffmpeg_path,
    )

    forbidden_after = forbidden_metadata_snapshot()
    samples = collector.samples if collector is not None else []
    evaluation = evaluate_trial(
        samples=samples,
        scenario_results=scenario_results,
        systemd=systemd,
        restoration=restoration,
        forbidden_before=forbidden_before,
        forbidden_after=forbidden_after,
        sidecar=sidecar_report,
        process_stop=process_stop,
        post_restore_health=post_restore_health,
    )
    report = {
        "schema": SCHEMA,
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "passed": bool(evaluation.get("passed")) and not errors,
        "failure_reasons": list(evaluation.get("failure_reasons") or []) + (["trial_errors_present"] if errors else []),
        "warnings": list(evaluation.get("warnings") or []),
        "errors": errors,
        "snapshot": {
            "kiosk_path_alias": safe_path_alias(str(kiosk_path)),
            "kiosk_py_sha256": sha256_file(kiosk_path),
            "mpv_path_alias": safe_path_alias(args.mpv_path),
            "public_initial": initial_snapshot if "initial_snapshot" in locals() else {},
            "forbidden_before": forbidden_before,
            "forbidden_after": forbidden_after,
        },
        "isolation": {
            "output_dir_alias": safe_path_alias(str(output_dir)),
            "work_dir_alias": safe_path_alias(str(work_dir)),
            "real_config_content_read": False,
            "backend": "127.0.0.1 fixture only",
            "data_mutation_policy": "candidate_tmp_only; restored services may update operational timestamps",
        },
        "systemd": {
            "service": args.service,
            "timers": args.timers,
            "restoration": restoration,
            "post_restore_health": post_restore_health,
            "nrestarts_delta": systemd.nrestarts_delta(),
            "actions": systemd.actions,
        },
        "http_fixture": server.public_request_summary() if server is not None else {},
        "scenario_results": scenario_results,
        "sidecar": sidecar_report,
        "process_stop": process_stop,
        "evaluation": evaluation,
        "artifacts": {
            "samples": "samples.ndjson",
            "report": "c22_rapid_media_fault_trial_report.json",
        },
    }
    assert_public_json_safe(report)
    write_json_private(output_dir / "c22_rapid_media_fault_trial_report.json", report)
    return report


class FakeSystemctlRunner:
    def __init__(self) -> None:
        self.states = {
            DEFAULT_TIMERS[0]: UnitState(DEFAULT_TIMERS[0], active_state="active", sub_state="waiting", load_state="loaded", unit_file_state="enabled", nrestarts=None),
            DEFAULT_TIMERS[1]: UnitState(DEFAULT_TIMERS[1], active_state="inactive", sub_state="dead", load_state="loaded", unit_file_state="enabled", nrestarts=None),
            DEFAULT_SERVICE: UnitState(DEFAULT_SERVICE, active_state="active", sub_state="running", load_state="loaded", unit_file_state="enabled", nrestarts=7),
        }
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], _timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if args[:2] == ["systemctl", "show"]:
            unit = args[2]
            state = self.states.get(unit, UnitState(unit))
            lines = [
                f"ActiveState={state.active_state}",
                f"SubState={state.sub_state}",
                f"LoadState={state.load_state}",
                f"UnitFileState={state.unit_file_state}",
            ]
            if state.nrestarts is not None:
                lines.append(f"NRestarts={state.nrestarts}")
            return subprocess.CompletedProcess(args, 0, "\n".join(lines) + "\n", "")
        if args[:2] == ["systemctl", "stop"]:
            unit = args[2]
            if unit in self.states:
                self.states[unit].active_state = "inactive"
                self.states[unit].sub_state = "dead"
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:2] == ["systemctl", "start"]:
            unit = args[2]
            if unit in self.states:
                self.states[unit].active_state = "active"
                self.states[unit].sub_state = "running" if unit.endswith(".service") else "waiting"
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")


def self_test_payload() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    with tempfile.TemporaryDirectory(prefix="c22-rapid-self-test-", dir="/tmp") as tmp:
        root = Path(tmp)
        try:
            checks["output_dir_accepts_tmp"] = require_tmp_output_dir(root / "out").is_absolute()
        except Exception:
            checks["output_dir_accepts_tmp"] = False
        try:
            require_tmp_output_dir("/data/not-allowed")
            checks["output_dir_rejects_data"] = False
        except TrialError:
            checks["output_dir_rejects_data"] = True

        cfg = build_trial_config(
            work_dir=root / "work",
            api_url="http://127.0.0.1:12345/api/search",
            mpv_path=DEFAULT_MPV_PATH,
            ffmpeg_path="/usr/bin/ffmpeg",
            ffprobe_path="/usr/bin/ffprobe",
        )
        checks["config_uses_tmp_paths"] = all(
            path_is_under(Path(str(cfg[key])), TMP_ROOT)
            for key in ("cache_dir", "state_dir", "ipc_path", "runtime_dir", "status_file", "log_file", "mpv_log_file")
        )
        checks["config_uses_localhost_api"] = str(cfg["api_url"]).startswith("http://127.0.0.1:")
        checks["config_disables_real_backend_and_telemetry"] = cfg["telemetry_enabled"] is False and cfg["config_ui_enabled"] is False

        fake_runner = FakeSystemctlRunner()
        controller = SystemdController(DEFAULT_SERVICE, list(DEFAULT_TIMERS), runner=fake_runner)
        controller.quiesce()
        restoration = controller.restore()
        checks["systemd_restore_active_state"] = bool(restoration["restored_active_state"])
        checks["systemd_stops_timers_and_service"] = (
            ["systemctl", "stop", DEFAULT_TIMERS[0]] in fake_runner.calls
            and ["systemctl", "stop", DEFAULT_TIMERS[1]] in fake_runner.calls
            and ["systemctl", "stop", DEFAULT_SERVICE] in fake_runner.calls
        )
        checks["systemd_starts_only_previously_active_units"] = (
            ["systemctl", "start", DEFAULT_SERVICE] in fake_runner.calls
            and ["systemctl", "start", DEFAULT_TIMERS[0]] in fake_runner.calls
            and ["systemctl", "start", DEFAULT_TIMERS[1]] not in fake_runner.calls
        )

        samples = make_self_test_samples()
        scenario_results = {
            name: {"condition_met": True}
            for name in ("mixed", "api_500", "empty_playlist", "truncated_download", "sidecar_rebuild", "recovery")
        }
        scenario_results["mixed"]["continuous_kms"] = {
            "result": "success",
            "frames": 120,
            "unique_frame_hashes": 3,
            "black_frames": 0,
            "max_black_duration_ms": 0,
        }
        sidecar = {"rebuilt": True, "ffprobe_h264_ok": True, "first_frame_decode_ok": True}
        evaluation = evaluate_trial(
            samples=samples,
            scenario_results=scenario_results,
            systemd=controller,
            restoration=restoration,
            forbidden_before={"path-a": {"exists": False}},
            forbidden_after={"path-a": {"exists": False}},
            sidecar=sidecar,
            process_stop={"method": "sigterm", "returncode": 0},
            post_restore_health={"passed": True},
        )
        details["evaluation"] = evaluation
        checks["evaluation_contract_passes"] = bool(evaluation.get("passed"))
        unsafe = {"leak": "/data/config/config.json", "url": "https://api.example.invalid/search"}
        try:
            assert_public_json_safe(unsafe)
            checks["privacy_scan_blocks_private_report"] = False
        except PrivacyError:
            checks["privacy_scan_blocks_private_report"] = True

    failure_reasons = [key for key, passed in checks.items() if not passed]
    return {
        "schema": SELF_TEST_SCHEMA,
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
        "checks": checks,
        "details": details,
    }


def make_self_test_samples() -> list[dict[str, Any]]:
    def status(alias_value: str, *, playlist_size: int, update_state: str = "playlist_applied", stale: bool = False, reason: str | None = None) -> dict[str, Any]:
        return {
            "present": True,
            "playback_state": "playing",
            "player_state": "playing",
            "content_state": "playing",
            "playlist_size": playlist_size,
            "playlist_update_state": update_state,
            "content_stale": stale,
            "content_stale_reason": reason,
            "first_frame_ready": True,
            "mpv_running": True,
            "current_item": {"path_alias": alias_value, "alias": alias_value},
        }

    def sample(seq: int, scenario: str, alias_value: str, status_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "seq": seq,
            "rel_sec": float(seq),
            "utc": utc_now(),
            "scenario": scenario,
            "status": status_payload,
            "ipc": {"result": "success", "path_alias": alias_value, "hwdec_current": "v4l2request-copy"},
            "kms": {"result": "success", "luma_avg": 80.0, "raw_black": False, "sha256": alias_value},
        }

    samples: list[dict[str, Any]] = []
    aliases = ["<path:a>", "<path:b>", "<path:c>", "<path:a>", "<path:b>", "<path:c>"]
    for index, alias_value in enumerate(aliases, start=1):
        samples.append(sample(index, "mixed", alias_value, status(alias_value, playlist_size=3)))
    fault_statuses = {
        "api_500": status("<path:a>", playlist_size=3, update_state="api_error_retaining_last_known_good", stale=True, reason="api_error"),
        "empty_playlist": status("<path:a>", playlist_size=3, update_state="api_empty_retaining_last_known_good", stale=True, reason="api_empty_playlist"),
        "truncated_download": status("<path:a>", playlist_size=3, update_state="download_incomplete_retaining_last_known_good", stale=True, reason="playlist_download_incomplete"),
    }
    seq = len(samples) + 1
    for scenario, payload in fault_statuses.items():
        samples.append(sample(seq, scenario, "<path:a>", payload))
        seq += 1
    samples.append(sample(seq, "sidecar_rebuild", "<path:sidecar>", status("<path:sidecar>", playlist_size=1)))
    seq += 1
    for alias_value in ("<path:r1>", "<path:r2>"):
        samples.append(sample(seq, "recovery", alias_value, status(alias_value, playlist_size=2)))
        seq += 1
    return samples


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run off-board parser/contract/restoration checks")
    parser.add_argument("--output-dir", type=Path, help="dedicated output directory below /tmp")
    parser.add_argument("--kiosk-path", type=Path, default=DEFAULT_KIOSK_PATH, help="kiosk.py to execute")
    parser.add_argument("--mpv-path", default=DEFAULT_MPV_PATH, help="C18 MPV wrapper path")
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--timer", dest="timers", action="append", help="systemd timer to stop/restore; repeat twice")
    parser.add_argument("--ffmpeg-path", default="/usr/bin/ffmpeg")
    parser.add_argument("--ffprobe-path", default="/usr/bin/ffprobe")
    parser.add_argument("--sample-interval-sec", type=float, default=1.0)
    parser.add_argument("--ipc-timeout-sec", type=float, default=0.8)
    parser.add_argument("--kms-timeout-sec", type=float, default=4.0)
    parser.add_argument("--mixed-timeout-sec", type=float, default=35.0)
    parser.add_argument("--fault-timeout-sec", type=float, default=18.0)
    parser.add_argument("--sidecar-timeout-sec", type=float, default=25.0)
    parser.add_argument("--recovery-timeout-sec", type=float, default=25.0)
    parser.add_argument("--json", action="store_true", help="print report JSON")
    args = parser.parse_args(argv)
    if args.timers is None:
        args.timers = list(DEFAULT_TIMERS)
    if len(args.timers) != 2:
        parser.error("exactly two --timer values are required when overriding defaults")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        payload = self_test_payload()
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload.get("passed") else 1
    try:
        report = run_trial(args)
    except Exception as exc:
        payload = {
            "schema": SCHEMA,
            "passed": False,
            "failure_reasons": ["trial_runner_failed"],
            "runner_error": type(exc).__name__,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"trial_runner_failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"c22_rapid_media_fault_trial_passed={str(bool(report.get('passed'))).lower()}")
        print("report=c22_rapid_media_fault_trial_report.json")
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
