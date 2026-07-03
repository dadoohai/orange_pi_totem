#!/usr/bin/env python3
"""Lab-only health runner for a staged C18 player-runtime candidate.

This module does not thaw the public updater CLI. It runs an extracted
player-runtime release in an isolated temporary workspace, collects sanitized
deep-health artifacts for that candidate, and returns the hook-compatible
health shape expected by totem_updatectl's internal lab path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import re
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
GPU_FAULT_RE = re.compile(
    r"panfrost.*(fault|hang|reset|error)|gpu sched timeout|JOB_BUS_FAULT|Unhandled Page fault|BO has no sgt",
    re.IGNORECASE,
)
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
CANARY_MEDIA_ALLOWED_ROOTS = (Path("/tmp"), Path("/data/media"))
CANARY_MEDIA_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi"}
UNIX_SOCKET_PATH_SOFT_LIMIT = 100


class CandidateSetupInaccessibleError(RuntimeError):
    """Raised when the candidate workspace/release is unreachable by the run_user — a SETUP error,
    not a candidate health failure. Propagated to the apply path so it aborts via the
    deep_health_exception route (fail-closed: no promotion) WITHOUT quarantining the candidate
    identity. An environment problem (e.g. a work_root under 0700 /root) must never permanently
    poison a good release's tree_sha256."""


