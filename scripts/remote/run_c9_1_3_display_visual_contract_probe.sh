#!/usr/bin/env bash
set -euo pipefail

HOST="root@192.168.18.115"
MODE="prepare-only"
DISPLAY_SECONDS="90"

REQUIRED_AUTH="Autorizo C9.1.3: exibir padrão visual temporário na HDMI para diagnóstico de proporção/orientação, com restauração do player ao final."

usage() {
  cat <<'USAGE'
Usage:
  run_c9_1_3_display_visual_contract_probe.sh [host] [--prepare-only|--display] [--display-seconds N]

Modes:
  --prepare-only
      Copy the probe to /tmp, run self-test, generate the visual pattern, and
      collect a read-only snapshot. Does not stop service, start MPV, or occupy
      HDMI.

  --display
      After the required exact human authorization text, stop the player only
      if needed, show the SVG pattern temporarily through MPV/DRM, restore the
      player, collect final metadata, and ask normalized human validation
      questions.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only)
      MODE="prepare-only"
      ;;
    --display)
      MODE="display"
      ;;
    --display-seconds)
      shift
      if [ "$#" -eq 0 ]; then
        echo "error: --display-seconds requires a value" >&2
        exit 2
      fi
      DISPLAY_SECONDS="$1"
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

case "$DISPLAY_SECONDS" in
  ''|*[!0-9]*)
    echo "error: --display-seconds must be a positive integer" >&2
    exit 2
    ;;
esac
if [ "$DISPLAY_SECONDS" -lt 10 ] || [ "$DISPLAY_SECONDS" -gt 600 ]; then
  echo "error: --display-seconds must be between 10 and 600" >&2
  exit 2
fi

REMOTE_DIR="/tmp/dadooh-c9-1-3"
REMOTE_OUT_DIR="/tmp/dadooh-c9-1-3-display-contract"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCAL_PROBE="$REPO_ROOT/scripts/board/totem_display_visual_contract_probe.py"

if [ ! -f "$LOCAL_PROBE" ]; then
  echo "error: missing $LOCAL_PROBE" >&2
  exit 1
fi

echo "Preparing $REMOTE_DIR on $HOST"
ssh "$HOST" "umask 077 && mkdir -p '$REMOTE_DIR' && chmod 700 '$REMOTE_DIR'"

echo "Copying C9.1.3 display visual contract probe to $HOST:$REMOTE_DIR"
scp "$LOCAL_PROBE" "$HOST:$REMOTE_DIR/"

echo "Running C9.1.3 prepare/read-only phase on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_PREP'
set -euo pipefail

PROBE="$REMOTE_DIR/totem_display_visual_contract_probe.py"

service_active() {
  systemctl is-active kiosky-player.service 2>/dev/null || true
}

service_enabled() {
  systemctl is-enabled kiosky-player.service 2>/dev/null || true
}

nrestarts() {
  systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null || true
}

strict_counts() {
  python3 - <<'PY'
import os
import pathlib

self_pid = os.getpid()
player = 0
mpv = 0
renderer = 0
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        raw = (proc / "cmdline").read_bytes()
        parts = [part.decode("utf-8", "ignore") for part in raw.split(b"\x00") if part]
        cmdline = " ".join(parts)
        comm = (proc / "comm").read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        continue
    first = parts[0] if parts else ""
    if comm == "mpv" or first.endswith("/mpv"):
        mpv += 1
    if comm in {"python3", "python"} and ("/kiosk.py" in cmdline or cmdline.strip().endswith("kiosk.py")):
        player += 1
    if comm in {"python3", "python"} and ("status_splash" in cmdline or "renderer" in cmdline):
        renderer += 1
print(f"{player} {mpv} {renderer}")
PY
}

umask 077
rm -rf "$REMOTE_OUT_DIR"
mkdir -p "$REMOTE_DIR" "$REMOTE_OUT_DIR"
chmod 700 "$REMOTE_DIR" "$REMOTE_OUT_DIR"

