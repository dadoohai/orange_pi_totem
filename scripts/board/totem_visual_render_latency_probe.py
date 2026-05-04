#!/usr/bin/env python3
"""C9.9.1 isolated visual render latency probe.

This probe uses only synthetic screens and sanitized timing metadata. It does
not read real config, does not touch Wi-Fi, does not call writer, and writes
only private artifacts under /tmp.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import pathlib
import select
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import termios
import time
import tty
from dataclasses import dataclass
from typing import Any


sys.dont_write_bytecode = True


SCHEMA_VERSION = "dadooh-c9.9.1-visual-latency-probe.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c9-9-1-visual-latency-probe"
STATUS_FILENAME = "latency-status.json"
SUMMARY_FILENAME = "summary.txt"
TMP_ROOT = pathlib.Path("/tmp").resolve()
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
WIDTH = 1280
HEIGHT = 720
UNKNOWN = "unknown"
MPV_VIDEO_MODES = ("drm", "gpu_drm")
PRESENT_SETTLE_SEC = float(os.environ.get("TOTEM_VISUAL_PROBE_PRESENT_SETTLE_SEC", "0.55"))
DOUBLE_LOAD_PER_SCREEN = os.environ.get("TOTEM_VISUAL_PROBE_DOUBLE_LOAD_PER_SCREEN", "1") != "0"

METHODS = (
    "same_path_ipc",
    "unique_path_ipc",
    "unique_path_fsync_ipc",
    "unique_path_ipc_wait",
    "restart_mpv_unique_path",
)

EVENT_SEQUENCE = (
    ("initial", "STATE_INITIAL", ""),
    ("enter", "STATE_AFTER_ENTER", "ENTER"),
    ("char_a", "STATE_AFTER_A", "A"),
    ("char_b", "STATE_AFTER_B", "B"),
    ("backspace", "STATE_AFTER_BACKSPACE", "BACKSPACE"),
    ("enter_done", "STATE_DONE", "ENTER"),
)


class ProbeError(RuntimeError):
    """Public-safe probe error."""


@dataclass(frozen=True)
class MethodSpec:
    name: str
    same_path: bool
    fsync_svg: bool
    wait_ipc_path: bool
    restart_mpv: bool


METHOD_SPECS = {
    "same_path_ipc": MethodSpec("same_path_ipc", same_path=True, fsync_svg=False, wait_ipc_path=False, restart_mpv=False),
    "unique_path_ipc": MethodSpec("unique_path_ipc", same_path=False, fsync_svg=False, wait_ipc_path=False, restart_mpv=False),
    "unique_path_fsync_ipc": MethodSpec("unique_path_fsync_ipc", same_path=False, fsync_svg=True, wait_ipc_path=False, restart_mpv=False),
    "unique_path_ipc_wait": MethodSpec("unique_path_ipc_wait", same_path=False, fsync_svg=True, wait_ipc_path=True, restart_mpv=False),
    "restart_mpv_unique_path": MethodSpec("restart_mpv_unique_path", same_path=False, fsync_svg=True, wait_ipc_path=False, restart_mpv=True),
}


def now() -> float:
    return time.time()


def path_is_under(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root)
        return True
    except ValueError:
        return False


def require_tmp_dir(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    if not path.is_absolute():
        raise ProbeError("out-dir must be absolute")
    resolved = path.resolve(strict=False)
    if resolved == TMP_ROOT or not path_is_under(resolved, TMP_ROOT):
        raise ProbeError("out-dir must be under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise ProbeError("out-dir exists and is not a directory")
    return resolved


def prepare_private_dir(path: pathlib.Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, PRIVATE_DIR_MODE)


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


def atomic_write_private_text(path: pathlib.Path, content: str, out_dir: pathlib.Path, *, fsync_file: bool) -> None:
    if path.parent != out_dir:
        raise ProbeError("artifact path must stay in out-dir")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(out_dir), text=True)
    tmp_path = pathlib.Path(tmp_name)
    try:
        os.fchmod(fd, PRIVATE_FILE_MODE)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            if fsync_file:
                os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        os.chmod(path, PRIVATE_FILE_MODE)
        if fsync_file:
            fsync_directory(out_dir)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def atomic_write_private_json(path: pathlib.Path, payload: dict[str, Any], out_dir: pathlib.Path) -> None:
    atomic_write_private_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n", out_dir, fsync_file=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def synthetic_svg(label: str, seq: int, event_name: str, color: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <rect width="{WIDTH}" height="{HEIGHT}" fill="{color}"/>
  <rect x="76" y="74" width="1128" height="572" rx="12" fill="#0f172a" stroke="#e2e8f0" stroke-width="6"/>
  <text x="112" y="146" font-family="Arial, DejaVu Sans, sans-serif" font-size="44" font-weight="700" fill="#ffffff">Dadooh</text>
  <text x="112" y="212" font-family="Arial, DejaVu Sans, sans-serif" font-size="34" font-weight="700" fill="#67e8f9">C9.9.1 Latency Probe</text>
  <text x="112" y="318" font-family="Arial, DejaVu Sans Mono, monospace" font-size="68" font-weight="700" fill="#ffffff">{escape(label)}</text>
  <text x="112" y="404" font-family="Arial, DejaVu Sans Mono, monospace" font-size="42" fill="#dbeafe">render_seq={seq:04d}</text>
  <text x="112" y="470" font-family="Arial, DejaVu Sans Mono, monospace" font-size="34" fill="#dbeafe">event={escape(event_name)}</text>
  <text x="112" y="562" font-family="Arial, DejaVu Sans, sans-serif" font-size="26" fill="#e2e8f0">Tela sintetica sem dados reais. Observe se muda no primeiro input.</text>
</svg>
"""


