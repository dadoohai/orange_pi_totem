#!/usr/bin/env python3
"""Build the exact C18 totem-core GitHub release asset list.

This helper is offline-only. It does not publish, contact GitHub, create tags,
or validate promotion evidence. The publisher calls it after the promotion and
server-side gates have already produced/validated their artifacts, so the final
``gh release create -- <assets>`` list is assembled by tested code instead of
ad-hoc shell array edits.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path


VALID_CHANNELS = {"lab", "homologation", "stable"}


def resolve_regular_file(path: Path, *, label: str) -> Path:
    candidate = path
    for current in [candidate, *candidate.parents]:
        if current.exists() and current.is_symlink():
            raise ValueError(f"publish_asset_symlink:{label}:{path}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"publish_asset_missing:{label}:{path}") from exc
    if not resolved.is_file():
        raise ValueError(f"publish_asset_not_file:{label}:{path}")
    return resolved


def append_unique(paths: list[Path], path: Path) -> None:
    if path not in paths:
        paths.append(path)


def build_asset_list(
    *,
    manifest: Path,
    payload: Path,
    gate_evidence: Path,
    channel: str,
    stable_evidence: Path | None = None,
    stable_server_side_assets: list[Path] | None = None,
) -> list[Path]:
    if channel not in VALID_CHANNELS:
        raise ValueError(f"publish_asset_channel_invalid:{channel}")

    assets: list[Path] = []
    append_unique(assets, resolve_regular_file(manifest, label="manifest"))
    append_unique(assets, resolve_regular_file(payload, label="payload"))
    append_unique(assets, resolve_regular_file(gate_evidence, label="gate_evidence"))

    stable_assets = list(stable_server_side_assets or [])
    if channel == "stable":
        if stable_evidence is None:
            raise ValueError("publish_asset_stable_evidence_missing")
        if not stable_assets:
            raise ValueError("publish_asset_stable_server_side_assets_missing")
        append_unique(assets, resolve_regular_file(stable_evidence, label="stable_evidence"))
        for index, asset in enumerate(stable_assets, 1):
            append_unique(assets, resolve_regular_file(asset, label=f"stable_server_side_asset:{index}"))
    else:
        if stable_evidence is not None or stable_assets:
            raise ValueError("publish_asset_stable_assets_on_non_stable_channel")
    return assets


class TotemCorePublishAssetListSelfTest(unittest.TestCase):
    def write_file(self, root: Path, name: str) -> Path:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{name}\n", encoding="utf-8")
        return path

    def test_stable_list_includes_base_stable_and_server_side_assets_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.write_file(root, "manifest.json")
            payload = self.write_file(root, "payload.tar.gz")
            gate = self.write_file(root, "c18-ota-release-gate.json")
            stable = self.write_file(root, "c18-stable-promotion-evidence.json")
            server_side = self.write_file(root, "server-side.json")
            audit = self.write_file(root, "audit-log.ndjson")

            assets = build_asset_list(
                manifest=manifest,
                payload=payload,
                gate_evidence=gate,
                channel="stable",
                stable_evidence=stable,
                stable_server_side_assets=[server_side, audit, server_side],
            )

        self.assertEqual(
            [path.name for path in assets],
            [
                "manifest.json",
                "payload.tar.gz",
                "c18-ota-release-gate.json",
                "c18-stable-promotion-evidence.json",
                "server-side.json",
                "audit-log.ndjson",
            ],
        )

    def test_stable_requires_server_side_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "publish_asset_stable_server_side_assets_missing"):
                build_asset_list(
                    manifest=self.write_file(root, "manifest.json"),
                    payload=self.write_file(root, "payload.tar.gz"),
                    gate_evidence=self.write_file(root, "gate.json"),
                    channel="stable",
                    stable_evidence=self.write_file(root, "stable.json"),
                    stable_server_side_assets=[],
                )

    def test_non_stable_rejects_stable_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "publish_asset_stable_assets_on_non_stable_channel"):
                build_asset_list(
                    manifest=self.write_file(root, "manifest.json"),
                    payload=self.write_file(root, "payload.tar.gz"),
                    gate_evidence=self.write_file(root, "gate.json"),
                    channel="homologation",
                    stable_evidence=self.write_file(root, "stable.json"),
                    stable_server_side_assets=[],
                )

    def test_missing_asset_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "publish_asset_missing:payload"):
                build_asset_list(
                    manifest=self.write_file(root, "manifest.json"),
                    payload=root / "missing.tar.gz",
                    gate_evidence=self.write_file(root, "gate.json"),
                    channel="lab",
                )

    def test_symlink_asset_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.write_file(root, "manifest.json")
            payload = self.write_file(root, "payload.tar.gz")
            payload_link = root / "payload-link.tar.gz"
            payload_link.symlink_to(payload)
            with self.assertRaisesRegex(ValueError, "publish_asset_symlink:payload"):
                build_asset_list(
                    manifest=manifest,
                    payload=payload_link,
                    gate_evidence=self.write_file(root, "gate.json"),
                    channel="lab",
                )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build C18 totem-core release publish asset list.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--gate-evidence", type=Path)
    parser.add_argument("--channel", choices=sorted(VALID_CHANNELS))
    parser.add_argument("--stable-evidence", type=Path)
    parser.add_argument("--stable-server-side-asset", type=Path, action="append", default=[])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TotemCorePublishAssetListSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    for label in ("manifest", "payload", "gate_evidence", "channel"):
        if getattr(args, label) is None:
            raise SystemExit(f"missing --{label.replace('_', '-')}")
    try:
        assets = build_asset_list(
            manifest=args.manifest,
            payload=args.payload,
            gate_evidence=args.gate_evidence,
            channel=args.channel,
            stable_evidence=args.stable_evidence,
            stable_server_side_assets=args.stable_server_side_asset,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.json:
        print(json.dumps({"assets": [str(path) for path in assets]}, indent=2, sort_keys=True))
    else:
        for path in assets:
            print(path)
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
