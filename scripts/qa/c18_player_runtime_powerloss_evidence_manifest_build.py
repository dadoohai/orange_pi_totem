#!/usr/bin/env python3
"""Build the top-level manifest for pulled C18 power-loss evidence.

This helper is offline/local-only. It does not run board commands, does not
validate the evidence, and does not relax the power-loss evidence gate. It only
materializes the `evidence-manifest.json` file that the gate requires after an
operator has pulled one checkpoint directory from the board.
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


SCHEMA = "dadooh.c18.powerloss.evidence_manifest.v1"
COMPONENT = "player-runtime"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evidence_files(run_dir: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        rel = path.relative_to(run_dir).as_posix()
        if path.is_symlink():
            raise RuntimeError(f"symlink_not_allowed:{rel}")
        if path.is_dir() or rel == "evidence-manifest.json":
            continue
        files.append({
            "file": rel,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    if not files:
        raise RuntimeError("no_evidence_files")
    return files


def validate_args(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    if args.run_dir is None:
        blockers.append("run_dir_missing")
    elif not args.run_dir.is_dir():
        blockers.append(f"run_dir_missing:{args.run_dir}")
    if not args.checkpoint:
        blockers.append("checkpoint_missing")
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_commit or ""):
        blockers.append("source_commit_invalid")
    if not args.target_package_version:
        blockers.append("target_package_version_missing")
    if not args.board_image_marker:
        blockers.append("board_image_marker_missing")
    if (args.run_dir / "evidence-manifest.json").exists() and not args.overwrite:
        blockers.append("evidence_manifest_already_exists")
    return blockers


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    blockers = validate_args(args)
    if blockers:
        return {
            "schema": SCHEMA,
            "passed": False,
            "blockers": blockers,
            "result_claim": "powerloss_evidence_manifest_blocked",
        }

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "artifact_id": args.artifact_id or f"c18-player-runtime-h2-powerloss-{args.checkpoint}-{args.run_dir.name}",
        "component": COMPONENT,
        "checkpoint": args.checkpoint,
        "board_image_marker": args.board_image_marker,
        "source_commit": args.source_commit,
        "target_package_version": args.target_package_version,
        "files": evidence_files(args.run_dir),
    }
    optional_fields = (
        "expected_active_version",
        "setup_expected_active_version",
        "setup_candidate_version",
        "rollback_expectation",
    )
    for field in optional_fields:
        value = getattr(args, field)
        if value:
            manifest[field] = value
    return {
        "schema": SCHEMA,
        "passed": True,
        "result_claim": "powerloss_evidence_manifest_written",
        "manifest": manifest,
    }


def write_manifest(args: argparse.Namespace) -> dict[str, Any]:
    result = build_manifest(args)
    if result.get("passed") is True:
        manifest_path = args.run_dir / "evidence-manifest.json"
        manifest_path.write_text(json.dumps(result["manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = dict(result)
        result.pop("manifest", None)
        result["manifest_path"] = str(manifest_path)
        result["manifest_sha256"] = sha256_file(manifest_path)
    return result


class PowerlossEvidenceManifestBuildSelfTest(unittest.TestCase):
    def test_writes_manifest_with_declared_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "after_payload_staged"
            (run_dir / "powerloss-checkpoint").mkdir(parents=True)
            (run_dir / "powerloss-checkpoint" / "checkpoint.json").write_text('{"ok": true}\n', encoding="utf-8")
            args = argparse.Namespace(
                run_dir=run_dir,
                checkpoint="after_payload_staged",
                source_commit="a" * 40,
                target_package_version="c18.player-runtime-test",
                board_image_marker="c18-hwdecode-lab-test-image",
                expected_active_version="runtime-a",
                setup_expected_active_version="runtime-a",
                setup_candidate_version="runtime-b",
                rollback_expectation=None,
                artifact_id=None,
                overwrite=False,
            )
            result = write_manifest(args)
            manifest = json.loads((run_dir / "evidence-manifest.json").read_text(encoding="utf-8"))

        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
        self.assertEqual(manifest["schema"], SCHEMA)
        self.assertEqual(manifest["component"], COMPONENT)
        self.assertEqual(manifest["checkpoint"], "after_payload_staged")
        self.assertEqual(manifest["source_commit"], "a" * 40)
        self.assertEqual(manifest["target_package_version"], "c18.player-runtime-test")
        self.assertEqual(manifest["expected_active_version"], "runtime-a")
        self.assertEqual(manifest["setup_candidate_version"], "runtime-b")
        self.assertEqual(manifest["files"][0]["file"], "powerloss-checkpoint/checkpoint.json")

    def test_refuses_existing_manifest_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "evidence-manifest.json").write_text("{}\n", encoding="utf-8")
            args = argparse.Namespace(
                run_dir=run_dir,
                checkpoint="after_payload_staged",
                source_commit="a" * 40,
                target_package_version="c18.player-runtime-test",
                board_image_marker="c18-hwdecode-lab-test-image",
                expected_active_version=None,
                setup_expected_active_version=None,
                setup_candidate_version=None,
                rollback_expectation=None,
                artifact_id=None,
                overwrite=False,
            )
            result = build_manifest(args)

        self.assertFalse(result["passed"])
        self.assertIn("evidence_manifest_already_exists", result["blockers"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--checkpoint")
    parser.add_argument("--source-commit")
    parser.add_argument("--target-package-version")
    parser.add_argument("--board-image-marker")
    parser.add_argument("--expected-active-version")
    parser.add_argument("--setup-expected-active-version")
    parser.add_argument("--setup-candidate-version")
    parser.add_argument("--rollback-expectation")
    parser.add_argument("--artifact-id")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(PowerlossEvidenceManifestBuildSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = write_manifest(args)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result.get("passed") is not True:
        print(json.dumps(result, indent=2, sort_keys=True), file=sys.stderr)
    return 0 if result.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
