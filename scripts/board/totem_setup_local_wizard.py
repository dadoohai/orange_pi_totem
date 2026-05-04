#!/usr/bin/env python3
"""C9.4 controlled local setup wizard for HDMI + USB keyboard.

This is a local, keyboard-driven setup path for the totem itself. It uses only
Python stdlib, writes mock/local setup artifacts under /tmp, validates the
candidate with the C5.1 contract, and does not expose a free shell or execute
operational commands.
"""

from __future__ import annotations

import argparse
import curses
import json
import pathlib
import shutil
import stat
import sys
import tempfile
from typing import Any


sys.dont_write_bytecode = True

import totem_setup_minimal_server as setup


SCHEMA_VERSION = "dadooh-c9.4-setup-product-local-v0.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c9-4-setup-product-v0"

BRAND = "Dadooh"
TITLE = "Configuracao do Totem"
INTERFACE_MODE = "local_hdmi_keyboard_controlled"
SETUP_SOURCE = "c9.4-setup-product-local-v0"

CANDIDATE_FILENAME = "config.candidate.json"
STATUS_FILENAME = "setup-status.json"
SUMMARY_FILENAME = "summary.txt"
CANCELLED_FILENAME = "setup-cancelled.json"

STEPS = ("Conexao", "Ambiente", "Tela", "Revisao", "Concluir")

NETWORK_OPTIONS: tuple[dict[str, str], ...] = (
    {
        "key": "existing_connection",
        "label": "Usar conexao atual",
        "description": "Apenas verifica um estado agregado, sem alterar rede.",
    },
    {
        "key": "wifi_future",
        "label": "Configurar Wi-Fi - em breve",
        "description": "Reserva o passo para a proxima etapa do produto.",
    },
    {
        "key": "mock",
        "label": "Continuar em modo de bancada/mock",
        "description": "Segue sem verificar internet ou rede real.",
    },
)

DISPLAY_OPTIONS: tuple[dict[str, str | int], ...] = (
    {
        "key": "landscape",
        "label": "Paisagem",
        "description": "Tela na posicao normal.",
        "rotation_deg": 0,
    },
    {
        "key": "portrait_right",
        "label": "Retrato para direita",
        "description": "Topo da imagem virado para a direita.",
        "rotation_deg": 90,
    },
    {
        "key": "portrait_left",
        "label": "Retrato para esquerda",
        "description": "Topo da imagem virado para a esquerda.",
        "rotation_deg": 270,
    },
    {
        "key": "landscape_inverted",
        "label": "Invertido",
        "description": "Imagem de cabeca para baixo.",
        "rotation_deg": 180,
    },
)

NETWORK_STEP_BY_KEY = {item["key"]: item for item in NETWORK_OPTIONS}
DISPLAY_OPTION_BY_KEY = {str(item["key"]): item for item in DISPLAY_OPTIONS}


class WizardAbort(RuntimeError):
    """Raised when the operator intentionally aborts the controlled wizard."""


