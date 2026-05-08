#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
TIMESTAMP="${C12_3_8_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${C12_3_8_RUN_ROOT:-/tmp/dadooh-c12-3-8-readonly-mechanism-decision}"
OUT_DIR="${C12_3_8_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-3-8-readonly-mechanism-decision}"
KNOWN_HOSTS="${C12_3_8_KNOWN_HOSTS:-/tmp/dadooh-c12-3-8-known-hosts}"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_3_8_readonly_mechanism_decision.sh [root@host] [mode]

Modes:
  --prepare-only
  --inspect-running
  --inspect-initramfs
  --inspect-overlayroot-script
  --classify
  --summary

Rules:
  - decision gate only on the disposable C12 image-lab board;
  - read-only diagnostics by default;
  - no remount, reboot, poweroff, writer, real config, Wi-Fi changes,
    package install, apt upgrade, or raw log publication;
  - no repeated overlayroot enable attempts.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect-running) MODE="inspect-running" ;;
    --inspect-initramfs) MODE="inspect-initramfs" ;;
    --inspect-overlayroot-script) MODE="inspect-overlayroot-script" ;;
    --classify) MODE="classify" ;;
    --summary) MODE="summary" ;;
    --help|-h) usage; exit 0 ;;
    --*) echo "error: unsupported mode $1" >&2; usage; exit 2 ;;
    *) HOST="$1" ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|inspect-running|inspect-initramfs|inspect-overlayroot-script|classify|summary) ;;
  *) echo "error: unsupported mode $MODE" >&2; usage; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"

ssh_board() {
  if [ -z "$HOST" ]; then
    echo "error: host is required for $MODE" >&2
    exit 2
  fi
  ssh \
    -o UserKnownHostsFile="$KNOWN_HOSTS" \
    -o StrictHostKeyChecking=accept-new \
    -o ServerAliveInterval=10 \
    -o ServerAliveCountMax=3 \
    "$HOST" "$@"
}

prepare_only() {
  git -C "$REPO_ROOT" diff --check
  bash -n "$0"
  bash -n "$REPO_ROOT/scripts/remote/run_c12_3_7_overlay_module_initramfs_lab.sh"
  bash -n "$REPO_ROOT/scripts/remote/run_c12_3_6_overlayroot_runtime_lab.sh"
  bash -n "$REPO_ROOT/scripts/build/run_c12_1_build_image_lab_readonly.sh"
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  {
    printf 'c12_3_8_prepare_only=ok\n'
    printf 'repo_diff_check=ok\n'
    printf 'writer_called=false\n'
    printf 'real_config_written=false\n'
    printf 'wifi_changed=false\n'
    printf 'packages_installed=false\n'
    printf 'poweroff_executed=false\n'
    printf 'reboot_executed=false\n'
  } > "$OUT_DIR/prepare.env"
  cat "$OUT_DIR/prepare.env"
}

inspect_running() {
  ssh_board "python3 -" > "$OUT_DIR/running.json" <<'PY'
import json
import pathlib
import re
import subprocess


def run(cmd, timeout=20):
    try:
        return subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=timeout,
        )
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, "", "")


def shell(command, timeout=20):
    return (run(["sh", "-lc", command], timeout=timeout).stdout or "").strip()


def exists(path):
    return pathlib.Path(path).exists()


def read_text(path, limit=1024 * 1024):
    try:
        p = pathlib.Path(path)
        if p.stat().st_size > limit:
            return p.read_text(encoding="utf-8", errors="replace")[:limit]
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def command_available(name):
    return bool(shell(f"command -v {name} 2>/dev/null || true"))


def package_installed(name):
    return shell(f"dpkg-query -W -f='${{Status}}' {name} 2>/dev/null || true") == "install ok installed"


def parse_kv_file(path):
    values = {}
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def category_value(value):
    if value is None:
        return "missing"
    if value == "":
        return "empty"
    if value == "tmpfs":
        return "tmpfs"
    if value in {"disabled", "disable"}:
        return "disabled"
    return "other"


def overlay_conf(path):
    values = parse_kv_file(path)
    return {
        "present": exists(path),
        "overlayroot_category": category_value(values.get("overlayroot")),
        "overlayroot_cfgdisk_category": category_value(values.get("overlayroot_cfgdisk")),
    }


