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
import hashlib
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
DEFAULT_AUTHORIZE_BASE_URL = "https://home.dadooh.ai/totem/activate"
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
QR_MAX_PAYLOAD_BYTES = 200
QR_QUIET_ZONE_MODULES = 4


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


def qr_matrix(value: str) -> tuple[str, ...]:
    payload = validate_authorize_base_url(value)
    payload_size = len(payload.encode("utf-8"))
    if payload_size == 0 or payload_size > QR_MAX_PAYLOAD_BYTES:
        raise PairingError("qr_payload_size_invalid")
    qr = QrCode.encode_text(payload, QrCode.Ecc.MEDIUM)
    size = qr.get_size()
    return tuple(
        "".join("1" if qr.get_module(x, y) else "0" for x in range(size))
        for y in range(size)
    )


def qr_rects_svg(
    value: str,
    *,
    x: int,
    y: int,
    target_size: int,
    dark: str = "#0f172a",
    light: str = "#ffffff",
) -> str:
    matrix = qr_matrix(value)
    module_count = len(matrix)
    total_modules = module_count + QR_QUIET_ZONE_MODULES * 2
    cell = max(1, target_size // total_modules)
    rendered_size = cell * total_modules
    outer_x = x + (target_size - rendered_size) // 2
    outer_y = y + (target_size - rendered_size) // 2
    matrix_x = outer_x + QR_QUIET_ZONE_MODULES * cell
    matrix_y = outer_y + QR_QUIET_ZONE_MODULES * cell
    modules = []
    for row_index, row in enumerate(matrix):
        for column_index, bit in enumerate(row):
            if bit == "1":
                modules.append(
                    f'<rect data-qr-module="true" x="{matrix_x + column_index * cell}" '
                    f'y="{matrix_y + row_index * cell}" width="{cell}" height="{cell}" fill="{dark}"/>'
                )
    return (
        f'<rect data-qr-background="true" x="{outer_x}" y="{outer_y}" '
        f'width="{rendered_size}" height="{rendered_size}" rx="4" fill="{light}"/>'
        + "\n  ".join(modules)
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
    modules_svg = qr_rects_svg(url, x=682, y=168, target_size=213)
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
  {modules_svg}
  <text x="680" y="430" font-family="Arial, DejaVu Sans, sans-serif" font-size="16" fill="#94a3b8">Escaneie com a camera do celular.</text>
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
        card_svg = (out_dir / "pairing-card.svg").read_text(encoding="utf-8")
        assert "ABCD1234" in card_svg
        assert 'data-qr-background="true"' in card_svg
        assert card_svg.count('data-qr-module="true"') > 100
        matrix = qr_matrix(public_session["authorize_url"])
        assert 21 <= len(matrix) <= 57 and len(matrix) % 2 == 1
        assert all(len(row) == len(matrix) and set(row) <= {"0", "1"} for row in matrix)
        matrix_sha256 = hashlib.sha256("\n".join(matrix).encode("ascii")).hexdigest()
        assert matrix_sha256 == "9895404d9277b8d531c19243c6a9c6160d0e7fe8917d68801df75df78bf28b34"
        assert "not_scannable_qr_yet" not in json.dumps(public_session)
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


# ---- Vendored QR encoder -------------------------------------------------
#
# qrcodegen 1.8.0 by Project Nayuki, vendored in this already-allowlisted
# executable so deployed C21.9 updaters do not need a new payload path.
#
#
# QR Code generator library (Python)
#
# Copyright (c) Project Nayuki. (MIT License)
# https://www.nayuki.io/page/qr-code-generator-library
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
# - The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
# - The Software is provided "as is", without warranty of any kind, express or
#   implied, including but not limited to the warranties of merchantability,
#   fitness for a particular purpose and noninfringement. In no event shall the
#   authors or copyright holders be liable for any claim, damages or other
#   liability, whether in an action of contract, tort or otherwise, arising from,
#   out of or in connection with the Software or the use or other dealings in the
#   Software.
#

import collections, itertools, re
from collections.abc import Sequence
from typing import Callable, Dict, List, Optional, Tuple, Union


# ---- QR Code symbol class ----

class QrCode:
	"""A QR Code symbol, which is a type of two-dimension barcode.
	Invented by Denso Wave and described in the ISO/IEC 18004 standard.
	Instances of this class represent an immutable square grid of dark and light cells.
	The class provides static factory functions to create a QR Code from text or binary data.
	The class covers the QR Code Model 2 specification, supporting all versions (sizes)
	from 1 to 40, all 4 error correction levels, and 4 character encoding modes.

	Ways to create a QR Code object:
	- High level: Take the payload data and call QrCode.encode_text() or QrCode.encode_binary().
	- Mid level: Custom-make the list of segments and call QrCode.encode_segments().
	- Low level: Custom-make the array of data codeword bytes (including
	  segment headers and final padding, excluding error correction codewords),
	  supply the appropriate version number, and call the QrCode() constructor.
	(Note that all ways require supplying the desired error correction level.)"""

	# ---- Static factory functions (high level) ----

	@staticmethod
	def encode_text(text: str, ecl: QrCode.Ecc) -> QrCode:
		"""Returns a QR Code representing the given Unicode text string at the given error correction level.
		As a conservative upper bound, this function is guaranteed to succeed for strings that have 738 or fewer
		Unicode code points (not UTF-16 code units) if the low error correction level is used. The smallest possible
		QR Code version is automatically chosen for the output. The ECC level of the result may be higher than the
		ecl argument if it can be done without increasing the version."""
		segs: List[QrSegment] = QrSegment.make_segments(text)
		return QrCode.encode_segments(segs, ecl)


	@staticmethod
	def encode_binary(data: Union[bytes,Sequence[int]], ecl: QrCode.Ecc) -> QrCode:
		"""Returns a QR Code representing the given binary data at the given error correction level.
		This function always encodes using the binary segment mode, not any text mode. The maximum number of
		bytes allowed is 2953. The smallest possible QR Code version is automatically chosen for the output.
		The ECC level of the result may be higher than the ecl argument if it can be done without increasing the version."""
		return QrCode.encode_segments([QrSegment.make_bytes(data)], ecl)


	# ---- Static factory functions (mid level) ----

	@staticmethod
	def encode_segments(segs: Sequence[QrSegment], ecl: QrCode.Ecc, minversion: int = 1, maxversion: int = 40, mask: int = -1, boostecl: bool = True) -> QrCode:
		"""Returns a QR Code representing the given segments with the given encoding parameters.
		The smallest possible QR Code version within the given range is automatically
		chosen for the output. Iff boostecl is true, then the ECC level of the result
		may be higher than the ecl argument if it can be done without increasing the
		version. The mask number is either between 0 to 7 (inclusive) to force that
		mask, or -1 to automatically choose an appropriate mask (which may be slow).
		This function allows the user to create a custom sequence of segments that switches
		between modes (such as alphanumeric and byte) to encode text in less space.
		This is a mid-level API; the high-level API is encode_text() and encode_binary()."""

		if not (QrCode.MIN_VERSION <= minversion <= maxversion <= QrCode.MAX_VERSION) or not (-1 <= mask <= 7):
			raise ValueError("Invalid value")

		# Find the minimal version number to use
		for version in range(minversion, maxversion + 1):
			datacapacitybits: int = QrCode._get_num_data_codewords(version, ecl) * 8  # Number of data bits available
			datausedbits: Optional[int] = QrSegment.get_total_bits(segs, version)
			if (datausedbits is not None) and (datausedbits <= datacapacitybits):
				break  # This version number is found to be suitable
			if version >= maxversion:  # All versions in the range could not fit the given data
				msg: str = "Segment too long"
				if datausedbits is not None:
					msg = f"Data length = {datausedbits} bits, Max capacity = {datacapacitybits} bits"
				raise DataTooLongError(msg)
		assert datausedbits is not None

		# Increase the error correction level while the data still fits in the current version number
		for newecl in (QrCode.Ecc.MEDIUM, QrCode.Ecc.QUARTILE, QrCode.Ecc.HIGH):  # From low to high
			if boostecl and (datausedbits <= QrCode._get_num_data_codewords(version, newecl) * 8):
				ecl = newecl

		# Concatenate all segments to create the data bit string
		bb = _BitBuffer()
		for seg in segs:
			bb.append_bits(seg.get_mode().get_mode_bits(), 4)
			bb.append_bits(seg.get_num_chars(), seg.get_mode().num_char_count_bits(version))
			bb.extend(seg._bitdata)
		assert len(bb) == datausedbits

		# Add terminator and pad up to a byte if applicable
		datacapacitybits = QrCode._get_num_data_codewords(version, ecl) * 8
		assert len(bb) <= datacapacitybits
		bb.append_bits(0, min(4, datacapacitybits - len(bb)))
		bb.append_bits(0, -len(bb) % 8)  # Note: Python's modulo on negative numbers behaves better than C family languages
		assert len(bb) % 8 == 0

		# Pad with alternating bytes until data capacity is reached
		for padbyte in itertools.cycle((0xEC, 0x11)):
			if len(bb) >= datacapacitybits:
				break
			bb.append_bits(padbyte, 8)

		# Pack bits into bytes in big endian
		datacodewords = bytearray([0] * (len(bb) // 8))
		for (i, bit) in enumerate(bb):
			datacodewords[i >> 3] |= bit << (7 - (i & 7))

		# Create the QR Code object
		return QrCode(version, ecl, datacodewords, mask)


	# ---- Private fields ----

	# The version number of this QR Code, which is between 1 and 40 (inclusive).
	# This determines the size of this barcode.
	_version: int

	# The width and height of this QR Code, measured in modules, between
	# 21 and 177 (inclusive). This is equal to version * 4 + 17.
	_size: int

	# The error correction level used in this QR Code.
	_errcorlvl: QrCode.Ecc

	# The index of the mask pattern used in this QR Code, which is between 0 and 7 (inclusive).
	# Even if a QR Code is created with automatic masking requested (mask = -1),
	# the resulting object still has a mask value between 0 and 7.
	_mask: int

	# The modules of this QR Code (False = light, True = dark).
	# Immutable after constructor finishes. Accessed through get_module().
	_modules: List[List[bool]]

	# Indicates function modules that are not subjected to masking. Discarded when constructor finishes.
	_isfunction: List[List[bool]]


	# ---- Constructor (low level) ----

	def __init__(self, version: int, errcorlvl: QrCode.Ecc, datacodewords: Union[bytes,Sequence[int]], msk: int) -> None:
		"""Creates a new QR Code with the given version number,
		error correction level, data codeword bytes, and mask number.
		This is a low-level API that most users should not use directly.
		A mid-level API is the encode_segments() function."""

		# Check scalar arguments and set fields
		if not (QrCode.MIN_VERSION <= version <= QrCode.MAX_VERSION):
			raise ValueError("Version value out of range")
		if not (-1 <= msk <= 7):
			raise ValueError("Mask value out of range")

		self._version = version
		self._size = version * 4 + 17
		self._errcorlvl = errcorlvl

		# Initialize both grids to be size*size arrays of Boolean false
		self._modules    = [[False] * self._size for _ in range(self._size)]  # Initially all light
		self._isfunction = [[False] * self._size for _ in range(self._size)]

		# Compute ECC, draw modules
		self._draw_function_patterns()
		allcodewords: bytes = self._add_ecc_and_interleave(bytearray(datacodewords))
		self._draw_codewords(allcodewords)

		# Do masking
		if msk == -1:  # Automatically choose best mask
			minpenalty: int = 1 << 32
			for i in range(8):
				self._apply_mask(i)
				self._draw_format_bits(i)
				penalty = self._get_penalty_score()
				if penalty < minpenalty:
					msk = i
					minpenalty = penalty
				self._apply_mask(i)  # Undoes the mask due to XOR
		assert 0 <= msk <= 7
		self._mask = msk
		self._apply_mask(msk)  # Apply the final choice of mask
		self._draw_format_bits(msk)  # Overwrite old format bits

		del self._isfunction


	# ---- Accessor methods ----

	def get_version(self) -> int:
		"""Returns this QR Code's version number, in the range [1, 40]."""
		return self._version

	def get_size(self) -> int:
		"""Returns this QR Code's size, in the range [21, 177]."""
		return self._size

	def get_error_correction_level(self) -> QrCode.Ecc:
		"""Returns this QR Code's error correction level."""
		return self._errcorlvl

	def get_mask(self) -> int:
		"""Returns this QR Code's mask, in the range [0, 7]."""
		return self._mask

	def get_module(self, x: int, y: int) -> bool:
		"""Returns the color of the module (pixel) at the given coordinates, which is False
		for light or True for dark. The top left corner has the coordinates (x=0, y=0).
		If the given coordinates are out of bounds, then False (light) is returned."""
		return (0 <= x < self._size) and (0 <= y < self._size) and self._modules[y][x]


	# ---- Private helper methods for constructor: Drawing function modules ----

	def _draw_function_patterns(self) -> None:
		"""Reads this object's version field, and draws and marks all function modules."""
		# Draw horizontal and vertical timing patterns
		for i in range(self._size):
			self._set_function_module(6, i, i % 2 == 0)
			self._set_function_module(i, 6, i % 2 == 0)

		# Draw 3 finder patterns (all corners except bottom right; overwrites some timing modules)
		self._draw_finder_pattern(3, 3)
		self._draw_finder_pattern(self._size - 4, 3)
		self._draw_finder_pattern(3, self._size - 4)

		# Draw numerous alignment patterns
		alignpatpos: List[int] = self._get_alignment_pattern_positions()
		numalign: int = len(alignpatpos)
		skips: Sequence[Tuple[int,int]] = ((0, 0), (0, numalign - 1), (numalign - 1, 0))
		for i in range(numalign):
			for j in range(numalign):
				if (i, j) not in skips:  # Don't draw on the three finder corners
					self._draw_alignment_pattern(alignpatpos[i], alignpatpos[j])

		# Draw configuration data
		self._draw_format_bits(0)  # Dummy mask value; overwritten later in the constructor
		self._draw_version()


	def _draw_format_bits(self, mask: int) -> None:
		"""Draws two copies of the format bits (with its own error correction code)
		based on the given mask and this object's error correction level field."""
		# Calculate error correction code and pack bits
		data: int = self._errcorlvl.formatbits << 3 | mask  # errCorrLvl is uint2, mask is uint3
		rem: int = data
		for _ in range(10):
			rem = (rem << 1) ^ ((rem >> 9) * 0x537)
		bits: int = (data << 10 | rem) ^ 0x5412  # uint15
		assert bits >> 15 == 0

		# Draw first copy
		for i in range(0, 6):
			self._set_function_module(8, i, _get_bit(bits, i))
		self._set_function_module(8, 7, _get_bit(bits, 6))
		self._set_function_module(8, 8, _get_bit(bits, 7))
		self._set_function_module(7, 8, _get_bit(bits, 8))
		for i in range(9, 15):
			self._set_function_module(14 - i, 8, _get_bit(bits, i))

		# Draw second copy
		for i in range(0, 8):
			self._set_function_module(self._size - 1 - i, 8, _get_bit(bits, i))
		for i in range(8, 15):
			self._set_function_module(8, self._size - 15 + i, _get_bit(bits, i))
		self._set_function_module(8, self._size - 8, True)  # Always dark


	def _draw_version(self) -> None:
		"""Draws two copies of the version bits (with its own error correction code),
		based on this object's version field, iff 7 <= version <= 40."""
		if self._version < 7:
			return

		# Calculate error correction code and pack bits
		rem: int = self._version  # version is uint6, in the range [7, 40]
		for _ in range(12):
			rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
		bits: int = self._version << 12 | rem  # uint18
		assert bits >> 18 == 0

		# Draw two copies
		for i in range(18):
			bit: bool = _get_bit(bits, i)
			a: int = self._size - 11 + i % 3
			b: int = i // 3
			self._set_function_module(a, b, bit)
			self._set_function_module(b, a, bit)


	def _draw_finder_pattern(self, x: int, y: int) -> None:
		"""Draws a 9*9 finder pattern including the border separator,
		with the center module at (x, y). Modules can be out of bounds."""
		for dy in range(-4, 5):
			for dx in range(-4, 5):
				xx, yy = x + dx, y + dy
				if (0 <= xx < self._size) and (0 <= yy < self._size):
					# Chebyshev/infinity norm
					self._set_function_module(xx, yy, max(abs(dx), abs(dy)) not in (2, 4))


	def _draw_alignment_pattern(self, x: int, y: int) -> None:
		"""Draws a 5*5 alignment pattern, with the center module
		at (x, y). All modules must be in bounds."""
		for dy in range(-2, 3):
			for dx in range(-2, 3):
				self._set_function_module(x + dx, y + dy, max(abs(dx), abs(dy)) != 1)


	def _set_function_module(self, x: int, y: int, isdark: bool) -> None:
		"""Sets the color of a module and marks it as a function module.
		Only used by the constructor. Coordinates must be in bounds."""
		assert type(isdark) is bool
		self._modules[y][x] = isdark
		self._isfunction[y][x] = True


	# ---- Private helper methods for constructor: Codewords and masking ----

	def _add_ecc_and_interleave(self, data: bytearray) -> bytes:
		"""Returns a new byte string representing the given data with the appropriate error correction
		codewords appended to it, based on this object's version and error correction level."""
		version: int = self._version
		assert len(data) == QrCode._get_num_data_codewords(version, self._errcorlvl)

		# Calculate parameter numbers
		numblocks: int = QrCode._NUM_ERROR_CORRECTION_BLOCKS[self._errcorlvl.ordinal][version]
		blockecclen: int = QrCode._ECC_CODEWORDS_PER_BLOCK  [self._errcorlvl.ordinal][version]
		rawcodewords: int = QrCode._get_num_raw_data_modules(version) // 8
		numshortblocks: int = numblocks - rawcodewords % numblocks
		shortblocklen: int = rawcodewords // numblocks

		# Split data into blocks and append ECC to each block
		blocks: List[bytes] = []
		rsdiv: bytes = QrCode._reed_solomon_compute_divisor(blockecclen)
		k: int = 0
		for i in range(numblocks):
			dat: bytearray = data[k : k + shortblocklen - blockecclen + (0 if i < numshortblocks else 1)]
			k += len(dat)
			ecc: bytes = QrCode._reed_solomon_compute_remainder(dat, rsdiv)
			if i < numshortblocks:
				dat.append(0)
			blocks.append(dat + ecc)
		assert k == len(data)

		# Interleave (not concatenate) the bytes from every block into a single sequence
		result = bytearray()
		for i in range(len(blocks[0])):
			for (j, blk) in enumerate(blocks):
				# Skip the padding byte in short blocks
				if (i != shortblocklen - blockecclen) or (j >= numshortblocks):
					result.append(blk[i])
		assert len(result) == rawcodewords
		return result


	def _draw_codewords(self, data: bytes) -> None:
		"""Draws the given sequence of 8-bit codewords (data and error correction) onto the entire
		data area of this QR Code. Function modules need to be marked off before this is called."""
		assert len(data) == QrCode._get_num_raw_data_modules(self._version) // 8

		i: int = 0  # Bit index into the data
		# Do the funny zigzag scan
		for right in range(self._size - 1, 0, -2):  # Index of right column in each column pair
			if right <= 6:
				right -= 1
			for vert in range(self._size):  # Vertical counter
				for j in range(2):
					x: int = right - j  # Actual x coordinate
					upward: bool = (right + 1) & 2 == 0
					y: int = (self._size - 1 - vert) if upward else vert  # Actual y coordinate
					if (not self._isfunction[y][x]) and (i < len(data) * 8):
						self._modules[y][x] = _get_bit(data[i >> 3], 7 - (i & 7))
						i += 1
					# If this QR Code has any remainder bits (0 to 7), they were assigned as
					# 0/false/light by the constructor and are left unchanged by this method
		assert i == len(data) * 8


	def _apply_mask(self, mask: int) -> None:
		"""XORs the codeword modules in this QR Code with the given mask pattern.
		The function modules must be marked and the codeword bits must be drawn
		before masking. Due to the arithmetic of XOR, calling _apply_mask() with
		the same mask value a second time will undo the mask. A final well-formed
		QR Code needs exactly one (not zero, two, etc.) mask applied."""
		if not (0 <= mask <= 7):
			raise ValueError("Mask value out of range")
		masker: Callable[[int,int],int] = QrCode._MASK_PATTERNS[mask]
		for y in range(self._size):
			for x in range(self._size):
				self._modules[y][x] ^= (masker(x, y) == 0) and (not self._isfunction[y][x])


	def _get_penalty_score(self) -> int:
		"""Calculates and returns the penalty score based on state of this QR Code's current modules.
		This is used by the automatic mask choice algorithm to find the mask pattern that yields the lowest score."""
		result: int = 0
		size: int = self._size
		modules: List[List[bool]] = self._modules

		# Adjacent modules in row having same color, and finder-like patterns
		for y in range(size):
			runcolor: bool = False
			runx: int = 0
			runhistory = collections.deque([0] * 7, 7)
			for x in range(size):
				if modules[y][x] == runcolor:
					runx += 1
					if runx == 5:
						result += QrCode._PENALTY_N1
					elif runx > 5:
						result += 1
				else:
					self._finder_penalty_add_history(runx, runhistory)
					if not runcolor:
						result += self._finder_penalty_count_patterns(runhistory) * QrCode._PENALTY_N3
					runcolor = modules[y][x]
					runx = 1
			result += self._finder_penalty_terminate_and_count(runcolor, runx, runhistory) * QrCode._PENALTY_N3
		# Adjacent modules in column having same color, and finder-like patterns
		for x in range(size):
			runcolor = False
			runy = 0
			runhistory = collections.deque([0] * 7, 7)
			for y in range(size):
				if modules[y][x] == runcolor:
					runy += 1
					if runy == 5:
						result += QrCode._PENALTY_N1
					elif runy > 5:
						result += 1
				else:
					self._finder_penalty_add_history(runy, runhistory)
					if not runcolor:
						result += self._finder_penalty_count_patterns(runhistory) * QrCode._PENALTY_N3
					runcolor = modules[y][x]
					runy = 1
			result += self._finder_penalty_terminate_and_count(runcolor, runy, runhistory) * QrCode._PENALTY_N3

		# 2*2 blocks of modules having same color
		for y in range(size - 1):
			for x in range(size - 1):
				if modules[y][x] == modules[y][x + 1] == modules[y + 1][x] == modules[y + 1][x + 1]:
					result += QrCode._PENALTY_N2

		# Balance of dark and light modules
		dark: int = sum((1 if cell else 0) for row in modules for cell in row)
		total: int = size**2  # Note that size is odd, so dark/total != 1/2
		# Compute the smallest integer k >= 0 such that (45-5k)% <= dark/total <= (55+5k)%
		k: int = (abs(dark * 20 - total * 10) + total - 1) // total - 1
		assert 0 <= k <= 9
		result += k * QrCode._PENALTY_N4
		assert 0 <= result <= 2568888  # Non-tight upper bound based on default values of PENALTY_N1, ..., N4
		return result


	# ---- Private helper functions ----

	def _get_alignment_pattern_positions(self) -> List[int]:
		"""Returns an ascending list of positions of alignment patterns for this version number.
		Each position is in the range [0,177), and are used on both the x and y axes.
		This could be implemented as lookup table of 40 variable-length lists of integers."""
		ver: int = self._version
		if ver == 1:
			return []
		else:
			numalign: int = ver // 7 + 2
			step: int = 26 if (ver == 32) else \
				(ver * 4 + numalign * 2 + 1) // (numalign * 2 - 2) * 2
			result: List[int] = [(self._size - 7 - i * step) for i in range(numalign - 1)] + [6]
			return list(reversed(result))


	@staticmethod
	def _get_num_raw_data_modules(ver: int) -> int:
		"""Returns the number of data bits that can be stored in a QR Code of the given version number, after
		all function modules are excluded. This includes remainder bits, so it might not be a multiple of 8.
		The result is in the range [208, 29648]. This could be implemented as a 40-entry lookup table."""
		if not (QrCode.MIN_VERSION <= ver <= QrCode.MAX_VERSION):
			raise ValueError("Version number out of range")
		result: int = (16 * ver + 128) * ver + 64
		if ver >= 2:
			numalign: int = ver // 7 + 2
			result -= (25 * numalign - 10) * numalign - 55
			if ver >= 7:
				result -= 36
		assert 208 <= result <= 29648
		return result


	@staticmethod
	def _get_num_data_codewords(ver: int, ecl: QrCode.Ecc) -> int:
		"""Returns the number of 8-bit data (i.e. not error correction) codewords contained in any
		QR Code of the given version number and error correction level, with remainder bits discarded.
		This stateless pure function could be implemented as a (40*4)-cell lookup table."""
		return QrCode._get_num_raw_data_modules(ver) // 8 \
			- QrCode._ECC_CODEWORDS_PER_BLOCK    [ecl.ordinal][ver] \
			* QrCode._NUM_ERROR_CORRECTION_BLOCKS[ecl.ordinal][ver]


	@staticmethod
	def _reed_solomon_compute_divisor(degree: int) -> bytes:
		"""Returns a Reed-Solomon ECC generator polynomial for the given degree. This could be
		implemented as a lookup table over all possible parameter values, instead of as an algorithm."""
		if not (1 <= degree <= 255):
			raise ValueError("Degree out of range")
		# Polynomial coefficients are stored from highest to lowest power, excluding the leading term which is always 1.
		# For example the polynomial x^3 + 255x^2 + 8x + 93 is stored as the uint8 array [255, 8, 93].
		result = bytearray([0] * (degree - 1) + [1])  # Start off with the monomial x^0

		# Compute the product polynomial (x - r^0) * (x - r^1) * (x - r^2) * ... * (x - r^{degree-1}),
		# and drop the highest monomial term which is always 1x^degree.
		# Note that r = 0x02, which is a generator element of this field GF(2^8/0x11D).
		root: int = 1
		for _ in range(degree):  # Unused variable i
			# Multiply the current product by (x - r^i)
			for j in range(degree):
				result[j] = QrCode._reed_solomon_multiply(result[j], root)
				if j + 1 < degree:
					result[j] ^= result[j + 1]
			root = QrCode._reed_solomon_multiply(root, 0x02)
		return result


	@staticmethod
	def _reed_solomon_compute_remainder(data: bytes, divisor: bytes) -> bytes:
		"""Returns the Reed-Solomon error correction codeword for the given data and divisor polynomials."""
		result = bytearray([0] * len(divisor))
		for b in data:  # Polynomial division
			factor: int = b ^ result.pop(0)
			result.append(0)
			for (i, coef) in enumerate(divisor):
				result[i] ^= QrCode._reed_solomon_multiply(coef, factor)
		return result


	@staticmethod
	def _reed_solomon_multiply(x: int, y: int) -> int:
		"""Returns the product of the two given field elements modulo GF(2^8/0x11D). The arguments and result
		are unsigned 8-bit integers. This could be implemented as a lookup table of 256*256 entries of uint8."""
		if (x >> 8 != 0) or (y >> 8 != 0):
			raise ValueError("Byte out of range")
		# Russian peasant multiplication
		z: int = 0
		for i in reversed(range(8)):
			z = (z << 1) ^ ((z >> 7) * 0x11D)
			z ^= ((y >> i) & 1) * x
		assert z >> 8 == 0
		return z


	def _finder_penalty_count_patterns(self, runhistory: collections.deque) -> int:
		"""Can only be called immediately after a light run is added, and
		returns either 0, 1, or 2. A helper function for _get_penalty_score()."""
		n: int = runhistory[1]
		assert n <= self._size * 3
		core: bool = n > 0 and (runhistory[2] == runhistory[4] == runhistory[5] == n) and runhistory[3] == n * 3
		return (1 if (core and runhistory[0] >= n * 4 and runhistory[6] >= n) else 0) \
		     + (1 if (core and runhistory[6] >= n * 4 and runhistory[0] >= n) else 0)


	def _finder_penalty_terminate_and_count(self, currentruncolor: bool, currentrunlength: int, runhistory: collections.deque) -> int:
		"""Must be called at the end of a line (row or column) of modules. A helper function for _get_penalty_score()."""
		if currentruncolor:  # Terminate dark run
			self._finder_penalty_add_history(currentrunlength, runhistory)
			currentrunlength = 0
		currentrunlength += self._size  # Add light border to final run
		self._finder_penalty_add_history(currentrunlength, runhistory)
		return self._finder_penalty_count_patterns(runhistory)


	def _finder_penalty_add_history(self, currentrunlength: int, runhistory: collections.deque) -> None:
		if runhistory[0] == 0:
			currentrunlength += self._size  # Add light border to initial run
		runhistory.appendleft(currentrunlength)


	# ---- Constants and tables ----

	MIN_VERSION: int =  1  # The minimum version number supported in the QR Code Model 2 standard
	MAX_VERSION: int = 40  # The maximum version number supported in the QR Code Model 2 standard

	# For use in _get_penalty_score(), when evaluating which mask is best.
	_PENALTY_N1: int =  3
	_PENALTY_N2: int =  3
	_PENALTY_N3: int = 40
	_PENALTY_N4: int = 10

	_ECC_CODEWORDS_PER_BLOCK: Sequence[Sequence[int]] = (
		# Version: (note that index 0 is for padding, and is set to an illegal value)
		# 0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40    Error correction level
		(-1,  7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),  # Low
		(-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),  # Medium
		(-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30, 28, 30, 30, 30, 30, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),  # Quartile
		(-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28, 30, 24, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30))  # High

	_NUM_ERROR_CORRECTION_BLOCKS: Sequence[Sequence[int]] = (
		# Version: (note that index 0 is for padding, and is set to an illegal value)
		# 0, 1, 2, 3, 4, 5, 6, 7, 8, 9,10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40    Error correction level
		(-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4,  4,  4,  4,  4,  6,  6,  6,  6,  7,  8,  8,  9,  9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25),  # Low
		(-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5,  5,  8,  9,  9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49),  # Medium
		(-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8,  8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68),  # Quartile
		(-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81))  # High

	_MASK_PATTERNS: Sequence[Callable[[int,int],int]] = (
		(lambda x, y:  (x + y) % 2                  ),
		(lambda x, y:  y % 2                        ),
		(lambda x, y:  x % 3                        ),
		(lambda x, y:  (x + y) % 3                  ),
		(lambda x, y:  (x // 3 + y // 2) % 2        ),
		(lambda x, y:  x * y % 2 + x * y % 3        ),
		(lambda x, y:  (x * y % 2 + x * y % 3) % 2  ),
		(lambda x, y:  ((x + y) % 2 + x * y % 3) % 2),
	)


	# ---- Public helper enumeration ----

	class Ecc:
		ordinal: int  # (Public) In the range 0 to 3 (unsigned 2-bit integer)
		formatbits: int  # (Package-private) In the range 0 to 3 (unsigned 2-bit integer)

		"""The error correction level in a QR Code symbol. Immutable."""
		# Private constructor
		def __init__(self, i: int, fb: int) -> None:
			self.ordinal = i
			self.formatbits = fb

		# Placeholders
		LOW     : QrCode.Ecc
		MEDIUM  : QrCode.Ecc
		QUARTILE: QrCode.Ecc
		HIGH    : QrCode.Ecc

	# Public constants. Create them outside the class.
	Ecc.LOW      = Ecc(0, 1)  # The QR Code can tolerate about  7% erroneous codewords
	Ecc.MEDIUM   = Ecc(1, 0)  # The QR Code can tolerate about 15% erroneous codewords
	Ecc.QUARTILE = Ecc(2, 3)  # The QR Code can tolerate about 25% erroneous codewords
	Ecc.HIGH     = Ecc(3, 2)  # The QR Code can tolerate about 30% erroneous codewords



# ---- Data segment class ----

class QrSegment:
	"""A segment of character/binary/control data in a QR Code symbol.
	Instances of this class are immutable.
	The mid-level way to create a segment is to take the payload data
	and call a static factory function such as QrSegment.make_numeric().
	The low-level way to create a segment is to custom-make the bit buffer
	and call the QrSegment() constructor with appropriate values.
	This segment class imposes no length restrictions, but QR Codes have restrictions.
	Even in the most favorable conditions, a QR Code can only hold 7089 characters of data.
	Any segment longer than this is meaningless for the purpose of generating QR Codes."""

	# ---- Static factory functions (mid level) ----

	@staticmethod
	def make_bytes(data: Union[bytes,Sequence[int]]) -> QrSegment:
		"""Returns a segment representing the given binary data encoded in byte mode.
		All input byte lists are acceptable. Any text string can be converted to
		UTF-8 bytes (s.encode("UTF-8")) and encoded as a byte mode segment."""
		bb = _BitBuffer()
		for b in data:
			bb.append_bits(b, 8)
		return QrSegment(QrSegment.Mode.BYTE, len(data), bb)


	@staticmethod
	def make_numeric(digits: str) -> QrSegment:
		"""Returns a segment representing the given string of decimal digits encoded in numeric mode."""
		if not QrSegment.is_numeric(digits):
			raise ValueError("String contains non-numeric characters")
		bb = _BitBuffer()
		i: int = 0
		while i < len(digits):  # Consume up to 3 digits per iteration
			n: int = min(len(digits) - i, 3)
			bb.append_bits(int(digits[i : i + n]), n * 3 + 1)
			i += n
		return QrSegment(QrSegment.Mode.NUMERIC, len(digits), bb)


	@staticmethod
	def make_alphanumeric(text: str) -> QrSegment:
		"""Returns a segment representing the given text string encoded in alphanumeric mode.
		The characters allowed are: 0 to 9, A to Z (uppercase only), space,
		dollar, percent, asterisk, plus, hyphen, period, slash, colon."""
		if not QrSegment.is_alphanumeric(text):
			raise ValueError("String contains unencodable characters in alphanumeric mode")
		bb = _BitBuffer()
		for i in range(0, len(text) - 1, 2):  # Process groups of 2
			temp: int = QrSegment._ALPHANUMERIC_ENCODING_TABLE[text[i]] * 45
			temp += QrSegment._ALPHANUMERIC_ENCODING_TABLE[text[i + 1]]
			bb.append_bits(temp, 11)
		if len(text) % 2 > 0:  # 1 character remaining
			bb.append_bits(QrSegment._ALPHANUMERIC_ENCODING_TABLE[text[-1]], 6)
		return QrSegment(QrSegment.Mode.ALPHANUMERIC, len(text), bb)


	@staticmethod
	def make_segments(text: str) -> List[QrSegment]:
		"""Returns a new mutable list of zero or more segments to represent the given Unicode text string.
		The result may use various segment modes and switch modes to optimize the length of the bit stream."""

		# Select the most efficient segment encoding automatically
		if text == "":
			return []
		elif QrSegment.is_numeric(text):
			return [QrSegment.make_numeric(text)]
		elif QrSegment.is_alphanumeric(text):
			return [QrSegment.make_alphanumeric(text)]
		else:
			return [QrSegment.make_bytes(text.encode("UTF-8"))]


	@staticmethod
	def make_eci(assignval: int) -> QrSegment:
		"""Returns a segment representing an Extended Channel Interpretation
		(ECI) designator with the given assignment value."""
		bb = _BitBuffer()
		if assignval < 0:
			raise ValueError("ECI assignment value out of range")
		elif assignval < (1 << 7):
			bb.append_bits(assignval, 8)
		elif assignval < (1 << 14):
			bb.append_bits(0b10, 2)
			bb.append_bits(assignval, 14)
		elif assignval < 1000000:
			bb.append_bits(0b110, 3)
			bb.append_bits(assignval, 21)
		else:
			raise ValueError("ECI assignment value out of range")
		return QrSegment(QrSegment.Mode.ECI, 0, bb)


	# Tests whether the given string can be encoded as a segment in numeric mode.
	# A string is encodable iff each character is in the range 0 to 9.
	@staticmethod
	def is_numeric(text: str) -> bool:
		return QrSegment._NUMERIC_REGEX.fullmatch(text) is not None


	# Tests whether the given string can be encoded as a segment in alphanumeric mode.
	# A string is encodable iff each character is in the following set: 0 to 9, A to Z
	# (uppercase only), space, dollar, percent, asterisk, plus, hyphen, period, slash, colon.
	@staticmethod
	def is_alphanumeric(text: str) -> bool:
		return QrSegment._ALPHANUMERIC_REGEX.fullmatch(text) is not None


	# ---- Private fields ----

	# The mode indicator of this segment. Accessed through get_mode().
	_mode: QrSegment.Mode

	# The length of this segment's unencoded data. Measured in characters for
	# numeric/alphanumeric/kanji mode, bytes for byte mode, and 0 for ECI mode.
	# Always zero or positive. Not the same as the data's bit length.
	# Accessed through get_num_chars().
	_numchars: int

	# The data bits of this segment. Accessed through get_data().
	_bitdata: List[int]


	# ---- Constructor (low level) ----

	def __init__(self, mode: QrSegment.Mode, numch: int, bitdata: Sequence[int]) -> None:
		"""Creates a new QR Code segment with the given attributes and data.
		The character count (numch) must agree with the mode and the bit buffer length,
		but the constraint isn't checked. The given bit buffer is cloned and stored."""
		if numch < 0:
			raise ValueError()
		self._mode = mode
		self._numchars = numch
		self._bitdata = list(bitdata)  # Make defensive copy


	# ---- Accessor methods ----

	def get_mode(self) -> QrSegment.Mode:
		"""Returns the mode field of this segment."""
		return self._mode

	def get_num_chars(self) -> int:
		"""Returns the character count field of this segment."""
		return self._numchars

	def get_data(self) -> List[int]:
		"""Returns a new copy of the data bits of this segment."""
		return list(self._bitdata)  # Make defensive copy


	# Package-private function
	@staticmethod
	def get_total_bits(segs: Sequence[QrSegment], version: int) -> Optional[int]:
		"""Calculates the number of bits needed to encode the given segments at
		the given version. Returns a non-negative number if successful. Otherwise
		returns None if a segment has too many characters to fit its length field."""
		result = 0
		for seg in segs:
			ccbits: int = seg.get_mode().num_char_count_bits(version)
			if seg.get_num_chars() >= (1 << ccbits):
				return None  # The segment's length doesn't fit the field's bit width
			result += 4 + ccbits + len(seg._bitdata)
		return result


	# ---- Constants ----

	# Describes precisely all strings that are encodable in numeric mode.
	_NUMERIC_REGEX: re.Pattern = re.compile(r"[0-9]*")

	# Describes precisely all strings that are encodable in alphanumeric mode.
	_ALPHANUMERIC_REGEX: re.Pattern = re.compile(r"[A-Z0-9 $%*+./:-]*")

	# Dictionary of "0"->0, "A"->10, "$"->37, etc.
	_ALPHANUMERIC_ENCODING_TABLE: Dict[str,int] = {ch: i for (i, ch) in enumerate("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:")}


	# ---- Public helper enumeration ----

	class Mode:
		"""Describes how a segment's data bits are interpreted. Immutable."""

		_modebits: int  # The mode indicator bits, which is a uint4 value (range 0 to 15)
		_charcounts: Tuple[int,int,int]  # Number of character count bits for three different version ranges

		# Private constructor
		def __init__(self, modebits: int, charcounts: Tuple[int,int,int]):
			self._modebits = modebits
			self._charcounts = charcounts

		# Package-private method
		def get_mode_bits(self) -> int:
			"""Returns an unsigned 4-bit integer value (range 0 to 15) representing the mode indicator bits for this mode object."""
			return self._modebits

		# Package-private method
		def num_char_count_bits(self, ver: int) -> int:
			"""Returns the bit width of the character count field for a segment in this mode
			in a QR Code at the given version number. The result is in the range [0, 16]."""
			return self._charcounts[(ver + 7) // 17]

		# Placeholders
		NUMERIC     : QrSegment.Mode
		ALPHANUMERIC: QrSegment.Mode
		BYTE        : QrSegment.Mode
		KANJI       : QrSegment.Mode
		ECI         : QrSegment.Mode

	# Public constants. Create them outside the class.
	Mode.NUMERIC      = Mode(0x1, (10, 12, 14))
	Mode.ALPHANUMERIC = Mode(0x2, ( 9, 11, 13))
	Mode.BYTE         = Mode(0x4, ( 8, 16, 16))
	Mode.KANJI        = Mode(0x8, ( 8, 10, 12))
	Mode.ECI          = Mode(0x7, ( 0,  0,  0))



# ---- Private helper class ----

class _BitBuffer(list):
	"""An appendable sequence of bits (0s and 1s). Mainly used by QrSegment."""

	def append_bits(self, val: int, n: int) -> None:
		"""Appends the given number of low-order bits of the given
		value to this buffer. Requires n >= 0 and 0 <= val < 2^n."""
		if (n < 0) or (val >> n != 0):
			raise ValueError("Value out of range")
		self.extend(((val >> i) & 1) for i in reversed(range(n)))


def _get_bit(x: int, i: int) -> bool:
	"""Returns true iff the i'th bit of x is set to 1."""
	return (x >> i) & 1 != 0



class DataTooLongError(ValueError):
	"""Raised when the supplied data does not fit any QR Code version. Ways to handle this exception include:
	- Decrease the error correction level if it was greater than Ecc.LOW.
	- If the encode_segments() function was called with a maxversion argument, then increase
	  it if it was less than QrCode.MAX_VERSION. (This advice does not apply to the other
	  factory functions because they search all versions up to QrCode.MAX_VERSION.)
	- Split the text data into better or optimal segments in order to reduce the number of bits required.
	- Change the text or binary data to be shorter.
	- Change the text to fit the character set of a particular segment mode (e.g. alphanumeric).
	- Propagate the error upward to the caller/user."""
	pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PairingError as exc:
        print(f"error={exc}", file=sys.stderr)
        raise SystemExit(2)
