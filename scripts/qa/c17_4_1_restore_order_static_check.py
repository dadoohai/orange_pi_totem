#!/usr/bin/env python3
"""Static smoke check for C17.4.1 settings-session restore ordering."""

from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
SESSION = ROOT / "scripts" / "board" / "totem_open_settings_session.sh"
CLEANUP = ROOT / "scripts" / "board" / "totem_open_settings_cleanup.sh"


def section(text: str, start: str, end: str) -> str:
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[start_index:end_index]


def main() -> int:
    text = SESSION.read_text(encoding="utf-8")
    cleanup = CLEANUP.read_text(encoding="utf-8")
    restore = section(text, "restore_service() {", "\n}\n\nstop_openvt_if_running()")
    openvt_stop = section(text, "stop_openvt_if_running() {", "\n}\n\nkill_visual_if_running()")
    release = section(text, "release_session_lock_for_restore() {", "\n}\n\nwrite_final_status()")
    final_status = section(text, "write_final_status() {", "\nimport json\n")
    fast_status = section(
        final_status,
        'if [ "$player_wait_mode" = "skip-player-wait" ]; then',
        'elif [ -e "$LOCK_DIR" ]; then',
    )
    on_exit = section(text, "on_exit() {", "\n}\non_term()")
    signal_handlers = section(text, "on_term()", "\ntrap on_exit EXIT")
    normal = section(text, 'c1523_phase "session_cleanup_start rc=0"', 'c1523_phase "session_done rc=0"')
    nonblocking_start = "systemctl start --no-block kiosky-player.service"
    bounded_start = f"/usr/bin/timeout -k 1s 5s {nonblocking_start}"

    checks = {
        "restore_has_lock_guard": '[ -e "$LOCK_DIR" ]' in restore,
        "restore_has_nonblocking_start": nonblocking_start in restore,
        "restore_start_is_bounded": bounded_start in restore,
        "restore_guard_before_start": restore.index('[ -e "$LOCK_DIR" ]') < restore.index(nonblocking_start),
        "restore_records_start_rc": "SERVICE_RESTORE_START_RC" in restore,
        "cleanup_has_nonblocking_start": nonblocking_start in cleanup,
        "cleanup_start_is_bounded": bounded_start in cleanup,
        "cleanup_records_start_rc": "PLAYER_RESTORE_START_RC" in cleanup,
        "cleanup_status_records_restore": '"player_restore_enqueued"' in cleanup,
        "release_removes_request": "cleanup_trigger_request" in release,
        "release_removes_lock": "cleanup_session_lock" in release,
        "release_logs_before_restore": "session_lock_released_before_restore" in release,
        "normal_releases_before_restore": normal.index("release_session_lock_for_restore") < normal.index("restore_service"),
        "normal_restore_inside_release_success_branch": re.search(r"if release_session_lock_for_restore; then\s+restore_service", normal) is not None,
        "normal_waits_after_restore": normal.index("restore_service") < normal.index("wait_player_running"),
        "normal_wait_inside_release_success_branch": re.search(r"restore_service\s+\|\|\s+true\s+wait_player_running", normal) is not None,
        "normal_cleanup_still_idempotent": normal.rindex("cleanup_session_lock") > normal.index("restore_service"),
        "final_status_wait_guarded_by_lock_absence": '[ -e "$LOCK_DIR" ]' in final_status and "wait_player_running" in final_status,
        "final_status_defaults_to_normal_wait": 'local player_wait_mode="${1:-wait-player}"' in final_status,
        "signal_status_skips_long_wait": "wait_player_running" not in fast_status,
        "signal_status_records_wait_mode": 'FINAL_STATUS_PLAYER_WAIT_MODE="$player_wait_mode"' in final_status,
        "signal_stop_initialized_false": 'SIGNAL_STOP="false"' in text,
        "signal_handlers_select_fast_stop": signal_handlers.count('SIGNAL_STOP="true"') == 3,
        "systemd_term_exits_clean": 'SIGNAL_STOP_REASON="TERM"; c15_trace "trap_signal=TERM"; on_exit 0' in signal_handlers,
        "signal_reason_is_recorded": 'SIGNAL_STOP_REASON="$SIGNAL_STOP_REASON"' in final_status,
        "signal_exit_stops_openvt_before_visual": on_exit.index("stop_openvt_if_running") < on_exit.index("kill_visual_if_running"),
        "signal_exit_selects_skip_wait": 'final_status_mode="skip-player-wait"' in on_exit,
        "signal_exit_passes_wait_mode": 'write_final_status "$final_status_mode"' in on_exit,
        "openvt_stop_is_bounded": "for _ in $(seq 1 10)" in openvt_stop and "sleep 0.1" in openvt_stop,
        "openvt_stop_terminates_then_escalates": openvt_stop.index("kill -TERM") < openvt_stop.index("kill -KILL"),
        "openvt_stop_reaps_child": 'wait "$pid"' in openvt_stop,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print("restore-order-static-check: failed " + ",".join(failed))
        return 1

    if re.search(r"restore_service\s*\|\|\s*true\s*\n\s+wait_player_running", normal) is None:
        print("restore-order-static-check: failed restore_wait_sequence")
        return 1

    print("restore-order-static-check: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
