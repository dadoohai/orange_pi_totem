#!/usr/bin/env python3
"""Minimal Dadooh framebuffer splash for boot/shutdown transitions.

This script is intentionally small and standalone so the remote runner can
install it as a reversible boot guardrail. It writes only a public product
message to /dev/fb0, never reads config, never touches Wi-Fi and never starts
the player.
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import mmap
import os
import pathlib
import stat
import struct
import sys
import time
from typing import Any


sys.dont_write_bytecode = True

DEFAULT_FONT = "/usr/share/consolefonts/Lat15-Fixed18.psf.gz"
PUBLIC_ORIENTATION_PATH = pathlib.Path("/data/state/totem-display/orientation.json")
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
TMP_ROOT = pathlib.Path("/tmp")

MESSAGES = {
    "boot": ("Dadooh", "Inicializando"),
    "firstboot": ("Dadooh", ("Preparando sistema", "Conclua o primeiro acesso tecnico")),
    "preparing": ("Dadooh", "Preparando sistema"),
    "reboot": ("Dadooh", "Reiniciando totem"),
    "player": ("Dadooh", "Iniciando player"),
    "setup": ("Dadooh", "Abrindo configuracao"),
    "saving": ("Dadooh", "Salvando configuracao"),
    "config_pending": ("Dadooh", ("Configuracao pendente", "Pressione F10")),
    "shutdown": (
        "Desligamento seguro",
        (
            "Aguarde",
            "Quando a tela apagar,",
            "remova e reconecte a energia",
            "para ligar novamente.",
        ),
    ),
}

PREVIEW_MODES = ("boot", "player", "config_pending", "setup", "saving")

ORIENTATIONS = {
    "landscape": 0,
    "portrait_right": 90,
    "portrait_left": 270,
    "inverted": 180,
    "landscape_inverted": 180,
}


def normalize_rotation_deg(value: int | str) -> int:
    try:
        rotation = int(value) % 360
    except (TypeError, ValueError):
        rotation = 0
    if rotation not in {0, 90, 180, 270}:
        return 0
    return rotation


def read_public_orientation_rotation(path: pathlib.Path = PUBLIC_ORIENTATION_PATH) -> tuple[int, str]:
    try:
        if path.is_symlink() or not path.exists():
            return 0, "default"
        data = json.loads(path.read_text(encoding="utf-8"))
        rotation = normalize_rotation_deg(data.get("rotation_deg", 0))
        return rotation, "public_orientation"
    except Exception:
        return 0, "default"


def source_size_for_rotation(rotation_deg: int) -> tuple[int, int, str]:
    rotation = normalize_rotation_deg(rotation_deg)
    if rotation in {90, 270}:
        return 720, 1280, "portrait"
    return 1280, 720, "landscape"


class SplashError(RuntimeError):
    """Public-safe splash error."""


class PSFFont:
    def __init__(self, path: str) -> None:
        font_path = pathlib.Path(path)
        if not font_path.exists():
            raise SplashError("font_missing")
        raw = gzip.open(font_path, "rb").read() if font_path.suffix == ".gz" else font_path.read_bytes()
        if len(raw) >= 4 and raw[:2] == b"\x36\x04":
            mode = raw[2]
            char_size = raw[3]
            glyph_count = 512 if mode & 0x01 else 256
            self.width = 8
            self.height = int(char_size)
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
        raise SplashError("font_invalid")

    def glyph(self, char: str) -> bytes:
        code = ord(char)
        if code >= self.glyph_count:
            code = ord("?")
        start = code * self.height
        return self.glyphs[start : start + self.height]


class FramebufferSplash:
    def __init__(self, font_path: str) -> None:
        self.fb_path = pathlib.Path("/dev/fb0")
        if not self.fb_path.exists():
            raise SplashError("framebuffer_missing")
        self.width, self.height = self.read_virtual_size()
        self.bpp = self.read_int("/sys/class/graphics/fb0/bits_per_pixel")
        self.stride = self.read_int("/sys/class/graphics/fb0/stride")
        if self.bpp != 32 or self.width <= 0 or self.height <= 0 or self.stride <= 0:
            raise SplashError("framebuffer_incompatible")
        self.font = PSFFont(font_path)
        self.fb_file = self.fb_path.open("r+b", buffering=0)
        self.fb = mmap.mmap(self.fb_file.fileno(), self.stride * self.height, access=mmap.ACCESS_WRITE)

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

    def close(self) -> None:
        try:
            self.fb.flush()
            self.fb.close()
        finally:
            self.fb_file.close()

    def fill(self, color: tuple[int, int, int]) -> None:
        row = self.pixel_bytes(color) * self.width
        for py in range(self.height):
            offset = py * self.stride
            self.fb[offset : offset + len(row)] = row

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

    def render_context(self, rotation_deg: int) -> dict[str, float | int]:
        source_w, source_h, _ = source_size_for_rotation(rotation_deg)
        rotation = normalize_rotation_deg(rotation_deg)
        if rotation in {90, 270}:
            rotated_w, rotated_h = source_h, source_w
        else:
            rotated_w, rotated_h = source_w, source_h
        scale = min(self.width / rotated_w, self.height / rotated_h)
        drawn_w = rotated_w * scale
        drawn_h = rotated_h * scale
        return {
            "source_w": float(source_w),
            "source_h": float(source_h),
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
        scale: int,
        color: tuple[int, int, int],
        ctx: dict[str, float | int],
    ) -> None:
        cursor_x = x
        top_y = y
        for char in text:
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

    @staticmethod
    def normalized_lines(message: str | tuple[str, ...]) -> tuple[str, ...]:
        if isinstance(message, tuple):
            return tuple(str(line) for line in message if str(line).strip())
        return (str(message),)

    def render(self, title: str, message: str | tuple[str, ...], *, rotation_deg: int = 0) -> None:
        ctx = self.render_context(rotation_deg)
        source_w = int(ctx["source_w"])
        source_h = int(ctx["source_h"])
        self.fill((15, 23, 42))
        top_bar = max(10, source_h // 70)
        footer_h = max(64, source_h // 13)
        self.draw_logical_rect(0, 0, source_w, top_bar, (6, 182, 212), ctx)
        self.draw_logical_rect(0, source_h - footer_h, source_w, footer_h, (11, 17, 32), ctx)
        title_scale = max(3, min(7, source_w // 210))
        message_scale = max(2, min(4, source_w // 330))
        title_width = len(title) * (self.font.width + 1) * title_scale
        message_lines = self.normalized_lines(message)
        line_height = (self.font.height + 8) * message_scale
        message_block_h = max(line_height, len(message_lines) * line_height)
        title_y = max(80, source_h // 2 - 110)
        message_y = max(150, int(source_h // 2 + 8 - message_block_h / 2))
        self.draw_text(max(32, (source_w - title_width) // 2), title_y, title, title_scale, (248, 250, 252), ctx)
        for index, line in enumerate(message_lines):
            line_width = len(line) * (self.font.width + 1) * message_scale
            self.draw_text(
                max(32, (source_w - line_width) // 2),
                message_y + index * line_height,
                line,
                message_scale,
                (203, 213, 225),
                ctx,
            )
        self.fb.flush()


def require_tmp_path(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path)
    resolved = path.parent.resolve(strict=False)
    if TMP_ROOT not in [resolved, *resolved.parents]:
        raise SplashError("status_path_outside_tmp")
    return path


def require_tmp_dir(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path)
    resolved = path.resolve(strict=False)
    if TMP_ROOT not in [resolved, *resolved.parents]:
        raise SplashError("preview_dir_outside_tmp")
    return path


def atomic_write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.resolve(strict=False) != TMP_ROOT:
        os.chmod(path.parent, PRIVATE_DIR_MODE)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, PRIVATE_FILE_MODE)
    os.replace(tmp, path)
    os.chmod(path, PRIVATE_FILE_MODE)


def atomic_write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.resolve(strict=False) != TMP_ROOT:
        os.chmod(path.parent, PRIVATE_DIR_MODE)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.chmod(tmp, PRIVATE_FILE_MODE)
    os.replace(tmp, path)
    os.chmod(path, PRIVATE_FILE_MODE)


def escape_text(value: Any) -> str:
    return html.escape(str(value), quote=True)


def build_preview_svg(mode: str, *, rotation_deg: int = 0) -> str:
    title, message = MESSAGES[mode]
    rotation = normalize_rotation_deg(rotation_deg)
    source_w, source_h, layout_mode = source_size_for_rotation(rotation)
    message_lines = FramebufferSplash.normalized_lines(message)
    line_y = source_h // 2 + 24
    line_parts = []
    for index, line in enumerate(message_lines[:3]):
        line_parts.append(
            f'<text x="{source_w // 2}" y="{line_y + index * 44}" '
            'font-family="Arial, DejaVu Sans, sans-serif" font-size="30" '
            f'text-anchor="middle" fill="#cbd5e1">{escape_text(line)}</text>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{source_w}" height="{source_h}" viewBox="0 0 {source_w} {source_h}" data-display-rotation-deg="{rotation}" data-layout-mode="{layout_mode}" role="img" aria-label="Dadooh splash preview {escape_text(mode)}">
  <rect width="{source_w}" height="{source_h}" fill="#0f172a"/>
  <rect x="0" y="0" width="{source_w}" height="12" fill="#06b6d4"/>
  <rect x="0" y="{source_h - 72}" width="{source_w}" height="72" fill="#0b1120"/>
  <text x="{source_w // 2}" y="{source_h // 2 - 58}" font-family="Arial, DejaVu Sans, sans-serif" font-size="52" font-weight="700" text-anchor="middle" fill="#f8fafc">{escape_text(title)}</text>
  {' '.join(line_parts)}
</svg>
"""


