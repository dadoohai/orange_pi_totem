#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
TIMESTAMP="${C12_3_17_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${C12_3_17_RUN_ROOT:-/tmp/dadooh-c12-3-17-boot-validate-overlayfs-builtin}"
OUT_DIR="${C12_3_17_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-3-17-boot-validate-overlayfs-builtin}"
KNOWN_HOSTS="${C12_3_17_KNOWN_HOSTS:-/tmp/dadooh-c12-3-17-known-hosts}"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_3_17_boot_validate_overlayfs_builtin.sh [root@host] [mode]

Modes:
  --prepare-only
  --inspect
  --persistence-test
  --post-reboot
  --summary

Rules:
  - --inspect is read-only and must not alter the board;
  - --persistence-test creates synthetic timestamped markers and runs one
    controlled systemctl reboot only when overlay is active;
  - --post-reboot validates marker persistence after that controlled reboot;
  - never call writer, change Wi-Fi/NetworkManager, install packages, run apt,
    poweroff, power cut, publish secrets, or read real config contents.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --persistence-test) MODE="persistence-test" ;;
    --post-reboot) MODE="post-reboot" ;;
    --summary) MODE="summary" ;;
    --help|-h) usage; exit 0 ;;
    --*) echo "error: unsupported mode $1" >&2; usage; exit 2 ;;
    *) HOST="$1" ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|inspect|persistence-test|post-reboot|summary) ;;
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
  bash -n "$REPO_ROOT/scripts/build/run_c12_1_build_image_lab_readonly.sh"
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_config_contract_validate.py" --self-test >/dev/null
  {
    printf 'c12_3_17_prepare_only=ok\n'
    printf 'boards_touched=false\n'
    printf 'ssh_used=false\n'
    printf 'writer_called=false\n'
    printf 'apt_update_executed=false\n'
    printf 'apt_upgrade_executed=false\n'
    printf 'poweroff_executed=false\n'
  } > "$OUT_DIR/prepare.env"
  cat "$OUT_DIR/prepare.env"
}