def build_local_wizard_status(
    generated_at: str,
    rotation: dict[str, str | int],
    environment_id: str,
    network: dict[str, Any],
    contract_validation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "state": "candidate_ready",
        "flow": "setup_product_local_v0",
        "interface": {
            "mode": INTERFACE_MODE,
            "operator_input": "keyboard_only",
            "free_shell_available": False,
            "browser_required": False,
            "chromium_used": False,
            "desktop_used": False,
            "compositor_used": False,
        },
        "files": {
            "candidate_config": CANDIDATE_FILENAME,
            "summary": SUMMARY_FILENAME,
            "status": STATUS_FILENAME,
        },
        "network": {
            "network_step": network["network_step"],
            "connectivity": network["connectivity"],
            "connected": network["connected"],
            "connection_type": network["connection_type"],
            "read_only_check": network["read_only_check"],
            "internet_external_check": False,
        },
        "environment": {
            "mode": setup.SELECTION_MODE_MANUAL,
            "environment_id_present": bool(environment_id),
            "environment_id_valid": True,
            "environment_identifier_raw_written_to_status": False,
        },
        "validation": {
            "environment_id": "format_validated_only",
            "display": "candidate_only",
            "rotation_degrees": int(rotation["rotation_deg"]),
            "rotation_label_written_to_status": False,
            "backend_validation": "not_checked",
            "network_validation": network["connectivity"],
        },
        "contract_validation": contract_validation,
        "guardrails": {
            "writes_only_under_tmp": True,
            "candidate_generated": True,
            "real_config_read": False,
            "real_config_written": False,
            "writer_called": False,
            "writer_real_mode_called": False,
            "data_written": False,
            "opt_written": False,
            "network_external_access": False,
            "network_changed": False,
            "wifi_changed": False,
            "display_changed": False,
            "rotation_applied": False,
            "hotspot_created": False,
            "commands_executed": False,
            "systemctl_called": False,
            "service_changed": False,
            "player_started": False,
            "player_stopped": False,
            "mpv_called": False,
            "backend_called": False,
            "nmcli_called": False,
        },
        "privacy": {
            "candidate_payload_copied_to_status": False,
            "candidate_payload_copied_to_summary": False,
            "environment_identifier_raw_written_to_status": False,
            "environment_identifier_raw_written_to_summary": False,
            "credential_value_written_to_status": False,
            "credential_value_written_to_summary": False,
            "private_url_written_to_status": False,
            "private_url_written_to_summary": False,
            "wifi_network_name_written_to_status": False,
            "wifi_network_name_written_to_summary": False,
            "network_metadata_written_to_status": False,
            "network_metadata_written_to_summary": False,
        },
    }


def build_local_wizard_summary(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Dadooh C9.4 setup produto local V0",
            "",
            f"schema_version: {status['schema_version']}",
            f"generated_at_utc: {status['generated_at_utc']}",
            f"state: {status['state']}",
            f"flow: {status['flow']}",
            f"interface_mode: {status['interface']['mode']}",
            "operator_input: keyboard_only",
            "free_shell_available: false",
            "browser_required: false",
            "chromium_used: false",
            "desktop_used: false",
            "compositor_used: false",
            f"network_step: {status['network']['network_step']}",
            f"connectivity: {status['network']['connectivity']}",
            f"network_connected: {status['network']['connected']}",
            f"connection_type: {status['network']['connection_type']}",
            f"environment_id_present: {str(status['environment']['environment_id_present']).lower()}",
            f"environment_id_valid: {str(status['environment']['environment_id_valid']).lower()}",
            f"rotation_degrees: {status['validation']['rotation_degrees']}",
            "rotation_field: rotation_deg",
            "contract_validator: C5.1 allow-mock",
            f"contract_allow_mock_valid: {str(status['contract_validation']['allow_mock']['valid']).lower()}",
            "contract_real_dry_run_expected_failure: true",
            f"candidate_config: {CANDIDATE_FILENAME}",
            "summary: summary.txt",
            f"status: {STATUS_FILENAME}",
            "",
            "Guardrails:",
            "writes_only_under_tmp: true",
            "real_config_read: false",
            "real_config_written: false",
            "writer_called: false",
            "data_written: false",
            "opt_written: false",
            "commands_executed: false",
            "systemctl_called: false",
            "service_changed: false",
            "player_started: false",
            "player_stopped: false",
            "mpv_called: false",
            "nmcli_called: false",
            "network_changed: false",
            "wifi_changed: false",
            "display_changed: false",
            "rotation_applied: false",
            "hotspot_created: false",
            "",
            "Privacy:",
            "candidate_payload_copied_to_summary: false",
            "environment_identifier_raw_written_to_summary: false",
            "credential_value_written_to_summary: false",
            "private_url_written_to_summary: false",
            "wifi_network_name_written_to_summary: false",
            "network_metadata_written_to_summary: false",
        ]
    )


