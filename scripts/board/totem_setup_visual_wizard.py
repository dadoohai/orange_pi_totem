#!/usr/bin/env python3
"""C9.9 visual local setup wizard for HDMI + keyboard.

The visual wizard renders product screens as private SVG files under /tmp and
uses MPV/DRM only as a temporary local renderer. It keeps the C9.8 Wi-Fi
adapter and C5.1 candidate handoff, and does not read/write real config or call
the writer.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import pathlib
import select
import shutil
import signal
import socket
import stat
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

CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720
BRAND = "Dadooh"
TITLE = "Configuracao do Totem"
STEPS = ("Inicio", "Conexao", "Ambiente", "Tela", "Revisao", "Concluir")

CANDIDATE_FILENAME = "config.candidate.json"
STATUS_FILENAME = "setup-status.json"
SUMMARY_FILENAME = "summary.txt"
CANCELLED_FILENAME = "setup-cancelled.json"
FAILED_FILENAME = "setup-failed.json"

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


class VisualWizardAbort(RuntimeError):
    """Raised when the operator intentionally cancels the visual setup."""


class VisualWizardError(RuntimeError):
    """Public-safe visual wizard error."""


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    description: str


NETWORK_OPTIONS = (
    Option(
        "configured_wifi",
        "Usar Wi-Fi ja configurado",
        "Usa o perfil dedicado ja validado neste totem.",
    ),
    Option(
        "wifi_persistent",
        "Configurar Wi-Fi deste totem",
        "Coleta rede e senha localmente e mantem perfil dedicado.",
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
        "description": "Tela na posicao normal.",
        "rotation_deg": 0,
    },
    {
        "key": "portrait_right",
        "label": "Retrato para direita",
        "description": "Topo da imagem virado para a direita.",
        "rotation_deg": 90,
    },
    {
        "key": "portrait_left",
        "label": "Retrato para esquerda",
        "description": "Topo da imagem virado para a esquerda.",
        "rotation_deg": 270,
    },
    {
        "key": "landscape_inverted",
        "label": "Invertido",
        "description": "Imagem de cabeca para baixo.",
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


def step_indicator(active_step: int) -> str:
    parts = []
    x = 86
    y = 92
    for index, step in enumerate(STEPS):
        active = index == active_step
        fill = "#ecfeff" if active else "#1f2937"
        stroke = "#0891b2" if active else "#334155"
        text_fill = "#0f172a" if active else "#cbd5e1"
        width = 148 if index in {0, 5} else 154
        parts.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="44" rx="8" fill="{fill}" stroke="{stroke}"/>'
            f'<text x="{x + 18}" y="{y + 29}" font-family="Arial, DejaVu Sans, sans-serif" '
            f'font-size="17" font-weight="700" fill="{text_fill}">{index + 1}. {escape_text(step)}</text>'
        )
        x += width + 14
    return "\n  ".join(parts)


def option_cards(options: list[Option], selected_index: int) -> str:
    parts = []
    y = 262
    for index, option in enumerate(options[:5]):
        active = index == selected_index
        fill = "#f8fafc" if active else "#182130"
        stroke = "#06b6d4" if active else "#334155"
        title_fill = "#111827" if active else "#f8fafc"
        body_fill = "#334155" if active else "#cbd5e1"
        marker_fill = "#0891b2" if active else "#475569"
        parts.append(
            f'<rect x="96" y="{y}" width="760" height="82" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
            f'<circle cx="132" cy="{y + 41}" r="18" fill="{marker_fill}"/>'
            f'<text x="126" y="{y + 48}" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" '
            f'font-weight="700" fill="#ffffff">{index + 1}</text>'
            f'<text x="168" y="{y + 34}" font-family="Arial, DejaVu Sans, sans-serif" font-size="24" '
            f'font-weight="700" fill="{title_fill}">{escape_text(option.label)}</text>'
            f'<text x="168" y="{y + 62}" font-family="Arial, DejaVu Sans, sans-serif" font-size="17" '
            f'fill="{body_fill}">{escape_text(option.description)}</text>'
        )
        y += 96
    return "\n  ".join(parts)


def info_panel(items: list[str], *, title: str = "Nesta etapa") -> str:
    y = 278
    bullet_parts = []
    for item in items[:5]:
        bullet_parts.append(
            f'<circle cx="924" cy="{y - 6}" r="5" fill="#06b6d4"/>'
            f'{svg_lines(item, x=944, y=y, size=17, fill="#cbd5e1", width=30, line_gap=24, max_lines=2)}'
        )
        y += 66
    return f"""
  <rect x="888" y="220" width="300" height="330" rx="8" fill="#111827" stroke="#334155"/>
  <text x="920" y="260" font-family="Arial, DejaVu Sans, sans-serif" font-size="24" font-weight="700" fill="#f8fafc">{escape_text(title)}</text>
  {' '.join(bullet_parts)}
