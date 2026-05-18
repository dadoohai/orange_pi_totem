#!/usr/bin/env python3
"""C17.8 read-only boot artifact comparison for C17.4.2 vs C17.7 images.

The script never mounts an image and never opens the image read-write.  Because
debugfs cannot address an ext4 filesystem at an MBR partition offset directly
without a loop device, the ext4 partition is copied into a private temporary
file and inspected read-only with debugfs.  The temporary copy is removed before
exit.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_IMAGE_DIR = Path("/home/builder/totem-os/armbian-build-v25.11/output/images")
RUNS_DIR = Path("docs/evidence/candidate-a/runs")
RUN_NAME = "c17-8-simulation-lab-mvp"

C17_4_2_TOKENS = ("c17-4-2", "settings-restore-clean")
C17_7_TOKENS = ("c17-7", "totem-core-embedded")

MARKER_PATHS = (
    "/etc/dadooh/c17-4-2-settings-restore-clean-image",
    "/etc/dadooh/c17-7-totem-core-embedded-image",
)

SYSTEMD_PATHS = (
    "/etc/systemd/system/dadooh-visual-splash.service",
    "/etc/systemd/system/kiosky-player.service",
    "/etc/systemd/system/totem-open-settings.service",
    "/etc/systemd/system/totem-visual-tty-guard.service",
    "/etc/systemd/system/totem-firstboot-gate.service",
    "/etc/systemd/system/totem-update-agent.service",
    "/etc/systemd/system/totem-update-agent.timer",
    "/etc/systemd/system/multi-user.target.wants/dadooh-visual-splash.service",
    "/etc/systemd/system/multi-user.target.wants/kiosky-player.service",
    "/etc/systemd/system/multi-user.target.wants/totem-firstboot-gate.service",
    "/etc/systemd/system/timers.target.wants/totem-update-agent.timer",
    "/lib/systemd/system/armbian-firstrun.service",
)

TOTEM_CORE_VERSION = "c17.6-environment-input-20260514T211247Z"
TOTEM_CORE_PATHS = (
    "/data/core/totem/current",
    "/data/core/totem/previous",
    "/data/core/totem/state.json",
    f"/data/core/totem/releases/{TOTEM_CORE_VERSION}/health/totem-core-health.json",
    f"/data/core/totem/releases/{TOTEM_CORE_VERSION}/manifest-fragment/totem-core.json",
    f"/data/core/totem/releases/{TOTEM_CORE_VERSION}/bin/totem_setup_visual_wizard.py",
    f"/data/core/totem/releases/{TOTEM_CORE_VERSION}/bin/totem_visual_splash.py",
    "/opt/totem/bin/totem_setup_visual_wizard.py",
    "/opt/totem/bin/totem_visual_splash.py",
    "/opt/totem/bin/totem_open_settings_session.sh",
    "/opt/totem/core-fallback/bin/totem_setup_visual_wizard.py",
    "/opt/totem/core-fallback/bin/totem_visual_splash.py",
    "/opt/totem/core-fallback/bin/totem_open_settings_session.sh",
)


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare C17.4.2 and C17.7 Orange Pi image boot artifacts."
    )
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary")
    return parser.parse_args()


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_region(path: Path, start: int, length: int) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        fh.seek(start)
        remaining = length
        while remaining > 0:
            block = fh.read(min(1024 * 1024, remaining))
            if not block:
                break
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def find_image(image_dir: Path, tokens: tuple[str, ...]) -> Path | None:
    if not image_dir.is_dir():
        return None
    candidates = [
        path
        for path in image_dir.glob("*.img")
        if any(token in path.name.lower() for token in tokens)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: (p.stat().st_mtime, p.name))


def parse_mbr_linux_partition(image: Path) -> tuple[int, int]:
    with image.open("rb") as fh:
        mbr = fh.read(512)
    if len(mbr) != 512 or mbr[510:512] != b"\x55\xaa":
        raise RuntimeError("image_partition_table_invalid")
    candidates: list[tuple[int, int]] = []
    for idx in range(4):
        entry = mbr[446 + idx * 16 : 446 + (idx + 1) * 16]
        ptype = entry[4]
        start = struct.unpack_from("<I", entry, 8)[0]
        sectors = struct.unpack_from("<I", entry, 12)[0]
        if ptype == 0x83 and start and sectors:
            candidates.append((start * 512, sectors * 512))
    if len(candidates) != 1:
        raise RuntimeError("image_linux_partition_not_unique")
    return candidates[0]


def sfdisk_table(image: Path) -> dict[str, Any]:
    proc = run(["sfdisk", "-J", str(image)])
    if proc.returncode == 0:
        try:
            data = json.loads(proc.stdout)
            return data.get("partitiontable") or {}
        except json.JSONDecodeError:
            pass
    offset, length = parse_mbr_linux_partition(image)
    return {
        "label": "dos",
        "unit": "sectors",
        "sectorsize": 512,
        "partitions": [{"start": offset // 512, "size": length // 512, "type": "83"}],
        "fallback_parser": "mbr",
    }


def normalise_partition_table(table: dict[str, Any]) -> dict[str, Any]:
    partitions = []
    for part in table.get("partitions") or []:
        partitions.append(
            {
                "start": part.get("start"),
                "size": part.get("size"),
                "type": str(part.get("type")),
                "bootable": bool(part.get("bootable", False)),
            }
        )
    return {
        "label": table.get("label"),
        "unit": table.get("unit"),
        "sectorsize": table.get("sectorsize"),
        "partitions": partitions,
    }


def linux_partition_from_table(table: dict[str, Any]) -> tuple[int, int]:
    sector_size = int(table.get("sectorsize") or 512)
    candidates: list[tuple[int, int]] = []
    for part in table.get("partitions") or []:
        if str(part.get("type")).lower() in {"83", "linux"}:
            start = int(part["start"]) * sector_size
            length = int(part["size"]) * sector_size
            candidates.append((start, length))
    if len(candidates) != 1:
        raise RuntimeError("image_linux_partition_not_unique")
    return candidates[0]


def copy_partition_private(image: Path, offset: int, length: int, tempdir: Path) -> Path:
    target = tempdir / f"{image.stem}.rootfs.ext4"
    chunk_size = 16 * 1024 * 1024
    with image.open("rb") as src, target.open("wb") as dst:
        os.chmod(target, 0o600)
        src.seek(offset)
        remaining = length
        while remaining:
            data = src.read(min(chunk_size, remaining))
            if not data:
                break
            dst.write(data)
            remaining -= len(data)
    return target


class DebugFs:
    def __init__(self, rootfs: Path, dump_dir: Path) -> None:
        self.rootfs = rootfs
        self.dump_dir = dump_dir

    def run(self, request: str) -> str:
        proc = subprocess.run(
            ["debugfs", "-R", request, str(self.rootfs)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return proc.stdout or ""

    def stat(self, path: str) -> str:
        output = self.run(f"stat {path}")
        if "File not found" in output or "Inode:" not in output:
            return ""
        return output

    def exists(self, path: str) -> bool:
        return bool(self.stat(path))

    def file_type(self, path: str) -> str:
        stat = self.stat(path)
        match = re.search(r"Type:\s+([A-Za-z0-9_-]+)", stat)
        return match.group(1) if match else "missing"

    def symlink_target(self, path: str) -> str:
        stat = self.stat(path)
        match = re.search(r'Fast link dest:\s+"([^"]*)"', stat)
        return match.group(1) if match else ""

    def file_size(self, path: str) -> int:
        stat = self.stat(path)
        match = re.search(r"\bSize:\s+(\d+)", stat)
        return int(match.group(1)) if match else -1

    def dump_file(self, path: str) -> Path | None:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.strip("/")) or "root"
        target = self.dump_dir / f"{safe}.dump"
        output = self.run(f"dump -p {path} {target}")
        if "File not found" in output or not target.exists():
            return None
        os.chmod(target, 0o600)
        return target

    def read_text(self, path: str) -> str:
        output = self.run(f"cat {path}")
        if "File not found" in output:
            return ""
        lines = output.splitlines()
        if lines and lines[0].startswith("debugfs "):
            lines = lines[1:]
        return "\n".join(lines)

    def resolve_path(self, path: str) -> str:
        current = path
        for _ in range(8):
            if self.file_type(current) != "symlink":
                return current
            target = self.symlink_target(current)
            if not target:
                return current
            if target.startswith("/"):
                current = target
            else:
                current = str(Path(current).parent / target)
        return current

    def list_dir(self, path: str) -> list[dict[str, Any]]:
        output = self.run(f"ls -p {path}")
        entries: list[dict[str, Any]] = []
        for line in output.splitlines():
            if not line.startswith("/"):
                continue
            parts = line.split("/")
            if len(parts) < 6:
                continue
            name = parts[5]
            if name in {"", ".", ".."}:
                continue
            mode = parts[2]
            if mode.startswith("04"):
                file_type = "directory"
            elif mode.startswith("10"):
                file_type = "regular"
            elif mode.startswith("12"):
                file_type = "symlink"
            else:
                file_type = "other"
            size = -1
            if len(parts) > 6 and parts[6].isdigit():
                size = int(parts[6])
            entries.append(
                {
                    "path": str(Path(path) / name),
                    "name": name,
                    "type": file_type,
                    "mode": mode,
                    "size": size,
                }
            )
        return entries

    def recursive_entries(self, root: str, max_depth: int = 6) -> dict[str, dict[str, Any]]:
        if not self.exists(root):
            return {}
        found: dict[str, dict[str, Any]] = {}
        queue: list[tuple[str, int]] = [(root, 0)]
        while queue:
            directory, depth = queue.pop(0)
            for entry in self.list_dir(directory):
                path = entry["path"]
                found[path] = entry
                if entry["type"] == "directory" and depth < max_depth:
                    queue.append((path, depth + 1))
        return found

    def summary(self, path: str, resolve_regular_symlink: bool = False) -> dict[str, Any]:
        file_type = self.file_type(path)
        if file_type == "missing":
            return {"type": "missing", "exists": False}
        result: dict[str, Any] = {
            "type": file_type,
            "exists": True,
            "size": self.file_size(path),
        }
        if file_type == "symlink":
            target = self.symlink_target(path)
            result["symlink_target"] = target
            if resolve_regular_symlink:
                resolved = self.resolve_path(path)
                result["resolved_path"] = resolved
                resolved_type = self.file_type(resolved)
                result["resolved_type"] = resolved_type
                if resolved_type == "regular":
                    dumped = self.dump_file(resolved)
                    if dumped:
                        result["resolved_size"] = dumped.stat().st_size
                        result["resolved_sha256"] = sha256_file(dumped)
            return result
        if file_type == "regular":
            dumped = self.dump_file(path)
            if dumped:
                result["sha256"] = sha256_file(dumped)
        return result


def path_map(debug: DebugFs, paths: list[str], resolve_symlinks: bool = False) -> dict[str, Any]:
    return {path: debug.summary(path, resolve_regular_symlink=resolve_symlinks) for path in paths}


def boot_file_groups(debug: DebugFs) -> dict[str, Any]:
    boot_entries = debug.recursive_entries("/boot", max_depth=1)
    boot_paths = sorted(boot_entries)
    boot_files = path_map(debug, boot_paths, resolve_symlinks=True)

    def basenames_matching(patterns: tuple[str, ...]) -> list[str]:
        out = []
        for path in boot_paths:
            name = Path(path).name
            if any(re.fullmatch(pattern, name) for pattern in patterns):
                out.append(path)
        return sorted(out)

    kernel_paths = basenames_matching((r"Image", r"zImage", r"vmlinuz.*"))
    initrd_paths = basenames_matching((r"uInitrd.*", r"initrd\.img.*"))
    boot_script_paths = [
        path
        for path in (
            "/boot/boot.cmd",
            "/boot/boot.scr",
            "/boot/armbianEnv.txt",
            "/boot/extlinux/extlinux.conf",
            "/boot/config.txt",
        )
        if debug.exists(path)
    ]
    config_paths = sorted(path for path in boot_paths if Path(path).name.startswith("config-"))

    dtb_roots = [
        path
        for path, entry in boot_entries.items()
        if entry["type"] == "directory" and Path(path).name.startswith("dtb")
    ]
    dtb_entries: dict[str, dict[str, Any]] = {}
    for root in dtb_roots:
        dtb_entries.update(debug.recursive_entries(root, max_depth=8))
    dtb_paths = sorted(path for path, entry in dtb_entries.items() if entry["type"] in {"regular", "symlink"})

    return {
        "boot_files": boot_files,
        "kernel": path_map(debug, kernel_paths, resolve_symlinks=True),
        "initrd": path_map(debug, initrd_paths, resolve_symlinks=True),
        "boot_script": path_map(debug, boot_script_paths, resolve_symlinks=True),
        "boot_config": path_map(debug, config_paths, resolve_symlinks=True),
        "dtb": path_map(debug, dtb_paths, resolve_symlinks=True),
    }


def marker_summary(debug: DebugFs) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in MARKER_PATHS:
        summary = debug.summary(path)
        if summary.get("type") == "regular":
            text = debug.read_text(path)
            summary["line_count"] = len(text.splitlines())
            summary["contains_totem_core"] = "totem_core" in text
            summary["contains_kernel_reused"] = "kernel_reused=true" in text
            summary["contains_c17_7_status_gate"] = "ready_for_c18_player_audit=false" in text
        result[path] = summary
    return result


def inspect_image(label: str, image: Path) -> dict[str, Any]:
    if not shutil.which("debugfs"):
        raise RuntimeError("debugfs_missing")
    table = sfdisk_table(image)
    offset, length = linux_partition_from_table(table)
    tempdir = Path(tempfile.mkdtemp(prefix=f"dadooh-{label}-bootdiff-", dir="/tmp"))
    os.chmod(tempdir, 0o700)
    try:
        rootfs = copy_partition_private(image, offset, length, tempdir)
        debug = DebugFs(rootfs, tempdir)
        boot_groups = boot_file_groups(debug)
        systemd = path_map(debug, list(SYSTEMD_PATHS), resolve_symlinks=True)
        totem_core = path_map(debug, list(TOTEM_CORE_PATHS), resolve_symlinks=True)
        wrapper_markers: dict[str, bool] = {}
        for path in (
            "/opt/totem/bin/totem_setup_visual_wizard.py",
            "/opt/totem/bin/totem_visual_splash.py",
            "/opt/totem/bin/totem_open_settings_session.sh",
        ):
            text = debug.read_text(path) if debug.file_type(path) == "regular" else ""
            wrapper_markers[path] = "TOTEM_CORE_EXEC_WRAPPER" in text
        return {
            "label": label,
            "image": str(image),
            "image_name": image.name,
            "image_size": image.stat().st_size,
            "image_sha256": sha256_file(image),
            "partition_table": normalise_partition_table(table),
            "rootfs_offset": offset,
            "rootfs_bytes": length,
            "mbr_sha256": sha256_region(image, 0, 512),
            "pre_partition_sha256_excluding_mbr": (
                sha256_region(image, 512, max(0, offset - 512)) if offset > 512 else ""
            ),
            "boot_directory_present": debug.exists("/boot"),
            "boot": boot_groups,
            "systemd_units": systemd,
            "markers": marker_summary(debug),
            "totem_core_paths": totem_core,
            "wrapper_markers": wrapper_markers,
        }
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def comparable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: comparable(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [comparable(v) for v in value]
    return value


def changed(a: Any, b: Any) -> bool | str:
    if a is None or b is None:
        return "unknown"
    return comparable(a) != comparable(b)


def group_changed(left: dict[str, Any], right: dict[str, Any], group: str) -> bool | str:
    try:
        return changed(left["boot"][group], right["boot"][group])
    except KeyError:
        return "unknown"


def classify(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    if left is None or right is None:
        return {
            "boot_partition_changed": "unknown",
            "uboot_changed": "unknown",
            "kernel_changed": "unknown",
            "dtb_changed": "unknown",
            "initrd_changed": "unknown",
            "boot_script_changed": "unknown",
            "rootfs_only_change": "unknown",
            "boot_risk_level": "unknown",
            "conclusion": "Image missing; boot artifact risk cannot be classified locally.",
        }

    boot_partition_changed = changed(left["partition_table"], right["partition_table"])
    uboot_changed = left["pre_partition_sha256_excluding_mbr"] != right["pre_partition_sha256_excluding_mbr"]
    kernel_changed = group_changed(left, right, "kernel")
    dtb_changed = group_changed(left, right, "dtb")
    initrd_changed = group_changed(left, right, "initrd")
    boot_script_changed = group_changed(left, right, "boot_script")

    critical = (boot_partition_changed, uboot_changed, kernel_changed, dtb_changed, initrd_changed, boot_script_changed)
    if any(item == "unknown" for item in critical):
        rootfs_only_change: bool | str = "unknown"
        boot_risk = "unknown"
    elif any(bool(item) for item in (uboot_changed, kernel_changed, dtb_changed, initrd_changed)):
        rootfs_only_change = False
        boot_risk = "high"
    elif bool(boot_partition_changed) or bool(boot_script_changed):
        rootfs_only_change = False
        boot_risk = "medium"
    else:
        rootfs_groups_changed = any(
            bool(changed(left.get(group), right.get(group)))
            for group in ("systemd_units", "markers", "totem_core_paths", "wrapper_markers")
        )
        rootfs_only_change = rootfs_groups_changed
        boot_risk = "low"

    if boot_risk == "low":
        conclusion = (
            "Boot-critical artifacts matched; observed delta is rootfs/userland. "
            "Hardware validation remains mandatory because C17.7 has not booted on Orange Pi."
        )
    elif boot_risk in {"medium", "high"}:
        conclusion = (
            "Boot-critical artifacts changed; local diff raises boot risk and Orange Pi "
            "hardware validation is mandatory before batch, dispatch or C18."
        )
    else:
        conclusion = "Local comparison was incomplete; Orange Pi hardware validation is mandatory."

    return {
        "boot_partition_changed": boot_partition_changed,
        "uboot_changed": uboot_changed,
        "kernel_changed": kernel_changed,
        "dtb_changed": dtb_changed,
        "initrd_changed": initrd_changed,
        "boot_script_changed": boot_script_changed,
        "rootfs_only_change": rootfs_only_change,
        "boot_risk_level": boot_risk,
        "conclusion": conclusion,
    }


def build_missing_result(args: argparse.Namespace, c17_4_2: Path | None, c17_7: Path | None) -> dict[str, Any]:
    classification = classify(None if c17_4_2 is None else {}, None if c17_7 is None else {})
    return {
        "schema": "dadooh.c17_8.boot_artifact_diff.v1",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "image_dir": str(args.image_dir),
        "image_missing": True,
        "c17_4_2_image_found": c17_4_2 is not None,
        "c17_7_image_found": c17_7 is not None,
        **classification,
        "images": {
            "c17_4_2": str(c17_4_2) if c17_4_2 else None,
            "c17_7": str(c17_7) if c17_7 else None,
        },
        "guardrails": {
            "mounted_rw": False,
            "image_written": False,
            "debugfs_readonly": True,
            "loop_device_used": False,
        },
    }


def main() -> int:
    args = parse_args()
    evidence_dir = args.evidence_dir or RUNS_DIR / f"{timestamp()}-{RUN_NAME}"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    c17_4_2 = find_image(args.image_dir, C17_4_2_TOKENS)
    c17_7 = find_image(args.image_dir, C17_7_TOKENS)

    if c17_4_2 is None or c17_7 is None:
        result = build_missing_result(args, c17_4_2, c17_7)
    else:
        left = inspect_image("c17_4_2", c17_4_2)
        right = inspect_image("c17_7", c17_7)
        classification = classify(left, right)
        result = {
            "schema": "dadooh.c17_8.boot_artifact_diff.v1",
            "created_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "image_dir": str(args.image_dir),
            "image_missing": False,
            "c17_4_2_image_found": True,
            "c17_7_image_found": True,
            **classification,
            "images": {
                "c17_4_2": left,
                "c17_7": right,
            },
            "notable_deltas": {
                "systemd_units_changed": changed(left["systemd_units"], right["systemd_units"]),
                "markers_changed": changed(left["markers"], right["markers"]),
                "totem_core_paths_changed": changed(left["totem_core_paths"], right["totem_core_paths"]),
                "wrapper_markers_changed": changed(left["wrapper_markers"], right["wrapper_markers"]),
            },
            "guardrails": {
                "mounted_rw": False,
                "image_written": False,
                "debugfs_readonly": True,
                "loop_device_used": False,
                "temporary_partition_copy_removed": True,
            },
        }

    out_path = evidence_dir / "boot-artifact-diff.json"
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps({
            "boot_artifact_diff_created": True,
            "output": str(out_path),
            "boot_risk_level": result["boot_risk_level"],
            "c17_4_2_image_found": result["c17_4_2_image_found"],
            "c17_7_image_found": result["c17_7_image_found"],
        }, sort_keys=True))
    else:
        print(f"boot_artifact_diff_created=true")
        print(f"output={out_path}")
        print(f"c17_4_2_image_found={str(result['c17_4_2_image_found']).lower()}")
        print(f"c17_7_image_found={str(result['c17_7_image_found']).lower()}")
        print(f"boot_risk_level={result['boot_risk_level']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
