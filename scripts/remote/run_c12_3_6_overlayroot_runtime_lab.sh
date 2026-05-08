#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
TIMESTAMP="${C12_3_6_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${C12_3_6_RUN_ROOT:-/tmp/dadooh-c12-3-6-overlayroot-runtime-lab}"
OUT_DIR="${C12_3_6_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-3-6-overlayroot-runtime-lab}"
KNOWN_HOSTS="${C12_3_6_KNOWN_HOSTS:-/tmp/dadooh-c12-3-6-known-hosts}"
HYPOTHESIS="${C12_3_6_HYPOTHESIS:-}"
CONFIRM_APPLY="${C12_3_6_CONFIRM_APPLY:-}"
CONFIRM_REBOOT="${C12_3_6_CONFIRM_REBOOT:-}"
EXPECTED_APPLY_CONFIRM="CONFIRMO APLICAR HIPOTESE OVERLAYROOT C12.3.6"
EXPECTED_REBOOT_CONFIRM="CONFIRMO REBOOT OVERLAYROOT LAB C12.3.6"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_3_6_overlayroot_runtime_lab.sh [root@host] [mode]

Modes:
  --prepare-only
  --inspect
  --hypothesis-plan
  --apply-hypothesis
  --reboot-check
  --rollback
  --summary

Environment:
  C12_3_6_HYPOTHESIS=H1|H2|H3|H4
      Required for --apply-hypothesis.
  C12_3_6_CONFIRM_APPLY="CONFIRMO APLICAR HIPOTESE OVERLAYROOT C12.3.6"
      Required for --apply-hypothesis.
  C12_3_6_CONFIRM_REBOOT="CONFIRMO REBOOT OVERLAYROOT LAB C12.3.6"
      Required for --reboot-check.

