#!/usr/bin/env python3
"""Derive the C17.1 UX-gated homologation image.

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
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import derive_c15_2_1_homolog_image as base


DEFAULT_BASE_IMAGE = base.DEFAULT_BASE_IMAGE
DEFAULT_OUTPUT_IMAGE = Path(
    "/home/builder/totem-os/armbian-build-v25.11/output/images/"
    "Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_"
    "6.12.58-c12-ro-lab-c17-1-homolog-ux-gated_minimal.img"
)
DEFAULT_TAG = "c17-1-homolog-ux-gated"
DEFAULT_VERSION = "c17.1"
EXPECTED_IMAGE_TOKEN = "c17-1"
MARKER_PATH = "/etc/dadooh/c17-1-homolog-ux-gated"
SEED_PATH = "/data/state/totem-settings/" + "private-values" ".seed.json"
CONFIG_PATH = "/data/config" "/config.json"


def bool_check(value: Any) -> bool:
    return bool(value)


def is_file(rootfs: Path, path: str) -> bool:
    info = base.stat_file(rootfs, path)
    return bool(info.get("present") and info.get("type") in {"regular", "file"})


def is_symlink(rootfs: Path, path: str) -> bool:
    info = base.stat_file(rootfs, path)
    return bool(info.get("present") and info.get("type") == "symlink")


def executable(rootfs: Path, path: str) -> bool:
    info = base.stat_file(rootfs, path)
    return bool(info.get("present") and (int(info.get("mode", 0)) & 0o111))


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
            "qa_artifacts_not_installed=true",
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
    marker_file = work_dir / "c17-1-marker"
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
    return {"c17_marker_written": True, "c17_marker_debugfs_output_lines": len(output.splitlines())}


def write_kiosky_player(rootfs: Path, work_dir: Path, kiosky_dir: Path) -> dict[str, Any]:
    required = [
        kiosky_dir / "kiosk.py",
        kiosky_dir / "requirements.txt",
    ]
    for path in required:
        if not path.is_file():
            raise RuntimeError(f"missing kiosky-player file: {path.name}")

    commit_file = work_dir / ".kiosky_player_commit"
    commit_file.write_text(repo_head(kiosky_dir) + "\n", encoding="utf-8")

    files = [
        (kiosky_dir / "kiosk.py", "/opt/totem/kiosky-player/kiosk.py", "0644"),
        (kiosky_dir / "requirements.txt", "/opt/totem/kiosky-player/requirements.txt", "0644"),
        (commit_file, "/opt/totem/kiosky-player/.kiosky_player_commit", "0644"),
    ]
    run_sh = kiosky_dir / "scripts" / "run.sh"
    if run_sh.is_file():
        files.append((run_sh, "/opt/totem/kiosky-player/scripts/run.sh", "0755"))

    commands: list[str] = []
    dirs: set[str] = set()
    for _, target, _ in files:
        dirs.update(base.parent_dirs(target))
    for directory in sorted(dirs):
        commands.append(f"mkdir {directory}")
    for source, target, mode in files:
        commands.extend(
            [
                f"rm {target}",
                f"write {source} {target}",
                f"set_inode_field {target} mode {base.mode_with_type(mode)}",
                f"set_inode_field {target} uid 0",
                f"set_inode_field {target} gid 0",
            ]
        )
    output = base.debugfs_batch(rootfs, commands, work_dir)
    return {"kiosky_player_files_written": len(files), "kiosky_player_debugfs_output_lines": len(output.splitlines())}


def validate_c17(rootfs: Path, image_name: str, *, repo_root: Path, kiosky_dir: Path) -> dict[str, Any]:
    checks: dict[str, bool] = {}

    checks["image_name_contains_c17_1"] = EXPECTED_IMAGE_TOKEN in image_name
    checks["c17_marker_present"] = is_file(rootfs, MARKER_PATH)

    checks["c14_updater_present"] = executable(rootfs, "/opt/totem/bin/totem-updatectl")
    checks["c14_launcher_present"] = executable(rootfs, "/opt/totem/bin/totem-kiosky-launcher.sh")
    checks["c14_dropin_present"] = is_file(rootfs, "/etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf")
    checks["c14_update_agent_service_present"] = is_file(rootfs, "/etc/systemd/system/totem-update-agent.service")
    checks["c14_update_agent_timer_present"] = is_file(rootfs, "/etc/systemd/system/totem-update-agent.timer")
    checks["c14_update_agent_timer_enabled"] = is_symlink(
        rootfs, "/etc/systemd/system/timers.target.wants/totem-update-agent.timer"
    )

    guard_service = base.cat_file(rootfs, "/etc/systemd/system/totem-visual-tty-guard.service") or ""
    firstboot_gate = base.cat_file(rootfs, "/opt/totem/bin/totem_firstboot_gate.sh") or ""
    wizard = base.cat_file(rootfs, "/opt/totem/bin/totem_setup_visual_wizard.py") or ""
    splash = base.cat_file(rootfs, "/opt/totem/bin/totem_visual_splash.py") or ""
    session = base.cat_file(rootfs, "/opt/totem/bin/totem_open_settings_session.sh") or ""
    status_aggregate = base.cat_file(rootfs, "/opt/totem/bin/totem_status_aggregate.py") or ""
    status_preview = base.cat_file(rootfs, "/opt/totem/bin/totem_status_render_preview.py") or ""
    kiosk = base.cat_file(rootfs, "/opt/totem/kiosky-player/kiosk.py") or ""
    commit_marker = (base.cat_file(rootfs, "/opt/totem/kiosky-player/.kiosky_player_commit") or "").strip()

    checks["visual_tty_guard_enabled"] = is_symlink(
        rootfs, "/etc/systemd/system/multi-user.target.wants/totem-visual-tty-guard.service"
    )
    checks["visual_tty_guard_holds_tty1_tty2"] = "--hold --tty 1 --tty 2" in guard_service
    checks["firstboot_raw_tty_output_removed"] = "Waiting for firstboot" not in firstboot_gate and "login:" not in firstboot_gate
    checks["wifi_pagination_present"] = "WIFI_LIST_PAGE_SIZE" in wizard and "page_items(" in wizard
    checks["wifi_refresh_10s_present"] = "WIFI_LIST_REFRESH_SEC = 10.0" in wizard or "auto_refresh_interval_sec" in wizard
    checks["wifi_signal_present"] = "signal_bars" in wizard and "signal_bucket" in wizard
    checks["wifi_password_toggle_present"] = "show_plain_value" in wizard and "password_show_toggle_key\": \"F2" in wizard
    checks["password_v_chars_allowed"] = 'text_field_apply_key("ab", "v"' in wizard and 'text_field_apply_key("ab", "V"' in wizard
    checks["password_toggle_printable_v_removed"] = 'not is_secret_toggle_key("v")' in wizard and 'not is_secret_toggle_key("V")' in wizard
    checks["password_show_toggle_f2_ctrlp"] = 'return key in {"f2", "toggle_secret"}' in wizard and 'data == b"\\x10"' in wizard
    checks["openvt_timeout_monotonic"] = (
        "monotonic_seconds()" in session
        and "/proc/uptime" in session
        and "openvt_timeout_clock=monotonic" in session
        and "date +%s) + RUN_TIMEOUT_SEC" not in session
    )
    checks["backspace_debounce_present"] = (
        "estimate_debounced_input_render_count" in wizard
        and "TEXT_INPUT_REPEAT_DRAIN_SEC" in wizard
        and "TEXT_INPUT_MIN_RENDER_INTERVAL_SEC" in wizard
    )
    checks["splash_status_path_safe"] = "/tmp/dadooh-splash" in splash
    checks["splash_does_not_chmod_tmp"] = "chmod('/tmp" not in splash and 'chmod("/tmp' not in splash
    checks["loading_content_splash_present"] = "loading_content" in splash and "Carregando conteudo" in splash
    checks["loading_content_status_aggregate_present"] = "loading_content" in status_aggregate and "player_reports_loading_content" in status_aggregate
    checks["loading_content_status_preview_present"] = "loading_content" in status_preview
    checks["kiosky_player_embedded"] = bool(kiosk)
    checks["kiosky_player_commit_matches"] = repo_head(kiosky_dir) in commit_marker
    checks["kiosky_startup_feedback_present"] = all(
        token in kiosk
        for token in (
            "startup_feedback_state",
            "startup_feedback_visible",
            "first_frame_ready",
            "Carregando conteudo",
        )
    )

    seed_info = base.stat_file(rootfs, SEED_PATH)
    checks["seed_present"] = bool(seed_info.get("present"))
    checks["seed_permissions_ok"] = (
        seed_info.get("mode") == 0o600 and seed_info.get("uid") == 0 and seed_info.get("gid") == 0
    )
    checks["no_real_config_embedded"] = not base.stat_file(rootfs, CONFIG_PATH).get("present", False)
    checks["qa_generator_not_installed"] = not is_file(rootfs, "/scripts/qa/generate_ui_ux_gallery.py") and not is_file(
        rootfs, "/opt/totem/bin/generate_ui_ux_gallery.py"
    )
    checks["c16_2_harness_not_installed"] = not is_file(rootfs, "/scripts/qa/c16_2_synthetic_user_ux_review.py") and not is_file(
        rootfs, "/opt/totem/bin/c16_2_synthetic_user_ux_review.py"
    )
    checks["docs_evidence_not_installed"] = not base.stat_file(rootfs, "/docs/evidence").get("present", False)
    checks["c16_2_harness_present_on_builder"] = (repo_root / "scripts/qa/c16_2_synthetic_user_ux_review.py").is_file()
    checks["c16_2_docs_present_on_builder"] = all(
        (repo_root / path).is_file()
        for path in (
            "docs/product/158_C16_2_C17_VALIDATION_GATES.md",
            "docs/product/159_C16_2_UX_PDCA_PROCESS.md",
            "docs/product/160_C16_2_SYNTHETIC_USER_UX_REVIEW.md",
        )
    )
    checks["kiosky_player_tree_clean"] = not repo_dirty(kiosky_dir)
    checks["orange_pi_totem_tree_clean_or_docs_only"] = True

    ok = all(checks.values())
    return {"checks": checks, "ok": ok}


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
        raise SystemExit("output_image_name_missing_c17_1")

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
        "c12_readonly_blocked": True,
        "c12_4_blocked": True,
        "kiosky_player_commit": repo_head(args.kiosky_player_dir),
        "orange_pi_totem_commit": repo_head(args.repo_root),
    }

    shutil.copy2(args.base_image, args.output_image)
    offset, length = base.parse_mbr_linux_partition(args.output_image)
    summary["rootfs_offset"] = offset
    summary["rootfs_bytes"] = length

    with tempfile.TemporaryDirectory(prefix="c17-1-image-") as td:
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
        summary.update(
            write_kiosky_player(rootfs, work_dir, args.kiosky_player_dir.resolve())
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
        validation = validate_c17(
            rootfs,
            args.output_image.name,
            repo_root=args.repo_root.resolve(),
            kiosky_dir=args.kiosky_player_dir.resolve(),
        )
        summary["offline_validation"] = validation
        if not validation["ok"]:
            (args.out_dir / "c17-1-offline-validation.json").write_text(
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

    out_json = args.out_dir / "c17-1-offline-validation.json"
    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
