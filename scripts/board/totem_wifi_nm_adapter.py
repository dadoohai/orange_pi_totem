#!/usr/bin/env python3
"""C9.6 controlled NetworkManager Wi-Fi adapter.

Read-only and plan modes remain non-invasive. Real apply is available only with
explicit gates, a restricted temporary secrets file, a dedicated product
profile, timeout, rollback, and sanitized artifacts under /tmp.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import pathlib
import re
import selectors
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Any, Callable


sys.dont_write_bytecode = True


SCHEMA_VERSION = "dadooh-c9.6-wifi-controlled-apply.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c9-6-wifi-apply"
STATUS_FILENAME = "status.json"
PLAN_FILENAME = "plan.json"
SUMMARY_FILENAME = "summary.txt"
PREFLIGHT_FILENAME = "preflight.json"
ROLLBACK_FILENAME = "rollback.json"
DIAGNOSE_FILENAME = "diagnose-status.json"
DIAGNOSE_SUMMARY_FILENAME = "diagnose-summary.txt"
TMP_ROOT = pathlib.Path("/tmp").resolve()
SYSTEM_CONNECTION_DIR = pathlib.Path("/etc/NetworkManager/system-connections")
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
UNKNOWN = "unknown"
CONFIRM_REAL_WIFI_APPLY = "CONFIRMO APPLY WIFI REAL C9.6 EM BANCADA"
CONFIRM_REAL_WIFI_APPLY_LOCAL_CONSOLE = "CONFIRMO APPLY WIFI REAL C9.6 COM CONSOLE LOCAL"
CONFIRM_KEEP_DEDICATED_PROFILE = "CONFIRMO MANTER WIFI DEDICADO C9.8"
DEFAULT_PROFILE_NAME = "dadooh-c9-6-wifi-test"
DEFAULT_PERSISTENT_PROFILE_NAME = "dadooh-c9-8-wifi-persistent"
ALLOWED_PROFILE_PREFIXES = ("dadooh-c9-6-", "dadooh-c9-8-", "dadooh-product-wifi-")
PERSISTENT_PROFILE_PREFIXES = ("dadooh-c9-8-", "dadooh-product-wifi-")

ALLOWED_READ_ONLY_COMMANDS = {
    ("ip", "-j", "-4", "route", "show", "table", "main", "default"),
    ("nmcli", "-t", "-f", "RUNNING", "general"),
    ("nmcli", "-t", "-f", "CONNECTIVITY", "general"),
    ("nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"),
    ("nmcli", "-t", "-f", "TYPE,DEVICE", "connection", "show", "--active"),
    ("nmcli", "-t", "-f", "NAME", "connection", "show", "--active"),
    ("nmcli", "-t", "-f", "DEVICE,IN-USE,SIGNAL", "device", "wifi", "list", "--rescan", "no"),
    ("nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "no"),
    ("nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes"),
}

IP_ROUTE_DEFAULT_COMMAND = ["ip", "-j", "-4", "route", "show", "table", "main", "default"]
MAX_ROUTE_JSON_BYTES = 64 * 1024
MAX_ROUTE_JSON_ENTRIES = 64
MAX_READ_ONLY_COMMAND_OUTPUT_BYTES = 64 * 1024
READ_ONLY_COMMAND_CHUNK_BYTES = 8 * 1024

SENSITIVE_MARKERS = (
    "FAKE-STORE-WIFI",
    "fake-password",
    "fake-psk-value",
    "192.0.2.44",
    "192.0.2.1",
    "203.0.113.53",
    "aa:bb:cc:dd:ee:ff",
    "11:22:33:44:55:66",
    "fake-hostname",
    "Fake product wifi",
    "fake-uuid-value",
    "fake-token-value",
    "fake-api-key",
)


class AdapterError(RuntimeError):
    """Public-safe adapter error."""


class CommandResult:
    def __init__(self, status: str, stdout: str = "", stderr: str = "", returncode: int | None = None) -> None:
        self.status = status
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def utc_timestamp() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def path_is_under(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root)
        return True
    except ValueError:
        return False


def require_tmp_dir(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path)
    if not path.is_absolute():
        raise AdapterError("out-dir must be an absolute path under /tmp")
    resolved = path.resolve(strict=False)
    if resolved == TMP_ROOT or not path_is_under(resolved, TMP_ROOT):
        raise AdapterError("out-dir must be under /tmp")
    return resolved


def prepare_out_dir(out_dir: pathlib.Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if not out_dir.is_dir():
        raise AdapterError("out-dir is not a directory")
    if not path_is_under(out_dir, TMP_ROOT):
        raise AdapterError("out-dir must stay under /tmp")
    os.chmod(out_dir, PRIVATE_DIR_MODE)


def atomic_write_private_text(path: pathlib.Path, text: str, out_dir: pathlib.Path) -> None:
    if path.parent != out_dir:
        raise AdapterError("artifact path must be inside out-dir")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(out_dir), text=True)
    tmp_path = pathlib.Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp_path, PRIVATE_FILE_MODE)
        os.replace(tmp_path, path)
        os.chmod(path, PRIVATE_FILE_MODE)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def atomic_write_private_json(path: pathlib.Path, payload: dict[str, Any], out_dir: pathlib.Path) -> None:
    atomic_write_private_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n", out_dir)


def file_mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def command_is_forbidden(args: list[str]) -> bool:
    if not args:
        return True
    lowered = [part.lower() for part in args]
    command = lowered[0]

    if command == "nmcli":
        if len(lowered) >= 3 and lowered[1] == "connection" and lowered[2] in {"up", "down", "delete", "modify"}:
            return True
        if len(lowered) >= 4 and lowered[1:4] == ["device", "wifi", "connect"]:
            return True
        if len(lowered) >= 3 and lowered[1] == "radio" and lowered[2] in {"on", "off", "wifi"}:
            return True
        return False

    if command == "systemctl" and any(part == "networkmanager" for part in lowered):
        return any(action in lowered for action in {"restart", "start", "stop", "reload", "try-restart"})

    if command in {"ifdown", "ifup"}:
        return True

    if command == "ip" and "link" in lowered and "set" in lowered:
        return "down" in lowered or "up" in lowered

    return False


def assert_read_only_command(args: list[str]) -> None:
    if command_is_forbidden(args):
        raise AdapterError("network modifying command blocked")
    if tuple(args) not in ALLOWED_READ_ONLY_COMMANDS:
        raise AdapterError("command is not in the C9.5 read-only allowlist")


def run_read_only_command(args: list[str], timeout_sec: float) -> CommandResult:
    assert_read_only_command(args)
    try:
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=read_only_command_env(),
        )
    except FileNotFoundError:
        return CommandResult("unavailable")
    except OSError:
        return CommandResult("failed")

    deadline = time.monotonic() + max(0.05, float(timeout_sec))
    selector = selectors.DefaultSelector()
    stdout = bytearray()
    stderr = bytearray()
    streams = ((process.stdout, stdout), (process.stderr, stderr))

    def kill_and_wait() -> None:
        if process.poll() is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        process.wait()

    try:
        for stream, buffer in streams:
            if stream is not None:
                selector.register(stream, selectors.EVENT_READ, buffer)

        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                kill_and_wait()
                return CommandResult("timeout")
            events = selector.select(remaining)
            if not events:
                kill_and_wait()
                return CommandResult("timeout")
            for key, _ in events:
                try:
                    chunk = os.read(key.fileobj.fileno(), READ_ONLY_COMMAND_CHUNK_BYTES)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                key.data.extend(chunk)
                if len(stdout) + len(stderr) > MAX_READ_ONLY_COMMAND_OUTPUT_BYTES:
                    kill_and_wait()
                    return CommandResult("too_large")

        remaining = max(0.05, deadline - time.monotonic())
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            kill_and_wait()
            return CommandResult("timeout")
    finally:
        selector.close()
        for stream, _ in streams:
            if stream is not None:
                stream.close()

    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")
    status = "ok" if returncode == 0 else "failed"
    return CommandResult(status, stdout_text, stderr_text, returncode)


def read_only_command_env() -> dict[str, str]:
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return env


def run_internal_command(args: list[str], timeout_sec: int) -> CommandResult:
    try:
        completed = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except FileNotFoundError:
        return CommandResult("unavailable")
    except subprocess.TimeoutExpired:
        return CommandResult("timeout")
    except OSError:
        return CommandResult("failed")

    if completed.returncode == 0:
        return CommandResult("ok", completed.stdout, completed.stderr, completed.returncode)
    return CommandResult("failed", completed.stdout, completed.stderr, completed.returncode)


def profile_name_allowed(profile_name: str) -> bool:
    if not (1 <= len(profile_name) <= 80):
        return False
    if not profile_name.startswith(ALLOWED_PROFILE_PREFIXES):
        return False
    return all(char.isalnum() or char in "._:-" for char in profile_name)


def require_allowed_profile_name(profile_name: str) -> str:
    cleaned = profile_name.strip()
    if not profile_name_allowed(cleaned):
        raise AdapterError("profile-name not allowed")
    return cleaned


def persistent_profile_name_allowed(profile_name: str) -> bool:
    return profile_name_allowed(profile_name) and profile_name.startswith(PERSISTENT_PROFILE_PREFIXES)


def require_persistent_profile_name(profile_name: str) -> str:
    cleaned = require_allowed_profile_name(profile_name)
    if not persistent_profile_name_allowed(cleaned):
        raise AdapterError("persistent profile-name not allowed")
    return cleaned


def deterministic_profile_uuid(profile_name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"dadooh-wifi-profile:{profile_name}"))


def command_targets_dedicated_profile(args: list[str], profile_name: str) -> bool:
    return profile_name in args and profile_name_allowed(profile_name)


def assert_apply_command(args: list[str], profile_name: str, keyfile_path: pathlib.Path | None = None) -> None:
    if not args:
        raise AdapterError("empty command blocked")
    lowered = [part.lower() for part in args]

    if lowered[:3] == ["nmcli", "connection", "load"]:
        if keyfile_path is None or args != ["nmcli", "connection", "load", str(keyfile_path)]:
            raise AdapterError("apply command blocked")
        return

    if lowered[:4] == ["nmcli", "connection", "delete", "id"]:
        if args == ["nmcli", "connection", "delete", "id", profile_name]:
            return
        raise AdapterError("apply command blocked")

    if lowered[:4] == ["nmcli", "connection", "down", "id"]:
        if args == ["nmcli", "connection", "down", "id", profile_name]:
            return
        raise AdapterError("apply command blocked")

    if len(args) >= 7 and lowered[:2] == ["nmcli", "--wait"] and lowered[3:6] == ["connection", "up", "id"]:
        if args[6] == profile_name:
            return
        raise AdapterError("apply command blocked")

    if lowered[:5] == ["nmcli", "-t", "-f", "connection.id", "connection"]:
        if args == ["nmcli", "-t", "-f", "connection.id", "connection", "show", profile_name]:
            return
        raise AdapterError("apply command blocked")

    if lowered[:5] == ["nmcli", "-t", "-f", "ip4.address", "connection"]:
        if args == ["nmcli", "-t", "-f", "IP4.ADDRESS", "connection", "show", profile_name]:
            return
        raise AdapterError("apply command blocked")

    raise AdapterError("apply command blocked")


def run_apply_command(
    args: list[str],
    timeout_sec: int,
    profile_name: str,
    keyfile_path: pathlib.Path | None = None,
) -> CommandResult:
    assert_apply_command(args, profile_name, keyfile_path)
    return run_internal_command(args, timeout_sec)


def split_nmcli_terse(line: str) -> list[str]:
    fields: list[str] = []
    buffer: list[str] = []
    escaped = False
    for char in line.rstrip("\n"):
        if escaped:
            buffer.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == ":":
            fields.append("".join(buffer))
            buffer = []
            continue
        buffer.append(char)
    fields.append("".join(buffer))
    return fields


def tri_bool(value: bool | str) -> bool | str:
    if isinstance(value, bool):
        return value
    return UNKNOWN


def merge_tri_bool(*values: bool | str) -> bool | str:
    if any(value is True for value in values):
        return True
    if values and all(value is False for value in values):
        return False
    return UNKNOWN


def type_is_ethernet(raw_type: str, device_name: str = "") -> bool:
    lowered_type = raw_type.strip().lower()
    lowered_device = device_name.strip().lower()
    return lowered_type in {"ethernet", "802-3-ethernet"} or lowered_device.startswith(("eth", "en"))


def type_is_wifi(raw_type: str, device_name: str = "") -> bool:
    lowered_type = raw_type.strip().lower()
    lowered_device = device_name.strip().lower()
    return lowered_type in {"wifi", "802-11-wireless"} or lowered_device.startswith(("wl", "wlan"))


def state_is_connected(raw_state: str) -> bool:
    return raw_state.strip().lower() in {"connected", "activated"}


def parse_nmcli_running(stdout: str) -> bool | str:
    lowered = stdout.strip().lower()
    if not lowered:
        return UNKNOWN
    if "not running" in lowered or "stopped" in lowered:
        return False
    if "running" in lowered:
        return True
    return UNKNOWN


def parse_device_status(stdout: str) -> dict[str, Any]:
    wifi_present = False
    ethernet_active = False
    wifi_active = False
    ethernet_connected_devices: set[str] = set()
    wifi_connected_devices: set[str] = set()
    parsed = False

    for raw_line in stdout.splitlines():
        if not raw_line.strip():
            continue
        fields = split_nmcli_terse(raw_line)
        if len(fields) < 3:
            continue
        parsed = True
        device_name, device_type, state = fields[:3]
        if type_is_wifi(device_type, device_name):
            wifi_present = True
            if state_is_connected(state):
                wifi_active = True
                wifi_connected_devices.add(device_name)
        if type_is_ethernet(device_type, device_name) and state_is_connected(state):
            ethernet_active = True
            ethernet_connected_devices.add(device_name)

    if not parsed:
        return {
            "wifi_device_present": UNKNOWN,
            "ethernet_active": UNKNOWN,
            "wifi_active": UNKNOWN,
            "ethernet_connected_devices": [],
            "wifi_connected_devices": [],
        }

    return {
        "wifi_device_present": wifi_present,
        "ethernet_active": ethernet_active,
        "wifi_active": wifi_active,
        "ethernet_connected_devices": sorted(ethernet_connected_devices),
        "wifi_connected_devices": sorted(wifi_connected_devices),
    }


def parse_active_connections(stdout: str) -> dict[str, Any]:
    ethernet_active = False
    wifi_active = False
    ethernet_active_devices: set[str] = set()
    wifi_active_devices: set[str] = set()
    parsed = False

    for raw_line in stdout.splitlines():
        if not raw_line.strip():
            continue
        fields = split_nmcli_terse(raw_line)
        if len(fields) < 2:
            continue
        parsed = True
        connection_type, device_name = fields[:2]
        if type_is_wifi(connection_type, device_name):
            wifi_active = True
            wifi_active_devices.add(device_name)
        if type_is_ethernet(connection_type, device_name):
            ethernet_active = True
            ethernet_active_devices.add(device_name)

    if not parsed:
        return {
            "ethernet_active": False,
            "wifi_active": False,
            "ethernet_active_devices": [],
            "wifi_active_devices": [],
        }

    return {
        "ethernet_active": ethernet_active,
        "wifi_active": wifi_active,
        "ethernet_active_devices": sorted(ethernet_active_devices),
        "wifi_active_devices": sorted(wifi_active_devices),
    }


def signal_bucket(raw_signal: str | int | None) -> str:
    try:
        value = int(str(raw_signal or "").strip())
    except ValueError:
        return UNKNOWN
    if value >= 70:
        return "strong"
    if value >= 40:
        return "medium"
    return "weak"


def parse_nmcli_connectivity(stdout: str) -> str:
    lines = [raw_line.strip() for raw_line in stdout.splitlines() if raw_line.strip()]
    if len(lines) != 1:
        return UNKNOWN
    fields = split_nmcli_terse(lines[0])
    if len(fields) != 1:
        return UNKNOWN
    value = fields[0].strip().lower()
    return value if value in {"full", "limited", "portal", "none"} else UNKNOWN


def parse_active_wifi_signal(stdout: str, *, expected_device: str = "") -> str:
    active_signals: list[int] = []
    for raw_line in stdout.splitlines():
        if not raw_line.strip():
            continue
        fields = split_nmcli_terse(raw_line)
        if len(fields) != 3:
            continue
        device, in_use, signal = fields
        if in_use.strip().lower() in {"*", "yes", "true"}:
            if expected_device and device.strip() != expected_device:
                continue
            try:
                value = int(signal.strip())
            except ValueError:
                return UNKNOWN
            if value < 0 or value > 100:
                return UNKNOWN
            active_signals.append(value)
    if len(active_signals) != 1:
        return UNKNOWN
    return signal_bucket(active_signals[0])


def security_present(raw_security: str | None) -> bool | str:
    cleaned = (raw_security or "").strip()
    if not cleaned or cleaned in {"--", "none", "NONE"}:
        return False
    return True


def parse_wifi_network_list(stdout: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Parse nmcli Wi-Fi list for local UI use.

    The returned dictionaries intentionally keep SSID only for the local HDMI UI.
    Callers must not write these dictionaries to public status or evidence.
    """

    by_ssid: dict[str, dict[str, Any]] = {}
    for raw_line in stdout.splitlines():
        if not raw_line.strip():
            continue
        fields = split_nmcli_terse(raw_line)
        if len(fields) < 3:
            continue
        ssid, signal, security = fields[:3]
        ssid = ssid.strip()
        if not ssid:
            continue
        bucket = signal_bucket(signal)
        try:
            signal_value = int(signal)
        except ValueError:
            signal_value = -1
        item = {
            "ssid": ssid,
            "signal_bucket": bucket,
            "security_present": security_present(security),
            "_signal_value": signal_value,
        }
        previous = by_ssid.get(ssid)
        if previous is None or signal_value > int(previous.get("_signal_value", -1)):
            by_ssid[ssid] = item

    networks = sorted(by_ssid.values(), key=lambda item: int(item.get("_signal_value", -1)), reverse=True)
    public_safe: list[dict[str, Any]] = []
    limited_networks = networks if limit is None else networks[: max(0, int(limit))]
    for item in limited_networks:
        public_safe.append(
            {
                "ssid": str(item["ssid"]),
                "signal_percent": max(0, min(100, int(item.get("_signal_value", -1)))),
                "signal_bucket": str(item["signal_bucket"]),
                "security_present": item["security_present"],
            }
        )
    return public_safe


