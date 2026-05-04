#!/usr/bin/env python3
"""C9.2.1 source-only launcher/setup decision simulation.

This module models the future launcher decision contract without importing or
executing the operational launcher, renderer, MPV, wizard, writer, network, or
service controls. It is intentionally pure: fixtures in, decision records out.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from typing import Any


sys.dont_write_bytecode = True

SCHEMA_VERSION = "dadooh-c9.2.1-launcher-setup-decision-sim.v1"
RESERVED_TTY = "tty2"


@dataclasses.dataclass(frozen=True)
class Fixture:
    name: str
    display_connected: bool
    config_valid: bool
    setup_requested: bool = False
    wizard_result: str = "not_run"
    config_valid_after_future_write: bool = False


FIXTURES: tuple[Fixture, ...] = (
    Fixture(
        name="display_disconnected",
        display_connected=False,
        config_valid=False,
    ),
    Fixture(
        name="display_connected_config_valid",
        display_connected=True,
        config_valid=True,
    ),
    Fixture(
        name="config_missing_setup_not_requested",
        display_connected=True,
        config_valid=False,
        setup_requested=False,
    ),
    Fixture(
        name="config_missing_setup_requested",
        display_connected=True,
        config_valid=False,
        setup_requested=True,
    ),
    Fixture(
        name="wizard_cancelled",
        display_connected=True,
        config_valid=False,
        setup_requested=True,
        wizard_result="cancelled",
    ),
    Fixture(
        name="wizard_candidate_ready",
        display_connected=True,
        config_valid=False,
        setup_requested=True,
        wizard_result="candidate_ready",
    ),
    Fixture(
        name="config_valid_after_future_write",
        display_connected=True,
        config_valid=False,
        setup_requested=True,
        wizard_result="candidate_ready",
        config_valid_after_future_write=True,
    ),
)


EXPECTED: dict[str, dict[str, str]] = {
    "display_disconnected": {
        "public_state": "display_missing",
        "exclusive_owner": "none",
        "next_step": "wait_for_display",
    },
    "display_connected_config_valid": {
        "public_state": "starting_player",
        "exclusive_owner": "player",
        "next_step": "player_running",
    },
    "config_missing_setup_not_requested": {
        "public_state": "config_missing",
        "exclusive_owner": "renderer",
        "next_step": "wait_config_retry_or_setup_trigger",
    },
    "config_missing_setup_requested": {
        "public_state": "setup_local_running",
        "exclusive_owner": "wizard",
        "next_step": "wait_wizard_exit",
    },
    "wizard_cancelled": {
        "public_state": "setup_local_cancelled",
        "exclusive_owner": "renderer",
        "next_step": "config_missing",
    },
    "wizard_candidate_ready": {
        "public_state": "setup_candidate_ready",
        "exclusive_owner": "renderer",
        "next_step": "setup_handoff_pending",
    },
    "config_valid_after_future_write": {
        "public_state": "starting_player",
        "exclusive_owner": "player",
        "next_step": "player_running",
    },
}


def no_operational_actions() -> dict[str, bool]:
    return {
        "operational_launcher_executed": False,
        "service_started": False,
        "service_stopped": False,
        "mpv_called": False,
        "renderer_called": False,
        "wizard_called_on_hdmi": False,
        "writer_called": False,
        "real_config_read": False,
        "real_config_written": False,
        "data_written": False,
        "opt_written": False,
        "network_changed": False,
        "nmcli_called": False,
        "display_changed": False,
        "kiosky_player_changed": False,
        "production_released": False,
    }


def fixture_input(fixture: Fixture) -> dict[str, Any]:
    return {
        "display_connected": fixture.display_connected,
        "config_valid": fixture.config_valid,
        "setup_requested": fixture.setup_requested,
        "wizard_result": fixture.wizard_result,
        "config_valid_after_future_write": fixture.config_valid_after_future_write,
    }


def base_decision(fixture: Fixture) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "scenario": fixture.name,
        "input": fixture_input(fixture),
        "reserved_tty": RESERVED_TTY,
        "public_state": "undecided",
        "exclusive_owner": "none",
        "renderer": "none",
        "wizard": "none",
        "player": "none",
        "handoff": "none",
        "next_step": "none",
        "guardrails": no_operational_actions(),
    }


def decide(fixture: Fixture) -> dict[str, Any]:
    decision = base_decision(fixture)

    if not fixture.display_connected:
        decision.update(
            {
                "public_state": "display_missing",
                "renderer": "ensure_stopped",
                "wizard": "not_allowed_without_display",
                "player": "not_started",
                "exclusive_owner": "none",
                "next_step": "wait_for_display",
            }
        )
        return decision

    if fixture.config_valid or fixture.config_valid_after_future_write:
        decision.update(
            {
                "public_state": "starting_player",
                "renderer": "stop_before_player",
                "wizard": "not_started",
                "player": "start_player_future_operation",
                "exclusive_owner": "player",
                "next_step": "player_running",
            }
        )
        if fixture.config_valid_after_future_write:
            decision["handoff"] = "future_writer_made_config_valid"
        return decision

    if not fixture.setup_requested:
        decision.update(
            {
                "public_state": "config_missing",
                "renderer": "show_config_missing_status",
                "wizard": "not_requested",
                "player": "not_started",
                "exclusive_owner": "renderer",
                "next_step": "wait_config_retry_or_setup_trigger",
            }
        )
        return decision

    if fixture.wizard_result == "cancelled":
        decision.update(
            {
                "public_state": "setup_local_cancelled",
                "renderer": "return_to_config_missing_status",
                "wizard": "ended_cancelled",
                "player": "not_started",
                "exclusive_owner": "renderer",
                "next_step": "config_missing",
            }
        )
        return decision

    if fixture.wizard_result == "candidate_ready":
        decision.update(
            {
                "public_state": "setup_candidate_ready",
                "renderer": "return_to_config_missing_status",
                "wizard": "ended_candidate_ready",
                "player": "not_started",
                "exclusive_owner": "renderer",
                "handoff": "candidate_ready_under_tmp",
                "next_step": "setup_handoff_pending",
            }
        )
        return decision

    decision.update(
        {
            "public_state": "setup_local_running",
            "renderer": "stop_before_wizard",
            "wizard": "run_on_reserved_tty_without_shell",
            "player": "not_started",
            "exclusive_owner": "wizard",
            "next_step": "wait_wizard_exit",
        }
    )
    return decision


def active_owner_count(decision: dict[str, Any]) -> int:
    owner = decision["exclusive_owner"]
    return 0 if owner == "none" else 1


def run_matrix() -> list[dict[str, Any]]:
    return [decide(fixture) for fixture in FIXTURES]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_self_test() -> None:
    decisions = run_matrix()
    assert_true(len(decisions) == 7, "matrix should cover seven required fixtures")
    seen = {decision["scenario"] for decision in decisions}
    assert_true(seen == set(EXPECTED), "matrix scenario set mismatch")

    for decision in decisions:
        expected = EXPECTED[decision["scenario"]]
        assert_true(decision["schema_version"] == SCHEMA_VERSION, "schema mismatch")
        assert_true(decision["reserved_tty"] == RESERVED_TTY, "reserved tty mismatch")
        assert_true(decision["public_state"] == expected["public_state"], f"state mismatch: {decision['scenario']}")
        assert_true(decision["exclusive_owner"] == expected["exclusive_owner"], f"owner mismatch: {decision['scenario']}")
        assert_true(decision["next_step"] == expected["next_step"], f"next step mismatch: {decision['scenario']}")
        assert_true(active_owner_count(decision) <= 1, f"xor violation: {decision['scenario']}")
        for key, value in decision["guardrails"].items():
            assert_true(value is False, f"operational guardrail violated: {decision['scenario']} {key}")

    candidate = next(item for item in decisions if item["scenario"] == "wizard_candidate_ready")
    assert_true(candidate["handoff"] == "candidate_ready_under_tmp", "candidate handoff should stay under /tmp")

    future_write = next(item for item in decisions if item["scenario"] == "config_valid_after_future_write")
    assert_true(
        future_write["handoff"] == "future_writer_made_config_valid",
        "future write should be modeled as future-only",
    )


def format_text(decisions: list[dict[str, Any]]) -> str:
    lines = [
        "Dadooh C9.2.1 launcher/setup source-only decision matrix",
        "",
        "scenario | public_state | owner | renderer | wizard | player | next_step",
    ]
    for item in decisions:
        lines.append(
            " | ".join(
                [
                    item["scenario"],
                    item["public_state"],
                    item["exclusive_owner"],
                    item["renderer"],
                    item["wizard"],
                    item["player"],
                    item["next_step"],
                ]
            )
        )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run C9.2.1 source-only launcher/setup decision simulation.",
        allow_abbrev=False,
    )
    parser.add_argument("--self-test", action="store_true", help="Validate the required decision matrix.")
    parser.add_argument("--json", action="store_true", help="Print the decision matrix as JSON.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0

        decisions = run_matrix()
        if args.json:
            print(json.dumps({"schema_version": SCHEMA_VERSION, "decisions": decisions}, ensure_ascii=True, indent=2))
        else:
            print(format_text(decisions))
        return 0
    except AssertionError:
        print("error: self-test failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
