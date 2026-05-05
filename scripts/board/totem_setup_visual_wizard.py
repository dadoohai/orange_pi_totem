#!/usr/bin/env python3
"""C9.9 visual local setup wizard for HDMI + keyboard.

The visual wizard renders product screens as private SVG files under /tmp and
uses MPV/DRM only as a temporary local renderer. It keeps the C9.8 Wi-Fi
adapter and C5.1 candidate handoff, and does not read/write real config or call
the writer.
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import mmap
import os
import pathlib
import re
import select
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import termios
import tempfile
import textwrap
import time
import tty
from dataclasses import dataclass
from typing import Any


sys.dont_write_bytecode = True

import totem_config_contract_validate as contract
import totem_setup_minimal_server as setup
import totem_wifi_nm_adapter as wifi_adapter


SCHEMA_VERSION = "dadooh-c9.9-visual-wizard-local.v1"
SETUP_SOURCE = "c9.9-visual-wizard-local"
INTERFACE_MODE = "local_visual_mpv_drm_keyboard_controlled"
DEFAULT_OUT_DIR = "/tmp/dadooh-c9-9-visual-wizard"
DEFAULT_WIFI_SECRETS_DIR = "/tmp/dadooh-c9-9-visual-wifi-secrets"
WIFI_APPLY_DIRNAME = "wifi-persistent"
WIFI_TIMEOUT_SEC = 45
WIFI_PERSISTENT_PROFILE_NAME = wifi_adapter.DEFAULT_PERSISTENT_PROFILE_NAME
ADAPTER_SCRIPT = pathlib.Path(__file__).with_name("totem_wifi_nm_adapter.py")
PRESENT_SETTLE_SEC = float(os.environ.get("TOTEM_VISUAL_WIZARD_PRESENT_SETTLE_SEC", "0.18"))
RESTART_MPV_PER_SCREEN = os.environ.get("TOTEM_VISUAL_WIZARD_RESTART_MPV_PER_SCREEN", "1") != "0"
MPV_VIDEO_MODE = os.environ.get("TOTEM_VISUAL_WIZARD_MPV_VIDEO_MODE", "drm").strip().lower()
DOUBLE_LOAD_PER_SCREEN = os.environ.get("TOTEM_VISUAL_WIZARD_DOUBLE_LOAD_PER_SCREEN", "1") != "0"
RENDERER_MODE = os.environ.get("TOTEM_VISUAL_WIZARD_RENDERER", "framebuffer").strip().lower()
PSF_FONT_PATH = os.environ.get("TOTEM_VISUAL_WIZARD_PSF_FONT", "/usr/share/consolefonts/Lat15-Fixed18.psf.gz")

LANDSCAPE_CANVAS_WIDTH = 1280
LANDSCAPE_CANVAS_HEIGHT = 720
PORTRAIT_CANVAS_WIDTH = 720
PORTRAIT_CANVAS_HEIGHT = 1280
CANVAS_WIDTH = LANDSCAPE_CANVAS_WIDTH
CANVAS_HEIGHT = LANDSCAPE_CANVAS_HEIGHT
BRAND = "Dadooh"
TITLE = "Configuracao do Totem"
STEPS = ("Tela", "Conexao", "Ambiente", "Revisao", "Concluir")

CANDIDATE_FILENAME = "config.candidate.json"
STATUS_FILENAME = "setup-status.json"
SUMMARY_FILENAME = "summary.txt"
CANCELLED_FILENAME = "setup-cancelled.json"
FAILED_FILENAME = "setup-failed.json"
ORIENTATION_FILENAME = "orientation.json"

SENSITIVE_MARKERS = (
    "FAKE-STORE-WIFI",
    "fake-password",
    "fake-psk-value",
    "192.0.2.44",
    "192.0.2.1",
    "203.0.113.53",
    "aa:bb:cc:dd:ee:ff",
    "11:22:33:44:55:66",
    "fake-hostname",
    "Fake product wifi",
    "fake-uuid-value",
    "fake-token-value",
    "fake-api-key",
    setup.SAFE_PLACEHOLDER_API_KEY,
    setup.SAFE_PLACEHOLDER_API_URL,
)

ATTR_RE = re.compile(r'([a-zA-Z_:][\w:.-]*)="([^"]*)"')
RECT_RE = re.compile(r"<rect\b([^>]*)/?>", re.IGNORECASE)
TEXT_RE = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.IGNORECASE | re.DOTALL)
TSPAN_RE = re.compile(r"<tspan\b([^>]*)>(.*?)</tspan>", re.IGNORECASE | re.DOTALL)
SVG_RE = re.compile(r"<svg\b([^>]*)>", re.IGNORECASE)


class VisualWizardAbort(RuntimeError):
    """Raised when the operator intentionally cancels the visual setup."""


class VisualWizardError(RuntimeError):
    """Public-safe visual wizard error."""


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    description: str


@dataclass(frozen=True)
class ScreenLayout:
    rotation_deg: int
    width: int
    height: int
    mode: str
    note: str
    margin_x: int

    @property
    def portrait(self) -> bool:
        return self.mode == "portrait"


def normalize_rotation_deg(value: int | str) -> int:
    try:
        rotation = int(value) % 360
    except (TypeError, ValueError):
        rotation = 0
    if rotation not in {0, 90, 180, 270}:
        return 0
    return rotation


def screen_layout(layout_rotation_deg: int = 0) -> ScreenLayout:
    rotation = normalize_rotation_deg(layout_rotation_deg)
    if rotation in {90, 270}:
        note = "Layout retrato para direita" if rotation == 90 else "Layout retrato para esquerda"
        return ScreenLayout(rotation, PORTRAIT_CANVAS_WIDTH, PORTRAIT_CANVAS_HEIGHT, "portrait", note, 56)
    note = "Layout invertido" if rotation == 180 else "Layout paisagem"
    return ScreenLayout(rotation, LANDSCAPE_CANVAS_WIDTH, LANDSCAPE_CANVAS_HEIGHT, "landscape", note, 96)


NETWORK_OPTIONS = (
    Option(
        "configured_wifi",
        "Usar Wi-Fi ja configurado",
        "Usa o perfil dedicado ja validado neste totem.",
    ),
    Option(
        "wifi_select",
        "Selecionar rede Wi-Fi",
        "Escolhe a rede em lista local e mantem perfil dedicado.",
    ),
    Option(
        "bench_mock",
        "Continuar em modo de bancada",
        "Segue sem nova alteracao de rede.",
    ),
)

DISPLAY_OPTIONS = (
    {
        "key": "landscape",
        "label": "Paisagem",
        "description": "Topo para cima.",
        "rotation_deg": 0,
    },
    {
        "key": "portrait_right",
        "label": "Retrato para direita",
        "description": "Topo vira para a direita.",
        "rotation_deg": 90,
    },
    {
        "key": "portrait_left",
        "label": "Retrato para esquerda",
        "description": "Topo vira para a esquerda.",
        "rotation_deg": 270,
    },
    {
        "key": "landscape_inverted",
        "label": "Invertido",
        "description": "Topo fica embaixo.",
        "rotation_deg": 180,
    },
)
DISPLAY_OPTION_BY_KEY = {str(item["key"]): item for item in DISPLAY_OPTIONS}


def utc_timestamp() -> str:
    return setup.utc_timestamp()


def file_mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def require_tmp_dir(raw_path: str) -> pathlib.Path:
    return setup.require_tmp_dir(raw_path)


def prepare_private_dir(path: pathlib.Path) -> None:
    setup.prepare_out_dir(path)


def atomic_write_private_text(path: pathlib.Path, content: str, out_dir: pathlib.Path) -> None:
    setup.atomic_write_private_text(path, content, out_dir)


def atomic_write_private_json(path: pathlib.Path, value: dict[str, Any], out_dir: pathlib.Path) -> None:
    setup.atomic_write_private_json(path, value, out_dir)


def escape_text(value: Any) -> str:
    return html.escape(str(value), quote=True)


def parse_attrs(raw_attrs: str) -> dict[str, str]:
    return {key: value for key, value in ATTR_RE.findall(raw_attrs)}


def parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_int(value: str | None, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def parse_color(value: str | None) -> tuple[int, int, int] | None:
    if not value or not value.startswith("#") or len(value) != 7:
        return None
    try:
        return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
    except ValueError:
        return None


def wrap_text(value: str, width: int, max_lines: int) -> list[str]:
    lines = textwrap.wrap(" ".join(value.split()), width=width) or [""]
    return lines[:max_lines]


def svg_lines(
    value: str,
    *,
    x: int,
    y: int,
    size: int,
    fill: str,
    width: int,
    line_gap: int,
    max_lines: int = 3,
    weight: int | None = None,
) -> str:
    tspans = []
    for index, line in enumerate(wrap_text(value, width, max_lines)):
        dy = 0 if index == 0 else line_gap
        tspans.append(f'<tspan x="{x}" dy="{dy}">{escape_text(line)}</tspan>')
    weight_attr = f' font-weight="{weight}"' if weight is not None else ""
    return (
        f'<text x="{x}" y="{y}" font-family="Arial, DejaVu Sans, sans-serif" '
        f'font-size="{size}" fill="{fill}"{weight_attr}>'
        + "".join(tspans)
        + "</text>"
    )


def step_indicator(active_step: int, *, layout_rotation_deg: int = 0) -> str:
    parts = []
    layout = screen_layout(layout_rotation_deg)
    x = 48 if layout.portrait else 86
    y = 96
    for index, step in enumerate(STEPS):
        active = index == active_step
        fill = "#ecfeff" if active else "#1f2937"
        stroke = "#0891b2" if active else "#334155"
        text_fill = "#0f172a" if active else "#cbd5e1"
        width = 116 if layout.portrait else (180 if index in {0, 4} else 176)
        label = step if not layout.portrait else step[:7]
        font_size = 14 if layout.portrait else 17
        parts.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="44" rx="8" fill="{fill}" stroke="{stroke}"/>'
            f'<text x="{x + 13}" y="{y + 29}" font-family="Arial, DejaVu Sans, sans-serif" '
            f'font-size="{font_size}" font-weight="700" fill="{text_fill}">{index + 1}. {escape_text(label)}</text>'
        )
        x += width + (8 if layout.portrait else 14)
    return "\n  ".join(parts)


def option_cards(options: list[Option], selected_index: int, *, layout_rotation_deg: int = 0) -> str:
    parts = []
    layout = screen_layout(layout_rotation_deg)
    x = layout.margin_x
    y = 354 if layout.portrait else 262
    card_width = layout.width - (layout.margin_x * 2) if layout.portrait else 760
    card_height = 98 if layout.portrait else 82
    label_width = 31 if layout.portrait else 34
    description_width = 47 if layout.portrait else 54
    for index, option in enumerate(options[:5]):
        active = index == selected_index
        fill = "#f8fafc" if active else "#182130"
        stroke = "#06b6d4" if active else "#334155"
        title_fill = "#111827" if active else "#f8fafc"
        body_fill = "#334155" if active else "#cbd5e1"
        marker_fill = "#0891b2" if active else "#475569"
        parts.append(
            f'<rect x="{x}" y="{y}" width="{card_width}" height="{card_height}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
            f'<circle cx="{x + 36}" cy="{y + 48}" r="18" fill="{marker_fill}"/>'
            f'<text x="{x + 30}" y="{y + 55}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" '
            f'font-weight="700" fill="#ffffff">{escape_text(">" if active else "")}</text>'
            f'{svg_lines(option.label, x=x + 72, y=y + 37, size=23, fill=title_fill, width=label_width, line_gap=28, max_lines=1, weight=700)}'
            f'{svg_lines(option.description, x=x + 72, y=y + 68, size=17, fill=body_fill, width=description_width, line_gap=22, max_lines=1)}'
        )
        y += card_height + 14
    return "\n  ".join(parts)


def info_panel(
    items: list[str],
    *,
    title: str = "Nesta etapa",
    layout_rotation_deg: int = 0,
    panel_y: int | None = None,
) -> str:
    if not items:
        return ""
    layout = screen_layout(layout_rotation_deg)
    panel_x = layout.margin_x if layout.portrait else 888
    panel_width = layout.width - (layout.margin_x * 2) if layout.portrait else 300
    panel_y = panel_y if panel_y is not None else (920 if layout.portrait else 220)
    panel_height = min(300 if layout.portrait else 330, max(190, layout.height - panel_y - 104))
    text_width = 50 if layout.portrait else 30
    y = panel_y + 58
    bullet_parts = []
    for item in items[:5]:
        bullet_parts.append(
            f'<circle cx="{panel_x + 36}" cy="{y - 6}" r="5" fill="#06b6d4"/>'
            f'{svg_lines(item, x=panel_x + 56, y=y, size=17, fill="#cbd5e1", width=text_width, line_gap=24, max_lines=2)}'
        )
        y += 54 if layout.portrait else 66
    return f"""
  <rect x="{panel_x}" y="{panel_y}" width="{panel_width}" height="{panel_height}" rx="8" fill="#111827" stroke="#334155"/>
  <text x="{panel_x + 32}" y="{panel_y + 40}" font-family="Arial, DejaVu Sans, sans-serif" font-size="24" font-weight="700" fill="#f8fafc">{escape_text(title)}</text>
  {' '.join(bullet_parts)}