def list_wifi_networks_for_local_ui(
    *,
    timeout_sec: int = 8,
    command_runner: Callable[[list[str], int], CommandResult] = run_read_only_command,
    nmcli_path: str | None = None,
    rescan: bool = False,
) -> tuple[list[dict[str, Any]], str]:
    """Return SSIDs for local operator display only.

    This function never writes artifacts and uses only the read-only nmcli
    allowlist. The caller is responsible for keeping SSIDs out of status,
    summary, docs and evidence.
    """

    if nmcli_path is None:
        nmcli_path = shutil.which("nmcli")
    if not nmcli_path:
        return [], "nmcli_unavailable"
    command = [
        "nmcli",
        "-t",
        "-f",
        "SSID,SIGNAL,SECURITY",
        "device",
        "wifi",
        "list",
        "--rescan",
        "yes" if rescan else "no",
    ]
    result = command_runner(command, timeout_sec)
    if result.status != "ok":
        return [], result.status
    return parse_wifi_network_list(result.stdout), "ok"


def wifi_selection_public_metadata(networks: list[dict[str, Any]], selected: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "wifi_networks_found_count": len(networks),
        "selected_network_present": selected is not None,
        "selected_network_signal_bucket": str(selected.get("signal_bucket", UNKNOWN)) if selected else UNKNOWN,
        "selected_network_security_present": selected.get("security_present", UNKNOWN) if selected else UNKNOWN,
    }


PROC_NET_ROUTE_HEADER = (
    "Iface",
    "Destination",
    "Gateway",
    "Flags",
    "RefCnt",
    "Use",
    "Metric",
    "Mask",
    "MTU",
    "Window",
    "IRTT",
)


def parse_default_route_candidate(parts: list[str]) -> tuple[str, int] | None:
    if len(parts) != len(PROC_NET_ROUTE_HEADER):
        return None
    device, destination, gateway, flags = parts[:4]
    mask = parts[7]
    if not device or len(device) > 15:
        return None
    if destination != "00000000" or mask != "00000000":
        return None
    if not re.fullmatch(r"[0-9A-F]{8}", gateway):
        return None
    if not re.fullmatch(r"[0-9A-F]{4,8}", flags):
        return None
    route_flags = int(flags, 16)
    if flags != f"{route_flags:04X}":
        return None
    decimal_fields = parts[4:7] + parts[8:11]
    if any(len(value) > 20 or not re.fullmatch(r"0|[1-9][0-9]*", value) for value in decimal_fields):
        return None
    if len(parts[6]) > 10 or int(parts[6], 10) > 0xFFFFFFFF:
        return None

    rtf_up = 0x1
    rtf_gateway = 0x2
    rtf_host = 0x4
    rtf_reject = 0x200
    supported_flags = 0x1 | 0x2 | 0x8 | 0x10 | 0x20 | 0x40 | 0x80 | 0x100
    if (
        not route_flags & rtf_up
        or route_flags & (rtf_host | rtf_reject)
        or route_flags & ~supported_flags
    ):
        return None

    gateway_value = int(gateway, 16)
    uses_gateway = bool(route_flags & rtf_gateway)
    if uses_gateway != (gateway_value != 0):
        return None
    return device, int(parts[6], 10)


def detect_default_route_from_text(text: str) -> bool | str:
    return bool(default_route_devices_from_text(text))


def default_route_devices_from_text(text: str) -> list[str]:
    lines = text.splitlines()
    if len(lines) < 2 or tuple(lines[0].split()) != PROC_NET_ROUTE_HEADER:
        return []
    candidates: list[tuple[str, int]] = []
    for line in lines[1:]:
        candidate = parse_default_route_candidate(line.split())
        if candidate is not None:
            candidates.append(candidate)
    if not candidates:
        return []
    best_metric = min(metric for _, metric in candidates)
    return sorted({device for device, metric in candidates if metric == best_metric})


def default_route_device_from_text(text: str) -> str:
    devices = default_route_devices_from_text(text)
    return devices[0] if len(devices) == 1 else ""


