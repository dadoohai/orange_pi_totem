#!/usr/bin/env python3
"""Prepare and validate restricted private values for bench provisioning.

The tool intentionally reports only booleans and policy status. It never prints
the actual api_key, never writes values outside /tmp, and refuses symlinks.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import pathlib
import re
import stat
import sys
import tempfile
from typing import Any
from urllib.parse import urlparse


sys.dont_write_bytecode = True

SCHEMA_VERSION = "dadooh-private-values-prepare.v1"
DEFAULT_PRIVATE_VALUES = "/tmp/dadooh-private-values/private-values.json"
DEFAULT_OUT_DIR = "/tmp/dadooh-private-values-summary"
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
TMP_ROOT = pathlib.Path("/tmp").resolve()
TEMPLATE_PAYLOAD = {
    "api_url": "PREENCHER_LOCALMENTE_SEM_PUBLICAR",
    "api_key": "PREENCHER_LOCALMENTE_SEM_PUBLICAR",
}
PLACEHOLDER_RE = re.compile(
    r"(preencher|cole_aqui|placeholder|replace|changeme|example|exemplo|todo|inserir|sem_publicar)",
    re.IGNORECASE,
)


class PrivateValuesError(ValueError):
    """Raised for expected validation/preparation errors."""


def path_is_under(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def path_is_in_repository(path: pathlib.Path) -> bool:
    current = path if path.is_dir() else path.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return True
    return False


def absolute_no_resolve(raw_path: str) -> pathlib.Path:
    return pathlib.Path(os.path.abspath(str(pathlib.Path(raw_path).expanduser())))


def normalize_tmp_file(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    raw_absolute = absolute_no_resolve(raw_path)
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise PrivateValuesError("private values path must be under /tmp")
    resolved = path.resolve(strict=False)
    if not path_is_under(resolved, TMP_ROOT):
        raise PrivateValuesError("private values path must resolve under /tmp")
    if resolved == TMP_ROOT:
        raise PrivateValuesError("private values path must be a file under a dedicated /tmp directory")
    if path_is_in_repository(resolved):
        raise PrivateValuesError("private values path must not be inside a repository")
    return resolved


def normalize_tmp_dir(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    raw_absolute = absolute_no_resolve(raw_path)
    if not path_is_under(raw_absolute, TMP_ROOT):
        raise PrivateValuesError("out-dir must be under /tmp")
    resolved = path.resolve(strict=False)
    if not path_is_under(resolved, TMP_ROOT):
        raise PrivateValuesError("out-dir must resolve under /tmp")
    if resolved == TMP_ROOT:
        raise PrivateValuesError("out-dir must be a dedicated directory under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise PrivateValuesError("out-dir exists and is not a directory")
    if path_is_in_repository(resolved):
        raise PrivateValuesError("out-dir must not be inside a repository")
    return resolved


def fsync_directory(path: pathlib.Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def prepare_dir(path: pathlib.Path) -> None:
    if path.is_symlink():
        raise PrivateValuesError("private values parent must not be a symlink")
    path.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    if not path.is_dir():
        raise PrivateValuesError("private values parent is not a directory")
    if stat.S_IMODE(path.stat().st_mode) != PRIVATE_DIR_MODE:
        path.chmod(PRIVATE_DIR_MODE)


def atomic_write_json(path: pathlib.Path, payload: dict[str, Any], mode: int) -> None:
    tmp_name: str | None = None
    fd: int | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent), text=True)
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
        path.chmod(mode)
        fsync_directory(path.parent)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def atomic_write_text(path: pathlib.Path, content: str, mode: int) -> None:
    tmp_name: str | None = None
    fd: int | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent), text=True)
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(content if content.endswith("\n") else content + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
        path.chmod(mode)
        fsync_directory(path.parent)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    if not stripped:
        return True
    return bool(PLACEHOLDER_RE.search(stripped))


def is_url_like(value: str | None) -> bool:
    if not value or is_placeholder(value):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def load_private_values(path: pathlib.Path) -> tuple[bool, dict[str, Any], str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, {}, "missing"
    except json.JSONDecodeError:
        return False, {}, "invalid_json"
    except OSError:
        return False, {}, "read_failed"
    if not isinstance(data, dict):
        return False, {}, "json_root_not_object"
    return True, data, None


def inspect_private_values(path: pathlib.Path, *, require_api_url: bool) -> dict[str, Any]:
    status: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "private_values_path": "<tmp-private-values>",
        "path_under_tmp": path_is_under(path.resolve(strict=False), TMP_ROOT),
        "path_inside_repo": path_is_in_repository(path.resolve(strict=False)),
        "file_exists": path.exists(),
        "file_is_symlink": path.is_symlink(),
        "parent_is_symlink": path.parent.is_symlink(),
        "file_mode_600": False,
        "parent_mode_700": False,
        "file_secure": False,
        "parse_ok": False,
        "api_url_present": False,
        "api_url_placeholder": True,
        "api_url_format_ok": False,
        "api_key_present": False,
        "api_key_placeholder": True,
        "environment_id_required_in_file": False,
        "environment_id_source": "wizard",
        "require_api_url": require_api_url,
        "values_printed": False,
        "valid": False,
        "reason": "unknown",
    }
    if status["path_inside_repo"]:
        status["reason"] = "path_inside_repo"
        return status
    if not status["path_under_tmp"]:
        status["reason"] = "path_not_under_tmp"
        return status
    if status["file_is_symlink"] or status["parent_is_symlink"]:
        status["reason"] = "symlink_refused"
        return status
    if not status["file_exists"]:
        status["reason"] = "missing"
        return status
    try:
        parent_mode = stat.S_IMODE(path.parent.stat().st_mode)
        file_mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        status["reason"] = "stat_failed"
        return status
    status["parent_mode_700"] = parent_mode == PRIVATE_DIR_MODE
    status["file_mode_600"] = file_mode == PRIVATE_FILE_MODE
    status["file_secure"] = bool(status["parent_mode_700"] and status["file_mode_600"])
    if not status["file_secure"]:
        status["reason"] = "insecure_permissions"
        return status

    parse_ok, data, parse_reason = load_private_values(path)
    status["parse_ok"] = parse_ok
    if not parse_ok:
        status["reason"] = parse_reason or "parse_failed"
        return status

    api_url = data.get("api_url")
    api_key = data.get("api_key")
    status["api_url_present"] = isinstance(api_url, str) and bool(api_url.strip())
    status["api_url_placeholder"] = is_placeholder(api_url) if status["api_url_present"] else False
    status["api_url_format_ok"] = is_url_like(api_url) if status["api_url_present"] else False
    status["api_key_present"] = isinstance(api_key, str) and bool(api_key.strip())
    status["api_key_placeholder"] = is_placeholder(api_key) if status["api_key_present"] else True

    if not status["api_key_present"]:
        status["reason"] = "api_key_missing"
    elif status["api_key_placeholder"]:
        status["reason"] = "api_key_placeholder"
    elif require_api_url and not status["api_url_present"]:
        status["reason"] = "api_url_missing_no_versioned_default"
    elif status["api_url_present"] and status["api_url_placeholder"]:
        status["reason"] = "api_url_placeholder"
    elif status["api_url_present"] and not status["api_url_format_ok"]:
        status["reason"] = "api_url_invalid"
    else:
        status["reason"] = "ok"
        status["valid"] = True
    return status


def print_summary(status: dict[str, Any]) -> None:
    keys = (
        "api_url_present",
        "api_url_placeholder",
        "api_key_present",
        "api_key_placeholder",
        "file_mode_600",
        "file_secure",
        "environment_id_source",
        "valid",
        "reason",
        "values_printed",
    )
    for key in keys:
        value = status.get(key)
        if isinstance(value, bool):
            value = str(value).lower()
        print(f"{key}={value}")


def write_artifacts(out_dir: pathlib.Path, status: dict[str, Any]) -> None:
    prepare_dir(out_dir)
    atomic_write_json(out_dir / "private-values-summary.json", status, PRIVATE_FILE_MODE)
    summary_lines = [
        "private values sanitized summary",
        f"api_url_present={str(status['api_url_present']).lower()}",
        f"api_url_placeholder={str(status['api_url_placeholder']).lower()}",
        f"api_key_present={str(status['api_key_present']).lower()}",
        f"api_key_placeholder={str(status['api_key_placeholder']).lower()}",
        f"file_mode_600={str(status['file_mode_600']).lower()}",
        f"file_secure={str(status['file_secure']).lower()}",
        "environment_id_source=wizard",
        f"valid={str(status['valid']).lower()}",
        f"reason={status['reason']}",
        "values_printed=false",
    ]
    atomic_write_text(out_dir / "summary.txt", "\n".join(summary_lines), PRIVATE_FILE_MODE)


def write_template(path: pathlib.Path, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    if path.exists() and path.is_symlink():
        raise PrivateValuesError("private values file must not be a symlink")
    prepare_dir(path.parent)
    atomic_write_json(path, TEMPLATE_PAYLOAD, PRIVATE_FILE_MODE)
    return True


def interactive_write(path: pathlib.Path) -> None:
    prepare_dir(path.parent)
    print("api_url_optional_hidden_prompt=true")
    api_url = getpass.getpass("api_url (optional, hidden): ").strip()
    api_key = getpass.getpass("api_key (required, hidden): ").strip()
    payload: dict[str, str] = {"api_key": api_key}
    if api_url:
        payload["api_url"] = api_url
    atomic_write_json(path, payload, PRIVATE_FILE_MODE)


def run_self_test() -> None:
    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-private-values-selftest-", dir="/tmp"))
    try:
        path = root / "private" / "private-values.json"
        out_dir = root / "out"
        write_template(path, force=False)
        template_status = inspect_private_values(path, require_api_url=True)
        if template_status["valid"] or template_status["reason"] != "api_key_placeholder":
            raise AssertionError("template should be invalid because it uses placeholders")

        payload = {
            "api_url": "https://api.dadooh.invalid/search",
            "api_key": "AK_LOCAL_SELF_CHECK_VALUE_123456",
        }
        atomic_write_json(path, payload, PRIVATE_FILE_MODE)
        status = inspect_private_values(path, require_api_url=True)
        write_artifacts(out_dir, status)
        if not status["valid"]:
            raise AssertionError(f"expected valid private values, got {status['reason']}")

        symlink_path = root / "link.json"
        symlink_path.symlink_to(path)
        symlink_status = inspect_private_values(symlink_path, require_api_url=True)
        if symlink_status["reason"] != "symlink_refused":
            raise AssertionError("symlink should be refused")
    finally:
        for child in sorted(root.rglob("*"), reverse=True):
            try:
                if child.is_symlink() or child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            except FileNotFoundError:
                pass
        try:
            root.rmdir()
        except FileNotFoundError:
            pass
    print("self-test: ok")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare restricted private values without printing them.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--interactive", action="store_true")
    mode.add_argument("--validate", action="store_true")
    mode.add_argument("--summary", action="store_true")
    mode.add_argument("--write-template", action="store_true")
    mode.add_argument("--self-test", action="store_true")
    parser.add_argument("--path", default=DEFAULT_PRIVATE_VALUES)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--require-api-url", action="store_true")
    parser.add_argument("--force", action="store_true", help="overwrite an existing private values file in template/interactive modes")
    args = parser.parse_args(argv)

    if args.self_test:
        run_self_test()
        return 0

    try:
        path = normalize_tmp_file(args.path)
        out_dir = normalize_tmp_dir(args.out_dir)
        if args.write_template:
            created = write_template(path, force=bool(args.force))
            status = inspect_private_values(path, require_api_url=args.require_api_url)
            status["template_created"] = created
        elif args.interactive:
            if path.exists() and not args.force:
                raise PrivateValuesError("private values file already exists; pass --force to overwrite")
            interactive_write(path)
            status = inspect_private_values(path, require_api_url=args.require_api_url)
        else:
            status = inspect_private_values(path, require_api_url=args.require_api_url)
        write_artifacts(out_dir, status)
        print_summary(status)
        if args.validate and not status["valid"]:
            return 24
        return 0
    except PrivateValuesError as exc:
        status = {
            "schema_version": SCHEMA_VERSION,
            "private_values_path": "<tmp-private-values>",
            "file_secure": False,
            "file_mode_600": False,
            "api_url_present": False,
            "api_url_placeholder": False,
            "api_key_present": False,
            "api_key_placeholder": True,
            "environment_id_source": "wizard",
            "values_printed": False,
            "valid": False,
            "reason": str(exc).replace("\n", " "),
        }
        try:
            out_dir = normalize_tmp_dir(args.out_dir)
            write_artifacts(out_dir, status)
        except Exception:
            pass
        print_summary(status)
        return 24 if args.validate else 2


if __name__ == "__main__":
    raise SystemExit(main())
