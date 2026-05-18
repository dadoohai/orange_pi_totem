#!/usr/bin/env python3
"""Prepare the C17.8 local totem simulation sandbox.

Default mode is repo_overlay: scripts from this repository are exposed through
the simulated /opt/totem layout without extracting an appliance image.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SANDBOX = REPO_ROOT / ".sim" / "totem"
DEFAULT_IMAGE_DIR = Path("/home/builder/totem-os/armbian-build-v25.11/output/images")
TOTEM_CORE_VERSION = "c17.6-environment-input-20260514T211247Z"

CORE_FILES = (
    "totem_setup_visual_wizard.py",
    "totem_wifi_nm_adapter.py",
    "totem_visual_splash.py",
    "totem_status_aggregate.py",
    "totem_status_render_preview.py",
    "totem_config_contract_validate.py",
    "totem_open_settings_session.sh",
    "totem_visual_tty_guard.sh",
    "totem_firstboot_gate.sh",
    "totem_status_renderer.sh",
    "totem_settings_trigger.py",
    "totem_open_settings_cleanup.sh",
    "totem_visual_setup_writer_handoff.py",
    "totem_config_writer_real.py",
    "totem_setup_minimal_server.py",
    "totem_setup_local_wizard.py",
    "kiosky_service_launcher.sh",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare .sim/totem sandbox for C17.8.")
    parser.add_argument("--sandbox", "--out-dir", dest="sandbox", type=Path, default=DEFAULT_SANDBOX)
    parser.add_argument("--mode", choices=("repo_overlay", "image_copyout"), default="repo_overlay")
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--reset", action="store_true", help="Remove the existing sandbox first")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of key=value lines")
    return parser.parse_args()


def safe_reset(path: Path) -> None:
    resolved = path.resolve()
    allowed = (REPO_ROOT / ".sim").resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise RuntimeError(f"unsafe_sandbox_reset_path:{resolved}") from exc
    if resolved.exists():
        shutil.rmtree(resolved)


def ensure_layout(sandbox: Path) -> list[Path]:
    paths = [
        sandbox / "data",
        sandbox / "run",
        sandbox / "tmp",
        sandbox / "opt" / "totem" / "bin",
        sandbox / "opt" / "totem" / "core-fallback" / "bin",
        sandbox / "data" / "core" / "totem" / "releases",
        sandbox / "evidence",
    ]
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    return paths


def replace_symlink(target: Path | str, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        if link.is_dir() and not link.is_symlink():
            shutil.rmtree(link)
        else:
            link.unlink()
    os.symlink(str(target), str(link))


def repo_overlay(sandbox: Path) -> dict[str, Any]:
    created_paths = ensure_layout(sandbox)
    fallback_bin = sandbox / "opt" / "totem" / "core-fallback" / "bin"
    wrappers_bin = sandbox / "opt" / "totem" / "bin"
    wrapper_py = REPO_ROOT / "scripts" / "board" / "totem_core_exec.py"
    wrapper_sh = REPO_ROOT / "scripts" / "board" / "totem_core_exec.sh"

    for name in CORE_FILES:
        source = REPO_ROOT / "scripts" / "board" / name
        if not source.is_file():
            raise RuntimeError(f"missing_core_file:{name}")
        replace_symlink(source, fallback_bin / name)
        wrapper = wrapper_py if name.endswith(".py") else wrapper_sh
        replace_symlink(wrapper, wrappers_bin / name)

    replace_symlink(wrapper_py, wrappers_bin / "totem_core_exec.py")
    replace_symlink(wrapper_sh, wrappers_bin / "totem_core_exec.sh")

    return {
        "sandbox_created": True,
        "sandbox_mode": "repo_overlay",
        "paths_created": [str(path) for path in created_paths],
        "fallback_files": len(CORE_FILES),
        "wrapper_files": len(CORE_FILES),
    }


def find_c17_7_image(image_dir: Path) -> Path | None:
    if not image_dir.is_dir():
        return None
    candidates = [
        path
        for path in image_dir.glob("*.img")
        if "c17-7" in path.name.lower() or "totem-core-embedded" in path.name.lower()
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


def copy_partition_private(image: Path, offset: int, length: int, tempdir: Path) -> Path:
    target = tempdir / "rootfs.ext4"
    with image.open("rb") as src, target.open("wb") as dst:
        os.chmod(target, 0o600)
        src.seek(offset)
        remaining = length
        while remaining:
            data = src.read(min(16 * 1024 * 1024, remaining))
            if not data:
                break
            dst.write(data)
            remaining -= len(data)
    return target


class DebugFs:
    def __init__(self, rootfs: Path) -> None:
        self.rootfs = rootfs

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

    def symlink_target(self, path: str) -> str:
        match = re.search(r'Fast link dest:\s+"([^"]*)"', self.stat(path))
        return match.group(1) if match else ""

    def dump(self, source: str, target: Path) -> bool:
        target.parent.mkdir(parents=True, exist_ok=True)
        output = self.run(f"dump -p {source} {target}")
        return "File not found" not in output and target.exists()


def image_copyout(sandbox: Path, image_dir: Path) -> dict[str, Any]:
    if not shutil.which("debugfs"):
        raise RuntimeError("debugfs_missing")
    image = find_c17_7_image(image_dir)
    if image is None:
        raise RuntimeError("c17_7_image_missing")

    created_paths = ensure_layout(sandbox)
    tempdir = Path(tempfile.mkdtemp(prefix="dadooh-c17-8-image-copyout-", dir="/tmp"))
    os.chmod(tempdir, 0o700)
    try:
        offset, length = parse_mbr_linux_partition(image)
        rootfs = copy_partition_private(image, offset, length, tempdir)
        debug = DebugFs(rootfs)
        release_bin = sandbox / "data" / "core" / "totem" / "releases" / TOTEM_CORE_VERSION / "bin"
        fallback_bin = sandbox / "opt" / "totem" / "core-fallback" / "bin"
        wrappers_bin = sandbox / "opt" / "totem" / "bin"

        copied = 0
        for name in CORE_FILES:
            if debug.dump(f"/data/core/totem/releases/{TOTEM_CORE_VERSION}/bin/{name}", release_bin / name):
                copied += 1
            if debug.dump(f"/opt/totem/core-fallback/bin/{name}", fallback_bin / name):
                copied += 1
            if debug.dump(f"/opt/totem/bin/{name}", wrappers_bin / name):
                copied += 1
        debug.dump(
            f"/data/core/totem/releases/{TOTEM_CORE_VERSION}/health/totem-core-health.json",
            sandbox / "data" / "core" / "totem" / "releases" / TOTEM_CORE_VERSION / "health" / "totem-core-health.json",
        )
        debug.dump(
            f"/data/core/totem/releases/{TOTEM_CORE_VERSION}/manifest-fragment/totem-core.json",
            sandbox / "data" / "core" / "totem" / "releases" / TOTEM_CORE_VERSION / "manifest-fragment" / "totem-core.json",
        )
        debug.dump("/data/core/totem/state.json", sandbox / "data" / "core" / "totem" / "state.json")

        current_target = debug.symlink_target("/data/core/totem/current") or f"releases/{TOTEM_CORE_VERSION}"
        replace_symlink(current_target, sandbox / "data" / "core" / "totem" / "current")

        if copied < len(CORE_FILES):
            raise RuntimeError(f"image_copyout_incomplete:copied={copied}")

        return {
            "sandbox_created": True,
            "sandbox_mode": "image_copyout",
            "paths_created": [str(path) for path in created_paths],
            "source_image": str(image),
            "files_copied": copied,
        }
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def main() -> int:
    args = parse_args()
    sandbox = args.sandbox.resolve()
    if args.reset:
        safe_reset(sandbox)

    result: dict[str, Any]
    try:
        if args.mode == "image_copyout":
            try:
                result = image_copyout(sandbox, args.image_dir)
            except Exception as exc:
                fallback = repo_overlay(sandbox)
                fallback["sandbox_mode"] = "repo_overlay"
                fallback["image_copyout_attempted"] = True
                fallback["image_copyout_error"] = str(exc)
                result = fallback
        else:
            result = repo_overlay(sandbox)
    except Exception as exc:
        result = {
            "sandbox_created": False,
            "sandbox_mode": "failed",
            "error": str(exc),
            "paths_created": [],
        }

    result.update(
        {
            "schema": "dadooh.c17_8.sim_sandbox.v1",
            "created_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sandbox": str(sandbox),
            "secrets_published": False,
        }
    )
    evidence_path = sandbox / "evidence" / "prepare-sandbox.json"
    try:
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        pass

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"sandbox_created={str(result['sandbox_created']).lower()}")
        print(f"sandbox_mode={result['sandbox_mode']}")
        print(f"sandbox={sandbox}")
        print("paths_created=" + ",".join(result.get("paths_created", [])))
    return 0 if result["sandbox_created"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
