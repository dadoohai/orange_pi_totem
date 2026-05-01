#!/usr/bin/env python3
"""Generate a safe local SVG preview for the totem status screen.

This preview is intentionally non-invasive: it does not use network, MPV,
systemd, /dev/dri or any appliance status file. It only writes an SVG under
/tmp so the layout can be reviewed before launcher integration exists.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import pathlib
import re
import sys
import textwrap


STATE_PRESETS = {
    "booting": {
        "title": "Inicializando",
        "message": "O totem está preparando a exibição.",
        "hint": "Aguarde alguns instantes.",
        "status": "Sistema preparando exibição",
        "code": "BOOTING",
        "accent": "#38bdf8",
    },
    "display_missing": {
        "title": "Tela não detectada",
        "message": "A exibição ainda não encontrou uma tela conectada.",
        "hint": "Verifique o cabo HDMI e a energia da tela.",
        "status": "Player aguardando tela",
        "code": "DISPLAY_MISSING",
        "accent": "#f59e0b",
    },
    "config_missing": {
        "title": "Configuração pendente",
        "message": "Este totem ainda não foi ativado.",
        "hint": "Acione a equipe responsável para concluir a configuração.",
        "status": "Player parado com segurança",
        "code": "CONFIG_MISSING",
        "accent": "#f97316",
    },
    "starting_player": {
        "title": "Iniciando exibição",
        "message": "O conteúdo será exibido em instantes.",
        "hint": "Aguarde alguns instantes.",
        "status": "Player iniciando",
        "code": "STARTING_PLAYER",
        "accent": "#22c55e",
    },
    "player_running": {
        "title": "Exibição em andamento",
        "message": "O player está ativo.",
        "hint": "Nenhuma ação necessária.",
        "status": "Player em execução",
        "code": "PLAYER_RUNNING",
        "accent": "#22c55e",
    },
    "player_error": {
        "title": "Exibição indisponível",
        "message": "O conteúdo não pôde ser exibido agora.",
        "hint": "O sistema tentará reiniciar automaticamente.",
        "status": "Player em recuperação",
        "code": "PLAYER_EXITED",
        "accent": "#ef4444",
    },
    "maintenance_placeholder": {
        "title": "Manutenção local",
        "message": "Área reservada para suporte autorizado.",
        "hint": "Nenhum comando operacional está disponível nesta fase.",
        "status": "Modo de manutenção reservado",
        "code": "MAINTENANCE_PLACEHOLDER",
        "accent": "#94a3b8",
    },
}

SENSITIVE_PATTERNS = (
    re.compile(r"https?://\S+", re.IGNORECASE),
    re.compile(r"\b(api[_-]?key|token|secret|password|senha)\b\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b(environment[_-]?id|station[_-]?id)\b\s*[:=]\s*\S+", re.IGNORECASE),
)


def utc_timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sanitize_public_text(value: str, *, max_len: int = 96) -> str:
    text = " ".join(value.split())
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub("[redacted]", text)
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "..."
    return text


def require_tmp_output(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    if path.suffix.lower() != ".svg":
        raise ValueError("output must use .svg extension")

    resolved = path.resolve()
    tmp_root = pathlib.Path("/tmp").resolve()
    try:
        resolved.relative_to(tmp_root)
    except ValueError as exc:
        raise ValueError("output must be under /tmp") from exc

    if resolved == tmp_root:
        raise ValueError("output must be a file path under /tmp")

    return resolved


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
    lines = textwrap.wrap(text, width=max_chars) or [""]
    tspans = []
    for index, line in enumerate(lines[:3]):
        dy = 0 if index == 0 else line_gap
        tspans.append(
            f'<tspan x="{x}" dy="{dy}">{html.escape(line)}</tspan>'
        )
    weight_attr = f' font-weight="{weight}"' if weight is not None else ""
    return (
        f'<text x="{x}" y="{y}" font-family="Arial, DejaVu Sans, sans-serif" '
        f'font-size="{size}" fill="{fill}"{weight_attr}>' + "".join(tspans) + "</text>"
    )


def badge(text: str, *, x: int, y: int, width: int, fill: str, stroke: str, text_fill: str) -> str:
    return f"""
  <rect x="{x}" y="{y}" width="{width}" height="48" rx="8" fill="{fill}" stroke="{stroke}"/>
  <text x="{x + 24}" y="{y + 31}" font-family="Arial, DejaVu Sans, sans-serif" font-size="20" font-weight="700" fill="{text_fill}">{html.escape(text)}</text>"""


def build_svg(
    *,
    state: str,
    message: str,
    action_hint: str,
    device_label: str,
    width: int,
    height: int,
) -> str:
    preset = STATE_PRESETS[state]
    accent = preset["accent"]
    now = utc_timestamp()
    canvas_width = 1280
    canvas_height = 720
    margin_x = 72
    brand_y = 76
    main_x = 72
    main_y = 136
    main_width = 704
    main_height = 438
    side_x = 824
    side_y = main_y
    side_width = canvas_width - side_x - margin_x
    side_height = main_height
    footer_y = canvas_height - 42
    code = preset["code"]
    status = preset["status"]

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {canvas_width} {canvas_height}" role="img" aria-label="Dadooh status preview">
  <rect width="{canvas_width}" height="{canvas_height}" fill="#101318"/>
  <rect x="0" y="0" width="{canvas_width}" height="10" fill="{accent}"/>
  <rect x="0" y="10" width="{canvas_width}" height="{canvas_height - 10}" fill="#101318"/>
  <path d="M0 {canvas_height - 118} L{canvas_width} {canvas_height - 196} L{canvas_width} {canvas_height} L0 {canvas_height} Z" fill="#151923"/>
  <text x="{margin_x}" y="{brand_y}" font-family="Arial, DejaVu Sans, sans-serif" font-size="42" font-weight="700" fill="#f8fafc">Dadooh</text>
  <text x="{margin_x}" y="{brand_y + 34}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" fill="#94a3b8">{html.escape(device_label)}</text>

  <rect x="{main_x}" y="{main_y}" width="{main_width}" height="{main_height}" rx="8" fill="#171b24" stroke="#2b3240"/>
  <rect x="{main_x}" y="{main_y}" width="8" height="{main_height}" rx="4" fill="{accent}"/>
  <text x="{main_x + 40}" y="{main_y + 78}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" font-weight="700" fill="{accent}">STATUS DO TOTEM</text>
  {svg_text_lines(preset["title"], x=main_x + 40, y=main_y + 154, size=56, fill="#f8fafc", max_chars=22, line_gap=60, weight=700)}
  {svg_text_lines(message, x=main_x + 40, y=main_y + 226, size=30, fill="#d8dee9", max_chars=37, line_gap=40)}
  {svg_text_lines(action_hint, x=main_x + 40, y=main_y + 302, size=24, fill="#b6c2d2", max_chars=48, line_gap=34)}
  {badge(status, x=main_x + 40, y=main_y + 348, width=360, fill="#111827", stroke="#374151", text_fill="#f8fafc")}
  <text x="{main_x + 40}" y="{main_y + 430}" font-family="Arial, DejaVu Sans, sans-serif" font-size="16" font-weight="700" fill="#94a3b8">CÓDIGO PÚBLICO</text>
  <text x="{main_x + 218}" y="{main_y + 432}" font-family="Arial, DejaVu Sans Mono, monospace" font-size="30" font-weight="700" fill="{accent}">{html.escape(code)}</text>

  <rect x="{side_x}" y="{side_y}" width="{side_width}" height="{side_height}" rx="8" fill="#121620" stroke="#2b3240"/>
  <text x="{side_x + 34}" y="{side_y + 62}" font-family="Arial, DejaVu Sans, sans-serif" font-size="26" font-weight="700" fill="#f8fafc">Configuração assistida</text>
  {svg_text_lines("Área reservada para a próxima fase.", x=side_x + 34, y=side_y + 98, size=18, fill="#94a3b8", max_chars=31, line_gap=26)}
  <rect x="{side_x + 78}" y="{side_y + 136}" width="212" height="212" rx="8" fill="#0f131c" stroke="{accent}" stroke-width="3" stroke-dasharray="12 12"/>
  <text x="{side_x + 122}" y="{side_y + 238}" font-family="Arial, DejaVu Sans, sans-serif" font-size="34" font-weight="700" fill="#f8fafc">Em breve</text>
  <text x="{side_x + 104}" y="{side_y + 278}" font-family="Arial, DejaVu Sans, sans-serif" font-size="17" fill="#b6c2d2">Sem QR ativo agora</text>
  <line x1="{side_x + 34}" y1="{side_y + 382}" x2="{side_x + side_width - 34}" y2="{side_y + 382}" stroke="#2b3240"/>
  {svg_text_lines("A configuração será guiada sem expor dados privados.", x=side_x + 34, y=side_y + 420, size=18, fill="#cbd5e1", max_chars=31, line_gap=26)}

  <text x="{margin_x}" y="{footer_y}" font-family="Arial, DejaVu Sans, sans-serif" font-size="17" fill="#7d8796">Estado público: {html.escape(state)} | Atualizado: {html.escape(now)}</text>
</svg>
"""


