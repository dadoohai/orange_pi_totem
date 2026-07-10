#!/usr/bin/env python3
"""Derive the current C18 production HW-decode candidate image.

This is a thin wrapper around the validated C18 HW-decode image derivation
engine. It selects production identity and the production totem-core auto-pull
profile explicitly; the lab builder remains lab/manual by default.
"""

from __future__ import annotations

import sys

import derive_c18_image_lab_1_hwdecode as base


DEFAULTS = {
    "--image-profile": "production",
    "--totem-core-profile": "production",
}


def with_defaults(argv: list[str]) -> list[str]:
    result = list(argv)
    for flag, value in reversed(list(DEFAULTS.items())):
        if not any(item == flag or item.startswith(flag + "=") for item in result):
            result[0:0] = [flag, value]
    return result


def main() -> int:
    requested_lab_profile = any(
        item == "--image-profile=lab"
        or (item == "--image-profile" and index + 2 < len(sys.argv) and sys.argv[index + 2] == "lab")
        for index, item in enumerate(sys.argv[1:])
    )
    if requested_lab_profile:
        raise SystemExit("BLOCKED: production builder cannot select lab image profile")
    sys.argv = [sys.argv[0], *with_defaults(sys.argv[1:])]
    return base.main()


if __name__ == "__main__":
    sys.exit(main())
