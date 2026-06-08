#!/usr/bin/env python3
"""C18 lab probe for MPV relaunch/teardown GPU faults.

This is a diagnostic tool, not an updater path or release gate. It stops the
kiosk service, runs short MPV launches through the C18 hwdecode wrapper,
records kernel/GPU fault deltas around each launch, then restores the service.
Artifacts should be treated as lab evidence until a separate QA gate promotes
the probe into the C18 player-runtime contract.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.mpv_relaunch_teardown_probe.v1"
SERVICE = "kiosky-player.service"
APP_USER = "totem"
DEFAULT_MEDIA = Path("/data/media/c18-m6-canary.mp4")
DEFAULT_WRAPPER = Path("/opt/totem/bin/totem-mpv-hwdecode")
DEFAULT_RUNTIME_ROOT = Path("/tmp/kiosky/c18-mpv-relaunch")
FAULT_RE = re.compile(
    r"panfrost.*(fault|hang|reset|error)|gpu sched timeout|JOB_BUS_FAULT|Unhandled Page fault|BO has no sgt",
    re.IGNORECASE,
)


def run(cmd: list[str], *, timeout: float = 30.0, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=check,
    )


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def chown_to_app_user(path: Path) -> None:
    try:
        import pwd

        pw = pwd.getpwnam(APP_USER)
    except Exception:
        return
    try:
        os.chown(path, pw.pw_uid, pw.pw_gid)
    except OSError:
        pass


def monotonic_uptime() -> float:
    return float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])


def kernel_fault_lines() -> list[str]:
    proc = run(["journalctl", "-k", "-b", "--no-pager", "--output=short-monotonic"], timeout=20)
    lines = (proc.stdout or "").splitlines()
    return [line for line in lines if FAULT_RE.search(line)]


def service_state() -> dict[str, Any]:
    active = run(["systemctl", "is-active", SERVICE], timeout=10)
    enabled = run(["systemctl", "is-enabled", SERVICE], timeout=10)
    nrestarts = run(["systemctl", "show", SERVICE, "-p", "NRestarts", "--value"], timeout=10)
    return {
        "active": active.stdout.strip(),
        "active_rc": active.returncode,
        "enabled": enabled.stdout.strip(),
        "enabled_rc": enabled.returncode,
        "nrestarts": nrestarts.stdout.strip(),
        "nrestarts_rc": nrestarts.returncode,
    }


def pgrep_mpv() -> str:
    proc = run(["pgrep", "-a", "mpv"], timeout=10)
    return proc.stdout


def fuser_dri() -> str:
    proc = run(["bash", "-lc", "fuser -v /dev/dri/* 2>&1 || true"], timeout=10)
    return proc.stdout + proc.stderr


def ipc_command(sock_path: Path, command: list[Any], timeout: float = 1.0) -> Any:
    payload = json.dumps({"command": command}) + "\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(sock_path))
        client.sendall(payload.encode("utf-8"))
        data = b""
        while not data.endswith(b"\n"):
            chunk = client.recv(65536)
            if not chunk:
                break
            data += chunk
    if not data:
        return None
    return json.loads(data.decode("utf-8"))


def wait_for_ipc(sock_path: Path, timeout_sec: float) -> int | None:
    deadline = time.monotonic() + timeout_sec
    start = time.monotonic()
    while time.monotonic() < deadline:
        if sock_path.exists():
            try:
                ipc_command(sock_path, ["get_property", "pid"], timeout=0.4)
                return int((time.monotonic() - start) * 1000)
            except Exception:
                pass
        time.sleep(0.1)
    return None


def get_property(sock_path: Path, name: str) -> Any:
    try:
        data = ipc_command(sock_path, ["get_property", name], timeout=0.8)
    except Exception:
        return None
    if isinstance(data, dict) and data.get("error") == "success":
        return data.get("data")
    return None


def stop_mpv(proc: subprocess.Popen[str], sock_path: Path, timeout_sec: float = 5.0) -> dict[str, Any]:
    stopped = {
        "quit_sent": False,
        "method": "none",
        "returncode": None,
        "stop_elapsed_ms": None,
    }
    started = time.monotonic()
    if proc.poll() is None and sock_path.exists():
        try:
            ipc_command(sock_path, ["quit"], timeout=0.8)
            stopped["quit_sent"] = True
            stopped["method"] = "ipc_quit"
        except Exception:
            stopped["method"] = "ipc_quit_failed"
    try:
        proc.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        try:
            proc.terminate()
            stopped["method"] = "sigterm"
            proc.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                stopped["method"] = "sigkill"
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=timeout_sec)
            except subprocess.TimeoutExpired:
                stopped["method"] = "sigkill_timeout"
    stopped["returncode"] = proc.poll()
    stopped["stop_elapsed_ms"] = int((time.monotonic() - started) * 1000)
    try:
        sock_path.unlink()
    except FileNotFoundError:
        pass
    return stopped


def ensure_media(media: Path, run_dir: Path) -> Path:
    if media.is_file():
        return media
    generated = run_dir / "generated-testsrc-8s.mp4"
    ffmpeg = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    proc = run(
        [
            ffmpeg,
            "-nostdin",
            "-y",
            "-hide_banner",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=8:size=640x360:rate=30",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "35",
            "-pix_fmt",
            "yuv420p",
            str(generated),
        ],
        timeout=60,
    )
    write_text(run_dir / "ffmpeg-media.stdout", proc.stdout)
    write_text(run_dir / "ffmpeg-media.stderr", proc.stderr)
    if proc.returncode != 0 or not generated.is_file():
        raise RuntimeError("failed_to_create_probe_media")
    return generated


def launch_mpv(
    wrapper: Path,
    media: Path,
    phase_dir: Path,
    runtime_root: Path,
    launch_name: str,
    duration_sec: float,
) -> dict[str, Any]:
    runtime_dir = runtime_root / f"{phase_dir.name}-{launch_name}"
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(runtime_dir, 0o700)
    except OSError:
        pass
    chown_to_app_user(runtime_dir)
    sock_path = runtime_dir / f"{launch_name}.sock"
    log_path = runtime_dir / f"{launch_name}.mpv.log"
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "XDG_RUNTIME_DIR": "/tmp/kiosky",
    }
    argv = [
        "runuser",
        "-u",
        APP_USER,
        "--",
        "env",
        *[f"{key}={value}" for key, value in env.items()],
        str(wrapper),
        "--no-config",
        "--fs",
        "--force-window=yes",
        "--idle=yes",
        "--keep-open=yes",
        "--loop-file=inf",
        "--no-terminal",
        "--no-osc",
        "--osd-level=0",
        f"--input-ipc-server={sock_path}",
        f"--log-file={log_path}",
        "--msg-level=all=v",
        "--vo=gpu",
        "--gpu-context=drm",
        "--ao=null",
        "--hwdec=auto-safe",
        str(media),
    ]
    before_faults = kernel_fault_lines()
    before_uptime = monotonic_uptime()
    write_text(phase_dir / f"{launch_name}.argv.txt", "\n".join(argv) + "\n")
    proc = subprocess.Popen(argv, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ipc_ready_ms = wait_for_ipc(sock_path, 10.0)
    samples: list[dict[str, Any]] = []
    sample_count = max(2, int(duration_sec))
    for _ in range(sample_count):
        samples.append(
            {
                "uptime": monotonic_uptime(),
                "pid": proc.pid,
                "alive": proc.poll() is None,
                "time_pos": get_property(sock_path, "time-pos") if ipc_ready_ms is not None else None,
                "estimated_frame_number": get_property(sock_path, "estimated-frame-number") if ipc_ready_ms is not None else None,
                "hwdec_current": get_property(sock_path, "hwdec-current") if ipc_ready_ms is not None else None,
                "vo_configured": get_property(sock_path, "vo-configured") if ipc_ready_ms is not None else None,
            }
        )
        time.sleep(1.0)
    stop = stop_mpv(proc, sock_path)
    time.sleep(2.0)
    after_faults = kernel_fault_lines()
    after_uptime = monotonic_uptime()
    frames = [item["estimated_frame_number"] for item in samples if isinstance(item.get("estimated_frame_number"), (int, float))]
    times = [item["time_pos"] for item in samples if isinstance(item.get("time_pos"), (int, float))]
    hwdec_values = [item.get("hwdec_current") for item in samples if item.get("hwdec_current")]
    vo_values = [item.get("vo_configured") for item in samples if item.get("vo_configured") is not None]
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
        "hwdec_values": sorted({str(value) for value in hwdec_values}),
        "vo_values": sorted({str(value) for value in vo_values}),
        "stop": stop,
        "passed": (
            ipc_ready_ms is not None
            and proc.poll() is not None
            and max(0, len(after_faults) - len(before_faults)) == 0
            and (bool(frames and max(frames) > min(frames)) or bool(times and max(times) > min(times)))
        ),
    }
    write_json(phase_dir / f"{launch_name}.samples.json", {"samples": samples})
    write_json(phase_dir / f"{launch_name}.result.json", result)
    write_text(phase_dir / f"{launch_name}.kernel-before.txt", "\n".join(before_faults) + "\n")
    write_text(phase_dir / f"{launch_name}.kernel-after.txt", "\n".join(after_faults) + "\n")
    write_text(phase_dir / f"{launch_name}.pgrep-after.txt", pgrep_mpv())
    write_text(phase_dir / f"{launch_name}.dri-users-after.txt", fuser_dri())
    if log_path.exists():
        shutil.copy2(log_path, phase_dir / f"{launch_name}.mpv.log")
    return result


def barrier(phase_dir: Path, barrier_sec: float) -> dict[str, Any]:
    before = pgrep_mpv()
    for _ in range(40):
        if not pgrep_mpv().strip():
            break
        time.sleep(0.25)
    run(["udevadm", "settle", "--timeout=5"], timeout=10)
    time.sleep(max(0.0, barrier_sec))
    result = {
        "pgrep_before": before,
        "pgrep_after": pgrep_mpv(),
        "dri_users_after": fuser_dri(),
        "barrier_sec": barrier_sec,
    }
    write_json(phase_dir / "barrier.json", result)
    return result


def phase_single(name: str, run_dir: Path, wrapper: Path, media: Path, runtime_root: Path, duration_sec: float) -> dict[str, Any]:
    phase_dir = run_dir / name
    phase_dir.mkdir(parents=True, exist_ok=True)
    first = launch_mpv(wrapper, media, phase_dir, runtime_root, "launch-1", duration_sec)
    return {"phase": name, "launches": [first], "passed": first["passed"]}


def phase_double(
    name: str,
    run_dir: Path,
    wrapper: Path,
    media: Path,
    runtime_root: Path,
    duration_sec: float,
    *,
    use_barrier: bool,
) -> dict[str, Any]:
    phase_dir = run_dir / name
    phase_dir.mkdir(parents=True, exist_ok=True)
    first = launch_mpv(wrapper, media, phase_dir, runtime_root, "launch-1", duration_sec)
    barrier_result = barrier(phase_dir, 2.0) if use_barrier else None
    second = launch_mpv(wrapper, media, phase_dir, runtime_root, "launch-2", duration_sec)
    launches = [first, second]
    return {
        "phase": name,
        "launches": launches,
        "barrier": barrier_result,
        "passed": all(item["passed"] for item in launches),
    }


def collect_static(run_dir: Path, label: str) -> None:
    out_dir = run_dir / label
    out_dir.mkdir(parents=True, exist_ok=True)
    write_text(out_dir / "date-utc.txt", run(["date", "-u"], timeout=10).stdout)
    write_text(out_dir / "boot-id.txt", Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8"))
    write_text(out_dir / "uptime.txt", Path("/proc/uptime").read_text(encoding="utf-8"))
    write_json(out_dir / "service-state.json", service_state())
    write_text(out_dir / "pgrep-mpv.txt", pgrep_mpv())
    write_text(out_dir / "dri-users.txt", fuser_dri())
    write_text(out_dir / "kernel-fault-lines.txt", "\n".join(kernel_fault_lines()) + "\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=Path("/root/totem-diag"))
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    parser.add_argument("--wrapper", type=Path, default=DEFAULT_WRAPPER)
    parser.add_argument("--media", type=Path, default=DEFAULT_MEDIA)
    parser.add_argument("--duration-sec", type=float, default=10.0)
    parser.add_argument("--restore-service", action="store_true", default=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if os.geteuid() != 0:
        print("must run as root", file=sys.stderr)
        return 2
    if not args.wrapper.is_file():
        print(f"wrapper missing: {args.wrapper}", file=sys.stderr)
        return 2

    run_id = time.strftime("c18-mpv-relaunch-%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = args.run_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    try:
        os.chmod(run_dir, 0o700)
    except OSError:
        pass

    summary: dict[str, Any] = {
        "schema": SCHEMA,
        "run_dir": str(run_dir),
        "phases": [],
        "passed": False,
        "service_restored": False,
    }
    rc = 1
    try:
        collect_static(run_dir, "pre")
        if args.runtime_root.exists():
            shutil.rmtree(args.runtime_root)
        args.runtime_root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(args.runtime_root, 0o711)
        except OSError:
            pass
        media = ensure_media(args.media, run_dir)
        summary["media"] = str(media)
        stop = run(["systemctl", "stop", SERVICE], timeout=30)
        summary["service_stop_rc"] = stop.returncode
        time.sleep(2.0)
        collect_static(run_dir, "after-service-stop")
        if pgrep_mpv().strip():
            raise RuntimeError("mpv_still_running_after_service_stop")
        phases = [
            phase_single("p0-single", run_dir, args.wrapper, media, args.runtime_root, args.duration_sec),
            phase_double("p1-double-immediate", run_dir, args.wrapper, media, args.runtime_root, args.duration_sec, use_barrier=False),
            phase_double("p2-double-barrier", run_dir, args.wrapper, media, args.runtime_root, args.duration_sec, use_barrier=True),
        ]
        summary["phases"] = phases
        summary["passed"] = all(item["passed"] for item in phases)
        rc = 0 if summary["passed"] else 1
    except Exception as exc:
        summary["error"] = type(exc).__name__
        summary["error_message"] = str(exc)
        rc = 1
    finally:
        if args.restore_service:
            run(["systemctl", "unmask", SERVICE], timeout=30)
            run(["systemctl", "restart", SERVICE], timeout=60)
            time.sleep(10.0)
            summary["service_restored"] = run(["systemctl", "is-active", SERVICE], timeout=10).stdout.strip() == "active"
        collect_static(run_dir, "post")
        write_json(run_dir / "summary.json", summary)
        tar_path = Path(str(run_dir) + ".tgz")
        run(["tar", "-C", str(run_dir.parent), "-czf", str(tar_path), run_dir.name], timeout=120)
        shutil.rmtree(args.runtime_root, ignore_errors=True)
        summary["tar_path"] = str(tar_path)
        write_json(run_dir / "summary.json", summary)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"run_dir={run_dir}")
        print(f"passed={str(summary.get('passed') is True).lower()}")
        print(f"tar_path={summary.get('tar_path')}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