"""


def field_panel(label: str, value_hint: str, note: str, *, layout_rotation_deg: int = 0) -> str:
    layout = screen_layout(layout_rotation_deg)
    panel_x = layout.margin_x
    panel_y = 390 if layout.portrait else 300
    panel_width = layout.width - (layout.margin_x * 2) if layout.portrait else 760
    text_width = 40 if layout.portrait else 44
    value_svg = svg_lines(
        value_hint,
        x=panel_x + 36,
        y=panel_y + 92,
        size=26,
        fill="#111827",
        width=text_width,
        line_gap=34,
        max_lines=2,
        weight=700,
    )
    return f"""
  <rect x="{panel_x}" y="{panel_y}" width="{panel_width}" height="142" rx="8" fill="#f8fafc" stroke="#06b6d4" stroke-width="2"/>
  <text x="{panel_x + 36}" y="{panel_y + 46}" font-family="Arial, DejaVu Sans, sans-serif" font-size="20" font-weight="700" fill="#0f172a">{escape_text(label)}</text>
  {value_svg}
  <text x="{panel_x + 36}" y="{panel_y + 174}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" fill="#475569">{escape_text(note)}</text>
"""


def footer_text(text: str, *, layout_rotation_deg: int = 0) -> str:
    layout = screen_layout(layout_rotation_deg)
    return (
        f'<rect x="0" y="{layout.height - 70}" width="{layout.width}" height="70" fill="#0b1120"/>'
        f'<text x="{layout.margin_x}" y="{layout.height - 28}" font-family="Arial, DejaVu Sans, sans-serif" '
        f'font-size="20" fill="#dbeafe">{escape_text(text)}</text>'
    )


def rect_svg(x: int, y: int, width: int, height: int, fill: str, *, rx: int = 0) -> str:
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{rx}" fill="{fill}"/>'


def rotate_rect(rect: tuple[int, int, int, int], rotation_deg: int, base_w: int, base_h: int) -> tuple[int, int, int, int]:
    x, y, width, height = rect
    if rotation_deg == 0:
        return rect
    if rotation_deg == 180:
        return base_w - x - width, base_h - y - height, width, height
    if rotation_deg == 90:
        return base_h - y - height, x, height, width
    if rotation_deg == 270:
        return y, base_w - x - width, height, width
    return rect


BLOCK_FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
}


def block_word_marker(value: str, rotation_deg: int, *, x: int, y: int, scale: int = 3) -> str:
    letters = [char for char in value.upper() if char in BLOCK_FONT]
    glyph_w = 5
    glyph_h = 7
    gap = 1
    base_w = max(1, len(letters) * glyph_w + max(0, len(letters) - 1) * gap)
    base_h = glyph_h
    base_rects: list[tuple[int, int, int, int]] = []
    cursor_x = 0
    for char in letters:
        for row_y, row in enumerate(BLOCK_FONT[char]):
            for col_x, bit in enumerate(row):
                if bit == "1":
                    base_rects.append((cursor_x + col_x, row_y, 1, 1))
        cursor_x += glyph_w + gap
    rotated_w, rotated_h = (base_h, base_w) if rotation_deg in {90, 270} else (base_w, base_h)
    origin_x = x - (rotated_w * scale) // 2
    origin_y = y - (rotated_h * scale) // 2
    parts = []
    for rect in base_rects:
        rx, ry, rw, rh = rotate_rect(rect, rotation_deg, base_w, base_h)
        parts.append(rect_svg(origin_x + rx * scale, origin_y + ry * scale, rw * scale, rh * scale, "#f8fafc", rx=1))
    return "\n    ".join(parts)


def orientation_preview(
    rotation_key: str,
    *,
    x: int | None = None,
    y: int | None = None,
    layout_rotation_deg: int = 0,
) -> str:
    rotation = resolve_display_selection(rotation_key)
    rotation_deg = int(rotation["rotation_deg"])
    layout = screen_layout(layout_rotation_deg)
    is_portrait = rotation_deg in {90, 270}
    outer_w = 116 if is_portrait else 176
    outer_h = 176 if is_portrait else 116
    if x is None:
        x = (layout.width - outer_w) // 2 if layout.portrait else 918
    if y is None:
        y = 690 if layout.portrait else 300
    inner_w = outer_w - 28
    inner_h = outer_h - 28
    marker = {
        0: (x + 14, y + 14, inner_w, 12),
        90: (x + outer_w - 26, y + 14, 12, inner_h),
        270: (x + 14, y + 14, 12, inner_h),
        180: (x + 14, y + outer_h - 26, inner_w, 12),
    }[rotation_deg]
    label_y = y + outer_h + 42
    word = block_word_marker("DADOOH", rotation_deg, x=x + outer_w // 2, y=y + outer_h // 2 + 8, scale=2)
    marker_x, marker_y, marker_w, marker_h = marker
    return f"""
  <g id="orientation-preview">
    <rect x="{x - 30}" y="{y - 54}" width="292" height="286" rx="8" fill="#111827" stroke="#334155"/>
    <text x="{x}" y="{y - 20}" font-family="Arial, DejaVu Sans, sans-serif" font-size="22" font-weight="700" fill="#f8fafc">Preview</text>
    <rect x="{x}" y="{y}" width="{outer_w}" height="{outer_h}" rx="12" fill="#e0f2fe" stroke="#06b6d4" stroke-width="4"/>
    <rect x="{x + 14}" y="{y + 14}" width="{inner_w}" height="{inner_h}" rx="8" fill="#0f172a"/>
    <rect x="{marker_x}" y="{marker_y}" width="{marker_w}" height="{marker_h}" rx="4" fill="#22c55e"/>
    {word}
    <text x="{x}" y="{label_y}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" fill="#cbd5e1">{escape_text(rotation['label'])}</text>
  </g>
"""


def build_screen_svg(
    *,
    active_step: int,
    title: str,
    subtitle: str,
    footer: str,
    options: list[Option] | None = None,
    selected_index: int = 0,
    field_label: str | None = None,
    field_value_hint: str = "",
    field_note: str = "",
    panel_title: str = "Nesta etapa",
    panel_items: list[str] | None = None,
    extra_svg: str = "",
    accent: str = "#06b6d4",
    layout_rotation_deg: int = 0,
) -> str:
    layout = screen_layout(layout_rotation_deg)
    options_svg = option_cards(options, selected_index, layout_rotation_deg=layout_rotation_deg) if options else ""
    field_svg = (
        field_panel(field_label, field_value_hint, field_note, layout_rotation_deg=layout_rotation_deg)
        if field_label is not None
        else ""
    )
    if layout.portrait:
        if field_label is not None:
            panel_y = 610
        elif extra_svg:
            panel_y = 960
        else:
            panel_y = 930 if options and len(options) >= 5 else 740
        title_y = 220
        subtitle_y = 258
        subtitle_width = 46
        note_x = layout.margin_x
        note_y = 162
    else:
        panel_y = 220
        title_y = 200
        subtitle_y = 236
        subtitle_width = 62
        note_x = 1030
        note_y = 58
    panel_svg = info_panel(
        panel_items or [],
        title=panel_title,
        layout_rotation_deg=layout_rotation_deg,
        panel_y=panel_y,
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" data-display-rotation-deg="{layout.rotation_deg}" data-layout-mode="{layout.mode}" role="img" aria-label="Dadooh setup visual wizard">
  <rect width="{layout.width}" height="{layout.height}" fill="#0f172a"/>
  <rect x="0" y="0" width="{layout.width}" height="12" fill="{accent}"/>
  <rect x="0" y="12" width="{layout.width}" height="148" fill="#111827"/>
  <text x="{layout.margin_x}" y="58" font-family="Arial, DejaVu Sans, sans-serif" font-size="38" font-weight="700" fill="#f8fafc">{BRAND}</text>
  <text x="{layout.margin_x + 154}" y="56" font-family="Arial, DejaVu Sans, sans-serif" font-size="20" fill="#94a3b8">{TITLE}</text>
  <text x="{note_x}" y="{note_y}" font-family="Arial, DejaVu Sans, sans-serif" font-size="16" fill="#94a3b8">{escape_text(layout.note)}</text>
  {step_indicator(active_step, layout_rotation_deg=layout_rotation_deg)}
  <text x="{layout.margin_x}" y="{title_y}" font-family="Arial, DejaVu Sans, sans-serif" font-size="44" font-weight="700" fill="#f8fafc">{escape_text(title)}</text>
  {svg_lines(subtitle, x=layout.margin_x + 2, y=subtitle_y, size=21, fill="#cbd5e1", width=subtitle_width, line_gap=28, max_lines=2)}
  {options_svg}
  {field_svg}
  {panel_svg}
  {extra_svg}
  {footer_text(footer, layout_rotation_deg=layout_rotation_deg)}
</svg>
"""


def visual_renderer_name() -> str:
    return "framebuffer_svg" if RENDERER_MODE == "framebuffer" else "mpv_drm_svg"


def visual_renderer_uses_mpv() -> bool:
    return RENDERER_MODE != "framebuffer"


class PSFFont:
    def __init__(self, path: str) -> None:
        font_path = pathlib.Path(path)
        if not font_path.exists():
            raise VisualWizardError("fonte visual indisponivel")
        raw = gzip.open(font_path, "rb").read() if font_path.suffix == ".gz" else font_path.read_bytes()
        if len(raw) >= 4 and raw[:2] == b"\x36\x04":
            mode = raw[2]
            char_size = raw[3]
            glyph_count = 512 if mode & 0x01 else 256
            self.width = 8
            self.height = char_size
            self.glyphs = raw[4 : 4 + glyph_count * char_size]
            self.glyph_count = glyph_count
            return
        if len(raw) >= 32 and struct.unpack_from("<I", raw, 0)[0] == 0x864AB572:
            _, _, header_size, _, glyph_count, char_size, height, width = struct.unpack_from("<IIIIIIII", raw, 0)
            self.width = int(width)
            self.height = int(height)
            self.glyphs = raw[header_size : header_size + glyph_count * char_size]
            self.glyph_count = int(glyph_count)
            return
        raise VisualWizardError("fonte visual invalida")

    def glyph(self, char: str) -> bytes:
        code = ord(char)
        if code >= self.glyph_count:
            code = ord("?")
        start = code * self.height
        end = start + self.height
        return self.glyphs[start:end]


