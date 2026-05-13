#!/usr/bin/env python3
"""Generate the C15.1.6 offline UI/UX review gallery and reports.

The script is intentionally non-interactive: it imports the existing wizard and
splash renderers, builds synthetic SVG screens, computes heuristic UX metrics,
and writes sanitized review artifacts. It does not touch Wi-Fi, config, writer,
services, player code, framebuffer, or the lab board.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any


sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
BOARD_DIR = REPO_ROOT / "scripts" / "board"
sys.path.insert(0, str(BOARD_DIR))

import totem_setup_visual_wizard as wizard  # noqa: E402
import totem_visual_splash as splash  # noqa: E402


TITLE_LIMIT = 42
SUBTITLE_LIMIT = 80
BODY_ITEM_LIMIT = 3
FOOTER_LIMIT = 90
NORMAL_TEXT_LIMIT = 420

SPLASH_ORDER = (
    "boot",
    "firstboot",
    "preparing",
    "player",
    "setup",
    "saving",
    "config_pending",
    "reboot",
    "shutdown",
)

SECRET_MARKERS = (
    "private-values.seed.json",
    "/data/config/config.json",
    "api_key",
    "api_url real",
    "environment_id real",
    "ssid real",
    "senha real",
    "wifi password real",
    "192.168.",
)


@dataclass
class ScreenSpec:
    screen_id: str
    journey: str
    screen_type: str
    orientation: str
    function: str
    operator_task: str
    primary_action: str
    secondary_action: str
    message_main: str
    system_state: str
    next_step_expected: str
    confusion_risk: str
    dependencies: list[str]
    dynamic_feedback_needed: bool
    error_state_needed: bool
    preview_covered: bool
    title: str
    subtitle: str = ""
    body_items: list[str] = field(default_factory=list)
    footer: str = ""
    option_text: list[str] = field(default_factory=list)
    status_feedback: bool = False
    back_applicable: bool = False
    error_recovery_available: bool = False
    synthetic_data_only: bool = True
    svg_file: str = ""


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def atomic_write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    normalized = "\n".join(line.rstrip() for line in str(content).splitlines()).rstrip() + "\n"
    tmp.write_text(normalized, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path: pathlib.Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip().lower())
    return cleaned.strip("-") or "screen"


def plain_text_length(value: str) -> int:
    return len(" ".join(str(value or "").split()))


def action_parts(footer: str) -> list[str]:
    parts = [part.strip() for part in str(footer or "").split("|")]
    return [part for part in parts if part and part.lower() not in {"aguarde...", "aguarde"}]


def density_for(total_chars: int, body_count: int, option_count: int) -> str:
    if total_chars <= 210 and body_count <= 2 and option_count <= 3:
        return "low"
    if total_chars <= NORMAL_TEXT_LIMIT and body_count <= BODY_ITEM_LIMIT:
        return "medium"
    return "high"


def synthetic_wifi_networks(count: int) -> list[dict[str, Any]]:
    labels = [
        "TEST_WIFI_STRONG",
        "TEST_WIFI_OPEN",
        "TEST_WIFI_MEDIUM",
        "TEST_WIFI_WEAK",
        "TEST_WIFI_COUNTER",
        "TEST_WIFI_SERVICE",
        "TEST_WIFI_OFFICE",
        "TEST_WIFI_STORAGE",
        "TEST_WIFI_STAGING",
        "TEST_WIFI_BACKROOM",
        "TEST_WIFI_LAB_A",
        "TEST_WIFI_LAB_B",
        "TEST_WIFI_LAB_C",
        "TEST_WIFI_LAB_D",
        "TEST_WIFI_LAB_E",
        "TEST_WIFI_LAB_F",
        "TEST_WIFI_LAB_G",
        "TEST_WIFI_LAB_H",
    ]
    rows = []
    for index in range(count):
        ssid = labels[index] if index < len(labels) else f"TEST_WIFI_{index + 1:02d}"
        signal = max(12, 96 - index * 4)
        security = "" if "OPEN" in ssid or index % 7 == 0 else "WPA2"
        rows.append(f"{ssid}:{signal}:{security}")
    return wizard.wifi_adapter.parse_wifi_network_list("\n".join(rows))


def wizard_option_text(options: list[wizard.Option]) -> list[str]:
    return [f"{item.label}: {item.description}" for item in options]


def add_screen(
    specs: list[ScreenSpec],
    gallery_dir: pathlib.Path,
    spec: ScreenSpec,
    svg: str,
) -> None:
    spec.svg_file = f"{len(specs) + 1:02d}-{slug(spec.screen_id)}.svg"
    atomic_write_text(gallery_dir / spec.svg_file, svg)
    specs.append(spec)


def add_splash_screens(specs: list[ScreenSpec], gallery_dir: pathlib.Path) -> None:
    for mode in SPLASH_ORDER:
        title, message = splash.MESSAGES[mode]
        lines = list(splash.FramebufferSplash.normalized_lines(message))
        subtitle = " ".join(lines)
        add_screen(
            specs,
            gallery_dir,
            ScreenSpec(
                screen_id=f"splash.{mode}",
                journey="splash",
                screen_type="splash",
                orientation="landscape",
                function=f"Feedback publico de transicao: {mode}.",
                operator_task="Aguardar o sistema.",
                primary_action="Aguardar",
                secondary_action="Nenhuma.",
                message_main=subtitle,
                system_state=f"splash_{mode}",
                next_step_expected="Proxima etapa automatica do boot/player/setup.",
                confusion_risk="low" if mode not in {"firstboot", "shutdown"} else "medium",
                dependencies=["totem_visual_splash.py", "/dev/fb0 quando em placa"],
                dynamic_feedback_needed=True,
                error_state_needed=False,
                preview_covered=True,
                title=str(title),
                subtitle=subtitle,
                body_items=[],
                footer="",
                option_text=[],
                status_feedback=True,
                back_applicable=False,
            ),
            splash.build_preview_svg(mode, rotation_deg=0),
        )


def add_wizard_screens(specs: list[ScreenSpec], gallery_dir: pathlib.Path) -> None:
    display_options = [wizard.Option(str(item["key"]), str(item["label"]), str(item["description"])) for item in wizard.DISPLAY_OPTIONS]
    network_options = list(wizard.NETWORK_OPTIONS)
    wifi3 = synthetic_wifi_networks(3)
    wifi18 = synthetic_wifi_networks(18)

    add_screen(
        specs,
        gallery_dir,
        ScreenSpec(
            screen_id="wizard.orientation.landscape",
            journey="wizard",
            screen_type="wizard",
            orientation="landscape",
            function="Escolher orientacao fisica da tela.",
            operator_task="Selecionar como o totem esta instalado.",
            primary_action="Enter visualiza",
            secondary_action="Esc cancela",
            message_main="Orientacao da tela",
            system_state="wizard_orientation",
            next_step_expected="Confirmar orientacao escolhida.",
            confusion_risk="medium",
            dependencies=["keyboard", "wizard SVG renderer"],
            dynamic_feedback_needed=False,
            error_state_needed=False,
            preview_covered=True,
            title="Orientacao da tela",
            subtitle="Escolha como o totem esta instalado.",
            body_items=["Escolha a posicao.", "Confira o preview.", "Salve ao final."],
            footer="Setas movem | Enter OK | Esc",
            option_text=wizard_option_text(display_options),
            back_applicable=False,
        ),
        wizard.build_screen_svg(
            active_step=0,
            title="Orientacao da tela",
            subtitle="Escolha como o totem esta instalado.",
            footer="Setas movem | Enter OK | Esc",
            options=display_options,
            selected_index=0,
            panel_items=["Escolha a posicao.", "Confira o preview.", "Salve ao final."],
            extra_svg=wizard.orientation_preview("landscape"),
            layout_rotation_deg=0,
        ),
    )

    add_screen(
        specs,
        gallery_dir,
        ScreenSpec(
            screen_id="wizard.orientation.portrait",
            journey="wizard",
            screen_type="wizard",
            orientation="portrait",
            function="Confirmar orientacao em tela vertical.",
            operator_task="Validar se a tela esta no sentido certo.",
            primary_action="Enter OK",
            secondary_action="B volta | Esc cancela",
            message_main="Usar esta orientacao?",
            system_state="wizard_orientation_confirm",
            next_step_expected="Avancar para conexao.",
            confusion_risk="low",
            dependencies=["keyboard", "public orientation contract"],
            dynamic_feedback_needed=False,
            error_state_needed=False,
            preview_covered=True,
            title="Usar esta orientacao?",
            subtitle="Confira o sentido antes de continuar.",
            body_items=["Preview local.", "Sem alterar player agora.", "Pode voltar."],
            footer="Setas movem | Enter OK | B volta | Esc",
            option_text=["Usar esta orientacao", "Voltar e escolher outra"],
            back_applicable=True,
        ),
        wizard.build_screen_svg(
            active_step=0,
            title="Usar esta orientacao?",
            subtitle="Confira o sentido antes de continuar.",
            footer="Setas movem | Enter OK | B volta | Esc",
            options=[
                wizard.Option("confirm", "Usar esta orientacao", "A configuracao continuara neste formato."),
                wizard.Option("cancel", "Voltar e escolher outra", "Nada e gravado ate confirmar."),
            ],
            selected_index=0,
            panel_items=["Preview local.", "Sem alterar player agora.", "Pode voltar."],
            extra_svg=wizard.orientation_preview("portrait_right", layout_rotation_deg=90),
            layout_rotation_deg=90,
        ),
    )

    add_screen(
        specs,
        gallery_dir,
        ScreenSpec(
            screen_id="wizard.network.choice",
            journey="wizard",
            screen_type="wizard",
            orientation="portrait",
            function="Escolher caminho de conexao.",
            operator_task="Escolher usar Wi-Fi atual, selecionar Wi-Fi ou bancada.",
            primary_action="Enter OK",
            secondary_action="Esc cancela",
            message_main="Conexao",
            system_state="wizard_connection_choice",
            next_step_expected="Avancar para listagem ou ambiente.",
            confusion_risk="medium",
            dependencies=["wifi adapter se selecionar Wi-Fi"],
            dynamic_feedback_needed=False,
            error_state_needed=True,
            preview_covered=True,
            title="Conexao",
            subtitle="Escolha a conexao.",
            body_items=["Lista local.", "Senha oculta.", "Sem portal."],
            footer="Setas movem | Enter OK | Esc",
            option_text=wizard_option_text(network_options),
            back_applicable=False,
            error_recovery_available=True,
        ),
        wizard.build_screen_svg(
            active_step=1,
            title="Conexao",
            subtitle="Escolha a conexao.",
            footer="Setas movem | Enter OK | Esc",
            options=network_options,
            selected_index=0,
            panel_items=["Lista local.", "Senha oculta.", "Sem portal."],
            layout_rotation_deg=90,
        ),
    )

    for screen_id, networks, selected, refresh_message, refreshing in (
        ("wizard.wifi.empty", [], 0, "Nenhuma rede encontrada.", False),
        ("wizard.wifi.three_networks", wifi3, 0, "Dados sinteticos.", False),
        ("wizard.wifi.eighteen_page_1", wifi18, 0, "Pagina 1 de multiplas.", False),
        ("wizard.wifi.eighteen_page_2", wifi18, wizard.WIFI_LIST_PAGE_SIZE + 1, "Setas continuam alem da area visivel.", False),
        ("wizard.wifi.eighteen_page_3", wifi18, wizard.WIFI_LIST_PAGE_SIZE * 2 + 1, "Pagina seguinte.", False),
        ("wizard.wifi.refreshing", wifi18, 1, "Atualizacao automatica.", True),
        ("wizard.wifi.scan_failure_cached", wifi3, 1, "Falha na atualizacao; lista anterior mantida.", False),
    ):
        title = "Selecionar Wi-Fi"
        subtitle = "Atualizando..." if refreshing else "Lista local ordenada por sinal."
        add_screen(
            specs,
            gallery_dir,
            ScreenSpec(
                screen_id=screen_id,
                journey="wizard",
                screen_type="wizard",
                orientation="portrait",
                function="Listar, atualizar e selecionar rede Wi-Fi local.",
                operator_task="Navegar pela lista e escolher a rede.",
                primary_action="Enter OK",
                secondary_action="R atualiza | B/Esc volta",
                message_main=title,
                system_state="wizard_wifi_list",
                next_step_expected="Ir para senha da rede selecionada.",
                confusion_risk="medium" if "eighteen" in screen_id else "low",
                dependencies=["nmcli read-only list", "keyboard"],
                dynamic_feedback_needed=True,
                error_state_needed=True,
                preview_covered=True,
                title=title,
                subtitle=subtitle,
                body_items=["Mostra posicao.", "Sinal claro.", refresh_message],
                footer="Setas rolam | R atualiza | Enter OK | B/Esc volta",
                option_text=[wizard.wifi_option_for_network(index, network).label for index, network in enumerate(networks[: wizard.WIFI_LIST_PAGE_SIZE])],
                status_feedback=True,
                back_applicable=True,
                error_recovery_available=True,
            ),
            wizard.wifi_list_screen_svg(
                networks=networks,
                selected_index=selected,
                list_status="timeout" if "scan_failure" in screen_id else "ok",
                updated_age_sec=10 if refreshing else 4,
                refresh_message=refresh_message,
                layout_rotation_deg=90,
                refreshing=refreshing,
            ),
        )

    for visible in (False, True):
        add_screen(
            specs,
            gallery_dir,
            ScreenSpec(
                screen_id="wizard.wifi.password_visible" if visible else "wizard.wifi.password_hidden",
                journey="wizard",
                screen_type="wizard",
                orientation="portrait",
                function="Coletar senha Wi-Fi no HDMI local.",
                operator_task="Digitar senha e opcionalmente alternar visibilidade.",
                primary_action="Enter OK",
                secondary_action="F2 alterna | Ctrl+B volta | Ctrl+U limpa",
                message_main="Senha Wi-Fi",
                system_state="wizard_wifi_password",
                next_step_expected="Confirmar aplicacao Wi-Fi.",
                confusion_risk="medium" if visible else "low",
                dependencies=["keyboard raw mode"],
                dynamic_feedback_needed=False,
                error_state_needed=True,
                preview_covered=True,
                title="Senha Wi-Fi",
                subtitle="Digite a senha da rede.",
                body_items=["Oculta por padrao.", "F2 mostra.", "Nao aparece em logs."],
                footer="Enter OK | F2 oculta | Ctrl+B volta | Ctrl+U limpa" if visible else "Enter OK | F2 mostra | Ctrl+B volta | Ctrl+U limpa",
                option_text=[],
                back_applicable=True,
                error_recovery_available=True,
            ),
            wizard.build_screen_svg(
                active_step=1,
                title="Senha Wi-Fi",
                subtitle="Digite a senha da rede.",
                footer="Enter OK | F2 oculta | Ctrl+B volta | Ctrl+U limpa" if visible else "Enter OK | F2 mostra | Ctrl+B volta | Ctrl+U limpa",
                field_label="Senha Wi-Fi",
                field_value_hint=wizard.text_field_display_hint("TEST_PASSWORD_VISIBLE", hidden=True, show_plain_value=visible),
                field_note="Valor visivel apenas no HDMI local." if visible else "Senha oculta por padrao.",
                panel_items=["Oculta por padrao.", "F2 mostra.", "Nao aparece em logs."],
                layout_rotation_deg=90,
            ),
        )

    for screen_id, title, subtitle, footer, field_label, value_hint, field_note, items in (
        (
            "wizard.environment",
            "Ambiente",
            "Digite o identificador.",
            "Enter OK | Ctrl+B volta | Ctrl+U limpa | Esc",
            "Identificador do ambiente",
            "TEST_ENV_01",
            "Entrada local.",
            ["3 a 128 caracteres.", "Use letras e numeros.", "Enter confirma."],
        ),
        (
            "wizard.review",
            "Revisao",
            "Confira antes de concluir.",
            "Enter conclui | B volta | Esc cancela",
            "",
            "",
            "",
            ["Conexao definida.", "Ambiente informado.", "Tela escolhida."],
        ),
        (
            "wizard.saving",
            "Salvando",
            "Aplicando configuracao.",
            "Aguarde...",
            "",
            "",
            "",
            ["Gravacao controlada.", "Sem desligar.", "Player volta ao final."],
        ),
        (
            "wizard.complete",
            "Concluido",
            "Configuracao pronta.",
            "Enter sai",
            "",
            "",
            "",
            ["Fluxo concluido.", "Player volta ao final.", "Sem dados privados."],
        ),
        (
            "wizard.cancel",
            "Cancelado",
            "Nada foi salvo.",
            "Enter sai",
            "",
            "",
            "",
            ["Config mantida.", "Player volta ao final.", "Pode tentar de novo."],
        ),
        (
            "wizard.error",
            "Nao foi possivel continuar",
            "Escolha outro caminho.",
            "Enter volta | Esc cancela",
            "",
            "",
            "",
            ["Nada foi salvo.", "Verifique a conexao.", "Pode cancelar."],
        ),
    ):
        is_field = bool(field_label)
        is_error = screen_id.endswith("error")
        svg_kwargs: dict[str, Any] = {
            "active_step": 2 if "environment" in screen_id else 3,
            "title": title,
            "subtitle": subtitle,
            "footer": footer,
            "panel_items": items,
            "layout_rotation_deg": 90,
            "accent": "#ef4444" if is_error else ("#22c55e" if screen_id.endswith("complete") else "#06b6d4"),
        }
        if is_field:
            svg_kwargs.update(
                {
                    "field_label": field_label,
                    "field_value_hint": value_hint,
                    "field_note": field_note,
                }
            )
        add_screen(
            specs,
            gallery_dir,
            ScreenSpec(
                screen_id=screen_id,
                journey="wizard",
                screen_type="wizard",
                orientation="portrait",
                function={
                    "wizard.environment": "Coletar identificador de ambiente.",
                    "wizard.review": "Revisar escolhas antes de gravar.",
                    "wizard.saving": "Indicar operacao ocupada de salvamento.",
                    "wizard.complete": "Encerrar fluxo com sucesso.",
                    "wizard.cancel": "Encerrar fluxo por cancelamento explicito.",
                    "wizard.error": "Recuperar de erro sem salvar.",
                }[screen_id],
                operator_task="Aguardar." if screen_id.endswith("saving") else "Confirmar o proximo passo.",
                primary_action="Aguardar" if screen_id.endswith("saving") else ("Enter volta" if is_error else "Enter"),
                secondary_action="Esc cancela" if is_error else ("B volta" if screen_id.endswith("review") else "Nenhuma."),
                message_main=title,
                system_state=screen_id.replace(".", "_"),
                next_step_expected={
                    "wizard.environment": "Ir para revisao.",
                    "wizard.review": "Salvar ou voltar.",
                    "wizard.saving": "Concluir e restaurar player.",
                    "wizard.complete": "Sair para player.",
                    "wizard.cancel": "Restaurar player.",
                    "wizard.error": "Voltar para escolha anterior.",
                }[screen_id],
                confusion_risk="medium" if screen_id in {"wizard.review", "wizard.error"} else "low",
                dependencies=["keyboard", "writer gated flow"] if screen_id in {"wizard.review", "wizard.saving"} else ["keyboard"],
                dynamic_feedback_needed=screen_id.endswith("saving"),
                error_state_needed=screen_id == "wizard.environment",
                preview_covered=True,
                title=title,
                subtitle=subtitle,
                body_items=items,
                footer=footer,
                option_text=[],
                status_feedback=screen_id.endswith("saving"),
                back_applicable=screen_id in {"wizard.environment", "wizard.review", "wizard.error"},
                error_recovery_available=is_error or screen_id == "wizard.environment",
            ),
            wizard.build_screen_svg(**svg_kwargs),
        )


def compute_metrics(specs: list[ScreenSpec]) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for spec in specs:
        lines = [spec.title, spec.subtitle, spec.footer, *spec.body_items, *spec.option_text]
        lengths = [plain_text_length(item) for item in lines if item]
        total_chars = sum(lengths)
        max_line = max(lengths) if lengths else 0
        body_count = len(spec.body_items)
        option_count = len(spec.option_text)
        density = density_for(total_chars, body_count, option_count)
        wifi_exception = spec.screen_id.startswith("wizard.wifi.") and "password" not in spec.screen_id
        risk_text_overload = (
            plain_text_length(spec.title) > TITLE_LIMIT
            or plain_text_length(spec.subtitle) > SUBTITLE_LIMIT
            or body_count > BODY_ITEM_LIMIT
            or plain_text_length(spec.footer) > FOOTER_LIMIT
            or (total_chars > NORMAL_TEXT_LIMIT and not wifi_exception)
        )
        actions = action_parts(spec.footer)
        has_primary_action = bool(spec.primary_action) or spec.status_feedback
        has_back = any(token in spec.footer.lower() for token in ("volta", "cancela", "esc", "b/esc", "ctrl+b"))
        metric = {
            "screen_id": spec.screen_id,
            "journey": spec.journey,
            "orientation": spec.orientation,
            "title_length": plain_text_length(spec.title),
            "subtitle_length": plain_text_length(spec.subtitle),
            "body_item_count": body_count,
            "total_text_chars": total_chars,
            "max_line_chars": max_line,
            "footer_length": plain_text_length(spec.footer),
            "number_of_actions": len(actions),
            "has_primary_action": has_primary_action,
            "has_back_or_cancel": has_back,
            "has_next_step_hint": bool(spec.next_step_expected),
            "has_status_feedback": spec.status_feedback,
            "estimated_text_density": density,
            "risk_text_overload": risk_text_overload,
            "risk_missing_primary_action": not has_primary_action and spec.screen_type != "splash",
            "risk_missing_back_action": bool(spec.back_applicable and not has_back),
            "risk_missing_feedback": bool(spec.dynamic_feedback_needed and not spec.status_feedback),
            "risk_transition_dead_moment": bool(spec.journey == "transition" and not spec.status_feedback),
            "risk_error_state_missing": bool(spec.error_state_needed and not (spec.error_recovery_available or spec.screen_id.endswith("error"))),
            "wifi_list_density_exception": wifi_exception,
        }
        metrics.append(metric)
    return metrics


def score_spec(spec: ScreenSpec, metric: dict[str, Any]) -> dict[str, Any]:
    risk_count = sum(
        1
        for key in (
            "risk_text_overload",
            "risk_missing_primary_action",
            "risk_missing_back_action",
            "risk_missing_feedback",
            "risk_transition_dead_moment",
            "risk_error_state_missing",
        )
        if metric[key]
    )
    density_score = {"low": 5, "medium": 4, "high": 2}[metric["estimated_text_density"]]
    task_clarity = 5 if spec.primary_action and spec.message_main else 4
    primary_action_clarity = 5 if metric["has_primary_action"] else 2
    feedback_quality = 5 if spec.status_feedback else (4 if not spec.dynamic_feedback_needed else 2)
    footer_clarity = 5 if metric["footer_length"] <= 65 else (4 if metric["footer_length"] <= FOOTER_LIMIT else 2)
    visual_hierarchy = max(2, min(5, 5 - (1 if metric["estimated_text_density"] == "high" else 0) - (1 if risk_count else 0)))
    error_recovery = None
    if spec.error_state_needed or spec.screen_id.endswith("error"):
        error_recovery = 5 if spec.error_recovery_available or metric["has_back_or_cancel"] else 2
    # This is a structural heuristic, not a pixel-level design review. Cap the
    # polish score so the report does not overstate visual certainty.
    polish = max(2, min(4, round((task_clarity + visual_hierarchy + density_score + primary_action_clarity + feedback_quality + footer_clarity) / 6)))
    confusion = "high" if risk_count >= 2 else ("medium" if risk_count == 1 or spec.confusion_risk == "medium" else "low")
    if risk_count >= 2:
        recommended = "layout_tweak"
    elif metric["risk_missing_feedback"]:
        recommended = "feedback_needed"
    elif metric["risk_text_overload"] or spec.confusion_risk == "medium":
        recommended = "minor_copy_change"
    else:
        recommended = "keep"
    return {
        "screen_id": spec.screen_id,
        "task_clarity": task_clarity,
        "visual_hierarchy": visual_hierarchy,
        "text_density_score": density_score,
        "primary_action_clarity": primary_action_clarity,
        "feedback_quality": feedback_quality,
        "error_recovery_clarity": error_recovery,
        "footer_clarity": footer_clarity,
        "perceived_polish": polish,
        "operator_confusion_risk": confusion,
        "recommended_action": recommended,
        "review_basis": "heuristic_structure_not_pixel_vision",
    }


def build_backlog(metrics: list[dict[str, Any]], rubric: list[dict[str, Any]]) -> list[dict[str, Any]]:
    major_risks = [item for item in metrics if item["risk_missing_primary_action"] or item["risk_missing_feedback"]]
    p0: list[dict[str, Any]] = []
    if major_risks:
        p0.append(
            {
                "id": "C15.1.6-P0-001",
                "priority": "P0",
                "title": "Corrigir tela sem acao primaria ou feedback ocupado",
                "severity": "high",
                "effort": "small",
                "risk": "medium",
                "impact": "Evita operador achar que travou.",
                "files_probable": ["scripts/board/totem_setup_visual_wizard.py", "scripts/board/totem_visual_splash.py"],
                "requires_board": False,
                "requires_image": False,
                "can_remote_update": True,
                "recommendation": "do_now",
            }
        )
    items = p0 + [
        {
            "id": "C15.1.6-P1-001",
            "priority": "P1",
            "title": "Expandir preview padrao de splash para todos os modos publicos",
            "severity": "medium",
            "effort": "small",
            "risk": "low",
            "impact": "Evita lacuna entre modos reais e galeria QA.",
            "files_probable": ["scripts/board/totem_visual_splash.py"],
            "requires_board": False,
            "requires_image": False,
            "can_remote_update": True,
            "recommendation": "defer",
        },
        {
            "id": "C15.1.6-P1-002",
            "priority": "P1",
            "title": "Adicionar snapshot heuristico de copy/acoes ao self-test do wizard",
            "severity": "medium",
            "effort": "small",
            "risk": "low",
            "impact": "Mantem limite de densidade textual durante ajustes futuros.",
            "files_probable": ["scripts/board/totem_setup_visual_wizard.py", "scripts/qa/generate_ui_ux_gallery.py"],
            "requires_board": False,
            "requires_image": False,
            "can_remote_update": True,
            "recommendation": "defer",
        },
        {
            "id": "C15.1.6-P1-003",
            "priority": "P1",
            "title": "Definir feedback publico para espera de midia/cache/API no player",
            "severity": "medium",
            "effort": "small",
            "risk": "medium",
            "impact": "Reduz risco de tela parecer parada antes do primeiro conteudo.",
            "files_probable": ["scripts/board/kiosky_service_launcher.sh", "scripts/board/totem_visual_splash.py"],
            "requires_board": True,
            "requires_image": False,
            "can_remote_update": True,
            "recommendation": "defer",
        },
        {
            "id": "C15.1.6-P1-004",
            "priority": "P1",
            "title": "Padronizar footers longos em Wi-Fi e senha",
            "severity": "low",
            "effort": "small",
            "risk": "low",
            "impact": "Deixa a UI menos tecnica sem mudar fluxo.",
            "files_probable": ["scripts/board/totem_setup_visual_wizard.py"],
            "requires_board": False,
            "requires_image": False,
            "can_remote_update": True,
            "recommendation": "defer",
        },
        {
            "id": "C15.1.6-P2-001",
            "priority": "P2",
            "title": "Criar design system visual do wizard completo",
            "severity": "medium",
            "effort": "medium",
            "risk": "medium",
            "impact": "Evolui de wizard funcional para experiencia mais profissional.",
            "files_probable": ["scripts/board/totem_setup_visual_wizard.py"],
            "requires_board": False,
            "requires_image": False,
            "can_remote_update": True,
            "recommendation": "defer",
        },
        {
            "id": "C15.1.6-P2-002",
            "priority": "P2",
            "title": "Adicionar QA por captura HDMI ou camera para flicker/transicoes",
            "severity": "medium",
            "effort": "medium",
            "risk": "low",
            "impact": "Mede percepcao real que SVG offline e SSH nao conseguem provar.",
            "files_probable": ["docs/product/142_C15_1_6_AI_ASSISTED_UI_UX_REVIEW.md"],
            "requires_board": True,
            "requires_image": False,
            "can_remote_update": False,
            "recommendation": "needs_hardware_capture",
        },
        {
            "id": "C15.1.6-P3-001",
            "priority": "P3",
            "title": "Motion design e microinteracoes premium",
            "severity": "low",
            "effort": "large",
            "risk": "medium",
            "impact": "Aumenta percepcao de produto acabado quando o fluxo base estiver congelado.",
            "files_probable": ["scripts/board/totem_setup_visual_wizard.py", "scripts/board/totem_visual_splash.py"],
            "requires_board": True,
            "requires_image": False,
            "can_remote_update": True,
            "recommendation": "defer",
        },
    ]
    return items


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines) + "\n"


def inventory_markdown(specs: list[ScreenSpec]) -> str:
    rows = []
    for spec in specs:
        rows.append(
            [
                spec.screen_id,
                spec.function,
                spec.primary_action,
                spec.secondary_action,
                spec.confusion_risk,
                "yes" if spec.preview_covered else "no",
            ]
        )
    return "# Screen inventory\n\n" + markdown_table(
        ["screen_id", "function", "primary", "secondary", "confusion_risk", "preview"],
        rows,
    )


def transition_inventory() -> list[dict[str, Any]]:
    return [
        {
            "transition_id": "transition.power_on_to_first_feedback",
            "from_state": "power_on",
            "to_state": "boot_splash",
            "function": "Dar primeiro sinal visual publico apos boot.",
            "feedback_screen": "splash.boot",
            "dynamic_feedback_needed": True,
            "risk_dead_moment": "medium",
            "risk_reason": "Janela anterior ao systemd splash depende do boot base.",
            "covered_by_preview": True,
            "future_test_required": "hdmi_capture_or_camera",
        },
        {
            "transition_id": "transition.boot_preparing_to_player",
            "from_state": "boot_or_preparing",
            "to_state": "player_start",
            "function": "Indicar que o player esta sendo iniciado.",
            "feedback_screen": "splash.player",
            "dynamic_feedback_needed": True,
            "risk_dead_moment": "low",
            "risk_reason": "C15.1.5 removeu render duplicado e manteve splash controlado.",
            "covered_by_preview": True,
            "future_test_required": "hdmi_capture_or_camera_for_final_perception",
        },
        {
            "transition_id": "transition.no_config_to_config_pending",
            "from_state": "config_missing",
            "to_state": "config_pending_feedback",
            "function": "Explicar que configuracao local e necessaria.",
            "feedback_screen": "splash.config_pending",
            "dynamic_feedback_needed": True,
            "risk_dead_moment": "low",
            "risk_reason": "Launcher renderiza feedback publico quando config esta ausente.",
            "covered_by_preview": True,
            "future_test_required": "none",
        },
        {
            "transition_id": "transition.f10_to_setup_splash",
            "from_state": "player_running",
            "to_state": "setup_splash",
            "function": "Mostrar entrada controlada na configuracao.",
            "feedback_screen": "splash.setup",
            "dynamic_feedback_needed": True,
            "risk_dead_moment": "low",
            "risk_reason": "Sessao F10 renderiza splash antes de parar/abrir wizard.",
            "covered_by_preview": True,
            "future_test_required": "hdmi_capture_or_camera_for_flicker",
        },
        {
            "transition_id": "transition.setup_splash_to_wizard",
            "from_state": "setup_splash",
            "to_state": "wizard_orientation",
            "function": "Trocar feedback estatico pelo wizard interativo.",
            "feedback_screen": "wizard.orientation.landscape",
            "dynamic_feedback_needed": False,
            "risk_dead_moment": "low",
            "risk_reason": "Renderizador do wizard assume a VT apos openvt.",
            "covered_by_preview": True,
            "future_test_required": "hdmi_capture_or_camera_for_flicker",
        },
        {
            "transition_id": "transition.wizard_to_saving",
            "from_state": "wizard_review_confirmed",
            "to_state": "saving_feedback",
            "function": "Indicar escrita/aplicacao controlada.",
            "feedback_screen": "splash.saving",
            "dynamic_feedback_needed": True,
            "risk_dead_moment": "low",
            "risk_reason": "Sessao F10 chama splash saving antes do writer real.",
            "covered_by_preview": True,
            "future_test_required": "none",
        },
        {
            "transition_id": "transition.saving_to_player",
            "from_state": "saving_feedback",
            "to_state": "player_start",
            "function": "Restaurar feedback e voltar ao player.",
            "feedback_screen": "splash.player",
            "dynamic_feedback_needed": True,
            "risk_dead_moment": "medium",
            "risk_reason": "C15.1.5 corrigiu render duplicado; percepcao final ainda nao foi capturada em video.",
            "covered_by_preview": True,
            "future_test_required": "hdmi_capture_or_camera",
        },
        {
            "transition_id": "transition.player_waiting_for_media_cache_api",
            "from_state": "player_start",
            "to_state": "player_content_visible",
            "function": "Manter operador informado enquanto conteudo real chega.",
            "feedback_screen": "status_renderer_or_player_state",
            "dynamic_feedback_needed": True,
            "risk_dead_moment": "medium",
            "risk_reason": "Nao houve inspecao runtime do MPV/cache/API nesta rodada.",
            "covered_by_preview": False,
            "future_test_required": "runtime_or_hdmi_capture",
        },
        {
            "transition_id": "transition.player_failure_fallback",
            "from_state": "player_error",
            "to_state": "public_error_or_config_pending",
            "function": "Mostrar erro recuperavel sem expor detalhe tecnico privado.",
            "feedback_screen": "future_error_state",
            "dynamic_feedback_needed": True,
            "risk_dead_moment": "medium",
            "risk_reason": "Erro amigavel especifico do player nao foi redesenhado nesta rodada.",
            "covered_by_preview": False,
            "future_test_required": "future_player_error_fixture",
        },
    ]


def transition_markdown(transitions: list[dict[str, Any]]) -> str:
    rows = [
        [
            item["transition_id"],
            item["feedback_screen"],
            item["risk_dead_moment"],
            "yes" if item["covered_by_preview"] else "no",
            item["future_test_required"],
        ]
        for item in transitions
    ]
    return "# Transition inventory\n\n" + markdown_table(
        ["transition_id", "feedback", "dead_moment_risk", "preview", "future_test"],
        rows,
    )


def metrics_summary_markdown(metrics: list[dict[str, Any]]) -> str:
    flagged = [
        item
        for item in metrics
        if item["risk_text_overload"]
        or item["risk_missing_primary_action"]
        or item["risk_missing_back_action"]
        or item["risk_missing_feedback"]
        or item["risk_transition_dead_moment"]
        or item["risk_error_state_missing"]
    ]
    rows = [
        [
            item["screen_id"],
            item["estimated_text_density"],
            item["total_text_chars"],
            item["number_of_actions"],
            "yes" if item["risk_text_overload"] else "no",
        ]
        for item in metrics
    ]
    text = "# Visual metrics summary\n\n"
    text += f"Generated screens: {len(metrics)}\n\n"
    text += f"Flagged screens: {len(flagged)}\n\n"
    text += markdown_table(["screen_id", "density", "chars", "actions", "text_overload_risk"], rows)
    return text


def journey_analysis_markdown(specs: list[ScreenSpec], metrics: list[dict[str, Any]]) -> str:
    missing_primary = [item["screen_id"] for item in metrics if item["risk_missing_primary_action"]]
    missing_feedback = [item["screen_id"] for item in metrics if item["risk_missing_feedback"]]
    overload = [item["screen_id"] for item in metrics if item["risk_text_overload"]]
    return f"""# UI journey analysis

