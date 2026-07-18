#!/usr/bin/env python3
"""Canonical HTTPS URL contract shared by setup and product reset."""

from __future__ import annotations

import sys
from typing import Any
from urllib import parse as urllib_parse


MAX_API_URL_BYTES = 2048


class ApiUrlContractError(ValueError):
    """Raised when a URL cannot be used safely by the appliance."""


def validate_https_api_url(value: Any) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ApiUrlContractError("api_url_invalid")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ApiUrlContractError("api_url_invalid") from exc
    if len(encoded) > MAX_API_URL_BYTES:
        raise ApiUrlContractError("api_url_invalid")
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
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
    return value


def run_self_test() -> None:
    exact_limit_prefix = "https://api.example.com/"
    exact_limit = exact_limit_prefix + ("x" * (MAX_API_URL_BYTES - len(exact_limit_prefix)))
    accepted = (
        "https://api.example.com",
        "https://api.example.com/search?source=totem",
        "https://api.example.com:443/search",
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


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        run_self_test()
        print("totem_api_url_contract_self_test=passed")
        raise SystemExit(0)
    raise SystemExit("usage: totem_api_url_contract.py --self-test")
