#!/usr/bin/env python3
"""Sanitized offline inspection for C12 image-lab rootfs artifacts."""

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
        target = self.dump_file(path, private=private)
        if target is None:
            return ""
        return target.read_text(encoding="utf-8", errors="replace")

    def stat(self, path: str) -> str:
        proc = self.run(f"stat {path}")
        output = proc.stdout or ""
        if "File not found" in output or "Inode:" not in output:
            return ""
        return output

    def file_type(self, path: str) -> str:
        stat = self.stat(path)
        match = re.search(r"Type:\s+([a-zA-Z0-9_-]+)", stat)
        return match.group(1) if match else "missing"

    def file_size(self, path: str) -> int:
        stat = self.stat(path)
        match = re.search(r"\bSize:\s+(\d+)", stat)
        return int(match.group(1)) if match else -1

    def symlink_target(self, path: str) -> str:
        stat = self.stat(path)
        match = re.search(r'Fast link dest:\s+"([^"]+)"', stat)
        return match.group(1) if match else ""

    def resolve_path(self, path: str) -> str:
        if self.file_type(path) != "symlink":
            return path
        target = self.symlink_target(path)
        if not target:
            return path
        if target.startswith("/"):
            return target
        parent = str(Path(path).parent)
        return str(Path(parent) / target)

    def dump_file(self, path: str, private: bool = False) -> Path | None:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.strip("/")) or "root"
        target = self.dump_dir / (safe + (".private" if private else ".dump"))
        proc = self.run(f"dump -p {path} {target}")
        output = proc.stdout or ""
        if "File not found" in output or not target.exists():
            return None
        os.chmod(target, 0o600 if private else 0o644)
        return target


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dump_uinitrd_payload(uinitrd: Path, target: Path) -> bool:
    if not shutil.which("dumpimage"):
        return False
    proc = subprocess.run(
        ["dumpimage", "-T", "ramdisk", "-p", "0", "-o", str(target), str(uinitrd)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.returncode == 0 and target.exists() and target.stat().st_size > 0


def gzip_cpio_contains(initrd: Path, names: tuple[str, ...]) -> dict[str, bool]:
    result = {name: False for name in names}
    if not shutil.which("gzip") or not shutil.which("cpio"):
        return result
    proc = subprocess.run(
        f"gzip -cd {shlex_quote(str(initrd))} 2>/dev/null | cpio -t 2>/dev/null",
        shell=True,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode not in (0, 2):
        return result
    entries = set(proc.stdout.splitlines())
    normalized = {entry.lstrip("./") for entry in entries}
    for name in names:
        result[name] = name.lstrip("/") in normalized
    return result


def gzip_cpio_listing(initrd: Path) -> list[str]:
    if not shutil.which("gzip") or not shutil.which("cpio"):
        return []
    proc = subprocess.run(
        f"gzip -cd {shlex_quote(str(initrd))} 2>/dev/null | cpio -t 2>/dev/null",
        shell=True,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode not in (0, 2):
        return []
    return [entry.lstrip("./") for entry in proc.stdout.splitlines()]


def gzip_cpio_verbose_listing(initrd: Path) -> list[str]:
    if not shutil.which("gzip") or not shutil.which("cpio"):
        return []
    proc = subprocess.run(
        f"gzip -cd {shlex_quote(str(initrd))} 2>/dev/null | cpio -tv 2>/dev/null",
        shell=True,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode not in (0, 2):
        return []
    return proc.stdout.splitlines()


def cpio_symlink_points_to(lines: list[str], name: str, target: str) -> bool:
    suffix = f" {name.lstrip('./')} -> {target}"
    return any(line.endswith(suffix) for line in lines)


def gzip_cpio_read_text(initrd: Path, name: str) -> str:
    if not shutil.which("gzip") or not shutil.which("cpio"):
        return ""
    normalized = name.lstrip("/")
    proc = subprocess.run(
        (
            f"gzip -cd {shlex_quote(str(initrd))} 2>/dev/null | "
            f"cpio -i --to-stdout {shlex_quote(normalized)} 2>/dev/null"
        ),
        shell=True,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return proc.stdout if proc.returncode == 0 else ""


def listing_contains_prefix(entries: list[str], prefix: str) -> bool:
    return any(entry.startswith(prefix) for entry in entries)


def shlex_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


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
        boot_cmd = debug.dump("/boot/boot.cmd")

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
        payload["boot_script_uses_uinitrd"] = "uInitrd" in boot_cmd
        payload["boot_script_uses_initrd_img"] = "initrd.img" in boot_cmd

        kernel_version = ""
        for candidate in (
            "6.12.58-current-sunxi64",
            "6.12.58-current-sunxi64",
        ):
            if debug.exists(f"/boot/initrd.img-{candidate}"):
                kernel_version = candidate
                break
        if not kernel_version:
            stat_paths = debug.run("ls -l /boot").stdout or ""
            match = re.search(r"initrd\.img-([0-9][^\s]+)", stat_paths)
            kernel_version = match.group(1) if match else ""
        initrd_path = f"/boot/initrd.img-{kernel_version}" if kernel_version else "/boot/initrd.img"
        uinitrd_path = "/boot/uInitrd"
        effective_uinitrd_path = debug.resolve_path(uinitrd_path)
        payload["initrd_kernel_version"] = kernel_version or "unknown"
        payload["initrd_img_exists"] = debug.exists(initrd_path)
        payload["uinitrd_exists"] = debug.exists(uinitrd_path)
        payload["uinitrd_is_symlink"] = debug.file_type(uinitrd_path) == "symlink"
        payload["uinitrd_effective_path_known"] = effective_uinitrd_path != uinitrd_path or debug.exists(uinitrd_path)
        payload["uinitrd_effective_exists"] = debug.exists(effective_uinitrd_path)
        payload["uinitrd_effective_size"] = debug.file_size(effective_uinitrd_path)
        payload["uinitrd_nonempty"] = payload["uinitrd_effective_size"] > 1024 * 1024

        initrd_file = debug.dump_file(initrd_path, private=True) if payload["initrd_img_exists"] else None
        uinitrd_file = (
            debug.dump_file(effective_uinitrd_path, private=True)
            if payload["uinitrd_effective_exists"]
            else None
        )
        uinitrd_payload = tempdir / "uinitrd.raw"
        payload["uinitrd_payload_extracted"] = (
            dump_uinitrd_payload(uinitrd_file, uinitrd_payload)
            if uinitrd_file is not None
            else False
        )
        payload["uinitrd_payload_matches_initrd_img"] = (
            bool(initrd_file)
            and payload["uinitrd_payload_extracted"]
            and sha256(initrd_file) == sha256(uinitrd_payload)
        )
        initrd_scan = gzip_cpio_contains(
            initrd_file,
            (
                "scripts/init-bottom/overlayroot",
                "scripts/init-top/dadooh-force-overlay",
                "etc/dadooh/c12-overlayroot-initramfs-marker",
                "etc/dadooh/c12-overlay-module-path-marker",
                f"usr/lib/modules/{kernel_version}/kernel/fs/overlayfs/overlay.ko",
                f"lib/modules/{kernel_version}/kernel/fs/overlayfs/overlay.ko",
                f"lib/modules/{kernel_version}/modules.dep",
                f"lib/modules/{kernel_version}/modules.alias",
                "usr/sbin/modprobe",
                "usr/bin/insmod",
            ),
        ) if initrd_file else {}
        uinitrd_scan = gzip_cpio_contains(
            uinitrd_payload,
            (
                "scripts/init-bottom/overlayroot",
                "scripts/init-top/dadooh-force-overlay",
                "etc/dadooh/c12-overlayroot-initramfs-marker",
                "etc/dadooh/c12-overlay-module-path-marker",
                f"usr/lib/modules/{kernel_version}/kernel/fs/overlayfs/overlay.ko",
                f"lib/modules/{kernel_version}/kernel/fs/overlayfs/overlay.ko",
                f"lib/modules/{kernel_version}/modules.dep",
                f"lib/modules/{kernel_version}/modules.alias",
                "usr/sbin/modprobe",
                "usr/bin/insmod",
            ),
        ) if payload["uinitrd_payload_extracted"] else {}
        initrd_entries = gzip_cpio_listing(initrd_file) if initrd_file else []
        uinitrd_entries = gzip_cpio_listing(uinitrd_payload) if payload["uinitrd_payload_extracted"] else []
        initrd_verbose_entries = gzip_cpio_verbose_listing(initrd_file) if initrd_file else []
        uinitrd_verbose_entries = (
            gzip_cpio_verbose_listing(uinitrd_payload) if payload["uinitrd_payload_extracted"] else []
        )
        effective_entries = uinitrd_entries or initrd_entries
        effective_verbose_entries = uinitrd_verbose_entries or initrd_verbose_entries
        overlay_effective_prefix = f"lib/modules/{kernel_version}/kernel/fs/overlayfs/overlay.ko"
        usr_overlay_effective_prefix = f"usr/lib/modules/{kernel_version}/kernel/fs/overlayfs/overlay.ko"
        modules_dep_path = f"lib/modules/{kernel_version}/modules.dep"
        usr_modules_dep_path = f"usr/lib/modules/{kernel_version}/modules.dep"
        modules_alias_path = f"lib/modules/{kernel_version}/modules.alias"
        usr_modules_alias_path = f"usr/lib/modules/{kernel_version}/modules.alias"
        modules_dep_text = gzip_cpio_read_text(
            uinitrd_payload if payload["uinitrd_payload_extracted"] else initrd_file,
            modules_dep_path,
        ) if (payload["uinitrd_payload_extracted"] or initrd_file) else ""
        if not modules_dep_text:
            modules_dep_text = gzip_cpio_read_text(
                uinitrd_payload if payload["uinitrd_payload_extracted"] else initrd_file,
                usr_modules_dep_path,
            ) if (payload["uinitrd_payload_extracted"] or initrd_file) else ""
        overlay_load_hook_text = gzip_cpio_read_text(
            uinitrd_payload if payload["uinitrd_payload_extracted"] else initrd_file,
            "scripts/init-top/dadooh-force-overlay",
        ) if (payload["uinitrd_payload_extracted"] or initrd_file) else ""
        initrd_lib_symlink = cpio_symlink_points_to(initrd_verbose_entries, "lib", "usr/lib")
        uinitrd_lib_symlink = cpio_symlink_points_to(uinitrd_verbose_entries, "lib", "usr/lib")
        effective_lib_symlink = cpio_symlink_points_to(effective_verbose_entries, "lib", "usr/lib")
        payload["initrd_contains_overlayroot_hook"] = bool(initrd_scan.get("scripts/init-bottom/overlayroot"))
        payload["initrd_contains_overlay_load_hook"] = bool(initrd_scan.get("scripts/init-top/dadooh-force-overlay"))
        payload["initrd_contains_c12_overlayroot_marker"] = bool(
            initrd_scan.get("etc/dadooh/c12-overlayroot-initramfs-marker")
        )
        payload["initrd_contains_c12_overlay_module_path_marker"] = bool(
            initrd_scan.get("etc/dadooh/c12-overlay-module-path-marker")
        )
        payload["initrd_contains_overlay_module"] = bool(
            initrd_scan.get(f"usr/lib/modules/{kernel_version}/kernel/fs/overlayfs/overlay.ko")
        )
        payload["initrd_contains_overlay_module_effective_path"] = bool(
            initrd_scan.get(f"lib/modules/{kernel_version}/kernel/fs/overlayfs/overlay.ko")
            or (
                initrd_lib_symlink
                and initrd_scan.get(f"usr/lib/modules/{kernel_version}/kernel/fs/overlayfs/overlay.ko")
            )
        )
        payload["uinitrd_contains_overlayroot_hook"] = bool(uinitrd_scan.get("scripts/init-bottom/overlayroot"))
        payload["uinitrd_contains_overlay_load_hook"] = bool(uinitrd_scan.get("scripts/init-top/dadooh-force-overlay"))
        payload["uinitrd_contains_c12_overlayroot_marker"] = bool(
            uinitrd_scan.get("etc/dadooh/c12-overlayroot-initramfs-marker")
        )
        payload["uinitrd_contains_c12_overlay_module_path_marker"] = bool(
            uinitrd_scan.get("etc/dadooh/c12-overlay-module-path-marker")
        )
        payload["uinitrd_contains_overlay_module"] = bool(
            uinitrd_scan.get(f"usr/lib/modules/{kernel_version}/kernel/fs/overlayfs/overlay.ko")
        )
        payload["uinitrd_contains_overlay_module_effective_path"] = bool(
            uinitrd_scan.get(f"lib/modules/{kernel_version}/kernel/fs/overlayfs/overlay.ko")
            or (
                uinitrd_lib_symlink
                and uinitrd_scan.get(f"usr/lib/modules/{kernel_version}/kernel/fs/overlayfs/overlay.ko")
            )
        )
        payload["initrd_lib_symlink_to_usr_lib"] = initrd_lib_symlink
        payload["uinitrd_lib_symlink_to_usr_lib"] = uinitrd_lib_symlink
        payload["effective_initramfs_lib_symlink_to_usr_lib"] = effective_lib_symlink
        payload["overlay_module_effective_path_present"] = listing_contains_prefix(
            effective_entries, overlay_effective_prefix
        ) or (
            effective_lib_symlink and listing_contains_prefix(effective_entries, usr_overlay_effective_prefix)
        )
        payload["overlay_module_usr_path_present"] = listing_contains_prefix(
            effective_entries, usr_overlay_effective_prefix
        )
        payload["modules_dep_effective_path_present"] = modules_dep_path in effective_entries or (
            effective_lib_symlink and usr_modules_dep_path in effective_entries
        )
        payload["modules_alias_effective_path_present"] = modules_alias_path in effective_entries or (
            effective_lib_symlink and usr_modules_alias_path in effective_entries
        )
        payload["modules_dep_references_overlay"] = "kernel/fs/overlayfs/overlay.ko" in modules_dep_text
        payload["modprobe_present_in_initramfs"] = "usr/sbin/modprobe" in effective_entries
        payload["insmod_present_in_initramfs"] = "usr/bin/insmod" in effective_entries
        payload["overlay_load_hook_uses_effective_path"] = (
            "/lib/modules/$KERNEL/kernel/fs/overlayfs/overlay.ko" in overlay_load_hook_text
            and "insmod" in overlay_load_hook_text
        )
        payload["effective_boot_initramfs_overlay_resolvable"] = bool(
            payload["overlay_module_effective_path_present"]
            and payload["modules_dep_effective_path_present"]
            and payload["modules_dep_references_overlay"]
            and payload["modprobe_present_in_initramfs"]
            and payload["insmod_present_in_initramfs"]
            and payload["uinitrd_contains_overlay_load_hook"]
            and payload["overlay_load_hook_uses_effective_path"]
        )
        payload["uinitrd_generated_after_initrd_img"] = bool(
            payload["uinitrd_payload_matches_initrd_img"]
        )
        payload["uinitrd_generated_after_overlayroot"] = bool(
            payload["overlayroot_tmpfs_configured"]
            and payload["uinitrd_contains_overlayroot_hook"]
            and payload["uinitrd_contains_c12_overlayroot_marker"]
        )
        payload["effective_boot_initramfs_valid"] = bool(
            payload["boot_script_uses_uinitrd"]
            and payload["uinitrd_nonempty"]
            and payload["uinitrd_payload_matches_initrd_img"]
            and payload["uinitrd_contains_overlayroot_hook"]
            and payload["uinitrd_contains_c12_overlayroot_marker"]
            and payload["uinitrd_contains_overlay_module"]
            and payload["effective_boot_initramfs_overlay_resolvable"]
        )

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
            and payload.get("effective_boot_initramfs_valid")
            and payload.get("effective_boot_initramfs_overlay_resolvable")
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
