#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
TIMESTAMP="${C12_3_15_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${C12_3_15_RUN_ROOT:-/tmp/dadooh-c12-3-15-initramfs-overlay-load-failure}"
OUT_DIR="${C12_3_15_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-3-15-initramfs-overlay-load-failure}"
KNOWN_HOSTS="${C12_3_15_KNOWN_HOSTS:-/tmp/dadooh-c12-3-15-known-hosts}"
CONFIRM_HOOK="${C12_3_15_CONFIRM_HOOK:-}"
CONFIRM_REBOOT="${C12_3_15_CONFIRM_REBOOT:-}"
EXPECTED_HOOK_CONFIRM="CONFIRMO DIAGNOSTICO LOAD OVERLAY C12.3.15"
EXPECTED_REBOOT_CONFIRM="CONFIRMO REBOOT DIAGNOSTICO LOAD OVERLAY C12.3.15"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_3_15_initramfs_overlay_load_failure.sh [root@host] [mode]

Modes:
  --prepare-only
  --inspect
  --install-load-diagnostic-hook
  --reboot-check
  --collect-diagnostic
  --rollback
  --summary

Environment:
  C12_3_15_CONFIRM_HOOK="CONFIRMO DIAGNOSTICO LOAD OVERLAY C12.3.15"
      Required for --install-load-diagnostic-hook.
  C12_3_15_CONFIRM_REBOOT="CONFIRMO REBOOT DIAGNOSTICO LOAD OVERLAY C12.3.15"
      Required for --reboot-check.

Rules:
  - lab board only; do not use dev or old test boards;
  - inspect and collect are read-only;
  - hook install writes only a temporary initramfs diagnostic hook plus backed-up
    initrd/uInitrd;
  - reboot requires separate explicit confirmation;
  - rollback restores backups and removes the temporary hook;
  - no writer, real config provisioning, Wi-Fi changes, package install, apt
    upgrade, poweroff, power cut, secrets or raw logs.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --install-load-diagnostic-hook) MODE="install-load-diagnostic-hook" ;;
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
  prepare-only|inspect|install-load-diagnostic-hook|reboot-check|collect-diagnostic|rollback|summary) ;;
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