def file_size_bucket(path):
    try:
        size = pathlib.Path(path).stat().st_size
    except OSError:
        return "missing"
    if size == 0:
        return "empty"
    if size < 1024 * 1024:
        return "small"
    return "nonempty"


def mount_info(target):
    text = shell(f"findmnt -n -o SOURCE,FSTYPE,OPTIONS --target {target} 2>/dev/null || true")
    parts = text.split(None, 2)
    source = parts[0] if parts else ""
    options = parts[2] if len(parts) > 2 else ""
    option_set = {item.strip() for item in options.split(",")}
    return {
        "present": bool(parts),
        "source_category": "overlay" if source == "overlay" else ("device" if source.startswith("/dev/") else source if source in {"tmpfs", "proc", "sysfs"} else "other"),
        "fstype": parts[1] if len(parts) > 1 else "unknown",
        "options_category": "ro" if "ro" in option_set else "rw_or_unknown",
        "overlay_upperdir_present": "upperdir=" in options,
        "overlay_workdir_present": "workdir=" in options,
    }


def service(name):
    return {
        "active": shell(f"systemctl is-active {name} 2>/dev/null || true") or "unknown",
        "enabled": shell(f"systemctl is-enabled {name} 2>/dev/null || true") or "unknown",
        "result": shell(f"systemctl show {name} -p Result --value 2>/dev/null || true") or "unknown",
        "n_restarts": shell(f"systemctl show {name} -p NRestarts --value 2>/dev/null || echo 0") or "0",
    }


def boot_snapshot():
    cmdline = read_text("/proc/cmdline")
    env = read_text("/boot/armbianEnv.txt")
    boot_cmd = read_text("/boot/boot.cmd")
    if not boot_cmd and exists("/boot/boot.scr"):
        boot_cmd = shell("strings /boot/boot.scr 2>/dev/null | grep -E 'uInitrd|initrd|bootargs|extraargs' || true")
    env_values = parse_kv_file("/boot/armbianEnv.txt")
    extraargs = env_values.get("extraargs", "")
    bootargs = env_values.get("bootargs", "")
    return {
        "kernel_version": shell("uname -r"),
        "cmdline_overlayroot_present": "overlayroot" in cmdline,
        "cmdline_root_present": bool(re.search(r"(^|\\s)root=", cmdline)),
        "cmdline_console_category": "serial" if "console=ttyS" in cmdline else ("tty" if "console=tty" in cmdline else "none"),
        "armbian_env_present": exists("/boot/armbianEnv.txt"),
        "armbian_env_overlayroot_present": "overlayroot" in env,
        "extraargs_overlayroot_present": "overlayroot=" in extraargs,
        "bootargs_overlayroot_present": "overlayroot=" in bootargs,
        "boot_script_uses_uinitrd": "uInitrd" in boot_cmd,
        "boot_script_uses_initrd_img": "initrd.img" in boot_cmd,
    }


def module_snapshot():
    module_path = shell("modinfo -n overlay 2>/dev/null || true")
    modprobe_dry = run(["modprobe", "-n", "-v", "overlay"], timeout=15)
    proc_filesystems = read_text("/proc/filesystems")
    lsmod = shell("lsmod 2>/dev/null | awk '$1 == \"overlay\" {print $1}' | head -1 || true")
    modules_text = read_text("/etc/initramfs-tools/modules")
    return {
        "overlay_module_path_exists": bool(module_path),
        "overlay_module_path_category": "kernel_module" if module_path.endswith((".ko", ".ko.xz", ".ko.zst")) else ("builtin_or_unknown" if module_path else "missing"),
        "modprobe_overlay_dry_run_ok": modprobe_dry.returncode == 0,
        "runtime_proc_filesystems_contains_overlay": bool(re.search(r"(^|\\n)nodev\\s+overlay(\\n|$)", proc_filesystems)),
        "runtime_lsmod_overlay_loaded": lsmod == "overlay",
        "initramfs_tools_modules_contains_overlay": any(line.strip() == "overlay" for line in modules_text.splitlines()),
        "force_overlay_hook_present": exists("/etc/initramfs-tools/scripts/init-top/dadooh-force-overlay"),
    }


