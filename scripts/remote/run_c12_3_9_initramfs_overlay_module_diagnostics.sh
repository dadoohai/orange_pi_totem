#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
TIMESTAMP="${C12_3_9_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${C12_3_9_RUN_ROOT:-/tmp/dadooh-c12-3-9-initramfs-overlay-module-diagnostics}"
OUT_DIR="${C12_3_9_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-3-9-initramfs-overlay-module-diagnostics}"
KNOWN_HOSTS="${C12_3_9_KNOWN_HOSTS:-/tmp/dadooh-c12-3-9-known-hosts}"
CONFIRM_INSTALL="${C12_3_9_CONFIRM_INSTALL:-}"
CONFIRM_REBOOT="${C12_3_9_CONFIRM_REBOOT:-}"
EXPECTED_INSTALL_CONFIRM="CONFIRMO INSTALAR DIAGNOSTICO INITRAMFS C12.3.9"
EXPECTED_REBOOT_CONFIRM="CONFIRMO REBOOT DIAGNOSTICO INITRAMFS C12.3.9"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_3_9_initramfs_overlay_module_diagnostics.sh [root@host] [mode]

Modes:
  --prepare-only
  --inspect
  --install-diagnostic-hook
  --reboot-check
  --collect-diagnostic
  --rollback
  --summary

Environment:
  C12_3_9_CONFIRM_INSTALL="CONFIRMO INSTALAR DIAGNOSTICO INITRAMFS C12.3.9"
      Required for --install-diagnostic-hook.
  C12_3_9_CONFIRM_REBOOT="CONFIRMO REBOOT DIAGNOSTICO INITRAMFS C12.3.9"
      Required for --reboot-check.

Rules:
  - diagnostics only on the disposable C12 image-lab board;
  - inspect and collect are read-only;
  - no dev board, old test board, writer, real config, Wi-Fi changes, packages,
    apt upgrade, poweroff, power cut, secrets or raw logs;
  - at most two diagnostic hook cycles in this runner.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --install-diagnostic-hook) MODE="install-diagnostic-hook" ;;
    --reboot-check) MODE="reboot-check" ;;
    --collect-diagnostic) MODE="collect-diagnostic" ;;
    --rollback) MODE="rollback" ;;
    --summary) MODE="summary" ;;
    --help|-h) usage; exit 0 ;;
    --*) echo "error: unsupported mode $1" >&2; usage; exit 2 ;;
    *) HOST="$1" ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|inspect|install-diagnostic-hook|reboot-check|collect-diagnostic|rollback|summary) ;;
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

require_install_confirmation() {
  if [ "$CONFIRM_INSTALL" != "$EXPECTED_INSTALL_CONFIRM" ]; then
    echo "error: --install-diagnostic-hook requires confirmation:" >&2
    echo "$EXPECTED_INSTALL_CONFIRM" >&2
    exit 3
  fi
}

require_reboot_confirmation() {
  if [ "$CONFIRM_REBOOT" != "$EXPECTED_REBOOT_CONFIRM" ]; then
    echo "error: --reboot-check requires confirmation:" >&2
    echo "$EXPECTED_REBOOT_CONFIRM" >&2
    exit 3
  fi
}