class FramebufferSVGRenderer:
    def __init__(self, font_path: str = PSF_FONT_PATH) -> None:
        self.fb_path = pathlib.Path("/dev/fb0")
        if not self.fb_path.exists():
            raise VisualWizardError("framebuffer indisponivel")
        self.width, self.height = self.read_virtual_size()
        self.bpp = self.read_int("/sys/class/graphics/fb0/bits_per_pixel")
        self.stride = self.read_int("/sys/class/graphics/fb0/stride")
        if self.bpp != 32 or self.width <= 0 or self.height <= 0 or self.stride <= 0:
            raise VisualWizardError("framebuffer visual incompativel")
        self.font = PSFFont(font_path)
        self.fb_file = self.fb_path.open("r+b", buffering=0)
        self.fb = mmap.mmap(self.fb_file.fileno(), self.stride * self.height, access=mmap.ACCESS_WRITE)

    def close(self) -> None:
        try:
            self.fb.flush()
            self.fb.close()
        finally:
            self.fb_file.close()

    @staticmethod
    def read_int(path: str) -> int:
        return int(pathlib.Path(path).read_text(encoding="utf-8").strip())

    @staticmethod
    def read_virtual_size() -> tuple[int, int]:
        raw = pathlib.Path("/sys/class/graphics/fb0/virtual_size").read_text(encoding="utf-8").strip()
        left, right = raw.split(",", 1)
        return int(left), int(right)

    @staticmethod
    def pixel_bytes(color: tuple[int, int, int]) -> bytes:
        red, green, blue = color
        return bytes((blue, green, red, 0))

    def draw_physical_rect(self, x: float, y: float, width: float, height: float, color: tuple[int, int, int]) -> None:
        x0 = max(0, min(self.width, int(round(x))))
        y0 = max(0, min(self.height, int(round(y))))
        x1 = max(0, min(self.width, int(round(x + width))))
        y1 = max(0, min(self.height, int(round(y + height))))
        if x1 <= x0 or y1 <= y0:
            return
        row = self.pixel_bytes(color) * (x1 - x0)
        for py in range(y0, y1):
            offset = py * self.stride + x0 * 4
            self.fb[offset : offset + len(row)] = row

    def render_context(self, svg: str) -> dict[str, float | int]:
        match = SVG_RE.search(svg)
        attrs = parse_attrs(match.group(1)) if match else {}
        source_w = max(1.0, parse_float(attrs.get("width"), CANVAS_WIDTH))
        source_h = max(1.0, parse_float(attrs.get("height"), CANVAS_HEIGHT))
        rotation = normalize_rotation_deg(parse_int(attrs.get("data-display-rotation-deg"), 0))
        if rotation in {90, 270}:
            rotated_w, rotated_h = source_h, source_w
        else:
            rotated_w, rotated_h = source_w, source_h
        scale = min(self.width / rotated_w, self.height / rotated_h)
        drawn_w = rotated_w * scale
        drawn_h = rotated_h * scale
        return {
            "source_w": source_w,
            "source_h": source_h,
            "rotation": rotation,
            "scale": scale,
            "offset_x": max(0.0, (self.width - drawn_w) / 2),
            "offset_y": max(0.0, (self.height - drawn_h) / 2),
        }

    @staticmethod
    def transform_rect(
        x: float,
        y: float,
        width: float,
        height: float,
        ctx: dict[str, float | int],
    ) -> tuple[float, float, float, float]:
        source_w = float(ctx["source_w"])
        source_h = float(ctx["source_h"])
        scale = float(ctx["scale"])
        offset_x = float(ctx["offset_x"])
        offset_y = float(ctx["offset_y"])
        rotation = int(ctx["rotation"])
        if rotation == 90:
            return (
                offset_x + (source_h - y - height) * scale,
                offset_y + x * scale,
                height * scale,
                width * scale,
            )
        if rotation == 270:
            return (
                offset_x + y * scale,
                offset_y + (source_w - x - width) * scale,
                height * scale,
                width * scale,
            )
        if rotation == 180:
            return (
                offset_x + (source_w - x - width) * scale,
                offset_y + (source_h - y - height) * scale,
                width * scale,
                height * scale,
            )
        return (offset_x + x * scale, offset_y + y * scale, width * scale, height * scale)

    def draw_logical_rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        color: tuple[int, int, int],
        ctx: dict[str, float | int],
    ) -> None:
        self.draw_physical_rect(*self.transform_rect(x, y, width, height, ctx), color)

    def draw_text(
        self,
        x: float,
        y: float,
        text: str,
        font_size: float,
        color: tuple[int, int, int],
        ctx: dict[str, float | int],
    ) -> None:
        clean = html.unescape(re.sub(r"<[^>]+>", "", text))
        if not clean:
            return
        scale = max(1, int(round(font_size / max(1, self.font.height))))
        cursor_x = x
        top_y = max(0.0, y - self.font.height * scale)
        for char in clean:
            if char == "\n":
                cursor_x = x
                top_y += (self.font.height + 2) * scale
                continue
            glyph = self.font.glyph(char)
            for gy, row in enumerate(glyph):
                for gx in range(self.font.width):
                    if not (row & (0x80 >> gx)):
                        continue
                    self.draw_logical_rect(
                        cursor_x + gx * scale,
                        top_y + gy * scale,
                        scale,
                        scale,
                        color,
                        ctx,
                    )
            cursor_x += (self.font.width + 1) * scale

    def render(self, svg: str) -> None:
        ctx = self.render_context(svg)
        self.draw_physical_rect(0, 0, self.width, self.height, (15, 23, 42))
        for match in RECT_RE.finditer(svg):
            attrs = parse_attrs(match.group(1))
            color = parse_color(attrs.get("fill"))
            if color is None:
                continue
            self.draw_logical_rect(
                parse_float(attrs.get("x")),
                parse_float(attrs.get("y")),
                parse_float(attrs.get("width")),
                parse_float(attrs.get("height")),
                color,
                ctx,
            )
        for match in TEXT_RE.finditer(svg):
            attrs = parse_attrs(match.group(1))
            color = parse_color(attrs.get("fill")) or (255, 255, 255)
            font_size = parse_float(attrs.get("font-size"), 20.0)
            x = parse_float(attrs.get("x"))
            y = parse_float(attrs.get("y"))
            body = match.group(2)
            tspans = TSPAN_RE.findall(body)
            if tspans:
                current_y = y
                for tspan_attrs_raw, tspan_text in tspans:
                    tspan_attrs = parse_attrs(tspan_attrs_raw)
                    current_y += parse_float(tspan_attrs.get("dy"), 0.0)
                    self.draw_text(parse_float(tspan_attrs.get("x"), x), current_y, tspan_text, font_size, color, ctx)
            else:
                self.draw_text(x, y, body, font_size, color, ctx)
        self.fb.flush()


class VisualDisplay:
    def __init__(self, out_dir: pathlib.Path, *, mpv_bin: str = "mpv", enabled: bool = True) -> None:
        self.out_dir = out_dir
        self.screens_dir = out_dir / "screens"
        self.ipc_path = out_dir / "visual-wizard-mpv.sock"
        self.mpv_bin = mpv_bin
        self.enabled = enabled
        self.process: subprocess.Popen[bytes] | None = None
        self.sequence = 0
        self.request_id = 0
        self.framebuffer: FramebufferSVGRenderer | None = None
        prepare_private_dir(self.screens_dir)
        if enabled and RENDERER_MODE == "framebuffer":
            self.framebuffer = FramebufferSVGRenderer()

    def mpv_video_args(self) -> list[str]:
        if MPV_VIDEO_MODE == "drm":
            return ["--vo=drm", "--profile=sw-fast"]
        if MPV_VIDEO_MODE == "gpu_drm":
            return ["--vo=gpu", "--gpu-context=drm"]
        raise VisualWizardError("modo visual indisponivel")

    def write_svg(self, screen_id: str, svg: str) -> pathlib.Path:
        safe_name = "".join(char if char.isalnum() or char in "._-" else "_" for char in screen_id)
        self.sequence += 1
        path = self.screens_dir / f"{self.sequence:04d}-{safe_name}.svg"
        atomic_write_private_text(path, svg, self.screens_dir)
        return path

    def ensure_started(self, initial_svg: pathlib.Path) -> None:
        if not self.enabled or self.process is not None:
            return
        if not shutil.which(self.mpv_bin):
            raise VisualWizardError("renderer visual indisponivel")
        try:
            self.ipc_path.unlink()
        except FileNotFoundError:
            pass
        command = [
            self.mpv_bin,
            "--no-config",
            "--fs",
            "--force-window=yes",
            "--image-display-duration=inf",
            "--keep-open=yes",
            "--no-terminal",
            "--no-osc",
            "--osd-level=0",
            "--input-terminal=no",
            "--input-default-bindings=no",
            "--input-vo-keyboard=no",
            "--cursor-autohide=always",
            "--ao=null",
            f"--input-ipc-server={self.ipc_path}",
            *self.mpv_video_args(),
            "--",
            str(initial_svg),
        ]
        self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 5
        while time.time() < deadline:
            if self.ipc_path.exists():
                return
            if self.process.poll() is not None:
                break
            time.sleep(0.1)
        if self.process.poll() is not None:
            raise VisualWizardError("renderer visual encerrou antes da tela")

    def ipc_request(self, command: list[Any], *, timeout_sec: float = 1.0) -> dict[str, Any] | None:
        if not self.enabled or self.process is None or self.process.poll() is not None:
            return None
        self.request_id += 1
        request_id = self.request_id
        payload = json.dumps({"command": command, "request_id": request_id}).encode("utf-8") + b"\n"
        deadline = time.monotonic() + timeout_sec
        buffer = b""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(timeout_sec)
                client.connect(str(self.ipc_path))
                client.sendall(payload)
                while time.monotonic() < deadline:
                    try:
                        chunk = client.recv(4096)
                    except socket.timeout:
                        return None
                    if not chunk:
                        return None
                    buffer += chunk
                    while b"\n" in buffer:
                        raw_line, buffer = buffer.split(b"\n", 1)
                        if not raw_line.strip():
                            continue
                        try:
                            response = json.loads(raw_line.decode("utf-8", "ignore"))
                        except json.JSONDecodeError:
                            continue
                        if response.get("request_id") == request_id:
                            return response if isinstance(response, dict) else None
        except OSError:
            return None
        return None

    def send_command(self, command: list[Any]) -> bool:
        response = self.ipc_request(command, timeout_sec=1.0)
        return bool(response and response.get("error") == "success")

    def wait_for_loaded_path(self, path: pathlib.Path) -> bool:
        if not self.enabled or self.process is None or self.process.poll() is not None:
            return False
        expected = str(path)
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            response = self.ipc_request(["get_property", "path"], timeout_sec=0.5)
            if response and response.get("error") == "success" and response.get("data") == expected:
                return True
            time.sleep(0.03)
        return False

    def show(self, screen_id: str, svg: str) -> pathlib.Path:
        path = self.write_svg(screen_id, svg)
        if not self.enabled:
            return path
        if self.framebuffer is not None:
            self.framebuffer.render(svg)
            return path
        if RESTART_MPV_PER_SCREEN:
            self.stop()
            self.ensure_started(path)
            if PRESENT_SETTLE_SEC > 0:
                time.sleep(PRESENT_SETTLE_SEC)
            return path
        if self.process is None:
            self.ensure_started(path)
        else:
            if not self.send_command(["loadfile", str(path), "replace"]):
                self.stop()
                self.ensure_started(path)
            elif DOUBLE_LOAD_PER_SCREEN:
                self.wait_for_loaded_path(path)
                self.send_command(["loadfile", str(path), "replace"])
        self.wait_for_loaded_path(path)
        if PRESENT_SETTLE_SEC > 0:
            time.sleep(PRESENT_SETTLE_SEC)
        return path

    def stop(self) -> None:
        process = self.process
        self.process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        try:
            self.ipc_path.unlink()
        except FileNotFoundError:
            pass
        if self.framebuffer is not None:
            self.framebuffer.close()
            self.framebuffer = None


