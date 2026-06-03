#!/usr/bin/env python3
"""Build a sanitized C18 playback deep-health summary from observer artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.playback.deep_health.v1"
EXPECTED_HWDEC = "v4l2request-copy"
EXPECTED_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
EXPECTED_MPV_BINARY = "/opt/totem/hwdecode/bin/mpv"
EXPECTED_MPV_PATHS = {EXPECTED_WRAPPER, EXPECTED_MPV_BINARY}


def read_json(path: Path | None, label: str) -> dict[str, Any]:
    if path is None:
        raise ValueError(f"missing required {label} sidecar")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{label} sidecar must be a JSON object")
    return data


def as_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(value)
    except Exception:
        return 0


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def as_bool_string(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value or "").strip().lower()


def load_samples(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def status_has_failure(row: dict[str, str]) -> bool:
    state = str(row.get("status_playback_state") or "").lower()
    if "error" in state or "failed" in state:
        return True

    raw = row.get("status_snapshot_json") or ""
    if not raw:
        return False
    try:
        data = json.loads(raw)
    except Exception:
        return True
    if not isinstance(data, dict):
        return True
    if as_int(data.get("consecutive_failures")) > 0:
        return True
    if as_int(data.get("blocked_media_count")) > 0:
        return True
    for key in ("last_poll_error", "last_render_error", "black_screen_risk_reason"):
        if data.get(key) not in (None, "", "null", False):
            return True
    return False


def max_playlist_size(rows: list[dict[str, str]]) -> int:
    maximum = 0
    for row in rows:
        raw = row.get("status_snapshot_json") or ""
        if raw:
            try:
                data = json.loads(raw)
            except Exception:
                data = {}
            if isinstance(data, dict):
                maximum = max(maximum, as_int(data.get("playlist_size")))
        maximum = max(maximum, as_int(row.get("status_playlist_size")))
    return maximum


def progressed(values: list[float | None]) -> bool:
    clean = [value for value in values if value is not None]
    if len(clean) < 2:
        return False
    return max(clean) > min(clean)


def evaluate(
    *,
    samples_path: Path,
    systemd_path: Path | None,
    process_path: Path | None,
    kernel_path: Path | None,
    player_counters_path: Path | None,
) -> dict[str, Any]:
    rows = load_samples(samples_path)
    systemd = read_json(systemd_path, "systemd")
    process = read_json(process_path, "process")
    kernel = read_json(kernel_path, "kernel")
    player_counters = read_json(player_counters_path, "player counters")

    success_rows = [row for row in rows if row.get("ipc_result") == "success"]
    seen_success = False
    ipc_timeout_after_success = 0
    ipc_error_after_success = 0
    for row in rows:
        result = row.get("ipc_result")
        if result == "success":
            seen_success = True
        elif seen_success and result == "timeout":
            ipc_timeout_after_success += 1
        elif seen_success and result == "error":
            ipc_error_after_success += 1

    hwdec_expected_samples = 0
    hwdec_unexpected_samples = 0
    vo_configured_true_samples = 0
    vo_configured_unexpected_samples = 0
    aliases = set()
    time_values: list[float | None] = []
    frame_values: list[float | None] = []
    status_failure_samples = 0

    for row in rows:
        alias = row.get("current_alias") or row.get("status_current_alias") or row.get("status_path_alias")
        if alias:
            aliases.add(alias)

        if row.get("ipc_result") == "success":
            hwdec = row.get("hwdec_current") or ""
            if hwdec == EXPECTED_HWDEC:
                hwdec_expected_samples += 1
            elif hwdec:
                hwdec_unexpected_samples += 1

            vo_configured = as_bool_string(row.get("vo_configured"))
            if vo_configured == "true":
                vo_configured_true_samples += 1
            elif vo_configured:
                vo_configured_unexpected_samples += 1

            time_values.append(as_float(row.get("time_pos")))
            frame_values.append(as_float(row.get("estimated_frame_number")))

        if status_has_failure(row):
            status_failure_samples += 1

    service_active = bool(systemd.get("service_active"))
    target_mode = str(systemd.get("target_mode") or "service")
    nrestarts_delta = as_int(systemd.get("nrestarts_delta"))
    mpv_count = as_int(process.get("mpv_count"))
    total_mpv_count_present = "total_mpv_count" in process
    total_mpv_count = as_int(process.get("total_mpv_count"))
    process_filter = str(process.get("process_filter") or "")
    mpv_path = str(process.get("mpv_path") or "")
    mpv_path_ok = mpv_path in EXPECTED_MPV_PATHS
    panfrost_faults = as_int(kernel.get("panfrost_faults"))
    mmc_timeout_reset = as_int(kernel.get("mmc_timeout_reset"))
    ext4_errors_present = "ext4_errors" in kernel
    ext4_errors = as_int(kernel.get("ext4_errors"))
    media_load_failed = as_int(player_counters.get("media_load_failed"))
    mpv_restart = as_int(player_counters.get("mpv_restart"))
    playlist_size = max_playlist_size(rows)
    transition_required = playlist_size >= 2
    unique_aliases = len(aliases)
    transition_ok = not transition_required or unique_aliases >= 2
    time_pos_progressed = progressed(time_values)
    frame_progressed = progressed(frame_values)

    checks = {
        "samples_present": len(rows) > 0,
        "ipc_success_present": len(success_rows) > 0,
        "ipc_stable_after_success": ipc_timeout_after_success == 0 and ipc_error_after_success == 0,
        "hwdec_expected_present": hwdec_expected_samples > 0,
        "hwdec_no_unexpected": hwdec_unexpected_samples == 0,
        "vo_configured_present": vo_configured_true_samples > 0,
        "vo_configured_no_unexpected": vo_configured_unexpected_samples == 0,
        "playback_progressed": time_pos_progressed or frame_progressed,
        "status_no_failures": status_failure_samples == 0,
        "transitions_observed_when_required": transition_ok,
        "service_active": service_active,
        "nrestarts_stable": nrestarts_delta == 0,
        "single_mpv": mpv_count == 1,
        "service_process_unfiltered": target_mode != "service" or not process_filter,
        "service_total_mpv_count_present": target_mode != "service" or total_mpv_count_present,
        "service_single_total_mpv": target_mode != "service" or total_mpv_count == 1,
        "candidate_process_filtered": target_mode != "candidate" or process_filter == "input-ipc-server",
        "mpv_path_c18_stack": mpv_path_ok,
        "media_load_failed_zero": media_load_failed == 0,
        "mpv_restart_zero": mpv_restart == 0,
        "panfrost_faults_zero": panfrost_faults == 0,
        "mmc_timeout_reset_zero": mmc_timeout_reset == 0,
        "ext4_errors_present": ext4_errors_present,
        "ext4_errors_zero": ext4_errors == 0,
    }
    failure_reasons = [key for key, passed in checks.items() if not passed]

    return {
        "schema": SCHEMA,
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
        "expected": {
            "hwdec_current": EXPECTED_HWDEC,
            "mpv_paths": sorted(EXPECTED_MPV_PATHS),
        },
        "checks": checks,
        "counters": {
            "samples": len(rows),
            "ipc_success": len(success_rows),
            "ipc_timeout_after_first_success": ipc_timeout_after_success,
            "ipc_error_after_first_success": ipc_error_after_success,
            "unique_aliases": unique_aliases,
            "playlist_size_max": playlist_size,
            "hwdec_expected_samples": hwdec_expected_samples,
            "hwdec_unexpected_samples": hwdec_unexpected_samples,
            "vo_configured_true_samples": vo_configured_true_samples,
            "vo_configured_unexpected_samples": vo_configured_unexpected_samples,
            "time_pos_progressed": time_pos_progressed,
            "estimated_frame_progressed": frame_progressed,
            "status_failure_samples": status_failure_samples,
            "nrestarts_delta": nrestarts_delta,
            "mpv_count": mpv_count,
            "total_mpv_count": total_mpv_count,
            "media_load_failed": media_load_failed,
            "mpv_restart": mpv_restart,
            "panfrost_faults": panfrost_faults,
            "mmc_timeout_reset": mmc_timeout_reset,
            "ext4_errors": ext4_errors,
        },
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--systemd", required=True, type=Path)
    parser.add_argument("--process", required=True, type=Path)
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--player-counters", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = evaluate(
        samples_path=args.samples,
        systemd_path=args.systemd,
        process_path=args.process,
        kernel_path=args.kernel,
        player_counters_path=args.player_counters,
    )
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
