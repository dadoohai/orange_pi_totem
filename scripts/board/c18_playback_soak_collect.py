#!/usr/bin/env python3
"""Run read-only C18 playback deep-health cycles for soak evidence.

This wrapper repeatedly invokes c18_playback_health_collect.py against the
running kiosky-player service and aggregates the sanitized public results. It
does not stop, start, restart, thaw, publish, or modify player-runtime state.
Long duration is a product decision; this script only makes the evidence path
repeatable.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import c18_playback_health_collect as collect_health
import c18_playback_health_summary as health


SCHEMA = "dadooh.c18.playback.soak.v1"
DEFAULT_CYCLES = 3
DEFAULT_CYCLE_DURATION_SEC = 300.0
DEFAULT_SETTLE_SEC = 5.0
DEFAULT_MIN_SAMPLE_COVERAGE_RATIO = 0.80
DEFAULT_MIN_IPC_SUCCESS_RATIO = 0.95
DEFAULT_MIN_HWDEC_EXPECTED_RATIO = 0.95


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def default_output_dir() -> Path:
    ts = time.strftime("%Y%m%d-%H%M%SZ", time.gmtime())
    return Path("/tmp") / f"c18-playback-soak-{ts}"


def as_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def as_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def planned_samples(args: argparse.Namespace) -> int:
    interval = max(float(args.interval_sec), 0.001)
    return max(1, int(math.ceil(float(args.cycle_duration_sec) / interval)))


def cycle_brief(index: int, cycle_dir: Path, result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    counters = result.get("counters") if isinstance(result.get("counters"), dict) else {}
    samples = as_int(counters.get("samples"))
    ipc_success = as_int(counters.get("ipc_success"))
    hwdec_expected_samples = as_int(counters.get("hwdec_expected_samples"))
    expected_samples = planned_samples(args)
    min_samples = int(math.ceil(expected_samples * float(args.min_sample_coverage_ratio)))
    ipc_success_ratio = ratio(ipc_success, samples)
    hwdec_expected_ratio = ratio(hwdec_expected_samples, ipc_success)
    return {
        "cycle": index,
        "dir": cycle_dir.name,
        "passed": result.get("passed") is True,
        "failure_reasons": result.get("failure_reasons") if isinstance(result.get("failure_reasons"), list) else [],
        "samples": samples,
        "ipc_success": ipc_success,
        "hwdec_expected_samples": hwdec_expected_samples,
        "hwdec_unexpected_samples": as_int(counters.get("hwdec_unexpected_samples")),
        "estimated_frame_progressed": counters.get("estimated_frame_progressed") is True,
        "nrestarts_delta": as_int(counters.get("nrestarts_delta")),
        "media_load_failed": as_int(counters.get("media_load_failed")),
        "mpv_restart": as_int(counters.get("mpv_restart")),
        "panfrost_faults": as_int(counters.get("panfrost_faults")),
        "panfrost_faults_delta": as_int(counters.get("panfrost_faults_delta")),
        "mmc_timeout_reset_delta": as_int(counters.get("mmc_timeout_reset_delta")),
        "ext4_errors_delta": as_int(counters.get("ext4_errors_delta")),
        "planned_samples": expected_samples,
        "min_samples": min_samples,
        "sample_coverage_ratio": ratio(samples, expected_samples),
        "ipc_success_ratio": ipc_success_ratio,
        "hwdec_expected_ratio": hwdec_expected_ratio,
    }


def summarize(cycles: list[dict[str, Any]], *, output_dir: Path, started_at: str, ended_at: str, args: argparse.Namespace) -> dict[str, Any]:
    failed = [cycle for cycle in cycles if cycle.get("passed") is not True]
    failure_reasons: list[str] = []
    if failed:
        failure_reasons.append("cycle_failed")
    for cycle in cycles:
        if as_int(cycle.get("samples")) < as_int(cycle.get("min_samples")):
            failure_reasons.append("sample_coverage_below_min")
        if as_float(cycle.get("ipc_success_ratio")) < float(args.min_ipc_success_ratio):
            failure_reasons.append("ipc_success_ratio_below_min")
        if as_float(cycle.get("hwdec_expected_ratio")) < float(args.min_hwdec_expected_ratio):
            failure_reasons.append("hwdec_expected_ratio_below_min")
        for key in ("nrestarts_delta", "media_load_failed", "mpv_restart", "panfrost_faults_delta", "mmc_timeout_reset_delta", "ext4_errors_delta"):
            if as_int(cycle.get(key)) > 0:
                failure_reasons.append(f"{key}_nonzero")
    failure_reasons = sorted(set(failure_reasons))
    return {
        "schema": SCHEMA,
        "passed": not failure_reasons,
        "result_claim": "read_only_playback_collection_policy_passed",
        "evidence_scope": args.evidence_scope,
        "failure_reasons": failure_reasons,
        "started_at_utc": started_at,
        "ended_at_utc": ended_at,
        "output_dir": str(output_dir),
        "cycles": cycles,
        "collection_policy": {
            "cycles": args.cycles,
            "cycle_duration_sec": args.cycle_duration_sec,
            "settle_sec": args.settle_sec,
            "interval_sec": args.interval_sec,
            "planned_samples_per_cycle": planned_samples(args),
            "min_sample_coverage_ratio": args.min_sample_coverage_ratio,
            "min_ipc_success_ratio": args.min_ipc_success_ratio,
            "min_hwdec_expected_ratio": args.min_hwdec_expected_ratio,
            "panfrost_fault_policy": args.panfrost_fault_policy,
        },
        "counters": {
            "cycle_count": len(cycles),
            "passed_cycles": len([cycle for cycle in cycles if cycle.get("passed") is True]),
            "failed_cycles": len(failed),
            "samples": sum(as_int(cycle.get("samples")) for cycle in cycles),
            "ipc_success": sum(as_int(cycle.get("ipc_success")) for cycle in cycles),
            "min_sample_coverage_ratio": min([as_float(cycle.get("sample_coverage_ratio")) for cycle in cycles] or [0.0]),
            "min_ipc_success_ratio": min([as_float(cycle.get("ipc_success_ratio")) for cycle in cycles] or [0.0]),
            "min_hwdec_expected_ratio": min([as_float(cycle.get("hwdec_expected_ratio")) for cycle in cycles] or [0.0]),
            "max_nrestarts_delta": max([as_int(cycle.get("nrestarts_delta")) for cycle in cycles] or [0]),
            "max_media_load_failed": max([as_int(cycle.get("media_load_failed")) for cycle in cycles] or [0]),
            "max_mpv_restart": max([as_int(cycle.get("mpv_restart")) for cycle in cycles] or [0]),
            "max_panfrost_faults_delta": max([as_int(cycle.get("panfrost_faults_delta")) for cycle in cycles] or [0]),
            "max_mmc_timeout_reset_delta": max([as_int(cycle.get("mmc_timeout_reset_delta")) for cycle in cycles] or [0]),
            "max_ext4_errors_delta": max([as_int(cycle.get("ext4_errors_delta")) for cycle in cycles] or [0]),
        },
        "non_claims": [
            "endurance_certification_without_external_duration_policy",
            "physical_power_loss",
            "public_player_runtime_thaw",
            "stable_or_production",
        ],
    }


def collect_cycle(args: argparse.Namespace, output_dir: Path, index: int) -> dict[str, Any]:
    cycle_dir = output_dir / f"cycle-{index:03d}"
    cycle_args = SimpleNamespace(
        duration_sec=args.cycle_duration_sec,
        interval_sec=args.interval_sec,
        ipc_timeout_sec=args.ipc_timeout_sec,
        output_dir=cycle_dir,
        target_mode="service",
        candidate_pid=None,
        service=args.service,
        app_user=args.app_user,
        config=args.config,
        status=args.status,
        match_process_ipc=args.match_process_ipc,
        process_ipc_path=args.process_ipc_path,
        mpv_log=args.mpv_log,
        mpv_generation_dir=args.mpv_generation_dir,
        panfrost_fault_policy=args.panfrost_fault_policy,
    )
    _, result = collect_health.collect(cycle_args)
    return cycle_brief(index, cycle_dir, result, args)


def run_soak(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = args.output_dir or default_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(output_dir, 0o700)
    except OSError:
        pass

    started_at = timestamp()
    cycles: list[dict[str, Any]] = []
    for index in range(1, args.cycles + 1):
        cycles.append(collect_cycle(args, output_dir, index))
        if index < args.cycles and args.settle_sec > 0:
            time.sleep(args.settle_sec)
    ended_at = timestamp()
    summary = summarize(cycles, output_dir=output_dir, started_at=started_at, ended_at=ended_at, args=args)
    write_json(output_dir / "soak-summary.json", summary)
    return summary


def self_test() -> None:
    cycles = [
        {
            "cycle": 1,
            "passed": True,
            "samples": 3,
            "ipc_success": 3,
            "nrestarts_delta": 0,
            "media_load_failed": 0,
            "mpv_restart": 0,
            "panfrost_faults_delta": 0,
            "mmc_timeout_reset_delta": 0,
            "ext4_errors_delta": 0,
        },
        {
            "cycle": 2,
            "passed": True,
            "samples": 3,
            "ipc_success": 3,
            "nrestarts_delta": 0,
            "media_load_failed": 0,
            "mpv_restart": 0,
            "panfrost_faults_delta": 0,
            "mmc_timeout_reset_delta": 0,
            "ext4_errors_delta": 0,
        },
    ]
    args = SimpleNamespace(
        cycles=2,
        cycle_duration_sec=3.0,
        settle_sec=0.0,
        interval_sec=1.0,
        min_sample_coverage_ratio=0.80,
        min_ipc_success_ratio=0.95,
        min_hwdec_expected_ratio=0.95,
        evidence_scope="smoke",
        panfrost_fault_policy="absolute",
    )
    for cycle in cycles:
        cycle["planned_samples"] = 3
        cycle["min_samples"] = 3
        cycle["sample_coverage_ratio"] = 1.0
        cycle["ipc_success_ratio"] = 1.0
        cycle["hwdec_expected_ratio"] = 1.0
        cycle["hwdec_expected_samples"] = 3
    ok = summarize(cycles, output_dir=Path("/tmp/self-test"), started_at="a", ended_at="b", args=args)
    if ok["passed"] is not True:
        raise AssertionError("expected passing soak summary")
    bad_cycles = [dict(cycles[0]), dict(cycles[1], panfrost_faults_delta=1)]
    bad = summarize(bad_cycles, output_dir=Path("/tmp/self-test"), started_at="a", ended_at="b", args=args)
    if bad["passed"] is not False or "panfrost_faults_delta_nonzero" not in bad["failure_reasons"]:
        raise AssertionError("expected panfrost delta failure")
    sparse_cycles = [dict(cycles[0], samples=60, ipc_success=60, hwdec_expected_samples=3, hwdec_expected_ratio=0.05)]
    sparse = summarize(sparse_cycles, output_dir=Path("/tmp/self-test"), started_at="a", ended_at="b", args=args)
    if sparse["passed"] is not False or "hwdec_expected_ratio_below_min" not in sparse["failure_reasons"]:
        raise AssertionError("expected sparse hwdec coverage failure")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=DEFAULT_CYCLES)
    parser.add_argument("--cycle-duration-sec", type=float, default=DEFAULT_CYCLE_DURATION_SEC)
    parser.add_argument("--settle-sec", type=float, default=DEFAULT_SETTLE_SEC)
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--ipc-timeout-sec", type=float, default=0.8)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--service", default=collect_health.DEFAULT_SERVICE)
    parser.add_argument("--app-user", default=collect_health.DEFAULT_APP_USER)
    parser.add_argument("--config", type=Path, default=collect_health.DEFAULT_CONFIG)
    parser.add_argument("--status", type=Path, default=collect_health.DEFAULT_STATUS)
    parser.add_argument("--match-process-ipc", action="store_true")
    parser.add_argument("--process-ipc-path", type=Path, default=None)
    parser.add_argument("--mpv-log", type=Path, default=collect_health.DEFAULT_MPV_LOG)
    parser.add_argument("--mpv-generation-dir", type=Path, default=collect_health.DEFAULT_MPV_GENERATION_DIR)
    parser.add_argument("--panfrost-fault-policy", choices=sorted(health.PANFROST_FAULT_POLICIES), default="absolute")
    parser.add_argument("--evidence-scope", choices=("smoke", "endurance-candidate"), default="smoke")
    parser.add_argument("--min-sample-coverage-ratio", type=float, default=DEFAULT_MIN_SAMPLE_COVERAGE_RATIO)
    parser.add_argument("--min-ipc-success-ratio", type=float, default=DEFAULT_MIN_IPC_SUCCESS_RATIO)
    parser.add_argument("--min-hwdec-expected-ratio", type=float, default=DEFAULT_MIN_HWDEC_EXPECTED_RATIO)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        print(json.dumps({"self_test": True, "schema": SCHEMA}, sort_keys=True))
        return 0
    if args.cycles < 1:
        print("cycles must be >= 1", file=sys.stderr)
        return 2
    try:
        summary = run_soak(args)
    except Exception as exc:
        payload = {
            "schema": SCHEMA,
            "passed": False,
            "failure_reasons": ["soak_collector_failed"],
            "collector_error": type(exc).__name__,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"soak_collector_failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"output_dir={summary['output_dir']}")
        print(f"soak_passed={str(bool(summary.get('passed'))).lower()}")
    return 0 if summary.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
