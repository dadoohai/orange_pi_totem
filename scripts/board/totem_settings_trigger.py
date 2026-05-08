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
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any


sys.dont_write_bytecode = True

SCHEMA_VERSION = "dadooh-c10.6-settings-trigger.v1"
REQUEST_SCHEMA_VERSION = 1
DEFAULT_REQUEST_DIR = "/run/dadooh-settings"
REQUEST_FILENAME = "request.json"
STATUS_FILENAME = "trigger-status.json"
SUMMARY_FILENAME = "summary.txt"
DIR_MODE = 0o700
FILE_MODE = 0o600
LOCK_STALE_WARN_SEC = 1800
EV_KEY = 0x01
KEY_F10 = 68
KEY_F12 = 88
KEY_I = 23
KEY_LEFTCTRL = 29
KEY_RIGHTCTRL = 97
ALL_FUNCTION_TRIGGERS = {
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
    def __init__(
        self,
        hold_sec: float = 5.0,
        *,
        enabled_function_triggers: dict[int, str] | None = None,
        enable_ctrl_i: bool = False,
    ) -> None:
        if hold_sec <= 0:
            raise TriggerError("hold_sec_invalid")
        self.hold_sec = hold_sec
        self.enabled_function_triggers = enabled_function_triggers or {KEY_F10: "keyboard_f10_hold"}
        self.enable_ctrl_i = enable_ctrl_i
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
        if self.enable_ctrl_i and event.code in CTRL_KEYS:
            if event.value in {1, 2}:
                if self.ctrl_down_since is None:
                    self.ctrl_down_since = event.timestamp
                if self.i_down_since is not None and self.ctrl_i_down_at is None:
                    self.ctrl_i_down_at = event.timestamp
            elif event.value == 0:
                self.ctrl_down_since = None
                self.ctrl_i_down_at = None
            return self.poll(event.timestamp)
        if self.enable_ctrl_i and event.code == KEY_I:
            if event.value in {1, 2}:
                if self.i_down_since is None:
                    self.i_down_since = event.timestamp
                if self.ctrl_down_since is not None and self.ctrl_i_down_at is None:
                    self.ctrl_i_down_at = event.timestamp
            elif event.value == 0:
                self.i_down_since = None
                self.ctrl_i_down_at = None
            return self.poll(event.timestamp)
        if event.code not in self.enabled_function_triggers:
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
                self.trigger_type = self.enabled_function_triggers.get(code, "unknown")
                return True
        return False

    def reset(self) -> None:
        self.down_since.clear()
        self.ctrl_down_since = None
        self.i_down_since = None
        self.ctrl_i_down_at = None
        self.triggered = False
        self.trigger_type = "unknown"


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
        "schema_version": REQUEST_SCHEMA_VERSION,
        "requested_at": utc_timestamp(),
        "trigger_type": trigger_type,
        "action": "open_settings",
    }


def write_request(request_dir: pathlib.Path, trigger_type: str) -> pathlib.Path:
    target = request_dir / REQUEST_FILENAME
    try:
        target.unlink()
    except FileNotFoundError:
        pass
    atomic_write_json(target, build_request(trigger_type))
    return target


def clear_request(request_dir: pathlib.Path) -> None:
    try:
        (request_dir / REQUEST_FILENAME).unlink()
    except FileNotFoundError:
        pass


