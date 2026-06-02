#!/usr/bin/env python3
"""Shared offline helper for embedding the totem-core update layout in images."""

from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import derive_c15_2_1_homolog_image as base


TOTEM_CORE_VERSION = "c17.6-environment-input-20260514T211247Z"
TOTEM_CORE_RELEASE_TAG = "totem-core-c17.6-environment-input-20260514T211247Z"
TOTEM_CORE_PAYLOAD_SHA256 = "e6b643429709ba9f747d86bb113abc35ab9645da23216eb81455dbc2f5a9acb9"
TOTEM_CORE_CREATED_AT_UTC = "2026-05-14T21:12:47Z"
UPDATE_POLICY_TARGET = "/data/updates/policy.json"
UPDATE_AGENT_SERVICE_TARGET = "/etc/systemd/system/totem-update-agent.service"
UPDATE_AGENT_TIMER_TARGET = "/etc/systemd/system/totem-update-agent.timer"
UPDATE_AGENT_TIMER_WANTS = "/etc/systemd/system/timers.target.wants/totem-update-agent.timer"

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
    "kiosky_service_launcher.sh",
]


def repo_head(path: Path) -> str:
    return (base.run(["git", "-C", str(path), "rev-parse", "HEAD"]).stdout or "").strip()


def write_file_commands(source: Path, target: str, mode_text: str = "0755") -> list[str]:
    commands: list[str] = []
    for directory in base.parent_dirs(target):
        if directory == "/":
            continue
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


def write_totem_core_embed(rootfs: Path, work_dir: Path, repo_root: Path) -> dict[str, Any]:
    """Embed C17.6 totem-core as image current + /opt fallback/wrappers."""
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
    update_policy = repo_root / "scripts/board/totem_update_policy.json"
    update_agent_service = repo_root / "scripts/board/systemd/totem-update-agent.service"
    update_agent_timer = repo_root / "scripts/board/systemd/totem-update-agent.timer"
    for required in (wrapper_py, wrapper_sh, update_policy, update_agent_service, update_agent_timer):
        if not required.is_file():
            raise RuntimeError(f"missing_totem_core_embed_input:{required}")

    commands: list[str] = []
    for directory in (
        "/data/updates",
        "/data/updates/incoming",
        "/data/updates/incoming/totem-core",
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
        "/etc/systemd/system",
        "/etc/systemd/system/timers.target.wants",
    ):
        commands.append(f"mkdir {directory}")

    commands.extend(write_file_commands(update_policy, UPDATE_POLICY_TARGET, "0644"))
    commands.extend(write_file_commands(update_agent_service, UPDATE_AGENT_SERVICE_TARGET, "0644"))
    commands.extend(write_file_commands(update_agent_timer, UPDATE_AGENT_TIMER_TARGET, "0644"))
    commands.append(f"rm {UPDATE_AGENT_TIMER_WANTS}")
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
                    "bash -n bin/kiosky_service_launcher.sh",
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
                    "manifest_created_at_utc": TOTEM_CORE_CREATED_AT_UTC,
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
    splash_service_file = work_dir / "dadooh-visual-splash.service"
    splash_service_file.write_text(
        "\n".join(
            [
                "[Unit]",
                "Description=Dadooh visual boot splash",
                "DefaultDependencies=no",
                "After=local-fs.target",
                "Before=basic.target getty.target kiosky-player.service",
                "",
                "[Service]",
                "Type=oneshot",
                "RemainAfterExit=yes",
                "ExecStartPre=/opt/totem/bin/totem_visual_tty_guard.sh --clear --tty 2",
                "ExecStart=/opt/totem/bin/totem_visual_splash.py boot --wait-framebuffer-sec 12 --status-out /tmp/dadooh-splash/boot/status.json",
                "ExecStop=/opt/totem/bin/totem_visual_splash.py shutdown --status-out /tmp/dadooh-splash/shutdown/status.json",
                "TimeoutSec=16",
                "StandardOutput=null",
                "StandardError=null",
                "",
                "[Install]",
                "WantedBy=sysinit.target",
                "",
            ]
        ),
        encoding="utf-8",
    )
    commands.extend(write_file_commands(splash_service_file, "/etc/systemd/system/dadooh-visual-splash.service", "0644"))
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
        "totem_core_embed_debugfs_output_lines": len(output.splitlines()),
    }


def _is_file(rootfs: Path, path: str) -> bool:
    info = base.stat_file(rootfs, path)
    return bool(info.get("present") and info.get("type") in {"regular", "file"})


def _is_symlink(rootfs: Path, path: str) -> bool:
    info = base.stat_file(rootfs, path)
    return bool(info.get("present") and info.get("type") == "symlink")


def _has_exec(rootfs: Path, path: str) -> bool:
    info = base.stat_file(rootfs, path)
    return bool(info.get("present") and (int(info.get("mode", 0)) & 0o111))


