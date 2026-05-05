#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
REMOTE_DIR="${REMOTE_DIR:-/tmp/dadooh-c10-5-3}"
REMOTE_OUT_DIR="${REMOTE_OUT_DIR:-/tmp/dadooh-c10-5-3-early-boot-visual-audit}"
APPLY_CONFIRM_PHRASE="${APPLY_CONFIRM_PHRASE:-CONFIRMO EARLY BOOT QUIET C10.5.3}"
ROLLBACK_CONFIRM_PHRASE="${ROLLBACK_CONFIRM_PHRASE:-CONFIRMO ROLLBACK EARLY BOOT QUIET C10.5.3}"
REBOOT_CONFIRM_PHRASE="${REBOOT_CONFIRM_PHRASE:-CONFIRMO REBOOT VISUAL EARLY BOOT C10.5.3}"
STATE_DIR="/data/state/totem-boot-visual"
STATE_FILE="$STATE_DIR/c10-5-3-boot-quiet-state.json"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_5_3_early_boot_visual_audit.sh <host> [mode]

Modes:
  --prepare-only
      Prepare temporary workspace and run non-mutating checks.

  --inspect
      Sanitized read-only inspection of early boot visual categories.

  --plan
      Produce a sanitized reversible change plan. Does not apply changes.

  --apply-reversible-boot-quiet
      Requires exact confirmation. Applies minimal reversible boot quieting.

  --rollback-reversible-boot-quiet
      Requires exact confirmation. Restores backup from recorded state.

  --reboot-visual-check
      Requires exact confirmation. Reboots once and collects sanitized state.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only)
      MODE="prepare-only"
      ;;
    --inspect)
      MODE="inspect"
      ;;
    --plan)
      MODE="plan"
      ;;
    --apply-reversible-boot-quiet)
      MODE="apply-reversible-boot-quiet"
      ;;
    --rollback-reversible-boot-quiet)
      MODE="rollback-reversible-boot-quiet"
      ;;
    --reboot-visual-check)
      MODE="reboot-visual-check"
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
  prepare-only|inspect|plan|apply-reversible-boot-quiet|rollback-reversible-boot-quiet|reboot-visual-check)
    ;;
  *)
    echo "error: unsupported mode $MODE" >&2
    exit 2
    ;;
esac

if [ -z "$HOST" ]; then
  echo "error: host is required; pass it explicitly, for example root@<board-host>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_SPLASH="$REPO_ROOT/scripts/board/totem_visual_splash.py"
LOCAL_C1052="$SCRIPT_DIR/run_c10_5_2_visual_guard_boot_shutdown.sh"

for path in "$LOCAL_SPLASH" "$LOCAL_C1052"; do
  if [ ! -f "$path" ]; then
    echo "error: missing local input" >&2
    exit 1
  fi
done

confirm_exact() {
  local expected="$1"
  local prompt="$2"
  echo
  echo "$prompt"
  echo "Type exactly:"
  echo "$expected"
  printf '> '
  IFS= read -r typed
  if [ "$typed" != "$expected" ]; then
    echo "confirmation_mismatch" >&2
    exit 20
  fi
}

prepare_remote() {
  echo "Preparing C10.5.3 early boot audit workspace on $HOST"
  ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR'"
  scp "$LOCAL_SPLASH" "$HOST:$REMOTE_DIR/"
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail
SPLASH="$REMOTE_DIR/totem_visual_splash.py"
OUT="$REMOTE_OUT_DIR/prepare"
mkdir -p "$OUT"
chmod 700 "$OUT"
python3 "$SPLASH" --self-test
python3 "$SPLASH" boot --status-out "$OUT/splash-boot-status.json" >/dev/null 2>&1 || true
python3 - "$OUT/splash-boot-status.json" <<'PY'
import json
import pathlib
import sys
status = pathlib.Path(sys.argv[1])
if status.exists():
    data = json.loads(status.read_text(encoding="utf-8"))
    assert data["real_config_read"] is False
    assert data["real_config_written"] is False
    assert data["writer_called"] is False
    assert data["wifi_changed"] is False
print("remote C10.5.3 prepare checks: ok")
PY
REMOTE_PREP
}

remote_python_common='
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import time

BOOT_ENV = pathlib.Path("/boot/armbianEnv.txt")
STATE_DIR = pathlib.Path("/data/state/totem-boot-visual")
STATE_FILE = STATE_DIR / "c10-5-3-boot-quiet-state.json"

def cmd(args):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False).stdout.strip()

