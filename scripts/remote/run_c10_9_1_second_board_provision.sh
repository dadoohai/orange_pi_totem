#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
TIMESTAMP="${C10_9_1_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LOCAL_RUN_ROOT="${LOCAL_RUN_ROOT:-/tmp/dadooh-c10-9-1-second-board-provision}"
LOCAL_OUT_DIR="${C10_9_1_LOCAL_OUT_DIR:-$LOCAL_RUN_ROOT/$TIMESTAMP-c10-9-1-second-board-provision}"
REMOTE_ROOT="${REMOTE_ROOT:-/tmp/dadooh-c10-9-1-second-board-provision}"
REMOTE_REPO="$REMOTE_ROOT/repo-$TIMESTAMP"
REMOTE_OUT_DIR="$REMOTE_ROOT/out-$TIMESTAMP"
PRIVATE_VALUES="${PRIVATE_VALUES:-/tmp/dadooh-c10-9-1-private/private-values.json}"
SESSION_OUT="/tmp/dadooh-c10-9-1-open-settings/session"
WIZARD_OUT="/tmp/dadooh-c10-9-1-visual-wizard"
HANDOFF_OUT="/tmp/dadooh-c10-9-1-handoff"
WRITER_OUT="/tmp/dadooh-c10-9-1-writer"
PROVISION_CONFIRM_PHRASE="CONFIRMO PROVISIONAR CONFIG REAL C10.9.1 SEGUNDA PLACA"
REBOOT_CONFIRM_PHRASE="CONFIRMO REBOOT C10.9.1 SEGUNDA PLACA"
SSH_CONTROL_DIR="/tmp/dadooh-c10-9-1-ssh-$TIMESTAMP"
SSH_CONTROL_PATH="$SSH_CONTROL_DIR/%C"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_9_1_second_board_provision.sh <root@host> [mode] [options]

Modes:
  --prepare-only
  --refresh-install
  --verify-config-missing-visual
  --run-f10-candidate-only-check
  --prepare-private-template
  --validate-private-values
  --provision-real-config
  --verify-player
  --reboot-check

Options:
  --private-values /tmp/.../private-values.json
      Restricted private values file on the second board. The preferred
      product path is api_key-only when a real api_url source exists; for this
      development round, include api_url too if no versioned real default
      exists. Values are validated by totem_private_values_prepare.py and are
      never printed or copied.

  --local-out-dir /tmp/...

Rules:
  - host is an argument, never hardcoded;
  - never touches the dev board;
  - never copies config from the dev board;
  - never prints api_key, api_url, environment_id, SSID, password, IP, MAC or DNS;
  - never changes Wi-Fi/NetworkManager by itself;
  - never runs apt upgrade/full-upgrade/dist-upgrade/armbian-upgrade;
  - never calls writer except --provision-real-config after exact confirmation;
  - writes only sanitized artifacts under /tmp.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) MODE="prepare-only" ;;
    --refresh-install) MODE="refresh-install" ;;
    --verify-config-missing-visual) MODE="verify-config-missing-visual" ;;
    --run-f10-candidate-only-check) MODE="run-f10-candidate-only-check" ;;
    --prepare-private-template) MODE="prepare-private-template" ;;
    --validate-private-values) MODE="validate-private-values" ;;
    --provision-real-config) MODE="provision-real-config" ;;
    --verify-player) MODE="verify-player" ;;
    --reboot-check) MODE="reboot-check" ;;
    --private-values)
      shift
      PRIVATE_VALUES="${1:-}"
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
  prepare-only|refresh-install|verify-config-missing-visual|run-f10-candidate-only-check|prepare-private-template|validate-private-values|provision-real-config|verify-player|reboot-check) ;;
  *) echo "error: unsupported mode $MODE" >&2; exit 2 ;;
esac

if [ -z "$HOST" ]; then
  echo "error: host is required; pass root@<second-board-host>" >&2
  exit 2
fi

