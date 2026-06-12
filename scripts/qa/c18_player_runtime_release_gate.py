#!/usr/bin/env python3
"""Validate a future C18 player-runtime release payload without enabling OTA apply."""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import os
import py_compile
import re
import shutil
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_KIOSK = REPO_ROOT / "player-runtime" / "kiosky-player" / "kiosk.py"
SCHEMA = "dadooh.c18.player_runtime.release_gate.v1"
UPDATE_SCHEMA = "dadooh.totem.update.v1"
COMPONENT = "player-runtime"
DEVICE = "orangepizero3"
DEVICE_TRACK = "c18-hwdecode"
BASE_IMAGE_LINE = "c17.4.2"
EXPECTED_WRAPPER = "/opt/totem/bin/totem-mpv-hwdecode"
EXPECTED_HWDEC = "v4l2request-copy"
EXPECTED_DEEP_HEALTH_SCHEMA = "dadooh.c18.playback.deep_health.v1"
SUPPORTED_UPDATER_FEATURES = {
    "c18-freeze-kiosky-player-v1",
    "c18-rollback-reapply-v1",
    "c18-safe-payload-v1",
    "c18-track-v1",
    "c18-player-runtime-verify-then-promote-v1",
}
REQUIRED_UPDATER_FEATURES = {
    "c18-player-runtime-verify-then-promote-v1",
}
SAFE_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MARKER_NAME = ".release_verified.json"
ALLOWED_PAYLOAD_DIRS = {""}
ALLOWED_PAYLOAD_FILES = {"kiosk.py"}
FORBIDDEN_RUNTIME_BASENAMES = {
    "totem_updatectl.py",
    "totem-kiosky-launcher.sh",
    "kiosky_service_launcher.sh",
}
FORBIDDEN_MPV_OPTION_PREFIXES = (
    "--script",
    "--scripts",
    "--scripts-append",
    "--load-scripts",
    "--ytdl",
    "--script-opts",
    "--config-dir",
    "--config=",
    "--include",
    "--use-filedir-conf",
    "--input-file",
    "--input-terminal",
    "--input-test",
    "--input-command",
    "--osc",
)