def unit_state(unit):
    return {
        "active": cmd(["systemctl", "is-active", unit]) or "unknown",
        "enabled": cmd(["systemctl", "is-enabled", unit]) or "unknown",
    }

def parse_env(path=BOOT_ENV):
    result = {"exists": path.exists(), "is_symlink": path.is_symlink(), "pairs": {}, "line_count": 0}
    if not path.exists() or path.is_symlink():
        return result
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    result["line_count"] = len(lines)
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        result["pairs"][key.strip()] = value.strip()
    return result

def verbosity_category(value):
    if value is None:
        return "missing"
    try:
        numeric = int(value)
    except Exception:
        return "unknown"
    if numeric <= 0:
        return "quiet"
    if numeric <= 3:
        return "normal"
    return "verbose"

def console_category(value):
    if value is None:
        return "missing"
    lowered = value.strip().lower()
    if lowered in {"serial", "ttyS0", "ttyS2"} or "serial" in lowered:
        return "serial"
    if lowered == "display" or "display" in lowered:
        return "display"
    if lowered == "both" or "both" in lowered:
        return "both"
    return "unknown"

def token_set(value):
    return set((value or "").split())

def categorize_tokens(tokens):
    loglevel_value = None
    for token in tokens:
        if token.startswith("loglevel="):
            loglevel_value = token.split("=", 1)[1]
    loglevel_quiet = False
    if loglevel_value is not None:
        try:
            loglevel_quiet = int(loglevel_value) <= 3
        except Exception:
            loglevel_quiet = False
    return {
        "quiet_present": "quiet" in tokens,
        "loglevel_3_or_lower": loglevel_quiet,
        "loglevel_0": "loglevel=0" in tokens,
        "systemd_show_status_false": "systemd.show_status=false" in tokens,
        "rd_systemd_show_status_false": "rd.systemd.show_status=false" in tokens,
        "cursor_hidden": "vt.global_cursor_default=0" in tokens,
        "logo_hidden": "logo.nologo" in tokens,
        "consoleblank_present": any(token.startswith("consoleblank=") for token in tokens),
        "fsck_skip_present": "fsck.mode=skip" in tokens,
    }

def inspect_payload():
    env = parse_env()
    pairs = env["pairs"]
    extra_tokens = token_set(pairs.get("extraargs"))
    try:
        cmdline_tokens = set(pathlib.Path("/proc/cmdline").read_text(encoding="utf-8", errors="ignore").split())
    except Exception:
        cmdline_tokens = set()
    getty_units = {
        "getty@tty1.service": unit_state("getty@tty1.service"),
        "getty@tty2.service": unit_state("getty@tty2.service"),
    }
    failed = [line for line in cmd(["systemctl", "--failed", "--no-legend"]).splitlines() if line.strip()]
    orientation = pathlib.Path("/data/state/totem-display/orientation.json")
    c1052_state = pathlib.Path("/tmp/dadooh-c10-5-2-visual-guard-boot-shutdown/boot-visual-guardrails/state.json")
    return {
        "schema_version": "dadooh-c10.5.3-early-boot-inspect.v1",
        "boot_env_exists": env["exists"],
        "boot_env_symlink": env["is_symlink"],
        "boot_env_recognized": env["exists"] and not env["is_symlink"] and bool(set(pairs) & {"verbosity", "console", "extraargs", "rootdev", "overlay_prefix"}),
        "boot_env_line_count": env["line_count"],
        "armbian_verbosity_category": verbosity_category(pairs.get("verbosity")),
        "armbian_console_category": console_category(pairs.get("console")),
        "extraargs_categories": categorize_tokens(extra_tokens),
        "kernel_cmdline_categories": categorize_tokens(cmdline_tokens),
        "kernel_cmdline_console_display_or_tty_present": any(token.startswith("console=tty") for token in cmdline_tokens) or "console=display" in cmdline_tokens,
        "getty_units": getty_units,
        "getty_visible_category": "active_or_enabled" if any(item["active"] == "active" or item["enabled"] == "enabled" for item in getty_units.values()) else "not_active",
        "probable_hdmi_console_tty": "tty2" if getty_units["getty@tty2.service"]["active"] == "active" else ("tty1" if getty_units["getty@tty1.service"]["active"] == "active" else "unknown"),
        "systemd_show_status_apparent": "false" if ("systemd.show_status=false" in cmdline_tokens or "systemd.show_status=false" in extra_tokens) else "unknown",
        "visual_services": {
            "dadooh_visual_splash": unit_state("dadooh-visual-splash.service"),
            "kiosky_player": unit_state("kiosky-player.service"),
        },
        "orientation_public_present": orientation.exists() and not orientation.is_symlink(),
        "c10_5_2_rollback_state_present": c1052_state.exists() and not c1052_state.is_symlink(),
        "c10_5_3_rollback_state_present": STATE_FILE.exists() and not STATE_FILE.is_symlink(),
        "ssh_available": True,
        "systemctl_failed_count": len(failed),
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "wifi_changed": False,
        "raw_logs_written": False,
    }

