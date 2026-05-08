#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
TIMESTAMP="${C12_3_13_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${C12_3_13_RUN_ROOT:-/tmp/dadooh-c12-3-13-insmod-and-black-screen-triage}"
OUT_DIR="${C12_3_13_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-3-13-insmod-and-black-screen-triage}"
KNOWN_HOSTS="${C12_3_13_KNOWN_HOSTS:-/tmp/dadooh-c12-3-13-known-hosts}"
CONFIRM_HOOK="${C12_3_13_CONFIRM_HOOK:-}"
CONFIRM_REBOOT="${C12_3_13_CONFIRM_REBOOT:-}"
EXPECTED_HOOK_CONFIRM="CONFIRMO DIAGNOSTICO INSMOD C12.3.13"
EXPECTED_REBOOT_CONFIRM="CONFIRMO REBOOT DIAGNOSTICO INSMOD C12.3.13"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_3_13_insmod_and_black_screen_triage.sh [root@host] [mode]

Modes:
  --prepare-only
  --inspect-current
  --install-insmod-diagnostic-hook
  --reboot-insmod-diagnostic
  --collect-insmod-diagnostic
  --triage-config-missing-visual
  --rollback-diagnostic-hook
  --summary

Environment:
  C12_3_13_CONFIRM_HOOK="CONFIRMO DIAGNOSTICO INSMOD C12.3.13"
      Required for --install-insmod-diagnostic-hook.
  C12_3_13_CONFIRM_REBOOT="CONFIRMO REBOOT DIAGNOSTICO INSMOD C12.3.13"
      Required for --reboot-insmod-diagnostic.

Rules:
  - diagnostics only on the disposable C12 image-lab board;
  - inspect and visual triage are read-only;
  - no dev board, old test board, writer, real config, Wi-Fi changes, packages,
    apt upgrade, poweroff, power cut, secrets or raw logs;
  - at most one initramfs diagnostic reboot in this runner.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect-current) MODE="inspect-current" ;;
    --install-insmod-diagnostic-hook) MODE="install-insmod-diagnostic-hook" ;;
    --reboot-insmod-diagnostic) MODE="reboot-insmod-diagnostic" ;;
    --collect-insmod-diagnostic) MODE="collect-insmod-diagnostic" ;;
    --triage-config-missing-visual) MODE="triage-config-missing-visual" ;;
    --rollback-diagnostic-hook) MODE="rollback-diagnostic-hook" ;;
    --summary) MODE="summary" ;;
    --help|-h) usage; exit 0 ;;
    --*) echo "error: unsupported mode $1" >&2; usage; exit 2 ;;
    *) HOST="$1" ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|inspect-current|install-insmod-diagnostic-hook|reboot-insmod-diagnostic|collect-insmod-diagnostic|triage-config-missing-visual|rollback-diagnostic-hook|summary) ;;
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
    echo "error: --install-insmod-diagnostic-hook requires confirmation:" >&2
    echo "$EXPECTED_HOOK_CONFIRM" >&2
    exit 3
  fi
}

require_reboot_confirmation() {
  if [ "$CONFIRM_REBOOT" != "$EXPECTED_REBOOT_CONFIRM" ]; then
    echo "error: --reboot-insmod-diagnostic requires confirmation:" >&2
    echo "$EXPECTED_REBOOT_CONFIRM" >&2
    exit 3
  fi
}

prepare_only() {
  git -C "$REPO_ROOT" diff --check
  bash -n "$0"
  for script in \
    "$REPO_ROOT/scripts/remote/run_c12_3_10_boot_validate_c12_1_9.sh" \
    "$REPO_ROOT/scripts/remote/run_c12_3_11_initramfs_insmod_error_classification.sh" \
    "$REPO_ROOT/scripts/remote/run_c12_3_12_boot_validate_c12_1_10.sh" \
    "$REPO_ROOT/scripts/build/run_c12_1_build_image_lab_readonly.sh"
  do
    if [ -f "$script" ]; then
      bash -n "$script"
    fi
  done
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  {
    printf 'c12_3_13_prepare_only=ok\n'
    printf 'repo_diff_check=ok\n'
    printf 'writer_called=false\n'
    printf 'real_config_written=false\n'
    printf 'wifi_changed=false\n'
    printf 'packages_installed=false\n'
    printf 'poweroff_executed=false\n'
  } > "$OUT_DIR/prepare.env"
  cat "$OUT_DIR/prepare.env"
}

