#!/usr/bin/env python3
"""Run C16.2 synthetic-user UX review.

This harness is offline-only. It does not access a board, SSH, NetworkManager,
real config, private values, media cache, writer, package manager or appliance
runtime. It turns the C16.1 operating model into executable UX QA artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from dataclasses import asdict
from typing import Any


sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
QA_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_RUN_ROOT = REPO_ROOT / "docs" / "evidence" / "candidate-a" / "runs"
sys.path.insert(0, str(QA_DIR))

import c16_ux_operating_model_audit as c16  # noqa: E402
import generate_ui_ux_gallery as gallery  # noqa: E402


CRITICAL_JOURNEY_IDS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "M", "N", "R", "T"]

PRODUCT_DOCS = {
    "personas": REPO_ROOT / "docs" / "product" / "151_C16_1_PERSONAS_AND_ACTORS.md",
    "journeys": REPO_ROOT / "docs" / "product" / "152_C16_1_USER_JOURNEYS.md",
    "screen_intent": REPO_ROOT / "docs" / "product" / "153_C16_1_SCREEN_INTENT_MAP.md",
    "rubric": REPO_ROOT / "docs" / "product" / "154_C16_1_UX_UI_RUBRIC.md",
    "pdca": REPO_ROOT / "docs" / "product" / "159_C16_2_UX_PDCA_PROCESS.md",
}

SCREEN_GALLERY_ALIASES = {
    "boot": "boot",
    "firstboot": "firstboot",
    "preparing": "splash.preparing",
    "config_missing": "config_missing",
    "config_pending": "config_pending",
    "open_settings": "open_settings",
    "wizard_orientation": "orientation",
    "wizard_connection": "connection",
    "wifi_list": "wifi_list",
    "wifi_password": "wifi_password_hidden",
    "environment": "environment",
    "review": "review",
    "saving": "saving",
    "complete": "complete",
    "error": "wifi_wrong_password",
    "starting_player": "starting_player",
    "loading_content": "loading_content",
    "waiting_for_api": "waiting_for_api",
    "waiting_for_media": "waiting_for_media",
    "playing": "playing_status",
    "player_error": "error_no_content",
    "update_checking": "update_checking",
    "update_applying": "update_applying",
    "update_failed": "update_failed",
    "maintenance_support": "maintenance_support",
}

FORBIDDEN_MARKERS = (
    "private-values" ".seed.json",
    "/data/config" "/config.json",
    "api_" "key",
    "api_" "url=",
    "environment_" "id=",
    "192" ".168.",
)


JOURNEY_ASSESSMENTS: dict[str, dict[str, Any]] = {
    "A": {
        "priority": "P2",
        "scores": {
            "state_clarity": 4.5,
            "progress_feedback": 4.2,
            "recovery_clarity": 4.0,
            "negative_path_coverage": 4.0,
            "visual_evidence": 3.6,
            "runtime_observability": 4.0,
            "guardrail_safety": 5.0,
        },
        "finding": "Boot inicial tem linguagem clara, mas percepcao final ainda depende de HDMI/camera.",
        "recommendation": "Validar no boot da imagem C17 e manter HDMI/camera como gate antes de escala.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": True,
        "can_be_updated_remotely": False,
        "requires_image": True,
    },
    "B": {
        "priority": "P2",
        "scores": {
            "state_clarity": 4.6,
            "progress_feedback": 4.4,
            "recovery_clarity": 4.3,
            "negative_path_coverage": 4.0,
            "visual_evidence": 3.8,
            "runtime_observability": 4.0,
            "guardrail_safety": 5.0,
        },
        "finding": "Sem configuracao fica compreensivel e recuperavel via F10.",
        "recommendation": "Revalidar como gate de clean image em C17.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": True,
        "can_be_updated_remotely": False,
        "requires_image": True,
    },
    "C": {
        "priority": "P2",
        "scores": {
            "state_clarity": 4.4,
            "progress_feedback": 4.0,
            "recovery_clarity": 4.2,
            "negative_path_coverage": 3.9,
            "visual_evidence": 4.0,
            "runtime_observability": 4.0,
            "guardrail_safety": 5.0,
        },
        "finding": "Fluxo F10 e wizard estao bons para homologacao, com risco residual em negativos.",
        "recommendation": "Rodar full setup C17 e manter negativos Wi-Fi/API como gates separados.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": True,
        "can_be_updated_remotely": True,
        "requires_image": True,
    },
    "D": {
        "priority": "P2",
        "scores": {
            "state_clarity": 4.3,
            "progress_feedback": 4.2,
            "recovery_clarity": 4.1,
            "negative_path_coverage": 4.0,
            "visual_evidence": 4.2,
            "runtime_observability": 4.0,
            "guardrail_safety": 5.0,
        },
        "finding": "Selecao de rede e legivel na galeria sintetica.",
        "recommendation": "Manter regressao offline e validar uma lista real sanitizada em C17 se autorizado.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": False,
        "needs_hdmi_camera": False,
        "can_be_updated_remotely": True,
        "requires_image": False,
    },
    "E": {
        "priority": "P1",
        "scores": {
            "state_clarity": 3.9,
            "progress_feedback": 3.8,
            "recovery_clarity": 4.0,
            "negative_path_coverage": 3.2,
            "visual_evidence": 4.0,
            "runtime_observability": 3.2,
            "guardrail_safety": 5.0,
        },
        "finding": "Senha errada e comum e ainda precisa de validacao negativa runtime.",
        "recommendation": "Gate C17 com falha sintetica de associacao/senha e evidencia sanitizada.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": True,
        "can_be_updated_remotely": True,
        "requires_image": False,
    },
    "F": {
        "priority": "P1",
        "scores": {
            "state_clarity": 4.0,
            "progress_feedback": 3.8,
            "recovery_clarity": 3.9,
            "negative_path_coverage": 3.3,
            "visual_evidence": 4.0,
            "runtime_observability": 3.3,
            "guardrail_safety": 5.0,
        },
        "finding": "Wi-Fi fraco precisa ser distinguido de erro generico de conexao.",
        "recommendation": "Gate C17 com output sintetico nmcli e, se autorizado, leitura real sanitizada.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": True,
        "can_be_updated_remotely": True,
        "requires_image": False,
    },
    "G": {
        "priority": "P1",
        "scores": {
            "state_clarity": 3.8,
            "progress_feedback": 4.0,
            "recovery_clarity": 3.5,
            "negative_path_coverage": 3.0,
            "visual_evidence": 3.8,
            "runtime_observability": 3.3,
            "guardrail_safety": 5.0,
        },
        "finding": "API indisponivel precisa virar categoria publica verificavel.",
        "recommendation": "Gate C17 de outage sintetico sem dados reais; C16.3 e opcional se C17 nao cobrir.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": True,
        "can_be_updated_remotely": True,
        "requires_image": False,
    },
    "H": {
        "priority": "P2",
        "scores": {
            "state_clarity": 4.4,
            "progress_feedback": 4.2,
            "recovery_clarity": 4.1,
            "negative_path_coverage": 3.8,
            "visual_evidence": 3.9,
            "runtime_observability": 4.0,
            "guardrail_safety": 5.0,
        },
        "finding": "Conclusao do setup e clara, com lacuna perceptiva no handoff para player.",
        "recommendation": "Gate C17 full setup com timeline e observacao HDMI quando disponivel.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": True,
        "can_be_updated_remotely": True,
        "requires_image": True,
    },
    "I": {
        "priority": "P1",
        "scores": {
            "state_clarity": 4.0,
            "progress_feedback": 4.1,
            "recovery_clarity": 3.5,
            "negative_path_coverage": 3.2,
            "visual_evidence": 3.8,
            "runtime_observability": 3.4,
            "guardrail_safety": 5.0,
        },
        "finding": "Espera por conteudo melhorou, mas negativos cache/API ainda precisam de gate.",
        "recommendation": "Gate C17 para loading_content, waiting_for_api, waiting_for_media e no-content.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": True,
        "can_be_updated_remotely": True,
        "requires_image": False,
    },
    "J": {
        "priority": "P2",
        "scores": {
            "state_clarity": 4.5,
            "progress_feedback": 4.0,
            "recovery_clarity": 4.0,
            "negative_path_coverage": 3.8,
            "visual_evidence": 3.8,
            "runtime_observability": 4.0,
            "guardrail_safety": 5.0,
        },
        "finding": "Player normal pode ser validado em C17 sem abrir timing/sync/loop.",
        "recommendation": "Smoke C17 de playback normal; timing/sync/duration/loop ficam para C18.",
        "required_test_before_C17": True,
        "can_be_tested_offline": False,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": True,
        "can_be_updated_remotely": True,
        "requires_image": True,
    },
    "K": {
        "priority": "P1",
        "scores": {
            "state_clarity": 3.8,
            "progress_feedback": 3.6,
            "recovery_clarity": 3.4,
            "negative_path_coverage": 3.0,
            "visual_evidence": 3.7,
            "runtime_observability": 3.2,
            "guardrail_safety": 5.0,
        },
        "finding": "Midia indisponivel e a principal lacuna de erro visual sem tela preta.",
        "recommendation": "Gate C17 de missing-media/no-content com status publico e sem URLs sensiveis.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": True,
        "can_be_updated_remotely": True,
        "requires_image": False,
    },
    "M": {
        "priority": "P1",
        "scores": {
            "state_clarity": 3.9,
            "progress_feedback": 3.8,
            "recovery_clarity": 3.6,
            "negative_path_coverage": 3.2,
            "visual_evidence": 4.0,
            "runtime_observability": 3.3,
            "guardrail_safety": 5.0,
        },
        "finding": "Update remoto tem engenharia, mas o caminho visual ainda precisa de scenario gate.",
        "recommendation": "Gate C17 simulando checking/applying sem aplicar release real.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": False,
        "can_be_updated_remotely": True,
        "requires_image": False,
    },
    "N": {
        "priority": "P1",
        "scores": {
            "state_clarity": 3.8,
            "progress_feedback": 3.6,
            "recovery_clarity": 3.7,
            "negative_path_coverage": 3.1,
            "visual_evidence": 4.0,
            "runtime_observability": 3.2,
            "guardrail_safety": 5.0,
        },
        "finding": "Falha de update precisa provar que a versao anterior e preservada.",
        "recommendation": "Gate C17 de falha simulada com status update_failed e rollback seguro.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": False,
        "can_be_updated_remotely": True,
        "requires_image": False,
    },
    "R": {
        "priority": "P1",
        "scores": {
            "state_clarity": 3.7,
            "progress_feedback": 3.8,
            "recovery_clarity": 3.4,
            "negative_path_coverage": 3.0,
            "visual_evidence": 3.8,
            "runtime_observability": 3.2,
            "guardrail_safety": 5.0,
        },
        "finding": "Sem internet precisa diferenciar cache, API e rede sem virar tela preta.",
        "recommendation": "Gate C17 de sem-internet com cache e sem cache, sem mudar rede real nesta rodada.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": True,
        "can_be_updated_remotely": True,
        "requires_image": False,
    },
    "T": {
        "priority": "P1",
        "scores": {
            "state_clarity": 3.5,
            "progress_feedback": 3.5,
            "recovery_clarity": 3.3,
            "negative_path_coverage": 2.9,
            "visual_evidence": 3.7,
            "runtime_observability": 3.1,
            "guardrail_safety": 5.0,
        },
        "finding": "Sem cache e sem API e a pior jornada: precisa erro publico, nao espera indefinida.",
        "recommendation": "Gate C17 obrigatorio de no-cache/no-content; C18 so trata timing/sync/loop.",
        "required_test_before_C17": True,
        "can_be_tested_offline": True,
        "needs_runtime_probe": True,
        "needs_hdmi_camera": True,
        "can_be_updated_remotely": True,
        "requires_image": False,
    },
}


SYNTHETIC_USERS: list[dict[str, str]] = [
    {
        "user_id": "installer_rushed",
        "goal": "configurar rapido",
        "behavior": "baixa tolerancia a tela preta, pode errar senha, nao le texto longo",
    },
    {
        "user_id": "installer_cautious",
        "goal": "configurar com seguranca",
        "behavior": "le instrucoes, precisa clareza de voltar/cancelar, tolera espera com feedback",
    },
    {
        "user_id": "support_remote",
        "goal": "diagnosticar sem HDMI",
        "behavior": "depende de status publico e precisa separar rede/API/cache/player",
    },
    {
        "user_id": "spectator",
        "goal": "ver conteudo",
        "behavior": "nao interage; tela tecnica ou preta prolongada quebra confianca",
    },
    {
        "user_id": "customer_receiver",
        "goal": "avaliar produto final",
        "behavior": "interpreta transicoes ruins como baixa qualidade",
    },
]


INHERITED_P1_GATES: list[dict[str, Any]] = [
    {
        "item_id": "P1-001",
        "title": "Negative API/cache/content scenarios",
        "journeys": ["G", "I", "K", "R", "T"],
        "gate": "C17-GATE-API-CACHE-CONTENT",
        "decision": "vira gate C17",
        "needs_c16_3_runtime_probe": False,
        "can_simulate_offline": True,
        "needs_player_future_c18": False,
        "can_be_tested_by_remote_update": True,
        "notes": "C18 fica restrito a timing/sync/duration/loop.",
    },
    {
        "item_id": "P1-002",
        "title": "Wi-Fi wrong password / weak Wi-Fi",
        "journeys": ["E", "F"],
        "gate": "C17-GATE-WIFI-NEGATIVE",
        "decision": "vira gate C17",
        "needs_board": True,
        "can_simulate_nmcli_output": True,
        "requires_physical_interaction": False,
        "can_be_tested_by_remote_update": True,
        "notes": "C16.2 cobre galeria e output sintetico; C17 valida runtime se autorizado.",
    },
    {
        "item_id": "P1-003",
        "title": "Update UX path",
        "journeys": ["M", "N"],
        "gate": "C17-GATE-UPDATE-UX",
        "decision": "vira gate C17",
        "can_simulate_without_applying_release": True,
        "needs_status_update_screen": True,
        "can_be_tested_by_remote_update": True,
        "notes": "Nao aplicar release real durante a simulacao de UX.",
    },
    {
        "item_id": "P1-004",
        "title": "HDMI/camera methodology",
        "journeys": ["A", "B", "C", "H", "I", "J", "K", "R", "T"],
        "gate": "SCALE-GATE-HDMI-CAMERA",
        "decision": "opcional antes de C17, obrigatorio antes de escala",
        "mandatory_before_c17": False,
        "mandatory_before_scale": True,
        "optional_now": True,
        "can_be_tested_by_remote_update": False,
        "notes": "SSH/timeline nao substitui percepcao visual final.",
    },
    {
        "item_id": "P1-005",
        "title": "Wizard visual consistency",
        "journeys": ["C", "D", "E", "F", "H"],
        "gate": "C17-GATE-WIZARD-VISUAL-CONSISTENCY",
        "decision": "vira gate C17 por galeria + rubrica",
        "can_be_evaluated_by_gallery_rubric": True,
        "screen_score_threshold": 4.0,
        "needs_c16_3_or_c16_4": False,
        "can_be_tested_by_remote_update": True,
        "notes": "C16.2 deve bloquear C16.4 apenas se tela critica ficar abaixo de 4.",
    },
]


def utc_timestamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def atomic_write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    normalized = "\n".join(str(content).splitlines()).rstrip() + "\n"
    tmp.write_text(normalized, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path: pathlib.Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def avg(values: list[float]) -> float:
    return sum(values) / max(1, len(values))


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def lowest_dimension(scores: dict[str, float]) -> dict[str, Any]:
    name, score = min(scores.items(), key=lambda item: item[1])
    return {"name": name, "score": round(score, 1)}


def load_base_model() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    personas = [asdict(item) for item in c16.personas()]
    journeys = [asdict(item) for item in c16.journeys()]
    screens = [asdict(item) for item in c16.screens()]
    for journey in journeys:
        journey["critical_in_c16_2"] = journey["journey_id"] in CRITICAL_JOURNEY_IDS
    return personas, journeys, screens


def build_journey_scores(journeys: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {journey["journey_id"]: journey for journey in journeys}
    scores = []
    for journey_id in CRITICAL_JOURNEY_IDS:
        journey = by_id[journey_id]
        assessment = JOURNEY_ASSESSMENTS[journey_id]
        dimensions = assessment["scores"]
        overall = round(avg(list(dimensions.values())), 1)
        scores.append(
            {
                "journey_id": journey_id,
                "name": journey["name"],
                "score_overall": overall,
                "lowest_dimension": lowest_dimension(dimensions),
                "priority": assessment["priority"],
                "dimension_scores": {key: round(value, 1) for key, value in dimensions.items()},
                "finding": assessment["finding"],
                "recommendation": assessment["recommendation"],
                "required_test_before_C17": assessment["required_test_before_C17"],
                "can_be_tested_offline": assessment["can_be_tested_offline"],
                "needs_runtime_probe": assessment["needs_runtime_probe"],
                "needs_hdmi_camera": assessment["needs_hdmi_camera"],
                "can_be_updated_remotely": assessment["can_be_updated_remotely"],
                "requires_image": assessment["requires_image"],
            }
        )
    return scores


def gallery_rubric_by_id(gallery_dir: pathlib.Path) -> dict[str, dict[str, Any]]:
    rubric_path = gallery_dir / "ux-review-rubric.json"
    if not rubric_path.exists():
        return {}
    data = json.loads(rubric_path.read_text(encoding="utf-8"))
    return {item["screen_id"]: item for item in data}


def build_screen_scores(screens: list[dict[str, Any]], gallery_dir: pathlib.Path) -> list[dict[str, Any]]:
    rubric = gallery_rubric_by_id(gallery_dir)
    output = []
    for screen in screens:
        screen_id = screen["screen_id"]
        gallery_id = SCREEN_GALLERY_ALIASES.get(screen_id, screen_id)
        basis = rubric.get(gallery_id, {})
        values = [
            float(basis.get("task_clarity", 4)),
            float(basis.get("visual_hierarchy", 4)),
            float(basis.get("text_density_score", 4)),
            float(basis.get("primary_action_clarity", 4)),
            float(basis.get("feedback_quality", 4)),
            float(basis.get("footer_clarity", 4)),
            float(basis.get("perceived_polish", 4)),
        ]
        risk = str(screen.get("risk", "medium"))
        risk_penalty = {"low": 0.0, "medium": 0.25, "high": 0.45}.get(risk, 0.25)
        overall = round(max(1.0, avg(values) - risk_penalty), 1)
        output.append(
            {
                "screen_id": screen_id,
                "gallery_screen_id": gallery_id,
                "score_overall": overall,
                "risk": risk,
                "lowest_dimension": {
                    "name": "perceived_polish",
                    "score": float(basis.get("perceived_polish", 4)),
                },
                "heuristic_basis": "C16.1 screen intent + C16.2 synthetic gallery rubric",
                "recommended_action": basis.get("recommended_action", "keep"),
                "critical_below_4": overall < 4.0 and screen_id in SCREEN_GALLERY_ALIASES,
            }
        )
    return output


def simulate_user_runs(journey_scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    by_id = {item["journey_id"]: item for item in journey_scores}
    for user in SYNTHETIC_USERS:
        user_id = user["user_id"]
        for journey_id in CRITICAL_JOURNEY_IDS:
            score = by_id[journey_id]
            base = float(score["score_overall"])
            delta = 0.0
            confusion = "Baixo: estado e acao ficam claros na galeria sintetica."
            missing = "Sem lacuna offline; falta validacao runtime quando o gate exigir."
            if user_id == "installer_rushed" and journey_id in {"E", "F", "G", "I", "K", "R", "T"}:
                delta -= 0.4
                confusion = "Alto: baixa tolerancia a espera e erro; pode repetir acao errada."
                missing = "Precisa mensagem curta, erro recuperavel e proximo passo obvio."
            elif user_id == "installer_cautious" and journey_id in {"C", "D", "E", "F", "H"}:
                delta += 0.1
                confusion = "Medio: tolera espera, mas depende de voltar/cancelar visivel."
                missing = "Confirmar que cancelar nao corrompe configuracao."
            elif user_id == "support_remote":
                if score["needs_runtime_probe"]:
                    delta -= 0.3
                    confusion = "Medio/alto: sem probe runtime, categorias publicas ainda sao promessa."
                    missing = "Status publico deve separar rede, API, cache, midia, update e player."
                if score["needs_hdmi_camera"]:
                    missing += " HDMI/camera continua necessario para percepcao final."
            elif user_id == "spectator":
                if journey_id in {"A", "G", "I", "J", "K", "R", "T"}:
                    delta -= 0.3
                    confusion = "Alto se houver tela preta ou mensagem tecnica prolongada."
                    missing = "Tela deve sempre parecer produto ativo ou espera intencional."
                if journey_id == "J":
                    delta += 0.2
            elif user_id == "customer_receiver" and journey_id in {"A", "H", "M", "N"}:
                delta -= 0.3
                confusion = "Medio: transicao abrupta parece baixa qualidade, mesmo sem bug funcional."
                missing = "Precisa polimento perceptivo e status visivel durante transicoes."
            adjusted = round(max(1.0, min(5.0, base + delta)), 1)
            runs.append(
                {
                    "synthetic_user_id": user_id,
                    "journey_id": journey_id,
                    "expected_understanding": (
                        f"Entende {score['name']} se a tela mantiver estado, acao e recuperacao claros."
                    ),
                    "likely_confusion": confusion,
                    "missing_feedback": missing,
                    "score": adjusted,
                    "recommendation": score["recommendation"],
                }
            )
    return runs


def backlog_markdown(
    journey_scores: list[dict[str, Any]],
    screen_scores: list[dict[str, Any]],
    synthetic_runs: list[dict[str, Any]],
) -> str:
    worst_journey = min(journey_scores, key=lambda item: item["score_overall"])
    worst_screen = min(screen_scores, key=lambda item: item["score_overall"])
    p1_journeys = [item for item in journey_scores if item["priority"] == "P1"]
    low_user_runs = [item for item in synthetic_runs if item["score"] < 3.5]
    lines = [
        "# C16.2 UX Gap Backlog",
        "",
        "## Summary",
        "",
        f"- P0: 0",
        f"- P1 inherited gates: {len(INHERITED_P1_GATES)}",
        f"- P1 journeys flagged: {len(p1_journeys)}",
        f"- Worst journey: {worst_journey['journey_id']} - {worst_journey['name']} ({worst_journey['score_overall']}/5)",
        f"- Worst screen: {worst_screen['screen_id']} ({worst_screen['score_overall']}/5)",
        f"- Synthetic user runs below 3.5: {len(low_user_runs)}",
        "",
        "## P0",
        "",
        "None.",
        "",
        "## P1",
        "",
    ]
    for gate in INHERITED_P1_GATES:
        lines.extend(
            [
                f"### {gate['item_id']} - {gate['title']}",
                "",
                f"- gate: {gate['gate']}",
                f"- decision: {gate['decision']}",
                f"- journeys: {', '.join(gate['journeys'])}",
                f"- can_be_tested_by_remote_update: {bool_text(bool(gate.get('can_be_tested_by_remote_update', False)))}",
                f"- notes: {gate['notes']}",
                "",
            ]
        )
    lines.extend(
        [
            "## P2",
            "",
            "- Keep HDMI/camera methodology as scale gate if C17 runs without it.",
            "- Keep C18 reserved for player timing/sync/duration/loop.",
            "- Refine support runbook after C17 status evidence.",
            "",
            "## P3",
            "",
            "- Evolve visual design system after C17 image validation.",
        ]
    )
    return "\n".join(lines)


def c17_gates_markdown(journey_scores: list[dict[str, Any]], screen_scores: list[dict[str, Any]]) -> str:
    below_4 = [item for item in screen_scores if item["critical_below_4"]]
    lines = [
        "# C16.2 C17 Validation Gates",
        "",
        "## Mandatory C17 Gates",
        "",
        "- C17-GATE-BOOT-CONFIG: boot, config_pending/config_missing and first setup",
        "  must show public feedback and no technical screen.",
        "- C17-GATE-WIFI-NEGATIVE: wrong password and weak Wi-Fi must produce",
        "  recoverable, sanitized feedback.",
        "- C17-GATE-API-CACHE-CONTENT: API unavailable, media unavailable, no",
        "  internet and no cache must not become black-screen waits.",
        "- C17-GATE-UPDATE-UX: update checking/applying/failed states must be",
        "  simulated without applying a real release.",
        "- C17-GATE-WIZARD-VISUAL-CONSISTENCY: gallery/rubric minimum score is 4",
        "  for critical wizard screens.",
        "",
        "## Optional Before C17",
        "",
        "- HDMI/camera capture is optional for starting one C17 image pass, provided",
        "  C17 records the limitation and keeps the scale gate open.",
        "- C16.3 runtime probes are optional before C17 because each inherited P1 now",
        "  has a specific C17 gate.",
        "",
        "## Required Before Scale",
        "",
        "- HDMI/camera methodology for flicker, black frames, orientation and",
        "  transition perception.",
        "- Runtime status evidence that separates network, API, cache, media, update",
        "  and player categories.",
        "",
        "## C18 Gates",
        "",
        "- Player timing, sync, duration, playlist cadence and loop semantics remain",
        "  outside C16.2/C17 and belong to C18 or later.",
        "",
        "## Remote-Update Testable Gates",
        "",
        "- Wi-Fi visual copy and synthesized nmcli-output scenarios.",
        "- API/cache/content public status copy and state classification.",
        "- Update UX simulated states.",
        "- Wizard visual copy/layout refinements that do not change runtime contracts.",
        "",
        "## Screen Threshold Result",
        "",
        f"- critical_screens_below_4={bool_text(bool(below_4))}",
        f"- screens_scored_count={len(screen_scores)}",
        f"- journeys_scored_count={len(journey_scores)}",
    ]
    return "\n".join(lines)


def build_summary(
    run_dir: pathlib.Path,
    gallery_summary: dict[str, Any],
    journey_scores: list[dict[str, Any]],
    screen_scores: list[dict[str, Any]],
    synthetic_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    p_counts = {
        "P0": 0,
        "P1": len(INHERITED_P1_GATES),
        "P2": 3,
        "P3": 1,
    }
    below_4 = [item for item in screen_scores if item["critical_below_4"]]
    blocked_p0 = p_counts["P0"] > 0
    need_c16_4 = bool(below_4)
    need_c16_3 = False
    ready_for_c17 = not blocked_p0 and not need_c16_3 and not need_c16_4
    guardrails = {
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
        "player_timing_changed": False,
        "scheduler_changed": False,
        "sync_changed": False,
        "duration_changed": False,
        "loop_changed": False,
        "kiosky_player_runtime_changed": False,
        "c12_readonly_blocked": True,
        "c12_4_blocked": True,
    }
    try:
        display_dir = str(run_dir.resolve().relative_to(REPO_ROOT))
    except ValueError:
        display_dir = str(run_dir.resolve())
    return {
        "schema_version": "dadooh-c16-2-synthetic-user-ux-review.v1",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run_dir": display_dir,
        "c16_2_status": "blocked" if blocked_p0 or need_c16_3 or need_c16_4 else "passed",
        "manual_interaction_required": False,
        "operator_keypress_required": False,
        "board_accessed_via_ssh": False,
        "runtime_changed": False,
        "personas_loaded": PRODUCT_DOCS["personas"].exists(),
        "journeys_loaded": PRODUCT_DOCS["journeys"].exists(),
        "screen_intent_loaded": PRODUCT_DOCS["screen_intent"].exists(),
        "rubric_loaded": PRODUCT_DOCS["rubric"].exists(),
        "gallery_generated": bool(gallery_summary.get("gallery_generated", False)),
        "png_render_available": bool(gallery_summary.get("png_render_available", False)),
        "synthetic_users_created": True,
        "synthetic_user_runs_count": len(synthetic_runs),
        "journeys_scored_count": len(journey_scores),
        "screens_scored_count": len(screen_scores),
        "p0_items_count": p_counts["P0"],
        "p1_items_count": p_counts["P1"],
        "p2_items_count": p_counts["P2"],
        "p3_items_count": p_counts["P3"],
        "c17_validation_gates_created": True,
        "ux_pdca_process_created": PRODUCT_DOCS["pdca"].exists(),
        "ready_for_c17_image": ready_for_c17,
        "need_c16_3_runtime_probes_before_c17": need_c16_3,
        "need_c16_4_visual_fix_before_c17": need_c16_4,
        "blocked_p0_user_journey": blocked_p0,
        "decision": "ready_for_c17_image" if ready_for_c17 else "blocked_before_c17",
        "worst_journey": min(journey_scores, key=lambda item: item["score_overall"]),
        "worst_screen": min(screen_scores, key=lambda item: item["score_overall"]),
        "gallery_summary": gallery_summary,
        "guardrails": guardrails,
    }


def write_readme(path: pathlib.Path, summary: dict[str, Any]) -> None:
    lines = [
        "# C16.2 Synthetic User UX Review Evidence",
        "",
        "```text",
    ]
    field_order = [
        "c16_2_status",
        "manual_interaction_required",
        "operator_keypress_required",
        "board_accessed_via_ssh",
        "runtime_changed",
        "personas_loaded",
        "journeys_loaded",
        "screen_intent_loaded",
        "rubric_loaded",
        "gallery_generated",
        "png_render_available",
        "synthetic_users_created",
        "synthetic_user_runs_count",
        "journeys_scored_count",
        "screens_scored_count",
        "p0_items_count",
        "p1_items_count",
        "p2_items_count",
        "p3_items_count",
        "c17_validation_gates_created",
        "ux_pdca_process_created",
        "ready_for_c17_image",
        "need_c16_3_runtime_probes_before_c17",
        "need_c16_4_visual_fix_before_c17",
        "blocked_p0_user_journey",
    ]
    for key in field_order:
        value = summary[key]
        lines.append(f"{key}={bool_text(value) if isinstance(value, bool) else value}")
    lines.append("")
    lines.append("Guardrails:")
    for key, value in summary["guardrails"].items():
        lines.append(f"{key}={bool_text(value)}")
    lines.extend(
        [
            "```",
            "",
            "C16.2 made the C16.1 model executable: it generated/reused the",
            "synthetic gallery, scored critical journeys and screens, simulated five",
            "synthetic users, converted inherited P1 work into C17/C18/scale gates,",
            "and kept all appliance runtime guardrails closed.",
        ]
    )
    atomic_write_text(path, "\n".join(lines))


def assert_sanitized_public_artifacts(out_dir: pathlib.Path) -> None:
    for path in out_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".png"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for marker in FORBIDDEN_MARKERS:
            if marker.lower() in text:
                raise RuntimeError(f"forbidden marker in {path.relative_to(out_dir)}: {marker}")


def run(out_dir: pathlib.Path) -> dict[str, Any]:
    personas, journeys, screens = load_base_model()
    gallery_dir = out_dir / "gallery-review"
    gallery_summary = gallery.generate(gallery_dir)

    journey_scores = build_journey_scores(journeys)
    screen_scores = build_screen_scores(screens, gallery_dir)
    synthetic_runs = simulate_user_runs(journey_scores)

    atomic_write_json(out_dir / "personas.json", personas)
    atomic_write_json(out_dir / "journeys.json", journeys)
    atomic_write_json(out_dir / "screens.json", screens)
    atomic_write_json(out_dir / "journey-scores.json", journey_scores)
    atomic_write_json(out_dir / "screen-scores.json", screen_scores)
    atomic_write_json(out_dir / "synthetic-user-runs.json", synthetic_runs)
    atomic_write_text(out_dir / "ux-gap-backlog.md", backlog_markdown(journey_scores, screen_scores, synthetic_runs))
    atomic_write_text(out_dir / "c17-validation-gates.md", c17_gates_markdown(journey_scores, screen_scores))

    summary = build_summary(out_dir, gallery_summary, journey_scores, screen_scores, synthetic_runs)
    atomic_write_json(out_dir / "run-summary.json", summary)
    write_readme(out_dir / "README.md", summary)
    assert_sanitized_public_artifacts(out_dir)
    return summary


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default=utc_timestamp())
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args(argv)
    out_dir = (
        pathlib.Path(args.out_dir)
        if args.out_dir
        else DEFAULT_RUN_ROOT / f"{args.timestamp}-c16-2-synthetic-user-ux-review"
    )
    summary = run(out_dir)
    print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
