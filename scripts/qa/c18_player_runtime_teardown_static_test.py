#!/usr/bin/env python3
"""Static guard for the kiosk.py ``self._ipc`` teardown invariant.

The C18 teardown/panfrost gate is measurement-based and treats the fresh-IPC
(C1) quit path as a SECONDARY ``self._ipc is None`` corner. That decision relies
on a code invariant (verified by reading + adversarial refutation):

  * the ONLY writers of ``self._ipc`` are ``__init__`` (None), ``_open_ipc``
    (live pipe/sock), and ``_close_ipc_locked`` (None); and
  * ``_open_ipc`` is called ONLY from ``_start_locked`` (there is no IPC
    reconnect path that re-opens IPC on a still-running mpv).

Together these make the fresh-IPC quit SUCCESS path (``_ipc is None`` with a
live, connectable socket) unreachable in production, so ``_start_locked``'s
``start_ipc_unavailable`` branch is dead/defensive today.

If a future change breaks either clause, the fresh-IPC quit SUCCESS path could
become a live but UNTESTED teardown path -- this check fails closed and flags
that GR4 then needs real hardware proof. It does NOT modify kiosk.py.
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

    return {
        "passed": not errors,
        "errors": errors,
        "kiosk_py": str(kiosk_py),
        "self_ipc_writers": {k: sorted(v) for k, v in sorted(ipc_writers.items())},
        "open_ipc_callers": {k: sorted(v) for k, v in sorted(open_ipc_callers.items())},
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
