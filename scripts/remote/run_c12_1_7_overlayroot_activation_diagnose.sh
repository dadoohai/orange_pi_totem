#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
TIMESTAMP="${C12_1_7_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${C12_1_7_RUN_ROOT:-/tmp/dadooh-c12-1-7-overlayroot-activation-diagnose}"
OUT_DIR="${C12_1_7_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-1-7-overlayroot-activation-diagnose}"
KNOWN_HOSTS="${C12_1_7_KNOWN_HOSTS:-/tmp/dadooh-c12-1-7-known-hosts}"
SSH_CONTROL_PATH="${C12_1_7_SSH_CONTROL_PATH:-}"
IMAGE_PATH="${C12_1_7_IMAGE_PATH:-/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-6_minimal.img}"
BUILD_LOG="${C12_1_7_BUILD_LOG:-/home/builder/totem-os/armbian-build-v25.11/output/logs/log-build-299de716-0d1f-451c-a145-0edd7fd955c6.log}"
PACKAGE_MANIFEST="${C12_1_7_PACKAGE_MANIFEST:-releases/image-lab-readonly/package-manifest-c12-1-6.txt}"
INTEGRATION_MANIFEST="${C12_1_7_INTEGRATION_MANIFEST:-releases/image-lab-readonly/read-only-integration-manifest-c12-1-6.txt}"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_1_7_overlayroot_activation_diagnose.sh [root@host] [mode]

Modes:
  --prepare-only
  --inspect-running-board
  --inspect-image-artifact
  --compare
  --summary

Rules:
  - read-only diagnostics only;
  - no remount, reboot, poweroff, writer, config provisioning, Wi-Fi changes,
    package install, apt upgrade, or raw log publication;
  - host must be passed as an argument for board inspection.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect-running-board) MODE="inspect-running-board" ;;
    --inspect-image-artifact) MODE="inspect-image-artifact" ;;
    --compare) MODE="compare" ;;
    --summary) MODE="summary" ;;
    --help|-h) usage; exit 0 ;;
    --*) echo "error: unsupported mode $1" >&2; usage; exit 2 ;;
    *) HOST="$1" ;;
  esac
  shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"

ssh_board() {
  if [ -z "$HOST" ]; then
    echo "error: host is required for $MODE" >&2
    exit 2
  fi
  local opts=(
    -o UserKnownHostsFile="$KNOWN_HOSTS"
    -o StrictHostKeyChecking=accept-new
    -o ServerAliveInterval=10
    -o ServerAliveCountMax=3
  )
  if [ -n "$SSH_CONTROL_PATH" ]; then
    opts+=(-o ControlPath="$SSH_CONTROL_PATH")
  fi
  ssh "${opts[@]}" "$HOST" "$@"
}

prepare_only() {
  git -C "$REPO_ROOT" diff --check
  bash -n "$REPO_ROOT/scripts/remote/run_c12_3_4_image_lab_boot_validation.sh"
  bash -n "$REPO_ROOT/scripts/remote/run_c12_1_image_lab_readonly_validation.sh"
  bash -n "$REPO_ROOT/scripts/build/run_c12_1_build_image_lab_readonly.sh"
  test -f "$IMAGE_PATH"
  test -f "$PACKAGE_MANIFEST"
  test -f "$INTEGRATION_MANIFEST"
  {
    printf 'prepare_only=ok\n'
    printf 'image_path_exists=true\n'
    printf 'package_manifest_exists=true\n'
    printf 'integration_manifest_exists=true\n'
    printf 'boards_touched=false\n'
  } > "$OUT_DIR/prepare.env"
}

inspect_running_board() {
  ssh_board "python3 -" > "$OUT_DIR/running-board.json" <<'PY'
import json
import os
import pathlib
import re
import subprocess


def run(cmd, timeout=12):
    try:
        return subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, "", "")


def out(cmd, timeout=12):
    return (run(cmd, timeout).stdout or "").strip()


def shell(command, timeout=12):
    return out(["sh", "-lc", command], timeout=timeout)


def package_installed(name):
    return shell(f"dpkg-query -W -f='${{Status}}' {name} 2>/dev/null || true") == "install ok installed"


def command_available(name):
    return bool(shell(f"command -v {name} 2>/dev/null || true"))


