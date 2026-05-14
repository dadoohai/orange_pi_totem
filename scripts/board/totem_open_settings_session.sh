#!/usr/bin/env bash
set -euo pipefail

MODE="interactive"
EXPECTED_RESULT="any"
REMOTE_TTY="2"
RUN_TIMEOUT_SEC="1800"
PREVIEW_SEC="12"
OUT_DIR="/tmp/dadooh-c10-6-open-settings-session"
WIZARD_OUT_DIR="/tmp/dadooh-c10-6-visual-wizard-session"
HANDOFF_OUT_DIR="/tmp/dadooh-c10-6-2-handoff"
WRITER_OUT_DIR="/tmp/dadooh-c10-6-2-writer"
PRIVATE_VALUES="/tmp/dadooh-c10-6-2-private/private-values.json"
APPLY_POLICY_PATH="/run/dadooh-settings/apply-policy.json"
REQUEST_DIR="/run/dadooh-settings"
APPLY_MODE="policy"
PRIVATE_SOURCE="none"
ACTIVE_CONFIG_PRIVATE_SOURCE_CONFIRMED="false"
LOCAL_OPERATOR_SAVE_CONFIRMED="false"
PRIVATE_SETTINGS_CONTEXT_PATH="/data/state/totem-settings/last-settings.json"
LOCK_DIR="/run/totem/settings-session.lock"
RESTORE_GETTY_AFTER_SETTINGS="${TOTEM_RESTORE_GETTY_AFTER_SETTINGS:-0}"
TOTEM_C17_4_FIRSTBOOT_TRACE_DIR="${TOTEM_C17_4_FIRSTBOOT_TRACE_DIR:-/data/state/totem-debug/c17-4-firstboot}"

usage() {
  cat <<'USAGE'
Usage:
  totem_open_settings_session.sh [--mode preview|interactive] [--expect preview|cancelled|candidate_ready|any] [--tty N] [--timeout-sec N] [--preview-sec N] [--out-dir /tmp/...] [--apply-mode policy|candidate-only|dry-run|real-write] [--request-dir /run/...]

Opens the existing visual setup wizard as "Configuracoes do Totem" while the
player is running. By default it does not call writer. Real write requires a
restricted policy file created by an authorized runner.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode)
      shift
      MODE="${1:-}"
      ;;
    --expect)
      shift
      EXPECTED_RESULT="${1:-}"
      ;;
    --tty)
      shift
      REMOTE_TTY="${1:-}"
      ;;
    --timeout-sec)
      shift
      RUN_TIMEOUT_SEC="${1:-}"
      ;;
    --preview-sec)
      shift
      PREVIEW_SEC="${1:-}"
      ;;
    --out-dir)
      shift
      OUT_DIR="${1:-}"
      ;;
    --wizard-out-dir)
      shift
      WIZARD_OUT_DIR="${1:-}"
      ;;
    --handoff-out-dir)
      shift
      HANDOFF_OUT_DIR="${1:-}"
      ;;
    --writer-out-dir)
      shift
      WRITER_OUT_DIR="${1:-}"
      ;;
    --private-values)
      shift
      PRIVATE_VALUES="${1:-}"
      ;;
    --apply-policy-path)
      shift
      APPLY_POLICY_PATH="${1:-}"
      ;;
    --request-dir)
      shift
      REQUEST_DIR="${1:-}"
      ;;
    --apply-mode)
      shift
      APPLY_MODE="${1:-}"
      ;;
    --private-source)
      shift
      PRIVATE_SOURCE="${1:-}"
      ;;
    --confirm-active-config-private-source)
      ACTIVE_CONFIG_PRIVATE_SOURCE_CONFIRMED="true"
      ;;
    --confirm-local-operator-save)
      LOCAL_OPERATOR_SAVE_CONFIRMED="true"
      ;;
    --private-settings-context-path)
      shift
      PRIVATE_SETTINGS_CONTEXT_PATH="${1:-}"
      ;;
    --lock-dir)
      shift
      LOCK_DIR="${1:-}"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "error: unsupported argument $1" >&2
      exit 2
      ;;
  esac
  shift
done

case "$MODE" in
  preview|interactive)
    ;;
  *)
    echo "error: unsupported mode $MODE" >&2
    exit 2
    ;;
esac

case "$EXPECTED_RESULT" in
  preview|cancelled|candidate_ready|dry_run_passed|real_write_passed|any)
    ;;
  *)
    echo "error: unsupported expected result $EXPECTED_RESULT" >&2
    exit 2
    ;;
esac

case "$REMOTE_TTY" in
  ''|*[!0-9]*|0)
    echo "error: --tty must be a positive integer" >&2
    exit 2
    ;;
esac

case "$RUN_TIMEOUT_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --timeout-sec must be a positive integer" >&2
    exit 2
    ;;
esac

case "$PREVIEW_SEC" in
  ''|*[!0-9]*|0)
    echo "error: --preview-sec must be a positive integer" >&2
    exit 2
    ;;
esac

