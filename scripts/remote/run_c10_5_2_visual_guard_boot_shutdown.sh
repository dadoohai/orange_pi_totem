#!/usr/bin/env bash
set -euo pipefail

HOST=""
MODE="prepare-only"
REMOTE_TTY="${REMOTE_TTY:-2}"
RUN_TIMEOUT_SEC="${RUN_TIMEOUT_SEC:-900}"
PREVIEW_SEC="${PREVIEW_SEC:-10}"
REMOTE_DIR="${REMOTE_DIR:-/tmp/dadooh-c10-5-2}"
REMOTE_OUT_DIR="${REMOTE_OUT_DIR:-/tmp/dadooh-c10-5-2-visual-guard-boot-shutdown}"
REMOTE_WIZARD_OUT_DIR="${REMOTE_WIZARD_OUT_DIR:-/tmp/dadooh-c10-5-2-visual-wizard}"
PROFILE_NAME="${PROFILE_NAME:-dadooh-c9-8-wifi-persistent}"
PAUSE_CONFIRM_PHRASE="${PAUSE_CONFIRM_PHRASE:-CONFIRMO C10.5.2 VISUAL GUARD COM PAUSA DO PLAYER}"
BOOT_APPLY_CONFIRM_PHRASE="${BOOT_APPLY_CONFIRM_PHRASE:-CONFIRMO GUARDRAILS VISUAIS BOOT C10.5.2}"
BOOT_ROLLBACK_CONFIRM_PHRASE="${BOOT_ROLLBACK_CONFIRM_PHRASE:-CONFIRMO ROLLBACK GUARDRAILS VISUAIS BOOT C10.5.2}"
REBOOT_CONFIRM_PHRASE="${REBOOT_CONFIRM_PHRASE:-CONFIRMO REBOOT VISUAL C10.5.2}"

usage() {
  cat <<'USAGE'
Usage:
  run_c10_5_2_visual_guard_boot_shutdown.sh <host> [mode] [--tty N] [--preview-sec N]

Modes:
  --prepare-only
      Copy scripts to /tmp and run self-tests. Does not touch service/config/Wi-Fi.

  --inspect
      Read-only sanitized inspection of getty/console/splash/orientation state.

  --preview-transition-splash
      Requires confirmation. Pauses player/getty, renders transition splash, restores player/getty.

  --apply-visual-guardrails
      Requires confirmation. Applies reversible boot/getty/splash guardrails.

  --rollback-visual-guardrails
      Requires confirmation. Rolls back boot/getty/splash guardrails.

  --reboot-visual-check
      Requires confirmation. Reboots once and collects sanitized final state.

  --transition-stress-short
      Requires confirmation. Runs a short player->splash->wizard preview->splash->player cycle.
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
    --preview-transition-splash)
      MODE="preview-transition-splash"
      ;;
    --apply-visual-guardrails)
      MODE="apply-visual-guardrails"
      ;;
    --rollback-visual-guardrails)
      MODE="rollback-visual-guardrails"
      ;;
    --reboot-visual-check)
      MODE="reboot-visual-check"
      ;;
    --transition-stress-short)
      MODE="transition-stress-short"
      ;;
    --tty)
      shift
      REMOTE_TTY="${1:-}"
      ;;
    --preview-sec)
      shift
      PREVIEW_SEC="${1:-}"
      ;;
    --timeout-sec)
      shift
      RUN_TIMEOUT_SEC="${1:-}"
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
  prepare-only|inspect|preview-transition-splash|apply-visual-guardrails|rollback-visual-guardrails|reboot-visual-check|transition-stress-short)
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

case "$REMOTE_TTY" in
  ''|*[!0-9]*|0)
    echo "error: --tty must be a positive integer" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BOARD_DIR="$REPO_ROOT/scripts/board"
BASE_RUNNER="$SCRIPT_DIR/run_c10_5_visual_boot_rotation.sh"

