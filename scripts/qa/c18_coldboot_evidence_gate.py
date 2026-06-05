#!/usr/bin/env python3
"""Validate sanitized C18 cold-boot evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.coldboot_state.v2"
DEFAULT_BOOT_STATE = "boot-state-public.json"
MAX_POST_BOOT_UPTIME_SECONDS = 900
LEAK_PATTERNS = (
    ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("mac", re.compile(r"\b[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}\b")),
    ("api_key", re.compile(r"api[_-]?key", re.IGNORECASE)),
    ("token", re.compile(r"\b(?:github_pat_|ghp_|gho_|ghs_)[A-Za-z0-9_]+\b")),
    ("url", re.compile(r"https?://", re.IGNORECASE)),
    ("ssid", re.compile(r"\bssid\b", re.IGNORECASE)),
    ("uuid_source", re.compile(r"\b(?:UUID|PARTUUID)=[A-Za-z0-9._:-]+\b")),
    ("raw_uuid", re.compile(r"\b[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\b")),
    ("dev_disk_path", re.compile(r"/dev/disk/by-[A-Za-z0-9._/-]+")),
    ("raw_block_device", re.compile(r"/dev/(?:mmcblk\d+p\d+|sd[a-z]\d*|nvme\d+n\d+p\d+)")),
)


def fail(errors: list[str], code: str) -> None:
    errors.append(code)


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(errors, f"json_invalid:{path.name}:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        fail(errors, f"json_not_object:{path.name}")
        return {}
    return data


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_leaks(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for label, pattern in LEAK_PATTERNS:
            if pattern.search(text):
                hits.append(f"{label}:{path.name}")
    return hits


def evidence_files(run_dir: Path) -> list[Path]:
    return sorted(path for path in run_dir.rglob("*") if path.is_file())


def validate_manifest(run_dir: Path, errors: list[str]) -> None:
    manifest_path = run_dir / "evidence-manifest.json"
    if not manifest_path.is_file():
        return
    manifest = load_json(manifest_path, errors)
    items = manifest.get("artifacts", manifest.get("files", []))
    if not isinstance(items, list):
        fail(errors, "manifest_files_not_list")
        return
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("file"), str):
            fail(errors, "manifest_file_entry_invalid")
            continue
        rel = item["file"]
        if rel.startswith("/") or ".." in Path(rel).parts:
            fail(errors, f"manifest_file_path_unsafe:{rel}")
            continue
        path = run_dir / rel
        if not path.is_file():
            fail(errors, f"manifest_file_missing:{rel}")
            continue
        expected_size = item.get("bytes", item.get("size"))
        if expected_size is not None and path.stat().st_size != expected_size:
            fail(errors, f"manifest_file_size_mismatch:{rel}")
        if item.get("sha256") and sha256_file(path) != item["sha256"]:
            fail(errors, f"manifest_file_sha256_mismatch:{rel}")


def validate_boot_state(
    data: dict[str, Any],
    errors: list[str],
    *,
    expect_source: str,
    adoption: dict[str, Any] | None = None,
) -> None:
    if data.get("schema") != SCHEMA:
        fail(errors, "schema_mismatch")
    boot = data.get("boot")
    if not isinstance(boot, dict):
        fail(errors, "boot_missing")
        boot = {}
    post_hash = boot.get("post_boot_id_sha256_12")
    pre_hash = boot.get("pre_boot_id_sha256_12")
    if not isinstance(pre_hash, str) or not re.fullmatch(r"[0-9a-f]{12}", pre_hash):
        fail(errors, "pre_boot_id_hash_missing")
    if not isinstance(post_hash, str) or not re.fullmatch(r"[0-9a-f]{12}", post_hash):
        fail(errors, "post_boot_id_hash_missing")
    if boot.get("boot_id_changed") is not True or (
        isinstance(pre_hash, str)
        and isinstance(post_hash, str)
        and re.fullmatch(r"[0-9a-f]{12}", pre_hash)
        and re.fullmatch(r"[0-9a-f]{12}", post_hash)
        and pre_hash == post_hash
    ):
        fail(errors, "boot_id_not_changed")
    uptime = boot.get("post_uptime_seconds")
    if not isinstance(uptime, (int, float)) or uptime < 0:
        fail(errors, "post_uptime_invalid")
    elif uptime > MAX_POST_BOOT_UPTIME_SECONDS:
        fail(errors, "post_uptime_too_high")
    pre_btime = boot.get("pre_btime")
    post_btime = boot.get("post_btime")
    if not isinstance(pre_btime, int):
        fail(errors, "pre_btime_missing")
    if not isinstance(post_btime, int):
        fail(errors, "post_btime_missing")
    if boot.get("btime_changed") is not True or (
        isinstance(pre_btime, int)
        and isinstance(post_btime, int)
        and post_btime <= pre_btime
    ):
        fail(errors, "btime_not_changed")
    captured_at = data.get("captured_at_unix")
    if isinstance(captured_at, (int, float)) and isinstance(post_btime, int) and isinstance(uptime, (int, float)):
        if abs((post_btime + uptime) - captured_at) > MAX_POST_BOOT_UPTIME_SECONDS:
            fail(errors, "boot_time_capture_inconsistent")

    mounts = data.get("mounts")
    if not isinstance(mounts, dict):
        fail(errors, "mounts_missing")
        mounts = {}
    root = mounts.get("root")
    data_mount = mounts.get("data")
    if not isinstance(root, dict) or not root.get("found"):
        fail(errors, "root_mount_missing")
    if not isinstance(data_mount, dict) or not data_mount.get("found"):
        fail(errors, "data_mount_missing")
    claim = mounts.get("data_mount_claim")
    if claim not in {"rootfs_directory", "separate_mount"}:
        fail(errors, "data_mount_claim_invalid")
    if mounts.get("data_same_device_as_root") is True and claim != "rootfs_directory":
        fail(errors, "data_mount_claim_conflicts_with_same_device")

    systemd = data.get("systemd")
    if not isinstance(systemd, dict):
        fail(errors, "systemd_missing")
        systemd = {}
    if systemd.get("active_state") != "active":
        fail(errors, "service_not_active")
    if systemd.get("requires_data_mount") is not True:
        fail(errors, "requires_mounts_for_data_missing")
    if systemd.get("after_contains_local_fs") is not True:
        fail(errors, "after_local_fs_missing")
    if systemd.get("exec_start_pre_reconcile_present") is not True:
        fail(errors, "exec_start_pre_reconcile_missing")

    player = data.get("player_runtime")
    if not isinstance(player, dict):
        fail(errors, "player_runtime_missing")
        player = {}
    selected = player.get("selected_source")
    if expect_source != "any" and selected != expect_source:
        fail(errors, f"selected_source_mismatch:{selected}")
    if expect_source == "data" and player.get("current_present") is not True:
        fail(errors, "data_current_missing")
    if expect_source == "data":
        if player.get("data_current_marker_verified") is not True:
            fail(errors, "data_current_marker_not_verified")
        if not isinstance(adoption, dict) or not adoption:
            fail(errors, "adoption_probe_missing")
        else:
            if adoption.get("schema") != "dadooh.c18.player_runtime.adoption.v1":
                fail(errors, "adoption_probe_schema")
            if adoption.get("passed") is not True:
                fail(errors, "adoption_probe_not_passed")
            if adoption.get("selected_source") != "data":
                fail(errors, "adoption_probe_not_data")
            if adoption.get("marker_valid") is not True:
                fail(errors, "adoption_probe_marker_invalid")
            if adoption.get("running_identity_matches_marker") is not True:
                fail(errors, "adoption_probe_identity_mismatch")
    if expect_source == "fallback" and player.get("current_present") is True:
        fail(errors, "unexpected_data_current")

    safety = data.get("update_safety")
    if isinstance(safety, dict) and safety.get("included") is True:
        for key in (
            "public_player_runtime_rollback_rc",
            "public_player_runtime_reconcile_rc",
            "public_kiosky_player_rollback_rc",
        ):
            if safety.get(key) != 44:
                fail(errors, f"freeze_probe_not_rc44:{key}")
        if "boot_player_runtime_reconcile_rc" in safety and safety.get("boot_player_runtime_reconcile_rc") != 0:
            fail(errors, "boot_reconcile_probe_not_rc0")

    privacy = data.get("privacy")
    if not isinstance(privacy, dict):
        fail(errors, "privacy_missing")
    else:
        for key in ("raw_boot_id_persisted", "raw_mount_source_persisted", "raw_journal_persisted"):
            if privacy.get(key) is not False:
                fail(errors, f"privacy_flag_not_false:{key}")


def validate(run_dir: Path | None, boot_state: Path | None, *, expect_source: str) -> dict[str, Any]:
    errors: list[str] = []
    if run_dir is not None:
        boot_path = run_dir / DEFAULT_BOOT_STATE
        files = evidence_files(run_dir)
        validate_manifest(run_dir, errors)
        adoption = {}
        for name in ("launcher-adoption.json", "adoption-probe.json", "player-runtime-adoption.json"):
            candidate = run_dir / name
            if candidate.is_file():
                adoption = load_json(candidate, errors)
                break
    else:
        if boot_state is None:
            raise RuntimeError("boot_state required without run_dir")
        boot_path = boot_state
        files = [boot_state]
        adoption = {}
    if not boot_path.is_file():
        fail(errors, "boot_state_missing")
        data: dict[str, Any] = {}
    else:
        data = load_json(boot_path, errors)
        validate_boot_state(data, errors, expect_source=expect_source, adoption=adoption)
    for hit in scan_leaks(files):
        fail(errors, f"privacy_leak:{hit}")
    return {
        "passed": not errors,
        "errors": errors,
        "boot_state": str(boot_path),
    }


def write_fixture(path: Path, *, source: str = "fallback") -> None:
    data = {
        "schema": SCHEMA,
        "boot": {
            "pre_boot_id_sha256_12": "0" * 12,
            "post_boot_id_sha256_12": "1" * 12,
            "boot_id_changed": True,
            "pre_btime": 100,
            "post_btime": 200,
            "btime_changed": True,
            "post_uptime_seconds": 42.0,
            "post_uptime_bucket": "lt_5m",
        },
        "mounts": {
            "root": {"found": True, "target": "/", "fstype": "ext4", "source_kind": "block"},
            "data": {"found": True, "target": "/", "fstype": "ext4", "source_kind": "block"},
            "data_same_device_as_root": True,
            "data_mount_claim": "rootfs_directory",
        },
        "systemd": {
            "active_state": "active",
            "sub_state": "running",
            "nrestarts": 0,
            "requires_mounts_for": ["/data"],
            "requires_data_mount": True,
            "after_contains_local_fs": True,
            "exec_start_pre_reconcile_present": True,
            "critical_chain": {"contains_local_fs": True, "collected": True},
        },
        "player_runtime": {
            "current_present": source == "data",
            "previous_present": False,
            "data_current_kiosk_present": source == "data",
            "data_current_marker_verified": source == "data",
            "data_current_marker_reason": "verified" if source == "data" else "no_data_current_kiosk",
            "fallback_kiosk_present": True,
            "selected_source": source,
        },
        "update_safety": {
            "included": True,
            "public_player_runtime_rollback_rc": 44,
            "public_player_runtime_reconcile_rc": 44,
            "boot_player_runtime_reconcile_rc": 0,
            "public_kiosky_player_rollback_rc": 44,
        },
        "privacy": {
            "raw_boot_id_persisted": False,
            "raw_mount_source_persisted": False,
            "raw_journal_persisted": False,
        },
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_adoption_fixture(path: Path) -> None:
    data = {
        "schema": "dadooh.c18.player_runtime.adoption.v1",
        "passed": True,
        "selected_source": "data",
        "marker_valid": True,
        "running_identity_matches_marker": True,
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        boot_path = root / DEFAULT_BOOT_STATE
        write_fixture(boot_path)
        result = validate(root, None, expect_source="fallback")
        if not result["passed"]:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 1

        bad = json.loads(boot_path.read_text(encoding="utf-8"))
        bad["boot"]["boot_id_changed"] = False
        boot_path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
        result = validate(root, None, expect_source="fallback")
        if result["passed"] or "boot_id_not_changed" not in result["errors"]:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 1

        write_fixture(boot_path)
        bad = json.loads(boot_path.read_text(encoding="utf-8"))
        bad["boot"]["pre_boot_id_sha256_12"] = bad["boot"]["post_boot_id_sha256_12"]
        bad["boot"]["boot_id_changed"] = True
        boot_path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
        result = validate(root, None, expect_source="fallback")
        if result["passed"] or "boot_id_not_changed" not in result["errors"]:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 1

        write_fixture(boot_path)
        bad = json.loads(boot_path.read_text(encoding="utf-8"))
        bad["boot"]["pre_btime"] = bad["boot"]["post_btime"]
        bad["boot"]["btime_changed"] = True
        boot_path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
        result = validate(root, None, expect_source="fallback")
        if result["passed"] or "btime_not_changed" not in result["errors"]:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 1

        write_fixture(boot_path, source="data")
        write_adoption_fixture(root / "launcher-adoption.json")
        result = validate(root, None, expect_source="data")
        if not result["passed"]:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 1

        (root / "launcher-adoption.json").unlink()
        result = validate(root, None, expect_source="data")
        if result["passed"] or "adoption_probe_missing" not in result["errors"]:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 1
        write_adoption_fixture(root / "launcher-adoption.json")

        missing_pre = json.loads(boot_path.read_text(encoding="utf-8"))
        missing_pre["boot"]["pre_boot_id_sha256_12"] = None
        boot_path.write_text(json.dumps(missing_pre) + "\n", encoding="utf-8")
        result = validate(root, None, expect_source="data")
        if result["passed"] or "pre_boot_id_hash_missing" not in result["errors"]:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 1
        write_fixture(boot_path, source="data")

        (root / "leak.txt").write_text("api_key=secret\n", encoding="utf-8")
        result = validate(root, None, expect_source="data")
        if result["passed"] or not any(item.startswith("privacy_leak") for item in result["errors"]):
            print(json.dumps(result, indent=2, sort_keys=True))
            return 1

        (root / "leak.txt").write_text("PARTUUID=abcd-1234 /dev/disk/by-uuid/private /dev/mmcblk0p2 12345678-1234-1234-1234-123456789abc\n", encoding="utf-8")
        result = validate(root, None, expect_source="data")
        if result["passed"] or not any("uuid_source" in item for item in result["errors"]):
            print(json.dumps(result, indent=2, sort_keys=True))
            return 1
    print(json.dumps({"self_test": True}, sort_keys=True))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir")
    parser.add_argument("--boot-state")
    parser.add_argument("--expect-selected-source", choices=("any", "fallback", "data"), default="any")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.run_dir and not args.boot_state:
        parser.error("provide --run-dir or --boot-state")
    result = validate(
        Path(args.run_dir) if args.run_dir else None,
        Path(args.boot_state) if args.boot_state else None,
        expect_source=args.expect_selected_source,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["passed"]:
        print("PASS")
    else:
        print("FAIL " + ",".join(result["errors"]))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
