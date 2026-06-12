#!/usr/bin/env python3
"""Collect sanitized read-only C18 display/player status.

This collector helps distinguish connector/sink issues from player pipeline
issues during homologation and field triage. It reads only public local status:
DRM connector state from sysfs, systemd active state, and the sanitized player
status file. It does not read EDID, framebuffer pixels, media, config, logs, or
network resources, and it never starts, stops, restarts or signals the player.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.display_status.v1"
COLLECTOR_VERSION = 1
DEFAULT_DRM_ROOT = Path("/sys/class/drm")
DEFAULT_STATUS_FILE = Path("/tmp/kiosky-status.json")
DEFAULT_SERVICE = "kiosky-player.service"
VISIBLE_STATES = ("unknown", "ok", "black", "frozen", "looping_same_media", "startup_screen")
DRM_TEXT_FIELDS = ("status", "enabled", "mode", "modes")
ERROR_STATES = {"error", "failed", "fatal"}
RUNNING_STATES = {"playing", "buffering", "running"}
PUBLIC_STATE_VALUES = (
    ERROR_STATES
    | RUNNING_STATES
    | {
        "idle",
        "loading",
        "starting",
        "stopped",
        "unknown",
        "player_starting",
        "waiting_for_api",
        "waiting_for_playlist",
        "waiting_for_media_cache",
        "waiting_for_media",
        "waiting_for_content",
        "preparing_first_frame",
    }
)
SAFE_CONNECTOR_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


def utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_text(path: Path, *, max_bytes: int = 8192) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(max_bytes).strip()
    except OSError:
        return ""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return {"_parse_error": True}


def safe_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return None


def safe_int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return 0


def safe_state(value: Any) -> str:
    return str(value or "").strip().lower()


def safe_public_state(value: Any) -> str:
    state = safe_state(value)
    if not state:
        return ""
    return state if state in PUBLIC_STATE_VALUES else "present"


def connector_label(path: Path) -> str:
    name = SAFE_CONNECTOR_RE.sub("_", path.name)
    if "-" in name:
        return name.split("-", 1)[1]
    return name


def connector_summary(path: Path) -> dict[str, Any]:
    status = read_text(path / "status", max_bytes=128).lower()
    enabled = read_text(path / "enabled", max_bytes=128).lower()
    mode_file = path / "mode"
    mode_observed = mode_file.exists()
    mode = read_text(mode_file, max_bytes=128)
    modes = [line.strip() for line in read_text(path / "modes").splitlines() if line.strip()]
    return {
        "connector": connector_label(path),
        "status": status or "unknown",
        "enabled": enabled or "unknown",
        "enabled_active": enabled == "enabled",
        "mode_observed": mode_observed,
        "mode_present": bool(mode),
        "modes_count": len(modes),
    }


def collect_drm(root: Path) -> dict[str, Any]:
    if not root.exists():
        return {
            "present": False,
            "connectors": [],
            "connected_count": 0,
            "modes_present_count": 0,
        }
    connectors: list[dict[str, Any]] = []
    for path in sorted(root.glob("card*-*")):
        if not path.is_dir():
            continue
        if not any((path / field).exists() for field in DRM_TEXT_FIELDS):
            continue
        connectors.append(connector_summary(path))
    return {
        "present": True,
        "connectors": connectors,
        "connected_count": sum(1 for item in connectors if item.get("status") == "connected"),
        "modes_present_count": sum(1 for item in connectors if safe_int(item.get("modes_count")) > 0),
        "connected_active_count": sum(
            1
            for item in connectors
            if (
                item.get("status") == "connected"
                and item.get("enabled_active") is True
                and safe_int(item.get("modes_count")) > 0
            )
        ),
        "connected_ready_count": sum(
            1
            for item in connectors
            if (
                item.get("status") == "connected"
                and item.get("mode_present") is True
                and safe_int(item.get("modes_count")) > 0
            )
        ),
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
    state = (proc.stdout or "").strip().lower()
    return {
        "service": service,
        "active_state": state or "unknown",
        "returncode": proc.returncode,
    }


def sanitize_error(value: Any) -> str:
    if value in (None, "", False, "null"):
        return "null"
    return "present"


def sanitize_player_status(path: Path) -> dict[str, Any]:
    raw = load_json(path)
    if raw is None:
        return {"present": False}
    if not isinstance(raw, dict) or raw.get("_parse_error"):
        return {"present": True, "parse_error": True}
    return {
        "present": True,
        "playback_state": safe_public_state(raw.get("playback_state")),
        "player_state": safe_public_state(raw.get("player_state")),
        "startup_phase": safe_public_state(raw.get("startup_phase")),
        "mpv_running": safe_bool(raw.get("mpv_running")),
        "playlist_size": safe_int(raw.get("playlist_size")),
        "current_index": safe_int(raw.get("current_index")),
        "consecutive_failures": safe_int(raw.get("consecutive_failures")),
        "blocked_media_count": safe_int(raw.get("blocked_media_count")),
        "last_poll_error": sanitize_error(raw.get("last_poll_error")),
        "last_render_error": sanitize_error(raw.get("last_render_error")),
        "black_screen_risk_reason": sanitize_error(raw.get("black_screen_risk_reason")),
    }


def player_has_error(status: dict[str, Any]) -> bool:
    if status.get("parse_error"):
        return True
    states = {safe_state(status.get("playback_state")), safe_state(status.get("player_state"))}
    if states & ERROR_STATES:
        return True
    if safe_int(status.get("consecutive_failures")) > 0:
        return True
    if safe_int(status.get("blocked_media_count")) > 0:
        return True
    return any(
        status.get(key) == "present"
        for key in ("last_poll_error", "last_render_error", "black_screen_risk_reason")
    )


def player_is_running(status: dict[str, Any]) -> bool:
    states = {safe_state(status.get("playback_state")), safe_state(status.get("player_state"))}
    return bool(states & RUNNING_STATES) or status.get("mpv_running") is True


def classify(
    drm: dict[str, Any],
    service: dict[str, Any],
    player_status: dict[str, Any],
    visible_state: str,
) -> str:
    if drm.get("present") is False:
        return "unknown"
    if safe_int(drm.get("connected_count")) <= 0:
        return "no_sink"
    scanout_ready = safe_int(drm.get("connected_ready_count")) > 0
    scanout_indeterminate = not scanout_ready and safe_int(drm.get("connected_active_count")) > 0

    service_active = service.get("active_state") == "active"
    has_status = player_status.get("present") is True
    has_error = has_status and player_has_error(player_status)
    running = has_status and player_is_running(player_status)
    board_healthy = service_active and running and not has_error

    if visible_state in {"black", "frozen"} and board_healthy and scanout_ready:
        return "sink_hung_board_healthy"
    if visible_state == "ok" and board_healthy and (scanout_ready or scanout_indeterminate):
        return "display_ok"
    if visible_state == "looping_same_media":
        return "pipeline_stalled"
    if not scanout_ready or has_error or (service_active and has_status and not running):
        if scanout_indeterminate and board_healthy:
            return "unknown"
        return "pipeline_stalled"
    if board_healthy:
        return "display_ok"
    return "unknown"


def build_result(args: argparse.Namespace) -> dict[str, Any]:
    started = utc_timestamp()
    drm = collect_drm(args.drm_root)
    service = collect_service(args.service)
    player_status = sanitize_player_status(args.status_file)
    classification = classify(drm, service, player_status, args.visible_state)
    return {
        "schema": SCHEMA,
        "collector_version": COLLECTOR_VERSION,
        "passed": True,
        "result_claim": "read_only_display_status_collected",
        "classification": classification,
        "started_at_utc": started,
        "ended_at_utc": utc_timestamp(),
        "collection_policy": {
            "read_only": True,
            "drm_fields": list(DRM_TEXT_FIELDS),
            "reads_edid": False,
            "reads_framebuffer": False,
            "reads_media": False,
            "reads_config": False,
            "uses_network": False,
            "mutates_player": False,
        },
        "visible_state": args.visible_state,
        "drm": drm,
        "service": service,
        "player_status": player_status,
        "non_claims": [
            "this_collector_does_not_start_stop_or_restart_player",
            "this_collector_does_not_read_edid_framebuffer_media_or_config",
            "this_collector_does_not_validate_playback_decode_health",
            "this_collector_does_not_replace_h2_powerloss_or_soak",
            "this_collector_does_not_publish_or_thaw",
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def make_args(**overrides: Any) -> argparse.Namespace:
    args = argparse.Namespace(
        drm_root=Path("/nonexistent"),
        status_file=Path("/nonexistent"),
        service=DEFAULT_SERVICE,
        visible_state="unknown",
        output=None,
        json=True,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


class DisplayStatusCollectSelfTest(unittest.TestCase):
    def write_connector(
        self,
        root: Path,
        name: str,
        *,
        status: str,
        modes: str = "1920x1080\n",
        write_mode_file: bool = True,
    ) -> None:
        path = root / name
        path.mkdir(parents=True)
        (path / "status").write_text(status + "\n", encoding="utf-8")
        (path / "enabled").write_text(("enabled" if status == "connected" else "disabled") + "\n", encoding="utf-8")
        (path / "modes").write_text(modes, encoding="utf-8")
        if status == "connected" and modes.strip() and write_mode_file:
            (path / "mode").write_text(modes.splitlines()[0] + "\n", encoding="utf-8")

    def test_no_sink_classification(self) -> None:
        with self.subTest("disconnected"):
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.write_connector(root, "card0-HDMI-A-1", status="disconnected", modes="")
                result = build_result(make_args(drm_root=root))
        self.assertEqual(result["classification"], "no_sink")
        self.assertFalse(result["collection_policy"]["reads_edid"])
        self.assertFalse(result["collection_policy"]["reads_framebuffer"])

    def test_display_ok_classification(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "drm"
            status = Path(tmp) / "status.json"
            self.write_connector(root, "card0-HDMI-A-1", status="connected")
            status.write_text(json.dumps({
                "playback_state": "playing",
                "mpv_running": True,
                "playlist_size": 3,
            }), encoding="utf-8")
            result = build_result(make_args(drm_root=root, status_file=status))
            result["service"]["active_state"] = "active"
            result["classification"] = classify(result["drm"], result["service"], result["player_status"], "unknown")
        self.assertEqual(result["classification"], "display_ok")

    def test_visible_black_with_healthy_board_classifies_sink_hung(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "drm"
            status = Path(tmp) / "status.json"
            self.write_connector(root, "card0-HDMI-A-1", status="connected")
            status.write_text(json.dumps({"playback_state": "playing", "mpv_running": True}), encoding="utf-8")
            result = build_result(make_args(drm_root=root, status_file=status, visible_state="black"))
            result["service"]["active_state"] = "active"
            result["classification"] = classify(result["drm"], result["service"], result["player_status"], "black")
        self.assertEqual(result["classification"], "sink_hung_board_healthy")

    def test_status_error_classifies_pipeline_stalled(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "drm"
            status = Path(tmp) / "status.json"
            self.write_connector(root, "card0-HDMI-A-1", status="connected")
            status.write_text(json.dumps({
                "playback_state": "playing",
                "mpv_running": True,
                "last_render_error": "private-media-token",
            }), encoding="utf-8")
            result = build_result(make_args(drm_root=root, status_file=status))
            result["service"]["active_state"] = "active"
            result["classification"] = classify(result["drm"], result["service"], result["player_status"], "unknown")
        self.assertEqual(result["classification"], "pipeline_stalled")
        self.assertEqual(result["player_status"]["last_render_error"], "present")
        self.assertNotIn("private-media-token", json.dumps(result, sort_keys=True))

    def test_connected_without_mode_is_pipeline_stalled(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "drm"
            status = Path(tmp) / "status.json"
            self.write_connector(root, "card0-HDMI-A-1", status="connected", modes="")
            status.write_text(json.dumps({"playback_state": "playing", "mpv_running": True}), encoding="utf-8")
            result = build_result(make_args(drm_root=root, status_file=status))
            result["service"]["active_state"] = "active"
            result["classification"] = classify(result["drm"], result["service"], result["player_status"], "unknown")
        self.assertEqual(result["classification"], "pipeline_stalled")

    def test_connected_enabled_modes_without_mode_file_is_unknown_not_stalled(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "drm"
            status = Path(tmp) / "status.json"
            self.write_connector(root, "card0-HDMI-A-1", status="connected", write_mode_file=False)
            status.write_text(json.dumps({"playback_state": "playing", "mpv_running": True}), encoding="utf-8")
            result = build_result(make_args(drm_root=root, status_file=status))
            result["service"]["active_state"] = "active"
            result["classification"] = classify(result["drm"], result["service"], result["player_status"], "unknown")
        self.assertEqual(result["drm"]["connected_ready_count"], 0)
        self.assertEqual(result["drm"]["connected_active_count"], 1)
        self.assertEqual(result["classification"], "unknown")

    def test_visible_ok_with_mode_file_unavailable_can_classify_display_ok(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "drm"
            status = Path(tmp) / "status.json"
            self.write_connector(root, "card0-HDMI-A-1", status="connected", write_mode_file=False)
            status.write_text(json.dumps({"playback_state": "playing", "mpv_running": True}), encoding="utf-8")
            result = build_result(make_args(drm_root=root, status_file=status, visible_state="ok"))
            result["service"]["active_state"] = "active"
            result["classification"] = classify(result["drm"], result["service"], result["player_status"], "ok")
        self.assertEqual(result["classification"], "display_ok")

    def test_disconnected_connector_modes_do_not_make_connected_sink_ready(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "drm"
            status = Path(tmp) / "status.json"
            self.write_connector(root, "card0-HDMI-A-1", status="connected", modes="")
            self.write_connector(root, "card0-DP-1", status="disconnected", modes="1920x1080\n")
            status.write_text(json.dumps({"playback_state": "playing", "mpv_running": True}), encoding="utf-8")
            result = build_result(make_args(drm_root=root, status_file=status))
            result["service"]["active_state"] = "active"
            result["classification"] = classify(result["drm"], result["service"], result["player_status"], "unknown")
        self.assertEqual(result["drm"]["connected_ready_count"], 0)
        self.assertEqual(result["classification"], "pipeline_stalled")

    def test_visible_ok_without_status_does_not_overclaim_display_ok(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "drm"
            self.write_connector(root, "card0-HDMI-A-1", status="connected")
            result = build_result(make_args(drm_root=root, visible_state="ok"))
        self.assertEqual(result["classification"], "unknown")

    def test_status_fields_are_token_sanitized(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "drm"
            status = Path(tmp) / "status.json"
            self.write_connector(root, "card0-HDMI-A-1", status="connected")
            status.write_text(json.dumps({
                "playback_state": "secret-token",
                "player_state": "private-url-token",
                "startup_phase": "/data/private/config",
                "mpv_running": True,
            }), encoding="utf-8")
            result = build_result(make_args(drm_root=root, status_file=status))
        rendered = json.dumps(result, sort_keys=True)
        self.assertNotIn("secret-token", rendered)
        self.assertNotIn("private-url-token", rendered)
        self.assertNotIn("/data/private/config", rendered)
        self.assertEqual(result["player_status"]["playback_state"], "present")

    def test_output_json_roundtrip(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "display-status.json"
            result = build_result(make_args(output=out))
            write_json(out, result)
            loaded = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(loaded["schema"], SCHEMA)
        self.assertIn("this_collector_does_not_read_edid_framebuffer_media_or_config", loaded["non_claims"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--drm-root", type=Path, default=DEFAULT_DRM_ROOT)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS_FILE)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--visible-state", choices=VISIBLE_STATES, default="unknown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(DisplayStatusCollectSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = build_result(args)
    if args.output is not None:
        write_json(args.output, result)
    if args.json or args.output is None:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"classification={result['classification']} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