def output_text(out_dir: pathlib.Path) -> str:
    parts = []
    for name in (STATUS_FILENAME, SUMMARY_FILENAME):
        path = out_dir / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def forbidden_variants(value: str) -> tuple[str, str]:
    escaped = json.dumps(value, ensure_ascii=True)[1:-1]
    return (value, escaped)


def assert_sanitized_outputs(out_dir: pathlib.Path, environment_id: str) -> None:
    text = output_text(out_dir)
    forbidden_values = [
        environment_id,
        setup.SAFE_PLACEHOLDER_API_KEY,
        setup.SAFE_PLACEHOLDER_API_URL,
    ]
    for item in setup.MOCK_ENVIRONMENTS:
        forbidden_values.append(item["environment_id"])
        forbidden_values.append(item["name"])

    for value in forbidden_values:
        for variant in forbidden_variants(value):
            if variant and variant in text:
                raise setup.SetupError("privacy scan blocked raw setup value in status/summary")

    for marker in (
        "api_key",
        "api_url",
        "token",
        "secret",
        "password",
        "senha",
        "ssid",
        "mac",
        "dns",
        "hostname",
        "gateway",
        "raw_payload",
    ):
        if marker in text.lower():
            raise setup.SetupError("privacy scan blocked sensitive marker in status/summary")


def write_local_wizard_artifacts(
    out_dir: pathlib.Path,
    environment_id: str,
    rotation: dict[str, str | int],
    network: dict[str, Any],
) -> dict[str, Any]:
    setup.prepare_out_dir(out_dir)
    generated_at = setup.utc_timestamp()
    candidate = setup.build_candidate_config(
        environment_id,
        int(rotation["rotation_deg"]),
        setup.SELECTION_MODE_MANUAL,
    )
    candidate["setup_source"] = SETUP_SOURCE
    candidate["setup_interface"] = INTERFACE_MODE
    candidate["setup_network_step"] = network["network_step"]
    candidate["setup_connectivity"] = network["connectivity"]
    candidate["setup_display_source"] = "mock_candidate_only"

    contract_validation = setup.validate_candidate_handoff(candidate)
    status = build_local_wizard_status(generated_at, rotation, environment_id, network, contract_validation)

    setup.atomic_write_private_json(out_dir / CANDIDATE_FILENAME, candidate, out_dir)
    setup.atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    setup.atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_local_wizard_summary(status), out_dir)
    assert_sanitized_outputs(out_dir, environment_id)
    return status


def write_cancelled_artifact(out_dir: pathlib.Path) -> None:
    setup.prepare_out_dir(out_dir)
    status = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": setup.utc_timestamp(),
        "state": "setup_cancelled",
        "candidate_generated": False,
        "guardrails": {
            "writes_only_under_tmp": True,
            "real_config_read": False,
            "real_config_written": False,
            "writer_called": False,
            "network_changed": False,
            "wifi_changed": False,
            "display_changed": False,
            "player_started": False,
            "mpv_called": False,
            "nmcli_called": False,
        },
        "privacy": {
            "candidate_payload_copied": False,
            "environment_identifier_raw_written": False,
            "credential_value_written": False,
            "network_metadata_written": False,
        },
    }
    setup.atomic_write_private_json(out_dir / CANCELLED_FILENAME, status, out_dir)


def resolve_display_selection(rotation_key: str) -> dict[str, str | int]:
    option = DISPLAY_OPTION_BY_KEY.get(rotation_key)
    if option is None:
        raise setup.SetupError("unknown orientation option")
    return {
        "key": str(option["key"]),
        "label": str(option["label"]),
        "description": str(option["description"]),
        "rotation_deg": int(option["rotation_deg"]),
    }