"""


def field_panel(label: str, value_hint: str, note: str) -> str:
    value_svg = svg_lines(
        value_hint,
        x=132,
        y=392,
        size=26,
        fill="#111827",
        width=44,
        line_gap=34,
        max_lines=2,
        weight=700,
    )
    return f"""
  <rect x="96" y="300" width="760" height="130" rx="8" fill="#f8fafc" stroke="#06b6d4" stroke-width="2"/>
  <text x="132" y="346" font-family="Arial, DejaVu Sans, sans-serif" font-size="20" font-weight="700" fill="#0f172a">{escape_text(label)}</text>
  {value_svg}
  <text x="132" y="462" font-family="Arial, DejaVu Sans, sans-serif" font-size="18" fill="#475569">{escape_text(note)}</text>
"""


def footer_text(text: str) -> str:
    return (
        f'<rect x="0" y="650" width="{CANVAS_WIDTH}" height="70" fill="#0b1120"/>'
        f'<text x="96" y="692" font-family="Arial, DejaVu Sans, sans-serif" '
        f'font-size="20" fill="#dbeafe">{escape_text(text)}</text>'
    )


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
    accent: str = "#06b6d4",
) -> str:
    options_svg = option_cards(options, selected_index) if options else ""
    field_svg = field_panel(field_label, field_value_hint, field_note) if field_label is not None else ""
    panel_svg = info_panel(panel_items or [], title=panel_title)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" role="img" aria-label="Dadooh setup visual wizard">
  <rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="#0f172a"/>
  <rect x="0" y="0" width="{CANVAS_WIDTH}" height="12" fill="{accent}"/>
  <rect x="0" y="12" width="{CANVAS_WIDTH}" height="132" fill="#111827"/>
  <text x="96" y="58" font-family="Arial, DejaVu Sans, sans-serif" font-size="38" font-weight="700" fill="#f8fafc">{BRAND}</text>
  <text x="250" y="56" font-family="Arial, DejaVu Sans, sans-serif" font-size="20" fill="#94a3b8">{TITLE}</text>
  {step_indicator(active_step)}
  <text x="96" y="200" font-family="Arial, DejaVu Sans, sans-serif" font-size="44" font-weight="700" fill="#f8fafc">{escape_text(title)}</text>
  {svg_lines(subtitle, x=98, y=236, size=21, fill="#cbd5e1", width=62, line_gap=28, max_lines=2)}
  {options_svg}
  {field_svg}
  {panel_svg}
  {footer_text(footer)}
</svg>
"""


