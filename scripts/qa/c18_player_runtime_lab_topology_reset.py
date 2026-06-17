#!/usr/bin/env python3
"""Lab-only topology reset for C18 player-runtime power-loss trials.

This governed bench tool prepares `/data/player-runtime` for a fresh physical
H2/P0 power-loss apply matrix by restoring a verified old current release and
removing only the target release directory when it is safe to do so. It is not a
public thaw path, does not publish, fetch, apply, rollback, or authorize stable.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BOARD_DIR = REPO_ROOT / "scripts" / "board"
QA_DIR = REPO_ROOT / "scripts" / "qa"
sys.path.insert(0, str(BOARD_DIR))
sys.path.insert(0, str(QA_DIR))

import c18_player_runtime_release_gate as release_gate  # noqa: E402
import totem_updatectl as updatectl  # noqa: E402


SCHEMA = "dadooh.c18.player_runtime.lab_topology_reset.v1"
LAB_ENV = "C18_PLAYER_RUNTIME_LAB_TOPOLOGY_RESET"
DEVICE_DATA_ENV = "C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT"
COMPONENT = "player-runtime"
NON_CLAIMS = (
    "not_powerloss_evidence",
    "not_17_17",
    "not_pilot_authorization",
    "not_stable_or_production",
    "not_public_thaw",
    "does_not_fetch_or_publish_releases",
    "does_not_apply_or_rollback_runtime",
)


def path_is_under(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    root_resolved = root.resolve()
    return resolved == root_resolved or root_resolved in resolved.parents


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


def configure_updatectl_for_lab(data_root: Path, policy_path: Path) -> None:
    updatectl.DATA_ROOT = data_root
    updatectl.UPDATES_DIR = updatectl.DATA_ROOT / "updates"
    updatectl.POLICY_FILE = policy_path
    updatectl.LOG_DIR = updatectl.DATA_ROOT / "logs"
    updatectl.LOG_FILE = updatectl.LOG_DIR / "totem-update.log"
    updatectl.TOKEN_FILE = updatectl.DATA_ROOT / "secrets" / "github-release-token"
    updatectl.configure_component(COMPONENT)


def write_lab_policy(policy_path: Path) -> None:
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


def public_cli_freeze(data_root: Path, action: str) -> dict[str, Any]:
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TOTEM_DATA_ROOT": str(data_root),
    }
    cmd = [sys.executable, str(BOARD_DIR / "totem_updatectl.py")]
    if action == "apply":
        missing = Path(tempfile.gettempdir()) / "c18-player-runtime-missing.manifest.json"
        cmd.extend(["apply-local", "--component", COMPONENT, str(missing)])
    elif action == "rollback":
        cmd.extend(["rollback", "--component", COMPONENT])
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
    quarantine = updatectl._quarantine_entries(state)
    return {
        "current_link": updatectl._read_symlink_target(updatectl.CURRENT_LINK),
        "previous_link": updatectl._read_symlink_target(updatectl.PREVIOUS_LINK),
        "current_exists": updatectl.CURRENT_LINK.exists() or updatectl.CURRENT_LINK.is_symlink(),
        "previous_exists": updatectl.PREVIOUS_LINK.exists() or updatectl.PREVIOUS_LINK.is_symlink(),
        "state_current_version": (state.get("current") or {}).get("version") if isinstance(state.get("current"), dict) else None,
        "state_previous_version": (state.get("previous") or {}).get("version") if isinstance(state.get("previous"), dict) else None,
        "last_operation": state.get("last_operation") if isinstance(state.get("last_operation"), dict) else None,
        "quarantine_count": len(quarantine),
        "quarantine_versions": sorted(str(entry.get("version") or "") for entry in quarantine if entry.get("version")),
    }


def payload_identity(manifest: dict[str, Any], payload: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c18-topology-reset-identity-") as tmp:
        release_dir = Path(tmp) / "release"
        release_dir.mkdir()
        updatectl._safe_extract_tar(payload, release_dir)
        return updatectl._player_runtime_identity(release_dir, manifest)


def marker_identity(link: str, marker: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": marker.get("version") or link.split("/")[-1],
        "payload_sha256": marker.get("payload_sha256"),
        "kiosk_py_sha256": marker.get("kiosk_py_sha256"),
        "tree_sha256": marker.get("tree_sha256"),
    }


def identity_matches(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        bool(left.get("version"))
        and left.get("version") == right.get("version")
        and bool(left.get("payload_sha256"))
        and left.get("payload_sha256") == right.get("payload_sha256")
        and bool(left.get("tree_sha256"))
        and left.get("tree_sha256") == right.get("tree_sha256")
    )


def release_link(version: str) -> str:
    if not version or "/" in version or version.startswith("."):
        raise RuntimeError("invalid_release_version")
    return f"releases/{version}"


def safe_remove_target_release(target_link: str) -> tuple[bool, str]:
    target_dir = updatectl.APP_BASE / target_link
    current = updatectl._read_symlink_target(updatectl.CURRENT_LINK)
    previous = updatectl._read_symlink_target(updatectl.PREVIOUS_LINK)
    if current == target_link or previous == target_link:
        return False, "target_release_linked"
    if not target_dir.exists():
        return True, "target_release_dir_absent"
    shutil.rmtree(target_dir)
    updatectl._fsync_dir(updatectl.RELEASES_DIR)
    return True, "target_release_dir_removed"


def prevalidate_target_release_for_removal(target_link: str, target_identity: dict[str, Any]) -> tuple[list[str], str]:
    target_dir = updatectl.APP_BASE / target_link
    blockers: list[str] = []
    try:
        target_dir.relative_to(updatectl.RELEASES_DIR)
    except ValueError:
        blockers.append("target_release_dir_outside_releases")
    if target_dir.is_symlink():
        blockers.append("target_release_dir_symlink")
    if not target_dir.exists():
        return blockers, "target_release_dir_absent"
    if not target_dir.is_dir():
        blockers.append("target_release_path_not_dir")
        return blockers, "target_release_path_not_dir"
    ok, info, marker = updatectl._validate_player_runtime_marker(target_dir)
    if not ok:
        blockers.append(f"target_release_marker_invalid:{info}")
        return blockers, "target_release_marker_invalid"
    if not identity_matches(marker_identity(target_link, marker), target_identity):
        blockers.append("target_release_marker_identity_mismatch")
        return blockers, "target_release_marker_identity_mismatch"
    return blockers, "target_release_dir_verified_for_removal"


def restore_topology(current_link: Any, previous_link: Any, state: dict[str, Any]) -> None:
    if isinstance(current_link, str) and current_link:
        updatectl._atomic_symlink(current_link, updatectl.CURRENT_LINK)
    elif updatectl.CURRENT_LINK.is_symlink() or updatectl.CURRENT_LINK.exists():
        updatectl.CURRENT_LINK.unlink()
        updatectl._fsync_dir(updatectl.CURRENT_LINK.parent)
    if isinstance(previous_link, str) and previous_link:
        updatectl._atomic_symlink(previous_link, updatectl.PREVIOUS_LINK)
    elif updatectl.PREVIOUS_LINK.is_symlink() or updatectl.PREVIOUS_LINK.exists():
        updatectl.PREVIOUS_LINK.unlink()
        updatectl._fsync_dir(updatectl.PREVIOUS_LINK.parent)
    updatectl._write_state(state)


def build_result(
    *,
    passed: bool,
    blockers: list[str],
    work_dir: Path,
    data_root: Path,
    manifest: dict[str, Any] | None = None,
    target_identity: dict[str, Any] | None = None,
    previous_identity: dict[str, Any] | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    public_before: dict[str, dict[str, Any]] | None = None,
    public_after: dict[str, dict[str, Any]] | None = None,
    removed_target_release_dir: str | None = None,
    target_release_prevalidation: str | None = None,
    reset_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "component": COMPONENT,
        "passed": passed,
        "result_claim": "player_runtime_lab_topology_reset_prepared" if passed else "player_runtime_lab_topology_reset_blocked",
        "blockers": blockers,
        "version": (manifest or {}).get("version"),
        "channel": (manifest or {}).get("channel"),
        "source_commit": (manifest or {}).get("source_commit"),
        "target_identity": target_identity,
        "previous_identity": previous_identity,
        "reset_reason": reset_reason,
        "target_release_prevalidation": target_release_prevalidation,
        "removed_target_release_dir": removed_target_release_dir,
        "before": before,
        "after": after,
        "public_cli_apply_frozen_before_reset": (public_before or {}).get("apply"),
        "public_cli_rollback_frozen_before_reset": (public_before or {}).get("rollback"),
        "public_cli_reconcile_frozen_before_reset": (public_before or {}).get("reconcile"),
        "public_cli_apply_still_frozen": (public_after or {}).get("apply"),
        "public_cli_rollback_still_frozen": (public_after or {}).get("rollback"),
        "public_cli_reconcile_still_frozen": (public_after or {}).get("reconcile"),
        "data_root": str(data_root),
        "device_data_root": data_root.resolve() == Path("/data"),
        "output_dir": str(work_dir),
        "network_required": False,
        "github_used": False,
        "non_claims": list(NON_CLAIMS),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--lab-only-topology-reset", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--previous-version")
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--allow-device-data-root", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--reason", default="h2_powerloss_topology_prep")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def run_self_test() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    for token in (
        "C18_PLAYER_RUNTIME_LAB_TOPOLOGY_RESET",
        "C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT",
        "--lab-only-topology-reset",
        "--allow-device-data-root",
        "release_gate.validate_release",
        "_validate_player_runtime_marker",
        "_atomic_symlink",
        "_write_state",
        "prevalidate_target_release_for_removal",
        "restore_topology",
        "public_cli_apply_frozen_before_reset",
        "public_cli_apply_still_frozen",
        "not_public_thaw",
        "does_not_apply_or_rollback_runtime",
        "target_release_linked",
        "target_release_dir_removed",
        "target_release_marker_identity_mismatch",
    ):
        if token not in source:
            raise AssertionError(f"missing topology reset token: {token}")
    with tempfile.TemporaryDirectory(prefix="c18-topology-reset-self-test-") as tmp:
        root = Path(tmp)
        nested = root / "a" / "b"
        nested.mkdir(parents=True)
        if not path_is_under(nested, root):
            raise AssertionError("path guard failed")
        if path_is_under(root, nested):
            raise AssertionError("reverse path guard failed")


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        run_self_test()
        return 0
    if not args.lab_only_topology_reset or os.environ.get(LAB_ENV) != "1":
        print(
            f"player_runtime_lab_topology_reset_guard_required: pass --lab-only-topology-reset and set {LAB_ENV}=1",
            file=sys.stderr,
        )
        return 44
    if args.manifest is None or args.payload is None or not args.previous_version:
        print("manifest_payload_previous_required", file=sys.stderr)
        return 42

    work_dir = args.output_dir or Path(tempfile.mkdtemp(prefix="c18-player-runtime-lab-topology-reset-"))
    data_root = args.data_root or (work_dir / "data")
    ok, guard_reason = guarded_paths(args, work_dir, data_root)
    if not ok:
        print(guard_reason, file=sys.stderr)
        return 43

    manifest: dict[str, Any] | None = None
    target_identity: dict[str, Any] | None = None
    previous_identity: dict[str, Any] | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    public_before: dict[str, dict[str, Any]] | None = None
    public_after: dict[str, dict[str, Any]] | None = None
    removed_status: str | None = None
    target_prevalidation: str | None = None
    blockers: list[str] = []
    try:
        manifest = read_json(args.manifest)
        release_gate.validate_release(args.manifest, args.payload)
        if manifest.get("channel") != "homologation":
            blockers.append("manifest_channel_not_homologation")

        policy_path = work_dir / "lab-policy.json"
        write_lab_policy(policy_path)
        configure_updatectl_for_lab(data_root, policy_path)
        target_identity = payload_identity(manifest, args.payload)
        target_link = release_link(str(target_identity.get("version") or ""))
        previous_link = release_link(args.previous_version)

        public_before = {
            "apply": public_cli_freeze(data_root, "apply"),
            "rollback": public_cli_freeze(data_root, "rollback"),
            "reconcile": public_cli_freeze(data_root, "reconcile"),
        }
        if not all(item.get("frozen") is True for item in public_before.values()):
            blockers.append("public_cli_not_frozen_before_reset")

        before = runtime_snapshot()
        state = updatectl._read_state()
        state_before = json.loads(json.dumps(state))
        previous_dir = updatectl.APP_BASE / previous_link
        previous_ok, previous_info, previous_marker = updatectl._validate_player_runtime_marker(previous_dir, state)
        if not previous_ok:
            blockers.append(f"previous_release_marker_invalid:{previous_info}")
        else:
            previous_identity = marker_identity(previous_link, previous_marker)
            if previous_identity.get("version") != args.previous_version:
                blockers.append("previous_release_marker_version_mismatch")
            if identity_matches(previous_identity, target_identity):
                blockers.append("previous_release_matches_target_identity")

        quarantine_entries = updatectl._quarantine_entries(state)
        target_quarantined = any(
            entry.get("version") == target_identity.get("version")
            or (
                entry.get("payload_sha256")
                and entry.get("payload_sha256") == target_identity.get("payload_sha256")
            )
            or (
                entry.get("tree_sha256")
                and entry.get("tree_sha256") == target_identity.get("tree_sha256")
            )
            for entry in quarantine_entries
        )
        if target_quarantined:
            blockers.append("target_identity_quarantined")

        current_link = before.get("current_link")
        previous_before = before.get("previous_link")
        if current_link not in (target_link, previous_link, None):
            blockers.append("unexpected_current_link_before_reset")
        if previous_before == target_link:
            blockers.append("target_is_previous_link_before_reset")
        target_prevalidation_blockers, target_prevalidation = prevalidate_target_release_for_removal(
            target_link,
            target_identity,
        )
        blockers.extend(target_prevalidation_blockers)

        if not blockers:
            if updatectl.PREVIOUS_LINK.is_symlink() or updatectl.PREVIOUS_LINK.exists():
                updatectl.PREVIOUS_LINK.unlink()
                updatectl._fsync_dir(updatectl.PREVIOUS_LINK.parent)
            updatectl._atomic_symlink(previous_link, updatectl.CURRENT_LINK)
            state["schema"] = updatectl.SCHEMA_STATE
            state["component"] = COMPONENT
            state["current"] = updatectl._player_runtime_state_entry_from_marker(
                previous_link,
                previous_marker,
                "lab_topology_reset",
            )
            state["previous"] = None
            state["last_operation"] = {
                "type": "lab_topology_reset",
                "status": "success",
                "started_at_utc": updatectl._utcnow_iso(),
                "finished_at_utc": updatectl._utcnow_iso(),
                "reason": args.reason,
                "target_version_removed": target_identity.get("version"),
                "current_restored_to": args.previous_version,
            }
            updatectl._write_state(state)
            try:
                remove_ok, removed_status = safe_remove_target_release(target_link)
            except Exception as exc:
                blockers.append(f"target_release_remove_exception:{type(exc).__name__}")
                restore_topology(current_link, previous_before, state_before)
            else:
                if not remove_ok:
                    blockers.append(removed_status)
                    restore_topology(current_link, previous_before, state_before)

        after = runtime_snapshot()
        public_after = {
            "apply": public_cli_freeze(data_root, "apply"),
            "rollback": public_cli_freeze(data_root, "rollback"),
            "reconcile": public_cli_freeze(data_root, "reconcile"),
        }
        if not all(item.get("frozen") is True for item in public_after.values()):
            blockers.append("public_cli_not_frozen_after_reset")
        if not blockers:
            if after.get("current_link") != previous_link:
                blockers.append("current_link_not_previous_after_reset")
            if after.get("previous_link") is not None:
                blockers.append("previous_link_not_absent_after_reset")
            if after.get("state_current_version") != args.previous_version:
                blockers.append("state_current_version_not_previous_after_reset")
            target_dir = updatectl.APP_BASE / target_link
            if target_dir.exists() or target_dir.is_symlink():
                blockers.append("target_release_dir_still_exists_after_reset")
    except Exception as exc:
        blockers.append(f"topology_reset_exception:{type(exc).__name__}")

    passed = not blockers
    result = build_result(
        passed=passed,
        blockers=blockers,
        work_dir=work_dir,
        data_root=data_root,
        manifest=manifest,
        target_identity=target_identity,
        previous_identity=previous_identity,
        before=before,
        after=after,
        public_before=public_before,
        public_after=public_after,
        removed_target_release_dir=removed_status,
        target_release_prevalidation=target_prevalidation,
        reset_reason=args.reason,
    )
    write_json(work_dir / "topology-reset.json", result)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"player_runtime_lab_topology_reset_passed={str(bool(result['passed'])).lower()}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
