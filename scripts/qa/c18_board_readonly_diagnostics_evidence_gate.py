#!/usr/bin/env python3
"""Validate C18 board read-only diagnostics evidence.

This gate admits sanitized appliance/display diagnostics into the C18 evidence
tree. It validates hashes, privacy, and non-claims only. It does not prove
playback health, power-loss, soak, H2, stable promotion, production readiness,
publish, auto-pull, or thaw.
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


SCHEMA = "dadooh.c18.board_readonly_diagnostics_evidence_gate.v1"
MANIFEST_SCHEMA = "dadooh.c18.board_readonly_diagnostics_evidence.v1"
APPLIANCE_SCHEMA = "dadooh-c7-appliance-status.v0"
APPLIANCE_GOVERNANCE_SCHEMA = "dadooh.c18.appliance_public_state.governance.v1"
DISPLAY_SCHEMA = "dadooh.c18.display_status.v1"
REQUIRED_FILES = {
    "appliance-status.json",
    "c18-display-status.json",
    "summary.txt",
}
OPTIONAL_FILES = {"README.md", "evidence-manifest.json"}
REQUIRED_RESULT_CLAIMS = {
    "read_only_appliance_public_state_collected",
    "read_only_display_status_collected",
}
REQUIRED_EVIDENCE_NON_CLAIMS = {
    "this_evidence_does_not_start_stop_restart_or_signal_player",
    "this_evidence_does_not_read_config_content_media_edid_framebuffer_journal_or_network",
    "this_evidence_does_not_validate_playback_decode_health",
    "this_evidence_does_not_replace_powerloss_or_soak",
    "this_evidence_does_not_complete_h2",
    "this_evidence_does_not_publish_promote_stable_enable_auto_pull_or_thaw",
}
REQUIRED_DISPLAY_NON_CLAIMS = {
    "this_collector_does_not_start_stop_or_restart_player",
    "this_collector_does_not_read_edid_framebuffer_media_or_config",
    "this_collector_does_not_validate_playback_decode_health",
    "this_collector_does_not_replace_h2_powerloss_or_soak",
    "this_collector_does_not_publish_or_thaw",
}
ALLOWED_DISPLAY_CLASSIFICATIONS = {
    "display_ok",
    "sink_hung_board_healthy",
    "pipeline_stalled",
    "no_sink",
    "unknown",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url", re.compile(r"https?://", re.I)),
    ("private_ip", re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")),
    ("mac", re.compile(r"\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b", re.I)),
    ("data_media_path", re.compile(r"/data/media(?:/|\b)", re.I)),
    ("data_config_path", re.compile(r"/data/config(?:/|\b)", re.I)),
    ("opt_totem_path", re.compile(r"/opt/totem(?:/|\b)", re.I)),
    ("secret_key", re.compile(r"(api[_-]?key|secret|password|passwd|senha)\s*[:=]", re.I)),
    ("bearer", re.compile(r"\bBearer\s+\S+", re.I)),
    ("network_id", re.compile(r"\b(ssid|bssid|gateway|dns|hostname|mac)\b\s*[:=]", re.I)),
)


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    if path.is_symlink():
        errors.append(f"{label}_symlink_forbidden")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{label}_json_error:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{label}_not_object")
        return {}
    return data


def is_utc_timestamp(raw: Any) -> bool:
    if not isinstance(raw, str) or not raw.endswith("Z"):
        return False
    try:
        parsed = dt.datetime.fromisoformat(raw[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.utcoffset() == dt.timedelta(0)


def validate_regular_tree(run_dir: Path, errors: list[str]) -> set[str]:
    if run_dir.is_symlink():
        errors.append("run_dir_symlink_forbidden")
        return set()
    if not run_dir.is_dir():
        errors.append("run_dir_missing")
        return set()
    files: set[str] = set()
    for path in sorted(run_dir.rglob("*")):
        rel_path = rel(path, run_dir)
        if path.is_symlink():
            errors.append(f"symlink_forbidden:{rel_path}")
            continue
        if path.is_dir():
            continue
        files.add(rel_path)
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in LEAK_PATTERNS:
            if pattern.search(text):
                errors.append(f"privacy_leak:{label}:{rel_path}")
    unexpected = sorted(files - REQUIRED_FILES - OPTIONAL_FILES)
    if unexpected:
        errors.append("unexpected_files:" + ",".join(unexpected))
    missing = sorted(REQUIRED_FILES - files)
    for name in missing:
        errors.append(f"required_file_missing:{name}")
    return files


def validate_manifest(run_dir: Path, errors: list[str]) -> dict[str, Any]:
    manifest = read_json(run_dir / "evidence-manifest.json", errors, "manifest")
    if not manifest:
        return {}
    if manifest.get("schema") != MANIFEST_SCHEMA:
        errors.append("manifest_schema")
    if not is_utc_timestamp(manifest.get("collected_at_utc")):
        errors.append("manifest_collected_at_utc")
    if not isinstance(manifest.get("repo_commit"), str) or not COMMIT_RE.fullmatch(manifest["repo_commit"]):
        errors.append("manifest_repo_commit")
    if manifest.get("collection_mode") != "assisted_ssh_read_only":
        errors.append("manifest_collection_mode")
    claims = set(manifest.get("result_claims") if isinstance(manifest.get("result_claims"), list) else [])
    if claims != REQUIRED_RESULT_CLAIMS:
        errors.append("manifest_result_claims")
    non_claims = set(manifest.get("non_claims") if isinstance(manifest.get("non_claims"), list) else [])
    for claim in sorted(REQUIRED_EVIDENCE_NON_CLAIMS - non_claims):
        errors.append(f"manifest_non_claim_missing:{claim}")
    privacy = manifest.get("privacy_scan") if isinstance(manifest.get("privacy_scan"), dict) else {}
    expected_privacy = {
        "passed": True,
        "raw_config_content_included": False,
        "raw_media_paths_included": False,
        "raw_network_identifiers_included": False,
        "raw_journal_included": False,
    }
    for key, expected in expected_privacy.items():
        if privacy.get(key) is not expected:
            errors.append(f"manifest_privacy_{key}")
    files = manifest.get("files")
    if not isinstance(files, list):
        errors.append("manifest_files_missing")
        return manifest
    declared: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            errors.append("manifest_file_entry_not_object")
            continue
        file_name = item.get("path")
        if not isinstance(file_name, str) or file_name.startswith("/") or ".." in Path(file_name).parts:
            errors.append("manifest_file_path_invalid")
            continue
        declared.add(file_name)
        path = run_dir / file_name
        if path.is_symlink():
            errors.append(f"manifest_file_symlink:{file_name}")
            continue
        if not path.is_file():
            errors.append(f"manifest_file_missing:{file_name}")
            continue
        if item.get("bytes") != path.stat().st_size:
            errors.append(f"manifest_file_bytes_mismatch:{file_name}")
        if not isinstance(item.get("sha256"), str) or not SHA256_RE.fullmatch(item["sha256"]):
            errors.append(f"manifest_file_sha256_invalid:{file_name}")
        elif sha256_file(path) != item["sha256"]:
            errors.append(f"manifest_file_sha256_mismatch:{file_name}")
    if declared != REQUIRED_FILES:
        errors.append("manifest_declared_files")
    return manifest


def validate_appliance(run_dir: Path, manifest: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    appliance = read_json(run_dir / "appliance-status.json", errors, "appliance")
    if not appliance:
        return {}
    if appliance.get("schema_version") != APPLIANCE_SCHEMA:
        errors.append("appliance_schema")
    governance = appliance.get("c18_governance") if isinstance(appliance.get("c18_governance"), dict) else {}
    expected = {
        "schema": APPLIANCE_GOVERNANCE_SCHEMA,
        "responsibility": "field-data",
        "result_claim": "read_only_appliance_public_state_collected",
        "collection_mode": "local_offline_read_only",
        "reads_config_content": False,
        "copies_raw_player_status": False,
        "copies_raw_public_status": False,
        "reads_media": False,
        "reads_network": False,
        "reads_journal": False,
        "executes_commands": False,
        "writes_only_under_tmp": True,
        "not_ota_release_payload": True,
        "not_player_runtime_release": True,
        "not_system_image_release": True,
        "not_h2_or_production_readiness": True,
    }
    for key, value in expected.items():
        if governance.get(key) != value:
            errors.append(f"appliance_governance_{key}")
    if appliance.get("privacy_scan") != "ok":
        errors.append("appliance_privacy_scan")
    if appliance.get("config_file_content_read") is not False:
        errors.append("appliance_config_content_read")
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    if summary.get("appliance_privacy_scan") != appliance.get("privacy_scan"):
        errors.append("manifest_appliance_privacy_mismatch")
    if summary.get("appliance_public_state") != appliance.get("public_state"):
        errors.append("manifest_appliance_state_mismatch")
    if summary.get("appliance_playback_state") != appliance.get("playback_state"):
        errors.append("manifest_appliance_playback_mismatch")
    if summary.get("appliance_config_content_read") is not appliance.get("config_file_content_read"):
        errors.append("manifest_appliance_config_content_mismatch")
    return appliance


def validate_display(run_dir: Path, manifest: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    display = read_json(run_dir / "c18-display-status.json", errors, "display")
    if not display:
        return {}
    if display.get("schema") != DISPLAY_SCHEMA:
        errors.append("display_schema")
    if display.get("result_claim") != "read_only_display_status_collected":
        errors.append("display_result_claim")
    if display.get("passed") is not True:
        errors.append("display_passed")
    if display.get("classification") not in ALLOWED_DISPLAY_CLASSIFICATIONS:
        errors.append("display_classification")
    policy = display.get("collection_policy") if isinstance(display.get("collection_policy"), dict) else {}
    expected_policy = {
        "read_only": True,
        "reads_edid": False,
        "reads_framebuffer": False,
        "reads_media": False,
        "reads_config": False,
        "uses_network": False,
        "mutates_player": False,
    }
    for key, value in expected_policy.items():
        if policy.get(key) is not value:
            errors.append(f"display_policy_{key}")
    non_claims = set(display.get("non_claims") if isinstance(display.get("non_claims"), list) else [])
    for claim in sorted(REQUIRED_DISPLAY_NON_CLAIMS - non_claims):
        errors.append(f"display_non_claim_missing:{claim}")
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    if summary.get("display_classification") != display.get("classification"):
        errors.append("manifest_display_classification_mismatch")
    if summary.get("display_visible_state") != display.get("visible_state"):
        errors.append("manifest_display_visible_state_mismatch")
    return display


def evaluate(run_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    run_dir = run_dir.resolve()
    validate_regular_tree(run_dir, errors)
    manifest = validate_manifest(run_dir, errors)
    validate_appliance(run_dir, manifest, errors)
    validate_display(run_dir, manifest, errors)
    return {
        "schema": SCHEMA,
        "run_dir": str(run_dir),
        "passed": not errors,
        "blockers": sorted(set(errors)),
        "result_claim": "board_readonly_diagnostics_evidence_accepted" if not errors else "board_readonly_diagnostics_evidence_rejected",
        "non_claims": [
            "this_gate_does_not_execute_board_commands_or_ssh",
            "this_gate_does_not_validate_playback_decode_health",
            "this_gate_does_not_replace_powerloss_or_soak",
            "this_gate_does_not_complete_h2",
            "this_gate_does_not_publish_promote_stable_enable_auto_pull_or_thaw",
        ],
    }


def valid_fixture(root: Path) -> Path:
    run = root / "run"
    appliance = {
        "schema_version": APPLIANCE_SCHEMA,
        "c18_governance": {
            "schema": APPLIANCE_GOVERNANCE_SCHEMA,
            "responsibility": "field-data",
            "result_claim": "read_only_appliance_public_state_collected",
            "collection_mode": "local_offline_read_only",
            "reads_config_content": False,
            "copies_raw_player_status": False,
            "copies_raw_public_status": False,
            "reads_media": False,
            "reads_network": False,
            "reads_journal": False,
            "executes_commands": False,
            "writes_only_under_tmp": True,
            "not_ota_release_payload": True,
            "not_player_runtime_release": True,
            "not_system_image_release": True,
            "not_h2_or_production_readiness": True,
        },
        "privacy_scan": "ok",
        "public_state": "player_running",
        "playback_state": "playing",
        "config_file_content_read": False,
    }
    display = {
        "schema": DISPLAY_SCHEMA,
        "passed": True,
        "result_claim": "read_only_display_status_collected",
        "classification": "unknown",
        "visible_state": "unknown",
        "collection_policy": {
            "read_only": True,
            "reads_edid": False,
            "reads_framebuffer": False,
            "reads_media": False,
            "reads_config": False,
            "uses_network": False,
            "mutates_player": False,
        },
        "non_claims": sorted(REQUIRED_DISPLAY_NON_CLAIMS),
    }
    write_json(run / "appliance-status.json", appliance)
    write_json(run / "c18-display-status.json", display)
    (run / "summary.txt").write_text("privacy_scan: ok\nconfig_file_content_read: false\n", encoding="utf-8")
    files = []
    for name in sorted(REQUIRED_FILES):
        path = run / name
        files.append({"path": name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(run / "evidence-manifest.json", {
        "schema": MANIFEST_SCHEMA,
        "collected_at_utc": "2026-06-12T18:37:25Z",
        "repo_commit": "a" * 40,
        "collection_mode": "assisted_ssh_read_only",
        "result_claims": sorted(REQUIRED_RESULT_CLAIMS),
        "summary": {
            "appliance_privacy_scan": "ok",
            "appliance_public_state": "player_running",
            "appliance_playback_state": "playing",
            "appliance_config_content_read": False,
            "display_classification": "unknown",
            "display_visible_state": "unknown",
        },
        "files": files,
        "privacy_scan": {
            "passed": True,
            "raw_config_content_included": False,
            "raw_media_paths_included": False,
            "raw_network_identifiers_included": False,
            "raw_journal_included": False,
        },
        "non_claims": sorted(REQUIRED_EVIDENCE_NON_CLAIMS),
    })
    return run


class BoardReadonlyDiagnosticsEvidenceGateSelfTest(unittest.TestCase):
    def test_valid_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate(valid_fixture(Path(tmp)))
        self.assertTrue(result["passed"], result["blockers"])

    def test_privacy_leak_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = valid_fixture(Path(tmp))
            (run / "summary.txt").write_text("bad=https://private.invalid\n", encoding="utf-8")
            result = evaluate(run)
        self.assertFalse(result["passed"])
        self.assertIn("privacy_leak:url:summary.txt", result["blockers"])

    def test_manifest_hash_mismatch_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = valid_fixture(Path(tmp))
            data = json.loads((run / "evidence-manifest.json").read_text(encoding="utf-8"))
            data["files"][0]["sha256"] = "0" * 64
            write_json(run / "evidence-manifest.json", data)
            result = evaluate(run)
        self.assertFalse(result["passed"])
        self.assertTrue(any(item.startswith("manifest_file_sha256_mismatch:") for item in result["blockers"]))

    def test_h2_claim_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = valid_fixture(Path(tmp))
            data = json.loads((run / "evidence-manifest.json").read_text(encoding="utf-8"))
            data["non_claims"].remove("this_evidence_does_not_complete_h2")
            write_json(run / "evidence-manifest.json", data)
            result = evaluate(run)
        self.assertFalse(result["passed"])
        self.assertIn("manifest_non_claim_missing:this_evidence_does_not_complete_h2", result["blockers"])

    def test_config_content_read_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = valid_fixture(Path(tmp))
            data = json.loads((run / "appliance-status.json").read_text(encoding="utf-8"))
            data["config_file_content_read"] = True
            write_json(run / "appliance-status.json", data)
            result = evaluate(run)
        self.assertFalse(result["passed"])
        self.assertIn("appliance_config_content_read", result["blockers"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(BoardReadonlyDiagnosticsEvidenceGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if args.run_dir is None:
        print("error: --run-dir is required unless --self-test is used", file=sys.stderr)
        return 2
    result = evaluate(args.run_dir)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} result_claim={result['result_claim']}")
        for blocker in result["blockers"]:
            print(f"blocker={blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