def default_route_devices_from_ip_json(text: str) -> list[str]:
    if not isinstance(text, str) or not text or len(text) > MAX_ROUTE_JSON_BYTES:
        return []
    try:
        if len(text.encode("utf-8")) > MAX_ROUTE_JSON_BYTES:
            return []
        routes = json.loads(text)
    except (ValueError, UnicodeError):
        return []
    if not isinstance(routes, list) or not routes or len(routes) > MAX_ROUTE_JSON_ENTRIES:
        return []

    allowed_keys = {
        "dev",
        "dst",
        "flags",
        "gateway",
        "metric",
        "prefsrc",
        "protocol",
        "scope",
        "table",
        "type",
    }
    candidates: list[tuple[int, str]] = []
    for route in routes:
        if not isinstance(route, dict) or set(route) - allowed_keys or route.get("dst") != "default":
            return []
        route_type = route.get("type", "unicast")
        table = route.get("table", "main")
        metric = route.get("metric", 0)
        device = route.get("dev")
        scope = route.get("scope")
        gateway = route.get("gateway")
        protocol = route.get("protocol")
        preferred_source = route.get("prefsrc")
        flags = route.get("flags", [])
        table_is_main = table == "main" or (
            isinstance(table, int) and not isinstance(table, bool) and table == 254
        )
        if route_type != "unicast" or not table_is_main:
            return []
        if isinstance(metric, bool) or not isinstance(metric, int) or not 0 <= metric <= 0xFFFFFFFF:
            return []
        if not isinstance(device, str) or not re.fullmatch(r"[A-Za-z0-9_.:@-]{1,15}", device) or device == "*":
            return []
        if scope not in {None, "global", "link"}:
            return []
        if flags != []:
            return []
        if protocol is not None and (
            not isinstance(protocol, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", protocol)
        ):
            return []
        if preferred_source is not None and not valid_ipv4_route_address(preferred_source):
            return []
        if gateway is not None:
            if scope == "link" or not valid_ipv4_route_address(gateway, reject_reserved=True):
                return []
        elif scope != "link":
            return []
        candidates.append((metric, device))

    best_metric = min(metric for metric, _ in candidates)
    best_routes = [device for metric, device in candidates if metric == best_metric]
    return best_routes if len(best_routes) == 1 else []


def valid_ipv4_route_address(value: Any, *, reject_reserved: bool = False) -> bool:
    if not isinstance(value, str):
        return False
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        return False
    if address.is_unspecified or address.is_loopback or address.is_multicast:
        return False
    if reject_reserved and address.is_reserved:
        return False
    return True


def command_result_stdout_is_bounded(result: CommandResult) -> bool:
    if result.status != "ok" or len(result.stdout) > MAX_READ_ONLY_COMMAND_OUTPUT_BYTES:
        return False
    try:
        return len(result.stdout.encode("utf-8")) <= MAX_READ_ONLY_COMMAND_OUTPUT_BYTES
    except UnicodeError:
        return False


def detect_dns_from_text(text: str) -> bool | str:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "nameserver":
            return True
    return False


def read_text_if_present(path: pathlib.Path) -> tuple[str, bool]:
    try:
        return path.read_text(encoding="utf-8"), True
    except OSError:
        return "", False


def bool_for_json(value: bool | str) -> bool | str:
    if isinstance(value, bool):
        return value
    return UNKNOWN


def public_privacy_flags() -> dict[str, bool]:
    return {
        "network_changed": False,
        "credentials_collected": False,
        "ssid_written": False,
        "password_written": False,
        "ip_written": False,
        "mac_written": False,
        "bssid_written": False,
        "gateway_written": False,
        "dns_written": False,
        "hostname_written": False,
        "connection_name_written": False,
        "nmcli_modify_called": False,
        "writer_called": False,
        "real_config_read": False,
        "real_config_written": False,
        "player_changed": False,
        "mpv_changed": False,
    }


def collect_read_only_status(
    *,
    timeout_sec: int,
    command_runner: Callable[[list[str], int], CommandResult] = run_read_only_command,
    file_reader: Callable[[pathlib.Path], tuple[str, bool]] = read_text_if_present,
    nmcli_path: str | None = None,
) -> dict[str, Any]:
    if nmcli_path is None:
        nmcli_path = shutil.which("nmcli")

    checks = {
        "nmcli_general": "not_run",
        "nmcli_device_status": "not_run",
        "nmcli_active_connections": "not_run",
        "default_route": "not_run",
        "resolver": "not_run",
    }
    nmcli_available = bool(nmcli_path)
    network_manager_available: bool | str = False if not nmcli_available else UNKNOWN
    device_status = {
        "wifi_device_present": UNKNOWN,
        "ethernet_active": UNKNOWN,
        "wifi_active": UNKNOWN,
    }
    active_connections = {
        "ethernet_active": UNKNOWN,
        "wifi_active": UNKNOWN,
    }

    if nmcli_available:
        general_result = command_runner(["nmcli", "-t", "-f", "RUNNING", "general"], timeout_sec)
        checks["nmcli_general"] = general_result.status
        if general_result.status == "ok":
            network_manager_available = parse_nmcli_running(general_result.stdout)

        device_result = command_runner(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"], timeout_sec)
        checks["nmcli_device_status"] = device_result.status
        if device_result.status == "ok":
            device_status = parse_device_status(device_result.stdout)

        active_result = command_runner(
            ["nmcli", "-t", "-f", "TYPE,DEVICE", "connection", "show", "--active"],
            timeout_sec,
        )
        checks["nmcli_active_connections"] = active_result.status
        if active_result.status == "ok":
            active_connections = parse_active_connections(active_result.stdout)

    route_text, route_available = file_reader(pathlib.Path("/proc/net/route"))
    default_route_present = detect_default_route_from_text(route_text) if route_available else UNKNOWN
    checks["default_route"] = "ok" if route_available else "unavailable"

    resolver_text, resolver_available = file_reader(pathlib.Path("/etc/resolv.conf"))
    dns_configured = detect_dns_from_text(resolver_text) if resolver_available else UNKNOWN
    checks["resolver"] = "ok" if resolver_available else "unavailable"

    ethernet_active = merge_tri_bool(device_status["ethernet_active"], active_connections["ethernet_active"])
    wifi_active = merge_tri_bool(device_status["wifi_active"], active_connections["wifi_active"])

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "mode": "read-only",
        "network_manager_available": bool_for_json(network_manager_available),
        "nmcli_available": nmcli_available,
        "wifi_device_present": bool_for_json(device_status["wifi_device_present"]),
        "ethernet_active": bool_for_json(ethernet_active),
        "wifi_active": bool_for_json(wifi_active),
        "default_route_present": bool_for_json(default_route_present),
        "dns_configured": bool_for_json(dns_configured),
        "connectivity": "not_checked",
        "timeout_sec": timeout_sec,
        "read_only_checks": checks,
        "guardrails": {
            "read_only_commands_only": True,
            "external_connectivity_probe": False,
            "networkmanager_restarted": False,
            "ethernet_preserved": True,
            "hotspot_created": False,
            "portal_created": False,
            "data_config_read": False,
            "data_config_written": False,
            "writer_called": False,
            "service_changed": False,
            "player_changed": False,
            "mpv_changed": False,
            "reboot_called": False,
        },
        "privacy_flags": public_privacy_flags(),
    }


def parse_route_device(stdout: str) -> str:
    parts = stdout.replace("\n", " ").split()
    for index, item in enumerate(parts):
        if item == "dev" and index + 1 < len(parts):
            return parts[index + 1]
    return ""


def classify_device_category(device_name: str) -> str:
    lowered = device_name.strip().lower()
    if lowered.startswith(("eth", "en")):
        return "ethernet"
    if lowered.startswith(("wl", "wlan")):
        return "wifi"
    return UNKNOWN


def collect_connectivity_indicator(
    *,
    timeout_sec: int = 2,
    command_runner: Callable[[list[str], float], CommandResult] = run_read_only_command,
    nmcli_path: str | None = None,
    ip_path: str | None = None,
    monotonic_clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Collect one bounded, privacy-safe network snapshot for local UI."""

    deadline = monotonic_clock() + max(0.05, float(timeout_sec))

    def run_snapshot_command(args: list[str]) -> CommandResult:
        remaining = deadline - monotonic_clock()
        if remaining <= 0:
            return CommandResult("timeout")
        return command_runner(args, max(0.05, remaining))

    if nmcli_path is None:
        nmcli_path = shutil.which("nmcli")
    if ip_path is None:
        ip_path = shutil.which("ip")
    nmcli_available = bool(nmcli_path)
    checks = {
        "device_status": "not_run",
        "active_connections": "not_run",
        "connectivity_cached": "not_run",
        "active_wifi_signal": "not_run",
        "default_route": "not_run",
    }
    device_status: dict[str, Any] = {
        "wifi_device_present": UNKNOWN,
        "ethernet_active": UNKNOWN,
        "wifi_active": UNKNOWN,
        "ethernet_connected_devices": [],
        "wifi_connected_devices": [],
    }
    active_connections: dict[str, Any] = {
        "ethernet_active": UNKNOWN,
        "wifi_active": UNKNOWN,
        "ethernet_active_devices": [],
        "wifi_active_devices": [],
    }
    cached_connectivity = UNKNOWN

    if nmcli_available:
        device_result = run_snapshot_command(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"]
        )
        checks["device_status"] = device_result.status
        if device_result.status == "ok" and not command_result_stdout_is_bounded(device_result):
            checks["device_status"] = "too_large"
        elif device_result.status == "ok":
            device_status = parse_device_status(device_result.stdout)

        active_result = run_snapshot_command(
            ["nmcli", "-t", "-f", "TYPE,DEVICE", "connection", "show", "--active"]
        )
        checks["active_connections"] = active_result.status
        if active_result.status == "ok" and not command_result_stdout_is_bounded(active_result):
            checks["active_connections"] = "too_large"
        elif active_result.status == "ok":
            active_connections = parse_active_connections(active_result.stdout)

        connectivity_result = run_snapshot_command(
            ["nmcli", "-t", "-f", "CONNECTIVITY", "general"]
        )
        checks["connectivity_cached"] = connectivity_result.status
        if connectivity_result.status == "ok" and not command_result_stdout_is_bounded(connectivity_result):
            checks["connectivity_cached"] = "too_large"
        elif connectivity_result.status == "ok":
            cached_connectivity = parse_nmcli_connectivity(connectivity_result.stdout)

    route_devices: list[str] = []
    if ip_path:
        route_result = run_snapshot_command(IP_ROUTE_DEFAULT_COMMAND)
        checks["default_route"] = route_result.status
        if route_result.status == "ok" and not command_result_stdout_is_bounded(route_result):
            checks["default_route"] = "too_large"
        elif route_result.status == "ok":
            route_devices = default_route_devices_from_ip_json(route_result.stdout)
    else:
        checks["default_route"] = "unavailable"
    route_device = route_devices[0] if len(route_devices) == 1 else ""
    route_ambiguous = len(route_devices) > 1

    ethernet_devices = set(device_status.get("ethernet_connected_devices") or []) & set(
        active_connections.get("ethernet_active_devices") or []
    )
    wifi_devices = set(device_status.get("wifi_connected_devices") or []) & set(
        active_connections.get("wifi_active_devices") or []
    )
    route_verified = bool(route_device and (route_device in ethernet_devices or route_device in wifi_devices))
    if route_ambiguous:
        transport = UNKNOWN
    elif route_device in ethernet_devices:
        transport = "ethernet"
    elif route_device in wifi_devices:
        transport = "wifi"
    elif route_device:
        transport = UNKNOWN
    elif ethernet_devices and not wifi_devices:
        transport = "ethernet"
    elif wifi_devices and not ethernet_devices:
        transport = "wifi"
    elif (
        device_status["ethernet_active"] is False
        and device_status["wifi_active"] is False
        and active_connections["ethernet_active"] is False
        and active_connections["wifi_active"] is False
    ):
        transport = "none"
    else:
        transport = UNKNOWN

    wifi_signal = UNKNOWN
    if nmcli_available and transport == "wifi":
        signal_result = run_snapshot_command(
            ["nmcli", "-t", "-f", "DEVICE,IN-USE,SIGNAL", "device", "wifi", "list", "--rescan", "no"]
        )
        checks["active_wifi_signal"] = signal_result.status
        if signal_result.status == "ok" and not command_result_stdout_is_bounded(signal_result):
            checks["active_wifi_signal"] = "too_large"
        elif signal_result.status == "ok":
            wifi_signal = parse_active_wifi_signal(
                signal_result.stdout,
                expected_device=route_device if route_device in wifi_devices else "",
            )

    if transport == "none":
        internet = "offline"
    elif transport == UNKNOWN or not route_verified:
        internet = UNKNOWN
    elif cached_connectivity == "full":
        internet = "online"
    elif cached_connectivity in {"limited", "portal"}:
        internet = cached_connectivity
    elif cached_connectivity == "none":
        internet = "offline"
    else:
        internet = UNKNOWN

    return {
        "schema_version": "dadooh.c20.connectivity_indicator.v1",
        "generated_at_utc": utc_timestamp(),
        "transport": transport,
        "wifi_signal": wifi_signal,
        "internet": internet,
        "read_only_checks": checks,
        "guardrails": {
            "read_only_commands_only": True,
            "network_changed": False,
            "external_connectivity_probe": False,
            "speed_test_executed": False,
            "wifi_rescan_executed": False,
            "ssid_collected": False,
            "credentials_collected": False,
            "history_persisted": False,
            "writer_called": False,
        },
    }


def safe_route_target(value: str) -> bool:
    return bool(value) and all(char.isalnum() or char in ".:%" for char in value)


def detect_ssh_path_category(
    *,
    timeout_sec: int,
    command_runner: Callable[[list[str], int], CommandResult] = run_internal_command,
) -> str:
    raw = os.environ.get("SSH_CONNECTION", "")
    parts = raw.split()
    if len(parts) < 4 or not safe_route_target(parts[0]):
        return UNKNOWN
    result = command_runner(["ip", "-o", "route", "get", parts[0]], timeout_sec)
    if result.status != "ok":
        return UNKNOWN
    return classify_device_category(parse_route_device(result.stdout))


def dedicated_profile_present(
    *,
    profile_name: str,
    timeout_sec: int,
    command_runner: Callable[[list[str], int], CommandResult] = run_internal_command,
) -> bool | str:
    profile_name = require_allowed_profile_name(profile_name)
    args = ["nmcli", "-t", "-f", "connection.id", "connection", "show", profile_name]
    assert_apply_command(args, profile_name)
    result = command_runner(args, timeout_sec)
    if result.status == "ok":
        return True
    if result.status == "failed":
        return False
    return UNKNOWN


def dedicated_profile_active(
    *,
    profile_name: str,
    timeout_sec: int,
    command_runner: Callable[[list[str], int], CommandResult] = run_read_only_command,
) -> bool | str:
    profile_name = require_allowed_profile_name(profile_name)
    args = ["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"]
    result = command_runner(args, timeout_sec)
    if result.status == "ok":
        active_names = {
            split_nmcli_terse(line)[0]
            for line in result.stdout.splitlines()
            if line.strip() and split_nmcli_terse(line)
        }
        return profile_name in active_names
    return UNKNOWN


def build_preflight_apply(
    status: dict[str, Any],
    *,
    profile_name: str,
    out_dir: pathlib.Path,
    timeout_sec: int,
    allow_ssh_risk_with_local_console_confirmed: bool = False,
    local_console_confirmed: bool = False,
    command_runner: Callable[[list[str], int], CommandResult] = run_internal_command,
) -> dict[str, Any]:
    profile_allowed = profile_name_allowed(profile_name)
    ssh_path_category = detect_ssh_path_category(timeout_sec=timeout_sec, command_runner=command_runner)
    pending_profile = (
        dedicated_profile_present(profile_name=profile_name, timeout_sec=timeout_sec, command_runner=command_runner)
        if profile_allowed and status["nmcli_available"]
        else UNKNOWN
    )
    rollback_marker_present = (out_dir / ROLLBACK_FILENAME).exists()
    abort_reasons: list[str] = []

    if status["nmcli_available"] is not True:
        abort_reasons.append("nmcli_unavailable")
    if status["network_manager_available"] is not True:
        abort_reasons.append("network_manager_unavailable")
    if status["wifi_device_present"] is not True:
        abort_reasons.append("wifi_device_not_detected")
    if not profile_allowed:
        abort_reasons.append("profile_not_allowed")
    ssh_risk_acknowledged = allow_ssh_risk_with_local_console_confirmed and local_console_confirmed
    if ssh_path_category == "wifi" and not ssh_risk_acknowledged:
        abort_reasons.append("ssh_path_wifi")
    if ssh_path_category == UNKNOWN and not ssh_risk_acknowledged:
        abort_reasons.append("ssh_path_unknown")

    apply_allowed = not abort_reasons
    can_drop_current_session: bool | str
    if ssh_path_category == "wifi":
        can_drop_current_session = True
    elif ssh_path_category == "ethernet":
        can_drop_current_session = False
    else:
        can_drop_current_session = UNKNOWN

    return {
        **status,
        "generated_at_utc": utc_timestamp(),
        "mode": "preflight-apply",
        "profile_name_allowed": profile_allowed,
        "dedicated_profile_present": bool_for_json(pending_profile),
        "rollback_marker_present": rollback_marker_present,
        "ssh_path_category": ssh_path_category,
        "can_drop_current_session": bool_for_json(can_drop_current_session),
        "allow_ssh_risk_with_local_console_confirmed": allow_ssh_risk_with_local_console_confirmed,
        "ssh_path_risk_acknowledged": ssh_risk_acknowledged,
        "local_console_confirmed": local_console_confirmed,
        "apply_requires_local_recovery": ssh_path_category in {"wifi", UNKNOWN},
        "apply_allowed": apply_allowed,
        "would_touch_only_dedicated_profile": profile_allowed,
        "would_preserve_ethernet": True,
        "would_read_real_config": False,
        "would_write_real_config": False,
        "would_call_writer": False,
        "would_change_player": False,
        "would_change_mpv": False,
        "abort_reasons": abort_reasons,
    }


def validate_apply_gates(
    *,
    enable_real_apply: bool,
    confirmation: str | None,
    secrets_file: str | None,
    profile_name: str,
    keep_dedicated_profile: bool = False,
    persistent_product_wifi: bool = False,
    confirm_keep_dedicated_profile: str | None = None,
    allow_ssh_risk_with_local_console_confirmed: bool = False,
    local_console_confirmed: bool = False,
) -> str:
    if not enable_real_apply:
        raise AdapterError("real wifi apply requires --enable-real-apply")
    expected_confirmation = CONFIRM_REAL_WIFI_APPLY_LOCAL_CONSOLE if (
        allow_ssh_risk_with_local_console_confirmed or local_console_confirmed
    ) else CONFIRM_REAL_WIFI_APPLY
    if confirmation != expected_confirmation:
        raise AdapterError("real wifi apply confirmation mismatch")
    if allow_ssh_risk_with_local_console_confirmed and not local_console_confirmed:
        raise AdapterError("local console confirmation required")
    if persistent_product_wifi and not keep_dedicated_profile:
        raise AdapterError("persistent product wifi requires --keep-dedicated-profile")
    if keep_dedicated_profile:
        if confirm_keep_dedicated_profile != CONFIRM_KEEP_DEDICATED_PROFILE:
            raise AdapterError("keep dedicated profile confirmation mismatch")
        require_persistent_profile_name(profile_name)
    if not secrets_file:
        raise AdapterError("secrets-file required")
    return require_allowed_profile_name(profile_name)


def validate_secret_text(value: str, *, field: str) -> str:
    if not isinstance(value, str):
        raise AdapterError("secrets-file invalid")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 256:
        raise AdapterError("secrets-file invalid")
    if any(char in cleaned for char in ("\x00", "\n", "\r")):
        raise AdapterError("secrets-file invalid")
    if field == "psk" and len(cleaned) < 8:
        raise AdapterError("secrets-file invalid")
    return cleaned


def load_wifi_secrets(secrets_file: str) -> dict[str, str]:
    raw_path = pathlib.Path(secrets_file)
    if not raw_path.is_absolute():
        raise AdapterError("secrets-file must be under /tmp")
    path = raw_path.resolve(strict=False)
    if not path_is_under(path, TMP_ROOT):
        raise AdapterError("secrets-file must be under /tmp")
    if raw_path.is_symlink():
        raise AdapterError("secrets-file must not be symlink")
    try:
        file_stat = raw_path.lstat()
        parent_stat = raw_path.parent.lstat()
    except OSError as exc:
        raise AdapterError("secrets-file unavailable") from exc
    if not stat.S_ISREG(file_stat.st_mode):
        raise AdapterError("secrets-file unavailable")
    if not stat.S_ISDIR(parent_stat.st_mode) or raw_path.parent.is_symlink():
        raise AdapterError("secrets-file parent invalid")
    if stat.S_IMODE(file_stat.st_mode) != PRIVATE_FILE_MODE:
        raise AdapterError("secrets-file must be 0600")
    if stat.S_IMODE(parent_stat.st_mode) != PRIVATE_DIR_MODE:
        raise AdapterError("secrets-file parent must be 0700")

    try:
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AdapterError("secrets-file invalid") from exc
    if not isinstance(payload, dict):
        raise AdapterError("secrets-file invalid")
    return {
        "ssid": validate_secret_text(payload.get("ssid"), field="ssid"),
        "psk": validate_secret_text(payload.get("psk"), field="psk"),
    }


def keyfile_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "").replace("\r", "")


def nmconnection_text(profile_name: str, secrets: dict[str, str], *, autoconnect: bool = False) -> str:
    return "\n".join(
        [
            "[connection]",
            f"id={profile_name}",
            f"uuid={deterministic_profile_uuid(profile_name)}",
            "type=wifi",
            f"autoconnect={'true' if autoconnect else 'false'}",
            "",
            "[wifi]",
            "mode=infrastructure",
            f"ssid={keyfile_value(secrets['ssid'])}",
            "",
            "[wifi-security]",
            "key-mgmt=wpa-psk",
            f"psk={keyfile_value(secrets['psk'])}",
            "",
            "[ipv4]",
            "method=auto",
            "",
            "[ipv6]",
            "method=auto",
            "",
        ]
    )


def write_private_nmconnection(
    path: pathlib.Path,
    profile_name: str,
    secrets: dict[str, str],
    *,
    autoconnect: bool = False,
) -> pathlib.Path:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink() or path.is_symlink():
        raise AdapterError("profile source path invalid")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(parent), text=True)
    tmp_path = pathlib.Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(nmconnection_text(profile_name, secrets, autoconnect=autoconnect))
        os.chmod(tmp_path, PRIVATE_FILE_MODE)
        os.replace(tmp_path, path)
        os.chmod(path, PRIVATE_FILE_MODE)
        return path
    except Exception:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def dedicated_profile_filename(profile_name: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in profile_name) + ".nmconnection"


def write_system_nmconnection(
    system_connection_dir: pathlib.Path,
    profile_name: str,
    secrets: dict[str, str],
    *,
    autoconnect: bool = False,
) -> pathlib.Path:
    profile_name = require_allowed_profile_name(profile_name)
    return write_private_nmconnection(
        system_connection_dir / dedicated_profile_filename(profile_name),
        profile_name,
        secrets,
        autoconnect=autoconnect,
    )


def ip_acquired_for_profile(
    *,
    profile_name: str,
    timeout_sec: int,
    command_runner: Callable[[list[str], int], CommandResult] = run_internal_command,
) -> bool | str:
    profile_name = require_allowed_profile_name(profile_name)
    args = ["nmcli", "-t", "-f", "IP4.ADDRESS", "connection", "show", profile_name]
    assert_apply_command(args, profile_name)
    result = command_runner(args, timeout_sec)
    if result.status == "ok":
        return bool(result.stdout.strip())
    if result.status in {"timeout", "unavailable"}:
        return UNKNOWN
    return False


def build_rollback_status(
    *,
    reason: str,
    attempted: bool,
    down_result: str,
    delete_result: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "mode": "rollback",
        "rollback_scope": "dedicated_profile_only",
        "rollback_reason": reason,
        "rollback_attempted": attempted,
        "dedicated_profile_down_result": down_result,
        "dedicated_profile_delete_result": delete_result,
        "rollback_status": "attempted" if attempted else "not_attempted_reason_safe_abort",
        "ethernet_modified": False,
        "old_profiles_modified": False,
        "network_identifiers_published": False,
        "privacy_flags": public_privacy_flags(),
    }


def rollback_dedicated_profile(
    *,
    profile_name: str,
    out_dir: pathlib.Path,
    timeout_sec: int,
    reason: str,
    command_runner: Callable[[list[str], int], CommandResult] = run_internal_command,
) -> dict[str, Any]:
    profile_name = require_allowed_profile_name(profile_name)
    down_args = ["nmcli", "connection", "down", "id", profile_name]
    delete_args = ["nmcli", "connection", "delete", "id", profile_name]
    assert_apply_command(down_args, profile_name)
    assert_apply_command(delete_args, profile_name)
    down_result = command_runner(down_args, timeout_sec)
    delete_result = command_runner(delete_args, timeout_sec)
    rollback = build_rollback_status(
        reason=reason,
        attempted=True,
        down_result=down_result.status,
        delete_result=delete_result.status,
    )
    write_rollback_artifact(out_dir, rollback)
    return rollback


def create_or_update_dedicated_profile(
    *,
    profile_name: str,
    secrets: dict[str, str],
    out_dir: pathlib.Path,
    timeout_sec: int,
    autoconnect: bool = False,
    system_connection_dir: pathlib.Path = SYSTEM_CONNECTION_DIR,
    command_runner: Callable[[list[str], int], CommandResult] = run_internal_command,
) -> tuple[str, bool, pathlib.Path | None]:
    profile_name = require_allowed_profile_name(profile_name)
    keyfile_path = write_system_nmconnection(system_connection_dir, profile_name, secrets, autoconnect=autoconnect)
    replaced_existing = False
    try:
        existing = dedicated_profile_present(
            profile_name=profile_name,
            timeout_sec=timeout_sec,
            command_runner=command_runner,
        )
        if existing is True:
            delete_args = ["nmcli", "connection", "delete", "id", profile_name]
            assert_apply_command(delete_args, profile_name)
            delete_result = command_runner(delete_args, timeout_sec)
            if delete_result.status not in {"ok", "failed"}:
                return delete_result.status, replaced_existing, keyfile_path
            replaced_existing = delete_result.status == "ok"

        load_args = ["nmcli", "connection", "load", str(keyfile_path)]
        assert_apply_command(load_args, profile_name, keyfile_path)
        load_result = command_runner(load_args, timeout_sec)
        if load_result.status == "ok":
            loaded = dedicated_profile_present(
                profile_name=profile_name,
                timeout_sec=timeout_sec,
                command_runner=command_runner,
            )
            if loaded is not True:
                return "profile_not_present_after_load", replaced_existing, keyfile_path
        return load_result.status, replaced_existing, keyfile_path
    except Exception:
        try:
            keyfile_path.unlink()
        except FileNotFoundError:
            pass
        raise


def classify_failure_from_text(text: str) -> str:
    lowered = text.lower()
    if not lowered:
        return UNKNOWN
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    if any(marker in lowered for marker in ("secrets were required", "no agents were available", "password", "psk", "auth", "802.1x")):
        return "auth_failed_suspected"
    if any(marker in lowered for marker in ("ssid", "not found", "not available", "no network")):
        return "network_not_found_suspected"
    if any(marker in lowered for marker in ("association", "supplicant", "signal", "scan")):
        return "signal_or_range_suspected"
    if any(marker in lowered for marker in ("dhcp", "ip-config", "ip configuration")):
        return "dhcp_timeout_suspected"
    if any(marker in lowered for marker in ("no suitable device", "device", "unavailable", "not managed")):
        return "device_unavailable"
    return "nm_activation_failed_generic"


def classify_activation_failure(
    *,
    activation_result: str,
    preflight: dict[str, Any],
    profile_create_result: str,
    activation_command_result: CommandResult | None = None,
) -> str:
    if activation_result == "success":
        return "none"
    if activation_result == "timeout":
        return "timeout"
    if preflight.get("wifi_device_present") is not True:
        return "device_unavailable"
    if preflight.get("network_manager_available") is not True or preflight.get("nmcli_available") is not True:
        return "device_unavailable"
    if profile_create_result == "profile_not_present_after_load":
        return "nm_profile_load_failed"
    if profile_create_result not in {"ok", "not_attempted"} and activation_result == "not_attempted":
        return "nm_activation_failed_generic"
    if activation_command_result is not None:
        category = classify_failure_from_text(f"{activation_command_result.stdout}\n{activation_command_result.stderr}")
        if category != UNKNOWN:
            return category
    if activation_result == "failure":
        return "nm_activation_failed_generic"
    return UNKNOWN


def build_apply_status(
    *,
    preflight: dict[str, Any],
    profile_create_result: str,
    profile_replaced: bool,
    activation_result: str,
    failure_category: str,
    ip_acquired: bool | str,
    default_route_present: bool | str,
    rollback: dict[str, Any] | None,
    profile_retained: bool,
    secrets_file_cleanup: bool,
    profile_source_retained_during_activation: bool,
    persistent_product_wifi: bool,
    autoconnect_enabled: bool,
) -> dict[str, Any]:
    network_changed = activation_result in {"success", "failure", "timeout"}
    privacy = public_privacy_flags()
    privacy["network_changed"] = network_changed
    privacy["credentials_collected"] = True
    privacy["nmcli_modify_called"] = profile_create_result == "ok" or activation_result != "not_attempted"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "mode": "apply",
        "preflight_apply_allowed": preflight["apply_allowed"],
        "ssh_path_category": preflight.get("ssh_path_category", UNKNOWN),
        "ssh_path_risk_acknowledged": preflight.get("ssh_path_risk_acknowledged", False),
        "local_console_confirmed": preflight.get("local_console_confirmed", False),
        "apply_requires_local_recovery": preflight.get("apply_requires_local_recovery", False),
        "wifi_profile_created": profile_create_result == "ok",
        "wifi_profile_replaced": profile_replaced,
        "wifi_activation_attempted": activation_result != "not_attempted",
        "wifi_activation_result": activation_result,
        "failure_category": failure_category,
        "ip_acquired": bool_for_json(ip_acquired),
        "default_route_present": bool_for_json(default_route_present),
        "connectivity_check": "not_checked",
        "rollback_after_test": rollback is not None,
        "rollback_status": rollback["rollback_status"] if rollback else "not_attempted",
        "profile_retained": profile_retained,
        "persistent_product_wifi": persistent_product_wifi,
        "dedicated_profile_persistent": bool(profile_retained and persistent_product_wifi),
        "autoconnect_enabled": bool(profile_retained and autoconnect_enabled),
        "profile_source_retained_during_activation": profile_source_retained_during_activation,
        "secrets_file_cleanup": secrets_file_cleanup,
        "network_changed": network_changed,
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "service_changed": False,
        "player_changed": False,
        "mpv_changed": False,
        "hotspot_created": False,
        "portal_created": False,
        "reboot_called": False,
        "privacy_flags": privacy,
    }


def apply_wifi_controlled(
    *,
    out_dir: pathlib.Path,
    timeout_sec: int,
    enable_real_apply: bool,
    confirmation: str | None,
    secrets_file: str | None,
    profile_name: str,
    rollback_after_test: bool,
    keep_dedicated_profile: bool,
    persistent_product_wifi: bool,
    confirm_keep_dedicated_profile: str | None,
    cleanup_secrets_file: bool,
    allow_ssh_risk_with_local_console_confirmed: bool,
    local_console_confirmed: bool = False,
    system_connection_dir: pathlib.Path = SYSTEM_CONNECTION_DIR,
    command_runner: Callable[[list[str], int], CommandResult] = run_internal_command,
    file_reader: Callable[[pathlib.Path], tuple[str, bool]] = read_text_if_present,
    nmcli_path: str | None = None,
) -> dict[str, Any]:
    profile_name = validate_apply_gates(
        enable_real_apply=enable_real_apply,
        confirmation=confirmation,
        secrets_file=secrets_file,
        profile_name=profile_name,
        keep_dedicated_profile=keep_dedicated_profile,
        persistent_product_wifi=persistent_product_wifi,
        confirm_keep_dedicated_profile=confirm_keep_dedicated_profile,
        allow_ssh_risk_with_local_console_confirmed=allow_ssh_risk_with_local_console_confirmed,
        local_console_confirmed=local_console_confirmed,
    )
    prepare_out_dir(out_dir)

    read_only = collect_read_only_status(
        timeout_sec=timeout_sec,
        command_runner=command_runner,
        file_reader=file_reader,
        nmcli_path=nmcli_path,
    )
    preflight = build_preflight_apply(
        read_only,
        profile_name=profile_name,
        out_dir=out_dir,
        timeout_sec=timeout_sec,
        allow_ssh_risk_with_local_console_confirmed=allow_ssh_risk_with_local_console_confirmed,
        local_console_confirmed=local_console_confirmed,
        command_runner=command_runner,
    )
    write_preflight_artifacts(out_dir, preflight)
    if not preflight["apply_allowed"]:
        rollback = build_rollback_status(
            reason="preflight_abort",
            attempted=False,
            down_result="not_attempted",
            delete_result="not_attempted",
        )
        write_rollback_artifact(out_dir, rollback)
        status = build_apply_status(
            preflight=preflight,
            profile_create_result="not_attempted",
            profile_replaced=False,
            activation_result="not_attempted",
            failure_category=classify_activation_failure(
                activation_result="not_attempted",
                preflight=preflight,
                profile_create_result="not_attempted",
            ),
            ip_acquired=UNKNOWN,
            default_route_present=preflight["default_route_present"],
            rollback=rollback,
            profile_retained=False,
            secrets_file_cleanup=False,
            profile_source_retained_during_activation=False,
            persistent_product_wifi=persistent_product_wifi,
            autoconnect_enabled=False,
        )
        write_apply_artifacts(out_dir, status, preflight, rollback)
        raise AdapterError("preflight blocked real wifi apply")

    secrets = load_wifi_secrets(secrets_file or "")
    cleanup_done = False
    rollback: dict[str, Any] | None = None
    profile_retained = False
    profile_create_result = "not_attempted"
    profile_replaced = False
    activation_result = "not_attempted"
    activation_command_result: CommandResult | None = None
    profile_source_path: pathlib.Path | None = None
    ip_acquired: bool | str = UNKNOWN
    default_route_present: bool | str = preflight["default_route_present"]
    autoconnect_enabled = bool(persistent_product_wifi and keep_dedicated_profile)

    try:
        profile_create_result, profile_replaced, profile_source_path = create_or_update_dedicated_profile(
            profile_name=profile_name,
            secrets=secrets,
            out_dir=out_dir,
            timeout_sec=timeout_sec,
            autoconnect=autoconnect_enabled,
            system_connection_dir=system_connection_dir,
            command_runner=command_runner,
        )
        if profile_create_result == "ok":
            up_args = ["nmcli", "--wait", str(timeout_sec), "connection", "up", "id", profile_name]
            assert_apply_command(up_args, profile_name)
            activation_command_result = command_runner(up_args, timeout_sec + 2)
            if activation_command_result.status == "ok":
                activation_result = "success"
            elif activation_command_result.status == "timeout":
                activation_result = "timeout"
            else:
                activation_result = "failure"
            ip_acquired = ip_acquired_for_profile(
                profile_name=profile_name,
                timeout_sec=timeout_sec,
                command_runner=command_runner,
            )
            route_text, route_available = file_reader(pathlib.Path("/proc/net/route"))
            default_route_present = detect_default_route_from_text(route_text) if route_available else UNKNOWN

        should_rollback = rollback_after_test or not keep_dedicated_profile or activation_result != "success"
        if should_rollback:
            rollback = rollback_dedicated_profile(
                profile_name=profile_name,
                out_dir=out_dir,
                timeout_sec=timeout_sec,
                reason="rollback_after_test" if activation_result == "success" else "activation_not_successful",
                command_runner=command_runner,
            )
        else:
            profile_retained = True
    finally:
        if profile_source_path is not None and not (profile_retained and persistent_product_wifi):
            try:
                profile_source_path.unlink()
            except FileNotFoundError:
                pass
        if cleanup_secrets_file and secrets_file:
            try:
                pathlib.Path(secrets_file).unlink()
                cleanup_done = True
            except OSError:
                cleanup_done = False

    status = build_apply_status(
        preflight=preflight,
        profile_create_result=profile_create_result,
        profile_replaced=profile_replaced,
        activation_result=activation_result,
        failure_category=classify_activation_failure(
            activation_result=activation_result,
            preflight=preflight,
            profile_create_result=profile_create_result,
            activation_command_result=activation_command_result,
        ),
        ip_acquired=ip_acquired,
        default_route_present=default_route_present,
        rollback=rollback,
        profile_retained=profile_retained,
        secrets_file_cleanup=cleanup_done,
        profile_source_retained_during_activation=profile_source_path is not None,
        persistent_product_wifi=persistent_product_wifi,
        autoconnect_enabled=autoconnect_enabled,
    )
    write_apply_artifacts(out_dir, status, preflight, rollback)
    return status


def build_plan(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "mode": "plan",
        "apply_enabled": False,
        "target_network": "redacted",
        "credentials_source": "not_collected_in_read_only_or_plan",
        "current_state_source": "sanitized_read_only_status",
        "read_only_status": {
            "network_manager_available": status["network_manager_available"],
            "nmcli_available": status["nmcli_available"],
            "wifi_device_present": status["wifi_device_present"],
            "ethernet_active": status["ethernet_active"],
            "wifi_active": status["wifi_active"],
            "default_route_present": status["default_route_present"],
            "dns_configured": status["dns_configured"],
            "connectivity": status["connectivity"],
        },
        "future_apply_sequence": [
            "require_explicit_human_confirmation",
            "collect_credentials_outside_logs",
            "preserve_active_ethernet",
            "create_or_update_dedicated_product_profile",
            "do_not_remove_existing_profile_before_success",
            "test_new_connection_with_timeout",
            "rollback_to_previous_state_on_failure",
            "write_sanitized_evidence_only",
        ],
        "future_apply_guardrails": {
            "human_confirmation_required": True,
            "destructive_nmcli_requires_confirmation": True,
            "delete_previous_profile_before_success": False,
            "password_logged": False,
            "network_identifiers_published": False,
            "network_addressing_published": False,
            "raw_logs_published": False,
            "config_real_read": False,
            "config_real_written": False,
            "writer_called": False,
            "player_changed": False,
            "mpv_changed": False,
            "hotspot_created": False,
            "portal_created": False,
            "reboot_called": False,
        },
        "privacy_flags": public_privacy_flags(),
    }


def build_summary(status: dict[str, Any], plan: dict[str, Any] | None = None) -> str:
    lines = [
        "Dadooh C9.6 wifi controlled",
        "",
        f"schema_version: {status['schema_version']}",
        f"generated_at_utc: {status['generated_at_utc']}",
        f"mode: {status['mode'] if plan is None else 'plan'}",
        f"network_manager_available: {status['network_manager_available']}",
        f"nmcli_available: {status['nmcli_available']}",
        f"wifi_device_present: {status['wifi_device_present']}",
        f"ethernet_active: {status['ethernet_active']}",
        f"wifi_active: {status['wifi_active']}",
        f"default_route_present: {status['default_route_present']}",
        f"resolver_configured: {status['dns_configured']}",
        f"connectivity: {status['connectivity']}",
        "",
        "Guardrails:",
        "network_changed: false",
        "credentials_collected: false",
        "network_details_published: false",
        "address_details_published: false",
        "modifying_commands_called: false",
        "real_config_read: false",
        "real_config_written: false",
        "writer_called: false",
        "service_changed: false",
        "player_changed: false",
        "mpv_changed: false",
        "hotspot_created: false",
        "portal_created: false",
        "reboot_called: false",
    ]
    if plan is not None:
        lines.extend(
            [
                "",
                "Plan:",
                f"apply_enabled: {str(plan['apply_enabled']).lower()}",
                f"target_network: {plan['target_network']}",
                f"credentials_source: {plan['credentials_source']}",
                "human_confirmation_required: true",
                "rollback_required: true",
            ]
        )
    return "\n".join(lines) + "\n"


def build_preflight_summary(preflight: dict[str, Any]) -> str:
    lines = [
        "Dadooh C9.6 wifi preflight",
        "",
        f"schema_version: {preflight['schema_version']}",
        f"generated_at_utc: {preflight['generated_at_utc']}",
        "mode: preflight-apply",
        f"network_manager_available: {preflight['network_manager_available']}",
        f"nmcli_available: {preflight['nmcli_available']}",
        f"wifi_device_present: {preflight['wifi_device_present']}",
        f"ethernet_active: {preflight['ethernet_active']}",
        f"wifi_active: {preflight['wifi_active']}",
        f"default_route_present: {preflight['default_route_present']}",
        f"resolver_configured: {preflight['dns_configured']}",
        f"ssh_path_category: {preflight['ssh_path_category']}",
        f"can_drop_current_session: {preflight['can_drop_current_session']}",
        f"ssh_path_risk_acknowledged: {str(preflight['ssh_path_risk_acknowledged']).lower()}",
        f"local_console_confirmed: {str(preflight['local_console_confirmed']).lower()}",
        f"apply_requires_local_recovery: {str(preflight['apply_requires_local_recovery']).lower()}",
        f"profile_name_allowed: {str(preflight['profile_name_allowed']).lower()}",
        f"dedicated_profile_present: {preflight['dedicated_profile_present']}",
        f"rollback_marker_present: {str(preflight['rollback_marker_present']).lower()}",
        f"apply_allowed: {str(preflight['apply_allowed']).lower()}",
        "",
        "Guardrails:",
        f"would_touch_only_dedicated_profile: {str(preflight['would_touch_only_dedicated_profile']).lower()}",
        "would_preserve_ethernet: true",
        "real_config_read: false",
        "real_config_written: false",
        "writer_called: false",
        "player_changed: false",
        "mpv_changed: false",
        "hotspot_created: false",
        "portal_created: false",
        "reboot_called: false",
    ]
    return "\n".join(lines) + "\n"


def build_apply_summary(status: dict[str, Any]) -> str:
    lines = [
        "Dadooh C9.6 wifi apply",
        "",
        f"schema_version: {status['schema_version']}",
        f"generated_at_utc: {status['generated_at_utc']}",
        "mode: apply",
        f"preflight_apply_allowed: {str(status['preflight_apply_allowed']).lower()}",
        f"ssh_path_category: {status['ssh_path_category']}",
        f"ssh_path_risk_acknowledged: {str(status['ssh_path_risk_acknowledged']).lower()}",
        f"local_console_confirmed: {str(status['local_console_confirmed']).lower()}",
        f"apply_requires_local_recovery: {str(status['apply_requires_local_recovery']).lower()}",
        f"wifi_profile_created: {str(status['wifi_profile_created']).lower()}",
        f"wifi_profile_replaced: {str(status['wifi_profile_replaced']).lower()}",
        f"wifi_activation_attempted: {str(status['wifi_activation_attempted']).lower()}",
        f"wifi_activation_result: {status['wifi_activation_result']}",
        f"failure_category: {status['failure_category']}",
        f"ip_acquired: {status['ip_acquired']}",
        f"default_route_present: {status['default_route_present']}",
        f"connectivity_check: {status['connectivity_check']}",
        f"rollback_status: {status['rollback_status']}",
        f"profile_retained: {str(status['profile_retained']).lower()}",
        f"persistent_product_wifi: {str(status['persistent_product_wifi']).lower()}",
        f"dedicated_profile_persistent: {str(status['dedicated_profile_persistent']).lower()}",
        f"autoconnect_enabled: {str(status['autoconnect_enabled']).lower()}",
        f"profile_source_retained_during_activation: {str(status['profile_source_retained_during_activation']).lower()}",
        f"secrets_file_cleanup: {str(status['secrets_file_cleanup']).lower()}",
        "",
        "Guardrails:",
        f"network_changed: {str(status['network_changed']).lower()}",
        "real_config_read: false",
        "real_config_written: false",
        "writer_called: false",
        "service_changed: false",
        "player_changed: false",
        "mpv_changed: false",
        "hotspot_created: false",
        "portal_created: false",
        "reboot_called: false",
        "network_details_published: false",
        "address_details_published: false",
        "credential_values_published: false",
    ]
    return "\n".join(lines) + "\n"


def write_read_only_artifacts(out_dir: pathlib.Path, status: dict[str, Any]) -> None:
    prepare_out_dir(out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_summary(status), out_dir)


def write_plan_artifacts(out_dir: pathlib.Path, status: dict[str, Any], plan: dict[str, Any]) -> None:
    prepare_out_dir(out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_json(out_dir / PLAN_FILENAME, plan, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_summary(status, plan), out_dir)


def write_preflight_artifacts(out_dir: pathlib.Path, preflight: dict[str, Any]) -> None:
    prepare_out_dir(out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, preflight, out_dir)
    atomic_write_private_json(out_dir / PREFLIGHT_FILENAME, preflight, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_preflight_summary(preflight), out_dir)


def write_rollback_artifact(out_dir: pathlib.Path, rollback: dict[str, Any]) -> None:
    prepare_out_dir(out_dir)
    atomic_write_private_json(out_dir / ROLLBACK_FILENAME, rollback, out_dir)


def write_apply_artifacts(
    out_dir: pathlib.Path,
    status: dict[str, Any],
    preflight: dict[str, Any],
    rollback: dict[str, Any] | None,
) -> None:
    prepare_out_dir(out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_json(out_dir / PREFLIGHT_FILENAME, preflight, out_dir)
    if rollback is not None:
        atomic_write_private_json(out_dir / ROLLBACK_FILENAME, rollback, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_apply_summary(status), out_dir)


def read_private_json_if_present(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists() or path.is_symlink():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_diagnosis_summary(diagnosis: dict[str, Any]) -> str:
    lines = [
        "Dadooh C9.6.3 wifi failure diagnosis",
        "",
        f"schema_version: {diagnosis['schema_version']}",
        f"generated_at_utc: {diagnosis['generated_at_utc']}",
        "mode: diagnose-last-failure",
        f"nm_available: {diagnosis['nm_available']}",
        f"wifi_device_present: {diagnosis['wifi_device_present']}",
        f"activation_attempted: {str(diagnosis['activation_attempted']).lower()}",
        f"activation_result: {diagnosis['activation_result']}",
        f"failure_category: {diagnosis['failure_category']}",
        f"rollback_status: {diagnosis['rollback_status']}",
        f"dedicated_profile_present_final: {diagnosis['dedicated_profile_present_final']}",
        f"secrets_file_removed: {diagnosis['secrets_file_removed']}",
        f"network_changed: {str(diagnosis['network_changed']).lower()}",
        "",
        "Guardrails:",
        "real_config_read: false",
        "real_config_written: false",
        "writer_called: false",
        "network_details_published: false",
        "credential_values_published: false",
    ]
    return "\n".join(lines) + "\n"


def diagnose_last_failure(
    *,
    out_dir: pathlib.Path,
    profile_name: str,
    timeout_sec: int,
    secrets_file: str | None = None,
    command_runner: Callable[[list[str], int], CommandResult] = run_internal_command,
) -> dict[str, Any]:
    prepare_out_dir(out_dir)
    status = read_private_json_if_present(out_dir / STATUS_FILENAME)
    preflight = read_private_json_if_present(out_dir / PREFLIGHT_FILENAME)
    rollback = read_private_json_if_present(out_dir / ROLLBACK_FILENAME)

    read_only = collect_read_only_status(timeout_sec=timeout_sec, command_runner=command_runner)
    profile_present = (
        dedicated_profile_present(profile_name=profile_name, timeout_sec=timeout_sec, command_runner=command_runner)
        if read_only.get("nmcli_available") is True
        else UNKNOWN
    )

    activation_result = status.get("wifi_activation_result", "unknown")
    activation_attempted = bool(status.get("wifi_activation_attempted", False))
    failure_category = status.get("failure_category")
    if not isinstance(failure_category, str) or not failure_category:
        failure_category = classify_activation_failure(
            activation_result=activation_result if isinstance(activation_result, str) else UNKNOWN,
            preflight=preflight or read_only,
            profile_create_result="ok" if status.get("wifi_profile_created") else "not_attempted",
        )

    if secrets_file:
        try:
            secrets_cleanup: bool | str = not pathlib.Path(secrets_file).exists()
        except OSError:
            secrets_cleanup = UNKNOWN
    else:
        secrets_cleanup = status.get("secrets_file_cleanup", UNKNOWN)
    privacy = public_privacy_flags()
    privacy["network_changed"] = bool(status.get("network_changed", False))
    diagnosis = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "mode": "diagnose-last-failure",
        "nm_available": bool_for_json(read_only.get("network_manager_available", UNKNOWN)),
        "nmcli_available": bool_for_json(read_only.get("nmcli_available", UNKNOWN)),
        "wifi_device_present": bool_for_json(read_only.get("wifi_device_present", UNKNOWN)),
        "activation_attempted": activation_attempted,
        "activation_result": activation_result if isinstance(activation_result, str) else UNKNOWN,
        "failure_category": failure_category,
        "rollback_status": rollback.get("rollback_status", status.get("rollback_status", "unknown")),
        "dedicated_profile_present_final": bool_for_json(profile_present),
        "secrets_file_removed": bool_for_json(secrets_cleanup),
        "network_changed": bool(status.get("network_changed", False)),
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "network_identifiers_published": False,
        "credential_values_published": False,
        "raw_logs_published": False,
        "privacy_flags": privacy,
    }
    atomic_write_private_json(out_dir / DIAGNOSE_FILENAME, diagnosis, out_dir)
    atomic_write_private_text(out_dir / DIAGNOSE_SUMMARY_FILENAME, build_diagnosis_summary(diagnosis), out_dir)
    return diagnosis


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_raises(func: Callable[[], object], message: str) -> None:
    try:
        func()
    except Exception:
        return
    raise AssertionError(message)


def assert_artifact_permissions(out_dir: pathlib.Path, names: tuple[str, ...]) -> None:
    assert_true(file_mode(out_dir) == PRIVATE_DIR_MODE, "out-dir mode should be 0700")
    for name in names:
        path = out_dir / name
        assert_true(path.exists(), f"{name} should exist")
        assert_true(file_mode(path) == PRIVATE_FILE_MODE, f"{name} mode should be 0600")
        assert_true(path_is_under(path, TMP_ROOT), f"{name} should stay under /tmp")


def assert_no_forbidden_values(text: str) -> None:
    lowered = text.lower()
    for value in SENSITIVE_MARKERS:
        assert_true(value.lower() not in lowered, f"public output leaked {value}")


def run_self_test() -> None:
    assert_raises(
        lambda: require_tmp_dir("/var/tmp/dadooh-c9-6-wifi-apply"),
        "out-dir outside /tmp should fail",
    )
    assert_raises(
        lambda: validate_apply_gates(
            enable_real_apply=False,
            confirmation=CONFIRM_REAL_WIFI_APPLY,
            secrets_file="/tmp/x/secrets.json",
            profile_name=DEFAULT_PROFILE_NAME,
        ),
        "apply without enable should abort",
    )
    assert_raises(
        lambda: validate_apply_gates(
            enable_real_apply=True,
            confirmation="CONFIRMO APPLY WIFI REAL C9.6",
            secrets_file="/tmp/x/secrets.json",
            profile_name=DEFAULT_PROFILE_NAME,
        ),
        "apply without exact confirmation should abort",
    )
    assert_raises(
        lambda: validate_apply_gates(
            enable_real_apply=True,
            confirmation=CONFIRM_REAL_WIFI_APPLY,
            secrets_file="/tmp/x/secrets.json",
            profile_name="office-wifi",
        ),
        "non-dedicated profile should abort",
    )
    assert_raises(
        lambda: validate_apply_gates(
            enable_real_apply=True,
            confirmation=CONFIRM_REAL_WIFI_APPLY,
            secrets_file="/tmp/x/secrets.json",
            profile_name=DEFAULT_PROFILE_NAME,
            allow_ssh_risk_with_local_console_confirmed=True,
            local_console_confirmed=True,
        ),
        "local console apply should require the local console phrase",
    )
    assert_raises(
        lambda: validate_apply_gates(
            enable_real_apply=True,
            confirmation=CONFIRM_REAL_WIFI_APPLY_LOCAL_CONSOLE,
            secrets_file="/tmp/x/secrets.json",
            profile_name=DEFAULT_PROFILE_NAME,
            allow_ssh_risk_with_local_console_confirmed=True,
            local_console_confirmed=False,
        ),
        "ssh risk exception should require local console confirmation",
    )
    assert_raises(
        lambda: validate_apply_gates(
            enable_real_apply=True,
            confirmation=CONFIRM_REAL_WIFI_APPLY,
            secrets_file="/tmp/x/secrets.json",
            profile_name=DEFAULT_PERSISTENT_PROFILE_NAME,
            keep_dedicated_profile=True,
            confirm_keep_dedicated_profile="",
        ),
        "persistent profile should require explicit keep confirmation",
    )
    assert_raises(
        lambda: validate_apply_gates(
            enable_real_apply=True,
            confirmation=CONFIRM_REAL_WIFI_APPLY,
            secrets_file="/tmp/x/secrets.json",
            profile_name=DEFAULT_PROFILE_NAME,
            keep_dedicated_profile=True,
            persistent_product_wifi=True,
            confirm_keep_dedicated_profile=CONFIRM_KEEP_DEDICATED_PROFILE,
        ),
        "persistent product wifi should require a C9.8/product profile prefix",
    )
    validate_apply_gates(
        enable_real_apply=True,
        confirmation=CONFIRM_REAL_WIFI_APPLY,
        secrets_file="/tmp/x/secrets.json",
        profile_name=DEFAULT_PERSISTENT_PROFILE_NAME,
        keep_dedicated_profile=True,
        persistent_product_wifi=True,
        confirm_keep_dedicated_profile=CONFIRM_KEEP_DEDICATED_PROFILE,
    )

    for command in (
        ["nmcli", "connection", "up", "Fake product wifi"],
        ["nmcli", "connection", "down", "Fake product wifi"],
        ["nmcli", "connection", "delete", "Fake product wifi"],
        ["nmcli", "connection", "modify", "Fake product wifi"],
        ["nmcli", "device", "wifi", "connect", "FAKE-STORE-WIFI", "password", "fake-password"],
        ["nmcli", "radio", "off"],
        ["systemctl", "restart", "NetworkManager"],
        ["ifdown", "eth0"],
        ["ifup", "eth0"],
        ["ip", "link", "set", "eth0", "down"],
    ):
        assert_raises(lambda command=command: assert_read_only_command(command), "modifier should be blocked")

    for command in (
        ["nmcli", "-t", "-f", "CONNECTIVITY", "general"],
        ["nmcli", "-t", "-f", "DEVICE,IN-USE,SIGNAL", "device", "wifi", "list", "--rescan", "no"],
    ):
        assert_read_only_command(command)
    assert_true(read_only_command_env()["LC_ALL"] == "C", "read-only nmcli output should use a stable locale")

    device_fixture = "\n".join(
        [
            "eth0:ethernet:connected:Fake product wifi",
            "wlan0:wifi:connected:FAKE-STORE-WIFI",
            "aa\\:bb\\:cc\\:dd\\:ee\\:ff:wifi:disconnected:fake-token-value",
        ]
    )
    parsed_device = parse_device_status(device_fixture)
    assert_true(parsed_device["wifi_device_present"] is True, "wifi device should be detected")
    assert_true(parsed_device["ethernet_active"] is True, "ethernet should be active")
    assert_true(parsed_device["wifi_active"] is True, "wifi active should be detected")
    assert_true(
        parsed_device["wifi_connected_devices"] == ["wlan0"],
        "connected Wi-Fi identity should be retained for route coherence",
    )

    active_fixture = "\n".join(
        [
            "802-3-ethernet:eth0:Fake product wifi",
            "802-11-wireless:wlan0:FAKE-STORE-WIFI",
        ]
    )
    parsed_active = parse_active_connections(active_fixture)
    assert_true(parsed_active["ethernet_active"] is True, "active ethernet should be detected")
    assert_true(parsed_active["wifi_active"] is True, "active wifi should be detected")
    assert_true(
        parsed_active["wifi_active_devices"] == ["wlan0"],
        "active Wi-Fi connection identity should be retained for route coherence",
    )
    active_name_command = ["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"]
    assert_true(
        dedicated_profile_active(
            profile_name=DEFAULT_PERSISTENT_PROFILE_NAME,
            timeout_sec=2,
            command_runner=lambda args, timeout: CommandResult(
                "ok",
                f"ethernet-default\n{DEFAULT_PERSISTENT_PROFILE_NAME}\n",
            )
            if args == active_name_command
            else CommandResult("failed"),
        )
        is True,
        "dedicated profile should be recognized only when active",
    )
    assert_true(
        dedicated_profile_active(
            profile_name=DEFAULT_PERSISTENT_PROFILE_NAME,
            timeout_sec=2,
            command_runner=lambda args, timeout: CommandResult("ok", "ethernet-default\n")
            if args == active_name_command
            else CommandResult("failed"),
        )
        is False,
        "saved but inactive dedicated profile should fail closed",
    )

    wifi_list_fixture = "\n".join(
        [
            "FAKE-STORE-WIFI:82:WPA2",
            ":99:WPA2",
            "FAKE-STORE-WIFI:55:WPA2",
            "Fake product wifi:35:",
            "aa\\:bb\\:cc\\:dd\\:ee\\:ff:12:WPA1",
        ]
    )
    parsed_wifi_list = parse_wifi_network_list(wifi_list_fixture)
    assert_true(len(parsed_wifi_list) == 3, "wifi list should deduplicate SSIDs")
    assert_true(parsed_wifi_list[0]["ssid"] == "FAKE-STORE-WIFI", "strongest SSID should sort first")
    assert_true(parsed_wifi_list[0]["signal_percent"] == 82, "signal percent should be kept for local UI")
    assert_true(parsed_wifi_list[0]["signal_bucket"] == "strong", "signal bucket should be strong")
    assert_true(all(item["ssid"] for item in parsed_wifi_list), "wifi list should ignore empty SSIDs")
    public_wifi_meta = wifi_selection_public_metadata(parsed_wifi_list, parsed_wifi_list[0])
    assert_true(public_wifi_meta["wifi_networks_found_count"] == 3, "wifi count should be public")
    assert_true(public_wifi_meta["selected_network_present"] is True, "selection presence should be public")
    assert_true(public_wifi_meta["selected_network_signal_bucket"] == "strong", "selected bucket should be public")
    assert_true(public_wifi_meta["selected_network_security_present"] is True, "security presence should be public")
    assert_no_forbidden_values(json.dumps(public_wifi_meta, sort_keys=True))
    assert_true(parse_nmcli_connectivity("full\n") == "full", "full connectivity should parse")
    assert_true(parse_nmcli_connectivity("limited\n") == "limited", "limited connectivity should parse")
    assert_true(parse_nmcli_connectivity("portal\n") == "portal", "portal connectivity should parse")
    assert_true(parse_nmcli_connectivity("none\n") == "none", "offline connectivity should parse")
    assert_true(parse_nmcli_connectivity("unexpected\n") == UNKNOWN, "unexpected connectivity should fail closed")
    assert_true(parse_nmcli_connectivity("prefix:full\n") == UNKNOWN, "extra connectivity fields should fail closed")
    assert_true(parse_nmcli_connectivity("full\nnone\n") == UNKNOWN, "multiple connectivity rows should fail closed")
    assert_true(
        parse_active_wifi_signal("wlan0: :91\nwlan0:*:68\n", expected_device="wlan0") == "medium",
        "active Wi-Fi signal should parse",
    )
    assert_true(parse_active_wifi_signal("wlan0: :91\n") == UNKNOWN, "missing active Wi-Fi should be unknown")
    assert_true(
        parse_active_wifi_signal("wlan0:*:68\nwlan1:*:80\n") == UNKNOWN,
        "multiple active radios without a route identity should be unknown",
    )
    assert_true(parse_active_wifi_signal("wlan0:*:101\n") == UNKNOWN, "out-of-range signal should be unknown")

    route_fixture = "\n".join(
        [
            "Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT",
            "eth0 00000000 010200C0 0003 0 0 100 00000000 0 0 0",
        ]
    )
    resolver_fixture = "\n".join(
        [
            "search fake-hostname.invalid",
            "nameserver 203.0.113.53",
        ]
    )
    assert_true(detect_default_route_from_text(route_fixture) is True, "default route should be aggregated")
    assert_true(default_route_device_from_text(route_fixture) == "eth0", "default route device should parse")
    route_without_up_fixture = route_fixture.replace("0003", "0002", 1)
    assert_true(
        detect_default_route_from_text(route_without_up_fixture) is False,
        "a gateway route without RTF_UP must fail closed",
    )
    assert_true(
        default_route_device_from_text(route_without_up_fixture) == "",
        "a gateway route without RTF_UP must not identify a device",
    )
    non_default_mask_fixture = route_fixture.replace("100 00000000", "100 00FFFFFF", 1)
    assert_true(
        detect_default_route_from_text(non_default_mask_fixture) is False,
        "a zero destination with a nonzero mask must fail closed",
    )
    assert_true(
        default_route_device_from_text(non_default_mask_fixture) == "",
        "a zero destination with a nonzero mask must not identify a device",
    )
    zero_gateway_fixture = route_fixture.replace("010200C0", "00000000", 1)
    assert_true(
        default_route_device_from_text(zero_gateway_fixture) == "",
        "a gateway-flagged route with no gateway must fail closed",
    )
    direct_route_fixture = route_fixture.replace("010200C0 0003", "00000000 0001", 1)
    assert_true(
        default_route_device_from_text(direct_route_fixture) == "eth0",
        "a canonical on-link default route should remain valid",
    )
    preferred_route_fixture = route_fixture + "\nwlan0 00000000 010200C0 0003 0 0 600 00000000 0 0 0"
    assert_true(
        default_route_device_from_text(preferred_route_fixture) == "eth0",
        "the lowest-metric default route should select its device",
    )
    ambiguous_route_fixture = route_fixture + "\nwlan0 00000000 010200C0 0003 0 0 100 00000000 0 0 0"
    assert_true(
        default_route_device_from_text(ambiguous_route_fixture) == "",
        "equal-metric default routes on multiple devices should fail closed",
    )
    malformed_route_rows = [
        "eth0 00000000 010200C0 0003 0 0 100 00000000",
        "eth0 00000000 1 0003 0 0 100 00000000 0 0 0",
        "eth0 00000000 -1 0003 0 0 100 00000000 0 0 0",
        "eth0 00000000 100000000 0003 0 0 100 00000000 0 0 0",
        "eth0 00000000 0x010200C0 0003 0 0 100 00000000 0 0 0",
        "eth0 00000000 010200C0 3 0 0 100 00000000 0 0 0",
        "eth0 00000000 010200C0 -1 0 0 100 00000000 0 0 0",
        "eth0 00000000 010200C0 0003 0 0 -1 00000000 0 0 0",
        "eth0 00000000 010200C0 0203 0 0 100 00000000 0 0 0",
        "eth0 00000000 010200C0 1003 0 0 100 00000000 0 0 0",
    ]
    for malformed_row in malformed_route_rows:
        malformed_fixture = " ".join(PROC_NET_ROUTE_HEADER) + "\n" + malformed_row
        assert_true(
            default_route_device_from_text(malformed_fixture) == "",
            f"malformed route row must fail closed: {malformed_row}",
        )
    wrong_header_fixture = route_fixture.replace("Iface", "Device", 1)
    assert_true(default_route_device_from_text(wrong_header_fixture) == "", "unexpected route header must fail closed")

    route_json_fixture = json.dumps(
        [{"dst": "default", "gateway": "192.0.2.1", "dev": "eth0", "protocol": "dhcp", "metric": 100, "flags": []}]
    )
    direct_route_json_fixture = json.dumps(
        [{"dst": "default", "dev": "eth0", "protocol": "static", "scope": "link", "metric": 100, "flags": []}]
    )
    preferred_route_json_fixture = json.dumps(
        [
            {"dst": "default", "gateway": "192.0.2.1", "dev": "eth0", "metric": 100, "flags": []},
            {"dst": "default", "gateway": "192.0.2.1", "dev": "wlan0", "metric": 600, "flags": []},
        ]
    )
    ambiguous_route_json_fixture = json.dumps(
        [
            {"dst": "default", "gateway": "192.0.2.1", "dev": "eth0", "metric": 100, "flags": []},
            {"dst": "default", "gateway": "192.0.2.1", "dev": "wlan0", "metric": 100, "flags": []},
        ]
    )
    same_device_ambiguous_route_json_fixture = json.dumps(
        [
            {"dst": "default", "gateway": "192.0.2.1", "dev": "eth0", "metric": 100, "flags": []},
            {"dst": "default", "gateway": "192.0.2.2", "dev": "eth0", "metric": 100, "flags": []},
        ]
    )
    wifi_route_json_fixture = json.dumps(
        [{"dst": "default", "gateway": "192.0.2.1", "dev": "wlan0", "metric": 100, "flags": []}]
    )
    assert_true(default_route_devices_from_ip_json(route_json_fixture) == ["eth0"], "typed default route should parse")
    assert_true(
        default_route_devices_from_ip_json(direct_route_json_fixture) == ["eth0"],
        "typed on-link default route should parse",
    )
    assert_true(
        default_route_devices_from_ip_json(preferred_route_json_fixture) == ["eth0"],
        "typed route should select the lowest metric",
    )
    assert_true(
        default_route_devices_from_ip_json(ambiguous_route_json_fixture) == [],
        "equal typed metrics should fail closed",
    )
    rejected_route_json_fixtures = [
        "",
        "{}",
        "not-json",
        json.dumps([{"dst": "default", "tos": "0x10", "gateway": "192.0.2.1", "dev": "eth0", "flags": []}]),
        json.dumps([{"type": "local", "dst": "default", "dev": "eth0", "metric": 0, "flags": []}]),
        json.dumps([{"type": "blackhole", "dst": "default", "metric": 0, "flags": []}]),
        json.dumps([{"dst": "default", "dev": "*", "metric": 0, "flags": []}]),
        json.dumps([{"dst": "default", "dev": "eth0", "metric": -1, "flags": []}]),
        json.dumps([{"dst": "default", "dev": "eth0", "metric": 0x100000000, "flags": []}]),
        json.dumps([{"dst": "default", "dev": "eth0", "metric": True, "flags": []}]),
        json.dumps([{"dst": "default", "dev": "eth0", "metric": 0, "scope": "host", "flags": []}]),
        json.dumps([{"dst": "default", "dev": "eth0", "metric": 0, "table": "local", "flags": []}]),
        json.dumps([{"dst": "default", "dev": "eth0", "metric": 0, "table": 254.0, "flags": []}]),
        json.dumps([{"dst": "default", "dev": "eth0", "metric": 0, "gateway": "127.0.0.1", "flags": []}]),
        json.dumps([{"dst": "default", "dev": "eth0", "metric": 0, "gateway": "bad", "flags": []}]),
        json.dumps([{"dst": "default", "dev": "eth0", "metric": 0, "gateway": "255.255.255.255", "flags": []}]),
        json.dumps([{"dst": "default", "dev": "eth0", "metric": 0, "flags": ["linkdown"]}]),
        json.dumps([{"dst": "default", "dev": "eth0", "metric": 0, "flags": ["not-an-iproute-flag"]}]),
        json.dumps([{"dst": "default", "dev": "eth0", "metric": 0, "flags": [], "nexthops": []}]),
        json.dumps([{"dst": "default", "dev": "eth0", "metric": 0, "flags": [], "via": {"family": "inet6"}}]),
        json.dumps([{"dst": "192.0.2.0/24", "dev": "eth0", "metric": 0, "flags": []}]),
        same_device_ambiguous_route_json_fixture,
        json.dumps(
            [
                {"dst": "default", "gateway": "192.0.2.1", "dev": "eth0", "metric": 100, "flags": []},
                {"dst": "default", "gateway": "192.0.2.1", "dev": 123, "metric": 600, "flags": []},
            ]
        ),
    ]
    for rejected_fixture in rejected_route_json_fixtures:
        assert_true(
            default_route_devices_from_ip_json(rejected_fixture) == [],
            f"untrusted typed route must fail closed: {rejected_fixture}",
        )
    assert_true(detect_dns_from_text(resolver_fixture) is True, "resolver should be aggregated")

    fake_nm_state = {"profiles_loaded": set()}

    def fake_runner(args: list[str], timeout_sec: int) -> CommandResult:
        if args == IP_ROUTE_DEFAULT_COMMAND:
            return CommandResult("ok", route_json_fixture)
        if args == ["nmcli", "-t", "-f", "RUNNING", "general"]:
            return CommandResult("ok", "running\n")
        if args == ["nmcli", "-t", "-f", "CONNECTIVITY", "general"]:
            return CommandResult("ok", "full\n")
        if args == ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"]:
            return CommandResult("ok", device_fixture)
        if args == ["nmcli", "-t", "-f", "TYPE,DEVICE", "connection", "show", "--active"]:
            return CommandResult("ok", active_fixture)
        if args == ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "no"]:
            return CommandResult("ok", wifi_list_fixture)
        if args == ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes"]:
            return CommandResult("ok", wifi_list_fixture)
        if args == ["nmcli", "-t", "-f", "DEVICE,IN-USE,SIGNAL", "device", "wifi", "list", "--rescan", "no"]:
            return CommandResult("ok", "wlan0: :92\nwlan0:*:68\n")
        if args == ["ip", "-o", "route", "get", "192.0.2.10"]:
            return CommandResult("ok", "192.0.2.10 dev eth0 src 192.0.2.44 uid 0\n")
        if len(args) == 7 and args[:6] == ["nmcli", "-t", "-f", "connection.id", "connection", "show"]:
            profile = args[6]
            return CommandResult("ok", profile + "\n") if profile in fake_nm_state["profiles_loaded"] else CommandResult("failed")
        if len(args) == 7 and args[:6] == ["nmcli", "-t", "-f", "IP4.ADDRESS", "connection", "show"]:
            return CommandResult("ok", "IP4.ADDRESS[1]:192.0.2.44/24\n")
        if args == ["nmcli", "connection", "load", args[-1]]:
            loaded_profile = pathlib.Path(args[-1]).name.removesuffix(".nmconnection")
            if loaded_profile == dedicated_profile_filename(DEFAULT_PROFILE_NAME).removesuffix(".nmconnection"):
                loaded_profile = DEFAULT_PROFILE_NAME
            if loaded_profile == dedicated_profile_filename(DEFAULT_PERSISTENT_PROFILE_NAME).removesuffix(".nmconnection"):
                loaded_profile = DEFAULT_PERSISTENT_PROFILE_NAME
            fake_nm_state["profiles_loaded"].add(loaded_profile)
            return CommandResult("ok", "loaded Fake product wifi\n")
        if len(args) == 7 and args[:6] == ["nmcli", "--wait", "1", "connection", "up", "id"]:
            return CommandResult("ok", "successfully activated fake-token-value\n")
        if len(args) == 5 and args[:4] == ["nmcli", "connection", "down", "id"]:
            return CommandResult("ok", "down fake-uuid-value\n")
        if len(args) == 5 and args[:4] == ["nmcli", "connection", "delete", "id"]:
            fake_nm_state["profiles_loaded"].discard(args[4])
            return CommandResult("ok", "deleted Fake product wifi\n")
        return CommandResult("failed")

    def runner_with_route(
        base_runner: Callable[[list[str], float], CommandResult],
        route_json: str,
        *,
        route_status: str = "ok",
    ) -> Callable[[list[str], float], CommandResult]:
        def wrapped(args: list[str], timeout_sec: float) -> CommandResult:
            if args == IP_ROUTE_DEFAULT_COMMAND:
                return CommandResult(route_status, route_json if route_status == "ok" else "")
            return base_runner(args, timeout_sec)

        return wrapped

    def fake_reader(path: pathlib.Path) -> tuple[str, bool]:
        if str(path) == "/proc/net/route":
            return route_fixture, True
        if str(path) == "/etc/resolv.conf":
            return resolver_fixture, True
        return "", False

    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c9-6-wifi-apply-self-test-", dir="/tmp"))
    try:
        fake_bin_dir = root / "fake-bin"
        fake_bin_dir.mkdir(mode=0o700)
        fake_nmcli = fake_bin_dir / "nmcli"
        fake_nmcli.write_text(
            "#!/usr/bin/python3\n"
            f"import sys\nsys.stdout.write('x' * {MAX_READ_ONLY_COMMAND_OUTPUT_BYTES + 1})\n",
            encoding="utf-8",
        )
        fake_nmcli.chmod(0o700)
        previous_path = os.environ.get("PATH")
        os.environ["PATH"] = f"{fake_bin_dir}:{previous_path or ''}"
        try:
            oversized_command_result = run_read_only_command(
                ["nmcli", "-t", "-f", "CONNECTIVITY", "general"],
                1,
            )
        finally:
            if previous_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = previous_path
        assert_true(
            oversized_command_result.status == "too_large",
            "read-only subprocess output must be bounded before capture completes",
        )

        os.environ["SSH_CONNECTION"] = "192.0.2.10 54321 192.0.2.44 22"
        status = collect_read_only_status(
            timeout_sec=1,
            command_runner=fake_runner,
            file_reader=fake_reader,
            nmcli_path="/usr/bin/nmcli",
        )
        assert_true(status["network_manager_available"] is True, "NetworkManager should be detected")
        assert_true(status["nmcli_available"] is True, "nmcli should be detected")
        assert_true(status["wifi_device_present"] is True, "wifi device should be true")
        assert_true(status["ethernet_active"] is True, "ethernet active should be true")
        assert_true(status["wifi_active"] is True, "wifi active should be true")
        assert_true(status["default_route_present"] is True, "default route should be true")
        assert_true(status["dns_configured"] is True, "resolver should be true")
        assert_true(status["connectivity"] == "not_checked", "connectivity should not be externally checked")
        indicator = collect_connectivity_indicator(
            timeout_sec=1,
            command_runner=fake_runner,
            nmcli_path="/usr/bin/nmcli",
            ip_path="/usr/sbin/ip",
        )
        assert_true(indicator["transport"] == "ethernet", "default Ethernet route should drive the indicator")
        assert_true(indicator["internet"] == "online", "cached full connectivity should show online")
        assert_true(indicator["wifi_signal"] == UNKNOWN, "Ethernet should not claim Wi-Fi signal")
        assert_true(indicator["guardrails"]["external_connectivity_probe"] is False, "indicator must not probe")
        assert_true(indicator["guardrails"]["history_persisted"] is False, "indicator must not retain history")

        direct_indicator = collect_connectivity_indicator(
            timeout_sec=1,
            command_runner=runner_with_route(fake_runner, direct_route_json_fixture),
            nmcli_path="/usr/bin/nmcli",
            ip_path="/usr/sbin/ip",
        )
        assert_true(direct_indicator["transport"] == "ethernet", "an on-link default should select Ethernet")
        assert_true(direct_indicator["internet"] == "online", "cached full may confirm a valid on-link default")

        preferred_indicator = collect_connectivity_indicator(
            timeout_sec=1,
            command_runner=runner_with_route(fake_runner, preferred_route_json_fixture),
            nmcli_path="/usr/bin/nmcli",
            ip_path="/usr/sbin/ip",
        )
        assert_true(preferred_indicator["transport"] == "ethernet", "the lowest route metric should select Ethernet")
        assert_true(preferred_indicator["internet"] == "online", "cached full may confirm the preferred default route")

        wifi_indicator = collect_connectivity_indicator(
            timeout_sec=1,
            command_runner=runner_with_route(fake_runner, wifi_route_json_fixture),
            nmcli_path="/usr/bin/nmcli",
            ip_path="/usr/sbin/ip",
        )
        assert_true(wifi_indicator["transport"] == "wifi", "default Wi-Fi route should drive the indicator")
        assert_true(wifi_indicator["wifi_signal"] == "medium", "active Wi-Fi signal should be bucketed")
        assert_true(wifi_indicator["internet"] == "online", "Wi-Fi may be online")

        disconnected_device_fixture = "eth0:ethernet:disconnected\nwlan0:wifi:disconnected\n"

        def disconnected_runner(args: list[str], timeout_sec: int) -> CommandResult:
            if args == ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"]:
                return CommandResult("ok", disconnected_device_fixture)
            if args == ["nmcli", "-t", "-f", "TYPE,DEVICE", "connection", "show", "--active"]:
                return CommandResult("ok", "")
            if args == ["nmcli", "-t", "-f", "CONNECTIVITY", "general"]:
                return CommandResult("ok", "full\n")
            return CommandResult("failed")

        disconnected_indicator = collect_connectivity_indicator(
            timeout_sec=1,
            command_runner=runner_with_route(disconnected_runner, "[]"),
            nmcli_path="/usr/bin/nmcli",
            ip_path="/usr/sbin/ip",
        )
        assert_true(disconnected_indicator["transport"] == "none", "no active link should show no transport")
        assert_true(
            disconnected_indicator["internet"] == "offline",
            "stale cached full state must not override an absent transport",
        )

        def active_wifi_without_route_runner(args: list[str], timeout_sec: float) -> CommandResult:
            if args == ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"]:
                return CommandResult("ok", "wlan0:wifi:connected\n")
            if args == ["nmcli", "-t", "-f", "TYPE,DEVICE", "connection", "show", "--active"]:
                return CommandResult("ok", "802-11-wireless:wlan0\n")
            if args == ["nmcli", "-t", "-f", "CONNECTIVITY", "general"]:
                return CommandResult("ok", "full\n")
            if args == [
                "nmcli",
                "-t",
                "-f",
                "DEVICE,IN-USE,SIGNAL",
                "device",
                "wifi",
                "list",
                "--rescan",
                "no",
            ]:
                return CommandResult("ok", "wlan0:*:77\n")
            return CommandResult("failed")

        active_without_route_indicator = collect_connectivity_indicator(
            timeout_sec=1,
            command_runner=runner_with_route(active_wifi_without_route_runner, "[]"),
            nmcli_path="/usr/bin/nmcli",
            ip_path="/usr/sbin/ip",
        )
        assert_true(
            active_without_route_indicator["transport"] == "wifi",
            "an active Wi-Fi link may still identify its local transport without a route",
        )
        assert_true(
            active_without_route_indicator["internet"] == UNKNOWN,
            "cached full must not show online without a verified default route",
        )
        for rejected_route_json in rejected_route_json_fixtures:
            malformed_indicator = collect_connectivity_indicator(
                timeout_sec=1,
                command_runner=runner_with_route(active_wifi_without_route_runner, rejected_route_json),
                nmcli_path="/usr/bin/nmcli",
                ip_path="/usr/sbin/ip",
            )
            assert_true(
                malformed_indicator["internet"] == UNKNOWN,
                f"untrusted typed route must not promote cached full: {rejected_route_json}",
            )
        oversized_nmcli_output = "\n" * (MAX_READ_ONLY_COMMAND_OUTPUT_BYTES + 1)

        def oversized_nmcli_runner(args: list[str], timeout_sec: float) -> CommandResult:
            if args == ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"]:
                return CommandResult("ok", oversized_nmcli_output + "wlan0:wifi:connected\n")
            if args == ["nmcli", "-t", "-f", "TYPE,DEVICE", "connection", "show", "--active"]:
                return CommandResult("ok", oversized_nmcli_output + "802-11-wireless:wlan0\n")
            if args == ["nmcli", "-t", "-f", "CONNECTIVITY", "general"]:
                return CommandResult("ok", oversized_nmcli_output + "full\n")
            if args == IP_ROUTE_DEFAULT_COMMAND:
                return CommandResult("ok", wifi_route_json_fixture)
            return CommandResult("failed")

        oversized_indicator = collect_connectivity_indicator(
            timeout_sec=1,
            command_runner=oversized_nmcli_runner,
            nmcli_path="/usr/bin/nmcli",
            ip_path="/usr/sbin/ip",
        )
        assert_true(oversized_indicator["internet"] == UNKNOWN, "oversized status input must fail closed")
        assert_true(
            oversized_indicator["read_only_checks"]["device_status"] == "too_large",
            "oversized status input should be classified",
        )
        stale_route_indicator = collect_connectivity_indicator(
            timeout_sec=1,
            command_runner=runner_with_route(disconnected_runner, route_json_fixture),
            nmcli_path="/usr/bin/nmcli",
            ip_path="/usr/sbin/ip",
        )
        assert_true(stale_route_indicator["transport"] == UNKNOWN, "stale route must not prove a transport")
        assert_true(stale_route_indicator["internet"] == UNKNOWN, "stale route plus cached full must not show online")

        mismatched_device_fixture = "wlan0:wifi:disconnected\nwlan1:wifi:connected\n"
        mismatched_active_fixture = "802-11-wireless:wlan1\n"

        def mismatched_runner(args: list[str], timeout_sec: int) -> CommandResult:
            if args == ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"]:
                return CommandResult("ok", mismatched_device_fixture)
            if args == ["nmcli", "-t", "-f", "TYPE,DEVICE", "connection", "show", "--active"]:
                return CommandResult("ok", mismatched_active_fixture)
            if args == ["nmcli", "-t", "-f", "CONNECTIVITY", "general"]:
                return CommandResult("ok", "full\n")
            return CommandResult("failed")

        mismatched_indicator = collect_connectivity_indicator(
            timeout_sec=1,
            command_runner=runner_with_route(mismatched_runner, wifi_route_json_fixture),
            nmcli_path="/usr/bin/nmcli",
            ip_path="/usr/sbin/ip",
        )
        assert_true(
            mismatched_indicator["transport"] == UNKNOWN,
            "a stale route must not borrow another active device of the same type",
        )
        assert_true(
            mismatched_indicator["internet"] == UNKNOWN,
            "cached full must not override an exact interface mismatch",
        )
        ambiguous_route_indicator = collect_connectivity_indicator(
            timeout_sec=1,
            command_runner=runner_with_route(fake_runner, ambiguous_route_json_fixture),
            nmcli_path="/usr/bin/nmcli",
            ip_path="/usr/sbin/ip",
        )
        assert_true(
            ambiguous_route_indicator["transport"] == UNKNOWN,
            "multiple default-route devices should not choose a transport implicitly",
        )
        assert_true(
            ambiguous_route_indicator["internet"] == UNKNOWN,
            "multiple default-route devices should not inherit cached full connectivity",
        )
        budget_clock = [0.0]
        budget_timeouts: list[float] = []

        def budget_runner(args: list[str], timeout_sec: float) -> CommandResult:
            budget_timeouts.append(timeout_sec)
            budget_clock[0] += 0.4
            return fake_runner(args, 1)

        collect_connectivity_indicator(
            timeout_sec=1,
            command_runner=budget_runner,
            nmcli_path="/usr/bin/nmcli",
            ip_path="/usr/sbin/ip",
            monotonic_clock=lambda: budget_clock[0],
        )
        assert_true(len(budget_timeouts) == 3, "expired snapshot budget should skip later commands")
        assert_true(
            budget_timeouts[0] <= 1.0 and budget_timeouts[-1] <= 0.21,
            "all network commands should share one total refresh budget",
        )
        local_networks, local_list_status = list_wifi_networks_for_local_ui(
            timeout_sec=1,
            command_runner=fake_runner,
            nmcli_path="/usr/bin/nmcli",
        )
        assert_true(local_list_status == "ok", "local Wi-Fi list should parse")
        assert_true(local_networks[0]["ssid"] == "FAKE-STORE-WIFI", "local list may keep SSID for UI only")
        refreshed_networks, refreshed_list_status = list_wifi_networks_for_local_ui(
            timeout_sec=1,
            command_runner=fake_runner,
            nmcli_path="/usr/bin/nmcli",
            rescan=True,
        )
        assert_true(refreshed_list_status == "ok", "manual refresh Wi-Fi list should parse")
        assert_true(refreshed_networks[0]["ssid"] == "FAKE-STORE-WIFI", "rescan list should keep sorting")
        for key in (
            "network_changed",
            "credentials_collected",
            "ssid_written",
            "password_written",
            "ip_written",
            "mac_written",
            "dns_written",
            "nmcli_modify_called",
            "writer_called",
            "real_config_read",
            "real_config_written",
        ):
            assert_true(status["privacy_flags"][key] is False, f"{key} should be false")

        read_only_out = require_tmp_dir(str(root / "read-only"))
        write_read_only_artifacts(read_only_out, status)
        assert_artifact_permissions(read_only_out, (STATUS_FILENAME, SUMMARY_FILENAME))
        public_text = (read_only_out / STATUS_FILENAME).read_text(encoding="utf-8")
        public_text += (read_only_out / SUMMARY_FILENAME).read_text(encoding="utf-8")
        assert_no_forbidden_values(public_text)

        summary_lower = (read_only_out / SUMMARY_FILENAME).read_text(encoding="utf-8").lower()
        for marker in ("ssid", "password", "senha", "bssid", "gateway", "hostname"):
            assert_true(marker not in summary_lower, f"summary should not contain {marker}")

        plan = build_plan(status)
        assert_true(plan["apply_enabled"] is False, "plan should keep apply disabled")
        assert_true(plan["target_network"] == "redacted", "plan target should be redacted")
        assert_true(
            plan["credentials_source"] == "not_collected_in_read_only_or_plan",
            "plan should not collect credentials",
        )
        plan_out = require_tmp_dir(str(root / "plan"))
        write_plan_artifacts(plan_out, status, plan)
        assert_artifact_permissions(plan_out, (STATUS_FILENAME, PLAN_FILENAME, SUMMARY_FILENAME))
        plan_text = (plan_out / STATUS_FILENAME).read_text(encoding="utf-8")
        plan_text += (plan_out / PLAN_FILENAME).read_text(encoding="utf-8")
        plan_text += (plan_out / SUMMARY_FILENAME).read_text(encoding="utf-8")
        assert_no_forbidden_values(plan_text)

        no_nmcli_status = collect_read_only_status(
            timeout_sec=1,
            command_runner=fake_runner,
            file_reader=fake_reader,
            nmcli_path="",
        )
        assert_true(no_nmcli_status["nmcli_available"] is False, "nmcli absence should be tolerated")
        assert_true(
            no_nmcli_status["network_manager_available"] is False,
            "NetworkManager should be false when nmcli is absent",
        )

        preflight_out = require_tmp_dir(str(root / "preflight"))
        preflight = build_preflight_apply(
            status,
            profile_name=DEFAULT_PROFILE_NAME,
            out_dir=preflight_out,
            timeout_sec=1,
            command_runner=fake_runner,
        )
        assert_true(preflight["ssh_path_category"] == "ethernet", "ssh path should be classified by category")
        assert_true(preflight["apply_allowed"] is True, "preflight should allow controlled apply fixture")
        write_preflight_artifacts(preflight_out, preflight)
        assert_artifact_permissions(preflight_out, (STATUS_FILENAME, PREFLIGHT_FILENAME, SUMMARY_FILENAME))
        preflight_text = (preflight_out / STATUS_FILENAME).read_text(encoding="utf-8")
        preflight_text += (preflight_out / PREFLIGHT_FILENAME).read_text(encoding="utf-8")
        preflight_text += (preflight_out / SUMMARY_FILENAME).read_text(encoding="utf-8")
        assert_no_forbidden_values(preflight_text)

        os.environ["SSH_CONNECTION"] = "192.0.2.20 54321 192.0.2.44 22"

        def wifi_route_runner(args: list[str], timeout_sec: int) -> CommandResult:
            if args == ["ip", "-o", "route", "get", "192.0.2.20"]:
                return CommandResult("ok", "192.0.2.20 dev wlan0 src 192.0.2.44 uid 0\n")
            return fake_runner(args, timeout_sec)

        blocked_preflight = build_preflight_apply(
            status,
            profile_name=DEFAULT_PROFILE_NAME,
            out_dir=preflight_out,
            timeout_sec=1,
            command_runner=wifi_route_runner,
        )
        assert_true(blocked_preflight["apply_allowed"] is False, "wifi ssh path should block apply by default")
        assert_true("ssh_path_wifi" in blocked_preflight["abort_reasons"], "wifi ssh path should be explicit")
        allowed_wifi_preflight = build_preflight_apply(
            status,
            profile_name=DEFAULT_PROFILE_NAME,
            out_dir=preflight_out,
            timeout_sec=1,
            allow_ssh_risk_with_local_console_confirmed=True,
            local_console_confirmed=True,
            command_runner=wifi_route_runner,
        )
        assert_true(allowed_wifi_preflight["apply_allowed"] is True, "local console should allow wifi ssh risk")
        assert_true(
            allowed_wifi_preflight["ssh_path_risk_acknowledged"] is True,
            "ssh risk should be acknowledged",
        )
        assert_true(allowed_wifi_preflight["local_console_confirmed"] is True, "local console should be recorded")
        assert_true(
            allowed_wifi_preflight["apply_requires_local_recovery"] is True,
            "wifi ssh apply should require local recovery",
        )

        secrets_parent = root / "secrets"
        secrets_parent.mkdir(mode=PRIVATE_DIR_MODE)
        safe_secret = secrets_parent / "wifi.json"
        safe_secret.write_text(
            json.dumps({"ssid": "FAKE-STORE-WIFI", "psk": "fake-password"}),
            encoding="utf-8",
        )
        os.chmod(safe_secret, PRIVATE_FILE_MODE)
        loaded = load_wifi_secrets(str(safe_secret))
        assert_true(loaded["ssid"] == "FAKE-STORE-WIFI", "safe secrets should load internally")

        insecure_secret = secrets_parent / "insecure.json"
        insecure_secret.write_text(json.dumps({"ssid": "FAKE-STORE-WIFI", "psk": "fake-password"}), encoding="utf-8")
        os.chmod(insecure_secret, 0o644)
        assert_raises(lambda: load_wifi_secrets(str(insecure_secret)), "insecure secrets-file should abort")
        assert_raises(lambda: load_wifi_secrets("/var/tmp/wifi.json"), "secrets-file outside /tmp should abort")
        symlink_secret = secrets_parent / "link.json"
        symlink_secret.symlink_to(safe_secret)
        assert_raises(lambda: load_wifi_secrets(str(symlink_secret)), "symlink secrets-file should abort")

        assert_raises(
            lambda: assert_apply_command(["nmcli", "connection", "delete", "id", "home-wifi"], DEFAULT_PROFILE_NAME),
            "rollback must not target non-dedicated profile",
        )
        assert_raises(
            lambda: assert_apply_command(
                ["nmcli", "device", "wifi", "connect", "FAKE-STORE-WIFI", "password", "fake-password"],
                DEFAULT_PROFILE_NAME,
            ),
            "apply must not pass credentials on nmcli argv",
        )

        apply_out = require_tmp_dir(str(root / "apply"))
        os.environ["SSH_CONNECTION"] = "192.0.2.10 54321 192.0.2.44 22"
        apply_status = apply_wifi_controlled(
            out_dir=apply_out,
            timeout_sec=1,
            enable_real_apply=True,
            confirmation=CONFIRM_REAL_WIFI_APPLY,
            secrets_file=str(safe_secret),
            profile_name=DEFAULT_PROFILE_NAME,
            rollback_after_test=True,
            keep_dedicated_profile=False,
            persistent_product_wifi=False,
            confirm_keep_dedicated_profile=None,
            cleanup_secrets_file=False,
            allow_ssh_risk_with_local_console_confirmed=False,
            local_console_confirmed=False,
            system_connection_dir=root / "system-connections",
            command_runner=fake_runner,
            file_reader=fake_reader,
            nmcli_path="/usr/bin/nmcli",
        )
        assert_true(apply_status["wifi_activation_result"] == "success", "fixture apply should succeed")
        assert_true(apply_status["rollback_status"] == "attempted", "rollback-after-test should run")
        assert_artifact_permissions(
            apply_out,
            (STATUS_FILENAME, PREFLIGHT_FILENAME, SUMMARY_FILENAME, ROLLBACK_FILENAME),
        )
        apply_text = (apply_out / STATUS_FILENAME).read_text(encoding="utf-8")
        apply_text += (apply_out / PREFLIGHT_FILENAME).read_text(encoding="utf-8")
        apply_text += (apply_out / ROLLBACK_FILENAME).read_text(encoding="utf-8")
        apply_text += (apply_out / SUMMARY_FILENAME).read_text(encoding="utf-8")
        assert_no_forbidden_values(apply_text)

        persistent_out = require_tmp_dir(str(root / "persistent-apply"))
        persistent_status = apply_wifi_controlled(
            out_dir=persistent_out,
            timeout_sec=1,
            enable_real_apply=True,
            confirmation=CONFIRM_REAL_WIFI_APPLY,
            secrets_file=str(safe_secret),
            profile_name=DEFAULT_PERSISTENT_PROFILE_NAME,
            rollback_after_test=False,
            keep_dedicated_profile=True,
            persistent_product_wifi=True,
            confirm_keep_dedicated_profile=CONFIRM_KEEP_DEDICATED_PROFILE,
            cleanup_secrets_file=False,
            allow_ssh_risk_with_local_console_confirmed=False,
            local_console_confirmed=False,
            system_connection_dir=root / "system-connections",
            command_runner=fake_runner,
            file_reader=fake_reader,
            nmcli_path="/usr/bin/nmcli",
        )
        assert_true(persistent_status["wifi_activation_result"] == "success", "persistent fixture apply should succeed")
        assert_true(persistent_status["rollback_after_test"] is False, "persistent apply should not rollback after success")
        assert_true(persistent_status["profile_retained"] is True, "persistent apply should retain profile")
        assert_true(
            persistent_status["dedicated_profile_persistent"] is True,
            "persistent apply should record dedicated persistence",
        )
        assert_true(persistent_status["autoconnect_enabled"] is True, "persistent apply should enable autoconnect")
        persistent_source = root / "system-connections" / dedicated_profile_filename(DEFAULT_PERSISTENT_PROFILE_NAME)
        assert_true(persistent_source.exists(), "persistent apply should retain dedicated profile source")
        assert_true(file_mode(persistent_source) == PRIVATE_FILE_MODE, "persistent profile source should be 0600")
        assert_artifact_permissions(persistent_out, (STATUS_FILENAME, PREFLIGHT_FILENAME, SUMMARY_FILENAME))
        persistent_text = (persistent_out / STATUS_FILENAME).read_text(encoding="utf-8")
        persistent_text += (persistent_out / PREFLIGHT_FILENAME).read_text(encoding="utf-8")
        persistent_text += (persistent_out / SUMMARY_FILENAME).read_text(encoding="utf-8")
        assert_no_forbidden_values(persistent_text)

        failure_out = require_tmp_dir(str(root / "failure"))
        prepare_out_dir(failure_out)
        failure_status = dict(apply_status)
        failure_status.update(
            {
                "wifi_activation_attempted": True,
                "wifi_activation_result": "failure",
                "failure_category": "auth_failed_suspected",
                "network_changed": True,
                "secrets_file_cleanup": True,
            }
        )
        atomic_write_private_json(failure_out / STATUS_FILENAME, failure_status, failure_out)
        atomic_write_private_json(failure_out / PREFLIGHT_FILENAME, apply_status, failure_out)
        atomic_write_private_json(
            failure_out / ROLLBACK_FILENAME,
            build_rollback_status(
                reason="activation_not_successful",
                attempted=True,
                down_result="failed",
                delete_result="ok",
            ),
            failure_out,
        )
        diagnosis = diagnose_last_failure(
            out_dir=failure_out,
            profile_name=DEFAULT_PROFILE_NAME,
            timeout_sec=1,
            command_runner=fake_runner,
        )
        assert_true(diagnosis["failure_category"] == "auth_failed_suspected", "diagnosis should use public category")
        assert_artifact_permissions(failure_out, (STATUS_FILENAME, PREFLIGHT_FILENAME, ROLLBACK_FILENAME, DIAGNOSE_FILENAME, DIAGNOSE_SUMMARY_FILENAME))
        diagnosis_text = (failure_out / DIAGNOSE_FILENAME).read_text(encoding="utf-8")
        diagnosis_text += (failure_out / DIAGNOSE_SUMMARY_FILENAME).read_text(encoding="utf-8")
        assert_no_forbidden_values(diagnosis_text)

        assert_true(
            classify_failure_from_text("Secrets were required for fake-password") == "auth_failed_suspected",
            "auth text should classify without publishing raw text",
        )
    finally:
        os.environ.pop("SSH_CONNECTION", None)
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run C9.6 Wi-Fi read-only, preflight, controlled apply, or rollback.",
        allow_abbrev=False,
    )
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--timeout-sec", type=int, default=3, help="Per-command timeout for read-only checks.")
    parser.add_argument("--profile-name", default=DEFAULT_PROFILE_NAME, help="Dedicated product profile name.")
    parser.add_argument("--enable-real-apply", action="store_true", help="Required gate for --apply.")
    parser.add_argument("--confirm-real-wifi-apply", help="Exact human confirmation phrase required for --apply.")
    parser.add_argument("--secrets-file", help="Restricted JSON file under /tmp with Wi-Fi credentials for --apply.")
    parser.add_argument("--rollback-after-test", action="store_true", help="Rollback dedicated profile after apply test.")
    parser.add_argument("--keep-dedicated-profile", action="store_true", help="Keep the dedicated profile after successful apply.")
    parser.add_argument(
        "--persistent-product-wifi",
        action="store_true",
        help="Enable C9.8 persistent product Wi-Fi mode with an explicitly confirmed dedicated profile.",
    )
    parser.add_argument(
        "--confirm-keep-dedicated-profile",
        help="Exact C9.8 confirmation phrase required before keeping a dedicated profile.",
    )
    parser.add_argument("--cleanup-secrets-file", action="store_true", help="Remove the temporary secrets file after apply.")
    parser.add_argument(
        "--allow-ssh-risk-with-local-console-confirmed",
        action="store_true",
        help="Allow apply when SSH path is risky and local console is explicitly confirmed.",
    )
    parser.add_argument(
        "--local-console-confirmed",
        action="store_true",
        help="Confirm HDMI/local keyboard recovery is available for risky apply.",
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-test", action="store_true", help="Run local self-tests and exit.")
    modes.add_argument("--read-only", action="store_true", help="Collect sanitized aggregate network state.")
    modes.add_argument("--plan", action="store_true", help="Generate a sanitized future apply plan without applying it.")
    modes.add_argument("--preflight-apply", action="store_true", help="Run sanitized apply preflight without applying.")
    modes.add_argument("--apply", action="store_true", help="Run controlled real Wi-Fi apply only when all gates are present.")
    modes.add_argument("--rollback-last", action="store_true", help="Rollback only the dedicated C9.6 profile.")
    modes.add_argument("--diagnose-last-failure", action="store_true", help="Classify the last sanitized activation failure.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.timeout_sec <= 0 or args.timeout_sec > 120:
            raise AdapterError("timeout-sec must be between 1 and 120")
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0

        out_dir = require_tmp_dir(args.out_dir)
        status = collect_read_only_status(timeout_sec=args.timeout_sec)
        if args.read_only:
            write_read_only_artifacts(out_dir, status)
            print(json.dumps(status, indent=2, sort_keys=True))
            return 0

        if args.plan:
            plan = build_plan(status)
            write_plan_artifacts(out_dir, status, plan)
            print(json.dumps(plan, indent=2, sort_keys=True))
            return 0

        profile_name = require_allowed_profile_name(args.profile_name)
        if args.preflight_apply:
            preflight = build_preflight_apply(
                status,
                profile_name=profile_name,
                out_dir=out_dir,
                timeout_sec=args.timeout_sec,
                allow_ssh_risk_with_local_console_confirmed=args.allow_ssh_risk_with_local_console_confirmed,
                local_console_confirmed=args.local_console_confirmed,
            )
            write_preflight_artifacts(out_dir, preflight)
            print(json.dumps(preflight, indent=2, sort_keys=True))
            return 0

        if args.rollback_last:
            rollback = rollback_dedicated_profile(
                profile_name=profile_name,
                out_dir=out_dir,
                timeout_sec=args.timeout_sec,
                reason="manual_rollback_last",
            )
            print(json.dumps(rollback, indent=2, sort_keys=True))
            return 0

        if args.diagnose_last_failure:
            diagnosis = diagnose_last_failure(
                out_dir=out_dir,
                profile_name=profile_name,
                timeout_sec=args.timeout_sec,
                secrets_file=args.secrets_file,
            )
            print(json.dumps(diagnosis, indent=2, sort_keys=True))
            return 0

        effective_keep_dedicated_profile = args.keep_dedicated_profile or args.persistent_product_wifi
        if args.persistent_product_wifi and args.rollback_after_test:
            raise AdapterError("persistent product wifi cannot use rollback-after-test")
        effective_rollback_after_test = args.rollback_after_test or not effective_keep_dedicated_profile
        apply_status = apply_wifi_controlled(
            out_dir=out_dir,
            timeout_sec=args.timeout_sec,
            enable_real_apply=args.enable_real_apply,
            confirmation=args.confirm_real_wifi_apply,
            secrets_file=args.secrets_file,
            profile_name=profile_name,
            rollback_after_test=effective_rollback_after_test,
            keep_dedicated_profile=effective_keep_dedicated_profile,
            persistent_product_wifi=args.persistent_product_wifi,
            confirm_keep_dedicated_profile=args.confirm_keep_dedicated_profile,
            cleanup_secrets_file=args.cleanup_secrets_file,
            allow_ssh_risk_with_local_console_confirmed=args.allow_ssh_risk_with_local_console_confirmed,
            local_console_confirmed=args.local_console_confirmed,
        )
        print(json.dumps(apply_status, indent=2, sort_keys=True))
        return 0
    except AdapterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except AssertionError:
        print("error: self-test failed", file=sys.stderr)
        return 1
    except Exception:
        print("error: wifi adapter unavailable", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
