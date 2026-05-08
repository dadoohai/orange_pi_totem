#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
TIMESTAMP="${C12_3_14_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${C12_3_14_RUN_ROOT:-/tmp/dadooh-c12-3-14-overlay-module-packaging-lab}"
OUT_DIR="${C12_3_14_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-3-14-overlay-module-packaging-lab}"
KNOWN_HOSTS="${C12_3_14_KNOWN_HOSTS:-/tmp/dadooh-c12-3-14-known-hosts}"
CONFIRM_APPLY="${C12_3_14_CONFIRM_APPLY:-}"
CONFIRM_REBOOT="${C12_3_14_CONFIRM_REBOOT:-}"
HYPOTHESIS="${C12_3_14_HYPOTHESIS:-manual_add_modules}"
EXPECTED_APPLY_CONFIRM="CONFIRMO APLICAR OVERLAY MODULE PACKAGING C12.3.14"
EXPECTED_REBOOT_CONFIRM="CONFIRMO REBOOT OVERLAY MODULE PACKAGING C12.3.14"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_3_14_overlay_module_packaging_lab.sh [root@host] [mode]

Modes:
  --prepare-only
  --inspect
  --plan
  --apply-initramfs-module-fix
  --reboot-check
  --collect-post-reboot
  --rollback
  --summary

Environment:
  C12_3_14_CONFIRM_APPLY="CONFIRMO APLICAR OVERLAY MODULE PACKAGING C12.3.14"
      Required for --apply-initramfs-module-fix.
  C12_3_14_CONFIRM_REBOOT="CONFIRMO REBOOT OVERLAY MODULE PACKAGING C12.3.14"
      Required for --reboot-check.
  C12_3_14_HYPOTHESIS=manual_add_modules|explicit_copy
      Defaults to manual_add_modules. Use explicit_copy only if H1 fails.

Rules:
  - lab board only; do not use dev or old test boards;
  - inspect and plan are read-only;
  - apply writes only initramfs/module packaging hooks plus initrd/uInitrd with backups;
  - reboot requires a separate explicit confirmation;
  - no writer, real config provisioning, Wi-Fi changes, package install, apt upgrade,
    poweroff, power cut, secrets or raw logs.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --plan) MODE="plan" ;;
    --apply-initramfs-module-fix) MODE="apply-initramfs-module-fix" ;;
    --reboot-check) MODE="reboot-check" ;;
    --collect-post-reboot) MODE="collect-post-reboot" ;;
    --rollback) MODE="rollback" ;;
    --summary) MODE="summary" ;;
    --help|-h) usage; exit 0 ;;
    --*) echo "error: unsupported mode $1" >&2; usage; exit 2 ;;
    *) HOST="$1" ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|inspect|plan|apply-initramfs-module-fix|reboot-check|collect-post-reboot|rollback|summary) ;;
  *) echo "error: unsupported mode $MODE" >&2; usage; exit 2 ;;
esac

case "$HYPOTHESIS" in
  manual_add_modules|explicit_copy) ;;
  *) echo "error: unsupported C12_3_14_HYPOTHESIS=$HYPOTHESIS" >&2; exit 2 ;;
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

require_apply_confirmation() {
  if [ "$CONFIRM_APPLY" != "$EXPECTED_APPLY_CONFIRM" ]; then
    echo "error: --apply-initramfs-module-fix requires confirmation:" >&2
    echo "$EXPECTED_APPLY_CONFIRM" >&2
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
  for script in \
    "$REPO_ROOT/scripts/remote/run_c12_3_13_insmod_and_black_screen_triage.sh" \
    "$REPO_ROOT/scripts/remote/run_c12_3_11_initramfs_insmod_error_classification.sh" \
    "$REPO_ROOT/scripts/build/run_c12_1_build_image_lab_readonly.sh"
  do
    if [ -f "$script" ]; then
      bash -n "$script"
    fi
  done
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  {
    printf 'c12_3_14_prepare_only=ok\n'
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
import tempfile


def run(cmd, timeout=30):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=timeout)
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, "", "")


def shell(command, timeout=30):
    return (run(["sh", "-lc", command], timeout=timeout).stdout or "").strip()


def read_text(path, limit=262144):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def bucket_size(size):
    if size is None:
        return "missing"
    if size == 0:
        return "empty"
    if size < 1024:
        return "tiny"
    if size < 1024 * 1024:
        return "small"
    return "nonempty"


