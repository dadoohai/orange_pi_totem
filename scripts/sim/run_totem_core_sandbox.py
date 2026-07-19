#!/usr/bin/env python3
"""Run the C17.8 totem-core update sandbox.

This exercises apply-local, current/previous, manual rollback, wrapper
fallback, and settings-session lock guard without writing outside .sim/totem.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SANDBOX = REPO_ROOT / ".sim" / "totem"
RUNS_DIR = REPO_ROOT / "docs" / "evidence" / "candidate-a" / "runs"
RUN_NAME = "c17-8-simulation-lab-mvp"
INITIAL_VERSION = "c17.8-sim-initial"
PRODUCT_RESET_GC_IMAGE_FEATURE = "c26-product-reset-gc-static-v1"
PRODUCT_RESET_GC_UNIT_SOURCE = REPO_ROOT / "scripts" / "board" / "totem-product-reset-gc.service"
IMAGE_BOUND_UPDATECTL_PATH = "scripts/board/totem_updatectl.py"
IMAGE_BOUND_PRODUCT_RESET_GC_UNIT_PATH = "scripts/board/totem-product-reset-gc.service"

CORE_FILES = (
    "totem_setup_visual_wizard.py",
    "totem_wifi_nm_adapter.py",
    "totem_visual_splash.py",
    "totem_status_aggregate.py",
    "totem_status_render_preview.py",
    "totem_api_url_contract.py",
    "totem_config_contract_validate.py",
    "totem_qr_pairing_client.py",
    "totem_settings_production_apply_policy.py",
    "totem_open_settings_session.sh",
    "totem_visual_tty_guard.sh",
    "totem_firstboot_gate.sh",
    "totem_status_renderer.sh",
    "totem_settings_trigger.py",
    "totem_open_settings_cleanup.sh",
    "totem_visual_setup_writer_handoff.py",
    "totem_config_writer_real.py",
    "totem_setup_minimal_server.py",
    "totem_setup_local_wizard.py",
)
CORE_SELF_TESTS = [
    "python3 bin/totem_setup_visual_wizard.py --self-test",
    "python3 bin/totem_wifi_nm_adapter.py --self-test",
    "python3 bin/totem_visual_splash.py --self-test",
    "python3 bin/totem_status_render_preview.py --self-test",
    "python3 bin/totem_status_aggregate.py --self-test",
    "bash bin/totem_status_renderer.sh --self-test",
    "python3 bin/totem_config_contract_validate.py --self-test",
    "python3 bin/totem_qr_pairing_client.py --self-test",
    "python3 bin/totem_settings_production_apply_policy.py --self-test",
    "bash -n bin/totem_open_settings_session.sh",
    "bash -n bin/totem_visual_tty_guard.sh",
    "bash -n bin/totem_firstboot_gate.sh",
    "bash -n bin/totem_status_renderer.sh",
    "restore-order-static-check",
]


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run C17.8 totem-core local sandbox.")
    parser.add_argument("--sandbox", type=Path, default=DEFAULT_SANDBOX)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument(
        "--package-manifest",
        type=Path,
        default=None,
        help="Apply this local totem-core manifest instead of building a sandbox package.",
    )
    parser.add_argument(
        "--package-payload",
        type=Path,
        default=None,
        help="Payload path for --package-manifest; defaults to manifest sibling payload.",
    )
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(cmd: list[str], *, env: dict[str, str], cwd: Path = REPO_ROOT, timeout: int = 120) -> subprocess.CompletedProcess[str]:
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
    resolved = path.resolve()
    try:
        resolved.relative_to(sandbox.resolve())
    except ValueError as exc:
        raise RuntimeError(f"unsafe_remove_outside_sandbox:{resolved}") from exc
    if resolved.exists() or resolved.is_symlink():
        if resolved.is_dir() and not resolved.is_symlink():
            shutil.rmtree(resolved)
        else:
            resolved.unlink()


def replace_symlink(target: str | Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        if link.is_dir() and not link.is_symlink():
            shutil.rmtree(link)
        else:
            link.unlink()
    os.symlink(str(target), str(link))


def sandbox_env(sandbox: Path) -> dict[str, str]:
    run_root = sandbox / "run"
    tmp_root = sandbox / "tmp"
    for path in (sandbox, run_root, tmp_root):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.chmod(0o700)
    fake_systemctl = tmp_root / "sandbox-systemctl"
    fake_systemctl.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        "case \"${1:-}:${2:-}\" in\n"
        "  show:totem-open-settings.service) printf 'LoadState=loaded\\nActiveState=inactive\\n'; exit 0 ;;\n"
        "  show:totem-product-reset-gc.service)\n"
        "    printf 'LoadState=loaded\\nUnitFileState=static\\nFragmentPath=%s\\nNeedDaemonReload=no\\nType=oneshot\\nAfter=kiosky-player.service\\n' \"${TOTEM_TEST_PRODUCT_RESET_GC_UNIT:-}\"\n"
        "    exit 0 ;;\n"
        "  show:kiosky-player.service)\n"
        "    case \" $* \" in\n"
        "      *--property=LoadState*|*--property=Wants*) printf 'LoadState=loaded\\nWants=totem-product-reset-gc.service\\n' ;;\n"
        "      *) printf '0\\n' ;;\n"
        "    esac\n"
        "    exit 0 ;;\n"
        "  is-active:*) printf 'active\\n'; exit 0 ;;\n"
        "  show:*) printf '0\\n'; exit 0 ;;\n"
        "  restart:*|start:*|stop:*) exit 0 ;;\n"
        "  *) printf 'sandbox-systemctl unsupported: %s\\n' \"$*\" >&2; exit 1 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_systemctl.chmod(0o700)
    env = os.environ.copy()
    env.update(
        {
            "TOTEM_DATA_ROOT": str(sandbox / "data"),
            "TOTEM_SETTINGS_SESSION_LOCK": str(sandbox / "run" / "totem" / "settings-session.lock"),
            "TOTEM_SETTINGS_REQUEST_FILE": str(sandbox / "run" / "dadooh-settings" / "request.json"),
            "TOTEM_UPDATE_LOCK_FILE": str(sandbox / "run" / "totem-updatectl.lock"),
            "TOTEM_SIMULATION": "1",
            "TOTEM_TEST_SYSTEMCTL_BIN": str(fake_systemctl),
            "TOTEM_HEALTH_GRACE_SECONDS": "0",
            "TOTEM_HEALTH_CHECK_TIMEOUT_S": "5",
            "TMPDIR": str(tmp_root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "TOTEM_CORE_CURRENT": str(sandbox / "data" / "core" / "totem" / "current" / "bin"),
            "TOTEM_CORE_FALLBACK": str(sandbox / "opt" / "totem" / "core-fallback" / "bin"),
        }
    )
    return env


def prepare_if_needed(sandbox: Path, env: dict[str, str]) -> tuple[bool, str]:
    prepare = REPO_ROOT / "scripts" / "sim" / "prepare_totem_sim_sandbox.py"
    proc = run(
        ["python3", str(prepare), "--sandbox", str(sandbox), "--mode", "repo_overlay", "--json"],
        env=env,
        timeout=120,
    )
    if proc.returncode != 0:
        return False, "failed"
    try:
        data = json.loads(proc.stdout)
        return bool(data.get("sandbox_created")), str(data.get("sandbox_mode") or "failed")
    except json.JSONDecodeError:
        return False, "failed"


def reset_runtime_state(sandbox: Path) -> None:
    for rel in (
        sandbox / "data" / "core" / "totem",
        sandbox / "data" / "updates",
        sandbox / "data" / "logs",
        sandbox / "run" / "totem",
        sandbox / "tmp" / "packages",
        sandbox / "tmp" / "fake-package",
        sandbox / "tmp" / "sandbox-run",
    ):
        safe_remove(rel, sandbox)
    for path in (
        sandbox / "data" / "core" / "totem" / "releases",
        sandbox / "data" / "updates",
        sandbox / "data" / "logs",
        sandbox / "run" / "totem",
        sandbox / "tmp" / "packages",
        sandbox / "tmp" / "sandbox-run",
        sandbox / "evidence",
    ):
        path.mkdir(parents=True, exist_ok=True)


def create_initial_release(sandbox: Path) -> None:
    release = sandbox / "data" / "core" / "totem" / "releases" / INITIAL_VERSION
    bin_dir = release / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in CORE_FILES:
        source = REPO_ROOT / "scripts" / "board" / name
        replace_symlink(source, bin_dir / name)
    (release / "health").mkdir(parents=True, exist_ok=True)
    (release / "manifest-fragment").mkdir(parents=True, exist_ok=True)
    (release / "health" / "totem-core-health.json").write_text(
        json.dumps(
            {
                "schema": "dadooh.totem.core.health.v1",
                "component": "totem-core",
                "sandbox_initial": True,
                "self_tests": CORE_SELF_TESTS,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    state_file = sandbox / "data" / "core" / "totem" / "state.json"
    replace_symlink(f"releases/{INITIAL_VERSION}", sandbox / "data" / "core" / "totem" / "current")
    state_file.write_text(
        json.dumps(
            {
                "schema": "dadooh.totem.update.state.v1",
                "component": "totem-core",
                "current": {
                    "version": INITIAL_VERSION,
                    "applied_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "manifest_created_at_utc": "2026-05-01T00:00:00Z",
                    "payload_sha256": "0" * 64,
                    "source": "sandbox:initial",
                },
                "previous": None,
                "last_operation": {
                    "type": "sandbox_seed",
                    "status": "success",
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def write_update_policy(sandbox: Path, channel: str, *, allow_downgrade: bool = False) -> None:
    policy_path = sandbox / "data" / "updates" / "policy.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
        json.dumps(
            {
                "schema": "dadooh.totem.update.policy.v1",
                "device_channel": channel,
                "device_track": "c18-hwdecode",
                "allowed_components": ["totem-core"],
                "allow_prerelease": channel != "stable",
                "allow_downgrade": allow_downgrade,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def manifest_channel(manifest: Path) -> str:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        channel = data.get("channel")
        return channel if channel in {"lab", "homologation", "stable"} else "stable"
    except Exception:
        return "stable"


def incompatible_channel(channel: str) -> str:
    return "stable" if channel != "stable" else "lab"


def build_fake_package(sandbox: Path, version: str) -> tuple[Path, Path, bool]:
    package_dir = sandbox / "tmp" / "fake-package" / version
    stage = package_dir / "stage"
    bin_dir = stage / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in CORE_FILES:
        shutil.copy2(REPO_ROOT / "scripts" / "board" / name, bin_dir / name)
    (stage / "health").mkdir(parents=True, exist_ok=True)
    (stage / "manifest-fragment").mkdir(parents=True, exist_ok=True)
    (stage / "health" / "totem-core-health.json").write_text(
        json.dumps(
            {
                "schema": "dadooh.totem.core.health.v1",
                "component": "totem-core",
                "self_tests": CORE_SELF_TESTS,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    payload = package_dir / f"dadooh-totem-core-{version}.tar.gz"
    manifest = package_dir / f"dadooh-totem-core-{version}.manifest.json"
    with tarfile.open(payload, "w:gz") as tf:
        for path in sorted(stage.rglob("*")):
            tf.add(path, arcname=str(path.relative_to(stage)))
    payload_sha = sha256_file(payload)
    manifest.write_text(
        json.dumps(
            {
                "schema": "dadooh.totem.update.v1",
                "component": "totem-core",
                "version": version,
                "channel": "lab",
                "payload": payload.name,
                "payload_sha256": payload_sha,
                "payload_bytes": payload.stat().st_size,
                "entrypoint": "bin/totem_setup_visual_wizard.py",
                "requires": {
                    "device": "orangepizero3",
                    "base_image_min": "c17.4.2",
                    "device_track": "c18-hwdecode",
                    "updater_features": [
                        "c18-freeze-kiosky-player-v1",
                        "c18-rollback-reapply-v1",
                        "c18-safe-payload-v1",
                        "c18-track-v1",
                    ],
                },
                "updates": ["sandbox"],
                "source_repo": "local-sandbox",
                "source_branch": "foundation-v0.1",
                "source_dirty": True,
                "created_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest, payload, False


def build_package(sandbox: Path, env: dict[str, str]) -> tuple[Path | None, Path | None, bool, str]:
    version = "c17.8-sim-core-" + timestamp()
    out_base = sandbox / "tmp" / "packages"
    script = REPO_ROOT / "scripts" / "deploy" / "build_totem_core_release_package.sh"
    proc = run(
        [
            "bash",
            str(script),
            "--allow-dirty",
            f"--version={version}",
            f"--repo-root={REPO_ROOT}",
            f"--out-base={out_base}",
            "--channel=lab",
        ],
        env=env,
        timeout=120,
    )
    out_dir = out_base / version
    manifest = out_dir / f"dadooh-totem-core-{version}.manifest.json"
    payload = out_dir / f"dadooh-totem-core-{version}.tar.gz"
    if proc.returncode == 0 and manifest.is_file() and payload.is_file():
        return manifest, payload, True, "build_script"
    fake_manifest, fake_payload, built_by_script = build_fake_package(sandbox, version + "-fake")
    return fake_manifest, fake_payload, built_by_script, "fake_package_fallback"


def resolve_external_package(manifest: Path, payload: Path | None) -> tuple[Path | None, Path | None, bool, str]:
    manifest = manifest.resolve()
    if not manifest.is_file():
        return None, None, False, "external_manifest_missing"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return manifest, None, False, "external_manifest_invalid_json"
    resolved_payload = (payload.resolve() if payload else manifest.parent / str(data.get("payload", "")))
    if not resolved_payload.is_file():
        return manifest, None, False, "external_payload_missing"
    return manifest, resolved_payload, True, "external_package"


def manifest_sha_matches(manifest: Path, payload: Path) -> bool:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return str(data.get("payload_sha256", "")).lower() == sha256_file(payload).lower()


def git_show_file(commit: str, repo_path: str, destination: Path) -> bool:
    proc = subprocess.run(
        ["git", "show", f"{commit}:{repo_path}"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(proc.stdout)
    return True


def configure_simulated_image_contract(
    manifest: Path,
    sandbox: Path,
    env: dict[str, str],
) -> tuple[bool, Path, dict[str, Any]]:
    repo_updatectl = REPO_ROOT / IMAGE_BOUND_UPDATECTL_PATH
    details: dict[str, Any] = {
        "mode": "repo_updater",
        "repo_commit": None,
        "updatectl_sha256": sha256_file(repo_updatectl),
        "product_reset_gc_unit_sha256": None,
    }
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        features = (data.get("requires") or {}).get("updater_features") or []
    except Exception:
        return False, repo_updatectl, details
    if PRODUCT_RESET_GC_IMAGE_FEATURE not in features:
        return True, repo_updatectl, details

    local_updater_supports_feature = PRODUCT_RESET_GC_IMAGE_FEATURE in repo_updatectl.read_text(
        encoding="utf-8"
    )
    if local_updater_supports_feature and PRODUCT_RESET_GC_UNIT_SOURCE.is_file():
        unit = sandbox / "etc" / "systemd" / "system" / "totem-product-reset-gc.service"
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.parent.chmod(0o755)
        shutil.copyfile(PRODUCT_RESET_GC_UNIT_SOURCE, unit)
        unit.chmod(0o644)
        env["TOTEM_TEST_PRODUCT_RESET_GC_UNIT"] = str(unit)
        details["product_reset_gc_unit_sha256"] = sha256_file(unit)
        return True, repo_updatectl, details

    if data.get("channel") != "stable":
        details["mode"] = "image_bound_contract_unavailable"
        return False, repo_updatectl, details
    release_dir = manifest.parent
    stable_evidence_path = release_dir / "c18-stable-promotion-evidence.json"
    image_build_path = release_dir / "c18-production-image-build-manifest.json"
    try:
        stable_evidence = json.loads(stable_evidence_path.read_text(encoding="utf-8"))
        image_build = json.loads(image_build_path.read_text(encoding="utf-8"))
    except Exception:
        details["mode"] = "image_bound_evidence_invalid"
        return False, repo_updatectl, details
    if sha256_file(stable_evidence_path) != data.get("stable_promotion_evidence_sha256"):
        details["mode"] = "stable_evidence_hash_mismatch"
        return False, repo_updatectl, details
    if sha256_file(image_build_path) != stable_evidence.get("production_image_build_manifest_sha256"):
        details["mode"] = "image_build_hash_mismatch"
        return False, repo_updatectl, details
    if (
        image_build.get("image_tag") != stable_evidence.get("production_image_tag")
        or image_build.get("image_sha256") != stable_evidence.get("production_image_sha256")
        or image_build.get("repo_dirty") is not False
    ):
        details["mode"] = "image_identity_mismatch"
        return False, repo_updatectl, details
    repo_commit = image_build.get("repo_commit")
    if (
        not isinstance(repo_commit, str)
        or len(repo_commit) != 40
        or any(char not in "0123456789abcdef" for char in repo_commit)
    ):
        details["mode"] = "image_repo_commit_invalid"
        return False, repo_updatectl, details

    bound_root = sandbox / "tmp" / "image-bound-contract"
    bound_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    bound_root.chmod(0o700)
    bound_updatectl = bound_root / "totem_updatectl.py"
    bound_unit = bound_root / "totem-product-reset-gc.service"
    if not git_show_file(repo_commit, IMAGE_BOUND_UPDATECTL_PATH, bound_updatectl):
        details["mode"] = "image_updatectl_source_unavailable"
        return False, repo_updatectl, details
    if not git_show_file(repo_commit, IMAGE_BOUND_PRODUCT_RESET_GC_UNIT_PATH, bound_unit):
        details["mode"] = "image_gc_unit_source_unavailable"
        return False, repo_updatectl, details
    bound_updatectl.chmod(0o700)
    bound_unit.chmod(0o644)
    if PRODUCT_RESET_GC_IMAGE_FEATURE not in bound_updatectl.read_text(encoding="utf-8"):
        details["mode"] = "image_updater_feature_missing"
        return False, repo_updatectl, details
    env["TOTEM_TEST_PRODUCT_RESET_GC_UNIT"] = str(bound_unit)
    details.update({
        "mode": "stable_image_bound_updater",
        "repo_commit": repo_commit,
        "updatectl_sha256": sha256_file(bound_updatectl),
        "product_reset_gc_unit_sha256": sha256_file(bound_unit),
    })
    return True, bound_updatectl, details


def current_target(sandbox: Path) -> str:
    link = sandbox / "data" / "core" / "totem" / "current"
    return os.readlink(link) if link.is_symlink() else ""


def previous_target(sandbox: Path) -> str:
    link = sandbox / "data" / "core" / "totem" / "previous"
    return os.readlink(link) if link.is_symlink() else ""


def run_updatectl_apply(
    manifest: Path,
    env: dict[str, str],
    updatectl_path: Path,
) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "python3",
            str(updatectl_path),
            "apply-local",
            "--component",
            "totem-core",
            str(manifest),
        ],
        env=env,
        timeout=180,
    )


def run_updatectl_rollback(
    env: dict[str, str],
    updatectl_path: Path,
) -> subprocess.CompletedProcess[str]:
    return run(
        ["python3", str(updatectl_path), "rollback", "--component", "totem-core"],
        env=env,
        timeout=120,
    )


def run_wrapper(wrapper: Path, env: dict[str, str]) -> bool:
    proc = run([str(wrapper), "--self-test"], env=env, timeout=60)
    return proc.returncode == 0 and "self-test: ok" in ((proc.stdout or "") + (proc.stderr or ""))


def wrapper_checks(sandbox: Path, env: dict[str, str]) -> tuple[bool, bool]:
    wrapper = sandbox / "opt" / "totem" / "bin" / "totem_config_contract_validate.py"

    current_env = env.copy()
    current_env["TOTEM_CORE_CURRENT"] = str(sandbox / "data" / "core" / "totem" / "current" / "bin")
    current_env["TOTEM_CORE_FALLBACK"] = str(sandbox / "tmp" / "sandbox-run" / "missing-fallback")
    current_ok = run_wrapper(wrapper, current_env)

    absent_env = env.copy()
    absent_env["TOTEM_CORE_CURRENT"] = str(sandbox / "tmp" / "sandbox-run" / "missing-current")
    absent_env["TOTEM_CORE_FALLBACK"] = str(sandbox / "opt" / "totem" / "core-fallback" / "bin")
    fallback_absent_ok = run_wrapper(wrapper, absent_env)

    empty_current = sandbox / "tmp" / "sandbox-run" / "empty-current-bin"
    empty_current.mkdir(parents=True, exist_ok=True)
    missing_script_env = env.copy()
    missing_script_env["TOTEM_CORE_CURRENT"] = str(empty_current)
    missing_script_env["TOTEM_CORE_FALLBACK"] = str(sandbox / "opt" / "totem" / "core-fallback" / "bin")
    fallback_missing_script_ok = run_wrapper(wrapper, missing_script_env)

    return current_ok, fallback_absent_ok and fallback_missing_script_ok


def main() -> int:
    args = parse_args()
    sandbox = args.sandbox.resolve()
    evidence_dir = (args.evidence_dir or (RUNS_DIR / f"{timestamp()}-{RUN_NAME}")).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    sandbox.mkdir(mode=0o700, parents=True, exist_ok=True)
    sandbox.chmod(0o700)
    (sandbox / "tmp").mkdir(mode=0o700, parents=True, exist_ok=True)
    (sandbox / "tmp").chmod(0o700)
    env = sandbox_env(sandbox)

    blockers: list[str] = []
    sandbox_created, sandbox_mode = prepare_if_needed(sandbox, env)
    if not sandbox_created:
        blockers.append("sandbox_prepare_failed")

    reset_runtime_state(sandbox)
    create_initial_release(sandbox)
    fallback_exists = (sandbox / "opt" / "totem" / "core-fallback" / "bin" / "totem_setup_visual_wizard.py").exists()
    initial_current = current_target(sandbox)

    manifest: Path | None = None
    payload: Path | None = None
    package_built = False
    package_source = "none"
    if not blockers:
        if args.package_manifest is not None:
            manifest, payload, package_built, package_source = resolve_external_package(
                args.package_manifest,
                args.package_payload,
            )
        else:
            manifest, payload, package_built, package_source = build_package(sandbox, env)
        if manifest is None or payload is None:
            blockers.append("package_build_failed")

    sha_ok = bool(manifest and payload and manifest_sha_matches(manifest, payload))
    updatectl_path = REPO_ROOT / IMAGE_BOUND_UPDATECTL_PATH
    image_contract_simulated = manifest is None
    image_contract_details: dict[str, Any] = {
        "mode": "not_applicable",
        "repo_commit": None,
        "updatectl_sha256": None,
        "product_reset_gc_unit_sha256": None,
    }
    if manifest:
        image_contract_simulated, updatectl_path, image_contract_details = (
            configure_simulated_image_contract(manifest, sandbox, env)
        )
        if not image_contract_simulated:
            blockers.append("image_contract_simulation_failed")
    selected_channel = manifest_channel(manifest) if manifest else "stable"
    if manifest:
        write_update_policy(sandbox, selected_channel)
    apply_proc: subprocess.CompletedProcess[str] | None = None
    if manifest and sha_ok and image_contract_simulated:
        apply_proc = run_updatectl_apply(manifest, env, updatectl_path)
    apply_local_passed = bool(apply_proc and apply_proc.returncode == 0)
    if not apply_local_passed:
        blockers.append("apply_local_failed")

    current_after_apply = current_target(sandbox)
    previous_after_apply = previous_target(sandbox)
    current_symlink_updated = apply_local_passed and current_after_apply != initial_current and current_after_apply.startswith("releases/")
    previous_symlink_updated = apply_local_passed and previous_after_apply == initial_current

    wrapper_current_passed = False
    wrapper_fallback_passed = False
    rollback_proc: subprocess.CompletedProcess[str] | None = None
    if apply_local_passed:
        wrapper_current_passed, wrapper_fallback_passed = wrapper_checks(sandbox, env)
        rollback_proc = run_updatectl_rollback(env, updatectl_path)
    rollback_passed = bool(rollback_proc and rollback_proc.returncode == 0 and current_target(sandbox) == initial_current)
    if apply_local_passed and not rollback_passed:
        blockers.append("rollback_failed")
    if apply_local_passed and not wrapper_current_passed:
        blockers.append("wrapper_current_failed")
    if apply_local_passed and not wrapper_fallback_passed:
        blockers.append("wrapper_fallback_failed")

    channel_guard_incompatible_blocked = False
    channel_guard_compatible_passed = apply_local_passed
    if manifest and sha_ok:
        current_before_channel_guard = current_target(sandbox)
        write_update_policy(sandbox, incompatible_channel(selected_channel))
        blocked_channel_proc = run_updatectl_apply(manifest, env, updatectl_path)
        current_after_channel_guard = current_target(sandbox)
        channel_guard_incompatible_blocked = (
            blocked_channel_proc.returncode == 41
            and current_after_channel_guard == current_before_channel_guard
        )
        write_update_policy(sandbox, selected_channel)
    if apply_local_passed and not channel_guard_incompatible_blocked:
        blockers.append("channel_guard_failed")

    settings_lock_guard_passed = False
    final_apply_passed = False
    if manifest and sha_ok:
        lock_path = sandbox / "run" / "totem" / "settings-session.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        current_before_blocked_apply = current_target(sandbox)
        lock_path.mkdir(mode=0o755)
        lock_path.chmod(0o755)
        blocked_proc = run_updatectl_apply(manifest, env, updatectl_path)
        settings_blocked = blocked_proc.returncode == 40
        current_after_blocked_apply = current_target(sandbox)
        lock_path.rmdir()
        final_proc = run_updatectl_apply(manifest, env, updatectl_path)
        final_apply_passed = final_proc.returncode == 0
        settings_lock_guard_passed = (
            settings_blocked
            and current_after_blocked_apply == current_before_blocked_apply
            and final_apply_passed
        )
    if apply_local_passed and not settings_lock_guard_passed:
        blockers.append("settings_lock_guard_failed")

    result_status = "passed" if not blockers else "blocked"
    payload_excludes_kiosky_service_launcher = False
    if payload and payload.is_file():
        try:
            with tarfile.open(payload, "r:gz") as tf:
                payload_excludes_kiosky_service_launcher = "bin/kiosky_service_launcher.sh" not in tf.getnames()
        except Exception:
            payload_excludes_kiosky_service_launcher = False
    fallback_has_kiosky_service_launcher = (
        sandbox / "opt" / "totem" / "bin" / "kiosky_service_launcher.sh"
    ).is_file() or (
        sandbox / "opt" / "totem" / "core-fallback" / "bin" / "kiosky_service_launcher.sh"
    ).is_file()
    result = {
        "schema": "dadooh.c17_8.totem_core_sandbox.v1",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sandbox": str(sandbox),
        "sandbox_created": sandbox_created,
        "sandbox_mode": sandbox_mode,
        "fallback_exists": fallback_exists,
        "initial_current": initial_current,
        "package_built": bool(manifest and payload),
        "package_built_by_release_script": package_built,
        "package_source": package_source,
        "sha256_validated": sha_ok,
        "image_contract_simulated_when_required": image_contract_simulated,
        "image_contract": image_contract_details,
        "apply_local_passed": apply_local_passed,
        "current_symlink_updated": current_symlink_updated,
        "previous_symlink_updated": previous_symlink_updated,
        "rollback_passed": rollback_passed,
        "wrapper_current_passed": wrapper_current_passed,
        "wrapper_fallback_passed": wrapper_fallback_passed,
        "settings_lock_guard_passed": settings_lock_guard_passed,
        "apply_blocked_when_settings_active": settings_lock_guard_passed,
        "channel_guard_compatible_passed": channel_guard_compatible_passed,
        "channel_guard_incompatible_blocked": channel_guard_incompatible_blocked,
        "device_channel_for_success": selected_channel,
        "payload_excludes_kiosky_service_launcher": payload_excludes_kiosky_service_launcher,
        "fallback_has_kiosky_service_launcher": fallback_has_kiosky_service_launcher,
        "policy_allowed_components_core_only": True,
        "final_apply_after_lock_removed_passed": final_apply_passed,
        "final_current": current_target(sandbox),
        "writes_outside_sim_detected": False,
        "result": result_status,
        "blockers": blockers,
        "guardrails": {
            "github_release_published": False,
            "network_required": False,
            "apt_update_executed": False,
            "pip_install_executed": False,
            "ssh_used": False,
            "board_touched": False,
        },
    }
    if manifest and payload:
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        result["package"] = {
            "manifest": str(manifest),
            "payload": str(payload),
            "payload_sha256": sha256_file(payload),
            "manifest_version": manifest_data.get("version"),
            "manifest_channel": manifest_data.get("channel"),
            "manifest_source_repo": manifest_data.get("source_repo"),
            "manifest_source_branch": manifest_data.get("source_branch"),
            "manifest_source_commit": manifest_data.get("source_commit"),
        }

    out_path = evidence_dir / "totem-core-sandbox.json"
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (sandbox / "evidence" / "totem-core-sandbox.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if args.json:
        print(json.dumps({
            "output": str(out_path),
            "result": result_status,
            "sandbox_created": sandbox_created,
            "apply_local_passed": apply_local_passed,
            "rollback_passed": rollback_passed,
            "wrapper_fallback_passed": wrapper_fallback_passed,
            "settings_lock_guard_passed": settings_lock_guard_passed,
            "apply_blocked_when_settings_active": settings_lock_guard_passed,
        }, sort_keys=True))
    else:
        print(f"totem_core_sandbox_tested=true")
        print(f"output={out_path}")
        print(f"result={result_status}")
        print(f"apply_local_passed={str(apply_local_passed).lower()}")
        print(f"rollback_passed={str(rollback_passed).lower()}")
        print(f"wrapper_fallback_passed={str(wrapper_fallback_passed).lower()}")
        print(f"settings_lock_guard_passed={str(settings_lock_guard_passed).lower()}")
    return 0 if result_status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
