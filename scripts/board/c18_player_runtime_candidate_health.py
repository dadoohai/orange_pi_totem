#!/usr/bin/env python3
"""Lab-only health runner for a staged C18 player-runtime candidate.

This module does not thaw the public updater CLI. It runs an extracted
player-runtime release in an isolated temporary workspace, collects sanitized
deep-health artifacts for that candidate, and returns the hook-compatible
health shape expected by totem_updatectl's internal lab path.
"""

from __future__ import annotations

import argparse
import json
import os
import pwd
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import c18_playback_health_collect as collector
import totem_updatectl as updatectl


LAB_ENV = "C18_PLAYER_RUNTIME_CANDIDATE_HEALTH_LAB_ONLY"
SCHEMA = "dadooh.c18.player_runtime.candidate_health.v1"
WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
SAFE_TEMPLATE_KEYS = {
    "allow_empty_playlist_from_api",
    "cache_max_bytes",
    "cache_max_files",
    "cleanup_interval_sec",
    "default_duration_ms",
    "disable_cleanup_when_offline",
    "hotkey_open_key",
    "hotkeys_enabled",
    "hwdec",
    "include_descendants",
    "limit",
    "lock_input",
    "low_resource_mode",
    "max_download_bytes",
    "media_load_retry_cooldown_sec",
    "min_free_space_bytes",
    "mpv_ao",
    "mpv_debug_events",
    "mpv_gpu_context",
    "mpv_ipc_timeout_sec",
    "mpv_msg_level",
    "mpv_query_uses_fresh_ipc",
    "mpv_startup_timeout_sec",
    "mpv_vo",
    "mpv_watchdog_grace_after_load_sec",
    "mpv_watchdog_grace_after_restart_sec",
    "mpv_watchdog_ping_failures_before_restart",
    "mute",
    "offline_fallback",
    "offline_ignore_max_age_when_no_network",
    "offline_max_age_hours",
    "only_standby",
    "poll_interval_sec",
    "preload_next",
    "request_timeout_sec",
    "require_full_download_before_switch",
    "rotation_deg",
    "search_in",
    "startup_feedback_enabled",
    "status_interval_sec",
    "sync_drift_threshold_ms",
    "sync_hard_resync_ms",
    "tmp_max_age_sec",
    "watchdog_interval_sec",
}


