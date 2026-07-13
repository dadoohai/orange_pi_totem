#!/usr/bin/env python3
"""Collect non-destructive C18 playback deep-health artifacts.

This collector observes the currently running kiosky-player service.  It does
not stop, start, restart or otherwise mutate the player.  It writes the artifact
set consumed by c18_playback_health_summary.py and emits only sanitized public
summary data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pwd
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import c18_playback_health_summary as health


DEFAULT_SERVICE = "kiosky-player.service"
DEFAULT_APP_USER = "totem"
DEFAULT_CONFIG = Path("/data/config/config.json")
DEFAULT_STATUS = Path("/tmp/kiosky-status.json")
DEFAULT_MPV_LOG = Path("/tmp/kiosky/mpv.log")
DEFAULT_MPV_GENERATION_DIR = Path("/tmp/kiosky")
DEFAULT_WATCHDOG_STATE = Path("/data/state/kiosky-player/status-mpv-watchdog.json")
DEFAULT_DURATION_SEC = 60
DEFAULT_INTERVAL_SEC = 1.0
DEFAULT_IPC_TIMEOUT_SEC = 0.8
TARGET_MODES = ("service", "candidate")
PROPS = (
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
SAMPLE_FIELDS = (
    "seq",
    "rel_sec",
    "wall_time",
    "ipc_result",
    "ipc_error",
    "ipc_elapsed_ms",
    "current_alias",
    "path_alias",
    "current_path_kind",
    "filename_alias",
    "time_pos",
    "duration",
    "percent_pos",
    "idle_active",
    "pause",
    "eof_reached",
    "estimated_frame_number",
    "hwdec_current",
    "vo_configured",
    "video_params_json",
    "property_errors_json",
    "status_present",
    "status_playback_state",
    "status_current_alias",
    "status_path_alias",
    "status_duration_ms",
    "status_current_index",
    "status_mpv_running",
    "status_snapshot_json",
)

PUBLIC_SURFACE_BASENAME_RE = re.compile(
    r"^startup-feedback-c25-visible-state-h264-v1-(?:loading_content|content_unavailable|player_error)-[0-9a-f]{16}-[0-9]+x[0-9]+\.mp4$"
)
STILL_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")


def sha1_short(value: Any) -> str:
    return hashlib.sha1(str(value).encode("utf-8"), usedforsecurity=False).hexdigest()[:10]


def media_alias(path: str = "", url: str = "") -> str:
    source = url or path or ""
    return f"media-{sha1_short(source)}" if source else ""


def safe_path_alias(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    if "://" in value:
        return f"<redacted-url:{sha1_short(value)}>"
    if value.startswith("/data/media/") or value.startswith("/tmp/"):
        return f"<media-path:{sha1_short(value)}>"
    if value.startswith("/data/"):
        return f"<data-path:{sha1_short(value)}>"
    if value.startswith("/"):
        return f"<local-path:{sha1_short(value)}>"
    return f"<filename:{sha1_short(value)}>"


def classify_current_path(
    value: Any,
    current_item: dict[str, Any] | None = None,
    next_item: dict[str, Any] | None = None,
) -> str:
    """Return a non-sensitive playback evidence class for the active MPV path."""
    if not isinstance(value, str) or not value:
        return "unclassified_media"
    basename = Path(value).name.lower()
    path_alias = safe_path_alias(value)
    for item in (current_item, next_item):
        sanitized_item = item if isinstance(item, dict) else {}
        if sanitized_item.get("path_alias") != path_alias:
            continue
        if sanitized_item.get("media_kind") == "still_image":
            return "still_image_sidecar"
        return "motion_media"
    if value.startswith("/tmp/") and PUBLIC_SURFACE_BASENAME_RE.fullmatch(basename):
        return "public_surface"
    return "unclassified_media"


def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return f"{float(value):.6f}".rstrip("0").rstrip(".")
    return str(value)


def as_int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return 0


def compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    fsync_dir(path.parent)


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def load_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return {"_parse_error": True}


def sanitize_error_presence(value: Any) -> str:
    if value in (None, "", False):
        return "null"
    return "present"


def sanitize_poll_error(value: Any) -> str:
    if value in (None, "", False):
        return "null"
    if isinstance(value, str) and "polling_disabled" in value:
        return "polling_disabled"
    return "present"


def sanitize_item(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    path = value.get("path") if isinstance(value.get("path"), str) else ""
    source_path = value.get("source_path") if isinstance(value.get("source_path"), str) else ""
    url = value.get("url") if isinstance(value.get("url"), str) else ""
    source_is_image = Path(source_path).suffix.lower() in STILL_IMAGE_EXTENSIONS
    path_is_image = Path(path).suffix.lower() in STILL_IMAGE_EXTENSIONS
    exact_sidecar = bool(source_is_image and path == f"{source_path}.h264.mp4")
    out: dict[str, Any] = {
        "alias": media_alias(path, url),
        "path_alias": safe_path_alias(path),
        "media_kind": (
            "still_image"
            if path_is_image or exact_sidecar
            else "motion_media"
        ),
    }
    for key in ("duration_ms", "offset_ms"):
        if isinstance(value.get(key), (int, float, str)):
            try:
                out[key] = int(value.get(key))
            except Exception:
                pass
    if isinstance(value.get("started_at"), str):
        out["started_at_present"] = True
    return out


def sanitize_status(status_path: Path) -> dict[str, Any]:
    raw = load_json_file(status_path)
    if raw is None:
        return {"present": False}
    if not isinstance(raw, dict) or raw.get("_parse_error"):
        return {"present": True, "parse_error": True}
    current_item = sanitize_item(raw.get("current_item"))
    next_item = sanitize_item(raw.get("next_item"))
    return {
        "present": True,
        "playback_state": raw.get("playback_state"),
        "playlist_size": raw.get("playlist_size"),
        "current_index": raw.get("current_index"),
        "mpv_running": raw.get("mpv_running"),
        "consecutive_failures": raw.get("consecutive_failures"),
        "blocked_media_count": raw.get("blocked_media_count"),
        "uptime_sec": raw.get("uptime_sec"),
        "last_poll_error": sanitize_poll_error(raw.get("last_poll_error")),
        "last_render_error": sanitize_error_presence(raw.get("last_render_error")),
        "black_screen_risk_reason": sanitize_error_presence(raw.get("black_screen_risk_reason")),
        "current_item": current_item,
        "next_item": next_item,
    }


def sanitize_video_params(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key in (
        "w",
        "h",
        "dw",
        "dh",
        "aspect",
        "par",
        "rotate",
        "pixelformat",
        "hw-pixelformat",
        "stereo-in",
    ):
        if key in value and (value[key] is None or isinstance(value[key], (str, int, float, bool))):
            safe[key] = value[key]
    return safe


def ipc_query_many(ipc_path: Path, timeout_s: float) -> tuple[str, str, dict[str, Any], int, dict[str, str]]:
    if not ipc_path.exists():
        return "error", "missing_socket", {}, 0, {}
    start = time.monotonic()
    responses: dict[str, Any] = {}
    prop_errors: dict[str, str] = {}
    rid_to_prop: dict[int, str] = {}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_s)
            sock.connect(str(ipc_path))
            for index, prop in enumerate(PROPS, start=1):
                rid = 800000 + index
                rid_to_prop[rid] = prop
                sock.sendall((json.dumps({"command": ["get_property", prop], "request_id": rid}) + "\n").encode("utf-8"))

            buffer = ""
            deadline = start + timeout_s
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
        return "timeout", "socket_timeout", responses, int(round((time.monotonic() - start) * 1000)), prop_errors
    except Exception as exc:
        return "error", type(exc).__name__, responses, int(round((time.monotonic() - start) * 1000)), prop_errors

    elapsed_ms = int(round((time.monotonic() - start) * 1000))
    if len(responses) < len(rid_to_prop):
        return "timeout", "partial_response", responses, elapsed_ms, prop_errors
    return "success", "", responses, elapsed_ms, prop_errors


def read_config(config_path: Path, fallback_status: Path) -> tuple[Path, Path]:
    data = load_json_file(config_path)
    if not isinstance(data, dict):
        raise RuntimeError(f"config JSON unavailable or invalid: {config_path}")
    ipc_path = Path(str(data.get("ipc_path") or "/tmp/kiosky/mpv.sock"))
    status_path = Path(str(data.get("status_file") or fallback_status))
    return ipc_path, status_path


def collect_samples(out_dir: Path,
                    *,
                    config_path: Path,
                    fallback_status: Path,
                    duration_sec: float,
                    interval_sec: float,
                    ipc_timeout_sec: float) -> None:
    ipc_path, status_path = read_config(config_path, fallback_status)
    samples_path = out_dir / "playback-samples.tsv"
    status_samples_path = out_dir / "status-samples.ndjson"
    started = time.monotonic()
    deadline = started + duration_sec
    seq = 0

    with samples_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, delimiter="\t", fieldnames=SAMPLE_FIELDS, lineterminator="\n")
        writer.writeheader()
        fh.flush()
        os.fsync(fh.fileno())
    fsync_dir(samples_path.parent)

    while time.monotonic() < deadline or seq == 0:
        seq += 1
        rel_sec = time.monotonic() - started
        ipc_result, ipc_error, values, ipc_elapsed_ms, prop_errors = ipc_query_many(ipc_path, ipc_timeout_sec)
        status = sanitize_status(status_path)
        current_item = status.get("current_item") if isinstance(status.get("current_item"), dict) else {}
        next_item = status.get("next_item") if isinstance(status.get("next_item"), dict) else {}
        current_alias = safe_path_alias(values.get("path")) or safe_path_alias(values.get("filename"))
        status_current_alias = str(current_item.get("alias") or "")
        status_path_alias = str(current_item.get("path_alias") or "")
        if not current_alias:
            current_alias = status_path_alias or status_current_alias
        row = {
            "seq": str(seq),
            "rel_sec": f"{rel_sec:.3f}",
            "wall_time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "ipc_result": ipc_result,
            "ipc_error": ipc_error,
            "ipc_elapsed_ms": str(ipc_elapsed_ms),
            "current_alias": current_alias,
            "path_alias": safe_path_alias(values.get("path")),
            "current_path_kind": classify_current_path(values.get("path"), current_item, next_item),
            "filename_alias": safe_path_alias(values.get("filename")),
            "time_pos": scalar(values.get("time-pos")),
            "duration": scalar(values.get("duration")),
            "percent_pos": scalar(values.get("percent-pos")),
            "idle_active": scalar(values.get("idle-active")),
            "pause": scalar(values.get("pause")),
            "eof_reached": scalar(values.get("eof-reached")),
            "estimated_frame_number": scalar(values.get("estimated-frame-number")),
            "hwdec_current": scalar(values.get("hwdec-current")),
            "vo_configured": scalar(values.get("vo-configured")),
            "video_params_json": compact_json(sanitize_video_params(values.get("video-params"))),
            "property_errors_json": compact_json(prop_errors),
            "status_present": "true" if status.get("present") else "false",
            "status_playback_state": scalar(status.get("playback_state")),
            "status_current_alias": status_current_alias,
            "status_path_alias": status_path_alias,
            "status_duration_ms": scalar(current_item.get("duration_ms")),
            "status_current_index": scalar(status.get("current_index")),
            "status_mpv_running": scalar(status.get("mpv_running")),
            "status_snapshot_json": compact_json(status),
        }
        with samples_path.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, delimiter="\t", fieldnames=SAMPLE_FIELDS, lineterminator="\n")
            writer.writerow(row)
            fh.flush()
            os.fsync(fh.fileno())
        with status_samples_path.open("a", encoding="utf-8") as fh:
            fh.write(compact_json({"seq": seq, "rel_sec": round(rel_sec, 3), "status": status}) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        fsync_dir(out_dir)

        next_sample = time.monotonic() + interval_sec
        while time.monotonic() < deadline and time.monotonic() < next_sample:
            time.sleep(min(0.1, next_sample - time.monotonic(), deadline - time.monotonic()))


def pid_running(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    proc = Path("/proc") / str(pid)
    if not proc.exists():
        return False
    try:
        status = (proc / "status").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    match = re.search(r"^State:\s+(\S+)", status, re.MULTILINE)
    return not (match and match.group(1) == "Z")


def service_nrestarts(service: str) -> int:
    return as_int(run(["systemctl", "show", service, "-p", "NRestarts", "--value"]).stdout)


def parse_systemd_duration_sec(value: str | None) -> float | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"infinity", "infinityus"}:
        return None
    parts = re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)?", text)
    if not parts:
        return None
    total = 0.0
    matched = False
    for number, unit in parts:
        matched = True
        value_float = float(number)
        unit_lower = (unit or "s").lower()
        if unit_lower in {"us", "usec"}:
            total += value_float / 1_000_000.0
        elif unit_lower in {"ms", "msec"}:
            total += value_float / 1_000.0
        elif unit_lower in {"s", "sec", "secs", "second", "seconds"}:
            total += value_float
        elif unit_lower in {"min", "mins", "minute", "minutes"}:
            total += value_float * 60.0
        elif unit_lower in {"h", "hr", "hour", "hours"}:
            total += value_float * 3600.0
        else:
            return None
    return total if matched else None


def service_lifecycle_properties(service: str) -> dict[str, Any]:
    keys = ("KillMode", "TimeoutStopUSec", "SendSIGKILL")
    proc = run(["systemctl", "show", service, *sum([["-p", key] for key in keys], [])])
    raw: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            raw[key] = value
    timeout_stop = raw.get("TimeoutStopUSec", "")
    timeout_stop_sec = parse_systemd_duration_sec(timeout_stop)
    return {
        "service_lifecycle_show_rc": proc.returncode,
        "kill_mode": raw.get("KillMode", ""),
        "timeout_stop_usec": timeout_stop,
        "timeout_stop_sec": timeout_stop_sec,
        "send_sigkill": raw.get("SendSIGKILL", ""),
    }


def write_systemd_sidecar(out_dir: Path,
                          service: str,
                          nrestarts_start: int,
                          *,
                          target_mode: str,
                          candidate_pid: int | None = None) -> None:
    if target_mode == "candidate":
        active = pid_running(candidate_pid)
        nrestarts_delta = 0
    else:
        active = run(["systemctl", "is-active", service]).stdout.strip() == "active"
        nrestarts_end = service_nrestarts(service)
        nrestarts_delta = max(nrestarts_end - nrestarts_start, 0)
    payload = {
        "target_mode": target_mode,
        "service_active": active,
        "nrestarts_delta": nrestarts_delta,
        "candidate_pid_present": bool(candidate_pid) if target_mode == "candidate" else False,
    }
    payload.update(service_lifecycle_properties(service))
    write_json(out_dir / "deep-health-systemd.json", payload)


def argv_matches_ipc(argv: list[str], ipc_path: Path) -> bool:
    expected = str(ipc_path)
    for index, arg in enumerate(argv):
        if arg == f"--input-ipc-server={expected}":
            return True
        if arg == "--input-ipc-server" and index + 1 < len(argv) and argv[index + 1] == expected:
            return True
    return False


def proc_argv(proc: Path) -> list[str]:
    raw = (proc / "cmdline").read_bytes()
    return [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]


def write_process_sidecar(out_dir: Path, app_user: str, process_ipc_path: Path | None = None) -> None:
    mpv_processes: list[str] = []
    total_mpv_processes = 0
    try:
        app_uid = pwd.getpwnam(app_user).pw_uid
    except Exception:
        app_uid = None
    if app_uid is not None:
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit():
                continue
            try:
                status = (proc / "status").read_text(encoding="utf-8", errors="replace")
                uid_match = re.search(r"^Uid:\s+(\d+)\s", status, re.MULTILINE)
                if not uid_match or int(uid_match.group(1)) != app_uid:
                    continue
                comm = (proc / "comm").read_text(encoding="utf-8", errors="replace").strip()
                if comm != "mpv":
                    continue
                total_mpv_processes += 1
                if process_ipc_path is not None and not argv_matches_ipc(proc_argv(proc), process_ipc_path):
                    continue
                mpv_processes.append(os.readlink(proc / "exe"))
            except Exception:
                continue
    write_json(out_dir / "deep-health-process.json", {
        "mpv_count": len(mpv_processes),
        "total_mpv_count": total_mpv_processes,
        "process_filter": "input-ipc-server" if process_ipc_path is not None else "",
        "mpv_path": mpv_processes[0] if mpv_processes else "",
    })


def kernel_event_counts() -> dict[str, int]:
    kernel_text = run(["journalctl", "-k", "-b", "--no-pager", "--output=cat"]).stdout
    return {
        "panfrost_faults": len(re.findall(r"panfrost.*(fault|hang|reset|error)", kernel_text, re.I)),
        "mmc_timeout_reset": len(re.findall(r"mmc.*(timeout|timed out|reset|I/O error)", kernel_text, re.I)),
        "ext4_errors": len(re.findall(r"EXT4-fs error|Aborting journal|Remounting filesystem read-only", kernel_text, re.I)),
    }


def kernel_boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def uptime_sec() -> float:
    try:
        return float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
    except Exception:
        return 0.0


def write_kernel_sidecar(out_dir: Path, start_counts: dict[str, int], start_uptime_sec: float) -> None:
    end_counts = kernel_event_counts()
    payload: dict[str, Any] = {
        **end_counts,
        "boot_id_present": bool(kernel_boot_id()),
        "uptime_start_sec": round(start_uptime_sec, 3),
        "uptime_end_sec": round(uptime_sec(), 3),
    }
    for key, end_value in end_counts.items():
        start_value = int(start_counts.get(key, 0))
        payload[f"{key}_start"] = start_value
        payload[f"{key}_delta"] = max(int(end_value) - start_value, 0)
    write_json(out_dir / "deep-health-kernel.json", payload)


def count_player_event_patterns(text: str) -> dict[str, int]:
    return {
        "media_load_failed": len(re.findall(r"media_load_failed|Failed to load media", text, re.I)),
        "mpv_restart": len(re.findall(r"\bRestarting MPV\b", text)),
    }


def journalctl_utc_arg(value: str) -> str:
    if value.endswith("Z") and "T" in value:
        return value[:-1].replace("T", " ") + " UTC"
    return value


def count_player_log_counters(
    mpv_log: Path,
    generation_dir: Path,
    *,
    service: str,
    start_utc: str,
    end_utc: str,
) -> dict[str, Any]:
    log_text = ""
    paths = [mpv_log]
    try:
        paths.extend(sorted(generation_dir.glob("mpv-g*.log")))
    except Exception:
        pass
    for path in paths:
        try:
            log_text += path.read_text(encoding="utf-8", errors="replace") + "\n"
        except Exception:
            continue
    file_counts = count_player_event_patterns(log_text)
    journal_counts = {"media_load_failed": 0, "mpv_restart": 0}
    journal_query_failed = False
    if service:
        proc = run([
            "journalctl",
            "-u",
            service,
            "--since",
            journalctl_utc_arg(start_utc),
            "--until",
            journalctl_utc_arg(end_utc),
            "--no-pager",
            "--output=cat",
        ])
        if proc.returncode == 0:
            journal_counts = count_player_event_patterns(proc.stdout)
        else:
            journal_query_failed = True
    media_load_failed = file_counts["media_load_failed"] + journal_counts["media_load_failed"]
    mpv_restart = file_counts["mpv_restart"] + journal_counts["mpv_restart"]
    if journal_query_failed:
        media_load_failed = -1
        mpv_restart = -1
    return {
        "media_load_failed": media_load_failed,
        "mpv_restart": mpv_restart,
        "file_media_load_failed": file_counts["media_load_failed"],
        "file_mpv_restart": file_counts["mpv_restart"],
        "journal_media_load_failed": journal_counts["media_load_failed"],
        "journal_mpv_restart": journal_counts["mpv_restart"],
        "journal_query_failed": journal_query_failed,
    }


def write_player_counter_sidecar(
    out_dir: Path,
    mpv_log: Path,
    generation_dir: Path,
    *,
    service: str,
    start_utc: str,
    end_utc: str,
) -> None:
    write_json(
        out_dir / "deep-health-player-counters.json",
        count_player_log_counters(
            mpv_log,
            generation_dir,
            service=service,
            start_utc=start_utc,
            end_utc=end_utc,
        ),
    )


def watchdog_state_snapshot(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
        raw = path.read_bytes()
    except FileNotFoundError:
        return {"exists": False, "path": str(path)}
    except OSError:
        return {"exists": False, "path": str(path), "read_error": "present"}
    data: Any
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    event = {
        "schema": data.get("schema"),
        "action": data.get("action"),
        "reason": data.get("reason"),
        "recorded_at_utc": data.get("recorded_at_utc"),
    }
    return {
        "exists": True,
        "path": str(path),
        "mtime_ns": stat.st_mtime_ns,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "event": {key: value for key, value in event.items() if value not in (None, "")},
    }


def write_watchdog_sidecar(
    out_dir: Path,
    watchdog_state: Path,
    *,
    start: dict[str, Any],
    start_utc: str,
    end_utc: str,
) -> None:
    end = watchdog_state_snapshot(watchdog_state)
    changed = (
        start.get("exists") != end.get("exists")
        or start.get("mtime_ns") != end.get("mtime_ns")
        or start.get("sha256") != end.get("sha256")
    )
    action = ""
    if changed and isinstance(end.get("event"), dict):
        action = str(end["event"].get("action") or "")
    write_json(out_dir / "deep-health-watchdog.json", {
        "schema": "dadooh.c18.playback.deep_health.watchdog.v1",
        "state_file": str(watchdog_state),
        "collection_started_at_utc": start_utc,
        "collection_finished_at_utc": end_utc,
        "event_changed_during_window": changed,
        "action_during_window": action,
        "start": start,
        "end": end,
    })


def evaluate_artifacts(out_dir: Path, artifact_id: str, *, panfrost_fault_policy: str = "absolute") -> dict[str, Any]:
    result = health.evaluate(
        samples_path=out_dir / "playback-samples.tsv",
        systemd_path=out_dir / "deep-health-systemd.json",
        process_path=out_dir / "deep-health-process.json",
        kernel_path=out_dir / "deep-health-kernel.json",
        player_counters_path=out_dir / "deep-health-player-counters.json",
        watchdog_path=out_dir / "deep-health-watchdog.json",
        panfrost_fault_policy=panfrost_fault_policy,
    )
    result["artifact_id"] = artifact_id
    return result


def default_output_dir() -> Path:
    ts = time.strftime("%Y%m%d-%H%M%S%z")
    return Path("/tmp") / f"c18-playback-health-{ts}"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-sec", type=float, default=float(os.environ.get("C18_PLAYBACK_HEALTH_DURATION_SEC", DEFAULT_DURATION_SEC)))
    parser.add_argument("--interval-sec", type=float, default=float(os.environ.get("C18_PLAYBACK_HEALTH_INTERVAL_SEC", DEFAULT_INTERVAL_SEC)))
    parser.add_argument("--ipc-timeout-sec", type=float, default=float(os.environ.get("C18_PLAYBACK_HEALTH_IPC_TIMEOUT_SEC", DEFAULT_IPC_TIMEOUT_SEC)))
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--target-mode", choices=TARGET_MODES, default="service")
    parser.add_argument("--candidate-pid", type=int, default=None)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--app-user", default=DEFAULT_APP_USER)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--match-process-ipc", action="store_true", help="count only the mpv process using the config IPC socket")
    parser.add_argument("--process-ipc-path", type=Path, default=None, help="count only the mpv process using this IPC socket")
    parser.add_argument("--mpv-log", type=Path, default=DEFAULT_MPV_LOG)
    parser.add_argument("--mpv-generation-dir", type=Path, default=DEFAULT_MPV_GENERATION_DIR)
    parser.add_argument("--watchdog-state", type=Path, default=DEFAULT_WATCHDOG_STATE)
    parser.add_argument("--panfrost-fault-policy", choices=sorted(health.PANFROST_FAULT_POLICIES), default="absolute")
    parser.add_argument("--json", action="store_true", help="print sanitized public summary JSON to stdout")
    return parser.parse_args(argv)


def collect(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    out_dir = args.output_dir or default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(out_dir, 0o700)
    except OSError:
        pass

    ipc_path, _status_path = read_config(args.config, args.status)
    process_ipc_path = args.process_ipc_path
    if process_ipc_path is None and args.match_process_ipc:
        process_ipc_path = ipc_path

    nrestarts_start = service_nrestarts(args.service) if args.target_mode == "service" else 0
    kernel_start_counts = kernel_event_counts()
    kernel_start_uptime_sec = uptime_sec()
    watchdog_start_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    watchdog_start = watchdog_state_snapshot(args.watchdog_state)
    collect_samples(
        out_dir,
        config_path=args.config,
        fallback_status=args.status,
        duration_sec=max(float(args.duration_sec), 0.1),
        interval_sec=max(float(args.interval_sec), 0.1),
        ipc_timeout_sec=max(float(args.ipc_timeout_sec), 0.05),
    )
    watchdog_end_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_systemd_sidecar(
        out_dir,
        args.service,
        nrestarts_start,
        target_mode=args.target_mode,
        candidate_pid=args.candidate_pid,
    )
    write_process_sidecar(out_dir, args.app_user, process_ipc_path)
    write_kernel_sidecar(out_dir, kernel_start_counts, kernel_start_uptime_sec)
    write_player_counter_sidecar(
        out_dir,
        args.mpv_log,
        args.mpv_generation_dir,
        service=args.service if args.target_mode == "service" else "",
        start_utc=watchdog_start_utc,
        end_utc=watchdog_end_utc,
    )
    write_watchdog_sidecar(
        out_dir,
        args.watchdog_state,
        start=watchdog_start,
        start_utc=watchdog_start_utc,
        end_utc=watchdog_end_utc,
    )
    result = evaluate_artifacts(out_dir, out_dir.name, panfrost_fault_policy=args.panfrost_fault_policy)
    write_json(out_dir / "playback-deep-health-public.json", result)
    return out_dir, result


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        out_dir, result = collect(args)
    except Exception as exc:
        payload = {
            "schema": health.SCHEMA,
            "passed": False,
            "failure_reasons": ["collector_failed"],
            "collector_error": type(exc).__name__,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"collector_failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"output_dir={out_dir}")
        print(f"playback_deep_health_passed={str(bool(result.get('passed'))).lower()}")
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
