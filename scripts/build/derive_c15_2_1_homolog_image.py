#!/usr/bin/env python3
"""Derive a C15.2.x homologation image from the validated C14.2.1 image.

The normal Armbian Build runner still requires Docker.  This derivation path is
intentionally narrower: copy the already validated private C14.2.1 image,
replace only the appliance-layer files declared in
scripts/board/totem_appliance_manifest.json, keep the base kernel/U-Boot/DTB/BSP
bits unchanged, and validate the resulting ext4 rootfs offline via debugfs.

The script never reads or prints private seed/config contents.
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
from typing import Any


DEFAULT_BASE_IMAGE = Path(
    "/home/builder/totem-os/armbian-build-v25.11/output/images/"
    "Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
    "6.12.58-c12-ro-lab-c14-2-1-shipping-homolog_minimal.img"
)
DEFAULT_OUTPUT_IMAGE = Path(
    "/home/builder/totem-os/armbian-build-v25.11/output/images/"
    "Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
    "6.12.58-c12-ro-lab-c15-2-4-homolog-clean-board-fixes_minimal.img"
)
DEFAULT_TAG = "c15-2-4-homolog-clean-board-fixes"
DEFAULT_VERSION = "c15.2.4"
MARKER_PATH = "/etc/dadooh/c15-2-4-clean-board-fixes"
DEFAULT_EXPECTED_IMAGE_TOKEN = "c15-2-4"


def run(args: list[str], *, text: bool = True, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        check=check,
    )


def parse_mbr_linux_partition(image: Path) -> tuple[int, int]:
    with image.open("rb") as fh:
        mbr = fh.read(512)
    if len(mbr) != 512 or mbr[510:512] != b"\x55\xaa":
        raise RuntimeError("image_partition_table_invalid")
    candidates: list[tuple[int, int]] = []
    for slot in range(4):
        entry = mbr[446 + slot * 16 : 446 + (slot + 1) * 16]
        ptype = entry[4]
        start = struct.unpack_from("<I", entry, 8)[0]
        sectors = struct.unpack_from("<I", entry, 12)[0]
        if ptype == 0x83 and start and sectors:
            candidates.append((start, sectors))
    if not candidates:
        raise RuntimeError("no_linux_partition_found")
    candidates.sort(key=lambda item: item[1], reverse=True)
    start, sectors = candidates[0]
    return start * 512, sectors * 512


def copy_range(source: Path, target: Path, *, offset: int = 0, length: int | None = None) -> None:
    chunk_size = 4 * 1024 * 1024
    with source.open("rb") as src, target.open("wb") as dst:
        src.seek(offset)
        remaining = length
        while remaining is None or remaining > 0:
            size = chunk_size if remaining is None else min(chunk_size, remaining)
            chunk = src.read(size)
            if not chunk:
                break
            dst.write(chunk)
            if remaining is not None:
                remaining -= len(chunk)


def write_range(target: Path, source: Path, *, offset: int) -> None:
    chunk_size = 4 * 1024 * 1024
    with target.open("r+b") as dst, source.open("rb") as src:
        dst.seek(offset)
        while True:
            chunk = src.read(chunk_size)
            if not chunk:
                break
            dst.write(chunk)


def debugfs(rootfs: Path, request: str) -> str:
    result = run(["debugfs", "-R", request, str(rootfs)])
    return (result.stdout or "") + (result.stderr or "")


def debugfs_batch(rootfs: Path, commands: list[str], work_dir: Path) -> str:
    command_file = work_dir / "debugfs.commands"
    command_file.write_text("\n".join(commands) + "\n", encoding="utf-8")
    result = run(["debugfs", "-w", "-f", str(command_file), str(rootfs)])
    return (result.stdout or "") + (result.stderr or "")


def stat_file(rootfs: Path, path: str) -> dict[str, Any]:
    out = debugfs(rootfs, f"stat {path}")
    if "File not found" in out or "couldn't" in out.lower() or "no such" in out.lower():
        return {"present": False}
    info: dict[str, Any] = {"present": True}
    mode = re.search(r"Mode:\s+0([0-7]+)", out)
    if mode:
        info["mode"] = int(mode.group(1), 8)
    owner = re.search(r"User:\s+(\d+)\s+Group:\s+(\d+)", out)
    if owner:
        info["uid"] = int(owner.group(1))
        info["gid"] = int(owner.group(2))
    ftype = re.search(r"Type:\s+(\S+)", out)
    if ftype:
        info["type"] = ftype.group(1).lower()
    return info


def cat_file(rootfs: Path, path: str) -> str | None:
    out = debugfs(rootfs, f"cat {path}")
    if "File not found" in out or "couldn't" in out.lower() or "no such" in out.lower():
        return None
    return out


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mode_with_type(mode_text: str) -> str:
    return "010" + mode_text


def parent_dirs(path: str) -> list[str]:
    current = Path(path).parent
    dirs: list[str] = []
    while str(current) not in {"", "."}:
        dirs.append(str(current))
        if str(current) == "/":
            break
        current = current.parent
    return list(reversed(dirs))


def load_manifest_sources(repo_root: Path, manifest_path: Path) -> list[dict[str, str]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items: list[dict[str, str]] = []
    for section in ("bin_scripts", "extra_files", "systemd_units"):
        for item in manifest.get(section, []):
            source = item.get("source")
            target = item.get("target")
            if not source or not target:
                continue
            source_path = repo_root / source
            if not source_path.is_file():
                raise RuntimeError(f"missing manifest source: {source}")
            items.append(
                {
                    "source": str(source_path),
                    "target": str(target),
                    "mode": str(item.get("mode", "0644")),
                    "owner": str(item.get("owner", "root")),
                    "group": str(item.get("group", "root")),
                    "section": section,
                }
            )
    return items


def systemd_symlink_commands() -> list[str]:
    links = {
        "/etc/systemd/system/multi-user.target.wants/kiosky-player.service": "/etc/systemd/system/kiosky-player.service",
        "/etc/systemd/system/multi-user.target.wants/totem-visual-tty-guard.service": "/etc/systemd/system/totem-visual-tty-guard.service",
        "/etc/systemd/system/multi-user.target.wants/totem-firstboot-gate.service": "/etc/systemd/system/totem-firstboot-gate.service",
        "/etc/systemd/system/multi-user.target.wants/totem-settings-trigger.service": "/etc/systemd/system/totem-settings-trigger.service",
        "/etc/systemd/system/sysinit.target.wants/dadooh-visual-splash.service": "/etc/systemd/system/dadooh-visual-splash.service",
        "/etc/systemd/system/timers.target.wants/totem-update-agent.timer": "/etc/systemd/system/totem-update-agent.timer",
    }
    commands: list[str] = []
    for link in links:
        commands.extend(f"mkdir {directory}" for directory in parent_dirs(link))
    for link, target in links.items():
        commands.append(f"rm {link}")
        commands.append(f"symlink {link} {target}")
    # Keep HDMI VTs quiet for the appliance path; preserve serial getty.
    commands.append("rm /etc/systemd/system/getty.target.wants/getty@tty1.service")
    commands.append("rm /etc/systemd/system/getty.target.wants/getty@tty2.service")
    return commands


def build_marker(marker_file: Path, *, image_tag: str, image_version: str, repo_head: str) -> None:
    marker_file.write_text(
        "\n".join(
            [
                f"image_tag={image_tag}",
                f"image_version={image_version}",
                "artifact_private=true",
                "final_image=false",
                "homologation_shipping_image=true",
                "not_for_production=true",
                "not_for_distribution=true",
                "base_image=c14.2.1-shipping-homolog",
                "kernel_reused=true",
                "kernel_rebuild_executed=false",
                "c15_1_3_embedded=true",
                "c15_1_4_embedded=true",
                "c15_1_5_embedded=true",
                "c15_1_6_qa_artifacts_not_installed=true",
                "c15_2_2_embedded=true",
                "c15_2_3_monitor_not_enabled_by_default=true",
                "c15_2_3_post_wizard_classification_passed=true",
                "c12_readonly_blocked=true",
                "c12_4_blocked=true",
                f"orange_pi_totem_commit={repo_head}",
                "secrets_published=false",
                "",
            ]
        ),
        encoding="utf-8",
    )


def apply_appliance_layer(
    rootfs: Path,
    repo_root: Path,
    work_dir: Path,
    *,
    image_tag: str,
    image_version: str,
) -> dict[str, Any]:
    manifest_path = repo_root / "scripts/board/totem_appliance_manifest.json"
    items = load_manifest_sources(repo_root, manifest_path)
    repo_head = run(["git", "-C", str(repo_root), "rev-parse", "HEAD"]).stdout.strip() or "unknown"

    marker_file = work_dir / "c15-2-1-image-ui-ux-fixes"
    build_marker(marker_file, image_tag=image_tag, image_version=image_version, repo_head=repo_head)
    items.append(
        {
            "source": str(marker_file),
            "target": MARKER_PATH,
            "mode": "0644",
            "owner": "root",
            "group": "root",
            "section": "c15_marker",
        }
    )

    commands: list[str] = []
    dirs: set[str] = set()
    for item in items:
        dirs.update(parent_dirs(item["target"]))
    for directory in sorted(dirs):
        commands.append(f"mkdir {directory}")
    for item in items:
        target = item["target"]
        mode = item["mode"]
        commands.append(f"rm {target}")
        commands.append(f"write {item['source']} {target}")
        commands.append(f"set_inode_field {target} mode {mode_with_type(mode)}")
        commands.append(f"set_inode_field {target} uid 0")
        commands.append(f"set_inode_field {target} gid 0")
    commands.extend(systemd_symlink_commands())
    output = debugfs_batch(rootfs, commands, work_dir)
    return {"manifest_files_written": len(items), "debugfs_output_lines": len(output.splitlines())}


def is_file(rootfs: Path, path: str) -> bool:
    info = stat_file(rootfs, path)
    return bool(info.get("present") and info.get("type") in {"regular", "file"})


def is_symlink(rootfs: Path, path: str) -> bool:
    info = stat_file(rootfs, path)
    return bool(info.get("present") and info.get("type") == "symlink")


def executable(rootfs: Path, path: str) -> bool:
    info = stat_file(rootfs, path)
    return bool(info.get("present") and (int(info.get("mode", 0)) & 0o111))


def validate_c15(rootfs: Path, image_name: str) -> dict[str, Any]:
    checks: dict[str, bool] = {}

    checks["image_name_contains_c15_2_4"] = DEFAULT_EXPECTED_IMAGE_TOKEN in image_name
    checks["c15_marker_present"] = is_file(rootfs, MARKER_PATH)

    checks["visual_tty_guard_present"] = is_file(rootfs, "/opt/totem/bin/totem_visual_tty_guard.sh")
    checks["visual_tty_guard_exec"] = executable(rootfs, "/opt/totem/bin/totem_visual_tty_guard.sh")
    checks["visual_tty_guard_service_present"] = is_file(rootfs, "/etc/systemd/system/totem-visual-tty-guard.service")
    checks["visual_tty_guard_enabled"] = is_symlink(
        rootfs, "/etc/systemd/system/multi-user.target.wants/totem-visual-tty-guard.service"
    )
    guard_service = cat_file(rootfs, "/etc/systemd/system/totem-visual-tty-guard.service") or ""
    checks["visual_tty_guard_holds_tty1_tty2"] = "--hold --tty 1 --tty 2" in guard_service

    firstboot_gate = cat_file(rootfs, "/opt/totem/bin/totem_firstboot_gate.sh") or ""
    checks["firstboot_gate_present"] = bool(firstboot_gate)
    checks["firstboot_raw_tty_output_removed"] = "Waiting for firstboot" not in firstboot_gate and "login:" not in firstboot_gate

    wizard = cat_file(rootfs, "/opt/totem/bin/totem_setup_visual_wizard.py") or ""
    wifi = cat_file(rootfs, "/opt/totem/bin/totem_wifi_nm_adapter.py") or ""
    splash = cat_file(rootfs, "/opt/totem/bin/totem_visual_splash.py") or ""
    session = cat_file(rootfs, "/opt/totem/bin/totem_open_settings_session.sh") or ""
    checks["wizard_present"] = bool(wizard)
    checks["wifi_adapter_present"] = bool(wifi)
    checks["splash_present"] = bool(splash)
    checks["open_settings_session_present"] = bool(session)
    checks["wifi_pagination_present"] = "WIFI_LIST_PAGE_SIZE" in wizard and "page_items(" in wizard
    checks["wifi_refresh_10s_present"] = "WIFI_LIST_REFRESH_SEC = 10.0" in wizard or "auto_refresh_interval_sec" in wizard
    checks["wifi_signal_present"] = "signal_bars" in wizard and "signal_bucket" in wizard
    checks["wifi_password_toggle_present"] = "show_plain_value" in wizard and "password_show_toggle_key\": \"F2" in wizard
    checks["password_v_chars_allowed"] = 'text_field_apply_key("ab", "v"' in wizard and 'text_field_apply_key("ab", "V"' in wizard
    checks["password_toggle_printable_v_removed"] = 'not is_secret_toggle_key("v")' in wizard and 'not is_secret_toggle_key("V")' in wizard
    checks["password_show_toggle_f2_ctrlp"] = 'return key in {"f2", "toggle_secret"}' in wizard and 'data == b"\\x10"' in wizard
    checks["openvt_timeout_monotonic"] = (
        "monotonic_seconds()" in session
        and "/proc/uptime" in session
        and "openvt_timeout_clock=monotonic" in session
        and "date +%s) + RUN_TIMEOUT_SEC" not in session
    )
    checks["backspace_debounce_present"] = (
        "estimate_debounced_input_render_count" in wizard
        and "TEXT_INPUT_REPEAT_DRAIN_SEC" in wizard
        and "TEXT_INPUT_MIN_RENDER_INTERVAL_SEC" in wizard
    )
    checks["splash_feedback_present"] = all(mode in splash for mode in ("boot", "player", "setup", "saving", "config_pending"))
    checks["splash_status_path_safe"] = "/tmp/dadooh-splash" in splash
    checks["splash_does_not_chmod_tmp"] = "chmod('/tmp" not in splash and 'chmod("/tmp' not in splash

    checks["pull_updater_present"] = executable(rootfs, "/opt/totem/bin/totem-updatectl")
    checks["pull_launcher_present"] = executable(rootfs, "/opt/totem/bin/totem-kiosky-launcher.sh")
    checks["pull_update_timer_present"] = is_file(rootfs, "/etc/systemd/system/totem-update-agent.timer")
    checks["pull_update_timer_enabled"] = is_symlink(
        rootfs, "/etc/systemd/system/timers.target.wants/totem-update-agent.timer"
    )
    timer = cat_file(rootfs, "/etc/systemd/system/totem-update-agent.timer") or ""
    checks["pull_update_timer_c14_2_1_interval"] = all(
        token in timer for token in ("OnBootSec=10min", "OnUnitActiveSec=6h", "RandomizedDelaySec=10min", "Persistent=true")
    )

    seed_info = stat_file(rootfs, "/data/state/totem-settings/private-values.seed.json")
    checks["seed_present"] = bool(seed_info.get("present"))
    checks["seed_permissions_ok"] = (
        seed_info.get("mode") == 0o600 and seed_info.get("uid") == 0 and seed_info.get("gid") == 0
    )
    checks["no_real_config_embedded"] = not stat_file(rootfs, "/data/config/config.json").get("present", False)

    checks["qa_generator_not_installed"] = not is_file(rootfs, "/scripts/qa/generate_ui_ux_gallery.py") and not is_file(
        rootfs, "/opt/totem/bin/generate_ui_ux_gallery.py"
    )
    checks["docs_evidence_not_installed"] = not stat_file(rootfs, "/docs/evidence").get("present", False)
    checks["c15_2_3_monitor_not_installed"] = not is_file(rootfs, "/opt/totem/bin/c15_2_3_post_wizard_monitor.sh")
    checks["c15_2_3_monitor_not_enabled"] = not is_file(rootfs, "/etc/systemd/system/c15_2_3_post_wizard_monitor.service")

    checks["kiosky_player_service_present"] = is_file(rootfs, "/etc/systemd/system/kiosky-player.service")
    checks["kiosky_player_enabled"] = is_symlink(
        rootfs, "/etc/systemd/system/multi-user.target.wants/kiosky-player.service"
    )
    checks["dadooh_visual_splash_enabled"] = is_symlink(
        rootfs, "/etc/systemd/system/sysinit.target.wants/dadooh-visual-splash.service"
    )
    checks["getty_tty1_not_enabled"] = not is_symlink(rootfs, "/etc/systemd/system/getty.target.wants/getty@tty1.service")
    checks["getty_tty2_not_enabled"] = not is_symlink(rootfs, "/etc/systemd/system/getty.target.wants/getty@tty2.service")

    ok = all(checks.values())
    return {"checks": checks, "ok": ok}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build C15.2.x by applying the current appliance manifest to C14.2.1.")
    parser.add_argument("--base-image", type=Path, default=DEFAULT_BASE_IMAGE)
    parser.add_argument("--output-image", type=Path, default=DEFAULT_OUTPUT_IMAGE)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--image-tag", default=DEFAULT_TAG)
    parser.add_argument("--image-version", default=DEFAULT_VERSION)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output image.")
    args = parser.parse_args()

    if not shutil.which("debugfs"):
        raise SystemExit("debugfs_missing")
    if not args.base_image.is_file():
        raise SystemExit("base_image_missing")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(args.out_dir, 0o700)
    if args.output_image.exists() and not args.force:
        raise SystemExit("output_image_already_exists")

    summary: dict[str, Any] = {
        "image_tag": args.image_tag,
        "image_version": args.image_version,
        "base_image": str(args.base_image),
        "output_image": str(args.output_image),
        "kernel_reused": True,
        "kernel_rebuild_executed": False,
        "artifact_private": True,
        "final_image": False,
        "homologation_shipping_image": True,
        "not_for_production": True,
        "not_for_distribution": True,
        "seed_content_published": False,
    }

    shutil.copy2(args.base_image, args.output_image)
    offset, length = parse_mbr_linux_partition(args.output_image)
    summary["rootfs_offset"] = offset
    summary["rootfs_bytes"] = length

    with tempfile.TemporaryDirectory(prefix="c15-2-4-image-") as td:
        work_dir = Path(td)
        rootfs = work_dir / "rootfs.ext4"
        copy_range(args.output_image, rootfs, offset=offset, length=length)
        summary.update(apply_appliance_layer(rootfs, args.repo_root.resolve(), work_dir, image_tag=args.image_tag, image_version=args.image_version))
        e2fsck = run(["e2fsck", "-fy", str(rootfs)])
        summary["e2fsck_exit"] = e2fsck.returncode
        summary["e2fsck_ok"] = e2fsck.returncode in {0, 1}
        validation = validate_c15(rootfs, args.output_image.name)
        summary["offline_validation"] = validation
        if not validation["ok"]:
            (args.out_dir / "c15-2-4-offline-validation.json").write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return 1
        write_range(args.output_image, rootfs, offset=offset)

    digest = file_sha256(args.output_image)
    checksum_file = args.output_image.with_suffix(args.output_image.suffix + ".sha256")
    checksum_file.write_text(f"{digest}  {args.output_image.name}\n", encoding="utf-8")
    summary["image_sha256"] = digest
    summary["image_sha256_file"] = str(checksum_file)
    summary["image_bytes"] = args.output_image.stat().st_size
    summary["ok"] = True

    out_json = args.out_dir / "c15-2-4-offline-validation.json"
    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