LOCAL_VISUAL_WIZARD="$BOARD_DIR/totem_setup_visual_wizard.py"
LOCAL_WIZARD="$BOARD_DIR/totem_setup_local_wizard.py"
LOCAL_SERVER="$BOARD_DIR/totem_setup_minimal_server.py"
LOCAL_CONTRACT="$BOARD_DIR/totem_config_contract_validate.py"
LOCAL_WIFI_ADAPTER="$BOARD_DIR/totem_wifi_nm_adapter.py"
LOCAL_STATUS_AGGREGATE="$BOARD_DIR/totem_status_aggregate.py"
LOCAL_STATUS_RENDER="$BOARD_DIR/totem_status_render_preview.py"
LOCAL_VISUAL_SPLASH="$BOARD_DIR/totem_visual_splash.py"

for path in "$LOCAL_VISUAL_WIZARD" "$LOCAL_WIZARD" "$LOCAL_SERVER" "$LOCAL_CONTRACT" "$LOCAL_WIFI_ADAPTER" "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_VISUAL_SPLASH" "$BASE_RUNNER"; do
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
  echo "Preparing C10.5.2 visual guard workspace on $HOST"
  ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' '$REMOTE_OUT_DIR' '$REMOTE_WIZARD_OUT_DIR' && chmod 700 '$REMOTE_DIR' '$REMOTE_OUT_DIR' '$REMOTE_WIZARD_OUT_DIR'"
  scp "$LOCAL_VISUAL_WIZARD" "$LOCAL_WIZARD" "$LOCAL_SERVER" "$LOCAL_CONTRACT" "$LOCAL_WIFI_ADAPTER" "$LOCAL_STATUS_AGGREGATE" "$LOCAL_STATUS_RENDER" "$LOCAL_VISUAL_SPLASH" "$HOST:$REMOTE_DIR/"

  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail
VISUAL="$REMOTE_DIR/totem_setup_visual_wizard.py"
CONTRACT="$REMOTE_DIR/totem_config_contract_validate.py"
WIFI_ADAPTER="$REMOTE_DIR/totem_wifi_nm_adapter.py"
SPLASH="$REMOTE_DIR/totem_visual_splash.py"
OUT="$REMOTE_OUT_DIR/prepare"
PUBLIC_ORIENTATION="$OUT/public-orientation/orientation.json"

umask 077
rm -rf "$OUT"
mkdir -p "$OUT"
chmod 700 "$OUT"

python3 "$CONTRACT" --self-test
python3 "$WIFI_ADAPTER" --self-test --out-dir "$OUT/wifi-self-test"
python3 "$VISUAL" --self-test
python3 "$SPLASH" --self-test
python3 "$VISUAL" \
  --scripted \
  --environment-id ENV-C10-5-2-VISUAL-GUARD \
  --rotation-key portrait_right \
  --network-step configured_wifi \
  --write-public-orientation \
  --public-orientation-path "$PUBLIC_ORIENTATION" \
  --out-dir "$OUT/scripted" >/dev/null
python3 - "$OUT/scripted/setup-status.json" "$PUBLIC_ORIENTATION" <<'PY'
import json
import pathlib
import stat
import sys
status = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
orientation = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
assert status["orientation"]["public_orientation_contract_written"] is True
assert status["guardrails"]["allowlisted_data_state_written"] is True
assert orientation["rotation_deg"] == 90
assert set(orientation) == {"schema_version", "updated_at", "rotation_deg", "orientation_label"}
assert stat.S_IMODE(pathlib.Path(sys.argv[2]).stat().st_mode) == 0o644
PY
python3 "$SPLASH" preparing --status-out "$OUT/splash-status.json" >/dev/null 2>&1 || true
python3 - "$OUT/splash-status.json" <<'PY'
import json
import pathlib
import sys
data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["public_orientation_path_supported"] is True
assert data["real_config_read"] is False
assert data["real_config_written"] is False
assert data["writer_called"] is False
assert data["wifi_changed"] is False
PY
echo "remote C10.5.2 prepare checks: ok"
REMOTE_PREP
}

