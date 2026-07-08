#!/usr/bin/env python3
"""Send a small keyboard sequence through /dev/uinput for board QA.

This helper is intentionally narrow: it emits only named navigation keys used by
the C20 wizard QA flow. It does not read keyboard input and does not log typed
characters.
"""

from __future__ import annotations

import argparse
import fcntl
import struct
import time
from pathlib import Path


EV_SYN = 0x00
EV_KEY = 0x01
SYN_REPORT = 0

UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565

KEYS = {
    "b": 48,
    "esc": 1,
    "enter": 28,
    "f10": 68,
    "left": 105,
    "q": 16,
    "right": 106,
    "down": 108,
    "up": 103,
}

EVENT_STRUCT = "llHHI"


def parse_keys(raw: str) -> list[int]:
    names = [part.strip().lower() for part in raw.split(",") if part.strip()]
    if not names:
        raise ValueError("empty key sequence")
    unknown = [name for name in names if name not in KEYS]
    if unknown:
        raise ValueError(f"unknown key(s): {', '.join(unknown)}")
    return [KEYS[name] for name in names]


def emit_event(device, event_type: int, code: int, value: int) -> None:
    device.write(struct.pack(EVENT_STRUCT, 0, 0, event_type, code, value))
    device.flush()


def tap(device, key_code: int, *, delay_sec: float) -> None:
    emit_event(device, EV_KEY, key_code, 1)
    emit_event(device, EV_SYN, SYN_REPORT, 0)
    time.sleep(0.05)
    emit_event(device, EV_KEY, key_code, 0)
    emit_event(device, EV_SYN, SYN_REPORT, 0)
    time.sleep(delay_sec)


def build_uinput_user_device(name: str) -> bytes:
    encoded_name = name.encode("ascii", errors="ignore")[:79]
    padded_name = encoded_name + b"\0" * (80 - len(encoded_name))
    input_id = struct.pack("HHHHI", 0x03, 0x1234, 0xC20, 1, 0)
    abs_arrays = bytes(4 * 64 * 4)
    return padded_name + input_id + abs_arrays


def send_sequence(
    keys: list[int],
    *,
    device_path: Path,
    delay_sec: float,
    initial_delay_sec: float,
) -> None:
    with device_path.open("wb", buffering=0) as device:
        fcntl.ioctl(device, UI_SET_EVBIT, EV_KEY)
        for key in sorted(set(keys)):
            fcntl.ioctl(device, UI_SET_KEYBIT, key)
        device.write(build_uinput_user_device("c20-e2e-qa-keyboard"))
        device.flush()
        fcntl.ioctl(device, UI_DEV_CREATE)
        try:
            time.sleep(initial_delay_sec)
            for key in keys:
                tap(device, key, delay_sec=delay_sec)
        finally:
            try:
                fcntl.ioctl(device, UI_DEV_DESTROY)
            except OSError:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit C20 QA key sequence through /dev/uinput.")
    parser.add_argument("--keys", required=True, help="Comma-separated keys: up,down,left,right,enter,esc,f10,q,b.")
    parser.add_argument("--device", default="/dev/uinput", help="uinput device path.")
    parser.add_argument("--delay-sec", type=float, default=0.35, help="Delay after each key tap.")
    parser.add_argument("--initial-delay-sec", type=float, default=0.5, help="Delay after virtual device creation.")
    parser.add_argument("--dry-run", action="store_true", help="Only parse and print the key count.")
    args = parser.parse_args()

    keys = parse_keys(args.keys)
    if args.dry_run:
        print(f"keys_ok count={len(keys)}")
        return 0
    send_sequence(
        keys,
        device_path=Path(args.device),
        delay_sec=args.delay_sec,
        initial_delay_sec=args.initial_delay_sec,
    )
    print(f"uinput_sequence_sent count={len(keys)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