python3 "$PROBE" --self-test
python3 "$PROBE" --out-dir "$REMOTE_OUT_DIR" --generate-pattern --phase prepare-read-only
set -- $(strict_counts)
python3 "$PROBE" \
  --out-dir "$REMOTE_OUT_DIR" \
  --record-operation \
  --operation-result prepared \
  --abort-reason prepare_only_no_display \
  --display-seconds 0 \
  --service-was-active false \
  --temporary-player-stop-authorized false \
  --temporary-player-stop-performed false \
  --temporary-mpv-started false \
  --temporary-mpv-terminated false \
  --restore-attempted false \
  --restore-ok false \
  --service-active-after "$(service_active)" \
  --service-enabled-after "$(service_enabled)" \
  --service-nrestarts-after "$(nrestarts)" \
  --player-count-after "${1:-0}" \
  --mpv-count-after "${2:-0}" \
  --renderer-count-after "${3:-0}"

echo "remote C9.1.3 prepare/read-only: ok"
REMOTE_PREP

if [ "$MODE" = "prepare-only" ]; then
  echo "C9.1.3 prepare-only complete. Evidence: $REMOTE_OUT_DIR"
  exit 0
fi

echo
echo "Before occupying HDMI or stopping the player, type exactly:"
echo "$REQUIRED_AUTH"
printf '> '
IFS= read -r AUTH_TEXT

if [ "$AUTH_TEXT" != "$REQUIRED_AUTH" ]; then
  echo "Authorization text did not match. Recording blocked state and leaving HDMI/player untouched." >&2
  ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' bash -s" <<'REMOTE_BLOCK'
set -euo pipefail

PROBE="$REMOTE_DIR/totem_display_visual_contract_probe.py"

service_active() {
  systemctl is-active kiosky-player.service 2>/dev/null || true
}
service_enabled() {
  systemctl is-enabled kiosky-player.service 2>/dev/null || true
}
nrestarts() {
  systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null || true
}
strict_counts() {
  python3 - <<'PY'
import os
import pathlib
self_pid = os.getpid()
player = 0
mpv = 0
renderer = 0
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        raw = (proc / "cmdline").read_bytes()
        parts = [part.decode("utf-8", "ignore") for part in raw.split(b"\x00") if part]
        cmdline = " ".join(parts)
        comm = (proc / "comm").read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        continue
    first = parts[0] if parts else ""
    if comm == "mpv" or first.endswith("/mpv"):
        mpv += 1
    if comm in {"python3", "python"} and ("/kiosk.py" in cmdline or cmdline.strip().endswith("kiosk.py")):
        player += 1
    if comm in {"python3", "python"} and ("status_splash" in cmdline or "renderer" in cmdline):
        renderer += 1
print(f"{player} {mpv} {renderer}")
PY
}
set -- $(strict_counts)
python3 "$PROBE" \
  --out-dir "$REMOTE_OUT_DIR" \
  --phase blocked-no-authorization \
  --record-operation \
  --operation-result blocked \
  --abort-reason authorization_text_not_confirmed \
  --display-seconds 0 \
  --service-was-active false \
  --temporary-player-stop-authorized false \
  --temporary-player-stop-performed false \
  --temporary-mpv-started false \
  --temporary-mpv-terminated false \
  --restore-attempted false \
  --restore-ok false \
  --service-active-after "$(service_active)" \
  --service-enabled-after "$(service_enabled)" \
  --service-nrestarts-after "$(nrestarts)" \
  --player-count-after "${1:-0}" \
  --mpv-count-after "${2:-0}" \
  --renderer-count-after "${3:-0}"
REMOTE_BLOCK
  exit 20
fi

echo "Running authorized C9.1.3 HDMI display phase on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' DISPLAY_SECONDS='$DISPLAY_SECONDS' bash -s" <<'REMOTE_DISPLAY'
set -euo pipefail

PROBE="$REMOTE_DIR/totem_display_visual_contract_probe.py"
PATTERN="$REMOTE_OUT_DIR/display-visual-contract.svg"
MPV_SOCKET="$REMOTE_OUT_DIR/probe-mpv.sock"
MPV_PID=""
SERVICE_WAS_ACTIVE="false"
STOP_PERFORMED="false"
TEMP_MPV_STARTED="false"
TEMP_MPV_TERMINATED="false"
RESTORE_ATTEMPTED="false"
RESTORE_OK="false"
RESULT="not_run"
ABORT_REASON=""

