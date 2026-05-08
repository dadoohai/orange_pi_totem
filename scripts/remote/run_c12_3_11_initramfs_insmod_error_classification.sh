#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
TIMESTAMP="${C12_3_11_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${C12_3_11_RUN_ROOT:-/tmp/dadooh-c12-3-11-initramfs-insmod-error-classification}"
OUT_DIR="${C12_3_11_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-3-11-initramfs-insmod-error-classification}"
KNOWN_HOSTS="${C12_3_11_KNOWN_HOSTS:-/tmp/dadooh-c12-3-11-known-hosts}"
CONFIRM_INSTALL="${C12_3_11_CONFIRM_INSTALL:-}"
CONFIRM_REBOOT="${C12_3_11_CONFIRM_REBOOT:-}"
EXPECTED_INSTALL_CONFIRM="CONFIRMO DIAGNOSTICO INSMOD INITRAMFS C12.3.11"
EXPECTED_REBOOT_CONFIRM="CONFIRMO REBOOT DIAGNOSTICO INSMOD C12.3.11"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_3_11_initramfs_insmod_error_classification.sh [root@host] [mode]

Modes:
  --prepare-only
  --inspect
  --install-diagnostic-hook
  --reboot-check
  --collect-diagnostic
  --rollback
  --summary

Environment:
  C12_3_11_CONFIRM_INSTALL="CONFIRMO DIAGNOSTICO INSMOD INITRAMFS C12.3.11"
      Required for --install-diagnostic-hook.
  C12_3_11_CONFIRM_REBOOT="CONFIRMO REBOOT DIAGNOSTICO INSMOD C12.3.11"
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
  bash -n "$REPO_ROOT/scripts/remote/run_c12_3_10_boot_validate_c12_1_9.sh"
  bash -n "$REPO_ROOT/scripts/remote/run_c12_3_9_initramfs_overlay_module_diagnostics.sh"
  bash -n "$REPO_ROOT/scripts/build/run_c12_1_build_image_lab_readonly.sh"
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  {
    printf 'c12_3_11_prepare_only=ok\n'
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
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=timeout)
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


def bucket_size(path):
    try:
        size = pathlib.Path(path).stat().st_size
    except OSError:
        return "missing"
    if size == 0:
        return "empty"
    if size < 1024 * 1024:
        return "small"
    return "nonempty"


def module_format(path):
    if not path:
        return "missing"
    if path.endswith(".ko"):
        return "plain_ko"
    if path.endswith((".ko.xz", ".ko.zst", ".ko.gz")):
        return "compressed"
    return "unknown"


def modinfo_field(module, field):
    return shell(f"modinfo -F {field} {module} 2>/dev/null || true")


def deps_from_modinfo():
    text = modinfo_field("overlay", "depends")
    deps = []
    for item in re.split(r"[,\\s]+", text):
        item = item.strip()
        if item:
            deps.append(item)
    return sorted(set(deps))


def deps_present_in_initramfs(kernel, deps):
    if not deps:
        return "not_applicable"
    initrd = pathlib.Path(f"/boot/initrd.img-{kernel}")
    uinitrd = pathlib.Path("/boot/uInitrd")
    listings = []
    for image in (initrd, uinitrd):
        if not image.exists() or not command_available("lsinitramfs"):
            continue
        listings.append(shell(f"lsinitramfs {image} 2>/dev/null || true", timeout=40))
    joined = "\n".join(listings)
    if not joined:
        return "unknown"
    missing = [dep for dep in deps if f"/{dep}.ko" not in joined and f"/{dep}.ko." not in joined]
    return not missing


def modules_dep_references_overlay(kernel):
    dep = pathlib.Path(f"/lib/modules/{kernel}/modules.dep")
    text = read_text(str(dep))
    return "overlay.ko" in text


def initramfs_contains_dependencies(kernel, deps):
    return deps_present_in_initramfs(kernel, deps)


kernel = shell("uname -r")
overlay_path = modinfo_field("overlay", "filename")
vermagic = modinfo_field("overlay", "vermagic").split()
vermagic_match = "unknown"
if vermagic:
    vermagic_match = vermagic[0] == kernel