def file_bucket(path):
    try:
        return bucket_size(pathlib.Path(path).stat().st_size)
    except OSError:
        return "missing"


def file_type_category(path):
    if not path:
        return "missing"
    if path.endswith(".ko"):
        return "plain_ko"
    if path.endswith((".ko.xz", ".ko.zst", ".ko.gz")):
        return "compressed"
    return "unknown"


def command_available(name):
    return bool(shell(f"command -v {name} 2>/dev/null || true"))


def modinfo(field):
    return shell(f"modinfo -F {field} overlay 2>/dev/null || true")


def deps_from_modinfo():
    deps = []
    for item in re.split(r"[,\s]+", modinfo("depends")):
        item = item.strip()
        if item:
            deps.append(item)
    return sorted(set(deps))


def mount_info(target):
    text = shell(f"findmnt -n -o SOURCE,FSTYPE,OPTIONS --target {target} 2>/dev/null || true")
    parts = text.split(None, 2)
    source = parts[0] if parts else ""
    options = parts[2] if len(parts) > 2 else ""
    option_set = {item.strip() for item in options.split(",") if item.strip()}
    return {
        "present": bool(parts),
        "source_category": "overlay" if source == "overlay" else ("device" if source.startswith("/dev/") else source if source in {"tmpfs", "proc", "sysfs"} else "other"),
        "fstype": parts[1] if len(parts) > 1 else "unknown",
        "options_category": "ro" if "ro" in option_set else "rw_or_unknown",
        "has_upperdir": "upperdir=" in options,
        "has_workdir": "workdir=" in options,
    }


def extract_initramfs(image):
    result = {
        "extractable": False,
        "overlay_present": False,
        "overlay_nonempty": False,
        "overlay_empty": False,
        "overlay_size_bucket": "missing",
        "overlay_type": "missing",
        "modules_dep_present": False,
        "modules_dep_references_overlay": False,
        "modules_alias_present": False,
        "fallback_hook_present": False,
    }
    if not pathlib.Path(image).exists():
        return result
    temp = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c12-3-14-initramfs-", dir="/tmp"))
    try:
        if command_available("unmkinitramfs"):
            proc = run(["unmkinitramfs", image, str(temp)], timeout=80)
            result["extractable"] = proc.returncode == 0
        if not result["extractable"]:
            return result
        overlay_files = [
            p for p in temp.rglob("overlay.ko*")
            if "/lib/modules/" in str(p) and p.is_file()
        ]
        if overlay_files:
            overlay = sorted(overlay_files, key=lambda p: (p.stat().st_size, str(p)), reverse=True)[0]
            size = overlay.stat().st_size
            result["overlay_present"] = True
            result["overlay_nonempty"] = size > 0
            result["overlay_empty"] = size == 0
            result["overlay_size_bucket"] = bucket_size(size)
            result["overlay_type"] = file_type_category(overlay.name)
        dep_files = [p for p in temp.rglob("modules.dep") if "/lib/modules/" in str(p) and p.is_file()]
        result["modules_dep_present"] = bool(dep_files)
        for dep in dep_files:
            text = dep.read_text(encoding="utf-8", errors="replace")
            if "overlay.ko" in text:
                result["modules_dep_references_overlay"] = True
                break
        result["modules_alias_present"] = any(p.name == "modules.alias" for p in temp.rglob("modules.alias"))
        result["fallback_hook_present"] = any(str(p).endswith("scripts/init-top/dadooh-force-overlay") for p in temp.rglob("dadooh-force-overlay"))
        return result
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def extract_uinitrd_payload(uinitrd):
    if not pathlib.Path(uinitrd).exists() or not command_available("dumpimage"):
        return ""
    temp = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c12-3-14-uinitrd-", dir="/tmp"))
    try:
        payload = temp / "uinitrd.payload"
        proc = run(["dumpimage", "-T", "ramdisk", "-p", "0", "-o", str(payload), uinitrd], timeout=40)
        if proc.returncode == 0 and payload.exists() and payload.stat().st_size > 0:
            final = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c12-3-14-uinitrd-payload-", dir="/tmp")) / "payload"
            shutil.copy2(payload, final)
            return str(final)
        return ""
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def overlayroot_conf_category():
    text = read_text("/etc/overlayroot.conf")
    if 'overlayroot="tmpfs"' in text or "overlayroot=tmpfs" in text:
        return "tmpfs"
    if 'overlayroot=""' in text:
        return "empty"
    if "overlayroot=" in text:
        return "other"
    return "missing"