case "$OUT_DIR" in
  /tmp/*|/run/*)
    ;;
  *)
    echo "error: --out-dir must be under /tmp or /run" >&2
    exit 2
    ;;
esac

case "$WIZARD_OUT_DIR" in
  /tmp/*|/run/*)
    ;;
  *)
    echo "error: --wizard-out-dir must be under /tmp or /run" >&2
    exit 2
    ;;
esac
case "$HANDOFF_OUT_DIR" in
  /tmp/*|/run/*)
    ;;
  *)
    echo "error: --handoff-out-dir must be under /tmp or /run" >&2
    exit 2
    ;;
esac
case "$WRITER_OUT_DIR" in
  /tmp/*|/run/*)
    ;;
  *)
    echo "error: --writer-out-dir must be under /tmp or /run" >&2
    exit 2
    ;;
esac
case "$PRIVATE_VALUES" in
  /tmp/*)
    ;;
  *)
    echo "error: --private-values must be under /tmp" >&2
    exit 2
    ;;
esac
case "$APPLY_POLICY_PATH" in
  /tmp/*|/run/*)
    ;;
  *)
    echo "error: --apply-policy-path must be under /tmp or /run" >&2
    exit 2
    ;;
esac
case "$REQUEST_DIR" in
  /tmp/*|/run/*)
    ;;
  *)
    echo "error: --request-dir must be under /tmp or /run" >&2
    exit 2
    ;;
esac
case "$APPLY_MODE" in
  policy|candidate-only|dry-run|real-write)
    ;;
  *)
    echo "error: unsupported apply mode $APPLY_MODE" >&2
    exit 2
    ;;
esac
case "$PRIVATE_SOURCE" in
  none|active-config)
    ;;
  *)
    echo "error: unsupported --private-source $PRIVATE_SOURCE" >&2
    exit 2
    ;;
esac
if [ "$APPLY_MODE" = "real-write" ] && [ "$LOCAL_OPERATOR_SAVE_CONFIRMED" != "true" ]; then
  echo "error: real-write requires --confirm-local-operator-save outside policy mode" >&2
  exit 2
fi
if [ "$PRIVATE_SOURCE" = "active-config" ] && [ "$ACTIVE_CONFIG_PRIVATE_SOURCE_CONFIRMED" != "true" ]; then
  echo "error: active-config private source requires explicit confirmation" >&2
  exit 2
fi
case "$PRIVATE_SETTINGS_CONTEXT_PATH" in
  /data/state/totem-settings/last-settings.json|/tmp/*)
    ;;
  *)
    echo "error: --private-settings-context-path must be the approved /data/state path or under /tmp" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VISUAL="$SCRIPT_DIR/totem_setup_visual_wizard.py"
SPLASH="$SCRIPT_DIR/totem_visual_splash.py"
TTY_GUARD="$SCRIPT_DIR/totem_visual_tty_guard.sh"
AGGREGATE="$SCRIPT_DIR/totem_status_aggregate.py"
HANDOFF="$SCRIPT_DIR/totem_visual_setup_writer_handoff.py"
WRITER="$SCRIPT_DIR/totem_config_writer_real.py"
CONTRACT="$SCRIPT_DIR/totem_config_contract_validate.py"
TTY_DEVICE="/dev/tty$REMOTE_TTY"
FINAL_STATUS="$OUT_DIR/session-status.json"
REQUEST_FILE="$REQUEST_DIR/request.json"
GETTY_UNITS=("getty@tty1.service" "getty@tty${REMOTE_TTY}.service")
WIZARD_RC="not_run"
HANDOFF_RC="not_run"
WRITER_RC="not_run"
SERVICE_STOP_ATTEMPTED="false"
SERVICE_RESTORE_ATTEMPTED="false"
WRITER_CALLED="false"
REAL_CONFIG_READ="false"
REAL_CONFIG_WRITTEN="false"
PRIVATE_SOURCE_TEMP_REMOVED="false"
PRIVATE_CANDIDATE_REMOVED="false"
SOURCE_CANDIDATE_REMOVED="false"
ORIENTATION_JSON_UPDATED="false"
PRIVATE_SETTINGS_CONTEXT_UPDATED="false"
PRIVATE_SETTINGS_CONTEXT_SEEDED="false"
SELECTED_ROTATION_DEG="unknown"
POLICY_USED="false"
POLICY_PRIVATE_SOURCE="none"
POLICY_REAL_WRITE_CONFIRMED="false"
POLICY_DRY_RUN_CONFIRMED="false"
APPLY_POLICY_REMOVED="false"
HOMOLOGATION_SEED_MODE="false"
INITIAL_SERVICE_ACTIVE="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
INITIAL_SERVICE_ENABLED="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"
declare -A GETTY_ACTIVE
declare -A GETTY_ENABLED

c17_4_trace() {
  local event="$1"
  local root="$TOTEM_C17_4_FIRSTBOOT_TRACE_DIR"
  local lock_state="absent"
  local uptime_value="unknown"

  [ -e "$LOCK_DIR" ] && lock_state="present"
  uptime_value="$(awk '{print int($1)}' /proc/uptime 2>/dev/null || printf unknown)"
  if ! mkdir -p "$root" 2>/dev/null; then
    root="/run/totem/c17-4-firstboot"
    mkdir -p "$root" 2>/dev/null || return 0
  fi
  chown totem:totem "$root" 2>/dev/null || true
  chmod 700 "$root" 2>/dev/null || true
  printf '%s uptime=%s pid=%d component=open_settings_session event=%s session_lock=%s\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$uptime_value" "$$" "$event" "$lock_state" \
    >> "$root/events.log" 2>/dev/null || true
  case "$root" in
    /data/*) sync "$root/events.log" >/dev/null 2>&1 || true ;;
  esac
}

for path in "$VISUAL" "$SPLASH" "$AGGREGATE"; do
  if [ ! -f "$path" ]; then
    echo "error: missing local session dependency" >&2
    exit 1
  fi
done

write_private_settings_context() {
  local source_json="$1"
  local context_source="$2"
  python3 - "$source_json" "$PRIVATE_SETTINGS_CONTEXT_PATH" "$context_source" <<'PY'
import json
import os
import pathlib
import stat
import sys
import time

source = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
context_source = sys.argv[3]
if target.is_symlink():
    raise SystemExit("private_context_symlink")
if str(target) != "/data/state/totem-settings/last-settings.json" and not str(target).startswith("/tmp/"):
    raise SystemExit("private_context_path_invalid")
data = json.loads(source.read_text(encoding="utf-8"))
environment_id = data.get("environment_id")
if not isinstance(environment_id, str) or not environment_id.strip():
    raise SystemExit("private_context_missing_environment")
rotation = int(data.get("rotation_deg", 0)) % 360
if rotation not in {0, 90, 180, 270}:
    raise SystemExit("private_context_invalid_rotation")
orientation_label = {0: "landscape", 90: "portrait_right", 180: "inverted", 270: "portrait_left"}[rotation]
target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
if stat.S_IMODE(target.parent.stat().st_mode) != 0o700:
    target.parent.chmod(0o700)
payload = {
    "schema_version": "dadooh-private-settings-context.v1",
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "source": context_source,
    "environment_id": environment_id.strip(),
    "rotation_deg": rotation,
    "orientation_label": orientation_label,
    "network_step": data.get("setup_network_step", "existing_configured_wifi"),
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
PY
}

umask 077
mkdir -p "$OUT_DIR" "$WIZARD_OUT_DIR" "$HANDOFF_OUT_DIR" "$WRITER_OUT_DIR" "$(dirname "$LOCK_DIR")" "$REQUEST_DIR"
chmod 700 "$OUT_DIR" "$WIZARD_OUT_DIR" "$HANDOFF_OUT_DIR" "$WRITER_OUT_DIR" "$REQUEST_DIR" 2>/dev/null || true
chmod 755 "$(dirname "$LOCK_DIR")" 2>/dev/null || true
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "settings_session_already_running" >&2
  exit 23
fi
chmod 755 "$LOCK_DIR" 2>/dev/null || true
c17_4_trace "session_lock_acquired"

for unit in "${GETTY_UNITS[@]}"; do
  GETTY_ACTIVE["$unit"]="$(systemctl is-active "$unit" 2>/dev/null || true)"
  GETTY_ENABLED["$unit"]="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
done

process_counts() {
  python3 - <<'PY'
import os
import pathlib
counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    names = [pathlib.Path(part).name.lower() for part in parts]
    if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
        counts["setup"] += 1
    if any("totem_status_renderer" in name for name in names):
        counts["renderer"] += 1
    if any(name == "mpv" for name in names):
        counts["mpv"] += 1
    if "kiosk.py" in names:
        counts["player"] += 1
print(f"{counts['player']} {counts['mpv']} {counts['renderer']} {counts['setup']}")
PY
}

monotonic_seconds() {
  awk '{print int($1)}' /proc/uptime 2>/dev/null
}

refresh_public_status() {
  if [ -f /opt/totem/bin/totem_status_aggregate.py ]; then
    PYTHONPATH=/opt/totem/bin python3 /opt/totem/bin/totem_status_aggregate.py >/dev/null 2>&1 || true
  else
    PYTHONPATH="$SCRIPT_DIR" python3 "$AGGREGATE" >/dev/null 2>&1 || true
  fi
}

read_json_value() {
  local path="$1"
  local key="$2"
  python3 - "$path" "$key" <<'PY'
import json
import pathlib
import sys
try:
    data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    key = sys.argv[2]
    value = data.get("public_state") or data.get("state") if key == "public_state" else data.get(key)
    print(value if isinstance(value, str) else "unknown")
except Exception:
    print("unknown")
PY
}

wait_player_running() {
  if [ ! -f /data/config/config.json ]; then
    refresh_public_status
    return 0
  fi
  for _ in $(seq 1 90); do
    refresh_public_status
    state="$(read_json_value /tmp/dadooh-status/status.json public_state)"
    playback="$(read_json_value /tmp/kiosky-status.json playback_state)"
    set -- $(process_counts)
    if [ "$state" = "player_running" ] && [ "$playback" = "playing" ] && [ "${1:-0}" -ge 1 ] && [ "${2:-0}" -ge 1 ] && [ "${3:-0}" -eq 0 ] && [ "${4:-0}" -eq 0 ]; then
      return 0
    fi
    sleep 2
  done
  return 1
}

show_transition() {
  local mode="$1"
  local rotation="${2:-}"
  command -v chvt >/dev/null 2>&1 && chvt "$REMOTE_TTY" >/dev/null 2>&1 || true
  if [ -x "$TTY_GUARD" ]; then
    "$TTY_GUARD" --clear --tty "$REMOTE_TTY" >/dev/null 2>&1 || true
  fi
  printf '\033c\033[2J\033[3J\033[H\033[?25l' > "$TTY_DEVICE" 2>/dev/null || true
  sleep 0.05
  printf '\033c\033[2J\033[3J\033[H\033[?25l' > "$TTY_DEVICE" 2>/dev/null || true
  if [ -n "$rotation" ] && [ "$rotation" != "unknown" ]; then
    env TERM=linux PYTHONPATH="$SCRIPT_DIR" python3 "$SPLASH" "$mode" --rotation-deg "$rotation" --status-out "$OUT_DIR/splash-$mode-status.json" <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
  else
    env TERM=linux PYTHONPATH="$SCRIPT_DIR" python3 "$SPLASH" "$mode" --status-out "$OUT_DIR/splash-$mode-status.json" <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
  fi
}

restore_getty() {
  if [ "$RESTORE_GETTY_AFTER_SETTINGS" != "1" ]; then
    for unit in "${GETTY_UNITS[@]}"; do
      systemctl disable "$unit" >/dev/null 2>&1 || true
      systemctl stop "$unit" >/dev/null 2>&1 || true
    done
    if [ -x "$TTY_GUARD" ]; then
      "$TTY_GUARD" --quiet --tty 1 --tty "$REMOTE_TTY" >/dev/null 2>&1 || true
    fi
    return 0
  fi
  for unit in "${GETTY_UNITS[@]}"; do
    if [ "${GETTY_ENABLED[$unit]}" = "enabled" ]; then
      systemctl enable "$unit" >/dev/null 2>&1 || true
    else
      systemctl disable "$unit" >/dev/null 2>&1 || true
    fi
    if [ "${GETTY_ACTIVE[$unit]}" = "active" ]; then
      systemctl start "$unit" >/dev/null 2>&1 || true
    else
      systemctl stop "$unit" >/dev/null 2>&1 || true
    fi
  done
}

restore_service() {
  SERVICE_RESTORE_ATTEMPTED="true"
  if [ -e "$LOCK_DIR" ]; then
    c15_trace "restore_service_blocked_session_lock_present"
    c1523_phase "player_restore_blocked_by_session_lock"
    c17_4_trace "restore_service_blocked_session_lock_present"
    return 1
  fi
  if [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
    systemctl enable kiosky-player.service >/dev/null 2>&1 || true
  fi
  if [ "$INITIAL_SERVICE_ACTIVE" = "active" ] || [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
    c1523_phase "player_restore_start"
    if [ -f /data/config/config.json ]; then
      show_transition player "$SELECTED_ROTATION_DEG" || true
      install -d -o totem -g totem -m 0750 /tmp/kiosky >/dev/null 2>&1 || true
      install -o totem -g totem -m 0600 /dev/null /tmp/kiosky/player-splash-rendered >/dev/null 2>&1 || true
    else
      show_transition config_pending "$SELECTED_ROTATION_DEG" || true
    fi
    systemctl start kiosky-player.service >/dev/null 2>&1 || true
    c1523_phase "player_restore_done active=$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
  fi
}

kill_visual_if_running() {
  python3 - "$VISUAL" "$WIZARD_OUT_DIR" <<'PY'
import os
import pathlib
import signal
import sys
import time
visual = sys.argv[1]
out = sys.argv[2]
pids = []
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == os.getpid():
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    joined = " ".join(parts)
    if visual in joined or out in joined:
        pids.append(int(proc.name))
for pid in pids:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
time.sleep(2)
for pid in pids:
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
PY
}

load_apply_policy() {
  if [ "$APPLY_MODE" != "policy" ]; then
    POLICY_PRIVATE_SOURCE="$PRIVATE_SOURCE"
    return 0
  fi
  if [ ! -f "$APPLY_POLICY_PATH" ]; then
    APPLY_MODE="candidate-only"
    return 0
  fi
  POLICY_USED="true"
  eval "$(
    python3 - "$APPLY_POLICY_PATH" "$PRIVATE_VALUES" <<'PY'
import json
import os
import pathlib
import shlex
import stat
import sys

path = pathlib.Path(sys.argv[1])
default_private = sys.argv[2]
if path.is_symlink():
    raise SystemExit("apply_policy_symlink")
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit("apply_policy_invalid")
if not isinstance(data, dict):
    raise SystemExit("apply_policy_invalid")
mode = data.get("mode", "candidate-only")
if mode not in {"candidate-only", "dry-run", "real-write"}:
    raise SystemExit("apply_policy_mode_invalid")
private_source = data.get("private_source", "none")
if private_source not in {"none", "tmp-file", "active-config", "homologation-seed"}:
    raise SystemExit("apply_policy_private_source_invalid")
private_values = data.get("private_values_path") or default_private
if private_source == "homologation-seed":
    if private_values != "/data/state/totem-settings/private-values.seed.json":
        raise SystemExit("apply_policy_private_values_invalid")
    if not bool(data.get("homologation_seed", False)):
        raise SystemExit("apply_policy_homologation_seed_not_marked")
elif not isinstance(private_values, str) or not private_values.startswith("/tmp/"):
    raise SystemExit("apply_policy_private_values_invalid")
real_confirmed = bool(data.get("real_write_confirmed", False))
dry_confirmed = bool(data.get("dry_run_confirmed", False))
source_confirmed = bool(data.get("active_config_private_source_confirmed", False))
homologation_seed = bool(data.get("homologation_seed", False))
if mode == "real-write" and not real_confirmed:
    raise SystemExit("apply_policy_real_write_not_confirmed")
if mode == "dry-run" and not dry_confirmed:
    raise SystemExit("apply_policy_dry_run_not_confirmed")
if private_source == "active-config" and not source_confirmed:
    raise SystemExit("apply_policy_active_config_not_confirmed")
print(f"APPLY_MODE={shlex.quote(mode)}")
print(f"POLICY_PRIVATE_SOURCE={shlex.quote(private_source)}")
print(f"PRIVATE_VALUES={shlex.quote(private_values)}")
print(f"POLICY_REAL_WRITE_CONFIRMED={str(real_confirmed).lower()}")
print(f"POLICY_DRY_RUN_CONFIRMED={str(dry_confirmed).lower()}")
print(f"HOMOLOGATION_SEED_MODE={str(homologation_seed).lower()}")
PY
  )"
}

prepare_private_values_from_active_config_if_requested() {
  if [ "$POLICY_PRIVATE_SOURCE" != "active-config" ]; then
    return 0
  fi
  if [ ! -f /data/config/config.json ]; then
    APPLY_MODE="candidate-only"
    POLICY_PRIVATE_SOURCE="none"
    REAL_CONFIG_READ="false"
    return 0
  fi
  REAL_CONFIG_READ="true"
  python3 - "$PRIVATE_VALUES" <<'PY'
import json
import os
import pathlib
import stat
import sys
target = pathlib.Path(sys.argv[1])
active = pathlib.Path("/data/config/config.json")
if not str(target).startswith("/tmp/"):
    raise SystemExit("private_values_target_not_tmp")
if target.is_symlink():
    raise SystemExit("private_values_target_symlink")
target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
if stat.S_IMODE(target.parent.stat().st_mode) != 0o700:
    target.parent.chmod(0o700)
with active.open("r", encoding="utf-8") as handle:
    config = json.load(handle)
payload = {}
for field in ("api_url", "api_key", "station_id"):
    value = config.get(field)
    if isinstance(value, str) and value.strip():
        payload[field] = value.strip()
if "api_url" not in payload or "api_key" not in payload:
    raise SystemExit("active_config_missing_private_categories")
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
PY
}

validate_private_values_metadata() {
  if [ "$POLICY_PRIVATE_SOURCE" = "none" ]; then
    return 0
  fi
  python3 - "$PRIVATE_VALUES" <<'PY'
import pathlib
import stat
import sys
path = pathlib.Path(sys.argv[1])
is_tmp = str(path).startswith("/tmp/")
is_seed = str(path) == "/data/state/totem-settings/private-values.seed.json"
if (not is_tmp and not is_seed) or path.is_symlink() or not path.exists():
    raise SystemExit("private_values_not_ready")
if path.parent.is_symlink():
    raise SystemExit("private_values_parent_symlink")
if stat.S_IMODE(path.parent.stat().st_mode) & 0o077:
    raise SystemExit("private_values_parent_permissive")
mode = stat.S_IMODE(path.stat().st_mode)
if mode & 0o077 or not (mode & 0o600):
    raise SystemExit("private_values_file_permissive")
PY
}

selected_rotation_from_candidate() {
  python3 - "$WIZARD_OUT_DIR/config.candidate.json" <<'PY'
import json
import pathlib
import sys
try:
    data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    value = int(data.get("rotation_deg", 0)) % 360
    if value not in {0, 90, 180, 270}:
        value = 0
    print(value)
except Exception:
    print("unknown")
PY
}

write_public_orientation_from_candidate() {
  python3 - "$WIZARD_OUT_DIR/config.candidate.json" <<'PY'
import json
import os
import pathlib
import time
import sys
candidate = pathlib.Path(sys.argv[1])
data = json.loads(candidate.read_text(encoding="utf-8"))
rotation = int(data.get("rotation_deg", 0)) % 360
if rotation not in {0, 90, 180, 270}:
    raise SystemExit("rotation_invalid")
label = {0: "landscape", 90: "portrait_right", 180: "inverted", 270: "portrait_left"}[rotation]
target = pathlib.Path("/data/state/totem-display/orientation.json")
target.parent.mkdir(parents=True, exist_ok=True)
payload = {
    "schema_version": "dadooh-display-orientation.v1",
    "rotation_deg": rotation,
    "orientation_label": label,
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o644)
os.replace(tmp, target)
os.chmod(target, 0o644)
PY
  ORIENTATION_JSON_UPDATED="true"
}

cleanup_private_artifacts() {
  if [ -f "$HANDOFF_OUT_DIR/config.candidate.private.json" ]; then
    rm -f "$HANDOFF_OUT_DIR/config.candidate.private.json" || true
  fi
  if [ ! -e "$HANDOFF_OUT_DIR/config.candidate.private.json" ]; then
    PRIVATE_CANDIDATE_REMOVED="true"
  fi
  if [ "$POLICY_PRIVATE_SOURCE" = "active-config" ]; then
    rm -rf "$(dirname "$PRIVATE_VALUES")" || true
    if [ ! -e "$PRIVATE_VALUES" ]; then
      PRIVATE_SOURCE_TEMP_REMOVED="true"
    fi
  fi
}

cleanup_apply_policy() {
  if [ "$POLICY_USED" = "true" ] && [ -f "$APPLY_POLICY_PATH" ]; then
    rm -f "$APPLY_POLICY_PATH" || true
  fi
  if [ ! -e "$APPLY_POLICY_PATH" ]; then
    APPLY_POLICY_REMOVED="true"
  fi
}

cleanup_trigger_request() {
  case "$REQUEST_FILE" in
    /run/*|/tmp/*)
      rm -f "$REQUEST_FILE" || true
      ;;
  esac
}

cleanup_session_lock() {
  case "$LOCK_DIR" in
    /run/*|/tmp/*)
      rm -rf "$LOCK_DIR" || true
      ;;
    *)
      rmdir "$LOCK_DIR" 2>/dev/null || true
      ;;
  esac
}

release_session_lock_for_restore() {
  c15_trace "release_session_lock_for_restore_begin"
  c1523_phase "settings_visual_done"
  cleanup_trigger_request || true
  cleanup_session_lock || true
  c17_4_trace "session_lock_released_before_restore"
  if [ -e "$LOCK_DIR" ]; then
    c15_trace "release_session_lock_for_restore_failed"
    c1523_phase "release_session_lock_failed"
    return 1
  fi
  c15_trace "release_session_lock_for_restore_done"
  c1523_phase "release_session_lock_done lock_removed_before_restore=true"
  return 0
}

write_final_status() {
  if [ -e "$LOCK_DIR" ]; then
    c15_trace "write_final_status_skip_wait_session_lock_present"
    c1523_phase "write_final_status_skip_wait_session_lock_present"
  else
    wait_player_running || true
  fi
  python3 - "$FINAL_STATUS" "$OUT_DIR" "$WIZARD_OUT_DIR" "$MODE" "$EXPECTED_RESULT" "$WIZARD_RC" \
    "$INITIAL_SERVICE_ACTIVE" "$INITIAL_SERVICE_ENABLED" "$SERVICE_STOP_ATTEMPTED" "$SERVICE_RESTORE_ATTEMPTED" \
    "$(systemctl is-active kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)" \
    "$(systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null || true)" \
    "$(read_json_value /tmp/dadooh-status/status.json public_state)" \
    "$(read_json_value /tmp/kiosky-status.json playback_state)" \
    "$HANDOFF_OUT_DIR" "$WRITER_OUT_DIR" "$APPLY_MODE" "$POLICY_USED" "$POLICY_PRIVATE_SOURCE" \
    "$HANDOFF_RC" "$WRITER_RC" "$WRITER_CALLED" "$REAL_CONFIG_READ" "$REAL_CONFIG_WRITTEN" \
    "$PRIVATE_SOURCE_TEMP_REMOVED" "$PRIVATE_CANDIDATE_REMOVED" "$ORIENTATION_JSON_UPDATED" "$SELECTED_ROTATION_DEG" \
    "$APPLY_POLICY_REMOVED" "$PRIVATE_SETTINGS_CONTEXT_SEEDED" "$PRIVATE_SETTINGS_CONTEXT_UPDATED" \
    "$HOMOLOGATION_SEED_MODE" <<'PY'
import json
import os
import pathlib
import pwd
import grp
import stat
import sys

target = pathlib.Path(sys.argv[1])
out_dir = pathlib.Path(sys.argv[2])
wizard_out = pathlib.Path(sys.argv[3])
mode = sys.argv[4]
expected_result = sys.argv[5]
wizard_rc = sys.argv[6]
initial_active = sys.argv[7] or "unknown"
initial_enabled = sys.argv[8] or "unknown"
service_stop_attempted = sys.argv[9] == "true"
service_restore_attempted = sys.argv[10] == "true"
service_active = sys.argv[11] or "unknown"
service_enabled = sys.argv[12] or "unknown"
nrestarts = sys.argv[13] or "unknown"
public_state = sys.argv[14] or "unknown"
playback = sys.argv[15] or "unknown"
handoff_out = pathlib.Path(sys.argv[16])
writer_out = pathlib.Path(sys.argv[17])
apply_mode = sys.argv[18]
policy_used = sys.argv[19] == "true"
policy_private_source = sys.argv[20]
handoff_rc = sys.argv[21]
writer_rc = sys.argv[22]
writer_called = sys.argv[23] == "true"
real_config_read = sys.argv[24] == "true"
real_config_written = sys.argv[25] == "true"
private_source_temp_removed = sys.argv[26] == "true"
private_candidate_removed = sys.argv[27] == "true"
orientation_json_updated = sys.argv[28] == "true"
selected_rotation_raw = sys.argv[29]
apply_policy_removed = sys.argv[30] == "true"
private_settings_context_seeded = sys.argv[31] == "true"
private_settings_context_updated = sys.argv[32] == "true"
homologation_seed_mode = sys.argv[33] == "true"

def load_json(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}

setup_status = load_json(wizard_out / "setup-status.json")
handoff_status = load_json(handoff_out / "setup-status.json")
writer_status = load_json(writer_out / "writer-status.json")
network = setup_status.get("network") if isinstance(setup_status.get("network"), dict) else {}
validation = setup_status.get("validation") if isinstance(setup_status.get("validation"), dict) else {}
interface = setup_status.get("interface") if isinstance(setup_status.get("interface"), dict) else {}
counts = {"player": 0, "mpv": 0, "renderer": 0, "setup": 0}
self_pid = os.getpid()
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    names = [pathlib.Path(part).name.lower() for part in parts]
    if "totem_setup_visual_wizard.py" in names or "totem_setup_local_wizard.py" in names:
        counts["setup"] += 1
    if any("totem_status_renderer" in name for name in names):
        counts["renderer"] += 1
    if any(name == "mpv" for name in names):
        counts["mpv"] += 1
    if "kiosk.py" in names:
        counts["player"] += 1
selected_rotation = validation.get("rotation_degrees", "unknown")
if selected_rotation == "unknown" and selected_rotation_raw != "unknown":
    try:
        selected_rotation = int(selected_rotation_raw)
    except ValueError:
        selected_rotation = "unknown"
orientation_json = load_json(pathlib.Path("/data/state/totem-display/orientation.json"))
orientation_rotation = orientation_json.get("rotation_deg", "unknown")
orientation_matches = (
    isinstance(selected_rotation, int)
    and isinstance(orientation_rotation, int)
    and selected_rotation == orientation_rotation
)
active_config_rotation = "unknown"
active_config_rotation_matches = "unknown"
active_config = pathlib.Path("/data/config/config.json")
config_meta = {"exists": active_config.exists(), "mode": None, "owner_root": False, "group_totem": False}
if active_config.exists():
    st = active_config.stat()
    config_meta["mode"] = f"{stat.S_IMODE(st.st_mode):04o}"[-4:]
    try:
        config_meta["owner_root"] = pwd.getpwuid(st.st_uid).pw_name == "root"
    except KeyError:
        pass
    try:
        config_meta["group_totem"] = grp.getgrgid(st.st_gid).gr_name == "totem"
    except KeyError:
        pass
if writer_called and active_config.exists() and selected_rotation != "unknown":
    try:
        active_config_rotation = int(load_json(active_config).get("rotation_deg", -1))
        active_config_rotation_matches = active_config_rotation == selected_rotation
    except Exception:
        active_config_rotation = "unknown"
        active_config_rotation_matches = False

payload = {
    "schema_version": "dadooh-c10.6.2-open-settings-session.v1",
    "mode": mode,
    "apply_mode": apply_mode,
    "policy_used": policy_used,
    "apply_policy_removed": apply_policy_removed,
    "policy_private_source": policy_private_source,
    "homologation_seed_mode": homologation_seed_mode,
    "expected_result": expected_result,
    "trigger_opens_wizard_directly": True,
    "wizard_rc": wizard_rc,
    "handoff_rc": handoff_rc,
    "writer_rc": writer_rc,
    "visual_wizard_opened": (wizard_out / "screens").exists() or bool(setup_status) or (wizard_out / "setup-cancelled.json").exists(),
    "visual_candidate_generated": (wizard_out / "config.candidate.json").exists(),
    "setup_cancelled": (wizard_out / "setup-cancelled.json").exists(),
    "orientation_category": {0: "landscape", 90: "portrait_right", 180: "inverted", 270: "portrait_left"}.get(
        validation.get("rotation_degrees"), "unknown"
    ),
    "rotation_degrees": validation.get("rotation_degrees", "unknown"),
    "selected_rotation_deg": selected_rotation,
    "network_step": network.get("network_step", "unknown"),
    "private_candidate_real_dry_run_passed": bool(
        handoff_status.get("contract_validation", {}).get("private_real_dry_run", {}).get("valid")
    ),
    "writer_result": writer_status.get("result", "not_available"),
    "backup_created": bool(writer_status.get("backup", {}).get("created", False)),
    "permissions_ok": bool(config_meta["exists"] and config_meta["mode"] == "0640" and config_meta["owner_root"] and config_meta["group_totem"]),
    "active_config_rotation_deg_matches": active_config_rotation_matches,
    "expected_rotation_deg": selected_rotation,
    "active_config_rotation_deg_public_check": active_config_rotation if isinstance(active_config_rotation, int) else "unknown",
    "orientation_json_updated": orientation_json_updated,
    "orientation_json_rotation_matches": orientation_matches,
    "private_settings_context_seeded": private_settings_context_seeded,
    "private_settings_context_updated": private_settings_context_updated,
    "private_settings_context_values_published": False,
    "splash_orientation_source": "public_orientation_json",
    "linux_prompt_visible": bool(interface.get("linux_prompt_visible", False)),
    "service_initial_active": initial_active,
    "service_initial_enabled": initial_enabled,
    "service_stop_attempted": service_stop_attempted,
    "service_restore_attempted": service_restore_attempted,
    "service_active": service_active,
    "service_enabled": service_enabled,
    "nrestarts": nrestarts,
    "public_state": public_state,
    "playback": playback,
    "process_counts": counts,
    "writer_called": writer_called,
    "real_config_read": real_config_read,
    "real_config_read_authorized_for_private_source": real_config_read,
    "real_config_written": real_config_written,
    "private_source_temp_removed": private_source_temp_removed,
    "private_candidate_removed": private_candidate_removed,
    "wifi_changed": False,
    "networkmanager_changed": False,
    "hotspot_created": False,
    "portal_created": False,
    "root_read_only_enabled": False,
    "power_cut_tested": False,
    "credential_values_published": False,
    "network_identifiers_published": False,
    "environment_identifier_raw_published": False,
    "config_content_published": False,
    "raw_logs_written": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
assert stat.S_IMODE(out_dir.stat().st_mode) == 0o700
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

C15_TRACE_FILE="${C15_TRACE_FILE:-/tmp/c15-session.trace}"
c15_trace() {
  printf '%s pid=%d phase=%s\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%S.%N')" "$$" "$*" \
    >> "$C15_TRACE_FILE" 2>/dev/null || true
}

C1523_DEBUG_ROOT="/data/state/totem-debug/c15-2-3"
c1523_monitor_dir() {
  if [ -n "${TOTEM_C15_2_3_MONITOR_DIR:-}" ]; then
    printf '%s\n' "$TOTEM_C15_2_3_MONITOR_DIR"
    return 0
  fi
  if [ -f "$C1523_DEBUG_ROOT/current-run-dir" ] && [ ! -L "$C1523_DEBUG_ROOT/current-run-dir" ]; then
    head -n 1 "$C1523_DEBUG_ROOT/current-run-dir" 2>/dev/null || true
  fi
}

c1523_phase() {
  phase="$1"
  dir="$(c1523_monitor_dir)"
  case "$dir" in
    "$C1523_DEBUG_ROOT"/*)
      ;;
    *)
      return 0
      ;;
  esac
  [ -d "$dir" ] || return 0
  printf '%s uptime=%s pid=%d phase=%s\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$(monotonic_seconds)" "$$" "$phase" \
    >> "$dir/phases.log" 2>/dev/null || true
  sync "$dir/phases.log" >/dev/null 2>&1 || true
}
c15_trace "session_sh_start argv=$# pid=$$ ppid=$PPID"

on_exit() {
  rc="$?"
  trap - EXIT INT TERM HUP
  c15_trace "on_exit_begin rc=$rc"
  c1523_phase "session_cleanup_start rc=$rc"
  kill_visual_if_running || true
  cleanup_apply_policy || true
  cleanup_trigger_request || true
  cleanup_session_lock || true
  c17_4_trace "session_lock_released"
  restore_service || true
  write_final_status || true
  restore_getty || true
  c1523_phase "session_done rc=$rc"
  c15_trace "on_exit_done rc=$rc"
  exit "$rc"
}
on_term() { c15_trace "trap_signal=TERM rc=$?"; on_exit; }
on_int()  { c15_trace "trap_signal=INT rc=$?";  on_exit; }
on_hup()  { c15_trace "trap_signal=HUP rc=$?";  on_exit; }
trap on_exit EXIT
trap on_term TERM
trap on_int  INT
trap on_hup  HUP

load_apply_policy
if [ "$APPLY_MODE" = "dry-run" ] || [ "$APPLY_MODE" = "real-write" ]; then
  for path in "$HANDOFF" "$CONTRACT"; do
    if [ ! -f "$path" ]; then
      echo "error: missing handoff dependency" >&2
      exit 1
    fi
  done
  if [ "$APPLY_MODE" = "real-write" ] && [ ! -f "$WRITER" ]; then
    echo "error: missing writer dependency" >&2
    exit 1
  fi
  if [ "$APPLY_MODE" = "real-write" ] && [ "$POLICY_USED" != "true" ] && [ "$LOCAL_OPERATOR_SAVE_CONFIRMED" != "true" ]; then
    echo "real_write_not_confirmed" >&2
    exit 2
  fi
  prepare_private_values_from_active_config_if_requested
  validate_private_values_metadata
  if [ "$POLICY_PRIVATE_SOURCE" = "active-config" ] && [ -f /data/config/config.json ]; then
    write_private_settings_context /data/config/config.json active_config_prefill || true
    if [ -f "$PRIVATE_SETTINGS_CONTEXT_PATH" ]; then
      PRIVATE_SETTINGS_CONTEXT_SEEDED="true"
    fi
  fi
fi

c15_trace "before_getty_stop"
for unit in "${GETTY_UNITS[@]}"; do
  systemctl stop "$unit" >/dev/null 2>&1 || true
done

c15_trace "before_show_transition_1"
c17_4_trace "settings_transition_start"
show_transition setup || true
c15_trace "after_show_transition_1 INITIAL_SERVICE_ACTIVE=$INITIAL_SERVICE_ACTIVE"
if [ "$INITIAL_SERVICE_ACTIVE" = "active" ] || [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then
  SERVICE_STOP_ATTEMPTED="true"
  c15_trace "before_systemctl_stop_kiosky"
  systemctl stop kiosky-player.service >/dev/null 2>&1 || true
  c15_trace "after_systemctl_stop_kiosky"
  for _ in $(seq 1 30); do
    set -- $(process_counts)
    if [ "${1:-0}" -eq 0 ] && [ "${2:-0}" -eq 0 ] && [ "${3:-0}" -eq 0 ] && [ "${4:-0}" -eq 0 ]; then
      break
    fi
    sleep 1
  done
  c15_trace "after_drain_wait counts=${1:-?},${2:-?},${3:-?},${4:-?}"
  set -- $(process_counts)
  if [ "${1:-0}" -ne 0 ] || [ "${2:-0}" -ne 0 ] || [ "${3:-0}" -ne 0 ] || [ "${4:-0}" -ne 0 ]; then
    c15_trace "drain_escalating_sigkill counts=${1:-?},${2:-?},${3:-?},${4:-?}"
    systemctl kill --signal=SIGKILL kiosky-player.service >/dev/null 2>&1 || true
    pkill -KILL -f '/opt/totem/kiosky-player/kiosk\.py'        >/dev/null 2>&1 || true
    pkill -KILL -f '/data/apps/kiosky-player/.*/kiosk\.py'     >/dev/null 2>&1 || true
    pkill -KILL -x mpv                                          >/dev/null 2>&1 || true
    pkill -KILL -f '/opt/totem/bin/kiosky_service_launcher\.sh'>/dev/null 2>&1 || true
    pkill -KILL -f '/opt/totem/bin/totem-kiosky-launcher\.sh'  >/dev/null 2>&1 || true
    for _ in $(seq 1 5); do
      set -- $(process_counts)
      if [ "${1:-0}" -eq 0 ] && [ "${2:-0}" -eq 0 ] && [ "${3:-0}" -eq 0 ] && [ "${4:-0}" -eq 0 ]; then
        break
      fi
      sleep 1
    done
    c15_trace "after_sigkill_drain counts=${1:-?},${2:-?},${3:-?},${4:-?}"
  fi