def write_json(path, payload, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, mode)
    os.replace(tmp, path)
    os.chmod(path, mode)

def plan_payload():
    inspect = inspect_payload()
    can_modify = inspect["boot_env_recognized"] and not inspect["boot_env_symlink"]
    changes = []
    if can_modify and inspect["armbian_verbosity_category"] != "quiet":
        changes.append("set_verbosity_0")
    if can_modify and inspect["armbian_console_category"] in {"display", "both"}:
        changes.append("set_console_serial")
    if can_modify:
        for flag, name in [
            ("quiet_present", "add_quiet"),
            ("loglevel_0", "set_loglevel_0"),
            ("systemd_show_status_false", "add_systemd_show_status_false"),
            ("rd_systemd_show_status_false", "add_rd_systemd_show_status_false"),
            ("cursor_hidden", "hide_cursor"),
            ("logo_hidden", "hide_kernel_logo"),
        ]:
            if not inspect["extraargs_categories"].get(flag, False):
                changes.append(name)
    return {
        "schema_version": "dadooh-c10.5.3-early-boot-plan.v1",
        "apply_enabled": False,
        "requires_confirmation": "CONFIRMO EARLY BOOT QUIET C10.5.3",
        "rollback_confirmation": "CONFIRMO ROLLBACK EARLY BOOT QUIET C10.5.3",
        "reboot_confirmation": "CONFIRMO REBOOT VISUAL EARLY BOOT C10.5.3",
        "boot_env_recognized": inspect["boot_env_recognized"],
        "rollback_available_after_apply": can_modify,
        "planned_changes": changes,
        "preserve_ssh": True,
        "preserve_rollback": True,
        "fsck_not_disabled": True,
        "read_only_not_enabled": True,
        "power_cut_not_tested": True,
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "wifi_changed": False,
        "raw_logs_written": False,
    }

def update_boot_env_lines(lines):
    wanted_extra = [
        "quiet",
        "loglevel=0",
        "systemd.show_status=false",
        "rd.systemd.show_status=false",
        "vt.global_cursor_default=0",
        "logo.nologo",
    ]
    seen = {"verbosity": False, "console": False, "extraargs": False}
    updated = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            updated.append(line)
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key == "verbosity":
            updated.append("verbosity=0")
            seen["verbosity"] = True
        elif key == "console":
            updated.append("console=serial")
            seen["console"] = True
        elif key == "extraargs":
            current = [token for token in value.split() if not token.startswith("loglevel=")]
            for token in wanted_extra:
                if token not in current:
                    current.append(token)
            updated.append("extraargs=" + " ".join(current))
            seen["extraargs"] = True
        else:
            updated.append(line)
    if not seen["verbosity"]:
        updated.append("verbosity=0")
    if not seen["console"]:
        updated.append("console=serial")
    if not seen["extraargs"]:
        updated.append("extraargs=" + " ".join(wanted_extra))
    return updated

