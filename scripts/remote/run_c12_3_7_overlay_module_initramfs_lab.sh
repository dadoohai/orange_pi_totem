#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
TIMESTAMP="${C12_3_7_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${C12_3_7_RUN_ROOT:-/tmp/dadooh-c12-3-7-overlay-module-initramfs-lab}"
OUT_DIR="${C12_3_7_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-3-7-overlay-module-initramfs-lab}"
KNOWN_HOSTS="${C12_3_7_KNOWN_HOSTS:-/tmp/dadooh-c12-3-7-known-hosts}"
CONFIRM_APPLY="${C12_3_7_CONFIRM_APPLY:-}"
CONFIRM_REBOOT="${C12_3_7_CONFIRM_REBOOT:-}"
EXPECTED_APPLY_CONFIRM="CONFIRMO APLICAR OVERLAY MODULE INITRAMFS C12.3.7"
EXPECTED_REBOOT_CONFIRM="CONFIRMO REBOOT OVERLAY MODULE C12.3.7"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_3_7_overlay_module_initramfs_lab.sh [root@host] [mode]

Modes:
  --prepare-only
  --inspect
  --plan
  --apply-force-module
  --apply-force-load-hook
  --reboot-check
  --rollback
  --summary

Environment:
  C12_3_7_CONFIRM_APPLY="CONFIRMO APLICAR OVERLAY MODULE INITRAMFS C12.3.7"
      Required for --apply-force-module and --apply-force-load-hook.
  C12_3_7_CONFIRM_REBOOT="CONFIRMO REBOOT OVERLAY MODULE C12.3.7"
      Required for --reboot-check.

Rules:
  - runtime lab only on the disposable C12.1.8 image-lab board;
  - no dev board, old test board, writer, real config, Wi-Fi changes, packages,
    apt upgrade, poweroff, power cut, secrets or raw logs;
  - inspect and plan are read-only;
  - apply changes one hypothesis at a time with backups and rollback state;
  - at most two hypothesis->reboot->verification cycles in this runner.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --plan) MODE="plan" ;;
    --apply-force-module) MODE="apply-force-module" ;;
    --apply-force-load-hook) MODE="apply-force-load-hook" ;;
    --reboot-check) MODE="reboot-check" ;;
    --rollback) MODE="rollback" ;;
    --summary) MODE="summary" ;;
    --help|-h) usage; exit 0 ;;
    --*) echo "error: unsupported mode $1" >&2; usage; exit 2 ;;
    *) HOST="$1" ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|inspect|plan|apply-force-module|apply-force-load-hook|reboot-check|rollback|summary) ;;
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
  bash -n "$REPO_ROOT/scripts/remote/run_c12_3_6_overlayroot_runtime_lab.sh"
  bash -n "$REPO_ROOT/scripts/build/run_c12_1_build_image_lab_readonly.sh"
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  {
    printf 'c12_3_7_prepare_only=ok\n'
    printf 'repo_diff_check=ok\n'
    printf 'writer_called=false\n'
    printf 'real_config_written=false\n'
    printf 'wifi_changed=false\n'
    printf 'packages_installed=false\n'
    printf 'poweroff_executed=false\n'
  } > "$OUT_DIR/prepare.env"
  cat "$OUT_DIR/prepare.env"
}