service_active() {
  systemctl is-active kiosky-player.service 2>/dev/null || true
}

service_enabled() {
  systemctl is-enabled kiosky-player.service 2>/dev/null || true
}

nrestarts() {
  systemctl show kiosky-player.service -p NRestarts --value 2>/dev/null || true
}

strict_counts() {
  python3 - <<'PY'
import os
import pathlib

self_pid = os.getpid()
player = 0
mpv = 0
renderer = 0
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) == self_pid:
        continue
    try:
        raw = (proc / "cmdline").read_bytes()
        parts = [part.decode("utf-8", "ignore") for part in raw.split(b"\x00") if part]
        cmdline = " ".join(parts)
        comm = (proc / "comm").read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        continue
    first = parts[0] if parts else ""
    if comm == "mpv" or first.endswith("/mpv"):
        mpv += 1
    if comm in {"python3", "python"} and ("/kiosk.py" in cmdline or cmdline.strip().endswith("kiosk.py")):
        player += 1
    if comm in {"python3", "python"} and ("status_splash" in cmdline or "renderer" in cmdline):
        renderer += 1
print(f"{player} {mpv} {renderer}")
PY
}

stop_temp_mpv() {
  if [ -n "$MPV_PID" ] && kill -0 "$MPV_PID" >/dev/null 2>&1; then
    kill -TERM "$MPV_PID" >/dev/null 2>&1 || true
    wait "$MPV_PID" 2>/dev/null || true
  fi
  if [ "$TEMP_MPV_STARTED" = "true" ]; then
    TEMP_MPV_TERMINATED="true"
  fi
  MPV_PID=""
  rm -f "$MPV_SOCKET"
}

restore_service_if_needed() {
  if [ "$STOP_PERFORMED" = "true" ] && [ "$SERVICE_WAS_ACTIVE" = "true" ]; then
    RESTORE_ATTEMPTED="true"
    if [ "$(service_active)" != "active" ]; then
      systemctl start kiosky-player.service || true
    fi
    for _ in $(seq 1 60); do
      if [ "$(service_active)" = "active" ]; then
        set -- $(strict_counts)
        if [ "${1:-0}" -ge 1 ] && [ "${2:-0}" -ge 1 ]; then
          RESTORE_OK="true"
          return 0
        fi
      fi
      sleep 1
    done
    return 1
  fi
  RESTORE_OK="true"
  return 0
}

record_operation() {
  set -- $(strict_counts)
  python3 "$PROBE" \
    --out-dir "$REMOTE_OUT_DIR" \
    --record-operation \
    --operation-result "$RESULT" \
    --abort-reason "$ABORT_REASON" \
    --display-seconds "$DISPLAY_SECONDS" \
    --service-was-active "$SERVICE_WAS_ACTIVE" \
    --temporary-player-stop-authorized true \
    --temporary-player-stop-performed "$STOP_PERFORMED" \
    --temporary-mpv-started "$TEMP_MPV_STARTED" \
    --temporary-mpv-terminated "$TEMP_MPV_TERMINATED" \
    --restore-attempted "$RESTORE_ATTEMPTED" \
    --restore-ok "$RESTORE_OK" \
    --service-active-after "$(service_active)" \
    --service-enabled-after "$(service_enabled)" \
    --service-nrestarts-after "$(nrestarts)" \
    --player-count-after "${1:-0}" \
    --mpv-count-after "${2:-0}" \
    --renderer-count-after "${3:-0}"
}

on_exit() {
  rc="$?"
  stop_temp_mpv || true
  restore_service_if_needed || true
  python3 "$PROBE" --out-dir "$REMOTE_OUT_DIR" --phase final-read-only || true
  if [ "$RESULT" = "not_run" ]; then
    if [ "$rc" -eq 0 ]; then
      RESULT="passed"
    else
      RESULT="failed"
      ABORT_REASON="unexpected_exit_${rc}"
    fi
  fi
  record_operation || true
  exit "$rc"
}
trap on_exit EXIT TERM INT

