#!/usr/bin/env python3
"""Create the transient production apply policy for the visual settings flow."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import tempfile
import time
import unittest
from typing import Any


SCHEMA = "dadooh-settings-apply-policy.v1"
DEFAULT_POLICY = pathlib.Path("/run/dadooh-settings/apply-policy.json")
DEFAULT_REQUEST_DIR = pathlib.Path("/run/dadooh-settings")
DEFAULT_ACTIVE_CONFIG = pathlib.Path("/data/config/config.json")
PRIVATE_VALUES_TMP = "/tmp/dadooh-c10-6-2-private/private-values.json"


def runtime_path(path: pathlib.Path, label: str) -> pathlib.Path:
    value = str(path)
    normalized = pathlib.Path(os.path.normpath(value))
    if not path.is_absolute() or normalized != path:
        raise RuntimeError(f"{label}_not_normalized")
    if not (value.startswith("/run/") or value.startswith("/tmp/")):
        raise RuntimeError(f"{label}_outside_runtime")
    if path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError(f"{label}_symlink")
    return path


def active_config_ready(path: pathlib.Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    return all(
        isinstance(data.get(key), str) and data[key].strip()
        for key in ("api_url", "api_key", "environment_id")
    )


def build_policy(active_config: pathlib.Path) -> dict[str, Any]:
    use_active = active_config_ready(active_config)
    return {
        "schema_version": SCHEMA,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "real-write",
        "private_source": "active-config" if use_active else "none",
        "private_values_path": PRIVATE_VALUES_TMP,
        "real_write_confirmed": True,
        "dry_run_confirmed": False,
        "active_config_private_source_confirmed": use_active,
        "policy_scope": "production",
        "final_image": True,
    }


def write_policy(policy_path: pathlib.Path, request_dir: pathlib.Path, active_config: pathlib.Path) -> dict[str, Any]:
    policy_path = runtime_path(policy_path, "policy_path")
    request_dir = runtime_path(request_dir, "request_dir")
    request_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    request_dir.chmod(0o700)
    payload = build_policy(active_config)
    temp_path = policy_path.with_name(f".{policy_path.name}.{os.getpid()}.tmp")
    if temp_path.exists() or temp_path.is_symlink():
        temp_path.unlink()
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.chmod(0o600)
    os.replace(temp_path, policy_path)
    policy_path.chmod(0o600)
    return payload


def clear_policy(policy_path: pathlib.Path) -> None:
    policy_path = runtime_path(policy_path, "policy_path")
    if policy_path.exists() or policy_path.is_symlink():
        policy_path.unlink()


class ProductionApplyPolicySelfTest(unittest.TestCase):
    def test_new_device_uses_qr_ready_private_source_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            payload = build_policy(root / "missing-config.json")
        self.assertEqual(payload["mode"], "real-write")
        self.assertEqual(payload["private_source"], "none")
        self.assertTrue(payload["real_write_confirmed"])
        self.assertEqual(payload["policy_scope"], "production")
        self.assertTrue(payload["final_image"])

    def test_existing_valid_config_uses_active_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = pathlib.Path(tmp) / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "api_url": "https://example.invalid",
                        "api_key": "fixture",
                        "environment_id": "environment-fixture",
                    }
                ),
                encoding="utf-8",
            )
            payload = build_policy(config)
        self.assertEqual(payload["private_source"], "active-config")
        self.assertTrue(payload["active_config_private_source_confirmed"])

    def test_invalid_config_falls_back_to_pairing_without_read_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = pathlib.Path(tmp) / "config.json"
            config.write_text("{}", encoding="utf-8")
            payload = build_policy(config)
        self.assertEqual(payload["private_source"], "none")
        self.assertFalse(payload["active_config_private_source_confirmed"])

    def test_written_policy_is_private_and_has_no_lab_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            request_dir = root / "run" / "request"
            policy_path = request_dir / "apply-policy.json"
            payload = write_policy(policy_path, request_dir, root / "missing.json")
            loaded = json.loads(policy_path.read_text(encoding="utf-8"))
            mode = policy_path.stat().st_mode & 0o777
        self.assertEqual(loaded, payload)
        self.assertEqual(mode, 0o600)
        self.assertEqual(loaded["policy_scope"], "production")
        self.assertNotIn("homologation_seed", loaded)
        self.assertNotIn("lab_only", loaded)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--clear", action="store_true")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--self-test", action="store_true")
    parser.add_argument("--policy-path", type=pathlib.Path, default=DEFAULT_POLICY)
    parser.add_argument("--request-dir", type=pathlib.Path, default=DEFAULT_REQUEST_DIR)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProductionApplyPolicySelfTest)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if args.clear:
        clear_policy(args.policy_path)
        print("policy_present=false")
        return 0
    if args.status:
        present = args.policy_path.is_file() and not args.policy_path.is_symlink()
        print(f"policy_present={str(present).lower()}")
        return 0
    payload = write_policy(args.policy_path, args.request_dir, DEFAULT_ACTIVE_CONFIG)
    print("policy_written=true")
    print(f"private_source={payload['private_source']}")
    print("policy_scope=production")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(os.sys.argv[1:]))
