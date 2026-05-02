#!/usr/bin/env python3
"""Generate static C2 onboarding mock SVG previews.

This tool is intentionally local and non-operational. It does not read network,
config or status state; does not call MPV, systemd or nmcli; and writes only
under /tmp.
"""

from __future__ import annotations

import argparse
import html
import pathlib
import re
import stat
import sys
import textwrap
from dataclasses import dataclass


DEFAULT_OUT_DIR = "/tmp/dadooh-c2-preview"
CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720
MOCK_NOTICE = "Mock visual - nao altera rede nem salva configuracao."
DEVICE_LABEL = "Totem Dadooh"

NETWORK_OPTIONS = (
    "Rede Exemplo 1",
    "Rede Exemplo 2",
    "Rede Convidado Mock",
)

SENSITIVE_PATTERNS = (
    re.compile(r"https?://\S+", re.IGNORECASE),
    re.compile(r"\bapi[_-]?key\b", re.IGNORECASE),
    re.compile(r"\btoken\b", re.IGNORECASE),
    re.compile(r"\bsecret\b", re.IGNORECASE),
    re.compile(r"\bpassword\b", re.IGNORECASE),
    re.compile(r"\bsenha\b", re.IGNORECASE),
    re.compile(r"\benvironment_id\s*[:=]\s*(?!ENVIRONMENT_ID_MOCK\b)\S+", re.IGNORECASE),
    re.compile(r"\bstation[_-]?id\b(?:\s*[:=]\s*\S+)?", re.IGNORECASE),
    re.compile(r"/data/media\S*", re.IGNORECASE),
    re.compile(r"/opt/totem\S*", re.IGNORECASE),
)


@dataclass(frozen=True)
class Screen:
    state: str
    title: str
    message: str
    action: str
    code: str
    accent: str
    step: str
    panel_title: str
    panel_items: tuple[str, ...]
    field_label: str | None = None
    field_value: str | None = None
    field_note: str | None = None


