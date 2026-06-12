#!/usr/bin/env python3
"""Tests for the C18 player-runtime lab quarantine reset harness."""

from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RESET_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_lab_quarantine_reset.py"
RELEASE_GATE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_release_gate.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reset = load_module(RESET_PATH, "c18_player_runtime_lab_quarantine_reset_under_test")
release_gate = load_module(RELEASE_GATE_PATH, "c18_player_runtime_release_gate_for_reset_test")


class C18PlayerRuntimeLabQuarantineResetTest(unittest.TestCase):
    def make_package(self, root: Path, version: str, suffix: str = "target") -> tuple[Path, Path, dict]:
        source = release_gate.SNAPSHOT_KIOSK.read_text(encoding="utf-8") + f"\n# quarantine reset test {suffix}\n"
        payload = release_gate.write_payload(root, version, source)
        manifest = release_gate.write_manifest(root, version, payload)
        identity = reset.payload_identity(json.loads(manifest.read_text(encoding="utf-8")), payload)
        return manifest, payload, identity

    def run_reset(self, args: list[str]) -> int:
        old_lab = os.environ.get(reset.LAB_ENV)
        try:
            os.environ[reset.LAB_ENV] = "1"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return reset.main(args)
        finally:
            if old_lab is None:
                os.environ.pop(reset.LAB_ENV, None)
            else:
                os.environ[reset.LAB_ENV] = old_lab

    def test_guard_blocks_without_env_and_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, _identity = self.make_package(root, "runtime-reset-guard")
            old_lab = os.environ.pop(reset.LAB_ENV, None)
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    rc = reset.main([
                        "--manifest", str(manifest),
                        "--payload", str(payload),
                        "--reset-scope", "p0_isolation_reset",
                        "--reason", "unit",
                    ])
            finally:
                if old_lab is not None:
                    os.environ[reset.LAB_ENV] = old_lab
            self.assertEqual(rc, 44)

    def test_removes_only_matching_target_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, identity = self.make_package(root, "runtime-reset-target")
            _other_manifest, _other_payload, other_identity = self.make_package(root, "runtime-reset-other", "other")
            data_root = root / "data"
            out = root / "out"
            reset.configure_updatectl_for_lab(data_root, out / "policy.json")
            state = {
                "schema": reset.updatectl.SCHEMA_STATE,
                "component": "player-runtime",
                "current": {"version": "runtime-current"},
                "previous": {"version": "runtime-previous"},
                "quarantine": [
                    {**identity, "reason": "physical_powerloss_trial"},
                    {**other_identity, "reason": "unrelated"},
                ],
            }
            reset.updatectl.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            reset.updatectl._write_state(state)
            reset.updatectl.CURRENT_LINK.parent.mkdir(parents=True, exist_ok=True)
            reset.updatectl.CURRENT_LINK.symlink_to("releases/runtime-current")
            reset.updatectl.PREVIOUS_LINK.symlink_to("releases/runtime-previous")

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_isolation_reset",
                "--reason", "unit-repeat-p0",
            ])

            self.assertEqual(rc, 0)
            after = reset.updatectl._read_state()
            entries = reset.updatectl._quarantine_entries(after)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["version"], other_identity["version"])
            self.assertEqual(reset.updatectl._read_symlink_target(reset.updatectl.CURRENT_LINK), "releases/runtime-current")
            self.assertEqual(reset.updatectl._read_symlink_target(reset.updatectl.PREVIOUS_LINK), "releases/runtime-previous")
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["removed_count"], 1)
            self.assertTrue(result["public_cli_apply_still_frozen"]["frozen"])
            self.assertTrue(result["public_cli_rollback_still_frozen"]["frozen"])
            self.assertTrue(result["public_cli_reconcile_still_frozen"]["frozen"])

    def test_fails_when_target_is_not_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, payload, _identity = self.make_package(root, "runtime-reset-absent")
            data_root = root / "data"
            out = root / "out"
            reset.configure_updatectl_for_lab(data_root, out / "policy.json")
            reset.updatectl.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            reset.updatectl._write_state({"schema": reset.updatectl.SCHEMA_STATE, "component": "player-runtime", "quarantine": []})

            rc = self.run_reset([
                "--lab-only-quarantine-reset",
                "--manifest", str(manifest),
                "--payload", str(payload),
                "--data-root", str(data_root),
                "--output-dir", str(out),
                "--reset-scope", "p0_isolation_reset",
                "--reason", "unit-repeat-p0",
            ])

            self.assertEqual(rc, 1)
            result = json.loads((out / "quarantine-reset.json").read_text(encoding="utf-8"))
            self.assertFalse(result["passed"])
            self.assertEqual(result["removed_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