class GateError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def tree_hash(root: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == MARKER_NAME:
            continue
        if path.is_dir():
            continue
        if not path.is_file() or path.is_symlink():
            raise GateError(f"unsupported member in extracted tree: {rel}")
        hasher.update(rel.encode("utf-8") + b"\0")
        hasher.update(sha256_file(path).encode("ascii") + b"\0")
    return hasher.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise GateError(f"{path.name} must be a JSON object")
    return data


def parse_utc_timestamp(value: Any) -> None:
    if not isinstance(value, str) or not value:
        raise GateError("created_at_utc must be a non-empty string")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError as exc:
        raise GateError("created_at_utc must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise GateError("created_at_utc must include timezone")


def validate_manifest(manifest: dict[str, Any], payload: Path) -> dict[str, Any]:
    required = {
        "schema",
        "component",
        "version",
        "channel",
        "created_at_utc",
        "payload",
        "payload_sha256",
        "requires",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise GateError(f"manifest missing fields: {missing}")
    if manifest["schema"] != UPDATE_SCHEMA:
        raise GateError(f"unsupported manifest schema: {manifest['schema']!r}")
    if manifest["component"] != COMPONENT:
        raise GateError(f"manifest component must be {COMPONENT!r}")
    version = manifest["version"]
    if not isinstance(version, str) or not SAFE_VERSION_RE.fullmatch(version):
        raise GateError("unsafe version string")
    expected_payload = f"dadooh-{COMPONENT}-{version}.tar.gz"
    if manifest["payload"] != expected_payload:
        raise GateError(f"payload name must be {expected_payload!r}")
    if manifest["payload_sha256"].lower() != sha256_file(payload):
        raise GateError("payload_sha256 mismatch")
    if manifest.get("channel") == "stable":
        raise GateError("player-runtime stable releases are blocked until lab thaw and homologation gates exist")
    if manifest.get("source_dirty") is not False:
        raise GateError("source_dirty must be false for player-runtime lab evidence")
    parse_utc_timestamp(manifest["created_at_utc"])

    requires = manifest["requires"]
    if not isinstance(requires, dict):
        raise GateError("requires must be a JSON object")
    expected_requires = {
        "device": DEVICE,
        "base_image_min": BASE_IMAGE_LINE,
        "device_track": DEVICE_TRACK,
        "media_stack_id": "c18-hwdecode-v4l2request-copy",
        "mpv_wrapper": EXPECTED_WRAPPER,
        "hwdec": EXPECTED_HWDEC,
        "vo": "gpu",
        "gpu_context": "drm",
        "deep_health_schema": EXPECTED_DEEP_HEALTH_SCHEMA,
    }
    for key, expected in expected_requires.items():
        if requires.get(key) != expected:
            raise GateError(f"requires.{key} must be {expected!r}")
    updater_features = requires.get("updater_features")
    if (
        not isinstance(updater_features, list)
        or not updater_features
        or not all(isinstance(item, str) and item for item in updater_features)
    ):
        raise GateError("requires.updater_features must be a non-empty string list")
    missing_features = sorted(REQUIRED_UPDATER_FEATURES - set(updater_features))
    if missing_features:
        raise GateError(f"requires.updater_features missing required features: {missing_features}")
    unsupported_features = sorted(set(updater_features) - SUPPORTED_UPDATER_FEATURES)
    if unsupported_features:
        raise GateError(f"requires.updater_features contains unsupported features: {unsupported_features}")

    return {
        "version": version,
        "payload_sha256": manifest["payload_sha256"].lower(),
    }


def safe_member_path(name: str) -> Path:
    if name.startswith("/") or ".." in Path(name).parts:
        raise GateError(f"unsafe tar member path: {name}")
    return Path(name)


def normalized_member_name(path: Path) -> str:
    normalized = "/".join(path.parts)
    return "" if normalized == "." else normalized


def validate_tar_member(member: tarfile.TarInfo) -> Path:
    path = safe_member_path(member.name)
    if not (member.isfile() or member.isdir()):
        raise GateError(f"unsupported tar member type: {member.name}")
    normalized = normalized_member_name(path)
    lowered = normalized.lower()
    basename = path.name.lower()
    if lowered.startswith(("opt/", "etc/systemd/", "usr/", "lib/systemd/")):
        raise GateError(f"image-fixed/control path is not allowed in player-runtime payload: {member.name}")
    if lowered.startswith(("boot/", "lib/modules/", "lib/firmware/")):
        raise GateError(f"media-system/image path is not allowed in player-runtime payload: {member.name}")
    if lowered.startswith(("data/", "media/", "secrets/", "config/")):
        raise GateError(f"field-data path is not allowed in player-runtime payload: {member.name}")
    if basename in {".env", "config.json", "seed.json", "policy.json", "playlist.json", "state.json", "cache_index.json"}:
        raise GateError(f"field-data file is not allowed in player-runtime payload: {member.name}")
    if basename in {"mpv", "ffmpeg", "ffprobe"} or basename.endswith(".ko"):
        raise GateError(f"media-system file is not allowed in player-runtime payload: {member.name}")
    if basename == MARKER_NAME:
        raise GateError(f"verified marker must be written by updater, not payload: {member.name}")
    if basename in FORBIDDEN_RUNTIME_BASENAMES:
        raise GateError(f"control file is not allowed in player-runtime payload: {member.name}")
    if basename.endswith((".key", ".token", ".secret")):
        raise GateError(f"secret-like file is not allowed in player-runtime payload: {member.name}")
    if member.mode & 0o002:
        raise GateError(f"world-writable file mode is not allowed in player-runtime payload: {member.name}")
    if member.isdir() and normalized not in ALLOWED_PAYLOAD_DIRS:
        raise GateError(f"unexpected player-runtime payload directory: {member.name}")
    if member.isfile() and normalized not in ALLOWED_PAYLOAD_FILES:
        raise GateError(f"unexpected player-runtime payload entry: {member.name}")
    return path


def find_kiosk_member(tf: tarfile.TarFile) -> tarfile.TarInfo:
    kiosk_members = []
    for member in tf.getmembers():
        path = validate_tar_member(member)
        if member.isfile() and path.name == "kiosk.py":
            kiosk_members.append(member)
    if len(kiosk_members) != 1:
        raise GateError(f"expected exactly one kiosk.py, found {len(kiosk_members)}")
    return kiosk_members[0]


def literal_default_config_values(source: str) -> dict[str, Any]:
    """Return literal DEFAULT_CONFIG keys that are safety-critical for C18."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise GateError(f"kiosk.py syntax error: {exc}") from exc

    configs: list[ast.Dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "DEFAULT_CONFIG" for target in node.targets):
            if not isinstance(node.value, ast.Dict):
                raise GateError("DEFAULT_CONFIG must be a dict literal")
            configs.append(node.value)
    if len(configs) != 1:
        raise GateError(f"expected exactly one DEFAULT_CONFIG assignment, found {len(configs)}")

    result: dict[str, Any] = {}
    for key_node, value_node in zip(configs[0].keys, configs[0].values):
        try:
            key = ast.literal_eval(key_node)
        except Exception:
            continue
        if key not in {"mpv_path", "hwdec", "mpv_vo", "mpv_gpu_context"}:
            continue
        try:
            result[str(key)] = ast.literal_eval(value_node)
        except Exception:
            raise GateError(f"DEFAULT_CONFIG[{key!r}] must be a literal value")
    return result


def find_function(tree: ast.AST, name: str) -> ast.FunctionDef:
    matches = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise GateError(f"expected exactly one {name}() function, found {len(matches)}")
    return matches[0]


def cfg_subscript_key(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Subscript):
        return None
    if not isinstance(node.value, ast.Name) or node.value.id != "cfg":
        return None
    try:
        key = ast.literal_eval(node.slice)
    except Exception:
        return None
    return str(key) if isinstance(key, str) else None


def joined_option_cfg_key(node: ast.JoinedStr, prefix: str) -> str | None:
    if len(node.values) != 2:
        return None
    head, tail = node.values
    if not isinstance(head, ast.Constant) or head.value != prefix:
        return None
    if not isinstance(tail, ast.FormattedValue):
        return None
    return cfg_subscript_key(tail.value)


def joined_single_name(node: ast.JoinedStr, prefix: str) -> str | None:
    if len(node.values) != 2:
        return None
    head, tail = node.values
    if not isinstance(head, ast.Constant) or head.value != prefix:
        return None
    if not isinstance(tail, ast.FormattedValue) or not isinstance(tail.value, ast.Name):
        return None
    return tail.value.id


def iter_string_nodes_without_joined_children(node: ast.AST):
    if isinstance(node, ast.JoinedStr):
        yield node
        return
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node
        return
    for child in ast.iter_child_nodes(node):
        yield from iter_string_nodes_without_joined_children(child)


def literal_string_expr(node: ast.AST) -> str | None:
    """Fold only side-effect-free string constants used as MPV argv entries."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = literal_string_expr(node.left)
        right = literal_string_expr(node.right)
        if left is not None and right is not None:
            return left + right
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for item in node.values:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                return None
            parts.append(item.value)
        return "".join(parts)
    return None


def is_dangerous_format_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
        and isinstance(node.func.value, ast.Constant)
        and isinstance(node.func.value.value, str)
        and node.func.value.value.startswith("--")
    )


def is_cfg_like(node: ast.AST) -> bool:
    if isinstance(node, ast.Name) and node.id == "cfg":
        return True
    return isinstance(node, ast.Attribute) and node.attr in {"_cfg", "cfg"}


def assigned_subscript_key(node: ast.AST) -> tuple[ast.AST, str] | None:
    if not isinstance(node, ast.Subscript):
        return None
    try:
        key = ast.literal_eval(node.slice)
    except Exception:
        return None
    if not isinstance(key, str):
        return None
    return node.value, key


def cfg_get_key(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "get":
        return None
    if not isinstance(node.func.value, ast.Name) or node.func.value.id != "cfg":
        return None
    if not node.args:
        return None
    try:
        key = ast.literal_eval(node.args[0])
    except Exception:
        return None
    return str(key) if isinstance(key, str) else None


def validate_mpv_arg_expr(node: ast.AST, *, context: str,
                          counts: dict[str, int] | None = None) -> None:
    if cfg_subscript_key(node) == "mpv_path":
        return

    literal = literal_string_expr(node)
    if literal is not None:
        if any(literal.startswith(item) for item in FORBIDDEN_MPV_OPTION_PREFIXES):
            raise GateError(f"{context} contains forbidden MPV option: {literal}")
        if literal.startswith("--input-ipc-server="):
            raise GateError(f"{context} must not hard-code --input-ipc-server")
        if literal.startswith("--input-conf="):
            raise GateError(f"{context} must not hard-code --input-conf")
        if literal.startswith("--hwdec=") and literal not in {
            "--hwdec=auto",
            "--hwdec=auto-safe",
            f"--hwdec={EXPECTED_HWDEC}",
        }:
            raise GateError(f"{context} contains forbidden hwdec option: {literal}")
        return

    if is_dangerous_format_call(node):
        raise GateError(f"{context} must not construct MPV options with .format()")

    if isinstance(node, ast.JoinedStr):
        prefix = ""
        if node.values and isinstance(node.values[0], ast.Constant) and isinstance(node.values[0].value, str):
            prefix = node.values[0].value
        if prefix == "--input-ipc-server=":
            if joined_option_cfg_key(node, prefix) != "ipc_path":
                raise GateError(f"{context} must derive --input-ipc-server from cfg['ipc_path']")
            if counts is not None:
                counts["ipc"] = counts.get("ipc", 0) + 1
            return
        if prefix == "--hwdec=":
            if joined_option_cfg_key(node, prefix) != "hwdec":
                raise GateError(f"{context} must derive --hwdec from cfg['hwdec']")
            if counts is not None:
                counts["hwdec"] = counts.get("hwdec", 0) + 1
            return
        if prefix == "--input-conf=":
            if joined_single_name(node, prefix) != "hotkey_conf":
                raise GateError(f"{context} must derive --input-conf from hotkey_conf")
            return
        if any(prefix.startswith(item) for item in FORBIDDEN_MPV_OPTION_PREFIXES):
            raise GateError(f"{context} contains forbidden MPV option: {prefix}")
        if prefix in {"--log-file=", "--msg-level=", "--video-rotate="}:
            return
        if prefix.startswith("--"):
            raise GateError(f"{context} contains unsupported dynamic MPV option: {prefix}")
        return

    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "int":
        return

    raise GateError(f"{context} contains unsupported dynamic MPV argument expression")


def validate_append_mpv_option_calls(fn: ast.FunctionDef) -> None:
    allowed = {
        "vo": "mpv_vo",
        "gpu-context": "mpv_gpu_context",
        "ao": "mpv_ao",
    }
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "append_mpv_option_once":
            continue
        if len(node.args) != 3 or not isinstance(node.args[0], ast.Name) or node.args[0].id != "args":
            raise GateError("append_mpv_option_once calls must use args plus one controlled cfg option")
        try:
            option_name = ast.literal_eval(node.args[1])
        except Exception as exc:
            raise GateError("append_mpv_option_once option name must be literal") from exc
        if option_name not in allowed:
            raise GateError(f"append_mpv_option_once uses forbidden MPV option: {option_name!r}")
        if cfg_get_key(node.args[2]) != allowed[option_name]:
            raise GateError(f"append_mpv_option_once {option_name!r} must read cfg[{allowed[option_name]!r}]")


def validate_mpv_args_semantics(tree: ast.AST) -> None:
    fn = find_function(tree, "build_mpv_args")
    validate_append_mpv_option_calls(fn)
    counts: dict[str, int] = {"ipc": 0, "hwdec": 0}
    for node in ast.walk(fn):
        if isinstance(node, ast.List):
            for item in node.elts:
                validate_mpv_arg_expr(item, context="build_mpv_args", counts=counts)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "append":
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "args" and node.args:
                    validate_mpv_arg_expr(node.args[0], context="build_mpv_args", counts=counts)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "args":
                if not isinstance(node.value, ast.List):
                    raise GateError("build_mpv_args must only extend args with literal lists")
                for item in node.value.elts:
                    validate_mpv_arg_expr(item, context="build_mpv_args", counts=counts)

    if counts["ipc"] != 1:
        raise GateError("build_mpv_args must set exactly one controlled --input-ipc-server")
    if counts["hwdec"] != 1:
        raise GateError("build_mpv_args must set exactly one controlled --hwdec")


def is_build_mpv_args_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "build_mpv_args"


def is_subprocess_popen_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Popen"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    )


def mutates_name(node: ast.AST, name: str) -> bool:
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return any(isinstance(target, ast.Name) and target.id == name for target in targets)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name) and node.func.value.id == name:
            return node.func.attr in {"append", "extend", "insert", "remove", "pop", "clear", "sort", "reverse"}
    return False


def stmt_contains_popen(stmt: ast.stmt) -> ast.Call | None:
    for node in ast.walk(stmt):
        if is_subprocess_popen_call(node):
            return node
    return None


def validate_effective_popen_args(tree: ast.AST) -> None:
    fn = find_function(tree, "_start_locked")
    body = list(fn.body)
    build_index: int | None = None
    popen_index: int | None = None
    popen_call: ast.Call | None = None
    build_assigns = 0
    popen_calls = 0

    for index, stmt in enumerate(body):
        if isinstance(stmt, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "args" for target in stmt.targets):
                if not is_build_mpv_args_call(stmt.value):
                    raise GateError("_start_locked must assign args directly from build_mpv_args")
                build_assigns += 1
                build_index = index
        call = stmt_contains_popen(stmt)
        if call is not None:
            popen_calls += 1
            popen_index = index
            popen_call = call

    if build_assigns != 1:
        raise GateError("_start_locked must assign args from build_mpv_args exactly once")
    if popen_calls != 1 or popen_call is None:
        raise GateError("_start_locked must call subprocess.Popen exactly once")
    if popen_index is None or build_index is None or popen_index <= build_index:
        raise GateError("_start_locked must build args before subprocess.Popen")
    if not popen_call.args or not isinstance(popen_call.args[0], ast.Name) or popen_call.args[0].id != "args":
        raise GateError("subprocess.Popen must receive the verified args variable")

    for stmt in body[build_index + 1:popen_index + 1]:
        for node in ast.walk(stmt):
            if mutates_name(node, "args"):
                raise GateError("_start_locked must not mutate args after build_mpv_args")


def validate_hwdec_not_mutated(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                result = assigned_subscript_key(target)
                if result is None:
                    continue
                base, key = result
                if key == "hwdec" and is_cfg_like(base):
                    raise GateError("kiosk.py must not mutate cfg['hwdec'] at runtime")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr not in {"setdefault", "update"} or not is_cfg_like(node.func.value):
                continue
            for arg in node.args:
                if not isinstance(arg, ast.Dict):
                    continue
                for key_node in arg.keys:
                    try:
                        key = ast.literal_eval(key_node)
                    except Exception:
                        continue
                    if key == "hwdec":
                        raise GateError("kiosk.py must not mutate cfg['hwdec'] at runtime")


def validate_kiosk_source(source: str) -> None:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise GateError(f"kiosk.py syntax error: {exc}") from exc
    defaults = literal_default_config_values(source)
    if defaults.get("mpv_path") != EXPECTED_WRAPPER:
        raise GateError("kiosk.py must default mpv_path to the C18 hwdecode wrapper")
    if defaults.get("mpv_path") in {"mpv", "/usr/bin/mpv"}:
        raise GateError("kiosk.py must not default mpv_path to stock mpv")
    hwdec = defaults.get("hwdec")
    if hwdec not in {"auto", "auto-safe", EXPECTED_HWDEC}:
        raise GateError("kiosk.py must default hwdec to auto/auto-safe/v4l2request-copy")
    if hwdec == "no" or "--hwdec=no" in source:
        raise GateError("kiosk.py must not disable hardware decode")
    validate_mpv_args_semantics(tree)
    validate_effective_popen_args(tree)
    validate_hwdec_not_mutated(tree)
    required_anchors = (
        'cfg["mpv_path"]',
        "--hwdec-codecs=h264,mpeg4,mpeg2video",
        "--no-osc",
        '"loadfile"',
        '"replace"',
    )
    for anchor in required_anchors:
        if anchor not in source:
            raise GateError(f"kiosk.py missing required runtime anchor: {anchor}")


def validate_payload(payload: Path) -> dict[str, Any]:
    if not payload.is_file() or payload.is_symlink():
        raise GateError("payload must be a regular file")
    with tempfile.TemporaryDirectory(prefix="c18-player-runtime-gate-") as tmp:
        temp_root = Path(tmp)
        with tarfile.open(payload, "r:gz") as tf:
            kiosk_members = []
            for member in tf.getmembers():
                path = validate_tar_member(member)
                if member.isdir():
                    (temp_root / path).mkdir(parents=True, exist_ok=True)
                    continue
                if path.name == "kiosk.py":
                    kiosk_members.append(member)
                extracted = tf.extractfile(member)
                if extracted is None:
                    raise GateError(f"failed to read payload member: {member.name}")
                target = temp_root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(extracted.read())
                os.chmod(target, member.mode & 0o7777)
            if len(kiosk_members) != 1:
                raise GateError(f"expected exactly one kiosk.py, found {len(kiosk_members)}")
        kiosk_path = temp_root / "kiosk.py"
        source = kiosk_path.read_text(encoding="utf-8")
        validate_kiosk_source(source)
        tree = tree_hash(temp_root)
        py_compile.compile(str(kiosk_path), doraise=True)
    return {
        "kiosk_py_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "tree_sha256": tree,
    }


def validate_release(manifest_path: Path, payload_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    manifest_result = validate_manifest(manifest, payload_path)
    payload_result = validate_payload(payload_path)
    return {
        "schema": SCHEMA,
        "passed": True,
        "component": COMPONENT,
        "manifest": manifest_result,
        "payload": payload_result,
    }


def write_payload(root: Path, version: str, kiosk_source: str, extra_files: dict[str, bytes] | None = None) -> Path:
    work = root / "payload-root"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    (work / "kiosk.py").write_text(kiosk_source, encoding="utf-8")
    for name, content in (extra_files or {}).items():
        target = work / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    payload = root / f"dadooh-{COMPONENT}-{version}.tar.gz"
    with tarfile.open(payload, "w:gz") as tf:
        for path in sorted(work.rglob("*")):
            if not path.is_file():
                continue
            tf.add(path, arcname=str(path.relative_to(work)))
    return payload


def write_manifest(root: Path, version: str, payload: Path, mutate: dict[str, Any] | None = None) -> Path:
    manifest = {
        "schema": UPDATE_SCHEMA,
        "component": COMPONENT,
        "version": version,
        "channel": "homologation",
        "created_at_utc": "2026-06-03T00:00:00Z",
        "source_dirty": False,
        "payload": payload.name,
        "payload_sha256": sha256_file(payload),
        "requires": {
            "device": DEVICE,
            "base_image_min": BASE_IMAGE_LINE,
            "device_track": DEVICE_TRACK,
            "updater_features": sorted(SUPPORTED_UPDATER_FEATURES),
            "media_stack_id": "c18-hwdecode-v4l2request-copy",
            "mpv_wrapper": EXPECTED_WRAPPER,
            "hwdec": EXPECTED_HWDEC,
            "vo": "gpu",
            "gpu_context": "drm",
            "deep_health_schema": EXPECTED_DEEP_HEALTH_SCHEMA,
        },
    }
    if mutate:
        for key, value in mutate.items():
            if key.startswith("requires."):
                manifest["requires"][key.split(".", 1)[1]] = value
            else:
                manifest[key] = value
    path = root / f"dadooh-{COMPONENT}-{version}.manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


class C18PlayerRuntimeReleaseGateSelfTest(unittest.TestCase):
    def with_case(self, version: str = "test-player-runtime") -> tuple[Path, Path, tempfile.TemporaryDirectory[str]]:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        root = Path(tmp.name)
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8")
        payload = write_payload(root, version, source)
        manifest = write_manifest(root, version, payload)
        return manifest, payload, tmp

    def assert_bad_source(self, version: str, source: str, pattern: str) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        payload = write_payload(root, version, source)
        manifest = write_manifest(root, version, payload)
        with self.assertRaisesRegex(GateError, pattern):
            validate_release(manifest, payload)

    def test_accepts_governed_snapshot_payload(self) -> None:
        manifest, payload, tmp = self.with_case("good")
        self.addCleanup(tmp.cleanup)
        result = validate_release(manifest, payload)
        self.assertTrue(result["passed"])

    def test_rejects_stable_channel_until_thaw(self) -> None:
        manifest, payload, tmp = self.with_case("stable-blocked")
        self.addCleanup(tmp.cleanup)
        data = load_json(manifest)
        data["channel"] = "stable"
        manifest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(GateError, "stable releases are blocked"):
            validate_release(manifest, payload)

    def test_rejects_dirty_source_manifest(self) -> None:
        manifest, payload, tmp = self.with_case("dirty-source")
        self.addCleanup(tmp.cleanup)
        data = load_json(manifest)
        data["source_dirty"] = True
        manifest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(GateError, "source_dirty must be false"):
            validate_release(manifest, payload)

    def test_rejects_missing_player_runtime_updater_feature(self) -> None:
        manifest, payload, tmp = self.with_case("missing-runtime-feature")
        self.addCleanup(tmp.cleanup)
        data = load_json(manifest)
        data["requires"]["updater_features"] = [
            item for item in data["requires"]["updater_features"]
            if item != "c18-player-runtime-verify-then-promote-v1"
        ]
        manifest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(GateError, "missing required features"):
            validate_release(manifest, payload)

    def test_rejects_unsupported_player_runtime_updater_feature(self) -> None:
        manifest, payload, tmp = self.with_case("unsupported-runtime-feature")
        self.addCleanup(tmp.cleanup)
        data = load_json(manifest)
        data["requires"]["updater_features"].append("c18-unknown-future-feature")
        manifest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(GateError, "unsupported features"):
            validate_release(manifest, payload)

    def test_rejects_stock_mpv_default(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(EXPECTED_WRAPPER, "mpv")
        payload = write_payload(root, "bad-mpv", source)
        manifest = write_manifest(root, "bad-mpv", payload)
        with self.assertRaisesRegex(GateError, "stock mpv|hwdecode wrapper"):
            validate_release(manifest, payload)

    def test_rejects_hwdec_no_default(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace('"hwdec": "auto"', '"hwdec": "no"')
        payload = write_payload(root, "bad-hwdec-no", source)
        manifest = write_manifest(root, "bad-hwdec-no", payload)
        with self.assertRaisesRegex(GateError, "hardware decode|hwdec"):
            validate_release(manifest, payload)

    def test_rejects_hwdec_no_mpv_arg(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            "return args",
            'args.append("--hwdec=no")\n    return args',
        )
        payload = write_payload(root, "bad-hwdec-arg", source)
        manifest = write_manifest(root, "bad-hwdec-arg", payload)
        with self.assertRaisesRegex(GateError, "hardware decode|hwdec|forbidden"):
            validate_release(manifest, payload)

    def test_rejects_dangerous_mpv_script_arg(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            "return args",
            'args.append("--script=/tmp/evil.lua")\n    return args',
        )
        payload = write_payload(root, "bad-script-arg", source)
        manifest = write_manifest(root, "bad-script-arg", payload)
        with self.assertRaisesRegex(GateError, "forbidden MPV option"):
            validate_release(manifest, payload)

    def test_rejects_callsite_mpv_arg_mutation_after_builder(self) -> None:
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            "args = build_mpv_args(self._cfg, mpv_log_file=mpv_log_file)",
            "args = build_mpv_args(self._cfg, mpv_log_file=mpv_log_file)\n"
            '        args.append("--script=/tmp/evil.lua")',
        )
        self.assert_bad_source("bad-callsite-append", source, "mutate args after build_mpv_args")

    def test_rejects_callsite_mpv_arg_reassignment_after_builder(self) -> None:
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            "args = build_mpv_args(self._cfg, mpv_log_file=mpv_log_file)",
            "args = build_mpv_args(self._cfg, mpv_log_file=mpv_log_file)\n"
            '        args = args + ["--script=/tmp/evil.lua"]',
        )
        self.assert_bad_source("bad-callsite-reassign", source, "args")

    def test_rejects_dynamic_concatenated_dangerous_mpv_arg(self) -> None:
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            "return args",
            'args.append("--scr" + "ipt=/tmp/evil.lua")\n    return args',
        )
        self.assert_bad_source("bad-dynamic-concat", source, "forbidden MPV option")

    def test_rejects_format_constructed_dangerous_mpv_arg(self) -> None:
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            "return args",
            'args.append("--{}={}".format("script", "/tmp/evil.lua"))\n    return args',
        )
        self.assert_bad_source("bad-dynamic-format", source, r"\.format")

    def test_rejects_alternative_builder_at_popen_callsite(self) -> None:
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            "\n\nclass MPVController:",
            '\n\ndef build_alt_mpv_args(cfg: Dict, mpv_log_file: Optional[str] = None) -> List[str]:\n'
            '    return [cfg["mpv_path"], "--script=/tmp/evil.lua"]\n'
            "\n\nclass MPVController:",
        ).replace(
            "args = build_mpv_args(self._cfg, mpv_log_file=mpv_log_file)",
            "args = build_alt_mpv_args(self._cfg, mpv_log_file=mpv_log_file)",
        )
        self.assert_bad_source("bad-alt-builder", source, "build_mpv_args")

    def test_rejects_runtime_hwdec_mutation_before_builder(self) -> None:
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            "args = build_mpv_args(self._cfg, mpv_log_file=mpv_log_file)",
            'self._cfg["hwdec"] = "n" + "o"\n'
            "        args = build_mpv_args(self._cfg, mpv_log_file=mpv_log_file)",
        )
        self.assert_bad_source("bad-hwdec-runtime-mutation", source, r"cfg\['hwdec'\]")

    def test_rejects_external_ipc_server_arg(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            'f"--input-ipc-server={cfg[\'ipc_path\']}",',
            '"--input-ipc-server=/tmp/evil.sock",',
        )
        payload = write_payload(root, "bad-ipc-arg", source)
        manifest = write_manifest(root, "bad-ipc-arg", payload)
        with self.assertRaisesRegex(GateError, "input-ipc-server"):
            validate_release(manifest, payload)

    def test_rejects_hardcoded_input_conf_arg(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            "return args",
            'args.append("--input-conf=/tmp/evil.conf")\n    return args',
        )
        payload = write_payload(root, "bad-input-conf", source)
        manifest = write_manifest(root, "bad-input-conf", payload)
        with self.assertRaisesRegex(GateError, "input-conf"):
            validate_release(manifest, payload)

    def test_rejects_ytdl_and_include_args(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            "return args",
            'args.append("--ytdl=yes")\n    args.append("--include=/tmp/mpv.conf")\n    return args',
        )
        payload = write_payload(root, "bad-ytdl-include", source)
        manifest = write_manifest(root, "bad-ytdl-include", payload)
        with self.assertRaisesRegex(GateError, "forbidden MPV option"):
            validate_release(manifest, payload)

    def test_rejects_osc_enable_arg(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            "return args",
            'args.append("--osc=yes")\n    return args',
        )
        payload = write_payload(root, "bad-osc", source)
        manifest = write_manifest(root, "bad-osc", payload)
        with self.assertRaisesRegex(GateError, "forbidden MPV option"):
            validate_release(manifest, payload)

    def test_rejects_forbidden_append_mpv_option_helper_call(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            'append_mpv_option_once(args, "ao", cfg.get("mpv_ao"))',
            'append_mpv_option_once(args, "ao", cfg.get("mpv_ao"))\n'
            '    append_mpv_option_once(args, "script", "/tmp/evil.lua")',
        )
        payload = write_payload(root, "bad-helper-script", source)
        manifest = write_manifest(root, "bad-helper-script", payload)
        with self.assertRaisesRegex(GateError, "append_mpv_option_once"):
            validate_release(manifest, payload)

    def test_accepts_explicit_c18_hwdec_default(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = SNAPSHOT_KIOSK.read_text(encoding="utf-8").replace(
            '"hwdec": "auto"',
            f'"hwdec": "{EXPECTED_HWDEC}"',
        )
        payload = write_payload(root, "good-explicit-hwdec", source)
        manifest = write_manifest(root, "good-explicit-hwdec", payload)
        result = validate_release(manifest, payload)
        self.assertTrue(result["passed"])

    def test_rejects_field_data_payload(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        payload = write_payload(
            root,
            "bad-config",
            SNAPSHOT_KIOSK.read_text(encoding="utf-8"),
            {"config.json": b"{}"},
        )
        manifest = write_manifest(root, "bad-config", payload)
        with self.assertRaisesRegex(GateError, "field-data"):
            validate_release(manifest, payload)

    def test_rejects_unexpected_payload_entries(self) -> None:
        cases = {
            "cache/item.bin": "unexpected|field-data",
            "playlist.json": "field-data",
            "state.json": "field-data",
            "mpv": "media-system",
            "ffmpeg": "media-system",
            "lib/modules/panfrost.ko": "media-system",
            "helpers/runtime_helper.py": "unexpected player-runtime payload",
        }
        for name, pattern in cases.items():
            with self.subTest(name=name):
                tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
                self.addCleanup(tmp.cleanup)
                root = Path(tmp.name)
                version = re.sub(r"[^A-Za-z0-9._-]+", "-", f"bad-extra-{name}")[:120]
                payload = write_payload(
                    root,
                    version,
                    SNAPSHOT_KIOSK.read_text(encoding="utf-8"),
                    {name: b"nope\n"},
                )
                manifest = write_manifest(root, version, payload)
                with self.assertRaisesRegex(GateError, pattern):
                    validate_release(manifest, payload)

    def test_rejects_control_files(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        payload = write_payload(
            root,
            "bad-control",
            SNAPSHOT_KIOSK.read_text(encoding="utf-8"),
            {"bin/totem-kiosky-launcher.sh": b"#!/bin/sh\n"},
        )
        manifest = write_manifest(root, "bad-control", payload)
        with self.assertRaisesRegex(GateError, "control file"):
            validate_release(manifest, payload)

    def test_rejects_payload_provided_verified_marker(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        payload = write_payload(
            root,
            "bad-marker",
            SNAPSHOT_KIOSK.read_text(encoding="utf-8"),
            {MARKER_NAME: b"{}\n"},
        )
        manifest = write_manifest(root, "bad-marker", payload)
        with self.assertRaisesRegex(GateError, "verified marker"):
            validate_release(manifest, payload)

    def test_rejects_image_fixed_paths(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        payload = write_payload(
            root,
            "bad-opt",
            SNAPSHOT_KIOSK.read_text(encoding="utf-8"),
            {"opt/totem/bin/anything": b"nope\n"},
        )
        manifest = write_manifest(root, "bad-opt", payload)
        with self.assertRaisesRegex(GateError, "image-fixed|control path"):
            validate_release(manifest, payload)

    def test_rejects_tampered_payload_sha(self) -> None:
        manifest, payload, tmp = self.with_case("bad-sha")
        self.addCleanup(tmp.cleanup)
        raw = load_json(manifest)
        raw["payload_sha256"] = "b" * 64
        manifest.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(GateError, "payload_sha256 mismatch"):
            validate_release(manifest, payload)

    def test_rejects_wrong_media_stack_contract(self) -> None:
        manifest, payload, tmp = self.with_case("bad-stack")
        self.addCleanup(tmp.cleanup)
        manifest = write_manifest(Path(tmp.name), "bad-stack", payload, {"requires.hwdec": "no"})
        with self.assertRaisesRegex(GateError, "requires.hwdec"):
            validate_release(manifest, payload)

    def test_rejects_symlink_members(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="c18-player-runtime-release-gate-test-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        payload = root / f"dadooh-{COMPONENT}-bad-link.tar.gz"
        with tarfile.open(payload, "w:gz") as tf:
            info = tarfile.TarInfo("kiosk.py")
            data = SNAPSHOT_KIOSK.read_bytes()
            info.size = len(data)
            tf.addfile(info, fileobj=__import__("io").BytesIO(data))
            link = tarfile.TarInfo("evil-link")
            link.type = tarfile.SYMTYPE
            link.linkname = "/etc/passwd"
            tf.addfile(link)
        manifest = write_manifest(root, "bad-link", payload)
        with self.assertRaisesRegex(GateError, "unsupported tar member type"):
            validate_release(manifest, payload)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(C18PlayerRuntimeReleaseGateSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if not args.manifest or not args.payload:
        raise SystemExit("--manifest and --payload are required unless --self-test is used")
    try:
        result = validate_release(args.manifest, args.payload)
    except Exception as exc:
        print(json.dumps({"schema": SCHEMA, "passed": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