def overlay_status():
    allowed = {
        "overlay_load_status",
        "modprobe_rc",
        "insmod_rc",
        "overlay_module_path_found",
        "overlay_module_path_source",
        "overlay_in_proc",
        "raw_logs_published",
    }
    path = pathlib.Path("/run/initramfs/dadooh-overlay-load.status")
    status = {}
    if not path.exists():
        return status
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in allowed:
            status[key] = value
    return status


kernel = shell("uname -r")
overlay_filename = modinfo("filename")
vermagic = modinfo("vermagic").split()
vermagic_match = "unknown"
if vermagic:
    vermagic_match = vermagic[0] == kernel
deps = deps_from_modinfo()
initrd_path = f"/boot/initrd.img-{kernel}"
uinitrd_path = "/boot/uInitrd"
uinitrd_payload = extract_uinitrd_payload(uinitrd_path)
initrd = extract_initramfs(initrd_path)
uinitrd = extract_initramfs(uinitrd_payload) if uinitrd_payload else extract_initramfs(uinitrd_path)
proc_filesystems = read_text("/proc/filesystems")
root = mount_info("/")
overlay_status_payload = overlay_status()

payload = {
    "schema_version": "dadooh-c12.3.14-overlay-module-packaging-inspect.v1",
    "board_category": "lab_board",
    "inspect_read_only": True,
    "kernel_version": kernel,
    "modinfo_overlay_works": bool(overlay_filename),
    "modinfo_overlay_filename_category": "kernel_overlayfs_module" if "/kernel/fs/overlayfs/" in overlay_filename else ("module_path_other" if overlay_filename else "missing"),
    "overlay_ko_real_exists": bool(overlay_filename and pathlib.Path(overlay_filename).exists()),
    "overlay_ko_real_size_bucket": file_bucket(overlay_filename),
    "overlay_ko_real_file_type": file_type_category(overlay_filename),
    "overlay_ko_real_vermagic_match": vermagic_match,
    "dependencies_detected": deps,
    "modprobe_overlay_dry_run_works": run(["modprobe", "-n", "-v", "overlay"], timeout=20).returncode == 0,
    "runtime_proc_filesystems_contains_overlay": bool(re.search(r"(^|\n)nodev\s+overlay(\n|$)", proc_filesystems)),
    "root_fstype": root["fstype"],
    "read_only_enabled": root["options_category"] == "ro" or root["source_category"] == "overlay",
    "overlay_active": root["source_category"] == "overlay" or root["fstype"] == "overlay",
    "overlayroot_conf_category": overlayroot_conf_category(),
    "cmdline_overlayroot_tmpfs_present": "overlayroot=tmpfs" in read_text("/proc/cmdline"),
    "initrd_path_present": pathlib.Path(initrd_path).exists(),
    "uinitrd_path_present": pathlib.Path(uinitrd_path).exists(),
    "uinitrd_nonempty": pathlib.Path(uinitrd_path).exists() and pathlib.Path(uinitrd_path).stat().st_size > 1024 * 1024,
    "initrd_contains_overlay_module": initrd["overlay_present"],
    "initrd_overlay_module_nonempty": initrd["overlay_nonempty"],
    "initrd_overlay_module_empty": initrd["overlay_empty"],
    "initrd_overlay_module_size_bucket": initrd["overlay_size_bucket"],
    "initrd_overlay_module_type": initrd["overlay_type"],
    "initrd_modules_dep_present": initrd["modules_dep_present"],
    "initrd_modules_dep_references_overlay": initrd["modules_dep_references_overlay"],
    "initrd_modules_alias_present": initrd["modules_alias_present"],
    "initrd_fallback_hook_present": initrd["fallback_hook_present"],
    "uinitrd_contains_overlay_module": uinitrd["overlay_present"],
    "uinitrd_overlay_module_nonempty": uinitrd["overlay_nonempty"],
    "uinitrd_overlay_module_empty": uinitrd["overlay_empty"],
    "uinitrd_overlay_module_size_bucket": uinitrd["overlay_size_bucket"],
    "uinitrd_overlay_module_type": uinitrd["overlay_type"],
    "uinitrd_modules_dep_present": uinitrd["modules_dep_present"],
    "uinitrd_modules_dep_references_overlay": uinitrd["modules_dep_references_overlay"],
    "uinitrd_modules_alias_present": uinitrd["modules_alias_present"],
    "uinitrd_fallback_hook_present": uinitrd["fallback_hook_present"],
    "current_overlay_load_status": overlay_status_payload,
    "raw_logs_published": False,
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/inspect.json"
  cat "$OUT_DIR/inspect.json"
}

