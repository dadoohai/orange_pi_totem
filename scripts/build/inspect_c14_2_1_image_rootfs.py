#!/usr/bin/env python3
"""C14.2.1 - Offline validation of the shipping homologation rootfs.

Verifies that the C14.1.1 pull updater is embedded and that
totem-update-agent.timer is enabled in the image.  Uses debugfs to
inspect the ext4 partition without mounting it, so this runs as a
non-root user.

Usage:
  inspect_c14_2_1_image_rootfs.py <image.img>

Exit codes:
  0  all gates passed
  1  one or more gates failed
  2  bad invocation / unable to read partition

Output is a single JSON object on stdout — suitable for the evidence
README.  Never reads or prints private file contents.
"""
from __future__ import annotations

import argparse
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
from typing import Any, Dict, List, Optional, Tuple


def parse_mbr_linux_partition(image: Path) -> Tuple[int, int]:
    """Return (byte_offset, byte_length) of the largest Linux primary partition."""
    with image.open("rb") as fh:
        mbr = fh.read(512)
    if len(mbr) != 512 or mbr[510:512] != b"\x55\xaa":
        raise SystemExit("image_partition_table_invalid")
    candidates = []
    for slot in range(4):
        entry = mbr[446 + slot * 16: 446 + (slot + 1) * 16]
        ptype = entry[4]
        start = struct.unpack_from("<I", entry, 8)[0]
        sectors = struct.unpack_from("<I", entry, 12)[0]
        if ptype == 0x83 and start and sectors:
            candidates.append((start, sectors))
    if not candidates:
        raise SystemExit("no_linux_partition_found")
    # Pick the largest
    candidates.sort(key=lambda t: t[1], reverse=True)
    start, sectors = candidates[0]
    return start * 512, sectors * 512


def copy_partition(image: Path, offset: int, length: int, tempdir: Path) -> Path:
    """Copy the rootfs partition to a separate file."""
    target = tempdir / "rootfs.ext4"
    buf_size = 4 * 1024 * 1024
    with image.open("rb") as src, target.open("wb") as dst:
        src.seek(offset)
        remaining = length
        while remaining > 0:
            chunk = src.read(min(buf_size, remaining))
            if not chunk:
                break
            dst.write(chunk)
            remaining -= len(chunk)
    return target


