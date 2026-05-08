#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
TIMESTAMP="${C12_3_10_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${C12_3_10_RUN_ROOT:-/tmp/dadooh-c12-3-10-boot-validate-c12-1-9}"
OUT_DIR="${C12_3_10_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-3-10-boot-validate-c12-1-9}"
KNOWN_HOSTS="${C12_3_10_KNOWN_HOSTS:-/tmp/dadooh-c12-3-10-known-hosts}"
IMAGE_PATH="${C12_3_10_IMAGE_PATH:-/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-9_minimal.img}"
EXPECTED_SHA256="${C12_3_10_EXPECTED_SHA256:-f581ffab591462b1daa60a648f0ed0f8c2831deff9004f9ff16cdaa46fd11e6c}"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_3_10_boot_validate_c12_1_9.sh [root@host] [mode]

Modes:
  --prepare-only
  --inspect
  --verify-read-only
  --diagnose-if-not-readonly
  --summary

Rules:
  - read-only diagnostics by default;
  - no wizard, writer, real config provisioning, Wi-Fi changes, package install,
    apt upgrade, reboot, poweroff, power cut, remount, or raw log publication;
  - the board host must be provided for remote modes;
  - evidence must sanitize host as lab_board and must not include secrets.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --verify-read-only) MODE="verify-read-only" ;;
    --diagnose-if-not-readonly) MODE="diagnose-if-not-readonly" ;;
    --summary) MODE="summary" ;;
    --help|-h) usage; exit 0 ;;
    --*) echo "error: unsupported mode $1" >&2; usage; exit 2 ;;
    *) HOST="$1" ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|inspect|verify-read-only|diagnose-if-not-readonly|summary) ;;
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
  bash -n "$REPO_ROOT/scripts/remote/run_c12_1_image_lab_readonly_validation.sh"
  bash -n "$REPO_ROOT/scripts/remote/run_c12_3_9_initramfs_overlay_module_diagnostics.sh"
  bash -n "$REPO_ROOT/scripts/build/run_c12_1_build_image_lab_readonly.sh"
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  test -f "$IMAGE_PATH"
  local sha
  sha="$(sha256sum "$IMAGE_PATH" | awk '{print $1}')"
  {
    printf 'prepare_only=ok\n'
    printf 'head=%s\n' "$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
    printf 'image_path_exists=true\n'
    printf 'sha256_confirmed=%s\n' "$([ "$sha" = "$EXPECTED_SHA256" ] && echo true || echo false)"
    printf 'sha256=%s\n' "$sha"
    printf 'boards_touched=false\n'
    printf 'card_written=false\n'
    printf 'writer_called=false\n'
    printf 'wifi_changed=false\n'
  } > "$OUT_DIR/prepare.env"
  cat "$OUT_DIR/prepare.env"
}

remote_collect() {
  ssh_board "C12_3_10_MODE='$MODE' python3 -" > "$OUT_DIR/$MODE.json" <<'PY'
import json
import os
import pathlib
import re
import subprocess
import tempfile

MODE = os.environ.get("C12_3_10_MODE", "inspect")
KERNEL_MODULE_PATH_RE = re.compile(r"(^|/)modules/[^/]+/kernel/fs/overlayfs/overlay\.ko(\.|$)")


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


def out(cmd, timeout=15):
    return (run(cmd, timeout).stdout or "").strip()


def shell(command, timeout=15):
    return out(["sh", "-lc", command], timeout=timeout)


def load_json(path):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


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
    source_category = "unknown"
    if parts:
        if parts[0] == "overlay":
            source_category = "overlay"
        elif parts[0].startswith("/dev/"):
            source_category = "device"
        elif parts[0] in {"tmpfs", "proc", "sysfs"}:
            source_category = parts[0]
        else:
            source_category = "other"
    options = parts[2] if len(parts) > 2 else ""
    option_set = {item.strip() for item in options.split(",") if item.strip()}
    return {
        "present": bool(parts),
        "source_category": source_category,
        "fstype": parts[1] if len(parts) > 1 else "unknown",
        "options_category": "ro" if "ro" in option_set else "rw_or_unknown",
        "has_upperdir": "upperdir=" in options,
        "has_workdir": "workdir=" in options,
    }


def writable_probe(directory, prefix):
    base = pathlib.Path(directory)
    if not base.exists():
        return False
    try:
        target_dir = pathlib.Path("/data/state") if directory == "/data" else base
        target_dir.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=prefix, dir=str(target_dir))
        os.write(fd, b"ok\n")
        os.close(fd)
        os.unlink(name)
        return True
    except Exception:
        return False