def resolve_scripted_inputs(
    environment_id: str,
    rotation_key: str,
    network_step: str,
) -> tuple[str, dict[str, str | int], dict[str, Any]]:
    environment = setup.validate_environment_id(environment_id)
    rotation = resolve_display_selection(rotation_key)
    network = resolve_network_selection(network_step)
    return environment, rotation, network


def safe_interface_name(value: str) -> bool:
    return bool(value) and all(char.isalnum() or char in "_.:-" for char in value)


def classify_interface_type(interface_name: str) -> str:
    lowered = interface_name.lower()
    if lowered.startswith(("eth", "en")):
        return "ethernet"
    if lowered.startswith(("wl", "wlan")):
        return "wifi"
    return "unknown"


def read_default_route_interface() -> str | None:
    try:
        lines = pathlib.Path("/proc/net/route").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        interface_name, destination, _gateway, flags = parts[:4]
        if destination != "00000000" or not safe_interface_name(interface_name):
            continue
        try:
            route_flags = int(flags, 16)
        except ValueError:
            continue
        if route_flags & 0x2:
            return interface_name
    return None


def detect_current_connection() -> dict[str, Any]:
    interface_name = read_default_route_interface()
    if interface_name is None:
        return {
            "connected": "no",
            "connection_type": "unknown",
            "connectivity": "unknown",
            "read_only_check": True,
        }

    return {
        "connected": "yes",
        "connection_type": classify_interface_type(interface_name),
        "connectivity": "unknown",
        "read_only_check": True,
    }


def resolve_network_selection(network_key: str) -> dict[str, Any]:
    if network_key == "existing_connection":
        detected = detect_current_connection()
        return {
            "network_step": "existing_connection",
            "label": "Usar conexao atual",
            **detected,
        }
    if network_key == "mock":
        return {
            "network_step": "mock",
            "label": "Modo de bancada/mock",
            "connected": "unknown",
            "connection_type": "unknown",
            "connectivity": "not_checked",
            "read_only_check": False,
        }
    if network_key in {"skipped", "wifi_future"}:
        return {
            "network_step": "skipped",
            "label": "Configurar Wi-Fi - em breve",
            "connected": "unknown",
            "connection_type": "unknown",
            "connectivity": "not_checked",
            "read_only_check": False,
        }
    raise setup.SetupError("network_step must be existing_connection, mock or skipped")


def safe_addstr(stdscr: Any, row: int, col: int, text: str, attr: int = curses.A_NORMAL) -> None:
    height, width = stdscr.getmaxyx()
    if row < 0 or row >= height or col >= width:
        return
    safe = text[: max(0, width - col - 1)]
    try:
        stdscr.addstr(row, col, safe, attr)
    except curses.error:
        pass


