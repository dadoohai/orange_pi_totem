#!/usr/bin/env python3
"""C18 OTA release gate.

Offline-only gate for totem-core OTA work. It does not use SSH, GitHub, apt,
pip, real config, media, or secrets. Use it before publishing a totem-core
release and before promoting a C18 OTA/image change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PY_COMPILE_TARGETS = (
    "scripts/board/totem_updatectl.py",
    "scripts/build/totem_core_image_embed.py",
    "scripts/build/derive_c18_image_lab_1_hwdecode.py",
    "scripts/sim/run_totem_core_sandbox.py",
    "scripts/qa/c18_ota_policy_static_test.py",
    "scripts/qa/c18_updatectl_freeze_downgrade_gc_test.py",
    "scripts/qa/c18_ota_release_gate.py",
)
TEST_COMMANDS = (
    ("c18_ota_policy_static", ["python3", "scripts/qa/c18_ota_policy_static_test.py"]),
    ("c18_updatectl_freeze_downgrade_gc", ["python3", "scripts/qa/c18_updatectl_freeze_downgrade_gc_test.py"]),
    ("c17_9_update_channel_policy", ["python3", "scripts/qa/c17_9_update_channel_policy_test.py"]),
    ("c18_runtime_3_release_perms", ["python3", "scripts/qa/c18_runtime_3_release_perms_test.py"]),
)
BASH_SYNTAX_TARGETS = (
    "scripts/deploy/build_totem_core_release_package.sh",
    "scripts/deploy/publish_totem_core_github_release.sh",
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
    checks["created_at_utc_present"] = isinstance(data.get("created_at_utc"), str) and bool(data.get("created_at_utc"))
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
    parser.add_argument("--sandbox", type=Path, default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    steps: list[dict[str, Any]] = []
    package_result: dict[str, Any] | None = None

    steps.append(run_step("py_compile", ["python3", "-m", "py_compile", *PY_COMPILE_TARGETS]))
    for target in BASH_SYNTAX_TARGETS:
        steps.append(run_step(f"bash_syntax:{target}", ["bash", "-n", target]))
    for name, cmd in TEST_COMMANDS:
        steps.append(run_step(name, cmd))

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
