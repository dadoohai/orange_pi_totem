#!/usr/bin/env bash
set -euo pipefail

MODE="prepare-only"
HOST=""
TIMESTAMP="${C12_3_12_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${C12_3_12_RUN_ROOT:-/tmp/dadooh-c12-3-12-boot-validate-c12-1-10}"
OUT_DIR="${C12_3_12_OUT_DIR:-$RUN_ROOT/$TIMESTAMP-c12-3-12-boot-validate-c12-1-10}"
KNOWN_HOSTS="${C12_3_12_KNOWN_HOSTS:-/tmp/dadooh-c12-3-12-known-hosts}"
IMAGE_PATH="${C12_3_12_IMAGE_PATH:-/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-10_minimal.img}"
EXPECTED_SHA256="${C12_3_12_EXPECTED_SHA256:-c7e3e2af5e2cfa52db0a1cb73141b941a239471940020953d6debfbb0133e4b2}"

usage() {
  cat <<'USAGE'
Usage:
  run_c12_3_12_boot_validate_c12_1_10.sh [root@host] [mode]

Modes:
  --prepare-only
  --inspect
  --verify-read-only
  --verify-visual
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
    --verify-visual) MODE="verify-visual" ;;
    --summary) MODE="summary" ;;
    --help|-h) usage; exit 0 ;;
    --*) echo "error: unsupported mode $1" >&2; usage; exit 2 ;;
    *) HOST="$1" ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|inspect|verify-read-only|verify-visual|summary) ;;
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
    printf 'card_written_by_runner=false\n'
    printf 'writer_called=false\n'
    printf 'wifi_changed=false\n'
  } > "$OUT_DIR/prepare.env"
  cat "$OUT_DIR/prepare.env"
}

remote_collect() {
  ssh_board "C12_3_12_MODE='$MODE' python3 -" > "$OUT_DIR/$MODE.json" <<'PY'
import json
import os
import pathlib
import re
import subprocess

MODE = os.environ.get("C12_3_12_MODE", "inspect")


def run(cmd, timeout=15):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=timeout)
    except Exception:
        return subprocess.CompletedProcess(cmd, 127, "", "")


def shell(command, timeout=15):
    return (run(["sh", "-lc", command], timeout=timeout).stdout or "").strip()


def exists(path):
    return pathlib.Path(path).exists()


def read_text(path, limit=65536):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def load_json(path):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8", errors="replace"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


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


def failed_snapshot():
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
    return {"count": len(lines), "categories": sorted(set(categories))}


def bucket_size(path):
    try:
        size = pathlib.Path(path).stat().st_size
    except OSError:
        return "missing"
    if size == 0:
        return "empty"
    if size < 4096:
        return "small"
    return "nonempty"


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


public = load_json("/tmp/dadooh-status/status.json")
launcher = load_json("/data/state/kiosky-player/launcher-status.json") or load_json("/tmp/kiosky-launcher-status.json")
root = mount_info("/")
cmdline = read_text("/proc/cmdline")
armbian_env = read_text("/boot/armbianEnv.txt")
counts = proc_counts()
status = overlay_status()
svg_path = pathlib.Path("/tmp/dadooh-status/status.svg")
root_read_only = root["source_category"] == "overlay" or root["options_category"] == "ro"
overlay_active = root["source_category"] == "overlay" or root["fstype"] == "overlay"
public_state = public.get("public_state") or public.get("state") or launcher.get("state", "unknown")

visual_classification = "unknown"
if public_state == "config_missing" and counts["renderer"] > 0 and counts["MPV"] > 0:
    visual_classification = "CONFIG_MISSING_VISUAL_BLACK_SCREEN_WITH_RENDERER_ACTIVE"
elif public_state == "config_missing" and counts["renderer"] == 0:
    visual_classification = "CONFIG_MISSING_RENDERER_ABSENT"
elif public_state == "config_missing":
    visual_classification = "CONFIG_MISSING_VISUAL_STATE_UNKNOWN"

read_only_classification = "READ_ONLY_ACTIVE" if root_read_only and overlay_active else "IMAGE_LAB_READ_ONLY_NOT_ACTIVE"
if status.get("overlay_module_path_found") == "true" and status.get("insmod_rc") not in {"0", "missing", None}:
    read_only_failure = "DYNAMIC_PATH_FOUND_INSMOD_FAILED"
elif status.get("overlay_module_path_found") == "false":
    read_only_failure = "DYNAMIC_PATH_NOT_FOUND"
else:
    read_only_failure = "UNKNOWN"

payload = {
    "schema_version": "dadooh-c12.3.12-boot-validate-c12.1.10.v1",
    "mode": MODE,
    "board_category": "lab_board",
    "inspect_read_only": True,
    "image_version": "c12.1.10",
    "ssh_available": True,
    "firstboot_marker_present": exists("/root/.not_logged_in_yet"),
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
    "failed": failed_snapshot(),
    "public_state": public_state,
    "playback": public.get("playback") or public.get("playback_state") or "unknown",
    "proc_counts": counts,
    "session_lock_present": exists("/run/dadooh-settings/session.lock") or exists("/tmp/dadooh-settings/session.lock"),
    "request_present": exists("/run/dadooh-settings/request.json") or exists("/tmp/dadooh-settings/request.json"),
    "config_real_present": exists("/data/config/config.json"),
    "orientation_json_present": exists("/data/state/totem-display/orientation.json"),
    "status_svg_exists": svg_path.exists(),
    "status_svg_size_bucket": bucket_size(str(svg_path)),
    "human_observed_black_screen": True,
    "visual_classification": visual_classification,
    "root_mount": root,
    "read_only_enabled": root_read_only,
    "overlay_active": overlay_active,
    "root_write_blocked_inferred": root_read_only,
    "data_mount": mount_info("/data"),
    "tmp_mount": mount_info("/tmp"),
    "run_mount": mount_info("/run"),
    "cmdline_overlayroot_tmpfs_present": "overlayroot=tmpfs" in cmdline,
    "armbian_env_overlayroot_present": "overlayroot" in armbian_env,
    "overlay_status_present": bool(status),
    "sanitized_overlay_load_status": status,
    "proc_filesystems_contains_overlay_after_boot": bool(re.search(r"(^|\n)nodev\s+overlay(\n|$)", read_text("/proc/filesystems"))),
    "read_only_classification": read_only_classification,
    "read_only_failure_category": read_only_failure,
    "ready_for_c12_4": bool(root_read_only and overlay_active),
    "writer_called": False,
    "real_config_written": False,
    "wifi_changed": False,
    "raw_logs_published": False,
}
print(json.dumps(payload, indent=2, sort_keys=True))
PY
  chmod 600 "$OUT_DIR/$MODE.json"
}

summary() {
  local source="$OUT_DIR/inspect.json"
  if [ ! -f "$source" ]; then
    source="$(find "$OUT_DIR" -maxdepth 1 -type f -name '*.json' | sort | head -1 || true)"
  fi
  if [ -z "$source" ] || [ ! -f "$source" ]; then
    echo "error: no JSON output found in $OUT_DIR" >&2
    exit 2
  fi
  python3 - "$source" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for key in (
    "image_version",
    "ssh_available",
    "public_state",
    "read_only_enabled",
    "overlay_active",
    "root_write_blocked_inferred",
    "read_only_failure_category",
    "visual_classification",
    "ready_for_c12_4",
):
    print(f"{key}={data.get(key)}")
PY
}

case "$MODE" in
  prepare-only) prepare_only ;;
  inspect|verify-read-only|verify-visual) remote_collect; cat "$OUT_DIR/$MODE.json" ;;
  summary) summary ;;
esac
