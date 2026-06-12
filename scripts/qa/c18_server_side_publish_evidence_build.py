#!/usr/bin/env python3
"""Build C18 server-side publish governance evidence for an existing release.

This tool is offline-only. It writes the evidence family that
``c18_server_side_publish_governance_gate.py`` validates, but it does not
publish, fetch, promote stable, enable auto-pull, or thaw player-runtime.

The signing private key, trusted public key, and trust-anchor evidence must live
outside the release directory. The private key is never copied into the release.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from c18_player_runtime_release_gate import (
    SNAPSHOT_KIOSK,
    validate_release as validate_player_runtime_release,
    write_manifest as write_player_runtime_manifest,
    write_payload as write_player_runtime_payload,
)
from c18_server_side_publish_governance_gate import (
    ALLOWED_CHANNELS,
    EXPECTED_COMPONENT_SCOPE,
    FIXTURE_AUDIT_LOG_NAME,
    RELEASE_GATE_SCHEMA_BY_COMPONENT,
    RELEASE_GATE_TOOL_BY_COMPONENT,
    REQUIRED_ATTESTATION_COVERS,
    REQUIRED_AUDIT_EVENTS,
    REQUIRED_SIGNED_OR_ATTESTED_ASSETS,
    REQUIRED_TRUST_ANCHOR_NON_CLAIMS,
    SCHEMA,
    SERVER_SIDE_EVIDENCE_FILENAME,
    SIGNATURE_ALGORITHM,
    SIGNATURE_SCHEMA,
    TRUST_ANCHOR_PUBLIC_KEY_ALGORITHM,
    TRUST_ANCHOR_PURPOSE,
    TRUST_ANCHOR_SCHEMA,
    canonical_json_bytes,
    evaluate,
    has_any_symlink_component,
    is_relative_to,
    public_key_spki_sha256,
    release_set_sha256,
    run_openssl,
    sha256_bytes,
    sha256_file,
    sign_payload,
    signature_payload,
    valid_fixture,
    write_json,
)


DEFAULT_RELEASE_GATE_BY_COMPONENT = {
    "totem-core": "c18-ota-release-gate.json",
    "player-runtime": "c18-player-runtime-release-gate.json",
}
DEFAULT_ACTOR = "c18-release-governance"
DEFAULT_SELECTED_BY = "operator-release-01"
DEFAULT_KEY_OWNER = "release-security-01"
REPO_ROOT = Path(__file__).resolve().parents[2]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json_not_object:{path}")
    return data


def resolve_existing_file(path: Path, *, release_dir: Path, label: str) -> Path:
    if has_any_symlink_component(path):
        raise ValueError(f"{label}_symlink:{path}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"{label}_missing:{path}") from exc
    if not resolved.is_file():
        raise ValueError(f"{label}_not_file:{path}")
    release_root = release_dir.resolve(strict=True)
    if is_relative_to(resolved, release_root):
        raise ValueError(f"{label}_inside_release_dir:{path}")
    if label == "signing_private_key" and is_relative_to(resolved, REPO_ROOT):
        raise ValueError(f"{label}_inside_repo:{path}")
    return resolved


def resolve_output_file(path: Path, *, release_dir: Path, label: str) -> Path:
    release_root = release_dir.resolve(strict=True)
    resolved = path.resolve(strict=False)
    if is_relative_to(resolved, release_root):
        raise ValueError(f"{label}_inside_release_dir:{path}")
    if has_any_symlink_component(path.parent) or (path.exists() and has_any_symlink_component(path)):
        raise ValueError(f"{label}_symlink:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def resolve_release_member(path: Path, *, release_dir: Path, label: str) -> Path:
    if has_any_symlink_component(path):
        raise ValueError(f"{label}_symlink:{path}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"{label}_missing:{path}") from exc
    release_root = release_dir.resolve(strict=True)
    if not is_relative_to(resolved, release_root):
        raise ValueError(f"{label}_outside_release_dir:{path}")
    if not resolved.is_file():
        raise ValueError(f"{label}_not_file:{path}")
    return resolved


def discover_manifest(release_dir: Path, component: str) -> Path:
    matches = sorted(release_dir.glob(f"dadooh-{component}-*.manifest.json"))
    if len(matches) != 1:
        raise ValueError(f"release_manifest_count:{component}:{len(matches)}")
    return matches[0]


def release_paths(
    *,
    release_dir: Path,
    component: str,
    manifest_path: Path | None,
    payload_path: Path | None,
    release_gate_path: Path | None,
) -> tuple[Path, Path, Path, dict[str, Any]]:
    release_root = release_dir.resolve(strict=True)
    manifest = resolve_release_member(
        manifest_path or discover_manifest(release_root, component),
        release_dir=release_root,
        label="manifest",
    )
    data = read_json(manifest)
    if data.get("schema") != "dadooh.totem.update.v1":
        raise ValueError("manifest_schema")
    if data.get("component") != component:
        raise ValueError(f"manifest_component:{data.get('component')}!={component}")
    if data.get("channel") not in ALLOWED_CHANNELS:
        raise ValueError(f"manifest_channel:{data.get('channel')}")
    payload = resolve_release_member(
        payload_path or release_root / str(data.get("payload", "")),
        release_dir=release_root,
        label="payload",
    )
    if payload.name != data.get("payload"):
        raise ValueError("manifest_payload_name_mismatch")
    if sha256_file(payload) != data.get("payload_sha256"):
        raise ValueError("manifest_payload_sha256_mismatch")
    gate = resolve_release_member(
        release_gate_path or release_root / DEFAULT_RELEASE_GATE_BY_COMPONENT[component],
        release_dir=release_root,
        label="release_gate",
    )
    return manifest, payload, gate, data


def fail_if_outputs_exist(paths: list[Path], *, force: bool) -> None:
    if force:
        return
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise ValueError("server_side_output_exists:" + ",".join(existing))


def write_trust_anchor(
    path: Path,
    *,
    trusted_key_spki_sha256: str,
    selected_by: str,
    key_owner: str,
    selected_at_utc: str,
    allowed_channels: list[str],
) -> None:
    write_json(path, {
        "schema": TRUST_ANCHOR_SCHEMA,
        "purpose": TRUST_ANCHOR_PURPOSE,
        "trusted_key_spki_sha256": trusted_key_spki_sha256,
        "public_key_algorithm": TRUST_ANCHOR_PUBLIC_KEY_ALGORITHM,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "scope": {
            "components": list(EXPECTED_COMPONENT_SCOPE),
            "channels": allowed_channels,
        },
        "selected_by": selected_by,
        "key_owner": key_owner,
        "selected_at_utc": selected_at_utc,
        "private_key_material_present": False,
        "non_claims": list(REQUIRED_TRUST_ANCHOR_NON_CLAIMS),
    })


def write_audit_log(path: Path, *, actor: str, at_utc: str, asset_hashes: dict[str, str]) -> None:
    audit_hashes = {
        asset: asset_hashes[asset]
        for asset in ("manifest", "payload", "c18-ota-release-gate")
    }
    lines = [
        json.dumps({
            "event": event,
            "actor": actor,
            "at_utc": at_utc,
            "artifact_hashes": audit_hashes,
            "promotion_performed": False,
            "auto_pull_enabled": False,
            "public_player_runtime_thaw": False,
        }, sort_keys=True)
        for event in REQUIRED_AUDIT_EVENTS
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_evidence(args: argparse.Namespace) -> dict[str, Any]:
    release_dir = args.release_dir.resolve(strict=True)
    component = args.component
    manifest_path, payload_path, release_gate_path, manifest = release_paths(
        release_dir=release_dir,
        component=component,
        manifest_path=args.manifest,
        payload_path=args.payload,
        release_gate_path=args.release_gate,
    )
    private_key = resolve_existing_file(args.signing_private_key_pem, release_dir=release_dir, label="signing_private_key")
    public_key = resolve_existing_file(args.trusted_public_key_pem, release_dir=release_dir, label="trusted_public_key")
    trust_anchor_path = resolve_output_file(args.trust_anchor_evidence, release_dir=release_dir, label="trust_anchor_evidence")
    key_sha256 = public_key_spki_sha256(public_key)
    if key_sha256 is None:
        raise ValueError("trusted_public_key_spki_sha256_unavailable")

    evidence_path = release_dir / SERVER_SIDE_EVIDENCE_FILENAME
    audit_path = release_dir / FIXTURE_AUDIT_LOG_NAME
    signature_dir = release_dir / "signatures"
    proof_paths = [
        signature_dir / f"{asset}.signature.json"
        for asset in REQUIRED_SIGNED_OR_ATTESTED_ASSETS
    ]
    signature_paths = [
        signature_dir / f"{asset}.sig"
        for asset in REQUIRED_SIGNED_OR_ATTESTED_ASSETS
    ]
    fail_if_outputs_exist(
        [evidence_path, audit_path, trust_anchor_path, *proof_paths, *signature_paths],
        force=args.force,
    )

    selected_at_utc = args.selected_at_utc or utc_now()
    allowed_channels = args.trust_anchor_channel or [str(manifest["channel"])]
    if any(channel not in ALLOWED_CHANNELS for channel in allowed_channels):
        raise ValueError("trust_anchor_channel_invalid")
    write_trust_anchor(
        trust_anchor_path,
        trusted_key_spki_sha256=key_sha256,
        selected_by=args.selected_by,
        key_owner=args.key_owner,
        selected_at_utc=selected_at_utc,
        allowed_channels=allowed_channels,
    )

    asset_hashes = {
        "manifest": sha256_file(manifest_path),
        "payload": sha256_file(payload_path),
        "c18-ota-release-gate": sha256_file(release_gate_path),
    }
    write_audit_log(
        audit_path,
        actor=args.actor,
        at_utc=selected_at_utc,
        asset_hashes=asset_hashes,
    )
    asset_hashes["audit-log"] = sha256_file(audit_path)
    expected_release_set_sha256 = release_set_sha256(asset_hashes)

    signature_dir.mkdir(parents=True, exist_ok=True)
    proof_files: dict[str, str] = {}
    proof_hashes: dict[str, str] = {}
    signature_hashes: dict[str, str] = {}
    for asset in REQUIRED_SIGNED_OR_ATTESTED_ASSETS:
        signature_rel = f"signatures/{asset}.sig"
        proof_rel = f"signatures/{asset}.signature.json"
        proof = {
            "schema": SIGNATURE_SCHEMA,
            "subject_asset": asset,
            "subject_sha256": asset_hashes[asset],
            "release_set_sha256": expected_release_set_sha256,
            "source_commit": manifest["source_commit"],
            "component": manifest["component"],
            "channel": manifest["channel"],
            "created_at_utc": manifest["created_at_utc"],
            "covers": list(REQUIRED_ATTESTATION_COVERS),
            "signature_algorithm": SIGNATURE_ALGORITHM,
            "trusted_key_sha256": key_sha256,
            "signature_file": signature_rel,
        }
        signature_path = release_dir / signature_rel
        sign_payload(private_key, canonical_json_bytes(signature_payload(proof)), signature_path)
        proof_path = release_dir / proof_rel
        write_json(proof_path, proof)
        proof_files[asset] = proof_rel
        proof_hashes[asset] = sha256_bytes(canonical_json_bytes(proof))
        signature_hashes[asset] = sha256_file(signature_path)

    evidence = valid_fixture(component=component, asset_hashes=asset_hashes)
    evidence["test_fixture"] = False
    evidence["release_assets"] = {
        "manifest": manifest_path.name,
        "payload": payload_path.name,
        "release_gate": release_gate_path.name,
        "audit_log": audit_path.name,
    }
    evidence["publish_gate"]["tool"] = RELEASE_GATE_TOOL_BY_COMPONENT[component]
    evidence["asset_attestations"] = [
        {
            "asset": asset,
            "sha256": asset_hashes[asset],
            "attestation_type": "signature",
            "signer": args.actor,
            "signature_sha256": signature_hashes[asset],
            "proof_sha256": proof_hashes[asset],
            "proof_file": proof_files[asset],
            "covers": list(REQUIRED_ATTESTATION_COVERS),
        }
        for asset in REQUIRED_SIGNED_OR_ATTESTED_ASSETS
    ]
    write_json(evidence_path, evidence)

    gate = evaluate(
        evidence_path,
        expected_component=component,
        trusted_key_pems=[public_key],
        trust_anchor_evidence=trust_anchor_path,
    )
    if gate.get("passed") is not True:
        raise ValueError("generated_server_side_evidence_failed_gate:" + ",".join(gate.get("blockers", [])))
    return {
        "schema": "dadooh.c18.server_side_publish_evidence_build.v1",
        "passed": True,
        "component": component,
        "release_dir": str(release_dir),
        "evidence": str(evidence_path),
        "trust_anchor_evidence": str(trust_anchor_path),
        "trusted_public_key": str(public_key),
        "manifest": str(manifest_path),
        "payload": str(payload_path),
        "release_gate": str(release_gate_path),
        "audit_log": str(audit_path),
        "signature_count": len(signature_paths),
        "non_claims": [
            "this_tool_does_not_publish_releases",
            "this_tool_does_not_enable_auto_pull",
            "this_tool_does_not_promote_stable",
            "this_tool_does_not_thaw_player_runtime",
        ],
    }


def write_release_fixture(root: Path, *, component: str = "player-runtime", channel: str = "homologation") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if component == "player-runtime":
        version = "signed-evidence-test"
        payload = write_player_runtime_payload(root, version, SNAPSHOT_KIOSK.read_text(encoding="utf-8"))
        manifest_path = write_player_runtime_manifest(root, version, payload, mutate={"channel": channel})
        release_gate = validate_player_runtime_release(manifest_path, payload)
    else:
        payload = root / f"dadooh-{component}-signed-evidence-test.tar.gz"
        payload.write_bytes(b"c18 server-side publish evidence build fixture\n")
        manifest = {
            "schema": "dadooh.totem.update.v1",
            "component": component,
            "version": "signed-evidence-test",
            "channel": channel,
            "created_at_utc": "2026-06-12T00:00:00Z",
            "source_commit": "c" * 40,
            "source_dirty": False,
            "payload": payload.name,
            "payload_sha256": sha256_file(payload),
        }
        manifest_path = root / f"dadooh-{component}-signed-evidence-test.manifest.json"
        write_json(manifest_path, manifest)
        release_gate = {
            "schema": RELEASE_GATE_SCHEMA_BY_COMPONENT[component],
            "passed": True,
            "steps": [{"name": "fixture_release_gate", "passed": True}],
            "repo": {"dirty": False},
            "guardrails": {"github_used": False},
            "package": {
                "manifest": manifest_path.name,
                "payload": payload.name,
                "payload_sha256": manifest["payload_sha256"],
                "source_commit": manifest["source_commit"],
                "component": component,
                "channel": channel,
                "checks": {"fixture_release_gate": True},
                "passed": True,
            },
        }
    write_json(root / DEFAULT_RELEASE_GATE_BY_COMPONENT[component], release_gate)
    return root


def generate_keypair(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    private_key = root / "release-signing-key.pem"
    public_key = root / "release-signing-key.pub.pem"
    run_openssl(["genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key)])
    run_openssl(["rsa", "-pubout", "-in", str(private_key), "-out", str(public_key)])
    return private_key, public_key


class ServerSidePublishEvidenceBuildSelfTest(unittest.TestCase):
    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_generates_player_runtime_evidence_accepted_by_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = write_release_fixture(root / "release", component="player-runtime")
            private_key, public_key = generate_keypair(root / "trust")
            result = build_evidence(argparse.Namespace(
                release_dir=release,
                component="player-runtime",
                manifest=None,
                payload=None,
                release_gate=None,
                signing_private_key_pem=private_key,
                trusted_public_key_pem=public_key,
                trust_anchor_evidence=root / "trust-anchor.json",
                selected_by=DEFAULT_SELECTED_BY,
                key_owner=DEFAULT_KEY_OWNER,
                selected_at_utc="2026-06-12T00:00:00Z",
                actor=DEFAULT_ACTOR,
                trust_anchor_channel=["homologation"],
                force=False,
            ))
            self.assertTrue(result["passed"])
            gate = evaluate(
                Path(result["evidence"]),
                expected_component="player-runtime",
                trusted_key_pems=[public_key],
                trust_anchor_evidence=Path(result["trust_anchor_evidence"]),
            )
            self.assertTrue(gate["passed"], msg=json.dumps(gate, indent=2, sort_keys=True))

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_generates_totem_core_evidence_accepted_by_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = write_release_fixture(root / "release", component="totem-core", channel="stable")
            private_key, public_key = generate_keypair(root / "trust")
            result = build_evidence(argparse.Namespace(
                release_dir=release,
                component="totem-core",
                manifest=None,
                payload=None,
                release_gate=None,
                signing_private_key_pem=private_key,
                trusted_public_key_pem=public_key,
                trust_anchor_evidence=root / "trust-anchor.json",
                selected_by=DEFAULT_SELECTED_BY,
                key_owner=DEFAULT_KEY_OWNER,
                selected_at_utc="2026-06-12T00:00:00Z",
                actor=DEFAULT_ACTOR,
                trust_anchor_channel=["stable"],
                force=False,
            ))
            self.assertTrue(result["passed"])

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_refuses_private_key_inside_release_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = write_release_fixture(root / "release", component="player-runtime")
            private_key, public_key = generate_keypair(root / "trust")
            inside_private = release / "release-signing-key.pem"
            shutil.copyfile(private_key, inside_private)
            with self.assertRaisesRegex(ValueError, "signing_private_key_inside_release_dir"):
                build_evidence(argparse.Namespace(
                    release_dir=release,
                    component="player-runtime",
                    manifest=None,
                    payload=None,
                    release_gate=None,
                    signing_private_key_pem=inside_private,
                    trusted_public_key_pem=public_key,
                    trust_anchor_evidence=root / "trust-anchor.json",
                    selected_by=DEFAULT_SELECTED_BY,
                    key_owner=DEFAULT_KEY_OWNER,
                    selected_at_utc="2026-06-12T00:00:00Z",
                    actor=DEFAULT_ACTOR,
                    trust_anchor_channel=["homologation"],
                    force=False,
                ))

    def test_refuses_private_key_inside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release = write_release_fixture(Path(tmp) / "release", component="player-runtime")
            with self.assertRaisesRegex(ValueError, "signing_private_key_inside_repo"):
                resolve_existing_file(REPO_ROOT / "README.md", release_dir=release, label="signing_private_key")

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_refuses_public_key_inside_release_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = write_release_fixture(root / "release", component="player-runtime")
            _private_key, public_key = generate_keypair(root / "trust")
            inside_public = release / "release-signing-key.pub.pem"
            shutil.copyfile(public_key, inside_public)
            with self.assertRaisesRegex(ValueError, "trusted_public_key_inside_release_dir"):
                resolve_existing_file(inside_public, release_dir=release, label="trusted_public_key")

    def test_refuses_trust_anchor_inside_release_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release = write_release_fixture(Path(tmp) / "release", component="player-runtime")
            with self.assertRaisesRegex(ValueError, "trust_anchor_evidence_inside_release_dir"):
                resolve_output_file(release / "trust-anchor.json", release_dir=release, label="trust_anchor_evidence")

    @unittest.skipIf(shutil.which("openssl") is None, "openssl missing")
    def test_refuses_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = write_release_fixture(root / "release", component="player-runtime")
            private_key, public_key = generate_keypair(root / "trust")
            common = dict(
                release_dir=release,
                component="player-runtime",
                manifest=None,
                payload=None,
                release_gate=None,
                signing_private_key_pem=private_key,
                trusted_public_key_pem=public_key,
                trust_anchor_evidence=root / "trust-anchor.json",
                selected_by=DEFAULT_SELECTED_BY,
                key_owner=DEFAULT_KEY_OWNER,
                selected_at_utc="2026-06-12T00:00:00Z",
                actor=DEFAULT_ACTOR,
                trust_anchor_channel=["homologation"],
            )
            build_evidence(argparse.Namespace(**common, force=False))
            with self.assertRaisesRegex(ValueError, "server_side_output_exists"):
                build_evidence(argparse.Namespace(**common, force=False))
            result = build_evidence(argparse.Namespace(**common, force=True))
            self.assertTrue(result["passed"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build C18 server-side publish evidence.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--release-dir", type=Path)
    parser.add_argument("--component", choices=sorted(RELEASE_GATE_SCHEMA_BY_COMPONENT))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--release-gate", type=Path)
    parser.add_argument("--signing-private-key-pem", type=Path)
    parser.add_argument("--trusted-public-key-pem", type=Path)
    parser.add_argument("--trust-anchor-evidence", type=Path)
    parser.add_argument("--trust-anchor-channel", action="append", choices=ALLOWED_CHANNELS)
    parser.add_argument("--selected-by", default=DEFAULT_SELECTED_BY)
    parser.add_argument("--key-owner", default=DEFAULT_KEY_OWNER)
    parser.add_argument("--selected-at-utc")
    parser.add_argument("--actor", default=DEFAULT_ACTOR)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ServerSidePublishEvidenceBuildSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    for label in (
        "release_dir",
        "component",
        "signing_private_key_pem",
        "trusted_public_key_pem",
        "trust_anchor_evidence",
    ):
        if getattr(args, label) is None:
            raise SystemExit(f"missing --{label.replace('_', '-')}")
    try:
        result = build_evidence(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} evidence={result['evidence']}")
        print(f"trust_anchor_evidence={result['trust_anchor_evidence']}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
