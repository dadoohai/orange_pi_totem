#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
TIMESTAMP="${C12_3_5_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${C12_3_5_RUN_ROOT:-/tmp/dadooh-c12-3-5-boot-readonly-wizard-classification}"
OUT_DIR="${C12_3_5_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-3-5-boot-readonly-wizard-classification}"
KNOWN_HOSTS="${C12_3_5_KNOWN_HOSTS:-/tmp/dadooh-c12-3-5-known-hosts}"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_3_5_boot_readonly_wizard_classification.sh [root@host] [mode]

Modes:
  --prepare-only
  --inspect
  --verify-read-only
  --verify-config-missing
  --classify-wizard-result
  --summary

This runner is diagnostic-only for C12.3.5. It must not call writer, write real
config, change Wi-Fi/NetworkManager, install packages, reboot, poweroff, run apt
upgrade, or publish secrets/raw logs. The read-only mode uses only sanitized
mount inspection plus short create/delete probes under /data, /tmp and /run.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --verify-read-only) MODE="verify-read-only" ;;
    --verify-config-missing) MODE="verify-config-missing" ;;
    --classify-wizard-result) MODE="classify-wizard-result" ;;
    --summary) MODE="summary" ;;
    --help|-h) usage; exit 0 ;;
    --*) echo "error: unsupported mode $1" >&2; usage; exit 2 ;;
    *) HOST="$1" ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|inspect|verify-read-only|verify-config-missing|classify-wizard-result|summary) ;;
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
  if [ -f "$REPO_ROOT/scripts/remote/run_c12_1_7_overlayroot_activation_diagnose.sh" ]; then
    bash -n "$REPO_ROOT/scripts/remote/run_c12_1_7_overlayroot_activation_diagnose.sh"
  fi
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_config_contract_validate.py" --self-test >/dev/null
  {
    printf 'c12_3_5_prepare_only=ok\n'
    printf 'repo_diff_check=ok\n'
    printf 'boards_touched=false\n'
    printf 'writer_called=false\n'
    printf 'real_config_written=false\n'
    printf 'wifi_changed=false\n'
  } > "$OUT_DIR/prepare.env"
  cat "$OUT_DIR/prepare.env"
}