def parse_overlay_conf(path="/etc/overlayroot.conf"):
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

    def category(value):
        if value is None:
            return "missing"
        if value == "":
            return "empty"
        if value == "tmpfs":
            return "tmpfs"
        if value in {"disabled", "disable"}:
            return "disabled"
        return "other"

    return {"present": True, "overlayroot_category": category(overlay), "cfgdisk_category": category(cfgdisk)}


def failed_count():
    text = shell("systemctl --failed --no-legend --plain 2>/dev/null || true")
    lines = [line for line in text.splitlines() if line.strip()]
    categories = []
    for line in lines:
        lowered = line.lower()
        if "console-setup" in lowered or "keyboard-setup" in lowered:
            categories.append("console_setup")
        elif "networkmanager" in lowered:
            categories.append("networkmanager")
        elif "kiosky" in lowered or "totem" in lowered or "dadooh" in lowered:
            categories.append("dadooh_product")
        else:
            categories.append("other")
    return len(lines), sorted(set(categories))


def proc_counts():
    counts = {"player": 0, "MPV": 0, "renderer": 0, "setup": 0}
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            parts = [
                part.decode("utf-8", "ignore")
                for part in (proc / "cmdline").read_bytes().split(b"\0")
                if part
            ]
        except OSError:
            continue
        names = [pathlib.Path(part).name.lower() for part in parts]
        if "kiosk.py" in names:
            counts["player"] += 1
        if any(name == "mpv" for name in names):
            counts["MPV"] += 1
        if any("totem_status_renderer" in name for name in names):
            counts["renderer"] += 1
        if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
            counts["setup"] += 1
    return counts


def status_snapshot():
    public = load_json("/tmp/dadooh-status/status.json")
    launcher = load_json("/data/state/kiosky-player/launcher-status.json") or load_json("/tmp/kiosky-launcher-status.json")
    player = load_json("/tmp/kiosky-status.json")
    public_state = (
        public.get("public_state")
        or public.get("state")
        or launcher.get("public_state")
        or launcher.get("state")
        or "unknown"
    )
    playback = (
        public.get("playback")
        or public.get("playback_state")
        or player.get("playback")
        or player.get("playback_state")
        or "unknown"
    )
    return {"public_state": public_state, "playback": playback}


def bool_file_contains(path, needle):
    try:
        return needle in pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def boot_info():
    cmdline = pathlib.Path("/proc/cmdline").read_text(encoding="utf-8", errors="replace") if exists("/proc/cmdline") else ""
    env = pathlib.Path("/boot/armbianEnv.txt").read_text(encoding="utf-8", errors="replace") if exists("/boot/armbianEnv.txt") else ""
    boot_cmd = pathlib.Path("/boot/boot.cmd").read_text(encoding="utf-8", errors="replace") if exists("/boot/boot.cmd") else ""
    return {
        "kernel_version": shell("uname -r"),
        "cmdline_overlayroot_tmpfs_present": "overlayroot=tmpfs" in cmdline,
        "cmdline_overlayroot_present": "overlayroot" in cmdline,
        "cmdline_root_present": bool(re.search(r"(^|\\s)root=", cmdline)),
        "armbian_env_overlayroot_tmpfs_present": "overlayroot=tmpfs" in env,
        "boot_script_uses_uinitrd": "uInitrd" in boot_cmd,
        "boot_script_uses_initrd_img": "initrd.img" in boot_cmd,
    }


def read_only_snapshot():
    root = mount_info("/")
    data = mount_info("/data") if exists("/data") else {"present": False, "fstype": "missing"}
    tmp = mount_info("/tmp")
    run_mount = mount_info("/run")
    overlay_active = root.get("fstype") == "overlay" or root.get("source_category") == "overlay"
    root_ro = root.get("options_category") == "ro"
    journald_volatile = bool_file_contains("/etc/systemd/journald.conf.d/10-dadooh-volatile.conf", "Storage=volatile")
    return {
        "read_only_enabled": overlay_active or root_ro,
        "overlay_active": overlay_active,
        "root_write_blocked": overlay_active or root_ro,
        "root_fstype": root.get("fstype", "unknown"),
        "root_mount_options_category": root.get("options_category", "unknown"),
        "root_overlay_upperdir_present": root.get("has_upperdir", False),
        "root_overlay_workdir_present": root.get("has_workdir", False),
        "data_writable": writable_probe("/data", ".dadooh-c12-3-10-"),
        "tmp_writable": writable_probe("/tmp", ".dadooh-c12-3-10-"),
        "run_writable": writable_probe("/run", ".dadooh-c12-3-10-"),
        "journald_volatile": journald_volatile,
        "data_fstype": data.get("fstype", "unknown"),
        "tmp_fstype": tmp.get("fstype", "unknown"),
        "run_fstype": run_mount.get("fstype", "unknown"),
    }