prepare_only() {
  git -C "$REPO_ROOT" diff --check
  bash -n "$0"
  bash -n "$REPO_ROOT/scripts/remote/run_c12_3_8_readonly_mechanism_decision.sh"
  bash -n "$REPO_ROOT/scripts/remote/run_c12_3_7_overlay_module_initramfs_lab.sh"
  bash -n "$REPO_ROOT/scripts/build/run_c12_1_build_image_lab_readonly.sh"
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  {
    printf 'c12_3_9_prepare_only=ok\n'
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


def initramfs_listing(path):
    if not path or not command_available("lsinitramfs"):
        return ""
    return shell(
        f"lsinitramfs {path} 2>/dev/null | "
        "grep -E 'overlayroot|overlay\\.ko|modules\\.dep|modules\\.alias|bin/modprobe|sbin/modprobe|usr/sbin/modprobe|usr/bin/kmod|busybox|dadooh-overlay-diagnostic|dadooh-force-overlay|c12-overlayroot-initramfs-marker' || true",
        timeout=30,
    )


def uinitrd_listing():
    if not exists("/boot/uInitrd"):
        return ""
    listing = initramfs_listing("/boot/uInitrd")
    if listing:
        return listing
    if not command_available("dumpimage"):
        return ""
    return shell(
        "tmp=$(mktemp /tmp/dadooh-uinitrd-c12-3-9.XXXXXX); "
        "trap 'rm -f \"$tmp\"' EXIT; "
        "dumpimage -T ramdisk -p 0 -o \"$tmp\" /boot/uInitrd >/dev/null 2>&1 && "
        "lsinitramfs \"$tmp\" 2>/dev/null | "
        "grep -E 'overlayroot|overlay\\.ko|modules\\.dep|modules\\.alias|bin/modprobe|sbin/modprobe|usr/sbin/modprobe|usr/bin/kmod|busybox|dadooh-overlay-diagnostic|dadooh-force-overlay|c12-overlayroot-initramfs-marker' || true",
        timeout=45,
    )


def module_snapshot():
    kernel = shell("uname -r")
    initrd_path = f"/boot/initrd.img-{kernel}"
    initrd_listing = initramfs_listing(initrd_path)
    u_listing = uinitrd_listing()
    module_path = shell("modinfo -n overlay 2>/dev/null || true")
    modprobe = run(["modprobe", "-n", "-v", "overlay"], timeout=15)
    proc_filesystems = read_text("/proc/filesystems")
    lsmod = shell("lsmod 2>/dev/null | awk '$1 == \"overlay\" {print $1}' | head -1 || true")
    overlay_ko_present = "overlay.ko" in initrd_listing or "overlay.ko" in u_listing
    return {
        "overlay_ko_present_in_initramfs": overlay_ko_present,
        "overlay_ko_path_category": "kernel_module" if module_path.endswith((".ko", ".ko.xz", ".ko.zst")) else ("builtin_or_unknown" if module_path else "missing"),
        "modules_dep_present_in_initramfs": "modules.dep" in initrd_listing or "modules.dep" in u_listing,
        "modules_alias_present_in_initramfs": "modules.alias" in initrd_listing or "modules.alias" in u_listing,
        "modprobe_present_in_initramfs": "modprobe" in initrd_listing or "modprobe" in u_listing or "kmod" in initrd_listing or "kmod" in u_listing,
        "insmod_present_runtime": command_available("insmod"),
        "busybox_present_in_initramfs": "busybox" in initrd_listing or "busybox" in u_listing,
        "diagnostic_hook_present_in_initramfs": "dadooh-overlay-diagnostic" in initrd_listing or "dadooh-overlay-diagnostic" in u_listing,
        "force_overlay_hook_present_in_initramfs": "dadooh-force-overlay" in initrd_listing or "dadooh-force-overlay" in u_listing,
        "modprobe_overlay_post_boot_ok": modprobe.returncode == 0,
        "proc_filesystems_post_boot_contains_overlay": bool(re.search(r"(^|\\n)nodev\\s+overlay(\\n|$)", proc_filesystems)),
        "lsmod_post_boot_shows_overlay": lsmod == "overlay",
    }


def boot_snapshot():
    cmdline = read_text("/proc/cmdline")
    env = read_text("/boot/armbianEnv.txt")
    boot_cmd = read_text("/boot/boot.cmd")
    if not boot_cmd and exists("/boot/boot.scr"):
        boot_cmd = shell("strings /boot/boot.scr 2>/dev/null | grep -E 'uInitrd|initrd|bootargs|extraargs' || true")
    return {
        "kernel_version": shell("uname -r"),
        "cmdline_overlayroot_tmpfs_present": "overlayroot=tmpfs" in cmdline,
        "cmdline_root_present": bool(re.search(r"(^|\\s)root=", cmdline)),
        "cmdline_console_category": "serial" if "console=ttyS" in cmdline else ("tty" if "console=tty" in cmdline else "none"),
        "armbian_env_overlayroot_present": "overlayroot" in env,
        "boot_script_uses_uinitrd": "uInitrd" in boot_cmd,
        "uinitrd_valid": exists("/boot/uInitrd") and file_size_bucket("/boot/uInitrd") == "nonempty",
    }


root = mount_info("/")
payload = {
    "schema_version": "dadooh-c12.3.9-initramfs-overlay-diagnostics-inspect.v1",
    "board_category": "lab_board",
    "inspect_read_only": True,
    "boot": boot_snapshot(),
    "overlayroot_conf": overlay_conf("/etc/overlayroot.conf"),
    "root_fstype": root["fstype"],
    "root_options_category": root["options_category"],
    "read_only_enabled": root["source_category"] == "overlay" or root["options_category"] == "ro",
    "overlay_active": root["source_category"] == "overlay" or root["fstype"] == "overlay",
    "root_write_blocked": root["source_category"] == "overlay" or root["options_category"] == "ro",
    "mount_data": mount_info("/data"),
    "mount_tmp": mount_info("/tmp"),
    "mount_run": mount_info("/run"),
    "initrd_img_size_bucket": file_size_bucket(f"/boot/initrd.img-{shell('uname -r')}"),
    "uinitrd_size_bucket": file_size_bucket("/boot/uInitrd"),
    "module": module_snapshot(),
    "systemctl_failed_count": shell("systemctl --failed --no-legend 2>/dev/null | wc -l | tr -d ' '") or "unknown",
    "diagnostic_state_present": exists("/data/state/totem-overlayroot-diagnostics/state.json"),
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
    "poweroff_executed": False,
    "raw_logs_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/inspect.json"
}

install_diagnostic_hook() {
  require_install_confirmation
  ssh_board "python3 -" > "$OUT_DIR/install-diagnostic-hook.json" <<'PY'
import json
import os
import pathlib
import shutil
import subprocess
import time

STATE = pathlib.Path("/data/state/totem-overlayroot-diagnostics")
BACKUPS = STATE / "backups"
TS = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
BACKUP_DIR = BACKUPS / f"{TS}-C12-3-9-diagnostic-hook"
HOOK = pathlib.Path("/etc/initramfs-tools/scripts/init-top/dadooh-overlay-diagnostic")


def run(cmd, timeout=180):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)
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
        "/etc/initramfs-tools/scripts/init-top/dadooh-overlay-diagnostic",
        "/boot/uInitrd",
        f"/boot/uInitrd-{kernel}",
        f"/boot/initrd.img-{kernel}",
    ):
        backed[path] = backup_file(path)
    return backed


def current_cycles():
    try:
        data = json.loads((STATE / "state.json").read_text(encoding="utf-8"))
        cycles = data.get("cycles", [])
        return cycles if isinstance(cycles, list) else []
    except Exception:
        return []


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


def write_hook():
    HOOK.parent.mkdir(parents=True, exist_ok=True)
    HOOK.write_text("""#!/bin/sh
PREREQ=""
prereqs() { echo "$PREREQ"; }
case "$1" in
  prereqs) prereqs; exit 0 ;;
esac

OUT="/run/initramfs/dadooh-overlay-diagnostic.json"
mkdir -p /run/initramfs

bool_file_readable() { [ -r "$1" ] && echo true || echo false; }
bucket_rc() {
  case "$1" in
    missing) echo missing ;;
    0) echo zero ;;
    *) echo nonzero ;;
  esac
}
contains_overlay() {
  if [ -r /proc/filesystems ] && grep -qw overlay /proc/filesystems 2>/dev/null; then
    echo true
  else
    echo false
  fi
}

KERNEL="$(uname -r 2>/dev/null || echo unknown)"
PROC_MOUNTED="$(bool_file_readable /proc/filesystems)"
OVERLAY_BEFORE="$(contains_overlay)"
MODPROBE_PRESENT=false
INSMOD_PRESENT=false
MODINFO_PRESENT=false
command -v modprobe >/dev/null 2>&1 && MODPROBE_PRESENT=true
command -v insmod >/dev/null 2>&1 && INSMOD_PRESENT=true
command -v modinfo >/dev/null 2>&1 && MODINFO_PRESENT=true
OVERLAY_KO="$(find "/lib/modules/$KERNEL" -type f \\( -name 'overlay.ko' -o -name 'overlay.ko.*' \\) 2>/dev/null | head -n 1)"
OVERLAY_KO_EXISTS=false
[ -n "$OVERLAY_KO" ] && OVERLAY_KO_EXISTS=true
MODULES_DEP_EXISTS="$(bool_file_readable "/lib/modules/$KERNEL/modules.dep")"
MODULE_PATH_MATCH=false
case "$OVERLAY_KO" in
  *"/$KERNEL/"*) MODULE_PATH_MATCH=true ;;
esac
VERMAGIC_MATCH=unknown
if [ "$MODINFO_PRESENT" = true ] && [ "$OVERLAY_KO_EXISTS" = true ]; then
  VM="$(modinfo -F vermagic "$OVERLAY_KO" 2>/dev/null | awk '{print $1}' | head -n 1)"
  if [ "$VM" = "$KERNEL" ]; then
    VERMAGIC_MATCH=true
  else
    VERMAGIC_MATCH=false
  fi
fi

MODPROBE_RC=missing
if [ "$MODPROBE_PRESENT" = true ]; then
  modprobe overlay >/dev/null 2>&1
  MODPROBE_RC=$?
fi
OVERLAY_AFTER_MODPROBE="$(contains_overlay)"

INSMOD_ATTEMPTED=false
INSMOD_RC=missing
if [ "$OVERLAY_AFTER_MODPROBE" != true ] && [ "$INSMOD_PRESENT" = true ] && [ "$OVERLAY_KO_EXISTS" = true ]; then
  INSMOD_ATTEMPTED=true
  insmod "$OVERLAY_KO" >/dev/null 2>&1
  INSMOD_RC=$?
fi
OVERLAY_AFTER_INSMOD="$(contains_overlay)"

cat > "$OUT" <<EOF
{
  "schema_version": "dadooh-c12.3.9-initramfs-overlay-diagnostic.v1",
  "proc_mounted": $PROC_MOUNTED,
  "overlay_in_proc_before": $OVERLAY_BEFORE,
  "modprobe_present": $MODPROBE_PRESENT,
  "insmod_present": $INSMOD_PRESENT,
  "overlay_ko_exists": $OVERLAY_KO_EXISTS,
  "modules_dep_exists": $MODULES_DEP_EXISTS,
  "vermagic_match": "$VERMAGIC_MATCH",
  "uname_kernel_matches_module_path": $MODULE_PATH_MATCH,
  "modprobe_overlay_attempted": true,
  "modprobe_overlay_exit_code_bucket": "$(bucket_rc "$MODPROBE_RC")",
  "overlay_in_proc_after_modprobe": $OVERLAY_AFTER_MODPROBE,
  "insmod_overlay_attempted": $INSMOD_ATTEMPTED,
  "insmod_overlay_exit_code_bucket": "$(bucket_rc "$INSMOD_RC")",
  "overlay_in_proc_after_insmod": $OVERLAY_AFTER_INSMOD,
  "mount_overlay_test_attempted": false,
  "raw_logs_published": false
}
EOF
exit 0
""", encoding="utf-8")
    os.chmod(HOOK, 0o755)


cycles = current_cycles()
if len(cycles) >= 2:
    raise SystemExit("maximum C12.3.9 diagnostic cycles already reached")
backed = backup_all()
write_hook()
update = update_initramfs()
cycles.append({"cycle": len(cycles) + 1, "backup_dir": str(BACKUP_DIR), "installed_at": TS})
state = {
    "schema_version": "dadooh-c12.3.9-initramfs-overlay-diagnostics-state.v1",
    "updated_at": TS,
    "cycles": cycles,
    "last_backup_dir": str(BACKUP_DIR),
    "rollback_available": True,
    "hook_path": str(HOOK),
    "secrets_published": False,
}
(STATE / "state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(STATE / "state.json", 0o600)
payload = {
    "schema_version": "dadooh-c12.3.9-initramfs-overlay-diagnostics-install.v1",
    "diagnostic_hook_installed": HOOK.exists(),
    "backup_dir": str(BACKUP_DIR),
    "backups_created": backed,
    "rollback_available": True,
    "cycles_count": len(cycles),
    "hook_path_category": "initramfs_init_top",
}
payload.update(update)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/install-diagnostic-hook.json"
}

reboot_check() {
  require_reboot_confirmation
  ssh_board "sync; nohup sh -c 'sleep 2; systemctl reboot' >/dev/null 2>&1 &"
  sleep 8
  local attempts=0
  while [ "$attempts" -lt 60 ]; do
    if ssh_board "true" >/dev/null 2>&1; then
      break
    fi
    attempts=$((attempts + 1))
    sleep 3
  done
  if [ "$attempts" -ge 60 ]; then
    cat > "$OUT_DIR/reboot-check.json" <<'JSON'
{
  "schema_version": "dadooh-c12.3.9-initramfs-overlay-diagnostics-reboot.v1",
  "reboot_executed": true,
  "ssh_returned": false,
  "offline_recovery_required": true
}
JSON
    cat "$OUT_DIR/reboot-check.json"
    return 4
  fi
  collect_diagnostic
  python3 - "$OUT_DIR/diagnostic.json" > "$OUT_DIR/reboot-check.json" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
payload = {
    "schema_version": "dadooh-c12.3.9-initramfs-overlay-diagnostics-reboot.v1",
    "reboot_executed": True,
    "ssh_returned": True,
    "read_only_enabled": data.get("read_only_enabled"),
    "overlay_active": data.get("overlay_active"),
    "root_write_blocked": data.get("root_write_blocked"),
    "cause_category": data.get("cause_category"),
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/reboot-check.json"
  cat "$OUT_DIR/reboot-check.json"
}

collect_diagnostic() {
  ssh_board "python3 -" > "$OUT_DIR/diagnostic.json" <<'PY'
import json
import pathlib
import re
import subprocess


def run(cmd, timeout=15):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=timeout)
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, "", "")


def shell(command, timeout=15):
    return (run(["sh", "-lc", command], timeout=timeout).stdout or "").strip()


def exists(path):
    return pathlib.Path(path).exists()


def load_json(path):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def read_text(path):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


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
    }