base_runner() {
  env \
    REMOTE_DIR="$REMOTE_DIR" \
    REMOTE_OUT_DIR="$REMOTE_OUT_DIR" \
    REMOTE_WIZARD_OUT_DIR="$REMOTE_WIZARD_OUT_DIR" \
    REMOTE_TTY="$REMOTE_TTY" \
    RUN_TIMEOUT_SEC="$RUN_TIMEOUT_SEC" \
    PREVIEW_SEC="$PREVIEW_SEC" \
    PROFILE_NAME="$PROFILE_NAME" \
    PAUSE_CONFIRM_PHRASE="$PAUSE_CONFIRM_PHRASE" \
    BOOT_APPLY_CONFIRM_PHRASE="$BOOT_APPLY_CONFIRM_PHRASE" \
    BOOT_ROLLBACK_CONFIRM_PHRASE="$BOOT_ROLLBACK_CONFIRM_PHRASE" \
    REBOOT_CONFIRM_PHRASE="$REBOOT_CONFIRM_PHRASE" \
    WRITE_PUBLIC_ORIENTATION=1 \
    PUBLIC_ORIENTATION_PATH="/data/state/totem-display/orientation.json" \
    "$BASE_RUNNER" "$HOST" "$@"
}

run_inspect() {
  ssh "$HOST" "REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_TTY='$REMOTE_TTY' bash -s" <<'REMOTE_INSPECT'
set -euo pipefail
OUT="$REMOTE_OUT_DIR/inspect"
STATUS="$OUT/status.json"
mkdir -p "$OUT"
chmod 700 "$OUT"
python3 - "$STATUS" "$REMOTE_TTY" <<'PY'
import json
import os
import pathlib
import subprocess
import sys

target = pathlib.Path(sys.argv[1])
remote_tty = sys.argv[2]

def cmd(args):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False).stdout.strip()

def unit_state(unit):
    return {
        "active": cmd(["systemctl", "is-active", unit]) or "unknown",
        "enabled": cmd(["systemctl", "is-enabled", unit]) or "unknown",
    }

def public_state():
    try:
        data = json.loads(pathlib.Path("/tmp/dadooh-status/status.json").read_text(encoding="utf-8"))
        return data.get("public_state") or data.get("state") or "unknown"
    except Exception:
        return "unknown"

cmdline = pathlib.Path("/proc/cmdline").read_text(encoding="utf-8", errors="ignore").split()
orientation_path = pathlib.Path("/data/state/totem-display/orientation.json")
orientation = {"present": False, "rotation_deg": "unknown", "orientation_label": "unknown"}
if orientation_path.exists() and not orientation_path.is_symlink():
    try:
        data = json.loads(orientation_path.read_text(encoding="utf-8"))
        orientation = {
            "present": True,
            "rotation_deg": data.get("rotation_deg", "unknown"),
            "orientation_label": data.get("orientation_label", "unknown"),
        }
    except Exception:
        orientation = {"present": True, "rotation_deg": "unknown", "orientation_label": "unknown"}