def positive_dimension(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if number < 320 or number > 3840:
        raise argparse.ArgumentTypeError("must be between 320 and 3840")
    return number


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a local Dadooh status SVG preview.")
    parser.add_argument("--state", choices=sorted(STATE_PRESETS), default="booting")
    parser.add_argument("--message", help="Public message to render. Do not pass secrets.")
    parser.add_argument("--action-hint", help="Public action hint to render. Do not pass secrets.")
    parser.add_argument("--device-label", default="Totem Dadooh", help="Public device label.")
    parser.add_argument("--output", default="/tmp/totem-status-preview.svg", help="SVG output path under /tmp.")
    parser.add_argument("--width", type=positive_dimension, default=1280)
    parser.add_argument("--height", type=positive_dimension, default=720)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    preset = STATE_PRESETS[args.state]
    message = sanitize_public_text(args.message or preset["message"])
    action_hint = sanitize_public_text(args.action_hint or preset["hint"])
    device_label = sanitize_public_text(args.device_label, max_len=48)

    try:
        output = require_tmp_output(args.output)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        build_svg(
            state=args.state,
            message=message,
            action_hint=action_hint,
            device_label=device_label,
            width=args.width,
            height=args.height,
        ),
        encoding="utf-8",
    )
    output.chmod(0o600)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
