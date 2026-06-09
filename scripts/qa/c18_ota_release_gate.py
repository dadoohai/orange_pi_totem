#!/usr/bin/env python3
"""C18 OTA release gate.

Offline-only gate for totem-core OTA work. It does not use SSH, GitHub, apt,
pip, real config, media, or secrets. Use it before publishing a totem-core
release and before promoting a C18 OTA/image change.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from c18_current_golden import load_current_golden


REPO_ROOT = Path(__file__).resolve().parents[2]
CURRENT_GOLDEN = load_current_golden()
CURRENT_COLDBOOT_EVIDENCE_DIR = str(CURRENT_GOLDEN["coldboot_evidence_dir"])
CURRENT_GOLDEN_IMAGE_TAG = str(CURRENT_GOLDEN["image_tag"])
CURRENT_GOLDEN_IMAGE_SHA256 = str(CURRENT_GOLDEN["image_sha256"])
CURRENT_GOLDEN_IMAGE_MARKER_SHA256 = str(CURRENT_GOLDEN["image_marker_sha256"])
PY_COMPILE_TARGETS = (
    "scripts/board/totem_config_contract_validate.py",
    "scripts/board/totem_config_writer_real.py",
    "scripts/board/totem_visual_setup_writer_handoff.py",
    "scripts/board/totem_status_render_preview.py",
    "scripts/board/totem_updatectl.py",
    "scripts/board/c18_coldboot_state_collect.py",
    "scripts/board/c18_playback_health_collect.py",
    "scripts/board/c18_playback_soak_collect.py",
    "scripts/board/c18_playback_health_summary.py",
    "scripts/board/c18_player_runtime_candidate_health.py",
    "scripts/build/totem_core_image_embed.py",
    "scripts/build/derive_c18_image_lab_1_hwdecode.py",
    "scripts/sim/run_totem_core_sandbox.py",
    "scripts/sim/run_player_runtime_sandbox.py",
    "scripts/qa/c18_ota_policy_static_test.py",
    "scripts/qa/c18_updatectl_freeze_downgrade_gc_test.py",
    "scripts/qa/c18_player_runtime_static_test.py",
    "scripts/qa/c18_player_runtime_release_gate.py",
    "scripts/qa/c18_player_runtime_lab_apply.py",
    "scripts/qa/c18_player_runtime_lab_rollback.py",
    "scripts/qa/c18_player_runtime_adoption_probe.py",
    "scripts/qa/c18_current_golden.py",
    "scripts/qa/c18_coldboot_evidence_gate.py",
    "scripts/qa/c18_player_runtime_evidence_gate.py",
    "scripts/qa/c18_player_runtime_persistent_trial.py",
    "scripts/qa/c18_player_runtime_m6_coldboot_trial.py",
    "scripts/qa/c18_player_runtime_lab_thaw.py",
    "scripts/qa/c18_playback_deep_health_fixture_test.py",
    "scripts/qa/c18_ota_release_gate.py",
    "player-runtime/kiosky-player/kiosk.py",
)
TEST_COMMANDS = (
    ("totem_config_contract_self_test", ["python3", "scripts/board/totem_config_contract_validate.py", "--self-test"]),
    ("totem_config_writer_real_self_test", ["python3", "scripts/board/totem_config_writer_real.py", "--self-test"]),
    ("totem_visual_setup_writer_handoff_self_test", ["python3", "scripts/board/totem_visual_setup_writer_handoff.py", "--self-test"]),
    ("totem_status_render_preview_self_test", ["python3", "scripts/board/totem_status_render_preview.py", "--self-test"]),
    ("c18_ota_policy_static", ["python3", "scripts/qa/c18_ota_policy_static_test.py"]),
    ("c18_updatectl_freeze_downgrade_gc", ["python3", "scripts/qa/c18_updatectl_freeze_downgrade_gc_test.py"]),
    ("c18_player_runtime_static", ["python3", "scripts/qa/c18_player_runtime_static_test.py"]),
    ("c18_player_runtime_release_gate", ["python3", "scripts/qa/c18_player_runtime_release_gate.py", "--self-test"]),
    ("c18_coldboot_evidence_gate", ["python3", "scripts/qa/c18_coldboot_evidence_gate.py", "--self-test"]),
    ("c18_playback_soak_collect_self_test", ["python3", "scripts/board/c18_playback_soak_collect.py", "--self-test"]),
    ("c18_coldboot_evidence_current", [
        "python3",
        "scripts/qa/c18_coldboot_evidence_gate.py",
        "--run-dir",
        CURRENT_COLDBOOT_EVIDENCE_DIR,
        "--expect-selected-source",
        "fallback",
        "--json",
    ]),
    ("c18_playback_deep_health_fixture", ["python3", "scripts/qa/c18_playback_deep_health_fixture_test.py"]),
    ("c17_9_update_channel_policy", ["python3", "scripts/qa/c17_9_update_channel_policy_test.py"]),
    ("c18_runtime_3_release_perms", ["python3", "scripts/qa/c18_runtime_3_release_perms_test.py"]),
    ("player_runtime_sandbox", ["python3", "scripts/sim/run_player_runtime_sandbox.py", "--json"]),
)
BASH_SYNTAX_TARGETS = (
    "scripts/board/kiosky_playback_observer_probe.sh",
    "scripts/board/kiosky_service_observer_probe.sh",
    "scripts/board/mpv_controller_playlist_probe.sh",
    "scripts/deploy/build_player_runtime_release_package.sh",
    "scripts/deploy/build_totem_core_release_package.sh",
    "scripts/deploy/publish_totem_core_github_release.sh",
    "scripts/remote/apply_c15_1_1_session_hotfix.sh",
    "scripts/remote/bootstrap_c14_1_1_on_board.sh",
    "scripts/remote/bootstrap_c17_5_totem_core_on_board.sh",
    "scripts/remote/deploy_kiosky_player.sh",
    "scripts/remote/push_and_run.sh",
    "scripts/remote/validate_c14_2_1_clean_board.sh",
)
FORBIDDEN_TAR_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "config.json",
    "private-values.seed.json",
    ".env",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
}
SECRET_PATTERNS = (
    "github_pat_",
    "ghp_",
    "gho_",
    "ghs_",
    "-----BEGIN ",
)
FORBIDDEN_TOTEM_CORE_TAR_NAMES = {
    "bin/kiosky_service_launcher.sh",
    "./bin/kiosky_service_launcher.sh",
    "bin/totem-kiosky-launcher.sh",
    "./bin/totem-kiosky-launcher.sh",
}
PLAYER_RUNTIME_DIFF_PATHS = {
    "scripts/board/kiosky_service_launcher.sh",
    "scripts/board/totem-kiosky-launcher.sh",
    "scripts/board/kiosky-player.service",
    "scripts/board/systemd/kiosky-player.service.d/20-dadooh-launcher.conf",
    "player-runtime/kiosky-player/kiosk.py",
    "player-runtime/kiosky-player/SOURCE.json",
}


def run_step(name: str, cmd: list[str], *, timeout: int = 180) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return {
        "name": name,
        "cmd": cmd,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def failed_internal_step(name: str, message: str) -> dict[str, Any]:
    return {
        "name": name,
        "cmd": ["internal", name],
        "returncode": 1,
        "passed": False,
        "stdout_tail": "",
        "stderr_tail": message,
    }


def repo_clean_guard() -> dict[str, Any]:
    cmd = ["git", "status", "--porcelain", "--untracked-files=normal"]
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    dirty = bool(proc.stdout.strip())
    return {
        "name": "repo_clean_guard",
        "cmd": cmd,
        "returncode": 1 if proc.returncode != 0 or dirty else 0,
        "passed": proc.returncode == 0 and not dirty,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": (
            proc.stderr[-4000:]
            if proc.returncode != 0
            else "repository must be clean before claiming C18 release readiness"
            if dirty
            else ""
        ),
    }


def load_json_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return data


def player_runtime_data_evidence_summary(args: argparse.Namespace) -> dict[str, Any]:
    required = args.player_runtime_evidence_mode == "decisive"
    return {
        "required": required,
        "decisive": False,
        "status": "pending" if required else "not_requested",
        "mode": args.player_runtime_evidence_mode,
        "coldboot_evidence_dir": (
            str(args.player_runtime_data_coldboot_evidence_dir)
            if args.player_runtime_data_coldboot_evidence_dir is not None
            else None
        ),
        "data_evidence_dir": (
            str(args.player_runtime_data_evidence_dir)
            if args.player_runtime_data_evidence_dir is not None
            else None
        ),
        "expected_image_tag": args.expect_image_tag,
        "expected_image_sha256": args.expect_image_sha256,
        "expected_image_marker_sha256": args.expect_image_marker_sha256,
        "non_claims": [] if required else [
            "player_runtime_data_coldboot",
            "player_runtime_data_release_adoption",
            "player_runtime_public_thaw",
            "stable_or_production",
        ],
        "errors": [],
    }


def link_player_runtime_data_evidence(coldboot_dir: Path, data_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        marker = load_json_file(data_dir / "verified-marker.json")
    except Exception as exc:
        return failed_internal_step("c18_player_runtime_data_evidence_link", f"verified_marker_read_failed:{type(exc).__name__}")
    try:
        boot = load_json_file(coldboot_dir / "boot-state-public.json")
    except Exception as exc:
        return failed_internal_step("c18_player_runtime_data_evidence_link", f"boot_state_read_failed:{type(exc).__name__}")
    player = boot.get("player_runtime")
    if not isinstance(player, dict):
        errors.append("coldboot_player_runtime_missing")
        player = {}
    checks = {
        "version": (
            marker.get("version"),
            player.get("data_current_marker_version"),
        ),
        "tree_sha256": (
            marker.get("tree_sha256"),
            player.get("data_current_tree_sha256"),
        ),
        "kiosk_py_sha256": (
            marker.get("kiosk_py_sha256"),
            player.get("data_current_kiosk_py_sha256"),
        ),
    }
    for key, (expected, actual) in checks.items():
        if not expected or not actual:
            errors.append(f"{key}_missing")
        elif expected != actual:
            errors.append(f"{key}_mismatch")
    passed = not errors
    return {
        "name": "c18_player_runtime_data_evidence_link",
        "cmd": ["internal", "link_player_runtime_data_evidence"],
        "returncode": 0 if passed else 1,
        "passed": passed,
        "stdout_tail": json.dumps({
            "version": checks["version"][0],
            "tree_sha256": checks["tree_sha256"][0],
            "kiosk_py_sha256": checks["kiosk_py_sha256"][0],
        }, sort_keys=True),
        "stderr_tail": ",".join(errors),
    }


def player_runtime_decisive_data_evidence_steps(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    summary = player_runtime_data_evidence_summary(args)
    if args.player_runtime_evidence_mode == "decisive":
        if args.player_runtime_data_coldboot_evidence_dir is None:
            steps.append(failed_internal_step(
                "c18_player_runtime_data_coldboot_evidence_required",
                "missing --player-runtime-data-coldboot-evidence-dir",
            ))
            summary["errors"].append("missing_player_runtime_data_coldboot_evidence_dir")
        if args.player_runtime_data_evidence_dir is None:
            steps.append(failed_internal_step(
                "c18_player_runtime_data_evidence_required",
                "missing --player-runtime-data-evidence-dir",
            ))
            summary["errors"].append("missing_player_runtime_data_evidence_dir")
    image_marker_arg: list[str] = []
    if args.expect_image_marker_sha256:
        image_marker_arg = ["--expect-image-marker-sha256", args.expect_image_marker_sha256]
    if args.player_runtime_data_coldboot_evidence_dir is not None:
        steps.append(run_step(
            "c18_player_runtime_data_coldboot_evidence",
            [
                "python3",
                "scripts/qa/c18_coldboot_evidence_gate.py",
                "--run-dir",
                str(args.player_runtime_data_coldboot_evidence_dir),
                "--expect-selected-source",
                "data",
                "--require-pre-state",
                "--expect-image-tag",
                args.expect_image_tag,
                *image_marker_arg,
                "--json",
            ],
        ))
    if args.player_runtime_data_evidence_dir is not None:
        steps.append(run_step(
            "c18_player_runtime_data_evidence",
            [
                "python3",
                "scripts/qa/c18_player_runtime_evidence_gate.py",
                "--run-dir",
                str(args.player_runtime_data_evidence_dir),
                "--expect-image-tag",
                args.expect_image_tag,
                "--expect-image-sha256",
                args.expect_image_sha256,
                *image_marker_arg,
                "--json",
            ],
        ))
    if (
        args.player_runtime_evidence_mode == "decisive"
        and args.player_runtime_data_coldboot_evidence_dir is not None
        and args.player_runtime_data_evidence_dir is not None
    ):
        steps.append(link_player_runtime_data_evidence(
            args.player_runtime_data_coldboot_evidence_dir,
            args.player_runtime_data_evidence_dir,
        ))
    if summary["errors"]:
        summary["status"] = "failed"
    return steps, summary


def player_runtime_decisive_dirty_manifest_guard(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.player_runtime_evidence_mode == "decisive" and args.allow_dirty_manifest:
        return failed_internal_step(
            "player_runtime_decisive_dirty_manifest_guard",
            "--allow-dirty-manifest is not allowed for player-runtime decisive evidence",
        )
    return None


def player_runtime_diff_guard(base_ref: str | None = None) -> dict[str, Any]:
    names: set[str] = set()
    for cmd in (
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            return {
                "name": "player_runtime_diff_guard",
                "cmd": cmd,
                "returncode": proc.returncode,
                "passed": False,
                "stdout_tail": proc.stdout[-4000:],
                "stderr_tail": proc.stderr[-4000:],
            }
        names.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
    base_cmd: list[str] | None = None
    if base_ref:
        merge_base = subprocess.run(
            ["git", "merge-base", base_ref, "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if merge_base.returncode != 0:
            return {
                "name": "player_runtime_diff_guard",
                "cmd": ["git", "merge-base", base_ref, "HEAD"],
                "returncode": merge_base.returncode,
                "passed": False,
                "stdout_tail": merge_base.stdout[-4000:],
                "stderr_tail": merge_base.stderr[-4000:],
            }
        base_cmd = ["git", "diff", "--name-only", f"{base_ref}...HEAD"]
        proc = subprocess.run(
            base_cmd,
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            return {
                "name": "player_runtime_diff_guard",
                "cmd": base_cmd,
                "returncode": proc.returncode,
                "passed": False,
                "stdout_tail": proc.stdout[-4000:],
                "stderr_tail": proc.stderr[-4000:],
            }
        names.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
    hits = sorted(names & PLAYER_RUNTIME_DIFF_PATHS)
    message = (
        "player-runtime files changed; this is outside ordinary totem-core OTA "
        "and requires image/homologation or an explicit C18-aware player-runtime release"
    )
    return {
        "name": "player_runtime_diff_guard",
        "cmd": [
            "git",
            "diff/status name scan",
            *(["--base-ref", base_ref] if base_ref else []),
        ],
        "returncode": 1 if hits else 0,
        "passed": not hits,
        "stdout_tail": "\n".join(hits),
        "stderr_tail": message if hits else "",
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def payload_for_manifest(manifest_path: Path, override: Path | None) -> Path:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = override or manifest_path.parent / str(data.get("payload", ""))
    return payload


def is_utc_timestamp(raw: Any) -> bool:
    if not isinstance(raw, str) or not raw:
        return False
    value = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == dt.timedelta(0)


def validate_package(manifest_path: Path, payload_path: Path | None, *, allow_dirty: bool) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    payload_path = payload_for_manifest(manifest_path, payload_path).resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    result: dict[str, Any] = {
        "manifest": str(manifest_path),
        "payload": str(payload_path),
        "component": data.get("component"),
        "version": data.get("version"),
        "channel": data.get("channel"),
        "source_commit": data.get("source_commit"),
        "source_dirty": data.get("source_dirty"),
        "dirty_allowed": allow_dirty,
        "checks": {},
        "errors": [],
    }
    checks = result["checks"]
    errors = result["errors"]

    expected_payload = f"dadooh-{data.get('component')}-{data.get('version')}.tar.gz"
    checks["manifest_schema"] = data.get("schema") == "dadooh.totem.update.v1"
    checks["component_totem_core"] = data.get("component") == "totem-core"
    checks["channel_valid"] = data.get("channel") in {"lab", "homologation", "stable"}
    checks["source_clean_or_allowed"] = allow_dirty or data.get("source_dirty") is False
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    result["repo_dirty"] = bool(status.stdout.strip())
    checks["repo_worktree_clean_or_allowed"] = allow_dirty or (status.returncode == 0 and not status.stdout.strip())
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    checks["source_commit_is_head"] = (
        head.returncode == 0
        and isinstance(data.get("source_commit"), str)
        and data.get("source_commit") == head.stdout.strip()
    )
    checks["payload_name_exact"] = data.get("payload") == expected_payload and payload_path.name == expected_payload
    checks["created_at_utc_utc_timestamp"] = is_utc_timestamp(data.get("created_at_utc"))
    checks["requires_device"] = (data.get("requires") or {}).get("device") == "orangepizero3"
    checks["requires_device_track"] = (data.get("requires") or {}).get("device_track") == "c18-hwdecode"
    required_features = set((data.get("requires") or {}).get("updater_features") or [])
    expected_features = {
        "c18-freeze-kiosky-player-v1",
        "c18-rollback-reapply-v1",
        "c18-safe-payload-v1",
        "c18-track-v1",
    }
    checks["requires_updater_features"] = expected_features.issubset(required_features)
    checks["updates_non_empty"] = isinstance(data.get("updates"), list) and bool(data.get("updates"))
    checks["payload_exists"] = payload_path.is_file()
    if checks["payload_exists"]:
        actual_sha = sha256_file(payload_path)
        checks["payload_sha256_matches"] = actual_sha == str(data.get("payload_sha256", "")).lower()
        result["payload_sha256"] = actual_sha
    else:
        checks["payload_sha256_matches"] = False

    if checks["payload_exists"]:
        try:
            with tarfile.open(payload_path, "r:gz") as tf:
                names = tf.getnames()
                bad_names = []
                for name in names:
                    parts = Path(name).parts
                    if name.startswith("/") or ".." in parts or any(part in FORBIDDEN_TAR_PARTS for part in parts):
                        bad_names.append(name)
                bad_types = [
                    member.name
                    for member in tf.getmembers()
                    if not (member.isfile() or member.isdir())
                ]
                checks["tar_no_path_escape_or_forbidden_entries"] = not bad_names
                checks["tar_regular_files_and_dirs_only"] = not bad_types
                checks["tar_excludes_player_launcher"] = not (
                    data.get("component") == "totem-core"
                    and any(name.lstrip("./") in FORBIDDEN_TOTEM_CORE_TAR_NAMES for name in names)
                )
                result["tar_entry_count"] = len(names)
                result["tar_bad_entries"] = bad_names[:20]
                result["tar_bad_type_entries"] = bad_types[:20]
                small_text_hits: list[str] = []
                for member in tf.getmembers():
                    if not member.isfile() or member.size > 256 * 1024:
                        continue
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        continue
                    text = extracted.read().decode("utf-8", "ignore").lower()
                    if any(pattern.lower() in text for pattern in SECRET_PATTERNS):
                        small_text_hits.append(member.name)
                checks["tar_secret_pattern_paths_absent"] = not small_text_hits
                result["tar_secret_pattern_path_hits"] = small_text_hits[:20]
        except Exception as exc:
            checks["tar_no_path_escape_or_forbidden_entries"] = False
            checks["tar_secret_pattern_paths_absent"] = False
            errors.append(f"tar_read_failed:{exc}")

    for key, passed in checks.items():
        if not passed:
            errors.append(key)
    result["passed"] = not errors
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the offline C18 OTA release gate.")
    parser.add_argument("--package-manifest", type=Path, default=None)
    parser.add_argument("--package-payload", type=Path, default=None)
    parser.add_argument("--allow-dirty-manifest", action="store_true")
    parser.add_argument("--base-ref", default=os.environ.get("C18_OTA_BASE_REF") or None)
    parser.add_argument("--sandbox", type=Path, default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--player-runtime-data-coldboot-evidence-dir", type=Path, default=None)
    parser.add_argument("--player-runtime-data-evidence-dir", type=Path, default=None)
    parser.add_argument("--player-runtime-evidence-mode", choices=("baseline", "decisive"), default="baseline")
    parser.add_argument("--expect-image-tag", default=CURRENT_GOLDEN_IMAGE_TAG)
    parser.add_argument("--expect-image-sha256", default=CURRENT_GOLDEN_IMAGE_SHA256)
    parser.add_argument("--expect-image-marker-sha256", default=CURRENT_GOLDEN_IMAGE_MARKER_SHA256)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    steps: list[dict[str, Any]] = []
    package_result: dict[str, Any] | None = None

    steps.append(repo_clean_guard())
    dirty_manifest_guard = player_runtime_decisive_dirty_manifest_guard(args)
    if dirty_manifest_guard is not None:
        steps.append(dirty_manifest_guard)
    steps.append(run_step("py_compile", ["python3", "-m", "py_compile", *PY_COMPILE_TARGETS]))
    for target in BASH_SYNTAX_TARGETS:
        steps.append(run_step(f"bash_syntax:{target}", ["bash", "-n", target]))
    steps.append(player_runtime_diff_guard(args.base_ref))
    for name, cmd in TEST_COMMANDS:
        step_cmd = list(cmd)
        if name == "player_runtime_sandbox":
            step_cmd.extend(["--sandbox", tempfile.mkdtemp(prefix="c18-player-runtime-sandbox-")])
        steps.append(run_step(name, step_cmd))
    data_evidence_steps, data_evidence_summary = player_runtime_decisive_data_evidence_steps(args)
    steps.extend(data_evidence_steps)
    if data_evidence_steps:
        failed_data_steps = [step["name"] for step in data_evidence_steps if not step["passed"]]
        if failed_data_steps:
            data_evidence_summary["status"] = "failed"
            data_evidence_summary["errors"].extend(failed_data_steps)
        elif args.player_runtime_evidence_mode == "decisive":
            data_evidence_summary["status"] = "passed"
            data_evidence_summary["decisive"] = True
        else:
            data_evidence_summary["status"] = "advisory_passed"

    steps.append(run_step("git_diff_check", ["git", "diff", "--check"]))

    sandbox = args.sandbox or Path(tempfile.mkdtemp(prefix="c18-ota-gate-sandbox-"))
    evidence = args.evidence_dir or Path(tempfile.mkdtemp(prefix="c18-ota-gate-evidence-"))
    sandbox_cmd = [
        "python3",
        "scripts/sim/run_totem_core_sandbox.py",
        "--sandbox",
        str(sandbox),
        "--evidence-dir",
        str(evidence),
        "--json",
    ]
    if args.package_manifest is not None:
        package_result = validate_package(
            args.package_manifest,
            args.package_payload,
            allow_dirty=args.allow_dirty_manifest,
        )
        sandbox_cmd.extend(["--package-manifest", str(args.package_manifest)])
        if args.package_payload is not None:
            sandbox_cmd.extend(["--package-payload", str(args.package_payload)])
    steps.append(run_step("totem_core_sandbox", sandbox_cmd, timeout=240))

    passed = all(step["passed"] for step in steps) and (package_result is None or bool(package_result["passed"]))
    result = {
        "schema": "dadooh.c18.ota.release_gate.v1",
        "passed": passed,
        "steps": steps,
        "package": package_result,
        "sandbox": str(sandbox),
        "evidence_dir": str(evidence),
        "current_golden": CURRENT_GOLDEN,
        "player_runtime_data_evidence": data_evidence_summary,
        "guardrails": {
            "ssh_used": False,
            "github_used": False,
            "apt_used": False,
            "pip_used": False,
            "secrets_read": False,
            "media_read": False,
        },
    }
    print(json.dumps(result, indent=2 if args.json else None, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