require_hook_confirmation() {
  if [ "$CONFIRM_HOOK" != "$EXPECTED_HOOK_CONFIRM" ]; then
    echo "error: --install-load-diagnostic-hook requires confirmation:" >&2
    echo "$EXPECTED_HOOK_CONFIRM" >&2
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
    "$REPO_ROOT/scripts/remote/run_c12_3_14_overlay_module_packaging_lab.sh" \
    "$REPO_ROOT/scripts/remote/run_c12_3_13_insmod_and_black_screen_triage.sh" \
    "$REPO_ROOT/scripts/build/run_c12_1_build_image_lab_readonly.sh"
  do
    if [ -f "$script" ]; then
      bash -n "$script"
    fi
  done
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  {
    printf 'c12_3_15_prepare_only=ok\n'
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


def command_available(name):
    return bool(shell(f"command -v {name} 2>/dev/null || true"))


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


def file_type(path):
    if not path:
        return "missing"
    if path.endswith(".ko"):
        return "plain_ko"
    if path.endswith((".ko.xz", ".ko.zst", ".ko.gz")):
        return "compressed"
    return "unknown"


def modinfo(field):
    return shell(f"modinfo -F {field} overlay 2>/dev/null || true")


def deps_from_modinfo():
    deps = []
    for item in re.split(r"[,\s]+", modinfo("depends")):
        item = item.strip()
        if item:
            deps.append(item)
    return sorted(set(deps))


def extract_uinitrd_payload(uinitrd):
    if not pathlib.Path(uinitrd).exists() or not command_available("dumpimage"):
        return ""
    temp = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c12-3-15-uinitrd-", dir="/tmp"))
    try:
        payload = temp / "uinitrd.payload"
        proc = run(["dumpimage", "-T", "ramdisk", "-p", "0", "-o", str(payload), uinitrd], timeout=40)
        if proc.returncode == 0 and payload.exists() and payload.stat().st_size > 0:
            final_dir = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c12-3-15-uinitrd-payload-", dir="/tmp"))
            final = final_dir / "payload"
            shutil.copy2(payload, final)
            return str(final)
        return ""
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def inspect_initramfs(image, kernel, deps):
    result = {
        "extractable": False,
        "overlay_ko_present": False,
        "overlay_ko_nonempty": False,
        "overlay_ko_size_bucket": "missing",
        "overlay_ko_file_type": "missing",
        "modules_dep_present": False,
        "modules_dep_references_overlay": False,
        "dependencies_present": "unknown",
    }
    if not pathlib.Path(image).exists() or not command_available("unmkinitramfs"):
        return result
    temp = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c12-3-15-initramfs-", dir="/tmp"))
    try:
        proc = run(["unmkinitramfs", image, str(temp)], timeout=90)
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
            result["overlay_ko_present"] = True
            result["overlay_ko_nonempty"] = size > 0
            result["overlay_ko_size_bucket"] = bucket_size(size)
            result["overlay_ko_file_type"] = file_type(overlay.name)
        dep_files = [p for p in temp.rglob("modules.dep") if "/lib/modules/" in str(p) and p.is_file()]
        result["modules_dep_present"] = bool(dep_files)
        dep_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in dep_files)
        result["modules_dep_references_overlay"] = "overlay.ko" in dep_text
        if not deps:
            result["dependencies_present"] = "not_applicable"
        else:
            missing = []
            for dep in deps:
                found = any(p.name == f"{dep}.ko" or p.name.startswith(f"{dep}.ko.") for p in temp.rglob(f"{dep}.ko*"))
                if not found:
                    missing.append(dep)
            result["dependencies_present"] = not missing
        return result
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def mount_info(target):
    text = shell(f"findmnt -n -o SOURCE,FSTYPE,OPTIONS --target {target} 2>/dev/null || true")
    parts = text.split(None, 2)
    source = parts[0] if parts else ""
    options = parts[2] if len(parts) > 2 else ""
    option_set = {item.strip() for item in options.split(",") if item.strip()}
    return {
        "source_category": "overlay" if source == "overlay" else ("device" if source.startswith("/dev/") else source if source in {"tmpfs", "proc", "sysfs"} else "other"),
        "fstype": parts[1] if len(parts) > 1 else "unknown",
        "options_category": "ro" if "ro" in option_set else "rw_or_unknown",
    }


kernel = shell("uname -r")
overlay_filename = modinfo("filename")
vermagic = modinfo("vermagic").split()
vermagic_match = "unknown"
if vermagic:
    vermagic_match = vermagic[0] == kernel
deps = deps_from_modinfo()
signer = modinfo("signer")
sig_key = modinfo("sig_key")
root = mount_info("/")
u_payload = extract_uinitrd_payload("/boot/uInitrd")
initrd = inspect_initramfs(f"/boot/initrd.img-{kernel}", kernel, deps)
uinitrd = inspect_initramfs(u_payload or "/boot/uInitrd", kernel, deps)
proc_filesystems = read_text("/proc/filesystems")

payload = {
    "schema_version": "dadooh-c12.3.15-initramfs-overlay-load-inspect.v1",
    "board_category": "lab_board",
    "inspect_read_only": True,
    "kernel_booted": kernel,
    "kernel_expected_by_module": vermagic[0] if vermagic else "unknown",
    "overlay_ko_real_present_rootfs": bool(overlay_filename and pathlib.Path(overlay_filename).exists()),
    "overlay_ko_real_size_bucket": file_bucket(overlay_filename),
    "overlay_ko_real_file_type": file_type(overlay_filename),
    "overlay_ko_present_initrd": initrd["overlay_ko_present"],
    "overlay_ko_present_uinitrd": uinitrd["overlay_ko_present"],
    "overlay_ko_nonempty_initrd": initrd["overlay_ko_nonempty"],
    "overlay_ko_nonempty_uinitrd": uinitrd["overlay_ko_nonempty"],
    "overlay_ko_size_bucket_initrd": initrd["overlay_ko_size_bucket"],
    "overlay_ko_size_bucket_uinitrd": uinitrd["overlay_ko_size_bucket"],
    "overlay_ko_file_type_initrd": initrd["overlay_ko_file_type"],
    "overlay_ko_file_type_uinitrd": uinitrd["overlay_ko_file_type"],
    "modules_dep_references_overlay_initrd": initrd["modules_dep_references_overlay"],
    "modules_dep_references_overlay_uinitrd": uinitrd["modules_dep_references_overlay"],
    "modinfo_vermagic_match": vermagic_match,
    "modinfo_depends": deps,
    "modinfo_signer_present": bool(signer),
    "modinfo_signature_present": bool(sig_key),
    "dependencies_present_in_initrd": initrd["dependencies_present"],
    "dependencies_present_in_uinitrd": uinitrd["dependencies_present"],
    "modprobe_overlay_post_boot_works": run(["modprobe", "-n", "-v", "overlay"], timeout=20).returncode == 0,
    "proc_filesystems_contains_overlay_post_boot": bool(re.search(r"(^|\n)nodev\s+overlay(\n|$)", proc_filesystems)),
    "read_only_enabled": root["source_category"] == "overlay" or root["options_category"] == "ro",
    "overlay_active": root["source_category"] == "overlay" or root["fstype"] == "overlay",
    "root_fstype": root["fstype"],
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

install_load_diagnostic_hook() {
  require_hook_confirmation
  ssh_board "python3 -" > "$OUT_DIR/install-load-diagnostic-hook.json" <<'PY'
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time


STATE = pathlib.Path("/data/state/totem-overlay-load-diagnostic-c12-3-15")
TS = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
BACKUP = STATE / "backups" / TS
HOOK = pathlib.Path("/etc/initramfs-tools/scripts/init-top/dadooh-c12-3-15-overlay-load-diagnostic")


def run(cmd, timeout=180):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=timeout)
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, "", "")


def shell(command, timeout=60):
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
    marker = pathlib.Path(str(dst) + ".missing")
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("missing\n", encoding="utf-8")
    return False


def write_hook():
    HOOK.parent.mkdir(parents=True, exist_ok=True)
    HOOK.write_text(r'''#!/bin/sh
PREREQ=""
prereqs() { echo "$PREREQ"; }
case "$1" in
  prereqs) prereqs; exit 0 ;;
esac

OUT="/run/initramfs/dadooh-c12-3-15-overlay-load-diagnostic.json"
mkdir -p /run/initramfs
TMPERR="/run/initramfs/dadooh-c12-3-15-stderr.tmp"
TMPDMESG="/run/initramfs/dadooh-c12-3-15-dmesg.tmp"
MOUNTTMP="/run/initramfs/dadooh-c12-3-15-mount"

json_string() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

contains_overlay() {
  [ -r /proc/filesystems ] && grep -qw overlay /proc/filesystems 2>/dev/null
}

bool_file_nonempty() {
  [ -s "$1" ] && echo true || echo false
}

bucket_rc() {
  case "$1" in
    0) echo zero ;;
    missing) echo missing ;;
    *) echo nonzero ;;
  esac
}

stderr_category() {
  FILE="$1"
  if [ ! -s "$FILE" ]; then
    echo no_message
  elif grep -Eiq 'invalid module format|vermagic' "$FILE"; then
    echo invalid_module_format
  elif grep -Eiq 'unknown symbol|unresolved symbol' "$FILE"; then
    echo unknown_symbol
  elif grep -Eiq 'exec format' "$FILE"; then
    echo exec_format_error
  elif grep -Eiq 'no such file|not found|cannot stat' "$FILE"; then
    echo file_not_found
  elif grep -Eiq 'permission denied|operation not permitted' "$FILE"; then
    echo permission_denied
  elif grep -Eiq 'already loaded|file exists' "$FILE"; then
    echo already_loaded
  elif grep -Eiq 'no such device' "$FILE"; then
    echo no_such_device
  elif grep -Eiq 'required key|key was rejected|signature' "$FILE"; then
    echo required_key_missing
  elif grep -Eiq 'dependency|module not found' "$FILE"; then
    echo dependency_missing
  else
    echo unknown
  fi
}

dmesg_category() {
  FILE="$1"
  if [ ! -s "$FILE" ]; then
    echo no_message
  elif grep -Eiq 'invalid module format|vermagic' "$FILE"; then
    echo invalid_module_format
  elif grep -Eiq 'disagrees about version' "$FILE"; then
    echo disagrees_about_version
  elif grep -Eiq 'unknown symbol|unresolved symbol' "$FILE"; then
    echo unknown_symbol
  elif grep -Eiq 'required key|key was rejected|signature' "$FILE"; then
    echo required_key_missing
  elif grep -Eiq 'module_layout' "$FILE"; then
    echo module_layout_mismatch
  else
    echo unknown
  fi
}

mount_error_category() {
  FILE="$1"
  if [ ! -s "$FILE" ]; then
    echo no_message
  elif grep -Eiq 'invalid argument' "$FILE"; then
    echo invalid_argument
  elif grep -Eiq 'permission denied|operation not permitted' "$FILE"; then
    echo permission_denied
  elif grep -Eiq 'lowerdir|upperdir|workdir|no such file' "$FILE"; then
    echo missing_lower_upper_work
  else
    echo unknown
  fi
}

file_type_category() {
  case "$1" in
    *.ko) echo plain_ko ;;
    *.ko.xz|*.ko.zst|*.ko.gz) echo compressed ;;
    "") echo missing ;;
    *) echo unknown ;;
  esac
}

find_overlay_module() {
  K="$1"
  if [ -r "/lib/modules/$K/modules.dep" ]; then
    DEP_PATH="$(awk -F: '/(^|\/)overlay\.ko(\..*)?:/ {print $1; exit}' "/lib/modules/$K/modules.dep" 2>/dev/null || true)"
    if [ -n "$DEP_PATH" ]; then
      case "$DEP_PATH" in
        /lib/modules/*) CANDIDATE="$DEP_PATH" ;;
        *) CANDIDATE="/lib/modules/$K/$DEP_PATH" ;;
      esac
      if [ -s "$CANDIDATE" ]; then
        printf '%s|modules_dep' "$CANDIDATE"
        return
      fi
    fi
  fi
  CANDIDATE="/lib/modules/$K/kernel/fs/overlayfs/overlay.ko"
  if [ -s "$CANDIDATE" ]; then
    printf '%s|static_fallback' "$CANDIDATE"
    return
  fi
  FOUND="$(find "/lib/modules/$K" -type f \( -name 'overlay.ko' -o -name 'overlay.ko.*' \) -size +0c 2>/dev/null | head -n 1)"
  if [ -n "$FOUND" ]; then
    printf '%s|find' "$FOUND"
    return
  fi
  printf '|missing'
}

KERNEL="$(uname -r 2>/dev/null || echo unknown)"
PROC_MOUNTED=false
[ -r /proc/filesystems ] && PROC_MOUNTED=true
OVERLAY_BEFORE="$(contains_overlay && echo true || echo false)"
PATH_AND_SOURCE="$(find_overlay_module "$KERNEL")"
OVERLAY_KO="${PATH_AND_SOURCE%|*}"
OVERLAY_SOURCE="${PATH_AND_SOURCE#*|}"
OVERLAY_KO_EXISTS=false
OVERLAY_KO_NONEMPTY=false
[ -n "$OVERLAY_KO" ] && [ -f "$OVERLAY_KO" ] && OVERLAY_KO_EXISTS=true
[ -n "$OVERLAY_KO" ] && [ -s "$OVERLAY_KO" ] && OVERLAY_KO_NONEMPTY=true
OVERLAY_TYPE="$(file_type_category "$OVERLAY_KO")"
MODULE_PATH_MATCH=false
case "$OVERLAY_KO" in
  *"/$KERNEL/"*) MODULE_PATH_MATCH=true ;;
esac
MODULES_DEP="/lib/modules/$KERNEL/modules.dep"
MODULES_DEP_REFS=false
[ -r "$MODULES_DEP" ] && grep -q 'overlay\.ko' "$MODULES_DEP" 2>/dev/null && MODULES_DEP_REFS=true

DEPS=""
DEPS_PRESENT=unknown
if [ -r "$MODULES_DEP" ] && [ "$OVERLAY_KO_NONEMPTY" = true ]; then
  REL="${OVERLAY_KO#/lib/modules/$KERNEL/}"
  LINE="$(grep -E "(^|/)$REL:" "$MODULES_DEP" 2>/dev/null | head -n 1)"
  if [ -n "$LINE" ]; then
    RAW_DEPS="$(printf '%s' "$LINE" | cut -d: -f2-)"
    if [ -z "$RAW_DEPS" ]; then
      DEPS_PRESENT=not_applicable
    else
      DEPS_PRESENT=true
      for DEP in $RAW_DEPS; do
        NAME="$(basename "$DEP" | sed -E 's/\.ko(\..*)?$//')"
        [ -n "$NAME" ] && DEPS="${DEPS}${NAME},"
        case "$DEP" in
          /lib/modules/*) DEP_ABS="$DEP" ;;
          *) DEP_ABS="/lib/modules/$KERNEL/$DEP" ;;
        esac
        [ -e "$DEP_ABS" ] || DEPS_PRESENT=false
      done
    fi
  fi
fi

VERMAGIC_MATCH=unknown
if command -v modinfo >/dev/null 2>&1 && [ "$OVERLAY_KO_NONEMPTY" = true ]; then
  VM="$(modinfo -F vermagic "$OVERLAY_KO" 2>/dev/null | awk '{print $1}' | head -n 1)"
  if [ "$VM" = "$KERNEL" ]; then
    VERMAGIC_MATCH=true
  elif [ -n "$VM" ]; then
    VERMAGIC_MATCH=false
  fi
fi

MODPROBE_RC=missing
MODPROBE_ATTEMPTED=false
: > "$TMPERR"
if command -v modprobe >/dev/null 2>&1; then
  MODPROBE_ATTEMPTED=true
  modprobe overlay >/dev/null 2>"$TMPERR"
  MODPROBE_RC=$?
fi
MODPROBE_ERROR="$(stderr_category "$TMPERR")"
OVERLAY_AFTER_MODPROBE="$(contains_overlay && echo true || echo false)"

INSMOD_RC=missing
INSMOD_ATTEMPTED=false
INSMOD_ERROR=missing
DMESG_CATEGORY=no_message
if [ "$OVERLAY_AFTER_MODPROBE" != true ] && command -v insmod >/dev/null 2>&1 && [ "$OVERLAY_KO_NONEMPTY" = true ]; then
  INSMOD_ATTEMPTED=true
  : > "$TMPERR"
  insmod "$OVERLAY_KO" >/dev/null 2>"$TMPERR"
  INSMOD_RC=$?
  INSMOD_ERROR="$(stderr_category "$TMPERR")"
  if command -v dmesg >/dev/null 2>&1; then
    dmesg 2>/dev/null | tail -n 100 > "$TMPDMESG" 2>/dev/null || true
    DMESG_CATEGORY="$(dmesg_category "$TMPDMESG")"
  fi
else
  INSMOD_ERROR=not_attempted
fi
OVERLAY_AFTER_INSMOD="$(contains_overlay && echo true || echo false)"
if [ "$INSMOD_ATTEMPTED" = true ] && [ "$INSMOD_RC" = 0 ] && [ "$OVERLAY_AFTER_INSMOD" != true ]; then
  INSMOD_ERROR=no_error_but_not_registered
fi

MOUNT_ATTEMPTED=false
MOUNT_RESULT=not_attempted
MOUNT_ERROR=not_attempted
if [ "$OVERLAY_AFTER_INSMOD" = true ] || [ "$OVERLAY_AFTER_MODPROBE" = true ]; then
  MOUNT_ATTEMPTED=true
  mkdir -p "$MOUNTTMP/lower" "$MOUNTTMP/upper" "$MOUNTTMP/work" "$MOUNTTMP/merged"
  echo ok > "$MOUNTTMP/lower/probe" 2>/dev/null || true
  : > "$TMPERR"
  if mount -t overlay overlay -o "lowerdir=$MOUNTTMP/lower,upperdir=$MOUNTTMP/upper,workdir=$MOUNTTMP/work" "$MOUNTTMP/merged" >/dev/null 2>"$TMPERR"; then
    MOUNT_RESULT=success
    umount "$MOUNTTMP/merged" >/dev/null 2>&1 || true
  else
    MOUNT_RESULT=failure
  fi
  MOUNT_ERROR="$(mount_error_category "$TMPERR")"
fi
rm -rf "$MOUNTTMP" "$TMPERR" "$TMPDMESG" 2>/dev/null || true

cat > "$OUT" <<EOF
{
  "schema_version": "dadooh-c12.3.15-overlay-load-diagnostic.v1",
  "proc_mounted": $PROC_MOUNTED,
  "overlay_in_proc_before": $OVERLAY_BEFORE,
  "overlay_ko_exists": $OVERLAY_KO_EXISTS,
  "overlay_ko_nonempty": $OVERLAY_KO_NONEMPTY,
  "overlay_ko_file_type": "$OVERLAY_TYPE",
  "overlay_ko_path_source": "$(json_string "$OVERLAY_SOURCE")",
  "module_path_kernel_matches": $MODULE_PATH_MATCH,
  "modules_dep_references_overlay": $MODULES_DEP_REFS,
  "dependencies_detected": "$(json_string "$DEPS")",
  "dependencies_present": "$(json_string "$DEPS_PRESENT")",
  "vermagic_match": "$(json_string "$VERMAGIC_MATCH")",
  "modprobe_overlay_attempted": $MODPROBE_ATTEMPTED,
  "modprobe_overlay_exit": "$(bucket_rc "$MODPROBE_RC")",
  "modprobe_error_category": "$MODPROBE_ERROR",
  "overlay_in_proc_after_modprobe": $OVERLAY_AFTER_MODPROBE,
  "insmod_overlay_attempted": $INSMOD_ATTEMPTED,
  "insmod_overlay_exit": "$(bucket_rc "$INSMOD_RC")",
  "insmod_error_category": "$INSMOD_ERROR",
  "dmesg_category": "$DMESG_CATEGORY",
  "overlay_in_proc_after_insmod": $OVERLAY_AFTER_INSMOD,
  "mount_overlay_attempted": $MOUNT_ATTEMPTED,
  "mount_overlay_result": "$MOUNT_RESULT",
  "mount_overlay_error_category": "$MOUNT_ERROR",
  "raw_logs_published": false
}
EOF
exit 0
''', encoding="utf-8")
    os.chmod(HOOK, 0o755)


def regenerate_uinitrd(kernel):
    initrd = pathlib.Path(f"/boot/initrd.img-{kernel}")
    uinitrd = pathlib.Path("/boot/uInitrd")
    if not initrd.exists() or not command_available("mkimage"):
        return {"mkimage_available": command_available("mkimage"), "uinitrd_regenerated": False}
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c12-3-15-uinitrd-", dir="/tmp"))
    try:
        out = tmp / "uInitrd"
        proc = run(["mkimage", "-A", "arm64", "-O", "linux", "-T", "ramdisk", "-C", "gzip", "-n", f"uInitrd-{kernel}", "-d", str(initrd), str(out)], timeout=120)
        if proc.returncode == 0 and out.exists() and out.stat().st_size > 1024 * 1024:
            shutil.copy2(out, uinitrd)
            return {"mkimage_available": True, "uinitrd_regenerated": True, "uinitrd_nonempty": True}
        return {"mkimage_available": True, "uinitrd_regenerated": False, "uinitrd_nonempty": uinitrd.exists() and uinitrd.stat().st_size > 1024 * 1024}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def hook_in_initramfs(kernel):
    if not pathlib.Path(f"/boot/initrd.img-{kernel}").exists() or not command_available("lsinitramfs"):
        return False
    text = shell(f"lsinitramfs /boot/initrd.img-{kernel} 2>/dev/null | grep -F dadooh-c12-3-15-overlay-load-diagnostic || true", timeout=40)
    return bool(text)


STATE.mkdir(parents=True, exist_ok=True)
BACKUP.mkdir(parents=True, exist_ok=True)
kernel = shell("uname -r")
targets = [
    str(HOOK),
    f"/boot/initrd.img-{kernel}",
    "/boot/uInitrd",
]
backups = {target: copy_if_exists(target) for target in targets}
write_hook()
update = run(["update-initramfs", "-u", "-k", kernel], timeout=240)
uinitrd = regenerate_uinitrd(kernel)
state = {
    "schema_version": "dadooh-c12.3.15-overlay-load-diagnostic-state.v1",
    "updated_at": TS,
    "kernel": kernel,
    "backup_dir": str(BACKUP),
    "hook_path": str(HOOK),
    "rollback_available": True,
    "cycles_count": 1,
}
(STATE / "state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(STATE / "state.json", 0o600)
payload = {
    "schema_version": "dadooh-c12.3.15-overlay-load-diagnostic-install.v1",
    "diagnostic_hook_installed": HOOK.exists(),
    "diagnostic_hook_in_initrd": hook_in_initramfs(kernel),
    "backups_created": backups,
    "backup_dir_category": "data_state_totem_overlay_load_diagnostic_c12_3_15",
    "rollback_available": True,
    "update_initramfs_exit_code_bucket": "zero" if update.returncode == 0 else "nonzero",
    "uinitrd_regenerated": uinitrd.get("uinitrd_regenerated", False),
    "uinitrd_nonempty": uinitrd.get("uinitrd_nonempty", False),
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
    "raw_logs_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/install-load-diagnostic-hook.json"
  cat "$OUT_DIR/install-load-diagnostic-hook.json"
}

reboot_check() {
  require_reboot_confirmation
  ssh_board "python3 - <<'PY'
import json
import pathlib
state = pathlib.Path('/data/state/totem-overlay-load-diagnostic-c12-3-15/state.json')
try:
    payload = json.loads(state.read_text(encoding='utf-8'))
    ok = payload.get('rollback_available') is True and payload.get('cycles_count') == 1
except Exception:
    ok = False
if not ok:
    raise SystemExit('diagnostic_state_not_ready')
PY
systemctl reboot" || true
  {
    printf 'reboot_requested=true\n'
    printf 'host_category=lab_board\n'
    printf 'reboot_requires_manual_ssh_wait=true\n'
  } > "$OUT_DIR/reboot-request.env"
  cat "$OUT_DIR/reboot-request.env"
}

collect_diagnostic() {
  ssh_board "python3 -" > "$OUT_DIR/diagnostic.json" <<'PY'
import json
import pathlib
import subprocess


def run(cmd, timeout=20):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=timeout)
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, "", "")


def shell(command, timeout=20):
    return (run(["sh", "-lc", command], timeout=timeout).stdout or "").strip()


def load_json(path):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def mount_info(target):
    text = shell(f"findmnt -n -o SOURCE,FSTYPE,OPTIONS --target {target} 2>/dev/null || true")
    parts = text.split(None, 2)
    source = parts[0] if parts else ""
    options = parts[2] if len(parts) > 2 else ""
    option_set = {item.strip() for item in options.split(",") if item.strip()}
    return {
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
        probe = target / ".dadooh-c12-3-15-writable-probe"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def root_write_blocked():
    path = pathlib.Path("/root/.dadooh-c12-3-15-root-write-probe")
    try:
        path.write_text("blocked?\n", encoding="utf-8")
        path.unlink()
        return False
    except Exception:
        return True


def failed_count():
    text = shell("systemctl --failed --no-legend --plain 2>/dev/null || true")
    return len([line for line in text.splitlines() if line.strip()])


def public_state():
    for path in ("/tmp/dadooh-status/status.json", "/data/state/kiosky-player/launcher-status.json", "/tmp/kiosky-launcher-status.json"):
        value = load_json(path)
        state = value.get("public_state") or value.get("state")
        if state:
            return state
    return "unknown"


diag = load_json("/run/initramfs/dadooh-c12-3-15-overlay-load-diagnostic.json")
root = mount_info("/")
payload = {
    "schema_version": "dadooh-c12.3.15-overlay-load-diagnostic-collect.v1",
    "ssh_returned": True,
    "diagnostic_present": bool(diag),
    "diagnostic": diag,
    "read_only_enabled": root["source_category"] == "overlay" or root["options_category"] == "ro",
    "overlay_active": root["source_category"] == "overlay" or root["fstype"] == "overlay",
    "root_write_blocked": root_write_blocked(),
    "root_fstype": root["fstype"],
    "data_writable": writable_probe("/data"),
    "tmp_writable": writable_probe("/tmp"),
    "run_writable": writable_probe("/run"),
    "public_state": public_state(),
    "systemctl_failed_count": failed_count(),
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "raw_logs_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/diagnostic.json"
  cat "$OUT_DIR/diagnostic.json"
}

rollback() {
  ssh_board "python3 -" > "$OUT_DIR/rollback.json" <<'PY'
import json
import pathlib
import shutil
import subprocess


STATE_FILE = pathlib.Path("/data/state/totem-overlay-load-diagnostic-c12-3-15/state.json")


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
        if target_path.exists() or target_path.is_symlink():
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
    tmp = pathlib.Path("/tmp/dadooh-c12-3-15-rollback-uInitrd")
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
hook = state.get("hook_path") or "/etc/initramfs-tools/scripts/init-top/dadooh-c12-3-15-overlay-load-diagnostic"
targets = [hook, f"/boot/initrd.img-{kernel}", "/boot/uInitrd"]
restored = {target: restore_path(backup_dir, target) for target in targets} if backup_dir else {}
update = run(["update-initramfs", "-u", "-k", kernel], timeout=240)
uinitrd = regenerate_uinitrd(kernel)
payload = {
    "schema_version": "dadooh-c12.3.15-overlay-load-diagnostic-rollback.v1",
    "rollback_executed": True,
    "backup_dir_present": bool(backup_dir),
    "restored": restored,
    "update_initramfs_exit_code_bucket": "zero" if update.returncode == 0 else "nonzero",
    "uinitrd_regenerated": uinitrd,
    "diagnostic_hook_present_after": pathlib.Path(hook).exists(),
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
  local diagnostic_file="$OUT_DIR/diagnostic.json"
  local rollback_file="$OUT_DIR/rollback.json"
  python3 - "$inspect_file" "$diagnostic_file" "$rollback_file" > "$OUT_DIR/summary.env" <<'PY'
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
collected = load(sys.argv[2])
rollback = load(sys.argv[3])
diag = collected.get("diagnostic", {}) if isinstance(collected.get("diagnostic"), dict) else {}


def classify():
    if diag.get("vermagic_match") == "false":
        return "OVERLAY_MODULE_VERMAGIC_MISMATCH", "C12_KERNEL_OR_MODULE_COMPATIBILITY_DECISION"
    if diag.get("dependencies_present") == "false":
        return "OVERLAY_MODULE_DEPENDENCY_MISSING", "C12_1_11_REBUILD_WITH_MODULE_DEPENDENCY_FIX"
    insmod_error = diag.get("insmod_error_category", "unknown")
    dmesg = diag.get("dmesg_category", "unknown")
    if insmod_error == "unknown_symbol" or dmesg == "unknown_symbol":
        return "OVERLAY_INSMOD_UNKNOWN_SYMBOL", "C12_1_11_REBUILD_WITH_MODULE_DEPENDENCY_FIX"
    if insmod_error in {"invalid_module_format", "vermagic_mismatch"} or dmesg in {"invalid_module_format", "disagrees_about_version", "module_layout_mismatch"}:
        return "OVERLAY_INSMOD_INVALID_FORMAT", "C12_KERNEL_OR_MODULE_COMPATIBILITY_DECISION"
    if insmod_error == "required_key_missing" or dmesg == "required_key_missing":
        return "OVERLAY_MODULE_SIGNATURE_OR_KEY_REJECTED", "C12_KERNEL_OR_MODULE_COMPATIBILITY_DECISION"
    if insmod_error == "exec_format_error":
        return "OVERLAY_MODULE_EXEC_FORMAT_ERROR", "C12_KERNEL_OR_MODULE_COMPATIBILITY_DECISION"
    if diag.get("overlay_in_proc_after_insmod") is True or diag.get("overlay_in_proc_after_modprobe") is True:
        if diag.get("mount_overlay_result") == "failure":
            return "OVERLAY_MOUNT_FAILED_AFTER_LOAD", "C12_OVERLAYROOT_SCRIPT_COMPATIBILITY_FIX"
        if not collected.get("overlay_active") or not collected.get("root_write_blocked"):
            return "OVERLAY_MODULE_LOADS_BUT_NOT_REGISTERED", "C12_KERNEL_OVERLAY_COMPATIBILITY_DECISION"
    if diag.get("insmod_error_category") == "no_error_but_not_registered":
        return "OVERLAY_MODULE_LOADS_BUT_NOT_REGISTERED", "C12_KERNEL_OVERLAY_COMPATIBILITY_DECISION"
    if diag.get("modprobe_overlay_exit") == "zero" and diag.get("insmod_overlay_exit") == "nonzero" and diag.get("dmesg_category") == "no_message":
        return "INITRAMFS_MODULE_LOADING_UNSUPPORTED", "C12_KERNEL_OR_MODULE_COMPATIBILITY_DECISION"
    return "UNKNOWN", "ADR_UPDATE_READONLY_MECHANISM_DECISION"


cause, next_step = classify()
values = {
    "hook_installed": pathlib.Path(sys.argv[2]).exists(),
    "reboot_executed": bool(collected),
    "overlay_ko_nonempty": diag.get("overlay_ko_nonempty", inspect.get("overlay_ko_nonempty_uinitrd", "unknown")),
    "vermagic_match": diag.get("vermagic_match", inspect.get("modinfo_vermagic_match", "unknown")),
    "dependencies_present": diag.get("dependencies_present", inspect.get("dependencies_present_in_uinitrd", "unknown")),
    "modprobe_result": diag.get("modprobe_overlay_exit", "unknown"),
    "insmod_result": diag.get("insmod_overlay_exit", "unknown"),
    "insmod_error_category": diag.get("insmod_error_category", "unknown"),
    "dmesg_category": diag.get("dmesg_category", "unknown"),
    "mount_overlay_result": diag.get("mount_overlay_result", "not_attempted"),
    "read_only_enabled": collected.get("read_only_enabled", inspect.get("read_only_enabled", "unknown")),
    "overlay_active": collected.get("overlay_active", inspect.get("overlay_active", "unknown")),
    "root_write_blocked": collected.get("root_write_blocked", "unknown"),
    "rollback_executed": rollback.get("rollback_executed", False),
    "cause_category": cause,
    "next_step": next_step,
    "ready_for_c12_1_11_rebuild": next_step == "C12_1_11_REBUILD_WITH_MODULE_DEPENDENCY_FIX",
}
for key, value in values.items():
    if isinstance(value, bool):
        value = str(value).lower()
    print(f"{key}={value}")
PY
  cat "$OUT_DIR/summary.env"
}

case "$MODE" in
  prepare-only) prepare_only ;;
  inspect) remote_inspect ;;
  install-load-diagnostic-hook) install_load_diagnostic_hook ;;
  reboot-check) reboot_check ;;
  collect-diagnostic) collect_diagnostic ;;
  rollback) rollback ;;
  summary) summary ;;
esac