def framebuffer_snapshot_hash() -> dict[str, Any]:
    info = {
        "available": False,
        "hash": UNKNOWN,
        "bytes_read": 0,
        "method": "fb0_sha256_prefix",
    }
    fb_path = pathlib.Path("/dev/fb0")
    if not fb_path.exists():
        return info
    try:
        with fb_path.open("rb", buffering=0) as handle:
            payload = handle.read(1024 * 1024)
    except OSError:
        return info
    if not payload:
        return info
    info["available"] = True
    info["hash"] = hashlib.sha256(payload).hexdigest()[:16]
    info["bytes_read"] = len(payload)
    return info


class MPMVRenderer:
    def __init__(self, out_dir: pathlib.Path, *, mpv_bin: str, video_mode: str) -> None:
        self.out_dir = out_dir
        self.ipc_path = out_dir / "probe-mpv.sock"
        self.mpv_bin = mpv_bin
        self.video_mode = video_mode
        self.process: subprocess.Popen[bytes] | None = None
        self.request_id = 0

    def video_args(self) -> list[str]:
        if self.video_mode == "drm":
            return ["--vo=drm", "--profile=sw-fast"]
        if self.video_mode == "gpu_drm":
            return ["--vo=gpu", "--gpu-context=drm"]
        raise ProbeError("unknown video mode")

    def start(self, path: pathlib.Path) -> str:
        if not shutil.which(self.mpv_bin):
            return "mpv_unavailable"
        self.stop()
        try:
            self.ipc_path.unlink()
        except FileNotFoundError:
            pass
        command = [
            self.mpv_bin,
            "--no-config",
            "--fs",
            "--force-window=yes",
            "--image-display-duration=inf",
            "--keep-open=yes",
            "--no-terminal",
            "--no-osc",
            "--osd-level=0",
            "--input-terminal=no",
            "--input-default-bindings=no",
            "--input-vo-keyboard=no",
            "--cursor-autohide=always",
            "--ao=null",
            f"--input-ipc-server={self.ipc_path}",
            *self.video_args(),
            "--",
            str(path),
        ]
        self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.ipc_path.exists():
                return "started"
            if self.process.poll() is not None:
                return "mpv_exited"
            time.sleep(0.05)
        return "ipc_unavailable"

    def stop(self) -> None:
        process = self.process
        self.process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        try:
            self.ipc_path.unlink()
        except FileNotFoundError:
            pass

    def ipc_request(self, command: list[Any], *, timeout_sec: float = 1.0) -> dict[str, Any] | None:
        if self.process is None or self.process.poll() is not None:
            return None
        self.request_id += 1
        request_id = self.request_id
        payload = json.dumps({"command": command, "request_id": request_id}).encode("utf-8") + b"\n"
        deadline = time.monotonic() + timeout_sec
        buffer = b""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(timeout_sec)
                client.connect(str(self.ipc_path))
                client.sendall(payload)
                while time.monotonic() < deadline:
                    try:
                        chunk = client.recv(4096)
                    except socket.timeout:
                        return None
                    if not chunk:
                        return None
                    buffer += chunk
                    while b"\n" in buffer:
                        raw_line, buffer = buffer.split(b"\n", 1)
                        if not raw_line.strip():
                            continue
                        try:
                            response = json.loads(raw_line.decode("utf-8", "ignore"))
                        except json.JSONDecodeError:
                            continue
                        if response.get("request_id") == request_id:
                            return response if isinstance(response, dict) else None
        except OSError:
            return None
        return None

    def load(self, path: pathlib.Path) -> str:
        response = self.ipc_request(["loadfile", str(path), "replace"], timeout_sec=1.0)
        if not response:
            return "no_response"
        return str(response.get("error") or UNKNOWN)

    def path_loaded(self, path: pathlib.Path, timeout_sec: float = 1.5) -> str:
        expected = str(path)
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            response = self.ipc_request(["get_property", "path"], timeout_sec=0.5)
            if response and response.get("error") == "success" and response.get("data") == expected:
                return "loaded"
            time.sleep(0.03)
        return "not_confirmed"