hypothesis_plan() {
  {
    printf 'c12_3_14_plan=overlay_module_packaging_lab\n'
    printf 'h1=initramfs_tools_manual_add_modules_overlay\n'
    printf 'h1_apply_requires_confirmation=true\n'
    printf 'h1_reboot_only_if_preboot_validation_passes=true\n'
    printf 'h2=dynamic_explicit_copy_real_overlay_module_and_metadata\n'
    printf 'h2_only_if_h1_fails=true\n'
    printf 'max_cycles=2\n'
    printf 'no_writer=true\n'
    printf 'no_real_config=true\n'
    printf 'no_wifi_change=true\n'
    printf 'no_package_install=true\n'
    printf 'rollback_required=true\n'
  } > "$OUT_DIR/plan.env"
  cat "$OUT_DIR/plan.env"
}

apply_initramfs_module_fix() {
  require_apply_confirmation
  ssh_board "C12_3_14_HYPOTHESIS='$HYPOTHESIS' python3 -" > "$OUT_DIR/apply-$HYPOTHESIS.json" <<'PY'
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time


STATE = pathlib.Path("/data/state/totem-overlay-module-packaging-lab")
TS = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
BACKUP = STATE / "backups" / TS
HOOK = pathlib.Path("/etc/initramfs-tools/hooks/dadooh-overlay-module")
EXPLICIT_HOOK = pathlib.Path("/etc/initramfs-tools/hooks/dadooh-overlay-module-explicit-copy")
HYPOTHESIS = os.environ.get("C12_3_14_HYPOTHESIS", "manual_add_modules")


def run(cmd, timeout=120):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=timeout)
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, "", "")


def shell(command, timeout=120):
    return (run(["sh", "-lc", command], timeout=timeout).stdout or "").strip()


def command_available(name):
    return bool(shell(f"command -v {name} 2>/dev/null || true"))


def copy_if_exists(path):
    src = pathlib.Path(path)
    dst = BACKUP / path.lstrip("/")
    if src.exists() or src.is_symlink():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink():
            dst.write_text(f"SYMLINK->{os.readlink(src)}\n", encoding="utf-8")
        else:
            shutil.copy2(src, dst)
        return True
    marker = dst.with_suffix(dst.suffix + ".missing")
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("missing\n", encoding="utf-8")
    return False


def write_manual_hook():
    HOOK.parent.mkdir(parents=True, exist_ok=True)
    HOOK.write_text("""#!/bin/sh
set -e

case "$1" in
  prereqs) echo ""; exit 0 ;;
esac

. /usr/share/initramfs-tools/hook-functions

manual_add_modules overlay

mkdir -p "${DESTDIR}/etc/dadooh"
cat > "${DESTDIR}/etc/dadooh/c12-3-14-overlay-module-packaging-marker" <<MARKER
c12_3_14_overlay_module_packaging=manual_add_modules
manual_add_modules_overlay=attempted
raw_logs_published=false
MARKER
""", encoding="utf-8")
    os.chmod(HOOK, 0o755)
    if EXPLICIT_HOOK.exists():
        EXPLICIT_HOOK.unlink()


