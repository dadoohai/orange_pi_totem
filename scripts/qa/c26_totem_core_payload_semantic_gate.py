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
        "totem_qr_pairing_client.py",
        "totem_setup_minimal_server.py",
        "totem_setup_visual_wizard.py",
        "totem_wifi_nm_adapter.py",
    }
)

PROBE = r'''
import json
import pathlib
import tempfile

import totem_api_url_contract as api_contract
import totem_config_contract_validate as config_contract
import totem_config_writer_real as config_writer
import totem_qr_pairing_client as pairing_client
import totem_setup_visual_wizard as visual_wizard


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
