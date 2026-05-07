#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
KNOWN_HOSTS="${C12_3_4_KNOWN_HOSTS:-/tmp/dadooh-c12-3-4-known-hosts}"
OUT_DIR="${C12_3_4_OUT_DIR:-/tmp/dadooh-c12-3-4-image-lab-boot-validation}"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_3_4_image_lab_boot_validation.sh [host] [mode]

Modes:
  --prepare-only
  --inspect
  --verify-read-only
  --verify-firstboot-bootstrap
  --verify-config-missing
  --verify-f10-cancel
  --verify-wizard-candidate-only
  --summary

This runner is diagnostic-only for C12.3.4. It must not call writer, write real
config, change Wi-Fi/NetworkManager, install packages, reboot, poweroff, run apt
upgrade, or publish secrets/raw logs.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --verify-read-only) MODE="verify-read-only" ;;
    --verify-firstboot-bootstrap) MODE="verify-firstboot-bootstrap" ;;
    --verify-config-missing) MODE="verify-config-missing" ;;
    --verify-f10-cancel) MODE="verify-f10-cancel" ;;
    --verify-wizard-candidate-only) MODE="verify-wizard-candidate-only" ;;
    --summary) MODE="summary" ;;
    --help|-h) usage; exit 0 ;;
    --*) echo "error: unsupported mode $1" >&2; usage; exit 2 ;;
    *) HOST="$1" ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|inspect|verify-read-only|verify-firstboot-bootstrap|verify-config-missing|verify-f10-cancel|verify-wizard-candidate-only|summary) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ssh_base() {
  ssh \
    -o UserKnownHostsFile="$KNOWN_HOSTS" \
    -o StrictHostKeyChecking=accept-new \
    -o ServerAliveInterval=10 \
    -o ServerAliveCountMax=3 \
    "$HOST" "$@"
}