def service(name):
    return {
        "active": shell(f"systemctl is-active {name} 2>/dev/null || true") or "unknown",
        "enabled": shell(f"systemctl is-enabled {name} 2>/dev/null || true") or "unknown",
        "result": shell(f"systemctl show {name} -p Result --value 2>/dev/null || true") or "unknown",
        "n_restarts": shell(f"systemctl show {name} -p NRestarts --value 2>/dev/null || echo 0") or "0",
    }


def mount_info(target):
    text = shell(f"findmnt -n -o SOURCE,FSTYPE,OPTIONS --target {target} 2>/dev/null || true")
    parts = text.split(None, 2)
    return {
        "present": bool(parts),
        "source_category": "overlay" if parts and parts[0] == "overlay" else ("device" if parts else "unknown"),
        "fstype": parts[1] if len(parts) > 1 else "unknown",
        "options": parts[2] if len(parts) > 2 else "",
    }


def bool_path(path):
    return pathlib.Path(path).exists()


def file_size(path):
    try:
        return pathlib.Path(path).stat().st_size
    except OSError:
        return -1


def parse_overlay_conf(path):
    p = pathlib.Path(path)
    if not p.exists():
        return {"present": False, "overlayroot_category": "missing", "cfgdisk_category": "missing"}
    overlay = None
    cfgdisk = None
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("overlayroot="):
            overlay = stripped.split("=", 1)[1].strip().strip('"').strip("'")
        elif stripped.startswith("overlayroot_cfgdisk="):
            cfgdisk = stripped.split("=", 1)[1].strip().strip('"').strip("'")
    def cat(value):
        if value is None:
            return "missing"
        if value == "":
            return "empty"
        if value == "tmpfs":
            return "tmpfs"
        if value in {"disabled", "disable"}:
            return "disabled"
        return "other"
    return {"present": True, "overlayroot_category": cat(overlay), "cfgdisk_category": cat(cfgdisk)}


def boot_categories():
    cmdline = pathlib.Path("/proc/cmdline").read_text(encoding="utf-8", errors="replace") if pathlib.Path("/proc/cmdline").exists() else ""
    env_path = pathlib.Path("/boot/armbianEnv.txt")
    env = env_path.read_text(encoding="utf-8", errors="replace") if env_path.exists() else ""
    return {
        "kernel_version": shell("uname -r"),
        "cmdline_overlayroot_present": "overlayroot" in cmdline,
        "cmdline_root_present": bool(re.search(r"(^|\\s)root=", cmdline)),
        "cmdline_console_category": (
            "serial" if re.search(r"console=(ttyS|serial)", cmdline)
            else "tty" if "console=tty" in cmdline
            else "none"
        ),
        "armbian_env_present": env_path.exists(),
        "armbian_env_overlayroot_present": "overlayroot" in env,
        "armbian_env_extraargs_present": "extraargs=" in env,
        "armbian_env_uinitrd_reference_present": "uInitrd" in env,
        "armbian_env_quiet_present": "quiet" in env,
        "armbian_env_loglevel_present": "loglevel" in env,
    }


def status_snapshot():
    def load(path):
        try:
            value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}
    public = load("/tmp/dadooh-status/status.json")
    launcher = load("/data/state/kiosky-player/launcher-status.json") or load("/tmp/kiosky-launcher-status.json")
    player = load("/tmp/kiosky-status.json")
    return {
        "public_state": public.get("public_state") or public.get("state") or launcher.get("state", "unknown"),
        "playback": public.get("playback") or public.get("playback_state") or player.get("playback") or player.get("playback_state") or "unknown",
    }


def proc_counts():
    counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            parts = [p.decode("utf-8", "ignore") for p in (proc / "cmdline").read_bytes().split(b"\0") if p]
        except OSError:
            continue
        names = [pathlib.Path(part).name.lower() for part in parts]
        if "kiosk.py" in names:
            counts["player"] += 1
        if "mpv" in names:
            counts["mpv"] += 1
        if any("totem_status_renderer" in name for name in names):
            counts["renderer"] += 1
        if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
            counts["setup"] += 1
    return counts


def failed_count():
    text = shell("systemctl --failed --no-legend --plain 2>/dev/null || true")
    return len([line for line in text.splitlines() if line.strip()])


def kernel_categories():
    text = shell("journalctl -k -b --no-pager 2>/dev/null | grep -Ei 'overlayroot|cloud-initramfs|initramfs|Unable to find a driver|overlay' || true", timeout=20)
    lowered = text.lower()
    return {
        "overlayroot_log_seen": "overlayroot" in lowered,
        "initramfs_error_category": (
            "driver_lookup_failed" if "unable to find a driver" in lowered
            else "overlay_mount_failed" if "overlay" in lowered and "fail" in lowered
            else "none" if not lowered
            else "other"
        ),
        "initramfs_log_driver_lookup_failed": "unable to find a driver" in lowered,
        "raw_logs_published": False,
    }