class RawKeyboard:
    def __enter__(self) -> "RawKeyboard":
        self.fd = sys.stdin.fileno()
        self.previous = termios.tcgetattr(self.fd)
        tty.setraw(self.fd)
        termios.tcflush(self.fd, termios.TCIFLUSH)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        termios.tcsetattr(self.fd, termios.TCSANOW, self.previous)


def read_key() -> str:
    data = os.read(sys.stdin.fileno(), 1)
    if data in {b"\r", b"\n"}:
        return "enter"
    if data in {b"\x7f", b"\x08"}:
        return "backspace"
    if data == b"\x02":
        return "back"
    if data == b"\x15":
        return "clear"
    if data == b"\x1b":
        chunks = []
        while True:
            ready, _, _ = select.select([sys.stdin], [], [], 0.12)
            if not ready:
                break
            chunks.append(os.read(sys.stdin.fileno(), 1))
            if len(chunks) >= 8:
                break
        if not chunks:
            return "escape"
        rest = b"".join(chunks)
        if rest == b"[A":
            return "up"
        if rest == b"[B":
            return "down"
        if rest == b"[C":
            return "right"
        if rest == b"[D":
            return "left"
        if rest in {b"[5~", b"[H", b"OH"}:
            return "up"
        if rest in {b"[6~", b"[F", b"OF"}:
            return "down"
        if rest in {b"[3~", b"[P"}:
            return "backspace"
        if rest in {b"OQ", b"[12~"}:
            return "back"
        return "unknown"
    try:
        char = data.decode("utf-8")
    except UnicodeDecodeError:
        return "unknown"
    if len(char) == 1 and 32 <= ord(char) <= 126:
        return char
    return "unknown"


def draw_welcome(display: VisualDisplay) -> None:
    display.show(
        "01-welcome",
        build_screen_svg(
            active_step=0,
            title="Bem-vindo",
            subtitle="Este assistente prepara rede, ambiente e tela sem abrir Linux ou shell para o operador.",
            footer="Enter inicia | Esc cancela",
            panel_title="Garantias desta fase",
            panel_items=[
                "Config real nao sera lida ou escrita.",
                "Writer real nao sera chamado.",
                "Hotspot e portal continuam fora.",
                "Player volta ao final do runner.",
            ],
        ),
    )


def wait_enter_or_cancel() -> None:
    while True:
        key = read_key()
        if key == "enter":
            return
        if key in {"escape", "quit"}:
            raise VisualWizardAbort("setup visual cancelado pelo operador")


def choose_option(
    display: VisualDisplay,
    *,
    screen_id: str,
    active_step: int,
    title: str,
    subtitle: str,
    options: list[Option],
    panel_items: list[str],
    allow_back: bool = False,
    layout_rotation_deg: int = 0,
) -> Option | None:
    selected = 0
    while True:
        footer = "Setas movem | Enter confirma | Esc cancela"
        if allow_back:
            footer = "Setas movem | Enter confirma | B volta | Esc cancela"
        display.show(
            screen_id,
            build_screen_svg(
                active_step=active_step,
                title=title,
                subtitle=subtitle,
                footer=footer,
                options=options,
                selected_index=selected,
                panel_items=panel_items,
                layout_rotation_deg=layout_rotation_deg,
            ),
        )
        key = read_key()
        if key in {"up", "left"}:
            selected = (selected - 1) % len(options)
        elif key in {"down", "right"}:
            selected = (selected + 1) % len(options)
        elif key == "enter":
            return options[selected]
        elif allow_back and key in {"b", "B", "back"}:
            return None
        elif key in {"escape", "q", "Q"}:
            raise VisualWizardAbort("setup visual cancelado pelo operador")


def choose_orientation(display: VisualDisplay) -> dict[str, str | int]:
    options = [Option(str(item["key"]), str(item["label"]), str(item["description"])) for item in DISPLAY_OPTIONS]
    selected = 0
    needs_render = True
    while True:
        if needs_render:
            selected_rotation = resolve_display_selection(options[selected].key)
            display.show(
                "01-orientation",
                build_screen_svg(
                    active_step=0,
                    title="Orientacao da tela",
                    subtitle="Use as setas para escolher como o totem esta instalado.",
                    footer="Setas movem | Enter visualiza | Esc cancela",
                    options=options,
                    selected_index=selected,
                    panel_title="Como funciona",
                    panel_items=[
                        "Primeira etapa da configuracao.",
                        "A proxima tela confirma a escolha.",
                        "As midias usam esta orientacao ao salvar.",
                    ],
                    extra_svg=orientation_preview(str(selected_rotation["key"])),
                ),
            )
            needs_render = False
        key = read_key()
        if key in {"up", "left"}:
            selected = (selected - 1) % len(options)
            needs_render = True
            continue
        if key in {"down", "right"}:
            selected = (selected + 1) % len(options)
            needs_render = True
            continue
        if key in {"1", "2", "3", "4"}:
            selected = int(key) - 1
            needs_render = True
            continue
        if key in {"escape", "q", "Q"}:
            raise VisualWizardAbort("setup visual cancelado pelo operador")
        if key != "enter":
            continue

        rotation = resolve_display_selection(options[selected].key)
        layout_rotation_deg = int(rotation["rotation_deg"])
        confirm_options = [
            Option("confirm", "Usar esta orientacao", "A configuracao continuara neste formato."),
            Option("cancel", "Voltar e escolher outra", "Nada e gravado ate confirmar."),
        ]
        confirm_selected = 0
        while True:
            display.show(
                "01-orientation-confirm",
                build_screen_svg(
                    active_step=0,
                    title="Usar esta orientacao?",
                    subtitle="A configuracao continuara nesta orientacao. As midias tambem usarao este sentido depois de salvar.",
                    footer="Setas movem | Enter confirma | B volta | Esc cancela",
                    options=confirm_options,
                    selected_index=confirm_selected,
                    panel_title="Confirmacao",
                    panel_items=[
                        "Textos sao renderizados nativamente.",
                        "Sem esticar ou deformar a imagem.",
                        "rotation_deg entra na candidata.",
                    ],
                    extra_svg=orientation_preview(str(rotation["key"]), layout_rotation_deg=layout_rotation_deg),
                    layout_rotation_deg=layout_rotation_deg,
                ),
            )
            confirm_key = read_key()
            if confirm_key in {"up", "left", "down", "right"}:
                confirm_selected = 1 - confirm_selected
                continue
            if confirm_key == "enter":
                if confirm_options[confirm_selected].key == "confirm":
                    return rotation
                needs_render = True
                break
            if confirm_key in {"b", "B", "back"}:
                needs_render = True
                break
            if confirm_key in {"escape", "q", "Q"}:
                raise VisualWizardAbort("setup visual cancelado pelo operador")


def read_text_field(
    display: VisualDisplay,
    *,
    screen_id: str,
    active_step: int,
    title: str,
    subtitle: str,
    label: str,
    hidden: bool,
    min_length: int,
    max_length: int,
    validator: Any | None = None,
    panel_items: list[str],
    allow_back: bool = True,
    show_plain_value: bool = False,
    layout_rotation_deg: int = 0,
) -> str | None:
    value = ""
    error = ""
    while True:
        hint = text_field_display_hint(value, hidden=hidden, show_plain_value=show_plain_value)
        note = error or "O valor digitado nao sera gravado nos SVGs publicos desta rodada."
        footer = "Digite no teclado | Enter confirma | Ctrl+U limpa | Esc cancela"
        if allow_back:
            footer = "Digite no teclado | Enter confirma | F2/Ctrl+B volta | Ctrl+U limpa | Esc cancela"
        display.show(
            screen_id,
            build_screen_svg(
                active_step=active_step,
                title=title,
                subtitle=subtitle,
                footer=footer,
                field_label=label,
                field_value_hint=hint,
                field_note=note,
                panel_items=panel_items,
                accent="#ef4444" if error else "#06b6d4",
                layout_rotation_deg=layout_rotation_deg,
            ),
        )
        key = read_key()
        if key == "enter":
            candidate = value.strip() if not hidden else value
            if len(candidate) < min_length:
                error = "Entrada incompleta."
                continue
            if validator is not None:
                try:
                    return validator(candidate)
                except Exception:
                    error = "Formato invalido. Corrija e tente novamente."
                    continue
            return candidate
        if allow_back and key == "back":
            return None
        if key in {"escape", "q", "Q"}:
            raise VisualWizardAbort("setup visual cancelado pelo operador")
        if key == "backspace":
            value = value[:-1]
            error = ""
        elif key == "clear":
            value = ""
            error = ""
        elif len(key) == 1 and 32 <= ord(key) <= 126 and len(value) < max_length:
            value += key
            error = ""


def text_field_display_hint(value: str, *, hidden: bool, show_plain_value: bool) -> str:
    if hidden:
        return "*" * len(value) if value else "Aguardando entrada"
    if show_plain_value:
        return value or "Aguardando entrada"
    return f"{len(value)} caracteres digitados" if value else "Aguardando entrada"


def validate_environment_id(value: str) -> str:
    return setup.validate_environment_id(value)


def resolve_display_selection(rotation_key: str) -> dict[str, str | int]:
    option = DISPLAY_OPTION_BY_KEY.get(rotation_key)
    if option is None:
        raise VisualWizardError("orientacao desconhecida")
    return {
        "key": str(option["key"]),
        "label": str(option["label"]),
        "description": str(option["description"]),
        "rotation_deg": int(option["rotation_deg"]),
    }


def network_defaults(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "network_step": "bench_mock",
        "label": "Modo de bancada",
        "connectivity": "not_checked",
        "connected": "unknown",
        "connection_type": "unknown",
        "read_only_check": False,
        "wifi_real_test_attempted": False,
        "wifi_activation_result": "not_run",
        "rollback_after_test": "not_run",
        "dedicated_profile_present_final": "unknown",
        "dedicated_profile_persistent": False,
        "network_changed": False,
        "credentials_collected": False,
        "secrets_file_removed": False,
        "commands_executed": False,
        "nmcli_called": False,
        "wifi_networks_found_count": "unknown",
        "selected_network_present": False,
        "selected_network_signal_bucket": "unknown",
        "selected_network_security_present": "unknown",
    }
    payload.update(overrides)
    return payload


def dedicated_profile_present() -> bool | str:
    try:
        return wifi_adapter.dedicated_profile_present(
            profile_name=WIFI_PERSISTENT_PROFILE_NAME,
            timeout_sec=WIFI_TIMEOUT_SEC,
        )
    except Exception:
        return "unknown"


def use_configured_wifi_network() -> dict[str, Any]:
    present = dedicated_profile_present()
    if present is not True:
        raise VisualWizardError("wifi dedicado nao encontrado")
    return network_defaults(
        network_step="existing_configured_wifi",
        label="Wi-Fi ja configurado",
        connectivity="unknown",
        connected="yes",
        connection_type="wifi",
        read_only_check=True,
        dedicated_profile_present_final=True,
        dedicated_profile_persistent=True,
    )


