#!/usr/bin/env python3
"""Lab-only C18 player-runtime physical power-loss checkpoint harness.

This harness turns existing player-runtime crash-boundary hooks into an
operator-attended physical power-loss trial. It does not thaw the public
updater CLI and does not publish or fetch anything. The harness arms one named
checkpoint, writes/fsyncs a checkpoint artifact, prints CUT_POWER_NOW, and then
waits for the operator to remove power. Phase ``resume`` validates the state
after boot using the existing adoption, deep-health and reconcile tools.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QA_DIR = REPO_ROOT / "scripts" / "qa"
BOARD_DIR = REPO_ROOT / "scripts" / "board"
sys.path.insert(0, str(QA_DIR))
sys.path.insert(0, str(BOARD_DIR))

import c18_player_runtime_lab_apply as lab_apply  # noqa: E402
import c18_player_runtime_lab_rollback as lab_rollback  # noqa: E402
import totem_updatectl as updatectl  # noqa: E402


SCHEMA = "dadooh.c18.player_runtime.powerloss_trial.v1"
LAB_ENV = "C18_PLAYER_RUNTIME_POWER_LOSS_TRIAL"
DEVICE_DATA_ENV = "C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT"
APPLY_ENV = "C18_PLAYER_RUNTIME_LAB_APPLY"
ROLLBACK_ENV = "C18_PLAYER_RUNTIME_LAB_ROLLBACK"
SERVICE = "kiosky-player.service"

APPLY_CHECKPOINTS = {
    "after_payload_staged",
    "after_release_dir_created",
    "after_extract",
    "after_state_verifying",
    "after_health_passed",
    "after_release_tree_fsync",
    "after_marker_written",
    "after_previous_symlink",
    "after_current_symlink",
    "after_state_success",
    "before_stage_cleanup",
}
ROLLBACK_CHECKPOINTS = {
    "rollback_after_identify_links",
    "rollback_after_current_to_previous",
    "rollback_after_previous_removed",
    "rollback_after_quarantine",
    "rollback_after_current_unlinked",
    "rollback_after_state_success",
}


class CheckpointWaitExpired(RuntimeError):
    pass


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_json_fsync(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    fsync_dir(path.parent)


def write_text_fsync(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    fsync_dir(path.parent)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return data


def path_is_under(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    root_resolved = root.resolve()
    return resolved == root_resolved or root_resolved in resolved.parents


def require_lab_guard(args: argparse.Namespace) -> None:
    if os.environ.get(LAB_ENV) != "1":
        raise RuntimeError(f"powerloss_guard_required:set {LAB_ENV}=1")
    touches_device_data = path_is_under(args.data_root, Path("/data")) or path_is_under(args.evidence_root, Path("/data"))
    if touches_device_data and (
        not args.allow_device_data_root or os.environ.get(DEVICE_DATA_ENV) != "1"
    ):
        raise RuntimeError(f"device_data_root_guard_required:set {DEVICE_DATA_ENV}=1 and pass --allow-device-data-root")


def env_base(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if extra:
        env.update(extra)
    return env


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
        "action": "systemctl " + " ".join([*args, SERVICE]),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-400:],
        "stderr_tail": proc.stderr[-400:],
        "passed": proc.returncode == 0,
    }


def require_systemctl(result: dict[str, Any], label: str) -> None:
    if result.get("returncode") != 0:
        raise RuntimeError(f"{label}_failed:{result.get('stderr_tail') or result.get('stdout_tail')}")


def restart_service_best_effort(evidence_root: Path, label: str) -> None:
    unmask = run_systemctl_service("unmask")
    start = run_systemctl_service("start")
    write_json_fsync(evidence_root / f"{label}-service-restore.json", {
        "schema": SCHEMA,
        "phase": label,
        "unmask": unmask,
        "start": start,
    })


def safe_context(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): safe_context(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_context(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def runtime_snapshot() -> dict[str, Any]:
    state: dict[str, Any] = {}
    try:
        state = updatectl._read_state()
    except Exception:
        state = {}
    quarantine = state.get("quarantine") or state.get("quarantined_identities") or []
    if not isinstance(quarantine, list):
        quarantine = []
    return {
        "current_link": updatectl._read_symlink_target(updatectl.CURRENT_LINK),
        "previous_link": updatectl._read_symlink_target(updatectl.PREVIOUS_LINK),
        "state_current_version": (state.get("current") or {}).get("version") if isinstance(state.get("current"), dict) else None,
        "state_previous_version": (state.get("previous") or {}).get("version") if isinstance(state.get("previous"), dict) else None,
        "last_operation": state.get("last_operation") if isinstance(state.get("last_operation"), dict) else None,
        "quarantine": [entry for entry in quarantine if isinstance(entry, dict)],
    }


def boot_state() -> dict[str, Any]:
    state: dict[str, Any] = {"captured_at_utc": utcnow()}
    try:
        state["boot_id"] = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    except OSError:
        state["boot_id"] = None
    try:
        state["uptime_sec"] = float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        state["uptime_sec"] = None
    try:
        for line in Path("/proc/stat").read_text(encoding="utf-8").splitlines():
            if line.startswith("btime "):
                state["btime"] = int(line.split()[1])
                break
        else:
            state["btime"] = None
    except (OSError, ValueError, IndexError):
        state["btime"] = None
    return state


def checkpoint_hook(args: argparse.Namespace, action: str):
    def hook(label: str, context: dict[str, Any]) -> None:
        if label != args.checkpoint:
            return
        checkpoint_dir = args.evidence_root / "powerloss-checkpoint"
        checkpoint = {
            "schema": SCHEMA,
            "phase": "armed",
            "action": action,
            "checkpoint": label,
            "hit_at_utc": utcnow(),
            "wait_sec": args.wait_for_power_cut_sec,
            "data_root": str(args.data_root),
            "context": safe_context(context),
            "runtime_snapshot": runtime_snapshot(),
            "boot_state_at_checkpoint": boot_state(),
            "operator_instruction": "CUT_POWER_NOW",
            "non_claims": [
                "power_loss_observed_until_board_boots_and_resume_phase_passes",
                "public_player_runtime_thaw",
                "stable_or_production",
            ],
        }
        write_json_fsync(checkpoint_dir / "checkpoint.json", checkpoint)
        write_text_fsync(
            checkpoint_dir / "CUT_POWER_NOW.txt",
            f"CUT_POWER_NOW checkpoint={label} action={action} evidence={checkpoint_dir}\n",
        )
        fsync_dir(checkpoint_dir)
        print(f"C18_POWERLOSS_CHECKPOINT_REACHED action={action} checkpoint={label}", flush=True)
        print("CUT_POWER_NOW", flush=True)
        deadline = time.monotonic() + max(args.wait_for_power_cut_sec, 0.0)
        while time.monotonic() < deadline:
            time.sleep(1.0)
        raise CheckpointWaitExpired(f"power_cut_not_observed_before_timeout:{label}")
    return hook


def run_apply_arm(args: argparse.Namespace) -> int:
    if args.checkpoint not in APPLY_CHECKPOINTS:
        raise RuntimeError(f"unsupported_apply_checkpoint:{args.checkpoint}")
    if args.evidence_root.exists() and any(args.evidence_root.iterdir()):
        raise RuntimeError(f"evidence_root_must_be_empty:{args.evidence_root}")
    args.evidence_root.mkdir(parents=True, exist_ok=True)
    write_json_fsync(args.evidence_root / "powerloss-trial-state.json", {
        "schema": SCHEMA,
        "phase": "arm-apply",
        "checkpoint": args.checkpoint,
        "manifest": str(args.manifest),
        "payload": str(args.payload),
        "data_root": str(args.data_root),
        "armed_at_utc": utcnow(),
    })
    service_held = False
    stop_result = run_systemctl_service("stop")
    write_json_fsync(args.evidence_root / "service-stop-before-apply.json", {
        "schema": SCHEMA,
        "phase": "arm-apply",
        "result": stop_result,
    })
    require_systemctl(stop_result, "service_stop_before_powerloss_apply")
    try:
        mask_result = run_systemctl_service("mask", "--runtime")
        write_json_fsync(args.evidence_root / "service-runtime-mask-before-apply.json", {
            "schema": SCHEMA,
            "phase": "arm-apply",
            "result": mask_result,
        })
        require_systemctl(mask_result, "service_runtime_mask_before_powerloss_apply")
        service_held = True
    except Exception:
        restart_service_best_effort(args.evidence_root, "arm-apply-mask-failed")
        raise
    previous_hook = updatectl.PLAYER_RUNTIME_FAULT_HOOK
    updatectl.PLAYER_RUNTIME_FAULT_HOOK = checkpoint_hook(args, "apply")
    old_apply_env = os.environ.get(APPLY_ENV)
    old_device_env = os.environ.get(DEVICE_DATA_ENV)
    os.environ[APPLY_ENV] = "1"
    os.environ[DEVICE_DATA_ENV] = "1"
    try:
        try:
            apply_argv = [
                "--lab-only-apply",
                "--manifest", str(args.manifest),
                "--payload", str(args.payload),
                "--data-root", str(args.data_root),
                "--allow-device-data-root",
                "--canary-media", str(args.canary_media),
                "--output-dir", str(args.evidence_root / "raw" / "apply"),
                "--duration-sec", str(args.duration_sec),
                "--interval-sec", str(args.interval_sec),
                "--startup-wait-sec", str(args.startup_wait_sec),
                "--json",
            ]
            if args.allow_reapply_linked_previous:
                apply_argv.append("--allow-reapply-linked-previous")
            rc = lab_apply.main(apply_argv)
        except CheckpointWaitExpired as exc:
            write_json_fsync(args.evidence_root / "arm-timeout.json", {
                "schema": SCHEMA,
                "phase": "arm-apply",
                "passed": False,
                "checkpoint_reached": True,
                "reason": str(exc),
                "resume_required": True,
            })
            return 75
    finally:
        updatectl.PLAYER_RUNTIME_FAULT_HOOK = previous_hook
        if old_apply_env is None:
            os.environ.pop(APPLY_ENV, None)
        else:
            os.environ[APPLY_ENV] = old_apply_env
        if old_device_env is None:
            os.environ.pop(DEVICE_DATA_ENV, None)
        else:
            os.environ[DEVICE_DATA_ENV] = old_device_env
        if service_held:
            restart_service_best_effort(args.evidence_root, "arm-apply")
    write_json_fsync(args.evidence_root / "arm-result.json", {
        "schema": SCHEMA,
        "phase": "arm-apply",
        "passed": False,
        "checkpoint_reached": False,
        "rc": rc,
        "reason": "apply_completed_without_checkpoint",
    })
    return 1


def run_rollback_arm(args: argparse.Namespace) -> int:
    if args.checkpoint not in ROLLBACK_CHECKPOINTS:
        raise RuntimeError(f"unsupported_rollback_checkpoint:{args.checkpoint}")
    if args.evidence_root.exists() and any(args.evidence_root.iterdir()):
        raise RuntimeError(f"evidence_root_must_be_empty:{args.evidence_root}")
    args.evidence_root.mkdir(parents=True, exist_ok=True)
    write_json_fsync(args.evidence_root / "powerloss-trial-state.json", {
        "schema": SCHEMA,
        "phase": "arm-rollback",
        "checkpoint": args.checkpoint,
        "data_root": str(args.data_root),
        "armed_at_utc": utcnow(),
    })
    previous_hook = updatectl.PLAYER_RUNTIME_FAULT_HOOK
    updatectl.PLAYER_RUNTIME_FAULT_HOOK = checkpoint_hook(args, "rollback")
    old_rollback_env = os.environ.get(ROLLBACK_ENV)
    old_device_env = os.environ.get(DEVICE_DATA_ENV)
    os.environ[ROLLBACK_ENV] = "1"
    os.environ[DEVICE_DATA_ENV] = "1"
    argv = [
        "--lab-only-rollback",
        "--action", "rollback",
        "--data-root", str(args.data_root),
        "--allow-device-data-root",
        "--output-dir", str(args.evidence_root / "raw" / "rollback"),
        "--reason", "physical_powerloss_trial",
        "--json",
    ]
    if args.quarantine_current:
        argv.append("--quarantine-current")
    if args.expect_rolled_to:
        argv.extend(["--expect-rolled-to", args.expect_rolled_to])
    try:
        rc = lab_rollback.main(argv)
    except CheckpointWaitExpired as exc:
        write_json_fsync(args.evidence_root / "arm-timeout.json", {
            "schema": SCHEMA,
            "phase": "arm-rollback",
            "passed": False,
            "checkpoint_reached": True,
            "reason": str(exc),
            "resume_required": True,
        })
        return 75
    finally:
        updatectl.PLAYER_RUNTIME_FAULT_HOOK = previous_hook
        if old_rollback_env is None:
            os.environ.pop(ROLLBACK_ENV, None)
        else:
            os.environ[ROLLBACK_ENV] = old_rollback_env
        if old_device_env is None:
            os.environ.pop(DEVICE_DATA_ENV, None)
        else:
            os.environ[DEVICE_DATA_ENV] = old_device_env
    write_json_fsync(args.evidence_root / "arm-result.json", {
        "schema": SCHEMA,
        "phase": "arm-rollback",
        "passed": False,
        "checkpoint_reached": False,
        "rc": rc,
        "reason": "rollback_completed_without_checkpoint",
    })
    return 1


def run_json(cmd: list[str], stdout_path: Path, *, env: dict[str, str] | None = None, timeout: int = 900) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=timeout,
    )
    payload: dict[str, Any]
    try:
        decoded = json.loads(proc.stdout)
        payload = decoded if isinstance(decoded, dict) else {}
    except json.JSONDecodeError:
        payload = {
            "schema": SCHEMA,
            "passed": False,
            "stdout_tail": proc.stdout[-800:],
        }
    payload.setdefault("returncode", proc.returncode)
    if proc.stderr:
        payload.setdefault("stderr_tail", proc.stderr[-800:])
    write_json_fsync(stdout_path, payload)
    if proc.returncode != 0:
        raise RuntimeError(f"command_failed:{cmd[1] if len(cmd) > 1 else cmd[0]} rc={proc.returncode}")
    return payload


def run_systemctl(action: str, stdout_path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        ["systemctl", action, SERVICE],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=45,
    )
    result = {
        "schema": SCHEMA,
        "action": f"systemctl {action} {SERVICE}",
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-800:],
        "stderr_tail": proc.stderr[-800:],
    }
    write_json_fsync(stdout_path, result)
    return result


def collect_adoption(args: argparse.Namespace, label: str, expected_source: str, expected_version: str | None) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(QA_DIR / "c18_player_runtime_adoption_probe.py"),
        "--data-root", str(args.data_root),
        "--expected-source", expected_source,
        "--json",
    ]
    if expected_version:
        cmd.extend(["--expected-version", expected_version])
    return run_json(cmd, args.evidence_root / "resume" / f"{label}-adoption.json", env=env_base())


def collect_health(args: argparse.Namespace, label: str) -> dict[str, Any]:
    out_dir = args.evidence_root / "resume" / f"{label}-health"
    cmd = [
        sys.executable,
        str(BOARD_DIR / "c18_playback_health_collect.py"),
        "--duration-sec", str(args.duration_sec),
        "--interval-sec", str(args.interval_sec),
        "--output-dir", str(out_dir),
        "--json",
    ]
    return run_json(cmd, args.evidence_root / "resume" / f"{label}-health.json", env=env_base(), timeout=1800)


def run_reconcile(args: argparse.Namespace) -> dict[str, Any]:
    env = env_base({ROLLBACK_ENV: "1", DEVICE_DATA_ENV: "1"})
    cmd = [
        sys.executable,
        str(QA_DIR / "c18_player_runtime_lab_rollback.py"),
        "--lab-only-rollback",
        "--action", "reconcile",
        "--data-root", str(args.data_root),
        "--allow-device-data-root",
        "--output-dir", str(args.evidence_root / "resume" / "reconcile"),
        "--reason", "physical_powerloss_trial_resume",
        "--json",
    ]
    return run_json(cmd, args.evidence_root / "resume" / "reconcile.json", env=env)


def run_restore_rollback(args: argparse.Namespace) -> dict[str, Any]:
    env = env_base({ROLLBACK_ENV: "1", DEVICE_DATA_ENV: "1"})
    cmd = [
        sys.executable,
        str(QA_DIR / "c18_player_runtime_lab_rollback.py"),
        "--lab-only-rollback",
        "--action", "rollback",
        "--data-root", str(args.data_root),
        "--allow-device-data-root",
        "--quarantine-current",
        "--output-dir", str(args.evidence_root / "resume" / "restore-rollback"),
        "--reason", "physical_powerloss_trial_restore",
        "--json",
    ]
    if args.restore_expect_rolled_to:
        cmd.extend(["--expect-rolled-to", args.restore_expect_rolled_to])
    return run_json(cmd, args.evidence_root / "resume" / "restore-rollback.json", env=env)


def run_resume(args: argparse.Namespace) -> int:
    checkpoint_path = args.evidence_root / "powerloss-checkpoint" / "checkpoint.json"
    if not checkpoint_path.is_file():
        raise RuntimeError(f"checkpoint_artifact_missing:{checkpoint_path}")
    checkpoint = read_json(checkpoint_path)
    resume_boot_state = boot_state()
    resume_dir = args.evidence_root / "resume"
    resume_dir.mkdir(parents=True, exist_ok=True)
    before = collect_adoption(args, "before-reconcile", args.expected_source, args.expected_version)
    before_health = collect_health(args, "before-reconcile")
    reconcile = run_reconcile(args)
    after = collect_adoption(args, "after-reconcile", args.expected_source_after_reconcile, args.expected_version_after_reconcile)
    after_health = collect_health(args, "after-reconcile")
    restore: dict[str, Any] | None = None
    restore_restart: dict[str, Any] | None = None
    restore_adoption: dict[str, Any] | None = None
    restore_health: dict[str, Any] | None = None
    if args.restore_rollback:
        restore = run_restore_rollback(args)
        restore_restart = run_systemctl("restart", resume_dir / "restore-restart.json")
        time.sleep(max(args.startup_wait_sec, 0.0))
        restore_adoption = collect_adoption(
            args,
            "after-restore-rollback",
            args.restore_expected_source,
            args.restore_expect_rolled_to,
        )
        restore_health = collect_health(args, "after-restore-rollback")
    passed = (
        before.get("passed") is True
        and before_health.get("passed") is True
        and reconcile.get("passed") is True
        and after.get("passed") is True
        and after_health.get("passed") is True
        and (not args.restore_rollback or (
            restore is not None and restore.get("passed") is True
            and restore_restart is not None and restore_restart.get("passed") is True
            and restore_adoption is not None and restore_adoption.get("passed") is True
            and restore_health is not None and restore_health.get("passed") is True
        ))
    )
    summary = {
        "schema": SCHEMA,
        "phase": "resume",
        "passed": passed,
        "checkpoint": checkpoint,
        "boot_state_at_resume": resume_boot_state,
        "before_reconcile": before,
        "before_reconcile_health_passed": before_health.get("passed") is True,
        "reconcile": reconcile,
        "after_reconcile": after,
        "after_reconcile_health_passed": after_health.get("passed") is True,
        "restore_rollback": restore,
        "restore_restart": restore_restart,
        "restore_adoption": restore_adoption,
        "restore_health_passed": restore_health.get("passed") is True if restore_health else None,
        "non_claims": [
            "covers_only_the_named_checkpoint",
            "public_player_runtime_thaw",
            "stable_or_production",
        ],
    }
    write_json_fsync(args.evidence_root / "powerloss-summary.json", summary)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if passed else 1


def self_test() -> None:
    missing = sorted({"after_current_symlink", "after_marker_written"} - APPLY_CHECKPOINTS)
    if missing:
        raise AssertionError(f"missing apply checkpoints: {missing}")
    missing_rollback = sorted({"rollback_after_current_to_previous", "rollback_after_state_success"} - ROLLBACK_CHECKPOINTS)
    if missing_rollback:
        raise AssertionError(f"missing rollback checkpoints: {missing_rollback}")
    source = Path(__file__).read_text(encoding="utf-8")
    for token in (
        'run_systemctl_service("stop")',
        'run_systemctl_service("mask", "--runtime")',
        "restart_service_best_effort",
        "service-runtime-mask-before-apply.json",
        "--allow-reapply-linked-previous",
    ):
        if token not in source:
            raise AssertionError(f"missing service-hold token: {token}")
    payload = {"schema": SCHEMA, "ok": True}
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"c18-powerloss-self-test-{os.getpid()}.json"
    try:
        write_json_fsync(tmp, payload)
        if read_json(tmp).get("ok") is not True:
            raise AssertionError("fsync json roundtrip failed")
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--phase", choices=("arm-apply", "arm-rollback", "resume"), required=False)
    parser.add_argument("--checkpoint")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--canary-media", type=Path)
    parser.add_argument("--data-root", type=Path, default=Path("/data"))
    parser.add_argument("--allow-device-data-root", action="store_true")
    parser.add_argument("--allow-reapply-linked-previous", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=Path("/data/c18-evidence/powerloss-trial"))
    parser.add_argument("--wait-for-power-cut-sec", type=float, default=600.0)
    parser.add_argument("--duration-sec", type=float, default=45.0)
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--startup-wait-sec", type=float, default=8.0)
    parser.add_argument("--quarantine-current", action="store_true")
    parser.add_argument("--expect-rolled-to")
    parser.add_argument("--expected-source", choices=("data", "fallback", "any"), default="any")
    parser.add_argument("--expected-version")
    parser.add_argument("--expected-source-after-reconcile", choices=("data", "fallback", "any"), default="any")
    parser.add_argument("--expected-version-after-reconcile")
    parser.add_argument("--restore-rollback", action="store_true")
    parser.add_argument("--restore-expect-rolled-to")
    parser.add_argument("--restore-expected-source", choices=("data", "fallback", "any"), default="data")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        print(json.dumps({"schema": SCHEMA, "self_test": True}, sort_keys=True))
        return 0
    if not args.phase:
        raise RuntimeError("phase_required")
    require_lab_guard(args)
    if args.phase == "arm-apply":
        for key in ("checkpoint", "manifest", "payload", "canary_media"):
            if getattr(args, key) is None:
                raise RuntimeError(f"missing_required_for_arm_apply:{key}")
        return run_apply_arm(args)
    if args.phase == "arm-rollback":
        if not args.checkpoint:
            raise RuntimeError("missing_required_for_arm_rollback:checkpoint")
        return run_rollback_arm(args)
    return run_resume(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except RuntimeError as exc:
        message = str(exc)
        print(message, file=sys.stderr)
        if message.startswith("powerloss_guard_required"):
            raise SystemExit(44)
        if message.startswith("device_data_root_guard_required"):
            raise SystemExit(43)
        raise SystemExit(1)