def initramfs_log_snapshot():
    initramfs_log = read_text("/run/initramfs/overlayroot.log", limit=256 * 1024)
    force_hook_status = read_text("/run/initramfs/dadooh-overlay-module.status", limit=4096)
    journal = shell("journalctl -k -b --no-pager 2>/dev/null | grep -Ei 'overlayroot|cloud-initramfs|initramfs|overlay|driver|module' || true", timeout=25)
    lowered = (initramfs_log + "\n" + force_hook_status + "\n" + journal).lower()
    if "unable to find driver/module" in lowered or "unable to find a driver" in lowered:
        category = "modprobe_overlay_failed"
    elif "loaded 'overlay' module but no 'overlay' in /proc/filesystems" in lowered:
        category = "modprobe_overlay_success_but_driver_unregistered"
    elif "mount" in lowered and "overlay" in lowered and ("failed" in lowered or "invalid" in lowered):
        category = "mount_overlay_failed"
    elif "overlayroot" in lowered and ("skip" in lowered or "skipping" in lowered):
        category = "overlayroot_skipped_before_mount"
    elif "overlayroot" in lowered:
        category = "overlayroot_seen_unclassified"
    else:
        category = "unknown"
    return {
        "overlayroot_log_seen": "overlayroot" in lowered,
        "overlayroot_hook_started": "overlayroot" in lowered,
        "overlayroot_read_config": "tmpfs" in lowered or "overlayroot=tmpfs" in lowered,
        "overlayroot_mode_tmpfs": "tmpfs" in lowered,
        "modprobe_overlay_attempted": "modprobe" in lowered and "overlay" in lowered,
        "force_hook_status_present": bool(force_hook_status),
        "force_hook_modprobe_overlay_success": "overlay_modprobe=ok" in force_hook_status,
        "force_hook_modprobe_overlay_failed": "overlay_modprobe=failed" in force_hook_status,
        "modprobe_overlay_success": (
            True if "overlay_modprobe=ok" in force_hook_status
            else False if "overlay_modprobe=failed" in force_hook_status or category in {"modprobe_overlay_failed"} else "unknown"
        ),
        "mount_overlay_attempted": "mount" in lowered and "overlay" in lowered,
        "mount_overlay_success": True if "overlayroot mounted" in lowered or "overlay mounted" in lowered else (False if category == "mount_overlay_failed" else "unknown"),
        "overlay_in_proc_filesystems_before_attempt": "no 'overlay' in /proc/filesystems" not in lowered if "proc/filesystems" in lowered else "unknown",
        "overlay_in_proc_filesystems_after_modprobe": False if "loaded 'overlay' module but no 'overlay' in /proc/filesystems" in lowered else "unknown",
        "failure_category": category,
        "raw_logs_published": False,
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
    return {
        "public_state": public.get("public_state") or public.get("state") or launcher.get("state", "unknown"),
        "playback": public.get("playback") or public.get("playback_state") or "unknown",
    }


root_mount = mount_info("/")
payload = {
    "schema_version": "dadooh-c12.3.8-readonly-mechanism-running.v1",
    "running_board_inspected": True,
    "board_category": "lab_board",
    "uptime_bucket": "under_10m" if float(shell("cut -d. -f1 /proc/uptime 2>/dev/null || echo 0") or 0) < 600 else "over_10m",
    "mount_root": root_mount,
    "mount_data": mount_info("/data"),
    "mount_tmp": mount_info("/tmp"),
    "mount_run": mount_info("/run"),
    "read_only_enabled": root_mount["source_category"] == "overlay" or root_mount["options_category"] == "ro",
    "overlay_active": root_mount["source_category"] == "overlay" or root_mount["fstype"] == "overlay",
    "root_write_blocked": root_mount["options_category"] == "ro" or root_mount["source_category"] == "overlay",
    "overlayroot_package_installed": package_installed("overlayroot"),
    "overlayroot_chroot_present": command_available("overlayroot-chroot"),
    "overlayroot_conf": overlay_conf("/etc/overlayroot.conf"),
    "overlayroot_local_conf": overlay_conf("/etc/overlayroot.local.conf"),
    "initrd_img_exists": exists(f"/boot/initrd.img-{shell('uname -r')}"),
    "initrd_img_size_bucket": file_size_bucket(f"/boot/initrd.img-{shell('uname -r')}"),
    "uinitrd_exists": exists("/boot/uInitrd"),
    "uinitrd_size_bucket": file_size_bucket("/boot/uInitrd"),
    "boot": boot_snapshot(),
    "module": module_snapshot(),
    "logs": initramfs_log_snapshot(),
    "services": {
        "kiosky-player.service": service("kiosky-player.service"),
        "totem-settings-trigger.service": service("totem-settings-trigger.service"),
        "totem-open-settings.service": service("totem-open-settings.service"),
        "dadooh-visual-splash.service": service("dadooh-visual-splash.service"),
    },
    "systemctl_failed_count": shell("systemctl --failed --no-legend 2>/dev/null | wc -l | tr -d ' '") or "unknown",
    "product": status_snapshot(),
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
    "reboot_executed": False,
    "poweroff_executed": False,
    "raw_logs_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/running.json"
}

inspect_initramfs() {
  if [ -z "$HOST" ]; then
    echo "error: host is required for $MODE" >&2
    exit 2
  fi
  local kernel
  kernel="$(ssh_board "uname -r")"
  local tempdir
  tempdir="$(mktemp -d "$OUT_DIR/initramfs.XXXXXX")"
  chmod 700 "$tempdir"
  trap 'rm -rf "$tempdir"' RETURN

  ssh_board "test -f /boot/initrd.img-$kernel && cat /boot/initrd.img-$kernel || true" > "$tempdir/initrd.img"
  ssh_board "test -f /boot/uInitrd && cat /boot/uInitrd || true" > "$tempdir/uInitrd"
  ssh_board "test -f /boot/boot.cmd && cat /boot/boot.cmd || (test -f /boot/boot.scr && strings /boot/boot.scr || true)" > "$tempdir/boot-script.txt"
  ssh_board "test -f /boot/armbianEnv.txt && sed -n '/overlayroot\\|uInitrd\\|bootargs\\|extraargs\\|verbosity\\|console\\|loglevel/p' /boot/armbianEnv.txt || true" > "$tempdir/armbian-env-categories.txt"

  python3 - "$tempdir" "$kernel" > "$OUT_DIR/initramfs.json" <<'PY'
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

tempdir = Path(sys.argv[1])
kernel = sys.argv[2]
initrd = tempdir / "initrd.img"
uinitrd = tempdir / "uInitrd"
uinitrd_raw = tempdir / "uInitrd.raw"
boot_script = (tempdir / "boot-script.txt").read_text(encoding="utf-8", errors="replace")
armbian_env_categories = (tempdir / "armbian-env-categories.txt").read_text(encoding="utf-8", errors="replace")


def run(cmd, input_bytes=None, timeout=60):
    try:
        return subprocess.run(
            cmd,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=timeout,
        )
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, b"", b"")


def extract_uinitrd():
    if not shutil.which("dumpimage") or not uinitrd.exists() or uinitrd.stat().st_size == 0:
        return False
    proc = run(["dumpimage", "-T", "ramdisk", "-p", "0", "-o", str(uinitrd_raw), str(uinitrd)])
    return proc.returncode == 0 and uinitrd_raw.exists() and uinitrd_raw.stat().st_size > 0


def cpio_listing(path):
    if not path.exists() or path.stat().st_size == 0:
        return ""
    try:
        data = gzip.decompress(path.read_bytes())
    except Exception:
        return ""
    proc = run(["cpio", "-it"], input_bytes=data)
    return proc.stdout.decode("utf-8", "replace") if proc.returncode == 0 else ""


def sha256(path):
    if not path.exists() or path.stat().st_size == 0:
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def listing_has_any(listing, needles):
    return any(needle in listing for needle in needles)


def listing_has_relevant_module(listing):
    return "kernel/fs/overlayfs/overlay.ko" in listing or "overlay.ko" in listing


def file_size_bucket(path):
    if not path.exists():
        return "missing"
    size = path.stat().st_size
    if size == 0:
        return "empty"
    if size < 1024 * 1024:
        return "small"
    return "nonempty"


uinitrd_payload_extracted = extract_uinitrd()
initrd_listing = cpio_listing(initrd)
uinitrd_listing = cpio_listing(uinitrd_raw) if uinitrd_payload_extracted else ""
effective_listing = uinitrd_listing or initrd_listing
payload_hash_matches = bool(uinitrd_payload_extracted and sha256(initrd) and sha256(initrd) == sha256(uinitrd_raw))

payload = {
    "schema_version": "dadooh-c12.3.8-readonly-mechanism-initramfs.v1",
    "initramfs_inspected": True,
    "kernel_version": kernel,
    "initrd_img_exists": initrd.exists(),
    "initrd_img_size_bucket": file_size_bucket(initrd),
    "uinitrd_exists": uinitrd.exists(),
    "uinitrd_size_bucket": file_size_bucket(uinitrd),
    "uinitrd_payload_extracted": uinitrd_payload_extracted,
    "uinitrd_payload_matches_initrd_img": payload_hash_matches,
    "boot_script_uses_uinitrd": "uInitrd" in boot_script,
    "boot_script_uses_initrd_img": "initrd.img" in boot_script,
    "armbian_env_overlayroot_present": "overlayroot" in armbian_env_categories,
    "armbian_env_uinitrd_present": "uInitrd" in armbian_env_categories,
    "initrd_contains_overlayroot_hook": "scripts/init-bottom/overlayroot" in initrd_listing,
    "uinitrd_contains_overlayroot_hook": "scripts/init-bottom/overlayroot" in uinitrd_listing,
    "effective_contains_overlayroot_hook": "scripts/init-bottom/overlayroot" in effective_listing,
    "initrd_contains_force_overlay_hook": "dadooh-force-overlay" in initrd_listing,
    "uinitrd_contains_force_overlay_hook": "dadooh-force-overlay" in uinitrd_listing,
    "effective_contains_force_overlay_hook": "dadooh-force-overlay" in effective_listing,
    "initrd_contains_overlay_module": listing_has_relevant_module(initrd_listing),
    "uinitrd_contains_overlay_module": listing_has_relevant_module(uinitrd_listing),
    "effective_contains_overlay_module": listing_has_relevant_module(effective_listing),
    "effective_contains_modules_dep": listing_has_any(effective_listing, [f"lib/modules/{kernel}/modules.dep", "modules.dep"]),
    "effective_contains_modules_alias": listing_has_any(effective_listing, [f"lib/modules/{kernel}/modules.alias", "modules.alias"]),
    "effective_contains_modprobe": listing_has_any(effective_listing, ["bin/modprobe", "sbin/modprobe", "usr/sbin/modprobe", "usr/bin/kmod", "bin/kmod", "sbin/kmod"]),
    "effective_contains_busybox": "bin/busybox" in effective_listing or "usr/bin/busybox" in effective_listing,
    "effective_contains_c12_1_8_marker": "c12-overlayroot-initramfs-marker" in effective_listing,
    "effective_contains_c12_3_7_hook": "dadooh-force-overlay" in effective_listing,
    "effective_contains_overlayroot_conf": "etc/overlayroot.conf" in effective_listing,
    "raw_listing_published": False,
    "raw_initramfs_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/initramfs.json"
}

inspect_overlayroot_script() {
  ssh_board "python3 -" > "$OUT_DIR/overlayroot-script.json" <<'PY'
import json
import pathlib
import re

paths = [
    pathlib.Path("/usr/share/initramfs-tools/scripts/init-bottom/overlayroot"),
    pathlib.Path("/usr/share/initramfs-tools/scripts/local-bottom/overlayroot"),
    pathlib.Path("/usr/share/initramfs-tools/hooks/overlayroot"),
]


def read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


script_path = paths[0]
script = read(script_path)
hook = read(paths[2])
combined = script + "\n" + hook
lowered = combined.lower()

payload = {
    "schema_version": "dadooh-c12.3.8-readonly-mechanism-script.v1",
    "overlayroot_script_present": script_path.exists(),
    "overlayroot_script_phase": "init-bottom" if script_path.exists() else "missing",
    "overlayroot_hook_present": paths[2].exists(),
    "script_calls_modprobe_overlay": "modprobe" in lowered and ("overlay" in lowered or "driver" in lowered),
    "script_checks_proc_filesystems": "/proc/filesystems" in combined,
    "script_uses_mount_overlay": "-t overlay" in combined or "mount -t" in lowered and "overlay" in lowered,
    "script_loads_driver_before_mount": ("modprobe" in lowered and "/proc/filesystems" in lowered),
    "script_mentions_tmpfs_mode": "tmpfs" in lowered,
    "script_mentions_cfgdisk": "cfgdisk" in lowered,
    "script_has_failure_unable_driver_message": "unable to find driver" in lowered or "unable to find a driver" in lowered,
    "script_has_loaded_overlay_but_no_proc_filesystems_message": "loaded" in lowered and "proc/filesystems" in lowered,
    "script_may_exit_zero_after_failure": "exit 0" in lowered and ("unable to find" in lowered or "failure" in lowered),
    "script_raw_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/overlayroot-script.json"
}

classify_results() {
  python3 - "$OUT_DIR/running.json" "$OUT_DIR/initramfs.json" "$OUT_DIR/overlayroot-script.json" > "$OUT_DIR/classification.json" <<'PY'
import json
import sys
from pathlib import Path


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


running = load(sys.argv[1])
initramfs = load(sys.argv[2])
script = load(sys.argv[3])
logs = running.get("logs", {})
module = running.get("module", {})
conf = running.get("overlayroot_conf", {})

overlay_module_present = bool(initramfs.get("effective_contains_overlay_module"))
modules_dep_present = bool(initramfs.get("effective_contains_modules_dep"))
modprobe_present = bool(initramfs.get("effective_contains_modprobe"))
overlayroot_hook_present = bool(initramfs.get("effective_contains_overlayroot_hook"))
force_hook_present = bool(initramfs.get("effective_contains_force_overlay_hook"))
cmdline_overlayroot = bool(running.get("boot", {}).get("cmdline_overlayroot_present"))
mode_tmpfs = conf.get("overlayroot_category") == "tmpfs"
failure = logs.get("failure_category", "unknown")

if not overlayroot_hook_present:
    cause = "OVERLAYROOT_HOOK_MISSING_FROM_EFFECTIVE_INITRAMFS"
    next_step = "C12.1.9_REBUILD_WITH_OVERLAYROOT_HOOK_IN_EFFECTIVE_INITRAMFS"
elif not cmdline_overlayroot and not mode_tmpfs:
    cause = "CONFIG_NOT_READ_OR_BOOT_ARGS_MISSING"
    next_step = "C12.3.9_CONFIG_PATH_OR_BOOT_ARGS_DECISION"
elif not overlay_module_present:
    cause = "OVERLAY_MODULE_MISSING_IN_INITRAMFS"
    next_step = "C12.1.9_REBUILD_WITH_OVERLAY_MODULE_IN_INITRAMFS"
elif not modules_dep_present:
    cause = "MODULES_DEP_MISSING_IN_INITRAMFS"
    next_step = "C12.3.9_FIX_INITRAMFS_MODULE_DEPENDENCIES"
elif not modprobe_present:
    cause = "MODPROBE_MISSING_IN_INITRAMFS"
    next_step = "C12.3.9_FIX_INITRAMFS_MODULE_LOADING"
elif failure in {"modprobe_overlay_failed", "modprobe_overlay_success_but_driver_unregistered"}:
    cause = "OVERLAY_MODULE_PRESENT_BUT_NOT_REGISTERED_IN_INITRAMFS_RUNTIME"
    next_step = "C12.3.9_FIX_INITRAMFS_MODULE_LOADING_OR_KERNEL_OVERLAY_COMPATIBILITY"
elif script.get("script_checks_proc_filesystems") and not logs.get("mount_overlay_attempted", False):
    cause = "OVERLAYROOT_SKIPPED_BEFORE_MOUNT_DUE_DRIVER_CHECK"
    next_step = "C12.3.9_OVERLAYROOT_SCRIPT_COMPATIBILITY"
elif logs.get("mount_overlay_attempted") and logs.get("mount_overlay_success") is False:
    cause = "MOUNT_OVERLAY_FAILED"
    next_step = "C12.3.9_OVERLAYROOT_SCRIPT_COMPATIBILITY"
else:
    cause = "UNKNOWN_MECHANISM_FAILURE"
    next_step = "ADR_UPDATE_SELECT_ALTERNATIVE_READONLY_MECHANISM"

decision = "root_read_only_continues_blocked"
if cause == "OVERLAY_MODULE_MISSING_IN_INITRAMFS":
    decision = "overlayroot_correctable_by_rebuild"
elif cause in {
    "MODULES_DEP_MISSING_IN_INITRAMFS",
    "MODPROBE_MISSING_IN_INITRAMFS",
    "OVERLAY_MODULE_PRESENT_BUT_NOT_REGISTERED_IN_INITRAMFS_RUNTIME",
    "OVERLAYROOT_SKIPPED_BEFORE_MOUNT_DUE_DRIVER_CHECK",
    "MOUNT_OVERLAY_FAILED",
}:
    decision = "overlayroot_requires_deeper_initramfs_fix"
elif cause == "UNKNOWN_MECHANISM_FAILURE":
    decision = "alternative_readonly_mechanism_decision_required"

payload = {
    "schema_version": "dadooh-c12.3.8-readonly-mechanism-classification.v1",
    "initramfs_inspected": bool(initramfs.get("initramfs_inspected")),
    "running_board_inspected": bool(running.get("running_board_inspected")),
    "overlayroot_script_present": bool(script.get("overlayroot_script_present")),
    "overlayroot_hook_started": logs.get("overlayroot_hook_started", "unknown"),
    "overlayroot_read_config": logs.get("overlayroot_read_config", "unknown"),
    "overlayroot_mode": "tmpfs" if mode_tmpfs else conf.get("overlayroot_category", "unknown"),
    "overlay_module_present_in_initramfs": overlay_module_present,
    "modules_dep_present": modules_dep_present,
    "modules_alias_present": bool(initramfs.get("effective_contains_modules_alias")),
    "modprobe_present": modprobe_present,
    "busybox_present": bool(initramfs.get("effective_contains_busybox")),
    "force_overlay_hook_present": force_hook_present,
    "modprobe_overlay_dry_run_ok_runtime": module.get("modprobe_overlay_dry_run_ok", "unknown"),
    "runtime_proc_filesystems_contains_overlay": module.get("runtime_proc_filesystems_contains_overlay", "unknown"),
    "runtime_lsmod_overlay_loaded": module.get("runtime_lsmod_overlay_loaded", "unknown"),
    "modprobe_overlay_attempted": logs.get("modprobe_overlay_attempted", "unknown"),
    "modprobe_overlay_success": logs.get("modprobe_overlay_success", "unknown"),
    "mount_overlay_attempted": logs.get("mount_overlay_attempted", "unknown"),
    "mount_overlay_success": logs.get("mount_overlay_success", "unknown"),
    "read_only_enabled": running.get("read_only_enabled", False),
    "overlay_active": running.get("overlay_active", False),
    "root_write_blocked": running.get("root_write_blocked", False),
    "cause_category": cause,
    "decision": decision,
    "recommended_next_step": next_step,
    "c12_4_blocked": True,
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
    "raw_logs_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/classification.json"
}

summary() {
  local classification="$OUT_DIR/classification.json"
  if [ ! -f "$classification" ]; then
    classify_results
  fi
  python3 - "$classification" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
keys = [
    "running_board_inspected",
    "initramfs_inspected",
    "overlayroot_script_present",
    "overlay_module_present_in_initramfs",
    "modules_dep_present",
    "modprobe_present",
    "overlayroot_hook_started",
    "modprobe_overlay_success",
    "mount_overlay_attempted",
    "read_only_enabled",
    "overlay_active",
    "root_write_blocked",
    "cause_category",
    "decision",
    "recommended_next_step",
]
for key in keys:
    print(f"{key}={data.get(key)}")
PY
}

case "$MODE" in
  prepare-only) prepare_only ;;
  inspect-running) inspect_running; cat "$OUT_DIR/running.json" ;;
  inspect-initramfs) inspect_initramfs; cat "$OUT_DIR/initramfs.json" ;;
  inspect-overlayroot-script) inspect_overlayroot_script; cat "$OUT_DIR/overlayroot-script.json" ;;
  classify) classify_results; cat "$OUT_DIR/classification.json" ;;
  summary) summary ;;
esac
