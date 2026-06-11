#!/usr/bin/env python3
"""C18 player-runtime HW teardown/panfrost trial (producer).

Lab-only, operator-attended harness that drives >=2 MPV launch/teardown cycles in
ONE boot -- including at least one REAL ``systemctl restart kiosky-player.service``
cycle -- and records a per-window, boot/monotonic-anchored panfrost fault delta for
each teardown. It optionally runs a SECONDARY fresh-IPC probe that forces
``self._ipc is None`` (short ``mpv_startup_timeout_sec``) and records, honestly,
whether the C1 ``_fresh_ipc_command`` quit path was reached and its outcome.

Evidence is consumed by ``scripts/qa/c18_player_runtime_teardown_evidence_gate.py``.
This harness produces evidence; it does NOT authorize anything. The runtime panfrost
fix is the wrapper (``v4l2request-copy``); fresh-IPC is a secondary corner. GR4b
(fresh-IPC quit SUCCESS vs a live socket) is an explicit non-claim.

Fail-closed lab guard: the real run requires ``C18_PLAYER_RUNTIME_TEARDOWN_TRIAL=1``
(exit 44 otherwise). ``--self-test`` runs pure-logic + gate round-trip checks and
needs no board.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_teardown_evidence_gate.py"
BOARD_DIR = REPO_ROOT / "scripts" / "board"
HEALTH_COLLECTOR = BOARD_DIR / "c18_playback_health_collect.py"

SERVICE_NAME = "kiosky-player.service"
# Public updater on the board. The frozen player-runtime apply/rollback/reconcile
# verbs MUST fail closed with rc 44; that is the freeze re-attestation (task #6).
DEFAULT_UPDATECTL = "/opt/totem/bin/totem-updatectl"
DEFAULT_CONFIG = Path("/data/config/config.json")
DEFAULT_KIOSK_LOG = Path("/tmp/kiosky/kiosk.log")
FREEZE_RC = 44
# A benign, deliberately non-matching placeholder so kernel-before/after.txt is
# never zero-size (the gate rejects zero-size files) yet contributes 0 faults.
CLEAN_WINDOW_PLACEHOLDER = "kernel: c18-teardown window: zero matching gpu hardware fault events\n"

TRIAL_SCHEMA = "dadooh.c18.player_runtime.teardown_trial.v1"
CYCLE_SCHEMA = "dadooh.c18.player_runtime.teardown_cycle.v1"
FRESH_IPC_SCHEMA = "dadooh.c18.player_runtime.teardown_fresh_ipc_probe.v1"
MID_DECODE_SCHEMA = "dadooh.c18.player_runtime.teardown_mid_decode_sigterm_probe.v1"
PLAYBACK_SCHEMA = "dadooh.c18.playback.deep_health.v1"
MANIFEST_SCHEMA = "dadooh.c18.teardown.evidence_manifest.v1"

LAB_GUARD_ENV = "C18_PLAYER_RUNTIME_TEARDOWN_TRIAL"
LAB_GUARD_EXIT = 44

# Broad teardown-class GPU fault matcher. Kept textually identical to the GATE
# (scripts/qa/c18_player_runtime_teardown_evidence_gate.py GPU_FAULT_RE) so the
# producer's counts agree with the gate's authoritative recompute. Intentionally
# greedy (fail-closed bias); recall is bounded and must be tuned on real HW.
GPU_FAULT_RE = re.compile(
    r"panfrost.*(?:fault|hang|reset|error)"
    r"|(?:panfrost|lima|mali)\b.*(?:fault|hang|hung|reset|error|timeout|"
    r"timed[ -]?out|lockup|stall|abort|terminated|unrecoverable)"
    r"|gpu sched timeout|drm_sched[^\n]*timeout|JOB_BUS_FAULT|"
    r"Unhandled Page fault|BO has no sgt",
    re.IGNORECASE,
)
FRESH_SENT_LOG = "MPV IPC fresh command sent command=quit"
FRESH_FAILED_LOG = "MPV IPC fresh command failed command=quit"
_HEX_RUN_RE = re.compile(r"0x[0-9a-fA-F]+")
MPV_STARTED_RE = re.compile(r"MPV process started pid=(?P<pid>\d+)")
EXPECTED_MPV_EXE = "/opt/totem/hwdecode/bin/mpv"
EXPECTED_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
EXPECTED_HWDEC = "v4l2request-copy"
MID_DECODE_EOF_MARGIN_SEC = 2.0
MID_DECODE_MAX_SAMPLE_TO_SIGNAL_SEC = 1.0

HEALTH_CHECKS = (
    "samples_present", "service_active", "single_mpv", "mpv_path_c18_stack",
    "hwdec_expected_present", "hwdec_no_unexpected", "estimated_frame_present",
    "playback_progressed", "media_load_failed_zero", "mpv_restart_zero",
    "panfrost_faults_zero", "panfrost_faults_delta_zero", "mmc_timeout_reset_zero",
    "ext4_errors_zero", "nrestarts_stable", "status_no_failures",
)

NON_CLAIMS = [
    "GR4b fresh-IPC quit SUCCESS against a live socket is NOT claimed (secondary _ipc-None corner).",
    "Soak/endurance, torn-write power-loss, server-side publish, and public thaw are NOT claimed.",
    "A green run proves teardown only for the cycles captured here; the runtime panfrost fix is the wrapper.",
]

MID_DECODE_NON_CLAIMS = [
    "GR4b fresh-IPC quit SUCCESS against a live socket is NOT claimed.",
    "healthy-not-wedged: this probe measures a healthy decoding mpv, not a wedged ipc_unresponsive mpv.",
    "no-kiosk-alive: the isolated kiosk is SIGKILLed before the signal; IPC quit, watchdog, waitpid, and auto-relaunch are NOT in this probe window.",
    "production-timing-unmeasured: exact production timing is NOT claimed.",
]


# --------------------------------------------------------------------------- #
# Pure logic (off-board testable).                                            #
# --------------------------------------------------------------------------- #
def sanitize_kernel_line(line: str) -> str:
    return _HEX_RUN_RE.sub("0xADDR", line).strip()


def fault_lines(kernel_text: str) -> list[str]:
    return [ln for ln in kernel_text.splitlines() if GPU_FAULT_RE.search(ln)]


def compute_window_delta(before: list[str], after: list[str]) -> tuple[int, int, int, bool]:
    """Return (before_count, after_count, signed_delta, anomalous).

    The delta is SIGNED (not clamped). A negative delta means the post-teardown
    fault list is shorter than the pre-launch one -- journal rotation/reset --
    which the gate must reject rather than silently read as zero. We flag it
    ``anomalous`` instead of clamping with ``max(0, ...)``.
    """
    b, a = len(before), len(after)
    delta = a - b
    return b, a, delta, delta < 0


def build_cycle_record(index: int, kind: str, boot_id: str, *,
                       before: list[str], after: list[str],
                       monotonic_before: float, monotonic_after: float,
                       stop: dict[str, Any], process_exited: bool,
                       health_passed: bool) -> dict[str, Any]:
    b, a, delta, anomalous = compute_window_delta(before, after)
    new_lines = [sanitize_kernel_line(ln) for ln in after[len(before):][:20]]
    passed = (delta == 0 and not anomalous and process_exited
              and stop.get("returncode") == 0 and health_passed)
    return {
        "schema": CYCLE_SCHEMA,
        "index": index,
        "kind": kind,
        "boot_id": boot_id,
        "gpu_faults_before": b,
        "gpu_faults_after": a,
        "gpu_faults_delta": delta,
        "gpu_faults_delta_anomalous": anomalous,
        "window_anchor": {
            "boot_id": boot_id,
            "monotonic_before": monotonic_before,
            "monotonic_after": monotonic_after,
        },
        "stop": stop,
        "process_exited": process_exited,
        "new_fault_lines_sanitized": new_lines,
        "passed": passed,
    }


def build_summary(boot_id: str, btime: int, cycles: list[dict[str, Any]],
                  *, gr4_secondary_present: bool,
                  mid_decode_probe_present: bool = False) -> dict[str, Any]:
    restart_indices = [c["index"] for c in cycles if c["kind"] == "service_restart"]
    summary = {
        "schema": TRIAL_SCHEMA,
        "passed": all(c["passed"] for c in cycles) and len(cycles) >= 2 and bool(restart_indices),
        "boot_id": boot_id,
        "btime": btime,
        "cycles_count": len(cycles),
        "service_restart_cycle_indices": restart_indices,
        "cycles": [{k: c[k] for k in ("index", "kind", "gpu_faults_delta", "passed")} for c in cycles],
        "gr4_secondary_present": gr4_secondary_present,
        "non_claims": list(NON_CLAIMS),
    }
    if mid_decode_probe_present:
        summary["mid_decode_probe_present"] = True
    return summary


def classify_fresh_ipc(kiosk_log_text: str, *,
                       forced_ipc_none: bool = False,
                       forcing_method: str = "none",
                       probe: dict[str, Any] | None = None) -> dict[str, Any]:
    """Inspect a kiosk.log for the fresh-IPC quit outcome (GR4 secondary).

    ``forced_ipc_none`` MUST reflect whether the caller actually staged the
    corner (short ``mpv_startup_timeout_sec``). It defaults to False so an
    un-staged probe can never claim forcing: the gate then fails closed with
    ``fresh_ipc_probe_not_forced`` instead of trusting a no-op probe.
    """
    sent = FRESH_SENT_LOG in kiosk_log_text
    failed = FRESH_FAILED_LOG in kiosk_log_text
    reached = sent or failed
    if sent:
        outcome, observed = "fresh_sent", FRESH_SENT_LOG
    elif failed:
        outcome, observed = "fresh_failed_fallback_sigterm", FRESH_FAILED_LOG
    else:
        # Neither log line present: the forced _ipc-None corner was NOT reached.
        # Do not claim a log line that is not in the journal. code_path_reached is
        # False below, so the gate fails this probe (the operator must re-force it).
        outcome, observed = "fresh_failed_fallback_sigterm", ""
    result: dict[str, Any] = {
        "schema": FRESH_IPC_SCHEMA,
        "forced_ipc_none": bool(forced_ipc_none),
        "forcing_method": forcing_method,
        "code_path_reached": reached,
        "observed_log": observed,
        "outcome": outcome,
        "process_exited": True,
        "non_claim": "GR4b (fresh-IPC quit SUCCESS vs a live socket) is NOT proven; secondary corner only.",
    }
    if probe:
        result["probe"] = probe
    return result


# --------------------------------------------------------------------------- #
# Evidence emission.                                                          #
# --------------------------------------------------------------------------- #
def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def seal_manifest(root: Path, *, artifact_id: str, board_image_marker: str, source_commit: str) -> None:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "evidence-manifest.json":
            files.append({
                "file": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    write_json(root / "evidence-manifest.json", {
        "schema": MANIFEST_SCHEMA,
        "artifact_id": artifact_id,
        "component": "player-runtime",
        "board_image_marker": board_image_marker,
        "source_commit": source_commit,
        "files": files,
    })


def write_cycle_dir(root: Path, cycle: dict[str, Any], *,
                    health: dict[str, Any], kernel_before: str, kernel_after: str) -> None:
    cdir = root / f"cycles/cycle-{cycle['index']:02d}"
    write_json(cdir / "cycle.json", cycle)
    write_json(cdir / "health" / "playback-deep-health-public.json", health)
    (cdir / "kernel-before.txt").write_text(kernel_before or "none\n", encoding="utf-8")
    (cdir / "kernel-after.txt").write_text(kernel_after or "none\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Real HW run (lab-guarded; board-validated).                                 #
# --------------------------------------------------------------------------- #
def require_lab_guard() -> None:
    if os.environ.get(LAB_GUARD_ENV) != "1":
        sys.stderr.write(
            f"refusing to run: set {LAB_GUARD_ENV}=1 to run the lab-only teardown trial\n")
        raise SystemExit(LAB_GUARD_EXIT)


# --------------------------------------------------------------------------- #
# Shimmable board seams.                                                       #
#                                                                             #
# EVERY real board command lives behind one of these small functions so the   #
# full ``run_trial`` orchestration can be exercised off-board: the self-test  #
# monkeypatches these seams with fakes and asserts the produced run-dir passes #
# the REAL gate. Keep each seam thin (one syscall/subprocess worth of work)    #
# and side-effect-free w.r.t. the harness's own emission helpers.             #
# --------------------------------------------------------------------------- #
def _run(cmd: list[str], *, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
    )


def _read_text_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _boot_state() -> dict[str, Any]:
    """Capture boot_id + btime + uptime once. All cycles share this boot_id."""
    boot_id = _read_text_file("/proc/sys/kernel/random/boot_id").strip()
    btime = 0
    for line in _read_text_file("/proc/stat").splitlines():
        if line.startswith("btime "):
            btime = int(line.split()[1])
            break
    uptime = float(_read_text_file("/proc/uptime").split()[0])
    return {"boot_id": boot_id, "btime": btime, "uptime": uptime}


def _capture_kernel_fault_lines() -> str:
    """Return the in-boot kernel journal text filtered to GPU-fault lines.

    Mirrors the candidate-health / deep-health collector invocation:
    ``journalctl -k -b --no-pager --output=short-monotonic``. Returns ONLY the
    GPU_FAULT_RE-matching lines (joined) so that ``fault_lines(text)`` over the
    returned text equals the matched set, and a clean board yields "".
    """
    proc = _run(
        ["journalctl", "-k", "-b", "--no-pager", "--output=short-monotonic"],
        timeout=20.0,
    )
    # Fail closed: a non-zero journalctl exit (degraded/rotated journal, permission
    # or transient error) must NOT be read as a clean window. Reporting 0 faults from
    # a failed capture would let a faulting board pass. Raise so the trial aborts and
    # the operator re-captures, rather than silently emitting a clean kernel window.
    if proc.returncode != 0:
        raise RuntimeError(
            f"journalctl_kernel_capture_failed:rc={proc.returncode}:"
            f"{(proc.stderr or '').strip()[:200]}"
        )
    matched = [ln for ln in (proc.stdout or "").splitlines() if GPU_FAULT_RE.search(ln)]
    return ("\n".join(matched) + "\n") if matched else ""


def _kernel_window_text(fault_text: str) -> str:
    """Wrap captured fault lines into a non-empty kernel-window file body.

    The gate rejects zero-size files AND recomputes counts from this text, so a
    clean window must be a benign NON-matching placeholder (0 faults) while a
    dirty window must contain EXACTLY the matched fault lines (and nothing else
    that GPU_FAULT_RE would match) so the recompute agrees with the recorded
    count.
    """
    return fault_text if fault_text else CLEAN_WINDOW_PLACEHOLDER


def _service_restart() -> dict[str, Any]:
    """Real ``systemctl restart kiosky-player.service``. Returns a stop record."""
    started = time.monotonic()
    proc = _run(["systemctl", "restart", SERVICE_NAME], timeout=60.0)
    return {
        "method": "ipc_quit" if proc.returncode == 0 else "sigterm",
        "returncode": proc.returncode,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "kind": "service_restart",
        "stderr_tail": (proc.stderr or "")[-200:],
    }


def _run_relaunch_teardown() -> dict[str, Any]:
    """Controlled real stop/start of the player (a relaunch, not a unit restart).

    ``systemctl stop`` (graceful IPC-quit teardown by the service ExecStop) then
    ``systemctl start``. This exercises the same MPV teardown path as a restart
    but as two distinct operations, modelling an in-place player relaunch.
    """
    started = time.monotonic()
    stop = _run(["systemctl", "stop", SERVICE_NAME], timeout=60.0)
    start = _run(["systemctl", "start", SERVICE_NAME], timeout=60.0)
    rc = stop.returncode or start.returncode
    return {
        "method": "ipc_quit" if rc == 0 else "sigterm",
        "returncode": rc,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "kind": "relaunch",
        "stderr_tail": ((stop.stderr or "") + (start.stderr or ""))[-200:],
    }


def _service_active() -> bool:
    return _run(["systemctl", "is-active", SERVICE_NAME], timeout=20.0).stdout.strip() == "active"


def _timer_enabled(timer: str) -> bool:
    return _run(["systemctl", "is-enabled", timer], timeout=20.0).stdout.strip() == "enabled"


def _collect_deep_health(cycle_dir: Path, *, duration_sec: float, interval_sec: float) -> dict[str, Any]:
    """Run the REAL deep-health collector against the live service.

    Shells out to ``c18_playback_health_collect.py`` (the production collector
    used by the M6 trial) with the cycle's health dir as output, then returns
    the parsed sanitized ``playback-deep-health-public.json``.
    """
    health_dir = cycle_dir / "health"
    health_dir.mkdir(parents=True, exist_ok=True)
    proc = _run(
        [
            sys.executable, str(HEALTH_COLLECTOR),
            "--duration-sec", str(duration_sec),
            "--interval-sec", str(interval_sec),
            "--output-dir", str(health_dir),
            "--panfrost-fault-policy", "absolute",
            "--json",
        ],
        timeout=max(300.0, duration_sec + 120.0),
    )
    public = health_dir / "playback-deep-health-public.json"
    if public.is_file():
        return json.loads(public.read_text(encoding="utf-8"))
    # Surface a failing-but-structured record; the cycle will then fail the gate.
    return {
        "schema": PLAYBACK_SCHEMA,
        "passed": False,
        "failure_reasons": ["deep_health_collector_no_output"],
        "checks": {k: False for k in HEALTH_CHECKS},
        "collector_rc": proc.returncode,
    }


def _resolve_probe_kiosk() -> Path:
    """The kiosk source the fresh-IPC probe must exercise: the ADOPTED /data
    runtime when present (that is what H1 is about), else the /opt fallback."""
    data_kiosk = Path("/data/player-runtime/current/kiosk.py")
    if data_kiosk.is_file():
        return data_kiosk
    return Path("/opt/totem/kiosky-player/kiosk.py")


def _kill_probe_orphans(ws: Path) -> int:
    """Best-effort SIGKILL of anything still referencing the probe workspace.

    The kiosk starts mpv in its OWN session (``start_new_session=True``), so
    terminating the kiosk does NOT reach a hung mpv -- an orphan would keep
    /dev/dri busy. The mkdtemp workspace path is unique, so the pgrep -f pattern
    cannot match unrelated processes."""
    proc = _run(["pgrep", "-f", str(ws)], timeout=10.0)
    killed = 0
    for token in (proc.stdout or "").split():
        try:
            pid = int(token)
        except ValueError:
            continue
        if pid == os.getpid():
            continue
        try:
            os.kill(pid, 9)
            killed += 1
        except (ProcessLookupError, PermissionError):
            continue
    return killed


def _run_fresh_ipc_probe(args: argparse.Namespace, run_root: Path) -> tuple[str, dict[str, Any]]:
    """Force the start_ipc_timeout corner END-TO-END; return (kiosk_log_text, classify kwargs).

    Stages, on an ISOLATED kiosk instance of the adopted runtime (the production
    service is NOT touched; the probe runs AFTER all cycles, so any probe-induced
    kernel noise lands outside the cycles' fault windows):
    - the workspace dirs PRE-CREATED before the access preflight (a missing dir
      reads as inaccessible and would abort staging);
    - an OFFLINE CANARY PLAYLIST (without content the kiosk exits ``no_content``
      rc=2 BEFORE ``mpv.start()`` and the corner is unreachable) -- requires
      ``--fresh-ipc-probe-canary-media`` (a real video under /tmp or /data/media);
    - a short ``mpv_startup_timeout_sec`` (default 0.05s -- far below the time
      mpv needs to expose its IPC socket on this board).
    The kiosk then launches mpv, ``_open_ipc`` times out, and
    ``_stop_locked("start_ipc_timeout")`` drives the C1 fresh-IPC quit (proc
    alive + ``_ipc is None``). Honest expected outcome:
    ``fresh_failed_fallback_sigterm``; a genuine ``fresh_sent`` is REJECTED by
    the gate pending an explicit operator policy decision. Whenever staging
    could not actually happen this returns ``forced_ipc_none=False`` (gate fails
    closed with ``fresh_ipc_probe_not_forced``) and persists a probe-error
    artifact -- the forcing is never faked.
    """
    import shutil as _shutil

    import c18_player_runtime_candidate_health as ch

    # Default calibrated on HW (2026-06-10): a HEALTHY mpv exposes its IPC socket in
    # ~0.03s on this board, so 0.05s let _open_ipc SUCCEED and the corner never fired;
    # 0.01s forces it deterministically (fresh attempt ~11ms -> socket absent -> ENOENT).
    timeout_sec = float(getattr(args, "fresh_ipc_probe_startup_timeout_sec", None) or 0.01)
    attempts_max = max(1, int(getattr(args, "fresh_ipc_probe_attempts", None) or 3))
    canary_arg = getattr(args, "fresh_ipc_probe_canary_media", None)
    not_forced: dict[str, Any] = {"forced_ipc_none": False, "forcing_method": "none"}
    artifacts = run_root / "fresh-ipc-probe"

    def _early(error: str, **extra: Any) -> tuple[str, dict[str, Any]]:
        info: dict[str, Any] = {"error": error, **extra}
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "probe-error.txt").write_text(
            json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return "", {**not_forced, "probe": info}

    kiosk_path = _resolve_probe_kiosk()
    if not kiosk_path.is_file():
        return _early("probe_kiosk_missing", kiosk_path=str(kiosk_path))
    try:
        canary = ch.normalize_canary_media(Path(canary_arg) if canary_arg else None)
    except RuntimeError as exc:
        return _early("probe_canary_invalid", detail=str(exc))
    if canary is None:
        return _early(
            "probe_canary_missing",
            hint="pass --fresh-ipc-probe-canary-media (video under /tmp or /data/media); "
                 "without offline content the kiosk exits no_content before mpv.start()",
        )

    # Workspace in tmp (traversable by the run_user) -- the sealed run_root is
    # root-0700, so the probe instance cannot live under it; sanitized artifacts
    # are copied into run_root afterwards so the manifest still seals them.
    ws = Path(tempfile.mkdtemp(prefix="c18-fresh-ipc-probe-"))
    try:
        cfg = ch.candidate_config(None, ws)
        cfg["mpv_startup_timeout_sec"] = timeout_sec
        config_path = ws / "probe-config.json"
        write_json(config_path, cfg)
        ch.write_canary_playlist(cfg, canary)
        # Pre-create derived dirs so the preflight (and chown) act on a concrete
        # tree (mirrors candidate_health; os.access on a missing dir reads False).
        for sub in ("runtime_dir", "state_dir", "cache_dir"):
            Path(str(cfg[sub])).mkdir(parents=True, exist_ok=True)
        env = ch.minimal_candidate_env(ws)
        run_user = ch.candidate_run_user()
        ch.chown_tree(ws, run_user.pw_uid, run_user.pw_gid)
        inaccessible = ch.access_failures_as_user(
            ch.access_check_targets(cfg, kiosk_path.parent, ws, config_path, canary),
            run_user,
        )
        if inaccessible:
            return _early("probe_workspace_inaccessible_to_run_user",
                          inaccessible_targets=sorted(set(inaccessible)))

        log_path = Path(str(cfg["log_file"]))
        log_text = ""
        attempts = 0
        orphans_killed = 0
        for attempts in range(1, attempts_max + 1):
            try:
                log_path.unlink()
            except OSError:
                pass
            with open(ws / "probe-stdout.txt", "a", encoding="utf-8") as so, \
                 open(ws / "probe-stderr.txt", "a", encoding="utf-8") as se:
                proc = subprocess.Popen(
                    [sys.executable, str(kiosk_path), "--config", str(config_path)],
                    cwd=str(kiosk_path.parent), env=env, text=True,
                    stdout=so, stderr=se,
                    preexec_fn=ch.drop_to_user_preexec(
                        run_user.pw_name, run_user.pw_uid, run_user.pw_gid),
                )
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                try:
                    log_text = log_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    log_text = ""
                if FRESH_SENT_LOG in log_text or FRESH_FAILED_LOG in log_text:
                    break
                if proc.poll() is not None:
                    break  # kiosk already exited (e.g. crashed): stop burning the window
                time.sleep(0.2)
            ch.terminate_process(proc)
            orphans_killed += _kill_probe_orphans(ws)
            try:
                log_text = log_path.read_text(encoding="utf-8", errors="replace") or log_text
            except OSError:
                pass
            if FRESH_SENT_LOG in log_text or FRESH_FAILED_LOG in log_text:
                break

        # Persist sanitized probe artifacts inside the sealed run dir so the
        # probe outcome stays re-derivable from committed evidence.
        artifacts.mkdir(parents=True, exist_ok=True)
        tail = "\n".join(ch.sanitize_lines(log_text)[-120:])
        (artifacts / "probe-kiosk-log-tail.txt").write_text(tail + "\n", encoding="utf-8")
        for name in ("probe-stderr.txt", "probe-stdout.txt"):
            try:
                lines = ch.sanitize_lines((ws / name).read_text(encoding="utf-8", errors="replace"))
                (artifacts / name).write_text("\n".join(lines[-40:]) + "\n", encoding="utf-8")
            except OSError:
                pass

        return log_text, {
            "forced_ipc_none": True,
            "forcing_method": "short_mpv_startup_timeout_sec",
            "probe": {
                "isolated_instance": True,
                "service_untouched": True,
                "canary_staged": True,
                "kiosk_path": str(kiosk_path),
                "kiosk_py_sha256": sha256_file(kiosk_path),
                "mpv_startup_timeout_sec": timeout_sec,
                "attempts": attempts,
                "orphans_killed": orphans_killed,
                "run_user": run_user.pw_name,
            },
        }
    finally:
        _shutil.rmtree(ws, ignore_errors=True)


def _write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _read_proc_identity(pid: int, *, ipc_path: str, expected_exe: str = EXPECTED_MPV_EXE) -> dict[str, Any]:
    """Best-effort /proc identity for a live MPV process.

    The gate treats this as producer attestation, but it is still valuable on the
    board: PID reuse and wrong-process matches must be surfaced before a signal.
    """
    base = Path("/proc") / str(pid)
    result: dict[str, Any] = {
        "pid": pid,
        "exists": base.exists(),
        "exe": "",
        "cmdline": "",
        "cmdline_contains_ipc_path": False,
        "pgid": None,
        "pgid_is_pid": False,
        "state": "",
        "starttime": None,
        "expected_exe": expected_exe,
        "exe_matches": False,
    }
    if not base.exists():
        return result
    try:
        result["exe"] = os.readlink(base / "exe")
    except OSError:
        result["exe"] = ""
    try:
        raw_cmdline = (base / "cmdline").read_bytes()
        result["cmdline"] = raw_cmdline.replace(b"\x00", b" ").decode("utf-8", "replace").strip()
    except OSError:
        result["cmdline"] = ""
    try:
        stat_text = (base / "stat").read_text(encoding="utf-8", errors="replace")
        close = stat_text.rfind(")")
        rest = stat_text[close + 2:].split() if close != -1 else []
        if rest:
            result["state"] = rest[0]
        if len(rest) > 19:
            result["starttime"] = int(rest[19])
    except (OSError, ValueError):
        pass
    try:
        result["pgid"] = os.getpgid(pid)
    except OSError:
        result["pgid"] = None
    result["cmdline_contains_ipc_path"] = bool(ipc_path and ipc_path in str(result.get("cmdline") or ""))
    result["pgid_is_pid"] = result.get("pgid") == pid
    result["exe_matches"] = result.get("exe") == expected_exe
    return result


def _proc_identity_ok(identity: dict[str, Any], *, starttime: int | None = None) -> bool:
    if identity.get("exists") is not True:
        return False
    if identity.get("state") == "Z":
        return False
    if identity.get("exe_matches") is not True:
        return False
    if identity.get("cmdline_contains_ipc_path") is not True:
        return False
    if identity.get("pgid_is_pid") is not True:
        return False
    if starttime is not None and identity.get("starttime") != starttime:
        return False
    return isinstance(identity.get("starttime"), int)


def _ipc_query_props(ipc_path: Path, props: list[str], *, timeout_s: float = 0.8) -> tuple[str, str, dict[str, Any], int]:
    if not ipc_path.exists():
        return "error", "missing_socket", {}, 0
    start = time.monotonic()
    responses: dict[str, Any] = {}
    rid_to_prop: dict[int, str] = {}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_s)
            sock.connect(str(ipc_path))
            for index, prop in enumerate(props, start=1):
                rid = 900000 + index
                rid_to_prop[rid] = prop
                payload = json.dumps({"command": ["get_property", prop], "request_id": rid}) + "\n"
                sock.sendall(payload.encode("utf-8"))
            buffer = ""
            deadline = start + timeout_s
            while len(responses) < len(rid_to_prop) and time.monotonic() < deadline:
                sock.settimeout(max(deadline - time.monotonic(), 0.05))
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    break
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line.strip():
                        continue
                    try:
                        candidate = json.loads(line)
                    except Exception:
                        continue
                    prop = rid_to_prop.get(candidate.get("request_id"))
                    if prop:
                        responses[prop] = candidate.get("data")
    except socket.timeout:
        return "timeout", "socket_timeout", responses, int((time.monotonic() - start) * 1000)
    except Exception as exc:
        return "error", type(exc).__name__, responses, int((time.monotonic() - start) * 1000)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if len(responses) < len(rid_to_prop):
        return "timeout", "partial_response", responses, elapsed_ms
    return "success", "", responses, elapsed_ms


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _decode_sample(ipc_path: Path, *, boot_id: str) -> dict[str, Any]:
    props = [
        "estimated-frame-number", "time-pos", "duration", "hwdec-current",
        "vo-configured", "idle-active", "pause", "eof-reached",
    ]
    status, error, values, elapsed_ms = _ipc_query_props(ipc_path, props, timeout_s=0.8)
    return {
        "boot_id": boot_id,
        "monotonic": time.monotonic(),
        "ipc_result": status,
        "ipc_error": error,
        "ipc_elapsed_ms": elapsed_ms,
        "estimated_frame_number": values.get("estimated-frame-number"),
        "time_pos": values.get("time-pos"),
        "duration": values.get("duration"),
        "hwdec_current": values.get("hwdec-current"),
        "vo_configured": values.get("vo-configured"),
        "idle_active": values.get("idle-active"),
        "pause": values.get("pause"),
        "eof_reached": values.get("eof-reached"),
    }


def _decode_confirm(samples: list[dict[str, Any]], *, signal_monotonic: float | None = None) -> dict[str, Any]:
    errors: list[str] = []
    good = [s for s in samples if s.get("ipc_result") == "success"]
    if len(good) < 3:
        errors.append("too_few_samples")
    for prev, cur in zip(good, good[1:]):
        pm, cm = _number(prev.get("monotonic")), _number(cur.get("monotonic"))
        if pm is None or cm is None or cm <= pm:
            errors.append("sample_monotonic_not_increasing")
        elif cm - pm < 0.5:
            errors.append("sample_spacing_too_short")
    frames = [_number(s.get("estimated_frame_number")) for s in good]
    times = [_number(s.get("time_pos")) for s in good]
    duration = _number(good[-1].get("duration")) if good else None
    if any(v is None for v in frames) or any(v is None for v in times):
        errors.append("sample_missing_frame_or_time")
    elif any(cur <= prev for prev, cur in zip(frames, frames[1:])):  # type: ignore[arg-type]
        errors.append("frames_not_strictly_increasing")
    elif (times[-1] - times[0]) < 0.2:  # type: ignore[operator]
        errors.append("time_pos_not_advancing")
    if good:
        last = good[-1]
        if last.get("hwdec_current") != EXPECTED_HWDEC:
            errors.append("hwdec_current_not_expected")
        if last.get("vo_configured") is not True:
            errors.append("vo_not_configured")
        for key in ("idle_active", "pause", "eof_reached"):
            if last.get(key) is not False:
                errors.append(f"{key}_not_false")
        if duration is None or times[-1] is None:  # type: ignore[index]
            errors.append("duration_or_time_missing")
        elif duration - times[-1] < MID_DECODE_EOF_MARGIN_SEC:  # type: ignore[operator]
            errors.append("eof_margin_too_small")
        if signal_monotonic is not None:
            last_m = _number(last.get("monotonic"))
            if last_m is None or signal_monotonic - last_m > MID_DECODE_MAX_SAMPLE_TO_SIGNAL_SEC:
                errors.append("last_sample_stale_for_signal")
            elif signal_monotonic < last_m:
                errors.append("signal_before_last_sample")
    return {
        "confirmed": not errors,
        "errors": errors,
        "samples_n": len(good),
        "frame_first": frames[0] if frames and frames[0] is not None else None,
        "frame_last": frames[-1] if frames and frames[-1] is not None else None,
        "time_pos_first": times[0] if times and times[0] is not None else None,
        "time_pos_last": times[-1] if times and times[-1] is not None else None,
        "duration": duration,
        "hwdec_current": good[-1].get("hwdec_current") if good else None,
        "last_sample_monotonic": good[-1].get("monotonic") if good else None,
        "last_sample_to_signal_sec": (
            signal_monotonic - float(good[-1]["monotonic"])
            if signal_monotonic is not None and good and isinstance(good[-1].get("monotonic"), (int, float))
            else None
        ),
        "mid_decode_margin_sec": (
            duration - times[-1]  # type: ignore[operator]
            if duration is not None and times and times[-1] is not None else None
        ),
    }


def _wait_for_mpv_identity(log_path: Path, *, ipc_path: Path, timeout_sec: float = 20.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_sec
    last_text = ""
    while time.monotonic() < deadline:
        try:
            last_text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            last_text = ""
        match = MPV_STARTED_RE.search(last_text)
        if match:
            pid = int(match.group("pid"))
            identity = _read_proc_identity(pid, ipc_path=str(ipc_path))
            identity["log_pid"] = pid
            return identity
        time.sleep(0.1)
    return {"error": "mpv_pid_not_observed", "log_tail": last_text[-400:]}


def _pgrep_mpv() -> list[int]:
    proc = _run(["pgrep", "-x", "mpv"], timeout=10.0)
    pids: list[int] = []
    for token in (proc.stdout or "").split():
        try:
            pids.append(int(token))
        except ValueError:
            pass
    return pids


def _fuser_dri() -> str:
    candidates = [Path("/dev/dri/card0"), Path("/dev/dri/renderD128")]
    paths = [str(p) for p in candidates if p.exists()]
    if not paths:
        return ""
    proc = _run(["fuser", *paths], timeout=10.0)
    return ((proc.stdout or "") + (proc.stderr or "")).strip()


def _wait_for_no_mpv_or_dri(timeout_sec: float = 10.0) -> tuple[bool, list[int], str]:
    deadline = time.monotonic() + timeout_sec
    last_mpv: list[int] = []
    last_fuser = ""
    while time.monotonic() < deadline:
        last_mpv = _pgrep_mpv()
        last_fuser = _fuser_dri()
        if not last_mpv and not last_fuser:
            return True, last_mpv, last_fuser
        time.sleep(0.25)
    return False, last_mpv, last_fuser


def _collect_deep_health_output(output_dir: Path, *, duration_sec: float, interval_sec: float) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    proc = _run(
        [
            sys.executable, str(HEALTH_COLLECTOR),
            "--duration-sec", str(duration_sec),
            "--interval-sec", str(interval_sec),
            "--output-dir", str(output_dir),
            "--panfrost-fault-policy", "absolute",
            "--json",
        ],
        timeout=max(300.0, duration_sec + 120.0),
    )
    public = output_dir / "playback-deep-health-public.json"
    if public.is_file():
        return json.loads(public.read_text(encoding="utf-8"))
    return {
        "schema": PLAYBACK_SCHEMA,
        "passed": False,
        "failure_reasons": ["deep_health_collector_no_output"],
        "checks": {k: False for k in HEALTH_CHECKS},
        "collector_rc": proc.returncode,
    }


def _restore_after_mid_decode_probe(probe_dir: Path, workspaces: list[Path], *,
                                    duration_sec: float, interval_sec: float) -> dict[str, Any]:
    killed = 0
    for ws in workspaces:
        killed += _kill_probe_orphans(ws)
    barrier_passed, before_start_mpv, before_start_fuser = _wait_for_no_mpv_or_dri(timeout_sec=10.0)
    if not barrier_passed:
        restore = {
            "service": SERVICE_NAME,
            "start_rc": None,
            "active": False,
            "reset_failed_used": False,
            "probe_orphans_killed": killed,
            "pre_start_barrier_passed": False,
            "pre_start_mpv_pids": before_start_mpv,
            "pre_start_fuser_dri": before_start_fuser,
            "deep_health_passed": False,
        }
        write_json(probe_dir / "service-restore.json", restore)
        return restore
    start = _run(["systemctl", "start", SERVICE_NAME], timeout=60.0)
    active = False
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if _service_active():
            active = True
            break
        time.sleep(1.0)
    reset_failed_used = False
    if not active:
        reset_failed_used = True
        _run(["systemctl", "reset-failed", SERVICE_NAME], timeout=20.0)
        _run(["systemctl", "start", SERVICE_NAME], timeout=60.0)
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            if _service_active():
                active = True
                break
            time.sleep(1.0)
    health = _collect_deep_health_output(
        probe_dir / "post-restore-health",
        duration_sec=duration_sec,
        interval_sec=interval_sec,
    ) if active else {
        "schema": PLAYBACK_SCHEMA,
        "passed": False,
        "failure_reasons": ["service_not_active_after_restore"],
        "checks": {k: False for k in HEALTH_CHECKS},
    }
    restore = {
        "service": SERVICE_NAME,
        "start_rc": start.returncode,
        "active": active,
        "reset_failed_used": reset_failed_used,
        "probe_orphans_killed": killed,
        "pre_start_barrier_passed": True,
        "pre_start_mpv_pids": before_start_mpv,
        "pre_start_fuser_dri": before_start_fuser,
        "deep_health_passed": bool(health.get("passed")),
    }
    write_json(probe_dir / "service-restore.json", restore)
    return restore


def _prepare_mid_decode_attempt_setups(attempts_n: int, *, canary: Path,
                                       workspaces: list[Path]) -> list[dict[str, Any]]:
    import c18_player_runtime_candidate_health as ch

    setups: list[dict[str, Any]] = []
    kiosk_path = _resolve_probe_kiosk()
    run_user = ch.candidate_run_user()
    for index in range(attempts_n):
        ws = Path(tempfile.mkdtemp(prefix=f"c18-mid-decode-{index:02d}-"))
        workspaces.append(ws)
        cfg = ch.candidate_config(None, ws)
        config_path = ws / "probe-config.json"
        write_json(config_path, cfg)
        ch.write_canary_playlist(cfg, canary)
        for sub in ("runtime_dir", "state_dir", "cache_dir"):
            Path(str(cfg[sub])).mkdir(parents=True, exist_ok=True)
        ch.chown_tree(ws, run_user.pw_uid, run_user.pw_gid)
        inaccessible = ch.access_failures_as_user(
            ch.access_check_targets(cfg, kiosk_path.parent, ws, config_path, canary),
            run_user,
        )
        if inaccessible:
            raise RuntimeError(
                "mid_decode_probe_workspace_inaccessible_to_run_user:"
                + ",".join(sorted(set(inaccessible)))
            )
        setups.append({
            "index": index,
            "workspace": ws,
            "cfg": cfg,
            "config_path": config_path,
            "env": ch.minimal_candidate_env(ws),
            "run_user": run_user,
            "kiosk_path": kiosk_path,
        })
    return setups


def _run_one_mid_decode_attempt(index: int, *, args: argparse.Namespace,
                                probe_dir: Path, boot_id: str,
                                setup: dict[str, Any]) -> dict[str, Any]:
    import c18_player_runtime_candidate_health as ch

    attempt_dir = probe_dir / f"attempt-{index:02d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    kiosk_path = Path(str(setup["kiosk_path"]))
    cfg = setup["cfg"]
    config_path = Path(str(setup["config_path"]))
    env = setup["env"]
    run_user = setup["run_user"]

    stdout_path = attempt_dir / "probe-stdout.txt"
    stderr_path = attempt_dir / "probe-stderr.txt"
    proc: subprocess.Popen[str] | None = None
    samples: list[dict[str, Any]] = []
    kernel_before_text = ""
    kernel_after_text = ""
    monotonic_before = time.monotonic()
    monotonic_after = monotonic_before + 0.001
    signal_info: dict[str, Any] = {"name": "SIGTERM", "target": "mpv_pgid", "delivered": False}
    mpv_exit: dict[str, Any] = {"exited": False, "waited_ms": 0, "escalated": False}
    pid_chain: dict[str, Any] = {}
    failure_reasons: list[str] = []
    kiosk_killed = False
    try:
        with stdout_path.open("w", encoding="utf-8") as so, stderr_path.open("w", encoding="utf-8") as se:
            proc = subprocess.Popen(
                [sys.executable, str(kiosk_path), "--config", str(config_path)],
                cwd=str(kiosk_path.parent), env=env, text=True,
                stdout=so, stderr=se,
                preexec_fn=ch.drop_to_user_preexec(run_user.pw_name, run_user.pw_uid, run_user.pw_gid),
            )
        identity = _wait_for_mpv_identity(Path(str(cfg["log_file"])), ipc_path=Path(str(cfg["ipc_path"])))
        pid_chain["initial"] = identity
        if "error" in identity or not _proc_identity_ok(identity):
            failure_reasons.append("mpv_identity_not_verified")
            return {
                "index": index, "passed": False, "failure_reasons": failure_reasons,
                "pid_chain": pid_chain,
            }
        pid = int(identity["pid"])
        starttime = int(identity["starttime"])
        ipc_path = Path(str(cfg["ipc_path"]))
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            samples.append(_decode_sample(ipc_path, boot_id=boot_id))
            confirm = _decode_confirm(samples)
            if confirm["confirmed"]:
                break
            time.sleep(0.5)
        if not _decode_confirm(samples)["confirmed"]:
            failure_reasons.append("decode_not_confirmed")
            return {
                "index": index, "passed": False, "failure_reasons": failure_reasons,
                "pid_chain": pid_chain, "decode_confirm": _decode_confirm(samples),
            }
        if proc.poll() is None:
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5.0)
        kiosk_killed = True
        orphan_identity = _read_proc_identity(pid, ipc_path=str(ipc_path))
        pid_chain["after_kiosk_kill"] = orphan_identity
        if not _proc_identity_ok(orphan_identity, starttime=starttime):
            failure_reasons.append("mpv_exited_before_signal")
            return {
                "index": index, "passed": False, "failure_reasons": failure_reasons,
                "pid_chain": pid_chain, "decode_confirm": _decode_confirm(samples),
            }

        kernel_before_text = _capture_kernel_fault_lines()
        monotonic_before = time.monotonic()
        if samples and isinstance(samples[-1].get("monotonic"), (int, float)):
            age = time.monotonic() - float(samples[-1]["monotonic"])
            if age < 0.55:
                time.sleep(0.55 - age)
        final_sample = _decode_sample(ipc_path, boot_id=boot_id)
        samples.append(final_sample)
        presignal = _read_proc_identity(pid, ipc_path=str(ipc_path))
        pid_chain["pre_signal"] = presignal
        signal_monotonic = time.monotonic()
        confirm = _decode_confirm(samples, signal_monotonic=signal_monotonic)
        if not confirm["confirmed"] or not _proc_identity_ok(presignal, starttime=starttime):
            failure_reasons.append("decode_not_confirmed_at_signal")
            return {
                "index": index, "passed": False, "failure_reasons": failure_reasons,
                "pid_chain": pid_chain, "decode_confirm": confirm,
            }
        os.killpg(pid, signal.SIGTERM)
        signal_info = {
            "name": "SIGTERM",
            "target": "mpv_pgid",
            "delivered": True,
            "monotonic": signal_monotonic,
        }
        started = time.monotonic()
        exited = False
        while time.monotonic() - started < 5.0:
            post = _read_proc_identity(pid, ipc_path=str(ipc_path))
            if post.get("exists") is not True or post.get("state") == "Z":
                exited = True
                break
            time.sleep(0.1)
        waited_ms = int((time.monotonic() - started) * 1000)
        escalated = False
        if not exited:
            escalated = True
            try:
                os.killpg(pid, signal.SIGKILL)
            except OSError:
                pass
            failure_reasons.append("mpv_did_not_exit_after_sigterm")
        time.sleep(max(float(getattr(args, "settle_sec", 3.0)), 0.0))
        kernel_after_text = _capture_kernel_fault_lines()
        monotonic_after = time.monotonic()
        mpv_exit = {"exited": exited, "waited_ms": waited_ms, "escalated": escalated}
    except Exception as exc:
        failure_reasons.append(f"mid_decode_probe_exception:{type(exc).__name__}")
    finally:
        if proc is not None and proc.poll() is None:
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                proc.wait(timeout=5.0)
            except Exception:
                pass
        try:
            log_text = Path(str(cfg["log_file"])).read_text(encoding="utf-8", errors="replace")
            tail = "\n".join(ch.sanitize_lines(log_text)[-120:])
            (attempt_dir / "probe-kiosk-log-tail.txt").write_text(tail + "\n", encoding="utf-8")
        except Exception:
            pass
        for src, dest in ((stdout_path, attempt_dir / "probe-stdout.txt"), (stderr_path, attempt_dir / "probe-stderr.txt")):
            try:
                lines = ch.sanitize_lines(src.read_text(encoding="utf-8", errors="replace"))
                dest.write_text("\n".join(lines[-80:]) + ("\n" if lines else ""), encoding="utf-8")
            except OSError:
                pass
        _write_ndjson(attempt_dir / "decode-samples.ndjson", samples)
        (attempt_dir / "kernel-before.txt").write_text(_kernel_window_text(kernel_before_text), encoding="utf-8")
        (attempt_dir / "kernel-after.txt").write_text(_kernel_window_text(kernel_after_text), encoding="utf-8")
    _write_ndjson(attempt_dir / "decode-samples.ndjson", samples)
    (attempt_dir / "kernel-before.txt").write_text(_kernel_window_text(kernel_before_text), encoding="utf-8")
    (attempt_dir / "kernel-after.txt").write_text(_kernel_window_text(kernel_after_text), encoding="utf-8")
    before_faults, after_faults = fault_lines(kernel_before_text), fault_lines(kernel_after_text)
    before, after, delta, anomalous = compute_window_delta(before_faults, after_faults)
    confirm = _decode_confirm(samples, signal_monotonic=signal_info.get("monotonic"))
    if delta != 0:
        failure_reasons.append("mid_decode_probe_gpu_faults_delta_nonzero")
    if before_faults or after_faults:
        failure_reasons.append("mid_decode_probe_panfrost_faults_present")
    if mpv_exit.get("escalated"):
        failure_reasons.append("mid_decode_probe_mpv_escalated_after_sigterm")
    if not confirm.get("confirmed"):
        failure_reasons.append("mid_decode_probe_decode_not_confirmed")
    passed = not failure_reasons and mpv_exit.get("exited") is True
    return {
        "index": index,
        "passed": passed,
        "failure_reasons": sorted(set(failure_reasons)),
        "window_anchor": {
            "boot_id": boot_id,
            "monotonic_before": monotonic_before,
            "monotonic_after": monotonic_after if monotonic_after > monotonic_before else monotonic_before + 0.001,
        },
        "pid_chain": pid_chain,
        "decode_confirm": confirm,
        "signal": signal_info,
        "mpv_exit": mpv_exit,
        "kiosk_killed_before_signal": kiosk_killed,
        "gpu_faults_before": before,
        "gpu_faults_after": after,
        "gpu_faults_delta": delta,
        "gpu_faults_delta_anomalous": anomalous,
        "new_fault_lines_sanitized": [sanitize_kernel_line(ln) for ln in after_faults[len(before_faults):]][:20],
    }


def _run_mid_decode_sigterm_probe(args: argparse.Namespace, run_root: Path,
                                  boot_state: dict[str, Any],
                                  last_cycle_after: float | None) -> dict[str, Any]:
    import c18_player_runtime_candidate_health as ch

    probe_dir = run_root / "mid-decode-sigterm-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    attempts_n = max(1, int(getattr(args, "mid_decode_probe_attempts", None) or 1))
    workspaces: list[Path] = []
    service_stopped = False
    attempts: list[dict[str, Any]] = []
    production_service: dict[str, Any] = {
        "stopped": False,
        "restored": False,
        "deep_health_passed": False,
    }
    failure_reasons: list[str] = []
    try:
        if Path("/run/totem/settings-session.lock").exists():
            failure_reasons.append("settings_session_lock_present")
            raise RuntimeError("settings_session_lock_present")
        canary_arg = getattr(args, "mid_decode_probe_canary_media", None)
        canary = ch.normalize_canary_media(Path(canary_arg) if canary_arg else None)
        if canary is None:
            failure_reasons.append("mid_decode_probe_canary_missing")
            raise RuntimeError("mid_decode_probe_canary_missing")
        try:
            setups = _prepare_mid_decode_attempt_setups(attempts_n, canary=canary, workspaces=workspaces)
        except RuntimeError as exc:
            failure_reasons.append(str(exc))
            raise
        stop = _run(["systemctl", "stop", SERVICE_NAME], timeout=60.0)
        production_service["stop_rc"] = stop.returncode
        production_service["stopped"] = stop.returncode == 0
        service_stopped = True
        time.sleep(1.0)
        residual = _pgrep_mpv()
        production_service["residual_mpv_pids_after_stop"] = residual
        if residual:
            failure_reasons.append("production_mpv_still_running")
            raise RuntimeError("production_mpv_still_running")
        for index in range(attempts_n):
            attempt = _run_one_mid_decode_attempt(
                index, args=args, probe_dir=probe_dir,
                boot_id=str(boot_state.get("boot_id") or ""), setup=setups[index],
            )
            if last_cycle_after is not None:
                attempt["last_cycle_after"] = last_cycle_after
            attempts.append(attempt)
    except Exception as exc:
        if not failure_reasons:
            failure_reasons.append(f"mid_decode_probe_exception:{type(exc).__name__}")
    finally:
        if service_stopped:
            restore = _restore_after_mid_decode_probe(
                probe_dir, workspaces,
                duration_sec=float(getattr(args, "health_duration_sec", 30.0)),
                interval_sec=float(getattr(args, "health_interval_sec", 1.0)),
            )
            production_service["restored"] = bool(restore.get("active"))
            production_service["deep_health_passed"] = bool(restore.get("deep_health_passed"))
        else:
            production_service["restored"] = _service_active()
            production_service["deep_health_passed"] = production_service["restored"]
        for ws in workspaces:
            shutil.rmtree(ws, ignore_errors=True)
    if not attempts:
        attempts.append({
            "index": 0,
            "passed": False,
            "failure_reasons": sorted(set(failure_reasons or ["mid_decode_probe_not_attempted"])),
        })
    non_claims = list(MID_DECODE_NON_CLAIMS)
    non_claims.append(f"N={len(attempts)} single-image")
    wrapper_path = Path(EXPECTED_WRAPPER)
    artifact = {
        "schema": MID_DECODE_SCHEMA,
        "passed": all(a.get("passed") is True for a in attempts)
        and production_service.get("restored") is True
        and production_service.get("deep_health_passed") is True,
        "claim": "mid_decode_sigterm_panfrost_window_measured",
        "kiosk_killed_before_signal": True,
        "cfg_hwdec": "auto",
        "wrapper": {
            "path": EXPECTED_WRAPPER,
            "sha256": sha256_file(wrapper_path) if wrapper_path.is_file() else "",
        },
        "production_service": production_service,
        "attempts": attempts,
        "non_claims": non_claims,
    }
    write_json(run_root / "mid_decode_sigterm_probe.json", artifact)
    return artifact


def _freeze_postcheck(updatectl: str, manifest_path: str) -> dict[str, int]:
    """Re-attest the player-runtime freeze via the PUBLIC updater verbs.

    Runs the public apply-local / rollback / reconcile verbs for player-runtime
    and returns their return codes. Each MUST be ``44`` (frozen) for the gate's
    postcheck to pass. We do NOT pass the reconcile maintenance guard, so the
    public reconcile path stays frozen.
    """
    rollback = _run([updatectl, "rollback", "--component", "player-runtime"], timeout=30.0).returncode
    reconcile = _run([updatectl, "reconcile", "--component", "player-runtime"], timeout=30.0).returncode
    # `apply-local` takes the manifest as a POSITIONAL arg (the CLI usage is
    # `apply-local [--component X] [--payload P] manifest`). Passing it as
    # `--manifest <p>` makes argparse fail with "unrecognized arguments" -> rc=2,
    # which the HW run exposed. Keep the manifest trailing-positional.
    apply_local = _run(
        [updatectl, "apply-local", "--component", "player-runtime", manifest_path],
        timeout=30.0,
    ).returncode
    return {
        "apply_local_rc": apply_local,
        "rollback_rc": rollback,
        "reconcile_rc": reconcile,
    }


def _git_head() -> str:
    proc = _run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], timeout=20.0)
    return (proc.stdout or "").strip()


# --------------------------------------------------------------------------- #
# Live orchestration.                                                          #
# --------------------------------------------------------------------------- #
def _cycle_kinds(n: int) -> list[str]:
    """Plan N cycle kinds: cycle-00 is a service_restart; the rest relaunch.

    At least one service_restart is REQUIRED by the gate (GR3). We front-load it
    so a 2-cycle run is [service_restart, relaunch].
    """
    return ["service_restart"] + ["relaunch"] * (n - 1)


def _write_postcheck(root: Path, *, boot_state: dict[str, Any], freeze: dict[str, int],
                     service_active: bool, timer_enabled: bool) -> None:
    lines = [
        f"BOOT_ID={boot_state['boot_id']}",
        f"UPTIME={boot_state['uptime']}",
        f"SERVICE_ACTIVE={'active' if service_active else 'inactive'}",
        f"TIMER_ENABLED={'enabled' if timer_enabled else 'disabled'}",
        "STRICT_GPU_FAULTS=0",
        f"PUBLIC_PLAYER_RUNTIME_APPLY_LOCAL_RC={freeze['apply_local_rc']}",
        f"PUBLIC_PLAYER_RUNTIME_ROLLBACK_RC={freeze['rollback_rc']}",
        f"PUBLIC_PLAYER_RUNTIME_RECONCILE_RC={freeze['reconcile_rc']}",
    ]
    (root / "postcheck.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_trial(args: argparse.Namespace) -> int:
    """Drive the real HW teardown trial and emit gate-passing evidence.

    Captures one boot_state, runs ``args.cycles`` (>=2) launch/teardown cycles in
    that single boot (>=1 ``service_restart``), recording a per-window panfrost
    fault delta and per-cycle deep-health for each, optionally drives the
    fresh-IPC corner, re-attests the player-runtime freeze (public rc 44), seals
    the manifest, and writes everything under ``args.run_root``. The structured
    emission is fully covered by ``--self-test`` (which shims the board seams);
    this path itself stays lab-guarded and fails closed off-board.
    """
    require_lab_guard()
    cycles_n = int(getattr(args, "cycles", 2))
    if cycles_n < 2:
        sys.stderr.write("run_trial: --cycles must be >= 2 (gate requires >=2 same-boot cycles)\n")
        raise SystemExit(2)

    run_root = Path(args.run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(run_root, 0o700)
    except OSError:
        pass

    updatectl = getattr(args, "updatectl", None) or DEFAULT_UPDATECTL
    config_path = Path(getattr(args, "config", None) or DEFAULT_CONFIG)
    duration_sec = float(getattr(args, "health_duration_sec", 30.0))
    interval_sec = float(getattr(args, "health_interval_sec", 1.0))
    settle_sec = float(getattr(args, "settle_sec", 3.0))
    startup_wait_sec = float(getattr(args, "startup_wait_sec", 5.0))
    freeze_manifest = getattr(args, "freeze_manifest", None) or "/nonexistent/player-runtime.manifest.json"
    timer_name = getattr(args, "timer", None) or "kiosky-player-update.timer"

    boot_state = _boot_state()
    boot_id = boot_state["boot_id"]
    if not boot_id:
        sys.stderr.write("run_trial: could not read boot_id from /proc/sys/kernel/random/boot_id\n")
        raise SystemExit(1)

    cycles: list[dict[str, Any]] = []
    try:
        for index, kind in enumerate(_cycle_kinds(cycles_n)):
            # Before-window faults + monotonic anchor.
            before_text = _capture_kernel_fault_lines()
            before = fault_lines(before_text)
            monotonic_before = time.monotonic()

            # The teardown itself.
            if kind == "service_restart":
                stop = _service_restart()
            else:
                stop = _run_relaunch_teardown()

            # Settle, let the player come back, let any late GPU faults land.
            time.sleep(max(settle_sec, 0.0))

            # After-window faults + monotonic anchor.
            after_text = _capture_kernel_fault_lines()
            after = fault_lines(after_text)
            monotonic_after = time.monotonic()
            if monotonic_after <= monotonic_before:  # defensive: guarantee +width window
                monotonic_after = monotonic_before + 0.001

            # Per-cycle deep-health against the (restarted) live service.
            cycle_dir = run_root / f"cycles/cycle-{index:02d}"
            time.sleep(max(startup_wait_sec, 0.0))
            health = _collect_deep_health(cycle_dir, duration_sec=duration_sec, interval_sec=interval_sec)
            health_passed = bool(health.get("passed"))

            stop_record = {k: stop[k] for k in ("method", "returncode", "elapsed_ms") if k in stop}
            stop_record.setdefault("method", "none")
            stop_record.setdefault("returncode", stop.get("returncode"))

            cycle = build_cycle_record(
                index, kind, boot_id,
                before=before, after=after,
                monotonic_before=monotonic_before, monotonic_after=monotonic_after,
                stop=stop_record,
                process_exited=(stop.get("returncode") == 0),
                health_passed=health_passed,
            )
            cycles.append(cycle)
            write_cycle_dir(
                run_root, cycle, health=health,
                kernel_before=_kernel_window_text(before_text),
                kernel_after=_kernel_window_text(after_text),
            )

        # Optional fresh-IPC probe (honest; the gate rejects "fresh_sent"). A probe
        # failure must NEVER lose the cycles' evidence: any exception degrades to an
        # honest not-forced artifact (gate REDs the probe; cycles/manifest survive).
        gr4_secondary_present = bool(getattr(args, "with_fresh_ipc_probe", False))
        if gr4_secondary_present:
            try:
                kiosk_log, probe_kwargs = _run_fresh_ipc_probe(args, run_root)
            except Exception as exc:
                kiosk_log, probe_kwargs = "", {
                    "forced_ipc_none": False, "forcing_method": "none",
                    "probe": {"error": f"probe_exception:{type(exc).__name__}"},
                }
            write_json(run_root / "fresh_ipc_probe.json",
                       classify_fresh_ipc(kiosk_log, **probe_kwargs))

        mid_decode_probe_present = bool(getattr(args, "with_mid_decode_sigterm_probe", False))
        if mid_decode_probe_present:
            finite_cycle_ends = [
                c.get("window_anchor", {}).get("monotonic_after")
                for c in cycles
                if isinstance(c.get("window_anchor"), dict)
                and isinstance(c.get("window_anchor", {}).get("monotonic_after"), (int, float))
            ]
            _run_mid_decode_sigterm_probe(
                args, run_root, boot_state,
                max(finite_cycle_ends) if finite_cycle_ends else None,
            )

        # Setup/state breadcrumb (informational; sanitized).
        write_json(run_root / "setup/service-state-before.json", {
            "is_active": "active" if _service_active() else "inactive",
            "boot_id_present": bool(boot_id),
        })

        # Freeze re-attestation via the PUBLIC updater verbs (each MUST be rc 44).
        freeze = _freeze_postcheck(updatectl, freeze_manifest)
        _write_postcheck(
            run_root,
            boot_state=boot_state,
            freeze=freeze,
            service_active=_service_active(),
            timer_enabled=_timer_enabled(timer_name),
        )

        (run_root / "README.md").write_text(
            "# C18 player-runtime teardown/panfrost trial evidence\n"
            "Producer: scripts/board/c18_player_runtime_teardown_trial.py\n"
            "Validate with: scripts/qa/c18_player_runtime_teardown_evidence_gate.py\n",
            encoding="utf-8",
        )

        summary = build_summary(
            boot_id, int(boot_state["btime"]), cycles,
            gr4_secondary_present=gr4_secondary_present,
            mid_decode_probe_present=mid_decode_probe_present,
        )
        write_json(run_root / "teardown-summary.json", summary)

        source_commit = getattr(args, "source_commit", None) or _git_head()
        seal_manifest(
            run_root,
            artifact_id=f"c18-player-runtime-teardown-{boot_id[:12]}",
            board_image_marker=str(getattr(args, "board_image_marker", None) or "c18-hwdecode-lab"),
            source_commit=source_commit,
        )
    finally:
        # Always leave the production player running.
        try:
            _run(["systemctl", "start", SERVICE_NAME], timeout=60.0)
        except Exception:
            pass

    # Validate our own output with the real gate before returning success.
    proc = _run([sys.executable, str(GATE), "--run-dir", str(run_root), "--json"], timeout=120.0)
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.stderr.write(f"run_trial: gate REJECTED the produced evidence at {run_root}\n")
        return 1
    sys.stderr.write(f"run_trial: gate PASSED; evidence at {run_root}\n")
    return 0 if bool(summary.get("passed")) else 1


# --------------------------------------------------------------------------- #
# Self-test: pure logic + producer->gate round trip.                          #
# --------------------------------------------------------------------------- #
def _make_health() -> dict[str, Any]:
    return {
        "schema": PLAYBACK_SCHEMA,
        "passed": True,
        "failure_reasons": [],
        "checks": {k: True for k in HEALTH_CHECKS},
    }


def _build_clean_fixture(root: Path) -> None:
    boot_id = "00000000-0000-4000-8000-000000000000"
    before: list[str] = []  # clean board -> zero panfrost faults in any window
    clean_text = "kernel: window clean; zero matching gpu hardware events\n"
    cycles = []
    for index, kind in ((0, "relaunch"), (1, "service_restart")):
        cycle = build_cycle_record(
            index, kind, boot_id,
            before=before, after=before,  # delta 0
            monotonic_before=100.0 + index * 10, monotonic_after=103.0 + index * 10,
            stop={"method": "ipc_quit", "returncode": 0, "elapsed_ms": 400 + index},
            process_exited=True, health_passed=True,
        )
        cycles.append(cycle)
        write_cycle_dir(root, cycle, health=_make_health(),
                        kernel_before=clean_text, kernel_after=clean_text)
    fresh = classify_fresh_ipc(
        "... MPV IPC fresh command failed command=quit ...",
        forced_ipc_none=True, forcing_method="short_mpv_startup_timeout_sec",
    )
    write_json(root / "fresh_ipc_probe.json", fresh)
    write_json(root / "setup/service-state-before.json", {"is_active": "active", "is_enabled": "enabled"})
    summary = build_summary(boot_id, 1700000000, cycles, gr4_secondary_present=True)
    write_json(root / "teardown-summary.json", summary)
    (root / "postcheck.txt").write_text(
        "BOOT_ID=00000000-0000-4000-8000-000000000000\nUPTIME=42.0\n"
        "SERVICE_ACTIVE=active\nTIMER_ENABLED=disabled\nSTRICT_GPU_FAULTS=0\n"
        "PUBLIC_PLAYER_RUNTIME_APPLY_LOCAL_RC=44\nPUBLIC_PLAYER_RUNTIME_ROLLBACK_RC=44\n"
        "PUBLIC_PLAYER_RUNTIME_RECONCILE_RC=44\n", encoding="utf-8")
    (root / "README.md").write_text("# c18 teardown self-test fixture\n", encoding="utf-8")
    seal_manifest(root, artifact_id="selftest", board_image_marker="c18-selftest", source_commit="a" * 40)


class TeardownTrialSelfTest(unittest.TestCase):
    def test_delta_zero(self) -> None:
        b, a, delta, anomalous = compute_window_delta(["x"], ["x"])
        self.assertEqual((b, a, delta, anomalous), (1, 1, 0, False))

    def test_delta_positive(self) -> None:
        _, _, delta, anomalous = compute_window_delta(["x"], ["x", "y"])
        self.assertEqual(delta, 1)
        self.assertFalse(anomalous)

    def test_delta_negative_is_anomalous(self) -> None:
        # Journal rotation: fewer lines after than before -> must NOT clamp to 0.
        _, _, delta, anomalous = compute_window_delta(["x", "y", "z"], ["x"])
        self.assertEqual(delta, -2)
        self.assertTrue(anomalous)

    def test_cycle_fails_on_nonzero_delta(self) -> None:
        cycle = build_cycle_record(
            0, "relaunch", "boot",
            before=[], after=["panfrost fault: oops"],
            monotonic_before=1.0, monotonic_after=2.0,
            stop={"method": "ipc_quit", "returncode": 0, "elapsed_ms": 1},
            process_exited=True, health_passed=True,
        )
        self.assertEqual(cycle["gpu_faults_delta"], 1)
        self.assertFalse(cycle["passed"])

    def test_fresh_ipc_classify_honesty(self) -> None:
        self.assertEqual(classify_fresh_ipc(FRESH_SENT_LOG)["outcome"], "fresh_sent")
        self.assertEqual(classify_fresh_ipc(FRESH_FAILED_LOG)["outcome"], "fresh_failed_fallback_sigterm")
        none = classify_fresh_ipc("no fresh log here")
        self.assertEqual(none["outcome"], "fresh_failed_fallback_sigterm")
        self.assertFalse(none["code_path_reached"])

    def test_fresh_ipc_classify_defaults_to_not_forced(self) -> None:
        # REGRESSION (convergence 2026-06-10): forced_ipc_none was hardcoded True,
        # claiming a staged corner even when nothing forced it. The default MUST be
        # False so an un-staged probe is rejected by the gate, never trusted.
        probe = classify_fresh_ipc(FRESH_FAILED_LOG)
        self.assertIs(probe["forced_ipc_none"], False)
        self.assertEqual(probe["forcing_method"], "none")

    def test_unforced_probe_rejected_by_gate(self) -> None:
        # Gate round-trip: a probe artifact whose staging did NOT happen
        # (forced_ipc_none=False) must RED the real gate.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_clean_fixture(root)
            write_json(root / "fresh_ipc_probe.json",
                       classify_fresh_ipc("... MPV IPC fresh command failed command=quit ..."))
            seal_manifest(root, artifact_id="selftest", board_image_marker="c18-selftest",
                          source_commit="a" * 40)
            proc = subprocess.run(
                [sys.executable, str(GATE), "--run-dir", str(root), "--json"],
                capture_output=True, text=True, check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("fresh_ipc_probe_not_forced", proc.stdout + proc.stderr)

    def test_probe_without_fresh_line_rejected_by_gate(self) -> None:
        # The PRE-FIX probe behavior (service restart only): on a healthy board the
        # IPC connects, no fresh line is logged, and the corner is NOT reached. The
        # gate must RED that, so a no-op probe can never read as exercised.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_clean_fixture(root)
            write_json(root / "fresh_ipc_probe.json",
                       classify_fresh_ipc("service restarted; ipc connected fine",
                                          forced_ipc_none=True,
                                          forcing_method="short_mpv_startup_timeout_sec"))
            seal_manifest(root, artifact_id="selftest", board_image_marker="c18-selftest",
                          source_commit="a" * 40)
            proc = subprocess.run(
                [sys.executable, str(GATE), "--run-dir", str(root), "--json"],
                capture_output=True, text=True, check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("fresh_ipc_probe_code_path_not_reached", proc.stdout + proc.stderr)

    def test_probe_real_driver_stages_corner_end_to_end(self) -> None:
        """Run the REAL _run_fresh_ipc_probe off-board against a FAKE kiosk.

        REGRESSION (audit 2026-06-10, C1a/C1b): the fake kiosk emits the fresh
        line ONLY IF the staging is complete -- workspace dirs pre-created,
        offline canary playlist present, short mpv_startup_timeout_sec staged.
        The old probe (service restart only) and a probe that skips dir
        pre-creation or content staging both fail this test.
        """
        fake_kiosk = (
            "import json, sys, time\n"
            "from pathlib import Path\n"
            "cfg = json.loads(Path(sys.argv[sys.argv.index('--config') + 1]).read_text())\n"
            "state = Path(cfg['state_dir']); runtime = Path(cfg['runtime_dir'])\n"
            "playlist = state / 'playlist_last.json'\n"
            "ok = (state.is_dir() and runtime.is_dir() and playlist.is_file()\n"
            "      and float(cfg.get('mpv_startup_timeout_sec', 10.0)) <= 0.05)\n"
            "log = Path(cfg['log_file'])\n"
            "if ok:\n"
            "    log.write_text('MPV IPC fresh command failed command=quit error=probe\\n')\n"
            "else:\n"
            "    log.write_text('staging incomplete; no_content path\\n')\n"
            "time.sleep(30)\n"
        )
        mod = sys.modules[__name__]
        orig_resolve = mod._resolve_probe_kiosk
        with tempfile.TemporaryDirectory() as tmp:
            kiosk_path = Path(tmp) / "kiosk.py"
            kiosk_path.write_text(fake_kiosk, encoding="utf-8")
            canary = Path(tempfile.gettempdir()) / "c18-probe-selftest-canary.mp4"
            canary.write_bytes(b"x")
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            args = argparse.Namespace(
                fresh_ipc_probe_startup_timeout_sec=0.05,
                fresh_ipc_probe_attempts=2,
                fresh_ipc_probe_canary_media=canary,
            )
            try:
                mod._resolve_probe_kiosk = lambda: kiosk_path
                log_text, kwargs = _run_fresh_ipc_probe(args, run_root)
            finally:
                mod._resolve_probe_kiosk = orig_resolve
                try:
                    canary.unlink()
                except OSError:
                    pass
            self.assertIs(kwargs["forced_ipc_none"], True)
            self.assertEqual(kwargs["forcing_method"], "short_mpv_startup_timeout_sec")
            self.assertIs(kwargs["probe"]["canary_staged"], True)
            self.assertEqual(kwargs["probe"]["attempts"], 1)
            probe_json = classify_fresh_ipc(log_text, **kwargs)
            self.assertIs(probe_json["code_path_reached"], True)
            self.assertEqual(probe_json["outcome"], "fresh_failed_fallback_sigterm")
            tail = (run_root / "fresh-ipc-probe" / "probe-kiosk-log-tail.txt").read_text(encoding="utf-8")
            self.assertIn("MPV IPC fresh command failed command=quit", tail)

    def test_probe_real_driver_without_canary_is_not_forced(self) -> None:
        # No canary -> the kiosk would exit no_content before mpv.start(); the
        # probe must refuse to claim forcing AND persist a probe-error artifact.
        mod = sys.modules[__name__]
        orig_resolve = mod._resolve_probe_kiosk
        with tempfile.TemporaryDirectory() as tmp:
            kiosk_path = Path(tmp) / "kiosk.py"
            kiosk_path.write_text("print('fake')\n", encoding="utf-8")
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            args = argparse.Namespace(
                fresh_ipc_probe_startup_timeout_sec=0.05,
                fresh_ipc_probe_attempts=1,
                fresh_ipc_probe_canary_media=None,
            )
            try:
                mod._resolve_probe_kiosk = lambda: kiosk_path
                log_text, kwargs = _run_fresh_ipc_probe(args, run_root)
            finally:
                mod._resolve_probe_kiosk = orig_resolve
            self.assertEqual(log_text, "")
            self.assertIs(kwargs["forced_ipc_none"], False)
            self.assertEqual(kwargs["probe"]["error"], "probe_canary_missing")
            err = (run_root / "fresh-ipc-probe" / "probe-error.txt").read_text(encoding="utf-8")
            self.assertIn("probe_canary_missing", err)

    def test_producer_output_passes_gate(self) -> None:
        # The strongest check: evidence this harness emits must pass the real gate.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_clean_fixture(root)
            proc = subprocess.run(
                [sys.executable, str(GATE), "--run-dir", str(root), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_run_trial_end_to_end_passes_gate(self) -> None:
        """Run the FULL run_trial() with every board seam shimmed by a fake.

        This proves the LIVE orchestration emits gate-passing evidence with NO
        board: fake journalctl returns a clean window, fake systemctl ok, fake
        deep-health passing, fake freeze rc 44. We then shell out to the REAL
        gate and require rc 0.
        """
        import contextlib
        import io

        state = {"monotonic": 1000.0, "restarts": 0, "relaunches": 0,
                 "health_calls": 0, "fresh_probe_calls": 0, "mid_probe_calls": 0,
                 "freeze_calls": 0}

        def fake_monotonic() -> float:
            state["monotonic"] += 5.0  # strictly increasing -> non-overlapping windows
            return state["monotonic"]

        def fake_boot_state() -> dict[str, Any]:
            return {"boot_id": "11111111-2222-4333-8444-555555555555",
                    "btime": 1700000000, "uptime": 123.4}

        def fake_capture_kernel_fault_lines() -> str:
            return ""  # clean board: zero matching GPU fault lines in every window

        def fake_service_restart() -> dict[str, Any]:
            state["restarts"] += 1
            return {"method": "ipc_quit", "returncode": 0, "elapsed_ms": 410,
                    "kind": "service_restart"}

        def fake_relaunch() -> dict[str, Any]:
            state["relaunches"] += 1
            return {"method": "ipc_quit", "returncode": 0, "elapsed_ms": 520,
                    "kind": "relaunch"}

        def fake_collect_deep_health(cycle_dir: Path, *, duration_sec: float,
                                     interval_sec: float) -> dict[str, Any]:
            state["health_calls"] += 1
            (cycle_dir / "health").mkdir(parents=True, exist_ok=True)
            return _make_health()

        def fake_fresh_ipc_probe(args_: argparse.Namespace, run_root_: Path) -> tuple[str, dict[str, Any]]:
            state["fresh_probe_calls"] += 1
            # Honest forced-corner log: SIGTERM fallback, never "fresh_sent".
            return ("... MPV IPC fresh command failed command=quit ...\n",
                    {"forced_ipc_none": True,
                     "forcing_method": "short_mpv_startup_timeout_sec"})

        def fake_mid_decode_probe(args_: argparse.Namespace, run_root_: Path,
                                  boot_state_: dict[str, Any],
                                  last_cycle_after: float | None) -> dict[str, Any]:
            state["mid_probe_calls"] += 1
            probe_dir = run_root_ / "mid-decode-sigterm-probe"
            attempt_dir = probe_dir / "attempt-00"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            base = (last_cycle_after or 1100.0) + 10.0
            samples = [
                {"boot_id": boot_state_["boot_id"], "monotonic": base + 0.1,
                 "ipc_result": "success", "ipc_error": "", "ipc_elapsed_ms": 1,
                 "estimated_frame_number": 100, "time_pos": 10.0, "duration": 60.0,
                 "hwdec_current": EXPECTED_HWDEC, "vo_configured": True,
                 "idle_active": False, "pause": False, "eof_reached": False},
                {"boot_id": boot_state_["boot_id"], "monotonic": base + 0.7,
                 "ipc_result": "success", "ipc_error": "", "ipc_elapsed_ms": 1,
                 "estimated_frame_number": 120, "time_pos": 10.7, "duration": 60.0,
                 "hwdec_current": EXPECTED_HWDEC, "vo_configured": True,
                 "idle_active": False, "pause": False, "eof_reached": False},
                {"boot_id": boot_state_["boot_id"], "monotonic": base + 1.3,
                 "ipc_result": "success", "ipc_error": "", "ipc_elapsed_ms": 1,
                 "estimated_frame_number": 140, "time_pos": 11.4, "duration": 60.0,
                 "hwdec_current": EXPECTED_HWDEC, "vo_configured": True,
                 "idle_active": False, "pause": False, "eof_reached": False},
            ]
            _write_ndjson(attempt_dir / "decode-samples.ndjson", samples)
            (attempt_dir / "kernel-before.txt").write_text("boot clean\n", encoding="utf-8")
            (attempt_dir / "kernel-after.txt").write_text("boot clean\n", encoding="utf-8")
            (attempt_dir / "probe-kiosk-log-tail.txt").write_text("MPV process started pid=123\n", encoding="utf-8")
            signal_m = base + 1.5
            confirm = _decode_confirm(samples, signal_monotonic=signal_m)
            artifact = {
                "schema": MID_DECODE_SCHEMA,
                "passed": True,
                "claim": "mid_decode_sigterm_panfrost_window_measured",
                "kiosk_killed_before_signal": True,
                "cfg_hwdec": "auto",
                "wrapper": {"path": EXPECTED_WRAPPER, "sha256": "b" * 64},
                "production_service": {"stopped": True, "restored": True, "deep_health_passed": True},
                "attempts": [{
                    "index": 0,
                    "passed": True,
                    "failure_reasons": [],
                    "window_anchor": {"boot_id": boot_state_["boot_id"],
                                      "monotonic_before": base + 1.4,
                                      "monotonic_after": base + 4.0},
                    "pid_chain": {"pre_signal": {"pid": 123, "exe": EXPECTED_MPV_EXE,
                                                   "cmdline_contains_ipc_path": True,
                                                   "pgid_is_pid": True,
                                                   "starttime": 999}},
                    "decode_confirm": confirm,
                    "signal": {"name": "SIGTERM", "target": "mpv_pgid",
                               "delivered": True, "monotonic": signal_m},
                    "mpv_exit": {"exited": True, "waited_ms": 500, "escalated": False},
                    "kiosk_killed_before_signal": True,
                    "gpu_faults_before": 0,
                    "gpu_faults_after": 0,
                    "gpu_faults_delta": 0,
                    "gpu_faults_delta_anomalous": False,
                    "new_fault_lines_sanitized": [],
                }],
                "non_claims": [
                    "GR4b fresh-IPC quit SUCCESS against a live socket is NOT claimed.",
                    "healthy-not-wedged: this probe measures a healthy decoding mpv.",
                    "no-kiosk-alive: IPC quit, watchdog, waitpid, and auto-relaunch are NOT in this probe window.",
                    "production-timing-unmeasured: exact production timing is NOT claimed.",
                    "N=1 single-image",
                ],
            }
            write_json(run_root_ / "mid_decode_sigterm_probe.json", artifact)
            write_json(probe_dir / "service-restore.json",
                       {"active": True, "deep_health_passed": True,
                        "pre_start_barrier_passed": True, "reset_failed_used": False})
            write_json(probe_dir / "post-restore-health" / "playback-deep-health-public.json", _make_health())
            return artifact

        def fake_freeze_postcheck(updatectl: str, manifest_path: str) -> dict[str, int]:
            state["freeze_calls"] += 1
            return {"apply_local_rc": 44, "rollback_rc": 44, "reconcile_rc": 44}

        def fake_run(cmd: list[str], *, timeout: float = 30.0):
            # The finally-block service restart + any stray _run go through here.
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            args = argparse.Namespace(
                run_root=root, cycles=3, with_fresh_ipc_probe=True,
                with_mid_decode_sigterm_probe=True,
                mid_decode_probe_attempts=1,
                mid_decode_probe_canary_media=None,
                source_commit="b" * 40, board_image_marker="c18-selftest",
                updatectl="/fake/totem-updatectl", config=Path("/fake/config.json"),
                freeze_manifest="/fake/manifest.json", timer="kiosky-player-update.timer",
                health_duration_sec=0.1, health_interval_sec=0.1,
                settle_sec=0.0, startup_wait_sec=0.0,
            )
            mod = sys.modules[__name__]
            patches = {
                "_boot_state": fake_boot_state,
                "_capture_kernel_fault_lines": fake_capture_kernel_fault_lines,
                "_service_restart": fake_service_restart,
                "_run_relaunch_teardown": fake_relaunch,
                "_collect_deep_health": fake_collect_deep_health,
                "_run_fresh_ipc_probe": fake_fresh_ipc_probe,
                "_run_mid_decode_sigterm_probe": fake_mid_decode_probe,
                "_freeze_postcheck": fake_freeze_postcheck,
                "_service_active": lambda: True,
                "_timer_enabled": lambda timer: False,
                "_run": fake_run,
            }
            saved = {name: getattr(mod, name) for name in patches}
            saved_monotonic = time.monotonic
            os.environ[LAB_GUARD_ENV] = "1"
            try:
                for name, fn in patches.items():
                    setattr(mod, name, fn)
                time.monotonic = fake_monotonic  # type: ignore[assignment]
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    rc = run_trial(args)
            finally:
                for name, fn in saved.items():
                    setattr(mod, name, fn)
                time.monotonic = saved_monotonic  # type: ignore[assignment]
                os.environ.pop(LAB_GUARD_ENV, None)

            self.assertEqual(rc, 0, msg="run_trial returned non-zero")
            # The orchestration must have driven every real path via its seam.
            self.assertEqual(state["restarts"] >= 1, True)   # >=1 service_restart cycle
            self.assertEqual(state["relaunches"], 2)          # cycles 1,2 are relaunches
            self.assertEqual(state["health_calls"], 3)        # one deep-health per cycle
            self.assertEqual(state["freeze_calls"], 1)
            self.assertEqual(state["fresh_probe_calls"], 1)
            self.assertEqual(state["mid_probe_calls"], 1)

            # The strongest check: the produced run-dir passes the REAL gate.
            proc = subprocess.run(
                [sys.executable, str(GATE), "--run-dir", str(root), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

            # And the probe artifact records REAL staging (no hardcoded forcing).
            probe_written = json.loads((root / "fresh_ipc_probe.json").read_text(encoding="utf-8"))
            self.assertIs(probe_written["forced_ipc_none"], True)
            self.assertEqual(probe_written["forcing_method"], "short_mpv_startup_timeout_sec")
            summary_written = json.loads((root / "teardown-summary.json").read_text(encoding="utf-8"))
            self.assertIs(summary_written["mid_decode_probe_present"], True)

    def test_run_trial_lab_guard_blocks_without_env(self) -> None:
        os.environ.pop(LAB_GUARD_ENV, None)
        with self.assertRaises(SystemExit) as ctx:
            run_trial(argparse.Namespace(run_root=Path("/nonexistent"), cycles=2))
        self.assertEqual(ctx.exception.code, LAB_GUARD_EXIT)

    def test_journalctl_failure_fails_closed(self) -> None:
        # A non-zero journalctl exit must raise, never be read as a clean window
        # (else a faulting board whose capture failed would pass as 0 faults).
        mod = sys.modules[__name__]
        orig = mod._run
        try:
            mod._run = lambda cmd, *, timeout=30.0: subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr="journal degraded")
            with self.assertRaises(RuntimeError) as ctx:
                _capture_kernel_fault_lines()
            self.assertIn("journalctl_kernel_capture_failed", str(ctx.exception))
        finally:
            mod._run = orig

    def test_freeze_postcheck_apply_local_manifest_is_positional(self) -> None:
        # REGRESSION (HW-exposed): the public `apply-local` CLI takes the manifest
        # as a POSITIONAL arg (`apply-local [--component X] [--payload P] manifest`).
        # Passing `--manifest <p>` made argparse fail with "unrecognized arguments"
        # -> rc=2 -> postcheck APPLY_LOCAL_RC != 44 -> gate FAIL. The prior self-test
        # shimmed the whole freeze seam, masking the command FORM; this asserts the
        # exact argv so the mistake can never slip through off-board again.
        mod = sys.modules[__name__]
        orig = mod._run
        captured: list[list[str]] = []

        def fake_run(cmd, *, timeout=30.0):
            captured.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 44, stdout="", stderr="")

        try:
            mod._run = fake_run
            _freeze_postcheck("/opt/totem/bin/totem-updatectl", "/tmp/x.manifest.json")
        finally:
            mod._run = orig
        apply_cmds = [c for c in captured if "apply-local" in c]
        self.assertEqual(len(apply_cmds), 1, "apply-local must be invoked exactly once")
        cmd = apply_cmds[0]
        self.assertNotIn("--manifest", cmd, "manifest must be POSITIONAL, not --manifest")
        self.assertEqual(cmd[-1], "/tmp/x.manifest.json", "manifest must be the trailing positional arg")
        self.assertIn("--component", cmd)
        self.assertIn("player-runtime", cmd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="C18 player-runtime HW teardown/panfrost trial (producer).")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--run-root", type=Path, default=Path("/root/totem-diag"))
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--with-fresh-ipc-probe", action="store_true")
    parser.add_argument("--fresh-ipc-probe-startup-timeout-sec", type=float, default=0.01,
                        help="staged mpv_startup_timeout_sec used by the probe to force the "
                             "start_ipc_timeout corner on an ISOLATED kiosk instance "
                             "(HW-calibrated: healthy mpv exposes the socket in ~0.03s)")
    parser.add_argument("--fresh-ipc-probe-attempts", type=int, default=3)
    parser.add_argument("--fresh-ipc-probe-canary-media", type=Path, default=None,
                        help="REQUIRED with --with-fresh-ipc-probe: a real video under /tmp or "
                             "/data/media staged as the probe's offline playlist (the kiosk "
                             "exits no_content before mpv.start() without content)")
    parser.add_argument("--with-mid-decode-sigterm-probe", action="store_true",
                        help="run the Track A lab-only mid-decode SIGTERM probe after the "
                             "teardown cycles; requires a canary media file")
    parser.add_argument("--mid-decode-probe-attempts", type=int, default=1,
                        help="number of mid-decode SIGTERM attempts; operator-recommended N=2")
    parser.add_argument("--mid-decode-probe-canary-media", type=Path, default=None,
                        help="REQUIRED with --with-mid-decode-sigterm-probe: a real video "
                             "under /tmp or /data/media")
    parser.add_argument("--source-commit", default=None)
    parser.add_argument("--board-image-marker", default=None)
    parser.add_argument("--updatectl", default=DEFAULT_UPDATECTL)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--freeze-manifest", default=None,
                        help="path passed to the public apply-local freeze re-attestation (expected rc 44)")
    parser.add_argument("--timer", default="kiosky-player-update.timer")
    parser.add_argument("--health-duration-sec", type=float, default=30.0)
    parser.add_argument("--health-interval-sec", type=float, default=1.0)
    parser.add_argument("--settle-sec", type=float, default=3.0)
    parser.add_argument("--startup-wait-sec", type=float, default=5.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TeardownTrialSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    return run_trial(args)


if __name__ == "__main__":
    sys.exit(main())
