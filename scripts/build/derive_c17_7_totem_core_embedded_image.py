#!/usr/bin/env python3
"""Derive the C17.7 image with C17.6 totem-core embedded.

This offline derivation copies the clean-card validated C17.4.2 image, applies
the current appliance layer, embeds the C17.6 totem-core release as
/data/core/totem/current, installs /opt fallback scripts, and replaces the
core entrypoints in /opt/totem/bin with the C17.5 wrappers.

It does not invoke Armbian Build, apt, pip, kernel tooling, or a board, and it
never reads or prints private config/seed contents.

C18 update-contract note: kiosky_service_launcher.sh and totem-kiosky-launcher.sh
are player-runtime. Keep them fixed in /opt/totem/bin and out of the
totem-core release/fallback payload.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import derive_c15_2_1_homolog_image as base
import derive_c17_1_homolog_ux_gated_image as c17_1
import derive_c17_4_firstboot_visual_f10_image as c17_4


DEFAULT_BASE_IMAGE = Path(
    "/home/builder/totem-os/armbian-build-v25.11/output/images/"
    "Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
    "6.12.58-c12-ro-lab-c17-4-2-settings-restore-clean_minimal.img"
)
DEFAULT_OUTPUT_IMAGE = Path(
    "/home/builder/totem-os/armbian-build-v25.11/output/images/"
    "Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
    "6.12.58-c12-ro-lab-c17-7-totem-core-embedded_minimal.img"
)
DEFAULT_TAG = "c17-7-totem-core-embedded"
DEFAULT_VERSION = "c17.7"
EXPECTED_IMAGE_TOKEN = "c17-7"
MARKER_PATH = "/etc/dadooh/c17-7-totem-core-embedded-image"
TOTEM_CORE_VERSION = "c17.6-environment-input-20260514T211247Z"
TOTEM_CORE_RELEASE_TAG = "totem-core-c17.6-environment-input-20260514T211247Z"
TOTEM_CORE_PAYLOAD_SHA256 = "e6b643429709ba9f747d86bb113abc35ab9645da23216eb81455dbc2f5a9acb9"

CORE_FILES = [
    "totem_setup_visual_wizard.py",
    "totem_wifi_nm_adapter.py",
    "totem_visual_splash.py",
    "totem_status_aggregate.py",
    "totem_status_render_preview.py",
    "totem_config_contract_validate.py",
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
]

IMAGE_FIXED_PLAYER_FILES = [
    "kiosky_service_launcher.sh",
    "totem-kiosky-launcher.sh",
]


def repo_head(path: Path) -> str:
    return (base.run(["git", "-C", str(path), "rev-parse", "HEAD"]).stdout or "").strip()


def repo_dirty(path: Path) -> bool:
    return bool((base.run(["git", "-C", str(path), "status", "--short"]).stdout or "").strip())


def write_file_commands(source: Path, target: str, mode_text: str = "0755") -> list[str]:
    commands: list[str] = []
    for directory in base.parent_dirs(target):
        commands.append(f"mkdir {directory}")
    commands.extend(
        [
            f"rm {target}",
            f"write {source} {target}",
            f"set_inode_field {target} mode {base.mode_with_type(mode_text)}",
            f"set_inode_field {target} uid 0",
            f"set_inode_field {target} gid 0",
        ]
    )
    return commands


def marker_text(*, image_tag: str, image_version: str, repo_root: Path, kiosky_dir: Path) -> str:
    return "\n".join(
        [
            f"image_tag={image_tag}",
            f"image_version={image_version}",
            "artifact_private=true",
            "final_image=false",
            "homologation_shipping_image=true",
            "not_for_production=true",
            "not_for_distribution=true",
            "base_image=c17.4.2-settings-restore-clean",
            "kernel_reused=true",
            "kernel_rebuild_executed=false",
            "c17_4_2_clean_board_validation_passed=true",
            "c17_5_totem_core_remote_update_mvp_passed=true",
            "c17_6_environment_input_update_passed=true",
            "c17_6_environment_input_embedded=true",
            "totem_core_component_defined=true",
            "totem_core_current_embedded=true",
            f"totem_core_current_version={TOTEM_CORE_VERSION}",
            f"totem_core_release_tag={TOTEM_CORE_RELEASE_TAG}",
            f"totem_core_payload_sha256={TOTEM_CORE_PAYLOAD_SHA256}",
            "totem_core_wrappers_created=true",
            "totem_core_fallback_available=true",
            "splash_service_uses_totem_core_wrapper=true",
            "qa_artifacts_not_installed=true",
            "c12_readonly_blocked=true",
            "c12_4_blocked=true",
            "ready_for_clean_card_validation=true",
            "ready_for_batch_flash=false",
            "ready_for_dispatch=false",
            "ready_for_c18_player_audit=false",
            f"orange_pi_totem_commit={repo_head(repo_root)}",
            f"kiosky_player_commit={repo_head(kiosky_dir)}",
            "secrets_published=false",
            "",
        ]
    )


def write_totem_core_embed(rootfs: Path, work_dir: Path, repo_root: Path) -> dict[str, Any]:
    manifest_path = repo_root / "scripts/board/totem_appliance_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    embed = manifest.get("totem_core_image_embed") or {}
    core_files = list(embed.get("core_files") or CORE_FILES)
    current_target = str((embed.get("layout") or {}).get("current_target") or f"releases/{TOTEM_CORE_VERSION}")
    release_root = f"/data/core/totem/releases/{TOTEM_CORE_VERSION}"
    release_bin = f"{release_root}/bin"
    fallback_bin = "/opt/totem/core-fallback/bin"
    wrappers_bin = "/opt/totem/bin"
    wrapper_py = repo_root / "scripts/board/totem_core_exec.py"
    wrapper_sh = repo_root / "scripts/board/totem_core_exec.sh"

    commands: list[str] = []
    for directory in (
        "/data/core",
        "/data/core/totem",
        "/data/core/totem/releases",
        release_root,
        release_bin,
        f"{release_root}/health",
        f"{release_root}/manifest-fragment",
        "/opt/totem/core-fallback",
        fallback_bin,
        wrappers_bin,
    ):
        commands.append(f"mkdir {directory}")

    commands.extend(write_file_commands(wrapper_py, f"{wrappers_bin}/totem_core_exec.py"))
    commands.extend(write_file_commands(wrapper_sh, f"{wrappers_bin}/totem_core_exec.sh"))
    for core_file in core_files:
        if "/" in core_file or core_file.startswith("."):
            raise RuntimeError(f"unsafe_totem_core_file:{core_file}")
        source = repo_root / "scripts/board" / core_file
        if not source.is_file():
            raise RuntimeError(f"missing_totem_core_file:{core_file}")
        commands.extend(write_file_commands(source, f"{fallback_bin}/{core_file}"))
        commands.extend(write_file_commands(source, f"{release_bin}/{core_file}"))
        if core_file.endswith(".py"):
            commands.extend(write_file_commands(wrapper_py, f"{wrappers_bin}/{core_file}"))
        elif core_file.endswith(".sh"):
            commands.extend(write_file_commands(wrapper_sh, f"{wrappers_bin}/{core_file}"))
        else:
            raise RuntimeError(f"unknown_totem_core_wrapper_type:{core_file}")
    for player_file in IMAGE_FIXED_PLAYER_FILES:
        if "/" in player_file or player_file.startswith("."):
            raise RuntimeError(f"unsafe_fixed_player_file:{player_file}")
        source = repo_root / "scripts/board" / player_file
        if not source.is_file():
            raise RuntimeError(f"missing_fixed_player_file:{player_file}")
        commands.extend(write_file_commands(source, f"{wrappers_bin}/{player_file}"))

    health_file = work_dir / "totem-core-health.json"
    health_file.write_text(
        json.dumps(
            {
                "schema": "dadooh.totem.core.health.v1",
                "component": "totem-core",
                "version": TOTEM_CORE_VERSION,
                "embedded_in_image": True,
                "self_tests": [
                    "python3 bin/totem_setup_visual_wizard.py --self-test",
                    "python3 bin/totem_wifi_nm_adapter.py --self-test",
                    "python3 bin/totem_visual_splash.py --self-test",
                    "python3 bin/totem_config_contract_validate.py --self-test",
                    "bash -n bin/totem_open_settings_session.sh",
                    "bash -n bin/totem_visual_tty_guard.sh",
                    "bash -n bin/totem_firstboot_gate.sh",
                    "bash -n bin/totem_status_renderer.sh",
                    "restore-order-static-check",
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    fragment_file = work_dir / "totem-core-fragment.json"
    fragment_file.write_text(
        json.dumps(
            {
                "component": "totem-core",
                "layout": "/data/core/totem",
                "fallback": fallback_bin,
                "wrappers": wrappers_bin,
                "systemd_units_included": False,
                "updater_self_update": False,
                "embedded_in_image": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    state_file = work_dir / "totem-core-state.json"
    state_file.write_text(
        json.dumps(
            {
                "schema": "dadooh.totem.update.state.v1",
                "component": "totem-core",
                "current": {
                    "version": TOTEM_CORE_VERSION,
                    "path": current_target,
                    "source": "image_embed",
                    "source_repo": "dadoohai/orange_pi_totem",
                    "source_branch": "foundation-v0.1",
                    "source_commit": repo_head(repo_root),
                    "payload_sha256": TOTEM_CORE_PAYLOAD_SHA256,
                },
                "previous": None,
                "last_operation": {
                    "type": "image_embed",
                    "status": "ok",
                    "version": TOTEM_CORE_VERSION,
                },
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    commands.extend(write_file_commands(health_file, f"{release_root}/health/totem-core-health.json", "0644"))
    commands.extend(write_file_commands(fragment_file, f"{release_root}/manifest-fragment/totem-core.json", "0644"))
    commands.extend(write_file_commands(state_file, "/data/core/totem/state.json", "0644"))
    commands.extend(
        [
            "rm /data/core/totem/current",
            f"symlink /data/core/totem/current {current_target}",
        ]
    )

    output = base.debugfs_batch(rootfs, commands, work_dir)
    return {
        "totem_core_current_version": TOTEM_CORE_VERSION,
        "totem_core_files_embedded": len(core_files),
        "image_fixed_player_files_embedded": len(IMAGE_FIXED_PLAYER_FILES),
        "totem_core_embed_debugfs_output_lines": len(output.splitlines()),
    }


def write_marker(
    rootfs: Path,
    work_dir: Path,
    *,
    image_tag: str,
    image_version: str,
    repo_root: Path,
    kiosky_dir: Path,
) -> dict[str, Any]:
    marker_file = work_dir / "c17-7-marker"
    marker_file.write_text(
        marker_text(
            image_tag=image_tag,
            image_version=image_version,
            repo_root=repo_root,
            kiosky_dir=kiosky_dir,
        ),
        encoding="utf-8",
    )
    commands = write_file_commands(marker_file, MARKER_PATH, "0644")
    output = base.debugfs_batch(rootfs, commands, work_dir)
    return {"c17_7_marker_written": True, "c17_7_marker_debugfs_output_lines": len(output.splitlines())}


def is_file(rootfs: Path, path: str) -> bool:
    info = base.stat_file(rootfs, path)
    return bool(info.get("present") and info.get("type") in {"regular", "file"})


def executable(rootfs: Path, path: str) -> bool:
    info = base.stat_file(rootfs, path)
    return bool(info.get("present") and (int(info.get("mode", 0)) & 0o111))


def is_symlink(rootfs: Path, path: str) -> bool:
    info = base.stat_file(rootfs, path)
    return bool(info.get("present") and info.get("type") == "symlink")


def manifest_on_builder_ok(repo_root: Path) -> bool:
    manifest = json.loads((repo_root / "scripts/board/totem_appliance_manifest.json").read_text(encoding="utf-8"))
    release = manifest.get("homologation_release") or {}
    embed = manifest.get("totem_core_image_embed") or {}
    return (
        release.get("image_tag") == DEFAULT_TAG
        and release.get("image_version") == DEFAULT_VERSION
        and release.get("c17_6_environment_input_embedded") is True
        and release.get("totem_core_current_embedded") is True
        and release.get("clean_board_validation_pending") is True
        and release.get("ready_for_batch_flash") is False
        and release.get("ready_for_dispatch") is False
        and release.get("ready_for_c18_player_audit") is False
        and embed.get("enabled") is True
        and embed.get("current_version") == TOTEM_CORE_VERSION
        and embed.get("fallback_available_without_data_current") is True
        and embed.get("splash_service_uses_totem_core_wrapper") is True
    )


def restore_order_checks(session: str) -> dict[str, bool]:
    return {
        "release_session_lock_for_restore_present": "release_session_lock_for_restore" in session,
        "session_lock_released_before_restore_logged": "session_lock_released_before_restore" in session,
        "restore_has_lock_guard": '[ -e "$LOCK_DIR" ]' in session and "restore_service_blocked_session_lock_present" in session,
        "write_final_status_lock_wait_guard": "write_final_status_skip_wait_session_lock_present" in session,
    }


def validate_c17_7(rootfs: Path, image_name: str, *, repo_root: Path) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    marker = base.cat_file(rootfs, MARKER_PATH) or ""
    wrapper = base.cat_file(rootfs, "/opt/totem/bin/totem_setup_visual_wizard.py") or ""
    splash_service = base.cat_file(rootfs, "/etc/systemd/system/dadooh-visual-splash.service") or ""
    wizard_current = base.cat_file(
        rootfs, f"/data/core/totem/releases/{TOTEM_CORE_VERSION}/bin/totem_setup_visual_wizard.py"
    ) or ""
    wizard_fallback = base.cat_file(rootfs, "/opt/totem/core-fallback/bin/totem_setup_visual_wizard.py") or ""
    session_current = base.cat_file(
        rootfs, f"/data/core/totem/releases/{TOTEM_CORE_VERSION}/bin/totem_open_settings_session.sh"
    ) or ""
    updatectl = base.cat_file(rootfs, "/opt/totem/bin/totem-updatectl") or ""
    player_launcher = base.cat_file(rootfs, "/opt/totem/bin/kiosky_service_launcher.sh") or ""
    checks["image_name_contains_c17_7"] = EXPECTED_IMAGE_TOKEN in image_name
    checks["c17_7_marker_present"] = is_file(rootfs, MARKER_PATH)
    checks["c17_7_marker_records_totem_core"] = all(
        token in marker
        for token in (
            "c17_6_environment_input_embedded=true",
            "totem_core_current_embedded=true",
            f"totem_core_current_version={TOTEM_CORE_VERSION}",
            "splash_service_uses_totem_core_wrapper=true",
        )
    )
    checks["manifest_on_builder_ok"] = manifest_on_builder_ok(repo_root)
    checks["totem_core_current_symlink_present"] = is_symlink(rootfs, "/data/core/totem/current")
    checks["totem_core_state_present"] = is_file(rootfs, "/data/core/totem/state.json")
    checks["totem_core_release_health_present"] = is_file(
        rootfs, f"/data/core/totem/releases/{TOTEM_CORE_VERSION}/health/totem-core-health.json"
    )
    checks["totem_core_release_fragment_present"] = is_file(
        rootfs, f"/data/core/totem/releases/{TOTEM_CORE_VERSION}/manifest-fragment/totem-core.json"
    )
    checks["wizard_wrapper_installed"] = "TOTEM_CORE_EXEC_WRAPPER" in wrapper
    checks["wizard_current_release_installed"] = "text_field_apply_edit_key" in wizard_current
    checks["wizard_fallback_installed"] = "text_field_apply_edit_key" in wizard_fallback
    checks["environment_uuid_validation_embedded"] = all(
        token in wizard_current
        for token in (
            "uuid.UUID",
            "derive_environment_endpoint",
            "response_has_content",
            "validation_unavailable",
        )
    )
    checks["settings_restore_order_current_ok"] = all(restore_order_checks(session_current).values())
    checks["splash_service_uses_wrapper"] = "/opt/totem/bin/totem_visual_splash.py boot" in splash_service
    checks["totem_updatectl_multi_component"] = "totem-core" in updatectl and "_totem_core_health_check" in updatectl
    checks["image_fixed_player_launcher_present"] = executable(rootfs, "/opt/totem/bin/kiosky_service_launcher.sh")
    checks["image_fixed_player_launcher_not_totem_core_wrapper"] = "TOTEM_CORE_EXEC_WRAPPER" not in player_launcher
    checks["totem_core_release_excludes_player_launcher"] = not is_file(
        rootfs, f"/data/core/totem/releases/{TOTEM_CORE_VERSION}/bin/kiosky_service_launcher.sh"
    )
    checks["pull_update_timer_enabled"] = is_symlink(
        rootfs, "/etc/systemd/system/timers.target.wants/totem-update-agent.timer"
    )
    checks["firstboot_gate_enabled"] = is_symlink(
        rootfs, "/etc/systemd/system/multi-user.target.wants/totem-firstboot-gate.service"
    )
    seed_info = base.stat_file(rootfs, "/data/state/totem-settings/private-values.seed.json")
    checks["seed_present"] = bool(seed_info.get("present"))
    checks["seed_permissions_ok"] = seed_info.get("mode") == 0o600 and seed_info.get("uid") == 0 and seed_info.get("gid") == 0
    checks["no_real_config_embedded"] = not base.stat_file(rootfs, "/data/config/config.json").get("present", False)
    checks["qa_artifacts_not_installed"] = not base.stat_file(rootfs, "/docs/evidence").get("present", False)
    checks["kiosky_player_installed"] = is_file(rootfs, "/opt/totem/kiosky-player/kiosk.py")
    checks["c17_4_2_marker_inherited"] = is_file(rootfs, "/etc/dadooh/c17-4-2-settings-restore-clean-image")
    return {"checks": checks, "ok": all(checks.values())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-image", type=Path, default=DEFAULT_BASE_IMAGE)
    parser.add_argument("--output-image", type=Path, default=DEFAULT_OUTPUT_IMAGE)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--kiosky-player-dir", type=Path, default=Path("/home/builder/kiosky-player"))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--image-tag", default=DEFAULT_TAG)
    parser.add_argument("--image-version", default=DEFAULT_VERSION)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output image.")
    args = parser.parse_args()

    if not shutil.which("debugfs"):
        raise SystemExit("debugfs_missing")
    if not args.base_image.is_file():
        raise SystemExit("base_image_missing")
    if not (args.kiosky_player_dir / ".git").is_dir():
        raise SystemExit("kiosky_player_repo_missing")
    if repo_dirty(args.kiosky_player_dir):
        raise SystemExit("kiosky_player_tree_dirty")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(args.out_dir, 0o700)
    if args.output_image.exists() and not args.force:
        raise SystemExit("output_image_already_exists")
    if EXPECTED_IMAGE_TOKEN not in args.output_image.name:
        raise SystemExit("output_image_name_missing_c17_7")

    summary: dict[str, Any] = {
        "image_tag": args.image_tag,
        "image_version": args.image_version,
        "base_image": str(args.base_image),
        "output_image": str(args.output_image),
        "kernel_reused": True,
        "kernel_rebuild_executed": False,
        "artifact_private": True,
        "final_image": False,
        "homologation_shipping_image": True,
        "not_for_production": True,
        "not_for_distribution": True,
        "seed_content_published": False,
        "c17_6_environment_input_embedded": True,
        "totem_core_current_embedded": True,
        "totem_core_current_version": TOTEM_CORE_VERSION,
        "totem_core_payload_sha256": TOTEM_CORE_PAYLOAD_SHA256,
        "c12_readonly_blocked": True,
        "c12_4_blocked": True,
        "kiosky_player_commit": repo_head(args.kiosky_player_dir),
        "orange_pi_totem_commit": repo_head(args.repo_root),
    }

    shutil.copy2(args.base_image, args.output_image)
    offset, length = base.parse_mbr_linux_partition(args.output_image)
    summary["rootfs_offset"] = offset
    summary["rootfs_bytes"] = length

    with tempfile.TemporaryDirectory(prefix="c17-7-image-") as td:
        work_dir = Path(td)
        rootfs = work_dir / "rootfs.ext4"
        base.copy_range(args.output_image, rootfs, offset=offset, length=length)
        summary.update(
            base.apply_appliance_layer(
                rootfs,
                args.repo_root.resolve(),
                work_dir,
                image_tag=args.image_tag,
                image_version=args.image_version,
            )
        )
        summary.update(c17_1.write_kiosky_player(rootfs, work_dir, args.kiosky_player_dir.resolve()))
        summary.update(
            c17_4.write_appliance_marker(
                rootfs,
                work_dir,
                image_tag=args.image_tag,
                image_version=args.image_version,
                repo_root=args.repo_root.resolve(),
                kiosky_dir=args.kiosky_player_dir.resolve(),
            )
        )
        summary.update(write_totem_core_embed(rootfs, work_dir, args.repo_root.resolve()))
        summary.update(
            write_marker(
                rootfs,
                work_dir,
                image_tag=args.image_tag,
                image_version=args.image_version,
                repo_root=args.repo_root.resolve(),
                kiosky_dir=args.kiosky_player_dir.resolve(),
            )
        )
        e2fsck = base.run(["e2fsck", "-fy", str(rootfs)])
        summary["e2fsck_exit"] = e2fsck.returncode
        summary["e2fsck_ok"] = e2fsck.returncode in {0, 1}
        validation = validate_c17_7(rootfs, args.output_image.name, repo_root=args.repo_root.resolve())
        summary["offline_validation"] = validation
        if not validation["ok"]:
            out_json = args.out_dir / "c17-7-offline-validation.json"
            out_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 1
        base.write_range(args.output_image, rootfs, offset=offset)

    digest = base.file_sha256(args.output_image)
    checksum_file = args.output_image.with_suffix(args.output_image.suffix + ".sha256")
    checksum_file.write_text(f"{digest}  {args.output_image.name}\n", encoding="utf-8")
    summary["image_sha256"] = digest
    summary["image_sha256_file"] = str(checksum_file)
    summary["image_bytes"] = args.output_image.stat().st_size
    summary["ok"] = True

    out_json = args.out_dir / "c17-7-offline-validation.json"
    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