def _dump_text(rootfs: Path, path: str) -> str:
    with tempfile.TemporaryDirectory(prefix="totem-core-validate-") as tmp:
        out_path = Path(tmp) / "dump.txt"
        base.debugfs(rootfs, f"dump {path} {out_path}")
        if not out_path.is_file():
            return ""
        return out_path.read_text(encoding="utf-8", errors="replace")


def _symlink_target(rootfs: Path, path: str) -> str:
    out = base.debugfs(rootfs, f"stat {path}")
    if "File not found" in out or "couldn't" in out.lower() or "no such" in out.lower():
        return ""
    for pattern in (r"Fast link dest:\s*(.+)", r"link:\s*(.+)"):
        match = re.search(pattern, out)
        if match:
            return match.group(1).strip().strip('"')
    return ""


def validate_totem_core_embed(rootfs: Path) -> dict[str, Any]:
    """Return an offline validation bundle for the totem-core image layout."""
    release_root = f"/data/core/totem/releases/{TOTEM_CORE_VERSION}"
    state = base.cat_file(rootfs, "/data/core/totem/state.json") or ""
    updatectl = base.cat_file(rootfs, "/opt/totem/bin/totem-updatectl") or ""
    splash_service = base.cat_file(rootfs, "/etc/systemd/system/dadooh-visual-splash.service") or ""
    update_agent_service = _dump_text(rootfs, UPDATE_AGENT_SERVICE_TARGET)
    policy_text = _dump_text(rootfs, UPDATE_POLICY_TARGET)
    try:
        update_policy = json.loads(policy_text)
    except json.JSONDecodeError:
        update_policy = {}
    policy_stat = base.stat_file(rootfs, UPDATE_POLICY_TARGET)
    current_target = _symlink_target(rootfs, "/data/core/totem/current")

    checks: dict[str, bool] = {
        "totem_core_current_symlink_present": _is_symlink(rootfs, "/data/core/totem/current"),
        "totem_core_current_symlink_target_exact": current_target == f"releases/{TOTEM_CORE_VERSION}",
        "totem_core_state_present": _is_file(rootfs, "/data/core/totem/state.json"),
        "totem_core_state_records_current_version": TOTEM_CORE_VERSION in state,
        "totem_core_state_records_created_at": TOTEM_CORE_CREATED_AT_UTC in state,
        "totem_core_release_health_present": _is_file(rootfs, f"{release_root}/health/totem-core-health.json"),
        "totem_core_release_fragment_present": _is_file(rootfs, f"{release_root}/manifest-fragment/totem-core.json"),
        "totem_core_updatectl_capable": "_totem_core_health_check" in updatectl and "_make_world_traversable" in updatectl,
        "totem_core_splash_service_uses_wrapper": "/opt/totem/bin/totem_visual_splash.py" in splash_service,
        "totem_core_update_policy_present": _is_file(rootfs, UPDATE_POLICY_TARGET),
        "totem_core_update_policy_mode_0644": int(policy_stat.get("mode", 0)) == 0o644,
        "totem_core_update_policy_root_owned": policy_stat.get("uid") == 0 and policy_stat.get("gid") == 0,
        "totem_core_update_policy_restricts_core": update_policy.get("allowed_components") == ["totem-core"],
        "totem_core_update_policy_device_track_c18": update_policy.get("device_track") == "c18-hwdecode",
        "totem_core_update_policy_downgrade_false": update_policy.get("allow_downgrade") is False,
        "totem_core_update_policy_channel_explicit": update_policy.get("device_channel") in {"lab", "homologation", "stable"},
        "totem_core_update_agent_service_core_repo": (
            "--component totem-core" in update_agent_service
            and "--repo dadoohai/orange_pi_totem" in update_agent_service
            and "dadoohai/kiosky-player" not in update_agent_service
        ),
        "totem_core_update_timer_unit_present": _is_file(rootfs, UPDATE_AGENT_TIMER_TARGET),
        "totem_core_update_timer_disabled": not base.stat_file(rootfs, UPDATE_AGENT_TIMER_WANTS).get("present", False),
    }
    for core_file in CORE_FILES:
        checks[f"totem_core_release_{core_file}"] = _has_exec(rootfs, f"{release_root}/bin/{core_file}")
        checks[f"totem_core_fallback_{core_file}"] = _has_exec(rootfs, f"/opt/totem/core-fallback/bin/{core_file}")
        wrapper = base.cat_file(rootfs, f"/opt/totem/bin/{core_file}") or ""
        checks[f"totem_core_wrapper_{core_file}"] = "TOTEM_CORE_EXEC_WRAPPER" in wrapper
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "totem_core_current_version": TOTEM_CORE_VERSION,
    }
