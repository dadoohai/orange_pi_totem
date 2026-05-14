#!/usr/bin/env python3
"""C17.5 Python wrapper for remotely updated totem-core scripts.

Installed at /opt/totem/bin/<script>.py. It dispatches to
/data/core/totem/current/bin/<script>.py when available, otherwise to the
factory fallback in /opt/totem/core-fallback/bin.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


MARKER = "TOTEM_CORE_EXEC_WRAPPER"
DATA_CURRENT = Path(os.environ.get("TOTEM_CORE_CURRENT", "/data/core/totem/current/bin"))
FALLBACK = Path(os.environ.get("TOTEM_CORE_FALLBACK", "/opt/totem/core-fallback/bin"))
PYTHON = os.environ.get("TOTEM_CORE_PYTHON", "/usr/bin/python3")


def _candidate(base: Path, name: str) -> Path:
    return base / name


def _usable(path: Path) -> bool:
    try:
        return path.is_file() and os.access(path, os.R_OK)
    except OSError:
        return False


def main() -> int:
    name = Path(sys.argv[0]).name
    search = []
    if os.environ.get("TOTEM_CORE_DISABLE_DATA", "") != "1":
        search.append(("data", _candidate(DATA_CURRENT, name)))
    search.append(("fallback", _candidate(FALLBACK, name)))

    self_path = Path(__file__).resolve()
    for source, script in search:
        if not _usable(script):
            continue
        try:
            if script.resolve() == self_path:
                continue
        except OSError:
            pass
        os.environ["TOTEM_CORE_SCRIPT_SOURCE"] = source
        os.execv(PYTHON, [PYTHON, str(script), *sys.argv[1:]])

    print(f"totem-core wrapper: no usable target for {name}", file=sys.stderr)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
