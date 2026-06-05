#!/usr/bin/env python3
"""Collect sanitized C18 cold-boot state evidence.

Read-only by default. It does not read real config, media, network settings, or
private logs. Optional freeze probes must be requested explicitly because they
call updatectl verbs that are expected to fail closed with rc=44.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.coldboot_state.v2"
DEFAULT_SERVICE = "kiosky-player.service"
DEFAULT_UPDATECTL = "/opt/totem/bin/totem-updatectl"
DEFAULT_OUTPUT = "boot-state-public.json"
PLAYER_RUNTIME_MARKER_NAME = ".release_verified.json"
PLAYER_RUNTIME_MARKER_SCHEMA = "dadooh.c18.player_runtime.verified.v1"


def sha12(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()[:12]


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
    )


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def boot_id() -> str | None:
    return read_text(Path("/proc/sys/kernel/random/boot_id"))


def uptime_seconds() -> float | None:
    text = read_text(Path("/proc/uptime"))
    if not text:
        return None
    try:
        return float(text.split()[0])
    except (IndexError, ValueError):
        return None


def boot_time() -> int | None:
    text = read_text(Path("/proc/stat"))
    if not text:
        return None
    for line in text.splitlines():
        if line.startswith("btime "):
            try:
                return int(line.split()[1])
            except (IndexError, ValueError):
                return None
    return None


def uptime_bucket(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds < 300:
        return "lt_5m"
    if seconds < 900:
        return "lt_15m"
    return "gte_15m"


def source_kind(source: str | None) -> str:
    if not source:
        return "unknown"
    if source.startswith("/dev/"):
        return "block"
    if "UUID=" in source or "PARTUUID=" in source:
        return "uuid"
    if source in {"overlay", "tmpfs", "rootfs"}:
        return source
    return "other"


def safe_mount_entry(target: str) -> dict[str, Any]:
    proc = run(["findmnt", "-J", "-T", target, "-o", "TARGET,SOURCE,FSTYPE,OPTIONS"], timeout=10)
    entry: dict[str, Any] = {
        "target": target,
        "found": proc.returncode == 0,
    }
    if proc.returncode != 0:
        entry["error"] = "findmnt_failed"
        return entry
    try:
        data = json.loads(proc.stdout)
        filesystems = data.get("filesystems") or []
        raw = filesystems[0] if filesystems else {}
    except (json.JSONDecodeError, IndexError, TypeError):
        entry["error"] = "findmnt_parse_failed"
        return entry
    source = str(raw.get("source") or "")
    options = str(raw.get("options") or "")
    option_set = {item.strip() for item in options.split(",") if item.strip()}
    entry.update({
        "target": raw.get("target") or target,
        "fstype": raw.get("fstype"),
        "source_kind": source_kind(source),
        "source_sha256_12": sha12(source) if source else None,
        "read_only": "ro" in option_set,
        "read_write": "rw" in option_set,
    })
    return entry


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hash(root: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == PLAYER_RUNTIME_MARKER_NAME:
            continue
        try:
            st = path.lstat()
        except OSError:
            continue
        if path.is_dir():
            continue
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"unsupported_release_member:{rel}")
        hasher.update(rel.encode("utf-8") + b"\0")
        hasher.update(sha256_file(path).encode("ascii") + b"\0")
    return hasher.hexdigest()


def verify_player_runtime_marker(current: Path) -> dict[str, Any]:
    marker_path = current / PLAYER_RUNTIME_MARKER_NAME
    out: dict[str, Any] = {
        "data_current_marker_present": marker_path.is_file(),
        "data_current_marker_verified": False,
        "data_current_marker_reason": "missing",
    }
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if not isinstance(marker, dict):
            out["data_current_marker_reason"] = "not_object"
            return out
        if marker.get("schema") != PLAYER_RUNTIME_MARKER_SCHEMA:
            out["data_current_marker_reason"] = "schema"
            return out
        if marker.get("verdict") != "verified":
            out["data_current_marker_reason"] = "verdict"
            return out
        kiosk = current / "kiosk.py"
        if not kiosk.is_file():
            out["data_current_marker_reason"] = "kiosk_missing"
            return out
        kiosk_sha = sha256_file(kiosk)
        current_tree = tree_hash(current)
        if marker.get("kiosk_py_sha256") != kiosk_sha:
            out["data_current_marker_reason"] = "kiosk_sha_mismatch"
            return out
        if marker.get("tree_sha256") != current_tree:
            out["data_current_marker_reason"] = "tree_sha_mismatch"
            return out
        out.update({
            "data_current_marker_verified": True,
            "data_current_marker_reason": "verified",
            "data_current_marker_version": marker.get("version"),
            "data_current_kiosk_py_sha256": kiosk_sha,
            "data_current_tree_sha256": current_tree,
        })
    except Exception as exc:
        out["data_current_marker_reason"] = f"invalid:{type(exc).__name__}"
    return out


def same_device(left: Path, right: Path) -> bool | None:
    try:
        return left.stat().st_dev == right.stat().st_dev
    except OSError:
        return None


def systemctl_show(service: str) -> dict[str, Any]:
    keys = [
        "ActiveState",
        "SubState",
        "NRestarts",
        "RequiresMountsFor",
        "After",
        "DropInPaths",
        "ExecStartPre",
    ]
    proc = run(["systemctl", "show", service, *sum([["-p", key] for key in keys], [])], timeout=10)
    out: dict[str, Any] = {
        "service": service,
        "show_rc": proc.returncode,
    }
    raw: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            raw[key] = value
    requires = raw.get("RequiresMountsFor", "")
    after = raw.get("After", "")
    exec_pre = raw.get("ExecStartPre", "")
    out.update({
        "active_state": raw.get("ActiveState"),
        "sub_state": raw.get("SubState"),
        "nrestarts": parse_int(raw.get("NRestarts")),
        "requires_mounts_for": split_words(requires),
        "requires_data_mount": "/data" in split_words(requires),
        "after_contains_local_fs": "local-fs.target" in split_words(after),
        "dropin_count": len(split_words(raw.get("DropInPaths", ""))),
        "exec_start_pre_reconcile_present": "reconcile --component player-runtime" in exec_pre,
    })
    return out


def split_words(value: str | None) -> list[str]:
    if not value:
        return []
    return [item for item in re.split(r"\s+", value.strip()) if item]


def parse_int(value: str | None) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def critical_chain(service: str) -> dict[str, Any]:
    proc = run(["systemd-analyze", "critical-chain", service], timeout=15)
    text = proc.stdout if proc.returncode == 0 else ""
    return {
        "rc": proc.returncode,
        "contains_local_fs": "local-fs.target" in text,
        "contains_data_mount": "data.mount" in text,
        "collected": proc.returncode == 0,
    }


def player_runtime_paths() -> dict[str, Any]:
    base = Path("/data/player-runtime")
    current = base / "current"
    previous = base / "previous"
    opt = Path("/opt/totem/player-runtime/kiosk.py")
    current_kiosk_present = (current / "kiosk.py").is_file()
    marker = verify_player_runtime_marker(current) if current_kiosk_present else {
        "data_current_marker_present": False,
        "data_current_marker_verified": False,
        "data_current_marker_reason": "no_data_current_kiosk",
    }
    return {
        "data_base_present": base.exists(),
        "current_present": current.exists() or current.is_symlink(),
        "previous_present": previous.exists() or previous.is_symlink(),
        "data_current_kiosk_present": current_kiosk_present,
        **marker,
        "fallback_kiosk_present": opt.is_file(),
        "selected_source": "data" if marker.get("data_current_marker_verified") else "fallback",
    }


def freeze_probe(updatectl_path: str) -> dict[str, Any]:
    updatectl = Path(updatectl_path)
    if not updatectl.exists():
        return {"included": False, "reason": "updatectl_missing"}
    probes = {
        "public_player_runtime_rollback_rc": [str(updatectl), "rollback", "--component", "player-runtime"],
        "public_player_runtime_reconcile_rc": [
            str(updatectl),
            "reconcile",
            "--component",
            "player-runtime",
        ],
        "boot_player_runtime_reconcile_rc": [
            "/usr/bin/env",
            "C18_PLAYER_RUNTIME_RECONCILE=1",
            str(updatectl),
            "reconcile",
            "--component",
            "player-runtime",
            "--allow-player-runtime-maintenance",
        ],
        "public_kiosky_player_rollback_rc": [str(updatectl), "rollback", "--component", "kiosky-player"],
    }
    out: dict[str, Any] = {"included": True}
    for key, cmd in probes.items():
        proc = run(cmd, timeout=20)
        out[key] = proc.returncode
    return out


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    current_boot = boot_id()
    current_uptime = uptime_seconds()
    current_btime = boot_time()
    root_mount = safe_mount_entry("/")
    data_mount = safe_mount_entry("/data")
    data_same_device = same_device(Path("/"), Path("/data"))
    if data_mount.get("target") == "/" or data_same_device is True:
        data_claim = "rootfs_directory"
    elif data_mount.get("target") == "/data":
        data_claim = "separate_mount"
    else:
        data_claim = "unknown"
    pre_boot_hash = sha12(args.pre_boot_id)
    post_boot_hash = sha12(current_boot)
    report = {
        "schema": SCHEMA,
        "captured_at_unix": int(time.time()),
        "boot": {
            "pre_boot_id_sha256_12": pre_boot_hash,
            "post_boot_id_sha256_12": post_boot_hash,
            "boot_id_changed": None if pre_boot_hash is None else pre_boot_hash != post_boot_hash,
            "pre_btime": args.pre_btime,
            "post_btime": current_btime,
            "btime_changed": None if args.pre_btime is None or current_btime is None else args.pre_btime != current_btime,
            "post_uptime_seconds": current_uptime,
            "post_uptime_bucket": uptime_bucket(current_uptime),
        },
        "mounts": {
            "root": root_mount,
            "data": data_mount,
            "data_same_device_as_root": data_same_device,
            "data_mount_claim": data_claim,
        },
        "systemd": {
            **systemctl_show(args.service),
            "critical_chain": critical_chain(args.service),
        },
        "player_runtime": player_runtime_paths(),
        "update_safety": {"included": False},
        "privacy": {
            "raw_boot_id_persisted": False,
            "raw_mount_source_persisted": False,
            "raw_journal_persisted": False,
        },
    }
    if args.include_freeze_probes:
        report["update_safety"] = freeze_probe(args.updatectl)
    return report


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--pre-boot-id")
    parser.add_argument("--pre-btime", type=int)
    parser.add_argument("--include-freeze-probes", action="store_true")
    parser.add_argument("--updatectl", default=DEFAULT_UPDATECTL)
    args = parser.parse_args(argv)
    report = build_report(args)
    write_report(report, Path(args.output))
    print(json.dumps({"output": args.output, "schema": SCHEMA}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