Rules:
  - runtime lab only on the disposable C12.1.8 image-lab board;
  - no dev board, old test board, writer, real config, Wi-Fi changes, packages,
    apt upgrade, poweroff, power cut, secrets or raw logs;
  - inspect and plan are read-only;
  - apply changes one hypothesis at a time with backups and rollback state.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --hypothesis-plan) MODE="hypothesis-plan" ;;
    --apply-hypothesis) MODE="apply-hypothesis" ;;
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
  prepare-only|inspect|hypothesis-plan|apply-hypothesis|reboot-check|rollback|summary) ;;
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
  bash -n "$REPO_ROOT/scripts/remote/run_c12_3_5_boot_readonly_wizard_classification.sh"
  if [ -f "$REPO_ROOT/scripts/remote/run_c12_1_7_overlayroot_activation_diagnose.sh" ]; then
    bash -n "$REPO_ROOT/scripts/remote/run_c12_1_7_overlayroot_activation_diagnose.sh"
  fi
  bash -n "$REPO_ROOT/scripts/build/run_c12_1_build_image_lab_readonly.sh"
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  {
    printf 'c12_3_6_prepare_only=ok\n'
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
import os
import pathlib
import re
import shutil
import subprocess


def run(cmd, timeout=15):
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


def shell(command, timeout=15):
    return (run(["sh", "-lc", command], timeout=timeout).stdout or "").strip()


def command_available(name):
    return bool(shell(f"command -v {name} 2>/dev/null || true"))


def package_installed(name):
    return shell(f"dpkg-query -W -f='${{Status}}' {name} 2>/dev/null || true") == "install ok installed"


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
    return {
        "present": bool(parts),
        "source_category": "overlay" if source == "overlay" else ("device" if source.startswith("/dev/") else source if source in {"tmpfs", "proc", "sysfs"} else "other"),
        "fstype": parts[1] if len(parts) > 1 else "unknown",
        "options_category": "ro" if "ro" in {item.strip() for item in options.split(",")} else "rw_or_unknown",
        "overlay_upperdir_present": "upperdir=" in options,
        "overlay_workdir_present": "workdir=" in options,
    }


def writable_probe(directory):
    if directory not in {"/data", "/tmp", "/run"}:
        return "not_executed"
    target = pathlib.Path("/data/state") if directory == "/data" else pathlib.Path(directory)
    try:
        target.mkdir(parents=True, exist_ok=True)
        path = target / ".dadooh-c12-3-6-writable-probe"
        path.write_text("ok\n", encoding="utf-8")
        path.unlink()
        return True
    except Exception:
        return False


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
    return shell(f"lsinitramfs {path} 2>/dev/null | grep -E 'overlayroot|overlay\\.ko|c12-overlayroot-initramfs-marker' || true", timeout=30)


def boot_snapshot():
    cmdline = read_text("/proc/cmdline")
    env = read_text("/boot/armbianEnv.txt")
    boot_cmd = read_text("/boot/boot.cmd")
    if not boot_cmd and exists("/boot/boot.scr"):
        boot_cmd = shell("strings /boot/boot.scr 2>/dev/null | grep -E 'uInitrd|initrd|bootargs|extraargs' || true")
    env_values = parse_kv_file("/boot/armbianEnv.txt")
    extraargs = env_values.get("extraargs", "")
    bootargs = env_values.get("bootargs", "")
    initrd = latest_initrd_path()
    listing = initramfs_listing(initrd)
    dump = shell("dumpimage -l /boot/uInitrd 2>/dev/null | sed -n '1,12p' || true") if exists("/boot/uInitrd") else ""
    arch_category = "unknown"
    if re.search(r"Architecture:\\s*ARM64", dump, re.I):
        arch_category = "arm64"
    elif re.search(r"Architecture:\\s*ARM", dump, re.I):
        arch_category = "arm"
    return {
        "kernel_version": shell("uname -r"),
        "cmdline_overlayroot_present": "overlayroot" in cmdline,
        "cmdline_root_present": bool(re.search(r"(^|\\s)root=", cmdline)),
        "cmdline_console_category": "serial" if "console=ttyS" in cmdline else ("tty" if "console=tty" in cmdline else "none"),
        "armbian_env_present": exists("/boot/armbianEnv.txt"),
        "armbian_env_overlayroot_present": "overlayroot" in env,
        "armbian_env_extraargs_present": "extraargs=" in env,
        "extraargs_overlayroot_present": "overlayroot=" in extraargs,
        "bootargs_overlayroot_present": "overlayroot=" in bootargs,
        "armbian_env_bootargs_present": "bootargs=" in env,
        "boot_script_uses_uinitrd": "uInitrd" in boot_cmd,
        "boot_script_uses_initrd_img": "initrd.img" in boot_cmd,
        "initrd_img_exists": bool(initrd),
        "initrd_img_size_bucket": file_size_bucket(initrd) if initrd else "missing",
        "uinitrd_exists": exists("/boot/uInitrd"),
        "uinitrd_size_bucket": file_size_bucket("/boot/uInitrd"),
        "uinitrd_dumpimage_arch_category": arch_category,
        "initramfs_contains_overlayroot_hook": "scripts/init-bottom/overlayroot" in listing or "overlayroot" in listing,
        "initramfs_contains_overlay_module": "overlay.ko" in listing,
        "initramfs_contains_c12_marker": "c12-overlayroot-initramfs-marker" in listing,
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
    "schema_version": "dadooh-c12.3.6-runtime-lab-inspect.v1",
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
payload.update(boot_snapshot())
payload.update(kernel_log_categories())
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/inspect.json"
  cat "$OUT_DIR/inspect.json"
}

hypothesis_plan() {
  remote_inspect >/dev/null
  python3 - "$OUT_DIR/inspect.json" > "$OUT_DIR/hypothesis-plan.json" <<'PY'
import json
import sys
from pathlib import Path

inspect = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
recommended = []
if not inspect.get("cmdline_overlayroot_present") and not inspect.get("extraargs_overlayroot_present"):
    recommended.append("H1")
if inspect.get("update_initramfs_available") and inspect.get("mkimage_available"):
    recommended.append("H2")
if inspect.get("overlayroot_local_conf", {}).get("present") is False:
    recommended.append("H3")
if (
    inspect.get("overlayroot_conf", {}).get("overlayroot_category") != "tmpfs"
    or inspect.get("overlayroot_conf", {}).get("overlayroot_cfgdisk_category") != "disabled"
):
    recommended.append("H4")
for fallback in ("H1", "H2", "H3", "H4"):
    if fallback not in recommended:
        recommended.append(fallback)

payload = {
    "schema_version": "dadooh-c12.3.6-hypothesis-plan.v1",
    "plan_changes_applied": False,
    "recommended_order": recommended[:4],
    "first_recommended_hypothesis": recommended[0],
    "hypotheses": {
        "H1": "add overlayroot=tmpfs to /boot/armbianEnv.txt extraargs with backup",
        "H2": "run update-initramfs for current kernel and regenerate /boot/uInitrd through Armbian/mkimage path",
        "H3": "add minimal /etc/overlayroot.local.conf only if package path hypothesis is selected",
        "H4": "normalize /etc/overlayroot.conf to overlayroot=tmpfs and overlayroot_cfgdisk=disabled",
    },
    "max_cycles": 3,
    "next_required_confirmation": "CONFIRMO APLICAR HIPOTESE OVERLAYROOT C12.3.6",
    "recommended_apply_env": f"C12_3_6_HYPOTHESIS={recommended[0]}",
    "secrets_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/hypothesis-plan.json"
  cat "$OUT_DIR/hypothesis-plan.json"
}

require_apply_confirmation() {
  if [ "$CONFIRM_APPLY" != "$EXPECTED_APPLY_CONFIRM" ]; then
    echo "error: --apply-hypothesis requires confirmation: $EXPECTED_APPLY_CONFIRM" >&2
    exit 2
  fi
  case "$HYPOTHESIS" in
    H1|H2|H3|H4) ;;
    *) echo "error: C12_3_6_HYPOTHESIS must be H1, H2, H3 or H4" >&2; exit 2 ;;
  esac
}