umask 077
mkdir -p "$REMOTE_OUT_DIR"
chmod 700 "$REMOTE_OUT_DIR"

if [ ! -f "$PATTERN" ]; then
  python3 "$PROBE" --out-dir "$REMOTE_OUT_DIR" --generate-pattern
fi
if ! command -v mpv >/dev/null 2>&1; then
  RESULT="blocked"
  ABORT_REASON="mpv_unavailable"
  exit 20
fi

python3 "$PROBE" --out-dir "$REMOTE_OUT_DIR" --phase before-display

set -- $(strict_counts)
if [ "$(service_active)" = "active" ]; then
  SERVICE_WAS_ACTIVE="true"
  systemctl stop kiosky-player.service
  STOP_PERFORMED="true"
  for _ in $(seq 1 30); do
    if [ "$(service_active)" != "active" ]; then
      break
    fi
    sleep 1
  done
  if [ "$(service_active)" = "active" ]; then
    RESULT="failed"
    ABORT_REASON="service_did_not_stop"
    exit 1
  fi
elif [ "${1:-0}" -gt 0 ] || [ "${2:-0}" -gt 0 ]; then
  RESULT="blocked"
  ABORT_REASON="player_or_mpv_active_without_service"
  exit 20
fi

python3 "$PROBE" --out-dir "$REMOTE_OUT_DIR" --phase after-player-stop

rm -f "$MPV_SOCKET"
mpv \
  --no-config \
  --fs \
  --force-window=yes \
  --loop-file=inf \
  --image-display-duration=inf \
  --keep-open=yes \
  --no-terminal \
  --no-osc \
  --osd-level=0 \
  --input-terminal=no \
  --input-default-bindings=no \
  --input-vo-keyboard=no \
  --cursor-autohide=always \
  --vo=gpu \
  --gpu-context=drm \
  --ao=null \
  --input-ipc-server="$MPV_SOCKET" \
  -- "$PATTERN" >/dev/null 2>&1 &
MPV_PID="$!"
TEMP_MPV_STARTED="true"

for _ in $(seq 1 20); do
  if [ -S "$MPV_SOCKET" ] && kill -0 "$MPV_PID" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done
if ! kill -0 "$MPV_PID" >/dev/null 2>&1; then
  RESULT="failed"
  ABORT_REASON="temporary_mpv_exited_early"
  exit 1
fi

python3 "$PROBE" --out-dir "$REMOTE_OUT_DIR" --phase display-active --ipc-socket "$MPV_SOCKET"

echo "C9.1.3: visual pattern is on HDMI for ${DISPLAY_SECONDS}s."
sleep "$DISPLAY_SECONDS"

stop_temp_mpv
python3 "$PROBE" --out-dir "$REMOTE_OUT_DIR" --phase after-display-stop

restore_service_if_needed
python3 "$PROBE" --out-dir "$REMOTE_OUT_DIR" --phase after-restore

RESULT="passed"
ABORT_REASON=""
echo "remote C9.1.3 display phase: ok"
REMOTE_DISPLAY

normalize_yes_no_unclear() {
  case "${1,,}" in
    yes|sim|s)
      printf 'yes'
      ;;
    no|nao|não|n)
      printf 'no'
      ;;
    unclear|incerto|naosei|nao_sei|não_sei|duvida)
      printf 'unclear'
      ;;
    *)
      return 1
      ;;
  esac
}