def draw_product_screen(
    stdscr: Any,
    *,
    active_step: int,
    heading: str,
    body: list[str],
    options: list[dict[str, Any]] | None = None,
    selected_index: int = 0,
    footer: str = "Enter confirma | Esc cancela",
    input_value: str | None = None,
    error_message: str = "",
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()

    safe_addstr(stdscr, 0, 2, BRAND.upper(), curses.A_BOLD)
    safe_addstr(stdscr, 1, 2, TITLE, curses.A_BOLD)
    safe_addstr(stdscr, 3, 2, "  ".join(
        f"[{index + 1}. {step}]" if index == active_step else f"{index + 1}. {step}"
        for index, step in enumerate(STEPS)
    ))
    safe_addstr(stdscr, 4, 2, "-" * max(12, min(width - 4, 72)))
    safe_addstr(stdscr, 6, 2, heading, curses.A_BOLD)

    row = 8
    for line in body:
        if row >= height - 3:
            break
        safe_addstr(stdscr, row, 4, line)
        row += 1

    if input_value is not None and row < height - 3:
        row += 1
        safe_addstr(stdscr, row, 4, "Identificador:")
        safe_addstr(stdscr, row + 1, 4, input_value or "", curses.A_REVERSE if not input_value else curses.A_BOLD)
        row += 3

    if options:
        row += 1
        for index, option in enumerate(options):
            if row >= height - 3:
                break
            attr = curses.A_REVERSE if index == selected_index else curses.A_NORMAL
            marker = ">" if index == selected_index else " "
            safe_addstr(stdscr, row, 4, f"{marker} {option['label']}", attr)
            row += 1
            description = str(option.get("description", ""))
            if description and row < height - 3:
                safe_addstr(stdscr, row, 8, description)
                row += 1

    if error_message:
        safe_addstr(stdscr, max(0, height - 3), 2, error_message[: max(1, width - 4)], curses.A_BOLD)
    safe_addstr(stdscr, max(0, height - 2), 2, footer[: max(1, width - 4)])
    stdscr.refresh()


def choose_option(
    stdscr: Any,
    *,
    active_step: int,
    heading: str,
    body: list[str],
    options: list[dict[str, Any]],
    allow_back: bool = False,
) -> dict[str, Any] | None:
    selected = 0
    while True:
        footer = "Setas movem | Enter confirma | Esc cancela"
        if allow_back:
            footer = "Setas movem | Enter confirma | b volta | Esc cancela"
        draw_product_screen(
            stdscr,
            active_step=active_step,
            heading=heading,
            body=body,
            options=options,
            selected_index=selected,
            footer=footer,
        )
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord("k"), ord("K")):
            selected = (selected - 1) % len(options)
        elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
            selected = (selected + 1) % len(options)
        elif key in (curses.KEY_ENTER, 10, 13):
            return options[selected]
        elif allow_back and key in (ord("b"), ord("B")):
            return None
        elif key in (ord("q"), ord("Q"), 27):
            raise WizardAbort("setup local cancelado pelo operador")


def validate_environment_entry(raw_value: str) -> tuple[str, str]:
    try:
        return setup.validate_environment_id(raw_value), ""
    except setup.SetupError:
        return "", "Use 3 a 128 caracteres: letras, numeros, _, -, . ou :."


def read_environment_id(stdscr: Any) -> str | None:
    value = ""
    error_message = ""
    curses.curs_set(1)
    try:
        while True:
            draw_product_screen(
                stdscr,
                active_step=1,
                heading="Ambiente",
                body=[
                    "Digite o identificador fornecido pela Dadooh.",
                    "O valor sera usado apenas na candidata temporaria.",
                    "Ele nao aparece no resumo publico.",
                ],
                input_value=value,
                error_message=error_message,
                footer="Enter continua | F2 volta | Esc cancela",
            )
            key = stdscr.getch()
            if key in (curses.KEY_ENTER, 10, 13):
                environment_id, error_message = validate_environment_entry(value)
                if environment_id:
                    return environment_id
            elif key in (27,):
                raise WizardAbort("setup local cancelado pelo operador")
            elif key == curses.KEY_F2:
                return None
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                value = value[:-1]
                error_message = ""
            elif key == 21:
                value = ""
                error_message = ""
            elif 32 <= key <= 126 and len(value) < 128:
                value += chr(key)
                error_message = ""
    finally:
        try:
            curses.curs_set(0)
        except curses.error:
            pass


def review_and_confirm(
    stdscr: Any,
    environment_id: str,
    rotation: dict[str, str | int],
    network: dict[str, Any],
) -> bool:
    while True:
        draw_product_screen(
            stdscr,
            active_step=3,
            heading="Revisao",
            body=[
                f"Conexao: {network['label']}",
                f"Ambiente informado: {'sim' if environment_id else 'nao'}",
                f"Tela: {rotation['label']}",
                "",
                "Sera gerada uma candidata temporaria.",
                "Rede, Wi-Fi, player, MPV e configuracao real nao serao alterados.",
            ],
            footer="Enter conclui | b volta | Esc cancela",
        )
        key = stdscr.getch()
        if key in (curses.KEY_ENTER, 10, 13):
            return True
        if key in (ord("b"), ord("B")):
            return False
        if key in (ord("q"), ord("Q"), 27):
            raise WizardAbort("setup local cancelado pelo operador")


