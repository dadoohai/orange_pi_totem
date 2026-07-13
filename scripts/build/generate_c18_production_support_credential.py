#!/usr/bin/env python3
"""Generate the external shared support credential used by a production image build."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = "dadooh.c18.production_support_credential_provenance.v1"
RANDOM_BYTES = 48


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_path, path)
        os.chmod(path, mode)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output = args.output.expanduser().resolve()
    repo_root = Path(__file__).resolve().parents[2]
    if output == repo_root or repo_root in output.parents:
        raise SystemExit("BLOCKED: production credential output must stay outside the source repo")
    provenance = Path(str(output) + ".provenance.json")
    if not args.force and (output.exists() or provenance.exists()):
        raise SystemExit("BLOCKED: credential or provenance already exists; pass --force to rotate")

    output.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(output.parent, 0o700)
    generator = Path(__file__).resolve()
    generator_sha256 = sha256_bytes(generator.read_bytes())
    password = "Aa9!" + secrets.token_urlsafe(RANDOM_BYTES)
    password_bytes = (password + "\n").encode("ascii")
    credential_sha256 = sha256_bytes(password.encode("ascii"))
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    provenance_payload = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "generator": "python-secrets.token_urlsafe",
        "generator_file_sha256": generator_sha256,
        "random_source": "os_csprng_via_python_secrets",
        "random_bytes": RANDOM_BYTES,
        "credential_length": len(password),
        "credential_sha256": credential_sha256,
        "plaintext_embedded_in_provenance": False,
    }

    atomic_write(output, password_bytes, 0o600)
    atomic_write(
        provenance,
        (json.dumps(provenance_payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        0o600,
    )
    print(f"credential_written={output}")
    print(f"provenance_written={provenance}")
    print(f"credential_length={len(password)}")
    print(f"random_bytes={RANDOM_BYTES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