def writable_probe(directory):
    if directory not in {"/data", "/tmp", "/run"}:
        return "not_executed"
    target = pathlib.Path("/data/state") if directory == "/data" else pathlib.Path(directory)
    try:
        target.mkdir(parents=True, exist_ok=True)
        path = target / ".dadooh-c12-3-9-writable-probe"
        path.write_text("ok\n", encoding="utf-8")
        path.unlink()
        return True
    except Exception:
        return False


def status_snapshot():
    public = load_json("/tmp/dadooh-status/status.json")
    launcher = load_json("/data/state/kiosky-player/launcher-status.json") or load_json("/tmp/kiosky-launcher-status.json")
    return {
        "public_state": public.get("public_state") or public.get("state") or launcher.get("state", "unknown"),
        "playback": public.get("playback") or public.get("playback_state") or "unknown",
    }


diag = load_json("/run/initramfs/dadooh-overlay-diagnostic.json")
root = mount_info("/")
read_only_enabled = root["source_category"] == "overlay" or root["options_category"] == "ro"
overlay_active = root["source_category"] == "overlay" or root["fstype"] == "overlay"
root_write_blocked = root["source_category"] == "overlay" or root["options_category"] == "ro"

if not diag:
    cause = "UNKNOWN"
elif diag.get("modprobe_overlay_exit_code_bucket") == "missing":
    cause = "OVERLAY_MODPROBE_NOT_ATTEMPTED"