deps = deps_from_modinfo()
modprobe = run(["modprobe", "-n", "-v", "overlay"], timeout=15)
proc_filesystems = read_text("/proc/filesystems")
lsmod_overlay = shell("lsmod 2>/dev/null | awk '$1 == \"overlay\" {print $1}' | head -1 || true")

payload = {
    "schema_version": "dadooh-c12.3.11-initramfs-insmod-error-inspect.v1",
    "board_category": "lab_board",
    "inspect_read_only": True,
    "kernel_version": kernel,
    "overlay_ko_exists": bool(overlay_path and pathlib.Path(overlay_path).exists()),
    "overlay_ko_size_bucket": bucket_size(overlay_path),
    "overlay_ko_file_type": module_format(overlay_path),
    "overlay_ko_path_category": "kernel_overlayfs_module" if "/kernel/fs/overlayfs/" in overlay_path else ("module_path_other" if overlay_path else "missing"),
    "vermagic_match": vermagic_match,
    "dependencies_detected": deps,
    "dependencies_present": initramfs_contains_dependencies(kernel, deps),
    "modules_dep_references_overlay": modules_dep_references_overlay(kernel),
    "modules_dep_references_dependencies": "not_applicable" if not deps else initramfs_contains_dependencies(kernel, deps),
    "modprobe_overlay_post_boot_works": modprobe.returncode == 0,
    "lsmod_shows_overlay": lsmod_overlay == "overlay",
    "proc_filesystems_contains_overlay": bool(re.search(r"(^|\\n)nodev\\s+overlay(\\n|$)", proc_filesystems)),
    "initramfs_contains_dependencies": initramfs_contains_dependencies(kernel, deps),
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
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

STATE = pathlib.Path("/data/state/totem-insmod-diagnostics")
BACKUPS = STATE / "backups"
TS = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
BACKUP_DIR = BACKUPS / f"{TS}-C12-3-11-insmod-diagnostic"
HOOK = pathlib.Path("/etc/initramfs-tools/scripts/init-top/dadooh-insmod-error-diagnostic")


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


def backup_all(kernel):
    STATE.mkdir(parents=True, exist_ok=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o700)
    backed = {}
    for path in (
        str(HOOK),
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


def regenerate_uinitrd(kernel):
    initrd = pathlib.Path(f"/boot/initrd.img-{kernel}")
    target = pathlib.Path(f"/boot/uInitrd-{kernel}")
    uinitrd = pathlib.Path("/boot/uInitrd")
    payload = {
        "uinitrd_regenerated": False,
        "uinitrd_nonempty_after": uinitrd.exists() and uinitrd.stat().st_size > 0,
        "mkimage_available": bool(shutil.which("mkimage")),
    }
    if initrd.exists() and shutil.which("mkimage"):
        arch = "arm64" if shell("dpkg --print-architecture") == "arm64" else "arm"
        mk = run(["mkimage", "-A", arch, "-O", "linux", "-T", "ramdisk", "-C", "gzip", "-n", "uInitrd", "-d", str(initrd), str(target)], timeout=180)
        payload["mkimage_returncode"] = mk.returncode
        if mk.returncode == 0 and target.exists() and target.stat().st_size > 0:
            if uinitrd.exists() or uinitrd.is_symlink():
                uinitrd.unlink()
            uinitrd.symlink_to(target.name)
            payload["uinitrd_regenerated"] = True
            payload["uinitrd_nonempty_after"] = True
        else:
            payload["uinitrd_nonempty_after"] = uinitrd.exists() and uinitrd.stat().st_size > 0
    return payload


def update_initramfs(kernel):
    result = run(["update-initramfs", "-u", "-k", kernel], timeout=300)
    payload = {
        "update_initramfs_executed": True,
        "update_initramfs_returncode": result.returncode,
        "update_initramfs_ok": result.returncode == 0,
    }
    payload.update(regenerate_uinitrd(kernel))
    return payload


def write_hook():
    HOOK.parent.mkdir(parents=True, exist_ok=True)
    HOOK.write_text("""#!/bin/sh
PREREQ=""
prereqs() { echo "$PREREQ"; }
case "$1" in
  prereqs) prereqs; exit 0 ;;
esac

OUT="/run/initramfs/dadooh-insmod-error-diagnostic.json"
TMPERR="/run/initramfs/dadooh-insmod-error-diagnostic.err"
TMPDMESG="/run/initramfs/dadooh-insmod-error-diagnostic.dmesg"
mkdir -p /run/initramfs

json_string() {
  printf '%s' "$1" | sed 's/\\\\/\\\\\\\\/g; s/"/\\\\"/g'
}
bool_file_readable() { [ -r "$1" ] && echo true || echo false; }
bucket_rc() {
  case "$1" in
    missing) echo missing ;;
    0) echo zero ;;
    *) echo nonzero ;;
  esac
}
size_bucket() {
  if [ ! -e "$1" ]; then
    echo missing
    return
  fi
  SIZE="$(wc -c < "$1" 2>/dev/null || echo 0)"
  if [ "$SIZE" -eq 0 ] 2>/dev/null; then
    echo empty
  elif [ "$SIZE" -lt 1048576 ] 2>/dev/null; then
    echo small
  else
    echo nonempty
  fi
}
contains_overlay() {
  if [ -r /proc/filesystems ] && grep -qw overlay /proc/filesystems 2>/dev/null; then
    echo true
  else
    echo false
  fi
}
stderr_category() {
  FILE="$1"
  if [ ! -s "$FILE" ]; then
    echo no_message
  elif grep -Eiq 'invalid module format|exec format' "$FILE"; then
    echo invalid_module_format
  elif grep -Eiq 'unknown symbol|unresolved symbol' "$FILE"; then
    echo unknown_symbol
  elif grep -Eiq 'no such file|not found|cannot find' "$FILE"; then
    echo file_not_found
  elif grep -Eiq 'permission denied|operation not permitted' "$FILE"; then
    echo permission_denied
  elif grep -Eiq 'file exists|already loaded' "$FILE"; then
    echo module_already_loaded
  elif grep -Eiq 'no such device' "$FILE"; then
    echo no_such_device
  elif grep -Eiq 'required key|key was rejected|signature' "$FILE"; then
    echo required_key_missing
  else
    echo unknown
  fi
}
dmesg_category() {
  FILE="$1"
  if [ ! -s "$FILE" ]; then
    echo no_message
  elif grep -Eiq 'invalid module format|vermagic' "$FILE"; then
    echo vermagic_mismatch
  elif grep -Eiq 'unknown symbol|unresolved symbol' "$FILE"; then
    echo unknown_symbol
  elif grep -Eiq 'disagrees about version of symbol|module_layout' "$FILE"; then
    echo module_layout_mismatch
  elif grep -Eiq 'required key|key was rejected|signature' "$FILE"; then
    echo required_key_missing
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
OVERLAY_TYPE="$(file_type_category "$OVERLAY_KO")"
OVERLAY_SIZE_BUCKET="$(size_bucket "$OVERLAY_KO")"
MODULES_DEP="/lib/modules/$KERNEL/modules.dep"
MODULES_DEP_EXISTS="$(bool_file_readable "$MODULES_DEP")"
MODULES_DEP_REFS=false
if [ -r "$MODULES_DEP" ] && grep -q 'overlay\\.ko' "$MODULES_DEP" 2>/dev/null; then
  MODULES_DEP_REFS=true
fi
MODULE_PATH_MATCH=false
case "$OVERLAY_KO" in
  *"/$KERNEL/"*) MODULE_PATH_MATCH=true ;;
esac
DEPS=""
DEPS_PRESENT=unknown
if [ -r "$MODULES_DEP" ] && [ "$OVERLAY_KO_EXISTS" = true ]; then
  REL="${OVERLAY_KO#/lib/modules/$KERNEL/}"
  LINE="$(grep -E "(^|/)$REL:" "$MODULES_DEP" 2>/dev/null | head -n 1)"
  if [ -n "$LINE" ]; then
    RAW_DEPS="$(printf '%s' "$LINE" | cut -d: -f2-)"
    DEPS_PRESENT=true
    for DEP in $RAW_DEPS; do
      NAME="$(basename "$DEP" | sed -E 's/\\.ko(\\..*)?$//')"
      [ -n "$NAME" ] && DEPS="${DEPS}${NAME},"
      if [ ! -e "/lib/modules/$KERNEL/$DEP" ]; then
        DEPS_PRESENT=false
      fi
    done
  fi
fi
[ -z "$DEPS" ] && DEPS=""
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
MODPROBE_STDERR_CATEGORY=missing
if [ "$MODPROBE_PRESENT" = true ]; then
  : > "$TMPERR"
  modprobe overlay >/dev/null 2>"$TMPERR"
  MODPROBE_RC=$?
  MODPROBE_STDERR_CATEGORY="$(stderr_category "$TMPERR")"
fi
OVERLAY_AFTER_MODPROBE="$(contains_overlay)"

INSMOD_ATTEMPTED=false
INSMOD_RC=missing
INSMOD_STDERR_CATEGORY=missing
DMESG_CATEGORY=no_message
if [ "$OVERLAY_AFTER_MODPROBE" != true ] && [ "$INSMOD_PRESENT" = true ] && [ "$OVERLAY_KO_EXISTS" = true ]; then
  INSMOD_ATTEMPTED=true
  : > "$TMPERR"
  insmod "$OVERLAY_KO" >/dev/null 2>"$TMPERR"
  INSMOD_RC=$?
  INSMOD_STDERR_CATEGORY="$(stderr_category "$TMPERR")"
  if command -v dmesg >/dev/null 2>&1; then
    dmesg 2>/dev/null | tail -n 80 > "$TMPDMESG" 2>/dev/null || true
    DMESG_CATEGORY="$(dmesg_category "$TMPDMESG")"
  fi
fi
OVERLAY_AFTER_INSMOD="$(contains_overlay)"
rm -f "$TMPERR" "$TMPDMESG" 2>/dev/null || true

cat > "$OUT" <<EOF
{
  "schema_version": "dadooh-c12.3.11-initramfs-insmod-error-diagnostic.v1",
  "proc_mounted": $PROC_MOUNTED,
  "overlay_in_proc_before": $OVERLAY_BEFORE,
  "modprobe_present": $MODPROBE_PRESENT,
  "insmod_present": $INSMOD_PRESENT,
  "overlay_ko_exists": $OVERLAY_KO_EXISTS,
  "overlay_ko_file_type": "$OVERLAY_TYPE",
  "overlay_ko_size_bucket": "$OVERLAY_SIZE_BUCKET",
  "uname_kernel": "$(json_string "$KERNEL")",
  "module_path_kernel_matches": $MODULE_PATH_MATCH,
  "modules_dep_exists": $MODULES_DEP_EXISTS,
  "modules_dep_references_overlay": $MODULES_DEP_REFS,
  "overlay_dependencies_detected": "$(json_string "$DEPS")",
  "dependencies_present": "$DEPS_PRESENT",
  "vermagic_match": "$VERMAGIC_MATCH",
  "modprobe_overlay_exit_code_bucket": "$(bucket_rc "$MODPROBE_RC")",
  "modprobe_stderr_category": "$MODPROBE_STDERR_CATEGORY",
  "proc_filesystems_has_overlay_after_modprobe": $OVERLAY_AFTER_MODPROBE,
  "insmod_overlay_attempted": $INSMOD_ATTEMPTED,
  "insmod_overlay_exit_code_bucket": "$(bucket_rc "$INSMOD_RC")",
  "insmod_stderr_category": "$INSMOD_STDERR_CATEGORY",
  "dmesg_category": "$DMESG_CATEGORY",
  "proc_filesystems_has_overlay_after": $OVERLAY_AFTER_INSMOD,
  "mount_overlay_test_attempted": false,
  "raw_logs_published": false
}
EOF
exit 0
""", encoding="utf-8")
    os.chmod(HOOK, 0o755)


kernel = shell("uname -r")
cycles = current_cycles()
if len(cycles) >= 2:
    raise SystemExit("maximum C12.3.11 diagnostic cycles already reached")
backed = backup_all(kernel)
write_hook()
update = update_initramfs(kernel)
cycles.append({"cycle": len(cycles) + 1, "backup_dir": str(BACKUP_DIR), "installed_at": TS})
state = {
    "schema_version": "dadooh-c12.3.11-initramfs-insmod-error-state.v1",
    "updated_at": TS,
    "cycles": cycles,
    "last_backup_dir": str(BACKUP_DIR),
    "rollback_available": True,
    "hook_path": str(HOOK),
    "secrets_published": False,
}
(STATE / "state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(STATE / "state.json", 0o600)

hook_in_initrd = False
if pathlib.Path(f"/boot/initrd.img-{kernel}").exists() and shutil.which("lsinitramfs"):
    listing = shell(f"lsinitramfs /boot/initrd.img-{kernel} 2>/dev/null | grep -F dadooh-insmod-error-diagnostic || true", timeout=40)
    hook_in_initrd = bool(listing)

payload = {
    "schema_version": "dadooh-c12.3.11-initramfs-insmod-error-install.v1",
    "diagnostic_hook_installed": HOOK.exists(),
    "diagnostic_hook_in_initrd": hook_in_initrd,
    "backup_dir_category": "data_state_totem_insmod_diagnostics",
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
  "schema_version": "dadooh-c12.3.11-initramfs-insmod-error-reboot.v1",
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
    "schema_version": "dadooh-c12.3.11-initramfs-insmod-error-reboot.v1",
    "reboot_executed": True,
    "ssh_returned": True,
    "read_only_enabled": data.get("read_only_enabled"),
    "overlay_active": data.get("overlay_active"),
    "root_write_blocked": data.get("root_write_blocked"),
    "cause_category": data.get("cause_category"),
    "next_step": data.get("next_step"),
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
        path = target / ".dadooh-c12-3-11-writable-probe"
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


def classify(diag):
    if not diag:
        return "UNKNOWN", "READONLY_MECHANISM_DECISION_REOPEN"
    if diag.get("vermagic_match") in {False, "false"}:
        return "OVERLAY_MODULE_VERMAGIC_MISMATCH", "KERNEL_MODULE_VERSION_FIX_OR_REBUILD"
    if diag.get("dependencies_present") in {False, "false"}:
        return "OVERLAY_MODULE_DEPENDENCY_MISSING", "C12_1_10_REBUILD_WITH_OVERLAY_DEPENDENCIES"
    if diag.get("overlay_ko_file_type") == "compressed" and diag.get("insmod_stderr_category") in {"invalid_module_format", "exec_format_error", "unknown"}:
        return "OVERLAY_MODULE_COMPRESSED_UNSUPPORTED", "UNCOMPRESS_OR_LOAD_MODULE_CORRECTLY_IN_INITRAMFS"
    if diag.get("insmod_stderr_category") == "unknown_symbol" or diag.get("dmesg_category") == "unknown_symbol":
        return "OVERLAY_INSMOD_UNKNOWN_SYMBOL", "INCLUDE_MISSING_SYMBOL_DEPENDENCIES"
    if diag.get("insmod_stderr_category") in {"invalid_module_format", "exec_format_error"}:
        return "OVERLAY_INSMOD_INVALID_FORMAT", "UNCOMPRESS_OR_LOAD_MODULE_CORRECTLY_IN_INITRAMFS"
    if diag.get("module_path_kernel_matches") in {False, "false"} or not diag.get("overlay_ko_exists"):
        return "OVERLAY_MODULE_PATH_MISMATCH", "C12_1_10_REBUILD_WITH_EFFECTIVE_MODULE_PATH"
    if diag.get("insmod_stderr_category") == "required_key_missing" or diag.get("dmesg_category") == "required_key_missing":
        return "OVERLAY_MODULE_SIGNATURE_OR_KEY_REJECTED", "READONLY_MECHANISM_DECISION_REOPEN"
    if diag.get("modprobe_overlay_exit_code_bucket") == "zero" and diag.get("proc_filesystems_has_overlay_after_modprobe") is False:
        if diag.get("insmod_overlay_exit_code_bucket") == "nonzero":
            stderr = diag.get("insmod_stderr_category", "unknown")
            dmesg = diag.get("dmesg_category", "unknown")
            if stderr in {"no_message", "unknown"} and dmesg in {"no_message", "unknown"}:
                return "OVERLAY_MODPROBE_FALSE_SUCCESS", "READONLY_MECHANISM_DECISION_REOPEN"
    if diag.get("proc_filesystems_has_overlay_after") is True:
        return "OVERLAY_RUNTIME_ONLY_AVAILABLE_AFTER_LATE_BOOT", "READONLY_MECHANISM_DECISION_REOPEN"
    return "UNKNOWN", "READONLY_MECHANISM_DECISION_REOPEN"


diag = load_json("/run/initramfs/dadooh-insmod-error-diagnostic.json")
root = mount_info("/")
read_only_enabled = root["source_category"] == "overlay" or root["options_category"] == "ro"
overlay_active = root["source_category"] == "overlay" or root["fstype"] == "overlay"
root_write_blocked = root["source_category"] == "overlay" or root["options_category"] == "ro"
cause, next_step = classify(diag)

payload = {
    "schema_version": "dadooh-c12.3.11-initramfs-insmod-error-result.v1",
    "diagnostic_collected": bool(diag),
    "diagnostic_hook_installed": exists("/etc/initramfs-tools/scripts/init-top/dadooh-insmod-error-diagnostic"),
    "diagnostic_file_present": exists("/run/initramfs/dadooh-insmod-error-diagnostic.json"),
    "proc_mounted": diag.get("proc_mounted", "unknown"),
    "overlay_in_proc_before": diag.get("overlay_in_proc_before", "unknown"),
    "overlay_ko_exists": diag.get("overlay_ko_exists", "unknown"),
    "overlay_ko_file_type": diag.get("overlay_ko_file_type", "unknown"),
    "overlay_ko_size_bucket": diag.get("overlay_ko_size_bucket", "unknown"),
    "module_path_kernel_matches": diag.get("module_path_kernel_matches", "unknown"),
    "modules_dep_exists": diag.get("modules_dep_exists", "unknown"),
    "modules_dep_references_overlay": diag.get("modules_dep_references_overlay", "unknown"),
    "dependencies_detected": diag.get("overlay_dependencies_detected", ""),
    "dependencies_present": diag.get("dependencies_present", "unknown"),
    "vermagic_match": diag.get("vermagic_match", "unknown"),
    "modprobe_overlay_result": diag.get("modprobe_overlay_exit_code_bucket", "unknown"),
    "modprobe_stderr_category": diag.get("modprobe_stderr_category", "unknown"),
    "proc_filesystems_has_overlay_after_modprobe": diag.get("proc_filesystems_has_overlay_after_modprobe", "unknown"),
    "insmod_overlay_attempted": diag.get("insmod_overlay_attempted", "unknown"),
    "insmod_overlay_result": diag.get("insmod_overlay_exit_code_bucket", "unknown"),
    "insmod_stderr_category": diag.get("insmod_stderr_category", "unknown"),
    "dmesg_category": diag.get("dmesg_category", "unknown"),
    "proc_filesystems_has_overlay_after": diag.get("proc_filesystems_has_overlay_after", "unknown"),
    "read_only_enabled": read_only_enabled,
    "overlay_active": overlay_active,
    "root_write_blocked": root_write_blocked,
    "data_writable": writable_probe("/data"),
    "tmp_writable": writable_probe("/tmp"),
    "run_writable": writable_probe("/run"),
    "product": status_snapshot(),
    "systemctl_failed_count": shell("systemctl --failed --no-legend 2>/dev/null | wc -l | tr -d ' '") or "unknown",
    "cause_category": cause,
    "next_step": next_step,
    "raw_logs_published": False,
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
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

STATE = pathlib.Path("/data/state/totem-insmod-diagnostics")
HOOK = pathlib.Path("/etc/initramfs-tools/scripts/init-top/dadooh-insmod-error-diagnostic")


def run(cmd, timeout=180):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)
    except Exception as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def shell(command, timeout=30):
    return (run(["sh", "-lc", command], timeout=timeout).stdout or "").strip()


def load_state():
    try:
        data = json.loads((STATE / "state.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def restore_file(backup_dir, path):
    dest = pathlib.Path(path)
    src = pathlib.Path(backup_dir) / dest.relative_to("/")
    symlink_marker = src.with_suffix(src.suffix + ".symlink")
    if symlink_marker.exists():
        target = symlink_marker.read_text(encoding="utf-8").strip()
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        dest.symlink_to(target)
        return True
    if src.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return True
    return False


def regenerate_uinitrd(kernel):
    initrd = pathlib.Path(f"/boot/initrd.img-{kernel}")
    target = pathlib.Path(f"/boot/uInitrd-{kernel}")
    uinitrd = pathlib.Path("/boot/uInitrd")
    payload = {"uinitrd_regenerated": False, "uinitrd_nonempty_after": uinitrd.exists() and uinitrd.stat().st_size > 0}
    if initrd.exists() and shutil.which("mkimage"):
        arch = "arm64" if shell("dpkg --print-architecture") == "arm64" else "arm"
        mk = run(["mkimage", "-A", arch, "-O", "linux", "-T", "ramdisk", "-C", "gzip", "-n", "uInitrd", "-d", str(initrd), str(target)], timeout=180)
        payload["mkimage_returncode"] = mk.returncode
        if mk.returncode == 0 and target.exists() and target.stat().st_size > 0:
            if uinitrd.exists() or uinitrd.is_symlink():
                uinitrd.unlink()
            uinitrd.symlink_to(target.name)
            payload["uinitrd_regenerated"] = True
            payload["uinitrd_nonempty_after"] = True
    return payload


state = load_state()
backup_dir = state.get("last_backup_dir")
kernel = shell("uname -r")
restored = {}
if backup_dir:
    for path in (
        str(HOOK),
        "/boot/uInitrd",
        f"/boot/uInitrd-{kernel}",
        f"/boot/initrd.img-{kernel}",
    ):
        restored[path] = restore_file(backup_dir, path)

if not restored.get(str(HOOK), False) and HOOK.exists():
    HOOK.unlink()

update = run(["update-initramfs", "-u", "-k", kernel], timeout=300)
regen = regenerate_uinitrd(kernel)

payload = {
    "schema_version": "dadooh-c12.3.11-initramfs-insmod-error-rollback.v1",
    "rollback_executed": True,
    "backup_dir_category": "data_state_totem_insmod_diagnostics" if backup_dir else "missing",
    "restored": restored,
    "diagnostic_hook_present_after": HOOK.exists(),
    "update_initramfs_returncode": update.returncode,
    "update_initramfs_ok": update.returncode == 0,
}
payload.update(regen)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/rollback.json"
}

summary() {
  local source="$OUT_DIR/diagnostic.json"
  if [ ! -f "$source" ]; then
    if [ -f "$OUT_DIR/inspect.json" ]; then
      source="$OUT_DIR/inspect.json"
    else
      echo "error: no diagnostic or inspect output found in $OUT_DIR" >&2
      exit 2
    fi
  fi
  python3 - "$source" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
keys = [
    "diagnostic_collected",
    "overlay_ko_exists",
    "overlay_ko_file_type",
    "vermagic_match",
    "dependencies_detected",
    "dependencies_present",
    "insmod_stderr_category",
    "dmesg_category",
    "read_only_enabled",
    "overlay_active",
    "root_write_blocked",
    "cause_category",
    "next_step",
]
for key in keys:
    if key in data:
        print(f"{key}={data[key]}")
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
