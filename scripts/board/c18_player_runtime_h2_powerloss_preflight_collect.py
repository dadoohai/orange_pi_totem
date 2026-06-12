#!/usr/bin/env python3
"""Collect read-only C18 H2 power-loss board preflight state.

This collector snapshots a board before the physical power-loss matrix. It does
not arm checkpoints, cut power, resume trials, run updatectl freeze probes,
mutate player-runtime state, create evidence directories, write output files,
fetch releases, or claim H2 readiness. The offline gate decides whether the
snapshot is acceptable for a physical session.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from c18_coldboot_state_collect import image_identity, player_runtime_paths, sha12


SCHEMA = "dadooh.c18.player_runtime.h2_powerloss_board_preflight.v1"
MANIFEST_SCHEMA = "dadooh.totem.update.v1"
POLICY_SCHEMA = "dadooh.totem.update.policy.v1"
DEFAULT_POLICY = Path("/data/updates/policy.json")
DEFAULT_DATA_ROOT = Path("/data")
DEFAULT_UPDATE_TIMER = "totem-update-agent.timer"
DEFAULT_PLAYER_SERVICE = "kiosky-player.service"
DEFAULT_MPV_WRAPPER = Path("/opt/totem/bin/totem-mpv-hwdecode")
DEFAULT_HWDECODE_MPV = Path("/opt/totem/hwdecode/bin/mpv")
NON_CLAIMS = (
    "this_preflight_is_not_powerloss_evidence",
    "this_preflight_does_not_claim_17_17",
    "this_preflight_does_not_arm_or_resume_trials",
    "this_preflight_does_not_replace_physical_power_cut",
    "this_preflight_does_not_create_or_modify_evidence",
    "this_preflight_does_not_apply_or_rollback_player_runtime",
    "this_preflight_does_not_probe_or_prove_public_freeze_rc44",
    "this_preflight_does_not_authorize_stable_or_production",
    "this_preflight_does_not_thaw_player_runtime",
    "this_preflight_does_not_publish_or_fetch_releases",
)


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def read_json_object(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"json_read_failed:{type(exc).__name__}"
    if not isinstance(data, dict):
        return {}, "json_not_object"
    return data, None


def sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def path_status(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists() or path.is_symlink(),
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
        "is_symlink": path.is_symlink(),
    }
    try:
        stat = path.stat()
        out["size_bytes"] = stat.st_size
        out["mode_octal"] = oct(stat.st_mode & 0o777)
    except OSError:
        out["size_bytes"] = None
        out["mode_octal"] = None
    return out


def run(cmd: list[str], *, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
    }
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env=env,
        check=False,
    )


def systemd_unit_state(unit: str) -> dict[str, Any]:
    enabled = run(["systemctl", "is-enabled", unit], timeout=10)
    active = run(["systemctl", "is-active", unit], timeout=10)
    return {
        "unit": unit,
        "enabled_rc": enabled.returncode,
        "enabled_raw": enabled.stdout.strip() or enabled.stderr.strip(),
        "active_rc": active.returncode,
        "active_raw": active.stdout.strip() or active.stderr.strip(),
        "enabled": enabled.returncode == 0 and enabled.stdout.strip() == "enabled",
        "active": active.returncode == 0 and active.stdout.strip() == "active",
    }


def load_policy(path: Path) -> dict[str, Any]:
    policy, error = read_json_object(path)
    return {
        "path": str(path),
        "present": path.is_file(),
        "read_error": error,
        "schema": policy.get("schema"),
        "device_track": policy.get("device_track"),
        "device_channel": policy.get("device_channel"),
        "allow_prerelease": policy.get("allow_prerelease"),
        "allow_downgrade": policy.get("allow_downgrade"),
        "allowed_components": policy.get("allowed_components"),
    }


def package_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    manifest = args.package_manifest
    payload = args.package_payload
    if manifest is None:
        candidates = sorted(args.bundle_dir.rglob("dadooh-player-runtime-*.manifest.json"))
        if len(candidates) == 1:
            manifest = candidates[0]
    if manifest is not None and payload is None:
        data, _error = read_json_object(manifest)
        payload_name = data.get("payload")
        if isinstance(payload_name, str) and payload_name:
            payload = manifest.parent / payload_name
    if payload is None:
        candidates = sorted(args.bundle_dir.rglob("dadooh-player-runtime-*.tar.gz"))
        if len(candidates) == 1:
            payload = candidates[0]
    return manifest or Path(""), payload or Path("")


def load_package(manifest_path: Path, payload_path: Path) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    manifest, error = read_json_object(manifest_path)
    payload_sha256_actual = sha256_file(payload_path) if payload_path.is_file() else None
    if not manifest_path.is_file():
        blockers.append("package_manifest_missing")
    elif error:
        blockers.append(f"package_manifest_{error}")
    if not payload_path.is_file():
        blockers.append("package_payload_missing")
    if manifest and manifest.get("schema") != MANIFEST_SCHEMA:
        blockers.append("package_manifest_schema")
    if manifest and manifest.get("component") != "player-runtime":
        blockers.append("package_component_not_player_runtime")
    if manifest and manifest.get("channel") != "homologation":
        blockers.append("package_channel_not_homologation")
    if manifest and payload_path.name and manifest.get("payload") != payload_path.name:
        blockers.append("package_payload_name_mismatch")
    if manifest and payload_sha256_actual and manifest.get("payload_sha256") != payload_sha256_actual:
        blockers.append("package_payload_sha256_mismatch")
    return {
        "manifest_path": str(manifest_path),
        "payload_path": str(payload_path),
        "manifest_present": manifest_path.is_file(),
        "payload_present": payload_path.is_file(),
        "manifest_schema": manifest.get("schema"),
        "component": manifest.get("component"),
        "channel": manifest.get("channel"),
        "version": manifest.get("version"),
        "source_commit": manifest.get("source_commit"),
        "payload_name": manifest.get("payload"),
        "payload_sha256": manifest.get("payload_sha256"),
        "payload_sha256_actual": payload_sha256_actual,
        "payload_sha256_matches_manifest": (
            bool(payload_sha256_actual)
            and manifest.get("payload_sha256") == payload_sha256_actual
        ),
    }, blockers


def evidence_root_status(path: Path) -> dict[str, Any]:
    children: list[str] = []
    if path.is_dir():
        try:
            children = sorted(item.name for item in path.iterdir() if item.is_dir())
        except OSError:
            children = []
    parent = path.parent
    return {
        "path": str(path),
        "exists": path.exists() or path.is_symlink(),
        "is_dir": path.is_dir(),
        "parent": str(parent),
        "parent_exists": parent.exists(),
        "parent_is_dir": parent.is_dir(),
        "parent_writable": os.access(parent, os.W_OK) if parent.exists() else False,
        "direct_child_dirs": children,
    }


def wrappers_status(mpv_wrapper: Path, hwdecode_mpv: Path) -> dict[str, Any]:
    wrapper = path_status(mpv_wrapper)
    hwdecode = path_status(hwdecode_mpv)
    wrapper["executable"] = os.access(mpv_wrapper, os.X_OK)
    hwdecode["executable"] = os.access(hwdecode_mpv, os.X_OK)
    return {
        "expected_mpv_wrapper": str(mpv_wrapper),
        "expected_hwdecode_mpv": str(hwdecode_mpv),
        "mpv_wrapper": wrapper,
        "hwdecode_mpv": hwdecode,
    }


def read_symlink(path: Path) -> str | None:
    try:
        return os.readlink(path)
    except OSError:
        return None


def state_entry_version(entry: Any) -> str | None:
    if isinstance(entry, dict) and isinstance(entry.get("version"), str):
        return entry["version"]
    return None


def state_entry_payload_sha256(entry: Any) -> str | None:
    if isinstance(entry, dict) and isinstance(entry.get("payload_sha256"), str):
        return entry["payload_sha256"]
    return None


def quarantine_entries(state: dict[str, Any]) -> list[dict[str, Any]]:
    entries = state.get("quarantine") or state.get("quarantined_identities") or []
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def runtime_topology(data_root: Path, target_version: str | None) -> dict[str, Any]:
    app_base = data_root / "player-runtime"
    state_file = app_base / "state.json"
    state, state_error = read_json_object(state_file)
    current_link = read_symlink(app_base / "current")
    previous_link = read_symlink(app_base / "previous")
    target_link = f"releases/{target_version}" if target_version else None
    target_release_dir = app_base / target_link if target_link else None
    current = state.get("current") if isinstance(state.get("current"), dict) else None
    previous = state.get("previous") if isinstance(state.get("previous"), dict) else None
    quarantine = quarantine_entries(state)
    target_payload = (
        state_entry_payload_sha256(current)
        if target_version and state_entry_version(current) == target_version
        else state_entry_payload_sha256(previous)
        if target_version and state_entry_version(previous) == target_version
        else None
    )
    target_quarantine = [
        entry
        for entry in quarantine
        if (
            target_version
            and (
                entry.get("version") == target_version
                or (target_payload and entry.get("payload_sha256") == target_payload)
            )
        )
    ]
    return {
        "data_root": str(data_root),
        "app_base": str(app_base),
        "state_file": str(state_file),
        "state_present": state_file.is_file(),
        "state_read_error": state_error,
        "state_schema": state.get("schema"),
        "current_link": current_link,
        "previous_link": previous_link,
        "state_current_version": state_entry_version(current),
        "state_previous_version": state_entry_version(previous),
        "state_current_payload_sha256": state_entry_payload_sha256(current),
        "state_previous_payload_sha256": state_entry_payload_sha256(previous),
        "last_operation": state.get("last_operation") if isinstance(state.get("last_operation"), dict) else None,
        "quarantine_count": len(quarantine),
        "quarantine_versions": sorted(str(entry.get("version") or "") for entry in quarantine if entry.get("version")),
        "target_quarantine_count": len(target_quarantine),
        "target_quarantined": bool(target_quarantine),
        "target_link": target_link,
        "target_release_dir": str(target_release_dir) if target_release_dir else None,
        "target_release_dir_exists": bool(target_release_dir and target_release_dir.is_dir()),
        "target_is_current_link": bool(target_link and current_link == target_link),
        "target_is_previous_link": bool(target_link and previous_link == target_link),
        "target_is_current_state": bool(target_version and state_entry_version(current) == target_version),
        "target_is_previous_state": bool(target_version and state_entry_version(previous) == target_version),
    }


def boot_summary() -> dict[str, Any]:
    boot_id = read_text(Path("/proc/sys/kernel/random/boot_id"))
    return {
        "boot_id_sha256_12": sha12(boot_id),
        "raw_boot_id_persisted": False,
    }


def collect(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path, payload_path = package_paths(args)
    package, package_blockers = load_package(manifest_path, payload_path)
    evidence_root = evidence_root_status(args.evidence_root)
    blockers = list(package_blockers)
    if not args.bundle_dir.is_dir():
        blockers.append("bundle_dir_missing")
    if not args.canary_media.is_file():
        blockers.append("canary_media_missing")
    if evidence_root["exists"] and not evidence_root["is_dir"]:
        blockers.append("evidence_root_not_dir")
    if not evidence_root["parent_exists"] or not evidence_root["parent_is_dir"]:
        blockers.append("evidence_root_parent_missing")
    if not evidence_root["parent_writable"]:
        blockers.append("evidence_root_parent_not_writable")
    policy = load_policy(args.policy)
    if policy["read_error"]:
        blockers.append("policy_read_failed")
    timer = systemd_unit_state(args.update_timer)
    service = systemd_unit_state(args.player_service)
    result_claim = (
        "h2_powerloss_board_preflight_collected"
        if not blockers
        else "h2_powerloss_board_preflight_collection_blocked"
    )
    return {
        "schema": SCHEMA,
        "passed": not blockers,
        "result_claim": result_claim,
        "captured_at_utc": utcnow(),
        "collection_mode": "read_only_preflight",
        "target_package": package,
        "board_paths": {
            "bundle_dir": str(args.bundle_dir),
            "evidence_root": str(args.evidence_root),
            "canary_media": str(args.canary_media),
        },
        "bundle": path_status(args.bundle_dir),
        "canary_media": path_status(args.canary_media),
        "evidence_root": evidence_root,
        "policy": policy,
        "systemd": {
            "update_timer": timer,
            "player_service": service,
        },
        "image": image_identity(args.image_marker),
        "player_runtime": player_runtime_paths(),
        "runtime_topology": runtime_topology(args.data_root, package.get("version")),
        "wrappers": wrappers_status(args.mpv_wrapper, args.hwdecode_mpv),
        "boot": boot_summary(),
        "updatectl_freeze_probe": {
            "included": False,
            "reason": "read_only_h2_powerloss_preflight",
        },
        "blockers": blockers,
        "non_claims": list(NON_CLAIMS),
        "privacy": {
            "raw_boot_id_persisted": False,
            "raw_mount_source_persisted": False,
            "raw_journal_persisted": False,
            "raw_device_serial_persisted": False,
        },
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--package-manifest", type=Path)
    parser.add_argument("--package-payload", type=Path)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--canary-media", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--update-timer", default=DEFAULT_UPDATE_TIMER)
    parser.add_argument("--player-service", default=DEFAULT_PLAYER_SERVICE)
    parser.add_argument("--mpv-wrapper", type=Path, default=DEFAULT_MPV_WRAPPER)
    parser.add_argument("--hwdecode-mpv", type=Path, default=DEFAULT_HWDECODE_MPV)
    parser.add_argument("--image-marker")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    report = collect(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"passed={str(report['passed']).lower()} result={report['result_claim']}")
        for blocker in report["blockers"]:
            print(f"- {blocker}")
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
