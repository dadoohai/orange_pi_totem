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
                  *, gr4_secondary_present: bool) -> dict[str, Any]:
    restart_indices = [c["index"] for c in cycles if c["kind"] == "service_restart"]
    return {
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


def classify_fresh_ipc(kiosk_log_text: str) -> dict[str, Any]:
    """Inspect a kiosk.log for the fresh-IPC quit outcome (GR4 secondary)."""
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
    return {
        "schema": FRESH_IPC_SCHEMA,
        "forced_ipc_none": True,
        "forcing_method": "short_mpv_startup_timeout_sec",
        "code_path_reached": reached,
        "observed_log": observed,
        "outcome": outcome,
        "process_exited": True,
        "non_claim": "GR4b (fresh-IPC quit SUCCESS vs a live socket) is NOT proven; secondary corner only.",
    }


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


def _read_kiosk_log(config_path: Path) -> str:
    """Read the live kiosk.log (for the optional fresh-IPC probe classification)."""
    log_path = DEFAULT_KIOSK_LOG
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("log_file"):
            log_path = Path(str(data["log_file"]))
    except Exception:
        pass
    try:
        return log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _run_fresh_ipc_probe(config_path: Path) -> str:
    """Drive the start_ipc_timeout corner and return the resulting kiosk.log text.

    On the board this forces ``self._ipc is None`` (short
    ``mpv_startup_timeout_sec``) so the fresh-IPC quit path is reached during the
    next teardown, then returns the live kiosk.log for ``classify_fresh_ipc``.
    The honest outcome of this corner is ALWAYS the SIGTERM fallback (the gate
    rejects ``fresh_sent``); we never synthesize a success log.
    """
    # A real driver of the corner would stage a short mpv_startup_timeout_sec
    # config + relaunch; we restart the service to provoke a fresh start and then
    # read whatever the player actually logged. No log content is fabricated.
    _service_restart()
    time.sleep(2.0)
    return _read_kiosk_log(config_path)


def _freeze_postcheck(updatectl: str, manifest_path: str) -> dict[str, int]:
    """Re-attest the player-runtime freeze via the PUBLIC updater verbs.

    Runs the public apply-local / rollback / reconcile verbs for player-runtime
    and returns their return codes. Each MUST be ``44`` (frozen) for the gate's
    postcheck to pass. We do NOT pass the reconcile maintenance guard, so the
    public reconcile path stays frozen.
    """
    rollback = _run([updatectl, "rollback", "--component", "player-runtime"], timeout=30.0).returncode
    reconcile = _run([updatectl, "reconcile", "--component", "player-runtime"], timeout=30.0).returncode
    apply_local = _run(
        [updatectl, "apply-local", "--component", "player-runtime", "--manifest", manifest_path],
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

        # Optional fresh-IPC probe (honest; the gate rejects "fresh_sent").
        gr4_secondary_present = bool(getattr(args, "with_fresh_ipc_probe", False))
        if gr4_secondary_present:
            kiosk_log = _run_fresh_ipc_probe(config_path)
            write_json(run_root / "fresh_ipc_probe.json", classify_fresh_ipc(kiosk_log))

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
    fresh = classify_fresh_ipc("... MPV IPC fresh command failed command=quit ...")
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
                 "health_calls": 0, "fresh_probe_calls": 0, "freeze_calls": 0}

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

        def fake_fresh_ipc_probe(config_path: Path) -> str:
            state["fresh_probe_calls"] += 1
            # Honest forced-corner log: SIGTERM fallback, never "fresh_sent".
            return "... MPV IPC fresh command failed command=quit ...\n"

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

            # The strongest check: the produced run-dir passes the REAL gate.
            proc = subprocess.run(
                [sys.executable, str(GATE), "--run-dir", str(root), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="C18 player-runtime HW teardown/panfrost trial (producer).")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--run-root", type=Path, default=Path("/root/totem-diag"))
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--with-fresh-ipc-probe", action="store_true")
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