def write_status(request_dir: pathlib.Path, status: dict[str, Any]) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": status.get("status", "unknown"),
        "trigger_type": status.get("trigger_type", "keyboard_function_hold"),
        "trigger_detected": bool(status.get("trigger_detected", False)),
        "request_written": bool(status.get("request_written", False)),
        "devices_opened_count": int(status.get("devices_opened_count", 0)),
        "open_service_start_attempted": bool(status.get("open_service_start_attempted", False)),
        "open_service_start_result": status.get("open_service_start_result", "not_requested"),
        "session_lock_active": bool(status.get("session_lock_active", False)),
        "session_lock_age_bucket": status.get("session_lock_age_bucket", "unknown"),
        "open_service_active_state": status.get("open_service_active_state", "unknown"),
        "stale_lock_suspected": bool(status.get("stale_lock_suspected", False)),
        "stale_lock_removed": bool(status.get("stale_lock_removed", False)),
        "cooldown_active": bool(status.get("cooldown_active", False)),
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
            f"open_service_start_result: {payload['open_service_start_result']}",
            f"session_lock_active: {str(payload['session_lock_active']).lower()}",
            f"session_lock_age_bucket: {payload['session_lock_age_bucket']}",
            f"open_service_active_state: {payload['open_service_active_state']}",
            f"stale_lock_suspected: {str(payload['stale_lock_suspected']).lower()}",
            f"stale_lock_removed: {str(payload['stale_lock_removed']).lower()}",
            f"cooldown_active: {str(payload['cooldown_active']).lower()}",
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
    enabled_function_triggers: dict[int, str] | None = None,
    enable_ctrl_i: bool = False,
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

    detector = FunctionHoldDetector(
        hold_sec,
        enabled_function_triggers=enabled_function_triggers,
        enable_ctrl_i=enable_ctrl_i,
    )
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


