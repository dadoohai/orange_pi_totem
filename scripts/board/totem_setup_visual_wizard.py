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
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


sys.dont_write_bytecode = True

import totem_config_contract_validate as contract
import totem_setup_minimal_server as setup
import totem_wifi_nm_adapter as wifi_adapter

try:
    import totem_qr_pairing_client as pairing_client
except ModuleNotFoundError:
    pairing_client = None


SCHEMA_VERSION = "dadooh-c9.9-visual-wizard-local.v1"
SETUP_SOURCE = "c9.9-visual-wizard-local"
INTERFACE_MODE = "local_visual_mpv_drm_keyboard_controlled"
DEFAULT_OUT_DIR = "/tmp/dadooh-c9-9-visual-wizard"
DEFAULT_WIFI_SECRETS_DIR = "/tmp/dadooh-c9-9-visual-wifi-secrets"
WIFI_APPLY_DIRNAME = "wifi-persistent"
PAIRING_DIRNAME = "qr-pairing"
PAIRING_SESSION_SCHEMA = "dadooh.c21.totem_qr_pairing.session.v1"
PAIRING_RESULT_SCHEMA = "dadooh.c21.totem_qr_pairing.result.v1"
PAIRING_PRIVATE_VALUES_SCHEMA = "dadooh.c21.totem_qr_pairing.private_values.v1"
PAIRING_DEFAULT_AUTHORIZE_BASE_URL = "https://home.dadooh.ai/totem/activate"
PAIRING_MANUAL_ENTRY_URL = "home.dadooh.ai/totem/activate"
PAIRING_DEFAULT_BACKEND_BASE_URL = "https://api-lbyvh5uf6q-uc.a.run.app"
PAIRING_DEFAULT_API_URL = "https://api-lbyvh5uf6q-uc.a.run.app/search"
PAIRING_DEFAULT_ENVIRONMENT_ID = "11111111-2222-4333-8444-555555555555"
PAIRING_DEFAULT_STATION_ID = "22222222-3333-4444-8555-666666666666"
PAIRING_DEFAULT_MOCK_API_KEY = "C21_MOCK_DEVICE_KEY_NOT_FOR_PROD_1234567890"
PAIRING_MODE = os.environ.get("TOTEM_VISUAL_WIZARD_PAIRING_MODE", "mock").strip().lower()
PAIRING_REAL_TIMEOUT_SEC = float(os.environ.get("TOTEM_VISUAL_WIZARD_PAIRING_TIMEOUT_SEC", "1800"))
PAIRING_REAL_MIN_WATCHDOG_SEC = 600.0
PAIRING_REAL_MAX_SERVER_TIMEOUT_SEC = float(
    os.environ.get("TOTEM_VISUAL_WIZARD_PAIRING_MAX_SERVER_TIMEOUT_SEC", "1800")
)
PAIRING_REAL_HTTP_TIMEOUT_SEC = float(os.environ.get("TOTEM_VISUAL_WIZARD_PAIRING_HTTP_TIMEOUT_SEC", "8"))
PAIRING_REAL_MAX_RENEWALS = max(
    0,
    min(3, int(os.environ.get("TOTEM_VISUAL_WIZARD_PAIRING_MAX_RENEWALS", "2"))),
)
PAIRING_QR_MAX_PAYLOAD_BYTES = 200
PAIRING_STATES = {
    "pending",
    "authorized",
    "expired",
    "denied",
    "backend_unavailable",
    "empty_environment_list",
    "already_used",
    "local_timeout",
}
PAIRING_REAL_TERMINAL_STATES = frozenset(
    {"expired", "denied", "backend_unavailable", "already_used", "empty_environment_list", "local_timeout"}
)
WIFI_TIMEOUT_SEC = 45
WIFI_LIST_REFRESH_SEC = 10.0
WIFI_LIST_TIMEOUT_SEC = 4
WIFI_LIST_PAGE_SIZE = 5
WIFI_LIST_LANDSCAPE_PAGE_SIZE = 4
MAX_PANEL_ITEMS = 3
CLOCK_IMPLAUSIBLE_LABEL = "Hora nao ajustada"
CLOCK_MIN_PLAUSIBLE_YEAR = 2024
CLOCK_MAX_PLAUSIBLE_YEAR = 2100
TEXT_INPUT_MIN_RENDER_INTERVAL_SEC = float(os.environ.get("TOTEM_VISUAL_WIZARD_INPUT_RENDER_INTERVAL_SEC", "0.10"))
TEXT_INPUT_REPEAT_DRAIN_SEC = float(os.environ.get("TOTEM_VISUAL_WIZARD_INPUT_REPEAT_DRAIN_SEC", "0.035"))
TEXT_INPUT_MAX_DRAIN_KEYS = int(os.environ.get("TOTEM_VISUAL_WIZARD_INPUT_MAX_DRAIN_KEYS", "80"))
WIFI_PERSISTENT_PROFILE_NAME = wifi_adapter.DEFAULT_PERSISTENT_PROFILE_NAME
ADAPTER_SCRIPT = pathlib.Path(__file__).with_name("totem_wifi_nm_adapter.py")
PRESENT_SETTLE_SEC = float(os.environ.get("TOTEM_VISUAL_WIZARD_PRESENT_SETTLE_SEC", "0.18"))
RESTART_MPV_PER_SCREEN = os.environ.get("TOTEM_VISUAL_WIZARD_RESTART_MPV_PER_SCREEN", "1") != "0"
MPV_VIDEO_MODE = os.environ.get("TOTEM_VISUAL_WIZARD_MPV_VIDEO_MODE", "drm").strip().lower()
DOUBLE_LOAD_PER_SCREEN = os.environ.get("TOTEM_VISUAL_WIZARD_DOUBLE_LOAD_PER_SCREEN", "1") != "0"
RENDERER_MODE = os.environ.get("TOTEM_VISUAL_WIZARD_RENDERER", "framebuffer").strip().lower()
PSF_FONT_PATH = os.environ.get("TOTEM_VISUAL_WIZARD_PSF_FONT", "/usr/share/consolefonts/Lat15-Fixed18.psf.gz")
APPLY_CONTEXT = os.environ.get("TOTEM_VISUAL_WIZARD_APPLY_CONTEXT", "candidate").strip().lower()
HOMOLOGATION_MODE = os.environ.get("TOTEM_VISUAL_WIZARD_HOMOLOGATION_MODE", "false").strip().lower() in {
    "1",
    "true",
    "yes",
}

LANDSCAPE_CANVAS_WIDTH = 1024
LANDSCAPE_CANVAS_HEIGHT = 768
PORTRAIT_CANVAS_WIDTH = 768
PORTRAIT_CANVAS_HEIGHT = 1024
CANVAS_WIDTH = LANDSCAPE_CANVAS_WIDTH
CANVAS_HEIGHT = LANDSCAPE_CANVAS_HEIGHT
BRAND = "Dadooh"
TITLE = "Configuracao do Totem"
STEPS = ("Tela", "Wi-Fi", "Ambiente", "Revisao", "Concluir")
PORTRAIT_STEP_LABELS = ("Tela", "Wi-Fi", "Amb.", "Revisao", "Fim")
NAVIGABLE_STEPS = (0, 1, 2, 3)
C17_2_VISUAL_SYSTEM_VERSION = "c17.2-appliance-ui.v1"
VISUAL = {
    "bg": "#07111f",
    "surface": "#111827",
    "surface_raised": "#151d2a",
    "surface_active": "#12324a",
    "surface_selected": "#0f3a55",
    "surface_input": "#f8fafc",
    "border": "#2f3d4a",
    "border_muted": "#334155",
    "text": "#f8fafc",
    "text_muted": "#cbd5e1",
    "text_dim": "#94a3b8",
    "text_dark": "#111827",
    "accent": "#06b6d4",
    "accent_strong": "#22d3ee",
    "accent_soft": "#164e63",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "footer": "#050b14",
}

CANDIDATE_FILENAME = "config.candidate.json"
STATUS_FILENAME = "setup-status.json"
SUMMARY_FILENAME = "summary.txt"
CANCELLED_FILENAME = "setup-cancelled.json"
FAILED_FILENAME = "setup-failed.json"
ORIENTATION_FILENAME = "orientation.json"
PUBLIC_ORIENTATION_PATH = pathlib.Path("/data/state/totem-display/orientation.json")
PRIVATE_SETTINGS_CONTEXT_PATH = pathlib.Path(
    os.environ.get("TOTEM_VISUAL_WIZARD_PRIVATE_SETTINGS_CONTEXT", "/data/state/totem-settings/last-settings.json")
)
PRIVATE_VALUES_SEED_PATH = pathlib.Path(
    os.environ.get("TOTEM_VISUAL_WIZARD_PRIVATE_VALUES_SEED", "/data/state/totem-settings/private-values.seed.json")
)
ENVIRONMENT_VALIDATION_TIMEOUT_SEC = float(
    os.environ.get("TOTEM_VISUAL_WIZARD_ENV_VALIDATION_TIMEOUT_SEC", "4.0")
)
ENVIRONMENT_VALIDATION_ENABLED = os.environ.get("TOTEM_VISUAL_WIZARD_ENV_VALIDATION_ENABLED", "1") != "0"

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
_CLOCK_LABEL_AUTO = object()


class VisualWizardAbort(RuntimeError):
    """Raised when the operator intentionally cancels the visual setup."""


class VisualWizardError(RuntimeError):
    """Public-safe visual wizard error."""


class VisualWizardStepJump(RuntimeError):
    """Raised when the operator chooses another top-level wizard step."""

    def __init__(self, step: int, *, focus_area: str = "content") -> None:
        self.step = step
        self.focus_area = focus_area
        super().__init__(f"wizard step jump: {step} focus={focus_area}")


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    description: str


@dataclass(frozen=True)
class EnvironmentPreflight:
    endpoint: str
    environment_exists: str
    environment_not_found: bool
    invalid_environment_id: bool
    validation_auth_required: bool
    validation_unavailable: bool
    content_available: str
    content_empty: bool
    requires_confirmation: bool
    confirmed_by_operator: bool


@dataclass
class WizardState:
    rotation: dict[str, str | int]
    rotation_status: str
    network: dict[str, Any] | None = None
    network_status: str = "pending"
    environment_id: str = ""
    environment_preflight: EnvironmentPreflight | None = None
    environment_status: str = "pending"


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
        return ScreenLayout(rotation, PORTRAIT_CANVAS_WIDTH, PORTRAIT_CANVAS_HEIGHT, "portrait", note, 48)
    note = "Layout invertido" if rotation == 180 else "Layout paisagem"
    return ScreenLayout(rotation, LANDSCAPE_CANVAS_WIDTH, LANDSCAPE_CANVAS_HEIGHT, "landscape", note, 76)


def wifi_list_page_size(layout_rotation_deg: int = 0) -> int:
    return WIFI_LIST_PAGE_SIZE if screen_layout(layout_rotation_deg).portrait else WIFI_LIST_LANDSCAPE_PAGE_SIZE


NETWORK_OPTIONS = (
    Option(
        "configured_wifi",
        "Usar Wi-Fi ja configurado",
        "Mantem o perfil atual do produto.",
    ),
    Option(
        "wifi_select",
        "Selecionar rede Wi-Fi",
        "Escolhe uma rede na lista local.",
    ),
    Option(
        "bench_mock",
        "Continuar em modo de bancada",
        "Segue sem alterar a rede.",
    ),
)

