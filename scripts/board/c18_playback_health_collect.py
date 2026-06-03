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
DEFAULT_DURATION_SEC = 60
DEFAULT_INTERVAL_SEC = 1.0
DEFAULT_IPC_TIMEOUT_SEC = 0.8
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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


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


def sanitize_item(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    path = value.get("path") if isinstance(value.get("path"), str) else ""
    url = value.get("url") if isinstance(value.get("url"), str) else ""
    out: dict[str, Any] = {
        "alias": media_alias(path, url),
        "path_alias": safe_path_alias(path),
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
        "last_poll_error": sanitize_error_presence(raw.get("last_poll_error")),
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

    while time.monotonic() < deadline or seq == 0:
        seq += 1
        rel_sec = time.monotonic() - started
        ipc_result, ipc_error, values, ipc_elapsed_ms, prop_errors = ipc_query_many(ipc_path, ipc_timeout_sec)
        status = sanitize_status(status_path)
        current_item = status.get("current_item") if isinstance(status.get("current_item"), dict) else {}
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
        with status_samples_path.open("a", encoding="utf-8") as fh:
            fh.write(compact_json({"seq": seq, "rel_sec": round(rel_sec, 3), "status": status}) + "\n")

        next_sample = time.monotonic() + interval_sec
        while time.monotonic() < deadline and time.monotonic() < next_sample:
            time.sleep(min(0.1, next_sample - time.monotonic(), deadline - time.monotonic()))


def service_nrestarts(service: str) -> int:
    return as_int(run(["systemctl", "show", service, "-p", "NRestarts", "--value"]).stdout)


def write_systemd_sidecar(out_dir: Path, service: str, nrestarts_start: int) -> None:
    active = run(["systemctl", "is-active", service]).stdout.strip() == "active"
    nrestarts_end = service_nrestarts(service)
    write_json(out_dir / "deep-health-systemd.json", {
        "service_active": active,
        "nrestarts_delta": max(nrestarts_end - nrestarts_start, 0),
    })


def write_process_sidecar(out_dir: Path, app_user: str) -> None:
    mpv_processes: list[str] = []
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
                mpv_processes.append(os.readlink(proc / "exe"))
            except Exception:
                continue
    write_json(out_dir / "deep-health-process.json", {
        "mpv_count": len(mpv_processes),
        "mpv_path": mpv_processes[0] if mpv_processes else "",
    })


def write_kernel_sidecar(out_dir: Path) -> None:
    kernel_text = run(["journalctl", "-k", "-b", "--no-pager", "--output=cat"]).stdout
    write_json(out_dir / "deep-health-kernel.json", {
        "panfrost_faults": len(re.findall(r"panfrost.*(fault|hang|reset|error)", kernel_text, re.I)),
        "mmc_timeout_reset": len(re.findall(r"mmc.*(timeout|timed out|reset|I/O error)", kernel_text, re.I)),
        "ext4_errors": len(re.findall(r"EXT4-fs error|Aborting journal|Remounting filesystem read-only", kernel_text, re.I)),
    })


def count_player_log_counters(mpv_log: Path, generation_dir: Path) -> dict[str, int]:
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
    return {
        "media_load_failed": len(re.findall(r"media_load_failed|Failed to load media", log_text, re.I)),
        "mpv_restart": len(re.findall(r"\bRestarting MPV\b", log_text)),
    }


def write_player_counter_sidecar(out_dir: Path, mpv_log: Path, generation_dir: Path) -> None:
    write_json(out_dir / "deep-health-player-counters.json", count_player_log_counters(mpv_log, generation_dir))


def evaluate_artifacts(out_dir: Path, artifact_id: str) -> dict[str, Any]:
    result = health.evaluate(
        samples_path=out_dir / "playback-samples.tsv",
        systemd_path=out_dir / "deep-health-systemd.json",
        process_path=out_dir / "deep-health-process.json",
        kernel_path=out_dir / "deep-health-kernel.json",
        player_counters_path=out_dir / "deep-health-player-counters.json",
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
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--app-user", default=DEFAULT_APP_USER)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--mpv-log", type=Path, default=DEFAULT_MPV_LOG)
    parser.add_argument("--mpv-generation-dir", type=Path, default=DEFAULT_MPV_GENERATION_DIR)
    parser.add_argument("--json", action="store_true", help="print sanitized public summary JSON to stdout")
    return parser.parse_args(argv)


def collect(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    out_dir = args.output_dir or default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(out_dir, 0o700)
    except OSError:
        pass

    nrestarts_start = service_nrestarts(args.service)
    collect_samples(
        out_dir,
        config_path=args.config,
        fallback_status=args.status,
        duration_sec=max(float(args.duration_sec), 0.1),
        interval_sec=max(float(args.interval_sec), 0.1),
        ipc_timeout_sec=max(float(args.ipc_timeout_sec), 0.05),
    )
    write_systemd_sidecar(out_dir, args.service, nrestarts_start)
    write_process_sidecar(out_dir, args.app_user)
    write_kernel_sidecar(out_dir)
    write_player_counter_sidecar(out_dir, args.mpv_log, args.mpv_generation_dir)
    result = evaluate_artifacts(out_dir, out_dir.name)
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