def render_event(
    *,
    renderer: MPMVRenderer,
    screens_dir: pathlib.Path,
    spec: MethodSpec,
    method_dir: pathlib.Path,
    event_seq: int,
    event_name: str,
    state_before: str,
    state_after: str,
    expected_screen_label: str,
    input_label: str,
) -> dict[str, Any]:
    color = ("#1d4ed8", "#047857", "#7c3aed", "#b45309", "#be123c", "#0f766e")[event_seq % 6]
    svg = synthetic_svg(expected_screen_label, event_seq, event_name, color)
    svg_hash = sha256_text(svg)
    svg_path = method_dir / ("screen.svg" if spec.same_path else f"screen-{event_seq:04d}.svg")
    timestamp_input = now()
    timestamp_svg_written = now()
    atomic_write_private_text(svg_path, svg, method_dir, fsync_file=spec.fsync_svg)

    before_fb = framebuffer_snapshot_hash()
    timestamp_render_command = now()
    mpv_command_sent = "start" if event_seq == 0 or spec.restart_mpv else "loadfile_replace"
    if event_seq == 0 or spec.restart_mpv:
        command_result = renderer.start(svg_path)
    else:
        command_result = renderer.load(svg_path)
        if DOUBLE_LOAD_PER_SCREEN and command_result == "success":
            renderer.path_loaded(svg_path, timeout_sec=1.0)
            second_result = renderer.load(svg_path)
            command_result = "success" if second_result == "success" else f"success_then_{second_result}"
    path_confirm = renderer.path_loaded(svg_path) if spec.wait_ipc_path or event_seq == 0 or spec.restart_mpv else "not_requested"
    time.sleep(PRESENT_SETTLE_SEC)
    after_fb = framebuffer_snapshot_hash()
    fb_changed = (
        before_fb.get("available") is True
        and after_fb.get("available") is True
        and before_fb.get("hash") != after_fb.get("hash")
    )
    return {
        "event_seq": event_seq,
        "event_name": event_name,
        "input_label": input_label,
        "timestamp_input": timestamp_input,
        "state_before": state_before,
        "state_after": state_after,
        "render_seq": event_seq,
        "svg_path_public": svg_path.name,
        "svg_hash": svg_hash[:16],
        "timestamp_svg_written": timestamp_svg_written,
        "mpv_command_sent": mpv_command_sent,
        "mpv_command_result": command_result,
        "mpv_path_confirm": path_confirm,
        "timestamp_render_command": timestamp_render_command,
        "expected_screen_label": expected_screen_label,
        "observed_method": "framebuffer_hash" if after_fb.get("available") else "mpv_ipc_only",
        "observed_hash_or_marker": after_fb.get("hash", UNKNOWN),
        "framebuffer_hash_changed_after_render": fb_changed,
        "raw_screen_captured": False,
    }


