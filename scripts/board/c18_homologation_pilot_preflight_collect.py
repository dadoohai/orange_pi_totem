#!/usr/bin/env python3
"""Collect read-only C18 homologation pilot preflight state.

This collector emits the `dadooh.c18.homologation_pilot_preflight.v1` artifact
required by the pilot readiness and operational resume gates. It is intended to
run on the board immediately before a resumed pilot operation.

It does not apply, rollback, reconcile with maintenance privileges, publish,
promote stable, thaw player-runtime, fetch releases, read secrets into output,
or claim H2 readiness. The public freeze probes are only executed after a local
static guard confirms the installed updatectl still declares player-runtime as
frozen with rc=44.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import c18_coldboot_state_collect as coldboot
import c18_playback_health_collect as playback


SCHEMA = "dadooh.c18.homologation_pilot_preflight.v1"
POLICY_SCHEMA = "dadooh.totem.update.policy.v1"
DEFAULT_POLICY = Path("/data/updates/policy.json")
DEFAULT_UPDATECTL = Path("/opt/totem/bin/totem-updatectl")
DEFAULT_CONFIG = Path("/data/config/config.json")
DEFAULT_STATUS = Path("/tmp/kiosky-status.json")
DEFAULT_UPDATE_TIMER = "totem-update-agent.timer"
DEFAULT_PLAYER_SERVICE = "kiosky-player.service"
EXPECTED_DEVICE_TRACK = "c18-hwdecode"
EXPECTED_CHANNEL = "homologation"
EXPECTED_ALLOWED_COMPONENTS = ["totem-core"]
EXPECTED_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
EXPECTED_HWDEC = "v4l2request-copy"
PREFLIGHT_STAGES = {"pre_apply", "post_apply_observation"}
DEVICE_HASH_RE = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
NON_CLAIMS = (
    "this_preflight_does_not_authorize_production",
    "this_preflight_does_not_promote_stable",
    "this_preflight_does_not_enable_auto_pull",
    "this_preflight_does_not_publish_releases",
    "this_preflight_does_not_thaw_public_player_runtime",
    "this_preflight_does_not_satisfy_24h_soak",
    "this_preflight_does_not_satisfy_powerloss_17_17",
    "this_preflight_does_not_replace_h2_readiness",
    "this_preflight_does_not_apply_or_rollback_player_runtime",
    "this_preflight_does_not_run_authorized_maintenance_reconcile",
)


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json_object(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"json_read_failed:{type(exc).__name__}"
    if not isinstance(data, dict):
        return {}, "json_not_object"
    return data, None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_device_hash(raw: str) -> str | None:
    match = DEVICE_HASH_RE.fullmatch(raw)
    if not match:
        return None
    return match.group(1)


def is_sha1(raw: Any) -> bool:
    return isinstance(raw, str) and SHA1_RE.fullmatch(raw) is not None


def is_sha256(raw: Any) -> bool:
    return isinstance(raw, str) and SHA256_RE.fullmatch(raw) is not None


def run(cmd: list[str], *, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
    }
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env=env,
        check=False,
    )


def systemd_unit_state(unit: str) -> dict[str, Any]:
    enabled = run(["systemctl", "is-enabled", unit], timeout=10)
    active = run(["systemctl", "is-active", unit], timeout=10)
    return {
        "unit": unit,
        "enabled_raw": (enabled.stdout or enabled.stderr).strip(),
        "active_raw": (active.stdout or active.stderr).strip(),
        "enabled": enabled.returncode == 0 and enabled.stdout.strip() == "enabled",
        "active": active.returncode == 0 and active.stdout.strip() == "active",
    }


def load_policy(path: Path) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    data, error = read_json_object(path)
    if not path.is_file():
        blockers.append("policy_missing")
    elif error:
        blockers.append(f"policy_{error}")
    policy = {
        "path": str(path),
        "present": path.is_file(),
        "schema": data.get("schema"),
        "device_track": data.get("device_track"),
        "device_channel": data.get("device_channel"),
        "allow_prerelease": data.get("allow_prerelease"),
        "allow_downgrade": data.get("allow_downgrade"),
        "allowed_components": data.get("allowed_components"),
    }
    if policy["schema"] != POLICY_SCHEMA:
        blockers.append("policy_schema")
    if policy["device_track"] != EXPECTED_DEVICE_TRACK:
        blockers.append("policy_device_track_not_c18_hwdecode")
    if policy["device_channel"] != EXPECTED_CHANNEL:
        blockers.append("policy_not_homologation")
    if policy["allow_prerelease"] is not True:
        blockers.append("policy_allow_prerelease_not_true")
    if policy["allow_downgrade"] is not False:
        blockers.append("policy_allow_downgrade_not_false")
    if policy["allowed_components"] != EXPECTED_ALLOWED_COMPONENTS:
        blockers.append("policy_allowed_components_not_totem_core")
    return policy, blockers


def safe_summary(text: str) -> str:
    compact = " ".join(text.replace("\r", "\n").split())
    return compact[:240]


def updatectl_static_freeze_guard(updatectl: Path) -> dict[str, Any]:
    blockers: list[str] = []
    try:
        text = updatectl.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {
            "passed": False,
            "path": str(updatectl),
            "blockers": [f"updatectl_read_failed:{type(exc).__name__}"],
        }
    required = {
        "ota_frozen_components": "OTA_FROZEN_COMPONENTS",
        "player_runtime_key": '"player-runtime"',
        "rc44": "return 44",
        "apply_guard": "apply_blocked_component_frozen",
        "rollback_guard": "rollback_blocked_component_frozen",
        "reconcile_guard": "player_runtime_reconcile_guard_required",
    }
    missing = [label for label, needle in required.items() if needle not in text]
    blockers.extend(f"updatectl_static_guard_missing:{item}" for item in missing)
    return {
        "passed": not blockers,
        "path": str(updatectl),
        "blockers": blockers,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def freeze_probe(updatectl: Path, label: str, cmd: list[str]) -> dict[str, Any]:
    proc = run(cmd, timeout=20)
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return {
        "command": label,
        "returncode": proc.returncode,
        "frozen": proc.returncode == 44,
        "output_sha256": hashlib.sha256(combined.encode("utf-8")).hexdigest(),
        "summary": safe_summary(combined),
    }


def public_freeze(updatectl: Path, static_guard: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    if static_guard.get("passed") is not True:
        return {"included": False, "reason": "static_guard_failed"}, ["public_freeze_static_guard_failed"]
    probes = {
        "apply_local": [
            str(updatectl),
            "apply-local",
            "--component",
            "player-runtime",
            "/tmp/c18-player-runtime-public-freeze-probe-nonexistent.manifest.json",
        ],
        "rollback": [str(updatectl), "rollback", "--component", "player-runtime"],
        "reconcile": [str(updatectl), "reconcile", "--component", "player-runtime"],
    }
    out = {label: freeze_probe(updatectl, label, cmd) for label, cmd in probes.items()}
    for label, result in out.items():
        if result.get("returncode") != 44 or result.get("frozen") is not True:
            blockers.append(f"public_freeze_{label}_not_rc44")
    return out, blockers


def config_contract(config: Path) -> dict[str, Any]:
    data, error = read_json_object(config)
    if error:
        return {
            "config_present": config.is_file(),
            "config_read_error": error,
            "mpv_path_c18_stack": False,
        }
    mpv_path = data.get("mpv_path")
    return {
        "config_present": config.is_file(),
        "mpv_path_present": isinstance(mpv_path, str),
        "mpv_path_c18_stack": mpv_path == EXPECTED_WRAPPER,
    }


def playback_hwdec_check(config: Path, status: Path, timeout_sec: float) -> dict[str, Any]:
    try:
        ipc_path, _status_path = playback.read_config(config, status)
    except Exception as exc:
        return {
            "ipc_query_result": "error",
            "ipc_error": f"config:{type(exc).__name__}",
            "hwdec_expected_present": False,
        }
    result, error, values, elapsed_ms, _prop_errors = playback.ipc_query_many(ipc_path, timeout_sec)
    hwdec = values.get("hwdec-current") if isinstance(values, dict) else None
    return {
        "ipc_query_result": result,
        "ipc_error": error,
        "ipc_elapsed_ms": elapsed_ms,
        "hwdec_expected_present": hwdec == EXPECTED_HWDEC,
        "hwdec_unexpected_present": bool(hwdec and hwdec != EXPECTED_HWDEC),
    }


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    device_hash = normalize_device_hash(args.device_hash)
    if device_hash is None:
        blockers.append("device_hash_invalid")
    if args.stage not in PREFLIGHT_STAGES:
        blockers.append("stage_invalid")
    if not is_sha1(args.source_commit):
        blockers.append("source_commit_invalid")
    if not is_sha256(args.image_sha256):
        blockers.append("image_sha256_invalid")
    if args.expect_image_marker_sha256 and not is_sha256(args.expect_image_marker_sha256):
        blockers.append("expect_image_marker_sha256_invalid")

    policy, policy_blockers = load_policy(args.policy)
    blockers.extend(policy_blockers)
    timer = systemd_unit_state(args.update_timer)
    service = systemd_unit_state(args.player_service)
    if timer["enabled"] is not False:
        blockers.append("timer_enabled")
    if timer["active"] is not False:
        blockers.append("timer_active")
    if service["active"] is not True:
        blockers.append("service_not_active")

    static_guard = updatectl_static_freeze_guard(args.updatectl)
    blockers.extend(static_guard.get("blockers") if isinstance(static_guard.get("blockers"), list) else [])
    freeze, freeze_blockers = public_freeze(args.updatectl, static_guard)
    blockers.extend(freeze_blockers)

    image_identity = coldboot.image_identity(args.image_marker)
    image = {
        "tag": image_identity.get("image_tag"),
        "image_tag": image_identity.get("image_tag"),
        "sha256": args.image_sha256,
        "marker_sha256": image_identity.get("marker_sha256"),
        "marker_present": image_identity.get("marker_present"),
        "marker_path": image_identity.get("marker_path"),
    }
    if image["marker_present"] is not True:
        blockers.append("image_marker_missing")
    if args.expect_image_tag and image["tag"] != args.expect_image_tag:
        blockers.append("image_tag_mismatch")
    if args.expect_image_marker_sha256 and image["marker_sha256"] != args.expect_image_marker_sha256:
        blockers.append("image_marker_sha256_mismatch")

    config_checks = config_contract(args.config)
    hwdec_checks = playback_hwdec_check(args.config, args.status, args.ipc_timeout_sec)
    player_checks = {
        **config_checks,
        **hwdec_checks,
        "service_active": service["active"] is True,
    }
    if player_checks.get("mpv_path_c18_stack") is not True:
        blockers.append("mpv_path_c18_stack_missing")
    if player_checks.get("hwdec_expected_present") is not True:
        blockers.append("hwdec_expected_missing")

    passed = not blockers
    return {
        "schema": SCHEMA,
        "passed": passed,
        "result_claim": "homologation_pilot_preflight_collected" if passed else "homologation_pilot_preflight_blocked",
        "stage": args.stage,
        "collected_at_utc": utcnow(),
        "device_hash": "sha256:" + device_hash if device_hash else args.device_hash,
        "source_commit": args.source_commit,
        "policy": policy,
        "timer": {
            "enabled": timer["enabled"],
            "enabled_raw": timer["enabled_raw"],
            "active": timer["active"],
            "active_raw": timer["active_raw"],
        },
        "service": service,
        "public_freeze_static_guard": static_guard,
        "public_freeze": freeze,
        "image": image,
        "player_runtime": {
            "checks": player_checks,
        },
        "blockers": sorted(set(blockers)),
        "non_claims": list(NON_CLAIMS),
        "privacy": {
            "raw_serial_persisted": False,
            "raw_mac_persisted": False,
            "raw_ip_persisted": False,
            "raw_config_persisted": False,
            "raw_media_path_persisted": False,
        },
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--stage", choices=sorted(PREFLIGHT_STAGES), default="pre_apply")
    parser.add_argument("--device-hash", default="")
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--image-sha256", default="")
    parser.add_argument("--expect-image-tag", default="")
    parser.add_argument("--expect-image-marker-sha256", default="")
    parser.add_argument("--image-marker")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--updatectl", type=Path, default=DEFAULT_UPDATECTL)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--update-timer", default=DEFAULT_UPDATE_TIMER)
    parser.add_argument("--player-service", default=DEFAULT_PLAYER_SERVICE)
    parser.add_argument("--ipc-timeout-sec", type=float, default=0.8)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def fake_completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["fake"], returncode, stdout, stderr)


class HomologationPilotPreflightCollectSelfTest(unittest.TestCase):
    def fixture_args(self, root: Path) -> argparse.Namespace:
        policy = root / "policy.json"
        write_json(policy, {
            "schema": POLICY_SCHEMA,
            "device_track": EXPECTED_DEVICE_TRACK,
            "device_channel": EXPECTED_CHANNEL,
            "allow_prerelease": True,
            "allow_downgrade": False,
            "allowed_components": EXPECTED_ALLOWED_COMPONENTS,
        })
        marker = root / "c18-hwdecode-lab-1x-image"
        marker.write_text("image_tag=c18-hwdecode-lab-1x\n", encoding="utf-8")
        updatectl = root / "totem-updatectl"
        updatectl.write_text(
            "\n".join([
                "OTA_FROZEN_COMPONENTS = {\"player-runtime\": \"frozen\"}",
                "def cmd_apply_local():",
                "    print('apply_blocked_component_frozen')",
                "    return 44",
                "def cmd_rollback():",
                "    print('rollback_blocked_component_frozen')",
                "    return 44",
                "def cmd_reconcile():",
                "    print('player_runtime_reconcile_guard_required')",
                "    return 44",
            ]),
            encoding="utf-8",
        )
        config = root / "config.json"
        write_json(config, {"mpv_path": EXPECTED_WRAPPER, "ipc_path": str(root / "mpv.sock")})
        return argparse.Namespace(
            stage="pre_apply",
            device_hash="sha256:" + "a" * 64,
            source_commit="b" * 40,
            image_sha256="c" * 64,
            expect_image_tag="c18-hwdecode-lab-1x",
            expect_image_marker_sha256=hashlib.sha256(marker.read_bytes()).hexdigest(),
            image_marker=str(marker),
            policy=policy,
            updatectl=updatectl,
            config=config,
            status=root / "status.json",
            update_timer="totem-update-agent.timer",
            player_service="kiosky-player.service",
            ipc_timeout_sec=0.1,
        )

    def run_mock(self, cmd: list[str], *, timeout: int = 15) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["systemctl", "is-enabled"]:
            return fake_completed("disabled\n")
        if cmd[:2] == ["systemctl", "is-active"] and cmd[-1] == "totem-update-agent.timer":
            return fake_completed("inactive\n", returncode=3)
        if cmd[:2] == ["systemctl", "is-active"] and cmd[-1] == "kiosky-player.service":
            return fake_completed("active\n")
        if "apply-local" in cmd:
            return fake_completed(stderr="component_frozen_for_ota: player-runtime\n", returncode=44)
        if "rollback" in cmd:
            return fake_completed(stderr="component_frozen_for_ota: player-runtime\n", returncode=44)
        if "reconcile" in cmd:
            return fake_completed(stderr="player_runtime_reconcile_guard_required\n", returncode=44)
        return fake_completed(returncode=1)

    def test_valid_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = self.fixture_args(Path(tmp))
            with mock.patch(__name__ + ".run", side_effect=self.run_mock), mock.patch(
                "c18_playback_health_collect.ipc_query_many",
                return_value=("success", "", {"hwdec-current": EXPECTED_HWDEC}, 10, {}),
            ):
                result = evaluate(args)
        self.assertTrue(result["passed"], result["blockers"])
        self.assertEqual(result["public_freeze"]["rollback"]["returncode"], 44)
        self.assertTrue(result["player_runtime"]["checks"]["hwdec_expected_present"])

    def test_static_guard_blocks_before_freeze_probes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = self.fixture_args(Path(tmp))
            args.updatectl.write_text("def cmd_rollback():\n    return 0\n", encoding="utf-8")
            calls: list[list[str]] = []

            def capture(cmd: list[str], *, timeout: int = 15) -> subprocess.CompletedProcess[str]:
                calls.append(cmd)
                return self.run_mock(cmd, timeout=timeout)

            with mock.patch(__name__ + ".run", side_effect=capture), mock.patch(
                "c18_playback_health_collect.ipc_query_many",
                return_value=("success", "", {"hwdec-current": EXPECTED_HWDEC}, 10, {}),
            ):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn("public_freeze_static_guard_failed", result["blockers"])
        self.assertFalse(any("rollback" in cmd for cmd in calls))
        self.assertFalse(any("apply-local" in cmd for cmd in calls))

    def test_unexpected_hwdec_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = self.fixture_args(Path(tmp))
            with mock.patch(__name__ + ".run", side_effect=self.run_mock), mock.patch(
                "c18_playback_health_collect.ipc_query_many",
                return_value=("success", "", {"hwdec-current": "no"}, 10, {}),
            ):
                result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn("hwdec_expected_missing", result["blockers"])


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(HomologationPilotPreflightCollectSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    report = evaluate(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"passed={str(report['passed']).lower()} result={report['result_claim']}")
        for blocker in report["blockers"]:
            print(f"- {blocker}")
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
