#!/usr/bin/env python3
"""Collect C18 production totem-core auto-pull timer evidence on a board.

Default mode is read-only except for the optional frozen player-runtime probe.
Use --probe-frozen-player-runtime for the production validation run; it calls a
public rollback verb that must fail closed with rc=44.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.totem_core.production_timer_collect.v1"
DEFAULT_EXPECTED_IMAGE_TAG = "c18-hwdecode-prod-1"
DEFAULT_EXPECTED_RELEASE_TAG = "totem-core-c18.ota-core-prod-20260705T184013Z-ccaf5a1"
DEFAULT_POLICY = Path("/data/updates/policy.json")
DEFAULT_UPDATECTL = Path("/opt/totem/bin/totem-updatectl")


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_cmd(cmd: list[str], *, timeout: int = 30) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except Exception as exc:
        return {
            "cmd": cmd,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }


def parse_key_value(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key.strip()] = value.strip()
    return fields


def parse_json_from_output(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def read_text(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def load_json_file(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    raw, error = read_text(path)
    if error:
        return None, error
    try:
        data = json.loads(raw or "")
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    return (data, None) if isinstance(data, dict) else (None, "json_not_object")


def systemctl_raw(*args: str) -> str:
    result = run_cmd(["systemctl", *args])
    return str(result["stdout"]).strip()


def systemctl_show(unit: str, props: list[str]) -> dict[str, str]:
    result = run_cmd(["systemctl", "show", unit, *[f"-p{prop}" for prop in props]])
    values: dict[str, str] = {}
    for line in str(result["stdout"]).splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    values["_returncode"] = str(result["returncode"])
    if result["stderr"]:
        values["_stderr"] = str(result["stderr"])[-1000:]
    return values


def collect(args: argparse.Namespace) -> dict[str, Any]:
    marker_path = Path(args.marker_path or f"/etc/dadooh/{args.expected_image_tag}-image")
    marker_raw, marker_error = read_text(marker_path)
    policy, policy_error = load_json_file(args.policy)

    status_cmd = [str(args.updatectl), "status", "--component", "totem-core"]
    status_result = run_cmd(status_cmd, timeout=30)
    self_test_result = run_cmd([str(args.updatectl), "self-test", "--component", "totem-core"], timeout=60)

    journal_result = run_cmd(
        ["journalctl", "-u", args.service_unit, "-b", "-n", str(args.journal_lines), "--no-pager"],
        timeout=30,
    )
    timer_journal_result = run_cmd(
        ["journalctl", "-u", args.timer_unit, "-b", "-n", str(args.journal_lines), "--no-pager"],
        timeout=30,
    )

    freeze_probe: dict[str, Any] = {"ran": False}
    if args.probe_frozen_player_runtime:
        probe = run_cmd([str(args.updatectl), "rollback", "--component", "player-runtime"], timeout=60)
        freeze_probe = {
            "ran": True,
            "cmd": probe["cmd"],
            "returncode": probe["returncode"],
            "stdout_tail": str(probe["stdout"])[-2000:],
            "stderr_tail": str(probe["stderr"])[-2000:],
        }

    player_nrestarts = systemctl_raw("show", args.player_unit, "-p", "NRestarts", "--value")

    return {
        "schema": SCHEMA,
        "collected_at_utc": now_utc(),
        "expected": {
            "image_tag": args.expected_image_tag,
            "release_tag": args.expected_release_tag,
        },
        "non_claims": [
            "does_not_thaw_player_runtime",
            "does_not_update_media_system",
            "does_not_publish_release",
        ],
        "image_marker": {
            "path": str(marker_path),
            "exists": marker_raw is not None,
            "read_error": marker_error,
            "raw_sha256": sha256_text(marker_raw) if marker_raw is not None else None,
            "fields": parse_key_value(marker_raw or ""),
        },
        "policy": policy or {},
        "policy_path": str(args.policy),
        "policy_error": policy_error,
        "timer": {
            "unit": args.timer_unit,
            "enabled_raw": systemctl_raw("is-enabled", args.timer_unit),
            "active_raw": systemctl_raw("is-active", args.timer_unit),
            "show": systemctl_show(args.timer_unit, [
                "LastTriggerUSec",
                "LastTriggerUSecMonotonic",
                "NextElapseUSecRealtime",
                "Result",
                "Unit",
            ]),
            "journal_tail": str(timer_journal_result["stdout"]).splitlines()[-args.journal_lines:],
            "journal_returncode": timer_journal_result["returncode"],
        },
        "service": {
            "unit": args.service_unit,
            "show": systemctl_show(args.service_unit, [
                "ActiveState",
                "Result",
                "ExecMainStatus",
                "TriggeredBy",
            ]),
            "journal_tail": str(journal_result["stdout"]).splitlines()[-args.journal_lines:],
            "journal_returncode": journal_result["returncode"],
        },
        "totem_core_status": parse_json_from_output(str(status_result["stdout"])) or {},
        "totem_core_status_raw_tail": str(status_result["stdout"])[-4000:],
        "totem_core_status_returncode": status_result["returncode"],
        "totem_core_self_test": parse_json_from_output(str(self_test_result["stdout"])) or {},
        "totem_core_self_test_raw_tail": str(self_test_result["stdout"])[-4000:],
        "totem_core_self_test_returncode": self_test_result["returncode"],
        "player_service": {
            "unit": args.player_unit,
            "active_raw": systemctl_raw("is-active", args.player_unit),
            "nrestarts": player_nrestarts,
        },
        "player_runtime_freeze_probe": freeze_probe,
    }


class CollectSelfTest(unittest.TestCase):
    def test_parse_key_value(self) -> None:
        self.assertEqual(
            parse_key_value("image_tag=c18\nfinal_image=true\n#x\nbad\n"),
            {"image_tag": "c18", "final_image": "true"},
        )

    def test_parse_json_from_output(self) -> None:
        self.assertEqual(parse_json_from_output("INFO x\n{\"ok\": true}\n")["ok"], True)

    def test_read_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw, error = read_text(Path(tmp) / "missing")
        self.assertIsNone(raw)
        self.assertIn("FileNotFoundError", error or "")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect production totem-core timer evidence.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected-image-tag", default=DEFAULT_EXPECTED_IMAGE_TAG)
    parser.add_argument("--expected-release-tag", default=DEFAULT_EXPECTED_RELEASE_TAG)
    parser.add_argument("--marker-path")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--updatectl", type=Path, default=DEFAULT_UPDATECTL)
    parser.add_argument("--timer-unit", default="totem-update-agent.timer")
    parser.add_argument("--service-unit", default="totem-update-agent.service")
    parser.add_argument("--player-unit", default="kiosky-player.service")
    parser.add_argument("--journal-lines", type=int, default=120)
    parser.add_argument("--probe-frozen-player-runtime", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(CollectSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    payload = collect(args)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