failed = [line for line in cmd(["systemctl", "--failed", "--no-legend"]).splitlines() if line.strip()]
gettys = {unit: unit_state(unit) for unit in ("getty@tty1.service", f"getty@tty{remote_tty}.service")}
payload = {
    "schema_version": "dadooh-c10.5.2-visual-guard-inspect.v1",
    "mode": "inspect",
    "display_owner_contract": {
        "allowed": ["boot_splash", "transition_splash", "wizard", "player", "shutdown_splash"],
        "operator_forbidden": ["getty_login", "shell", "armbian_console", "visible_systemd_kernel_messages", "technical_text"],
    },
    "getty_units": gettys,
    "getty_visible_before": any(item["active"] == "active" or item["enabled"] == "enabled" for item in gettys.values()),
    "console_quiet_flags_present": {
        "quiet": "quiet" in cmdline,
        "loglevel_3_or_lower": any(token.startswith("loglevel=") and token.split("=", 1)[1] in {"0", "1", "2", "3"} for token in cmdline),
        "systemd_show_status_false": "systemd.show_status=false" in cmdline,
        "cursor_hidden": "vt.global_cursor_default=0" in cmdline,
    },
    "splash_service": unit_state("dadooh-visual-splash.service"),
    "orientation_public": orientation,
    "service_active": cmd(["systemctl", "is-active", "kiosky-player.service"]) or "unknown",
    "service_enabled": cmd(["systemctl", "is-enabled", "kiosky-player.service"]) or "unknown",
    "nrestarts": cmd(["systemctl", "show", "kiosky-player.service", "-p", "NRestarts", "--value"]) or "unknown",
    "public_state": public_state(),
    "systemctl_failed_count": len(failed),
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "wifi_changed": False,
    "raw_logs_written": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
REMOTE_INSPECT
}

