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
        "label": "Inicializando",
        "message": "Inicializando totem",
        "hint": "Aguarde alguns instantes.",
        "accent": "#2563eb",
    },
    "display_missing": {
        "label": "Tela nao detectada",
        "message": "Tela nao detectada",
        "hint": "Verifique o cabo HDMI e a energia da tela.",
        "accent": "#d97706",
    },
    "config_missing": {
        "label": "Configuracao pendente",
        "message": "Configuracao pendente",
        "hint": "Acione a manutencao autorizada para concluir a ativacao.",
        "accent": "#7c3aed",
    },
    "starting_player": {
        "label": "Iniciando exibicao",
        "message": "Iniciando exibicao",
        "hint": "Aguarde alguns instantes.",
        "accent": "#059669",
    },
    "player_running": {
        "label": "Exibicao em andamento",
        "message": "Exibicao em andamento",
        "hint": "Nenhuma acao necessaria.",
        "accent": "#16a34a",
    },
    "player_error": {
        "label": "Exibicao indisponivel",
        "message": "Exibicao temporariamente indisponivel",
        "hint": "O sistema tentara reiniciar automaticamente.",
        "accent": "#dc2626",
    },
    "maintenance_placeholder": {
        "label": "Manutencao",
        "message": "Manutencao local",
        "hint": "Modo reservado para fase futura.",
        "accent": "#475569",
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


def svg_text_lines(text: str, *, x: int, y: int, size: int, fill: str, max_chars: int, line_gap: int) -> str:
    lines = textwrap.wrap(text, width=max_chars) or [""]
    tspans = []
    for index, line in enumerate(lines[:3]):
        dy = 0 if index == 0 else line_gap
        tspans.append(
            f'<tspan x="{x}" dy="{dy}">{html.escape(line)}</tspan>'
        )
    return (
        f'<text x="{x}" y="{y}" font-family="Inter, Arial, sans-serif" '
        f'font-size="{size}" fill="{fill}">' + "".join(tspans) + "</text>"
    )


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
    margin_x = max(72, width // 14)
    brand_y = max(90, height // 7)
    state_y = max(260, height // 2 - 95)
    message_y = state_y + 98
    hint_y = message_y + 76
    footer_y = height - 72
    panel_width = width - margin_x * 2

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Dadooh status preview">
  <rect width="{width}" height="{height}" fill="#f8fafc"/>
  <rect x="0" y="0" width="{width}" height="18" fill="{accent}"/>
  <circle cx="{margin_x + 34}" cy="{brand_y - 14}" r="24" fill="{accent}"/>
  <text x="{margin_x + 76}" y="{brand_y}" font-family="Inter, Arial, sans-serif" font-size="42" font-weight="700" fill="#0f172a">Dadooh</text>
  <text x="{margin_x + 78}" y="{brand_y + 34}" font-family="Inter, Arial, sans-serif" font-size="20" fill="#475569">{html.escape(device_label)}</text>
  <rect x="{margin_x}" y="{state_y - 62}" width="{panel_width}" height="198" rx="8" fill="#ffffff" stroke="#cbd5e1"/>
  <text x="{margin_x + 42}" y="{state_y}" font-family="Inter, Arial, sans-serif" font-size="30" font-weight="700" fill="{accent}">{html.escape(preset["label"])}</text>
  {svg_text_lines(message, x=margin_x + 42, y=message_y, size=54, fill="#0f172a", max_chars=31, line_gap=58)}
  {svg_text_lines(action_hint, x=margin_x + 42, y=hint_y, size=25, fill="#334155", max_chars=62, line_gap=34)}
  <text x="{margin_x}" y="{footer_y}" font-family="Inter, Arial, sans-serif" font-size="18" fill="#64748b">Estado: {html.escape(state)} | Atualizado: {html.escape(now)}</text>
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
