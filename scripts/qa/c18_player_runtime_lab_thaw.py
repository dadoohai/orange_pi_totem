#!/usr/bin/env python3
"""Canonical C18 player-runtime lab thaw wrapper.

This is the operator-facing wrapper for the already-proven M6 two-phase
player-runtime `/data` cold-boot trial. It does not thaw public
`totem-updatectl` verbs, does not use GitHub, does not publish, and rejects
stable packages. It supplies the current golden image identity by default and
delegates apply/rollback/reconcile/deep-health to the existing guarded M6
harness.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QA_DIR = REPO_ROOT / "scripts" / "qa"
sys.path.insert(0, str(QA_DIR))

from c18_current_golden import load_current_golden  # noqa: E402
import c18_player_runtime_release_gate as release_gate  # noqa: E402


LAB_ENV = "C18_PLAYER_RUNTIME_LAB_THAW"
M6_ENV = "C18_PLAYER_RUNTIME_M6_COLDBOOT_TRIAL"
DEVICE_DATA_ENV = "C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT"
SCHEMA = "dadooh.c18.player_runtime.lab_thaw.v1"
REQUIRED_UPDATER_FEATURES = release_gate.REQUIRED_UPDATER_FEATURES
SUPPORTED_UPDATER_FEATURES = release_gate.SUPPORTED_UPDATER_FEATURES


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def path_is_under(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    root_resolved = root.resolve()
    return resolved == root_resolved or root_resolved in resolved.parents


def env_base() -> dict[str, str]:
    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    data = read_json(path)
    if data.get("component") != "player-runtime":
        raise RuntimeError("manifest_component_not_player_runtime")
    if data.get("channel") not in {"lab", "homologation"}:
        raise RuntimeError("lab_thaw_only_accepts_lab_or_homologation_channel")
    if data.get("source_dirty") is not False:
        raise RuntimeError("manifest_source_dirty_must_be_false")
    requires = data.get("requires")
    if not isinstance(requires, dict):
        raise RuntimeError("manifest_requires_missing")
    features = requires.get("updater_features")
    if not isinstance(features, list):
        raise RuntimeError("manifest_missing_player_runtime_verify_then_promote_feature")
    feature_set = set(features)
    missing_features = sorted(REQUIRED_UPDATER_FEATURES - feature_set)
    if missing_features:
        raise RuntimeError("manifest_missing_player_runtime_verify_then_promote_feature")
    unsupported_features = sorted(feature_set - SUPPORTED_UPDATER_FEATURES)
    if unsupported_features:
        raise RuntimeError("manifest_unsupported_updater_features:" + ",".join(unsupported_features))
    return data


def current_golden_defaults(args: argparse.Namespace) -> tuple[str, str, Path]:
    golden = load_current_golden()
    image_tag = args.image_tag or str(golden["image_tag"])
    image_sha256 = args.image_sha256 or str(golden["image_sha256"])
    marker_file = args.image_marker_file or Path(str(golden["image_marker_path"]))
    return image_tag, image_sha256, marker_file


def require_lab_guard(args: argparse.Namespace) -> None:
    if not args.lab_only_thaw or os.environ.get(LAB_ENV) != "1":
        raise RuntimeError(f"lab_thaw_guard_required:set {LAB_ENV}=1 and pass --lab-only-thaw")
    touches_device_data = path_is_under(args.data_root, Path("/data")) or path_is_under(args.evidence_root, Path("/data"))
    if touches_device_data and (
        not args.allow_device_data_root or os.environ.get(DEVICE_DATA_ENV) != "1"
    ):
        raise RuntimeError(f"device_data_root_guard_required:set {DEVICE_DATA_ENV}=1 and pass --allow-device-data-root")


def validate_arm_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    missing = [
        name
        for name in ("manifest_a", "payload_a", "manifest_b", "payload_b", "canary_media")
        if getattr(args, name) is None
    ]
    if missing:
        raise RuntimeError("missing_required_for_arm:" + ",".join(missing))
    manifest_a = load_manifest(args.manifest_a)
    manifest_b = load_manifest(args.manifest_b)
    if manifest_a.get("version") == manifest_b.get("version"):
        raise RuntimeError("lab_thaw_requires_distinct_a_b_versions")
    release_gate.validate_release(args.manifest_a, args.payload_a)
    release_gate.validate_release(args.manifest_b, args.payload_b)
    return manifest_a, manifest_b


def run_m6(args: argparse.Namespace, image_tag: str, image_sha256: str, marker_file: Path) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(QA_DIR / "c18_player_runtime_m6_coldboot_trial.py"),
        "--phase",
        args.phase,
        "--data-root",
        str(args.data_root),
        "--allow-device-data-root",
        "--evidence-root",
        str(args.evidence_root),
        "--image-tag",
        image_tag,
        "--image-sha256",
        image_sha256,
        "--image-marker-file",
        str(marker_file),
        "--mechanical-action",
        args.mechanical_action,
        "--duration-sec",
        str(args.duration_sec),
        "--interval-sec",
        str(args.interval_sec),
        "--startup-wait-sec",
        str(args.startup_wait_sec),
        "--json",
    ]
    if args.repo_identity_file is not None:
        cmd.extend(["--repo-identity-file", str(args.repo_identity_file)])
    if args.candidate_duration_sec is not None:
        cmd.extend(["--candidate-duration-sec", str(args.candidate_duration_sec)])
    if args.service_duration_sec is not None:
        cmd.extend(["--service-duration-sec", str(args.service_duration_sec)])
    if args.defer_release_gate:
        cmd.append("--defer-release-gate")
    if args.phase == "arm":
        cmd.extend([
            "--manifest-a", str(args.manifest_a),
            "--payload-a", str(args.payload_a),
            "--manifest-b", str(args.manifest_b),
            "--payload-b", str(args.payload_b),
            "--canary-media", str(args.canary_media),
        ])
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env={**env_base(), LAB_ENV: "1", M6_ENV: "1", DEVICE_DATA_ENV: "1"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=3600,
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"m6_json_failed rc={proc.returncode} stderr_tail={proc.stderr[-800:]}") from exc
    write_json(args.evidence_root / f"lab-thaw-{args.phase}.json", data)
    deferred_resume = (
        args.phase == "resume"
        and args.defer_release_gate
        and data.get("m6_checks_passed") is True
        and data.get("release_gate_deferred") is True
        and data.get("passed") is False
    )
    if proc.returncode != 0 and not deferred_resume:
        raise RuntimeError(f"m6_failed rc={proc.returncode} phase={args.phase} stderr_tail={proc.stderr[-800:]}")
    return data


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--lab-only-thaw", action="store_true")
    parser.add_argument("--phase", choices=("arm", "resume", "rollback-only"), required=True)
    parser.add_argument("--manifest-a", type=Path)
    parser.add_argument("--payload-a", type=Path)
    parser.add_argument("--manifest-b", type=Path)
    parser.add_argument("--payload-b", type=Path)
    parser.add_argument("--canary-media", type=Path)
    parser.add_argument("--data-root", type=Path, default=Path("/data"))
    parser.add_argument("--allow-device-data-root", action="store_true")
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--image-tag")
    parser.add_argument("--image-sha256")
    parser.add_argument("--image-marker-file", type=Path)
    parser.add_argument("--repo-identity-file", type=Path)
    parser.add_argument("--mechanical-action", default="operator_controlled_reboot")
    parser.add_argument("--defer-release-gate", action="store_true")
    parser.add_argument("--duration-sec", type=float, default=45.0)
    parser.add_argument("--candidate-duration-sec", type=float)
    parser.add_argument("--service-duration-sec", type=float)
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--startup-wait-sec", type=float, default=8.0)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        require_lab_guard(args)
        image_tag, image_sha256, marker_file = current_golden_defaults(args)
        if not marker_file.is_file():
            raise RuntimeError(f"image_marker_file_missing:{marker_file}")
        manifest_a: dict[str, Any] | None = None
        manifest_b: dict[str, Any] | None = None
        if args.phase == "arm":
            manifest_a, manifest_b = validate_arm_inputs(args)
        result = run_m6(args, image_tag, image_sha256, marker_file)
        m6_passed = result.get("passed") is True or (
            args.phase == "resume"
            and bool(result.get("release_gate_deferred"))
            and result.get("m6_checks_passed") is True
        )
        final_authorization = (
            args.phase == "resume"
            and m6_passed
            and not bool(result.get("release_gate_deferred"))
            and (result.get("release_gate") or {}).get("passed") is True
        )
        passed = final_authorization if args.phase == "resume" else m6_passed
        summary = {
            "schema": SCHEMA,
            "phase": args.phase,
            "passed": passed,
            "m6_passed": m6_passed,
            "final_authorization": final_authorization,
            "public_cli_thawed": False,
            "github_used": False,
            "stable_allowed": False,
            "requires_real_reboot": args.phase == "arm",
            "release_gate_deferred": bool(result.get("release_gate_deferred")),
            "image_tag": image_tag,
            "image_sha256": image_sha256,
            "image_marker_sha256": sha256_file(marker_file),
            "version_a": manifest_a.get("version") if manifest_a else result.get("version_a"),
            "version_b": manifest_b.get("version") if manifest_b else result.get("version_b"),
            "evidence_root": str(args.evidence_root),
        }
        write_json(args.evidence_root / "lab-thaw-summary.json", summary)
        print(json.dumps(summary, indent=2 if args.json else None, sort_keys=True))
        return 0 if passed else 1
    except RuntimeError as exc:
        message = str(exc)
        print(message, file=sys.stderr)
        if message.startswith("lab_thaw_guard_required"):
            return 44
        if message.startswith("device_data_root_guard_required"):
            return 43
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