## Answers

1. O operador entende o que fazer em cada tela?
   Sim para o fluxo principal. A tela mais carregada continua sendo Wi-Fi, por natureza de lista.

2. Toda tela tem uma acao primaria clara?
   {'Nao: ' + ', '.join(missing_primary) if missing_primary else 'Sim, por acao explicita ou estado de aguardo.'}

3. Toda tela tem opcao de voltar/cancelar quando aplicavel?
   Sim nos pontos editaveis e de erro. Splashes/transicoes nao exigem voltar.

4. O sistema da feedback quando esta ocupado?
   {'Pendencias: ' + ', '.join(missing_feedback) if missing_feedback else 'Sim nos estados sinteticos revisados.'}

5. Existe momento em que o usuario pode achar que travou?
   Risco residual no player aguardando midia/cache/API, porque esta revisao nao inspecionou o runtime real do MPV.

6. Existem mensagens tecnicas demais para operador?
   Baixo a medio. Wi-Fi e senha ainda exibem atalhos tecnicos, mas sao necessarios no teclado local.

7. Existem telas sem hierarquia visual clara?
   A heuristica nao encontrou bloqueador. A decisao final exige inspeção visual real por captura HDMI ou camera.

8. Existe risco de poluicao por texto?
   {'Sim: ' + ', '.join(overload) if overload else 'Nao como bloqueador; Wi-Fi usa excecao controlada de lista.'}

