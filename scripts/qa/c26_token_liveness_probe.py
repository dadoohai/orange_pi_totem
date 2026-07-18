#!/usr/bin/env python3
"""Hold one active token in RAM and publish only pre/post reset HTTP codes."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


SCHEMA = "dadooh.c26.token_liveness_probe.v1"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def require_private_config(path: pathlib.Path) -> dict[str, Any]:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != 0:
        raise SystemExit("config_shape_invalid")
    if stat.S_IMODE(info.st_mode) & 0o027:
        raise SystemExit("config_mode_invalid")
    if info.st_size <= 0 or info.st_size > 64 * 1024:
        raise SystemExit("config_size_invalid")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("config_payload_invalid")
    return value


def probe_url(api_url: str) -> str:
    parsed = urllib.parse.urlsplit(api_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise SystemExit("api_url_invalid")
    return urllib.parse.urlunsplit(("https", parsed.netloc, "/environments", "", ""))


def http_status(url: str, api_key: str, timeout_sec: float) -> int | str:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"Accept": "application/json", "x-api-key": api_key},
    )
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout_sec) as response:
            response.read(1)
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except (TimeoutError, urllib.error.URLError, OSError):
        return "network_error"


def prepare_out_dir(path: pathlib.Path) -> None:
    if path.parent != pathlib.Path("/tmp") or path.name in {"", ".", ".."}:
        raise SystemExit("out_dir_invalid")
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        raise SystemExit("out_dir_untrusted")


def write_status(path: pathlib.Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)
    dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/data/config/config.json")
    parser.add_argument("--receipt", default="/data/state/totem-appliance/product-reset/receipt.json")
    parser.add_argument("--out-dir", default="/tmp/c26-token-liveness-probe")
    parser.add_argument("--wait-sec", type=int, default=900)
    parser.add_argument("--http-timeout-sec", type=float, default=8.0)
    args = parser.parse_args()

    config = require_private_config(pathlib.Path(args.config))
    api_key = config.get("api_key")
    api_url = config.get("api_url")
    if not isinstance(api_key, str) or len(api_key) < 16:
        raise SystemExit("api_key_invalid")
    if not isinstance(api_url, str):
        raise SystemExit("api_url_invalid")

    out_dir = pathlib.Path(args.out_dir)
    prepare_out_dir(out_dir)
    status_path = out_dir / "status.json"
    receipt_path = pathlib.Path(args.receipt)
    started = time.monotonic()
    status: dict[str, Any] = {
        "schema": SCHEMA,
        "started_at_utc": utc_now(),
        "pre_reset_http_status": http_status(probe_url(api_url), api_key, args.http_timeout_sec),
        "receipt_observed": False,
        "post_reset_http_status": "not_run",
        "credentials_written": False,
    }
    write_status(status_path, status)

    while time.monotonic() - started <= args.wait_sec:
        if receipt_path.is_file():
            status["receipt_observed"] = True
            status["post_reset_http_status"] = http_status(
                probe_url(api_url), api_key, args.http_timeout_sec
            )
            status["completed_at_utc"] = utc_now()
            write_status(status_path, status)
            return 0
        time.sleep(0.5)

    status["completed_at_utc"] = utc_now()
    status["timeout"] = True
    write_status(status_path, status)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
