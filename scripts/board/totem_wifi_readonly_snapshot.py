#!/usr/bin/env python3
"""Generate a sanitized, read-only C3 Wi-Fi/network snapshot.

This tool observes local network state through a closed allowlist of read-only
commands. It writes only sanitized aggregate status files under /tmp and never
stores raw command output.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


SCHEMA_VERSION = "dadooh-c3-wifi-readonly.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c3-wifi-readonly"
COMMAND_TIMEOUT_SECONDS = 5

ALLOWED_COMMANDS: dict[str, tuple[str, ...]] = {
    "nmcli_device_status": ("nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"),
    "nmcli_active_connections": (
        "nmcli",
        "-t",
        "-f",
        "NAME,TYPE,DEVICE",
        "connection",
        "show",
        "--active",
    ),
    "ip_brief_addr": ("ip", "-brief", "addr", "show"),
    "ip_default_route": ("ip", "route", "show", "default"),
    "iw_dev": ("iw", "dev"),
}

PROHIBITED_COMMAND_TOKENS = {
    "up",
    "down",
    "modify",
    "delete",
    "del",
    "connect",
    "disconnect",
    "block",
    "unblock",
    "add",
    "replace",
    "set",
    "start",
    "stop",
    "restart",
    "reload",
    "enable",
    "disable",
    "hotspot",
    "portal",
    "ping",
    "curl",
    "wget",
    "ssh",
    "rfkill",
    "systemctl",
    "apt",
}

SENSITIVE_PATTERNS = (
    re.compile(r"https?://[^\s]+", re.IGNORECASE),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|token|secret|password|passwd|senha)\b\s*[:=]\s*[^\s,;]+",
        re.IGNORECASE,
    ),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\bssid\b\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bbssid\b\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bmac\b\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bgateway\b\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bhostname\b\s*[:= ]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bhost\b\s*[:= ]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bconnection(?:_name)?\b\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"/data/media[^\s]*", re.IGNORECASE),
    re.compile(r"/data/config[^\s]*", re.IGNORECASE),
    re.compile(r"/opt/totem[^\s]*", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9_.-]+\.(?:local|lan|internal|corp)\b", re.IGNORECASE),
)


class CommandValidationError(RuntimeError):
    """Raised when a command is outside the C3 read-only allowlist."""


@dataclass(frozen=True)
class CommandResult:
    key: str
    argv: tuple[str, ...]
    status: str
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None


def utc_timestamp() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def require_tmp_dir(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    resolved = path.resolve()
    tmp_root = pathlib.Path("/tmp").resolve()

    try:
        resolved.relative_to(tmp_root)
    except ValueError as exc:
        raise ValueError("out-dir must be under /tmp") from exc

    if resolved == tmp_root:
        raise ValueError("out-dir must be a dedicated directory under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise ValueError("out-dir exists and is not a directory")
    return resolved


def prepare_out_dir(path: pathlib.Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    current_mode = stat.S_IMODE(path.stat().st_mode)
    if current_mode != 0o700:
        path.chmod(0o700)


def write_private_text(path: pathlib.Path, content: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            if not content.endswith("\n"):
                handle.write("\n")
    finally:
        try:
            os.chmod(path, 0o600)
        except FileNotFoundError:
            pass


def sanitize_text(value: str, *, max_len: int = 180) -> str:
    text = " ".join(value.split())
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub("<redacted>", text)
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def validate_command(argv: tuple[str, ...]) -> None:
    lowered = tuple(part.strip().lower() for part in argv)
    for token in lowered:
        if token in PROHIBITED_COMMAND_TOKENS:
            raise CommandValidationError(f"prohibited command token: {token}")

    if argv not in ALLOWED_COMMANDS.values():
        raise CommandValidationError("command is not in the C3 read-only allowlist")


def run_allowed_command(key: str) -> CommandResult:
    argv = ALLOWED_COMMANDS[key]
    validate_command(argv)

    executable = shutil.which(argv[0])
    if executable is None:
        return CommandResult(key=key, argv=argv, status="unavailable", returncode=127)

    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(key=key, argv=argv, status="timeout", returncode=None)
    except OSError:
        return CommandResult(key=key, argv=argv, status="error", returncode=None)

    stdout = completed.stdout if completed.stdout else ""
    stderr = sanitize_text(completed.stderr if completed.stderr else "")
    status = "ok" if completed.returncode == 0 else "error"
    return CommandResult(
        key=key,
        argv=argv,
        status=status,
        stdout=stdout,
        stderr=stderr,
        returncode=completed.returncode,
    )


def nm_state_is_connected(state: str) -> bool:
    normalized = state.strip().lower()
    return normalized == "connected" or normalized.startswith("connected ")


def split_nmcli_line(line: str, expected_parts: int) -> list[str] | None:
    parts = line.rstrip("\n").split(":")
    if len(parts) < expected_parts:
        return None
    if expected_parts == 3:
        return [":".join(parts[:-2]), parts[-2], parts[-1]]
    return parts


def parse_nmcli_device_status(output: str) -> dict[str, Any]:
    wifi_count = 0
    wifi_connected = False
    ethernet_connected = False
    wifi_devices: set[str] = set()

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = split_nmcli_line(line, 3)
        if parts is None:
            continue
        device, device_type, state = (part.strip() for part in parts)
        kind = device_type.lower()
        if kind == "wifi":
            wifi_count += 1
            if device:
                wifi_devices.add(device)
            if nm_state_is_connected(state):
                wifi_connected = True
        elif kind == "ethernet" and nm_state_is_connected(state):
            ethernet_connected = True

    return {
        "wifi_count": wifi_count,
        "wifi_connected": wifi_connected,
        "ethernet_connected": ethernet_connected,
        "wifi_devices": wifi_devices,
    }


def parse_nmcli_active_connections(output: str) -> dict[str, bool]:
    wifi_active = False
    ethernet_active = False

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = split_nmcli_line(line, 3)
        if parts is None:
            continue
        connection_type = parts[1].strip().lower()
        if connection_type in {"wifi", "802-11-wireless"} or "wireless" in connection_type:
            wifi_active = True
        if connection_type in {"ethernet", "802-3-ethernet"} or "ethernet" in connection_type:
            ethernet_active = True

    return {"wifi_active": wifi_active, "ethernet_active": ethernet_active}


def parse_iw_dev(output: str) -> dict[str, Any]:
    interfaces: set[str] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("Interface "):
            name = line.split(None, 1)[1].strip()
            if name:
                interfaces.add(name)
    return {"wifi_count": len(interfaces), "wifi_devices": interfaces}


def line_has_non_loopback_ip(line: str) -> bool:
    parts = line.split()
    if not parts:
        return False
    interface_name = parts[0]
    if interface_name == "lo":
        return False

    for part in parts[2:]:
        address = part.split("/", 1)[0]
        if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", address):
            if not address.startswith("127.") and not address.startswith("169.254."):
                return True
        if ":" in address:
            lowered = address.lower()
            if lowered != "::1" and not lowered.startswith("fe80:"):
                return True
    return False


def parse_ip_brief_addr(output: str) -> dict[str, bool]:
    has_local_ip = any(line_has_non_loopback_ip(line) for line in output.splitlines())
    return {"has_local_ip": has_local_ip}


def parse_default_route(output: str) -> dict[str, bool]:
    has_default_route = any(line.strip().startswith("default") for line in output.splitlines())
    return {"has_default_route": has_default_route}


def public_warning_for(result: CommandResult) -> str | None:
    key = result.key.upper()
    if result.status == "ok":
        return None
    if result.status == "unavailable":
        return f"{key}_UNAVAILABLE"
    if result.status == "timeout":
        return f"{key}_TIMEOUT"
    return f"{key}_ERROR"


def unknown_bool() -> str:
    return "unknown"


def build_status(results: dict[str, CommandResult]) -> dict[str, Any]:
    warnings: set[str] = set()
    for result in results.values():
        warning = public_warning_for(result)
        if warning:
            warnings.add(warning)

    nmcli_available = shutil.which("nmcli") is not None
    ip_available = shutil.which("ip") is not None
    iw_available = shutil.which("iw") is not None

    nm_device = results["nmcli_device_status"]
    nm_active = results["nmcli_active_connections"]
    ip_brief = results["ip_brief_addr"]
    ip_route = results["ip_default_route"]
    iw_dev = results["iw_dev"]

    networkmanager_observed: bool | str
    ethernet_connected: bool | str = unknown_bool()
    wifi_connected: bool | str = unknown_bool()
    wifi_device_count = 0

    if nm_device.status == "ok":
        networkmanager_observed = True
        parsed_nm_device = parse_nmcli_device_status(nm_device.stdout)
        wifi_device_count = parsed_nm_device["wifi_count"]
        wifi_connected = parsed_nm_device["wifi_connected"]
        ethernet_connected = parsed_nm_device["ethernet_connected"]
    elif not nmcli_available:
        networkmanager_observed = unknown_bool()
    else:
        networkmanager_observed = unknown_bool()

    if nm_active.status == "ok":
        active = parse_nmcli_active_connections(nm_active.stdout)
        if active["wifi_active"]:
            wifi_connected = True
        if active["ethernet_active"]:
            ethernet_connected = True

    if iw_dev.status == "ok":
        parsed_iw = parse_iw_dev(iw_dev.stdout)
        wifi_device_count = max(wifi_device_count, parsed_iw["wifi_count"])

    has_local_ip: bool | str = unknown_bool()
    if ip_brief.status == "ok":
        has_local_ip = parse_ip_brief_addr(ip_brief.stdout)["has_local_ip"]

    has_default_route: bool | str = unknown_bool()
    if ip_route.status == "ok":
        has_default_route = parse_default_route(ip_route.stdout)["has_default_route"]

    if wifi_device_count == 0 and iw_available is False and nm_device.status != "ok":
        warnings.add("WIFI_DEVICE_COUNT_UNKNOWN")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "nmcli_available": nmcli_available,
        "ip_available": ip_available,
        "iw_available": iw_available,
        "networkmanager_observed": networkmanager_observed,
        "ethernet_connected": ethernet_connected,
        "wifi_device_count": wifi_device_count,
        "wifi_connected": wifi_connected,
        "has_local_ip": has_local_ip,
        "has_default_route": has_default_route,
        "dns_state": "not_checked",
        "internet_state": "not_checked",
        "backend_state": "not_checked",
        "warnings": sorted(warnings),
        "command_results": {key: result.status for key, result in results.items()},
        "privacy": {
            "ssid": "omitted",
            "ip_address": "omitted",
            "mac_address": "omitted",
            "bssid": "omitted",
            "hostname": "omitted",
            "connection_name": "omitted",
            "gateway": "omitted",
            "dns_server": "omitted",
            "raw_command_output": "omitted",
        },
    }


def format_summary(status: dict[str, Any]) -> str:
    lines = [
        "Dadooh C3 Wi-Fi read-only snapshot",
        f"schema_version: {status['schema_version']}",
        f"generated_at: {status['generated_at']}",
        "",
        "Aggregated state:",
        f"- nmcli_available: {status['nmcli_available']}",
        f"- ip_available: {status['ip_available']}",
        f"- iw_available: {status['iw_available']}",
        f"- networkmanager_observed: {status['networkmanager_observed']}",
        f"- ethernet_connected: {status['ethernet_connected']}",
        f"- wifi_device_count: {status['wifi_device_count']}",
        f"- wifi_connected: {status['wifi_connected']}",
        f"- has_local_ip: {status['has_local_ip']}",
        f"- has_default_route: {status['has_default_route']}",
        f"- dns_state: {status['dns_state']}",
        f"- internet_state: {status['internet_state']}",
        f"- backend_state: {status['backend_state']}",
        "",
        "Warnings:",
    ]

    warnings = status.get("warnings") or []
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "Privacy:",
            "- SSID, IP, MAC, BSSID, hostname, connection name, gateway, DNS server and raw command output were omitted.",
            "- No external network probe, ping, socket, hotspot or backend call was executed.",
            "- No NetworkManager mutation command was executed.",
        ]
    )
    return "\n".join(lines)


def run_snapshot(out_dir: pathlib.Path) -> dict[str, Any]:
    prepare_out_dir(out_dir)
    results = {key: run_allowed_command(key) for key in ALLOWED_COMMANDS}
    status = build_status(results)

    status_json = json.dumps(status, indent=2, ensure_ascii=True) + "\n"
    summary = format_summary(status) + "\n"

    write_private_text(out_dir / "status.json", status_json)
    write_private_text(out_dir / "summary.txt", summary)
    return status


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_self_test() -> None:
    sensitive_values = {
        "ssid": "ClientePrivadoWiFi",
        "ip": "192.168.55.44",
        "mac": "aa:bb:cc:dd:ee:ff",
        "url": "https://backend.privado.example/internal",
        "api_key": "sk_fake_private_api_key_123",
        "token": "tok_fake_private_456",
        "path": "/data/media/kiosky-player/private.mp4",
        "hostname": "totem-private-01",
    }
    sample = (
        f"SSID={sensitive_values['ssid']} "
        f"ip={sensitive_values['ip']} "
        f"mac={sensitive_values['mac']} "
        f"url={sensitive_values['url']} "
        f"api_key={sensitive_values['api_key']} "
        f"token={sensitive_values['token']} "
        f"path={sensitive_values['path']} "
        f"hostname={sensitive_values['hostname']}"
    )
    sanitized = sanitize_text(sample, max_len=1000)
    for name, value in sensitive_values.items():
        assert_true(value not in sanitized, f"sanitizer leaked {name}")
    assert_true("/data/media" not in sanitized, "sanitizer leaked /data/media")
    assert_true("api_key" not in sanitized.lower(), "sanitizer leaked api_key label")
    assert_true("token" not in sanitized.lower(), "sanitizer leaked token label")

    try:
        require_tmp_dir("/data/not-allowed")
    except ValueError:
        pass
    else:
        raise AssertionError("out-dir outside /tmp was accepted")

    prohibited_commands = (
        ("nmcli", "connection", "up", "private"),
        ("nmcli", "connection", "down", "private"),
        ("nmcli", "connection", "modify", "private", "autoconnect", "yes"),
        ("nmcli", "connection", "delete", "private"),
        ("nmcli", "device", "wifi", "connect", "private"),
        ("nmcli", "device", "disconnect", "wlan0"),
        ("rfkill", "unblock", "wifi"),
        ("ip", "route", "add", "default", "via", "192.0.2.1"),
    )
    for command in prohibited_commands:
        try:
            validate_command(command)
        except CommandValidationError:
            continue
        raise AssertionError(f"prohibited command was accepted: {command}")

    for command in ALLOWED_COMMANDS.values():
        validate_command(command)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a sanitized read-only C3 Wi-Fi/network snapshot under /tmp.",
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"dedicated output directory under /tmp (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run offline sanitizer and command-validation self-tests",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if args.self_test:
        try:
            run_self_test()
        except AssertionError as exc:
            print(f"self-test: failed: {exc}", file=sys.stderr)
            return 1
        print("self-test: ok")
        return 0

    try:
        out_dir = require_tmp_dir(args.out_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        run_snapshot(out_dir)
    except CommandValidationError as exc:
        print(f"error: command validation failed: {exc}", file=sys.stderr)
        return 3

    print(f"wrote sanitized C3 Wi-Fi snapshot to {out_dir}")
    print("files: status.json summary.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
