#!/usr/bin/env python3
"""Validate a future C18 player-runtime release payload without enabling OTA apply."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import py_compile
import re
import shutil
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_KIOSK = REPO_ROOT / "player-runtime" / "kiosky-player" / "kiosk.py"
SCHEMA = "dadooh.c18.player_runtime.release_gate.v1"
UPDATE_SCHEMA = "dadooh.totem.update.v1"
COMPONENT = "player-runtime"
DEVICE = "orangepizero3"
DEVICE_TRACK = "c18-hwdecode"
BASE_IMAGE_LINE = "c17.4.2"
EXPECTED_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
EXPECTED_HWDEC = "v4l2request-copy"
EXPECTED_DEEP_HEALTH_SCHEMA = "dadooh.c18.playback.deep_health.v1"
SAFE_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class GateError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise GateError(f"{path.name} must be a JSON object")
    return data


def parse_utc_timestamp(value: Any) -> None:
    if not isinstance(value, str) or not value:
        raise GateError("created_at_utc must be a non-empty string")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError as exc:
        raise GateError("created_at_utc must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise GateError("created_at_utc must include timezone")


def validate_manifest(manifest: dict[str, Any], payload: Path) -> dict[str, Any]:
    required = {
        "schema",
        "component",
        "version",
        "channel",
        "created_at_utc",
        "payload",
        "payload_sha256",
        "requires",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise GateError(f"manifest missing fields: {missing}")
    if manifest["schema"] != UPDATE_SCHEMA:
        raise GateError(f"unsupported manifest schema: {manifest['schema']!r}")
    if manifest["component"] != COMPONENT:
        raise GateError(f"manifest component must be {COMPONENT!r}")
    version = manifest["version"]
    if not isinstance(version, str) or not SAFE_VERSION_RE.fullmatch(version):
        raise GateError("unsafe version string")
    expected_payload = f"dadooh-{COMPONENT}-{version}.tar.gz"
    if manifest["payload"] != expected_payload:
        raise GateError(f"payload name must be {expected_payload!r}")
    if manifest["payload_sha256"].lower() != sha256_file(payload):
        raise GateError("payload_sha256 mismatch")
    parse_utc_timestamp(manifest["created_at_utc"])

    requires = manifest["requires"]
    if not isinstance(requires, dict):
        raise GateError("requires must be a JSON object")
    expected_requires = {
        "device": DEVICE,
        "base_image_min": BASE_IMAGE_LINE,
        "device_track": DEVICE_TRACK,
        "media_stack_id": "c18-hwdecode-v4l2request-copy",
        "mpv_wrapper": EXPECTED_WRAPPER,
        "hwdec": EXPECTED_HWDEC,
        "vo": "gpu",
        "gpu_context": "drm",
        "deep_health_schema": EXPECTED_DEEP_HEALTH_SCHEMA,
    }
    for key, expected in expected_requires.items():
        if requires.get(key) != expected:
            raise GateError(f"requires.{key} must be {expected!r}")

    return {
        "version": version,
        "payload_sha256": manifest["payload_sha256"].lower(),
    }


def safe_member_path(name: str) -> Path:
    if name.startswith("/") or ".." in Path(name).parts:
        raise GateError(f"unsafe tar member path: {name}")
    return Path(name)


def validate_tar_member(member: tarfile.TarInfo) -> Path:
    path = safe_member_path(member.name)
    if not (member.isfile() or member.isdir()):
        raise GateError(f"unsupported tar member type: {member.name}")
    lowered = "/".join(path.parts).lower()
    basename = path.name.lower()
    if lowered.startswith(("data/", "media/", "secrets/", "config/")):
        raise GateError(f"field-data path is not allowed in player-runtime payload: {member.name}")
    if basename in {".env", "config.json", "seed.json", "policy.json"}:
        raise GateError(f"field-data file is not allowed in player-runtime payload: {member.name}")
    if basename.endswith((".key", ".token", ".secret")):
        raise GateError(f"secret-like file is not allowed in player-runtime payload: {member.name}")
    return path


def find_kiosk_member(tf: tarfile.TarFile) -> tarfile.TarInfo:
    kiosk_members = []
    for member in tf.getmembers():
        path = validate_tar_member(member)
        if member.isfile() and path.name == "kiosk.py":
            kiosk_members.append(member)
    if len(kiosk_members) != 1:
        raise GateError(f"expected exactly one kiosk.py, found {len(kiosk_members)}")
    return kiosk_members[0]


def validate_kiosk_source(source: str) -> None:
    if f'"mpv_path": "{EXPECTED_WRAPPER}"' not in source:
        raise GateError("kiosk.py must default mpv_path to the C18 hwdecode wrapper")
    if '"mpv_path": "mpv"' in source or '"mpv_path": "/usr/bin/mpv"' in source:
        raise GateError("kiosk.py must not default mpv_path to stock mpv")
    required_anchors = (
        'cfg["mpv_path"]',
        "--hwdec-codecs=h264,mpeg4,mpeg2video",
        "--no-osc",
        '"loadfile"',
        '"replace"',
    )
    for anchor in required_anchors:
        if anchor not in source:
            raise GateError(f"kiosk.py missing required runtime anchor: {anchor}")


def validate_payload(payload: Path) -> dict[str, Any]:
    if not payload.is_file() or payload.is_symlink():
        raise GateError("payload must be a regular file")
    with tempfile.TemporaryDirectory(prefix="c18-player-runtime-gate-") as tmp:
        temp_root = Path(tmp)
        with tarfile.open(payload, "r:gz") as tf:
            kiosk_member = find_kiosk_member(tf)
            extracted = tf.extractfile(kiosk_member)
            if extracted is None:
                raise GateError("failed to read kiosk.py from payload")
            source = extracted.read().decode("utf-8")
        kiosk_path = temp_root / "kiosk.py"
        kiosk_path.write_text(source, encoding="utf-8")
        py_compile.compile(str(kiosk_path), doraise=True)
        validate_kiosk_source(source)
    return {"kiosk_py_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest()}


def validate_release(manifest_path: Path, payload_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    manifest_result = validate_manifest(manifest, payload_path)
    payload_result = validate_payload(payload_path)
    return {
        "schema": SCHEMA,
        "passed": True,
        "component": COMPONENT,
        "manifest": manifest_result,
        "payload": payload_result,
    }


def write_payload(root: Path, version: str, kiosk_source: str, extra_files: dict[str, bytes] | None = None) -> Path:
    work = root / "payload-root"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    (work / "kiosk.py").write_text(kiosk_source, encoding="utf-8")
    for name, content in (extra_files or {}).items():
        target = work / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    payload = root / f"dadooh-{COMPONENT}-{version}.tar.gz"
    with tarfile.open(payload, "w:gz") as tf:
        for path in sorted(work.rglob("*")):
            tf.add(path, arcname=str(path.relative_to(work)))
    return payload


def write_manifest(root: Path, version: str, payload: Path, mutate: dict[str, Any] | None = None) -> Path:
    manifest = {
        "schema": UPDATE_SCHEMA,
        "component": COMPONENT,
        "version": version,
        "channel": "homologation",
        "created_at_utc": "2026-06-03T00:00:00Z",
        "payload": payload.name,
        "payload_sha256": sha256_file(payload),
        "requires": {
            "device": DEVICE,
            "base_image_min": BASE_IMAGE_LINE,
            "device_track": DEVICE_TRACK,
            "media_stack_id": "c18-hwdecode-v4l2request-copy",
            "mpv_wrapper": EXPECTED_WRAPPER,
            "hwdec": EXPECTED_HWDEC,
            "vo": "gpu",
            "gpu_context": "drm",
            "deep_health_schema": EXPECTED_DEEP_HEALTH_SCHEMA,
        },
    }
    if mutate:
        for key, value in mutate.items():
            if key.startswith("requires."):
                manifest["requires"][key.split(".", 1)[1]] = value
            else:
                manifest[key] = value
    path = root / f"dadooh-{COMPONENT}-{version}.manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


class C18PlayerRuntimeReleaseGateSelfTest(unittest.TestCase):
    def with_case(self, version: str = "test-player-runtime") -> tuple[Path, Path, tempfile.TemporaryDirectory[str]]:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        root = Path(tmp.name)
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8")
        payload = write_payload(root, version, source)
        manifest = write_manifest(root, version, payload)
        return manifest, payload, tmp

    def test_accepts_governed_snapshot_payload(self) -> None:
        manifest, payload, tmp = self.with_case("good")
        self.addCleanup(tmp.cleanup)
        result = validate_release(manifest, payload)
        self.assertTrue(result["passed"])

    def test_rejects_stock_mpv_default(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(EXPECTED_WRAPPER, "mpv")
        payload = write_payload(root, "bad-mpv", source)
        manifest = write_manifest(root, "bad-mpv", payload)
        with self.assertRaisesRegex(GateError, "stock mpv|hwdecode wrapper"):
            validate_release(manifest, payload)

    def test_rejects_field_data_payload(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        payload = write_payload(
            root,
            "bad-config",
            SNAPSHOT_KIOSK.read_text(encoding="utf-8"),
            {"config.json": b"{}"},
        )
        manifest = write_manifest(root, "bad-config", payload)
        with self.assertRaisesRegex(GateError, "field-data"):
            validate_release(manifest, payload)

    def test_rejects_wrong_media_stack_contract(self) -> None:
        manifest, payload, tmp = self.with_case("bad-stack")
        self.addCleanup(tmp.cleanup)
        manifest = write_manifest(Path(tmp.name), "bad-stack", payload, {"requires.hwdec": "no"})
        with self.assertRaisesRegex(GateError, "requires.hwdec"):
            validate_release(manifest, payload)

    def test_rejects_symlink_members(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        payload = root / f"dadooh-{COMPONENT}-bad-link.tar.gz"
        with tarfile.open(payload, "w:gz") as tf:
            info = tarfile.TarInfo("kiosk.py")
            data = SNAPSHOT_KIOSK.read_bytes()
            info.size = len(data)
            tf.addfile(info, fileobj=__import__("io").BytesIO(data))
            link = tarfile.TarInfo("evil-link")
            link.type = tarfile.SYMTYPE
            link.linkname = "/etc/passwd"
            tf.addfile(link)
        manifest = write_manifest(root, "bad-link", payload)
        with self.assertRaisesRegex(GateError, "unsupported tar member type"):
            validate_release(manifest, payload)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(C18PlayerRuntimeReleaseGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if not args.manifest or not args.payload:
        raise SystemExit("--manifest and --payload are required unless --self-test is used")
    try:
        result = validate_release(args.manifest, args.payload)
    except Exception as exc:
        print(json.dumps({"schema": SCHEMA, "passed": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
