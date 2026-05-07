#!/usr/bin/env python3
"""Sanitized offline inspection for C12 image-lab rootfs artifacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


REQUIRED_FIRSTBOOT_KEYS = (
    "PRESET_NET_CHANGE_DEFAULTS",
    "PRESET_NET_ETHERNET_ENABLED",
    "PRESET_NET_WIFI_ENABLED",
    "PRESET_CONNECT_WIRELESS",
    "SET_LANG_BASED_ON_LOCATION",
    "PRESET_LOCALE",
    "PRESET_TIMEZONE",
    "PRESET_USER_SHELL",
    "PRESET_ROOT_PASSWORD",
    "PRESET_USER_NAME",
    "PRESET_USER_PASSWORD",
    "PRESET_DEFAULT_REALNAME",
)

PLACEHOLDERS = (
    "REPLACE_WITH_PRIVATE_LAB_ROOT_PASSWORD",
    "REPLACE_WITH_PRIVATE_LAB_USER_PASSWORD",
    "REPLACE_WITH_PRIVATE_LAB_WIFI_SSID",
    "REPLACE_WITH_PRIVATE_LAB_WIFI_PASSWORD",
    "RootPassword",
    "UserPassword",
    "MySSID",
    "MyWiFiKEY",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect a C12 image-lab rootfs without printing private values."
    )
    parser.add_argument("image", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--require-lab-bootstrap-service", action="store_true")
    parser.add_argument("--keep-private-rootfs-copy", action="store_true")
    return parser.parse_args()


def parse_mbr_linux_partition(image: Path) -> tuple[int, int]:
    with image.open("rb") as fh:
        mbr = fh.read(512)
    if len(mbr) != 512 or mbr[510:512] != b"\x55\xaa":
        raise SystemExit("image_partition_table_invalid")
    candidates: list[tuple[int, int]] = []
    for idx in range(4):
        entry = mbr[446 + idx * 16 : 446 + (idx + 1) * 16]
        ptype = entry[4]
        start = struct.unpack_from("<I", entry, 8)[0]
        sectors = struct.unpack_from("<I", entry, 12)[0]
        if ptype == 0x83 and start and sectors:
            candidates.append((start, sectors))
    if len(candidates) != 1:
        raise SystemExit("image_linux_partition_not_unique")
    start, sectors = candidates[0]
    return start * 512, sectors * 512


def copy_partition_private(image: Path, offset: int, length: int, tempdir: Path) -> Path:
    target = tempdir / "rootfs.ext4"
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

    def run(self, request: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["debugfs", "-R", request, str(self.rootfs)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def exists(self, path: str) -> bool:
        proc = self.run(f"stat {path}")
        output = proc.stdout or ""
        return "File not found" not in output and "Inode:" in output

    def dump(self, path: str, private: bool = False) -> str:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.strip("/")) or "root"
        target = self.dump_dir / (safe + (".private" if private else ".dump"))
        proc = self.run(f"dump -p {path} {target}")
        output = proc.stdout or ""
        if "File not found" in output or not target.exists():
            return ""
        os.chmod(target, 0o600 if private else 0o644)
        return target.read_text(encoding="utf-8", errors="replace")


def parse_firstboot(text: str) -> dict[str, bool]:
    keys: set[str] = set()
    values: dict[str, str] = {}
    for match in re.finditer(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$", text, re.M):
        raw = match.group(2).strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
            raw = raw[1:-1]
        keys.add(match.group(1))
        values[match.group(1)] = raw
    wifi_enabled = values.get("PRESET_NET_WIFI_ENABLED") == "1"
    ethernet_enabled = values.get("PRESET_NET_ETHERNET_ENABLED") == "1"
    return {
        "firstboot_required_fields_present": all(k in keys for k in REQUIRED_FIRSTBOOT_KEYS),
        "firstboot_placeholders_present": any(p in text for p in PLACEHOLDERS),
        "firstboot_network_path_present": ethernet_enabled or wifi_enabled,
        "firstboot_wifi_fields_present_if_enabled": (
            True
            if not wifi_enabled
            else all(
                bool(values.get(k))
                for k in (
                    "PRESET_NET_WIFI_SSID",
                    "PRESET_NET_WIFI_KEY",
                    "PRESET_NET_WIFI_COUNTRYCODE",
                )
            )
        ),
        "firstboot_password_fields_present": bool(values.get("PRESET_ROOT_PASSWORD"))
        and bool(values.get("PRESET_USER_PASSWORD")),
    }


def inspect(args: argparse.Namespace) -> dict[str, object]:
    if not args.image.is_file():
        raise SystemExit("image_missing")
    if not shutil.which("debugfs"):
        raise SystemExit("debugfs_missing")

    tempdir = Path(tempfile.mkdtemp(prefix="dadooh-c12-rootfs-inspect-", dir="/tmp"))
    os.chmod(tempdir, 0o700)
    try:
        offset, length = parse_mbr_linux_partition(args.image)
        rootfs = copy_partition_private(args.image, offset, length, tempdir)
        debug = DebugFs(rootfs, tempdir)

        payload: dict[str, object] = {
            "image_inspected": True,
            "image_partition_type": "linux_ext",
            "private_values_published": False,
        }
        paths = {
            "root_firstboot_conf_present": "/root/.not_logged_in_yet",
            "lab_firstboot_marker_present": "/etc/dadooh/image-lab-firstboot-autoconfig.present",
            "firstboot_gate_script_present": "/opt/totem/bin/totem_firstboot_gate.sh",
            "firstboot_gate_unit_present": "/etc/systemd/system/totem-firstboot-gate.service",
            "firstboot_gate_enabled": "/etc/systemd/system/multi-user.target.wants/totem-firstboot-gate.service",
            "lab_bootstrap_script_present": "/opt/totem/bin/totem_lab_firstboot_autoconfig.sh",
            "lab_bootstrap_unit_present": "/etc/systemd/system/totem-lab-firstboot-autoconfig.service",
            "lab_bootstrap_enabled": "/etc/systemd/system/multi-user.target.wants/totem-lab-firstboot-autoconfig.service",
            "armbian_firstrun_unit_present": "/lib/systemd/system/armbian-firstrun.service",
            "armbian_firstrun_enabled": "/etc/systemd/system/multi-user.target.wants/armbian-firstrun.service",
            "overlayroot_conf_present": "/etc/overlayroot.conf",
            "integration_json_present": "/data/state/totem-read-only-image-lab/integration.json",
        }
        for key, path in paths.items():
            payload[key] = debug.exists(path)

        firstboot = debug.dump("/root/.not_logged_in_yet", private=True)
        payload.update(parse_firstboot(firstboot) if firstboot else {})

        gate_script = debug.dump("/opt/totem/bin/totem_firstboot_gate.sh")
        gate_unit = debug.dump("/etc/systemd/system/totem-firstboot-gate.service")
        lab_unit = debug.dump("/etc/systemd/system/totem-lab-firstboot-autoconfig.service")
        integration_text = debug.dump("/data/state/totem-read-only-image-lab/integration.json")
        overlayroot_conf = debug.dump("/etc/overlayroot.conf")

        payload["gate_expected_path_matches"] = (
            'MARKER="/root/.not_logged_in_yet"' in gate_script
            and "ConditionPathExists=/root/.not_logged_in_yet" in gate_unit
        )
        payload["lab_bootstrap_runs_before_gate"] = (
            "Before=totem-firstboot-gate.service" in lab_unit
            or "Before=totem-firstboot-gate.service " in lab_unit
        )
        payload["overlayroot_tmpfs_configured"] = 'overlayroot="tmpfs"' in overlayroot_conf
        payload["overlayroot_cfgdisk_disabled"] = 'overlayroot_cfgdisk="disabled"' in overlayroot_conf

        try:
            integration = json.loads(integration_text) if integration_text else {}
        except json.JSONDecodeError:
            integration = {}
        payload["integration_json_valid"] = bool(integration)
        payload["integration_lab_firstboot_autoconfig_present"] = bool(
            integration.get("armbian_firstboot_autoconfig_present")
        )
        payload["integration_lab_bootstrap_service_present"] = bool(
            integration.get("lab_firstboot_bootstrap_service_present")
        )
        payload["integration_boot_validatable"] = bool(
            integration.get("image_lab_boot_validatable_with_private_firstboot")
        )

        payload["rootfs_firstboot_autoconfig_proven"] = bool(
            payload.get("root_firstboot_conf_present")
            and payload.get("lab_firstboot_marker_present")
            and payload.get("firstboot_required_fields_present")
            and not payload.get("firstboot_placeholders_present", True)
            and payload.get("firstboot_network_path_present")
            and payload.get("firstboot_password_fields_present")
        )
        payload["rootfs_lab_bootstrap_proven"] = bool(
            payload.get("lab_bootstrap_script_present")
            and payload.get("lab_bootstrap_unit_present")
            and payload.get("lab_bootstrap_enabled")
            and payload.get("lab_bootstrap_runs_before_gate")
        )
        payload["ready_for_card_write_by_rootfs"] = bool(
            payload.get("rootfs_firstboot_autoconfig_proven")
            and payload.get("rootfs_lab_bootstrap_proven")
            and payload.get("gate_expected_path_matches")
            and payload.get("overlayroot_tmpfs_configured")
        )
        if args.require_lab_bootstrap_service and not payload["ready_for_card_write_by_rootfs"]:
            payload["validation_error"] = "rootfs_lab_firstboot_autoconfig_not_proven"
    finally:
        if not args.keep_private_rootfs_copy:
            shutil.rmtree(tempdir, ignore_errors=True)

    return payload


def write_payload(payload: dict[str, object], out: Path | None) -> None:
    lines = []
    for key in sorted(payload):
        value = payload[key]
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        lines.append(f"{key}={rendered}")
    text = "\n".join(lines) + "\n"
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
        tmp.write_text(text, encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, out)
        os.chmod(out, 0o600)
    else:
        sys.stdout.write(text)


def main() -> int:
    args = parse_args()
    payload = inspect(args)
    write_payload(payload, args.out)
    if args.require_lab_bootstrap_service and not payload.get("ready_for_card_write_by_rootfs"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