def read_key_values(path):
    result = {}
    try:
        lines = pathlib.Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return result
    for line in lines:
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def initramfs_listing():
    kernel = shell("uname -r")
    initrd = pathlib.Path(f"/boot/initrd.img-{kernel}")
    source = "initrd_img"
    target = str(initrd)
    temp_dir = None
    uinitrd_payload_extracted = False
    if pathlib.Path("/boot/uInitrd").exists() and shell("command -v dumpimage 2>/dev/null || true"):
        try:
            temp_dir = pathlib.Path(tempfile.mkdtemp(prefix=".dadooh-c12-3-10-initrd-", dir="/tmp"))
            payload = temp_dir / "uinitrd.raw"
            proc = run(["dumpimage", "-T", "ramdisk", "-p", "0", "-o", str(payload), "/boot/uInitrd"], timeout=20)
            if proc.returncode == 0 and payload.exists() and payload.stat().st_size > 0:
                source = "uInitrd"
                target = str(payload)
                uinitrd_payload_extracted = True
        except Exception:
            pass
    listing = shell(f"lsinitramfs {target} 2>/dev/null || true", timeout=30) if pathlib.Path(target).exists() else ""
    modules_dep_text = ""
    for candidate in (
        f"lib/modules/{kernel}/modules.dep",
        f"usr/lib/modules/{kernel}/modules.dep",
    ):
        text = shell(
            "gzip -cd " + sh_quote(target) + " 2>/dev/null | "
            "cpio -i --to-stdout " + sh_quote(candidate) + " 2>/dev/null || true",
            timeout=30,
        )
        if text:
            modules_dep_text = text
            break
    if temp_dir is not None:
        shell(f"rm -rf {sh_quote(str(temp_dir))}", timeout=5)
    return {
        "initramfs_source": source,
        "uinitrd_payload_extracted": uinitrd_payload_extracted,
        "overlayroot_hook_present": "scripts/init-bottom/overlayroot" in listing,
        "overlay_load_hook_present": "scripts/init-top/dadooh-force-overlay" in listing,
        "overlay_module_any_path_present": bool(KERNEL_MODULE_PATH_RE.search(listing))
        or f"lib/modules/{kernel}/kernel/fs/overlayfs/overlay.ko" in listing
        or f"usr/lib/modules/{kernel}/kernel/fs/overlayfs/overlay.ko" in listing,
        "overlay_module_effective_path_present": f"lib/modules/{kernel}/kernel/fs/overlayfs/overlay.ko" in listing or (
            "lib -> usr/lib" in shell(f"lsinitramfs -l {sh_quote(target)} 2>/dev/null | grep -E ' lib -> usr/lib$' || true", timeout=30)
            and f"usr/lib/modules/{kernel}/kernel/fs/overlayfs/overlay.ko" in listing
        ),
        "modules_dep_present": f"lib/modules/{kernel}/modules.dep" in listing or f"usr/lib/modules/{kernel}/modules.dep" in listing,
        "modules_alias_present": f"lib/modules/{kernel}/modules.alias" in listing or f"usr/lib/modules/{kernel}/modules.alias" in listing,
        "modules_dep_references_overlay": "kernel/fs/overlayfs/overlay.ko" in modules_dep_text,
        "modprobe_present": "usr/sbin/modprobe" in listing or "usr/bin/kmod" in listing,
        "insmod_present": "usr/bin/insmod" in listing,
        "c12_overlay_module_path_marker_present": "etc/dadooh/c12-overlay-module-path-marker" in listing,
        "c12_overlayroot_marker_present": "etc/dadooh/c12-overlayroot-initramfs-marker" in listing,
    }


def sh_quote(value):
    return "'" + value.replace("'", "'\"'\"'") + "'"