ENVIRONMENT_ENTRY_OPTIONS = (
    Option(
        "qr_pairing",
        "Entrar com codigo/QR",
        "Autoriza pelo celular e escolhe ambiente.",
    ),
    Option(
        "manual_environment",
        "Digitar ID manual",
        "Usa o caminho tecnico de suporte.",
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


def local_datetime_label(now: time.struct_time | None = None) -> str:
    current = now if now is not None else time.localtime()
    if current.tm_year < CLOCK_MIN_PLAUSIBLE_YEAR or current.tm_year > CLOCK_MAX_PLAUSIBLE_YEAR:
        return CLOCK_IMPLAUSIBLE_LABEL
    return f"{current.tm_mday:02d}/{current.tm_mon:02d}/{current.tm_year:04d} {current.tm_hour:02d}:{current.tm_min:02d}"


def header_note_label(clock_label: object = _CLOCK_LABEL_AUTO) -> str:
    if clock_label is _CLOCK_LABEL_AUTO:
        return local_datetime_label()
    if clock_label is None:
        return ""
    return str(clock_label)


def header_note_position(layout: ScreenLayout) -> tuple[int, int]:
    if layout.portrait:
        return layout.width - layout.margin_x - 220, 58
    return layout.width - layout.margin_x - 156, 54


def step_indicator(
    active_step: int,
    *,
    layout_rotation_deg: int = 0,
    focused_step: int | None = None,
    focus_area: str = "content",
) -> str:
    parts = []
    layout = screen_layout(layout_rotation_deg)
    x = layout.margin_x
    y = 86 if layout.portrait else 92
    focused = active_step if focused_step is None else focused_step
    step_focus = focus_area == "steps"
    for index, step in enumerate(STEPS):
        active = index == active_step
        focused_item = step_focus and index == focused
        if active:
            fill = VISUAL["surface_active"]
            text_fill = VISUAL["text"]
        elif focused_item:
            fill = "#1c2a3c"
            text_fill = VISUAL["text"]
        else:
            fill = "#172033"
            text_fill = VISUAL["text_muted"]
        if focused_item:
            stroke = VISUAL["accent_strong"]
            rail_fill = VISUAL["accent_strong"]
            stroke_width = 3
        elif active:
            stroke = VISUAL["accent_soft"]
            rail_fill = "#64748b"
            stroke_width = 1
        else:
            stroke = VISUAL["border_muted"]
            rail_fill = ""
            stroke_width = 1
        width = 124 if layout.portrait else (140 if index in {0, 4} else 136)
        label = step if not layout.portrait else PORTRAIT_STEP_LABELS[index]
        font_size = 14 if layout.portrait else 16
        rail = (
            f'<rect x="{x}" y="{y}" width="6" height="42" rx="3" fill="{rail_fill}"/>'
            if active or focused_item
            else ""
        )
        parts.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="42" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"/>'
            f"{rail}"
            f'<text x="{x + 12}" y="{y + 28}" font-family="Arial, DejaVu Sans, sans-serif" '
            f'font-size="{font_size}" font-weight="700" fill="{text_fill}">{index + 1}. {escape_text(label)}</text>'
        )
        x += width + (8 if layout.portrait else 12)
    return "\n  ".join(parts)


def option_cards(
    options: list[Option],
    selected_index: int,
    *,
    layout_rotation_deg: int = 0,
    has_focus: bool = True,
) -> str:
    parts = []
    layout = screen_layout(layout_rotation_deg)
    x = layout.margin_x
    y = 314 if layout.portrait else 266
    card_width = layout.width - (layout.margin_x * 2) if layout.portrait else 608
    card_height = 98 if layout.portrait else 82
    label_width = 34 if layout.portrait else 28
    description_width = 50 if layout.portrait else 42
    for index, option in enumerate(options[:5]):
        active = index == selected_index
        fill = VISUAL["surface_selected"] if active and has_focus else ("#183047" if active else VISUAL["surface"])
        underlay_fill = "#0a1628" if active and has_focus else "#0a111f"
        title_fill = VISUAL["text"] if active else "#eef5ff"
        body_fill = VISUAL["text_muted"] if active else "#aebbd0"
        marker_fill = VISUAL["accent_strong"] if active and has_focus else ("#64748b" if active else "#263244")
        marker_text_fill = VISUAL["text_dark"] if active and has_focus else VISUAL["text_dim"]
        rail_fill = VISUAL["accent_strong"] if active and has_focus else ("#64748b" if active else "#334155")
        marker = ">" if active and has_focus else str(index + 1)
        parts.append(
            f'<rect x="{x + 8}" y="{y + 8}" width="{card_width}" height="{card_height}" rx="8" fill="{underlay_fill}"/>'
            f'<rect data-option-card="true" x="{x}" y="{y}" width="{card_width}" height="{card_height}" rx="8" fill="{fill}"/>'
            f'<rect x="{x}" y="{y}" width="8" height="{card_height}" rx="4" fill="{rail_fill}"/>'
            f'<rect x="{x + 26}" y="{y + 20}" width="42" height="42" rx="8" fill="{marker_fill}"/>'
            f'<text x="{x + 38}" y="{y + 48}" font-family="Arial, DejaVu Sans, sans-serif" font-size="20" '
            f'font-weight="700" fill="{marker_text_fill}">{escape_text(marker)}</text>'
            f'{svg_lines(option.label, x=x + 88, y=y + 37, size=23, fill=title_fill, width=label_width, line_gap=28, max_lines=1, weight=700)}'
            f'{svg_lines(option.description, x=x + 88, y=y + 68, size=17, fill=body_fill, width=description_width, line_gap=22, max_lines=1)}'
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
    panel_x = layout.margin_x if layout.portrait else 708
    panel_width = layout.width - (layout.margin_x * 2) if layout.portrait else 240
    panel_y = panel_y if panel_y is not None else (760 if layout.portrait else 230)
    panel_height = min(300 if layout.portrait else 330, max(190, layout.height - panel_y - 104))
    # The framebuffer renderer uses a fixed-width PSF font. Twenty columns keep
    # both text lines inside the compact landscape panel at the real glyph width.
    text_width = 50 if layout.portrait else 20
    y = panel_y + 58
    bullet_parts = []
    for item in items[:MAX_PANEL_ITEMS]:
        bullet_parts.append(
            f'<rect x="{panel_x + 31}" y="{y - 13}" width="10" height="10" rx="3" fill="{VISUAL["accent_strong"]}"/>'
            f'{svg_lines(item, x=panel_x + 56, y=y, size=17, fill=VISUAL["text_muted"], width=text_width, line_gap=24, max_lines=2)}'
        )
        y += 54 if layout.portrait else 66
    return f"""
  <rect id="info-panel" x="{panel_x}" y="{panel_y}" width="{panel_width}" height="{panel_height}" rx="8" fill="{VISUAL["surface_raised"]}" stroke="{VISUAL["border"]}"/>
  <rect x="{panel_x}" y="{panel_y}" width="7" height="{panel_height}" rx="4" fill="{VISUAL["accent"]}"/>
  <text x="{panel_x + 32}" y="{panel_y + 40}" font-family="Arial, DejaVu Sans, sans-serif" font-size="24" font-weight="700" fill="{VISUAL["text"]}">{escape_text(title)}</text>
  {' '.join(bullet_parts)}
"""


def field_panel(label: str, value_hint: str, note: str, *, layout_rotation_deg: int = 0) -> str:
    layout = screen_layout(layout_rotation_deg)
    panel_x = layout.margin_x
    panel_y = 360 if layout.portrait else 300
    panel_width = layout.width - (layout.margin_x * 2) if layout.portrait else 608
    text_width = 40 if layout.portrait else 44
    label_width = 40 if layout.portrait else 42
    note_width = 48 if layout.portrait else 44
    label_svg = svg_lines(
        label,
        x=panel_x + 36,
        y=panel_y + 46,
        size=20,
        fill=VISUAL["text_muted"],
        width=label_width,
        line_gap=24,
        max_lines=1,
        weight=700,
    )
    value_svg = svg_lines(
        value_hint,
        x=panel_x + 36,
        y=panel_y + 92,
        size=26,
        fill=VISUAL["text"],
        width=text_width,
        line_gap=34,
        max_lines=2,
        weight=700,
    )
    return f"""
  <rect x="{panel_x + 8}" y="{panel_y + 8}" width="{panel_width}" height="142" rx="8" fill="#0a1628"/>
  <rect x="{panel_x}" y="{panel_y}" width="{panel_width}" height="142" rx="8" fill="{VISUAL["surface_raised"]}"/>
  <rect x="{panel_x}" y="{panel_y}" width="8" height="142" rx="4" fill="{VISUAL["accent"]}"/>
  {label_svg}
  {value_svg}
  {svg_lines(note, x=panel_x + 36, y=panel_y + 174, size=18, fill=VISUAL["text_dim"], width=note_width, line_gap=22, max_lines=1)}
"""


def summary_rows_svg(rows: list[tuple[str, str]], *, layout_rotation_deg: int = 0) -> str:
    layout = screen_layout(layout_rotation_deg)
    x = layout.margin_x
    y = 292 if layout.portrait else 282
    width = layout.width - (layout.margin_x * 2) if layout.portrait else 608
    row_height = 82 if layout.portrait else 76
    gap = 12
    parts = []
    for index, (label, value) in enumerate(rows[:4]):
        row_y = y + index * (row_height + gap)
        parts.append(
            f'<rect x="{x}" y="{row_y}" width="{width}" height="{row_height}" rx="8" fill="{VISUAL["surface"]}" stroke="{VISUAL["border"]}" stroke-width="2"/>'
            f'<rect x="{x}" y="{row_y}" width="8" height="{row_height}" rx="4" fill="{VISUAL["accent"]}"/>'
            f'<text x="{x + 32}" y="{row_y + 32}" font-family="Arial, DejaVu Sans, sans-serif" font-size="17" font-weight="700" fill="{VISUAL["text_dim"]}">{escape_text(label)}</text>'
            f'{svg_lines(value, x=x + 32, y=row_y + 62, size=22, fill=VISUAL["text"], width=42 if layout.portrait else 34, line_gap=26, max_lines=1, weight=700)}'
        )
    return "\n  ".join(parts)


def footer_chip_width(action: str, layout: ScreenLayout) -> int:
    return max(132 if not layout.portrait else 116, len(action) * (11 if not layout.portrait else 10) + 42)


def visible_footer_actions(actions: list[str], layout: ScreenLayout) -> list[str]:
    if not actions:
        return []
    chip_gap = 12 if not layout.portrait else 8
    max_width = layout.width - (layout.margin_x * 2)

    def total_width(indices: list[int]) -> int:
        if not indices:
            return 0
        return sum(footer_chip_width(actions[index], layout) for index in indices) + chip_gap * (len(indices) - 1)

    required = {0}
    required.update(index for index, action in enumerate(actions) if action.lower().startswith("esc"))
    selected = sorted(required)
    if total_width(selected) > max_width:
        selected = [0]
    for index in range(len(actions)):
        if index in selected:
            continue
        candidate = sorted([*selected, index])
        if total_width(candidate) <= max_width:
            selected = candidate
    return [actions[index] for index in selected]


def footer_text(text: str, *, layout_rotation_deg: int = 0) -> str:
    layout = screen_layout(layout_rotation_deg)
    footer_h = 82
    footer_y = layout.height - footer_h
    actions = [part.strip() for part in str(text or "").split("|") if part.strip()]
    primary = actions[0] if actions else str(text or "")
    chip_gap = 12 if not layout.portrait else 8
    x = layout.margin_x
    chips = []
    for index, action in enumerate(visible_footer_actions(actions, layout)):
        width = footer_chip_width(action, layout)
        if index == 0:
            fill = VISUAL["accent_strong"]
            text_fill = VISUAL["text_dark"]
        else:
            fill = VISUAL["surface_active"] if index == 1 else VISUAL["surface"]
            text_fill = VISUAL["text"]
        chips.append(
            f'<rect x="{x}" y="{footer_y + 18}" width="{width}" height="46" rx="8" fill="{fill}"/>'
            f'<text x="{x + 22}" y="{footer_y + 48}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" font-weight="700" fill="{text_fill}">{escape_text(action)}</text>'
        )
        x += width + chip_gap
    if not chips and primary:
        chips.append(
            f'<text x="{layout.margin_x}" y="{footer_y + 50}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" font-weight="700" fill="{VISUAL["text"]}">{escape_text(primary)}</text>'
        )
    return f"""
  <rect x="0" y="{footer_y}" width="{layout.width}" height="{footer_h}" fill="{VISUAL["footer"]}"/>
  <rect x="0" y="{footer_y}" width="{layout.width}" height="3" fill="{VISUAL["accent_soft"]}"/>
  {' '.join(chips)}
"""


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
        x = (layout.width - outer_w) // 2 if layout.portrait else 756
    if y is None:
        y = 610 if layout.portrait else 300
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
    <rect id="orientation-preview-shell" x="{x - 30}" y="{y - 54}" width="292" height="286" rx="8" fill="#111827" stroke="#334155"/>
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
    suppress_landscape_info_panel: bool = False,
    focus_area: str = "content",
    focused_step: int | None = None,
    clock_label: object = _CLOCK_LABEL_AUTO,
) -> str:
    layout = screen_layout(layout_rotation_deg)
    options_svg = (
        option_cards(
            options,
            selected_index,
            layout_rotation_deg=layout_rotation_deg,
            has_focus=focus_area == "content",
        )
        if options
        else ""
    )
    field_svg = (
        field_panel(field_label, field_value_hint, field_note, layout_rotation_deg=layout_rotation_deg)
        if field_label is not None
        else ""
    )
    if layout.portrait:
        if field_label is not None:
            panel_y = 590
        elif extra_svg:
            panel_y = 650 if active_step == 3 else 770
        else:
            panel_y = 760 if options and len(options) >= 5 else 650
        title_y = 188
        subtitle_y = 224
        subtitle_width = 46
    else:
        panel_y = 230
        title_y = 198
        subtitle_y = 234
        subtitle_width = 52
    note_x, note_y = header_note_position(layout)
    safe_panel_items = panel_items or []
    if suppress_landscape_info_panel and not layout.portrait:
        safe_panel_items = []
    layout_note = header_note_label(clock_label)
    panel_svg = info_panel(
        safe_panel_items,
        title=panel_title,
        layout_rotation_deg=layout_rotation_deg,
        panel_y=panel_y,
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" data-display-rotation-deg="{layout.rotation_deg}" data-layout-mode="{layout.mode}" role="img" aria-label="Dadooh setup visual wizard">
  <rect width="{layout.width}" height="{layout.height}" fill="{VISUAL["bg"]}"/>
  <rect x="0" y="0" width="{layout.width}" height="12" fill="{accent}"/>
  <rect x="0" y="12" width="{layout.width}" height="136" fill="{VISUAL["surface"]}"/>
  <rect x="{layout.margin_x}" y="32" width="120" height="38" rx="8" fill="{VISUAL["surface_active"]}" stroke="{accent}"/>
  <text x="{layout.margin_x + 18}" y="58" font-family="Arial, DejaVu Sans, sans-serif" font-size="22" font-weight="700" fill="{VISUAL["text"]}">{BRAND}</text>
  <text x="{layout.margin_x + 140}" y="57" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" fill="{VISUAL["text_dim"]}">{TITLE}</text>
  <text x="{note_x}" y="{note_y}" font-family="Arial, DejaVu Sans, sans-serif" font-size="16" fill="{VISUAL["text_dim"]}">{escape_text(layout_note)}</text>
  {step_indicator(active_step, layout_rotation_deg=layout_rotation_deg, focused_step=focused_step, focus_area=focus_area)}
  <text x="{layout.margin_x}" y="{title_y}" font-family="Arial, DejaVu Sans, sans-serif" font-size="38" font-weight="700" fill="{VISUAL["text"]}">{escape_text(title)}</text>
  {svg_lines(subtitle, x=layout.margin_x + 2, y=subtitle_y, size=19, fill=VISUAL["text_muted"], width=subtitle_width, line_gap=28, max_lines=1)}
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
        self.draw_target: mmap.mmap | bytearray = self.fb

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
            self.draw_target[offset : offset + len(row)] = row

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
        frame = bytearray(self.stride * self.height)
        previous_target = self.draw_target
        self.draw_target = frame
        try:
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
            self.fb[:] = frame
            self.fb.flush()
        finally:
            self.draw_target = previous_target


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


def read_key(timeout_sec: float | None = None) -> str:
    if timeout_sec is not None:
        ready, _, _ = select.select([sys.stdin], [], [], max(0.0, timeout_sec))
        if not ready:
            return "timeout"
    data = os.read(sys.stdin.fileno(), 1)
    if data in {b"\r", b"\n"}:
        return "enter"
    if data in {b"\x7f", b"\x08"}:
        return "backspace"
    if data == b"\t":
        return "tab"
    if data == b"\x02":
        return "back"
    if data == b"\x10":
        return "toggle_secret"
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
        if rest == b"[5~":
            return "pageup"
        if rest == b"[6~":
            return "pagedown"
        if rest in {b"[H", b"OH"}:
            return "home"
        if rest in {b"[F", b"OF"}:
            return "end"
        if rest in {b"[3~", b"[P"}:
            return "delete"
        if rest in {b"OQ", b"[[B", b"[12~"}:
            return "f2"
        return "unknown"
    try:
        char = data.decode("utf-8")
    except UnicodeDecodeError:
        return "unknown"
    if len(char) == 1 and 32 <= ord(char) <= 126:
        return char
    return "unknown"


C1523_DEBUG_ROOT = pathlib.Path("/data/state/totem-debug/c15-2-3")


def c1523_monitor_dir() -> pathlib.Path | None:
    raw = os.environ.get("TOTEM_C15_2_3_MONITOR_DIR", "").strip()
    if not raw:
        marker = C1523_DEBUG_ROOT / "current-run-dir"
        try:
            if marker.exists() and not marker.is_symlink():
                raw = marker.read_text(encoding="utf-8").splitlines()[0].strip()
        except Exception:
            raw = ""
    if not raw:
        return None
    path = pathlib.Path(raw)
    try:
        resolved = path.resolve(strict=False)
        root = C1523_DEBUG_ROOT.resolve(strict=False)
    except Exception:
        return None
    if root not in [resolved, *resolved.parents] or not path.is_dir():
        return None
    return path


def c1523_phase(phase: str, **fields: object) -> None:
    run_dir = c1523_monitor_dir()
    if run_dir is None:
        return
    safe_fields = []
    for key, value in sorted(fields.items()):
        safe_key = "".join(ch for ch in str(key) if ch.isalnum() or ch in "_-")[:40]
        safe_value = "".join(ch for ch in str(value) if ch.isalnum() or ch in "._:-")[:80]
        if safe_key and safe_value:
            safe_fields.append(f"{safe_key}={safe_value}")
    line = (
        f"{utc_timestamp()} uptime={time.monotonic():.3f} pid={os.getpid()} "
        f"phase={phase}"
    )
    if safe_fields:
        line += " " + " ".join(safe_fields)
    try:
        path = run_dir / "phases.log"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        return


def draw_welcome(display: VisualDisplay) -> None:
    display.show(
        "01-welcome",
        build_screen_svg(
            active_step=0,
            title="Bem-vindo",
            subtitle="Vamos ajustar tela, rede e ambiente.",
            footer="Enter inicia | Esc cancela",
            panel_title="Fluxo",
            panel_items=[
                "Teclado local.",
                "Sem shell na tela.",
                "Player volta ao final.",
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


def read_advertised_action(*allowed_keys: str) -> str:
    allowed = set(allowed_keys)
    while True:
        key = read_key()
        if key in allowed:
            return key
        if key in {"q", "Q"}:
            raise VisualWizardAbort("setup visual cancelado pelo operador")


def adjacent_navigable_step(step: int, delta: int) -> int:
    steps = list(NAVIGABLE_STEPS)
    if step not in steps:
        return steps[0]
    index = steps.index(step)
    return steps[(index + delta) % len(steps)]


def option_footer(*, focus_area: str, primary: str, allow_back: bool) -> str:
    if focus_area == "steps":
        return "Enter abre | Esc volta"
    suffix = "Esc volta" if allow_back else "Esc cancela"
    return f"{primary} | Cima menu | Baixo escolhe | {suffix}"


def handle_step_focus_key(key: str, *, focused_step: int, active_step: int) -> tuple[str, int]:
    if key == "left":
        next_step = adjacent_navigable_step(focused_step, -1)
        if next_step != active_step:
            raise VisualWizardStepJump(next_step, focus_area="steps")
        return "steps", next_step
    if key == "right":
        next_step = adjacent_navigable_step(focused_step, 1)
        if next_step != active_step:
            raise VisualWizardStepJump(next_step, focus_area="steps")
        return "steps", next_step
    if key in {"enter", "down"}:
        if focused_step == active_step:
            return "content", focused_step
        raise VisualWizardStepJump(focused_step)
    return "steps", focused_step


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
    initial_selected_index: int = 0,
    initial_focus_area: str = "content",
) -> Option | None:
    selected = max(0, min(len(options) - 1, int(initial_selected_index))) if options else 0
    focus_area = "steps" if initial_focus_area == "steps" else "content"
    focused_step = active_step
    while True:
        footer = option_footer(focus_area=focus_area, primary="Enter confirma", allow_back=allow_back)
        display.show(
            screen_id,
            build_screen_svg(
                active_step=active_step,
                focused_step=focused_step,
                focus_area=focus_area,
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
        if focus_area == "steps":
            if allow_back and key in {"b", "B", "back", "escape"}:
                return None
            if key in {"q", "Q"} or (key == "escape" and not allow_back):
                raise VisualWizardAbort("setup visual cancelado pelo operador")
            focus_area, focused_step = handle_step_focus_key(
                key,
                focused_step=focused_step,
                active_step=active_step,
            )
            continue
        if key == "up":
            if selected == 0:
                focus_area = "steps"
                focused_step = active_step
            else:
                selected -= 1
        elif key == "down":
            selected = min(len(options) - 1, selected + 1)
        elif key in {"1", "2", "3", "4", "5"} and int(key) <= len(options):
            selected = int(key) - 1
        elif key == "enter":
            return options[selected]
        elif allow_back and key in {"b", "B", "back", "escape"}:
            return None
        elif key in {"q", "Q"} or (key == "escape" and not allow_back):
            raise VisualWizardAbort("setup visual cancelado pelo operador")


def selected_orientation_index_for_rotation(rotation_deg: int) -> int:
    normalized = normalize_rotation_deg(rotation_deg)
    for index, item in enumerate(DISPLAY_OPTIONS):
        if int(item["rotation_deg"]) == normalized:
            return index
    return 0


def choose_orientation(
    display: VisualDisplay,
    *,
    initial_rotation_deg: int = 0,
    initial_focus_area: str = "content",
) -> dict[str, str | int]:
    options = [Option(str(item["key"]), str(item["label"]), str(item["description"])) for item in DISPLAY_OPTIONS]
    selected = selected_orientation_index_for_rotation(initial_rotation_deg)
    current_layout_rotation_deg = normalize_rotation_deg(initial_rotation_deg)
    focus_area = "steps" if initial_focus_area == "steps" else "content"
    focused_step = 0
    needs_render = True
    while True:
        if needs_render:
            selected_rotation = resolve_display_selection(options[selected].key)
            display.show(
                "01-orientation",
                build_screen_svg(
                    active_step=0,
                    focused_step=focused_step,
                    focus_area=focus_area,
                    title="Orientacao da tela",
                    subtitle="Escolha como o totem esta instalado.",
                    footer=option_footer(focus_area=focus_area, primary="Enter visualiza", allow_back=False),
                    options=options,
                    selected_index=selected,
                    panel_title="Tela",
                    panel_items=[
                        "Escolha a posicao.",
                        "Confira o preview.",
                        "Salve ao final.",
                    ],
                    extra_svg=orientation_preview(
                        str(selected_rotation["key"]),
                        layout_rotation_deg=current_layout_rotation_deg,
                    ),
                    layout_rotation_deg=current_layout_rotation_deg,
                    suppress_landscape_info_panel=True,
                ),
            )
            needs_render = False
        key = read_key()
        if focus_area == "steps":
            if key in {"escape", "q", "Q"}:
                raise VisualWizardAbort("setup visual cancelado pelo operador")
            focus_area, focused_step = handle_step_focus_key(
                key,
                focused_step=focused_step,
                active_step=0,
            )
            needs_render = True
            continue
        if key == "up":
            if selected == 0:
                focus_area = "steps"
                focused_step = 0
            else:
                selected -= 1
            needs_render = True
            continue
        if key == "down":
            selected = min(len(options) - 1, selected + 1)
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
        confirm_focus_area = "content"
        confirm_focused_step = 0
        while True:
            display.show(
                "01-orientation-confirm",
                build_screen_svg(
                    active_step=0,
                    focused_step=confirm_focused_step,
                    focus_area=confirm_focus_area,
                    title="Usar esta orientacao?",
                    subtitle="Confira o sentido antes de continuar.",
                    footer=option_footer(focus_area=confirm_focus_area, primary="Enter confirma", allow_back=True),
                    options=confirm_options,
                    selected_index=confirm_selected,
                    panel_title="Confirmar",
                    panel_items=[
                        "Preview local.",
                        "Sem alterar player agora.",
                        "Pode voltar.",
                    ],
                    extra_svg=orientation_preview(str(rotation["key"]), layout_rotation_deg=layout_rotation_deg),
                    layout_rotation_deg=layout_rotation_deg,
                    suppress_landscape_info_panel=True,
                ),
            )
            confirm_key = read_key()
            if confirm_focus_area == "steps":
                if confirm_key in {"b", "B", "back", "escape"}:
                    needs_render = True
                    break
                if confirm_key in {"q", "Q"}:
                    raise VisualWizardAbort("setup visual cancelado pelo operador")
                confirm_focus_area, confirm_focused_step = handle_step_focus_key(
                    confirm_key,
                    focused_step=confirm_focused_step,
                    active_step=0,
                )
                continue
            if confirm_key == "up":
                if confirm_selected == 0:
                    confirm_focus_area = "steps"
                    confirm_focused_step = 0
                else:
                    confirm_selected -= 1
                continue
            if confirm_key == "down":
                confirm_selected = min(len(confirm_options) - 1, confirm_selected + 1)
                continue
            if confirm_key == "enter":
                if confirm_options[confirm_selected].key == "confirm":
                    return rotation
                needs_render = True
                break
            if confirm_key in {"b", "B", "back", "escape"}:
                needs_render = True
                break
            if confirm_key in {"q", "Q"}:
                raise VisualWizardAbort("setup visual cancelado pelo operador")


def is_printable_input_key(key: str) -> bool:
    return len(key) == 1 and 32 <= ord(key) <= 126


def is_text_mutation_key(key: str) -> bool:
    return key in {"backspace", "delete", "clear"} or is_printable_input_key(key)


def is_secret_toggle_key(key: str) -> bool:
    return key in {"f2", "toggle_secret"}


def drain_key_repeats(initial_key: str) -> list[str]:
    keys = [initial_key]
    if not is_text_mutation_key(initial_key):
        return keys
    deadline = time.monotonic() + max(0.0, TEXT_INPUT_REPEAT_DRAIN_SEC)
    while len(keys) < max(1, TEXT_INPUT_MAX_DRAIN_KEYS) and time.monotonic() < deadline:
        key = read_key(timeout_sec=0.0)
        if key == "timeout":
            time.sleep(0.005)
            continue
        keys.append(key)
        if not is_text_mutation_key(key):
            break
    return keys


def text_field_apply_key(
    value: str,
    key: str,
    *,
    max_length: int,
    error: str,
) -> tuple[str, str, bool]:
    next_value = value
    next_error = error
    if key == "backspace":
        next_value = value[:-1]
        next_error = ""
    elif key == "clear":
        next_value = ""
        next_error = ""
    elif is_printable_input_key(key) and len(value) < max_length:
        next_value = value + key
        next_error = ""
    return next_value, next_error, (next_value != value or next_error != error)


def text_field_apply_edit_key(
    value: str,
    cursor: int,
    key: str,
    *,
    max_length: int,
    error: str,
) -> tuple[str, int, str, bool]:
    cursor = max(0, min(len(value), cursor))
    next_value = value
    next_cursor = cursor
    next_error = error
    if key == "left":
        next_cursor = max(0, cursor - 1)
    elif key == "right":
        next_cursor = min(len(value), cursor + 1)
    elif key == "home":
        next_cursor = 0
    elif key == "end":
        next_cursor = len(value)
    elif key == "backspace":
        if cursor > 0:
            next_value = value[: cursor - 1] + value[cursor:]
            next_cursor = cursor - 1
            next_error = ""
    elif key == "delete":
        if cursor < len(value):
            next_value = value[:cursor] + value[cursor + 1 :]
            next_error = ""
    elif key == "clear":
        next_value = ""
        next_cursor = 0
        next_error = ""
    elif is_printable_input_key(key) and len(value) < max_length:
        next_value = value[:cursor] + key + value[cursor:]
        next_cursor = cursor + 1
        next_error = ""
    changed = next_value != value or next_cursor != cursor or next_error != error
    return next_value, next_cursor, next_error, changed


def estimate_debounced_input_render_count(
    initial_value: str,
    keys: list[str],
    *,
    event_interval_sec: float,
    min_render_interval_sec: float = TEXT_INPUT_MIN_RENDER_INTERVAL_SEC,
    max_length: int = 128,
) -> int:
    value = initial_value
    error = ""
    last_render_at = 0.0
    renders = 1
    dirty = False
    now = 0.0
    for key in keys:
        now += max(0.0, event_interval_sec)
        value, error, changed = text_field_apply_key(value, key, max_length=max_length, error=error)
        dirty = dirty or changed
        if dirty and now - last_render_at >= min_render_interval_sec:
            renders += 1
            last_render_at = now
            dirty = False
    if dirty:
        renders += 1
    return renders


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
    allow_hidden_toggle: bool = False,
    layout_rotation_deg: int = 0,
    initial_value: str = "",
    show_cursor: bool = False,
    custom_footer: str | None = None,
    escape_returns_back: bool = False,
    validation_error_message: str = "Formato invalido.",
    initial_focus_area: str = "content",
) -> str | None:
    value = str(initial_value or "")[:max_length]
    cursor = len(value)
    error = ""
    reveal_hidden_value = False
    focus_area = "steps" if initial_focus_area == "steps" else "content"
    focused_step = active_step
    needs_render = True
    force_render = True
    last_render_at = 0.0
    last_visual_state: tuple[str, str, bool, int, str, int] | None = None
    while True:
        if needs_render:
            now = time.monotonic()
            if (
                not force_render
                and last_render_at > 0
                and now - last_render_at < TEXT_INPUT_MIN_RENDER_INTERVAL_SEC
            ):
                key = read_key(timeout_sec=TEXT_INPUT_MIN_RENDER_INTERVAL_SEC - (now - last_render_at))
                if key != "timeout":
                    for drained_key in drain_key_repeats(key):
                        if focus_area == "steps":
                            if allow_back and drained_key in {"back", "escape"}:
                                return None
                            if drained_key in {"escape", "q", "Q"}:
                                raise VisualWizardAbort("setup visual cancelado pelo operador")
                            focus_area, focused_step = handle_step_focus_key(
                                drained_key,
                                focused_step=focused_step,
                                active_step=active_step,
                            )
                            needs_render = True
                            force_render = True
                            break
                        if drained_key == "up":
                            focus_area = "steps"
                            focused_step = active_step
                            needs_render = True
                            force_render = True
                            break
                        if drained_key == "enter":
                            candidate = value.strip() if not hidden else value
                            if len(candidate) < min_length:
                                error = "Entrada incompleta."
                                needs_render = True
                                force_render = True
                                break
                            if validator is not None:
                                try:
                                    return validator(candidate)
                                except Exception:
                                    error = validation_error_message
                                    needs_render = True
                                    force_render = True
                                    break
                            return candidate
                        if hidden and allow_hidden_toggle and is_secret_toggle_key(drained_key):
                            reveal_hidden_value = not reveal_hidden_value
                            if error:
                                error = ""
                            needs_render = True
                            force_render = True
                            break
                        if allow_back and drained_key in {"back", "escape"}:
                            return None
                        if drained_key in {"escape", "q", "Q"}:
                            raise VisualWizardAbort("setup visual cancelado pelo operador")
                        previous_value = value
                        previous_cursor = cursor
                        previous_error = error
                        value, cursor, error, changed = text_field_apply_edit_key(
                            value,
                            cursor,
                            drained_key,
                            max_length=max_length,
                            error=error,
                        )
                        needs_render = (
                            needs_render
                            or changed
                            or value != previous_value
                            or cursor != previous_cursor
                            or error != previous_error
                        )
                    continue
                continue

            effective_show_plain_value = show_plain_value or bool(hidden and allow_hidden_toggle and reveal_hidden_value)
            hint = text_field_display_hint(
                value,
                hidden=hidden,
                show_plain_value=effective_show_plain_value,
                cursor_index=cursor if show_cursor and not hidden and effective_show_plain_value else None,
            )
            note = error or ("Senha oculta." if hidden and not effective_show_plain_value else "Entrada local.")
            footer = custom_footer or "Enter confirma | Esc cancela"
            if allow_back:
                footer = custom_footer or "Enter confirma | Esc volta"
            if hidden and allow_hidden_toggle:
                toggle_label = "oculta" if reveal_hidden_value else "mostra"
                footer = f"Enter confirma | Esc volta | F2 {toggle_label}"
            if focus_area == "steps":
                footer = option_footer(focus_area=focus_area, primary="Enter edita", allow_back=allow_back)
            visual_state = (hint, note, reveal_hidden_value, cursor, focus_area, focused_step)
            if visual_state != last_visual_state:
                display.show(
                    screen_id,
                    build_screen_svg(
                        active_step=active_step,
                        title=title,
                        subtitle=subtitle,
                        footer=footer,
                        focused_step=focused_step,
                        focus_area=focus_area,
                        field_label=label,
                        field_value_hint=hint,
                        field_note=note,
                        panel_items=panel_items,
                        accent="#ef4444" if error else "#06b6d4",
                        layout_rotation_deg=layout_rotation_deg,
                    ),
                )
                last_render_at = time.monotonic()
                last_visual_state = visual_state
            needs_render = False
            force_render = False

        key = read_key()
        for drained_key in drain_key_repeats(key):
            if focus_area == "steps":
                if allow_back and drained_key in {"back", "escape"}:
                    return None
                if drained_key in {"escape", "q", "Q"}:
                    raise VisualWizardAbort("setup visual cancelado pelo operador")
                focus_area, focused_step = handle_step_focus_key(
                    drained_key,
                    focused_step=focused_step,
                    active_step=active_step,
                )
                needs_render = True
                force_render = True
                break
            if drained_key == "up":
                focus_area = "steps"
                focused_step = active_step
                needs_render = True
                force_render = True
                break
            if drained_key == "enter":
                candidate = value.strip() if not hidden else value
                if len(candidate) < min_length:
                    error = "Entrada incompleta."
                    needs_render = True
                    force_render = True
                    break
                if validator is not None:
                    try:
                        return validator(candidate)
                    except Exception:
                        error = validation_error_message
                        needs_render = True
                        force_render = True
                        break
                return candidate
            if hidden and allow_hidden_toggle and is_secret_toggle_key(drained_key):
                reveal_hidden_value = not reveal_hidden_value
                error = ""
                needs_render = True
                force_render = True
                break
            if allow_back and drained_key in {"back", "escape"}:
                return None
            if drained_key in {"escape", "q", "Q"}:
                raise VisualWizardAbort("setup visual cancelado pelo operador")
            value, cursor, error, changed = text_field_apply_edit_key(
                value,
                cursor,
                drained_key,
                max_length=max_length,
                error=error,
            )
            needs_render = needs_render or changed


def text_field_display_hint(
    value: str,
    *,
    hidden: bool,
    show_plain_value: bool,
    cursor_index: int | None = None,
) -> str:
    if hidden:
        if show_plain_value:
            return value or "Aguardando entrada"
        return "*" * len(value) if value else "Aguardando entrada"
    if show_plain_value:
        if cursor_index is not None:
            cursor = max(0, min(len(value), cursor_index))
            rendered = value[:cursor] + "|" + value[cursor:]
            return rendered or "|"
        return value or "Aguardando entrada"
    return f"{len(value)} caracteres digitados" if value else "Aguardando entrada"


def validate_environment_id(value: str) -> str:
    candidate = value.strip()
    try:
        parsed = uuid.UUID(candidate)
    except (AttributeError, TypeError, ValueError) as exc:
        raise VisualWizardError("environment_id must be a UUID") from exc
    if not re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        candidate,
    ):
        raise VisualWizardError("environment_id must be a canonical UUID")
    return str(parsed)


def private_file_mode_ok(path: pathlib.Path) -> bool:
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return False
    return bool(mode & 0o600) and not bool(mode & 0o077)


def load_environment_validation_credentials(path: pathlib.Path = PRIVATE_VALUES_SEED_PATH) -> dict[str, str] | None:
    if not ENVIRONMENT_VALIDATION_ENABLED:
        return None
    try:
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file() or not private_file_mode_ok(path):
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    api_url = data.get("api_url")
    api_key = data.get("api_key")
    if not isinstance(api_url, str) or not isinstance(api_key, str):
        return None
    api_url = api_url.strip()
    api_key = api_key.strip()
    if not api_url or not api_key:
        return None
    parsed = urllib_parse.urlsplit(api_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return {"api_url": api_url, "api_key": api_key}


def derive_environment_endpoint(api_url: str, environment_id: str) -> str | None:
    parsed = urllib_parse.urlsplit(api_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    path = parsed.path.rstrip("/")
    if path.endswith("/search"):
        base_path = path[: -len("/search")]
    elif path == "/search":
        base_path = ""
    else:
        base_path = path
    env_path = f"{base_path}/environments/{urllib_parse.quote(environment_id, safe='')}"
    return urllib_parse.urlunsplit((parsed.scheme, parsed.netloc, env_path, "", ""))


def http_json_request(
    url: str,
    *,
    api_key: str,
    method: str,
    payload: dict[str, Any] | None = None,
    timeout_sec: float = ENVIRONMENT_VALIDATION_TIMEOUT_SEC,
) -> tuple[int, dict[str, Any] | None]:
    data = None
    headers = {
        "Accept": "application/json",
        "x-api-key": api_key,
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib_request.Request(url, data=data, headers=headers, method=method)
    with urllib_request.urlopen(req, timeout=max(1.0, timeout_sec)) as resp:
        raw = resp.read(256 * 1024)
        body: dict[str, Any] | None = None
        if raw:
            try:
                parsed = json.loads(raw.decode("utf-8"))
                body = parsed if isinstance(parsed, dict) else None
            except Exception:
                body = None
        return int(resp.status), body


def http_json_request_no_auth(
    url: str,
    *,
    method: str,
    payload: dict[str, Any] | None = None,
    timeout_sec: float = ENVIRONMENT_VALIDATION_TIMEOUT_SEC,
) -> tuple[int, dict[str, Any] | None]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib_request.Request(url, data=data, headers=headers, method=method)
    with urllib_request.urlopen(req, timeout=max(1.0, timeout_sec)) as resp:
        raw = resp.read(256 * 1024)
        body: dict[str, Any] | None = None
        if raw:
            try:
                parsed = json.loads(raw.decode("utf-8"))
                body = parsed if isinstance(parsed, dict) else None
            except Exception:
                body = None
        return int(resp.status), body


def response_has_content(data: dict[str, Any] | None) -> tuple[str, bool]:
    if not isinstance(data, dict):
        return "unknown", False
    total = data.get("total")
    if isinstance(total, int):
        return ("true", False) if total > 0 else ("false", True)
    if isinstance(total, str) and total.isdigit():
        return ("true", False) if int(total) > 0 else ("false", True)
    units = data.get("units")
    if isinstance(units, list):
        for unit in units:
            if not isinstance(unit, dict):
                continue
            campaigns = unit.get("campaigns")
            if isinstance(campaigns, list) and campaigns:
                return "true", False
            media_urls = unit.get("media_urls")
            if isinstance(media_urls, list) and media_urls:
                return "true", False
    return "unknown", False


def environment_preflight_unavailable(endpoint: str = "none", *, requires_confirmation: bool = True) -> EnvironmentPreflight:
    return EnvironmentPreflight(
        endpoint=endpoint,
        environment_exists="unknown",
        environment_not_found=False,
        invalid_environment_id=False,
        validation_auth_required=False,
        validation_unavailable=True,
        content_available="unknown",
        content_empty=False,
        requires_confirmation=requires_confirmation,
        confirmed_by_operator=False,
    )


def environment_preflight_pairing_authorized() -> EnvironmentPreflight:
    return EnvironmentPreflight(
        endpoint="qr_pairing_mock",
        environment_exists="true",
        environment_not_found=False,
        invalid_environment_id=False,
        validation_auth_required=False,
        validation_unavailable=False,
        content_available="unknown",
        content_empty=False,
        requires_confirmation=False,
        confirmed_by_operator=True,
    )


def validate_environment_remote(environment_id: str) -> EnvironmentPreflight:
    credentials = load_environment_validation_credentials()
    if credentials is None:
        return environment_preflight_unavailable("none")
    api_url = credentials["api_url"]
    api_key = credentials["api_key"]
    env_endpoint = derive_environment_endpoint(api_url, environment_id)
    if env_endpoint is None:
        return environment_preflight_unavailable("none")

    environment_exists = "unknown"
    validation_auth_required = False
    validation_unavailable = False
    endpoint_label = "environments_by_id"
    try:
        status, _data = http_json_request(env_endpoint, api_key=api_key, method="GET")
        if 200 <= status < 300:
            environment_exists = "true"
        else:
            validation_unavailable = True
    except urllib_error.HTTPError as exc:
        if exc.code == 404:
            return EnvironmentPreflight(
                endpoint=endpoint_label,
                environment_exists="false",
                environment_not_found=True,
                invalid_environment_id=False,
                validation_auth_required=False,
                validation_unavailable=False,
                content_available="unknown",
                content_empty=False,
                requires_confirmation=False,
                confirmed_by_operator=False,
            )
        if exc.code == 400:
            return EnvironmentPreflight(
                endpoint=endpoint_label,
                environment_exists="unknown",
                environment_not_found=False,
                invalid_environment_id=True,
                validation_auth_required=False,
                validation_unavailable=False,
                content_available="unknown",
                content_empty=False,
                requires_confirmation=False,
                confirmed_by_operator=False,
            )
        if exc.code in {401, 403}:
            validation_auth_required = True
        else:
            validation_unavailable = True
    except Exception:
        validation_unavailable = True

    content_available = "unknown"
    content_empty = False
    try:
        _status, search_data = http_json_request(
            api_url,
            api_key=api_key,
            method="POST",
            payload={
                "environmentId": environment_id,
                "onlyStandby": False,
                "searchIn": "campaign",
                "includeDescendants": True,
                "limit": 20,
            },
        )
        content_available, content_empty = response_has_content(search_data)
        if environment_exists == "unknown" and content_available == "true":
            endpoint_label = "search_only"
    except urllib_error.HTTPError as exc:
        if exc.code in {401, 403}:
            validation_auth_required = True
        else:
            validation_unavailable = True
    except Exception:
        validation_unavailable = True

    requires_confirmation = (
        validation_auth_required
        or validation_unavailable
        or content_empty
        or environment_exists == "unknown"
    )
    return EnvironmentPreflight(
        endpoint=endpoint_label,
        environment_exists=environment_exists,
        environment_not_found=False,
        invalid_environment_id=False,
        validation_auth_required=validation_auth_required,
        validation_unavailable=validation_unavailable,
        content_available=content_available,
        content_empty=content_empty,
        requires_confirmation=requires_confirmation,
        confirmed_by_operator=False,
    )


def preflight_public_status(preflight: EnvironmentPreflight | None) -> dict[str, Any]:
    if preflight is None:
        return {
            "available": False,
            "endpoint": "none",
            "environment_exists": "not_checked",
            "environment_not_found": False,
            "invalid_environment_id": False,
            "validation_auth_required": False,
            "validation_unavailable": False,
            "content_available": "not_checked",
            "content_empty": False,
            "requires_confirmation": False,
            "confirmed_by_operator": False,
            "raw_values_written": False,
        }
    return {
        "available": preflight.endpoint != "none",
        "endpoint": preflight.endpoint,
        "environment_exists": preflight.environment_exists,
        "environment_not_found": preflight.environment_not_found,
        "invalid_environment_id": preflight.invalid_environment_id,
        "validation_auth_required": preflight.validation_auth_required,
        "validation_unavailable": preflight.validation_unavailable,
        "content_available": preflight.content_available,
        "content_empty": preflight.content_empty,
        "requires_confirmation": preflight.requires_confirmation,
        "confirmed_by_operator": preflight.confirmed_by_operator,
        "raw_values_written": False,
    }


def preflight_with_confirmation(preflight: EnvironmentPreflight) -> EnvironmentPreflight:
    return EnvironmentPreflight(
        endpoint=preflight.endpoint,
        environment_exists=preflight.environment_exists,
        environment_not_found=preflight.environment_not_found,
        invalid_environment_id=preflight.invalid_environment_id,
        validation_auth_required=preflight.validation_auth_required,
        validation_unavailable=preflight.validation_unavailable,
        content_available=preflight.content_available,
        content_empty=preflight.content_empty,
        requires_confirmation=preflight.requires_confirmation,
        confirmed_by_operator=True,
    )


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


def rotation_selection_from_degrees(rotation_deg: int) -> dict[str, str | int]:
    option = DISPLAY_OPTIONS[selected_orientation_index_for_rotation(rotation_deg)]
    return resolve_display_selection(str(option["key"]))


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


def initial_wizard_state(initial_rotation_deg: int, initial_environment_id: str) -> WizardState:
    return WizardState(
        rotation=rotation_selection_from_degrees(initial_rotation_deg),
        rotation_status="default",
        environment_id=str(initial_environment_id or ""),
        environment_status="pending",
    )


def network_option_index_for_step(network_step: str | None) -> int:
    key_by_step = {
        "existing_configured_wifi": "configured_wifi",
        "wifi_persistent": "wifi_select",
        "bench_mock": "bench_mock",
    }
    key = key_by_step.get(str(network_step or ""), "configured_wifi")
    for index, option in enumerate(NETWORK_OPTIONS):
        if option.key == key:
            return index
    return 0


def network_review_note(network: dict[str, Any] | None, status: str = "pending") -> str:
    if network is None:
        return "Pendente"
    base = {
        "existing_configured_wifi": "Wi-Fi atual",
        "wifi_persistent": "Wi-Fi dedicado",
        "bench_mock": "Bancada",
    }.get(str(network.get("network_step", "")), "Rede")
    if status == "default":
        return f"{base} (default)"
    return base


def environment_review_note(environment_id: str, preflight: EnvironmentPreflight | None) -> str:
    if not str(environment_id or "").strip():
        return "Pendente"
    if preflight is None:
        return "Precisa validar"
    if preflight.content_empty:
        return "Validado sem midia"
    if preflight.requires_confirmation and preflight.confirmed_by_operator:
        return "Confirmado"
    return "Validado"


def wizard_can_commit(state: WizardState) -> bool:
    return bool(state.network is not None and state.environment_id.strip() and state.environment_preflight is not None)


def first_incomplete_step(state: WizardState) -> int:
    if state.network is None:
        return 1
    if not state.environment_id.strip() or state.environment_preflight is None:
        return 2
    return 3


def step_status_label(state: WizardState, step: int) -> str:
    if step == 0:
        return "Confirmado" if state.rotation_status == "confirmed" else "Default"
    if step == 1:
        if state.network is None:
            return "Pendente"
        return "Confirmado"
    if step == 2:
        if not state.environment_id.strip():
            return "Pendente"
        if state.environment_preflight is None:
            return "Precisa validar"
        return "Validado"
    if step == 3:
        return "Pronto" if wizard_can_commit(state) else "Bloqueado"
    return "Indisponivel"


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
        return "Protegida"
    if value is False:
        return "Aberta"
    return "Seguranca desconhecida"


def signal_percent(network: dict[str, Any]) -> int:
    try:
        return max(0, min(100, int(network.get("signal_percent", 0))))
    except (TypeError, ValueError):
        return 0


def signal_bars(percent: int) -> str:
    if percent >= 90:
        return "[####]"
    if percent >= 70:
        return "[###.]"
    if percent >= 40:
        return "[##..]"
    return "[#...]"


def signal_label(percent: int) -> str:
    if percent >= 90:
        return "Forte"
    if percent >= 70:
        return "Bom"
    if percent >= 40:
        return "Medio"
    return "Fraco"


def wifi_option_for_network(index: int, network: dict[str, Any]) -> Option:
    percent = signal_percent(network)
    return Option(
        f"wifi-{index}",
        local_display_value(str(network["ssid"])),
        f"{percent}% {signal_label(percent)} | {security_label(network.get('security_present'))}",
    )


def page_bounds(total_count: int, selected_index: int, page_size: int) -> tuple[int, int, int, int]:
    safe_total = max(0, int(total_count))
    safe_page_size = max(1, int(page_size))
    if safe_total == 0:
        return 0, 0, 0, 0
    safe_selected = max(0, min(safe_total - 1, int(selected_index)))
    page_index = safe_selected // safe_page_size
    start = page_index * safe_page_size
    end = min(safe_total, start + safe_page_size)
    return start, end, page_index, max(1, (safe_total + safe_page_size - 1) // safe_page_size)


def page_items(items: list[dict[str, Any]], selected_index: int, page_size: int) -> tuple[list[dict[str, Any]], int, int, int, int]:
    start, end, page_index, page_count = page_bounds(len(items), selected_index, page_size)
    return items[start:end], start, end, page_index, page_count


def refresh_selected_index(
    previous_networks: list[dict[str, Any]],
    refreshed_networks: list[dict[str, Any]],
    previous_selected_index: int,
) -> tuple[int, bool]:
    if not refreshed_networks:
        return 0, False
    selected_ssid = ""
    if previous_networks:
        safe_previous = max(0, min(len(previous_networks) - 1, previous_selected_index))
        selected_ssid = str(previous_networks[safe_previous].get("ssid", ""))
    if selected_ssid:
        for index, network in enumerate(refreshed_networks):
            if str(network.get("ssid", "")) == selected_ssid:
                return index, True
    return max(0, min(len(refreshed_networks) - 1, previous_selected_index)), False


def apply_wifi_refresh_result(
    previous_networks: list[dict[str, Any]],
    refreshed_networks: list[dict[str, Any]],
    refreshed_status: str,
    previous_selected_index: int,
) -> tuple[list[dict[str, Any]], int, str]:
    if refreshed_status == "ok":
        if refreshed_networks:
            selected_index, preserved = refresh_selected_index(
                previous_networks,
                refreshed_networks,
                previous_selected_index,
            )
            return refreshed_networks, selected_index, "" if preserved else "Rede anterior saiu da lista."
        return [], 0, "Nenhuma rede encontrada."
    if previous_networks:
        safe_index = max(0, min(len(previous_networks) - 1, previous_selected_index))
        return previous_networks, safe_index, "Falha na atualizacao; lista anterior mantida."
    return [], 0, "Falha na atualizacao."


def wifi_list_screen_svg(
    *,
    networks: list[dict[str, Any]],
    selected_index: int,
    list_status: str,
    updated_age_sec: int,
    refresh_message: str,
    layout_rotation_deg: int,
    refreshing: bool = False,
) -> str:
    page_size = wifi_list_page_size(layout_rotation_deg)
    visible_networks, page_start, page_end, page_index, page_count = page_items(
        networks,
        selected_index,
        page_size,
    )
    options = [wifi_option_for_network(page_start + index, network) for index, network in enumerate(visible_networks)]
    selected_on_page = max(0, selected_index - page_start) if options else 0
    if networks:
        position = f"Mostrando {page_start + 1}-{page_end} de {len(networks)}"
        selected_line = f"Rede {selected_index + 1} de {len(networks)}"
    else:
        position = "Nenhuma rede encontrada"
        selected_line = "Use R para atualizar"
    updated_line = "Atualizando..." if refreshing else f"Atualizado ha {max(0, updated_age_sec)}s"
    panel_items = [
        position,
        selected_line,
        refresh_message or (f"Pagina {page_index + 1} de {page_count}" if networks else "Pagina 0 de 0"),
    ]
    return build_screen_svg(
        active_step=1,
        title="Selecionar Wi-Fi",
        subtitle=f"{updated_line}. Sinal e seguranca.",
        footer="Enter escolhe | Setas rolam | R atualiza | Esc volta",
        options=options,
        selected_index=selected_on_page,
        panel_title="Lista local",
        panel_items=panel_items,
        accent="#f59e0b" if refreshing else ("#ef4444" if not networks else "#06b6d4"),
        layout_rotation_deg=layout_rotation_deg,
    )


def synthetic_wifi_networks_for_preview() -> list[dict[str, Any]]:
    fixture = "\n".join(
        [
            "TEST_WIFI_STRONG:96:WPA2",
            "TEST_WIFI_STRONG:80:WPA2",
            "TEST_WIFI_MEDIUM:58:WPA2",
            "TEST_WIFI_WEAK:24:WPA2",
            "TEST_WIFI_OPEN:72:",
            "TEST_WIFI_BACKROOM:64:WPA2",
            "TEST_WIFI_COUNTER:51:WPA2",
            "TEST_WIFI_OFFICE:45:WPA2",
            "TEST_WIFI_GUEST:38:",
            "TEST_WIFI_STAGING:34:WPA2",
            "TEST_WIFI_SERVICE:28:WPA2",
            "TEST_WIFI_STORAGE:18:WPA2",
        ]
    )
    return wifi_adapter.parse_wifi_network_list(fixture)


def choose_wifi_network(
    display: VisualDisplay,
    *,
    layout_rotation_deg: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    networks, list_status = wifi_adapter.list_wifi_networks_for_local_ui(
        timeout_sec=WIFI_LIST_TIMEOUT_SEC,
        rescan=True,
    )
    page_size = wifi_list_page_size(layout_rotation_deg)
    selected_index = 0
    last_refresh = time.monotonic()
    refresh_message = ""
    needs_render = True
    while True:
        now = time.monotonic()
        if needs_render:
            display.show(
                "02-wifi-list",
                wifi_list_screen_svg(
                    networks=networks,
                    selected_index=selected_index,
                    list_status=list_status,
                    updated_age_sec=int(now - last_refresh),
                    refresh_message=refresh_message,
                    layout_rotation_deg=layout_rotation_deg,
                ),
            )
            needs_render = False

        wait_sec = max(0.0, WIFI_LIST_REFRESH_SEC - (time.monotonic() - last_refresh))
        key = read_key(timeout_sec=wait_sec)
        if key == "timeout":
            display.show(
                "02-wifi-list-refreshing",
                wifi_list_screen_svg(
                    networks=networks,
                    selected_index=selected_index,
                    list_status=list_status,
                    updated_age_sec=int(time.monotonic() - last_refresh),
                    refresh_message="Atualizacao automatica.",
                    layout_rotation_deg=layout_rotation_deg,
                    refreshing=True,
                ),
            )
            refreshed, refreshed_status = wifi_adapter.list_wifi_networks_for_local_ui(
                timeout_sec=WIFI_LIST_TIMEOUT_SEC,
                rescan=True,
            )
            networks, selected_index, refresh_message = apply_wifi_refresh_result(
                networks,
                refreshed,
                refreshed_status,
                selected_index,
            )
            list_status = refreshed_status
            last_refresh = time.monotonic()
            needs_render = True
            continue
        if key in {"r", "R"}:
            display.show(
                "02-wifi-list-refreshing",
                wifi_list_screen_svg(
                    networks=networks,
                    selected_index=selected_index,
                    list_status=list_status,
                    updated_age_sec=int(time.monotonic() - last_refresh),
                    refresh_message="Atualizacao manual.",
                    layout_rotation_deg=layout_rotation_deg,
                    refreshing=True,
                ),
            )
            refreshed, refreshed_status = wifi_adapter.list_wifi_networks_for_local_ui(
                timeout_sec=WIFI_LIST_TIMEOUT_SEC,
                rescan=True,
            )
            networks, selected_index, refresh_message = apply_wifi_refresh_result(
                networks,
                refreshed,
                refreshed_status,
                selected_index,
            )
            list_status = refreshed_status
            last_refresh = time.monotonic()
            needs_render = True
            continue
        if key in {"up", "left"} and networks:
            selected_index = max(0, selected_index - 1)
            refresh_message = ""
            needs_render = True
            continue
        if key in {"down", "right"} and networks:
            selected_index = min(len(networks) - 1, selected_index + 1)
            refresh_message = ""
            needs_render = True
            continue
        if key == "pageup" and networks:
            selected_index = max(0, selected_index - page_size)
            refresh_message = ""
            needs_render = True
            continue
        if key == "pagedown" and networks:
            selected_index = min(len(networks) - 1, selected_index + page_size)
            refresh_message = ""
            needs_render = True
            continue
        if key == "enter":
            if networks:
                return networks[selected_index], networks
            display.show(
                "02-wifi-list-refreshing",
                wifi_list_screen_svg(
                    networks=networks,
                    selected_index=selected_index,
                    list_status=list_status,
                    updated_age_sec=int(time.monotonic() - last_refresh),
                    refresh_message="Atualizacao manual.",
                    layout_rotation_deg=layout_rotation_deg,
                    refreshing=True,
                ),
            )
            refreshed, refreshed_status = wifi_adapter.list_wifi_networks_for_local_ui(
                timeout_sec=WIFI_LIST_TIMEOUT_SEC,
                rescan=True,
            )
            networks, selected_index, refresh_message = apply_wifi_refresh_result(
                networks,
                refreshed,
                refreshed_status,
                selected_index,
            )
            list_status = refreshed_status
            last_refresh = time.monotonic()
            needs_render = True
            continue
        if key in {"b", "B", "back", "escape"}:
            return None
        if key in {"q", "Q"}:
            raise VisualWizardAbort("setup visual cancelado pelo operador")


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
            footer="Enter continua | Esc volta",
            panel_title="Proximo",
            panel_items=[
                "Digite a senha.",
                "Ela inicia oculta.",
                "Pode voltar.",
            ],
            layout_rotation_deg=layout_rotation_deg,
        ),
    )
    key = read_advertised_action("enter", "b", "B", "back", "escape")
    if key in {"b", "B", "back", "escape"}:
        return None

    selection_metadata = wifi_adapter.wifi_selection_public_metadata(networks, selected_network)
    psk = read_text_field(
        display,
        screen_id="02-wifi-psk",
        active_step=1,
        title="Senha Wi-Fi",
        subtitle="Digite a senha da rede.",
        label="Senha Wi-Fi",
        hidden=True,
        min_length=8,
        max_length=128,
        panel_items=[
            "Oculta por padrao.",
            "F2 mostra.",
            "Nao aparece em logs.",
        ],
        allow_hidden_toggle=True,
        layout_rotation_deg=layout_rotation_deg,
    )
    if psk is None:
        return None
    display.show(
        "02-wifi-confirm",
        build_screen_svg(
            active_step=1,
            title="Aplicar Wi-Fi",
            subtitle="Vamos testar o perfil dedicado.",
            footer="Enter aplica | Esc volta",
            panel_title="Atencao",
            panel_items=[
                "SSH pode oscilar.",
                "Console local fica ativo.",
                "Pode voltar.",
            ],
            layout_rotation_deg=layout_rotation_deg,
        ),
    )
    key = read_advertised_action("enter", "b", "B", "back", "escape")
    if key in {"b", "B", "back", "escape"}:
        return None
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
    c1523_phase("wifi_step_entered", mode="persistent")
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
                    title="Salvando Wi-Fi",
                    subtitle="Testando o perfil dedicado.",
                    footer="Aguarde...",
                    panel_title="Em andamento",
                    panel_items=[
                        "Sem dados na tela.",
                        "Timeout curto ativo.",
                        "Perfil dedicado.",
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
            subtitle=f"Resultado: {network['wifi_activation_result']}.",
            footer="Enter continua | Esc volta",
            panel_title="Resultado",
            panel_items=[
                f"Perfil presente: {network['dedicated_profile_present_final']}",
                f"Persistente: {str(network['dedicated_profile_persistent']).lower()}",
                f"Senha temporaria removida: {str(network['secrets_file_removed']).lower()}",
            ],
            layout_rotation_deg=layout_rotation_deg,
        ),
    )
    key = read_advertised_action("enter", "b", "B", "back", "escape")
    if key in {"b", "B", "back", "escape"}:
        return None
    return network


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
    environment_preflight: EnvironmentPreflight | None = None,
) -> dict[str, Any]:
    preflight_status = preflight_public_status(environment_preflight)
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
            "uuid_format_validation": True,
            "remote_preflight": preflight_status,
        },
        "validation": {
            "environment_id": "uuid_format_validated",
            "display": "candidate_only",
            "rotation_degrees": int(rotation["rotation_deg"]),
            "rotation_label_written_to_status": False,
            "backend_validation": preflight_status["endpoint"],
            "environment_exists": preflight_status["environment_exists"],
            "content_available": preflight_status["content_available"],
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
            "network_external_access": preflight_status["endpoint"] != "none",
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
            "backend_called": preflight_status["endpoint"] != "none",
            "backend_preflight_attempted": environment_preflight is not None,
            "backend_preflight_raw_values_written": False,
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
            "environment_uuid_format_validation: true",
            f"environment_validation_endpoint: {status['environment']['remote_preflight']['endpoint']}",
            f"environment_exists: {status['environment']['remote_preflight']['environment_exists']}",
            f"content_available: {status['environment']['remote_preflight']['content_available']}",
            f"validation_unavailable_requires_confirmation: "
            f"{str(status['environment']['remote_preflight']['requires_confirmation']).lower()}",
            f"validation_confirmed_by_operator: "
            f"{str(status['environment']['remote_preflight']['confirmed_by_operator']).lower()}",
            f"rotation_degrees: {status['validation']['rotation_degrees']}",
            "splash_rotation_supported: true",
            "player_rotation_contract: config.rotation_deg",
            "contract_validator: C5.1 allow-mock",
            f"contract_allow_mock_valid: {str(status['contract_validation']['allow_mock']['valid']).lower()}",
            "contract_real_dry_run_expected_failure: true",
            "",
            "Guardrails:",
            f"writes_only_under_tmp: {str(status['guardrails']['writes_only_under_tmp']).lower()}",
            "real_config_read: false",
            "real_config_written: false",
            "writer_called: false",
            f"allowlisted_data_state_written: {str(status['guardrails'].get('allowlisted_data_state_written', False)).lower()}",
            f"data_written: {str(status['guardrails']['data_written']).lower()}",
            "opt_written: false",
            f"commands_executed: {str(status['guardrails']['commands_executed']).lower()}",
            "systemctl_called: false",
            "service_changed: false",
            "main_player_mpv_called: false",
            f"visual_renderer_mpv_called: {str(status['guardrails']['visual_renderer_mpv_called']).lower()}",
            f"nmcli_called: {str(status['guardrails']['nmcli_called']).lower()}",
            f"network_changed: {str(status['guardrails']['network_changed']).lower()}",
            f"backend_preflight_attempted: {str(status['guardrails']['backend_preflight_attempted']).lower()}",
            "backend_preflight_raw_values_written: false",
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


def require_public_orientation_path(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path)
    if path.is_symlink():
        raise VisualWizardError("orientation public path invalido")
    allowed_data_root = pathlib.Path("/data/state/totem-display")
    resolved_parent = path.parent.resolve(strict=False)
    if resolved_parent != allowed_data_root and setup.TMP_ROOT not in [resolved_parent, *resolved_parent.parents]:
        raise VisualWizardError("orientation public path fora da allowlist")
    if path.name != ORIENTATION_FILENAME:
        raise VisualWizardError("orientation public filename invalido")
    return path


def atomic_write_public_orientation(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o755)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
    os.chmod(path, 0o644)


def write_public_orientation_contract(path: pathlib.Path, generated_at: str, rotation: dict[str, str | int]) -> None:
    payload = orientation_contract_payload(generated_at, rotation)
    public_payload = {
        "schema_version": payload["schema_version"],
        "updated_at": payload["updated_at"],
        "rotation_deg": payload["rotation_deg"],
        "orientation_label": payload["orientation_label"],
    }
    atomic_write_public_orientation(path, public_payload)


def read_public_orientation_rotation(path: pathlib.Path = PUBLIC_ORIENTATION_PATH) -> int | None:
    try:
        if path.is_symlink() or not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        rotation = normalize_rotation_deg(data.get("rotation_deg", 0))
        return rotation
    except Exception:
        return None


def require_private_settings_context_path(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path)
    if path.is_symlink():
        raise VisualWizardError("contexto privado invalido")
    allowed_data_root = pathlib.Path("/data/state/totem-settings")
    resolved_parent = path.parent.resolve(strict=False)
    if resolved_parent != allowed_data_root and setup.TMP_ROOT not in [resolved_parent, *resolved_parent.parents]:
        raise VisualWizardError("contexto privado fora da allowlist")
    if path.name != "last-settings.json":
        raise VisualWizardError("contexto privado com nome invalido")
    return path


def load_private_settings_context(path: pathlib.Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or path.parent.is_symlink() or not path.exists():
            return {}
        if file_mode(path) != setup.PRIVATE_FILE_MODE:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    context: dict[str, Any] = {}
    raw_environment = data.get("environment_id")
    if isinstance(raw_environment, str) and raw_environment.strip():
        try:
            context["environment_id"] = validate_environment_id(raw_environment.strip())
        except Exception:
            pass
    if "rotation_deg" in data:
        context["rotation_deg"] = normalize_rotation_deg(data.get("rotation_deg", 0))
    if data.get("network_step") == "existing_configured_wifi":
        context["network_step"] = "existing_configured_wifi"
    return context


def initial_rotation_from_context(private_context: dict[str, Any], public_orientation_path: pathlib.Path = PUBLIC_ORIENTATION_PATH) -> int:
    if "rotation_deg" in private_context:
        return normalize_rotation_deg(private_context["rotation_deg"])
    public_rotation = read_public_orientation_rotation(public_orientation_path)
    if public_rotation is not None:
        return public_rotation
    return 0


def write_visual_artifacts(
    out_dir: pathlib.Path,
    environment_id: str,
    rotation: dict[str, str | int],
    network: dict[str, Any],
    *,
    public_orientation_path: pathlib.Path | None = None,
    environment_preflight: EnvironmentPreflight | None = None,
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
    public_orientation_written = False
    if public_orientation_path is not None:
        write_public_orientation_contract(public_orientation_path, generated_at, rotation)
        public_orientation_written = True

    status = build_visual_status(
        generated_at,
        rotation,
        environment_id,
        network,
        contract_validation,
        environment_preflight=environment_preflight,
    )
    status["orientation"]["public_orientation_contract_written"] = public_orientation_written
    status["orientation"]["public_orientation_path_allowlisted"] = public_orientation_written
    status["guardrails"]["writes_only_under_tmp"] = not public_orientation_written
    status["guardrails"]["allowlisted_data_state_written"] = public_orientation_written
    status["guardrails"]["data_written"] = public_orientation_written
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
    network: dict[str, Any] | None,
    *,
    environment_preflight: EnvironmentPreflight | None = None,
    rotation_status: str = "confirmed",
    network_status: str = "confirmed",
    initial_focus_area: str = "content",
) -> bool:
    ready = bool(network is not None and environment_id.strip() and environment_preflight is not None)
    network_note = network_review_note(network, network_status)
    environment_note = environment_review_note(environment_id, environment_preflight)
    focus_area = "steps" if initial_focus_area == "steps" else "content"
    focused_step = 3
    while True:
        if APPLY_CONTEXT == "real-write":
            subtitle = "Continue para a confirmacao final."
            primary = "Enter continua"
        elif APPLY_CONTEXT == "dry-run":
            subtitle = "Concluir valida sem aplicar."
            primary = "Enter valida"
        else:
            subtitle = "Concluir prepara a candidata."
            primary = "Enter prepara candidata"
        title = "Pronto para concluir"
        panel_title = "Antes de salvar"
        panel_items = [
            "A configuracao final ainda nao foi salva.",
            "O Wi-Fi selecionado pode ja estar ativo.",
            "Esc volta.",
        ]
        if not ready:
            title = "Pendencias antes de concluir"
            subtitle = "Complete os itens pendentes antes de salvar."
            primary = "Enter corrige"
            panel_title = "Bloqueado"
            panel_items = ["Sem candidata parcial.", "Revise os pendentes.", "Nada salvo."]
        elif rotation_status == "default":
            panel_items = ["Tela usa default atual.", "Dados privados ocultos.", "Esc volta."]
        footer = "Enter abre | Esc volta" if focus_area == "steps" else f"{primary} | Cima menu | Esc volta"
        display.show(
            "05-review",
            build_screen_svg(
                active_step=3,
                focused_step=focused_step,
                focus_area=focus_area,
                title=title,
                subtitle=subtitle,
                footer=footer,
                panel_title=panel_title,
                panel_items=panel_items,
                extra_svg=summary_rows_svg(
                    [
                        ("Tela", f'{rotation["label"]} ({step_status_label(WizardState(rotation, rotation_status), 0)})'),
                        ("Wi-Fi", network_note),
                        ("Ambiente", environment_note),
                    ],
                    layout_rotation_deg=int(rotation["rotation_deg"]),
                ),
                layout_rotation_deg=int(rotation["rotation_deg"]),
            ),
        )
        key = read_key()
        if focus_area == "steps":
            if key in {"b", "B", "back", "escape"}:
                return False
            if key in {"q", "Q"}:
                raise VisualWizardAbort("setup visual cancelado pelo operador")
            focus_area, focused_step = handle_step_focus_key(
                key,
                focused_step=focused_step,
                active_step=3,
            )
            continue
        if key == "up":
            focus_area = "steps"
            focused_step = 3
            continue
        if key == "enter":
            return ready
        if key in {"b", "B", "back", "escape"}:
            return False
        if key in {"q", "Q"}:
            raise VisualWizardAbort("setup visual cancelado pelo operador")
        # Unsupported keys must not turn an otherwise valid review into a cancel.
        continue


def show_environment_validation_status(
    display: VisualDisplay,
    *,
    title: str,
    subtitle: str,
    panel_items: list[str],
    footer: str,
    accent: str,
    layout_rotation_deg: int,
) -> str:
    display.show(
        "03-environment-validation",
        build_screen_svg(
            active_step=2,
            title=title,
            subtitle=subtitle,
            footer=footer,
            panel_title="Validacao",
            panel_items=panel_items,
            accent=accent,
            layout_rotation_deg=layout_rotation_deg,
        ),
    )
    return read_advertised_action("enter", "b", "B", "back", "escape")


def run_environment_preflight(
    display: VisualDisplay,
    environment_id: str,
    *,
    layout_rotation_deg: int,
) -> EnvironmentPreflight | None:
    display.show(
        "03-environment-validating",
        build_screen_svg(
            active_step=2,
            title="Ambiente",
            subtitle="Validando ambiente...",
            footer="Aguarde",
            panel_title="Checagem",
            panel_items=[
                "Formato UUID OK.",
                "Consultando cadastro.",
                "Sem exibir dados privados.",
            ],
            layout_rotation_deg=layout_rotation_deg,
        ),
    )
    preflight = validate_environment_remote(environment_id)
    if preflight.environment_not_found:
        key = show_environment_validation_status(
            display,
            title="Ambiente nao encontrado",
            subtitle="Verifique o ID e tente novamente.",
            footer="Enter corrige | Esc cancela",
            panel_items=["Nada foi salvo.", "ID nao publicado.", "Corrija o campo."],
            accent="#ef4444",
            layout_rotation_deg=layout_rotation_deg,
        )
        if key == "enter":
            return None
        raise VisualWizardAbort("setup visual cancelado pelo operador")
    if preflight.invalid_environment_id:
        key = show_environment_validation_status(
            display,
            title="ID invalido",
            subtitle="Verifique e tente novamente.",
            footer="Enter corrige | Esc cancela",
            panel_items=["Formato recusado.", "Nada foi salvo.", "Corrija o campo."],
            accent="#ef4444",
            layout_rotation_deg=layout_rotation_deg,
        )
        if key == "enter":
            return None
        raise VisualWizardAbort("setup visual cancelado pelo operador")

    if preflight.content_available == "true" and not preflight.requires_confirmation:
        key = show_environment_validation_status(
            display,
            title="Ambiente validado",
            subtitle="Conteudo encontrado.",
            footer="Enter continua | Esc volta",
            panel_items=["Cadastro encontrado.", "Midia disponivel.", "Pode revisar."],
            accent="#22c55e",
            layout_rotation_deg=layout_rotation_deg,
        )
        if key == "enter":
            return preflight
        if key in {"b", "B", "back", "escape"}:
            return None
        raise VisualWizardAbort("setup visual cancelado pelo operador")

    if preflight.content_empty:
        key = show_environment_validation_status(
            display,
            title="Sem midia ativa agora",
            subtitle="O ambiente existe, mas pode iniciar aguardando conteudo.",
            footer="Enter continua | Esc volta",
            panel_items=["Ambiente nao e invalido.", "Player pode aguardar.", "Revise antes de salvar."],
            accent="#f59e0b",
            layout_rotation_deg=layout_rotation_deg,
        )
        if key == "enter":
            return preflight_with_confirmation(preflight)
        if key in {"b", "B", "back", "escape"}:
            return None
        raise VisualWizardAbort("setup visual cancelado pelo operador")

    if preflight.requires_confirmation:
        reason = "API indisponivel"
        if preflight.validation_auth_required:
            reason = "Validacao exige permissao"
        key = show_environment_validation_status(
            display,
            title="Nao foi possivel validar agora",
            subtitle=reason,
            footer="Enter continua | Esc volta",
            panel_items=["Formato UUID OK.", "Sem dados privados.", "Confirme para seguir."],
            accent="#f59e0b",
            layout_rotation_deg=layout_rotation_deg,
        )
        if key == "enter":
            return preflight_with_confirmation(preflight)
        if key in {"b", "B", "back", "escape"}:
            return None
        raise VisualWizardAbort("setup visual cancelado pelo operador")

    key = show_environment_validation_status(
        display,
        title="Ambiente validado",
        subtitle="Cadastro confirmado.",
        footer="Enter continua | Esc volta",
        panel_items=["Cadastro encontrado.", "Sem dados privados.", "Pode revisar."],
        accent="#22c55e",
        layout_rotation_deg=layout_rotation_deg,
    )
    if key == "enter":
        return preflight
    if key in {"b", "B", "back", "escape"}:
        return None
    raise VisualWizardAbort("setup visual cancelado pelo operador")


def create_mock_pairing_artifacts(out_dir: pathlib.Path, *, state: str | None = None) -> dict[str, Any]:
    pairing_dir = require_pairing_mock_out_dir(out_dir / PAIRING_DIRNAME)
    requested_state = (
        state
        or os.environ.get("TOTEM_VISUAL_WIZARD_PAIRING_MOCK_STATE", "authorized").strip()
        or "authorized"
    )
    requested_code = os.environ.get("TOTEM_VISUAL_WIZARD_PAIRING_CODE", "").strip()
    if pairing_client is not None:
        code = pairing_client.validate_code(requested_code) if requested_code else pairing_client.generate_code()
        return pairing_client.run_mock_pairing(
            out_dir=pairing_dir,
            state=requested_state,
            code=code,
            authorize_base_url=PAIRING_DEFAULT_AUTHORIZE_BASE_URL,
            api_url=PAIRING_DEFAULT_API_URL,
            api_key=PAIRING_DEFAULT_MOCK_API_KEY,
            environment_id=PAIRING_DEFAULT_ENVIRONMENT_ID,
            station_id=PAIRING_DEFAULT_STATION_ID,
            expires_in_sec=600,
        )
    code = validate_pairing_code(requested_code) if requested_code else generate_pairing_code()
    return run_embedded_mock_pairing(pairing_dir, state=requested_state, code=code)


def require_pairing_mock_out_dir(path: pathlib.Path) -> pathlib.Path:
    if not path.is_absolute():
        raise VisualWizardError("pareamento exige diretorio absoluto")
    if path == setup.TMP_ROOT or not setup.path_is_under(path, setup.TMP_ROOT):
        raise VisualWizardError("pareamento deve usar diretorio dedicado em /tmp")
    if path.exists() and not path.is_dir():
        raise VisualWizardError("diretorio de pareamento invalido")
    if path.is_symlink() or path.parent.is_symlink():
        raise VisualWizardError("diretorio de pareamento inseguro")
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(setup.PRIVATE_DIR_MODE)
    return path


def generate_pairing_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    seed = uuid.uuid4().hex.upper()
    return "".join(alphabet[int(seed[i : i + 2], 16) % len(alphabet)] for i in range(0, 16, 2))


def validate_pairing_code(value: str) -> str:
    raw = str(value or "").strip().upper().replace("-", "")
    if len(raw) != 8 or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" for ch in raw):
        raise VisualWizardError("codigo de pareamento invalido")
    return raw


def pairing_authorize_url(code: str) -> str:
    parsed = urllib_parse.urlsplit(PAIRING_DEFAULT_AUTHORIZE_BASE_URL)
    query = urllib_parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("code", code))
    return urllib_parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib_parse.urlencode(query), parsed.fragment)
    )


def utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_pairing_json(path: pathlib.Path, payload: dict[str, Any], out_dir: pathlib.Path) -> None:
    setup.atomic_write_private_json(path, payload, out_dir)


def run_embedded_mock_pairing(out_dir: pathlib.Path, *, state: str, code: str) -> dict[str, Any]:
    if state not in PAIRING_STATES:
        raise VisualWizardError("estado de pareamento invalido")
    authorize_url = pairing_authorize_url(code)
    public_session = {
        "schema": PAIRING_SESSION_SCHEMA,
        "mode": "mock_embedded",
        "session_id": "mock-session-not-production",
        "state": state,
        "pairing_code": code,
        "authorize_url": authorize_url,
        "created_at_utc": utc_timestamp(),
        "expires_in_sec": 600,
        "poll_after_sec": 2,
        "poll_token_public": False,
        "credential_public": False,
        "human_firebase_token_on_device": False,
        "private_values_written": state == "authorized",
        "non_claims": [
            "not_production_backend",
            "not_scannable_qr_yet",
            "not_real_user_auth",
            "not_real_device_token",
        ],
    }
    session_path = out_dir / "pairing-session.public.json"
    result_path = out_dir / "pairing-result.public.json"
    private_path = out_dir / "private-values.json"
    write_pairing_json(session_path, public_session, out_dir)

    private_written = False
    if state == "authorized":
        private_values = {
            "schema": PAIRING_PRIVATE_VALUES_SCHEMA,
            "api_url": PAIRING_DEFAULT_API_URL,
            "api_key": PAIRING_DEFAULT_MOCK_API_KEY,
            "environment_id": PAIRING_DEFAULT_ENVIRONMENT_ID,
            "station_id": PAIRING_DEFAULT_STATION_ID,
            "issued_by": "c21-embedded-mock-pairing",
            "human_firebase_token_on_device": False,
        }
        write_pairing_json(private_path, private_values, out_dir)
        private_written = True
    elif private_path.exists():
        private_path.unlink()

    result = {
        "schema": PAIRING_RESULT_SCHEMA,
        "passed": state == "authorized",
        "state": state,
        "session_public_path": str(session_path),
        "pairing_card_svg_path": None,
        "private_values_path": str(private_path) if private_written else None,
        "private_values_mode": "0600" if private_written else None,
        "public_artifacts_sanitized": True,
        "human_firebase_token_on_device": False,
    }
    write_pairing_json(result_path, result, out_dir)
    return result


def pairing_real_enabled() -> bool:
    return PAIRING_MODE in {"real", "backend", "totem-auth", "production"}


def normalize_pairing_backend_base_url(raw: str | None = None) -> str:
    value = str(raw or os.environ.get("TOTEM_VISUAL_WIZARD_PAIRING_API_BASE_URL", PAIRING_DEFAULT_BACKEND_BASE_URL)).strip()
    parsed = urllib_parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise VisualWizardError("backend de pareamento invalido")
    return urllib_parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def pairing_backend_endpoint(path: str) -> str:
    base = normalize_pairing_backend_base_url()
    return f"{base}{path}"


def validate_pairing_https_url(value: str, field: str) -> str:
    raw = str(value or "").strip()
    parsed = urllib_parse.urlsplit(raw)
    if parsed.scheme != "https" or not parsed.netloc:
        raise VisualWizardError(f"{field} invalida")
    return raw


def validate_pairing_authorize_url(value: str, *, code: str, activation_id: str) -> str:
    raw = validate_pairing_https_url(value, "authorize_url")
    if len(raw.encode("utf-8")) > PAIRING_QR_MAX_PAYLOAD_BYTES:
        raise VisualWizardError("authorize_url longa demais")
    parsed = urllib_parse.urlsplit(raw)
    expected = urllib_parse.urlsplit(PAIRING_DEFAULT_AUTHORIZE_BASE_URL)
    try:
        invalid_authority = bool(parsed.username or parsed.password or parsed.port is not None)
    except ValueError as exc:
        raise VisualWizardError("authorize_url com autoridade invalida") from exc
    if invalid_authority:
        raise VisualWizardError("authorize_url com autoridade invalida")
    if parsed.hostname != expected.hostname or parsed.path.rstrip("/") != expected.path.rstrip("/"):
        raise VisualWizardError("authorize_url fora do fluxo Dadooh")
    if parsed.fragment:
        raise VisualWizardError("authorize_url com fragmento invalido")
    query = urllib_parse.parse_qsl(parsed.query, keep_blank_values=True)
    keys = [key for key, _value in query]
    if keys.count("code") != 1 or keys.count("activation_id") > 1:
        raise VisualWizardError("authorize_url com parametros invalidos")
    if any(key not in {"code", "activation_id"} for key in keys):
        raise VisualWizardError("authorize_url com parametros inesperados")
    values = dict(query)
    if validate_pairing_code(values.get("code", "")) != code:
        raise VisualWizardError("authorize_url nao corresponde ao codigo")
    linked_activation_id = values.get("activation_id", "").strip()
    if "activation_id" in values and not linked_activation_id:
        raise VisualWizardError("authorize_url com sessao vazia")
    if linked_activation_id and validate_environment_id(linked_activation_id) != activation_id:
        raise VisualWizardError("authorize_url nao corresponde a sessao")
    return raw


def pairing_wait_content_svg(url: str, code: str, *, layout_rotation_deg: int) -> str:
    if pairing_client is None or not hasattr(pairing_client, "qr_rects_svg"):
        raise VisualWizardError("encoder QR indisponivel")
    layout = screen_layout(layout_rotation_deg)
    display_code = f"{code[:4]} {code[4:]}"
    if layout.portrait:
        qr_x, qr_y, qr_size = (layout.width - 340) // 2, 282, 340
        code_x, code_y, code_width = layout.margin_x, 642, layout.width - layout.margin_x * 2
        manual_y = 782
        qr_label_x, qr_label_y = qr_x + 45, 272
        status_y = 918
        code_value_x, code_value_y = code_x + 34, code_y + 82
    else:
        qr_x, qr_y, qr_size = 650, 278, 300
        code_x, code_y, code_width = layout.margin_x, 302, 520
        manual_y = 462
        qr_label_x, qr_label_y = qr_x + 35, 266
        status_y = 624
        code_value_x, code_value_y = code_x + 34, code_y + 88
    qr_svg = pairing_client.qr_rects_svg(url, x=qr_x, y=qr_y, target_size=qr_size)
    return f"""
  <text data-qr-label="true" x="{qr_label_x}" y="{qr_label_y}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" font-weight="700" fill="{VISUAL['text_muted']}">Escaneie com a camera</text>
  {qr_svg}
  <rect x="{code_x + 8}" y="{code_y + 8}" width="{code_width}" height="126" rx="8" fill="#0a1628"/>
  <rect x="{code_x}" y="{code_y}" width="{code_width}" height="126" rx="8" fill="{VISUAL['surface_raised']}" stroke="{VISUAL['border']}"/>
  <rect x="{code_x}" y="{code_y}" width="8" height="126" rx="4" fill="{VISUAL['accent']}"/>
  <text x="{code_x + 34}" y="{code_y + 38}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" font-weight="700" fill="{VISUAL['text_muted']}">Codigo do totem</text>
  <text data-pairing-code="true" x="{code_value_x}" y="{code_value_y}" font-family="Arial, DejaVu Sans, sans-serif" font-size="38" font-weight="700" fill="{VISUAL['text']}">{escape_text(display_code)}</text>
  <rect x="{code_x}" y="{manual_y}" width="{code_width}" height="108" rx="8" fill="{VISUAL['surface']}" stroke="{VISUAL['border']}"/>
  <text x="{code_x + 28}" y="{manual_y + 36}" font-family="Arial, DejaVu Sans, sans-serif" font-size="17" fill="{VISUAL['text_muted']}">Ou acesse no navegador:</text>
  <text data-pairing-manual-url="true" x="{code_x + 28}" y="{manual_y + 76}" font-family="Arial, DejaVu Sans, sans-serif" font-size="21" font-weight="700" fill="{VISUAL['text']}">{escape_text(PAIRING_MANUAL_ENTRY_URL)}</text>
  <text x="{layout.margin_x}" y="{status_y}" font-family="Arial, DejaVu Sans, sans-serif" font-size="17" fill="{VISUAL['text_dim']}">O codigo renova automaticamente ao expirar.</text>
"""


def validate_pairing_api_key(value: str) -> str:
    raw = str(value or "").strip()
    if len(raw) < 16:
        raise VisualWizardError("credencial de pareamento curta")
    lowered = raw.lower()
    if "placeholder" in lowered or "preencher" in lowered or "mock" in lowered:
        raise VisualWizardError("credencial de pareamento invalida")
    return raw


def pairing_real_watchdog_seconds() -> float:
    max_timeout = max(PAIRING_REAL_MIN_WATCHDOG_SEC, PAIRING_REAL_MAX_SERVER_TIMEOUT_SEC)
    return min(max(PAIRING_REAL_MIN_WATCHDOG_SEC, PAIRING_REAL_TIMEOUT_SEC), max_timeout)


def pairing_real_state_after_poll(raw_state: object, *, final_poll: bool) -> str:
    state = str(raw_state or "pending")
    if final_poll and state != "authorized" and state not in PAIRING_REAL_TERMINAL_STATES:
        return "local_timeout"
    return state


def normalize_runtime_api_url(value: str) -> str:
    raw = validate_pairing_https_url(value, "api_url")
    parsed = urllib_parse.urlsplit(raw)
    path = parsed.path.rstrip("/")
    if path in {"", "/"}:
        path = "/search"
    return urllib_parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def device_fingerprint() -> str:
    hostname = socket.gethostname() or "totem"
    machine_id = ""
    for candidate in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            machine_id = pathlib.Path(candidate).read_text(encoding="utf-8").strip()
            if machine_id:
                break
        except Exception:
            continue
    seed = f"{hostname}:{machine_id or 'no-machine-id'}"
    digest = uuid.uuid5(uuid.NAMESPACE_DNS, seed).hex[:12]
    safe_hostname = re.sub(r"[^a-zA-Z0-9_.-]", "-", hostname)[:48] or "totem"
    return f"{safe_hostname}-{digest}"


def create_real_pairing_session(out_dir: pathlib.Path) -> dict[str, Any]:
    pairing_dir = require_pairing_mock_out_dir(out_dir / PAIRING_DIRNAME)
    status, body = http_json_request_no_auth(
        pairing_backend_endpoint("/totem-auth/activations"),
        method="POST",
        payload={"device_fingerprint": device_fingerprint()},
        timeout_sec=PAIRING_REAL_HTTP_TIMEOUT_SEC,
    )
    if not (200 <= status < 300) or not isinstance(body, dict):
        raise VisualWizardError("backend de pareamento indisponivel")

    activation_id = validate_environment_id(str(body.get("activation_id", "")))
    code = validate_pairing_code(str(body.get("user_code", "")))
    device_secret = str(body.get("device_secret", "")).strip()
    if len(device_secret) < 24:
        raise VisualWizardError("segredo de dispositivo invalido")
    authorize_url = validate_pairing_authorize_url(
        str(body.get("qr_url", "")),
        code=code,
        activation_id=activation_id,
    )
    if pairing_client is None or not hasattr(pairing_client, "qr_matrix"):
        raise VisualWizardError("encoder QR indisponivel")
    pairing_client.qr_matrix(authorize_url)
    expires_at = str(body.get("expires_at") or "").strip()
    poll_interval_ms = body.get("poll_interval_ms")
    poll_after_sec = 2.0
    if isinstance(poll_interval_ms, (int, float)) and poll_interval_ms > 0:
        poll_after_sec = max(1.0, min(10.0, float(poll_interval_ms) / 1000.0))

    public_session = {
        "schema": PAIRING_SESSION_SCHEMA,
        "mode": "real_totem_auth",
        "session_id": activation_id,
        "state": "pending",
        "pairing_code": code,
        "authorize_url": authorize_url,
        "expires_at_utc": expires_at,
        "poll_after_sec": poll_after_sec,
        "poll_token_public": False,
        "credential_public": False,
        "human_firebase_token_on_device": False,
        "private_values_written": False,
        "non_claims": [
            "not_written_to_final_config_yet",
            "not_human_firebase_token_on_device",
        ],
    }
    for stale_name in ("pairing-result.public.json", "private-values.json"):
        stale_path = pairing_dir / stale_name
        if stale_path.exists() and not stale_path.is_symlink():
            stale_path.unlink()
    session_path = pairing_dir / "pairing-session.public.json"
    write_pairing_json(session_path, public_session, pairing_dir)
    return {
        "session_id": activation_id,
        "pairing_code": code,
        "authorize_url": authorize_url,
        "device_secret": device_secret,
        "expires_at_utc": expires_at,
        "poll_after_sec": poll_after_sec,
        "session_public_path": str(session_path),
        "pairing_dir": str(pairing_dir),
    }


def poll_real_pairing_once(session_id: str, device_secret: str) -> dict[str, Any]:
    status, body = http_json_request_no_auth(
        pairing_backend_endpoint(f"/totem-auth/activations/{urllib_parse.quote(session_id, safe='')}/poll"),
        method="POST",
        payload={"device_secret": device_secret},
        timeout_sec=PAIRING_REAL_HTTP_TIMEOUT_SEC,
    )
    if not (200 <= status < 300) or not isinstance(body, dict):
        raise VisualWizardError("poll de pareamento indisponivel")
    return body


def write_real_pairing_result(
    out_dir: pathlib.Path,
    *,
    state: str,
    session_path: pathlib.Path,
    credential: dict[str, Any] | None,
) -> dict[str, Any]:
    private_path = out_dir / "private-values.json"
    private_written = False
    if state == "authorized" and credential is not None:
        environment_id = validate_environment_id(str(credential.get("environment_id", "")))
        station_id_raw = str(credential.get("station_id") or "").strip()
        private_values: dict[str, Any] = {
            "schema": PAIRING_PRIVATE_VALUES_SCHEMA,
            "api_url": normalize_runtime_api_url(str(credential.get("api_url", ""))),
            "api_key": validate_pairing_api_key(str(credential.get("api_key", ""))),
            "environment_id": environment_id,
            "issued_by": "c21-real-totem-auth",
            "human_firebase_token_on_device": False,
        }
        if station_id_raw:
            private_values["station_id"] = validate_environment_id(station_id_raw)
        api_token_id = str(credential.get("api_token_id") or "").strip()
        if api_token_id:
            private_values["api_token_id"] = api_token_id
        write_pairing_json(private_path, private_values, out_dir)
        private_written = True
    elif private_path.exists():
        private_path.unlink()

    result = {
        "schema": PAIRING_RESULT_SCHEMA,
        "passed": state == "authorized",
        "state": state,
        "session_public_path": str(session_path),
        "pairing_card_svg_path": None,
        "private_values_path": str(private_path) if private_written else None,
        "private_values_mode": "0600" if private_written else None,
        "public_artifacts_sanitized": True,
        "human_firebase_token_on_device": False,
    }
    write_pairing_json(out_dir / "pairing-result.public.json", result, out_dir)
    return result


def load_pairing_environment_id(private_values_path: str | None) -> str:
    if not private_values_path:
        raise VisualWizardError("pareamento sem credencial privada")
    path = pathlib.Path(private_values_path)
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise VisualWizardError("credencial privada invalida")
    if not setup.path_is_under(path.resolve(strict=True), setup.TMP_ROOT):
        raise VisualWizardError("credencial privada fora de /tmp")
    if file_mode(path) != setup.PRIVATE_FILE_MODE:
        raise VisualWizardError("credencial privada com permissao invalida")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise VisualWizardError("credencial privada invalida")
    return validate_environment_id(str(data.get("environment_id", "")))


def run_mock_environment_pairing(
    display: VisualDisplay,
    out_dir: pathlib.Path,
    *,
    layout_rotation_deg: int,
) -> tuple[str, EnvironmentPreflight] | None:
    display.show(
        "03-environment-pairing-start",
        build_screen_svg(
            active_step=2,
            title="Autorizar totem",
            subtitle="Criando codigo de pareamento...",
            footer="Aguarde",
            panel_title="Pareamento",
            panel_items=["Celular autoriza.", "Sem login na placa.", "Nada aplicado ainda."],
            layout_rotation_deg=layout_rotation_deg,
        ),
    )
    try:
        result = create_mock_pairing_artifacts(out_dir)
    except Exception:
        key = show_environment_validation_status(
            display,
            title="Pareamento indisponivel",
            subtitle="Nao foi possivel gerar o codigo agora.",
            footer="Enter tenta de novo | Esc volta",
            panel_items=["Nada foi salvo.", "Use ID manual.", "Tente de novo."],
            accent="#f59e0b",
            layout_rotation_deg=layout_rotation_deg,
        )
        if key in {"enter", "b", "B", "back", "escape"}:
            return None
        raise VisualWizardAbort("setup visual cancelado pelo operador")

    session_path = pathlib.Path(str(result["session_public_path"]))
    session = json.loads(session_path.read_text(encoding="utf-8"))
    state = str(result.get("state") or session.get("state") or "unknown")
    code = str(session.get("pairing_code") or "")
    url = str(session.get("authorize_url") or "")
    if result.get("passed") is True:
        environment_id = load_pairing_environment_id(str(result.get("private_values_path") or ""))
        display.show(
            "03-environment-pairing-authorized",
            build_screen_svg(
                active_step=2,
                title="Totem autorizado",
                subtitle="Ambiente recebido pelo pareamento.",
                footer="Enter continua | Esc volta",
                field_label="Codigo",
                field_value_hint=code,
                field_note=url,
                panel_title="Seguranca",
                panel_items=["Credencial privada.", "Token humano nao fica.", "Nada aplicado ainda."],
                accent="#22c55e",
                layout_rotation_deg=layout_rotation_deg,
            ),
        )
        key = read_advertised_action("enter", "b", "B", "back", "escape")
        if key == "enter":
            return environment_id, environment_preflight_pairing_authorized()
        if key in {"b", "B", "back", "escape"}:
            return None

    title_by_state = {
        "pending": "Aguardando autorizacao",
        "expired": "Codigo expirado",
        "denied": "Autorizacao negada",
        "backend_unavailable": "Servidor indisponivel",
        "empty_environment_list": "Sem ambientes",
        "already_used": "Codigo ja usado",
    }
    key = show_environment_validation_status(
        display,
        title=title_by_state.get(state, "Pareamento nao concluido"),
        subtitle="Use Enter para tentar de novo ou Esc para voltar.",
        footer="Enter tenta de novo | Esc volta",
        panel_items=["Nada foi salvo.", "Manual continua disponivel.", "Sem token humano."],
        accent="#f59e0b",
        layout_rotation_deg=layout_rotation_deg,
    )
    if key in {"enter", "b", "B", "back", "escape"}:
        return None
    raise VisualWizardAbort("setup visual cancelado pelo operador")


def run_real_environment_pairing(
    display: VisualDisplay,
    out_dir: pathlib.Path,
    *,
    layout_rotation_deg: int,
) -> tuple[str, EnvironmentPreflight] | None:
    display.show(
        "03-environment-pairing-real-start",
        build_screen_svg(
            active_step=2,
            title="Autorizar totem",
            subtitle="Criando codigo no servidor...",
            footer="Aguarde",
            panel_title="Pareamento",
            panel_items=["Celular autoriza.", "Sem login na placa.", "Nada aplicado ainda."],
            layout_rotation_deg=layout_rotation_deg,
        ),
    )
    try:
        session = create_real_pairing_session(out_dir)
    except Exception:
        key = show_environment_validation_status(
            display,
            title="Pareamento indisponivel",
            subtitle="Nao foi possivel criar o codigo agora.",
            footer="Enter tenta de novo | Esc volta",
            panel_items=["Nada foi salvo.", "Use ID manual.", "Verifique a internet."],
            accent="#f59e0b",
            layout_rotation_deg=layout_rotation_deg,
        )
        if key in {"enter", "b", "B", "back", "escape"}:
            return None
        raise VisualWizardAbort("setup visual cancelado pelo operador")

    pairing_dir = pathlib.Path(str(session["pairing_dir"]))
    session_path = pathlib.Path(str(session["session_public_path"]))
    code = str(session["pairing_code"])
    url = str(session["authorize_url"])
    poll_after_sec = float(session["poll_after_sec"])
    deadline = time.monotonic() + pairing_real_watchdog_seconds()
    state = "pending"
    renewal_count = 0

    while True:
        remaining_sec = deadline - time.monotonic()
        final_poll = remaining_sec <= 0.0
        if not final_poll:
            display.show(
                "03-environment-pairing-real-wait",
                build_screen_svg(
                    active_step=2,
                    title="Autorizar pelo celular",
                    subtitle="Escaneie o QR ou use o endereco e o codigo.",
                    footer="Esc volta",
                    panel_items=[],
                    extra_svg=pairing_wait_content_svg(url, code, layout_rotation_deg=layout_rotation_deg),
                    accent="#38bdf8",
                    layout_rotation_deg=layout_rotation_deg,
                    suppress_landscape_info_panel=True,
                ),
            )
            key = read_key(timeout_sec=min(poll_after_sec, max(0.05, remaining_sec)))
            if key in {"b", "B", "back", "escape"}:
                write_real_pairing_result(pairing_dir, state="denied", session_path=session_path, credential=None)
                return None
        try:
            poll = poll_real_pairing_once(str(session["session_id"]), str(session["device_secret"]))
        except Exception:
            state = "backend_unavailable"
            break
        state = pairing_real_state_after_poll(poll.get("status"), final_poll=final_poll)
        if state == "authorized":
            result = write_real_pairing_result(
                pairing_dir,
                state="authorized",
                session_path=session_path,
                credential=poll,
            )
            environment_id = load_pairing_environment_id(str(result.get("private_values_path") or ""))
            display.show(
                "03-environment-pairing-real-authorized",
                build_screen_svg(
                    active_step=2,
                    title="Totem autorizado",
                    subtitle="Ambiente recebido pelo pareamento.",
                    footer="Enter continua | Esc volta",
                    field_label="Codigo",
                    field_value_hint=code,
                    field_note=url,
                    panel_title="Seguranca",
                    panel_items=["Credencial privada.", "Token humano nao fica.", "Nada aplicado ainda."],
                    accent="#22c55e",
                    layout_rotation_deg=layout_rotation_deg,
                ),
            )
            key = read_advertised_action("enter", "b", "B", "back", "escape")
            if key == "enter":
                return environment_id, environment_preflight_pairing_authorized()
            if key in {"b", "B", "back", "escape"}:
                return None
        if (
            state == "expired"
            and renewal_count < PAIRING_REAL_MAX_RENEWALS
            and deadline - time.monotonic() > 0.0
        ):
            write_real_pairing_result(pairing_dir, state="expired", session_path=session_path, credential=None)
            display.show(
                "03-environment-pairing-real-renewing",
                build_screen_svg(
                    active_step=2,
                    title="Atualizando codigo",
                    subtitle="A sessao expirou. Gerando outro QR...",
                    footer="Esc volta",
                    panel_title="Pareamento",
                    panel_items=["Codigo antigo encerrado.", "Novo QR em instantes.", "Nada foi salvo."],
                    accent="#38bdf8",
                    layout_rotation_deg=layout_rotation_deg,
                ),
            )
            try:
                session = create_real_pairing_session(out_dir)
            except Exception:
                state = "backend_unavailable"
                break
            pairing_dir = pathlib.Path(str(session["pairing_dir"]))
            session_path = pathlib.Path(str(session["session_public_path"]))
            code = str(session["pairing_code"])
            url = str(session["authorize_url"])
            poll_after_sec = float(session["poll_after_sec"])
            renewal_count += 1
            state = "pending"
            continue
        if state in PAIRING_REAL_TERMINAL_STATES:
            break
    write_real_pairing_result(pairing_dir, state=state, session_path=session_path, credential=None)
    title_by_state = {
        "expired": "Codigo expirado",
        "denied": "Autorizacao cancelada",
        "backend_unavailable": "Servidor indisponivel",
        "empty_environment_list": "Sem ambientes",
        "already_used": "Codigo ja usado",
        "local_timeout": "Tempo de autorizacao encerrado",
    }
    key = show_environment_validation_status(
        display,
        title=title_by_state.get(state, "Pareamento nao concluido"),
        subtitle="Use Enter para tentar de novo ou Esc para voltar.",
        footer="Enter tenta de novo | Esc volta",
        panel_items=["Nada foi salvo.", "Manual continua disponivel.", "Sem token humano."],
        accent="#f59e0b",
        layout_rotation_deg=layout_rotation_deg,
    )
    if key in {"enter", "b", "B", "back", "escape"}:
        return None
    raise VisualWizardAbort("setup visual cancelado pelo operador")


def run_environment_pairing(
    display: VisualDisplay,
    out_dir: pathlib.Path,
    *,
    layout_rotation_deg: int,
) -> tuple[str, EnvironmentPreflight] | None:
    if pairing_real_enabled():
        return run_real_environment_pairing(display, out_dir, layout_rotation_deg=layout_rotation_deg)
    return run_mock_environment_pairing(display, out_dir, layout_rotation_deg=layout_rotation_deg)


def build_completion_screen_svg(status: dict[str, Any]) -> str:
    rotation_deg = int(status.get("validation", {}).get("rotation_degrees", 0))
    if APPLY_CONTEXT == "real-write":
        title = "Pronto para salvar"
        subtitle = "Confirme para gravar a configuracao final."
        footer = "Enter salva | Esc cancela"
        panel_items = [
            "Tela, Wi-Fi e ambiente revisados.",
            "A configuracao final ainda nao foi salva.",
            "Esc cancela sem gravar.",
        ]
    elif APPLY_CONTEXT == "dry-run":
        title = "Pronto para validar"
        subtitle = "Ao continuar, a candidata sera validada."
        footer = "Enter continua"
        panel_items = [
            "Dry-run privado.",
            "Writer bloqueado.",
            "Nada aplicado.",
        ]
    else:
        title = "Candidata preparada"
        subtitle = "Candidata temporaria pronta."
        footer = "Enter sai"
        panel_items = [
            f"Estado: {status['state']}",
            "Writer bloqueado.",
            "Nada aplicado.",
        ]
    return build_screen_svg(
        active_step=4,
        title=title,
        subtitle=subtitle,
        footer=footer,
        panel_title="Confirmacao final" if APPLY_CONTEXT == "real-write" else "Proximo passo",
        panel_items=panel_items,
        accent="#22d3ee" if APPLY_CONTEXT == "real-write" else "#94a3b8",
        layout_rotation_deg=rotation_deg,
    )


def show_complete(display: VisualDisplay, status: dict[str, Any]) -> None:
    display.show("06-complete", build_completion_screen_svg(status))
    wait_enter_or_cancel()


def run_visual_wizard(
    out_dir: pathlib.Path,
    *,
    mpv_bin: str,
    public_orientation_path: pathlib.Path | None = None,
    private_settings_context_path: pathlib.Path | None = None,
) -> dict[str, Any]:
    display = VisualDisplay(out_dir, mpv_bin=mpv_bin, enabled=True)
    c1523_phase("wizard_started")
    private_context = load_private_settings_context(private_settings_context_path) if private_settings_context_path else {}
    initial_rotation_deg = initial_rotation_from_context(private_context)
    initial_environment_id = str(private_context.get("environment_id", ""))
    state = initial_wizard_state(initial_rotation_deg, initial_environment_id)
    active_step = 0
    entry_focus_area = "content"
    try:
        with RawKeyboard():
            while True:
                layout_rotation_deg = int(state.rotation["rotation_deg"])
                try:
                    if active_step == 0:
                        state.rotation = choose_orientation(
                            display,
                            initial_rotation_deg=int(state.rotation["rotation_deg"]),
                            initial_focus_area=entry_focus_area,
                        )
                        state.rotation_status = "confirmed"
                        active_step = 1
                        entry_focus_area = "content"
                        continue

                    if active_step == 1:
                        c1523_phase("wifi_step_entered", mode="selection")
                        selected_network = choose_option(
                            display,
                            screen_id="02-connection",
                            active_step=1,
                            title="Wi-Fi",
                            subtitle="Escolha o Wi-Fi.",
                            options=list(NETWORK_OPTIONS),
                            panel_items=[
                                "Lista local.",
                                "Senha oculta.",
                                "Sem portal.",
                            ],
                            layout_rotation_deg=layout_rotation_deg,
                            initial_selected_index=network_option_index_for_step(
                                state.network.get("network_step") if state.network else None
                            ),
                            initial_focus_area=entry_focus_area,
                        )
                        if selected_network is None:
                            active_step = 0
                            entry_focus_area = "content"
                            continue
                        try:
                            if selected_network.key == "configured_wifi":
                                state.network = use_configured_wifi_network()
                                c1523_phase("wifi_step_done", network_step="existing_configured_wifi")
                            elif selected_network.key == "wifi_select":
                                maybe_network = run_wifi_persistent(display, out_dir, layout_rotation_deg=layout_rotation_deg)
                                if maybe_network is None:
                                    continue
                                state.network = maybe_network
                                c1523_phase(
                                    "wifi_step_done",
                                    network_step=state.network["network_step"],
                                    wifi_activation_result=state.network["wifi_activation_result"],
                                )
                            else:
                                state.network = network_defaults()
                                c1523_phase("wifi_step_done", network_step=state.network["network_step"])
                            state.network_status = "confirmed"
                            active_step = 2
                            entry_focus_area = "content"
                            continue
                        except VisualWizardError as exc:
                            display.show(
                                "02-connection-error",
                                build_screen_svg(
                                    active_step=1,
                                    title="Wi-Fi nao confirmado",
                                    subtitle=str(exc),
                                    footer="Enter volta | Esc cancela",
                                    panel_title="Tente de novo",
                                    panel_items=[
                                        "Nada foi salvo.",
                                        "Escolha outro caminho.",
                                        "Pode cancelar.",
                                    ],
                                    accent="#ef4444",
                                    layout_rotation_deg=layout_rotation_deg,
                                ),
                            )
                            key = read_advertised_action("enter", "b", "B", "back", "escape")
                            if key == "enter":
                                continue
                            raise VisualWizardAbort("setup visual cancelado pelo operador")

                    if active_step == 2:
                        c1523_phase(
                            "environment_input_entered",
                            network_step=state.network["network_step"] if state.network else "pending",
                        )
                        entry_method = choose_option(
                            display,
                            screen_id="03-environment",
                            active_step=2,
                            title="Ambiente",
                            subtitle="Como deseja autorizar este totem?",
                            options=list(ENVIRONMENT_ENTRY_OPTIONS),
                            panel_items=[
                                "Celular e mais simples.",
                                "Manual fica para suporte.",
                                "Nada salvo agora.",
                            ],
                            allow_back=True,
                            layout_rotation_deg=layout_rotation_deg,
                            initial_selected_index=1 if state.environment_id.strip() else 0,
                            initial_focus_area=entry_focus_area,
                        )
                        if entry_method is None:
                            active_step = 1
                            entry_focus_area = "content"
                            continue
                        if entry_method.key == "qr_pairing":
                            paired = run_environment_pairing(
                                display,
                                out_dir,
                                layout_rotation_deg=layout_rotation_deg,
                            )
                            if paired is None:
                                continue
                            environment_id, environment_preflight = paired
                            if environment_id != state.environment_id:
                                state.environment_preflight = None
                                state.environment_status = "pending"
                            state.environment_id = environment_id
                            state.environment_preflight = environment_preflight
                            state.environment_status = "confirmed"
                            active_step = 3
                            entry_focus_area = "content"
                            continue
                        environment_id = read_text_field(
                            display,
                            screen_id="03-environment-manual",
                            active_step=2,
                            title="Ambiente manual",
                            subtitle="Digite o ID do ambiente",
                            label="ID do ambiente",
                            hidden=False,
                            min_length=36,
                            max_length=36,
                            validator=validate_environment_id,
                            panel_items=[
                                "UUID do ambiente.",
                                "Backspace corrige.",
                                "Enter valida.",
                            ],
                            show_plain_value=True,
                            show_cursor=True,
                            custom_footer="Enter valida | Esc volta",
                            escape_returns_back=True,
                            validation_error_message="ID invalido. Verifique e tente novamente.",
                            layout_rotation_deg=layout_rotation_deg,
                            initial_value=state.environment_id,
                            initial_focus_area="content",
                        )
                        if environment_id is None:
                            active_step = 2
                            entry_focus_area = "content"
                            continue
                        if environment_id != state.environment_id:
                            state.environment_preflight = None
                            state.environment_status = "pending"
                        state.environment_id = environment_id
                        environment_preflight = run_environment_preflight(
                            display,
                            environment_id,
                            layout_rotation_deg=layout_rotation_deg,
                        )
                        if environment_preflight is None:
                            continue
                        state.environment_preflight = environment_preflight
                        state.environment_status = "confirmed"
                        active_step = 3
                        entry_focus_area = "content"
                        continue

                    if active_step == 3:
                        confirmed = review_and_confirm(
                            display,
                            state.environment_id,
                            state.rotation,
                            state.network,
                            environment_preflight=state.environment_preflight,
                            rotation_status=state.rotation_status,
                            network_status=state.network_status,
                            initial_focus_area=entry_focus_area,
                        )
                        if confirmed and wizard_can_commit(state):
                            status = write_visual_artifacts(
                                out_dir,
                                state.environment_id,
                                state.rotation,
                                state.network,
                                public_orientation_path=public_orientation_path,
                                environment_preflight=state.environment_preflight,
                            )
                            show_complete(display, status)
                            return status
                        active_step = first_incomplete_step(state) if not wizard_can_commit(state) else 2
                        entry_focus_area = "content"
                        continue

                    active_step = 0
                except VisualWizardStepJump as exc:
                    active_step = int(exc.step)
                    entry_focus_area = exc.focus_area
    finally:
        display.stop()


def generate_preview_screens(out_dir: pathlib.Path) -> None:
    display = VisualDisplay(out_dir, enabled=False)
    display.show(
        "01-orientation",
        build_screen_svg(
            active_step=0,
            title="Orientacao da tela",
            subtitle="Escolha como o totem esta instalado.",
            footer="Enter confirma | Cima menu | Baixo escolhe | Esc cancela",
            options=[Option(str(item["key"]), str(item["label"]), str(item["description"])) for item in DISPLAY_OPTIONS],
            selected_index=0,
            panel_items=["Escolha a posicao.", "Confira o preview.", "Salve ao final."],
            extra_svg=orientation_preview("landscape"),
            suppress_landscape_info_panel=True,
        ),
    )
    display.show(
        "05-review-pending",
        build_screen_svg(
            active_step=3,
            title="Pendencias antes de concluir",
            subtitle="Complete os itens pendentes antes de salvar.",
            footer="Enter corrige | Cima menu | Esc volta",
            panel_title="Bloqueado",
            panel_items=["Sem candidata parcial.", "Revise os pendentes.", "Nada salvo."],
            extra_svg=summary_rows_svg(
                [
                    ("Tela", "Paisagem (Default)"),
                    ("Wi-Fi", "Pendente"),
                    ("Ambiente", "Pendente"),
                ],
                layout_rotation_deg=0,
            ),
        ),
    )
    display.show(
        "01-orientation-confirm-landscape",
        build_screen_svg(
            active_step=0,
            title="Usar esta orientacao?",
            subtitle="Confira o sentido antes de continuar.",
            footer="Enter confirma | Cima menu | Baixo escolhe | Esc volta",
            options=[
                Option("confirm", "Usar esta orientacao", "A configuracao continuara neste formato."),
                Option("cancel", "Voltar e escolher outra", "Nada e gravado ate confirmar."),
            ],
            selected_index=0,
            panel_items=["Preview local.", "Sem alterar player agora.", "Pode voltar."],
            extra_svg=orientation_preview("landscape"),
            suppress_landscape_info_panel=True,
        ),
    )
    display.show(
        "01-orientation-confirm-portrait",
        build_screen_svg(
            active_step=0,
            title="Usar esta orientacao?",
            subtitle="Confira o sentido antes de continuar.",
            footer="Enter confirma | Cima menu | Baixo escolhe | Esc volta",
            options=[
                Option("confirm", "Usar esta orientacao", "A configuracao continuara neste formato."),
                Option("cancel", "Voltar e escolher outra", "Nada e gravado ate confirmar."),
            ],
            selected_index=0,
            panel_items=["Preview local.", "Sem alterar player agora.", "Pode voltar."],
            extra_svg=orientation_preview("portrait_right", layout_rotation_deg=90),
            layout_rotation_deg=90,
            suppress_landscape_info_panel=True,
        ),
    )
    display.show(
        "02-connection",
        build_screen_svg(
            active_step=1,
            title="Wi-Fi",
            subtitle="Escolha o Wi-Fi.",
            footer="Enter confirma | Cima menu | Baixo escolhe | Esc cancela",
            options=list(NETWORK_OPTIONS),
            selected_index=0,
            panel_items=["Lista local.", "Senha oculta.", "Sem portal."],
            layout_rotation_deg=90,
        ),
    )
    preview_networks = synthetic_wifi_networks_for_preview()
    display.show(
        "02-wifi-list-page-1",
        wifi_list_screen_svg(
            networks=preview_networks,
            selected_index=0,
            list_status="ok",
            updated_age_sec=0,
            refresh_message="Dados sinteticos de preview.",
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "02-wifi-list-page-2",
        wifi_list_screen_svg(
            networks=preview_networks,
            selected_index=wifi_list_page_size(90) + 1,
            list_status="ok",
            updated_age_sec=8,
            refresh_message="Setas continuam alem da area visivel.",
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "02-wifi-list-refreshing",
        wifi_list_screen_svg(
            networks=preview_networks,
            selected_index=1,
            list_status="ok",
            updated_age_sec=10,
            refresh_message="Atualizacao automatica.",
            layout_rotation_deg=90,
            refreshing=True,
        ),
    )
    display.show(
        "02-wifi-list-empty",
        wifi_list_screen_svg(
            networks=[],
            selected_index=0,
            list_status="ok",
            updated_age_sec=0,
            refresh_message="Nenhuma rede encontrada.",
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "02-wifi-psk-hidden",
        build_screen_svg(
            active_step=1,
            title="Senha Wi-Fi",
            subtitle="Digite a senha da rede.",
            footer="Enter confirma | Esc volta | F2 mostra",
            field_label="Senha Wi-Fi",
            field_value_hint=text_field_display_hint("preview-password", hidden=True, show_plain_value=False),
            field_note="Senha oculta por padrao.",
            panel_items=["Oculta por padrao.", "F2 mostra.", "Nao aparece em logs."],
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "02-wifi-psk-visible",
        build_screen_svg(
            active_step=1,
            title="Senha Wi-Fi",
            subtitle="Digite a senha da rede.",
            footer="Enter confirma | Esc volta | F2 oculta",
            field_label="Senha Wi-Fi",
            field_value_hint=text_field_display_hint("preview-password", hidden=True, show_plain_value=True),
            field_note="Valor visivel apenas no HDMI local.",
            panel_items=["Visivel so localmente.", "F2 oculta.", "Nao aparece em logs."],
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "03-environment",
        build_screen_svg(
            active_step=2,
            title="Ambiente",
            subtitle="Como deseja autorizar este totem?",
            footer="Enter confirma | Cima menu | Baixo escolhe | Esc volta",
            options=list(ENVIRONMENT_ENTRY_OPTIONS),
            selected_index=0,
            panel_items=["Celular e mais simples.", "Manual fica para suporte.", "Nada salvo agora."],
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "03-environment-manual",
        build_screen_svg(
            active_step=2,
            title="Ambiente manual",
            subtitle="Digite o ID do ambiente",
            footer="Enter valida | Esc volta",
            field_label="ID do ambiente",
            field_value_hint=text_field_display_hint(
                "11111111-2222-4333-8444-555555555555",
                hidden=False,
                show_plain_value=True,
                cursor_index=14,
            ),
            field_note="Entrada local.",
            panel_items=["UUID do ambiente.", "Backspace corrige.", "Enter valida."],
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "03-environment-pairing-wait",
        build_screen_svg(
            active_step=2,
            title="Autorizar pelo celular",
            subtitle="Escaneie o QR ou use o endereco e o codigo.",
            footer="Esc volta",
            panel_items=[],
            extra_svg=pairing_wait_content_svg(
                "https://home.dadooh.ai/totem/activate?code=ABCD1234",
                "ABCD1234",
                layout_rotation_deg=90,
            ),
            accent="#38bdf8",
            layout_rotation_deg=90,
            suppress_landscape_info_panel=True,
        ),
    )
    display.show(
        "03-environment-pairing-authorized",
        build_screen_svg(
            active_step=2,
            title="Totem autorizado",
            subtitle="Ambiente recebido pelo pareamento.",
            footer="Enter continua | Esc volta",
            field_label="Codigo",
            field_value_hint="ABCD1234",
            field_note=PAIRING_MANUAL_ENTRY_URL,
            panel_title="Seguranca",
            panel_items=["Credencial privada.", "Token humano nao fica.", "Nada aplicado ainda."],
            accent="#22c55e",
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "03-environment-validating",
        build_screen_svg(
            active_step=2,
            title="Ambiente",
            subtitle="Validando ambiente...",
            footer="Aguarde",
            panel_title="Checagem",
            panel_items=["Formato UUID OK.", "Consultando cadastro.", "Sem dados privados."],
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "03-environment-empty-content",
        build_screen_svg(
            active_step=2,
            title="Sem midia ativa agora",
            subtitle="O ambiente existe, mas pode iniciar aguardando conteudo.",
            footer="Enter continua | Esc volta",
            panel_title="Validacao",
            panel_items=["Ambiente nao e invalido.", "Player pode aguardar.", "Revise antes de salvar."],
            accent="#f59e0b",
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "03-environment-not-found",
        build_screen_svg(
            active_step=2,
            title="Ambiente nao encontrado",
            subtitle="Verifique o ID e tente novamente.",
            footer="Enter corrige | Esc cancela",
            panel_title="Validacao",
            panel_items=["Nada foi salvo.", "ID nao publicado.", "Corrija o campo."],
            accent="#ef4444",
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "05-review",
        build_screen_svg(
            active_step=3,
            title="Pronto para concluir",
            subtitle="Confira antes de concluir.",
            footer="Enter conclui | Esc volta",
            panel_title="Seguranca",
            panel_items=["Nada aplicado ainda.", "Dados privados ocultos.", "Esc volta."],
            extra_svg=summary_rows_svg(
                [
                    ("Tela", "Retrato para direita"),
                    ("Wi-Fi", "Wi-Fi configurado"),
                    ("Ambiente", "Informado"),
                ],
                layout_rotation_deg=90,
            ),
            layout_rotation_deg=90,
        ),
    )
    display.show(
        "06-complete",
        build_completion_screen_svg(
            {"state": "config_candidate_ready", "validation": {"rotation_degrees": 90}}
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
    display_enabled: bool = False,
) -> dict[str, Any]:
    prepare_private_dir(out_dir)
    rotation = resolve_display_selection(rotation_key)
    layout_rotation_deg = int(rotation["rotation_deg"])
    networks = synthetic_wifi_networks_for_preview()
    list_status = "synthetic"
    selected = networks[0] if networks else None
    metadata = wifi_adapter.wifi_selection_public_metadata(networks, selected)
    display = VisualDisplay(out_dir, mpv_bin=mpv_bin, enabled=display_enabled)
    try:
        display.show(
            "02-wifi-list-preview-page-1",
            wifi_list_screen_svg(
                networks=networks,
                selected_index=0,
                list_status=list_status,
                updated_age_sec=0,
                refresh_message="Dados sinteticos de preview.",
                layout_rotation_deg=layout_rotation_deg,
            ),
        )
        display.show(
            "02-wifi-list-preview-page-2",
            wifi_list_screen_svg(
                networks=networks,
                selected_index=wifi_list_page_size(layout_rotation_deg) + 1,
                list_status=list_status,
                updated_age_sec=8,
                refresh_message="Setas continuam alem da area visivel.",
                layout_rotation_deg=layout_rotation_deg,
            ),
        )
        display.show(
            "02-wifi-list-preview-refreshing",
            wifi_list_screen_svg(
                networks=networks,
                selected_index=1,
                list_status=list_status,
                updated_age_sec=10,
                refresh_message="Atualizacao automatica.",
                layout_rotation_deg=layout_rotation_deg,
                refreshing=True,
            ),
        )
        display.show(
            "02-wifi-list-preview-empty",
            wifi_list_screen_svg(
                networks=[],
                selected_index=0,
                list_status="ok",
                updated_age_sec=0,
                refresh_message="Nenhuma rede encontrada.",
                layout_rotation_deg=layout_rotation_deg,
            ),
        )
        display.show(
            "02-wifi-psk-preview-hidden",
            build_screen_svg(
                active_step=1,
                title="Senha Wi-Fi",
                subtitle="Digite a senha da rede.",
                footer="Enter confirma | Esc volta | F2 mostra",
                field_label="Senha Wi-Fi",
                field_value_hint=text_field_display_hint("preview-password", hidden=True, show_plain_value=False),
                field_note="Senha oculta por padrao.",
                panel_items=["Oculta por padrao.", "F2 mostra.", "Nao aparece em logs."],
                layout_rotation_deg=layout_rotation_deg,
            ),
        )
        display.show(
            "02-wifi-psk-preview-visible",
            build_screen_svg(
                active_step=1,
                title="Senha Wi-Fi",
                subtitle="Digite a senha da rede.",
                footer="Enter confirma | Esc volta | F2 oculta",
                field_label="Senha Wi-Fi",
                field_value_hint=text_field_display_hint("preview-password", hidden=True, show_plain_value=True),
                field_note="Valor visivel apenas no HDMI local.",
                panel_items=["Visivel so localmente.", "F2 oculta.", "Nao aparece em logs."],
                layout_rotation_deg=layout_rotation_deg,
            ),
        )
        if display_enabled:
            time.sleep(max(1, auto_exit_sec))
    finally:
        display.stop()
    status = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_timestamp(),
        "mode": "wifi_list_preview",
        "list_status": list_status,
        "preview_uses_synthetic_data": True,
        "preview_screens_generated": 6,
        "wifi_refresh_interval_sec": int(WIFI_LIST_REFRESH_SEC),
        "paginated_wifi_list": True,
        "password_hidden_by_default": True,
        "password_show_toggle_available": True,
        "password_show_toggle_key": "F2",
        "password_show_toggle_fallback_key": "Ctrl+P",
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


def run_scripted(
    out_dir: pathlib.Path,
    environment_id: str,
    rotation_key: str,
    network_step: str,
    *,
    public_orientation_path: pathlib.Path | None = None,
) -> dict[str, Any]:
    prepare_private_dir(out_dir)
    display = VisualDisplay(out_dir, enabled=False)
    generate_preview_screens(out_dir)
    environment = validate_environment_id(environment_id)
    rotation = resolve_display_selection(rotation_key)
    network = resolve_network_scripted(network_step)
    status = write_visual_artifacts(
        out_dir,
        environment,
        rotation,
        network,
        public_orientation_path=public_orientation_path,
    )
    display.show(
        "06-complete-scripted",
        build_screen_svg(
            active_step=4,
            title="Candidata preparada",
            subtitle="Candidata temporaria pronta.",
            footer="Fim do modo scripted",
            panel_items=["Validacao concluida.", "Sem writer.", "Nada aplicado."],
            accent="#22d3ee",
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


def assert_framebuffer_backbuffer_contract() -> None:
    class FlushableBuffer(bytearray):
        def __init__(self, initial: bytes) -> None:
            super().__init__(initial)
            self.flush_count = 0

        def flush(self) -> None:
            self.flush_count += 1

    renderer = object.__new__(FramebufferSVGRenderer)
    renderer.width = 4
    renderer.height = 2
    renderer.stride = 16
    renderer.fb = FlushableBuffer(b"\x7f" * (renderer.stride * renderer.height))
    renderer.draw_target = renderer.fb
    initial_frame = bytes(renderer.fb)
    original_draw_text = renderer.draw_text
    failure_injected = False

    def fail_mid_frame(*_args: Any, **_kwargs: Any) -> None:
        nonlocal failure_injected
        failure_injected = True
        raise VisualWizardError("synthetic render failure")

    renderer.draw_text = fail_mid_frame
    failing_svg = '<svg width="4" height="2"><text x="0" y="1">fail</text></svg>'
    try:
        renderer.render(failing_svg)
    except VisualWizardError as exc:
        assert_true(str(exc) == "synthetic render failure", "framebuffer test should observe the injected failure")
    else:
        raise AssertionError("synthetic framebuffer render should fail")
    assert_true(failure_injected, "framebuffer test must reach the injected mid-frame failure")
    assert_true(bytes(renderer.fb) == initial_frame, "failed render must preserve the complete visible frame")
    assert_true(renderer.draw_target is renderer.fb, "failed render must restore the live framebuffer target")
    assert_true(renderer.fb.flush_count == 0, "failed render must not flush a partial frame")

    renderer.draw_text = original_draw_text
    complete_svg = '<svg width="4" height="2"><rect x="0" y="0" width="4" height="2" fill="#ff0000"/></svg>'
    renderer.render(complete_svg)
    assert_true(
        bytes(renderer.fb) == FramebufferSVGRenderer.pixel_bytes((255, 0, 0)) * 8,
        "successful render should publish one complete frame",
    )
    assert_true(renderer.fb.flush_count == 1, "successful render should flush exactly once")
    assert_true(renderer.draw_target is renderer.fb, "successful render must restore the live framebuffer target")


def run_self_test() -> None:
    assert_framebuffer_backbuffer_contract()
    assert_raises(lambda: require_tmp_dir("/var/tmp/dadooh-c9-9"), "out-dir outside /tmp should fail")
    assert_raises(lambda: validate_environment_id("bad environment"), "environment with space should fail")
    assert_raises(lambda: validate_environment_id("api_key"), "api_key-like environment should fail")
    assert_raises(lambda: validate_environment_id("ENV-PRODUTO-VISUAL-01"), "non-UUID environment should fail")
    assert_true(
        validate_environment_id("11111111-2222-4333-8444-555555555555")
        == "11111111-2222-4333-8444-555555555555",
        "canonical UUID environment should pass",
    )
    assert_raises(lambda: resolve_display_selection("diagonal"), "unknown display option should fail")

    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c9-9-visual-wizard-self-test-", dir="/tmp"))
    try:
        synthetic_ssid = "TEST_WIFI_SHOULD_NOT_LEAK"
        synthetic_password = "TEST_PASSWORD_SHOULD_NOT_LEAK"
        context_environment_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        primary_environment_id = "11111111-2222-4333-8444-555555555555"
        public_environment_id = "22222222-3333-4444-8555-666666666666"
        assert_true(
            text_field_display_hint(synthetic_ssid, hidden=False, show_plain_value=True) == synthetic_ssid,
            "Wi-Fi network field should show local typed value",
        )
        password_hint = text_field_display_hint(synthetic_password, hidden=True, show_plain_value=False)
        assert_true(password_hint == "*" * len(synthetic_password), "Wi-Fi password should stay masked")
        assert_true(synthetic_password not in password_hint, "Wi-Fi password hint should not leak value")
        visible_password_hint = text_field_display_hint(synthetic_password, hidden=True, show_plain_value=True)
        assert_true(visible_password_hint == synthetic_password, "F2 password toggle should show value locally")
        count_hint = text_field_display_hint(synthetic_ssid, hidden=False, show_plain_value=False)
        assert_true(
            synthetic_ssid not in count_hint and "caracteres digitados" in count_hint,
            "count-only mode should not show raw value",
        )
        assert_true(
            text_field_display_hint(context_environment_id, hidden=False, show_plain_value=True) == context_environment_id,
            "environment prefill should be visible only in the local field",
        )
        assert_true(
            text_field_display_hint("abcd", hidden=False, show_plain_value=True, cursor_index=2) == "ab|cd",
            "cursor should render inside visible environment field",
        )
        assert_true(adjacent_navigable_step(0, 1) == 1, "right on focused steps should move to connection")
        assert_true(adjacent_navigable_step(0, -1) == 3, "left on focused steps should wrap to review")
        try:
            handle_step_focus_key("right", focused_step=0, active_step=0)
            instant_step_jump_ok = False
        except VisualWizardStepJump as exc:
            instant_step_jump_ok = exc.step == 1 and exc.focus_area == "steps"
        assert_true(instant_step_jump_ok, "right on top menu should immediately render the next step")
        focus_area, focused_step = handle_step_focus_key("down", focused_step=0, active_step=0)
        assert_true(focus_area == "content" and focused_step == 0, "down on active step should return to content")
        try:
            handle_step_focus_key("enter", focused_step=3, active_step=0)
            step_jump_ok = False
        except VisualWizardStepJump as exc:
            step_jump_ok = exc.step == 3 and exc.focus_area == "content"
        assert_true(step_jump_ok, "enter on another focused step should jump to that step")
        original_action_read_key = globals()["read_key"]
        try:
            action_keys = iter(("right", "tab", "down", "enter"))
            globals()["read_key"] = lambda timeout_sec=None: next(action_keys)
            assert_true(
                read_advertised_action("enter", "back", "escape") == "enter",
                "single-action prompts should ignore unsupported keys before Enter",
            )
            action_keys = iter(("left", "pageup", "escape"))
            assert_true(
                read_advertised_action("enter", "back", "escape") == "escape",
                "single-action prompts should preserve the advertised Escape action",
            )
            globals()["read_key"] = lambda timeout_sec=None: "q"
            assert_raises(
                lambda: read_advertised_action("enter", "back", "escape"),
                "explicit Q should preserve the global abort shortcut",
            )
        finally:
            globals()["read_key"] = original_action_read_key
        original_review_read_key = globals()["read_key"]
        review_display = VisualDisplay(root / "review-key-contract", enabled=False)
        review_keys = iter(("right", "tab", "down", "enter"))
        try:
            globals()["read_key"] = lambda timeout_sec=None: next(review_keys)
            review_confirmed = review_and_confirm(
                review_display,
                primary_environment_id,
                resolve_display_selection("landscape"),
                network_defaults(),
                environment_preflight=environment_preflight_pairing_authorized(),
            )
        finally:
            globals()["read_key"] = original_review_read_key
            review_display.stop()
        assert_true(
            review_confirmed,
            "unsupported review keys should be ignored until an explicit action is received",
        )
        navigation_state = initial_wizard_state(270, "")
        assert_true(navigation_state.rotation_status == "default", "initial orientation should be a default")
        assert_true(not wizard_can_commit(navigation_state), "empty navigation state should not commit")
        assert_true(first_incomplete_step(navigation_state) == 1, "network should be the first required pending step")
        assert_true(step_status_label(navigation_state, 3) == "Bloqueado", "review should block partial state")
        navigation_state.network = network_defaults(network_step="bench_mock")
        navigation_state.network_status = "confirmed"
        assert_true(first_incomplete_step(navigation_state) == 2, "environment should be pending after network")
        navigation_state.environment_id = primary_environment_id
        assert_true(
            environment_review_note(navigation_state.environment_id, navigation_state.environment_preflight)
            == "Precisa validar",
            "environment with UUID but no preflight should stay pending",
        )
        navigation_state.environment_preflight = preflight_with_confirmation(
            environment_preflight_unavailable(requires_confirmation=True)
        )
        assert_true(wizard_can_commit(navigation_state), "validated navigation state should commit")
        assert_true(first_incomplete_step(navigation_state) == 3, "ready state should land on review")
        assert_true(MAX_PANEL_ITEMS == 3, "operator panels should stay limited to three items")
        panel_limit_svg = info_panel(["one", "two", "three", "four"])
        assert_true("four" not in panel_limit_svg, "operator panel should not render more than three items")
        original_apply_context = globals()["APPLY_CONTEXT"]
        try:
            globals()["APPLY_CONTEXT"] = "real-write"
            completion_svg = build_completion_screen_svg(
                {"state": "config_candidate_ready", "validation": {"rotation_degrees": 0}}
            )
            assert_true("Pronto para salvar" in completion_svg, "real write should stop before claiming success")
            assert_true("ainda nao foi salva" in completion_svg, "real write should disclose the pending write")
            assert_true("Enter salva" in completion_svg, "final confirmation should name the write action")
            assert_true("Esc cancela" in completion_svg, "final confirmation should disclose cancel")
            assert_true("Configuracao salva" not in completion_svg, "wizard should not claim writer success")
            globals()["APPLY_CONTEXT"] = "candidate"
            candidate_svg = build_completion_screen_svg(
                {"state": "config_candidate_ready", "validation": {"rotation_degrees": 0}}
            )
            assert_true("Candidata preparada" in candidate_svg, "candidate mode should stay explicitly non-writing")
            assert_true("Nada aplicado" in candidate_svg, "candidate mode should disclose that nothing changed")
        finally:
            globals()["APPLY_CONTEXT"] = original_apply_context
        assert_true(
            len(wrap_text("one two three four five six seven", width=8, max_lines=1)) == 1,
            "wizard subtitles should be constrained to one visual line",
        )
        fixed_clock = "08/07/2026 16:45"
        assert_true(
            local_datetime_label(time.struct_time((2026, 7, 8, 16, 45, 0, 2, 190, -1))) == fixed_clock,
            "wizard clock should render local date and minute without seconds",
        )
        assert_true(
            local_datetime_label(time.struct_time((1970, 1, 1, 0, 0, 0, 3, 1, -1))) == CLOCK_IMPLAUSIBLE_LABEL,
            "wizard clock should not render implausible epoch dates",
        )
        assert_true(
            local_datetime_label(time.struct_time((2201, 1, 1, 0, 0, 0, 3, 1, -1))) == CLOCK_IMPLAUSIBLE_LABEL,
            "wizard clock should not render implausible future dates",
        )
        clock_step0_svg = build_screen_svg(
            active_step=0,
            title="Orientacao",
            subtitle="Escolha a tela.",
            footer="Enter confirma",
            options=[Option(str(item["key"]), str(item["label"]), str(item["description"])) for item in DISPLAY_OPTIONS],
            selected_index=0,
            clock_label=fixed_clock,
        )
        assert_true(fixed_clock in clock_step0_svg, "step 0 should render the clock label")
        assert_true("Layout paisagem" not in clock_step0_svg, "step 0 should not render the redundant layout note")
        assert_true('x="792" y="54"' in clock_step0_svg, "step 0 landscape clock should use the header clock slot")
        clock_step1_svg = build_screen_svg(
            active_step=1,
            title="Wi-Fi",
            subtitle="Escolha o Wi-Fi.",
            footer="Enter confirma",
            options=list(NETWORK_OPTIONS),
            selected_index=0,
            clock_label=fixed_clock,
        )
        assert_true(fixed_clock in clock_step1_svg, "steps after orientation should render the clock label")
        assert_true('x="792" y="54"' in clock_step1_svg, "landscape clock should reuse the header note slot")
        clock_portrait_svg = build_screen_svg(
            active_step=1,
            title="Wi-Fi",
            subtitle="Escolha o Wi-Fi.",
            footer="Enter confirma",
            options=list(NETWORK_OPTIONS),
            selected_index=0,
            layout_rotation_deg=90,
            clock_label=fixed_clock,
        )
        assert_true(fixed_clock in clock_portrait_svg, "portrait screens should render the clock label")
        assert_true('x="500" y="58"' in clock_portrait_svg, "portrait clock should stay attached to header row")
        clock_portrait_left_svg = build_screen_svg(
            active_step=1,
            title="Wi-Fi",
            subtitle="Escolha o Wi-Fi.",
            footer="Enter confirma",
            options=list(NETWORK_OPTIONS),
            selected_index=0,
            layout_rotation_deg=270,
            clock_label=fixed_clock,
        )
        assert_true(fixed_clock in clock_portrait_left_svg, "portrait-left screens should render the clock label")
        assert_true('x="500" y="58"' in clock_portrait_left_svg, "portrait-left clock should stay attached to header row")
        clock_inverted_svg = build_screen_svg(
            active_step=1,
            title="Wi-Fi",
            subtitle="Escolha o Wi-Fi.",
            footer="Enter confirma",
            options=list(NETWORK_OPTIONS),
            selected_index=0,
            layout_rotation_deg=180,
            clock_label=fixed_clock,
        )
        assert_true(fixed_clock in clock_inverted_svg, "landscape-inverted screens should render the clock label")
        assert_true('x="792" y="54"' in clock_inverted_svg, "landscape-inverted clock should reuse the header note slot")
        clock_invalid_svg = build_screen_svg(
            active_step=1,
            title="Wi-Fi",
            subtitle="Escolha o Wi-Fi.",
            footer="Enter confirma",
            options=list(NETWORK_OPTIONS),
            selected_index=0,
            clock_label=CLOCK_IMPLAUSIBLE_LABEL,
        )
        assert_true(CLOCK_IMPLAUSIBLE_LABEL in clock_invalid_svg, "invalid clocks should render the approved fallback")
        assert_true(
            text_field_apply_key("abcdef", "backspace", max_length=128, error="")[0] == "abcde",
            "Backspace should remove one character semantically",
        )
        assert_true(
            text_field_apply_key("abcdef", "clear", max_length=128, error="")[0] == "",
            "Ctrl+U clear should keep working",
        )
        edited, edited_cursor, edited_error, edited_changed = text_field_apply_edit_key(
            "abef",
            2,
            "c",
            max_length=128,
            error="old",
        )
        assert_true(
            (edited, edited_cursor, edited_error, edited_changed) == ("abcef", 3, "", True),
            "editable field should insert in the middle and clear stale error",
        )
        edited, edited_cursor, _, _ = text_field_apply_edit_key("abcef", 3, "delete", max_length=128, error="")
        assert_true((edited, edited_cursor) == ("abcf", 3), "Delete should remove character at cursor")
        edited, edited_cursor, _, _ = text_field_apply_edit_key("abcf", 3, "backspace", max_length=128, error="")
        assert_true((edited, edited_cursor) == ("abf", 2), "Backspace should remove before cursor")
        edited, edited_cursor, _, _ = text_field_apply_edit_key("abf", 2, "home", max_length=128, error="")
        assert_true((edited, edited_cursor) == ("abf", 0), "Home should move cursor to start")
        edited, edited_cursor, _, _ = text_field_apply_edit_key("abf", 0, "end", max_length=128, error="")
        assert_true((edited, edited_cursor) == ("abf", 3), "End should move cursor to end")
        endpoint = derive_environment_endpoint("https://api.example.com/search", primary_environment_id)
        assert_true(
            endpoint == f"https://api.example.com/environments/{primary_environment_id}",
            "environment endpoint should derive from /search URL",
        )
        assert_true(response_has_content({"total": 1}) == ("true", False), "search total>0 should mean content")
        assert_true(response_has_content({"total": 0}) == ("false", True), "search total=0 should warn, not invalidate")
        original_load_credentials = globals()["load_environment_validation_credentials"]
        original_http_json_request = globals()["http_json_request"]

        def fake_credentials() -> dict[str, str]:
            return {
                "api_url": "https://api.example.com/search",
                "api_key": "SYNTHETIC_KEY_NOT_PRINTED",
            }

        def fake_http_json_request(
            url: str,
            *,
            api_key: str,
            method: str,
            payload: dict[str, Any] | None = None,
            timeout_sec: float = ENVIRONMENT_VALIDATION_TIMEOUT_SEC,
        ) -> tuple[int, dict[str, Any] | None]:
            assert_true(api_key == "SYNTHETIC_KEY_NOT_PRINTED", "preflight should pass API key only to request layer")
            if method == "GET":
                return 200, {"ok": True}
            assert_true(payload is not None and payload.get("environmentId") == primary_environment_id, "search should use selected environment")
            return 200, {"total": 0}

        globals()["load_environment_validation_credentials"] = fake_credentials
        globals()["http_json_request"] = fake_http_json_request
        try:
            preflight = validate_environment_remote(primary_environment_id)
            assert_true(preflight.environment_exists == "true", "environment 200 should mark exists")
            assert_true(preflight.content_empty is True, "search total=0 should become content warning")
            assert_true(preflight.requires_confirmation is True, "empty content should require operator confirmation")
            public_preflight = json.dumps(preflight_public_status(preflight), sort_keys=True)
            for forbidden in (primary_environment_id, "SYNTHETIC_KEY_NOT_PRINTED", "api.example.com"):
                assert_true(forbidden not in public_preflight, "preflight public status should stay sanitized")

            def fake_http_404(
                url: str,
                *,
                api_key: str,
                method: str,
                payload: dict[str, Any] | None = None,
                timeout_sec: float = ENVIRONMENT_VALIDATION_TIMEOUT_SEC,
            ) -> tuple[int, dict[str, Any] | None]:
                if method == "GET":
                    raise urllib_error.HTTPError("https://redacted.invalid", 404, "Not Found", {}, None)
                return 200, {"total": 1}

            globals()["http_json_request"] = fake_http_404
            missing = validate_environment_remote(primary_environment_id)
            assert_true(missing.environment_not_found is True, "environment 404 should block")

            def fake_http_timeout(
                url: str,
                *,
                api_key: str,
                method: str,
                payload: dict[str, Any] | None = None,
                timeout_sec: float = ENVIRONMENT_VALIDATION_TIMEOUT_SEC,
            ) -> tuple[int, dict[str, Any] | None]:
                raise TimeoutError("synthetic timeout")

            globals()["http_json_request"] = fake_http_timeout
            unavailable = validate_environment_remote(primary_environment_id)
            assert_true(
                unavailable.validation_unavailable and unavailable.requires_confirmation,
                "validation unavailable should require confirmation",
            )
        finally:
            globals()["load_environment_validation_credentials"] = original_load_credentials
            globals()["http_json_request"] = original_http_json_request
        pairing_dir = require_tmp_dir(str(root / "pairing-mock"))
        pairing_result = create_mock_pairing_artifacts(pairing_dir, state="authorized")
        assert_true(pairing_result["passed"] is True, "authorized pairing mock should pass")
        pairing_private_path = pathlib.Path(str(pairing_result["private_values_path"]))
        assert_true(file_mode(pairing_private_path) == setup.PRIVATE_FILE_MODE, "pairing private values should be 0600")
        pairing_environment = load_pairing_environment_id(str(pairing_private_path))
        assert_true(
            pairing_environment == PAIRING_DEFAULT_ENVIRONMENT_ID,
            "pairing mock should provide a validated environment id",
        )
        pairing_public = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((pairing_dir / PAIRING_DIRNAME).glob("*"))
            if path.name != "private-values.json"
        )
        for forbidden in (
            PAIRING_DEFAULT_MOCK_API_KEY,
            PAIRING_DEFAULT_API_URL,
            PAIRING_DEFAULT_ENVIRONMENT_ID,
            PAIRING_DEFAULT_STATION_ID,
        ):
            assert_true(forbidden not in pairing_public, "pairing public artifacts should not leak private values")
        denied_pairing = create_mock_pairing_artifacts(pairing_dir, state="already_used")
        assert_true(denied_pairing["passed"] is False, "already_used pairing mock should not pass")
        assert_true(denied_pairing["private_values_path"] is None, "already_used pairing should not write private values")

        watchdog_timeout = min(
            max(PAIRING_REAL_MIN_WATCHDOG_SEC, PAIRING_REAL_TIMEOUT_SEC),
            max(PAIRING_REAL_MIN_WATCHDOG_SEC, PAIRING_REAL_MAX_SERVER_TIMEOUT_SEC),
        )
        assert_true(
            pairing_real_watchdog_seconds() == watchdog_timeout and watchdog_timeout >= 600.0,
            "pairing watchdog should outlive the server default TTL without using the board wall clock",
        )
        assert_true(
            PAIRING_REAL_TERMINAL_STATES.issubset(PAIRING_STATES),
            "all real pairing terminal states should be modeled explicitly",
        )
        assert_true(
            pairing_real_state_after_poll("authorized", final_poll=True) == "authorized",
            "authorization on the final poll should still win",
        )
        assert_true(
            pairing_real_state_after_poll("pending", final_poll=True) == "local_timeout",
            "pending on the final watchdog poll should not be mislabeled as server expiry",
        )
        assert_true(
            pairing_real_state_after_poll("processing", final_poll=True) == "local_timeout",
            "unknown final state should close the watchdog without a busy poll loop",
        )
        assert_true(
            pairing_real_state_after_poll("empty_environment_list", final_poll=False) == "empty_environment_list",
            "empty environment response should preserve its terminal state",
        )

        original_pairing_request = globals()["http_json_request_no_auth"]
        original_pairing_read_key = globals()["read_key"]
        original_pairing_base = os.environ.get("TOTEM_VISUAL_WIZARD_PAIRING_API_BASE_URL")
        try:
            os.environ["TOTEM_VISUAL_WIZARD_PAIRING_API_BASE_URL"] = "https://api.example.com"
            real_activation_id = "33333333-4444-4555-8666-777777777777"
            real_environment_id = "44444444-5555-4666-8777-888888888888"
            real_station_id = "55555555-6666-4777-8888-999999999999"
            real_api_key = "REAL_DEVICE_KEY_FOR_SELF_TEST_123456789"

            def fake_pairing_request(
                url: str,
                *,
                method: str,
                payload: dict[str, Any] | None = None,
                timeout_sec: float = ENVIRONMENT_VALIDATION_TIMEOUT_SEC,
            ) -> tuple[int, dict[str, Any] | None]:
                if url.endswith("/totem-auth/activations") and method == "POST":
                    assert_true(payload is not None and payload.get("device_fingerprint"), "real pairing should send fingerprint")
                    return 201, {
                        "activation_id": real_activation_id,
                        "device_secret": "device-secret-self-test-1234567890",
                        "user_code": "ZXCV9876",
                        "qr_url": "https://home.dadooh.ai/totem/activate?code=ZXCV9876",
                        "expires_at": "2026-07-08T15:00:00Z",
                        "poll_interval_ms": 1000,
                    }
                if url.endswith(f"/totem-auth/activations/{real_activation_id}/poll") and method == "POST":
                    assert_true(
                        payload is not None and payload.get("device_secret") == "device-secret-self-test-1234567890",
                        "poll should use device_secret",
                    )
                    return 200, {
                        "status": "authorized",
                        "credential_public": False,
                        "api_url": "https://api.example.com/search",
                        "api_key": real_api_key,
                        "api_token_id": "token-self-test",
                        "token_type": "x-api-key",
                        "environment_id": real_environment_id,
                        "station_id": real_station_id,
                    }
                raise AssertionError(f"unexpected pairing request {method} {url}")

            globals()["http_json_request_no_auth"] = fake_pairing_request
            real_pairing_dir = require_tmp_dir(str(root / "pairing-real"))
            real_session = create_real_pairing_session(real_pairing_dir)
            assert_true(
                real_session["expires_at_utc"] == "2026-07-08T15:00:00Z",
                "real pairing should carry the server expiry into the polling session",
            )
            assert_true(
                "activation_id=" not in str(real_session["authorize_url"]),
                "new QR URL should keep the activation id internal",
            )
            legacy_url = (
                "https://home.dadooh.ai/totem/activate?code=ZXCV9876"
                f"&activation_id={real_activation_id}"
            )
            assert_true(
                validate_pairing_authorize_url(
                    legacy_url,
                    code="ZXCV9876",
                    activation_id=real_activation_id,
                )
                == legacy_url,
                "legacy QR URLs should remain accepted during migration",
            )
            for invalid_authorize_url in (
                "https://example.com/totem/activate?code=ZXCV9876",
                "https://home.dadooh.ai/totem/activate?code=BADQ1234",
                "https://home.dadooh.ai/totem/activate?code=ZXCV9876&activation_id=",
                "https://home.dadooh.ai/totem/activate?code=ZXCV9876&utm_source=unexpected",
            ):
                try:
                    validate_pairing_authorize_url(
                        invalid_authorize_url,
                        code="ZXCV9876",
                        activation_id=real_activation_id,
                    )
                    raise AssertionError("unsafe pairing authorize URL accepted")
                except VisualWizardError:
                    pass
            landscape_pairing_svg = pairing_wait_content_svg(
                str(real_session["authorize_url"]),
                "ZXCV9876",
                layout_rotation_deg=0,
            )
            portrait_pairing_svg = pairing_wait_content_svg(
                str(real_session["authorize_url"]),
                "ZXCV9876",
                layout_rotation_deg=270,
            )
            for pairing_svg in (landscape_pairing_svg, portrait_pairing_svg):
                assert_true(
                    pairing_svg.count('data-qr-module="true"') > 100,
                    "pairing screen should contain a real QR matrix",
                )
                assert_true(PAIRING_MANUAL_ENTRY_URL in pairing_svg, "pairing screen should show manual URL")
                assert_true("ZXCV 9876" in pairing_svg, "pairing screen should group the short code")
            real_poll = poll_real_pairing_once(str(real_session["session_id"]), str(real_session["device_secret"]))
            real_result = write_real_pairing_result(
                pathlib.Path(str(real_session["pairing_dir"])),
                state=str(real_poll["status"]),
                session_path=pathlib.Path(str(real_session["session_public_path"])),
                credential=real_poll,
            )
            assert_true(real_result["passed"] is True, "real pairing authorized response should pass")
            real_private_path = pathlib.Path(str(real_result["private_values_path"]))
            assert_true(file_mode(real_private_path) == setup.PRIVATE_FILE_MODE, "real pairing private values should be 0600")
            real_private = json.loads(real_private_path.read_text(encoding="utf-8"))
            assert_true(real_private["api_url"].endswith("/search"), "real pairing should keep runtime search endpoint")
            real_public = "\n".join(
                path.read_text(encoding="utf-8")
                for path in sorted(pathlib.Path(str(real_session["pairing_dir"])).glob("*"))
                if path.name != "private-values.json"
            )
            for forbidden in (real_api_key, real_environment_id, real_station_id):
                assert_true(forbidden not in real_public, "real pairing public artifacts should not leak private values")

            renewal_activation_ids = (
                "66666666-7777-4888-8999-aaaaaaaaaaaa",
                "77777777-8888-4999-8aaa-bbbbbbbbbbbb",
            )
            renewal_codes = ("OLDQ1234", "NEWQ5678")
            renewal_create_count = 0

            def fake_renewing_pairing_request(
                url: str,
                *,
                method: str,
                payload: dict[str, Any] | None = None,
                timeout_sec: float = ENVIRONMENT_VALIDATION_TIMEOUT_SEC,
            ) -> tuple[int, dict[str, Any] | None]:
                nonlocal renewal_create_count
                if url.endswith("/totem-auth/activations") and method == "POST":
                    index = min(renewal_create_count, 1)
                    renewal_create_count += 1
                    return 201, {
                        "activation_id": renewal_activation_ids[index],
                        "device_secret": f"renew-device-secret-{index}-1234567890",
                        "user_code": renewal_codes[index],
                        "qr_url": f"https://home.dadooh.ai/totem/activate?code={renewal_codes[index]}",
                        "expires_at": "2026-07-08T15:00:00Z",
                        "poll_interval_ms": 1000,
                    }
                if url.endswith(f"/totem-auth/activations/{renewal_activation_ids[0]}/poll"):
                    return 200, {"status": "expired", "credential_public": False}
                if url.endswith(f"/totem-auth/activations/{renewal_activation_ids[1]}/poll"):
                    return 200, {
                        "status": "authorized",
                        "credential_public": False,
                        "api_url": "https://api.example.com/search",
                        "api_key": real_api_key,
                        "api_token_id": "token-renew-self-test",
                        "token_type": "x-api-key",
                        "environment_id": real_environment_id,
                        "station_id": real_station_id,
                    }
                raise AssertionError(f"unexpected renewing pairing request {method} {url}")

            class PairingDisplayProbe:
                def __init__(self) -> None:
                    self.screens: list[tuple[str, str]] = []

                def show(self, name: str, svg: str) -> None:
                    self.screens.append((name, svg))

            def fake_pairing_read_key(timeout_sec: float | None = None) -> str | None:
                return None if timeout_sec is not None else "enter"

            globals()["http_json_request_no_auth"] = fake_renewing_pairing_request
            globals()["read_key"] = fake_pairing_read_key
            renewal_display = PairingDisplayProbe()
            renewal_result = run_real_environment_pairing(
                renewal_display,  # type: ignore[arg-type]
                require_tmp_dir(str(root / "pairing-real-renewal")),
                layout_rotation_deg=0,
            )
            assert_true(renewal_create_count == 2, "expired pairing should create exactly one replacement session")
            assert_true(
                renewal_result is not None and renewal_result[0] == real_environment_id,
                "replacement QR session should complete authorization",
            )
            renewal_screen_names = [name for name, _svg in renewal_display.screens]
            assert_true(
                "03-environment-pairing-real-renewing" in renewal_screen_names,
                "expired pairing should visibly enter renewal",
            )
            waiting_svgs = [svg for name, svg in renewal_display.screens if name == "03-environment-pairing-real-wait"]
            assert_true(
                any("OLDQ 1234" in svg for svg in waiting_svgs)
                and any("NEWQ 5678" in svg for svg in waiting_svgs),
                "renewal should replace both the visible code and QR payload",
            )
        finally:
            globals()["http_json_request_no_auth"] = original_pairing_request
            globals()["read_key"] = original_pairing_read_key
            if original_pairing_base is None:
                os.environ.pop("TOTEM_VISUAL_WIZARD_PAIRING_API_BASE_URL", None)
            else:
                os.environ["TOTEM_VISUAL_WIZARD_PAIRING_API_BASE_URL"] = original_pairing_base
        assert_true(
            text_field_apply_key("ab", "v", max_length=128, error="")[0] == "abv",
            "lowercase v should remain a printable password character",
        )
        assert_true(
            text_field_apply_key("ab", "V", max_length=128, error="")[0] == "abV",
            "uppercase V should remain a printable password character",
        )
        assert_true(not is_secret_toggle_key("v") and not is_secret_toggle_key("V"), "printable V/v must not toggle password display")
        assert_true(is_secret_toggle_key("f2") and is_secret_toggle_key("toggle_secret"), "F2 and Ctrl+P should toggle password display")
        backspace_render_count = estimate_debounced_input_render_count(
            "x" * 20,
            ["backspace"] * 20,
            event_interval_sec=0.005,
        )
        assert_true(backspace_render_count <= 3, "20 rapid Backspaces should not render per key")
        sustained_render_count = estimate_debounced_input_render_count(
            "x" * 100,
            ["backspace"] * 100,
            event_interval_sec=0.005,
        )
        sustained_duration = 100 * 0.005
        assert_true(
            sustained_render_count / sustained_duration <= 12,
            "debounced text input should stay at or below 12 fps",
        )
        assert_true(selected_orientation_index_for_rotation(270) == 2, "portrait-left should be selected from saved rotation")
        assert_true(selected_orientation_index_for_rotation(90) == 1, "portrait-right should be selected from saved rotation")
        context_path = require_private_settings_context_path(str(root / "private-context" / "last-settings.json"))
        context_path.parent.mkdir(parents=True, mode=setup.PRIVATE_DIR_MODE)
        context_payload = {
            "schema_version": "dadooh-private-settings-context.v1",
            "environment_id": context_environment_id,
            "rotation_deg": 270,
            "network_step": "existing_configured_wifi",
        }
        context_path.write_text(json.dumps(context_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        context_path.chmod(setup.PRIVATE_FILE_MODE)
        loaded_context = load_private_settings_context(context_path)
        assert_true(loaded_context["environment_id"] == context_environment_id, "private context should load environment")
        assert_true(loaded_context["rotation_deg"] == 270, "private context should load rotation")
        assert_true(loaded_context["network_step"] == "existing_configured_wifi", "private context should load network step")
        public_orientation_path = root / "public-orientation-priority" / "orientation.json"
        public_orientation_path.parent.mkdir(parents=True, mode=setup.PRIVATE_DIR_MODE)
        public_orientation_path.write_text(
            json.dumps(
                {
                    "schema_version": "dadooh-display-orientation.v1",
                    "rotation_deg": 0,
                    "orientation_label": "landscape",
                    "updated_at": "2026-05-05T00:00:00Z",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        assert_true(
            initial_rotation_from_context(loaded_context, public_orientation_path) == 270,
            "private active-config context should win over stale public orientation",
        )
        local_wifi_options = wifi_adapter.parse_wifi_network_list(
            "TEST_WIFI_SHOULD_NOT_LEAK:88:WPA2\nTEST_WIFI_WEAK:22:--\n:99:WPA2\n",
        )
        assert_true(local_wifi_options[0]["ssid"] == synthetic_ssid, "local Wi-Fi list should keep SSID for HDMI")
        assert_true(local_wifi_options[0]["signal_percent"] == 88, "local Wi-Fi list should keep signal percent")
        local_metadata = wifi_adapter.wifi_selection_public_metadata(local_wifi_options, local_wifi_options[0])
        assert_true(local_metadata["wifi_networks_found_count"] == 2, "Wi-Fi count should be public")
        assert_true(local_metadata["selected_network_present"] is True, "selected network presence should be public")
        assert_true(local_metadata["selected_network_signal_bucket"] == "strong", "signal bucket should be public")
        assert_true(local_metadata["selected_network_security_present"] is True, "security presence should be public")
        assert_true(synthetic_ssid not in json.dumps(local_metadata), "Wi-Fi metadata should not leak SSID")
        page_fixture = [
            {"ssid": f"PAGE_TEST_{index:02d}", "signal_percent": 100 - index, "signal_bucket": "strong", "security_present": True}
            for index in range(18)
        ]
        page_1, start_1, end_1, _, _ = page_items(page_fixture, 0, 8)
        page_2, start_2, end_2, _, _ = page_items(page_fixture, 8, 8)
        page_3, start_3, end_3, _, _ = page_items(page_fixture, 16, 8)
        assert_true((start_1, end_1, len(page_1)) == (0, 8, 8), "pagination page 1 should show 1-8")
        assert_true((start_2, end_2, len(page_2)) == (8, 16, 8), "pagination page 2 should show 9-16")
        assert_true((start_3, end_3, len(page_3)) == (16, 18, 2), "pagination page 3 should show 17-18")
        assert_true(wifi_list_page_size(0) == 4, "landscape Wi-Fi list should show 4 networks")
        assert_true(wifi_list_page_size(90) == 5, "portrait Wi-Fi list should keep 5 networks")
        landscape_footer_y = screen_layout(0).height - 82
        landscape_last_card_bottom = 266 + (wifi_list_page_size(0) - 1) * (82 + 14) + 82
        assert_true(landscape_last_card_bottom < landscape_footer_y, "landscape Wi-Fi cards should not touch footer")
        portrait_footer_y = screen_layout(90).height - 82
        portrait_last_card_bottom = 314 + (wifi_list_page_size(90) - 1) * (98 + 14) + 98
        assert_true(portrait_last_card_bottom < portrait_footer_y, "portrait Wi-Fi cards should not touch footer")
        preserved_index, preserved = refresh_selected_index(page_fixture[:3], [page_fixture[2], page_fixture[1]], 1)
        assert_true(preserved and preserved_index == 1, "refresh should preserve selected SSID")
        disappeared_networks, disappeared_index, disappeared_message = apply_wifi_refresh_result(
            page_fixture[:3],
            [page_fixture[3], page_fixture[4]],
            "ok",
            2,
        )
        assert_true(len(disappeared_networks) == 2, "refresh should accept a valid changed list")
        assert_true(disappeared_index == 1, "refresh should keep selection index close when SSID disappears")
        assert_true("saiu da lista" in disappeared_message, "refresh should warn locally when selected SSID disappears")
        failed_networks, failed_index, failed_message = apply_wifi_refresh_result(page_fixture[:3], [], "timeout", 1)
        assert_true(failed_networks == page_fixture[:3], "failed refresh should keep last valid list")
        assert_true(failed_index == 1 and "lista anterior" in failed_message, "failed refresh should keep safe selection")
        assert_true(signal_bars(90) == "[####]" and signal_label(90) == "Forte", "90 signal should be four bars")
        assert_true(signal_bars(70) == "[###.]" and signal_label(70) in {"Forte", "Bom"}, "70 signal should be three bars")
        assert_true(signal_bars(40) == "[##..]" and signal_label(40) == "Medio", "40 signal should be two bars")
        assert_true(signal_bars(20) == "[#...]" and signal_label(20) == "Fraco", "20 signal should be one bar")

        preview_dir = require_tmp_dir(str(root / "preview"))
        prepare_private_dir(preview_dir)
        generate_preview_screens(preview_dir)
        orientation_preview_path = next((preview_dir / "screens").glob("*-01-orientation.svg"))
        orientation_preview_text = orientation_preview_path.read_text(encoding="utf-8")
        assert_true("orientation-preview" in orientation_preview_text, "orientation step should include visual preview")
        assert_true('id="orientation-preview-shell"' in orientation_preview_text, "orientation preview should expose shell marker")
        assert_true('id="info-panel"' not in orientation_preview_text, "landscape orientation preview should omit info panel")
        assert_true("Escolha a posicao." not in orientation_preview_text, "landscape orientation preview should omit side-panel bullets")
        assert_true("Confira o preview." not in orientation_preview_text, "landscape orientation preview should not render overlapping panel")
        assert_true("DADOOH" not in orientation_preview_text, "orientation marker should use vector blocks, not text")
        landscape_confirm = next((preview_dir / "screens").glob("*-01-orientation-confirm-landscape.svg"))
        landscape_confirm_text = landscape_confirm.read_text(encoding="utf-8")
        assert_true("orientation-preview" in landscape_confirm_text, "landscape confirmation should keep visual preview")
        assert_true('id="info-panel"' not in landscape_confirm_text, "landscape confirmation should omit info panel")
        assert_true("Preview local." not in landscape_confirm_text, "landscape confirmation should omit overlapping panel")
        assert_true(
            any((preview_dir / "screens").glob("*-01-orientation-confirm-portrait.svg")),
            "preview should generate orientation confirmation screen",
        )
        landscape_without_preview = build_screen_svg(
            active_step=1,
            title="Wi-Fi",
            subtitle="Escolha a rede.",
            footer="Enter confirma | Cima menu | Baixo escolhe | Esc volta",
            options=list(NETWORK_OPTIONS),
            selected_index=0,
            panel_items=["Lista local."],
            layout_rotation_deg=0,
        )
        assert_true(
            'id="info-panel"' in landscape_without_preview,
            "landscape screens without orientation preview should keep info panel",
        )
        portrait_confirm = next((preview_dir / "screens").glob("*-01-orientation-confirm-portrait.svg"))
        portrait_confirm_text = portrait_confirm.read_text(encoding="utf-8")
        assert_true("orientation-preview" in portrait_confirm_text, "orientation confirmation should keep visual preview")
        assert_true('id="info-panel"' in portrait_confirm_text, "portrait confirmation should keep non-overlapping info panel")
        assert_true("Preview local." in portrait_confirm_text, "portrait confirmation should keep non-overlapping panel")
        portrait_connection = next((preview_dir / "screens").glob("*-02-connection.svg"))
        portrait_connection_text = portrait_connection.read_text(encoding="utf-8")
        assert_true('id="info-panel"' in portrait_connection_text, "screens without preview should keep info panel")
        assert_true('width="768" height="1024"' in portrait_connection_text, "portrait preview should use native portrait canvas")
        assert_true(
            'data-display-rotation-deg="90"' in portrait_connection_text,
            "portrait preview should carry display rotation contract",
        )
        wifi_preview_page = next((preview_dir / "screens").glob("*-02-wifi-list-page-1.svg"))
        wifi_preview_text = wifi_preview_page.read_text(encoding="utf-8")
        assert_true("TEST_WIFI_STRONG" in wifi_preview_text, "synthetic Wi-Fi preview should show local SSID")
        assert_true("Mostrando 1-5 de" in wifi_preview_text, "Wi-Fi preview should show pagination position")
        assert_true("96%" in wifi_preview_text and "Forte" in wifi_preview_text, "Wi-Fi preview should show signal clarity")
        assert_true(any((preview_dir / "screens").glob("*-02-wifi-list-empty.svg")), "Wi-Fi preview should include empty state")
        assert_true(any((preview_dir / "screens").glob("*-02-wifi-psk-hidden.svg")), "Wi-Fi preview should include hidden password")
        assert_true(any((preview_dir / "screens").glob("*-02-wifi-psk-visible.svg")), "Wi-Fi preview should include visible password")
        assert_true(file_mode(preview_dir / "screens") == setup.PRIVATE_DIR_MODE, "preview screens should be 0700")

        wifi_preview_dir = require_tmp_dir(str(root / "wifi-preview"))
        wifi_preview_status = show_wifi_list_preview(
            wifi_preview_dir,
            mpv_bin="mpv",
            auto_exit_sec=1,
            rotation_key="landscape",
            display_enabled=False,
        )
        wifi_preview_public_text = (wifi_preview_dir / "wifi-list-preview-status.json").read_text(encoding="utf-8")
        landscape_wifi_preview = next((wifi_preview_dir / "screens").glob("*-02-wifi-list-preview-page-1.svg"))
        landscape_wifi_preview_text = landscape_wifi_preview.read_text(encoding="utf-8")
        assert_true("Mostrando 1-4 de" in landscape_wifi_preview_text, "landscape Wi-Fi preview should show 1-4")
        assert_true(
            landscape_wifi_preview_text.count('data-option-card="true"') == wifi_list_page_size(0),
            "landscape Wi-Fi preview should render 4 network cards",
        )
        assert_true("<circle" not in landscape_wifi_preview_text, "option cards must use framebuffer-rendered rect markers")
        assert_true("TEST_WIFI_COUNTER" not in landscape_wifi_preview_text, "landscape Wi-Fi preview should not render a fifth card")
        portrait_footer_probe = footer_text(
            "Enter confirma | Cima/Baixo escolhe | R atualiza | Esc volta",
            layout_rotation_deg=90,
        )
        assert_true("Enter confirma" in portrait_footer_probe, "footer should preserve primary action")
        assert_true("Esc volta" in portrait_footer_probe, "footer should preserve escape action before optional actions")
        long_footer_probe = footer_text(
            "Enter confirma | Cima/Baixo escolhe | R atualiza | PageDown | Esc volta",
            layout_rotation_deg=90,
        )
        assert_true("Enter confirma" in long_footer_probe, "long footer should preserve primary action")
        assert_true("Esc volta" in long_footer_probe, "long footer should preserve escape action beyond the fourth item")
        assert_true(wifi_preview_status["paginated_wifi_list"] is True, "Wi-Fi list preview should be paginated")
        assert_true(wifi_preview_status["password_show_toggle_key"] == "F2", "password toggle should use F2")
        assert_true(wifi_preview_status["password_show_toggle_fallback_key"] == "Ctrl+P", "password fallback should use Ctrl+P")
        for forbidden in (synthetic_ssid, synthetic_password, "TEST_WIFI_STRONG", "preview-password"):
            assert_true(forbidden not in wifi_preview_public_text, "Wi-Fi preview status should stay sanitized")

        out_dir = require_tmp_dir(str(root / "out"))
        status = run_scripted(
            out_dir,
            environment_id=primary_environment_id,
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
        assert_true(candidate["environment_id"] == primary_environment_id, "candidate should keep environment")
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
        assert_sanitized_outputs(out_dir, primary_environment_id)
        public_text = output_text(out_dir)
        for forbidden in (synthetic_ssid, synthetic_password, context_environment_id):
            assert_true(forbidden not in public_text, "Wi-Fi credentials should not be public artifacts")

        public_dir = require_tmp_dir(str(root / "public-orientation"))
        public_path = require_public_orientation_path(str(public_dir / ORIENTATION_FILENAME))
        public_out_dir = require_tmp_dir(str(root / "out-public"))
        public_status = run_scripted(
            public_out_dir,
            environment_id=public_environment_id,
            rotation_key="landscape_inverted",
            network_step="bench_mock",
            public_orientation_path=public_path,
        )
        public_contract = json.loads(public_path.read_text(encoding="utf-8"))
        assert_true(file_mode(public_path) == 0o644, "public orientation file should be 0644")
        assert_true(public_contract["rotation_deg"] == 180, "public orientation should keep rotation")
        assert_true(set(public_contract) == {"schema_version", "updated_at", "rotation_deg", "orientation_label"}, "public orientation should be allowlisted")
        assert_true(public_status["orientation"]["public_orientation_contract_written"] is True, "public orientation should be recorded")
        assert_true(public_status["guardrails"]["allowlisted_data_state_written"] is True, "allowlisted /data write should be recorded")
        public_text = output_text(public_out_dir) + public_path.read_text(encoding="utf-8")
        for forbidden in (synthetic_ssid, synthetic_password, public_environment_id, "api_key"):
            assert_true(forbidden not in public_text, "public orientation/status should stay sanitized")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run C9.9 local visual setup wizard.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Artifact directory under /tmp.")
    parser.add_argument("--mpv-bin", default="mpv", help="MPV binary for visual DRM rendering.")
    parser.add_argument(
        "--environment-id",
        default="11111111-2222-4333-8444-555555555555",
        help="Scripted environment_id UUID.",
    )
    parser.add_argument("--rotation-key", default="landscape", help="Scripted rotation key.")
    parser.add_argument("--network-step", default="configured_wifi", help="Scripted network step.")
    parser.add_argument("--auto-exit-sec", type=int, default=12, help="Preview display duration.")
    parser.add_argument("--show-preview", action="store_true", help="Display preview screens with MPV/DRM.")
    parser.add_argument(
        "--write-public-orientation",
        action="store_true",
        help="Write allowlisted orientation contract outside /tmp.",
    )
    parser.add_argument(
        "--public-orientation-path",
        default=str(PUBLIC_ORIENTATION_PATH),
        help="Allowlisted public orientation path.",
    )
    parser.add_argument(
        "--private-settings-context-path",
        default=str(PRIVATE_SETTINGS_CONTEXT_PATH),
        help="Restricted private settings context path.",
    )
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
        public_orientation_path = (
            require_public_orientation_path(args.public_orientation_path) if args.write_public_orientation else None
        )
        private_settings_context_path = require_private_settings_context_path(args.private_settings_context_path)
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
                display_enabled=args.show_preview,
            )
            print(json.dumps(status, indent=2, sort_keys=True))
            return 0
        if args.scripted:
            status = run_scripted(
                out_dir,
                args.environment_id,
                args.rotation_key,
                args.network_step,
                public_orientation_path=public_orientation_path,
            )
            print(json.dumps(status, indent=2, sort_keys=True))
            return 0
        run_visual_wizard(
            out_dir,
            mpv_bin=args.mpv_bin,
            public_orientation_path=public_orientation_path,
            private_settings_context_path=private_settings_context_path,
        )
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