apply_hypothesis() {
  require_apply_confirmation
  ssh_board "C12_3_6_HYPOTHESIS='$HYPOTHESIS' python3 -" > "$OUT_DIR/apply-$HYPOTHESIS.json" <<'PY'
import json
import os
import pathlib
import shutil
import subprocess
import time

HYPOTHESIS = os.environ["C12_3_6_HYPOTHESIS"]
STATE = pathlib.Path("/data/state/totem-overlayroot-lab")
BACKUPS = STATE / "backups"
TS = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
BACKUP_DIR = BACKUPS / f"{TS}-{HYPOTHESIS}"


def run(cmd, timeout=120):
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
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o700)
    backed = {}
    kernel = run(["uname", "-r"]).stdout.strip()
    for path in (
        "/etc/overlayroot.conf",
        "/etc/overlayroot.local.conf",
        "/boot/armbianEnv.txt",
        "/boot/uInitrd",
        f"/boot/uInitrd-{kernel}",
        f"/boot/initrd.img-{kernel}",
    ):
        backed[path] = backup_file(path)
    return backed


def set_overlayroot_conf(path):
    p = pathlib.Path(path)
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines() if p.exists() else []
    out = []
    seen_overlayroot = False
    seen_cfgdisk = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("overlayroot="):
            out.append('overlayroot="tmpfs"')
            seen_overlayroot = True
        elif stripped.startswith("overlayroot_cfgdisk="):
            out.append('overlayroot_cfgdisk="disabled"')
            seen_cfgdisk = True
        else:
            out.append(line)
    if not seen_overlayroot:
        out.append('overlayroot="tmpfs"')
    if not seen_cfgdisk:
        out.append('overlayroot_cfgdisk="disabled"')
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.chmod(p, 0o644)