root = mount_info("/")
root_options = {item.strip() for item in root["options"].split(",") if item.strip()}
uinitrd = pathlib.Path("/boot/uInitrd")
initrd = pathlib.Path(f"/boot/initrd.img-{shell('uname -r')}")
payload = {
    "schema_version": "dadooh-c12.1.7-running-board.v1",
    "running_board_inspected": True,
    "read_only_enabled": root["fstype"] == "overlay" or "ro" in root_options,
    "overlay_active": root["fstype"] == "overlay",
    "root_fstype": root["fstype"],
    "root_write_blocked": root["fstype"] == "overlay" or "ro" in root_options,
    "mount_root": root,
    "mount_data": mount_info("/data"),
    "mount_tmp": mount_info("/tmp"),
    "mount_run": mount_info("/run"),
    "overlay_mount_present": bool(shell("findmnt -t overlay --noheadings 2>/dev/null || true")),
    "overlayroot_package_installed": package_installed("overlayroot"),
    "overlayroot_chroot_present": command_available("overlayroot-chroot"),
    "hook_initramfs_present": bool_path("/usr/share/initramfs-tools/hooks/overlayroot"),
    "init_bottom_overlayroot_present": bool_path("/usr/share/initramfs-tools/scripts/init-bottom/overlayroot"),
    "overlayroot_conf": parse_overlay_conf("/etc/overlayroot.conf"),
    "overlayroot_local_conf_present": bool_path("/etc/overlayroot.local.conf"),
    "current_initrd_exists": initrd.exists(),
    "current_initrd_size": file_size(initrd),
    "uinitrd_exists": uinitrd.exists(),
    "uinitrd_size": file_size(uinitrd),
    "uinitrd_size_category": "missing" if not uinitrd.exists() else ("empty" if file_size(uinitrd) == 0 else "nonempty"),
    "journald_volatile": "Storage=volatile" in (pathlib.Path("/etc/systemd/journald.conf.d/10-dadooh-volatile.conf").read_text(encoding="utf-8", errors="replace") if pathlib.Path("/etc/systemd/journald.conf.d/10-dadooh-volatile.conf").exists() else ""),
    "systemctl_failed_count": failed_count(),
    "console_setup_failed": "console-setup.service" in shell("systemctl --failed --no-legend --plain 2>/dev/null || true"),
    "services": {name: service(name) for name in ("kiosky-player.service", "totem-settings-trigger.service", "dadooh-visual-splash.service")},
    "proc_counts": proc_counts(),
    "status": status_snapshot(),
    "secrets_published": False,
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "wifi_changed": False,
}
payload.update(boot_categories())
payload.update(kernel_categories())
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/running-board.json"
}