elif diag.get("modprobe_overlay_exit_code_bucket") == "nonzero":
    cause = "OVERLAY_MODPROBE_FAILED"
elif diag.get("vermagic_match") is False:
    cause = "OVERLAY_MODULE_VERMAGIC_MISMATCH"
elif diag.get("uname_kernel_matches_module_path") is False:
    cause = "OVERLAY_MODULE_PATH_INVALID"
elif diag.get("proc_mounted") is False:
    cause = "OVERLAY_PROC_FILESYSTEMS_NOT_READY"
elif diag.get("overlay_in_proc_after_modprobe") is True:
    cause = "OVERLAYROOT_CHECKS_TOO_EARLY" if not overlay_active else "OVERLAY_MOUNT_FAILED_AFTER_LOAD"
elif diag.get("insmod_overlay_attempted") and diag.get("insmod_overlay_exit_code_bucket") == "nonzero":
    cause = "OVERLAY_INSMOD_FAILED"
elif diag.get("modprobe_overlay_exit_code_bucket") == "zero" and diag.get("overlay_in_proc_after_modprobe") is False:
    cause = "OVERLAY_REQUIRES_KERNEL_BUILTIN"
else:
    cause = "UNKNOWN"

payload = {
    "schema_version": "dadooh-c12.3.9-initramfs-overlay-diagnostics-result.v1",
    "diagnostic_collected": bool(diag),
    "diagnostic_hook_installed": exists("/etc/initramfs-tools/scripts/init-top/dadooh-overlay-diagnostic"),
    "diagnostic_file_present": exists("/run/initramfs/dadooh-overlay-diagnostic.json"),
    "proc_mounted": diag.get("proc_mounted", "unknown"),
    "overlay_in_proc_before": diag.get("overlay_in_proc_before", "unknown"),
    "modprobe_present": diag.get("modprobe_present", "unknown"),
    "insmod_present": diag.get("insmod_present", "unknown"),
    "modprobe_overlay_result": diag.get("modprobe_overlay_exit_code_bucket", "unknown"),
    "overlay_in_proc_after_modprobe": diag.get("overlay_in_proc_after_modprobe", "unknown"),
    "insmod_overlay_attempted": diag.get("insmod_overlay_attempted", "unknown"),
    "insmod_overlay_result": diag.get("insmod_overlay_exit_code_bucket", "unknown"),
    "overlay_in_proc_after_insmod": diag.get("overlay_in_proc_after_insmod", "unknown"),
    "overlay_ko_exists": diag.get("overlay_ko_exists", "unknown"),
    "modules_dep_exists": diag.get("modules_dep_exists", "unknown"),
    "vermagic_match": diag.get("vermagic_match", "unknown"),
    "module_path_match": diag.get("uname_kernel_matches_module_path", "unknown"),
    "mount_overlay_test_attempted": diag.get("mount_overlay_test_attempted", False),
    "read_only_enabled": read_only_enabled,
    "overlay_active": overlay_active,
    "root_write_blocked": root_write_blocked,
    "data_writable": writable_probe("/data"),
    "tmp_writable": writable_probe("/tmp"),
    "run_writable": writable_probe("/run"),
    "product": status_snapshot(),
    "systemctl_failed_count": shell("systemctl --failed --no-legend 2>/dev/null | wc -l | tr -d ' '") or "unknown",
    "cause_category": cause,
    "recommended_next_step": (
        "C12.1.9_REBUILD_WITH_INITRAMFS_MODULE_PATH_FIX"
        if cause in {"OVERLAYROOT_CHECKS_TOO_EARLY", "OVERLAY_MODULE_PATH_INVALID"}
        else "KERNEL_CONFIG_OR_ALTERNATIVE_READONLY_DECISION"
        if cause == "OVERLAY_REQUIRES_KERNEL_BUILTIN"
        else "C12.3.10_OR_KERNEL_MECHANISM_DECISION"
    ),
    "raw_logs_published": False,
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/diagnostic.json"
}

