#!/usr/bin/env python3
"""Lab-only rollback/reconcile harness for C18 player-runtime.

This is the symmetric escape hatch for `c18_player_runtime_lab_apply.py`.
It does not thaw the public updater CLI, does not use GitHub, and only touches
`/data` when the operator supplies both the explicit flag and environment var.
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
sys.path.insert(0, str(BOARD_DIR))

import totem_updatectl as updatectl


LAB_ENV = "C18_PLAYER_RUNTIME_LAB_ROLLBACK"
DEVICE_DATA_ENV = "C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT"
COMPONENT = "player-runtime"


def path_is_under(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    root_resolved = root.resolve()
    return resolved == root_resolved or root_resolved in resolved.parents


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
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TOTEM_DATA_ROOT": str(data_root),
    }
    cmd = [
        sys.executable,
        str(BOARD_DIR / "totem_updatectl.py"),
    ]
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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--lab-only-rollback", action="store_true")
    parser.add_argument("--action", choices=("rollback", "reconcile"), default="rollback")
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--allow-device-data-root", action="store_true")
    parser.add_argument("--quarantine-current", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--reason", default="lab_player_runtime_rollback")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.lab_only_rollback or os.environ.get(LAB_ENV) != "1":
        print(f"player_runtime_lab_rollback_guard_required: pass --lab-only-rollback and set {LAB_ENV}=1", file=sys.stderr)
        return 44

    work_dir = args.output_dir or Path(tempfile.mkdtemp(prefix="c18-player-runtime-lab-rollback-"))
    data_root = args.data_root or (work_dir / "data")
    ok, reason = guarded_paths(args, work_dir, data_root)
    if not ok:
        print(reason, file=sys.stderr)
        return 43

    policy_path = work_dir / "lab-policy.json"
    write_lab_policy(policy_path)
    configure_updatectl_for_lab(data_root, policy_path)

    previous_thaw = updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED
    updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
    before_snapshot = runtime_snapshot()
    try:
        if args.action == "rollback":
            rc = updatectl._rollback_player_runtime_unfrozen(
                reason=args.reason,
                quarantine_current=args.quarantine_current,
            )
            after_snapshot = runtime_snapshot()
            operation: dict[str, Any] = {
                "action": "rollback",
                "rc": rc,
                "result": "ok" if rc == 0 else "failed",
                "quarantine_current": bool(args.quarantine_current),
                "before": before_snapshot,
                "after": after_snapshot,
                "rolled_back_to": (
                    (after_snapshot.get("current_link") or "").split("/")[-1]
                    if after_snapshot.get("current_link")
                    else "image_fallback"
                ),
            }
        else:
            rc, reconcile = updatectl._reconcile_player_runtime_state(reason=args.reason)
            after_snapshot = runtime_snapshot()
            operation = {
                "action": "reconcile",
                "rc": rc,
                "result": reconcile.get("status"),
                "reconcile": reconcile,
                "before": before_snapshot,
                "after": after_snapshot,
            }
    finally:
        updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = previous_thaw

    public_apply = public_cli_freeze(data_root, "apply")
    public_rollback = public_cli_freeze(data_root, "rollback")
    public_reconcile = public_cli_freeze(data_root, "reconcile")
    result = {
        "schema": "dadooh.c18.player_runtime.lab_rollback.v1",
        "component": COMPONENT,
        "passed": (
            rc == 0
            and public_apply["frozen"]
            and public_rollback["frozen"]
            and public_reconcile["frozen"]
        ),
        "operation": operation,
        "public_cli_apply_still_frozen": public_apply,
        "public_cli_rollback_still_frozen": public_rollback,
        "public_cli_reconcile_still_frozen": public_reconcile,
        "data_root": str(data_root),
        "device_data_root": data_root.resolve() == Path("/data"),
        "output_dir": str(work_dir),
        "network_required": False,
        "github_used": False,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"player_runtime_lab_rollback_passed={str(bool(result['passed'])).lower()}")
    return 0 if result["passed"] else (rc if rc else 1)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
