#!/usr/bin/env python3
"""Canonical API transport contract shared by setup and product reset."""

from __future__ import annotations

import ipaddress
import re
import sys
from typing import Any
from urllib import parse as urllib_parse


MAX_API_URL_BYTES = 2048
MIN_API_KEY_BYTES = 16
MAX_API_KEY_BYTES = 4096
MAX_PRODUCT_RESET_CREDENTIAL_BYTES = 8 * 1024
DNS_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
INVALID_PERCENT_ESCAPE_RE = re.compile(r"%(?![0-9A-Fa-f]{2})")


class ApiUrlContractError(ValueError):
    """Raised when a URL cannot be used safely by the appliance."""


class ApiKeyContractError(ValueError):
    """Raised when an API key cannot be transported safely in a header."""


def _validate_hostname(hostname: str) -> None:
    if not hostname or "\\" in hostname or "%" in hostname:
        raise ApiUrlContractError("api_url_invalid")
    try:
        hostname.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ApiUrlContractError("api_url_invalid") from exc

    if ":" in hostname:
        try:
            ipaddress.IPv6Address(hostname)
        except ValueError as exc:
            raise ApiUrlContractError("api_url_invalid") from exc
        return

    if re.fullmatch(r"[0-9.]+", hostname):
        try:
            ipaddress.IPv4Address(hostname)
        except ValueError as exc:
            raise ApiUrlContractError("api_url_invalid") from exc
        return

    if len(hostname) > 253 or hostname.endswith("."):
        raise ApiUrlContractError("api_url_invalid")
    labels = hostname.split(".")
    if not labels or any(DNS_LABEL_RE.fullmatch(label) is None for label in labels):
        raise ApiUrlContractError("api_url_invalid")


def validate_https_api_url(value: Any) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ApiUrlContractError("api_url_invalid")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ApiUrlContractError("api_url_invalid") from exc
    if len(encoded) > MAX_API_URL_BYTES:
        raise ApiUrlContractError("api_url_invalid")
    if (
        any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)
        or "\\" in value
        or INVALID_PERCENT_ESCAPE_RE.search(value) is not None
    ):
        raise ApiUrlContractError("api_url_invalid")
    try:
        parsed = urllib_parse.urlsplit(value)
        port = parsed.port
    except (UnicodeError, ValueError) as exc:
        raise ApiUrlContractError("api_url_invalid") from exc
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not parsed.hostname
        or "@" in parsed.netloc
        or parsed.netloc.endswith(":")
        or "#" in value
        or port == 0
    ):
        raise ApiUrlContractError("api_url_invalid")
    _validate_hostname(parsed.hostname)
    return value


def validate_api_key_format(value: Any) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ApiKeyContractError("api_key_invalid")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ApiKeyContractError("api_key_invalid") from exc
    if not MIN_API_KEY_BYTES <= len(encoded) <= MAX_API_KEY_BYTES:
        raise ApiKeyContractError("api_key_invalid")
    if any(byte < 32 or byte == 127 for byte in encoded):
        raise ApiKeyContractError("api_key_invalid")
    return value


def run_self_test() -> None:
    exact_limit_prefix = "https://api.example.com/"
    exact_limit = exact_limit_prefix + ("x" * (MAX_API_URL_BYTES - len(exact_limit_prefix)))
    accepted = (
        "https://api.example.com",
        "https://api.example.com/search?source=totem",
        "https://api.example.com:443/search",
        "https://127.0.0.1:443/search",
        "https://[2001:db8::1]:8443/search",
        exact_limit,
    )
    for value in accepted:
        assert validate_https_api_url(value) == value

    rejected: tuple[Any, ...] = (
        None,
        123,
        "",
        " https://api.example.com",
        "http://api.example.com",
        "https://api.example.com:",
        "https://api.example.com:0",
        "https://api.example.com:65536",
        "https://@api.example.com",
        "https://:@api.example.com",
        "https://user:pass@api.example.com",
        "https://api.example.com#",
        "https://api.example.com#fragment",
        "https://api.example.com/with space",
        "https://api.example.com/\npath",
        "https://api.example.com\\bad/search",
        "https://%/search",
        "https://a..example.com/search",
        "https://" + ("a" * 64) + ".example.com/search",
        "https://999.999.999.999/search",
        "https://api.example.com./search",
        "https://api.example.com/%ZZ",
        "https://api.example.com/nao-ascii-é",
        "https://[2001:db8::1",
        "https://api.example.com/" + ("x" * MAX_API_URL_BYTES),
        "https://api.example.com/\ud800",
    )
    for value in rejected:
        try:
            validate_https_api_url(value)
        except ApiUrlContractError:
            continue
        raise AssertionError(f"invalid URL accepted: {value!r}")

    for value in ("A" * MIN_API_KEY_BYTES, "A" * MAX_API_KEY_BYTES):
        assert validate_api_key_format(value) == value
    rejected_keys: tuple[Any, ...] = (
        None,
        "",
        "A" * (MIN_API_KEY_BYTES - 1),
        "A" * (MAX_API_KEY_BYTES + 1),
        " " + ("A" * MIN_API_KEY_BYTES),
        ("A" * MIN_API_KEY_BYTES) + "\n",
        "é" * MIN_API_KEY_BYTES,
        "😀" * MIN_API_KEY_BYTES,
    )
    for value in rejected_keys:
        try:
            validate_api_key_format(value)
        except ApiKeyContractError:
            continue
        raise AssertionError(f"invalid API key accepted: {value!r}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        run_self_test()
        print("totem_api_url_contract_self_test=passed")
        raise SystemExit(0)
    raise SystemExit("usage: totem_api_url_contract.py --self-test")
