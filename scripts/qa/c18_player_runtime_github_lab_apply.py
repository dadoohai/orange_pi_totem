#!/usr/bin/env python3
"""Lab-only exact GitHub Release apply harness for C18 player-runtime.

This script closes the remote-consumption gap without opening public OTA apply:
it fetches one explicit GitHub Release tag, validates the governed
homologation manifest and expected hashes, then calls the internal
verify-then-promote path with a remote payload URL under an explicit lab guard.

It is not auto-pull, not stable rollout, and not public thaw. The public
`totem-updatectl` CLI must keep returning rc=44 for player-runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BOARD_DIR = REPO_ROOT / "scripts" / "board"
sys.path.insert(0, str(BOARD_DIR))

import c18_player_runtime_candidate_health as candidate_health
import c18_player_runtime_release_gate as release_gate
import totem_updatectl as updatectl


LAB_ENV = "C18_PLAYER_RUNTIME_GITHUB_LAB_APPLY"
DEVICE_DATA_ENV = "C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT"
COMPONENT = "player-runtime"
DEFAULT_REPO = "dadoohai/orange_pi_totem"
DEFAULT_TAG = "player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1"
DEFAULT_VERSION = "c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1"
DEFAULT_SOURCE_COMMIT = "9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522"
DEFAULT_PAYLOAD_SHA256 = "d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0"

REQUIRED_ASSET_NAMES = {
    "c18-player-runtime-release-gate.json",
    "c18-player-runtime-thaw-decision.json",
    "c18-stable-promotion.json",
    "h2-readiness-business-exception.json",
    "c18-server-side-publish-governance.json",
    "c18-server-side-trust-anchor.json",
}
REQUIRED_ASSET_PREFIXES = (
    "c18-player-runtime-activation-",
)


def path_is_under(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    root_resolved = root.resolve()
    return resolved == root_resolved or root_resolved in resolved.parents


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def configure_updatectl_for_lab(data_root: Path, policy_path: Path) -> None:
    updatectl.DATA_ROOT = data_root
    updatectl.UPDATES_DIR = updatectl.DATA_ROOT / "updates"
    updatectl.POLICY_FILE = policy_path
    updatectl.LOG_DIR = updatectl.DATA_ROOT / "logs"
    updatectl.LOG_FILE = updatectl.LOG_DIR / "totem-update.log"
    updatectl.TOKEN_FILE = updatectl.DATA_ROOT / "secrets" / "github-release-token"
    updatectl.configure_component(COMPONENT)


def write_lab_policy(policy_path: Path, channel: str) -> None:
    if channel != "homologation":
        raise RuntimeError("remote lab apply only accepts homologation player-runtime packages")
    write_json(
        policy_path,
        {
            "schema": "dadooh.totem.update.policy.v1",
            "device_channel": "homologation",
            "device_track": "c18-hwdecode",
            "allowed_components": ["player-runtime", "totem-core"],
            "allow_prerelease": True,
            "allow_downgrade": False,
        },
    )


def guarded_paths(args: argparse.Namespace, work_dir: Path, data_root: Path) -> tuple[bool, str]:
    touches_device_data = path_is_under(data_root, Path("/data")) or path_is_under(work_dir, Path("/data"))
    if touches_device_data and (
        not args.allow_device_data_root or os.environ.get(DEVICE_DATA_ENV) != "1"
    ):
        return False, f"device_data_root_guard_required: pass --allow-device-data-root and set {DEVICE_DATA_ENV}=1"
    return True, "ok"


def runtime_snapshot() -> dict[str, Any]:
    state: dict[str, Any] = {}
    try:
        state = updatectl._read_state()
    except Exception:
        state = {}
    return {
        "current_link": updatectl._read_symlink_target(updatectl.CURRENT_LINK),
        "previous_link": updatectl._read_symlink_target(updatectl.PREVIOUS_LINK),
        "current_exists": updatectl.CURRENT_LINK.exists() or updatectl.CURRENT_LINK.is_symlink(),
        "previous_exists": updatectl.PREVIOUS_LINK.exists() or updatectl.PREVIOUS_LINK.is_symlink(),
        "state_current_version": (state.get("current") or {}).get("version") if isinstance(state.get("current"), dict) else None,
        "state_previous_version": (state.get("previous") or {}).get("version") if isinstance(state.get("previous"), dict) else None,
        "last_operation": state.get("last_operation") if isinstance(state.get("last_operation"), dict) else None,
    }


def public_cli_freeze(data_root: Path, action: str) -> dict[str, Any]:
    missing = Path(tempfile.gettempdir()) / "c18-player-runtime-missing.manifest.json"
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TOTEM_DATA_ROOT": str(data_root),
    }
    cmd = [sys.executable, str(BOARD_DIR / "totem_updatectl.py")]
    if action == "apply":
        cmd.extend(["apply-local", "--component", COMPONENT, str(missing)])
    elif action == "reconcile":
        cmd.extend(["reconcile", "--component", COMPONENT])
    else:
        raise RuntimeError(f"unsupported public freeze action: {action}")
    proc = subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=30,
    )
    return {
        "returncode": proc.returncode,
        "frozen": proc.returncode == 44,
    }


def release_asset_names(release: dict[str, Any]) -> list[str]:
    return sorted(
        str(asset.get("name"))
        for asset in release.get("assets", [])
        if isinstance(asset, dict) and asset.get("name")
    )


def find_asset(release: dict[str, Any], name: str) -> dict[str, Any]:
    for asset in release.get("assets", []):
        if isinstance(asset, dict) and asset.get("name") == name:
            return asset
    raise RuntimeError(f"release {release.get('tag_name')} missing required asset: {name}")


def assert_required_governance_assets(release: dict[str, Any]) -> None:
    names = release_asset_names(release)
    missing = sorted(REQUIRED_ASSET_NAMES - set(names))
    if missing:
        raise RuntimeError(f"release missing governance assets: {missing}")
    for prefix in REQUIRED_ASSET_PREFIXES:
        if not any(name.startswith(prefix) and name.endswith(".json") for name in names):
            raise RuntimeError(f"release missing governance asset prefix: {prefix}*.json")


def fetch_release_by_tag(repo: str, tag: str) -> dict[str, Any]:
    safe_tag = urllib.parse.quote(tag, safe="")
    url = f"{updatectl.GITHUB_API}/repos/{repo}/releases/tags/{safe_tag}"
    data = updatectl._http_get_json(url)
    if not isinstance(data, dict):
        raise RuntimeError("unexpected GitHub release response shape")
    return data


def download_manifest(release: dict[str, Any], work_dir: Path) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest_asset, payload_asset = updatectl._gh_pick_assets(release, COMPONENT)
    manifest_path = updatectl._download_manifest_asset(manifest_asset, work_dir / "github-release" / str(release.get("tag_name") or "unknown"))
    with manifest_path.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    if not isinstance(manifest, dict):
        raise RuntimeError("downloaded manifest is not a JSON object")
    return manifest_path, manifest, manifest_asset, payload_asset


def download_payload_for_release_gate(
    payload_asset: dict[str, Any],
    manifest: dict[str, Any],
    work_dir: Path,
) -> Path:
    url = payload_asset.get("browser_download_url")
    if not isinstance(url, str) or not url:
        raise RuntimeError("payload asset missing browser_download_url")
    name = updatectl._safe_stage_name(str(payload_asset.get("name") or "payload.tar.gz"))
    payload_path = work_dir / "release-gate-payload" / name
    expected_sha = str(manifest.get("payload_sha256") or "")
    updatectl._http_download(url, payload_path, expected_sha256=expected_sha)
    return payload_path


def validate_manifest_expectations(
    release: dict[str, Any],
    manifest: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    tag = str(release.get("tag_name") or "")
    if tag != args.tag:
        raise RuntimeError(f"release tag mismatch: actual={tag} expected={args.tag}")
    if release.get("draft"):
        raise RuntimeError("draft release is not acceptable for remote lab apply")
    if manifest.get("component") != COMPONENT:
        raise RuntimeError(f"manifest component mismatch: {manifest.get('component')}")
    if manifest.get("channel") != "homologation":
        raise RuntimeError(f"manifest channel must be homologation: {manifest.get('channel')}")
    if args.expect_version and manifest.get("version") != args.expect_version:
        raise RuntimeError(f"manifest version mismatch: actual={manifest.get('version')} expected={args.expect_version}")
    if args.expect_source_commit and manifest.get("source_commit") != args.expect_source_commit:
        raise RuntimeError(
            f"manifest source_commit mismatch: actual={manifest.get('source_commit')} expected={args.expect_source_commit}"
        )
    if args.expect_payload_sha256 and str(manifest.get("payload_sha256", "")).lower() != args.expect_payload_sha256.lower():
        raise RuntimeError(
            f"manifest payload_sha256 mismatch: actual={manifest.get('payload_sha256')} expected={args.expect_payload_sha256}"
        )
    if bool(manifest.get("source_dirty")):
        raise RuntimeError("player-runtime manifest source_dirty must be false")


def build_selection_summary(
    release: dict[str, Any],
    manifest: dict[str, Any],
    manifest_asset: dict[str, Any],
    payload_asset: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    return {
        "repo": args.repo,
        "tag_name": release.get("tag_name"),
        "release_id": release.get("id"),
        "draft": bool(release.get("draft")),
        "prerelease": bool(release.get("prerelease")),
        "published_at": release.get("published_at"),
        "asset_count": len(release.get("assets") or []),
        "asset_names": release_asset_names(release),
        "manifest_asset": manifest_asset.get("name"),
        "payload_asset": payload_asset.get("name"),
        "payload_url_safe": updatectl._safe_url(str(payload_asset.get("browser_download_url") or "")),
        "selected_by_latest": False,
        "selection_mode": "exact_tag",
        "manifest_version": manifest.get("version"),
        "manifest_channel": manifest.get("channel"),
        "manifest_source_commit": manifest.get("source_commit"),
        "manifest_payload_sha256": manifest.get("payload_sha256"),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--lab-only-remote-apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--expect-version", default=DEFAULT_VERSION)
    parser.add_argument("--expect-source-commit", default=DEFAULT_SOURCE_COMMIT)
    parser.add_argument("--expect-payload-sha256", default=DEFAULT_PAYLOAD_SHA256)
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--allow-device-data-root", action="store_true")
    parser.add_argument("--config-template", type=Path)
    parser.add_argument("--canary-media", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--duration-sec", type=float, default=30.0)
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--startup-wait-sec", type=float, default=5.0)
    parser.add_argument("--panfrost-fault-policy", choices=("absolute", "delta"), default="absolute")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def run_self_test() -> int:
    fake_release = {
        "tag_name": DEFAULT_TAG,
        "draft": False,
        "prerelease": False,
        "published_at": "2026-07-04T22:47:54Z",
        "assets": [
            {"name": f"dadooh-player-runtime-{DEFAULT_VERSION}.manifest.json", "browser_download_url": "https://example.invalid/manifest.json"},
            {"name": f"dadooh-player-runtime-{DEFAULT_VERSION}.tar.gz", "browser_download_url": "https://example.invalid/payload.tar.gz"},
            {"name": "c18-player-runtime-release-gate.json"},
            {"name": "c18-player-runtime-thaw-decision.json"},
            {"name": "c18-stable-promotion.json"},
            {"name": "h2-readiness-business-exception.json"},
            {"name": "c18-server-side-publish-governance.json"},
            {"name": "c18-server-side-trust-anchor.json"},
            {"name": "c18-player-runtime-activation-test.json"},
        ],
    }
    fake_manifest = {
        "component": COMPONENT,
        "channel": "homologation",
        "version": DEFAULT_VERSION,
        "source_commit": DEFAULT_SOURCE_COMMIT,
        "source_dirty": False,
        "payload_sha256": DEFAULT_PAYLOAD_SHA256,
    }
    args = parse_args([])
    assert_required_governance_assets(fake_release)
    manifest_asset, payload_asset = updatectl._gh_pick_assets(fake_release, COMPONENT)
    validate_manifest_expectations(fake_release, fake_manifest, args)
    summary = build_selection_summary(fake_release, fake_manifest, manifest_asset, payload_asset, args)
    assert summary["asset_count"] == len(fake_release["assets"])
    assert summary["selection_mode"] == "exact_tag"
    assert summary["selected_by_latest"] is False
    try:
        broken = dict(fake_manifest)
        broken["payload_sha256"] = "0" * 64
        validate_manifest_expectations(fake_release, broken, args)
    except RuntimeError as exc:
        assert "payload_sha256 mismatch" in str(exc)
    else:
        raise AssertionError("payload sha mismatch did not fail")
    try:
        missing = dict(fake_release)
        missing["assets"] = fake_release["assets"][:2]
        assert_required_governance_assets(missing)
    except RuntimeError as exc:
        assert "missing governance assets" in str(exc)
    else:
        raise AssertionError("missing governance assets did not fail")
    print(json.dumps({"self_test": True, "checks": 6}, indent=2, sort_keys=True))
    return 0


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        return run_self_test()
    if not args.lab_only_remote_apply or os.environ.get(LAB_ENV) != "1":
        print(f"player_runtime_github_lab_apply_guard_required: pass --lab-only-remote-apply and set {LAB_ENV}=1", file=sys.stderr)
        return 44

    work_dir = args.output_dir or Path(tempfile.mkdtemp(prefix="c18-player-runtime-github-lab-apply-"))
    data_root = args.data_root or (work_dir / "data")
    ok, reason = guarded_paths(args, work_dir, data_root)
    if not ok:
        print(reason, file=sys.stderr)
        return 43

    policy_path = work_dir / "lab-policy.json"
    write_lab_policy(policy_path, "homologation")
    configure_updatectl_for_lab(data_root, policy_path)

    release = fetch_release_by_tag(args.repo, args.tag)
    assert_required_governance_assets(release)
    manifest_path, manifest, manifest_asset, payload_asset = download_manifest(release, work_dir)
    validate_manifest_expectations(release, manifest, args)
    updatectl._validate_manifest(manifest, policy=updatectl._load_update_policy(), component=COMPONENT)
    release_gate_payload = download_payload_for_release_gate(payload_asset, manifest, work_dir)
    release_gate_result = release_gate.validate_release(manifest_path, release_gate_payload)
    selection = build_selection_summary(release, manifest, manifest_asset, payload_asset, args)
    payload_url = payload_asset.get("browser_download_url")
    if not isinstance(payload_url, str) or not payload_url:
        raise RuntimeError("payload asset missing browser_download_url")

    public_apply_before = public_cli_freeze(data_root, "apply")
    public_reconcile_before = public_cli_freeze(data_root, "reconcile")
    if args.dry_run:
        result = {
            "schema": "dadooh.c18.player_runtime.github_lab_apply.v1",
            "component": COMPONENT,
            "dry_run": True,
            "state_changed": False,
            "passed": public_apply_before["frozen"] and public_reconcile_before["frozen"],
            "delivery_mode": "operator_assisted",
            "selection": selection,
            "manifest_path": str(manifest_path),
            "release_gate_validated": bool(release_gate_result.get("passed")),
            "release_gate_package": release_gate_result.get("package"),
            "public_cli_apply_still_frozen": public_apply_before,
            "public_cli_reconcile_still_frozen": public_reconcile_before,
            "github_used": True,
            "network_required": True,
            "public_thaw_enabled": False,
            "auto_pull_enabled": False,
            "auto_pull_config_changed": False,
            "policy_persisted_to_device": False,
            "thaw_execution_performed": False,
            "updater_freeze_modified": False,
            "non_claims": [
                "no_auto_pull",
                "no_public_thaw",
                "no_staged_rollout",
                "no_stable_channel_manifest",
            ],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["passed"] else 1

    def health_hook(release_dir: Path, identity: dict[str, Any]) -> dict[str, Any]:
        return candidate_health.run_candidate_health(
            release_dir,
            identity,
            config_template=args.config_template,
            canary_media=args.canary_media,
            output_dir=work_dir / "candidate-health",
            duration_sec=args.duration_sec,
            interval_sec=args.interval_sec,
            startup_wait_sec=args.startup_wait_sec,
            panfrost_fault_policy=args.panfrost_fault_policy,
        )

    previous_hook = updatectl.PLAYER_RUNTIME_HEALTH_HOOK
    previous_thaw = updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED
    updatectl.PLAYER_RUNTIME_HEALTH_HOOK = health_hook
    updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
    before_snapshot = runtime_snapshot()
    try:
        rc = updatectl._apply_from_manifest_path_unfrozen(
            manifest_path,
            payload_url,
            f"github-lab-exact:{args.repo}:{args.tag}",
        )
    finally:
        after_snapshot = runtime_snapshot()
        updatectl.PLAYER_RUNTIME_HEALTH_HOOK = previous_hook
        updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = previous_thaw

    public_apply_after = public_cli_freeze(data_root, "apply")
    public_reconcile_after = public_cli_freeze(data_root, "reconcile")
    result = {
        "schema": "dadooh.c18.player_runtime.github_lab_apply.v1",
        "component": COMPONENT,
        "dry_run": False,
        "rc": rc,
        "passed": rc == 0 and public_apply_after["frozen"] and public_reconcile_after["frozen"],
        "delivery_mode": "operator_assisted",
        "selection": selection,
        "manifest_path": str(manifest_path),
        "release_gate_validated": bool(release_gate_result.get("passed")),
        "release_gate_package": release_gate_result.get("package"),
        "before": before_snapshot,
        "after": after_snapshot,
        "public_cli_apply_still_frozen": public_apply_after,
        "public_cli_reconcile_still_frozen": public_reconcile_after,
        "public_cli_apply_was_frozen_before": public_apply_before,
        "public_cli_reconcile_was_frozen_before": public_reconcile_before,
        "data_root": str(data_root),
        "device_data_root": data_root.resolve() == Path("/data"),
        "output_dir": str(work_dir),
        "github_used": True,
        "network_required": True,
        "public_thaw_enabled": False,
        "auto_pull_enabled": False,
        "auto_pull_config_changed": False,
        "policy_persisted_to_device": False,
        "thaw_execution_performed": False,
        "updater_freeze_modified": False,
        "non_claims": [
            "no_auto_pull",
            "no_public_thaw",
            "no_staged_rollout",
            "no_stable_channel_manifest",
        ],
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"player_runtime_github_lab_apply_passed={str(bool(result['passed'])).lower()}")
    return 0 if result["passed"] else (rc if rc else 1)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