def write_explicit_hook():
    EXPLICIT_HOOK.parent.mkdir(parents=True, exist_ok=True)
    EXPLICIT_HOOK.write_text("""#!/bin/sh
set -e

case "$1" in
  prereqs) echo ""; exit 0 ;;
esac

. /usr/share/initramfs-tools/hook-functions

manual_add_modules overlay || true

KERNEL="${version:-$(uname -r)}"
DEST_BASE="${DESTDIR}/lib/modules/$KERNEL"
mkdir -p "$DEST_BASE"

find_module() {
  for root in "/lib/modules/$KERNEL" "/usr/lib/modules/$KERNEL"; do
    [ -d "$root" ] || continue
    found="$(find "$root" -type f \( -name 'overlay.ko' -o -name 'overlay.ko.*' \) -size +0c 2>/dev/null | head -n 1)"
    [ -n "$found" ] || continue
    printf '%s' "$found"
    return 0
  done
  return 1
}

module="$(find_module || true)"
copied=false
if [ -n "$module" ]; then
  rel="${module#/lib/modules/$KERNEL/}"
  rel="${rel#/usr/lib/modules/$KERNEL/}"
  dest="$DEST_BASE/$rel"
  mkdir -p "$(dirname "$dest")"
  cp -p "$module" "$dest"
  copied=true
fi

for root in "/lib/modules/$KERNEL" "/usr/lib/modules/$KERNEL"; do
  [ -d "$root" ] || continue
  for metadata in \
    modules.dep modules.dep.bin modules.alias modules.alias.bin \
    modules.builtin modules.builtin.bin modules.builtin.modinfo \
    modules.order modules.symbols modules.symbols.bin modules.softdep; do
    [ -f "$root/$metadata" ] || continue
    cp -p "$root/$metadata" "$DEST_BASE/$metadata"
  done
done

mkdir -p "${DESTDIR}/etc/dadooh"
cat > "${DESTDIR}/etc/dadooh/c12-3-14-overlay-module-packaging-marker" <<MARKER
c12_3_14_overlay_module_packaging=explicit_copy
overlay_module_copied=$copied
raw_logs_published=false
MARKER
""", encoding="utf-8")
    os.chmod(EXPLICIT_HOOK, 0o755)
    if HOOK.exists():
        HOOK.unlink()


def regenerate_uinitrd(kernel):
    initrd = pathlib.Path(f"/boot/initrd.img-{kernel}")
    uinitrd = pathlib.Path("/boot/uInitrd")
    if not initrd.exists() or not command_available("mkimage"):
        return {"mkimage_available": command_available("mkimage"), "uinitrd_regenerated": False}
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c12-3-14-uinitrd-", dir="/tmp"))
    try:
        out = tmp / "uInitrd"
        proc = run(["mkimage", "-A", "arm64", "-O", "linux", "-T", "ramdisk", "-C", "gzip", "-n", f"uInitrd-{kernel}", "-d", str(initrd), str(out)], timeout=120)
        if proc.returncode == 0 and out.exists() and out.stat().st_size > 1024 * 1024:
            shutil.copy2(out, uinitrd)
            return {"mkimage_available": True, "uinitrd_regenerated": True, "uinitrd_nonempty": True}
        return {"mkimage_available": True, "uinitrd_regenerated": False, "uinitrd_nonempty": uinitrd.exists() and uinitrd.stat().st_size > 1024 * 1024}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def extract_image(image):
    result = {
        "extractable": False,
        "overlay_module_nonempty": False,
        "overlay_module_empty": False,
        "overlay_module_size_bucket": "missing",
        "modules_dep_references_overlay": False,
        "modules_dep_present": False,
        "marker_present": False,
    }
    if not pathlib.Path(image).exists() or not command_available("unmkinitramfs"):
        return result
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c12-3-14-inspect-", dir="/tmp"))
    try:
        proc = run(["unmkinitramfs", image, str(tmp)], timeout=120)
        result["extractable"] = proc.returncode == 0
        if not result["extractable"]:
            return result
        overlay_files = [p for p in tmp.rglob("overlay.ko*") if "/lib/modules/" in str(p) and p.is_file()]
        if overlay_files:
            overlay = sorted(overlay_files, key=lambda p: (p.stat().st_size, str(p)), reverse=True)[0]
            size = overlay.stat().st_size
            result["overlay_module_nonempty"] = size > 0
            result["overlay_module_empty"] = size == 0
            result["overlay_module_size_bucket"] = "empty" if size == 0 else ("small" if size < 1024 * 1024 else "nonempty")
        dep_files = [p for p in tmp.rglob("modules.dep") if "/lib/modules/" in str(p) and p.is_file()]
        result["modules_dep_present"] = bool(dep_files)
        result["modules_dep_references_overlay"] = any("overlay.ko" in p.read_text(encoding="utf-8", errors="replace") for p in dep_files)
        result["marker_present"] = any(p.name == "c12-3-14-overlay-module-packaging-marker" for p in tmp.rglob("c12-3-14-overlay-module-packaging-marker"))
        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


