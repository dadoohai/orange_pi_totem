#!/usr/bin/env python3
"""C10.6 local trigger for opening Totem settings.

The trigger monitors Linux input events read-only and detects only long product
function-key holds. It does not log typed keys, passwords, SSIDs or any input
payload. When the hold is detected it writes a small public request under /run
or /tmp for a separate session runner to open the existing visual setup wizard.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import pathlib
import select
import stat
import struct
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any


sys.dont_write_bytecode = True

SCHEMA_VERSION = "dadooh-c10.6-settings-trigger.v1"
DEFAULT_REQUEST_DIR = "/run/dadooh-settings"
REQUEST_FILENAME = "request.json"
STATUS_FILENAME = "trigger-status.json"
SUMMARY_FILENAME = "summary.txt"
DIR_MODE = 0o700
FILE_MODE = 0o600
EV_KEY = 0x01
KEY_F10 = 68
KEY_F12 = 88
KEY_I = 23
KEY_LEFTCTRL = 29
KEY_RIGHTCTRL = 97
TRIGGER_KEYS = {
    KEY_F10: "keyboard_f10_hold",
    KEY_F12: "keyboard_f12_hold",
}
CTRL_KEYS = {KEY_LEFTCTRL, KEY_RIGHTCTRL}
INPUT_EVENT = struct.Struct("llHHI")


class TriggerError(RuntimeError):
    """Public-safe trigger failure."""


@dataclass
class KeyEvent:
    event_type: int
    code: int
    value: int
    timestamp: float


class FunctionHoldDetector:
    def __init__(self, hold_sec: float = 5.0) -> None:
        if hold_sec <= 0:
            raise TriggerError("hold_sec_invalid")
        self.hold_sec = hold_sec
        self.down_since: dict[int, float] = {}
        self.ctrl_down_since: float | None = None
        self.i_down_since: float | None = None
        self.ctrl_i_down_at: float | None = None
        self.triggered = False
        self.trigger_type = "unknown"

    def handle_event(self, event: KeyEvent) -> bool:
        if self.triggered:
            return True
        if event.event_type != EV_KEY:
            return False
        if event.code in CTRL_KEYS:
            if event.value in {1, 2}:
                if self.ctrl_down_since is None:
                    self.ctrl_down_since = event.timestamp
                if self.i_down_since is not None and self.ctrl_i_down_at is None:
                    self.ctrl_i_down_at = event.timestamp
            elif event.value == 0:
                self.ctrl_down_since = None
                self.ctrl_i_down_at = None
            return self.poll(event.timestamp)
        if event.code == KEY_I:
            if event.value in {1, 2}:
                if self.i_down_since is None:
                    self.i_down_since = event.timestamp
                if self.ctrl_down_since is not None and self.ctrl_i_down_at is None:
                    self.ctrl_i_down_at = event.timestamp
            elif event.value == 0:
                self.i_down_since = None
                self.ctrl_i_down_at = None
            return self.poll(event.timestamp)
        if event.code not in TRIGGER_KEYS:
            return False
        if event.value in {1, 2}:
            if event.code not in self.down_since:
                self.down_since[event.code] = event.timestamp
            return self.poll(event.timestamp)
        if event.value == 0:
            self.down_since.pop(event.code, None)
        return False

    def poll(self, now: float) -> bool:
        if self.triggered:
            return True
        if self.ctrl_i_down_at is not None and now - self.ctrl_i_down_at >= self.hold_sec:
            self.triggered = True
            self.trigger_type = "keyboard_ctrl_i_hold"
            return True
        for code, started_at in list(self.down_since.items()):
            if now - started_at >= self.hold_sec:
                self.triggered = True
                self.trigger_type = TRIGGER_KEYS.get(code, "unknown")
                return True
        return False


def require_public_dir(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    if path.is_symlink():
        raise TriggerError("request_dir_symlink")
    resolved = path.resolve(strict=False)
    if not (str(resolved).startswith("/run/") or str(resolved).startswith("/tmp/")):
        raise TriggerError("request_dir_must_be_run_or_tmp")
    if resolved.exists() and not resolved.is_dir():
        raise TriggerError("request_dir_not_directory")
    resolved.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
    if stat.S_IMODE(resolved.stat().st_mode) != DIR_MODE:
        resolved.chmod(DIR_MODE)
    return resolved


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


def atomic_write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    fd: int | None = None
    tmp_name: str | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent), text=True)
        os.fchmod(fd, FILE_MODE)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
        path.chmod(FILE_MODE)
        fsync_directory(path.parent)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_request(trigger_type: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "requested_at": utc_timestamp(),
        "trigger_type": trigger_type,
        "action": "open_settings",
    }


def write_request(request_dir: pathlib.Path, trigger_type: str) -> pathlib.Path:
    target = request_dir / REQUEST_FILENAME
    atomic_write_json(target, build_request(trigger_type))
    return target


def write_status(request_dir: pathlib.Path, status: dict[str, Any]) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": status.get("status", "unknown"),
        "trigger_type": status.get("trigger_type", "keyboard_function_hold"),
        "trigger_detected": bool(status.get("trigger_detected", False)),
        "request_written": bool(status.get("request_written", False)),
        "devices_opened_count": int(status.get("devices_opened_count", 0)),
        "raw_key_values_logged": False,
        "characters_logged": False,
        "credentials_collected": False,
    }
    atomic_write_json(request_dir / STATUS_FILENAME, payload)
    summary = "\n".join(
        [
            "Dadooh C10.6 settings trigger",
            "",
            f"schema_version: {SCHEMA_VERSION}",
            f"status: {payload['status']}",
            f"trigger_type: {payload['trigger_type']}",
            f"trigger_detected: {str(payload['trigger_detected']).lower()}",
            f"request_written: {str(payload['request_written']).lower()}",
            "raw_key_values_logged: false",
            "characters_logged: false",
            "credentials_collected: false",
        ]
    )
    summary_path = request_dir / SUMMARY_FILENAME
    tmp = summary_path.with_name(f".{summary_path.name}.{os.getpid()}.tmp")
    tmp.write_text(summary + "\n", encoding="utf-8")
    tmp.chmod(FILE_MODE)
    os.replace(tmp, summary_path)
    summary_path.chmod(FILE_MODE)


def discover_devices(patterns: list[str]) -> list[pathlib.Path]:
    found: list[pathlib.Path] = []
    for pattern in patterns:
        for raw in sorted(glob.glob(pattern)):
            path = pathlib.Path(raw)
            if path.exists() and not path.is_symlink() and path.is_char_device():
                found.append(path)
    seen: set[str] = set()
    unique: list[pathlib.Path] = []
    for path in found:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def parse_input_events(data: bytes, timestamp: float) -> list[KeyEvent]:
    events: list[KeyEvent] = []
    usable = len(data) - (len(data) % INPUT_EVENT.size)
    for offset in range(0, usable, INPUT_EVENT.size):
        try:
            _, _, event_type, code, value = INPUT_EVENT.unpack_from(data, offset)
        except struct.error:
            continue
        events.append(KeyEvent(int(event_type), int(code), int(value), timestamp))
    return events


def wait_for_function_hold(
    *,
    device_patterns: list[str],
    hold_sec: float,
    timeout_sec: float,
    request_dir: pathlib.Path,
) -> int:
    devices = discover_devices(device_patterns)
    if not devices:
        write_status(
            request_dir,
            {
                "status": "no_input_devices",
                "trigger_detected": False,
                "request_written": False,
                "devices_opened_count": 0,
            },
        )
        return 3

    fds: dict[int, Any] = {}
    for path in devices:
        try:
            handle = path.open("rb", buffering=0)
            os.set_blocking(handle.fileno(), False)
            fds[handle.fileno()] = handle
        except OSError:
            continue
    if not fds:
        write_status(
            request_dir,
            {
                "status": "input_devices_unreadable",
                "trigger_detected": False,
                "request_written": False,
                "devices_opened_count": 0,
            },
        )
        return 4

    detector = FunctionHoldDetector(hold_sec)
    deadline = time.monotonic() + timeout_sec if timeout_sec > 0 else None
    try:
        while True:
            now = time.monotonic()
            if detector.poll(now):
                write_request(request_dir, detector.trigger_type)
                write_status(
                    request_dir,
                    {
                        "status": "trigger_detected",
                        "trigger_type": detector.trigger_type,
                        "trigger_detected": True,
                        "request_written": True,
                        "devices_opened_count": len(fds),
                    },
                )
                return 0
            if deadline is not None and now >= deadline:
                write_status(
                    request_dir,
                    {
                        "status": "timeout",
                        "trigger_detected": False,
                        "request_written": False,
                        "devices_opened_count": len(fds),
                    },
                )
                return 124
            wait_sec = 0.1
            if deadline is not None:
                wait_sec = max(0.0, min(wait_sec, deadline - now))
            readable, _, _ = select.select(list(fds.keys()), [], [], wait_sec)
            for fd in readable:
                handle = fds.get(fd)
                if handle is None:
                    continue
                try:
                    data = handle.read(INPUT_EVENT.size * 16)
                except BlockingIOError:
                    continue
                except OSError:
                    try:
                        handle.close()
                    finally:
                        fds.pop(fd, None)
                    continue
                if not data:
                    continue
                timestamp = time.monotonic()
                for event in parse_input_events(data, timestamp):
                    if detector.handle_event(event):
                        write_request(request_dir, detector.trigger_type)
                        write_status(
                            request_dir,
                            {
                                "status": "trigger_detected",
                                "trigger_type": detector.trigger_type,
                                "trigger_detected": True,
                                "request_written": True,
                                "devices_opened_count": len(fds),
                            },
                        )
                        return 0
            if not fds:
                write_status(
                    request_dir,
                    {
                        "status": "input_devices_disconnected",
                        "trigger_detected": False,
                        "request_written": False,
                        "devices_opened_count": 0,
                    },
                )
                return 5
    finally:
        for handle in list(fds.values()):
            try:
                handle.close()
            except OSError:
                pass


def self_test() -> None:
    detector = FunctionHoldDetector(hold_sec=5.0)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_F12, 1, 0.0))
    assert not detector.poll(4.9)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_F12, 0, 5.1))
    assert not detector.poll(7.0)

    detector = FunctionHoldDetector(hold_sec=5.0)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_F12, 1, 10.0))
    assert detector.poll(15.0)
    assert detector.trigger_type == "keyboard_f12_hold"

    detector = FunctionHoldDetector(hold_sec=5.0)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_F10, 1, 20.0))
    assert detector.poll(25.0)
    assert detector.trigger_type == "keyboard_f10_hold"

    detector = FunctionHoldDetector(hold_sec=5.0)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_LEFTCTRL, 1, 30.0))
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_I, 1, 30.2))
    assert not detector.poll(35.1)
    assert detector.poll(35.3)
    assert detector.trigger_type == "keyboard_ctrl_i_hold"

    detector = FunctionHoldDetector(hold_sec=5.0)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_I, 1, 40.0))
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_LEFTCTRL, 1, 40.5))
    assert detector.poll(45.5)
    assert detector.trigger_type == "keyboard_ctrl_i_hold"

    detector = FunctionHoldDetector(hold_sec=5.0)
    assert not detector.handle_event(KeyEvent(EV_KEY, 30, 1, 0.0))
    assert not detector.poll(10.0)

    with tempfile.TemporaryDirectory(prefix="dadooh-trigger-self-test-") as raw:
        request_dir = require_public_dir(raw)
        write_request(request_dir, "keyboard_f10_hold")
        write_status(
            request_dir,
            {
                "status": "trigger_detected",
                "trigger_type": "keyboard_f10_hold",
                "trigger_detected": True,
                "request_written": True,
                "devices_opened_count": 1,
            },
        )
        combined = (request_dir / REQUEST_FILENAME).read_text(encoding="utf-8")
        combined += (request_dir / STATUS_FILENAME).read_text(encoding="utf-8")
        combined += (request_dir / SUMMARY_FILENAME).read_text(encoding="utf-8")
        forbidden = ["TEST_PASSWORD_SHOULD_NOT_LEAK", "TEST_WIFI_SHOULD_NOT_LEAK", "typed-character"]
        for marker in forbidden:
            assert marker not in combined
    print("self-test: ok")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dadooh C10.6 local settings trigger")
    parser.add_argument("--request-dir", default=DEFAULT_REQUEST_DIR)
    parser.add_argument("--hold-sec", type=float, default=5.0)
    parser.add_argument("--timeout-sec", type=float, default=0.0)
    parser.add_argument("--device-glob", action="append", default=["/dev/input/event*"])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--wait-once", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    request_dir = require_public_dir(args.request_dir)
    return wait_for_function_hold(
        device_patterns=list(args.device_glob),
        hold_sec=float(args.hold_sec),
        timeout_sec=float(args.timeout_sec),
        request_dir=request_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
