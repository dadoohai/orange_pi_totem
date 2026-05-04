#!/usr/bin/env python3
"""C9.5 read-only NetworkManager adapter and future apply plan.

This adapter intentionally implements only --read-only and --plan. It never
collects Wi-Fi credentials, never changes NetworkManager state, and writes only
sanitized artifacts under /tmp.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable


sys.dont_write_bytecode = True


SCHEMA_VERSION = "dadooh-c9.5-wifi-readonly-plan.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c9-5-wifi-readonly"
STATUS_FILENAME = "status.json"
PLAN_FILENAME = "plan.json"
SUMMARY_FILENAME = "summary.txt"
TMP_ROOT = pathlib.Path("/tmp").resolve()
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
UNKNOWN = "unknown"

ALLOWED_READ_ONLY_COMMANDS = {
    ("nmcli", "-t", "-f", "RUNNING", "general"),
    ("nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"),
    ("nmcli", "-t", "-f", "TYPE,DEVICE", "connection", "show", "--active"),
}


class AdapterError(RuntimeError):
    """Public-safe adapter error."""


class CommandResult:
    def __init__(self, status: str, stdout: str = "", returncode: int | None = None) -> None:
        self.status = status
        self.stdout = stdout
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


def run_read_only_command(args: list[str], timeout_sec: int) -> CommandResult:
    assert_read_only_command(args)
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
        return CommandResult("ok", completed.stdout, completed.returncode)
    return CommandResult("failed", returncode=completed.returncode)


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


def parse_device_status(stdout: str) -> dict[str, bool | str]:
    wifi_present = False
    ethernet_active = False
    wifi_active = False
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
        if type_is_ethernet(device_type, device_name) and state_is_connected(state):
            ethernet_active = True

    if not parsed:
        return {
            "wifi_device_present": UNKNOWN,
            "ethernet_active": UNKNOWN,
            "wifi_active": UNKNOWN,
        }

    return {
        "wifi_device_present": wifi_present,
        "ethernet_active": ethernet_active,
        "wifi_active": wifi_active,
    }


def parse_active_connections(stdout: str) -> dict[str, bool | str]:
    ethernet_active = False
    wifi_active = False
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
        if type_is_ethernet(connection_type, device_name):
            ethernet_active = True

    if not parsed:
        return {
            "ethernet_active": False,
            "wifi_active": False,
        }

    return {
        "ethernet_active": ethernet_active,
        "wifi_active": wifi_active,
    }


def detect_default_route_from_text(text: str) -> bool | str:
    lines = text.splitlines()
    if len(lines) < 2:
        return False

    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        destination = parts[1]
        flags = parts[3]
        if destination != "00000000":
            continue
        try:
            route_flags = int(flags, 16)
        except ValueError:
            continue
        if route_flags & 0x2:
            return True
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


def build_plan(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "mode": "plan",
        "apply_enabled": False,
        "target_network": "redacted",
        "credentials_source": "not_collected_in_c9_5",
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
        "Dadooh C9.5 wifi readonly/plan",
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


def write_read_only_artifacts(out_dir: pathlib.Path, status: dict[str, Any]) -> None:
    prepare_out_dir(out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_summary(status), out_dir)


def write_plan_artifacts(out_dir: pathlib.Path, status: dict[str, Any], plan: dict[str, Any]) -> None:
    prepare_out_dir(out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_json(out_dir / PLAN_FILENAME, plan, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_summary(status, plan), out_dir)


def abort_apply() -> None:
    raise AdapterError("apply disabled in C9.5")


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
    forbidden_values = (
        "FAKE-STORE-WIFI",
        "192.0.2.44",
        "aa:bb:cc:dd:ee:ff",
        "192.0.2.1",
        "203.0.113.53",
        "fake-hostname",
        "Fake product wifi",
        "fake-password",
        "fake-token-value",
        "fake-api-key",
    )
    lowered = text.lower()
    for value in forbidden_values:
        assert_true(value.lower() not in lowered, f"public output leaked {value}")


def run_self_test() -> None:
    assert_raises(
        lambda: require_tmp_dir("/var/tmp/dadooh-c9-5-wifi-readonly"),
        "out-dir outside /tmp should fail",
    )
    assert_raises(lambda: abort_apply(), "--apply should abort in C9.5")

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

    device_fixture = "\n".join(
        [
            "eth0:ethernet:connected:Fake product wifi",
            "wlan0:wifi:disconnected:FAKE-STORE-WIFI",
            "aa\\:bb\\:cc\\:dd\\:ee\\:ff:wifi:connected:fake-token-value",
        ]
    )
    parsed_device = parse_device_status(device_fixture)
    assert_true(parsed_device["wifi_device_present"] is True, "wifi device should be detected")
    assert_true(parsed_device["ethernet_active"] is True, "ethernet should be active")
    assert_true(parsed_device["wifi_active"] is True, "wifi active should be detected")

    active_fixture = "\n".join(
        [
            "802-3-ethernet:eth0:Fake product wifi",
            "802-11-wireless:wlan0:FAKE-STORE-WIFI",
        ]
    )
    parsed_active = parse_active_connections(active_fixture)
    assert_true(parsed_active["ethernet_active"] is True, "active ethernet should be detected")
    assert_true(parsed_active["wifi_active"] is True, "active wifi should be detected")

    route_fixture = "\n".join(
        [
            "Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT",
            "eth0 00000000 010200C0 0003 0 0 100 00000000 0 0 0 # 192.0.2.1",
        ]
    )
    resolver_fixture = "\n".join(
        [
            "search fake-hostname.invalid",
            "nameserver 203.0.113.53",
        ]
    )
    assert_true(detect_default_route_from_text(route_fixture) is True, "default route should be aggregated")
    assert_true(detect_dns_from_text(resolver_fixture) is True, "resolver should be aggregated")

    def fake_runner(args: list[str], timeout_sec: int) -> CommandResult:
        assert_read_only_command(args)
        if args == ["nmcli", "-t", "-f", "RUNNING", "general"]:
            return CommandResult("ok", "running\n")
        if args == ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"]:
            return CommandResult("ok", device_fixture)
        if args == ["nmcli", "-t", "-f", "TYPE,DEVICE", "connection", "show", "--active"]:
            return CommandResult("ok", active_fixture)
        return CommandResult("failed")

    def fake_reader(path: pathlib.Path) -> tuple[str, bool]:
        if str(path) == "/proc/net/route":
            return route_fixture, True
        if str(path) == "/etc/resolv.conf":
            return resolver_fixture, True
        return "", False

    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c9-5-wifi-readonly-self-test-", dir="/tmp"))
    try:
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
        assert_true(plan["credentials_source"] == "not_collected_in_c9_5", "plan should not collect credentials")
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
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run C9.5 Wi-Fi read-only NetworkManager adapter or generate the future apply plan.",
        allow_abbrev=False,
    )
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--timeout-sec", type=int, default=3, help="Per-command timeout for read-only checks.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-test", action="store_true", help="Run local self-tests and exit.")
    modes.add_argument("--read-only", action="store_true", help="Collect sanitized aggregate network state.")
    modes.add_argument("--plan", action="store_true", help="Generate a sanitized future apply plan without applying it.")
    modes.add_argument("--apply", action="store_true", help="Disabled in C9.5; exits with an error.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.timeout_sec <= 0 or args.timeout_sec > 30:
            raise AdapterError("timeout-sec must be between 1 and 30")
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0
        if args.apply:
            abort_apply()

        out_dir = require_tmp_dir(args.out_dir)
        status = collect_read_only_status(timeout_sec=args.timeout_sec)
        if args.read_only:
            write_read_only_artifacts(out_dir, status)
            print(json.dumps(status, indent=2, sort_keys=True))
            return 0

        plan = build_plan(status)
        write_plan_artifacts(out_dir, status, plan)
        print(json.dumps(plan, indent=2, sort_keys=True))
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