STATE.mkdir(parents=True, exist_ok=True)
BACKUP.mkdir(parents=True, exist_ok=True)
kernel = shell("uname -r")
targets = [
    "/etc/initramfs-tools/hooks/dadooh-overlay-module",
    "/etc/initramfs-tools/hooks/dadooh-overlay-module-explicit-copy",
    f"/boot/initrd.img-{kernel}",
    "/boot/uInitrd",
]
backups = {target: copy_if_exists(target) for target in targets}

if HYPOTHESIS == "manual_add_modules":
    write_manual_hook()
elif HYPOTHESIS == "explicit_copy":
    write_explicit_hook()
else:
    raise SystemExit("unsupported_hypothesis")

depmod = run(["depmod", "-a", kernel], timeout=120)
update = run(["update-initramfs", "-u", "-k", kernel], timeout=240)
uinitrd = regenerate_uinitrd(kernel)
post = extract_image(f"/boot/initrd.img-{kernel}")
preboot_validation_passed = bool(
    post["overlay_module_nonempty"]
    and post["modules_dep_references_overlay"]
    and uinitrd.get("uinitrd_regenerated")
    and uinitrd.get("uinitrd_nonempty")
)
state = {
    "schema_version": "dadooh-c12.3.14-overlay-module-packaging-state.v1",
    "updated_at": TS,
    "hypothesis": HYPOTHESIS,
    "kernel": kernel,
    "backup_dir": str(BACKUP),
    "rollback_available": True,
    "preboot_validation_passed": preboot_validation_passed,
}
(STATE / "state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(STATE / "state.json", 0o600)

payload = {
    "schema_version": "dadooh-c12.3.14-overlay-module-packaging-apply.v1",
    "hypothesis": HYPOTHESIS,
    "backups_created": backups,
    "rollback_available": True,
    "depmod_exit_code_bucket": "zero" if depmod.returncode == 0 else "nonzero",
    "update_initramfs_exit_code_bucket": "zero" if update.returncode == 0 else "nonzero",
    "uinitrd_regenerated": uinitrd.get("uinitrd_regenerated", False),
    "uinitrd_nonempty": uinitrd.get("uinitrd_nonempty", False),
    "overlay_module_nonempty_in_initramfs": post["overlay_module_nonempty"],
    "overlay_module_empty_in_initramfs": post["overlay_module_empty"],
    "overlay_module_size_bucket": post["overlay_module_size_bucket"],
    "modules_dep_references_overlay": post["modules_dep_references_overlay"],
    "modules_dep_present": post["modules_dep_present"],
    "packaging_marker_present": post["marker_present"],
    "preboot_validation_passed": preboot_validation_passed,
    "reboot_allowed_by_runner": preboot_validation_passed,
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
    "raw_logs_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/apply-$HYPOTHESIS.json"
  cat "$OUT_DIR/apply-$HYPOTHESIS.json"
}

reboot_check() {
  require_reboot_confirmation
  local preboot_file="$OUT_DIR/apply-$HYPOTHESIS.json"
  if [ -f "$preboot_file" ] && ! grep -q '"preboot_validation_passed": true' "$preboot_file"; then
    echo "error: refusing reboot because preboot validation did not pass" >&2
    exit 4
  fi
  ssh_board "python3 - <<'PY'
import json
import pathlib
state = pathlib.Path('/data/state/totem-overlay-module-packaging-lab/state.json')
ok = False
try:
    payload = json.loads(state.read_text(encoding='utf-8'))
    ok = payload.get('preboot_validation_passed') is True
except Exception:
    ok = False
if not ok:
    raise SystemExit('preboot_validation_not_passed')
PY
systemctl reboot" || true
  {
    printf 'reboot_requested=true\n'
    printf 'reboot_requires_manual_ssh_wait=true\n'
    printf 'host_category=lab_board\n'
  } > "$OUT_DIR/reboot-request.env"
  cat "$OUT_DIR/reboot-request.env"
}

remote_post_reboot_summary() {
  ssh_board "python3 -" > "$OUT_DIR/post-reboot.json" <<'PY'
import json
import pathlib
import re
import subprocess


def run(cmd, timeout=20):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=timeout)
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, "", "")


