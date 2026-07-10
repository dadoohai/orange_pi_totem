#!/usr/bin/env python3
"""Validate C18 player-runtime production auto-pull board evidence.

Offline-only gate. It consumes five collector snapshots plus the exact
authorization, manifest, payload, and release-gate artifacts. The final restored
snapshot must include a continuous playback window long enough to cover delayed
failures. It does not fetch GitHub, mutate policy/timers, apply player-runtime,
rollback, or restart the player service. It detects omitted or internally
inconsistent evidence; without device attestation it cannot make coherently
fabricated artifacts tamper-proof.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import c18_player_runtime_production_autopull_authorization_gate as authorization_gate  # noqa: E402


COLLECT_SCHEMA = "dadooh.c18.player_runtime.production_autopull_collect.v1"
GATE_SCHEMA = "dadooh.c18.player_runtime.production_autopull_evidence_gate.v2"
AUTH_SCHEMA = "dadooh.c18.player_runtime.production_autopull_authorization.v1"
MANIFEST_SCHEMA = "dadooh.totem.update.v1"
RELEASE_GATE_SCHEMA = "dadooh.c18.player_runtime.release_gate.v1"
PUBLICATION_SCHEMA = "dadooh.c18.player_runtime.exact_target_publication_result.v1"
COMPONENT = "player-runtime"
CHANNEL = "homologation"
DEVICE_TRACK = "c18-hwdecode"
PRODUCTION_REPO = "dadoohai/orange_pi_totem"
DEFAULT_EXPECTED_IMAGE_TAG = "c18-hwdecode-prod-7"
DEFAULT_EXPECTED_IMAGE_VERSION = "c18.image-prod.7"
DEFAULT_EXPECTED_UPDATER_SHA256 = hashlib.sha256(
    (REPO_ROOT / "scripts" / "board" / "totem_updatectl.py").read_bytes()
).hexdigest()
DEFAULT_TARGET_VERSION = "c18.player-runtime-homolog-20260710-c22-c023eae"
DEFAULT_BASELINE_VERSION = "c18.player-runtime-homolog-20260703-baseline-bridge-8ac1c63"
DEFAULT_ROLLBACK_REASON = "production_authorized_rollback"
DEFAULT_MIN_CONTINUOUS_RESTORED_SEC = 600.0
PHASES = ("pre", "post_apply", "noop", "rollback", "restored")
REQUIRED_NON_CLAIMS = (
    "this_gate_does_not_fetch_github",
    "this_gate_does_not_apply_player_runtime",
    "this_gate_does_not_rollback_player_runtime",
    "this_gate_does_not_modify_device_policy_or_timer",
    "this_gate_does_not_restart_services",
    "this_gate_does_not_provide_device_attestation_or_tamper_proof_evidence",
)
PLAYER_RUNTIME_APPLY_SUCCESS_JOURNAL_TOKENS = (
    "apply_success",
    "player_runtime_post_promotion_service_restart",
)
REQUIRED_PUBLICATION_NON_CLAIMS = {
    "this_route_does_not_promote_stable",
    "this_route_does_not_update_latest",
    "this_route_does_not_create_or_push_tags",
    "this_route_does_not_publish_extra_assets",
    "this_route_does_not_enable_broad_latest_autopull",
    "this_route_does_not_create_draft_or_prerelease",
}
REQUIRED_HEALTH_ARTIFACTS = {
    "deep-health-kernel.json",
    "deep-health-player-counters.json",
    "deep-health-process.json",
    "deep-health-systemd.json",
    "deep-health-watchdog.json",
    "playback-deep-health-public.json",
    "playback-samples.tsv",
    "status-samples.ndjson",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_HEALTH_CHECKS = (
    "samples_present",
    "service_active",
    "single_mpv",
    "mpv_path_c18_stack",
    "hwdec_expected_present",
    "hwdec_no_unexpected",
    "vo_configured_present",
    "vo_configured_no_unexpected",
    "ipc_success_present",
    "ipc_stable_after_success",
    "estimated_frame_present",
    "playback_progressed",
    "media_load_failed_present",
    "media_load_failed_zero",
    "mpv_restart_present",
    "mpv_restart_zero",
    "panfrost_faults_present",
    "panfrost_faults_zero",
    "panfrost_faults_delta_zero",
    "mmc_timeout_reset_present",
    "mmc_timeout_reset_zero",
    "ext4_errors_present",
    "ext4_errors_zero",
    "nrestarts_delta_present",
    "nrestarts_stable",
    "status_no_failures",
)
CONTINUOUS_ZERO_COUNTERS = (
    "media_load_failed",
    "mpv_restart",
    "nrestarts_delta",
    "ipc_timeout_after_first_success",
    "ipc_error_after_first_success",
    "panfrost_faults_delta",
    "mmc_timeout_reset_delta",
    "ext4_errors_delta",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json_sha256(data: dict[str, Any]) -> str:
    return sha256_text(json.dumps(data, sort_keys=True, separators=(",", ":")))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def is_git_sha(value: Any) -> bool:
    return isinstance(value, str) and GIT_SHA_RE.fullmatch(value) is not None


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def str_field(value: Any) -> str:
    return value if isinstance(value, str) else ""


def truthy_marker(value: Any) -> bool:
    return value in (True, "true", "True", "1", 1)


def false_or_absent(value: Any) -> bool:
    return value in (None, "", False, "false", "False", "0", 0)


def basename_version(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value.rstrip("/").rsplit("/", 1)[-1]


def require_regular_file(path: Path | None, blockers: list[str], label: str) -> bool:
    if path is None:
        blockers.append(f"{label}_missing")
        return False
    if path.is_symlink() or not path.is_file():
        blockers.append(f"{label}_missing_or_symlink")
        return False
    return True


def load_json_path(path: Path | None, blockers: list[str], label: str) -> dict[str, Any]:
    if not require_regular_file(path, blockers, label):
        return {}
    assert path is not None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append(f"{label}_json_error:{type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        blockers.append(f"{label}_not_object")
        return {}
    return data


def load_snapshot(path: Path | None, blockers: list[str], phase: str) -> dict[str, Any]:
    data = load_json_path(path, blockers, f"{phase}_snapshot")
    if not data:
        blockers.append(f"{phase}_snapshot_empty_or_unavailable")
        return {}
    if data.get("schema") != COLLECT_SCHEMA:
        blockers.append(f"{phase}_snapshot_schema")
    if data.get("phase") != phase:
        blockers.append(f"{phase}_snapshot_phase")
    if path is not None:
        data["_evidence_path"] = str(path)
    return data


def parse_utc(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        return dt.datetime.fromisoformat(value[:-1] + "+00:00").astimezone(dt.timezone.utc)
    except ValueError:
        return None


def phase_label(snapshot: dict[str, Any], fallback: str) -> str:
    return str(snapshot.get("phase") or fallback)


def state_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    return as_dict(as_dict(snapshot.get("state")).get("summary"))


def state_file_data(snapshot: dict[str, Any]) -> dict[str, Any]:
    return as_dict(as_dict(as_dict(snapshot.get("state")).get("state_file")).get("data"))


def state_entry(snapshot: dict[str, Any], key: str) -> dict[str, Any]:
    summary = state_summary(snapshot)
    entry = summary.get(key)
    if isinstance(entry, dict):
        return entry
    data = state_file_data(snapshot)
    return as_dict(data.get(key))


def link_target(snapshot: dict[str, Any], key: str) -> str:
    link = as_dict(as_dict(snapshot.get("state")).get(f"{key}_symlink"))
    return str_field(link.get("target"))


def entry_or_link_version(snapshot: dict[str, Any], key: str) -> str | None:
    entry_version = state_entry(snapshot, key).get("version")
    if isinstance(entry_version, str) and entry_version:
        return entry_version
    return basename_version(link_target(snapshot, key))


def current_version(snapshot: dict[str, Any]) -> str | None:
    return entry_or_link_version(snapshot, "current")


def previous_version(snapshot: dict[str, Any]) -> str | None:
    return entry_or_link_version(snapshot, "previous")


def current_marker(snapshot: dict[str, Any]) -> dict[str, Any]:
    return as_dict(as_dict(as_dict(snapshot.get("state")).get("current_release_marker")).get("data"))


def current_marker_sha(snapshot: dict[str, Any]) -> str | None:
    marker = as_dict(as_dict(snapshot.get("state")).get("current_release_marker"))
    value = marker.get("sha256")
    return value if isinstance(value, str) else None


def current_or_previous_mentions(snapshot: dict[str, Any], version: str) -> bool:
    versions = {current_version(snapshot), previous_version(snapshot)}
    links = {link_target(snapshot, "current"), link_target(snapshot, "previous")}
    if version in versions:
        return True
    return any(isinstance(link, str) and basename_version(link) == version for link in links)


def validate_state_consistency(snapshot: dict[str, Any], phase: str, blockers: list[str]) -> None:
    summary = state_summary(snapshot)
    state_file = as_dict(as_dict(snapshot.get("state")).get("state_file"))
    state_data = state_file_data(snapshot)
    if state_file.get("exists") is not True or state_file.get("is_file") is not True:
        blockers.append(f"{phase}_state_file_not_regular")
    if state_file.get("is_symlink") is not False:
        blockers.append(f"{phase}_state_file_symlink_or_unknown")
    if not is_sha256(state_file.get("sha256")):
        blockers.append(f"{phase}_state_file_sha256_invalid")
    if state_file.get("json_error") is not None:
        blockers.append(f"{phase}_state_file_json_error")
    if not state_data:
        blockers.append(f"{phase}_state_file_data_missing")
        return
    if state_file.get("canonical_json_sha256") != canonical_json_sha256(state_data):
        blockers.append(f"{phase}_state_file_data_hash_mismatch")
    for key in ("current", "previous", "last_operation"):
        if summary.get(key) != state_data.get(key):
            blockers.append(f"{phase}_state_summary_{key}_mismatch")
    if as_list(summary.get("quarantine")) != as_list(state_data.get("quarantine")):
        blockers.append(f"{phase}_state_summary_quarantine_mismatch")
    for key in ("current", "previous"):
        entry = summary.get(key)
        entry_version = entry.get("version") if isinstance(entry, dict) else None
        link_version = basename_version(link_target(snapshot, key))
        if entry_version != link_version:
            blockers.append(f"{phase}_{key}_state_symlink_mismatch")
    marker = current_marker(snapshot)
    if marker and marker.get("version") != current_version(snapshot):
        blockers.append(f"{phase}_current_marker_state_mismatch")


def validate_phase_order(snapshots: dict[str, dict[str, Any]], blockers: list[str]) -> None:
    previous: dt.datetime | None = None
    for phase in PHASES:
        value = parse_utc(snapshots[phase].get("collected_at_utc"))
        if value is None:
            blockers.append(f"{phase}_collected_at_utc_invalid")
            continue
        if previous is not None and value <= previous:
            blockers.append(f"{phase}_collected_at_not_after_previous_phase")
        previous = value


def journal_text(snapshot: dict[str, Any]) -> str:
    parts: list[str] = []
    systemd = as_dict(snapshot.get("systemd"))
    for unit_name in ("service", "timer", "player"):
        journal = as_dict(as_dict(systemd.get(unit_name)).get("journal"))
        parts.extend(str(item) for item in as_list(journal.get("lines")))
    return "\n".join(parts)


def validate_manifest_payload_release_gate(
    *,
    manifest_path: Path | None,
    payload_path: Path | None,
    release_gate_path: Path | None,
    target_version: str,
    blockers: list[str],
) -> dict[str, Any]:
    manifest = load_json_path(manifest_path, blockers, "manifest")
    release_gate = load_json_path(release_gate_path, blockers, "release_gate")
    if not require_regular_file(payload_path, blockers, "payload"):
        payload_sha = ""
        payload_bytes = 0
    else:
        assert payload_path is not None
        payload_sha = sha256_file(payload_path)
        payload_bytes = payload_path.stat().st_size

    if manifest.get("schema") != MANIFEST_SCHEMA:
        blockers.append("manifest_schema")
    if manifest.get("component") != COMPONENT:
        blockers.append("manifest_component_not_player_runtime")
    if manifest.get("channel") != CHANNEL:
        blockers.append("manifest_channel_not_homologation")
    if manifest.get("version") != target_version:
        blockers.append("manifest_target_version_mismatch")
    if manifest.get("payload") != (payload_path.name if payload_path is not None else None):
        blockers.append("manifest_payload_name_mismatch")
    if manifest.get("payload_sha256") != payload_sha:
        blockers.append("manifest_payload_sha256_mismatch")
    if not is_git_sha(manifest.get("source_commit")):
        blockers.append("manifest_source_commit_missing_or_invalid")
    if manifest.get("source_dirty") is not False:
        blockers.append("manifest_source_dirty_not_false")
    requires = as_dict(manifest.get("requires"))
    if requires.get("device_track") != DEVICE_TRACK:
        blockers.append("manifest_device_track_mismatch")
    if requires.get("hwdec") != "v4l2request-copy":
        blockers.append("manifest_hwdec_mismatch")

    if release_gate.get("schema") != RELEASE_GATE_SCHEMA:
        blockers.append("release_gate_schema")
    if release_gate.get("passed") is not True:
        blockers.append("release_gate_not_passed")
    if release_gate.get("component") != COMPONENT:
        blockers.append("release_gate_component_not_player_runtime")
    package = as_dict(release_gate.get("package"))
    gate_manifest = as_dict(release_gate.get("manifest"))
    gate_payload = as_dict(release_gate.get("payload"))
    if package.get("manifest") != (manifest_path.name if manifest_path is not None else None):
        blockers.append("release_gate_manifest_name_mismatch")
    if package.get("payload") != (payload_path.name if payload_path is not None else None):
        blockers.append("release_gate_payload_name_mismatch")
    if package.get("payload_sha256") != manifest.get("payload_sha256"):
        blockers.append("release_gate_payload_sha256_mismatch")
    if package.get("source_commit") != manifest.get("source_commit"):
        blockers.append("release_gate_source_commit_mismatch")
    if package.get("channel") != CHANNEL:
        blockers.append("release_gate_channel_not_homologation")
    if gate_manifest.get("version") != target_version:
        blockers.append("release_gate_manifest_version_mismatch")
    if gate_manifest.get("payload_sha256") != manifest.get("payload_sha256"):
        blockers.append("release_gate_manifest_payload_sha256_mismatch")
    if gate_manifest.get("source_commit") != manifest.get("source_commit"):
        blockers.append("release_gate_manifest_source_commit_mismatch")
    if not is_sha256(gate_payload.get("tree_sha256")):
        blockers.append("release_gate_tree_sha256_missing_or_invalid")
    if not is_sha256(gate_payload.get("kiosk_py_sha256")):
        blockers.append("release_gate_kiosk_py_sha256_missing_or_invalid")

    return {
        "version": str(manifest.get("version") or target_version),
        "source_commit": str(manifest.get("source_commit") or ""),
        "source_repo": str(manifest.get("source_repo") or ""),
        "manifest_name": manifest_path.name if manifest_path is not None else "",
        "payload_name": payload_path.name if payload_path is not None else "",
        "release_gate_name": release_gate_path.name if release_gate_path is not None else "",
        "payload_sha256": str(manifest.get("payload_sha256") or payload_sha),
        "payload_bytes": payload_bytes,
        "manifest_sha256": sha256_file(manifest_path) if manifest_path is not None and manifest_path.is_file() else "",
        "release_gate_sha256": sha256_file(release_gate_path) if release_gate_path is not None and release_gate_path.is_file() else "",
        "tree_sha256": str(gate_payload.get("tree_sha256") or ""),
        "kiosk_py_sha256": str(gate_payload.get("kiosk_py_sha256") or ""),
    }


def validate_authorization(
    auth_path: Path | None,
    *,
    target: dict[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    auth = load_json_path(auth_path, blockers, "authorization")
    if auth.get("schema") != AUTH_SCHEMA:
        blockers.append("authorization_schema")
    if auth.get("enabled") is not True:
        blockers.append("authorization_not_enabled")
    if auth.get("component") != COMPONENT:
        blockers.append("authorization_component_not_player_runtime")
    if auth.get("auto_pull_enabled") is not True:
        blockers.append("authorization_autopull_not_enabled")
    if auth.get("channel") != CHANNEL:
        blockers.append("authorization_channel_not_homologation")
    if auth.get("device_track") != DEVICE_TRACK:
        blockers.append("authorization_device_track_mismatch")
    for key in ("allow_latest", "allow_prerelease", "allow_downgrade"):
        if auth.get(key) is not False:
            blockers.append(f"authorization_{key}_not_false")
    if auth.get("version") != target.get("version"):
        blockers.append("authorization_version_target_mismatch")
    if auth.get("source_commit") != target.get("source_commit"):
        blockers.append("authorization_source_commit_target_mismatch")
    if auth.get("payload_sha256") != target.get("payload_sha256"):
        blockers.append("authorization_payload_sha256_target_mismatch")
    if auth.get("manifest_sha256") != target.get("manifest_sha256"):
        blockers.append("authorization_manifest_sha256_target_mismatch")
    if auth.get("release_gate_sha256") != target.get("release_gate_sha256"):
        blockers.append("authorization_release_gate_sha256_target_mismatch")
    if auth.get("repo") != PRODUCTION_REPO:
        blockers.append("authorization_repo_not_production_repo")
    tag = auth.get("tag_name")
    if not isinstance(tag, str) or target.get("version") not in tag:
        blockers.append("authorization_tag_not_bound_to_target")
    business = as_dict(auth.get("business_decision"))
    if business.get("risk_accepted") is not True:
        blockers.append("authorization_risk_not_accepted")
    non_claims = set(str(item) for item in as_list(auth.get("non_claims")))
    if "not_latest_broad" not in non_claims:
        blockers.append("authorization_missing_not_latest_non_claim")
    return auth


def validate_publication(
    publication_path: Path | None,
    *,
    target: dict[str, Any],
    authorization: dict[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    publication = load_json_path(publication_path, blockers, "publication_evidence")
    if publication.get("schema") != PUBLICATION_SCHEMA:
        blockers.append("publication_evidence_schema")
    if publication.get("passed") is not True or publication.get("published") is not True:
        blockers.append("publication_evidence_not_passed")
    required_remote_claims = {
        "mode": "publish",
        "would_publish": True,
        "manifest_channel": CHANNEL,
        "authorization_gate": "passed",
        "remote_source_commit_present": True,
        "remote_exact_tag_verified": True,
        "release_exists": True,
        "asset_count": 3,
    }
    for key, value in required_remote_claims.items():
        if publication.get(key) != value:
            blockers.append(f"publication_evidence_{key}_invalid")
    expected = {
        "repo": authorization.get("repo"),
        "tag": authorization.get("tag_name"),
        "version": target.get("version"),
        "target_source_commit": target.get("source_commit"),
    }
    for key, value in expected.items():
        if publication.get(key) != value:
            blockers.append(f"publication_evidence_{key}_mismatch")
    expected_release_url = (
        f"https://github.com/{authorization.get('repo')}/releases/tag/"
        f"{authorization.get('tag_name')}"
    )
    if publication.get("release_url") != expected_release_url:
        blockers.append("publication_evidence_release_url_mismatch")
    publication_non_claims = set(str(item) for item in as_list(publication.get("non_claims")))
    if publication_non_claims != REQUIRED_PUBLICATION_NON_CLAIMS:
        blockers.append("publication_evidence_non_claims_mismatch")
    latest_before = publication.get("latest_before")
    latest_after = publication.get("latest_after")
    if not isinstance(latest_before, str) or not latest_before:
        blockers.append("publication_evidence_latest_before_missing")
    if latest_after != latest_before:
        blockers.append("publication_evidence_latest_drift")
    assets = publication.get("assets")
    if not isinstance(assets, list) or len(assets) != 3:
        blockers.append("publication_evidence_assets_not_exact_three")
        assets = []
    actual_assets = {
        str(item.get("name")): str(item.get("sha256"))
        for item in assets
        if isinstance(item, dict)
    }
    expected_assets = {
        target.get("manifest_name"): target.get("manifest_sha256"),
        target.get("payload_name"): target.get("payload_sha256"),
        "c18-player-runtime-release-gate.json": target.get("release_gate_sha256"),
    }
    if actual_assets != expected_assets:
        blockers.append("publication_evidence_asset_hashes_mismatch")
    return publication


def validate_snapshot_common(
    snapshot: dict[str, Any],
    *,
    phase: str,
    expected_image_tag: str,
    expected_image_version: str,
    expected_updater_sha256: str,
    authorization_sha256: str,
    authorization_data: dict[str, Any],
    max_player_restarts: int,
    require_freeze_probe: bool,
    blockers: list[str],
) -> None:
    if not snapshot:
        return
    marker = as_dict(snapshot.get("image_marker"))
    marker_fields = as_dict(marker.get("fields"))
    if marker.get("exists") is not True:
        blockers.append(f"{phase}_production_image_marker_missing")
    if marker_fields.get("image_tag") != expected_image_tag:
        blockers.append(f"{phase}_production_image_tag_mismatch")
    if marker_fields.get("image_version") != expected_image_version:
        blockers.append(f"{phase}_production_image_version_mismatch")
    if not truthy_marker(marker_fields.get("final_image")):
        blockers.append(f"{phase}_production_marker_final_image_not_true")
    if marker_fields.get("artifact_private") not in ("false", False):
        blockers.append(f"{phase}_production_marker_artifact_private_not_false")
    if not false_or_absent(marker_fields.get("not_for_production")):
        blockers.append(f"{phase}_production_marker_not_for_production_true")
    if not false_or_absent(marker_fields.get("not_for_distribution")):
        blockers.append(f"{phase}_production_marker_not_for_distribution_true")

    updater = as_dict(snapshot.get("updater"))
    if updater.get("sha256") != expected_updater_sha256:
        blockers.append(f"{phase}_updater_sha256_mismatch")

    auth = as_dict(snapshot.get("authorization"))
    if auth.get("sha256") != authorization_sha256:
        blockers.append(f"{phase}_authorization_sha256_mismatch")
    if as_dict(auth.get("data")) != authorization_data:
        blockers.append(f"{phase}_authorization_data_mismatch")

    policy = as_dict(as_dict(snapshot.get("policy")).get("data"))
    if policy.get("schema") != "dadooh.totem.update.policy.v1":
        blockers.append(f"{phase}_policy_schema")
    if policy.get("device_channel") != "stable":
        blockers.append(f"{phase}_policy_channel_not_stable")
    if policy.get("device_track") != DEVICE_TRACK:
        blockers.append(f"{phase}_policy_track_mismatch")
    if policy.get("allowed_components") != ["totem-core"]:
        blockers.append(f"{phase}_policy_not_core_only")
    if policy.get("allow_prerelease") is not False:
        blockers.append(f"{phase}_policy_allow_prerelease_not_false")
    if policy.get("allow_downgrade") is not False:
        blockers.append(f"{phase}_policy_allow_downgrade_not_false")

    timer = as_dict(as_dict(snapshot.get("systemd")).get("timer"))
    if timer.get("enabled_raw") != "enabled":
        blockers.append(f"{phase}_timer_not_enabled")
    if timer.get("active_raw") != "active":
        blockers.append(f"{phase}_timer_not_active")

    player = as_dict(snapshot.get("player_service"))
    player_show = as_dict(player.get("show"))
    active = player.get("active_raw") or player_show.get("ActiveState")
    if active != "active":
        blockers.append(f"{phase}_player_service_not_active")
    try:
        restarts = int(player.get("nrestarts") if player.get("nrestarts") not in (None, "") else player_show.get("NRestarts"))
    except Exception:
        restarts = max_player_restarts + 1
    if restarts > max_player_restarts:
        blockers.append(f"{phase}_player_service_nrestarts_exceeded")

    freeze = as_dict(snapshot.get("freeze_probe"))
    if require_freeze_probe and freeze.get("ran") is not True:
        blockers.append(f"{phase}_freeze_probe_missing")
    if freeze.get("ran") is True and freeze.get("returncode") != 44:
        blockers.append(f"{phase}_freeze_probe_rc_not_44")


def timer_last_trigger(snapshot: dict[str, Any]) -> str:
    timer = as_dict(as_dict(snapshot.get("systemd")).get("timer"))
    return str_field(as_dict(timer.get("show")).get("LastTriggerUSec"))


def service_invocation(snapshot: dict[str, Any]) -> str:
    service = as_dict(as_dict(snapshot.get("systemd")).get("service"))
    return str_field(as_dict(service.get("show")).get("InvocationID"))


def validate_timer_execution(
    pre: dict[str, Any],
    post_apply: dict[str, Any],
    noop: dict[str, Any],
    authorization: dict[str, Any],
    blockers: list[str],
) -> None:
    pre_trigger = timer_last_trigger(pre)
    post_trigger = timer_last_trigger(post_apply)
    if not post_trigger or post_trigger in {"n/a", "0", "0us"}:
        blockers.append("post_apply_timer_last_trigger_missing")
    if post_trigger == pre_trigger:
        blockers.append("post_apply_timer_did_not_trigger_after_pre")
    service = as_dict(as_dict(post_apply.get("systemd")).get("service"))
    triggered_by = str_field(as_dict(service.get("show")).get("TriggeredBy"))
    if "totem-player-runtime-update-agent.timer" not in triggered_by:
        blockers.append("post_apply_service_not_bound_to_timer")
    pre_invocation = service_invocation(pre)
    post_invocation = service_invocation(post_apply)
    noop_invocation = service_invocation(noop)
    if not post_invocation or post_invocation == pre_invocation:
        blockers.append("post_apply_service_invocation_not_new")
    if not noop_invocation or noop_invocation == post_invocation:
        blockers.append("noop_service_invocation_not_new")
    post_journal = journal_text(post_apply)
    tag = str_field(authorization.get("tag_name"))
    if (
        not any(token in post_journal for token in PLAYER_RUNTIME_APPLY_SUCCESS_JOURNAL_TOKENS)
        or tag not in post_journal
    ):
        blockers.append("post_apply_timer_journal_missing_apply_success")


def validate_service_success(snapshot: dict[str, Any], phase: str, blockers: list[str]) -> None:
    service = as_dict(as_dict(snapshot.get("systemd")).get("service"))
    show = as_dict(service.get("show"))
    result = str_field(show.get("Result"))
    status = str_field(show.get("ExecMainStatus"))
    if result != "success":
        blockers.append(f"{phase}_timer_service_result_not_success")
    if status != "0":
        blockers.append(f"{phase}_timer_service_exec_status_not_zero")


def validate_authorized_rollback_activation(
    snapshot: dict[str, Any],
    phase: str,
    blockers: list[str],
) -> None:
    last = as_dict(state_summary(snapshot).get("last_operation") or state_file_data(snapshot).get("last_operation"))
    if last.get("type") != "rollback":
        blockers.append(f"{phase}_last_operation_type_not_rollback")
    if last.get("status") != "success":
        blockers.append(f"{phase}_last_operation_status_not_success")
    if last.get("service_restart_performed") is not True:
        blockers.append(f"{phase}_service_restart_not_recorded")
    if last.get("service_health_passed") is not True:
        blockers.append(f"{phase}_service_health_not_recorded")


def validate_health_green(snapshot: dict[str, Any], phase: str, blockers: list[str]) -> None:
    health_block = as_dict(snapshot.get("playback_deep_health"))
    if health_block.get("ran") is not True:
        blockers.append(f"{phase}_deep_health_not_collected")
        return
    if health_block.get("returncode") not in (0, None):
        blockers.append(f"{phase}_deep_health_collector_rc_nonzero")
    evidence_path = snapshot.get("_evidence_path")
    artifact_dir_name = health_block.get("artifact_dir_name")
    artifact_dir: Path | None = None
    if artifact_dir_name != f"{phase}-deep-health":
        blockers.append(f"{phase}_deep_health_artifact_dir_not_phase_bound")
    if (
        isinstance(evidence_path, str)
        and isinstance(artifact_dir_name, str)
        and artifact_dir_name
        and Path(artifact_dir_name).name == artifact_dir_name
    ):
        artifact_dir = Path(evidence_path).parent / artifact_dir_name
    else:
        blockers.append(f"{phase}_deep_health_artifact_dir_invalid")

    records = health_block.get("artifacts")
    record_map: dict[str, tuple[str, int]] = {}
    if not isinstance(records, list):
        blockers.append(f"{phase}_deep_health_artifact_records_missing")
    else:
        for item in records:
            if not isinstance(item, dict):
                blockers.append(f"{phase}_deep_health_artifact_record_invalid")
                continue
            name = item.get("name")
            sha = item.get("sha256")
            size = item.get("bytes")
            if (
                not isinstance(name, str)
                or not name
                or Path(name).name != name
                or not is_sha256(sha)
                or not isinstance(size, int)
                or size < 0
                or name in record_map
            ):
                blockers.append(f"{phase}_deep_health_artifact_record_invalid")
                continue
            record_map[name] = (sha, size)

    actual_map: dict[str, tuple[str, int]] = {}
    if artifact_dir is None or not artifact_dir.is_dir() or artifact_dir.is_symlink():
        blockers.append(f"{phase}_deep_health_artifact_dir_missing")
    else:
        for path in artifact_dir.iterdir():
            if path.is_symlink() or not path.is_file():
                blockers.append(f"{phase}_deep_health_artifact_not_regular:{path.name}")
                continue
            actual_map[path.name] = (sha256_file(path), path.stat().st_size)
    if record_map != actual_map:
        blockers.append(f"{phase}_deep_health_artifact_hashes_mismatch")

    for name in sorted(REQUIRED_HEALTH_ARTIFACTS - set(actual_map)):
        blockers.append(f"{phase}_deep_health_artifact_missing:{name}")

    health = as_dict(health_block.get("summary"))
    summary_path = artifact_dir / "playback-deep-health-public.json" if artifact_dir is not None else None
    summary_file: dict[str, Any] = {}
    if summary_path is not None and summary_path.is_file() and not summary_path.is_symlink():
        try:
            loaded = json.loads(summary_path.read_text(encoding="utf-8"))
            summary_file = loaded if isinstance(loaded, dict) else {}
        except Exception:
            summary_file = {}
    if summary_file != health:
        blockers.append(f"{phase}_deep_health_summary_file_mismatch")
    if summary_path is not None and summary_path.is_file():
        if health_block.get("summary_sha256") != sha256_file(summary_path):
            blockers.append(f"{phase}_deep_health_summary_sha256_mismatch")
    if health.get("schema") != "dadooh.c18.playback.deep_health.v1":
        blockers.append(f"{phase}_deep_health_schema")
    if health.get("passed") is not True:
        blockers.append(f"{phase}_deep_health_not_passed")
    if health.get("failure_reasons") not in ([], None):
        blockers.append(f"{phase}_deep_health_failure_reasons_not_empty")
    checks = as_dict(health.get("checks"))
    for check in REQUIRED_HEALTH_CHECKS:
        if checks.get(check) is not True:
            blockers.append(f"{phase}_deep_health_check_failed:{check}")
    counters = as_dict(health.get("counters"))
    try:
        samples = int(counters.get("samples") or 0)
    except Exception:
        samples = 0
    if samples <= 0:
        blockers.append(f"{phase}_deep_health_samples_empty")
    if artifact_dir is not None:
        sample_path = artifact_dir / "playback-samples.tsv"
        status_path = artifact_dir / "status-samples.ndjson"
        try:
            sample_lines = len(sample_path.read_text(encoding="utf-8").splitlines()) - 1
        except Exception:
            sample_lines = -1
        try:
            status_lines = len([line for line in status_path.read_text(encoding="utf-8").splitlines() if line])
        except Exception:
            status_lines = -1
        if sample_lines < samples or status_lines < samples:
            blockers.append(f"{phase}_deep_health_sample_artifacts_incomplete")
    try:
        positive_steps = int(counters.get("estimated_frame_positive_steps") or 0)
        required_steps = int(counters.get("estimated_frame_required_steps") or 2)
    except Exception:
        positive_steps = 0
        required_steps = 2
    if positive_steps < required_steps:
        blockers.append(f"{phase}_deep_health_frame_steps_insufficient")


def validate_continuous_restored_health(
    snapshot: dict[str, Any],
    min_duration_sec: float,
    blockers: list[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "min_duration_sec": min_duration_sec,
        "duration_sec": 0.0,
        "samples": 0,
        "started_at_utc": None,
        "finished_at_utc": None,
    }
    if min_duration_sec < 1.0:
        blockers.append("continuous_restored_min_duration_invalid")
        return result

    health_block = as_dict(snapshot.get("playback_deep_health"))
    evidence_path = snapshot.get("_evidence_path")
    artifact_name = health_block.get("artifact_dir_name")
    if (
        not isinstance(evidence_path, str)
        or not isinstance(artifact_name, str)
        or not artifact_name
        or Path(artifact_name).name != artifact_name
    ):
        blockers.append("continuous_restored_artifact_dir_invalid")
        return result
    artifact_dir = Path(evidence_path).parent / artifact_name
    watchdog_path = artifact_dir / "deep-health-watchdog.json"
    try:
        watchdog = json.loads(watchdog_path.read_text(encoding="utf-8"))
    except Exception:
        blockers.append("continuous_restored_watchdog_unavailable")
        return result
    if not isinstance(watchdog, dict):
        blockers.append("continuous_restored_watchdog_not_object")
        return result

    started = parse_utc(watchdog.get("collection_started_at_utc"))
    finished = parse_utc(watchdog.get("collection_finished_at_utc"))
    result["started_at_utc"] = watchdog.get("collection_started_at_utc")
    result["finished_at_utc"] = watchdog.get("collection_finished_at_utc")
    if started is None or finished is None or finished <= started:
        blockers.append("continuous_restored_window_invalid")
    else:
        duration_sec = (finished - started).total_seconds()
        result["duration_sec"] = duration_sec
        if duration_sec + 0.001 < min_duration_sec:
            blockers.append("continuous_restored_duration_too_short")
        collected = parse_utc(snapshot.get("collected_at_utc"))
        if collected is None or started < collected:
            blockers.append("continuous_restored_started_before_snapshot_collection")
        elif (started - collected).total_seconds() > 300:
            blockers.append("continuous_restored_started_too_late_after_snapshot_collection")
        last = as_dict(state_summary(snapshot).get("last_operation") or state_file_data(snapshot).get("last_operation"))
        operation_finished = parse_utc(last.get("finished_at_utc"))
        if operation_finished is None or started < operation_finished:
            blockers.append("continuous_restored_started_before_restore_finished")

    if watchdog.get("event_changed_during_window") is not False:
        blockers.append("continuous_restored_watchdog_event_changed")
    if str_field(watchdog.get("action_during_window")):
        blockers.append("continuous_restored_watchdog_action_present")

    health = as_dict(health_block.get("summary"))
    counters = as_dict(health.get("counters"))
    try:
        samples = int(counters.get("samples") or 0)
    except Exception:
        samples = 0
    result["samples"] = samples
    if samples < int(min_duration_sec * 0.9):
        blockers.append("continuous_restored_samples_too_few")
    for name in CONTINUOUS_ZERO_COUNTERS:
        value = counters.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != 0:
            blockers.append(f"continuous_restored_counter_not_zero:{name}")
    return result


def validate_distinct_health_evidence(
    snapshots: dict[str, dict[str, Any]],
    blockers: list[str],
) -> None:
    seen: dict[tuple[tuple[str, str, int], ...], str] = {}
    for phase in ("post_apply", "rollback", "restored"):
        health = as_dict(snapshots[phase].get("playback_deep_health"))
        fingerprint = tuple(sorted(
            (
                str(item.get("name")),
                str(item.get("sha256")),
                int(item.get("bytes")),
            )
            for item in as_list(health.get("artifacts"))
            if (
                isinstance(item, dict)
                and isinstance(item.get("name"), str)
                and isinstance(item.get("sha256"), str)
                and isinstance(item.get("bytes"), int)
            )
        ))
        if not fingerprint:
            continue
        if fingerprint in seen:
            blockers.append(f"{phase}_deep_health_artifacts_reused_from_{seen[fingerprint]}")
        else:
            seen[fingerprint] = phase


def validate_current_marker(snapshot: dict[str, Any], phase: str, target: dict[str, Any], blockers: list[str]) -> None:
    marker = current_marker(snapshot)
    if marker.get("schema") != "dadooh.c18.player_runtime.verified.v1":
        blockers.append(f"{phase}_current_marker_schema")
    if marker.get("verdict") != "verified":
        blockers.append(f"{phase}_current_marker_not_verified")
    if marker.get("version") != target.get("version"):
        blockers.append(f"{phase}_current_marker_version_mismatch")
    if marker.get("payload_sha256") != target.get("payload_sha256"):
        blockers.append(f"{phase}_current_marker_payload_sha256_mismatch")
    if marker.get("kiosk_py_sha256") != target.get("kiosk_py_sha256"):
        blockers.append(f"{phase}_current_marker_kiosk_sha256_mismatch")
    if marker.get("tree_sha256") != target.get("tree_sha256"):
        blockers.append(f"{phase}_current_marker_tree_sha256_mismatch")
    deep_health = as_dict(marker.get("deep_health"))
    if deep_health.get("passed") is not True:
        blockers.append(f"{phase}_current_marker_deep_health_not_passed")


def validate_pre(snapshot: dict[str, Any], *, baseline_version: str, target_version: str, blockers: list[str]) -> None:
    if current_version(snapshot) != baseline_version:
        blockers.append("pre_current_not_baseline_c21")
    if current_or_previous_mentions(snapshot, target_version):
        blockers.append("pre_target_c22_linked_before_apply")


def validate_post_apply(
    snapshot: dict[str, Any],
    *,
    baseline_version: str,
    target: dict[str, Any],
    authorization: dict[str, Any],
    blockers: list[str],
) -> None:
    if current_version(snapshot) != target.get("version"):
        blockers.append("post_apply_current_not_target_c22")
    if previous_version(snapshot) != baseline_version:
        blockers.append("post_apply_previous_not_baseline_c21")
    current = state_entry(snapshot, "current")
    if current.get("payload_sha256") != target.get("payload_sha256"):
        blockers.append("post_apply_current_payload_sha256_mismatch")
    source = str_field(current.get("source"))
    tag = str_field(authorization.get("tag_name"))
    expected_source = f"github-authorized:{authorization.get('repo')}:{tag}"
    if source != expected_source:
        blockers.append("post_apply_current_source_missing_github_tag")
    validate_current_marker(snapshot, "post_apply", target, blockers)
    validate_service_success(snapshot, "post_apply", blockers)
    validate_health_green(snapshot, "post_apply", blockers)


def mutation_fingerprint(snapshot: dict[str, Any]) -> dict[str, Any]:
    summary = state_summary(snapshot)
    state_file = as_dict(as_dict(snapshot.get("state")).get("state_file"))
    return {
        "current_symlink": link_target(snapshot, "current"),
        "previous_symlink": link_target(snapshot, "previous"),
        "state_current": summary.get("current"),
        "state_previous": summary.get("previous"),
        "state_quarantine": summary.get("quarantine"),
        "state_file_sha256": state_file.get("sha256"),
        "current_marker_sha256": current_marker_sha(snapshot),
    }


def release_identity(snapshot: dict[str, Any], key: str) -> dict[str, Any]:
    entry = state_entry(snapshot, key)
    return {
        field: entry.get(field)
        for field in ("version", "payload_sha256", "kiosk_py_sha256", "tree_sha256")
    }


def validate_new_operation_after_snapshot(
    snapshot: dict[str, Any],
    *,
    phase: str,
    previous_snapshot: dict[str, Any],
    disallowed_state_snapshots: tuple[dict[str, Any], ...],
    blockers: list[str],
) -> None:
    last = as_dict(state_summary(snapshot).get("last_operation"))
    previous_last = as_dict(state_summary(previous_snapshot).get("last_operation"))
    started = parse_utc(last.get("started_at_utc"))
    finished = parse_utc(last.get("finished_at_utc"))
    previous_collected = parse_utc(previous_snapshot.get("collected_at_utc"))
    collected = parse_utc(snapshot.get("collected_at_utc"))
    if started is None:
        blockers.append(f"{phase}_last_operation_started_at_invalid")
    if finished is None:
        blockers.append(f"{phase}_last_operation_finished_at_invalid")
    if started is not None and previous_collected is not None and started < previous_collected:
        blockers.append(f"{phase}_last_operation_started_before_previous_snapshot")
    if started is not None and finished is not None and finished < started:
        blockers.append(f"{phase}_last_operation_finished_before_start")
    if finished is not None and collected is not None and finished > collected:
        blockers.append(f"{phase}_last_operation_finished_after_snapshot")
    if last == previous_last:
        blockers.append(f"{phase}_last_operation_not_new")

    state_file = as_dict(as_dict(snapshot.get("state")).get("state_file"))
    state_sha = state_file.get("sha256")
    canonical_sha = state_file.get("canonical_json_sha256")
    for previous in disallowed_state_snapshots:
        previous_state = as_dict(as_dict(previous.get("state")).get("state_file"))
        if state_sha == previous_state.get("sha256"):
            blockers.append(f"{phase}_state_file_sha256_not_new")
            break
    for previous in disallowed_state_snapshots:
        previous_state = as_dict(as_dict(previous.get("state")).get("state_file"))
        if canonical_sha == previous_state.get("canonical_json_sha256"):
            blockers.append(f"{phase}_state_data_sha256_not_new")
            break


def validate_noop(
    snapshot: dict[str, Any],
    *,
    post_apply: dict[str, Any],
    blockers: list[str],
) -> None:
    if current_version(snapshot) != current_version(post_apply):
        blockers.append("noop_current_changed_from_post_apply")
    if previous_version(snapshot) != previous_version(post_apply):
        blockers.append("noop_previous_changed_from_post_apply")
    if mutation_fingerprint(snapshot) != mutation_fingerprint(post_apply):
        blockers.append("noop_state_mutated_from_post_apply")
    service_journal = journal_text(snapshot).lower()
    if not any(token in service_journal for token in ("player_runtime_apply_noop_already_current", "already_current", "noop")):
        blockers.append("noop_event_missing")
    validate_service_success(snapshot, "noop", blockers)


def validate_rollback(
    snapshot: dict[str, Any],
    *,
    previous_snapshot: dict[str, Any],
    baseline_version: str,
    target_version: str,
    expected_reason: str,
    blockers: list[str],
) -> None:
    if current_version(snapshot) != baseline_version:
        blockers.append("rollback_current_not_baseline_c21")
    if previous_version(snapshot) != target_version:
        blockers.append("rollback_previous_not_target_c22")
    last = as_dict(state_summary(snapshot).get("last_operation") or state_file_data(snapshot).get("last_operation"))
    if last.get("type") != "rollback":
        blockers.append("rollback_last_operation_type_not_rollback")
    if last.get("status") != "success":
        blockers.append("rollback_last_operation_status_not_success")
    if last.get("rolled_back_to") != baseline_version:
        blockers.append("rollback_last_operation_target_mismatch")
    reason = str_field(last.get("rollback_reason"))
    if reason != expected_reason and expected_reason not in journal_text(snapshot):
        blockers.append("rollback_not_authorized_reason")
    validate_authorized_rollback_activation(snapshot, "rollback", blockers)
    validate_new_operation_after_snapshot(
        snapshot,
        phase="rollback",
        previous_snapshot=previous_snapshot,
        disallowed_state_snapshots=(previous_snapshot,),
        blockers=blockers,
    )
    validate_health_green(snapshot, "rollback", blockers)


def validate_restored(
    snapshot: dict[str, Any],
    *,
    rollback_snapshot: dict[str, Any],
    post_apply_snapshot: dict[str, Any],
    baseline_version: str,
    target: dict[str, Any],
    expected_reason: str,
    blockers: list[str],
) -> None:
    if current_version(snapshot) != target.get("version"):
        blockers.append("restored_current_not_target_c22")
    if previous_version(snapshot) != baseline_version:
        blockers.append("restored_previous_not_baseline_c21")
    if release_identity(snapshot, "current") != release_identity(rollback_snapshot, "previous"):
        blockers.append("restored_current_not_rollback_previous_identity")
    if release_identity(snapshot, "previous") != release_identity(rollback_snapshot, "current"):
        blockers.append("restored_previous_not_rollback_current_identity")
    validate_current_marker(snapshot, "restored", target, blockers)
    validate_authorized_rollback_activation(snapshot, "restored", blockers)
    last = as_dict(state_summary(snapshot).get("last_operation") or state_file_data(snapshot).get("last_operation"))
    if last.get("rolled_back_to") != target.get("version"):
        blockers.append("restored_last_operation_target_mismatch")
    reason = str_field(last.get("rollback_reason"))
    if reason != expected_reason and expected_reason not in journal_text(snapshot):
        blockers.append("restored_not_authorized_reason")
    validate_new_operation_after_snapshot(
        snapshot,
        phase="restored",
        previous_snapshot=rollback_snapshot,
        disallowed_state_snapshots=(rollback_snapshot, post_apply_snapshot),
        blockers=blockers,
    )
    validate_health_green(snapshot, "restored", blockers)
    if target_is_quarantined(snapshot, target):
        blockers.append("restored_target_c22_quarantined")


def target_is_quarantined(snapshot: dict[str, Any], target: dict[str, Any]) -> bool:
    for entry in as_list(state_summary(snapshot).get("quarantine")):
        if not isinstance(entry, dict):
            continue
        if entry.get("version") == target.get("version"):
            return True
        if entry.get("payload_sha256") == target.get("payload_sha256"):
            return True
        if entry.get("tree_sha256") == target.get("tree_sha256"):
            return True
    return False


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    authorization_result = authorization_gate.evaluate(
        args.authorization,
        manifest=args.manifest,
        payload=args.payload,
        release_gate_path=args.release_gate,
    )
    if authorization_result.get("passed") is not True:
        blockers.extend(
            f"authorization_gate:{blocker}"
            for blocker in as_list(authorization_result.get("blockers"))
        )
    target = validate_manifest_payload_release_gate(
        manifest_path=args.manifest,
        payload_path=args.payload,
        release_gate_path=args.release_gate,
        target_version=args.target_version,
        blockers=blockers,
    )
    authorization = validate_authorization(args.authorization, target=target, blockers=blockers)
    publication = validate_publication(
        args.publication_evidence,
        target=target,
        authorization=authorization,
        blockers=blockers,
    )
    authorization_sha = (
        sha256_file(args.authorization)
        if args.authorization is not None and args.authorization.is_file() and not args.authorization.is_symlink()
        else ""
    )

    snapshots = {
        phase: load_snapshot(getattr(args, phase), blockers, phase)
        for phase in PHASES
    }
    for phase, snapshot in snapshots.items():
        validate_snapshot_common(
            snapshot,
            phase=phase,
            expected_image_tag=args.expected_image_tag,
            expected_image_version=args.expected_image_version,
            expected_updater_sha256=args.expected_updater_sha256,
            authorization_sha256=authorization_sha,
            authorization_data=authorization,
            max_player_restarts=args.max_player_restarts,
            require_freeze_probe=args.require_freeze_probe,
            blockers=blockers,
        )
        validate_state_consistency(snapshot, phase, blockers)

    validate_phase_order(snapshots, blockers)
    validate_timer_execution(
        snapshots["pre"],
        snapshots["post_apply"],
        snapshots["noop"],
        authorization,
        blockers,
    )

    validate_pre(
        snapshots["pre"],
        baseline_version=args.baseline_version,
        target_version=args.target_version,
        blockers=blockers,
    )
    validate_post_apply(
        snapshots["post_apply"],
        baseline_version=args.baseline_version,
        target=target,
        authorization=authorization,
        blockers=blockers,
    )
    validate_noop(snapshots["noop"], post_apply=snapshots["post_apply"], blockers=blockers)
    validate_rollback(
        snapshots["rollback"],
        previous_snapshot=snapshots["noop"],
        baseline_version=args.baseline_version,
        target_version=args.target_version,
        expected_reason=args.expected_rollback_reason,
        blockers=blockers,
    )
    validate_restored(
        snapshots["restored"],
        rollback_snapshot=snapshots["rollback"],
        post_apply_snapshot=snapshots["post_apply"],
        baseline_version=args.baseline_version,
        target=target,
        expected_reason=args.expected_rollback_reason,
        blockers=blockers,
    )
    validate_distinct_health_evidence(snapshots, blockers)
    mechanics_blockers = list(blockers)
    cleanliness_blockers: list[str] = []
    continuous_playback = validate_continuous_restored_health(
        snapshots["restored"],
        args.min_continuous_restored_sec,
        cleanliness_blockers,
    )
    blockers.extend(cleanliness_blockers)
    mechanics_passed = not mechanics_blockers
    cleanliness_passed = not cleanliness_blockers
    passed = mechanics_passed and cleanliness_passed

    return {
        "schema": GATE_SCHEMA,
        "passed": passed,
        "mechanics_passed": mechanics_passed,
        "mechanics_blockers": mechanics_blockers,
        "product_distribution_cleanliness_passed": cleanliness_passed,
        "continuous_playback_passed": cleanliness_passed,
        "continuous_playback_blockers": cleanliness_blockers,
        "continuous_playback": continuous_playback,
        "result_claim": (
            "player_runtime_production_autopull_evidence_ready"
            if passed
            else (
                "player_runtime_production_autopull_mechanics_ready_product_cleanliness_blocked"
                if mechanics_passed
                else "player_runtime_production_autopull_evidence_blocked"
            )
        ),
        "inputs": {
            "authorization": str(args.authorization) if args.authorization is not None else None,
            "publication_evidence": str(args.publication_evidence) if args.publication_evidence is not None else None,
            "manifest": str(args.manifest) if args.manifest is not None else None,
            "payload": str(args.payload) if args.payload is not None else None,
            "release_gate": str(args.release_gate) if args.release_gate is not None else None,
            **{phase: str(getattr(args, phase)) if getattr(args, phase) is not None else None for phase in PHASES},
        },
        "expected": {
            "image_tag": args.expected_image_tag,
            "image_version": args.expected_image_version,
            "updater_sha256": args.expected_updater_sha256,
            "target_version": args.target_version,
            "baseline_version": args.baseline_version,
            "max_player_restarts": args.max_player_restarts,
            "require_freeze_probe": args.require_freeze_probe,
            "min_continuous_restored_sec": args.min_continuous_restored_sec,
        },
        "target": target,
        "authorization_sha256": authorization_sha,
        "publication_evidence": publication,
        "authorization_gate": authorization_result,
        "blockers": blockers,
        "non_claims": list(REQUIRED_NON_CLAIMS),
    }


def valid_health(samples: int = 4) -> dict[str, Any]:
    checks = {key: True for key in REQUIRED_HEALTH_CHECKS}
    return {
        "schema": "dadooh.c18.playback.deep_health.v1",
        "passed": True,
        "failure_reasons": [],
        "checks": checks,
        "counters": {
            "samples": samples,
            "estimated_frame_positive_steps": 3,
            "estimated_frame_required_steps": 2,
            "estimated_frame_trailing_nonprogress_steps": 0,
            "hwdec_current": "v4l2request-copy",
            **{name: 0 for name in CONTINUOUS_ZERO_COUNTERS},
        },
    }


def fixture_artifacts(root: Path) -> dict[str, Any]:
    target_version = DEFAULT_TARGET_VERSION
    manifest_path, payload, release_gate_path = authorization_gate.write_fixture_artifacts(
        root,
        version=target_version,
    )
    release_gate = json.loads(release_gate_path.read_text(encoding="utf-8"))
    auth, blockers = authorization_gate.expected_authorization_from_artifacts(
        manifest_path,
        payload,
        release_gate_path,
        operator="operator-prod-01",
        rollback_owner="rollback-owner-01",
        accepted_at_local_date="2026-07-10",
    )
    if blockers:
        raise AssertionError(f"fixture authorization blockers: {blockers}")
    auth_path = root / "player-runtime-production-autopull.json"
    write_json(auth_path, auth)
    release_payload = as_dict(release_gate.get("payload"))
    publication_path = root / "exact-target-publication.json"
    write_json(publication_path, {
        "schema": PUBLICATION_SCHEMA,
        "passed": True,
        "mode": "publish",
        "would_publish": True,
        "published": True,
        "repo": auth["repo"],
        "tag": auth["tag_name"],
        "version": target_version,
        "target_source_commit": auth["source_commit"],
        "manifest_channel": CHANNEL,
        "release_url": f"https://github.com/{auth['repo']}/releases/tag/{auth['tag_name']}",
        "asset_count": 3,
        "assets": [
            {"name": manifest_path.name, "sha256": sha256_file(manifest_path)},
            {"name": payload.name, "sha256": sha256_file(payload)},
            {"name": release_gate_path.name, "sha256": sha256_file(release_gate_path)},
        ],
        "authorization_gate": "passed",
        "remote_source_commit_present": True,
        "remote_exact_tag_verified": True,
        "release_exists": True,
        "latest_before": "totem-core-fixture",
        "latest_after": "totem-core-fixture",
        "non_claims": sorted(REQUIRED_PUBLICATION_NON_CLAIMS),
    })
    return {
        "authorization": auth_path,
        "manifest": manifest_path,
        "payload": payload,
        "release_gate": release_gate_path,
        "publication_evidence": publication_path,
        "authorization_data": auth,
        "authorization_sha256": sha256_file(auth_path),
        "target": {
            "version": target_version,
            "source_commit": auth["source_commit"],
            "payload_sha256": auth["payload_sha256"],
            "manifest_name": manifest_path.name,
            "manifest_sha256": sha256_file(manifest_path),
            "payload_name": payload.name,
            "release_gate_sha256": sha256_file(release_gate_path),
            "tree_sha256": release_payload["tree_sha256"],
            "kiosk_py_sha256": release_payload["kiosk_py_sha256"],
        },
    }


def marker_for(version: str, target: dict[str, Any]) -> dict[str, Any]:
    if version == target["version"]:
        return {
            "schema": "dadooh.c18.player_runtime.verified.v1",
            "verdict": "verified",
            "version": target["version"],
            "payload_sha256": target["payload_sha256"],
            "kiosk_py_sha256": target["kiosk_py_sha256"],
            "tree_sha256": target["tree_sha256"],
            "deep_health": {"passed": True},
        }
    return {
        "schema": "dadooh.c18.player_runtime.verified.v1",
        "verdict": "verified",
        "version": version,
        "payload_sha256": "b" * 64,
        "kiosk_py_sha256": "c" * 64,
        "tree_sha256": "d" * 64,
        "deep_health": {"passed": True},
    }


def fixture_snapshot(
    phase: str,
    *,
    artifacts: dict[str, Any],
    current: str,
    previous: str | None,
    source: str,
    last_operation: dict[str, Any] | None = None,
    journal_line: str = "INFO apply_success",
    state_salt: str = "",
) -> dict[str, Any]:
    target = artifacts["target"]
    phase_index = PHASES.index(phase)
    collected_at = "2026-07-10T12:03:59Z" if phase == "restored" else f"2026-07-10T12:0{phase_index}:00Z"
    if last_operation is not None:
        last_operation = copy.deepcopy(last_operation)
        if phase == "pre":
            started_at = "2026-07-10T11:59:10Z"
            finished_at = "2026-07-10T11:59:30Z"
        else:
            started_at = f"2026-07-10T12:0{phase_index - 1}:10Z"
            finished_at = f"2026-07-10T12:0{phase_index - 1}:30Z"
        last_operation.setdefault("started_at_utc", started_at)
        last_operation.setdefault("finished_at_utc", finished_at)
    current_marker_data = marker_for(current, target)
    current_entry = {
        "version": current,
        "payload_sha256": current_marker_data["payload_sha256"],
        "source": source,
        "kiosk_py_sha256": current_marker_data["kiosk_py_sha256"],
        "tree_sha256": current_marker_data["tree_sha256"],
    }
    previous_entry = None
    if previous is not None:
        previous_marker = marker_for(previous, target)
        previous_entry = {
            "version": previous,
            "payload_sha256": previous_marker["payload_sha256"],
            "source": "fixture",
            "kiosk_py_sha256": previous_marker["kiosk_py_sha256"],
            "tree_sha256": previous_marker["tree_sha256"],
        }
    state_data = {
        "current": current_entry,
        "previous": previous_entry,
        "last_operation": last_operation,
        "quarantine": [],
    }
    if state_salt:
        state_data["fixture_salt"] = state_salt
    state_text = json.dumps(state_data, sort_keys=True)
    last_trigger = "n/a" if phase == "pre" else "Fri 2026-07-10 12:01:00 UTC"
    return {
        "schema": COLLECT_SCHEMA,
        "phase": phase,
        "collected_at_utc": collected_at,
        "image_marker": {
            "exists": True,
            "fields": {
                "image_tag": DEFAULT_EXPECTED_IMAGE_TAG,
                "image_version": DEFAULT_EXPECTED_IMAGE_VERSION,
                "artifact_private": "false",
                "final_image": "true",
            },
        },
        "updater": {"sha256": DEFAULT_EXPECTED_UPDATER_SHA256},
        "authorization": {
            "sha256": artifacts["authorization_sha256"],
            "data": artifacts["authorization_data"],
        },
        "policy": {
            "data": {
                "schema": "dadooh.totem.update.policy.v1",
                "device_channel": "stable",
                "device_track": DEVICE_TRACK,
                "allowed_components": ["totem-core"],
                "allow_prerelease": False,
                "allow_downgrade": False,
            }
        },
        "systemd": {
            "timer": {
                "enabled_raw": "enabled",
                "active_raw": "active",
                "show": {"LastTriggerUSec": last_trigger},
            },
            "service": {
                "show": {
                    "Result": "success",
                    "ExecMainStatus": "0",
                    "InvocationID": f"invocation-{phase}",
                    "TriggeredBy": "totem-player-runtime-update-agent.timer",
                },
                "journal": {"lines": [journal_line]},
            },
            "player": {"journal": {"lines": []}},
        },
        "player_service": {"active_raw": "active", "nrestarts": "0", "show": {"NRestarts": "0"}},
        "state": {
            "current_symlink": {"target": f"releases/{current}"},
            "previous_symlink": {"target": f"releases/{previous}" if previous else ""},
            "state_file": {
                "exists": True,
                "is_file": True,
                "is_symlink": False,
                "sha256": sha256_text(state_text),
                "json_error": None,
                "canonical_json_sha256": canonical_json_sha256(state_data),
                "data": state_data,
            },
            "current_release_marker": {
                "sha256": sha256_text(json.dumps(current_marker_data, sort_keys=True)),
                "data": current_marker_data,
            },
            "summary": {
                "current": current_entry,
                "previous": previous_entry,
                "last_operation": last_operation,
                "quarantine": [],
            },
        },
        "playback_deep_health": {
            "ran": True,
            "returncode": 0,
            "summary": valid_health(600 if phase == "restored" else 4),
        },
        "freeze_probe": {"ran": True, "returncode": 44},
    }


def fixture_run(root: Path) -> tuple[argparse.Namespace, dict[str, Path], dict[str, Any]]:
    artifacts = fixture_artifacts(root)
    target_version = DEFAULT_TARGET_VERSION
    baseline = DEFAULT_BASELINE_VERSION
    auth = artifacts["authorization_data"]
    post = fixture_snapshot(
        "post_apply",
        artifacts=artifacts,
        current=target_version,
        previous=baseline,
        source=f"github-authorized:{auth['repo']}:{auth['tag_name']}",
        last_operation={"type": "apply", "status": "success", "version": target_version, "source": f"github-authorized:{auth['repo']}:{auth['tag_name']}"},
        journal_line=f"INFO apply_success tag={auth['tag_name']}",
    )
    noop = copy.deepcopy(post)
    noop["phase"] = "noop"
    noop["collected_at_utc"] = "2026-07-10T12:02:00Z"
    noop["systemd"]["service"]["show"]["InvocationID"] = "invocation-noop"
    noop["systemd"]["service"]["journal"]["lines"] = ["INFO player_runtime_apply_noop_already_current"]
    snapshots = {
        "pre": fixture_snapshot(
            "pre",
            artifacts=artifacts,
            current=baseline,
            previous=None,
            source="fixture-baseline",
            last_operation={"type": "apply", "status": "success", "version": baseline},
        ),
        "post_apply": post,
        "noop": noop,
        "rollback": fixture_snapshot(
            "rollback",
            artifacts=artifacts,
            current=baseline,
            previous=target_version,
            source="player_runtime_rollback",
            last_operation={
                "type": "rollback",
                "status": "success",
                "rollback_reason": DEFAULT_ROLLBACK_REASON,
                "rolled_back_to": baseline,
                "service_restart_performed": True,
                "service_health_passed": True,
            },
            journal_line="INFO rollback-player-runtime-authorized",
        ),
        "restored": fixture_snapshot(
            "restored",
            artifacts=artifacts,
            current=target_version,
            previous=baseline,
            source="player_runtime_rollback",
            last_operation={
                "type": "rollback",
                "status": "success",
                "rollback_reason": DEFAULT_ROLLBACK_REASON,
                "rolled_back_to": target_version,
                "service_restart_performed": True,
                "service_health_passed": True,
            },
            journal_line="INFO rollback-player-runtime-authorized",
            state_salt="restored",
        ),
    }
    paths: dict[str, Path] = {}
    for phase, payload in snapshots.items():
        path = root / f"{phase}.json"
        health_dir = root / f"{phase}-deep-health"
        health_dir.mkdir()
        health = payload["playback_deep_health"]["summary"]
        sample_count = int(as_dict(health.get("counters")).get("samples") or 0)
        write_json(health_dir / "playback-deep-health-public.json", health)
        (health_dir / "playback-samples.tsv").write_text(
            "seq\tframe\n" + "".join(f"{index}\t{index * 10}\n" for index in range(1, sample_count + 1)),
            encoding="utf-8",
        )
        (health_dir / "status-samples.ndjson").write_text(
            "".join(
                json.dumps({"seq": index, "status": "playing"}) + "\n"
                for index in range(1, sample_count + 1)
            ),
            encoding="utf-8",
        )
        for sidecar in sorted(name for name in REQUIRED_HEALTH_ARTIFACTS if name.startswith("deep-health-")):
            if sidecar == "deep-health-watchdog.json":
                watchdog = {
                    "schema": "dadooh.c18.playback.deep_health.watchdog.v1",
                    "collection_started_at_utc": (
                        "2026-07-10T12:04:00Z" if phase == "restored" else f"2026-07-10T12:0{PHASES.index(phase)}:00Z"
                    ),
                    "collection_finished_at_utc": (
                        "2026-07-10T12:14:00Z" if phase == "restored" else f"2026-07-10T12:0{PHASES.index(phase)}:30Z"
                    ),
                    "event_changed_during_window": False,
                    "action_during_window": "",
                }
                write_json(health_dir / sidecar, watchdog)
            else:
                write_json(
                    health_dir / sidecar,
                    {"schema": "dadooh.c18.fixture.v1", "passed": True, "phase": phase},
                )
        health_files = sorted(health_dir.iterdir(), key=lambda item: item.name)
        payload["playback_deep_health"].update({
            "artifact_dir_name": health_dir.name,
            "summary_path": str(health_dir / "playback-deep-health-public.json"),
            "summary_sha256": sha256_file(health_dir / "playback-deep-health-public.json"),
            "artifacts": [
                {"name": item.name, "sha256": sha256_file(item), "bytes": item.stat().st_size}
                for item in health_files
            ],
        })
        write_json(path, payload)
        paths[phase] = path
    args = argparse.Namespace(
        authorization=artifacts["authorization"],
        publication_evidence=artifacts["publication_evidence"],
        manifest=artifacts["manifest"],
        payload=artifacts["payload"],
        release_gate=artifacts["release_gate"],
        pre=paths["pre"],
        post_apply=paths["post_apply"],
        noop=paths["noop"],
        rollback=paths["rollback"],
        restored=paths["restored"],
        expected_image_tag=DEFAULT_EXPECTED_IMAGE_TAG,
        expected_image_version=DEFAULT_EXPECTED_IMAGE_VERSION,
        expected_updater_sha256=DEFAULT_EXPECTED_UPDATER_SHA256,
        target_version=DEFAULT_TARGET_VERSION,
        baseline_version=DEFAULT_BASELINE_VERSION,
        expected_rollback_reason=DEFAULT_ROLLBACK_REASON,
        max_player_restarts=0,
        require_freeze_probe=True,
        min_continuous_restored_sec=DEFAULT_MIN_CONTINUOUS_RESTORED_SEC,
        json=False,
        self_test=False,
    )
    return args, paths, artifacts


def refresh_fixture_health(paths: dict[str, Path], phase: str) -> None:
    snapshot = json.loads(paths[phase].read_text(encoding="utf-8"))
    health_dir = paths[phase].parent / f"{phase}-deep-health"
    summary_path = health_dir / "playback-deep-health-public.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    health_files = sorted(health_dir.iterdir(), key=lambda item: item.name)
    snapshot["playback_deep_health"]["summary"] = summary
    snapshot["playback_deep_health"]["summary_sha256"] = sha256_file(summary_path)
    snapshot["playback_deep_health"]["artifacts"] = [
        {"name": item.name, "sha256": sha256_file(item), "bytes": item.stat().st_size}
        for item in health_files
    ]
    write_json(paths[phase], snapshot)


class ProductionAutopullEvidenceGateSelfTest(unittest.TestCase):
    def run_fixture(self, mutator: Any | None = None) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args, paths, artifacts = fixture_run(root)
            if mutator is not None:
                mutator(args, paths, artifacts)
            return evaluate(args)

    def test_valid_five_phase_fixture_passes(self) -> None:
        result = self.run_fixture()
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))
        self.assertTrue(result["mechanics_passed"])
        self.assertTrue(result["product_distribution_cleanliness_passed"])
        self.assertGreaterEqual(
            result["continuous_playback"]["duration_sec"],
            DEFAULT_MIN_CONTINUOUS_RESTORED_SEC,
        )

    def test_short_restored_window_preserves_mechanics_but_blocks_product_cleanliness(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            watchdog_path = paths["restored"].parent / "restored-deep-health" / "deep-health-watchdog.json"
            watchdog = json.loads(watchdog_path.read_text(encoding="utf-8"))
            watchdog["collection_finished_at_utc"] = "2026-07-10T12:04:30Z"
            write_json(watchdog_path, watchdog)
            refresh_fixture_health(paths, "restored")

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertTrue(result["mechanics_passed"])
        self.assertFalse(result["continuous_playback_passed"])
        self.assertEqual(
            result["result_claim"],
            "player_runtime_production_autopull_mechanics_ready_product_cleanliness_blocked",
        )
        self.assertIn("continuous_restored_duration_too_short", result["blockers"])

    def test_continuous_window_restart_counter_blocks_only_product_cleanliness(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            summary_path = paths["restored"].parent / "restored-deep-health" / "playback-deep-health-public.json"
            health = json.loads(summary_path.read_text(encoding="utf-8"))
            health["counters"]["mpv_restart"] = 1
            write_json(summary_path, health)
            refresh_fixture_health(paths, "restored")

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertTrue(result["mechanics_passed"])
        self.assertIn("continuous_restored_counter_not_zero:mpv_restart", result["blockers"])

    def test_continuous_window_must_start_after_restore_operation(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            watchdog_path = paths["restored"].parent / "restored-deep-health" / "deep-health-watchdog.json"
            watchdog = json.loads(watchdog_path.read_text(encoding="utf-8"))
            watchdog["collection_started_at_utc"] = "2026-07-10T12:03:00Z"
            watchdog["collection_finished_at_utc"] = "2026-07-10T12:13:00Z"
            write_json(watchdog_path, watchdog)
            refresh_fixture_health(paths, "restored")

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertTrue(result["mechanics_passed"])
        self.assertIn("continuous_restored_started_before_restore_finished", result["blockers"])

    def test_real_player_runtime_success_journal_passes(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], artifacts: dict[str, Any]) -> None:
            data = json.loads(paths["post_apply"].read_text(encoding="utf-8"))
            tag = artifacts["authorization_data"]["tag_name"]
            data["systemd"]["service"]["journal"]["lines"] = [
                f"INFO downloading_manifest tag={tag}",
                "INFO player_runtime_post_promotion_service_restart service=kiosky-player.service",
            ]
            write_json(paths["post_apply"], data)

        result = self.run_fixture(mutate)
        self.assertTrue(result["passed"], msg=json.dumps(result, indent=2, sort_keys=True))

    def test_missing_post_apply_success_journal_denies(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], artifacts: dict[str, Any]) -> None:
            data = json.loads(paths["post_apply"].read_text(encoding="utf-8"))
            tag = artifacts["authorization_data"]["tag_name"]
            data["systemd"]["service"]["journal"]["lines"] = [f"INFO downloading_manifest tag={tag}"]
            write_json(paths["post_apply"], data)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("post_apply_timer_journal_missing_apply_success", result["blockers"])

    def test_empty_snapshot_denies_fail_closed(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            write_json(paths["pre"], {})

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("pre_snapshot_empty_or_unavailable", result["blockers"])

    def test_pre_tamper_denies(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            data = json.loads(paths["pre"].read_text(encoding="utf-8"))
            data["image_marker"]["fields"]["image_tag"] = "c18-hwdecode-lab-1x"
            data["state"]["summary"]["current"]["version"] = DEFAULT_TARGET_VERSION
            write_json(paths["pre"], data)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("pre_production_image_tag_mismatch", result["blockers"])
        self.assertIn("pre_current_not_baseline_c21", result["blockers"])

    def test_post_apply_tamper_denies(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            data = json.loads(paths["post_apply"].read_text(encoding="utf-8"))
            data["state"]["summary"]["current"]["payload_sha256"] = "0" * 64
            data["state"]["current_release_marker"]["data"]["verdict"] = "pending"
            write_json(paths["post_apply"], data)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("post_apply_current_payload_sha256_mismatch", result["blockers"])
        self.assertIn("post_apply_current_marker_not_verified", result["blockers"])

    def test_noop_tamper_denies(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            data = json.loads(paths["noop"].read_text(encoding="utf-8"))
            data["systemd"]["service"]["journal"]["lines"] = ["INFO apply_success"]
            data["state"]["state_file"]["sha256"] = "0" * 64
            write_json(paths["noop"], data)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("noop_event_missing", result["blockers"])
        self.assertIn("noop_state_mutated_from_post_apply", result["blockers"])

    def test_rollback_tamper_denies(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            data = json.loads(paths["rollback"].read_text(encoding="utf-8"))
            data["state"]["summary"]["last_operation"]["type"] = "apply"
            data["state"]["summary"]["current"]["version"] = DEFAULT_TARGET_VERSION
            write_json(paths["rollback"], data)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("rollback_last_operation_type_not_rollback", result["blockers"])
        self.assertIn("rollback_current_not_baseline_c21", result["blockers"])

    def test_restored_tamper_denies(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], artifacts: dict[str, Any]) -> None:
            data = json.loads(paths["restored"].read_text(encoding="utf-8"))
            data["state"]["summary"]["previous"]["version"] = "wrong"
            data["state"]["summary"]["quarantine"] = [{"payload_sha256": artifacts["target"]["payload_sha256"]}]
            write_json(paths["restored"], data)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("restored_previous_not_baseline_c21", result["blockers"])
        self.assertIn("restored_target_c22_quarantined", result["blockers"])

    def test_authorized_rollback_service_restart_and_health_flags_required(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            for phase in ("rollback", "restored"):
                data = json.loads(paths[phase].read_text(encoding="utf-8"))
                last = data["state"]["summary"]["last_operation"]
                last.pop("service_restart_performed", None)
                last["service_health_passed"] = False
                data["state"]["state_file"]["data"]["last_operation"] = dict(last)
                write_json(paths[phase], data)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("rollback_service_restart_not_recorded", result["blockers"])
        self.assertIn("rollback_service_health_not_recorded", result["blockers"])
        self.assertIn("restored_service_restart_not_recorded", result["blockers"])
        self.assertIn("restored_service_health_not_recorded", result["blockers"])

    def test_authorization_hash_tamper_denies(self) -> None:
        def mutate(args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            auth = json.loads(args.authorization.read_text(encoding="utf-8"))
            auth["version"] = "wrong"
            write_json(args.authorization, auth)
            pre = json.loads(paths["pre"].read_text(encoding="utf-8"))
            pre["authorization"]["sha256"] = sha256_file(args.authorization)
            pre["authorization"]["data"] = auth
            write_json(paths["pre"], pre)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("authorization_version_target_mismatch", result["blockers"])
        self.assertIn("post_apply_authorization_sha256_mismatch", result["blockers"])

    def test_timer_and_phase_time_are_decisive(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            pre = json.loads(paths["pre"].read_text(encoding="utf-8"))
            post = json.loads(paths["post_apply"].read_text(encoding="utf-8"))
            post["collected_at_utc"] = pre["collected_at_utc"]
            post["systemd"]["timer"]["show"] = {}
            post["systemd"]["service"]["show"]["InvocationID"] = pre["systemd"]["service"]["show"]["InvocationID"]
            write_json(paths["post_apply"], post)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("post_apply_collected_at_not_after_previous_phase", result["blockers"])
        self.assertIn("post_apply_timer_last_trigger_missing", result["blockers"])
        self.assertIn("post_apply_service_invocation_not_new", result["blockers"])

    def test_restored_requires_second_authorized_rollback_target(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            data = json.loads(paths["restored"].read_text(encoding="utf-8"))
            last = data["state"]["summary"]["last_operation"]
            last.pop("rolled_back_to")
            last.pop("rollback_reason")
            data["state"]["state_file"]["data"]["last_operation"] = copy.deepcopy(last)
            write_json(paths["restored"], data)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("restored_last_operation_target_mismatch", result["blockers"])
        self.assertIn("restored_not_authorized_reason", result["blockers"])

    def test_restored_requires_new_state_and_operation_after_rollback_snapshot(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            restored = json.loads(paths["restored"].read_text(encoding="utf-8"))
            rollback = json.loads(paths["rollback"].read_text(encoding="utf-8"))
            post_apply = json.loads(paths["post_apply"].read_text(encoding="utf-8"))
            restored["state"]["state_file"]["sha256"] = post_apply["state"]["state_file"]["sha256"]
            stale_started = rollback["state"]["summary"]["last_operation"]["started_at_utc"]
            restored["state"]["summary"]["last_operation"]["started_at_utc"] = stale_started
            restored["state"]["state_file"]["data"]["last_operation"]["started_at_utc"] = stale_started
            restored["state"]["state_file"]["canonical_json_sha256"] = canonical_json_sha256(
                restored["state"]["state_file"]["data"]
            )
            write_json(paths["restored"], restored)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("restored_state_file_sha256_not_new", result["blockers"])
        self.assertIn("restored_last_operation_started_before_previous_snapshot", result["blockers"])

    def test_deep_health_requires_hashed_artifact_bundle(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            data = json.loads(paths["post_apply"].read_text(encoding="utf-8"))
            data["playback_deep_health"].pop("artifact_dir_name")
            data["playback_deep_health"]["artifacts"] = []
            write_json(paths["post_apply"], data)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("post_apply_deep_health_artifact_dir_invalid", result["blockers"])
        self.assertIn(
            "post_apply_deep_health_artifact_missing:playback-deep-health-public.json",
            result["blockers"],
        )

    def test_deep_health_requires_collector_sidecars(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            health_dir = paths["post_apply"].parent / "post_apply-deep-health"
            (health_dir / "deep-health-watchdog.json").unlink()

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn(
            "post_apply_deep_health_artifact_missing:deep-health-watchdog.json",
            result["blockers"],
        )

    def test_deep_health_cannot_reuse_another_phase_bundle(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            restored = json.loads(paths["restored"].read_text(encoding="utf-8"))
            post_apply = json.loads(paths["post_apply"].read_text(encoding="utf-8"))
            restored["playback_deep_health"] = copy.deepcopy(post_apply["playback_deep_health"])
            write_json(paths["restored"], restored)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("restored_deep_health_artifact_dir_not_phase_bound", result["blockers"])
        self.assertIn("restored_deep_health_artifacts_reused_from_post_apply", result["blockers"])

    def test_state_summary_must_match_file_and_symlink(self) -> None:
        def mutate(_args: argparse.Namespace, paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            data = json.loads(paths["post_apply"].read_text(encoding="utf-8"))
            data["state"]["current_symlink"]["target"] = f"releases/{DEFAULT_BASELINE_VERSION}"
            data["state"]["state_file"]["data"]["current"]["version"] = DEFAULT_BASELINE_VERSION
            write_json(paths["post_apply"], data)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("post_apply_state_summary_current_mismatch", result["blockers"])
        self.assertIn("post_apply_current_state_symlink_mismatch", result["blockers"])

    def test_publication_evidence_is_remote_target_and_hash_bound(self) -> None:
        def mutate(args: argparse.Namespace, _paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            data = json.loads(args.publication_evidence.read_text(encoding="utf-8"))
            data["repo"] = "example.invalid/repo"
            data["assets"][0]["sha256"] = "0" * 64
            data["latest_after"] = "unexpected-latest"
            write_json(args.publication_evidence, data)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertFalse(result["mechanics_passed"])
        self.assertTrue(result["product_distribution_cleanliness_passed"])
        self.assertIn("publication_evidence_repo_mismatch", result["blockers"])
        self.assertIn("publication_evidence_asset_hashes_mismatch", result["blockers"])
        self.assertIn("publication_evidence_latest_drift", result["blockers"])

    def test_publication_evidence_requires_successful_remote_publish_claims(self) -> None:
        def mutate(args: argparse.Namespace, _paths: dict[str, Path], _artifacts: dict[str, Any]) -> None:
            data = json.loads(args.publication_evidence.read_text(encoding="utf-8"))
            data["mode"] = "prepare-only"
            data["authorization_gate"] = "failed"
            data["remote_source_commit_present"] = False
            data["remote_exact_tag_verified"] = False
            data["release_exists"] = False
            data.pop("release_url")
            write_json(args.publication_evidence, data)

        result = self.run_fixture(mutate)
        self.assertFalse(result["passed"])
        self.assertIn("publication_evidence_mode_invalid", result["blockers"])
        self.assertIn("publication_evidence_authorization_gate_invalid", result["blockers"])
        self.assertIn("publication_evidence_remote_source_commit_present_invalid", result["blockers"])
        self.assertIn("publication_evidence_remote_exact_tag_verified_invalid", result["blockers"])
        self.assertIn("publication_evidence_release_exists_invalid", result["blockers"])
        self.assertIn("publication_evidence_release_url_mismatch", result["blockers"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--publication-evidence", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--release-gate", type=Path)
    parser.add_argument("--pre", type=Path)
    parser.add_argument("--post-apply", dest="post_apply", type=Path)
    parser.add_argument("--noop", type=Path)
    parser.add_argument("--rollback", type=Path)
    parser.add_argument("--restored", type=Path)
    parser.add_argument("--expected-image-tag", default=DEFAULT_EXPECTED_IMAGE_TAG)
    parser.add_argument("--expected-image-version", default=DEFAULT_EXPECTED_IMAGE_VERSION)
    parser.add_argument("--expected-updater-sha256", default=DEFAULT_EXPECTED_UPDATER_SHA256)
    parser.add_argument("--target-version", default=DEFAULT_TARGET_VERSION)
    parser.add_argument("--baseline-version", default=DEFAULT_BASELINE_VERSION)
    parser.add_argument("--expected-rollback-reason", default=DEFAULT_ROLLBACK_REASON)
    parser.add_argument("--max-player-restarts", type=int, default=0)
    parser.add_argument("--require-freeze-probe", action="store_true")
    parser.add_argument(
        "--min-continuous-restored-sec",
        type=float,
        default=DEFAULT_MIN_CONTINUOUS_RESTORED_SEC,
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProductionAutopullEvidenceGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    result = evaluate(args)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"passed={str(result['passed']).lower()} result_claim={result['result_claim']}")
        for blocker in result["blockers"]:
            print(f"blocker={blocker}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