def apply_changes(target_status):
    inspect = inspect_payload()
    if not inspect["boot_env_recognized"] or inspect["boot_env_symlink"]:
        payload = {
            "schema_version": "dadooh-c10.5.3-early-boot-apply.v1",
            "changes_applied": False,
            "abort_reason": "boot_env_not_recognized",
            "rollback_available": False,
            "real_config_read": False,
            "real_config_written": False,
            "writer_called": False,
            "wifi_changed": False,
            "raw_logs_written": False,
        }
        write_json(target_status, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup = BOOT_ENV.with_name(f"{BOOT_ENV.name}.dadooh-c10-5-3.{timestamp}.bak")
    shutil.copy2(BOOT_ENV, backup)
    os.chmod(backup, 0o600)
    original_lines = BOOT_ENV.read_text(encoding="utf-8", errors="ignore").splitlines()
    new_lines = update_boot_env_lines(original_lines)
    BOOT_ENV.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    state = {
        "schema_version": "dadooh-c10.5.3-early-boot-quiet-state.v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "boot_env_path": str(BOOT_ENV),
        "boot_env_backup": str(backup),
        "rollback_available": True,
        "sensitive_data_present": False,
    }
    write_json(STATE_FILE, state)
    after = inspect_payload()
    payload = {
        "schema_version": "dadooh-c10.5.3-early-boot-apply.v1",
        "changes_applied": True,
        "rollback_available": True,
        "backup_created": True,
        "backup_permissions_restricted": stat.S_IMODE(backup.stat().st_mode) == 0o600,
        "armbian_verbosity_category_after": after["armbian_verbosity_category"],
        "armbian_console_category_after": after["armbian_console_category"],
        "extraargs_categories_after": after["extraargs_categories"],
        "reboot_required": True,
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "wifi_changed": False,
        "raw_logs_written": False,
    }
    write_json(target_status, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0

def rollback_changes(target_status):
    if not STATE_FILE.exists() or STATE_FILE.is_symlink():
        payload = {
            "schema_version": "dadooh-c10.5.3-early-boot-rollback.v1",
            "rollback_executed": False,
            "rollback_status": "state_missing",
            "real_config_read": False,
            "real_config_written": False,
            "writer_called": False,
            "wifi_changed": False,
            "raw_logs_written": False,
        }
        write_json(target_status, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    backup = pathlib.Path(state.get("boot_env_backup", ""))
    if not backup.exists() or backup.is_symlink():
        status = "backup_missing"
        executed = False
    else:
        shutil.copy2(backup, BOOT_ENV)
        executed = True
        status = "restored"
    payload = {
        "schema_version": "dadooh-c10.5.3-early-boot-rollback.v1",
        "rollback_executed": executed,
        "rollback_status": status,
        "service_active": cmd(["systemctl", "is-active", "kiosky-player.service"]) or "unknown",
        "service_enabled": cmd(["systemctl", "is-enabled", "kiosky-player.service"]) or "unknown",
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "wifi_changed": False,
        "raw_logs_written": False,
    }
    write_json(target_status, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if executed else 2

def process_counts():
    result = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
    self_pid = os.getpid()
    for proc in pathlib.Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == self_pid:
            continue
        try:
            parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
        except OSError:
            continue
        names = [pathlib.Path(part).name.lower() for part in parts]
        if "kiosk.py" in names:
            result["player"] += 1
        if any(name == "mpv" for name in names):
            result["mpv"] += 1
        if any("totem_status_renderer" in name for name in names):
            result["renderer"] += 1
        if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
            result["setup"] += 1
    return result

def public_status():
    if pathlib.Path("/opt/totem/bin/totem_status_aggregate.py").exists():
        subprocess.run(["python3", "/opt/totem/bin/totem_status_aggregate.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    try:
        data = json.loads(pathlib.Path("/tmp/dadooh-status/status.json").read_text(encoding="utf-8"))
        state = data.get("public_state") or data.get("state") or "unknown"
    except Exception:
        state = "unknown"
    try:
        status = json.loads(pathlib.Path("/tmp/kiosky-status.json").read_text(encoding="utf-8"))
        playback = status.get("playback_state") or status.get("playback", {}).get("state") or "unknown"
    except Exception:
        playback = "unknown"
    return state, playback

def kernel_critical_filter_count():
    text = subprocess.run(["journalctl", "-k", "-b", "--no-pager", "--no-hostname"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False).stdout
    patterns = [r"\\bOops\\b", r"kernel panic", r"EXT4-fs error", r"mmc.*timeout", r"mmc.*reset", r"I/O error"]
    return sum(1 for line in text.splitlines() if any(re.search(pattern, line, re.IGNORECASE) for pattern in patterns))

def reboot_status_payload(ssh_return_sec):
    for _ in range(60):
        state, playback = public_status()
        counts = process_counts()
        if state == "player_running" and playback == "playing" and counts["player"] >= 1 and counts["mpv"] >= 1:
            break
        time.sleep(2)
    state, playback = public_status()
    failed = [line for line in cmd(["systemctl", "--failed", "--no-legend"]).splitlines() if line.strip()]
    return {
        "schema_version": "dadooh-c10.5.3-early-boot-reboot-check.v1",
        "reboot_visual_check": True,
        "ssh_return_sec": ssh_return_sec,
        "service_active": cmd(["systemctl", "is-active", "kiosky-player.service"]) or "unknown",
        "service_enabled": cmd(["systemctl", "is-enabled", "kiosky-player.service"]) or "unknown",
        "nrestarts": cmd(["systemctl", "show", "kiosky-player.service", "-p", "NRestarts", "--value"]) or "unknown",
        "public_state": state,
        "playback": playback,
        "process_counts": process_counts(),
        "systemctl_failed_count": len(failed),
        "kernel_critical_filter_count": kernel_critical_filter_count(),
        "early_boot_linux_visible": "human_observation_required",
        "visible_phase": "human_observation_required",
        "duration_bucket": "human_observation_required",
        "rollback_needed": "human_observation_required",
        "read_only_not_enabled": True,
        "power_cut_not_tested": True,
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "wifi_changed": False,
        "raw_logs_written": False,
    }
'

run_remote_python() {
  local code="$1"
  ssh "$HOST" "REMOTE_OUT_DIR='$REMOTE_OUT_DIR' STATE_FILE='$STATE_FILE' STATE_DIR='$STATE_DIR' python3 - <<'REMOTE_PY'
$remote_python_common
$code
REMOTE_PY"
}

run_inspect() {
  run_remote_python '
target = pathlib.Path(os.environ["REMOTE_OUT_DIR"]) / "inspect" / "status.json"
payload = inspect_payload()
write_json(target, payload)
print(json.dumps(payload, indent=2, sort_keys=True))
'
}

run_plan() {
  run_remote_python '
target = pathlib.Path(os.environ["REMOTE_OUT_DIR"]) / "plan" / "plan.json"
payload = plan_payload()
write_json(target, payload)
print(json.dumps(payload, indent=2, sort_keys=True))
'
}

run_apply() {
  confirm_exact "$APPLY_CONFIRM_PHRASE" "Aplicar ajustes reversiveis de early boot quiet. Nao reboota automaticamente."
  run_remote_python '
target = pathlib.Path(os.environ["REMOTE_OUT_DIR"]) / "apply-reversible-boot-quiet" / "status.json"
raise SystemExit(apply_changes(target))
'
}

run_rollback() {
  confirm_exact "$ROLLBACK_CONFIRM_PHRASE" "Restaurar backup dos ajustes early boot quiet."
  run_remote_python '
target = pathlib.Path(os.environ["REMOTE_OUT_DIR"]) / "rollback-reversible-boot-quiet" / "status.json"
raise SystemExit(rollback_changes(target))
'
}

run_reboot_visual_check() {
  confirm_exact "$REBOOT_CONFIRM_PHRASE" "Reboot controlado C10.5.3. Nao executa corte seco e nao altera config/Wi-Fi."
  local started
  local host_target
  started="$(date +%s)"
  host_target="${HOST#*@}"
  host_target="${host_target%%:*}"
  ssh "$HOST" "mkdir -p '$REMOTE_OUT_DIR/reboot-visual-check' && chmod 700 '$REMOTE_OUT_DIR/reboot-visual-check' && systemctl reboot" || true
  echo "Waiting for SSH to return"
  for _ in $(seq 1 120); do
    if python3 - "$host_target" <<'PY' >/dev/null 2>&1
import socket
import sys
with socket.create_connection((sys.argv[1], 22), timeout=5):
    pass
PY
    then
      break
    fi
    sleep 3
  done
  local returned
  returned="$(date +%s)"
  local collect_rc=1
  for _ in $(seq 1 30); do
    if ssh "$HOST" "REMOTE_OUT_DIR='$REMOTE_OUT_DIR' SSH_RETURN_SEC='$((returned - started))' python3 - <<'REMOTE_PY'
$remote_python_common
target = pathlib.Path(os.environ['REMOTE_OUT_DIR']) / 'reboot-visual-check' / 'status.json'
payload = reboot_status_payload(os.environ.get('SSH_RETURN_SEC', 'unknown'))
write_json(target, payload)
print(json.dumps(payload, indent=2, sort_keys=True))
REMOTE_PY"
    then
      collect_rc=0
      break
    fi
    sleep 5
  done
  if [ "$collect_rc" -ne 0 ]; then
    echo "reboot_visual_status_collection_failed" >&2
    exit 1
  fi
}

prepare_remote

case "$MODE" in
  prepare-only)
    echo "C10.5.3 prepare-only complete. Evidence dir reserved: $REMOTE_OUT_DIR"
    ;;
  inspect)
    run_inspect
    ;;
  plan)
    run_plan
    ;;
  apply-reversible-boot-quiet)
    run_apply
    ;;
  rollback-reversible-boot-quiet)
    run_rollback
    ;;
  reboot-visual-check)
    run_reboot_visual_check
    ;;
esac

echo "C10.5.3 early boot visual audit mode complete: $MODE"