SCREENS: tuple[Screen, ...] = (
    Screen(
        state="config_missing",
        title="Configuracao pendente",
        message="Este totem ainda precisa de configuracao minima.",
        action="Inicie a configuracao assistida quando autorizado.",
        code="CONFIG_MISSING",
        accent="#f97316",
        step="Entrada do fluxo",
        panel_title="Estado seguro",
        panel_items=(
            "Player principal parado",
            "Renderer/setup visual pode aparecer",
            "Nenhuma config real sera escrita",
        ),
    ),
    Screen(
        state="setup_start",
        title="Configuracao assistida",
        message="Este fluxo guiado revisa rede e ambiente em modo prototipo.",
        action="Avance para escolher uma rede de exemplo.",
        code="SETUP_START_MOCK",
        accent="#38bdf8",
        step="1 de 10",
        panel_title="Antes de comecar",
        panel_items=(
            "Nao usa rede real",
            "Nao usa portal local",
            "Nao salva configuracao",
        ),
    ),
    Screen(
        state="wifi_select_mock",
        title="Escolha uma rede",
        message="Selecione uma rede ficticia para revisar a ordem do fluxo.",
        action="Escolha uma opcao de exemplo e avance.",
        code="WIFI_SELECT_MOCK",
        accent="#38bdf8",
        step="2 de 10",
        panel_title="Redes de exemplo",
        panel_items=NETWORK_OPTIONS,
    ),
    Screen(
        state="wifi_password_mock",
        title="Credencial da rede",
        message="Simule a entrada de uma credencial de teste.",
        action="Use somente valor ficticio. Nada sera persistido.",
        code="WIFI_CREDENTIAL_MOCK",
        accent="#38bdf8",
        step="3 de 10",
        panel_title="Entrada ficticia",
        panel_items=(
            "Campo demonstrativo",
            "Nao registrar valor digitado",
            "Nao testar conexao real",
        ),
        field_label="Valor de teste",
        field_value="••••••••",
        field_note="Valor oculto e descartado no mock.",
    ),
    Screen(
        state="wifi_testing_mock",
        title="Testando conexao",
        message="O prototipo mostra uma espera curta sem acessar rede.",
        action="Aguarde a proxima tela de exemplo.",
        code="WIFI_TESTING_MOCK",
        accent="#f59e0b",
        step="4 de 10",
        panel_title="Checagens planejadas",
        panel_items=(
            "Associacao Wi-Fi futura",
            "IP local futuro",
            "Internet basica futura",
        ),
    ),
    Screen(
        state="wifi_ok_mock",
        title="Conexao aprovada",
        message="A tela representa sucesso ficticio de conectividade.",
        action="Avance para informar o ambiente.",
        code="WIFI_OK_MOCK",
        accent="#22c55e",
        step="5 de 10",
        panel_title="Resultado de exemplo",
        panel_items=(
            "Conexao simulada aprovada",
            "Nenhum adaptador de rede alterado",
            "Nenhum perfil salvo",
        ),
    ),
    Screen(
        state="wifi_error_mock",
        title="Nao foi possivel conectar",
        message="A tela representa erro recuperavel sem detalhe tecnico.",
        action="Volte, revise a entrada ficticia ou escolha outra rede.",
        code="WIFI_ERROR_MOCK",
        accent="#ef4444",
        step="5b de 10",
        panel_title="Erro de exemplo",
        panel_items=(
            "Mensagem publica apenas",
            "Sem erro bruto de sistema",
            "Permite tentar novamente",
        ),
    ),
    Screen(
        state="environment_input_mock",
        title="Informe o ambiente",
        message="Digite o identificador de ambiente em formato permitido.",
        action="Use apenas placeholder em revisoes e evidencias.",
        code="ENVIRONMENT_INPUT_MOCK",
        accent="#38bdf8",
        step="6 de 10",
        panel_title="Formato proposto",
        panel_items=(
            "3 a 128 caracteres",
            "Letras ASCII, numeros, ponto, dois-pontos, hifen e sublinhado",
            "Sem validacao backend nesta fase",
        ),
        field_label="environment_id",
        field_value="ENVIRONMENT_ID_MOCK",
        field_note="Placeholder explicito. Nao use valor real.",
    ),
    Screen(
        state="environment_invalid_mock",
        title="Ambiente invalido",
        message="O valor informado nao passou na validacao local do mock.",
        action="Corrija o formato antes de continuar.",
        code="ENVIRONMENT_INVALID_MOCK",
        accent="#ef4444",
        step="6b de 10",
        panel_title="Validacao local",
        panel_items=(
            "Nao pode ficar vazio",
            "Nao pode conter espaco",
            "Nao consulta backend",
        ),
        field_label="environment_id",
        field_value="INVALIDO MOCK",
        field_note="Exemplo ficticio recusado por conter espaco.",
    ),
    Screen(
        state="config_ready_mock",
        title="Configuracao pronta",
        message="O prototipo chegou ao ponto em que um writer futuro atuaria.",
        action="Revise os dados ficticios antes da transicao.",
        code="CONFIG_READY_MOCK",
        accent="#22c55e",
        step="7 de 10",
        panel_title="Resumo ficticio",
        panel_items=(
            "Rede de exemplo selecionada",
            "Ambiente mock preenchido",
            "Nenhuma config real substituida",
        ),
    ),
    Screen(
        state="starting_player_mock",
        title="Iniciando exibicao",
        message="A transicao mostra onde o setup sairia antes do player.",
        action="Em implementacao real, renderer/setup para primeiro.",
        code="STARTING_PLAYER_MOCK",
        accent="#22c55e",
        step="8 de 10",
        panel_title="Regra operacional",
        panel_items=(
            "Setup visual encerrado antes do player",
            "MPV principal nao disputa DRM/KMS",
            "Estado real ainda nao implementado em C2",
        ),
    ),
)


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
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != 0o700:
        path.chmod(0o700)


def redact_sensitive(value: str, *, max_len: int = 160) -> str:
    text = " ".join(value.split())
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub("[redacted]", text)
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "..."
    return text


def assert_clean_rendered_text(text: str) -> None:
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"sensitive pattern remained in rendered text: {pattern.pattern}")