fi
c15_trace "before_show_transition_2"
show_transition setup || true
c15_trace "after_show_transition_2"

set -- $(process_counts)
if [ "${1:-0}" -ne 0 ] || [ "${2:-0}" -ne 0 ] || [ "${3:-0}" -ne 0 ] || [ "${4:-0}" -ne 0 ]; then
  c15_trace "abort_hdmi_not_free counts=${1:-?},${2:-?},${3:-?},${4:-?}"
  echo "hdmi_not_free_after_player_pause" >&2
  exit 42
fi
c15_trace "before_openvt"
c17_4_trace "wizard_surface_owner"
c1523_phase "wizard_started"

set +e
if [ "$MODE" = "preview" ]; then
  setsid openvt -c "$REMOTE_TTY" -s -f -w -- \
    env TERM=linux PYTHONPATH="$SCRIPT_DIR" TOTEM_VISUAL_WIZARD_APPLY_CONTEXT="$APPLY_MODE" TOTEM_VISUAL_WIZARD_HOMOLOGATION_MODE="$HOMOLOGATION_SEED_MODE" /usr/bin/python3 "$VISUAL" \
      --out-dir "$WIZARD_OUT_DIR" --private-settings-context-path "$PRIVATE_SETTINGS_CONTEXT_PATH" \
      --preview-screens --show-preview --auto-exit-sec "$PREVIEW_SEC" >/dev/null 2>&1
  WIZARD_RC="$?"
