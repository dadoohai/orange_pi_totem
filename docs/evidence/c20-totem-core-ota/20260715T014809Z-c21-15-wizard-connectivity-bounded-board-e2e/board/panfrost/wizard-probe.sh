#!/usr/bin/env bash
set -euo pipefail

WORK="/tmp/c21-15-wizard-panfrost-probe"
KEY_HELPER="/tmp/c20_uinput_key_sequence.py"
SETTINGS_SERVICE="totem-open-settings.service"
PLAYER_SERVICE="kiosky-player.service"

rm -rf "$WORK"
install -d -m 0700 "$WORK"

fault_count() {
  journalctl -k -b --no-pager | grep -c "Unhandled Page fault" || true
}

cleanup() {
  systemctl stop "$SETTINGS_SERVICE" >/dev/null 2>&1 || true
  /opt/totem/bin/totem_open_settings_cleanup.sh --reason c21-15-panfrost-probe >/dev/null 2>&1 || true
  systemctl reset-failed "$SETTINGS_SERVICE" >/dev/null 2>&1 || true
  systemctl start "$PLAYER_SERVICE" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM HUP

initial="$(fault_count)"
printf 'initial_fault_events=%s\n' "$initial" >"$WORK/summary.txt"

for cycle in 1 2 3; do
  cleanup
  before="$(fault_count)"
  systemctl start "$SETTINGS_SERVICE" >"$WORK/cycle-$cycle-start.stdout" 2>"$WORK/cycle-$cycle-start.stderr" &
  start_pid=$!
  wizard_seen=false
  for _ in $(seq 1 30); do
    if pgrep -af "totem_setup_visual_wizard.py" >/dev/null; then
      wizard_seen=true
      break
    fi
    sleep 1
  done
  sleep 2
  after_open="$(fault_count)"
  "$KEY_HELPER" --keys q --delay-sec 0.2 >"$WORK/cycle-$cycle-key.txt"
  for _ in $(seq 1 45); do
    if ! pgrep -af "totem_setup_visual_wizard.py" >/dev/null \
      && [ "$(systemctl is-active "$SETTINGS_SERVICE" 2>/dev/null || true)" = "inactive" ]; then
      break
    fi
    sleep 1
  done
  wait "$start_pid" 2>/dev/null || true
  cleanup
  after_close="$(fault_count)"
  printf 'cycle=%s wizard_seen=%s before=%s after_open=%s after_close=%s\n' \
    "$cycle" "$wizard_seen" "$before" "$after_open" "$after_close" >>"$WORK/summary.txt"
done

final="$(fault_count)"
printf 'final_fault_events=%s\ndelta_fault_events=%s\n' "$final" "$((final - initial))" >>"$WORK/summary.txt"
printf 'player_active=%s\n' "$(systemctl is-active "$PLAYER_SERVICE")" >>"$WORK/summary.txt"
printf 'player_restarts=%s\n' "$(systemctl show "$PLAYER_SERVICE" -p NRestarts --value)" >>"$WORK/summary.txt"
cat "$WORK/summary.txt"

trap - EXIT INT TERM HUP
cleanup