def public_text(value: str, *, max_len: int = 160) -> str:
    text = redact_sensitive(value, max_len=max_len)
    assert_clean_rendered_text(text)
    return text


def svg_text_lines(
    text: str,
    *,
    x: int,
    y: int,
    size: int,
    fill: str,
    max_chars: int,
    line_gap: int,
    weight: int | None = None,
) -> str:
    lines = textwrap.wrap(public_text(text), width=max_chars) or [""]
    tspans = []
    for index, line in enumerate(lines[:4]):
        dy = 0 if index == 0 else line_gap
        tspans.append(f'<tspan x="{x}" dy="{dy}">{html.escape(line)}</tspan>')
    weight_attr = f' font-weight="{weight}"' if weight is not None else ""
    return (
        f'<text x="{x}" y="{y}" font-family="Arial, DejaVu Sans, sans-serif" '
        f'font-size="{size}" fill="{fill}"{weight_attr}>'
        + "".join(tspans)
        + "</text>"
    )


def pill(text: str, *, x: int, y: int, width: int, fill: str, stroke: str) -> str:
    return f"""
  <rect x="{x}" y="{y}" width="{width}" height="44" rx="8" fill="{fill}" stroke="{stroke}"/>
  <text x="{x + 18}" y="{y + 29}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" font-weight="700" fill="#f8fafc">{html.escape(public_text(text, max_len=64))}</text>"""


def field_box(label: str, value: str, note: str, *, x: int, y: int, width: int) -> str:
    return f"""
  <text x="{x}" y="{y}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" font-weight="700" fill="#94a3b8">{html.escape(public_text(label, max_len=48))}</text>
  <rect x="{x}" y="{y + 16}" width="{width}" height="58" rx="8" fill="#0f131c" stroke="#374151"/>
  <text x="{x + 20}" y="{y + 54}" font-family="Arial, DejaVu Sans Mono, monospace" font-size="22" fill="#f8fafc">{html.escape(public_text(value, max_len=80))}</text>
  {svg_text_lines(note, x=x, y=y + 102, size=16, fill="#94a3b8", max_chars=44, line_gap=22)}"""


def render_panel_items(items: tuple[str, ...], *, x: int, y: int, width: int) -> str:
    output = []
    for index, item in enumerate(items[:5]):
        item_y = y + index * 52
        output.append(
            f"""
  <circle cx="{x + 12}" cy="{item_y - 6}" r="5" fill="#38bdf8"/>
  {svg_text_lines(item, x=x + 32, y=item_y, size=18, fill="#d8dee9", max_chars=34, line_gap=24)}"""
        )
    return "".join(output)


