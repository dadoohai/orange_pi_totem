#!/usr/bin/env bash
set -u

ARTIFACT_DIR="${1:-/tmp/c20-e2e-rc-probe}"
WIZARD_DIR="/tmp/dadooh-c10-6-2-visual-wizard"
SESSION_DIR="/tmp/dadooh-c10-6-2-open-settings/session"
REQUEST_DIR="/run/dadooh-settings"
LOCK_DIR="/run/totem/settings-session.lock"
KEY_HELPER="/tmp/c20_uinput_key_sequence.py"

mkdir -p "$ARTIFACT_DIR/captures" "$ARTIFACT_DIR/screens"
LOG="$ARTIFACT_DIR/probe.log"
: >"$LOG"

log() {
  printf '%s %s\n' "$(date -Is)" "$*" | tee -a "$LOG"
}

run() {
  log "RUN $*"
  "$@" >>"$LOG" 2>&1
  rc=$?
  log "RC $rc :: $*"
  return "$rc"
}

status_snapshot() {
  label="$1"
  {
    echo "---$label"
    date -Is
    echo "kiosky-player=$(systemctl is-active kiosky-player.service || true)"
    echo "open-settings-active=$(systemctl is-active totem-open-settings.service || true)"
    echo "open-settings-failed=$(systemctl is-failed totem-open-settings.service || true)"
    echo "---processes"
    ps -eo pid,ppid,stat,comm,args | grep -E "totem_open_settings_session|totem_setup_visual_wizard|openvt|kiosk.py|mpv" | grep -v grep || true
    echo "---locks"
    ls -la "$LOCK_DIR" "$REQUEST_DIR/request.json" "$REQUEST_DIR" 2>/dev/null || true
    echo "---totem-core-status"
    /opt/totem/bin/totem-updatectl status --component totem-core 2>/dev/null || true
  } >"$ARTIFACT_DIR/$label.txt"
}

capture_fb() {
  name="$1"
  ffmpeg -hide_banner -loglevel error -f fbdev -i /dev/fb0 -frames:v 1 -update 1 \
    "$ARTIFACT_DIR/captures/$name.jpg" >>"$LOG" 2>&1 || true
  sha256sum "$ARTIFACT_DIR/captures/$name.jpg" >>"$LOG" 2>&1 || true
}

copy_latest_screen() {
  name="$1"
  latest="$(find "$WIZARD_DIR/screens" -maxdepth 1 -type f -name "*.svg" -printf "%T@ %p\n" 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2- || true)"
  if [ -n "${latest:-}" ] && [ -f "$latest" ]; then
    cp "$latest" "$ARTIFACT_DIR/screens/$name-$(basename "$latest")" 2>/dev/null || true
    log "latest_screen $name $(basename "$latest")"
  else
    log "latest_screen $name missing"
  fi
}

wait_for_wizard() {
  for i in $(seq 1 30); do
    if pgrep -af "totem_setup_visual_wizard.py" >"$ARTIFACT_DIR/wizard-process.txt"; then
      log "wizard_seen_at=${i}s"
      return 0
    fi
    sleep 1
  done
  log "wizard_not_seen"
  return 1
}

wait_for_review_screen() {
  for _ in $(seq 1 20); do
    if find "$WIZARD_DIR/screens" -maxdepth 1 -type f -name "*-05-review.svg" | grep -q .; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

wait_for_settings_exit() {
  for _ in $(seq 1 30); do
    if ! pgrep -af "totem_setup_visual_wizard.py" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

send_keys() {
  keys="$1"
  if [ ! -x "$KEY_HELPER" ]; then
    log "key_helper_missing $KEY_HELPER"
    return 2
  fi
  run "$KEY_HELPER" --keys "$keys" --delay-sec 0.45
}

log "c20_e2e_probe_start artifact_dir=$ARTIFACT_DIR"
status_snapshot "00-pre"

run /opt/totem/bin/totem_open_settings_cleanup.sh --reason c20-e2e-probe-preclean || true
run systemctl reset-failed totem-open-settings.service || true
run systemctl start kiosky-player.service || true
rm -rf "$WIZARD_DIR" "$SESSION_DIR"
mkdir -p "$WIZARD_DIR" "$SESSION_DIR"

status_snapshot "01-clean"

log "start_open_settings_service"
systemctl start totem-open-settings.service >"$ARTIFACT_DIR/systemctl-start.stdout" 2>"$ARTIFACT_DIR/systemctl-start.stderr" &
echo "$!" >"$ARTIFACT_DIR/systemctl-start.pid"

if wait_for_wizard; then
  sleep 1
  capture_fb "01-opened"
  copy_latest_screen "01-opened"
else
  status_snapshot "99-wizard-not-seen"
  exit 0
fi

log "navigate_to_review"
send_keys "up,right,right,right" || true
sleep 2
if wait_for_review_screen; then
  echo "review_screen_seen=true" >"$ARTIFACT_DIR/review-screen-status.txt"
else
  echo "review_screen_seen=false" >"$ARTIFACT_DIR/review-screen-status.txt"
fi
capture_fb "02-review-attempt"
copy_latest_screen "02-review-attempt"

log "enter_on_review_or_current"
send_keys "enter" || true
sleep 2
capture_fb "03-enter-after-review"
copy_latest_screen "03-enter-after-review"

log "cancel_with_q"
send_keys "q" || true
if wait_for_settings_exit; then
  echo "cancel_exited=true" >"$ARTIFACT_DIR/cancel-status.txt"
else
  echo "cancel_exited=false" >"$ARTIFACT_DIR/cancel-status.txt"
fi

status_snapshot "90-after-cancel"

if pgrep -af "totem_setup_visual_wizard.py" >/dev/null 2>&1; then
  log "forced_cleanup_after_cancel_failure"
  systemctl stop totem-open-settings.service >>"$LOG" 2>&1 || true
fi
run /opt/totem/bin/totem_open_settings_cleanup.sh --reason c20-e2e-probe-final || true
run systemctl reset-failed totem-open-settings.service || true
run systemctl start kiosky-player.service || true
sleep 3

status_snapshot "99-final"

find "$ARTIFACT_DIR" -maxdepth 3 -type f -printf "%p %s\n" | sort >"$ARTIFACT_DIR/file-list.txt"
log "c20_e2e_probe_done"
