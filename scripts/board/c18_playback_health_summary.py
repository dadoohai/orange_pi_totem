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
MIN_FRAME_PROGRESS_DELTAS = 2
MAX_TRAILING_NONPROGRESS_DELTAS = 1
PANFROST_FAULT_POLICIES = {"absolute", "delta"}


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


def status_has_failure(row: dict[str, str], target_mode: str) -> bool:
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
        value = data.get(key)
        if (
            target_mode == "candidate"
            and key == "last_poll_error"
            and isinstance(value, str)
            and "polling_disabled" in value
        ):
            continue
        if value not in (None, "", "null", False):
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


def sustained_progress_stats(values: list[float | None]) -> dict[str, int | bool]:
    clean = [value for value in values if value is not None]
    pair_count = max(len(clean) - 1, 0)
    deltas = [current - previous for previous, current in zip(clean, clean[1:])]
    positive_steps = sum(1 for delta in deltas if delta > 0)
    trailing_nonprogress_steps = 0
    for delta in reversed(deltas):
        if delta > 0:
            break
        trailing_nonprogress_steps += 1
    return {
        "sample_count": len(clean),
        "pair_count": pair_count,
        "positive_steps": positive_steps,
        "required_steps": MIN_FRAME_PROGRESS_DELTAS,
        "trailing_nonprogress_steps": trailing_nonprogress_steps,
        "passed": (
            len(clean) >= 3
            and positive_steps >= MIN_FRAME_PROGRESS_DELTAS
            and trailing_nonprogress_steps <= MAX_TRAILING_NONPROGRESS_DELTAS
        ),
    }


def sustained_progressed(values: list[float | None]) -> bool:
    return bool(sustained_progress_stats(values)["passed"])


def playback_item_key(row: dict[str, str]) -> str:
    status_alias = row.get("status_current_alias") or row.get("status_path_alias")
    status_index = row.get("status_current_index") or ""
    if status_alias or status_index:
        return f"status:{status_alias or '__unknown__'}:{status_index}"
    return f"mpv:{row.get('current_alias') or '__unknown__'}"


def status_item_key(row: dict[str, str]) -> str:
    status_alias = row.get("status_current_alias") or row.get("status_path_alias")
    status_index = row.get("status_current_index") or ""
    if status_alias or status_index:
        return f"status:{status_alias or '__unknown__'}:{status_index}"
    return ""


def mpv_item_key(row: dict[str, str]) -> str:
    alias = row.get("current_alias") or row.get("path_alias") or row.get("filename_alias")
    return f"mpv:{alias}" if alias else ""


def frame_progress_segments(rows: list[dict[str, str]]) -> list[list[float | None]]:
    segments: list[list[float | None]] = []
    current_key: str | None = None
    current_segment: list[float | None] = []
    previous_frame: float | None = None

    for row in rows:
        key = playback_item_key(row)
        frame_value = as_float(row.get("estimated_frame_number"))
        reset = (
            frame_value is not None
            and previous_frame is not None
            and frame_value < previous_frame
        )
        if current_segment and (key != current_key or reset):
            segments.append(current_segment)
            current_segment = []
        current_key = key
        current_segment.append(frame_value)
        previous_frame = frame_value

    if current_segment:
        segments.append(current_segment)
    return segments


def present_count(values: list[float | None]) -> int:
    return len([value for value in values if value is not None])


