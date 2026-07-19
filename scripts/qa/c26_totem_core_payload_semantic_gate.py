#!/usr/bin/env python3
"""Validate the C26 recovery transport contract inside a totem-core payload."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tarfile
import tempfile
from typing import Any


SCHEMA = "dadooh.c26.totem_core_payload_semantic_gate.v1"
REQUIRED_BIN_FILES = frozenset(
    {
        "totem_api_url_contract.py",
        "totem_config_contract_validate.py",
        "totem_config_writer_real.py",
        "totem_open_settings_session.sh",
        "totem_qr_pairing_client.py",
        "totem_settings_production_apply_policy.py",
        "totem_setup_minimal_server.py",
        "totem_setup_visual_wizard.py",
        "totem_visual_setup_writer_handoff.py",
        "totem_wifi_nm_adapter.py",
    }
)

PROBE = r'''
import json
import pathlib
import shlex
import subprocess
import tempfile

import totem_api_url_contract as api_contract
import totem_config_contract_validate as config_contract
import totem_config_writer_real as config_writer
import totem_qr_pairing_client as pairing_client
import totem_settings_production_apply_policy as apply_policy
import totem_setup_visual_wizard as visual_wizard
import totem_visual_setup_writer_handoff as writer_handoff


def require_rejection(label, callback, value):
    try:
        callback(value)
    except Exception:
        return
    raise AssertionError(label)


invalid_urls = (
    "https://api.example.com:",
    "https://[2001:db8::1",
    "https://%/search",
    "https://a..example.com/search",
    "https://" + ("a" * 64) + ".example.com/search",
    "https://api.example.com\\bad/search",
    "https://api.example.com/nao-ascii-é",
)
for value in invalid_urls:
    require_rejection("api_contract_url_accepted", api_contract.validate_https_api_url, value)
    require_rejection("writer_url_accepted", config_writer.product_reset_validate_https_api_url, value)
    require_rejection("qr_url_accepted", pairing_client.validate_api_url, value)
    require_rejection("wizard_url_accepted", visual_wizard.normalize_runtime_api_url, value)
    candidate = config_contract.build_mock_candidate()
    candidate["api_url"] = value
    if config_contract.validate_candidate_config(candidate, "real-dry-run")["valid"]:
        raise AssertionError("config_contract_url_accepted")

invalid_keys = (
    "A" * 15,
    "A" * 4097,
    "é" * 1500,
    "😀" * 16,
    ("A" * 16) + "\n",
)
for value in invalid_keys:
    require_rejection("api_contract_key_accepted", api_contract.validate_api_key_format, value)
    require_rejection("writer_key_accepted", config_writer.product_reset_validate_api_key, value)
    require_rejection("qr_key_accepted", pairing_client.validate_api_key, value)
    require_rejection("wizard_key_accepted", visual_wizard.validate_pairing_api_key, value)
    candidate = config_contract.build_mock_candidate()
    candidate["api_key"] = value
    if config_contract.validate_candidate_config(candidate, "real-dry-run")["valid"]:
        raise AssertionError("config_contract_key_accepted")

placeholder_key = "real_preencher_key_1234567890"
if not api_contract.api_key_is_placeholder(placeholder_key):
    raise AssertionError("placeholder_key_not_classified")
require_rejection("writer_placeholder_key_accepted", config_writer.product_reset_validate_api_key, placeholder_key)
require_rejection("qr_placeholder_key_accepted", pairing_client.validate_api_key, placeholder_key)
require_rejection("wizard_placeholder_key_accepted", visual_wizard.validate_pairing_api_key, placeholder_key)
placeholder_candidate = config_contract.build_mock_candidate()
placeholder_candidate["api_key"] = placeholder_key
if config_contract.validate_candidate_config(placeholder_candidate, "real-dry-run")["valid"]:
    raise AssertionError("config_contract_placeholder_key_accepted")

query_url = "https://api.example.com/search?source=totem"
if visual_wizard.normalize_runtime_api_url(query_url) != query_url:
    raise AssertionError("wizard_did_not_preserve_valid_query")
exact_query_prefix = "https://api.example.com?source="
exact_query_url = exact_query_prefix + ("x" * (api_contract.MAX_API_URL_BYTES - len(exact_query_prefix)))
if api_contract.validate_https_api_url(exact_query_url) != exact_query_url:
    raise AssertionError("exact_limit_input_rejected")
require_rejection("wizard_normalized_url_exceeded_limit", visual_wizard.normalize_runtime_api_url, exact_query_url)
require_rejection(
    "wizard_noncanonical_api_token_id_accepted",
    visual_wizard.validate_pairing_api_token_id,
    "token-self-test",
)
if pairing_client.PRODUCT_RESET_MAX_CREDENTIAL_BYTES != api_contract.MAX_PRODUCT_RESET_CREDENTIAL_BYTES:
    raise AssertionError("qr_pending_limit_diverged")

candidate = config_contract.build_mock_candidate()
candidate.update(
    {
        "api_url": query_url,
        "api_key": "A" * 32,
        "api_token_id": "66666666-7777-4888-8999-aaaaaaaaaaaa",
        "environment_id": "11111111-2222-4333-8444-555555555555",
        "station_id": "22222222-3333-4444-8555-666666666666",
    }
)
if not config_contract.validate_candidate_config(candidate, "real-dry-run")["valid"]:
    raise AssertionError("valid_composed_candidate_rejected")

with tempfile.TemporaryDirectory(prefix="c26-environment-binding-probe-") as raw_root:
    root = pathlib.Path(raw_root)
    source_path = root / "source" / "config.candidate.json"
    private_path = root / "private" / "private-values.json"
    writer_handoff.write_json_file(source_path, candidate)
    writer_handoff.write_json_file(
        private_path,
        {
            "api_url": query_url,
            "api_key": "B" * 32,
            "environment_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            "station_id": "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
            "api_token_id": "cccccccc-dddd-4eee-8fff-000000000000",
        },
    )
    try:
        writer_handoff.run_handoff(
            source_candidate_raw=str(source_path),
            private_values_raw=str(private_path),
            out_dir_raw=str(root / "mismatched-out"),
            confirm_private_values_approved=True,
        )
    except writer_handoff.HandoffError as exc:
        if str(exc) != "private credential does not match selected environment":
            raise
    else:
        raise AssertionError("mismatched_qr_environment_accepted")
    bound_private = json.loads(private_path.read_text(encoding="utf-8"))
    bound_private["environment_id"] = candidate["environment_id"]
    writer_handoff.write_json_file(private_path, bound_private)
    bound_status = writer_handoff.run_handoff(
        source_candidate_raw=str(source_path),
        private_values_raw=str(private_path),
        out_dir_raw=str(root / "bound-out"),
        confirm_private_values_approved=True,
    )
    if not bound_status["private_inputs"]["environment_identifier_binding_verified"]:
        raise AssertionError("matching_qr_environment_not_bound")
    bound_private.pop("environment_id")
    writer_handoff.write_json_file(private_path, bound_private)
    try:
        writer_handoff.run_handoff(
            source_candidate_raw=str(source_path),
            private_values_raw=str(private_path),
            out_dir_raw=str(root / "unbound-out"),
            confirm_private_values_approved=True,
        )
    except writer_handoff.HandoffError:
        pass
    else:
        raise AssertionError("unbound_private_source_accepted")

    legacy_active = root / "legacy-active.json"
    legacy_active.write_text(
        json.dumps({"api_url": query_url, "api_key": "D" * 32}) + "\n",
        encoding="utf-8",
    )
    if apply_policy.active_config_ready(legacy_active):
        raise AssertionError("production_policy_accepted_unbound_active_config")
    bound_active = root / "bound-active.json"
    bound_active.write_text(
        json.dumps(
            {
                "api_url": query_url,
                "api_key": "D" * 32,
                "environment_id": candidate["environment_id"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    if not apply_policy.active_config_ready(bound_active):
        raise AssertionError("production_policy_rejected_bound_active_config")

with tempfile.TemporaryDirectory(prefix="c26-session-qr-binding-probe-") as raw_root:
    root = pathlib.Path(raw_root)
    wizard_root = root / "wizard"
    pairing_root = wizard_root / "qr-pairing"
    pairing_root.mkdir(mode=0o700, parents=True)
    private_path = pairing_root / "private-values.json"
    result_path = pairing_root / "pairing-result.public.json"
    candidate_path = wizard_root / "config.candidate.json"
    qr_environment = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    manual_environment = "11111111-2222-4333-8444-555555555555"
    private_path.write_text(
        json.dumps(
            {
                "api_url": query_url,
                "api_key": "C" * 32,
                "environment_id": qr_environment,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    private_path.chmod(0o600)
    result_path.write_text(
        json.dumps(
            {
                "passed": True,
                "state": "authorized",
                "private_values_path": str(private_path),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    session_source = pathlib.Path("totem_open_settings_session.sh").read_text(encoding="utf-8")
    if 'for field in ("api_url", "api_key", "environment_id", "station_id", "api_token_id"):' not in session_source:
        raise AssertionError("active_config_environment_binding_discarded")

    def shell_function(name, next_name):
        start = session_source.index(name + "() {")
        end = session_source.index("\n" + next_name + "() {", start)
        return session_source[start:end]

    selector_source = "\n".join(
        (
            shell_function("validate_private_values_metadata", "select_qr_pairing_private_values_if_available"),
            shell_function("select_qr_pairing_private_values_if_available", "selected_rotation_from_candidate"),
        )
    )

    def run_selector(environment_id):
        candidate_path.write_text(
            json.dumps({"environment_id": environment_id}) + "\n",
            encoding="utf-8",
        )
        script = "\n".join(
            (
                "set -euo pipefail",
                "APPLY_MODE=real-write",
                f"WIZARD_OUT_DIR={shlex.quote(str(wizard_root))}",
                f"PRIVATE_VALUES={shlex.quote(str(root / 'unused-private-values.json'))}",
                "POLICY_PRIVATE_SOURCE=none",
                "HOMOLOGATION_SEED_MODE=false",
                "PAIRING_PRIVATE_VALUES_USED=false",
                selector_source,
                "select_qr_pairing_private_values_if_available",
                'printf "%s\\n" "$PRIVATE_VALUES" "$POLICY_PRIVATE_SOURCE" "$PAIRING_PRIVATE_VALUES_USED"',
            )
        )
        return subprocess.run(
            ["bash", "-c", script],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    mismatched_selection = run_selector(manual_environment)
    if mismatched_selection.returncode != 0:
        raise AssertionError("mismatched_qr_selector_failed_instead_of_ignoring_stale_result")
    if mismatched_selection.stdout.splitlines() != [
        str(root / "unused-private-values.json"),
        "none",
        "false",
    ]:
        raise AssertionError("mismatched_qr_selector_selected_stale_credential")
    matching_selection = run_selector(qr_environment)
    if matching_selection.returncode != 0:
        raise AssertionError("matching_qr_selector_rejected")
    if matching_selection.stdout.splitlines() != [str(private_path), "tmp-file", "true"]:
        raise AssertionError("matching_qr_selector_not_selected")

with tempfile.TemporaryDirectory(prefix="c26-writer-fsync-probe-") as raw_root:
    root = pathlib.Path(raw_root)
    old_config = config_writer.build_synthetic_candidate()
    old_config["station_id"] = "STATION_BEFORE_FSYNC_FAILURE"
    new_config = dict(old_config)
    new_config["station_id"] = "STATION_AFTER_FSYNC_FAILURE"
    candidate_path = root / "candidate" / "candidate.json"
    dest_path = root / "active" / "config.json"
    backup_dir = root / "backups"
    config_writer.write_self_test_candidate(candidate_path, new_config)
    config_writer.write_self_test_candidate(dest_path, old_config)
    before_failure = dest_path.read_bytes()
    original_fsync_directory = config_writer.fsync_directory

    def fail_after_replace(path, *, required=False):
        current_path = pathlib.Path(path)
        if current_path == dest_path.parent and dest_path.exists():
            current = config_writer.load_json_file(dest_path, label="fsync probe active config")
            if current.get("station_id") == new_config["station_id"]:
                if not required:
                    raise AssertionError("active_config_directory_fsync_not_required")
                raise OSError("semantic gate fsync failure after replace")
        original_fsync_directory(current_path, required=required)

    config_writer.fsync_directory = fail_after_replace
    try:
        try:
            config_writer.run_writer(
                candidate_raw=str(candidate_path),
                dest_raw=str(dest_path),
                backup_dir_raw=str(backup_dir),
                out_dir_raw=str(root / "writer-out"),
            )
        except config_writer.WriterError:
            pass
        else:
            raise AssertionError("post_replace_fsync_failure_not_reported")
    finally:
        config_writer.fsync_directory = original_fsync_directory
    if dest_path.read_bytes() != before_failure:
        raise AssertionError("post_replace_fsync_failure_not_rolled_back")
    rollback_status = config_writer.load_json_file(
        root / "writer-out" / config_writer.STATUS_FILENAME,
        label="fsync probe writer status",
    )
    if not rollback_status["write"]["atomic_rename_completed"]:
        raise AssertionError("post_replace_fsync_failure_rename_not_recorded")
    if rollback_status["write"]["fsync_directory_completed"]:
        raise AssertionError("post_replace_fsync_failure_claimed_durable")
    if not rollback_status["rollback"]["restored_valid"]:
        raise AssertionError("post_replace_fsync_failure_restore_not_verified")
    no_backup_dest = root / "no-backup-active" / "config.json"

    def fail_new_destination_after_replace(path, *, required=False):
        current_path = pathlib.Path(path)
        if current_path == no_backup_dest.parent and no_backup_dest.exists():
            current = config_writer.load_json_file(no_backup_dest, label="no-backup fsync probe active config")
            if current.get("station_id") == new_config["station_id"]:
                if not required:
                    raise AssertionError("new_active_config_directory_fsync_not_required")
                raise OSError("semantic gate no-backup fsync failure after replace")
        original_fsync_directory(current_path, required=required)

    config_writer.fsync_directory = fail_new_destination_after_replace
    try:
        try:
            config_writer.run_writer(
                candidate_raw=str(candidate_path),
                dest_raw=str(no_backup_dest),
                backup_dir_raw=str(root / "no-backup-store"),
                out_dir_raw=str(root / "no-backup-writer-out"),
            )
        except config_writer.WriterError:
            pass
        else:
            raise AssertionError("no_backup_post_replace_failure_not_reported")
    finally:
        config_writer.fsync_directory = original_fsync_directory
    if no_backup_dest.exists():
        raise AssertionError("no_backup_post_replace_failure_left_candidate")
    no_backup_status = config_writer.load_json_file(
        root / "no-backup-writer-out" / config_writer.STATUS_FILENAME,
        label="no-backup fsync probe writer status",
    )
    if not no_backup_status["rollback"]["active_removed_without_backup"]:
        raise AssertionError("no_backup_post_replace_failure_not_removed")

    config_writer.write_self_test_candidate(dest_path, old_config)

    def remove_backup_then_fail(path, *, required=False):
        current_path = pathlib.Path(path)
        if current_path == dest_path.parent and dest_path.exists():
            current = config_writer.load_json_file(dest_path, label="missing backup active config")
            if current.get("station_id") == new_config["station_id"]:
                for backup_path in backup_dir.glob("*.bak"):
                    backup_path.unlink()
                raise OSError("semantic gate backup disappearance")
        original_fsync_directory(current_path, required=required)

    config_writer.fsync_directory = remove_backup_then_fail
    try:
        try:
            config_writer.run_writer(
                candidate_raw=str(candidate_path),
                dest_raw=str(dest_path),
                backup_dir_raw=str(backup_dir),
                out_dir_raw=str(root / "missing-backup-writer-out"),
            )
        except config_writer.WriterError:
            pass
        else:
            raise AssertionError("missing_backup_failure_not_reported")
    finally:
        config_writer.fsync_directory = original_fsync_directory
    if dest_path.exists():
        raise AssertionError("missing_backup_failure_left_candidate")
    missing_backup_status = config_writer.load_json_file(
        root / "missing-backup-writer-out" / config_writer.STATUS_FILENAME,
        label="missing backup writer status",
    )
    if not missing_backup_status["rollback"]["attempted"]:
        raise AssertionError("missing_backup_rollback_attempt_not_recorded")
    if not missing_backup_status["rollback"]["active_removed_fail_closed"]:
        raise AssertionError("missing_backup_candidate_not_removed_fail_closed")

    config_writer.write_self_test_candidate(dest_path, old_config)
    original_copy_file_private_atomic = config_writer.copy_file_private_atomic

    def fail_restore_before_replace(src, dst, mode, *, real_write_enabled):
        if pathlib.Path(dst) == dest_path and pathlib.Path(src).parent == backup_dir:
            raise OSError("semantic gate persistent restore failure")
        original_copy_file_private_atomic(
            pathlib.Path(src),
            pathlib.Path(dst),
            mode,
            real_write_enabled=real_write_enabled,
        )

    config_writer.copy_file_private_atomic = fail_restore_before_replace
    try:
        try:
            config_writer.run_writer(
                candidate_raw=str(candidate_path),
                dest_raw=str(dest_path),
                backup_dir_raw=str(backup_dir),
                out_dir_raw=str(root / "persistent-restore-writer-out"),
                simulate_post_write_failure=True,
            )
        except config_writer.WriterError:
            pass
        else:
            raise AssertionError("persistent_restore_failure_not_reported")
    finally:
        config_writer.copy_file_private_atomic = original_copy_file_private_atomic
    if dest_path.exists():
        raise AssertionError("persistent_restore_failure_left_candidate")
    persistent_restore_status = config_writer.load_json_file(
        root / "persistent-restore-writer-out" / config_writer.STATUS_FILENAME,
        label="persistent restore writer status",
    )
    if not persistent_restore_status["rollback"]["attempted"]:
        raise AssertionError("persistent_restore_attempt_not_recorded")
    if not persistent_restore_status["rollback"]["active_removed_fail_closed"]:
        raise AssertionError("persistent_restore_candidate_not_removed_fail_closed")

    config_writer.write_self_test_candidate(dest_path, old_config)
    old_bytes = dest_path.read_bytes()

    def fail_all_active_directory_fsyncs(path, *, required=False):
        current_path = pathlib.Path(path)
        if current_path == dest_path.parent and dest_path.exists():
            raise OSError("semantic gate persistent active directory fsync failure")
        original_fsync_directory(current_path, required=required)

    config_writer.fsync_directory = fail_all_active_directory_fsyncs
    try:
        try:
            config_writer.run_writer(
                candidate_raw=str(candidate_path),
                dest_raw=str(dest_path),
                backup_dir_raw=str(backup_dir),
                out_dir_raw=str(root / "persistent-fsync-writer-out"),
            )
        except config_writer.WriterError:
            pass
        else:
            raise AssertionError("persistent_fsync_failure_not_reported")
    finally:
        config_writer.fsync_directory = original_fsync_directory
    if dest_path.read_bytes() != old_bytes:
        raise AssertionError("persistent_fsync_failure_did_not_expose_prior_config")
    persistent_fsync_status = config_writer.load_json_file(
        root / "persistent-fsync-writer-out" / config_writer.STATUS_FILENAME,
        label="persistent fsync writer status",
    )
    if not persistent_fsync_status["rollback"]["restored"]:
        raise AssertionError("persistent_fsync_restore_not_observed")
    if persistent_fsync_status["rollback"]["durability_verified"]:
        raise AssertionError("persistent_fsync_false_durability_claim")

    stale_out = root / "stale-evidence-out"
    stale_out.mkdir(mode=0o700)
    for name in (config_writer.STATUS_FILENAME, config_writer.SUMMARY_FILENAME):
        (stale_out / name).write_text("stale\n", encoding="utf-8")
    evidence_failure_dest = root / "evidence-failure-active" / "config.json"
    original_write_status_artifacts = config_writer.write_status_artifacts

    def fail_status_artifacts(_out_dir, _status):
        raise OSError("semantic gate evidence write failure")

    config_writer.write_status_artifacts = fail_status_artifacts
    try:
        evidence_failure_status = config_writer.run_writer(
            candidate_raw=str(candidate_path),
            dest_raw=str(evidence_failure_dest),
            backup_dir_raw=str(root / "evidence-failure-backups"),
            out_dir_raw=str(stale_out),
        )
    finally:
        config_writer.write_status_artifacts = original_write_status_artifacts
    if evidence_failure_status["result"] != "passed":
        raise AssertionError("diagnostic_failure_undid_valid_config")
    for name in (config_writer.STATUS_FILENAME, config_writer.SUMMARY_FILENAME):
        if (stale_out / name).exists():
            raise AssertionError("diagnostic_failure_left_stale_artifact")

with tempfile.TemporaryDirectory(prefix="c26-physical-pending-probe-") as raw_root:
    fixture = config_writer.product_reset_self_test_fixture(pathlib.Path(raw_root), 991)
    data = fixture["data"]
    ctx = config_writer.product_reset_self_test_context(data)
    config_writer.product_reset_prepare_state(ctx)
    operation_id = config_writer.product_reset_self_test_uuid(991)
    pending = config_writer.product_reset_capture_active_credential(ctx, operation_id)
    raw_pending = config_writer.product_reset_json_payload(pending)
    pending_path = config_writer.product_reset_pending_credential_path(ctx)
    pending_path.write_bytes(
        raw_pending
        + (b" " * (api_contract.MAX_PRODUCT_RESET_CREDENTIAL_BYTES + 1 - len(raw_pending)))
    )
    pending_path.chmod(config_writer.PRIVATE_FILE_MODE)
    try:
        config_writer.product_reset_start_or_resume(ctx, operation_id_raw=None, start=False)
    except config_writer.WriterError as exc:
        if str(exc) != "product_reset_pending_credential_too_large":
            raise
    else:
        raise AssertionError("oversized_physical_pending_accepted")
    if not (data / "config/config.json").exists():
        raise AssertionError("oversized_physical_pending_moved_config")
    if config_writer.product_reset_intent_path(ctx).exists():
        raise AssertionError("oversized_physical_pending_wrote_intent")
    if not (data / "media/kiosky-player/marker.txt").exists():
        raise AssertionError("oversized_physical_pending_moved_media")

print(json.dumps({"passed": True, "contract": "c26-recovery-transport-v1"}, sort_keys=True))
'''


def _safe_extract_bin(payload: pathlib.Path, destination: pathlib.Path) -> pathlib.Path:
    bin_dir = destination / "bin"
    bin_dir.mkdir(mode=0o700)
    seen: set[str] = set()
    with tarfile.open(payload, "r:gz") as archive:
        for member in archive.getmembers():
            raw_parts = pathlib.PurePosixPath(member.name).parts
            parts = tuple(part for part in raw_parts if part not in {"", "."})
            if member.name.startswith("/") or ".." in parts:
                raise ValueError("unsafe_payload_path")
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError("unsafe_payload_member_type")
            if len(parts) != 2 or parts[0] != "bin":
                continue
            name = parts[1]
            if name in seen:
                raise ValueError("duplicate_payload_member")
            seen.add(name)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("payload_member_unreadable")
            target = bin_dir / name
            target.write_bytes(source.read())
            target.chmod(0o700)
    missing = sorted(REQUIRED_BIN_FILES - seen)
    if missing:
        raise ValueError("missing_required_bin_files:" + ",".join(missing))
    return bin_dir


def validate_payload(payload: pathlib.Path) -> dict[str, Any]:
    checks = {
        "payload_regular_file": payload.is_file() and not payload.is_symlink(),
        "required_files_present": False,
        "composed_transport_probe": False,
    }
    reason = ""
    probe_stdout = ""
    probe_stderr = ""
    if checks["payload_regular_file"]:
        try:
            with tempfile.TemporaryDirectory(prefix="dadooh-c26-payload-semantic-") as raw_root:
                root = pathlib.Path(raw_root)
                bin_dir = _safe_extract_bin(payload, root)
                checks["required_files_present"] = True
                env = {
                    "HOME": str(root),
                    "LC_ALL": "C.UTF-8",
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(bin_dir),
                    "TMPDIR": str(root),
                }
                result = subprocess.run(
                    [sys.executable, "-B", "-c", PROBE],
                    cwd=bin_dir,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=120,
                    check=False,
                )
                probe_stdout = result.stdout[-2000:]
                probe_stderr = result.stderr[-2000:]
                checks["composed_transport_probe"] = result.returncode == 0
                if result.returncode != 0:
                    reason = f"composed_transport_probe_failed:rc={result.returncode}"
        except Exception as exc:
            reason = f"payload_semantic_validation_error:{type(exc).__name__}:{exc}"
    else:
        reason = "payload_not_regular_file"
    return {
        "schema": SCHEMA,
        "passed": all(checks.values()),
        "payload": str(payload),
        "checks": checks,
        "reason": reason,
        "probe_stdout_tail": probe_stdout,
        "probe_stderr_tail": probe_stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--payload", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate_payload(pathlib.Path(args.payload))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("passed=" + str(result["passed"]).lower())
        if result["reason"]:
            print("reason=" + result["reason"])
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
