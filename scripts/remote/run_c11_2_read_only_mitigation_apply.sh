#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
CONFIRMATION="${C11_2_CONFIRMATION:-}"
TIMESTAMP="${C11_2_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-/tmp/dadooh-c11-2-read-only-mitigation}"
LOCAL_OUT_DIR="${C11_2_LOCAL_OUT_DIR:-$LOCAL_RUN_ROOT/$TIMESTAMP-c11-2-read-only-mitigation-apply}"
REMOTE_ROOT="${REMOTE_ROOT:-/tmp/dadooh-c11-2-read-only-mitigation}"
REMOTE_WORK="$REMOTE_ROOT/work-$TIMESTAMP"
REMOTE_OUT="$REMOTE_ROOT/out-$TIMESTAMP"
SSH_CONTROL_DIR="/tmp/dadooh-c11-2-ssh-$TIMESTAMP"
SSH_CONTROL_PATH="$SSH_CONTROL_DIR/%C"

APPLY_CONFIRMATION="CONFIRMO APPLY MITIGACOES READONLY C11.2 NA DEV"
REBOOT_CONFIRMATION="CONFIRMO REBOOT C11.2 DEV"

usage() {
  cat <<'USAGE'
Usage:
  run_c11_2_read_only_mitigation_apply.sh <root@host> [mode] [options]

Modes:
  --prepare-only
  --inspect
  --dry-run
  --apply-dev
  --verify
  --rollback
  --reboot-check

Options:
  --confirm "CONFIRMO ..."
  --local-out-dir /tmp/...

Rules:
  - dev board only for C11.2;
  - --inspect and --dry-run do not alter the board;
  - --apply-dev requires: CONFIRMO APPLY MITIGACOES READONLY C11.2 NA DEV;
  - --reboot-check requires: CONFIRMO REBOOT C11.2 DEV;
  - does not enable root read-only, power-cut, poweroff, writer, config write,
    Wi-Fi change, NetworkManager profile change, package install or test board;
  - never publishes raw logs, config, secrets, SSID, IP, MAC, DNS, gateway,
    hostname or NetworkManager profile names.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --inspect) MODE="inspect" ;;
    --dry-run) MODE="dry-run" ;;
    --apply-dev) MODE="apply-dev" ;;
    --verify) MODE="verify" ;;
    --rollback) MODE="rollback" ;;
    --reboot-check) MODE="reboot-check" ;;
    --confirm)
      shift
      CONFIRMATION="${1:-}"
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
  prepare-only|inspect|dry-run|apply-dev|verify|rollback|reboot-check) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ "$MODE" != "prepare-only" ] && [ -z "$HOST" ]; then
  echo "error: host is required for $MODE" >&2
  exit 2
fi

if [ "$MODE" = "apply-dev" ] && [ "$CONFIRMATION" != "$APPLY_CONFIRMATION" ]; then
  echo "error: apply-dev requires exact confirmation" >&2
  exit 2
fi

if [ "$MODE" = "reboot-check" ] && [ "$CONFIRMATION" != "$REBOOT_CONFIRMATION" ]; then
  echo "error: reboot-check requires exact confirmation" >&2
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
  bash -n "$REPO_ROOT/scripts/remote/run_c11_2_read_only_mitigation_apply.sh"
  bash -n "$REPO_ROOT/scripts/remote/run_c11_1_read_only_policy_probe.sh"
  bash -n "$REPO_ROOT/scripts/board/verify_totem_read_only_policy.sh"
  python3 -m json.tool "$REPO_ROOT/scripts/board/totem_read_only_policy.json" >/dev/null
  "$REPO_ROOT/scripts/board/verify_totem_read_only_policy.sh" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_wifi_nm_adapter.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_config_contract_validate.py" --self-test >/dev/null
}