def debugfs(rootfs: Path, request: str) -> str:
    """Run `debugfs -R <request> rootfs` and return combined stdout/stderr."""
    r = subprocess.run(
        ["debugfs", "-R", request, str(rootfs)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, check=False,
    )
    return (r.stdout or "") + (r.stderr or "")


def stat_file(rootfs: Path, path: str) -> Dict[str, Any]:
    out = debugfs(rootfs, f"stat <{path}>") if path.startswith("/") is False else \
          debugfs(rootfs, f"stat {path}")
    if "File not found" in out or "couldn't" in out.lower():
        return {"present": False}
    info: Dict[str, Any] = {"present": True, "raw_lines": []}
    # Parse Mode, Type, User, Group
    m = re.search(r"Mode:\s+0([0-7]+)", out)
    if m:
        info["mode"] = int(m.group(1), 8)
    m = re.search(r"User:\s+(\d+)\s+Group:\s+(\d+)", out)
    if m:
        info["uid"] = int(m.group(1))
        info["gid"] = int(m.group(2))
    m = re.search(r"Type:\s+(\S+)", out)
    if m:
        info["type"] = m.group(1)
    return info


def cat_file(rootfs: Path, path: str) -> Optional[str]:
    """Return file content as text, or None if missing."""
    out = debugfs(rootfs, f"cat {path}")
    if "File not found" in out or "couldn't" in out.lower() or "no such" in out.lower():
        return None
    return out


def is_symlink(rootfs: Path, path: str) -> bool:
    info = stat_file(rootfs, path)
    return info.get("type") == "symlink"


def is_file(rootfs: Path, path: str) -> bool:
    info = stat_file(rootfs, path)
    return info.get("present", False) and info.get("type") in {"regular", "Regular"}


def is_dir(rootfs: Path, path: str) -> bool:
    info = stat_file(rootfs, path)
    return info.get("present", False) and info.get("type") in {"directory", "Directory"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("image", type=Path)
    p.add_argument("--allow-any-image-path", action="store_true")
    args = p.parse_args()

    image = args.image.resolve()
    if not image.is_file():
        print(json.dumps({"error": "image_not_found", "image": str(image)}),
              file=sys.stderr)
        return 2

    expected_prefix = Path("/home/builder/totem-os/armbian-build-v25.11/output/images")
    if not args.allow_any_image_path:
        try:
            image.relative_to(expected_prefix)
        except ValueError:
            print(json.dumps({"error": "image_outside_expected_prefix",
                              "expected_prefix": str(expected_prefix),
                              "got": str(image)}),
                  file=sys.stderr)
            return 2

    if not shutil.which("debugfs"):
        print(json.dumps({"error": "debugfs_not_installed"}), file=sys.stderr)
        return 2

    out: Dict[str, Any] = {
        "image": str(image),
        "image_filename": image.name,
        "image_bytes": image.stat().st_size,
        "image_name_contains_c14_2_1": "c14-2-1-shipping-homolog" in image.name,
        "checks": {},
        "ok": True,
    }

    with tempfile.TemporaryDirectory(prefix="c14-inspect-") as td:
        td_path = Path(td)
        try:
            offset, length = parse_mbr_linux_partition(image)
        except SystemExit as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            return 2

        rootfs = copy_partition(image, offset, length, td_path)
        out["rootfs_bytes"] = length
        checks = out["checks"]

        # ---- C14.1.1 binaries ----
        for name, path in {
            "totem_updatectl_present":
                "/opt/totem/bin/totem-updatectl",
            "totem_kiosky_launcher_present":
                "/opt/totem/bin/totem-kiosky-launcher.sh",
            "kiosky_service_launcher_present":
                "/opt/totem/bin/kiosky_service_launcher.sh",
            "dropin_present":
                "/etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf",
            "update_agent_service_present":
                "/etc/systemd/system/totem-update-agent.service",
            "update_agent_timer_present":
                "/etc/systemd/system/totem-update-agent.timer",
        }.items():
            checks[name] = is_file(rootfs, path)

        # ---- executable bits ----
        for name, path in {
            "totem_updatectl_exec":
                "/opt/totem/bin/totem-updatectl",
            "totem_kiosky_launcher_exec":
                "/opt/totem/bin/totem-kiosky-launcher.sh",
            "kiosky_service_launcher_exec":
                "/opt/totem/bin/kiosky_service_launcher.sh",
        }.items():
            info = stat_file(rootfs, path)
            checks[name] = bool(info.get("mode", 0) & 0o111)

        # ---- timer enabled on image ----
        # Armbian Build runs systemctl enable in the chroot, which creates a
        # symlink under /etc/systemd/system/timers.target.wants/.
        checks["timer_enabled_on_image"] = is_symlink(
            rootfs,
            "/etc/systemd/system/timers.target.wants/totem-update-agent.timer"
        )

        # ---- timer values ----
        timer_content = cat_file(rootfs,
                                 "/etc/systemd/system/totem-update-agent.timer")
        if timer_content is None:
            checks["timer_on_boot_10min"] = False
            checks["timer_interval_6h"] = False
            checks["timer_randomized_delay_10min"] = False
            checks["timer_persistent_true"] = False
        else:
            checks["timer_on_boot_10min"] = "OnBootSec=10min" in timer_content
            checks["timer_interval_6h"] = "OnUnitActiveSec=6h" in timer_content
            checks["timer_randomized_delay_10min"] = (
                "RandomizedDelaySec=10min" in timer_content)
            checks["timer_persistent_true"] = "Persistent=true" in timer_content

        # ---- service contents ----
        svc_content = cat_file(rootfs,
                               "/etc/systemd/system/totem-update-agent.service")
        if svc_content is None:
            checks["service_targets_kiosky_repo"] = False
            checks["service_uses_updatectl"] = False
        else:
            checks["service_targets_kiosky_repo"] = (
                "--repo dadoohai/kiosky-player" in svc_content)
            checks["service_uses_updatectl"] = (
                "/opt/totem/bin/totem-updatectl" in svc_content)

        # ---- kiosky_service_launcher.sh KIOSKY_APP_DIR aware ----
        ksl = cat_file(rootfs, "/opt/totem/bin/kiosky_service_launcher.sh")
        checks["kiosky_service_launcher_supports_app_dir"] = (
            ksl is not None and "KIOSKY_APP_DIR" in ksl)

        # ---- dropin redirects ExecStart to wrapper ----
        dropin = cat_file(rootfs,
            "/etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf")
        checks["dropin_overrides_execstart"] = (
            dropin is not None
            and "ExecStart=" in dropin
            and "/opt/totem/bin/totem-kiosky-launcher.sh" in dropin)

        # ---- seed (existence + permissions only) ----
        seed_info = stat_file(rootfs,
                              "/data/state/totem-settings/private-values.seed.json")
        checks["seed_present"] = seed_info.get("present", False)
        if seed_info.get("present"):
            checks["seed_mode_0600"] = seed_info.get("mode") == 0o600
            checks["seed_owner_uid_0"] = seed_info.get("uid") == 0
            checks["seed_group_gid_0"] = seed_info.get("gid") == 0
        else:
            checks["seed_mode_0600"] = False
            checks["seed_owner_uid_0"] = False
            checks["seed_group_gid_0"] = False

        parent_info = stat_file(rootfs, "/data/state/totem-settings")
        checks["seed_parent_mode_0700"] = (
            parent_info.get("present", False)
            and parent_info.get("mode") == 0o700)

        marker_info = stat_file(rootfs,
                                "/data/state/totem-settings/homologation-seed.enabled")
        checks["seed_marker_present"] = marker_info.get("present", False)

        # ---- /data layout for C14 ----
        for name, path in {
            "data_apps_dir":
                "/data/apps",
            "data_apps_kiosky_player_dir":
                "/data/apps/kiosky-player",
            "data_apps_kiosky_player_releases_dir":
                "/data/apps/kiosky-player/releases",
            "data_updates_dir":
                "/data/updates",
            "data_updates_incoming_dir":
                "/data/updates/incoming",
            "data_logs_dir":
                "/data/logs",
        }.items():
            checks[name] = is_dir(rootfs, path)

        # ---- forbidden artifacts ----
        forbidden_real_config = stat_file(rootfs, "/data/config/config.json")
        checks["no_real_config_in_data_config"] = not forbidden_real_config.get(
            "present", False)

        # ---- final ok ----
        out["ok"] = all(bool(v) for v in checks.values())

    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
