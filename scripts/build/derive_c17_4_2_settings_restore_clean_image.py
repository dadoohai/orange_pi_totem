#!/usr/bin/env python3
"""Derive the C17.4.2 settings-restore clean homologation image.

This is an offline derivation path. It copies the already validated private
C14.2.1 homologation image, applies the current manifest-managed appliance
layer, embeds the current pinned kiosky-player tree, and validates the rootfs
with debugfs. It does not invoke Armbian Build, apt, pip, kernel tooling, or a
board.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import derive_c15_2_1_homolog_image as base
import derive_c17_1_homolog_ux_gated_image as c17_1
import derive_c17_4_firstboot_visual_f10_image as c17_4


DEFAULT_BASE_IMAGE = base.DEFAULT_BASE_IMAGE
DEFAULT_OUTPUT_IMAGE = Path(
    "/home/builder/totem-os/armbian-build-v25.11/output/images/"
    "Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
    "6.12.58-c12-ro-lab-c17-4-2-settings-restore-clean_minimal.img"
)
DEFAULT_TAG = "c17-4-2-settings-restore-clean"
DEFAULT_VERSION = "c17.4.2"
EXPECTED_IMAGE_TOKEN = "c17-4-2"
VISUAL_SYSTEM_VERSION = c17_4.VISUAL_SYSTEM_VERSION
OWNERSHIP_VERSION = c17_4.OWNERSHIP_VERSION
RESTORE_ORDER_VERSION = "c17.4.1-settings-lock-restore.v1"
MARKER_PATH = "/etc/dadooh/c17-4-2-settings-restore-clean-image"


def repo_head(path: Path) -> str:
    return (base.run(["git", "-C", str(path), "rev-parse", "HEAD"]).stdout or "").strip()


def repo_dirty(path: Path) -> bool:
    return bool((base.run(["git", "-C", str(path), "status", "--short"]).stdout or "").strip())


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
            "base_image=c14.2.1-shipping-homolog",
            "kernel_reused=true",
            "kernel_rebuild_executed=false",
            "c14_updater_embedded=true",
            "c15_fixes_embedded=true",
            "c15_3_2_startup_feedback_embedded=true",
            "c16_2_harness_present_on_builder=true",
            "c17_2_visual_polish_embedded=true",
            "c17_4_firstboot_visual_f10_fix_embedded=true",
            "c17_4_1_settings_lock_restore_fix_embedded=true",
            f"visual_surface_ownership_version={OWNERSHIP_VERSION}",
            f"settings_restore_order_version={RESTORE_ORDER_VERSION}",
            "release_session_lock_before_restore=true",
            "restore_service_refuses_lock_present=true",
            "write_final_status_lock_wait_guard=true",
            "first_boot_black_screen_fix_expected=true",
            "f10_ready_before_config_pending=true",
            "status_renderer_respects_session_lock=true",
            f"visual_design_system_version={VISUAL_SYSTEM_VERSION}",
            "qa_artifacts_not_installed=true",
            "new_fonts_required=false",
            "new_assets_required=false",
            "new_dependencies_required=false",
            "c12_readonly_blocked=true",
            "c12_4_blocked=true",
            f"orange_pi_totem_commit={repo_head(repo_root)}",
            f"kiosky_player_commit={repo_head(kiosky_dir)}",
            "secrets_published=false",
            "",
        ]
    )


def write_appliance_marker(
    rootfs: Path,
    work_dir: Path,
    *,
    image_tag: str,
    image_version: str,
    repo_root: Path,
    kiosky_dir: Path,
) -> dict[str, Any]:
    marker_file = work_dir / "c17-4-2-marker"
    marker_file.write_text(
        marker_text(
            image_tag=image_tag,
            image_version=image_version,
            repo_root=repo_root,
            kiosky_dir=kiosky_dir,
        ),
        encoding="utf-8",
    )
    commands = []
    for directory in base.parent_dirs(MARKER_PATH):
        commands.append(f"mkdir {directory}")
    commands.extend(
        [
            f"rm {MARKER_PATH}",
            f"write {marker_file} {MARKER_PATH}",
            f"set_inode_field {MARKER_PATH} mode {base.mode_with_type('0644')}",
            f"set_inode_field {MARKER_PATH} uid 0",
            f"set_inode_field {MARKER_PATH} gid 0",
        ]
    )
    output = base.debugfs_batch(rootfs, commands, work_dir)
    return {
        "c17_4_2_marker_written": True,
        "c17_4_2_marker_debugfs_output_lines": len(output.splitlines()),
    }


def section(text: str, start: str, end: str) -> str:
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[start_index:end_index]


def restore_order_checks(session: str) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    try:
        restore = section(session, "restore_service() {", "\n}\n\nkill_visual_if_running()")
        release = section(session, "release_session_lock_for_restore() {", "\n}\n\nwrite_final_status()")
        final_status = section(session, "write_final_status() {", "\nimport json\n")
        normal = section(session, 'c1523_phase "session_cleanup_start rc=0"', 'c1523_phase "session_done rc=0"')
    except ValueError:
        return {
            "restore_has_lock_guard": False,
            "restore_has_nonblocking_start": False,
            "restore_start_is_bounded": False,
            "restore_guard_before_start": False,
            "release_removes_request": False,
            "release_removes_lock": False,
            "release_logs_before_restore": False,
            "normal_releases_before_restore": False,
            "normal_restore_inside_release_success_branch": False,
            "normal_waits_after_restore": False,
            "normal_wait_inside_release_success_branch": False,
            "normal_cleanup_still_idempotent": False,
            "final_status_wait_guarded_by_lock_absence": False,
        }

    nonblocking_start = "systemctl start --no-block kiosky-player.service"
    bounded_start = f"/usr/bin/timeout -k 1s 5s {nonblocking_start}"
    checks["restore_has_lock_guard"] = '[ -e "$LOCK_DIR" ]' in restore
    checks["restore_has_nonblocking_start"] = nonblocking_start in restore
    checks["restore_start_is_bounded"] = bounded_start in restore
    checks["restore_guard_before_start"] = (
        checks["restore_has_lock_guard"]
        and nonblocking_start in restore
        and restore.index('[ -e "$LOCK_DIR" ]') < restore.index(nonblocking_start)
    )
    checks["release_removes_request"] = "cleanup_trigger_request" in release
    checks["release_removes_lock"] = "cleanup_session_lock" in release
    checks["release_logs_before_restore"] = "session_lock_released_before_restore" in release
    checks["normal_releases_before_restore"] = (
        "release_session_lock_for_restore" in normal
        and "restore_service" in normal
        and normal.index("release_session_lock_for_restore") < normal.index("restore_service")
    )
    checks["normal_restore_inside_release_success_branch"] = (
        re.search(r"if release_session_lock_for_restore; then\s+restore_service", normal) is not None
    )
    checks["normal_waits_after_restore"] = (
        "restore_service" in normal
        and "wait_player_running" in normal
        and normal.index("restore_service") < normal.index("wait_player_running")
    )
    checks["normal_wait_inside_release_success_branch"] = (
        re.search(r"restore_service\s+\|\|\s+true\s+wait_player_running", normal) is not None
    )
    checks["normal_cleanup_still_idempotent"] = (
        "restore_service" in normal
        and "cleanup_session_lock" in normal
        and normal.rindex("cleanup_session_lock") > normal.index("restore_service")
    )
    checks["final_status_wait_guarded_by_lock_absence"] = (
        '[ -e "$LOCK_DIR" ]' in final_status
        and "wait_player_running" in final_status
        and "write_final_status_skip_wait_session_lock_present" in final_status
    )
    return checks


def settings_restore_manifest_ok(repo_root: Path) -> bool:
    manifest_path = repo_root / "scripts/board/totem_appliance_manifest.json"
    if not manifest_path.is_file():
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    release = manifest.get("homologation_release") or {}
    ownership = manifest.get("visual_surface_ownership") or {}
    restore = manifest.get("settings_restore_order") or {}
    return (
        release.get("image_tag") == DEFAULT_TAG
        and release.get("image_version") == DEFAULT_VERSION
        and release.get("c17_4_firstboot_visual_f10_fix_embedded") is True
        and release.get("c17_4_1_settings_lock_restore_fix_embedded") is True
        and release.get("ready_for_c17_4_2_image_rebuild") is True
        and release.get("ready_for_batch_flash") is False
        and release.get("ready_for_dispatch") is False
        and release.get("ready_for_c18_player_audit") is False
        and ownership.get("settings_session_releases_lock_before_restoring_player") is True
        and restore.get("version") == RESTORE_ORDER_VERSION
        and restore.get("release_session_lock_before_restore_service") is True
        and restore.get("restore_service_refuses_start_while_lock_exists") is True
        and restore.get("write_final_status_skips_long_wait_while_lock_exists") is True
        and restore.get("hotfix_runtime_validated") is True
        and restore.get("clean_card_validation_required_before_batch") is True
    )


def c17_4_1_evidence_present(repo_root: Path) -> bool:
    runs = repo_root / "docs/evidence/candidate-a/runs"
    for readme in runs.glob("*-c17-4-1-settings-lock-restore-fix/README.md"):
        text = readme.read_text(encoding="utf-8")
        if (
            "c17_4_1_status=passed" in text
            and "ready_for_c17_4_2_image_rebuild=true" in text
            and "lock_removed_before_restore=true" in text
        ):
            return True
    return False


def validate_c17_4_2(rootfs: Path, image_name: str, *, repo_root: Path, kiosky_dir: Path) -> dict[str, Any]:
    original_tag = c17_4.DEFAULT_TAG
    original_version = c17_4.DEFAULT_VERSION
    try:
        c17_4.DEFAULT_TAG = DEFAULT_TAG
        c17_4.DEFAULT_VERSION = DEFAULT_VERSION
        inherited = c17_4.validate_c17_4(
            rootfs,
            image_name,
            repo_root=repo_root,
            kiosky_dir=kiosky_dir,
        )
    finally:
        c17_4.DEFAULT_TAG = original_tag
        c17_4.DEFAULT_VERSION = original_version

    session = base.cat_file(rootfs, "/opt/totem/bin/totem_open_settings_session.sh") or ""
    marker = base.cat_file(rootfs, MARKER_PATH) or ""
    restore_checks = restore_order_checks(session)
    checks = dict(inherited["checks"])
    checks.update(
        {
            "image_name_contains_c17_4_2": EXPECTED_IMAGE_TOKEN in image_name,
            "c17_4_2_marker_present": c17_4.is_file(rootfs, MARKER_PATH),
            "c17_4_2_marker_records_restore_fix": all(
                token in marker
                for token in (
                    "c17_4_1_settings_lock_restore_fix_embedded=true",
                    "release_session_lock_before_restore=true",
                    "restore_service_refuses_lock_present=true",
                    "write_final_status_lock_wait_guard=true",
                )
            ),
            "settings_restore_manifest_on_builder_ok": settings_restore_manifest_ok(repo_root),
            "c17_4_1_static_check_on_builder_present": (
                repo_root / "scripts/qa/c17_4_1_restore_order_static_check.py"
            ).is_file(),
            "c17_4_1_doc_on_builder": (
                repo_root / "docs/product/167_C17_4_1_SETTINGS_LOCK_RESTORE_FIX.md"
            ).is_file(),
            "c17_4_1_evidence_on_builder": c17_4_1_evidence_present(repo_root),
        }
    )
    checks.update({f"restore_order_{name}": ok for name, ok in restore_checks.items()})
    return {
        "checks": checks,
        "inherited_c17_4_ok": inherited["ok"],
        "restore_order_checks": restore_checks,
        "ok": all(checks.values()),
    }


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
        raise SystemExit("output_image_name_missing_c17_4_2")

    summary: dict[str, Any] = {
        "image_tag": args.image_tag,
        "image_version": args.image_version,
        "visual_design_system_version": VISUAL_SYSTEM_VERSION,
        "settings_restore_order_version": RESTORE_ORDER_VERSION,
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
        "c17_2_visual_polish_embedded": True,
        "c17_4_firstboot_visual_f10_fix_embedded": True,
        "c17_4_1_settings_lock_restore_fix_embedded": True,
        "c12_readonly_blocked": True,
        "c12_4_blocked": True,
        "kiosky_player_commit": repo_head(args.kiosky_player_dir),
        "orange_pi_totem_commit": repo_head(args.repo_root),
    }

    shutil.copy2(args.base_image, args.output_image)
    offset, length = base.parse_mbr_linux_partition(args.output_image)
    summary["rootfs_offset"] = offset
    summary["rootfs_bytes"] = length

    with tempfile.TemporaryDirectory(prefix="c17-4-2-image-") as td:
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
        summary.update(
            write_appliance_marker(
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
        validation = validate_c17_4_2(
            rootfs,
            args.output_image.name,
            repo_root=args.repo_root.resolve(),
            kiosky_dir=args.kiosky_player_dir.resolve(),
        )
        summary["offline_validation"] = validation
        if not validation["ok"]:
            (args.out_dir / "c17-4-2-offline-validation.json").write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return 1
        base.write_range(args.output_image, rootfs, offset=offset)

    digest = base.file_sha256(args.output_image)
    checksum_file = args.output_image.with_suffix(args.output_image.suffix + ".sha256")
    checksum_file.write_text(f"{digest}  {args.output_image.name}\n", encoding="utf-8")
    summary["image_sha256"] = digest
    summary["image_sha256_file"] = str(checksum_file)
    summary["image_bytes"] = args.output_image.stat().st_size
    summary["ok"] = True

    out_json = args.out_dir / "c17-4-2-offline-validation.json"
    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