rollback() {
  ssh_board "python3 -" > "$OUT_DIR/rollback.json" <<'PY'
import json
import os
import pathlib
import shutil
import subprocess

STATE = pathlib.Path("/data/state/totem-overlayroot-diagnostics")
HOOK = pathlib.Path("/etc/initramfs-tools/scripts/init-top/dadooh-overlay-diagnostic")


def run(cmd, timeout=180):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)
    except Exception as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def shell(command, timeout=30):
    return (run(["sh", "-lc", command], timeout=timeout).stdout or "").strip()


def restore_file(src, dst):
    src = pathlib.Path(src)
    dst = pathlib.Path(dst)
    if src.exists() and src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True
    return False


def latest_backup():
    try:
        data = json.loads((STATE / "state.json").read_text(encoding="utf-8"))
        return pathlib.Path(data.get("last_backup_dir", ""))
    except Exception:
        return pathlib.Path("")


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


backup = latest_backup()
restored = {}
if backup.exists():
    kernel = shell("uname -r")
    for path in (
        "/etc/initramfs-tools/scripts/init-top/dadooh-overlay-diagnostic",
        "/boot/uInitrd",
        f"/boot/uInitrd-{kernel}",
        f"/boot/initrd.img-{kernel}",
    ):
        restored[path] = restore_file(backup / path.lstrip("/"), path)