else
  setsid openvt -c "$REMOTE_TTY" -s -f -w -- \
    env TERM=linux PYTHONPATH="$SCRIPT_DIR" TOTEM_VISUAL_WIZARD_APPLY_CONTEXT="$APPLY_MODE" TOTEM_VISUAL_WIZARD_HOMOLOGATION_MODE="$HOMOLOGATION_SEED_MODE" /usr/bin/python3 "$VISUAL" \
      --out-dir "$WIZARD_OUT_DIR" --private-settings-context-path "$PRIVATE_SETTINGS_CONTEXT_PATH" >/dev/null 2>&1 &
  OPENVT_PID="$!"
  c15_trace "openvt_started pid=$OPENVT_PID"
  start_monotonic="$(monotonic_seconds)"
  deadline=$(( start_monotonic + RUN_TIMEOUT_SEC ))
  c15_trace "openvt_timeout_clock=monotonic start=$start_monotonic deadline=$deadline"
  while kill -0 "$OPENVT_PID" 2>/dev/null && [ "$(monotonic_seconds)" -lt "$deadline" ]; do
    sleep 2
  done
  if kill -0 "$OPENVT_PID" 2>/dev/null; then
    c15_trace "openvt_still_running_after_deadline TIMEOUT_SEC=$RUN_TIMEOUT_SEC"
    kill -TERM "-$OPENVT_PID" 2>/dev/null || kill -TERM "$OPENVT_PID" 2>/dev/null || true
    sleep 3
    kill -KILL "-$OPENVT_PID" 2>/dev/null || kill -KILL "$OPENVT_PID" 2>/dev/null || true
    kill_visual_if_running || true
    WIZARD_RC="124"
  else
    wait "$OPENVT_PID"
    WIZARD_RC="$?"
    c15_trace "openvt_exited WIZARD_RC=$WIZARD_RC"
  fi
