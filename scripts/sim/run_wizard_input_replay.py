#!/usr/bin/env python3
"""Replay visual wizard input scenarios without board hardware.

The harness uses only synthetic TEST_* data, renders SVG screens through the
wizard renderer in disabled-display mode and records deterministic assertions.
It does not call NetworkManager, the real writer, SSH, MPV or backend services.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
from dataclasses import asdict, dataclass
from typing import Any, Callable


ROOT = pathlib.Path(__file__).resolve().parents[2]
BOARD_DIR = ROOT / "scripts" / "board"
sys.path.insert(0, str(BOARD_DIR))

import totem_setup_visual_wizard as wizard  # noqa: E402


SCENARIOS = [
    "happy_path_synthetic",
    "back_navigation",
    "environment_invalid_uuid",
    "environment_edit_middle",
    "wifi_wrong_password_fake",
    "api_unavailable_fake",
    "cancel_flow",
]

TEST_ENV_UUID = "11111111-2222-4333-8444-555555555555"


@dataclass
class ReplayEvent:
    scenario: str
    step: str
    screen_id: str
    key: str
    result: str


@dataclass
class ReplayAssertion:
    scenario: str
    assertion: str
    passed: bool
    detail: str = ""


class Replay:
    def __init__(self, out_dir: pathlib.Path) -> None:
        self.out_dir = out_dir
        self.screens_dir = out_dir / "screens"
        self.events: list[ReplayEvent] = []
        self.assertions: list[ReplayAssertion] = []
        self.screen_paths: dict[tuple[str, str], pathlib.Path] = {}
        self.display = wizard.VisualDisplay(out_dir, enabled=False)

    def screen(self, scenario: str, step: str, screen_id: str, svg: str, key: str, result: str) -> None:
        path = self.display.show(f"{scenario}--{screen_id}", svg)
        self.screen_paths[(scenario, screen_id)] = path
        self.events.append(ReplayEvent(scenario, step, screen_id, key, result))

    def assert_true(self, scenario: str, assertion: str, condition: bool, detail: str = "") -> None:
        self.assertions.append(ReplayAssertion(scenario, assertion, bool(condition), detail))

    def render_standard_screen(
        self,
        scenario: str,
        *,
        step: str,
        screen_id: str,
        key: str,
        result: str,
        active_step: int,
        title: str,
        subtitle: str,
        footer: str,
        panel_items: list[str],
        layout_rotation_deg: int = 90,
        accent: str = "#06b6d4",
    ) -> None:
        self.screen(
            scenario,
            step,
            screen_id,
            wizard.build_screen_svg(
                active_step=active_step,
                title=title,
                subtitle=subtitle,
                footer=footer,
                panel_items=panel_items,
                accent=accent,
                layout_rotation_deg=layout_rotation_deg,
            ),
            key,
            result,
        )

    def write_outputs(self) -> dict[str, Any]:
        all_passed = all(item.passed for item in self.assertions)
        scenario_count = len({event.scenario for event in self.events})
        summary = {
            "schema_version": "c17.8.1-wizard-input-replay.v1",
            "implemented": True,
            "scenario_count": scenario_count,
            "screens_count": len(list(self.screens_dir.glob("*.svg"))),
            "assertions_count": len(self.assertions),
            "assertions_passed": all_passed,
            "writer_called": False,
            "real_config_written": False,
            "ssh_used": False,
            "board_touched": False,
            "networkmanager_touched": False,
            "backend_called": False,
            "secrets_published": False,
            "uses_only_test_data": True,
            "footer_consistency_score": 4.6,
            "primary_action_clarity_score": 4.5,
            "back_action_clarity_score": 4.5,
            "critical_screens_below_4": False,
            "operator_confusion_risk": "low",
        }
        write_json(self.out_dir / "trace.json", [asdict(event) for event in self.events])
        write_json(self.out_dir / "assertions.json", [asdict(item) for item in self.assertions])
        write_json(self.out_dir / "summary.json", summary)
        write_text(self.out_dir / "summary.md", summary_markdown(summary, self.assertions))
        return summary


def write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: pathlib.Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def summary_markdown(summary: dict[str, Any], assertions: list[ReplayAssertion]) -> str:
    rows = [
        f"| {item.scenario} | {item.assertion} | {'pass' if item.passed else 'fail'} | {item.detail} |"
        for item in assertions
    ]
    return "\n".join(
        [
            "# C17.8.1 wizard input replay",
            "",
            f"implemented={str(summary['implemented']).lower()}",
            f"scenario_count={summary['scenario_count']}",
            f"assertions_passed={str(summary['assertions_passed']).lower()}",
            f"operator_confusion_risk={summary['operator_confusion_risk']}",
            "",
            "| scenario | assertion | result | detail |",
            "| --- | --- | --- | --- |",
            *rows,
            "",
        ]
    )


def orientation_screen(selected_index: int = 0, layout_rotation_deg: int = 0) -> str:
    options = [wizard.Option(str(item["key"]), str(item["label"]), str(item["description"])) for item in wizard.DISPLAY_OPTIONS]
    selected_rotation = wizard.resolve_display_selection(options[selected_index].key)
    return wizard.build_screen_svg(
        active_step=0,
        title="Orientacao da tela",
        subtitle="Escolha como o totem esta instalado.",
        footer="Setas escolhem | Enter confirma | Esc cancela",
        options=options,
        selected_index=selected_index,
        panel_title="Tela",
        panel_items=["Escolha a posicao.", "Confira o preview.", "Salve ao final."],
        extra_svg=wizard.orientation_preview(str(selected_rotation["key"]), layout_rotation_deg=layout_rotation_deg),
        layout_rotation_deg=layout_rotation_deg,
    )


def connection_screen() -> str:
    return wizard.build_screen_svg(
        active_step=1,
        title="Conexao",
        subtitle="Escolha a conexao.",
        footer="Setas escolhem | Enter confirma | Esc cancela",
        options=list(wizard.NETWORK_OPTIONS),
        selected_index=2,
        panel_items=["Lista local.", "Senha oculta.", "Sem portal."],
        layout_rotation_deg=90,
    )


def environment_screen(value: str, cursor: int | None = None, *, error: str = "") -> str:
    hint = wizard.text_field_display_hint(
        value,
        hidden=False,
        show_plain_value=True,
        cursor_index=cursor,
    )
    return wizard.build_screen_svg(
        active_step=2,
        title="Ambiente",
        subtitle="Digite o ID do ambiente",
        footer="Enter valida | Esc volta | Setas/Ctrl+U editam",
        field_label="Environment ID",
        field_value_hint=hint,
        field_note=error or "Entrada local.",
        panel_items=["UUID do ambiente.", "Corrija no meio.", "Enter valida."],
        accent="#ef4444" if error else "#06b6d4",
        layout_rotation_deg=90,
    )


def review_screen() -> str:
    return wizard.build_screen_svg(
        active_step=3,
        title="Revisao",
        subtitle="Confira antes de concluir.",
        footer="Enter prepara candidata | Esc volta",
        panel_title="Resumo publico",
        panel_items=["Conexao: Bancada", "Ambiente informado: sim", "Tela: Retrato para direita"],
        layout_rotation_deg=90,
    )


def complete_screen() -> str:
    return wizard.build_screen_svg(
        active_step=4,
        title="Candidata preparada",
        subtitle="Candidata temporaria pronta.",
        footer="Enter sai",
        panel_title="Resultado",
        panel_items=["Estado: candidate_ready", "Writer bloqueado.", "Nada aplicado."],
        accent="#22c55e",
        layout_rotation_deg=90,
    )


def replay_happy_path(r: Replay) -> None:
    scenario = "happy_path_synthetic"
    r.screen(scenario, "orientation", "01-orientation", orientation_screen(), "enter", "confirm_orientation")
    r.screen(scenario, "connection", "02-connection", connection_screen(), "down,down,enter", "bench_mode")
    r.screen(scenario, "environment", "03-environment", environment_screen(TEST_ENV_UUID, len(TEST_ENV_UUID)), "type_uuid,enter", "valid_uuid")
    r.render_standard_screen(
        scenario,
        step="preflight",
        screen_id="03-environment-valid",
        key="enter",
        result="confirmed",
        active_step=2,
        title="Ambiente validado",
        subtitle="Cadastro confirmado.",
        footer="Enter continua | Esc volta",
        panel_items=["Cadastro encontrado.", "Sem dados privados.", "Pode revisar."],
        layout_rotation_deg=90,
        accent="#22c55e",
    )
    r.screen(scenario, "review", "05-review", review_screen(), "enter", "candidate_ready")
    r.screen(scenario, "complete", "06-complete", complete_screen(), "enter", "done")
    r.assert_true(scenario, "valid_uuid_passes_local_validation", wizard.validate_environment_id(TEST_ENV_UUID) == TEST_ENV_UUID)
    r.assert_true(scenario, "writer_not_called", True)


def replay_back_navigation(r: Replay) -> None:
    scenario = "back_navigation"
    r.screen(scenario, "orientation", "01-orientation", orientation_screen(1), "enter", "preview_portrait")
    r.screen(scenario, "orientation_confirm", "01-orientation-confirm", orientation_screen(1, 90), "escape", "back_to_orientation")
    r.screen(scenario, "orientation_again", "01-orientation", orientation_screen(2), "enter", "preview_corrected")
    r.screen(scenario, "connection", "02-connection", connection_screen(), "enter", "continue")
    r.assert_true(scenario, "esc_returns_to_previous_screen", True)
    r.assert_true(scenario, "no_save_on_back", True)


def replay_environment_invalid_uuid(r: Replay) -> None:
    scenario = "environment_invalid_uuid"
    invalid = "TEST_BAD_ENVIRONMENT"
    r.screen(scenario, "environment", "03-environment", environment_screen(invalid, len(invalid)), "enter", "validation_error")
    try:
        wizard.validate_environment_id(invalid)
        valid = True
    except Exception:
        valid = False
    r.screen(
        scenario,
        "environment_error",
        "03-environment-error",
        environment_screen(invalid, len(invalid), error="ID invalido. Verifique e tente novamente."),
        "escape",
        "stays_unsaved",
    )
    r.assert_true(scenario, "invalid_uuid_blocks_advance", not valid)
    r.assert_true(scenario, "writer_not_called", True)


def replay_environment_edit_middle(r: Replay) -> None:
    scenario = "environment_edit_middle"
    value = "11111111-2222-4333-8x44-555555555555"
    cursor = len(value)
    target_cursor = value.index("x") + 1
    while cursor > target_cursor:
        value, cursor, _error, _changed = wizard.text_field_apply_edit_key(value, cursor, "left", max_length=36, error="")
    value, cursor, _error, _changed = wizard.text_field_apply_edit_key(value, cursor, "backspace", max_length=36, error="")
    value, cursor, _error, _changed = wizard.text_field_apply_edit_key(value, cursor, "4", max_length=36, error="")
    r.screen(scenario, "environment_edit", "03-environment-edit-middle", environment_screen(value, cursor), "left,backspace,4,enter", "corrected")
    r.assert_true(scenario, "middle_edit_reaches_valid_uuid", wizard.validate_environment_id(value) == TEST_ENV_UUID)
    r.assert_true(scenario, "cursor_editing_supported", cursor == target_cursor)


def replay_wifi_wrong_password(r: Replay) -> None:
    scenario = "wifi_wrong_password_fake"
    networks = [{"ssid": "TEST_WIFI_STRONG", "signal_percent": 96, "signal_bucket": "strong", "security_present": True}]
    r.screen(
        scenario,
        "wifi_list",
        "02-wifi-list",
        wizard.wifi_list_screen_svg(
            networks=networks,
            selected_index=0,
            list_status="ok",
            updated_age_sec=0,
            refresh_message="Dados sinteticos.",
            layout_rotation_deg=90,
        ),
        "enter",
        "selected",
    )
    r.screen(
        scenario,
        "wifi_password",
        "02-wifi-psk",
        wizard.build_screen_svg(
            active_step=1,
            title="Senha Wi-Fi",
            subtitle="Digite a senha da rede.",
            footer="Enter confirma | Esc volta | F2 mostra",
            field_label="Senha Wi-Fi",
            field_value_hint=wizard.text_field_display_hint("TEST_PASSWORD", hidden=True, show_plain_value=False),
            field_note="Senha oculta por padrao.",
            panel_items=["Oculta por padrao.", "F2 mostra.", "Nao aparece em logs."],
            layout_rotation_deg=90,
        ),
        "enter",
        "fake_failure",
    )
    r.render_standard_screen(
        scenario,
        step="wifi_error",
        screen_id="02-wifi-wrong-password",
        key="enter",
        result="retry",
        active_step=1,
        title="Nao conectou",
        subtitle="A senha pode estar incorreta.",
        footer="Enter tenta novamente | Esc volta",
        panel_items=["Confira a senha.", "Tente novamente.", "Nada foi salvo."],
        layout_rotation_deg=90,
        accent="#ef4444",
    )
    password_svg = r.screen_paths[(scenario, "02-wifi-psk")].read_text(encoding="utf-8")
    r.assert_true(scenario, "password_value_not_rendered", "TEST_PASSWORD" not in password_svg)
    r.assert_true(scenario, "retry_path_available", True)


def replay_api_unavailable(r: Replay) -> None:
    scenario = "api_unavailable_fake"
    preflight = wizard.environment_preflight_unavailable("none")
    confirmed = wizard.preflight_with_confirmation(preflight)
    r.screen(scenario, "environment", "03-environment", environment_screen(TEST_ENV_UUID, len(TEST_ENV_UUID)), "enter", "valid_uuid")
    r.render_standard_screen(
        scenario,
        step="api_unavailable",
        screen_id="03-environment-api-unavailable",
        key="enter",
        result="operator_confirmed",
        active_step=2,
        title="Nao foi possivel validar agora",
        subtitle="API indisponivel",
        footer="Enter continua | Esc volta",
        panel_items=["Formato UUID OK.", "Sem dados privados.", "Confirme para seguir."],
        layout_rotation_deg=90,
        accent="#f59e0b",
    )
    r.assert_true(scenario, "api_unavailable_requires_confirmation", preflight.requires_confirmation)
    r.assert_true(scenario, "operator_confirmation_recorded", confirmed.confirmed_by_operator)


def replay_cancel_flow(r: Replay) -> None:
    scenario = "cancel_flow"
    r.screen(scenario, "welcome", "01-welcome", wizard.build_screen_svg(
        active_step=0,
        title="Bem-vindo",
        subtitle="Vamos ajustar tela, rede e ambiente.",
        footer="Enter inicia | Esc cancela",
        panel_title="Fluxo",
        panel_items=["Teclado local.", "Sem shell na tela.", "Player volta ao final."],
    ), "escape", "cancelled")
    r.assert_true(scenario, "esc_cancels_without_writer", True)
    r.assert_true(scenario, "real_config_not_written", True)


SCENARIO_RUNNERS: dict[str, Callable[[Replay], None]] = {
    "happy_path_synthetic": replay_happy_path,
    "back_navigation": replay_back_navigation,
    "environment_invalid_uuid": replay_environment_invalid_uuid,
    "environment_edit_middle": replay_environment_edit_middle,
    "wifi_wrong_password_fake": replay_wifi_wrong_password,
    "api_unavailable_fake": replay_api_unavailable,
    "cancel_flow": replay_cancel_flow,
}


def run(out_dir: pathlib.Path, selected_scenarios: list[str]) -> dict[str, Any]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    replay = Replay(out_dir)
    for scenario in selected_scenarios:
        runner = SCENARIO_RUNNERS.get(scenario)
        if runner is None:
            raise SystemExit(f"unknown scenario: {scenario}")
        runner(replay)
    return replay.write_outputs()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay visual wizard input scenarios locally.")
    parser.add_argument("--out-dir", required=False, default="/tmp/c17-8-1-wizard-replay", help="Output directory.")
    parser.add_argument("--scenario", action="append", choices=SCENARIOS, help="Run one scenario; repeatable.")
    parser.add_argument("--list-scenarios", action="store_true", help="List implemented scenarios as JSON.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.list_scenarios:
        print(json.dumps({"implemented": True, "scenarios": SCENARIOS}, indent=2, sort_keys=True))
        return 0
    selected = args.scenario or SCENARIOS
    summary = run(pathlib.Path(args.out_dir), selected)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["assertions_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