remote_collect() {
  if [ -z "$HOST" ]; then
    echo "error: host is required for $MODE" >&2
    exit 2
  fi
  mkdir -p "$OUT_DIR"
  chmod 700 "$OUT_DIR"
  ssh_base "C12_MODE='$MODE' python3 -" <<'PY'
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

MODE = os.environ.get("C12_MODE", "summary")


def run(cmd):
    try:
        return subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", "")


def text(cmd):
    return (run(cmd).stdout or "").strip()


def bool_path(path):
    return pathlib.Path(path).exists()


def load_json(path):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def service(unit):
    return {
        "active": text(["systemctl", "is-active", unit]) or "unknown",
        "enabled": text(["systemctl", "is-enabled", unit]) or "unknown",
        "result": text(["systemctl", "show", unit, "-p", "Result", "--value"]) or "unknown",
        "exec_main_status": text(["systemctl", "show", unit, "-p", "ExecMainStatus", "--value"]) or "unknown",
        "n_restarts": text(["systemctl", "show", unit, "-p", "NRestarts", "--value"]) or "unknown",
    }


def failed_count():
    out = text(["systemctl", "--failed", "--no-legend", "--plain"])
    if not out:
        return 0
    return len([line for line in out.splitlines() if line.strip()])


def proc_counts():
    counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
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
            counts["mpv"] += 1
        if any("totem_status_renderer" in name for name in names):
            counts["renderer"] += 1
        if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
            counts["setup"] += 1
    return counts


def status_snapshot():
    public_status = load_json("/tmp/dadooh-status/status.json")
    launcher = load_json("/data/state/kiosky-player/launcher-status.json") or load_json("/tmp/kiosky-launcher-status.json")
    player = load_json("/tmp/kiosky-status.json")
    public_state = (
        public_status.get("public_state")
        or public_status.get("state")
        or launcher.get("public_state")
        or launcher.get("state")
        or "unknown"
    )
    playback = (
        public_status.get("playback")
        or public_status.get("playback_state")
        or player.get("playback")
        or player.get("playback_state")
        or "unknown"
    )
    return {
        "public_state": public_state,
        "playback": playback,
        "launcher_state": launcher.get("state", "unknown"),
    }


def mount_info(path):
    out = text(["findmnt", "-n", "-o", "FSTYPE,OPTIONS", path])
    parts = out.split(maxsplit=1)
    return {
        "fstype": parts[0] if parts else "unknown",
        "options": parts[1] if len(parts) > 1 else "",
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
    data = mount_info("/data") if pathlib.Path("/data").exists() else {"fstype": "missing", "options": ""}
    tmp = mount_info("/tmp")
    run_mount = mount_info("/run")
    overlay_active = root["fstype"] == "overlay"
    root_ro = "ro" in {item.strip() for item in root["options"].split(",")}
    journald_dropin = pathlib.Path("/etc/systemd/journald.conf.d/10-dadooh-volatile.conf")
    journald_volatile = False
    try:
        journald_volatile = "Storage=volatile" in journald_dropin.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return {
        "read_only_enabled": overlay_active or root_ro,
        "overlay_active": overlay_active,
        "root_fstype": root["fstype"],
        "root_write_blocked": overlay_active or root_ro,
        "data_writable": writable_probe("/data", ".dadooh-c12-3-4-"),
        "tmp_writable": writable_probe("/tmp", ".dadooh-c12-3-4-"),
        "run_writable": writable_probe("/run", ".dadooh-c12-3-4-"),
        "journald_volatile": journald_volatile,
        "data_fstype": data["fstype"],
        "tmp_fstype": tmp["fstype"],
        "run_fstype": run_mount["fstype"],
    }


def firstboot_snapshot():
    status = load_json("/run/dadooh-lab-firstboot/status.json")
    marker_present = bool_path("/root/.not_logged_in_yet")
    lab_marker_present = bool_path("/etc/dadooh/image-lab-firstboot-autoconfig.present")
    return {
        "firstboot_marker_present": marker_present,
        "lab_firstboot_marker_present": lab_marker_present,
        "lab_bootstrap_status_present": bool(status),
        "lab_bootstrap_state": status.get("state", "unknown"),
        "lab_bootstrap_marker_removed": bool(status.get("firstboot_marker_removed", False)),
        "lab_bootstrap_network_apply_attempted": bool(status.get("network_apply_attempted", False)),
        "private_firstboot_data_published": False,
    }


def session_snapshot():
    candidates = []
    session_statuses = []
    roots = [
        pathlib.Path("/tmp/dadooh-c10-6-2-open-settings"),
        pathlib.Path("/tmp/dadooh-c10-6-open-settings-from-player"),
        pathlib.Path("/tmp"),
    ]
    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob("session-status.json"):
                if len(session_statuses) < 10:
                    session_statuses.append(path)
            for path in root.rglob("config.candidate.json"):
                if len(candidates) < 10:
                    candidates.append(path)
        except OSError:
            continue
    latest_status = {}
    if session_statuses:
        newest = max(session_statuses, key=lambda p: p.stat().st_mtime)
        latest_status = load_json(newest)
    writer_status = {}
    writer_paths = []
    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob("writer-status.json"):
                writer_paths.append(path)
        except OSError:
            continue
    if writer_paths:
        writer_status = load_json(max(writer_paths, key=lambda p: p.stat().st_mtime))
    writer_called = bool(latest_status.get("writer_called", False)) or bool(writer_status)
    real_config_written = bool(latest_status.get("real_config_written", False)) or bool(
        writer_status.get("result") in {"passed", "ok"}
    )
    candidate_generated = bool(latest_status.get("visual_candidate_generated", False)) or bool(candidates)
    return {
        "session_status_present": bool(latest_status),
        "apply_mode": latest_status.get("apply_mode", "unknown"),
        "visual_wizard_opened": bool(latest_status.get("visual_wizard_opened", False)),
        "visual_candidate_generated": candidate_generated,
        "setup_cancelled": bool(latest_status.get("setup_cancelled", False)),
        "writer_called": writer_called,
        "real_config_written": real_config_written,
        "writer_result": writer_status.get("result", latest_status.get("writer_result", "unknown")),
        "candidate_files_count": len(candidates),
        "session_lock_present": bool_path("/run/dadooh-settings/session.lock"),
        "request_present": bool_path("/run/dadooh-settings/request.json"),
    }


def inspect_snapshot():
    services = {
        unit: service(unit)
        for unit in (
            "kiosky-player.service",
            "totem-settings-trigger.service",
            "totem-open-settings.service",
            "dadooh-visual-splash.service",
            "totem-firstboot-gate.service",
            "totem-lab-firstboot-autoconfig.service",
        )
    }
    status = status_snapshot()
    counts = proc_counts()
    return {
        "uptime_seconds_bucket": "lt_10m"
        if float(open("/proc/uptime", encoding="utf-8").read().split()[0]) < 600
        else "gte_10m",
        "services": services,
        "systemctl_failed_count": failed_count(),
        "public_state": status["public_state"],
        "playback": status["playback"],
        "launcher_state": status["launcher_state"],
        "process_counts": counts,
        "session_lock_present": bool_path("/run/dadooh-settings/session.lock"),
        "request_present": bool_path("/run/dadooh-settings/request.json"),
        "config_real_present": bool_path("/data/config/config.json"),
        "orientation_json_present": bool_path("/data/state/totem-display/orientation.json"),
    }


def config_missing_snapshot(public_state):
    return {
        "config_missing_visual_ok": public_state == "config_missing",
        "stuck_starting_player": public_state == "starting_player",
        "shell_seen": "unknown",
    }


def classification(payload):
    ro = payload["read_only"]
    sess = payload["session"]
    inspect = payload["inspect"]
    classes = []
    if not ro["read_only_enabled"] or not ro["overlay_active"]:
        classes.append("IMAGE_LAB_READ_ONLY_NOT_ACTIVE")
    if (
        sess["visual_candidate_generated"]
        and not sess["writer_called"]
        and not sess["real_config_written"]
        and inspect["public_state"] == "config_missing"
    ):
        classes.append("CANDIDATE_ONLY_EXPECTED_WITHOUT_PRIVATE_VALUES")
    if sess["writer_called"] and not sess["real_config_written"]:
        classes.append("WRITER_ATTEMPT_FAILED")
    if sess["session_status_present"] and sess["apply_mode"] == "candidate-only" and inspect["public_state"] == "config_missing":
        classes.append("UX_AMBIGUOUS_CANDIDATE_ONLY")
    return classes or ["UNKNOWN"]


payload = {
    "schema_version": "dadooh-c12.3.4-image-lab-boot-validation.v1",
    "mode": MODE,
    "image_version": "c12.1.6",
    "boot_success": True,
    "ssh_available": True,
    "secrets_published": False,
    "raw_logs_published": False,
    "writer_invoked_by_runner": False,
    "wifi_changed_by_runner": False,
    "real_config_changed_by_runner": False,
}
payload["inspect"] = inspect_snapshot()
payload["read_only"] = read_only_snapshot()
payload["firstboot"] = firstboot_snapshot()
payload["session"] = session_snapshot()
payload["config_missing"] = config_missing_snapshot(payload["inspect"]["public_state"])
payload["classification"] = classification(payload)
payload["ready_for_c12_4"] = (
    payload["read_only"]["read_only_enabled"]
    and payload["read_only"]["overlay_active"]
    and payload["config_missing"]["config_missing_visual_ok"]
    and "IMAGE_LAB_READ_ONLY_NOT_ACTIVE" not in payload["classification"]
)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

case "$MODE" in
  prepare-only)
    git -C "$REPO_ROOT" diff --check
    bash -n "$0"
    python3 "$REPO_ROOT/scripts/board/totem_settings_trigger.py" --self-test >/dev/null
    python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
    python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
    python3 "$REPO_ROOT/scripts/board/totem_config_contract_validate.py" --self-test >/dev/null
    printf 'c12_3_4_prepare_only=ok\n'
    ;;
  *)
    remote_collect
    ;;
esac