def show_result(stdscr: Any, out_dir: pathlib.Path, status: dict[str, Any]) -> None:
    draw_product_screen(
        stdscr,
        active_step=4,
        heading="Concluir",
        body=[
            "Candidata temporaria gerada.",
            f"Estado: {status['state']}",
            f"Arquivo: {CANDIDATE_FILENAME}",
            f"Status: {STATUS_FILENAME}",
            f"Resumo: {SUMMARY_FILENAME}",
            "",
            "C5.1 allow-mock passou.",
            "C5.1 real-dry-run falhou como esperado por mock.",
            "Nada foi escrito fora de /tmp.",
        ],
        footer="Enter sai",
    )
    while True:
        key = stdscr.getch()
        if key in (curses.KEY_ENTER, 10, 13, ord("q"), ord("Q"), 27):
            return


def run_curses_wizard(out_dir: pathlib.Path) -> dict[str, Any]:
    def inner(stdscr: Any) -> dict[str, Any]:
        curses.curs_set(0)
        stdscr.keypad(True)

        while True:
            selected_network = choose_option(
                stdscr,
                active_step=0,
                heading="Conexao",
                body=[
                    "Escolha como seguir agora.",
                    "Esta etapa nao muda nenhuma conexao.",
                ],
                options=[dict(item) for item in NETWORK_OPTIONS],
            )
            if selected_network is None:
                continue
            network = resolve_network_selection(str(selected_network["key"]))

            while True:
                environment_id = read_environment_id(stdscr)
                if environment_id is None:
                    break

                selected_rotation = choose_option(
                    stdscr,
                    active_step=2,
                    heading="Tela",
                    body=[
                        "Escolha a orientacao desejada.",
                        "A rotacao real nao sera aplicada nesta etapa.",
                    ],
                    options=[dict(item) for item in DISPLAY_OPTIONS],
                    allow_back=True,
                )
                if selected_rotation is None:
                    continue
                rotation = resolve_display_selection(str(selected_rotation["key"]))
                if review_and_confirm(stdscr, environment_id, rotation, network):
                    status = write_local_wizard_artifacts(out_dir, environment_id, rotation, network)
                    show_result(stdscr, out_dir, status)
                    return status

    return curses.wrapper(inner)


def file_mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_raises(func, message: str) -> None:
    try:
        func()
    except Exception:
        return
    raise AssertionError(message)


def assert_artifact_permissions(out_dir: pathlib.Path) -> None:
    assert_true(file_mode(out_dir) == setup.PRIVATE_DIR_MODE, "out-dir mode should be 0700")
    for name in (CANDIDATE_FILENAME, STATUS_FILENAME, SUMMARY_FILENAME):
        path = out_dir / name
        assert_true(path.exists(), f"{name} should exist")
        assert_true(file_mode(path) == setup.PRIVATE_FILE_MODE, f"{name} mode should be 0600")
        resolved = path.resolve(strict=True)
        assert_true(setup.path_is_under(resolved, setup.TMP_ROOT), f"{name} should stay under /tmp")
        assert_true(not setup.path_is_under(resolved, pathlib.Path("/data")), f"{name} wrote under /data")
        assert_true(not setup.path_is_under(resolved, pathlib.Path("/opt")), f"{name} wrote under /opt")