fi
set -e
c15_trace "after_wizard WIZARD_RC=$WIZARD_RC"

if [ "$EXPECTED_RESULT" = "preview" ] && [ ! -d "$WIZARD_OUT_DIR/screens" ]; then
  echo "preview_not_generated" >&2
  exit 41
fi
if [ "$EXPECTED_RESULT" = "cancelled" ] && [ ! -f "$WIZARD_OUT_DIR/setup-cancelled.json" ] && [ "$WIZARD_RC" != "130" ]; then
  echo "expected_cancel_not_observed" >&2
  exit 43
fi
if [ "$EXPECTED_RESULT" = "candidate_ready" ] && [ ! -f "$WIZARD_OUT_DIR/config.candidate.json" ]; then
  echo "candidate_not_generated" >&2
  exit 44
fi
if [ -f "$WIZARD_OUT_DIR/config.candidate.json" ]; then
  SELECTED_ROTATION_DEG="$(selected_rotation_from_candidate)"
fi

if [ "$APPLY_MODE" = "dry-run" ] || [ "$APPLY_MODE" = "real-write" ]; then
  if [ ! -f "$WIZARD_OUT_DIR/config.candidate.json" ]; then
    echo "candidate_not_generated" >&2
    exit 44
  fi
  set +e
  handoff_args=(
    --source-candidate "$WIZARD_OUT_DIR/config.candidate.json"
    --private-values "$PRIVATE_VALUES"
    --out-dir "$HANDOFF_OUT_DIR"
    --confirm-private-values-approved
  )
  if [ "$HOMOLOGATION_SEED_MODE" = "true" ]; then
    handoff_args+=(--allow-homologation-seed)
  fi
  python3 "$HANDOFF" "${handoff_args[@]}" >/dev/null
  HANDOFF_RC="$?"
  set -e
  if [ "$HANDOFF_RC" != "0" ]; then
    echo "private_handoff_failed" >&2
    exit 45
  fi
  if [ ! -f "$HANDOFF_OUT_DIR/config.candidate.private.json" ]; then
    echo "private_candidate_not_generated" >&2
    exit 46
  fi