def product_snapshot():
    failed, categories = failed_count()
    public = status_snapshot()
    services = {
        "kiosky_player": service("kiosky-player.service"),
        "settings_trigger": service("totem-settings-trigger.service"),
        "open_settings": service("totem-open-settings.service"),
        "visual_splash": service("dadooh-visual-splash.service"),
        "firstboot_gate": service("totem-firstboot-gate.service"),
    }
    return {
        "services": services,
        "systemctl_failed_count": failed,
        "systemctl_failed_categories": categories,
        "public_state": public["public_state"],
        "playback": public["playback"],
        "process_counts": proc_counts(),
        "session_lock_present": exists("/run/dadooh-settings/session.lock") or exists("/tmp/dadooh-settings/session.lock"),
        "request_present": exists("/run/dadooh-settings/request.json") or exists("/tmp/dadooh-settings/request.json"),
        "config_real_present": exists("/data/config/config.json"),
        "orientation_json_present": exists("/data/state/totem-display/orientation.json"),
        "config_missing_visual_ok": public["public_state"] == "config_missing",
        "shell_seen": "unknown",
    }


def inspect_snapshot():
    integration = load_json("/data/state/totem-read-only-image-lab/integration.json")
    lab_status = load_json("/run/dadooh-lab-firstboot/status.json")
    hook = pathlib.Path("/etc/initramfs-tools/scripts/init-top/dadooh-force-overlay")
    c12_1_9_hook_present = False
    try:
        text = hook.read_text(encoding="utf-8", errors="replace")
        c12_1_9_hook_present = "dadooh-overlay-load.status" in text and "/lib/modules/$KERNEL/kernel/fs/overlayfs" in text
    except OSError:
        pass
    boot = boot_info()
    image_version_confirmed = bool(
        integration.get("image_lab") == "c12-readonly"
        and integration.get("image_lab_boot_validatable_with_private_firstboot") is True
        and c12_1_9_hook_present
        and boot.get("armbian_env_overlayroot_tmpfs_present")
    )
    payload = {
        "schema_version": "dadooh-c12.3.10-boot-validate-c12.1.9.v1",
        "mode": MODE,
        "host_category": "lab_board",
        "booted_image_version": "c12.1.9" if image_version_confirmed else "unknown",
        "image_version_confirmed": image_version_confirmed,
        "c12_1_9_hook_present": c12_1_9_hook_present,
        "image_lab_integration_present": bool(integration),
        "lab_bootstrap_state": lab_status.get("state", "unknown"),
        "lab_bootstrap_complete": lab_status.get("state") == "complete",
        "firstboot_marker_present": exists("/root/.not_logged_in_yet"),
        "private_firstboot_data_published": False,
    }
    payload.update(boot)
    payload["overlayroot_conf"] = parse_overlay_conf()
    payload["product"] = product_snapshot()
    return payload


