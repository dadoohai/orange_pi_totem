#!/usr/bin/env python3
"""Static guard for the kiosk.py ``self._ipc`` teardown invariant.

The C18 teardown/panfrost gate is measurement-based. In fresh-IPC mode the
startup connection is intentionally only a readiness probe, so normal runtime
keeps ``self._ipc is None`` and teardown uses the fresh-IPC quit path. This
guard verifies the transport boundary that makes that behavior explicit:

  * the ONLY writers of ``self._ipc`` are ``__init__`` (None), ``_open_ipc``
    (live pipe/sock), and ``_close_ipc_locked`` (None); and
  * ``_open_ipc`` is called ONLY from ``_start_locked``; and
  * fresh mode closes the startup probe and routes control commands through
    serialized, short-lived request/response connections.

If a future change retains an unread persistent socket in fresh mode, this
check fails closed. Hardware teardown proof remains required for the live
fresh-IPC quit path. It does NOT modify kiosk.py.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
KIOSK_PY = REPO_ROOT / "player-runtime" / "kiosky-player" / "kiosk.py"

ALLOWED_IPC_WRITERS = {"__init__", "_open_ipc", "_close_ipc_locked"}
ALLOWED_OPEN_IPC_CALLERS = {"_start_locked"}
REQUIRED_FRESH_TRANSPORT_TOKENS = {
    "startup_probe_closed": "transport=fresh-socket-probe",
    "fresh_command_route": "response = self._fresh_ipc_query(command, command_name=command_label, timeout=timeout)",
    "fresh_command_serialization": "return self._fresh_ipc_query_locked(command, command_name, timeout)",
}


def _enclosing_funcs(tree: ast.AST) -> dict[ast.AST, str]:
    """Map each node to the name of its nearest enclosing FunctionDef."""
    mapping: dict[ast.AST, str] = {}

    def walk(node: ast.AST, current: str | None) -> None:
        name = current
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
        for child in ast.iter_child_nodes(node):
            if name is not None:
                mapping[child] = name
            walk(child, name)

    walk(tree, None)
    return mapping


def _is_self_ipc(target: ast.AST) -> bool:
    return (
        isinstance(target, ast.Attribute)
        and target.attr == "_ipc"
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
    )


def _is_self_open_ipc(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_open_ipc"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
    )


def check(kiosk_py: Path) -> dict[str, Any]:
    errors: list[str] = []
    if not kiosk_py.is_file():
        return {"passed": False, "errors": [f"kiosk_py_not_found:{kiosk_py}"]}
    source = kiosk_py.read_text(encoding="utf-8")
    tree = ast.parse(source)
    enclosing = _enclosing_funcs(tree)

    ipc_writers: dict[str, list[int]] = {}
    open_ipc_callers: dict[str, list[int]] = {}

    for node in ast.walk(tree):
        # Assignments / annotated assignments to self._ipc.
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        for target in targets:
            if _is_self_ipc(target):
                func = enclosing.get(node, "<module>")
                ipc_writers.setdefault(func, []).append(getattr(node, "lineno", -1))
        # Calls to self._open_ipc().
        if _is_self_open_ipc(node):
            func = enclosing.get(node, "<module>")
            open_ipc_callers.setdefault(func, []).append(getattr(node, "lineno", -1))

    if not ipc_writers:
        errors.append("no_self_ipc_writer_found")
    for func, lines in sorted(ipc_writers.items()):
        if func not in ALLOWED_IPC_WRITERS:
            errors.append(f"unexpected_self_ipc_writer:{func}:{lines}")
    for required in ALLOWED_IPC_WRITERS:
        if required not in ipc_writers:
            errors.append(f"expected_self_ipc_writer_absent:{required}")

    if not open_ipc_callers:
        errors.append("no_open_ipc_caller_found")
    for func, lines in sorted(open_ipc_callers.items()):
        if func not in ALLOWED_OPEN_IPC_CALLERS:
            errors.append(f"unexpected_open_ipc_caller:{func}:{lines}")
    for label, token in REQUIRED_FRESH_TRANSPORT_TOKENS.items():
        if token not in source:
            errors.append(f"fresh_transport_invariant_missing:{label}")

    return {
        "passed": not errors,
        "errors": errors,
        "kiosk_py": str(kiosk_py),
        "self_ipc_writers": {k: sorted(v) for k, v in sorted(ipc_writers.items())},
        "open_ipc_callers": {k: sorted(v) for k, v in sorted(open_ipc_callers.items())},
        "fresh_transport_tokens": sorted(REQUIRED_FRESH_TRANSPORT_TOKENS),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Static guard for kiosk.py self._ipc teardown invariant.")
    parser.add_argument("--kiosk-py", type=Path, default=KIOSK_PY)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = check(args.kiosk_py)
    print(json.dumps(result, indent=2 if args.json else None, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