class VisualDisplay:
    def __init__(self, out_dir: pathlib.Path, *, mpv_bin: str = "mpv", enabled: bool = True) -> None:
        self.out_dir = out_dir
        self.screens_dir = out_dir / "screens"
        self.ipc_path = out_dir / "visual-wizard-mpv.sock"
        self.mpv_bin = mpv_bin
        self.enabled = enabled
        self.process: subprocess.Popen[bytes] | None = None
        self.sequence = 0
        prepare_private_dir(self.screens_dir)

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
            "--loop-file=inf",
            "--image-display-duration=inf",
            "--keep-open=yes",
            "--no-terminal",
            "--no-osc",
            "--osd-level=0",
            "--input-terminal=no",
            "--input-default-bindings=no",
            "--input-vo-keyboard=no",
            "--cursor-autohide=always",
            "--vo=gpu",
            "--gpu-context=drm",
            "--ao=null",
            f"--input-ipc-server={self.ipc_path}",
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

    def send_command(self, command: list[Any]) -> bool:
        if not self.enabled or self.process is None or self.process.poll() is not None:
            return False
        payload = json.dumps({"command": command}).encode("utf-8") + b"\n"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(1.0)
                client.connect(str(self.ipc_path))
                client.sendall(payload)
            return True
        except OSError:
            return False

    def show(self, screen_id: str, svg: str) -> pathlib.Path:
        path = self.write_svg(screen_id, svg)
        if not self.enabled:
            return path
        if self.process is None:
            self.ensure_started(path)
        elif not self.send_command(["loadfile", str(path), "replace"]):
            self.stop()
            self.ensure_started(path)
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


class RawKeyboard:
    def __enter__(self) -> "RawKeyboard":
        self.fd = sys.stdin.fileno()
        self.previous = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.previous)


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
            ready, _, _ = select.select([sys.stdin], [], [], 0.03)
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
        if rest in {b"[3~", b"[P"}:
            return "backspace"
        if rest in {b"OQ", b"[12~"}:
            return "back"
        return "escape"
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
) -> str | None:
    value = ""
    error = ""
    while True:
        if hidden:
            hint = "*" * len(value) if value else "Aguardando entrada"
        elif show_plain_value:
            hint = value or "Aguardando entrada"
        else:
            hint = f"{len(value)} caracteres digitados" if value else "Aguardando entrada"
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


def collect_wifi_credentials(display: VisualDisplay) -> pathlib.Path | None:
    ssid = read_text_field(
        display,
        screen_id="02-wifi-ssid",
        active_step=1,
        title="Configurar Wi-Fi",
        subtitle="Digite a rede neste totem. Ela nao sera publicada em status, resumo ou evidencia.",
        label="Rede Wi-Fi",
        hidden=False,
        min_length=1,
        max_length=128,
        panel_items=[
            "Use uma rede WPA/WPA2 comum.",
            "Evite portal cativo nesta rodada.",
            "O perfil dedicado sera mantido.",
        ],
    )
    if ssid is None:
        return None
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
        ),
    )
    key = read_key()
    if key == "back":
        return None
    if key != "enter":
        raise VisualWizardAbort("setup visual cancelado pelo operador")
    return write_wifi_secrets_file(prepare_wifi_secrets_dir(), ssid, psk)


def wifi_network_from_status(adapter_status: dict[str, Any], secrets_path: pathlib.Path) -> dict[str, Any]:
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
    )


