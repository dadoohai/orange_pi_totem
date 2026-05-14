#!/usr/bin/env python3
"""Static smoke check for C17.4.1 settings-session restore ordering."""

from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
SESSION = ROOT / "scripts" / "board" / "totem_open_settings_session.sh"


def section(text: str, start: str, end: str) -> str:
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[start_index:end_index]


def main() -> int:
    text = SESSION.read_text(encoding="utf-8")
    restore = section(text, "restore_service() {", "\n}\n\nkill_visual_if_running()")
    release = section(text, "release_session_lock_for_restore() {", "\n}\n\nwrite_final_status()")
    final_status = section(text, "write_final_status() {", "\n  python3 - ")
    normal = section(text, 'c1523_phase "session_cleanup_start rc=0"', 'c1523_phase "session_done rc=0"')

    checks = {
        "restore_has_lock_guard": '[ -e "$LOCK_DIR" ]' in restore,
        "restore_guard_before_start": restore.index('[ -e "$LOCK_DIR" ]') < restore.index("systemctl start kiosky-player.service"),
        "release_removes_request": "cleanup_trigger_request" in release,
        "release_removes_lock": "cleanup_session_lock" in release,
        "release_logs_before_restore": "session_lock_released_before_restore" in release,
        "normal_releases_before_restore": normal.index("release_session_lock_for_restore") < normal.index("restore_service"),
        "normal_restore_inside_release_success_branch": re.search(r"if release_session_lock_for_restore; then\s+restore_service", normal) is not None,
        "normal_waits_after_restore": normal.index("restore_service") < normal.index("wait_player_running"),
        "normal_wait_inside_release_success_branch": re.search(r"restore_service\s+\|\|\s+true\s+wait_player_running", normal) is not None,
        "normal_cleanup_still_idempotent": normal.rindex("cleanup_session_lock") > normal.index("restore_service"),
        "final_status_wait_guarded_by_lock_absence": '[ -e "$LOCK_DIR" ]' in final_status and "wait_player_running" in final_status,
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