def write_preview_screens(out_dir: pathlib.Path, *, rotation_deg: int = 0) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, PRIVATE_DIR_MODE)
    screens_dir = out_dir / "screens"
    screens_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(screens_dir, PRIVATE_DIR_MODE)
    for index, mode in enumerate(PREVIEW_MODES, start=1):
        atomic_write_text(screens_dir / f"{index:02d}-{mode}.svg", build_preview_svg(mode, rotation_deg=rotation_deg))
    payload = {
        "schema_version": "dadooh-c10.5-visual-splash-preview.v1",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "preview_modes": list(PREVIEW_MODES),
        "preview_screens_generated": len(PREVIEW_MODES),
        "rotation_deg": normalize_rotation_deg(rotation_deg),
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "wifi_changed": False,
        "network_identifiers_published": False,
        "raw_logs_written": False,
    }
    atomic_write_json(out_dir / "splash-preview-status.json", payload)
    return payload


def render_mode(
    mode: str,
    *,
    font_path: str,
    status_out: pathlib.Path | None,
    rotation_deg: int = 0,
    orientation_source: str = "argument",
) -> dict[str, Any]:
    title, message = MESSAGES[mode]
    rotation = normalize_rotation_deg(rotation_deg)
    _, _, layout_mode = source_size_for_rotation(rotation)
    payload: dict[str, Any] = {
        "schema_version": "dadooh-c10.5-visual-splash.v2",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": mode,
        "rotation_deg": rotation,
        "layout_mode": layout_mode,
        "orientation_source": orientation_source,
        "orientation_contract_supported": True,
        "public_orientation_path_supported": True,
        "rendered": False,
        "fallback_safe": False,
        "real_config_read": False,
        "real_config_written": False,
        "writer_called": False,
        "wifi_changed": False,
        "network_identifiers_published": False,
        "raw_logs_written": False,
    }
    try:
        renderer = FramebufferSplash(font_path)
        try:
            renderer.render(title, message, rotation_deg=rotation)
        finally:
            renderer.close()
        payload["rendered"] = True
    except Exception:
        payload["fallback_safe"] = True
    if status_out is not None:
        atomic_write_json(status_out, payload)
    return payload