remote_collect() {
  ssh_board "C12_3_5_MODE='$MODE' python3 -" > "$OUT_DIR/$MODE.json" <<'PY'
import json
import os
import pathlib
import stat
import subprocess
import tempfile
import time

MODE = os.environ.get("C12_3_5_MODE", "summary")


def run(cmd, timeout=12):
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


def out(cmd, timeout=12):
    return (run(cmd, timeout).stdout or "").strip()


def shell(command, timeout=12):
    return out(["sh", "-lc", command], timeout=timeout)


def load_json(path):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def bool_path(path):
    return pathlib.Path(path).exists()


def service(unit):
    return {
        "active": shell(f"systemctl is-active {unit} 2>/dev/null || true") or "unknown",
        "enabled": shell(f"systemctl is-enabled {unit} 2>/dev/null || true") or "unknown",
        "result": shell(f"systemctl show {unit} -p Result --value 2>/dev/null || true") or "unknown",
        "n_restarts": shell(f"systemctl show {unit} -p NRestarts --value 2>/dev/null || echo 0") or "0",
    }


def failed_count_and_categories():
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
    return {
        "public_state": public_state,
        "playback": playback,
        "launcher_state": launcher.get("state", "unknown"),
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
    return {
        "present": bool(parts),
        "source_category": source_category,
        "fstype": parts[1] if len(parts) > 1 else "unknown",
        "options_category": "ro" if len(parts) > 2 and "ro" in {item.strip() for item in parts[2].split(",")} else "rw_or_unknown",
        "has_upperdir": len(parts) > 2 and "upperdir=" in parts[2],
        "has_workdir": len(parts) > 2 and "workdir=" in parts[2],
    }


def writable_probe(directory, prefix):
    base = pathlib.Path(directory)
    if not base.exists():
        return False
    try:
        if directory == "/data":
            target_dir = pathlib.Path("/data/state")
            target_dir.mkdir(parents=True, exist_ok=True)
        else:
            target_dir = base
        fd, name = tempfile.mkstemp(prefix=prefix, dir=str(target_dir))
        os.write(fd, b"ok\n")
        os.close(fd)
        os.unlink(name)
        return True
    except Exception:
        return False


def read_only_snapshot():
    root = mount_info("/")
    data = mount_info("/data") if pathlib.Path("/data").exists() else {"present": False, "fstype": "missing"}
    tmp = mount_info("/tmp")
    run_mount = mount_info("/run")
    overlay_active = root.get("fstype") == "overlay" or root.get("source_category") == "overlay"
    root_ro = root.get("options_category") == "ro"
    journald_dropin = pathlib.Path("/etc/systemd/journald.conf.d/10-dadooh-volatile.conf")
    journald_volatile = False
    try:
        journald_volatile = "Storage=volatile" in journald_dropin.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return {
        "read_only_enabled": overlay_active or root_ro,
        "overlay_active": overlay_active,
        "root_write_blocked": overlay_active or root_ro,
        "root_fstype": root.get("fstype", "unknown"),
        "root_options_category": root.get("options_category", "unknown"),
        "root_overlay_upperdir_present": root.get("has_upperdir", False),
        "root_overlay_workdir_present": root.get("has_workdir", False),
        "data_writable": writable_probe("/data", ".dadooh-c12-3-5-"),
        "tmp_writable": writable_probe("/tmp", ".dadooh-c12-3-5-"),
        "run_writable": writable_probe("/run", ".dadooh-c12-3-5-"),
        "journald_volatile": journald_volatile,
        "data_fstype": data.get("fstype", "unknown"),
        "tmp_fstype": tmp.get("fstype", "unknown"),
        "run_fstype": run_mount.get("fstype", "unknown"),
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


def overlayroot_config():
    path = pathlib.Path("/etc/overlayroot.conf")
    result = {"present": path.exists(), "overlayroot_category": "missing", "cfgdisk_category": "missing"}
    if not path.exists():
        return result
    overlay = None
    cfgdisk = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("overlayroot="):
            overlay = stripped.split("=", 1)[1].strip().strip('"').strip("'")
        elif stripped.startswith("overlayroot_cfgdisk="):
            cfgdisk = stripped.split("=", 1)[1].strip().strip('"').strip("'")
    def cat(value):
        if value is None:
            return "missing"
        if value == "":
            return "empty"
        if value == "tmpfs":
            return "tmpfs"
        if value in {"disabled", "disable"}:
            return "disabled"
        return "other"
    result["overlayroot_category"] = cat(overlay)
    result["cfgdisk_category"] = cat(cfgdisk)
    return result


def boot_snapshot():
    cmdline = pathlib.Path("/proc/cmdline").read_text(encoding="utf-8", errors="replace") if pathlib.Path("/proc/cmdline").exists() else ""
    armbian_env = pathlib.Path("/boot/armbianEnv.txt")
    env_text = armbian_env.read_text(encoding="utf-8", errors="replace") if armbian_env.exists() else ""
    boot_cmd = pathlib.Path("/boot/boot.cmd")
    boot_script_text = ""
    if boot_cmd.exists():
        boot_script_text = boot_cmd.read_text(encoding="utf-8", errors="replace")
    elif pathlib.Path("/boot/boot.scr").exists():
        boot_script_text = shell("strings /boot/boot.scr 2>/dev/null | grep -E 'uInitrd|initrd' || true")
    kernel = shell("uname -r")
    initrd_candidates = sorted(pathlib.Path("/boot").glob("initrd.img*"))
    uinitrd = pathlib.Path("/boot/uInitrd")
    marker_visible = False
    overlay_hook_visible = False
    overlay_module_visible = False
    lsinitramfs = shell("command -v lsinitramfs 2>/dev/null || true")
    if initrd_candidates and lsinitramfs:
        listing = shell(f"lsinitramfs {str(initrd_candidates[-1])} 2>/dev/null | grep -E 'overlayroot|overlay\\.ko|c12-overlayroot-initramfs-marker' || true", timeout=20)
        marker_visible = "c12-overlayroot-initramfs-marker" in listing
        overlay_hook_visible = "overlayroot" in listing
        overlay_module_visible = "overlay.ko" in listing
    return {
        "kernel_version": kernel,
        "cmdline_overlayroot_present": "overlayroot" in cmdline,
        "cmdline_root_present": " root=" in f" {cmdline}",
        "cmdline_console_category": (
            "serial" if "console=ttyS" in cmdline or "console=serial" in cmdline
            else "tty" if "console=tty" in cmdline
            else "none"
        ),
        "armbian_env_present": armbian_env.exists(),
        "armbian_env_overlayroot_present": "overlayroot" in env_text,
        "armbian_env_extraargs_present": "extraargs=" in env_text,
        "armbian_env_uses_uinitrd": "uInitrd" in env_text,
        "boot_script_uses_uinitrd": "uInitrd" in boot_script_text,
        "boot_uinitrd_exists": uinitrd.exists(),
        "boot_uinitrd_size_bucket": file_size_bucket("/boot/uInitrd"),
        "initrd_img_exists": bool(initrd_candidates),
        "initrd_marker_c12_1_8_visible": marker_visible,
        "initrd_overlayroot_hook_visible": overlay_hook_visible,
        "initrd_overlay_module_visible": overlay_module_visible,
    }


def firstboot_snapshot():
    status = load_json("/run/dadooh-lab-firstboot/status.json")
    return {
        "firstboot_marker_present": bool_path("/root/.not_logged_in_yet"),
        "lab_firstboot_marker_present": bool_path("/etc/dadooh/image-lab-firstboot-autoconfig.present"),
        "lab_bootstrap_status_present": bool(status),
        "lab_bootstrap_applied": status.get("state") == "complete" or bool_path("/etc/dadooh/image-lab-firstboot-autoconfig.present"),
        "lab_bootstrap_state": status.get("state", "unknown"),
        "private_firstboot_data_published": False,
    }


def config_meta():
    path = pathlib.Path("/data/config/config.json")
    meta = {"present": path.exists(), "permissions_ok": "unknown", "content_read": False}
    if not path.exists():
        return meta
    try:
        st = path.stat()
        meta["mode"] = f"{stat.S_IMODE(st.st_mode):04o}"[-4:]
        meta["permissions_ok"] = meta["mode"] == "0640"
    except OSError:
        meta["permissions_ok"] = False
    return meta


def recent_artifacts():
    roots = []
    tmp = pathlib.Path("/tmp")
    if tmp.exists():
        roots.extend([p for p in tmp.glob("dadooh-*") if p.is_dir()])
    for extra in ("/data/state/totem-settings", "/run/dadooh-settings"):
        p = pathlib.Path(extra)
        if p.exists():
            roots.append(p)
    candidate_paths = []
    setup_status_paths = []
    session_status_paths = []
    writer_status_paths = []
    handoff_status_paths = []
    for root in roots:
        try:
            for path in root.rglob("config.candidate.json"):
                candidate_paths.append(path)
            for path in root.rglob("setup-status.json"):
                if "handoff" in str(path) or "writer" in str(path):
                    handoff_status_paths.append(path)
                else:
                    setup_status_paths.append(path)
            for path in root.rglob("session-status.json"):
                session_status_paths.append(path)
            for path in root.rglob("writer-status.json"):
                writer_status_paths.append(path)
        except OSError:
            continue
    def newest(paths):
        if not paths:
            return {}
        try:
            return load_json(max(paths, key=lambda p: p.stat().st_mtime))
        except OSError:
            return {}
    return {
        "candidate_files_count": len(candidate_paths),
        "latest_setup_status": newest(setup_status_paths),
        "latest_session_status": newest(session_status_paths),
        "latest_handoff_status": newest(handoff_status_paths),
        "latest_writer_status": newest(writer_status_paths),
    }


def invalid_reason_category(invalid_fields):
    if not isinstance(invalid_fields, list):
        return "unknown"
    fields = {(item.get("field"), item.get("reason")) for item in invalid_fields if isinstance(item, dict)}
    only_fields = {field for field, _ in fields}
    reasons = {reason for _, reason in fields}
    if "api_url" in only_fields:
        if any("missing" in str(reason) for reason in reasons):
            return "missing_api_url"
        return "api_url_placeholder_or_invalid"
    if "api_key" in only_fields:
        if any("required" in str(reason) or "empty" in str(reason) for reason in reasons):
            return "missing_api_key"
        if any("placeholder" in str(reason) for reason in reasons):
            return "api_key_placeholder"
        return "api_key_invalid"
    if "environment_id" in only_fields:
        return "missing_environment_id" if any("missing" in str(reason) for reason in reasons) else "environment_id_invalid"
    if any(field in only_fields for field in {"media_dir", "cache_dir", "status_file"}):
        return "path_invalid"
    if invalid_fields:
        return "other"
    return "none"


def wizard_result_snapshot(public_state, config_present):
    artifacts = recent_artifacts()
    setup = artifacts["latest_setup_status"]
    session = artifacts["latest_session_status"]
    handoff = artifacts["latest_handoff_status"]
    writer = artifacts["latest_writer_status"]
    setup_contract = setup.get("contract_validation") if isinstance(setup.get("contract_validation"), dict) else {}
    allow = setup_contract.get("allow_mock") if isinstance(setup_contract.get("allow_mock"), dict) else {}
    handoff_contract = handoff.get("contract_validation") if isinstance(handoff.get("contract_validation"), dict) else {}
    private_real = handoff_contract.get("private_real_dry_run") if isinstance(handoff_contract.get("private_real_dry_run"), dict) else {}
    writer_called = bool(session.get("writer_called", False)) or bool(writer)
    real_config_written = bool(session.get("real_config_written", False)) or writer.get("result") in {"passed", "ok"}
    candidate_generated = (
        bool(session.get("visual_candidate_generated", False))
        or bool(setup.get("guardrails", {}).get("candidate_generated", False))
        or artifacts["candidate_files_count"] > 0
    )
    real_dry_run_executed = bool(private_real)
    real_dry_run_valid = private_real.get("valid", "unknown") if real_dry_run_executed else False
    real_dry_run_failure_reason = invalid_reason_category(private_real.get("invalid_fields", [])) if real_dry_run_executed and not real_dry_run_valid else "not_run"
    if candidate_generated and not writer_called and not real_config_written and not config_present:
        classification = "CANDIDATE_ONLY_EXPECTED_WITHOUT_PRIVATE_VALUES"
    elif candidate_generated and not writer_called and not real_config_written:
        classification = "WRITER_NOT_CALLED_POLICY"
    elif writer_called and not real_config_written:
        classification = "WRITER_ATTEMPT_FAILED"
    elif real_config_written and public_state == "config_missing":
        classification = "CONFIG_WRITTEN_BUT_INVALID"
    elif config_present and public_state == "config_missing":
        classification = "CONFIG_PATH_MISMATCH"
    else:
        classification = "UNKNOWN"
    ux_ambiguous = candidate_generated and not real_config_written and public_state == "config_missing"
    return {
        "candidate_generated": candidate_generated,
        "candidate_files_count": artifacts["candidate_files_count"],
        "writer_called": writer_called,
        "real_config_written": real_config_written,
        "c5_1_allow_mock_passed": allow.get("valid", "unknown"),
        "c5_1_real_dry_run_executed": real_dry_run_executed,
        "c5_1_real_dry_run_valid": real_dry_run_valid,
        "real_dry_run_failure_reason": real_dry_run_failure_reason,
        "apply_mode": session.get("apply_mode", "unknown"),
        "writer_result": writer.get("result", session.get("writer_result", "unknown")),
        "final_state_after_wizard": public_state,
        "launcher_config_missing_due_to_absent_config": (not config_present and public_state == "config_missing"),
        "launcher_config_missing_due_to_invalid_config": (config_present and public_state == "config_missing"),
        "wizard_showed_candidate_only_clearly": "unknown",
        "wizard_result_classification": classification,
        "ux_ambiguous_candidate_only": ux_ambiguous,
    }


failed_count, failed_categories = failed_count_and_categories()
status = status_snapshot()
config = config_meta()
read_only = read_only_snapshot()
wizard = wizard_result_snapshot(status["public_state"], config["present"])
config_missing_visual_ok = status["public_state"] == "config_missing"
blockers = []
if not read_only["read_only_enabled"] or not read_only["overlay_active"] or not read_only["root_write_blocked"]:
    blockers.append("IMAGE_LAB_READ_ONLY_NOT_ACTIVE")
if failed_count:
    blockers.append("SYSTEMD_FAILED_PRESENT")
if wizard["wizard_result_classification"] in {"WRITER_ATTEMPT_FAILED", "CONFIG_WRITTEN_BUT_INVALID", "CONFIG_PATH_MISMATCH", "UNKNOWN"}:
    blockers.append(wizard["wizard_result_classification"])
if wizard["ux_ambiguous_candidate_only"]:
    blockers.append("UX_AMBIGUOUS_CANDIDATE_ONLY")

payload = {
    "schema_version": "dadooh-c12.3.5-boot-readonly-wizard-classification.v1",
    "mode": MODE,
    "image_version": "c12.1.8",
    "boot_success": True,
    "ssh_available": True,
    "host_published": False,
    "secrets_published": False,
    "raw_logs_published": False,
    "writer_invoked_by_runner": False,
    "wifi_changed_by_runner": False,
    "real_config_changed_by_runner": False,
    "packages_installed_by_runner": False,
    "reboot_executed": False,
    "poweroff_executed": False,
    "uptime_seconds_bucket": "lt_10m" if float(open("/proc/uptime", encoding="utf-8").read().split()[0]) < 600 else "gte_10m",
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
    "systemctl_failed_count": failed_count,
    "systemctl_failed_categories": failed_categories,
    "public_state": status["public_state"],
    "playback": status["playback"],
    "launcher_state": status["launcher_state"],
    "process_counts": proc_counts(),
    "session_lock_present": bool_path("/run/dadooh-settings/session.lock"),
    "request_present": bool_path("/run/dadooh-settings/request.json"),
    "config_real_present": config["present"],
    "config_permissions_ok_if_present": config["permissions_ok"],
    "config_content_read": False,
    "orientation_json_present": bool_path("/data/state/totem-display/orientation.json"),
    "firstboot": firstboot_snapshot(),
    "overlayroot_config": overlayroot_config(),
    "boot": boot_snapshot(),
    "read_only": read_only,
    "config_missing": {
        "config_missing_visual_ok": config_missing_visual_ok,
        "stuck_starting_player": status["public_state"] == "starting_player",
        "shell_seen": "unknown",
    },
    "wizard": wizard,
    "candidate_only_expected_without_private_values": wizard["wizard_result_classification"] == "CANDIDATE_ONLY_EXPECTED_WITHOUT_PRIVATE_VALUES",
    "ready_for_c12_4": (
        read_only["read_only_enabled"]
        and read_only["overlay_active"]
        and read_only["root_write_blocked"]
        and config_missing_visual_ok
        and wizard["wizard_result_classification"] in {
            "CANDIDATE_ONLY_EXPECTED_WITHOUT_PRIVATE_VALUES",
            "WRITER_NOT_CALLED_POLICY",
        }
    ),
    "blockers": sorted(set(blockers)),
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  cat "$OUT_DIR/$MODE.json"
}

case "$MODE" in
  prepare-only)
    prepare_only
    ;;
  inspect|verify-read-only|verify-config-missing|classify-wizard-result|summary)
    remote_collect
    ;;
esac
