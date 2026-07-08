#!/usr/bin/env python3
"""C21 totem pairing client.

This first slice is intentionally offline/mockable: it defines the device
pairing contract used by the visual wizard without requiring the production
backend to exist yet. Public artifacts may show the short code and URL. Machine
credentials are written only to a restricted private file under /tmp.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import secrets
import stat
import string
import sys
import tempfile
import uuid
from typing import Any
from urllib import parse as urllib_parse


SESSION_SCHEMA = "dadooh.c21.totem_qr_pairing.session.v1"
RESULT_SCHEMA = "dadooh.c21.totem_qr_pairing.result.v1"
PRIVATE_VALUES_SCHEMA = "dadooh.c21.totem_qr_pairing.private_values.v1"

DEFAULT_OUT_DIR = "/tmp/dadooh-c21-totem-pairing"
DEFAULT_AUTHORIZE_BASE_URL = "https://home.dadooh.ai/totem/authorize"
DEFAULT_API_URL = "https://api-lbyvh5uf6q-uc.a.run.app/search"
DEFAULT_ENVIRONMENT_ID = "11111111-2222-4333-8444-555555555555"
DEFAULT_STATION_ID = "22222222-3333-4444-8555-666666666666"
DEFAULT_MOCK_API_KEY = "C21_MOCK_DEVICE_KEY_NOT_FOR_PROD_1234567890"
PAIRING_STATES = (
    "pending",
    "authorized",
    "expired",
    "denied",
    "backend_unavailable",
    "empty_environment_list",
    "already_used",
)
PUBLIC_FILE_MODE = 0o644
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


class PairingError(RuntimeError):
    """Public-safe pairing error."""


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_uuid(value: str, field: str) -> str:
    raw = str(value or "").strip()
    try:
        parsed = uuid.UUID(raw)
    except ValueError as exc:
        raise PairingError(f"{field}_invalid") from exc
    if str(parsed) != raw.lower():
        raise PairingError(f"{field}_not_canonical")
    return str(parsed)


def validate_api_url(value: str) -> str:
    raw = str(value or "").strip()
    parsed = urllib_parse.urlsplit(raw)
    if parsed.scheme != "https" or not parsed.netloc:
        raise PairingError("api_url_invalid")
    return raw


def validate_authorize_base_url(value: str) -> str:
    raw = str(value or "").strip()
    parsed = urllib_parse.urlsplit(raw)
    if parsed.scheme != "https" or not parsed.netloc:
        raise PairingError("authorize_url_invalid")
    return raw


def validate_api_key(value: str) -> str:
    raw = str(value or "").strip()
    if len(raw) < 16:
        raise PairingError("api_key_too_short")
    lowered = raw.lower()
    if "placeholder" in lowered or "preencher" in lowered:
        raise PairingError("api_key_placeholder")
    return raw


def generate_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def validate_code(value: str) -> str:
    raw = str(value or "").strip().upper().replace("-", "")
    if len(raw) != 8 or any(ch not in string.ascii_uppercase + string.digits for ch in raw):
        raise PairingError("pairing_code_invalid")
    return raw


def authorize_url(base_url: str, code: str) -> str:
    parsed = urllib_parse.urlsplit(base_url)
    query = urllib_parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("code", code))
    return urllib_parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib_parse.urlencode(query), parsed.fragment)
    )


def require_tmp_out_dir(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path)
    if not path.is_absolute():
        raise PairingError("out_dir_must_be_absolute")
    if path == pathlib.Path("/tmp"):
        raise PairingError("out_dir_must_be_dedicated")
    if path.parts[:2] != ("/", "tmp"):
        raise PairingError("out_dir_must_be_under_tmp")
    if path.exists() and not path.is_dir():
        raise PairingError("out_dir_not_directory")
    if path.is_symlink():
        raise PairingError("out_dir_symlink")
    path.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise PairingError("out_dir_parent_symlink")
    os.chmod(path, PRIVATE_DIR_MODE)
    return path


def fsync_dir(path: pathlib.Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_text(path: pathlib.Path, content: str, mode: int) -> None:
    if path.exists() and path.is_symlink():
        raise PairingError("output_symlink")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
        tmp = pathlib.Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)
    fsync_dir(path.parent)


def atomic_write_json(path: pathlib.Path, payload: dict[str, Any], mode: int) -> None:
    atomic_write_text(path, json.dumps(payload, sort_keys=True, indent=2) + "\n", mode)


def pairing_card_svg(*, code: str, url: str, state: str, expires_at: str) -> str:
    safe_code = html.escape(code)
    safe_url = html.escape(url)
    safe_state = html.escape(state)
    safe_expires = html.escape(expires_at)
    seed = sum(ord(ch) for ch in code + url)
    modules = []
    size = 13
    cell = 13
    x0 = 704
    y0 = 190
    for row in range(size):
        for col in range(size):
            border = row in {0, size - 1} or col in {0, size - 1}
            marker = (row < 4 and col < 4) or (row < 4 and col >= size - 4) or (row >= size - 4 and col < 4)
            value = border or marker or ((row * 17 + col * 31 + seed) % 5 in {0, 1})
            if value:
                modules.append(
                    f'<rect x="{x0 + col * cell}" y="{y0 + row * cell}" width="{cell}" height="{cell}" fill="#0f172a"/>'
                )
    modules_svg = "\n    ".join(modules)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="768" viewBox="0 0 1024 768" role="img" aria-label="Dadooh pairing card">
  <rect width="1024" height="768" fill="#0f172a"/>
  <rect x="0" y="0" width="1024" height="12" fill="#38bdf8"/>
  <rect x="64" y="82" width="540" height="470" rx="8" fill="#111827" stroke="#334155"/>
  <rect x="64" y="82" width="8" height="470" rx="4" fill="#38bdf8"/>
  <text x="104" y="150" font-family="Arial, DejaVu Sans, sans-serif" font-size="38" font-weight="700" fill="#f8fafc">Autorizar totem</text>
  <text x="104" y="204" font-family="Arial, DejaVu Sans, sans-serif" font-size="22" fill="#cbd5e1">Abra a URL no celular e confirme este codigo.</text>
  <rect x="104" y="244" width="300" height="76" rx="8" fill="#0b1220" stroke="#38bdf8"/>
  <text x="130" y="294" font-family="Arial, DejaVu Sans, sans-serif" font-size="38" font-weight="700" fill="#f8fafc">{safe_code}</text>
  <text x="104" y="370" font-family="Arial, DejaVu Sans, sans-serif" font-size="20" fill="#cbd5e1">URL:</text>
  <text x="104" y="402" font-family="Arial, DejaVu Sans, sans-serif" font-size="19" fill="#f8fafc">{safe_url}</text>
  <text x="104" y="462" font-family="Arial, DejaVu Sans, sans-serif" font-size="19" fill="#94a3b8">Estado: {safe_state}</text>
  <text x="104" y="496" font-family="Arial, DejaVu Sans, sans-serif" font-size="19" fill="#94a3b8">Expira em: {safe_expires}</text>
  <rect x="682" y="168" width="213" height="213" rx="8" fill="#f8fafc"/>
  {modules_svg}
  <text x="680" y="430" font-family="Arial, DejaVu Sans, sans-serif" font-size="16" fill="#94a3b8">Mock visual; QR escaneavel entra na integracao real.</text>
</svg>
'''


def public_session_payload(*, code: str, url: str, state: str, expires_at: str) -> dict[str, Any]:
    return {
        "schema": SESSION_SCHEMA,
        "mode": "mock",
        "session_id": "mock-session-not-production",
        "state": state,
        "pairing_code": code,
        "authorize_url": url,
        "expires_at_utc": expires_at,
        "poll_after_sec": 2,
        "poll_token_public": False,
        "credential_public": False,
        "human_firebase_token_on_device": False,
        "private_values_written": state == "authorized",
        "non_claims": [
            "not_production_backend",
            "not_scannable_qr_yet",
            "not_real_user_auth",
            "not_real_device_token",
        ],
    }


def private_values_payload(*, api_url: str, api_key: str, environment_id: str, station_id: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": PRIVATE_VALUES_SCHEMA,
        "api_url": api_url,
        "api_key": api_key,
        "environment_id": environment_id,
        "issued_by": "c21-mock-pairing",
        "human_firebase_token_on_device": False,
    }
    if station_id:
        payload["station_id"] = station_id
    return payload


def run_mock_pairing(
    *,
    out_dir: pathlib.Path,
    state: str,
    code: str,
    authorize_base_url: str,
    api_url: str,
    api_key: str,
    environment_id: str,
    station_id: str,
    expires_in_sec: int,
) -> dict[str, Any]:
    if state not in PAIRING_STATES:
        raise PairingError("pairing_state_invalid")
    expires_at = iso_utc(utc_now() + dt.timedelta(seconds=max(30, int(expires_in_sec))))
    url = authorize_url(authorize_base_url, code)
    public_payload = public_session_payload(code=code, url=url, state=state, expires_at=expires_at)

    session_path = out_dir / "pairing-session.public.json"
    card_path = out_dir / "pairing-card.svg"
    private_path = out_dir / "private-values.json"

    atomic_write_json(session_path, public_payload, PUBLIC_FILE_MODE)
    atomic_write_text(card_path, pairing_card_svg(code=code, url=url, state=state, expires_at=expires_at), PUBLIC_FILE_MODE)

    private_written = False
    if state == "authorized":
        private_payload = private_values_payload(
            api_url=api_url,
            api_key=api_key,
            environment_id=environment_id,
            station_id=station_id,
        )
        atomic_write_json(private_path, private_payload, PRIVATE_FILE_MODE)
        private_written = True
    elif private_path.exists():
        private_path.unlink()
        fsync_dir(out_dir)

    result = {
        "schema": RESULT_SCHEMA,
        "passed": state == "authorized",
        "state": state,
        "session_public_path": str(session_path),
        "pairing_card_svg_path": str(card_path),
        "private_values_path": str(private_path) if private_written else None,
        "private_values_mode": "0600" if private_written else None,
        "public_artifacts_sanitized": True,
        "human_firebase_token_on_device": False,
    }
    atomic_write_json(out_dir / "pairing-result.public.json", result, PUBLIC_FILE_MODE)
    return result


def assert_no_public_secret_leak(out_dir: pathlib.Path, forbidden: list[str]) -> None:
    for path in sorted(out_dir.glob("*")):
        if path.name == "private-values.json" or not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for value in forbidden:
            if value and value in content:
                raise AssertionError(f"secret leaked in {path.name}: {value[:8]}")


def run_self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="dadooh-c21-pairing-self-test-") as raw:
        out_dir = require_tmp_out_dir(raw)
        env_id = DEFAULT_ENVIRONMENT_ID
        station_id = DEFAULT_STATION_ID
        api_key = DEFAULT_MOCK_API_KEY
        result = run_mock_pairing(
            out_dir=out_dir,
            state="authorized",
            code="ABCD1234",
            authorize_base_url=DEFAULT_AUTHORIZE_BASE_URL,
            api_url=DEFAULT_API_URL,
            api_key=api_key,
            environment_id=env_id,
            station_id=station_id,
            expires_in_sec=300,
        )
        assert result["passed"] is True
        private_path = pathlib.Path(str(result["private_values_path"]))
        assert private_path.exists()
        assert stat.S_IMODE(private_path.stat().st_mode) == PRIVATE_FILE_MODE
        public_session = json.loads((out_dir / "pairing-session.public.json").read_text(encoding="utf-8"))
        assert public_session["human_firebase_token_on_device"] is False
        assert "ABCD1234" in (out_dir / "pairing-card.svg").read_text(encoding="utf-8")
        assert_no_public_secret_leak(out_dir, [api_key, env_id, station_id, DEFAULT_API_URL])

        for state in (
            "pending",
            "expired",
            "denied",
            "backend_unavailable",
            "empty_environment_list",
            "already_used",
        ):
            state_out = require_tmp_out_dir(str(pathlib.Path(raw) / state))
            state_result = run_mock_pairing(
                out_dir=state_out,
                state=state,
                code="EFGH5678",
                authorize_base_url=DEFAULT_AUTHORIZE_BASE_URL,
                api_url=DEFAULT_API_URL,
                api_key=api_key,
                environment_id=env_id,
                station_id=station_id,
                expires_in_sec=300,
            )
            assert state_result["passed"] is False
            assert state_result["private_values_path"] is None
            assert not (state_out / "private-values.json").exists()
            assert_no_public_secret_leak(state_out, [api_key, env_id, station_id, DEFAULT_API_URL])

        try:
            require_tmp_out_dir("/var/tmp/dadooh-c21-bad")
            raise AssertionError("out dir outside /tmp accepted")
        except PairingError:
            pass

        try:
            validate_code("bad code")
            raise AssertionError("bad pairing code accepted")
        except PairingError:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="C21 totem QR pairing mock client")
    parser.add_argument("--self-test", action="store_true", help="Run offline self-test.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help=f"Dedicated output directory under /tmp. Default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--state", choices=PAIRING_STATES, default="authorized", help="Mock backend state.")
    parser.add_argument("--pairing-code", default="", help="Optional fixed 8-char pairing code for tests.")
    parser.add_argument("--authorize-base-url", default=DEFAULT_AUTHORIZE_BASE_URL, help="Phone authorization URL without code query.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Runtime API /search URL for private output.")
    parser.add_argument("--api-key", default=DEFAULT_MOCK_API_KEY, help="Machine credential for private output only.")
    parser.add_argument("--environment-id", default=DEFAULT_ENVIRONMENT_ID, help="Authorized environment UUID.")
    parser.add_argument("--station-id", default=DEFAULT_STATION_ID, help="Optional authorized station UUID.")
    parser.add_argument("--expires-in-sec", type=int, default=600, help="Mock pairing session TTL.")
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        print("totem_qr_pairing_client_self_test=passed")
        return 0

    out_dir = require_tmp_out_dir(args.out_dir)
    code = validate_code(args.pairing_code) if args.pairing_code else generate_code()
    result = run_mock_pairing(
        out_dir=out_dir,
        state=args.state,
        code=code,
        authorize_base_url=validate_authorize_base_url(args.authorize_base_url),
        api_url=validate_api_url(args.api_url),
        api_key=validate_api_key(args.api_key),
        environment_id=validate_uuid(args.environment_id, "environment_id"),
        station_id=validate_uuid(args.station_id, "station_id") if args.station_id else "",
        expires_in_sec=args.expires_in_sec,
    )
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"state={result['state']}")
        print(f"session_public_path={result['session_public_path']}")
        print(f"pairing_card_svg_path={result['pairing_card_svg_path']}")
        if result["private_values_path"]:
            print(f"private_values_path={result['private_values_path']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PairingError as exc:
        print(f"error={exc}", file=sys.stderr)
        raise SystemExit(2)
