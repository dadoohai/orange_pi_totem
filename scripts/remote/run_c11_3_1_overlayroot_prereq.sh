#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
CONFIRMATION="${C11_3_1_CONFIRMATION:-}"
PACKAGE_NAME="${C11_3_1_PACKAGE:-overlayroot}"
TIMESTAMP="${C11_3_1_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-/tmp/dadooh-c11-3-1-overlayroot-prereq}"
LOCAL_OUT_DIR="${C11_3_1_LOCAL_OUT_DIR:-$LOCAL_RUN_ROOT/$TIMESTAMP-c11-3-1-overlayroot-prereq}"
REMOTE_ROOT="${REMOTE_ROOT:-/tmp/dadooh-c11-3-1-overlayroot-prereq}"
REMOTE_OUT="$REMOTE_ROOT/out-$TIMESTAMP"
SSH_CONTROL_DIR="/tmp/dadooh-c11-3-1-ssh-$TIMESTAMP"
SSH_CONTROL_PATH="$SSH_CONTROL_DIR/%C"

INSTALL_CONFIRMATION="CONFIRMO INSTALAR OVERLAYROOT C11.3.1 NA DEV"

usage() {
  cat <<'USAGE'
Usage:
  run_c11_3_1_overlayroot_prereq.sh <root@host> [mode] [options]

Modes:
  --prepare-only
  --inspect
  --apt-policy
  --dry-run-install
  --install-prereq
  --verify-prereq
  --summary

Options:
  --confirm "CONFIRMO ..."
  --package overlayroot
  --local-out-dir /tmp/...

Rules:
  - dev board only for C11.3.1;
  - does not enable read-only, reboot, poweroff, touch the test board, call
    writer, read/write real config, change Wi-Fi or NetworkManager profiles;
  - --install-prereq requires: CONFIRMO INSTALAR OVERLAYROOT C11.3.1 NA DEV;
  - install uses only the exact package with apt-get install --no-upgrade
    --no-install-recommends; never runs apt upgrade/full-upgrade/dist-upgrade
    or armbian-upgrade;
  - never publishes raw apt logs, config, secrets, SSID, IP, MAC, DNS, gateway
    or hostname.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --apt-policy) MODE="apt-policy" ;;
    --dry-run-install) MODE="dry-run-install" ;;
    --install-prereq) MODE="install-prereq" ;;
    --verify-prereq) MODE="verify-prereq" ;;
    --summary) MODE="summary" ;;
    --confirm)
      shift
      CONFIRMATION="${1:-}"
      ;;
    --package)
      shift
      PACKAGE_NAME="${1:-}"
      ;;
    --local-out-dir)
      shift
      LOCAL_OUT_DIR="${1:-}"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      HOST="$1"
      ;;
  esac
  shift
done

case "$MODE" in
  prepare-only|inspect|apt-policy|dry-run-install|install-prereq|verify-prereq|summary) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ "$MODE" != "prepare-only" ] && [ "$MODE" != "summary" ] && [ -z "$HOST" ]; then
  echo "error: host is required for $MODE" >&2
  exit 2
fi

case "$PACKAGE_NAME" in
  overlayroot) ;;
  *) echo "error: only exact package overlayroot is allowed in C11.3.1" >&2; exit 2 ;;
esac

if [ "$MODE" = "install-prereq" ] && [ "$CONFIRMATION" != "$INSTALL_CONFIRMATION" ]; then
  echo "error: install-prereq requires exact confirmation" >&2
  exit 2
fi