remote_inspect() {
  ssh_board "python3 -" > "$OUT_DIR/inspect.json" <<'PY'
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


def read_text(path, limit=512 * 1024):
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


def writable_probe(directory):
    if directory not in {"/data", "/tmp", "/run"}:
        return "not_executed"
    target = pathlib.Path("/data/state") if directory == "/data" else pathlib.Path(directory)
    try:
        target.mkdir(parents=True, exist_ok=True)
        path = target / ".dadooh-c12-3-7-writable-probe"
        path.write_text("ok\n", encoding="utf-8")
        path.unlink()
        return True
    except Exception:
        return False


def latest_initrd_path():
    kernel = shell("uname -r")
    candidates = [pathlib.Path(f"/boot/initrd.img-{kernel}")]
    candidates.extend(sorted(pathlib.Path("/boot").glob("initrd.img*")))
    for path in candidates:
        if path.exists():
            return str(path)
    return ""


def initramfs_listing(path):
    if not path or not command_available("lsinitramfs"):
        return ""
    return shell(f"lsinitramfs {path} 2>/dev/null | grep -E 'overlayroot|overlay\\.ko|c12-overlayroot-initramfs-marker|etc/initramfs-tools/modules|dadooh-force-overlay' || true", timeout=30)


def uinitrd_listing():
    if not exists("/boot/uInitrd"):
        return ""
    if command_available("lsinitramfs"):
        listing = shell("lsinitramfs /boot/uInitrd 2>/dev/null | grep -E 'overlayroot|overlay\\.ko|c12-overlayroot-initramfs-marker|etc/initramfs-tools/modules|dadooh-force-overlay' || true", timeout=30)
        if listing:
            return listing
    if not command_available("dumpimage"):
        return ""
    # Best-effort category extraction through a temporary file in /tmp. The
    # file contains initramfs bytes only and is removed immediately.
    return shell(
        "tmp=$(mktemp /tmp/dadooh-uinitrd-c12-3-7.XXXXXX); "
        "trap 'rm -f \"$tmp\"' EXIT; "
        "dumpimage -T ramdisk -p 0 -o \"$tmp\" /boot/uInitrd >/dev/null 2>&1 && "
        "lsinitramfs \"$tmp\" 2>/dev/null | grep -E 'overlayroot|overlay\\.ko|c12-overlayroot-initramfs-marker|etc/initramfs-tools/modules|dadooh-force-overlay' || true",
        timeout=40,
    )


def module_snapshot():
    modules_text = read_text("/etc/initramfs-tools/modules")
    module_path = shell("modinfo -n overlay 2>/dev/null || true")
    modprobe_dry_run = run(["modprobe", "-n", "-v", "overlay"], timeout=15)
    proc_filesystems = read_text("/proc/filesystems")
    lsmod = shell("lsmod 2>/dev/null | awk '$1 == \"overlay\" {print $1}' | head -1 || true")
    initrd = latest_initrd_path()
    initrd_listing = initramfs_listing(initrd)
    uinitrd_listing_text = uinitrd_listing()
    return {
        "overlay_module_path_exists": bool(module_path),
        "overlay_module_path_category": "kernel_module" if module_path.endswith(".ko") or module_path.endswith(".ko.xz") or module_path.endswith(".ko.zst") else ("builtin_or_unknown" if module_path else "missing"),
        "modprobe_overlay_dry_run_ok": modprobe_dry_run.returncode == 0,
        "runtime_proc_filesystems_contains_overlay": bool(re.search(r"(^|\\n)nodev\\s+overlay(\\n|$)", proc_filesystems)),
        "runtime_lsmod_overlay_loaded": lsmod == "overlay",
        "initramfs_tools_modules_contains_overlay": any(line.strip() == "overlay" for line in modules_text.splitlines()),
        "force_overlay_hook_present": exists("/etc/initramfs-tools/scripts/init-top/dadooh-force-overlay"),
        "initrd_img_exists": bool(initrd),
        "initrd_img_size_bucket": file_size_bucket(initrd) if initrd else "missing",
        "uinitrd_exists": exists("/boot/uInitrd"),
        "uinitrd_size_bucket": file_size_bucket("/boot/uInitrd"),
        "initrd_contains_overlay_module": "overlay.ko" in initrd_listing,
        "initrd_contains_overlayroot_hook": "overlayroot" in initrd_listing,
        "initrd_contains_force_overlay_hook": "dadooh-force-overlay" in initrd_listing,
        "uinitrd_contains_overlay_module": "overlay.ko" in uinitrd_listing_text,
        "uinitrd_contains_overlayroot_hook": "overlayroot" in uinitrd_listing_text,
        "uinitrd_contains_force_overlay_hook": "dadooh-force-overlay" in uinitrd_listing_text,
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
        "cmdline_overlayroot_present": "overlayroot" in cmdline,
        "cmdline_root_present": bool(re.search(r"(^|\\s)root=", cmdline)),
        "cmdline_console_category": "serial" if "console=ttyS" in cmdline else ("tty" if "console=tty" in cmdline else "none"),
        "armbian_env_overlayroot_present": "overlayroot" in env,
        "extraargs_overlayroot_present": "overlayroot=" in extraargs,
        "bootargs_overlayroot_present": "overlayroot=" in bootargs,
        "boot_script_uses_uinitrd": "uInitrd" in boot_cmd,
        "update_initramfs_available": command_available("update-initramfs"),
        "mkimage_available": command_available("mkimage"),
        "dumpimage_available": command_available("dumpimage"),
        "post_update_uboot_present": exists("/etc/initramfs/post-update.d/99-uboot"),
    }


def kernel_log_categories():
    initramfs_log = ""
    try:
        initramfs_log = pathlib.Path("/run/initramfs/overlayroot.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    text = shell("journalctl -k -b --no-pager 2>/dev/null | grep -Ei 'overlayroot|cloud-initramfs|initramfs|overlay|driver' || true", timeout=25)
    lowered = (initramfs_log + "\n" + text).lower()
    reason = "none"
    if "unable to find driver/module" in lowered or "unable to find a driver" in lowered:
        reason = "overlay_driver_unavailable_in_initramfs"
    elif "loaded 'overlay' module but no 'overlay' in /proc/filesystems" in lowered:
        reason = "overlay_module_loaded_without_filesystem_registration"
    elif "overlayroot" in lowered and "disabled" in lowered:
        reason = "overlayroot_disabled"
    elif "overlayroot" in lowered and ("skip" in lowered or "skipping" in lowered):
        reason = "overlayroot_skipped"
    elif "overlayroot" in lowered or "cloud-initramfs" in lowered:
        reason = "overlayroot_seen"
    elif lowered:
        reason = "other"
    return {
        "overlayroot_log_seen": "overlayroot" in lowered,
        "cloud_initramfs_log_seen": "cloud-initramfs" in lowered,
        "initramfs_error_category": reason,
        "initramfs_overlay_log_file_present": bool(initramfs_log),
        "initramfs_log_driver_lookup_failed": "unable to find driver/module" in lowered or "unable to find a driver" in lowered,
        "initramfs_loaded_overlay_but_no_proc_filesystems": "loaded 'overlay' module but no 'overlay' in /proc/filesystems" in lowered,
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
    player = load("/tmp/kiosky-status.json")
    return {
        "public_state": public.get("public_state") or public.get("state") or launcher.get("state", "unknown"),
        "playback": public.get("playback") or public.get("playback_state") or player.get("playback") or player.get("playback_state") or "unknown",
    }


def service(name):
    return {
        "active": shell(f"systemctl is-active {name} 2>/dev/null || true") or "unknown",
        "enabled": shell(f"systemctl is-enabled {name} 2>/dev/null || true") or "unknown",
        "result": shell(f"systemctl show {name} -p Result --value 2>/dev/null || true") or "unknown",
        "n_restarts": shell(f"systemctl show {name} -p NRestarts --value 2>/dev/null || echo 0") or "0",
    }


def failed_count():
    text = shell("systemctl --failed --no-legend --plain 2>/dev/null || true")
    lines = [line for line in text.splitlines() if line.strip()]
    categories = []
    for line in lines:
        lowered = line.lower()
        if "console" in lowered or "keyboard" in lowered:
            categories.append("console_setup")
        elif "dadooh" in lowered or "totem" in lowered or "kiosky" in lowered:
            categories.append("dadooh_product")
        else:
            categories.append("other")
    return len(lines), sorted(set(categories))


root = mount_info("/")
failed, failed_categories = failed_count()
payload = {
    "schema_version": "dadooh-c12.3.7-overlay-module-initramfs-lab-inspect.v1",
    "running_board_inspected": True,
    "host_published": False,
    "secrets_published": False,
    "raw_logs_published": False,
    "writer_called": False,
    "real_config_read": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
    "reboot_executed": False,
    "poweroff_executed": False,
    "kernel_version": shell("uname -r"),
    "overlayroot_package_installed": package_installed("overlayroot"),
    "overlayroot_chroot_present": command_available("overlayroot-chroot"),
    "hook_initramfs_present": exists("/usr/share/initramfs-tools/hooks/overlayroot"),
    "init_bottom_overlayroot_present": exists("/usr/share/initramfs-tools/scripts/init-bottom/overlayroot"),
    "overlayroot_conf": overlay_conf("/etc/overlayroot.conf"),
    "overlayroot_local_conf": overlay_conf("/etc/overlayroot.local.conf"),
    "mount_root": root,
    "mount_data": mount_info("/data"),
    "mount_tmp": mount_info("/tmp"),
    "mount_run": mount_info("/run"),
    "overlay_mount_present": bool(shell("findmnt -t overlay --noheadings 2>/dev/null || true")),
    "read_only_enabled": root["fstype"] == "overlay" or root["options_category"] == "ro",
    "overlay_active": root["fstype"] == "overlay" or root["source_category"] == "overlay",
    "root_write_blocked_inferred": root["fstype"] == "overlay" or root["options_category"] == "ro",
    "root_write_probe_executed": False,
    "data_writable": writable_probe("/data"),
    "tmp_writable": writable_probe("/tmp"),
    "run_writable": writable_probe("/run"),
    "services": {unit: service(unit) for unit in ("kiosky-player.service", "totem-settings-trigger.service", "dadooh-visual-splash.service")},
    "systemctl_failed_count": failed,
    "systemctl_failed_categories": failed_categories,
    "status": status_snapshot(),
    "rollback_state_present": exists("/data/state/totem-overlayroot-lab/state.json"),
}
payload.update(module_snapshot())
payload.update(boot_snapshot())
payload.update(kernel_log_categories())
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/inspect.json"
  cat "$OUT_DIR/inspect.json"
}

plan_hypotheses() {
  remote_inspect >/dev/null
  python3 - "$OUT_DIR/inspect.json" > "$OUT_DIR/plan.json" <<'PY'
import json
import sys
from pathlib import Path

inspect = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
h1_needed = not inspect.get("initramfs_tools_modules_contains_overlay", False)
h2_needed = not inspect.get("force_overlay_hook_present", False)
payload = {
    "schema_version": "dadooh-c12.3.7-overlay-module-initramfs-lab-plan.v1",
    "plan_changes_applied": False,
    "max_cycles": 2,
    "recommended_order": ["H1_FORCE_MODULE", "H2_FORCE_LOAD_HOOK"],
    "first_recommended_hypothesis": "H1_FORCE_MODULE" if h1_needed else "H2_FORCE_LOAD_HOOK",
    "h1_force_module_needed": h1_needed,
    "h2_force_load_hook_needed": h2_needed,
    "hypotheses": {
        "H1_FORCE_MODULE": "add overlay to /etc/initramfs-tools/modules, update initramfs, regenerate uInitrd, reboot",
        "H2_FORCE_LOAD_HOOK": "add initramfs init-top hook that modprobes overlay before overlayroot, update initramfs, regenerate uInitrd, reboot",
    },
    "next_required_apply_confirmation": "CONFIRMO APLICAR OVERLAY MODULE INITRAMFS C12.3.7",
    "next_required_reboot_confirmation": "CONFIRMO REBOOT OVERLAY MODULE C12.3.7",
    "secrets_published": False,
    "raw_logs_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/plan.json"
  cat "$OUT_DIR/plan.json"
}

require_apply_confirmation() {
  if [ "$CONFIRM_APPLY" != "$EXPECTED_APPLY_CONFIRM" ]; then
    echo "error: apply requires confirmation: $EXPECTED_APPLY_CONFIRM" >&2
    exit 2
  fi
}

remote_apply() {
  local hypothesis="$1"
  require_apply_confirmation
  ssh_board "C12_3_7_HYPOTHESIS='$hypothesis' python3 -" > "$OUT_DIR/apply-$hypothesis.json" <<'PY'
import json
import os
import pathlib
import shutil
import subprocess
import time

HYPOTHESIS = os.environ["C12_3_7_HYPOTHESIS"]
STATE = pathlib.Path("/data/state/totem-overlayroot-lab")
BACKUPS = STATE / "backups"
TS = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
BACKUP_DIR = BACKUPS / f"{TS}-C12-3-7-{HYPOTHESIS}"
HOOK = pathlib.Path("/etc/initramfs-tools/scripts/init-top/dadooh-force-overlay")
MODULES = pathlib.Path("/etc/initramfs-tools/modules")


def run(cmd, timeout=180):
    try:
        return subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except Exception as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def shell(command, timeout=30):
    return (run(["sh", "-lc", command], timeout=timeout).stdout or "").strip()


def backup_file(path):
    src = pathlib.Path(path)
    if not src.exists() and not src.is_symlink():
        return False
    target = BACKUP_DIR / src.relative_to("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    if src.is_symlink():
        target.write_text(f"SYMLINK->{os.readlink(src)}\n", encoding="utf-8")
        target.with_suffix(target.suffix + ".symlink").write_text(os.readlink(src), encoding="utf-8")
        real = src.resolve()
        if real.exists():
            real_target = BACKUP_DIR / real.relative_to("/")
            real_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(real, real_target)
    elif src.is_file():
        shutil.copy2(src, target)
    return True


def backup_all():
    STATE.mkdir(parents=True, exist_ok=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o700)
    kernel = shell("uname -r")
    backed = {}
    for path in (
        "/etc/initramfs-tools/modules",
        "/etc/initramfs-tools/scripts/init-top/dadooh-force-overlay",
        "/boot/uInitrd",
        f"/boot/uInitrd-{kernel}",
        f"/boot/initrd.img-{kernel}",
    ):
        backed[path] = backup_file(path)
    return backed


def current_cycles():
    try:
        data = json.loads((STATE / "c12-3-7-state.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    cycles = data.get("cycles", [])
    return cycles if isinstance(cycles, list) else []


def save_state(cycles, applied):
    payload = {
        "schema_version": "dadooh-c12.3.7-overlay-module-initramfs-lab-state.v1",
        "updated_at": TS,
        "cycles": cycles,
        "last_hypothesis": HYPOTHESIS,
        "last_backup_dir": str(BACKUP_DIR),
        "rollback_available": True,
        "applied": applied,
        "secrets_published": False,
    }
    (STATE / "c12-3-7-state.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(STATE / "c12-3-7-state.json", 0o600)


def ensure_uinitrd(kernel):
    uinitrd = pathlib.Path("/boot/uInitrd")
    initrd = pathlib.Path(f"/boot/initrd.img-{kernel}")
    manual_mkimage = False
    if uinitrd.exists() and uinitrd.stat().st_size > 0:
        return {"manual_mkimage_fallback_executed": False, "uinitrd_nonempty_after": True}
    if initrd.exists() and shutil.which("mkimage"):
        arch = "arm64" if shell("dpkg --print-architecture") == "arm64" else "arm"
        target = pathlib.Path(f"/boot/uInitrd-{kernel}")
        mk = run(["mkimage", "-A", arch, "-O", "linux", "-T", "ramdisk", "-C", "gzip", "-n", "uInitrd", "-d", str(initrd), str(target)], timeout=120)
        if mk.returncode == 0 and target.exists() and target.stat().st_size > 0:
            if uinitrd.exists() or uinitrd.is_symlink():
                uinitrd.unlink()
            uinitrd.symlink_to(target.name)
            manual_mkimage = True
    return {"manual_mkimage_fallback_executed": manual_mkimage, "uinitrd_nonempty_after": uinitrd.exists() and uinitrd.stat().st_size > 0}


def update_initramfs():
    kernel = shell("uname -r")
    result = run(["update-initramfs", "-u", "-k", kernel], timeout=300)
    payload = {
        "update_initramfs_executed": True,
        "update_initramfs_returncode": result.returncode,
        "update_initramfs_ok": result.returncode == 0,
    }
    payload.update(ensure_uinitrd(kernel))
    return payload


def list_contains(path, needle):
    if not path.exists():
        return False
    return any(line.strip() == needle for line in path.read_text(encoding="utf-8", errors="replace").splitlines())


def apply_force_module():
    MODULES.parent.mkdir(parents=True, exist_ok=True)
    lines = MODULES.read_text(encoding="utf-8", errors="replace").splitlines() if MODULES.exists() else []
    already = any(line.strip() == "overlay" for line in lines)
    if not already:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# Dadooh C12.3.7: required by overlayroot runtime lab")
        lines.append("overlay")
        MODULES.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.chmod(MODULES, 0o644)
    payload = {"h1_force_module_applied": not already, "initramfs_tools_modules_contains_overlay": list_contains(MODULES, "overlay")}
    payload.update(update_initramfs())
    return payload


def apply_force_load_hook():
    HOOK.parent.mkdir(parents=True, exist_ok=True)
    HOOK.write_text("""#!/bin/sh
PREREQ=""
prereqs() { echo "$PREREQ"; }
case "$1" in
  prereqs) prereqs; exit 0 ;;
esac

mkdir -p /run/initramfs
if modprobe overlay >/dev/null 2>&1; then
  echo "overlay_modprobe=ok" > /run/initramfs/dadooh-overlay-module.status
else
  echo "overlay_modprobe=failed" > /run/initramfs/dadooh-overlay-module.status
fi
exit 0
""", encoding="utf-8")
    os.chmod(HOOK, 0o755)
    payload = {"h2_force_load_hook_applied": True, "force_overlay_hook_present": HOOK.exists()}
    payload.update(update_initramfs())
    return payload


cycles = current_cycles()
if len(cycles) >= 2:
    raise SystemExit("maximum C12.3.7 hypothesis cycles already reached")
backed = backup_all()
if HYPOTHESIS == "H1_FORCE_MODULE":
    applied = apply_force_module()
elif HYPOTHESIS == "H2_FORCE_LOAD_HOOK":
    applied = apply_force_load_hook()
else:
    raise SystemExit(f"unsupported hypothesis: {HYPOTHESIS}")
cycles.append({"hypothesis": HYPOTHESIS, "backup_dir": str(BACKUP_DIR), "applied_at": TS})
save_state(cycles, applied)
payload = {
    "schema_version": "dadooh-c12.3.7-overlay-module-initramfs-lab-apply.v1",
    "hypothesis": HYPOTHESIS,
    "backup_dir": str(BACKUP_DIR),
    "backups_created": backed,
    "rollback_available": True,
    "cycles_after_apply": len(cycles),
    "read_only_enabled_before_reboot": False,
    "reboot_required": True,
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
    "poweroff_executed": False,
}
payload.update(applied)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/apply-$hypothesis.json"
  cat "$OUT_DIR/apply-$hypothesis.json"
}

require_reboot_confirmation() {
  if [ "$CONFIRM_REBOOT" != "$EXPECTED_REBOOT_CONFIRM" ]; then
    echo "error: --reboot-check requires confirmation: $EXPECTED_REBOOT_CONFIRM" >&2
    exit 2
  fi
}

reboot_check() {
  require_reboot_confirmation
  ssh_board "sync; systemctl reboot" >/dev/null || true
  local attempt
  for attempt in $(seq 1 60); do
    if ssh_board "true" >/dev/null 2>&1; then
      break
    fi
    sleep 5
  done
  if ! ssh_board "true" >/dev/null 2>&1; then
    {
      printf 'reboot_executed=true\n'
      printf 'ssh_returned=false\n'
      printf 'offline_recovery_required=true\n'
      printf 'raw_logs_published=false\n'
    } > "$OUT_DIR/reboot.env"
    cat "$OUT_DIR/reboot.env"
    exit 1
  fi
  {
    printf 'reboot_executed=true\n'
    printf 'ssh_returned=true\n'
    printf 'offline_recovery_required=false\n'
  } > "$OUT_DIR/reboot.env"
  remote_inspect >/dev/null
  python3 - "$OUT_DIR/inspect.json" "$OUT_DIR/reboot.env" > "$OUT_DIR/reboot-result.json" <<'PY'
import json
import sys
from pathlib import Path

inspect = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
payload = {
    "schema_version": "dadooh-c12.3.7-overlay-module-initramfs-lab-reboot.v1",
    "reboot_executed": True,
    "ssh_returned": True,
    "read_only_enabled": inspect.get("read_only_enabled"),
    "overlay_active": inspect.get("overlay_active"),
    "root_write_blocked": inspect.get("root_write_blocked_inferred"),
    "data_writable": inspect.get("data_writable"),
    "tmp_writable": inspect.get("tmp_writable"),
    "run_writable": inspect.get("run_writable"),
    "writable_paths_ok": bool(inspect.get("data_writable") and inspect.get("tmp_writable") and inspect.get("run_writable")),
    "public_state": inspect.get("status", {}).get("public_state"),
    "playback": inspect.get("status", {}).get("playback"),
    "systemctl_failed_count": inspect.get("systemctl_failed_count"),
    "initramfs_error_category": inspect.get("initramfs_error_category"),
    "overlay_module_in_initramfs": inspect.get("initrd_contains_overlay_module"),
    "overlay_module_in_uinitrd": inspect.get("uinitrd_contains_overlay_module"),
    "force_overlay_hook_in_initramfs": inspect.get("initrd_contains_force_overlay_hook"),
    "winning_hypothesis_detected": inspect.get("read_only_enabled") and inspect.get("overlay_active") and inspect.get("root_write_blocked_inferred"),
    "raw_logs_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  cat "$OUT_DIR/reboot-result.json"
}

rollback() {
  ssh_board "python3 -" > "$OUT_DIR/rollback.json" <<'PY'
import json
import os
import pathlib
import shutil
import subprocess

STATE = pathlib.Path("/data/state/totem-overlayroot-lab")
STATE_FILE = STATE / "c12-3-7-state.json"
HOOK = pathlib.Path("/etc/initramfs-tools/scripts/init-top/dadooh-force-overlay")


def run(cmd, timeout=240):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)
    except Exception as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def restore_file(backup_dir, path):
    src = pathlib.Path(path)
    backup = backup_dir / src.relative_to("/")
    symlink_info = backup.with_suffix(backup.suffix + ".symlink")
    if symlink_info.exists():
        target = symlink_info.read_text(encoding="utf-8").strip()
        if src.exists() or src.is_symlink():
            src.unlink()
        src.symlink_to(target)
        real_backup = backup_dir / pathlib.Path(os.path.realpath(path)).relative_to("/")
        if real_backup.exists() and pathlib.Path(os.path.realpath(path)).exists():
            shutil.copy2(real_backup, pathlib.Path(os.path.realpath(path)))
        return True
    if backup.exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, src)
        return True
    if path == str(HOOK) and HOOK.exists():
        HOOK.unlink()
        return True
    return False


try:
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit("rollback state not found")
cycles = state.get("cycles", [])
if not cycles:
    raise SystemExit("rollback cycles not found")
backup_dir = pathlib.Path(cycles[-1]["backup_dir"])
kernel = run(["uname", "-r"]).stdout.strip()
restored = {}
for path in (
    "/etc/initramfs-tools/modules",
    "/etc/initramfs-tools/scripts/init-top/dadooh-force-overlay",
    "/boot/uInitrd",
    f"/boot/uInitrd-{kernel}",
    f"/boot/initrd.img-{kernel}",
):
    restored[path] = restore_file(backup_dir, path)
result = run(["update-initramfs", "-u", "-k", kernel])
payload = {
    "schema_version": "dadooh-c12.3.7-overlay-module-initramfs-lab-rollback.v1",
    "rollback_executed": True,
    "backup_dir": str(backup_dir),
    "restored": restored,
    "update_initramfs_executed": True,
    "update_initramfs_returncode": result.returncode,
    "reboot_required": True,
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/rollback.json"
  cat "$OUT_DIR/rollback.json"
}

summary() {
  {
    printf 'c12_3_7_summary_generated=true\n'
    printf 'host_category=lab_board\n'
    printf 'writer_called=false\n'
    printf 'real_config_written=false\n'
    printf 'wifi_changed=false\n'
    printf 'packages_installed=false\n'
    printf 'poweroff_executed=false\n'
    printf 'raw_logs_published=false\n'
  } > "$OUT_DIR/summary.env"
  cat "$OUT_DIR/summary.env"
}

case "$MODE" in
  prepare-only) prepare_only ;;
  inspect) remote_inspect ;;
  plan) plan_hypotheses ;;
  apply-force-module) remote_apply "H1_FORCE_MODULE" ;;
  apply-force-load-hook) remote_apply "H2_FORCE_LOAD_HOOK" ;;
  reboot-check) reboot_check ;;
  rollback) rollback ;;
  summary) summary ;;
esac
