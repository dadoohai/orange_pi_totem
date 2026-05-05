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
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
TMP_ROOT = pathlib.Path("/tmp")

MESSAGES = {
    "boot": ("Dadooh", "Inicializando"),
    "preparing": ("Dadooh", "Preparando"),
    "player": ("Dadooh", "Iniciando player"),
    "setup": ("Dadooh", "Abrindo configuracao"),
    "shutdown": ("Dadooh", "Encerrando"),
}


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

    def draw_rect(self, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
        x0 = max(0, min(self.width, x))
        y0 = max(0, min(self.height, y))
        x1 = max(0, min(self.width, x + width))
        y1 = max(0, min(self.height, y + height))
        if x1 <= x0 or y1 <= y0:
            return
        row = self.pixel_bytes(color) * (x1 - x0)
        for py in range(y0, y1):
            offset = py * self.stride + x0 * 4
            self.fb[offset : offset + len(row)] = row

    def draw_text(self, x: int, y: int, text: str, scale: int, color: tuple[int, int, int]) -> None:
        pixel = self.pixel_bytes(color)
        cursor_x = x
        top_y = y
        for char in text:
            glyph = self.font.glyph(char)
            for gy, row in enumerate(glyph):
                for gx in range(self.font.width):
                    if not (row & (0x80 >> gx)):
                        continue
                    px0 = cursor_x + gx * scale
                    py0 = top_y + gy * scale
                    for yy in range(scale):
                        py = py0 + yy
                        if py < 0 or py >= self.height:
                            continue
                        for xx in range(scale):
                            px = px0 + xx
                            if px < 0 or px >= self.width:
                                continue
                            offset = py * self.stride + px * 4
                            self.fb[offset : offset + 4] = pixel
            cursor_x += (self.font.width + 1) * scale

    def render(self, title: str, message: str) -> None:
        self.fill((15, 23, 42))
        self.draw_rect(0, 0, self.width, max(10, self.height // 55), (6, 182, 212))
        self.draw_rect(0, self.height - max(52, self.height // 12), self.width, max(52, self.height // 12), (11, 17, 32))
        title_scale = max(3, min(7, self.width // 210))
        message_scale = max(2, min(4, self.width // 330))
        title_width = len(title) * (self.font.width + 1) * title_scale
        message_width = len(message) * (self.font.width + 1) * message_scale
        self.draw_text(max(32, (self.width - title_width) // 2), max(80, self.height // 2 - 86), title, title_scale, (248, 250, 252))
        self.draw_text(max(32, (self.width - message_width) // 2), max(150, self.height // 2 + 18), message, message_scale, (203, 213, 225))
        self.fb.flush()


def require_tmp_path(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path)
    resolved = path.parent.resolve(strict=False)
    if TMP_ROOT not in [resolved, *resolved.parents]:
        raise SplashError("status_path_outside_tmp")
    return path


def atomic_write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, PRIVATE_DIR_MODE)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, PRIVATE_FILE_MODE)
    os.replace(tmp, path)
    os.chmod(path, PRIVATE_FILE_MODE)


def render_mode(mode: str, *, font_path: str, status_out: pathlib.Path | None) -> dict[str, Any]:
    title, message = MESSAGES[mode]
    payload: dict[str, Any] = {
        "schema_version": "dadooh-c10.5-visual-splash.v1",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": mode,
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
            renderer.render(title, message)
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
        payload = render_mode(mode, font_path="/missing-font-for-self-test.psf", status_out=None)
        assert payload["mode"] == mode
        assert payload["real_config_read"] is False
        assert payload["real_config_written"] is False
        assert payload["writer_called"] is False
        assert payload["wifi_changed"] is False
        assert payload["network_identifiers_published"] is False
    target = require_tmp_path("/tmp/dadooh-c10-5-splash-self-test/status.json")
    payload = render_mode("boot", font_path="/missing-font-for-self-test.psf", status_out=target)
    assert target.exists()
    assert stat.S_IMODE(target.stat().st_mode) == PRIVATE_FILE_MODE
    text = target.read_text(encoding="utf-8")
    for forbidden in ("api_key", "SSID", "password", "192.0.2.1", "aa:bb:cc:dd:ee:ff"):
        assert forbidden not in text
    target.unlink(missing_ok=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a minimal Dadooh framebuffer splash.")
    parser.add_argument("mode", nargs="?", default="boot", choices=sorted(MESSAGES), help="Splash mode to render.")
    parser.add_argument("--font", default=DEFAULT_FONT, help="PSF console font path.")
    parser.add_argument("--status-out", help="Optional sanitized status JSON path under /tmp.")
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
    render_mode(args.mode, font_path=args.font, status_out=status_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