def apply_h1():
    path = pathlib.Path("/boot/armbianEnv.txt")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    out = []
    seen = False
    for line in lines:
        if line.startswith("extraargs="):
            tokens = [token for token in line.split("=", 1)[1].split() if not token.startswith("overlayroot=")]
            tokens.append("overlayroot=tmpfs")
            out.append("extraargs=" + " ".join(tokens))
            seen = True
        else:
            out.append(line)
    if not seen:
        out.append("extraargs=overlayroot=tmpfs")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.chmod(path, 0o644)
    return {"armbian_env_extraargs_overlayroot_added": True}


def apply_h2():
    kernel = run(["uname", "-r"]).stdout.strip()
    initrd = pathlib.Path(f"/boot/initrd.img-{kernel}")
    result = run(["update-initramfs", "-u", "-k", kernel], timeout=240)
    uinitrd = pathlib.Path("/boot/uInitrd")
    manual_mkimage = False
    if (not uinitrd.exists() or uinitrd.stat().st_size == 0) and initrd.exists() and shutil.which("mkimage"):
        arch = "arm64" if run(["dpkg", "--print-architecture"]).stdout.strip() == "arm64" else "arm"
        target = pathlib.Path(f"/boot/uInitrd-{kernel}")
        mk = run(["mkimage", "-A", arch, "-O", "linux", "-T", "ramdisk", "-C", "gzip", "-n", "uInitrd", "-d", str(initrd), str(target)], timeout=120)
        if mk.returncode == 0 and target.exists() and target.stat().st_size > 0:
            if uinitrd.exists() or uinitrd.is_symlink():
                uinitrd.unlink()
            uinitrd.symlink_to(target.name)
            manual_mkimage = True
    return {
        "update_initramfs_executed": True,
        "update_initramfs_returncode": result.returncode,
        "manual_mkimage_fallback_executed": manual_mkimage,
        "uinitrd_nonempty_after": uinitrd.exists() and uinitrd.stat().st_size > 0,
    }


def apply_h3():
    set_overlayroot_conf("/etc/overlayroot.local.conf")
    return {"overlayroot_local_conf_written": True}


def apply_h4():
    set_overlayroot_conf("/etc/overlayroot.conf")
    return {"overlayroot_conf_normalized": True}


STATE.mkdir(parents=True, exist_ok=True)
BACKUPS.mkdir(parents=True, exist_ok=True)
backed = backup_all()
if HYPOTHESIS == "H1":
    applied = apply_h1()
elif HYPOTHESIS == "H2":
    applied = apply_h2()
elif HYPOTHESIS == "H3":
    applied = apply_h3()
elif HYPOTHESIS == "H4":
    applied = apply_h4()
else:
    raise SystemExit("unsupported_hypothesis")

