#!/usr/bin/env python3
"""Shared offline helper for embedding the totem-core update layout in images."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

import derive_c15_2_1_homolog_image as base


TOTEM_CORE_VERSION = "c26.9-local-recovery-20260718-a9ffd4c-composed-actions"
TOTEM_CORE_RELEASE_TAG = "totem-core-c26.9-local-recovery-20260718-a9ffd4c-composed-actions"
TOTEM_CORE_CHANNEL = "homologation"
TOTEM_CORE_PAYLOAD_SHA256 = "bfca7aeb90c2b5e9c35ce3c14f540ef631a8a1fab0b1860625d90f777c4e26fb"
TOTEM_CORE_CREATED_AT_UTC = "2026-07-18T23:59:01Z"
TOTEM_CORE_SOURCE_COMMIT = "a9ffd4c6c6c3e42d155ea248d009786ca25a6675"
TOTEM_CORE_CAPABILITIES = ("product-reset-v1", "totem-actions-v1")
TOTEM_CORE_PREVIOUS_VERSION = "c26.8-local-recovery-20260718-08d9412-transport-actions"
TOTEM_CORE_PREVIOUS_RELEASE_TAG = "totem-core-c26.8-local-recovery-20260718-08d9412-transport-actions"
TOTEM_CORE_PREVIOUS_CHANNEL = "homologation"
TOTEM_CORE_PREVIOUS_PAYLOAD_SHA256 = "7515375cf2245e0fedc297284a034bd955c2acb10ad3ae36d5c3bde87f089542"
TOTEM_CORE_PREVIOUS_CREATED_AT_UTC = "2026-07-18T23:53:13Z"
TOTEM_CORE_PREVIOUS_SOURCE_COMMIT = "08d9412780c811ff72efa7718636366a64bf82f1"
TOTEM_CORE_PREVIOUS_CAPABILITIES = ("product-reset-v1", "totem-actions-v1")
UPDATE_POLICY_TARGET = "/data/updates/policy.json"
UPDATE_AGENT_SERVICE_TARGET = "/etc/systemd/system/totem-update-agent.service"
UPDATE_AGENT_TIMER_TARGET = "/etc/systemd/system/totem-update-agent.timer"
UPDATE_AGENT_TIMER_WANTS = "/etc/systemd/system/timers.target.wants/totem-update-agent.timer"
PLAYER_RUNTIME_AUTH_TARGET = "/data/updates/player-runtime-production-autopull.json"
PLAYER_RUNTIME_CANARY_SOURCE = "assets/c18-canary-h264.mp4"
PLAYER_RUNTIME_CANARY_TARGET = "/data/media/c18-canary-h264.mp4"
PLAYER_RUNTIME_UPDATE_AGENT_SERVICE_TARGET = "/etc/systemd/system/totem-player-runtime-update-agent.service"
PLAYER_RUNTIME_UPDATE_AGENT_TIMER_TARGET = "/etc/systemd/system/totem-player-runtime-update-agent.timer"
PLAYER_RUNTIME_UPDATE_AGENT_TIMER_WANTS = "/etc/systemd/system/timers.target.wants/totem-player-runtime-update-agent.timer"
FIRSTBOOT_GATE_SERVICE_TARGET = "/etc/systemd/system/totem-firstboot-gate.service"
FIRSTBOOT_GATE_SERVICE_WANTS = "/etc/systemd/system/multi-user.target.wants/totem-firstboot-gate.service"
PRODUCT_RESET_GC_SERVICE_TARGET = "/etc/systemd/system/totem-product-reset-gc.service"
PLAYER_RUNTIME_PRODUCTION_AUTH_SCHEMA = "dadooh.c18.player_runtime.production_autopull_authorization.v1"
PLAYER_RUNTIME_PRODUCTION_AUTH_REPO = "dadoohai/orange_pi_totem"
PLAYER_RUNTIME_PRODUCTION_AUTH_ESSENTIAL_FIELDS = (
    "schema",
    "enabled",
    "component",
    "auto_pull_enabled",
    "allow_latest",
    "allow_prerelease",
    "allow_downgrade",
    "repo",
    "tag_name",
    "version",
    "channel",
    "device_track",
    "source_commit",
    "payload_sha256",
    "manifest_sha256",
    "release_gate_asset_name",
    "release_gate_sha256",
)
PLAYER_RUNTIME_PRODUCTION_AUTH_FIELDS = frozenset(
    {*PLAYER_RUNTIME_PRODUCTION_AUTH_ESSENTIAL_FIELDS, "business_decision", "non_claims"}
)
PLAYER_RUNTIME_PRODUCTION_AUTH_BUSINESS_FIELDS = frozenset(
    {"risk_accepted", "rollout_mode", "operator", "rollback_owner", "accepted_at_local_date"}
)
PLAYER_RUNTIME_PRODUCTION_AUTH_REQUIRED_NON_CLAIMS = frozenset(
    {
        "not_latest_broad",
        "not_future_player_runtime_targets",
        "not_kiosky_player_legacy_release_path",
        "not_media_system_update",
        "not_dashboard_or_canary_groups",
        "not_device_side_signature_enforcement",
    }
)
TOTEM_CORE_EMBED_PROFILES = {
    "homologation": {
        "policy_file": "totem_update_policy.json",
        "service_file": "totem-update-agent.service",
        "timer_file": "totem-update-agent.timer",
        "timer_enabled": False,
        "player_runtime_authorization_file": None,
        "player_runtime_service_file": None,
        "player_runtime_timer_file": None,
        "player_runtime_timer_enabled": False,
    },
    "production": {
        "policy_file": "totem_update_policy_production.json",
        "service_file": "totem-update-agent.production.service",
        "timer_file": "totem-update-agent.production.timer",
        "timer_enabled": True,
        "player_runtime_authorization_file": "player_runtime_production_autopull.json",
        "player_runtime_service_file": "totem-player-runtime-update-agent.production.service",
        "player_runtime_timer_file": "totem-player-runtime-update-agent.production.timer",
        "player_runtime_timer_enabled": True,
    },
}

CORE_FILES = [
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
]
TOTEM_CORE_PREVIOUS_EXCLUDED_FILES = frozenset()

IMAGE_FIXED_PLAYER_FILES = [
    "kiosky_service_launcher.sh",
    "totem-kiosky-launcher.sh",
    "totem_player_status_mpv_watchdog.py",
    "c18_player_runtime_candidate_health.py",
    "c18_playback_health_collect.py",
    "c18_playback_health_summary.py",
    "totem_updatectl.py",
]
IMAGE_FIXED_PLAYER_SYSTEMD_FILES = [
    (
        "systemd/kiosky-player.service.d/20-dadooh-launcher.conf",
        "/etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf",
    ),
    (
        "totem-firstboot-gate.service",
        "/etc/systemd/system/totem-firstboot-gate.service",
    ),
    (
        "totem-product-reset-gc.service",
        "/etc/systemd/system/totem-product-reset-gc.service",
    ),
]


def _validate_totem_core_release(
    repo_root: Path,
    core_files: list[str],
    *,
    version: str,
    channel: str,
    source_commit: str,
    payload_sha256: str,
    created_at_utc: str,
    capabilities: tuple[str, ...],
    require_worktree_exact: bool,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    release_dir = repo_root / "releases" / "core-updates" / version
    manifest_path = release_dir / f"dadooh-totem-core-{version}.manifest.json"
    payload_path = release_dir / f"dadooh-totem-core-{version}.tar.gz"
    if not manifest_path.is_file() or not payload_path.is_file():
        raise RuntimeError("totem_core_embed_release_artifacts_missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {
        "component": "totem-core",
        "version": version,
        "channel": channel,
        "source_commit": source_commit,
        "source_dirty": False,
        "payload_sha256": payload_sha256,
        "created_at_utc": created_at_utc,
        "source_repo": "dadoohai/orange_pi_totem",
        "source_branch": "foundation-v0.1",
        "payload": payload_path.name,
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise RuntimeError("totem_core_embed_manifest_identity_mismatch")
    payload_sha = hashlib.sha256(payload_path.read_bytes()).hexdigest()
    if payload_sha != payload_sha256:
        raise RuntimeError("totem_core_embed_payload_sha256_mismatch")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
        cwd=repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if ancestor.returncode != 0:
        raise RuntimeError("totem_core_embed_source_commit_not_ancestor")
    payload_files: dict[str, bytes] = {}
    with tarfile.open(payload_path, "r:gz") as archive:
        members: dict[str, tarfile.TarInfo] = {}
        for member in archive.getmembers():
            if not member.isfile():
                continue
            name = member.name.removeprefix("./")
            if name in members:
                raise RuntimeError(f"totem_core_embed_payload_duplicate_member:{name}")
            members[name] = member
        health_member = members.get("health/totem-core-health.json")
        health_file = archive.extractfile(health_member) if health_member is not None else None
        if health_file is None:
            raise RuntimeError("totem_core_embed_payload_health_missing")
        health_bytes = health_file.read()
        health = json.loads(health_bytes.decode("utf-8"))
        if health.get("capabilities") != list(capabilities):
            raise RuntimeError("totem_core_embed_payload_capabilities_mismatch")
        payload_files["health/totem-core-health.json"] = health_bytes
        fragment_member = members.get("manifest-fragment/totem-core.json")
        fragment_file = archive.extractfile(fragment_member) if fragment_member is not None else None
        if fragment_file is None:
            raise RuntimeError("totem_core_embed_payload_fragment_missing")
        payload_files["manifest-fragment/totem-core.json"] = fragment_file.read()
        for core_file in core_files:
            member = members.get(f"bin/{core_file}")
            extracted = archive.extractfile(member) if member is not None else None
            if extracted is None:
                raise RuntimeError(f"totem_core_embed_payload_file_missing:{core_file}")
            extracted_bytes = extracted.read()
            committed = subprocess.run(
                ["git", "show", f"{source_commit}:scripts/board/{core_file}"],
                cwd=repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if committed.returncode != 0 or extracted_bytes != committed.stdout:
                raise RuntimeError(f"totem_core_embed_payload_commit_mismatch:{core_file}")
            source = repo_root / "scripts" / "board" / core_file
            if require_worktree_exact and extracted_bytes != source.read_bytes():
                raise RuntimeError(f"totem_core_embed_payload_source_mismatch:{core_file}")
            payload_files[f"bin/{core_file}"] = extracted_bytes
    provenance = {
        "version": version,
        "release_tag": f"totem-core-{version}",
        "channel": channel,
        "source_commit": source_commit,
        "source_dirty": False,
        "payload_sha256": payload_sha,
        "created_at_utc": created_at_utc,
        "capabilities": list(capabilities),
        "manifest": str(manifest_path.relative_to(repo_root)),
        "payload": str(payload_path.relative_to(repo_root)),
    }
    return provenance, payload_files


def validate_totem_core_release_provenance(repo_root: Path, core_files: list[str]) -> dict[str, Any]:
    provenance, _payload_files = _validate_totem_core_release(
        repo_root,
        core_files,
        version=TOTEM_CORE_VERSION,
        channel=TOTEM_CORE_CHANNEL,
        source_commit=TOTEM_CORE_SOURCE_COMMIT,
        payload_sha256=TOTEM_CORE_PAYLOAD_SHA256,
        created_at_utc=TOTEM_CORE_CREATED_AT_UTC,
        capabilities=TOTEM_CORE_CAPABILITIES,
        require_worktree_exact=True,
    )
    return provenance


def validate_totem_core_previous_release_provenance(repo_root: Path, core_files: list[str]) -> dict[str, Any]:
    previous_core_files = [
        core_file for core_file in core_files if core_file not in TOTEM_CORE_PREVIOUS_EXCLUDED_FILES
    ]
    provenance, _payload_files = _validate_totem_core_release(
        repo_root,
        previous_core_files,
        version=TOTEM_CORE_PREVIOUS_VERSION,
        channel=TOTEM_CORE_PREVIOUS_CHANNEL,
        source_commit=TOTEM_CORE_PREVIOUS_SOURCE_COMMIT,
        payload_sha256=TOTEM_CORE_PREVIOUS_PAYLOAD_SHA256,
        created_at_utc=TOTEM_CORE_PREVIOUS_CREATED_AT_UTC,
        capabilities=TOTEM_CORE_PREVIOUS_CAPABILITIES,
        require_worktree_exact=False,
    )
    return provenance


def _materialize_payload_file(work_dir: Path, slot: str, relative_path: str, content: bytes) -> Path:
    output = work_dir / "totem-core-slots" / slot / relative_path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    return output


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


def resolve_totem_core_embed_profile(profile: str) -> dict[str, Any]:
    if profile not in TOTEM_CORE_EMBED_PROFILES:
        raise RuntimeError(f"unsupported_totem_core_embed_profile:{profile}")
    return dict(TOTEM_CORE_EMBED_PROFILES[profile])


def _hex_digest(value: Any, length: int = 64) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(char in "0123456789abcdef" for char in value.lower())
    )


def _player_runtime_production_authorization_failures(auth: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if set(auth) != PLAYER_RUNTIME_PRODUCTION_AUTH_FIELDS:
        failures.append("fields_mismatch")
    expected_values = {
        "schema": PLAYER_RUNTIME_PRODUCTION_AUTH_SCHEMA,
        "enabled": True,
        "component": "player-runtime",
        "auto_pull_enabled": True,
        "allow_latest": False,
        "allow_prerelease": False,
        "allow_downgrade": False,
        "channel": "homologation",
        "device_track": "c18-hwdecode",
    }
    for key, value in expected_values.items():
        if auth.get(key) != value:
            failures.append(f"{key}_mismatch")
    for key in ("repo", "tag_name", "version", "release_gate_asset_name"):
        if not isinstance(auth.get(key), str) or not auth.get(key):
            failures.append(f"{key}_missing")
    if auth.get("repo") != PLAYER_RUNTIME_PRODUCTION_AUTH_REPO:
        failures.append("repo_invalid")
    if isinstance(auth.get("version"), str) and auth.get("tag_name") != f"player-runtime-{auth['version']}":
        failures.append("tag_name_version_mismatch")
    if auth.get("release_gate_asset_name") != "c18-player-runtime-release-gate.json":
        failures.append("release_gate_asset_name_mismatch")
    if not _hex_digest(auth.get("source_commit"), 40):
        failures.append("source_commit_invalid")
    for key in ("payload_sha256", "manifest_sha256", "release_gate_sha256"):
        if not _hex_digest(auth.get(key)):
            failures.append(f"{key}_invalid")
    decision = auth.get("business_decision")
    if (
        not isinstance(decision, dict)
        or set(decision) != PLAYER_RUNTIME_PRODUCTION_AUTH_BUSINESS_FIELDS
        or decision.get("risk_accepted") is not True
    ):
        failures.append("business_decision_risk_not_accepted")
    else:
        if decision.get("rollout_mode") != "simple_global":
            failures.append("business_decision_rollout_mode_mismatch")
        for key in ("operator", "rollback_owner"):
            if not isinstance(decision.get(key), str) or not decision[key].strip():
                failures.append(f"business_decision_{key}_missing")
        accepted_date = decision.get("accepted_at_local_date")
        try:
            parsed_date = dt.date.fromisoformat(accepted_date) if isinstance(accepted_date, str) else None
        except ValueError:
            parsed_date = None
        if parsed_date is None or parsed_date.isoformat() != accepted_date:
            failures.append("business_decision_date_invalid")
    non_claims = auth.get("non_claims")
    if not isinstance(non_claims, list) or not all(isinstance(item, str) for item in non_claims):
        failures.append("non_claims_invalid")
    elif (
        len(non_claims) != len(PLAYER_RUNTIME_PRODUCTION_AUTH_REQUIRED_NON_CLAIMS)
        or set(non_claims) != PLAYER_RUNTIME_PRODUCTION_AUTH_REQUIRED_NON_CLAIMS
    ):
        failures.append("non_claims_missing_required")
    return failures


def validate_player_runtime_production_authorization(auth: dict[str, Any]) -> bool:
    return not _player_runtime_production_authorization_failures(auth)


def load_player_runtime_production_authorization(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing_player_runtime_production_authorization:{path}")
    try:
        auth = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid_player_runtime_authorization_json:{path}") from exc
    if not isinstance(auth, dict):
        raise RuntimeError(f"invalid_player_runtime_authorization_json:{path}")
    failures = _player_runtime_production_authorization_failures(auth)
    if failures:
        raise RuntimeError(f"invalid_player_runtime_production_authorization:{path}:{','.join(failures)}")
    return auth


def _profile_authorization_path(profile_config: dict[str, Any], repo_root: Path) -> Path | None:
    authorization_file = profile_config.get("player_runtime_authorization_file")
    if not authorization_file:
        return None
    return repo_root / "scripts/board" / str(authorization_file)


def _player_runtime_authorization_matches_expected(
    embedded: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    if not validate_player_runtime_production_authorization(embedded):
        return False
    for field in PLAYER_RUNTIME_PRODUCTION_AUTH_ESSENTIAL_FIELDS:
        if embedded.get(field) != expected.get(field):
            return False
    if set(embedded.get("non_claims") or []) != set(expected.get("non_claims") or []):
        return False
    return embedded.get("business_decision") == expected.get("business_decision")


def write_totem_core_embed(
    rootfs: Path,
    work_dir: Path,
    repo_root: Path,
    *,
    profile: str = "homologation",
    debugfs_batch_runner: Callable[[Path, list[str], Path], str] | None = None,
) -> dict[str, Any]:
    """Embed a distinct C26 current/previous pair plus /opt fallback/wrappers."""
    profile_config = resolve_totem_core_embed_profile(profile)
    manifest_path = repo_root / "scripts/board/totem_appliance_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    embed = manifest.get("totem_core_image_embed") or {}
    core_files = list(embed.get("core_files") or CORE_FILES)
    release_provenance, current_payload_files = _validate_totem_core_release(
        repo_root,
        core_files,
        version=TOTEM_CORE_VERSION,
        channel=TOTEM_CORE_CHANNEL,
        source_commit=TOTEM_CORE_SOURCE_COMMIT,
        payload_sha256=TOTEM_CORE_PAYLOAD_SHA256,
        created_at_utc=TOTEM_CORE_CREATED_AT_UTC,
        capabilities=TOTEM_CORE_CAPABILITIES,
        require_worktree_exact=True,
    )
    previous_core_files = [
        core_file for core_file in core_files if core_file not in TOTEM_CORE_PREVIOUS_EXCLUDED_FILES
    ]
    previous_release_provenance, previous_payload_files = _validate_totem_core_release(
        repo_root,
        previous_core_files,
        version=TOTEM_CORE_PREVIOUS_VERSION,
        channel=TOTEM_CORE_PREVIOUS_CHANNEL,
        source_commit=TOTEM_CORE_PREVIOUS_SOURCE_COMMIT,
        payload_sha256=TOTEM_CORE_PREVIOUS_PAYLOAD_SHA256,
        created_at_utc=TOTEM_CORE_PREVIOUS_CREATED_AT_UTC,
        capabilities=TOTEM_CORE_PREVIOUS_CAPABILITIES,
        require_worktree_exact=False,
    )
    if TOTEM_CORE_VERSION == TOTEM_CORE_PREVIOUS_VERSION:
        raise RuntimeError("totem_core_embed_slots_same_version")
    if TOTEM_CORE_PAYLOAD_SHA256 == TOTEM_CORE_PREVIOUS_PAYLOAD_SHA256:
        raise RuntimeError("totem_core_embed_slots_same_payload")
    current_target = f"releases/{TOTEM_CORE_VERSION}"
    previous_target = f"releases/{TOTEM_CORE_PREVIOUS_VERSION}"
    release_root = f"/data/core/totem/releases/{TOTEM_CORE_VERSION}"
    previous_release_root = f"/data/core/totem/releases/{TOTEM_CORE_PREVIOUS_VERSION}"
    release_bin = f"{release_root}/bin"
    previous_release_bin = f"{previous_release_root}/bin"
    fallback_bin = "/opt/totem/core-fallback/bin"
    wrappers_bin = "/opt/totem/bin"
    wrapper_py = repo_root / "scripts/board/totem_core_exec.py"
    wrapper_sh = repo_root / "scripts/board/totem_core_exec.sh"
    updatectl_py = repo_root / "scripts/board/totem_updatectl.py"
    update_policy = repo_root / "scripts/board" / str(profile_config["policy_file"])
    update_agent_service = repo_root / "scripts/board/systemd" / str(profile_config["service_file"])
    update_agent_timer = repo_root / "scripts/board/systemd" / str(profile_config["timer_file"])
    player_runtime_authorization = _profile_authorization_path(profile_config, repo_root)
    player_runtime_service = (
        repo_root / "scripts/board/systemd" / str(profile_config["player_runtime_service_file"])
        if profile_config.get("player_runtime_service_file")
        else None
    )
    player_runtime_timer = (
        repo_root / "scripts/board/systemd" / str(profile_config["player_runtime_timer_file"])
        if profile_config.get("player_runtime_timer_file")
        else None
    )
    for required in (wrapper_py, wrapper_sh, updatectl_py, update_policy, update_agent_service, update_agent_timer):
        if not required.is_file():
            raise RuntimeError(f"missing_totem_core_embed_input:{required}")
    for required in (player_runtime_authorization, player_runtime_service, player_runtime_timer):
        if required is not None and not required.is_file():
            raise RuntimeError(f"missing_totem_core_embed_input:{required}")
    if profile == "production":
        if player_runtime_authorization is None:
            raise RuntimeError("missing_player_runtime_production_authorization_profile")
        load_player_runtime_production_authorization(player_runtime_authorization)

    commands: list[str] = []
    wanted_directories = (
        "/data/updates",
        "/data/updates/incoming",
        "/data/updates/incoming/totem-core",
        "/data/updates/incoming/player-runtime",
        "/data/core",
        "/data/core/totem",
        "/data/core/totem/releases",
        "/data/player-runtime",
        "/data/player-runtime/releases",
        "/data/media",
        release_root,
        release_bin,
        f"{release_root}/health",
        f"{release_root}/manifest-fragment",
        previous_release_root,
        previous_release_bin,
        f"{previous_release_root}/health",
        f"{previous_release_root}/manifest-fragment",
        "/opt/totem/core-fallback",
        fallback_bin,
        wrappers_bin,
        "/etc/systemd/system",
        "/etc/systemd/system/timers.target.wants",
        "/etc/systemd/system/multi-user.target.wants",
    )
    mkdir_directories: list[str] = []
    for directory in wanted_directories:
        for parent in base.parent_dirs(f"{directory}/.keep"):
            if parent != "/" and parent not in mkdir_directories:
                mkdir_directories.append(parent)
    for directory in mkdir_directories:
        commands.append(f"mkdir {directory}")

    commands.extend(write_file_commands(update_policy, UPDATE_POLICY_TARGET, "0644"))
    commands.extend(write_file_commands(update_agent_service, UPDATE_AGENT_SERVICE_TARGET, "0644"))
    commands.extend(write_file_commands(update_agent_timer, UPDATE_AGENT_TIMER_TARGET, "0644"))
    commands.append(f"rm {UPDATE_AGENT_TIMER_WANTS}")
    if profile_config["timer_enabled"]:
        commands.append(f"symlink {UPDATE_AGENT_TIMER_WANTS} {UPDATE_AGENT_TIMER_TARGET}")
    commands.append(f"rm {PLAYER_RUNTIME_UPDATE_AGENT_TIMER_WANTS}")
    commands.append(f"rm {PLAYER_RUNTIME_AUTH_TARGET}")
    commands.append(f"rm {PLAYER_RUNTIME_UPDATE_AGENT_SERVICE_TARGET}")
    commands.append(f"rm {PLAYER_RUNTIME_UPDATE_AGENT_TIMER_TARGET}")
    if player_runtime_authorization is not None:
        commands.extend(write_file_commands(player_runtime_authorization, PLAYER_RUNTIME_AUTH_TARGET, "0644"))
    if player_runtime_service is not None:
        commands.extend(write_file_commands(
            player_runtime_service,
            PLAYER_RUNTIME_UPDATE_AGENT_SERVICE_TARGET,
            "0644",
        ))
    if player_runtime_timer is not None:
        commands.extend(write_file_commands(
            player_runtime_timer,
            PLAYER_RUNTIME_UPDATE_AGENT_TIMER_TARGET,
            "0644",
        ))
    if profile_config.get("player_runtime_timer_enabled"):
        commands.append(
            f"symlink {PLAYER_RUNTIME_UPDATE_AGENT_TIMER_WANTS} {PLAYER_RUNTIME_UPDATE_AGENT_TIMER_TARGET}"
        )
    if profile == "production":
        canary_media = repo_root / "scripts/board" / PLAYER_RUNTIME_CANARY_SOURCE
        if not canary_media.is_file():
            raise RuntimeError(f"missing_player_runtime_canary_media:{PLAYER_RUNTIME_CANARY_SOURCE}")
        commands.extend(write_file_commands(canary_media, PLAYER_RUNTIME_CANARY_TARGET, "0644"))
    commands.extend(write_file_commands(wrapper_py, f"{wrappers_bin}/totem_core_exec.py"))
    commands.extend(write_file_commands(wrapper_sh, f"{wrappers_bin}/totem_core_exec.sh"))
    commands.extend(write_file_commands(updatectl_py, f"{wrappers_bin}/totem-updatectl"))
    for core_file in core_files:
        if "/" in core_file or core_file.startswith("."):
            raise RuntimeError(f"unsafe_totem_core_file:{core_file}")
        worktree_source = repo_root / "scripts/board" / core_file
        if not worktree_source.is_file():
            raise RuntimeError(f"missing_totem_core_file:{core_file}")
        current_source = _materialize_payload_file(
            work_dir,
            "current",
            f"bin/{core_file}",
            current_payload_files[f"bin/{core_file}"],
        )
        commands.extend(write_file_commands(current_source, f"{fallback_bin}/{core_file}"))
        commands.extend(write_file_commands(current_source, f"{release_bin}/{core_file}"))
        if core_file in previous_core_files:
            previous_source = _materialize_payload_file(
                work_dir,
                "previous",
                f"bin/{core_file}",
                previous_payload_files[f"bin/{core_file}"],
            )
            commands.extend(write_file_commands(previous_source, f"{previous_release_bin}/{core_file}"))
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
    for source_rel, target in IMAGE_FIXED_PLAYER_SYSTEMD_FILES:
        if source_rel.startswith(".") or ".." in Path(source_rel).parts:
            raise RuntimeError(f"unsafe_fixed_player_systemd_file:{source_rel}")
        source = repo_root / "scripts/board" / source_rel
        if not source.is_file():
            raise RuntimeError(f"missing_fixed_player_systemd_file:{source_rel}")
        commands.extend(write_file_commands(source, target, "0644"))
    commands.append(f"rm {FIRSTBOOT_GATE_SERVICE_WANTS}")
    commands.append(f"symlink {FIRSTBOOT_GATE_SERVICE_WANTS} {FIRSTBOOT_GATE_SERVICE_TARGET}")

    health_file = _materialize_payload_file(
        work_dir,
        "current",
        "health/totem-core-health.json",
        current_payload_files["health/totem-core-health.json"],
    )
    fragment_file = _materialize_payload_file(
        work_dir,
        "current",
        "manifest-fragment/totem-core.json",
        current_payload_files["manifest-fragment/totem-core.json"],
    )
    previous_health_file = _materialize_payload_file(
        work_dir,
        "previous",
        "health/totem-core-health.json",
        previous_payload_files["health/totem-core-health.json"],
    )
    previous_fragment_file = _materialize_payload_file(
        work_dir,
        "previous",
        "manifest-fragment/totem-core.json",
        previous_payload_files["manifest-fragment/totem-core.json"],
    )
    state_file = work_dir / "totem-core-state.json"
    state_file.write_text(
        json.dumps(
            {
                "schema": "dadooh.totem.update.state.v1",
                "component": "totem-core",
                "current": {
                    "version": TOTEM_CORE_VERSION,
                    "channel": TOTEM_CORE_CHANNEL,
                    "path": current_target,
                    "source": "image_embed",
                    "source_repo": "dadoohai/orange_pi_totem",
                    "source_branch": "foundation-v0.1",
                    "source_commit": TOTEM_CORE_SOURCE_COMMIT,
                    "payload_sha256": TOTEM_CORE_PAYLOAD_SHA256,
                    "manifest_created_at_utc": TOTEM_CORE_CREATED_AT_UTC,
                },
                "previous": {
                    "version": TOTEM_CORE_PREVIOUS_VERSION,
                    "channel": TOTEM_CORE_PREVIOUS_CHANNEL,
                    "path": previous_target,
                    "source": "image_embed_previous",
                    "source_repo": "dadoohai/orange_pi_totem",
                    "source_branch": "foundation-v0.1",
                    "source_commit": TOTEM_CORE_PREVIOUS_SOURCE_COMMIT,
                    "payload_sha256": TOTEM_CORE_PREVIOUS_PAYLOAD_SHA256,
                    "manifest_created_at_utc": TOTEM_CORE_PREVIOUS_CREATED_AT_UTC,
                },
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
    commands.extend(
        write_file_commands(
            previous_health_file,
            f"{previous_release_root}/health/totem-core-health.json",
            "0644",
        )
    )
    commands.extend(
        write_file_commands(
            previous_fragment_file,
            f"{previous_release_root}/manifest-fragment/totem-core.json",
            "0644",
        )
    )
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
            "rm /data/core/totem/previous",
            f"symlink /data/core/totem/previous {previous_target}",
        ]
    )

    runner = debugfs_batch_runner or base.debugfs_batch
    output = runner(rootfs, commands, work_dir)
    return {
        "totem_core_current_version": TOTEM_CORE_VERSION,
        "totem_core_previous_version": TOTEM_CORE_PREVIOUS_VERSION,
        "totem_core_embed_profile": profile,
        "totem_core_files_embedded": len(core_files),
        "image_fixed_player_files_embedded": len(IMAGE_FIXED_PLAYER_FILES),
        "image_fixed_player_systemd_files_embedded": len(IMAGE_FIXED_PLAYER_SYSTEMD_FILES),
        "totem_core_update_policy_source": str(profile_config["policy_file"]),
        "totem_core_update_timer_enabled": bool(profile_config["timer_enabled"]),
        "totem_core_embed_debugfs_output_lines": len(output.splitlines()),
        "totem_core_release_provenance": release_provenance,
        "totem_core_previous_release_provenance": previous_release_provenance,
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


def _dump_sha256(rootfs: Path, path: str) -> str:
    with tempfile.TemporaryDirectory(prefix="totem-core-hash-") as tmp:
        out_path = Path(tmp) / "dump.bin"
        base.debugfs(rootfs, f"dump {path} {out_path}")
        if not out_path.is_file():
            return ""
        return base.file_sha256(out_path)


def _symlink_target(rootfs: Path, path: str) -> str:
    out = base.debugfs(rootfs, f"stat {path}")
    if "File not found" in out or "couldn't" in out.lower() or "no such" in out.lower():
        return ""
    for pattern in (r"Fast link dest:\s*(.+)", r"link:\s*(.+)"):
        match = re.search(pattern, out)
        if match:
            return match.group(1).strip().strip('"')
    # ext4 stores longer symlink values in a data block instead of the inode's
    # fast-link field. debugfs `dump` reads both representations faithfully.
    return _dump_text(rootfs, path).strip()


def validate_totem_core_embed(rootfs: Path, *, profile: str = "homologation") -> dict[str, Any]:
    """Return an offline validation bundle for the totem-core image layout."""
    profile_config = resolve_totem_core_embed_profile(profile)
    repo_root = Path(__file__).resolve().parents[2]
    current_release_provenance, current_payload_files = _validate_totem_core_release(
        repo_root,
        CORE_FILES,
        version=TOTEM_CORE_VERSION,
        channel=TOTEM_CORE_CHANNEL,
        source_commit=TOTEM_CORE_SOURCE_COMMIT,
        payload_sha256=TOTEM_CORE_PAYLOAD_SHA256,
        created_at_utc=TOTEM_CORE_CREATED_AT_UTC,
        capabilities=TOTEM_CORE_CAPABILITIES,
        require_worktree_exact=True,
    )
    previous_core_files = [
        core_file for core_file in CORE_FILES if core_file not in TOTEM_CORE_PREVIOUS_EXCLUDED_FILES
    ]
    previous_release_provenance, previous_payload_files = _validate_totem_core_release(
        repo_root,
        previous_core_files,
        version=TOTEM_CORE_PREVIOUS_VERSION,
        channel=TOTEM_CORE_PREVIOUS_CHANNEL,
        source_commit=TOTEM_CORE_PREVIOUS_SOURCE_COMMIT,
        payload_sha256=TOTEM_CORE_PREVIOUS_PAYLOAD_SHA256,
        created_at_utc=TOTEM_CORE_PREVIOUS_CREATED_AT_UTC,
        capabilities=TOTEM_CORE_PREVIOUS_CAPABILITIES,
        require_worktree_exact=False,
    )
    expected_player_runtime_auth: dict[str, Any] = {}
    expected_auth_path = _profile_authorization_path(profile_config, repo_root)
    if profile == "production":
        if expected_auth_path is not None:
            try:
                expected_player_runtime_auth = load_player_runtime_production_authorization(expected_auth_path)
            except RuntimeError:
                expected_player_runtime_auth = {}
    release_root = f"/data/core/totem/releases/{TOTEM_CORE_VERSION}"
    previous_release_root = f"/data/core/totem/releases/{TOTEM_CORE_PREVIOUS_VERSION}"
    state = _dump_text(rootfs, "/data/core/totem/state.json")
    try:
        state_data = json.loads(state)
    except json.JSONDecodeError:
        state_data = {}
    updatectl = base.cat_file(rootfs, "/opt/totem/bin/totem-updatectl") or ""
    splash_service = base.cat_file(rootfs, "/etc/systemd/system/dadooh-visual-splash.service") or ""
    update_agent_service = _dump_text(rootfs, UPDATE_AGENT_SERVICE_TARGET)
    player_service_launcher = _dump_text(rootfs, "/opt/totem/bin/kiosky_service_launcher.sh")
    player_dropin = _dump_text(rootfs, "/etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf")
    player_runtime_auth_text = _dump_text(rootfs, PLAYER_RUNTIME_AUTH_TARGET)
    player_runtime_service = _dump_text(rootfs, PLAYER_RUNTIME_UPDATE_AGENT_SERVICE_TARGET)
    firstboot_unit = _dump_text(rootfs, FIRSTBOOT_GATE_SERVICE_TARGET)
    firstboot_wants_target = _symlink_target(rootfs, FIRSTBOOT_GATE_SERVICE_WANTS)
    product_reset_gc_unit = _dump_text(rootfs, PRODUCT_RESET_GC_SERVICE_TARGET)
    expected_product_reset_gc_unit = (
        repo_root / "scripts" / "board" / "totem-product-reset-gc.service"
    ).read_text(encoding="utf-8")
    expected_player_dropin = (
        repo_root
        / "scripts"
        / "board"
        / "systemd"
        / "kiosky-player.service.d"
        / "20-dadooh-launcher.conf"
    ).read_text(encoding="utf-8")
    player_dropin_wants_gc = "Wants=totem-product-reset-gc.service" in player_dropin
    health_text = _dump_text(rootfs, f"{release_root}/health/totem-core-health.json")
    previous_health_text = _dump_text(
        rootfs,
        f"{previous_release_root}/health/totem-core-health.json",
    )
    policy_text = _dump_text(rootfs, UPDATE_POLICY_TARGET)
    try:
        update_policy = json.loads(policy_text)
    except json.JSONDecodeError:
        update_policy = {}
    try:
        player_runtime_auth = json.loads(player_runtime_auth_text)
    except json.JSONDecodeError:
        player_runtime_auth = {}
    try:
        embedded_health = json.loads(health_text)
    except json.JSONDecodeError:
        embedded_health = {}
    try:
        embedded_previous_health = json.loads(previous_health_text)
    except json.JSONDecodeError:
        embedded_previous_health = {}
    policy_stat = base.stat_file(rootfs, UPDATE_POLICY_TARGET)
    product_reset_gc_unit_stat = base.stat_file(rootfs, PRODUCT_RESET_GC_SERVICE_TARGET)
    player_dropin_stat = base.stat_file(
        rootfs,
        "/etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf",
    )
    current_target = _symlink_target(rootfs, "/data/core/totem/current")
    previous_target = _symlink_target(rootfs, "/data/core/totem/previous")
    timer_enabled = bool(base.stat_file(rootfs, UPDATE_AGENT_TIMER_WANTS).get("present", False))
    player_runtime_timer_enabled = bool(
        base.stat_file(rootfs, PLAYER_RUNTIME_UPDATE_AGENT_TIMER_WANTS).get("present", False)
    )
    expected_current_state = {
        "version": TOTEM_CORE_VERSION,
        "channel": TOTEM_CORE_CHANNEL,
        "path": f"releases/{TOTEM_CORE_VERSION}",
        "source": "image_embed",
        "source_repo": "dadoohai/orange_pi_totem",
        "source_branch": "foundation-v0.1",
        "source_commit": TOTEM_CORE_SOURCE_COMMIT,
        "payload_sha256": TOTEM_CORE_PAYLOAD_SHA256,
        "manifest_created_at_utc": TOTEM_CORE_CREATED_AT_UTC,
    }
    expected_previous_state = {
        "version": TOTEM_CORE_PREVIOUS_VERSION,
        "channel": TOTEM_CORE_PREVIOUS_CHANNEL,
        "path": f"releases/{TOTEM_CORE_PREVIOUS_VERSION}",
        "source": "image_embed_previous",
        "source_repo": "dadoohai/orange_pi_totem",
        "source_branch": "foundation-v0.1",
        "source_commit": TOTEM_CORE_PREVIOUS_SOURCE_COMMIT,
        "payload_sha256": TOTEM_CORE_PREVIOUS_PAYLOAD_SHA256,
        "manifest_created_at_utc": TOTEM_CORE_PREVIOUS_CREATED_AT_UTC,
    }

    checks: dict[str, bool] = {
        "totem_core_slots_versions_distinct": TOTEM_CORE_VERSION != TOTEM_CORE_PREVIOUS_VERSION,
        "totem_core_slots_payloads_distinct": (
            current_release_provenance["payload_sha256"]
            != previous_release_provenance["payload_sha256"]
        ),
        "totem_core_current_symlink_present": _is_symlink(rootfs, "/data/core/totem/current"),
        "totem_core_current_symlink_target_exact": current_target == f"releases/{TOTEM_CORE_VERSION}",
        "totem_core_previous_symlink_present": _is_symlink(rootfs, "/data/core/totem/previous"),
        "totem_core_previous_symlink_target_exact": (
            previous_target == f"releases/{TOTEM_CORE_PREVIOUS_VERSION}"
        ),
        "totem_core_state_present": _is_file(rootfs, "/data/core/totem/state.json"),
        "totem_core_state_current_exact": state_data.get("current") == expected_current_state,
        "totem_core_state_previous_exact": state_data.get("previous") == expected_previous_state,
        "totem_core_state_records_current_version": TOTEM_CORE_VERSION in state,
        "totem_core_state_records_current_channel": f'"channel": "{TOTEM_CORE_CHANNEL}"' in state,
        "totem_core_state_records_created_at": TOTEM_CORE_CREATED_AT_UTC in state,
        "totem_core_state_records_source_commit": TOTEM_CORE_SOURCE_COMMIT in state,
        "totem_core_state_records_payload_sha256": TOTEM_CORE_PAYLOAD_SHA256 in state,
        "totem_core_release_health_present": _is_file(rootfs, f"{release_root}/health/totem-core-health.json"),
        "totem_core_previous_release_health_present": _is_file(
            rootfs,
            f"{previous_release_root}/health/totem-core-health.json",
        ),
        "totem_core_release_health_capabilities_exact": (
            embedded_health.get("capabilities") == list(TOTEM_CORE_CAPABILITIES)
        ),
        "totem_core_previous_release_health_capabilities_exact": (
            embedded_previous_health.get("capabilities")
            == list(TOTEM_CORE_PREVIOUS_CAPABILITIES)
        ),
        "totem_core_release_health_payload_exact": (
            _dump_sha256(rootfs, f"{release_root}/health/totem-core-health.json")
            == hashlib.sha256(current_payload_files["health/totem-core-health.json"]).hexdigest()
        ),
        "totem_core_previous_release_health_payload_exact": (
            _dump_sha256(rootfs, f"{previous_release_root}/health/totem-core-health.json")
            == hashlib.sha256(previous_payload_files["health/totem-core-health.json"]).hexdigest()
        ),
        "totem_core_release_health_has_c26_companion_tests": {
            "python3 bin/totem_config_writer_real.py --self-test",
            "python3 bin/totem_settings_trigger.py --self-test",
            "bash bin/totem_firstboot_gate.sh --self-test",
            "bash bin/totem_open_settings_cleanup.sh --self-test",
        }
        <= set(embedded_health.get("self_tests") or []),
        "totem_core_release_fragment_present": _is_file(rootfs, f"{release_root}/manifest-fragment/totem-core.json"),
        "totem_core_previous_release_fragment_present": _is_file(
            rootfs,
            f"{previous_release_root}/manifest-fragment/totem-core.json",
        ),
        "totem_core_release_fragment_payload_exact": (
            _dump_sha256(rootfs, f"{release_root}/manifest-fragment/totem-core.json")
            == hashlib.sha256(current_payload_files["manifest-fragment/totem-core.json"]).hexdigest()
        ),
        "totem_core_previous_release_fragment_payload_exact": (
            _dump_sha256(rootfs, f"{previous_release_root}/manifest-fragment/totem-core.json")
            == hashlib.sha256(previous_payload_files["manifest-fragment/totem-core.json"]).hexdigest()
        ),
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
        "firstboot_gate_unit_orders_before_both_ota_agents": (
            "Before=" in firstboot_unit
            and "totem-update-agent.service" in firstboot_unit
            and "totem-player-runtime-update-agent.service" in firstboot_unit
        ),
        "firstboot_gate_enabled_symlink_present": _is_symlink(rootfs, FIRSTBOOT_GATE_SERVICE_WANTS),
        "firstboot_gate_enabled_symlink_target_exact": (
            firstboot_wants_target == FIRSTBOOT_GATE_SERVICE_TARGET
        ),
        "product_reset_gc_unit_deferred_after_player": (
            "After=kiosky-player.service" in product_reset_gc_unit
            and "ConditionPathExists=/data/state/totem-appliance/product-reset/gc-pending.json"
            in product_reset_gc_unit
            and "IOSchedulingClass=best-effort" in product_reset_gc_unit
            and "IOSchedulingPriority=7" in product_reset_gc_unit
            and "--confirm-product-reset-background-gc" in product_reset_gc_unit
        ),
        "product_reset_gc_unit_installed_exact": (
            product_reset_gc_unit == expected_product_reset_gc_unit
            and int(product_reset_gc_unit_stat.get("mode", 0)) == 0o644
            and product_reset_gc_unit_stat.get("uid") == 0
            and product_reset_gc_unit_stat.get("gid") == 0
        ),
        "product_reset_gc_unit_static": "[Install]" not in product_reset_gc_unit,
        "product_reset_gc_player_dropin_installed_exact": (
            player_dropin == expected_player_dropin
            and int(player_dropin_stat.get("mode", 0)) == 0o644
            and player_dropin_stat.get("uid") == 0
            and player_dropin_stat.get("gid") == 0
        ),
        "product_reset_gc_pulled_by_player": player_dropin_wants_gc,
        "totem_core_update_timer_unit_present": _is_file(rootfs, UPDATE_AGENT_TIMER_TARGET),
        "totem_core_update_timer_matches_profile": timer_enabled is bool(profile_config["timer_enabled"]),
        "totem_core_update_policy_matches_profile": (
            (
                update_policy.get("device_channel") == "stable"
                and update_policy.get("allow_prerelease") is False
            )
            if profile == "production"
            else update_policy.get("device_channel") in {"lab", "homologation"}
        ),
        "player_runtime_authorization_matches_profile": (
            _player_runtime_authorization_matches_expected(
                player_runtime_auth,
                expected_player_runtime_auth,
            )
            if profile == "production"
            else not _is_file(rootfs, PLAYER_RUNTIME_AUTH_TARGET)
        ),
        "player_runtime_update_agent_service_matches_profile": (
            (
                "apply-player-runtime-authorized" in player_runtime_service
                and PLAYER_RUNTIME_AUTH_TARGET in player_runtime_service
                and "--startup-wait-sec 8" in player_runtime_service
                and "apply-github-latest" not in player_runtime_service
            )
            if profile == "production"
            else not _is_file(rootfs, PLAYER_RUNTIME_UPDATE_AGENT_SERVICE_TARGET)
        ),
        "player_runtime_update_timer_matches_profile": (
            player_runtime_timer_enabled is bool(profile_config["player_runtime_timer_enabled"])
        ),
        "image_fixed_player_dropin_present": _is_file(
            rootfs, "/etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf"
        ),
        "image_fixed_player_dropin_reconciles_player_runtime": (
            "C18_PLAYER_RUNTIME_RECONCILE=1" in player_dropin
            and "--allow-player-runtime-maintenance" in player_dropin
            and "reconcile --component player-runtime" in player_dropin
            and "ExecStartPre=-+/usr/bin/env C18_PLAYER_RUNTIME_RECONCILE=1" in player_dropin
            and "prefixed with `+`" in player_dropin
            and "while reconcile must manage /data/player-runtime" in player_dropin
            and "root-owned state" in player_dropin
            and "RequiresMountsFor=/data" in player_dropin
            and "After=local-fs.target" in player_dropin
            and "KillMode=mixed" in player_dropin
            and "TimeoutStopSec=90s" in player_dropin
            and "SendSIGKILL=yes" in player_dropin
            and "mpv to quit over IPC before falling back" in player_dropin
            and "KillMode=control-group" not in player_dropin
            and "ExecStartPre=-/usr/bin/env C18_PLAYER_RUNTIME_RECONCILE=1" not in player_dropin
        ),
        "image_fixed_player_dropin_routes_through_totem_launcher": (
            "ExecStart=/usr/bin/env bash /opt/totem/bin/totem-kiosky-launcher.sh" in player_dropin
        ),
        "image_fixed_player_launcher_waits_for_child_shutdown": (
            "wait_child_after_stop()" in player_service_launcher
            and "shutdown_waiting_for_child" in player_service_launcher
            and "shutdown_child_exited" in player_service_launcher
            and 'wait_child_after_stop "$child_pid" "$rc"' in player_service_launcher
        ),
        "image_fixed_player_launcher_has_status_mpv_watchdog": (
            "TOTEM_PLAYER_STATUS_MPV_WATCHDOG" in player_service_launcher
            and "start_player_health_watchdog" in player_service_launcher
            and "status-mpv-watchdog.json" in player_service_launcher
        ),
    }
    if profile == "homologation":
        checks["totem_core_update_timer_disabled"] = not timer_enabled
        checks["player_runtime_production_canary_not_embedded"] = not _is_file(
            rootfs,
            PLAYER_RUNTIME_CANARY_TARGET,
        )
    elif profile == "production":
        checks["totem_core_update_timer_enabled"] = timer_enabled
        checks["player_runtime_production_canary_embedded"] = _is_file(
            rootfs,
            PLAYER_RUNTIME_CANARY_TARGET,
        )
    for core_file in CORE_FILES:
        checks[f"totem_core_release_{core_file}"] = _has_exec(rootfs, f"{release_root}/bin/{core_file}")
        checks[f"totem_core_previous_release_{core_file}"] = (
            _has_exec(rootfs, f"{previous_release_root}/bin/{core_file}")
            if core_file in previous_core_files
            else not _is_file(rootfs, f"{previous_release_root}/bin/{core_file}")
        )
        checks[f"totem_core_fallback_{core_file}"] = _has_exec(rootfs, f"/opt/totem/core-fallback/bin/{core_file}")
        source_sha = hashlib.sha256(current_payload_files[f"bin/{core_file}"]).hexdigest()
        checks[f"totem_core_release_{core_file}_source_exact"] = (
            _dump_sha256(rootfs, f"{release_root}/bin/{core_file}") == source_sha
        )
        if core_file in previous_core_files:
            previous_source_sha = hashlib.sha256(
                previous_payload_files[f"bin/{core_file}"]
            ).hexdigest()
            checks[f"totem_core_previous_release_{core_file}_source_exact"] = (
                _dump_sha256(rootfs, f"{previous_release_root}/bin/{core_file}")
                == previous_source_sha
            )
        checks[f"totem_core_fallback_{core_file}_source_exact"] = (
            _dump_sha256(rootfs, f"/opt/totem/core-fallback/bin/{core_file}") == source_sha
        )
        wrapper = base.cat_file(rootfs, f"/opt/totem/bin/{core_file}") or ""
        checks[f"totem_core_wrapper_{core_file}"] = "TOTEM_CORE_EXEC_WRAPPER" in wrapper
    for player_file in IMAGE_FIXED_PLAYER_FILES:
        wrapper = base.cat_file(rootfs, f"/opt/totem/bin/{player_file}") or ""
        checks[f"image_fixed_player_{player_file}"] = _has_exec(rootfs, f"/opt/totem/bin/{player_file}")
        checks[f"image_fixed_player_{player_file}_source_exact"] = (
            _dump_sha256(rootfs, f"/opt/totem/bin/{player_file}")
            == base.file_sha256(repo_root / "scripts" / "board" / player_file)
        )
        checks[f"image_fixed_player_{player_file}_not_totem_core_wrapper"] = "TOTEM_CORE_EXEC_WRAPPER" not in wrapper
        checks[f"totem_core_release_excludes_{player_file}"] = not _is_file(rootfs, f"{release_root}/bin/{player_file}")
    for source_rel, target in IMAGE_FIXED_PLAYER_SYSTEMD_FILES:
        checks[f"image_fixed_player_systemd_{Path(source_rel).name}_source_exact"] = (
            _dump_sha256(rootfs, target)
            == base.file_sha256(repo_root / "scripts" / "board" / source_rel)
        )
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "totem_core_embed_profile": profile,
        "totem_core_current_version": TOTEM_CORE_VERSION,
        "totem_core_previous_version": TOTEM_CORE_PREVIOUS_VERSION,
    }