remote_python() {
  ssh_board "C12_3_17_MODE='$MODE' python3 -" > "$OUT_DIR/$MODE.json" <<'PY'
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

MODE = os.environ.get("C12_3_17_MODE", "inspect")


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


def read_text(path, limit=20000):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def load_json(path):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def bool_path(path):
    return pathlib.Path(path).exists()


def mount_info(target):
    text = shell(f"findmnt -n -o SOURCE,FSTYPE,OPTIONS --target {target} 2>/dev/null || true")
    parts = text.split(None, 2)
    options = parts[2] if len(parts) > 2 else ""
    source = parts[0] if parts else ""
    source_category = "unknown"
    if source == "overlay":
        source_category = "overlay"
    elif source.startswith("/dev/"):
        source_category = "device"
    elif source in {"tmpfs", "proc", "sysfs", "devtmpfs"}:
        source_category = source
    elif source:
        source_category = "other"
    return {
        "present": bool(parts),
        "source_category": source_category,
        "fstype": parts[1] if len(parts) > 1 else "unknown",
        "options_category": "ro" if ",ro," in f",{options}," else "rw_or_unknown",
        "has_lowerdir": "lowerdir=" in options,
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


def overlay_conf():
    result = {
        "overlayroot_config_detected": False,
        "overlayroot_tmpfs_detected": False,
        "overlayroot_category": "missing",
        "overlayroot_cfgdisk_category": "missing",
    }
    text = read_text("/etc/overlayroot.conf")
    if not text:
        return result
    result["overlayroot_config_detected"] = True
    overlay = None
    cfgdisk = None
    for line in text.splitlines():
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

    result["overlayroot_category"] = category(overlay)
    result["overlayroot_cfgdisk_category"] = category(cfgdisk)
    result["overlayroot_tmpfs_detected"] = overlay == "tmpfs"
    return result


def failed_units():
    text = shell("systemctl --failed --no-legend --plain 2>/dev/null || true")
    lines = [line for line in text.splitlines() if line.strip()]
    categories = []
    for line in lines:
        lowered = line.lower()
        if "networkmanager" in lowered:
            categories.append("networkmanager")
        elif "journald" in lowered:
            categories.append("journald")
        elif "mount" in lowered or "overlay" in lowered or "initramfs" in lowered:
            categories.append("mount_or_readonly")
        elif "kiosky" in lowered or "totem" in lowered or "dadooh" in lowered:
            categories.append("dadooh_product")
        elif "console-setup" in lowered or "keyboard-setup" in lowered:
            categories.append("console_setup")
        else:
            categories.append("other")
    return len(lines), sorted(set(categories))


def status_snapshot():
    public = load_json("/tmp/dadooh-status/status.json")
    launcher = load_json("/data/state/kiosky-player/launcher-status.json") or load_json("/tmp/kiosky-launcher-status.json")
    player = load_json("/tmp/kiosky-status.json")
    return {
        "public_state": public.get("public_state") or public.get("state") or launcher.get("public_state") or launcher.get("state") or "unknown",
        "playback": public.get("playback") or public.get("playback_state") or player.get("playback") or player.get("playback_state") or "unknown",
        "config_real_present": bool_path("/data/config/config.json"),
    }


def service_active(unit):
    return shell(f"systemctl is-active {unit} 2>/dev/null || true") or "unknown"


def journald_volatile():
    storage = shell("systemd-analyze cat-config systemd/journald.conf 2>/dev/null | awk -F= '/^[[:space:]]*Storage=/{v=$2} END{gsub(/[[:space:]]/, \"\", v); print v}'")
    return {
        "journald_storage_category": storage or "default_or_unknown",
        "journald_volatile": storage == "volatile" and bool_path("/run/log/journal") and not bool_path("/var/log/journal"),
        "run_log_journal_present": bool_path("/run/log/journal"),
        "var_log_journal_present": bool_path("/var/log/journal"),
    }


def kernel_config_overlayfs_builtin():
    text = shell("grep -h '^CONFIG_OVERLAY_FS=' /boot/config-* 2>/dev/null | tail -n 1 || true")
    return text.strip() == "CONFIG_OVERLAY_FS=y"


def inspect():
    root = mount_info("/")
    data = mount_info("/data")
    tmp = mount_info("/tmp")
    run_mount = mount_info("/run")
    proc_filesystems = read_text("/proc/filesystems")
    cmdline = read_text("/proc/cmdline")
    failed_count, failed_categories = failed_units()
    root_mount_type = root["fstype"]
    overlay_active = root["fstype"] == "overlay" or root["source_category"] == "overlay" or root["has_upperdir"]
    mount_overlay_attempt_detected = bool(shell("findmnt -t overlay -n 2>/dev/null || true"))
    result = {
        "host_category": "lab_board",
        "mode": MODE,
        "date_utc": shell("date -u +%Y-%m-%dT%H:%M:%SZ"),
        "kernel_release": shell("uname -r"),
        "kernel_overlayfs_builtin_running": kernel_config_overlayfs_builtin(),
        "overlay_in_proc_filesystems": "overlay" in proc_filesystems.split(),
        "cmdline_overlayroot_present": "overlayroot=" in cmdline,
        "cmdline_overlayroot_tmpfs_present": "overlayroot=tmpfs" in cmdline,
        "root_mount_type": root_mount_type,
        "root_mount_source_category": root["source_category"],
        "root_mount_options_category": root["options_category"],
        "root_apparent_write_allowed": root["options_category"] == "rw_or_unknown",
        "overlay_active": overlay_active,
        "data_mount_type": data["fstype"],
        "tmp_mount_type": tmp["fstype"],
        "run_mount_type": run_mount["fstype"],
        "data_writable": writable_probe("/data", "dadooh-c12-3-17-data-probe-"),
        "tmp_writable": writable_probe("/tmp", "dadooh-c12-3-17-tmp-probe-"),
        "run_writable": writable_probe("/run", "dadooh-c12-3-17-run-probe-"),
        "networkmanager_active": service_active("NetworkManager.service") == "active",
        "systemd_journald_active": service_active("systemd-journald.service") in {"active", "static"},
        "systemctl_failed_count": failed_count,
        "systemctl_failed_categories": failed_categories,
        "mount_overlay_attempt_detected": mount_overlay_attempt_detected,
        "readonly_semantics_possible": overlay_active,
        "uinitrd_present": bool_path("/boot/uInitrd"),
        "initrd_present": bool(shell("ls /boot/initrd.img-* 2>/dev/null | head -n 1 || true")),
        "os_release_id": shell(". /etc/os-release 2>/dev/null && printf %s \"$ID\" || true"),
        "os_release_version_codename": shell(". /etc/os-release 2>/dev/null && printf %s \"${VERSION_CODENAME:-unknown}\" || true"),
        "overlayroot_package_installed": shell("dpkg-query -W -f='${Status}' overlayroot 2>/dev/null || true").startswith("install ok installed"),
        "poweroff_executed": False,
        "power_cut_tested": False,
        "apt_update_executed": False,
        "apt_upgrade_executed": False,
        "writer_called": False,
        "secrets_published": False,
    }
    result.update(overlay_conf())
    result.update(journald_volatile())
    result.update(status_snapshot())
    if not overlay_active:
        result["c12_3_17_status"] = "blocked"
        result["c12_3_17_failure_category"] = "IMAGE_LAB_READ_ONLY_NOT_ACTIVE_WITH_BUILTIN_OVERLAYFS"
    else:
        result["c12_3_17_status"] = "inspect_passed_overlay_active"
        result["c12_3_17_failure_category"] = "none"
    return result


def persistence_test():
    state = inspect()
    if not state.get("overlay_active"):
        state["persistence_test_skipped"] = True
        state["skip_reason"] = "overlay_not_active"
        return state
    ts = shell("date -u +%Y%m%dT%H%M%SZ")
    root_marker = f"/etc/dadooh-c12-root-nonpersistent-{ts}.txt"
    data_dir = "/data/state/totem-readonly-validation"
    data_marker = f"{data_dir}/dadooh-c12-data-persistent-{ts}.txt"
    tmp_marker = f"/tmp/dadooh-c12-tmp-{ts}.txt"
    run_marker = f"/run/dadooh-c12-run-{ts}.txt"
    pathlib.Path(data_dir).mkdir(parents=True, exist_ok=True)
    created = {}
    for name, path, label in [
        ("root_test_file_created", root_marker, "root nonpersistent test"),
        ("data_test_file_created", data_marker, "data persistent test"),
        ("tmp_test_file_created", tmp_marker, "tmp writable test"),
        ("run_test_file_created", run_marker, "run writable test"),
    ]:
        try:
            pathlib.Path(path).write_text(f"{ts} {label}\n", encoding="utf-8")
            created[name] = True
        except Exception:
            created[name] = False
    shell("sync", timeout=30)
    state.update(created)
    state.update({
        "marker_timestamp": ts,
        "root_marker_path_category": "/etc/dadooh-c12-root-nonpersistent-<timestamp>.txt",
        "data_marker_path_category": "/data/state/totem-readonly-validation/dadooh-c12-data-persistent-<timestamp>.txt",
        "tmp_marker_path_category": "/tmp/dadooh-c12-tmp-<timestamp>.txt",
        "run_marker_path_category": "/run/dadooh-c12-run-<timestamp>.txt",
        "controlled_reboot_requested": all(created.values()),
    })
    state_file = pathlib.Path("/data/state/totem-readonly-validation/c12-3-17-last-test.json")
    state_file.write_text(json.dumps({
        "marker_timestamp": ts,
        "root_marker": root_marker,
        "data_marker": data_marker,
        "tmp_marker": tmp_marker,
        "run_marker": run_marker,
    }, sort_keys=True), encoding="utf-8")
    shell("sync", timeout=30)
    if all(created.values()):
        subprocess.Popen(["systemctl", "reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        state["controlled_reboot_executed"] = True
    else:
        state["controlled_reboot_executed"] = False
    return state


def post_reboot():
    state_file = pathlib.Path("/data/state/totem-readonly-validation/c12-3-17-last-test.json")
    markers = load_json(state_file)
    result = inspect()
    root_marker = markers.get("root_marker", "")
    data_marker = markers.get("data_marker", "")
    result["marker_state_present"] = bool(markers)
    result["root_test_file_persisted_after_reboot"] = bool(root_marker and bool_path(root_marker))
    result["data_test_file_persisted_after_reboot"] = bool(data_marker and bool_path(data_marker))
    result["root_test_write_nonpersistent"] = bool(markers) and not result["root_test_file_persisted_after_reboot"]
    result["data_test_write_persistent"] = bool(markers) and result["data_test_file_persisted_after_reboot"]
    result["controlled_reboot_executed"] = bool(markers)
    result["readonly_semantics_valid"] = all([
        result.get("kernel_overlayfs_builtin_running"),
        result.get("overlay_in_proc_filesystems"),
        result.get("overlay_active"),
        result.get("root_mount_type") == "overlay",
        result.get("root_test_write_nonpersistent"),
        result.get("data_test_write_persistent"),
        result.get("data_writable"),
        result.get("tmp_writable"),
        result.get("run_writable"),
        result.get("journald_volatile"),
    ])
    result["ready_for_c12_4"] = False
    result["c12_4_blocked"] = True
    result["ready_for_c12_4_candidate_review"] = bool(result["readonly_semantics_valid"])
    if data_marker and bool_path(data_marker):
        try:
            pathlib.Path(data_marker).unlink()
            shell("sync", timeout=30)
            result["data_marker_cleanup_executed"] = True
        except Exception:
            result["data_marker_cleanup_executed"] = False
    else:
        result["data_marker_cleanup_executed"] = False
    if result["readonly_semantics_valid"]:
        result["c12_3_17_status"] = "passed"
        result["c12_3_17_failure_category"] = "none"
    elif result["root_test_file_persisted_after_reboot"]:
        result["c12_3_17_status"] = "blocked"
        result["c12_3_17_failure_category"] = "ROOT_WRITE_PERSISTED_UNEXPECTEDLY"
    else:
        result["c12_3_17_status"] = "blocked"
        result["c12_3_17_failure_category"] = "READONLY_SEMANTICS_NOT_VALID"
    return result


if MODE == "inspect":
    payload = inspect()
elif MODE == "persistence-test":
    payload = persistence_test()
elif MODE == "post-reboot":
    payload = post_reboot()
elif MODE == "summary":
    payload = inspect()
else:
    payload = {"error": f"unsupported remote mode {MODE}"}

json.dump(payload, sys.stdout, sort_keys=True, indent=2)
sys.stdout.write("\n")
PY
}

summary() {
  local source_json=""
  if [ -f "$OUT_DIR/post-reboot.json" ]; then
    source_json="$OUT_DIR/post-reboot.json"
  elif [ -f "$OUT_DIR/inspect.json" ]; then
    source_json="$OUT_DIR/inspect.json"
  fi
  if [ -z "$source_json" ]; then
    echo "error: no inspect/post-reboot result available in $OUT_DIR" >&2
    exit 2
  fi
  python3 - "$source_json" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
keys = [
    "c12_3_17_status",
    "c12_3_17_failure_category",
    "kernel_overlayfs_builtin_running",
    "overlay_in_proc_filesystems",
    "root_mount_type",
    "overlay_active",
    "root_test_write_nonpersistent",
    "data_test_write_persistent",
    "data_writable",
    "tmp_writable",
    "run_writable",
    "journald_volatile",
    "networkmanager_active",
    "systemctl_failed_count",
    "readonly_semantics_valid",
    "ready_for_c12_4_candidate_review",
]
for key in keys:
    print(f"{key}={data.get(key, 'unknown')}")
PY
}

case "$MODE" in
  prepare-only) prepare_only ;;
  inspect|persistence-test|post-reboot) remote_python ;;
  summary) summary ;;
esac
