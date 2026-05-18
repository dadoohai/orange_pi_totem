#!/usr/bin/env python3
"""C17.8.1 placeholder for wizard input replay.

This round only reserves the harness shape.  Implementation is intentionally
deferred until the C17.8 totem-core sandbox is accepted.
"""

from __future__ import annotations

import argparse
import json


SCENARIOS = [
    "firstboot_orientation_wifi_environment_happy_path",
    "environment_id_edit_middle_delete_backspace_ctrl_u",
    "environment_id_invalid_uuid_local_validation",
    "environment_id_api_not_found_safe_feedback",
    "environment_search_preflight_no_content",
    "settings_session_timeout_monotonic",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Placeholder for replaying visual wizard keyboard/input scenarios."
    )
    parser.add_argument("--list-scenarios", action="store_true", help="List planned scenarios as JSON")
    args = parser.parse_args()
    if args.list_scenarios:
        print(json.dumps({"implemented": False, "planned_scenarios": SCENARIOS}, indent=2, sort_keys=True))
    else:
        print("wizard_input_replay_stub=true")
        print("implemented=false")
        print("next_harness=c17_8_1_wizard_replay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
