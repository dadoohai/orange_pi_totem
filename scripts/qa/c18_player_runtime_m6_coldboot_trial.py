#!/usr/bin/env python3
"""Run the C18 M-6 player-runtime /data cold-boot trial.

This is an operator-attended, lab-only two-phase harness. It does not thaw the
public updater CLI. Phase ``arm`` leaves the B player-runtime release active in
``/data/current`` and captures pre-state; the operator then performs a real
reboot. Phase ``resume`` validates that the same B release was adopted after
boot, runs deep-health, rolls back to A, reconciles, and emits evidence for the
release gate decisive mode.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QA_DIR = REPO_ROOT / "scripts" / "qa"
BOARD_DIR = REPO_ROOT / "scripts" / "board"
sys.path.insert(0, str(QA_DIR))

from c18_player_runtime_persistent_trial import (  # noqa: E402
    DEVICE_DATA_ENV,
    copy_public_health,
    path_is_under,
    read_json,
    repo_identity,
    run_json,
    run_systemctl_result,
    sha256_file,
    write_evidence_manifest,
    write_json,
)


LAB_ENV = "C18_PLAYER_RUNTIME_M6_COLDBOOT_TRIAL"
SCHEMA = "dadooh.c18.player_runtime.m6_coldboot_trial.v1"
TRANSITION_FLOW = "C18-M6-PLAYER-RUNTIME-DATA-COLDBOOT"
MECHANICAL_ACTION = "operator_controlled_reboot"
REPO_IDENTITY_FILE = "repo-identity.json"
SERVICE = "kiosky-player.service"
M6_LOCK_PATH = Path("/run/lock/c18-player-runtime-m6.lock")
SUPPORTED_UPDATER_FEATURES = {
    "c18-freeze-kiosky-player-v1",
    "c18-rollback-reapply-v1",
    "c18-safe-payload-v1",
    "c18-track-v1",
    "c18-player-runtime-verify-then-promote-v1",
}
REQUIRED_UPDATER_FEATURES = {
    "c18-player-runtime-verify-then-promote-v1",
}


def require_guard(args: argparse.Namespace) -> None:
    if os.environ.get(LAB_ENV) != "1":
        raise RuntimeError(f"m6_guard_required:set {LAB_ENV}=1")
    if path_is_under(args.data_root, Path("/data")) and (
        not args.allow_device_data_root or os.environ.get(DEVICE_DATA_ENV) != "1"
    ):
        raise RuntimeError(f"device_data_root_guard_required:set {DEVICE_DATA_ENV}=1 and pass --allow-device-data-root")


def env_base() -> dict[str, str]:
    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


class M6RunLock:
    def __init__(self, path: Path = M6_LOCK_PATH) -> None:
        self.path = path
        self._fh: Any | None = None

    def __enter__(self) -> "M6RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w", encoding="utf-8")
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._fh.close()
            self._fh = None
            raise RuntimeError("m6_lock_busy") from exc
        self._fh.write(f"pid={os.getpid()} phase=locked\n")
        self._fh.flush()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._fh is None:
            return
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None


def validate_repo_identity_data(data: dict[str, Any]) -> dict[str, Any]:
    repo_commit = data.get("repo_commit")
    repo_tree = data.get("repo_tree")
    repo_dirty = data.get("repo_dirty")
    repo_exact_tag = data.get("repo_exact_tag")
    if not isinstance(repo_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", repo_commit):
        raise RuntimeError("repo_identity_invalid_repo_commit")
    if not isinstance(repo_tree, str) or not re.fullmatch(r"[0-9a-f]{40}", repo_tree):
        raise RuntimeError("repo_identity_invalid_repo_tree")
    if repo_dirty is not False:
        raise RuntimeError("repo_identity_must_be_clean")
    if repo_exact_tag is not None and not isinstance(repo_exact_tag, str):
        raise RuntimeError("repo_identity_invalid_repo_exact_tag")
    return {
        "repo_commit": repo_commit,
        "repo_tree": repo_tree,
        "repo_dirty": False,
        "repo_exact_tag": repo_exact_tag,
    }


def load_repo_identity(path: Path | None) -> dict[str, Any]:
    data = repo_identity() if path is None else read_json(path)
    return validate_repo_identity_data(data)


def repo_identity_for_phase(args: argparse.Namespace, run_dir: Path) -> dict[str, Any]:
    path = args.repo_identity_file
    if path is None:
        persisted = run_dir / REPO_IDENTITY_FILE
        if persisted.is_file():
            path = persisted
    return load_repo_identity(path)


def validate_package_repo_identity(manifest: dict[str, Any], repo_info: dict[str, Any], label: str) -> None:
    source_commit = manifest.get("source_commit")
    if source_commit != repo_info.get("repo_commit"):
        raise RuntimeError(f"{label}_source_commit_repo_mismatch")


def package_manifest(path: Path) -> dict[str, Any]:
    data = read_json(path)
    if data.get("component") != "player-runtime":
        raise RuntimeError("package_manifest_component_not_player_runtime")
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise RuntimeError("package_manifest_version_missing")
    if data.get("source_dirty") is not False:
        raise RuntimeError("package_manifest_source_dirty")
    requires = data.get("requires")
    features = requires.get("updater_features") if isinstance(requires, dict) else None
    if not isinstance(features, list):
        raise RuntimeError("package_manifest_missing_player_runtime_updater_feature")
    feature_set = set(features)
    missing_features = sorted(REQUIRED_UPDATER_FEATURES - feature_set)
    if missing_features:
        raise RuntimeError("package_manifest_missing_player_runtime_updater_feature")
    unsupported_features = sorted(feature_set - SUPPORTED_UPDATER_FEATURES)
    if unsupported_features:
        raise RuntimeError("package_manifest_unsupported_updater_features:" + ",".join(unsupported_features))
    return data


def copy_package_manifest(manifest: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest, dst / manifest.name)


def run_release_gate(manifest: Path, payload: Path, dst: Path, env: dict[str, str]) -> dict[str, Any]:
    return run_json(
        [
            sys.executable,
            str(QA_DIR / "c18_player_runtime_release_gate.py"),
            "--manifest",
            str(manifest),
            "--payload",
            str(payload),
        ],
        env=env,
        stdout_path=dst,
    )


def run_lab_apply(args: argparse.Namespace,
                  manifest: Path,
                  payload: Path,
                  output_dir: Path,
                  stdout_path: Path,
                  env: dict[str, str]) -> dict[str, Any]:
    return run_json(
        [
            sys.executable,
            str(QA_DIR / "c18_player_runtime_lab_apply.py"),
            "--lab-only-apply",
            "--manifest",
            str(manifest),
            "--payload",
            str(payload),
            "--data-root",
            str(args.data_root),
            "--allow-device-data-root",
            "--canary-media",
            str(args.canary_media),
            "--output-dir",
            str(output_dir),
            "--duration-sec",
            str(args.duration_sec),
            "--interval-sec",
            str(args.interval_sec),
            "--startup-wait-sec",
            str(args.startup_wait_sec),
            "--json",
        ],
        env={**env, "C18_PLAYER_RUNTIME_LAB_APPLY": "1", DEVICE_DATA_ENV: "1"},
        stdout_path=stdout_path,
        timeout=1800,
    )


def run_systemctl_service(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        ["systemctl", *args, SERVICE],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    return {
        "action": " ".join(args),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-400:],
        "stderr_tail": proc.stderr[-400:],
    }


def require_systemctl(result: dict[str, Any], label: str) -> None:
    if result["returncode"] != 0:
        raise RuntimeError(f"{label}_failed:{result['stderr_tail'] or result['stdout_tail']}")


def restart_service_best_effort() -> None:
    run_systemctl_service("unmask")
    run_systemctl_service("start")


def run_lab_apply_with_service_held(args: argparse.Namespace,
                                    manifest: Path,
                                    payload: Path,
                                    output_dir: Path,
                                    stdout_path: Path,
                                    env: dict[str, str]) -> dict[str, Any]:
    require_systemctl(run_systemctl_service("stop"), "service_stop_before_apply")
    require_systemctl(run_systemctl_service("mask", "--runtime"), "service_runtime_mask_before_apply")
    try:
        result = run_lab_apply(args, manifest, payload, output_dir, stdout_path, env)
    except Exception:
        restart_service_best_effort()
        raise
    finally:
        run_systemctl_service("unmask")
    if result.get("passed") is not True:
        restart_service_best_effort()
    return result


def run_adoption(args: argparse.Namespace,
                 expected_source: str,
                 expected_version: str | None,
                 stdout_path: Path,
                 env: dict[str, str]) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(QA_DIR / "c18_player_runtime_adoption_probe.py"),
        "--data-root",
        str(args.data_root),
        "--expected-source",
        expected_source,
        "--json",
    ]
    if expected_version:
        cmd.extend(["--expected-version", expected_version])
    return run_json(cmd, env=env, stdout_path=stdout_path)


def collect_health(args: argparse.Namespace, output_dir: Path, stdout_path: Path, env: dict[str, str]) -> dict[str, Any]:
    return run_json(
        [
            sys.executable,
            str(BOARD_DIR / "c18_playback_health_collect.py"),
            "--duration-sec",
            str(args.duration_sec),
            "--interval-sec",
            str(args.interval_sec),
            "--output-dir",
            str(output_dir),
            "--json",
        ],
        env=env,
        stdout_path=stdout_path,
        timeout=1800,
    )


def collect_health_atomic(args: argparse.Namespace, output_dir: Path, stdout_path: Path, env: dict[str, str]) -> dict[str, Any]:
    if output_dir.exists():
        raise RuntimeError(f"health_output_dir_already_exists:{output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_dir.parent / f".{output_dir.name}.tmp-{os.getpid()}-{int(time.time() * 1000)}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    try:
        result = collect_health(args, tmp_dir, stdout_path, env)
        wait_for_evidence_tree_stable(tmp_dir)
        tmp_dir.rename(output_dir)
        wait_for_evidence_tree_stable(output_dir)
        return result
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def evidence_tree_snapshot(root: Path) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        stat = path.stat()
        snapshot[rel] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def wait_for_evidence_tree_stable(root: Path, *, settle_sec: float = 0.75, attempts: int = 8) -> None:
    previous = evidence_tree_snapshot(root)
    for _ in range(attempts):
        time.sleep(settle_sec)
        current = evidence_tree_snapshot(root)
        if current == previous:
            return
        previous = current
    raise RuntimeError(f"evidence_tree_not_stable:{root}")


def collect_pre_state(args: argparse.Namespace, output: Path, env: dict[str, str]) -> dict[str, Any]:
    return run_json(
        [
            sys.executable,
            str(BOARD_DIR / "c18_coldboot_state_collect.py"),
            "--capture-pre-state",
            "--output",
            str(output),
            "--image-marker",
            str(args.image_marker_file),
            "--transition-flow",
            TRANSITION_FLOW,
            "--mechanical-action",
            args.mechanical_action,
            "--controlled-reboot",
            "--include-freeze-probes",
        ],
        env=env,
        stdout_path=output.parent / "pre-state-collect.json",
    )


def collect_post_state(args: argparse.Namespace, pre_state: Path, output: Path, env: dict[str, str]) -> dict[str, Any]:
    return run_json(
        [
            sys.executable,
            str(BOARD_DIR / "c18_coldboot_state_collect.py"),
            "--output",
            str(output),
            "--pre-state",
            str(pre_state),
            "--image-marker",
            str(args.image_marker_file),
            "--transition-flow",
            TRANSITION_FLOW,
            "--mechanical-action",
            args.mechanical_action,
            "--controlled-reboot",
            "--include-freeze-probes",
        ],
        env=env,
        stdout_path=output.parent / "post-state-collect.json",
    )


def write_coldboot_manifest(run_dir: Path, *, package_manifest_b: dict[str, Any], repo_info: dict[str, Any]) -> None:
    artifacts = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(run_dir).as_posix()
        if rel == "evidence-manifest.json":
            continue
        artifacts.append({
            "file": rel,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    manifest = {
        "schema": "dadooh.c18.coldboot_data_evidence_manifest.v1",
        "artifact_scope": "player-runtime-data-coldboot-lab-trial",
        "component": "player-runtime",
        "source_commit": package_manifest_b.get("source_commit"),
        "version": package_manifest_b.get("version"),
        "artifacts": artifacts,
        **repo_info,
    }
    write_json(run_dir / "evidence-manifest.json", manifest)


def run_lab_rollback(args: argparse.Namespace,
                     expected_version: str,
                     output_dir: Path,
                     stdout_path: Path,
                     env: dict[str, str]) -> dict[str, Any]:
    return run_json(
        [
            sys.executable,
            str(QA_DIR / "c18_player_runtime_lab_rollback.py"),
            "--lab-only-rollback",
            "--action",
            "rollback",
            "--data-root",
            str(args.data_root),
            "--allow-device-data-root",
            "--quarantine-current",
            "--expect-rolled-to",
            expected_version,
            "--output-dir",
            str(output_dir),
            "--reason",
            "m6_coldboot_trial_rollback",
            "--json",
        ],
        env={**env, "C18_PLAYER_RUNTIME_LAB_ROLLBACK": "1", DEVICE_DATA_ENV: "1"},
        stdout_path=stdout_path,
    )


def run_lab_reconcile(args: argparse.Namespace, output_dir: Path, stdout_path: Path, env: dict[str, str]) -> dict[str, Any]:
    return run_json(
        [
            sys.executable,
            str(QA_DIR / "c18_player_runtime_lab_rollback.py"),
            "--lab-only-rollback",
            "--action",
            "reconcile",
            "--data-root",
            str(args.data_root),
            "--allow-device-data-root",
            "--output-dir",
            str(output_dir),
            "--reason",
            "m6_coldboot_trial_reconcile",
            "--json",
        ],
        env={**env, "C18_PLAYER_RUNTIME_LAB_ROLLBACK": "1", DEVICE_DATA_ENV: "1"},
        stdout_path=stdout_path,
    )


def cross_check_marker(data_dir: Path, coldboot_dir: Path, adoption_path: Path) -> dict[str, Any]:
    marker = read_json(data_dir / "verified-marker.json")
    boot = read_json(coldboot_dir / "boot-state-public.json")
    adoption = read_json(adoption_path)
    player = boot.get("player_runtime") if isinstance(boot.get("player_runtime"), dict) else {}
    checks = {
        "version": [marker.get("version"), player.get("data_current_marker_version"), adoption.get("marker_version")],
        "tree_sha256": [marker.get("tree_sha256"), player.get("data_current_tree_sha256"), adoption.get("marker_tree_sha256")],
        "kiosk_py_sha256": [marker.get("kiosk_py_sha256"), player.get("data_current_kiosk_py_sha256"), adoption.get("marker_kiosk_py_sha256")],
    }
    errors = []
    for key, values in checks.items():
        if any(not value for value in values):
            errors.append(f"{key}_missing")
        elif len(set(values)) != 1:
            errors.append(f"{key}_mismatch")
    return {
        "schema": "dadooh.c18.player_runtime.m6_marker_link.v1",
        "passed": not errors,
        "errors": errors,
        "checks": checks,
    }


def write_trial_readme(data_dir: Path, *, version_b: str) -> None:
    write_json(data_dir / "README.md", {
        "schema": "dadooh.c18.player_runtime.trial_readme.v1",
        "artifact_id": f"c18-player-runtime-m6-coldboot-{version_b}",
        "component": "player-runtime",
        "version": version_b,
        "scope": "lab-only persistent /data coldboot trial",
        "rollback_expectation": "data-previous",
        "claims": [
            "local_package_apply",
            "verified_marker_adoption",
            "service_deep_health_after_restart",
            "rollback_to_data_previous",
            "service_deep_health_after_rollback",
        ],
        "non_claims": [
            "public_thaw",
            "github_publish",
            "auto_pull",
            "stable_or_production",
            "power_loss_safety",
            "cold_boot_adoption",
            "server_side_gate",
            "soak_endurance",
        ],
    })


def phase_arm(args: argparse.Namespace) -> int:
    require_guard(args)
    if args.evidence_root.exists() and any(args.evidence_root.iterdir()):
        raise RuntimeError(f"evidence_root_must_be_empty:{args.evidence_root}")
    env = env_base()
    repo_info = repo_identity_for_phase(args, args.evidence_root)
    manifest_a = package_manifest(args.manifest_a)
    manifest_b = package_manifest(args.manifest_b)
    validate_package_repo_identity(manifest_a, repo_info, "manifest_a")
    validate_package_repo_identity(manifest_b, repo_info, "manifest_b")
    version_a = str(manifest_a["version"])
    version_b = str(manifest_b["version"])
    if version_a == version_b:
        raise RuntimeError("m6_requires_distinct_a_b_versions")
    run_dir = args.evidence_root
    data_dir = run_dir / "player-runtime-data-evidence"
    coldboot_dir = run_dir / "coldboot-data-evidence"
    raw_dir = run_dir / "raw"
    package_dir = data_dir / "package"
    package_dir.mkdir(parents=True, exist_ok=True)
    coldboot_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / REPO_IDENTITY_FILE, repo_info)
    copy_package_manifest(args.manifest_b, package_dir)
    run_release_gate(args.manifest_b, args.payload_b, package_dir / "player-runtime-release-gate.json", env)

    apply_a = run_lab_apply_with_service_held(args, args.manifest_a, args.payload_a, raw_dir / "apply-a", raw_dir / "apply-a.json", env)
    if apply_a.get("passed") is not True:
        raise RuntimeError("apply_a_failed")
    restart_result = run_systemctl_result("restart")
    if restart_result["returncode"] != 0:
        raise RuntimeError("service_restart_failed_after_apply_a")
    time.sleep(max(args.startup_wait_sec, 0.0))
    run_adoption(args, "data", version_a, data_dir / "service-before-apply" / "launcher-adoption.json", env)
    collect_health_atomic(args, data_dir / "service-before-apply", raw_dir / "service-before-apply.json", env)

    apply_b = run_lab_apply_with_service_held(args, args.manifest_b, args.payload_b, raw_dir / "apply-b", data_dir / "lab-apply.json", env)
    if apply_b.get("passed") is not True:
        raise RuntimeError("apply_b_failed")
    copy_public_health(raw_dir / "apply-b" / "candidate-health" / "health", data_dir / "candidate-health")
    shutil.copy2(raw_dir / "apply-b" / "candidate-health" / "candidate-health-result.json", data_dir / "candidate-health-result.json")
    marker_path = args.data_root / "player-runtime" / "current" / ".release_verified.json"
    if not marker_path.is_file():
        raise RuntimeError("verified_marker_missing_after_apply_b")
    shutil.copy2(marker_path, data_dir / "verified-marker.json")
    restart_result = run_systemctl_result("restart")
    if restart_result["returncode"] != 0:
        raise RuntimeError("service_restart_failed_after_apply_b")
    time.sleep(max(args.startup_wait_sec, 0.0))
    run_adoption(args, "data", version_b, data_dir / "service-after-restart" / "launcher-adoption.json", env)
    collect_health_atomic(args, data_dir / "service-after-restart", raw_dir / "service-after-restart.json", env)
    collect_pre_state(args, coldboot_dir / "pre-state-public.json", env)
    write_json(run_dir / "m6-run-state.json", {
        "schema": SCHEMA,
        "phase": "armed",
        "version_a": version_a,
        "version_b": version_b,
        "data_root": str(args.data_root),
        "image_tag": args.image_tag,
        "image_sha256": args.image_sha256,
        "image_marker_file": str(args.image_marker_file),
        "repo_identity_file": str(run_dir / REPO_IDENTITY_FILE),
        "player_runtime_data_evidence_dir": str(data_dir),
        "coldboot_data_evidence_dir": str(coldboot_dir),
        "armed_at_unix": int(time.time()),
    })
    result = {
        "schema": SCHEMA,
        "phase": "arm",
        "passed": True,
        "requires_reboot": True,
        "next_phase": "resume",
        "evidence_root": str(run_dir),
        "version_a": version_a,
        "version_b": version_b,
    }
    print(json.dumps(result, indent=2 if args.json else None, sort_keys=True))
    return 0


def phase_resume(args: argparse.Namespace) -> int:
    require_guard(args)
    env = env_base()
    run_dir = args.evidence_root
    repo_info = repo_identity_for_phase(args, run_dir)
    state = read_json(run_dir / "m6-run-state.json")
    version_a = str(state["version_a"])
    version_b = str(state["version_b"])
    data_dir = Path(str(state["player_runtime_data_evidence_dir"]))
    coldboot_dir = Path(str(state["coldboot_data_evidence_dir"]))
    raw_dir = run_dir / "raw"
    manifest_b_files = sorted((data_dir / "package").glob("*.manifest.json"))
    if len(manifest_b_files) != 1:
        raise RuntimeError("m6_package_manifest_b_count")
    manifest_b = package_manifest(manifest_b_files[0])
    validate_package_repo_identity(manifest_b, repo_info, "manifest_b")
    collect_post_state(args, coldboot_dir / "pre-state-public.json", coldboot_dir / "boot-state-public.json", env)
    run_adoption(args, "data", version_b, coldboot_dir / "launcher-adoption.json", env)
    collect_health_atomic(args, coldboot_dir / "service-after-coldboot", raw_dir / "service-after-coldboot.json", env)
    marker_link = cross_check_marker(data_dir, coldboot_dir, coldboot_dir / "launcher-adoption.json")
    write_json(coldboot_dir / "marker-link.json", marker_link)
    if marker_link["passed"] is not True:
        raise RuntimeError("m6_marker_link_failed")
    wait_for_evidence_tree_stable(coldboot_dir)
    write_coldboot_manifest(coldboot_dir, package_manifest_b=manifest_b, repo_info=repo_info)
    coldboot_gate = run_json(
        [
            sys.executable,
            str(QA_DIR / "c18_coldboot_evidence_gate.py"),
            "--run-dir",
            str(coldboot_dir),
            "--expect-selected-source",
            "data",
            "--require-pre-state",
            "--expect-image-tag",
            args.image_tag,
            "--expect-image-marker-sha256",
            sha256_file(args.image_marker_file),
            "--json",
        ],
        env=env,
        stdout_path=run_dir / "coldboot-evidence-gate.json",
    )
    if coldboot_gate.get("passed") is not True:
        raise RuntimeError("m6_coldboot_gate_failed")
    rollback = run_lab_rollback(args, version_a, raw_dir / "rollback", data_dir / "lab-rollback.json", env)
    if rollback.get("passed") is not True:
        raise RuntimeError("m6_rollback_failed")
    restart_result = run_systemctl_result("restart")
    if restart_result["returncode"] != 0:
        raise RuntimeError("service_restart_failed_after_rollback")
    time.sleep(max(args.startup_wait_sec, 0.0))
    run_adoption(args, "data", version_a, data_dir / "service-after-rollback" / "launcher-adoption.json", env)
    collect_health_atomic(args, data_dir / "service-after-rollback", raw_dir / "service-after-rollback.json", env)
    reconcile = run_lab_reconcile(args, raw_dir / "reconcile", run_dir / "lab-reconcile.json", env)
    if reconcile.get("passed") is not True:
        raise RuntimeError("m6_reconcile_failed")
    write_trial_readme(data_dir, version_b=version_b)
    wait_for_evidence_tree_stable(data_dir)
    write_evidence_manifest(
        data_dir,
        package_manifest=manifest_b,
        trial_id=f"c18-player-runtime-m6-coldboot-{version_b}",
        rollback_expectation="data-previous",
        repo_info=repo_info,
        image_tag=args.image_tag,
        image_sha256=args.image_sha256,
        image_marker_file=args.image_marker_file,
    )
    player_gate = run_json(
        [
            sys.executable,
            str(QA_DIR / "c18_player_runtime_evidence_gate.py"),
            "--run-dir",
            str(data_dir),
            "--expect-image-tag",
            args.image_tag,
            "--expect-image-sha256",
            args.image_sha256,
            "--expect-image-marker-sha256",
            sha256_file(args.image_marker_file),
            "--json",
        ],
        env=env,
        stdout_path=run_dir / "player-runtime-evidence-gate.json",
    )
    if player_gate.get("passed") is not True:
        raise RuntimeError("m6_player_runtime_evidence_gate_failed")
    if args.defer_release_gate:
        release_gate = {
            "passed": None,
            "status": "deferred",
            "reason": "run c18_ota_release_gate.py on the host after copying evidence from the board",
        }
        write_json(run_dir / "m6-release-gate.json", release_gate)
    else:
        release_gate = run_json(
            [
                sys.executable,
                str(QA_DIR / "c18_ota_release_gate.py"),
                "--player-runtime-evidence-mode",
                "decisive",
                "--player-runtime-data-coldboot-evidence-dir",
                str(coldboot_dir),
                "--player-runtime-data-evidence-dir",
                str(data_dir),
                "--expect-image-tag",
                args.image_tag,
                "--expect-image-sha256",
                args.image_sha256,
                "--expect-image-marker-sha256",
                sha256_file(args.image_marker_file),
                "--json",
            ],
            env=env,
            stdout_path=run_dir / "m6-release-gate.json",
            timeout=240,
        )
    summary = {
        "schema": SCHEMA,
        "phase": "resume",
        "passed": release_gate.get("passed") is True,
        "m6_checks_passed": True,
        "release_gate_deferred": bool(args.defer_release_gate),
        "version_a": version_a,
        "version_b": version_b,
        "evidence_root": str(run_dir),
        "player_runtime_data_evidence_dir": str(data_dir),
        "coldboot_data_evidence_dir": str(coldboot_dir),
        "release_gate": release_gate,
    }
    write_json(run_dir / "m6-summary.json", summary)
    print(json.dumps(summary, indent=2 if args.json else None, sort_keys=True))
    return 0 if summary["passed"] else 1


def phase_rollback_only(args: argparse.Namespace) -> int:
    require_guard(args)
    env = env_base()
    run_dir = args.evidence_root
    state = read_json(run_dir / "m6-run-state.json")
    version_a = str(state["version_a"])
    rollback = run_lab_rollback(args, version_a, run_dir / "raw" / "rollback-only", run_dir / "rollback-only.json", env)
    restart = run_systemctl_result("restart")
    summary = {
        "schema": SCHEMA,
        "phase": "rollback-only",
        "passed": rollback.get("passed") is True and restart["returncode"] == 0,
        "rollback": rollback,
        "restart": restart,
    }
    print(json.dumps(summary, indent=2 if args.json else None, sort_keys=True))
    return 0 if summary["passed"] else 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("arm", "resume", "rollback-only"), required=True)
    parser.add_argument("--manifest-a", type=Path)
    parser.add_argument("--payload-a", type=Path)
    parser.add_argument("--manifest-b", type=Path)
    parser.add_argument("--payload-b", type=Path)
    parser.add_argument("--canary-media", type=Path)
    parser.add_argument("--data-root", type=Path, default=Path("/data"))
    parser.add_argument("--allow-device-data-root", action="store_true")
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--image-tag", required=True)
    parser.add_argument("--image-sha256", required=True)
    parser.add_argument("--image-marker-file", required=True, type=Path)
    parser.add_argument("--repo-identity-file", type=Path)
    parser.add_argument("--mechanical-action", default=MECHANICAL_ACTION)
    parser.add_argument("--defer-release-gate", action="store_true")
    parser.add_argument("--duration-sec", type=float, default=45.0)
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--startup-wait-sec", type=float, default=8.0)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        with M6RunLock():
            if args.phase == "arm":
                for key in ("manifest_a", "payload_a", "manifest_b", "payload_b", "canary_media"):
                    if getattr(args, key) is None:
                        raise RuntimeError(f"missing_required_for_arm:{key}")
                return phase_arm(args)
            if args.phase == "resume":
                return phase_resume(args)
            return phase_rollback_only(args)
    except RuntimeError as exc:
        message = str(exc)
        print(message, file=sys.stderr)
        if message.startswith("m6_guard_required"):
            return 44
        if message.startswith("device_data_root_guard_required"):
            return 43
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