def prepare_wifi_secrets_dir(raw_path: str = DEFAULT_WIFI_SECRETS_DIR) -> pathlib.Path:
    secrets_dir = wifi_adapter.require_tmp_dir(raw_path)
    wifi_adapter.prepare_out_dir(secrets_dir)
    if secrets_dir.is_symlink():
        raise VisualWizardError("diretorio temporario indisponivel")
    return secrets_dir


def write_wifi_secrets_file(secrets_dir: pathlib.Path, ssid: str, psk: str) -> pathlib.Path:
    secrets_path = secrets_dir / "secrets.json"
    if secrets_path.exists() and secrets_path.is_symlink():
        raise VisualWizardError("arquivo temporario indisponivel")
    wifi_adapter.atomic_write_private_json(secrets_path, {"ssid": ssid, "psk": psk}, secrets_dir)
    if secrets_path.is_symlink() or file_mode(secrets_path) != wifi_adapter.PRIVATE_FILE_MODE:
        raise VisualWizardError("arquivo temporario indisponivel")
    return secrets_path


def local_display_value(value: str, *, max_chars: int = 36) -> str:
    cleaned = " ".join(str(value).split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max(0, max_chars - 3)] + "..."


def security_label(value: Any) -> str:
    if value is True:
        return "segura"
    if value is False:
        return "aberta"
    return "seguranca desconhecida"


def choose_wifi_network(
    display: VisualDisplay,
    *,
    layout_rotation_deg: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    networks, list_status = wifi_adapter.list_wifi_networks_for_local_ui(timeout_sec=8)
    if not networks:
        display.show(
            "02-wifi-list-empty",
            build_screen_svg(
                active_step=1,
                title="Redes Wi-Fi",
                subtitle="Nao foi possivel montar uma lista local de redes agora.",
                footer="Enter volta | Esc cancela",
                panel_title="Resultado publico",
                panel_items=[
                    f"Listagem: {list_status}",
                    "Nenhuma rede sera alterada.",
                    "Nenhum identificador sera publicado.",
                ],
                accent="#ef4444",
                layout_rotation_deg=layout_rotation_deg,
            ),
        )
        key = read_key()
        if key == "enter":
            return None
        raise VisualWizardAbort("setup visual cancelado pelo operador")

    options = [
        Option(
            f"wifi-{index}",
            local_display_value(str(network["ssid"])),
            f"Sinal {network['signal_bucket']} | {security_label(network.get('security_present'))}",
        )
        for index, network in enumerate(networks[:5])
    ]
    selected = choose_option(
        display,
        screen_id="02-wifi-list",
        active_step=1,
        title="Redes Wi-Fi",
        subtitle="Escolha a rede na lista local. O nome nao sera gravado em evidencia.",
        options=options,
        panel_items=[
            f"Redes encontradas: {len(networks)}",
            "A lista e exibida somente aqui.",
            "BSSID, MAC, IP e DNS nao aparecem.",
            "A senha continua oculta.",
        ],
        allow_back=True,
        layout_rotation_deg=layout_rotation_deg,
    )
    if selected is None:
        return None
    index = int(selected.key.split("-", 1)[1])
    return networks[index], networks


def collect_wifi_credentials(
    display: VisualDisplay,
    *,
    layout_rotation_deg: int,
) -> tuple[pathlib.Path, dict[str, Any]] | None:
    selected = choose_wifi_network(display, layout_rotation_deg=layout_rotation_deg)
    if selected is None:
        return None
    selected_network, networks = selected
    ssid = str(selected_network["ssid"])
    display.show(
        "02-wifi-selected",
        build_screen_svg(
            active_step=1,
            title="Rede selecionada",
            subtitle=local_display_value(ssid, max_chars=56),
            footer="Enter continua | B volta | Esc cancela",
            panel_title="Privacidade",
            panel_items=[
                "Nome aparece so nesta tela local.",
                "Status e resumo gravam apenas categorias.",
                "Senha sera digitada oculta.",
            ],
            layout_rotation_deg=layout_rotation_deg,
        ),
    )
    key = read_key()
    if key == "back":
        return None
    if key != "enter":
        raise VisualWizardAbort("setup visual cancelado pelo operador")

    selection_metadata = wifi_adapter.wifi_selection_public_metadata(networks, selected_network)
    psk = read_text_field(
        display,
        screen_id="02-wifi-psk",
        active_step=1,
        title="Senha Wi-Fi",
        subtitle="Digite a senha no teclado local. O campo fica oculto.",
        label="Senha Wi-Fi",
        hidden=True,
        min_length=8,
        max_length=128,
        panel_items=[
            "Senha nao vai para argv.",
            "Senha nao vai para logs.",
            "Secrets temporario fica sob /tmp.",
        ],
        layout_rotation_deg=layout_rotation_deg,
    )
    if psk is None:
        return None
    display.show(
        "02-wifi-confirm",
        build_screen_svg(
            active_step=1,
            title="Aplicar Wi-Fi",
            subtitle="O teste vai manter apenas o perfil dedicado do produto.",
            footer="Enter aplica | F2/Ctrl+B volta | Esc cancela",
            panel_title="Antes de aplicar",
            panel_items=[
                "SSH pode oscilar se estiver na mesma rede.",
                "Console local permanece disponivel.",
                "Config real nao sera escrita.",
                "Writer nao sera chamado.",
            ],
            layout_rotation_deg=layout_rotation_deg,
        ),
    )
    key = read_key()
    if key == "back":
        return None
    if key != "enter":
        raise VisualWizardAbort("setup visual cancelado pelo operador")
    return write_wifi_secrets_file(prepare_wifi_secrets_dir(), ssid, psk), selection_metadata


def wifi_network_from_status(
    adapter_status: dict[str, Any],
    secrets_path: pathlib.Path,
    selection_metadata: dict[str, Any],
) -> dict[str, Any]:
    profile_present = dedicated_profile_present()
    activation_result = str(adapter_status.get("wifi_activation_result") or "unknown")
    network_changed = bool(adapter_status.get("network_changed", False)) or bool(
        adapter_status.get("wifi_activation_attempted", False)
    )
    return network_defaults(
        network_step="wifi_persistent",
        label="Wi-Fi configurado neste totem",
        connected="yes" if activation_result == "success" else "unknown",
        connection_type="wifi",
        connectivity="ok" if activation_result == "success" else "unknown",
        read_only_check=False,
        wifi_real_test_attempted=bool(adapter_status.get("wifi_activation_attempted", False)),
        wifi_activation_result=activation_result,
        rollback_after_test="not_requested" if activation_result == "success" else "failure",
        dedicated_profile_present_final=profile_present,
        dedicated_profile_persistent=bool(activation_result == "success" and profile_present is True),
        network_changed=network_changed,
        credentials_collected=True,
        secrets_file_removed=not secrets_path.exists(),
        commands_executed=True,
        nmcli_called=True,
        **selection_metadata,
    )


def run_wifi_persistent(
    display: VisualDisplay,
    out_dir: pathlib.Path,
    *,
    layout_rotation_deg: int,
) -> dict[str, Any] | None:
    collected = collect_wifi_credentials(display, layout_rotation_deg=layout_rotation_deg)
    if collected is None:
        return None
    secrets_path, selection_metadata = collected
    wifi_out_dir = require_tmp_dir(str(out_dir / WIFI_APPLY_DIRNAME))
    prepare_private_dir(wifi_out_dir)
    stdout_path = wifi_out_dir / "apply-stdout.json"
    command = [
        sys.executable,
        str(ADAPTER_SCRIPT),
        "--apply",
        "--enable-real-apply",
        "--confirm-real-wifi-apply",
        wifi_adapter.CONFIRM_REAL_WIFI_APPLY_LOCAL_CONSOLE,
        "--secrets-file",
        str(secrets_path),
        "--profile-name",
        WIFI_PERSISTENT_PROFILE_NAME,
        "--timeout-sec",
        str(WIFI_TIMEOUT_SEC),
        "--cleanup-secrets-file",
        "--allow-ssh-risk-with-local-console-confirmed",
        "--local-console-confirmed",
        "--keep-dedicated-profile",
        "--persistent-product-wifi",
        "--confirm-keep-dedicated-profile",
        wifi_adapter.CONFIRM_KEEP_DEDICATED_PROFILE,
        "--out-dir",
        str(wifi_out_dir),
    ]
    if stdout_path.exists() and stdout_path.is_symlink():
        raise VisualWizardError("arquivo temporario indisponivel")
    with stdout_path.open("w", encoding="utf-8") as stdout_handle:
        os.chmod(stdout_path, setup.PRIVATE_FILE_MODE)
        process = subprocess.Popen(command, stdout=stdout_handle, stderr=subprocess.DEVNULL, text=True)
        while process.poll() is None:
            display.show(
                "02-wifi-applying",
                build_screen_svg(
                    active_step=1,
                    title="Aplicando Wi-Fi",
                    subtitle="Aguarde. O perfil dedicado esta sendo testado e mantido se funcionar.",
                    footer="Aguarde...",
                    panel_title="Em andamento",
                    panel_items=[
                        "Nenhum dado da rede sera exibido.",
                        "Timeout curto esta ativo.",
                        "Apenas perfil dedicado pode ser tocado.",
                    ],
                    layout_rotation_deg=layout_rotation_deg,
                ),
            )
            time.sleep(1)
        rc = process.wait()
    status_path = wifi_out_dir / wifi_adapter.STATUS_FILENAME
    try:
        adapter_status = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        adapter_status = {
            "wifi_activation_attempted": False,
            "wifi_activation_result": "unknown",
            "network_changed": False,
            "rollback_after_test": False,
            "rollback_status": "not_run",
        }
    if secrets_path.exists() and not secrets_path.is_symlink():
        try:
            secrets_path.unlink()
        except OSError:
            pass
    if rc != 0 and adapter_status.get("wifi_activation_result") == "success":
        adapter_status["wifi_activation_result"] = "unknown"
    network = wifi_network_from_status(adapter_status, secrets_path, selection_metadata)
    display.show(
        "02-wifi-result",
        build_screen_svg(
            active_step=1,
            title="Resultado do Wi-Fi",
            subtitle=f"Resultado publico: {network['wifi_activation_result']}. Nenhum identificador de rede sera publicado.",
            footer="Enter continua | B volta | Esc cancela",
            panel_title="Resultado",
            panel_items=[
                f"Perfil dedicado presente: {network['dedicated_profile_present_final']}",
                f"Persistente: {str(network['dedicated_profile_persistent']).lower()}",
                f"Secrets removido: {str(network['secrets_file_removed']).lower()}",
            ],
            layout_rotation_deg=layout_rotation_deg,
        ),
    )
    key = read_key()
    if key == "back":
        return None
    if key == "enter":
        return network
    raise VisualWizardAbort("setup visual cancelado pelo operador")


def resolve_network_scripted(network_step: str) -> dict[str, Any]:
    if network_step in {"configured_wifi", "existing_configured_wifi", "existing_connection"}:
        return network_defaults(
            network_step="existing_configured_wifi",
            label="Wi-Fi ja configurado",
            connectivity="unknown",
            connected="yes",
            connection_type="wifi",
            read_only_check=True,
            dedicated_profile_present_final=True,
            dedicated_profile_persistent=True,
        )
    if network_step in {"wifi_persistent", "persistent", "wifi_select"}:
        return network_defaults(
            network_step="wifi_persistent",
            label="Wi-Fi configurado neste totem",
            connected="unknown",
            connection_type="wifi",
            connectivity="not_checked",
            dedicated_profile_present_final="unknown",
            dedicated_profile_persistent=False,
            wifi_networks_found_count=1,
            selected_network_present=True,
            selected_network_signal_bucket="strong",
            selected_network_security_present=True,
        )
    if network_step in {"bench_mock", "mock"}:
        return network_defaults()
    raise VisualWizardError("network-step invalido")


def build_visual_status(
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
        "flow": "setup_product_local_v0_visual",
        "interface": {
            "mode": INTERFACE_MODE,
            "operator_input": "keyboard_only",
            "free_shell_available": False,
            "linux_prompt_visible": False,
            "browser_required": False,
            "chromium_used": False,
            "desktop_used": False,
            "xorg_used": False,
            "wayland_used": False,
            "compositor_used": False,
            "visual_renderer": visual_renderer_name(),
            "mpv_video_mode": MPV_VIDEO_MODE,
            "screens_generated": True,
        },
        "files": {
            "candidate_config": CANDIDATE_FILENAME,
            "summary": SUMMARY_FILENAME,
            "status": STATUS_FILENAME,
            "screens": "screens",
            "orientation_contract": ORIENTATION_FILENAME,
        },
        "orientation": {
            "rotation_deg": int(rotation["rotation_deg"]),
            "orientation_label": str(rotation["key"]),
            "contract_file": ORIENTATION_FILENAME,
            "wizard_layout_mode": screen_layout(int(rotation["rotation_deg"])).mode,
            "splash_rotation_supported": True,
            "player_rotation_contract": "config.rotation_deg",
            "media_rotation_contract": "config.rotation_deg",
        },
        "network": {
            "network_step": network["network_step"],
            "connectivity": network["connectivity"],
            "connected": network["connected"],
            "connection_type": network["connection_type"],
            "read_only_check": network["read_only_check"],
            "internet_external_check": False,
            "wifi_real_test_attempted": network["wifi_real_test_attempted"],
            "wifi_activation_result": network["wifi_activation_result"],
            "rollback_after_test": network["rollback_after_test"],
            "dedicated_profile_present_final": network["dedicated_profile_present_final"],
            "dedicated_profile_persistent": network["dedicated_profile_persistent"],
            "network_changed": network["network_changed"],
            "credentials_collected": network["credentials_collected"],
            "secrets_file_removed": network["secrets_file_removed"],
            "wifi_networks_found_count": network["wifi_networks_found_count"],
            "selected_network_present": network["selected_network_present"],
            "selected_network_signal_bucket": network["selected_network_signal_bucket"],
            "selected_network_security_present": network["selected_network_security_present"],
            "ssid_written_to_public_status": False,
            "password_written_to_public_status": False,
            "ip_written_to_public_status": False,
            "mac_written_to_public_status": False,
            "dns_written_to_public_status": False,
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
            "wifi_activation_result": network["wifi_activation_result"],
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
            "network_changed": network["network_changed"],
            "wifi_changed": network["network_changed"],
            "display_changed": False,
            "rotation_applied": False,
            "hotspot_created": False,
            "portal_created": False,
            "commands_executed": network["commands_executed"],
            "systemctl_called": False,
            "service_changed": False,
            "player_started": False,
            "player_stopped": False,
            "main_player_mpv_called": False,
            "visual_renderer_mpv_called": visual_renderer_uses_mpv(),
            "backend_called": False,
            "nmcli_called": network["nmcli_called"],
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
            "raw_logs_written": False,
        },
    }


def build_visual_summary(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Dadooh C9.9 setup visual local",
            "",
            f"schema_version: {status['schema_version']}",
            f"generated_at_utc: {status['generated_at_utc']}",
            f"state: {status['state']}",
            f"flow: {status['flow']}",
            f"interface_mode: {status['interface']['mode']}",
            "operator_input: keyboard_only",
            "free_shell_available: false",
            "linux_prompt_visible: false",
            "browser_required: false",
            "chromium_used: false",
            "desktop_used: false",
            "xorg_used: false",
            "wayland_used: false",
            "compositor_used: false",
            f"visual_renderer: {status['interface']['visual_renderer']}",
            f"mpv_video_mode: {status['interface']['mpv_video_mode']}",
            f"orientation_contract: {status['files']['orientation_contract']}",
            f"orientation_layout_mode: {status['orientation']['wizard_layout_mode']}",
            f"network_step: {status['network']['network_step']}",
            f"connectivity: {status['network']['connectivity']}",
            f"connection_type: {status['network']['connection_type']}",
            f"wifi_activation_result: {status['network']['wifi_activation_result']}",
            f"rollback_after_test: {status['network']['rollback_after_test']}",
            f"dedicated_profile_present_final: {status['network']['dedicated_profile_present_final']}",
            f"dedicated_profile_persistent: {str(status['network']['dedicated_profile_persistent']).lower()}",
            f"network_changed: {str(status['network']['network_changed']).lower()}",
            f"credentials_collected: {str(status['network']['credentials_collected']).lower()}",
            f"credential_file_removed: {str(status['network']['secrets_file_removed']).lower()}",
            f"wifi_networks_found_count: {status['network']['wifi_networks_found_count']}",
            f"selected_network_present: {str(status['network']['selected_network_present']).lower()}",
            f"selected_network_signal_bucket: {status['network']['selected_network_signal_bucket']}",
            f"selected_network_security_present: {status['network']['selected_network_security_present']}",
            f"environment_id_present: {str(status['environment']['environment_id_present']).lower()}",
            f"environment_id_valid: {str(status['environment']['environment_id_valid']).lower()}",
            f"rotation_degrees: {status['validation']['rotation_degrees']}",
            "splash_rotation_supported: true",
            "player_rotation_contract: config.rotation_deg",
            "contract_validator: C5.1 allow-mock",
            f"contract_allow_mock_valid: {str(status['contract_validation']['allow_mock']['valid']).lower()}",
            "contract_real_dry_run_expected_failure: true",
            "",
            "Guardrails:",
            "writes_only_under_tmp: true",
            "real_config_read: false",
            "real_config_written: false",
            "writer_called: false",
            "data_written: false",
            "opt_written: false",
            f"commands_executed: {str(status['guardrails']['commands_executed']).lower()}",
            "systemctl_called: false",
            "service_changed: false",
            "main_player_mpv_called: false",
            f"visual_renderer_mpv_called: {str(status['guardrails']['visual_renderer_mpv_called']).lower()}",
            f"nmcli_called: {str(status['guardrails']['nmcli_called']).lower()}",
            f"network_changed: {str(status['guardrails']['network_changed']).lower()}",
            "display_changed: false",
            "rotation_applied: false",
            "hotspot_created: false",
            "portal_created: false",
            "",
            "Privacy:",
            "candidate_payload_copied_to_summary: false",
            "environment_identifier_raw_written_to_summary: false",
            "credential_values_public: false",
            "private_url_written_to_summary: false",
            "network_identifiers_public: false",
            "raw_logs_written: false",
        ]
    )


