#!/usr/bin/env python3
"""C9.1 controlled local setup wizard for HDMI + USB keyboard.

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


SCHEMA_VERSION = "dadooh-c9.1-local-setup-wizard.v1"
DEFAULT_OUT_DIR = "/tmp/dadooh-c9-1-local-wizard"

TITLE = "Dadooh setup local"
INTERFACE_MODE = "local_hdmi_keyboard_controlled"
SETUP_SOURCE = "c9.1-local-wizard-hdmi-keyboard-no-wifi"


class WizardAbort(RuntimeError):
    """Raised when the operator intentionally aborts the controlled wizard."""


def build_local_wizard_status(
    generated_at: str,
    rotation: dict[str, str | int],
    selection: dict[str, str],
    contract_validation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "state": "candidate_ready",
        "flow": "local_hdmi_keyboard_mock_local_no_wifi",
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
            "candidate_config": setup.CANDIDATE_FILENAME,
            "summary": setup.SUMMARY_FILENAME,
            "status": setup.STATUS_FILENAME,
        },
        "environment_selection": {
            "mode": selection["mode"],
            "catalog": "local_mock",
            "mock_environment_selected": selection["mode"] == setup.SELECTION_MODE_MOCK,
            "manual_environment_entry_available": False,
            "environment_identifier_raw_written_to_status": False,
            "environment_public_name_written_to_status": False,
        },
        "validation": {
            "environment_identifier": "format_validated_only",
            "orientation": "validated",
            "rotation_degrees": int(rotation["rotation_deg"]),
            "rotation_label_written_to_status": False,
            "backend_validation": "not_checked",
            "wifi_validation": "not_configured",
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
            "Dadooh C9.1 setup local na propria plaquinha",
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
            f"environment_selection_mode: {status['environment_selection']['mode']}",
            "environment_catalog: local_mock",
            "environment_identifier: format_validated_only",
            f"rotation_degrees: {status['validation']['rotation_degrees']}",
            "rotation_field: rotation_deg",
            "contract_validator: C5.1 allow-mock",
            f"contract_allow_mock_valid: {str(status['contract_validation']['allow_mock']['valid']).lower()}",
            "contract_real_dry_run_expected_failure: true",
            "candidate_config: candidate-config.json",
            "summary: summary.txt",
            "status: status.json",
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
    for name in (setup.STATUS_FILENAME, setup.SUMMARY_FILENAME):
        path = out_dir / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def forbidden_variants(value: str) -> tuple[str, str]:
    escaped = json.dumps(value, ensure_ascii=True)[1:-1]
    return (value, escaped)


def assert_sanitized_outputs(out_dir: pathlib.Path, selection: dict[str, str]) -> None:
    text = output_text(out_dir)
    forbidden_values = [
        selection["environment_id"],
        selection["public_name"],
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
        "hostname",
        "gateway",
        "raw_payload",
    ):
        if marker in text.lower():
            raise setup.SetupError("privacy scan blocked sensitive marker in status/summary")


def write_local_wizard_artifacts(
    out_dir: pathlib.Path,
    selection: dict[str, str],
    rotation: dict[str, str | int],
) -> dict[str, Any]:
    setup.prepare_out_dir(out_dir)
    generated_at = setup.utc_timestamp()
    candidate = setup.build_candidate_config(
        selection["environment_id"],
        int(rotation["rotation_deg"]),
        selection["mode"],
    )
    candidate["setup_source"] = SETUP_SOURCE
    candidate["setup_interface"] = INTERFACE_MODE

    contract_validation = setup.validate_candidate_handoff(candidate)
    status = build_local_wizard_status(generated_at, rotation, selection, contract_validation)

    setup.atomic_write_private_json(out_dir / setup.CANDIDATE_FILENAME, candidate, out_dir)
    setup.atomic_write_private_json(out_dir / setup.STATUS_FILENAME, status, out_dir)
    setup.atomic_write_private_text(out_dir / setup.SUMMARY_FILENAME, build_local_wizard_summary(status), out_dir)
    assert_sanitized_outputs(out_dir, selection)
    return status


def resolve_scripted_selection(environment_key: str, rotation_key: str) -> tuple[dict[str, str], dict[str, str | int]]:
    selection = setup.resolve_environment_selection(
        {
            "environment_mode": "mock",
            "environment_key": environment_key,
        }
    )
    rotation = setup.resolve_rotation_selection({"rotation_key": rotation_key})
    return selection, rotation


def draw_lines(stdscr: Any, lines: list[str], selected_index: int | None = None) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    max_y = max(0, height - 1)
    for row, line in enumerate(lines[:max_y]):
        attr = curses.A_NORMAL
        if selected_index is not None and row == selected_index:
            attr = curses.A_REVERSE
        safe = line[: max(1, width - 1)]
        try:
            stdscr.addstr(row, 0, safe, attr)
        except curses.error:
            pass
    stdscr.refresh()


def choose_option(
    stdscr: Any,
    *,
    title: str,
    subtitle: str,
    options: list[dict[str, Any]],
    render_option,
) -> dict[str, Any]:
    selected = 0
    while True:
        lines = [
            TITLE,
            "",
            title,
            subtitle,
            "",
        ]
        option_row_start = len(lines)
        for index, option in enumerate(options):
            prefix = ">" if index == selected else " "
            lines.append(f"{prefix} {render_option(option)}")
        lines.extend(
            [
                "",
                "Use setas ou j/k para mover. Enter confirma. q cancela.",
            ]
        )
        draw_lines(stdscr, lines, option_row_start + selected)
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord("k"), ord("K")):
            selected = (selected - 1) % len(options)
        elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
            selected = (selected + 1) % len(options)
        elif key in (curses.KEY_ENTER, 10, 13):
            return options[selected]
        elif key in (ord("q"), ord("Q"), 27):
            raise WizardAbort("setup local cancelado pelo operador")


def review_and_confirm(
    stdscr: Any,
    selection: dict[str, str],
    rotation: dict[str, str | int],
) -> bool:
    while True:
        lines = [
            TITLE,
            "",
            "Revisao",
            "",
            f"Ambiente: {selection['public_name']}",
            f"Orientacao: {rotation['label']}",
            "",
            "Esta etapa gera apenas uma candidata de teste em /tmp.",
            "Nenhuma configuracao real sera escrita.",
            "Nenhum servico, player, MPV, rede ou Wi-Fi sera alterado.",
            "",
            "Enter gera a candidata. b volta para orientacao. q cancela.",
        ]
        draw_lines(stdscr, lines)
        key = stdscr.getch()
        if key in (curses.KEY_ENTER, 10, 13):
            return True
        if key in (ord("b"), ord("B")):
            return False
        if key in (ord("q"), ord("Q"), 27):
            raise WizardAbort("setup local cancelado pelo operador")


def show_result(stdscr: Any, out_dir: pathlib.Path, status: dict[str, Any]) -> None:
    lines = [
        TITLE,
        "",
        "Candidata gerada",
        "",
        f"Estado: {status['state']}",
        f"Diretorio: {out_dir}",
        f"Arquivo: {setup.CANDIDATE_FILENAME}",
        f"Status: {setup.STATUS_FILENAME}",
        f"Resumo: {setup.SUMMARY_FILENAME}",
        "",
        "C5.1 allow-mock passou.",
        "C5.1 real-dry-run falhou como esperado por placeholders.",
        "",
        "Nada foi escrito fora de /tmp.",
        "Pressione Enter para sair.",
    ]
    draw_lines(stdscr, lines)
    while True:
        key = stdscr.getch()
        if key in (curses.KEY_ENTER, 10, 13, ord("q"), ord("Q"), 27):
            return


def run_curses_wizard(out_dir: pathlib.Path) -> dict[str, Any]:
    def inner(stdscr: Any) -> dict[str, Any]:
        curses.curs_set(0)
        stdscr.keypad(True)

        environment_options = [dict(item) for item in setup.MOCK_ENVIRONMENTS]
        rotation_options = [dict(item) for item in setup.ROTATION_OPTIONS]

        selected_environment = choose_option(
            stdscr,
            title="Selecionar ambiente mock/local",
            subtitle="Escolha um ambiente de teste local. Nenhum backend sera chamado.",
            options=environment_options,
            render_option=lambda item: f"{item['name']} - {item['description']}",
        )
        selection = setup.resolve_environment_selection(
            {"environment_mode": "mock", "environment_key": selected_environment["key"]}
        )

        while True:
            selected_rotation = choose_option(
                stdscr,
                title="Orientacao da tela",
                subtitle="Escolha como a midia devera aparecer no totem.",
                options=rotation_options,
                render_option=lambda item: f"{item['label']} ({item['rotation_deg']} graus)",
            )
            rotation = setup.resolve_rotation_selection({"rotation_key": selected_rotation["key"]})
            if review_and_confirm(stdscr, selection, rotation):
                break

        status = write_local_wizard_artifacts(out_dir, selection, rotation)
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
    for name in (setup.CANDIDATE_FILENAME, setup.STATUS_FILENAME, setup.SUMMARY_FILENAME):
        path = out_dir / name
        assert_true(path.exists(), f"{name} should exist")
        assert_true(file_mode(path) == setup.PRIVATE_FILE_MODE, f"{name} mode should be 0600")
        resolved = path.resolve(strict=True)
        assert_true(setup.path_is_under(resolved, setup.TMP_ROOT), f"{name} should stay under /tmp")
        assert_true(not setup.path_is_under(resolved, pathlib.Path("/data")), f"{name} wrote under /data")
        assert_true(not setup.path_is_under(resolved, pathlib.Path("/opt")), f"{name} wrote under /opt")


def run_self_test() -> None:
    assert_raises(
        lambda: setup.require_tmp_dir("/var/tmp/dadooh-c9-1-local-wizard"),
        "out-dir outside /tmp should fail",
    )
    assert_raises(
        lambda: resolve_scripted_selection("unknown", "portrait_left"),
        "unknown environment should fail",
    )
    assert_raises(
        lambda: resolve_scripted_selection("loja-a", "diagonal"),
        "unknown rotation should fail",
    )

    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c9-1-local-wizard-self-test-", dir="/tmp"))
    try:
        out_dir = setup.require_tmp_dir(str(root / "out"))
        selection, rotation = resolve_scripted_selection("loja-a", "portrait_left")
        status = write_local_wizard_artifacts(out_dir, selection, rotation)
        assert_true(status["schema_version"] == SCHEMA_VERSION, "status schema should be C9.1")
        assert_true(status["state"] == "candidate_ready", "status should be candidate_ready")
        assert_true(status["interface"]["mode"] == INTERFACE_MODE, "status should record local interface")
        assert_true(status["interface"]["free_shell_available"] is False, "free shell should be false")
        assert_true(status["interface"]["chromium_used"] is False, "chromium should be false")
        assert_true(status["guardrails"]["commands_executed"] is False, "commands should be false")
        assert_true(status["guardrails"]["writer_called"] is False, "writer should be false")
        assert_true(status["guardrails"]["data_written"] is False, "data_written should be false")
        assert_true(status["guardrails"]["opt_written"] is False, "opt_written should be false")
        assert_true(status["guardrails"]["systemctl_called"] is False, "systemctl should be false")
        assert_true(status["guardrails"]["service_changed"] is False, "service_changed should be false")
        assert_true(status["guardrails"]["mpv_called"] is False, "mpv should be false")
        assert_true(status["guardrails"]["nmcli_called"] is False, "nmcli should be false")

        assert_artifact_permissions(out_dir)
        with (out_dir / setup.CANDIDATE_FILENAME).open("r", encoding="utf-8") as handle:
            candidate = json.load(handle)
        assert_true(candidate["environment_id"] == "ENV-MOCK-LOJA-A", "candidate should keep selected environment")
        assert_true(candidate["rotation_deg"] == 270, "candidate should keep selected rotation")
        assert_true(candidate["setup_source"] == SETUP_SOURCE, "candidate should record C9.1 source")
        assert_true(candidate["setup_interface"] == INTERFACE_MODE, "candidate should record local interface")
        assert_true("display_rotation_degrees" not in candidate, "candidate should not use legacy rotation field")

        allow_mock = setup.contract.validate_candidate_config(candidate, "allow-mock")
        real_dry_run = setup.contract.validate_candidate_config(candidate, "real-dry-run")
        assert_true(allow_mock["valid"], "C9.1 candidate should pass C5.1 allow-mock")
        assert_true(not real_dry_run["valid"], "C9.1 candidate should fail real-dry-run with placeholders")
        assert_true(status["contract_validation"]["allow_mock"]["valid"], "status should record allow-mock pass")
        assert_true(
            status["contract_validation"]["real_dry_run_expected_failure"],
            "status should record expected real-dry-run failure",
        )

        text = output_text(out_dir)
        for forbidden in (
            "ENV-MOCK-LOJA-A",
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
        second_selection, second_rotation = resolve_scripted_selection("recepcao", "landscape")
        second_status = write_local_wizard_artifacts(second_out, second_selection, second_rotation)
        assert_true(second_status["validation"]["rotation_degrees"] == 0, "landscape should map to 0")
        assert_artifact_permissions(second_out)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the C9.1 controlled local setup wizard for HDMI + USB keyboard.",
        allow_abbrev=False,
    )
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--self-test", action="store_true", help="Run local C9.1 self-tests under /tmp and exit.")
    parser.add_argument("--scripted", action="store_true", help="Run without curses for automated smoke tests.")
    parser.add_argument(
        "--environment-key",
        choices=sorted(setup.MOCK_ENVIRONMENT_BY_KEY),
        help="Mock/local environment key for --scripted.",
    )
    parser.add_argument(
        "--rotation-key",
        choices=sorted(setup.ROTATION_OPTION_BY_KEY),
        help="Orientation key for --scripted.",
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
            if not args.environment_key or not args.rotation_key:
                raise setup.SetupError("--scripted requires --environment-key and --rotation-key")
            selection, rotation = resolve_scripted_selection(args.environment_key, args.rotation_key)
            write_local_wizard_artifacts(out_dir, selection, rotation)
            print(f"C9.1 local wizard artifacts generated under {out_dir}")
            print(setup.CANDIDATE_FILENAME)
            print(setup.STATUS_FILENAME)
            print(setup.SUMMARY_FILENAME)
            return 0

        run_curses_wizard(out_dir)
        return 0
    except WizardAbort as exc:
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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
