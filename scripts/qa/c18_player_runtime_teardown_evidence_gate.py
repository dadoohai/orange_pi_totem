#!/usr/bin/env python3
"""Validate C18 player-runtime HW teardown/panfrost evidence.

This gate validates a lab-only, operator-attended teardown trial directory that
proves, on hardware, that repeated MPV teardown/relaunch AND the production
service restart path complete with per-window ``panfrost_faults_delta == 0``.

It is measurement-based and path-agnostic (see
``docs/c18-player-runtime-teardown-gate-design.md``). It does NOT claim public
thaw, stable/prod readiness, soak/endurance, full power-loss coverage, or that
the fresh-IPC (C1) quit SUCCESS path works against a live socket (that path is a
secondary ``_ipc is None`` corner and is an explicit non-claim).

A green ``--self-test`` proves the gate logic only, NOT teardown on hardware.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.player_runtime.teardown_evidence_gate.v1"
MANIFEST_SCHEMA = "dadooh.c18.teardown.evidence_manifest.v1"
TRIAL_SCHEMA = "dadooh.c18.player_runtime.teardown_trial.v1"
CYCLE_SCHEMA = "dadooh.c18.player_runtime.teardown_cycle.v1"
FRESH_IPC_SCHEMA = "dadooh.c18.player_runtime.teardown_fresh_ipc_probe.v1"
MID_DECODE_SCHEMA = "dadooh.c18.player_runtime.teardown_mid_decode_sigterm_probe.v1"
PLAYBACK_SCHEMA = "dadooh.c18.playback.deep_health.v1"

MIN_CYCLES = 2
CYCLE_KINDS = {"relaunch", "service_restart"}
GRACEFUL_STOP_METHODS = {"none", "ipc_quit", "sigterm"}
EXPECTED_HWDEC = "v4l2request-copy"
EXPECTED_MPV_EXE = "/opt/totem/hwdecode/bin/mpv"
EXPECTED_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
MID_DECODE_MAX_SAMPLE_TO_SIGNAL_SEC = 1.0
MID_DECODE_EOF_MARGIN_SEC = 2.0

PRIVATE_IP_RE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
SECRET_TEXT_PATTERNS = (
    ("github_token", re.compile(r"\b(?:github_pat_|gh[opsu]_[A-Za-z0-9_]{12,})")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I)),
    ("authorization_header", re.compile(r"\bAuthorization\s*:\s*\S+", re.I)),
    ("password_value", re.compile(r"\bpassword\s*[:=]\s*['\"]?[^'\"\s,}]+", re.I)),
)
SENSITIVE_KEY_PARTS = ("api_key", "token", "password", "secret", "ssid", "environment_id")

HEALTH_CHECKS = (
    "samples_present",
    "service_active",
    "single_mpv",
    "mpv_path_c18_stack",
    "hwdec_expected_present",
    "hwdec_no_unexpected",
    "estimated_frame_present",
    "playback_progressed",
    "media_load_failed_zero",
    "mpv_restart_zero",
    "panfrost_faults_zero",
    "panfrost_faults_delta_zero",
    "mmc_timeout_reset_zero",
    "ext4_errors_zero",
    "nrestarts_stable",
    "status_no_failures",
)

# Parsed as exact KEY=VALUE pairs (a substring test would let "STRICT_GPU_FAULTS=05"
# or "...RC=440" poison the attestation). None means "any non-empty value".
POSTCHECK_REQUIRED = {
    "BOOT_ID": None,
    "UPTIME": None,
    "SERVICE_ACTIVE": "active",
    "TIMER_ENABLED": "disabled",
    "STRICT_GPU_FAULTS": "0",
    "PUBLIC_PLAYER_RUNTIME_APPLY_LOCAL_RC": "44",
    "PUBLIC_PLAYER_RUNTIME_ROLLBACK_RC": "44",
    "PUBLIC_PLAYER_RUNTIME_RECONCILE_RC": "44",
}

# Broad teardown-class GPU fault matcher. Kept textually identical to the
# producer harness (scripts/board/c18_player_runtime_teardown_trial.py
# GPU_FAULT_RE). The GATE is authoritative: it RECOMPUTES the per-window fault
# counts from the manifest-bound kernel-before/after text and rejects any
# cycle.json scalar that disagrees, so a drift between the two regexes can only
# make the gate stricter (fail closed), never weaker.
#
# Intentionally GREEDY (fail-closed bias): a GPU-driver token (panfrost|lima|mali)
# co-occurring with any teardown/abort keyword is treated as a fault, plus a set
# of driver-specific literals. RECALL IS BOUNDED, NOT EXHAUSTIVE: a fault whose
# wording this matcher does not cover is invisible to GR2. The HW run (task #6)
# MUST validate this matcher against real clean-board journal output and may need
# to switch to deny-by-default (flag any panfrost|lima|mali line not on a tuned
# benign allowlist). See docs/c18-player-runtime-teardown-gate-design.md.
#
# The first alternative is an exact SUPERSET of the on-board deep-health collector
# (scripts/board/c18_playback_health_collect.py: panfrost.*(fault|hang|reset|error)),
# so this gate can never be WEAKER than the production health source it corroborates.
# There is NO trailing word boundary on the keyword group: inflected forms such as
# "resetting" / "faults" / "faulting" / "hanging" (the canonical panfrost teardown
# recovery wordings) must match.
GPU_FAULT_RE = re.compile(
    r"panfrost.*(?:fault|hang|reset|error)"
    r"|(?:panfrost|lima|mali)\b.*(?:fault|hang|hung|reset|error|timeout|"
    r"timed[ -]?out|lockup|stall|abort|terminated|unrecoverable)"
    r"|gpu sched timeout|drm_sched[^\n]*timeout|JOB_BUS_FAULT|"
    r"Unhandled Page fault|BO has no sgt",
    re.IGNORECASE,
)
_HEX_RUN_RE = re.compile(r"0x[0-9a-fA-F]+")


def fault_lines(kernel_text: str) -> list[str]:
    return [ln for ln in kernel_text.splitlines() if GPU_FAULT_RE.search(ln)]


def sanitize_kernel_line(line: str) -> str:
    return _HEX_RUN_RE.sub("0xADDR", line).strip()


# --------------------------------------------------------------------------- #
# Shared scaffolding (cloned from c18_player_runtime_powerloss_evidence_gate). #
# --------------------------------------------------------------------------- #
def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _reject_nonfinite(token: str) -> float:
    # Called by json for the bare NaN / Infinity / -Infinity literals. Rejecting
    # them stops a NaN window_anchor (NaN compares False to everything) from
    # silently evading the strict window-ordering guards.
    raise ValueError(f"non_finite_json_constant:{token}")


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _nonfinite_paths(value: Any, *, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, float) and not math.isfinite(value):
        hits.append(path)
    elif isinstance(value, dict):
        for key, child in value.items():
            hits.extend(_nonfinite_paths(child, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_nonfinite_paths(child, path=f"{path}[{index}]"))
    return hits


def load_json(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_nonfinite)
    except Exception as exc:
        errors.append(f"{label}_json_error:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{label}_not_object")
        return {}
    for hit in _nonfinite_paths(data):
        errors.append(f"{label}_non_finite:{hit}")
    return data


def sensitive_json_values(value: Any, *, key_path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            lower = str(key).lower()
            if any(part in lower for part in SENSITIVE_KEY_PARTS):
                if child not in ("", None, [], {}, "null"):
                    hits.append(child_path)
            hits.extend(sensitive_json_values(child, key_path=child_path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            hits.extend(sensitive_json_values(child, key_path=f"{key_path}[{idx}]"))
    return hits


def validate_files(run_dir: Path, errors: list[str]) -> list[str]:
    files: list[str] = []
    for path in sorted(run_dir.rglob("*")):
        rel_path = rel(path, run_dir)
        if path.is_symlink():
            errors.append(f"symlink_not_allowed:{rel_path}")
            continue
        if path.is_dir():
            continue
        files.append(rel_path)
        if path.stat().st_size == 0:
            errors.append(f"zero_size_file:{rel_path}")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"read_error:{rel_path}:{type(exc).__name__}")
            continue
        if PRIVATE_IP_RE.search(text):
            errors.append(f"private_ip_leak:{rel_path}")
        for label, pattern in SECRET_TEXT_PATTERNS:
            if pattern.search(text):
                errors.append(f"secret_pattern:{label}:{rel_path}")
        if path.suffix == ".json":
            data = load_json(path, errors, rel_path)
            for hit in sensitive_json_values(data):
                errors.append(f"sensitive_json_value:{rel_path}:{hit}")
        elif path.suffix == ".ndjson":
            for line_no, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line, parse_constant=_reject_nonfinite)
                except Exception as exc:
                    errors.append(f"ndjson_parse_error:{rel_path}:{line_no}:{type(exc).__name__}")
                    break
                for hit in _nonfinite_paths(row):
                    errors.append(f"ndjson_non_finite:{rel_path}:{line_no}:{hit}")
    return files


def validate_manifest(run_dir: Path, files: list[str], errors: list[str]) -> dict[str, Any]:
    manifest = load_json(run_dir / "evidence-manifest.json", errors, "evidence_manifest")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        errors.append("manifest_schema")
    for key in ("artifact_id", "component", "board_image_marker", "source_commit"):
        if not isinstance(manifest.get(key), str) or not manifest.get(key):
            errors.append(f"manifest_missing_{key}")
    if manifest.get("component") != "player-runtime":
        errors.append("manifest_component")
    if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("source_commit", ""))):
        errors.append("manifest_source_commit")
    artifacts = manifest.get("files")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("manifest_files_missing")
        return manifest
    declared: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            errors.append("manifest_file_entry_not_object")
            continue
        name = item.get("file")
        if not isinstance(name, str) or not name or name.startswith("/") or ".." in Path(name).parts:
            errors.append(f"manifest_bad_file:{name}")
            continue
        declared[name] = item
        path = run_dir / name
        if not path.is_file():
            errors.append(f"manifest_file_missing:{name}")
            continue
        if item.get("bytes") != path.stat().st_size:
            errors.append(f"manifest_bytes_mismatch:{name}")
        if item.get("sha256") != sha256_file(path):
            errors.append(f"manifest_sha256_mismatch:{name}")
    actual = set(files) - {"evidence-manifest.json"}
    declared_set = set(declared)
    for extra in sorted(actual - declared_set):
        errors.append(f"manifest_undeclared_file:{extra}")
    for missing in sorted(declared_set - actual):
        errors.append(f"manifest_declared_absent:{missing}")
    return manifest


def validate_health(data: dict[str, Any], label: str, errors: list[str]) -> None:
    if data.get("schema") != PLAYBACK_SCHEMA:
        errors.append(f"{label}_schema")
    if data.get("passed") is not True:
        errors.append(f"{label}_not_passed")
    if data.get("failure_reasons") not in ([], None):
        errors.append(f"{label}_failure_reasons")
    checks = data.get("checks")
    if not isinstance(checks, dict):
        errors.append(f"{label}_checks_missing")
        return
    for check in HEALTH_CHECKS:
        if check not in checks:
            errors.append(f"{label}_check_missing:{check}")
        elif checks.get(check) is not True:
            errors.append(f"{label}_check_failed:{check}")


# --------------------------------------------------------------------------- #
# Teardown-specific semantics.                                                 #
# --------------------------------------------------------------------------- #
def require_files(run_dir: Path, required: list[str], errors: list[str]) -> None:
    for rel_path in required:
        if not (run_dir / rel_path).is_file():
            errors.append(f"missing_required:{rel_path}")


def validate_cycle(run_dir: Path,
                   cycle_dir: str,
                   expected_index: int,
                   summary_boot_id: str,
                   summary_cycle: dict[str, Any],
                   errors: list[str]) -> dict[str, Any]:
    """Validate one cycle dir. Returns {kind, monotonic_before, monotonic_after}.

    GR2 is RECOMPUTED from the manifest-bound kernel-before/after text; the
    cycle.json scalars are treated as claims that must agree with the raw
    evidence, never as the source of truth.
    """
    label = f"cycle{expected_index:02d}"
    result: dict[str, Any] = {"kind": None, "monotonic_before": None, "monotonic_after": None}
    cycle = load_json(run_dir / cycle_dir / "cycle.json", errors, label)
    if cycle.get("schema") != CYCLE_SCHEMA:
        errors.append(f"{label}_schema")
    if cycle.get("index") != expected_index:
        errors.append(f"{label}_index_mismatch")
    kind = cycle.get("kind")
    if kind not in CYCLE_KINDS:
        errors.append(f"{label}_kind_invalid:{kind}")
    else:
        result["kind"] = kind
    # GR1: every cycle must be in the SAME boot as the summary.
    if not isinstance(cycle.get("boot_id"), str) or not cycle.get("boot_id"):
        errors.append(f"{label}_boot_id_missing")
    elif summary_boot_id and cycle.get("boot_id") != summary_boot_id:
        errors.append(f"{label}_boot_id_not_same_boot")
    anchor = cycle.get("window_anchor")
    if not isinstance(anchor, dict):
        errors.append(f"{label}_window_anchor_missing")
    else:
        if anchor.get("boot_id") != cycle.get("boot_id"):
            errors.append(f"{label}_window_anchor_boot_mismatch")
        for key in ("monotonic_before", "monotonic_after"):
            if not _finite_number(anchor.get(key)):  # rejects missing/bool/NaN/inf
                errors.append(f"{label}_window_anchor_{key}_missing")
        mb, ma = anchor.get("monotonic_before"), anchor.get("monotonic_after")
        if _finite_number(mb) and _finite_number(ma):
            result["monotonic_before"], result["monotonic_after"] = mb, ma
            # Require a POSITIVE-width window; a zero-width [T,T] window is a
            # single instant photocopied as a "teardown" and is rejected.
            if ma <= mb:
                errors.append(f"{label}_window_anchor_zero_or_negative_width")

    # GR2: REQUIRE the raw journal windows and RECOMPUTE the fault counts.
    before_path = run_dir / cycle_dir / "kernel-before.txt"
    after_path = run_dir / cycle_dir / "kernel-after.txt"
    before_faults: list[str] | None = None
    after_faults: list[str] | None = None
    for tag, path in (("kernel-before.txt", before_path), ("kernel-after.txt", after_path)):
        if not path.is_file():
            errors.append(f"missing_required:{cycle_dir}/{tag}")
    if before_path.is_file():
        before_faults = fault_lines(before_path.read_text(encoding="utf-8", errors="replace"))
    if after_path.is_file():
        after_faults = fault_lines(after_path.read_text(encoding="utf-8", errors="replace"))

    before, after = cycle.get("gpu_faults_before"), cycle.get("gpu_faults_after")
    delta = cycle.get("gpu_faults_delta")
    for key, val in (("gpu_faults_before", before), ("gpu_faults_after", after), ("gpu_faults_delta", delta)):
        if not isinstance(val, int) or isinstance(val, bool):
            errors.append(f"{label}_{key}_not_int")
    if isinstance(before, int) and isinstance(after, int) and isinstance(delta, int):
        if delta != after - before:
            errors.append(f"{label}_gpu_faults_delta_inconsistent")
    # Bind the scalar claims to the recomputed counts from the hashed kernel text.
    if before_faults is not None and isinstance(before, int) and len(before_faults) != before:
        errors.append(f"{label}_gpu_faults_before_text_mismatch:{len(before_faults)}!={before}")
    if after_faults is not None and isinstance(after, int) and len(after_faults) != after:
        errors.append(f"{label}_gpu_faults_after_text_mismatch:{len(after_faults)}!={after}")
    if before_faults is not None and after_faults is not None:
        # Cursor-anchored window: the after-list must extend the before-list.
        if after_faults[:len(before_faults)] != before_faults:
            errors.append(f"{label}_kernel_window_not_superset")
        recomputed_delta = len(after_faults) - len(before_faults)
        if recomputed_delta != 0:
            errors.append(f"{label}_recomputed_gpu_faults_delta_nonzero:{recomputed_delta}")
        # new_fault_lines_sanitized must equal the sanitized tail beyond the before-window.
        expected_new = [sanitize_kernel_line(ln) for ln in after_faults[len(before_faults):]][:20]
        if cycle.get("new_fault_lines_sanitized") != expected_new:
            errors.append(f"{label}_new_fault_lines_sanitized_mismatch")
    # ABSOLUTE-ZERO: delta==0 is not enough -- a board with a persistent panfrost
    # fault present in EVERY window (before==after>0) has delta 0 yet is faulting.
    # Honor the deep-health panfrost_faults_zero contract from the raw kernel text
    # rather than trusting the health boolean: any matched fault line in any window
    # fails the cycle.
    if before_faults:
        errors.append(f"{label}_panfrost_faults_present_before:{len(before_faults)}")
    if after_faults:
        errors.append(f"{label}_panfrost_faults_present_after:{len(after_faults)}")

    if isinstance(delta, int) and not isinstance(delta, bool) and delta < 0 \
            and cycle.get("gpu_faults_delta_anomalous") is not True:
        errors.append(f"{label}_negative_delta_not_flagged_anomalous")
    if cycle.get("gpu_faults_delta_anomalous") is True:
        errors.append(f"{label}_gpu_faults_delta_anomalous")
    if delta != 0:
        errors.append(f"{label}_gpu_faults_delta_nonzero:{delta}")
    if cycle.get("process_exited") is not True:
        errors.append(f"{label}_process_not_exited")
    stop = cycle.get("stop")
    if not isinstance(stop, dict):
        errors.append(f"{label}_stop_missing")
    else:
        if stop.get("method") not in GRACEFUL_STOP_METHODS:
            errors.append(f"{label}_stop_method_not_graceful:{stop.get('method')}")
        if stop.get("returncode") != 0:
            errors.append(f"{label}_stop_returncode_nonzero")
    if cycle.get("passed") is not True:
        errors.append(f"{label}_not_passed")
    # Bind the per-cycle record to the summary's cycle entry.
    if isinstance(summary_cycle, dict):
        for key in ("index", "kind", "gpu_faults_delta", "passed"):
            if summary_cycle.get(key) != cycle.get(key):
                errors.append(f"{label}_summary_cycle_{key}_mismatch")
    # Per-cycle deep-health (independent GR2 corroboration incl. panfrost_faults_delta_zero).
    validate_health(
        load_json(run_dir / cycle_dir / "health" / "playback-deep-health-public.json", errors, f"{label}_health"),
        f"{label}_health",
        errors,
    )
    return result


def validate_fresh_ipc_probe(run_dir: Path, summary: dict[str, Any], errors: list[str]) -> None:
    path = run_dir / "fresh_ipc_probe.json"
    present = path.is_file()
    if summary.get("gr4_secondary_present") is not present:
        errors.append("fresh_ipc_probe_presence_mismatch")
    if not present:
        return
    probe = load_json(path, errors, "fresh_ipc_probe")
    if probe.get("schema") != FRESH_IPC_SCHEMA:
        errors.append("fresh_ipc_probe_schema")
    if probe.get("forced_ipc_none") is not True:
        errors.append("fresh_ipc_probe_not_forced")
    failed_log = "MPV IPC fresh command failed command=quit"
    observed = probe.get("observed_log")
    outcome = probe.get("outcome")
    # The fresh-IPC quit SUCCESS path is, per design + the kiosk.py _ipc invariant
    # (guarded by c18_player_runtime_teardown_static_test.py), effectively
    # unreachable in production: the only moment _ipc is None with mpv alive is the
    # start_ipc_timeout corner, where the socket is not yet connectable, so the
    # fresh quit FAILS and falls back to SIGTERM. An honest probe of the forced
    # _ipc-is-None corner can therefore ONLY observe "fresh_failed_fallback_sigterm".
    # A "fresh_sent" claim is REJECTED so it can never be read as "fresh-IPC quit
    # SUCCESS proven on hardware" (the GR4b non-claim). If a board ever genuinely
    # reaches the success path, that is a NEW fact for a human to investigate, not a
    # result this gate silently accepts.
    if outcome == "fresh_sent":
        errors.append("fresh_ipc_probe_success_path_unreachable_claim")
    elif outcome == "fresh_failed_fallback_sigterm":
        if observed != failed_log:
            errors.append("fresh_ipc_probe_outcome_log_disagree")
    else:
        errors.append(f"fresh_ipc_probe_outcome_invalid:{outcome}")
    if probe.get("code_path_reached") is not True:
        errors.append("fresh_ipc_probe_code_path_not_reached")
    if not isinstance(probe.get("non_claim"), str) or "GR4b" not in str(probe.get("non_claim")):
        errors.append("fresh_ipc_probe_non_claim_missing")
    # This probe NEVER contributes a pass for GR4b; it is informational only.


def load_ndjson(path: Path, errors: list[str], label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        errors.append(f"missing_required:{rel(path, path.parents[2]) if len(path.parents) > 2 else path.name}")
        return rows
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        errors.append(f"{label}_read_error:{type(exc).__name__}")
        return rows
    for line_no, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line, parse_constant=_reject_nonfinite)
        except Exception as exc:
            errors.append(f"{label}_ndjson_error:{line_no}:{type(exc).__name__}")
            continue
        if not isinstance(row, dict):
            errors.append(f"{label}_ndjson_row_not_object:{line_no}")
            continue
        for hit in _nonfinite_paths(row):
            errors.append(f"{label}_ndjson_non_finite:{line_no}:{hit}")
        rows.append(row)
    return rows


def _as_number(value: Any) -> float | None:
    if _finite_number(value):
        return float(value)
    return None


def recompute_mid_decode(samples: list[dict[str, Any]], *,
                         summary_boot_id: str,
                         signal_monotonic: float | None) -> dict[str, Any]:
    errs: list[str] = []
    good = [s for s in samples if s.get("ipc_result") == "success"]
    if len(good) < 3:
        errs.append("too_few_samples")
    for sample in good:
        if sample.get("boot_id") != summary_boot_id:
            errs.append("sample_boot_id_mismatch")
            break
    for prev, cur in zip(good, good[1:]):
        pm, cm = _as_number(prev.get("monotonic")), _as_number(cur.get("monotonic"))
        if pm is None or cm is None or cm <= pm:
            errs.append("sample_monotonic_not_increasing")
        elif cm - pm < 0.5:
            errs.append("sample_spacing_too_short")
    frames = [_as_number(s.get("estimated_frame_number")) for s in good]
    times = [_as_number(s.get("time_pos")) for s in good]
    duration = _as_number(good[-1].get("duration")) if good else None
    if any(v is None for v in frames) or any(v is None for v in times):
        errs.append("sample_missing_frame_or_time")
    elif any(cur <= prev for prev, cur in zip(frames, frames[1:])):  # type: ignore[arg-type]
        errs.append("frames_not_strictly_increasing")
    elif (times[-1] - times[0]) < 0.2:  # type: ignore[operator]
        errs.append("time_pos_not_advancing")
    if good:
        last = good[-1]
        if last.get("hwdec_current") != EXPECTED_HWDEC:
            errs.append("hwdec_current_not_expected")
        if last.get("vo_configured") is not True:
            errs.append("vo_not_configured")
        for key in ("idle_active", "pause", "eof_reached"):
            if last.get(key) is not False:
                errs.append(f"{key}_not_false")
        if duration is None or times[-1] is None:  # type: ignore[index]
            errs.append("duration_or_time_missing")
        elif duration - times[-1] < MID_DECODE_EOF_MARGIN_SEC:  # type: ignore[operator]
            errs.append("eof_margin_too_small")
        if signal_monotonic is not None:
            last_m = _as_number(last.get("monotonic"))
            if last_m is None or signal_monotonic - last_m > MID_DECODE_MAX_SAMPLE_TO_SIGNAL_SEC:
                errs.append("last_sample_stale_for_signal")
            elif signal_monotonic < last_m:
                errs.append("signal_before_last_sample")
    return {
        "confirmed": not errs,
        "errors": errs,
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
            if signal_monotonic is not None and good and _finite_number(good[-1].get("monotonic"))
            else None
        ),
        "mid_decode_margin_sec": (
            duration - times[-1]  # type: ignore[operator]
            if duration is not None and times and times[-1] is not None else None
        ),
    }


def _rounded_match(expected: Any, observed: Any) -> bool:
    if isinstance(expected, float) and isinstance(observed, (int, float)) and not isinstance(observed, bool):
        return abs(expected - float(observed)) < 0.001
    return expected == observed


def validate_mid_decode_probe(run_dir: Path, summary: dict[str, Any],
                              cycle_windows: list[tuple[int, Any, Any]],
                              summary_boot_id: str,
                              errors: list[str]) -> None:
    path = run_dir / "mid_decode_sigterm_probe.json"
    present = path.is_file()
    attested = summary.get("mid_decode_probe_present") is True
    if present != attested:
        errors.append("mid_decode_probe_presence_mismatch")
    if not present and not attested:
        return
    probe = load_json(path, errors, "mid_decode_probe")
    if probe.get("schema") != MID_DECODE_SCHEMA:
        errors.append("mid_decode_probe_schema")
    if probe.get("passed") is not True:
        errors.append("mid_decode_probe_not_passed")
    if probe.get("claim") != "mid_decode_sigterm_panfrost_window_measured":
        errors.append("mid_decode_probe_unknown_claim")
    if probe.get("kiosk_killed_before_signal") is not True:
        errors.append("mid_decode_probe_kiosk_not_killed_before_signal")
    if probe.get("cfg_hwdec") != "auto":
        errors.append("mid_decode_probe_cfg_hwdec")
    wrapper = probe.get("wrapper")
    if not isinstance(wrapper, dict):
        errors.append("mid_decode_probe_wrapper_missing")
    else:
        if wrapper.get("path") != EXPECTED_WRAPPER:
            errors.append("mid_decode_probe_wrapper_path")
        if not re.fullmatch(r"[0-9a-f]{64}", str(wrapper.get("sha256", ""))):
            errors.append("mid_decode_probe_wrapper_sha256")
    non_claims = probe.get("non_claims")
    non_claim_text = "\n".join(str(item) for item in non_claims) if isinstance(non_claims, list) else ""
    for token in ("GR4b", "healthy-not-wedged", "no-kiosk-alive", "production-timing-unmeasured", "single-image"):
        if token not in non_claim_text:
            errors.append(f"mid_decode_probe_non_claim_missing:{token}")
    prod = probe.get("production_service")
    if not isinstance(prod, dict):
        errors.append("mid_decode_probe_production_service_missing")
    else:
        for key in ("stopped", "restored", "deep_health_passed"):
            if prod.get(key) is not True:
                errors.append(f"mid_decode_probe_production_service_{key}_not_true")
    attempts = probe.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        errors.append("mid_decode_probe_attempts_missing")
        attempts = []
    probe_root = run_dir / "mid-decode-sigterm-probe"
    present_attempt_dirs = sorted(
        p.name for p in probe_root.iterdir()
        if probe_root.is_dir() and p.is_dir() and p.name.startswith("attempt-")
    ) if probe_root.is_dir() else []
    expected_attempt_dirs = [f"attempt-{i:02d}" for i in range(len(attempts))]
    if present_attempt_dirs != expected_attempt_dirs:
        errors.append(f"mid_decode_probe_attempt_dirs_mismatch:{present_attempt_dirs}!={expected_attempt_dirs}")
    last_cycle_after = None
    finite_cycle_ends = [ma for (_i, _mb, ma) in cycle_windows if _finite_number(ma)]
    if finite_cycle_ends:
        last_cycle_after = max(finite_cycle_ends)
    previous_after = last_cycle_after
    for index, attempt in enumerate(attempts):
        label = f"mid_decode_attempt{index:02d}"
        if not isinstance(attempt, dict):
            errors.append(f"{label}_not_object")
            continue
        if attempt.get("index") != index:
            errors.append(f"{label}_index_mismatch")
        if attempt.get("passed") is not True:
            errors.append(f"{label}_not_passed")
        anchor = attempt.get("window_anchor")
        mb = ma = None
        if not isinstance(anchor, dict):
            errors.append(f"{label}_window_anchor_missing")
        else:
            if anchor.get("boot_id") != summary_boot_id:
                errors.append(f"{label}_window_anchor_boot_mismatch")
            mb, ma = anchor.get("monotonic_before"), anchor.get("monotonic_after")
            if not _finite_number(mb):
                errors.append(f"{label}_window_anchor_monotonic_before_missing")
            if not _finite_number(ma):
                errors.append(f"{label}_window_anchor_monotonic_after_missing")
            if _finite_number(mb) and _finite_number(ma):
                if ma <= mb:
                    errors.append(f"{label}_window_anchor_zero_or_negative_width")
                if previous_after is not None and previous_after >= mb:
                    errors.append("mid_decode_probe_window_overlaps_cycles" if index == 0 else "mid_decode_probe_attempt_windows_overlap")
                previous_after = ma
        signal = attempt.get("signal")
        signal_m = None
        if not isinstance(signal, dict):
            errors.append(f"{label}_signal_missing")
        else:
            if signal.get("name") != "SIGTERM":
                errors.append(f"{label}_signal_name")
            if signal.get("target") != "mpv_pgid":
                errors.append(f"{label}_signal_target")
            if signal.get("delivered") is not True:
                errors.append(f"{label}_signal_not_delivered")
            signal_m = signal.get("monotonic")
            if not _finite_number(signal_m):
                errors.append(f"{label}_signal_monotonic_missing")
            elif _finite_number(mb) and _finite_number(ma) and not (mb <= signal_m <= ma):
                errors.append(f"{label}_signal_monotonic_outside_window")
        attempt_dir = run_dir / "mid-decode-sigterm-probe" / f"attempt-{index:02d}"
        before_path = attempt_dir / "kernel-before.txt"
        after_path = attempt_dir / "kernel-after.txt"
        samples_path = attempt_dir / "decode-samples.ndjson"
        for tag, file_path in (
            ("kernel-before.txt", before_path),
            ("kernel-after.txt", after_path),
            ("decode-samples.ndjson", samples_path),
        ):
            if not file_path.is_file():
                errors.append(f"missing_required:mid-decode-sigterm-probe/attempt-{index:02d}/{tag}")
        before_faults = fault_lines(before_path.read_text(encoding="utf-8", errors="replace")) if before_path.is_file() else []
        after_faults = fault_lines(after_path.read_text(encoding="utf-8", errors="replace")) if after_path.is_file() else []
        for key in ("gpu_faults_before", "gpu_faults_after", "gpu_faults_delta"):
            if not isinstance(attempt.get(key), int) or isinstance(attempt.get(key), bool):
                errors.append(f"{label}_{key}_not_int")
        if isinstance(attempt.get("gpu_faults_before"), int) and len(before_faults) != attempt.get("gpu_faults_before"):
            errors.append(f"{label}_gpu_faults_before_text_mismatch")
        if isinstance(attempt.get("gpu_faults_after"), int) and len(after_faults) != attempt.get("gpu_faults_after"):
            errors.append(f"{label}_gpu_faults_after_text_mismatch")
        if after_faults[:len(before_faults)] != before_faults:
            errors.append(f"{label}_kernel_window_not_superset")
        recomputed_delta = len(after_faults) - len(before_faults)
        if recomputed_delta != 0:
            errors.append(f"{label}_recomputed_gpu_faults_delta_nonzero:{recomputed_delta}")
        if before_faults:
            errors.append(f"{label}_panfrost_faults_present_before:{len(before_faults)}")
        if after_faults:
            errors.append(f"{label}_panfrost_faults_present_after:{len(after_faults)}")
        if attempt.get("gpu_faults_delta") != recomputed_delta:
            errors.append(f"{label}_gpu_faults_delta_text_mismatch")
        expected_new = [sanitize_kernel_line(ln) for ln in after_faults[len(before_faults):]][:20]
        if attempt.get("new_fault_lines_sanitized") != expected_new:
            errors.append(f"{label}_new_fault_lines_sanitized_mismatch")
        samples = load_ndjson(samples_path, errors, f"{label}_decode_samples")
        recomputed = recompute_mid_decode(samples, summary_boot_id=summary_boot_id,
                                          signal_monotonic=signal_m if _finite_number(signal_m) else None)
        observed = attempt.get("decode_confirm")
        if not isinstance(observed, dict):
            errors.append(f"{label}_decode_confirm_missing")
        else:
            for key in ("confirmed", "samples_n", "frame_first", "frame_last",
                        "time_pos_first", "time_pos_last", "hwdec_current",
                        "last_sample_monotonic", "last_sample_to_signal_sec",
                        "mid_decode_margin_sec"):
                if not _rounded_match(recomputed.get(key), observed.get(key)):
                    errors.append("mid_decode_probe_decode_claim_text_mismatch")
                    break
            if observed.get("confirmed") is not True:
                errors.append(f"{label}_decode_not_confirmed")
        pid_chain = attempt.get("pid_chain")
        if not isinstance(pid_chain, dict):
            errors.append(f"{label}_pid_chain_missing")
        else:
            presignal = pid_chain.get("pre_signal")
            if not isinstance(presignal, dict):
                errors.append(f"{label}_pid_chain_pre_signal_missing")
            else:
                if presignal.get("exe") != EXPECTED_MPV_EXE:
                    errors.append(f"{label}_pid_chain_exe_mismatch")
                if presignal.get("cmdline_contains_ipc_path") is not True:
                    errors.append(f"{label}_pid_chain_cmdline_ipc_missing")
                if presignal.get("pgid_is_pid") is not True:
                    errors.append(f"{label}_pid_chain_pgid_not_pid")
        mpv_exit = attempt.get("mpv_exit")
        if not isinstance(mpv_exit, dict):
            errors.append(f"{label}_mpv_exit_missing")
        else:
            if mpv_exit.get("exited") is not True:
                errors.append(f"{label}_mpv_not_exited")
            if mpv_exit.get("escalated") is not False:
                errors.append("mid_decode_probe_mpv_escalated_after_sigterm")
        if attempt.get("kiosk_killed_before_signal") is not True:
            errors.append(f"{label}_kiosk_not_killed_before_signal")
    validate_health(
        load_json(
            run_dir / "mid-decode-sigterm-probe" / "post-restore-health" / "playback-deep-health-public.json",
            errors,
            "mid_decode_post_restore_health",
        ),
        "mid_decode_post_restore_health",
        errors,
    )
    restore = load_json(run_dir / "mid-decode-sigterm-probe" / "service-restore.json", errors, "mid_decode_service_restore")
    if restore.get("active") is not True:
        errors.append("mid_decode_probe_service_not_active_after_restore")
    if restore.get("deep_health_passed") is not True:
        errors.append("mid_decode_probe_restore_deep_health_not_passed")
    if restore.get("pre_start_barrier_passed") is not True:
        errors.append("mid_decode_probe_restore_barrier_not_passed")


def validate_postcheck(run_dir: Path, errors: list[str]) -> None:
    postcheck = run_dir / "postcheck.txt"
    if not postcheck.is_file():
        errors.append("postcheck_missing")
        return
    text = postcheck.read_text(encoding="utf-8", errors="replace")
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in POSTCHECK_REQUIRED and key in parsed:
            errors.append(f"postcheck_duplicate_key:{key}")
        parsed[key] = value.strip()
    for key, expected in POSTCHECK_REQUIRED.items():
        if key not in parsed:
            errors.append(f"postcheck_missing:{key}")
        elif expected is None:
            if not parsed[key]:
                errors.append(f"postcheck_empty:{key}")
        elif parsed[key] != expected:
            errors.append(f"postcheck_value:{key}={parsed[key]}!={expected}")


def validate_semantics(run_dir: Path, manifest: dict[str, Any], errors: list[str]) -> None:
    summary = load_json(run_dir / "teardown-summary.json", errors, "teardown_summary")
    if summary.get("schema") != TRIAL_SCHEMA:
        errors.append("summary_schema")
    if summary.get("passed") is not True:
        errors.append("summary_not_passed")
    summary_boot_id = summary.get("boot_id")
    if not isinstance(summary_boot_id, str) or not summary_boot_id:
        errors.append("summary_boot_id_missing")
        summary_boot_id = ""
    if not isinstance(summary.get("btime"), int):
        errors.append("summary_btime_missing")

    cycles = summary.get("cycles")
    if not isinstance(cycles, list):
        errors.append("summary_cycles_missing")
        cycles = []
    cycles_count = summary.get("cycles_count")
    if cycles_count != len(cycles):
        errors.append("summary_cycles_count_mismatch")
    if len(cycles) < MIN_CYCLES:
        errors.append(f"too_few_cycles:{len(cycles)}<{MIN_CYCLES}")

    # The cycle dirs must be exactly cycle-00..cycle-(N-1), consecutive.
    cycles_root = run_dir / "cycles"
    present_dirs = sorted(
        p.name for p in cycles_root.iterdir()
        if cycles_root.is_dir() and p.is_dir() and p.name.startswith("cycle-")
    ) if cycles_root.is_dir() else []
    expected_dirs = [f"cycle-{i:02d}" for i in range(len(cycles))]
    if present_dirs != expected_dirs:
        errors.append(f"cycle_dirs_mismatch:{present_dirs}!={expected_dirs}")

    kinds_by_index: dict[int, str] = {}
    cycle_windows: list[tuple[int, Any, Any]] = []
    for index in range(len(cycles)):
        cycle_dir = f"cycles/cycle-{index:02d}"
        if not (run_dir / cycle_dir / "cycle.json").is_file():
            errors.append(f"missing_required:{cycle_dir}/cycle.json")
            continue
        summary_cycle = cycles[index] if index < len(cycles) and isinstance(cycles[index], dict) else {}
        info = validate_cycle(run_dir, cycle_dir, index, summary_boot_id, summary_cycle, errors)
        if info["kind"]:
            kinds_by_index[index] = info["kind"]
        cycle_windows.append((index, info["monotonic_before"], info["monotonic_after"]))

    # GR3: >=1 cycle must exercise the real service restart path, and every
    # declared restart index must actually point at a service_restart cycle.
    restart_indices = summary.get("service_restart_cycle_indices")
    if not isinstance(restart_indices, list) or not restart_indices:
        errors.append("no_service_restart_cycle")
    else:
        for idx in restart_indices:
            if not isinstance(idx, int) or isinstance(idx, bool) or not (0 <= idx < len(cycles)):
                errors.append(f"service_restart_index_out_of_range:{idx}")
            elif kinds_by_index.get(idx) != "service_restart":
                errors.append(f"service_restart_index_kind_mismatch:{idx}")
    if "service_restart" not in kinds_by_index.values():
        errors.append("no_service_restart_cycle_kind")

    # GR1 temporal integrity: cycles must be sequential, non-overlapping windows
    # in one boot (rejects a single teardown duplicated as two, or reversed order).
    ordered = [(i, mb, ma) for (i, mb, ma) in cycle_windows
               if isinstance(mb, (int, float)) and isinstance(ma, (int, float))]
    for (i_a, _mb_a, ma_a), (i_b, mb_b, _ma_b) in zip(ordered, ordered[1:]):
        # Strictly increasing, NON-touching windows: cycle[i] must fully finish
        # before cycle[i+1] begins (rejects duplicated/zero-gap/reversed windows).
        if ma_a >= mb_b:
            errors.append(f"cycle_windows_overlap_or_reversed:{i_a}->{i_b}")

    validate_fresh_ipc_probe(run_dir, summary, errors)
    validate_mid_decode_probe(run_dir, summary, cycle_windows, summary_boot_id, errors)
    validate_postcheck(run_dir, errors)

    non_claims = summary.get("non_claims")
    if not isinstance(non_claims, list) or not any("GR4b" in str(item) for item in non_claims):
        errors.append("summary_non_claims_missing")


def validate(run_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    files: list[str] = []
    if not run_dir.is_dir():
        return {"schema": SCHEMA, "passed": False, "errors": [f"run_dir_not_found:{run_dir}"], "files": []}
    try:
        files = validate_files(run_dir, errors)
        manifest = validate_manifest(run_dir, files, errors)
        require_files(run_dir, ["teardown-summary.json", "postcheck.txt"], errors)
        validate_semantics(run_dir, manifest, errors)
    except Exception as exc:  # a crash must never read as benign for library callers
        errors.append(f"internal_error:{type(exc).__name__}")
    return {
        "schema": SCHEMA,
        "passed": not errors,
        "errors": errors,
        "run_dir": str(run_dir),
        "files": sorted(files),
    }


# --------------------------------------------------------------------------- #
# Self-test: a passing fixture plus fail-closed tamper cases.                  #
# --------------------------------------------------------------------------- #
def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def make_health() -> dict[str, Any]:
    return {
        "schema": PLAYBACK_SCHEMA,
        "passed": True,
        "failure_reasons": [],
        "checks": {key: True for key in HEALTH_CHECKS},
    }


def make_cycle(index: int, kind: str, boot_id: str) -> dict[str, Any]:
    return {
        "schema": CYCLE_SCHEMA,
        "index": index,
        "kind": kind,
        "boot_id": boot_id,
        "gpu_faults_before": 0,
        "gpu_faults_after": 0,
        "gpu_faults_delta": 0,
        "gpu_faults_delta_anomalous": False,
        "window_anchor": {
            "boot_id": boot_id,
            "monotonic_before": 100.0 + index * 10,
            "monotonic_after": 102.0 + index * 10,
        },
        "stop": {"method": "ipc_quit", "returncode": 0, "elapsed_ms": 420},
        "process_exited": True,
        "new_fault_lines_sanitized": [],
        "passed": True,
    }


def write_fixture(root: Path, *, with_fresh_ipc: bool = True) -> None:
    boot_id = "00000000-0000-4000-8000-000000000000"
    cycle_defs = [(0, "relaunch"), (1, "service_restart")]
    cycles_summary = []
    for index, kind in cycle_defs:
        cycle = make_cycle(index, kind, boot_id)
        write_json(root / f"cycles/cycle-{index:02d}/cycle.json", cycle)
        write_json(root / f"cycles/cycle-{index:02d}/health/playback-deep-health-public.json", make_health())
        (root / f"cycles/cycle-{index:02d}/kernel-before.txt").write_text("boot start\n", encoding="utf-8")
        (root / f"cycles/cycle-{index:02d}/kernel-after.txt").write_text("boot start\n", encoding="utf-8")
        cycles_summary.append({k: cycle[k] for k in ("index", "kind", "gpu_faults_delta", "passed")})
    write_json(root / "setup/service-state-before.json", {"is_active": "active", "is_enabled": "enabled"})
    summary = {
        "schema": TRIAL_SCHEMA,
        "passed": True,
        "boot_id": boot_id,
        "btime": 1700000000,
        "cycles_count": len(cycles_summary),
        "service_restart_cycle_indices": [1],
        "cycles": cycles_summary,
        "gr4_secondary_present": with_fresh_ipc,
        "non_claims": [
            "GR4b fresh-IPC quit SUCCESS against a live socket is NOT claimed.",
            "Soak/endurance, torn-write power-loss, server-side publish, and public thaw are NOT claimed.",
        ],
    }
    write_json(root / "teardown-summary.json", summary)
    if with_fresh_ipc:
        write_json(root / "fresh_ipc_probe.json", {
            "schema": FRESH_IPC_SCHEMA,
            "forced_ipc_none": True,
            "forcing_method": "short_mpv_startup_timeout_sec",
            "code_path_reached": True,
            "observed_log": "MPV IPC fresh command failed command=quit",
            "outcome": "fresh_failed_fallback_sigterm",
            "process_exited": True,
            "non_claim": "GR4b (fresh-IPC quit SUCCESS vs a live socket) is NOT proven; secondary corner only.",
        })
    (root / "postcheck.txt").write_text(
        "BOOT_ID=00000000-0000-4000-8000-000000000000\nUPTIME=42.0\n"
        "SERVICE_ACTIVE=active\nTIMER_ENABLED=disabled\nSTRICT_GPU_FAULTS=0\n"
        "PUBLIC_PLAYER_RUNTIME_APPLY_LOCAL_RC=44\nPUBLIC_PLAYER_RUNTIME_ROLLBACK_RC=44\n"
        "PUBLIC_PLAYER_RUNTIME_RECONCILE_RC=44\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text("# c18 teardown fixture\n", encoding="utf-8")
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
        "artifact_id": "teardown-fixture",
        "component": "player-runtime",
        "board_image_marker": "c18-fixture",
        "source_commit": "a" * 40,
        "files": files,
    })


def add_mid_decode_fixture(root: Path) -> None:
    summary = json.loads((root / "teardown-summary.json").read_text(encoding="utf-8"))
    summary["mid_decode_probe_present"] = True
    write_json(root / "teardown-summary.json", summary)
    probe_dir = root / "mid-decode-sigterm-probe"
    attempt_dir = probe_dir / "attempt-00"
    samples = [
        {
            "boot_id": summary["boot_id"],
            "monotonic": 130.0,
            "ipc_result": "success",
            "ipc_error": "",
            "ipc_elapsed_ms": 2,
            "estimated_frame_number": 100,
            "time_pos": 10.0,
            "duration": 60.0,
            "hwdec_current": EXPECTED_HWDEC,
            "vo_configured": True,
            "idle_active": False,
            "pause": False,
            "eof_reached": False,
        },
        {
            "boot_id": summary["boot_id"],
            "monotonic": 130.6,
            "ipc_result": "success",
            "ipc_error": "",
            "ipc_elapsed_ms": 2,
            "estimated_frame_number": 120,
            "time_pos": 10.7,
            "duration": 60.0,
            "hwdec_current": EXPECTED_HWDEC,
            "vo_configured": True,
            "idle_active": False,
            "pause": False,
            "eof_reached": False,
        },
        {
            "boot_id": summary["boot_id"],
            "monotonic": 131.2,
            "ipc_result": "success",
            "ipc_error": "",
            "ipc_elapsed_ms": 2,
            "estimated_frame_number": 140,
            "time_pos": 11.4,
            "duration": 60.0,
            "hwdec_current": EXPECTED_HWDEC,
            "vo_configured": True,
            "idle_active": False,
            "pause": False,
            "eof_reached": False,
        },
    ]
    attempt_dir.mkdir(parents=True, exist_ok=True)
    with (attempt_dir / "decode-samples.ndjson").open("w", encoding="utf-8") as fh:
        for row in samples:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (attempt_dir / "kernel-before.txt").write_text("boot clean\n", encoding="utf-8")
    (attempt_dir / "kernel-after.txt").write_text("boot clean\n", encoding="utf-8")
    (attempt_dir / "probe-kiosk-log-tail.txt").write_text("MPV process started pid=123\n", encoding="utf-8")
    signal_m = 131.4
    recomputed = recompute_mid_decode(samples, summary_boot_id=summary["boot_id"], signal_monotonic=signal_m)
    write_json(root / "mid_decode_sigterm_probe.json", {
        "schema": MID_DECODE_SCHEMA,
        "passed": True,
        "claim": "mid_decode_sigterm_panfrost_window_measured",
        "kiosk_killed_before_signal": True,
        "cfg_hwdec": "auto",
        "wrapper": {"path": EXPECTED_WRAPPER, "sha256": "b" * 64},
        "production_service": {"stopped": True, "restored": True, "deep_health_passed": True},
        "attempts": [
            {
                "index": 0,
                "passed": True,
                "failure_reasons": [],
                "window_anchor": {
                    "boot_id": summary["boot_id"],
                    "monotonic_before": 131.3,
                    "monotonic_after": 134.0,
                },
                "pid_chain": {
                    "pre_signal": {
                        "pid": 123,
                        "exe": EXPECTED_MPV_EXE,
                        "cmdline_contains_ipc_path": True,
                        "pgid_is_pid": True,
                        "starttime": 999,
                    }
                },
                "decode_confirm": recomputed,
                "signal": {
                    "name": "SIGTERM",
                    "target": "mpv_pgid",
                    "delivered": True,
                    "monotonic": signal_m,
                },
                "mpv_exit": {"exited": True, "waited_ms": 500, "escalated": False},
                "kiosk_killed_before_signal": True,
                "gpu_faults_before": 0,
                "gpu_faults_after": 0,
                "gpu_faults_delta": 0,
                "gpu_faults_delta_anomalous": False,
                "new_fault_lines_sanitized": [],
            }
        ],
        "non_claims": [
            "GR4b fresh-IPC quit SUCCESS against a live socket is NOT claimed.",
            "healthy-not-wedged: this probe measures a healthy decoding mpv.",
            "no-kiosk-alive: IPC quit, watchdog, waitpid, and auto-relaunch are NOT in this probe window.",
            "production-timing-unmeasured: exact production timing is NOT claimed.",
            "N=1 single-image",
        ],
    })
    write_json(probe_dir / "service-restore.json", {
        "active": True,
        "deep_health_passed": True,
        "pre_start_barrier_passed": True,
        "probe_orphans_killed": 0,
        "reset_failed_used": False,
    })
    write_json(probe_dir / "post-restore-health" / "playback-deep-health-public.json", make_health())
    _reseal_manifest(root)


def _reseal_manifest(root: Path) -> None:
    """Re-hash all files into the manifest (used by tamper tests that legitimately edit a file)."""
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "evidence-manifest.json":
            files.append({
                "file": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    manifest = json.loads((root / "evidence-manifest.json").read_text(encoding="utf-8"))
    manifest["files"] = files
    write_json(root / "evidence-manifest.json", manifest)


class TeardownEvidenceGateSelfTest(unittest.TestCase):
    def _fixture(self, tmp: str) -> Path:
        root = Path(tmp)
        write_fixture(root)
        return root

    def test_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(validate(self._fixture(tmp))["passed"])

    def test_fixture_without_fresh_ipc_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root, with_fresh_ipc=False)
            self.assertTrue(validate(root)["passed"])

    def test_fixture_with_mid_decode_probe_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            add_mid_decode_fixture(root)
            result = validate(root)
            self.assertTrue(result["passed"], msg=result["errors"])

    def test_mid_decode_presence_xor_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            add_mid_decode_fixture(root)
            summary = json.loads((root / "teardown-summary.json").read_text())
            summary.pop("mid_decode_probe_present", None)
            write_json(root / "teardown-summary.json", summary)
            self._assert_fails(root, "mid_decode_probe_presence_mismatch")

    def test_mid_decode_extra_attempt_dir_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            add_mid_decode_fixture(root)
            extra = root / "mid-decode-sigterm-probe/attempt-01"
            extra.mkdir(parents=True)
            (extra / "kernel-before.txt").write_text("boot clean\n", encoding="utf-8")
            (extra / "kernel-after.txt").write_text("panfrost gpu fault: Unhandled Page fault\n", encoding="utf-8")
            (extra / "decode-samples.ndjson").write_text("", encoding="utf-8")
            self._assert_fails(root, "mid_decode_probe_attempt_dirs_mismatch")

    def test_mid_decode_signal_outside_window_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            add_mid_decode_fixture(root)
            probe = json.loads((root / "mid_decode_sigterm_probe.json").read_text())
            probe["attempts"][0]["signal"]["monotonic"] = 140.0
            write_json(root / "mid_decode_sigterm_probe.json", probe)
            self._assert_fails(root, "signal_monotonic_outside_window")

    def test_mid_decode_ndjson_nan_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            add_mid_decode_fixture(root)
            samples = root / "mid-decode-sigterm-probe/attempt-00/decode-samples.ndjson"
            text = samples.read_text(encoding="utf-8").replace("10.7", "NaN", 1)
            samples.write_text(text, encoding="utf-8")
            self._assert_fails(root, "ndjson")

    def test_mid_decode_hwdec_substring_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            add_mid_decode_fixture(root)
            samples = root / "mid-decode-sigterm-probe/attempt-00/decode-samples.ndjson"
            text = samples.read_text(encoding="utf-8").replace(EXPECTED_HWDEC, "v4l2request")
            samples.write_text(text, encoding="utf-8")
            self._assert_fails(root, "mid_decode_probe_decode_claim_text_mismatch")

    def test_mid_decode_escalation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            add_mid_decode_fixture(root)
            probe = json.loads((root / "mid_decode_sigterm_probe.json").read_text())
            probe["attempts"][0]["mpv_exit"]["escalated"] = True
            write_json(root / "mid_decode_sigterm_probe.json", probe)
            self._assert_fails(root, "mid_decode_probe_mpv_escalated_after_sigterm")

    def test_mid_decode_restore_barrier_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            add_mid_decode_fixture(root)
            restore = json.loads((root / "mid-decode-sigterm-probe/service-restore.json").read_text())
            restore["pre_start_barrier_passed"] = False
            write_json(root / "mid-decode-sigterm-probe/service-restore.json", restore)
            self._assert_fails(root, "mid_decode_probe_restore_barrier_not_passed")

    def _assert_fails(self, root: Path, needle: str) -> None:
        _reseal_manifest(root)
        result = validate(root)
        self.assertFalse(result["passed"])
        self.assertTrue(
            any(needle in e for e in result["errors"]),
            msg=f"expected an error containing {needle!r}, got {result['errors']}",
        )

    def test_too_few_cycles_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            # Remove cycle-01 dir + its summary entry.
            import shutil
            shutil.rmtree(root / "cycles/cycle-01")
            summary = json.loads((root / "teardown-summary.json").read_text())
            summary["cycles"] = summary["cycles"][:1]
            summary["cycles_count"] = 1
            summary["service_restart_cycle_indices"] = []
            write_json(root / "teardown-summary.json", summary)
            self._assert_fails(root, "too_few_cycles")

    def test_cross_boot_cycle_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            cycle = json.loads((root / "cycles/cycle-01/cycle.json").read_text())
            cycle["boot_id"] = "ffffffff-ffff-4fff-8fff-ffffffffffff"
            cycle["window_anchor"]["boot_id"] = cycle["boot_id"]
            write_json(root / "cycles/cycle-01/cycle.json", cycle)
            self._assert_fails(root, "boot_id_not_same_boot")

    def test_nonzero_delta_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            cycle = json.loads((root / "cycles/cycle-00/cycle.json").read_text())
            cycle["gpu_faults_after"] = 4
            cycle["gpu_faults_delta"] = 1
            write_json(root / "cycles/cycle-00/cycle.json", cycle)
            self._assert_fails(root, "gpu_faults_delta_nonzero")

    def test_negative_delta_unflagged_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            cycle = json.loads((root / "cycles/cycle-00/cycle.json").read_text())
            # Simulate journal rotation: after < before, delta negative, NOT flagged anomalous.
            cycle["gpu_faults_before"] = 5
            cycle["gpu_faults_after"] = 2
            cycle["gpu_faults_delta"] = -3
            cycle["gpu_faults_delta_anomalous"] = False
            write_json(root / "cycles/cycle-00/cycle.json", cycle)
            self._assert_fails(root, "negative_delta_not_flagged_anomalous")

    def test_anomalous_delta_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            cycle = json.loads((root / "cycles/cycle-00/cycle.json").read_text())
            cycle["gpu_faults_delta_anomalous"] = True
            write_json(root / "cycles/cycle-00/cycle.json", cycle)
            self._assert_fails(root, "gpu_faults_delta_anomalous")

    def test_no_service_restart_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            cycle = json.loads((root / "cycles/cycle-01/cycle.json").read_text())
            cycle["kind"] = "relaunch"
            write_json(root / "cycles/cycle-01/cycle.json", cycle)
            summary = json.loads((root / "teardown-summary.json").read_text())
            summary["cycles"][1]["kind"] = "relaunch"
            summary["service_restart_cycle_indices"] = []
            write_json(root / "teardown-summary.json", summary)
            self._assert_fails(root, "no_service_restart_cycle")

    def test_process_not_exited_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            cycle = json.loads((root / "cycles/cycle-00/cycle.json").read_text())
            cycle["process_exited"] = False
            write_json(root / "cycles/cycle-00/cycle.json", cycle)
            self._assert_fails(root, "process_not_exited")

    def test_health_check_failed_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            health = make_health()
            health["checks"]["panfrost_faults_delta_zero"] = False
            write_json(root / "cycles/cycle-00/health/playback-deep-health-public.json", health)
            self._assert_fails(root, "check_failed:panfrost_faults_delta_zero")

    def test_summary_cycle_binding_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            summary = json.loads((root / "teardown-summary.json").read_text())
            summary["cycles"][0]["gpu_faults_delta"] = 7  # disagree with cycle.json
            write_json(root / "teardown-summary.json", summary)
            self._assert_fails(root, "summary_cycle_gpu_faults_delta_mismatch")

    def test_fresh_sent_claim_rejected(self) -> None:
        # The fresh-IPC SUCCESS path is unreachable in production; a consistent
        # "fresh_sent" claim (matching log) must still be rejected as an overclaim.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            probe = json.loads((root / "fresh_ipc_probe.json").read_text())
            probe["outcome"] = "fresh_sent"
            probe["observed_log"] = "MPV IPC fresh command sent command=quit"
            write_json(root / "fresh_ipc_probe.json", probe)
            self._assert_fails(root, "fresh_ipc_probe_success_path_unreachable_claim")

    def test_injected_fault_in_kernel_after_fails(self) -> None:
        # RED-TEAM #1/#3/#5: a real panfrost fault in kernel-after.txt while
        # cycle.json still claims delta==0 must be caught by the recompute.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            (root / "cycles/cycle-01/kernel-after.txt").write_text(
                "kernel: panfrost fa00000.gpu: Unhandled Page fault in AS0 at VA 0xC0FFEE\n",
                encoding="utf-8")
            self._assert_fails(root, "cycle01_recomputed_gpu_faults_delta_nonzero")

    def test_missing_kernel_after_file_fails(self) -> None:
        # RED-TEAM #2(L)/#5: deleting the journal evidence must fail closed.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            (root / "cycles/cycle-00/kernel-after.txt").unlink()
            self._assert_fails(root, "missing_required:cycles/cycle-00/kernel-after.txt")

    def test_kernel_count_mismatch_fails(self) -> None:
        # RED-TEAM #5(kgarbage): kernel text disagreeing with the claimed count.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            cycle = json.loads((root / "cycles/cycle-00/cycle.json").read_text())
            cycle["gpu_faults_before"] = 3
            cycle["gpu_faults_after"] = 3  # but kernel text has 0 fault lines
            write_json(root / "cycles/cycle-00/cycle.json", cycle)
            summary = json.loads((root / "teardown-summary.json").read_text())
            write_json(root / "teardown-summary.json", summary)
            self._assert_fails(root, "gpu_faults_before_text_mismatch")

    def test_service_restart_index_wrong_kind_fails(self) -> None:
        # RED-TEAM #2(D): restart index pointing at a relaunch cycle.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            summary = json.loads((root / "teardown-summary.json").read_text())
            summary["service_restart_cycle_indices"] = [0]  # cycle-00 is a relaunch
            write_json(root / "teardown-summary.json", summary)
            self._assert_fails(root, "service_restart_index_kind_mismatch")

    def test_overlapping_windows_fails(self) -> None:
        # RED-TEAM #2(I): one teardown duplicated as two via identical windows.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            for idx in (0, 1):
                cycle = json.loads((root / f"cycles/cycle-{idx:02d}/cycle.json").read_text())
                cycle["window_anchor"]["monotonic_before"] = 500.0
                cycle["window_anchor"]["monotonic_after"] = 502.0
                write_json(root / f"cycles/cycle-{idx:02d}/cycle.json", cycle)
            self._assert_fails(root, "cycle_windows_overlap_or_reversed")

    def test_reversed_windows_fails(self) -> None:
        # RED-TEAM #2(J): the second teardown happened before the first.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            c1 = json.loads((root / "cycles/cycle-01/cycle.json").read_text())
            c1["window_anchor"]["monotonic_before"] = 1.0
            c1["window_anchor"]["monotonic_after"] = 3.0  # before cycle-00's window
            write_json(root / "cycles/cycle-01/cycle.json", c1)
            self._assert_fails(root, "cycle_windows_overlap_or_reversed")

    # ---- Second-pass red-team regressions ---------------------------------- #
    def test_broadened_regex_catches_missed_fault_wordings(self) -> None:
        # RED-TEAM 2 #F1: real GPU teardown faults whose wording the original
        # regex missed (panfrost job/scheduler timeout, job hung, lima mmu fault).
        wordings = [
            "kernel: panfrost fa00000.gpu: job timeout, js=0 during teardown",
            "kernel: panfrost fa00000.gpu: Scheduler timeout, job hung on GPU after teardown",
            "kernel: lima 1c40000.gpu: mmu page fault at 0x0 from job",
            "kernel: panfrost fa00000.gpu: GPU lockup detected",
            # Round-3 regression: inflected stems must match (no trailing \b), and
            # the matcher must be a superset of the deep-health collector.
            "kernel: panfrost fb000000.gpu: resetting GPU after teardown",
            "kernel: panfrost fb000000.gpu: 3 GPU faults during teardown, resetting GPU",
        ]
        for wording in wordings:
            with tempfile.TemporaryDirectory() as tmp:
                root = self._fixture(tmp)
                (root / "cycles/cycle-01/kernel-after.txt").write_text(wording + "\n", encoding="utf-8")
                self._assert_fails(root, "cycle01_panfrost_faults_present_after")

    def test_persistent_fault_both_windows_fails(self) -> None:
        # RED-TEAM 2 #F3: a persistent panfrost fault present in BOTH windows
        # (before==after>0, delta 0) while health lies panfrost_faults_zero:true.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            fault_text = ("kernel: panfrost fa00000.gpu: Unhandled Page fault in AS0 at VA 0xC0FFEE\n"
                          "kernel: panfrost fa00000.gpu: gpu sched timeout, js=0\n")
            (root / "cycles/cycle-00/kernel-before.txt").write_text(fault_text, encoding="utf-8")
            (root / "cycles/cycle-00/kernel-after.txt").write_text(fault_text, encoding="utf-8")
            cycle = json.loads((root / "cycles/cycle-00/cycle.json").read_text())
            cycle["gpu_faults_before"] = 2
            cycle["gpu_faults_after"] = 2  # delta still 0; health left claiming zero
            write_json(root / "cycles/cycle-00/cycle.json", cycle)
            self._assert_fails(root, "cycle00_panfrost_faults_present")

    def test_zero_width_photocopy_windows_fails(self) -> None:
        # RED-TEAM 2 #F2: a single instant photocopied into N "cycles" via [T,T].
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            for idx in (0, 1):
                cycle = json.loads((root / f"cycles/cycle-{idx:02d}/cycle.json").read_text())
                cycle["window_anchor"]["monotonic_before"] = 555.0
                cycle["window_anchor"]["monotonic_after"] = 555.0
                write_json(root / f"cycles/cycle-{idx:02d}/cycle.json", cycle)
            self._assert_fails(root, "window_anchor_zero_or_negative_width")

    def test_touching_windows_fails(self) -> None:
        # Cross-cycle: cycle[i].after == cycle[i+1].before (zero gap) is rejected.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            c0 = json.loads((root / "cycles/cycle-00/cycle.json").read_text())
            c1 = json.loads((root / "cycles/cycle-01/cycle.json").read_text())
            c0["window_anchor"]["monotonic_before"] = 100.0
            c0["window_anchor"]["monotonic_after"] = 110.0
            c1["window_anchor"]["monotonic_before"] = 110.0  # touches c0's end
            c1["window_anchor"]["monotonic_after"] = 120.0
            write_json(root / "cycles/cycle-00/cycle.json", c0)
            write_json(root / "cycles/cycle-01/cycle.json", c1)
            self._assert_fails(root, "cycle_windows_overlap_or_reversed")

    def test_nan_window_anchor_fails(self) -> None:
        # RED-TEAM 3 #F2: NaN monotonics compare False to everything and would
        # evade the strict window guards. They must be rejected.
        for bad in (float("nan"), float("inf")):
            with tempfile.TemporaryDirectory() as tmp:
                root = self._fixture(tmp)
                for idx in (0, 1):
                    cycle = json.loads((root / f"cycles/cycle-{idx:02d}/cycle.json").read_text())
                    cycle["window_anchor"]["monotonic_before"] = bad
                    cycle["window_anchor"]["monotonic_after"] = bad
                    write_json(root / f"cycles/cycle-{idx:02d}/cycle.json", cycle)
                _reseal_manifest(root)
                result = validate(root)
                self.assertFalse(result["passed"])

    def test_non_int_delta_fails_without_crash(self) -> None:
        # RED-TEAM 2 #F3-secondary: a string/None delta must fail cleanly, not crash.
        for bad in ("not-a-number", None):
            with tempfile.TemporaryDirectory() as tmp:
                root = self._fixture(tmp)
                cycle = json.loads((root / "cycles/cycle-00/cycle.json").read_text())
                cycle["gpu_faults_delta"] = bad
                write_json(root / "cycles/cycle-00/cycle.json", cycle)
                _reseal_manifest(root)
                result = validate(root)  # must return a dict, never raise
                self.assertFalse(result["passed"])
                self.assertTrue(any("gpu_faults_delta_not_int" in e for e in result["errors"]))
                self.assertFalse(any(e.startswith("internal_error") for e in result["errors"]))

    def test_hash_tamper_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            # Edit a file WITHOUT resealing the manifest -> sha mismatch.
            (root / "README.md").write_text("# tampered\n", encoding="utf-8")
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertTrue(any("manifest_sha256_mismatch" in e for e in result["errors"]))

    def test_undeclared_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            (root / "stray.txt").write_text("extra\n", encoding="utf-8")
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertTrue(any("manifest_undeclared_file" in e for e in result["errors"]))

    def test_secret_leak_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            (root / "cycles/cycle-00/kernel-after.txt").write_text(
                "ghp_abcdefghijklmnopqrstuvwxyz0123\n", encoding="utf-8")
            self._assert_fails(root, "secret_pattern:github_token")

    def test_missing_required_summary_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            (root / "teardown-summary.json").unlink()
            result = validate(root)
            self.assertFalse(result["passed"])
            self.assertTrue(any("missing_required:teardown-summary.json" in e for e in result["errors"]))

    def test_postcheck_missing_freeze_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            (root / "postcheck.txt").write_text(
                "BOOT_ID=x\nUPTIME=1\nSERVICE_ACTIVE=active\nTIMER_ENABLED=disabled\nSTRICT_GPU_FAULTS=0\n",
                encoding="utf-8")
            self._assert_fails(root, "postcheck_missing:PUBLIC_PLAYER_RUNTIME_ROLLBACK_RC")

    def test_postcheck_value_poisoning_fails(self) -> None:
        # FINAL SWEEP: suffix-poisoned values that still "contain" the token must
        # fail (exact KEY=VALUE parsing, not substring containment).
        poisons = [
            ("STRICT_GPU_FAULTS=0", "STRICT_GPU_FAULTS=05"),
            ("PUBLIC_PLAYER_RUNTIME_ROLLBACK_RC=44", "PUBLIC_PLAYER_RUNTIME_ROLLBACK_RC=440"),
            ("TIMER_ENABLED=disabled", "TIMER_ENABLED=disabled-but-armed"),
            ("SERVICE_ACTIVE=active", "SERVICE_ACTIVE=active-but-failed"),
        ]
        for good, bad in poisons:
            with tempfile.TemporaryDirectory() as tmp:
                root = self._fixture(tmp)
                text = (root / "postcheck.txt").read_text().replace(good, bad)
                (root / "postcheck.txt").write_text(text, encoding="utf-8")
                self._assert_fails(root, "postcheck_value")

    def test_postcheck_duplicate_key_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp)
            text = (root / "postcheck.txt").read_text() + "STRICT_GPU_FAULTS=5\n"
            (root / "postcheck.txt").write_text(text, encoding="utf-8")
            self._assert_fails(root, "postcheck_duplicate_key:STRICT_GPU_FAULTS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate C18 player-runtime HW teardown/panfrost evidence.")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TeardownEvidenceGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if args.run_dir is None:
        raise SystemExit("--run-dir is required unless --self-test is used")
    result = validate(args.run_dir)
    print(json.dumps(result, indent=2 if args.json else None, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