case "$LOCAL_OUT_DIR" in
  /tmp/*) ;;
  *) echo "error: --local-out-dir must be under /tmp" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || printf unknown)"
LOCAL_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || printf unknown)"
LOCAL_DIRTY_COUNT="$(git -C "$REPO_ROOT" status --short 2>/dev/null | wc -l | tr -d ' ')"

ssh_board() {
  mkdir -p "$SSH_CONTROL_DIR"
  chmod 700 "$SSH_CONTROL_DIR"
  ssh -o ConnectTimeout=10 -o NumberOfPasswordPrompts=1 -o ControlMaster=auto -o ControlPersist=300 -o ControlPath="$SSH_CONTROL_PATH" "$HOST" "$@"
}

scp_board() {
  mkdir -p "$SSH_CONTROL_DIR"
  chmod 700 "$SSH_CONTROL_DIR"
  scp -o ConnectTimeout=10 -o NumberOfPasswordPrompts=1 -o ControlMaster=auto -o ControlPersist=300 -o ControlPath="$SSH_CONTROL_PATH" "$@"
}

prepare_local() {
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  git -C "$REPO_ROOT" diff --check
  bash -n "$REPO_ROOT/scripts/remote/run_c11_3_1_overlayroot_prereq.sh"
  bash -n "$REPO_ROOT/scripts/remote/run_c11_3_read_only_enablement_dev.sh"
  bash -n "$REPO_ROOT/scripts/board/install_totem_appliance.sh"
  bash -n "$REPO_ROOT/scripts/board/verify_totem_appliance.sh"
  bash -n "$REPO_ROOT/scripts/board/verify_totem_read_only_policy.sh"
  python3 -m json.tool "$REPO_ROOT/scripts/board/totem_read_only_policy.json" >/dev/null
  python3 -m json.tool "$REPO_ROOT/scripts/board/totem_appliance_manifest.json" >/dev/null
  "$REPO_ROOT/scripts/board/verify_totem_read_only_policy.sh" --self-test >/dev/null
}

write_local_readme() {
  local result="$1"
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  cat > "$LOCAL_OUT_DIR/README.md" <<EOF
# C11.3.1 overlayroot prerequisite runner artifact

- mode: \`$MODE\`
- result: \`$result\`
- repo_head: \`$LOCAL_HEAD\`
- repo_branch: \`$LOCAL_BRANCH\`
- source_dirty_entries: \`$LOCAL_DIRTY_COUNT\`
- host: \`<dev-board>\`
- package_name: \`$PACKAGE_NAME\`
- read_only_enabled: \`false\`
- test_board_touched: \`false\`
- power_cut_tested: \`false\`
- poweroff_executed: \`false\`
- reboot_executed: \`false\`
- writer_called: \`false\`
- real_config_read: \`false\`
- real_config_written: \`false\`
- wifi_changed: \`false\`
- networkmanager_profiles_changed: \`false\`
- raw_logs_published: \`false\`
- secrets_published: \`false\`
EOF
  chmod 600 "$LOCAL_OUT_DIR/README.md"
}

pull_remote_artifacts() {
  mkdir -p "$LOCAL_OUT_DIR/remote"
  chmod 700 "$LOCAL_OUT_DIR/remote"
  scp_board -q -r "$HOST:$REMOTE_OUT/." "$LOCAL_OUT_DIR/remote/" || true
}

run_remote_python() {
  local remote_mode="$1"
  ssh_board "mkdir -p '$REMOTE_OUT' && chmod 700 '$REMOTE_ROOT' '$REMOTE_OUT'"
  ssh_board "REMOTE_MODE='$remote_mode' REMOTE_OUT='$REMOTE_OUT' PACKAGE_NAME='$PACKAGE_NAME' python3 -" <<'PY'
import json
import os
import pathlib
import re
import subprocess
import time

MODE = os.environ["REMOTE_MODE"]
OUT = pathlib.Path(os.environ["REMOTE_OUT"])
PACKAGE = os.environ["PACKAGE_NAME"]


def run(args, timeout=20):
    try:
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        env["LANGUAGE"] = "C"
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout, check=False, env=env)
    except Exception:
        return None


def out(args, timeout=20):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


def command_available(name):
    return bool(out(["sh", "-c", f"command -v {name}"], 4))


def package_installed(name):
    result = run(["dpkg-query", "-W", "-f=${Status}", name], 8)
    return bool(result is not None and result.returncode == 0 and (result.stdout or "").strip() == "install ok installed")


def overlayroot_initramfs_script_present():
    return pathlib.Path("/usr/share/initramfs-tools/scripts/init-bottom/overlayroot").exists()


def armbian_overlay_module():
    paths = [
        pathlib.Path("/usr/lib/armbian-config/config.jobs.json"),
        pathlib.Path("/usr/lib/armbian-config/config.system.sh"),
    ]
    module_present = False
    for path in paths:
        if path.exists() and not path.is_symlink():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                text = ""
            if "module_overlayfs" in text and "overlayroot" in text:
                module_present = True
    return module_present


def unit_state(name):
    nrestarts = out(["systemctl", "show", name, "-p", "NRestarts", "--value"], 8)
    return {
        "active": out(["systemctl", "is-active", name], 8) or "unknown",
        "enabled": out(["systemctl", "is-enabled", name], 8) or "unknown",
        "nrestarts": int(nrestarts) if nrestarts.isdigit() else None,
    }


def failed_count():
    text = out(["systemctl", "list-units", "--failed", "--no-legend", "--no-pager"], 10)
    return len([line for line in text.splitlines() if line.strip()])


def first_json(paths):
    for raw in paths:
        path = pathlib.Path(raw)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            return data
    return {}


def apt_policy(name):
    result = run(["apt-cache", "policy", name], 15)
    text = "" if result is None else ((result.stdout or "") + "\n" + (result.stderr or ""))
    installed = "unknown"
    candidate = "unknown"
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("Installed:"):
            installed = line.split(":", 1)[1].strip()
        elif line.startswith("Candidate:"):
            candidate = line.split(":", 1)[1].strip()
    package_known = candidate not in {"", "unknown", "(none)"}
    return {
        "apt_cache_policy_available": result is not None,
        "apt_cache_policy_rc": None if result is None else result.returncode,
        "package_known_to_apt_cache": package_known,
        "installed_version_category": "none" if installed in {"(none)", "unknown", ""} else "present",
        "candidate_version_category": "none" if candidate in {"(none)", "unknown", ""} else "present",
        "raw_policy_published": False,
    }


def critical_package_name(name):
    return (
        name.startswith("linux-image")
        or name.startswith("linux-dtb")
        or name.startswith("linux-u-boot")
        or name.startswith("armbian-bsp")
    )


def holds():
    hold_text = out(["apt-mark", "showhold"], 12)
    held = {line.strip() for line in hold_text.splitlines() if line.strip()}
    pkg_text = out(["dpkg-query", "-W", "-f=${Package}\n"], 15)
    critical = {line.strip() for line in pkg_text.splitlines() if critical_package_name(line.strip())}
    held_critical = critical & held
    return {
        "hold_count": len(held),
        "critical_package_count": len(critical),
        "critical_held_count": len(held_critical),
        "kernel_packages_held": bool(critical) and critical == held_critical,
        "held_package_names_published": False,
    }


def parse_dry_run_text(text):
    install_names = []
    upgrade_names = []
    remove_names = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("Inst "):
            match = re.match(r"Inst\s+(\S+)(.*)", line)
            if not match:
                continue
            name = match.group(1)
            rest = match.group(2)
            if re.match(r"\s+\[", rest):
                upgrade_names.append(name)
            else:
                install_names.append(name)
        elif line.startswith("Remv "):
            parts = line.split()
            if len(parts) >= 2:
                remove_names.append(parts[1])
    touched = set(install_names + upgrade_names + remove_names)
    return {
        "would_install_count": len(install_names),
        "would_upgrade_count": len(upgrade_names),
        "would_remove_count": len(remove_names),
        "would_touch_kernel_packages": any(critical_package_name(name) for name in touched),
        "would_touch_package_names_published": False,
    }


def dry_run_install(name):
    result = run(["apt-get", "install", "--simulate", "--no-upgrade", "--no-install-recommends", name], 30)
    text = "" if result is None else ((result.stdout or "") + "\n" + (result.stderr or ""))
    parsed = parse_dry_run_text(text)
    rc = None if result is None else result.returncode
    parsed.update(
        {
            "dry_run_rc": rc,
            "dry_run_safe": bool(
                rc == 0
                and parsed["would_upgrade_count"] == 0
                and parsed["would_remove_count"] == 0
                and not parsed["would_touch_kernel_packages"]
            ),
            "raw_apt_output_published": False,
        }
    )
    return parsed


def install_prereq(name, dry_run):
    if not dry_run.get("dry_run_safe"):
        return {"install_attempted": False, "install_result": "blocked_unsafe_dry_run", "install_rc": None}
    result = run(["apt-get", "install", "-y", "--no-upgrade", "--no-install-recommends", name], 120)
    return {
        "install_attempted": True,
        "install_result": "passed" if result is not None and result.returncode == 0 else "failed",
        "install_rc": None if result is None else result.returncode,
        "raw_apt_output_published": False,
    }


def appliance_snapshot():
    status = first_json(("/tmp/dadooh-status/status.json", "/data/state/kiosky-player/launcher-status.json"))
    player = first_json(("/tmp/kiosky-status.json",))
    return {
        "public_state": status.get("public_state") or status.get("state") or "unknown",
        "playback": status.get("playback") or status.get("playback_state") or player.get("playback") or player.get("playback_state") or "unknown",
        "services": {
            "kiosky-player.service": unit_state("kiosky-player.service"),
            "totem-settings-trigger.service": unit_state("totem-settings-trigger.service"),
            "dadooh-visual-splash.service": unit_state("dadooh-visual-splash.service"),
        },
        "systemctl_failed_count": failed_count(),
    }


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


OUT.mkdir(parents=True, exist_ok=True)
OUT.chmod(0o700)
before = appliance_snapshot()
overlayroot_available_before = command_available("overlayroot")
overlayroot_chroot_available_before = command_available("overlayroot-chroot")
overlayroot_package_present_before = package_installed(PACKAGE)
overlayroot_initramfs_script_present_before = overlayroot_initramfs_script_present()
policy = apt_policy(PACKAGE)
hold_state = holds()
dry = dry_run_install(PACKAGE) if MODE in {"dry-run-install", "install-prereq"} else {
    "dry_run_rc": None,
    "dry_run_safe": False,
    "would_install_count": 0,
    "would_upgrade_count": 0,
    "would_remove_count": 0,
    "would_touch_kernel_packages": False,
    "raw_apt_output_published": False,
}
install_result = {"install_attempted": False, "install_result": "not_requested", "install_rc": None}
if MODE == "install-prereq":
    install_result = install_prereq(PACKAGE, dry)
after = appliance_snapshot()
overlayroot_available_after = command_available("overlayroot")
overlayroot_chroot_available_after = command_available("overlayroot-chroot")
overlayroot_package_present_after = package_installed(PACKAGE)
overlayroot_initramfs_script_present_after = overlayroot_initramfs_script_present()
payload = {
    "schema_version": "dadooh-c11.3.1-overlayroot-prereq.v1",
    "mode": MODE,
    "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "package_name": PACKAGE,
    "mechanism_detected": "armbian_config_module_overlayfs" if armbian_overlay_module() else "unknown",
    "armbian_module_overlayfs_present": armbian_overlay_module(),
    "overlayroot_available_before": overlayroot_available_before,
    "overlayroot_chroot_available_before": overlayroot_chroot_available_before,
    "overlayroot_package_present_before": overlayroot_package_present_before,
    "overlayroot_initramfs_script_present_before": overlayroot_initramfs_script_present_before,
    "apt_policy": policy,
    "apt_holds": hold_state,
    "dry_run": dry,
    "install": install_result,
    "overlayroot_available_after": overlayroot_available_after,
    "overlayroot_chroot_available_after": overlayroot_chroot_available_after,
    "overlayroot_package_present_after": overlayroot_package_present_after,
    "overlayroot_initramfs_script_present_after": overlayroot_initramfs_script_present_after,
    "package_install_required": not (overlayroot_chroot_available_after and overlayroot_package_present_after and overlayroot_initramfs_script_present_after),
    "can_enable_without_package_install": overlayroot_chroot_available_after and overlayroot_package_present_after and overlayroot_initramfs_script_present_after,
    "dry_run_safe": dry.get("dry_run_safe"),
    "installed": install_result["install_result"] == "passed",
    "kernel_packages_held": hold_state["kernel_packages_held"],
    "upgrades_attempted": False,
    "removes_attempted": False,
    "apt_update_attempted": False,
    "read_only_enabled": False,
    "power_cut_tested": False,
    "poweroff_executed": False,
    "reboot_executed": False,
    "writer_called": False,
    "real_config_read": False,
    "real_config_written": False,
    "wifi_changed": False,
    "networkmanager_profiles_changed": False,
    "raw_logs_published": False,
    "secrets_published": False,
    "before": before,
    "after": after,
}
payload["ready_for_c11_3_2_enablement"] = bool(
    payload["overlayroot_chroot_available_after"]
    and payload["overlayroot_package_present_after"]
    and payload["overlayroot_initramfs_script_present_after"]
    and payload["kernel_packages_held"]
    and after["public_state"] == "player_running"
    and after["playback"] == "playing"
    and after["systemctl_failed_count"] == 0
)
write_json(OUT / f"{MODE}.json", payload)
summary = [
    f"C11.3.1 {MODE}",
    f"package_name: {PACKAGE}",
    f"mechanism_detected: {payload['mechanism_detected']}",
    f"package_known_to_apt_cache: {str(policy['package_known_to_apt_cache']).lower()}",
    f"overlayroot_available_after: {str(payload['overlayroot_available_after']).lower()}",
    f"overlayroot_chroot_available_after: {str(payload['overlayroot_chroot_available_after']).lower()}",
    f"overlayroot_package_present_after: {str(payload['overlayroot_package_present_after']).lower()}",
    f"overlayroot_initramfs_script_present_after: {str(payload['overlayroot_initramfs_script_present_after']).lower()}",
    f"can_enable_without_package_install: {str(payload['can_enable_without_package_install']).lower()}",
    f"dry_run_safe: {str(payload['dry_run_safe']).lower()}",
    f"would_install_count: {dry.get('would_install_count')}",
    f"would_upgrade_count: {dry.get('would_upgrade_count')}",
    f"would_remove_count: {dry.get('would_remove_count')}",
    f"would_touch_kernel_packages: {str(dry.get('would_touch_kernel_packages')).lower()}",
    f"kernel_packages_held: {str(payload['kernel_packages_held']).lower()}",
    f"installed: {str(payload['installed']).lower()}",
    f"ready_for_c11_3_2_enablement: {str(payload['ready_for_c11_3_2_enablement']).lower()}",
    f"public_state: {after['public_state']}",
    f"playback: {after['playback']}",
    f"systemctl_failed_count: {after['systemctl_failed_count']}",
    "read_only_enabled: false",
    "power_cut_tested: false",
    "poweroff_executed: false",
    "reboot_executed: false",
    "writer_called: false",
    "real_config_read: false",
    "real_config_written: false",
    "wifi_changed: false",
    "networkmanager_profiles_changed: false",
    "upgrades_attempted: false",
    "raw_logs_published: false",
    "secrets_published: false",
]
(OUT / f"{MODE}-summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
(OUT / f"{MODE}-summary.txt").chmod(0o600)
if MODE == "install-prereq" and install_result["install_result"] != "passed":
    raise SystemExit(3)
PY
}

run_remote_mode() {
  local remote_mode="$1"
  prepare_local
  run_remote_python "$remote_mode"
  pull_remote_artifacts
  write_local_readme "$MODE-complete"
}

write_summary_from_latest() {
  prepare_local
  mkdir -p "$LOCAL_OUT_DIR/summary"
  chmod 700 "$LOCAL_OUT_DIR/summary"
  python3 - "$LOCAL_RUN_ROOT" "$LOCAL_OUT_DIR/summary/overlayroot-prereq-summary.json" "$LOCAL_OUT_DIR/summary/summary.txt" <<'PY'
import json, pathlib, sys, time
root = pathlib.Path(sys.argv[1])
out_json = pathlib.Path(sys.argv[2])
out_txt = pathlib.Path(sys.argv[3])
runs = []
for path in sorted(root.glob("*-c11-3-1-overlayroot-prereq/remote/*.json")):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    runs.append({
        "mode": data.get("mode"),
        "package_name": data.get("package_name"),
        "dry_run_safe": data.get("dry_run_safe"),
        "installed": data.get("installed"),
        "overlayroot_available_after": data.get("overlayroot_available_after"),
        "overlayroot_chroot_available_after": data.get("overlayroot_chroot_available_after"),
        "ready_for_c11_3_2_enablement": data.get("ready_for_c11_3_2_enablement"),
    })
payload = {
    "schema_version": "dadooh-c11.3.1-overlayroot-prereq-summary.v1",
    "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "runs_found": len(runs),
    "runs": runs[-10:],
    "read_only_enabled": False,
    "power_cut_tested": False,
    "poweroff_executed": False,
}
out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
out_json.chmod(0o600)
out_txt.write_text("C11.3.1 overlayroot prereq summary\nruns_found: %d\nread_only_enabled: false\npower_cut_tested: false\n" % len(runs), encoding="utf-8")
out_txt.chmod(0o600)
PY
  write_local_readme "summary-complete"
}

case "$MODE" in
  prepare-only)
    prepare_local
    write_local_readme "prepare-only-complete"
    ;;
  inspect)
    run_remote_mode inspect
    ;;
  apt-policy)
    run_remote_mode apt-policy
    ;;
  dry-run-install)
    run_remote_mode dry-run-install
    ;;
  install-prereq)
    run_remote_mode install-prereq
    ;;
  verify-prereq)
    run_remote_mode verify-prereq
    ;;
  summary)
    write_summary_from_latest
    ;;
esac