def output_text(out_dir: pathlib.Path) -> str:
    parts = []
    for path in [out_dir / STATUS_FILENAME, out_dir / SUMMARY_FILENAME]:
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def assert_sanitized_outputs(out_dir: pathlib.Path, environment_id: str) -> None:
    text = output_text(out_dir)
    forbidden_values = [environment_id, *SENSITIVE_MARKERS]
    for item in setup.MOCK_ENVIRONMENTS:
        forbidden_values.append(item["environment_id"])
        forbidden_values.append(item["name"])
    for value in forbidden_values:
        escaped = json.dumps(value, ensure_ascii=True)[1:-1]
        for variant in (value, escaped):
            if variant and variant in text:
                raise VisualWizardError("privacy scan blocked raw value in public artifacts")


def orientation_contract_payload(generated_at: str, rotation: dict[str, str | int]) -> dict[str, Any]:
    rotation_deg = int(rotation["rotation_deg"])
    layout = screen_layout(rotation_deg)
    return {
        "schema_version": "dadooh-display-orientation.v1",
        "updated_at": generated_at,
        "rotation_deg": rotation_deg,
        "orientation_label": str(rotation["key"]),
        "layout_mode": layout.mode,
        "public_allowlisted": True,
        "contains_sensitive_data": False,
    }


def write_visual_artifacts(
    out_dir: pathlib.Path,
    environment_id: str,
    rotation: dict[str, str | int],
    network: dict[str, Any],
) -> dict[str, Any]:
    prepare_private_dir(out_dir)
    generated_at = utc_timestamp()
    candidate = setup.build_candidate_config(
        environment_id,
        int(rotation["rotation_deg"]),
        setup.SELECTION_MODE_MANUAL,
    )
    candidate["setup_source"] = SETUP_SOURCE
    candidate["setup_interface"] = INTERFACE_MODE
    candidate["setup_network_step"] = network["network_step"]
    candidate["setup_connectivity"] = network["connectivity"]
    candidate["setup_wifi_real_test_attempted"] = bool(network["wifi_real_test_attempted"])
    candidate["setup_wifi_activation_result"] = network["wifi_activation_result"]
    candidate["setup_wifi_rollback_after_test"] = network["rollback_after_test"]
    candidate["setup_wifi_dedicated_profile_persistent"] = bool(network["dedicated_profile_persistent"])
    candidate["setup_wifi_networks_found_count"] = network["wifi_networks_found_count"]
    candidate["setup_wifi_selected_network_present"] = bool(network["selected_network_present"])
    candidate["setup_wifi_selected_network_signal_bucket"] = network["selected_network_signal_bucket"]
    candidate["setup_wifi_selected_network_security_present"] = network["selected_network_security_present"]
    candidate["setup_display_source"] = "mock_candidate_only"
    candidate["setup_visual_renderer"] = visual_renderer_name()

    contract_validation = setup.validate_candidate_handoff(candidate)
    status = build_visual_status(generated_at, rotation, environment_id, network, contract_validation)
    atomic_write_private_json(out_dir / CANDIDATE_FILENAME, candidate, out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_json(out_dir / ORIENTATION_FILENAME, orientation_contract_payload(generated_at, rotation), out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_visual_summary(status), out_dir)
    assert_sanitized_outputs(out_dir, environment_id)
    return status


def write_cancelled_artifact(out_dir: pathlib.Path) -> None:
    prepare_private_dir(out_dir)
    status = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "state": "setup_cancelled",
        "candidate_generated": False,
        "interface_mode": INTERFACE_MODE,
        "guardrails": {
            "writes_only_under_tmp": True,
            "real_config_read": False,
            "real_config_written": False,
            "writer_called": False,
            "network_changed": False,
            "display_changed": False,
            "player_started": False,
            "main_player_mpv_called": False,
            "visual_renderer_mpv_called": visual_renderer_uses_mpv(),
            "nmcli_called": False,
        },
        "privacy": {
            "candidate_payload_copied": False,
            "environment_identifier_raw_written": False,
            "credential_value_written": False,
            "network_metadata_written": False,
            "raw_logs_written": False,
        },
    }
    atomic_write_private_json(out_dir / CANCELLED_FILENAME, status, out_dir)


def write_failed_artifact(out_dir: pathlib.Path, reason: str) -> None:
    prepare_private_dir(out_dir)
    status = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "state": "setup_failed",
        "candidate_generated": False,
        "reason_category": reason,
        "interface_mode": INTERFACE_MODE,
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "network_identifiers_published": False,
        "credential_values_published": False,
        "raw_logs_written": False,
    }
    atomic_write_private_json(out_dir / FAILED_FILENAME, status, out_dir)


