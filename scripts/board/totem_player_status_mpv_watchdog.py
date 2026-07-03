#!/usr/bin/env python3
"""Restart the player process when public status advances while MPV is stuck.

This is intentionally outside kiosk.py so it can protect old player-runtime
releases selected by rollback. It observes only local status and MPV IPC state,
logs sanitized aliases, and terminates the player child so the service launcher
can restart it through the normal path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


DEFAULT_CONFIG = Path("/data/config/config.json")
DEFAULT_STATUS = Path("/tmp/kiosky-status.json")
DEFAULT_STATE_FILE = Path("/data/state/kiosky-player/status-mpv-watchdog.json")
DEFAULT_IPC_PATH = Path("/tmp/kiosky/mpv.sock")


def sha1_short(value: Any) -> str:
    return hashlib.sha1(str(value).encode("utf-8"), usedforsecurity=False).hexdigest()[:10]


def safe_alias(value: Any) -> str:
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
    return f"<token:{sha1_short(value)}>"


def normalize_media_identity(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    text = value
    if text.startswith("file://"):
        parsed = urlparse(text)
        text = unquote(parsed.path)
    if text.startswith("/"):
        return os.path.normcase(os.path.abspath(text))
    return text


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def load_paths(config_path: Path, fallback_status: Path) -> tuple[Path, Path]:
    config = load_json(config_path)
    if not isinstance(config, dict):
        return DEFAULT_IPC_PATH, fallback_status
    ipc_path = Path(str(config.get("ipc_path") or DEFAULT_IPC_PATH))
    status_path = Path(str(config.get("status_file") or fallback_status))
    return ipc_path, status_path


def current_status_identity(status_path: Path) -> tuple[str, bool]:
    status = load_json(status_path)
    if not isinstance(status, dict):
        return "", False
    if status.get("playback_state") not in {"playing", "preparing_first_frame"}:
        return "", False
    item = status.get("current_item")
    if not isinstance(item, dict):
        return "", False
    identity = normalize_media_identity(item.get("path"))
    if identity:
        return identity, True
    for key in ("path_alias", "alias"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value, True
    return "", False


def query_mpv_path(ipc_path: Path, timeout_sec: float) -> str:
    if not ipc_path.exists():
        return ""
    request = json.dumps({"command": ["get_property", "path"]}) + "\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_sec)
        sock.connect(str(ipc_path))
        sock.sendall(request.encode("utf-8"))
        deadline = time.monotonic() + timeout_sec
        pending = b""
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            pending += chunk
            lines = pending.splitlines(keepends=True)
            if lines and not lines[-1].endswith(b"\n"):
                pending = lines.pop()
            else:
                pending = b""
            for line in lines:
                try:
                    payload = json.loads(line.decode("utf-8", errors="replace"))
                except Exception:
                    continue
                if "error" not in payload:
                    continue
                if payload.get("error") != "success":
                    return ""
                return normalize_media_identity(payload.get("data"))
    return ""


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


@dataclass
class MismatchTracker:
    max_mismatch_sec: float
    min_status_advances: int
    fault_since: float | None = None
    mpv_identity: str = ""
    status_aliases: set[str] = field(default_factory=set)

    def reset(self) -> None:
        self.fault_since = None
        self.mpv_identity = ""
        self.status_aliases.clear()

    def observe(self, *, status_identity: str, mpv_identity: str, playable: bool, now: float) -> dict[str, Any] | None:
        if not playable or not status_identity or not mpv_identity or status_identity == mpv_identity:
            self.reset()
            return None
        if self.fault_since is None or mpv_identity != self.mpv_identity:
            self.fault_since = now
            self.mpv_identity = mpv_identity
            self.status_aliases = {safe_alias(status_identity)}
            return None
        self.status_aliases.add(safe_alias(status_identity))
        elapsed = max(now - self.fault_since, 0.0)
        if elapsed < self.max_mismatch_sec:
            return None
        if len(self.status_aliases) < self.min_status_advances:
            return None
        return {
            "reason": "status_advanced_without_mpv",
            "elapsed_sec": round(elapsed, 3),
            "mpv_alias": safe_alias(mpv_identity),
            "status_aliases": sorted(self.status_aliases),
            "status_alias_count": len(self.status_aliases),
        }


def terminate_player(pid: int) -> None:
    os.kill(pid, signal.SIGTERM)


def monitor(args: argparse.Namespace) -> int:
    tracker = MismatchTracker(
        max_mismatch_sec=args.max_mismatch_sec,
        min_status_advances=args.min_status_advances,
    )
    while pid_alive(args.pid):
        ipc_path, status_path = load_paths(args.config, args.status)
        try:
            status_identity, playable = current_status_identity(status_path)
            mpv_identity = query_mpv_path(ipc_path, args.ipc_timeout_sec)
        except Exception:
            tracker.reset()
            time.sleep(args.interval_sec)
            continue
        decision = tracker.observe(
            status_identity=status_identity,
            mpv_identity=mpv_identity,
            playable=playable,
            now=time.monotonic(),
        )
        if decision is not None:
            event = {
                "schema": "dadooh.player.status_mpv_watchdog.v1",
                "action": "terminate_player_child",
                "player_pid": args.pid,
                "recorded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                **decision,
            }
            write_json_atomic(args.state_file, event)
            print(
                "player_status_mpv_watchdog terminating child "
                f"pid={args.pid} reason={decision['reason']} "
                f"elapsed_sec={decision['elapsed_sec']} status_alias_count={decision['status_alias_count']}",
                flush=True,
            )
            if not args.dry_run:
                terminate_player(args.pid)
            return 10
        time.sleep(args.interval_sec)
    return 0


def self_test() -> int:
    tracker = MismatchTracker(max_mismatch_sec=4.0, min_status_advances=2)
    assert tracker.observe(status_identity="/data/media/a.mp4", mpv_identity="/data/media/x.mp4", playable=True, now=0.0) is None
    decision = tracker.observe(status_identity="/data/media/b.mp4", mpv_identity="/data/media/x.mp4", playable=True, now=5.0)
    assert decision is not None
    assert decision["reason"] == "status_advanced_without_mpv"
    assert decision["status_alias_count"] == 2

    tracker = MismatchTracker(max_mismatch_sec=4.0, min_status_advances=2)
    assert tracker.observe(status_identity="/data/media/a.mp4", mpv_identity="/data/media/x.mp4", playable=True, now=0.0) is None
    assert tracker.observe(status_identity="/data/media/a.mp4", mpv_identity="/data/media/x.mp4", playable=True, now=10.0) is None
    assert tracker.status_aliases == {safe_alias("/data/media/a.mp4")}

    tracker = MismatchTracker(max_mismatch_sec=4.0, min_status_advances=2)
    assert tracker.observe(status_identity="/data/media/a.mp4", mpv_identity="/data/media/x.mp4", playable=True, now=0.0) is None
    assert tracker.observe(status_identity="/data/media/a.mp4", mpv_identity="/data/media/a.mp4", playable=True, now=2.0) is None
    assert tracker.fault_since is None

    assert safe_alias("/data/media/private.mp4").startswith("<media-path:")
    assert "private.mp4" not in safe_alias("/data/media/private.mp4")
    assert normalize_media_identity("file:///data/media/a%20b.mp4").endswith("/data/media/a b.mp4")
    print("self-test ok")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--interval-sec", type=float, default=2.0)
    parser.add_argument("--max-mismatch-sec", type=float, default=20.0)
    parser.add_argument("--min-status-advances", type=int, default=2)
    parser.add_argument("--ipc-timeout-sec", type=float, default=0.8)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if not args.self_test and args.pid <= 0:
        parser.error("--pid is required unless --self-test is used")
    args.interval_sec = max(args.interval_sec, 0.2)
    args.max_mismatch_sec = max(args.max_mismatch_sec, args.interval_sec)
    args.min_status_advances = max(args.min_status_advances, 2)
    args.ipc_timeout_sec = max(args.ipc_timeout_sec, 0.1)
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        return self_test()
    return monitor(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
