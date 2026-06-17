#!/usr/bin/env python3
"""Validate C18 OTA scale governance before 24h soak/H2 production.

This is an offline aggregate gate for the pre-soak state. It proves the C18 OTA
governance model is coherent across the responsibility fronts, while keeping
production, stable, auto-pull and public player-runtime thaw blocked until H2.
It does not run SSH, apply updates, publish releases, promote stable, enable
auto-pull, collect soak, complete power-loss 17/17 or thaw player-runtime.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.ota_pre_soak_scale_governance_gate.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_PACKAGE_VERSION = "c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1"
TARGET_SOURCE_COMMIT = "9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522"
TARGET_PAYLOAD_SHA256 = "d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0"
TARGET_CHANNEL = "homologation"
TARGET_RING = "pilot"
H2_POWERLOSS_PREFLIGHT_MAX_AGE_SEC = 4 * 60 * 60
EXPECTED_H2_BLOCKERS = (
    "full_physical_powerloss_matrix:powerloss_matrix_incomplete",
    "soak_endurance_24h:missing_24h_soak_summary",
    "stable_promotion_authorization:missing_stable_promotion_evidence",
    "explicit_operator_thaw_decision:missing_operator_thaw_decision",
)
DEFAULT_H2_READINESS = (
    REPO_ROOT / "docs/evidence/c18-update-validation/20260617T192101Z-current-h2-readiness-mpv-stuck-fix-9bebaf1/h2-readiness.json"
)
DEFAULT_MACRO_SUMMARY = (
    REPO_ROOT
    / "docs/evidence/c18-update-validation/20260617T064617Z-current-macro-governance-a761a67/macro-governance.json"
)
DEFAULT_SERVER_SIDE_CURRENT_DIR = (
    REPO_ROOT / "docs/evidence/c18-update-validation/20260617T191658Z-server-side-current-mpv-stuck-fix-9bebaf1"
)
DEFAULT_H2_POWERLOSS_PREFLIGHT_DIR = (
    REPO_ROOT
    / "docs/evidence/c18-update-validation/20260617T203659Z-h2-powerloss-board-preflight-refresh-mpv-stuck-fix-9bebaf1"
)
DEFAULT_TARGET_BLOCKING_DIAGNOSTIC_DIRS: tuple[Path, ...] = ()
DEFAULT_DOCS = (
    REPO_ROOT / "docs/product/191_C18_OTA_OPERATING_MODEL.md",
    REPO_ROOT / "docs/product/192_C18_HOMOLOGATION_RC.md",
    REPO_ROOT / "docs/UPDATE_CONTRACT.md",
    REPO_ROOT / "docs/UPDATE_AUTHORIZATION_HEALTH.md",
    REPO_ROOT / "docs/c18-player-runtime-h2-stable-thaw-runbook.md",
)
RESPONSIBILITY_DOC_TOKENS = {
    "totem_core_common_ota": (
        "`totem-core`",
        "OTA C18 comum",
        "allowed_components=[\"totem-core\"]",
    ),
    "player_runtime_governed": (
        "`player-runtime`",
        "`kiosk.py`",
        "channel=homologation",
        "ring=pilot",
    ),
    "kiosky_subordinate_to_player_runtime": (
        "`kiosky-player`",
        "fronteira de `player-runtime`",
        "como `totem-core` operacional",
    ),
    "media_system_image_or_homologation": (
        "`media-system`",
        "MPV",
        "hwdecode",
        "imagem/homologacao propria",
    ),
    "field_data_operational": (
        "`field-data`",
        "config real",
        "snapshot publico",
        "read-only",
    ),
    "server_side_publish_governance": (
        "server-side/signature",
        "allowlist",
        "staged rollout",
        "audit",
    ),
    "h2_prod_blocked": (
        "power-loss 17/17",
        "soak 24h",
        "stable promotion",
        "decisao formal de thaw",
    ),
}
NON_CLAIMS = (
    "this_gate_does_not_authorize_production",
    "this_gate_does_not_promote_stable",
    "this_gate_does_not_enable_auto_pull",
    "this_gate_does_not_publish_releases",
    "this_gate_does_not_thaw_public_player_runtime",
    "this_gate_does_not_satisfy_24h_soak",
    "this_gate_does_not_satisfy_powerloss_17_17",
    "this_gate_does_not_replace_h2_readiness",
    "this_gate_does_not_replace_operational_resume",
)
TRACKED_INPUTS = (
    DEFAULT_H2_READINESS,
    DEFAULT_MACRO_SUMMARY,
    DEFAULT_SERVER_SIDE_CURRENT_DIR,
    DEFAULT_H2_POWERLOSS_PREFLIGHT_DIR,
    *DEFAULT_TARGET_BLOCKING_DIAGNOSTIC_DIRS,
    *DEFAULT_DOCS,
)


def step(passed: bool, blockers: list[str], **details: Any) -> dict[str, Any]:
    return {"passed": passed, "blockers": sorted(set(blockers)), **details}


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any, blockers: list[str], label: str) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        blockers.append(f"{label}_missing")
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        blockers.append(f"{label}_invalid")
        return None
    if parsed.tzinfo is None:
        blockers.append(f"{label}_not_timezone_aware")
        return None
    return parsed.astimezone(dt.timezone.utc)


def read_json(path: Path, blockers: list[str], label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append(f"{label}_json_read_failed:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        blockers.append(f"{label}_not_object")
        return {}
    return data


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_json_command(name: str, cmd: list[str], *, expected_returncodes: set[int]) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=300,
        check=False,
    )
    blockers: list[str] = []
    payload: dict[str, Any] = {}
    if proc.returncode not in expected_returncodes:
        blockers.append(f"{name}_returncode:{proc.returncode}")
    if proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
            if isinstance(parsed, dict):
                payload = parsed
            else:
                blockers.append(f"{name}_stdout_not_object")
        except json.JSONDecodeError:
            blockers.append(f"{name}_stdout_not_json")
    else:
        blockers.append(f"{name}_stdout_empty")
    return step(
        not blockers,
        blockers,
        command=cmd,
        returncode=proc.returncode,
        stdout_tail=proc.stdout[-1200:],
        stderr_tail=proc.stderr[-1200:],
        payload=payload,
    )


def target_blockers(target: dict[str, Any], *, label: str) -> list[str]:
    blockers: list[str] = []
    expected = {
        "package_version": TARGET_PACKAGE_VERSION,
        "source_commit": TARGET_SOURCE_COMMIT,
        "payload_sha256": TARGET_PAYLOAD_SHA256,
        "channel": TARGET_CHANNEL,
        "ring": TARGET_RING,
    }
    aliases = {
        "version": "package_version",
    }
    normalized = dict(target)
    for source, dest in aliases.items():
        if source in normalized and dest not in normalized:
            normalized[dest] = normalized[source]
    for key, value in expected.items():
        if normalized.get(key) != value:
            blockers.append(f"{label}_{key}_mismatch")
    return blockers


def evaluate_h2_readiness(path: Path) -> dict[str, Any]:
    blockers: list[str] = []
    data = read_json(path, blockers, "h2_readiness")
    if not data:
        return step(False, blockers, path=str(path))
    if data.get("schema") != "dadooh.c18.player_runtime.h2_readiness.v1":
        blockers.append("h2_readiness_schema")
    if data.get("passed") is not False:
        blockers.append("h2_must_remain_blocked_pre_soak")
    if data.get("result_claim") != "h2_readiness_blocked":
        blockers.append("h2_result_claim")
    if sorted(data.get("blockers", [])) != sorted(EXPECTED_H2_BLOCKERS):
        blockers.append("h2_blockers_not_exact_expected")
    checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    for name in (
        "h1_decisive_bundle",
        "server_side_publish_governance",
        "server_side_current_snapshot",
        "repo_clean",
        "tracked_inputs",
    ):
        if not isinstance(checks.get(name), dict) or checks[name].get("passed") is not True:
            blockers.append(f"h2_green_check_missing_or_failed:{name}")
    for name in (
        "full_physical_powerloss_matrix",
        "soak_endurance_24h",
        "stable_promotion_authorization",
        "explicit_operator_thaw_decision",
    ):
        if not isinstance(checks.get(name), dict) or checks[name].get("passed") is not False:
            blockers.append(f"h2_red_check_missing_or_not_red:{name}")
    non_claims = set(data.get("non_claims", []))
    for claim in (
        "this_gate_does_not_thaw_player_runtime",
        "this_gate_does_not_publish_or_fetch_releases",
        "this_gate_does_not_override_freeze_rc_44",
        "this_gate_does_not_promote_stable_without_operator_decision",
    ):
        if claim not in non_claims:
            blockers.append(f"h2_non_claim_missing:{claim}")
    return step(
        not blockers,
        blockers,
        path=str(path),
        sha256=sha256_file(path) if path.is_file() else None,
        result_claim=data.get("result_claim"),
        blockers_actual=data.get("blockers", []),
    )


def evaluate_macro_snapshot(path: Path) -> dict[str, Any]:
    blockers: list[str] = []
    data = read_json(path, blockers, "macro_governance")
    if not data:
        return step(False, blockers, path=str(path))
    if data.get("schema") != "dadooh.c18.ota_macro_governance_gate.v1":
        blockers.append("macro_schema")
    if data.get("passed") is not True:
        blockers.append("macro_not_passed")
    if data.get("result_claim") != "c18_homologation_governance_ready_pre_h2":
        blockers.append("macro_result_claim")
    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    blockers.extend(target_blockers(target, label="macro_target"))
    checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    h2 = checks.get("h2_preproduction_block") if isinstance(checks.get("h2_preproduction_block"), dict) else {}
    if h2.get("passed") is not True:
        blockers.append("macro_h2_preproduction_check_not_passed")
    if sorted(h2.get("blockers_actual", [])) != sorted(EXPECTED_H2_BLOCKERS):
        blockers.append("macro_h2_blockers_not_exact_expected")
    server = checks.get("server_side_current") if isinstance(checks.get("server_side_current"), dict) else {}
    if server.get("passed") is not True:
        blockers.append("macro_server_side_current_not_passed")
    return step(not blockers, blockers, path=str(path), result_claim=data.get("result_claim"))


def evaluate_server_side_current(run_dir: Path) -> dict[str, Any]:
    blockers: list[str] = []
    manifest = read_json(run_dir / "evidence-manifest.json", blockers, "server_side_current_manifest")
    if not manifest:
        return step(False, blockers, run_dir=str(run_dir))
    if manifest.get("schema") != "dadooh.c18.server_side_current_validation_snapshot.v1":
        blockers.append("server_side_current_schema")
    if manifest.get("passed") is not True:
        blockers.append("server_side_current_not_passed")
    if manifest.get("result_claim") != "server_side_publish_governance_ready":
        blockers.append("server_side_current_result_claim")
    target = manifest.get("target_package") if isinstance(manifest.get("target_package"), dict) else {}
    if target.get("version") != TARGET_PACKAGE_VERSION:
        blockers.append("server_side_current_target_version")
    if target.get("source_commit") != TARGET_SOURCE_COMMIT:
        blockers.append("server_side_current_source_commit")
    if target.get("payload_sha256") != TARGET_PAYLOAD_SHA256:
        blockers.append("server_side_current_payload_sha256")
    if target.get("component") != "player-runtime":
        blockers.append("server_side_current_component")
    if target.get("channel") != TARGET_CHANNEL:
        blockers.append("server_side_current_channel")
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    for filename in ("README.md", "server-side-governance-gate.json", "server-side-asset-list.json"):
        path = run_dir / filename
        entry = next((item for item in files if isinstance(item, dict) and item.get("file") == filename), None)
        if not path.is_file():
            blockers.append(f"server_side_current_file_missing:{filename}")
            continue
        if entry is None:
            blockers.append(f"server_side_current_manifest_file_missing:{filename}")
            continue
        if entry.get("sha256") != sha256_file(path):
            blockers.append(f"server_side_current_file_sha256_mismatch:{filename}")
        if entry.get("bytes") != path.stat().st_size:
            blockers.append(f"server_side_current_file_bytes_mismatch:{filename}")
    assets = read_json(run_dir / "server-side-asset-list.json", blockers, "server_side_asset_list")
    if assets:
        asset_records = assets.get("asset_records") if isinstance(assets.get("asset_records"), list) else []
        if len(asset_records) != 14:
            blockers.append("server_side_current_asset_count_not_14")
    return step(not blockers, blockers, run_dir=str(run_dir), result_claim=manifest.get("result_claim"))


def evaluate_h2_powerloss_preflight_snapshot(
    run_dir: Path,
    now_utc: str,
    *,
    max_age_sec: int = H2_POWERLOSS_PREFLIGHT_MAX_AGE_SEC,
) -> dict[str, Any]:
    blockers: list[str] = []
    manifest = read_json(run_dir / "evidence-manifest.json", blockers, "h2_powerloss_preflight_manifest")
    if not manifest:
        return step(False, blockers, run_dir=str(run_dir))
    if manifest.get("schema") != "dadooh.c18.h2_powerloss_board_preflight_snapshot.v1":
        blockers.append("h2_powerloss_preflight_schema")
    if manifest.get("passed") is not True:
        blockers.append("h2_powerloss_preflight_not_passed")
    if manifest.get("result_claim") != "h2_powerloss_board_preflight_accepted":
        blockers.append("h2_powerloss_preflight_result_claim")
    target = manifest.get("target_package") if isinstance(manifest.get("target_package"), dict) else {}
    if target.get("version") != TARGET_PACKAGE_VERSION:
        blockers.append("h2_powerloss_preflight_target_version")
    if target.get("source_commit") != TARGET_SOURCE_COMMIT:
        blockers.append("h2_powerloss_preflight_source_commit")
    if target.get("payload_sha256") != TARGET_PAYLOAD_SHA256:
        blockers.append("h2_powerloss_preflight_payload_sha256")
    captured_at = parse_utc(manifest.get("collected_at_utc"), blockers, "h2_powerloss_preflight_collected_at_utc")
    evaluated_at = parse_utc(now_utc, blockers, "now_utc")
    age_sec: int | None = None
    if captured_at is not None and evaluated_at is not None:
        age_sec = int((evaluated_at - captured_at).total_seconds())
        if age_sec < 0:
            blockers.append("h2_powerloss_preflight_collected_after_now")
        elif age_sec > max_age_sec:
            blockers.append("h2_powerloss_preflight_stale")
    checks = manifest.get("key_checks") if isinstance(manifest.get("key_checks"), dict) else {}
    for name in (
        "collector_passed",
        "offline_gate_passed",
        "preflight_fresh_under_4h",
        "policy_homologation",
        "allowed_components_totem_core_only",
        "update_timer_disabled",
        "image_marker_c18_hwdecode_lab_1x",
        "target_not_linked",
        "target_not_quarantined",
        "pending_checkpoint_dirs_absent",
    ):
        if checks.get(name) is not True:
            blockers.append(f"h2_powerloss_preflight_key_check_not_true:{name}")
    non_claims = set(manifest.get("non_claims", []))
    for claim in (
        "this_preflight_is_not_powerloss_evidence",
        "this_preflight_does_not_claim_17_17",
        "this_preflight_does_not_authorize_stable_or_production",
        "this_preflight_does_not_thaw_player_runtime",
        "this_preflight_does_not_satisfy_24h_soak",
        "this_preflight_does_not_complete_h2_readiness",
    ):
        if claim not in non_claims:
            blockers.append(f"h2_powerloss_preflight_non_claim_missing:{claim}")
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    for filename in ("README.md", "board-preflight.json", "h2-powerloss-preflight-gate.json"):
        path = run_dir / filename
        entry = next((item for item in files if isinstance(item, dict) and item.get("file") == filename), None)
        if not path.is_file():
            blockers.append(f"h2_powerloss_preflight_file_missing:{filename}")
            continue
        if entry is None:
            blockers.append(f"h2_powerloss_preflight_manifest_file_missing:{filename}")
            continue
        if entry.get("sha256") != sha256_file(path):
            blockers.append(f"h2_powerloss_preflight_file_sha256_mismatch:{filename}")
        if entry.get("bytes") != path.stat().st_size:
            blockers.append(f"h2_powerloss_preflight_file_bytes_mismatch:{filename}")
    return step(
        not blockers,
        blockers,
        run_dir=str(run_dir),
        result_claim=manifest.get("result_claim"),
        freshness={
            "captured_at_utc": manifest.get("collected_at_utc"),
            "evaluated_at_utc": now_utc,
            "age_sec": age_sec,
            "max_age_sec": max_age_sec,
        },
    )


def evaluate_docs(paths: tuple[Path, ...] = DEFAULT_DOCS) -> dict[str, Any]:
    blockers: list[str] = []
    combined_parts: list[str] = []
    for path in paths:
        try:
            combined_parts.append(path.read_text(encoding="utf-8"))
        except OSError:
            blockers.append(f"doc_missing:{path}")
    combined = "\n".join(combined_parts)
    for group, tokens in RESPONSIBILITY_DOC_TOKENS.items():
        for token in tokens:
            if token not in combined:
                blockers.append(f"doc_token_missing:{group}:{token}")
    forbidden = (
        "C18 Homologation RC pronta para producao",
        "public thaw autorizado",
        "auto-pull habilitado para player-runtime",
    )
    for token in forbidden:
        if token in combined:
            blockers.append(f"doc_forbidden_token_present:{token}")
    return step(not blockers, blockers, doc_count=len(paths))


def evaluate_release_gate() -> dict[str, Any]:
    result = run_json_command(
        "release_gate",
        ["python3", "scripts/qa/c18_ota_release_gate.py", "--json"],
        expected_returncodes={0},
    )
    payload = result.get("payload", {})
    blockers = list(result.get("blockers", []))
    if payload.get("passed") is not True:
        blockers.append("release_gate_not_passed")
    return step(not blockers, blockers, returncode=result.get("returncode"))


def evaluate_macro_gate(*, allow_dirty_repo: bool = False) -> dict[str, Any]:
    cmd = ["python3", "scripts/qa/c18_ota_macro_governance_gate.py", "--json"]
    if allow_dirty_repo:
        cmd.append("--allow-dirty-repo")
    result = run_json_command(
        "macro_gate",
        cmd,
        expected_returncodes={0, 1},
    )
    payload = result.get("payload", {})
    blockers = list(result.get("blockers", []))
    if payload.get("passed") is not True:
        blockers.append("macro_gate_not_passed")
        for blocker in payload.get("blockers", []):
            blockers.append(f"macro_gate_blocker:{blocker}")
    elif payload.get("result_claim") != "c18_homologation_governance_ready_pre_h2":
        blockers.append("macro_gate_result_claim")
    return step(not blockers, blockers, returncode=result.get("returncode"))


def evaluate_operational_resume_default(now_utc: str, *, allow_dirty_repo: bool = False) -> dict[str, Any]:
    cmd = ["python3", "scripts/qa/c18_ota_operational_resume_gate.py", "--now-utc", now_utc, "--json"]
    if allow_dirty_repo:
        cmd.append("--allow-dirty-repo")
    result = run_json_command(
        "operational_resume_default",
        cmd,
        expected_returncodes={1},
    )
    payload = result.get("payload", {})
    blockers = list(result.get("blockers", []))
    if payload.get("passed") is not False:
        blockers.append("operational_resume_default_must_block_without_current_inputs")
    if payload.get("result_claim") != "c18_operational_resume_blocked":
        blockers.append("operational_resume_default_result_claim")
    expected_blockers = {
        "current_board_preflight:current_board_preflight_missing",
        "current_pilot_authorization:current_pilot_authorization_missing",
    }
    if set(payload.get("blockers", [])) != expected_blockers:
        blockers.append("operational_resume_default_blockers_not_exact_expected")
    macro = payload.get("checks", {}).get("macro_governance_snapshot", {}) if isinstance(payload.get("checks"), dict) else {}
    if macro.get("passed") is not True:
        blockers.append("operational_resume_default_macro_not_passed")
    if "20260617T064617Z-current-macro-governance-a761a67" not in str(macro.get("summary_path")):
        blockers.append("operational_resume_default_macro_not_current")
    return step(not blockers, blockers, returncode=result.get("returncode"))


def evaluate_repo_clean(*, allow_dirty_repo: bool = False) -> dict[str, Any]:
    proc = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    blockers: list[str] = []
    changed = [line for line in proc.stdout.splitlines() if line.strip()]
    if proc.returncode != 0:
        blockers.append("repo_status_failed")
    if changed and not allow_dirty_repo:
        blockers.append("repo_dirty")
    return step(not blockers, blockers, changed_paths=changed, stderr_tail=proc.stderr[-800:])


def evaluate_tracked_inputs(paths: tuple[Path, ...] = TRACKED_INPUTS) -> dict[str, Any]:
    blockers: list[str] = []
    checked: list[str] = []
    for path in paths:
        rel = path.relative_to(REPO_ROOT) if path.is_absolute() and path.is_relative_to(REPO_ROOT) else path
        checked.append(str(rel))
        if path.is_dir():
            proc = subprocess.run(["git", "ls-files", "--", str(rel)], cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if proc.returncode != 0 or not proc.stdout.strip():
                blockers.append(f"tracked_input_dir_missing_or_untracked:{rel}")
        else:
            proc = subprocess.run(["git", "ls-files", "--error-unmatch", str(rel)], cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if proc.returncode != 0:
                blockers.append(f"tracked_input_file_missing_or_untracked:{rel}")
    return step(not blockers, blockers, paths=checked)


def effective_tracked_inputs(args: argparse.Namespace) -> tuple[Path, ...]:
    return (
        args.h2_readiness,
        args.macro_governance_summary,
        args.server_side_current_dir,
        args.h2_powerloss_preflight_dir,
        *DEFAULT_TARGET_BLOCKING_DIAGNOSTIC_DIRS,
        *DEFAULT_DOCS,
    )


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    now_utc = args.now_utc or utcnow()
    checks = {
        "repo_clean": evaluate_repo_clean(allow_dirty_repo=args.allow_dirty_repo),
        "tracked_inputs": evaluate_tracked_inputs(effective_tracked_inputs(args)),
        "responsibility_docs": evaluate_docs(),
        "h2_pre_soak_block": evaluate_h2_readiness(args.h2_readiness),
        "macro_snapshot": evaluate_macro_snapshot(args.macro_governance_summary),
        "server_side_current": evaluate_server_side_current(args.server_side_current_dir),
        "h2_powerloss_board_preflight_snapshot": evaluate_h2_powerloss_preflight_snapshot(
            args.h2_powerloss_preflight_dir,
            now_utc,
        ),
        "macro_gate": evaluate_macro_gate(allow_dirty_repo=args.allow_dirty_repo),
        "operational_resume_default": evaluate_operational_resume_default(
            now_utc,
            allow_dirty_repo=args.allow_dirty_repo,
        ),
    }
    if args.run_release_gate:
        checks["release_gate"] = evaluate_release_gate()
    else:
        checks["release_gate"] = step(True, [], skipped=True)
    blockers = [
        f"{name}:{blocker}"
        for name, result in checks.items()
        for blocker in result.get("blockers", [])
    ]
    passed = not blockers
    return {
        "schema": SCHEMA,
        "passed": passed,
        "result_claim": "c18_ota_pre_soak_scale_governance_ready" if passed else "c18_ota_pre_soak_scale_governance_blocked",
        "evaluated_at_utc": utcnow(),
        "now_utc": now_utc,
        "target": {
            "component": "player-runtime",
            "package_version": TARGET_PACKAGE_VERSION,
            "source_commit": TARGET_SOURCE_COMMIT,
            "payload_sha256": TARGET_PAYLOAD_SHA256,
            "channel": TARGET_CHANNEL,
            "ring": TARGET_RING,
        },
        "checks": checks,
        "blockers": blockers,
        "expected_h2_blockers": list(EXPECTED_H2_BLOCKERS),
        "non_claims": list(NON_CLAIMS),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class PreSoakScaleGovernanceGateSelfTest(unittest.TestCase):
    def write_h2_powerloss_preflight_fixture(self, root: Path, *, key_checks: dict[str, bool] | None = None) -> Path:
        run_dir = root / "h2-powerloss-preflight"
        run_dir.mkdir()
        for filename, content in {
            "README.md": "fixture\n",
            "board-preflight.json": "{}\n",
            "h2-powerloss-preflight-gate.json": "{}\n",
        }.items():
            (run_dir / filename).write_text(content, encoding="utf-8")
        checks = {
            "collector_passed": True,
            "offline_gate_passed": True,
            "preflight_fresh_under_4h": True,
            "policy_homologation": True,
            "allowed_components_totem_core_only": True,
            "update_timer_disabled": True,
            "image_marker_c18_hwdecode_lab_1x": True,
            "target_not_linked": True,
            "target_not_quarantined": True,
            "pending_checkpoint_dirs_absent": True,
        }
        if key_checks:
            checks.update(key_checks)
        write_json(run_dir / "evidence-manifest.json", {
            "schema": "dadooh.c18.h2_powerloss_board_preflight_snapshot.v1",
            "collected_at_utc": "2026-06-16T23:57:24Z",
            "passed": True,
            "result_claim": "h2_powerloss_board_preflight_accepted",
            "target_package": {
                "version": TARGET_PACKAGE_VERSION,
                "source_commit": TARGET_SOURCE_COMMIT,
                "payload_sha256": TARGET_PAYLOAD_SHA256,
            },
            "files": [
                {
                    "file": filename,
                    "sha256": sha256_file(run_dir / filename),
                    "bytes": (run_dir / filename).stat().st_size,
                }
                for filename in ("README.md", "board-preflight.json", "h2-powerloss-preflight-gate.json")
            ],
            "key_checks": checks,
            "non_claims": [
                "this_preflight_is_not_powerloss_evidence",
                "this_preflight_does_not_claim_17_17",
                "this_preflight_does_not_authorize_stable_or_production",
                "this_preflight_does_not_thaw_player_runtime",
                "this_preflight_does_not_satisfy_24h_soak",
                "this_preflight_does_not_complete_h2_readiness",
            ],
        })
        return run_dir

    def test_h2_must_remain_blocked_with_exact_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h2.json"
            write_json(path, {
                "schema": "dadooh.c18.player_runtime.h2_readiness.v1",
                "passed": False,
                "result_claim": "h2_readiness_blocked",
                "blockers": list(EXPECTED_H2_BLOCKERS),
                "checks": {
                    "h1_decisive_bundle": {"passed": True},
                    "server_side_publish_governance": {"passed": True},
                    "server_side_current_snapshot": {"passed": True},
                    "repo_clean": {"passed": True},
                    "tracked_inputs": {"passed": True},
                    "full_physical_powerloss_matrix": {"passed": False},
                    "soak_endurance_24h": {"passed": False},
                    "stable_promotion_authorization": {"passed": False},
                    "explicit_operator_thaw_decision": {"passed": False},
                },
                "non_claims": [
                    "this_gate_does_not_thaw_player_runtime",
                    "this_gate_does_not_publish_or_fetch_releases",
                    "this_gate_does_not_override_freeze_rc_44",
                    "this_gate_does_not_promote_stable_without_operator_decision",
                ],
            })
            result = evaluate_h2_readiness(path)
        self.assertTrue(result["passed"], msg=result)

    def test_h2_green_is_rejected_pre_soak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h2.json"
            write_json(path, {
                "schema": "dadooh.c18.player_runtime.h2_readiness.v1",
                "passed": True,
                "result_claim": "h2_readiness_ready",
                "blockers": [],
                "checks": {},
                "non_claims": [],
            })
            result = evaluate_h2_readiness(path)
        self.assertFalse(result["passed"])
        self.assertIn("h2_must_remain_blocked_pre_soak", result["blockers"])

    def test_h2_powerloss_preflight_snapshot_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.write_h2_powerloss_preflight_fixture(Path(tmp))
            result = evaluate_h2_powerloss_preflight_snapshot(run_dir, "2026-06-17T01:20:00Z")
        self.assertTrue(result["passed"], msg=result)

    def test_h2_powerloss_preflight_snapshot_rejects_stale_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.write_h2_powerloss_preflight_fixture(Path(tmp))
            result = evaluate_h2_powerloss_preflight_snapshot(run_dir, "2026-06-17T05:00:00Z")
        self.assertFalse(result["passed"])
        self.assertIn("h2_powerloss_preflight_stale", result["blockers"])

    def test_h2_powerloss_preflight_snapshot_rejects_tampered_key_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.write_h2_powerloss_preflight_fixture(
                Path(tmp),
                key_checks={"update_timer_disabled": False},
            )
            result = evaluate_h2_powerloss_preflight_snapshot(run_dir, "2026-06-17T01:20:00Z")
        self.assertFalse(result["passed"])
        self.assertIn(
            "h2_powerloss_preflight_key_check_not_true:update_timer_disabled",
            result["blockers"],
        )

    def test_tracked_inputs_follow_cli_overrides(self) -> None:
        args = argparse.Namespace(
            h2_readiness=Path("/tmp/custom-h2.json"),
            macro_governance_summary=Path("/tmp/custom-macro.json"),
            server_side_current_dir=Path("/tmp/custom-server-side"),
            h2_powerloss_preflight_dir=Path("/tmp/custom-powerloss-preflight"),
        )
        inputs = effective_tracked_inputs(args)

        self.assertIn(Path("/tmp/custom-h2.json"), inputs)
        self.assertIn(Path("/tmp/custom-macro.json"), inputs)
        self.assertIn(Path("/tmp/custom-server-side"), inputs)
        self.assertIn(Path("/tmp/custom-powerloss-preflight"), inputs)
        self.assertNotIn(DEFAULT_H2_READINESS, inputs)
        self.assertNotIn(DEFAULT_MACRO_SUMMARY, inputs)
        self.assertNotIn(DEFAULT_SERVER_SIDE_CURRENT_DIR, inputs)
        self.assertNotIn(DEFAULT_H2_POWERLOSS_PREFLIGHT_DIR, inputs)

    def test_docs_require_all_responsibility_fronts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "doc.md"
            doc.write_text("\n".join(
                token
                for tokens in RESPONSIBILITY_DOC_TOKENS.values()
                for token in tokens
            ), encoding="utf-8")
            result = evaluate_docs((doc,))
        self.assertTrue(result["passed"], msg=result)

    def test_operational_resume_default_requires_current_macro_and_blocks(self) -> None:
        payload = {
            "passed": False,
            "result_claim": "c18_operational_resume_blocked",
            "blockers": [
                "current_board_preflight:current_board_preflight_missing",
                "current_pilot_authorization:current_pilot_authorization_missing",
            ],
            "checks": {
                "macro_governance_snapshot": {
                    "passed": True,
                    "summary_path": str(DEFAULT_MACRO_SUMMARY),
                },
            },
        }
        with mock.patch(
            __name__ + ".run_json_command",
            return_value=step(True, [], returncode=1, payload=payload),
        ):
            result = evaluate_operational_resume_default("2026-06-17T01:20:00Z")
        self.assertTrue(result["passed"], msg=result)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--h2-readiness", type=Path, default=DEFAULT_H2_READINESS)
    parser.add_argument("--macro-governance-summary", type=Path, default=DEFAULT_MACRO_SUMMARY)
    parser.add_argument("--server-side-current-dir", type=Path, default=DEFAULT_SERVER_SIDE_CURRENT_DIR)
    parser.add_argument("--h2-powerloss-preflight-dir", type=Path, default=DEFAULT_H2_POWERLOSS_PREFLIGHT_DIR)
    parser.add_argument("--now-utc")
    parser.add_argument("--run-release-gate", action="store_true")
    parser.add_argument("--allow-dirty-repo", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(PreSoakScaleGovernanceGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = evaluate(args)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} result={result['result_claim']}")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