case "$LOCAL_OUT_DIR" in
  /tmp/*) ;;
  *) echo "error: --local-out-dir must be under /tmp" >&2; exit 2 ;;
esac

case "$PRIVATE_VALUES" in
  /tmp/*) ;;
  *) echo "error: --private-values must be under /tmp" >&2; exit 2 ;;
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

write_runner_summary() {
  local result="$1"
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  cat > "$LOCAL_OUT_DIR/README.md" <<EOF
# C10.9.1 remote runner artifact

- mode: \`$MODE\`
- result: \`$result\`
- repo_head: \`$LOCAL_HEAD\`
- repo_branch: \`$LOCAL_BRANCH\`
- source_dirty_entries: \`$LOCAL_DIRTY_COUNT\`
- host: \`<second-board-host>\`
- remote_workspace: \`/tmp/dadooh-c10-9-1-second-board-provision/...\`
- secrets_published: \`false\`
- config_content_published: \`false\`
- private_values_copied: \`false\`
- dev_board_touched: \`false\`
- dev_config_copied: \`false\`
- network_changed_by_runner: \`false\`
- broad_upgrade_called: \`false\`
EOF
}

prepare_local() {
  mkdir -p "$LOCAL_OUT_DIR"
  chmod 700 "$LOCAL_OUT_DIR"
  git -C "$REPO_ROOT" diff --check
  bash -n "$REPO_ROOT/scripts/remote/run_c10_9_1_second_board_provision.sh"
  bash -n "$REPO_ROOT/scripts/remote/run_c10_9_second_board_clean_install.sh"
  bash -n "$REPO_ROOT/scripts/board/install_totem_appliance.sh"
  bash -n "$REPO_ROOT/scripts/board/verify_totem_appliance.sh"
  bash -n "$REPO_ROOT/scripts/board/totem_open_settings_session.sh"
  python3 -m json.tool "$REPO_ROOT/scripts/board/totem_appliance_manifest.json" >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_private_values_prepare.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_setup_visual_wizard.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_splash.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_visual_setup_writer_handoff.py" --self-test >/dev/null
  python3 "$REPO_ROOT/scripts/board/totem_config_contract_validate.py" --self-test >/dev/null
}

copy_repo_subset() {
  ssh_board "rm -rf '$REMOTE_REPO' '$REMOTE_OUT_DIR' && mkdir -p '$REMOTE_REPO' '$REMOTE_OUT_DIR' '$REMOTE_ROOT' && chmod 700 '$REMOTE_ROOT' '$REMOTE_REPO' '$REMOTE_OUT_DIR'"
  tar -C "$REPO_ROOT" -czf - scripts/board scripts/remote docs/product/02_ROADMAP_IMPLEMENTACAO_PRODUTO.md docs/product/86_C10_8_INSTALADOR_IDEMPOTENTE_APPLIANCE.md docs/product/88_C10_9_SEGUNDA_PLACA_INSTALACAO_LIMPA.md \
    | ssh_board "tar -C '$REMOTE_REPO' -xzf -"
  ssh_board "printf '%s\n' '$LOCAL_HEAD' > '$REMOTE_REPO/.orange_pi_totem_head' && printf '%s\n' '$LOCAL_BRANCH' > '$REMOTE_REPO/.orange_pi_totem_branch' && printf '%s\n' '$LOCAL_DIRTY_COUNT' > '$REMOTE_REPO/.orange_pi_totem_dirty_entries' && chmod 600 '$REMOTE_REPO/.orange_pi_totem_head' '$REMOTE_REPO/.orange_pi_totem_branch' '$REMOTE_REPO/.orange_pi_totem_dirty_entries'"
}

remote_prepare_checks() {
  ssh_board "cd '$REMOTE_REPO' && bash -n scripts/board/install_totem_appliance.sh && bash -n scripts/board/verify_totem_appliance.sh && bash -n scripts/board/totem_open_settings_session.sh && bash -n scripts/remote/run_c10_9_1_second_board_provision.sh && python3 -m json.tool scripts/board/totem_appliance_manifest.json >/dev/null"
}

prepare_remote_workspace() {
  prepare_local
  copy_repo_subset
  remote_prepare_checks
}

pull_remote_artifacts() {
  mkdir -p "$LOCAL_OUT_DIR/remote"
  chmod 700 "$LOCAL_OUT_DIR/remote"
  scp_board -q -r "$HOST:$REMOTE_OUT_DIR/." "$LOCAL_OUT_DIR/remote/" || true
}

remote_inspect() {
  ssh_board "REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE'
set -euo pipefail
mkdir -p "$REMOTE_OUT_DIR/inspect"
chmod 700 "$REMOTE_OUT_DIR/inspect"
python3 - "$REMOTE_OUT_DIR/inspect/inspect.json" "$REMOTE_OUT_DIR/inspect/summary.txt" <<'PY'
import json
import pathlib
import subprocess
import time
import sys

json_out = pathlib.Path(sys.argv[1])
summary_out = pathlib.Path(sys.argv[2])

def run(args, timeout=6):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except Exception:
        return None

def out(args, timeout=6):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()

def load_public(path, keys):
    p = pathlib.Path(path)
    if not p.exists() or p.is_symlink():
        return {}, False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}, False
    if not isinstance(data, dict):
        return {}, False
    return {key: data.get(key) for key in keys if key in data}, True

def proc_count(pattern):
    result = run(["pgrep", "-fc", pattern], 5)
    if result is None or result.returncode not in {0, 1}:
        return 0
    try:
        return int((result.stdout or "0").strip() or "0")
    except ValueError:
        return 0

services = {
    name: {
        "active": out(["systemctl", "is-active", name], 5) or "unknown",
        "enabled": out(["systemctl", "is-enabled", name], 5) or "unknown",
        "nrestarts": out(["systemctl", "show", name, "-p", "NRestarts", "--value"], 5) or "unknown",
    }
    for name in ("kiosky-player.service", "totem-settings-trigger.service", "totem-open-settings.service", "dadooh-visual-splash.service")
}
launcher, launcher_ok = load_public("/data/state/kiosky-player/launcher-status.json", {"state", "config_missing", "config_state", "display_connected"})
public_status, public_ok = load_public("/tmp/dadooh-status/status.json", {"public_state", "config_state", "player_state", "playback_state", "error_code"})
player, player_ok = load_public("/tmp/kiosky-status.json", {"playback_state", "player_state", "config_missing", "error_code"})
failed_raw = out(["systemctl", "--failed", "--no-legend", "--plain"], 8)
failed_count = 0 if not failed_raw else len([line for line in failed_raw.splitlines() if line.strip()])
status_render_preview_present = pathlib.Path("/opt/totem/bin/totem_status_render_preview.py").exists()
manifest_installed = pathlib.Path("/data/state/totem-appliance/manifest-installed.json").exists()
config_present = pathlib.Path("/data/config/config.json").exists()
payload = {
    "schema_version": "dadooh-c10.9.1-inspect.v1",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "rules": {
        "config_content_read": False,
        "secrets_published": False,
        "network_changed": False,
        "writer_called": False,
        "raw_logs_collected": False,
    },
    "services": services,
    "systemctl_failed_count": failed_count,
    "config_real_present": config_present,
    "totem_status_render_preview_present": status_render_preview_present,
    "manifest_installed_present": manifest_installed,
    "launcher_status_parse_ok": launcher_ok,
    "launcher_public_fields": launcher,
    "public_status_parse_ok": public_ok,
    "public_status_fields": public_status,
    "player_status_parse_ok": player_ok,
    "player_public_fields": player,
    "process_counts": {
        "kiosk_process_count": proc_count("[k]iosk.py"),
        "mpv_process_count": proc_count("[m]pv"),
        "renderer_process_count": proc_count("[t]otem_status_renderer"),
        "setup_process_count": proc_count("[t]otem_setup_visual_wizard.py|[t]otem_setup_local_wizard.py"),
    },
    "runtime_flags": {
        "session_lock_present": pathlib.Path("/run/dadooh-settings/session.lock").exists(),
        "request_present": pathlib.Path("/run/dadooh-settings/request.json").exists(),
    },
}
json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
json_out.chmod(0o600)
summary_out.write_text(
    "\n".join([
        "C10.9.1 inspect summary",
        f"config_real_present={str(config_present).lower()}",
        f"totem_status_render_preview_present={str(status_render_preview_present).lower()}",
        f"systemctl_failed_count={failed_count}",
        f"launcher_state={launcher.get('state', 'unknown')}",
        f"public_state={public_status.get('public_state', 'unknown')}",
        f"mpv_process_count={payload['process_counts']['mpv_process_count']}",
        f"setup_process_count={payload['process_counts']['setup_process_count']}",
    ]) + "\n",
    encoding="utf-8",
)
summary_out.chmod(0o600)
print(f"inspect_json={json_out}")
PY
REMOTE
}

run_refresh_install() {
  prepare_remote_workspace
  remote_inspect
  ssh_board "cd '$REMOTE_REPO' && scripts/board/install_totem_appliance.sh --apply --repo-root '$REMOTE_REPO' --out-dir '$REMOTE_OUT_DIR/refresh-install'"
  ssh_board "cd '$REMOTE_REPO' && scripts/board/install_totem_appliance.sh --verify --repo-root '$REMOTE_REPO' --out-dir '$REMOTE_OUT_DIR/verify-after-refresh'"
  remote_inspect
  pull_remote_artifacts
  write_runner_summary "refresh-install-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

remote_verify_config_missing_visual() {
  ssh_board "REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE'
set -euo pipefail
mkdir -p "$REMOTE_OUT_DIR/config-missing-visual"
chmod 700 "$REMOTE_OUT_DIR/config-missing-visual"
python3 - "$REMOTE_OUT_DIR/config-missing-visual/visual.json" "$REMOTE_OUT_DIR/config-missing-visual/summary.txt" <<'PY'
import json
import pathlib
import subprocess
import time
import sys

json_out = pathlib.Path(sys.argv[1])
summary_out = pathlib.Path(sys.argv[2])

def run(args, timeout=8):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except Exception:
        return None

def out(args, timeout=8):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()

def load_json(path):
    p = pathlib.Path(path)
    if not p.exists() or p.is_symlink():
        return {}, False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}, False
    return (data if isinstance(data, dict) else {}), isinstance(data, dict)

def proc_count(pattern):
    result = run(["pgrep", "-fc", pattern], 5)
    if result is None or result.returncode not in {0, 1}:
        return 0
    try:
        return int((result.stdout or "0").strip() or "0")
    except ValueError:
        return 0

status_render_preview_present = pathlib.Path("/opt/totem/bin/totem_status_render_preview.py").exists()
aggregator_present = pathlib.Path("/opt/totem/bin/totem_status_aggregate.py").exists()
config_present = pathlib.Path("/data/config/config.json").exists()
aggregator_rc = 127
if aggregator_present:
    result = run([
        "python3",
        "/opt/totem/bin/totem_status_aggregate.py",
        "--launcher-status",
        "/data/state/kiosky-player/launcher-status.json",
        "--player-status",
        "/tmp/kiosky-status.json",
        "--out-dir",
        "/tmp/dadooh-status",
    ], 8)
    aggregator_rc = 999 if result is None else result.returncode
time.sleep(8)
status, status_ok = load_json("/tmp/dadooh-status/status.json")
svg_exists = pathlib.Path("/tmp/dadooh-status/status.svg").exists()
public_state = str(status.get("public_state") or status.get("state") or "unknown")
message = str(status.get("message") or "")
visual_message = "config_pending" if public_state == "config_missing" else public_state
renderer_count = proc_count("[t]otem_status_renderer")
mpv_count = proc_count("[m]pv")
stuck_starting = public_state == "starting_player" or "iniciando player" in message.lower()
config_missing_visual_ok = (
    not config_present
    and status_render_preview_present
    and aggregator_rc == 0
    and status_ok
    and svg_exists
    and public_state == "config_missing"
    and not stuck_starting
)
payload = {
    "schema_version": "dadooh-c10.9.1-config-missing-visual.v1",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "rules": {
        "config_content_read": False,
        "secrets_published": False,
        "network_changed": False,
        "writer_called": False,
    },
    "config_real_present": config_present,
    "totem_status_render_preview_present": status_render_preview_present,
    "status_aggregator_functional": aggregator_rc == 0,
    "status_json_present": status_ok,
    "status_svg_present": svg_exists,
    "public_state": public_state,
    "visual_message": visual_message,
    "stuck_starting_player": stuck_starting,
    "renderer_process_count": renderer_count,
    "mpv_process_count": mpv_count,
    "config_missing_visual_ok": config_missing_visual_ok,
}
json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
json_out.chmod(0o600)
summary_out.write_text(
    "\n".join([
        "C10.9.1 config-missing visual summary",
        f"config_real_present={str(config_present).lower()}",
        f"totem_status_render_preview_present={str(status_render_preview_present).lower()}",
        f"status_aggregator_functional={str(aggregator_rc == 0).lower()}",
        f"public_state={public_state}",
        f"visual_message={visual_message}",
        f"stuck_starting_player={str(stuck_starting).lower()}",
        f"config_missing_visual_ok={str(config_missing_visual_ok).lower()}",
    ]) + "\n",
    encoding="utf-8",
)
summary_out.chmod(0o600)
print(f"config_missing_visual_ok={str(config_missing_visual_ok).lower()}")
print(f"visual_json={json_out}")
PY
REMOTE
}

run_verify_config_missing_visual() {
  prepare_remote_workspace
  remote_verify_config_missing_visual
  pull_remote_artifacts
  write_runner_summary "verify-config-missing-visual-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

create_private_template_if_missing() {
  ssh_board "PRIVATE_VALUES='$PRIVATE_VALUES' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE'
set -euo pipefail
python3 "$REMOTE_REPO/scripts/board/totem_private_values_prepare.py" \
  --write-template \
  --path "$PRIVATE_VALUES" \
  --out-dir "$REMOTE_OUT_DIR/private-template" \
  --require-api-url
REMOTE
}

remote_validate_private_values() {
  ssh_board "PRIVATE_VALUES='$PRIVATE_VALUES' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE'
set -euo pipefail
python3 "$REMOTE_REPO/scripts/board/totem_private_values_prepare.py" \
  --validate \
  --path "$PRIVATE_VALUES" \
  --out-dir "$REMOTE_OUT_DIR/private-values-check" \
  --require-api-url
REMOTE
}

remote_sanitize_session_status() {
  ssh_board "REMOTE_OUT_DIR='$REMOTE_OUT_DIR' SESSION_OUT='$SESSION_OUT' WIZARD_OUT='$WIZARD_OUT' HANDOFF_OUT='$HANDOFF_OUT' WRITER_OUT='$WRITER_OUT' bash -s" <<'REMOTE'
set -euo pipefail
mkdir -p "$REMOTE_OUT_DIR/provision"
chmod 700 "$REMOTE_OUT_DIR/provision"
python3 - "$REMOTE_OUT_DIR/provision/provision.json" "$REMOTE_OUT_DIR/provision/summary.txt" "$SESSION_OUT" "$WIZARD_OUT" "$HANDOFF_OUT" "$WRITER_OUT" <<'PY'
import json
import pathlib
import stat
import subprocess
import sys
import time

json_out = pathlib.Path(sys.argv[1])
summary_out = pathlib.Path(sys.argv[2])
session_out = pathlib.Path(sys.argv[3])
wizard_out = pathlib.Path(sys.argv[4])
handoff_out = pathlib.Path(sys.argv[5])
writer_out = pathlib.Path(sys.argv[6])

def run(args, timeout=8):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except Exception:
        return None

def out(args, timeout=8):
    result = run(args, timeout)
    return "" if result is None else (result.stdout or "").strip()

def load(path):
    if not path.exists() or path.is_symlink():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}

def proc_count(pattern):
    result = run(["pgrep", "-fc", pattern], 5)
    if result is None or result.returncode not in {0, 1}:
        return 0
    try:
        return int((result.stdout or "0").strip() or "0")
    except ValueError:
        return 0

session = load(session_out / "session-status.json")
handoff = load(handoff_out / "setup-status.json")
writer = load(writer_out / "writer-status.json")
validation = load(session_out / "validate-real" / "validation-status.json")
config_path = pathlib.Path("/data/config/config.json")
backup_dir = pathlib.Path("/data/config/backups")
config_present = config_path.exists()
mode = None
owner_group_ok = False
totem_read_ok = False
totem_write_blocked = False
if config_present:
    mode = stat.S_IMODE(config_path.stat().st_mode)
    st = config_path.stat()
    try:
        import pwd, grp
        owner_group_ok = pwd.getpwuid(st.st_uid).pw_name == "root" and grp.getgrgid(st.st_gid).gr_name == "totem"
    except Exception:
        owner_group_ok = False
    totem_read_ok = subprocess.run(["runuser", "-u", "totem", "--", "test", "-r", str(config_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    totem_write_blocked = subprocess.run(["runuser", "-u", "totem", "--", "test", "-w", str(config_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0
public = load(pathlib.Path("/tmp/dadooh-status/status.json"))
player = load(pathlib.Path("/tmp/kiosky-status.json"))
launcher = load(pathlib.Path("/data/state/kiosky-player/launcher-status.json"))
services = {
    name: {
        "active": out(["systemctl", "is-active", name], 5) or "unknown",
        "enabled": out(["systemctl", "is-enabled", name], 5) or "unknown",
        "nrestarts": out(["systemctl", "show", name, "-p", "NRestarts", "--value"], 5) or "unknown",
    }
    for name in ("kiosky-player.service", "totem-settings-trigger.service", "totem-open-settings.service", "dadooh-visual-splash.service")
}
failed_raw = out(["systemctl", "--failed", "--no-legend", "--plain"], 8)
failed_count = 0 if not failed_raw else len([line for line in failed_raw.splitlines() if line.strip()])
public_state = str(public.get("public_state") or public.get("state") or launcher.get("state") or "unknown")
playback = str(player.get("playback_state") or public.get("playback_state") or "unknown")
failure_category = "none"
if public_state != "player_running":
    if public_state == "config_missing":
        failure_category = "config_missing"
    elif public_state == "player_error":
        failure_category = "player_error"
    elif config_present and services["kiosky-player.service"]["active"] != "active":
        failure_category = "service_not_active"
    elif config_present and proc_count("[k]iosk.py") == 0:
        failure_category = "app_not_running"
    else:
        failure_category = "unknown"
payload = {
    "schema_version": "dadooh-c10.9.1-provision.v1",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "rules": {
        "config_content_published": False,
        "private_values_copied": False,
        "secrets_published": False,
        "raw_logs_collected": False,
    },
    "environment_id_source": "wizard",
    "c5_real_dry_run": "passed" if handoff.get("contract_validation", {}).get("private_real_dry_run_passed") or validation.get("valid") else "unknown",
    "writer_called": bool(session.get("writer_called")) or bool(writer.get("write", {}).get("attempted")),
    "real_config_written": bool(session.get("real_config_written")) or bool(writer.get("write", {}).get("active_config_written")),
    "backup_created": bool(writer.get("backup", {}).get("created")),
    "config_present": config_present,
    "config_mode": f"{mode:04o}" if mode is not None else "missing",
    "config_owner_group_ok": owner_group_ok,
    "totem_read_ok": totem_read_ok,
    "totem_write_blocked": totem_write_blocked,
    "permissions_ok": config_present and mode == 0o640 and owner_group_ok and totem_read_ok and totem_write_blocked,
    "private_candidate_removed": not (handoff_out / "config.candidate.private.json").exists(),
    "session_private_values_removed": not pathlib.Path("/tmp/dadooh-c10-9-1-private/private-values.json").exists(),
    "public_state": public_state,
    "playback": playback,
    "failure_category": failure_category,
    "services": services,
    "process_counts": {
        "kiosk_process_count": proc_count("[k]iosk.py"),
        "mpv_process_count": proc_count("[m]pv"),
        "renderer_process_count": proc_count("[t]otem_status_renderer"),
        "setup_process_count": proc_count("[t]otem_setup_visual_wizard.py|[t]otem_setup_local_wizard.py"),
    },
    "systemctl_failed_count": failed_count,
}
json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
json_out.chmod(0o600)
summary_out.write_text(
    "\n".join([
        "C10.9.1 provision summary",
        f"environment_id_source={payload['environment_id_source']}",
        f"c5_real_dry_run={payload['c5_real_dry_run']}",
        f"writer_called={str(payload['writer_called']).lower()}",
        f"real_config_written={str(payload['real_config_written']).lower()}",
        f"backup_created={str(payload['backup_created']).lower()}",
        f"permissions_ok={str(payload['permissions_ok']).lower()}",
        f"private_candidate_removed={str(payload['private_candidate_removed']).lower()}",
        f"session_private_values_removed={str(payload['session_private_values_removed']).lower()}",
        f"public_state={public_state}",
        f"playback={playback}",
        f"failure_category={failure_category}",
        f"systemctl_failed_count={failed_count}",
    ]) + "\n",
    encoding="utf-8",
)
summary_out.chmod(0o600)
print(f"provision_json={json_out}")
PY
REMOTE
}

run_f10_candidate_only_check() {
  prepare_remote_workspace
  echo "This mode opens the visual settings session in candidate-only mode."
  echo "Use the board display/keyboard to save or cancel. It will not call writer."
  ssh_board "rm -rf '$SESSION_OUT' '$WIZARD_OUT' '$HANDOFF_OUT' '$WRITER_OUT'; /opt/totem/bin/totem_open_settings_session.sh --mode interactive --expect candidate_ready --tty 2 --timeout-sec 1800 --out-dir '$SESSION_OUT' --wizard-out-dir '$WIZARD_OUT' --handoff-out-dir '$HANDOFF_OUT' --writer-out-dir '$WRITER_OUT' --private-values '$PRIVATE_VALUES' --apply-mode candidate-only --private-source none --private-settings-context-path /data/state/totem-settings/last-settings.json"
  remote_sanitize_session_status
  remote_verify_config_missing_visual
  pull_remote_artifacts
  write_runner_summary "candidate-only-check-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_provision_real_config() {
  prepare_remote_workspace
  echo
  echo "Type exactly:"
  echo "$PROVISION_CONFIRM_PHRASE"
  printf '> '
  IFS= read -r typed
  if [ "$typed" != "$PROVISION_CONFIRM_PHRASE" ]; then
    echo "confirmation_mismatch" >&2
    exit 20
  fi
  create_private_template_if_missing
  set +e
  remote_validate_private_values
  validate_rc="$?"
  set -e
  if [ "$validate_rc" -ne 0 ]; then
    pull_remote_artifacts
    write_runner_summary "private-values-not-ready"
    echo "private_values_not_ready_fill_restricted_file_on_board" >&2
    exit "$validate_rc"
  fi
  set +e
  ssh_board "rm -rf '$SESSION_OUT' '$WIZARD_OUT' '$HANDOFF_OUT' '$WRITER_OUT'; /opt/totem/bin/totem_open_settings_session.sh --mode interactive --expect real_write_passed --tty 2 --timeout-sec 1800 --out-dir '$SESSION_OUT' --wizard-out-dir '$WIZARD_OUT' --handoff-out-dir '$HANDOFF_OUT' --writer-out-dir '$WRITER_OUT' --private-values '$PRIVATE_VALUES' --apply-mode real-write --private-source none --confirm-local-operator-save --private-settings-context-path /data/state/totem-settings/last-settings.json"
  session_rc="$?"
  set -e
  if [ "$session_rc" -ne 0 ]; then
    remote_sanitize_session_status || true
    remote_verify_config_missing_visual || true
    pull_remote_artifacts
    write_runner_summary "provision-real-config-session-failed"
    echo "provision_real_config_session_failed rc=$session_rc" >&2
    exit "$session_rc"
  fi
  ssh_board "rm -rf '$(dirname "$PRIVATE_VALUES")'"
  ssh_board "for i in \$(seq 1 60); do python3 /opt/totem/bin/totem_status_aggregate.py >/dev/null 2>&1 || true; sleep 2; state=\$(python3 - <<'PY'
import json, pathlib
for p in ('/tmp/dadooh-status/status.json','/data/state/kiosky-player/launcher-status.json'):
    try:
        data=json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
    except Exception:
        continue
    print(data.get('public_state') or data.get('state') or 'unknown')
    raise SystemExit
print('unknown')
PY
); [ \"\$state\" = player_running ] && break; done"
  remote_sanitize_session_status
  pull_remote_artifacts
  write_runner_summary "provision-real-config-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_prepare_private_template() {
  prepare_remote_workspace
  create_private_template_if_missing
  set +e
  remote_validate_private_values
  validate_rc="$?"
  set -e
  pull_remote_artifacts
  if [ "$validate_rc" -eq 0 ]; then
    write_runner_summary "private-template-ready"
  else
    write_runner_summary "private-template-created-or-needs-fill"
  fi
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
  exit 0
}

run_validate_private_values() {
  prepare_remote_workspace
  set +e
  remote_validate_private_values
  validate_rc="$?"
  set -e
  pull_remote_artifacts
  if [ "$validate_rc" -eq 0 ]; then
    write_runner_summary "private-values-valid"
  else
    write_runner_summary "private-values-invalid"
  fi
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
  exit "$validate_rc"
}

run_verify_player() {
  prepare_remote_workspace
  remote_sanitize_session_status
  pull_remote_artifacts
  write_runner_summary "verify-player-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

run_reboot_check() {
  prepare_remote_workspace
  echo
  echo "Type exactly:"
  echo "$REBOOT_CONFIRM_PHRASE"
  printf '> '
  IFS= read -r typed
  if [ "$typed" != "$REBOOT_CONFIRM_PHRASE" ]; then
    echo "confirmation_mismatch" >&2
    exit 20
  fi
  ssh_board "systemctl reboot"
  sleep 15
  for _ in $(seq 1 60); do
    if ssh_board "true" >/dev/null 2>&1; then
      break
    fi
    sleep 5
  done
  remote_sanitize_session_status
  pull_remote_artifacts
  write_runner_summary "reboot-check-complete"
  printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
}

case "$MODE" in
  prepare-only)
    prepare_local
    write_runner_summary "prepare-only-complete"
    printf 'artifacts=%s\n' "$LOCAL_OUT_DIR"
    ;;
  refresh-install) run_refresh_install ;;
  verify-config-missing-visual) run_verify_config_missing_visual ;;
  run-f10-candidate-only-check) run_f10_candidate_only_check ;;
  prepare-private-template) run_prepare_private_template ;;
  validate-private-values) run_validate_private_values ;;
  provision-real-config) run_provision_real_config ;;
  verify-player) run_verify_player ;;
  reboot-check) run_reboot_check ;;
esac
