#!/usr/bin/env python3
"""Lab-only local apply harness for C18 player-runtime packages.

This is not a production thaw path. The public totem-updatectl CLI keeps
returning rc=44 for player-runtime. This harness exists so a lab operator can
exercise the internal verify-then-promote path with a local manifest/payload
and the candidate deep-health hook, without changing the device policy file or
enabling GitHub/auto-pull.
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
sys.path.insert(0, str(REPO_ROOT / "scripts" / "qa"))

import c18_player_runtime_candidate_health as candidate_health
import c18_player_runtime_release_gate as release_gate
import totem_updatectl as updatectl


LAB_ENV = "C18_PLAYER_RUNTIME_LAB_APPLY"
DEVICE_DATA_ENV = "C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT"
COMPONENT = "player-runtime"


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
    if channel not in {"lab", "homologation"}:
        raise RuntimeError("lab apply only accepts lab or homologation player-runtime packages")
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


def public_cli_still_frozen(data_root: Path) -> dict[str, Any]:
    missing = Path(tempfile.gettempdir()) / "c18-player-runtime-missing.manifest.json"
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TOTEM_DATA_ROOT": str(data_root),
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(BOARD_DIR / "totem_updatectl.py"),
            "apply-local",
            "--component",
            COMPONENT,
            str(missing),
        ],
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab-only-apply", action="store_true")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--allow-device-data-root", action="store_true")
    parser.add_argument("--config-template", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--duration-sec", type=float, default=30.0)
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--startup-wait-sec", type=float, default=5.0)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.lab_only_apply or os.environ.get(LAB_ENV) != "1":
        print(f"player_runtime_lab_apply_guard_required: pass --lab-only-apply and set {LAB_ENV}=1", file=sys.stderr)
        return 44

    work_dir = args.output_dir or Path(tempfile.mkdtemp(prefix="c18-player-runtime-lab-apply-"))
    data_root = args.data_root or (work_dir / "data")
    ok, reason = guarded_paths(args, work_dir, data_root)
    if not ok:
        print(reason, file=sys.stderr)
        return 43

    manifest = read_json(args.manifest)
    release_gate.validate_release(args.manifest, args.payload)
    policy_path = work_dir / "lab-policy.json"
    write_lab_policy(policy_path, str(manifest.get("channel") or ""))
    configure_updatectl_for_lab(data_root, policy_path)

    def health_hook(release_dir: Path, identity: dict[str, Any]) -> dict[str, Any]:
        return candidate_health.run_candidate_health(
            release_dir,
            identity,
            config_template=args.config_template,
            output_dir=work_dir / "candidate-health",
            duration_sec=args.duration_sec,
            interval_sec=args.interval_sec,
            startup_wait_sec=args.startup_wait_sec,
        )

    previous_hook = updatectl.PLAYER_RUNTIME_HEALTH_HOOK
    previous_thaw = updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED
    updatectl.PLAYER_RUNTIME_HEALTH_HOOK = health_hook
    updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
    try:
        rc = updatectl._apply_from_manifest_path_unfrozen(
            args.manifest,
            payload_url=None,
            source=f"lab-local:{args.manifest.name}",
            payload_path_override=args.payload,
        )
    finally:
        updatectl.PLAYER_RUNTIME_HEALTH_HOOK = previous_hook
        updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = previous_thaw

    public_freeze = public_cli_still_frozen(data_root)
    result = {
        "schema": "dadooh.c18.player_runtime.lab_apply.v1",
        "component": COMPONENT,
        "version": manifest.get("version"),
        "channel": manifest.get("channel"),
        "rc": rc,
        "passed": rc == 0 and public_freeze["frozen"],
        "public_cli_apply_still_frozen": public_freeze,
        "data_root": str(data_root),
        "device_data_root": data_root.resolve() == Path("/data"),
        "output_dir": str(work_dir),
        "network_required": False,
        "github_used": False,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"player_runtime_lab_apply_passed={str(bool(result['passed'])).lower()}")
    return 0 if result["passed"] else (rc if rc else 1)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