fi

if [ "$APPLY_MODE" = "dry-run" ]; then
  python3 "$CONTRACT" \
    --candidate "$HANDOFF_OUT_DIR/config.candidate.private.json" \
    --real-dry-run \
    --out-dir "$OUT_DIR/validate-real" >/dev/null
  cleanup_private_artifacts || true
  cleanup_apply_policy || true
fi

if [ "$APPLY_MODE" = "real-write" ]; then
  show_transition saving "$SELECTED_ROTATION_DEG" || true
  WRITER_CALLED="true"
  c1523_phase "writer_start"
  set +e
  python3 "$WRITER" \
    --candidate "$HANDOFF_OUT_DIR/config.candidate.private.json" \
    --dest /data/config/config.json \
    --backup-dir /data/config/backups \
    --out-dir "$WRITER_OUT_DIR" \
    --enable-real-write \
    --confirm-service-stopped \
    --confirm-human-approved-real-write >/dev/null
  WRITER_RC="$?"
  set -e
  c1523_phase "writer_done writer_rc=$WRITER_RC"
  c1523_phase "writer_result writer_rc=$WRITER_RC"
  if [ "$WRITER_RC" != "0" ]; then
    echo "writer_failed" >&2
    exit 47
  fi
  REAL_CONFIG_WRITTEN="true"
  write_public_orientation_from_candidate
  write_private_settings_context "$WIZARD_OUT_DIR/config.candidate.json" visual_wizard_saved
  PRIVATE_SETTINGS_CONTEXT_UPDATED="true"
  cleanup_private_artifacts || true
  cleanup_apply_policy || true