def run_auto_probe(out_dir: pathlib.Path, *, mpv_bin: str, video_mode: str, methods: list[str]) -> dict[str, Any]:
    prepare_private_dir(out_dir)
    screens_dir = out_dir / "screens"
    prepare_private_dir(screens_dir)
    renderer = MPMVRenderer(out_dir, mpv_bin=mpv_bin, video_mode=video_mode)
    method_results = []
    try:
        for method_name in methods:
            spec = METHOD_SPECS[method_name]
            method_dir = screens_dir / method_name
            prepare_private_dir(method_dir)
            renderer.stop()
            events = []
            previous_state = "BOOT"
            for event_seq, (event_name, state_after, input_label) in enumerate(EVENT_SEQUENCE):
                events.append(
                    render_event(
                        renderer=renderer,
                        screens_dir=screens_dir,
                        spec=spec,
                        method_dir=method_dir,
                        event_seq=event_seq,
                        event_name=event_name,
                        state_before=previous_state,
                        state_after=state_after,
                        expected_screen_label=state_after,
                        input_label=input_label,
                    )
                )
                previous_state = state_after
            method_results.append(
                {
                    "method": method_name,
                    "events": events,
                    "all_mpv_commands_success": all(
                        item["mpv_command_result"] in {"started", "success"} for item in events
                    ),
                    "all_requested_paths_confirmed": all(
                        item["mpv_path_confirm"] in {"loaded", "not_requested"} for item in events
                    ),
                    "framebuffer_available": any(item["observed_method"] == "framebuffer_hash" for item in events),
                    "framebuffer_changed_count": sum(
                        1 for item in events if item["framebuffer_hash_changed_after_render"] is True
                    ),
                }
            )
    finally:
        renderer.stop()

    cause = classify_probe(method_results)
    status = {
        "schema_version": SCHEMA_VERSION,
        "mode": "auto-probe",
        "mpv_video_mode": video_mode,
        "generated_at": now(),
        "methods": method_results,
        "probable_cause": cause,
        "guardrails": guardrails(),
    }
    write_artifacts(out_dir, status)
    return status


class RawKeyboard:
    def __enter__(self) -> "RawKeyboard":
        self.fd = sys.stdin.fileno()
        self.previous = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.previous)


def read_key() -> str:
    data = os.read(sys.stdin.fileno(), 1)
    if data in {b"\r", b"\n"}:
        return "ENTER"
    if data in {b"\x7f", b"\x08"}:
        return "BACKSPACE"
    if data == b"\x1b":
        return "ESC"
    try:
        value = data.decode("utf-8")
    except UnicodeDecodeError:
        return "UNKNOWN"
    if value in {"a", "A"}:
        return "A"
    if value in {"b", "B"}:
        return "B"
    return "OTHER"