inspect_image_artifact() {
  python3 - "$IMAGE_PATH" "$BUILD_LOG" "$PACKAGE_MANIFEST" "$INTEGRATION_MANIFEST" > "$OUT_DIR/image-artifact.json" <<'PY'
from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

image = Path(sys.argv[1])
build_log = Path(sys.argv[2])
package_manifest = Path(sys.argv[3])
integration_manifest = Path(sys.argv[4])


def run(cmd, data=None, timeout=40):
    try:
        return subprocess.run(
            cmd,
            input=data,
            text=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, b"", b"")


def parse_mbr_linux_partition(path: Path):
    with path.open("rb") as fh:
        mbr = fh.read(512)
    if len(mbr) != 512 or mbr[510:512] != b"\x55\xaa":
        raise SystemExit("image_partition_table_invalid")
    candidates = []
    for idx in range(4):
        entry = mbr[446 + idx * 16 : 446 + (idx + 1) * 16]
        ptype = entry[4]
        start = struct.unpack_from("<I", entry, 8)[0]
        sectors = struct.unpack_from("<I", entry, 12)[0]
        if ptype == 0x83 and start and sectors:
            candidates.append((start * 512, sectors * 512))
    if len(candidates) != 1:
        raise SystemExit("image_linux_partition_not_unique")
    return candidates[0]


class DebugFs:
    def __init__(self, rootfs: Path, dump_dir: Path):
        self.rootfs = rootfs
        self.dump_dir = dump_dir

    def debugfs(self, request: str) -> str:
        proc = subprocess.run(
            ["debugfs", "-R", request, str(self.rootfs)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        return proc.stdout or ""

    def exists(self, path: str) -> bool:
        output = self.debugfs(f"stat {path}")
        return "Inode:" in output and "File not found" not in output

    def dump(self, path: str, private: bool = False) -> Path | None:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.strip("/")) or "root"
        target = self.dump_dir / (safe + (".private" if private else ".dump"))
        self.debugfs(f"dump -p {path} {target}")
        if not target.exists():
            return None
        os.chmod(target, 0o600 if private else 0o644)
        return target

    def read_text(self, path: str, private: bool = False) -> str:
        dumped = self.dump(path, private=private)
        if not dumped:
            return ""
        return dumped.read_text(encoding="utf-8", errors="replace")


def copy_partition(path: Path, offset: int, length: int, tempdir: Path) -> Path:
    target = tempdir / "rootfs.ext4"
    with path.open("rb") as src, target.open("wb") as dst:
        os.chmod(target, 0o600)
        src.seek(offset)
        remaining = length
        while remaining:
            data = src.read(min(remaining, 16 * 1024 * 1024))
            if not data:
                break
            dst.write(data)
            remaining -= len(data)
    return target


def overlay_conf_categories(text: str) -> dict[str, object]:
    overlay = None
    cfgdisk = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("overlayroot="):
            overlay = stripped.split("=", 1)[1].strip().strip('"').strip("'")
        elif stripped.startswith("overlayroot_cfgdisk="):
            cfgdisk = stripped.split("=", 1)[1].strip().strip('"').strip("'")
    def cat(value):
        if value is None:
            return "missing"
        if value == "":
            return "empty"
        if value == "tmpfs":
            return "tmpfs"
        if value in {"disabled", "disable"}:
            return "disabled"
        return "other"
    return {
        "present": bool(text),
        "overlayroot_category": cat(overlay),
        "cfgdisk_category": cat(cfgdisk),
    }


def cpio_listing_from_gzip(path: Path) -> str:
    try:
        data = gzip.decompress(path.read_bytes())
    except Exception:
        return ""
    proc = run(["cpio", "-it"], data=data, timeout=60)
    return proc.stdout.decode("utf-8", "replace")


def dumpimage_extract_uinitrd(path: Path, out_path: Path) -> bool:
    if not shutil.which("dumpimage") or not path.exists() or path.stat().st_size == 0:
        return False
    proc = subprocess.run(
        ["dumpimage", "-T", "ramdisk", "-p", "0", "-o", str(out_path), str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0


def bool_text(path: Path, pattern: str) -> bool:
    if not path.exists():
        return False
    return pattern in path.read_text(encoding="utf-8", errors="replace")


if not image.exists():
    raise SystemExit("image_missing")
if not shutil.which("debugfs"):
    raise SystemExit("debugfs_missing")

tempdir = Path(tempfile.mkdtemp(prefix="dadooh-c12-1-7-image-", dir="/tmp"))
os.chmod(tempdir, 0o700)
try:
    offset, length = parse_mbr_linux_partition(image)
    rootfs = copy_partition(image, offset, length, tempdir)
    debug = DebugFs(rootfs, tempdir)

    overlay_conf = debug.read_text("/etc/overlayroot.conf")
    armbian_env = debug.read_text("/boot/armbianEnv.txt")
    boot_cmd = debug.read_text("/boot/boot.cmd")
    boot_scr = debug.read_text("/boot/boot.scr")
    uinitrd = debug.dump("/boot/uInitrd")
    initrd = debug.dump("/boot/initrd.img-6.12.58-current-sunxi64")
    uinitrd_raw = tempdir / "uInitrd.raw"
    uinitrd_raw_extracted = bool(uinitrd and dumpimage_extract_uinitrd(uinitrd, uinitrd_raw))
    initrd_listing = cpio_listing_from_gzip(initrd) if initrd else ""
    uinitrd_listing = cpio_listing_from_gzip(uinitrd_raw) if uinitrd_raw_extracted else ""
    build_log_text = build_log.read_text(encoding="utf-8", errors="replace") if build_log.exists() else ""

    payload = {
        "schema_version": "dadooh-c12.1.7-image-artifact.v1",
        "image_artifact_inspected": True,
        "image_path_exists": image.exists(),
        "overlayroot_config_present_image": bool(overlay_conf),
        "overlayroot_conf": overlay_conf_categories(overlay_conf),
        "overlayroot_local_conf_present_image": debug.exists("/etc/overlayroot.local.conf"),
        "overlayroot_package_manifest_present": bool_text(package_manifest, "package=overlayroot "),
        "integration_manifest_present": integration_manifest.exists(),
        "integration_overlayroot_included": bool_text(integration_manifest, "overlayroot_included=true"),
        "integration_initramfs_generated_after_overlayroot": bool_text(integration_manifest, "initramfs_generated_after_overlayroot=true"),
        "hook_file_present_image": debug.exists("/usr/share/initramfs-tools/hooks/overlayroot"),
        "init_bottom_file_present_image": debug.exists("/usr/share/initramfs-tools/scripts/init-bottom/overlayroot"),
        "boot_cmd_present": bool(boot_cmd),
        "boot_scr_present": bool(boot_scr),
        "boot_uses_uinitrd": "uInitrd" in boot_cmd or "uInitrd" in boot_scr,
        "boot_uses_initrd_img": "initrd.img" in boot_cmd or "initrd.img" in boot_scr,
        "armbian_env_overlayroot_present": "overlayroot" in armbian_env,
        "armbian_env_extraargs_present": "extraargs=" in armbian_env,
        "armbian_env_uinitrd_reference_present": "uInitrd" in armbian_env,
        "uinitrd_exists_image": bool(uinitrd),
        "uinitrd_size": uinitrd.stat().st_size if uinitrd else -1,
        "uinitrd_size_category": "missing" if not uinitrd else ("empty" if uinitrd.stat().st_size == 0 else "nonempty"),
        "uinitrd_raw_extracted": uinitrd_raw_extracted,
        "uinitrd_contains_overlayroot": "scripts/init-bottom/overlayroot" in uinitrd_listing,
        "initrd_img_exists_image": bool(initrd),
        "initrd_img_size": initrd.stat().st_size if initrd else -1,
        "initrd_img_contains_overlayroot": "scripts/init-bottom/overlayroot" in initrd_listing,
        "initrd_img_contains_overlay_module": any("kernel/fs/overlayfs/overlay.ko" in line or "overlay.ko" in line for line in initrd_listing.splitlines()),
        "build_log_present": build_log.exists(),
        "build_log_updated_initramfs": "Updated initramfs" in build_log_text,
        "build_log_initrd_cache_hit": "initrd cache hit" in build_log_text,
        "build_log_overlayroot_package_install_seen": "Installing AGGREGATED_PACKAGES_IMAGE packages" in build_log_text and "overlayroot" in build_log_text,
        "private_values_published": False,
        "raw_logs_published": False,
    }
finally:
    shutil.rmtree(tempdir, ignore_errors=True)

print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/image-artifact.json"
}

compare_results() {
  python3 - "$OUT_DIR/running-board.json" "$OUT_DIR/image-artifact.json" > "$OUT_DIR/compare.json" <<'PY'
import json
import sys
from pathlib import Path

running_path = Path(sys.argv[1])
image_path = Path(sys.argv[2])
running = json.loads(running_path.read_text(encoding="utf-8")) if running_path.exists() else {}
image = json.loads(image_path.read_text(encoding="utf-8")) if image_path.exists() else {}

cause = "UNKNOWN"
recommended = "collect_missing_diagnostics_before_rebuild"
if image.get("boot_uses_uinitrd") and image.get("uinitrd_size_category") in {"empty", "missing"}:
    cause = "UINITRD_NOT_UPDATED"
    recommended = "rebuild_c12_1_8_with_nonempty_uInitrd_generated_from_overlayroot_initrd_or_fix_boot_script"
elif image.get("initrd_img_contains_overlayroot") and running.get("uinitrd_size_category") in {"empty", "missing"}:
    cause = "UINITRD_NOT_UPDATED"
    recommended = "ensure_boot_uses_the_initrd_that_contains_overlayroot"
elif not image.get("overlayroot_config_present_image"):
    cause = "CONFIG_NOT_IN_IMAGE"
    recommended = "fix_customize_image_overlayroot_conf"
elif not image.get("initrd_img_contains_overlayroot"):
    cause = "CONFIG_NOT_IN_INITRAMFS"
    recommended = "force_update_initramfs_after_overlayroot_install"
elif not image.get("build_log_updated_initramfs") and image.get("build_log_initrd_cache_hit"):
    cause = "INITRAMFS_CACHE_HIT_REUSED_WITHOUT_UINITRD_UPDATE"
    recommended = "disable_initrd_cache_or force uInitrd regeneration after customize-image"
elif running.get("cmdline_overlayroot_present") is False and image.get("boot_uses_uinitrd"):
    cause = "BOOT_ARGS_MISSING_OR_NOT_REQUIRED"
    recommended = "verify_overlayroot_package_expected_activation_path_before_rebuild"

payload = {
    "schema_version": "dadooh-c12.1.7-overlayroot-activation-compare.v1",
    "running_board_inspected": bool(running),
    "image_artifact_inspected": bool(image),
    "overlayroot_config_present_running": bool(running.get("overlayroot_conf", {}).get("present")),
    "overlayroot_config_present_image": bool(image.get("overlayroot_config_present_image")),
    "overlayroot_config_category_running": running.get("overlayroot_conf", {}).get("overlayroot_category", "unknown"),
    "overlayroot_config_category_image": image.get("overlayroot_conf", {}).get("overlayroot_category", "unknown"),
    "initramfs_contains_overlayroot": bool(image.get("initrd_img_contains_overlayroot") or image.get("uinitrd_contains_overlayroot")),
    "initrd_img_contains_overlayroot": bool(image.get("initrd_img_contains_overlayroot")),
    "uinitrd_contains_overlayroot": bool(image.get("uinitrd_contains_overlayroot")),
    "uinitrd_updated": image.get("uinitrd_size_category") == "nonempty",
    "uinitrd_size_category_image": image.get("uinitrd_size_category", "unknown"),
    "uinitrd_size_category_running": running.get("uinitrd_size_category", "unknown"),
    "boot_uses_uinitrd": bool(image.get("boot_uses_uinitrd")),
    "boot_args_overlay_present": bool(running.get("cmdline_overlayroot_present") or image.get("armbian_env_overlayroot_present")),
    "overlay_active": bool(running.get("overlay_active")),
    "read_only_enabled": bool(running.get("read_only_enabled")),
    "root_write_blocked": bool(running.get("root_write_blocked")),
    "initramfs_log_driver_lookup_failed": bool(running.get("initramfs_log_driver_lookup_failed")),
    "cause_category": cause,
    "recommended_fix": recommended,
    "next_step": "C12.1.8 rebuild image-lab overlayroot boot initrd fix" if cause != "UNKNOWN" else "C12.1.8 or deeper Armbian initramfs investigation",
    "raw_logs_published": False,
    "secrets_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/compare.json"
}

write_summary() {
  python3 - "$OUT_DIR" > "$OUT_DIR/summary.txt" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
def load(name):
    path = out / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

running = load("running-board.json")
image = load("image-artifact.json")
compare = load("compare.json")
print("C12.1.7 overlayroot activation diagnose")
print(f"running_board_inspected: {str(bool(running)).lower()}")
print(f"image_artifact_inspected: {str(bool(image)).lower()}")
print(f"overlay_active: {str(compare.get('overlay_active', running.get('overlay_active', False))).lower()}")
print(f"read_only_enabled: {str(compare.get('read_only_enabled', running.get('read_only_enabled', False))).lower()}")
print(f"root_write_blocked: {str(compare.get('root_write_blocked', running.get('root_write_blocked', False))).lower()}")
print(f"uinitrd_size_category_image: {compare.get('uinitrd_size_category_image', image.get('uinitrd_size_category', 'unknown'))}")
print(f"uinitrd_size_category_running: {compare.get('uinitrd_size_category_running', running.get('uinitrd_size_category', 'unknown'))}")
print(f"initrd_img_contains_overlayroot: {str(compare.get('initrd_img_contains_overlayroot', image.get('initrd_img_contains_overlayroot', False))).lower()}")
print(f"boot_uses_uinitrd: {str(compare.get('boot_uses_uinitrd', image.get('boot_uses_uinitrd', False))).lower()}")
print(f"cause_category: {compare.get('cause_category', 'UNKNOWN')}")
print(f"recommended_fix: {compare.get('recommended_fix', 'unknown')}")
PY
  chmod 600 "$OUT_DIR/summary.txt"
}

case "$MODE" in
  prepare-only)
    prepare_only
    ;;
  inspect-running-board)
    inspect_running_board
    ;;
  inspect-image-artifact)
    inspect_image_artifact
    ;;
  compare)
    compare_results
    write_summary
    ;;
  summary)
    write_summary
    ;;
  *)
    echo "error: unsupported mode $MODE" >&2
    exit 2
    ;;
esac

printf 'out_dir=%s\n' "$OUT_DIR"