ask_choice() {
  local __var="$1"
  local prompt="$2"
  local kind="$3"
  local raw normalized
  while true; do
    printf '%s ' "$prompt"
    IFS= read -r raw
    case "$kind" in
      circle)
        case "${raw,,}" in
          circle|circulo|círculo) normalized="circle" ;;
          oval) normalized="oval" ;;
          unclear|incerto|naosei|nao_sei|não_sei|duvida) normalized="unclear" ;;
          *) echo "Use: circle, oval ou unclear." >&2; continue ;;
        esac
        ;;
      square)
        case "${raw,,}" in
          square|quadrado) normalized="square" ;;
          rectangle|retangulo|retângulo) normalized="rectangle" ;;
          unclear|incerto|naosei|nao_sei|não_sei|duvida) normalized="unclear" ;;
          *) echo "Use: square, rectangle ou unclear." >&2; continue ;;
        esac
        ;;
      yesno)
        if ! normalized="$(normalize_yes_no_unclear "$raw")"; then
          echo "Use: yes, no ou unclear." >&2
          continue
        fi
        ;;
      stretch)
        case "${raw,,}" in
          none|normal|nenhum|nao|não) normalized="none" ;;
          horizontal) normalized="horizontal" ;;
          vertical) normalized="vertical" ;;
          unclear|incerto|naosei|nao_sei|não_sei|duvida) normalized="unclear" ;;
          *) echo "Use: none, horizontal, vertical ou unclear." >&2; continue ;;
        esac
        ;;
      restored)
        case "${raw,,}" in
          same|igual) normalized="same" ;;
          changed|mudou|diferente) normalized="changed" ;;
          not_restored|nao_restaurou|não_restaurou) normalized="not_restored" ;;
          unclear|incerto|naosei|nao_sei|não_sei|duvida) normalized="unclear" ;;
          *) echo "Use: same, changed, not_restored ou unclear." >&2; continue ;;
        esac
        ;;
      *)
        echo "internal error: unknown choice kind" >&2
        exit 2
        ;;
    esac
    printf -v "$__var" '%s' "$normalized"
    return 0
  done
}

echo
echo "Record human validation answers. Use the choices shown in each prompt."
ask_choice CIRCLE_ANSWER "1. O circulo parece circle, oval ou unclear?" circle
ask_choice SQUARE_ANSWER "2. O quadrado parece square, rectangle ou unclear?" square
ask_choice BORDER_ANSWER "3. A borda aparece inteira? yes, no ou unclear?" yesno
ask_choice CUT_ANSWER "4. Ha corte nas bordas? yes, no ou unclear?" yesno
ask_choice TOP_ARROW_ANSWER "5. A seta TOPO esta para cima? yes, no ou unclear?" yesno
ask_choice STRETCH_ANSWER "6. O padrao parece esticado? none, horizontal, vertical ou unclear?" stretch
ask_choice PLAYER_RESTORED_ANSWER "7. Depois de restaurar o player, a midia voltou igual? same, changed, not_restored ou unclear?" restored

echo "Recording human validation on the board"
ssh "$HOST" "REMOTE_DIR='$REMOTE_DIR' REMOTE_OUT_DIR='$REMOTE_OUT_DIR' CIRCLE_ANSWER='$CIRCLE_ANSWER' SQUARE_ANSWER='$SQUARE_ANSWER' BORDER_ANSWER='$BORDER_ANSWER' CUT_ANSWER='$CUT_ANSWER' TOP_ARROW_ANSWER='$TOP_ARROW_ANSWER' STRETCH_ANSWER='$STRETCH_ANSWER' PLAYER_RESTORED_ANSWER='$PLAYER_RESTORED_ANSWER' bash -s" <<'REMOTE_HUMAN'
set -euo pipefail

PROBE="$REMOTE_DIR/totem_display_visual_contract_probe.py"
python3 "$PROBE" \
  --out-dir "$REMOTE_OUT_DIR" \
  --record-human-validation \
  --circle-answer "$CIRCLE_ANSWER" \
  --square-answer "$SQUARE_ANSWER" \
  --border-answer "$BORDER_ANSWER" \
  --cut-answer "$CUT_ANSWER" \
  --top-arrow-answer "$TOP_ARROW_ANSWER" \
  --stretch-answer "$STRETCH_ANSWER" \
  --player-restored-answer "$PLAYER_RESTORED_ANSWER"
echo "remote C9.1.3 human validation: ok"
REMOTE_HUMAN

echo "C9.1.3 display visual contract complete. Evidence: $REMOTE_OUT_DIR"