def run_self_test() -> None:
    for mode in MESSAGES:
        payload = render_mode(
            mode,
            font_path="/missing-font-for-self-test.psf",
            status_out=None,
            rotation_deg=90,
            orientation_source="argument",
        )
        assert payload["mode"] == mode
        assert payload["rotation_deg"] == 90
        assert payload["layout_mode"] == "portrait"
        assert payload["orientation_source"] == "argument"
        assert payload["orientation_contract_supported"] is True
        assert payload["public_orientation_path_supported"] is True
        assert payload["real_config_read"] is False
        assert payload["real_config_written"] is False
        assert payload["writer_called"] is False
        assert payload["wifi_changed"] is False
        assert payload["network_identifiers_published"] is False
    assert "reboot" in MESSAGES
    assert "shutdown" in MESSAGES
    for mode in ("boot", "player", "setup", "saving", "config_pending"):
        assert mode in MESSAGES
    assert "Pressione F10" in " ".join(FramebufferSplash.normalized_lines(MESSAGES["config_pending"][1]))
    assert "remova e reconecte" in " ".join(FramebufferSplash.normalized_lines(MESSAGES["shutdown"][1]))
    preview_dir = require_tmp_dir("/tmp/dadooh-c10-5-splash-self-test/preview")
    preview_payload = write_preview_screens(preview_dir, rotation_deg=90)
    assert preview_payload["preview_screens_generated"] == len(PREVIEW_MODES)
    assert (preview_dir / "screens" / "01-boot.svg").exists()
    assert (preview_dir / "screens" / "03-config_pending.svg").exists()
    preview_text = (preview_dir / "splash-preview-status.json").read_text(encoding="utf-8")
    for forbidden in ("api_key", "SSID", "password", "192.0.2.1", "aa:bb:cc:dd:ee:ff"):
        assert forbidden not in preview_text
    target = require_tmp_path("/tmp/dadooh-c10-5-splash-self-test/status.json")
    payload = render_mode(
        "boot",
        font_path="/missing-font-for-self-test.psf",
        status_out=target,
        rotation_deg=270,
        orientation_source="argument",
    )
    assert target.exists()
    assert stat.S_IMODE(target.stat().st_mode) == PRIVATE_FILE_MODE
    text = target.read_text(encoding="utf-8")
    for forbidden in ("api_key", "SSID", "password", "192.0.2.1", "aa:bb:cc:dd:ee:ff"):
        assert forbidden not in text
    target.unlink(missing_ok=True)
    root_target = require_tmp_path("/tmp/dadooh-splash-root-status-self-test.json")
    render_mode(
        "player",
        font_path="/missing-font-for-self-test.psf",
        status_out=root_target,
        rotation_deg=0,
        orientation_source="argument",
    )
    assert stat.S_IMODE(TMP_ROOT.stat().st_mode) in {0o777, 0o1777}
    root_target.unlink(missing_ok=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a minimal Dadooh framebuffer splash.")
    parser.add_argument("mode", nargs="?", default="boot", choices=sorted(MESSAGES), help="Splash mode to render.")
    parser.add_argument("--font", default=DEFAULT_FONT, help="PSF console font path.")
    parser.add_argument("--status-out", help="Optional sanitized status JSON path under /tmp.")
    parser.add_argument("--rotation-deg", type=int, help="Display orientation rotation in degrees: 0, 90, 180 or 270.")
    parser.add_argument("--orientation", choices=sorted(ORIENTATIONS), help="Named orientation alias.")
    parser.add_argument("--out-dir", default="/tmp/dadooh-splash-preview", help="Preview output directory under /tmp.")
    parser.add_argument("--preview-screens", action="store_true", help="Generate offline SVG preview screens and exit.")
    parser.add_argument("--self-test", action="store_true", help="Run self-tests and exit.")
    return parser.parse_args(argv)


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
    status_out = require_tmp_path(args.status_out) if args.status_out else None
    if args.orientation:
        rotation = ORIENTATIONS[args.orientation]
        source = "argument"
    elif args.rotation_deg is not None:
        rotation = args.rotation_deg
        source = "argument"
    else:
        rotation, source = read_public_orientation_rotation()
    if args.preview_screens:
        out_dir = require_tmp_dir(args.out_dir)
        payload = write_preview_screens(out_dir, rotation_deg=rotation)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    render_mode(args.mode, font_path=args.font, status_out=status_out, rotation_deg=rotation, orientation_source=source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