def run_tty_guard(tty_guard: str, visual_tty: int) -> None:
    if not tty_guard:
        return
    guard_path = pathlib.Path(tty_guard)
    if not guard_path.exists() or guard_path.is_symlink():
        return
    try:
        subprocess.run(
            [str(guard_path), "--clear", "--tty", str(visual_tty)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except Exception:
        return


def trigger_service_start(open_service: str, *, tty_guard: str = "", visual_tty: int = 2) -> str:
    if not open_service:
        return "not_requested"
    run_tty_guard(tty_guard, visual_tty)
    try:
        completed = subprocess.run(
            ["systemctl", "start", open_service],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except Exception:
        return "failed"
    return "started" if completed.returncode == 0 else "failed"


def service_active_state(unit_name: str) -> str:
    if not unit_name:
        return "not_configured"
    try:
        completed = subprocess.run(
            ["systemctl", "is-active", unit_name],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
    except Exception:
        return "unknown"
    value = (completed.stdout or "").strip()
    return value if value else "unknown"


def session_lock_age_bucket(session_lock: pathlib.Path) -> str:
    try:
        age = max(0.0, time.time() - session_lock.stat().st_mtime)
    except OSError:
        return "unknown"
    if age < 60:
        return "lt_1m"
    if age < 300:
        return "1_5m"
    if age < LOCK_STALE_WARN_SEC:
        return "5_30m"
    return "gt_30m"


def session_lock_diagnostic(session_lock: pathlib.Path, open_service: str) -> dict[str, Any]:
    age_bucket = session_lock_age_bucket(session_lock)
    active_state = service_active_state(open_service)
    return {
        "session_lock_age_bucket": age_bucket,
        "open_service_active_state": active_state,
        "stale_lock_suspected": active_state not in {"active", "activating"},
    }


def daemon_wait_timeout(hold_sec: float) -> float:
    return max(float(hold_sec) + 2.0, 8.0)


def remove_stale_session_lock(session_lock: pathlib.Path) -> bool:
    resolved = session_lock.resolve(strict=False)
    if not (str(resolved).startswith("/run/") or str(resolved).startswith("/tmp/")):
        return False
    if not resolved.exists():
        return False
    if resolved.is_dir() and not resolved.is_symlink():
        shutil.rmtree(resolved, ignore_errors=True)
    elif not resolved.is_symlink():
        try:
            resolved.unlink()
        except FileNotFoundError:
            pass
    return not resolved.exists()


def daemon_loop(
    *,
    device_patterns: list[str],
    hold_sec: float,
    request_dir: pathlib.Path,
    session_lock: pathlib.Path,
    open_service: str,
    tty_guard: str,
    visual_tty: int,
    cooldown_sec: float,
    enabled_function_triggers: dict[int, str],
    enable_ctrl_i: bool,
) -> int:
    if cooldown_sec < 0:
        raise TriggerError("cooldown_sec_invalid")
    next_allowed = 0.0
    while True:
        rc = wait_for_function_hold(
            device_patterns=device_patterns,
            hold_sec=hold_sec,
            timeout_sec=daemon_wait_timeout(hold_sec),
            request_dir=request_dir,
            enabled_function_triggers=enabled_function_triggers,
            enable_ctrl_i=enable_ctrl_i,
        )
        if rc == 0:
            status = {}
            try:
                status = json.loads((request_dir / STATUS_FILENAME).read_text(encoding="utf-8"))
            except Exception:
                status = {}
            trigger_type = str(status.get("trigger_type") or "keyboard_f10_hold")
            now = time.monotonic()
            if now < next_allowed:
                clear_request(request_dir)
                write_status(
                    request_dir,
                    {
                        "status": "cooldown",
                        "trigger_type": trigger_type,
                        "trigger_detected": True,
                        "request_written": False,
                        "cooldown_active": True,
                        "devices_opened_count": int(status.get("devices_opened_count", 0) or 0),
                    },
                )
                time.sleep(min(1.0, max(0.0, next_allowed - now)))
                continue
            if session_lock.exists():
                diagnostic = session_lock_diagnostic(session_lock, open_service)
                if diagnostic["stale_lock_suspected"]:
                    removed = remove_stale_session_lock(session_lock)
                    if removed:
                        result = trigger_service_start(open_service, tty_guard=tty_guard, visual_tty=visual_tty)
                        write_status(
                            request_dir,
                            {
                                "status": "open_service_requested_after_stale_lock_cleanup"
                                if result == "started"
                                else "open_service_failed_after_stale_lock_cleanup",
                                "trigger_type": trigger_type,
                                "trigger_detected": True,
                                "request_written": True,
                                "open_service_start_attempted": True,
                                "open_service_start_result": result,
                                "session_lock_active": False,
                                "stale_lock_removed": True,
                                "devices_opened_count": int(status.get("devices_opened_count", 0) or 0),
                                **diagnostic,
                            },
                        )
                        next_allowed = time.monotonic() + cooldown_sec
                        continue
                clear_request(request_dir)
                write_status(
                    request_dir,
                    {
                        "status": "session_lock_active",
                        "trigger_type": trigger_type,
                        "trigger_detected": True,
                        "request_written": False,
                        "session_lock_active": True,
                        "stale_lock_removed": False,
                        "devices_opened_count": int(status.get("devices_opened_count", 0) or 0),
                        **diagnostic,
                    },
                )
                time.sleep(1.0)
                continue
            result = trigger_service_start(open_service, tty_guard=tty_guard, visual_tty=visual_tty)
            write_status(
                request_dir,
                {
                    "status": "open_service_requested" if result == "started" else "open_service_failed",
                    "trigger_type": trigger_type,
                    "trigger_detected": True,
                    "request_written": True,
                    "open_service_start_attempted": True,
                    "open_service_start_result": result,
                    "devices_opened_count": int(status.get("devices_opened_count", 0) or 0),
                },
            )
            next_allowed = time.monotonic() + cooldown_sec
        elif rc in {3, 4, 5, 124}:
            time.sleep(1.0)
        else:
            time.sleep(1.0)


def self_test() -> None:
    detector = FunctionHoldDetector(hold_sec=5.0)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_F12, 1, 0.0))
    assert not detector.poll(4.9)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_F12, 0, 5.1))
    assert not detector.poll(7.0)

    detector = FunctionHoldDetector(hold_sec=5.0)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_F12, 1, 10.0))
    assert not detector.poll(15.0)

    detector = FunctionHoldDetector(hold_sec=5.0)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_F10, 1, 20.0))
    assert detector.poll(25.0)
    assert detector.trigger_type == "keyboard_f10_hold"

    detector = FunctionHoldDetector(hold_sec=5.0)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_LEFTCTRL, 1, 30.0))
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_I, 1, 30.2))
    assert not detector.poll(35.3)

    detector = FunctionHoldDetector(hold_sec=5.0)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_F12, 1, 10.0))
    assert detector.handle_event(KeyEvent(EV_KEY, KEY_F12, 2, 15.1)) is False
    assert not detector.triggered

    detector = FunctionHoldDetector(
        hold_sec=5.0,
        enabled_function_triggers={KEY_F10: "keyboard_f10_hold", KEY_F12: "keyboard_f12_hold"},
    )
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_F12, 1, 10.0))
    assert detector.poll(15.0)
    assert detector.trigger_type == "keyboard_f12_hold"

    detector = FunctionHoldDetector(hold_sec=5.0, enable_ctrl_i=True)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_LEFTCTRL, 1, 30.0))
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_I, 1, 30.2))
    assert not detector.poll(35.1)
    assert detector.poll(35.3)
    assert detector.trigger_type == "keyboard_ctrl_i_hold"

    detector = FunctionHoldDetector(hold_sec=5.0, enable_ctrl_i=True)
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_I, 1, 40.0))
    assert not detector.handle_event(KeyEvent(EV_KEY, KEY_LEFTCTRL, 1, 40.5))
    assert detector.poll(45.5)
    assert detector.trigger_type == "keyboard_ctrl_i_hold"

    detector = FunctionHoldDetector(hold_sec=5.0)
    assert not detector.handle_event(KeyEvent(EV_KEY, 30, 1, 0.0))
    assert not detector.poll(10.0)

    assert daemon_wait_timeout(5.0) > 5.0
    assert daemon_wait_timeout(1.0) >= 8.0

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
        request_payload = json.loads((request_dir / REQUEST_FILENAME).read_text(encoding="utf-8"))
        assert request_payload == {
            "schema_version": REQUEST_SCHEMA_VERSION,
            "requested_at": request_payload["requested_at"],
            "trigger_type": "keyboard_f10_hold",
            "action": "open_settings",
        }
        combined = (request_dir / REQUEST_FILENAME).read_text(encoding="utf-8")
        combined += (request_dir / STATUS_FILENAME).read_text(encoding="utf-8")
        combined += (request_dir / SUMMARY_FILENAME).read_text(encoding="utf-8")
        forbidden = ["TEST_PASSWORD_SHOULD_NOT_LEAK", "TEST_WIFI_SHOULD_NOT_LEAK", "typed-character"]
        for marker in forbidden:
            assert marker not in combined
        assert "stale_lock_suspected" in combined
        assert "stale_lock_removed" in combined
        clear_request(request_dir)
        assert not (request_dir / REQUEST_FILENAME).exists()
        lock = request_dir / "session.lock"
        lock.mkdir()
        assert remove_stale_session_lock(lock)
        assert not lock.exists()
    print("self-test: ok")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dadooh C10.6 local settings trigger")
    parser.add_argument("--request-dir", default=DEFAULT_REQUEST_DIR)
    parser.add_argument("--hold-sec", type=float, default=5.0)
    parser.add_argument("--timeout-sec", type=float, default=0.0)
    parser.add_argument("--cooldown-sec", type=float, default=10.0)
    parser.add_argument("--session-lock", default="/run/totem/settings-session.lock")
    parser.add_argument("--open-service", default="")
    parser.add_argument("--tty-guard", default="/opt/totem/bin/totem_visual_tty_guard.sh")
    parser.add_argument("--visual-tty", type=int, default=2)
    parser.add_argument("--device-glob", action="append", default=["/dev/input/event*"])
    parser.add_argument("--enable-ctrl-i", action="store_true")
    parser.add_argument("--enable-f12", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--wait-once", action="store_true")
    mode.add_argument("--daemon", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    request_dir = require_public_dir(args.request_dir)
    enabled_function_triggers = {KEY_F10: "keyboard_f10_hold"}
    if args.enable_f12:
        enabled_function_triggers[KEY_F12] = "keyboard_f12_hold"
    if args.daemon:
        return daemon_loop(
            device_patterns=list(args.device_glob),
            hold_sec=float(args.hold_sec),
            request_dir=request_dir,
            session_lock=pathlib.Path(args.session_lock),
            open_service=str(args.open_service),
            tty_guard=str(args.tty_guard),
            visual_tty=int(args.visual_tty),
            cooldown_sec=float(args.cooldown_sec),
            enabled_function_triggers=enabled_function_triggers,
            enable_ctrl_i=bool(args.enable_ctrl_i),
        )
    return wait_for_function_hold(
        device_patterns=list(args.device_glob),
        hold_sec=float(args.hold_sec),
        timeout_sec=float(args.timeout_sec),
        request_dir=request_dir,
        enabled_function_triggers=enabled_function_triggers,
        enable_ctrl_i=bool(args.enable_ctrl_i),
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