def read_json_object(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("candidate config template must be a JSON object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    fsync_dir(path.parent)


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_text_fsync(path: Path, content: str, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    if mode is not None:
        try:
            os.chmod(path, mode)
        except OSError:
            pass
    fsync_dir(path.parent)


def materialize_symlink_file(path: Path) -> None:
    if not path.is_symlink():
        return
    target = path.resolve(strict=True)
    data = target.read_bytes()
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    fsync_dir(path.parent)


def is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def normalize_canary_media(raw_path: Path | None) -> Path | None:
    if raw_path is None:
        return None
    path = raw_path.expanduser()
    if not path.is_absolute():
        raise RuntimeError("canary media path must be absolute")
    if path.is_symlink():
        raise RuntimeError("canary media path must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise RuntimeError("canary media file not found") from exc
    if not resolved.is_file():
        raise RuntimeError("canary media must be a file")
    if resolved.suffix.lower() not in CANARY_MEDIA_EXTENSIONS:
        raise RuntimeError("canary media must be a supported video file")
    if not any(is_under(resolved, root) for root in CANARY_MEDIA_ALLOWED_ROOTS):
        raise RuntimeError("canary media must live under /tmp or /data/media")
    return resolved


def write_canary_playlist(cfg: dict[str, Any], canary_media: Path) -> None:
    state_dir = Path(str(cfg["state_dir"]))
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fingerprint": "c18-candidate-canary",
        "playlist": [
            {
                "url": "",
                "duration_ms": int(cfg.get("default_duration_ms") or 10000),
                "path": str(canary_media),
                "campaign_id": "c18-canary",
                "campaign_name": "C18 canary",
            }
        ],
    }
    write_json(state_dir / "playlist_last.json", payload)


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


def candidate_ipc_path(work_dir: Path) -> Path:
    default = work_dir / "mpv.sock"
    if len(str(default)) < UNIX_SOCKET_PATH_SOFT_LIMIT:
        return default
    digest = hashlib.sha256(str(work_dir).encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"c18-pr-ipc-{digest}" / "mpv.sock"


def prepare_candidate_ipc_path(ipc_path: Path, uid: int, gid: int) -> None:
    prepare_candidate_path(ipc_path.parent, uid, gid)
    try:
        if ipc_path.exists() or ipc_path.is_symlink():
            ipc_path.unlink()
    except OSError:
        pass


def cleanup_candidate_ipc_path(cfg: dict[str, Any], work_root: Path) -> None:
    try:
        ipc_path = Path(str(cfg.get("ipc_path") or ""))
        parent = ipc_path.parent
        if is_under(parent, work_root):
            return
        if parent.parent != Path(tempfile.gettempdir()) or not parent.name.startswith("c18-pr-ipc-"):
            return
        if ipc_path.exists() or ipc_path.is_symlink():
            ipc_path.unlink()
        parent.rmdir()
    except OSError:
        pass


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
        "default_duration_ms": int(cfg.get("default_duration_ms") or 10000),
        "cache_dir": str(work_dir / "media_cache"),
        "state_dir": str(work_dir / "state"),
        "ipc_path": str(candidate_ipc_path(work_dir)),
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


def kernel_gpu_fault_lines() -> list[str]:
    proc = subprocess.run(
        ["journalctl", "-k", "-b", "--no-pager", "--output=short-monotonic"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    return [line for line in (proc.stdout or "").splitlines() if GPU_FAULT_RE.search(line)]


def sanitize_kernel_line(line: str) -> str:
    line = re.sub(r"0x[0-9A-Fa-f]+", "0x<hex>", line)
    line = re.sub(r"\b[A-Fa-f0-9]{12,}\b", "<hex>", line)
    return line


def terminate_process(proc: subprocess.Popen[str], timeout_sec: float = 45.0) -> dict[str, Any]:
    started = time.monotonic()
    stop: dict[str, Any] = {
        "method": "none",
        "returncode": proc.poll(),
        "elapsed_ms": 0,
    }
    if proc.poll() is not None:
        return stop
    stop["method"] = "sigterm"
    proc.terminate()
    try:
        proc.wait(timeout=timeout_sec)
        stop["returncode"] = proc.poll()
        stop["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        return stop
    except subprocess.TimeoutExpired:
        pass
    stop["method"] = "sigkill"
    try:
        proc.send_signal(signal.SIGKILL)
    except ProcessLookupError:
        stop["returncode"] = proc.poll()
        stop["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        return stop
    try:
        proc.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        stop["method"] = "sigkill_timeout"
        pass
    stop["returncode"] = proc.poll()
    stop["elapsed_ms"] = int((time.monotonic() - started) * 1000)
    return stop


def current_user_name() -> str:
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        return "root"


def candidate_run_user() -> pwd.struct_passwd:
    requested = os.environ.get("C18_PLAYER_RUNTIME_CANDIDATE_USER")
    if not requested:
        requested = "totem" if os.geteuid() == 0 else current_user_name()
    try:
        pw = pwd.getpwnam(requested)
    except KeyError as exc:
        raise RuntimeError(f"candidate run user not found: {requested}") from exc
    if os.geteuid() == 0 and pw.pw_uid == 0:
        raise RuntimeError("candidate health refuses to run candidate kiosk.py as root")
    if os.geteuid() != 0 and pw.pw_uid != os.geteuid():
        raise RuntimeError("candidate health can only switch users when started as root")
    return pw


def chown_tree(root: Path, uid: int, gid: int) -> None:
    if os.geteuid() != 0:
        return
    for path in [root, *root.rglob("*")]:
        try:
            os.chown(path, uid, gid)
        except OSError:
            pass


def prepare_candidate_path(path: Path, uid: int, gid: int, mode: int = 0o700) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, mode)
    except OSError:
        pass
    if os.geteuid() != 0:
        return
    try:
        os.chown(path, uid, gid)
    except OSError:
        pass


def drop_to_user_preexec(user_name: str, uid: int, gid: int):
    if os.geteuid() != 0:
        return None

    def _drop() -> None:
        os.initgroups(user_name, gid)
        os.setgid(gid)
        os.setuid(uid)

    return _drop


def access_check_targets(
    cfg: dict[str, Any],
    release_dir: Path,
    work_root: Path,
    config_path: Path,
    canary: Path | None,
) -> list[tuple[str, Path, int]]:
    """Distinct (label, path, mode) the candidate process — running AS run_user — must reach.
    Ancestor traversal is implied: os.access() resolves the full path under the dropped
    credentials, so a work_root beneath a 0700 ancestor (e.g. /root) surfaces here."""
    targets: list[tuple[str, Path, int]] = [
        ("release_dir_traverse", release_dir, os.X_OK),
        ("release_kiosk_py_read", release_dir / "kiosk.py", os.R_OK),
        ("work_root_write", work_root, os.W_OK | os.X_OK),
        ("config_path_read", config_path, os.R_OK),
        ("state_dir_write", Path(str(cfg["state_dir"])), os.W_OK | os.X_OK),
        ("runtime_dir_write", Path(str(cfg["runtime_dir"])), os.W_OK | os.X_OK),
        ("ipc_dir_write", Path(str(cfg["ipc_path"])).parent, os.W_OK | os.X_OK),
        ("log_dir_write", Path(str(cfg["log_file"])).parent, os.W_OK | os.X_OK),
        ("mpv_log_dir_write", Path(str(cfg["mpv_log_file"])).parent, os.W_OK | os.X_OK),
        ("status_dir_write", Path(str(cfg["status_file"])).parent, os.W_OK | os.X_OK),
    ]
    if canary is not None:
        targets.append(("canary_media_read", canary, os.R_OK))
    return targets


def access_failures_as_user(
    targets: list[tuple[str, Path, int]],
    run_user: pwd.struct_passwd,
) -> list[str]:
    """Labels the run_user CANNOT access. As root, the probe runs in a forked child that drops
    to run_user EXACTLY like the launch preexec (initgroups+setgid+setuid), so supplementary
    groups and ancestor traversal are evaluated as the candidate will actually see them."""

    def _run_checks() -> list[str]:
        return [label for (label, path, mode) in targets if not os.access(str(path), mode)]

    if os.geteuid() != 0:
        return _run_checks()
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # child: drop privileges, probe, report, never return
        try:
            os.close(read_fd)
            os.initgroups(run_user.pw_name, run_user.pw_gid)
            os.setgid(run_user.pw_gid)
            os.setuid(run_user.pw_uid)
            os.write(write_fd, "\n".join(_run_checks()).encode("utf-8"))
        except BaseException:
            try:
                os.write(write_fd, b"run_user_privilege_drop_failed")
            except Exception:
                pass
        finally:
            os._exit(0)
    os.close(write_fd)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(read_fd, 4096)
        if not chunk:
            break
        chunks.append(chunk)
    os.close(read_fd)
    _pid, status = os.waitpid(pid, 0)
    text = b"".join(chunks).decode("utf-8", "replace")
    if text.strip() == "run_user_privilege_drop_failed":
        return ["run_user_privilege_drop_failed"]
    # Empty report with a clean exit means "all accessible". But if the child died before writing
    # (e.g. killed by a signal — not a Python exception, so the except above cannot catch it), do
    # NOT conclude "all accessible": fail closed so a real setup problem can't slip back through as
    # a generic health failure.
    if not text and (os.WIFSIGNALED(status) or (os.WIFEXITED(status) and os.WEXITSTATUS(status) != 0)):
        return ["run_user_privilege_drop_failed"]
    return [line for line in text.splitlines() if line]


def sanitize_lines(text: str) -> list[str]:
    return [sanitize_kernel_line(line) for line in text.splitlines()]


def setup_failure_result(
    identity: dict[str, Any],
    run_user: pwd.struct_passwd,
    canary_used: bool,
    inaccessible: list[str],
) -> dict[str, Any]:
    """Hook-compatible result for a SETUP failure (the candidate workspace is unreachable by the
    run_user). Distinct from a health failure: it names candidate_setup_inaccessible_to_run_user so
    the cause is obvious instead of a generic all-checks-failed health-fail."""
    distinct = sorted(set(inaccessible))
    return {
        "schema": updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
        "candidate_health_schema": SCHEMA,
        "passed": False,
        "failure_reasons": ["candidate_setup_inaccessible_to_run_user"],
        "setup_error": "candidate_setup_inaccessible_to_run_user",
        "inaccessible_targets": distinct,
        "candidate_run_user": run_user.pw_name,
        "observed_kiosk_py_sha256": identity.get("kiosk_py_sha256"),
        "observed_tree_sha256": identity.get("tree_sha256"),
        "candidate_version": identity.get("version"),
        "canary_media_used": canary_used,
        "checks": {"candidate_setup_accessible_to_run_user": False},
        "counters": {"candidate_setup_inaccessible_target_count": len(distinct)},
    }


def run_candidate_health(
    release_dir: Path,
    identity: dict[str, Any] | None = None,
    *,
    config_template: Path | None = None,
    canary_media: Path | None = None,
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
    normalized_canary = normalize_canary_media(canary_media)
    if normalized_canary is not None:
        write_canary_playlist(cfg, normalized_canary)

    env = minimal_candidate_env(work_root)
    run_user = candidate_run_user()
    # Pre-create derived workspace dirs so the preflight (and chown) act on a concrete tree.
    for sub in ("runtime_dir", "state_dir", "cache_dir"):
        Path(str(cfg[sub])).mkdir(parents=True, exist_ok=True)
    prepare_candidate_ipc_path(Path(str(cfg["ipc_path"])), run_user.pw_uid, run_user.pw_gid)
    chown_tree(work_root, run_user.pw_uid, run_user.pw_gid)

    # PREFLIGHT — the candidate kiosk.py runs as run_user via setuid. If any path it must
    # read/write (including ancestor traversal) is unreachable by that user — e.g. a work_root
    # beneath 0700 /root — it dies before it can open its own log, which previously looked like a
    # generic health failure. Detect it HERE and fail with an explicit SETUP error.
    inaccessible = access_failures_as_user(
        access_check_targets(cfg, release_dir, work_root, config_path, normalized_canary),
        run_user,
    )
    if inaccessible:
        result = setup_failure_result(
            identity, run_user, normalized_canary is not None, inaccessible
        )
        write_json(work_root / "candidate-health-result.json", result)
        cleanup_candidate_ipc_path(cfg, work_root)
        # Raise (not return passed=False): the apply path then aborts via deep_health_exception
        # (fail-closed, no promotion) WITHOUT quarantining the identity. The result artifact above
        # keeps the explicit setup_error/inaccessible_targets for diagnosis.
        raise CandidateSetupInaccessibleError(
            f"candidate workspace unreachable by run_user {run_user.pw_name}: "
            + ",".join(sorted(set(inaccessible)))
        )

    teardown: dict[str, Any] = {
        "schema": "dadooh.c18.player_runtime.candidate_teardown.v1",
        "measured": False,
        "passed": False,
        "failure_reasons": ["candidate_teardown_not_measured"],
    }
    candidate_stdout_path = work_root / "candidate-stdout.txt"
    candidate_stderr_path = work_root / "candidate-stderr.txt"
    # Capture the candidate's stdout/stderr (was DEVNULL) so an early death the preflight could
    # not foresee leaves a sanitized artifact instead of a silent, undiagnosable failure.
    with open(candidate_stdout_path, "w", encoding="utf-8") as _so, \
         open(candidate_stderr_path, "w", encoding="utf-8") as _se:
        proc = subprocess.Popen(
            [sys.executable, str(release_dir / "kiosk.py"), "--config", str(config_path)],
            cwd=str(release_dir),
            env=env,
            text=True,
            stdout=_so,
            stderr=_se,
            preexec_fn=drop_to_user_preexec(run_user.pw_name, run_user.pw_uid, run_user.pw_gid),
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
            app_user=run_user.pw_name,
            config=config_path,
            status=Path(str(cfg["status_file"])),
            match_process_ipc=True,
            process_ipc_path=Path(str(cfg["ipc_path"])),
            mpv_log=Path(str(cfg["mpv_log_file"])),
            mpv_generation_dir=Path(str(cfg["runtime_dir"])),
            panfrost_fault_policy="absolute",
            json=False,
        )
        _out_dir, result = collector.collect(ns)
    finally:
        before_faults = kernel_gpu_fault_lines()
        stop = terminate_process(proc)
        # GPU faults can be emitted just after the userspace process exits.
        time.sleep(2.0)
        after_faults = kernel_gpu_fault_lines()
        delta_lines = after_faults[len(before_faults):] if len(after_faults) >= len(before_faults) else after_faults
        fault_delta = max(0, len(after_faults) - len(before_faults))
        stop_method = str(stop.get("method") or "")
        stop_returncode = stop.get("returncode")
        stop_clean = stop_method in {"none", "sigterm"} and stop_returncode == 0
        failure_reasons = []
        if fault_delta != 0:
            failure_reasons.append("candidate_teardown_gpu_fault_delta_zero")
        if not stop_clean:
            failure_reasons.append("candidate_teardown_process_stopped_cleanly")
        teardown = {
            "schema": "dadooh.c18.player_runtime.candidate_teardown.v1",
            "measured": True,
            "passed": not failure_reasons,
            "failure_reasons": failure_reasons,
            "gpu_faults_before": len(before_faults),
            "gpu_faults_after": len(after_faults),
            "gpu_faults_delta": fault_delta,
            "stop": stop,
            "process_stopped_cleanly": stop_clean,
            "new_fault_lines_sanitized": [sanitize_kernel_line(line) for line in delta_lines[-20:]],
        }
        write_json(work_root / "candidate-teardown-kernel.json", teardown)
        # Sanitize the captured candidate launch logs so the committed evidence is clean.
        for _cap in (candidate_stdout_path, candidate_stderr_path):
            try:
                _lines = sanitize_lines(_cap.read_text(encoding="utf-8", errors="replace"))
                write_text_fsync(
                    _cap,
                    "\n".join(_lines) + ("\n" if _lines else "empty\n"),
                )
            except OSError:
                pass
        try:
            materialize_symlink_file(Path(str(cfg["mpv_log_file"])))
        except OSError:
            pass

    result["schema"] = updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA
    result["candidate_health_schema"] = SCHEMA
    result["observed_kiosk_py_sha256"] = identity.get("kiosk_py_sha256")
    result["observed_tree_sha256"] = identity.get("tree_sha256")
    result["candidate_version"] = identity.get("version")
    result["canary_media_used"] = normalized_canary is not None
    result["candidate_run_user"] = run_user.pw_name
    try:
        result["candidate_launch_stderr_tail"] = sanitize_lines(
            candidate_stderr_path.read_text(encoding="utf-8", errors="replace")
        )[-40:]
    except OSError:
        result["candidate_launch_stderr_tail"] = []
    result["candidate_teardown"] = teardown
    result.setdefault("checks", {})["candidate_teardown_gpu_fault_delta_zero"] = teardown.get("gpu_faults_delta") == 0
    result.setdefault("checks", {})["candidate_teardown_process_stopped_cleanly"] = teardown.get("process_stopped_cleanly") is True
    result.setdefault("counters", {})["candidate_teardown_gpu_faults_delta"] = teardown.get("gpu_faults_delta")
    if teardown.get("passed") is not True:
        reasons = result.setdefault("failure_reasons", [])
        for reason in teardown.get("failure_reasons") or ["candidate_teardown_failed"]:
            if reason not in reasons:
                reasons.append(reason)
        result["passed"] = False
    write_json(work_root / "candidate-health-result.json", result)
    cleanup_candidate_ipc_path(cfg, work_root)
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab-only-candidate-runner", action="store_true")
    parser.add_argument("--release-dir", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--config-template", type=Path)
    parser.add_argument("--canary-media", type=Path)
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
            canary_media=args.canary_media,
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
