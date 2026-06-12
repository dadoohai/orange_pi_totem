#!/usr/bin/env python3
"""Lab-only quarantine reset for a C18 player-runtime target.

This is a governed bench reset for repeating physical P0 power-loss trials after
an intentionally quarantining rollback checkpoint. It removes only the
quarantine entry matching the validated manifest/payload identity. It does not
thaw the public updater CLI, publish, fetch, apply, rollback, or touch symlinks.
"""

from __future__ import annotations

import argparse
import json
import os
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

import c18_player_runtime_release_gate as release_gate
import totem_updatectl as updatectl


LAB_ENV = "C18_PLAYER_RUNTIME_LAB_QUARANTINE_RESET"
DEVICE_DATA_ENV = "C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT"
COMPONENT = "player-runtime"
SCHEMA = "dadooh.c18.player_runtime.lab_quarantine_reset.v1"
RESET_SCOPES = {
    "p0_rollback_after_quarantine",
    "p0_rollback_after_state_success",
    "p0_isolation_reset",
}
ALLOWED_QUARANTINE_REASONS = {"physical_powerloss_trial"}


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


def write_lab_policy(policy_path: Path, channel: str) -> None:
    if channel != "homologation":
        raise RuntimeError("quarantine reset only accepts homologation player-runtime packages")
    write_json(
        policy_path,
        {
            "schema": "dadooh.totem.update.policy.v1",
            "device_channel": channel,
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
        cmd.extend(["apply-local", str(missing), "--component", COMPONENT])
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
        "quarantine_versions": sorted(str(entry.get("version") or "") for entry in quarantine),
    }


def payload_identity(manifest: dict[str, Any], payload: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c18-quarantine-reset-identity-") as tmp:
        release_dir = Path(tmp) / "release"
        release_dir.mkdir()
        updatectl._safe_extract_tar(payload, release_dir)
        return updatectl._player_runtime_identity(release_dir, manifest)


def identity_matches_target(entry: dict[str, Any], identity: dict[str, Any]) -> bool:
    if entry.get("version") != identity.get("version"):
        return False
    payload_match = bool(entry.get("payload_sha256")) and entry.get("payload_sha256") == identity.get("payload_sha256")
    tree_match = bool(entry.get("tree_sha256")) and entry.get("tree_sha256") == identity.get("tree_sha256")
    return payload_match or tree_match


def quarantine_reason_allowed(entry: dict[str, Any]) -> bool:
    return str(entry.get("reason") or "") in ALLOWED_QUARANTINE_REASONS


def matches_target(entry: dict[str, Any], identity: dict[str, Any]) -> bool:
    return identity_matches_target(entry, identity) and quarantine_reason_allowed(entry)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--lab-only-quarantine-reset", action="store_true")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--allow-device-data-root", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--reset-scope", choices=sorted(RESET_SCOPES), required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.lab_only_quarantine_reset or os.environ.get(LAB_ENV) != "1":
        print(
            f"player_runtime_lab_quarantine_reset_guard_required: pass --lab-only-quarantine-reset and set {LAB_ENV}=1",
            file=sys.stderr,
        )
        return 44

    work_dir = args.output_dir or Path(tempfile.mkdtemp(prefix="c18-player-runtime-lab-quarantine-reset-"))
    data_root = args.data_root or (work_dir / "data")
    ok, guard_reason = guarded_paths(args, work_dir, data_root)
    if not ok:
        print(guard_reason, file=sys.stderr)
        return 43

    manifest = read_json(args.manifest)
    release_gate.validate_release(args.manifest, args.payload)
    identity = payload_identity(manifest, args.payload)
    channel = str(manifest.get("channel") or "")
    if channel != "homologation":
        result = {
            "schema": SCHEMA,
            "component": COMPONENT,
            "passed": False,
            "blockers": ["manifest_channel_not_homologation"],
            "version": identity.get("version"),
            "channel": channel,
            "target_identity": identity,
            "reset_scope": args.reset_scope,
            "reason": args.reason,
            "removed_count": 0,
            "data_root": str(data_root),
            "device_data_root": data_root.resolve() == Path("/data"),
            "output_dir": str(work_dir),
            "network_required": False,
            "github_used": False,
            "non_claims": [
                "not_a_public_thaw",
                "not_stable_or_production",
                "does_not_apply_or_rollback_runtime",
            ],
        }
        write_json(work_dir / "quarantine-reset.json", result)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("player_runtime_lab_quarantine_reset_passed=false")
        return 42
    policy_path = work_dir / "lab-policy.json"
    write_lab_policy(policy_path, channel)
    configure_updatectl_for_lab(data_root, policy_path)

    public_before = {
        "apply": public_cli_freeze(data_root, "apply"),
        "rollback": public_cli_freeze(data_root, "rollback"),
        "reconcile": public_cli_freeze(data_root, "reconcile"),
    }
    before_snapshot = runtime_snapshot()
    state = updatectl._read_state()
    before_quarantine = updatectl._quarantine_entries(state)
    target_link = f"releases/{identity.get('version')}"
    active_links = [
        name
        for name, link in (
            ("current", before_snapshot.get("current_link")),
            ("previous", before_snapshot.get("previous_link")),
        )
        if link == target_link
    ]
    matching_entries = [entry for entry in before_quarantine if identity_matches_target(entry, identity)]
    disallowed_entries = [entry for entry in matching_entries if not quarantine_reason_allowed(entry)]
    removed = [entry for entry in matching_entries if quarantine_reason_allowed(entry)]
    blockers: list[str] = []
    if not all(item["frozen"] for item in public_before.values()):
        blockers.append("public_cli_not_frozen_before_reset")
    if active_links:
        blockers.append("target_linked_active")
    if disallowed_entries:
        blockers.append("target_quarantine_reason_not_allowed")
    if not matching_entries:
        blockers.append("target_quarantine_not_found")
    if blockers:
        still_quarantined, quarantine_reason = updatectl._player_runtime_is_quarantined(identity, state)
        after_snapshot = runtime_snapshot()
        result = {
            "schema": SCHEMA,
            "component": COMPONENT,
            "passed": False,
            "blockers": blockers,
            "version": identity.get("version"),
            "channel": channel,
            "target_identity": identity,
            "reset_scope": args.reset_scope,
            "reason": args.reason,
            "removed_count": 0,
            "removed_entries": [],
            "matching_disallowed_entries": disallowed_entries,
            "active_links": active_links,
            "still_quarantined": still_quarantined,
            "quarantine_reason": quarantine_reason,
            "links_unchanged": (
                before_snapshot.get("current_link") == after_snapshot.get("current_link")
                and before_snapshot.get("previous_link") == after_snapshot.get("previous_link")
            ),
            "before": before_snapshot,
            "after": after_snapshot,
            "public_cli_apply_frozen_before_reset": public_before["apply"],
            "public_cli_rollback_frozen_before_reset": public_before["rollback"],
            "public_cli_reconcile_frozen_before_reset": public_before["reconcile"],
            "public_cli_apply_still_frozen": public_before["apply"],
            "public_cli_rollback_still_frozen": public_before["rollback"],
            "public_cli_reconcile_still_frozen": public_before["reconcile"],
            "data_root": str(data_root),
            "device_data_root": data_root.resolve() == Path("/data"),
            "output_dir": str(work_dir),
            "network_required": False,
            "github_used": False,
            "non_claims": [
                "not_a_public_thaw",
                "not_stable_or_production",
                "does_not_apply_or_rollback_runtime",
            ],
        }
        write_json(work_dir / "quarantine-reset.json", result)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("player_runtime_lab_quarantine_reset_passed=false")
        return 1

    removed_ids = {id(entry) for entry in removed}
    remaining = [entry for entry in before_quarantine if id(entry) not in removed_ids]
    if removed:
        started_at = updatectl._utcnow_iso()
        state["quarantine"] = remaining
        state["last_operation"] = {
            "type": "lab_quarantine_reset",
            "status": "success",
            "started_at_utc": started_at,
            "finished_at_utc": updatectl._utcnow_iso(),
            "version": identity.get("version"),
            "payload_sha256": identity.get("payload_sha256"),
            "tree_sha256": identity.get("tree_sha256"),
            "reason": args.reason,
            "reset_scope": args.reset_scope,
            "removed_count": len(removed),
            "non_claims": [
                "not_a_public_thaw",
                "not_stable_or_production",
                "does_not_apply_or_rollback_runtime",
            ],
        }
        updatectl._write_state(state)

    public_after = {
        "apply": public_cli_freeze(data_root, "apply"),
        "rollback": public_cli_freeze(data_root, "rollback"),
        "reconcile": public_cli_freeze(data_root, "reconcile"),
    }
    reverted = False
    post_blockers: list[str] = []
    if not all(item["frozen"] for item in public_after.values()):
        post_blockers.append("public_cli_not_frozen_after_reset")
        rollback_state = updatectl._read_state()
        rollback_state["quarantine"] = before_quarantine
        rollback_state["last_operation"] = {
            "type": "lab_quarantine_reset",
            "status": "reverted",
            "finished_at_utc": updatectl._utcnow_iso(),
            "version": identity.get("version"),
            "payload_sha256": identity.get("payload_sha256"),
            "tree_sha256": identity.get("tree_sha256"),
            "reason": args.reason,
            "reset_scope": args.reset_scope,
            "rollback_reason": "public_cli_not_frozen_after_reset",
        }
        updatectl._write_state(rollback_state)
        reverted = True
    after_snapshot = runtime_snapshot()
    after_state = updatectl._read_state()
    still_quarantined, quarantine_reason = updatectl._player_runtime_is_quarantined(identity, after_state)
    links_unchanged = (
        before_snapshot.get("current_link") == after_snapshot.get("current_link")
        and before_snapshot.get("previous_link") == after_snapshot.get("previous_link")
    )
    passed = (
        bool(removed)
        and not still_quarantined
        and links_unchanged
        and all(item["frozen"] for item in public_before.values())
        and all(item["frozen"] for item in public_after.values())
    )
    result = {
        "schema": SCHEMA,
        "component": COMPONENT,
        "passed": passed,
        "blockers": post_blockers,
        "version": identity.get("version"),
        "channel": channel,
        "target_identity": identity,
        "reset_scope": args.reset_scope,
        "reason": args.reason,
        "removed_count": len(removed),
        "removed_entries": removed,
        "matching_disallowed_entries": [],
        "active_links": active_links,
        "reverted": reverted,
        "still_quarantined": still_quarantined,
        "quarantine_reason": quarantine_reason,
        "links_unchanged": links_unchanged,
        "before": before_snapshot,
        "after": after_snapshot,
        "public_cli_apply_frozen_before_reset": public_before["apply"],
        "public_cli_rollback_frozen_before_reset": public_before["rollback"],
        "public_cli_reconcile_frozen_before_reset": public_before["reconcile"],
        "public_cli_apply_still_frozen": public_after["apply"],
        "public_cli_rollback_still_frozen": public_after["rollback"],
        "public_cli_reconcile_still_frozen": public_after["reconcile"],
        "data_root": str(data_root),
        "device_data_root": data_root.resolve() == Path("/data"),
        "output_dir": str(work_dir),
        "network_required": False,
        "github_used": False,
        "non_claims": [
            "not_a_public_thaw",
            "not_stable_or_production",
            "does_not_apply_or_rollback_runtime",
        ],
    }
    write_json(work_dir / "quarantine-reset.json", result)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"player_runtime_lab_quarantine_reset_passed={str(bool(passed)).lower()}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
