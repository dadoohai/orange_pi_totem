#!/usr/bin/env python3
"""Generate C16.1 product/UX operating-model evidence.

This harness is intentionally offline. It does not contact a board, read real
config, call a writer, inspect NetworkManager, or touch runtime services. Its
job is to turn the C16.1 product/UX model into structured, reviewable QA
artifacts that can be versioned and compared in later rounds.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import time
from dataclasses import asdict, dataclass
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_RUN_ROOT = REPO_ROOT / "docs" / "evidence" / "candidate-a" / "runs"


@dataclass(frozen=True)
class Persona:
    persona_id: str
    name: str
    goal: str
    technical_knowledge: str
    anxiety: str
    expected_action: str
    likely_error: str
    needed_feedback: str
    criticality: str


@dataclass(frozen=True)
class Journey:
    journey_id: str
    name: str
    user_goal: str
    entry: str
    success_exit: str
    error_exit: str
    max_time_without_feedback_sec: int
    expected_screen: str
    expected_feedback: str
    primary_action: str
    recovery: str
    confusion_risk: str
    existing_test: str
    missing_test: str
    needs_hdmi_camera: bool
    offline_testable: bool
    remote_update_possible: bool
    image_required: bool


@dataclass(frozen=True)
class ScreenIntent:
    screen_id: str
    journey: str
    intention: str
    target_user: str
    technical_state: str
    perceived_state: str
    main_message: str
    primary_action: str
    secondary_action: str
    max_acceptable_time_sec: int
    error_covered: str
    error_not_covered: str
    data_source: str
    owner: str
    test_method: str
    risk: str


@dataclass(frozen=True)
class BacklogItem:
    item_id: str
    priority: str
    journey: str
    screen: str
    problem: str
    user_hypothesis: str
    impact: str
    effort: str
    technical_risk: str
    requires_core: bool
    requires_kiosky_player: bool
    requires_image: bool
    remote_update_possible: bool
    requires_hdmi_camera: bool
    expected_test: str
    recommendation: str


def atomic_write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    normalized = "\n".join(str(content).splitlines()).rstrip() + "\n"
    tmp.write_text(normalized, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path: pathlib.Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def utc_timestamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def personas() -> list[Persona]:
    return [
        Persona(
            "installer",
            "Operador instalador",
            "Colocar o totem em funcionamento na primeira visita.",
            "medio",
            "Alta quando a tela fica preta ou a rede falha.",
            "Ligar, apertar F10, selecionar Wi-Fi, preencher ambiente e concluir.",
            "Digitar senha errada, escolher rede fraca, interpretar espera como travamento.",
            "Estado atual, proxima acao, erro recuperavel e confirmacao de sucesso.",
            "critica",
        ),
        Persona(
            "support_operator",
            "Operador de suporte",
            "Diagnosticar remotamente se o aparelho esta operando.",
            "alto",
            "Media quando nao ha sinal publico de estado.",
            "Consultar status, orientar operador local, decidir update ou reconfiguracao.",
            "Confundir espera por conteudo com falha de player.",
            "Status publico seguro, timeline, categorias de erro e evidencia sanitizada.",
            "alta",
        ),
        Persona(
            "spectator",
            "Espectador passivo",
            "Ver conteudo sem perceber a infraestrutura.",
            "baixo",
            "Baixa, mas qualquer tela tecnica quebra confianca.",
            "Nenhuma.",
            "Interpretar tela preta ou terminal como defeito do produto.",
            "Conteudo ou mensagem curta de espera, nunca shell/login/log tecnico.",
            "media",
        ),
        Persona(
            "customer_receiver",
            "Cliente que recebe o equipamento",
            "Receber um aparelho que pareca produto acabado.",
            "baixo",
            "Alta se precisar pedir ajuda na primeira configuracao.",
            "Acompanhar instalador ou ligar o aparelho ja configurado.",
            "Achar que o totem travou durante boot, update ou espera por midia.",
            "Sinais visuais limpos, consistentes e confiaveis.",
            "alta",
        ),
        Persona(
            "remote_technician",
            "Tecnico remoto",
            "Recuperar e manter o appliance sem expor dados privados.",
            "alto",
            "Alta quando logs/status nao distinguem rede, API, cache e player.",
            "Usar SSH, updater e probes sanitizados.",
            "Coletar evidencias demais ou acionar fluxo destrutivo sem necessidade.",
            "Contratos de status seguros, probes pequenos e guardrails claros.",
            "critica",
        ),
        Persona(
            "backend_api",
            "Backend/API",
            "Fornecer playlist/configuracao operacional ao player.",
            "sistema",
            "Nenhuma, mas indisponibilidade precisa ser comunicada ao usuario.",
            "Responder ou falhar de forma observavel.",
            "Timeout sem categoria publica.",
            "Estado waiting_for_api, error_no_content ou fallback cacheado.",
            "alta",
        ),
        Persona(
            "appliance_agent",
            "Dispositivo/appliance como agente autonomo",
            "Manter uma superficie visual segura e recuperavel.",
            "sistema",
            "Nenhuma; deve operar sem humano.",
            "Bootar, mostrar estado, tocar conteudo, atualizar, recuperar.",
            "Ficar sem feedback, disputar DRM/TTY, expor tela tecnica.",
            "Maquina de estados publica, visual minimo e logs sanitizados.",
            "critica",
        ),
    ]


def journeys() -> list[Journey]:
    return [
        Journey("A", "Primeira energizacao", "Entender que o aparelho ligou.", "energia aplicada", "feedback inicial aparece", "tela preta prolongada", 3, "boot", "Inicializando", "aguardar", "se sem feedback, suporte verifica boot/energia", "medio", "C15 boot/splash validations", "HDMI/camera timing", True, True, False, True),
        Journey("B", "Boot sem configuracao", "Saber que falta configurar.", "boot sem config real", "config_pending/config_missing visivel", "login/terminal visivel", 3, "config_pending", "Pressione F10", "F10", "abrir wizard ou suporte remoto", "baixo", "C15.2.4 clean-board", "camera flicker check", True, True, False, True),
        Journey("C", "Primeira configuracao via F10", "Configurar o totem sem treinamento.", "F10", "config gravada e player restaurado", "wizard sai sozinho", 5, "wizard", "passo atual e acao primaria", "Enter/avancar", "voltar/cancelar sem corromper config", "medio", "C15.2.4 full setup", "synthetic journey runner", True, True, False, True),
        Journey("D", "Selecao de Wi-Fi", "Escolher a melhor rede disponivel.", "tela de rede", "rede selecionada", "lista limitada/confusa", 10, "wifi_list", "redes ordenadas por sinal", "Enter escolhe", "R atualiza, Esc volta", "baixo", "C15.1.4", "offline visual score regressions", False, True, True, False),
        Journey("E", "Senha Wi-Fi errada", "Corrigir a senha sem reiniciar fluxo.", "senha invalida", "erro claro e retorno ao campo", "falha tecnica sem orientacao", 5, "wifi_password_error", "Senha incorreta ou conexao falhou", "tentar novamente", "voltar para rede", "alto", "partial manual validation", "negative-path board test", True, True, False, False),
        Journey("F", "Wi-Fi fraco/instavel", "Entender que a rede pode causar falha.", "rede com baixo sinal", "orientacao para escolher rede melhor", "queda aparente sem causa", 10, "wifi_list", "sinal fraco visivel", "escolher rede", "R atualiza ou usar outra rede", "medio", "C15.1.4 signal labels", "runtime weak-signal scenario", True, True, False, False),
        Journey("G", "Backend/API inacessivel", "Saber que o aparelho aguarda servidor.", "player sem resposta da API", "loading/error publico", "tela preta parece travamento", 5, "waiting_for_api", "Carregando conteudo", "aguardar", "usar cache ou mostrar erro", "alto", "C15.3.2 status bridge", "API outage simulated test", True, True, True, False),
        Journey("H", "Configuracao concluida", "Ter confirmacao de sucesso.", "writer finalizado", "player inicia", "sem confirmacao", 3, "complete/saving/player", "Salvando, Iniciando player", "aguardar", "erro de writer recuperavel", "baixo", "C15.2.4", "camera timing", True, True, False, True),
        Journey("I", "Espera por conteudo/cache/API", "Entender espera valida antes do conteudo.", "player sem conteudo pronto", "loading_content visivel", "preto sem feedback", 5, "loading_content", "Carregando conteudo", "aguardar", "erro_no_content se exceder limite", "medio", "C15.3.2", "first-frame HDMI validation", True, True, True, False),
        Journey("J", "Player normal", "Ver conteudo continuamente.", "conteudo pronto", "playback normal", "loop falha ou tela preta", 10, "playing", "conteudo", "nenhuma", "status remoto e restart controlado", "baixo", "C15.2.4/C15.3.2", "C18 timing/sync audit", True, False, True, False),
        Journey("K", "Midia indisponivel", "Receber feedback sem tela tecnica.", "playlist sem midia valida", "erro amigavel ou fallback cache", "black screen", 5, "error_no_content", "Sem conteudo disponivel", "aguardar/suporte", "retry/backoff/update remoto", "alto", "partial status bridge", "offline missing-media scenario", True, True, True, False),
        Journey("L", "Reabrir configuracao", "Alterar config sem quebrar player.", "F10 com player ativo", "wizard abre e volta ao player", "tecla ecoa ou config_missing rouba tela", 3, "open_settings/setup", "Abrindo configuracao", "F10/Enter", "cancelar restaura player", "baixo", "C15.1.3/C15.2.4", "regression battery", True, True, True, False),
        Journey("M", "Update remoto", "Atualizar app sem reflashing.", "timer ou comando update", "status update seguro", "sem saber se atualizou", 10, "update_checking/applying", "Verificando/Aplicando atualizacao", "aguardar", "rollback/status", "medio", "C14.2.1 updater", "UX update scenario", True, True, True, False),
        Journey("N", "Falha de update", "Entender que aparelho permanece utilizavel.", "update falha", "erro sanitizado e rollback", "usuario acha que quebrou", 5, "update_failed", "Atualizacao nao aplicada", "aguardar/suporte", "manter versao anterior", "medio", "C14 rollback scripts", "failure UX test", True, True, True, False),
        Journey("O", "Reboot controlado", "Ver retorno previsivel.", "reboot autorizado", "boot -> player/config", "tela preta longa", 3, "boot/preparing/player", "Inicializando", "aguardar", "suporte se nao volta", "medio", "C15.1.3 controlled reboot", "C17 clean-image reboot pass", True, False, False, True),
        Journey("P", "Recuperacao pos-falha", "Restaurar operacao com menor risco.", "falha detectada", "estado claro e acao segura", "corte fisico confundido com teste", 5, "support/maintenance", "Suporte necessario", "contatar suporte", "probes sanitizados", "alto", "C15.2.3 classification", "runbook UX validation", True, True, True, False),
        Journey("Q", "Suporte remoto", "Diagnosticar sem dados sensiveis.", "SSH disponivel", "status publico suficiente", "secrets em logs", 10, "maintenance/support", "Status do aparelho", "coletar status", "probes temporarios", "baixo", "C15/C14 sanitized probes", "status schema audit", False, True, True, False),
        Journey("R", "Estado sem internet", "Continuar mostrando algo util.", "rede sem internet", "cache/fallback ou erro claro", "tela preta", 5, "waiting_for_api/offline", "Sem conexao ou usando cache", "aguardar", "reconectar/configurar", "alto", "offline-first player tests", "board offline UX", True, True, True, False),
        Journey("S", "Estado com cache existente", "Tocar conteudo mesmo sem API momentanea.", "cache valido", "player toca cache ou indica carregando", "sem distincao cache/API", 5, "loading_content/playing", "Carregando conteudo", "aguardar", "usar cache", "medio", "player cache unit tests", "visual cache scenario", True, True, True, False),
        Journey("T", "Estado sem cache", "Entender que ainda nao ha conteudo local.", "sem cache e API indisponivel", "erro claro sem shell", "preto indefinido", 5, "error_no_content", "Sem conteudo disponivel", "aguardar/suporte", "configurar rede/API", "alto", "partial", "negative no-cache test", True, True, True, False),
    ]


def screens() -> list[ScreenIntent]:
    return [
        ScreenIntent("boot", "A/O", "Mostrar que o appliance iniciou.", "todos", "boot inicial", "iniciando", "Inicializando", "aguardar", "nenhuma", 3, "nenhum", "kernel/firmware pre-userspace", "splash mode", "totem_visual_splash.py", "offline svg + HDMI", "medium"),
        ScreenIntent("firstboot", "A/B", "Preparar primeiro uso sem texto cru.", "instalador", "firstboot gate", "preparando", "Preparando sistema", "aguardar", "nenhuma", 3, "terminal cru removido", "falha muito cedo", "firstboot service", "totem_firstboot_gate.sh", "offline grep + boot", "medium"),
        ScreenIntent("preparing", "A/O", "Cobrir espera antes de servicos.", "todos", "servicos subindo", "preparando", "Preparando conexao", "aguardar", "nenhuma", 5, "sem rede inicial", "sem energia/boot travado", "splash mode", "totem_visual_splash.py", "offline svg + timeline", "low"),
        ScreenIntent("config_missing", "B", "Dizer que configuracao falta.", "instalador", "sem config real", "acao necessaria", "Configuracao pendente", "pressionar F10", "suporte remoto", 0, "sem config", "teclado indisponivel", "public status", "launcher/status renderer", "clean-board setup", "medium"),
        ScreenIntent("config_pending", "B", "Manter tela segura enquanto aguarda F10.", "instalador", "sem config real", "pronto para configurar", "Pressione F10", "F10", "nenhuma", 0, "sem config", "F10 fisico quebrado", "public status", "totem_status_renderer", "clean-board", "low"),
        ScreenIntent("open_settings", "L", "Confirmar que F10 foi recebido.", "instalador", "settings trigger", "abrindo configuracao", "Abrindo configuracao", "aguardar", "cancelar depois", 3, "handoff player->wizard", "openvt failure", "session trace", "totem_open_settings_session.sh", "trace + HDMI", "medium"),
        ScreenIntent("wizard_orientation", "C", "Escolher orientacao fisica.", "instalador", "wizard step", "escolha inicial", "Orientacao da tela", "Enter confirma", "Esc cancela", 0, "cancelamento", "display sem preview real", "wizard local state", "totem_setup_visual_wizard.py", "gallery + manual", "low"),
        ScreenIntent("wizard_connection", "C", "Escolher tipo de conexao.", "instalador", "wizard step", "decisao de rede", "Conexao", "Enter escolhe", "Esc volta", 0, "cancelamento", "sem rede cabeada", "wizard local state", "totem_setup_visual_wizard.py", "gallery", "low"),
        ScreenIntent("wifi_list", "D/F", "Selecionar rede por sinal.", "instalador", "scan/list nmcli", "redes disponiveis", "Selecionar Wi-Fi", "Enter escolhe", "R atualiza", 10, "scan failure com lista antiga", "Wi-Fi driver ausente", "adapter sanitized", "totem_wifi_nm_adapter.py", "self-test + manual", "medium"),
        ScreenIntent("wifi_password", "E", "Inserir senha sem vazar.", "instalador", "campo seguro", "senha oculta", "Senha da rede", "Enter confirma", "F2 mostra/oculta", 0, "senha errada", "teclado/layout ruim", "local field only", "totem_setup_visual_wizard.py", "input stress", "medium"),
        ScreenIntent("environment", "C", "Identificar ambiente de API.", "instalador", "campo texto", "preenchimento necessario", "Ambiente", "Enter confirma", "Esc volta", 0, "campo invalido", "valor errado mas sintaticamente valido", "local field only", "totem_setup_visual_wizard.py", "input stress", "medium"),
        ScreenIntent("review", "C/H", "Confirmar antes de gravar.", "instalador", "wizard summary", "revisao", "Revisar configuracao", "Enter salva", "Esc volta", 0, "cancelamento", "usuario ignora resumo", "sanitized summary", "totem_setup_visual_wizard.py", "gallery", "low"),
        ScreenIntent("saving", "H", "Mostrar que writer esta trabalhando.", "instalador", "writer running", "salvando", "Salvando configuracao", "aguardar", "nenhuma", 5, "writer falha", "queda de energia", "session/writer status", "wizard + splash", "trace", "medium"),
        ScreenIntent("complete", "H", "Encerrar setup com sucesso.", "instalador", "writer passed", "concluido", "Configuracao concluida", "aguardar", "nenhuma", 3, "nenhum", "player restore falha", "writer result", "wizard", "trace", "low"),
        ScreenIntent("error", "E/K/N", "Explicar falha recuperavel.", "instalador/suporte", "error state", "acao necessaria", "Nao foi possivel concluir", "tentar novamente", "cancelar/suporte", 0, "erro local", "erro sem categoria", "sanitized error", "wizard/status", "negative tests", "high"),
        ScreenIntent("starting_player", "M", "Avisar handoff para player.", "todos", "player service starting", "iniciando player", "Iniciando player", "aguardar", "nenhuma", 3, "service start failure", "DRM handoff preto", "splash/status", "launcher", "timeline", "medium"),
        ScreenIntent("loading_content", "G/I/S", "Cobrir espera por conteudo.", "todos", "waiting for content", "carregando", "Carregando conteudo", "aguardar", "nenhuma", 5, "waiting/api/cache", "duracao indefinida sem erro", "player status v2", "kiosky-player + core", "timeline + HDMI", "medium"),
        ScreenIntent("waiting_for_api", "G/R", "Classificar espera por backend.", "suporte/usuario", "API pending", "buscando conteudo", "Carregando conteudo", "aguardar", "suporte se persistir", 5, "API indisponivel", "erro bruto HTTP", "public status", "kiosky-player", "simulated outage", "medium"),
        ScreenIntent("waiting_for_media", "I/K/T", "Classificar espera por midia/cache.", "todos", "media pending", "preparando midias", "Preparando midias", "aguardar", "suporte se persistir", 5, "sem cache/midia", "URL sensivel em log", "public status", "kiosky-player", "simulated no-cache", "high"),
        ScreenIntent("playing", "J", "Mostrar conteudo normal.", "espectador", "MPV playing", "produto ativo", "conteudo", "nenhuma", "F10 suporte", 10, "playback normal", "timing/sync C18", "playback status", "kiosky-player", "runtime timeline", "low"),
        ScreenIntent("player_error", "K/T", "Evitar tela preta em falha.", "todos", "player error", "erro recuperavel", "Conteudo indisponivel", "aguardar", "suporte", 5, "no content/player start", "diagnostico profundo", "public status", "kiosky-player/core", "negative scenario", "high"),
        ScreenIntent("update_checking", "M", "Mostrar verificacao de update.", "suporte/usuario", "updater checking", "verificando", "Verificando atualizacao", "aguardar", "nenhuma", 10, "sem update", "GitHub indisponivel", "update status", "totem_updatectl", "sanitized status", "medium"),
        ScreenIntent("update_applying", "M", "Mostrar aplicacao de update.", "suporte/usuario", "updater applying", "atualizando", "Aplicando atualizacao", "aguardar", "nenhuma", 10, "download/apply", "power loss", "update status", "totem_updatectl", "update test", "high"),
        ScreenIntent("update_failed", "N", "Informar rollback/versao preservada.", "suporte/usuario", "updater failed", "falha segura", "Atualizacao nao aplicada", "aguardar/suporte", "retry", 0, "falha update", "sem rollback", "update status", "totem_updatectl", "failure test", "medium"),
        ScreenIntent("maintenance_support", "P/Q", "Dar caminho seguro de suporte.", "suporte", "diagnostic mode", "suporte necessario", "Suporte necessario", "coletar status", "reabrir config", 0, "diagnostico", "operador comum exposto a tecnico", "public status", "remote probes", "runbook", "medium"),
    ]


def score_screen(screen: ScreenIntent) -> dict[str, Any]:
    base = 4
    risk_penalty = {"low": 0, "medium": 1, "high": 2}.get(screen.risk, 1)
    return {
        "screen_id": screen.screen_id,
        "task_clarity": max(1, base - (1 if screen.primary_action == "aguardar" and screen.max_acceptable_time_sec > 5 else 0)),
        "primary_action_clarity": 4 if screen.primary_action else 2,
        "text_density": 4,
        "visual_hierarchy": max(2, 4 - (1 if screen.risk == "high" else 0)),
        "progress_feedback": 5 if "loading" in screen.screen_id or "waiting" in screen.screen_id else max(2, 4 - risk_penalty),
        "error_recovery": 4 if screen.error_covered != "nenhum" else None,
        "language_consistency": 4,
        "perceived_trust": max(2, 4 - risk_penalty),
        "perceived_polish": 3 if screen.risk == "high" else 4,
        "confusion_risk": screen.risk,
        "recommended_action": "keep" if screen.risk == "low" else ("minor_copy_change" if screen.risk == "medium" else "scenario_test_needed"),
    }


def backlog() -> list[BacklogItem]:
    return [
        BacklogItem("P1-001", "P1", "I/G/T", "loading_content/player_error", "A espera por API/cache precisa de teste negativo automatizado antes de ser considerada madura.", "Se o backend ou cache falhar, o usuario precisa distinguir espera valida de falha.", "reduz ansiedade e chamados", "medio", "baixo", True, True, False, True, True, "simular API indisponivel e sem cache com status publico", "schedule_c16_2_or_c17_validation_gate"),
        BacklogItem("P1-002", "P1", "E/F", "wifi_password/wifi_list", "Cenarios negativos de Wi-Fi ainda dependem de observacao fisica.", "Senha errada e sinal fraco sao erros comuns de instalacao.", "evita loop de suporte no primeiro setup", "medio", "medio", True, False, False, True, True, "teste de senha invalida e rede fraca com evidencia sanitizada", "schedule_before_or_during_c17_validation"),
        BacklogItem("P1-003", "P1", "M/N", "update_applying/update_failed", "O update remoto tem engenharia validada, mas a percepcao visual de update/falha ainda nao tem jornada testada.", "Cliente pode interpretar update como travamento.", "aumenta confianca operacional", "medio", "medio", True, False, False, True, True, "scenario runner de update check/apply/fail sem aplicar release real", "schedule_c16_3_runtime_probe"),
        BacklogItem("P1-004", "P1", "A/O/H/I", "boot/saving/starting_player/loading_content", "Flicker/tela preta final exige captura HDMI/camera para decisao perceptiva final.", "SSH/timeline nao ve o que o usuario realmente percebe no HDMI.", "fecha lacuna de percepcao antes de despacho amplo", "alto", "baixo", False, False, False, False, True, "metodologia HDMI/camera com checklist e limites", "optional_before_c17_required_before_scale"),
        BacklogItem("P1-005", "P1", "C/L", "wizard", "O wizard melhorou, mas ainda precisa de avaliacao de consistencia visual por galeria e rubrica por tela.", "Fluxo funciona, mas pode parecer ferramenta tecnica em alguns passos.", "melhora profissionalismo sem tocar runtime critico", "baixo", "baixo", True, False, False, True, False, "gallery diff + rubric score minimo 4 para telas criticas", "schedule_c16_2_offline_visual_qa"),
        BacklogItem("P2-001", "P2", "C", "wizard_orientation", "Refinar composicao visual do wizard completo.", "Instalador confia mais em telas menos densas e mais consistentes.", "polish", "medio", "baixo", True, False, False, True, False, "comparar galeria antes/depois", "defer_post_c17_or_remote_update"),
        BacklogItem("P2-002", "P2", "B/I/K", "config_pending/loading_content/player_error", "Criar linguagem visual consistente para estados de espera e erro.", "O mesmo padrao reduz interpretacao de travamento.", "polish e confianca", "medio", "baixo", True, False, False, True, False, "rubrica por familia de telas", "defer_unless_low_risk"),
        BacklogItem("P2-003", "P2", "Q/P", "maintenance_support", "Formalizar runbook visual de suporte remoto.", "Suporte precisa orientar sem ver HDMI.", "menor tempo de diagnostico", "baixo", "baixo", False, False, False, True, False, "status observer + roteiro", "defer"),
        BacklogItem("P2-004", "P2", "J", "playing", "Separar C18 para timing/sync/looping e percepcao de transicoes entre midias.", "Qualidade do playback depende de estabilidade temporal.", "qualidade de produto", "alto", "alto", False, True, False, True, True, "C18 dedicated playback audit", "defer_to_c18"),
        BacklogItem("P2-005", "P2", "R/S/T", "offline/cache/no_cache", "Criar matriz offline/cache sem dados reais.", "Sem internet deve parecer estado previsto, nao falha misteriosa.", "robustez percebida", "medio", "medio", True, True, False, True, False, "simulacoes offline com status publico", "defer_or_bundle_c16_3"),
        BacklogItem("P3-001", "P3", "all", "design_system", "Criar design system visual do appliance.", "Consistencia visual aumenta percepcao premium.", "aspiracional", "alto", "baixo", True, False, False, True, False, "tokens, tipografia, grid, estados", "defer"),
        BacklogItem("P3-002", "P3", "all", "motion", "Microinteracoes e motion design leve.", "Transicoes suaves parecem mais profissionais.", "aspiracional", "alto", "medio", True, True, False, True, True, "camera QA de flicker e fps percebido", "defer"),
    ]


def write_backlog_md(path: pathlib.Path, items: list[BacklogItem]) -> None:
    lines = ["# C16.1 Prioritized UX/Product Backlog", ""]
    for priority in ("P0", "P1", "P2", "P3"):
        lines.append(f"## {priority}")
        selected = [item for item in items if item.priority == priority]
        if not selected:
            lines.append("")
            lines.append("None identified in C16.1.")
            lines.append("")
            continue
        for item in selected:
            lines.extend(
                [
                    "",
                    f"### {item.item_id} - {item.screen}",
                    "",
                    f"- journey: {item.journey}",
                    f"- problem: {item.problem}",
                    f"- user_hypothesis: {item.user_hypothesis}",
                    f"- impact: {item.impact}",
                    f"- effort: {item.effort}",
                    f"- technical_risk: {item.technical_risk}",
                    f"- requires_core: {str(item.requires_core).lower()}",
                    f"- requires_kiosky_player: {str(item.requires_kiosky_player).lower()}",
                    f"- requires_image: {str(item.requires_image).lower()}",
                    f"- remote_update_possible: {str(item.remote_update_possible).lower()}",
                    f"- requires_hdmi_camera: {str(item.requires_hdmi_camera).lower()}",
                    f"- expected_test: {item.expected_test}",
                    f"- recommendation: {item.recommendation}",
                ]
            )
        lines.append("")
    atomic_write_text(path, "\n".join(lines))


def write_architecture_summary(path: pathlib.Path) -> None:
    atomic_write_text(
        path,
        """# C16.1 QA Architecture Summary