remote_current() {
  ssh_board "python3 -" > "$OUT_DIR/inspect-current.json" <<'PY'
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


def read_text(path, limit=262144):
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
        return text[:limit]
    except Exception:
        return ""


def load_json(path):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def exists(path):
    return pathlib.Path(path).exists()


def service(unit):
    return {
        "active": shell(f"systemctl is-active {unit} 2>/dev/null || true") or "unknown",
        "enabled": shell(f"systemctl is-enabled {unit} 2>/dev/null || true") or "unknown",
        "result": shell(f"systemctl show {unit} -p Result --value 2>/dev/null || true") or "unknown",
        "n_restarts": shell(f"systemctl show {unit} -p NRestarts --value 2>/dev/null || echo 0") or "0",
    }


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
        path = target / ".dadooh-c12-3-13-writable-probe"
        path.write_text("ok\n", encoding="utf-8")
        path.unlink()
        return True
    except Exception:
        return False


def proc_counts():
    counts = {"player": 0, "MPV": 0, "renderer": 0, "setup": 0, "splash": 0}
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmd = (proc / "cmdline").read_bytes().decode("utf-8", "ignore").replace("\0", " ").lower()
        except OSError:
            continue
        if "kiosk.py" in cmd:
            counts["player"] += 1
        if re.search(r"(^|/)mpv(\s|$)", cmd):
            counts["MPV"] += 1
        if "totem_status_renderer" in cmd:
            counts["renderer"] += 1
        if "totem_setup_visual_wizard.py" in cmd:
            counts["setup"] += 1
        if "totem_visual_splash.py" in cmd:
            counts["splash"] += 1
    return counts


def overlay_status():
    allowed = {
        "overlay_load_status",
        "modprobe_rc",
        "insmod_rc",
        "overlay_module_path_found",
        "overlay_module_path_source",
        "overlay_path_found",
        "overlay_in_proc",
        "raw_logs_published",
    }
    status = {}
    path = pathlib.Path("/run/initramfs/dadooh-overlay-load.status")
    if not path.exists():
        return status
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in allowed:
            status[key] = value
    return status


def modinfo_depends():
    text = shell("modinfo -F depends overlay 2>/dev/null || true")
    deps = sorted({item.strip() for item in re.split(r"[,\s]+", text) if item.strip()})
    return deps


kernel = shell("uname -r")
root = mount_info("/")
public = load_json("/tmp/dadooh-status/status.json")
launcher = load_json("/data/state/kiosky-player/launcher-status.json") or load_json("/tmp/kiosky-launcher-status.json")
status = overlay_status()
cmdline = read_text("/proc/cmdline")
armbian_env = read_text("/boot/armbianEnv.txt")
root_read_only = root["source_category"] == "overlay" or root["options_category"] == "ro"
overlay_active = root["source_category"] == "overlay" or root["fstype"] == "overlay"
payload = {
    "schema_version": "dadooh-c12.3.13-current-inspect.v1",
    "board_category": "lab_board",
    "inspect_read_only": True,
    "kernel_version": kernel,
    "public_state": public.get("public_state") or public.get("state") or launcher.get("state", "unknown"),
    "playback": public.get("playback") or public.get("playback_state") or "unknown",
    "services": {
        unit: service(unit)
        for unit in (
            "kiosky-player.service",
            "totem-settings-trigger.service",
            "totem-open-settings.service",
            "dadooh-visual-splash.service",
            "totem-firstboot-gate.service",
            "totem-lab-firstboot-autoconfig.service",
        )
    },
    "systemctl_failed_count": shell("systemctl --failed --no-legend 2>/dev/null | wc -l | tr -d ' '") or "unknown",
    "proc_counts": proc_counts(),
    "session_lock_present": exists("/run/dadooh-settings/session.lock") or exists("/tmp/dadooh-settings/session.lock"),
    "request_present": exists("/run/dadooh-settings/request.json") or exists("/tmp/dadooh-settings/request.json"),
    "config_real_present": exists("/data/config/config.json"),
    "root_mount": root,
    "read_only_enabled": root_read_only,
    "overlay_active": overlay_active,
    "root_write_blocked": root_read_only,
    "data_writable": writable_probe("/data"),
    "tmp_writable": writable_probe("/tmp"),
    "run_writable": writable_probe("/run"),
    "journald_volatile": shell("systemctl cat systemd-journald 2>/dev/null | grep -Eq '^[[:space:]]*Storage=volatile' && echo true || echo false") == "true",
    "cmdline_overlayroot_tmpfs_present": "overlayroot=tmpfs" in cmdline,
    "armbian_env_overlayroot_present": "overlayroot" in armbian_env,
    "overlay_status_present": bool(status),
    "sanitized_overlay_load_status": status,
    "proc_filesystems_contains_overlay_after_boot": bool(re.search(r"(^|\n)nodev\s+overlay(\n|$)", read_text("/proc/filesystems"))),
    "modinfo_overlay_dependencies": modinfo_depends(),
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "packages_installed": False,
    "raw_logs_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/inspect-current.json"
}

install_insmod_hook() {
  require_hook_confirmation
  ssh_board "python3 -" > "$OUT_DIR/install-insmod-diagnostic-hook.json" <<'PY'
import json
import os
import pathlib
import shutil
import subprocess
import time

STATE = pathlib.Path("/data/state/totem-c12-3-13-insmod-diagnostics")
BACKUPS = STATE / "backups"
TS = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
BACKUP_DIR = BACKUPS / f"{TS}-C12-3-13-insmod-diagnostic"
HOOK = pathlib.Path("/etc/initramfs-tools/scripts/init-top/dadooh-c12-3-13-insmod-diagnostic")


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
    HOOK.write_text(r"""#!/bin/sh
PREREQ=""
prereqs() { echo "$PREREQ"; }
case "$1" in
  prereqs) prereqs; exit 0 ;;
esac

OUT="/run/initramfs/dadooh-c12-3-13-insmod-diagnostic.json"
TMPERR="/run/initramfs/dadooh-c12-3-13-insmod.err"
TMPDMESG="/run/initramfs/dadooh-c12-3-13-insmod.dmesg"
mkdir -p /run/initramfs

json_string() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}
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
    echo already_loaded
  elif grep -Eiq 'no such device' "$FILE"; then
    echo no_such_device
  elif grep -Eiq 'required key|key was rejected|signature' "$FILE"; then
    echo signature_key_rejected
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
      if [ -f "$CANDIDATE" ]; then
        printf '%s|modules_dep' "$CANDIDATE"
        return
      fi
    fi
  fi
  CANDIDATE="/lib/modules/$K/kernel/fs/overlayfs/overlay.ko"
  if [ -f "$CANDIDATE" ]; then
    printf '%s|static_fallback' "$CANDIDATE"
    return
  fi
  FOUND="$(find "/lib/modules/$K" -type f \( -name 'overlay.ko' -o -name 'overlay.ko.*' \) 2>/dev/null | head -n 1)"
  if [ -n "$FOUND" ]; then
    printf '%s|find' "$FOUND"
    return
  fi
  printf '|missing'
}

KERNEL="$(uname -r 2>/dev/null || echo unknown)"
OVERLAY_BEFORE="$(contains_overlay)"
MODPROBE_PRESENT=false
INSMOD_PRESENT=false
MODINFO_PRESENT=false
DMESG_PRESENT=false
command -v modprobe >/dev/null 2>&1 && MODPROBE_PRESENT=true
command -v insmod >/dev/null 2>&1 && INSMOD_PRESENT=true
command -v modinfo >/dev/null 2>&1 && MODINFO_PRESENT=true
command -v dmesg >/dev/null 2>&1 && DMESG_PRESENT=true

PATH_AND_SOURCE="$(find_overlay_module "$KERNEL")"
OVERLAY_KO="${PATH_AND_SOURCE%|*}"
OVERLAY_SOURCE="${PATH_AND_SOURCE#*|}"
OVERLAY_KO_EXISTS=false
[ -n "$OVERLAY_KO" ] && [ -f "$OVERLAY_KO" ] && OVERLAY_KO_EXISTS=true
OVERLAY_TYPE="$(file_type_category "$OVERLAY_KO")"
OVERLAY_SIZE_BUCKET="$(size_bucket "$OVERLAY_KO")"
MODULES_DEP="/lib/modules/$KERNEL/modules.dep"
MODULES_DEP_EXISTS=false
[ -r "$MODULES_DEP" ] && MODULES_DEP_EXISTS=true
MODULES_DEP_REFS=false
if [ -r "$MODULES_DEP" ] && grep -q 'overlay\.ko' "$MODULES_DEP" 2>/dev/null; then
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
      NAME="$(basename "$DEP" | sed -E 's/\.ko(\..*)?$//')"
      [ -n "$NAME" ] && DEPS="${DEPS}${NAME},"
      case "$DEP" in
        /lib/modules/*) DEP_ABS="$DEP" ;;
        *) DEP_ABS="/lib/modules/$KERNEL/$DEP" ;;
      esac
      if [ ! -e "$DEP_ABS" ]; then
        DEPS_PRESENT=false
      fi
    done
  fi
fi

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

INSMOD_RC=missing
INSMOD_ATTEMPTED=false
INSMOD_STDERR_CATEGORY=missing
DMESG_CATEGORY=no_message
if [ "$OVERLAY_AFTER_MODPROBE" != true ] && [ "$INSMOD_PRESENT" = true ] && [ "$OVERLAY_KO_EXISTS" = true ]; then
  INSMOD_ATTEMPTED=true
  : > "$TMPERR"
  insmod "$OVERLAY_KO" >/dev/null 2>"$TMPERR"
  INSMOD_RC=$?
  INSMOD_STDERR_CATEGORY="$(stderr_category "$TMPERR")"
  if [ "$DMESG_PRESENT" = true ]; then
    dmesg 2>/dev/null | tail -n 80 > "$TMPDMESG" 2>/dev/null || true
    DMESG_CATEGORY="$(dmesg_category "$TMPDMESG")"
  fi
fi
OVERLAY_AFTER="$(contains_overlay)"
rm -f "$TMPERR" "$TMPDMESG" 2>/dev/null || true

cat > "$OUT" <<EOF
{
  "schema_version": "dadooh-c12.3.13-insmod-diagnostic.v1",
  "overlay_ko_path_resolved": $OVERLAY_KO_EXISTS,
  "overlay_ko_path_source": "$(json_string "$OVERLAY_SOURCE")",
  "overlay_ko_file_type": "$OVERLAY_TYPE",
  "overlay_ko_size_bucket": "$OVERLAY_SIZE_BUCKET",
  "uname_kernel_matches_module_path": $MODULE_PATH_MATCH,
  "vermagic_match": "$VERMAGIC_MATCH",
  "dependencies_detected": "$(json_string "$DEPS")",
  "dependencies_present": "$DEPS_PRESENT",
  "modules_dep_exists": $MODULES_DEP_EXISTS,
  "modules_dep_references_overlay": $MODULES_DEP_REFS,
  "modprobe_present": $MODPROBE_PRESENT,
  "insmod_present": $INSMOD_PRESENT,
  "modprobe_overlay_rc": "$(bucket_rc "$MODPROBE_RC")",
  "modprobe_error_category": "$MODPROBE_STDERR_CATEGORY",
  "overlay_in_proc_before": $OVERLAY_BEFORE,
  "overlay_in_proc_after_modprobe": $OVERLAY_AFTER_MODPROBE,
  "insmod_overlay_attempted": $INSMOD_ATTEMPTED,
  "insmod_overlay_rc": "$(bucket_rc "$INSMOD_RC")",
  "insmod_error_category": "$INSMOD_STDERR_CATEGORY",
  "dmesg_category": "$DMESG_CATEGORY",
  "overlay_in_proc_filesystems_after": $OVERLAY_AFTER,
  "raw_logs_published": false
}
EOF
exit 0
""", encoding="utf-8")
    os.chmod(HOOK, 0o755)


kernel = shell("uname -r")
cycles = current_cycles()
if len(cycles) >= 1:
    raise SystemExit("maximum C12.3.13 diagnostic cycle already reached")
backed = backup_all(kernel)
write_hook()
update = update_initramfs(kernel)
cycles.append({"cycle": 1, "backup_dir": str(BACKUP_DIR), "installed_at": TS})
state = {
    "schema_version": "dadooh-c12.3.13-insmod-diagnostic-state.v1",
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
    listing = shell(f"lsinitramfs /boot/initrd.img-{kernel} 2>/dev/null | grep -F dadooh-c12-3-13-insmod-diagnostic || true", timeout=40)
    hook_in_initrd = bool(listing)

payload = {
    "schema_version": "dadooh-c12.3.13-insmod-diagnostic-install.v1",
    "diagnostic_hook_installed": HOOK.exists(),
    "diagnostic_hook_in_initrd": hook_in_initrd,
    "backup_dir_category": "data_state_totem_c12_3_13_insmod_diagnostics",
    "backups_created": backed,
    "rollback_available": True,
    "cycles_count": len(cycles),
    "hook_path_category": "initramfs_init_top",
}
payload.update(update)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/install-insmod-diagnostic-hook.json"
}

collect_insmod_diagnostic() {
  ssh_board "python3 -" > "$OUT_DIR/insmod-diagnostic.json" <<'PY'
import json
import pathlib
import subprocess


def run(cmd, timeout=15):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=timeout)
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, "", "")


def shell(command, timeout=15):
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
        path = target / ".dadooh-c12-3-13-writable-probe"
        path.write_text("ok\n", encoding="utf-8")
        path.unlink()
        return True
    except Exception:
        return False


def classify(diag):
    if not diag:
        return "UNKNOWN", "READONLY_MECHANISM_DECISION_REOPEN"
    if diag.get("dependencies_present") in {False, "false"}:
        return "OVERLAY_MODULE_DEPENDENCY_MISSING", "C12_1_11_REBUILD_WITH_OVERLAY_DEPENDENCIES"
    if diag.get("vermagic_match") in {False, "false"}:
        return "OVERLAY_MODULE_VERMAGIC_MISMATCH", "KERNEL_MODULE_VERSION_FIX_OR_REBUILD"
    if diag.get("insmod_error_category") == "signature_key_rejected" or diag.get("dmesg_category") == "required_key_missing":
        return "OVERLAY_MODULE_SIGNATURE_REJECTED", "READONLY_MECHANISM_DECISION_REOPEN"
    if diag.get("insmod_error_category") == "invalid_module_format" or diag.get("dmesg_category") in {"invalid_module_format", "disagrees_about_version", "module_layout_mismatch"}:
        return "OVERLAY_MODULE_INVALID_FORMAT", "UNCOMPRESS_OR_LOAD_MODULE_CORRECTLY_IN_INITRAMFS"
    if diag.get("insmod_error_category") == "unknown_symbol" or diag.get("dmesg_category") == "unknown_symbol":
        return "OVERLAY_INSMOD_UNKNOWN_SYMBOL", "INCLUDE_MISSING_SYMBOL_DEPENDENCIES"
    if diag.get("insmod_error_category") == "file_not_found" or diag.get("overlay_ko_path_resolved") is False:
        return "OVERLAY_MODULE_PATH_MISMATCH", "C12_1_11_REBUILD_WITH_EFFECTIVE_MODULE_PATH"
    if diag.get("modprobe_overlay_rc") == "zero" and diag.get("overlay_in_proc_after_modprobe") is False:
        if diag.get("insmod_overlay_rc") == "nonzero":
            return "OVERLAY_INSMOD_OTHER", "C12_3_14_READONLY_MECHANISM_DECISION"
    return "UNKNOWN", "READONLY_MECHANISM_DECISION_REOPEN"


diag = load_json("/run/initramfs/dadooh-c12-3-13-insmod-diagnostic.json")
root = mount_info("/")
read_only_enabled = root["source_category"] == "overlay" or root["options_category"] == "ro"
overlay_active = root["source_category"] == "overlay" or root["fstype"] == "overlay"
cause, next_step = classify(diag)
payload = {
    "schema_version": "dadooh-c12.3.13-insmod-diagnostic-result.v1",
    "diagnostic_collected": bool(diag),
    "hook_installed": pathlib.Path("/etc/initramfs-tools/scripts/init-top/dadooh-c12-3-13-insmod-diagnostic").exists(),
    "reboot_executed": True,
    "overlay_ko_path_resolved": diag.get("overlay_ko_path_resolved", "unknown"),
    "overlay_ko_file_type": diag.get("overlay_ko_file_type", "unknown"),
    "overlay_ko_size_bucket": diag.get("overlay_ko_size_bucket", "unknown"),
    "uname_kernel_matches_module_path": diag.get("uname_kernel_matches_module_path", "unknown"),
    "vermagic_match": diag.get("vermagic_match", "unknown"),
    "dependencies_detected": diag.get("dependencies_detected", ""),
    "dependencies_present": diag.get("dependencies_present", "unknown"),
    "modules_dep_exists": diag.get("modules_dep_exists", "unknown"),
    "modules_dep_references_overlay": diag.get("modules_dep_references_overlay", "unknown"),
    "modprobe_overlay_rc": diag.get("modprobe_overlay_rc", "unknown"),
    "modprobe_error_category": diag.get("modprobe_error_category", "unknown"),
    "overlay_in_proc_after_modprobe": diag.get("overlay_in_proc_after_modprobe", "unknown"),
    "insmod_overlay_attempted": diag.get("insmod_overlay_attempted", "unknown"),
    "insmod_overlay_rc": diag.get("insmod_overlay_rc", "unknown"),
    "insmod_error_category": diag.get("insmod_error_category", "unknown"),
    "dmesg_category": diag.get("dmesg_category", "unknown"),
    "overlay_in_proc_filesystems_after": diag.get("overlay_in_proc_filesystems_after", "unknown"),
    "read_only_enabled": read_only_enabled,
    "overlay_active": overlay_active,
    "root_write_blocked": read_only_enabled,
    "data_writable": writable_probe("/data"),
    "tmp_writable": writable_probe("/tmp"),
    "run_writable": writable_probe("/run"),
    "systemctl_failed_count": shell("systemctl --failed --no-legend 2>/dev/null | wc -l | tr -d ' '") or "unknown",
    "cause_category": cause,
    "recommended_next_step_readonly": next_step,
    "raw_logs_published": False,
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/insmod-diagnostic.json"
}

reboot_insmod_diagnostic() {
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
    cat > "$OUT_DIR/reboot-insmod-diagnostic.json" <<'JSON'
{
  "schema_version": "dadooh-c12.3.13-reboot.v1",
  "reboot_executed": true,
  "ssh_returned": false,
  "offline_recovery_required": true
}
JSON
    cat "$OUT_DIR/reboot-insmod-diagnostic.json"
    return 4
  fi
  collect_insmod_diagnostic
  python3 - "$OUT_DIR/insmod-diagnostic.json" > "$OUT_DIR/reboot-insmod-diagnostic.json" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
payload = {
    "schema_version": "dadooh-c12.3.13-reboot.v1",
    "reboot_executed": True,
    "ssh_returned": True,
    "read_only_enabled": data.get("read_only_enabled"),
    "overlay_active": data.get("overlay_active"),
    "root_write_blocked": data.get("root_write_blocked"),
    "insmod_error_category": data.get("insmod_error_category"),
    "dmesg_category": data.get("dmesg_category"),
    "cause_category": data.get("cause_category"),
    "recommended_next_step_readonly": data.get("recommended_next_step_readonly"),
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/reboot-insmod-diagnostic.json"
  cat "$OUT_DIR/reboot-insmod-diagnostic.json"
}

triage_visual() {
  ssh_board "python3 -" > "$OUT_DIR/visual-triage.json" <<'PY'
import json
import pathlib
import re
import subprocess
import xml.etree.ElementTree as ET


def run(cmd, timeout=20):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=timeout)
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, "", "")


def shell(command, timeout=20):
    return (run(["sh", "-lc", command], timeout=timeout).stdout or "").strip()


def read_text(path, limit=262144):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def load_json(path):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def bucket_size(path):
    try:
        size = pathlib.Path(path).stat().st_size
    except OSError:
        return "missing"
    if size == 0:
        return "empty"
    if size < 4096:
        return "small"
    if size < 1048576:
        return "medium"
    return "large"


def proc_categories():
    categories = []
    counts = {"player": 0, "MPV": 0, "renderer": 0, "setup": 0, "splash": 0}
    mpv_cmd = ""
    renderer_cmd = ""
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmd = (proc / "cmdline").read_bytes().decode("utf-8", "ignore").replace("\0", " ")
        except OSError:
            continue
        lowered = cmd.lower()
        if "kiosk.py" in lowered:
            counts["player"] += 1
        if re.search(r"(^|/)mpv(\s|$)", lowered):
            counts["MPV"] += 1
            mpv_cmd = cmd
        if "totem_status_renderer" in lowered:
            counts["renderer"] += 1
            renderer_cmd = cmd
        if "totem_setup_visual_wizard.py" in lowered:
            counts["setup"] += 1
        if "totem_visual_splash.py" in lowered:
            counts["splash"] += 1
    if "--vo=drm" in mpv_cmd or " vo=drm" in mpv_cmd:
        categories.append("mpv_vo_drm")
    elif "--vo=gpu" in mpv_cmd or " vo=gpu" in mpv_cmd:
        categories.append("mpv_vo_gpu")
    elif mpv_cmd:
        categories.append("mpv_vo_unknown")
    if "/tmp/dadooh-status" in renderer_cmd:
        categories.append("renderer_status_path_tmp")
    elif renderer_cmd:
        categories.append("renderer_path_unknown")
    return counts, sorted(set(categories))


def svg_info(path):
    p = pathlib.Path(path)
    text = read_text(path)
    valid = False
    width = "unknown"
    height = "unknown"
    viewbox = "unknown"
    try:
        root = ET.fromstring(text)
        valid = root.tag.endswith("svg")
        width = root.attrib.get("width", "unknown")
        height = root.attrib.get("height", "unknown")
        viewbox = root.attrib.get("viewBox", "unknown")
    except Exception:
        pass
    lowered = text.lower()
    contains_visible_text = any(token in lowered for token in ("config", "dadooh", "totem", "configur"))
    style_black_canvas = "fill=\"#000" in lowered or "fill: #000" in lowered or "fill:black" in lowered
    return {
        "exists": p.exists(),
        "size_bucket": bucket_size(path),
        "mtime_present": p.exists(),
        "valid_svg": valid,
        "contains_visible_text": contains_visible_text,
        "canvas_width_category": "present" if width != "unknown" else "unknown",
        "canvas_height_category": "present" if height != "unknown" else "unknown",
        "viewbox_present": viewbox != "unknown",
        "black_canvas_style_seen": style_black_canvas,
    }


def classify(public_state, svg, counts, cmd_categories):
    if public_state != "config_missing":
        return "UNKNOWN"
    if not svg["exists"] or not svg["valid_svg"]:
        return "SVG_VALID_BUT_NOT_PRESENTED_BY_MPV"
    if counts["MPV"] > 0 and counts["renderer"] > 0 and "mpv_vo_drm" in cmd_categories:
        return "MPV_ACTIVE_BUT_NO_DRM_FRAME"
    if counts["MPV"] > 0 and counts["renderer"] > 0:
        return "SVG_VALID_BUT_NOT_PRESENTED_BY_MPV"
    if counts["renderer"] > 0 and counts["MPV"] == 0:
        return "SVG_VALID_BUT_NOT_PRESENTED_BY_MPV"
    if svg["black_canvas_style_seen"] and not svg["contains_visible_text"]:
        return "BLACK_CANVAS_OR_STYLE_BUG"
    return "UNKNOWN"


public = load_json("/tmp/dadooh-status/status.json")
launcher = load_json("/data/state/kiosky-player/launcher-status.json") or load_json("/tmp/kiosky-launcher-status.json")
public_state = public.get("public_state") or public.get("state") or launcher.get("state", "unknown")
counts, cmd_categories = proc_categories()
svg = svg_info("/tmp/dadooh-status/status.svg")
tty_active = shell("fgconsole 2>/dev/null || true")
display_connected = shell("for s in /sys/class/drm/*/status; do [ -r \"$s\" ] && printf '%s\\n' \"$(cat \"$s\")\"; done 2>/dev/null | sort -u | tr '\\n' ',' || true")
payload = {
    "schema_version": "dadooh-c12.3.13-config-missing-visual-triage.v1",
    "board_category": "lab_board",
    "public_state": public_state,
    "playback": public.get("playback") or public.get("playback_state") or "unknown",
    "status_svg": svg,
    "process_counts": counts,
    "process_command_categories": cmd_categories,
    "drm_status_category": "connected_present" if "connected" in display_connected else ("disconnected_or_unknown" if display_connected else "unknown"),
    "active_tty_category": "tty_present" if tty_active else "unknown",
    "getty_visible_active": shell("systemctl is-active getty@tty1.service 2>/dev/null || true") == "active",
    "renderer_target_category": "tmp_status_svg" if "renderer_status_path_tmp" in cmd_categories else "unknown",
    "mpv_vo_context_category": "drm" if "mpv_vo_drm" in cmd_categories else ("gpu" if "mpv_vo_gpu" in cmd_categories else "unknown"),
    "visual_black_screen_category": classify(public_state, svg, counts, cmd_categories),
    "raw_logs_published": False,
    "screenshot_saved": False,
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/visual-triage.json"
}

rollback_hook() {
  ssh_board "python3 -" > "$OUT_DIR/rollback-diagnostic-hook.json" <<'PY'
import json
import os
import pathlib
import shutil
import subprocess

STATE = pathlib.Path("/data/state/totem-c12-3-13-insmod-diagnostics")
HOOK = pathlib.Path("/etc/initramfs-tools/scripts/init-top/dadooh-c12-3-13-insmod-diagnostic")


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
    "schema_version": "dadooh-c12.3.13-insmod-diagnostic-rollback.v1",
    "rollback_executed": True,
    "backup_dir_category": "data_state_totem_c12_3_13_insmod_diagnostics" if backup_dir else "missing",
    "restored": restored,
    "diagnostic_hook_present_after": HOOK.exists(),
    "update_initramfs_returncode": update.returncode,
    "update_initramfs_ok": update.returncode == 0,
}
payload.update(regen)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/rollback-diagnostic-hook.json"
}

