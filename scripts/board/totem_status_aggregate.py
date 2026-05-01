#!/usr/bin/env python3
"""Aggregate sanitized totem status and render a local SVG.

This A1.1 component is deliberately offline and non-invasive. It reads local
JSON status files when present, writes only under /tmp by default, and never
starts MPV, touches systemd, accesses /dev/dri or reaches the network.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

from totem_status_render_preview import build_svg, sanitize_public_text, utc_timestamp


SCHEMA_VERSION = "totem-status.v0"
DEFAULT_PRIMARY_LAUNCHER_STATUS = pathlib.Path("/data/state/kiosky-player/launcher-status.json")
DEFAULT_FALLBACK_LAUNCHER_STATUS = pathlib.Path("/tmp/kiosky-launcher-status.json")
DEFAULT_PLAYER_STATUS = pathlib.Path("/tmp/kiosky-status.json")
DEFAULT_OUT_DIR = pathlib.Path("/tmp/dadooh-status")

PUBLIC_STATES = {
    "booting",
    "display_missing",
    "config_missing",
    "starting_player",
    "player_running",
    "player_error",
    "maintenance_placeholder",
}

STATE_MESSAGES = {
    "booting": {
        "message": "Inicializando totem",
        "hint": "Aguarde alguns instantes.",
        "error_code": None,
        "config_state": "unknown",
        "player_state": "not_started",
    },
    "display_missing": {
        "message": "Tela nao detectada",
        "hint": "Verifique o cabo HDMI e a energia da tela.",
        "error_code": "DISPLAY_MISSING",
        "config_state": "unknown",
        "player_state": "not_started",
    },
    "config_missing": {
        "message": "Configuracao pendente",
        "hint": "Acione a manutencao autorizada para concluir a ativacao.",
        "error_code": "CONFIG_MISSING",
        "config_state": "missing",
        "player_state": "not_started",
    },
    "starting_player": {
        "message": "Iniciando exibicao",
        "hint": "Aguarde alguns instantes.",
        "error_code": None,
        "config_state": "valid",
        "player_state": "starting",
    },
    "player_running": {
        "message": "Exibicao em andamento",
        "hint": "Nenhuma acao necessaria.",
        "error_code": None,
        "config_state": "valid",
        "player_state": "running",
    },
    "player_error": {
        "message": "Exibicao temporariamente indisponivel",
        "hint": "O sistema tentara reiniciar automaticamente.",
        "error_code": "PLAYER_EXITED",
        "config_state": "valid",
        "player_state": "error",
    },
    "maintenance_placeholder": {
        "message": "Manutencao local",
        "hint": "Modo reservado para fase futura.",
        "error_code": None,
        "config_state": "unknown",
        "player_state": "stopped",
    },
}


def load_json_if_present(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None

    if isinstance(value, dict):
        return value
    return None


def bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return None


def string_value(data: dict[str, Any] | None, key: str) -> str:
    if not data:
        return ""
    value = data.get(key)
    if isinstance(value, str):
        return value.strip().lower()
    return ""


def player_reports_running(player_status: dict[str, Any] | None) -> bool:
    if not player_status:
        return False

    playback_state = string_value(player_status, "playback_state")
    player_state = string_value(player_status, "player_state")
    mpv_running = bool_or_none(player_status.get("mpv_running"))

    if playback_state in {"playing", "buffering"}:
        return True
    if player_state in {"running", "playing"}:
        return True
    return mpv_running is True and playback_state not in {"error", "failed", "stopped"}


def player_reports_error(player_status: dict[str, Any] | None) -> bool:
    if not player_status:
        return False

    playback_state = string_value(player_status, "playback_state")
    player_state = string_value(player_status, "player_state")
    error_code = string_value(player_status, "error_code")

    if playback_state in {"error", "failed", "fatal"}:
        return True
    if player_state in {"error", "failed", "fatal"}:
        return True
    return error_code.startswith("player_") or error_code in {"unknown_error", "service_failed"}


def infer_config_state(
    launcher_status: dict[str, Any] | None,
    player_status: dict[str, Any] | None,
    state: str,
) -> str:
    if state == "config_missing":
        return "missing"

    for data in (launcher_status, player_status):
        if data is None:
            continue
        raw_state = string_value(data, "config_state")
        if raw_state in {"missing", "invalid", "valid", "unknown"}:
            return raw_state
        if bool_or_none(data.get("config_missing")) is True:
            return "missing"
        if bool_or_none(data.get("config_valid")) is True:
            return "valid"

    return STATE_MESSAGES[state]["config_state"]


def infer_service_state(launcher_status: dict[str, Any] | None, state: str) -> str:
    if not launcher_status:
        return "unknown"

    raw_service_state = string_value(launcher_status, "service_state")
    if raw_service_state in {"unknown", "inactive", "activating", "active", "failed"}:
        return raw_service_state

    launcher_state = string_value(launcher_status, "state")
    if launcher_state in {"starting", "running", "display_missing", "app_exited", "config_missing"}:
        return "active"
    if launcher_state == "stopped":
        return "inactive"
    if state == "player_error":
        return "active"
    return "unknown"


def infer_display_connected(launcher_status: dict[str, Any] | None, state: str) -> bool | None:
    display_connected = bool_or_none(launcher_status.get("display_connected") if launcher_status else None)
    if display_connected is not None:
        return display_connected
    if state == "display_missing":
        return False
    return None


def infer_state(
    launcher_status: dict[str, Any] | None,
    player_status: dict[str, Any] | None,
    state_override: str | None,
) -> str:
    if state_override:
        return state_override

    launcher_state = string_value(launcher_status, "state")
    launcher_display = bool_or_none(launcher_status.get("display_connected") if launcher_status else None)
    launcher_exit_code = launcher_status.get("last_app_exit_code") if launcher_status else None

    if launcher_state == "starting":
        if launcher_display is True:
            return "starting_player"
        return "booting"
    if launcher_state == "stopped":
        return "maintenance_placeholder"

    if launcher_state == "display_missing" or launcher_display is False:
        return "display_missing"

    if launcher_state == "config_missing":
        return "config_missing"
    if string_value(launcher_status, "config_state") == "missing":
        return "config_missing"
    if string_value(player_status, "config_state") == "missing":
        return "config_missing"
    if bool_or_none(launcher_status.get("config_missing") if launcher_status else None) is True:
        return "config_missing"

    if launcher_state == "app_exited" or isinstance(launcher_exit_code, int):
        return "player_error"
    if player_reports_error(player_status):
        return "player_error"

    if player_reports_running(player_status):
        return "player_running"

    if launcher_state == "running":
        return "starting_player"

    return "booting"


def build_status(
    *,
    launcher_status: dict[str, Any] | None,
    player_status: dict[str, Any] | None,
    state_override: str | None,
) -> dict[str, Any]:
    state = infer_state(launcher_status, player_status, state_override)
    public = STATE_MESSAGES[state]
    config_state = infer_config_state(launcher_status, player_status, state)

    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_timestamp(),
        "state": state,
        "display_connected": infer_display_connected(launcher_status, state),
        "network_state": "unknown",
        "config_state": config_state,
        "player_state": public["player_state"],
        "service_state": infer_service_state(launcher_status, state),
        "error_code": public["error_code"],
        "public_message": sanitize_public_text(public["message"]),
        "action_hint": sanitize_public_text(public["hint"]),
        "device_label": "Totem Dadooh",
        "version": {
            "image": "unknown",
            "launcher": "foundation-v0.1",
            "player": "unknown",
            "contract": SCHEMA_VERSION,
        },
    }


def resolve_launcher_status(path: pathlib.Path | None) -> dict[str, Any] | None:
    if path is not None:
        return load_json_if_present(path)

    primary = load_json_if_present(DEFAULT_PRIMARY_LAUNCHER_STATUS)
    fallback = load_json_if_present(DEFAULT_FALLBACK_LAUNCHER_STATUS)
    return primary if primary is not None else fallback


def require_tmp_dir(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    resolved = path.resolve()
    tmp_root = pathlib.Path("/tmp").resolve()
    try:
        resolved.relative_to(tmp_root)
    except ValueError as exc:
        raise ValueError("out-dir must be under /tmp") from exc
    if resolved == tmp_root:
        raise ValueError("out-dir must be a subdirectory under /tmp")
    return resolved


def write_text_atomic(path: pathlib.Path, content: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)


def render_status_svg(status: dict[str, Any]) -> str:
    return build_svg(
        state=status["state"],
        message=status["public_message"],
        action_hint=status["action_hint"],
        device_label=status.get("device_label") or "Totem Dadooh",
        width=1280,
        height=720,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate sanitized Dadooh totem status.")
    parser.add_argument("--launcher-status", help="Launcher status JSON path. Defaults to /data then /tmp.")
    parser.add_argument("--player-status", default=str(DEFAULT_PLAYER_STATUS), help="Player status JSON path.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory under /tmp.")
    parser.add_argument("--state-override", choices=sorted(PUBLIC_STATES), help="Force a public state for tests.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    try:
        out_dir = require_tmp_dir(args.out_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    launcher_status_path = pathlib.Path(args.launcher_status).expanduser() if args.launcher_status else None
    player_status_path = pathlib.Path(args.player_status).expanduser()

    launcher_status = resolve_launcher_status(launcher_status_path)
    player_status = load_json_if_present(player_status_path)
    status = build_status(
        launcher_status=launcher_status,
        player_status=player_status,
        state_override=args.state_override,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir.chmod(0o700)

    status_json = json.dumps(status, ensure_ascii=True, indent=2) + "\n"
    write_text_atomic(out_dir / "status.json", status_json)
    write_text_atomic(out_dir / "status.svg", render_status_svg(status))

    print(out_dir / "status.json")
    print(out_dir / "status.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