def review_and_confirm(
    display: VisualDisplay,
    environment_id: str,
    rotation: dict[str, str | int],
    network: dict[str, Any],
) -> bool:
    network_note = {
        "existing_configured_wifi": "Wi-Fi dedicado ja configurado sera usado.",
        "wifi_persistent": "Wi-Fi dedicado foi configurado para uso futuro.",
        "bench_mock": "Modo de bancada sem nova rede real.",
    }.get(network["network_step"], "Rede sem detalhe publico.")
    display.show(
        "05-review",
        build_screen_svg(
            active_step=3,
            title="Revisao",
            subtitle="Confirme a candidata temporaria. Dados sensiveis nao aparecem nesta tela.",
            footer="Enter conclui | B volta | Esc cancela",
            panel_title="Resumo publico",
            panel_items=[
                f"Conexao: {network_note}",
                "Ambiente informado: sim",
                f"Tela: {rotation['label']}",
                "Writer real segue bloqueado.",
                "Config real segue intocada.",
            ],
            layout_rotation_deg=int(rotation["rotation_deg"]),
        ),
    )
    key = read_key()
    if key == "enter":
        return True
    if key in {"b", "B", "back"}:
        return False
    raise VisualWizardAbort("setup visual cancelado pelo operador")


def show_complete(display: VisualDisplay, status: dict[str, Any]) -> None:
    rotation_deg = int(status.get("validation", {}).get("rotation_degrees", 0))
    display.show(
        "06-complete",
        build_screen_svg(
            active_step=4,
            title="Concluido",
            subtitle="Candidata temporaria gerada. A proxima etapa ainda precisa de writer controlado.",
            footer="Enter sai",
            panel_title="Resultado",
            panel_items=[
                f"Estado: {status['state']}",
                "C5.1 allow-mock passou.",
                "Real dry-run falhou como esperado.",
                "Nada foi escrito fora de /tmp.",
            ],
            accent="#22c55e",
            layout_rotation_deg=rotation_deg,
        ),
    )
    wait_enter_or_cancel()


def run_visual_wizard(out_dir: pathlib.Path, *, mpv_bin: str) -> dict[str, Any]:
    display = VisualDisplay(out_dir, mpv_bin=mpv_bin, enabled=True)
    try:
        with RawKeyboard():
            rotation = choose_orientation(display)
            layout_rotation_deg = int(rotation["rotation_deg"])
            while True:
                selected_network = choose_option(
                    display,
                    screen_id="02-connection",
                    active_step=1,
                    title="Conexao",
                    subtitle="Escolha como este totem deve seguir agora.",
                    options=list(NETWORK_OPTIONS),
                    panel_items=[
                        "Redes aparecem em lista local.",
                        "Senha fica oculta.",
                        "Sem hotspot e sem portal nesta rodada.",
                    ],
                    layout_rotation_deg=layout_rotation_deg,
                )
                if selected_network is None:
                    continue
                try:
                    if selected_network.key == "configured_wifi":
                        network = use_configured_wifi_network()
                    elif selected_network.key == "wifi_select":
                        maybe_network = run_wifi_persistent(display, out_dir, layout_rotation_deg=layout_rotation_deg)
                        if maybe_network is None:
                            continue
                        network = maybe_network
                    else:
                        network = network_defaults()
                except VisualWizardError as exc:
                    display.show(
                        "02-connection-error",
                        build_screen_svg(
                            active_step=1,
                            title="Conexao nao confirmada",
                            subtitle=str(exc),
                            footer="Enter volta | Esc cancela",
                            panel_title="Mensagem publica",
                            panel_items=[
                                "Nenhum identificador foi exibido.",
                                "Nenhuma config real foi tocada.",
                                "Tente outro caminho.",
                            ],
                            accent="#ef4444",
                            layout_rotation_deg=layout_rotation_deg,
                        ),
                    )
                    key = read_key()
                    if key == "enter":
                        continue
                    raise VisualWizardAbort("setup visual cancelado pelo operador")

                while True:
                    environment_id = read_text_field(
                        display,
                        screen_id="03-environment",
                        active_step=2,
                        title="Ambiente",
                        subtitle="Digite o identificador fornecido pela Dadooh.",
                        label="Identificador do ambiente",
                        hidden=False,
                        min_length=3,
                        max_length=128,
                        validator=validate_environment_id,
                        panel_items=[
                            "3 a 128 caracteres.",
                            "Letras ASCII, numeros, _, -, . ou :",
                            "Valor nao aparece no resumo publico.",
                        ],
                        show_plain_value=True,
                        layout_rotation_deg=layout_rotation_deg,
                    )
                    if environment_id is None:
                        break
                    if not review_and_confirm(display, environment_id, rotation, network):
                        continue
                    status = write_visual_artifacts(out_dir, environment_id, rotation, network)
                    show_complete(display, status)
                    return status
    finally:
        display.stop()