summary() {
  python3 - "$OUT_DIR" <<'PY'
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
for name in ("insmod-diagnostic.json", "visual-triage.json", "inspect-current.json"):
    path = root / name
    if not path.exists():
        continue
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"[{name}]")
    for key in (
        "public_state",
        "read_only_enabled",
        "overlay_active",
        "root_write_blocked",
        "insmod_error_category",
        "dmesg_category",
        "cause_category",
        "recommended_next_step_readonly",
        "visual_black_screen_category",
    ):
        if key in data:
            print(f"{key}={data[key]}")
PY
}

case "$MODE" in
  prepare-only) prepare_only ;;
  inspect-current) remote_current; cat "$OUT_DIR/inspect-current.json" ;;
  install-insmod-diagnostic-hook) install_insmod_hook; cat "$OUT_DIR/install-insmod-diagnostic-hook.json" ;;
  reboot-insmod-diagnostic) reboot_insmod_diagnostic ;;
  collect-insmod-diagnostic) collect_insmod_diagnostic; cat "$OUT_DIR/insmod-diagnostic.json" ;;
  triage-config-missing-visual) triage_visual; cat "$OUT_DIR/visual-triage.json" ;;
  rollback-diagnostic-hook) rollback_hook; cat "$OUT_DIR/rollback-diagnostic-hook.json" ;;
  summary) summary ;;
esac
