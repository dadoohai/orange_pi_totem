#!/usr/bin/env python3
"""Collect C18 server-side publish assets for a stable GitHub release.

This helper is offline-only. It reads the already validated server-side evidence
and prints the exact files that must be attached to the release.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from c18_server_side_publish_governance_gate import (
    REQUIRED_SIGNED_OR_ATTESTED_ASSETS,
    sha256_file,
    write_signed_fixture_release,
    write_trust_anchor_for_key,
)


HASH_RE = "0123456789abcdef"


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json_not_object:{path}")
    return data


def is_sha256(value: str | None) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in HASH_RE for ch in value)


def resolve_release_file(raw: object, *, release_dir: Path, label: str) -> Path:
    if not isinstance(raw, str) or not raw or raw.startswith("/") or ".." in Path(raw).parts:
        raise ValueError(f"invalid_server_side_asset_path:{label}:{raw!r}")
    candidate = release_dir / raw
    current = release_dir
    for part in Path(raw).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"server_side_asset_symlink:{label}:{raw!r}")
    try:
        path = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"missing_server_side_asset:{label}:{raw!r}") from exc
    try:
        path.relative_to(release_dir)
    except ValueError as exc:
        raise ValueError(f"server_side_asset_outside_release_dir:{label}:{raw!r}") from exc
    if not path.is_file():
        raise ValueError(f"missing_server_side_asset:{label}:{raw!r}")
    return path


def append_unique(paths: list[Path], path: Path) -> None:
    resolved = path.resolve(strict=True)
    if resolved not in paths:
        paths.append(resolved)


def collect_assets(
    evidence_path: Path,
    trust_anchor_path: Path,
    *,
    expected_release_gate_sha256: str | None = None,
) -> list[Path]:
    evidence = evidence_path.resolve(strict=True)
    trust_anchor = trust_anchor_path.resolve(strict=True)
    release_dir = evidence.parent.resolve(strict=True)
    data = read_json(evidence)

    paths: list[Path] = []
    append_unique(paths, evidence)

    release_assets = data.get("release_assets")
    if not isinstance(release_assets, dict):
        raise ValueError("server_side_evidence_missing_release_assets")

    release_gate_path: Path | None = None
    for field in ("manifest", "payload", "release_gate", "audit_log"):
        asset_path = resolve_release_file(release_assets.get(field), release_dir=release_dir, label=field)
        append_unique(paths, asset_path)
        if field == "release_gate":
            release_gate_path = asset_path

    if expected_release_gate_sha256 is not None:
        if not is_sha256(expected_release_gate_sha256):
            raise ValueError("expected_release_gate_sha256_invalid")
        if release_gate_path is None:
            raise ValueError("server_side_release_gate_asset_missing")
        actual = sha256_file(release_gate_path)
        if actual != expected_release_gate_sha256:
            raise ValueError(
                f"server_side_release_gate_sha256_mismatch:actual={actual}:expected={expected_release_gate_sha256}"
            )

    attestations = data.get("asset_attestations")
    if not isinstance(attestations, list):
        raise ValueError("server_side_evidence_missing_asset_attestations")
    for item in attestations:
        if not isinstance(item, dict):
            raise ValueError("server_side_asset_attestation_not_object")
        asset = item.get("asset")
        proof_path = resolve_release_file(
            item.get("proof_file"),
            release_dir=release_dir,
            label=f"{asset}:proof_file",
        )
        append_unique(paths, proof_path)
        proof = read_json(proof_path)

        proof_signature_file = proof.get("signature_file")
        if item.get("attestation_type") == "signature" and not proof_signature_file:
            raise ValueError(f"server_side_signature_file_missing_in_proof:{asset}")
        if isinstance(proof_signature_file, str) and proof_signature_file:
            append_unique(
                paths,
                resolve_release_file(
                    proof_signature_file,
                    release_dir=release_dir,
                    label=f"{asset}:proof.signature_file",
                ),
            )

        legacy_signature_file = item.get("signature_file")
        if isinstance(legacy_signature_file, str) and legacy_signature_file:
            append_unique(
                paths,
                resolve_release_file(
                    legacy_signature_file,
                    release_dir=release_dir,
                    label=f"{asset}:signature_file",
                ),
            )

    append_unique(paths, trust_anchor)
    return paths


class ServerSidePublishAssetCollectSelfTest(unittest.TestCase):
    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_signed_fixture_collects_proofs_signatures_and_trust_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence, public_key = write_signed_fixture_release(root / "release")
            trust_anchor = write_trust_anchor_for_key(root / "trust-anchor.json", public_key)
            data = read_json(evidence)
            release_gate = (evidence.parent / data["release_assets"]["release_gate"]).resolve(strict=True)

            paths = collect_assets(
                evidence,
                trust_anchor,
                expected_release_gate_sha256=sha256_file(release_gate),
            )

        names = {path.name for path in paths}
        self.assertIn("c18-server-side-publish-governance.json", names)
        self.assertIn("audit-log.ndjson", names)
        self.assertIn("trust-anchor.json", names)
        self.assertEqual(len([path for path in paths if path.suffix == ".sig"]), len(REQUIRED_SIGNED_OR_ATTESTED_ASSETS))
        self.assertEqual(len([path for path in paths if path.name.endswith(".signature.json")]), len(REQUIRED_SIGNED_OR_ATTESTED_ASSETS))

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_release_gate_hash_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence, public_key = write_signed_fixture_release(root / "release")
            trust_anchor = write_trust_anchor_for_key(root / "trust-anchor.json", public_key)
            with self.assertRaisesRegex(ValueError, "server_side_release_gate_sha256_mismatch"):
                collect_assets(evidence, trust_anchor, expected_release_gate_sha256="0" * 64)

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_missing_signature_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence, public_key = write_signed_fixture_release(root / "release")
            trust_anchor = write_trust_anchor_for_key(root / "trust-anchor.json", public_key)
            signature = next((evidence.parent / "signatures").glob("*.sig"))
            signature.unlink()
            with self.assertRaisesRegex(ValueError, "missing_server_side_asset"):
                collect_assets(evidence, trust_anchor)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--server-side-evidence", type=Path)
    parser.add_argument("--trust-anchor-evidence", type=Path)
    parser.add_argument("--expected-release-gate-sha256")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or [])
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ServerSidePublishAssetCollectSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if args.server_side_evidence is None:
        raise SystemExit("missing --server-side-evidence")
    if args.trust_anchor_evidence is None:
        raise SystemExit("missing --trust-anchor-evidence")
    paths = collect_assets(
        args.server_side_evidence,
        args.trust_anchor_evidence,
        expected_release_gate_sha256=args.expected_release_gate_sha256,
    )
    if args.json:
        print(json.dumps({"assets": [str(path) for path in paths]}, indent=2, sort_keys=True))
    else:
        for path in paths:
            print(path)
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
