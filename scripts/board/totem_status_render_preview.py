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
        "title": "Preparando o totem",
        "message": "A exibição começa automaticamente em instantes.",
        "hint": "Nenhuma ação é necessária.",
        "status": "Inicializando",
        "kind": "progress",
        "stage": 0,
        "accent": "#22d3ee",
    },
    "display_missing": {
        "title": "Tela não detectada",
        "message": "O totem está ligado, mas ainda não encontrou uma tela.",
        "hint": "Verifique o cabo HDMI e a energia da tela.",
        "status": "Aguardando tela",
        "kind": "action",
        "action_key": "HDMI",
        "action_label": "Verifique a conexão",
        "action_note": "Detecção automática",
        "accent": "#f59e0b",
    },
    "config_missing": {
        "title": "Vamos configurar este totem",
        "message": "A configuração leva poucos minutos.",
        "hint": "Segure F10 por 5 segundos para começar.",
        "status": "Configuração pendente",
        "kind": "action",
        "action_key": "F10",
        "action_label": "Segure por 5 segundos",
        "action_note": "Abertura automática",
        "accent": "#22d3ee",
    },
    "starting_player": {
        "title": "Preparando sua exibição",
        "message": "A exibição está iniciando com segurança.",
        "hint": "O conteúdo aparece automaticamente.",
        "status": "Iniciando exibição",
        "kind": "progress",
        "stage": 1,
        "accent": "#22d3ee",
    },
    "loading_content": {
        "title": "Carregando conteúdo",
        "message": "Estamos preparando as mídias para exibição.",
        "hint": "Isso pode levar alguns instantes.",
        "status": "Preparando conteúdo",
        "kind": "progress",
        "stage": 2,
        "accent": "#22d3ee",
    },
    "content_unavailable": {
        "title": "Conteúdo ainda não disponível",
        "message": "O totem continuará verificando automaticamente.",
        "hint": "Se a mensagem persistir, acione o suporte.",
        "status": "Tentando novamente",
        "kind": "recovery",
        "accent": "#f59e0b",
    },
    "player_running": {
        "title": "Totem em operação",
        "message": "A exibição foi iniciada.",
        "hint": "Nenhuma ação necessária.",
        "status": "Operação normal",
        "kind": "complete",
        "accent": "#22c55e",
    },
    "player_error": {
        "title": "Recuperando a exibição",
        "message": "A exibição será reiniciada automaticamente.",
        "hint": "Se a mensagem persistir, acione o suporte.",
        "status": "Recuperação automática",
        "kind": "recovery",
        "accent": "#f59e0b",
    },
    "maintenance_placeholder": {
        "title": "Modo de suporte",
        "message": "A exibição está pausada para manutenção autorizada.",
        "hint": "Aguarde a conclusão do atendimento.",
        "status": "Manutenção em andamento",
        "kind": "quiet",
        "accent": "#94a3b8",
    },
}