else:
    restored = {}

if not restored.get("/etc/initramfs-tools/scripts/init-top/dadooh-overlay-diagnostic", False) and HOOK.exists():
    HOOK.unlink()

kernel = shell("uname -r")
result = run(["update-initramfs", "-u", "-k", kernel], timeout=300)
payload = {
    "schema_version": "dadooh-c12.3.9-initramfs-overlay-diagnostics-rollback.v1",
    "rollback_executed": True,
    "backup_dir": str(backup) if backup else "",
    "files_restored": restored,
    "diagnostic_hook_present_after": HOOK.exists(),
    "update_initramfs_executed": True,
    "update_initramfs_returncode": result.returncode,
    "update_initramfs_ok": result.returncode == 0,
}
payload.update(ensure_uinitrd(kernel))
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/rollback.json"
}

summary() {
  local diagnostic="$OUT_DIR/diagnostic.json"
  if [ ! -f "$diagnostic" ]; then
    if [ -f "$OUT_DIR/inspect.json" ]; then
      diagnostic="$OUT_DIR/inspect.json"
    else
      echo "summary_unavailable=true"
      return 0
    fi
  fi
  python3 - "$diagnostic" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
keys = [
    "diagnostic_collected",
    "proc_mounted",
    "overlay_in_proc_before",
    "modprobe_overlay_result",
    "overlay_in_proc_after_modprobe",
    "insmod_overlay_attempted",
    "insmod_overlay_result",
    "overlay_in_proc_after_insmod",
    "vermagic_match",
    "module_path_match",
    "read_only_enabled",
    "overlay_active",
    "root_write_blocked",
    "cause_category",
    "recommended_next_step",
]
for key in keys:
    print(f"{key}={data.get(key)}")
PY
}

case "$MODE" in
  prepare-only) prepare_only ;;
  inspect) remote_inspect; cat "$OUT_DIR/inspect.json" ;;
  install-diagnostic-hook) install_diagnostic_hook; cat "$OUT_DIR/install-diagnostic-hook.json" ;;
  reboot-check) reboot_check ;;
  collect-diagnostic) collect_diagnostic; cat "$OUT_DIR/diagnostic.json" ;;
  rollback) rollback; cat "$OUT_DIR/rollback.json" ;;
  summary) summary ;;
esac