def read_json_object(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("candidate config template must be a JSON object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def candidate_identity(release_dir: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    kiosk = release_dir / "kiosk.py"
    if not kiosk.is_file():
        raise RuntimeError("candidate kiosk.py missing")
    manifest = manifest or {}
    return {
        "version": str(manifest.get("version") or release_dir.name),
        "payload_sha256": str(manifest.get("payload_sha256") or ""),
        "kiosk_py_sha256": updatectl._sha256_file(kiosk),
        "tree_sha256": updatectl._tree_hash(release_dir),
    }


def candidate_config(template_path: Path | None, work_dir: Path) -> dict[str, Any]:
    template = read_json_object(template_path)
    cfg = {key: template[key] for key in SAFE_TEMPLATE_KEYS if key in template}
    runtime_dir = work_dir / "runtime"
    overrides = {
        "api_url": "https://api.example.invalid/search",
        "api_key": "",
        "environment_id": "",
        "telemetry_enabled": False,
        "telemetry_url": "https://telemetry.example.invalid/telemetry",
        "telemetry_token": "",
        "config_ui_enabled": False,
        "sync_enabled": False,
        "cache_dir": str(work_dir / "media_cache"),
        "state_dir": str(work_dir / "state"),
        "ipc_path": str(work_dir / "mpv.sock"),
        "runtime_dir": str(runtime_dir),
        "status_file": str(work_dir / "status.json"),
        "mpv_log_file": str(work_dir / "mpv.log"),
        "log_file": str(work_dir / "kiosk.log"),
        "mpv_path": WRAPPER,
        "hwdec": cfg.get("hwdec") or "auto",
        "mpv_debug_events": True,
        "startup_feedback_enabled": False,
    }
    cfg.update(overrides)
    return cfg


def minimal_candidate_env(work_root: Path) -> dict[str, str]:
    home = work_root / "home"
    tmp = work_root / "tmp"
    xdg_runtime = work_root / "xdg-runtime"
    xdg_config = work_root / "xdg-config"
    for path in (home, tmp, xdg_runtime, xdg_config):
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONUNBUFFERED": "1",
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "XDG_RUNTIME_DIR": str(xdg_runtime),
        "XDG_CONFIG_HOME": str(xdg_config),
        "KIOSKY_TELEMETRY_TOKEN": "",
    }


def terminate_process(proc: subprocess.Popen[str], timeout_sec: float = 5.0) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout_sec)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        proc.send_signal(signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        pass


def current_user_name() -> str:
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        return "root"


def run_candidate_health(
    release_dir: Path,
    identity: dict[str, Any] | None = None,
    *,
    config_template: Path | None = None,
    output_dir: Path | None = None,
    duration_sec: float = 30.0,
    interval_sec: float = 1.0,
    startup_wait_sec: float = 5.0,
) -> dict[str, Any]:
    release_dir = release_dir.resolve()
    identity = identity or candidate_identity(release_dir)
    work_root = output_dir or Path(tempfile.mkdtemp(prefix="c18-player-runtime-candidate-"))
    work_root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(work_root, 0o700)
    except OSError:
        pass

    config_path = work_root / "candidate-config.json"
    cfg = candidate_config(config_template, work_root)
    write_json(config_path, cfg)

    env = minimal_candidate_env(work_root)

    proc = subprocess.Popen(
        [sys.executable, str(release_dir / "kiosk.py"), "--config", str(config_path)],
        cwd=str(release_dir),
        env=env,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(max(startup_wait_sec, 0.0))
        ns = argparse.Namespace(
            duration_sec=max(duration_sec, 0.1),
            interval_sec=max(interval_sec, 0.1),
            ipc_timeout_sec=0.8,
            output_dir=work_root / "health",
            target_mode="candidate",
            candidate_pid=proc.pid,
            service="kiosky-player.service",
            app_user=current_user_name(),
            config=config_path,
            status=Path(str(cfg["status_file"])),
            match_process_ipc=True,
            process_ipc_path=Path(str(cfg["ipc_path"])),
            mpv_log=Path(str(cfg["mpv_log_file"])),
            mpv_generation_dir=Path(str(cfg["runtime_dir"])),
            json=False,
        )
        _out_dir, result = collector.collect(ns)
    finally:
        terminate_process(proc)

    result["schema"] = updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA
    result["candidate_health_schema"] = SCHEMA
    result["observed_kiosk_py_sha256"] = identity.get("kiosk_py_sha256")
    result["observed_tree_sha256"] = identity.get("tree_sha256")
    result["candidate_version"] = identity.get("version")
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab-only-candidate-runner", action="store_true")
    parser.add_argument("--release-dir", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--config-template", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--duration-sec", type=float, default=30.0)
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--startup-wait-sec", type=float, default=5.0)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.lab_only_candidate_runner or os.environ.get(LAB_ENV) != "1":
        print(
            f"candidate_health_lab_guard_required: pass --lab-only-candidate-runner and set {LAB_ENV}=1",
            file=sys.stderr,
        )
        return 44
    manifest = read_json_object(args.manifest) if args.manifest else None
    try:
        result = run_candidate_health(
            args.release_dir,
            candidate_identity(args.release_dir, manifest),
            config_template=args.config_template,
            output_dir=args.output_dir,
            duration_sec=args.duration_sec,
            interval_sec=args.interval_sec,
            startup_wait_sec=args.startup_wait_sec,
        )
    except Exception as exc:
        result = {
            "schema": updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
            "candidate_health_schema": SCHEMA,
            "passed": False,
            "failure_reasons": ["candidate_health_runner_failed"],
            "runner_error": type(exc).__name__,
        }
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"candidate_health_runner_failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"candidate_deep_health_passed={str(bool(result.get('passed'))).lower()}")
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
