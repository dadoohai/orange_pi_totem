#!/usr/bin/env python3
"""Validate sanitized C18 player-runtime rehearsal evidence before commit."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.player_runtime.evidence_gate.v1"

ALLOWED_PATTERNS = (
    "README.md",
    "evidence-manifest.json",
    "package/*.manifest.json",
    "package/player-runtime-release-gate.json",
    "lab-apply.json",
    "lab-rollback.json",
    "lab-reconcile.json",
    "candidate-health-result.json",
    "candidate-health/playback-deep-health-public.json",
    "candidate-health/playback-samples.tsv",
    "candidate-health/status-samples.ndjson",
    "candidate-health/deep-health-systemd.json",
    "candidate-health/deep-health-process.json",
    "candidate-health/deep-health-kernel.json",
    "candidate-health/deep-health-player-counters.json",
    "verified-marker.json",
    "service-after-restart/playback-deep-health-public.json",
    "service-after-restart/playback-samples.tsv",
    "service-after-restart/status-samples.ndjson",
    "service-after-restart/deep-health-systemd.json",
    "service-after-restart/deep-health-process.json",
    "service-after-restart/deep-health-kernel.json",
    "service-after-restart/deep-health-player-counters.json",
    "service-after-rollback/playback-deep-health-public.json",
    "service-after-rollback/playback-samples.tsv",
    "service-after-rollback/status-samples.ndjson",
    "service-after-rollback/deep-health-systemd.json",
    "service-after-rollback/deep-health-process.json",
    "service-after-rollback/deep-health-kernel.json",
    "service-after-rollback/deep-health-player-counters.json",
    "qa/evidence-leak-scan.txt",
)

FORBIDDEN_BASENAMES = {
    ".env",
    "candidate-config.json",
    "config.json",
    "kiosk.log",
    "mpv.log",
    "playlist_last.json",
    "seed.json",
}

FORBIDDEN_SUFFIXES = (".tar.gz", ".tgz", ".log", ".key", ".token", ".secret")
FORBIDDEN_DIRS = {"raw", "extracted", "media_cache", "runtime", "state"}

LEAK_PATTERNS = (
    ("url", re.compile(r"https?://", re.I)),
    ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("mac", re.compile(r"\b[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}\b")),
    ("data_config_path", re.compile(r"/data/config\b")),
    ("data_media_path", re.compile(r"/data/media\b")),
    ("tmp_media_path", re.compile(r"/tmp/[^\s\"']+\.(?:mp4|mkv|mov|webm|avi|m4v)\b", re.I)),
    ("api_key", re.compile(r"api_key\s*[:=]", re.I)),
    ("authorization", re.compile(r"authorization\s*:", re.I)),
    ("bearer", re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]+", re.I)),
    ("password", re.compile(r"password\s*[:=]", re.I)),
    ("ssid", re.compile(r"ssid\s*[:=]", re.I)),
    ("environment_id", re.compile(r"environment_id\s*[:=]", re.I)),
)


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def allowed(rel_path: str) -> bool:
    return any(fnmatch.fnmatch(rel_path, pattern) for pattern in ALLOWED_PATTERNS)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_evidence_manifest(run_dir: Path, files: list[str]) -> list[str]:
    errors: list[str] = []
    manifest_path = run_dir / "evidence-manifest.json"
    if not manifest_path.is_file():
        return ["missing_required:evidence-manifest.json"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"manifest_read_error:{type(exc).__name__}"]
    if not isinstance(manifest, dict):
        return ["manifest_not_object"]
    if manifest.get("schema") not in {
        "dadooh.c18.update_validation.evidence_manifest.v1",
        "dadooh.c18.player_runtime.evidence_manifest.v1",
    }:
        errors.append("manifest_invalid_schema")
    artifacts = manifest.get("artifacts")
    if artifacts is None:
        artifacts = manifest.get("files")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("manifest_missing_artifacts")
        return errors
    present = set(files)
    for item in artifacts:
        if not isinstance(item, dict):
            errors.append("manifest_artifact_not_object")
            continue
        rel_path = str(item.get("file") or "")
        if not rel_path:
            errors.append("manifest_artifact_missing_file")
            continue
        if rel_path == "evidence-manifest.json":
            errors.append("manifest_must_not_hash_itself")
            continue
        if rel_path not in present:
            errors.append(f"manifest_artifact_missing:{rel_path}")
            continue
        path = run_dir / rel_path
        expected_bytes = item.get("bytes")
        expected_sha = item.get("sha256")
        if expected_bytes != path.stat().st_size:
            errors.append(f"manifest_artifact_bytes_mismatch:{rel_path}")
        if expected_sha != sha256_file(path):
            errors.append(f"manifest_artifact_sha_mismatch:{rel_path}")
    return errors


def validate(run_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    files: list[str] = []
    if not run_dir.is_dir():
        return {
            "schema": SCHEMA,
            "passed": False,
            "errors": [f"run_dir_not_found:{run_dir}"],
            "files": [],
        }

    for path in sorted(run_dir.rglob("*")):
        rel_path = rel(path, run_dir)
        parts = set(Path(rel_path).parts)
        if path.is_dir():
            if parts & FORBIDDEN_DIRS:
                errors.append(f"forbidden_dir:{rel_path}")
            continue
        files.append(rel_path)
        if parts & FORBIDDEN_DIRS:
            errors.append(f"file_under_forbidden_dir:{rel_path}")
        if path.name in FORBIDDEN_BASENAMES:
            errors.append(f"forbidden_file:{rel_path}")
        if path.name.endswith(FORBIDDEN_SUFFIXES):
            errors.append(f"forbidden_suffix:{rel_path}")
        if not allowed(rel_path):
            errors.append(f"unexpected_file:{rel_path}")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"read_error:{rel_path}:{type(exc).__name__}")
            continue
        for label, pattern in LEAK_PATTERNS:
            if pattern.search(text):
                errors.append(f"leak_pattern:{label}:{rel_path}")

    required = {
        "README.md",
        "evidence-manifest.json",
        "lab-apply.json",
        "lab-rollback.json",
        "candidate-health/playback-deep-health-public.json",
        "candidate-health/playback-samples.tsv",
        "service-after-restart/playback-deep-health-public.json",
        "service-after-rollback/playback-deep-health-public.json",
    }
    present = set(files)
    for rel_path in sorted(required - present):
        errors.append(f"missing_required:{rel_path}")
    errors.extend(validate_evidence_manifest(run_dir, files))

    return {
        "schema": SCHEMA,
        "passed": not errors,
        "errors": errors,
        "files": files,
    }


def self_test() -> None:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="c18-evidence-gate-") as tmp:
        root = Path(tmp)
        run = root / "run"
        for rel_path in (
            "README.md",
            "package/dadooh-player-runtime-demo.manifest.json",
            "package/player-runtime-release-gate.json",
            "lab-apply.json",
            "lab-rollback.json",
            "candidate-health-result.json",
            "candidate-health/playback-deep-health-public.json",
            "candidate-health/playback-samples.tsv",
            "candidate-health/deep-health-systemd.json",
            "candidate-health/deep-health-process.json",
            "candidate-health/deep-health-kernel.json",
            "candidate-health/deep-health-player-counters.json",
            "service-after-restart/playback-deep-health-public.json",
            "service-after-restart/playback-samples.tsv",
            "service-after-rollback/playback-deep-health-public.json",
            "service-after-rollback/playback-samples.tsv",
        ):
            path = run / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
        artifacts = []
        for path in sorted(run.rglob("*")):
            if path.is_file():
                artifacts.append({
                    "file": rel(path, run),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                })
        (run / "evidence-manifest.json").write_text(
            json.dumps(
                {
                    "schema": "dadooh.c18.player_runtime.evidence_manifest.v1",
                    "artifact_id": "self-test",
                    "artifacts": artifacts,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        ok = validate(run)
        assert ok["passed"], ok
        bad = run / "candidate-health" / "candidate-config.json"
        bad.write_text('{"api_key":"SECRET","media":"/data/media/private.mp4"}\n', encoding="utf-8")
        failed = validate(run)
        assert not failed["passed"], failed
        assert any("forbidden_file" in item for item in failed["errors"]), failed
        assert any("leak_pattern" in item for item in failed["errors"]), failed


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        if not args.json:
            print("self-test: ok")
        return 0
    if args.run_dir is None:
        print("missing --run-dir", file=sys.stderr)
        return 2
    result = validate(args.run_dir)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"evidence_gate_passed={str(bool(result['passed'])).lower()}")
        for error in result["errors"]:
            print(error, file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