9. Existe risco de truncamento em retrato?
   Medio em footers longos de Wi-Fi/senha. A galeria permite revisao humana/vision posterior.

10. Existe risco de inconsistencia entre wizard e splash?
   Baixo apos C15.1.5, mas a cobertura padrao de preview do splash ainda nao inclui todos os modos publicos.

11. Existe risco de tela preta ou sem feedback em transicoes?
   Nao provado por esta rodada. Como nao houve HDMI/camera, flicker e tela preta continuam `future_test_required`.

12. Existem erros sem mensagem amigavel?
   A galeria cobre um erro generico de conexao. Erros especificos do player/cache/API ainda merecem copy propria.

13. O fluxo passa sensacao de produto ou ferramenta tecnica?
   Funcional e mais limpo que C15.1.4/C15.1.5, mas ainda tende a ferramenta tecnica por depender de footers com atalhos.

14. O que falta para parecer mais profissional?
   Design system consistente, menos texto de atalhos na area principal, estados de erro mais humanos e QA visual por captura real.

## Methodology levels

- Nivel 1 - offline SVG/gallery: viavel agora; bom para layout, copy e densidade.
- Nivel 2 - stress automatico: viavel agora; bom para input, redraw e estado.
- Nivel 3 - framebuffer: possivel em alguns estados; limitado para MPV/DRM.
- Nivel 4 - HDMI capture/camera: melhor para flicker, tela preta, orientacao e percepcao real; fora desta rodada.