def run_manual_check(out_dir: pathlib.Path, *, mpv_bin: str, video_mode: str, method_name: str) -> dict[str, Any]:
    prepare_private_dir(out_dir)
    screens_dir = out_dir / "manual-screens"
    prepare_private_dir(screens_dir)
    spec = METHOD_SPECS[method_name]
    renderer = MPMVRenderer(out_dir, mpv_bin=mpv_bin, video_mode=video_mode)
    events = []
    state = "PRESS_ENTER"
    expected_keys = ["ENTER", "A", "B", "BACKSPACE", "ENTER"]
    labels = {
        "PRESS_ENTER": "PRESSIONE ENTER",
        "PRESS_A": "PRESSIONE A",
        "PRESS_B": "PRESSIONE B",
        "PRESS_BACKSPACE": "PRESSIONE BACKSPACE",
        "PRESS_FINAL_ENTER": "PRESSIONE ENTER FINAL",
        "DONE": "CHECK CONCLUIDO",
        "CANCELLED": "CHECK CANCELADO",
    }

    try:
        with RawKeyboard():
            events.append(
                render_event(
                    renderer=renderer,
                    screens_dir=screens_dir,
                    spec=spec,
                    method_dir=screens_dir,
                    event_seq=0,
                    event_name="manual_initial",
                    state_before="BOOT",
                    state_after=state,
                    expected_screen_label=labels[state],
                    input_label="",
                )
            )
            for index, expected_key in enumerate(expected_keys, start=1):
                key = read_key()
                if key == "ESC":
                    state_after = "CANCELLED"
                    events.append(
                        render_event(
                            renderer=renderer,
                            screens_dir=screens_dir,
                            spec=spec,
                            method_dir=screens_dir,
                            event_seq=index,
                            event_name="manual_cancel",
                            state_before=state,
                            state_after=state_after,
                            expected_screen_label=labels[state_after],
                            input_label="ESC",
                        )
                    )
                    break
                if key != expected_key:
                    state_after = f"EXPECTED_{expected_key}_GOT_{key}"
                elif expected_key == "ENTER" and index == 1:
                    state_after = "PRESS_A"
                elif expected_key == "A":
                    state_after = "PRESS_B"
                elif expected_key == "B":
                    state_after = "PRESS_BACKSPACE"
                elif expected_key == "BACKSPACE":
                    state_after = "PRESS_FINAL_ENTER"
                else:
                    state_after = "DONE"
                events.append(
                    render_event(
                        renderer=renderer,
                        screens_dir=screens_dir,
                        spec=spec,
                        method_dir=screens_dir,
                        event_seq=index,
                        event_name=f"manual_{expected_key.lower()}",
                        state_before=state,
                        state_after=state_after,
                        expected_screen_label=labels.get(state_after, state_after),
                        input_label=key,
                    )
                )
                state = state_after
                if state in {"DONE", "CANCELLED"} or state.startswith("EXPECTED_"):
                    break
    finally:
        renderer.stop()

    status = {
        "schema_version": SCHEMA_VERSION,
        "mode": "manual-check",
        "mpv_video_mode": video_mode,
        "generated_at": now(),
        "method": method_name,
        "events": events,
        "probable_cause": classify_manual_events(events),
        "guardrails": guardrails(),
    }
    write_artifacts(out_dir, status)
    return status


def classify_probe(method_results: list[dict[str, Any]]) -> str:
    if not method_results:
        return UNKNOWN
    for result in method_results:
        if not result["all_mpv_commands_success"]:
            return "mpv_ipc_load_not_presenting_immediately"
    if any(result["framebuffer_available"] for result in method_results):
        if all(result["framebuffer_changed_count"] == 0 for result in method_results):
            return "mpv_ipc_load_not_presenting_immediately"
    if any(result["method"] == "same_path_ipc" and not result["all_requested_paths_confirmed"] for result in method_results):
        return "svg_file_cache_or_same_path"
    if all(result["all_requested_paths_confirmed"] for result in method_results):
        return "unknown"
    return "mpv_ipc_load_not_presenting_immediately"


