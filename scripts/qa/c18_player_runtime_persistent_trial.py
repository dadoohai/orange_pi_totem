#!/usr/bin/env python3
"""Run one guarded C18 player-runtime persistent /data lab trial.

This is an operator-attended lab harness.  It does not thaw the public updater
CLI, publish anything, use GitHub, or enable auto-pull.  It exists to produce a
single curated evidence directory for a local player-runtime package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
LAB_ENV = "C18_PLAYER_RUNTIME_PERSISTENT_TRIAL"
DEVICE_DATA_ENV = "C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT"
SCHEMA = "dadooh.c18.player_runtime.persistent_trial.v1"
MANIFEST_SCHEMA = "dadooh.c18.player_runtime.evidence_manifest.v1"
SERVICE = "kiosky-player.service"


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(args: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def repo_identity() -> dict[str, Any]:
    commit = git_value(["rev-parse", "HEAD"])
    tree = git_value(["rev-parse", "HEAD^{tree}"])
    status = git_value(["status", "--porcelain", "--untracked-files=normal"])
    dirty = None if status is None else bool(status)
    tag = git_value(["describe", "--tags", "--exact-match", "HEAD"])
    return {
        "repo_commit": commit,
        "repo_tree": tree,
        "repo_dirty": dirty,
        "repo_exact_tag": tag,
    }


def path_is_under(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    root_resolved = root.resolve()
    return resolved == root_resolved or root_resolved in resolved.parents


def run_json(cmd: list[str],
             *,
             env: dict[str, str] | None = None,
             stdout_path: Path | None = None,
             timeout: int = 900) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"command_failed rc={proc.returncode} cmd={cmd[0]} stderr_tail={proc.stderr[-400:]}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"command_json_failed cmd={cmd[0]}") from exc
    if stdout_path is not None:
        write_json(stdout_path, data)
    return data


def read_symlink_target(path: Path) -> str | None:
    try:
        return os.readlink(path)
    except OSError:
        return None


def run_systemctl_result(action: str) -> dict[str, Any]:
    proc = subprocess.run(
        ["systemctl", action, SERVICE],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    return {
        "action": action,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-400:],
        "stderr_tail": proc.stderr[-400:],
    }


def copy_public_health(src_dir: Path, dst_dir: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    required = (
        "playback-deep-health-public.json",
        "playback-samples.tsv",
        "status-samples.ndjson",
        "deep-health-systemd.json",
        "deep-health-process.json",
        "deep-health-kernel.json",
        "deep-health-player-counters.json",
    )
    for name in required:
        src = src_dir / name
        if not src.is_file():
            raise RuntimeError(f"missing public health artifact: {src}")
        shutil.copy2(src, dst_dir / name)


def write_evidence_manifest(evidence_dir: Path,
                            *,
                            package_manifest: dict[str, Any],
                            trial_id: str,
                            rollback_expectation: str,
                            repo_info: dict[str, Any] | None = None,
                            image_tag: str | None = None,
                            image_sha256: str | None = None,
                            image_marker_file: Path | None = None) -> None:
    artifacts = []
    for path in sorted(evidence_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(evidence_dir).as_posix()
        if rel == "evidence-manifest.json":
            continue
        artifacts.append({
            "file": rel,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "artifact_id": trial_id,
        "artifact_scope": "player-runtime-persistent-data-lab-trial",
        "component": "player-runtime",
        "version": package_manifest.get("version"),
        "channel": package_manifest.get("channel"),
        "source_commit": package_manifest.get("source_commit"),
        "payload_sha256": package_manifest.get("payload_sha256"),
        "rollback_expectation": rollback_expectation,
        "artifacts": artifacts,
        **(repo_info if repo_info is not None else repo_identity()),
    }
    if image_tag:
        manifest["image_tag"] = image_tag
    if image_sha256:
        manifest["image_sha256"] = image_sha256.lower()
    if image_marker_file:
        if not image_marker_file.is_file():
            raise RuntimeError(f"image marker file not found: {image_marker_file}")
        manifest["image_marker_path"] = str(image_marker_file)
        manifest["image_marker_bytes"] = image_marker_file.stat().st_size
        manifest["image_marker_sha256"] = sha256_file(image_marker_file)
    write_json(evidence_dir / "evidence-manifest.json", manifest)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab-only-persistent-trial", action="store_true")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--canary-media", required=True, type=Path)
    parser.add_argument("--data-root", type=Path, default=Path("/data"))
    parser.add_argument("--allow-device-data-root", action="store_true")
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--duration-sec", type=float, default=45.0)
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--startup-wait-sec", type=float, default=8.0)
    parser.add_argument(
        "--rollback-expectation",
        choices=("image-fallback-or-previous", "image-fallback", "data-previous"),
        default="image-fallback-or-previous",
    )
    parser.add_argument("--image-tag")
    parser.add_argument("--image-sha256")
    parser.add_argument("--image-marker-file", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    def raise_on_sigterm(signum: int, _frame: Any) -> None:
        raise RuntimeError(f"received_signal:{signum}")

    signal.signal(signal.SIGTERM, raise_on_sigterm)

    args = parse_args(argv)
    if not args.lab_only_persistent_trial or os.environ.get(LAB_ENV) != "1":
        print(f"player_runtime_persistent_trial_guard_required: pass --lab-only-persistent-trial and set {LAB_ENV}=1", file=sys.stderr)
        return 44
    if path_is_under(args.data_root, Path("/data")) and (
        not args.allow_device_data_root or os.environ.get(DEVICE_DATA_ENV) != "1"
    ):
        print(f"device_data_root_guard_required: pass --allow-device-data-root and set {DEVICE_DATA_ENV}=1", file=sys.stderr)
        return 43

    repo_info = repo_identity()
    evidence_dir = args.evidence_dir
    if evidence_dir.exists() and any(evidence_dir.iterdir()):
        raise RuntimeError(f"evidence dir must be empty: {evidence_dir}")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.raw_dir or Path(tempfile.mkdtemp(prefix="c18-player-runtime-persistent-trial-"))
    raw_dir.mkdir(parents=True, exist_ok=True)

    manifest = read_json(args.manifest)
    version = str(manifest.get("version") or "")
    trial_id = f"c18-player-runtime-data-trial-{version}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    env_base = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    package_evidence_dir = evidence_dir / "package"
    package_evidence_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.manifest, package_evidence_dir / args.manifest.name)
    release_gate = run_json(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_release_gate.py"),
            "--manifest",
            str(args.manifest),
            "--payload",
            str(args.payload),
        ],
        env=env_base,
        stdout_path=evidence_dir / "package" / "player-runtime-release-gate.json",
    )
    if release_gate.get("passed") is not True:
        raise RuntimeError("release gate did not pass")

    apply_env = {
        **env_base,
        "C18_PLAYER_RUNTIME_LAB_APPLY": "1",
        DEVICE_DATA_ENV: "1",
    }
    rollback_env = {
        **env_base,
        "C18_PLAYER_RUNTIME_LAB_ROLLBACK": "1",
        DEVICE_DATA_ENV: "1",
    }
    apply_completed = False
    rollback_completed = False
    trial_completed = False
    service_stopped = False
    cleanup_actions: list[dict[str, Any]] = []
    current_link = args.data_root / "player-runtime" / "current"
    pre_trial_current_target = read_symlink_target(current_link)
    pre_apply_data_version: str | None = None
    pre_apply_tree_sha256: str | None = None
    try:
        if args.rollback_expectation == "data-previous":
            before_adoption = run_json(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_adoption_probe.py"),
                    "--data-root",
                    str(args.data_root),
                    "--expected-source",
                    "data",
                    "--json",
                ],
                env=env_base,
                stdout_path=evidence_dir / "service-before-apply" / "launcher-adoption.json",
            )
            pre_apply_data_version = str(before_adoption.get("selected_version") or "")
            pre_apply_tree_sha256 = str(before_adoption.get("marker_tree_sha256") or "")
            if not pre_apply_data_version or pre_apply_data_version == "image_fallback":
                raise RuntimeError("data_previous_rollback_requires_existing_data_current")
            if not pre_apply_tree_sha256:
                raise RuntimeError("data_previous_rollback_requires_existing_tree_sha")
            run_json(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "board" / "c18_playback_health_collect.py"),
                    "--duration-sec",
                    str(args.duration_sec),
                    "--interval-sec",
                    str(args.interval_sec),
                    "--output-dir",
                    str(evidence_dir / "service-before-apply"),
                    "--json",
                ],
                env=env_base,
                stdout_path=raw_dir / "service-before-apply.json",
                timeout=1800,
            )

        stop_result = run_systemctl_result("stop")
        if stop_result["returncode"] != 0:
            raise RuntimeError("service_stop_failed")
        service_stopped = True
        apply_json = run_json(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_lab_apply.py"),
                "--lab-only-apply",
                "--manifest",
                str(args.manifest),
                "--payload",
                str(args.payload),
                "--data-root",
                str(args.data_root),
                "--allow-device-data-root",
                "--canary-media",
                str(args.canary_media),
                "--output-dir",
                str(raw_dir / "apply"),
                "--duration-sec",
                str(args.duration_sec),
                "--interval-sec",
                str(args.interval_sec),
                "--startup-wait-sec",
                str(args.startup_wait_sec),
                "--json",
            ],
            env=apply_env,
            stdout_path=evidence_dir / "lab-apply.json",
            timeout=1800,
        )
        if apply_json.get("passed") is not True:
            raise RuntimeError("lab apply did not pass")
        apply_completed = True
        copy_public_health(raw_dir / "apply" / "candidate-health" / "health", evidence_dir / "candidate-health")
        shutil.copy2(raw_dir / "apply" / "candidate-health" / "candidate-health-result.json", evidence_dir / "candidate-health-result.json")
        current_marker = args.data_root / "player-runtime" / "current" / ".release_verified.json"
        if not current_marker.is_file():
            raise RuntimeError("verified marker missing after apply")
        shutil.copy2(current_marker, evidence_dir / "verified-marker.json")
        applied_marker = read_json(current_marker)
        if args.rollback_expectation == "data-previous":
            after_snapshot = apply_json.get("after") if isinstance(apply_json.get("after"), dict) else {}
            previous_link = str(after_snapshot.get("previous_link") or "")
            state_previous_version = str(after_snapshot.get("state_previous_version") or "")
            if not previous_link.endswith(pre_apply_data_version or ""):
                raise RuntimeError("data_previous_apply_did_not_preserve_previous_link")
            if state_previous_version != pre_apply_data_version:
                raise RuntimeError("data_previous_apply_did_not_preserve_previous_state")
            if applied_marker.get("tree_sha256") == pre_apply_tree_sha256:
                raise RuntimeError("data_previous_trial_requires_distinct_tree_sha")

        restart_result = run_systemctl_result("restart")
        if restart_result["returncode"] != 0:
            raise RuntimeError("service_restart_failed_after_apply")
        service_stopped = False
        time.sleep(max(args.startup_wait_sec, 0.0))
        adoption_cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_adoption_probe.py"),
            "--data-root",
            str(args.data_root),
            "--expected-source",
            "data",
            "--expected-version",
            version,
            "--json",
        ]
        run_json(adoption_cmd, env=env_base, stdout_path=evidence_dir / "service-after-restart" / "launcher-adoption.json")
        run_json(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "board" / "c18_playback_health_collect.py"),
                "--duration-sec",
                str(args.duration_sec),
                "--interval-sec",
                str(args.interval_sec),
                "--output-dir",
                str(evidence_dir / "service-after-restart"),
                "--json",
            ],
            env=env_base,
            stdout_path=raw_dir / "service-after-restart.json",
            timeout=1800,
        )

        rollback_json = run_json(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_lab_rollback.py"),
                "--lab-only-rollback",
                "--action",
                "rollback",
                "--data-root",
                str(args.data_root),
                "--allow-device-data-root",
                "--quarantine-current",
                *(
                    ["--expect-rolled-to", pre_apply_data_version]
                    if args.rollback_expectation == "data-previous" and pre_apply_data_version
                    else ["--expect-rolled-to", "image_fallback"]
                    if args.rollback_expectation == "image-fallback"
                    else []
                ),
                "--output-dir",
                str(raw_dir / "rollback"),
                "--reason",
                f"persistent_trial_rollback_{trial_id}",
                "--json",
            ],
            env=rollback_env,
            stdout_path=evidence_dir / "lab-rollback.json",
        )
        if rollback_json.get("passed") is not True:
            raise RuntimeError("lab rollback did not pass")
        rollback_completed = True

        restart_result = run_systemctl_result("restart")
        if restart_result["returncode"] != 0:
            raise RuntimeError("service_restart_failed_after_rollback")
        service_stopped = False
        time.sleep(max(args.startup_wait_sec, 0.0))
        rolled_to = (((rollback_json.get("operation") or {}).get("rolled_back_to")) or "image_fallback")
        expected_source = "fallback" if rolled_to == "image_fallback" else "data"
        if args.rollback_expectation == "data-previous":
            if rolled_to != pre_apply_data_version:
                raise RuntimeError("data_previous_rollback_target_mismatch")
            expected_source = "data"
        elif args.rollback_expectation == "image-fallback" and rolled_to != "image_fallback":
            raise RuntimeError("image_fallback_rollback_target_mismatch")
        rollback_adoption_cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_adoption_probe.py"),
            "--data-root",
            str(args.data_root),
            "--expected-source",
            expected_source,
            "--json",
        ]
        if expected_source == "data":
            rollback_adoption_cmd.extend(["--expected-version", str(rolled_to)])
        run_json(
            rollback_adoption_cmd,
            env=env_base,
            stdout_path=evidence_dir / "service-after-rollback" / "launcher-adoption.json",
        )
        run_json(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "board" / "c18_playback_health_collect.py"),
                "--duration-sec",
                str(args.duration_sec),
                "--interval-sec",
                str(args.interval_sec),
                "--output-dir",
                str(evidence_dir / "service-after-rollback"),
                "--json",
            ],
            env=env_base,
            stdout_path=raw_dir / "service-after-rollback.json",
            timeout=1800,
        )
        trial_completed = True
    finally:
        post_trial_current_target = read_symlink_target(current_link)
        current_changed = (
            post_trial_current_target is not None
            and post_trial_current_target != pre_trial_current_target
        )
        current_is_trial_version = post_trial_current_target in {
            f"releases/{version}",
            str((args.data_root / "player-runtime" / "releases" / version).resolve()),
        }
        if not trial_completed and not rollback_completed and (apply_completed or current_changed or current_is_trial_version):
            cleanup_cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_lab_rollback.py"),
                "--lab-only-rollback",
                "--action",
                "rollback",
                "--data-root",
                str(args.data_root),
                "--allow-device-data-root",
                "--quarantine-current",
                "--output-dir",
                str(raw_dir / "abort-rollback"),
                "--reason",
                f"persistent_trial_abort_{trial_id}",
                "--json",
            ]
            proc = subprocess.run(
                cleanup_cmd,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=rollback_env,
                timeout=120,
            )
            cleanup_actions.append({
                "action": "abort_rollback",
                "returncode": proc.returncode,
                "pre_trial_current_target": pre_trial_current_target,
                "post_trial_current_target": post_trial_current_target,
                "stdout_tail": proc.stdout[-1200:],
                "stderr_tail": proc.stderr[-1200:],
            })
        if not trial_completed and (service_stopped or apply_completed or current_changed):
            cleanup_actions.append(run_systemctl_result("restart"))
        if cleanup_actions:
            write_json(
                evidence_dir / "abort-cleanup.json",
                {
                    "schema": "dadooh.c18.player_runtime.persistent_trial.abort_cleanup.v1",
                    "apply_completed": apply_completed,
                    "rollback_completed": rollback_completed,
                    "actions": cleanup_actions,
                },
            )

    write_json(evidence_dir / "README.md", {
        "schema": "dadooh.c18.player_runtime.trial_readme.v1",
        "artifact_id": trial_id,
        "component": "player-runtime",
        "version": version,
        "scope": "lab-only persistent /data trial",
        "rollback_expectation": args.rollback_expectation,
        "claims": [
            "local_package_apply",
            "verified_marker_adoption",
            "service_deep_health_after_restart",
            (
                "rollback_to_data_previous"
                if args.rollback_expectation == "data-previous"
                else "rollback_to_image_fallback"
                if args.rollback_expectation == "image-fallback"
                else "rollback_to_previous_or_image"
            ),
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
            *(
                []
                if args.rollback_expectation == "data-previous"
                else ["rollback_A_to_B_previous_data_release"]
            ),
        ],
    })
    write_evidence_manifest(
        evidence_dir,
        package_manifest=manifest,
        trial_id=trial_id,
        rollback_expectation=args.rollback_expectation,
        repo_info=repo_info,
        image_tag=args.image_tag,
        image_sha256=args.image_sha256,
        image_marker_file=args.image_marker_file,
    )
    evidence_gate = run_json(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "qa" / "c18_player_runtime_evidence_gate.py"),
            "--run-dir",
            str(evidence_dir),
            "--json",
        ],
        env=env_base,
        stdout_path=raw_dir / "evidence-gate.json",
    )
    summary = {
        "schema": SCHEMA,
        "passed": evidence_gate.get("passed") is True,
        "artifact_id": trial_id,
        "version": version,
        "evidence_dir": str(evidence_dir),
        "raw_dir": str(raw_dir),
        "evidence_gate": evidence_gate,
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"player_runtime_persistent_trial_passed={str(bool(summary['passed'])).lower()}")
        print(f"evidence_dir={evidence_dir}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