fi
if [ "$EXPECTED_RESULT" = "dry_run_passed" ] && [ "$APPLY_MODE" != "dry-run" ]; then
  echo "expected_dry_run_not_observed" >&2
  exit 48
fi
if [ "$EXPECTED_RESULT" = "real_write_passed" ] && [ "$REAL_CONFIG_WRITTEN" != "true" ]; then
  echo "expected_real_write_not_observed" >&2
  exit 49
fi

c1523_phase "session_cleanup_start rc=0"
if release_session_lock_for_restore; then
  restore_service || true
  wait_player_running || true
else
  c15_trace "restore_skipped_session_lock_present"
  c1523_phase "restore_skipped_session_lock_present"
fi
c1523_phase "post_restore_t+0s active=$(systemctl is-active kiosky-player.service 2>/dev/null || true) playback=$(read_json_value /tmp/kiosky-status.json playback_state)"
if [ -n "$(c1523_monitor_dir)" ]; then
  sleep 5
  c1523_phase "post_restore_t+5s active=$(systemctl is-active kiosky-player.service 2>/dev/null || true) playback=$(read_json_value /tmp/kiosky-status.json playback_state)"
  sleep 10
  c1523_phase "post_restore_t+15s active=$(systemctl is-active kiosky-player.service 2>/dev/null || true) playback=$(read_json_value /tmp/kiosky-status.json playback_state)"
  sleep 15
  c1523_phase "post_restore_t+30s active=$(systemctl is-active kiosky-player.service 2>/dev/null || true) playback=$(read_json_value /tmp/kiosky-status.json playback_state)"
fi
write_final_status
restore_getty || true
cleanup_trigger_request || true
trap - EXIT INT TERM HUP
cleanup_session_lock || true
c17_4_trace "session_done_after_restore"
c1523_phase "session_done rc=0"
exit 0