def run_wifi_persistent(display: VisualDisplay, out_dir: pathlib.Path) -> dict[str, Any] | None:
    secrets_path = collect_wifi_credentials(display)
    if secrets_path is None:
        return None
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
    network = wifi_network_from_status(adapter_status, secrets_path)
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
    if network_step in {"wifi_persistent", "persistent"}:
        return network_defaults(
            network_step="wifi_persistent",
            label="Wi-Fi configurado neste totem",
            connected="unknown",
            connection_type="wifi",
            connectivity="not_checked",
            dedicated_profile_present_final="unknown",
            dedicated_profile_persistent=False,
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
            "visual_renderer": "mpv_drm_svg",
            "screens_generated": True,
        },
        "files": {
            "candidate_config": CANDIDATE_FILENAME,
            "summary": SUMMARY_FILENAME,
            "status": STATUS_FILENAME,
            "screens": "screens",
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
            "visual_renderer_mpv_called": True,
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
            "visual_renderer: mpv_drm_svg",
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
            f"environment_id_present: {str(status['environment']['environment_id_present']).lower()}",
            f"environment_id_valid: {str(status['environment']['environment_id_valid']).lower()}",
            f"rotation_degrees: {status['validation']['rotation_degrees']}",
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
            "visual_renderer_mpv_called: true",
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
    candidate["setup_display_source"] = "mock_candidate_only"
    candidate["setup_visual_renderer"] = "mpv_drm_svg"

    contract_validation = setup.validate_candidate_handoff(candidate)
    status = build_visual_status(generated_at, rotation, environment_id, network, contract_validation)
    atomic_write_private_json(out_dir / CANDIDATE_FILENAME, candidate, out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
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
            "visual_renderer_mpv_called": True,
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
            active_step=4,
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
        ),
    )
    key = read_key()
    if key == "enter":
        return True
    if key in {"b", "B", "back"}:
        return False
    raise VisualWizardAbort("setup visual cancelado pelo operador")


def show_complete(display: VisualDisplay, status: dict[str, Any]) -> None:
    display.show(
        "06-complete",
        build_screen_svg(
            active_step=5,
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
        ),
    )
    wait_enter_or_cancel()