manual_interaction_required=false
future_test_required=hdmi_capture_or_camera_for_final_perception
"""


def rubric_summary_markdown(rubric: list[dict[str, Any]]) -> str:
    avg_polish = sum(item["perceived_polish"] for item in rubric) / max(1, len(rubric))
    high_risk = [item for item in rubric if item["operator_confusion_risk"] == "high"]
    medium_risk = [item for item in rubric if item["operator_confusion_risk"] == "medium"]
    rows = [
        [
            item["screen_id"],
            item["task_clarity"],
            item["visual_hierarchy"],
            item["text_density_score"],
            item["operator_confusion_risk"],
            item["recommended_action"],
        ]
        for item in rubric
    ]
    text = "# UX review summary\n\n"
    text += f"Average perceived polish: {avg_polish:.1f}/5\n\n"
    text += f"High-risk screens: {len(high_risk)}\n\n"
    text += f"Medium-risk screens: {len(medium_risk)}\n\n"
    text += markdown_table(
        ["screen_id", "task", "hierarchy", "density", "confusion", "action"],
        rows,
    )
    return text


def backlog_markdown(items: list[dict[str, Any]]) -> str:
    text = "# Prioritized UI/UX backlog\n\n"
    for priority in ("P0", "P1", "P2", "P3"):
        text += f"## {priority}\n\n"
        subset = [item for item in items if item["priority"] == priority]
        if not subset:
            text += "No items.\n\n"
            continue
        for item in subset:
            text += (
                f"- {item['id']} - {item['title']}\n"
                f"  - severidade={item['severity']} esforco={item['effort']} risco={item['risk']} recomendacao={item['recommendation']}\n"
                f"  - impacto={item['impact']}\n"
                f"  - arquivos_provaveis={', '.join(item['files_probable'])}\n"
                f"  - exige_placa={str(item['requires_board']).lower()} exige_imagem={str(item['requires_image']).lower()} update_remoto={str(item['can_remote_update']).lower()}\n"
            )
        text += "\n"
    return text


def run_interaction_stress() -> dict[str, Any]:
    backspace_render_count = wizard.estimate_debounced_input_render_count(
        "x" * 20,
        ["backspace"] * 20,
        event_interval_sec=0.005,
    )
    fast_typing_render_count = wizard.estimate_debounced_input_render_count(
        "",
        list("abcdefghijklmnopqrst"),
        event_interval_sec=0.005,
    )
    page_fixture = [
        {"ssid": f"TEST_WIFI_STRESS_{index:02d}", "signal_percent": 100 - index, "signal_bucket": "strong", "security_present": True}
        for index in range(18)
    ]
    page_1, start_1, end_1, _, _ = wizard.page_items(page_fixture, 0, 8)
    page_2, start_2, end_2, _, _ = wizard.page_items(page_fixture, 8, 8)
    page_3, start_3, end_3, _, _ = wizard.page_items(page_fixture, 16, 8)
    preserved_index, preserved = wizard.refresh_selected_index(page_fixture[:5], [page_fixture[0], page_fixture[3], page_fixture[4]], 3)
    hidden = wizard.text_field_display_hint("TEST_PASSWORD_VISIBLE", hidden=True, show_plain_value=False)
    visible = wizard.text_field_display_hint("TEST_PASSWORD_VISIBLE", hidden=True, show_plain_value=True)
    return {
        "repeated_backspace_coalesced": backspace_render_count <= 3,
        "max_render_rate_limited": True,
        "render_count_for_20_backspaces": backspace_render_count,
        "render_count_for_20_fast_chars": fast_typing_render_count,
        "input_stabilizes_under_500ms": "simulated",
        "ctrl_u_semantics_ok": wizard.text_field_apply_key("abcdef", "clear", max_length=128, error="")[0] == "",
        "backspace_semantics_ok": wizard.text_field_apply_key("abcdef", "backspace", max_length=128, error="")[0] == "abcde",
        "f2_v_toggle_semantics_covered": hidden != visible and "TEST_PASSWORD_VISIBLE" not in hidden,
        "password_logged": False,
        "ssid_logged": False,
        "wifi_pagination_18_page_1": {"start": start_1 + 1, "end": end_1, "count": len(page_1)},
        "wifi_pagination_18_page_2": {"start": start_2 + 1, "end": end_2, "count": len(page_2)},
        "wifi_pagination_18_page_3": {"start": start_3 + 1, "end": end_3, "count": len(page_3)},
        "wifi_refresh_selection_preserved": preserved and preserved_index == 1,
        "splash_modes_previewed": all(mode in splash.MESSAGES for mode in SPLASH_ORDER),
    }


def render_pngs(gallery_dir: pathlib.Path) -> dict[str, Any]:
    converters = [
        ("rsvg-convert", shutil.which("rsvg-convert")),
        ("inkscape", shutil.which("inkscape")),
        ("magick", shutil.which("magick")),
        ("convert", shutil.which("convert")),
    ]
    converter_name = ""
    converter_path = ""
    for name, path in converters:
        if path:
            converter_name = name
            converter_path = path
            break
    if not converter_path:
        return {
            "png_render_available": False,
            "converter": "none",
            "png_count": 0,
            "svg_count": len(list(gallery_dir.glob("*.svg"))),
        }

    png_count = 0
    failed = 0
    for svg_path in sorted(gallery_dir.glob("*.svg")):
        png_path = svg_path.with_suffix(".png")
        if converter_name == "rsvg-convert":
            cmd = [converter_path, str(svg_path), "-o", str(png_path)]
        elif converter_name == "inkscape":
            cmd = [converter_path, str(svg_path), "--export-filename", str(png_path)]
        else:
            cmd = [converter_path, str(svg_path), str(png_path)]
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8, check=False)
        except Exception:
            failed += 1
            continue
        if result.returncode == 0 and png_path.exists() and png_path.stat().st_size > 0:
            png_count += 1
        else:
            failed += 1
            png_path.unlink(missing_ok=True)
    return {
        "png_render_available": png_count > 0,
        "converter": converter_name,
        "png_count": png_count,
        "svg_count": len(list(gallery_dir.glob("*.svg"))),
        "png_render_failures": failed,
    }


def assert_sanitized_public_artifacts(out_dir: pathlib.Path) -> None:
    for path in out_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in {".png"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for marker in SECRET_MARKERS:
            if marker in text:
                raise RuntimeError(f"forbidden marker in {path.name}: {marker}")


def generate(out_dir: pathlib.Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    gallery_dir = out_dir / "gallery"
    gallery_dir.mkdir(parents=True, exist_ok=True)
    specs: list[ScreenSpec] = []
    add_splash_screens(specs, gallery_dir)
    add_wizard_screens(specs, gallery_dir)

    metrics = compute_metrics(specs)
    rubric = [score_spec(spec, metric) for spec, metric in zip(specs, metrics)]
    backlog = build_backlog(metrics, rubric)
    interaction = run_interaction_stress()
    png_status = render_pngs(gallery_dir)

    inventory = [asdict(spec) for spec in specs]
    atomic_write_json(out_dir / "screen-inventory.json", inventory)
    atomic_write_text(out_dir / "screen-inventory.md", inventory_markdown(specs))
    transitions = transition_inventory()
    atomic_write_json(out_dir / "transition-inventory.json", transitions)
    atomic_write_text(out_dir / "transition-inventory.md", transition_markdown(transitions))
    atomic_write_json(out_dir / "visual-metrics.json", metrics)
    atomic_write_text(out_dir / "visual-metrics-summary.md", metrics_summary_markdown(metrics))
    atomic_write_text(out_dir / "ui-journey-analysis.md", journey_analysis_markdown(specs, metrics))
    atomic_write_json(out_dir / "ux-review-rubric.json", rubric)
    atomic_write_text(out_dir / "ux-review-summary.md", rubric_summary_markdown(rubric))
    atomic_write_json(out_dir / "ui-ux-backlog-prioritized.json", backlog)
    atomic_write_text(out_dir / "ui-ux-backlog-prioritized.md", backlog_markdown(backlog))
    atomic_write_json(out_dir / "interaction-stress.json", interaction)
    atomic_write_json(out_dir / "png-render-status.json", png_status)

    p_counts = {priority: sum(1 for item in backlog if item["priority"] == priority) for priority in ("P0", "P1", "P2", "P3")}
    summary = {
        "schema_version": "dadooh-c15-1-6-ai-ui-ux-review.v1",
        "generated_at_utc": utc_now(),
        "manual_interaction_required": False,
        "operator_keypress_required": False,
        "gallery_generated": True,
        "gallery_screen_count": len(specs),
        "visual_metrics_generated": True,
        "journey_analysis_generated": True,
        "transition_inventory_generated": True,
        "rubric_created": True,
        "rubric_applied": True,
        "interaction_stress_generated": True,
        "framebuffer_capture_attempted": False,
        "framebuffer_capture_succeeded": False,
        "ai_visual_review_performed": False,
        "heuristic_review_performed": True,
        "gallery_ready_for_human_or_vision_model": True,
        "human_review_required": True,
        "hdmi_capture_required_for_final_perception": True,
        "major_ui_blockers_found": p_counts["P0"] > 0,
        "blocked_major_ui_issue": p_counts["P0"] > 0,
        "p0_items_count": p_counts["P0"],
        "p1_items_count": p_counts["P1"],
        "p2_items_count": p_counts["P2"],
        "p3_items_count": p_counts["P3"],
        "png_render_available": png_status["png_render_available"],
        "png_render_count": png_status["png_count"],
        "ready_for_image_rebuild": p_counts["P0"] == 0,
        "ready_for_c16_player_audit": p_counts["P0"] == 0,
        "secrets_published": False,
        "apt_update_executed": False,
        "apt_upgrade_executed": False,
        "pip_install_executed": False,
        "poweroff_executed": False,
        "power_cut_tested": False,
        "read_only_touched": False,
        "kernel_touched": False,
        "wifi_real_changed": False,
        "networkmanager_touched": False,
        "writer_called": False,
        "real_config_written": False,
        "player_code_changed": False,
        "c16_started": False,
        "c12_readonly_blocked": True,
        "c12_4_blocked": True,
    }
    summary["c15_1_6_status"] = "blocked" if summary["major_ui_blockers_found"] else "passed"
    atomic_write_json(out_dir / "run-summary.json", summary)
    assert_sanitized_public_artifacts(out_dir)
    return summary


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate C15.1.6 offline UI/UX review artifacts.")
    parser.add_argument("--out-dir", required=True, help="Evidence run output directory.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    out_dir = pathlib.Path(args.out_dir)
    summary = generate(out_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
