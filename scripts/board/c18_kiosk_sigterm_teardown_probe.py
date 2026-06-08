#!/usr/bin/env python3
"""C18 lab probe for kiosk.py SIGTERM teardown GPU faults.

This complements c18_mpv_relaunch_teardown_probe.py. It is diagnostic
lab-only evidence, not an updater path or release gate. It runs the real
kiosk.py with an isolated config and canary playlist, terminates the kiosk
process with SIGTERM, and measures whether the embedded MPV teardown leaves
panfrost/DRM faults before a second launch in the same boot.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import c18_mpv_relaunch_teardown_probe as base


SCHEMA = "dadooh.c18.kiosk_sigterm_teardown_probe.v1"
DEFAULT_KIOSK = Path("/opt/totem/kiosky-player/kiosk.py")
DEFAULT_MEDIA = Path("/data/media/c18-m6-canary.mp4")
DEFAULT_RUNTIME_ROOT = Path("/tmp/kiosky/c18-kiosk-sigterm")


def write_config(work_dir: Path, media: Path) -> Path:
    state_dir = work_dir / "state"
    runtime_dir = work_dir / "runtime"
    cache_dir = work_dir / "media-cache"
    for path in (state_dir, runtime_dir, cache_dir):
        path.mkdir(parents=True, exist_ok=True)
        base.chown_to_app_user(path)
    cfg = {
        "api_url": "https://api.example.invalid/search",
        "api_key": "",
        "environment_id": "",
        "sync_enabled": False,
        "telemetry_enabled": False,
        "config_ui_enabled": False,
        "default_duration_ms": 10000,
        "offline_fallback": True,
        "offline_max_age_hours": 0,
        "cache_dir": str(cache_dir),
        "state_dir": str(state_dir),
        "runtime_dir": str(runtime_dir),
        "status_file": str(work_dir / "status.json"),
        "ipc_path": str(work_dir / "mpv.sock"),
        "mpv_log_file": str(work_dir / "mpv.log"),
        "log_file": str(work_dir / "kiosk.log"),
        "mpv_path": "/opt/totem/bin/totem-mpv-hwdecode",
        "mpv_vo": "gpu",
        "mpv_gpu_context": "drm",
        "mpv_ao": "null",
        "hwdec": "v4l2request-copy",
        "mpv_debug_events": True,
        "startup_feedback_enabled": False,
        "allow_empty_playlist_from_api": False,
        "watchdog_interval_sec": 30,
    }
    playlist = {
        "version": 1,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fingerprint": "c18-kiosk-sigterm-canary",
        "playlist": [
            {
                "url": "",
                "duration_ms": 10000,
                "path": str(media),
                "campaign_id": "c18-canary",
                "campaign_name": "C18 canary",
            }
        ],
    }
    config_path = work_dir / "config.json"
    base.write_json(config_path, cfg)
    base.write_json(state_dir / "playlist_last.json", playlist)
    for path in work_dir.rglob("*"):
        base.chown_to_app_user(path)
    return config_path


def stop_kiosk(proc: subprocess.Popen[str], timeout_sec: float = 5.0) -> dict[str, Any]:
    result = {"method": "sigterm", "returncode": None, "elapsed_ms": None}
    started = time.monotonic()
    if proc.poll() is None:
        proc.terminate()
    try:
        proc.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        result["method"] = "sigkill"
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            result["method"] = "sigkill_timeout"
    result["returncode"] = proc.poll()
    result["elapsed_ms"] = int((time.monotonic() - started) * 1000)
    return result


def launch_kiosk(kiosk: Path, media: Path, phase_dir: Path, runtime_root: Path, launch_name: str, duration_sec: float) -> dict[str, Any]:
    work_dir = runtime_root / f"{phase_dir.name}-{launch_name}"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(work_dir, 0o700)
    base.chown_to_app_user(work_dir)
    config_path = write_config(work_dir, media)
    sock_path = work_dir / "mpv.sock"
    before_faults = base.kernel_fault_lines()
    before_uptime = base.monotonic_uptime()
    argv = [
        "runuser",
        "-u",
        base.APP_USER,
        "--",
        "env",
        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG=C.UTF-8",
        "LC_ALL=C.UTF-8",
        f"HOME={work_dir / 'home'}",
        f"TMPDIR={work_dir / 'tmp'}",
        f"XDG_RUNTIME_DIR={work_dir / 'xdg-runtime'}",
        sys.executable,
        str(kiosk),
        "--config",
        str(config_path),
    ]
    for path in (work_dir / "home", work_dir / "tmp", work_dir / "xdg-runtime"):
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o700)
        base.chown_to_app_user(path)
    base.write_text(phase_dir / f"{launch_name}.argv.txt", "\n".join(argv) + "\n")
    proc = subprocess.Popen(argv, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ipc_ready_ms = base.wait_for_ipc(sock_path, 12.0)
    samples: list[dict[str, Any]] = []
    for _ in range(max(2, int(duration_sec))):
        samples.append(
            {
                "uptime": base.monotonic_uptime(),
                "pid": proc.pid,
                "alive": proc.poll() is None,
                "time_pos": base.get_property(sock_path, "time-pos") if ipc_ready_ms is not None else None,
                "estimated_frame_number": base.get_property(sock_path, "estimated-frame-number") if ipc_ready_ms is not None else None,
                "hwdec_current": base.get_property(sock_path, "hwdec-current") if ipc_ready_ms is not None else None,
                "vo_configured": base.get_property(sock_path, "vo-configured") if ipc_ready_ms is not None else None,
            }
        )
        time.sleep(1.0)
    stop = stop_kiosk(proc)
    time.sleep(3.0)
    after_faults = base.kernel_fault_lines()
    after_uptime = base.monotonic_uptime()
    frames = [item["estimated_frame_number"] for item in samples if isinstance(item.get("estimated_frame_number"), (int, float))]
    times = [item["time_pos"] for item in samples if isinstance(item.get("time_pos"), (int, float))]
    result = {
        "launch": launch_name,
        "pid": proc.pid,
        "ipc_ready_ms": ipc_ready_ms,
        "before_uptime": before_uptime,
        "after_uptime": after_uptime,
        "before_fault_count": len(before_faults),
        "after_fault_count": len(after_faults),
        "fault_delta": max(0, len(after_faults) - len(before_faults)),
        "frame_progressed": bool(frames and max(frames) > min(frames)),
        "time_progressed": bool(times and max(times) > min(times)),
        "hwdec_values": sorted({str(item.get("hwdec_current")) for item in samples if item.get("hwdec_current")}),
        "vo_values": sorted({str(item.get("vo_configured")) for item in samples if item.get("vo_configured") is not None}),
        "stop": stop,
        "passed": (
            ipc_ready_ms is not None
            and max(0, len(after_faults) - len(before_faults)) == 0
            and (bool(frames and max(frames) > min(frames)) or bool(times and max(times) > min(times)))
        ),
    }
    base.write_json(phase_dir / f"{launch_name}.samples.json", {"samples": samples})
    base.write_json(phase_dir / f"{launch_name}.result.json", result)
    base.write_text(phase_dir / f"{launch_name}.kernel-before.txt", "\n".join(before_faults) + "\n")
    base.write_text(phase_dir / f"{launch_name}.kernel-after.txt", "\n".join(after_faults) + "\n")
    base.write_text(phase_dir / f"{launch_name}.pgrep-after.txt", base.pgrep_mpv())
    base.write_text(phase_dir / f"{launch_name}.dri-users-after.txt", base.fuser_dri())
    for src_name in ("mpv.log", "kiosk.log", "status.json"):
        src = work_dir / src_name
        if src.exists():
            shutil.copy2(src, phase_dir / f"{launch_name}.{src_name}")
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=Path("/root/totem-diag"))
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    parser.add_argument("--kiosk", type=Path, default=DEFAULT_KIOSK)
    parser.add_argument("--media", type=Path, default=DEFAULT_MEDIA)
    parser.add_argument("--duration-sec", type=float, default=8.0)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if os.geteuid() != 0:
        print("must run as root", file=sys.stderr)
        return 2
    if not args.kiosk.is_file() or not args.media.is_file():
        print("kiosk_or_media_missing", file=sys.stderr)
        return 2
    run_id = time.strftime("c18-kiosk-sigterm-%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = args.run_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    os.chmod(run_dir, 0o700)
    summary: dict[str, Any] = {"schema": SCHEMA, "run_dir": str(run_dir), "passed": False, "service_restored": False}
    rc = 1
    try:
        base.collect_static(run_dir, "pre")
        if args.runtime_root.exists():
            shutil.rmtree(args.runtime_root)
        args.runtime_root.mkdir(parents=True, exist_ok=True)
        os.chmod(args.runtime_root, 0o711)
        stop = base.run(["systemctl", "stop", base.SERVICE], timeout=30)
        summary["service_stop_rc"] = stop.returncode
        time.sleep(2.0)
        base.collect_static(run_dir, "after-service-stop")
        if base.pgrep_mpv().strip():
            raise RuntimeError("mpv_still_running_after_service_stop")
        phase_dir = run_dir / "p1-kiosk-double-sigterm"
        phase_dir.mkdir(parents=True, exist_ok=True)
        first = launch_kiosk(args.kiosk, args.media, phase_dir, args.runtime_root, "launch-1", args.duration_sec)
        second = launch_kiosk(args.kiosk, args.media, phase_dir, args.runtime_root, "launch-2", args.duration_sec)
        summary["phase"] = {"phase": "p1-kiosk-double-sigterm", "launches": [first, second], "passed": first["passed"] and second["passed"]}
        summary["passed"] = bool(summary["phase"]["passed"])
        rc = 0 if summary["passed"] else 1
    except Exception as exc:
        summary["error"] = type(exc).__name__
        summary["error_message"] = str(exc)
        rc = 1
    finally:
        base.run(["systemctl", "unmask", base.SERVICE], timeout=30)
        base.run(["systemctl", "restart", base.SERVICE], timeout=60)
        time.sleep(10.0)
        summary["service_restored"] = base.run(["systemctl", "is-active", base.SERVICE], timeout=10).stdout.strip() == "active"
        base.collect_static(run_dir, "post")
        base.write_json(run_dir / "summary.json", summary)
        tar_path = Path(str(run_dir) + ".tgz")
        base.run(["tar", "-C", str(run_dir.parent), "-czf", str(tar_path), run_dir.name], timeout=120)
        shutil.rmtree(args.runtime_root, ignore_errors=True)
        summary["tar_path"] = str(tar_path)
        base.write_json(run_dir / "summary.json", summary)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"run_dir={run_dir}")
        print(f"passed={str(summary.get('passed') is True).lower()}")
        print(f"tar_path={summary.get('tar_path')}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
