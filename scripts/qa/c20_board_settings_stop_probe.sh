#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-/tmp/c20-board-settings-stop-probe}"
MAX_STOP_MS="${MAX_STOP_MS:-15000}"
LOCK_DIR="/run/totem/settings-session.lock"
REQUEST_FILE="/run/dadooh-settings/request.json"
APPLY_POLICY="/run/dadooh-settings/apply-policy.json"
TRACE_FILE="/tmp/c15-session.trace"
FINAL_STATUS="/tmp/dadooh-c10-6-2-open-settings/session/session-status.json"
umask 077
case "$OUT" in
  /tmp/*) ;;
  *) printf 'output path must be under /tmp\n' >&2; exit 2 ;;
esac
[ ! -L "$OUT" ]
rm -rf -- "$OUT"
mkdir -p "$OUT"

monotonic_ns() {
  python3 -c 'import time; print(time.monotonic_ns())'
}

kd_mode() {
  python3 - <<'PY'
import array
import fcntl
import os

fd = os.open("/dev/tty2", os.O_RDWR | os.O_NOCTTY)
value = array.array("i", [0])
try:
    fcntl.ioctl(fd, 0x4B3B, value, True)
finally:
    os.close(fd)
print(value[0])
PY
}

snapshot_file() {
  local path="$1"
  local target="$2"
  if [ -f "$path" ] && [ ! -L "$path" ]; then
    sha256sum "$path" > "$target.sha256"
    stat -c 'state=present mode=%a uid=%u gid=%g size=%s mtime=%Y' "$path" > "$target.stat"
  else
    printf 'state=absent\n' > "$target.sha256"
    printf 'state=absent\n' > "$target.stat"
  fi
}

wait_for_wizard() {
  for _ in $(seq 1 45); do
    if pgrep -af '[t]otem_setup_visual_wizard.py' >/dev/null && [ "$(kd_mode)" = 1 ]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for_player() {
  for _ in $(seq 1 60); do
    if systemctl is-active --quiet kiosky-player.service && [ "$(pgrep -xc mpv || true)" = 1 ]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

recover() {
  set +e
  /opt/totem/bin/totem_open_settings_cleanup.sh --reason c20-stop-probe-recovery >/dev/null 2>&1
  rm -f -- "$APPLY_POLICY"
  systemctl reset-failed totem-open-settings.service >/dev/null 2>&1
  systemctl start kiosky-player.service >/dev/null 2>&1
}

initial_player_state="$(systemctl is-active kiosky-player.service || true)"
initial_settings_state="$(systemctl is-active totem-open-settings.service || true)"
initial_mpv_count="$(pgrep -xc mpv || true)"
getty1_active="$(systemctl is-active getty@tty1.service || true)"
getty1_enabled="$(systemctl is-enabled getty@tty1.service || true)"
getty2_active="$(systemctl is-active getty@tty2.service || true)"
getty2_enabled="$(systemctl is-enabled getty@tty2.service || true)"
printf 'player=%s settings=%s mpv=%s getty1=%s/%s getty2=%s/%s\n' \
  "$initial_player_state" "$initial_settings_state" "$initial_mpv_count" \
  "$getty1_active" "$getty1_enabled" "$getty2_active" "$getty2_enabled" > "$OUT/preconditions.txt"
[ "$initial_player_state" = active ]
[ "$initial_settings_state" = inactive ]
[ "$initial_mpv_count" = 1 ]
[ "$getty1_active" = inactive ]
[ "$getty1_enabled" = disabled ]
[ "$getty2_active" = inactive ]
[ "$getty2_enabled" = disabled ]
! pgrep -af '[t]otem_open_settings_session.sh' >/dev/null
! pgrep -af '[t]otem_setup_visual_wizard.py' >/dev/null
[ ! -e "$LOCK_DIR" ]
[ ! -L "$LOCK_DIR" ]
[ ! -e "$REQUEST_FILE" ]
[ ! -L "$REQUEST_FILE" ]
[ ! -e "$APPLY_POLICY" ]
[ ! -L "$APPLY_POLICY" ]

trace_size_before="$(stat -c %s "$TRACE_FILE" 2>/dev/null || printf 0)"
trap recover EXIT

snapshot_file /data/config/config.json "$OUT/config.before"
snapshot_file /data/state/totem-settings/last-settings.json "$OUT/context.before"
journalctl -k -b --no-pager -o short-iso | grep -i -E 'panfrost.*(fault|error)|gpu.*(fault|error)' > "$OUT/gpu.before.log" || true

wait_for_player
systemctl reset-failed totem-open-settings.service || true
probe_started_at="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
systemctl start --no-block totem-open-settings.service
wait_for_wizard
printf '%s\n' "$(kd_mode)" > "$OUT/during.kd-mode"

started_ns="$(monotonic_ns)"
set +e
systemctl stop totem-open-settings.service > "$OUT/stop.stdout" 2> "$OUT/stop.stderr"
stop_rc="$?"
set -e
finished_ns="$(monotonic_ns)"
elapsed_ms=$(( (finished_ns - started_ns) / 1000000 ))
printf '%s\n' "$stop_rc" > "$OUT/stop.rc"
printf '%s\n' "$elapsed_ms" > "$OUT/stop.elapsed-ms"

journalctl -u totem-open-settings.service --since "$probe_started_at" --no-pager -o short-iso > "$OUT/service.journal"
systemctl show totem-open-settings.service -p ActiveState -p SubState -p Result -p ExecMainStatus > "$OUT/service.after"
ps -eo pid,ppid,pgid,sid,stat,comm,args > "$OUT/processes.after"
tail -c "+$((trace_size_before + 1))" "$TRACE_FILE" > "$OUT/session.trace.delta"

[ "$stop_rc" = 0 ]
[ "$elapsed_ms" -lt "$MAX_STOP_MS" ]
[ -s "$OUT/service.journal" ]
! grep -Eqi "timed out|result 'timeout'|SIGKILL" "$OUT/service.journal"
grep -qx "ActiveState=inactive" "$OUT/service.after"
grep -qx "Result=success" "$OUT/service.after"
grep -q "phase=trap_signal=TERM" "$OUT/session.trace.delta"
grep -q "phase=openvt_stop_done" "$OUT/session.trace.delta"
grep -q "phase=write_final_status_skip_player_wait" "$OUT/session.trace.delta"
grep -q "phase=on_exit_done rc=0" "$OUT/session.trace.delta"
python3 - "$FINAL_STATUS" > "$OUT/final-status-check.txt" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload.get("final_status_player_wait_mode") == "skip-player-wait"
assert payload.get("signal_stop_reason") == "TERM"
assert payload.get("service_restore_enqueued") is True
print("final_status_player_wait_mode=skip-player-wait")
print("signal_stop_reason=TERM")
print("service_restore_enqueued=true")
PY
wait_for_player

snapshot_file /data/config/config.json "$OUT/config.after"
snapshot_file /data/state/totem-settings/last-settings.json "$OUT/context.after"
journalctl -k -b --no-pager -o short-iso | grep -i -E 'panfrost.*(fault|error)|gpu.*(fault|error)' > "$OUT/gpu.after.log" || true

cmp "$OUT/config.before.sha256" "$OUT/config.after.sha256"
cmp "$OUT/config.before.stat" "$OUT/config.after.stat"
cmp "$OUT/context.before.sha256" "$OUT/context.after.sha256"
cmp "$OUT/context.before.stat" "$OUT/context.after.stat"
cmp "$OUT/gpu.before.log" "$OUT/gpu.after.log"
[ "$(systemctl is-active totem-open-settings.service || true)" = inactive ]
[ "$(systemctl is-failed totem-open-settings.service || true)" = inactive ]
[ "$(kd_mode)" = 0 ]
[ "$(systemctl is-active kiosky-player.service)" = active ]
[ "$(pgrep -xc mpv)" = 1 ]
! pgrep -af '[t]otem_open_settings_session.sh' >/dev/null
! pgrep -af '[t]otem_setup_visual_wizard.py' >/dev/null
! pgrep -af '[o]penvt.*totem_setup_visual_wizard.py' >/dev/null
[ ! -e "$LOCK_DIR" ]
[ ! -L "$LOCK_DIR" ]
[ ! -e "$REQUEST_FILE" ]
[ ! -L "$REQUEST_FILE" ]
[ ! -e "$APPLY_POLICY" ]
[ ! -L "$APPLY_POLICY" ]

for path in \
  /tmp/dadooh-c10-6-2-private/private-values.json \
  /tmp/dadooh-c10-6-2-private/last-settings.json \
  /tmp/dadooh-c10-6-2-handoff/config.candidate.private.json \
  /tmp/dadooh-c10-6-2-visual-wizard/qr-pairing/private-values.json
do
  [ ! -e "$path" ]
  [ ! -L "$path" ]
done

printf 'passed=true stop_elapsed_ms=%s max_stop_ms=%s\n' "$elapsed_ms" "$MAX_STOP_MS" > "$OUT/result.txt"
trap - EXIT
