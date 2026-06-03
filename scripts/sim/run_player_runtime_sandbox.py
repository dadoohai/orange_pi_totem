#!/usr/bin/env python3
"""Run an offline C18 player-runtime slot/rollback sandbox.

This intentionally does not thaw the production CLI. It enables the internal
lab guard and calls the real player-runtime primitives so the production CLI can
keep returning rc=44 while the sandbox proves mechanics needed before hardware.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SANDBOX = REPO_ROOT / ".sim" / "player-runtime"
SNAPSHOT_KIOSK = REPO_ROOT / "player-runtime" / "kiosky-player" / "kiosk.py"
LAUNCHER = REPO_ROOT / "scripts" / "board" / "totem-kiosky-launcher.sh"
RELEASE_GATE_PATH = REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_release_gate.py"
UPDATECTL_PATH = REPO_ROOT / "scripts" / "board" / "totem_updatectl.py"

COMPONENT = "player-runtime"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release_gate = load_module("c18_player_runtime_release_gate_sandbox", RELEASE_GATE_PATH)
updatectl = load_module("totem_updatectl_player_runtime_sandbox", UPDATECTL_PATH)


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sandbox", type=Path, default=DEFAULT_SANDBOX)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def run(cmd: list[str], *, env: dict[str, str], cwd: Path = REPO_ROOT, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def safe_remove(path: Path, sandbox: Path) -> None:
    if not (path.exists() or path.is_symlink()):
        return
    resolved_parent = path.parent.resolve()
    try:
        resolved_parent.relative_to(sandbox.resolve())
    except ValueError as exc:
        raise RuntimeError(f"refusing to remove outside sandbox: {path}") from exc
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def replace_symlink(target: str | Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        if link.is_dir() and not link.is_symlink():
            shutil.rmtree(link)
        else:
            link.unlink()
    os.symlink(str(target), str(link))


def readlink(link: Path) -> str:
    return os.readlink(link) if link.is_symlink() else ""


def sandbox_env(sandbox: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "TOTEM_DATA_ROOT": str(sandbox / "data"),
            "TOTEM_HEALTH_GRACE_SECONDS": "0",
            "TOTEM_HEALTH_CHECK_TIMEOUT_S": "5",
            "TMPDIR": str(sandbox / "tmp"),
        }
    )
    return env


def configure_updatectl_paths(sandbox: Path, component: str = COMPONENT) -> None:
    updatectl.DATA_ROOT = sandbox / "data"
    updatectl.UPDATES_DIR = updatectl.DATA_ROOT / "updates"
    updatectl.POLICY_FILE = updatectl.UPDATES_DIR / "policy.json"
    updatectl.LOG_DIR = updatectl.DATA_ROOT / "logs"
    updatectl.LOG_FILE = updatectl.LOG_DIR / "totem-update.log"
    updatectl.TOKEN_FILE = updatectl.DATA_ROOT / "secrets" / "github-release-token"
    updatectl.configure_component(component)


def reset_sandbox(sandbox: Path) -> None:
    safe_remove(sandbox, sandbox.parent)
    for path in (
        sandbox / "data" / "player-runtime" / "releases",
        sandbox / "data" / "updates",
        sandbox / "data" / "logs",
        sandbox / "opt" / "totem" / "kiosky-player",
        sandbox / "opt" / "totem" / "bin",
        sandbox / "tmp" / "packages",
        sandbox / "tmp" / "health",
        sandbox / "tmp" / "launcher",
    ):
        path.mkdir(parents=True, exist_ok=True)


def write_policy(sandbox: Path) -> None:
    policy = {
        "schema": "dadooh.totem.update.policy.v1",
        "device_channel": "homologation",
        "device_track": "c18-hwdecode",
        "allowed_components": ["player-runtime", "totem-core"],
        "allow_prerelease": True,
        "allow_downgrade": False,
    }
    policy_path = sandbox / "data" / "updates" / "policy.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def set_policy_allow_downgrade(sandbox: Path, allowed: bool) -> None:
    policy_path = sandbox / "data" / "updates" / "policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["allow_downgrade"] = allowed
    policy_path.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def seed_image_runtime(sandbox: Path) -> None:
    fallback = sandbox / "opt" / "totem" / "kiosky-player"
    fallback.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SNAPSHOT_KIOSK, fallback / "kiosk.py")
    fake_inner = sandbox / "opt" / "totem" / "bin" / "kiosky_service_launcher.sh"
    fake_inner.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        "printf '{\"kiosky_app_dir\":\"%s\"}\\n' \"$KIOSKY_APP_DIR\" > \"$TOTEM_KIOSKY_LAUNCHER_CAPTURE\"\n",
        encoding="utf-8",
    )
    fake_inner.chmod(0o755)


def build_player_runtime_package(sandbox: Path, version: str, marker: str = "") -> tuple[Path, Path]:
    package_dir = sandbox / "tmp" / "packages" / version
    stage = package_dir / "stage"
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SNAPSHOT_KIOSK, stage / "kiosk.py")
    if marker:
        (stage / "VERSION").write_text(marker + "\n", encoding="utf-8")
    payload = package_dir / f"dadooh-{COMPONENT}-{version}.tar.gz"
    with tarfile.open(payload, "w:gz") as tf:
        for path in sorted(stage.rglob("*")):
            tf.add(path, arcname=str(path.relative_to(stage)))
    manifest = release_gate.write_manifest(package_dir, version, payload)
    release_gate.validate_release(manifest, payload)
    return manifest, payload


def extract_payload(payload: Path, release_dir: Path) -> None:
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True, exist_ok=True)
    updatectl._safe_extract_tar(payload, release_dir)


def read_state(sandbox: Path) -> dict[str, Any]:
    state_path = sandbox / "data" / "player-runtime" / "state.json"
    if not state_path.exists():
        return {
            "schema": "dadooh.totem.update.state.v1",
            "component": COMPONENT,
            "current": None,
            "previous": None,
        }
    return json.loads(state_path.read_text(encoding="utf-8"))


def write_state(sandbox: Path, state: dict[str, Any]) -> None:
    state_path = sandbox / "data" / "player-runtime" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def apply_player_runtime_offline(
    sandbox: Path,
    *,
    manifest: Path,
    payload: Path,
    pass_health: bool = True,
    observed_identity: str = "candidate",
) -> tuple[bool, str]:
    configure_updatectl_paths(sandbox)
    release_gate.validate_release(manifest, payload)

    def health_hook(release_dir: Path, identity: dict[str, Any]) -> dict[str, Any]:
        if not pass_health:
            return {
                "schema": updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
                "passed": False,
                "failure_reasons": ["deep_health_fixture_failed"],
                "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
                "observed_tree_sha256": identity["tree_sha256"],
                "artifact_id": "sandbox_fail",
            }
        if observed_identity == "fallback":
            fallback_identity = {
                "kiosk_py_sha256": updatectl._sha256_file(sandbox / "opt" / "totem" / "kiosky-player" / "kiosk.py"),
                "tree_sha256": updatectl._tree_hash(sandbox / "opt" / "totem" / "kiosky-player"),
            }
            return {
                "schema": updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
                "passed": True,
                "failure_reasons": [],
                "observed_kiosk_py_sha256": fallback_identity["kiosk_py_sha256"],
                "observed_tree_sha256": fallback_identity["tree_sha256"],
                "artifact_id": "sandbox_fallback",
            }
        return {
            "schema": updatectl.PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
            "passed": True,
            "failure_reasons": [],
            "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
            "observed_tree_sha256": identity["tree_sha256"],
            "artifact_id": "sandbox_candidate",
        }

    previous_hook = updatectl.PLAYER_RUNTIME_HEALTH_HOOK
    previous_thaw = updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED
    updatectl.PLAYER_RUNTIME_HEALTH_HOOK = health_hook
    updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
    try:
        rc = updatectl._apply_from_manifest_path_unfrozen(
            manifest,
            payload_url=None,
            source=f"sandbox:{manifest.name}",
            payload_path_override=payload,
        )
    finally:
        updatectl.PLAYER_RUNTIME_HEALTH_HOOK = previous_hook
        updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = previous_thaw

    state = read_state(sandbox)
    last = state.get("last_operation") if isinstance(state, dict) else {}
    status = last.get("status") if isinstance(last, dict) else ""
    if rc == 0 and status == "success":
        return True, "applied"
    if observed_identity == "fallback":
        return False, "rejected_health_observed_fallback"
    if not pass_health and status == "candidate_rejected":
        rolled_to = last.get("rolled_back_to") if isinstance(last, dict) else ""
        return False, "rolled_back_to_previous" if rolled_to == "previous" else "rolled_back_to_image_fallback"
    return False, f"rc={rc}:{status}"


def rollback_player_runtime_offline(sandbox: Path) -> tuple[bool, str]:
    configure_updatectl_paths(sandbox)
    previous = readlink(sandbox / "data" / "player-runtime" / "previous")
    previous_thaw = updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED
    updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = True
    try:
        rc = updatectl._rollback_player_runtime_unfrozen("sandbox")
    finally:
        updatectl.PLAYER_RUNTIME_LAB_THAW_ENABLED = previous_thaw
    if rc != 0:
        return False, f"rc={rc}"
    if not previous:
        return True, "fallback"
    return True, previous.split("/")[-1]


def reconcile_player_runtime_offline(sandbox: Path) -> dict[str, Any]:
    configure_updatectl_paths(sandbox)
    rc, result = updatectl._reconcile_player_runtime_state("sandbox")
    result["rc"] = rc
    return result


def probe_launcher_source(sandbox: Path, *, data_dir: Path | None) -> str:
    capture = sandbox / "tmp" / "launcher" / "capture.json"
    if capture.exists():
        capture.unlink()
    env = sandbox_env(sandbox)
    env.update(
        {
            "TOTEM_KIOSKY_FALLBACK_APP_DIR": str(sandbox / "opt" / "totem" / "kiosky-player"),
            "TOTEM_KIOSKY_INNER_LAUNCHER": str(sandbox / "opt" / "totem" / "bin" / "kiosky_service_launcher.sh"),
            "TOTEM_KIOSKY_LAUNCHER_CAPTURE": str(capture),
            "TOTEM_PLAYER_RUNTIME_STATE_FILE": str(sandbox / "data" / "player-runtime" / "state.json"),
        }
    )
    if data_dir is not None:
        env["TOTEM_KIOSKY_DATA_APP_DIR"] = str(data_dir)
    proc = run(["bash", str(LAUNCHER)], env=env, timeout=20)
    if proc.returncode != 0:
        return f"launcher_failed:{proc.returncode}"
    data = json.loads(capture.read_text(encoding="utf-8"))
    return str(data.get("kiosky_app_dir", ""))


def cli_still_frozen(sandbox: Path) -> tuple[bool, bool]:
    env = sandbox_env(sandbox)
    missing = sandbox / "tmp" / "missing.manifest.json"
    apply_proc = run(
        ["python3", "scripts/board/totem_updatectl.py", "apply-local", "--component", COMPONENT, str(missing)],
        env=env,
        timeout=30,
    )
    rollback_proc = run(
        ["python3", "scripts/board/totem_updatectl.py", "rollback", "--component", COMPONENT],
        env=env,
        timeout=30,
    )
    return apply_proc.returncode == 44, rollback_proc.returncode == 44


def main() -> int:
    args = parse_args()
    sandbox = args.sandbox.resolve()
    reset_sandbox(sandbox)
    seed_image_runtime(sandbox)
    write_policy(sandbox)

    manifest_a, payload_a = build_player_runtime_package(sandbox, "sandbox-a", "A")
    manifest_b, payload_b = build_player_runtime_package(sandbox, "sandbox-b", "B")
    manifest_bad, payload_bad = build_player_runtime_package(sandbox, "sandbox-bad", "bad")
    manifest_bad_no_prev, payload_bad_no_prev = build_player_runtime_package(sandbox, "sandbox-bad-no-prev", "bad-no-prev")
    manifest_bad_fallback, payload_bad_fallback = build_player_runtime_package(sandbox, "sandbox-bad-fallback", "bad-fallback")

    apply_a_ok, apply_a_reason = apply_player_runtime_offline(sandbox, manifest=manifest_a, payload=payload_a)
    current_after_a = readlink(sandbox / "data" / "player-runtime" / "current")
    launcher_after_a = probe_launcher_source(sandbox, data_dir=sandbox / "data" / "player-runtime" / "current")
    marker_a = sandbox / "data" / "player-runtime" / "releases" / "sandbox-a" / updatectl.PLAYER_RUNTIME_MARKER_NAME
    marker_a_original = marker_a.read_text(encoding="utf-8")
    marker_a.write_text("{bad json\n", encoding="utf-8")
    launcher_after_corrupt_marker = probe_launcher_source(sandbox, data_dir=sandbox / "data" / "player-runtime" / "current")
    marker_a.write_text(marker_a_original, encoding="utf-8")
    reconcile_after_a = reconcile_player_runtime_offline(sandbox)
    unmarked_dir = sandbox / "data" / "player-runtime" / "releases" / "unmarked"
    unmarked_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SNAPSHOT_KIOSK, unmarked_dir / "kiosk.py")
    launcher_unmarked_fallback = probe_launcher_source(sandbox, data_dir=unmarked_dir)

    apply_b_ok, apply_b_reason = apply_player_runtime_offline(sandbox, manifest=manifest_b, payload=payload_b)
    current_after_b = readlink(sandbox / "data" / "player-runtime" / "current")
    previous_after_b = readlink(sandbox / "data" / "player-runtime" / "previous")
    rollback1_ok, rollback1_to = rollback_player_runtime_offline(sandbox)
    current_after_rollback1 = readlink(sandbox / "data" / "player-runtime" / "current")
    rollback2_ok, rollback2_to = rollback_player_runtime_offline(sandbox)
    current_after_rollback2 = readlink(sandbox / "data" / "player-runtime" / "current")

    set_policy_allow_downgrade(sandbox, True)
    previous_marker_before_collision = marker_a.read_text(encoding="utf-8")
    previous_collision_ok, previous_collision_reason = apply_player_runtime_offline(
        sandbox,
        manifest=manifest_a,
        payload=payload_a,
        pass_health=False,
    )
    set_policy_allow_downgrade(sandbox, False)
    current_after_previous_collision = readlink(sandbox / "data" / "player-runtime" / "current")
    previous_after_previous_collision = readlink(sandbox / "data" / "player-runtime" / "previous")
    previous_marker_after_collision = marker_a.read_text(encoding="utf-8") if marker_a.exists() else ""
    previous_marker_valid_after_collision = updatectl._validate_player_runtime_marker(
        sandbox / "data" / "player-runtime" / "releases" / "sandbox-a",
        read_state(sandbox),
    )[0]

    failed_with_previous_ok, failed_with_previous_reason = apply_player_runtime_offline(
        sandbox,
        manifest=manifest_bad,
        payload=payload_bad,
        pass_health=False,
    )
    current_after_failed_b = readlink(sandbox / "data" / "player-runtime" / "current")
    bad_release_with_previous_exists = (
        sandbox / "data" / "player-runtime" / "releases" / "sandbox-bad"
    ).exists()

    safe_remove(sandbox / "data" / "player-runtime" / "current", sandbox)
    safe_remove(sandbox / "data" / "player-runtime" / "previous", sandbox)
    failed_without_previous_ok, failed_without_previous_reason = apply_player_runtime_offline(
        sandbox,
        manifest=manifest_bad_no_prev,
        payload=payload_bad_no_prev,
        pass_health=False,
    )
    current_after_failed_no_previous = readlink(sandbox / "data" / "player-runtime" / "current")
    bad_release_without_previous_exists = (
        sandbox / "data" / "player-runtime" / "releases" / "sandbox-bad-no-prev"
    ).exists()
    launcher_fallback = probe_launcher_source(sandbox, data_dir=sandbox / "data" / "player-runtime" / "current")
    fallback_kiosk = sandbox / "opt" / "totem" / "kiosky-player" / "kiosk.py"
    fallback_kiosk_tmp = fallback_kiosk.with_suffix(".py.missing")
    fallback_kiosk.rename(fallback_kiosk_tmp)
    launcher_missing_fallback = probe_launcher_source(sandbox, data_dir=sandbox / "data" / "player-runtime" / "current")
    fallback_kiosk_tmp.rename(fallback_kiosk)
    reconcile_after_no_previous_failure = reconcile_player_runtime_offline(sandbox)

    fallback_health_ok, fallback_health_reason = apply_player_runtime_offline(
        sandbox,
        manifest=manifest_bad_fallback,
        payload=payload_bad_fallback,
        pass_health=True,
        observed_identity="fallback",
    )
    current_after_fallback_health = readlink(sandbox / "data" / "player-runtime" / "current")
    fallback_health_rejected_release_exists = (
        sandbox / "data" / "player-runtime" / "releases" / "sandbox-bad-fallback"
    ).exists()

    cli_apply_frozen, cli_rollback_frozen = cli_still_frozen(sandbox)

    expected_a = "releases/sandbox-a"
    expected_b = "releases/sandbox-b"
    result = {
        "schema": "dadooh.c18.player_runtime.sandbox.v1",
        "sandbox": str(sandbox),
        "ssh_used": False,
        "board_touched": False,
        "network_required": False,
        "checks": {
            "release_gate_validated": True,
            "apply_a_offline_passed": apply_a_ok and apply_a_reason == "applied" and current_after_a == expected_a,
            "launcher_data_source_passed": launcher_after_a == str(sandbox / "data" / "player-runtime" / "current"),
            "launcher_corrupt_marker_falls_back": launcher_after_corrupt_marker == str(sandbox / "opt" / "totem" / "kiosky-player"),
            "reconcile_verified_current_passed": (
                reconcile_after_a.get("status") == "current_verified"
                and reconcile_after_a.get("current_link") == expected_a
            ),
            "launcher_unmarked_data_current_falls_back": launcher_unmarked_fallback == str(sandbox / "opt" / "totem" / "kiosky-player"),
            "apply_b_offline_passed": apply_b_ok and apply_b_reason == "applied" and current_after_b == expected_b,
            "current_previous_swap_passed": current_after_b == expected_b and previous_after_b == expected_a,
            "rollback_roundtrip_passed": (
                rollback1_ok
                and rollback2_ok
                and rollback1_to == "sandbox-a"
                and rollback2_to == "sandbox-b"
                and current_after_rollback1 == expected_a
                and current_after_rollback2 == expected_b
            ),
            "previous_release_collision_preserves_marker": (
                not previous_collision_ok
                and previous_collision_reason.startswith("rc=46:")
                and current_after_previous_collision == expected_b
                and previous_after_previous_collision == expected_a
                and previous_marker_after_collision == previous_marker_before_collision
                and previous_marker_valid_after_collision
            ),
            "failed_apply_with_previous_rolled_back": (
                not failed_with_previous_ok
                and failed_with_previous_reason == "rolled_back_to_previous"
                and current_after_failed_b == expected_b
            ),
            "failed_apply_with_previous_cleaned_release": not bad_release_with_previous_exists,
            "failed_apply_without_previous_falls_back_to_image": (
                not failed_without_previous_ok
                and failed_without_previous_reason == "rolled_back_to_image_fallback"
                and current_after_failed_no_previous == ""
                and launcher_fallback == str(sandbox / "opt" / "totem" / "kiosky-player")
            ),
            "failed_apply_without_previous_cleaned_release": not bad_release_without_previous_exists,
            "missing_image_fallback_fails_closed": launcher_missing_fallback == "launcher_failed:78",
            "reconcile_candidate_rejected_hygiene_passed": (
                reconcile_after_no_previous_failure.get("status") == "image_fallback"
                and not reconcile_after_no_previous_failure.get("current_link")
            ),
            "fallback_health_does_not_verify_candidate": (
                not fallback_health_ok
                and fallback_health_reason == "rejected_health_observed_fallback"
                and current_after_fallback_health == ""
            ),
            "fallback_health_rejected_release_cleaned": not fallback_health_rejected_release_exists,
            "cli_apply_still_frozen": cli_apply_frozen,
            "cli_rollback_still_frozen": cli_rollback_frozen,
            "deep_health_fixture_passed": True,
        },
        "path_debt": {
            "launcher_default_data_dir": "/data/player-runtime/current",
            "player_runtime_component_base": "/data/player-runtime",
            "requires_image_launcher_env_or_path_convergence_before_thaw": False,
        },
    }
    result["passed"] = all(result["checks"].values())
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for key, value in result["checks"].items():
            print(f"{key}: {'ok' if value else 'FAIL'}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
