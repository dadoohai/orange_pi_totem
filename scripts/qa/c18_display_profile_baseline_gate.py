#!/usr/bin/env python3
"""Validate sanitized C18 display-profile baseline evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.display_profile_baseline_gate.v1"
BASELINE_SCHEMA = "dadooh.c18.display_profile_baseline.v1"
RESULT_CLAIM = "read_only_display_profile_baseline_collected"
ALLOWED_CLASSIFICATIONS = {
    "no_sink",
    "forced_mode_requested",
    "edid_missing_low_mode_fallback",
    "edid_missing",
    "auto_negotiated_modes_present",
    "unknown",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url", re.compile(r"https?://", re.I)),
    ("private_ip", re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")),
    ("mac", re.compile(r"\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b", re.I)),
    ("data_media_path", re.compile(r"/data/media(?:/|\b)", re.I)),
    ("data_config_path", re.compile(r"/data/config(?:/|\b)", re.I)),
    ("opt_totem_path", re.compile(r"/opt/totem(?:/|\b)", re.I)),
    ("secret_key", re.compile(r'"?(api[_-]?key|secret|password|passwd|senha)"?\s*[:=]', re.I)),
    ("bearer", re.compile(r"\bBearer\s+\S+", re.I)),
)
OVERCLAIM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("h2_ready", re.compile(r"\bH2\b.{0,40}\b(passed|green|ready|approved|complete|completed|verde|pronto|aprovad)", re.I)),
    ("production_ready", re.compile(r"\b(production|producao)\b.{0,40}\b(passed|green|ready|approved|enabled|complete|completed|verde|pronto|aprovad)", re.I)),
    ("stable_ready", re.compile(r"\bstable\b.{0,40}\b(passed|green|ready|approved|enabled|complete|completed|verde|pronto|aprovad)", re.I)),
)
REQUIRED_NON_CLAIMS = {
    "this_collector_does_not_start_stop_restart_or_signal_player",
    "this_collector_does_not_force_resolution_or_modeset",
    "this_collector_does_not_include_raw_edid_or_framebuffer",
    "this_collector_does_not_read_config_content_media_journal_or_network",
    "this_collector_does_not_validate_playback_decode_health",
    "this_collector_does_not_replace_powerloss_soak_h2_stable_or_thaw",
}


def read_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if path.is_symlink():
        errors.append("baseline_symlink_forbidden")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"baseline_json_error:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        errors.append("baseline_not_object")
        return {}
    return data


def scan_text(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for label, pattern in LEAK_PATTERNS:
        if pattern.search(text):
            errors.append(f"privacy_leak:{label}")
    for label, pattern in OVERCLAIM_PATTERNS:
        if pattern.search(text):
            errors.append(f"overclaim:{label}")


def walk_forbidden_keys(value: Any, errors: list[str], key_path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}"
            lower = str(key).lower()
            if lower in {"raw", "raw_edid", "edid_raw", "raw_cmdline", "framebuffer_raw", "journal"}:
                errors.append(f"forbidden_key:{child_path}")
            walk_forbidden_keys(child, errors, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk_forbidden_keys(child, errors, f"{key_path}[{index}]")


def validate_baseline(data: dict[str, Any], errors: list[str]) -> None:
    if data.get("schema") != BASELINE_SCHEMA:
        errors.append("baseline_schema")
    if data.get("result_claim") != RESULT_CLAIM:
        errors.append("baseline_result_claim")
    if data.get("passed") is not True:
        errors.append("baseline_not_passed")
    if data.get("classification") not in ALLOWED_CLASSIFICATIONS:
        errors.append("baseline_classification")
    policy = data.get("collection_policy") if isinstance(data.get("collection_policy"), dict) else {}
    expected_policy = {
        "read_only": True,
        "reads_edid_size_and_hash": True,
        "includes_raw_edid": False,
        "reads_framebuffer_pixels": False,
        "reads_config_content": False,
        "reads_media": False,
        "reads_journal": False,
        "uses_network": False,
        "mutates_player": False,
        "mutates_display": False,
        "raw_cmdline_included": False,
    }
    for key, value in expected_policy.items():
        if policy.get(key) is not value:
            errors.append(f"policy_{key}")
    non_claims = set(data.get("non_claims") if isinstance(data.get("non_claims"), list) else [])
    for claim in sorted(REQUIRED_NON_CLAIMS - non_claims):
        errors.append(f"non_claim_missing:{claim}")
    cmdline = data.get("cmdline") if isinstance(data.get("cmdline"), dict) else {}
    if cmdline.get("raw_cmdline_included") is not False:
        errors.append("cmdline_raw_included")
    drm = data.get("drm") if isinstance(data.get("drm"), dict) else {}
    connectors = drm.get("connectors") if isinstance(drm.get("connectors"), list) else []
    for index, item in enumerate(connectors):
        if not isinstance(item, dict):
            errors.append(f"connector_not_object:{index}")
            continue
        edid = item.get("edid") if isinstance(item.get("edid"), dict) else {}
        if edid.get("raw_edid_included") is not False:
            errors.append(f"edid_raw_included:{index}")
        if int(edid.get("bytes") or 0) > 0 and not SHA256_RE.fullmatch(str(edid.get("sha256") or "")):
            errors.append(f"edid_sha256_invalid:{index}")
        modes = item.get("modes") if isinstance(item.get("modes"), list) else []
        if len(modes) > 64:
            errors.append(f"too_many_modes:{index}")
    walk_forbidden_keys(data, errors)


def evaluate(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    target = path.expanduser().resolve(strict=False)
    if not target.is_file():
        errors.append("baseline_missing")
        data: dict[str, Any] = {}
    else:
        scan_text(target, errors)
        data = read_json(target, errors)
        if data:
            validate_baseline(data, errors)
    return {
        "schema": SCHEMA,
        "baseline": str(target),
        "passed": not errors,
        "blockers": sorted(set(errors)),
        "result_claim": "display_profile_baseline_accepted" if not errors else "display_profile_baseline_rejected",
        "non_claims": [
            "this_gate_does_not_execute_board_commands_or_ssh",
            "this_gate_does_not_validate_playback_decode_health",
            "this_gate_does_not_replace_powerloss_soak_h2_stable_or_thaw",
            "this_gate_does_not_publish_promote_stable_enable_auto_pull_or_thaw",
        ],
    }


def write_fixture(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": BASELINE_SCHEMA,
                "passed": True,
                "result_claim": RESULT_CLAIM,
                "classification": "edid_missing_low_mode_fallback",
                "collection_policy": {
                    "read_only": True,
                    "reads_edid_size_and_hash": True,
                    "includes_raw_edid": False,
                    "reads_framebuffer_pixels": False,
                    "reads_config_content": False,
                    "reads_media": False,
                    "reads_journal": False,
                    "uses_network": False,
                    "mutates_player": False,
                    "mutates_display": False,
                    "raw_cmdline_included": False,
                },
                "cmdline": {"raw_cmdline_included": False, "video_override_present": False, "video_overrides": []},
                "drm": {
                    "connectors": [
                        {
                            "connector": "HDMI-A-1",
                            "status": "connected",
                            "enabled": "enabled",
                            "dpms": "On",
                            "mode": "",
                            "mode_present": False,
                            "modes": ["1024x768", "800x600"],
                            "modes_count": 2,
                            "max_mode_area": 786432,
                            "edid": {
                                "present": True,
                                "bytes": 0,
                                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                                "empty": True,
                                "raw_edid_included": False,
                            },
                        }
                    ]
                },
                "non_claims": sorted(REQUIRED_NON_CLAIMS),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


class DisplayProfileBaselineGateSelfTest(unittest.TestCase):
    def test_valid_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.json"
            write_fixture(path)
            result = evaluate(path)
        self.assertTrue(result["passed"], result["blockers"])

    def test_raw_edid_key_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.json"
            write_fixture(path)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["drm"]["connectors"][0]["edid"]["raw"] = "00ff"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = evaluate(path)
        self.assertFalse(result["passed"])
        self.assertTrue(any(item.startswith("forbidden_key:") for item in result["blockers"]))

    def test_private_path_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.json"
            write_fixture(path)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["note"] = "/data/config/config.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = evaluate(path)
        self.assertFalse(result["passed"])
        self.assertIn("privacy_leak:data_config_path", result["blockers"])


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(DisplayProfileBaselineGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if args.baseline is None:
        payload = {
            "schema": SCHEMA,
            "passed": False,
            "blockers": ["baseline_required"],
            "result_claim": "display_profile_baseline_rejected",
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    payload = evaluate(args.baseline)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("passed=" + ("true" if payload["passed"] else "false"))
        if payload["blockers"]:
            print("blockers=" + ",".join(payload["blockers"]))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
