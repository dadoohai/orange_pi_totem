#!/usr/bin/env python3
"""Sanitized adoption proof for C18 player-runtime lab trials.

The playback deep-health summary proves that MPV/player are healthy.  This
probe proves which runtime the launched service actually adopted: the verified
/data/player-runtime/current slot or the image fallback under /opt.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BOARD_DIR = REPO_ROOT / "scripts" / "board"
sys.path.insert(0, str(BOARD_DIR))

import totem_updatectl as updatectl


SCHEMA = "dadooh.c18.player_runtime.adoption.v1"
COMPONENT = "player-runtime"
FALLBACK_APP_DIR = Path("/opt/totem/kiosky-player")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def configure(data_root: Path) -> None:
    updatectl.DATA_ROOT = data_root
    updatectl.UPDATES_DIR = updatectl.DATA_ROOT / "updates"
    updatectl.POLICY_FILE = updatectl.UPDATES_DIR / "policy.json"
    updatectl.LOG_DIR = updatectl.DATA_ROOT / "logs"
    updatectl.LOG_FILE = updatectl.LOG_DIR / "totem-update.log"
    updatectl.TOKEN_FILE = updatectl.DATA_ROOT / "secrets" / "github-release-token"
    updatectl.configure_component(COMPONENT)


def read_cmdline(pid_dir: Path) -> list[str]:
    try:
        raw = (pid_dir / "cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]


def classify_kiosk_path(path: Path) -> tuple[str, str | None]:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    current = updatectl.CURRENT_LINK.resolve() if (updatectl.CURRENT_LINK.exists() or updatectl.CURRENT_LINK.is_symlink()) else None
    if current is not None:
        try:
            resolved.relative_to(current)
            return "data", updatectl._read_symlink_target(updatectl.CURRENT_LINK)
        except ValueError:
            pass
    try:
        resolved.relative_to(FALLBACK_APP_DIR)
        return "fallback", None
    except ValueError:
        return "unknown", None


def running_kiosk_processes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pid_dir in sorted(Path("/proc").glob("[0-9]*")):
        cmd = read_cmdline(pid_dir)
        if not cmd:
            continue
        kiosk_args = [arg for arg in cmd if arg.endswith("kiosk.py") or arg.endswith("/kiosk.py")]
        if not kiosk_args:
            continue
        kiosk_path = Path(kiosk_args[0])
        source, current_link = classify_kiosk_path(kiosk_path)
        sha = ""
        if kiosk_path.is_file():
            try:
                sha = updatectl._sha256_file(kiosk_path)
            except OSError:
                sha = ""
        rows.append({
            "pid": int(pid_dir.name),
            "source": source,
            "current_link": current_link,
            "kiosk_py_sha256": sha,
        })
    return rows


def build_probe(expected_source: str, expected_version: str | None) -> dict[str, Any]:
    state = updatectl._read_state()
    current_link = updatectl._read_symlink_target(updatectl.CURRENT_LINK)
    previous_link = updatectl._read_symlink_target(updatectl.PREVIOUS_LINK)
    marker_valid = False
    marker_reason = "no_current"
    marker: dict[str, Any] = {}
    if current_link:
        marker_valid, marker_reason, marker = updatectl._validate_player_runtime_marker(
            updatectl.APP_BASE / current_link,
            state,
        )

    processes = running_kiosk_processes()
    data_processes = [item for item in processes if item["source"] == "data"]
    fallback_processes = [item for item in processes if item["source"] == "fallback"]
    selected_source = "unknown"
    selected_process: dict[str, Any] | None = None
    if data_processes:
        selected_source = "data"
        selected_process = data_processes[0]
    elif fallback_processes:
        selected_source = "fallback"
        selected_process = fallback_processes[0]

    version = marker.get("version") if marker_valid else None
    if selected_source == "fallback":
        version = "image_fallback"

    identity_matches_marker = False
    if selected_source == "data" and marker_valid and selected_process:
        identity_matches_marker = selected_process.get("kiosk_py_sha256") == marker.get("kiosk_py_sha256")

    source_ok = expected_source == "any" or selected_source == expected_source
    version_ok = not expected_version or version == expected_version
    data_ok = selected_source != "data" or (marker_valid and identity_matches_marker)
    passed = bool(source_ok and version_ok and data_ok and selected_source != "unknown")

    return {
        "schema": SCHEMA,
        "component": COMPONENT,
        "expected_source": expected_source,
        "expected_version": expected_version,
        "passed": passed,
        "selected_source": selected_source,
        "selected_version": version,
        "process_count": len(processes),
        "data_process_count": len(data_processes),
        "fallback_process_count": len(fallback_processes),
        "current_link": current_link,
        "previous_link": previous_link,
        "state_current_version": (state.get("current") or {}).get("version") if isinstance(state.get("current"), dict) else None,
        "state_previous_version": (state.get("previous") or {}).get("version") if isinstance(state.get("previous"), dict) else None,
        "marker_valid": marker_valid,
        "marker_reason": marker_reason,
        "marker_version": marker.get("version") if marker_valid else None,
        "marker_kiosk_py_sha256": marker.get("kiosk_py_sha256") if marker_valid else None,
        "marker_tree_sha256": marker.get("tree_sha256") if marker_valid else None,
        "running_kiosk_py_sha256": selected_process.get("kiosk_py_sha256") if selected_process else None,
        "running_identity_matches_marker": identity_matches_marker,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("/data"))
    parser.add_argument("--expected-source", choices=("data", "fallback", "any"), default="any")
    parser.add_argument("--expected-version")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    configure(args.data_root)
    result = build_probe(args.expected_source, args.expected_version)
    if args.output:
        write_json(args.output, result)
    if args.json or not args.output:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