run_transition_preview() {
  confirm_exact "$PAUSE_CONFIRM_PHRASE" "HDMI/tela e teclado local devem estar conectados. O player sera pausado temporariamente."
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_TTY='$REMOTE_TTY' PREVIEW_SEC='$PREVIEW_SEC' bash -s" <<'REMOTE_PREVIEW'
set -euo pipefail
SPLASH="$REMOTE_DIR/totem_visual_splash.py"
OUT="$REMOTE_OUT_DIR/transition-splash-preview"
STATUS="$OUT/status.json"
TTY_DEVICE="/dev/tty$REMOTE_TTY"
GETTY_UNITS=("getty@tty1.service" "getty@tty${REMOTE_TTY}.service")
INITIAL_SERVICE_ACTIVE="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
INITIAL_SERVICE_ENABLED="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"
mkdir -p "$OUT"
chmod 700 "$OUT"
declare -A GETTY_ACTIVE
declare -A GETTY_ENABLED
for unit in "${GETTY_UNITS[@]}"; do
  GETTY_ACTIVE["$unit"]="$(systemctl is-active "$unit" 2>/dev/null || true)"
  GETTY_ENABLED["$unit"]="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
done
restore() {
  for unit in "${GETTY_UNITS[@]}"; do
    if [ "${GETTY_ENABLED[$unit]}" = "enabled" ]; then systemctl enable "$unit" >/dev/null 2>&1 || true; else systemctl disable "$unit" >/dev/null 2>&1 || true; fi
    if [ "${GETTY_ACTIVE[$unit]}" = "active" ]; then systemctl start "$unit" >/dev/null 2>&1 || true; else systemctl stop "$unit" >/dev/null 2>&1 || true; fi
  done
  if [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then systemctl enable kiosky-player.service >/dev/null 2>&1 || true; fi
  if [ "$INITIAL_SERVICE_ACTIVE" = "active" ] || [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then systemctl start kiosky-player.service >/dev/null 2>&1 || true; fi
}
trap restore EXIT INT TERM HUP
for unit in "${GETTY_UNITS[@]}"; do systemctl stop "$unit" >/dev/null 2>&1 || true; done
command -v chvt >/dev/null 2>&1 && chvt "$REMOTE_TTY" >/dev/null 2>&1 || true
printf '\033c\033[2J\033[3J\033[H\033[?25l' > "$TTY_DEVICE" 2>/dev/null || true
systemctl stop kiosky-player.service >/dev/null 2>&1 || true
for mode in setup saving player preparing shutdown; do
  env TERM=linux python3 "$SPLASH" "$mode" --status-out "$OUT/splash-$mode-status.json" <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
  sleep 1
done
sleep "$PREVIEW_SEC"
python3 - "$STATUS" "$OUT" <<'PY'
import json
import os
import pathlib
import sys
target = pathlib.Path(sys.argv[1])
run_out = pathlib.Path(sys.argv[2])
items = []
for path in sorted(run_out.glob("splash-*-status.json")):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    items.append({
        "mode": data.get("mode", "unknown"),
        "rendered": data.get("rendered", "unknown"),
        "rotation_deg": data.get("rotation_deg", "unknown"),
        "layout_mode": data.get("layout_mode", "unknown"),
        "orientation_source": data.get("orientation_source", "unknown"),
    })
payload = {
    "schema_version": "dadooh-c10.5.2-transition-splash-preview.v1",
    "mode": "preview-transition-splash",
    "items": items,
    "transition_flicker_after": "human_observation_required",
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "wifi_changed": False,
    "raw_logs_written": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
REMOTE_PREVIEW
}

run_transition_stress_short() {
  confirm_exact "$PAUSE_CONFIRM_PHRASE" "Stress curto de transicao: player sera pausado e restaurado automaticamente."
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' REMOTE_WIZARD_OUT_DIR='$REMOTE_WIZARD_OUT_DIR' REMOTE_TTY='$REMOTE_TTY' PREVIEW_SEC='$PREVIEW_SEC' bash -s" <<'REMOTE_STRESS'
set -euo pipefail
VISUAL="$REMOTE_DIR/totem_setup_visual_wizard.py"
SPLASH="$REMOTE_DIR/totem_visual_splash.py"
OUT="$REMOTE_OUT_DIR/transition-stress-short"
WIZARD_OUT="$REMOTE_WIZARD_OUT_DIR-stress"
STATUS="$OUT/status.json"
TTY_DEVICE="/dev/tty$REMOTE_TTY"
GETTY_UNITS=("getty@tty1.service" "getty@tty${REMOTE_TTY}.service")
INITIAL_SERVICE_ACTIVE="$(systemctl is-active kiosky-player.service 2>/dev/null || true)"
INITIAL_SERVICE_ENABLED="$(systemctl is-enabled kiosky-player.service 2>/dev/null || true)"
mkdir -p "$OUT"
rm -rf "$WIZARD_OUT"
mkdir -p "$WIZARD_OUT"
chmod 700 "$OUT" "$WIZARD_OUT"
declare -A GETTY_ACTIVE
declare -A GETTY_ENABLED
for unit in "${GETTY_UNITS[@]}"; do
  GETTY_ACTIVE["$unit"]="$(systemctl is-active "$unit" 2>/dev/null || true)"
  GETTY_ENABLED["$unit"]="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
done
restore() {
  env TERM=linux python3 "$SPLASH" player --status-out "$OUT/splash-restore-player-status.json" <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
  if [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then systemctl enable kiosky-player.service >/dev/null 2>&1 || true; fi
  if [ "$INITIAL_SERVICE_ACTIVE" = "active" ] || [ "$INITIAL_SERVICE_ENABLED" = "enabled" ]; then systemctl start kiosky-player.service >/dev/null 2>&1 || true; fi
  for unit in "${GETTY_UNITS[@]}"; do
    if [ "${GETTY_ENABLED[$unit]}" = "enabled" ]; then systemctl enable "$unit" >/dev/null 2>&1 || true; else systemctl disable "$unit" >/dev/null 2>&1 || true; fi
    if [ "${GETTY_ACTIVE[$unit]}" = "active" ]; then systemctl start "$unit" >/dev/null 2>&1 || true; else systemctl stop "$unit" >/dev/null 2>&1 || true; fi
  done
}
trap restore EXIT INT TERM HUP
for unit in "${GETTY_UNITS[@]}"; do systemctl stop "$unit" >/dev/null 2>&1 || true; done
command -v chvt >/dev/null 2>&1 && chvt "$REMOTE_TTY" >/dev/null 2>&1 || true
printf '\033c\033[2J\033[3J\033[H\033[?25l' > "$TTY_DEVICE" 2>/dev/null || true

env TERM=linux python3 "$SPLASH" setup --status-out "$OUT/splash-setup-before-stop-status.json" <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
systemctl stop kiosky-player.service >/dev/null 2>&1 || true
env TERM=linux python3 "$SPLASH" setup --status-out "$OUT/splash-setup-after-stop-status.json" <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
env TERM=linux PYTHONPATH="$REMOTE_DIR" python3 "$VISUAL" --out-dir "$WIZARD_OUT" --preview-screens --show-preview --auto-exit-sec "$PREVIEW_SEC" <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
env TERM=linux python3 "$SPLASH" saving --status-out "$OUT/splash-saving-status.json" <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
env TERM=linux python3 "$SPLASH" player --status-out "$OUT/splash-player-status.json" <"$TTY_DEVICE" >"$TTY_DEVICE" 2>/dev/null || true
systemctl start kiosky-player.service >/dev/null 2>&1 || true
sleep 8
python3 - "$STATUS" "$OUT" "$WIZARD_OUT" <<'PY'
import json
import os
import pathlib
import subprocess
import sys
target = pathlib.Path(sys.argv[1])
run_out = pathlib.Path(sys.argv[2])
wizard_out = pathlib.Path(sys.argv[3])
def cmd(args):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False).stdout.strip()
def counts():
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
        if "totem_setup_visual_wizard.py" in names:
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
        playback_data = json.loads(pathlib.Path("/tmp/kiosky-status.json").read_text(encoding="utf-8"))
        playback = playback_data.get("playback_state") or playback_data.get("playback", {}).get("state") or "unknown"
    except Exception:
        playback = "unknown"
    return state, playback
state, playback = public_status()
failed = [line for line in cmd(["systemctl", "--failed", "--no-legend"]).splitlines() if line.strip()]
items = []
for path in sorted(run_out.glob("splash-*-status.json")):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    items.append({"mode": data.get("mode", "unknown"), "rendered": data.get("rendered", "unknown"), "rotation_deg": data.get("rotation_deg", "unknown")})
payload = {
    "schema_version": "dadooh-c10.5.2-transition-stress-short.v1",
    "mode": "transition-stress-short",
    "splash_items": items,
    "wizard_preview_generated": (wizard_out / "screens").is_dir(),
    "transition_flicker_after": "human_observation_required",
    "service_active": cmd(["systemctl", "is-active", "kiosky-player.service"]) or "unknown",
    "service_enabled": cmd(["systemctl", "is-enabled", "kiosky-player.service"]) or "unknown",
    "nrestarts": cmd(["systemctl", "show", "kiosky-player.service", "-p", "NRestarts", "--value"]) or "unknown",
    "public_state": state,
    "playback": playback,
    "process_counts": counts(),
    "systemctl_failed_count": len(failed),
    "real_config_read": False,
    "real_config_written": False,
    "writer_called": False,
    "wifi_changed": False,
    "raw_logs_written": False,
}
tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
os.chmod(target, 0o600)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
REMOTE_STRESS
}

prepare_remote

case "$MODE" in
  prepare-only)
    echo "C10.5.2 prepare-only complete. Evidence dir reserved: $REMOTE_OUT_DIR"
    ;;
  inspect)
    run_inspect
    ;;
  preview-transition-splash)
    run_transition_preview
    ;;
  apply-visual-guardrails)
    base_runner --apply-boot-visual-guardrails
    ;;
  rollback-visual-guardrails)
    base_runner --rollback-boot-visual-guardrails
    ;;
  reboot-visual-check)
    base_runner --reboot-visual-check
    ;;
  transition-stress-short)
    run_transition_stress_short
    ;;
esac

echo "C10.5.2 visual guard mode complete: $MODE"