C17_2_VISUAL_SYSTEM_VERSION = "c17.2-appliance-ui.v1"
C25_VISIBLE_STATE_SYSTEM_VERSION = "c25-visible-state-ui.v1"
VISUAL = {
    "bg": "#090c10",
    "surface": "#12171d",
    "surface_raised": "#181e25",
    "surface_active": "#102a31",
    "footer": "#0d1116",
    "border": "#2a333d",
    "border_muted": "#3a4652",
    "text": "#f8fafc",
    "text_muted": "#cbd5e1",
    "text_dim": "#9aa4b2",
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


def wrapped_line_count(text: str, *, max_chars: int, max_lines: int = 3) -> int:
    return max(1, min(len(textwrap.wrap(text, width=max_chars) or [""]), max_lines))


def state_side_visual(preset: dict[str, object], *, x: int, y: int, width: int, height: int) -> str:
    accent = str(preset["accent"])
    kind = str(preset["kind"])
    status = html.escape(str(preset["status"]))
    parts = [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" '
        f'fill="{VISUAL["surface"]}" stroke="{VISUAL["border"]}"/>',
        f'<rect x="{x}" y="{y}" width="6" height="{height}" rx="3" fill="{accent}"/>',
    ]

    if kind == "action":
        action_key = html.escape(str(preset.get("action_key") or ""))
        action_label = html.escape(str(preset.get("action_label") or "Continuar"))
        action_note = html.escape(str(preset.get("action_note") or "O totem continua automaticamente"))
        parts.extend(
            [
                f'<text x="{x + 38}" y="{y + 58}" font-family="Arial, DejaVu Sans, sans-serif" '
                f'font-size="18" font-weight="700" fill="{VISUAL["text_dim"]}">PRÓXIMO PASSO</text>',
                f'<rect x="{x + 38}" y="{y + 104}" width="{width - 76}" height="128" rx="8" '
                f'fill="{VISUAL["surface_active"]}" stroke="{accent}" stroke-width="2"/>',
                f'<text x="{x + width // 2}" y="{y + 184}" font-family="Arial, DejaVu Sans, sans-serif" '
                f'font-size="46" font-weight="700" text-anchor="middle" fill="{VISUAL["text"]}">{action_key}</text>',
                f'<text x="{x + width // 2}" y="{y + 286}" font-family="Arial, DejaVu Sans, sans-serif" '
                f'font-size="24" font-weight="700" text-anchor="middle" fill="{VISUAL["text"]}">{action_label}</text>',
                f'<text x="{x + width // 2}" y="{y + 338}" font-family="Arial, DejaVu Sans, sans-serif" '
                f'font-size="19" text-anchor="middle" fill="{VISUAL["text_muted"]}">{action_note}</text>',
            ]
        )
    elif kind == "progress":
        stage = max(0, min(int(preset.get("stage") or 0), 2))
        labels = ("Sistema", "Exibição", "Conteúdo")
        parts.append(
            f'<text x="{x + 38}" y="{y + 58}" font-family="Arial, DejaVu Sans, sans-serif" '
            f'font-size="18" font-weight="700" fill="{VISUAL["text_dim"]}">PROGRESSO</text>'
        )
        for index, label in enumerate(labels):
            node_y = y + 124 + index * 92
            if index < len(labels) - 1:
                line_color = accent if index < stage else VISUAL["border_muted"]
                parts.append(
                    f'<line x1="{x + 66}" y1="{node_y + 18}" x2="{x + 66}" y2="{node_y + 74}" '
                    f'stroke="{line_color}" stroke-width="4"/>'
                )
            reached = index <= stage
            fill = accent if reached else VISUAL["surface_raised"]
            stroke = accent if reached else VISUAL["border_muted"]
            text_fill = VISUAL["text"] if reached else VISUAL["text_dim"]
            parts.extend(
                [
                    f'<circle cx="{x + 66}" cy="{node_y}" r="15" fill="{fill}" stroke="{stroke}" stroke-width="3"/>',
                    f'<text x="{x + 104}" y="{node_y + 8}" font-family="Arial, DejaVu Sans, sans-serif" '
                    f'font-size="24" font-weight="700" fill="{text_fill}">{label}</text>',
                ]
            )
        parts.extend(
            [
                f'<line x1="{x + 38}" y1="{y + 360}" x2="{x + width - 38}" y2="{y + 360}" stroke="{VISUAL["border"]}"/>',
                f'<text x="{x + 38}" y="{y + 410}" font-family="Arial, DejaVu Sans, sans-serif" '
                f'font-size="22" font-weight="700" fill="{accent}">{status}</text>',
            ]
        )
    elif kind == "complete":
        parts.extend(
            [
                f'<circle cx="{x + width // 2}" cy="{y + 176}" r="76" fill="{VISUAL["surface_active"]}" stroke="{accent}" stroke-width="4"/>',
                f'<circle cx="{x + width // 2}" cy="{y + 176}" r="34" fill="{accent}"/>',
                f'<text x="{x + width // 2}" y="{y + 306}" font-family="Arial, DejaVu Sans, sans-serif" '
                f'font-size="27" font-weight="700" text-anchor="middle" fill="{VISUAL["text"]}">{status}</text>',
                f'<text x="{x + width // 2}" y="{y + 350}" font-family="Arial, DejaVu Sans, sans-serif" '
                f'font-size="19" text-anchor="middle" fill="{VISUAL["text_muted"]}">Operação normal</text>',
            ]
        )
    else:
        recovery_label = "Recuperando" if kind == "recovery" else "Em suporte"
        parts.extend(
            [
                f'<circle cx="{x + width // 2}" cy="{y + 166}" r="78" fill="none" stroke="{VISUAL["border_muted"]}" stroke-width="8"/>',
                f'<circle cx="{x + width // 2}" cy="{y + 166}" r="78" fill="none" stroke="{accent}" stroke-width="8" '
                f'stroke-dasharray="116 374" stroke-linecap="round" transform="rotate(-90 {x + width // 2} {y + 166})"/>',
                f'<circle cx="{x + width // 2}" cy="{y + 166}" r="18" fill="{accent}"/>',
                f'<text x="{x + width // 2}" y="{y + 304}" font-family="Arial, DejaVu Sans, sans-serif" '
                f'font-size="25" font-weight="700" text-anchor="middle" fill="{VISUAL["text"]}">{recovery_label}</text>',
                f'<text x="{x + width // 2}" y="{y + 350}" font-family="Arial, DejaVu Sans, sans-serif" '
                f'font-size="19" text-anchor="middle" fill="{VISUAL["text_muted"]}">{status}</text>',
            ]
        )
    return "\n  ".join(parts)


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
    accent = str(preset["accent"])
    portrait = height > width
    if portrait:
        canvas_width = 720
        canvas_height = 1280
        margin_x = 48
        brand_y = 70
        main_y = 150
        side_x = margin_x
        side_y = 680
        side_width = canvas_width - (margin_x * 2)
        side_height = 442
        title_size = 48
        title_chars = 21
        title_gap = 54
        message_size = 27
        message_chars = 34
        message_gap = 37
        hint_size = 21
        hint_chars = 42
        hint_gap = 30
        message_base_offset = 150
        hint_base_offset = 68
    else:
        canvas_width = 1280
        canvas_height = 720
        margin_x = 72
        brand_y = 76
        main_y = 160
        side_x = 884
        side_y = 132
        side_width = canvas_width - side_x - margin_x
        side_height = 442
        title_size = 58
        title_chars = 24
        title_gap = 64
        message_size = 29
        message_chars = 39
        message_gap = 39
        hint_size = 22
        hint_chars = 50
        hint_gap = 32
        message_base_offset = 168
        hint_base_offset = 72
    main_x = margin_x
    footer_y = canvas_height - 70
    title = str(preset["title"])
    title_lines = wrapped_line_count(title, max_chars=title_chars, max_lines=2)
    message_lines = wrapped_line_count(message, max_chars=message_chars, max_lines=3)
    message_y = main_y + message_base_offset + (title_lines - 1) * title_gap
    hint_y = message_y + hint_base_offset + (message_lines - 1) * message_gap
    status = html.escape(str(preset["status"]))
    layout_mode = "portrait" if portrait else "landscape"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {canvas_width} {canvas_height}" role="img" aria-label="Dadooh: {html.escape(title)}" data-visual-system="{C25_VISIBLE_STATE_SYSTEM_VERSION}" data-layout-mode="{layout_mode}">
  <rect width="{canvas_width}" height="{canvas_height}" fill="{VISUAL["bg"]}"/>
  <rect x="0" y="0" width="{canvas_width}" height="8" fill="{accent}"/>
  <rect x="0" y="{canvas_height - 74}" width="{canvas_width}" height="74" fill="{VISUAL["footer"]}"/>
  <text x="{margin_x}" y="{brand_y}" font-family="Arial, DejaVu Sans, sans-serif" font-size="32" font-weight="700" fill="{VISUAL["text"]}">Dadooh</text>
  <line x1="{margin_x + 132}" y1="48" x2="{margin_x + 132}" y2="82" stroke="{VISUAL["border_muted"]}"/>
  <text x="{margin_x + 158}" y="{brand_y - 2}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" fill="{VISUAL["text_dim"]}">{html.escape(device_label)}</text>

  <text x="{main_x}" y="{main_y}" font-family="Arial, DejaVu Sans, sans-serif" font-size="19" font-weight="700" fill="{accent}">{status.upper()}</text>
  {svg_text_lines(title, x=main_x, y=main_y + 82, size=title_size, fill=VISUAL["text"], max_chars=title_chars, line_gap=title_gap, weight=700)}
  {svg_text_lines(message, x=main_x, y=message_y, size=message_size, fill=VISUAL["text_muted"], max_chars=message_chars, line_gap=message_gap)}
  {svg_text_lines(action_hint, x=main_x, y=hint_y, size=hint_size, fill=VISUAL["text_dim"], max_chars=hint_chars, line_gap=hint_gap)}
  <rect x="{main_x}" y="{hint_y + 58 if portrait else hint_y + 66}" width="96" height="5" rx="2" fill="{accent}"/>

  {state_side_visual(preset, x=side_x, y=side_y, width=side_width, height=side_height)}

  <text x="{margin_x}" y="{footer_y + 27}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" fill="{VISUAL["text_muted"]}">{status}</text>
  <text x="{canvas_width - margin_x}" y="{footer_y + 27}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" text-anchor="end" fill="{VISUAL["text_dim"]}">Dadooh</text>
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
    parser.add_argument("--device-label", default="Totem", help="Public device label.")
    parser.add_argument("--output", default="/tmp/totem-status-preview.svg", help="SVG output path under /tmp.")
    parser.add_argument("--width", type=positive_dimension, default=1280)
    parser.add_argument("--height", type=positive_dimension, default=720)
    parser.add_argument("--self-test", action="store_true", help="Run offline renderer self-tests and exit.")
    return parser.parse_args(argv)


def run_self_test() -> None:
    out = require_tmp_output("/tmp/dadooh-status-render-preview-self-test/config-missing.svg")
    out.parent.mkdir(parents=True, exist_ok=True)
    svg = build_svg(
        state="config_missing",
        message=sanitize_public_text("api_key=abc https://example.invalid/secret"),
        action_hint=STATE_PRESETS["config_missing"]["hint"],
        device_label=sanitize_public_text("Totem Dadooh environment_id=private"),
        width=1280,
        height=720,
    )
    out.write_text(svg, encoding="utf-8")
    out.chmod(0o600)
    text = out.read_text(encoding="utf-8")
    assert "Segure F10 por 5 segundos" in text
    assert "Vamos configurar este totem" in text
    assert "Segure por 5 segundos" in text
    assert "Abertura automática" in text
    display_svg = build_svg(
        state="display_missing",
        message=str(STATE_PRESETS["display_missing"]["message"]),
        action_hint=str(STATE_PRESETS["display_missing"]["hint"]),
        device_label="Totem",
        width=1280,
        height=720,
    )
    assert "Detecção automática" in display_svg
    assert "aguarda sua confirmação" not in display_svg
    assert C25_VISIBLE_STATE_SYSTEM_VERSION in text
    for state, preset in STATE_PRESETS.items():
        rendered = build_svg(
            state=state,
            message=str(preset["message"]),
            action_hint=str(preset["hint"]),
            device_label="Totem",
            width=1280,
            height=720,
        )
        assert str(preset["title"]) in rendered
        assert str(preset["status"]) in rendered
        for technical in ("STATUS DO TOTEM", "CÓDIGO PÚBLICO", "Sem dados privados"):
            assert technical not in rendered
        portrait_rendered = build_svg(
            state=state,
            message=str(preset["message"]),
            action_hint=str(preset["hint"]),
            device_label="Totem",
            width=720,
            height=1280,
        )
        assert 'viewBox="0 0 720 1280"' in portrait_rendered
        assert 'data-layout-mode="portrait"' in portrait_rendered
    for forbidden in ("api_key=abc", "example.invalid/secret", "environment_id=private"):
        assert forbidden not in text
    assert require_tmp_output(str(out)) == out
    for bad in ("/var/tmp/status.svg", "/tmp/status.txt"):
        try:
            require_tmp_output(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe output path accepted: {bad}")


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        try:
            run_self_test()
        except Exception:
            print("error: self-test failed", file=sys.stderr)
            return 1
        print("self-test: ok")
        return 0
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