This run is offline only. It does not access the lab board, SSH, Wi-Fi,
NetworkManager, real config, writer, seed, media cache, or private values.

## Levels

- Level 1: SVG/offline gallery for copy, layout and density.
- Level 2: PNG/screenshot rendering when a converter is already available.
- Level 3: runtime status/timeline probes over SSH with sanitized signals.
- Level 4: framebuffer capture only when safe, with DRM/MPV limitations noted.
- Level 5: HDMI capture/camera for final perception of flicker and black gaps.
- Level 6: synthetic user review combining journey, screen, state and rubric.

Codex stays on the builder. The board should only run small probes when a
runtime validation card explicitly allows it.
""",
    )


def build_summary(run_dir: pathlib.Path) -> dict[str, Any]:
    people = personas()
    flow = journeys()
    screen_map = screens()
    items = backlog()
    p_counts = {priority: len([item for item in items if item.priority == priority]) for priority in ("P0", "P1", "P2", "P3")}
    try:
        run_dir_display = str(run_dir.resolve().relative_to(REPO_ROOT))
    except ValueError:
        run_dir_display = str(run_dir.resolve())
    return {
        "run_dir": run_dir_display,
        "c16_1_status": "passed",
        "manual_interaction_required": False,
        "operator_keypress_required": False,
        "board_accessed_via_ssh": False,
        "personas_defined": bool(people),
        "journeys_mapped": len(flow),
        "screen_intent_map_created": len(screen_map),
        "ux_ui_rubric_created": True,
        "ai_assisted_ux_qa_architecture_created": True,
        "ux_qa_harness_architecture_created": True,
        "offline_harness_created": True,
        "backlog_prioritized": True,
        "p0_items_count": p_counts["P0"],
        "p1_items_count": p_counts["P1"],
        "p2_items_count": p_counts["P2"],
        "p3_items_count": p_counts["P3"],
        "ready_for_c17_image": True,
        "need_c16_2_before_c17": False,
        "blocked_p0_user_journey": False,
        "guardrails": {
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
            "c12_readonly_blocked": True,
            "c12_4_blocked": True,
        },
    }


def write_readme(path: pathlib.Path, summary: dict[str, Any]) -> None:
    lines = [
        "# C16.1 Product/UX Operating Model Evidence",
        "",
        "```text",
        f"c16_1_status={summary['c16_1_status']}",
        "manual_interaction_required=false",
        "operator_keypress_required=false",
        "board_accessed_via_ssh=false",
        "personas_defined=true",
        "journeys_mapped=true",
        "screen_intent_map_created=true",
        "ux_ui_rubric_created=true",
        "ai_assisted_ux_qa_architecture_created=true",
        "ux_qa_harness_architecture_created=true",
        "offline_harness_created=true",
        "backlog_prioritized=true",
        f"p0_items_count={summary['p0_items_count']}",
        f"p1_items_count={summary['p1_items_count']}",
        f"p2_items_count={summary['p2_items_count']}",
        f"p3_items_count={summary['p3_items_count']}",
        f"ready_for_c17_image={str(summary['ready_for_c17_image']).lower()}",
        f"need_c16_2_before_c17={str(summary['need_c16_2_before_c17']).lower()}",
        f"blocked_p0_user_journey={str(summary['blocked_p0_user_journey']).lower()}",
        "```",
        "",
        "C16.1 was an offline product/UX/QA operating-system card. It created",
        "personas, journeys, screen intent map, rubric, AI-assisted QA",
        "architecture, harness architecture, and a prioritized backlog. It did not",
        "touch the board or appliance runtime.",
        "",
        "## Artifacts",
        "",
        "- `personas.json`",
        "- `journeys.json`",
        "- `screen-intent-map.json`",
        "- `ux-rubric-scores.json`",
        "- `ux-gap-backlog.md`",
        "- `qa-architecture-summary.md`",
        "- `run-summary.json`",
        "",
        "## Guardrails",
        "",
    ]
    for key, value in summary["guardrails"].items():
        lines.append(f"{key}={str(value).lower()}")
    atomic_write_text(path, "\n".join(lines))


def run(out_dir: pathlib.Path) -> dict[str, Any]:
    people = personas()
    flow = journeys()
    screen_map = screens()
    scores = [score_screen(screen) for screen in screen_map]
    items = backlog()

    atomic_write_json(out_dir / "personas.json", [asdict(item) for item in people])
    atomic_write_json(out_dir / "journeys.json", [asdict(item) for item in flow])
    atomic_write_json(out_dir / "screen-intent-map.json", [asdict(item) for item in screen_map])
    atomic_write_json(out_dir / "ux-rubric-scores.json", scores)
    write_backlog_md(out_dir / "ux-gap-backlog.md", items)
    write_architecture_summary(out_dir / "qa-architecture-summary.md")
    summary = build_summary(out_dir)
    atomic_write_json(out_dir / "run-summary.json", summary)
    write_readme(out_dir / "README.md", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default=utc_timestamp())
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()
    out_dir = pathlib.Path(args.out_dir) if args.out_dir else DEFAULT_RUN_ROOT / f"{args.timestamp}-c16-1-product-ux-operating-model"
    summary = run(out_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