def generate_preview_screens(out_dir: pathlib.Path) -> None:
    display = VisualDisplay(out_dir, enabled=False)
    display.show(
        "01-orientation",
        build_screen_svg(
            active_step=0,
            title="Orientacao da tela",
            subtitle="Escolha primeiro como o totem esta instalado.",
            footer="Setas movem | Enter confirma | Esc cancela",
            options=[Option(str(item["key"]), str(item["label"]), str(item["description"])) for item in DISPLAY_OPTIONS],
            selected_index=0,
            panel_items=["Primeira etapa", "Candidata em /tmp", "Sem rotacao real do player"],
            extra_svg=orientation_preview("landscape"),
        ),
    )
    display.show(
        "01-orientation-confirm-portrait",
        build_screen_svg(
            active_step=0,
            title="Usar esta orientacao?",
            subtitle="A configuracao continuara nesta orientacao.",
            footer="Setas movem | Enter confirma | B volta | Esc cancela",
            options=[
                Option("confirm", "Usar esta orientacao", "A configuracao continuara neste formato."),
                Option("cancel", "Voltar e escolher outra", "Nada e gravado ate confirmar."),
            ],
            selected_index=0,
            panel_items=["Layout retrato", "Confirmacao local", "Sem alterar player global"],
            extra_svg=orientation_preview("portrait_right", layout_rotation_deg=90),
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "02-connection",
        build_screen_svg(
            active_step=1,
            title="Conexao",
            subtitle="Escolha usar Wi-Fi ja configurado, selecionar rede ou seguir em bancada.",
            footer="Setas movem | Enter confirma | Esc cancela",
            options=list(NETWORK_OPTIONS),
            selected_index=0,
            panel_items=["Lista local", "Senha oculta", "Sem dados publicos"],
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "02-wifi-list",
        build_screen_svg(
            active_step=1,
            title="Redes Wi-Fi",
            subtitle="Exemplo sintetico de lista local. SSIDs reais nao entram em evidencia.",
            footer="Setas movem | Enter confirma | B volta",
            options=[
                Option("wifi-0", "REDE-DE-EXEMPLO-01", "Sinal strong | segura"),
                Option("wifi-1", "REDE-DE-EXEMPLO-02", "Sinal medium | segura"),
            ],
            selected_index=0,
            panel_items=["Aparece so no HDMI", "Sem BSSID/MAC", "Senha continua oculta"],
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "03-environment",
        build_screen_svg(
            active_step=2,
            title="Ambiente",
            subtitle="Entrada manual validada localmente.",
            footer="Digite no teclado | Enter confirma",
            field_label="Identificador do ambiente",
            field_value_hint="18 caracteres digitados",
            field_note="Valor real nao e gravado na tela de preview.",
            panel_items=["Formato C5.1", "Sem backend", "Sem publicacao do valor"],
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "05-review",
        build_screen_svg(
            active_step=3,
            title="Revisao",
            subtitle="Resumo publico antes da candidata.",
            footer="Enter conclui | B volta | Esc cancela",
            panel_items=["Conexao agregada", "Ambiente informado", "Tela escolhida"],
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "06-complete",
        build_screen_svg(
            active_step=4,
            title="Concluido",
            subtitle="Candidata temporaria pronta para a proxima etapa.",
            footer="Enter sai",
            panel_items=["C5.1 allow-mock", "Writer bloqueado", "Config real intocada"],
            accent="#22c55e",
            layout_rotation_deg=90,
        ),
    )


def show_preview(out_dir: pathlib.Path, *, mpv_bin: str, auto_exit_sec: int) -> None:
    display = VisualDisplay(out_dir, mpv_bin=mpv_bin, enabled=True)
    try:
        paths = sorted((out_dir / "screens").glob("*.svg"))
        if not paths:
            raise VisualWizardError("preview indisponivel")
        deadline = time.time() + max(1, auto_exit_sec)
        index = 0
        while time.time() < deadline:
            path = paths[index % len(paths)]
            display.show(path.stem, path.read_text(encoding="utf-8"))
            index += 1
            time.sleep(2)
    finally:
        display.stop()


def show_wifi_list_preview(
    out_dir: pathlib.Path,
    *,
    mpv_bin: str,
    auto_exit_sec: int,
    rotation_key: str,
) -> dict[str, Any]:
    prepare_private_dir(out_dir)
    rotation = resolve_display_selection(rotation_key)
    layout_rotation_deg = int(rotation["rotation_deg"])
    networks, list_status = wifi_adapter.list_wifi_networks_for_local_ui(timeout_sec=8)
    selected = networks[0] if networks else None
    metadata = wifi_adapter.wifi_selection_public_metadata(networks, selected)
    display = VisualDisplay(out_dir, mpv_bin=mpv_bin, enabled=True)
    try:
        if networks:
            options = [
                Option(
                    f"wifi-{index}",
                    local_display_value(str(network["ssid"])),
                    f"Sinal {network['signal_bucket']} | {security_label(network.get('security_present'))}",
                )
                for index, network in enumerate(networks[:5])
            ]
            display.show(
                "02-wifi-list-preview",
                build_screen_svg(
                    active_step=1,
                    title="Redes Wi-Fi",
                    subtitle="Preview read-only. Nomes aparecem somente nesta tela local.",
                    footer="Preview automatico",
                    options=options,
                    selected_index=0,
                    panel_items=[
                        f"Redes encontradas: {len(networks)}",
                        "Sem alteracao de rede.",
                        "Sem SSID em status/resumo.",
                    ],
                    layout_rotation_deg=layout_rotation_deg,
                ),
            )
        else:
            display.show(
                "02-wifi-list-preview-empty",
                build_screen_svg(
                    active_step=1,
                    title="Redes Wi-Fi",
                    subtitle="Preview read-only sem redes disponiveis agora.",
                    footer="Preview automatico",
                    panel_items=[
                        f"Listagem: {list_status}",
                        "Sem alteracao de rede.",
                        "Sem identificadores publicados.",
                    ],
                    accent="#ef4444",
                    layout_rotation_deg=layout_rotation_deg,
                ),
            )
        time.sleep(max(1, auto_exit_sec))
    finally:
        display.stop()
    status = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "mode": "wifi_list_preview",
        "list_status": list_status,
        "rotation_degrees": layout_rotation_deg,
        **metadata,
        "ssid_written_to_public_status": False,
        "password_written_to_public_status": False,
        "network_changed": False,
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
    }
    atomic_write_private_json(out_dir / "wifi-list-preview-status.json", status, out_dir)
    return status


def run_scripted(out_dir: pathlib.Path, environment_id: str, rotation_key: str, network_step: str) -> dict[str, Any]:
    prepare_private_dir(out_dir)
    display = VisualDisplay(out_dir, enabled=False)
    generate_preview_screens(out_dir)
    environment = validate_environment_id(environment_id)
    rotation = resolve_display_selection(rotation_key)
    network = resolve_network_scripted(network_step)
    status = write_visual_artifacts(out_dir, environment, rotation, network)
    display.show(
        "06-complete-scripted",
        build_screen_svg(
            active_step=4,
            title="Concluido",
            subtitle="Candidata temporaria gerada por fluxo controlado.",
            footer="Fim do modo scripted",
            panel_items=["C5.1 allow-mock", "Sem writer", "Sem config real"],
            accent="#22c55e",
            layout_rotation_deg=int(rotation["rotation_deg"]),
        ),
    )
    return status


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_raises(func: Any, message: str) -> None:
    try:
        func()
    except Exception:
        return
    raise AssertionError(message)


def assert_artifact_permissions(out_dir: pathlib.Path) -> None:
    assert_true(file_mode(out_dir) == setup.PRIVATE_DIR_MODE, "out-dir mode should be 0700")
    for name in (CANDIDATE_FILENAME, STATUS_FILENAME, SUMMARY_FILENAME, ORIENTATION_FILENAME):
        path = out_dir / name
        assert_true(path.exists(), f"{name} should exist")
        assert_true(file_mode(path) == setup.PRIVATE_FILE_MODE, f"{name} should be 0600")
        assert_true(setup.path_is_under(path.resolve(strict=True), setup.TMP_ROOT), f"{name} should stay under /tmp")
    screens_dir = out_dir / "screens"
    assert_true(screens_dir.exists(), "screens dir should exist")
    assert_true(file_mode(screens_dir) == setup.PRIVATE_DIR_MODE, "screens dir should be 0700")
    for path in screens_dir.glob("*.svg"):
        assert_true(file_mode(path) == setup.PRIVATE_FILE_MODE, f"{path.name} should be 0600")


def run_self_test() -> None:
    assert_raises(lambda: require_tmp_dir("/var/tmp/dadooh-c9-9"), "out-dir outside /tmp should fail")
    assert_raises(lambda: validate_environment_id("bad environment"), "environment with space should fail")
    assert_raises(lambda: validate_environment_id("api_key"), "api_key-like environment should fail")
    assert_raises(lambda: resolve_display_selection("diagonal"), "unknown display option should fail")

    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c9-9-visual-wizard-self-test-", dir="/tmp"))
    try:
        synthetic_ssid = "TEST_WIFI_SHOULD_NOT_LEAK"
        synthetic_password = "TEST_PASSWORD_SHOULD_NOT_LEAK"
        assert_true(
            text_field_display_hint(synthetic_ssid, hidden=False, show_plain_value=True) == synthetic_ssid,
            "Wi-Fi network field should show local typed value",
        )
        password_hint = text_field_display_hint(synthetic_password, hidden=True, show_plain_value=False)
        assert_true(password_hint == "*" * len(synthetic_password), "Wi-Fi password should stay masked")
        assert_true(synthetic_password not in password_hint, "Wi-Fi password hint should not leak value")
        count_hint = text_field_display_hint(synthetic_ssid, hidden=False, show_plain_value=False)
        assert_true(
            synthetic_ssid not in count_hint and "caracteres digitados" in count_hint,
            "count-only mode should not show raw value",
        )
        local_wifi_options = wifi_adapter.parse_wifi_network_list(
            "TEST_WIFI_SHOULD_NOT_LEAK:88:WPA2\nTEST_WIFI_WEAK:22:--\n",
        )
        assert_true(local_wifi_options[0]["ssid"] == synthetic_ssid, "local Wi-Fi list should keep SSID for HDMI")
        local_metadata = wifi_adapter.wifi_selection_public_metadata(local_wifi_options, local_wifi_options[0])
        assert_true(local_metadata["wifi_networks_found_count"] == 2, "Wi-Fi count should be public")
        assert_true(local_metadata["selected_network_present"] is True, "selected network presence should be public")
        assert_true(local_metadata["selected_network_signal_bucket"] == "strong", "signal bucket should be public")
        assert_true(local_metadata["selected_network_security_present"] is True, "security presence should be public")
        assert_true(synthetic_ssid not in json.dumps(local_metadata), "Wi-Fi metadata should not leak SSID")

        preview_dir = require_tmp_dir(str(root / "preview"))
        prepare_private_dir(preview_dir)
        generate_preview_screens(preview_dir)
        orientation_preview_path = next((preview_dir / "screens").glob("*-01-orientation.svg"))
        orientation_preview_text = orientation_preview_path.read_text(encoding="utf-8")
        assert_true("orientation-preview" in orientation_preview_text, "orientation step should include visual preview")
        assert_true("DADOOH" not in orientation_preview_text, "orientation marker should use vector blocks, not text")
        assert_true(
            any((preview_dir / "screens").glob("*-01-orientation-confirm-portrait.svg")),
            "preview should generate orientation confirmation screen",
        )
        portrait_confirm = next((preview_dir / "screens").glob("*-01-orientation-confirm-portrait.svg"))
        assert_true(
            "orientation-preview" in portrait_confirm.read_text(encoding="utf-8"),
            "orientation confirmation should keep visual preview",
        )
        portrait_connection = next((preview_dir / "screens").glob("*-02-connection.svg"))
        portrait_connection_text = portrait_connection.read_text(encoding="utf-8")
        assert_true('width="720" height="1280"' in portrait_connection_text, "portrait preview should use native portrait canvas")
        assert_true(
            'data-display-rotation-deg="90"' in portrait_connection_text,
            "portrait preview should carry display rotation contract",
        )
        assert_true(file_mode(preview_dir / "screens") == setup.PRIVATE_DIR_MODE, "preview screens should be 0700")

        out_dir = require_tmp_dir(str(root / "out"))
        status = run_scripted(
            out_dir,
            environment_id="ENV-PRODUTO-VISUAL-01",
            rotation_key="portrait_left",
            network_step="configured_wifi",
        )
        assert_true(status["schema_version"] == SCHEMA_VERSION, "status schema should be C9.9")
        assert_true(status["state"] == "candidate_ready", "status should be candidate_ready")
        assert_true(status["interface"]["mode"] == INTERFACE_MODE, "status should record visual mode")
        assert_true(status["interface"]["linux_prompt_visible"] is False, "linux prompt should be false")
        assert_true(status["interface"]["chromium_used"] is False, "chromium should be false")
        assert_true(status["interface"]["desktop_used"] is False, "desktop should be false")
        assert_true(status["interface"]["visual_renderer"] == visual_renderer_name(), "visual renderer should be recorded")
        assert_true(status["interface"]["mpv_video_mode"] == MPV_VIDEO_MODE, "MPV video mode should be recorded")
        assert_true(status["network"]["network_step"] == "existing_configured_wifi", "network step should use configured Wi-Fi")
        assert_true(status["network"]["dedicated_profile_persistent"] is True, "configured Wi-Fi should be persistent")
        assert_true(status["environment"]["environment_id_present"] is True, "environment should be present")
        assert_true(status["guardrails"]["real_config_read"] is False, "real config should not be read")
        assert_true(status["guardrails"]["real_config_written"] is False, "real config should not be written")
        assert_true(status["guardrails"]["writer_called"] is False, "writer should not be called")
        assert_true(status["guardrails"]["main_player_mpv_called"] is False, "main player MPV should be false")
        assert_true(
            status["guardrails"]["visual_renderer_mpv_called"] is visual_renderer_uses_mpv(),
            "visual renderer MPV flag should match renderer",
        )
        assert_true(status["guardrails"]["hotspot_created"] is False, "hotspot should be false")
        assert_true(status["guardrails"]["portal_created"] is False, "portal should be false")
        assert_artifact_permissions(out_dir)

        candidate = json.loads((out_dir / CANDIDATE_FILENAME).read_text(encoding="utf-8"))
        orientation_contract = json.loads((out_dir / ORIENTATION_FILENAME).read_text(encoding="utf-8"))
        assert_true(candidate["environment_id"] == "ENV-PRODUTO-VISUAL-01", "candidate should keep environment")
        assert_true(candidate["rotation_deg"] == 270, "candidate should keep rotation")
        assert_true(orientation_contract["rotation_deg"] == 270, "orientation contract should keep rotation")
        assert_true(orientation_contract["layout_mode"] == "portrait", "orientation contract should expose layout mode")
        assert_true(orientation_contract["contains_sensitive_data"] is False, "orientation contract should stay public-safe")
        assert_true(candidate["setup_source"] == SETUP_SOURCE, "candidate should record source")
        assert_true(candidate["setup_interface"] == INTERFACE_MODE, "candidate should record interface")
        assert_true(candidate["setup_network_step"] == "existing_configured_wifi", "candidate should record network")
        allow_mock = contract.validate_candidate_config(candidate, "allow-mock")
        real_dry_run = contract.validate_candidate_config(candidate, "real-dry-run")
        assert_true(allow_mock["valid"], "C9.9 candidate should pass allow-mock")
        assert_true(not real_dry_run["valid"], "C9.9 candidate should fail real-dry-run with placeholders")
        assert_sanitized_outputs(out_dir, "ENV-PRODUTO-VISUAL-01")
        public_text = output_text(out_dir)
        for forbidden in (synthetic_ssid, synthetic_password):
            assert_true(forbidden not in public_text, "Wi-Fi credentials should not be public artifacts")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run C9.9 local visual setup wizard.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Artifact directory under /tmp.")
    parser.add_argument("--mpv-bin", default="mpv", help="MPV binary for visual DRM rendering.")
    parser.add_argument("--environment-id", default="ENV-C9-9-VISUAL-SMOKE", help="Scripted environment_id.")
    parser.add_argument("--rotation-key", default="landscape", help="Scripted rotation key.")
    parser.add_argument("--network-step", default="configured_wifi", help="Scripted network step.")
    parser.add_argument("--auto-exit-sec", type=int, default=12, help="Preview display duration.")
    parser.add_argument("--show-preview", action="store_true", help="Display preview screens with MPV/DRM.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--self-test", action="store_true", help="Run self-tests and exit.")
    modes.add_argument("--preview-screens", action="store_true", help="Generate visual screens under /tmp and exit.")
    modes.add_argument("--wifi-list-preview", action="store_true", help="Display local read-only Wi-Fi list preview.")
    modes.add_argument("--scripted", action="store_true", help="Generate a scripted candidate without MPV.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        try:
            run_self_test()
        except AssertionError:
            print("error: self-test failed", file=sys.stderr)
            return 1
        except Exception:
            print("error: self-test failed", file=sys.stderr)
            return 1
        print("self-test: ok")
        return 0

    try:
        out_dir = require_tmp_dir(args.out_dir)
        prepare_private_dir(out_dir)
        if args.preview_screens:
            generate_preview_screens(out_dir)
            if args.show_preview:
                show_preview(out_dir, mpv_bin=args.mpv_bin, auto_exit_sec=args.auto_exit_sec)
            print(out_dir / "screens")
            return 0
        if args.wifi_list_preview:
            status = show_wifi_list_preview(
                out_dir,
                mpv_bin=args.mpv_bin,
                auto_exit_sec=args.auto_exit_sec,
                rotation_key=args.rotation_key,
            )
            print(json.dumps(status, indent=2, sort_keys=True))
            return 0
        if args.scripted:
            status = run_scripted(out_dir, args.environment_id, args.rotation_key, args.network_step)
            print(json.dumps(status, indent=2, sort_keys=True))
            return 0
        run_visual_wizard(out_dir, mpv_bin=args.mpv_bin)
        return 0
    except VisualWizardAbort:
        try:
            write_cancelled_artifact(require_tmp_dir(args.out_dir))
        except Exception:
            pass
        return 130
    except KeyboardInterrupt:
        try:
            write_cancelled_artifact(require_tmp_dir(args.out_dir))
        except Exception:
            pass
        return 130
    except Exception:
        try:
            write_failed_artifact(require_tmp_dir(args.out_dir), "visual_wizard_failed")
        except Exception:
            pass
        print("error: setup visual indisponivel", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