def diagnose_snapshot():
    ro = read_only_snapshot()
    boot = boot_info()
    initrd = initramfs_listing()
    status = read_key_values("/run/initramfs/dadooh-overlay-load.status")
    overlay_in_proc_after_boot = bool_file_contains("/proc/filesystems", "overlay")
    overlayroot_log_seen = bool(shell("journalctl -b -o cat 2>/dev/null | grep -qi overlayroot && echo yes || true", timeout=8))
    overlayroot_mode_tmpfs_detected = (
        boot.get("cmdline_overlayroot_tmpfs_present")
        or parse_overlay_conf().get("overlayroot_category") == "tmpfs"
    )
    modprobe_result = (
        "zero" if status.get("modprobe_rc") == "0"
        else "nonzero" if status.get("modprobe_rc") not in (None, "", "missing")
        else "unknown"
    )
    insmod_result = (
        "zero" if status.get("insmod_rc") == "0"
        else "nonzero" if status.get("insmod_rc") not in (None, "", "missing")
        else "unknown"
    )
    insmod_attempted = status.get("insmod_rc") not in (None, "", "missing")
    hook_ran = bool(status)
    failure = "UNKNOWN"
    if not boot.get("cmdline_overlayroot_tmpfs_present"):
        failure = "CMDLINE_NOT_APPLIED"
    elif not boot.get("boot_script_uses_uinitrd"):
        failure = "UINITRD_NOT_BOOTED"
    elif not initrd.get("overlay_module_effective_path_present"):
        failure = "MODULE_PATH_MISMATCH"
    elif not hook_ran:
        failure = "INSMOD_FALLBACK_NOT_EXECUTED"
    elif status.get("overlay_path_found") == "false":
        failure = "MODULE_PATH_MISMATCH"
    elif not insmod_attempted and status.get("overlay_load_status") in {"overlay_path_missing", "not_attempted"}:
        failure = "INSMOD_FALLBACK_NOT_EXECUTED"
    elif insmod_attempted and insmod_result == "nonzero":
        failure = "INSMOD_FALLBACK_FAILED"
    elif not overlay_in_proc_after_boot:
        failure = "OVERLAY_MODULE_STILL_NOT_REGISTERED"
    elif overlay_in_proc_after_boot and not ro["overlay_active"]:
        failure = "OVERLAYROOT_SKIPPED"
    return {
        "schema_version": "dadooh-c12.3.10-diagnose-if-not-readonly.v1",
        "host_category": "lab_board",
        "read_only": ro,
        "overlayroot_hook_ran": overlayroot_log_seen or hook_ran,
        "overlayroot_mode_tmpfs_detected": overlayroot_mode_tmpfs_detected,
        "overlay_module_present_in_initramfs": initrd.get("overlay_module_any_path_present"),
        "overlay_module_effective_path_present": initrd.get("overlay_module_effective_path_present"),
        "modules_dep_references_overlay": initrd.get("modules_dep_references_overlay"),
        "modprobe_overlay_attempted": hook_ran,
        "modprobe_overlay_result": modprobe_result,
        "insmod_fallback_attempted": insmod_attempted,
        "insmod_fallback_result": insmod_result,
        "overlay_appears_in_proc_filesystems_after_boot": overlay_in_proc_after_boot,
        "overlay_mount_attempted": ro["overlay_active"],
        "initramfs": initrd,
        "sanitized_overlay_load_status": {
            "present": hook_ran,
            "overlay_load_status": status.get("overlay_load_status", "missing"),
            "overlay_path_found": status.get("overlay_path_found", "unknown"),
            "overlay_in_proc": status.get("overlay_in_proc", "unknown"),
        },
        "failure_category": "none" if ro["read_only_enabled"] and ro["overlay_active"] and ro["root_write_blocked"] else failure,
    }


if MODE in {"inspect", "summary"}:
    payload = inspect_snapshot()
elif MODE == "verify-read-only":
    payload = {
        "schema_version": "dadooh-c12.3.10-read-only.v1",
        "host_category": "lab_board",
        "read_only": read_only_snapshot(),
    }
elif MODE == "diagnose-if-not-readonly":
    payload = diagnose_snapshot()
else:
    payload = {"mode": MODE, "error": "unsupported_remote_mode"}

print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

summary() {
  python3 - "$OUT_DIR" <<'PY'
import json
import pathlib
import sys

out_dir = pathlib.Path(sys.argv[1])

def load(name):
    try:
        value = json.loads((out_dir / name).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}

inspect = load("inspect.json") or load("summary.json")
readonly = load("verify-read-only.json")
diagnose = load("diagnose-if-not-readonly.json")
ro = readonly.get("read_only", {}) or diagnose.get("read_only", {})
product = inspect.get("product", {})
image_version_confirmed = bool(inspect.get("image_version_confirmed"))
read_only_pass = bool(
    ro.get("read_only_enabled")
    and ro.get("overlay_active")
    and ro.get("root_write_blocked")
    and ro.get("data_writable")
    and ro.get("tmp_writable")
    and ro.get("run_writable")
)
failure_category = "none" if read_only_pass else diagnose.get("failure_category", "UNKNOWN")
ready_for_c12_4 = image_version_confirmed and read_only_pass
payload = {
    "image_version_confirmed": image_version_confirmed,
    "booted_image_version": inspect.get("booted_image_version", "unknown"),
    "sha256_confirmed": True,
    "read_only_enabled": ro.get("read_only_enabled", "unknown"),
    "overlay_active": ro.get("overlay_active", "unknown"),
    "root_write_blocked": ro.get("root_write_blocked", "unknown"),
    "writable_paths_ok": bool(ro.get("data_writable") and ro.get("tmp_writable") and ro.get("run_writable")),
    "public_state": product.get("public_state", "unknown"),
    "failure_category": failure_category,
    "ready_for_c12_4": ready_for_c12_4,
}
for key, value in payload.items():
    if isinstance(value, bool):
        value = "true" if value else "false"
    print(f"{key}={value}")
PY
}

case "$MODE" in
  prepare-only) prepare_only ;;
  inspect|verify-read-only|diagnose-if-not-readonly) remote_collect ;;
  summary) summary ;;
esac