def run_visual_wizard(out_dir: pathlib.Path, *, mpv_bin: str) -> dict[str, Any]:
    display = VisualDisplay(out_dir, mpv_bin=mpv_bin, enabled=True)
    try:
        with RawKeyboard():
            draw_welcome(display)
            wait_enter_or_cancel()
            while True:
                selected_network = choose_option(
                    display,
                    screen_id="02-connection",
                    active_step=1,
                    title="Conexao",
                    subtitle="Escolha como este totem deve seguir agora.",
                    options=list(NETWORK_OPTIONS),
                    panel_items=[
                        "Wi-Fi persistente usa perfil dedicado.",
                        "Credenciais ficam apenas em arquivo temporario.",
                        "Sem hotspot e sem portal nesta rodada.",
                    ],
                )
                if selected_network is None:
                    continue
                try:
                    if selected_network.key == "configured_wifi":
                        network = use_configured_wifi_network()
                    elif selected_network.key == "wifi_persistent":
                        maybe_network = run_wifi_persistent(display, out_dir)
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
                    )
                    if environment_id is None:
                        break
                    selected_rotation = choose_option(
                        display,
                        screen_id="04-display",
                        active_step=3,
                        title="Tela",
                        subtitle="Escolha a orientacao desejada. A rotacao real ainda nao sera aplicada.",
                        options=[
                            Option(str(item["key"]), str(item["label"]), str(item["description"]))
                            for item in DISPLAY_OPTIONS
                        ],
                        panel_items=[
                            "Apenas candidata em /tmp.",
                            "Sem EDID, framebuffer ou MPV flags.",
                            "Aplicacao real fica para etapa futura.",
                        ],
                        allow_back=True,
                    )
                    if selected_rotation is None:
                        continue
                    rotation = resolve_display_selection(selected_rotation.key)
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
        "01-welcome",
        build_screen_svg(
            active_step=0,
            title="Bem-vindo",
            subtitle="Assistente visual local, sem desktop e sem navegador.",
            footer="Enter inicia | Esc cancela",
            panel_items=["SVG local", "MPV/DRM", "Teclado local"],
        ),
    )
    display.show(
        "02-connection",
        build_screen_svg(
            active_step=1,
            title="Conexao",
            subtitle="Escolha usar Wi-Fi ja configurado, configurar Wi-Fi ou seguir em bancada.",
            footer="Setas movem | Enter confirma | Esc cancela",
            options=list(NETWORK_OPTIONS),
            selected_index=0,
            panel_items=["Perfil dedicado", "Sem portal", "Sem dados publicos"],
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
        ),
    )
    display.show(
        "04-display",
        build_screen_svg(
            active_step=3,
            title="Tela",
            subtitle="Selecao mock/candidata de orientacao.",
            footer="Setas movem | Enter confirma | B volta",
            options=[Option(str(item["key"]), str(item["label"]), str(item["description"])) for item in DISPLAY_OPTIONS],
            selected_index=0,
            panel_items=["Nao aplica rotacao real", "Nao muda MPV", "Nao mexe em EDID"],
        ),
    )
    display.show(
        "05-review",
        build_screen_svg(
            active_step=4,
            title="Revisao",
            subtitle="Resumo publico antes da candidata.",
            footer="Enter conclui | B volta | Esc cancela",
            panel_items=["Conexao agregada", "Ambiente informado", "Tela escolhida"],
        ),
    )
    display.show(
        "06-complete",
        build_screen_svg(
            active_step=5,
            title="Concluido",
            subtitle="Candidata temporaria pronta para a proxima etapa.",
            footer="Enter sai",
            panel_items=["C5.1 allow-mock", "Writer bloqueado", "Config real intocada"],
            accent="#22c55e",
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
            active_step=5,
            title="Concluido",
            subtitle="Candidata temporaria gerada por fluxo controlado.",
            footer="Fim do modo scripted",
            panel_items=["C5.1 allow-mock", "Sem writer", "Sem config real"],
            accent="#22c55e",
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
    for name in (CANDIDATE_FILENAME, STATUS_FILENAME, SUMMARY_FILENAME):
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
        preview_dir = require_tmp_dir(str(root / "preview"))
        prepare_private_dir(preview_dir)
        generate_preview_screens(preview_dir)
        assert_true(
            any((preview_dir / "screens").glob("*-01-welcome.svg")),
            "preview should generate welcome",
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
        assert_true(status["interface"]["visual_renderer"] == "mpv_drm_svg", "visual renderer should be recorded")
        assert_true(status["network"]["network_step"] == "existing_configured_wifi", "network step should use configured Wi-Fi")
        assert_true(status["network"]["dedicated_profile_persistent"] is True, "configured Wi-Fi should be persistent")
        assert_true(status["environment"]["environment_id_present"] is True, "environment should be present")
        assert_true(status["guardrails"]["real_config_read"] is False, "real config should not be read")
        assert_true(status["guardrails"]["real_config_written"] is False, "real config should not be written")
        assert_true(status["guardrails"]["writer_called"] is False, "writer should not be called")
        assert_true(status["guardrails"]["main_player_mpv_called"] is False, "main player MPV should be false")
        assert_true(status["guardrails"]["visual_renderer_mpv_called"] is True, "visual renderer should be true")
        assert_true(status["guardrails"]["hotspot_created"] is False, "hotspot should be false")
        assert_true(status["guardrails"]["portal_created"] is False, "portal should be false")
        assert_artifact_permissions(out_dir)

        candidate = json.loads((out_dir / CANDIDATE_FILENAME).read_text(encoding="utf-8"))
        assert_true(candidate["environment_id"] == "ENV-PRODUTO-VISUAL-01", "candidate should keep environment")
        assert_true(candidate["rotation_deg"] == 270, "candidate should keep rotation")
        assert_true(candidate["setup_source"] == SETUP_SOURCE, "candidate should record source")
        assert_true(candidate["setup_interface"] == INTERFACE_MODE, "candidate should record interface")
        assert_true(candidate["setup_network_step"] == "existing_configured_wifi", "candidate should record network")
        allow_mock = contract.validate_candidate_config(candidate, "allow-mock")
        real_dry_run = contract.validate_candidate_config(candidate, "real-dry-run")
        assert_true(allow_mock["valid"], "C9.9 candidate should pass allow-mock")
        assert_true(not real_dry_run["valid"], "C9.9 candidate should fail real-dry-run with placeholders")
        assert_sanitized_outputs(out_dir, "ENV-PRODUTO-VISUAL-01")
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