def evaluate(
    *,
    samples_path: Path,
    systemd_path: Path | None,
    process_path: Path | None,
    kernel_path: Path | None,
    player_counters_path: Path | None,
    panfrost_fault_policy: str = "absolute",
) -> dict[str, Any]:
    if panfrost_fault_policy not in PANFROST_FAULT_POLICIES:
        raise ValueError(f"unsupported panfrost fault policy: {panfrost_fault_policy}")
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
    status_aliases = set()
    mpv_aliases = set()
    time_values: list[float | None] = []
    frame_values: list[float | None] = []
    status_failure_samples = 0
    target_mode = str(systemd.get("target_mode") or "service")

    for row in rows:
        aliases.add(playback_item_key(row))
        status_key = status_item_key(row)
        if status_key:
            status_aliases.add(status_key)
        mpv_key = mpv_item_key(row)
        if mpv_key:
            mpv_aliases.add(mpv_key)

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
            frame_value = as_float(row.get("estimated_frame_number"))
            frame_values.append(frame_value)

        if status_has_failure(row, target_mode):
            status_failure_samples += 1

    service_active = bool(systemd.get("service_active"))
    nrestarts_delta_present = "nrestarts_delta" in systemd
    nrestarts_delta = as_int(systemd.get("nrestarts_delta"))
    mpv_count = as_int(process.get("mpv_count"))
    total_mpv_count_present = "total_mpv_count" in process
    total_mpv_count = as_int(process.get("total_mpv_count"))
    process_filter = str(process.get("process_filter") or "")
    mpv_path = str(process.get("mpv_path") or "")
    mpv_path_ok = mpv_path in EXPECTED_MPV_PATHS
    panfrost_faults_present = "panfrost_faults" in kernel
    panfrost_faults = as_int(kernel.get("panfrost_faults"))
    panfrost_faults_start = as_int(kernel.get("panfrost_faults_start"))
    panfrost_faults_delta_present = "panfrost_faults_delta" in kernel
    panfrost_faults_delta = as_int(kernel.get("panfrost_faults_delta"))
    mmc_timeout_reset_present = "mmc_timeout_reset" in kernel
    mmc_timeout_reset = as_int(kernel.get("mmc_timeout_reset"))
    mmc_timeout_reset_start = as_int(kernel.get("mmc_timeout_reset_start"))
    mmc_timeout_reset_delta = as_int(kernel.get("mmc_timeout_reset_delta"))
    ext4_errors_present = "ext4_errors" in kernel
    ext4_errors = as_int(kernel.get("ext4_errors"))
    ext4_errors_start = as_int(kernel.get("ext4_errors_start"))
    ext4_errors_delta = as_int(kernel.get("ext4_errors_delta"))
    media_load_failed_present = "media_load_failed" in player_counters
    media_load_failed = as_int(player_counters.get("media_load_failed"))
    mpv_restart_present = "mpv_restart" in player_counters
    mpv_restart = as_int(player_counters.get("mpv_restart"))
    playlist_size = max_playlist_size(rows)
    transition_required = playlist_size >= 2
    unique_aliases = len(aliases)
    status_unique_aliases = len(status_aliases)
    mpv_unique_aliases = len(mpv_aliases)
    transition_ok = not transition_required or unique_aliases >= 2
    time_pos_progressed = progressed(time_values)
    estimated_frame_present = present_count(frame_values) >= 2
    frame_progress_stats = sustained_progress_stats(frame_values)
    frame_segments = frame_progress_segments(success_rows)
    if frame_segments:
        segment_stats = [sustained_progress_stats(values) for values in frame_segments]
        evaluable_segment_stats = [stats for stats in segment_stats if int(stats["sample_count"]) >= 3]
        short_segment_stats = [stats for stats in segment_stats if 0 < int(stats["sample_count"]) < 3]
        short_failed_segment_stats = [
            stats
            for stats in short_segment_stats
            if int(stats["pair_count"]) > 0 and int(stats["positive_steps"]) == 0
        ]
        if evaluable_segment_stats:
            failed_segment_stats = [
                stats for stats in evaluable_segment_stats if not bool(stats["passed"])
            ] + short_failed_segment_stats
            best_segment = failed_segment_stats[0] if failed_segment_stats else evaluable_segment_stats[-1]
            frame_progressed = not failed_segment_stats
        else:
            best_segment = segment_stats[-1]
            failed_segment_stats = short_failed_segment_stats or [best_segment]
            frame_progressed = False
    else:
        frame_progressed = bool(frame_progress_stats["passed"])
        best_segment = frame_progress_stats
        evaluable_segment_stats = []
        short_segment_stats = []
        short_failed_segment_stats = []
        failed_segment_stats = [] if frame_progressed else [frame_progress_stats]

    panfrost_faults_zero = panfrost_faults == 0
    panfrost_faults_delta_required = panfrost_fault_policy == "delta"
    panfrost_faults_delta_zero = (
        panfrost_faults_delta_present and panfrost_faults_delta == 0
        if panfrost_faults_delta_required
        else not panfrost_faults_delta_present or panfrost_faults_delta == 0
    )
    panfrost_faults_clean = panfrost_faults_zero if panfrost_fault_policy == "absolute" else panfrost_faults_delta_zero

    checks = {
        "samples_present": len(rows) > 0,
        "ipc_success_present": len(success_rows) > 0,
        "ipc_stable_after_success": ipc_timeout_after_success == 0 and ipc_error_after_success == 0,
        "hwdec_expected_present": hwdec_expected_samples > 0,
        "hwdec_no_unexpected": hwdec_unexpected_samples == 0,
        "vo_configured_present": vo_configured_true_samples > 0,
        "vo_configured_no_unexpected": vo_configured_unexpected_samples == 0,
        "estimated_frame_present": estimated_frame_present,
        "playback_progressed": frame_progressed,
        "status_no_failures": status_failure_samples == 0,
        "transitions_observed_when_required": transition_ok,
        "service_active": service_active,
        "nrestarts_delta_present": nrestarts_delta_present,
        "nrestarts_stable": nrestarts_delta == 0,
        "single_mpv": mpv_count == 1,
        "service_process_unfiltered": target_mode != "service" or not process_filter,
        "service_total_mpv_count_present": target_mode != "service" or total_mpv_count_present,
        "service_single_total_mpv": target_mode != "service" or total_mpv_count == 1,
        "candidate_process_filtered": target_mode != "candidate" or process_filter == "input-ipc-server",
        "mpv_path_c18_stack": mpv_path_ok,
        "media_load_failed_present": media_load_failed_present,
        "media_load_failed_zero": media_load_failed == 0,
        "mpv_restart_present": mpv_restart_present,
        "mpv_restart_zero": mpv_restart == 0,
        "panfrost_faults_present": panfrost_faults_present,
        "panfrost_faults_zero": panfrost_faults_zero,
        "panfrost_faults_delta_present": not panfrost_faults_delta_required or panfrost_faults_delta_present,
        "panfrost_faults_delta_zero": panfrost_faults_delta_zero,
        "panfrost_faults_clean_for_policy": panfrost_faults_clean,
        "mmc_timeout_reset_present": mmc_timeout_reset_present,
        "mmc_timeout_reset_zero": mmc_timeout_reset == 0,
        "ext4_errors_present": ext4_errors_present,
        "ext4_errors_zero": ext4_errors == 0,
    }
    if panfrost_fault_policy == "delta":
        checks["panfrost_faults_zero"] = True
    failure_reasons = [key for key, passed in checks.items() if not passed]

    return {
        "schema": SCHEMA,
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
        "expected": {
            "hwdec_current": EXPECTED_HWDEC,
            "mpv_paths": sorted(EXPECTED_MPV_PATHS),
            "panfrost_fault_policy": panfrost_fault_policy,
        },
        "checks": checks,
        "counters": {
            "samples": len(rows),
            "ipc_success": len(success_rows),
            "ipc_timeout_after_first_success": ipc_timeout_after_success,
            "ipc_error_after_first_success": ipc_error_after_success,
            "unique_aliases": unique_aliases,
            "status_unique_aliases": status_unique_aliases,
            "mpv_unique_aliases": mpv_unique_aliases,
            "status_transitions_observed": status_unique_aliases >= 2,
            "mpv_media_transitions_observed": mpv_unique_aliases >= 2,
            "playlist_size_max": playlist_size,
            "hwdec_expected_samples": hwdec_expected_samples,
            "hwdec_unexpected_samples": hwdec_unexpected_samples,
            "vo_configured_true_samples": vo_configured_true_samples,
            "vo_configured_unexpected_samples": vo_configured_unexpected_samples,
            "time_pos_progressed": time_pos_progressed,
            "estimated_frame_progressed": frame_progressed,
            "estimated_frame_positive_steps": best_segment["positive_steps"],
            "estimated_frame_required_steps": best_segment["required_steps"],
            "estimated_frame_trailing_nonprogress_steps": best_segment["trailing_nonprogress_steps"],
            "estimated_frame_evaluable_segments": len(evaluable_segment_stats),
            "estimated_frame_short_segments": len(short_segment_stats),
            "estimated_frame_failed_segments": len(failed_segment_stats),
            "status_failure_samples": status_failure_samples,
            "nrestarts_delta": nrestarts_delta,
            "mpv_count": mpv_count,
            "total_mpv_count": total_mpv_count,
            "media_load_failed": media_load_failed,
            "mpv_restart": mpv_restart,
            "panfrost_faults_start": panfrost_faults_start,
            "panfrost_faults": panfrost_faults,
            "panfrost_faults_delta": panfrost_faults_delta,
            "panfrost_fault_policy": panfrost_fault_policy,
            "mmc_timeout_reset_start": mmc_timeout_reset_start,
            "mmc_timeout_reset": mmc_timeout_reset,
            "mmc_timeout_reset_delta": mmc_timeout_reset_delta,
            "ext4_errors_start": ext4_errors_start,
            "ext4_errors": ext4_errors,
            "ext4_errors_delta": ext4_errors_delta,
        },
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--systemd", required=True, type=Path)
    parser.add_argument("--process", required=True, type=Path)
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--player-counters", required=True, type=Path)
    parser.add_argument("--panfrost-fault-policy", choices=sorted(PANFROST_FAULT_POLICIES), default="absolute")
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
        panfrost_fault_policy=args.panfrost_fault_policy,
    )
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