def shell(command, timeout=20):
    return (run(["sh", "-lc", command], timeout=timeout).stdout or "").strip()


def read_text(path, limit=65536):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def mount_info(target):
    text = shell(f"findmnt -n -o SOURCE,FSTYPE,OPTIONS --target {target} 2>/dev/null || true")
    parts = text.split(None, 2)
    source = parts[0] if parts else ""
    options = parts[2] if len(parts) > 2 else ""
    option_set = {item.strip() for item in options.split(",") if item.strip()}
    return {
        "present": bool(parts),
        "source_category": "overlay" if source == "overlay" else ("device" if source.startswith("/dev/") else source if source in {"tmpfs", "proc", "sysfs"} else "other"),
        "fstype": parts[1] if len(parts) > 1 else "unknown",
        "options_category": "ro" if "ro" in option_set else "rw_or_unknown",
        "has_upperdir": "upperdir=" in options,
        "has_workdir": "workdir=" in options,
    }


def writable_probe(directory):
    if directory not in {"/data", "/tmp", "/run"}:
        return "not_executed"
    target = pathlib.Path("/data/state") if directory == "/data" else pathlib.Path(directory)
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".dadooh-c12-3-14-writable-probe"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def root_write_blocked():
    path = pathlib.Path("/root/.dadooh-c12-3-14-root-write-probe")
    try:
        path.write_text("blocked?\n", encoding="utf-8")
        path.unlink()
        return False
    except Exception:
        return True


def load_json(path):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def failed_count():
    text = shell("systemctl --failed --no-legend --plain 2>/dev/null || true")
    return len([line for line in text.splitlines() if line.strip()])


root = mount_info("/")
public = load_json("/tmp/dadooh-status/status.json")
launcher = load_json("/data/state/kiosky-player/launcher-status.json") or load_json("/tmp/kiosky-launcher-status.json")
state = public.get("public_state") or public.get("state") or launcher.get("state", "unknown")
proc_filesystems = read_text("/proc/filesystems")

payload = {
    "schema_version": "dadooh-c12.3.14-overlay-module-packaging-post-reboot.v1",
    "ssh_returned": True,
    "read_only_enabled": root["source_category"] == "overlay" or root["options_category"] == "ro",
    "overlay_active": root["source_category"] == "overlay" or root["fstype"] == "overlay",
    "root_write_blocked": root_write_blocked(),
    "root_fstype": root["fstype"],
    "root_source_category": root["source_category"],
    "data_writable": writable_probe("/data"),
    "tmp_writable": writable_probe("/tmp"),
    "run_writable": writable_probe("/run"),
    "overlay_in_proc_after_boot": bool(re.search(r"(^|\n)nodev\s+overlay(\n|$)", proc_filesystems)),
    "public_state": state,
    "systemctl_failed_count": failed_count(),
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "raw_logs_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/post-reboot.json"
  cat "$OUT_DIR/post-reboot.json"
}

rollback() {
  ssh_board "python3 -" > "$OUT_DIR/rollback.json" <<'PY'
import json
import pathlib
import shutil
import subprocess

STATE = pathlib.Path("/data/state/totem-overlay-module-packaging-lab")
STATE_FILE = STATE / "state.json"


def run(cmd, timeout=180):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=timeout)
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, "", "")


def shell(command, timeout=60):
    return (run(["sh", "-lc", command], timeout=timeout).stdout or "").strip()


def command_available(name):
    return bool(shell(f"command -v {name} 2>/dev/null || true"))


def restore_path(backup_dir, target):
    target_path = pathlib.Path(target)
    backup_path = pathlib.Path(backup_dir) / target.lstrip("/")
    missing_marker = pathlib.Path(str(backup_path) + ".missing")
    if backup_path.exists():
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, target_path)
        return "restored"
    if missing_marker.exists():
        if target_path.exists():
            if target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                target_path.unlink()
        return "removed_created_file"
    return "backup_missing"


