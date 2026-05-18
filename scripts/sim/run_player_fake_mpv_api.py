#!/usr/bin/env python3
"""C18.1 placeholder for fake MPV/API player simulation.

This C17.8 round does not start player timing/sync/duration/looping work.  The
file only captures the planned local harness boundary.
"""

from __future__ import annotations

import argparse
import json


SCENARIOS = [
    "fake_api_environment_search_playlist",
    "fake_mpv_ipc_playback_state_transitions",
    "offline_cache_reuse_without_network",
    "media_download_failure_sanitized",
    "watchdog_restart_without_drm_kms",
    "duration_looping_audit_placeholder",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Placeholder for local fake MPV/API player simulation."
    )
    parser.add_argument("--list-scenarios", action="store_true", help="List planned scenarios as JSON")
    args = parser.parse_args()
    if args.list_scenarios:
        print(json.dumps({"implemented": False, "planned_scenarios": SCENARIOS}, indent=2, sort_keys=True))
    else:
        print("player_fake_mpv_api_stub=true")
        print("implemented=false")
        print("next_harness=c18_1_player_sim_audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
