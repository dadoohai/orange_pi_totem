#!/usr/bin/env python3
"""Build a sanitized C18 playback deep-health summary from observer artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import math
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
MAX_CONSECUTIVE_STATUS_MPV_MISMATCHES = 2
MAX_STATUS_MPV_MISMATCH_RATIO = 0.10
MAX_STATUS_MPV_TRANSITION_LAG_SAMPLES = 5
MAX_STATUS_MPV_TRANSITION_LAG_SECONDS = 6.0
MAX_STATUS_MPV_TRANSITION_LAG_RUNS = 3
MAX_STATUS_MPV_CHAINED_TRANSITION_LAG_SEGMENTS = 2
MAX_STATUS_MPV_FORWARD_STATUS_LAG_SEGMENTS = 3
MAX_STATUS_MPV_TERMINAL_LAG_SAMPLES = 1
MAX_TRANSIENT_MISSING_SOCKET_AFTER_SUCCESS = 2
MAX_CONSECUTIVE_TRANSIENT_MISSING_SOCKET_AFTER_SUCCESS = 2
TRANSIENT_MISSING_SOCKET_LONG_RUN_SAMPLE_WINDOW = 180
MAX_TRANSIENT_MISSING_SOCKET_LONG_RUN_CAP = 6
MAX_STARTUP_MISSING_SOCKET_SAMPLES = 6
MAX_STARTUP_MISSING_SOCKET_SECONDS = 6.0
MAX_STARTUP_UNCLASSIFIED_MEDIA_SAMPLES = 6
MAX_STARTUP_UNCLASSIFIED_MEDIA_SECONDS = 6.0
PANFROST_FAULT_POLICIES = {"absolute", "delta"}
WATCHDOG_RECOVERY_ACTIONS = {"realign_mpv_to_status", "terminate_player_child"}


def read_json(path: Path | None, label: str) -> dict[str, Any]:
    if path is None:
        raise ValueError(f"missing required {label} sidecar")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{label} sidecar must be a JSON object")
    return data


def read_optional_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


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
        parsed = float(value)
    except Exception:
        return None
    return parsed if math.isfinite(parsed) else None


def as_frame_number(value: Any) -> float | None:
    parsed = as_float(value)
    return parsed if parsed is not None and parsed >= 0 else None


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
    snapshot_state = str(data.get("playback_state") or state).lower()
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
        if (
            target_mode == "candidate"
            and key == "black_screen_risk_reason"
            and snapshot_state == "player_starting"
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


def mpv_item_alias(row: dict[str, str]) -> str:
    # current_alias may be filled from status fallback by older collectors.
    return row.get("path_alias") or row.get("filename_alias") or ""


def status_item_alias(row: dict[str, str]) -> str:
    return row.get("status_path_alias") or row.get("status_current_alias") or ""


def _status_snapshot_item_alias(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("path_alias") or item.get("alias") or "")


def status_next_item_alias(row: dict[str, str]) -> str:
    raw = row.get("status_snapshot_json") or ""
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    return _status_snapshot_item_alias(data.get("next_item"))


def _status_mpv_alias_pair_is_transition(status_alias: str, mpv_alias: str, old: str, new: str) -> bool:
    return (
        status_alias != mpv_alias
        and {status_alias, mpv_alias} == {old, new}
    )


def _status_mpv_lag_duration_seconds(events: list[dict[str, Any]]) -> float:
    values = [event["rel_sec"] for event in events if event["rel_sec"] is not None]
    if len(values) < 2:
        return 0.0
    return float(max(values) - min(values))


def _status_mpv_is_bounded_transition_lag(events: list[dict[str, Any]], start: int, end: int) -> bool:
    if start <= 0 or end >= len(events):
        return False
    before = events[start - 1]
    after = events[end]
    if not before["aligned"] or not after["aligned"]:
        return False
    old = before["status_alias"]
    new = after["status_alias"]
    if old != before["mpv_alias"] or new != after["mpv_alias"] or old == new:
        return False
    run = events[start:end]
    if len(run) > MAX_STATUS_MPV_TRANSITION_LAG_SAMPLES:
        return False
    if _status_mpv_lag_duration_seconds(run) > MAX_STATUS_MPV_TRANSITION_LAG_SECONDS:
        return False
    return all(
        _status_mpv_alias_pair_is_transition(event["status_alias"], event["mpv_alias"], old, new)
        for event in run
    )


def _status_mpv_is_terminal_transition_lag(events: list[dict[str, Any]], start: int, end: int) -> bool:
    if start <= 0 or end != len(events):
        return False
    before = events[start - 1]
    if not before["aligned"]:
        return False
    run = events[start:end]
    if len(run) > MAX_STATUS_MPV_TERMINAL_LAG_SAMPLES:
        return False
    old = before["status_alias"]
    if old != before["mpv_alias"]:
        return False
    return all(
        event["status_alias"] != event["mpv_alias"]
        and old in {event["status_alias"], event["mpv_alias"]}
        for event in run
    )


def _status_mpv_is_initial_transition_lag(events: list[dict[str, Any]], start: int, end: int) -> bool:
    if start != 0 or end >= len(events):
        return False
    after = events[end]
    if not after["aligned"]:
        return False
    run = events[start:end]
    if len(run) > MAX_STATUS_MPV_TRANSITION_LAG_SAMPLES:
        return False
    if _status_mpv_lag_duration_seconds(run) > MAX_STATUS_MPV_TRANSITION_LAG_SECONDS:
        return False
    new = after["status_alias"]
    if new != after["mpv_alias"]:
        return False
    return all(
        event["status_alias"] != event["mpv_alias"]
        and new in {event["status_alias"], event["mpv_alias"]}
        for event in run
    )


def _status_mpv_is_bounded_chained_transition_lag(events: list[dict[str, Any]], start: int, end: int) -> bool:
    if start <= 0 or end >= len(events):
        return False
    before = events[start - 1]
    after = events[end]
    if not before["aligned"] or not after["aligned"]:
        return False
    old = before["status_alias"]
    final = after["status_alias"]
    if old != before["mpv_alias"] or final != after["mpv_alias"] or old == final:
        return False

    segments: list[dict[str, Any]] = []
    index = start
    while index < end:
        pair = frozenset((events[index]["status_alias"], events[index]["mpv_alias"]))
        if len(pair) != 2:
            return False
        seg_start = index
        index += 1
        while index < end and frozenset((events[index]["status_alias"], events[index]["mpv_alias"])) == pair:
            index += 1
        segment_events = events[seg_start:index]
        if len(segment_events) > MAX_STATUS_MPV_TRANSITION_LAG_SAMPLES:
            return False
        if _status_mpv_lag_duration_seconds(segment_events) > MAX_STATUS_MPV_TRANSITION_LAG_SECONDS:
            return False
        segments.append({"pair": pair})

    if len(segments) < 2 or len(segments) > MAX_STATUS_MPV_CHAINED_TRANSITION_LAG_SEGMENTS:
        return False
    if old not in segments[0]["pair"] or final not in segments[-1]["pair"]:
        return False
    for left, right in zip(segments, segments[1:]):
        if len(left["pair"] & right["pair"]) != 1:
            return False
    return True


def _status_mpv_is_forward_status_lag(events: list[dict[str, Any]], start: int, end: int) -> bool:
    """Accept short runs where MPV has reached the status-declared next item.

    This covers fast media transitions where the MPV IPC sample is already on
    the next playlist entry while the public status snapshot still reports the
    previous current item. It deliberately does not cover the opposite failure
    mode, where status advances while MPV remains stuck on an older item.
    """

    if start <= 0:
        return False
    before = events[start - 1]
    if not before["aligned"]:
        return False
    if end < len(events):
        after = events[end]
        if not after["aligned"]:
            return False
        if after["status_alias"] == before["status_alias"]:
            return False

    segments: list[dict[str, Any]] = []
    index = start
    while index < end:
        status_alias = events[index]["status_alias"]
        mpv_alias = events[index]["mpv_alias"]
        status_next_alias = events[index].get("status_next_alias")
        if not mpv_alias:
            return False
        if status_alias == mpv_alias:
            return False
        seg_start = index
        index += 1
        while (
            index < end
            and events[index]["status_alias"] == status_alias
            and events[index]["mpv_alias"] == mpv_alias
        ):
            if events[index].get("status_next_alias") != status_next_alias:
                return False
            index += 1
        segment_events = events[seg_start:index]
        if len(segment_events) > MAX_STATUS_MPV_TRANSITION_LAG_SAMPLES:
            return False
        if _status_mpv_lag_duration_seconds(segment_events) > MAX_STATUS_MPV_TRANSITION_LAG_SECONDS:
            return False
        segments.append({
            "status_alias": status_alias,
            "mpv_alias": mpv_alias,
            "status_next_alias": status_next_alias,
            "samples": len(segment_events),
        })

    max_segments = MAX_STATUS_MPV_FORWARD_STATUS_LAG_SEGMENTS if end < len(events) else MAX_STATUS_MPV_CHAINED_TRANSITION_LAG_SEGMENTS
    if not segments or len(segments) > max_segments:
        return False
    if segments[0]["status_alias"] != before["status_alias"]:
        return False
    for offset, (left, right) in enumerate(zip(segments, segments[1:])):
        if left["mpv_alias"] == right["status_alias"]:
            continue
        final_bridge_to_alignment = (
            end < len(events)
            and offset == len(segments) - 2
            and right["samples"] <= MAX_STATUS_MPV_TERMINAL_LAG_SAMPLES
            and events[end]["aligned"]
            and events[end]["mpv_alias"] == right["mpv_alias"]
            and right["status_alias"] == left["status_alias"]
            and right["status_next_alias"] == left["mpv_alias"]
        )
        if not final_bridge_to_alignment:
            return False
    for offset, segment in enumerate(segments):
        if segment["status_next_alias"] == segment["mpv_alias"]:
            continue
        final_bridge_to_alignment = (
            end < len(events)
            and offset == len(segments) - 1
            and offset > 0
            and segment["samples"] <= MAX_STATUS_MPV_TERMINAL_LAG_SAMPLES
            and events[end]["aligned"]
            and events[end]["mpv_alias"] == segment["mpv_alias"]
            and segments[offset - 1]["mpv_alias"] == segment["status_next_alias"]
        )
        if not final_bridge_to_alignment:
            return False
    return True


def status_mpv_alignment_stats(rows: list[dict[str, str]]) -> dict[str, int | float]:
    comparable = 0
    mismatches = 0
    current_streak = 0
    max_streak = 0
    events: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        if row.get("ipc_result") != "success":
            current_streak = 0
            continue
        status_alias = status_item_alias(row)
        mpv_alias = mpv_item_alias(row)
        if not status_alias or not mpv_alias:
            current_streak = 0
            continue
        comparable += 1
        event = {
            "row_index": row_index,
            "status_alias": status_alias,
            "mpv_alias": mpv_alias,
            "status_next_alias": status_next_item_alias(row),
            "aligned": status_alias == mpv_alias,
            "rel_sec": as_float(row.get("rel_sec")),
        }
        events.append(event)
        if status_alias == mpv_alias:
            current_streak = 0
            continue
        mismatches += 1
        current_streak += 1
        max_streak = max(max_streak, current_streak)
    max_allowed_mismatches = max(
        MAX_CONSECUTIVE_STATUS_MPV_MISMATCHES,
        int(comparable * MAX_STATUS_MPV_MISMATCH_RATIO),
    )
    transition_lag_runs = 0
    transition_lag_samples = 0
    initial_transition_lag_runs = 0
    initial_transition_lag_samples = 0
    terminal_transition_lag_runs = 0
    terminal_transition_lag_samples = 0
    chained_transition_lag_runs = 0
    chained_transition_lag_samples = 0
    forward_status_lag_runs = 0
    forward_status_lag_samples = 0
    unexplained_mismatch_runs = 0
    unexplained_mismatch_samples = 0
    long_transition_lag_runs = 0
    long_transition_lag_samples = 0
    max_transition_lag_samples = 0
    max_transition_lag_seconds = 0.0
    index = 0
    while index < len(events):
        if events[index]["aligned"]:
            index += 1
            continue
        start = index
        index += 1
        while (
            index < len(events)
            and not events[index]["aligned"]
            and events[index]["row_index"] == events[index - 1]["row_index"] + 1
        ):
            index += 1
        end = index
        run = events[start:end]
        run_samples = len(run)
        run_seconds = _status_mpv_lag_duration_seconds(run)
        max_transition_lag_samples = max(max_transition_lag_samples, run_samples)
        max_transition_lag_seconds = max(max_transition_lag_seconds, run_seconds)
        if _status_mpv_is_bounded_transition_lag(events, start, end):
            transition_lag_runs += 1
            transition_lag_samples += run_samples
            continue
        if _status_mpv_is_initial_transition_lag(events, start, end):
            initial_transition_lag_runs += 1
            initial_transition_lag_samples += run_samples
            continue
        if _status_mpv_is_bounded_chained_transition_lag(events, start, end):
            chained_transition_lag_runs += 1
            chained_transition_lag_samples += run_samples
            continue
        if _status_mpv_is_terminal_transition_lag(events, start, end):
            terminal_transition_lag_runs += 1
            terminal_transition_lag_samples += run_samples
            continue
        if _status_mpv_is_forward_status_lag(events, start, end):
            forward_status_lag_runs += 1
            forward_status_lag_samples += run_samples
            continue
        if (
            start > 0
            and end < len(events)
            and events[start - 1]["aligned"]
            and events[end]["aligned"]
            and events[start - 1]["status_alias"] == events[start - 1]["mpv_alias"]
            and events[end]["status_alias"] == events[end]["mpv_alias"]
            and events[start - 1]["status_alias"] != events[end]["status_alias"]
            and all(
                _status_mpv_alias_pair_is_transition(
                    event["status_alias"],
                    event["mpv_alias"],
                    events[start - 1]["status_alias"],
                    events[end]["status_alias"],
                )
                for event in run
            )
        ):
            long_transition_lag_runs += 1
            long_transition_lag_samples += run_samples
            continue
        unexplained_mismatch_runs += 1
        unexplained_mismatch_samples += run_samples
    return {
        "comparable_samples": comparable,
        "mismatch_samples": mismatches,
        "max_allowed_mismatch_samples": max_allowed_mismatches,
        "max_consecutive_mismatches": max_streak,
        "max_allowed_consecutive_mismatches": MAX_CONSECUTIVE_STATUS_MPV_MISMATCHES,
        "transition_lag_runs": transition_lag_runs,
        "transition_lag_samples": transition_lag_samples,
        "initial_transition_lag_runs": initial_transition_lag_runs,
        "initial_transition_lag_samples": initial_transition_lag_samples,
        "terminal_transition_lag_runs": terminal_transition_lag_runs,
        "terminal_transition_lag_samples": terminal_transition_lag_samples,
        "chained_transition_lag_runs": chained_transition_lag_runs,
        "chained_transition_lag_samples": chained_transition_lag_samples,
        "forward_status_lag_runs": forward_status_lag_runs,
        "forward_status_lag_samples": forward_status_lag_samples,
        "unexplained_mismatch_runs": unexplained_mismatch_runs,
        "unexplained_mismatch_samples": unexplained_mismatch_samples,
        "long_transition_lag_runs": long_transition_lag_runs,
        "long_transition_lag_samples": long_transition_lag_samples,
        "max_transition_lag_samples": max_transition_lag_samples,
        "max_allowed_transition_lag_samples": MAX_STATUS_MPV_TRANSITION_LAG_SAMPLES,
        "max_transition_lag_seconds": max_transition_lag_seconds,
        "max_allowed_transition_lag_seconds": MAX_STATUS_MPV_TRANSITION_LAG_SECONDS,
        "max_allowed_transition_lag_runs": MAX_STATUS_MPV_TRANSITION_LAG_RUNS,
        "max_allowed_chained_transition_lag_segments": MAX_STATUS_MPV_CHAINED_TRANSITION_LAG_SEGMENTS,
        "max_allowed_forward_status_lag_segments": MAX_STATUS_MPV_FORWARD_STATUS_LAG_SEGMENTS,
    }


def playback_evidence_kind(row: dict[str, str]) -> str:
    if "current_path_kind" not in row:
        # Evidence collected before this field existed predates C25 surfaces.
        return "motion_media"
    kind = str(row.get("current_path_kind") or "")
    if kind in {"public_surface", "still_image_sidecar", "motion_media", "unclassified_media"}:
        return kind
    return "unclassified_media"


def valid_video_dimensions(row: dict[str, str]) -> bool:
    raw = row.get("video_params_json") or ""
    if not raw:
        return False
    try:
        data = json.loads(raw)
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    width = as_float(data.get("dw")) or as_float(data.get("w"))
    height = as_float(data.get("dh")) or as_float(data.get("h"))
    return bool(width and width > 0 and height and height > 0)


def playback_evidence_episodes(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    previous_seq: int | None = None
    previous_frame: float | None = None
    pending_start_reason = "window_start"

    def flush() -> None:
        nonlocal current
        if current is not None:
            episodes.append(current)
            current = None

    for row_index, row in enumerate(rows):
        kind = playback_evidence_kind(row)
        if row.get("ipc_result") != "success":
            flush()
            previous_seq = None
            previous_frame = None
            pending_start_reason = "ipc_interruption"
            continue
        if kind == "unclassified_media":
            flush()
            previous_seq = None
            previous_frame = None
            pending_start_reason = "unclassified_media"
            continue
        key = mpv_item_key(row) or playback_item_key(row)
        frame = as_frame_number(row.get("estimated_frame_number"))
        seq = as_int(row.get("seq"))
        sequence_gap = previous_seq is not None and seq > 0 and seq != previous_seq + 1
        frame_reset = frame is not None and previous_frame is not None and frame < previous_frame
        split_reason = ""
        if current is not None:
            if sequence_gap:
                split_reason = "sequence_gap"
            elif current["kind"] != kind:
                split_reason = "kind_change"
            elif current["key"] != key:
                split_reason = "key_change"
            elif frame_reset:
                split_reason = "frame_reset"
        if split_reason:
            flush()
            pending_start_reason = split_reason
        if current is None:
            current = {
                "kind": kind,
                "key": key,
                "rows": [],
                "frames": [],
                "start_index": row_index,
                "end_index": row_index,
                "start_reason": pending_start_reason,
            }
            pending_start_reason = "continuation"
        current["rows"].append(row)
        current["frames"].append(frame)
        current["end_index"] = row_index
        previous_seq = seq if seq > 0 else None
        previous_frame = frame
    flush()
    return episodes


def row_local_evidence(row: dict[str, str], *, typed: bool) -> bool:
    return (
        as_frame_number(row.get("estimated_frame_number")) is not None
        and row.get("hwdec_current") == EXPECTED_HWDEC
        and as_bool_string(row.get("vo_configured")) == "true"
        and (not typed or valid_video_dimensions(row))
    )


def episode_local_evidence(episode: dict[str, Any]) -> bool:
    rows = episode.get("rows") if isinstance(episode.get("rows"), list) else []
    if not rows:
        return False
    typed = any(bool(row.get("current_path_kind")) for row in rows)
    return any(row_local_evidence(row, typed=typed) for row in rows)


def episode_coherent_frames(episode: dict[str, Any]) -> list[float | None]:
    rows = episode.get("rows") if isinstance(episode.get("rows"), list) else []
    typed = any(bool(row.get("current_path_kind")) for row in rows)
    return [
        as_frame_number(row.get("estimated_frame_number"))
        if row_local_evidence(row, typed=typed)
        else None
        for row in rows
    ]


def sanitized_status_snapshot(row: dict[str, str]) -> dict[str, Any]:
    raw = row.get("status_snapshot_json") or ""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def bounded_transition_unclassified_indexes(rows: list[dict[str, str]]) -> set[int]:
    """Return typed unknown rows proven to be a bounded forward transition.

    The collector cannot classify a new MPV path until the public status catches
    up. This exception stays narrower than the general status/MPV lag policy: it
    requires alignment on both sides, one forward alias, valid local decode
    evidence, and sustained frame progress across the whole unknown run.
    """

    events: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        if row.get("ipc_result") != "success":
            continue
        status_alias = status_item_alias(row)
        mpv_alias = mpv_item_alias(row)
        if not status_alias or not mpv_alias:
            continue
        events.append(
            {
                "row_index": row_index,
                "status_alias": status_alias,
                "mpv_alias": mpv_alias,
                "status_next_alias": status_next_item_alias(row),
                "aligned": status_alias == mpv_alias,
                "rel_sec": as_float(row.get("rel_sec")),
            }
        )

    accepted: set[int] = set()
    index = 0
    while index < len(events):
        if events[index]["aligned"]:
            index += 1
            continue
        start = index
        index += 1
        while (
            index < len(events)
            and not events[index]["aligned"]
            and events[index]["row_index"] == events[index - 1]["row_index"] + 1
        ):
            index += 1
        end = index
        if not _status_mpv_is_bounded_transition_lag(events, start, end):
            continue

        before = events[start - 1]
        after = events[end]
        run = events[start:end]
        if (
            int(run[0]["row_index"]) != int(before["row_index"]) + 1
            or int(after["row_index"]) != int(run[-1]["row_index"]) + 1
        ):
            continue
        old_alias = before["mpv_alias"]
        new_alias = after["mpv_alias"]
        if not all(
            event["status_alias"] == old_alias and event["mpv_alias"] == new_alias
            for event in run
        ):
            continue
        run_rows = [rows[int(event["row_index"])] for event in run]
        before_row = rows[int(before["row_index"])]
        after_row = rows[int(after["row_index"])]
        if playback_evidence_kind(before_row) != "motion_media":
            continue
        if playback_evidence_kind(after_row) != "motion_media":
            continue
        if not row_local_evidence(before_row, typed=True):
            continue
        if not row_local_evidence(after_row, typed=True):
            continue
        if not all(playback_evidence_kind(row) == "unclassified_media" for row in run_rows):
            continue
        if not all(row_local_evidence(row, typed=True) for row in run_rows):
            continue
        bounded_rows = [before_row, *run_rows, after_row]
        sequences = [as_int(row.get("seq")) for row in bounded_rows]
        if any(value <= 0 for value in sequences) or any(
            current != previous + 1 for previous, current in zip(sequences, sequences[1:])
        ):
            continue
        rel_seconds = [as_float(row.get("rel_sec")) for row in bounded_rows]
        if any(value is None or value < 0 for value in rel_seconds):
            continue
        valid_rel_seconds = [float(value) for value in rel_seconds if value is not None]
        if any(
            current <= previous
            for previous, current in zip(valid_rel_seconds, valid_rel_seconds[1:])
        ):
            continue
        if max(valid_rel_seconds) - min(valid_rel_seconds) > MAX_STATUS_MPV_TRANSITION_LAG_SECONDS:
            continue
        frames = [as_frame_number(row.get("estimated_frame_number")) for row in run_rows]
        valid_frames = [float(value) for value in frames if value is not None]
        if len(valid_frames) != len(run_rows) or any(
            current < previous for previous, current in zip(valid_frames, valid_frames[1:])
        ):
            continue
        after_frame = as_frame_number(after_row.get("estimated_frame_number"))
        if after_frame is None or after_frame < valid_frames[-1]:
            continue
        if not sustained_progressed(valid_frames):
            continue
        accepted.update(int(event["row_index"]) for event in run)
    return accepted


def startup_unclassified_media_ok(
    rows: list[dict[str, str]],
    *,
    accepted_transition_indexes: set[int] | None = None,
) -> bool:
    accepted = accepted_transition_indexes or set()
    unclassified = [
        (index, row)
        for index, row in enumerate(rows)
        if row.get("ipc_result") == "success"
        and playback_evidence_kind(row) == "unclassified_media"
        and index not in accepted
    ]
    if not unclassified:
        return True
    first_content_index = next(
        (
            index
            for index, row in enumerate(rows)
            if row.get("ipc_result") == "success"
            and playback_evidence_kind(row) in {"motion_media", "still_image_sidecar"}
        ),
        None,
    )
    if first_content_index is None or len(unclassified) > MAX_STARTUP_UNCLASSIFIED_MEDIA_SAMPLES:
        return False
    if any(index >= first_content_index for index, _row in unclassified):
        return False
    rel_values = [as_float(row.get("rel_sec")) for _index, row in unclassified]
    rel_values = [value for value in rel_values if value is not None]
    if len(rel_values) != len(unclassified):
        return False
    if max(rel_values) - min(rel_values) > MAX_STARTUP_UNCLASSIFIED_MEDIA_SECONDS:
        return False
    allowed_states = {"", "player_starting", "waiting_for_content", "waiting_for_media"}
    for _index, row in unclassified:
        snapshot = sanitized_status_snapshot(row)
        state = str(snapshot.get("playback_state") or row.get("status_playback_state") or "").lower()
        if state not in allowed_states or bool(snapshot.get("current_item")):
            return False
    return True


def present_count(values: list[float | None]) -> int:
    return len([value for value in values if value is not None])


def allowed_transient_missing_socket_after_success(sample_count: int) -> int:
    long_run_allowance = sample_count // TRANSIENT_MISSING_SOCKET_LONG_RUN_SAMPLE_WINDOW
    return min(
        MAX_TRANSIENT_MISSING_SOCKET_LONG_RUN_CAP,
        max(MAX_TRANSIENT_MISSING_SOCKET_AFTER_SUCCESS, long_run_allowance),
    )


def evaluate(
    *,
    samples_path: Path,
    systemd_path: Path | None,
    process_path: Path | None,
    kernel_path: Path | None,
    player_counters_path: Path | None,
    watchdog_path: Path | None = None,
    panfrost_fault_policy: str = "absolute",
) -> dict[str, Any]:
    if panfrost_fault_policy not in PANFROST_FAULT_POLICIES:
        raise ValueError(f"unsupported panfrost fault policy: {panfrost_fault_policy}")
    rows = load_samples(samples_path)
    systemd = read_json(systemd_path, "systemd")
    process = read_json(process_path, "process")
    kernel = read_json(kernel_path, "kernel")
    player_counters = read_json(player_counters_path, "player counters")
    watchdog = read_optional_json(watchdog_path)

    success_rows = [row for row in rows if row.get("ipc_result") == "success"]
    first_success_index = next(
        (index for index, row in enumerate(rows) if row.get("ipc_result") == "success"),
        None,
    )
    startup_ipc_rows = rows[:first_success_index] if first_success_index is not None else rows
    startup_ipc_missing_socket = len(
        [
            row
            for row in startup_ipc_rows
            if row.get("ipc_result") == "error" and row.get("ipc_error") == "missing_socket"
        ]
    )
    startup_ipc_timeouts = len(
        [row for row in startup_ipc_rows if row.get("ipc_result") == "timeout"]
    )
    startup_ipc_other_errors = (
        len(startup_ipc_rows) - startup_ipc_missing_socket - startup_ipc_timeouts
    )
    startup_ipc_span_seconds = 0.0
    startup_ipc_timing_valid = True
    if startup_ipc_rows and first_success_index is not None:
        startup_timing_rows = startup_ipc_rows + [rows[first_success_index]]
        startup_rel_values = [as_float(row.get("rel_sec")) for row in startup_timing_rows]
        startup_ipc_timing_valid = (
            all(value is not None and value >= 0 for value in startup_rel_values)
            and all(
                current is not None and following is not None and following >= current
                for current, following in zip(startup_rel_values, startup_rel_values[1:])
            )
        )
        if startup_ipc_timing_valid:
            startup_ipc_span_seconds = startup_rel_values[-1] - startup_rel_values[0]
    ipc_startup_bounded = (
        first_success_index is not None
        and len(startup_ipc_rows) <= MAX_STARTUP_MISSING_SOCKET_SAMPLES
        and startup_ipc_missing_socket == len(startup_ipc_rows)
        and startup_ipc_timing_valid
        and startup_ipc_span_seconds <= MAX_STARTUP_MISSING_SOCKET_SECONDS
    )
    seen_success = False
    ipc_timeout_after_success = 0
    ipc_error_after_success = 0
    ipc_missing_socket_after_success = 0
    ipc_other_error_after_success = 0
    ipc_missing_socket_streak = 0
    ipc_missing_socket_max_streak = 0
    for row in rows:
        result = row.get("ipc_result")
        if result == "success":
            seen_success = True
            ipc_missing_socket_streak = 0
        elif seen_success and result == "timeout":
            ipc_timeout_after_success += 1
            ipc_missing_socket_streak = 0
        elif seen_success and result == "error":
            ipc_error_after_success += 1
            if row.get("ipc_error") == "missing_socket":
                ipc_missing_socket_after_success += 1
                ipc_missing_socket_streak += 1
                ipc_missing_socket_max_streak = max(ipc_missing_socket_max_streak, ipc_missing_socket_streak)
            else:
                ipc_other_error_after_success += 1
                ipc_missing_socket_streak = 0
        elif seen_success:
            ipc_missing_socket_streak = 0

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
            frame_value = as_frame_number(row.get("estimated_frame_number"))
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
    watchdog_present = bool(watchdog)
    watchdog_event_changed = bool(watchdog.get("event_changed_during_window"))
    watchdog_action = str(watchdog.get("action_during_window") or "")
    watchdog_recovery_during_window = watchdog_event_changed and watchdog_action in WATCHDOG_RECOVERY_ACTIONS
    playlist_size = max_playlist_size(rows)
    transition_required = playlist_size >= 2
    unique_aliases = len(aliases)
    status_unique_aliases = len(status_aliases)
    mpv_unique_aliases = len(mpv_aliases)
    episodes = playback_evidence_episodes(rows)
    motion_episodes = [episode for episode in episodes if episode["kind"] == "motion_media"]
    still_episodes = [episode for episode in episodes if episode["kind"] == "still_image_sidecar"]
    public_surface_episodes = [episode for episode in episodes if episode["kind"] == "public_surface"]
    content_episodes = motion_episodes + still_episodes
    content_aliases = {episode["key"] for episode in content_episodes if episode.get("key")}
    transition_ok = not transition_required or len(content_aliases) >= 2
    alignment_stats = status_mpv_alignment_stats(rows)
    status_advanced_without_mpv = status_unique_aliases >= 2 and len(content_aliases) < 2
    status_mpv_path_aligned = (
        (not transition_required or alignment_stats["comparable_samples"] > 0)
        and not status_advanced_without_mpv
        and alignment_stats["unexplained_mismatch_runs"] == 0
        and alignment_stats["long_transition_lag_runs"] == 0
        and alignment_stats["terminal_transition_lag_runs"] <= 1
    )
    time_pos_progressed = progressed(time_values)
    content_frame_values = [
        frame
        for episode in content_episodes
        for frame in episode.get("frames", [])
    ]
    estimated_frame_present = present_count(content_frame_values) >= 1
    frame_progress_stats = sustained_progress_stats(frame_values)
    public_surface_rows = [row for row in success_rows if playback_evidence_kind(row) == "public_surface"]
    still_image_rows = [row for row in success_rows if playback_evidence_kind(row) == "still_image_sidecar"]
    motion_media_rows = [row for row in success_rows if playback_evidence_kind(row) == "motion_media"]
    unclassified_media_rows = [row for row in success_rows if playback_evidence_kind(row) == "unclassified_media"]
    invalid_frame_number_rows = [
        row
        for row in success_rows
        if row.get("estimated_frame_number") not in (None, "")
        and as_frame_number(row.get("estimated_frame_number")) is None
    ]
    still_frame_values = [as_frame_number(row.get("estimated_frame_number")) for row in still_image_rows]
    motion_episode_stats = [sustained_progress_stats(episode_coherent_frames(episode)) for episode in motion_episodes]
    evaluable_segment_stats = [stats for stats in motion_episode_stats if int(stats["sample_count"]) >= 3]
    short_segment_stats = [stats for stats in motion_episode_stats if 0 < int(stats["sample_count"]) < 3]
    motion_episode_local_ok = [episode_local_evidence(episode) for episode in motion_episodes]
    still_episode_local_ok = [episode_local_evidence(episode) for episode in still_episodes]
    public_surface_episode_local_ok = [episode_local_evidence(episode) for episode in public_surface_episodes]
    motion_proven_indexes = [
        index
        for index, (episode, stats, local_ok) in enumerate(
            zip(motion_episodes, motion_episode_stats, motion_episode_local_ok)
        )
        if local_ok and (
            (int(stats["sample_count"]) >= 3 and bool(stats["passed"]))
            or (int(stats["sample_count"]) == 2 and int(stats["positive_steps"]) >= 1)
        )
    ]
    all_episode_positions = {id(episode): index for index, episode in enumerate(episodes)}
    proven_content_episode_ids = {
        id(motion_episodes[index]) for index in motion_proven_indexes
    }
    proven_content_episode_ids.update(
        id(episode)
        for episode, local_ok in zip(still_episodes, still_episode_local_ok)
        if local_ok
    )
    motion_tolerance_candidates: list[tuple[int, int]] = []
    for index, (episode, stats, local_ok) in enumerate(
        zip(motion_episodes, motion_episode_stats, motion_episode_local_ok)
    ):
        episode_rows = episode.get("rows") if isinstance(episode.get("rows"), list) else []
        if not local_ok or len(episode_rows) != 1 or int(stats["sample_count"]) != 1:
            continue
        position = all_episode_positions[id(episode)]
        later_proven = any(
            id(later) in proven_content_episode_ids for later in episodes[position + 1 :]
        )
        if position == 0 and later_proven:
            motion_tolerance_candidates.append((index, position))
            continue
        if (
            episode.get("start_reason") == "key_change"
            and later_proven
        ):
            motion_tolerance_candidates.append((index, position))
            continue
        if (
            episode.get("start_reason")
            in {"ipc_interruption", "sequence_gap", "frame_reset", "kind_change"}
            and later_proven
        ):
            motion_tolerance_candidates.append((index, position))
    proven_positions = sorted(
        all_episode_positions[episode_id]
        for episode_id in proven_content_episode_ids
    )
    tolerance_groups: dict[tuple[int | None, int], list[int]] = {}
    for motion_index, position in motion_tolerance_candidates:
        previous_proven = next((value for value in reversed(proven_positions) if value < position), None)
        next_proven = next(value for value in proven_positions if value > position)
        tolerance_groups.setdefault((previous_proven, next_proven), []).append(motion_index)
    motion_tolerated_boundary_indexes: list[int] = []
    for indexes in tolerance_groups.values():
        if len(indexes) == 1:
            motion_tolerated_boundary_indexes.append(indexes[0])
            continue
        grouped_episodes = [motion_episodes[index] for index in indexes]
        grouped_frames = [
            frame
            for episode in grouped_episodes
            for frame in episode_coherent_frames(episode)
        ]
        ipc_bridge_ok = (
            len(indexes) <= MAX_CONSECUTIVE_TRANSIENT_MISSING_SOCKET_AFTER_SUCCESS + 1
            and len({episode.get("key") for episode in grouped_episodes}) == 1
            and all(
                episode.get("start_reason") == "ipc_interruption"
                for episode in grouped_episodes[1:]
            )
            and int(sustained_progress_stats(grouped_frames)["positive_steps"]) >= 1
        )
        if ipc_bridge_ok:
            motion_tolerated_boundary_indexes.extend(indexes)
    motion_failed_indexes = [
        index
        for index in range(len(motion_episodes))
        if index not in motion_proven_indexes
        and index not in motion_tolerated_boundary_indexes
    ]
    failed_segment_stats = [motion_episode_stats[index] for index in motion_failed_indexes]
    short_failed_segment_stats = [
        motion_episode_stats[index]
        for index in motion_failed_indexes
        if int(motion_episode_stats[index]["sample_count"]) < 3
    ]
    still_frame_available = bool(still_episodes) and all(still_episode_local_ok)
    motion_frame_progress_ok = not motion_failed_indexes
    still_frame_availability_ok = all(still_episode_local_ok)
    public_surface_availability_ok = all(public_surface_episode_local_ok)
    bounded_transition_unclassified = bounded_transition_unclassified_indexes(rows)
    unclassified_media_bounded_to_startup = startup_unclassified_media_ok(
        rows,
        accepted_transition_indexes=bounded_transition_unclassified,
    )
    proven_content_episodes = [motion_episodes[index] for index in motion_proven_indexes]
    proven_content_episodes.extend(
        episode
        for episode, local_ok in zip(still_episodes, still_episode_local_ok)
        if local_ok
    )
    public_surface_recovery_ok = all(
        any(
            int(content_episode.get("start_index", -1)) > int(surface_episode.get("end_index", -1))
            for content_episode in proven_content_episodes
        )
        for surface_episode in public_surface_episodes
    )
    terminal_row = rows[-1] if rows else {}
    terminal_sample_success = terminal_row.get("ipc_result") == "success"
    terminal_snapshot = sanitized_status_snapshot(terminal_row)
    terminal_playback_state = str(
        terminal_snapshot.get("playback_state")
        or terminal_row.get("status_playback_state")
        or ""
    ).lower()
    terminal_playback_healthy = terminal_sample_success and terminal_playback_state == "playing"
    content_playback_observed = bool(motion_proven_indexes) or (
        bool(still_episodes) and still_frame_availability_ok
    )
    frame_progressed = (
        content_playback_observed
        and motion_frame_progress_ok
        and still_frame_availability_ok
    )
    if failed_segment_stats:
        best_segment = failed_segment_stats[0]
    elif motion_proven_indexes:
        best_segment = motion_episode_stats[motion_proven_indexes[-1]]
    elif motion_episode_stats:
        best_segment = motion_episode_stats[-1]
    elif still_frame_values:
        best_segment = sustained_progress_stats(still_frame_values)
    else:
        best_segment = frame_progress_stats

    panfrost_faults_zero = panfrost_faults == 0
    panfrost_faults_delta_required = panfrost_fault_policy == "delta"
    panfrost_faults_delta_zero = (
        panfrost_faults_delta_present and panfrost_faults_delta == 0
        if panfrost_faults_delta_required
        else not panfrost_faults_delta_present or panfrost_faults_delta == 0
    )
    panfrost_faults_clean = panfrost_faults_zero if panfrost_fault_policy == "absolute" else panfrost_faults_delta_zero
    ipc_missing_socket_allowed = allowed_transient_missing_socket_after_success(len(rows))
    ipc_transient_missing_socket_ok = (
        ipc_missing_socket_after_success <= ipc_missing_socket_allowed
        and ipc_missing_socket_max_streak <= MAX_CONSECUTIVE_TRANSIENT_MISSING_SOCKET_AFTER_SUCCESS
    )
    ipc_stable_after_success = (
        ipc_timeout_after_success == 0
        and ipc_other_error_after_success == 0
        and ipc_transient_missing_socket_ok
    )

    checks = {
        "samples_present": len(rows) > 0,
        "ipc_success_present": len(success_rows) > 0,
        "ipc_startup_bounded": ipc_startup_bounded,
        "ipc_stable_after_success": ipc_stable_after_success,
        "hwdec_expected_present": hwdec_expected_samples > 0,
        "hwdec_no_unexpected": hwdec_unexpected_samples == 0,
        "vo_configured_present": vo_configured_true_samples > 0,
        "vo_configured_no_unexpected": vo_configured_unexpected_samples == 0,
        "estimated_frame_present": estimated_frame_present,
        "estimated_frame_values_valid": not invalid_frame_number_rows,
        "content_playback_observed": content_playback_observed,
        "motion_frame_progress_ok": motion_frame_progress_ok,
        "still_frame_availability_ok": still_frame_availability_ok,
        "public_surface_availability_ok": public_surface_availability_ok,
        "unclassified_media_bounded_to_startup": unclassified_media_bounded_to_startup,
        "public_surface_recovery_ok": public_surface_recovery_ok,
        "terminal_sample_success": terminal_sample_success,
        "terminal_playback_healthy": terminal_playback_healthy,
        "playback_progressed": frame_progressed,
        "status_no_failures": status_failure_samples == 0,
        "transitions_observed_when_required": transition_ok,
        "status_mpv_path_aligned": status_mpv_path_aligned,
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
        "status_mpv_watchdog_recovery_absent": not watchdog_recovery_during_window,
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
            "ipc_startup_samples_before_first_success": len(startup_ipc_rows),
            "ipc_startup_missing_socket": startup_ipc_missing_socket,
            "ipc_startup_timeouts": startup_ipc_timeouts,
            "ipc_startup_other_errors": startup_ipc_other_errors,
            "ipc_startup_span_seconds": startup_ipc_span_seconds,
            "ipc_startup_max_allowed_samples": MAX_STARTUP_MISSING_SOCKET_SAMPLES,
            "ipc_startup_max_allowed_seconds": MAX_STARTUP_MISSING_SOCKET_SECONDS,
            "ipc_timeout_after_first_success": ipc_timeout_after_success,
            "ipc_error_after_first_success": ipc_error_after_success,
            "ipc_missing_socket_after_first_success": ipc_missing_socket_after_success,
            "ipc_other_error_after_first_success": ipc_other_error_after_success,
            "ipc_missing_socket_max_consecutive_after_first_success": ipc_missing_socket_max_streak,
            "ipc_missing_socket_allowed_after_first_success": ipc_missing_socket_allowed,
            "ipc_missing_socket_min_allowed_after_first_success": MAX_TRANSIENT_MISSING_SOCKET_AFTER_SUCCESS,
            "ipc_missing_socket_max_allowed_consecutive_after_first_success": (
                MAX_CONSECUTIVE_TRANSIENT_MISSING_SOCKET_AFTER_SUCCESS
            ),
            "ipc_missing_socket_long_run_sample_window": TRANSIENT_MISSING_SOCKET_LONG_RUN_SAMPLE_WINDOW,
            "ipc_missing_socket_long_run_cap": MAX_TRANSIENT_MISSING_SOCKET_LONG_RUN_CAP,
            "unique_aliases": unique_aliases,
            "status_unique_aliases": status_unique_aliases,
            "mpv_unique_aliases": mpv_unique_aliases,
            "status_transitions_observed": status_unique_aliases >= 2,
            "mpv_media_transitions_observed": len(content_aliases) >= 2,
            "mpv_content_unique_aliases": len(content_aliases),
            "status_mpv_comparable_samples": alignment_stats["comparable_samples"],
            "status_mpv_mismatch_samples": alignment_stats["mismatch_samples"],
            "status_mpv_max_allowed_mismatch_samples": alignment_stats["max_allowed_mismatch_samples"],
            "status_mpv_max_consecutive_mismatches": alignment_stats["max_consecutive_mismatches"],
            "status_mpv_max_allowed_consecutive_mismatches": alignment_stats["max_allowed_consecutive_mismatches"],
            "status_mpv_transition_lag_runs": alignment_stats["transition_lag_runs"],
            "status_mpv_transition_lag_samples": alignment_stats["transition_lag_samples"],
            "status_mpv_initial_transition_lag_runs": alignment_stats["initial_transition_lag_runs"],
            "status_mpv_initial_transition_lag_samples": alignment_stats["initial_transition_lag_samples"],
            "status_mpv_terminal_transition_lag_runs": alignment_stats["terminal_transition_lag_runs"],
            "status_mpv_terminal_transition_lag_samples": alignment_stats["terminal_transition_lag_samples"],
            "status_mpv_chained_transition_lag_runs": alignment_stats["chained_transition_lag_runs"],
            "status_mpv_chained_transition_lag_samples": alignment_stats["chained_transition_lag_samples"],
            "status_mpv_forward_status_lag_runs": alignment_stats["forward_status_lag_runs"],
            "status_mpv_forward_status_lag_samples": alignment_stats["forward_status_lag_samples"],
            "status_mpv_unexplained_mismatch_runs": alignment_stats["unexplained_mismatch_runs"],
            "status_mpv_unexplained_mismatch_samples": alignment_stats["unexplained_mismatch_samples"],
            "status_mpv_long_transition_lag_runs": alignment_stats["long_transition_lag_runs"],
            "status_mpv_long_transition_lag_samples": alignment_stats["long_transition_lag_samples"],
            "status_mpv_max_transition_lag_samples": alignment_stats["max_transition_lag_samples"],
            "status_mpv_max_allowed_transition_lag_samples": alignment_stats["max_allowed_transition_lag_samples"],
            "status_mpv_max_transition_lag_seconds": alignment_stats["max_transition_lag_seconds"],
            "status_mpv_max_allowed_transition_lag_seconds": alignment_stats["max_allowed_transition_lag_seconds"],
            "status_mpv_max_allowed_transition_lag_runs": alignment_stats["max_allowed_transition_lag_runs"],
            "status_mpv_max_allowed_chained_transition_lag_segments": alignment_stats[
                "max_allowed_chained_transition_lag_segments"
            ],
            "status_advanced_without_mpv": status_advanced_without_mpv,
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
            "motion_media_episodes": len(motion_episodes),
            "motion_media_proven_episodes": len(motion_proven_indexes),
            "motion_media_tolerated_boundary_episodes": len(motion_tolerated_boundary_indexes),
            "motion_media_failed_episodes": len(motion_failed_indexes),
            "still_image_episodes": len(still_episodes),
            "still_image_failed_episodes": len([ok for ok in still_episode_local_ok if not ok]),
            "public_surface_episodes": len(public_surface_episodes),
            "public_surface_failed_episodes": len(
                [ok for ok in public_surface_episode_local_ok if not ok]
            ),
            "public_surface_samples": len(public_surface_rows),
            "still_image_sidecar_samples": len(still_image_rows),
            "still_image_frame_available": still_frame_available,
            "motion_media_samples": len(motion_media_rows),
            "unclassified_media_samples": len(unclassified_media_rows),
            "unclassified_media_bounded_transition_samples": len(
                bounded_transition_unclassified
            ),
            "invalid_frame_number_samples": len(invalid_frame_number_rows),
            "unclassified_media_max_startup_samples": MAX_STARTUP_UNCLASSIFIED_MEDIA_SAMPLES,
            "unclassified_media_max_startup_seconds": MAX_STARTUP_UNCLASSIFIED_MEDIA_SECONDS,
            "terminal_playback_state": terminal_playback_state,
            "status_failure_samples": status_failure_samples,
            "nrestarts_delta": nrestarts_delta,
            "mpv_count": mpv_count,
            "total_mpv_count": total_mpv_count,
            "media_load_failed": media_load_failed,
            "mpv_restart": mpv_restart,
            "status_mpv_watchdog_sidecar_present": watchdog_present,
            "status_mpv_watchdog_event_changed": watchdog_event_changed,
            "status_mpv_watchdog_action_during_window": watchdog_action,
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
    parser.add_argument("--watchdog", type=Path)
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
        watchdog_path=args.watchdog,
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