def regenerate_uinitrd(kernel):
    initrd = pathlib.Path(f"/boot/initrd.img-{kernel}")
    if not initrd.exists() or not command_available("mkimage"):
        return False
    tmp = pathlib.Path("/tmp/dadooh-c12-3-14-rollback-uInitrd")
    if tmp.exists():
        tmp.unlink()
    proc = run(["mkimage", "-A", "arm64", "-O", "linux", "-T", "ramdisk", "-C", "gzip", "-n", f"uInitrd-{kernel}", "-d", str(initrd), str(tmp)], timeout=120)
    if proc.returncode == 0 and tmp.exists() and tmp.stat().st_size > 1024 * 1024:
        shutil.copy2(tmp, "/boot/uInitrd")
        tmp.unlink()
        return True
    return False


try:
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
except Exception:
    state = {}
backup_dir = state.get("backup_dir", "")
kernel = state.get("kernel") or shell("uname -r")
targets = [
    "/etc/initramfs-tools/hooks/dadooh-overlay-module",
    "/etc/initramfs-tools/hooks/dadooh-overlay-module-explicit-copy",
    f"/boot/initrd.img-{kernel}",
    "/boot/uInitrd",
]
restored = {target: restore_path(backup_dir, target) for target in targets} if backup_dir else {}
update = run(["update-initramfs", "-u", "-k", kernel], timeout=240)
uinitrd = regenerate_uinitrd(kernel)
payload = {
    "schema_version": "dadooh-c12.3.14-overlay-module-packaging-rollback.v1",
    "rollback_executed": True,
    "backup_dir_present": bool(backup_dir),
    "restored": restored,
    "update_initramfs_exit_code_bucket": "zero" if update.returncode == 0 else "nonzero",
    "uinitrd_regenerated": uinitrd,
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
    "raw_logs_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/rollback.json"
  cat "$OUT_DIR/rollback.json"
}

summary() {
  local inspect_file="$OUT_DIR/inspect.json"
  local apply_file="$OUT_DIR/apply-$HYPOTHESIS.json"
  local post_file="$OUT_DIR/post-reboot.json"
  python3 - "$inspect_file" "$apply_file" "$post_file" > "$OUT_DIR/summary.env" <<'PY'
import json
import pathlib
import sys


def load(path):
    try:
        p = pathlib.Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


inspect = load(sys.argv[1])
apply = load(sys.argv[2])
post = load(sys.argv[3])
winner = "none"
if post.get("read_only_enabled") and post.get("overlay_active") and post.get("root_write_blocked"):
    winner = apply.get("hypothesis", "unknown")
elif apply.get("preboot_validation_passed"):
    winner = "preboot_packaging_passed_runtime_failed_or_not_rebooted"

lines = {
    "h1_result": "unknown",
    "h2_result": "unknown",
    "overlay_module_nonempty_in_initramfs": apply.get("overlay_module_nonempty_in_initramfs", inspect.get("uinitrd_overlay_module_nonempty", "unknown")),
    "modules_dep_references_overlay": apply.get("modules_dep_references_overlay", inspect.get("uinitrd_modules_dep_references_overlay", "unknown")),
    "reboot_executed": bool(post),
    "read_only_enabled": post.get("read_only_enabled", inspect.get("read_only_enabled", "unknown")),
    "overlay_active": post.get("overlay_active", inspect.get("overlay_active", "unknown")),
    "root_write_blocked": post.get("root_write_blocked", "unknown"),
    "winning_fix": winner,
    "ready_for_c12_1_11_rebuild": winner in {"manual_add_modules", "explicit_copy"},
}
hypothesis = apply.get("hypothesis")
if hypothesis == "manual_add_modules":
    lines["h1_result"] = "preboot_passed" if apply.get("preboot_validation_passed") else "preboot_failed"
elif hypothesis == "explicit_copy":
    lines["h2_result"] = "preboot_passed" if apply.get("preboot_validation_passed") else "preboot_failed"
for key, value in lines.items():
    if isinstance(value, bool):
        value = str(value).lower()
    print(f"{key}={value}")
PY
  cat "$OUT_DIR/summary.env"
}

case "$MODE" in
  prepare-only) prepare_only ;;
  inspect) remote_inspect ;;
  plan) hypothesis_plan ;;
  apply-initramfs-module-fix) apply_initramfs_module_fix ;;
  reboot-check) reboot_check ;;
  collect-post-reboot) remote_post_reboot_summary ;;
  rollback) rollback ;;
  summary) summary ;;
esac
