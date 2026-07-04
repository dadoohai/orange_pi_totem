#!/usr/bin/env python3
"""Validate C18 player-runtime public thaw activation readiness.

This gate is the bridge between H2/stable/thaw authorization evidence and any
later operational execution. It does not publish releases, fetch assets, mutate
a board, enable auto-pull, or flip the updater freeze by itself.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from c18_player_runtime_thaw_decision_gate import evaluate as evaluate_thaw_decision


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "dadooh.c18.player_runtime.public_thaw_activation_gate.v1"
H2_SCHEMA = "dadooh.c18.player_runtime.h2_readiness.v1"
THAW_SCHEMA = "dadooh.c18.player_runtime.thaw_decision.v1"
STABLE_SCHEMA = "dadooh.c18.stable_promotion.v1"
MANIFEST_SCHEMA = "dadooh.totem.update.v1"
RELEASE_GATE_SCHEMA = "dadooh.c18.player_runtime.release_gate.v1"
COMPONENT = "player-runtime"
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_H2_CHECKS = (
    "h1_decisive_bundle",
    "player_runtime_release_gate",
    "full_physical_powerloss_matrix",
    "soak_endurance_24h",
    "stable_promotion_authorization",
    "server_side_publish_governance",
    "server_side_current_snapshot",
    "explicit_operator_thaw_decision",
    "repo_clean",
    "tracked_inputs",
)
NON_CLAIMS = (
    "this_gate_does_not_publish_releases",
    "this_gate_does_not_fetch_releases",
    "this_gate_does_not_enable_auto_pull",
    "this_gate_does_not_execute_public_thaw",
    "this_gate_does_not_override_freeze_rc_44_by_itself",
)


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_json(path: Path, blockers: list[str], label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append(f"{label}_json_error:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        blockers.append(f"{label}_json_not_object")
        return {}
    return data


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def is_git_sha(value: Any) -> bool:
    return isinstance(value, str) and GIT_SHA_RE.fullmatch(value) is not None


def parse_utc(value: str | None) -> dt.datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    return parsed.astimezone(dt.timezone.utc)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def normalise_path(path: Path) -> Path:
    return path.resolve(strict=False)


def recorded_path_matches(recorded: Any, actual: Path) -> bool:
    if not isinstance(recorded, str) or not recorded:
        return False
    recorded_path = Path(recorded)
    if not recorded_path.is_absolute():
        recorded_path = REPO_ROOT / recorded_path
    return normalise_path(recorded_path) == normalise_path(actual)


def require_existing_file(path: Path | None, blockers: list[str], label: str) -> bool:
    if path is None:
        blockers.append(f"{label}_missing")
        return False
    if path.is_symlink() or not path.is_file():
        blockers.append(f"{label}_missing_or_symlink")
        return False
    return True


def compare_hash(blockers: list[str], label: str, path: Path, expected: Any) -> None:
    if not is_sha256(expected):
        blockers.append(f"{label}_expected_sha256_missing_or_invalid")
        return
    actual = sha256_file(path)
    if actual != expected:
        blockers.append(f"{label}_sha256_mismatch")


def target_from_h2(h2: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    thaw = h2.get("checks", {}).get("explicit_operator_thaw_decision", {})
    target = thaw.get("expected_target") if isinstance(thaw, dict) else {}
    if not isinstance(target, dict):
        return {}, ["h2_thaw_expected_target_missing"]
    package_version = target.get("package_version")
    source_commit = target.get("source_commit")
    payload_sha256 = target.get("payload_sha256")
    if not isinstance(package_version, str) or not package_version:
        errors.append("h2_target_package_version_missing")
    if not is_git_sha(source_commit):
        errors.append("h2_target_source_commit_missing_or_invalid")
    if not is_sha256(payload_sha256):
        errors.append("h2_target_payload_sha256_missing_or_invalid")
    if errors:
        return {}, errors
    return {
        "package_version": package_version,
        "source_commit": source_commit,
        "payload_sha256": payload_sha256,
    }, []


def validate_h2(
    h2: dict[str, Any],
    *,
    h2_path: Path,
    stable_path: Path,
    thaw_path: Path,
    release_gate_path: Path,
    server_side_path: Path,
    blockers: list[str],
) -> dict[str, Any]:
    if h2.get("schema") != H2_SCHEMA:
        blockers.append("h2_schema")
    if h2.get("passed") is not True:
        blockers.append("h2_not_passed")
    if h2.get("result_claim") != "h2_readiness_all_required_evidence_present":
        blockers.append("h2_result_claim_not_ready")
    if h2.get("blockers") not in ([], None):
        blockers.append("h2_has_blockers")
    checks = h2.get("checks")
    if not isinstance(checks, dict):
        blockers.append("h2_checks_missing")
        return {}
    for name in REQUIRED_H2_CHECKS:
        check = checks.get(name)
        if not isinstance(check, dict):
            blockers.append(f"h2_check_missing:{name}")
        elif check.get("passed") is not True:
            blockers.append(f"h2_check_not_passed:{name}")

    soak = checks.get("soak_endurance_24h") if isinstance(checks.get("soak_endurance_24h"), dict) else {}
    if soak.get("clean_soak_passed") is not True and soak.get("accepted_by_exception") is not True:
        blockers.append("h2_soak_not_clean_or_exception_accepted")

    thaw = checks.get("explicit_operator_thaw_decision") if isinstance(checks.get("explicit_operator_thaw_decision"), dict) else {}
    if not recorded_path_matches(thaw.get("evidence_path"), thaw_path):
        blockers.append("h2_thaw_decision_path_mismatch")
    compare_hash(blockers, "h2_thaw_decision", thaw_path, thaw.get("evidence_sha256"))

    stable = checks.get("stable_promotion_authorization") if isinstance(checks.get("stable_promotion_authorization"), dict) else {}
    if not recorded_path_matches(stable.get("evidence_path"), stable_path):
        blockers.append("h2_stable_promotion_path_mismatch")

    release = checks.get("player_runtime_release_gate") if isinstance(checks.get("player_runtime_release_gate"), dict) else {}
    if not recorded_path_matches(release.get("evidence_path"), release_gate_path):
        blockers.append("h2_release_gate_path_mismatch")

    server = checks.get("server_side_publish_governance") if isinstance(checks.get("server_side_publish_governance"), dict) else {}
    if not recorded_path_matches(server.get("evidence_path"), server_side_path):
        blockers.append("h2_server_side_evidence_path_mismatch")

    target, target_errors = target_from_h2(h2)
    blockers.extend(target_errors)
    return target


def validate_manifest_payload_release_gate(
    *,
    manifest_path: Path,
    payload_path: Path,
    release_gate_path: Path,
    target: dict[str, str],
    blockers: list[str],
) -> dict[str, Any]:
    manifest = read_json(manifest_path, blockers, "manifest")
    release_gate = read_json(release_gate_path, blockers, "release_gate")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        blockers.append("manifest_schema")
    if manifest.get("component") != COMPONENT:
        blockers.append("manifest_component_not_player_runtime")
    if manifest.get("channel") != "homologation":
        blockers.append("manifest_channel_not_homologation_carrier")
    if manifest.get("version") != target.get("package_version"):
        blockers.append("manifest_version_target_mismatch")
    if manifest.get("source_commit") != target.get("source_commit"):
        blockers.append("manifest_source_commit_target_mismatch")
    if manifest.get("payload_sha256") != target.get("payload_sha256"):
        blockers.append("manifest_payload_sha256_target_mismatch")
    if manifest.get("source_dirty") is not False:
        blockers.append("manifest_source_dirty_not_false")
    compare_hash(blockers, "payload", payload_path, manifest.get("payload_sha256"))

    if release_gate.get("schema") != RELEASE_GATE_SCHEMA:
        blockers.append("release_gate_schema")
    if release_gate.get("passed") is not True:
        blockers.append("release_gate_not_passed")
    package = release_gate.get("package") if isinstance(release_gate.get("package"), dict) else {}
    if package.get("component") != COMPONENT:
        blockers.append("release_gate_package_component")
    if package.get("version") is not None and package.get("version") != target.get("package_version"):
        blockers.append("release_gate_package_version_target_mismatch")
    if package.get("manifest") not in (None, manifest_path.name):
        blockers.append("release_gate_manifest_name_mismatch")
    if package.get("payload") not in (None, payload_path.name):
        blockers.append("release_gate_payload_name_mismatch")
    if package.get("source_commit") != target.get("source_commit"):
        blockers.append("release_gate_source_commit_target_mismatch")
    if package.get("payload_sha256") != target.get("payload_sha256"):
        blockers.append("release_gate_payload_sha256_target_mismatch")
    if package.get("channel") != "homologation":
        blockers.append("release_gate_channel_not_homologation_carrier")
    return manifest


def validate_stable_and_thaw(
    *,
    stable_path: Path,
    thaw_path: Path,
    h2: dict[str, Any],
    target: dict[str, str],
    now_utc: dt.datetime,
    blockers: list[str],
) -> dict[str, Any]:
    stable = read_json(stable_path, blockers, "stable_promotion")
    thaw = read_json(thaw_path, blockers, "thaw_decision")
    if stable.get("schema") != STABLE_SCHEMA:
        blockers.append("stable_promotion_schema")
    if stable.get("component") != COMPONENT:
        blockers.append("stable_promotion_component_not_player_runtime")
    if stable.get("channel") != "stable":
        blockers.append("stable_promotion_channel_not_stable")
    if stable.get("approved") is not True:
        blockers.append("stable_promotion_not_approved")
    if stable.get("auto_pull_enabled") is not False:
        blockers.append("stable_promotion_auto_pull_enabled")
    if stable.get("public_player_runtime_thaw") is not False:
        blockers.append("stable_promotion_public_thaw_claimed")

    if thaw.get("schema") != THAW_SCHEMA:
        blockers.append("thaw_decision_schema")
    if thaw.get("target_package_version") != target.get("package_version"):
        blockers.append("thaw_decision_target_package_version_mismatch")
    if thaw.get("target_source_commit") != target.get("source_commit"):
        blockers.append("thaw_decision_target_source_commit_mismatch")
    if thaw.get("target_payload_sha256") != target.get("payload_sha256"):
        blockers.append("thaw_decision_target_payload_sha256_mismatch")

    thaw_check = h2.get("checks", {}).get("explicit_operator_thaw_decision", {})
    gate_result = thaw_check.get("gate_result") if isinstance(thaw_check, dict) else {}
    expected_hashes = gate_result.get("expected_hashes") if isinstance(gate_result, dict) else {}
    if not isinstance(expected_hashes, dict):
        expected_hashes = {}
    compare_hash(blockers, "stable_promotion", stable_path, expected_hashes.get("stable_promotion_evidence_sha256"))
    thaw_gate = evaluate_thaw_decision(
        thaw_path,
        expected_hashes={k: str(v) for k, v in expected_hashes.items() if isinstance(v, str)},
        require_expected_hashes=True,
        expected_package_version=target.get("package_version"),
        expected_source_commit=target.get("source_commit"),
        expected_payload_sha256=target.get("payload_sha256"),
        now_utc=now_utc,
    )
    if thaw_gate.get("passed") is not True:
        blockers.extend(f"thaw_decision_gate:{item}" for item in thaw_gate.get("blockers", []))
    return {
        "stable_promotion_sha256": sha256_file(stable_path),
        "thaw_decision_sha256": sha256_file(thaw_path),
        "thaw_window": thaw.get("window") if isinstance(thaw.get("window"), dict) else None,
        "thaw_gate": thaw_gate,
    }


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    paths = {
        "h2_readiness": args.h2_readiness,
        "stable_promotion": args.stable_promotion_evidence,
        "operator_thaw_decision": args.operator_thaw_decision,
        "release_gate": args.release_gate_summary,
        "server_side_evidence": args.server_side_evidence,
        "manifest": args.manifest,
        "payload": args.payload,
    }
    for label, path in paths.items():
        require_existing_file(path, blockers, label)
    now = parse_utc(args.now_utc) if args.now_utc else utc_now()
    if now is None:
        blockers.append("now_utc_invalid")
        now = utc_now()
    if blockers:
        return {
            "schema": SCHEMA,
            "passed": False,
            "result_claim": "public_thaw_activation_blocked",
            "blockers": blockers,
            "non_claims": list(NON_CLAIMS),
        }

    h2 = read_json(args.h2_readiness, blockers, "h2_readiness")
    target = validate_h2(
        h2,
        h2_path=args.h2_readiness,
        stable_path=args.stable_promotion_evidence,
        thaw_path=args.operator_thaw_decision,
        release_gate_path=args.release_gate_summary,
        server_side_path=args.server_side_evidence,
        blockers=blockers,
    )
    if not target:
        target = {}
    manifest = validate_manifest_payload_release_gate(
        manifest_path=args.manifest,
        payload_path=args.payload,
        release_gate_path=args.release_gate_summary,
        target=target,
        blockers=blockers,
    )
    decision = validate_stable_and_thaw(
        stable_path=args.stable_promotion_evidence,
        thaw_path=args.operator_thaw_decision,
        h2=h2,
        target=target,
        now_utc=now,
        blockers=blockers,
    )
    return {
        "schema": SCHEMA,
        "passed": not blockers,
        "result_claim": "public_thaw_activation_ready" if not blockers else "public_thaw_activation_blocked",
        "blockers": blockers,
        "target": {
            "component": COMPONENT,
            "package_version": target.get("package_version"),
            "source_commit": target.get("source_commit"),
            "payload_sha256": target.get("payload_sha256"),
            "manifest_channel": manifest.get("channel"),
            "stable_promotion_channel": "stable",
        },
        "activation_state": {
            "h2_readiness_passed": h2.get("passed") is True,
            "stable_promotion_validated": "stable_promotion_schema" not in blockers,
            "thaw_decision_validated": decision.get("thaw_gate", {}).get("passed") is True,
            "clean_soak_passed": h2.get("checks", {}).get("soak_endurance_24h", {}).get("clean_soak_passed"),
            "accepted_by_soak_exception": h2.get("checks", {}).get("soak_endurance_24h", {}).get("accepted_by_exception"),
            "publish_executed": False,
            "auto_pull_enabled": False,
            "public_thaw_executed": False,
        },
        "inputs": {label: str(path) for label, path in paths.items()},
        "input_hashes": {
            label: sha256_file(path)
            for label, path in paths.items()
            if path is not None and path.is_file()
        },
        "evaluated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "thaw_window": decision.get("thaw_window"),
        "non_claims": list(NON_CLAIMS),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_fixture(root: Path, *, active: bool = True, tamper_payload: bool = False) -> argparse.Namespace:
    stable = root / "stable.json"
    write_json(stable, {
        "schema": STABLE_SCHEMA,
        "component": COMPONENT,
        "channel": "stable",
        "approved": True,
        "auto_pull_enabled": False,
        "public_player_runtime_thaw": False,
    })
    stable_sha = sha256_file(stable)
    hashes = {
        "h1_release_gate_sha256": "1" * 64,
        "release_gate_sha256": "2" * 64,
        "powerloss_matrix_sha256": "3" * 64,
        "soak_summary_sha256": "4" * 64,
        "server_side_evidence_sha256": "5" * 64,
        "server_side_current_snapshot_sha256": "6" * 64,
        "server_side_trust_anchor_evidence_sha256": "7" * 64,
        "stable_promotion_evidence_sha256": stable_sha,
    }
    now = dt.datetime(2026, 7, 4, 22, 0, tzinfo=dt.timezone.utc)
    if active:
        start = "2026-07-04T21:00:00Z"
        end = "2026-07-05T00:59:00Z"
        now_raw = "2026-07-04T22:00:00Z"
    else:
        start = "2026-07-04T18:00:00Z"
        end = "2026-07-04T20:00:00Z"
        now_raw = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    target = {
        "package_version": "c18.player-runtime-homolog-test-abcdef0",
        "source_commit": "a" * 40,
        "payload_sha256": "b" * 64,
    }
    thaw = root / "thaw.json"
    thaw_payload = {
        "schema": THAW_SCHEMA,
        "component": COMPONENT,
        "channel": "stable",
        "approved": True,
        "acknowledges_h2_evidence": True,
        "explicit_operator_decision": True,
        "rollback_ready": True,
        "auto_pull_enabled": False,
        "thaw_execution_performed": False,
        "operator": "operator",
        "rollback_owner": "rollback",
        "target_package_version": target["package_version"],
        "target_source_commit": target["source_commit"],
        "target_payload_sha256": target["payload_sha256"],
        "window": {"start_utc": start, "end_utc": end},
        "non_claims": [
            "this_decision_does_not_execute_thaw",
            "this_decision_does_not_publish_releases",
            "this_decision_does_not_enable_auto_pull",
            "this_decision_does_not_override_freeze_rc_44_by_itself",
            "this_decision_requires_h2_green",
        ],
        **hashes,
    }
    write_json(thaw, thaw_payload)
    thaw_sha = sha256_file(thaw)
    manifest = root / f"dadooh-{COMPONENT}-{target['package_version']}.manifest.json"
    payload = root / f"dadooh-{COMPONENT}-{target['package_version']}.tar.gz"
    payload.write_bytes(b"payload" + (b"tamper" if tamper_payload else b""))
    target["payload_sha256"] = sha256_file(payload)
    thaw_payload["target_payload_sha256"] = target["payload_sha256"]
    write_json(thaw, thaw_payload)
    thaw_sha = sha256_file(thaw)
    write_json(manifest, {
        "schema": MANIFEST_SCHEMA,
        "component": COMPONENT,
        "version": target["package_version"],
        "channel": "homologation",
        "created_at_utc": "2026-07-04T21:00:00Z",
        "source_commit": target["source_commit"],
        "source_dirty": False,
        "payload": payload.name,
        "payload_sha256": target["payload_sha256"],
        "requires": {},
    })
    release_gate = root / "release-gate.json"
    write_json(release_gate, {
        "schema": RELEASE_GATE_SCHEMA,
        "passed": True,
        "package": {
            "component": COMPONENT,
            "version": target["package_version"],
            "channel": "homologation",
            "source_commit": target["source_commit"],
            "payload_sha256": target["payload_sha256"],
        },
    })
    server = root / "server-side.json"
    write_json(server, {"schema": "server", "passed": True})
    h2 = root / "h2.json"
    checks = {name: {"passed": True, "blockers": []} for name in REQUIRED_H2_CHECKS}
    checks["soak_endurance_24h"].update({"clean_soak_passed": False, "accepted_by_exception": True})
    checks["explicit_operator_thaw_decision"].update({
        "evidence_path": str(thaw),
        "evidence_sha256": thaw_sha,
        "expected_target": target,
        "gate_result": {
            "passed": True,
            "expected_hashes": hashes,
        },
    })
    checks["stable_promotion_authorization"].update({"evidence_path": str(stable)})
    checks["player_runtime_release_gate"].update({"evidence_path": str(release_gate)})
    checks["server_side_publish_governance"].update({"evidence_path": str(server)})
    write_json(h2, {
        "schema": H2_SCHEMA,
        "passed": True,
        "result_claim": "h2_readiness_all_required_evidence_present",
        "blockers": [],
        "checks": checks,
    })
    return argparse.Namespace(
        h2_readiness=h2,
        stable_promotion_evidence=stable,
        operator_thaw_decision=thaw,
        release_gate_summary=release_gate,
        server_side_evidence=server,
        manifest=manifest,
        payload=payload,
        now_utc=now_raw,
    )


class PublicThawActivationGateSelfTest(unittest.TestCase):
    def test_complete_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate(build_fixture(Path(tmp)))
        self.assertTrue(result["passed"], result["blockers"])
        self.assertEqual(result["result_claim"], "public_thaw_activation_ready")
        self.assertFalse(result["activation_state"]["public_thaw_executed"])

    def test_missing_inputs_default_deny(self) -> None:
        args = argparse.Namespace(
            h2_readiness=None,
            stable_promotion_evidence=None,
            operator_thaw_decision=None,
            release_gate_summary=None,
            server_side_evidence=None,
            manifest=None,
            payload=None,
            now_utc=None,
        )
        result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn("h2_readiness_missing", result["blockers"])

    def test_inactive_thaw_window_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate(build_fixture(Path(tmp), active=False))
        self.assertFalse(result["passed"])
        self.assertIn("thaw_decision_gate:thaw_decision_window_inactive", result["blockers"])

    def test_tampered_payload_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = build_fixture(Path(tmp))
            args.payload.write_bytes(b"tampered")
            result = evaluate(args)
        self.assertFalse(result["passed"])
        self.assertIn("payload_sha256_mismatch", result["blockers"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h2-readiness", type=Path)
    parser.add_argument("--stable-promotion-evidence", type=Path)
    parser.add_argument("--operator-thaw-decision", type=Path)
    parser.add_argument("--release-gate-summary", type=Path)
    parser.add_argument("--server-side-evidence", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--now-utc")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(PublicThawActivationGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = evaluate(args)
    if args.json or True:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("passed") is True else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