state = {
    "schema_version": 1,
    "timestamp": TS,
    "hypothesis": HYPOTHESIS,
    "backup_dir": str(BACKUP_DIR),
    "files_backed_up_categories": {key: value for key, value in backed.items()},
    "apply_result": applied,
    "rollback_available": True,
    "secrets_published": False,
    "raw_logs_published": False,
}
(STATE / "state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(STATE / "state.json", 0o600)
print(json.dumps(state, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/apply-$HYPOTHESIS.json"
  cat "$OUT_DIR/apply-$HYPOTHESIS.json"
}

require_reboot_confirmation() {
  if [ "$CONFIRM_REBOOT" != "$EXPECTED_REBOOT_CONFIRM" ]; then
    echo "error: --reboot-check requires confirmation: $EXPECTED_REBOOT_CONFIRM" >&2
    exit 2
  fi
}

reboot_check() {
  require_reboot_confirmation
  ssh_board "sync; systemctl reboot" || true
  {
    printf 'reboot_requested=true\n'
    printf 'poweroff_executed=false\n'
    printf 'post_reboot_action=run_inspect_after_ssh_returns\n'
  } > "$OUT_DIR/reboot-requested.env"
  cat "$OUT_DIR/reboot-requested.env"
}

rollback() {
  ssh_board "python3 -" > "$OUT_DIR/rollback.json" <<'PY'
import json
import os
import pathlib
import shutil
import subprocess

STATE = pathlib.Path("/data/state/totem-overlayroot-lab/state.json")


def run(cmd, timeout=120):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)
    except Exception as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


if not STATE.exists():
    print(json.dumps({"rollback_available": False, "rollback_executed": False, "reason": "state_missing"}, indent=2))
    raise SystemExit(0)

state = json.loads(STATE.read_text(encoding="utf-8"))
backup_dir = pathlib.Path(state.get("backup_dir", ""))
restored = {}
for source in (
    "/etc/overlayroot.conf",
    "/etc/overlayroot.local.conf",
    "/boot/armbianEnv.txt",
):
    backup = backup_dir / source.lstrip("/")
    target = pathlib.Path(source)
    if backup.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, target)
        restored[source] = True
    else:
        restored[source] = False

kernel = run(["uname", "-r"]).stdout.strip()
for source in (f"/boot/initrd.img-{kernel}", f"/boot/uInitrd-{kernel}"):
    backup = backup_dir / source.lstrip("/")
    target = pathlib.Path(source)
    if backup.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, target)
        restored[source] = True
    else:
        restored[source] = False

uinitrd_link = backup_dir / "boot/uInitrd.symlink"
uinitrd = pathlib.Path("/boot/uInitrd")
uinitrd_backup = backup_dir / "boot/uInitrd"
if uinitrd_link.exists():
    if uinitrd.exists() or uinitrd.is_symlink():
        uinitrd.unlink()
    uinitrd.symlink_to(uinitrd_link.read_text(encoding="utf-8").strip())
    restored["/boot/uInitrd"] = True
elif uinitrd_backup.exists():
    shutil.copy2(uinitrd_backup, uinitrd)
    restored["/boot/uInitrd"] = True
else:
    restored["/boot/uInitrd"] = False

rollback_done = {
    "schema_version": 1,
    "rollback_executed": True,
    "restored": restored,
    "reboot_required": True,
    "secrets_published": False,
    "raw_logs_published": False,
}
(STATE.parent / "rollback.json").write_text(json.dumps(rollback_done, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(rollback_done, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/rollback.json"
  cat "$OUT_DIR/rollback.json"
}

summary() {
  python3 - "$OUT_DIR" > "$OUT_DIR/README.md" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])

def load(name):
    path = out / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

inspect = load("inspect.json")
plan = load("hypothesis-plan.json")
print("# C12.3.6 Overlayroot Runtime Lab")
print()
print(f"- running_board_inspected: `{bool(inspect)}`")
print(f"- read_only_enabled: `{inspect.get('read_only_enabled', 'unknown')}`")
print(f"- overlay_active: `{inspect.get('overlay_active', 'unknown')}`")
print(f"- root_write_blocked_inferred: `{inspect.get('root_write_blocked_inferred', 'unknown')}`")
print(f"- recommended_order: `{plan.get('recommended_order', 'unknown')}`")
print("- secrets_published: `false`")
print("- raw_logs_published: `false`")
PY
  chmod 600 "$OUT_DIR/README.md"
  printf 'summary=%s\n' "$OUT_DIR/README.md"
}

case "$MODE" in
  prepare-only) prepare_only ;;
  inspect) remote_inspect ;;
  hypothesis-plan) hypothesis_plan ;;
  apply-hypothesis) apply_hypothesis ;;
  reboot-check) reboot_check ;;
  rollback) rollback ;;
  summary) summary ;;
esac
