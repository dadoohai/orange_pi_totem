#!/usr/bin/env python3
"""Validate sanitized C18 playback incident evidence.

This is an admissibility and pilot-hold gate for bundles produced from
``c18_playback_incident_collect.py``. A valid bundle can still hold pilot
readiness. This gate does not claim root cause, playback readiness, public thaw,
stable promotion, or production readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.playback.incident_evidence_gate.v1"
INCIDENT_SCHEMA = "dadooh.c18.playback.incident.v1"
PLAYBACK_SCHEMA = "dadooh.c18.playback.deep_health.v1"
MANIFEST_SCHEMA = "dadooh.c18.playback.incident_evidence_manifest.v1"

ALLOWED_EVENTS = {"loop_entered", "loop_recovered", "loop_reentered", "startup_screen_seen", "service_reset_seen"}
REQUIRED_NON_CLAIMS = {
    "root_cause_proven_without_log_review",
    "production_readiness",
    "stable_promotion",
    "public_player_runtime_thaw",
}
REQUIRED_DEEP_HEALTH_FILES = (
    "playback-deep-health-public.json",
    "playback-samples.tsv",
    "status-samples.ndjson",
    "deep-health-systemd.json",
    "deep-health-process.json",
    "deep-health-kernel.json",
    "deep-health-player-counters.json",
)
HOLD_SIGNATURE_RE = re.compile(
    r"media_load_failed|Failed to load media|MPV IPC|Restarting MPV|"
    r"panfrost|drm|gpu|mmc|EXT4|thermal|oom|hung|reset",
    re.I,
)
LEAK_PATTERNS = (
    ("url", re.compile(r"https?://", re.I)),
    ("private_ip", re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")),
    ("mac", re.compile(r"\b[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}\b")),
    ("data_media_path", re.compile(r"/data/media\b")),
    ("data_config_path", re.compile(r"/data/config\b")),
    ("secret", re.compile(r"(github_pat_|gh[opsu]_|Bearer\s+\S+|api[_-]?key\s*[:=]|token\s*[:=]|password\s*[:=])", re.I)),
)
FORBIDDEN_SUFFIXES = (".tgz", ".tar.gz", ".log", ".key", ".token", ".secret")
FORBIDDEN_DIRS = {"raw", "runtime", "state", "media_cache"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


def validate_manifest(run_dir: Path, errors: list[str]) -> dict[str, Any]:
    manifest_path = run_dir / "evidence-manifest.json"
    if not manifest_path.exists():
        errors.append("manifest_missing")
        return {}
    manifest = read_json(manifest_path, errors, "manifest")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        errors.append("manifest_schema")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        errors.append("manifest_files_missing")
        return manifest
    present = {rel(path, run_dir): path for path in run_dir.rglob("*") if path.is_file() and not path.is_symlink()}
    declared: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("file"), str):
            errors.append("manifest_file_entry_invalid")
            continue
        file_name = item["file"]
        declared.add(file_name)
        path = present.get(file_name)
        if path is None:
            errors.append(f"manifest_file_missing:{file_name}")
            continue
        if item.get("bytes") != path.stat().st_size:
            errors.append(f"manifest_file_size_mismatch:{file_name}")
        if not isinstance(item.get("sha256"), str) or not SHA256_RE.fullmatch(item["sha256"]):
            errors.append(f"manifest_file_sha256_invalid:{file_name}")
        elif sha256_file(path) != item["sha256"]:
            errors.append(f"manifest_file_sha256_mismatch:{file_name}")
    undeclared = sorted(set(present) - declared - {"evidence-manifest.json"})
    if undeclared:
        errors.append("manifest_undeclared_files")
    return manifest


def leak_scan(run_dir: Path, errors: list[str]) -> None:
    for path in run_dir.rglob("*"):
        rel_path = rel(path, run_dir)
        if path.is_symlink():
            errors.append(f"symlink_forbidden:{rel_path}")
            continue
        if path.is_dir():
            if path.name in FORBIDDEN_DIRS:
                errors.append(f"forbidden_dir:{rel_path}")
            continue
        if any(rel_path.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
            errors.append(f"forbidden_suffix:{rel_path}")
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in LEAK_PATTERNS:
            if pattern.search(text):
                errors.append(f"leak:{label}:{rel_path}")


def parse_events(run_dir: Path, errors: list[str]) -> list[str]:
    path = run_dir / "operator-events.tsv"
    if path.is_symlink():
        errors.append("operator_events_symlink_forbidden")
        return []
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    events: list[str] = []
    if not lines or lines[0].strip() != "utc\tevent\tnote_hash":
        errors.append("operator_events_header")
        return events
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) != 3:
            errors.append("operator_events_row_invalid")
            continue
        event = parts[1]
        if event not in ALLOWED_EVENTS:
            errors.append(f"operator_event_invalid:{event}")
        events.append(event)
    return events


def validate_deep_health(run_dir: Path, run_id: str, run_summary: dict[str, Any], errors: list[str]) -> tuple[dict[str, Any], list[str]]:
    health_dir = run_dir / "runs" / run_id / "deep-health"
    if health_dir.is_symlink():
        errors.append(f"deep_health_dir_symlink_forbidden:{run_id}")
        return {}, []
    for file_name in REQUIRED_DEEP_HEALTH_FILES:
        path = health_dir / file_name
        if path.is_symlink():
            errors.append(f"deep_health_file_symlink_forbidden:{run_id}:{file_name}")
        elif not path.is_file():
            errors.append(f"deep_health_file_missing:{run_id}:{file_name}")
    health = read_json(health_dir / "playback-deep-health-public.json", errors, f"deep_health:{run_id}")
    if health.get("schema") != PLAYBACK_SCHEMA:
        errors.append(f"deep_health_schema:{run_id}")
    summary_health = run_summary.get("deep_health") if isinstance(run_summary.get("deep_health"), dict) else {}
    if summary_health.get("passed") != health.get("passed"):
        errors.append(f"deep_health_passed_mismatch:{run_id}")
    if summary_health.get("failure_reasons") != health.get("failure_reasons"):
        errors.append(f"deep_health_failure_reasons_mismatch:{run_id}")
    return health, health.get("failure_reasons") if isinstance(health.get("failure_reasons"), list) else []


def validate_runs(run_dir: Path, top: dict[str, Any], errors: list[str]) -> tuple[list[str], list[str], list[str]]:
    runs_dir = run_dir / "runs"
    if runs_dir.is_symlink():
        errors.append("runs_dir_symlink_forbidden")
        return [], [], []
    if not runs_dir.is_dir():
        errors.append("runs_dir_missing")
        return [], [], []
    symlink_runs = sorted(path.name for path in runs_dir.iterdir() if path.is_symlink())
    for run_id in symlink_runs:
        errors.append(f"run_dir_symlink_forbidden:{run_id}")
    actual_runs = sorted(path.name for path in runs_dir.iterdir() if path.is_dir() and not path.is_symlink())
    if not actual_runs:
        errors.append("runs_empty")
    if sorted(top.get("runs") if isinstance(top.get("runs"), list) else []) != actual_runs:
        errors.append("top_runs_mismatch")
    hold_reasons: list[str] = []
    signal_reasons: list[str] = []
    for run_id in actual_runs:
        run_summary = read_json(runs_dir / run_id / "incident-summary.json", errors, f"run_summary:{run_id}")
        if run_summary.get("schema") != INCIDENT_SCHEMA:
            errors.append(f"run_summary_schema:{run_id}")
        if run_summary.get("run_id") != run_id:
            errors.append(f"run_summary_id_mismatch:{run_id}")
        if run_summary.get("result_claim") != "read_only_playback_incident_evidence_collected":
            errors.append(f"run_result_claim:{run_id}")
        non_claims = set(run_summary.get("non_claims") if isinstance(run_summary.get("non_claims"), list) else [])
        if not REQUIRED_NON_CLAIMS.issubset(non_claims):
            errors.append(f"run_non_claims_missing:{run_id}")
        health, failure_reasons = validate_deep_health(run_dir, run_id, run_summary, errors)
        signal_reasons.extend(str(reason) for reason in failure_reasons)
        if health.get("passed") is not True:
            hold_reasons.append(f"deep_health_failed:{run_id}")
        signatures_path = runs_dir / run_id / "journal-signatures.ndjson"
        if signatures_path.is_symlink():
            errors.append(f"journal_signatures_symlink_forbidden:{run_id}")
        elif not signatures_path.is_file():
            errors.append(f"journal_signatures_missing:{run_id}")
        else:
            if HOLD_SIGNATURE_RE.search(signatures_path.read_text(encoding="utf-8", errors="replace")):
                hold_reasons.append(f"journal_signature_hold:{run_id}")
                signal_reasons.append("journal_signature_hold")
    return actual_runs, sorted(set(hold_reasons)), sorted(set(signal_reasons))


def validate(run_dir: Path, *, require_recurrent: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    if run_dir.is_symlink():
        errors.append("run_dir_symlink_forbidden")
        return {
            "schema": SCHEMA,
            "evidence_valid": False,
            "pilot_hold": False,
            "passed": False,
            "run_dir": str(run_dir),
            "runs": [],
            "events": [],
            "hold_reasons": [],
            "signal_reasons": [],
            "errors": errors,
            "non_claims": [
                "root_cause_proven_without_log_review",
                "playback_readiness",
                "production_readiness",
                "stable_promotion",
                "public_player_runtime_thaw",
            ],
        }
    top = read_json(run_dir / "incident-summary.json", errors, "incident_summary") if run_dir.is_dir() else {}
    if not run_dir.is_dir():
        errors.append("run_dir_missing")
    if top.get("schema") != INCIDENT_SCHEMA:
        errors.append("incident_summary_schema")
    non_claims = set(top.get("non_claims") if isinstance(top.get("non_claims"), list) else [])
    if not REQUIRED_NON_CLAIMS.issubset(non_claims):
        errors.append("top_non_claims_missing")
    events = parse_events(run_dir, errors)
    actual_runs, hold_reasons, signal_reasons = validate_runs(run_dir, top, errors)
    if require_recurrent and not {"loop_entered", "loop_reentered"}.issubset(set(events)):
        errors.append("recurrent_events_missing")
    if {"loop_entered", "loop_reentered"}.issubset(set(events)):
        hold_reasons.append("recurrent_loop_observed")
    validate_manifest(run_dir, errors)
    leak_scan(run_dir, errors)
    evidence_valid = not errors
    pilot_hold = bool(hold_reasons)
    return {
        "schema": SCHEMA,
        "evidence_valid": evidence_valid,
        "pilot_hold": pilot_hold,
        "passed": evidence_valid and not pilot_hold,
        "run_dir": str(run_dir),
        "runs": actual_runs,
        "events": events,
        "hold_reasons": sorted(set(hold_reasons)),
        "signal_reasons": signal_reasons,
        "errors": sorted(set(errors)),
        "non_claims": [
            "root_cause_proven_without_log_review",
            "playback_readiness",
            "production_readiness",
            "stable_promotion",
            "public_player_runtime_thaw",
        ],
    }


def build_fixture(root: Path, *, recurrent: bool = False, leak: bool = False, health_passed: bool = True) -> Path:
    run_dir = root / "incident"
    run_id = "20260611T120000Z-1-loop_entered"
    health_dir = run_dir / "runs" / run_id / "deep-health"
    health_dir.mkdir(parents=True)
    failure_reasons = [] if health_passed else ["media_load_failed_zero"]
    counters = {"media_load_failed": 0 if health_passed else 1, "mpv_restart": 0}
    health = {"schema": PLAYBACK_SCHEMA, "passed": health_passed, "failure_reasons": failure_reasons, "counters": counters}
    for file_name in REQUIRED_DEEP_HEALTH_FILES:
        path = health_dir / file_name
        if file_name.endswith(".json"):
            write_json(path, health if file_name == "playback-deep-health-public.json" else {"ok": True})
        else:
            path.write_text("header\n", encoding="utf-8")
    signatures = "ok\n" if health_passed else "Restarting MPV reason=media_load_failed:media-123\n"
    if leak:
        signatures += "http://example.test/private\n"
    (run_dir / "runs" / run_id / "journal-signatures.ndjson").write_text(signatures, encoding="utf-8")
    run_summary = {
        "schema": INCIDENT_SCHEMA,
        "result_claim": "read_only_playback_incident_evidence_collected",
        "run_id": run_id,
        "deep_health": {"passed": health_passed, "failure_reasons": failure_reasons, "counters": counters},
        "non_claims": list(REQUIRED_NON_CLAIMS),
    }
    write_json(run_dir / "runs" / run_id / "incident-summary.json", run_summary)
    events = ["loop_entered"]
    if recurrent:
        events.append("loop_reentered")
    (run_dir / "operator-events.tsv").write_text(
        "utc\tevent\tnote_hash\n" + "".join(f"2026-06-11T12:00:00Z\t{event}\t\n" for event in events),
        encoding="utf-8",
    )
    top = {
        "schema": INCIDENT_SCHEMA,
        "result_claim": "read_only_playback_incident_evidence_collected",
        "runs": [run_id],
        "latest_run": run_summary,
        "operator_events": str(run_dir / "operator-events.tsv"),
        "non_claims": list(REQUIRED_NON_CLAIMS),
    }
    write_json(run_dir / "incident-summary.json", top)
    files = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name != "evidence-manifest.json":
            files.append({"file": rel(path, run_dir), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(run_dir / "evidence-manifest.json", {"schema": MANIFEST_SCHEMA, "files": files})
    return run_dir


class IncidentEvidenceGateSelfTest(unittest.TestCase):
    def test_valid_non_recurrent_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = validate(build_fixture(Path(tmp)))
        self.assertTrue(result["passed"], result)

    def test_recurrent_fixture_is_valid_but_holds_pilot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = validate(build_fixture(Path(tmp), recurrent=True), require_recurrent=True)
        self.assertTrue(result["evidence_valid"], result)
        self.assertTrue(result["pilot_hold"], result)
        self.assertIn("recurrent_loop_observed", result["hold_reasons"])

    def test_failed_health_holds_pilot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = validate(build_fixture(Path(tmp), health_passed=False))
        self.assertTrue(result["evidence_valid"], result)
        self.assertTrue(result["pilot_hold"], result)

    def test_leak_invalidates_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = validate(build_fixture(Path(tmp), leak=True))
        self.assertFalse(result["evidence_valid"], result)
        self.assertIn("leak:url:runs/20260611T120000Z-1-loop_entered/journal-signatures.ndjson", result["errors"])

    def test_manifest_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = build_fixture(Path(tmp))
            (run_dir / "evidence-manifest.json").unlink()
            result = validate(run_dir)
        self.assertFalse(result["evidence_valid"], result)
        self.assertIn("manifest_missing", result["errors"])

    def test_empty_runs_invalidates_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = build_fixture(Path(tmp))
            for path in sorted((run_dir / "runs").rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            top = read_json(run_dir / "incident-summary.json", [], "top")
            top["runs"] = []
            write_json(run_dir / "incident-summary.json", top)
            files = []
            for path in sorted(run_dir.rglob("*")):
                if path.is_file() and path.name != "evidence-manifest.json":
                    files.append({"file": rel(path, run_dir), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
            write_json(run_dir / "evidence-manifest.json", {"schema": MANIFEST_SCHEMA, "files": files})
            result = validate(run_dir)
        self.assertFalse(result["evidence_valid"], result)
        self.assertIn("runs_empty", result["errors"])

    def test_recurrent_mode_requires_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = build_fixture(Path(tmp))
            (run_dir / "operator-events.tsv").unlink()
            result = validate(run_dir, require_recurrent=True)
        self.assertFalse(result["evidence_valid"], result)
        self.assertIn("recurrent_events_missing", result["errors"])

    def test_symlink_is_invalid_without_following_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = build_fixture(root)
            (run_dir / "operator-events.tsv").unlink()
            (run_dir / "operator-events.tsv").symlink_to(root / "outside-events.tsv")
            result = validate(run_dir)
        self.assertFalse(result["evidence_valid"], result)
        self.assertIn("operator_events_symlink_forbidden", result["errors"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate C18 playback incident evidence.")
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--require-recurrent", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IncidentEvidenceGateSelfTest))
        return 0 if result.wasSuccessful() else 1
    if args.run_dir is None:
        print("missing --run-dir", file=sys.stderr)
        return 2
    result = validate(args.run_dir, require_recurrent=args.require_recurrent)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"evidence_valid={str(result['evidence_valid']).lower()} pilot_hold={str(result['pilot_hold']).lower()}")
        for error in result["errors"]:
            print(f"- error:{error}")
        for reason in result["hold_reasons"]:
            print(f"- hold:{reason}")
    return 0 if result["evidence_valid"] and not result["pilot_hold"] else 1


if __name__ == "__main__":
    sys.exit(main())