def run_self_test() -> None:
    assert_raises(
        lambda: setup.require_tmp_dir("/var/tmp/dadooh-c9-4-setup-product-v0"),
        "out-dir outside /tmp should fail",
    )
    assert_raises(
        lambda: resolve_scripted_inputs("bad environment", "portrait_left", "mock"),
        "invalid environment should fail",
    )
    assert_raises(
        lambda: resolve_scripted_inputs("ENV-PRODUTO-LOCAL-01", "diagonal", "mock"),
        "unknown rotation should fail",
    )
    assert_raises(
        lambda: resolve_scripted_inputs("https://example.invalid", "portrait_left", "mock"),
        "URL-like environment should fail",
    )
    assert_raises(
        lambda: resolve_scripted_inputs("api_key", "portrait_left", "mock"),
        "api_key-like environment should fail",
    )

    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c9-4-setup-product-v0-self-test-", dir="/tmp"))
    try:
        out_dir = setup.require_tmp_dir(str(root / "out"))
        environment_id, rotation, network = resolve_scripted_inputs(
            "ENV-PRODUTO-LOCAL-01",
            "portrait_left",
            "mock",
        )
        status = write_local_wizard_artifacts(out_dir, environment_id, rotation, network)
        assert_true(status["schema_version"] == SCHEMA_VERSION, "status schema should be C9.4")
        assert_true(status["state"] == "candidate_ready", "status should be candidate_ready")
        assert_true(status["interface"]["mode"] == INTERFACE_MODE, "status should record local interface")
        assert_true(status["interface"]["free_shell_available"] is False, "free shell should be false")
        assert_true(status["interface"]["chromium_used"] is False, "chromium should be false")
        assert_true(status["network"]["network_step"] == "mock", "network step should be mock")
        assert_true(status["network"]["connectivity"] == "not_checked", "mock connectivity should not be checked")
        assert_true(status["environment"]["environment_id_present"] is True, "environment should be present")
        assert_true(status["environment"]["environment_id_valid"] is True, "environment should be valid")
        assert_true(status["guardrails"]["commands_executed"] is False, "commands should be false")
        assert_true(status["guardrails"]["writer_called"] is False, "writer should be false")
        assert_true(status["guardrails"]["data_written"] is False, "data_written should be false")
        assert_true(status["guardrails"]["opt_written"] is False, "opt_written should be false")
        assert_true(status["guardrails"]["systemctl_called"] is False, "systemctl should be false")
        assert_true(status["guardrails"]["service_changed"] is False, "service_changed should be false")
        assert_true(status["guardrails"]["mpv_called"] is False, "mpv should be false")
        assert_true(status["guardrails"]["nmcli_called"] is False, "nmcli should be false")
        assert_true(status["guardrails"]["network_changed"] is False, "network should not change")
        assert_true(status["guardrails"]["display_changed"] is False, "display should not change")
        assert_true(status["guardrails"]["rotation_applied"] is False, "rotation should not be applied")

        assert_artifact_permissions(out_dir)
        with (out_dir / CANDIDATE_FILENAME).open("r", encoding="utf-8") as handle:
            candidate = json.load(handle)
        assert_true(candidate["environment_id"] == "ENV-PRODUTO-LOCAL-01", "candidate should keep selected environment")
        assert_true(candidate["rotation_deg"] == 270, "candidate should keep selected rotation")
        assert_true(candidate["setup_source"] == SETUP_SOURCE, "candidate should record C9.4 source")
        assert_true(candidate["setup_interface"] == INTERFACE_MODE, "candidate should record local interface")
        assert_true(candidate["setup_network_step"] == "mock", "candidate should record network step")
        assert_true(candidate["setup_connectivity"] == "not_checked", "candidate should record connectivity")
        assert_true("display_rotation_degrees" not in candidate, "candidate should not use legacy rotation field")

        allow_mock = setup.contract.validate_candidate_config(candidate, "allow-mock")
        real_dry_run = setup.contract.validate_candidate_config(candidate, "real-dry-run")
        assert_true(allow_mock["valid"], "C9.4 candidate should pass C5.1 allow-mock")
        assert_true(not real_dry_run["valid"], "C9.4 candidate should fail real-dry-run with mock values")
        assert_true(status["contract_validation"]["allow_mock"]["valid"], "status should record allow-mock pass")
        assert_true(
            status["contract_validation"]["real_dry_run_expected_failure"],
            "status should record expected real-dry-run failure",
        )

        text = output_text(out_dir)
        for forbidden in (
            "ENV-PRODUTO-LOCAL-01",
            "Ambiente Loja A - TESTE",
            setup.SAFE_PLACEHOLDER_API_KEY,
            setup.SAFE_PLACEHOLDER_API_URL,
            "api_key",
            "api_url",
            "token",
            "secret",
            "password",
            "ssid",
            "hostname",
            "gateway",
            "raw_payload",
        ):
            assert_true(forbidden.lower() not in text.lower(), f"status/summary leaked {forbidden}")

        second_out = setup.require_tmp_dir(str(root / "second-out"))
        second_environment, second_rotation, second_network = resolve_scripted_inputs(
            "ENV-PRODUTO-LOCAL-02",
            "landscape",
            "skipped",
        )
        second_status = write_local_wizard_artifacts(second_out, second_environment, second_rotation, second_network)
        assert_true(second_status["validation"]["rotation_degrees"] == 0, "landscape should map to 0")
        assert_true(second_status["network"]["network_step"] == "skipped", "wifi future should map to skipped")
        assert_artifact_permissions(second_out)

        cancel_out = setup.require_tmp_dir(str(root / "cancel-out"))
        write_cancelled_artifact(cancel_out)
        cancel_path = cancel_out / CANCELLED_FILENAME
        assert_true(cancel_path.exists(), "cancel marker should exist")
        assert_true(file_mode(cancel_path) == setup.PRIVATE_FILE_MODE, "cancel marker mode should be 0600")
        cancel_status = json.loads(cancel_path.read_text(encoding="utf-8"))
        assert_true(cancel_status["state"] == "setup_cancelled", "cancel marker should record cancellation")
        assert_true(cancel_status["candidate_generated"] is False, "cancel marker should not generate candidate")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the C9.4 controlled local setup wizard for HDMI + USB keyboard.",
        allow_abbrev=False,
    )
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--self-test", action="store_true", help="Run local C9.4 self-tests under /tmp and exit.")
    parser.add_argument("--scripted", action="store_true", help="Run without curses for automated smoke tests.")
    parser.add_argument(
        "--environment-id",
        help="Manual environment identifier for --scripted.",
    )
    parser.add_argument(
        "--rotation-key",
        choices=sorted(DISPLAY_OPTION_BY_KEY),
        help="Orientation key for --scripted.",
    )
    parser.add_argument(
        "--network-step",
        choices=("existing_connection", "mock", "skipped"),
        default="mock",
        help="Safe connection step for --scripted. Default: mock.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0

        out_dir = setup.require_tmp_dir(args.out_dir)
        if args.scripted:
            if not args.environment_id or not args.rotation_key:
                raise setup.SetupError("--scripted requires --environment-id and --rotation-key")
            environment_id, rotation, network = resolve_scripted_inputs(
                args.environment_id,
                args.rotation_key,
                args.network_step,
            )
            write_local_wizard_artifacts(out_dir, environment_id, rotation, network)
            print(f"C9.4 local setup artifacts generated under {out_dir}")
            print(CANDIDATE_FILENAME)
            print(STATUS_FILENAME)
            print(SUMMARY_FILENAME)
            return 0

        run_curses_wizard(out_dir)
        return 0
    except WizardAbort as exc:
        try:
            write_cancelled_artifact(setup.require_tmp_dir(args.out_dir))
        except Exception:
            pass
        print(f"aborted: {exc}", file=sys.stderr)
        return 130
    except setup.SetupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except AssertionError:
        print("error: self-test failed", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except curses.error as exc:
        print(f"error: terminal UI unavailable: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("error: setup local indisponivel no momento", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