write_local_readme() {
  local result="$1"
  local reboot_executed="false"
  if [ "$MODE" = "reboot-check" ]; then
    reboot_executed="true"
  fi
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  cat > "$LOCAL_OUT_DIR/README.md" <<EOF
# C11.2 read-only mitigation runner artifact

- mode: \`$MODE\`
- result: \`$result\`
- repo_head: \`$LOCAL_HEAD\`
- repo_branch: \`$LOCAL_BRANCH\`
- source_dirty_entries: \`$LOCAL_DIRTY_COUNT\`
- host: \`<dev-board>\`
- remote_workspace: \`/tmp/dadooh-c11-2-read-only-mitigation/...\`
- test_board_touched: \`false\`
- read_only_enabled: \`false\`
- power_cut_tested: \`false\`
- reboot_executed: \`$reboot_executed\`
- poweroff_executed: \`false\`
- writer_called: \`false\`
- real_config_read: \`false\`
- real_config_written: \`false\`
- wifi_changed: \`false\`
- networkmanager_profiles_changed: \`false\`
- packages_installed: \`false\`
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

copy_helpers() {
  ssh_board "mkdir -p '$REMOTE_WORK' '$REMOTE_OUT' && chmod 700 '$REMOTE_ROOT' '$REMOTE_WORK' '$REMOTE_OUT'"
  scp_board -q \
    "$REPO_ROOT/scripts/board/verify_totem_read_only_policy.sh" \
    "$REPO_ROOT/scripts/board/totem_read_only_policy.json" \
    "$HOST:$REMOTE_WORK/"
  ssh_board "chmod 700 '$REMOTE_WORK/verify_totem_read_only_policy.sh'"
}

run_remote_verify() {
  ssh_board "'$REMOTE_WORK/verify_totem_read_only_policy.sh' --policy '$REMOTE_WORK/totem_read_only_policy.json' --out-dir '$REMOTE_OUT/verify-$1'"
}

run_remote_python() {
  local remote_mode="$1"
  ssh_board "REMOTE_MODE='$remote_mode' REMOTE_OUT='$REMOTE_OUT' python3 -" <<'PY'
import json
import os
import pathlib
import shutil
import stat
import subprocess
import time

MODE = os.environ["REMOTE_MODE"]
OUT = pathlib.Path(os.environ["REMOTE_OUT"])
STATE = pathlib.Path("/data/state/totem-read-only-mitigation")
BACKUPS = STATE / "backups"
DROPIN_DIR = pathlib.Path("/etc/systemd/journald.conf.d")
DROPIN = DROPIN_DIR / "90-dadooh-volatile.conf"
ROLLBACK = STATE / "rollback-state.json"
APPLY_STATE = STATE / "apply-state.json"
NM_STATE = STATE / "networkmanager-policy.json"
VAR_STATE = STATE / "var-policy.json"
BOOT_ETC_STATE = STATE / "boot-etc-policy.json"
DROPIN_TEXT = """# Dadooh C11.2 read-only mitigation.
# Volatile journald avoids persistent raw system logs on the root filesystem.
[Journal]
Storage=volatile
RuntimeMaxUse=64M
Compress=yes
"""


def run(args, timeout=8):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except Exception:
        return None


def out(args, timeout=8):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()


def unit_state(name):
    nrestarts = out(["systemctl", "show", name, "-p", "NRestarts", "--value"])
    return {
        "active": out(["systemctl", "is-active", name]) or "unknown",
        "enabled": out(["systemctl", "is-enabled", name]) or "unknown",
        "nrestarts": int(nrestarts) if nrestarts.isdigit() else None,
    }


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


def journald_storage():
    paths = [pathlib.Path("/etc/systemd/journald.conf")]
    conf_dir = pathlib.Path("/etc/systemd/journald.conf.d")
    if conf_dir.exists() and conf_dir.is_dir() and not conf_dir.is_symlink():
        paths.extend(sorted(conf_dir.glob("*.conf")))
    storage = "default"
    for conf in paths:
        if not conf.exists() or conf.is_symlink():
            continue
        try:
            lines = conf.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            storage = "unknown"
            continue
        for raw in lines:
            line = raw.strip()
            if line and not line.startswith("#") and line.startswith("Storage="):
                storage = line.split("=", 1)[1].strip() or "default"
    return storage


def failed_count():
    text = out(["systemctl", "list-units", "--failed", "--no-legend", "--no-pager"], 10)
    return len([line for line in text.splitlines() if line.strip()])


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def snapshot():
    status = first_json(("/tmp/dadooh-status/status.json", "/data/state/kiosky-player/launcher-status.json"))
    player = first_json(("/tmp/kiosky-status.json",))
    return {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "public_state": status.get("public_state") or status.get("state") or "unknown",
        "playback": status.get("playback") or status.get("playback_state") or player.get("playback") or player.get("playback_state") or "unknown",
        "services": {
            "kiosky-player.service": unit_state("kiosky-player.service"),
            "totem-settings-trigger.service": unit_state("totem-settings-trigger.service"),
            "dadooh-visual-splash.service": unit_state("dadooh-visual-splash.service"),
        },
        "systemctl_failed_count": failed_count(),
        "journald_storage": journald_storage(),
        "journald_dropin_present": DROPIN.exists(),
        "rollback_state_present": ROLLBACK.exists(),
        "nm_policy_state_present": NM_STATE.exists(),
        "var_policy_state_present": VAR_STATE.exists(),
        "boot_etc_policy_state_present": BOOT_ETC_STATE.exists(),
    }


def planned_actions():
    actions = []
    if not DROPIN.exists() or DROPIN.read_text(encoding="utf-8", errors="ignore") != DROPIN_TEXT:
        actions.append("write_journald_volatile_dropin")
    if not NM_STATE.exists():
        actions.append("write_networkmanager_maintenance_policy_state")
    if not VAR_STATE.exists():
        actions.append("write_var_runtime_policy_state")
    if not BOOT_ETC_STATE.exists():
        actions.append("write_boot_etc_policy_state")
    if not ROLLBACK.exists():
        actions.append("write_rollback_state")
    actions.append("verify_policy")
    return actions


def policy_state(policy_id, selected_policy):
    return {
        "schema_version": "dadooh-c11.2-policy-state.v1",
        "updated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "policy_id": policy_id,
        "selected_policy": selected_policy,
        "read_only_enabled": False,
        "power_cut_tested": False,
        "raw_logs_published": False,
        "secrets_published": False,
    }


def apply():
    STATE.mkdir(parents=True, exist_ok=True)
    STATE.chmod(0o700)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    BACKUPS.chmod(0o700)
    rollback = {
        "schema_version": "dadooh-c11.2-read-only-mitigation-rollback.v1",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "journald_dropin_path": str(DROPIN),
        "journald_dropin_existed_before": DROPIN.exists(),
        "journald_dropin_backup": None,
        "networkmanager_profiles_changed": False,
        "wifi_changed": False,
        "boot_changed": False,
        "config_changed": False,
    }
    if DROPIN.exists() and not DROPIN.is_symlink():
        backup = BACKUPS / "90-dadooh-volatile.conf.before-c11-2"
        shutil.copy2(DROPIN, backup)
        backup.chmod(0o600)
        rollback["journald_dropin_backup"] = str(backup)
    DROPIN_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DROPIN.with_name(".90-dadooh-volatile.conf.tmp")
    tmp.write_text(DROPIN_TEXT, encoding="utf-8")
    tmp.chmod(0o644)
    os.replace(tmp, DROPIN)
    write_json(ROLLBACK, rollback)
    write_json(
        NM_STATE,
        policy_state(
            "nm_profiles_maintenance_window",
            "NetworkManager profiles remain in native /etc path; profile writes are allowed only inside a future controlled maintenance window.",
        ),
    )
    write_json(
        VAR_STATE,
        policy_state(
            "var_runtime_state_volatile",
            "/var runtime state remains system/volatile policy for C11.3 validation; product state stays in /data.",
        ),
    )
    write_json(
        BOOT_ETC_STATE,
        policy_state(
            "boot_etc_installer_maintenance_only",
            "/boot and /etc are immutable in normal runtime; installer/maintenance writes require backup and rollback.",
        ),
    )
    write_json(
        APPLY_STATE,
        {
            "schema_version": "dadooh-c11.2-read-only-mitigation-apply.v1",
            "status": "applied",
            "applied_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "journald_policy": "volatile",
            "journald_runtime_restarted": False,
            "read_only_enabled": False,
            "power_cut_tested": False,
            "writer_called": False,
            "real_config_written": False,
            "networkmanager_profiles_changed": False,
            "wifi_changed": False,
        },
    )


def rollback():
    state = {}
    if ROLLBACK.exists() and not ROLLBACK.is_symlink():
        try:
            state = json.loads(ROLLBACK.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    existed = bool(state.get("journald_dropin_existed_before"))
    backup = state.get("journald_dropin_backup")
    if existed and backup and pathlib.Path(backup).exists() and not pathlib.Path(backup).is_symlink():
        shutil.copy2(backup, DROPIN)
        DROPIN.chmod(0o644)
    elif DROPIN.exists() and not DROPIN.is_symlink():
        DROPIN.unlink()
    for path in (APPLY_STATE, NM_STATE, VAR_STATE, BOOT_ETC_STATE, ROLLBACK):
        if path.exists() and not path.is_symlink():
            path.unlink()


OUT.mkdir(parents=True, exist_ok=True)
OUT.chmod(0o700)
before = snapshot()
result = {
    "schema_version": "dadooh-c11.2-read-only-mitigation-run.v1",
    "mode": MODE,
    "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "read_only_enabled": False,
    "power_cut_tested": False,
    "poweroff_executed": False,
    "reboot_executed": False,
    "writer_called": False,
    "real_config_read": False,
    "real_config_written": False,
    "wifi_changed": False,
    "networkmanager_profiles_changed": False,
    "packages_installed": False,
    "raw_logs_published": False,
    "secrets_published": False,
    "before": before,
    "planned_actions": planned_actions(),
    "apply_executed": False,
    "rollback_executed": False,
}
if MODE == "apply":
    apply()
    result["apply_executed"] = True
elif MODE == "rollback":
    rollback()
    result["rollback_executed"] = True
after = snapshot()
result["after"] = after
result["journald_policy"] = "volatile" if after["journald_storage"] == "volatile" else "not_applied"
result["rollback_available"] = after["rollback_state_present"]
result["ready_for_c11_3_enablement"] = bool(
    after["journald_storage"] == "volatile"
    and after["rollback_state_present"]
    and after["nm_policy_state_present"]
    and after["var_policy_state_present"]
    and after["boot_etc_policy_state_present"]
)
write_json(OUT / f"{MODE}.json", result)
summary = [
    f"C11.2 {MODE}",
    f"apply_executed: {str(result['apply_executed']).lower()}",
    f"rollback_executed: {str(result['rollback_executed']).lower()}",
    f"journald_policy: {result['journald_policy']}",
    f"rollback_available: {str(result['rollback_available']).lower()}",
    f"ready_for_c11_3_enablement: {str(result['ready_for_c11_3_enablement']).lower()}",
    f"public_state: {after['public_state']}",
    f"playback: {after['playback']}",
    f"systemctl_failed_count: {after['systemctl_failed_count']}",
    "read_only_enabled: false",
    "power_cut_tested: false",
    "writer_called: false",
    "real_config_read: false",
    "real_config_written: false",
    "wifi_changed: false",
    "networkmanager_profiles_changed: false",
    "raw_logs_published: false",
]
(OUT / f"{MODE}-summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
(OUT / f"{MODE}-summary.txt").chmod(0o600)
PY
}

run_reboot_check() {
  prepare_local
  copy_helpers
  run_remote_verify before-reboot
  ssh_board "REMOTE_OUT='$REMOTE_OUT' python3 -" <<'PY'
import json, pathlib, time
out = pathlib.Path(__import__("os").environ["REMOTE_OUT"])
payload = {
  "schema_version": "dadooh-c11.2-reboot-check.v1",
  "reboot_requested_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "read_only_enabled": False,
  "power_cut_tested": False,
  "poweroff_executed": False
}
(out / "reboot-request.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(out / "reboot-request.json").chmod(0o600)
PY
  ssh_board "systemctl reboot" || true
  sleep 25
  ssh_board "true"
  copy_helpers
  run_remote_verify after-reboot
  pull_remote_artifacts
  write_local_readme "reboot-check-complete"
}

run_remote_mode() {
  local remote_mode="$1"
  prepare_local
  copy_helpers
  if [ "$remote_mode" = "inspect" ] || [ "$remote_mode" = "dry-run" ]; then
    run_remote_python "$remote_mode"
  elif [ "$remote_mode" = "apply" ]; then
    run_remote_python "apply"
  elif [ "$remote_mode" = "rollback" ]; then
    run_remote_python "rollback"
  fi
  run_remote_verify "$remote_mode"
  pull_remote_artifacts
  write_local_readme "$MODE-complete"
}

case "$MODE" in
  prepare-only)
    prepare_local
    write_local_readme "prepare-only-complete"
    ;;
  inspect)
    run_remote_mode inspect
    ;;
  dry-run)
    run_remote_mode dry-run
    ;;
  apply-dev)
    run_remote_mode apply
    ;;
  verify)
    prepare_local
    copy_helpers
    run_remote_verify current
    pull_remote_artifacts
    write_local_readme "verify-complete"
    ;;
  rollback)
    run_remote_mode rollback
    ;;
  reboot-check)
    run_reboot_check
    ;;
esac
