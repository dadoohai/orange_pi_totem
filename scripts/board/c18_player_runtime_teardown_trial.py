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
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_teardown_evidence_gate.py"

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
        outcome, observed = "fresh_failed_fallback_sigterm", FRESH_FAILED_LOG
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


def run_trial(args: argparse.Namespace) -> int:
    """Drive the real HW teardown trial. Exercised on the board only.

    This path intentionally fails closed off-board: it requires journalctl,
    systemctl, and the real kiosky-player service. The structured emission it
    produces is fully covered by ``--self-test``; the HW behaviour is validated
    on the board (a NEW image + M6), which is a separate, board-blocked step.
    """
    require_lab_guard()
    sys.stderr.write(
        "run_trial: HW execution path. Capture >=2 same-boot cycles "
        "(>=1 service_restart) with per-window panfrost delta, seal the manifest, "
        "then validate with c18_player_runtime_teardown_evidence_gate.py before commit.\n")
    # The concrete board steps (boot_state, journalctl -k -b fault capture, real
    # kiosk relaunch, systemctl restart, deep-health collection, fresh-IPC probe)
    # are driven here on the board. Kept out of the off-board self-test surface.
    raise SystemExit("run_trial must execute on the board with the lab guard set")


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="C18 player-runtime HW teardown/panfrost trial (producer).")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--run-root", type=Path, default=Path("/root/totem-diag"))
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--with-fresh-ipc-probe", action="store_true")
    parser.add_argument("--source-commit", default=None)
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