def classify_manual_events(events: list[dict[str, Any]]) -> str:
    if any(str(event.get("state_after", "")).startswith("EXPECTED_") for event in events):
        return "input_loop_one_step_behind"
    if all(event.get("mpv_command_result") in {"started", "success"} for event in events):
        return "human_validation_required"
    return "mpv_ipc_load_not_presenting_immediately"


def guardrails() -> dict[str, Any]:
    return {
        "writes_only_under_tmp": True,
        "synthetic_screens_only": True,
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "wifi_changed": False,
        "network_changed": False,
        "hotspot_created": False,
        "portal_created": False,
        "reboot_called": False,
        "raw_screenshot_saved": False,
        "credential_values_published": False,
        "network_identifiers_published": False,
    }


def build_summary(status: dict[str, Any]) -> str:
    lines = [
        "Dadooh C9.9.1 visual latency probe",
        "",
        f"schema_version: {status['schema_version']}",
        f"mode: {status['mode']}",
        f"mpv_video_mode: {status.get('mpv_video_mode', UNKNOWN)}",
        f"probable_cause: {status.get('probable_cause', UNKNOWN)}",
        "",
        "Guardrails:",
    ]
    for key, value in status["guardrails"].items():
        lines.append(f"{key}: {str(value).lower()}")
    return "\n".join(lines) + "\n"


def write_artifacts(out_dir: pathlib.Path, status: dict[str, Any]) -> None:
    prepare_private_dir(out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_summary(status), out_dir, fsync_file=True)


def run_self_test() -> None:
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c9-9-1-latency-probe-self-test-", dir="/tmp"))
    try:
        out_dir = require_tmp_dir(str(root / "out"))
        prepare_private_dir(out_dir)
        screens = out_dir / "screens"
        prepare_private_dir(screens)
        svg = synthetic_svg("STATE_TEST", 1, "test", "#1d4ed8")
        path = screens / "screen.svg"
        atomic_write_private_text(path, svg, screens, fsync_file=True)
        assert path.exists()
        assert file_mode(path) == PRIVATE_FILE_MODE
        status = {
            "schema_version": SCHEMA_VERSION,
            "mode": "self-test",
            "probable_cause": "unknown",
            "guardrails": guardrails(),
        }
        write_artifacts(out_dir, status)
        assert (out_dir / STATUS_FILENAME).exists()
        assert file_mode(out_dir) == PRIVATE_DIR_MODE
        assert file_mode(out_dir / STATUS_FILENAME) == PRIVATE_FILE_MODE
        text = (out_dir / SUMMARY_FILENAME).read_text(encoding="utf-8")
        for forbidden in ("ssid", "password", "api_key", "192.168", "environment_id"):
            assert forbidden not in text.lower()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run C9.9.1 synthetic visual latency probe.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--mpv-bin", default="mpv")
    parser.add_argument("--mpv-video-mode", choices=MPV_VIDEO_MODES, default="drm")
    parser.add_argument("--method", choices=METHODS, default="unique_path_ipc_wait")
    parser.add_argument("--methods", default=",".join(METHODS), help="Comma-separated methods for --auto-probe.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-test", action="store_true")
    modes.add_argument("--auto-probe", action="store_true")
    modes.add_argument("--manual-check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        try:
            run_self_test()
        except Exception:
            print("error: self-test failed", file=sys.stderr)
            return 1
        print("self-test: ok")
        return 0
    try:
        out_dir = require_tmp_dir(args.out_dir)
        if args.auto_probe:
            methods = [item.strip() for item in args.methods.split(",") if item.strip()]
            unknown = [item for item in methods if item not in METHOD_SPECS]
            if unknown:
                raise ProbeError("unknown method")
            status = run_auto_probe(out_dir, mpv_bin=args.mpv_bin, video_mode=args.mpv_video_mode, methods=methods)
        else:
            status = run_manual_check(
                out_dir,
                mpv_bin=args.mpv_bin,
                video_mode=args.mpv_video_mode,
                method_name=args.method,
            )
        print(json.dumps(status, indent=2, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        print("error: visual latency probe failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
