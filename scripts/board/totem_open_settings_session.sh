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
UPDATE_LOCK_FILE="${TOTEM_UPDATE_LOCK_FILE:-/run/totem-updatectl.lock}"
UPDATE_LOCK_HOLDER_ACTIVE_PID=""
SETTINGS_SESSION_ID=""
RESTORE_GETTY_AFTER_SETTINGS="${TOTEM_RESTORE_GETTY_AFTER_SETTINGS:-0}"
TOTEM_C17_4_FIRSTBOOT_TRACE_DIR="${TOTEM_C17_4_FIRSTBOOT_TRACE_DIR:-/data/state/totem-debug/c17-4-firstboot}"
PAIRING_PRIVATE_VALUES_USED="false"
OPENVT_PID=""
SIGNAL_STOP="false"
SIGNAL_STOP_REASON="none"
PRODUCT_RESET_STATE_DIR="${TOTEM_PRODUCT_RESET_STATE_DIR:-/data/state/totem-appliance/product-reset}"
PRODUCT_RESET_GUARD_ADOPTED="false"

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
  /tmp/*/*)
    ;;
  *)
    echo "error: --private-values must use a dedicated directory under /tmp" >&2
    exit 2
    ;;
esac
if ! python3 - "$PRIVATE_VALUES" <<'PY'
import os
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
if str(path) != os.path.normpath(str(path)) or path != path.resolve(strict=False):
    raise SystemExit("private_values_path_not_normalized")
if pathlib.Path("/tmp") not in path.parents or path.parent == pathlib.Path("/tmp"):
    raise SystemExit("private_values_path_not_dedicated")
PY
then
  echo "error: --private-values path is unsafe" >&2
  exit 2
fi
PRIVATE_VALUES_DIR="$(dirname -- "$PRIVATE_VALUES")"
INITIAL_PRIVATE_VALUES_PATH="$PRIVATE_VALUES"
WIZARD_PRIVATE_SETTINGS_CONTEXT_PATH="$PRIVATE_SETTINGS_CONTEXT_PATH"
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
QR_CLIENT="$SCRIPT_DIR/totem_qr_pairing_client.py"
CONTRACT="$SCRIPT_DIR/totem_config_contract_validate.py"
TTY_DEVICE="/dev/tty$REMOTE_TTY"
FINAL_STATUS="$OUT_DIR/session-status.json"
REQUEST_FILE="$REQUEST_DIR/request.json"
TERMINAL_ACTION_MARKER="$REQUEST_DIR/terminal-action.json"
ACTION_REQUEST_FILE="$WIZARD_OUT_DIR/totem-action-request.json"
ACTION_REQUEST_CONSUMED_FILE="$WIZARD_OUT_DIR/totem-action-request.consumed.json"
PRODUCT_RESET_RECOVERY_SIGNAL_FILE="$WIZARD_OUT_DIR/product-reset-recovery-network-ready.json"
PRODUCT_RESET_RECOVERY_SIGNAL_CONSUMED_FILE="$WIZARD_OUT_DIR/product-reset-recovery-network-ready.consumed.json"
TERMINAL_ACTION_PENDING="false"
PRODUCT_RESET_AVAILABLE="0"
PRODUCT_RESET_RECOVERY_MODE="0"
TOTEM_ACTIONS_AVAILABLE="0"
GETTY_UNITS=("getty@tty1.service" "getty@tty${REMOTE_TTY}.service")
WIZARD_RC="not_run"
HANDOFF_RC="not_run"
WRITER_RC="not_run"
SERVICE_STOP_ATTEMPTED="false"
SERVICE_RESTORE_ATTEMPTED="false"
SERVICE_RESTORE_START_MODE="none"
SERVICE_RESTORE_START_RC="not_attempted"
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
for path in /usr/bin/env /usr/bin/openvt /usr/bin/python3 /usr/bin/setsid; do
  if [ ! -x "$path" ]; then
    echo "error: missing executable session dependency" >&2
    exit 1
  fi
done

run_short() {
  if command -v timeout >/dev/null 2>&1; then
    timeout -k 0.2s 1.0s "$@" >/dev/null 2>&1 || true
  else
    "$@" >/dev/null 2>&1 || true
  fi
}

write_tty_payload() {
  local payload="$1"
  if command -v timeout >/dev/null 2>&1; then
    timeout -k 0.2s 1.0s /usr/bin/env bash -c 'printf "%b" "$1" > "$2"' _ "$payload" "$TTY_DEVICE" >/dev/null 2>&1 || true
  else
    /usr/bin/env bash -c 'printf "%b" "$1" > "$2"' _ "$payload" "$TTY_DEVICE" >/dev/null 2>&1 || true
  fi
}

run_tty_command() {
  local timeout_sec="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout -k 0.2s "$timeout_sec" /usr/bin/env bash -c 'tty_device="$1"; shift; exec "$@" <"$tty_device" >"$tty_device"' _ "$TTY_DEVICE" "$@" >/dev/null 2>&1 || true
  else
    "$@" <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
  fi
}

restore_tty_console_mode() {
  if [ ! -e "$TTY_DEVICE" ]; then
    return 0
  fi
  python3 - "$TTY_DEVICE" <<'PY'
import fcntl
import os
import sys

KDSETMODE = 0x4B3A
KD_TEXT = 0x00
fd = os.open(sys.argv[1], os.O_RDWR | os.O_NOCTTY)
try:
    fcntl.ioctl(fd, KDSETMODE, KD_TEXT)
finally:
    os.close(fd)
PY
  run_short /usr/bin/stty -F "$TTY_DEVICE" sane
  if [ -x "$TTY_GUARD" ]; then
    run_short "$TTY_GUARD" --quiet --tty "$REMOTE_TTY"
  fi
}

write_private_settings_context() {
  local source_json="$1"
  local context_source="$2"
  local target_path="${3:-$PRIVATE_SETTINGS_CONTEXT_PATH}"
  python3 - "$source_json" "$target_path" "$context_source" <<'PY'
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
allowed_persistent = pathlib.Path("/data/state/totem-settings/last-settings.json")
raw_target = str(target)
if raw_target != os.path.normpath(raw_target):
    raise SystemExit("private_context_path_not_normalized")
if target != allowed_persistent and pathlib.Path("/tmp") not in target.parents:
    raise SystemExit("private_context_path_invalid")
if target.name != "last-settings.json":
    raise SystemExit("private_context_filename_invalid")
if target.parent.is_symlink() or target.parent != target.parent.resolve(strict=False):
    raise SystemExit("private_context_parent_invalid")
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
    "network_step": data.get("setup_network_step", "unknown"),
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
PY
}

cleanup_update_lock() {
  if [ -n "$UPDATE_LOCK_HOLDER_ACTIVE_PID" ]; then
    kill -TERM "$UPDATE_LOCK_HOLDER_ACTIVE_PID" 2>/dev/null || true
    wait "$UPDATE_LOCK_HOLDER_ACTIVE_PID" 2>/dev/null || true
    UPDATE_LOCK_HOLDER_ACTIVE_PID=""
  fi
}

product_reset_pending() {
  local state_dir="${PRODUCT_RESET_STATE_DIR:-/data/state/totem-appliance/product-reset}"
  if [ -L "$state_dir" ]; then
    return 0
  fi
  if [ -e "$state_dir" ] && [ ! -d "$state_dir" ]; then
    return 0
  fi
  [ -e "$state_dir/intent.json" ] \
    || [ -L "$state_dir/intent.json" ] \
    || [ -e "$state_dir/pending-credential.json" ] \
    || [ -L "$state_dir/pending-credential.json" ]
}

product_reset_onboarding_pending() {
  local state_dir="${PRODUCT_RESET_STATE_DIR:-/data/state/totem-appliance/product-reset}"
  if [ -L "$state_dir" ]; then
    return 0
  fi
  if [ -e "$state_dir" ] && [ ! -d "$state_dir" ]; then
    return 0
  fi
  [ -e "$state_dir/receipt.json" ] \
    || [ -L "$state_dir/receipt.json" ]
}

product_reset_guard_required() {
  product_reset_pending || product_reset_onboarding_pending
}

product_reset_cleanup_pending() {
  local state_dir="${PRODUCT_RESET_STATE_DIR:-/data/state/totem-appliance/product-reset}"
  local graveyard="$state_dir/graveyard"
  local first_entry=""
  if [ -L "$state_dir" ] || { [ -e "$state_dir" ] && [ ! -d "$state_dir" ]; }; then
    return 0
  fi
  if [ -e "$state_dir/gc-pending.json" ] || [ -L "$state_dir/gc-pending.json" ]; then
    return 0
  fi
  if [ -L "$graveyard" ] || { [ -e "$graveyard" ] && [ ! -d "$graveyard" ]; }; then
    return 0
  fi
  [ -d "$graveyard" ] || return 1
  if ! first_entry="$(find "$graveyard" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)"; then
    return 0
  fi
  [ -n "$first_entry" ]
}

product_reset_homologation_seed_disabled_safe() {
  local state_dir="${PRODUCT_RESET_STATE_DIR:-/data/state/totem-appliance/product-reset}"
  local seed_path="/data/state/totem-settings/private-values.seed.json"
  local expected_uid="0"
  local expected_gid="0"
  if [ "${TOTEM_C26_TEST_MODE:-0}" = "1" ]; then
    seed_path="${TOTEM_C26_TEST_HOMOLOGATION_SEED:-}"
    case "$state_dir:$seed_path" in
      /tmp/*:/tmp/*) ;;
      *) return 1 ;;
    esac
    expected_uid="$(id -u)"
    expected_gid="$(id -g)"
  fi
  python3 - "$state_dir" "$seed_path" "$expected_uid" "$expected_gid" <<'PY'
import json
import os
import pathlib
import stat
import sys
import uuid

state_dir = pathlib.Path(sys.argv[1])
seed_path = pathlib.Path(sys.argv[2])
expected_uid = int(sys.argv[3])
expected_gid = int(sys.argv[4])
marker = state_dir / "homologation-seed-disabled.json"
try:
    state_info = os.lstat(state_dir)
    marker_info = os.lstat(marker)
except OSError:
    raise SystemExit(1)
if (
    stat.S_ISLNK(state_info.st_mode)
    or not stat.S_ISDIR(state_info.st_mode)
    or state_info.st_uid != expected_uid
    or state_info.st_gid != expected_gid
    or stat.S_IMODE(state_info.st_mode) != 0o700
    or stat.S_ISLNK(marker_info.st_mode)
    or not stat.S_ISREG(marker_info.st_mode)
    or marker_info.st_uid != expected_uid
    or marker_info.st_gid != expected_gid
    or marker_info.st_nlink != 1
    or stat.S_IMODE(marker_info.st_mode) != 0o600
    or marker_info.st_size <= 0
    or marker_info.st_size > 4096
):
    raise SystemExit(1)
flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
try:
    fd = os.open(marker, flags)
    try:
        opened_info = os.fstat(fd)
        if (opened_info.st_dev, opened_info.st_ino) != (marker_info.st_dev, marker_info.st_ino):
            raise SystemExit(1)
        payload = json.loads(os.read(fd, 4097).decode("utf-8"))
    finally:
        os.close(fd)
except (OSError, UnicodeDecodeError, json.JSONDecodeError):
    raise SystemExit(1)
if set(payload) != {"schema_version", "disabled", "disabled_at_utc", "first_operation_id"}:
    raise SystemExit(1)
if (
    payload.get("schema_version") != "dadooh-c26a-product-reset.v1"
    or payload.get("disabled") is not True
    or not isinstance(payload.get("disabled_at_utc"), str)
    or not payload["disabled_at_utc"]
):
    raise SystemExit(1)
try:
    operation_id = uuid.UUID(str(payload.get("first_operation_id")))
except ValueError:
    raise SystemExit(1)
if operation_id.version != 4 or str(operation_id) != payload.get("first_operation_id"):
    raise SystemExit(1)
try:
    os.lstat(seed_path)
except FileNotFoundError:
    raise SystemExit(0)
except OSError:
    raise SystemExit(1)
raise SystemExit(1)
PY
}

remove_session_lock_if_safe() {
  if product_reset_guard_required; then
    return 0
  fi
  rmdir "$LOCK_DIR" 2>/dev/null || true
}

product_reset_lock_is_trusted() {
  python3 - "$LOCK_DIR" <<'PY'
import os
import pathlib
import stat
import sys

path = pathlib.Path(sys.argv[1])
try:
    info = path.stat(follow_symlinks=False)
except OSError:
    raise SystemExit(1)
trusted = (
    path.is_absolute()
    and not path.is_symlink()
    and stat.S_ISDIR(info.st_mode)
    and info.st_uid == os.geteuid()
    and not stat.S_IMODE(info.st_mode) & 0o022
)
raise SystemExit(0 if trusted else 1)
PY
}

product_reset_resume_request_is_trusted() {
  python3 - "$REQUEST_FILE" <<'PY'
import json
import os
import pathlib
import stat
import sys

path = pathlib.Path(sys.argv[1])
try:
    info = path.stat(follow_symlinks=False)
    if (
        path.is_symlink()
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or info.st_size <= 0
        or info.st_size > 4096
    ):
        raise SystemExit(1)
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, ValueError, json.JSONDecodeError):
    raise SystemExit(1)
trusted = (
    isinstance(payload, dict)
    and set(payload) == {"schema_version", "requested_at", "trigger_type", "action"}
    and payload.get("schema_version") == 1
    and payload.get("trigger_type") == "product_reset_resume"
    and payload.get("action") == "open_settings"
    and isinstance(payload.get("requested_at"), str)
    and bool(payload["requested_at"])
)
raise SystemExit(0 if trusted else 1)
PY
}

settings_request_trigger_type() {
  python3 - "$REQUEST_FILE" <<'PY'
import json
import os
import pathlib
import stat
import sys

path = pathlib.Path(sys.argv[1])
try:
    info = path.stat(follow_symlinks=False)
    if (
        path.is_symlink()
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or info.st_size <= 0
        or info.st_size > 4096
    ):
        raise SystemExit(1)
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, ValueError, json.JSONDecodeError):
    raise SystemExit(1)
if (
    not isinstance(payload, dict)
    or set(payload) != {"schema_version", "requested_at", "trigger_type", "action"}
    or payload.get("schema_version") != 1
    or payload.get("action") != "open_settings"
):
    raise SystemExit(1)
trigger = payload.get("trigger_type")
if trigger not in {"keyboard_f10_hold", "product_reset_resume"}:
    raise SystemExit(1)
print(trigger)
PY
}

product_reset_operation_id_from_status() {
  python3 -c '
import sys
import uuid

prefix = "product_reset_operation_id="
values = [line[len(prefix):].strip() for line in sys.stdin if line.startswith(prefix)]
if len(values) != 1:
    raise SystemExit(1)
try:
    value = str(uuid.UUID(values[0]))
except (ValueError, AttributeError):
    raise SystemExit(1)
if value != values[0] or uuid.UUID(value).version != 4:
    raise SystemExit(1)
print(value)
'
}

resume_product_reset_if_pending() {
  local resume_output=""
  local resume_rc=0
  local operation_id=""
  local revoke_output=""
  local revoke_rc=0
  local revoke_result=""
  local finalize_output=""
  local finalize_rc=0

  product_reset_pending || return 0
  if [ ! -f "$WRITER" ] || [ ! -f "$QR_CLIENT" ]; then
    c17_4_trace "product_reset_recovery_dependency_missing"
    return 57
  fi

  c17_4_trace "product_reset_local_resume_start"
  if resume_output="$({
    /usr/bin/python3 "$WRITER" \
      --product-reset-resume \
      --enable-real-write \
      --confirm-service-stopped
  } 2>/dev/null)"; then
    resume_rc=0
  else
    resume_rc=$?
  fi
  case "$resume_rc" in
    0)
      if product_reset_pending; then
        c17_4_trace "product_reset_local_resume_inconsistent"
        return 57
      fi
      c17_4_trace "product_reset_already_finalized"
      return 0
      ;;
    10)
      ;;
    *)
      c17_4_trace "product_reset_local_resume_failed" rc="$resume_rc"
      return 57
      ;;
  esac

  if ! operation_id="$(printf '%s\n' "$resume_output" | product_reset_operation_id_from_status)"; then
    c17_4_trace "product_reset_operation_id_unavailable"
    return 57
  fi

  c17_4_trace "product_reset_revocation_attempt"
  if revoke_output="$({
    /usr/bin/python3 "$QR_CLIENT" \
      --product-reset-self-revoke \
      --pending-credential "$PRODUCT_RESET_STATE_DIR/pending-credential.json" \
      --timeout-sec 8
  } 2>/dev/null)"; then
    revoke_rc=0
  else
    revoke_rc=$?
  fi
  case "$revoke_rc:$revoke_output" in
    "0:product_reset_revocation=confirmed result=revoked")
      revoke_result="revoked"
      ;;
    "0:product_reset_revocation=confirmed result=not_device_activation")
      revoke_result="not_device_activation"
      ;;
    "10:product_reset_revocation=retryable")
      c17_4_trace "product_reset_revocation_retryable"
      return 55
      ;;
    "20:product_reset_revocation=terminal")
      c17_4_trace "product_reset_revocation_terminal"
      return 56
      ;;
    *)
      c17_4_trace "product_reset_revocation_contract_failed" rc="$revoke_rc"
      return 57
      ;;
  esac

  c17_4_trace "product_reset_finalize_start" result="$revoke_result"
  if finalize_output="$({
    /usr/bin/python3 "$WRITER" \
      --product-reset-finalize \
      --product-reset-operation-id "$operation_id" \
      --product-reset-result "$revoke_result" \
      --enable-real-write \
      --confirm-service-stopped
  } 2>/dev/null)"; then
    finalize_rc=0
  else
    finalize_rc=$?
  fi
  : "$finalize_output"
  if [ "$finalize_rc" -ne 0 ] || product_reset_pending; then
    c17_4_trace "product_reset_finalize_failed" rc="$finalize_rc"
    return 57
  fi
  c17_4_trace "product_reset_finalize_complete" result="$revoke_result"
  return 0
}

product_reset_recovery_can_open() {
  case "${1:-}:${2:-}" in
    55:keyboard_f10_hold|56:keyboard_f10_hold) return 0 ;;
    *) return 1 ;;
  esac
}

totem_core_capabilities_valid() {
  python3 - "$@" <<'PY'
import json
import os
import pathlib
import re
import stat
import sys

root = pathlib.Path("/data/core/totem")
safe_version = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
targets = []
requirements = []
for raw in sys.argv[1:]:
    if ":" not in raw:
        raise SystemExit(1)
    name, capability = raw.split(":", 1)
    if name not in {"current", "previous"} or capability not in {
        "product-reset-v1",
        "totem-actions-v1",
    }:
        raise SystemExit(1)
    requirements.append((name, capability))
if not requirements:
    raise SystemExit(1)

try:
    root_info = root.stat(follow_symlinks=False)
    releases = root / "releases"
    releases_info = releases.stat(follow_symlinks=False)
    if (
        root.is_symlink()
        or releases.is_symlink()
        or not stat.S_ISDIR(root_info.st_mode)
        or not stat.S_ISDIR(releases_info.st_mode)
        or root_info.st_uid != 0
        or releases_info.st_uid != 0
        or stat.S_IMODE(root_info.st_mode) & 0o022
        or stat.S_IMODE(releases_info.st_mode) & 0o022
    ):
        raise ValueError("untrusted root")

    for name, required_capability in requirements:
        link = root / name
        link_info = link.stat(follow_symlinks=False)
        if not stat.S_ISLNK(link_info.st_mode) or link_info.st_uid != 0:
            raise ValueError("untrusted link")
        raw_target = os.readlink(link)
        parts = pathlib.PurePosixPath(raw_target).parts
        if len(parts) != 2 or parts[0] != "releases" or not safe_version.fullmatch(parts[1]):
            raise ValueError("invalid target")
        release = releases / parts[1]
        release_info = release.stat(follow_symlinks=False)
        if (
            release.is_symlink()
            or not stat.S_ISDIR(release_info.st_mode)
            or release_info.st_uid != 0
            or stat.S_IMODE(release_info.st_mode) & 0o022
        ):
            raise ValueError("untrusted release")
        health_dir = release / "health"
        health = health_dir / "totem-core-health.json"
        health_dir_info = health_dir.stat(follow_symlinks=False)
        health_info = health.stat(follow_symlinks=False)
        if (
            health_dir.is_symlink()
            or not stat.S_ISDIR(health_dir_info.st_mode)
            or health_dir_info.st_uid != 0
            or stat.S_IMODE(health_dir_info.st_mode) & 0o022
            or health.is_symlink()
            or not stat.S_ISREG(health_info.st_mode)
            or health_info.st_uid != 0
            or health_info.st_nlink != 1
            or stat.S_IMODE(health_info.st_mode) & 0o022
            or health_info.st_size <= 0
            or health_info.st_size > 65536
        ):
            raise ValueError("untrusted health")
        payload = json.loads(health.read_text(encoding="utf-8"))
        capabilities = payload.get("capabilities")
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != "dadooh.totem.core.health.v1"
            or not isinstance(capabilities, list)
            or not all(isinstance(item, str) and item for item in capabilities)
            or required_capability not in capabilities
        ):
            raise ValueError("capability absent")
        targets.append(raw_target)
except (OSError, ValueError, json.JSONDecodeError):
    raise SystemExit(1)

raise SystemExit(0 if len(targets) == 1 or len(set(targets)) == len(targets) else 1)
PY
}

totem_core_product_reset_capable() {
  totem_core_capabilities_valid \
    "current:product-reset-v1" \
    "previous:product-reset-v1"
}

totem_actions_boot_order_safe() {
  local systemctl_bin="/usr/bin/systemctl"
  local ready_marker="/run/totem/c26-firstboot-ready.json"
  local boot_id_file="/proc/sys/kernel/random/boot_id"
  local expected_uid="0"
  local expected_gid="0"
  local properties=""
  if [ "${TOTEM_C26_TEST_MODE:-0}" = "1" ]; then
    [ "$(id -u)" -ne 0 ] || return 1
    systemctl_bin="${TOTEM_C26_TEST_SYSTEMCTL_BIN:-}"
    ready_marker="${TOTEM_C26_TEST_READY_MARKER:-}"
    boot_id_file="${TOTEM_C26_TEST_BOOT_ID_FILE:-}"
    case "$systemctl_bin:$ready_marker:$boot_id_file" in
      /tmp/*:/tmp/*:/tmp/*) ;;
      *) return 1 ;;
    esac
    [ -x "$systemctl_bin" ] || return 1
    expected_uid="$(id -u)"
    expected_gid="$(id -g)"
  fi
  properties="$("$systemctl_bin" show totem-firstboot-gate.service \
    --property=LoadState \
    --property=UnitFileState \
    --property=ActiveState \
    --property=SubState \
    --property=Result \
    --property=ExecMainStatus \
    --property=Before 2>/dev/null)" || return 1
  python3 - "$properties" "$ready_marker" "$boot_id_file" "$expected_uid" "$expected_gid" <<'PY'
import json
import os
import pathlib
import stat
import sys
import uuid

raw_properties = sys.argv[1]
ready_marker = pathlib.Path(sys.argv[2])
boot_id_file = pathlib.Path(sys.argv[3])
expected_uid = int(sys.argv[4])
expected_gid = int(sys.argv[5])

properties = {}
for line in raw_properties.splitlines():
    if "=" not in line:
        raise SystemExit(1)
    key, value = line.split("=", 1)
    if key in properties:
        raise SystemExit(1)
    properties[key] = value
expected = {
    "LoadState": "loaded",
    "UnitFileState": "enabled",
    "ActiveState": "inactive",
    "SubState": "dead",
    "Result": "success",
    "ExecMainStatus": "0",
}
if set(properties) != set(expected) | {"Before"}:
    raise SystemExit(1)
if any(properties[key] != value for key, value in expected.items()):
    raise SystemExit(1)
required_before = {
    "totem-update-agent.service",
    "totem-player-runtime-update-agent.service",
}
if not required_before <= set(properties["Before"].split()):
    raise SystemExit(1)

try:
    parent_info = os.lstat(ready_marker.parent)
    marker_info = os.lstat(ready_marker)
    boot_info = os.lstat(boot_id_file)
except OSError:
    raise SystemExit(1)
if (
    stat.S_ISLNK(parent_info.st_mode)
    or not stat.S_ISDIR(parent_info.st_mode)
    or parent_info.st_uid != expected_uid
    or parent_info.st_gid != expected_gid
    or stat.S_IMODE(parent_info.st_mode) & 0o022
    or stat.S_ISLNK(marker_info.st_mode)
    or not stat.S_ISREG(marker_info.st_mode)
    or marker_info.st_uid != expected_uid
    or marker_info.st_gid != expected_gid
    or marker_info.st_nlink != 1
    or stat.S_IMODE(marker_info.st_mode) != 0o600
    or marker_info.st_size <= 0
    or marker_info.st_size > 4096
    or stat.S_ISLNK(boot_info.st_mode)
    or not stat.S_ISREG(boot_info.st_mode)
):
    raise SystemExit(1)

flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
try:
    fd = os.open(ready_marker, flags)
    try:
        opened_info = os.fstat(fd)
        if (opened_info.st_dev, opened_info.st_ino) != (marker_info.st_dev, marker_info.st_ino):
            raise SystemExit(1)
        raw_marker = os.read(fd, 4097)
    finally:
        os.close(fd)
    payload = json.loads(raw_marker.decode("utf-8"))
except (OSError, UnicodeDecodeError, json.JSONDecodeError):
    raise SystemExit(1)
if set(payload) != {"schema_version", "boot_id", "completed_at_utc"}:
    raise SystemExit(1)
if payload.get("schema_version") != "dadooh.c26.firstboot-ready.v1":
    raise SystemExit(1)
if not isinstance(payload.get("completed_at_utc"), str) or not payload["completed_at_utc"].endswith("Z"):
    raise SystemExit(1)
boot_id = boot_id_file.read_text(encoding="ascii").strip()
try:
    parsed_boot_id = uuid.UUID(boot_id)
except ValueError:
    raise SystemExit(1)
if str(parsed_boot_id) != boot_id or payload.get("boot_id") != boot_id:
    raise SystemExit(1)
raise SystemExit(0)
PY
}

totem_actions_image_contract_safe() {
  local updatectl_bin="/opt/totem/bin/totem-updatectl"
  if [ "${TOTEM_C26_TEST_MODE:-0}" = "1" ]; then
    updatectl_bin="${TOTEM_C26_TEST_UPDATECTL_BIN:-}"
    case "$updatectl_bin" in
      /tmp/*) ;;
      *) return 1 ;;
    esac
  fi
  [ -x "$updatectl_bin" ] || return 1
  "$updatectl_bin" check-image-contract \
    --feature c26-product-reset-gc-static-v1 >/dev/null 2>&1
}

totem_core_actions_capable() {
  totem_core_capabilities_valid "current:totem-actions-v1" \
    && totem_actions_boot_order_safe \
    && totem_actions_image_contract_safe
}

consume_totem_action_request() {
  python3 - "$ACTION_REQUEST_FILE" "$ACTION_REQUEST_CONSUMED_FILE" "$SETTINGS_SESSION_ID" <<'PY'
import datetime as dt
import json
import os
import pathlib
import re
import stat
import sys
import uuid

source = pathlib.Path(sys.argv[1])
consumed = pathlib.Path(sys.argv[2])
session_id = sys.argv[3]
expected_fields = {
    "schema_version",
    "request_id",
    "settings_session_id",
    "action",
    "source",
    "confirmed_at_utc",
}

if re.fullmatch(r"[0-9a-f]{32}", session_id) is None:
    raise SystemExit(1)
try:
    parent_info = source.parent.stat(follow_symlinks=False)
    info = source.stat(follow_symlinks=False)
    if (
        source.is_symlink()
        or source.parent.is_symlink()
        or not stat.S_ISDIR(parent_info.st_mode)
        or parent_info.st_uid != os.geteuid()
        or stat.S_IMODE(parent_info.st_mode) != 0o700
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or info.st_size <= 0
        or info.st_size > 1024
        or consumed.exists()
        or consumed.is_symlink()
    ):
        raise ValueError("unsafe action request")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(source, flags)
    try:
        opened = os.fstat(fd)
        if opened.st_ino != info.st_ino or opened.st_dev != info.st_dev or opened.st_nlink != 1:
            raise ValueError("action request changed")
        chunks = []
        remaining = 1025
        while remaining > 0:
            chunk = os.read(fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
    finally:
        os.close(fd)
    if len(raw) > 1024:
        raise ValueError("action request too large")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise ValueError("action request fields")
    if payload.get("schema_version") != "dadooh.totem.action-request.v1":
        raise ValueError("action request schema")
    if payload.get("settings_session_id") != session_id:
        raise ValueError("action request session")
    if payload.get("source") != "visual_wizard_header":
        raise ValueError("action request source")
    action = payload.get("action")
    if action not in {"restart", "poweroff", "product_reset"}:
        raise ValueError("action request action")
    request_id = payload.get("request_id")
    parsed_id = uuid.UUID(str(request_id))
    if parsed_id.version != 4 or str(parsed_id) != request_id:
        raise ValueError("action request id")
    confirmed_raw = payload.get("confirmed_at_utc")
    if not isinstance(confirmed_raw, str) or not confirmed_raw.endswith("Z"):
        raise ValueError("action request time")
    confirmed = dt.datetime.fromisoformat(confirmed_raw.replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    if confirmed.utcoffset() != dt.timedelta(0) or confirmed > now + dt.timedelta(seconds=60):
        raise ValueError("action request time")
    os.replace(source, consumed)
    os.chmod(consumed, 0o600)
    parent_fd = os.open(source.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
    raise SystemExit(1)

print(action)
print(request_id)
PY
}

consume_product_reset_recovery_signal() {
  python3 - "$PRODUCT_RESET_RECOVERY_SIGNAL_FILE" "$PRODUCT_RESET_RECOVERY_SIGNAL_CONSUMED_FILE" "$SETTINGS_SESSION_ID" <<'PY'
import datetime as dt
import json
import os
import pathlib
import re
import stat
import sys

source = pathlib.Path(sys.argv[1])
consumed = pathlib.Path(sys.argv[2])
session_id = sys.argv[3]
expected_fields = {
    "schema_version",
    "settings_session_id",
    "result",
    "recorded_at_utc",
}
if re.fullmatch(r"[0-9a-f]{32}", session_id) is None:
    raise SystemExit(1)
try:
    parent_info = source.parent.stat(follow_symlinks=False)
    info = source.stat(follow_symlinks=False)
    if (
        source.is_symlink()
        or source.parent.is_symlink()
        or not stat.S_ISDIR(parent_info.st_mode)
        or parent_info.st_uid != os.geteuid()
        or stat.S_IMODE(parent_info.st_mode) != 0o700
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or info.st_size <= 0
        or info.st_size > 1024
        or consumed.exists()
        or consumed.is_symlink()
    ):
        raise ValueError("unsafe recovery signal")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(source, flags)
    try:
        opened = os.fstat(fd)
        if opened.st_ino != info.st_ino or opened.st_dev != info.st_dev or opened.st_nlink != 1:
            raise ValueError("recovery signal changed")
        raw = os.read(fd, 1025)
    finally:
        os.close(fd)
    if len(raw) > 1024:
        raise ValueError("recovery signal too large")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise ValueError("recovery signal fields")
    if payload.get("schema_version") != "dadooh.totem.product-reset-recovery.network-ready.v1":
        raise ValueError("recovery signal schema")
    if payload.get("settings_session_id") != session_id or payload.get("result") != "network_ready":
        raise ValueError("recovery signal scope")
    recorded_raw = payload.get("recorded_at_utc")
    if not isinstance(recorded_raw, str) or not recorded_raw.endswith("Z"):
        raise ValueError("recovery signal time")
    recorded = dt.datetime.fromisoformat(recorded_raw.replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    if (
        recorded.utcoffset() != dt.timedelta(0)
        or recorded > now + dt.timedelta(seconds=60)
        or recorded < now - dt.timedelta(hours=2)
    ):
        raise ValueError("recovery signal time")
    os.replace(source, consumed)
    os.chmod(consumed, 0o600)
    parent_fd = os.open(source.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
    raise SystemExit(1)
PY
}

write_terminal_action_marker() {
  local phase="$1"
  local action="$2"
  local request_id="$3"
  python3 - "$TERMINAL_ACTION_MARKER" "$phase" "$action" "$request_id" "$SETTINGS_SESSION_ID" <<'PY'
import datetime as dt
import json
import os
import pathlib
import stat
import sys
import tempfile
import uuid

target = pathlib.Path(sys.argv[1])
phase = sys.argv[2]
action = sys.argv[3]
request_id = sys.argv[4]
session_id = sys.argv[5]
expected_fields = {
    "schema_version",
    "phase",
    "action",
    "request_id",
    "settings_session_id",
    "prepared_at_utc",
    "accepted_at_utc",
}
if phase not in {"prepared", "armed", "accepted"} or action not in {"restart", "poweroff"}:
    raise SystemExit(1)
parsed_request_id = uuid.UUID(request_id)
if parsed_request_id.version != 4 or str(parsed_request_id) != request_id:
    raise SystemExit(1)
if len(session_id) != 32 or any(char not in "0123456789abcdef" for char in session_id):
    raise SystemExit(1)

parent_info = os.lstat(target.parent)
if (
    stat.S_ISLNK(parent_info.st_mode)
    or not stat.S_ISDIR(parent_info.st_mode)
    or parent_info.st_uid != os.geteuid()
    or stat.S_IMODE(parent_info.st_mode) & 0o077
):
    raise SystemExit(1)

now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
if phase == "prepared":
    try:
        os.lstat(target)
    except FileNotFoundError:
        pass
    else:
        raise SystemExit(1)
    payload = {
        "schema_version": "dadooh.c26.terminal-action.v1",
        "phase": "prepared",
        "action": action,
        "request_id": request_id,
        "settings_session_id": session_id,
        "prepared_at_utc": now,
        "accepted_at_utc": None,
    }
else:
    info = os.lstat(target)
    if (
        stat.S_ISLNK(info.st_mode)
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or info.st_size <= 0
        or info.st_size > 4096
    ):
        raise SystemExit(1)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(target, flags)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise SystemExit(1)
        prior = json.loads(os.read(fd, 4097).decode("utf-8"))
    finally:
        os.close(fd)
    if (
        not isinstance(prior, dict)
        or set(prior) != expected_fields
        or prior.get("schema_version") != "dadooh.c26.terminal-action.v1"
        or prior.get("phase") != ("prepared" if phase == "armed" else "armed")
        or prior.get("action") != action
        or prior.get("request_id") != request_id
        or prior.get("settings_session_id") != session_id
        or not isinstance(prior.get("prepared_at_utc"), str)
        or prior.get("accepted_at_utc") is not None
    ):
        raise SystemExit(1)
    payload = dict(prior)
    payload["phase"] = phase
    if phase == "accepted":
        payload["accepted_at_utc"] = now

fd, raw_tmp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
tmp = pathlib.Path(raw_tmp)
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        fd = -1
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    os.chmod(target, 0o600)
    parent_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
finally:
    if fd >= 0:
        os.close(fd)
    try:
        tmp.unlink()
    except FileNotFoundError:
        pass
PY
}

TERMINAL_ACTION_RECONCILE_UNIT=""

coalesce_terminal_action_reconcilers() {
  local keep_unit="$1"
  local listed=""
  local unit=""
  if ! [[ "$keep_unit" =~ ^totem-terminal-action-reconcile-[0-9a-f]{32}$ ]]; then
    return 1
  fi
  listed="$(/usr/bin/systemctl list-units \
    --all \
    --type=timer \
    --plain \
    --no-legend \
    'totem-terminal-action-reconcile-*.timer' 2>/dev/null)" || return 1
  while read -r unit _; do
    [ -n "$unit" ] || continue
    if ! [[ "$unit" =~ ^totem-terminal-action-reconcile-[0-9a-f]{32}\.timer$ ]]; then
      return 1
    fi
    [ "$unit" = "${keep_unit}.timer" ] && continue
    /usr/bin/timeout -k 1s 5s /usr/bin/systemctl stop "$unit" \
      >/dev/null 2>&1 || return 1
    /usr/bin/systemctl --no-block stop "${unit%.timer}.service" \
      >/dev/null 2>&1 || true
  done <<< "$listed"
}

schedule_terminal_action_reconcile() {
  local request_id="$1"
  local unit_suffix="${request_id//-/}"
  local player_was_active="false"
  local player_was_enabled="false"
  [ "$INITIAL_SERVICE_ACTIVE" = "active" ] && player_was_active="true"
  [ "$INITIAL_SERVICE_ENABLED" = "enabled" ] && player_was_enabled="true"
  TERMINAL_ACTION_RECONCILE_UNIT="totem-terminal-action-reconcile-${unit_suffix}"
  /usr/bin/systemd-run \
    --quiet \
    --collect \
    --unit="$TERMINAL_ACTION_RECONCILE_UNIT" \
    --property=DefaultDependencies=no \
    --on-active=125s \
    --on-unit-active=30s \
    --timer-property=AccuracySec=1s \
    --timer-property=DefaultDependencies=no \
    /opt/totem/bin/totem_open_settings_cleanup.sh \
      --reason terminal-action-timeout \
      --request-dir "$REQUEST_DIR" \
      --lock-dir "$LOCK_DIR" \
      --out-dir "$REQUEST_DIR" \
      --tty "$REMOTE_TTY" \
      --expire-terminal-action \
      --terminal-action-reconcile-unit "$TERMINAL_ACTION_RECONCILE_UNIT" \
      --terminal-action-player-was-active "$player_was_active" \
      --terminal-action-player-was-enabled "$player_was_enabled" \
      >/dev/null 2>&1 || return 1
  if ! coalesce_terminal_action_reconcilers "$TERMINAL_ACTION_RECONCILE_UNIT"; then
    /usr/bin/systemctl --no-block stop "$TERMINAL_ACTION_RECONCILE_UNIT.timer" \
      "$TERMINAL_ACTION_RECONCILE_UNIT.service" >/dev/null 2>&1 || true
    return 1
  fi
}

cancel_terminal_action_reconcile() {
  [ -n "$TERMINAL_ACTION_RECONCILE_UNIT" ] || return 0
  /usr/bin/systemctl --no-block stop "${TERMINAL_ACTION_RECONCILE_UNIT}.timer" \
    "${TERMINAL_ACTION_RECONCILE_UNIT}.service" >/dev/null 2>&1 || true
}

write_product_reset_resume_request() {
  python3 - "$REQUEST_FILE" <<'PY'
import json
import os
import pathlib
import tempfile
import time
import sys

target = pathlib.Path(sys.argv[1])
payload = {
    "schema_version": 1,
    "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "trigger_type": "product_reset_resume",
    "action": "open_settings",
}
fd, raw_tmp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
tmp = pathlib.Path(raw_tmp)
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        fd = -1
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    os.chmod(target, 0o600)
    parent_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
finally:
    if fd >= 0:
        os.close(fd)
    try:
        tmp.unlink()
    except FileNotFoundError:
        pass
PY
}

bootstrap_exit() {
  local rc="${1:-$?}"
  trap - EXIT INT TERM HUP
  cleanup_update_lock
  remove_session_lock_if_safe
  exit "$rc"
}
bootstrap_term() { bootstrap_exit 143; }
bootstrap_int()  { bootstrap_exit 130; }
bootstrap_hup()  { bootstrap_exit 129; }

# Protect the session marker from the first mutating operation onward. The
# complete cleanup handler replaces these traps before the player is stopped.
trap bootstrap_exit EXIT
trap bootstrap_term TERM
trap bootstrap_int  INT
trap bootstrap_hup  HUP

umask 077
mkdir -p "$(dirname "$LOCK_DIR")" "$REQUEST_DIR"
chmod 700 "$REQUEST_DIR" 2>/dev/null || true
chmod 755 "$(dirname "$LOCK_DIR")" 2>/dev/null || true
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  if { product_reset_guard_required || product_reset_resume_request_is_trusted; } \
    && product_reset_lock_is_trusted; then
    PRODUCT_RESET_GUARD_ADOPTED="true"
    c17_4_trace "product_reset_guard_adopted"
  else
    echo "settings_session_already_running" >&2
    exit 23
  fi
fi
chmod 755 "$LOCK_DIR" 2>/dev/null || true
c17_4_trace "session_lock_acquired"

coproc UPDATE_LOCK_HOLDER {
  exec /usr/bin/python3 /dev/fd/3 "$UPDATE_LOCK_FILE" "$$" 3<<'PY'
import fcntl
import os
import pathlib
import stat
import sys
import time

path = pathlib.Path(sys.argv[1])
parent_pid = int(sys.argv[2])
try:
    if (
        not path.is_absolute()
        or str(path) != os.path.normpath(str(path))
        or path.parent.resolve(strict=True) != path.parent
    ):
        raise RuntimeError("lock_path_invalid")
    parent_info = path.parent.stat()
    if (
        not stat.S_ISDIR(parent_info.st_mode)
        or parent_info.st_uid != os.geteuid()
        or stat.S_IMODE(parent_info.st_mode) & 0o022
    ):
        raise RuntimeError("lock_parent_untrusted")
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("lock_nofollow_unavailable")
    fd = os.open(
        path,
        os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
    )
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
        raise RuntimeError("lock_file_untrusted")
    os.fchmod(fd, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("BUSY", flush=True)
        raise SystemExit(0)
    print("LOCKED", flush=True)
    while os.getppid() == parent_pid:
        time.sleep(0.2)
except Exception as exc:
    print(f"ERROR:{type(exc).__name__}", flush=True)
    raise SystemExit(1)
PY
}
UPDATE_LOCK_HOLDER_ACTIVE_PID="$UPDATE_LOCK_HOLDER_PID"
UPDATE_LOCK_STATUS_FD="${UPDATE_LOCK_HOLDER[0]}"
UPDATE_LOCK_INPUT_FD="${UPDATE_LOCK_HOLDER[1]}"
exec {UPDATE_LOCK_INPUT_FD}>&-
UPDATE_LOCK_STATUS=""
IFS= read -r UPDATE_LOCK_STATUS <&"$UPDATE_LOCK_STATUS_FD" || true
exec {UPDATE_LOCK_STATUS_FD}<&-
if [ "$UPDATE_LOCK_STATUS" != "LOCKED" ]; then
  cleanup_update_lock
  remove_session_lock_if_safe
  if [ "$UPDATE_LOCK_STATUS" = "BUSY" ]; then
    echo "settings_deferred_update_active" >&2
  else
    echo "settings_update_lock_unavailable" >&2
  fi
  exit 25
fi

# Fixed /tmp paths are reused by systemd, so every lock owner needs fresh evidence.
if ! python3 - \
  "$OUT_DIR" "$WIZARD_OUT_DIR" "$HANDOFF_OUT_DIR" "$WRITER_OUT_DIR" "$PRIVATE_VALUES_DIR" \
  "$LOCK_DIR" "$REQUEST_DIR" "$APPLY_POLICY_PATH" "$UPDATE_LOCK_FILE" <<'PY'
import os
import pathlib
import re
import shutil
import stat
import sys

allowed_roots = tuple(pathlib.Path(raw).resolve() for raw in ("/tmp", "/run"))
scratch_paths = [pathlib.Path(raw) for raw in sys.argv[1:6]]
protected_paths = [pathlib.Path(raw) for raw in sys.argv[6:]]
euid = os.geteuid()
mount_escape = re.compile(r"\\([0-7]{3})")


def decode_mount_field(raw: str) -> str:
    return mount_escape.sub(lambda match: chr(int(match.group(1), 8)), raw)


def current_mount_points() -> set[pathlib.Path]:
    mountinfo = pathlib.Path("/proc/self/mountinfo")
    try:
        lines = mountinfo.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SystemExit("session_mountinfo_unavailable") from exc
    points = set()
    for line in lines:
        fields = line.split()
        if len(fields) < 6 or "-" not in fields:
            raise SystemExit("session_mountinfo_invalid")
        point = pathlib.Path(decode_mount_field(fields[4]))
        if point.is_absolute():
            points.add(point)
    return points


def reject_mount_boundary(path: pathlib.Path) -> None:
    for mount_point in current_mount_points():
        if mount_point == path or path in mount_point.parents:
            raise SystemExit("session_scratch_mount_boundary")
        if (
            mount_point in path.parents
            and mount_point not in allowed_roots
            and any(root in mount_point.parents for root in allowed_roots)
        ):
            raise SystemExit("session_scratch_mount_ancestor")


def normalized_allowed(path: pathlib.Path, *, label: str) -> pathlib.Path:
    raw = str(path)
    if not path.is_absolute() or raw != os.path.normpath(raw):
        raise SystemExit(f"{label}_path_not_normalized")
    resolved = path.resolve(strict=False)
    if path != resolved or path in allowed_roots:
        raise SystemExit(f"{label}_path_invalid")
    if not any(root in path.parents for root in allowed_roots):
        raise SystemExit(f"{label}_path_outside_allowed_roots")
    return path


scratch_paths = [normalized_allowed(path, label="session_scratch") for path in scratch_paths]
protected_paths = [normalized_allowed(path, label="session_protected") for path in protected_paths]
if len(set(scratch_paths)) != len(scratch_paths):
    raise SystemExit("session_scratch_paths_not_distinct")
for index, path in enumerate(scratch_paths):
    for other in scratch_paths[index + 1 :]:
        if path in other.parents or other in path.parents:
            raise SystemExit("session_scratch_paths_overlap")
    for protected in protected_paths:
        if path == protected or path in protected.parents or protected in path.parents:
            raise SystemExit("session_scratch_overlaps_protected_path")


def validate_existing_ancestors(path: pathlib.Path) -> None:
    for parent in path.parents:
        if parent in allowed_roots:
            return
        if not parent.exists() or parent.is_symlink():
            raise SystemExit("session_scratch_parent_invalid")
        info = parent.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != euid or stat.S_IMODE(info.st_mode) & 0o022:
            raise SystemExit("session_scratch_parent_untrusted")
    raise SystemExit("session_scratch_parent_outside_allowed_roots")


def clear_scratch(path: pathlib.Path) -> None:
    if path.exists():
        validate_existing_ancestors(path)
        info = path.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != euid or stat.S_IMODE(info.st_mode) != 0o700:
            raise SystemExit("session_scratch_root_untrusted")
    else:
        nearest = path.parent
        while not nearest.exists():
            nearest = nearest.parent
        validate_existing_ancestors(nearest / "placeholder")
        path.mkdir(mode=0o700, parents=True)
        os.chmod(path, 0o700)
    if path.is_symlink():
        raise SystemExit("session_scratch_root_link_or_mount")
    reject_mount_boundary(path)
    if not shutil.rmtree.avoids_symlink_attacks:
        raise SystemExit("session_scratch_platform_not_symlink_safe")

    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    root_fd = os.open(path, flags)
    try:
        root_info = os.fstat(root_fd)
        root_view = pathlib.Path(f"/proc/self/fd/{root_fd}")
        for current, directories, files in os.walk(root_view, topdown=True, followlinks=False):
            current_path = pathlib.Path(current)
            for name in [*directories, *files]:
                entry = current_path / name
                if entry.lstat().st_dev != root_info.st_dev:
                    raise SystemExit("session_scratch_cross_device_entry")
        for name in os.listdir(root_fd):
            entry_info = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            if stat.S_ISDIR(entry_info.st_mode):
                shutil.rmtree(name, dir_fd=root_fd)
            else:
                os.unlink(name, dir_fd=root_fd)
    finally:
        os.close(root_fd)

for scratch_path in scratch_paths:
    clear_scratch(scratch_path)
PY
then
  remove_session_lock_if_safe
  echo "session_scratch_reset_failed" >&2
  exit 24
fi
SETTINGS_SESSION_ID="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(16))
PY
)"
if [ -z "$SETTINGS_SESSION_ID" ]; then
  echo "settings_session_id_unavailable" >&2
  exit 24
fi
if totem_core_actions_capable; then
  TOTEM_ACTIONS_AVAILABLE="1"
  c17_4_trace "totem_actions_capability_available"
else
  TOTEM_ACTIONS_AVAILABLE="0"
  c17_4_trace "totem_actions_capability_unavailable"
fi
if [ "$TOTEM_ACTIONS_AVAILABLE" = "1" ] && totem_core_product_reset_capable \
  && ! product_reset_guard_required && ! product_reset_cleanup_pending; then
  PRODUCT_RESET_AVAILABLE="1"
  c17_4_trace "product_reset_capability_available"
else
  PRODUCT_RESET_AVAILABLE="0"
  c17_4_trace "product_reset_capability_unavailable"
fi

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
  restore_tty_console_mode || true
  command -v chvt >/dev/null 2>&1 && run_short chvt "$REMOTE_TTY"
  if [ -x "$TTY_GUARD" ]; then
    run_short "$TTY_GUARD" --clear --tty "$REMOTE_TTY"
  fi
  write_tty_payload '\033c\033[2J\033[3J\033[H\033[?25l'
  sleep 0.05
  write_tty_payload '\033c\033[2J\033[3J\033[H\033[?25l'
  if [ -n "$rotation" ] && [ "$rotation" != "unknown" ]; then
    run_tty_command 4s env TERM=linux PYTHONPATH="$SCRIPT_DIR" python3 "$SPLASH" "$mode" --rotation-deg "$rotation" --status-out "$OUT_DIR/splash-$mode-status.json"
  else
    run_tty_command 4s env TERM=linux PYTHONPATH="$SCRIPT_DIR" python3 "$SPLASH" "$mode" --status-out "$OUT_DIR/splash-$mode-status.json"
  fi
}

restore_getty() {
  if [ "$RESTORE_GETTY_AFTER_SETTINGS" != "1" ]; then
    for unit in "${GETTY_UNITS[@]}"; do
      systemctl disable "$unit" >/dev/null 2>&1 || true
      systemctl stop "$unit" >/dev/null 2>&1 || true
    done
    if [ -x "$TTY_GUARD" ]; then
      run_short "$TTY_GUARD" --quiet --tty 1 --tty "$REMOTE_TTY"
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
    SERVICE_RESTORE_START_MODE="no-block"
    if /usr/bin/timeout -k 1s 5s systemctl start --no-block kiosky-player.service >/dev/null 2>&1; then
      SERVICE_RESTORE_START_RC="0"
    else
      SERVICE_RESTORE_START_RC="$?"
    fi
    c1523_phase "player_restore_enqueued mode=$SERVICE_RESTORE_START_MODE rc=$SERVICE_RESTORE_START_RC active=$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
    if [ "$SERVICE_RESTORE_START_RC" != "0" ]; then
      return "$SERVICE_RESTORE_START_RC"
    fi
  fi
}

stop_openvt_if_running() {
  local pid="${OPENVT_PID:-}"
  [ -n "$pid" ] || return 0

  if kill -0 -- "-$pid" 2>/dev/null || kill -0 "$pid" 2>/dev/null; then
    c15_trace "openvt_stop_begin pid=$pid"
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 10); do
      if ! kill -0 -- "-$pid" 2>/dev/null && ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 0.1
    done
    if kill -0 -- "-$pid" 2>/dev/null || kill -0 "$pid" 2>/dev/null; then
      c15_trace "openvt_stop_escalate pid=$pid"
      kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
    fi
  fi
  wait "$pid" 2>/dev/null || true
  OPENVT_PID=""
  c15_trace "openvt_stop_done pid=$pid"
}

kill_visual_if_running() {
  python3 - "$VISUAL" "$WIZARD_OUT_DIR" "$$" "$BASHPID" <<'PY'
import os
import pathlib
import signal
import sys
import time
visual = sys.argv[1]
out = sys.argv[2]
skip = {os.getpid(), os.getppid()}
for raw in sys.argv[3:]:
    try:
        skip.add(int(raw))
    except ValueError:
        pass
pids = []
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) in skip:
        continue
    try:
        parts = [part.decode("utf-8", "ignore") for part in (proc / "cmdline").read_bytes().split(b"\0") if part]
    except OSError:
        continue
    joined = " ".join(parts)
    if "totem_open_settings_session.sh" in joined:
        continue
    if visual in joined and out in joined:
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
if private_source not in {"none", "active-config", "homologation-seed"}:
    raise SystemExit("apply_policy_private_source_invalid")
private_values = data.get("private_values_path") or default_private
if private_source == "homologation-seed":
    if private_values != "/data/state/totem-settings/private-values.seed.json":
        raise SystemExit("apply_policy_private_values_invalid")
    if not bool(data.get("homologation_seed", False)):
        raise SystemExit("apply_policy_homologation_seed_not_marked")
else:
    if not isinstance(private_values, str):
        raise SystemExit("apply_policy_private_values_invalid")
    if private_source in {"none", "active-config"} and private_values != default_private:
        raise SystemExit("apply_policy_private_values_not_session_owned")
    private_path = pathlib.Path(private_values)
    if (
        str(private_path) != os.path.normpath(str(private_path))
        or private_path != private_path.resolve(strict=False)
        or pathlib.Path("/tmp") not in private_path.parents
        or private_path.parent == pathlib.Path("/tmp")
    ):
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
if (
    str(target) != os.path.normpath(str(target))
    or target != target.resolve(strict=False)
    or pathlib.Path("/tmp") not in target.parents
    or target.parent == pathlib.Path("/tmp")
):
    raise SystemExit("private_values_target_not_tmp")
if target.is_symlink():
    raise SystemExit("private_values_target_symlink")
target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
parent_info = target.parent.stat()
if parent_info.st_uid != os.geteuid() or stat.S_IMODE(parent_info.st_mode) != 0o700:
    raise SystemExit("private_values_parent_untrusted")
with active.open("r", encoding="utf-8") as handle:
    config = json.load(handle)
payload = {}
for field in ("api_url", "api_key", "station_id", "api_token_id"):
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
    if [ -e "$PRIVATE_VALUES" ] || [ -L "$PRIVATE_VALUES" ]; then
      echo "unexpected_private_values_for_none_source" >&2
      return 1
    fi
    return 0
  fi
  python3 - "$PRIVATE_VALUES" <<'PY'
import os
import pathlib
import stat
import sys
path = pathlib.Path(sys.argv[1])
is_tmp = pathlib.Path("/tmp") in path.parents and path.parent != pathlib.Path("/tmp")
is_seed = str(path) == "/data/state/totem-settings/private-values.seed.json"
if (
    (not is_tmp and not is_seed)
    or str(path) != os.path.normpath(str(path))
    or path != path.resolve(strict=False)
    or path.is_symlink()
    or not path.exists()
):
    raise SystemExit("private_values_not_ready")
if path.parent.is_symlink():
    raise SystemExit("private_values_parent_symlink")
parent_info = path.parent.stat()
if parent_info.st_uid != os.geteuid() or stat.S_IMODE(parent_info.st_mode) != 0o700:
    raise SystemExit("private_values_parent_permissive")
mode = stat.S_IMODE(path.stat().st_mode)
if mode & 0o077 or not (mode & 0o600):
    raise SystemExit("private_values_file_permissive")
PY
}

select_qr_pairing_private_values_if_available() {
  if [ "$APPLY_MODE" != "dry-run" ] && [ "$APPLY_MODE" != "real-write" ]; then
    return 0
  fi
  local result_path="$WIZARD_OUT_DIR/qr-pairing/pairing-result.public.json"
  if [ ! -f "$result_path" ]; then
    return 0
  fi
  eval "$(
    python3 - "$result_path" "$WIZARD_OUT_DIR/qr-pairing/private-values.json" <<'PY'
import json
import os
import pathlib
import shlex
import stat
import sys

result_path = pathlib.Path(sys.argv[1])
expected_private_path = pathlib.Path(sys.argv[2])
if result_path.is_symlink() or result_path.parent.is_symlink():
    raise SystemExit("pairing_result_symlink")
try:
    result = json.loads(result_path.read_text(encoding="utf-8"))
except Exception as exc:
    raise SystemExit("pairing_result_invalid") from exc
if not isinstance(result, dict):
    raise SystemExit("pairing_result_not_object")
if result.get("passed") is not True or result.get("state") != "authorized":
    raise SystemExit(0)
raw_private = result.get("private_values_path")
if not isinstance(raw_private, str) or not raw_private.strip():
    raise SystemExit("pairing_private_values_missing")
private_path = pathlib.Path(raw_private)
if private_path != expected_private_path:
    raise SystemExit("pairing_private_values_not_session_owned")
if (
    str(private_path) != os.path.normpath(str(private_path))
    or private_path.is_symlink()
    or private_path.parent.is_symlink()
    or private_path.parent == pathlib.Path("/tmp")
):
    raise SystemExit("pairing_private_values_symlink")
try:
    resolved = private_path.resolve(strict=True)
except OSError as exc:
    raise SystemExit("pairing_private_values_missing") from exc
if not str(resolved).startswith("/tmp/"):
    raise SystemExit("pairing_private_values_not_tmp")
if not resolved.is_file():
    raise SystemExit("pairing_private_values_not_file")
parent_info = resolved.parent.stat()
parent_mode = stat.S_IMODE(parent_info.st_mode)
file_mode = stat.S_IMODE(resolved.stat().st_mode)
if parent_info.st_uid != os.geteuid() or parent_mode != 0o700:
    raise SystemExit("pairing_private_values_parent_permissive")
if file_mode & 0o077 or not (file_mode & 0o600):
    raise SystemExit("pairing_private_values_file_permissive")
try:
    private_values = json.loads(resolved.read_text(encoding="utf-8"))
except Exception as exc:
    raise SystemExit("pairing_private_values_invalid_json") from exc
if not isinstance(private_values, dict):
    raise SystemExit("pairing_private_values_not_object")
for field in ("api_url", "api_key", "environment_id"):
    value = private_values.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit("pairing_private_values_required_missing")
print(f"PRIVATE_VALUES={shlex.quote(str(resolved))}")
print("POLICY_PRIVATE_SOURCE=tmp-file")
print("HOMOLOGATION_SEED_MODE=false")
print("PAIRING_PRIVATE_VALUES_USED=true")
PY
  )"
  validate_private_values_metadata
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

candidate_is_current_session_ready() {
  python3 - "$WIZARD_OUT_DIR/config.candidate.json" "$WIZARD_OUT_DIR/setup-status.json" "$SETTINGS_SESSION_ID" <<'PY'
import json
import pathlib
import sys

candidate = pathlib.Path(sys.argv[1])
status_path = pathlib.Path(sys.argv[2])
expected_session_id = sys.argv[3]
for path in (candidate, status_path):
    if path.is_symlink() or not path.is_file():
        raise SystemExit("current_session_candidate_artifact_missing")
try:
    status = json.loads(status_path.read_text(encoding="utf-8"))
except Exception as exc:
    raise SystemExit("current_session_status_invalid") from exc
if not isinstance(status, dict) or status.get("state") != "candidate_ready":
    raise SystemExit("current_session_status_not_ready")
if not expected_session_id or status.get("settings_session_id") != expected_session_id:
    raise SystemExit("current_session_id_mismatch")
guardrails = status.get("guardrails")
if not isinstance(guardrails, dict) or guardrails.get("candidate_generated") is not True:
    raise SystemExit("current_session_candidate_not_attested")
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
  local pairing_private_values="$WIZARD_OUT_DIR/qr-pairing/private-values.json"
  if [ "$WIZARD_PRIVATE_SETTINGS_CONTEXT_PATH" != "$PRIVATE_SETTINGS_CONTEXT_PATH" ]; then
    rm -f -- "$WIZARD_PRIVATE_SETTINGS_CONTEXT_PATH" || true
  fi
  if [ -f "$HANDOFF_OUT_DIR/config.candidate.private.json" ]; then
    rm -f "$HANDOFF_OUT_DIR/config.candidate.private.json" || true
  fi
  if [ ! -e "$HANDOFF_OUT_DIR/config.candidate.private.json" ]; then
    PRIVATE_CANDIDATE_REMOVED="true"
  fi
  local initial_private_parent
  initial_private_parent="$(dirname -- "$INITIAL_PRIVATE_VALUES_PATH")"
  case "$INITIAL_PRIVATE_VALUES_PATH" in
    /tmp/?*) rm -f -- "$INITIAL_PRIVATE_VALUES_PATH" || true ;;
  esac
  case "$initial_private_parent" in
    /tmp/?*) rmdir -- "$initial_private_parent" 2>/dev/null || true ;;
  esac
  if [ "$PAIRING_PRIVATE_VALUES_USED" = "true" ]; then
    rm -f "$PRIVATE_VALUES" || true
  fi
  if [ -e "$pairing_private_values" ] || [ -L "$pairing_private_values" ]; then
    rm -f -- "$pairing_private_values" || true
  fi
  if [ ! -e "$INITIAL_PRIVATE_VALUES_PATH" ] && [ ! -L "$INITIAL_PRIVATE_VALUES_PATH" ] \
    && [ ! -e "$pairing_private_values" ] && [ ! -L "$pairing_private_values" ]; then
    PRIVATE_SOURCE_TEMP_REMOVED="true"
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
  if product_reset_guard_required; then
    return 0
  fi
  case "$REQUEST_FILE" in
    /run/*|/tmp/*)
      rm -f "$REQUEST_FILE" || true
      ;;
  esac
}

cleanup_session_lock() {
  if product_reset_guard_required; then
    return 0
  fi
  case "$LOCK_DIR" in
    /run/*|/tmp/*)
      rmdir -- "$LOCK_DIR" 2>/dev/null || true
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
  local player_wait_mode="${1:-wait-player}"
  if [ "$player_wait_mode" = "skip-player-wait" ]; then
    c15_trace "write_final_status_skip_player_wait signal_stop=$SIGNAL_STOP"
    c1523_phase "write_final_status_skip_player_wait signal_stop=$SIGNAL_STOP"
  elif [ -e "$LOCK_DIR" ]; then
    c15_trace "write_final_status_skip_wait_session_lock_present"
    c1523_phase "write_final_status_skip_wait_session_lock_present"
  else
    wait_player_running || true
  fi
  env \
    FINAL_STATUS_PLAYER_WAIT_MODE="$player_wait_mode" \
    SIGNAL_STOP_REASON="$SIGNAL_STOP_REASON" \
    SERVICE_RESTORE_START_MODE="$SERVICE_RESTORE_START_MODE" \
    SERVICE_RESTORE_START_RC="$SERVICE_RESTORE_START_RC" \
    SERVICE_RESULT_AFTER="$(systemctl show kiosky-player.service -p Result --value 2>/dev/null || true)" \
    SERVICE_EXEC_MAIN_STATUS_AFTER="$(systemctl show kiosky-player.service -p ExecMainStatus --value 2>/dev/null || true)" \
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
    "service_restore_start_mode": os.environ.get("SERVICE_RESTORE_START_MODE", "none"),
    "service_restore_start_rc": (
        int(os.environ["SERVICE_RESTORE_START_RC"])
        if os.environ.get("SERVICE_RESTORE_START_RC", "").isdigit()
        else None
    ),
    "service_restore_enqueued": service_restore_attempted and os.environ.get("SERVICE_RESTORE_START_RC") == "0",
    "final_status_player_wait_mode": os.environ.get("FINAL_STATUS_PLAYER_WAIT_MODE", "wait-player"),
    "signal_stop_reason": os.environ.get("SIGNAL_STOP_REASON", "none"),
    "service_result_after": os.environ.get("SERVICE_RESULT_AFTER") or "unknown",
    "service_exec_main_status_after": os.environ.get("SERVICE_EXEC_MAIN_STATUS_AFTER") or "unknown",
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
  rc="${1:-$?}"
  final_status_mode="wait-player"
  trap - EXIT INT TERM HUP
  c15_trace "on_exit_begin rc=$rc"
  c1523_phase "session_cleanup_start rc=$rc"
  if [ "$SIGNAL_STOP" = "true" ]; then
    final_status_mode="skip-player-wait"
  fi
  stop_openvt_if_running || true
  kill_visual_if_running || true
  restore_tty_console_mode || true
  cleanup_private_artifacts || true
  cleanup_apply_policy || true
  if [ "$TERMINAL_ACTION_PENDING" = "true" ]; then
    c15_trace "on_exit_terminal_action_pending"
    write_final_status "skip-player-wait" || true
    cleanup_update_lock
    c1523_phase "session_terminal_action_pending rc=$rc"
    exit "$rc"
  fi
  cleanup_trigger_request || true
  cleanup_session_lock || true
  c17_4_trace "session_lock_released"
  restore_service || true
  write_final_status "$final_status_mode" || true
  restore_getty || true
  cleanup_update_lock
  c1523_phase "session_done rc=$rc"
  c15_trace "on_exit_done rc=$rc"
  exit "$rc"
}
on_term() { SIGNAL_STOP="true"; SIGNAL_STOP_REASON="TERM"; c15_trace "trap_signal=TERM"; on_exit 0; }
on_int()  { SIGNAL_STOP="true"; SIGNAL_STOP_REASON="INT";  c15_trace "trap_signal=INT";  on_exit 130; }
on_hup()  { SIGNAL_STOP="true"; SIGNAL_STOP_REASON="HUP";  c15_trace "trap_signal=HUP";  on_exit 129; }
trap on_exit EXIT
trap on_term TERM
trap on_int  INT
trap on_hup  HUP

load_apply_policy
if product_reset_pending; then
  if [ "$POLICY_PRIVATE_SOURCE" = "homologation-seed" ]; then
    APPLY_MODE="candidate-only"
    POLICY_PRIVATE_SOURCE="none"
    PRIVATE_VALUES="$INITIAL_PRIVATE_VALUES_PATH"
    HOMOLOGATION_SEED_MODE="false"
    cleanup_apply_policy || true
  fi
elif product_reset_onboarding_pending \
  || [ -e "$PRODUCT_RESET_STATE_DIR/homologation-seed-disabled.json" ] \
  || [ -L "$PRODUCT_RESET_STATE_DIR/homologation-seed-disabled.json" ]; then
  if [ "$POLICY_PRIVATE_SOURCE" = "homologation-seed" ] \
    || ! product_reset_homologation_seed_disabled_safe; then
    echo "product_reset_homologation_seed_fail_closed" >&2
    exit 25
  fi
fi
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
    WIZARD_PRIVATE_SETTINGS_CONTEXT_PATH="$PRIVATE_VALUES_DIR/last-settings.json"
    write_private_settings_context \
      /data/config/config.json active_config_prefill "$WIZARD_PRIVATE_SETTINGS_CONTEXT_PATH" || true
    if [ -f "$WIZARD_PRIVATE_SETTINGS_CONTEXT_PATH" ]; then
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

if product_reset_pending; then
  c15_trace "product_reset_recovery_begin"
  if resume_product_reset_if_pending; then
    c15_trace "product_reset_recovery_complete"
  else
    product_reset_recovery_rc=$?
    c15_trace "product_reset_recovery_deferred rc=$product_reset_recovery_rc"
    show_transition product_reset_pending || true
    request_trigger="$(settings_request_trigger_type 2>/dev/null || true)"
    if product_reset_recovery_can_open "$product_reset_recovery_rc" "$request_trigger"; then
      PRODUCT_RESET_RECOVERY_MODE="1"
      PRODUCT_RESET_AVAILABLE="0"
      c17_4_trace "product_reset_recovery_opening" rc="$product_reset_recovery_rc"
    else
      exit "$product_reset_recovery_rc"
    fi
  fi
fi
if product_reset_guard_required \
  || [ -e "$PRODUCT_RESET_STATE_DIR/homologation-seed-disabled.json" ] \
  || [ -L "$PRODUCT_RESET_STATE_DIR/homologation-seed-disabled.json" ]; then
  if ! product_reset_homologation_seed_disabled_safe; then
    echo "product_reset_homologation_seed_fail_closed" >&2
    exit 25
  fi
fi

c15_trace "before_openvt"
c17_4_trace "wizard_surface_owner"
c1523_phase "wizard_started"

set +e
if [ "$MODE" = "preview" ]; then
  /usr/bin/setsid --wait /usr/bin/openvt -c "$REMOTE_TTY" -s -f -e -- \
    /usr/bin/env TERM=linux PYTHONPATH="$SCRIPT_DIR" TOTEM_SETTINGS_SESSION_ID="$SETTINGS_SESSION_ID" TOTEM_TOTEM_ACTIONS_AVAILABLE="$TOTEM_ACTIONS_AVAILABLE" TOTEM_PRODUCT_RESET_AVAILABLE="$PRODUCT_RESET_AVAILABLE" TOTEM_PRODUCT_RESET_RECOVERY_MODE="$PRODUCT_RESET_RECOVERY_MODE" TOTEM_VISUAL_WIZARD_APPLY_CONTEXT="$APPLY_MODE" TOTEM_VISUAL_WIZARD_HOMOLOGATION_MODE="$HOMOLOGATION_SEED_MODE" /usr/bin/python3 "$VISUAL" \
      --out-dir "$WIZARD_OUT_DIR" --private-settings-context-path "$WIZARD_PRIVATE_SETTINGS_CONTEXT_PATH" \
      --preview-screens --show-preview --auto-exit-sec "$PREVIEW_SEC" >/dev/null 2>&1
  WIZARD_RC="$?"
else
  /usr/bin/setsid --wait /usr/bin/openvt -c "$REMOTE_TTY" -s -f -e -- \
    /usr/bin/env TERM=linux PYTHONPATH="$SCRIPT_DIR" TOTEM_SETTINGS_SESSION_ID="$SETTINGS_SESSION_ID" TOTEM_TOTEM_ACTIONS_AVAILABLE="$TOTEM_ACTIONS_AVAILABLE" TOTEM_PRODUCT_RESET_AVAILABLE="$PRODUCT_RESET_AVAILABLE" TOTEM_PRODUCT_RESET_RECOVERY_MODE="$PRODUCT_RESET_RECOVERY_MODE" TOTEM_VISUAL_WIZARD_APPLY_CONTEXT="$APPLY_MODE" TOTEM_VISUAL_WIZARD_HOMOLOGATION_MODE="$HOMOLOGATION_SEED_MODE" /usr/bin/python3 "$VISUAL" \
      --out-dir "$WIZARD_OUT_DIR" --private-settings-context-path "$WIZARD_PRIVATE_SETTINGS_CONTEXT_PATH" >/dev/null 2>&1 &
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
    wait "$OPENVT_PID" 2>/dev/null || true
    WIZARD_RC="124"
  else
    wait "$OPENVT_PID"
    WIZARD_RC="$?"
    c15_trace "openvt_exited WIZARD_RC=$WIZARD_RC"
  fi
  OPENVT_PID=""
fi
set -e
restore_tty_console_mode || true
c15_trace "after_wizard WIZARD_RC=$WIZARD_RC"

if [ "$WIZARD_RC" = "76" ]; then
  if [ "$PRODUCT_RESET_RECOVERY_MODE" != "1" ] || ! product_reset_pending; then
    echo "product_reset_recovery_signal_out_of_context" >&2
    exit 47
  fi
  if ! consume_product_reset_recovery_signal; then
    echo "product_reset_recovery_signal_invalid" >&2
    exit 47
  fi
  if [ -e "$ACTION_REQUEST_FILE" ] || [ -L "$ACTION_REQUEST_FILE" ]; then
    echo "totem_action_request_during_product_reset_recovery" >&2
    exit 47
  fi
  if ! write_product_reset_resume_request; then
    echo "product_reset_resume_request_failed" >&2
    exit 47
  fi
  c17_4_trace "product_reset_network_repair_complete"
  show_transition product_reset_pending || true
  exit 0
elif [ -e "$PRODUCT_RESET_RECOVERY_SIGNAL_FILE" ] || [ -L "$PRODUCT_RESET_RECOVERY_SIGNAL_FILE" ]; then
  echo "product_reset_recovery_signal_without_exit_code" >&2
  exit 47
elif [ "$WIZARD_RC" = "75" ]; then
  mapfile -t action_request_fields < <(consume_totem_action_request)
  if [ "${#action_request_fields[@]}" -ne 2 ]; then
    echo "totem_action_request_invalid" >&2
    exit 47
  fi
  requested_action="${action_request_fields[0]}"
  requested_action_id="${action_request_fields[1]}"
  if [ "$TOTEM_ACTIONS_AVAILABLE" != "1" ] || ! totem_core_actions_capable; then
    echo "totem_actions_capability_unavailable" >&2
    exit 47
  fi
  c15_trace "totem_action_request_consumed action=$requested_action"
  case "$requested_action" in
    restart|poweroff)
      terminal_command="$requested_action"
      [ "$requested_action" = "restart" ] && terminal_command="reboot"
      if ! write_terminal_action_marker "prepared" "$requested_action" "$requested_action_id"; then
        echo "totem_terminal_action_marker_failed" >&2
        exit 47
      fi
      if ! schedule_terminal_action_reconcile "$requested_action_id"; then
        rm -f -- "$TERMINAL_ACTION_MARKER" 2>/dev/null || true
        echo "totem_terminal_action_reconcile_schedule_failed" >&2
        exit 47
      fi
      if ! write_terminal_action_marker "armed" "$requested_action" "$requested_action_id"; then
        cancel_terminal_action_reconcile
        rm -f -- "$TERMINAL_ACTION_MARKER" 2>/dev/null || true
        echo "totem_terminal_action_arm_failed" >&2
        exit 47
      fi
      # Shutdown may stop this service as soon as systemd accepts the request.
      # Arm the delayed recovery path before entering that interruption window.
      TERMINAL_ACTION_PENDING="true"
      if /usr/bin/systemctl --no-block "$terminal_command" >/dev/null 2>&1; then
        if ! write_terminal_action_marker "accepted" "$requested_action" "$requested_action_id"; then
          echo "totem_terminal_action_acceptance_marker_failed" >&2
          exit 47
        fi
        c17_4_trace "totem_terminal_action_accepted" action="$requested_action"
        exit 0
      fi
      if ! rm -f -- "$TERMINAL_ACTION_MARKER" 2>/dev/null; then
        echo "totem_terminal_action_disarm_failed" >&2
        exit 47
      fi
      TERMINAL_ACTION_PENDING="false"
      cancel_terminal_action_reconcile
      echo "totem_terminal_action_failed" >&2
      exit 47
      ;;
    product_reset)
      if [ "$PRODUCT_RESET_AVAILABLE" != "1" ] || ! totem_core_product_reset_capable \
        || product_reset_cleanup_pending; then
        echo "product_reset_capability_unavailable" >&2
        exit 47
      fi
      reset_start_output=""
      if reset_start_output="$({
        /usr/bin/python3 "$WRITER" \
          --product-reset-start \
          --product-reset-operation-id "$requested_action_id" \
          --enable-real-write \
          --confirm-service-stopped \
          --confirm-human-approved-product-reset
      } 2>/dev/null)"; then
        reset_start_rc=0
      else
        reset_start_rc=$?
      fi
      : "$reset_start_output"
      if [ "$reset_start_rc" -ne 10 ] || ! product_reset_pending; then
        c17_4_trace "product_reset_start_failed" rc="$reset_start_rc"
        echo "product_reset_start_failed" >&2
        exit 47
      fi
      if ! write_product_reset_resume_request; then
        c17_4_trace "product_reset_resume_request_failed"
        echo "product_reset_resume_request_failed" >&2
        exit 47
      fi
      c17_4_trace "product_reset_started"
      show_transition product_reset_pending || true
      exit 0
      ;;
    *)
      echo "totem_action_request_invalid" >&2
      exit 47
      ;;
  esac
elif [ -e "$ACTION_REQUEST_FILE" ] || [ -L "$ACTION_REQUEST_FILE" ]; then
  echo "totem_action_request_without_exit_code" >&2
  exit 47
fi

SETUP_CANCELLED="false"
if [ "$WIZARD_RC" = "130" ]; then
  SETUP_CANCELLED="true"
  c15_trace "wizard_cancelled_restore_path"
elif [ -e "$WIZARD_OUT_DIR/setup-cancelled.json" ] \
  || [ -L "$WIZARD_OUT_DIR/setup-cancelled.json" ]; then
  echo "wizard_cancel_artifact_without_exit_code" >&2
  exit 47
fi

if [ -f "$WIZARD_OUT_DIR/setup-failed.json" ]; then
  echo "wizard_failed_current_session" >&2
  exit 46
fi
if [ "$SETUP_CANCELLED" != "true" ]; then
  case "$WIZARD_RC" in
    0) ;;
    *)
      echo "wizard_unexpected_exit:$WIZARD_RC" >&2
      exit 46
      ;;
  esac
fi

if [ "$SETUP_CANCELLED" = "true" ]; then
  case "$EXPECTED_RESULT" in
    any|cancelled)
      ;;
    *)
      echo "wizard_cancelled_before_expected_result" >&2
      exit 43
      ;;
  esac
fi

if [ "$EXPECTED_RESULT" = "preview" ] && [ ! -d "$WIZARD_OUT_DIR/screens" ]; then
  echo "preview_not_generated" >&2
  exit 41
fi
if [ "$EXPECTED_RESULT" = "cancelled" ] && [ "$SETUP_CANCELLED" != "true" ]; then
  echo "expected_cancel_not_observed" >&2
  exit 43
fi
if [ "$EXPECTED_RESULT" = "candidate_ready" ] && [ ! -f "$WIZARD_OUT_DIR/config.candidate.json" ]; then
  echo "candidate_not_generated" >&2
  exit 44
fi
if [ -f "$WIZARD_OUT_DIR/config.candidate.json" ]; then
  if ! candidate_is_current_session_ready; then
    echo "candidate_not_attested_by_current_session" >&2
    exit 44
  fi
  SELECTED_ROTATION_DEG="$(selected_rotation_from_candidate)"
fi

if [ "$SETUP_CANCELLED" != "true" ]; then
  select_qr_pairing_private_values_if_available
fi

if [ "$SETUP_CANCELLED" = "true" ]; then
  cleanup_private_artifacts || true
  cleanup_apply_policy || true
fi

if [ "$SETUP_CANCELLED" != "true" ] && { [ "$APPLY_MODE" = "dry-run" ] || [ "$APPLY_MODE" = "real-write" ]; }; then
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

if [ "$SETUP_CANCELLED" != "true" ] && [ "$APPLY_MODE" = "dry-run" ]; then
  python3 "$CONTRACT" \
    --candidate "$HANDOFF_OUT_DIR/config.candidate.private.json" \
    --real-dry-run \
    --out-dir "$OUT_DIR/validate-real" >/dev/null
  cleanup_private_artifacts || true
  cleanup_apply_policy || true
fi

if [ "$SETUP_CANCELLED" != "true" ] && [ "$APPLY_MODE" = "real-write" ]; then
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
    show_transition save_failed "$SELECTED_ROTATION_DEG" || true
    sleep 2
    echo "writer_failed" >&2
    exit 47
  fi
  REAL_CONFIG_WRITTEN="true"
  if ! write_public_orientation_from_candidate; then
    echo "warning: public_orientation_update_deferred" >&2
    c1523_phase "post_write_metadata_warning kind=public_orientation"
  fi
  if write_private_settings_context "$WIZARD_OUT_DIR/config.candidate.json" visual_wizard_saved; then
    PRIVATE_SETTINGS_CONTEXT_UPDATED="true"
  else
    echo "warning: private_settings_context_update_deferred" >&2
    c1523_phase "post_write_metadata_warning kind=private_settings_context"
  fi
  cleanup_private_artifacts || true
  cleanup_apply_policy || true
  if product_reset_onboarding_pending; then
    set +e
    /usr/bin/python3 "$WRITER" \
      --product-reset-complete-onboarding \
      --product-reset-data-root /data \
      --enable-real-write \
      --confirm-service-stopped \
      --confirm-product-reset-new-config-applied >/dev/null 2>&1
    onboarding_complete_rc="$?"
    set -e
    if [ "$onboarding_complete_rc" -ne 0 ] || product_reset_guard_required; then
      c17_4_trace "product_reset_onboarding_complete_failed" rc="$onboarding_complete_rc"
      echo "product_reset_onboarding_complete_failed" >&2
      exit 47
    fi
    c17_4_trace "product_reset_onboarding_complete"
  fi
  show_transition complete "$SELECTED_ROTATION_DEG" || true
  sleep 1
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
