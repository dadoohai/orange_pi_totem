#!/usr/bin/env python3
"""Collect a sanitized C18 display-profile baseline.

This collector is read-only. It records connector mode negotiation signals that
matter for choosing a future display profile, including EDID size/hash, but it
never copies raw EDID bytes, framebuffer pixels, config content, media, journal
or network data.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.display_profile_baseline.v1"
COLLECTOR_VERSION = 1
DEFAULT_DRM_ROOT = Path("/sys/class/drm")
DEFAULT_STATUS_FILE = Path("/tmp/kiosky-status.json")
DEFAULT_SERVICE = "kiosky-player.service"
TMP_ROOT = Path("/tmp").resolve()
SAFE_CONNECTOR_RE = re.compile(r"[^A-Za-z0-9_.:-]+")
SAFE_MODE_RE = re.compile(r"^[0-9]{3,5}x[0-9]{3,5}(?:[ip]?[0-9]{1,3})?$")
MAX_MODES = 64
MAX_EDID_BYTES_HASHED = 65536


def utc_timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def path_is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def require_tmp_output(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    if not path_is_under(resolved, TMP_ROOT) or resolved == TMP_ROOT:
        raise ValueError("output must be a file under /tmp")
    return resolved


def read_text(path: Path, *, max_bytes: int = 8192) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_bytes].strip()
    except OSError:
        return ""


def connector_label(path: Path) -> str:
    name = SAFE_CONNECTOR_RE.sub("_", path.name)
    if "-" in name:
        return name.split("-", 1)[1]
    return name


def safe_modes(raw: str) -> list[str]:
    modes: list[str] = []
    for line in raw.splitlines():
        mode = line.strip()
        if not mode or not SAFE_MODE_RE.fullmatch(mode):
            continue
        if mode not in modes:
            modes.append(mode)
        if len(modes) >= MAX_MODES:
            break
    return modes


def mode_area(mode: str) -> int:
    try:
        match = re.fullmatch(r"([0-9]{3,5})x([0-9]{3,5})(?:[ip]?[0-9]{1,3})?", mode)
        if not match:
            return 0
        return int(match.group(1)) * int(match.group(2))
    except Exception:
        return 0


def edid_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "present": False,
            "bytes": 0,
            "sha256": "",
            "empty": True,
            "raw_edid_included": False,
        }
    try:
        data = path.read_bytes()
    except OSError:
        return {
            "present": True,
            "bytes": 0,
            "sha256": "",
            "empty": True,
            "read_error": True,
            "raw_edid_included": False,
        }
    if len(data) > MAX_EDID_BYTES_HASHED:
        data = data[:MAX_EDID_BYTES_HASHED]
    return {
        "present": True,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "empty": len(data) == 0,
        "raw_edid_included": False,
    }


def connector_summary(path: Path) -> dict[str, Any]:
    modes = safe_modes(read_text(path / "modes", max_bytes=16384))
    mode = read_text(path / "mode", max_bytes=128)
    if mode and not SAFE_MODE_RE.fullmatch(mode):
        mode = ""
    return {
        "connector": connector_label(path),
        "status": read_text(path / "status", max_bytes=128).lower() or "unknown",
        "enabled": read_text(path / "enabled", max_bytes=128).lower() or "unknown",
        "dpms": read_text(path / "dpms", max_bytes=128) or "unknown",
        "mode": mode,
        "mode_present": bool(mode),
        "modes": modes,
        "modes_count": len(modes),
        "max_mode_area": max((mode_area(item) for item in modes), default=0),
        "edid": edid_summary(path / "edid"),
    }


def collect_drm(root: Path) -> dict[str, Any]:
    connectors = []
    if root.exists():
        for path in sorted(root.glob("card*-*")):
            if path.is_dir() and any((path / field).exists() for field in ("status", "enabled", "modes", "edid")):
                connectors.append(connector_summary(path))
    connected = [item for item in connectors if item.get("status") == "connected"]
    return {
        "present": root.exists(),
        "connectors": connectors,
        "connected_count": len(connected),
        "connected_enabled_count": sum(1 for item in connected if item.get("enabled") == "enabled"),
        "connected_with_empty_edid_count": sum(1 for item in connected if item.get("edid", {}).get("empty") is True),
        "connected_with_modes_count": sum(1 for item in connected if int(item.get("modes_count") or 0) > 0),
        "connected_low_mode_only_count": sum(
            1
            for item in connected
            if int(item.get("max_mode_area") or 0) > 0 and int(item.get("max_mode_area") or 0) < 1280 * 720
        ),
    }


def parse_cmdline(path: Path = Path("/proc/cmdline")) -> dict[str, Any]:
    raw = read_text(path, max_bytes=4096)
    video_tokens = [part for part in raw.split() if part.startswith("video=")]
    safe_video_tokens = []
    for token in video_tokens:
        if re.fullmatch(r"video=[A-Za-z0-9_.:-]+(?::[A-Za-z0-9_.@:-]+)?", token):
            safe_video_tokens.append(token)
    return {
        "raw_cmdline_included": False,
        "video_override_present": bool(safe_video_tokens),
        "video_overrides": safe_video_tokens[:8],
    }


def collect_service(service: str) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["systemctl", "is-active", service],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except Exception as exc:
        return {"service": service, "active_state": "unavailable", "error": type(exc).__name__}
    return {"service": service, "active_state": (proc.stdout or "").strip().lower() or "unknown", "returncode": proc.returncode}


def load_player_status(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"present": False}
    except Exception:
        return {"present": True, "parse_error": True}
    if not isinstance(raw, dict):
        return {"present": True, "parse_error": True}
    return {
        "present": True,
        "playback_state": str(raw.get("playback_state") or "")[:32],
        "player_state": str(raw.get("player_state") or "")[:32],
        "startup_phase": str(raw.get("startup_phase") or "")[:48],
        "mpv_running": raw.get("mpv_running") if isinstance(raw.get("mpv_running"), bool) else None,
        "playlist_size": int(raw.get("playlist_size") or 0) if str(raw.get("playlist_size") or "0").isdigit() else 0,
        "current_index": int(raw.get("current_index") or 0) if str(raw.get("current_index") or "0").isdigit() else 0,
        "first_frame_ready": raw.get("first_frame_ready") if isinstance(raw.get("first_frame_ready"), bool) else None,
        "last_render_error": "present" if raw.get("last_render_error") not in (None, "", False, "null") else "null",
        "black_screen_risk_reason": "present" if raw.get("black_screen_risk_reason") not in (None, "", False, "null") else "null",
    }


def classify(drm: dict[str, Any], cmdline: dict[str, Any]) -> str:
    if int(drm.get("connected_count") or 0) <= 0:
        return "no_sink"
    if cmdline.get("video_override_present") is True:
        return "forced_mode_requested"
    if int(drm.get("connected_with_empty_edid_count") or 0) > 0 and int(drm.get("connected_low_mode_only_count") or 0) > 0:
        return "edid_missing_low_mode_fallback"
    if int(drm.get("connected_with_empty_edid_count") or 0) > 0:
        return "edid_missing"
    if int(drm.get("connected_with_modes_count") or 0) > 0:
        return "auto_negotiated_modes_present"
    return "unknown"


def build_result(args: argparse.Namespace) -> dict[str, Any]:
    started = utc_timestamp()
    drm = collect_drm(args.drm_root)
    cmdline = parse_cmdline(args.cmdline)
    return {
        "schema": SCHEMA,
        "collector_version": COLLECTOR_VERSION,
        "passed": True,
        "result_claim": "read_only_display_profile_baseline_collected",
        "classification": classify(drm, cmdline),
        "started_at_utc": started,
        "ended_at_utc": utc_timestamp(),
        "drm": drm,
        "cmdline": cmdline,
        "service": collect_service(args.service),
        "player_status": load_player_status(args.status_file),
        "collection_policy": {
            "read_only": True,
            "reads_edid_size_and_hash": True,
            "includes_raw_edid": False,
            "reads_framebuffer_pixels": False,
            "reads_config_content": False,
            "reads_media": False,
            "reads_journal": False,
            "uses_network": False,
            "mutates_player": False,
            "mutates_display": False,
            "raw_cmdline_included": False,
        },
        "non_claims": [
            "this_collector_does_not_start_stop_restart_or_signal_player",
            "this_collector_does_not_force_resolution_or_modeset",
            "this_collector_does_not_include_raw_edid_or_framebuffer",
            "this_collector_does_not_read_config_content_media_journal_or_network",
            "this_collector_does_not_validate_playback_decode_health",
            "this_collector_does_not_replace_powerloss_soak_h2_stable_or_thaw",
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    out = require_tmp_output(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(out, 0o600)
    except OSError:
        pass


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--drm-root", type=Path, default=DEFAULT_DRM_ROOT)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS_FILE)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--cmdline", type=Path, default=Path("/proc/cmdline"))
    parser.add_argument("--self-test", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(DisplayProfileBaselineSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    payload = build_result(args)
    if args.output:
        write_json(args.output, payload)
    if args.json or not args.output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


class DisplayProfileBaselineSelfTest(unittest.TestCase):
    def write_connector(self, root: Path, name: str, *, edid: bytes, modes: str, status: str = "connected") -> None:
        path = root / name
        path.mkdir(parents=True)
        (path / "status").write_text(status + "\n", encoding="utf-8")
        (path / "enabled").write_text(("enabled" if status == "connected" else "disabled") + "\n", encoding="utf-8")
        (path / "dpms").write_text("On\n", encoding="utf-8")
        (path / "modes").write_text(modes, encoding="utf-8")
        (path / "edid").write_bytes(edid)

    def test_empty_edid_low_mode_classifies_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_connector(root, "card0-HDMI-A-1", edid=b"", modes="1024x768\n800x600\n")
            args = argparse.Namespace(drm_root=root, status_file=root / "missing.json", service="missing.service", cmdline=root / "cmdline")
            (root / "cmdline").write_text("root=UUID=abc quiet\n", encoding="utf-8")
            result = build_result(args)
        self.assertEqual(result["classification"], "edid_missing_low_mode_fallback")
        edid = result["drm"]["connectors"][0]["edid"]
        self.assertEqual(edid["bytes"], 0)
        self.assertFalse(edid["raw_edid_included"])

    def test_non_empty_edid_does_not_include_raw_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_connector(root, "card0-HDMI-A-1", edid=b"\x00" * 128, modes="1920x1080\n1280x720\n")
            args = argparse.Namespace(drm_root=root, status_file=root / "missing.json", service="missing.service", cmdline=root / "cmdline")
            (root / "cmdline").write_text("root=UUID=abc quiet\n", encoding="utf-8")
            result = build_result(args)
        edid = result["drm"]["connectors"][0]["edid"]
        self.assertEqual(edid["bytes"], 128)
        self.assertEqual(len(edid["sha256"]), 64)
        self.assertNotIn("raw", edid)
        self.assertFalse(edid["raw_edid_included"])
        self.assertEqual(result["classification"], "auto_negotiated_modes_present")

    def test_mode_area_ignores_refresh_suffix(self) -> None:
        self.assertEqual(mode_area("1920x1080p60"), 1920 * 1080)
        self.assertEqual(mode_area("1280x720i50"), 1280 * 720)

    def test_video_override_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_connector(root, "card0-HDMI-A-1", edid=b"", modes="1024x768\n")
            (root / "cmdline").write_text("root=UUID=abc video=HDMI-A-1:1280x720@60 quiet\n", encoding="utf-8")
            args = argparse.Namespace(drm_root=root, status_file=root / "missing.json", service="missing.service", cmdline=root / "cmdline")
            result = build_result(args)
        self.assertEqual(result["classification"], "forced_mode_requested")
        self.assertTrue(result["cmdline"]["video_override_present"])
        self.assertEqual(result["cmdline"]["video_overrides"], ["video=HDMI-A-1:1280x720@60"])
        self.assertFalse(result["cmdline"]["raw_cmdline_included"])


if __name__ == "__main__":
    raise SystemExit(main())
