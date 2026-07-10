#!/usr/bin/env python3
"""Collect C18 player-runtime production auto-pull evidence on a board.

The default path is observational: it reads files, symlinks, systemd state and
journals, and may run the existing read-only playback deep-health collector.
It never applies player-runtime, rolls back player-runtime, or restarts the
player service. The optional --probe-freeze runs the generic public rollback
verb only to prove it is denied with rc=44.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCHEMA = "dadooh.c18.player_runtime.production_autopull_collect.v1"
PHASES = ("pre", "post_apply", "noop", "rollback", "restored")
DEFAULT_DATA_ROOT = Path("/data")
DEFAULT_UPDATECTL = Path("/opt/totem/bin/totem-updatectl")
DEFAULT_AUTHORIZATION = Path("/data/updates/player-runtime-production-autopull.json")
DEFAULT_POLICY = Path("/data/updates/policy.json")
DEFAULT_EXPECTED_IMAGE_TAG = "c18-hwdecode-prod-7"
DEFAULT_TIMER_UNIT = "totem-player-runtime-update-agent.timer"
DEFAULT_SERVICE_UNIT = "totem-player-runtime-update-agent.service"
DEFAULT_PLAYER_UNIT = "kiosky-player.service"
MARKER_NAME = ".release_verified.json"


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json_sha256(data: dict[str, Any]) -> str:
    return sha256_text(json.dumps(data, sort_keys=True, separators=(",", ":")))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_cmd(cmd: list[str], *, timeout: int = 30) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except Exception as exc:
        return {
            "cmd": cmd,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }


def parse_key_value(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key.strip()] = value.strip()
    return fields


def parse_json_from_text(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def read_text(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def load_json_file(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    raw, error = read_text(path)
    if error is not None:
        return None, error
    try:
        data = json.loads(raw or "")
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(data, dict):
        return None, "json_not_object"
    return data, None


def file_snapshot(path: Path, *, parse_json: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file(),
        "is_symlink": path.is_symlink(),
        "sha256": None,
        "bytes": None,
        "read_error": None,
    }
    if path.is_symlink():
        try:
            out["symlink_target"] = os.readlink(path)
            out["resolved_path"] = str(path.resolve(strict=False))
        except OSError as exc:
            out["symlink_error"] = f"{type(exc).__name__}: {exc}"
    if path.is_file():
        try:
            out["sha256"] = sha256_file(path)
            out["bytes"] = path.stat().st_size
        except Exception as exc:
            out["read_error"] = f"{type(exc).__name__}: {exc}"
    if parse_json:
        data, error = load_json_file(path)
        out["data"] = data or {}
        out["json_error"] = error
        out["canonical_json_sha256"] = canonical_json_sha256(data) if data is not None else None
    return out


def image_marker_snapshot(path: Path) -> dict[str, Any]:
    raw, error = read_text(path)
    return {
        "path": str(path),
        "exists": raw is not None,
        "read_error": error,
        "raw_sha256": sha256_text(raw) if raw is not None else None,
        "fields": parse_key_value(raw or ""),
    }


def systemctl_value(*args: str) -> dict[str, Any]:
    result = run_cmd(["systemctl", *args], timeout=20)
    return {
        "returncode": result["returncode"],
        "stdout": str(result["stdout"]).strip(),
        "stderr_tail": str(result["stderr"])[-1000:],
    }


def systemctl_show(unit: str, props: list[str]) -> dict[str, str]:
    cmd = ["systemctl", "show", unit]
    for prop in props:
        cmd.extend(["-p", prop])
    result = run_cmd(cmd, timeout=20)
    values: dict[str, str] = {}
    for line in str(result["stdout"]).splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    values["_returncode"] = str(result["returncode"])
    if result["stderr"]:
        values["_stderr_tail"] = str(result["stderr"])[-1000:]
    return values


def journal_tail(unit: str, lines: int) -> dict[str, Any]:
    result = run_cmd(
        ["journalctl", "-u", unit, "-b", "-n", str(lines), "--no-pager"],
        timeout=30,
    )
    return {
        "returncode": result["returncode"],
        "stderr_tail": str(result["stderr"])[-1000:],
        "lines": str(result["stdout"]).splitlines()[-lines:],
    }


def unit_snapshot(unit: str, *, lines: int, include_enabled: bool = True) -> dict[str, Any]:
    props = [
        "ActiveState",
        "SubState",
        "Result",
        "ExecMainStatus",
        "NRestarts",
        "MainPID",
        "TriggeredBy",
        "Unit",
        "LastTriggerUSec",
        "NextElapseUSecRealtime",
        "InvocationID",
        "ExecMainStartTimestamp",
        "ExecMainExitTimestamp",
    ]
    out: dict[str, Any] = {
        "unit": unit,
        "active": systemctl_value("is-active", unit),
        "show": systemctl_show(unit, props),
        "journal": journal_tail(unit, lines),
    }
    out["active_raw"] = out["active"]["stdout"]
    if include_enabled:
        out["enabled"] = systemctl_value("is-enabled", unit)
        out["enabled_raw"] = out["enabled"]["stdout"]
    return out


def symlink_snapshot(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists() or path.is_symlink(),
        "is_symlink": path.is_symlink(),
        "target": None,
        "resolved_path": None,
        "error": None,
    }
    if path.is_symlink():
        try:
            target = os.readlink(path)
            out["target"] = target
            target_path = Path(target)
            if not target_path.is_absolute():
                target_path = path.parent / target_path
            out["resolved_path"] = str(target_path.resolve(strict=False))
        except Exception as exc:
            out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def release_marker_snapshot(current_link: dict[str, Any]) -> dict[str, Any]:
    resolved = current_link.get("resolved_path")
    if not isinstance(resolved, str) or not resolved:
        return {
            "path": None,
            "exists": False,
            "sha256": None,
            "data": {},
            "json_error": "current_not_linked",
        }
    return file_snapshot(Path(resolved) / MARKER_NAME, parse_json=True)


def collect_state(data_root: Path) -> dict[str, Any]:
    component_base = data_root / "player-runtime"
    current = symlink_snapshot(component_base / "current")
    previous = symlink_snapshot(component_base / "previous")
    state_path = component_base / "state.json"
    state_file = file_snapshot(state_path, parse_json=True)
    state_data = state_file.get("data") if isinstance(state_file.get("data"), dict) else {}
    return {
        "data_root": str(data_root),
        "component_base": str(component_base),
        "releases_dir": str(component_base / "releases"),
        "current_symlink": current,
        "previous_symlink": previous,
        "state_file": state_file,
        "current_release_marker": release_marker_snapshot(current),
        "summary": {
            "current": state_data.get("current"),
            "previous": state_data.get("previous"),
            "last_operation": state_data.get("last_operation"),
            "quarantine": state_data.get("quarantine") or state_data.get("quarantined_identities") or [],
        },
    }


def deep_health_output_dir(args: argparse.Namespace) -> Path:
    if args.deep_health_output_dir is not None:
        return args.deep_health_output_dir
    if args.output is not None:
        return args.output.parent / f"{args.output.stem}-deep-health"
    return Path(tempfile.mkdtemp(prefix="c18-player-runtime-autopull-deep-health-"))


def collect_deep_health(args: argparse.Namespace) -> dict[str, Any]:
    if args.skip_deep_health:
        return {"ran": False, "reason": "skip_deep_health_requested"}
    script = Path(__file__).resolve().with_name("c18_playback_health_collect.py")
    if not script.is_file():
        return {"ran": False, "reason": "collector_missing", "script": str(script)}
    out_dir = deep_health_output_dir(args)
    cmd = [
        sys.executable,
        str(script),
        "--output-dir",
        str(out_dir),
        "--duration-sec",
        str(args.deep_health_duration_sec),
        "--interval-sec",
        str(args.deep_health_interval_sec),
        "--target-mode",
        "service",
        "--match-process-ipc",
        "--json",
    ]
    result = run_cmd(cmd, timeout=max(int(float(args.deep_health_duration_sec) + 90), 120))
    summary = parse_json_from_text(str(result["stdout"]))
    summary_path = out_dir / "playback-deep-health-public.json"
    if summary is None and summary_path.is_file():
        summary, _error = load_json_file(summary_path)
    artifacts: list[dict[str, Any]] = []
    if out_dir.is_dir():
        for path in sorted(out_dir.iterdir(), key=lambda item: item.name):
            if path.is_symlink() or not path.is_file():
                continue
            artifacts.append({
                "name": path.name,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            })
    return {
        "ran": True,
        "cmd": cmd,
        "returncode": result["returncode"],
        "output_dir": str(out_dir),
        "artifact_dir_name": out_dir.name,
        "artifacts": artifacts,
        "summary_path": str(summary_path),
        "summary_sha256": sha256_file(summary_path) if summary_path.is_file() else None,
        "summary": summary or {},
        "stdout_tail": str(result["stdout"])[-4000:],
        "stderr_tail": str(result["stderr"])[-4000:],
    }


def collect_freeze_probe(args: argparse.Namespace) -> dict[str, Any]:
    if not args.probe_freeze:
        return {"ran": False}
    cmd = [str(args.updatectl), "rollback", "--component", "player-runtime"]
    result = run_cmd(cmd, timeout=60)
    return {
        "ran": True,
        "cmd": cmd,
        "expected_returncode": 44,
        "returncode": result["returncode"],
        "stdout_tail": str(result["stdout"])[-2000:],
        "stderr_tail": str(result["stderr"])[-2000:],
    }


def collect(args: argparse.Namespace) -> dict[str, Any]:
    marker_path = args.marker_path or Path(f"/etc/dadooh/{args.expected_image_tag}-image")
    state = collect_state(args.data_root)
    timer = unit_snapshot(args.timer_unit, lines=args.journal_lines)
    service = unit_snapshot(args.service_unit, lines=args.journal_lines)
    player = unit_snapshot(args.player_unit, lines=args.journal_lines)
    return {
        "schema": SCHEMA,
        "phase": args.phase,
        "collected_at_utc": now_utc(),
        "non_claims": [
            "collector_does_not_apply_player_runtime",
            "collector_does_not_rollback_player_runtime",
            "collector_does_not_restart_services",
            "collector_does_not_publish_or_fetch_release_by_default",
        ],
        "paths": {
            "data_root": str(args.data_root),
            "updatectl": str(args.updatectl),
            "authorization": str(args.authorization),
            "policy": str(args.policy),
        },
        "image_marker": image_marker_snapshot(marker_path),
        "updater": file_snapshot(args.updatectl),
        "authorization": file_snapshot(args.authorization, parse_json=True),
        "policy": file_snapshot(args.policy, parse_json=True),
        "systemd": {
            "timer": timer,
            "service": service,
            "player": player,
        },
        "player_service": {
            "unit": args.player_unit,
            "active_raw": player.get("active_raw"),
            "nrestarts": player.get("show", {}).get("NRestarts"),
            "show": player.get("show", {}),
        },
        "state": state,
        "playback_deep_health": collect_deep_health(args),
        "freeze_probe": collect_freeze_probe(args),
    }


class CollectSelfTest(unittest.TestCase):
    def test_parse_key_value(self) -> None:
        self.assertEqual(
            parse_key_value("image_tag=c18\nfinal_image=true\n# ignored\nbad\n"),
            {"image_tag": "c18", "final_image": "true"},
        )

    def test_parse_json_from_text(self) -> None:
        self.assertEqual(parse_json_from_text("INFO\n{\"ok\": true}\n")["ok"], True)

    def test_symlink_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            link = root / "current"
            link.symlink_to("target")
            snap = symlink_snapshot(link)
        self.assertTrue(snap["is_symlink"])
        self.assertEqual(snap["target"], "target")
        self.assertTrue(str(snap["resolved_path"]).endswith("/target"))

    def test_missing_json_file_is_fail_observable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snap = file_snapshot(Path(tmp) / "missing.json", parse_json=True)
        self.assertFalse(snap["exists"])
        self.assertIn("FileNotFoundError", snap["json_error"])

    def test_json_snapshot_binds_parsed_data_to_canonical_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text('{"b": 2, "a": 1}\n', encoding="utf-8")
            snap = file_snapshot(path, parse_json=True)
        self.assertEqual(snap["data"], {"a": 1, "b": 2})
        self.assertEqual(snap["canonical_json_sha256"], canonical_json_sha256(snap["data"]))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--phase", choices=PHASES, default="pre")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--expected-image-tag", default=DEFAULT_EXPECTED_IMAGE_TAG)
    parser.add_argument("--marker-path", type=Path)
    parser.add_argument("--updatectl", type=Path, default=DEFAULT_UPDATECTL)
    parser.add_argument("--authorization", type=Path, default=DEFAULT_AUTHORIZATION)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--timer-unit", default=DEFAULT_TIMER_UNIT)
    parser.add_argument("--service-unit", default=DEFAULT_SERVICE_UNIT)
    parser.add_argument("--player-unit", default=DEFAULT_PLAYER_UNIT)
    parser.add_argument("--journal-lines", type=int, default=160)
    parser.add_argument("--skip-deep-health", action="store_true")
    parser.add_argument("--deep-health-output-dir", type=Path)
    parser.add_argument("--deep-health-duration-sec", type=float, default=30.0)
    parser.add_argument("--deep-health-interval-sec", type=float, default=1.0)
    parser.add_argument("--probe-freeze", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(CollectSelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    payload = collect(args)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    if args.json or args.output is None:
        sys.stdout.write(text)
    else:
        print(f"snapshot={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