def build_svg(screen: Screen) -> str:
    title = public_text(screen.title)
    message = public_text(screen.message)
    action = public_text(screen.action)
    code = public_text(screen.code, max_len=80)
    step = public_text(screen.step, max_len=48)
    panel_title = public_text(screen.panel_title, max_len=80)
    notice = public_text(MOCK_NOTICE, max_len=96)
    state_label = public_text(screen.state.replace("_password_", "_credential_"), max_len=80)
    accent = screen.accent

    field = ""
    if screen.field_label and screen.field_value and screen.field_note:
        field = field_box(
            screen.field_label,
            screen.field_value,
            screen.field_note,
            x=96,
            y=432,
            width=620,
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" role="img" aria-label="Dadooh C2 mock preview">
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="#101318"/>
  <rect x="0" y="0" width="{CANVAS_WIDTH}" height="10" fill="{accent}"/>
  <path d="M0 604 L1280 516 L1280 720 L0 720 Z" fill="#151923"/>

  <text x="72" y="76" font-family="Arial, DejaVu Sans, sans-serif" font-size="42" font-weight="700" fill="#f8fafc">Dadooh</text>
  <text x="72" y="110" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" fill="#94a3b8">{html.escape(DEVICE_LABEL)}</text>
  <rect x="826" y="55" width="356" height="48" rx="8" fill="#3a260c" stroke="#f59e0b"/>
  <text x="846" y="86" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" font-weight="700" fill="#fef3c7">{html.escape(notice)}</text>

  <rect x="72" y="138" width="700" height="454" rx="8" fill="#171b24" stroke="#2b3240"/>
  <rect x="72" y="138" width="8" height="454" rx="4" fill="{accent}"/>
  <text x="96" y="194" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" font-weight="700" fill="{accent}">C2 MOCK VISUAL</text>
  {svg_text_lines(title, x=96, y=270, size=52, fill="#f8fafc", max_chars=24, line_gap=58, weight=700)}
  {svg_text_lines(message, x=96, y=342, size=27, fill="#d8dee9", max_chars=42, line_gap=36)}
  {svg_text_lines(action, x=96, y=404, size=22, fill="#b6c2d2", max_chars=52, line_gap=30)}
  {field}
  {pill("Estado: " + state_label, x=96, y=612, width=330, fill="#111827", stroke="#374151")}
  <text x="456" y="641" font-family="Arial, DejaVu Sans Mono, monospace" font-size="22" font-weight="700" fill="{accent}">{html.escape(code)}</text>

  <rect x="824" y="138" width="384" height="454" rx="8" fill="#121620" stroke="#2b3240"/>
  <text x="858" y="190" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" font-weight="700" fill="{accent}">{html.escape(step)}</text>
  <text x="858" y="236" font-family="Arial, DejaVu Sans, sans-serif" font-size="30" font-weight="700" fill="#f8fafc">{html.escape(panel_title)}</text>
  {render_panel_items(screen.panel_items, x=858, y=292, width=300)}

  <text x="72" y="682" font-family="Arial, DejaVu Sans, sans-serif" font-size="16" fill="#7d8796">Preview local estatico. Sem rede, sem MPV, sem systemd, sem config real.</text>
</svg>
"""


def rendered_text_values(screen: Screen) -> tuple[str, ...]:
    values: list[str] = [
        DEVICE_LABEL,
        MOCK_NOTICE,
        screen.title,
        screen.message,
        screen.action,
        screen.code,
        screen.step,
        screen.panel_title,
        screen.state.replace("_password_", "_credential_"),
        "Preview local estatico. Sem rede, sem MPV, sem systemd, sem config real.",
    ]
    values.extend(screen.panel_items)
    if screen.field_label:
        values.append(screen.field_label)
    if screen.field_value:
        values.append(screen.field_value)
    if screen.field_note:
        values.append(screen.field_note)
    return tuple(values)


def assert_screen_text_is_clean(screen: Screen) -> None:
    for value in rendered_text_values(screen):
        assert_clean_rendered_text(public_text(value))


def write_file(path: pathlib.Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def screen_filename(index: int, screen: Screen) -> str:
    return f"{index:02d}-{screen.state}.svg"


def build_index(generated: list[tuple[Screen, pathlib.Path]]) -> str:
    lines = [
        "Dadooh C2 mock preview",
        "",
        "Mock visual. Nao altera rede nem salva configuracao.",
        "Gerado somente com dados ficticios.",
        "",
        "Arquivos:",
    ]
    for screen, path in generated:
        lines.append(f"- {screen.state}: {path.name}")
    lines.extend(
        [
            "",
            "Regras:",
            "- nao usa rede real",
            "- nao chama MPV, systemd ou nmcli",
            "- nao le config/status real",
            "- nao escreve em /data",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate static Dadooh C2 onboarding mock SVG previews."
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        out_dir = require_tmp_dir(args.out_dir)
        prepare_out_dir(out_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    generated: list[tuple[Screen, pathlib.Path]] = []
    for index, screen in enumerate(SCREENS, start=1):
        output = out_dir / screen_filename(index, screen)
        assert_screen_text_is_clean(screen)
        svg = build_svg(screen)
        write_file(output, svg)
        generated.append((screen, output))

    index_path = out_dir / "index.txt"
    write_file(index_path, build_index(generated))

    print(f"Generated {len(generated)} SVG previews under {out_dir}")
    for _, path in generated:
        print(path)
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
